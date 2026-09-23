"""
Читає вкладку "Тарифи" (одна вкладка, блоки під банерами) з Google Sheets
і повертає структуровані параметри для калькулятора Планового Паспорту.

Формат вкладки (див. Параметри_Паспорт_майстер.xlsx):
  [банер-рядок, лише колонка A]
  [заголовки колонок]
  [рядки даних]
  [порожній рядок-роздільник]
  ... наступний блок ...

Банери (мають зустрічатись рівно один раз, у цьому порядку не обов'язково):
  ПЕРЕКЛАД, РЕДАГУВАННЯ, ФОРМАТИ, КОЛЬОРОВИЙ ЗРІЗ, ОБКЛАДИНКА, ТИРИ, ЗАГАЛЬНІ
"""

import json
import os

from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

BANNERS = [
    "ПЕРЕКЛАД",
    "РЕДАГУВАННЯ",
    "ФОРМАТИ",
    "КОЛЬОРОВИЙ ЗРІЗ",
    "ОБКЛАДИНКА",
    "ТИРИ",
    "ЗАГАЛЬНІ",
    "КАНАЛЬНИЙ МІКС",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def _get_client():
    """Авторизація через service account. JSON бере з env GOOGLE_SERVICE_ACCOUNT_JSON."""
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("Не заданий GOOGLE_SERVICE_ACCOUNT_JSON у середовищі")
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _find_banner(cell_value: str):
    if not cell_value:
        return None
    v = cell_value.strip()
    for b in BANNERS:
        if v.startswith(b):
            return b
    return None


def _split_into_blocks(rows):
    """rows — список списків (як gspread get_all_values). Повертає {банер: [[рядок],...]}."""
    blocks = {}
    current = None
    buf = []
    for row in rows:
        first = row[0].strip() if row and row[0] else ""
        banner = _find_banner(first)
        is_blank = all((c is None or str(c).strip() == "") for c in row)

        if banner:
            if current:
                blocks[current] = buf
            current = banner
            buf = []
            continue

        if current is None:
            continue

        if is_blank:
            blocks[current] = buf
            current = None
            buf = []
            continue

        buf.append(row)

    if current:
        blocks[current] = buf
    return blocks


def _rows_to_dicts(block_rows):
    """Перший рядок блоку (після банера) — заголовки, решта — дані."""
    if not block_rows:
        return []
    headers = [h.strip() for h in block_rows[0]]
    out = []
    for row in block_rows[1:]:
        d = {}
        for i, h in enumerate(headers):
            if not h:
                continue
            val = row[i] if i < len(row) else ""
            d[h] = val
        out.append(d)
    return out


def _to_float(v, default=None):
    if v is None or str(v).strip() == "":
        return default
    s = str(v).replace(",", ".").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return default


def load_params(sheet_id: str, worksheet_name: str = "Тарифи") -> dict:
    """
    Головна функція. Повертає словник:
      translation:  {zirka: rate}                     напр. {"5★": 125.0, ...}
      editing:      {complexity: rate}                напр. {"простий": 35.0, ...}
      formats:      {format: {znakiv_stor, zoshyt, price_zoshyt}}
      zriz:         {format: price}
      cover:        {(format, effect): price}
      tiers:        [{"tier","lo","band","k","anchor"}, ...]  відсортовано за lo
                    ("anchor" — опційна колонка "Якір", None якщо немає)
      general:      {parametr: value}
      channel_mix:  {parametr: value} — блок "КАНАЛЬНИЙ МІКС" (частки
                    каналів B2B/B2C/Ecomm, знижка B2B, споживчі знижки
                    й операційка B2C/Ecomm), той самий принцип, що
                    "general". Відсутній рядок чи весь блок — не
                    помилка, calculator.get_channel_mix_defaults()
                    підставляє safe-дефолти.
      missing:      список (блок, ключ) із порожніми "жовтими" значеннями — ще не заповнено
    """
    client = _get_client()
    sh = client.open_by_key(sheet_id)
    ws = sh.worksheet(worksheet_name)
    # UNFORMATTED_VALUE — інакше Sheets API повертає відображуваний текст
    # ("12%", "2,000"), а не сирі числа (0.12, 2000), і парсинг ламається.
    all_values = ws.get_all_values(value_render_option="UNFORMATTED_VALUE")

    blocks_raw = _split_into_blocks(all_values)
    blocks = {b: _rows_to_dicts(rows) for b, rows in blocks_raw.items()}

    missing = []

    # ---- ПЕРЕКЛАД ----
    translation = {}
    for r in blocks.get("ПЕРЕКЛАД", []):
        z = r.get("Зірки", "").strip()
        val = _to_float(r.get("Тариф чистими"))
        if z:
            translation[z] = val
            if val is None:
                missing.append(("ПЕРЕКЛАД", z))

    # ---- РЕДАГУВАННЯ ----
    editing = {}
    for r in blocks.get("РЕДАГУВАННЯ", []):
        s = r.get("Складність", "").strip()
        val = _to_float(r.get("Тариф чистими"))
        if s:
            editing[s] = val
            if val is None:
                missing.append(("РЕДАГУВАННЯ", s))

    # ---- ФОРМАТИ ----
    formats = {}
    for r in blocks.get("ФОРМАТИ", []):
        fm = r.get("Формат", "").strip()
        if not fm:
            continue
        price = _to_float(r.get("Ціна зошита T3, грн"))
        formats[fm] = {
            "znakiv_stor": _to_float(r.get("Знаків/стор")),
            "zoshyt": _to_float(r.get("Зошит, стор")),
            "price_zoshyt": price,
        }
        if price is None:
            missing.append(("ФОРМАТИ / ціна зошита", fm))

    # ---- КОЛЬОРОВИЙ ЗРІЗ ----
    zriz = {}
    for r in blocks.get("КОЛЬОРОВИЙ ЗРІЗ", []):
        fm = r.get("Формат", "").strip()
        price = _to_float(r.get("Ціна зрізу, грн"))
        if fm:
            zriz[fm] = price
            if price is None:
                missing.append(("КОЛЬОРОВИЙ ЗРІЗ", fm))

    # ---- ОБКЛАДИНКА ----
    cover = {}
    for r in blocks.get("ОБКЛАДИНКА", []):
        fm = r.get("Формат", "").strip()
        ef = r.get("Ефект", "").strip()
        price = _to_float(r.get("Ціна T3, грн"))
        if fm and ef:
            cover[(fm, ef)] = price
            if price is None:
                missing.append(("ОБКЛАДИНКА", f"{fm} / {ef}"))

    # ---- ТИРИ ----
    tiers = []
    for r in blocks.get("ТИРИ", []):
        tiers.append({
            "tier": r.get("Тир", "").strip(),
            "lo": _to_float(r.get("Нижня межа"), 0),
            "band": r.get("Смуга", "").strip(),
            "k": _to_float(r.get("k")),
            # Опційна колонка — репрезентативний наклад для фічі
            # "Порівняння накладів". None, якщо колонки немає в таблиці
            # або клітинка порожня (тоді UI бере нижню межу + відступ).
            "anchor": _to_float(r.get("Якір")),
        })
    tiers.sort(key=lambda t: t["lo"] or 0)

    # ---- ЗАГАЛЬНІ ----
    general = {}
    for r in blocks.get("ЗАГАЛЬНІ", []):
        p = r.get("Параметр", "").strip()
        val = _to_float(r.get("Значення"))
        if p:
            general[p] = val
            if val is None:
                missing.append(("ЗАГАЛЬНІ", p))

    # ---- КАНАЛЬНИЙ МІКС ----
    channel_mix = {}
    for r in blocks.get("КАНАЛЬНИЙ МІКС", []):
        p = r.get("Параметр", "").strip()
        val = _to_float(r.get("Значення"))
        if p:
            channel_mix[p] = val
            if val is None:
                missing.append(("КАНАЛЬНИЙ МІКС", p))

    return {
        "translation": translation,
        "editing": editing,
        "formats": formats,
        "zriz": zriz,
        "cover": cover,
        "tiers": tiers,
        "general": general,
        "channel_mix": channel_mix,
        "missing": missing,
    }


def get_tier_for_naklad(tiers: list, naklad: float) -> dict:
    """Повертає тир (dict), у смугу якого потрапляє наклад."""
    chosen = tiers[0] if tiers else None
    for t in tiers:
        if naklad >= (t["lo"] or 0):
            chosen = t
        else:
            break
    return chosen
