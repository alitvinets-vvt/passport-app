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

from calculator import (
    DEFAULT_FACT_NAKLADY,
    DEFAULT_RETAIL_DISCOUNT,
    calculate,
    calculate_fact,
    compare_naklady,
    compare_naklady_fact,
    default_naklady,
    get_channel_mix_defaults,
    get_retail_discount,
)
from export import export_fact_to_xlsx, export_to_xlsx
from sheets_reader import load_params, get_tier_for_naklad

load_dotenv()

# Лейбли для випадних списків — ТІЛЬКИ візуальне відображення. Внутрішній
# ключ, яким код шукає тариф у params["translation"]/["cover"]/["editing"],
# лишається "5★"/"Норма"/"простий" тощо без змін (див. selectbox з
# format_func нижче) — інакше пошук тарифу зламається.
ZIRKA_LABELS = {
    "5★": "5★ Дорого Якісно",
    "4★": "4★ Репутаційно Якісно",
    "3★": "3★ Терміново Нормально",
    "2★": "2★ Не терміново Якісно",
    "1★": "1★ Спокійний режим",
}
COVER_EFFECT_LABELS = {
    "Норма": "Норма (УФ лак)",
    "Бонус": "Бонус (+ штамп + софттач)",
    "Преміум": "Преміум (+ ляссе + суперобкладинка)",
}
EDITING_LABELS = {
    "простий": "просте",
    "помірний": "помірне",
    "складний": "складне",
}

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
    /* Жирний текст вкладок — і верхнього рівня (Плановий Паспорт /
       Факт → наклади), і підвкладок розрахунку (Одиночний розрахунок /
       Порівняння накладів) — обидва пуляться цим самим селектором,
       бо це один і той самий компонент st.tabs(). */
    [data-testid="stTab"] p {
        font-weight: 700 !important;
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

    /* Значення в клітинках — і введені вручну (число/текст/вибір),
       і показники результату (метрик-картки) — однаковий розмір
       шрифту між собою, щоб жодне число не було "випадково" крупнішим. */
    .stNumberInput input,
    .stTextInput input,
    div[data-baseweb="select"] > div,
    .metric-card .metric-value {
        font-family: 'Montserrat', -apple-system, sans-serif !important;
        font-size: 1.05rem !important;
    }

    /* Поля "Індекс проєкту"/"Назва проєкту" — приглушений світло-зелений
       фон замість кремового решти форми, щоб виділити ідентифікацію
       проєкту як окрему категорію, а не параметр розрахунку. */
    .st-key-project_index_field [data-testid="stTextInputRootElement"],
    .st-key-project_name_field [data-testid="stTextInputRootElement"],
    .st-key-fact_project_index_field [data-testid="stTextInputRootElement"],
    .st-key-fact_project_name_field [data-testid="stTextInputRootElement"] {
        background-color: #DCE8D8 !important;
        border-color: #C3D3BE !important;
    }

    /* Боксовані картки для головних метрик результату (як у макеті) —
       власна розмітка замість st.metric: у st.metric підпис і число
       обрізаються трьома крапками на довгих значеннях (6+ значущих
       цифр у сумі, довгий підпис "Точка беззбитковості, прим.") і не
       переносяться — тут підпис переноситься по словах, а число
       переноситься, а не ховається. */
    .metric-card {
        background-color: #F1E9DC;
        border: 1px solid #E6DCC8;
        border-radius: 6px;
        padding: 0.9rem 1.1rem;
        height: 100%;
        box-sizing: border-box;
    }
    .metric-card .metric-label {
        font-family: 'Montserrat', -apple-system, sans-serif;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        color: #4A4238;
        font-size: 0.75rem;
        white-space: normal;
        overflow-wrap: break-word;
        margin-bottom: 0.3rem;
    }
    .metric-card .metric-value {
        font-family: 'Montserrat', -apple-system, sans-serif;
        font-weight: 700;
        color: #7A2331;
        font-size: 1.5rem;
        line-height: 1.25;
        white-space: normal;
        overflow-wrap: break-word;
        word-break: break-word;
    }
    .metric-card .metric-caption {
        font-family: 'Montserrat', -apple-system, sans-serif;
        font-size: 0.8rem;
        color: #8a7f6d;
        margin-top: 0.3rem;
    }
    .metric-card .metric-help {
        cursor: help;
        color: #8a7f6d;
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
        color: #4A4238;
        letter-spacing: 0;
    }

    /* Блок "Значення з таблиці для обраних параметрів" — довідковий,
       не має конкурувати з основними полями форми й результатами:
       розмір шрифту зменшено на 30% від базового (0.7em). */
    .st-key-lookup_values_block, .st-key-lookup_values_block p {
        font-size: 0.7em;
    }

    /* Три підказки, які мають читатись як звичайний текст форми, а не
       приглушений caption (st.caption за замовчуванням малює текст із
       opacity: 0.6 поверх основного кольору — тут це прибирається). */
    .st-key-compare_intro_caption [data-testid="stCaptionContainer"],
    .st-key-fact_intro_caption [data-testid="stCaptionContainer"],
    .st-key-fact_naklad_caption [data-testid="stCaptionContainer"] {
        opacity: 1 !important;
        color: #241A17 !important;
    }

    /* Технічні caption'и в "Деталізація розрахунку" — лишаються
       другорядними за роллю, але темнішими й контрастнішими за
       кремовий фон, ніж стандартний приглушений st.caption. */
    .st-key-print_missing_caption [data-testid="stCaptionContainer"],
    .st-key-print_stats_caption [data-testid="stCaptionContainer"] {
        opacity: 1 !important;
        color: #4A4238 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SHEET_ID = os.environ.get("PASSPORT_SHEET_ID", "")
params = None

st.title("🧮 Калькулятор собівартості і РРЦ")

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

        if "Знижка рітейлу" not in params["general"]:
            st.warning(
                f"⚠️ Параметр «Знижка рітейлу» не знайдено в блоці ЗАГАЛЬНІ — "
                f"використано дефолт {int(DEFAULT_RETAIL_DISCOUNT * 100)}% "
                f"для точки беззбитковості."
            )

tab_plan, tab_fact = st.tabs(["📖 Плановий Паспорт", "🧾 Факт → наклади"])

with tab_plan:
    # ---- Форма вводу (§2 драфту v0.2) — поки без розрахунку ----
    proj_col1, proj_col2 = st.columns(2)
    with proj_col1:
        project_index = st.text_input("Індекс проєкту", key="project_index_field")
    with proj_col2:
        project_name = st.text_input("Назва проєкту", key="project_name_field")

    col1, col2 = st.columns(2)
    with col1:
        fmt = st.selectbox(
            "Формат", options=list(params["formats"].keys()) or ["—"],
            help="84 звичайний, 60 ширший, 70 збільшений",
        )
        zirka = st.selectbox(
            "Зірковість перекладу", options=list(params["translation"].keys()) or ["—"],
            format_func=lambda z: ZIRKA_LABELS.get(z, z),
        )
        complexity = st.selectbox(
            "Редагування", options=list(params["editing"].keys()) or ["—"],
            format_func=lambda c: EDITING_LABELS.get(c, c),
        )

        znaky = st.number_input(
            "Кількість знаків (оригінал)", min_value=0, value=700_000, step=10_000,
            help="Знаків тексту в оригінальному творі до перекладу і редагування",
        )
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
        color_mode = st.selectbox("Колірність блоку", ["1+1 (ч/б)", "4+4 (повний колір)"])
        effect = st.selectbox(
            "Ефекти обкладинки", ["Норма", "Бонус", "Преміум"],
            format_func=lambda e: COVER_EFFECT_LABELS.get(e, e),
            help="Кожен наступний рівень включає ефекти попереднього",
        )
        has_zriz = st.checkbox("Кольоровий зріз")

        oblozhka_suma = st.number_input(
            "Дизайн обкладинки", min_value=0, value=9000, step=100,
            help="Вартість дизайну чи оригінальної обкладинки",
        )
        efekty_suma = st.number_input(
            "Розробка ефектів", min_value=0, value=2000, step=100,
            help="Розробка додаткових ефектів",
        )
        avans = st.number_input(
            "Аванс за текст", min_value=0, value=0, step=1000,
            help="Сума чистими по договору купівлі авторських прав",
        )
        retail_discount_pct = st.number_input(
            "Знижка рітейлу, %", min_value=0, max_value=100,
            value=round(get_retail_discount(params) * 100), step=1,
            help="Частка РРЦ, яку забирає рітейл для розрахунку точки беззбитковості",
        )

    def _display_value(value, suffix=""):
        if value is None:
            return "—" + suffix
        return f"{value}{suffix}"


    def _channel_mix_expander(key_prefix: str) -> dict:
        """Розгортаний блок "Канальний мікс" — зважений мікс трьох каналів
        продажу (B2B/B2C/Ecomm) з різною економікою. ДОДАТКОВИЙ до плоскої
        "Знижки рітейлу" вище (не заміна) — та сама книга рахується двома
        паралельними шляхами: точка беззбитковості (плоска знижка) і
        Маржа/Рентабельність/Прибуток (канальний мікс).

        Повертає channel_mix dict (частки й знижки як частки 0..1) —
        коректність суми часток (=100%) перевіряє
        _channel_mix_shares_valid() окремо, на момент розрахунку, а не тут.
        """
        defaults = get_channel_mix_defaults(params)
        with st.expander("Канальний мікс", expanded=False):
            st.caption(
                "Розподіл відвантаженого тиражу по каналах продажу з різною "
                "економікою — додатковий, паралельний розрахунок фінансових "
                "показників накладу поруч із точкою беззбитковості вище."
            )
            mc1, mc2, mc3 = st.columns(3)
            b2b_share_pct = mc1.number_input(
                "B2B, %", min_value=0, max_value=100,
                value=round(defaults["b2b_share"] * 100), step=1,
                key=f"{key_prefix}_b2b_share", help="Гурт/дистрибуція",
            )
            b2c_share_pct = mc2.number_input(
                "B2C, %", min_value=0, max_value=100,
                value=round(defaults["b2c_share"] * 100), step=1,
                key=f"{key_prefix}_b2c_share", help="Власна мережа магазинів",
            )
            ecomm_share_pct = mc3.number_input(
                "Ecomm, %", min_value=0, max_value=100,
                value=round(defaults["ecomm_share"] * 100), step=1,
                key=f"{key_prefix}_ecomm_share", help="Власний інтернет-магазин",
            )
            total_share_pct = b2b_share_pct + b2c_share_pct + ecomm_share_pct
            if total_share_pct != 100:
                st.warning(f"⚠️ Мікс каналів має сумувати до 100% (зараз {total_share_pct}%).")

            st.markdown("**B2B**")
            b2b_discount_pct = st.number_input(
                "Знижка B2B, %", min_value=0, max_value=100,
                value=round(defaults["b2b_discount"] * 100), step=1,
                key=f"{key_prefix}_b2b_discount",
                help="Реальна зовнішня знижка — гроші повністю покидають компанію",
            )

            st.markdown("**B2C**")
            bc1, bc2 = st.columns(2)
            b2c_promo_pct = bc1.number_input(
                "Споживча знижка/акція, %", min_value=0, max_value=100,
                value=round(defaults["b2c_promo_discount"] * 100), step=1,
                key=f"{key_prefix}_b2c_promo",
                help="⚠️ Уточнити: реальна типова глибина акцій від маркетингу",
            )
            b2c_opex_pct = bc2.number_input(
                "Операційні витрати каналу, %", min_value=0, max_value=100,
                value=round(defaults["b2c_opex"] * 100), step=1,
                key=f"{key_prefix}_b2c_opex",
                help="Оренда + персонал + логістика в точки, % від фактичної ціни продажу",
            )

            st.markdown("**Ecomm**")
            ec1, ec2 = st.columns(2)
            ecomm_promo_pct = ec1.number_input(
                "Споживча знижка/акція, %", min_value=0, max_value=100,
                value=round(defaults["ecomm_promo_discount"] * 100), step=1,
                key=f"{key_prefix}_ecomm_promo",
                help="⚠️ Уточнити: реальна типова глибина акцій від маркетингу",
            )
            ecomm_opex_pct = ec2.number_input(
                "Операційні витрати каналу, %", min_value=0, max_value=100,
                value=round(defaults["ecomm_opex"] * 100), step=1,
                key=f"{key_prefix}_ecomm_opex",
                help="Платформа + еквайринг + доставка + маркетинг + повернення",
            )

        return {
            "b2b_share": b2b_share_pct / 100.0,
            "b2c_share": b2c_share_pct / 100.0,
            "ecomm_share": ecomm_share_pct / 100.0,
            "b2b_discount": b2b_discount_pct / 100.0,
            "b2c_promo_discount": b2c_promo_pct / 100.0,
            "b2c_opex": b2c_opex_pct / 100.0,
            "ecomm_promo_discount": ecomm_promo_pct / 100.0,
            "ecomm_opex": ecomm_opex_pct / 100.0,
        }


    def _channel_mix_shares_valid(channel_mix: dict) -> bool:
        total = (
            channel_mix["b2b_share"] + channel_mix["b2c_share"] + channel_mix["ecomm_share"]
        )
        return abs(total - 1.0) <= 0.001


    def _metric_card(column, label, value, caption=None, help_text=None):
        """Картка-метрика власною розміткою (не st.metric) — підпис
        переноситься по словах, число переноситься замість обрізання
        трьома крапками на довгих значеннях."""
        help_html = f' <span class="metric-help" title="{help_text}">ⓘ</span>' if help_text else ""
        caption_html = f'<div class="metric-caption">{caption}</div>' if caption else ""
        column.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">{label}{help_html}</div>'
            f'<div class="metric-value">{value}</div>'
            f"{caption_html}"
            f"</div>",
            unsafe_allow_html=True,
        )


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

        def _breakeven_label(r):
            breakeven = r["result"]["breakeven"]
            if breakeven is None:
                return "—"
            units_label = f"{breakeven['units']:,}".replace(",", " ")
            return f"{units_label} / {breakeven['percent_of_run']:.1f}%"

        def _format_band(band):
            """Показ смуги тиру в шапці таблиці — прибирає позначку "(база)"
            і замінює "понад N" на ">N" незалежно від того, чи є ці
            позначки в сирому тексті смуги з Google-таблиці."""
            if not band:
                return band
            band = re.sub(r"\s*\(база\)\s*", "", band).strip()
            band = re.sub(r"^понад\s+", ">", band)
            return band

        headers = []
        for r in rows:
            band = _format_band(r["tier"]["band"]) if r["tier"] else "—"
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
            ("Точка беззбитковості", _breakeven_label, False),
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

        with st.container(key="lookup_values_block"):
            r1, r2 = st.columns(2)
            r1.write(f"**Тариф перекладу ({zirka}):** {params['translation'].get(zirka, '—')} грн/1000 (чистими)")
            r1.write(f"**Тариф редагування ({complexity}):** {params['editing'].get(complexity, '—')} грн/1000 (чистими)")
            r1.write(f"**Знаків/стор ({fmt}):** {_display_value(fmt_data.get('znakiv_stor'))}")
            r1.write(f"**Зошит ({fmt}):** {_display_value(fmt_data.get('zoshyt'))} стор.")

            r2.write(f"**Ціна зошита T3 ({fmt}):** {_display_value(fmt_data.get('price_zoshyt'))} грн")
            r2.write(f"**Ціна зрізу ({fmt}):** {_display_value(params['zriz'].get(fmt))} грн")
            r2.write(f"**Обкладинка ({fmt} / {effect}):** {_display_value(params['cover'].get((fmt, effect)))} грн")
            r2.write(f"**Тир ({naklad}):** {tier['tier'] if tier else '—'} (k={tier['k'] if tier else '—'})")

    channel_mix = _channel_mix_expander("plan")

    st.divider()

    # ---- Розрахунок (§4-§8 драфту) — Блок 1 (оригінал-макет) + заготовка РРЦ ----
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
        "retail_discount": retail_discount_pct / 100.0,
        "channel_mix": channel_mix,
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

            if result["missing_tarify"]:
                items = "; ".join(f"{stattia} «{znachennya}»" for stattia, znachennya in result["missing_tarify"])
                st.warning(
                    f"⚠️ Тариф не знайдено в майстер-таблиці для: {items} — "
                    "відповідна стаття порахована як 0 грн, тому ОРИГІНАЛ-МАКЕТ і РРЦ "
                    "нижче можуть бути занижені. Перевірте блоки ПЕРЕКЛАД/РЕДАГУВАННЯ "
                    "в Google-таблиці."
                )

            # ---- Головні результати: картки-метрики + РРЦ як акцент ----
            breakeven = result["breakeven"]
            m1, m2, m3 = st.columns(3)
            _metric_card(m1, "ОРИГІНАЛ-МАКЕТ, грн", _fmt(result["oryhinal_maket"]))
            _metric_card(m2, "Друк за 1 прим., грн", _fmt(block2["razom"]) if block2 else "—")
            if breakeven is None:
                _metric_card(m3, "Точка беззбитковості", "—")
            else:
                units_label = f"{breakeven['units']:,}".replace(",", " ")
                _metric_card(m3, "Точка беззбитковості", units_label)

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

            if breakeven is not None and breakeven["percent_of_run"] > 100:
                st.error(
                    f"⚠️ Точка беззбитковості ({breakeven['percent_of_run']:.0f}% тиражу) "
                    "перевищує наклад — книжка не окупається навіть повністю проданим "
                    "тиражем за поточної знижки рітейлу."
                )

            # ---- Фінансові показники накладу за канальним міксом — ДОДАТКОВИЙ,
            # паралельний блок до точки беззбитковості вище (не заміна). ----
            if not _channel_mix_shares_valid(inputs["channel_mix"]):
                st.warning("⚠️ Мікс каналів має сумувати до 100%.")
            elif result["channel_financials"] is not None:
                cf = result["channel_financials"]
                st.markdown("**Фінансові показники накладу (канальний мікс)**")
                cm1, cm2, cm3 = st.columns(3)
                _metric_card(cm1, "Маржа, %", f"{cf['marzha'] * 100:.1f}")
                _metric_card(cm2, "Рентабельність, %", f"{cf['rentabelnist'] * 100:.1f}")
                _metric_card(cm3, "Прибуток, грн", _fmt(cf["prybutok"]))

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
                inshi_row = result["inshi_row"]
                table_rows.append(
                    {
                        "Стаття": "Інші витрати (12%)",
                        "Чистими, грн": _fmt(inshi_row["chysto"]),
                        "Тіло, грн": _fmt(inshi_row["tilo"]),
                        "ЄСВ, грн": _fmt(inshi_row["esv"]),
                        "Разом, грн": _fmt(inshi_row["razom"]),
                    }
                )
                table_rows.append(
                    {
                        "Стаття": "Разом",
                        "Чистими, грн": _fmt(
                            sum(r["chysto"] for r in result["rows"].values()) + inshi_row["chysto"]
                        ),
                        "Тіло, грн": _fmt(
                            sum(r["tilo"] for r in result["rows"].values()) + inshi_row["tilo"]
                        ),
                        "ЄСВ, грн": _fmt(
                            sum(r["esv"] for r in result["rows"].values()) + inshi_row["esv"]
                        ),
                        "Разом, грн": _fmt(result["oryhinal_maket"]),
                    }
                )
                _render_table(table_rows, total_labels={"Разом"})

                st.markdown("**Друк (за 1 прим.)**")
                if block2 is None:
                    with st.container(key="print_missing_caption"):
                        st.caption("Друк не порахований — див. попередження вище.")
                else:
                    print_rows = [
                        {"Стаття": "Блок", "Разом, грн": _fmt(block2["blok"])},
                        {"Стаття": "Обкладинка (друк)", "Разом, грн": _fmt(block2["obkladynka_dr"])},
                        {"Стаття": "Кольоровий зріз", "Разом, грн": _fmt(block2["zriz"])},
                        {"Стаття": "Друк за 1 прим., разом", "Разом, грн": _fmt(block2["razom"])},
                    ]
                    _render_table(print_rows, total_labels={"Друк за 1 прим., разом"})
                    with st.container(key="print_stats_caption"):
                        st.caption(
                            f"Сторінок: {block2['storinky']:.0f} · Зошитів: {block2['zoshytiv']:.1f} · "
                            f"Тир: {block2['tier']['tier']} (k={block2['tier']['k']}) · "
                            f"K_колір: {block2['k_kolir']}"
                        )

    with tab_compare:
        with st.container(key="compare_intro_caption"):
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

with tab_fact:
    with st.container(key="fact_intro_caption"):
        st.caption("РРЦ під кілька накладів на основі ГОТОВОЇ суми оригінал-макета")

    fact_proj_col1, fact_proj_col2 = st.columns(2)
    with fact_proj_col1:
        fact_project_index = st.text_input("Індекс проєкту", key="fact_project_index_field")
    with fact_proj_col2:
        fact_project_name = st.text_input("Назва проєкту", key="fact_project_name_field")

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        fact_oryhinal_maket = st.number_input(
            "Сума видатків на оригінал-макет, грн", min_value=0.0, value=0.0, step=1000.0,
            key="fact_oryhinal_maket",
            help="Внесіть суму видатків на оригінал-макет згідно паспорта",
        )
        fact_fmt = st.selectbox(
            "Формат", options=list(params["formats"].keys()) or ["—"], key="fact_format",
            help="84 звичайний, 60 ширший, 70 збільшений",
        )
        fact_storinky = st.number_input(
            "Сторінки", min_value=0, value=0, step=1, key="fact_storinky",
            help="Реальна кількість сторінок із верстки",
        )
        fact_znaky = st.number_input(
            "Знаки", min_value=0, value=0, step=10_000, key="fact_znaky",
            help="Не використовується в розрахунку — тільки для відображення й експорту.",
        )
    with fcol2:
        fact_color_mode = st.selectbox(
            "Колірність блоку", ["1+1 (ч/б)", "4+4 (повний колір)"], key="fact_color_mode"
        )
        fact_effect = st.selectbox(
            "Ефекти обкладинки", ["Норма", "Бонус", "Преміум"], key="fact_effect",
            format_func=lambda e: COVER_EFFECT_LABELS.get(e, e),
            help="Кожен наступний рівень включає ефекти попереднього",
        )
        fact_has_zriz = st.checkbox("Кольоровий зріз", key="fact_has_zriz")
        fact_retail_discount_pct = st.number_input(
            "Знижка рітейлу, %", min_value=0, max_value=100,
            value=round(get_retail_discount(params) * 100), step=1, key="fact_retail_discount",
            help="Частка РРЦ, яку забирає рітейл для розрахунку точки беззбитковості",
        )

    fact_channel_mix = _channel_mix_expander("fact")

    with st.container(key="fact_naklad_caption"):
        st.caption(
            "Наклади для порівняння — редагований список, додавайте чи "
            "прибирайте рядки."
        )
    fact_naklad_editor_df = pd.DataFrame({"Наклад": DEFAULT_FACT_NAKLADY})
    fact_edited_naklady_df = st.data_editor(
        fact_naklad_editor_df,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Наклад": st.column_config.NumberColumn("Наклад", min_value=1, step=100)
        },
        key="fact_naklad_editor",
    )

    fact_book_inputs = {
        "oryhinal_maket": fact_oryhinal_maket,
        "format": fact_fmt,
        "storinky": fact_storinky,
        "znaky": fact_znaky,
        "color_mode": fact_color_mode,
        "effect": fact_effect,
        "has_zriz": fact_has_zriz,
        "retail_discount": fact_retail_discount_pct / 100.0,
        "channel_mix": fact_channel_mix,
    }

    if st.button("🧮 Порахувати наклади", type="primary", key="fact_calc_button"):
        fact_naklad_list = sorted(
            {float(n) for n in fact_edited_naklady_df["Наклад"].dropna().tolist() if n and n > 0}
        )
        if not fact_naklad_list:
            st.warning("Додайте хоча б один наклад для порівняння.")
            st.session_state.pop("fact_comparison_rows", None)
        else:
            st.session_state["fact_comparison_inputs"] = fact_book_inputs
            st.session_state["fact_comparison_rows"] = compare_naklady_fact(
                fact_book_inputs, params, fact_naklad_list
            )

    if "fact_comparison_rows" in st.session_state:
        fact_rows = st.session_state["fact_comparison_rows"]
        _render_comparison_table(fact_rows)

        if any(r["result"]["block2"] is None for r in fact_rows):
            st.warning(
                "⚠️ Для деяких накладів друк не порахований — бракує даних у "
                "майстер-таблиці (ціна зошита, обкладинки, зрізу, тир або "
                "множник 4+4)."
            )

        fact_project_ready = bool(fact_project_index.strip()) and bool(fact_project_name.strip())
        if not fact_project_ready:
            st.warning("Заповніть індекс і назву проєкту перед експортом.")

        fact_export_inputs = {
            **st.session_state["fact_comparison_inputs"],
            "project_index": fact_project_index.strip(),
            "project_name": fact_project_name.strip(),
        }
        fact_xlsx_buffer = (
            export_fact_to_xlsx(fact_export_inputs, fact_rows) if fact_project_ready else None
        )
        fact_date_str = datetime.date.today().strftime("%Y%m%d")
        if fact_project_ready:
            fact_file_name = (
                f"{_sanitize_filename_part(fact_project_index)}_"
                f"{_sanitize_filename_part(fact_project_name)}_"
                f"Факт_наклади_{fact_date_str}.xlsx"
            )
        else:
            fact_file_name = f"Факт_наклади_{fact_date_str}.xlsx"
        st.download_button(
            "📥 Експортувати в xlsx",
            data=fact_xlsx_buffer if fact_project_ready else b"",
            file_name=fact_file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=not fact_project_ready,
            key="fact_export_button",
        )
