# Price Discovery — Project Plan

## Summary

Auction Watch started as a way to catch good deals on Boise-metro government
and police surplus for Jeremy and his grandpa. It's turning into something
bigger: a real testbed for **AI-driven price discovery** — using AI to
estimate what things are actually worth, grounded in real observed
transactions rather than a guess, and over time building a first-party
dataset instead of depending on someone else's (eBay's, Carfax's, KBB's).

This is the cornerstone doc for that direction — same role `MONKEYS.md`
plays for the monkey-coin subsystem: the spec, the reasoning, the roadmap,
read before any session that touches this scaling-up work.

---

## The North Star

> **A world where pricing is transparent, and people can verify a price
> with their own AI instead of trusting an institution's number.**

Right now, "what's this actually worth" is answered by paid, closed,
institutional sources — Carfax owns vehicle history, KBB/Edmunds own car
pricing, eBay's sold-comps are the closest thing to a public price feed
that exists and even that requires scraping around bot detection to use
programmatically. Nobody personally owns their own sense of value; they
rent it, one lookup at a time, from whoever happens to sell that lookup.

The bet here: an AI that has actually watched a real regional market —
thousands of real auction closes, not a textbook — can start forming its
own **expected price** for a category of item, the way an experienced
estate-sale regular develops a gut sense for what a box of tools or a
used truck is worth just from doing it for years. That's not a metaphor
for what LLMs do badly (hallucinate a plausible-sounding number) — it's
specifically the opposite: grounding the estimate in **real closed
transactions this project itself observed**, the same discipline
`auction_value.py` already applies with eBay comps (real sold data beats
Claude's own guess, every time comps exist) extended to a dataset this
project owns outright instead of borrows.

Zoomed out further, past what one person's project can build alone: a
world where pricing is *shared*, not just personal — where the data this
project accumulates could eventually be one node in something bigger,
the way OpenStreetMap or Wikipedia turned "one person's careful records"
into a shared public resource nobody has to pay a gatekeeper for. That's
long-horizon and explicitly not being built now — noted here because it's
the actual reason "collect real data instead of relying on eBay" matters
beyond just this one site's convenience.

---

## Why auctions are a genuinely good testbed for this

Not a rationalization after the fact — auctions have real structural
properties that make them better price-discovery data than almost any
other common source:

- **A real market clears at a real price.** Unlike an asking price
  (Craigslist, Facebook Marketplace, a store shelf), an auction *closes*
  — someone actually paid that number. That's a transaction, not a wish.
- **Full bid history is observable.** Not just the final price but how it
  got there — opening bid, bid count, how late the action happened. A
  lot that opened at $5 and closed at $8 after 2 bids says something
  different than one that opened at $5 and closed at $400 after 60 bids.
- **Condition and category are stated up front**, however roughly (a
  title, sometimes real spec data like the VIN/mileage/title-status
  enrichment already built for vehicles) — enough to train a real sense
  of "this kind of thing, in this rough condition, in this region, is
  worth about X."
- **It's regional and repeatable.** The same auction houses run the same
  kinds of sales on a schedule. A "Boise-metro government surplus"
  price sense is a real, specific, learnable thing — not "used cars in
  general," a signal that's actually coherent enough to model.

---

## Current state (what's actually real, as of this doc)

- Real per-lot data from Musick Auction Co.: title, current bid, bid
  count, time-to-close, and (for watchlist-matched vehicles) real
  VIN/mileage/title status pulled from each lot's own detail page.
- A personal watchlist (`data/auction_watchlist.yaml`) acting as the
  keep bar — only lots worth Jeremy's attention get kept or deeply
  processed at all, the scaling lever for adding more sources without
  scaling noise.
- eBay sold-comps as the only outside pricing source currently wired up
  — and currently broken (403/parsing, open bug) — plus an AI-only
  fallback (needs `ANTHROPIC_API_KEY`, not currently configured; the
  owner has explicitly said no to adding one).
- A maturity gate on deal-flagging (real bids or real time pressure
  required) so a fresh, untested listing doesn't masquerade as a deal.
- **What does NOT exist yet, and is the actual gap this doc is about:**
  nothing today records what a lot *actually closed at*. Every deal
  score compares a live bid to an outside estimate; nothing yet becomes
  a permanent, owned data point once the auction ends. That's the single
  missing piece standing between "uses eBay's data" and "builds its own."

---

## Roadmap

### Phase 1 — Own the close price (highest priority, unblocks everything else)
- [ ] Re-visit each tracked lot after its `auction_ends_at` passes and
      record the real **closing price**, final bid count, and whether it
      sold at all — not just the mid-auction snapshot already captured.
- [ ] A persistent historical store, append-only (`research/price_history.*`
      or similar - format TBD, see Open Questions) so this survives
      every day's fetch/overwrite cycle that `auction_lots.yaml` doesn't.
- [ ] Fix the eBay-comps bug (open, separate task) - still worth having
      as a second signal even once first-party data exists.

### Phase 2 — More sources, same keep bar
- [ ] Re-enable and verify the platforms already built but disabled:
      PublicSurplus, GovDeals, Municibid, PropertyRoom (see
      `docs/AUCTION-MONITORING.md`'s Platforms table).
- [ ] Add Craigslist (Boise-area search).
- [ ] Add KSL Classifieds (Idaho/Utah regional - good geographic fit for
      this project's Treasure Valley focus).
- [ ] Add Facebook Marketplace - **flagged as higher-risk**: Meta
      actively fights scraping and FB Marketplace has no public API:
      needs real ToS/feasibility research before writing a single line
      of scraper code, not an assumption it'll work like the others.
- [ ] Every new source funnels through the same watchlist keep-bar and
      category classifier already built - the reason scaling sources
      doesn't have to mean scaling noise or cost.

### Phase 3 — First-party pricing
- [ ] Once Phase 1's closed-price history has real volume, use it as a
      valuation source **alongside or ahead of** eBay comps for the
      categories/regions it actually covers - the literal "turn away
      from outsourcing data" step.
- [ ] An "expected price" model per item type/category, built from this
      project's own observed closes - a real prior, not a one-shot
      lookup.
- [ ] Re-evaluate whether eBay comps are still needed once first-party
      coverage is real, category by category.

### Phase 4 — Business-potential agent (stubbed now, not built)
- [ ] `scripts/business_agent.py` exists as a stub (see below) -
      `evaluate_business_potential(lot)`, not wired into the real
      pipeline yet. The idea: given a lot, assess whether it's a
      plausible small-business input - resale inventory, a flip, tooling
      to start or supply a side business (e.g. "10 industrial sewing
      machines" reads differently than "1 sewing machine" to someone
      thinking about starting an alterations business). Real design
      needed before building for real: what counts as a "business
      angle," how confident does it need to be to surface, what's the
      failure mode of a wrong guess here (worse than a wrong price
      estimate, since it's advising an actual bet on a business idea).

### Phase 5 — The bigger vision (aspirational, not scoped, not being built)
- A personal "expected price" model that travels with the person, not
  just this one site.
- Eventually: pricing data that's actually shared and transparent across
  people, not gatekept by a paid institutional source. Not a concrete
  engineering task yet - the reason Phase 1-3 matter beyond convenience.

---

## The business agent stub

`scripts/business_agent.py` now exists with the function signature and a
docstring laying out the intent, returning `None` (not yet implemented)
for every lot. It is **not called anywhere** in `auction_finder.py` or
`auction_value.py` - wiring it in is future work, once there's a real
design for what "validated as a business opportunity" actually means and
how wrong a bad guess here is allowed to be.

---

## Open questions

> Most of these now have a call in **Decisions (2026-09-28)** below. Kept
> here as the original framing.

- **Storage at scale.** `data/auction_lots.yaml` gets fully overwritten
  every run - fine for a live snapshot, wrong for permanent history.
  What actually holds thousands of closed-price observations over time -
  still a flat file (jsonl, one append per close), or does this need a
  real database once volume grows past what git-tracked YAML can sanely
  hold?
- **Cache invalidation for "cached research."** If a per-lot AI reasoning
  pass gets cached to avoid re-running it daily, what invalidates that
  cache - the bid changing? A time window? Never, since the *item*
  hasn't changed even if the bid has?
- **The feedback loop shape.** Does "dial in the search" mean the
  watchlist gets tuned by hand (as now), or does it learn from what
  Jeremy actually clicks/ignores? Needs a real answer before it's
  buildable, not just a name.
- **Facebook Marketplace feasibility.** Genuinely unknown yet whether
  this is practical or advisable at all - research before code.
- **What does "shared pricing data" concretely look like**, if Phase 5
  ever gets scoped for real? Not answerable yet, and not blocking
  anything in Phase 1-3.

---

## Non-negotiables (carried over from everything already built)

These aren't up for revisiting just because the scope is growing:

- **Never manufacture false confidence.** A missing bid isn't a $0 bid,
  a missing VIN doesn't get guessed at, a fresh untested lot doesn't
  get flagged as a deal, an unmatched category gets dropped rather than
  padded with a guess. Every rule like this already in the codebase
  applies just as hard to a first-party price model - "no comps, no
  confident number" beats a plausible-sounding hallucinated one every
  time, especially once real money/business decisions ride on it.
- **No paid API key** unless the owner explicitly asks for one again -
  scaling sources happens through free/public access and this project's
  own observed data, not by reaching for a credential.
- **Verify against real markup before shipping**, same debug-and-inspect
  discipline used for every platform so far - a new source gets probed
  and its real response read before a parser is written against a
  guess.

---

## Decisions (2026-09-28 planning session)

These answer the Open Questions above, plus a few calls the roadmap left
implicit. They were made after reading the real code and data on `main`, not
just the roadmap. Revisit one only with a reason from real data.

1. **Phase 1 is the only thing that matters right now.** Every later phase
   depends on owned close prices. Nothing in Phase 2–4 starts until the close
   harvester has run on a schedule and recorded real rows.

2. **History records every lot we render, not just keep-bar lots.** The
   watchlist keep bar exists to bound *attention* and *render cost*. It was
   never meant to bound *data*. A closed catalog page already contains all 50
   lots whatever the watchlist says, so recording all of them adds one JSONL
   row each and no extra render. Dropping them would throw away free price
   data just to reduce noise that nobody sees anyway. `auction_lots.yaml`
   (the display snapshot) keeps the keep bar. `price_history/` does not.

3. **Storage: JSONL, append-only, one file per month.**
   `research/price_history/YYYY-MM.jsonl`, one line per *closed* lot, keyed by
   `(platform, lot_id)`. Rough volume: 6 sales/week × 50 lots ≈ 15k rows/yr ×
   ~600 bytes ≈ 9 MB/yr. That is fine in git for years, diffs are readable,
   and nothing needs a server. SQLite is the wrong fit here because it is a
   binary blob in git and every commit rewrites it. **Revisit at 100k rows**
   (or when full-catalog paging, see below, blows past that). Even then,
   build a SQLite *index* from the JSONL at runtime instead of swapping the
   source of truth.

4. **A close price is only called a close price if we saw it close.** Each row
   carries `price_kind`:
   - `"close"`: read off a page that says the lot is closed/sold.
   - `"last_seen_bid"`: the last bid we observed before the close, with
     `observed_at` and `minutes_before_close`. This is a lower bound, not a
     sale. Phase 3 never treats these as comps.
   - `"passed"`: closed with no sale or no bids. This is real data too
     ("nobody wanted this at $5"), so it gets recorded rather than skipped.
   This is the "never manufacture false confidence" rule applied to storage.

5. **The feedback loop is estimate calibration, not click tracking.** This is
   a static site. There is no click data, and adding analytics to get some is
   out of scope. The concrete loop: once closes exist, every lot that had an
   estimate gets an `estimate_error = close − estimated_value_mid` in its
   history row. The watchlist stays hand-tuned. What gets "dialed in"
   automatically is which estimate source we trust per category (for example,
   "eBay comps overestimate jewelry by 3×, stop flagging on them").

6. **Cache invalidation: key on the item, never the bid.** Any cached per-lot
   AI reasoning is keyed on `(platform, lot_id, sha1(title + description))`.
   A bid change never invalidates it, because Python applies the bid
   *after* reasoning, which is already the architecture (see "whichever
   number gets used is decided in Python"). A title or description edit
   invalidates it. Closed lots are frozen forever.

7. **Phase 2 re-orders: auctions before classifieds.** Craigslist, KSL, and FB
   Marketplace only show *asking* prices, and a listing disappearing is not
   a sale. For price discovery they're weak data, and this spec's own "Why
   auctions" section says so. So: (a) PublicSurplus/GovDeals/Municibid/
   PropertyRoom first, because they produce real closes; (b) KSL/Craigslist
   later, as a deal-finding feed and *asking-price* signal, stored with
   `price_kind: "asking"`; (c) Facebook Marketplace: **default no.** It's
   login-walled, Meta's terms prohibit automated collection, and Meta
   actively litigates. The research session below exists to confirm or
   overturn that, not to build a scraper.

8. **eBay gets one time-boxed session, then a verdict.** 403 from a GitHub
   Actions runner is almost certainly datacenter-IP bot defense, which a
   parser change can't fix. Getting around it (proxies, header spoofing,
   headless evasion) is off the table. There is also a real bug that can be
   fixed without network access: the eBay query is the raw lot title
   (`"Lot #5012: Large Gold-Tone Rope Chain Necklace With Circular..."`),
   including the lot-number prefix and 15+ words. That would return ~0
   results even from an unblocked eBay. Fix the query, dump one real
   response, and if it's a hard 403, record that finding and move on. Phase
   1 makes eBay less important every week it runs anyway.

9. **Phase 4 (business agent) is defined as a Phase 3 derivative, not an LLM
   judgment.** The only honest version of "is this a business input" is
   arithmetic on owned data: `quantity × first-party expected resale −
   expected close − fees`, with a confidence floor (N closes of that item
   type). Without Phase 3 data, the stub keeps returning `None`. An LLM
   saying "you could start an alterations business" with no price grounding
   is exactly the false confidence this project refuses to ship.

10. **Vehicles get a separate track.** eBay has no vehicle comps, and we have
    no paid key. The vehicle target price comes from (a) our own vehicle
    closes, which Musick sells 100+ of per cycle, the best-covered category
    we have, and later (b) a scheduled Claude Code Routine that reasons over
    `car_candidate` lots and commits a result, per the idea in
    `docs/AUCTION-MONITORING.md`. (b) waits until (a) gives it real local
    closes to anchor on.

---

## Build Plan — Session Task Lists

Ordered by dependency. Each block is one session's worth of work: copy a
block into a session and go.

**Before every session:** read `PRICE-DISCOVERY.md` (this file),
`docs/AUCTION-MONITORING.md`, and `CLAUDE.md`. The engineering log has the
real-markup findings. Don't re-derive them.

**Teaching mode:** per `CLAUDE.md` > "Learning philosophy", each session names
the Claude Code skill it exercises. Don't skip the callout.

**The verify-first loop** (used by every session that touches a new page):
dispatch `auction-monitor.yml` with `probe_url` or `debug_html` → read the
dump on the `debug/auction-html` branch → write the parser against that real
markup → dry-run locally against the saved HTML → ship. The dev sandbox
can't reach these sites directly. This loop is the only way in.

---

### Session A: Probe what a *closed* lot looks like (research only, ~no code)

**Goal:** Answer the one question Phase 1's design depends on: *does Musick
show the final price after close, and where?*

**Context:** Catalogs 914/915 (seen in the first debug run) are no longer in
the upcoming list, so they have almost certainly closed. That makes them free
test subjects today. Two outcomes, two designs:
- A **closed catalog page** still lists all lots with "Sold $X": the best
  case. One render per auction harvests 50 closes.
- Only **lot-detail pages** show it: harvest is one render per lot, so limit
  it to watchlist lots plus a sample.
- Neither shows it (lots vanish or show no price): fall back to
  `last_seen_bid`, and add a second cron run timed near close.

- [x] Dispatch `probe_url` = `https://bid.musickauction.com/auctions/catalog/id/914`
      (done in the original 09/23 session — see "Musick, verified against real
      markup" and "Closed lots, verified against real markup" in
      `docs/AUCTION-MONITORING.md`)
- [x] Dispatch `probe_url` = the bidding-history page for one lot on catalog 914
      (`/auctions/bidding-history/id/914/lot/511357`)
- [x] Read the dumps. Recorded the real markup for "sold price" (`item-win-bid`),
      "closed at" (`start-end-dates`, and the `auctionRows` JSON's `end_date`), and
      the full timestamped bid trail (bidding-history page, no bidder identity data)
      in `docs/AUCTION-MONITORING.md` under "Closed lots, verified against real
      markup". **"Passed"/unsold was NOT found** — every lot sampled across two
      pages (50 high-value + 70 low-value) was `ended sold`; the site's JS does
      define `langUnsold`/`langReserveNotMet` strings, so the state almost
      certainly exists, just not yet caught in a real sample.
- [x] Close timestamp: **absolute**, in two independent places — `start-end-dates`
      text on the catalog page, and `end_date` in the `auctionRows` JSON returned by
      `/auctions/?alf1=4` (a *closed-catalogs index*, found this session, not
      anticipated by the original plan — see below).
- [x] `?page=N` works on a closed catalog — confirmed, and `?items=100` also works
      (`?items=100&page=5` on catalog 914 correctly rendered lots 401–470, the tail
      of its 470-lot catalog). Full-catalog paging is real, not a size-50 ceiling.
- [x] Bonus, not in the original plan: found `https://bid.musickauction.com
      /auctions/?alf1=4` — an actual enumerable index of closed auctions (827 total,
      50/page, structured JSON per row with id/end_date/total_lots/status), which
      changes Session B's design (see below).

**Result:** All three original outcomes partially apply — it's better than the best
case. A closed catalog page still lists every lot with its real closing price
(`item-win-bid`) and status (`item-status` → `ended sold`), paginated to full depth
via `?items=100`, so one catalog can be harvested in a handful of renders regardless
of size. On top of that, a closed-catalogs *index* exists
(`/auctions/?alf1=4`, 827 catalogs, structured JSON, absolute `end_date` per row),
which the original plan didn't know to look for — it means the harvester can find
what closed and when without walking catalog ids blind or depending only on
`_pending.json`. The one open item: no unsold/passed lot has been seen in real
markup yet, so `price_kind: "passed"` in the Session B schema is still a *design*,
not something matched against real markup — worth one more probe (a lower-value
catalog, or paging further into an older one) before the harvester ships.

**Learning opportunity:** this is spec-driven development's "verify before
build" step. Thirty minutes of probing decides between three different
architectures. Guessing and building the wrong one costs a whole session.

---

### Session B: Close-price harvester (the Phase 1 build)

**Goal:** `research/price_history/` exists and fills itself daily.

**Context:** The schema below is the contract. Phase 3 reads it and
calibration reads it. Don't rename fields after the first row ships.

**Built (2026-09-28):** `scripts/price_history.py` implements the real,
slimmer schema (see docs/AUCTION-MONITORING.md's "Close-price history"
section - it differs from the field list originally sketched below: no
`url`/`opening_bid`/vehicle fields, `catalog_closed_at` instead of
`closed_at`/`minutes_before_close`, `price_kind` is `"close"`/`"unknown"`
only, `"passed"` collapsed into `"unknown"` since no real unsold markup has
ever been observed). Daily CI harvest (capped at 5 new catalogs/run) is
wired into `.github/workflows/auction-monitor.yml`, between "Fetch lots"
and "Estimate value", `continue-on-error: true`. Backfill: run once
locally, see `scripts/price_history.py --backfill`. Offline unit tests
against real saved markup: `scripts/tests/test_price_history.py`.

- [ ] Give every lot an absolute `auction_ends_at`, not just vehicles. **Use the
      catalog's absolute end time, not a per-lot countdown**: `start-end-dates`
      on the catalog page and `end_date` in the `auctionRows` JSON from
      `/auctions/?alf1=4` both give an absolute timestamp for the whole sale
      (**`end_date` is UTC**; `start-end-dates` text is MDT/MST, see the
      engineering log; store UTC ISO-8601 everywhere) — no "Time left"/duration parsing needed at all, which avoids
      the drift/edge cases a relative-string parser has (the countdown keeps
      ticking between fetch and parse). `_parse_musick_duration()` stays useful
      for `auction_ends_at` on *live* vehicle-detail pages (Session A didn't
      touch that), just not for catalog-level end time.
- [x] Add a stable `lot_id` field (the `/lot/511357/` segment of the URL — the
      lot's internal id, not its display "Lot #N", which differ, e.g. lot id
      511357 is "lot 800" in the sale) and `catalog_id`. Both are already in
      every URL. **Built as designed** — pulled from the `data-lid`/`data-aid`
      attributes on each lot's `<section>` wrapper rather than parsed out of
      the URL string, same values, more robust to a URL format change.
- [ ] ~~`research/price_history/_pending.json`~~ — **superseded by
      `research/price_history/_harvested.json`** (owner decision, see
      `scripts/price_history.py`'s docstring): the daily CI run itself queries
      `/auctions/?alf1=4` for closed catalogs rather than tracking pending ones
      via `auction_finder.py`, so there's no separate pending file, only a
      harvested-state one (`{"catalogs": {"914": {"end_date", "lots",
      "harvested_at"}}}`).
- [x] `scripts/price_history.py`: for each closed catalog not yet harvested,
      render it **paged with `?items=100`** (confirmed honored on a closed
      catalog — a 470-lot sale needs 5 renders, not 10) rather than the default
      50/page, parse `item-win-bid` + `item-status` (`ended sold` vs. any other
      status, which becomes `price_kind: "unknown"` — no real unsold/passed lot
      has ever been observed, see docs/AUCTION-MONITORING.md, so `"passed"`
      never shipped as its own kind), append rows, mark it harvested. Idempotent:
      never appends a `(platform, lot_id)` twice — verified by
      `scripts/tests/test_price_history.py`.
- [x] Row schema (one JSON object per line) — **shipped slimmer than
      originally sketched here** (owner decision, no `url`/image, no
      vehicle-enrichment fields, no `opening_bid`/`minutes_before_close`):
      `platform, catalog_id, lot_id, lot_no, title, category,
      watchlist_matches (omitted when empty), price_kind ("close"|"unknown"),
      price, num_bids, catalog_closed_at, observed_at, status_raw (only when
      price_kind is "unknown")`. See docs/AUCTION-MONITORING.md's "Close-price
      history" section for the full contract.
- [x] New workflow step, **before** valuation, so a valuation failure can't
      skip it. It commits `research/price_history/` in the same commit as lots.
- [x] Unit test the parser against the Session A dumps, saved as fixtures
      under `scripts/tests/fixtures/`.
- [ ] Dispatch once on `main` after merge, confirm rows land, and confirm a
      second run appends zero duplicates. **Not done in this session** — this
      needs a real GitHub Actions run against the live site, which the PR
      review/merge step should trigger next.

**Learning opportunity:** hooks. Add a pre-commit or session-start check
that validates every `price_history/*.jsonl` line parses and has the
required keys. An append-only store is only trustworthy if a malformed line
can't sneak in, so the environment should enforce that instead of memory.

---

### Session C: eBay verdict (time-boxed, can run in parallel with B)

**Goal:** Know for sure whether eBay comps can work, and fix the query bug
either way.

- [ ] `normalize_query(title)`: strip `Lot #N:`, drop filler ("With",
      "Large", "Hammered Finish"…), and cap at ~6 meaningful tokens. Unit-test
      it on 20 real titles from `auction_lots.yaml`.
- [ ] Wire `ebay_comps.py` into `--save-html` (it isn't today). Dispatch
      `debug_html: true`, then read the real eBay response from the debug
      branch.
- [ ] If it's a 403 or challenge page: write the finding into
      `docs/AUCTION-MONITORING.md`, set eBay to skip-with-a-note after the first
      403 per run (stop burning 90 × 2s sleeps on a wall), close the bug.
      **Don't evade.**
- [ ] If it's real results: fix the parser against the dump and ship.

**Learning opportunity:** worktree isolation. Run this as an Agent with
`isolation: "worktree"` alongside Session B's work, since the two touch
disjoint files. It's a real example of when parallel lanes are safe.

---

### Session D: Surface the history (after ~2 weeks of closes)

**Goal:** Make the owned data visible, and start the calibration loop.

- [ ] `/auctions/history/`: recent closes, grouped by watchlist group and
      category, showing `price_kind` honestly ("sold $140" vs "last seen at
      $60, 3h before close").
- [ ] Per-category calibration table: for lots that had an estimate at last
      sight, the median `close / estimate` ratio, n, and source. This is
      Decision 5's feedback loop, made visible.
- [ ] Hugo reads JSONL poorly. Have `price_history.py` also emit a small
      aggregated `data/price_summary.yaml` for templates. The JSONL stays the
      source of truth.

**Learning opportunity:** data-driven content. It's the same data/view split
as `music.yaml`, except now the data is generated by a pipeline rather than
hand-written.

---

### Session E: First-party comps (Phase 3, gated on volume)

**Gate:** don't start until some watchlist group or category has ≥ 30
`price_kind: "close"` rows. Check with a one-liner before opening the
session.

- [ ] `scripts/history_comps.py` exposes `lookup(lot)` with **the same return
      shape as `ebay_comps.lookup`**: `{"n", "median", "low", "high"}`.
      Matching: same category + same watchlist group + token overlap on the
      normalized title (reuse Session C's normalizer). Vehicles also match on
      year ±3 and a mileage band.
- [ ] `auction_value.py` tries history first, then eBay, then AI.
      `value_source: "history"`. Same `EBAY_MIN_COMPS`-style threshold (rename
      it `MIN_COMPS`). Fewer than 3 matches gives null, not a guess.
- [ ] The page shows "✓ N local closes" in its own color, ranked above eBay
      in the sort (owned local data beats national data).
- [ ] Re-check the calibration table. If history-based estimates beat eBay
      for a category, say so in the doc and consider dropping eBay there.

---

### Session F: Wider auction net (Phase 2, part 1)

- [ ] One platform per session, in this order: **PublicSurplus** (most Idaho
      agencies), **GovDeals**, **PropertyRoom**, **Municibid**. Each follows the
      verify-first loop: `debug_html` dump, then parser, then dry-run, then
      add it to `PLATFORMS`.
- [ ] Each must feed `_pending.json` and the harvester from day one. A
      source that can't give us closes is a lower-priority source.
- [ ] Fan-out note: the four `debug_html` dumps can be collected in *one*
      dispatch, and the four parsers can then be written by parallel
      agents, one per platform, since they touch separate functions.

**Learning opportunity:** parallel agent orchestration. Four independent
parsers against four saved dumps is the textbook fan-out case.

---

### Session G: Research only — classifieds + Facebook Marketplace

- [ ] Use the deep-research skill (parallel research agents) to read
      Craigslist, KSL, and Meta's current terms and technical access (RSS,
      APIs, login walls), plus relevant case law. Output: a short
      go/no-go table appended to this file.
- [ ] No scraper code this session. Build only what the table says is a
      "go", in a later session, stored as `price_kind: "asking"`.

---

### Not scheduled (and why)

- **Business agent (Phase 4):** blocked on Session E by Decision 9.
- **Vehicle Routine:** blocked on ~a month of vehicle closes (Decision 10).
  When unblocked, it's a good first use of scheduled Claude Code Routines.
- **"Discovery" sampling outside the watchlist:** mostly obsoleted by
  Decision 2. History already records non-watchlist lots, so Session D's
  page *is* the discovery view.
- **Full-catalog paging** (lots 51–1087): decided by Session A's `?page=2`
  finding. If paging a *closed* catalog works, the harvester should page
  (history wants volume). The live-bid fetch can stay at page 1 (attention
  is bounded by the keep bar anyway).
- **Phase 5:** unchanged. Aspirational.
