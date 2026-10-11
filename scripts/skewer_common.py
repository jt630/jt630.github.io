#!/usr/bin/env python3
"""
skewer_common.py - shared loaders and helpers for the Boise skewer pop-up
experiment. Spec and how-to: SKEWER-POPUP.md.

Data model (all under research/skewer_popup/):

    menu.yaml        what you sell: items, size/price variants, ingredients, costs
    nights.csv       one row per pop-up night (venue, hours, covers, fees, ...)
    night_items.csv  one row per night x item x size x price: start_count,
                     end_count, waste, sold_out_time

You only ever record what you cannot derive. Units sold, revenue, cost,
sell-through and sell-out are all computed from start/end counts + menu.yaml.

Times are 24h "HH:MM" ("23:30", "01:15"); 12h like "11:30pm" also parses. A
time earlier than the night's start is read as after midnight.
"""

import csv
import os
from datetime import datetime

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "research", "skewer_popup")
MENU_PATH = os.path.join(DATA_DIR, "menu.yaml")
NIGHTS_PATH = os.path.join(DATA_DIR, "nights.csv")
ITEMS_PATH = os.path.join(DATA_DIR, "night_items.csv")

NIGHT_COLS = ["night", "venue", "start", "end", "covers", "avg_wait_min", "weather",
              "venue_fee", "labor", "bundles_sold", "gross_sales", "notes"]
ITEM_COLS = ["night", "item", "size", "price", "start_count", "end_count",
             "waste", "sold_out_time"]


class DataError(ValueError):
    """Bad input data. The message says which row/field and how to fix it."""


# ---------------------------------------------------------------- times


def parse_time(s):
    """'23:30' / '1:15' / '11:30pm' / '11pm' -> minutes since midnight. Blank -> None."""
    s = (s or "").strip().lower().replace(" ", "")
    if not s:
        return None
    for fmt in ("%H:%M", "%I:%M%p", "%I%p"):
        try:
            t = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return t.hour * 60 + t.minute
    raise DataError(f"can't read time {s!r} - use 24h HH:MM, e.g. 23:30 or 01:15")


def minutes_after(start, later):
    """Minutes from `start` to `later`, wrapping past midnight. None if either is blank."""
    a, b = parse_time(start), parse_time(later)
    if a is None or b is None:
        return None
    return (b - a) % 1440


# ---------------------------------------------------------------- numbers


def to_num(value, field, where, default=None, integer=False):
    s = (str(value) if value is not None else "").strip().lstrip("$")
    if s == "":
        return default
    try:
        n = float(s)
    except ValueError:
        raise DataError(f"{where}: {field} should be a number, got {value!r}") from None
    return int(round(n)) if integer else n


# ---------------------------------------------------------------- menu


def load_menu(path=MENU_PATH):
    with open(path, encoding="utf-8") as f:
        menu = yaml.safe_load(f)
    if not isinstance(menu, dict) or not menu.get("items"):
        raise DataError(f"{path}: no items found")
    ids = [i["id"] for i in menu["items"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise DataError(f"{path}: duplicate item ids {sorted(dupes)}")
    for item in menu["items"]:
        if not item.get("variants"):
            raise DataError(f"{path}: item {item['id']} has no variants")
    return menu


def index_menu(menu):
    """{(item_id, size): variant dict merged with its item's name/category/item}."""
    idx = {}
    for item in menu["items"]:
        for v in item["variants"]:
            key = (item["id"], v["size"])
            if key in idx:
                raise DataError(f"menu: duplicate variant {item['id']}/{v['size']}")
            idx[key] = {**v, "item_id": item["id"], "name": item["name"],
                        "category": item.get("category", "skewer"), "item": item}
    return idx


def default_variant(item):
    for v in item["variants"]:
        if v.get("default"):
            return v
    return item["variants"][0]


def bundle_discount(menu):
    """Dollars knocked off per bundle sold (3 x $4 regular - $10 = $2)."""
    b = menu.get("bundle")
    if not b:
        return 0.0
    return b["count"] * b["regular_price"] - b["price"]


def collect_confirms(menu, keys=None):
    """Human-readable list of menu fields still marked `confirm`.
    keys: restrict to these (item_id, size) variants; None = whole menu."""
    out = []
    d = menu.get("defaults", {})
    if d.get("confirm"):
        out.append(f"defaults: {', '.join(d['confirm'])}")
    for item in menu["items"]:
        for v in item["variants"]:
            if keys is not None and (item["id"], v["size"]) not in keys:
                continue
            flagged = list(v.get("confirm", []))
            flagged += [f for f in item.get("confirm", []) if f not in flagged]
            if flagged:
                out.append(f"{item['id']}/{v['size']}: {', '.join(flagged)}")
    return out


# ---------------------------------------------------------------- csv


def read_csv(path, required):
    """List of stripped row dicts; [] if the file is missing. Checks the header."""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if reader.fieldnames and missing:
            raise DataError(f"{path}: missing column(s) {missing}")
        rows = []
        for r in reader:
            r = {k: (v or "").strip() for k, v in r.items() if k is not None}
            if any(r.values()):
                rows.append(r)
        return rows


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def append_csv(path, fieldnames, rows):
    """Append rows, writing the header first if the file is new/empty."""
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    needs_newline = False
    if not new:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            needs_newline = f.read(1) not in (b"\n", b"\r")
    with open(path, "a", newline="", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def load_log(nights_path=NIGHTS_PATH, items_path=ITEMS_PATH):
    """-> (nights {id: row}, item rows [dict], warnings [str]).

    Item rows get numeric fields parsed. Rows with a blank end_count are
    skipped (the night isn't counted yet) and reported as a warning.
    Impossible rows (sold more than you started with) raise DataError.
    """
    nights = {}
    for r in read_csv(nights_path, NIGHT_COLS[:1]):
        if r["night"] in nights:
            raise DataError(f"{nights_path}: night {r['night']!r} appears twice")
        nights[r["night"]] = r

    warnings, rows = [], []
    for r in read_csv(items_path, ITEM_COLS[:3] + ["start_count", "end_count"]):
        where = f"{r['night']} {r['item']}/{r.get('size') or 'standard'}"
        if r["night"] not in nights:
            raise DataError(f"{where}: night {r['night']!r} is not in nights.csv")
        if r.get("end_count", "") == "":
            warnings.append(f"{where}: no end_count yet - skipped (run skewer_log.py close)")
            continue
        start = to_num(r["start_count"], "start_count", where, integer=True)
        end = to_num(r["end_count"], "end_count", where, integer=True)
        waste = to_num(r.get("waste"), "waste", where, default=0, integer=True)
        price = to_num(r.get("price"), "price", where)
        if start is None or price is None:
            raise DataError(f"{where}: start_count and price are required")
        if min(start, end, waste) < 0 or end + waste > start:
            raise DataError(
                f"{where}: start {start}, left {end}, waste {waste} doesn't add up "
                "(left + waste can't exceed start)")
        sot = r.get("sold_out_time") or None
        parse_time(sot)  # validate
        rows.append({"night": r["night"], "item": r["item"], "size": r.get("size") or "standard",
                     "price": price, "start": start, "end": end, "waste": waste,
                     "sold_out_time": sot})
    return nights, rows, warnings


# ---------------------------------------------------------------- display


def fmt_table(headers, rows):
    """Plain-text table; first column left-aligned, the rest right-aligned."""
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    def line(cells):
        return "  ".join(c.ljust(widths[i]) if i == 0 else c.rjust(widths[i])
                         for i, c in enumerate(cells))
    return "\n".join([line(headers), "  ".join("-" * w for w in widths)]
                     + [line(r) for r in rows])


def money(x):
    return f"-${-x:,.2f}" if x < 0 else f"${x:,.2f}"
