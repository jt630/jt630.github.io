#!/usr/bin/env python3
"""
skewer_log.py - the low-effort way to log a night. Two commands:

    # BEFORE service: creates the night + one row per item with the planned
    # start_count and price already filled in
    python scripts/skewer_log.py open --night 2026-10-16 --venue "Brewery A" \\
        --start 23:00 --covers 120 [--lineup chorizo_piquillo:small@2,chorizo_piquillo:large@6,...]

    # AFTER service: asks "how many left?" for each item, then the night-level
    # numbers. Press Enter to skip anything you don't know.
    python scripts/skewer_log.py close --night 2026-10-16

--covers on `open` is only used to size the start counts (same math as
skewer_prep.py). The `covers` column in nights.csv is the ACTUAL count and is
asked for at `close`. If you change a start count on the night, edit the CSV.
Night ids are free text; use the date, and add a suffix for a second venue
(2026-10-16-bar).
"""

import argparse
import csv

import skewer_common as sc
import skewer_prep as sp


def open_night(menu, nights_path, items_path, night, venue, start, covers, lineup_spec="",
               units_per_cover=None, buffer_pct=None):
    """Append the night and its pre-filled item rows. Returns the plan rows."""
    sc.parse_time(start)
    existing = {r["night"] for r in sc.read_csv(nights_path, ["night"])}
    if night in existing:
        raise sc.DataError(f"night {night!r} already exists in nights.csv - pick another id")
    lineup = sp.parse_lineup(menu, lineup_spec)
    rows = sp.plan(menu, covers, lineup, units_per_cover, buffer_pct)
    sc.append_csv(nights_path, sc.NIGHT_COLS, [{"night": night, "venue": venue, "start": start}])
    sc.append_csv(items_path, sc.ITEM_COLS, [
        {"night": night, "item": r["item_id"], "size": r["size"], "price": f"{r['price']:g}",
         "start_count": r["units"]} for r in rows])
    return rows


def _ask(prompt, validate, input_fn):
    """Re-ask until the answer validates. '' means skip (returns '')."""
    while True:
        ans = input_fn(prompt).strip()
        if ans == "":
            return ""
        try:
            validate(ans)
            return ans
        except (sc.DataError, ValueError) as e:
            print(f"  ? {e}")


def _count(s):
    if int(s) < 0:
        raise ValueError("must be 0 or more")


def _number(s):
    float(s.lstrip("$"))


def _prompt_all(night, nrow, i_rows, input_fn):
    """Ask the questions, mutating the rows in place (so a Ctrl-C keeps progress)."""
    for r in (r for r in i_rows if r["night"] == night):
        if (r.get("end_count") or "").strip():
            continue
        label = f"{r['item']}/{r['size']} (started {r['start_count']})"
        left = _ask(f"{label} - how many LEFT? ", _count, input_fn)
        if left == "":
            continue
        if int(left) > int(float(r["start_count"])):
            print("  ? more left than you started with - recording anyway; fix start_count if that's wrong")
        r["end_count"] = left
        waste = _ask("    wasted / dropped / comped / staff-ate [0]? ", _count, input_fn)
        r["waste"] = waste or "0"
        if left == "0":
            r["sold_out_time"] = _ask("    sold out at what time (HH:MM, Enter if unsure)? ",
                                      sc.parse_time, input_fn)

    night_prompts = [("end", "closed at (HH:MM)", sc.parse_time),
                     ("covers", "covers / customers served", _count),
                     ("avg_wait_min", "average wait (minutes)", _number),
                     ("weather", "weather (e.g. 'clear 48F')", lambda s: None),
                     ("bundles_sold", "3-for-$10 bundles sold", _count),
                     ("gross_sales", "gross sales from register/Square ($)", _number),
                     ("venue_fee", "venue fee ($)", _number),
                     ("labor", "labor cost ($)", _number),
                     ("notes", "notes", lambda s: None)]
    for col, label, validate in night_prompts:
        if not (nrow.get(col) or "").strip():
            nrow[col] = _ask(f"{label}? ", validate, input_fn)


def close_night(nights_path, items_path, night, input_fn=input):
    """Interactively fill in end counts and night-level numbers for `night`."""
    with open(nights_path, newline="", encoding="utf-8") as f:
        nreader = csv.DictReader(f)
        n_fields, n_rows = nreader.fieldnames, list(nreader)
    with open(items_path, newline="", encoding="utf-8") as f:
        ireader = csv.DictReader(f)
        i_fields, i_rows = ireader.fieldnames, list(ireader)
    nrow = next((r for r in n_rows if r["night"] == night), None)
    if nrow is None:
        raise sc.DataError(f"night {night!r} not found in nights.csv")

    print(f"Closing {night} ({nrow.get('venue', '')}). Enter = skip.\n")
    try:
        _prompt_all(night, nrow, i_rows, input_fn)
    except (EOFError, KeyboardInterrupt):
        print("\nInterrupted - saving what you entered so far; run close again to finish.")
    sc.write_csv(nights_path, n_fields, n_rows)
    sc.write_csv(items_path, i_fields, i_rows)
    print("\nSaved. Run: python scripts/skewer_report.py")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open", help="create tonight's rows with planned start counts")
    o.add_argument("--night", required=True)
    o.add_argument("--venue", required=True)
    o.add_argument("--start", required=True, help="service start, 24h HH:MM (e.g. 23:00)")
    o.add_argument("--covers", type=int, required=True, help="expected customers (sizes the start counts)")
    o.add_argument("--lineup", default="")
    o.add_argument("--units-per-cover", type=float)
    o.add_argument("--buffer-pct", type=float)
    c = sub.add_parser("close", help="enter end counts and night totals")
    c.add_argument("--night", required=True)
    for s in (o, c):
        s.add_argument("--menu", default=sc.MENU_PATH)
        s.add_argument("--nights", default=sc.NIGHTS_PATH)
        s.add_argument("--items", default=sc.ITEMS_PATH)
    args = p.parse_args(argv)
    try:
        if args.cmd == "open":
            menu = sc.load_menu(args.menu)
            rows = open_night(menu, args.nights, args.items, args.night, args.venue, args.start,
                              args.covers, args.lineup, args.units_per_cover, args.buffer_pct)
            print(f"Opened {args.night}. Start counts to prep:")
            for r in rows:
                print(f"  {r['item']['name']:<24} {r['size']:<9} {sc.money(r['price']):>7}  x{r['units']}")
            print("\nAt close: python scripts/skewer_log.py close --night " + args.night)
        else:
            close_night(args.nights, args.items, args.night)
    except sc.DataError as e:
        raise SystemExit(f"error: {e}")


if __name__ == "__main__":
    main()
