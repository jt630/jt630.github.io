# Skewer Pop-up — Basque-Japanese late-night experiment

A low-cost test, run **before** committing to a truck or storefront: weekend
pop-ups at downtown Boise bars/breweries, 1–2 nights a week for ~4 weeks,
selling yakitori-technique skewers with Basque flavors (pimentón, chorizo,
piquillo, sherry vinegar, txuleta-style beef) to the after-11 p.m. bar crowd.

The question isn't "can I make good skewers." It's **what size and price
does this crowd actually buy, and does the margin hold up** against $11 hot
dogs and $5 pizza.

> This is a spec + README for a small CLI toolkit. No database, no web app —
> just a menu file, two CSVs, and three scripts. Everything is stdlib Python
> plus PyYAML (already used elsewhere in this repo).

---

## ▶ Where we are / next session

**State:** v1 built and tested (208 repo tests pass, `hugo --minify` clean).
Every menu number is a **placeholder** (`confirm:` flags in `menu.yaml`).
No nights logged yet.

**Next, in order:**
1. Replace placeholders in `menu.yaml` with real supplier prices and a timed
   grill test; delete each field from its `confirm:` list as you verify it.
2. Fill in the **Success criteria** below *before the first night*.
3. Make the permit/venue phone calls. Desk research is done and the call list
   is in **`docs/SKEWER-LEGAL.md`** (CDH health license, Boise Fire charcoal
   rules, city vendor license, tax, alcohol). Nothing there is confirmed yet.
   Entity form, venues, and the launch sequence are in
   **`docs/SKEWER-STRATEGY.md`** (recommendation: single-member LLC, kitchenless
   downtown taproom patio, Basque-inspired late-night slot).
4. Run night 1, log it, read the report. Then pick the next price/size test.

### Launch plan: prep this winter, open in spring (decided 2026-10-13)

Why: CDH needs ~30 days (plus a pre-op inspection ~2 weeks before opening),
Boise winter is ~38°F highs / 25°F lows (outdoor late-night charcoal is a poor
fit), and the license path, hood question and host terms are still open. Target
a soft launch around Treefort (late March 2027) and regular Thu-Sat nights from
April. Tick items as done; slip dates rather than skip steps.

- [ ] **Oct-Nov:** make the CDH, Boise Fire, City Clerk calls (numbers in
  `docs/SKEWER-LEGAL.md`). Buy a cheap grill and run the home **Grill test**
  below (recipes only, sell nothing).
- [ ] **Dec:** form the single-member LLC, get the EIN, DBA, bank account; get
  2-3 liability insurance quotes; pitch 2-3 host venues (kitchen status,
  charcoal OK, insurance minimum, fee/split); introduce yourself to the Basque
  Museum and Center.
- [ ] **Jan:** get fabricator quotes and order the service grill *only after*
  Boise Fire answers the hood/suppression question; book ServSafe; sign a
  commissary or host-kitchen agreement.
- [ ] **Feb:** file the CDH application (≥30 days ahead; plan review $100);
  buy extinguishers (ABC + Class K) and file the fire permits.
- [ ] **Mar:** pass inspections; soft-launch 1-2 nights (Treefort week if ready).
- [ ] **Apr+:** regular Thu-Sat nights; log every night, read the report.

Exceptions: a host with a covered, vented indoor space and licensed kitchen
could allow a winter indoor residency (indoor charcoal fire rules are stricter);
and if the permit calls come back easy, an Oct-Nov test is a bonus, not the plan.

---

## Setup

```bash
pip install pyyaml          # the only dependency
python -m unittest discover scripts/tests    # optional: run the tests
```

Files (note: the CSVs live in `research/`, **not** `data/` — Hugo fails the
whole site build on a `.csv` in `data/`):

| File | What it is |
|---|---|
| `research/skewer_popup/menu.yaml` | Menu: items, size/price variants, ingredients, cost, prep time |
| `research/skewer_popup/nights.csv` | One row per pop-up night |
| `research/skewer_popup/night_items.csv` | One row per night × item × size × price |
| `scripts/skewer_log.py` | `open` / `close` — the easy way to fill the two CSVs |
| `scripts/skewer_prep.py` | Prep sheet generator |
| `scripts/skewer_report.py` | The report |
| `scripts/tests/test_skewer_*.py`, `fixtures/skewer_*` | Tests and a worked example |

## The data model (and why it's shaped this way)

**Record only what you can't derive.** You count what you *start* with and
what's *left*; everything else is computed.

```
units sold = start_count − end_count − waste
revenue    = units × price  (− bundle discount)      [or gross_sales if you log it]
cost       = (start_count − end_count) × cost/unit   [waste was paid for too]
sold out   = end_count == 0
```

**`night_items.csv`** — one row per *arm* per night. An arm is
`item + size + price`, the thing you're testing:

| column | meaning |
|---|---|
| `night` | id from nights.csv (use the date; add a suffix for a 2nd venue: `2026-10-16-bar`) |
| `item`, `size` | ids from menu.yaml (`chorizo_piquillo`, `small`) |
| `price` | price you actually charged — this is what lets you test $2 vs $6 |
| `start_count` | how many you had at open |
| `end_count` | how many were left at close (`0` = sold out; blank = not counted yet) |
| `waste` | dropped / burnt / comped / staff-ate (optional, default 0) |
| `sold_out_time` | when it hit zero, 24h `HH:MM` (after-midnight times are fine) |

**`nights.csv`** — one row per night: `night, venue, start, end, covers,
avg_wait_min, weather, venue_fee, labor, bundles_sold, gross_sales, notes`.
`covers` is **actual** customers served. `gross_sales` (from Square/your
register) overrides the estimated revenue when present. `bundles_sold` is the
number of 3-for-$10 deals, used to discount the estimate.

**Why sell-out time matters.** If an item sells out, `units` is only a *floor*
on demand — you don't know how many more people wanted it. So the report also
shows **units/hour while stocked**, which compares a $2 small that sold out at
12:30 fairly against a $6 large that lasted all night. Over-prepping a little
(`buffer_pct`) protects the data as well as the sales.

**Testing price/size.** Prefer running arms **side by side on the same night**
(e.g. chorizo `small@2` and `large@6` together): same crowd, same weather.
Comparing Friday to Saturday confounds price with everything else. Change one
thing at a time, and treat anything under ~3 nights per arm as a hint, not a
result (the report says so).

## How to log a night

1. **Plan + prep.** Pick a lineup and expected covers:
   ```bash
   python scripts/skewer_prep.py --covers 120 \
     --lineup chorizo_piquillo:small@2,chorizo_piquillo:large@6,txuleta_beef,smashed_potato,baked_potato
   ```
   It prints units to build per item, ingredient totals, prep time, and the
   **morning-of** list (potatoes to parboil, coal-baked potato prep). Leave
   `--lineup` off to run the whole menu at default sizes/prices.
2. **Open the night** — creates the rows with prices and start counts filled in:
   ```bash
   python scripts/skewer_log.py open --night 2026-10-16 --venue "Brewery A" \
     --start 23:00 --covers 120 --lineup <same lineup as above>
   ```
   If you build a different number than planned, edit that `start_count` in the CSV.
3. **During service:** just note the time anything sells out (phone notes is fine).
4. **Close the night** — asks how many are left of each item, then the
   night-level numbers (Enter skips anything you don't know; Ctrl-C saves
   what you've entered):
   ```bash
   python scripts/skewer_log.py close --night 2026-10-16
   ```
   Or edit the two CSVs directly in a spreadsheet — the scripts don't care how
   they got filled in.

Adding a menu item or size later = add it to `menu.yaml`. The log never needs a
new column.

## How to run the report

```bash
python scripts/skewer_report.py
```

Prints: revenue / cost / profit per night (`*` = estimated, no `gross_sales`);
units, margin and sell-out rate per item (best sellers first); and a
price/size **arm comparison** with sell-through, units/hour while stocked, and
margin. It warns about unconfirmed costs and thin data.

To see what a report looks like before you have data, run it on the fixtures:

```bash
python scripts/skewer_report.py --menu scripts/tests/fixtures/skewer_menu.yaml \
  --nights scripts/tests/fixtures/skewer_nights.csv --items scripts/tests/fixtures/skewer_night_items.csv
```

After a few nights, `skewer_prep.py --history` sizes the next prep from your
*observed* units/cover and item mix instead of the menu's guesses.

## Grill test (home, cheap grill — recipes only, sell nothing)

Purpose: replace `menu.yaml` placeholders with measured numbers *before* you
spend on a licensed grill or a permit. A $30-150 hibachi/konro is enough. Do
**not** sell food from it; this is R&D, and the service grill choice waits on
the CDH and Boise Fire answers (`docs/SKEWER-LEGAL.md`).

For each menu item, cook at least 3 test batches of 10 skewers and record:

| Measure | How | Clears `confirm:` field |
|---|---|---|
| Real ingredient cost per skewer | Weigh the item's `ingredients` quantities, price them at an actual store (Cash & Carry, Basque Market, grocery) | `cost` |
| Hands-on minutes per skewer | Time build + grill for a batch of 10, divide by 10 | `prep_min` |
| Grill time per skewer, and sticks that fit at once | Stopwatch and tape measure; note the cooler zone for holding | informs `prep_min`, throughput |
| Internal temp when done | Probe thermometer: poultry 165°F, pork/beef/lamb 145°F, ground 155°F | pass/fail gate, not a field |
| Charcoal burned per hour | Weigh fuel in, weigh leftover out | cost model (add if missing) |
| Flare-ups / smoke / grease drip | Notes + photos | answers the hood/suppression question for Boise Fire |
| Taste and holding quality | Blind taste, plus 10 minutes held warm | `mix_weight` guess |

Rules: use the real portion sizes from `menu.yaml`, calibrate the thermometer
in ice water first, and once a field is measured, delete it from that entry's
`confirm:` list so `skewer_prep.py` and `skewer_report.py` stop warning about it.
`units_per_cover` and `buffer_pct` can only be learned from real nights, so
leave them flagged until night 1.

## Menu notes

- Pricing target: ~$4/skewer, 3 for $10 (skewers only), vs. $11 hot dogs / $5 pizza.
- Featured: smashed small-potato skewer (bravas topping, smoky fry-sauce
  aioli: pimentón mayo + ketchup + tare + katsuobushi). Coal-baked potato at
  $7–8. 7 other skewers + 2 sides.
- Skewers split the night's expected total by `mix_weight`; the baked potato
  and sides use `attach_rate` (units per cover). All are guesses until logged.

---

## Success criteria

**Write these before night 1** and don't edit them after data arrives — add a
dated note underneath instead (same rule as `THESIS.md`). Making the bar
explicit now is what lets the report answer "go / no-go" instead of "huh."

*Prompts to answer (delete the prompts as you fill them in):*

- **Money** — What profit per night (after venue fee, labor, food) makes this
  worth continuing? What does it need to be to justify a truck/storefront?
  > _TODO_
- **Demand** — How many covers per night, and skewers per cover, would count
  as proof people want this?
  > _TODO_
- **Price/size** — What would you need to see to pick a price point or size
  (e.g. which arm wins on margin/hour)? How many nights per arm is enough?
  > _TODO_
- **Operations** — Max acceptable average wait? Is "sold out before X a.m."
  good news (demand) or bad (under-prepped)?
  > _TODO_
- **Kill criteria** — What result after 4 weeks means *stop*?
  > _TODO_
- **Beyond the numbers** — Anything else (venue interest, repeat customers,
  how it feels to run)?
  > _TODO_

## Lab notebook

_Dated notes after each night: what happened, what surprised you, what to
change next. Newest at the bottom._

- _(none yet)_
