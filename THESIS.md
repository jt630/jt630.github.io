# Thesis — Convergence, Signal, and "Worth to Me"

*An independent research project run on this site's own auction data.
Engineering lives in `PRICE-DISCOVERY.md`; this file is the research: the
question, the argument, pre-registered predictions, and a dated lab notebook.*

**Pre-registered 2026-09-28**, before any closed-price history has been
collected or examined. The git commit that adds this file is the timestamp.
Predictions below are not edited after data arrives. Revisions go in the
notebook as dated amendments, with the reason stated, so a finding can
always be told apart from a story told after the fact.

---

## The question

When centralized AI appraisal becomes common (Google's AI answers,
ChatGPT, Claude, a phone photo at the consignment store asking "what's this
worth?"), what happens to the prices people actually pay? And what does
that do to the reason markets exist at all?

## The argument

Every auction close mixes three things:

> **price = common value** (what anyone could resell it for)
> **+ private value** (what it's worth to *this* bidder: grandpa can fix
> the vacuum, you need that exact part)
> **+ noise** (who happened to show up, timing)

Centralized AI appraisal is very good at the first term, and it gives
**everyone the same answer**. As people anchor on it, private-value
differences get crowded out and prices converge on the shared estimate.

That convergence has a cost. Markets exist *because values differ*: people
with the same information and beliefs have no reason to trade (the
no-trade theorem, Milgrom & Stokey 1982). Push convergence far enough and
you erode the reason trade happens and the information markets gather
(Hayek 1945). In information-theory terms, an AI trained on public prices
can't produce the private signal. The data processing inequality says
processing can't add information that wasn't in the inputs. It can only
repackage the common value.

Convergence doesn't arrive all at once. Adoption is staggered across
**people** (early adopters capture an information-arbitrage premium that
shrinks as adoption spreads; Grossman & Stiglitz 1980) and across **items**
(AI-legible items converge before AI-illegible ones).

**Position:** the fix isn't less AI but *personal context*: estimators that
answer "what is this worth **to me**" instead of "what is this worth". That
separates two kinds of trade:
- **Common-value arbitrage** (buy under market, resell) is zero-sum: the
  edge is someone else's loss.
- **Private-value matching** (buy what's worth more to you than to the
  market) is positive-sum: the trade creates value.

## Definitions (fixed now, so the analysis can't drift)

- **Item type:** a cluster of lots that are the same thing. Operationally,
  identical `normalize_query()` output (`scripts/ebay_comps.py`) *plus* the
  same `category`. Clusters with fewer than 5 closes are excluded from
  spread measures.
- **AI-legible:** the title contains an identifier that fixes the item
  exactly (a brand + model token, a VIN, a caliber + model, a year + make +
  model). **AI-illegible:** mixed/bulk lots ("box of", "lot of",
  "assorted"), "untested"/"as-is", or no brand/model token. The exact
  classifier is committed as code before it's run on history, and it isn't
  tuned against the outcome.
- **Spread:** the coefficient of variation (stdev / mean) of `price` within
  an item type. Entropy of the binned log-price is reported alongside it as
  a robustness check.
- **Only `price_kind: "close"` rows count.** `unknown` rows are reported
  (how many, which statuses) but never imputed.

## Pre-registered hypotheses

Each has a direction, a measure, and what would count against it.

**H1: Convergence.** Within-item-type spread *decreases* over calendar
time.
*Measure:* the slope of spread vs. sale quarter, pooled across item types.
*Against:* a flat or rising slope.
*Caveat stated now:* the backfill may start after consumer AI appraisal was
already common (the index's first `end_date` will say). If there's no
meaningful "before", H1 becomes a forward-looking test on the daily harvest
and is reported as underpowered for now, not as confirmed.

**H2: Legibility gap.** Spread falls *faster* for AI-legible items than for
AI-illegible ones, so the gap between them *widens* over the study period.
*Against:* equal slopes, or illegible items converging faster.

**H3: Bidder depth is signal.** Within an item type, closes with more bids
sit *closer* to the item type's median (less dispersion as `num_bids`
rises).
*Against:* no relationship, or more dispersion at high bid counts.
Testable as soon as the backfill lands.

**H4: Owned data carries more information.** Estimates built from this
project's own local closes have *lower* log-loss against actual closes
than eBay comps, which in turn beat AI-only estimates.
*Against:* eBay or AI estimates matching or beating local history once
local coverage is ≥30 closes per item type.

**H5: The arbitrage window closes.** The share of lots that close ≥30%
below their item type's trailing median *declines* over time, and declines
faster for AI-legible items.
*Against:* a flat or rising share.

**H6: Late, bursty information** (bid-history experiment, separate path).
Most price discovery, measured as the share of total price movement,
happens in the final 10% of an auction's duration, and bids with
sniping-like timing (the final seconds) make up a growing share over time.
*Against:* steady price movement across the auction, and a flat snipe
share.

**H7: "Worth to me" differs from market value** (needs new infrastructure).
A recorded personal valuation (a max bid and the reason) differs from the
eventual close by more than the item type's market spread. In other words,
personal context is signal the market price doesn't contain.
*Against:* personal valuations landing inside the market's own spread.

## Data

| Source | What it gives | Status |
|---|---|---|
| Close-price history (`research/price_history/`) | every closed Musick lot: price, bids, close time | harvester built; backfill pending (run once, locally) |
| Live lots (`data/auction_lots.yaml`) | the current snapshot plus estimates (eBay/AI) | running daily |
| Bid histories | per-bid amount + time, **no bidder identities** (verified: the site exposes none) | separate experiment, not built |
| Personal valuations | "my max, and why" per watched lot | not built (H7) |

## Threats to validity (stated before seeing data)

- **One auction house, one region.** Findings are about Musick /
  Treasure Valley until replicated on another source (Phase 2 platforms).
- **Confounds on time trends:** the economy, seasonality, and changes in
  what Musick sells. Mitigation: within-item-type measures only, and
  season-matched comparisons where volume allows.
- **No adoption measurement.** We can't observe *who* uses AI. H1, H2 and H5
  test predicted *consequences* of adoption, not adoption itself. This is
  inference to the best explanation, and it will be written up that way.
- **Selection:** the site's own "featured"/ordering may shift which lots
  attract bidders over time.
- **Researcher degrees of freedom:** the item-type and legibility
  definitions are fixed above and committed as code before the analysis
  runs.
- **Observer effect:** if this project's owner bids using its estimates,
  those bids enter the data. Any lot we bid on is flagged (`we_bid`) and the
  analysis is run with and without those lots.

## Ethics

- **No identities, ever.** Bid histories are recorded as amounts and times
  only. No attempt is made to infer bidders' ages or identities from
  behavior. The participant population is often older and less
  tech-oriented; that's *context* for the argument, not something this data
  measures, and conclusions stay about *bidding patterns*, not *kinds of
  people*.
- **Polite collection only:** public pages, a 2s rate limit, no login, and
  no evasion of blocks.
- **This project is itself an arbitrage tool.** The write-up says so, and
  says which uses are private-value matching (buying what grandpa can fix)
  versus common-value arbitrage.
- **Transparency as the democratic version.** Publishing aggregate price
  history (PRICE-DISCOVERY.md Phase 5) closes the arbitrage window for
  everyone at once instead of selling it to early adopters.

## Reading list

- Hayek, "The Use of Knowledge in Society" (1945): prices as knowledge
  aggregation.
- Shannon, "A Mathematical Theory of Communication" (1948): entropy, mutual
  information, data processing.
- Howard, "Information Value Theory" (1966): information is worth what it
  changes about *your* decision.
- Akerlof, "The Market for 'Lemons'" (1970): information asymmetry and
  market breakdown.
- Grossman & Stiglitz, "On the Impossibility of Informationally Efficient
  Markets" (1980).
- Milgrom & Weber, "A Theory of Auctions and Competitive Bidding" (1982):
  common vs. private value, the linkage principle.
- Milgrom & Stokey, "Information, Trade and Common Knowledge" (1982): the
  no-trade theorem.
- MacKenzie, *An Engine, Not a Camera* (2006): models that reshape the
  markets they describe.
- Calvano et al., "Artificial Intelligence, Algorithmic Pricing, and
  Collusion" (2020).

---

## Lab notebook

*Dated entries. Append only. Record what was done, what was seen, and what
changed in the plan and why.*

**2026-09-28.** Pre-registration. Verified live that Musick keeps closed
catalogs reachable after close, and that the closed-auctions index lists
827 sales with UTC end times (`docs/AUCTION-MONITORING.md`). Close-price
harvester built; backfill not yet run. No price-history data has been
looked at. Owner's working hypothesis: prices converge around shared value
as centralized AI appraisal spreads, unevenly by adoption and legibility;
the countermeasure is personal context ("worth to me"). H1 is predicted
directionally (convergence) by the owner's choice.

**2026-09-28 (later), amendment: survivorship bias confirmed in the data
source.** The first production harvest (2,638 lots from 5 sales) was 100%
sold. A control-probed missing lot returned 404 while its neighbor loaded:
**unsold (or withdrawn) lots are deleted from closed catalogs.** Consequences
for the pre-registered plan, recorded before any analysis:
- Every spread measure (H1, H2, H3, H5) is computed on **sold lots only**
  and is labeled that way. Deleted lots are *missing not at random* (plausibly
  the ones whose bids didn't reach a reserve), so dispersion is understated
  and prices skew high.
- H3 is at particular risk: low-bid lots that failed to sell are exactly the
  ones removed, which could manufacture a bids-vs-spread relationship. A
  sensitivity check will be added once "vanished" lots (seen live, absent
  after close) are being recorded going forward.
- The backfill cannot recover these; only forward collection can.
- New threat to validity: **the data source's own retention policy**
  shapes what can be learned. This is itself a finding about price
  discovery: the market's public record keeps successes and erases
  failures.
Hypotheses and predictions unchanged.

