#!/usr/bin/env python3
"""
test_skewer_prep.py - offline, stdlib-only unittest coverage for the prep
sheet generator and the open/close logging helpers (skewer_prep.py,
skewer_log.py). Uses fixtures/skewer_menu.yaml, not the real menu, so editing
research/skewer_popup/menu.yaml never breaks these.

Run with:
    python -m unittest discover scripts/tests
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import skewer_common as sc  # noqa: E402
import skewer_log as sl  # noqa: E402
import skewer_prep as sp  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
MENU = sc.load_menu(os.path.join(FIX, "skewer_menu.yaml"))


def units(rows):
    return {(r["item_id"], r["size"]): r["units"] for r in rows}


class PlanTests(unittest.TestCase):
    def test_whole_menu_quantities(self):
        # 100 covers x 3.0 = 300 skewers split 2:1:1 -> 150/75/75, +10% buffer
        # (165 / 82.5->83 / 83); baked potato = 0.1 x 100 x 1.1 = 11
        rows = sp.plan(MENU, 100, sp.parse_lineup(MENU, ""))
        self.assertEqual(units(rows), {("chorizo", "standard"): 165, ("beef", "standard"): 83,
                                       ("smash", "standard"): 83, ("baked", "standard"): 11})

    def test_float_noise_does_not_round_up(self):
        # 150 x 1.1 is 165.00000000000003 in floating point; must stay 165
        rows = sp.plan(MENU, 100, sp.parse_lineup(MENU, "chorizo,beef,smash"))
        self.assertEqual(units(rows)[("chorizo", "standard")], 165)

    def test_overrides(self):
        rows = sp.plan(MENU, 100, sp.parse_lineup(MENU, "chorizo,beef"), units_per_cover=2, buffer_pct=0)
        # 200 skewers split 2:1
        self.assertEqual(units(rows), {("chorizo", "standard"): 134, ("beef", "standard"): 67})

    def test_sizes_run_side_by_side_and_split_evenly(self):
        lineup = sp.parse_lineup(MENU, "chorizo:small@2,chorizo:large@6,beef")
        rows = sp.plan(MENU, 100, lineup)
        # chorizo gets 2/3 of 300 = 200 -> 100 each size, x1.1 = 110; beef 100 x 1.1 = 110
        self.assertEqual(units(rows), {("chorizo", "small"): 110, ("chorizo", "large"): 110,
                                       ("beef", "standard"): 110})

    def test_history_weights_replace_menu_mix(self):
        rows = sp.plan(MENU, 100, sp.parse_lineup(MENU, "chorizo,beef"), buffer_pct=0,
                       weights={"chorizo": 1, "beef": 3})
        self.assertEqual(units(rows), {("chorizo", "standard"): 75, ("beef", "standard"): 225})


class LineupTests(unittest.TestCase):
    def test_price_override(self):
        lineup = sp.parse_lineup(MENU, "beef@5.5")
        self.assertEqual(lineup[0]["price"], 5.5)
        self.assertEqual(lineup[0]["variant"]["size"], "standard")

    def test_unknown_item_and_size_raise(self):
        with self.assertRaises(sc.DataError):
            sp.parse_lineup(MENU, "nope")
        with self.assertRaises(sc.DataError):
            sp.parse_lineup(MENU, "chorizo:huge")

    def test_duplicate_raises(self):
        with self.assertRaises(sc.DataError):
            sp.parse_lineup(MENU, "beef,beef")


class MorningAndIngredientTests(unittest.TestCase):
    def test_parboil_math(self):
        # 83 smash units x 4 potatoes = 332, +20% = 398.4 -> 399, / 12 per lb = 33.25 lb
        rows = sp.plan(MENU, 100, sp.parse_lineup(MENU, ""))
        task = next(t for t in sp.morning_tasks(rows) if t.startswith("PARBOIL"))
        self.assertIn("33.2 lb", task)  # 33.25 rounds half-even to 33.2
        self.assertIn("~399", task)

    def test_ingredient_totals_scale_by_portion(self):
        lineup = sp.parse_lineup(MENU, "chorizo:small,chorizo:large")
        rows = sp.plan(MENU, 90, lineup, buffer_pct=0)  # 270 skewers, 135 each size
        # 135 x 30g x 0.5 + 135 x 30g x 1.5 = 8100 g
        self.assertAlmostEqual(sp.ingredient_totals(rows)[("chorizo", "g")], 8100)

    def test_no_parboil_without_potato_item(self):
        rows = sp.plan(MENU, 100, sp.parse_lineup(MENU, "beef"))
        self.assertEqual(sp.morning_tasks(rows), [])

    def test_sheet_flags_unconfirmed_values(self):
        rows = sp.plan(MENU, 100, sp.parse_lineup(MENU, "beef"))
        self.assertIn("beef/standard: cost", sp.format_sheet(MENU, 100, rows, "3.00 skewers/cover"))


class LogTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.nights = os.path.join(self.dir, "nights.csv")
        self.items = os.path.join(self.dir, "night_items.csv")
        sc.write_csv(self.nights, sc.NIGHT_COLS, [])
        sc.write_csv(self.items, sc.ITEM_COLS, [])

    def _open(self, night="2026-10-16"):
        return sl.open_night(MENU, self.nights, self.items, night, "Brewery A", "23:00", 100,
                             "chorizo:small@2,beef")

    def test_open_prefills_start_counts_and_prices(self):
        self._open()
        rows = sc.read_csv(self.items, sc.ITEM_COLS)
        got = {(r["item"], r["size"]): (r["price"], r["start_count"], r["end_count"]) for r in rows}
        # chorizo 2/3 of 300 = 200 x1.1 = 220; beef 100 x1.1 = 110
        self.assertEqual(got, {("chorizo", "small"): ("2", "220", ""), ("beef", "standard"): ("4", "110", "")})
        self.assertEqual(sc.read_csv(self.nights, sc.NIGHT_COLS)[0]["start"], "23:00")

    def test_open_twice_same_night_refuses(self):
        self._open()
        with self.assertRaises(sc.DataError):
            self._open()

    def test_uncounted_night_is_skipped_by_report_loader(self):
        self._open()
        _, rows, warnings = sc.load_log(self.nights, self.items)
        self.assertEqual((rows, len(warnings)), ([], 2))

    def test_close_fills_counts_and_night_totals(self):
        self._open()
        # prompts in order: chorizo left, waste, sold-out time; beef left, waste;
        # then end, covers, wait, weather, bundles, gross, fee, labor, notes
        answers = iter(["0", "2", "00:30", "30", "", "02:00", "88", "5", "clear", "", "412.5", "50", "", "go"])
        sl.close_night(self.nights, self.items, "2026-10-16", input_fn=lambda _p: next(answers))
        _, rows, warnings = sc.load_log(self.nights, self.items)
        by = {r["item"]: r for r in rows}
        self.assertEqual((by["chorizo"]["end"], by["chorizo"]["waste"], by["chorizo"]["sold_out_time"]),
                         (0, 2, "00:30"))
        self.assertEqual((by["beef"]["end"], by["beef"]["waste"]), (30, 0))
        night = sc.read_csv(self.nights, sc.NIGHT_COLS)[0]
        self.assertEqual((night["covers"], night["gross_sales"], night["bundles_sold"], night["labor"]),
                         ("88", "412.5", "", ""))
        self.assertEqual(warnings, [])

    def test_close_reasks_on_bad_input(self):
        self._open()
        answers = iter(["lots", "5", "", "", ] + [""] * 20)
        sl.close_night(self.nights, self.items, "2026-10-16", input_fn=lambda _p: next(answers))
        _, rows, _ = sc.load_log(self.nights, self.items)
        self.assertEqual(rows[0]["end"], 5)

    def test_interrupted_close_keeps_progress(self):
        self._open()
        answers = iter(["7", "0"])  # first item only, then the terminal "hangs up"

        def input_fn(_p):
            try:
                return next(answers)
            except StopIteration:
                raise EOFError

        sl.close_night(self.nights, self.items, "2026-10-16", input_fn=input_fn)
        _, rows, warnings = sc.load_log(self.nights, self.items)
        self.assertEqual([(r["item"], r["end"]) for r in rows], [("chorizo", 7)])
        self.assertEqual(len(warnings), 1)  # beef still uncounted


if __name__ == "__main__":
    unittest.main()
