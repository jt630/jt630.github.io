"""merge_deep_lots(): small-engine lots from the full-catalog crawl get
added to the live snapshot (zero extra Musick requests); nothing else does,
and nothing is duplicated."""
import os
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import auction_finder as af  # noqa: E402


def _url(cat, lot, slug="x", q=""):
    return f"https://bid.musickauction.com/lot-details/index/catalog/{cat}/lot/{lot}/{slug}{q}"


def _deep(cat, lot, title, bid=10):
    return {"platform": "musick", "title": title, "url": _url(cat, lot, q="?items=100"),
            "current_bid": bid, "num_bids": 1, "image_url": None, "close_time": None,
            "auction_ends_at": "2026-10-09T01:00:00Z", "description": "Asking bid $11",
            "category": None, "agency": None}


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "auction_lots.yaml")
        doc = {"generated": "2026-10-06", "lots": [
            {"platform": "musick", "title": "2010 FORD F-150", "url": _url(925, 1, q="?url=%2Fa"),
             "agency": "Musick Auction Co. (Meridian, ID)", "current_bid": 500},
            {"platform": "musick", "title": "Bissell Upright Vacuum", "url": _url(925, 2, q="?url=%2Fa"),
             "agency": "Musick Auction Co. (Meridian, ID)", "current_bid": 5},
        ]}
        with open(self.path, "w") as f:
            yaml.dump(doc, f)

    def lots(self):
        return yaml.safe_load(open(self.path))["lots"]

    def test_adds_small_engines_only_and_dedupes_by_lot_id(self):
        deep = [
            _deep(925, 2, "Bissell Upright Vacuum"),            # already present (diff query string)
            _deep(925, 3, "Shop-Vac 12 Gallon Wet/Dry Vacuum"),   # new vacuum -> added
            _deep(925, 4, "Murray Gas Lawn Mower"),               # new mower -> added
            _deep(925, 5, "Ruger SR40 Pistol"),                   # not small engines -> skipped
        ]
        n = af.merge_deep_lots(deep, out_path=self.path)
        self.assertEqual(n, 2)
        titles = [l["title"] for l in self.lots()]
        self.assertEqual(sum("Bissell" in t for t in titles), 1)
        self.assertIn("Shop-Vac 12 Gallon Wet/Dry Vacuum", titles)
        self.assertNotIn("Ruger SR40 Pistol", titles)

    def test_merged_lot_matches_normal_schema_and_agency(self):
        af.merge_deep_lots([_deep(925, 3, "Shop-Vac Wet/Dry Vacuum")], out_path=self.path)
        new = [l for l in self.lots() if "Shop-Vac" in l["title"]][0]
        self.assertEqual(new["category"], "Small Engines & Appliances")
        self.assertEqual(new["agency"], "Musick Auction Co. (Meridian, ID)")
        self.assertEqual(new["auction_ends_at"], "2026-10-09T01:00:00Z")
        for k in ("estimated_value_mid", "deal_score", "value_source", "flagged", "fetched_at"):
            self.assertIn(k, new)

    def test_idempotent(self):
        deep = [_deep(925, 3, "Shop-Vac Wet/Dry Vacuum")]
        self.assertEqual(af.merge_deep_lots(deep, out_path=self.path), 1)
        self.assertEqual(af.merge_deep_lots(deep, out_path=self.path), 0)

    def test_missing_snapshot_is_not_created(self):
        os.remove(self.path)
        self.assertEqual(af.merge_deep_lots([_deep(925, 3, "Vacuum")], out_path=self.path), 0)
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
