#!/usr/bin/env python3
"""
notify_rare.py - tell the owner the first time a RARE watchlist lot appears.

Rare = a group in data/auction_watchlist.yaml with `rare: true` (manual
Mustangs, Japanese dirt bikes, ski boots, Forester accessories, fly fishing).
auction_finder.normalize_lot() stamps lot["rare"]; this script opens ONE
GitHub issue per run listing the rare lots it hasn't announced before, so
GitHub's own email / mobile push does the notifying - no mail server or
secret needed beyond the workflow's built-in GITHUB_TOKEN.

Each lot is announced once: its URL is remembered in
research/auction_notified.json (committed by the workflow). Re-listed or
re-priced lots do not re-alert. Closed lots are skipped.

Usage:
    python scripts/notify_rare.py --dry-run     # print what would be posted
    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo python scripts/notify_rare.py
Without a token it prints and exits 0 (never blocks the refresh).
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import yaml

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LOTS = os.path.join(_ROOT, "data", "auction_lots.yaml")
SEEN = os.path.join(_ROOT, "research", "auction_notified.json")


def load_seen(path=SEEN):
    try:
        with open(path, encoding="utf-8") as f:
            return set(json.load(f).get("urls", []))
    except (OSError, ValueError):
        return set()


def save_seen(urls, path=SEEN):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"urls": sorted(urls)}, f, indent=1)


def is_open(lot, now=None):
    end = lot.get("auction_ends_at")
    if not end:
        return True
    now = now or datetime.now(timezone.utc)
    return datetime.fromisoformat(end.replace("Z", "+00:00")) > now


def new_rare_lots(lots, seen, now=None):
    return [
        l for l in lots
        if l.get("rare") and l.get("url") and l["url"] not in seen and is_open(l, now)
    ]


def build_issue(lots):
    n = len(lots)
    first = lots[0]["title"][:70]
    title = f"🎯 {n} new rare auction find{'s' if n != 1 else ''}: {first}"
    lines = ["Rare-group lots seen for the first time (Auction Watch):", ""]
    for l in lots:
        bid = l.get("current_bid")
        lines.append(
            f"- **[{l['title']}]({l['url']})** — "
            f"{', '.join(l.get('watchlist_matches') or [])}; "
            f"bid {'$%s' % bid if bid is not None else 'n/a'}; "
            f"closes {l.get('auction_ends_at') or 'unknown'}"
        )
    lines += ["", "Full list: https://almondfarm.us/auctions/ (🎯 Rare finds)."]
    return title, "\n".join(lines)


def post_issue(title, body, repo, token):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=json.dumps({"title": title, "body": body, "labels": ["auction-rare"]}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["html_url"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        with open(LOTS, encoding="utf-8") as f:
            lots = (yaml.safe_load(f) or {}).get("lots") or []
    except OSError:
        print("no lots file; nothing to do")
        return 0
    seen = load_seen()
    fresh = new_rare_lots(lots, seen)
    if not fresh:
        print("no new rare lots")
        return 0
    title, body = build_issue(fresh)
    print(title + "\n" + body)
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if a.dry_run or not (token and repo):
        print("\n(dry run / no token: not posted, not marked as seen)")
        return 0
    try:
        print("posted:", post_issue(title, body, repo, token))
    except Exception as e:  # never block the day's refresh over an alert
        print(f"issue post failed ({e}); will retry next run", file=sys.stderr)
        return 0
    save_seen(seen | {l["url"] for l in fresh})
    return 0


if __name__ == "__main__":
    sys.exit(main())
