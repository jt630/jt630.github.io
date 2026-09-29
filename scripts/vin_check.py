#!/usr/bin/env python3
"""
vin_check.py - Session V (PRICE-DISCOVERY.md): flag suspect VINs on
watchlist vehicles, for free, before anyone spends money on a paid
Carfax/AutoCheck pull.

Three checks, cheapest first:
1. Offline: ISO 3779 check-digit validation and the position-10
   model-year code, against the listing's own claimed year. Pure
   function, no network, unit-tested in scripts/tests/test_vin_check.py.
2. NHTSA vPIC decode (https://vpic.nhtsa.dot.gov, free, no key) - decoded
   year/make/model compared against the listing. A mismatch here is the
   strongest free red flag: it means the VIN and the listing describe two
   different vehicles.
3. NHTSA recalls + complaints by make/model/year (api.nhtsa.gov) - counts
   plus the top few recall summaries, for context only (not a flag).

Plus a plausibility flag that doesn't need the VIN at all: very low
mileage on an old vehicle ("odometer suspect") or implausibly high
miles/year. That flag also unsets car_candidate, since a suspect odometer
means the mileage-based filter can't be trusted.

Caching: forever, per VIN, in data/.cache/vin_{VIN}.json. A VIN's facts
(model year, make, model, recalls) don't change - PRICE-DISCOVERY.md
Decision 6, key on the item not the bid. Recall/complaint counts can grow
over time, so those are refreshed if the cache entry is older than 30
days; the decode itself never is.

Where this runs: the owner's PC or GitHub Actions. The dev sandbox this
was written in can't reach either NHTSA host (network policy), so this is
unverified against live NHTSA responses - the offline check-digit logic
below is verified (see test file); the network layer is a first draft to
be corrected against a real run, same caveat as ebay_comps.py.

Usage:
    python scripts/vin_check.py                  # all VIN'd lots in data/auction_lots.yaml
    python scripts/vin_check.py --candidates-only # only car_candidate: true lots
    python scripts/vin_check.py 1FMZU73W64ZA57062 2004  # single VIN, ad-hoc
"""

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auction_finder import UA  # noqa: E402 - reuse the same browser UA

import yaml  # noqa: E402

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", ".cache")
LOTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "auction_lots.yaml")
REFRESH_RECALLS_AFTER_DAYS = 30
REQUEST_PACING_SECONDS = 1.5  # polite pacing between NHTSA calls, per lot

# ISO 3779 / SAE J853 check-digit transliteration and position weights.
_TRANSLIT = {
    **{str(d): d for d in range(10)},
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

# Makes NHTSA's vPIC decodes under a different name than the badge on the
# vehicle - Ram Trucks split from Dodge as its own brand in 2010, but
# vPIC's WMI-based decode still returns "DODGE" for Ram VINs. Confirmed
# 2026-09-29 against 4 real Ram-badged listings in the live snapshot, all
# 4 decoded as DODGE. Without this, every Dodge/Ram truck in the watchlist
# false-positives on make_mismatch, which would drown the flags that
# actually matter.
_MAKE_ALIASES = {"ram": "dodge"}


def _makes_match(decoded_make, listed_make):
    a = (decoded_make or "").strip().lower()
    b = (listed_make or "").strip().lower()
    a = _MAKE_ALIASES.get(a, a)
    b = _MAKE_ALIASES.get(b, b)
    return a == b


# Position-10 model-year code. Cycles every 30 years; this repo only deals
# in vehicles from roughly 1980-2039, so resolve each letter/digit to the
# later of the two candidate years (the modern cycle) unless that would
# put the vehicle in the future, per _resolve_model_year below.
_YEAR_CODES = {
    "A": 1980, "B": 1981, "C": 1982, "D": 1983, "E": 1984, "F": 1985,
    "G": 1986, "H": 1987, "J": 1988, "K": 1989, "L": 1990, "M": 1991,
    "N": 1992, "P": 1993, "R": 1994, "S": 1995, "T": 1996, "V": 1997,
    "W": 1998, "X": 1999, "Y": 2000,
    "1": 2001, "2": 2002, "3": 2003, "4": 2004, "5": 2005, "6": 2006,
    "7": 2007, "8": 2008, "9": 2009,
}
_YEAR_CODE_CYCLE = 30


def check_digit_valid(vin):
    """True if VIN's position-9 check digit (ISO 3779) is correct. False
    for a malformed VIN (wrong length, invalid characters) too."""
    vin = (vin or "").strip().upper()
    if len(vin) != 17:
        return False
    if "I" in vin or "O" in vin or "Q" in vin:
        return False  # never valid in a real VIN, per the standard
    total = 0
    for i, ch in enumerate(vin):
        if ch not in _TRANSLIT:
            return False
        total += _TRANSLIT[ch] * _WEIGHTS[i]
    remainder = total % 11
    expected = "X" if remainder == 10 else str(remainder)
    return vin[8] == expected


def decode_model_year(vin, listed_year=None):
    """Return the model year implied by VIN position 10, resolved against
    listed_year (the 30-year code cycle repeats, so the code alone is
    ambiguous). Returns None if the VIN is too short or the code unknown.
    """
    vin = (vin or "").strip().upper()
    if len(vin) != 17:
        return None
    code = vin[9]
    base = _YEAR_CODES.get(code)
    if base is None:
        return None
    if listed_year is None:
        return base
    candidates = [base, base + _YEAR_CODE_CYCLE, base - _YEAR_CODE_CYCLE]
    return min(candidates, key=lambda y: abs(y - listed_year))


def offline_flags(vin, listed_year=None, mileage=None):
    """Pure, no-network checks. Returns a list of flag dicts:
    {code, severity ("suspect"|"note"), detail}."""
    flags = []
    vin = (vin or "").strip().upper()
    if not vin:
        return flags
    if not check_digit_valid(vin):
        flags.append({
            "code": "bad_check_digit",
            "severity": "suspect",
            "detail": f"VIN {vin} fails the ISO 3779 check digit - either a "
                      "typo in the listing or not a real VIN.",
        })
        return flags  # a malformed VIN makes the year code unreliable too

    decoded_year = decode_model_year(vin, listed_year)
    if listed_year is not None and decoded_year is not None and decoded_year != listed_year:
        flags.append({
            "code": "year_mismatch",
            "severity": "suspect",
            "detail": f"VIN's model-year code says {decoded_year}, listing "
                      f"says {listed_year}.",
        })

    if mileage is not None and listed_year is not None:
        age = max(0, datetime.now(timezone.utc).year - listed_year)
        if age >= 5 and mileage < 1000:
            flags.append({
                "code": "odometer_suspect",
                "severity": "suspect",
                "detail": f"{mileage} miles on a {age}-year-old vehicle - "
                          "almost certainly a rollover or unknown true "
                          "mileage, not a low-mile survivor.",
            })
        elif age > 0 and mileage / age > 25000:
            flags.append({
                "code": "high_miles_per_year",
                "severity": "note",
                "detail": f"{mileage / age:.0f} miles/year is well above "
                          "typical (~12k/year) - check for fleet/commercial use.",
            })
    return flags


def _cache_path(vin):
    return os.path.join(CACHE_DIR, f"vin_{vin}.json")


def _load_cache(vin):
    path = _cache_path(vin)
    if not os.path.exists(path):
        return None
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(vin, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with io.open(_cache_path(vin), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _get_json(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        # NHTSA's recalls/complaints endpoints return HTTP 400, not 200,
        # when a query legitimately has zero results - the body is still
        # valid JSON ({"count":0,...}). Confirmed 2026-09-29 against real
        # queries (e.g. CHEVROLET/Silverado/2020). Treat a parseable body
        # as real data; only a genuinely unparseable response is a failure.
        try:
            return json.loads(e.read().decode("utf-8", "replace"))
        except (json.JSONDecodeError, OSError):
            sys.stderr.write(f"  [vin_check] HTTP {e.code} on {url}\n")
            return None
    except Exception as e:
        sys.stderr.write(f"  [vin_check] error on {url}: {e}\n")
        return None


def decode_vin_nhtsa(vin):
    """DecodeVinValues - single flat dict of Year/Make/Model/etc, or None
    on failure."""
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
    data = _get_json(url)
    if not data or not data.get("Results"):
        return None
    row = data["Results"][0]
    return {
        "year": row.get("ModelYear") or None,
        "make": row.get("Make") or None,
        "model": row.get("Model") or None,
        "trim": row.get("Trim") or None,
        "engine": row.get("EngineCylinders") or None,
        "error_code": row.get("ErrorCode") or None,
        "error_text": row.get("ErrorText") or None,
    }


def recalls_and_complaints(make, model, year):
    """Counts plus up to 3 recall summaries. Best-effort - any missing
    make/model/year just skips that lookup."""
    out = {"recall_count": None, "recall_summaries": [], "complaint_count": None}
    if not (make and model and year):
        return out
    q = f"make={urllib.parse.quote(make)}&model={urllib.parse.quote(model)}&modelYear={year}"
    recalls = _get_json(f"https://api.nhtsa.gov/recalls/recallsByVehicle?{q}")
    if recalls and recalls.get("results") is not None:
        rows = recalls["results"]
        out["recall_count"] = len(rows)
        out["recall_summaries"] = [
            (r.get("Summary") or "")[:200] for r in rows[:3]
        ]
    complaints = _get_json(f"https://api.nhtsa.gov/complaints/complaintsByVehicle?{q}")
    if complaints and complaints.get("results") is not None:
        out["complaint_count"] = len(complaints["results"])
    return out


def check_vin(vin, listed_year=None, make=None, model=None, mileage=None, use_cache=True):
    """Full check for one VIN: offline flags + cached/fetched NHTSA decode
    and recall/complaint context. Returns a result dict; never raises for
    network failures (NHTSA fields come back None instead)."""
    vin = (vin or "").strip().upper()
    result = {
        "vin": vin,
        "flags": offline_flags(vin, listed_year, mileage),
        "nhtsa_decode": None,
        "recalls": None,
    }
    if not vin or not check_digit_valid(vin):
        return result

    cached = _load_cache(vin) if use_cache else None
    stale_recalls = True
    if cached:
        result["nhtsa_decode"] = cached.get("nhtsa_decode")
        result["recalls"] = cached.get("recalls")
        fetched_at = cached.get("recalls_fetched_at")
        if fetched_at:
            stale_recalls = (time.time() - fetched_at) > REFRESH_RECALLS_AFTER_DAYS * 86400

    if result["nhtsa_decode"] is None:
        result["nhtsa_decode"] = decode_vin_nhtsa(vin)
        time.sleep(REQUEST_PACING_SECONDS)

    decode = result["nhtsa_decode"] or {}
    if decode.get("year") and listed_year and str(decode["year"]) != str(listed_year):
        result["flags"].append({
            "code": "nhtsa_year_mismatch",
            "severity": "suspect",
            "detail": f"NHTSA decodes this VIN as model year {decode['year']}, "
                      f"listing says {listed_year}.",
        })
    if decode.get("make") and make and not _makes_match(decode["make"], make):
        result["flags"].append({
            "code": "nhtsa_make_mismatch",
            "severity": "suspect",
            "detail": f"NHTSA decodes make as '{decode['make']}', listing "
                      f"says '{make}'.",
        })
    # Model comparison is inherently noisier than make/year: listings often
    # store the trim/series number ("1500", "3500") where vPIC returns the
    # base model name ("Ram"), which isn't a real mismatch. Kept as a note
    # for a human to skim, not a suspect flag - confirmed 2026-09-29 against
    # 4 real listings that would otherwise have false-positived as suspect.
    if decode.get("model") and model and model.strip().lower() not in decode["model"].strip().lower() \
            and decode["model"].strip().lower() not in model.strip().lower():
        result["flags"].append({
            "code": "nhtsa_model_mismatch",
            "severity": "note",
            "detail": f"NHTSA decodes model as '{decode['model']}', listing "
                      f"says '{model}'. Often just a trim/series-number "
                      "naming difference, not a real mismatch - check by eye.",
        })

    if stale_recalls:
        result["recalls"] = recalls_and_complaints(
            decode.get("make") or make, decode.get("model") or model,
            decode.get("year") or listed_year,
        )
        time.sleep(REQUEST_PACING_SECONDS)
        _save_cache(vin, {
            "nhtsa_decode": result["nhtsa_decode"],
            "recalls": result["recalls"],
            "recalls_fetched_at": time.time(),
        })
    elif result["nhtsa_decode"] and not cached:
        _save_cache(vin, {
            "nhtsa_decode": result["nhtsa_decode"],
            "recalls": result["recalls"],
            "recalls_fetched_at": time.time(),
        })

    return result


def _load_lots():
    with io.open(LOTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["lots"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("vin", nargs="?", help="check a single VIN ad-hoc")
    ap.add_argument("year", nargs="?", type=int, help="listed year, for the ad-hoc single-VIN mode")
    ap.add_argument("--candidates-only", action="store_true",
                     help="only lots with car_candidate: true (default: all VIN'd lots)")
    ap.add_argument("--no-cache", action="store_true", help="ignore the forever-cache, refetch everything")
    args = ap.parse_args()

    if args.vin:
        result = check_vin(args.vin, listed_year=args.year, use_cache=not args.no_cache)
        print(json.dumps(result, indent=2))
        return

    lots = _load_lots()
    vinned = [l for l in lots if l.get("vin")]
    if args.candidates_only:
        vinned = [l for l in vinned if l.get("car_candidate")]

    print(f"Checking {len(vinned)} VIN'd lot(s)...")
    for lot in vinned:
        result = check_vin(
            lot["vin"], listed_year=lot.get("year"), make=lot.get("make"),
            model=lot.get("model"), mileage=lot.get("mileage"),
            use_cache=not args.no_cache,
        )
        suspects = [f for f in result["flags"] if f["severity"] == "suspect"]
        mark = "[!]" if suspects else "[ok]"  # ASCII-safe: Windows console defaults to cp1252
        print(f"  {mark} {lot.get('title', lot['vin'])}")
        for f in result["flags"]:
            print(f"      [{f['severity']}] {f['code']}: {f['detail']}")


if __name__ == "__main__":
    main()
