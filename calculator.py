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

# Канальний мікс (§ нова фіча) — дефолти, якщо блоку "КАНАЛЬНИЙ МІКС" ще
# нема в майстер-таблиці, або конкретний параметр у ньому порожній.
# Споживчі знижки B2C/Ecomm навмисно 0% — ПЛЕЙСХОЛДЕР до уточнення
# реальної типової глибини акцій від маркетингу (див. get_channel_mix()).
DEFAULT_CHANNEL_MIX = {
    "b2b_share": 0.70,
    "b2c_share": 0.15,
    "ecomm_share": 0.15,
    "b2b_discount": 0.45,
    "b2c_promo_discount": 0.0,
    "b2c_opex": 0.25,
    "ecomm_promo_discount": 0.0,
    "ecomm_opex": 0.25,
}

# Відповідність внутрішнього ключа й назви рядка "Параметр" у блоці
# "КАНАЛЬНИЙ МІКС" майстер-таблиці (той самий принцип, що блок ЗАГАЛЬНІ).
_CHANNEL_MIX_LABELS = {
    "b2b_share": "Частка B2B",
    "b2c_share": "Частка B2C",
    "ecomm_share": "Частка Ecomm",
    "b2b_discount": "Знижка B2B",
    "b2c_promo_discount": "Споживча знижка B2C",
    "b2c_opex": "Операційні витрати B2C",
    "ecomm_promo_discount": "Споживча знижка Ecomm",
    "ecomm_opex": "Операційні витрати Ecomm",
}


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


def get_channel_mix_defaults(params: dict) -> dict:
    """Дефолти каналів (частка 0..1) з params["channel_mix"] (блок
    "КАНАЛЬНИЙ МІКС" майстер-таблиці), інакше DEFAULT_CHANNEL_MIX для
    кожного окремого параметра, якщо його ще нема в таблиці чи блоку
    взагалі немає — той самий принцип, що get_retail_discount()."""
    block = params.get("channel_mix", {})
    return {
        key: _to_float(block.get(label), DEFAULT_CHANNEL_MIX[key])
        for key, label in _CHANNEL_MIX_LABELS.items()
    }


def calculate_channel_financials(
    rrc, naklad: float, oryhinal_maket: float, druk_za_sht, channel_mix: dict
):
    """
    Дохід на 1 проданий примірник по каналах, зважений (блендований)
    дохід і фінансові показники тиражу (Виручка/Собівартість/Прибуток/
    Маржа/Рентабельність) — додатковий, паралельний до точки
    беззбитковості розрахунок (не заміна).

    B2B — ОДНЕ число знижки (гроші повністю покидають компанію):
      дохід_b2b = РРЦ x (1 − b2b_discount)

    B2C/Ecomm — ДВА окремих числа, множення послідовне (спершу акція
    збиває фактичну ціну продажу, ПОТІМ від неї віднімається операційка
    каналу), НЕ додавання й НЕ одне число:
      дохід_b2c   = РРЦ x (1 − b2c_promo_discount)   x (1 − b2c_opex)
      дохід_ecomm = РРЦ x (1 − ecomm_promo_discount) x (1 − ecomm_opex)

    channel_mix: b2b_share, b2c_share, ecomm_share (частки 0..1, мають
      сумувати до 1.0 — інакше мікс каналів невизначений і функція
      повертає None, а не довільний/помилковий розрахунок), b2b_discount,
      b2c_promo_discount, b2c_opex, ecomm_promo_discount, ecomm_opex.

    Повертає None, якщо:
      - rrc чи druk_za_sht ще не порахований (бракує даних у майстер-
        таблиці для обраної комбінації формат/ефект/наклад), або
      - наклад <= 0, або
      - частки каналів не сумують до 100% (з похibкою округлення 0,1 в.п.).
    """
    if rrc is None or druk_za_sht is None or not naklad:
        return None

    b2b_share = channel_mix["b2b_share"]
    b2c_share = channel_mix["b2c_share"]
    ecomm_share = channel_mix["ecomm_share"]

    if abs(b2b_share + b2c_share + ecomm_share - 1.0) > 0.001:
        return None

    dohid_b2b = rrc * (1 - channel_mix["b2b_discount"])
    dohid_b2c = rrc * (1 - channel_mix["b2c_promo_discount"]) * (1 - channel_mix["b2c_opex"])
    dohid_ecomm = (
        rrc * (1 - channel_mix["ecomm_promo_discount"]) * (1 - channel_mix["ecomm_opex"])
    )

    blended_dohid = b2b_share * dohid_b2b + b2c_share * dohid_b2c + ecomm_share * dohid_ecomm

    vyruchka = naklad * blended_dohid
    sobivartist = oryhinal_maket + druk_za_sht * naklad
    prybutok = vyruchka - sobivartist
    marzha = prybutok / vyruchka if vyruchka else None
    rentabelnist = prybutok / sobivartist if sobivartist else None

    return {
        "dohid_b2b": dohid_b2b,
        "dohid_b2c": dohid_b2c,
        "dohid_ecomm": dohid_ecomm,
        "blended_dohid": blended_dohid,
        "vyruchka": vyruchka,
        "sobivartist": sobivartist,
        "prybutok": prybutok,
        "marzha": marzha,
        "rentabelnist": rentabelnist,
    }


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

    # «Інші» рахуються від сум РАЗОМ чотирьох виробничих ДП-статей
    # (редагування, коректура, обкладинка, ефекти обкладинки) — переклад
    # і аванс (АЛД-статті) у цю базу не входять (§5).
    inshi_baza = (
        rows["редагування"]["razom"]
        + rows["коректура"]["razom"]
        + rows["обкладинка"]["razom"]
        + rows["ефекти"]["razom"]
    )
    inshi = inshi_rate * inshi_baza

    # Розкладка "Інші" на тіло/ЄСВ/чистими — той самий податковий
    # взаємозв'язок, що й у _dp_row(), але у зворотному напрямку: тут
    # відома сума РАЗОМ (= inshi), а не чистими, тому тіло виводиться
    # з розом (тіло x (1+esv_rate) = razom), а чистими — довідково
    # (скільки з цього тіла лишається "на руки" після ПДФО/ВЗ).
    inshi_tilo = inshi / (1 + esv_rate)
    inshi_esv = inshi_tilo * esv_rate
    inshi_chysto = inshi_tilo * tilo_divisor
    inshi_row = {
        "chysto": inshi_chysto,
        "tilo": inshi_tilo,
        "esv": inshi_esv,
        "razom": inshi,
    }

    oryhinal_maket = sum(r["razom"] for r in rows.values()) + inshi

    return {
        "znaky_rozrah": znaky_rozrah,
        "tarif_pereklad": tarif_pereklad,
        "tarif_redaguvannya": tarif_redaguvannya,
        "rows": rows,
        "inshi": inshi,
        "inshi_row": inshi_row,
        "oryhinal_maket": oryhinal_maket,
        "missing_tarify": missing_tarify,
    }


def _print_calc(storinky: float, fmt: str, naklad: float, color_mode: str,
                 effect: str, has_zriz: bool, params: dict):
    """Друк (§6) за ГОТОВИМИ сторінками: блок + обкладинка_др + зріз.

    Спільна для Планового Паспорта (де `storinky` вже підігнані під
    кратність зошита в `_calculate_block2`) і фічі "Факт → наклади"
    (де `storinky` — реальна кількість з верстки, без підгонки).

    Зошитів рахуються прямим діленням `storinky` на фізичний зошит
    формату, БЕЗ округлення вгору — може вийти пів-зошита (X,5), і
    саме на цю дробову кількість множимо ціну зошита нижче.

    Повертає None, якщо для обраної комбінації формат/ефект/наклад
    бракує якогось значення в майстер-таблиці (замість падіння).
    """
    general = params.get("general", {})

    fmt_data = params.get("formats", {}).get(fmt)
    if not fmt_data:
        return None

    zoshyt_stor = fmt_data.get("zoshyt")
    price_zoshyt = fmt_data.get("price_zoshyt")
    if zoshyt_stor is None or price_zoshyt is None or zoshyt_stor <= 0:
        return None

    tier = get_tier_for_naklad(params.get("tiers", []), _to_float(naklad))
    k_tyr = tier.get("k") if tier else None
    if k_tyr is None:
        return None

    if "4+4" in (color_mode or ""):
        k_kolir = general.get("Множник блоку 4+4")
        if k_kolir is None:
            return None
    else:
        k_kolir = 1.0

    cena_obkladynky = params.get("cover", {}).get((fmt, effect))
    if cena_obkladynky is None:
        return None

    if has_zriz:
        cena_zrizu = params.get("zriz", {}).get(fmt)
        if cena_zrizu is None:
            return None
    else:
        cena_zrizu = 0.0

    zoshytiv = round(storinky / zoshyt_stor, 1)
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


def _calculate_block2(inputs: dict, params: dict):
    """
    Друк (§6) Планового Паспорта: сторінки з знаків + підгонка під
    кратність, тоді спільна `_print_calc()`.

    Сторінки підганяються під кратність (round-half-up, не завжди
    вгору) — зошитів тому може вийти з половиною (X,5), і блок
    рахується прямим множенням на цю дробову кількість.

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
    if znakiv_stor is None or zoshyt_stor is None:
        return None
    if znakiv_stor <= 0 or zoshyt_stor <= 0:
        return None

    zazor = general.get("Зазор сторінковості")
    if zazor is None:
        return None

    znaky_rozrah = _to_float(inputs.get("znaky")) * (
        _to_float(general.get("Коеф. перекладу"), 1.2)
        if inputs.get("perekladna")
        else 1.0
    )

    storinkovist_multiplier = _to_float(inputs.get("storinkovist_multiplier"), 1.0)
    storinky_syri = znaky_rozrah / znakiv_stor * (1 + zazor) * storinkovist_multiplier

    # Підгонка сторінок під кратність зошита — звичайне округлення
    # (round-half-up), НЕ завжди вгору. Кратність = половина фізичного
    # зошита (16 при зошиті=32, 8 при зошиті=16) — тому зошитів на
    # Кроці 4 нижче може вийти X,0 або рівно X,5, і ніколи інакше.
    # math.floor(x + 0.5) замість round(), бо round() у Python робить
    # банківське округлення (round half to even): round(22.5) -> 22,
    # а тут завжди потрібне класичне round-half-up: 22,5 -> 23.
    kratnist = zoshyt_stor / 2
    n = storinky_syri / kratnist
    n_rounded = math.floor(n + 0.5)
    storinky = n_rounded * kratnist

    return _print_calc(
        storinky, fmt, inputs.get("naklad"), inputs.get("color_mode", ""),
        inputs.get("effect"), bool(inputs.get("has_zriz")), params,
    )


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
      inshi (сума, = inshi_row["razom"]),
      inshi_row (та сама сума розкладена на chysto/tilo/esv/razom —
        тіло виводиться НАЗАД із razom, чистими тут довідкове),
      oryhinal_maket,
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
        приховувати брак даних під правдоподібним нулем),
      channel_financials (Виручка/Собівартість/Прибуток/Маржа/
        Рентабельність за зваженим каналовим міксом — див.
        calculate_channel_financials(); None, якщо rrc ще не
        порахований або мікс каналів не сумує до 100%).
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

    channel_mix = inputs.get("channel_mix")
    channel_mix = get_channel_mix_defaults(params) if channel_mix is None else channel_mix
    channel_financials = calculate_channel_financials(
        rrc, naklad, block1["oryhinal_maket"], druk_za_sht, channel_mix
    )

    return {
        "znaky_rozrah": block1["znaky_rozrah"],
        "tarif_pereklad": block1["tarif_pereklad"],
        "tarif_redaguvannya": block1["tarif_redaguvannya"],
        "rows": block1["rows"],
        "inshi": block1["inshi"],
        "inshi_row": block1["inshi_row"],
        "oryhinal_maket": block1["oryhinal_maket"],
        "block2": block2,
        "druk_za_sht": druk_za_sht,
        "rrc": rrc,
        "breakeven": breakeven,
        "missing_tarify": block1["missing_tarify"],
        "channel_financials": channel_financials,
    }


DEFAULT_FACT_NAKLADY = [2100, 3100, 5100, 7100]


def calculate_fact(inputs: dict, params: dict) -> dict:
    """
    Розрахунок РРЦ для фічі "Факт → наклади" — на основі ГОТОВОЇ суми
    оригінал-макета (з фактичного паспорта чи введеної вручну), а не
    розрахованої з тарифів.

    На відміну від calculate():
      1) oryhinal_maket береться напряму з inputs["oryhinal_maket"],
         Блок 1 (статті/тарифи) тут не рахується взагалі;
      2) сторінки беруться напряму з inputs["storinky"] — реальна
         кількість з верстки, БЕЗ підгонки під кратність зошита.

    Друк/РРЦ/точка беззбитковості рахуються тим самим шляхом, що й у
    calculate() — через спільну _print_calc().

    inputs: oryhinal_maket, format, storinky, color_mode, effect,
      has_zriz, naklad, retail_discount (опційно, як у calculate()).

    Повертає: oryhinal_maket, storinky, block2 (= _print_calc() чи
      None), druk_za_sht, rrc, breakeven, channel_financials — та сама
      форма ключів, що й у calculate(), тільки без znaky_rozrah/rows/
      inshi/missing_tarify (Блоку 1 тут немає).
    """
    general = params.get("general", {})
    oryhinal_maket = _to_float(inputs.get("oryhinal_maket"))
    storinky = _to_float(inputs.get("storinky"))
    naklad = _to_float(inputs.get("naklad"))

    block2 = _print_calc(
        storinky, inputs.get("format"), naklad, inputs.get("color_mode", ""),
        inputs.get("effect"), bool(inputs.get("has_zriz")), params,
    )
    druk_za_sht = block2["razom"] if block2 else None

    rrc = None
    if druk_za_sht is not None and naklad:
        k_narinka = _to_float(general.get("Націнка k"), 3.9)
        sobivartist_1 = oryhinal_maket / naklad + druk_za_sht
        rrc = _round_to_9(k_narinka * sobivartist_1)

    retail_discount = inputs.get("retail_discount")
    retail_discount = (
        get_retail_discount(params) if retail_discount is None else _to_float(retail_discount)
    )

    breakeven = None
    if rrc is not None and druk_za_sht is not None and naklad:
        dohid_na_1_prym = rrc * (1 - retail_discount)
        if dohid_na_1_prym > 0:
            povna_sobivartist = oryhinal_maket + druk_za_sht * naklad
            units = math.ceil(povna_sobivartist / dohid_na_1_prym)
            breakeven = {
                "units": units,
                "percent_of_run": units / naklad * 100,
                "retail_discount": retail_discount,
            }

    channel_mix = inputs.get("channel_mix")
    channel_mix = get_channel_mix_defaults(params) if channel_mix is None else channel_mix
    channel_financials = calculate_channel_financials(
        rrc, naklad, oryhinal_maket, druk_za_sht, channel_mix
    )

    return {
        "oryhinal_maket": oryhinal_maket,
        "storinky": storinky,
        "block2": block2,
        "druk_za_sht": druk_za_sht,
        "rrc": rrc,
        "breakeven": breakeven,
        "channel_financials": channel_financials,
    }


def compare_naklady_fact(inputs: dict, params: dict, naklady: list) -> list:
    """Той самий принцип, що compare_naklady(), тільки навколо
    calculate_fact() — для таблиці порівняння накладів у фічі
    "Факт → наклади".

    Повертає список у тому самому порядку, що й `naklady`:
      [{"naklad": ..., "tier": {...} чи None, "result": calculate_fact(...)}, ...]
    """
    rows = []
    for naklad in naklady:
        row_inputs = {**inputs, "naklad": naklad}
        result = calculate_fact(row_inputs, params)
        tier = (
            result["block2"]["tier"]
            if result["block2"]
            else get_tier_for_naklad(params.get("tiers", []), naklad)
        )
        rows.append({"naklad": naklad, "tier": tier, "result": result})
    return rows


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
        # Якір 100 (найменший тир) некоректний як наклад для порівняння —
        # у живій таблиці для нього нема/невірне значення "Якір", тому і
        # взятий з таблиці, і обчислений фолбек однаково дають 100.
        if anchor == 100:
            anchor = 1100
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
