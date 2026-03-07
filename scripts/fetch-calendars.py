#!/usr/bin/env python3
"""
fetch-calendars.py — Almond Farm calendar data fetcher
=======================================================

Pulls ICS feeds from MLB and Google Calendar, filters to a target year,
and writes data/baked_calendars.json for Hugo to bake into the calendar page.

USAGE
-----
  cd <repo-root>
  python3 scripts/fetch-calendars.py            # defaults to current year
  python3 scripts/fetch-calendars.py --year 2027  # next season

Then commit the updated data/baked_calendars.json and push.

HOW TO UPDATE EACH NEW YEAR
----------------------------
1. Run this script in January/February once MLB releases the schedule:
     python3 scripts/fetch-calendars.py --year 2027

2. Check the output:
     cat data/baked_calendars.json | python3 -m json.tool | head -40

3. Commit and push:
     git add data/baked_calendars.json
     git commit -m "Refresh 2027 calendar data"
     git push

4. Merge the PR — the site rebuilds automatically.

The calendar page will always show live personal events from
data/calendar_events.yaml (no script needed for those — just edit the YAML).

FEEDS
-----
- US Holidays: Google Calendar public ICS (no auth required)
- Yankees / Mets / Dodgers: mlb.com public ICS feeds

If an MLB team changes its ICS URL, update the FEEDS list below.
MLB ICS URLs historically follow: https://www.mlb.com/<team-slug>/schedule/list.ics
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

FEEDS = [
    {
        "name": "US Holidays",
        "url": "https://calendar.google.com/calendar/ical/en.usa%23holiday%40group.v.calendar.google.com/public/basic.ics",
        "color": "#D4AF37",
        "textColor": "#0A0A0A",
    },
    {
        "name": "Yankees",
        "url": "https://www.mlb.com/yankees/schedule/list.ics",
        "color": "#003087",
        "textColor": "#ffffff",
    },
    {
        "name": "Mets",
        "url": "https://www.mlb.com/mets/schedule/list.ics",
        "color": "#FF5910",
        "textColor": "#ffffff",
    },
    {
        "name": "Dodgers",
        "url": "https://www.mlb.com/dodgers/schedule/list.ics",
        "color": "#005A9C",
        "textColor": "#ffffff",
    },
]

OUTPUT_FILE = Path(__file__).parent.parent / "data" / "baked_calendars.json"


# ── ICS fetch ──────────────────────────────────────────────────────────────────

def fetch_ics(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ── ICS parser ─────────────────────────────────────────────────────────────────

def unfold(text: str) -> str:
    """Remove ICS line folding (continuation lines start with a space/tab)."""
    return re.sub(r"\r?\n[ \t]", "", text)


def parse_dt(value: str):
    """
    Parse an ICS DTSTART/DTEND value.
    Returns (iso_string, all_day_bool) or (None, None) on failure.
    """
    value = value.strip()
    if re.match(r"^\d{8}$", value):
        # All-day: YYYYMMDD
        d = datetime.strptime(value, "%Y%m%d")
        return d.strftime("%Y-%m-%d"), True
    if re.match(r"^\d{8}T\d{6}Z$", value):
        # UTC timed: YYYYMMDDTHHmmssZ
        d = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return d.strftime("%Y-%m-%dT%H:%M:%SZ"), False
    if re.match(r"^\d{8}T\d{6}$", value):
        # Local timed: YYYYMMDDTHHmmss
        d = datetime.strptime(value, "%Y%m%dT%H%M%S")
        return d.strftime("%Y-%m-%dT%H:%M:%S"), False
    return None, None


def shorten_mlb(title: str) -> str:
    """Condense verbose MLB game titles to fit calendar cells."""
    return (
        title
        .replace("New York Yankees", "NYY")
        .replace("New York Mets", "NYM")
        .replace("Los Angeles Dodgers", "LAD")
        .replace("Los Angeles Angels", "LAA")
        .replace("Boston Red Sox", "BOS")
        .replace("Houston Astros", "HOU")
        .replace("Chicago Cubs", "CHC")
        .replace("Chicago White Sox", "CWS")
        .replace("San Francisco Giants", "SF")
        .replace("San Diego Padres", "SD")
        .replace("Atlanta Braves", "ATL")
        .replace("Philadelphia Phillies", "PHI")
        .replace(" at ", " @ ")
        .replace(" vs. ", " vs ")
    )


def parse_ics(text: str, feed: dict, year: int) -> list:
    text = unfold(text)
    events = []
    in_vevent = False
    current = {}

    for line in text.splitlines():
        line = line.rstrip("\r")

        if line == "BEGIN:VEVENT":
            in_vevent = True
            current = {}
            continue

        if line == "END:VEVENT":
            in_vevent = False
            summary = current.get("SUMMARY", "")
            dtstart_raw = current.get("DTSTART", "")
            dtend_raw = current.get("DTEND", "")

            start_iso, all_day = parse_dt(dtstart_raw)
            end_iso, _ = parse_dt(dtend_raw) if dtend_raw else (None, None)

            if not start_iso:
                continue

            # Filter to target year only
            if not start_iso.startswith(str(year)):
                continue

            is_mlb = feed["name"] in ("Yankees", "Mets", "Dodgers")
            title = shorten_mlb(summary) if is_mlb else summary

            ev = {
                "title": title,
                "start": start_iso,
                "allDay": all_day,
                "backgroundColor": feed["color"],
                "borderColor": feed["color"],
                "textColor": feed["textColor"],
                "extendedProps": {"source": feed["name"]},
            }
            if end_iso:
                ev["end"] = end_iso
            events.append(ev)
            continue

        if not in_vevent:
            continue

        # Parse property lines: KEY or KEY;params:value
        m = re.match(r"^([A-Z\-]+)(?:;[^:]+)?:(.*)$", line)
        if m:
            current[m.group(1)] = m.group(2)

    return events


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch calendar ICS feeds → data/baked_calendars.json")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Year to filter events to (default: current year)")
    args = parser.parse_args()

    year = args.year
    print(f"Fetching {year} events from {len(FEEDS)} feeds...\n")

    all_events = []

    for feed in FEEDS:
        print(f"  [{feed['name']}] {feed['url']}")
        try:
            ics_text = fetch_ics(feed["url"])
            events = parse_ics(ics_text, feed, year)
            all_events.extend(events)
            print(f"    ✓ {len(events)} events for {year}")
        except Exception as e:
            print(f"    ✗ FAILED: {e}", file=sys.stderr)

    print(f"\nTotal: {len(all_events)} events")

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_events, f, indent=2)

    print(f"Written → {OUTPUT_FILE.relative_to(Path(__file__).parent.parent)}")
    print()
    print("Next steps:")
    print("  git add data/baked_calendars.json")
    print(f"  git commit -m 'Bake {year} calendar data'")
    print("  git push")


if __name__ == "__main__":
    main()
