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
- [ ] A persistent historical store, append-only (`data/price_history.*`
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
