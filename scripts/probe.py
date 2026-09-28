#!/usr/bin/env python3
"""
probe.py - render one or more catalog/lot pages locally, for writing parsers
against real markup without going through GitHub Actions.

Why this exists: live-markup probing used to mean dispatching the
auction-monitor workflow's `probe_url` input, which force-pushes the
rendered HTML to a public `debug/auction-html` branch - a workaround for a
dev-sandbox network policy that blocks the auction sites outright. Running
from your own PC is faster (no workflow-dispatch round trip), lets you probe
several URLs in one sitting, and - since raw pages can carry bidder
handles - keeps the dumps private in a gitignored `.debug/` folder instead of
on a public branch.

`probe_url` in .github/workflows/auction-monitor.yml still exists, but only
for a final check: does this work from GitHub's own datacenter IPs, not just
a residential connection? eBay in particular is believed to 403 datacenter
IPs while allowing residential ones, so a local probe succeeding here is not
proof the daily pipeline will succeed there.

Reuses render_catalog_page() from musick_render.py - no Playwright logic is
reimplemented here.

Usage:
    python scripts/probe.py URL [URL ...] [--out .debug]

Needs: pip install playwright && playwright install chromium
"""

import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SLEEP = 2.0  # polite gap between probes, matches auction_finder.py/car_finder.py


def _slugify(url, max_len=80):
    """Turn a URL into a filesystem-safe slug: host + path + query, stripped
    of scheme/punctuation the filesystem won't like, capped to max_len."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}{parsed.query}"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-").lower()
    return slug[:max_len] or "url"


def probe_one(url, out_dir, render_catalog_page):
    """Render a single URL, write the HTML + a log line, print XHR/fetch
    calls. Returns True on success, False on failure."""
    print(f"probing {url} ...")
    html, api_calls = render_catalog_page(url)

    now = datetime.datetime.now(datetime.timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")
    iso = now.isoformat()

    if html is None:
        print(f"  FAILED: {url}")
        with open(os.path.join(out_dir, "probe.log"), "a", encoding="utf-8") as f:
            f.write(f"{iso}\t{url}\tFAILED\t0 bytes\t{len(api_calls)} xhr\t-\n")
        return False

    slug = _slugify(url)
    filename = f"{ts}_{slug}.html"
    out_path = os.path.join(out_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  got {len(html)} bytes, {len(api_calls)} XHR/fetch call(s):")
    for c in api_calls:
        print(f"    {c['method']} {c['url']}")
    print(f"  wrote {out_path}")

    with open(os.path.join(out_dir, "probe.log"), "a", encoding="utf-8") as f:
        f.write(f"{iso}\t{url}\t{len(html)} bytes\t{len(api_calls)} xhr\t{filename}\n")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Render one or more URLs with a real headless browser "
        "and dump the HTML + XHR/fetch log locally, for writing parsers "
        "against real markup without a GitHub Actions round trip."
    )
    parser.add_argument("urls", nargs="+", help="URL(s) to render")
    parser.add_argument(
        "--out", default=".debug", help="output directory (default: .debug)"
    )
    args = parser.parse_args()

    try:
        import playwright  # noqa: F401
    except ImportError:
        print(
            "playwright not installed - "
            "pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(2)

    from musick_render import render_catalog_page

    os.makedirs(args.out, exist_ok=True)

    import time

    results = []
    for i, url in enumerate(args.urls):
        results.append(probe_one(url, args.out, render_catalog_page))
        if i < len(args.urls) - 1:
            time.sleep(SLEEP)

    succeeded = sum(1 for r in results if r)
    print(f"\n{succeeded}/{len(results)} succeeded. Log: {os.path.join(args.out, 'probe.log')}")

    if succeeded == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
