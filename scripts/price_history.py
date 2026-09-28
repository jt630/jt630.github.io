#!/usr/bin/env python3
"""
price_history.py - Phase 1 of PRICE-DISCOVERY.md: "own the close price".

Why this exists
----------------
Every other price signal in this project (an eBay comp, an AI guess) is
borrowed. Once a Musick Auction Co. lot actually closes, this project has
never recorded what it sold for - `auction_lots.yaml` is a live snapshot,
fully overwritten every run, so a closed lot's real winning price is gone
the moment the next `auction_finder.py` run replaces it. This script is
the fix: it walks Musick's closed-catalog pages (and the closed-catalogs
index at `/auctions/?alf1=4`), reads the real winning bid off each closed
lot, and appends one JSONL row per lot to `data/price_history/YYYY-MM.jsonl`
- an append-only store that survives every daily overwrite. This is the
single highest-priority piece of the whole Auction Watch project: every
later phase (first-party comps, calibration, the business agent) depends
on this data existing and being honest. See PRICE-DISCOVERY.md's
"Decisions (2026-09-28)" and "Session B" for the design this implements,
and docs/AUCTION-MONITORING.md's "Closed lots, verified against real
markup" for the real markup this parses against. Don't rename the row
schema fields once real rows have shipped - Phase 3 and the calibration
loop both read this file.

The price_kind honesty rule
----------------------------
A row is only ever `price_kind: "close"` when the page itself says the lot
is closed AND sold (`<span class="ended sold">Sold</span>`) AND a winning
bid (`item-win-bid`) was actually parsed. Anything else - a status class
this script hasn't seen before, a missing winning-bid span, a genuinely
unsold/passed lot - becomes `price_kind: "unknown"` with `price: null` and
the raw status class+text recorded in `status_raw`, so a later reader can
tell "we don't know" from "it sold for $0". A lot that hasn't concluded at
all yet (a live catalog's empty `<li id="item-status">`) isn't recorded as
a row either way - it has nothing to report yet. This is the same "never
manufacture false confidence" rule as every other estimate in this
codebase (auction_value.py's deal-flagging, the vehicle mileage/title
gate) applied to storage instead of a live estimate. NEVER guess a price -
a status this parser doesn't recognize is a bug report, not a reason to
invent a number.

The UTC note
------------
A catalog's `end_date` - both in the `/auctions/?alf1=4` index JSON and as
used here - is UTC, despite sitting next to a `timezone_location: "America/
Denver"` field that describes the *sale's own display timezone*, not the
timestamp's. Verified against two real catalogs (914's "2026-09-24
03:22:00" is 09/23 9:22 PM MDT; 920's "2026-09-28 23:07:00" is 09/28 5:07
PM MDT - both exactly UTC-6). Every `catalog_closed_at` this script writes
is that raw `end_date` string reinterpreted as UTC and reformatted as
"YYYY-MM-DDTHH:MM:SSZ" - never shifted by `timezone_location`. It's named
`catalog_closed_at`, not `closed_at`, on purpose: lots inside one catalog
close staggered over the course of the sale, and the catalog page only
gives one end time for the whole sale, not a per-lot timestamp - this
field is honest about being the *catalog's* close time, a reasonable
proxy but not a per-lot fact.

Usage
-----
    python scripts/price_history.py                   # daily CI harvest
    python scripts/price_history.py --backfill         # print size estimate, exit
    python scripts/price_history.py --backfill --yes   # actually backfill (local, resumable)
    python scripts/price_history.py --backfill --yes --since 2026-01-01
"""

import argparse
import html
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone

from auction_finder import (  # noqa: E402
    _MUSICK_LOT_NUM_RE as LOT_NUM_RE,
    _MUSICK_LOT_NUMBIDS_RE as LOT_NUMBIDS_RE,
    _MUSICK_LOT_SPLIT_RE as LOT_SPLIT_RE,
    _MUSICK_LOT_TITLE_RE as LOT_TITLE_RE,
    _money,
    guess_category,
    match_watchlist,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "..", "data")
PRICE_HISTORY_DIR = os.path.join(DATA_DIR, "price_history")
STATE_PATH = os.path.join(PRICE_HISTORY_DIR, "_harvested.json")

MUSICK_CLOSED_INDEX = "https://bid.musickauction.com/auctions/?alf1=4"
MUSICK_CATALOG_URL = "https://bid.musickauction.com/auctions/catalog/id/{catalog_id}"

DAILY_CATALOG_CAP = 5     # bound CI runtime - no backfill happens in CI
ITEMS_PER_PAGE = 100      # confirmed honored on a closed catalog (docs/AUCTION-MONITORING.md)
SLEEP_BETWEEN_RENDERS = 2.0  # polite delay between Playwright renders
# 30 pages * 100 items/page = 3000 lots/catalog, well above the largest real
# catalog seen so far (1090 total_lots) - a hard backstop against a site that
# clamps ?page=N past the last real page and just re-serves it forever,
# which the plain "stop when a page yields zero lots" loop can't detect on
# its own (see harvest_catalog()'s repeat-page detection for the other half
# of this fix).
MAX_CATALOG_PAGES = 30

# ---------------------------------------------------------------------------
# Closed-lot markup (catalog LISTING page). Reuses auction_finder.py's split/
# title/lot-number/bid-count regexes rather than duplicating them; adds the
# two patterns specific to a CONCLUDED lot's markup (a live lot uses
# item-currentbid/item-askingbid and an empty item-status instead - see
# docs/AUCTION-MONITORING.md's "Closed lots, verified against real markup").
# ---------------------------------------------------------------------------
_SECTION_IDS_RE = re.compile(r'data-lid="(\d+)" data-aid="(\d+)"')
_WIN_BID_RE = re.compile(
    r'<li class="item-win-bid"><span class="title">Winning Bid</span>'
    r'<span class="value"><span class="scur\d*">\$</span>'
    r'<span class="exratetip"[^>]*>([\d,]+)</span></span></li>'
)
# The inner <span class="title">Status</span>... block is entirely absent on
# a still-live lot (`<li id="item-status" class="item-status"></li>`) -
# CONFIRMED on the real open catalog 920 - so that whole piece is optional.
_STATUS_RE = re.compile(
    r'<li id="item-status" class="item-status">'
    r'(?:<span class="title">Status</span>'
    r'<span class="value"><span class="([^"]*)">([^<]*)</span></span>)?'
    r'</li>'
)

# The closed-catalogs index (/auctions/?alf1=4) embeds its data in a
# <script data-server="server-data-json"> blob. There are TWO such blobs on
# the real page and `auctionRows` sits nested inside whichever one of them
# has it (under a "default" key) - CONFIRMED via a live probe (see
# docs/AUCTION-MONITORING.md) - so this greps every such blob and searches
# each one recursively rather than assuming which blob or how deep.
_SERVER_JSON_RE = re.compile(r'data-server="server-data-json"[^>]*>(.*?)</script>', re.S)


def _find_key_recursive(obj, key):
    """Depth-first search for `key` anywhere in a parsed-JSON tree. Returns
    the first match, or None. Used because auctionRows' nesting depth in the
    closed-catalogs index isn't guaranteed - see module notes above."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key_recursive(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_key_recursive(v, key)
            if found is not None:
                return found
    return None


def extract_closed_index_rows(page):
    """Return the `auctionRows` list from a rendered /auctions/?alf1=4 page
    (any page number). [] if nothing parses - never raises."""
    for m in _SERVER_JSON_RE.finditer(page):
        try:
            data = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        found = _find_key_recursive(data, "auctionRows")
        if found:
            return found
    return []


def parse_closed_lots(page, catalog_id):
    """Parse every CONCLUDED lot (a status class starting with "ended") out
    of a rendered Musick catalog page - sold or not. A still-live lot (an
    empty `item-status`, see _STATUS_RE) is skipped entirely: it hasn't
    closed, so there's nothing yet to harvest - CONFIRMED this yields zero
    rows against a real open catalog (920). Never raises; a chunk missing a
    title or a lot id is skipped rather than guessed at.

    Returns a list of raw dicts (lot_id, catalog_id, lot_no, title,
    num_bids, price_kind, price, status_raw?) - NOT yet the full row schema
    (see build_row(), which adds category/watchlist/timestamps)."""
    out = []
    for chunk in LOT_SPLIT_RE.split(page)[1:]:
        title_m = LOT_TITLE_RE.search(chunk)
        status_m = _STATUS_RE.search(chunk)
        if not title_m or not status_m or not status_m.group(1):
            continue  # no title, or no "ended" status at all -> still live
        status_class = status_m.group(1).strip()
        status_text = (status_m.group(2) or "").strip()
        if not status_class.startswith("ended"):
            continue

        ids_m = _SECTION_IDS_RE.search(chunk)
        lot_id = int(ids_m.group(1)) if ids_m else None
        if lot_id is None:
            continue  # can't key/dedupe a row without a lot id

        title = html.unescape(title_m.group(1)).strip()
        if not title:
            continue
        num_m = LOT_NUM_RE.search(chunk)
        bids_m = LOT_NUMBIDS_RE.search(chunk)
        win_m = _WIN_BID_RE.search(chunk)

        row = {
            "lot_id": lot_id,
            "catalog_id": int(catalog_id),
            "lot_no": num_m.group(1) if num_m else None,
            "title": title,
            "num_bids": int(bids_m.group(1)) if bids_m else None,
        }
        if status_class == "ended sold" and win_m:
            row["price_kind"] = "close"
            row["price"] = _money(win_m.group(1))
        else:
            row["price_kind"] = "unknown"
            row["price"] = None
            row["status_raw"] = (
                f"{status_class}: {status_text}" if status_text else status_class
            )
        out.append(row)
    return out


def build_row(parsed, catalog_closed_at, observed_at):
    """Turn one parse_closed_lots() dict into the real row schema, in the
    exact key order the contract specifies. `watchlist_matches` is omitted
    entirely when empty (not written as `[]`); `status_raw` is only present
    for `price_kind: "unknown"`."""
    lot = {"title": parsed["title"]}  # category/watchlist run on title only
    row = {
        "platform": "musick",
        "catalog_id": parsed["catalog_id"],
        "lot_id": parsed["lot_id"],
        "lot_no": parsed["lot_no"],
        "title": parsed["title"],
        "category": guess_category(lot),
    }
    matches = match_watchlist(lot)
    if matches:
        row["watchlist_matches"] = matches
    row["price_kind"] = parsed["price_kind"]
    row["price"] = parsed["price"]
    row["num_bids"] = parsed["num_bids"]
    row["catalog_closed_at"] = catalog_closed_at
    row["observed_at"] = observed_at
    if parsed["price_kind"] == "unknown":
        row["status_raw"] = parsed["status_raw"]
    return row


def iso_utc_from_index(end_date_str):
    """'2026-09-24 03:22:00' (already UTC - see module docstring) ->
    '2026-09-24T03:22:00Z'."""
    dt = datetime.strptime(end_date_str.strip(), "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Storage: data/price_history/YYYY-MM.jsonl (one file per catalog_closed_at
# month), plus data/price_history/_harvested.json (state: which catalogs
# have been fully harvested already).
# ---------------------------------------------------------------------------

_MONTH_FILE_RE = re.compile(r"^\d{4}-\d{2}\.jsonl$")


def load_existing_keys(price_history_dir=None):
    """(platform, lot_id) keys already on disk, across every month file -
    the dedupe set every append checks so a re-run never writes a
    duplicate row, no matter which month file it would land in."""
    d = price_history_dir or PRICE_HISTORY_DIR
    keys = set()
    if not os.path.isdir(d):
        return keys
    for name in sorted(os.listdir(d)):
        if not _MONTH_FILE_RE.match(name):
            continue
        with open(os.path.join(d, name), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                keys.add((row.get("platform"), row.get("lot_id")))
    return keys


def append_rows(rows, price_history_dir=None):
    """Append `rows` (already in the full build_row() schema) to their
    catalog_closed_at month's JSONL file, skipping any (platform, lot_id)
    already on disk OR already seen earlier in this same call. Returns the
    number of rows actually appended. Re-running this against the same
    input always appends zero on the second call."""
    d = price_history_dir or PRICE_HISTORY_DIR
    os.makedirs(d, exist_ok=True)
    existing = load_existing_keys(d)
    by_month = {}
    appended = 0
    for row in rows:
        key = (row["platform"], row["lot_id"])
        if key in existing:
            continue
        existing.add(key)
        month = row["catalog_closed_at"][:7]
        by_month.setdefault(month, []).append(row)
        appended += 1
    for month, month_rows in by_month.items():
        path = os.path.join(d, f"{month}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for row in month_rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
    return appended


def load_state(state_path=None):
    p = state_path or STATE_PATH
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"catalogs": {}}


def save_state(state, state_path=None):
    p = state_path or STATE_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def mark_harvested(state, catalog_id, end_date_iso, lots, state_path=None):
    """Updates + saves state after ONE catalog - so a --backfill run killed
    with Ctrl-C loses at most the catalog in progress (Decision 2b)."""
    state.setdefault("catalogs", {})[str(catalog_id)] = {
        "end_date": end_date_iso,
        "lots": lots,
        "harvested_at": now_iso(),
    }
    save_state(state, state_path)
    return state


# ---------------------------------------------------------------------------
# Rendering a catalog end-to-end (network - not exercised by the offline
# test suite, which calls parse_closed_lots()/build_row() directly against
# saved fixtures instead).
# ---------------------------------------------------------------------------


def harvest_catalog(catalog_id, end_date_iso, all_notes, render=None, price_history_dir=None):
    """Render `catalog_id`'s closed catalog page, paged `?items=100&page=N`
    until a page yields zero concluded lots (confirmed honored on a real
    closed catalog - see docs/AUCTION-MONITORING.md), parse every concluded
    lot (sold or not), append new rows, and return (rows_built, appended,
    complete).

    Two guards against an unverified "what does page N past the last real
    page return" behavior (many sites clamp to the last page and just
    re-serve it, which a plain "stop at zero lots" loop can't detect):
    - repeat-page detection: if a page adds zero NEW lot ids (all already
      seen this run), that's the same page again - stop, and this counts
      as a clean end-of-data signal (`complete=True`), not an error.
    - MAX_CATALOG_PAGES hard cap: if hit, the catalog is `complete=False` -
      there may be real unharvested lots past the cap.

    `complete=False` also on a render failure mid-catalog (page 1 failing
    counts as failure too - it produces nothing usable). Callers must NOT
    call mark_harvested() when complete is False, so the next run retries
    this catalog from scratch - rows already appended are safe to
    re-attempt, since append_rows() dedupes on (platform, lot_id) and only
    the still-missing lots get written the second time.

    `render` defaults to musick_render.render_catalog_page; injectable for
    testing so this function itself never needs network access."""
    if render is None:
        from musick_render import render_catalog_page as render
    observed_at = now_iso()
    parsed_rows = []
    seen_lot_ids = set()
    complete = True
    page = 1
    while True:
        if page > MAX_CATALOG_PAGES:
            all_notes.append(
                f"[price-history] catalog {catalog_id}: hit MAX_CATALOG_PAGES "
                f"({MAX_CATALOG_PAGES}) without a clean stop - treating as "
                f"INCOMPLETE, will retry next run"
            )
            complete = False
            break
        url = (
            f"{MUSICK_CATALOG_URL.format(catalog_id=catalog_id)}"
            f"?items={ITEMS_PER_PAGE}&page={page}"
        )
        page_html, _ = render(url)
        if not page_html:
            all_notes.append(
                f"[price-history] catalog {catalog_id} page {page}: render "
                f"failed - treating catalog as INCOMPLETE, will retry next run"
            )
            complete = False
            break
        page_rows = parse_closed_lots(page_html, catalog_id)
        if not page_rows:
            break  # a genuinely empty page - clean end of data

        new_rows = [r for r in page_rows if r["lot_id"] not in seen_lot_ids]
        if not new_rows:
            all_notes.append(
                f"[price-history] catalog {catalog_id} page {page}: repeated "
                f"the previous page's lots (0 new) - stopping, treating as "
                f"end of data"
            )
            break
        for r in new_rows:
            seen_lot_ids.add(r["lot_id"])
        parsed_rows.extend(new_rows)
        page += 1
        time.sleep(SLEEP_BETWEEN_RENDERS)

    if complete and not parsed_rows:
        # A closed catalog with zero concluded lots isn't a real result - it's
        # what markup drift looks like (every page parses to nothing, which
        # reads as a clean empty stop). Never mark that harvested.
        all_notes.append(
            f"[price-history] catalog {catalog_id}: 0 concluded lots parsed - "
            f"possible markup change, treating as INCOMPLETE, will retry next run"
        )
        complete = False

    rows = [build_row(p, end_date_iso, observed_at) for p in parsed_rows]
    appended = append_rows(rows, price_history_dir)
    all_notes.append(
        f"[price-history] catalog {catalog_id}: {len(rows)} concluded lot(s) "
        f"parsed, {appended} new row(s) appended"
        + ("" if complete else " (INCOMPLETE - not marked harvested)")
    )
    return rows, appended, complete


def _closed_candidates(index_rows, now=None):
    """auctionRows entries that are actually closed (status "3") AND whose
    end_date has passed - the index's alf1=4 filter alone isn't trustworthy
    (page 1 mixes in not-yet-closed rows, see docs/AUCTION-MONITORING.md)."""
    now = now or datetime.now(timezone.utc)
    out = []
    for r in index_rows:
        if r.get("status") != "3":
            continue
        end_iso = iso_utc_from_index(r["end_date"])
        end_dt = datetime.strptime(end_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if end_dt > now:
            continue
        out.append((r["id"], end_iso))
    return out


def daily_harvest(all_notes=None, price_history_dir=None, state_path=None, render_index=None):
    """CI daily run (Decision 1): render the closed-catalogs index page 1,
    and page 2 too if every closed catalog found on page 1 is already new
    (not yet in the state file) - a sign there may be more backlog past
    page 1 worth a look. Harvest up to DAILY_CATALOG_CAP closed catalogs
    not yet recorded, updating state after each one. No backfill here."""
    if all_notes is None:
        all_notes = []
    if render_index is None:
        from musick_render import render_catalog_page as render_index

    state = load_state(state_path)

    page1_html, _ = render_index(f"{MUSICK_CLOSED_INDEX}&page=1")
    page1_rows = extract_closed_index_rows(page1_html) if page1_html else []
    page1_closed = _closed_candidates(page1_rows)
    candidates = list(page1_closed)

    already = state.get("catalogs", {})
    unharvested_p1 = [c for c in page1_closed if str(c[0]) not in already]
    if page1_closed and len(unharvested_p1) == len(page1_closed):
        time.sleep(SLEEP_BETWEEN_RENDERS)
        page2_html, _ = render_index(f"{MUSICK_CLOSED_INDEX}&page=2")
        page2_rows = extract_closed_index_rows(page2_html) if page2_html else []
        candidates.extend(_closed_candidates(page2_rows))

    seen_ids = set()
    to_harvest = []
    for cid, end_iso in candidates:
        if str(cid) in already or cid in seen_ids:
            continue
        seen_ids.add(cid)
        to_harvest.append((cid, end_iso))
        if len(to_harvest) >= DAILY_CATALOG_CAP:
            break

    total_appended = 0
    incomplete = []
    for cid, end_iso in to_harvest:
        rows, appended, complete = harvest_catalog(
            cid, end_iso, all_notes, price_history_dir=price_history_dir
        )
        total_appended += appended
        if complete:
            mark_harvested(state, cid, end_iso, len(rows), state_path)
        else:
            incomplete.append(cid)
        time.sleep(SLEEP_BETWEEN_RENDERS)

    all_notes.append(
        f"[price-history] daily: {len(to_harvest)} catalog(s) attempted, "
        f"{total_appended} new row(s) appended"
        + (f", {len(incomplete)} incomplete (will retry next run): {incomplete}" if incomplete else "")
    )
    return total_appended


# ---------------------------------------------------------------------------
# Backfill (owner's PC, once): --backfill prints a size estimate and exits;
# --backfill --yes actually runs it, resumably.
# ---------------------------------------------------------------------------


def _walk_all_index_pages(render_index, all_notes, max_pages=200):
    """Render every /auctions/?alf1=4 page (one render each) until a page
    comes back with zero auctionRows OR repeats a page already seen (same
    "clamps to the last page" risk as harvest_catalog() - unverified
    whether Musick does this, so it's guarded against rather than assumed
    away). max_pages is a hard backstop on top of that - the real index
    tops out around page 17 (827 rows / 50 per page). Rows are deduped by
    auction `id` before returning, so a repeated page never double-counts
    into the backfill size estimate."""
    rows = []
    seen_ids = set()
    page = 1
    while page <= max_pages:
        page_html, _ = render_index(f"{MUSICK_CLOSED_INDEX}&page={page}")
        if not page_html:
            all_notes.append(f"[price-history] index page {page}: render failed, stopping")
            break
        page_rows = extract_closed_index_rows(page_html)
        if not page_rows:
            break
        new_rows = [r for r in page_rows if r.get("id") not in seen_ids]
        if not new_rows:
            all_notes.append(
                f"[price-history] index page {page}: repeated a previous "
                f"page (0 new ids) - stopping"
            )
            break
        for r in new_rows:
            seen_ids.add(r.get("id"))
        rows.extend(new_rows)
        all_notes.append(f"[price-history] index page {page}: {len(new_rows)} new row(s)")
        page += 1
        time.sleep(SLEEP_BETWEEN_RENDERS)
    return rows


def measure_row_bytes():
    """A representative row's real on-disk size (compact JSON + newline),
    MEASURED against the actual schema rather than a guessed round number -
    used to turn "N lots" into a real MB estimate in the backfill preview."""
    sample = build_row(
        {
            "lot_id": 511357,
            "catalog_id": 914,
            "lot_no": "800",
            "title": "2017 FORD F-550 - BLUETOOTH!",
            "num_bids": 35,
            "price_kind": "close",
            "price": 4000,
        },
        "2026-09-24T03:22:00Z",
        "2026-09-28T12:00:00Z",
    )
    return len(json.dumps(sample, separators=(",", ":")).encode("utf-8")) + 1


def estimate_backfill(closed_index_rows, bytes_per_row=None):
    """closed_index_rows: auctionRows dicts already filtered to status "3".
    Returns the numbers `--backfill` prints before requiring --yes."""
    if bytes_per_row is None:
        bytes_per_row = measure_row_bytes()
    n_catalogs = len(closed_index_rows)
    total_lots = sum(int(r.get("total_lots") or 0) for r in closed_index_rows)
    renders = sum(
        math.ceil(max(1, int(r.get("total_lots") or 0)) / ITEMS_PER_PAGE)
        for r in closed_index_rows
    )
    est_bytes = total_lots * bytes_per_row
    seconds_per_render = 5.0  # rough Playwright render time - a real-world
    # observation would sharpen this, but there's no live measurement yet
    est_seconds = renders * (seconds_per_render + SLEEP_BETWEEN_RENDERS)
    return {
        "catalogs": n_catalogs,
        "total_lots": total_lots,
        "renders": renders,
        "bytes_per_row": bytes_per_row,
        "est_mb": round(est_bytes / (1024 * 1024), 1),
        "est_minutes": round(est_seconds / 60, 1),
    }


def _parse_since(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def backfill_main(args, all_notes=None):
    if all_notes is None:
        all_notes = []
    from musick_render import render_catalog_page as render_index

    all_rows = _walk_all_index_pages(render_index, all_notes)
    closed = [r for r in all_rows if r.get("status") == "3"]

    since_dt = _parse_since(args.since)
    if since_dt:
        closed = [
            r for r in closed
            if datetime.strptime(
                iso_utc_from_index(r["end_date"]), "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc) >= since_dt
        ]

    est = estimate_backfill(closed)
    print(f"Backfill size estimate ({len(all_rows)} total index row(s) scanned):")
    print(f"  closed catalogs:    {est['catalogs']}")
    print(f"  total lots:         {est['total_lots']}")
    print(f"  estimated renders:  {est['renders']} (?items={ITEMS_PER_PAGE} pages)")
    print(f"  estimated JSONL:    {est['est_mb']} MB ({est['bytes_per_row']} measured bytes/row)")
    print(
        f"  estimated runtime:  {est['est_minutes']} min "
        f"(assumes ~5s/render + {SLEEP_BETWEEN_RENDERS}s polite sleep per render)"
    )

    if not args.yes:
        print("\nRe-run with --yes to actually backfill.")
        return 0

    state_path = args.state_path or STATE_PATH
    price_history_dir = args.price_history_dir or PRICE_HISTORY_DIR
    state = load_state(state_path)
    total_appended = 0
    incomplete = []
    try:
        for r in closed:
            cid = r["id"]
            if str(cid) in state.get("catalogs", {}):
                continue
            end_iso = iso_utc_from_index(r["end_date"])
            rows, appended, complete = harvest_catalog(
                cid, end_iso, all_notes, price_history_dir=price_history_dir
            )
            total_appended += appended
            if complete:
                mark_harvested(state, cid, end_iso, len(rows), state_path)
            else:
                incomplete.append(cid)
            status = "OK" if complete else "INCOMPLETE - will retry next run"
            print(f"  catalog {cid}: {len(rows)} lot(s), {appended} new ({status})")
            time.sleep(SLEEP_BETWEEN_RENDERS)
    except KeyboardInterrupt:
        print(
            f"\nInterrupted - state saved through the last fully-completed "
            f"catalog ({total_appended} row(s) appended so far). Re-run "
            f"--backfill --yes to resume."
        )
        return 1
    print(f"\nBackfill complete: {total_appended} new row(s) appended.")
    if incomplete:
        print(
            f"{len(incomplete)} catalog(s) were INCOMPLETE and were NOT marked "
            f"harvested - re-run --backfill --yes to retry them: {incomplete}"
        )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Harvest real Musick Auction Co. closing prices into data/price_history/."
    )
    parser.add_argument(
        "--backfill", action="store_true",
        help="Walk every closed-catalog index page once, print a size estimate, "
             "and (only with --yes) actually harvest it all. Local/manual only.",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="With --backfill: actually run it (otherwise only the estimate prints).",
    )
    parser.add_argument(
        "--since", default=None,
        help="YYYY-MM-DD - with --backfill, only harvest catalogs whose end_date "
             "is on/after this date.",
    )
    args = parser.parse_args()
    args.state_path = None
    args.price_history_dir = None

    all_notes = []
    if args.backfill:
        rc = backfill_main(args, all_notes)
        for n in all_notes:
            print(n)
        sys.exit(rc)

    appended = daily_harvest(all_notes)
    for n in all_notes:
        print(n)
    print(f"[price-history] {appended} new row(s) appended this run")


if __name__ == "__main__":
    main()
