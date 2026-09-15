"""
Регресійний тест calculate() проти зафіксованого контрольного прикладу.

Еталон (§3-§8 драфту v0.2), звірений вручну і в чаті 2026-09-11:
  700 000 знаків / простий / не перекладна / формат 84х108/32 /
  колірність 1+1 (ч/б) / ефект обкладинки "Норма" / без кольорового
  зрізу / наклад 3100.

Параметри — знімок майстер-таблиці на момент фіксації контролю
(Ціна зошита=50, Ціна зрізу=20, Обкладинка=50/60/70, Множник 4+4=2.0
— ТЕСТОВІ значення, див. README_SETUP.md). Тест не звертається до
Google Sheets: params — статичний фікстур, щоб результат не залежав
від того, що зараз стоїть у живій таблиці.

Якщо цей тест почне падати після зміни calculator.py — або формула
змінилась навмисно (тоді онови еталонні числа й опиши чому в коміті),
або в код закралась регресія.
"""

import unittest

from calculator import calculate, compare_naklady, default_naklady

REFERENCE_PARAMS = {
    "translation": {"5★": 125.0, "4★": 120.0, "3★": 105.0, "2★": 120.0, "1★": 90.0},
    "editing": {"простий": 35.0, "помірний": 45.0, "складний": 60.0},
    "formats": {
        "84х108/32": {"znakiv_stor": 1290.0, "zoshyt": 32.0, "price_zoshyt": 50.0},
        "60х84/16": {"znakiv_stor": 1480.0, "zoshyt": 16.0, "price_zoshyt": 50.0},
        "70х100/16": {"znakiv_stor": 1920.0, "zoshyt": 16.0, "price_zoshyt": 50.0},
    },
    "zriz": {"84х108/32": 20.0, "60х84/16": 20.0, "70х100/16": 20.0},
    "cover": {
        ("84х108/32", "Норма"): 50.0,
        ("84х108/32", "Бонус"): 60.0,
        ("84х108/32", "Преміум"): 70.0,
        ("60х84/16", "Норма"): 50.0,
        ("60х84/16", "Бонус"): 60.0,
        ("60х84/16", "Преміум"): 70.0,
        ("70х100/16", "Норма"): 50.0,
        ("70х100/16", "Бонус"): 60.0,
        ("70х100/16", "Преміум"): 70.0,
    },
    "tiers": [
        {"tier": "T1", "lo": 0.0, "band": "до 2000", "k": 1.237},
        {"tier": "T2", "lo": 2000.0, "band": "2000–3000", "k": 1.09},
        {"tier": "T3", "lo": 3000.0, "band": "3000–5000 (база)", "k": 1.0},
        {"tier": "T4", "lo": 5000.0, "band": "5000–7000", "k": 0.915},
        {"tier": "T5", "lo": 7000.0, "band": "понад 7000", "k": 0.866},
    ],
    "general": {
        "Інші витрати": 0.12,
        "Зазор сторінковості": 0.0115,
        "Коеф. перекладу": 1.2,
        "Коректура": 0.3,
        "Множник блоку 4+4": 2.0,
        "Націнка k": 3.9,
        "ПДФО": 0.18,
        "Військовий збір": 0.05,
        "ЄСВ": 0.22,
    },
    "missing": [],
}

REFERENCE_INPUTS = {
    "format": "84х108/32",
    "zirka": "5★",
    "complexity": "простий",
    "perekladna": False,
    "znaky": 700_000,
    "oblozhka": 0,
    "efekty": 0,
    "color_mode": "1+1 (ч/б)",
    "effect": "Норма",
    "has_zriz": False,
    "naklad": 3100,
    "avans": 0,
}


class CalculateReferenceExampleTest(unittest.TestCase):
    """700 000 знаків / простий / не перекладна / 84х108/32 / ч/б / Норма / T3."""

    def setUp(self):
        self.result = calculate(dict(REFERENCE_INPUTS), REFERENCE_PARAMS)

    def test_block1_rows(self):
        rows = self.result["rows"]
        self.assertAlmostEqual(rows["редагування"]["razom"], 38818.18, places=2)
        self.assertAlmostEqual(rows["коректура"]["razom"], 11645.45, places=2)
        self.assertAlmostEqual(rows["переклад"]["razom"], 0.0, places=2)
        self.assertAlmostEqual(rows["аванс"]["razom"], 0.0, places=2)

    def test_inshi_i_oryhinal_maket(self):
        self.assertAlmostEqual(self.result["inshi"], 6055.64, places=2)
        self.assertAlmostEqual(self.result["oryhinal_maket"], 56519.27, places=2)

    def test_block2_druk(self):
        block2 = self.result["block2"]
        self.assertIsNotNone(block2)
        self.assertEqual(block2["zoshytiv"], 18)
        self.assertEqual(block2["tier"]["tier"], "T3")
        self.assertAlmostEqual(block2["blok"], 900.0, places=2)
        self.assertAlmostEqual(block2["obkladynka_dr"], 50.0, places=2)
        self.assertAlmostEqual(block2["zriz"], 0.0, places=2)
        self.assertAlmostEqual(self.result["druk_za_sht"], 950.0, places=2)

    def test_rrc(self):
        self.assertEqual(self.result["rrc"], 3779)


TRANSLATED_PARAMS = {
    **REFERENCE_PARAMS,
    "general": {
        **REFERENCE_PARAMS["general"],
        "Зазор сторінковості": 0.0,
    },
}

TRANSLATED_INPUTS = {
    "format": "84х108/32",
    "zirka": "5★",
    "complexity": "простий",
    "perekladna": True,
    "znaky": 700_000,
    "oblozhka": 0,
    "efekty": 0,
    "color_mode": "1+1 (ч/б)",
    "effect": "Норма",
    "has_zriz": False,
    "naklad": 3100,
    "avans": 0,
}


class CalculateTranslatedExampleTest(unittest.TestCase):
    """700 000 знаків / простий / ПЕРЕКЛАДНА / 84х108/32 / ч/б / Норма / T3.

    Переклад рахується від знаки_оригінал (700 000, БЕЗ множника 1,2).
    Редагування, коректура й сторінковість рахуються від знаки_розрах
    (700 000 x 1,2 = 840 000, З множником) — див. calculator.py.

    Зазор сторінковості = 0 (виправлено в майстер-таблиці; раніше там
    випадково стояло 1,15%) — окремий TRANSLATED_PARAMS, а не
    REFERENCE_PARAMS, щоб не зачепити головний контрольний приклад
    (не перекладний), який навмисно лишається на старому знімку.
    """

    def setUp(self):
        self.result = calculate(dict(TRANSLATED_INPUTS), TRANSLATED_PARAMS)

    def test_znaky_rozrah(self):
        self.assertAlmostEqual(self.result["znaky_rozrah"], 840_000.0, places=2)

    def test_block1_rows(self):
        rows = self.result["rows"]
        self.assertAlmostEqual(rows["переклад"]["razom"], 113636.36, places=2)
        self.assertAlmostEqual(rows["редагування"]["razom"], 46581.82, places=2)
        self.assertAlmostEqual(rows["коректура"]["razom"], 13974.55, places=2)
        self.assertAlmostEqual(rows["аванс"]["razom"], 0.0, places=2)

    def test_inshi_i_oryhinal_maket(self):
        self.assertAlmostEqual(self.result["inshi"], 7266.76, places=2)
        self.assertAlmostEqual(self.result["oryhinal_maket"], 181459.49, places=2)

    def test_block2_druk(self):
        block2 = self.result["block2"]
        self.assertIsNotNone(block2)
        self.assertAlmostEqual(block2["storinky"], 651.16, places=2)
        self.assertEqual(block2["zoshytiv"], 21)
        self.assertEqual(block2["tier"]["tier"], "T3")
        self.assertAlmostEqual(block2["blok"], 1050.0, places=2)
        self.assertAlmostEqual(block2["obkladynka_dr"], 50.0, places=2)
        self.assertAlmostEqual(block2["zriz"], 0.0, places=2)
        self.assertAlmostEqual(self.result["druk_za_sht"], 1100.0, places=2)

    def test_rrc(self):
        self.assertEqual(self.result["rrc"], 4519)


STORINKOVIST_INPUTS = {
    **REFERENCE_INPUTS,
    "storinkovist_multiplier": 1.2,
}


class CalculateStorinkovistMultiplierTest(unittest.TestCase):
    """Той самий контрольний приклад, що й CalculateReferenceExampleTest
    (700 000 знаків / простий / не перекладна / 84х108/32 / ч/б / Норма /
    T3), але з ручним Множником сторінковості = 1,2.

    Множник застосовується ТІЛЬКИ до сторінок (§ калькулятора):
      сторінки_база = 700000 / 1290 * (1 + 0,0115) = 548,8759689921...
      сторінки      = 548,8759689921... x 1,2       = 658,6511627907...
      зошитів       = ОКРУГЛ_ВГОРУ(658,6511.../32)  = 21   (було 18 при 1.0)

    Каскадом далі (блок1/ОРИГІНАЛ-МАКЕТ не зачеплені — рахуються від
    знаків, не сторінок):
      блок          = 21 x 50 (ціна зошита) x 1.0 (k_тир T3) x 1.0 (k_колір)
                      = 1050,0     (було 900,0)
      обкладинка_др = 50,0 (не залежить від зошитів — без змін)
      друк_за_шт    = 1050,0 + 50,0 + 0,0 = 1100,0   (було 950,0)
      РРЦ: собівартість_1 = 56519,272727.../3100 + 1100,0 = 1118,2320225...
           3,9 x 1118,2320225... = 4361,1048880...  → округлення до
           найближчого …9 = 4359                       (було 3779)
    """

    def setUp(self):
        self.result = calculate(dict(STORINKOVIST_INPUTS), REFERENCE_PARAMS)

    def test_oryhinal_maket_unchanged(self):
        # Множник не впливає на редакційні статті — тільки на сторінковість.
        self.assertAlmostEqual(self.result["oryhinal_maket"], 56519.27, places=2)

    def test_block2_druk(self):
        block2 = self.result["block2"]
        self.assertIsNotNone(block2)
        self.assertAlmostEqual(block2["storinky"], 658.65, places=2)
        self.assertEqual(block2["zoshytiv"], 21)
        self.assertAlmostEqual(block2["blok"], 1050.0, places=2)
        self.assertAlmostEqual(block2["obkladynka_dr"], 50.0, places=2)
        self.assertAlmostEqual(block2["zriz"], 0.0, places=2)
        self.assertAlmostEqual(self.result["druk_za_sht"], 1100.0, places=2)

    def test_rrc(self):
        self.assertEqual(self.result["rrc"], 4359)


class CompareNakladyTest(unittest.TestCase):
    """Фіча "Порівняння накладів" — default_naklady()/compare_naklady().

    default_naklady() бере по одному репрезентативному накладу на кожен
    тир із params["tiers"] (нижня межа + 100, бо REFERENCE_PARAMS не
    задає колонку "Якір"): [100, 2100, 3100, 5100, 7100] для 5 тирів.
    Наклад для T3 (3000 + 100 = 3100) навмисно збігається з накладом
    основного контрольного прикладу (CalculateReferenceExampleTest) —
    це не збіг, а перевірка, що compare_naklady() відтворює той самий
    результат через звичайний виклик calculate() у циклі.
    """

    def setUp(self):
        self.naklady = default_naklady(REFERENCE_PARAMS["tiers"])
        self.rows = compare_naklady(
            dict(REFERENCE_INPUTS), REFERENCE_PARAMS, sorted(self.naklady)
        )

    def test_default_naklady_count_matches_tiers(self):
        self.assertEqual(len(self.naklady), len(REFERENCE_PARAMS["tiers"]))
        self.assertEqual(self.naklady, [100, 2100.0, 3100.0, 5100.0, 7100.0])

    def test_naklad_3100_matches_single_calculate_reference(self):
        row = next(r for r in self.rows if r["naklad"] == 3100.0)
        result = row["result"]
        self.assertEqual(row["tier"]["tier"], "T3")
        self.assertAlmostEqual(result["oryhinal_maket"], 56519.27, places=2)
        self.assertAlmostEqual(result["druk_za_sht"], 950.0, places=2)
        self.assertEqual(result["rrc"], 3779)

    def test_rrc_non_increasing_as_naklad_grows(self):
        rrcs = [r["result"]["rrc"] for r in self.rows]
        self.assertTrue(all(v is not None for v in rrcs))
        for earlier, later in zip(rrcs, rrcs[1:]):
            self.assertGreaterEqual(
                earlier, later,
                f"РРЦ не повинен зростати зі збільшенням накладу: {rrcs}",
            )

    def test_oryhinal_maket_independent_of_naklad(self):
        oms = {r["result"]["oryhinal_maket"] for r in self.rows}
        self.assertEqual(len(oms), 1)


class RoundTo9Test(unittest.TestCase):
    """Округлення РРЦ — до найближчого числа, що закінчується на 9."""

    def test_round_to_9(self):
        from calculator import _round_to_9

        self.assertEqual(_round_to_9(230), 229)
        self.assertEqual(_round_to_9(235), 239)
        self.assertEqual(_round_to_9(239), 239)
        self.assertEqual(_round_to_9(240), 239)
        self.assertEqual(_round_to_9(244), 249)
        self.assertEqual(_round_to_9(254), 249)
        self.assertEqual(_round_to_9(260), 259)


if __name__ == "__main__":
    unittest.main()
