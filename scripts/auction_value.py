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

This is a text-only estimate (title + category + description); it does not
look at photos. Treat every number as a rough band, not an appraisal - it's
meant to surface lots worth a second look, not to be bid against blindly.

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

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_HERE, "..", "data", "auction_lots.yaml")

MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"
BATCH_SIZE = 12
FLAG_THRESHOLD = 0.30   # flag lots where est. value beats current bid by 30%+
FLAG_MIN_VALUE = 20     # ...and the estimate is at least worth $20, to skip noise

SYSTEM = (
    "You value used and government-surplus items for a Boise, Idaho auction "
    "deal-monitor. For each lot, estimate a realistic RESALE range - what a "
    "private-party buyer would actually pay in the Boise/Treasure Valley "
    "area within a couple weeks, not retail-new price - as low/high dollar "
    "integers, plus a one-sentence note. Be conservative: police and "
    "government surplus lots are frequently used, incomplete, evidence, "
    "unclaimed, or sold as-is with no warranty and no guarantee they power "
    "on - say so in the note whenever the title or description suggests it. "
    "If there isn't enough information in the title/description to value a "
    "lot with any confidence, return null for both low and high rather than "
    "guessing. Respond with ONLY a JSON array, one object per lot in the "
    "same order given: "
    '{"id": <int>, "low": <int|null>, "high": <int|null>, "note": <string>}.'
)


def call_claude(lots):
    items = [
        {
            "id": i,
            "title": lot.get("title"),
            "category": lot.get("category"),
            "description": (lot.get("description") or "")[:400],
            "current_bid": lot.get("current_bid"),
        }
        for i, lot in enumerate(lots)
    ]
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
    low, high = r.get("low"), r.get("high")
    lot["estimated_value_low"] = low
    lot["estimated_value_high"] = high
    lot["ai_note"] = r.get("note")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        mid = round((low + high) / 2)
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


def estimate(lots):
    for start in range(0, len(lots), BATCH_SIZE):
        batch = lots[start:start + BATCH_SIZE]
        try:
            results = call_claude(batch)
        except Exception as e:
            sys.stderr.write(f"  [batch starting at {start}] error: {e}\n")
            continue
        by_id = {r.get("id"): r for r in results if isinstance(r, dict)}
        for i, lot in enumerate(batch):
            r = by_id.get(i)
            if r:
                apply_estimate(lot, r)
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
