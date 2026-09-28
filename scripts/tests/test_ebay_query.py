#!/usr/bin/env python3
"""
test_ebay_query.py - offline, stdlib-only unittest coverage for
ebay_comps.normalize_query(). No network calls: this only exercises the
string-normalization logic, not lookup()'s HTTP fetch.

Run with:
    python -m unittest discover scripts/tests

The REAL_TITLES below are copied verbatim from data/auction_lots.yaml's
`title:` fields (jewelry, firearms, vehicles, tools/small-appliance "Other"
lots, and heavy equipment), so the assertions reflect what normalize_query()
actually does to the lot titles this site scrapes, not made-up examples.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ebay_comps import normalize_query  # noqa: E402


class NormalizeQueryRealTitlesTests(unittest.TestCase):
    """One assertion per real title, grouped by data/auction_lots.yaml category."""

    # -- Jewelry & Valuables --------------------------------------------
    def test_jewelry_rope_chain_necklace(self):
        title = (
            "Lot #5012: Large Gold-Tone Rope Chain Necklace With Circular "
            "Abalone Shell Pendant, Hammered Finish"
        )
        q = normalize_query(title)
        self.assertNotIn("lot", q)
        self.assertNotIn("#5012", q)
        self.assertNotIn("with", q.split())   # filler word dropped
        self.assertNotIn("large", q.split())  # filler word dropped
        self.assertIn("gold", q)
        self.assertIn("necklace", q)
        self.assertLessEqual(len(q.split()), 6)

    def test_jewelry_platinum_ring_carat_and_karat_survive(self):
        title = (
            "Lot #984: Platinum Ring with 3.25ct Natural Reddish Orange "
            "Coral & 0.18ct Diamond Accents, GIA Certified"
        )
        q = normalize_query(title)
        self.assertIn("3.25ct", q.split())  # decimal survives intact
        self.assertIn("platinum", q)
        self.assertIn("ring", q)

    def test_jewelry_18k_opal_diamond_ring(self):
        title = (
            "Lot #992: 18K White Gold Opal and Diamond Ring, 1.61 ct Opal, "
            "0.36 ct Diamonds, AIGL Appraised"
        )
        q = normalize_query(title)
        self.assertIn("18k", q.split())  # karat token preserved, lowercased
        self.assertNotIn("and", q.split())

    def test_jewelry_14k_rose_gold_pendant(self):
        title = (
            "Lot #974: 14K Rose Gold Pendant Necklace w/ 19.53ct Pear "
            "Morganite, 0.72ct Diamonds, Appraisal #GGA061697"
        )
        q = normalize_query(title)
        self.assertIn("14k", q.split())
        self.assertLessEqual(len(q.split()), 6)

    def test_jewelry_oscar_friedman_platinum_ring(self):
        title = (
            "Lot #973: Oscar Friedman Platinum Ring with 1.95 ct Pink "
            "Sapphire and 1.00 ct Diamonds"
        )
        q = normalize_query(title)
        self.assertNotIn("with", q.split())
        self.assertIn("oscar", q)
        self.assertIn("platinum", q)

    # -- Firearms ----------------------------------------------------------
    def test_firearm_marlin_22_wmr_caliber_survives(self):
        title = (
            'Lot #958: Marlin 25MN .22 WMR Bolt-Action Rifle, 22" Barrel, '
            "7-Round Magazine, Hardwood Stock"
        )
        q = normalize_query(title)
        self.assertIn(".22", q.split())  # leading-dot caliber survives
        self.assertIn("marlin", q.split())
        self.assertTrue(q.split()[0] == "marlin")  # brand leads

    def test_firearm_hipoint_40sw_caliber_survives(self):
        title = (
            "Lot #3002: Hi-Point JCP .40 S&W Semi-Auto Pistol, Polymer "
            "Frame, 4.5\" Barrel, 10rd Mag, SN: X874756"
        )
        q = normalize_query(title)
        self.assertIn(".40", q.split())

    def test_firearm_ruger_380acp_caliber_survives(self):
        title = (
            "Lot #3004: Ruger LCP II .380 ACP 6+1 Semi-Auto Pistol "
            "Stainless Slide Prescott AZ w/ Magazine"
        )
        q = normalize_query(title)
        self.assertIn(".380", q.split())
        self.assertNotIn("w", q.split())  # "w/" -> filler, dropped

    def test_firearm_winchester_no_lot_prefix_variant(self):
        title = (
            "Winchester Model 670 .30-06 SPRG Bolt-Action Rifle, Weaver "
            "Scope Mounts, Sling, Serial G233878"
        )
        # No "Lot #N:" prefix at all - must still normalize cleanly.
        q = normalize_query(title)
        self.assertTrue(q.startswith("winchester"))
        self.assertIn(".30-06", q.split())  # hyphenated caliber stays joined

    def test_firearm_mossberg_30_06_caliber_survives_whole(self):
        # Real title (data/auction_lots.yaml). The hyphenated caliber must
        # come through as one token, not get split or truncated by the
        # 6-token cap - ".30-06" and ".30-30" are real watchlist keywords
        # (data/auction_watchlist.yaml, deer rifle group).
        title = (
            'Lot #5003: Mossberg Patriot Bolt-Action Rifle .30-06 SPRG, '
            '22" Barrel, Synthetic Stock, Serial MPR086752'
        )
        q = normalize_query(title)
        self.assertIn(".30-06", q.split())
        self.assertNotIn(".30", q.split())  # not split into ".30" + "06"

    def test_firearm_30_30_caliber_survives_whole(self):
        title = "Marlin 336 .30-30 Win Lever-Action Rifle, 20in Barrel"
        q = normalize_query(title)
        self.assertIn(".30-30", q.split())

    def test_firearm_308_caliber_edge_case(self):
        # .308 doesn't appear in the current data/auction_lots.yaml, but the
        # task calls it out explicitly as a must-survive edge case: the
        # leading period must not get stripped as stray punctuation.
        title = (
            "Lot #7001: Remington 700 .308 Win Bolt-Action Rifle, Walnut "
            "Stock, 24in Barrel"
        )
        q = normalize_query(title)
        self.assertIn(".308", q.split())

    # -- Vehicles (year/make/model kept, shouted feature dropped) ----------
    def test_vehicle_drops_trailing_feature_shout(self):
        title = "Lot #318: 2012 CHEVROLET TRAVERSE - AWD!"
        self.assertEqual(normalize_query(title), "2012 chevrolet traverse")

    def test_vehicle_hyphenated_model_number_stays_joined(self):
        # "F-550" doesn't appear in the current data/auction_lots.yaml, but
        # it's the module docstring's own example (and this exact title
        # format matches the F-250/F-350 lots that ARE in the data - see
        # test_vehicle_diesel_f250_hyphenated_model below). Must survive as
        # written, not get split into "f" + "550" - eBay treats "f-550" as
        # one keyword.
        title = "Lot #800: 2017 FORD F-550 - BLUETOOTH!"
        self.assertEqual(normalize_query(title), "2017 ford f-550")

    def test_vehicle_diesel_f250_hyphenated_model(self):
        title = "2006 FORD F-250 - 4X4 - DIESEL!"
        q = normalize_query(title)
        self.assertIn("f-250", q.split())

    def test_vehicle_drops_double_bang_feature_shout(self):
        title = "Lot #322: 2010 CHEVROLET EQUINOX - AWD!!"
        self.assertEqual(normalize_query(title), "2010 chevrolet equinox")

    def test_vehicle_drops_local_police_agency_noise(self):
        title = "Lot #612: 2010 DODGE CHARGER - LOCAL POLICE AGENCY!"
        self.assertEqual(normalize_query(title), "2010 dodge charger")

    def test_vehicle_drops_government_surplus_and_mileage(self):
        title = "Lot #613: 2010 DODGE CHARGER - GOVERNMENT SURPLUS! 125K MILES!"
        self.assertEqual(normalize_query(title), "2010 dodge charger")

    def test_vehicle_drops_bank_repo_prefix_segment(self):
        title = "Lot #621: BANK REPO - 2012 TOYOTA PRIUS - HYBRID!"
        q = normalize_query(title)
        self.assertNotIn("bank", q)
        self.assertNotIn("repo", q)
        self.assertIn("2012", q.split())
        self.assertIn("toyota", q.split())
        self.assertIn("prius", q.split())

    def test_vehicle_no_lot_prefix_no_dash(self):
        title = "2011 FORD FLEX - HEATED SEATS"
        q = normalize_query(title)
        self.assertEqual(q, "2011 ford flex")

    def test_vehicle_fully_functional_tractor(self):
        title = (
            "Lot #915: 1960-1970s MASSEY FERGUSON YELLOW TRACTOR - "
            "FULLY FUNCTIONAL!"
        )
        q = normalize_query(title)
        self.assertNotIn("fully", q.split())
        self.assertNotIn("functional", q.split())
        self.assertIn("massey", q.split())
        self.assertIn("ferguson", q.split())

    # -- Tools / small appliances ("Other" category) ------------------------
    def test_tool_pool_cleaner(self):
        title = (
            "Lot #6012: H2 Robotic Pool Cleaner, 25.2V, 110W, Li-ion "
            "battery, 4L Filter Basket"
        )
        q = normalize_query(title)
        self.assertIn("pool", q)
        self.assertIn("cleaner", q)
        self.assertLessEqual(len(q.split()), 6)

    def test_tool_coffee_brewer_model_number(self):
        title = (
            "Lot #6017: Curtis G4 Gemini IntelliFresh Twin Coffee Brewer, "
            "Model G4GEMMXTIFT10A2149, 220V, 1 Phase, 15-21 GPH (Connex 3)"
        )
        q = normalize_query(title)
        self.assertIn("curtis", q.split())
        self.assertLessEqual(len(q.split()), 6)

    def test_tool_rebar_tie_rolls(self):
        title = (
            "Lot #6008: Otooling 19 Gauge Double Wire Rebar Tie Rolls, "
            "105 Ft, 30 Pack, Black Alloy Steel, X004WXTMH9"
        )
        q = normalize_query(title)
        self.assertIn("otooling", q.split())
        self.assertLessEqual(len(q.split()), 6)

    def test_tool_hoist(self):
        title = "Lot #6024: FitHoist 440 lb Mini Electric Hoist"
        q = normalize_query(title)
        self.assertIn("fithoist", q.split())
        self.assertIn("hoist", q.split())

    def test_tool_bar_stools(self):
        title = (
            "Lot #6005: Sweetcrispy Beige Adjustable Swivel Bar Stools "
            "With Footrest"
        )
        q = normalize_query(title)
        self.assertNotIn("with", q.split())
        self.assertIn("sweetcrispy", q.split())

    # -- Heavy equipment -----------------------------------------------------
    def test_heavy_equipment_offsite_car_lift(self):
        title = "Lot #632: (OFFSITE) BenPak Brand Model LR-60P Low-Rise Car Lift"
        q = normalize_query(title)
        self.assertNotIn("offsite", q)
        self.assertIn("benpak", q.split())

    def test_heavy_equipment_boat_and_trailer(self):
        title = "Lot #59: 1996 CHAPARRAL BOAT AND TRAILER"
        q = normalize_query(title)
        self.assertNotIn("and", q.split())
        self.assertIn("1996", q.split())
        self.assertIn("chaparral", q.split())

    # -- Gemstone lots (filler-word-heavy titles) -----------------------------
    def test_gemstone_lot_drops_set_of_small(self):
        title = (
            "Lot #3007: Set of 30 Small Marquise and Oval Cut Uranium "
            "Glass Gemstones"
        )
        q = normalize_query(title)
        for filler in ("set", "of", "small", "and"):
            self.assertNotIn(filler, q.split())
        self.assertIn("30", q.split())

    # -- Edge cases required by the task -------------------------------------
    def test_edge_case_lot_number_only_yields_empty(self):
        # No colon, no descriptive text at all - just the lot number.
        self.assertEqual(normalize_query("Lot #6023"), "")

    def test_edge_case_lot_number_with_colon_only_yields_empty(self):
        self.assertEqual(normalize_query("Lot #6023:"), "")

    def test_edge_case_no_lot_prefix_at_all(self):
        title = "Emperor Arms MPTAC12 Ultra 12GA Pump Shotgun"
        q = normalize_query(title)
        self.assertTrue(q.startswith("emperor arms"))
        self.assertNotIn("lot", q.split())

    def test_edge_case_empty_string(self):
        self.assertEqual(normalize_query(""), "")

    def test_edge_case_none_title(self):
        self.assertEqual(normalize_query(None), "")

    def test_never_returns_query_with_leading_or_trailing_whitespace(self):
        for title in ("Lot #5012: Large Gold-Tone Rope Chain Necklace", "Lot #6023", ""):
            q = normalize_query(title)
            self.assertEqual(q, q.strip())

    def test_always_capped_at_six_tokens(self):
        long_title = (
            "Lot #6000: WLIVE ASNG020 Fabric 5-Drawer Low Storage Cabinet, "
            'White, 39.4" W x 11.8" D x 21.7" H'
        )
        q = normalize_query(long_title)
        self.assertLessEqual(len(q.split()), 6)


if __name__ == "__main__":
    unittest.main()
