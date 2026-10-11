#!/usr/bin/env python3
"""
skewer_prep.py - prep sheet generator. Give it expected covers (customers),
get back how many of each item to build, the ingredient totals, how many
potatoes to parboil the morning of, and an estimated prep time.

    python scripts/skewer_prep.py --covers 120
    python scripts/skewer_prep.py --covers 120 --lineup chorizo_piquillo:small@2,chorizo_piquillo:large@6,txuleta_beef,smashed_potato
    python scripts/skewer_prep.py --covers 120 --history     # use observed units/cover and item mix from the log

--lineup is a comma list of  item[:size][@price]. Leave it out to run every
item at its default size and menu price. Putting two sizes of one item in the
lineup runs them side by side (the item's units are split evenly between
them) - the cleanest way to compare prices, same crowd and weather.

The "units" column is your start_count for the log: `skewer_log.py open`
writes exactly these numbers into night_items.csv.
"""

import argparse
import math
from collections import defaultdict

import skewer_common as sc
import skewer_report as sr


def parse_lineup(menu, spec):
    """'item[:size][@price],...' -> [{'item', 'variant', 'price'}]. None/'' = whole menu."""
    idx = sc.index_menu(menu)
    items = {i["id"]: i for i in menu["items"]}
    if not spec:
        return [{"item": i, "variant": sc.default_variant(i), "price": sc.default_variant(i)["price"]}
                for i in menu["items"]]
    out, seen = [], set()
    for tok in (t.strip() for t in spec.split(",") if t.strip()):
        price = None
        if "@" in tok:
            tok, p = tok.split("@", 1)
            price = sc.to_num(p, "price", f"lineup {tok!r}")
        item_id, _, size = tok.partition(":")
        if item_id not in items:
            raise sc.DataError(f"lineup: unknown item {item_id!r}. Items: {', '.join(items)}")
        item = items[item_id]
        if size and (item_id, size) not in idx:
            raise sc.DataError(f"lineup: {item_id} has no size {size!r}. Sizes: "
                               f"{', '.join(x['size'] for x in item['variants'])}")
        v = idx[(item_id, size)] if size else sc.default_variant(item)
        if (item_id, v["size"]) in seen:
            raise sc.DataError(f"lineup: {item_id}/{v['size']} listed twice")
        seen.add((item_id, v["size"]))
        out.append({"item": item, "variant": v, "price": price if price is not None else v["price"]})
    return out


def plan(menu, covers, lineup, units_per_cover=None, buffer_pct=None, weights=None):
    """Quantities per lineup entry. Skewers share covers x units_per_cover by
    mix weight (or `weights` {item_id: w}); other items use attach_rate x covers.
    Items with several lineup entries split their units evenly."""
    d = menu.get("defaults", {})
    upc = units_per_cover if units_per_cover is not None else d.get("units_per_cover", 3.0)
    buf = buffer_pct if buffer_pct is not None else d.get("buffer_pct", 15)

    per_item = defaultdict(list)
    for e in lineup:
        per_item[e["item"]["id"]].append(e)
    skewer_ids = [i for i, es in per_item.items() if es[0]["item"].get("category", "skewer") == "skewer"]
    w = {i: (weights or {}).get(i, per_item[i][0]["item"].get("mix_weight", 1.0)) for i in skewer_ids}
    w_total = sum(w.values())

    rows = []
    for item_id, entries in per_item.items():
        item = entries[0]["item"]
        if item_id in w:
            expected = covers * upc * w[item_id] / w_total if w_total else 0.0
        else:
            expected = covers * item.get("attach_rate", 0.0)
        for e in entries:
            exp_v = expected / len(entries)
            units = math.ceil(round(exp_v * (1 + buf / 100), 6))
            v = e["variant"]
            rows.append({"item": item, "variant": v, "item_id": item_id, "size": v["size"],
                         "price": e["price"], "expected": exp_v, "units": units,
                         "prep_minutes": units * v.get("prep_min", 0.0)})
    return rows


def ingredient_totals(rows):
    """{(name, unit): total qty} across the plan."""
    tot = defaultdict(float)
    for r in rows:
        for ing in r["item"].get("ingredients", []):
            tot[(ing["name"], ing["unit"])] += ing["qty"] * r["variant"].get("portion", 1.0) * r["units"]
    return dict(tot)


def morning_tasks(rows):
    """Things to do before the afternoon: parboil math + any item morning_notes."""
    tasks, done = [], set()
    for r in rows:
        item, item_id = r["item"], r["item_id"]
        if item_id in done:
            continue
        done.add(item_id)
        mine = [x for x in rows if x["item_id"] == item_id]
        pb = item.get("parboil")
        if pb:
            per_unit = next((i["qty"] for i in item["ingredients"] if i["name"] == pb["ingredient"]), 0)
            raw = sum(x["units"] * per_unit * x["variant"].get("portion", 1.0) for x in mine)
            waste = pb.get("waste_pct", 0)
            count = math.ceil(round(raw * (1 + waste / 100), 6))
            tasks.append(f"PARBOIL {count / pb['per_lb']:.1f} lb {pb['ingredient']} (~{count}, incl. {waste}% "
                         f"spare) for {item['name']}: simmer until just tender (~12-15 min), drain, cool, chill "
                         "uncovered. Smash and crisp on the grill at service.")
        if item.get("morning_note"):
            tasks.append(f"{item['name'].upper()} x{sum(x['units'] for x in mine)}: {item['morning_note']}")
    return tasks


def _qty(q, unit):
    s = f"{q:,.0f}" if q >= 10 or q == int(q) else f"{q:,.1f}"
    extra = f"  (= {q / 453.6:.1f} lb)" if unit == "g" and q >= 454 else ""
    return f"{s} {unit}{extra}"


def format_sheet(menu, covers, rows, upc_note):
    d = menu.get("defaults", {})
    buf = d.get("buffer_pct", 15)
    out = [f"PREP SHEET - {covers} expected covers ({upc_note}, +{buf}% buffer)", ""]
    out.append(sc.fmt_table(
        ["item", "size", "price", "units (=start_count)", "prep min"],
        [[r["item"]["name"], r["size"], sc.money(r["price"]), r["units"], f"{r['prep_minutes']:.0f}"]
         for r in rows]))
    total_units = sum(r["units"] for r in rows)
    out.append(f"   {total_units} units total, ~{sum(r['prep_minutes'] for r in rows) / 60:.1f} hands-on hours "
               "(one person; divide by crew size).")
    tasks = morning_tasks(rows)
    out += ["", "== MORNING OF =="]
    out += [f"  [ ] {t}" for t in tasks] or ["  (nothing)"]
    out += ["", "== INGREDIENTS (total for the night) =="]
    for (name, unit), q in sorted(ingredient_totals(rows).items()):
        out.append(f"  {name:<22} {_qty(q, unit)}")
    keys = {(r["item_id"], r["size"]) for r in rows}
    flagged = sc.collect_confirms(menu, keys)
    if flagged:
        out += ["", "! Still marked `confirm` in menu.yaml (placeholders - check before trusting this sheet):"]
        out += [f"    {c}" for c in flagged]
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--covers", type=int, required=True, help="expected customers")
    p.add_argument("--lineup", default="", help="item[:size][@price],... (default: whole menu)")
    p.add_argument("--units-per-cover", type=float, help="override menu.yaml default")
    p.add_argument("--buffer-pct", type=float, help="override menu.yaml default")
    p.add_argument("--history", action="store_true",
                   help="use observed units/cover and item mix from the log")
    p.add_argument("--menu", default=sc.MENU_PATH)
    p.add_argument("--nights", default=sc.NIGHTS_PATH)
    p.add_argument("--items", default=sc.ITEMS_PATH)
    args = p.parse_args(argv)
    try:
        menu = sc.load_menu(args.menu)
        lineup = parse_lineup(menu, args.lineup)
        upc, weights = args.units_per_cover, None
        if args.history:
            nights, rows, _ = sc.load_log(args.nights, args.items)
            enriched = sr.enrich_rows(rows, nights, sc.index_menu(menu), [])
            seen = sr.demand_mix(enriched)
            skewers = {e["item"]["id"] for e in lineup if e["item"].get("category", "skewer") == "skewer"}
            if upc is None:
                upc = sr.observed_units_per_cover(enriched, nights)
            if skewers and all(seen.get(i, 0) > 0 for i in skewers):
                weights = seen
            if upc is None or weights is None:
                print("note: not enough logged history for every lineup item - using menu.yaml defaults "
                      "where history is missing.\n")
        plan_rows = plan(menu, args.covers, lineup, upc, args.buffer_pct, weights)
        used = upc if upc is not None else menu.get("defaults", {}).get("units_per_cover", 3.0)
        note = f"{used:.2f} skewers/cover" + (", mix from log" if weights else "")
        print(format_sheet(menu, args.covers, plan_rows, note))
    except sc.DataError as e:
        raise SystemExit(f"error: {e}")


if __name__ == "__main__":
    main()
