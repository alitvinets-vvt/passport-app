"""
Плановий Паспорт книжки — СКЕЛЕТ (крок 3 роадмепу).

Мета цього файлу: підтвердити, що застосунок піднімається на Railway,
підключається до Google Sheets і коректно читає майстер-таблицю параметрів.
Розрахунків (§4 драфту v0.2) тут свідомо ще немає — це крок 4.
"""

import os

from dotenv import load_dotenv
import streamlit as st

from sheets_reader import load_params, get_tier_for_naklad

load_dotenv()

st.set_page_config(page_title="Плановий Паспорт — скелет", page_icon="📖", layout="centered")

SHEET_ID = os.environ.get("PASSPORT_SHEET_ID", "")
params = None

st.title("📖 Плановий Паспорт книжки")
st.caption("Скелет застосунку · крок 3 роадмепу · без розрахунків")

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

st.info(
    "Розрахунок собівартості й РРЦ (§4–7 драфту) підключається на кроці 4. "
    "Цей екран лише підтверджує, що всі look-up'и з майстер-таблиці працюють коректно."
)
