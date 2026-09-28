#!/usr/bin/env python3
"""
watchlist_test.py - test watchlist keywords against REAL auction titles
before committing them, so false positives show up here instead of on the
site.

Why this exists: every watchlist false positive so far was found the hard
way, after shipping - a bare "truck" matched a truck TOOLBOX, "tundra" a
YETI cooler, "308" a lot number. The close-price history now holds
thousands of real Musick titles, which makes a proper test corpus. This
uses auction_finder.group_matches(), the exact live matching rules.

Corpus: every title in research/price_history/*.jsonl (closed lots) plus
data/auction_lots.yaml (the live snapshot), de-duplicated.

Usage:
    python scripts/watchlist_test.py                       # every group: match counts
    python scripts/watchlist_test.py pistol_backcountry    # one group: all matching titles
    python scripts/watchlist_test.py --try "hellcat,p365" --exclude "dodge"
                                                           # draft keywords, no file edit
    python scripts/watchlist_test.py --diff pistol_backcountry --try "p365,ec9s"
                                                           # what a change adds/drops

No network access - reads local files only.
"""

import argparse
import glob
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auction_finder import WATCHLIST, group_matches  # noqa: E402

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HISTORY_GLOB = os.path.join(_ROOT, "research", "price_history", "*.jsonl")
LOTS_PATH = os.path.join(_ROOT, "data", "auction_lots.yaml")


def load_corpus():
    """[(title, source)] - closed-lot titles first, then live ones, deduped
    on title so a lot seen both live and closed counts once."""
    seen, out = set(), []
    for path in sorted(glob.glob(HISTORY_GLOB)):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    t = json.loads(line).get("title")
                except json.JSONDecodeError:
                    continue
                if t and t not in seen:
                    seen.add(t)
                    out.append((t, "closed"))
    try:
        with open(LOTS_PATH, encoding="utf-8") as f:
            for lot in (yaml.safe_load(f) or {}).get("lots") or []:
                t = lot.get("title")
                if t and t not in seen:
                    seen.add(t)
                    out.append((t, "live"))
    except (OSError, yaml.YAMLError):
        pass
    return out


def matches(group, corpus):
    return [(t, src) for t, src in corpus if group_matches(group, f" {t} ".lower())]


def _split(s):
    return [k.strip() for k in (s or "").split(",") if k.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("group", nargs="?", help="watchlist group id to list matches for")
    ap.add_argument("--try", dest="try_kw", help="comma-separated draft keywords")
    ap.add_argument("--exclude", help="comma-separated draft exclude terms")
    ap.add_argument("--diff", metavar="GROUP_ID",
                    help="compare --try/--exclude against this existing group")
    args = ap.parse_args(argv)

    corpus = load_corpus()
    by_id = {g.get("id"): g for g in WATCHLIST}
    print(f"corpus: {len(corpus)} unique real titles "
          f"({sum(s == 'closed' for _, s in corpus)} closed, "
          f"{sum(s == 'live' for _, s in corpus)} live)\n")

    if args.try_kw:
        draft = {"keywords": _split(args.try_kw), "exclude": _split(args.exclude)}
        new = matches(draft, corpus)
        if args.diff:
            old_group = by_id.get(args.diff)
            if not old_group:
                sys.exit(f"no group with id {args.diff!r}")
            old = matches(old_group, corpus)
            old_t, new_t = {t for t, _ in old}, {t for t, _ in new}
            print(f"{args.diff}: {len(old_t)} now -> {len(new_t)} with draft")
            for label, ts in (("ADDED", new_t - old_t), ("DROPPED", old_t - new_t)):
                print(f"\n{label} ({len(ts)}):")
                for t in sorted(ts):
                    print(f"  {t}")
        else:
            print(f"draft matches {len(new)} title(s):")
            for t, src in new:
                print(f"  [{src}] {t}")
        return 0

    if args.group:
        g = by_id.get(args.group)
        if not g:
            sys.exit(f"no group with id {args.group!r} (ids: {', '.join(by_id)})")
        found = matches(g, corpus)
        print(f"{args.group} ({g['label']}): {len(found)} match(es)")
        for t, src in found:
            print(f"  [{src}] {t}")
        return 0

    for gid, g in by_id.items():
        print(f"  {len(matches(g, corpus)):>5}  {gid}  ({g['label']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
