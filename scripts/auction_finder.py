#!/usr/bin/env python3
"""
auction_finder.py - pull live lots from Boise-metro government/police surplus
auctions across multiple platforms, filter to Treasure Valley agencies, and
write one ranked YAML that content/auctions.md renders.

Sources
-------
1. PublicSurplus.com  - most Idaho city/county/PD auctions (Boise PD, Ada
   County, Meridian, Nampa PD, Idaho State Police) run through this platform.
2. GovDeals.com       - larger municipal/county surplus, some ID agencies.
3. Municibid.com      - zip-radius search around Boise (83702); picks up
   smaller cities that don't show up on a keyword search.
4. PropertyRoom.com   - police/sheriff evidence & seized-property auctions.
5. MusickAuction.com  - Nampa-based Idaho auction house that runs a lot of
   the actual Treasure Valley law-enforcement/government sales in person
   (Jeremy's grandpa's usual circuit). Domain is a best guess (see below) -
   confirm/correct it if it's wrong.

Each platform gets a search URL per agency term (see AGENCY_TERMS). Parsing
tries, in order:
  1. embedded schema.org JSON-LD (<script type="application/ld+json">) -
     the most stable signal available, since it exists for Google rich
     snippets rather than for us, so it's less likely to break on a
     redesign than a hand-picked CSS class would be.
  2. give up cleanly on that (platform, term) and log a note - never raise,
     never fabricate a row.

IMPORTANT - unverified against live markup. This was written in a sandboxed
dev session whose network policy blocks all five of these domains outright
(confirmed via the egress proxy status, not guessed), so none of this has
been run against real HTML. musickauction.com specifically is also an
unverified *domain guess* (inferred from "musick" + Boise/police-auction
context, not looked up) - if that's not the real site, fix MUSICK_BASE
below. Treat the parsers as informed first drafts, the
same starting point car_finder.py had for Craigslist/Cars.com before a few
real runs shook out the actual markup. First live run should be the
`auction-monitor` GitHub Action's `workflow_dispatch` (a GH-hosted runner has
open internet) - read its job log's fetch notes, and if a platform reports
"0 rows (no json-ld found...)" on every term, that platform needs a
follow-up pass with a platform-specific regex added to `PLATFORM_FALLBACK`
below, informed by what the log/a manual page-view shows.

A second, separate concern: any of these five sites' Terms of Service may
restrict automated access. This fetches public search-result / listing
pages at a polite rate (one request per SLEEP seconds, browser User-Agent,
no login) for personal, non-commercial monitoring - the same posture as
this repo's existing car_finder.py - but it's worth a read of each site's
ToS before leaning on this long-term, and backing off (or dropping a
platform) if a site pushes back. Musick is a small local business, not a
national platform, so this is worth double-checking there in particular -
if scraping their site isn't welcome, drop "musick" from PLATFORMS and
just check it by hand.

Geo filter: agency/title/description text must mention a Treasure Valley
city or county (Boise, Meridian, Eagle, Nampa, Caldwell, Garden City, Kuna,
Star, Ada County, Canyon County, ...) - rows with no local signal are
dropped rather than kept-by-default, since these searches aren't reliably
geo-scoped the way car_finder's Craigslist search is. Musick is exempt from
this filter - being listed on a Nampa, ID auction house's own site already
is the local signal, and its lots won't reliably repeat a city name in
their title/description the way a national platform's do.

Category: every lot is keyword-classified into a broad bucket (Small
Engines & Appliances, Heavy Equipment, Vehicles, Firearms, Electronics,
Jewelry & Valuables, Tools & Equipment, Bikes & Recreation, Office &
Furniture, Other) - see CATEGORY_KEYWORDS / guess_category(). /auctions/
gives Vehicles its own section up top and groups everything else by
category below it, so the categories a casual bidder skims past don't get
buried in one long list. Small Engines & Appliances additionally gets its
own dedicated page at /grandpas-shop/ (content/grandpas-shop.md +
layouts/grandpas-shop/single.html) - vacuums, mowers, chainsaws, washers,
dryers, generators, the stuff Jeremy's grandpa actually repairs.

Usage
-----
    python scripts/auction_finder.py             # fetch, filter, write YAML
    python scripts/auction_finder.py --dry-run    # print, don't write

Output: data/auction_lots.yaml. estimated_value_* / deal_score / ai_note are
left null here - run scripts/auction_value.py afterward to fill those in
with an AI resale estimate.
"""

import argparse
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from musick_render import BLOCK_NOTE, looks_blocked  # noqa: E402 - stdlib-only module

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
SLEEP = 2.0

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "..", "data", "auction_lots.yaml")
CACHE_DIR = os.path.join(_HERE, "..", "data", ".cache")
WATCHLIST_PATH = os.path.join(_HERE, "..", "data", "auction_watchlist.yaml")
ZIP = "83702"  # Boise

# Narrowed to Musick alone by request: it's the one platform tied to
# Jeremy's grandpa's actual auction circuit (a Nampa, ID auction house, not
# a national platform). The other four keep their working fetch/parse code
# in _DISABLED_PLATFORMS below - add any back to PLATFORMS to re-enable.
PLATFORMS = ("musick",)
_DISABLED_PLATFORMS = ("publicsurplus", "govdeals", "municibid", "propertyroom")

# Musick Auction Co. (Nampa, ID) isn't a national keyword-search platform -
# it's a single local auctioneer, so instead of searching per agency term
# (like the other four) it just gets a handful of listing pages scanned
# once. CONFIRMED against real markup 2026-09-21 (domain, paths, and the
# query-row parser below all verified via a live GitHub Actions run whose
# raw HTML landed on the debug/auction-html branch - see
# docs/AUCTION-MONITORING.md). musickauction.com is a WordPress/Divi
# marketing site; "/current-auctions", "/online-auctions", and
# "/law-enforcement" all 404 - there's no such page, "Current Auctions" in
# the nav just points at "/auctions/".
MUSICK_BASE = "https://www.musickauction.com"
# "/" (homepage) has no events at all; "/auctions" and "/upcoming-auctions"
# both embed the identical event-list widget (redundant but cheap, and a
# fallback if one page's structure ever changes independently of the other).
MUSICK_PATHS = ["/auctions", "/upcoming-auctions"]

# Agencies whose auctions are worth searching for by name (police auctions
# are the deep ones - Boise PD and Ada County both run big multi-lot sales).
AGENCY_TERMS = [
    "Boise Police Department",
    "City of Boise",
    "Ada County",
    "City of Meridian",
    "Meridian Police Department",
    "Canyon County",
    "City of Nampa",
    "Nampa Police Department",
    "Idaho State Police",
    "City of Caldwell",
    "City of Garden City",
    "City of Eagle",
]

# Recognize an agency from lot title/description text, for display.
AGENCY_LABELS = [
    ("boise police", "Boise Police Department"),
    ("meridian police", "Meridian Police Department"),
    ("city of meridian", "City of Meridian"),
    ("ada county", "Ada County"),
    ("canyon county", "Canyon County"),
    ("nampa police", "Nampa Police Department"),
    ("city of nampa", "City of Nampa"),
    ("idaho state police", "Idaho State Police"),
    ("city of boise", "City of Boise"),
    ("boise, id", "City of Boise"),
    ("city of caldwell", "City of Caldwell"),
    ("garden city", "Garden City"),
    ("city of eagle", "City of Eagle"),
]

# Treasure Valley signal - a lot must mention one of these somewhere in its
# agency/title/description/url to be kept.
NEAR = [
    "boise", "meridian", "eagle", "nampa", "caldwell", "garden city", "kuna",
    "star", "middleton", "emmett", "mountain home", "ada county",
    "canyon county", "treasure valley", "idaho",
]

# Broad category buckets, keyword-matched against title+description.
# "Vehicles" and "Small Engines & Appliances" each get their own section /
# dedicated page (the two things Jeremy's grandpa actually wants to check -
# he fixes small engines and appliances, mostly vacuums, on top of already
# running the Meridian car-auction circuit); everything else groups by
# category so the categories a casual bidder skims past - tools,
# electronics, jewelry, unclaimed property - don't get buried in one giant
# undifferentiated list. Order matters: first match wins, so more specific
# buckets (Small Engines & Appliances, Firearms) come before generic ones,
# and mower/generator/chainsaw/etc. deliberately live ONLY here, not in
# Heavy Equipment or Tools & Equipment, so grandpa's page doesn't miss them.
CATEGORY_KEYWORDS = [
    ("Small Engines & Appliances", [
        "vacuum", "shop vac", "dyson", "shark", "bissell", "hoover", "kirby",
        "riccar", "oreck", "washer", "dryer", "washing machine",
        "dishwasher", "refrigerator", "fridge", "freezer", "microwave",
        "garbage disposal", "lawn mower", "push mower", "riding mower",
        "mower", "chainsaw", "leaf blower", "snow blower", "weed eater",
        "string trimmer", "hedge trimmer", "pressure washer", "generator",
        "small engine", "tiller", "rototiller", "edger",
    ]),
    ("Heavy Equipment", [
        "tractor", "excavator", "backhoe", "forklift", "loader",
        "skid steer", "dump truck", "bucket truck", "trailer",
    ]),
    ("Vehicles", [
        "car", "truck", "vehicle", "sedan", "suv", "pickup", "motorcycle", "atv", "utv",
        "coupe", "ford", "chevy", "chevrolet", "toyota", "honda", "dodge",
        "jeep", "gmc", "nissan", "subaru", "mustang", "silverado", "tahoe",
        "explorer", "wrangler", "charger", "impala", "camry", "accord",
        "civic", "cargo van", "minivan", "vin", "odometer", "mileage",
        "4x4", "awd", "sedan", "hatchback", "pickup truck",
    ]),
    ("Firearms", [
        "rifle", "pistol", "shotgun", "firearm", "ammo", "ammunition", "gun",
    ]),
    ("Electronics", [
        "laptop", "computer", "tablet", "iphone", "smartphone", "camera",
        "television", "tv", "monitor", "gps", "drone", "gaming console",
        "playstation", "xbox",
    ]),
    ("Jewelry & Valuables", [
        "ring", "necklace", "bracelet", "watch", "gold", "silver",
        "diamond", "jewelry", "coin collection",
    ]),
    ("Tools & Equipment", [
        "drill", "table saw", "toolbox", "tool set", "air compressor",
        "welder", "ladder", "power tool",
    ]),
    ("Bikes & Recreation", [
        "bicycle", "bike", "kayak", "canoe", "paddleboard", "scooter",
        "skateboard",
    ]),
    ("Office & Furniture", ["desk", "office chair", "file cabinet", "furniture"]),
]


def guess_category(lot):
    s = f" {lot.get('title', '')} {lot.get('description', '')} ".lower()
    for label, needles in CATEGORY_KEYWORDS:
        # \b...s?\b: word-boundary match with an optional trailing "s", so
        # "car"/"truck"/"excavator" also catch "cars"/"trucks"/"excavators"
        # without matching inside unrelated words ("scar", "cargo") the way
        # a plain substring check would.
        if any(re.search(r"\b" + re.escape(n) + r"s?\b", s) for n in needles):
            return label
    return "Other"


def load_watchlist():
    """data/auction_watchlist.yaml - Jeremy's personal cross-cutting tags
    (trucks, project cars, a backcountry pistol, fly fishing gear, ...),
    layered on top of category rather than replacing it. Editable without
    a code change; missing/malformed file just means no watchlist tags,
    same graceful-degrade rule as everything else here."""
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            groups = yaml.safe_load(f) or []
    except (OSError, yaml.YAMLError) as e:
        sys.stderr.write(f"  [watchlist] couldn't load {WATCHLIST_PATH}: {e}\n")
        return []
    return [g for g in groups if g.get("label") and g.get("keywords")]


WATCHLIST = load_watchlist()


def _watchlist_kw_pattern(kw):
    """Same word-boundary idea as guess_category(), but generalized: a
    keyword starting/ending in punctuation (".308", ".30-06" - real
    caliber keywords need the leading period to avoid matching a bare lot
    number like "Lot #308") breaks a plain \\b there, since \\b only fires
    between a word char and a non-word char - two non-word chars in a row
    (a space next to a literal ".") never form a boundary, so \\b.308\\b
    silently matches NOTHING, not even the real ".308" in a listing.
    CONFIRMED this was actually happening before this fix: every caliber
    keyword matched zero real listings, including .30-06 rifles plainly
    visible in the data. (?<!\\w)/(?!\\w) (a raw non-word lookaround)
    replaces \\b only on whichever side starts/ends with non-word
    punctuation."""
    esc = re.escape(kw.lower())
    start = r"\b" if kw[0].isalnum() else r"(?<!\w)"
    end = r"\b" if kw[-1].isalnum() else r"(?!\w)"
    return start + esc + r"s?" + end


def match_watchlist(lot):
    """Every group whose keywords appear anywhere in title+description, not
    just the first match, since a lot can genuinely be on more than one
    list (a "2017 Jeep Wrangler 4x4" is both a truck/off-road pick and,
    coincidentally, exactly the kind of thing a project-car listing might
    also mention)."""
    s = f" {lot.get('title', '')} {lot.get('description', '')} ".lower()
    return [g["label"] for g in WATCHLIST if group_matches(g, s)]


def group_matches(group, text):
    """One watchlist group against already-lowercased text: any `keywords`
    hit AND no `exclude` hit. `exclude` exists for real name collisions a
    keyword can't dodge on its own - "hellcat" is both a Springfield pistol
    and a Dodge Challenger trim on this vehicle-heavy site, so the pistol
    group excludes "dodge"/"challenger"/"charger". Shared with
    scripts/watchlist_test.py so testing a keyword uses the exact live
    matching rules."""
    if not any(re.search(_watchlist_kw_pattern(kw), text) for kw in group["keywords"]):
        return False
    return not any(
        re.search(_watchlist_kw_pattern(kw), text) for kw in group.get("exclude") or []
    )


def fetch(url, headers=None):
    hdr = dict(headers or UA)
    hdr.setdefault("Accept-Encoding", "gzip")
    req = urllib.request.Request(url, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
            return r.getcode(), raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        sys.stderr.write(f"  [fetch error] {url}: {e}\n")
        return 0, ""


def _money(v):
    if v is None:
        return None
    try:
        return int(round(float(str(v).replace(",", "").replace("$", ""))))
    except ValueError:
        return None


def _first(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v


def extract_jsonld(page):
    """Return dicts from any embedded schema.org JSON-LD (Product/Offer/
    ItemList) blocks. See module docstring for why this is tried first."""
    out = []
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        page, re.S,
    ):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for c in candidates:
            if not isinstance(c, dict):
                continue
            t = c.get("@type")
            if t == "ItemList":
                for el in c.get("itemListElement", []) or []:
                    it = el.get("item", el) if isinstance(el, dict) else None
                    if isinstance(it, dict):
                        out.append(it)
            elif t in ("Product", "Offer", "AggregateOffer"):
                out.append(c)
    return out


def jsonld_to_lot(it, platform):
    offers = it.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}
    return {
        "platform": platform,
        "title": html.unescape(str(it.get("name") or "")).strip(),
        "url": it.get("url") or offers.get("url") or "",
        "image_url": _first(it.get("image")),
        "current_bid": _money(offers.get("price") or it.get("price")),
        "num_bids": None,
        "close_time": None,
        "category": it.get("category"),
        "description": html.unescape(str(it.get("description") or ""))[:600] or None,
        "agency": None,
    }


def platform_urls(platform, term):
    """Best-guess search URL per platform. See module docstring - these need
    a live run to confirm, and the ones that don't pan out will show up as
    '0 rows' in the fetch notes."""
    if platform == "publicsurplus":
        q = urllib.parse.urlencode({"keyword": term, "s": "id"})
        return [f"https://www.publicsurplus.com/sms/browse/search?{q}"]
    if platform == "govdeals":
        q = urllib.parse.urlencode({
            "fa": "Main.AdvSearchResults", "kWord": term, "locState": "ID",
        })
        return [f"https://www.govdeals.com/index.cfm?{q}"]
    if platform == "municibid":
        q = urllib.parse.urlencode({
            "searchGuts": term, "zipcode": ZIP, "radius": 60,
        })
        return [f"https://www.municibid.com/Browse?{q}"]
    if platform == "propertyroom":
        q = urllib.parse.urlencode({"keywords": term})
        return [f"https://www.propertyroom.com/search?{q}"]
    return []


# PLATFORM_FALLBACK: if a platform reports "0 rows (no json-ld found...)" on
# every term after a real run (see docs/AUCTION-MONITORING.md), add a
# platform-specific regex parser here, called from parse_search() before it
# gives up - follow the shape of car_finder.py's carscom_parse() for the
# pattern (view the real page, target its actual markup, return the same
# lot-dict shape jsonld_to_lot() produces).


SAVE_HTML_DIR = None  # set from --save-html; dumps each fetched page for
                       # writing a platform-specific parser against real markup


def _save_html(platform, term, page):
    if not SAVE_HTML_DIR or not page:
        return
    os.makedirs(SAVE_HTML_DIR, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(term)).strip("_")[:60] or "index"
    path = os.path.join(SAVE_HTML_DIR, f"{platform}__{safe}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def parse_search(page, code, platform, term, notes):
    _save_html(platform, term, page)
    if code == 403:
        notes.append(f"[{platform}] {term!r}: 403 BLOCKED")
        return []
    if not page:
        notes.append(f"[{platform}] {term!r}: empty (code {code})")
        return []
    rows = [jsonld_to_lot(it, platform) for it in extract_jsonld(page)]
    rows = [r for r in rows if r.get("title")]
    if rows:
        notes.append(f"[{platform}] {term!r}: {len(rows)} via json-ld")
    else:
        notes.append(
            f"[{platform}] {term!r}: 0 rows (no json-ld found, page "
            f"{len(page)}b) -- needs a platform-specific parser, see "
            f"docs/AUCTION-MONITORING.md"
        )
    return rows


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        k = r.get("url") or (r.get("platform"), r.get("title"), r.get("current_bid"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def fetch_platform(platform, terms, all_notes):
    rows = []
    cache = os.path.join(CACHE_DIR, f"auction_{platform}.json")
    for term in terms:
        for url in platform_urls(platform, term):
            code, page = fetch(url)
            rows.extend(parse_search(page, code, platform, term, all_notes))
            time.sleep(SLEEP)
    rows = dedupe(rows)
    if rows:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump({"fetched": date.today().isoformat(), "rows": rows}, fh)
    elif os.path.exists(cache):
        with open(cache, encoding="utf-8") as fh:
            c = json.load(fh)
        rows = c.get("rows", [])
        all_notes.append(
            f"[{platform}] no live rows; used cache from {c.get('fetched')} "
            f"({len(rows)} rows)"
        )
    return rows


# Musick's public site is built with a Divi "Query Wrapper" widget that
# lists upcoming AUCTION EVENTS (not individual lots - musickauction.com
# itself carries no price/bid data at all). Each event links out to
# bid.musickauction.com, a separate subdomain that presumably has the real
# per-item lot/bid data - CONFIRMED the link pattern exists, UNVERIFIED what
# that subdomain's markup looks like (see fetch_musick_catalog below).
# Verified 2026-09-21 against real markup (debug/auction-html branch):
#   <div class="query-row ...">
#     <div class="query-field query-field-meta_auction_link qw-link">URL</div>
#     <div class="query-field query-field-meta_image_url qw-image">
#       <a href="URL"><img src="IMAGE_URL"></a></div>
#     <div class="query-field query-field-meta_auction_title qw-title">
#       <a href="URL"><h2>TITLE</h2></a></div>
#     <div class="query-field query-field-meta_auction_date">DATE</div>
#     <div class="query-field query-field-meta_auction_location">LOCATION</div>
#     ...
#   </div>
_MUSICK_ROW_SPLIT_RE = re.compile(r'<div class="query-row[^"]*">')
_MUSICK_LINK_RE = re.compile(r'query-field-meta_auction_link qw-link">\s*(\S[^<]*?)\s*<', re.S)
_MUSICK_IMG_RE = re.compile(r'query-field-meta_image_url qw-image">.*?<img[^>]*src="([^"]+)"', re.S)
_MUSICK_TITLE_RE = re.compile(r'query-field-meta_auction_title qw-title">\s*<a[^>]*>\s*<h2>(.*?)</h2>', re.S)
_MUSICK_DATE_RE = re.compile(r'query-field-meta_auction_date">\s*([^<]+?)\s*<', re.S)
_MUSICK_LOC_RE = re.compile(r'query-field-meta_auction_location">\s*([^<]+?)\s*<', re.S)


def parse_musick_events(page):
    """Parse Musick's upcoming-auction-events widget. Returns lot-shaped
    dicts with current_bid=None (this page has no price data - just what
    sale is happening, when, where, and a link to the real catalog)."""
    out = []
    for chunk in _MUSICK_ROW_SPLIT_RE.split(page)[1:]:
        link_m = _MUSICK_LINK_RE.search(chunk)
        title_m = _MUSICK_TITLE_RE.search(chunk)
        if not link_m or not title_m:
            continue
        url = link_m.group(1).strip()
        title = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip()
        if not url or not title:
            continue
        date_m = _MUSICK_DATE_RE.search(chunk)
        loc_m = _MUSICK_LOC_RE.search(chunk)
        img_m = _MUSICK_IMG_RE.search(chunk)
        location = loc_m.group(1).strip() if loc_m else None
        out.append({
            "platform": "musick",
            "title": title,
            "url": url,
            "image_url": img_m.group(1) if img_m else None,
            "current_bid": None,
            "num_bids": None,
            "close_time": date_m.group(1).strip() if date_m else None,
            "category": None,
            "description": f"Musick Auction event in {location}" if location else None,
            "agency": f"Musick Auction Co. ({location})" if location else "Musick Auction Co.",
        })
    return out


# Guessed JSON-API URL patterns to probe directly against
# bid.musickauction.com, on the theory that whatever JS populates the
# catalog page calls a real endpoint under the hood - if one of these (or
# something close to it) hits, the whole Playwright-rendering approach in
# fetch_musick_catalog() could be replaced with a plain, fast, cheap
# request instead. Pure brute force: nothing here is verified, these are
# just common REST-ish shapes for this kind of site. {id} gets both the
# catalog URL's id (e.g. 915) and the id embedded in that event's image
# URL (e.g. 883 in /images/auction/883_m.jpg) - CONFIRMED these two
# numbers differ for the same event, so whichever id the API actually
# wants is unknown; trying both roughly doubles the odds of a hit.
_MUSICK_API_GUESSES = [
    "/api/auctions/{id}",
    "/api/auctions/{id}/lots",
    "/api/auctions/{id}/items",
    "/api/catalog/{id}",
    "/api/catalog/{id}/lots",
    "/api/v1/auctions/{id}",
    "/api/v1/catalog/{id}",
    "/api/v1/lots?auction_id={id}",
    "/auctions/api/catalog/id/{id}",
    "/auctions/catalog/id/{id}.json",
    "/auctions/catalog/id/{id}/lots",
    "/auctions/catalog/id/{id}/items",
    "/auctions/catalog/id/{id}/lots.json",
    "/lots.json?auction_id={id}",
    "/lots?auction_id={id}",
]
_MUSICK_IMG_ID_RE = re.compile(r"/images/auction/(\d+)_")


def brute_force_musick_api(events, all_notes):
    """Try each _MUSICK_API_GUESSES pattern, with both id candidates from
    the first event, as a plain direct request (no browser) against
    bid.musickauction.com. Logs status/size/whether-it-looks-like-JSON for
    each guess - doesn't parse anything, this is purely reconnaissance for
    a human (or a future pass) to read the notes and follow up on whatever
    actually hit. Bounded to one event's worth of guesses so this stays
    cheap regardless of how many events got found."""
    if not events:
        return
    m = re.search(r"/id/(\d+)", events[0].get("url") or "")
    catalog_id = m.group(1) if m else None
    img_m = _MUSICK_IMG_ID_RE.search(events[0].get("image_url") or "")
    image_id = img_m.group(1) if img_m else None
    ids = [i for i in {catalog_id, image_id} if i]
    if not ids:
        all_notes.append("[musick-api-probe] no numeric id found on the first event, skipping")
        return

    base = "https://bid.musickauction.com"
    tried = set()
    for pattern in _MUSICK_API_GUESSES:
        for auction_id in ids:
            url = base + pattern.format(id=auction_id)
            if url in tried:
                continue
            tried.add(url)
            code, body = fetch(url, headers={**UA, "Accept": "application/json, */*"})
            looks_json = bool(body) and body.lstrip()[:1] in "{["
            all_notes.append(
                f"[musick-api-probe] {url}: code={code} bytes={len(body or '')} "
                f"json-like={looks_json}"
            )
            time.sleep(0.5)


# Real per-lot markup, CONFIRMED via a live debug run against the actual
# rendered bid.musickauction.com catalog pages (debug_html/musick_catalog__*.html
# on the debug/auction-html branch) - not guessed. The page is server-rendered
# with one <li id="blkLotItemMain{lotId}" class="item-block"> per lot, each
# holding a lot number, title+detail link, current/asking bid, bid count, and
# time left. There is no separate JSON API call for this: the "sync/lot" URL
# seen in brute_force_musick_api()/the XHR log is just how the page live-updates
# bids in place after this initial render, so rendering the page once already
# carries everything needed. Only page 1 (50 lots) of the catalog is fetched -
# the same "Results: Viewing items 1-N of TOTAL" pager seen on every catalog
# page means larger auctions (700+ lots) are only partially covered; paging
# through `?page=N` is future work if that proves worth the extra fetches.
_MUSICK_LOT_SPLIT_RE = re.compile(r'<li id="blkLotItemMain\d+" class="item-block\s*">')
_MUSICK_LOT_DETAIL_URL_RE = re.compile(r'<span class="lotTitle"><a class="yaaa" href="([^"]+)">')
_MUSICK_LOT_TITLE_RE = re.compile(r'<span class="lotTitle"><a class="yaaa" href="[^"]+">([^<]*)</a></span>')
_MUSICK_LOT_NUM_RE = re.compile(r'<span class="lot_no">Lot #<span class="no">(\d+)</span>')
_MUSICK_LOT_IMG_RE = re.compile(r'<img src="([^"]+)"')
# Currency span class is "scur{auction_id}" (e.g. scur915, scur919) on most
# lots, but plain "scur"/"scur2" shows up too (CONFIRMED - both forms seen
# across the 6 real saved catalog pages) - match either with scur\d*.
_MUSICK_LOT_CURBID_RE = re.compile(
    r'item-currentbid"><span class="title">Current bid</span>'
    r'<span class="value"><span class="scur\d*">\$</span>'
    r'<span class="exratetip[^>]*>([\d,]+)</span>'
)
_MUSICK_LOT_ASKBID_RE = re.compile(
    r'item-askingbid"><span class="title">Asking bid</span>'
    r'<span class="value"><span class="scur\d*">\$</span>'
    r'<span class="exratetip[^>]*>([\d,]+)</span>'
)
# A lot nobody has bid on yet shows "Starting" instead of "Current bid" -
# CONFIRMED on musick_catalog__919.html (a single-lot offsite auction with
# no bids). That's a minimum, not an actual bid, so it's kept out of
# current_bid (same "a missing bid isn't a $0 bid" rule as auction_value.py)
# and surfaced in the description instead.
_MUSICK_LOT_STARTBID_RE = re.compile(
    r'item-starting-bid"><span class="title">Starting</span>'
    r'<span class="value"><span class="scur\d*">\$</span>'
    r'<span class="exratetip[^>]*>([\d,]+)</span>'
)
_MUSICK_LOT_NUMBIDS_RE = re.compile(r'Bidding history\((\d+)\s*bids?\)')
_MUSICK_LOT_TIMELEFT_RE = re.compile(r'Time left:&nbsp;<a[^>]*>([^<]*)</a>')


def parse_musick_lots(page):
    """Parse real per-lot rows out of a rendered bid.musickauction.com
    catalog page (see markup notes above). Current bid is used as the
    lot's price for deal-scoring - it's what a bidder actually has to beat,
    same convention as every other platform in this file. Asking bid isn't
    kept on the lot dict (not part of the shared schema), but shows up in
    the fetch notes for the curious. A lot with no bids yet keeps its
    starting-bid price in the description with current_bid left None (not
    a real price to score against), rather than being dropped."""
    out = []
    for chunk in _MUSICK_LOT_SPLIT_RE.split(page)[1:]:
        title_m = _MUSICK_LOT_TITLE_RE.search(chunk)
        url_m = _MUSICK_LOT_DETAIL_URL_RE.search(chunk)
        if not title_m or not url_m:
            continue
        bid_m = _MUSICK_LOT_CURBID_RE.search(chunk)
        start_m = _MUSICK_LOT_STARTBID_RE.search(chunk)
        if not bid_m and not start_m:
            continue
        title = html.unescape(title_m.group(1)).strip()
        if not title:
            continue
        num_m = _MUSICK_LOT_NUM_RE.search(chunk)
        img_m = _MUSICK_LOT_IMG_RE.search(chunk)
        ask_m = _MUSICK_LOT_ASKBID_RE.search(chunk)
        bids_m = _MUSICK_LOT_NUMBIDS_RE.search(chunk)
        time_m = _MUSICK_LOT_TIMELEFT_RE.search(chunk)
        desc = None
        if ask_m:
            desc = f"Asking bid ${ask_m.group(1)}"
        elif start_m and not bid_m:
            desc = f"Starting bid ${start_m.group(1)} · no bids yet"
        if time_m:
            tl = time_m.group(1).strip()
            desc = f"{desc} · Time left: {tl}" if desc else f"Time left: {tl}"
        out.append({
            "platform": "musick",
            "title": f"Lot #{num_m.group(1)}: {title}" if num_m else title,
            "url": url_m.group(1),
            "image_url": img_m.group(1) if img_m else None,
            "current_bid": _money(bid_m.group(1)) if bid_m else None,
            "num_bids": int(bids_m.group(1)) if bids_m else None,
            "close_time": None,
            "category": None,
            "description": desc,
            "agency": None,
        })
    return out


# Real per-lot DETAIL page markup (distinct from the catalog LISTING page
# parsed above) - CONFIRMED via a live probe_url debug run against a real
# vehicle lot (see docs/AUCTION-MONITORING.md). The catalog listing never
# visits this page and has none of this: year/make/model, mileage, color,
# VIN, engine/cylinders/transmission/drivetrain/body, and title status all
# sit in plain `<span class="cat-header">Label:</span> value<br>` pairs -
# exactly the "mileage, title status, running condition" a bidder is told
# to go check for themselves in auction_value.py's vehicle-caveat prompt.
_MUSICK_DETAIL_FIELD_RE = re.compile(
    r'<span class="cat-header">([^<]+):</span>\s*(.*?)<br>', re.S
)
_MUSICK_DETAIL_CURBID_RE = re.compile(
    r'id="currentBid"><span class="exratetip[^>]*>\$([\d,]+)</span>'
)
_MUSICK_DETAIL_NUMBIDS_RE = re.compile(r'\((\d+)\s*bids?\)')
_MUSICK_DETAIL_TIMELEFT_RE = re.compile(
    r'class="[^"]*time-left"><span class="in-progress">Time left:</span>'
    r'&nbsp;<span class="in-progress">([^<]*)</span>'
)
# A relative "9d 20h 36m 50s"-style string, CONFIRMED on both the catalog
# and detail pages - any of the four fields can be absent (e.g. "45m 12s"
# with no days/hours), so every group here is optional.
_MUSICK_DURATION_RE = re.compile(
    r'(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?'
)
# Titles seen on real listings so far: "Clear" (clean). Anything else
# (Salvage/Rebuilt/Bill of Sale/missing) is treated as NOT clean by
# default - same "don't manufacture confidence that isn't there" rule as
# every other estimate in this file.
_MUSICK_CLEAN_TITLE_WORDS = {"clear", "clean"}


def _parse_musick_duration(raw):
    """'9d 20h 36m 50s' -> timedelta(...), or None if nothing matched."""
    if not raw:
        return None
    m = _MUSICK_DURATION_RE.match(raw.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(g) if g else 0 for g in m.groups())
    return timedelta(days=d, hours=h, minutes=mi, seconds=s)


def parse_musick_lot_detail(page):
    """Parse the year/make/model/mileage/VIN/title-status spec block plus
    this page's own current-bid/bid-count/time-left off a rendered
    bid.musickauction.com lot-DETAIL page (not the catalog listing - see
    module notes above)."""
    fields = {}
    for m in _MUSICK_DETAIL_FIELD_RE.finditer(page):
        label = m.group(1).strip().lower()
        value = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        fields[label] = value

    def _int(v):
        try:
            return int(re.sub(r"[^\d]", "", v)) if v else None
        except ValueError:
            return None

    vin = (fields.get("vin") or "").strip().upper() or None
    if vin and len(vin) != 17:
        # Sanity check only (real VINs are always 17 characters) - not a
        # checksum validation, just enough to catch a markup mismatch
        # producing garbage rather than silently keeping it.
        vin = None

    bid_m = _MUSICK_DETAIL_CURBID_RE.search(page)
    bids_m = _MUSICK_DETAIL_NUMBIDS_RE.search(page)
    time_m = _MUSICK_DETAIL_TIMELEFT_RE.search(page)
    return {
        "vin": vin,
        "mileage": _int(fields.get("mileage")),
        "title_status": fields.get("title"),
        "year": _int(fields.get("year")),
        "make": fields.get("make"),
        "model": fields.get("model"),
        "color": fields.get("color"),
        "engine": fields.get("engine"),
        "cylinders": fields.get("cylinders"),
        "transmission": fields.get("transmisson") or fields.get("transmission"),
        "drivetrain": fields.get("drivetrain"),
        "body": fields.get("body"),
        "detail_current_bid": _money(bid_m.group(1)) if bid_m else None,
        "detail_num_bids": int(bids_m.group(1)) if bids_m else None,
        "time_left_raw": time_m.group(1).strip() if time_m else None,
    }


class MusickRun:
    """Per-run Musick state: the render function (injectable for tests) and
    the circuit breaker. After the first blocked render (catalog or vehicle
    detail), `blocked` flips True and nothing further is rendered this run;
    main() then refuses to overwrite data/auction_lots.yaml with the partial
    result. We back off and never work around a block."""

    def __init__(self, render=None):
        self.render = render
        self.blocked = False

    def render_page(self, url):
        if self.render is None:
            from musick_render import render_catalog_page
            self.render = render_catalog_page
        return self.render(url)

    def note_block(self, url, page, all_notes):
        self.blocked = True
        all_notes.append(
            f"[musick] {url!r}: {BLOCK_NOTE} ({len(page or '')} bytes); "
            f"no further Musick renders this run"
        )


def fetch_musick_vehicle_detail(lot, all_notes, run=None):
    """Enrich one Vehicles-category lot in place with real mileage/VIN/
    title-status/spec data from its own lot-detail page - a second,
    separate Playwright render per vehicle (the catalog listing page
    parsed above never visits this page at all). Only called for
    Vehicles-category lots that ALSO match the personal watchlist
    (data/auction_watchlist.yaml) - not every vehicle - to keep this,
    the single most expensive step in the whole pipeline, scoped to
    lots already worth a second look on title alone. Never raises - a
    failed render just leaves the lot without these fields, same
    graceful-degrade rule as the rest of this file."""
    url = lot.get("url")
    if not url:
        return
    run = run or MusickRun()
    if run.blocked:
        return
    try:
        page, _ = run.render_page(url)
    except ImportError:
        page = None
    if page and looks_blocked(page):
        _save_html("musick_blocked", url.rstrip("/").rsplit("/", 1)[-1], page)
        run.note_block(url, page, all_notes)
        return
    if not page:
        all_notes.append(f"[musick-detail] {url!r}: render failed, no VIN/mileage/title")
        return

    detail = parse_musick_lot_detail(page)
    for key in ("vin", "mileage", "title_status", "year", "make", "model",
                "color", "engine", "cylinders", "transmission", "drivetrain", "body"):
        lot[key] = detail[key]

    ends_at_delta = _parse_musick_duration(detail["time_left_raw"])
    lot["auction_ends_at"] = (
        (datetime.now(timezone.utc) + ends_at_delta).strftime("%Y-%m-%dT%H:%M:%SZ")
        if ends_at_delta else None
    )

    title_status = (detail["title_status"] or "").strip().lower()
    lot["clean_title"] = title_status in _MUSICK_CLEAN_TITLE_WORDS
    mileage, year = detail["mileage"], detail["year"]
    lot["miles_per_year"] = (
        round(mileage / max(1, datetime.now(timezone.utc).year - year))
        if mileage is not None and year else None
    )
    # < 150,000 miles AND a clean title - both required, neither guessed:
    # a lot with no mileage on file or a non-"Clear" title is NOT a
    # candidate, it's unknown/excluded, same as leaving deal_pct null
    # rather than assuming the best case.
    lot["car_candidate"] = bool(
        mileage is not None and mileage < 150000 and lot["clean_title"]
    )


def fetch_musick_catalog(event_url, all_notes, run=None):
    """Follow one event's catalog link to bid.musickauction.com for
    individual lot-level data.

    CONFIRMED (not guessed) via a live debug run: a plain GET here returns
    HTTP 202 with an empty body - the signature of a JavaScript-rendered
    single-page app, not a markup-mismatch problem urllib could ever solve.
    So this renders the page with a real headless browser instead
    (musick_render.py, Playwright + Chromium) and only falls back to a
    plain fetch()/json-ld if Playwright isn't available for some reason
    (e.g. not installed - see .github/workflows/auction-monitor.yml's
    "Install dependencies" step, which is where it actually gets installed;
    this dev sandbox doesn't have it and can't reach this subdomain either
    way, so this path is UNVERIFIED against the real site - same
    debug-and-inspect process as everything else in this file applies).
    Also logs every XHR/fetch request Playwright saw the page make while
    loading (musick_render.py captures these) - if this SPA calls a JSON
    API under the hood, that's the one chance to actually see the URL
    instead of guessing at it. See brute_force_musick_api() below for a
    second, more direct way of hunting for the same thing.

    If nothing usable comes back, the calling event row is kept as-is
    rather than dropped."""
    run = run or MusickRun()
    if run.blocked:
        return []
    api_calls = []
    try:
        page, api_calls = run.render_page(event_url)
    except ImportError:
        page = None
    if page and looks_blocked(page):
        # Save the page so a real block page finally gets captured
        # (debug_html) - none has been seen yet, see musick_render.looks_blocked.
        _save_html("musick_blocked", event_url.rstrip("/").rsplit("/", 1)[-1], page)
        run.note_block(event_url, page, all_notes)
        return []
    if api_calls:
        all_notes.append(f"[musick-catalog] {event_url!r}: {len(api_calls)} XHR/fetch call(s) seen while rendering:")
        for c in api_calls[:15]:
            all_notes.append(f"    {c['method']} {c['url']}")
    if not page:
        # Fall back to a plain fetch in case Playwright genuinely isn't
        # available - won't produce real data (see docstring), but keeps
        # this from silently doing nothing if the render step is broken.
        code, page = fetch(event_url)
        if code == 403:
            all_notes.append(f"[musick-catalog] {event_url!r}: 403 BLOCKED (plain fetch, no render)")
            return []
        if not page:
            all_notes.append(f"[musick-catalog] {event_url!r}: empty (plain fetch, no render, code {code})")
            return []

    _save_html("musick_catalog", event_url.rstrip("/").rsplit("/", 1)[-1], page)
    rows = [jsonld_to_lot(it, "musick") for it in extract_jsonld(page)]
    rows = [r for r in rows if r.get("title")]
    if rows:
        all_notes.append(f"[musick-catalog] {event_url!r}: {len(rows)} lots via json-ld")
    else:
        rows = parse_musick_lots(page)
        if rows:
            all_notes.append(
                f"[musick-catalog] {event_url!r}: {len(rows)} real lots via "
                f"rendered-markup parser (page 1 only)"
            )
        else:
            # Only reached for a page that passed looks_blocked() (>= 2,000
            # bytes, not a challenge page), so "markup may have changed" is
            # a fair guess here - unlike for a tiny/blocked page.
            all_notes.append(
                f"[musick-catalog] {event_url!r}: 0 rows (no json-ld and no "
                f"blkLotItemMain rows in rendered page, {len(page)}b) -- markup "
                f"may have changed, see docs/AUCTION-MONITORING.md"
            )

    # The per-lot detail-page render (fetch_musick_vehicle_detail) is by far
    # the most expensive step in this whole pipeline - a second Playwright
    # page load per lot. Scoped to only Vehicles that ALSO match the
    # personal watchlist (data/auction_watchlist.yaml) rather than every
    # vehicle: no point spending that cost on a sedan nobody's watching for
    # just to find out its mileage. This is the main lever for "drop early,
    # don't waste time on subpar" as more sources get added - the expensive
    # work only happens on what was already worth a second look on title
    # alone.
    all_vehicles = [r for r in rows if guess_category(r) == "Vehicles"]
    vehicle_rows = [r for r in all_vehicles if match_watchlist(r)]
    skipped_vehicles = len(all_vehicles) - len(vehicle_rows)
    if vehicle_rows:
        n_candidates = 0
        for row in vehicle_rows:
            fetch_musick_vehicle_detail(row, all_notes, run)
            if run.blocked:
                break  # circuit breaker: no more Musick renders this run
            if row.get("car_candidate"):
                n_candidates += 1
            time.sleep(SLEEP)
        all_notes.append(
            f"[musick-detail] {event_url!r}: fetched detail for "
            f"{len(vehicle_rows)} watchlist-matched vehicle lot(s) "
            f"(skipped {skipped_vehicles} non-matching), {n_candidates} "
            f"candidate(s) (<150k mi, clean title)"
        )
    return rows


def fetch_musick(all_notes, run=None):
    """`run` (a MusickRun) carries the render function and the block flag
    back to main(); omitted, a private one is used."""
    run = run or MusickRun()
    platform = "musick"
    cache = os.path.join(CACHE_DIR, f"auction_{platform}.json")
    events = []
    for path in MUSICK_PATHS:
        url = MUSICK_BASE + path
        code, page = fetch(url)
        _save_html(platform, path, page)
        if code == 403:
            all_notes.append(f"[{platform}] {path!r}: 403 BLOCKED")
        elif not page:
            all_notes.append(f"[{platform}] {path!r}: empty (code {code})")
        else:
            found = parse_musick_events(page)
            if found:
                all_notes.append(f"[{platform}] {path!r}: {len(found)} auction events")
                events.extend(found)
            else:
                all_notes.append(
                    f"[{platform}] {path!r}: 0 rows (no auction-event rows "
                    f"found, page {len(page)}b) -- markup may have changed, "
                    f"see docs/AUCTION-MONITORING.md"
                )
        time.sleep(SLEEP)
    events = dedupe(events)

    brute_force_musick_api(events, all_notes)

    # Stage 2: try to get real per-item lots from each event's catalog page.
    # Whatever doesn't yield real lots keeps its event-level row instead of
    # being dropped - "a sale is happening Monday with vehicles in it" is
    # still useful even without per-item bids.
    lots = []
    for event in events:
        if run.blocked:
            lots.append(event)  # breaker open: no more Musick renders
            continue
        catalog_rows = fetch_musick_catalog(event["url"], all_notes, run)
        if run.blocked:
            lots.append(event)
            continue
        time.sleep(SLEEP)
        if catalog_rows:
            for r in catalog_rows:
                r["agency"] = event["agency"]
            lots.extend(catalog_rows)
        else:
            lots.append(event)

    rows = dedupe(lots)
    if rows and not run.blocked:  # never cache a partial, block-truncated result
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump({"fetched": date.today().isoformat(), "rows": rows}, fh)
    elif os.path.exists(cache):
        with open(cache, encoding="utf-8") as fh:
            c = json.load(fh)
        rows = c.get("rows", [])
        all_notes.append(
            f"[{platform}] no live rows; used cache from {c.get('fetched')} "
            f"({len(rows)} rows)"
        )
    return rows


def guess_agency(lot, term):
    if lot.get("agency"):
        # Already set by the fetcher itself (e.g. parse_musick_events()
        # knows the real event location) - trust that over a guess.
        return lot["agency"]
    s = f"{lot.get('title', '')} {lot.get('description', '')}".lower()
    for needle, label in AGENCY_LABELS:
        if needle in s:
            return label
    return term


def in_region(lot):
    if lot.get("platform") == "musick":
        return True  # a Nampa, ID auctioneer's own listings are local by definition
    s = " ".join(
        str(lot.get(k) or "") for k in ("agency", "title", "description", "url")
    ).lower()
    return any(re.search(r"\b" + re.escape(n) + r"\b", s) for n in NEAR)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--save-html", metavar="DIR",
                     help="dump each fetched page's raw HTML to DIR, for "
                          "writing a platform-specific parser against real "
                          "markup (see PLATFORM_FALLBACK)")
    a = ap.parse_args(argv)

    global SAVE_HTML_DIR
    SAVE_HTML_DIR = a.save_html

    all_rows, all_notes = [], []
    musick_run = MusickRun()
    for platform in PLATFORMS:
        if platform == "musick":
            rows = fetch_musick(all_notes, musick_run)
            fallback_agency = "Musick Auction Co."
        else:
            rows = fetch_platform(platform, AGENCY_TERMS, all_notes)
            fallback_agency = None
        for r in rows:
            r["agency"] = guess_agency(r, fallback_agency)
        all_rows.extend(rows)

    merged = dedupe(all_rows)
    kept = [r for r in merged if in_region(r)]
    dropped = len(merged) - len(kept)

    for r in kept:
        r.setdefault("num_bids", None)
        r.setdefault("close_time", None)
        r.setdefault("description", None)
        r["category"] = guess_category(r)
        r["watchlist_matches"] = match_watchlist(r)
        r["estimated_value_low"] = None
        r["estimated_value_high"] = None
        r["estimated_value_mid"] = None
        r["deal_score"] = None
        r["deal_pct"] = None
        r["ai_note"] = None
        r["value_source"] = None  # "ebay" | "ai" | None - set by auction_value.py
        r["ebay_n"] = None
        r["ebay_median"] = None
        r["flagged"] = False
        r["fetched_at"] = date.today().isoformat()

    # "Dial in the search": don't waste storage or a bidder's attention on
    # a lot that isn't actually being searched for. A lot is worth keeping
    # only if it's grandpa's original core interest (Small Engines &
    # Appliances) or it matches the personal watchlist
    # (data/auction_watchlist.yaml) - everything else gets dropped here,
    # before it's ever written to disk or rendered, not just hidden. This
    # is the actual lever for scaling to more sources later: the interest
    # bar, not the number of sites fetched, bounds how much ends up kept.
    ALWAYS_KEEP_CATEGORY = "Small Engines & Appliances"
    before_interest_filter = len(kept)
    kept = [
        r for r in kept
        if r["category"] == ALWAYS_KEEP_CATEGORY or r["watchlist_matches"]
    ]
    dropped_uninteresting = before_interest_filter - len(kept)

    kept.sort(key=lambda r: (r.get("current_bid") is None, r.get("current_bid") or 0))

    print(f"kept {len(kept)} lots across {len(PLATFORMS)} platforms "
          f"(dropped {dropped} with no Treasure Valley signal, "
          f"{dropped_uninteresting} matching neither the watchlist nor "
          f"'{ALWAYS_KEEP_CATEGORY}')")
    for platform in PLATFORMS:
        n = sum(1 for r in kept if r.get("platform") == platform)
        print(f"  {platform:14s} {n}")
    cat_counts = {}
    for r in kept:
        cat_counts[r["category"]] = cat_counts.get(r["category"], 0) + 1
    print("\nby category:")
    for cat, n in sorted(cat_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:20s} {n}")
    watch_counts = {}
    for r in kept:
        for label in r.get("watchlist_matches") or []:
            watch_counts[label] = watch_counts.get(label, 0) + 1
    if watch_counts:
        print("\nwatchlist matches:")
        for label, n in sorted(watch_counts.items(), key=lambda kv: -kv[1]):
            print(f"  {label:30s} {n}")
    print("\nfetch notes:")
    for n in all_notes:
        print("  " + n)

    if a.dry_run:
        print("\n--dry-run: not writing")
        return

    if musick_run.blocked:
        # A block truncates the result (some catalogs never rendered), and
        # writing it would silently drop live sales. Keep the last complete
        # snapshot; exit 0 so the workflow continues and valuation just
        # re-reads the old file.
        print(
            f"\nSKIPPED writing {os.path.abspath(OUT)}: Musick blocked this "
            f"run ({BLOCK_NOTE}). Keeping the previous complete snapshot "
            f"instead of a partial one."
        )
        return

    doc = {"generated": date.today().isoformat(), "lots": kept}
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\nwrote {os.path.abspath(OUT)}")
    print("run scripts/auction_value.py next to fill in AI value estimates.")


if __name__ == "__main__":
    main()
