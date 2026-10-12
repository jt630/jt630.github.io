#!/usr/bin/env python3
"""
test_skewer_report.py - offline, stdlib-only unittest coverage for the
skewer pop-up report math (skewer_common.py + skewer_report.py). Expected
numbers are hand-computed from fixtures/skewer_*.csv; see comments.

Run with:
    python -m unittest discover scripts/tests
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import skewer_common as sc  # noqa: E402
import skewer_report as sr  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    return os.path.join(FIX, name)


def load():
    menu = sc.load_menu(fixture("skewer_menu.yaml"))
    nights, rows, warnings = sc.load_log(fixture("skewer_nights.csv"), fixture("skewer_night_items.csv"))
    enriched = sr.enrich_rows(rows, nights, sc.index_menu(menu), warnings)
    return menu, nights, rows, enriched, warnings


class TimeTests(unittest.TestCase):
    def test_parse_formats(self):
        self.assertEqual(sc.parse_time("23:30"), 23 * 60 + 30)
        self.assertEqual(sc.parse_time("1:15"), 75)
        self.assertEqual(sc.parse_time("11:30pm"), 23 * 60 + 30)
        self.assertEqual(sc.parse_time("12am"), 0)
        self.assertIsNone(sc.parse_time(""))

    def test_bad_time_raises(self):
        with self.assertRaises(sc.DataError):
            sc.parse_time("late")

    def test_minutes_after_wraps_midnight(self):
        self.assertEqual(sc.minutes_after("23:00", "01:00"), 120)
        self.assertEqual(sc.minutes_after("23:00", "02:00"), 180)
        self.assertIsNone(sc.minutes_after("23:00", ""))


class DerivedFieldTests(unittest.TestCase):
    def test_units_sold_is_start_minus_end_minus_waste(self):
        _, _, _, enriched, _ = load()
        baked = next(e for e in enriched if e["item"] == "baked")
        self.assertEqual(baked["units"], 10 - 4 - 1)

    def test_cogs_includes_waste(self):
        # baked: 6 consumed (5 sold + 1 wasted) x $1.60
        _, _, _, enriched, _ = load()
        baked = next(e for e in enriched if e["item"] == "baked")
        self.assertAlmostEqual(baked["cogs"], 9.60)

    def test_sold_out_and_hours_stocked(self):
        _, _, _, enriched, _ = load()
        beef1 = next(e for e in enriched if e["item"] == "beef" and e["night"] == "2026-10-16")
        self.assertTrue(beef1["sold_out"])
        self.assertAlmostEqual(beef1["hours"], 2.0)        # 23:00 -> 01:00
        self.assertAlmostEqual(beef1["rate"], 20.0)        # 40 units / 2h
        chorizo1 = next(e for e in enriched if e["item"] == "chorizo" and e["night"] == "2026-10-16")
        self.assertFalse(chorizo1["sold_out"])
        self.assertAlmostEqual(chorizo1["hours"], 3.0)     # not sold out -> whole night

    def test_unknown_menu_item_warns_and_costs_zero(self):
        menu, nights, rows, _, _ = load()
        rows = rows + [dict(rows[0], item="mystery")]
        warnings = []
        enriched = sr.enrich_rows(rows, nights, sc.index_menu(menu), warnings)
        self.assertEqual(enriched[-1]["cogs"], 0)
        self.assertTrue(any("mystery" in w for w in warnings))


class NightSummaryTests(unittest.TestCase):
    def setUp(self):
        menu, nights, _, enriched, _ = load()
        self.ns = {n["night"]: n for n in sr.night_summary(enriched, nights, sc.bundle_discount(menu))}

    def test_bundle_discount(self):
        self.assertEqual(sc.bundle_discount(sc.load_menu(fixture("skewer_menu.yaml"))), 2.0)

    def test_estimated_revenue_applies_bundle_discount(self):
        # 50x$4 + 40x$4 + 5x$7.50 = 397.50, less 5 bundles x $2 = 387.50
        n = self.ns["2026-10-16"]
        self.assertAlmostEqual(n["revenue"], 387.50)
        self.assertEqual(n["revenue_source"], "est")
        self.assertEqual(n["units"], 95)

    def test_gross_sales_overrides_estimate(self):
        n = self.ns["2026-10-17"]
        self.assertEqual(n["revenue"], 300.0)
        self.assertEqual(n["revenue_source"], "actual")

    def test_profit_subtracts_cogs_fee_and_labor(self):
        # 387.50 - (50 + 80 + 9.60) - 50 fee - 100 labor = 97.90
        self.assertAlmostEqual(self.ns["2026-10-16"]["profit"], 97.90)
        # 300 - (40 + 27 + 50) - 0 - 80 = 103
        self.assertAlmostEqual(self.ns["2026-10-17"]["profit"], 103.0)

    def test_units_per_cover(self):
        self.assertAlmostEqual(self.ns["2026-10-16"]["units_per_cover"], 95 / 50)


class ItemAndArmTests(unittest.TestCase):
    def setUp(self):
        _, self.nights, _, self.enriched, _ = load()

    def test_units_per_item_and_best_seller_order(self):
        items = sr.item_summary(self.enriched)
        self.assertEqual([(i["item"], i["units"]) for i in items],
                         [("chorizo", 148), ("beef", 65), ("baked", 5)])

    def test_sellout_rate_overall_and_per_item(self):
        self.assertAlmostEqual(sr.sellout_rate(self.enriched), 2 / 6)
        items = {i["item"]: i for i in sr.item_summary(self.enriched)}
        self.assertAlmostEqual(items["beef"]["sellout_rate"], 0.5)
        self.assertAlmostEqual(items["chorizo"]["sellout_rate"], 1 / 3)

    def test_sellout_rate_empty_is_none(self):
        self.assertIsNone(sr.sellout_rate([]))

    def test_arms_compare_price_and_size(self):
        arms = {(a["item"], a["size"], a["price"]): a for a in sr.arm_summary(self.enriched)}
        small, large = arms[("chorizo", "small", 2.0)], arms[("chorizo", "large", 6.0)]
        self.assertEqual((small["units"], large["units"]), (80, 18))
        self.assertAlmostEqual(small["sell_through"], 1.0)
        self.assertAlmostEqual(large["sell_through"], 18 / 30)
        self.assertAlmostEqual(small["rate"], 80 / 1.5)     # sold out at 00:30
        self.assertAlmostEqual(large["rate"], 6.0)          # 18 units over 3h
        self.assertAlmostEqual(small["margin"], 160 - 40)
        self.assertAlmostEqual(large["margin"], 108 - 27)

    def test_observed_units_per_cover(self):
        # skewer units 90 + 123 over 50 + 40 covers
        self.assertAlmostEqual(sr.observed_units_per_cover(self.enriched, self.nights), 213 / 90)


class ValidationTests(unittest.TestCase):
    def _log(self, items_csv):
        d = tempfile.mkdtemp()
        n, i = os.path.join(d, "n.csv"), os.path.join(d, "i.csv")
        with open(n, "w") as f:
            f.write("night,venue,start,end\n2026-10-16,A,23:00,02:00\n")
        with open(i, "w") as f:
            f.write("night,item,size,price,start_count,end_count,waste,sold_out_time\n" + items_csv)
        return sc.load_log(n, i)

    def test_more_sold_than_started_raises(self):
        with self.assertRaises(sc.DataError):
            self._log("2026-10-16,beef,standard,4,10,8,5,\n")

    def test_unknown_night_raises(self):
        with self.assertRaises(sc.DataError):
            self._log("2099-01-01,beef,standard,4,10,2,0,\n")

    def test_blank_end_count_is_skipped_with_warning(self):
        _, rows, warnings = self._log("2026-10-16,beef,standard,4,10,,,\n")
        self.assertEqual(rows, [])
        self.assertEqual(len(warnings), 1)

    def test_blank_size_defaults_to_standard_and_dollar_sign_ok(self):
        _, rows, _ = self._log("2026-10-16,beef,,$4,10,2,,\n")
        self.assertEqual((rows[0]["size"], rows[0]["price"], rows[0]["waste"]), ("standard", 4.0, 0))

    def test_empty_report_message(self):
        menu = sc.load_menu(fixture("skewer_menu.yaml"))
        self.assertIn("No counted nights", sr.format_report(menu, {}, [], []))

    def test_full_report_renders(self):
        menu, nights, rows, _, warnings = load()
        text = sr.format_report(menu, nights, rows, warnings)
        for needle in ("== NIGHTS ==", "chorizo", "PRICE / SIZE ARMS", "cost"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
