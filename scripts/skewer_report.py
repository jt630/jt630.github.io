#!/usr/bin/env python3
"""
skewer_report.py - what's working? Reads the pop-up log and prints revenue and
profit per night, units per item, sell-out rate, best sellers, and a
price/size ("arm") comparison.

    python scripts/skewer_report.py
    python scripts/skewer_report.py --nights path/nights.csv --items path/night_items.csv

Two ideas worth knowing before reading the numbers:

  * Units sold = start_count - end_count - waste. You count, the script derives.
  * A sell-out CENSORS demand: if you sold out, units is a floor, not what
    people wanted. So arms are also compared on units/hour while stocked
    (stopped at the sell-out time), which is fair between a $2 small that
    sold out at 12:30 and a $6 large that lasted the night.
"""

import argparse
from collections import defaultdict

import skewer_common as sc

MIN_NIGHTS = 3  # fewer nights per arm than this is an anecdote, not a result


def enrich_rows(rows, nights, idx, warnings):
    """Add derived fields to each item row."""
    out = []
    for r in rows:
        night = nights[r["night"]]
        v = idx.get((r["item"], r["size"]))
        if v is None:
            warnings.append(f"{r['night']}: {r['item']}/{r['size']} isn't in menu.yaml - cost counted as $0")
        cost = v["cost"] if v else 0.0
        units = r["start"] - r["end"] - r["waste"]
        sold_out = r["end"] == 0
        if r["sold_out_time"] and not sold_out:
            warnings.append(f"{r['night']} {r['item']}/{r['size']}: has a sold_out_time but end_count is {r['end']}")
        mins = sc.minutes_after(night.get("start"), r["sold_out_time"] if r["sold_out_time"] and sold_out
                                else night.get("end"))
        hours = mins / 60 if mins else None
        out.append({**r, "units": units, "sold_out": sold_out,
                    "category": v["category"] if v else "unknown",
                    "revenue": units * r["price"],
                    "cogs": (r["start"] - r["end"]) * cost,  # waste was paid for too
                    "hours": hours,
                    "rate": units / hours if hours else None})
    return out


def night_summary(enriched, nights, discount):
    by_night = defaultdict(list)
    for e in enriched:
        by_night[e["night"]].append(e)
    out = []
    for nid in sorted(by_night):
        n, items = nights[nid], by_night[nid]
        units = sum(e["units"] for e in items)
        bundles = sc.to_num(n.get("bundles_sold"), "bundles_sold", nid, default=0, integer=True)
        est = sum(e["revenue"] for e in items) - bundles * discount
        gross = sc.to_num(n.get("gross_sales"), "gross_sales", nid)
        revenue = gross if gross is not None else est
        cogs = sum(e["cogs"] for e in items)
        fee = sc.to_num(n.get("venue_fee"), "venue_fee", nid, default=0.0)
        labor = sc.to_num(n.get("labor"), "labor", nid, default=0.0)
        covers = sc.to_num(n.get("covers"), "covers", nid, integer=True)
        out.append({"night": nid, "venue": n.get("venue", ""), "units": units,
                    "revenue": revenue, "revenue_source": "actual" if gross is not None else "est",
                    "cogs": cogs, "profit": revenue - cogs - fee - labor,
                    "covers": covers,
                    "units_per_cover": units / covers if covers else None,
                    "wait": sc.to_num(n.get("avg_wait_min"), "avg_wait_min", nid),
                    "weather": n.get("weather", "")})
    return out


def item_summary(enriched):
    acc = defaultdict(lambda: {"units": 0, "revenue": 0.0, "cogs": 0.0, "item_nights": 0, "sold_out": 0})
    for e in enriched:
        a = acc[e["item"]]
        a["units"] += e["units"]
        a["revenue"] += e["revenue"]
        a["cogs"] += e["cogs"]
        a["item_nights"] += 1
        a["sold_out"] += e["sold_out"]
    out = [{"item": k, **a, "margin": a["revenue"] - a["cogs"],
            "sellout_rate": a["sold_out"] / a["item_nights"]} for k, a in acc.items()]
    return sorted(out, key=lambda x: (-x["units"], x["item"]))


def sellout_rate(enriched):
    """Share of item-nights that ended at zero. None if nothing counted."""
    if not enriched:
        return None
    return sum(e["sold_out"] for e in enriched) / len(enriched)


def arm_summary(enriched):
    """Group by (item, size, price) - the thing being tested."""
    groups = defaultdict(list)
    for e in enriched:
        groups[(e["item"], e["size"], e["price"])].append(e)
    out = []
    for (item, size, price), es in groups.items():
        units = sum(e["units"] for e in es)
        started = sum(e["start"] for e in es)
        timed = [e for e in es if e["hours"]]
        revenue = sum(e["revenue"] for e in es)
        margin = revenue - sum(e["cogs"] for e in es)
        t_hours = sum(e["hours"] for e in timed)
        t_units = sum(e["units"] for e in timed)
        out.append({"item": item, "size": size, "price": price, "nights": len(es),
                    "units": units, "sell_through": units / started if started else 0.0,
                    "sold_out_nights": sum(e["sold_out"] for e in es),
                    "rate": t_units / t_hours if t_hours else None,
                    "revenue": revenue, "margin": margin,
                    "margin_per_hour": (sum(e["revenue"] - e["cogs"] for e in timed) / t_hours
                                        if t_hours else None)})
    return sorted(out, key=lambda x: (x["item"], x["price"], x["size"]))


def demand_mix(enriched):
    """{item_id: total units sold} - the observed mix across all counted nights."""
    mix = defaultdict(int)
    for e in enriched:
        mix[e["item"]] += e["units"]
    return dict(mix)


def observed_units_per_cover(enriched, nights):
    """Skewer units / covers over nights that logged covers. None if no data."""
    units = defaultdict(int)
    for e in enriched:
        if e["category"] == "skewer":
            units[e["night"]] += e["units"]
    tot_u = tot_c = 0
    for nid, u in units.items():
        c = sc.to_num(nights[nid].get("covers"), "covers", nid, integer=True)
        if c:
            tot_u += u
            tot_c += c
    return tot_u / tot_c if tot_c else None


def _pct(x):
    return "-" if x is None else f"{x * 100:.0f}%"


def _num(x, d=1):
    return "-" if x is None else f"{x:.{d}f}"


def format_report(menu, nights, rows, load_warnings):
    idx = sc.index_menu(menu)
    warnings = list(load_warnings)
    enriched = enrich_rows(rows, nights, idx, warnings)
    if not enriched:
        msg = ["No counted nights yet - see 'How to log a night' in SKEWER-POPUP.md."]
        return "\n".join(msg + [f"  ! {w}" for w in warnings])

    out = []
    ns = night_summary(enriched, nights, sc.bundle_discount(menu))
    out += ["== NIGHTS ==", sc.fmt_table(
        ["night", "venue", "covers", "units", "revenue", "cogs", "profit", "wait", "weather"],
        [[n["night"], n["venue"], n["covers"] if n["covers"] is not None else "-", n["units"],
          sc.money(n["revenue"]) + ("*" if n["revenue_source"] == "est" else ""),
          sc.money(n["cogs"]), sc.money(n["profit"]),
          _num(n["wait"], 0) if n["wait"] is not None else "-", n["weather"]] for n in ns])]
    out.append("   * = estimated from units x price (less bundle discount); no gross_sales logged."
               " profit = revenue - cogs - venue_fee - labor.")
    total_rev, total_profit = sum(n["revenue"] for n in ns), sum(n["profit"] for n in ns)
    out.append(f"   total: {len(ns)} night(s), revenue {sc.money(total_rev)}, profit {sc.money(total_profit)}"
               f" (avg {sc.money(total_profit / len(ns))}/night)")

    items = item_summary(enriched)
    out += ["", "== UNITS PER ITEM (best sellers first) ==", sc.fmt_table(
        ["item", "units", "revenue", "margin", "sold out", "sell-out rate"],
        [[i["item"], i["units"], sc.money(i["revenue"]), sc.money(i["margin"]),
          f"{i['sold_out']}/{i['item_nights']}", _pct(i["sellout_rate"])] for i in items])]
    out.append(f"   overall sell-out rate: {_pct(sellout_rate(enriched))} of item-nights ended at zero")
    best_margin = max(items, key=lambda i: i["margin"])
    out.append(f"   best by units: {items[0]['item']}   best by margin $: {best_margin['item']}")

    arms = arm_summary(enriched)
    out += ["", "== PRICE / SIZE ARMS ==", sc.fmt_table(
        ["arm", "nights", "units", "sell-thru", "sold out", "units/hr", "margin", "margin/hr"],
        [[f"{a['item']}/{a['size']} @{sc.money(a['price'])}", a["nights"], a["units"],
          _pct(a["sell_through"]), f"{a['sold_out_nights']}/{a['nights']}",
          _num(a["rate"]), sc.money(a["margin"]),
          sc.money(a["margin_per_hour"]) if a["margin_per_hour"] is not None else "-"] for a in arms])]
    out.append("   units/hr = units / hours stocked (to the sell-out time if sold out, else to close).")
    if any(a["sold_out_nights"] for a in arms):
        out.append("   NOTE: where an arm sold out, units is a floor on demand - compare units/hr, not units.")
    thin = [a for a in arms if a["nights"] < MIN_NIGHTS]
    if thin:
        out.append(f"   NOTE: {len(thin)} arm(s) have fewer than {MIN_NIGHTS} nights - treat as a hint, not a result."
                   " Running arms side by side on the same night controls for crowd and weather.")

    upc = observed_units_per_cover(enriched, nights)
    if upc is not None:
        out.append(f"\nObserved: {upc:.2f} skewer units per cover (sell-outs make this a floor)."
                   " Feed it to skewer_prep.py with --history.")

    flagged = [c for c in sc.collect_confirms(menu, {(e["item"], e["size"]) for e in enriched})
               if "cost" in c or c.startswith("defaults")]
    if flagged:
        out.append("\n! Costs still marked `confirm` in menu.yaml - profit is only as good as these:")
        out += [f"    {c}" for c in flagged if not c.startswith("defaults")]
    if warnings:
        out += ["", "Warnings:"] + [f"  ! {w}" for w in warnings]
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--menu", default=sc.MENU_PATH)
    p.add_argument("--nights", default=sc.NIGHTS_PATH)
    p.add_argument("--items", default=sc.ITEMS_PATH)
    args = p.parse_args(argv)
    try:
        menu = sc.load_menu(args.menu)
        nights, rows, warnings = sc.load_log(args.nights, args.items)
        print(format_report(menu, nights, rows, warnings))
    except sc.DataError as e:
        raise SystemExit(f"error: {e}")


if __name__ == "__main__":
    main()
