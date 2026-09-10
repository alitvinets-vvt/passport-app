"""
Розрахунок собівартості й РРЦ Планового Паспорту (крок 4 роадмепу).

Джерело правил: Плановий_паспорт_драфт_правил_v0.2.docx, §3-§8.

Реалізовано:
  Блок 1 (оригінал-макет) — повністю, за §3-§5, §8.
  Формула РРЦ (§7) — заготовка: працює лише коли відомий друк_за_шт.

Не реалізовано (заплановано на наступний крок, коли технолог заповнить
плейсхолдери §6/§9.4 у майстер-таблиці):
  Блок 2 (друк) — calculate() повертає druk_za_sht=None.
"""


def _to_float(v, default=0.0):
    if v is None:
        return default
    return float(v)


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

    pereklad_chysto = (
        _to_float(tarif_pereklad) * znaky_rozrah / 1000 if perekladna else 0.0
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
    }


def _calculate_block2(inputs: dict, params: dict):
    """
    Друк (§6) — ще НЕ реалізовано: у майстер-таблиці 21 значення (ціни
    зошита, обкладинки, зрізу, множник 4+4) поки що плейсхолдери від
    технолога (§9.4). Повертає None, поки вони не заповнені.
    """
    return None


def calculate(inputs: dict, params: dict) -> dict:
    """
    Головна функція калькулятора.

    inputs: словник вхідних даних користувача —
      format, zirka, complexity, perekladna, znaky,
      oblozhka, efekty, has_zriz, color_mode, naklad, avans.
    params: результат sheets_reader.load_params().

    Повертає:
      znaky_rozrah, rows (розбивка по статтях з податками),
      inshi, oryhinal_maket, druk_za_sht (None, поки Блок 2 не готовий),
      rrc (None, доки druk_za_sht невідомий).
    """
    general = params.get("general", {})
    block1 = _calculate_block1(inputs, params)

    druk_za_sht = _calculate_block2(inputs, params)

    naklad = _to_float(inputs.get("naklad"))
    rrc = None
    if druk_za_sht is not None and naklad:
        k_narinka = _to_float(general.get("Націнка k"), 3.9)
        sobivartist_1 = block1["oryhinal_maket"] / naklad + druk_za_sht
        rrc = _round_to_9(k_narinka * sobivartist_1)

    return {
        "znaky_rozrah": block1["znaky_rozrah"],
        "tarif_pereklad": block1["tarif_pereklad"],
        "tarif_redaguvannya": block1["tarif_redaguvannya"],
        "rows": block1["rows"],
        "inshi": block1["inshi"],
        "oryhinal_maket": block1["oryhinal_maket"],
        "druk_za_sht": druk_za_sht,
        "rrc": rrc,
    }
