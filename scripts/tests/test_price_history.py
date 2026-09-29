#!/usr/bin/env python3
"""
test_price_history.py - offline, stdlib-only unittest coverage for
price_history.py. No network calls: everything here parses real saved
HTML fixtures (scripts/tests/fixtures/musick_*.html, copied verbatim from
live probe_url dispatches against bid.musickauction.com - see
docs/AUCTION-MONITORING.md's "Closed lots, verified against real markup"
and PRICE-DISCOVERY.md's Session B) or exercises the JSONL storage layer
against a temp directory.

Run with:
    python -m unittest discover scripts/tests
"""

import json
import os
import re
import sys
import tempfile
import unittest
from collections import Counter
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import price_history as ph  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def _fake_render(pages_by_number, default=None):
    """Build a fake render(url) -> (html, api_calls) that dispatches on the
    `page=N` query param, for injecting into harvest_catalog()/
    daily_harvest() without any network access. `default` is returned for
    any page number not in `pages_by_number` (None means "render failed")."""
    def render(url):
        m = re.search(r"page=(\d+)", url)
        n = int(m.group(1)) if m else 1
        html = pages_by_number.get(n, default)
        if html is None:
            return None, []
        return html, []
    return render


def _padded(html):
    """Pad a tiny stub page to a realistic size. Real Musick pages are
    25KB+, and musick_render.looks_blocked() treats anything under 2,000
    bytes as a probable block page - so a stub standing in for "a real page
    with no lots" must not be tiny."""
    return html + "<!-- " + "x" * 3000 + " -->"


def _synthetic_lot_html(lot_id):
    """A minimal, real-shaped closed-lot chunk (matches every regex
    price_history.py parses against) for a single sold lot with a unique
    id - used to force harvest_catalog() to keep finding "new" lots
    indefinitely, for exercising the MAX_CATALOG_PAGES hard cap without a
    3000-lot fixture."""
    return f'''<li id="blkLotItemMain{lot_id}" class="item-block ">
 <section id="ali{lot_id}" class="item-block-wrapper" data-lid="{lot_id}" data-aid="914" data-alid="{lot_id}">
 <div class="bdttle"><i> </i><h2> </h2></div>
 <figure><a href="#"><img src="x"></a></figure>
 <div class="myTitle"><span class="lotNumber"><a href="#" class="auc-lot-link" id="lot{lot_id}"><span class="lot_no">Lot #<span class="no">{lot_id}</span></span></a> : </span><span class="lotTitle"><a class="yaaa" href="#">Synthetic Lot {lot_id}</a></span></div>
 <div class="bd-info"><ul class="price-info"><li class="item-win-bid"><span class="title">Winning Bid</span><span class="value"><span class="scur914">$</span><span class="exratetip" data-lid="{lot_id}">100</span></span></li><li id="item-status" class="item-status"><span class="title">Status</span><span class="value"><span class="ended sold">Sold</span></span></li><li class="item-bidhistory"><span class="title">Bidding history</span><span class="value"><span class="bid-history"><a href="#">Bidding history(1 bids)</a></span></span></li><li class="clear"></li></ul></div>
 </section>
</li>
'''


class ClosedIndexTests(unittest.TestCase):
    """/auctions/?alf1=4 page 1 - two data-server="server-data-json" blobs,
    auctionRows nested inside one of them (see extract_closed_index_rows'
    docstring). 50 rows: 43 status "3" (closed), 7 status "1" (not, despite
    the filter - CONFIRMED real, not a parser bug)."""

    def setUp(self):
        self.rows = ph.extract_closed_index_rows(_read("musick_closed_index_p1.html"))

    def test_row_count(self):
        self.assertEqual(len(self.rows), 50)

    def test_status_split(self):
        counts = Counter(r["status"] for r in self.rows)
        self.assertEqual(counts["3"], 43)
        self.assertEqual(counts["1"], 7)

    def test_catalog_914_utc_conversion(self):
        row = next(r for r in self.rows if r["id"] == "914")
        self.assertEqual(row["end_date"], "2026-09-24 03:22:00")
        # Verified: 09/23/2026 9:22 PM MDT == this timestamp read as UTC,
        # NOT shifted by timezone_location ("America/Denver").
        self.assertEqual(ph.iso_utc_from_index(row["end_date"]), "2026-09-24T03:22:00Z")

    def test_closed_candidates_excludes_not_yet_closed(self):
        import datetime as dt
        now = dt.datetime(2026, 9, 28, tzinfo=dt.timezone.utc)
        candidates = ph._closed_candidates(self.rows, now=now)
        ids = {c[0] for c in candidates}
        self.assertIn("914", ids)
        # None of the 7 status "1" rows should ever appear as a candidate.
        status1_ids = {r["id"] for r in self.rows if r["status"] == "1"}
        self.assertFalse(ids & status1_ids)


class ClosedLotParseTests(unittest.TestCase):
    """Catalog 914 page 1 (50 lots, all real, all `ended sold`)."""

    def setUp(self):
        self.rows = ph.parse_closed_lots(_read("musick_catalog_914_p1.html"), 914)

    def test_row_count(self):
        self.assertEqual(len(self.rows), 50)

    def test_all_close_kind(self):
        self.assertTrue(all(r["price_kind"] == "close" for r in self.rows))
        self.assertTrue(all("status_raw" not in r for r in self.rows))

    def test_f550_lot_all_fields(self):
        row = next(r for r in self.rows if r["lot_id"] == 511357)
        self.assertEqual(row["catalog_id"], 914)
        self.assertEqual(row["lot_no"], "800")
        self.assertIsInstance(row["lot_no"], str)
        self.assertEqual(row["title"], "2017 FORD F-550 - BLUETOOTH!")
        self.assertEqual(row["price_kind"], "close")
        self.assertEqual(row["price"], 4000)
        self.assertEqual(row["num_bids"], 35)

    def test_build_row_schema_and_key_order(self):
        parsed = next(r for r in self.rows if r["lot_id"] == 511357)
        row = ph.build_row(parsed, "2026-09-24T03:22:00Z", "2026-09-28T12:00:00Z")
        self.assertEqual(
            list(row.keys()),
            [
                "platform", "catalog_id", "lot_id", "lot_no", "title",
                "category", "price_kind", "price", "num_bids",
                "catalog_closed_at", "observed_at",
            ],
        )
        self.assertEqual(row["platform"], "musick")
        self.assertEqual(row["catalog_closed_at"], "2026-09-24T03:22:00Z")
        # Compact separators, real JSON round-trip.
        encoded = json.dumps(row, separators=(",", ":"))
        self.assertNotIn(", ", encoded)
        self.assertNotIn(": ", encoded.replace('"observed_at"', ""))
        self.assertEqual(json.loads(encoded), row)


class ClosedLotTailPageTests(unittest.TestCase):
    """catalog/id/914?items=100&page=5 - the 70-lot tail of a 470-lot
    catalog, all low-value, all real, all `ended sold` (no unsold lot was
    ever observed in real markup - see docs/AUCTION-MONITORING.md)."""

    def test_row_count(self):
        rows = ph.parse_closed_lots(_read("musick_catalog_914_p5_items100.html"), 914)
        self.assertEqual(len(rows), 70)
        self.assertTrue(all(r["price_kind"] == "close" for r in rows))
        self.assertTrue(all(r["catalog_id"] == 914 for r in rows))


class OpenCatalogNegativeTests(unittest.TestCase):
    """catalog 920, a real OPEN catalog: live lots must never produce a
    close row (or any row - a still-live lot has nothing concluded yet)."""

    def test_zero_rows(self):
        rows = ph.parse_closed_lots(_read("musick_catalog_920_open.html"), 920)
        self.assertEqual(rows, [])


class LiveLotParsingTests(unittest.TestCase):
    """parse_live_lots() (Session B2) against the same real OPEN catalog
    fixture used above - the inverse of parse_closed_lots()."""

    def setUp(self):
        self.rows = ph.parse_live_lots(_read("musick_catalog_920_open.html"), 920)

    def test_row_count_matches_closed_lots_zero_count(self):
        # 50 live lots on this page, 0 concluded (ClosedLotTailPageTests'
        # sibling assertion) - together they should account for every lot.
        self.assertEqual(len(self.rows), 50)

    def test_real_lot_fields(self):
        row = next(r for r in self.rows if r["lot_id"] == 515221)
        self.assertEqual(row["catalog_id"], 920)
        self.assertEqual(row["lot_no"], "300")
        self.assertEqual(row["title"], "2017 FORD F-150 - 4x4!!")
        self.assertEqual(row["last_bid"], 8800)
        self.assertEqual(row["num_bids"], 47)

    def test_second_real_lot(self):
        row = next(r for r in self.rows if r["lot_id"] == 515222)
        self.assertEqual(row["lot_no"], "301")
        self.assertEqual(row["last_bid"], 4200)
        self.assertEqual(row["num_bids"], 44)

    def test_never_yields_a_lot_id_that_parse_closed_lots_also_returns(self):
        closed_ids = {r["lot_id"] for r in ph.parse_closed_lots(_read("musick_catalog_920_open.html"), 920)}
        live_ids = {r["lot_id"] for r in self.rows}
        self.assertEqual(closed_ids & live_ids, set())

    def test_closed_catalog_page_yields_zero_live_lots(self):
        # The inverse of ClosedLotTailPageTests - every lot on a genuinely
        # closed page is `ended`, so parse_live_lots must find none.
        rows = ph.parse_live_lots(_read("musick_catalog_914_p1.html"), 914)
        self.assertEqual(rows, [])


class LiveSeenStorageTests(unittest.TestCase):
    """append_live_seen()/load_live_seen() round-trip and the
    latest-observation-wins logic find_vanished_lots() depends on."""

    def test_round_trip(self):
        rows = [
            {"catalog_id": 920, "lot_id": 1, "lot_no": "1", "title": "A", "last_bid": 100, "num_bids": 2},
            {"catalog_id": 920, "lot_id": 2, "lot_no": "2", "title": "B", "last_bid": None, "num_bids": None},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "_live_seen.jsonl")
            written = ph.append_live_seen(rows, "2026-09-28T12:00:00Z", live_seen_path=path)
            self.assertEqual(written, 2)
            latest = ph.load_live_seen(920, live_seen_path=path)
            self.assertEqual(len(latest), 2)
            self.assertEqual(latest[1]["last_bid"], 100)
            self.assertEqual(latest[1]["observed_at"], "2026-09-28T12:00:00Z")

    def test_latest_observation_wins_on_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "_live_seen.jsonl")
            ph.append_live_seen(
                [{"catalog_id": 920, "lot_id": 1, "lot_no": "1", "title": "A", "last_bid": 100, "num_bids": 2}],
                "2026-09-27T12:00:00Z", live_seen_path=path,
            )
            ph.append_live_seen(
                [{"catalog_id": 920, "lot_id": 1, "lot_no": "1", "title": "A", "last_bid": 250, "num_bids": 5}],
                "2026-09-28T12:00:00Z", live_seen_path=path,
            )
            latest = ph.load_live_seen(920, live_seen_path=path)
            self.assertEqual(latest[1]["last_bid"], 250)
            self.assertEqual(latest[1]["num_bids"], 5)

    def test_missing_file_returns_empty(self):
        self.assertEqual(ph.load_live_seen(920, live_seen_path="/nonexistent/_live_seen.jsonl"), {})

    def test_wrong_catalog_id_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "_live_seen.jsonl")
            ph.append_live_seen(
                [{"catalog_id": 921, "lot_id": 1, "lot_no": "1", "title": "A", "last_bid": 100, "num_bids": 2}],
                "2026-09-28T12:00:00Z", live_seen_path=path,
            )
            self.assertEqual(ph.load_live_seen(920, live_seen_path=path), {})


class VanishedLotTests(unittest.TestCase):
    """find_vanished_lots()/build_vanished_row(): a lot seen live but
    absent from its closed catalog's parsed lot_ids."""

    def test_lot_absent_from_closed_set_is_vanished(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "_live_seen.jsonl")
            ph.append_live_seen(
                [
                    {"catalog_id": 920, "lot_id": 1, "lot_no": "904", "title": "MISSING TRUCK",
                     "last_bid": 500, "num_bids": 3},
                    {"catalog_id": 920, "lot_id": 2, "lot_no": "905", "title": "SOLD TRUCK",
                     "last_bid": 4000, "num_bids": 27},
                ],
                "2026-09-28T12:00:00Z", live_seen_path=path,
            )
            closed_lot_ids = {2}  # only lot 2 shows up in the closed catalog
            vanished = ph.find_vanished_lots(
                920, closed_lot_ids, "2026-09-28T23:07:00Z", "2026-09-29T13:00:00Z",
                live_seen_path=path,
            )
        self.assertEqual(len(vanished), 1)
        row = vanished[0]
        self.assertEqual(row["lot_id"], 1)
        self.assertEqual(row["platform"], "musick")
        self.assertEqual(row["price_kind"], "vanished")
        self.assertIsNone(row["price"])
        self.assertEqual(row["last_seen_bid"], 500)
        self.assertEqual(row["last_seen_num_bids"], 3)
        self.assertEqual(row["last_seen_at"], "2026-09-28T12:00:00Z")
        self.assertEqual(row["catalog_closed_at"], "2026-09-28T23:07:00Z")
        self.assertEqual(row["observed_at"], "2026-09-29T13:00:00Z")

    def test_no_live_seen_file_means_no_vanished_lots(self):
        vanished = ph.find_vanished_lots(
            920, {1, 2, 3}, "2026-09-28T23:07:00Z", "2026-09-29T13:00:00Z",
            live_seen_path="/nonexistent/_live_seen.jsonl",
        )
        self.assertEqual(vanished, [])

    def test_all_seen_lots_closed_means_nothing_vanished(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "_live_seen.jsonl")
            ph.append_live_seen(
                [{"catalog_id": 920, "lot_id": 1, "lot_no": "1", "title": "A", "last_bid": 100, "num_bids": 2}],
                "2026-09-28T12:00:00Z", live_seen_path=path,
            )
            vanished = ph.find_vanished_lots(
                920, {1}, "2026-09-28T23:07:00Z", "2026-09-29T13:00:00Z", live_seen_path=path,
            )
        self.assertEqual(vanished, [])


class UnknownStatusTests(unittest.TestCase):
    """A synthesized fixture (real catalog 914 markup, lot 511358's status
    span edited from `ended sold`/"Sold" to `ended unsold`/"Unsold" - no
    real unsold lot has been observed yet, see docs/AUCTION-MONITORING.md)
    - the price_kind honesty rule in action."""

    def setUp(self):
        self.rows = ph.parse_closed_lots(_read("musick_catalog_914_unknown_status.html"), 914)

    def test_other_lots_still_close(self):
        kinds = {r["lot_id"]: r["price_kind"] for r in self.rows}
        self.assertEqual(kinds[511357], "close")  # F-550, untouched
        self.assertEqual(kinds[511358], "unknown")

    def test_unsold_lot_is_unknown_with_null_price(self):
        row = next(r for r in self.rows if r["lot_id"] == 511358)
        self.assertEqual(row["price_kind"], "unknown")
        self.assertIsNone(row["price"])
        self.assertIn("ended unsold", row["status_raw"])
        self.assertIn("Unsold", row["status_raw"])

    def test_build_row_includes_status_raw_only_for_unknown(self):
        parsed = next(r for r in self.rows if r["lot_id"] == 511358)
        row = ph.build_row(parsed, "2026-09-24T03:22:00Z", "2026-09-28T12:00:00Z")
        self.assertIn("status_raw", row)
        self.assertIsNone(row["price"])
        close_parsed = next(r for r in self.rows if r["lot_id"] == 511357)
        close_row = ph.build_row(close_parsed, "2026-09-24T03:22:00Z", "2026-09-28T12:00:00Z")
        self.assertNotIn("status_raw", close_row)


class DedupeIdempotencyTests(unittest.TestCase):
    """Writing the same rows twice into a fresh temp dir must append zero
    rows on the second call - the append-only contract's core guarantee."""

    def test_second_write_appends_zero(self):
        parsed = ph.parse_closed_lots(_read("musick_catalog_914_p1.html"), 914)
        rows = [
            ph.build_row(p, "2026-09-24T03:22:00Z", "2026-09-28T12:00:00Z")
            for p in parsed
        ]
        with tempfile.TemporaryDirectory() as d:
            first = ph.append_rows(rows, d)
            second = ph.append_rows(rows, d)
            self.assertEqual(first, 50)
            self.assertEqual(second, 0)

            # File landed in the right month, one JSON object per line.
            path = os.path.join(d, "2026-09.jsonl")
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf-8") as f:
                lines = [line for line in f if line.strip()]
            self.assertEqual(len(lines), 50)
            for line in lines:
                json.loads(line)  # must parse as standalone JSON

    def test_dedupe_key_is_platform_and_lot_id(self):
        keys_before = set()
        with tempfile.TemporaryDirectory() as d:
            parsed = ph.parse_closed_lots(_read("musick_catalog_914_p1.html"), 914)[:5]
            rows = [
                ph.build_row(p, "2026-09-24T03:22:00Z", "2026-09-28T12:00:00Z")
                for p in parsed
            ]
            ph.append_rows(rows, d)
            keys_before = ph.load_existing_keys(d)
            self.assertEqual(len(keys_before), 5)
            self.assertIn(("musick", 511357), keys_before)


class SizeEstimateTests(unittest.TestCase):
    """--backfill's size-estimate math, against synthetic index rows (real
    shape, from the 914/920 auctionRows samples above)."""

    def test_estimate_calculation(self):
        rows = [
            {"id": "914", "status": "3", "total_lots": "470"},
            {"id": "920", "status": "3", "total_lots": "150"},
        ]
        bytes_per_row = 260
        est = ph.estimate_backfill(rows, bytes_per_row=bytes_per_row)
        self.assertEqual(est["catalogs"], 2)
        self.assertEqual(est["total_lots"], 620)
        # ceil(470/100) + ceil(150/100) = 5 + 2 = 7
        self.assertEqual(est["renders"], 7)
        expected_mb = round((620 * 260) / (1024 * 1024), 1)
        self.assertEqual(est["est_mb"], expected_mb)
        self.assertGreater(est["est_minutes"], 0)

    def test_measure_row_bytes_matches_a_real_encoded_row(self):
        n = ph.measure_row_bytes()
        # Sanity: a real close row for the F-550 lot should land in the
        # same ballpark (within a few dozen bytes either way - titles vary).
        self.assertGreater(n, 100)
        self.assertLess(n, 500)


@patch("price_history.time.sleep", lambda *a, **kw: None)  # no real waiting in tests
class RepeatPageAndIncompleteHarvestTests(unittest.TestCase):
    """harvest_catalog()'s two anti-infinite-loop guards (repeat-page
    detection and MAX_CATALOG_PAGES) and the "don't mark harvested unless
    complete" rule that prevents silent data loss on a mid-catalog render
    failure."""

    def test_repeated_page_terminates_after_page_2_with_correct_rows(self):
        # Same real 50-lot page served no matter what page number is asked
        # for - the "site clamps to the last page" scenario. Repeat
        # detection must stop this after page 2 (0 new lot ids), not loop.
        page1 = _read("musick_catalog_914_p1.html")
        render = _fake_render({1: page1, 2: page1}, default=page1)
        notes = []
        with tempfile.TemporaryDirectory() as d:
            rows, appended, complete = ph.harvest_catalog(
                914, "2026-09-24T03:22:00Z", notes, render=render, price_history_dir=d
            )
        self.assertEqual(len(rows), 50)
        self.assertEqual(appended, 50)
        self.assertTrue(complete)  # a clean end-of-data signal, not an error
        self.assertTrue(any("repeated" in n for n in notes))

    def test_render_failure_mid_catalog_gives_incomplete_and_unmarked_state(self):
        page1 = _read("musick_catalog_914_p1.html")
        # Page 2 fails to render entirely.
        render_fails = _fake_render({1: page1, 2: None})
        notes = []
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "_harvested.json")
            rows, appended, complete = ph.harvest_catalog(
                914, "2026-09-24T03:22:00Z", notes, render=render_fails, price_history_dir=d
            )
            self.assertEqual(appended, 50)  # page 1's rows are still safe to keep
            self.assertFalse(complete)

            # Caller contract: only mark_harvested() when complete.
            state = ph.load_state(state_path)
            if complete:
                ph.mark_harvested(state, 914, "2026-09-24T03:22:00Z", len(rows), state_path)
            self.assertNotIn("914", ph.load_state(state_path).get("catalogs", {}))

            # A second run with a working render succeeds fully: page 1's
            # rows are already on disk (0 new there), page 2 (the real
            # 70-lot tail) is new, page 3 is a clean empty stop.
            page5 = _read("musick_catalog_914_p5_items100.html")
            render_ok = _fake_render({1: page1, 2: page5, 3: _padded("<html></html>")})
            rows2, appended2, complete2 = ph.harvest_catalog(
                914, "2026-09-24T03:22:00Z", notes, render=render_ok, price_history_dir=d
            )
            self.assertTrue(complete2)
            self.assertEqual(appended2, 70)  # only the missing lots, dedupe did its job
            state2 = ph.load_state(state_path)
            ph.mark_harvested(state2, 914, "2026-09-24T03:22:00Z", len(rows2), state_path)
            self.assertIn("914", ph.load_state(state_path).get("catalogs", {}))

    def test_max_catalog_pages_cap_gives_incomplete(self):
        # Every page returns exactly one brand-new lot - never empty, never
        # a repeat - so only the hard cap can end this loop.
        pages = {n: _padded(_synthetic_lot_html(600000 + n)) for n in range(1, ph.MAX_CATALOG_PAGES + 5)}
        render = _fake_render(pages)
        notes = []
        with tempfile.TemporaryDirectory() as d:
            rows, appended, complete = ph.harvest_catalog(
                999, "2026-09-24T03:22:00Z", notes, render=render, price_history_dir=d
            )
        self.assertFalse(complete)
        self.assertEqual(len(rows), ph.MAX_CATALOG_PAGES)
        self.assertTrue(any("MAX_CATALOG_PAGES" in n for n in notes))

    def test_zero_lots_parsed_is_incomplete_not_a_clean_stop(self):
        # Markup drift: the page renders fine but nothing parses. Must not
        # be marked harvested with 0 rows and never retried.
        render = _fake_render({1: _padded("<html><body>redesigned site</body></html>")})
        notes = []
        with tempfile.TemporaryDirectory() as d:
            rows, appended, complete = ph.harvest_catalog(
                914, "2026-09-24T03:22:00Z", notes, render=render, price_history_dir=d
            )
        self.assertEqual((len(rows), appended), (0, 0))
        self.assertFalse(complete)
        self.assertTrue(any("markup change" in n for n in notes))


@patch("price_history.time.sleep", lambda *a, **kw: None)  # no real waiting in tests
class IndexRepeatPageTests(unittest.TestCase):
    """_walk_all_index_pages()'s repeat-page detection - same risk as
    harvest_catalog(), bounded at 200 renders but must not inflate the
    backfill size estimate with duplicate rows."""

    def test_repeating_index_page_stops_and_does_not_double_count(self):
        index_page = _read("musick_closed_index_p1.html")
        render = _fake_render({1: index_page, 2: index_page}, default=index_page)
        notes = []
        rows = ph._walk_all_index_pages(render, notes, max_pages=10)
        self.assertEqual(len(rows), 50)  # not 100 - the repeat must not double-count
        ids = [r["id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any("repeated" in n for n in notes))


@patch("price_history.time.sleep", lambda *a, **kw: None)
class HarvestCatalogVanishedLotIntegrationTests(unittest.TestCase):
    """harvest_catalog() actually calls find_vanished_lots() and folds the
    result into its returned/appended rows - not just the standalone unit
    tested above."""

    def test_vanished_lot_appears_in_harvested_rows(self):
        page1 = _read("musick_catalog_914_p1.html")
        render = _fake_render({1: page1}, default=page1)
        notes = []
        with tempfile.TemporaryDirectory() as d:
            live_seen_path = os.path.join(d, "_live_seen.jsonl")
            # A lot NOT present anywhere in the real 914 fixture - stands
            # in for "seen live, then gone" (docs/AUCTION-MONITORING.md's
            # real missing-904 case, same shape).
            ph.append_live_seen(
                [{"catalog_id": 914, "lot_id": 999999, "lot_no": "904",
                  "title": "MISSING TRUCK", "last_bid": 500, "num_bids": 3}],
                "2026-09-23T12:00:00Z", live_seen_path=live_seen_path,
            )
            rows, appended, complete = ph.harvest_catalog(
                914, "2026-09-24T03:22:00Z", notes, render=render,
                price_history_dir=d, live_seen_path=live_seen_path,
            )
        self.assertTrue(complete)
        vanished = [r for r in rows if r["price_kind"] == "vanished"]
        self.assertEqual(len(vanished), 1)
        self.assertEqual(vanished[0]["lot_id"], 999999)
        self.assertEqual(vanished[0]["last_seen_bid"], 500)
        self.assertEqual(appended, 51)  # 50 real closes + 1 vanished
        self.assertTrue(any("1 vanished lot(s) recovered" in n for n in notes))

    def test_incomplete_harvest_never_runs_vanished_detection(self):
        # A render failure mid-catalog must not treat every not-yet-fetched
        # lot as vanished - complete=False skips the comparison entirely.
        page1 = _read("musick_catalog_914_p1.html")
        render_fails = _fake_render({1: page1, 2: None})
        notes = []
        with tempfile.TemporaryDirectory() as d:
            live_seen_path = os.path.join(d, "_live_seen.jsonl")
            ph.append_live_seen(
                [{"catalog_id": 914, "lot_id": 999999, "lot_no": "904",
                  "title": "MISSING TRUCK", "last_bid": 500, "num_bids": 3}],
                "2026-09-23T12:00:00Z", live_seen_path=live_seen_path,
            )
            rows, appended, complete = ph.harvest_catalog(
                914, "2026-09-24T03:22:00Z", notes, render=render_fails,
                price_history_dir=d, live_seen_path=live_seen_path,
            )
        self.assertFalse(complete)
        self.assertEqual([r for r in rows if r["price_kind"] == "vanished"], [])


class ValuationsJoinTests(unittest.TestCase):
    """build_row()'s my_max/we_bid join against Session P's
    data/my_valuations.yaml (scripts/value_it.py). Real HTML fixture rows,
    a synthetic valuations dict passed explicitly so this never touches
    the real data/my_valuations.yaml on disk."""

    def setUp(self):
        self.parsed = ph.parse_closed_lots(_read("musick_catalog_914_p1.html"), 914)

    def test_no_valuation_omits_fields(self):
        parsed = next(r for r in self.parsed if r["lot_id"] == 511357)
        row = ph.build_row(parsed, "2026-09-24T03:22:00Z", "2026-09-28T12:00:00Z", valuations={})
        self.assertNotIn("my_max", row)
        self.assertNotIn("we_bid", row)

    def test_matching_valuation_is_joined(self):
        parsed = next(r for r in self.parsed if r["lot_id"] == 511357)
        valuations = {("musick", 511357): {"my_max": 3500.0, "we_bid": True}}
        row = ph.build_row(parsed, "2026-09-24T03:22:00Z", "2026-09-28T12:00:00Z", valuations=valuations)
        self.assertEqual(row["my_max"], 3500.0)
        self.assertIs(row["we_bid"], True)
        # Lands after the always-present fields, same "append, don't
        # reorder" convention as watchlist_matches/status_raw.
        self.assertEqual(list(row.keys())[-2:], ["my_max", "we_bid"])

    def test_platform_mismatch_does_not_join(self):
        parsed = next(r for r in self.parsed if r["lot_id"] == 511357)
        valuations = {("ebay", 511357): {"my_max": 3500.0, "we_bid": True}}
        row = ph.build_row(parsed, "2026-09-24T03:22:00Z", "2026-09-28T12:00:00Z", valuations=valuations)
        self.assertNotIn("my_max", row)

    def test_load_valuations_reads_real_schema(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "my_valuations.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "valuations:\n"
                    "  - platform: musick\n"
                    "    lot_id: 511357\n"
                    "    my_max: 3500.0\n"
                    "    we_bid: true\n"
                    "  - platform: musick\n"
                    "    lot_id: 999999\n"
                    "    my_max: 40.0\n"
                    "    we_bid: false\n"
                )
            loaded = ph.load_valuations(path)
        self.assertEqual(loaded[("musick", 511357)], {"my_max": 3500.0, "we_bid": True})
        self.assertEqual(loaded[("musick", 999999)], {"my_max": 40.0, "we_bid": False})

    def test_load_valuations_missing_file_returns_empty(self):
        self.assertEqual(ph.load_valuations("/nonexistent/path/my_valuations.yaml"), {})


if __name__ == "__main__":
    unittest.main()
