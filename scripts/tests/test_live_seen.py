#!/usr/bin/env python3
"""
test_live_seen.py - offline, stdlib-only unittest coverage for
live_seen.py (Session B2). No network calls - fake render functions and
real saved HTML fixtures only, same pattern as test_price_history.py.

Run with:
    python -m unittest discover scripts/tests
"""

import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import live_seen as ls  # noqa: E402
import price_history as ph  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def _fake_render(pages_by_number, default=None):
    """Same dispatch-on-page-number fake as test_price_history.py's."""
    def render(url):
        m = re.search(r"page=(\d+)", url)
        n = int(m.group(1)) if m else 1
        html = pages_by_number.get(n, default)
        if html is None:
            return None, []
        return html, []
    return render


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class OpenCandidatesClosingSoonTests(unittest.TestCase):
    def test_excludes_closed_status(self):
        now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            {"id": "1", "status": "3", "end_date": "2026-09-29 20:00:00"},  # closed
            {"id": "2", "status": "1", "end_date": "2026-09-30 12:00:00"},  # open, +24h
        ]
        out = ls.open_candidates_closing_soon(rows, now=now, hours=48)
        self.assertEqual([c[0] for c in out], ["2"])

    def test_excludes_outside_the_window(self):
        now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            {"id": "far", "status": "1", "end_date": "2026-10-05 12:00:00"},  # +6 days
            {"id": "near", "status": "1", "end_date": "2026-09-30 12:00:00"},  # +24h
        ]
        out = ls.open_candidates_closing_soon(rows, now=now, hours=48)
        self.assertEqual([c[0] for c in out], ["near"])

    def test_excludes_already_past(self):
        # status "1" but end_date already behind now - shouldn't happen in
        # practice, but the window check must still exclude it defensively.
        now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
        rows = [{"id": "1", "status": "1", "end_date": "2026-09-28 12:00:00"}]
        out = ls.open_candidates_closing_soon(rows, now=now, hours=48)
        self.assertEqual(out, [])

    def test_boundary_inclusive(self):
        now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
        rows = [{"id": "1", "status": "1", "end_date": "2026-10-01 12:00:00"}]  # exactly +48h
        out = ls.open_candidates_closing_soon(rows, now=now, hours=48)
        self.assertEqual([c[0] for c in out], ["1"])

    def test_real_index_fixture_never_includes_a_closed_id(self):
        # musick_closed_index_p1.html: 43 status "3", 7 status "1" (see
        # test_price_history.py's ClosedIndexTests). The fixture's real
        # dates are fixed in the past relative to whenever this test
        # actually runs, so a wall-clock "now" makes the window's contents
        # untestable in a stable way - this only checks the one invariant
        # that holds regardless of wall-clock time: a status "3" (actually
        # closed) id must never come back as "closing soon", no matter how
        # wide the window is.
        rows = ph.extract_closed_index_rows(_read("musick_closed_index_p1.html"))
        closed_ids = {r["id"] for r in rows if r["status"] == "3"}
        for hours in (1, 48, 24 * 3650):
            out = ls.open_candidates_closing_soon(rows, hours=hours)
            self.assertEqual({c[0] for c in out} & closed_ids, set())

    def test_real_index_fixture_time_window_with_fixed_anchor(self):
        # Same 7 real status "1" rows, but with `now` fixed to just before
        # their own end_dates so the window logic runs against real data
        # instead of a wall-clock-dependent "now".
        rows = ph.extract_closed_index_rows(_read("musick_closed_index_p1.html"))
        open_rows = [r for r in rows if r["status"] == "1"]
        end_dts = [
            datetime.strptime(ph.iso_utc_from_index(r["end_date"]), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            for r in open_rows
        ]
        anchor = min(end_dts) - timedelta(hours=1)
        span_hours = (max(end_dts) - anchor).total_seconds() / 3600
        out = ls.open_candidates_closing_soon(rows, now=anchor, hours=span_hours)
        self.assertEqual({c[0] for c in out}, {r["id"] for r in open_rows})


@patch("live_seen.time.sleep", lambda *a, **kw: None)
class FetchCatalogLiveLotsTests(unittest.TestCase):
    def test_real_open_fixture(self):
        page = _read("musick_catalog_920_open.html")
        render = _fake_render({1: page}, default=page)
        notes = []
        rows, complete = ls.fetch_catalog_live_lots(920, notes, render=render)
        # Same repeat-page behavior as harvest_catalog(): page 2 repeats
        # page 1's 50 lots, 0 new, clean stop.
        self.assertEqual(len(rows), 50)
        self.assertTrue(complete)
        self.assertTrue(any(r["lot_id"] == 515221 for r in rows))

    def test_render_failure_is_incomplete(self):
        render = _fake_render({1: None})
        notes = []
        rows, complete = ls.fetch_catalog_live_lots(920, notes, render=render)
        self.assertEqual(rows, [])
        self.assertFalse(complete)

    def test_blocked_page_is_incomplete(self):
        blocked_page = "x" * 100  # under looks_blocked's 2000-byte threshold
        render = _fake_render({1: blocked_page})
        notes = []
        rows, complete = ls.fetch_catalog_live_lots(920, notes, render=render)
        self.assertEqual(rows, [])
        self.assertFalse(complete)

    def test_max_pages_cap_gives_incomplete(self):
        # A page that never repeats and never empties - same style as
        # test_price_history.py's cap test.
        def render(url):
            m = re.search(r"page=(\d+)", url)
            n = int(m.group(1))
            lot_id = 600000 + n
            chunk = (
                f'<li id="blkLotItemMain{lot_id}" class="item-block ">'
                f'<section data-lid="{lot_id}" data-aid="920">'
                f'<span class="lotTitle"><a class="yaaa" href="#">Synthetic {lot_id}</a></span>'
                f'<li id="item-status" class="item-status"></li>'
                f'</section></li>' + "x" * 3000
            )
            return chunk, []
        notes = []
        rows, complete = ls.fetch_catalog_live_lots(920, notes, render=render)
        self.assertFalse(complete)
        self.assertEqual(len(rows), ph.MAX_CATALOG_PAGES)


@patch("live_seen.time.sleep", lambda *a, **kw: None)
class RunIntegrationTests(unittest.TestCase):
    def test_writes_live_seen_for_catalogs_closing_soon(self):
        now = datetime.now(timezone.utc)
        index_rows = {
            "auctionRows": [
                {"id": "920", "status": "1", "end_date": _iso(now + timedelta(hours=10)).replace("T", " ").rstrip("Z")},
            ]
        }
        import json
        index_html = (
            '<script data-server="server-data-json">' + json.dumps(index_rows) + "</script>" + "x" * 3000
        )
        open_page = _read("musick_catalog_920_open.html")

        def render_index(url):
            return index_html, []

        def render(url):
            return open_page, []

        with tempfile.TemporaryDirectory() as d:
            live_seen_path = os.path.join(d, "_live_seen.jsonl")
            notes = []
            written = ls.run(
                notes, render_index=render_index, render=render,
                live_seen_path=live_seen_path, hours=48,
            )
            self.assertEqual(written, 50)
            latest = ph.load_live_seen(920, live_seen_path=live_seen_path)
            self.assertEqual(len(latest), 50)

    def test_no_catalogs_closing_soon_writes_nothing(self):
        import json
        index_rows = {"auctionRows": [{"id": "1", "status": "3", "end_date": "2020-01-01 00:00:00"}]}
        index_html = (
            '<script data-server="server-data-json">' + json.dumps(index_rows) + "</script>" + "x" * 3000
        )

        def render_index(url):
            return index_html, []

        notes = []
        with tempfile.TemporaryDirectory() as d:
            written = ls.run(
                notes, render_index=render_index,
                live_seen_path=os.path.join(d, "_live_seen.jsonl"), hours=48,
            )
        self.assertEqual(written, 0)

    def test_incomplete_catalog_fetch_is_not_recorded(self):
        import json
        now = datetime.now(timezone.utc)
        index_rows = {
            "auctionRows": [
                {"id": "920", "status": "1", "end_date": _iso(now + timedelta(hours=10)).replace("T", " ").rstrip("Z")},
            ]
        }
        index_html = (
            '<script data-server="server-data-json">' + json.dumps(index_rows) + "</script>" + "x" * 3000
        )

        def render_index(url):
            return index_html, []

        def render_fails(url):
            return None, []

        with tempfile.TemporaryDirectory() as d:
            live_seen_path = os.path.join(d, "_live_seen.jsonl")
            notes = []
            written = ls.run(
                notes, render_index=render_index, render=render_fails,
                live_seen_path=live_seen_path, hours=48,
            )
            self.assertEqual(written, 0)
            self.assertFalse(os.path.exists(live_seen_path))


if __name__ == "__main__":
    unittest.main()
