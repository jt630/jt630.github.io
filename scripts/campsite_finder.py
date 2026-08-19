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
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

BASE = "https://www.recreation.gov/api"
OSRM = "https://router.project-osrm.org/route/v1/driving"

# Phrases in the Forest Service's own directions/description text that mean the
# last stretch is not a highway. Ordered roughly worst-first.
ROAD_FLAGS = [
    ("4-wheel drive", "4WD"), ("four-wheel drive", "4WD"), ("4wd", "4WD"),
    ("high clearance", "HIGH-CLEARANCE"), ("high-clearance", "HIGH-CLEARANCE"),
    ("not recommended", "NOT RECOMMENDED"),
    ("primitive road", "PRIMITIVE"), ("rough", "ROUGH"),
    ("single lane", "1-LANE"), ("one lane", "1-LANE"),
    ("narrow", "NARROW"), ("steep", "STEEP"), ("winding", "WINDING"),
    ("not suitable for trailers", "NO TRAILERS"),
    ("discourage", "NO TRAILERS"),
    ("unpaved", "UNPAVED"), ("gravel", "GRAVEL"), ("dirt", "DIRT"),
    ("native surface", "DIRT"),
]

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

# As of 2026-08-18 the public OSRM demo server is serving an EXPIRED TLS
# certificate, so drive-time lookups fail with CERTIFICATE_VERIFY_FAILED.
#
# We do NOT silently work around that. Verification stays on everywhere by
# default; if OSRM's cert is bad you simply get no drive times, and the rest of
# the tool still works. Passing --insecure-routing relaxes verification for the
# OSRM host ONLY (an unauthenticated routing demo that receives nothing but a
# pair of coordinates). Recreation.gov always keeps full verification.
ALLOW_INSECURE_ROUTING = False

_INSECURE = ssl.create_default_context()
_INSECURE.check_hostname = False
_INSECURE.verify_mode = ssl.CERT_NONE


def _get(url, retries=3):
    ctx = _INSECURE if (ALLOW_INSECURE_ROUTING and url.startswith(OSRM)) else None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
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


def strip_html(s):
    out, depth = [], 0
    for ch in s or "":
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return " ".join("".join(out).split())


def facility_detail(facility_id):
    """Coordinates, official directions, and road-quality warnings."""
    try:
        d = _get(f"{BASE}/camps/campgrounds/{facility_id}").get("campground", {})
    except Exception:
        return {}

    text_parts = [strip_html(d.get("facility_directions", ""))]
    dm = d.get("facility_description_map") or {}
    if isinstance(dm, dict):
        for v in dm.values():
            text_parts.append(strip_html(v))
    text_parts.append(strip_html(d.get("facility_description", "")))
    blob = " ".join(text_parts).lower()

    flags = []
    for needle, label in ROAD_FLAGS:
        if needle in blob and label not in flags:
            flags.append(label)

    rules = d.get("facility_rules") or {}
    return {
        "lat": d.get("facility_latitude"),
        "lon": d.get("facility_longitude"),
        "directions": strip_html(d.get("facility_directions", "")),
        "road_flags": flags,
        "scan_and_pay": bool(rules.get("scanAndPay")),
        "phone": d.get("facility_phone"),
    }


_ROUTING_WARNED = []


def drive_from(origin, lat, lon):
    """
    Real driving distance/time via the public OSRM server. No API key.

    Returns None if routing is unavailable (expired cert, server down, no route).
    Callers must treat drive time as optional, never assume it.
    """
    if lat is None or lon is None or origin is None:
        return None
    olat, olon = origin
    url = f"{OSRM}/{olon},{olat};{lon},{lat}?overview=false"
    try:
        d = _get(url, retries=1)
        if d.get("code") != "Ok" or not d.get("routes"):
            return None
        r = d["routes"][0]
        return {"miles": r["distance"] / 1609.34, "hours": r["duration"] / 3600.0}
    except Exception as exc:
        if not _ROUTING_WARNED:
            _ROUTING_WARNED.append(True)
            msg = str(exc)
            if "CERTIFICATE_VERIFY_FAILED" in msg:
                sys.stderr.write(
                    "\n[routing unavailable] The public OSRM server's TLS certificate\n"
                    "is expired, so drive times are omitted. Re-run with\n"
                    "--insecure-routing to accept it for that host only, or read the\n"
                    "ROAD column and the campground's official directions instead.\n\n"
                )
            else:
                sys.stderr.write(f"\n[routing unavailable] {msg[:90]}\n\n")
        return None


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


def analyze(facility_id, nights, name=None, origin=None):
    """
    Return a dict describing bookable vs walk-up inventory for `nights`
    (a list of date objects, each one a night you want to sleep there).

    If `origin` is an (lat, lon) tuple, also resolve real driving distance and
    time, plus any road-quality warnings from the Forest Service's own text.
    Straight-line radius is close to meaningless in mountain country.
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

    detail = facility_detail(facility_id)
    time.sleep(SLEEP)
    drive = drive_from(origin, detail.get("lat"), detail.get("lon")) if origin else None
    if drive:
        time.sleep(SLEEP)

    return {
        "id": facility_id,
        "name": name,
        "open": len(open_sites),
        "open_sites": sorted(map(str, open_sites)),
        "booked": booked,
        "fcfs": fcfs,
        "unknown": unknown,
        # the explicit API flag beats the MANAGEMENT-site heuristic when present
        "scan_and_pay": scan_and_pay or (1 if detail.get("scan_and_pay") else 0),
        "total": len(open_sites) + booked + fcfs + unknown,
        "road_flags": detail.get("road_flags", []),
        "directions": detail.get("directions", ""),
        "drive_hours": drive["hours"] if drive else None,
        "drive_miles": drive["miles"] if drive else None,
    }


def nights_from(start, count):
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    return [d0 + timedelta(days=i) for i in range(count)]


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def print_table(rows, nights, origin_label=None, depart=None):
    span = f"{nights[0].isoformat()} .. {nights[-1].isoformat()}"
    print(f"\nAvailability for {len(nights)} night(s): {span}")
    print(f"Checked {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if origin_label:
        print(f"Drive times from {origin_label}")
    print()

    has_drive = any(r.get("drive_hours") for r in rows)
    hdr = f"{'CAMPGROUND':30s} {'OPEN':>4s} {'BKD':>4s} {'WALK':>5s} {'?':>3s}"
    if has_drive:
        hdr += f" {'DRIVE':>7s} {'MILES':>6s}"
    hdr += "  ROAD"
    print(hdr)
    print("-" * max(len(hdr), 74))

    def sort_key(r):
        # nearest first when we know drive times; that is the number that matters
        return (r.get("drive_hours") if r.get("drive_hours") is not None else 99,
                -(r.get("open") or 0), -(r.get("fcfs") or 0))

    rows = sorted(rows, key=sort_key)
    for r in rows:
        if r.get("error"):
            print(f"{(r.get('name') or r['id'])[:30]:30s}  ERROR {r['error'][:34]}")
            continue
        line = (f"{(r.get('name') or '')[:30]:30s} "
                f"{r['open']:4d} {r['booked']:4d} {r['fcfs']:5d} {r['unknown']:3d}")
        if has_drive:
            dh = r.get("drive_hours")
            dm = r.get("drive_miles")
            line += f" {dh:6.2f}h {dm:6.0f}" if dh else f" {'--':>7s} {'--':>6s}"
        flags = list(r.get("road_flags") or [])
        if r.get("scan_and_pay"):
            flags.append("SCAN&PAY")
        line += "  " + " ".join(flags[:4])
        print(line)

    print("\nOPEN  = bookable right now for every requested night")
    print("BKD   = reserved by someone else")
    print("WALK  = held out of the booking system all month -> first-come, first-served")
    print("?     = seasonal, closed, or not yet released")
    if has_drive:
        print("DRIVE = real routed driving time, not straight-line distance")
    print("ROAD  = warnings pulled from the Forest Service's own directions text")
    print("        GRAVEL/DIRT/NARROW/STEEP/ROUGH/HIGH-CLEARANCE/4WD/NO TRAILERS")
    print("        SCAN&PAY = pay on arrival via the rec.gov app (download it first)")

    if depart and has_drive:
        print(f"\nLeaving at {depart}, you would arrive:")
        try:
            t0 = datetime.strptime(depart, "%H:%M")
        except ValueError:
            t0 = None
        if t0:
            for r in rows[:8]:
                dh = r.get("drive_hours")
                if not dh:
                    continue
                eta = t0 + timedelta(hours=dh)
                warn = "  <-- after dark / too late for walk-up" if eta.hour >= 17 else ""
                print(f"  {eta.strftime('%H:%M')}  {r['name'][:34]}{warn}")

    best = [r for r in rows if not r.get("error") and r["open"]]
    if best:
        top = best[0]
        print(f"\nClosest bookable: {top['name']} - sites {', '.join(top['open_sites'][:10])}")
    walk = [r for r in rows if not r.get("error") and r["fcfs"] >= 5]
    if walk:
        print("\nStrong walk-up odds (5+ first-come sites), nearest first:")
        for r in walk[:6]:
            dh = f"{r['drive_hours']:.1f}h  " if r.get("drive_hours") else ""
            rd = f"  [{', '.join(r['road_flags'][:3])}]" if r.get("road_flags") else ""
            print(f"  {r['fcfs']:3d} sites  {dh}{r['name']}{rd}")
        print("  -> checkout is 11:00 AM; early arrival catches the turnover.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    p = argparse.ArgumentParser(
        description="Query recreation.gov for real campsite availability, "
                    "including the walk-up inventory the website hides."
    )
    p.add_argument(
        "--insecure-routing",
        action="store_true",
        help="accept the public OSRM demo server's expired certificate so drive "
             "times work. Affects that one routing host only; recreation.gov "
             "always keeps full TLS verification.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="find facility IDs by name")
    s.add_argument("query")
    s.add_argument("--size", type=int, default=10)

    c = sub.add_parser("check", help="check specific facility IDs")
    c.add_argument("ids", nargs="+")
    c.add_argument("--start", required=True, help="first night, YYYY-MM-DD")
    c.add_argument("--nights", type=int, default=2)
    c.add_argument("--origin", help='drive times from here, "lat,lon"')
    c.add_argument("--depart", help='departure time, "HH:MM", to show arrival times')
    c.add_argument("--json", action="store_true")

    n = sub.add_parser("near", help="sweep every campground near a point")
    n.add_argument("--lat", type=float)
    n.add_argument("--lon", type=float)
    n.add_argument("--from", dest="place", help='e.g. "McCall, ID"')
    n.add_argument("--radius", type=int, default=50, help="miles")
    n.add_argument("--start", required=True)
    n.add_argument("--nights", type=int, default=2)
    n.add_argument("--limit", type=int, default=25, help="max campgrounds to check")
    n.add_argument("--origin", help='drive times from here, "lat,lon" (defaults to search centre)')
    n.add_argument("--max-drive", type=float, help="hide anything over this many driving hours")
    n.add_argument("--depart", help='departure time, "HH:MM", to show arrival times')
    n.add_argument("--json", action="store_true")

    a = p.parse_args()

    global ALLOW_INSECURE_ROUTING
    ALLOW_INSECURE_ROUTING = bool(getattr(a, "insecure_routing", False))

    if a.cmd == "search":
        for r in search_campgrounds(a.query, size=a.size):
            print(
                f"{r.get('entity_id'):>10} | {r.get('name')} "
                f"| {r.get('city')}, {r.get('state_code')} "
                f"| {r.get('campsites_count')} sites"
            )
        return

    nights = nights_from(a.start, a.nights)

    def parse_origin(s):
        if not s:
            return None, None
        try:
            la, lo = [float(x) for x in s.split(",")]
            return (la, lo), s
        except ValueError:
            raise SystemExit('--origin must look like "43.6150,-116.2023"')

    if a.cmd == "check":
        origin, origin_label = parse_origin(a.origin)
        rows = []
        for fid in a.ids:
            r = analyze(fid, nights, origin=origin)
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

        origin, origin_label = parse_origin(a.origin)
        if origin is None:
            origin, origin_label = (lat, lon), f"{lat:.4f},{lon:.4f}"

        found = search_campgrounds("", size=a.limit, lat=lat, lon=lon, radius=a.radius)
        if not found:
            raise SystemExit("No campgrounds returned for that area.")
        print(f"Found {len(found)} campgrounds; checking availability and drive times...\n")
        rows = []
        for f in found[: a.limit]:
            fid = str(f.get("entity_id"))
            nm = f.get("name") or fid
            sys.stderr.write(f"  checking {nm[:40]:42s}\r")
            rows.append(analyze(fid, nights, name=nm, origin=origin))
        sys.stderr.write(" " * 60 + "\r")

        if a.max_drive:
            kept = [r for r in rows
                    if r.get("drive_hours") is None or r["drive_hours"] <= a.max_drive]
            dropped = len(rows) - len(kept)
            if dropped:
                print(f"({dropped} campground(s) hidden as over {a.max_drive}h drive)")
            rows = kept

    if getattr(a, "json", False):
        print(json.dumps(rows, indent=2))
    else:
        print_table(rows, nights, origin_label=origin_label,
                    depart=getattr(a, "depart", None))


if __name__ == "__main__":
    main()
