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
from datetime import date

import yaml

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


def fetch_musick_catalog(event_url, all_notes):
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
    api_calls = []
    try:
        from musick_render import render_catalog_page
        page, api_calls = render_catalog_page(event_url)
    except ImportError:
        page = None
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
        return rows

    rows = parse_musick_lots(page)
    if rows:
        all_notes.append(
            f"[musick-catalog] {event_url!r}: {len(rows)} real lots via "
            f"rendered-markup parser (page 1 only)"
        )
    else:
        all_notes.append(
            f"[musick-catalog] {event_url!r}: 0 rows (no json-ld and no "
            f"blkLotItemMain rows in rendered page, {len(page)}b) -- markup "
            f"may have changed, see docs/AUCTION-MONITORING.md"
        )
    return rows


def fetch_musick(all_notes):
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
        catalog_rows = fetch_musick_catalog(event["url"], all_notes)
        time.sleep(SLEEP)
        if catalog_rows:
            for r in catalog_rows:
                r["agency"] = event["agency"]
            lots.extend(catalog_rows)
        else:
            lots.append(event)

    rows = dedupe(lots)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--save-html", metavar="DIR",
                     help="dump each fetched page's raw HTML to DIR, for "
                          "writing a platform-specific parser against real "
                          "markup (see PLATFORM_FALLBACK)")
    a = ap.parse_args()

    global SAVE_HTML_DIR
    SAVE_HTML_DIR = a.save_html

    all_rows, all_notes = [], []
    for platform in PLATFORMS:
        if platform == "musick":
            rows = fetch_musick(all_notes)
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

    kept.sort(key=lambda r: (r.get("current_bid") is None, r.get("current_bid") or 0))

    print(f"kept {len(kept)} lots across {len(PLATFORMS)} platforms "
          f"(dropped {dropped} with no Treasure Valley signal)")
    for platform in PLATFORMS:
        n = sum(1 for r in kept if r.get("platform") == platform)
        print(f"  {platform:14s} {n}")
    cat_counts = {}
    for r in kept:
        cat_counts[r["category"]] = cat_counts.get(r["category"], 0) + 1
    print("\nby category:")
    for cat, n in sorted(cat_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:20s} {n}")
    print("\nfetch notes:")
    for n in all_notes:
        print("  " + n)

    if a.dry_run:
        print("\n--dry-run: not writing")
        return

    doc = {"generated": date.today().isoformat(), "lots": kept}
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\nwrote {os.path.abspath(OUT)}")
    print("run scripts/auction_value.py next to fill in AI value estimates.")


if __name__ == "__main__":
    main()
