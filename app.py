"""
Плановий Паспорт книжки.

Крок 5 роадмепу: повний розрахунок собівартості (Блок 1 — оригінал-макет,
Блок 2 — друк) і РРЦ за §3-§8 драфту v0.2.
"""

import datetime
import os
import re

from dotenv import load_dotenv
import pandas as pd
import streamlit as st

from calculator import calculate, compare_naklady, default_naklady
from export import export_to_xlsx
from sheets_reader import load_params, get_tier_for_naklad

load_dotenv()

st.set_page_config(page_title="Плановий Паспорт", page_icon="📖", layout="centered")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Montserrat', -apple-system, sans-serif;
    }

    /* Montserrat — єдиний шрифт застосунку, без винятків. */
    h1, h2, h3, [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {
        font-family: 'Montserrat', -apple-system, sans-serif !important;
        font-weight: 600;
        color: #241A17;
    }

    h1, [data-testid="stMarkdownContainer"] h1 {
        font-weight: 700;
        font-size: 1.9rem !important;
        line-height: 1.35 !important;
        color: #241A17;
        letter-spacing: 0;
    }

    [data-testid="stAppViewContainer"] {
        background-color: #FBF8F3;
    }

    /* Компактність: менше повітря між полями форми, вужчі відступи
       контейнера й заголовків. padding-top не менше висоти
       фіксованого хедера Streamlit (~60px) — інакше він перекриває
       верх H1 (саме це, а не шрифт, різало заголовок раніше). */
    .block-container {
        padding-top: 4rem !important;
        padding-bottom: 2rem !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0.25rem !important;
    }
    div[data-testid="stCaptionContainer"] {
        margin: 0 !important;
    }
    h1, h2, h3 {
        margin-top: 0.2rem !important;
        margin-bottom: 0.2rem !important;
    }
    hr {
        margin: 0.6rem 0 !important;
    }
    div[data-baseweb="select"] > div {
        min-height: 2.3rem;
    }
    div[data-testid="stElementContainer"] {
        margin-bottom: 0.15rem !important;
    }
    [data-testid="stWidgetLabel"] {
        margin-bottom: 0.1rem !important;
        padding-bottom: 0 !important;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 1rem !important;
    }
    .stCheckbox {
        padding-top: 0.15rem !important;
    }

    /* Прибрати +/- степери в number_input — поля займають менше висоти. */
    button[data-testid="stNumberInputStepDown"],
    button[data-testid="stNumberInputStepUp"] {
        display: none;
    }

    .stNumberInput label,
    .stSelectbox label,
    .stCheckbox label,
    .stRadio label {
        font-size: 0.9rem;
    }

    .form-group-title {
        font-family: 'Montserrat', -apple-system, sans-serif;
        font-weight: 600;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #7A2331;
        margin: 0.1rem 0 0.3rem 0;
    }

    /* Підзаголовки підгруп усередині колонки форми — дрібний сірий caps,
       без рамок/плашок, щоб не конкурувати з бордовими заголовками колонок. */
    .form-subgroup-title {
        font-family: 'Montserrat', -apple-system, sans-serif;
        font-weight: 600;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #8a7f6d;
        margin: 0.5rem 0 0.2rem 0;
    }

    /* Поля "Індекс проєкту"/"Назва проєкту" — приглушений світло-зелений
       фон замість кремового решти форми, щоб виділити ідентифікацію
       проєкту як окрему категорію, а не параметр розрахунку. */
    .st-key-project_index_field [data-testid="stTextInputRootElement"],
    .st-key-project_name_field [data-testid="stTextInputRootElement"] {
        background-color: #DCE8D8 !important;
        border-color: #C3D3BE !important;
    }

    /* Боксовані картки для головних метрик результату (як у макеті) —
       Streamlit-контейнер st.metric, а не власна розмітка. */
    div[data-testid="stMetric"] {
        background-color: #F1E9DC;
        border: 1px solid #E6DCC8;
        border-radius: 6px;
        padding: 0.9rem 1.1rem;
    }

    div[data-testid="stMetricValue"] {
        font-family: 'Montserrat', -apple-system, sans-serif;
        font-weight: 700;
        color: #7A2331;
    }

    /* Компактний список у sidebar-панелі "Стан даних" — вузька колонка,
       тому звичайний текстовий рядок замість st.metric (обрізало назви). */
    .sidebar-stat-row {
        font-size: 0.85rem;
        color: #241A17;
        padding: 0.1rem 0;
    }
    .sidebar-stat-row b {
        color: #7A2331;
        font-weight: 700;
    }

    .stButton > button[kind="primary"] {
        background-color: #7A2331;
        border-color: #7A2331;
        font-weight: 600;
        border-radius: 8px;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #5C1A25;
        border-color: #5C1A25;
    }

    .rrc-hero {
        background: linear-gradient(135deg, #7A2331, #5C1A25);
        color: #FBF8F3;
        border-radius: 12px;
        padding: 1.1rem 1.5rem;
        text-align: center;
        margin: 0.5rem 0 0.8rem 0;
    }
    .rrc-hero .rrc-label {
        font-family: 'Montserrat', -apple-system, sans-serif;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        opacity: 0.85;
    }
    .rrc-hero .rrc-value {
        font-family: 'Montserrat', -apple-system, sans-serif;
        font-weight: 700;
        font-size: 3rem;
        line-height: 1.2;
    }

    .detail-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.92rem;
        margin: 0.3rem 0 0.6rem 0;
    }
    .detail-table th {
        text-align: left;
        padding: 0.4rem 0.6rem;
        border-bottom: 2px solid #7A2331;
        color: #7A2331;
        font-weight: 600;
    }
    .detail-table td {
        padding: 0.35rem 0.6rem;
    }
    .detail-table tbody tr:nth-child(even) {
        background-color: #F1E9DC;
    }
    .detail-table tbody tr.total-row td {
        font-weight: 700;
        border-top: 2px solid #7A2331;
    }

    /* Таблиця "Порівняння накладів" — колонка на кожен наклад, під
       числом накладу в шапці дрібна підказка з тиром/смугою. */
    .comparison-table th {
        text-align: right;
        white-space: nowrap;
    }
    .comparison-table th:first-child,
    .comparison-table td:first-child {
        text-align: left;
    }
    .comparison-table td {
        text-align: right;
    }
    .comparison-band {
        display: block;
        font-size: 0.75rem;
        font-weight: 400;
        text-transform: none;
        color: #8a7f6d;
        letter-spacing: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SHEET_ID = os.environ.get("PASSPORT_SHEET_ID", "")
params = None

st.title("📖 Плановий Паспорт книжки")

with st.sidebar:
    if st.button("🔄 Оновити дані з таблиці", help="Скинути кеш і перечитати параметри з Google Sheets"):
        st.cache_data.clear()
        st.rerun()

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

# ---- Санітарна панель: що реально прочиталось — у sidebar, унизу, згорнута ----
with st.sidebar:
    st.divider()
    with st.expander("Стан даних", expanded=False):
        data_counts = [
            ("Тарифи перекладу", len(params["translation"])),
            ("Тарифи редагування", len(params["editing"])),
            ("Формати", len(params["formats"])),
            ("Ефекти обкладинки", len(params["cover"])),
            ("Тири накладу", len(params["tiers"])),
            ("Загальні коефіцієнти", len(params["general"])),
        ]
        st.markdown(
            "".join(
                f'<div class="sidebar-stat-row">{label}: <b>{count}</b></div>'
                for label, count in data_counts
            ),
            unsafe_allow_html=True,
        )

        if params["missing"]:
            st.warning(
                f"⚠️ Ще не заповнено {len(params['missing'])} значень "
                f"(жовті клітинки — очікують чисел від технолога):"
            )
            for block, key in params["missing"]:
                st.write(f"— {block}: **{key}**")
        else:
            st.success("Усі параметри заповнені.")

# ---- Форма вводу (§2 драфту v0.2) — поки без розрахунку ----
st.subheader("Вхідні параметри книжки")

st.markdown('<p class="form-group-title">Ідентифікація проєкту</p>', unsafe_allow_html=True)
proj_col1, proj_col2 = st.columns(2)
with proj_col1:
    project_index = st.text_input("Індекс проєкту", key="project_index_field")
with proj_col2:
    project_name = st.text_input("Назва проєкту", key="project_name_field")

col1, col2 = st.columns(2)
with col1:
    st.markdown('<p class="form-group-title">Текст книги</p>', unsafe_allow_html=True)

    st.markdown('<p class="form-subgroup-title">Параметри тексту</p>', unsafe_allow_html=True)
    fmt = st.selectbox("Формат", options=list(params["formats"].keys()) or ["—"])
    zirka = st.selectbox("Зірковість", options=list(params["translation"].keys()) or ["—"])
    complexity = st.selectbox("Складність", options=list(params["editing"].keys()) or ["—"])

    st.markdown('<p class="form-subgroup-title">Обсяг і тираж</p>', unsafe_allow_html=True)
    znaky = st.number_input("Кількість знаків (оригінал)", min_value=0, value=700_000, step=10_000)
    is_translated = st.checkbox("Перекладна книга")
    storinkovist_multiplier = st.number_input(
        "Множник сторінковості", min_value=1.0, value=1.0, step=0.05,
        help=(
            "За замовчуванням 1,0 — не впливає на розрахунок. Збільшуйте для "
            "проєктів з ілюструванням або складною версткою, яка робить текст "
            "об'ємнішим (наприклад, 1,2 = +20% сторінок)."
        ),
    )
    naklad = st.number_input("Наклад", min_value=100, value=3100, step=100)

with col2:
    st.markdown('<p class="form-group-title">Друк та оформлення</p>', unsafe_allow_html=True)

    st.markdown('<p class="form-subgroup-title">Оформлення блоку</p>', unsafe_allow_html=True)
    color_mode = st.selectbox("Колірність блоку", ["1+1 (ч/б)", "4+4 (повний колір)"])
    effect = st.selectbox("Ефекти обкладинки", ["Норма", "Бонус", "Преміум"])
    has_zriz = st.checkbox("Кольоровий зріз")

    st.markdown('<p class="form-subgroup-title">Витрати на обкладинку</p>', unsafe_allow_html=True)
    _suma_help = "Сума узгоджена вручну (поки без тарифів у таблиці)."
    oblozhka_suma = st.number_input(
        "Обкладинка (дизайн), грн чистими", min_value=0, value=0, step=100,
        help=_suma_help,
    )
    efekty_suma = st.number_input(
        "Ефекти обкладинки, грн чистими", min_value=0, value=0, step=100,
        help=_suma_help,
    )
    avans = st.number_input("Аванс за текст, грн", min_value=0, value=0, step=1000)

def _display_value(value, suffix=""):
    if value is None:
        return "—" + suffix
    return f"{value}{suffix}"


_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def _sanitize_filename_part(s: str) -> str:
    """Прибирає символи, недопустимі в назві файлу (Windows-обмеження)."""
    return _INVALID_FILENAME_CHARS.sub("_", s.strip())


def _render_table(rows, total_labels=()):
    """Zebra-таблиця з підсумковими рядками жирним (замість st.table)."""
    if not rows:
        return
    columns = list(rows[0].keys())
    header = "".join(f"<th>{c}</th>" for c in columns)
    body = []
    for row in rows:
        cls = ' class="total-row"' if row.get("Стаття") in total_labels else ""
        cells = "".join(f"<td>{row[c]}</td>" for c in columns)
        body.append(f"<tr{cls}>{cells}</tr>")
    st.markdown(
        f'<table class="detail-table"><thead><tr>{header}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>',
        unsafe_allow_html=True,
    )


def _render_comparison_table(rows):
    """Таблиця "Порівняння накладів": РЯДКИ = показники, КОЛОНКИ = наклади
    (кожен рядок з rows — один виклик calculate() із compare_naklady())."""
    if not rows:
        return

    def _om_per_unit(r):
        return r["result"]["oryhinal_maket"] / r["naklad"] if r["naklad"] else None

    def _sobivartist(r):
        druk = r["result"]["druk_za_sht"]
        om_unit = _om_per_unit(r)
        if druk is None or om_unit is None:
            return None
        return om_unit + druk

    headers = []
    for r in rows:
        band = r["tier"]["band"] if r["tier"] else "—"
        naklad_label = f"{int(r['naklad']):,}".replace(",", " ")
        headers.append(f"{naklad_label}<br><span class='comparison-band'>{band}</span>")

    metric_rows = [
        ("Наклад", lambda r: f"{int(r['naklad']):,}".replace(",", " "), False),
        ("Тир", lambda r: r["tier"]["tier"] if r["tier"] else "—", False),
        (
            "ОРИГІНАЛ-МАКЕТ на 1 прим., грн",
            lambda r: _fmt(_om_per_unit(r)) if _om_per_unit(r) is not None else "—",
            False,
        ),
        (
            "Друк за 1 прим., грн",
            lambda r: _fmt(r["result"]["druk_za_sht"]) if r["result"]["druk_za_sht"] is not None else "—",
            False,
        ),
        (
            "Собівартість 1 прим., грн",
            lambda r: _fmt(_sobivartist(r)) if _sobivartist(r) is not None else "—",
            False,
        ),
        (
            "РРЦ, грн",
            lambda r: str(r["result"]["rrc"]) if r["result"]["rrc"] is not None else "—",
            True,
        ),
    ]

    header_html = "<th>Показник</th>" + "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for label, fn, is_total in metric_rows:
        cls = ' class="total-row"' if is_total else ""
        cells = "".join(f"<td>{fn(r)}</td>" for r in rows)
        body.append(f"<tr{cls}><td>{label}</td>{cells}</tr>")

    st.markdown(
        f'<table class="detail-table comparison-table"><thead><tr>{header_html}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>',
        unsafe_allow_html=True,
    )


# ---- Показ підтягнутих значень для обраної комбінації (перевірка look-up'ів) ----
# Службовий блок, як і "Діагностика" вище — згорнутий, щоб уся форма
# вводу + кнопка вміщались на одному екрані.
with st.expander("📋 Значення з таблиці для обраних параметрів", expanded=False):
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

def _fmt(v):
    return f"{v:,.2f}".replace(",", " ")


# Параметри книги без накладу — спільні для одиночного розрахунку й
# порівняння накладів (щоб не вводити книжку двічі).
book_inputs = {
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
    "avans": avans,
    "storinkovist_multiplier": storinkovist_multiplier,
}

tab_single, tab_compare = st.tabs(["🧮 Одиночний розрахунок", "📊 Порівняння накладів"])

with tab_single:
    if st.button("🧮 Розрахувати", type="primary"):
        inputs = {**book_inputs, "naklad": naklad}
        st.session_state["passport_inputs"] = inputs
        st.session_state["passport_result"] = calculate(inputs, params)

    # ---- Результат живе в session_state, щоб пережити rerun від кнопки експорту ----
    if "passport_result" in st.session_state:
        inputs = st.session_state["passport_inputs"]
        result = st.session_state["passport_result"]
        block2 = result["block2"]

        # ---- Головні результати: картки-метрики + РРЦ як акцент ----
        m1, m2 = st.columns(2)
        m1.metric("ОРИГІНАЛ-МАКЕТ, грн", _fmt(result["oryhinal_maket"]))
        m2.metric("Друк за 1 прим., грн", _fmt(block2["razom"]) if block2 else "—")

        if result["rrc"] is None:
            st.warning(
                "РРЦ не порахований — для обраної комбінації формат/ефект/наклад "
                "бракує даних у майстер-таблиці (ціна зошита, обкладинки, зрізу, "
                "тир або множник 4+4)."
            )
        else:
            st.markdown(
                f'<div class="rrc-hero"><div class="rrc-label">РРЦ</div>'
                f'<div class="rrc-value">{result["rrc"]} грн</div></div>',
                unsafe_allow_html=True,
            )

        project_ready = bool(project_index.strip()) and bool(project_name.strip())
        if not project_ready:
            st.warning("Заповніть індекс і назву проєкту перед експортом.")

        export_inputs = {
            **inputs,
            "project_index": project_index.strip(),
            "project_name": project_name.strip(),
        }
        xlsx_buffer = export_to_xlsx(export_inputs, result) if project_ready else None
        date_str = datetime.date.today().strftime("%Y%m%d")
        if project_ready:
            file_name = (
                f"{_sanitize_filename_part(project_index)}_"
                f"{_sanitize_filename_part(project_name)}_"
                f"Плановий_паспорт_{date_str}.xlsx"
            )
        else:
            file_name = f"Плановий_паспорт_{date_str}.xlsx"
        st.download_button(
            "📥 Експортувати в xlsx",
            data=xlsx_buffer if project_ready else b"",
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=not project_ready,
        )

        # ---- Деталізація за статтями — для звірки, не для щоденного погляду ----
        with st.expander("🧾 Деталізація розрахунку", expanded=False):
            st.write(
                f"**Знаків до розрахунку (з коеф. перекладу):** "
                f"{result['znaky_rozrah']:,.0f}".replace(",", " ")
            )

            row_labels = {
                "аванс": "Аванс за текст (АЛД)",
                "переклад": "Переклад (АЛД)",
                "редагування": "Редагування (ДП)",
                "коректура": "Коректура (ДП)",
                "обкладинка": "Обкладинка, дизайн (ДП)",
                "ефекти": "Ефекти обкладинки (ДП)",
            }
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
                    "Чистими, грн": _fmt(0),
                    "Тіло, грн": _fmt(0),
                    "ЄСВ, грн": _fmt(0),
                    "Разом, грн": _fmt(result["inshi"]),
                }
            )
            table_rows.append(
                {
                    "Стаття": "Разом",
                    "Чистими, грн": _fmt(sum(r["chysto"] for r in result["rows"].values())),
                    "Тіло, грн": _fmt(sum(r["tilo"] for r in result["rows"].values())),
                    "ЄСВ, грн": _fmt(sum(r["esv"] for r in result["rows"].values())),
                    "Разом, грн": _fmt(result["oryhinal_maket"]),
                }
            )
            _render_table(table_rows, total_labels={"Разом"})

            st.markdown("**Друк (за 1 прим.)**")
            if block2 is None:
                st.caption("Друк не порахований — див. попередження вище.")
            else:
                print_rows = [
                    {"Стаття": "Блок", "Разом, грн": _fmt(block2["blok"])},
                    {"Стаття": "Обкладинка (друк)", "Разом, грн": _fmt(block2["obkladynka_dr"])},
                    {"Стаття": "Кольоровий зріз", "Разом, грн": _fmt(block2["zriz"])},
                    {"Стаття": "Друк за 1 прим., разом", "Разом, грн": _fmt(block2["razom"])},
                ]
                _render_table(print_rows, total_labels={"Друк за 1 прим., разом"})
                st.caption(
                    f"Сторінок: {block2['storinky']:.1f} · Зошитів: {block2['zoshytiv']} · "
                    f"Тир: {block2['tier']['tier']} (k={block2['tier']['k']}) · "
                    f"K_колір: {block2['k_kolir']}"
                )

with tab_compare:
    st.caption(
        "Ті самі параметри книги — собівартість і РРЦ одразу на кількох "
        "накладах, по одному репрезентативному на кожен тир. Список можна "
        "редагувати: додавайте чи прибирайте рядки."
    )
    naklad_editor_df = pd.DataFrame({"Наклад": default_naklady(params["tiers"])})
    edited_naklady_df = st.data_editor(
        naklad_editor_df,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Наклад": st.column_config.NumberColumn("Наклад", min_value=1, step=100)
        },
        key="naklad_compare_editor",
    )

    if st.button("📊 Порівняти", type="primary"):
        naklad_list = sorted(
            {float(n) for n in edited_naklady_df["Наклад"].dropna().tolist() if n and n > 0}
        )
        if not naklad_list:
            st.warning("Додайте хоча б один наклад для порівняння.")
            st.session_state.pop("comparison_rows", None)
        else:
            st.session_state["comparison_rows"] = compare_naklady(book_inputs, params, naklad_list)

    if "comparison_rows" in st.session_state:
        _render_comparison_table(st.session_state["comparison_rows"])
