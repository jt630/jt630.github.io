#!/usr/bin/env python3
"""
garage_finder.py - "Car Hunt 2.0": cheap, cool, OLD project vehicles with LOW
MILES FOR THEIR AGE. Same two sources and mechanics as car_finder.py (Boise
Craigslist HTML+JSON-LD, Cars.com via cache-backed fetch, Treasure Valley geo
filter) but a different question: not "best daily driver deal" but "best
garage project" -- a truck or old 4Runner/Cherokee that's been babied.

Categories
----------
1. fourrunner_classic - Toyota 4Runner (2nd/3rd gen), 1990-2002, <= $16,000
2. toyota_truck       - Toyota Pickup (pre-Tacoma, 1984-1995) or 1st-gen
                        Tacoma (1995-2004), <= $14,000
3. cherokee_xj         - Jeep Cherokee XJ body, 1984-2001, <= $10,000
                        (explicitly NOT Grand Cherokee - different platform)

No mileage floor. Instead we compute miles_per_year = odometer / (2026 - year)
so a low-miles-for-its-age listing sorts to the top of its category. Odometer
is usually present on Cars.com, usually absent on Craigslist search-result
pages (noted in fetch notes, same caveat car_finder.py logs).

This module imports its HTTP/parsing/geo-filter plumbing from car_finder.py
rather than re-implementing it - see that file's docstring for source notes.

Usage
-----
    python scripts/garage_finder.py           # run everything, write YAML
    python scripts/garage_finder.py --dry-run # print, don't write

Output: data/garage_listings.yaml
Cars.com cache (if live fetch is blocked): data/.cache/garage_<key>.json
"""

import argparse
import os
import re
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import car_finder as cf  # reuse fetch/, geo-filter, Cars.com parsing, YAML writer bits

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "..", "data", "garage_listings.yaml")
CACHE_DIR = os.path.join(_HERE, "..", "data", ".cache")
ZIP = cf.ZIP
CURRENT_YEAR = date.today().year  # 2026 at time of writing

# key, cl_terms, min_year, max_year, max_price, title_must, exclude_terms,
#     carscom_make, carscom_model
SEARCHES = [
    ("fourrunner_classic", ["4runner"], 1990, 2002, 16000,
     ["4runner", "4 runner"], [], "toyota", "toyota-4runner"),
    ("toyota_truck", ["tacoma", "toyota pickup", "toyota truck"], 1984, 2004,
     14000, ["tacoma", "pickup", "toyota truck", "xtracab", "extracab"], [],
     "toyota", "toyota-tacoma"),
    ("cherokee_xj", ["jeep cherokee"], 1984, 2001, 10000,
     ["cherokee"], ["grand cherokee", "grand-cherokee"], "jeep", "jeep-cherokee"),
]
YAML_KEYS = ("fourrunner_classic", "toyota_truck", "cherokee_xj")

# Reuse the same dealer flags / geo lists / sold-listing suppression as
# car_finder.py - it's the same Treasure Valley market.
DEALER_FLAGS = cf.DEALER_FLAGS
SOLD_URLS = set()   # nothing confirmed sold yet in this hunt
LISTING_FLAGS = {}  # nothing seen in person yet in this hunt

FIELDS = ("source", "title", "price", "year", "odometer", "url", "post_date",
          "location", "deal_rating", "market_delta", "miles_per_year",
          "dealer_flag")


# --------------------------------------------------------------------------- #
# year/odometer parsing - car_finder.parse_year floors at 1990, too tight for
# an XJ Cherokee or an '87 pickup, so widen the floor here.
# --------------------------------------------------------------------------- #

def parse_year(title):
    m = cf.YEAR_RE.search(title or "")
    if m:
        y = int(m.group(0))
        if 1980 <= y <= CURRENT_YEAR + 1:
            return y
    return None


def miles_per_year(odometer, year):
    if not odometer or not year:
        return None
    age = CURRENT_YEAR - year
    if age <= 0:
        return None
    return round(odometer / age)


def build_url(term, min_year, max_year, max_price):
    import urllib.parse
    q = urllib.parse.urlencode({
        "query": term,
        "min_auto_year": min_year,
        "max_auto_year": max_year,
        "max_price": max_price,
        "sort": "date",
        "bundleDuplicates": 1,
    })
    return f"{cf.BASE}?{q}"


# "WANTED ..." posts are buyers soliciting a car, not a seller's listing --
# the "price" on them is what the buyer will pay, which reads as an
# absurdly good deal if not filtered out. Universal exclude, all categories.
WANTED_RE = re.compile(r"\bwanted\b", re.I)


def _titlematch(title, musts, excludes):
    title = title or ""
    if WANTED_RE.search(title):
        return False
    t = re.sub(r"[^a-z0-9]", "", title.lower())
    if any(re.sub(r"[^a-z0-9]", "", x.lower()) in t for x in excludes):
        return False
    return any(re.sub(r"[^a-z0-9]", "", m.lower()) in t for m in musts)


def run_search(key, terms, min_year, max_year, max_price, title_must, excludes):
    all_rows, notes = [], []
    for term in terms:
        url = build_url(term, min_year, max_year, max_price)
        code, page = cf.fetch(url)
        if code == 403:
            notes.append(f"{term}: 403 BLOCKED")
        elif not page:
            notes.append(f"{term}: empty (code {code})")
        else:
            ld = cf.from_jsonld(page) or []
            rows = cf.from_html(page)
            how = "html+json-ld" if ld else "html"
            if not rows and ld:
                rows, how = ld, "json-ld"
            rows = cf._merge(rows, ld)
            for r in rows:
                r["year"] = parse_year(r.get("title"))
            if not rows:
                notes.append(f"{term}: 0 rows (page {len(page)}b, code {code})")
            else:
                notes.append(f"{term}: {len(rows)} via {how}")
                all_rows.extend(rows)
        time.sleep(cf.SLEEP)
    rows = cf.dedupe(all_rows)
    rows = [r for r in rows if _titlematch(r.get("title"), title_must, excludes)]
    rows = [r for r in rows
            if (r.get("year") is None or min_year <= r["year"] <= max_year)
            and (r.get("price") is None or r["price"] <= max_price)]
    return rows, notes


def carscom_search(key, make, model, min_year, max_year, max_price, title_must, excludes):
    notes = []
    cache = os.path.join(CACHE_DIR, f"garage_{key}.json")
    url = cf.carscom_url(make, model)
    code, page = cf.fetch(url, headers=cf.BROWSER)
    rows = cf.carscom_parse(page) if page else []
    time.sleep(cf.SLEEP)
    if rows:
        os.makedirs(CACHE_DIR, exist_ok=True)
        import json
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump({"fetched": date.today().isoformat(), "rows": rows}, fh)
        notes.append(f"cars.com: {len(rows)} live")
    else:
        why = "403 BLOCKED" if code == 403 else f"empty (code {code})"
        if os.path.exists(cache):
            import json
            with open(cache, encoding="utf-8") as fh:
                c = json.load(fh)
            rows = c.get("rows", [])
            notes.append(f"cars.com: {why}; used cache from {c.get('fetched')} "
                         f"({len(rows)} rows)")
        else:
            notes.append(f"cars.com: {why}; no cache")
    for r in rows:
        r.setdefault("deal_rating", None)
        r.setdefault("market_delta", None)
        r.setdefault("post_date", None)
    rows = [r for r in rows
            if _titlematch(r.get("title"), title_must, excludes)
            and (r.get("year") is None or min_year <= r["year"] <= max_year)
            and (r.get("price") is None or r["price"] <= max_price)]
    return rows, notes


def _yv(v):
    return cf._yv(v)


def dump_yaml(data):
    lines = [f"generated: {data['generated']}", ""]
    for key in YAML_KEYS:
        rows = data.get(key, [])
        lines.append(f"{key}:")
        if not rows:
            lines[-1] = f"{key}: []"
            lines.append("")
            continue
        for r in rows:
            first = True
            for f in FIELDS:
                prefix = "  - " if first else "    "
                lines.append(f"{prefix}{f}: {_yv(r.get(f))}")
                first = False
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    result = {"generated": date.today().isoformat()}
    all_notes = []
    total_dropped = 0
    for (key, terms, min_year, max_year, max_price, title_must, excludes,
         cc_make, cc_model) in SEARCHES:
        cl_rows, notes = run_search(key, terms, min_year, max_year, max_price,
                                     title_must, excludes)
        cc_rows, cc_notes = carscom_search(key, cc_make, cc_model, min_year,
                                            max_year, max_price, title_must, excludes)
        notes += cc_notes

        merged = cf.dedupe(cl_rows + cc_rows)
        kept = [r for r in merged
                if cf.in_region(r.get("location"), r.get("url"))
                and r.get("url") not in SOLD_URLS]
        dropped = len(merged) - len(kept)
        total_dropped += dropped
        for r in kept:
            loc = (r.get("location") or "").lower()
            r["dealer_flag"] = LISTING_FLAGS.get(r.get("url")) or next(
                (msg for sub, msg in DEALER_FLAGS.items() if sub in loc), None)
            r["miles_per_year"] = miles_per_year(r.get("odometer"), r.get("year"))
            r.setdefault("post_date", None)

        # low-miles-for-age first; unknown mpy sorts last (car_finder's
        # price-sort fallback pattern, applied to miles_per_year instead)
        kept.sort(key=lambda r: (r.get("miles_per_year") is None,
                                  r.get("miles_per_year") or 0))
        kept = kept[:35]
        result[key] = kept

        all_notes += [f"[{key}] {n}" for n in notes]
        n_cl = sum(1 for r in kept if r.get("source") == "craigslist")
        n_cc = sum(1 for r in kept if r.get("source") == "cars.com")
        prices = [r["price"] for r in kept if r.get("price")]
        odos = [r["odometer"] for r in kept if r.get("odometer")]
        rng = f"${min(prices):,}-${max(prices):,}" if prices else "n/a"
        orng = f"{min(odos):,}-{max(odos):,} mi" if odos else "n/a"
        print(f"{key:20s} {len(kept):2d}  (cl {n_cl}, cars.com {n_cc})  "
              f"price {rng}  odo {orng}  region_dropped {dropped}")

    print(f"\nregion_filtered_out (all categories): {total_dropped}")
    print("\nfetch notes:")
    for n in all_notes:
        print("  " + n)

    if a.dry_run:
        print("\n--dry-run: not writing")
        return
    path = os.path.abspath(OUT)
    text = dump_yaml(result)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
