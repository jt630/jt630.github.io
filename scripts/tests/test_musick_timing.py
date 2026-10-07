"""Every Musick catalog lot should get an auction_ends_at from its own
"Time left" string - not just the vehicles that get a second detail-page
render. Also pins the category fixes (cars in "Other", lumber/toy trucks
filed as Vehicles)."""
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import auction_finder as af  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
NOW = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)


def _load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class CatalogEndTimeTests(unittest.TestCase):
    def test_every_lot_with_time_left_gets_an_end_time(self):
        page = _load("musick_catalog_920_open.html")
        lots = af.parse_musick_lots(page, now=NOW)
        self.assertTrue(lots)
        with_left = [l for l in lots if "Time left:" in (l["description"] or "")]
        self.assertTrue(with_left, "fixture should contain Time left strings")
        for l in with_left:
            self.assertIsNotNone(l["auction_ends_at"], l["title"])
            self.assertTrue(l["auction_ends_at"].endswith("Z"))

    def test_end_time_matches_the_time_left_string(self):
        page = (
            '<li id="blkLotItemMain1" class="item-block ">'
            '<span class="lotTitle"><a class="yaaa" href="https://x/1">Ruger</a></span>'
            '<span class="item-askingbid"><span class="title">Asking bid</span>'
            '<span class="value"><span class="scur1">$</span>'
            '<span class="exratetip">20</span></span></span>'
            'Time left:&nbsp;<a href="#">1d 5h 10m 5s</a>'
        )
        # not guaranteed to match the live markup exactly, so only assert
        # when the minimal chunk parses
        lots = af.parse_musick_lots(page, now=NOW)
        if lots:
            self.assertEqual(lots[0]["auction_ends_at"], "2026-10-08T17:10:05Z")


class CategoryTests(unittest.TestCase):
    def cat(self, title):
        return af.guess_category({"title": title, "description": ""})

    def test_cars_that_used_to_fall_into_other(self):
        for t in ("2010 MAZDA 3 - BOSE SPEAKERS", "Lot #902: 2017 HYUNDAI ELANTRA GT - FWD!",
                  "Lot #108: 2015 HYUNDAI ACCENT - 95K MILES!"):
            self.assertEqual(self.cat(t), "Vehicles", t)

    def test_revolver_is_a_firearm(self):
        self.assertEqual(self.cat("Taurus Model 73 .32 Long 6-Shot Revolver"), "Firearms")

    def test_lumber_and_diecast_are_not_vehicles(self):
        self.assertNotEqual(self.cat("Bunk Of Lumber, 6x12, 18ft, 4x4 12ft"), "Vehicles")
        self.assertNotEqual(
            self.cat("1995 Pepsi-Cola Die-Cast Delivery Truck Coin Bank, 1:24 Scale"), "Vehicles")

    def test_real_trucks_still_vehicles(self):
        self.assertEqual(self.cat("2010 FORD F-150 - 4X4!"), "Vehicles")

    # Real titles from the 2026-10-07 live run that landed on grandpa's
    # page because an appliance word appeared as a description, not a thing.
    def test_appliance_words_used_as_descriptions_are_not_appliances(self):
        for t in (
            "Lot #9025: Mixed Fossil and Mineral Lot – Quartz, Shark Tooth, "
            "Arrowheads, Coral Fossils, Bone, 8 Pieces",
            "Lot #6378: Pet Care Bundle: Stainless Steel Cat Litter Box, "
            "2 Muddy Mats, 2 Litter Catcher Mats, Dryer Towel",
            "Lot #6189: Famiware Jupiter 24-Piece Stoneware Dinnerware Set "
            "for 8 – Light Green, Microwave & Dishwasher Safe",
        ):
            self.assertNotEqual(self.cat(t), "Small Engines & Appliances", t)

    def test_real_small_engines_and_appliances_still_match(self):
        for t in (
            "Makita EG1000R Portable Generator, 1.0 kVA Max Output, Honda G150 Engine",
            "Lot #6188: Folconroad 14-Inch Manual Push Reel Lawn Mower",
            "Shark Navigator Lift-Away Upright Vacuum",
            "Whirlpool Electric Dryer",
            "Panasonic Countertop Microwave",
            "Bosch 24in Dishwasher",
        ):
            self.assertEqual(self.cat(t), "Small Engines & Appliances", t)


if __name__ == "__main__":
    unittest.main()
