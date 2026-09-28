Refine an Auction Watch search: turn what the owner wants (often a profile from
a conversation with another AI) into tested watchlist keywords.

## Why this exists

`data/auction_watchlist.yaml` is the keep bar: a lot that matches no group
(and isn't Small Engines & Appliances) is dropped before it's ever shown or
priced. So keywords decide what the owner sees at all. Every false positive
so far was found only after it shipped: "truck" matched a truck toolbox,
"tundra" a YETI cooler, "308" a lot number, "pistol" a sprayer's pistol-grip
wand. Real Musick titles in `research/price_history/` now make it possible to
test keywords **before** they ship. This command always tests before it
edits.

## Steps

1. **Get the intent.** Accept whatever the owner gives: a pasted profile (YAML,
   notes, a conversation summary), a sentence ("add cheap generators"), or a
   complaint ("too much junk under Old Coins"). Ask only for what's missing:
   which group (new or existing), and what makes a lot a real *yes* for them.
   Capture *why* (purpose, constraints, price ceiling), not only model names.

2. **Save the why.** For anything bigger than a one-word tweak, write or update
   `data/search_profiles/<group_id>.yaml` with the owner's intent and reasoning
   (see `backcountry_pistol.yaml` for the shape). The watchlist holds compiled
   keywords; the profile keeps the reasoning, so the next refinement starts from
   intent. This is the "worth to me" context THESIS.md H7 is about.

3. **See the baseline.**
   ```bash
   python scripts/watchlist_test.py                 # every group's match count
   python scripts/watchlist_test.py <group_id>      # what one group matches now
   ```

4. **Draft and test keywords. Don't edit the watchlist yet.**
   ```bash
   python scripts/watchlist_test.py --diff <group_id> --try "kw1,kw2" --exclude "x,y"
   # or, for a brand-new group:
   python scripts/watchlist_test.py --try "kw1,kw2" --exclude "x,y"
   ```
   Read every ADDED and DROPPED title. Iterate until the added titles are real
   yeses and the dropped ones are real junk. Rules of thumb, learned the hard way:
   - **Check bare model names for collisions** on this site, which sells vehicles,
     guns, electronics, coins and tools side by side. "Hellcat" is also a Dodge
     trim, "G29" a Logitech wheel, "Sierra" an ammo brand, "RAM" computer memory.
     Test the bare word alone to see what it hits, then narrow it or add an
     `exclude`.
   - **Calibers keep their leading period** (".308", ".30-06"), or they match
     lot numbers.
   - **Word matching is whole-word with an optional trailing "s"**, so "p365"
     won't match "P365XL". List the variants.
   - **Zero matches in history isn't wrong.** Some targets are just rare at
     Musick. Say so, and consider keeping a broader sibling group so comparable
     items (same use, weight or price class) stay visible. See `handguns_other`.
   - **Watch the keep bar:** narrowing a group can silently drop lots from the
     site entirely. Always show the DROPPED list to the owner.

5. **Show the owner before editing**: the before and after counts, the added
   and dropped titles, and any collision you designed around. Get a yes.

6. **Edit `data/auction_watchlist.yaml`.** Add a comment above the group saying
   what was tested and why each exclude exists (future sessions read these).
   Then run:
   ```bash
   python scripts/watchlist_test.py           # sanity: all groups still load
   python -m unittest discover scripts/tests
   hugo --minify
   ```

7. **Ship it** per CLAUDE.md: a branch, a PR, and the session URL. The next
   scheduled pipeline run picks up the change; no code change is needed.

## Don't

- Don't probe Musick live to test keywords. The local corpus exists so you don't
  have to (see the collection etiquette in CLAUDE.md).
- Don't treat a price ceiling in a profile as a filter. The watchlist decides
  what's *shown*; price limits live in the profile until Session P gives them a
  real home.
