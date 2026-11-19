import os, sys, unittest
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import notify_rare as n  # noqa: E402

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


class NotifyRareTests(unittest.TestCase):
    def lot(self, **k):
        d = {"title": "2007 FORD MUSTANG", "url": "u1", "rare": True,
             "watchlist_matches": ["Manual Mustang"], "current_bid": 500,
             "auction_ends_at": "2026-11-25T00:00:00Z"}
        d.update(k)
        return d

    def test_only_new_open_rare_lots(self):
        lots = [self.lot(), self.lot(url="u2", rare=False), self.lot(url="u3"),
                self.lot(url="u4", auction_ends_at="2026-11-01T00:00:00Z")]
        got = n.new_rare_lots(lots, {"u3"}, NOW)
        self.assertEqual([l["url"] for l in got], ["u1"])

    def test_issue_text(self):
        t, b = n.build_issue([self.lot()])
        self.assertIn("1 new rare auction find:", t)
        self.assertIn("[2007 FORD MUSTANG](u1)", b)
        self.assertIn("$500", b)


if __name__ == "__main__":
    unittest.main()
