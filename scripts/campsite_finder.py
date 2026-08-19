#!/usr/bin/env python3
"""
campsite_finder.py - query the recreation.gov API for real campground availability.

The reason this exists: recreation.gov's website shows you a booking calendar,
which quietly hides walk-up inventory. A campground can look "sold out" while
half its sites are first-come, first-served and simply never enter the calendar.
This tool separates the two.

Three status values matter, and conflating the last two is the classic mistake:

    Available       bookable right now
    Reserved        somebody booked it, it is gone
    Not Reservable  NOT in the booking system

"Not Reservable" on a single date can mean the season hasn't opened. But a site
marked "Not Reservable" on *every* day of the month is being held out of the
system on purpose - that is walk-up inventory, and it is invisible if you only
read the booking calendar.

Usage
-----
    # find facility IDs by name
    python scripts/campsite_finder.py search "warm lake"

    # check specific campgrounds for a date range
    python scripts/campsite_finder.py check 234030 234254 --start 2026-08-28 --nights 2

    # sweep every campground within a radius of a point
    python scripts/campsite_finder.py near --lat 44.91 --lon -116.10 --radius 50 \
        --start 2026-08-28 --nights 2

    # sweep from a named place instead of coordinates
    python scripts/campsite_finder.py near --from "McCall, ID" --radius 50 \
        --start 2026-08-28 --nights 2

No API key required. Be polite: the script sleeps between calls.
"""

import argparse
import calendar
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

BASE = "https://www.recreation.gov/api"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
SLEEP = 0.4  # be kind to the endpoint


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

def _get(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as exc:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
            last = exc
    raise last


def search_campgrounds(query, size=10, lat=None, lon=None, radius=None):
    """Find facilities by free text, optionally constrained to a radius."""
    params = {"entity_type": "campground", "size": str(size)}
    if query:
        params["q"] = query
    if lat is not None and lon is not None:
        params.update({"lat": str(lat), "lng": str(lon)})
        if radius:
            params["radius"] = str(radius)
    url = f"{BASE}/search?{urllib.parse.urlencode(params)}"
    return _get(url).get("results", [])


def geocode(place):
    """Resolve a place name to (lat, lon) using recreation.gov's own geocoder."""
    url = f"{BASE}/search/geocoder?{urllib.parse.urlencode({'q': place})}"
    try:
        hits = _get(url)
    except Exception:
        hits = None
    if isinstance(hits, list) and hits:
        h = hits[0]
        return float(h["lat"]), float(h["lng"]), h.get("name", place)
    # fall back: search for anything near that name and borrow its coordinates
    res = search_campgrounds(place, size=1)
    if res:
        return float(res[0]["latitude"]), float(res[0]["longitude"]), place
    raise SystemExit(f"Could not locate '{place}'. Pass --lat/--lon instead.")


def campsite_metadata(facility_id):
    url = f"{BASE}/camps/campgrounds/{facility_id}/campsites"
    return _get(url).get("campsites", [])


def month_availability(facility_id, year, month):
    start = f"{year:04d}-{month:02d}-01T00:00:00.000Z"
    url = (
        f"{BASE}/camps/availability/campground/{facility_id}/month"
        f"?start_date={urllib.parse.quote(start)}"
    )
    return _get(url).get("campsites", {})


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #

def _keys_for(nights):
    return [f"{d.isoformat()}T00:00:00Z" for d in nights]


def _month_keys(year, month):
    days = calendar.monthrange(year, month)[1]
    return [f"{year:04d}-{month:02d}-{d:02d}T00:00:00Z" for d in range(1, days + 1)]


def analyze(facility_id, nights, name=None):
    """
    Return a dict describing bookable vs walk-up inventory for `nights`
    (a list of date objects, each one a night you want to sleep there).
    """
    months = sorted({(d.year, d.month) for d in nights})
    avail = {}
    for (y, m) in months:
        try:
            avail.update(month_availability(facility_id, y, m))
        except Exception as exc:
            return {"id": facility_id, "name": name, "error": str(exc)}
        time.sleep(SLEEP)

    try:
        meta = campsite_metadata(facility_id)
    except Exception:
        meta = []
    time.sleep(SLEEP)

    want = _keys_for(nights)
    # month keys for the first requested month, used to spot always-walk-up sites
    ref_month = _month_keys(nights[0].year, nights[0].month)

    scan_and_pay = 0
    open_sites, booked, fcfs, unknown = [], 0, 0, 0

    by_id = {s.get("campsite_id"): s for s in meta}
    ids = set(avail) | set(by_id)

    for sid in ids:
        info = by_id.get(sid, {})
        ctype = info.get("campsite_type", "")
        if ctype == "MANAGEMENT":
            # "Scan and Pay" placeholders: strong signal the site takes walk-ups
            scan_and_pay += 1
            continue

        a = avail.get(sid, {}).get("availabilities", {})
        if not a:
            continue
        vals = [a.get(k) for k in want]

        if all(v == "Available" for v in vals):
            open_sites.append(info.get("campsite_name") or sid)
        elif any(v == "Reserved" for v in vals):
            booked += 1
        elif all(v == "Not Reservable" for v in vals):
            month_vals = {a.get(k) for k in ref_month if a.get(k)}
            if month_vals == {"Not Reservable"}:
                fcfs += 1        # held out of the system all month -> walk-up
            else:
                unknown += 1     # seasonal / closed / partially released
        else:
            unknown += 1

    return {
        "id": facility_id,
        "name": name,
        "open": len(open_sites),
        "open_sites": sorted(map(str, open_sites)),
        "booked": booked,
        "fcfs": fcfs,
        "unknown": unknown,
        "scan_and_pay": scan_and_pay,
        "total": len(open_sites) + booked + fcfs + unknown,
    }


def nights_from(start, count):
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    return [d0 + timedelta(days=i) for i in range(count)]


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def print_table(rows, nights):
    span = f"{nights[0].isoformat()} .. {nights[-1].isoformat()}"
    print(f"\nAvailability for {len(nights)} night(s): {span}")
    print(f"Checked {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    hdr = f"{'CAMPGROUND':34s} {'ID':>9s} {'OPEN':>5s} {'BOOKED':>7s} {'WALK-UP':>8s} {'?':>4s}"
    print(hdr)
    print("-" * len(hdr))

    rows = sorted(
        rows,
        key=lambda r: (-(r.get("open") or 0), -(r.get("fcfs") or 0), r.get("name") or ""),
    )
    for r in rows:
        if r.get("error"):
            print(f"{(r.get('name') or r['id'])[:34]:34s} {r['id']:>9s}   ERROR  {r['error'][:30]}")
            continue
        star = " *" if r["scan_and_pay"] else ""
        print(
            f"{(r.get('name') or '')[:34]:34s} {r['id']:>9s} "
            f"{r['open']:5d} {r['booked']:7d} {r['fcfs']:8d} {r['unknown']:4d}{star}"
        )

    print("\nOPEN     = bookable right now for every requested night")
    print("BOOKED   = reserved by someone else")
    print("WALK-UP  = held out of the booking system all month -> first-come, first-served")
    print("?        = seasonal, closed, or not yet released")
    print("*        = campground has 'Scan and Pay' sites (pay on arrival via the rec.gov app)")

    best = [r for r in rows if not r.get("error") and r["open"]]
    if best:
        top = best[0]
        print(f"\nBookable now: {top['name']} - sites {', '.join(top['open_sites'][:10])}")
    walk = [r for r in rows if not r.get("error") and r["fcfs"] >= 5]
    if walk:
        print("\nStrong walk-up odds (5+ first-come sites):")
        for r in walk[:6]:
            print(f"  {r['fcfs']:3d} sites  {r['name']}")
        print("  -> arrive early Friday; checkout is 11:00 AM and sites turn over then.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    p = argparse.ArgumentParser(
        description="Query recreation.gov for real campsite availability, "
                    "including the walk-up inventory the website hides."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="find facility IDs by name")
    s.add_argument("query")
    s.add_argument("--size", type=int, default=10)

    c = sub.add_parser("check", help="check specific facility IDs")
    c.add_argument("ids", nargs="+")
    c.add_argument("--start", required=True, help="first night, YYYY-MM-DD")
    c.add_argument("--nights", type=int, default=2)
    c.add_argument("--json", action="store_true")

    n = sub.add_parser("near", help="sweep every campground near a point")
    n.add_argument("--lat", type=float)
    n.add_argument("--lon", type=float)
    n.add_argument("--from", dest="place", help='e.g. "McCall, ID"')
    n.add_argument("--radius", type=int, default=50, help="miles")
    n.add_argument("--start", required=True)
    n.add_argument("--nights", type=int, default=2)
    n.add_argument("--limit", type=int, default=25, help="max campgrounds to check")
    n.add_argument("--json", action="store_true")

    a = p.parse_args()

    if a.cmd == "search":
        for r in search_campgrounds(a.query, size=a.size):
            print(
                f"{r.get('entity_id'):>10} | {r.get('name')} "
                f"| {r.get('city')}, {r.get('state_code')} "
                f"| {r.get('campsites_count')} sites"
            )
        return

    nights = nights_from(a.start, a.nights)

    if a.cmd == "check":
        rows = []
        for fid in a.ids:
            r = analyze(fid, nights)
            if not r.get("name"):
                try:
                    meta = _get(f"{BASE}/camps/campgrounds/{fid}")
                    r["name"] = meta.get("campground", {}).get("facility_name", fid)
                except Exception:
                    r["name"] = fid
            rows.append(r)
    else:
        if a.place:
            lat, lon, label = geocode(a.place)
            print(f"Searching within {a.radius} mi of {label} ({lat:.4f}, {lon:.4f})")
        elif a.lat is not None and a.lon is not None:
            lat, lon = a.lat, a.lon
        else:
            raise SystemExit("Pass --from PLACE or both --lat and --lon.")

        found = search_campgrounds("", size=a.limit, lat=lat, lon=lon, radius=a.radius)
        if not found:
            raise SystemExit("No campgrounds returned for that area.")
        print(f"Found {len(found)} campgrounds; checking availability...\n")
        rows = []
        for f in found[: a.limit]:
            fid = str(f.get("entity_id"))
            nm = f.get("name") or fid
            sys.stderr.write(f"  checking {nm}\r")
            rows.append(analyze(fid, nights, name=nm))
        sys.stderr.write(" " * 60 + "\r")

    if getattr(a, "json", False):
        print(json.dumps(rows, indent=2))
    else:
        print_table(rows, nights)


if __name__ == "__main__":
    main()
