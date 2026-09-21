#!/usr/bin/env python3
"""
auction_value.py - fill in an AI-estimated resale range for each lot in
data/auction_lots.yaml (written by scripts/auction_finder.py), and compute
a deal score so content/auctions.md can rank "biggest gap between current
bid and what this would actually resell for" to the top.

Calls the Anthropic Messages API directly over HTTPS via urllib (no SDK,
no requests dependency - matches the rest of scripts/), batching several
lots per request to keep cost and latency down. Needs
ANTHROPIC_API_KEY in the environment - a GitHub Actions secret in
production, the same pattern as FRED_API_KEY / TMDB_KEY in
.github/workflows/refresh-data.yml and deploy.yml.

No key set -> the script prints a note and exits without changing anything.
The page still renders fine without estimates (current bid, close time,
link) - it just can't sort by deal or show a flag.

Value grounding: before asking Claude, each lot's title is looked up in
scripts/ebay_comps.py against recent eBay SOLD listings - real transaction
prices, not a guess. When there are enough comps (>= EBAY_MIN_COMPS), the
comp stats become the lot's estimated_value_low/high/mid directly and
`value_source` is recorded as "ebay"; Claude still sees the comps and still
writes the note (so it can flag "as-is"/condition caveats a raw median
can't know about), it just doesn't get to override the number. When comps
are too thin or eBay is unreachable, this falls back to Claude's own
text-only estimate as before, with `value_source` "ai". Either way this is
a rough band, not an appraisal - it's meant to surface lots worth a second
look, not to be bid against blindly.

Usage
-----
    python scripts/auction_value.py              # fill in missing estimates
    python scripts/auction_value.py --dry-run     # print, don't write
    python scripts/auction_value.py --all         # re-estimate every lot,
                                                     not just new ones
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ebay_comps import lookup as ebay_lookup  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_HERE, "..", "data", "auction_lots.yaml")

MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"
BATCH_SIZE = 12
FLAG_THRESHOLD = 0.30   # flag lots where est. value beats current bid by 30%+
FLAG_MIN_VALUE = 20     # ...and the estimate is at least worth $20, to skip noise
EBAY_MIN_COMPS = 3      # need at least this many sold comps to trust them over Claude
EBAY_SLEEP = 1.5        # politeness delay between eBay lookups

SYSTEM = (
    "You value used and government-surplus items for a Boise, Idaho auction "
    "deal-monitor. For each lot, estimate a realistic RESALE range - what a "
    "private-party buyer would actually pay in the Boise/Treasure Valley "
    "area within a couple weeks, not retail-new price - as low/high dollar "
    "integers, plus a one-sentence note. Be conservative: police and "
    "government surplus lots are frequently used, incomplete, evidence, "
    "unclaimed, or sold as-is with no warranty and no guarantee they power "
    "on - say so in the note whenever the title or description suggests it. "
    "For category 'Vehicles' specifically, be extra conservative: a title "
    "alone rarely gives mileage, condition, or clear title status, all of "
    "which swing resale value by thousands - default to a wide low/high "
    "band and mention in the note what's missing (mileage, title status, "
    "running condition) that a bidder should check before relying on this "
    "number. "
    "Some lots include an 'ebay_comps' field - real recent eBay SOLD prices "
    "for similar items (n = sample size, low/median/high in dollars). When "
    "present, treat it as the primary anchor for your low/high range rather "
    "than guessing from scratch, and use your note to explain how this "
    "specific lot's condition/completeness should move a buyer up or down "
    "from those comps (e.g. 'described as non-functional, so price toward "
    "the bottom of the $40-90 eBay range'). Comps are for a similar item in "
    "typical resale condition, not necessarily this exact lot's condition. "
    "If there isn't enough information in the title/description (and no "
    "usable ebay_comps) to value a lot with any confidence, return null for "
    "both low and high rather than guessing. Respond with ONLY a JSON "
    "array, one object per lot in the same order given: "
    '{"id": <int>, "low": <int|null>, "high": <int|null>, "note": <string>}.'
)


def call_claude(lots):
    items = []
    for i, lot in enumerate(lots):
        item = {
            "id": i,
            "title": lot.get("title"),
            "category": lot.get("category"),
            "description": (lot.get("description") or "")[:400],
            "current_bid": lot.get("current_bid"),
        }
        comps = lot.get("_ebay_comps")
        if comps:
            item["ebay_comps"] = comps
        items.append(item)
    body = {
        "model": MODEL,
        "max_tokens": 2000,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": json.dumps(items)}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode("utf-8"))
    text = "".join(
        b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text"
    )
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError(f"no JSON array in response: {text[:200]!r}")
    return json.loads(m.group(0))


def apply_estimate(lot, r):
    comps = lot.pop("_ebay_comps", None)
    lot["ebay_n"] = comps["n"] if comps else None
    lot["ebay_median"] = comps["median"] if comps else None
    lot["ai_note"] = r.get("note")

    if comps and comps["n"] >= EBAY_MIN_COMPS:
        # Real sold comps beat an LLM guess when there are enough of them -
        # Claude's note (above) still explains how this lot's condition
        # should move a buyer within/around this range. Use the observed
        # median directly as "mid", not the midpoint of low/high - those
        # are the 25th/75th percentile band, and for a skewed price
        # distribution the two are not the same number.
        low, high, mid = comps["low"], comps["high"], comps["median"]
        lot["value_source"] = "ebay"
    else:
        low, high = r.get("low"), r.get("high")
        mid = (
            round((low + high) / 2)
            if isinstance(low, (int, float)) and isinstance(high, (int, float))
            else None
        )
        lot["value_source"] = "ai" if mid is not None else None

    lot["estimated_value_low"] = low
    lot["estimated_value_high"] = high
    if isinstance(mid, (int, float)):
        bid = lot.get("current_bid") or 0
        deal_pct = round((mid - bid) / mid, 3) if mid else None
        lot["estimated_value_mid"] = mid
        lot["deal_score"] = mid - bid
        lot["deal_pct"] = deal_pct
        lot["flagged"] = bool(
            deal_pct is not None and deal_pct >= FLAG_THRESHOLD and mid >= FLAG_MIN_VALUE
        )
    else:
        lot["estimated_value_mid"] = None
        lot["deal_score"] = None
        lot["deal_pct"] = None
        lot["flagged"] = False


def fetch_ebay_comps(lots, notes):
    for lot in lots:
        title = lot.get("title")
        if not title:
            continue
        lot["_ebay_comps"] = ebay_lookup(title, notes=notes)
        time.sleep(EBAY_SLEEP)


def estimate(lots):
    ebay_notes = []
    print(f"looking up eBay sold comps for {len(lots)} lots...")
    fetch_ebay_comps(lots, ebay_notes)
    n_with_comps = sum(
        1 for l in lots
        if l.get("_ebay_comps") and l["_ebay_comps"]["n"] >= EBAY_MIN_COMPS
    )
    print(f"{n_with_comps} lot(s) have {EBAY_MIN_COMPS}+ eBay comps.")
    for n in ebay_notes:
        print("  " + n)

    for start in range(0, len(lots), BATCH_SIZE):
        batch = lots[start:start + BATCH_SIZE]
        try:
            results = call_claude(batch)
        except Exception as e:
            sys.stderr.write(f"  [batch starting at {start}] error: {e}\n")
            # Claude failed, but real eBay comps (if any) are still usable -
            # apply_estimate(lot, {}) falls back to comps-only when present,
            # and always pops the transient _ebay_comps key either way so it
            # never leaks into the written YAML.
            for lot in batch:
                apply_estimate(lot, {})
            continue
        by_id = {r.get("id"): r for r in results if isinstance(r, dict)}
        for i, lot in enumerate(batch):
            apply_estimate(lot, by_id.get(i) or {})
        time.sleep(1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true",
                     help="re-estimate every lot, not just ones missing a value")
    a = ap.parse_args()

    if not os.path.exists(DATA):
        sys.exit(f"no {DATA} - run scripts/auction_finder.py first")
    with open(DATA, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    lots = doc.get("lots") or []

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set - skipping valuation, lots keep null estimates.")
        return

    todo = lots if a.all else [l for l in lots if l.get("estimated_value_mid") is None]
    print(f"estimating {len(todo)} of {len(lots)} lots ({MODEL})...")
    estimate(todo)

    lots.sort(key=lambda l: (l.get("deal_score") is None, -(l.get("deal_score") or 0)))
    doc["lots"] = lots

    n_flagged = sum(1 for l in lots if l.get("flagged"))
    print(f"{n_flagged} lot(s) flagged as deals (est. value >= "
          f"{int(FLAG_THRESHOLD * 100)}% over current bid).")

    if a.dry_run:
        preview = [
            {"title": l.get("title"), "current_bid": l.get("current_bid"),
             "estimated_value_mid": l.get("estimated_value_mid"),
             "deal_score": l.get("deal_score")}
            for l in lots[:10]
        ]
        print(json.dumps(preview, indent=2))
        print("\n--dry-run: not writing")
        return

    with open(DATA, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"wrote {DATA}")


if __name__ == "__main__":
    main()
