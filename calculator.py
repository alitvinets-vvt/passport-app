"""
Розрахунок собівартості й РРЦ Планового Паспорту (кроки 4-5 роадмепу).

Джерело правил: Плановий_паспорт_драфт_правил_v0.2.docx, §3-§8.

Реалізовано повністю:
  Блок 1 (оригінал-макет) — §3-§5, §8.
  Блок 2 (друк) — §6.
  Формула РРЦ — §7.

Якщо якогось значення (ціна зошита/обкладинки/зрізу, множник 4+4,
k_тир) немає в майстер-таблиці для обраної комбінації, друк_за_шт і,
відповідно, РРЦ повертаються як None замість падіння з помилкою —
у такому разі UI показує прочерк.
"""

import math

from sheets_reader import get_tier_for_naklad

DEFAULT_RETAIL_DISCOUNT = 0.45


def _to_float(v, default=0.0):
    if v is None:
        return default
    return float(v)


def get_retail_discount(params: dict) -> float:
    """Знижка рітейлу (частка 0..1) — з params["general"]["Знижка рітейлу"],
    інакше safe-дефолт 45%, якщо параметра ще нема в майстер-таблиці
    (щоб точка беззбитковості не падала, доки технолог не додав рядок)."""
    general = params.get("general", {})
    return _to_float(general.get("Знижка рітейлу"), DEFAULT_RETAIL_DISCOUNT)


def _round_to_9(x: float) -> int:
    """Округлення до найближчого числа, що закінчується на 9 (…239, 249, 259)."""
    return int(round((x - 9) / 10)) * 10 + 9


def _ald_row(chysto: float, tilo_divisor: float) -> dict:
    """Авторсько-ліцензійний договір: тіло без ЄСВ."""
    tilo = chysto / tilo_divisor
    return {"chysto": chysto, "tilo": tilo, "esv": 0.0, "razom": tilo}


def _dp_row(chysto: float, tilo_divisor: float, esv_rate: float) -> dict:
    """Договір підряду: тіло + ЄСВ зверху."""
    tilo = chysto / tilo_divisor
    esv = tilo * esv_rate
    return {"chysto": chysto, "tilo": tilo, "esv": esv, "razom": tilo + esv}


def _calculate_block1(inputs: dict, params: dict) -> dict:
    """Оригінал-макет (§5) — чисті бази, податки, «інші», підсумок."""
    general = params.get("general", {})

    koef_pereklad = _to_float(general.get("Коеф. перекладу"), 1.2)
    koef_korektura = _to_float(general.get("Коректура"), 0.3)
    inshi_rate = _to_float(general.get("Інші витрати"), 0.12)
    esv_rate = _to_float(general.get("ЄСВ"), 0.22)
    pdfo_rate = _to_float(general.get("ПДФО"), 0.18)
    vz_rate = _to_float(general.get("Військовий збір"), 0.05)
    tilo_divisor = 1 - pdfo_rate - vz_rate  # = 0,77

    perekladna = bool(inputs.get("perekladna"))
    znaky = _to_float(inputs.get("znaky"))
    zirka = inputs.get("zirka")
    complexity = inputs.get("complexity")
    oblozhka_chysto = _to_float(inputs.get("oblozhka"))
    efekty_chysto = _to_float(inputs.get("efekty"))
    avans_chysto = _to_float(inputs.get("avans"))

    znaky_rozrah = znaky * (koef_pereklad if perekladna else 1.0)

    tarif_pereklad = params.get("translation", {}).get(zirka)
    tarif_redaguvannya = params.get("editing", {}).get(complexity)

    # Явно фіксуємо брак тарифу в майстер-таблиці (замість тихого
    # переходу в 0 через _to_float(None) — інакше "тариф не знайдено"
    # виглядає точнісінько як "тариф дорівнює нулю", і користувач не
    # має шансу це помітити, дивлячись лише на підсумкову таблицю).
    missing_tarify = []
    if perekladna and tarif_pereklad is None:
        missing_tarify.append(("переклад", zirka))
    if tarif_redaguvannya is None:
        missing_tarify.append(("редагування", complexity))

    # Переклад оплачується за обсягом ОРИГІНАЛУ — без множника 1,2.
    # Множник застосовується тільки до редагування, коректури й сторінковості,
    # бо вони працюють з уже перекладеним (розбухлим) текстом.
    pereklad_chysto = (
        _to_float(tarif_pereklad) * znaky / 1000 if perekladna else 0.0
    )
    redaguvannya_chysto = _to_float(tarif_redaguvannya) * znaky_rozrah / 1000
    korektura_chysto = koef_korektura * redaguvannya_chysto

    rows = {
        "аванс": _ald_row(avans_chysto, tilo_divisor),
        "переклад": _ald_row(pereklad_chysto, tilo_divisor),
        "редагування": _dp_row(redaguvannya_chysto, tilo_divisor, esv_rate),
        "коректура": _dp_row(korektura_chysto, tilo_divisor, esv_rate),
        "обкладинка": _dp_row(oblozhka_chysto, tilo_divisor, esv_rate),
        "ефекти": _dp_row(efekty_chysto, tilo_divisor, esv_rate),
    }

    # «Інші» рахуються від сум РАЗОМ трьох статей (редагування, коректура,
    # обкладинка) — переклад, аванс і ефекти в цю базу не входять (§5).
    inshi_baza = (
        rows["редагування"]["razom"]
        + rows["коректура"]["razom"]
        + rows["обкладинка"]["razom"]
    )
    inshi = inshi_rate * inshi_baza

    oryhinal_maket = sum(r["razom"] for r in rows.values()) + inshi

    return {
        "znaky_rozrah": znaky_rozrah,
        "tarif_pereklad": tarif_pereklad,
        "tarif_redaguvannya": tarif_redaguvannya,
        "rows": rows,
        "inshi": inshi,
        "oryhinal_maket": oryhinal_maket,
        "missing_tarify": missing_tarify,
    }


def _calculate_block2(inputs: dict, params: dict):
    """
    Друк (§6): блок + обкладинка_др + зріз.

    Повертає None, якщо для обраної комбінації формат/ефект/наклад
    бракує якогось значення в майстер-таблиці (замість падіння).
    """
    general = params.get("general", {})

    fmt = inputs.get("format")
    fmt_data = params.get("formats", {}).get(fmt)
    if not fmt_data:
        return None

    znakiv_stor = fmt_data.get("znakiv_stor")
    zoshyt_stor = fmt_data.get("zoshyt")
    price_zoshyt = fmt_data.get("price_zoshyt")
    if znakiv_stor is None or zoshyt_stor is None or price_zoshyt is None:
        return None
    if znakiv_stor <= 0 or zoshyt_stor <= 0:
        return None

    zazor = general.get("Зазор сторінковості")
    if zazor is None:
        return None

    tier = get_tier_for_naklad(params.get("tiers", []), _to_float(inputs.get("naklad")))
    k_tyr = tier.get("k") if tier else None
    if k_tyr is None:
        return None

    color_mode = inputs.get("color_mode", "")
    if "4+4" in color_mode:
        k_kolir = general.get("Множник блоку 4+4")
        if k_kolir is None:
            return None
    else:
        k_kolir = 1.0

    effect = inputs.get("effect")
    cena_obkladynky = params.get("cover", {}).get((fmt, effect))
    if cena_obkladynky is None:
        return None

    if inputs.get("has_zriz"):
        cena_zrizu = params.get("zriz", {}).get(fmt)
        if cena_zrizu is None:
            return None
    else:
        cena_zrizu = 0.0

    znaky_rozrah = _to_float(inputs.get("znaky")) * (
        _to_float(general.get("Коеф. перекладу"), 1.2)
        if inputs.get("perekladna")
        else 1.0
    )

    storinkovist_multiplier = _to_float(inputs.get("storinkovist_multiplier"), 1.0)
    storinky = znaky_rozrah / znakiv_stor * (1 + zazor) * storinkovist_multiplier
    zoshytiv = math.ceil(storinky / zoshyt_stor)
    blok = zoshytiv * price_zoshyt * k_tyr * k_kolir
    obkladynka_dr = cena_obkladynky * k_tyr
    zriz = cena_zrizu

    return {
        "storinky": storinky,
        "zoshytiv": zoshytiv,
        "tier": tier,
        "k_kolir": k_kolir,
        "blok": blok,
        "obkladynka_dr": obkladynka_dr,
        "zriz": zriz,
        "razom": blok + obkladynka_dr + zriz,
    }


def calculate(inputs: dict, params: dict) -> dict:
    """
    Головна функція калькулятора.

    inputs: словник вхідних даних користувача —
      format, zirka, complexity, perekladna, znaky,
      oblozhka, efekty, has_zriz, color_mode, effect, naklad, avans,
      storinkovist_multiplier (ручний, за замовчуванням 1.0 — не
        впливає на розрахунок; застосовується тільки до сторінок,
        звідти каскадом на зошити/блок/друк_за_шт/РРЦ),
      retail_discount (частка 0..1, ручний override; якщо не задано —
        береться get_retail_discount(params) — з майстер-таблиці, або
        DEFAULT_RETAIL_DISCOUNT, якщо параметра там ще нема).
    params: результат sheets_reader.load_params().

    Повертає:
      znaky_rozrah, rows (розбивка по статтях з податками),
      inshi, oryhinal_maket,
      block2 (деталі друку: сторінки/зошитів/блок/обкладинка_др/зріз,
        None, якщо для обраної комбінації бракує даних),
      druk_za_sht (= block2["razom"], або None),
      rrc (None, доки druk_za_sht невідомий),
      breakeven (точка беззбитковості: {"units", "percent_of_run",
        "retail_discount"}, або None — доки rrc невідомий чи дохід
        на 1 прим. (РРЦ × (1 − знижка)) <= 0),
      missing_tarify (список (стаття, значення) — тариф перекладу чи
        редагування не знайдено в майстер-таблиці для обраної зірки/
        складності; відповідна стаття тоді порахована як 0, а не
        пропущена — UI повинен показати явне попередження, не тишком
        приховувати брак даних під правдоподібним нулем).
    """
    general = params.get("general", {})
    block1 = _calculate_block1(inputs, params)
    block2 = _calculate_block2(inputs, params)
    druk_za_sht = block2["razom"] if block2 else None

    naklad = _to_float(inputs.get("naklad"))
    rrc = None
    if druk_za_sht is not None and naklad:
        k_narinka = _to_float(general.get("Націнка k"), 3.9)
        sobivartist_1 = block1["oryhinal_maket"] / naklad + druk_za_sht
        rrc = _round_to_9(k_narinka * sobivartist_1)

    retail_discount = inputs.get("retail_discount")
    retail_discount = (
        get_retail_discount(params) if retail_discount is None else _to_float(retail_discount)
    )

    breakeven = None
    if rrc is not None and druk_za_sht is not None and naklad:
        dohid_na_1_prym = rrc * (1 - retail_discount)
        if dohid_na_1_prym > 0:
            povna_sobivartist = block1["oryhinal_maket"] + druk_za_sht * naklad
            units = math.ceil(povna_sobivartist / dohid_na_1_prym)
            breakeven = {
                "units": units,
                "percent_of_run": units / naklad * 100,
                "retail_discount": retail_discount,
            }

    return {
        "znaky_rozrah": block1["znaky_rozrah"],
        "tarif_pereklad": block1["tarif_pereklad"],
        "tarif_redaguvannya": block1["tarif_redaguvannya"],
        "rows": block1["rows"],
        "inshi": block1["inshi"],
        "oryhinal_maket": block1["oryhinal_maket"],
        "block2": block2,
        "druk_za_sht": druk_za_sht,
        "rrc": rrc,
        "breakeven": breakeven,
        "missing_tarify": block1["missing_tarify"],
    }


def default_naklady(tiers: list) -> list:
    """Один репрезентативний наклад на кожен тир — стартовий список для
    фічі "Порівняння накладів" (UI будує з нього редаговану таблицю).

    Якір з майстер-таблиці (колонка "Якір" у блоці ТИРИ), якщо є для
    тиру, інакше нижня межа тиру + невеликий відступ — щоб гарантовано
    потрапити в межі смуги, а не впертись у сусідню знизу."""
    result = []
    for t in tiers:
        anchor = t.get("anchor")
        if anchor is None:
            anchor = (t.get("lo") or 0) + 100
        result.append(anchor)
    return result


def compare_naklady(inputs: dict, params: dict, naklady: list) -> list:
    """Рахує наявну calculate() окремо для кожного накладу зі списку
    `naklady`, лишаючи решту `inputs` незмінними — не нова логіка
    розрахунку, тільки виклик calculate() N разів і збір результатів
    для таблиці порівняння накладів в UI.

    Повертає список у тому самому порядку, що й `naklady`:
      [{"naklad": ..., "tier": {...} чи None, "result": calculate(...)}, ...]
    """
    rows = []
    for naklad in naklady:
        row_inputs = {**inputs, "naklad": naklad}
        result = calculate(row_inputs, params)
        tier = (
            result["block2"]["tier"]
            if result["block2"]
            else get_tier_for_naklad(params.get("tiers", []), naklad)
        )
        rows.append({"naklad": naklad, "tier": tier, "result": result})
    return rows
