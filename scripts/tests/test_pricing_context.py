"""Seller condition text, Musick fee math, and the close-price comp average."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import auction_finder as af  # noqa: E402
import comp_baseline as cb  # noqa: E402
import musick_fees as fees  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


class ConditionTextTests(unittest.TestCase):
    def test_real_lot_page_condition_text(self):
        page = open(os.path.join(FIX, "musick_lot_detail_wrangler.html"), encoding="utf-8").read()
        d = af.parse_musick_lot_detail(page)
        self.assertTrue(d["condition_text"].startswith("5-MILE TEST DRIVE: Runs, Drives"))
        self.assertNotIn("<", d["condition_text"])
        self.assertNotIn("Categories", d["condition_text"])
        self.assertEqual(d["vin"], "1C4BJWEG8HL523632")  # existing parsing unharmed

    def test_missing_description_is_none(self):
        self.assertIsNone(af.parse_musick_lot_detail("<html></html>")["condition_text"])


class FeeTests(unittest.TestCase):
    def test_tiers_and_flat_fees(self):
        self.assertEqual(fees.all_in(3000, "Vehicles"), 3600)
        self.assertEqual(fees.all_in(10000, "Vehicles"), 11150)
        self.assertEqual(fees.all_in(125, "Firearms"), round(125 * 1.15 + 15))
        self.assertIsNone(fees.all_in(None))

    def test_ten_thousand_cliff(self):
        # winning at $10,000 is cheaper all-in than winning at $9,999
        self.assertLess(fees.all_in(10000, "Vehicles"), fees.all_in(9999, "Vehicles"))

    def test_max_bid_round_trips(self):
        b = fees.max_bid_for_budget(3600, "Vehicles")
        self.assertEqual(b, 3000)
        self.assertLessEqual(fees.all_in(b, "Vehicles"), 3600)
        self.assertGreater(fees.all_in(b + 1, "Vehicles"), 3600)


def _close(title, price, days_ago):
    when = NOW - timedelta(days=days_ago)
    c = {"title": title, "price": price, "price_kind": "close", "_when": when}
    c["_vkey"] = cb.vehicle_key(title)
    c["_tok"] = cb.tokens(title)
    return c


class CompTests(unittest.TestCase):
    def test_vehicle_key(self):
        self.assertEqual(cb.vehicle_key("Lot #514: 2010 FORD F-150 - 4X4!"), (2010, "ford", "f150"))
        self.assertEqual(cb.vehicle_key("2017 JEEP GRAND CHEROKEE LIMITED - 4X4!"),
                         (2017, "jeep", "grandcherokee"))
        self.assertEqual(cb.vehicle_key("2011 FORD SUPER DUTY F-250"), (2011, "ford", "f250"))
        self.assertIsNone(cb.vehicle_key("Bissell Upright Vacuum"))

    def test_vehicle_comps_match_model_and_year_window(self):
        closes = [_close("2009 FORD F-150 - 4X4!", 4000, 10), _close("2011 FORD F-150", 5000, 20),
                  _close("2016 FORD F-150", 9000, 5),          # outside +-3 years
                  _close("2010 CHEVROLET SILVERADO", 4500, 5)]  # other model
        b = cb.baseline_for({"title": "2010 FORD F-150 - 4X4!", "category": "Vehicles"}, closes, NOW)
        self.assertEqual(b["comp_n"], 2)
        self.assertEqual(b["comp_median"], 4500)

    def test_junk_prices_are_dropped(self):
        closes = [_close("2017 JEEP WRANGLER", 19, 5), _close("2017 JEEP WRANGLER", 19000, 5),
                  _close("2018 JEEP WRANGLER", 21000, 8)]
        b = cb.baseline_for({"title": "2017 JEEP WRANGLER - 4X4!", "category": "Vehicles"}, closes, NOW)
        self.assertEqual(b["comp_n"], 2)

    def test_generic_overlap_is_not_a_comp(self):
        closes = [_close("Smith & Wesson Pocket Knife Set", 30, 5),
                  _close("Makita Cordless Drill", 40, 5)]
        lot = {"title": "Smith & Wesson SW9VE 9mm Pistol", "category": "Firearms"}
        self.assertIsNone(cb.baseline_for(lot, closes, NOW))

    def test_model_code_match(self):
        closes = [_close("Smith & Wesson SW9VE 9mm Pistol, Stainless", 190, 12)]
        lot = {"title": "Lot #955: Smith & Wesson SW9VE 9mm Pistol, Stainless Slide", "category": "Firearms"}
        self.assertEqual(cb.baseline_for(lot, closes, NOW)["comp_median"], 190)

    def test_other_categories_get_no_baseline(self):
        closes = [_close("1974-S Eisenhower Silver Dollar", 60, 5)]
        lot = {"title": "1974-S Eisenhower Silver Dollar", "category": "Jewelry & Valuables"}
        self.assertIsNone(cb.baseline_for(lot, closes, NOW))

    def test_recency_weighting_and_span(self):
        closes = [_close("2010 FORD F-150", 3000, 200), _close("2010 FORD F-150", 5000, 5)]
        b = cb.baseline_for({"title": "2010 FORD F-150", "category": "Vehicles"}, closes, NOW)
        self.assertGreater(b["comp_wavg"], b["comp_median"])  # recent close dominates
        self.assertEqual(b["comp_span_days"], 200)
        self.assertEqual(b["comp_30d"], 5000)

    def test_closes_older_than_a_year_ignored(self):
        closes = [_close("2010 FORD F-150", 3000, 400)]
        self.assertIsNone(cb.baseline_for({"title": "2010 FORD F-150", "category": "Vehicles"}, closes, NOW))


if __name__ == "__main__":
    unittest.main()
