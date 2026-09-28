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
            kws = {k.lower() for k in g["keywords"]}
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
        self.assertTrue(all(g.get("id") and g.get("keywords") for g in af.WATCHLIST))


if __name__ == "__main__":
    unittest.main()
