"""Watchlist matching: the `exclude` rule, and the real collisions the
current data/auction_watchlist.yaml was designed around (see the comments
there and .claude/commands/refine-search.md). Offline - titles are real
Musick titles or realistic stand-ins, no network."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import auction_finder as af  # noqa: E402
import watchlist_test as wt  # noqa: E402


class ExcludeRuleTests(unittest.TestCase):
    def test_exclude_vetoes_a_keyword_hit(self):
        g = {"keywords": ["hellcat"], "exclude": ["dodge"]}
        self.assertTrue(af.group_matches(g, " springfield armory hellcat 9mm "))
        self.assertFalse(af.group_matches(g, " 2019 dodge challenger srt hellcat "))

    def test_no_exclude_key_behaves_as_before(self):
        self.assertTrue(af.group_matches({"keywords": ["pickup"]}, " ford pickup "))


class VehiclesOnlyTests(unittest.TestCase):
    def test_floor_scrubber_is_not_a_commuter_car(self):
        lot = {"title": "Lot #7024: Nobles Focus II Walk-Behind Floor Scrubber, 20\" Path"}
        orig = af.WATCHLIST
        af.WATCHLIST = [{"label": "Commuter", "keywords": ["focus"], "vehicles_only": True}]
        try:
            self.assertEqual(af.match_watchlist(lot), [])
            real = {"title": "2018 FORD FOCUS - 90K MILES!"}
            self.assertEqual(af.match_watchlist(real), ["Commuter"])
        finally:
            af.WATCHLIST = orig


class CollisionGuardTests(unittest.TestCase):
    """Guard RULES, not a pinned watchlist: the owner edits
    data/auction_watchlist.yaml freely, and this suite runs as the daily
    bot's pre-commit gate - pinning exact keywords would let a legitimate
    edit silently stop the data commits. So each test only fires when a
    group actually uses a known-colliding term, and then requires that the
    real collision seen on Musick is excluded."""

    KNOWN_COLLISIONS = {
        # bare keyword -> real/realistic Musick titles it must NOT match
        "hellcat": ["2019 Dodge Challenger SRT Hellcat", "2021 Dodge Charger SRT Hellcat"],
        "g29": ["Logitech G29 Driving Force Racing Wheel"],
        "pistol": [  # real titles the old bare "pistol" group matched
            "D & B Supply 25 Gallon 12V ATV Spot Sprayer, 2.2 GPM Pump, 15 ft Hose, Pistol Grip Wand",
            "Hornady .38/.357 Cal 158 Gr Hollow Point Pistol Bullets, 2 Boxes Of 100 Reloading Projectiles",
            "Mixed Lot of 44 Rifle & Pistol Cartridges: .223, .308, 9mm, .45, .38, Brass/Nickel, FMJ",
        ],
    }

    def test_groups_using_a_colliding_term_exclude_the_collision(self):
        for g in af.WATCHLIST:
            kws = {k.lower() for k in g.get("keywords") or []}
            for term, bad_titles in self.KNOWN_COLLISIONS.items():
                if term not in kws:
                    continue
                for t in bad_titles:
                    self.assertFalse(
                        af.group_matches(g, f" {t} ".lower()),
                        f"group {g.get('id')!r} uses bare {term!r} and matches {t!r} - "
                        f"add an exclude (see .claude/commands/refine-search.md)",
                    )


class WatchlistTestToolTests(unittest.TestCase):
    def test_tool_runs_offline_and_every_group_loads(self):
        self.assertEqual(wt.main([]), 0)
        self.assertTrue(all(g.get("id") and (g.get("keywords") or g.get("regex") or g.get("year_ranges")) for g in af.WATCHLIST))


if __name__ == "__main__":
    unittest.main()


class StructuredRuleTests(unittest.TestCase):
    """structured_ok(): transmission / drivetrain / year rules on a group."""

    def test_unknown_transmission_and_drivetrain_pass(self):
        g = {"transmission": "manual", "drivetrain": ["4x4", "4wd"]}
        self.assertTrue(af.structured_ok(g, {"title": "2014 JEEP WRANGLER"}))

    def test_known_auto_or_2wd_fails(self):
        g = {"transmission": "manual", "drivetrain": ["4x4", "4wd"]}
        self.assertFalse(af.structured_ok(g, {"transmission": "Auto", "drivetrain": "4x4"}))
        self.assertFalse(af.structured_ok(g, {"transmission": "Manual", "drivetrain": "2WD"}))
        self.assertTrue(af.structured_ok(g, {"transmission": "Manual", "drivetrain": "4x4"}))

    def test_year_ranges_use_title_year_and_exclude_gap(self):
        g = {"year_ranges": [[2005, 2100], [1900, 1985]]}
        ok = lambda t: af.structured_ok(g, {"title": t})
        self.assertTrue(ok("2007 FORD MUSTANG - 5-SPEED MANUAL!"))
        self.assertTrue(ok("BANK REPO - 2014 FORD MUSTANG"))
        self.assertTrue(ok("1966 FORD MUSTANG"))
        self.assertFalse(ok("1990 FORD MUSTANG - ROLL CAGE!"))
        self.assertFalse(ok("2000 FORD MUSTANG - RWD!"))

    def test_year_rule_rejects_titles_without_leading_year(self):
        g = {"year_ranges": [[1900, 1989]]}
        self.assertFalse(af.structured_ok(g, {"title": "Haynes Ford Mustang II 1974-1978 Repair Manual"}))

    def test_year_only_group_and_not_year_led(self):
        orig = af.WATCHLIST
        af.WATCHLIST = [
            {"label": "Classic", "vehicles_only": True, "year_ranges": [[1900, 1989]]},
            {"label": "Forester acc", "not_year_led": True, "keywords": ["forester"]},
        ]
        try:
            self.assertEqual(af.match_watchlist({"title": "1969 DODGE D100 - 60K MILES!"}), ["Classic"])
            self.assertEqual(af.match_watchlist({"title": "2014 SUBARU FORESTER - AWD!"}), [])
            self.assertEqual(
                af.match_watchlist({"title": "Subaru Forester 2019 Cargo Mat & Roof Crossbars"}),
                ["Forester acc"],
            )
        finally:
            af.WATCHLIST = orig

    def test_regex_dirt_bike_needs_make_and_model(self):
        g = {"regex": [r"\b(honda|yamaha|suzuki|kawasaki)\s+(crf|xr|yz|ttr|kx)\s?-?\d{2,3}\b"]}
        self.assertTrue(af.group_matches(g, " 2004 yamaha ttr90 "))
        self.assertFalse(af.group_matches(g, " mongoose xr-75 mountain bike "))
