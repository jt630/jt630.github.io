#!/usr/bin/env python3
"""
comp_baseline.py - the "deep currents": what this kind of lot has actually
closed for at Musick, as a moving average over the harvested close history
(research/price_history/*.jsonl).

This is CONTEXT, not a target. The bid you place is about THIS auction -
who's bidding now, how much time is left, what condition this exact lot is
in. The baseline just tells you whether the live bid is cheap or dear
relative to the market's memory, so you can be aware of it without fighting
it.

For each live lot it finds comparable past closes and writes:
  comp_n          comparable closes found (after trimming junk prices)
  comp_median     median close, trailing 365d
  comp_wavg       recency-weighted mean (half-life 60d) - the moving average
  comp_low/high   25th / 75th percentile
  comp_30d / comp_90d   median over just the last 30 / 90 days (or None)
  comp_span_days  how far back the data ACTUALLY goes for these comps. The
                  history started 2026-08-27, so until a year accrues this
                  honestly says e.g. 39 - it matures on its own.
  comp_note       one human line for the page

Matching
  Vehicles: same make + model, year within +-3 (nearer years weigh more).
  Everything else: shares >=2 distinctive title tokens (brand/model words,
  not "pistol"/"vacuum"-type generics alone).

No network; pure reads of local files. Safe to run anywhere.

Usage:
    python scripts/comp_baseline.py            # print a table, change nothing
    python scripts/comp_baseline.py --apply    # write comp_* into data/auction_lots.yaml
"""

import argparse
import glob
import io
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_GLOB = os.path.join(_HERE, "..", "research", "price_history", "2*.jsonl")
LOTS_PATH = os.path.join(_HERE, "..", "data", "auction_lots.yaml")

WINDOW_DAYS = 365
HALF_LIFE_DAYS = 60
YEAR_TOLERANCE = 3
VEHICLE_MIN_PRICE = 300      # a real vehicle never closes for $19 - junk row
MIN_TOKEN_OVERLAP = 2
# Coins/jewelry/mixed lots are too heterogeneous for a title match to mean
# anything; only categories where "same make+model" is a real comparison.
COMP_CATEGORIES = {"Vehicles", "Firearms", "Small Engines & Appliances"}

_STOP = set("""
lot with and the for new used box boxed set kit lots mixed bulk assorted
black white blue red green gray grey silver gold chrome stainless wood
wooden steel plastic large small medium side front rear inch inches
""".split())

# Words that describe the KIND of thing but don't identify it: two
# different "pistol"s or "vacuum"s sharing only these are not comps.
_GENERIC = set("""
pistol rifle shotgun revolver handgun semi auto bolt action vacuum cleaner
upright canister mower trimmer blower chainsaw washer pressure generator
gas electric cordless barrel mag magazine round serial grips
""".split())

_YEAR_RE = re.compile(r"\b((?:19|20)\d\d)\b")
_PREFIX_RE = re.compile(r"^\s*(?:lot\s*#?\d+\s*:\s*)?(?:bank repo\s*-\s*)?", re.I)
_MULTI = {"grand", "land", "range", "super"}
_SKIP_MODEL_WORDS = {"super", "duty"}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def vehicle_key(title):
    """(year, make, model) from '2017 JEEP GRAND CHEROKEE LIMITED - 4X4!',
    or None if it doesn't look like 'YEAR MAKE MODEL'."""
    t = _PREFIX_RE.sub("", title or "")
    m = re.match(r"(\d{4})\s+([A-Za-z]+)\s+(.+)", t)
    if not m or not (1950 <= int(m.group(1)) <= 2035):
        return None
    year, make, rest = int(m.group(1)), m.group(2).lower(), m.group(3)
    words = [w for w in re.split(r"[\s\-]+(?=\S)", rest) if w]
    words = [w for w in re.findall(r"[A-Za-z0-9]+(?:-\d+)?", rest)]
    words = [w for w in words if w.lower() not in _SKIP_MODEL_WORDS]
    if not words:
        return None
    first = words[0].lower()
    model = first
    if first in _MULTI and len(words) > 1:
        model = first + words[1].lower()
    return year, make, _norm(model)


def tokens(title):
    t = _PREFIX_RE.sub("", title or "").lower()
    out = set()
    for w in re.findall(r"[a-z0-9][a-z0-9\-\.]*[a-z0-9]|[a-z0-9]", t):
        w = w.strip(".-")
        if len(w) < 3 or w in _STOP or w.isdigit():
            continue
        out.add(w)
    return out


def brand_token(title):
    """First distinctive word of a title - the make/brand ('makita',
    'bissell', 'ruger'). A comp must share it: two lots that only share
    'portable generator' are not the same thing."""
    t = _PREFIX_RE.sub("", title or "").lower()
    for w in re.findall(r"[a-z0-9][a-z0-9\-\.]*[a-z0-9]|[a-z0-9]", t):
        w = w.strip(".-")
        if len(w) >= 3 and not w.isdigit() and w not in _STOP and w not in _GENERIC:
            return w
    return None


def load_closes(glob_pattern=None):
    rows = []
    for path in glob.glob(glob_pattern or HISTORY_GLOB):
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("price_kind") != "close" or not r.get("price"):
                    continue
                when = r.get("catalog_closed_at")
                if not when:
                    continue
                try:
                    r["_when"] = datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc)
                except ValueError:
                    continue
                r["_vkey"] = vehicle_key(r.get("title"))
                r["_tok"] = tokens(r.get("title"))
                rows.append(r)
    return rows


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _trim(comps):
    """Drop junk closes (price a fraction/multiple of the middle) - the
    history has a few $9/$19 rows that are clearly parse artifacts."""
    if len(comps) < 4:
        return comps
    med = statistics.median(c["price"] for c in comps)
    return [c for c in comps if med / 4 <= c["price"] <= med * 4]


def find_comps(lot, closes, now=None):
    now = now or datetime.now(timezone.utc)
    vk = vehicle_key(lot.get("title"))
    lot_tok = tokens(lot.get("title"))
    brand = brand_token(lot.get("title"))
    out = []
    for c in closes:
        age = (now - c["_when"]).days
        if age < 0 or age > WINDOW_DAYS:
            continue
        if vk and c["_vkey"]:
            if c["_vkey"][1:] != vk[1:] or abs(c["_vkey"][0] - vk[0]) > YEAR_TOLERANCE:
                continue
            if c["price"] < VEHICLE_MIN_PRICE:
                continue
            out.append(dict(c, _age=age, _w=1.0 / (1 + abs(c["_vkey"][0] - vk[0]))))
        elif not vk and not c["_vkey"]:
            shared = lot_tok & c["_tok"]
            distinctive = shared - _GENERIC - {brand}
            # A model code ('sw9ve', 'g2c', 'sr40') is the strongest
            # signal; without one, need two distinctive words beyond the
            # brand ("smith & wesson" alone matches cases and knives).
            model_code = any(any(ch.isdigit() for ch in w) and any(ch.isalpha() for ch in w)
                             for w in shared)
            if brand in shared and len(shared) >= MIN_TOKEN_OVERLAP and (
                    model_code or len(distinctive) >= 2):
                out.append(dict(c, _age=age, _w=len(shared) / max(len(lot_tok), 1)))
    return _trim(out)


def summarize(comps, now=None):
    if not comps:
        return None
    prices = sorted(c["price"] for c in comps)
    wts = [c["_w"] * 0.5 ** (c["_age"] / HALF_LIFE_DAYS) for c in comps]
    wavg = sum(w * c["price"] for w, c in zip(wts, comps)) / sum(wts)

    def win(days):
        v = [c["price"] for c in comps if c["_age"] <= days]
        return round(statistics.median(v)) if v else None

    span = max(c["_age"] for c in comps)
    first = min(c["_when"] for c in comps).strftime("%b %-d")
    med = round(statistics.median(prices))
    return {
        "comp_n": len(comps),
        "comp_median": med,
        "comp_wavg": round(wavg),
        "comp_low": round(_percentile(prices, 0.25)),
        "comp_high": round(_percentile(prices, 0.75)),
        "comp_30d": win(30),
        "comp_90d": win(90),
        "comp_span_days": span,
        "comp_note": f"{len(comps)} past close{'s' if len(comps) != 1 else ''} since {first}"
                     f" · median ${med:,}",
    }


def baseline_for(lot, closes, now=None):
    if lot.get("category") not in COMP_CATEGORIES:
        return None
    return summarize(find_comps(lot, closes, now), now)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write comp_* fields into data/auction_lots.yaml")
    ap.add_argument("--lots", default=LOTS_PATH)
    a = ap.parse_args(argv)

    closes = load_closes()
    with open(a.lots, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    lots = doc.get("lots") or []
    hit = 0
    for lot in lots:
        b = baseline_for(lot, closes)
        for k in ("comp_n", "comp_median", "comp_wavg", "comp_low", "comp_high",
                  "comp_30d", "comp_90d", "comp_span_days", "comp_note"):
            lot[k] = b[k] if b else None
        if b:
            hit += 1
            bid = lot.get("current_bid")
            ratio = f"{bid / b['comp_median']:.0%}" if bid else "  -"
            print(f"{(lot.get('title') or '')[:46]:46s} bid {bid or '-':>6} "
                  f"med {b['comp_median']:>6} wavg {b['comp_wavg']:>6} n={b['comp_n']:<3} bid/med {ratio}")
    print(f"\n{hit}/{len(lots)} lots have comps from {len(closes)} closes")
    if a.apply:
        with open(a.lots, "w", encoding="utf-8") as f:
            yaml.dump(doc, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"wrote comp_* into {os.path.abspath(a.lots)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
