#!/usr/bin/env python3
"""
test_value_it.py - offline, stdlib-only unittest coverage for value_it.py
(Session P, THESIS.md H7). No network calls. Every test points LOTS_PATH/
VALUATIONS_PATH at a temp directory via monkeypatching, so nothing here
ever touches the real data/auction_lots.yaml or data/my_valuations.yaml.

Run with:
    python -m unittest discover scripts/tests
"""

import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import value_it as vi  # noqa: E402

LIVE_URL = (
    "https://bid.musickauction.com/lot-details/index/catalog/921/lot/515998/"
    "2004-FORD-EXPLORER-4X4?url=%2Fauctions%2Fcatalog%2Fid%2F921"
)
CLOSED_URL = (
    "https://bid.musickauction.com/lot-details/index/catalog/921/lot/515999/"
    "1999-JUNK-CAR?url=%2Fauctions%2Fcatalog%2Fid%2F921"
)
UNKNOWN_URL = (
    "https://bid.musickauction.com/lot-details/index/catalog/921/lot/1/"
    "not-in-snapshot?url=%2Fauctions%2Fcatalog%2Fid%2F921"
)


def _future_iso(hours=2):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _past_iso(hours=2):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


class TestExtraction(unittest.TestCase):
    def test_extract_lot_id(self):
        self.assertEqual(vi.extract_lot_id(LIVE_URL), 515998)

    def test_extract_lot_id_no_match(self):
        self.assertIsNone(vi.extract_lot_id("https://example.com/nope"))

    def test_platform_from_url(self):
        self.assertEqual(vi.platform_from_url(LIVE_URL), "musick")
        self.assertIsNone(vi.platform_from_url("https://ebay.com/itm/123"))


class TempDataMixin:
    """Points LOTS_PATH/VALUATIONS_PATH at a temp dir with a synthetic
    live snapshot (one still-live lot, one already-closed lot)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        lots_path = os.path.join(self.tmp.name, "auction_lots.yaml")
        valuations_path = os.path.join(self.tmp.name, "my_valuations.yaml")
        with io.open(lots_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({
                "generated": "2026-09-29T12:00:00Z",
                "lots": [
                    {
                        "platform": "musick",
                        "title": "Lot #526: 2004 FORD EXPLORER - 4X4!",
                        "url": LIVE_URL,
                        "auction_ends_at": _future_iso(),
                    },
                    {
                        "platform": "musick",
                        "title": "1999 JUNK CAR",
                        "url": CLOSED_URL,
                        "auction_ends_at": _past_iso(),
                    },
                ],
            }, f)
        self._patches = [
            patch.object(vi, "LOTS_PATH", lots_path),
            patch.object(vi, "VALUATIONS_PATH", valuations_path),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)
        self.valuations_path = valuations_path


class TestFindLiveLot(TempDataMixin, unittest.TestCase):
    def test_finds_live_lot(self):
        lot = vi.find_live_lot(515998, "musick")
        self.assertIsNotNone(lot)
        self.assertEqual(lot["title"], "Lot #526: 2004 FORD EXPLORER - 4X4!")

    def test_missing_lot_returns_none(self):
        self.assertIsNone(vi.find_live_lot(1, "musick"))

    def test_wrong_platform_returns_none(self):
        self.assertIsNone(vi.find_live_lot(515998, "ebay"))


class TestRecord(TempDataMixin, unittest.TestCase):
    def test_records_a_new_valuation(self):
        vi.record(LIVE_URL, 850.0, "runs, needs tires", "owner")
        entries = vi._load_valuations()
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["platform"], "musick")
        self.assertEqual(e["lot_id"], 515998)
        self.assertEqual(e["my_max"], 850.0)
        self.assertEqual(e["why"], "runs, needs tires")
        self.assertEqual(e["who"], "owner")
        self.assertEqual(e["we_bid"], False)
        self.assertIn("recorded_at", e)

    def test_refuses_duplicate(self):
        vi.record(LIVE_URL, 850.0, "first", "owner")
        with self.assertRaises(SystemExit):
            vi.record(LIVE_URL, 900.0, "second", "owner")
        entries = vi._load_valuations()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["my_max"], 850.0)  # untouched

    def test_refuses_already_closed_lot(self):
        with self.assertRaises(SystemExit):
            vi.record(CLOSED_URL, 100.0, "too late", "owner")
        self.assertEqual(vi._load_valuations(), [])

    def test_refuses_lot_not_in_live_snapshot(self):
        with self.assertRaises(SystemExit):
            vi.record(UNKNOWN_URL, 100.0, "unknown lot", "owner")
        self.assertEqual(vi._load_valuations(), [])


class TestMarkBid(TempDataMixin, unittest.TestCase):
    def test_marks_existing_valuation(self):
        vi.record(LIVE_URL, 850.0, "runs, needs tires", "owner")
        vi.mark_bid(LIVE_URL)
        entries = vi._load_valuations()
        self.assertEqual(entries[0]["we_bid"], True)

    def test_refuses_when_no_valuation_exists(self):
        with self.assertRaises(SystemExit):
            vi.mark_bid(LIVE_URL)

    def test_refuses_on_closed_lot(self):
        with self.assertRaises(SystemExit):
            vi.mark_bid(CLOSED_URL)


if __name__ == "__main__":
    unittest.main()
