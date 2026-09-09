#!/usr/bin/env python3
"""
car_finder.py - pull current used-car listings for a handful of target vehicles
from two sources (Boise Craigslist + Cars.com), geo-filter to the Treasure
Valley, and write one ranked YAML.

Sources
-------
1. Craigslist (boise.craigslist.org/search/cta). RSS is dead, but the HTML
   results page is fetchable server-side with a browser User-Agent. Each page
   embeds a JSON-LD ItemList in <script id="ld_searchpage_results"> AND a
   parallel <li class="cl-static-search-result"> list (which carries the URL the
   JSON-LD lacks) - we merge the two by position.

2. Cars.com (/shopping/results/). Listings live in <div class="vehicle-card">
   nodes with data-* attributes and in an embedded JSON blob; we parse whichever
   is present. Cars.com sits behind Akamai and returns 403 to datacenter IPs -
   when that happens the script records the block and falls back to a local
   cache at data/.cache/carscom_<key>.json (refreshed on any successful run).

Geo filter: only listings in / near the Treasure Valley are kept (Boise,
Meridian, Eagle, Nampa, Caldwell, Garden City, Kuna, Star, Mountain Home,
Ontario OR, Twin Falls, plus any dealer that identifies as Idaho). Spokane,
Houston, and other far cities are dropped and counted.

Usage
-----
    python scripts/car_finder.py           # run everything, write YAML
    python scripts/car_finder.py --dry-run # print, don't write

Output: data/car_listings.yaml
Be polite: 2s sleep between requests.
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime

BASE = "https://boise.craigslist.org/search/cta"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
SLEEP = 2.0

# Dealers to flag on the page. Keyed by a lowercase substring of the listing
# location. Reasons come from Jeremy's own visits -- his read of a lot beats
# any badge. A flagged listing still shows; it just carries a warning.
DEALER_FLAGS = {
    "dillon": "Dennis Dillon group (GMC/Fiat, CJDR Caldwell, Mitsubishi, "
              "Nissan) -- visited Sept 2026, staff were rude, bad vibes.",
    "autosavvy": "AutoSavvy -- rebuilt / branded-title dealer by business "
                 "model. A branded car always shows as a 'deal' vs clean-title "
                 "prices. Resale + insurance hit; rebuilt-title buyers only.",
}

# Listings confirmed gone in person (Cars.com lags real inventory). Suppressed.
SOLD_URLS = {
    # 2020 Forester Touring, CarMax Meridian -- dead when they went 2026-09
    "https://www.cars.com/vehicledetail/1b763353-50fa-4910-90d2-7e161f4a4293/",
}

# Listings seen in person and passed on. Kept on the page, flagged with why.
LISTING_FLAGS = {
    # 2024 Forester Touring, Capital City Auto -- clean Carfax but hard-used:
    # scratches inside and out, felt more worn than its 54k miles.
    "https://www.cars.com/vehicledetail/d342e928-7a58-47e1-9be2-d5478f12de0b/":
        "Seen in person Sept 2026 -- passed. Clean Carfax, but scratched "
        "inside and out and felt beat for the miles (54k / ~21k per year).",
}

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "..", "data", "car_listings.yaml")
CACHE_DIR = os.path.join(_HERE, "..", "data", ".cache")
ZIP = "83714"  # Garden City / Boise

SEARCHES = [
    # key, cl_terms, min_year, max_price, title_must, require_year,
    #      carscom_make, carscom_model
    ("forester",   ["forester"],       2019, 35500, ["forester"],           False, "subaru", "subaru-forester"),
    ("rav4",       ["rav4"],            2019, 33000, ["rav4", "rav 4"],      False, "toyota", "toyota-rav_4"),
    ("fourrunner", ["4runner"],         2010, 36500, ["4runner", "4 runner"], False, "toyota", "toyota-4runner"),
    # Honda Passport: require a parsed year >= 2019 to exclude the 90s
    # Isuzu-based Passport.
    ("passport",   ["passport"],        2019, 34000, ["passport"],           True,  "honda",  "honda-passport"),
]
YAML_KEYS = ("forester", "rav4", "fourrunner", "passport")

# --------------------------------------------------------------------------- #
# geo filter - Treasure Valley + reasonable driving distance
# --------------------------------------------------------------------------- #
NEAR = [
    "boise", "meridian", "eagle", "nampa", "caldwell", "garden city", "kuna",
    "star", "mountain home", "ontario", "twin falls", "emmett", "middleton",
    "fruitland", "payette", "weiser", "homedale", "parma", "melba",
    "new plymouth", "wilder", "marsing", "greenleaf", "notus", "jerome",
]
FAR = [
    "spokane", "houston", "seattle", "tacoma", "portland", "salem", "eugene",
    "salt lake", "provo", "ogden", "denver", "reno", "las vegas", "phoenix",
    "sacramento", "dallas", "atlanta", "chicago", "kennewick", "pasco",
    "richland", "yakima", "walla walla", "missoula", "bozeman", "billings",
    "pocatello", "idaho falls", "coeur d'alene", "lewiston", "bend",
]


def in_region(loc, url=""):
    """True if the listing's location is in/near the Treasure Valley (or
    unknown - we keep unknowns and let year/price filters carry them).
    Craigslist URL slugs embed the city (.../view/d/spokane-2019-...), so we
    fold the slug in as a secondary signal."""
    s = f"{loc or ''} {url or ''}".lower()
    if not s.strip():
        return True
    if any(re.search(r"\b" + re.escape(n) + r"\b", s) for n in NEAR):
        return True
    if any(f in s for f in FAR):
        return False
    if re.search(r"\bid(?:aho)?\b", s):   # "Some Dealer, ID" / "... Idaho"
        return True
    # names a state other than ID, or a city we don't recognise -> drop
    if re.search(r",\s*[a-z]{2}\b", s):
        return False
    return True


BROWSER = {
    "User-Agent": UA["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}


def fetch(url, headers=None):
    import gzip
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
        sys.stderr.write(f"  [fetch error] {e}\n")
        return 0, ""


def build_url(term, min_year, max_price):
    q = urllib.parse.urlencode({
        "query": term,
        "min_auto_year": min_year,
        "max_price": max_price,
        "sort": "date",
        "bundleDuplicates": 1,
    })
    return f"{BASE}?{q}"


YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
ODO_RE = re.compile(r"([\d,]{4,7})\s*(?:mi|miles|k\s*mi|k\s*miles)\b", re.I)


def parse_year(title):
    m = YEAR_RE.search(title or "")
    if m:
        y = int(m.group(0))
        if 1990 <= y <= date.today().year + 1:
            return y
    return None


def parse_odo(*texts):
    for t in texts:
        if not t:
            continue
        m = ODO_RE.search(t)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def from_jsonld(page):
    """Try the embedded JSON-LD ItemList. Returns list of dicts or None."""
    m = re.search(
        r'<script[^>]*id="ld_searchpage_results"[^>]*>(.*?)</script>',
        page, re.S,
    )
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return None
    items = data.get("itemListElement") or []
    out = []
    for el in items:
        it = el.get("item", el)
        offers = it.get("offers", {}) or {}
        price = offers.get("price")
        title = it.get("name") or ""
        url = it.get("url") or offers.get("url") or ""
        out.append({
            "title": html.unescape(title).strip(),
            "price": _money(price),
            "year": parse_year(title),
            "odometer": parse_odo(title, it.get("description")),
            "url": url,
            "post_date": (it.get("datePosted") or "")[:10] or None,
            "location": _hood(it),
            "source": "craigslist",
            "deal_rating": None,
            "market_delta": None,
        })
    return out


def _hood(it):
    for key in ("availableAtOrFrom", "areaServed"):
        v = it.get(key)
        if isinstance(v, dict):
            addr = v.get("address")
            if isinstance(addr, dict):
                return addr.get("addressLocality") or addr.get("name")
            if isinstance(addr, str):
                return addr
    return None


def _money(v):
    if v is None:
        return None
    try:
        return int(float(str(v).replace(",", "").replace("$", "")))
    except ValueError:
        return None


def from_html(page):
    """Fallback: parse the static <li class="cl-static-search-result"> markup."""
    out = []
    blocks = re.findall(
        r'<li class="cl-static-search-result"[^>]*?title="([^"]*)"[^>]*>(.*?)</li>',
        page, re.S,
    )
    if not blocks:
        # newer markup: div wrappers
        blocks = re.findall(
            r'<div class="cl-static-search-result"[^>]*>(.*?)</div>\s*</div>',
            page, re.S,
        )
        blocks = [("", b) for b in blocks]
    for title_attr, body in blocks:
        a = re.search(r'<a[^>]*href="([^"]+)"', body)
        t = re.search(r'<div class="title">(.*?)</div>', body, re.S)
        p = re.search(r'<div class="price">\s*\$?([\d,]+)', body)
        loc = re.search(r'<div class="location">\s*(.*?)\s*</div>', body, re.S)
        title = html.unescape((t.group(1) if t else title_attr) or "").strip()
        title = re.sub(r"<[^>]+>", "", title)
        out.append({
            "title": title,
            "price": _money(p.group(1)) if p else None,
            "year": parse_year(title),
            "odometer": parse_odo(title),
            "url": a.group(1) if a else "",
            "post_date": None,
            "location": (re.sub(r"<[^>]+>", "", loc.group(1)).strip() if loc else None),
            "source": "craigslist",
            "deal_rating": None,
            "market_delta": None,
        })
    return out


def _titlematch(title, musts):
    t = re.sub(r"[^a-z0-9]", "", (title or "").lower())
    return any(re.sub(r"[^a-z0-9]", "", m.lower()) in t for m in musts)


def dedupe(listings):
    seen, out = set(), []
    for x in listings:
        k = x.get("url") or (x.get("title"), x.get("price"))
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def _merge(html_rows, ld_rows):
    """The static <li> list and the JSON-LD ItemList are parallel and ordered.
    Take url/title/price from the <li> markup (JSON-LD has no url), and borrow
    the city + odometer from JSON-LD where the markup lacks them."""
    for i, r in enumerate(html_rows):
        if i < len(ld_rows):
            ld = ld_rows[i]
            r["location"] = ld.get("location") or r.get("location")
            r["odometer"] = r.get("odometer") or ld.get("odometer")
            r["post_date"] = r.get("post_date") or ld.get("post_date")
    return html_rows


def run_search(key, terms, min_year, max_price, title_must_match, require_year=False):
    all_rows, notes = [], []
    for term in terms:
        url = build_url(term, min_year, max_price)
        code, page = fetch(url)
        if code == 403:
            notes.append(f"{term}: 403 BLOCKED")
        elif not page:
            notes.append(f"{term}: empty (code {code})")
        else:
            ld = from_jsonld(page) or []
            rows = from_html(page)
            how = "html+json-ld" if ld else "html"
            if not rows and ld:
                rows, how = ld, "json-ld"  # markup changed; use JSON-LD alone
            rows = _merge(rows, ld)
            if not rows:
                notes.append(f"{term}: 0 rows (page {len(page)}b, code {code})")
            else:
                notes.append(f"{term}: {len(rows)} via {how}")
                all_rows.extend(rows)
        time.sleep(SLEEP)
    rows = dedupe(all_rows)
    # keep only listings whose title actually names the target model
    rows = [r for r in rows if _titlematch(r.get("title"), title_must_match)]
    # enforce filters that the URL params should already handle
    rows = [r for r in rows
            if (r["year"] >= min_year if require_year else
                (r.get("year") is None or r["year"] >= min_year))
            and (r.get("price") is None or r["price"] <= max_price)]
    return rows, notes


# --------------------------------------------------------------------------- #
# Cars.com
# --------------------------------------------------------------------------- #

def carscom_url(make, model):
    q = urllib.parse.urlencode({
        "stock_type": "used", "makes[]": make, "models[]": model,
        "maximum_distance": "100", "zip": ZIP,
        "page_size": "100", "sort": "list_price",
    }).replace("makes%5B%5D", "makes[]").replace("models%5B%5D", "models[]")
    return f"https://www.cars.com/shopping/results/?{q}"


_DEAL_CANON = {
    "great deal": "Great Deal",
    "good deal": "Good Deal",
    "fair deal": "Fair Price",
    "fair price": "Fair Price",
    "overpriced": "Overpriced",
    "high price": "Overpriced",
}


def canon_deal(txt):
    """Normalize a cars.com badge string to the canonical set, or None."""
    if not txt:
        return None
    return _DEAL_CANON.get(str(txt).strip().lower())


def parse_market_delta(txt):
    """'$1,432 below market' -> -1432 ; '$1.6K above market' -> 1600 ; else None."""
    if not txt:
        return None
    m = re.search(r"\$\s*([\d,.]+)\s*(k)?\b.*?(below|above)", str(txt), re.I)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    if m.group(2):
        n *= 1000
    n = int(round(n))
    return -n if m.group(3).lower() == "below" else n


def carscom_parse(page):
    """Cars.com: prefer the data-* attributes on <div class="vehicle-card">;
    fall back to the embedded JSON list of listing objects."""
    out = []
    for card in re.findall(r'<div [^>]*class="[^"]*vehicle-card[^"]*"[^>]*>', page):
        def attr(name):
            m = re.search(name + r'="([^"]*)"', card)
            return m.group(1) if m else None
        yr = attr("data-year")
        if not yr:
            continue
        lid = attr("data-listing-id")
        out.append({
            "title": " ".join(x for x in (yr, attr("data-make"),
                                          attr("data-model")) if x),
            "price": _money(attr("data-price")),
            "year": int(yr) if yr and yr.isdigit() else None,
            "odometer": _money(attr("data-mileage")),
            "url": (f"https://www.cars.com/vehicledetail/{lid}/" if lid else ""),
            "post_date": None,
            "location": None,
            "source": "cars.com",
            "deal_rating": canon_deal(attr("data-deal-rating")),
            "market_delta": parse_market_delta(attr("data-price-badge")),
        })
    if out:
        return out
    # JSON fallback - listing objects with the usual keys
    for blob in re.findall(r'\{"[^{}]*?"listing_id"[^{}]*?\}', page):
        try:
            o = json.loads(blob)
        except json.JSONDecodeError:
            continue
        out.append({
            "title": " ".join(str(o.get(k, "")) for k in
                               ("year", "make", "model")).strip(),
            "price": _money(o.get("price") or o.get("list_price")),
            "year": o.get("year"),
            "odometer": _money(o.get("mileage")),
            "url": o.get("canonical_url") or o.get("vdp_url") or "",
            "post_date": None,
            "location": ", ".join(x for x in (o.get("dealer_name"),
                                              o.get("seller_city"),
                                              o.get("seller_state")) if x) or None,
            "source": "cars.com",
            "deal_rating": canon_deal(o.get("deal_rating") or o.get("price_badge")),
            "market_delta": parse_market_delta(o.get("price_badge_text")
                                               or o.get("price_difference")),
        })
    return out


def carscom_search(key, make, model, min_year, max_price, title_must, require_year):
    notes = []
    cache = os.path.join(CACHE_DIR, f"carscom_{key}.json")
    url = carscom_url(make, model)
    code, page = fetch(url, headers=BROWSER)
    rows = carscom_parse(page) if page else []
    time.sleep(SLEEP)
    if rows:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump({"fetched": date.today().isoformat(), "rows": rows}, fh)
        notes.append(f"cars.com: {len(rows)} live")
    else:
        why = "403 BLOCKED" if code == 403 else f"empty (code {code})"
        if os.path.exists(cache):
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
    rows = [r for r in rows
            if _titlematch(r.get("title"), title_must)
            and (r.get("year") is None or r["year"] >= min_year)
            and (not require_year or r.get("year"))
            and (r.get("price") is None or r["price"] <= max_price)]
    return rows, notes


# --------------------------------------------------------------------------- #
# tiny YAML writer (avoid a dependency)
# --------------------------------------------------------------------------- #

def _yv(v):
    if v is None:
        return "null"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if s == "" or re.search(r'[:#\[\]{}"\']|^\s|\s$|^[-?]|^\d', s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


_DEAL_SCORE = {"Great Deal": -1500, "Good Deal": -500,
               "Fair Price": 0, "Overpriced": 1500}


def value_score(r):
    """Lower = better value. market delta if known, else derived from the
    deal-rating badge, else None (unrated craigslist rows sort last)."""
    if r.get("market_delta") is not None:
        return r["market_delta"]
    if r.get("deal_rating") in _DEAL_SCORE:
        return _DEAL_SCORE[r["deal_rating"]]
    return None


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
            r["value_score"] = value_score(r)
            first = True
            for f in ("source", "title", "price", "year", "odometer", "url",
                      "post_date", "location", "deal_rating", "market_delta",
                      "value_score", "dealer_flag"):
                prefix = "  - " if first else "    "
                lines.append(f"{prefix}{f}: {_yv(r.get(f))}")
                first = False
        lines.append("")
    out = "\n".join(lines) + "\n"
    cpo = preserve_cpo(os.path.abspath(OUT))
    if cpo:
        out = out.rstrip("\n") + "\n\n" + cpo
    return out


def preserve_cpo(path):
    """The cpo: block is hand-curated (see MONKEYS-style notes in the YAML) and
    is not regenerated by this script. Carry it over verbatim from the existing
    file, including its leading comment lines, so a run doesn't drop it."""
    if not os.path.exists(path):
        return ""
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"\n((?:#[^\n]*\n)*cpo:\n.*)$", txt, re.S)
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    result = {"generated": date.today().isoformat()}
    all_notes = []
    total_dropped = 0
    for (key, terms, min_year, max_price, title_must, require_year,
         cc_make, cc_model) in SEARCHES:
        cl_rows, notes = run_search(key, terms, min_year, max_price,
                                    title_must, require_year)
        cc_rows, cc_notes = carscom_search(key, cc_make, cc_model, min_year,
                                           max_price, title_must, require_year)
        notes += cc_notes

        merged = dedupe(cl_rows + cc_rows)
        kept = [r for r in merged
                if in_region(r.get("location"), r.get("url"))
                and r.get("url") not in SOLD_URLS]
        dropped = len(merged) - len(kept)
        total_dropped += dropped
        for r in kept:
            loc = (r.get("location") or "").lower()
            r["dealer_flag"] = LISTING_FLAGS.get(r.get("url")) or next(
                (msg for sub, msg in DEALER_FLAGS.items() if sub in loc), None)
        kept.sort(key=lambda r: (r.get("price") is None, r.get("price") or 0))
        kept = kept[:35]
        result[key] = kept

        all_notes += [f"[{key}] {n}" for n in notes]
        n_cl = sum(1 for r in kept if r.get("source") == "craigslist")
        n_cc = sum(1 for r in kept if r.get("source") == "cars.com")
        prices = [r["price"] for r in kept if r.get("price")]
        odos = [r["odometer"] for r in kept if r.get("odometer")]
        rng = f"${min(prices):,}-${max(prices):,}" if prices else "n/a"
        orng = f"{min(odos):,}-{max(odos):,} mi" if odos else "n/a"
        print(f"{key:10s} {len(kept):2d}  (cl {n_cl}, cars.com {n_cc})  "
              f"price {rng}  odo {orng}  region_dropped {dropped}")

    print(f"\nregion_filtered_out (all categories): {total_dropped}")
    print("\nfetch notes:")
    for n in all_notes:
        print("  " + n)

    if a.dry_run:
        print("\n--dry-run: not writing")
        return
    path = os.path.abspath(OUT)
    text = dump_yaml(result)  # reads existing file for the cpo block - before truncate
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
