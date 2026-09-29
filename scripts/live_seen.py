#!/usr/bin/env python3
"""
live_seen.py - Session B2 (PRICE-DISCOVERY.md): the "see it while it's
alive" half of vanished-lot recovery.

docs/AUCTION-MONITORING.md's "Unsold lots disappear after close" confirmed
that a lot which doesn't sell just vanishes from its catalog page - no
trace, no "Unsold" status, a plain 404. The only way to ever know it
existed is to have recorded it BEFORE it closed. This script does that
half; scripts/price_history.py's harvest_catalog() (via
find_vanished_lots()) does the other half, comparing what got recorded
here against what a closed catalog actually shows.

What it does
------------
1. Renders the closed-catalogs index (`/auctions/?alf1=4&page=1`) - the
   same page price_history.py already uses, which (per
   docs/AUCTION-MONITORING.md) mixes in not-yet-closed rows (`status:
   "1"`) sorted by end_date, so no separate "open catalogs" endpoint is
   needed.
2. Filters to catalogs whose end_date falls within the next
   CLOSING_SOON_HOURS (default 48) - bounds the cost to sales actually
   about to conclude, not every open catalog on the site.
3. Pages each one (`?items=100&page=N`, same pattern as harvest_catalog())
   and records every still-live lot's last bid/bid-count via
   price_history.parse_live_lots(), appended to
   research/price_history/_live_seen.jsonl.

Why this is separate from the daily harvest, not folded in: the harvest
walks CLOSED catalogs; this walks OPEN ones. Different render target,
different cadence rationale (this only matters run-to-run near a close;
the harvest matters catch-up-safe over days), different failure mode (a
missed live-fetch just means fewer vanished lots recovered later, never
corrupts anything - lower stakes than the close-price harvest itself).

UNVERIFIED against live markup - same caveat as every other Musick-facing
script in this repo before its first real run: this was written without
Playwright available (see musick_render.py's own docstring), so the
render/pagination logic is a first draft. parse_live_lots() itself reuses
price_history.py's already-verified regexes plus the data-lid/data-aid
extraction confirmed present on musick_catalog_920_open.html - the parsing
logic has offline test coverage; the page-walking loop against a REAL
live-narrowing catalog has not been run for real yet. Dispatch via
GitHub Actions (debug_html: true) and check
research/price_history/_live_seen.jsonl plus the job's fetch notes before
trusting this against a real sale.

Usage:
    python scripts/live_seen.py                  # CI: catalogs closing within 48h
    python scripts/live_seen.py --hours 12        # narrower window
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from musick_render import BLOCK_NOTE, looks_blocked  # noqa: E402
import price_history as ph

CLOSING_SOON_HOURS = 48


def open_candidates_closing_soon(index_rows, now=None, hours=CLOSING_SOON_HOURS):
    """auctionRows entries that are NOT yet closed (status != "3") whose
    end_date falls within [now, now+hours]. Mirrors price_history.py's
    _closed_candidates() but for the other side of the same status field -
    see docs/AUCTION-MONITORING.md on why status:"1" rows show up on the
    alf1=4 (Closed) index page at all."""
    now = now or datetime.now(timezone.utc)
    horizon = now + timedelta(hours=hours)
    out = []
    for r in index_rows:
        if r.get("status") == "3":
            continue
        try:
            end_iso = ph.iso_utc_from_index(r["end_date"])
        except (KeyError, ValueError):
            continue
        end_dt = datetime.strptime(end_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if not (now <= end_dt <= horizon):
            continue
        out.append((r["id"], end_iso))
    return out


def fetch_catalog_live_lots(catalog_id, all_notes, render=None):
    """Page through one open catalog (?items=100&page=N), same
    repeat-page/MAX_CATALOG_PAGES guards as harvest_catalog(). Returns
    (rows, complete) - complete=False on a render failure, a block, or the
    page cap, same meaning as harvest_catalog()'s (never appended in that
    case; a live snapshot is only useful if it's the whole catalog, not a
    guess at which pages got skipped)."""
    if render is None:
        from musick_render import render_catalog_page as render
    rows = []
    seen_lot_ids = set()
    complete = True
    page = 1
    while True:
        if page > ph.MAX_CATALOG_PAGES:
            all_notes.append(
                f"[live-seen] catalog {catalog_id}: hit MAX_CATALOG_PAGES "
                f"({ph.MAX_CATALOG_PAGES}) without a clean stop - INCOMPLETE"
            )
            complete = False
            break
        url = (
            f"{ph.MUSICK_CATALOG_URL.format(catalog_id=catalog_id)}"
            f"?items={ph.ITEMS_PER_PAGE}&page={page}"
        )
        page_html, _ = render(url)
        if not page_html:
            all_notes.append(
                f"[live-seen] catalog {catalog_id} page {page}: render failed - INCOMPLETE"
            )
            complete = False
            break
        if looks_blocked(page_html):
            all_notes.append(f"[live-seen] catalog {catalog_id} page {page}: {BLOCK_NOTE}")
            complete = False
            break
        page_rows = ph.parse_live_lots(page_html, catalog_id)
        if not page_rows:
            break  # clean end of data (or every remaining lot already closed)

        new_rows = [r for r in page_rows if r["lot_id"] not in seen_lot_ids]
        if not new_rows:
            all_notes.append(
                f"[live-seen] catalog {catalog_id} page {page}: repeated the "
                f"previous page (0 new) - stopping"
            )
            break
        for r in new_rows:
            seen_lot_ids.add(r["lot_id"])
        rows.extend(new_rows)
        page += 1
        time.sleep(ph.SLEEP_BETWEEN_RENDERS)
    return rows, complete


def run(all_notes=None, render_index=None, render=None, live_seen_path=None, hours=CLOSING_SOON_HOURS):
    """Full pass: find catalogs closing within `hours`, page each, append
    every observed live lot to _live_seen.jsonl. Returns total rows
    written."""
    if all_notes is None:
        all_notes = []
    if render_index is None:
        from musick_render import render_catalog_page as render_index

    page1_html, _ = render_index(f"{ph.MUSICK_CLOSED_INDEX}&page=1")
    if not page1_html:
        all_notes.append("[live-seen] index render failed (no page); nothing attempted")
        return 0
    if looks_blocked(page1_html):
        all_notes.append(f"[live-seen] index: {BLOCK_NOTE}; nothing attempted")
        return 0
    index_rows = ph.extract_closed_index_rows(page1_html)
    candidates = open_candidates_closing_soon(index_rows, hours=hours)
    all_notes.append(
        f"[live-seen] index page 1: {len(index_rows)} row(s), "
        f"{len(candidates)} catalog(s) closing within {hours}h"
    )

    total_written = 0
    for catalog_id, end_iso in candidates:
        rows, complete = fetch_catalog_live_lots(catalog_id, all_notes, render=render)
        if not complete:
            all_notes.append(
                f"[live-seen] catalog {catalog_id}: incomplete fetch, not recorded "
                f"(a partial live-seen list would look like every unfetched lot vanished)"
            )
            continue
        written = ph.append_live_seen(rows, ph.now_iso(), live_seen_path=live_seen_path)
        total_written += written
        all_notes.append(
            f"[live-seen] catalog {catalog_id} (closes {end_iso}): "
            f"{len(rows)} live lot(s) recorded"
        )
        time.sleep(ph.SLEEP_BETWEEN_RENDERS)

    all_notes.append(f"[live-seen] {total_written} live-lot observation(s) written this run")
    return total_written


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--hours", type=float, default=CLOSING_SOON_HOURS,
        help=f"only catalogs closing within this many hours (default {CLOSING_SOON_HOURS})",
    )
    args = parser.parse_args()

    all_notes = []
    run(all_notes, hours=args.hours)
    for n in all_notes:
        print(n)


if __name__ == "__main__":
    main()
