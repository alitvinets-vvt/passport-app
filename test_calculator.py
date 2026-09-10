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

from calculator import calculate

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
