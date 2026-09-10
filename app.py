"""
Плановий Паспорт книжки.

Крок 5 роадмепу: повний розрахунок собівартості (Блок 1 — оригінал-макет,
Блок 2 — друк) і РРЦ за §3-§8 драфту v0.2.
"""

import os

from dotenv import load_dotenv
import streamlit as st

from calculator import calculate
from sheets_reader import load_params, get_tier_for_naklad

load_dotenv()

st.set_page_config(page_title="Плановий Паспорт", page_icon="📖", layout="centered")

SHEET_ID = os.environ.get("PASSPORT_SHEET_ID", "")
params = None

st.title("📖 Плановий Паспорт книжки")
st.caption("Крок 5 роадмепу · повний розрахунок собівартості й РРЦ")

if not SHEET_ID:
    st.error(
        "Не заданий PASSPORT_SHEET_ID у змінних середовища.\n\n"
        "Додайте його в Railway Variables (або .env локально) — "
        "ID Google-таблиці «Параметри_Паспорт_майстер»."
    )
    st.stop()


@st.cache_data(ttl=300, show_spinner="Читаю параметри з Google Sheets…")
def _load(sheet_id: str):
    return load_params(sheet_id)


try:
    params = _load(SHEET_ID)
except Exception as e:
    st.error(f"Не вдалося прочитати таблицю параметрів: {e}")
    st.stop()

if not isinstance(params, dict):
    st.error("Не вдалося отримати словник параметрів із Google Sheets.")
    st.stop()

# ---- Санітарна панель: що реально прочиталось ----
with st.expander("🔧 Діагностика читання параметрів", expanded=True):
    c1, c2, c3 = st.columns(3)
    c1.metric("Тарифи перекладу", len(params["translation"]))
    c2.metric("Тарифи редагування", len(params["editing"]))
    c3.metric("Формати", len(params["formats"]))
    c1.metric("Ефекти обкладинки", len(params["cover"]))
    c2.metric("Тири накладу", len(params["tiers"]))
    c3.metric("Загальні коефіцієнти", len(params["general"]))

    if params["missing"]:
        st.warning(
            f"⚠️ Ще не заповнено {len(params['missing'])} значень "
            f"(жовті клітинки — очікують чисел від технолога):"
        )
        for block, key in params["missing"]:
            st.write(f"— {block}: **{key}**")
    else:
        st.success("Усі параметри заповнені.")

st.divider()

# ---- Форма вводу (§2 драфту v0.2) — поки без розрахунку ----
st.subheader("Вхідні параметри книжки")

col1, col2 = st.columns(2)
with col1:
    fmt = st.selectbox("Формат", options=list(params["formats"].keys()) or ["—"])
    zirka = st.selectbox("Зірковість", options=list(params["translation"].keys()) or ["—"])
    complexity = st.selectbox("Складність", options=list(params["editing"].keys()) or ["—"])
    znaky = st.number_input("Кількість знаків (оригінал)", min_value=0, value=700_000, step=10_000)

with col2:
    is_translated = st.checkbox("Перекладна книга")
    color_mode = st.radio("Колірність блоку", ["1+1 (ч/б)", "4+4 (повний колір)"])
    effect = st.selectbox("Ефекти обкладинки", ["Норма", "Бонус", "Преміум"])
    has_zriz = st.checkbox("Кольоровий зріз")

naklad = st.number_input("Наклад", min_value=100, value=3100, step=100)
avans = st.number_input("Аванс за текст, грн", min_value=0, value=0, step=1000)

st.caption(
    "Обкладинка (дизайн) і ефекти — суми, узгоджені по проєкту вручну "
    "(поки не тарифікуються в майстер-таблиці для Блоку 1)."
)
col3, col4 = st.columns(2)
with col3:
    oblozhka_suma = st.number_input(
        "Обкладинка (дизайн), грн чистими", min_value=0, value=0, step=100
    )
with col4:
    efekty_suma = st.number_input(
        "Ефекти обкладинки, грн чистими", min_value=0, value=0, step=100
    )

st.divider()


def _display_value(value, suffix=""):
    if value is None:
        return "—" + suffix
    return f"{value}{suffix}"


# ---- Показ підтягнутих значень для обраної комбінації (перевірка look-up'ів) ----
st.subheader("Значення з таблиці для обраних параметрів")

tier = get_tier_for_naklad(params["tiers"], naklad)
fmt_data = params["formats"].get(fmt, {})

r1, r2 = st.columns(2)
r1.write(f"**Тариф перекладу ({zirka}):** {params['translation'].get(zirka, '—')} грн/1000 (чистими)")
r1.write(f"**Тариф редагування ({complexity}):** {params['editing'].get(complexity, '—')} грн/1000 (чистими)")
r1.write(f"**Знаків/стор ({fmt}):** {_display_value(fmt_data.get('znakiv_stor'))}")
r1.write(f"**Зошит ({fmt}):** {_display_value(fmt_data.get('zoshyt'))} стор.")

r2.write(f"**Ціна зошита T3 ({fmt}):** {_display_value(fmt_data.get('price_zoshyt'))} грн")
r2.write(f"**Ціна зрізу ({fmt}):** {_display_value(params['zriz'].get(fmt))} грн")
r2.write(f"**Обкладинка ({fmt} / {effect}):** {_display_value(params['cover'].get((fmt, effect)))} грн")
r2.write(f"**Тир ({naklad}):** {tier['tier'] if tier else '—'} (k={tier['k'] if tier else '—'})")

st.divider()

# ---- Розрахунок (§4-§8 драфту) — Блок 1 (оригінал-макет) + заготовка РРЦ ----
st.subheader("Розрахунок собівартості")

if st.button("🧮 Розрахувати", type="primary"):
    inputs = {
        "format": fmt,
        "zirka": zirka,
        "complexity": complexity,
        "perekladna": is_translated,
        "znaky": znaky,
        "oblozhka": oblozhka_suma,
        "efekty": efekty_suma,
        "color_mode": color_mode,
        "effect": effect,
        "has_zriz": has_zriz,
        "naklad": naklad,
        "avans": avans,
    }
    result = calculate(inputs, params)

    st.write(f"**Знаків до розрахунку (з коеф. перекладу):** {result['znaky_rozrah']:,.0f}".replace(",", " "))

    row_labels = {
        "аванс": "Аванс за текст (АЛД)",
        "переклад": "Переклад (АЛД)",
        "редагування": "Редагування (ДП)",
        "коректура": "Коректура (ДП)",
        "обкладинка": "Обкладинка, дизайн (ДП)",
        "ефекти": "Ефекти обкладинки (ДП)",
    }

    def _fmt(v):
        return f"{v:,.2f}".replace(",", " ")

    table_rows = []
    for key, label in row_labels.items():
        row = result["rows"][key]
        table_rows.append(
            {
                "Стаття": label,
                "Чистими, грн": _fmt(row["chysto"]),
                "Тіло, грн": _fmt(row["tilo"]),
                "ЄСВ, грн": _fmt(row["esv"]),
                "Разом, грн": _fmt(row["razom"]),
            }
        )
    table_rows.append(
        {
            "Стаття": "Інші витрати (12%)",
            "Чистими, грн": "—",
            "Тіло, грн": "—",
            "ЄСВ, грн": "—",
            "Разом, грн": _fmt(result["inshi"]),
        }
    )

    st.table(table_rows)

    st.metric("ОРИГІНАЛ-МАКЕТ, грн", f"{result['oryhinal_maket']:,.2f}".replace(",", " "))

    st.divider()
    st.subheader("Друк (за 1 прим.)")

    block2 = result["block2"]
    if block2 is None:
        st.warning(
            "друк не порахований — для обраної комбінації формат/ефект/наклад "
            "бракує даних у майстер-таблиці (ціна зошита, обкладинки, зрізу, "
            "тир або множник 4+4)."
        )
    else:
        print_rows = [
            {"Стаття": "Блок", "Разом, грн": _fmt(block2["blok"])},
            {"Стаття": "Обкладинка (друк)", "Разом, грн": _fmt(block2["obkladynka_dr"])},
            {"Стаття": "Кольоровий зріз", "Разом, грн": _fmt(block2["zriz"])},
            {"Стаття": "Друк за 1 прим., разом", "Разом, грн": _fmt(block2["razom"])},
        ]
        st.table(print_rows)
        st.caption(
            f"Сторінок: {block2['storinky']:.1f} · Зошитів: {block2['zoshytiv']} · "
            f"Тир: {block2['tier']['tier']} (k={block2['tier']['k']}) · "
            f"K_колір: {block2['k_kolir']}"
        )

    st.divider()
    st.subheader("РРЦ")
    if result["rrc"] is None:
        st.warning("РРЦ не порахований — немає друк_за_шт (див. попередження вище). РРЦ: —")
    else:
        st.metric("РРЦ, грн", result["rrc"])
