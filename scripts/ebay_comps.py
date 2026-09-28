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


# QUERY_NORMALIZE: real auction titles look nothing like an eBay search query -
# "Lot #5012: Large Gold-Tone Rope Chain Necklace With Circular Abalone Shell
# Pendant, Hammered Finish" or "2017 FORD F-550 - BLUETOOTH!" - a lot-number
# prefix, shouty trailing feature call-outs, and 10-20 words. eBay's sold
# search is a keyword AND-match over the listing title, so a 15-word query
# matches almost nothing even when eBay isn't actively blocking us (see the
# module docstring) - that's a second, independent cause of "0 prices found"
# worth ruling out on its own. This trims each title down to the handful of
# tokens that actually identify the item (brand, model number, year, caliber,
# karat, size) before it ever reaches search_url()/lookup(), the same way a
# human would shorten the title before pasting it into eBay's search box.
MAX_QUERY_TOKENS = 6

_LOT_PREFIX_RE = re.compile(r"^\s*lot\s*#?\s*\d+\s*[:\-]?\s*", re.IGNORECASE)

# Whole phrases that are sale-condition/marketing noise, not part of the
# item's identity, wherever they land in the title (not just after a dash).
_NOISE_PHRASES = (
    "local police agency",
    "government surplus",
    "bank repo",
    "buyers assurance policy",
    "fully functional",
    "release series",
    "offsite",
)

# Filler/connective words with ~zero search signal. Deliberately does NOT
# include "new" - "new in box" is a meaningful condition claim, per spec.
_STOPWORDS = {
    "with", "and", "the", "a", "an", "of", "for", "in", "on", "w",
    "large", "small", "set", "lot", "assorted", "misc", "miscellaneous",
}

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# A token that's basically a number - year, caliber (".308"), karat ("14k"),
# ct weight ("3.25ct"), size ("4x4"), hyphenated caliber (".30-06") - keeps
# any internal decimal point or hyphen; anything else has its stray dots
# stripped in the cleanup pass below (hyphens are handled separately, see
# normalize_query).
_NUMERIC_TOKEN_RE = re.compile(r"^\.?\d+(?:[.\-]\d+)*[a-z]*$")


def normalize_query(title):
    """Turn a raw auction lot title into a short eBay search query.

    Strips the `Lot #N:` prefix, drops sale-type/marketing noise ("LOCAL
    POLICE AGENCY", "GOVERNMENT SURPLUS", "BANK REPO", trailing shouted
    features like "- BLUETOOTH!"), lowercases and collapses punctuation
    (while preserving decimal points inside numbers, so ".308" and "3.25ct"
    survive intact, and preserving hyphens inside alphanumeric tokens that
    contain a digit, so ".30-06", ".30-30" and "F-550" survive as eBay would
    expect them written - a hyphen in a plain word compound like
    "Gold-Tone" or "Bolt-Action" still splits into two words), drops
    low-signal filler words, and caps the result at MAX_QUERY_TOKENS tokens
    (a hyphenated caliber/model token like ".30-06" counts as one token
    toward that cap). Deterministic and stdlib-only (`re`) so it never needs
    network access or an extra dependency to run or test.

    Returns "" if nothing identifying is left (e.g. the title was only a lot
    number) - callers should treat that as "skip the lookup", never send an
    empty query to eBay's search.
    """
    if not title:
        return ""

    text = _LOT_PREFIX_RE.sub("", title)

    for phrase in _NOISE_PHRASES:
        text = re.sub(re.escape(phrase), " ", text, flags=re.IGNORECASE)

    # "2017 FORD F-550 - BLUETOOTH!" / "... - LOCAL POLICE AGENCY! 75K MILES!"
    # - a " - " almost always separates the item's identity (make/model/year)
    # from a shouted feature or sale-type call-out tacked on after it. Keep
    # whichever segment(s) carry a 4-digit year (the identity), or fall back
    # to the first segment when no segment has one (most non-vehicle lots).
    segments = [s.strip() for s in re.split(r"\s+-\s+", text) if s.strip()]
    if len(segments) > 1:
        dated = [s for s in segments if _YEAR_RE.search(s)]
        segments = dated if dated else segments[:1]
    text = " ".join(segments)

    # Collapse everything except letters/digits/dots/hyphens/whitespace to
    # spaces, then lowercase. Dots and hyphens both survive this pass - the
    # per-token step below decides which hyphens were actually meaningful
    # (".30-06", "f-550") versus a word-compound split ("gold-tone").
    text = re.sub(r"[^a-zA-Z0-9.\-\s]+", " ", text).lower()

    tokens = []
    for raw in text.split():
        # A hyphen between two alphanumeric halves stays put when the whole
        # token has a digit in it somewhere - that's a caliber ("f-550",
        # ".30-06", ".30-30") or a model number ("lr-60p"), and eBay expects
        # it written that way, not as two separate words. A hyphen with no
        # digit anywhere in the token is a plain word compound ("gold-tone",
        # "bolt-action") and splits into its two words as before.
        if "-" in raw and re.search(r"\d", raw):
            parts = [raw]
        else:
            parts = raw.split("-")

        for tok in parts:
            if _NUMERIC_TOKEN_RE.match(tok):
                pass  # numeric-ish (year/caliber/karat/ct/size) - keep as-is
            else:
                tok = tok.replace(".", "")
            if not tok or tok in _STOPWORDS:
                continue
            tokens.append(tok)

    return " ".join(tokens[:MAX_QUERY_TOKENS])


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


def lookup(raw_query, notes=None):
    """Return {"n", "median", "low", "high"} from recent eBay sold listings
    for `raw_query` (a raw lot title, or an already-short query - either
    works), or None if nothing usable came back. Runs `raw_query` through
    normalize_query() first, so both the cache key and the search URL are
    built from the short form, not the raw 15-word auction title - see
    normalize_query()'s docstring for why. Caches the last successful result
    per normalized query and falls back to it on failure, same resilience
    pattern as auction_finder.py's per-platform caching."""
    notes = notes if notes is not None else []
    query = normalize_query(raw_query)
    if not query:
        notes.append(f"[ebay] {raw_query!r}: normalized to an empty query, skipping lookup")
        return None
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
