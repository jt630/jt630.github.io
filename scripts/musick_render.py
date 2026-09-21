#!/usr/bin/env python3
"""
musick_render.py - render bid.musickauction.com catalog pages with a real
headless browser (Playwright + Chromium), since a plain HTTP GET returns an
empty HTTP 202 response - CONFIRMED via a live debug run (auction_finder.py's
fetch_musick_catalog(), before this file existed), not guessed. That pattern
is the signature of a JavaScript-rendered single-page app: the real content
never arrives in urllib's response at all, no matter how the parser is
written, so this exists to actually load the page the way a browser would.

While it's in there anyway, render_catalog_page() also logs every XHR/fetch
request the page makes while loading. Most SPAs like this one populate
themselves by calling a JSON API under the hood - if that API is visible
and doesn't itself require a browser to call, it would let a future version
of this drop Playwright entirely and go back to a plain, fast, cheap
request, the way every other platform in this repo works. This is the one
chance to actually see that traffic instead of guessing at it.

Needs the `playwright` package plus its Chromium browser installed
(`pip install playwright && playwright install --with-deps chromium`) -
handled in .github/workflows/auction-monitor.yml's "Install dependencies"
step. NOT available for live testing in whatever dev sandbox this was
written in: bid.musickauction.com is blocked by that sandbox's network
policy regardless of fetch method (confirmed via the same egress-proxy
check used throughout this repo's auction tooling), so this code has only
been smoke-tested by rendering a *reachable* page (musickauction.com
itself) to confirm Playwright launches and returns real content - never
against the actual target. Same debug-and-inspect process as everything
else here: dispatch the workflow with debug_html: true, read what
debug_html/musick_catalog__*.html actually contains (and the captured
XHR/fetch log in the job's fetch notes), and write a real per-item parser
against it (see PLATFORM_FALLBACK-style comment in auction_finder.py's
fetch_musick_catalog()).

Usage (as a library, called from auction_finder.py):
    from musick_render import render_catalog_page
    html, api_calls = render_catalog_page(url)
    # html: fully rendered HTML, or None on failure
    # api_calls: [{"url", "method"}, ...] for every XHR/fetch request seen
"""

import sys

RENDER_TIMEOUT_MS = 20000
UA_STRING = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def render_catalog_page(url, wait_selector=None):
    """Load `url` in headless Chromium, wait for the network to go idle (or
    an optional CSS selector to appear), and return (html, api_calls).
    Returns (None, []) on any failure - not installed, timeout, crash -
    never raises, matching the rest of this codebase's graceful-degrade
    pattern (the caller falls back to whatever it already has, same as a
    403 or an empty response from a plain fetch())."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.stderr.write("  [musick_render] playwright not installed - "
                          "pip install playwright && playwright install chromium\n")
        return None, []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=UA_STRING)
                api_calls = []

                def _on_request(request):
                    # xhr/fetch = the page's own JS calling out for data,
                    # as opposed to images/css/fonts/the doc itself - the
                    # thing worth looking at for a hidden JSON API.
                    if request.resource_type in ("xhr", "fetch"):
                        api_calls.append({"url": request.url, "method": request.method})

                page.on("request", _on_request)
                page.goto(url, timeout=RENDER_TIMEOUT_MS, wait_until="networkidle")
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=RENDER_TIMEOUT_MS)
                    except Exception:
                        pass  # take whatever rendered rather than failing outright
                return page.content(), api_calls
            finally:
                browser.close()
    except Exception as e:
        sys.stderr.write(f"  [musick_render] {url}: {e}\n")
        return None, []


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.musickauction.com/auctions/"
    print(f"rendering {url} ...")
    html, api_calls = render_catalog_page(url)
    print(f"got {len(html) if html else 0} bytes" if html else "render failed")
    print(f"{len(api_calls)} XHR/fetch call(s) seen:")
    for c in api_calls:
        print(f"  {c['method']} {c['url']}")
