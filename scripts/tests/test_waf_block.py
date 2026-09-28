#!/usr/bin/env python3
"""
test_waf_block.py - offline unittest coverage for the "back off when a site
pushes back" behavior added after the 2026-09-28 AWS WAF block on
bid.musickauction.com (and eBay 403s): musick_render.looks_blocked(), the
price_history.py and auction_finder.py circuit breakers, and the ebay_comps.py
403 breaker. No network: every render/fetch is an injected fake, and
time.sleep is patched to a no-op.

Run with:
    python -m unittest discover scripts/tests
"""

import json
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import auction_finder as af  # noqa: E402
import ebay_comps  # noqa: E402
import musick_render  # noqa: E402
import price_history as ph  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Stand-in for the real 212-byte page from the production log. We never saved
# the actual page, so this is only "something tiny", not its real markup.
BLOCKED_212 = "<html><body>" + "x" * 186 + "</body></html>"


def _read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def _noop_sleep(*a, **kw):
    return None


class LooksBlockedTests(unittest.TestCase):
    def test_212_byte_page_is_blocked(self):
        self.assertEqual(len(BLOCKED_212), 212)
        self.assertTrue(musick_render.looks_blocked(BLOCKED_212))

    def test_real_fixture_is_not_blocked(self):
        self.assertFalse(musick_render.looks_blocked(_read("musick_catalog_914_p1.html")))

    def test_real_404_page_is_gone_not_blocked(self):
        # Byte-for-byte the page Musick served for deleted lot 509410
        # (catalog 911) on 2026-09-28. A deleted lot must never trip the
        # breaker, or one withdrawn vehicle would freeze the whole day's run.
        real_404 = ('<html lang="en"><head><title>404 Not Found</title></head>'
                    '<body><h1>404 Page Not Found</h1><a href="/">Go to the '
                    'homepage</a></body></html>')
        self.assertEqual(len(real_404), 138)
        self.assertTrue(musick_render.looks_not_found(real_404))
        self.assertFalse(musick_render.looks_blocked(real_404))
        # ...while a same-sized non-404 page is still treated as blocked.
        self.assertFalse(musick_render.looks_not_found(BLOCKED_212))

    def test_empty_and_none_are_blocked(self):
        self.assertTrue(musick_render.looks_blocked(""))
        self.assertTrue(musick_render.looks_blocked(None))

    def test_large_challenge_page_is_blocked_only_without_real_content(self):
        pad = "x" * 3000
        self.assertTrue(musick_render.looks_blocked(f"<html>{pad} Access Denied </html>"))
        self.assertTrue(musick_render.looks_blocked(f"<html>{pad} AWSWAF Challenge </html>"))
        # A real page that merely mentions "captcha" somewhere is not blocked.
        self.assertFalse(musick_render.looks_blocked(f'<li id="blkLotItemMain1">{pad} captcha </li>'))
        self.assertFalse(musick_render.looks_blocked(f'<script data-server="server-data-json">{pad} captcha'))

    def test_large_plain_page_without_markers_is_not_blocked(self):
        self.assertFalse(musick_render.looks_blocked("<html>" + "y" * 3000 + "</html>"))

    def test_block_note_text(self):
        self.assertEqual(
            musick_render.BLOCK_NOTE,
            "BLOCKED (bot protection / rate limit), backing off; see docs/AUCTION-MONITORING.md",
        )


def _index_and_ids():
    index_page = _read("musick_closed_index_p1.html")
    closed = ph._closed_candidates(ph.extract_closed_index_rows(index_page))
    return index_page, [cid for cid, _ in closed]


@patch("price_history.time.sleep", _noop_sleep)
class PriceHistoryBlockTests(unittest.TestCase):
    def _run(self, render):
        """daily_harvest with `render` standing in for BOTH the index and
        catalog renders (harvest_catalog imports render_catalog_page at call
        time, so patching musick_render covers it)."""
        notes = []
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "_harvested.json")
            with patch("musick_render.render_catalog_page", render):
                ph.daily_harvest(notes, price_history_dir=d, state_path=state_path)
            state = ph.load_state(state_path)
            state_file_exists = os.path.exists(state_path)
        return notes, state, state_file_exists

    def test_constants(self):
        self.assertEqual(ph.SLEEP_BETWEEN_RENDERS, 5.0)
        self.assertEqual(ph.DAILY_CATALOG_CAP, 3)

    def test_blocked_index_attempts_nothing_and_marks_nothing(self):
        calls = []

        def render(url, *a, **kw):
            calls.append(url)
            return BLOCKED_212, []

        notes, state, state_file_exists = self._run(render)
        self.assertEqual(state, {"catalogs": {}})
        self.assertFalse(state_file_exists)  # state file untouched
        self.assertTrue(all("alf1=4" in u for u in calls), calls)  # index only, no catalogs
        self.assertEqual(len(calls), 1)  # and no retry
        joined = "\n".join(notes)
        self.assertIn(musick_render.BLOCK_NOTE, joined)
        self.assertIn("212 bytes", joined)
        self.assertIn("0 row(s) parsed", joined)

    def test_index_bytes_and_rows_are_always_logged(self):
        index_page, ids = _index_and_ids()

        def render(url, *a, **kw):
            if "alf1=4" in url:
                return index_page, []
            return None, []  # every catalog render fails (not a block)

        notes, _, _ = self._run(render)
        self.assertTrue(
            any(f"{len(index_page)} bytes" in n and "row(s) parsed" in n for n in notes), notes
        )

    def test_blocked_second_catalog_stops_the_run(self):
        index_page, ids = _index_and_ids()
        self.assertGreaterEqual(len(ids), 3, "fixture must offer 3+ closed catalogs")
        first, second, third = (str(i) for i in ids[:3])
        catalog_calls = []

        def render(url, *a, **kw):
            if "alf1=4" in url:
                return index_page, []
            m = re.search(r"/catalog/id/(\d+)", url)
            cid = m.group(1)
            catalog_calls.append(cid)
            if cid == first:
                if "page=1" in url:
                    return _read("musick_catalog_914_p1.html"), []
                return "<html></html>" + "<!-- " + "x" * 3000 + " -->", []  # clean end
            return BLOCKED_212, []

        notes, state, _ = self._run(render)
        self.assertIn(first, state["catalogs"])       # first harvested and marked
        self.assertNotIn(second, state["catalogs"])   # blocked -> unmarked
        self.assertNotIn(third, state["catalogs"])
        self.assertNotIn(third, catalog_calls)             # third never rendered
        self.assertEqual(catalog_calls.count(second), 1)   # blocked one not retried
        joined = "\n".join(notes)
        self.assertIn(musick_render.BLOCK_NOTE, joined)
        self.assertIn("2 catalog(s) attempted", joined)


class _FakeMusickSite:
    """Injected render for auction_finder: event URLs .../catalog/id/N. Ids in
    `blocked_ids` return a tiny block page; everything else returns the real
    50-lot fixture. Records every URL rendered."""

    def __init__(self, blocked_ids=()):
        self.blocked_ids = set(blocked_ids)
        self.calls = []

    def __call__(self, url, *a, **kw):
        self.calls.append(url)
        m = re.search(r"/catalog/id/(\d+)$", url)
        if m and int(m.group(1)) in self.blocked_ids:
            return BLOCKED_212, []
        return _read("musick_catalog_914_p1.html"), []


EVENTS = [
    {"platform": "musick", "title": f"Event {n}", "url": f"https://bid.musickauction.com/auctions/catalog/id/{n}",
     "agency": "Musick Auction Co. (Nampa)"}
    for n in (1, 2, 3)
]


@patch("auction_finder.time.sleep", _noop_sleep)
class AuctionFinderBlockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = os.path.join(self.tmp.name, "auction_lots.yaml")
        with open(self.out, "w", encoding="utf-8") as f:
            f.write("SENTINEL: yesterday's complete snapshot\n")
        for target, value in [
            ("auction_finder.OUT", self.out),
            ("auction_finder.CACHE_DIR", os.path.join(self.tmp.name, "cache")),
            ("auction_finder.fetch", lambda url, headers=None: (200, "<html>events</html>")),
            ("auction_finder.parse_musick_events", lambda page: [dict(e) for e in EVENTS]),
            ("auction_finder.brute_force_musick_api", lambda events, notes: None),
        ]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def _main_with_site(self, site):
        real = af.fetch_musick
        with patch("auction_finder.fetch_musick",
                   lambda notes, run=None: real(notes, run=_with_render(run, site))):
            af.main([])

    def test_blocked_catalog_stops_renders_and_skips_the_write(self):
        site = _FakeMusickSite(blocked_ids={2})
        self._main_with_site(site)
        catalog_urls = [u for u in site.calls if re.search(r"/catalog/id/\d+$", u)]
        self.assertEqual([u.rsplit("/", 1)[-1] for u in catalog_urls], ["1", "2"])  # 3 never rendered
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(f.read(), "SENTINEL: yesterday's complete snapshot\n")  # untouched

    def test_no_block_still_writes(self):
        site = _FakeMusickSite()
        self._main_with_site(site)
        with open(self.out, encoding="utf-8") as f:
            self.assertNotIn("SENTINEL", f.read())

    def test_blocked_catalog_note_names_url_and_bytes_not_markup(self):
        site = _FakeMusickSite(blocked_ids={1})
        notes = []
        run = af.MusickRun(render=site)
        rows = af.fetch_musick_catalog(EVENTS[0]["url"], notes, run)
        self.assertEqual(rows, [])
        self.assertTrue(run.blocked)
        joined = "\n".join(notes)
        self.assertIn(EVENTS[0]["url"], joined)
        self.assertIn("212 bytes", joined)
        self.assertIn(musick_render.BLOCK_NOTE, joined)
        self.assertNotIn("markup may have changed", joined)
        # once open, the breaker renders nothing further
        n = len(site.calls)
        af.fetch_musick_catalog(EVENTS[1]["url"], notes, run)
        self.assertEqual(len(site.calls), n)

    def test_blocked_vehicle_detail_trips_breaker(self):
        run = af.MusickRun(render=lambda url: (BLOCKED_212, []))
        notes = []
        af.fetch_musick_vehicle_detail({"url": "https://bid.musickauction.com/lot/1"}, notes, run)
        self.assertTrue(run.blocked)
        self.assertIn(musick_render.BLOCK_NOTE, "\n".join(notes))

    def test_large_page_with_zero_lots_keeps_markup_message(self):
        page = "<html>" + "z" * 3000 + "</html>"
        notes = []
        run = af.MusickRun(render=lambda url: (page, []))
        af.fetch_musick_catalog(EVENTS[0]["url"], notes, run)
        self.assertFalse(run.blocked)
        self.assertIn("markup may have changed", "\n".join(notes))


def _with_render(run, site):
    run = run or af.MusickRun()
    run.render = site
    return run


class EbayCircuitBreakerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch("ebay_comps.CACHE_DIR", self.tmp.name)
        p.start()
        self.addCleanup(p.stop)
        ebay_comps.reset_circuit()
        self.addCleanup(ebay_comps.reset_circuit)
        self.calls = []

        def fake_fetch(url, headers=None):
            self.calls.append(url)
            return 403, ""

        p2 = patch("ebay_comps.fetch", fake_fetch)
        p2.start()
        self.addCleanup(p2.stop)

    def test_after_403_no_more_fetches(self):
        notes = []
        self.assertIsNone(ebay_comps.lookup("Kirby G6 vacuum", notes=notes))
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(ebay_comps.circuit_open())
        for q in ("Stihl chainsaw", "Craftsman table saw", "Honda generator"):
            self.assertIsNone(ebay_comps.lookup(q, notes=notes))
        self.assertEqual(len(self.calls), 1)  # zero fetches after the 403
        self.assertIn("circuit open after 403, skipped 3 lookups", ebay_comps.circuit_summary())

    def test_skipped_lookup_still_returns_cache(self):
        ebay_comps.lookup("Kirby G6 vacuum", notes=[])  # trips the breaker
        cached = {"n": 8, "median": 95.0, "low": 62.0, "high": 140.0}
        key = ebay_comps._cache_key(ebay_comps.normalize_query("Stihl chainsaw"))
        with open(os.path.join(self.tmp.name, f"ebay_{key}.json"), "w") as f:
            json.dump(cached, f)
        notes = []
        self.assertEqual(ebay_comps.lookup("Stihl chainsaw", notes=notes), cached)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(any("cached comps" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
