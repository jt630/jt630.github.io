#!/usr/bin/env python3
"""
value_it.py - Session P (PRICE-DISCOVERY.md), THESIS.md H7: record a
personal valuation for a lot BEFORE it closes.

H7 needs a "worth to me" figure recorded before the close, so it can be
compared against the market price after. The whole point is the timing:
a valuation recorded after the price is known is contaminated and tells
you nothing. So this script is append-only and refuses two things:
recording (or marking a bid on) a lot that's already closed, and
overwriting an existing valuation for a lot that already has one -
mirrors THESIS.md's own rule that predictions are never edited after data
arrives, only amended in the notebook with a date and a reason.

Two modes:
    python scripts/value_it.py LOT_URL MAX "why it's worth that" [--who owner|grandpa]
        Records a new valuation.

    python scripts/value_it.py --mark-bid LOT_URL
        Marks an existing valuation's we_bid: true, for THESIS's observer-
        effect measure (did recording a number change whether we bid?).
        Same before-close guard applies.

Matches the lot against the live data/auction_lots.yaml snapshot (by
lot_id parsed from the URL) to pull its title and auction_ends_at, and to
confirm it hasn't closed yet. If the lot isn't in the current live
snapshot at all - already sold, or never fetched - recording is refused;
there's no way to confirm the before-close timing without it.
"""

import argparse
import io
import os
import re
import sys
from datetime import datetime, timezone

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "..", "data")
LOTS_PATH = os.path.join(DATA_DIR, "auction_lots.yaml")
VALUATIONS_PATH = os.path.join(DATA_DIR, "my_valuations.yaml")

_LOT_ID_RE = re.compile(r"/lot/(\d+)/")

WHO_CHOICES = ["owner", "grandpa"]


def extract_lot_id(url):
    m = _LOT_ID_RE.search(url or "")
    return int(m.group(1)) if m else None


def platform_from_url(url):
    if "musickauction.com" in (url or ""):
        return "musick"
    return None


def _load_yaml(path):
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_live_lot(lot_id, platform):
    """Return the matching lot dict from the live snapshot, or None."""
    lots_doc = _load_yaml(LOTS_PATH)
    if not lots_doc:
        return None
    for lot in lots_doc.get("lots", []):
        if lot.get("platform") != platform:
            continue
        if extract_lot_id(lot.get("url")) == lot_id:
            return lot
    return None


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _load_valuations():
    doc = _load_yaml(VALUATIONS_PATH) or {}
    return doc.get("valuations") or []


def _save_valuations(entries):
    os.makedirs(DATA_DIR, exist_ok=True)
    with io.open(VALUATIONS_PATH, "w", encoding="utf-8") as f:
        f.write(
            "# Session P (PRICE-DISCOVERY.md), THESIS.md H7: a personal "
            "valuation\n# recorded BEFORE a lot closes, to compare against "
            "the market price after.\n#\n# Written by scripts/value_it.py "
            "- don't hand-edit an existing entry's\n# my_max or why after "
            "the fact; that's exactly the contamination H7 exists\n# to "
            "prevent. Add a dated note instead if a valuation needs a "
            "correction.\n#\n# platform + lot_id is the join key "
            "scripts/price_history.py uses to\n# attach my_max (and "
            "we_bid) onto a lot's eventual close row.\n\n"
        )
        yaml.safe_dump({"valuations": entries}, f, sort_keys=False, allow_unicode=True)


def _find_entry(entries, platform, lot_id):
    for e in entries:
        if e.get("platform") == platform and e.get("lot_id") == lot_id:
            return e
    return None


def _guard_not_closed(lot, lot_id):
    """Refuse if the live lot is missing or already past its close time.
    Returns an error string, or None if it's safe to proceed.

    Two layers, of uneven strength: being present in the live snapshot at
    all is the real signal (a closed lot vanishes from the next day's
    fetch - see PRICE-DISCOVERY.md Session B2 on survivorship), which
    covers every lot. The auction_ends_at comparison below is a sharper
    check but only exists for vehicle lots - most categories (coins,
    jewelry, tools) don't carry that field, so for them this function can
    only fall back on "still in the snapshot". Confirmed 2026-09-29: a
    real coin lot has no auction_ends_at at all. Also worth knowing: while
    the WAF block holds, the live snapshot itself can be stale (see the
    handoff block), so "in the snapshot" is only as fresh as the last
    successful run, not real-time.
    """
    if lot is None:
        return (
            f"Lot {lot_id} isn't in the current live snapshot "
            f"({LOTS_PATH}) - either it's already closed, or this URL "
            "doesn't match a lot Auction Watch has fetched. Can't confirm "
            "before-close timing without it, so refusing."
        )
    ends_at = _parse_iso(lot.get("auction_ends_at"))
    if ends_at and datetime.now(timezone.utc) >= ends_at:
        return (
            f"'{lot.get('title')}' ended at {lot.get('auction_ends_at')}, "
            "which is in the past. Recording now would contaminate H7 - refusing."
        )
    return None


def record(url, my_max, why, who):
    lot_id = extract_lot_id(url)
    platform = platform_from_url(url)
    if lot_id is None or platform is None:
        sys.exit(f"Couldn't parse a lot_id/platform out of: {url}")

    lot = find_live_lot(lot_id, platform)
    err = _guard_not_closed(lot, lot_id)
    if err:
        sys.exit(err)

    entries = _load_valuations()
    if _find_entry(entries, platform, lot_id):
        sys.exit(
            f"Lot {lot_id} already has a recorded valuation - refusing to "
            f"overwrite (see {VALUATIONS_PATH}'s header). Edit the file "
            "by hand with a dated note if this is a deliberate amendment."
        )

    entries.append({
        "platform": platform,
        "lot_id": lot_id,
        "lot_url": url,
        "title": lot.get("title"),
        "my_max": my_max,
        "why": why,
        "who": who,
        "we_bid": False,
        "recorded_at": _now_iso(),
        "auction_ends_at": lot.get("auction_ends_at"),
    })
    _save_valuations(entries)
    print(f"Recorded: {lot.get('title')} -> ${my_max:,.2f} ({who}): {why}")


def mark_bid(url):
    lot_id = extract_lot_id(url)
    platform = platform_from_url(url)
    if lot_id is None or platform is None:
        sys.exit(f"Couldn't parse a lot_id/platform out of: {url}")

    lot = find_live_lot(lot_id, platform)
    err = _guard_not_closed(lot, lot_id)
    if err:
        sys.exit(err)

    entries = _load_valuations()
    entry = _find_entry(entries, platform, lot_id)
    if entry is None:
        sys.exit(f"No recorded valuation for lot {lot_id} yet - record one first.")
    entry["we_bid"] = True
    _save_valuations(entries)
    print(f"Marked we_bid: true for '{entry.get('title')}'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mark-bid", metavar="LOT_URL", help="mark an existing valuation as bid-on")
    ap.add_argument("lot_url", nargs="?", help="the lot's URL")
    ap.add_argument("my_max", nargs="?", type=float, help="the most you'd pay")
    ap.add_argument("why", nargs="?", help="free text: repair cost, use value, resale plan")
    ap.add_argument("--who", choices=WHO_CHOICES, default="owner")
    args = ap.parse_args()

    if args.mark_bid:
        mark_bid(args.mark_bid)
        return

    if not (args.lot_url and args.my_max is not None and args.why):
        ap.error("LOT_URL, MAX and \"why\" are all required unless using --mark-bid")

    record(args.lot_url, args.my_max, args.why, args.who)


if __name__ == "__main__":
    main()
