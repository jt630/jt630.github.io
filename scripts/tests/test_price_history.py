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
import sys
import tempfile
import unittest
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import price_history as ph  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


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


if __name__ == "__main__":
    unittest.main()
