#!/usr/bin/env python3
"""
ebay_comps.py - look up recent eBay SOLD listings for a search query, as a
real-transaction anchor for scripts/auction_value.py's resale estimate.

Why eBay specifically: it's the closest thing to a free, public source of
actual sale prices (not asking prices) for used goods. eBay retired its old
completed-items API years ago (the replacement, the Marketplace Insights
API, is partner-gated - not available for a casual project like this), so
the only way in is the same way the rest of this repo already gets data
from sites with no open API: fetch the public search results page and
parse it.

    https://www.ebay.com/sch/i.html?_nkw=<query>&LH_Sold=1&LH_Complete=1

That URL (sold + completed listings filter) is - as of when this was
written - viewable without logging in. Parsing tries JSON-LD first (same
reasoning as auction_finder.py: it's meant for Google rich snippets, so
it's a more stable target than a hand-picked CSS class), then a regex
against eBay's known `s-item__price` search-result markup as a fallback.

IMPORTANT - unverified against live markup, same caveat as everything else
in this repo's auction tooling: this dev sandbox's network policy blocks
ebay.com outright, so this has never run against a real eBay page. Treat it
as a first draft to be corrected against docs/AUCTION-MONITORING.md's
process once it's run for real (GitHub Actions workflow_dispatch, check the
fetch notes / --save-html dump, adjust the regex).

A second, separate concern, also carried over from the rest of this repo:
eBay's Terms of Service and User Agreement restrict scraping. This fetches
public search-result pages at a polite rate for personal, non-commercial
comp-checking - read eBay's ToS before leaning on this long-term, and drop
it (fall back to the AI-only estimate) if eBay pushes back.

Usage (as a library, called from auction_value.py):
    from ebay_comps import lookup
    comps = lookup("Kirby G6 vacuum")
    # -> {"n": 8, "median": 95.0, "low": 62.0, "high": 140.0} or None
"""

import json
import os
import re
import statistics
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auction_finder import fetch, UA  # noqa: E402 - reuse the same HTTP layer

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", ".cache")
MIN_PRICE = 3.0     # drop $0-2 junk rows (shipping-only / accessory listings)
MAX_COMPS = 25       # cap how many sold prices we average over


def _cache_key(query):
    return re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:80]


def search_url(query):
    q = urllib.parse.urlencode({
        "_nkw": query,
        "LH_Sold": "1",
        "LH_Complete": "1",
        "_ipg": "60",  # 60 results/page - more comps per fetch
    })
    return f"https://www.ebay.com/sch/i.html?{q}"


def _extract_jsonld_prices(page):
    prices = []
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S
    ):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for c in candidates:
            if not isinstance(c, dict):
                continue
            items = c.get("itemListElement") if c.get("@type") == "ItemList" else [c]
            for el in items or []:
                it = el.get("item", el) if isinstance(el, dict) else None
                if not isinstance(it, dict):
                    continue
                offers = it.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = (offers or {}).get("price") if isinstance(offers, dict) else None
                if price is not None:
                    try:
                        prices.append(float(price))
                    except (TypeError, ValueError):
                        pass
    return prices


# PLATFORM_FALLBACK (see auction_finder.py's version of this comment): if a
# live run shows JSON-LD isn't present, this regex targets the markup eBay's
# search-result cards have historically used (class="s-item__price">$NN.NN).
# Confirm/replace against real markup - see module docstring.
_PRICE_FALLBACK_RE = re.compile(r'class="s-item__price"[^>]*>[^$]*\$\s?([\d,]+\.\d{2})')


def _extract_fallback_prices(page):
    out = []
    for m in _PRICE_FALLBACK_RE.finditer(page):
        try:
            out.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return out


def _stats(prices):
    prices = sorted(p for p in prices if p >= MIN_PRICE)[:MAX_COMPS]
    if len(prices) < 2:
        return None
    n = len(prices)
    median = statistics.median(prices)
    low = prices[max(0, round(n * 0.25) - 1)]
    high = prices[min(n - 1, round(n * 0.75))]
    return {
        "n": n,
        "median": round(median, 2),
        "low": round(min(low, median), 2),
        "high": round(max(high, median), 2),
    }


def lookup(query, notes=None):
    """Return {"n", "median", "low", "high"} from recent eBay sold listings
    for `query`, or None if nothing usable came back. Caches the last
    successful result per query and falls back to it on failure, same
    resilience pattern as auction_finder.py's per-platform caching."""
    notes = notes if notes is not None else []
    cache_path = os.path.join(CACHE_DIR, f"ebay_{_cache_key(query)}.json")

    url = search_url(query)
    code, page = fetch(url, headers=UA)
    prices = []
    if code == 403:
        notes.append(f"[ebay] {query!r}: 403 BLOCKED")
    elif not page:
        notes.append(f"[ebay] {query!r}: empty (code {code})")
    else:
        prices = _extract_jsonld_prices(page)
        how = "json-ld"
        if not prices:
            prices = _extract_fallback_prices(page)
            how = "fallback-regex"
        if prices:
            notes.append(f"[ebay] {query!r}: {len(prices)} sold prices via {how}")
        else:
            notes.append(
                f"[ebay] {query!r}: 0 prices found (page {len(page)}b) -- "
                f"needs a markup check, see module docstring"
            )

    result = _stats(prices)
    if result:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh)
        return result

    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as fh:
            cached = json.load(fh)
        notes.append(f"[ebay] {query!r}: using cached comps ({cached.get('n')} samples)")
        return cached

    return None


if __name__ == "__main__":
    import sys as _sys
    q = " ".join(_sys.argv[1:]) or "Kirby vacuum"
    n = []
    print(f"searching eBay sold listings for {q!r}...")
    print(lookup(q, notes=n))
    for line in n:
        print(" ", line)
