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

## ▶ Where we are / next session (handoff, updated 2026-10-07, orchestrator session)

*Read this first. It's the state of play, so a new session doesn't have to
reconstruct it. Update it at the end of every session.*

**2026-10-07 orchestrator session: live verification of PR #158**
(branch `claude/auction-orchestrator-verify-wv03ox`, not yet merged)
- **Verified live** (dispatched run #37, 37636864378, on d3f0189, clean,
  no Musick block in real traffic, committed e28bb39 and deployed):
  `auction_ends_at` on **87/87** lots; `condition_text` on **51/52**
  vehicles; `comp_*` on **66/87** lots (13,771 closes);
  `[live-seen] merged 5 small-engine/appliance lot(s) from 1332
  deep-crawled lot(s)` (catalogs 922 + 923 only, the two closing in 48h).
- **Still unverified:** the AI valuation prompt change (no
  `ANTHROPIC_API_KEY`; eBay 403'd on its first lookup again) and how the
  `comp_*`/all-in text actually look on the deployed `/auctions/` page.
- **Oct 4 scheduled failure, fixed on this branch:** the Dinger Palooza
  bot pushed to main mid-run (17:24:58) and our `git push` was rejected
  ("fetch first"), losing the day's lots. The commit step now does
  `git pull --rebase` + push, 4 tries. Unverified until merged and run.
- **Oct 5 scheduled failure: cause unknown.** The job was *cancelled*
  (not failed) at exactly 15:01; its log is 404 and the zip host is
  blocked from the sandbox. Owner asked whether it was a manual cancel.
- **Log-reading trap:** after "Ran N tests" the job log prints fake
  fetch notes from the test fixtures (`catalog/id/1,2,3`, a 212-byte
  `BLOCKED`). Those are NOT real Musick traffic. Only read fetch notes
  above the test step.
- **Grandpa-page false positives fixed:** "Shark Tooth" (fossil lot),
  "Dryer Towel" (pet bundle), "Microwave & Dishwasher Safe" (dinnerware)
  matched appliance keywords. `NOT_AN_APPLIANCE_RE` in
  `auction_finder.py` strips those phrases first; tests use the real
  titles. Left on purpose for owner: a Pilates bundle that does include
  a mini washing machine, and a core drill "with Vacuum Base".
- **Request budget per daily run (from run #37's log): ~140 Musick page
  loads.** ~61 fetch (2 index, 7 catalog page-1, 52 vehicle details),
  **30 guessed-API GETs that always return 202/empty**, ~29 live_seen,
  ~20+ harvest. Dropping the dead API probes would free ~30 loads/run,
  enough to pay for most of a wider deep crawl. Not done: owner decides.
- **Catalog 893** parsed 0 concluded lots and is retried every run
  (INCOMPLETE). Watch it; if it never parses, look at its markup once.
- **Blocked this session:** the close-history junk-price audit (task 4)
  - reading `research/price_history/` was denied by the session's
  permission check. Needs the owner's OK.
- **Owner decisions pending:** (1) widen deep crawl past 48h / to
  cars+guns (all 7 open catalogs ≈ +55 loads/run, about the 30 probes
  freed + 25); (2) drop the API probes; (3) confirm buyer's premium
  wording (15% <$10k, 10% ≥$10k, +$150 vehicle doc, +$15/firearm);
  (4) seller notes for guns/small engines need a detail render each
  (~1 load per lot, 19 guns + ~4 small engines today ≈ +23/run).

**2026-10-07 session (timing + hide + swarm pricing)** — not yet verified
against a live run, dispatch the workflow and check the new `auction_ends_at`
coverage:
- **Timing bug fixed:** `parse_musick_lots()` now derives `auction_ends_at`
  from each catalog row's own "Time left" string. Before, only vehicles that
  got the expensive detail render had an end time, so firearms/coins/jewelry
  showed "—". The detail step no longer wipes it when its own countdown is
  missing. Tests: `scripts/tests/test_musick_timing.py`.
- **Categorizer fixed:** Mazda/Hyundai/Kia/etc. cars were landing in "Other"
  (so never got VIN/mileage/title fetches); "revolver" wasn't a firearm word;
  lumber ("4x4") and a die-cast toy truck were filed as Vehicles.
- **Hide-a-lot:** ✕ button per row, remembered per browser in localStorage
  (keyed by lot URL), "Show N hidden" toggle, hidden lots excluded from the
  flagged count and email digest. Not synced across devices (static site).
- **Swarm pricing:** `research/swarm_prices_2026-10-07.yaml` — 22 lots (11
  `car_candidate` vehicles + 11 firearms) priced by one Haiku each. Rough
  and unverified (see its `caveats`): truck retails look high for 130k+ mile
  fleet units, and car hammer guesses ignore the live bid trajectory.
- **Small engines / vacuums (the grandpa gap):** the live finder only sees
  page 1 (50 lots) of each catalog; on 2026-10-06 all 20 small-engine lots in
  catalog 925 sat at positions 90-736. `live_seen.py` already pages whole
  catalogs closing within 48h, so it now also hands those lots to
  `auction_finder.merge_deep_lots()` (small engines only, deduped by lot id)
  - **zero extra Musick requests**. Scope limits: only catalogs closing
  within 48h are deep-crawled, and the personal watchlist still only sees
  page 1. Unverified on a live run - check `[live-seen] merged N` in the log.
- **Listing-aware valuation:** one `probe_url` run (2026-10-07, Wrangler lot)
  showed the seller's condition text lives in `description-info-content`;
  `parse_musick_lot_detail()` now returns `condition_text` (fixture:
  `tests/fixtures/musick_lot_detail_wrangler.html`), stored on vehicles during
  the existing detail render. `auction_value.py` now sends it to the model as
  `condition_notes` (+ year/make/model/mileage/title) and prices a decent
  RUNNING example first, then adjusts down for described problems. Only
  vehicles get it so far (guns/small engines don't get a detail render).
- **Close-price comps ("deep currents"):** `scripts/comp_baseline.py` - for
  vehicles/firearms/small engines, median + recency-weighted (60d half-life)
  average of comparable past Musick closes, trailing 365d, reported with n
  and days of history. History only starts 2026-08-27 so it is ~6 weeks old,
  not a year, until it accrues. Runs in the workflow before valuation and is
  shown on the page. Context for THIS auction, not a target.
- **Buyer's premium:** `scripts/musick_fees.py` + "≈ $X all-in" under each
  bid. Reading of the terms tab: 15% under $10k, 10% at/above, +$150 vehicle
  doc fee, +$15 per firearm. Quirk: winning at $10,000 costs less all-in than
  winning at ~$9,100-$9,999. **Not** folded into deal flags (THESIS
  pre-registered definitions). The "15%" is my reading of an ambiguous
  sentence - confirm with Musick.
- Suspect rows in the close history (a Wrangler at $19, a Paramount pistol at
  $9) look like parse artifacts; comp_baseline trims them but the harvester
  should be checked.
- Still open: wire swarm/`value_it.py` valuations into `auction_lots.yaml`;
  fold musick_fees into the deal math if the owner wants it.

**Live and working**
- Daily pipeline (GitHub Actions, 13:00 UTC; GitHub often runs it hours
  late): live lots → close-price harvest → valuation → **test gate** →
  commit → deploy.
- **Block handling (PR #141):** the first blocked page load stops all Musick
  requests for the run, a blocked run **never rewrites** the live lots
  file, and the harvester logs its index byte count and runs slowly (5s
  between page loads, at most 3 catalogs a day). eBay stops after its first
  403.
- `research/price_history/`: **4,399 real closing prices** (2,638 +
  **1,761 new** from the 2026-09-29 18:27 UTC run, which harvested
  catalogs 920/912/907 cleanly — see "block lifted" below), spot-checked
  against live pages. (Not in `data/`: Hugo can't load .jsonl, and that
  broke the site once. A test now guards against it.)
- `/auctions/`: the **18:27 UTC 2026-09-29 snapshot** (88 lots, up from
  47 — the first clean run since the block).
- `THESIS.md`: pre-registered hypotheses H1–H7, with a dated notebook.
- **Session V (VIN checks): built and run live 2026-09-29.**
  `scripts/vin_check.py` + `scripts/tests/test_vin_check.py` (99 tests,
  all green). Confirms the two documented suspects (1996 Tacoma odometer,
  1998/1997 Ram year mismatch) independently against live NHTSA data.
  Caught and fixed two real defects along the way — see Session V below.
  **Not yet wired**: a suspect flag doesn't flip `car_candidate` in
  `auction_lots.yaml`, and there's no ✓/⚠ column in the lot table UI yet.
  Run manually: `python scripts/vin_check.py [--candidates-only]`.
- **Session P (worth-to-me valuations): built and run live 2026-09-29.**
  `scripts/value_it.py` records a pre-close valuation, joined into close
  rows by `price_history.py`'s `build_row()`. 117 tests total pass (30
  new). See Session P below for the caveat found on non-vehicle lots.
  Run: `python scripts/value_it.py LOT_URL MAX "why" [--who owner|grandpa]`.
- **Session B2 (vanished-lot recovery): built 2026-09-29, not yet run
  live.** `scripts/live_seen.py` (new) + `price_history.py`'s
  `find_vanished_lots()`. 144 tests total pass (26 new). **Not verified
  against real markup yet** — dispatch the workflow manually with
  `debug_html: true` before trusting a scheduled run. See Session B2
  below for the caveat and the still-open live-probe item.

**Update 2026-09-29 18:27 UTC: the WAF block lifted.** After being blocked
since 2026-09-28 ~18:00 UTC (confirmed still blocked at the 19:59 run), the
next scheduled run went through clean — every catalog rendered normally
(no 212-byte pages), 3 catalogs harvested, 1,761 new price-history rows.
Exactly one clean run so far, not the "clean stretch of days" the backfill
recommendation below was waiting on — don't treat this as fully resolved
yet, just as the first good sign. Watch the next few scheduled runs before
revisiting the backfill decision.

**Blocked or known broken**
- **Valuation is effectively off.** eBay is dead from CI, and there's no
  `ANTHROPIC_API_KEY` (the owner's choice), so **every lot has a null
  estimate and no deal can ever be flagged.** Session E (pricing from our
  own close history) is the real fix. It's the only valuation source that
  isn't blocked or paid.
- **The history is still sales-only for now.** Session B2's vanished-lot
  recovery is built but not yet proven against a real catalog — the fix
  exists, hasn't been confirmed working. Dispatch manually first (see
  Session B2 below).
- **The bulk backfill is on hold** (next-sessions item 2).

**Check the next scheduled run first** (Actions → "Auction Watch", "Harvest
closed-lot prices" step) before touching the backfill decision. Confirm
the last 2-3 runs stayed clean (real byte counts, catalogs harvested, no
`BLOCKED`) before treating the WAF block as resolved. Don't probe Musick
directly to find out.

**Next sessions, in order** (items 0–2 need the owner's PC)
0. **Set up Claude Code on the PC.** Install it, open this repo, and it
   reads `CLAUDE.md`, which points here. Then run the first commands below.
1. ~~Read Musick's Terms of Service~~ **Done 2026-09-29.** Neither domain
   has a published ToS; robots.txt on both explicitly permits crawling
   (faster than our current cadence, even). Full findings logged in
   `docs/AUCTION-MONITORING.md`'s ToS section. Verdict: **no policy bars
   this** — the WAF block is purely a technical rate limit, not a
   statement of policy.
2. **Backfill decision: still hold — recommend option (b), reassess soon.**
   ToS is clear. The WAF block **lifted as of the 2026-09-29 18:27 UTC
   run** (see "block lifted" note above), but that's one clean run, not
   the multi-day clean stretch this recommendation was waiting on.
   Running a bulk backfill too early, right after a block, risks the
   owner's home IP — the one used to actually bid — getting blocked from
   the site entirely, which is a worse outcome than slower history growth.
   **Recommendation: watch 2-3 more scheduled runs first.** If they're
   all clean, the backfill decision (option a vs b) is worth revisiting
   then. THESIS H1 stays forward-looking only until it's actually run.
   When ready, run `python scripts/price_history.py --backfill`
   (estimate only, no `--yes`) to size it before committing. **The size
   estimate runs about 25% low:** it assumes 259 bytes per row, real rows
   average 320.
3. ~~Session V: VIN checks~~ **Done 2026-09-29** — see the handoff note
   above and the full Session V section below. Remaining: wire a suspect
   flag into `car_candidate` and add the ✓/⚠ row UI, whenever that's
   worth the layout time.
4. ~~Session B2: record vanished lots~~ **Built 2026-09-29, needs a live
   dispatch to verify.** Correction to this item's original "offline code;
   cloud is fine" note — that was wrong, this touches live Musick catalog
   pages (unlike Session V's NHTSA-only calls), so it needed the same
   Playwright/GitHub Actions environment as the rest of the Musick
   pipeline. See the handoff note above and the full Session B2 section
   below. Remaining: dispatch manually with `debug_html: true` to verify
   against real markup, then the live-probe-one-lot confirmation.
5. **Session E: first-party comps**, as soon as any item type has 30+
   closes, because it's the only way valuation comes back.
6. **Session D: history page + calibration**, after about 2 weeks of closes.
7. ~~Session P: "worth to me" field~~ **Done 2026-09-29** — see the
   handoff note above and the full Session P section below. Remaining: no
   UI surfaces `my_max`/`we_bid` yet.
7b. **Refine the jewelry watchlist group with `/refine-search`** (quick,
   offline, needs the owner's taste calls). It matches **0 of 2,384** real
   titles because it requires the exact phrase "yellow gold", which no
   listing uses. Fine jewelry is written "14K Yellow Gold", "18K White
   Gold", etc. A karat-based draft (10k/14k/18k/22k/24k, excluding
   gold-tone/plated/filled/costume) was tested 2026-09-28. It found **no
   real fine jewelry** in the closed history (those sales' jewelry was
   costume lots), plus noise: "BD-10K" (a trailer brake drum part number),
   "24K Gold Trim" decor, and Idaho **Goldback** currency notes. Owner
   decides: (a) does white gold count, or yellow only? (b) are Goldbacks
   wanted (→ Old Coins?) (c) do "10k"-style part numbers need a
   jewelry-context word, like `"14k gold"`? Validate against live
   snapshots over the next weeks as fine jewelry comes through (catalog 922
   had 18K opal and platinum coral rings live on 2026-09-28).
8. **Session H: bid-history experiment** (THESIS H6), only once items 1 and
   2 settle what request volume is acceptable.

**First commands on the owner's PC**
```bash
git pull
pip install pyyaml playwright && playwright install chromium
python -m unittest discover scripts/tests         # should be all OK
python scripts/probe.py https://bid.musickauction.com/auctions/catalog/id/914
#   one probe only: check that .debug/ has a real page (tens of KB), not a
#   ~200-byte block page. If it's blocked, stop and wait a day.
```

**Changing what gets watched:** use `/refine-search` (PR #144). It tests
draft keywords against every real title before editing
`data/auction_watchlist.yaml`, and saves the reasoning in
`data/search_profiles/`.

**Collection etiquette (applies to every session from now on)**
- Probe from the PC (`scripts/probe.py`), **a handful of pages per session**,
  never loops.
- Use the workflow's `probe_url` only to confirm CI behaviour, at most one
  or two a day.
- On any sign of a block: stop for the day. Never retry around it.

**Housekeeping backlog (not urgent)**
- `guess_category()` puts **72% of harvested lots in "Other"** (e.g. a 2005
  Freightliner M2). That's fine for the thesis, which uses normalized-title
  item types, but bad for any page grouped by category. Widen the keywords
  using real titles from `research/price_history/`.
- The public `debug/auction-html` branch still holds raw page dumps from
  the cloud-sandbox probing era. Delete it once local probing is routine.
- The cloud environment's network policy blocks `vpic.nhtsa.dot.gov` and
  `api.nhtsa.gov`. Add them to its allowed domains if VIN work should ever
  run from cloud sessions; GitHub Actions and the PC can already reach them.

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

## The market mechanics underneath this (2026-10-03)

Why this is worth building, not just a nice-to-have feature on top of an
auction scraper — captured from a conversation worth keeping rather than
losing to chat scrollback.

**The floor-compression problem — corrected 2026-10-03, see Related
research below.** The original claim here was stronger than the
evidence supports, so the correction is logged rather than quietly
edited away: a cheap, universally-available AI valuation ("Claude, how
much??" on a screenshot) was framed as *favoring buyers by default*,
on the logic that once both sides of a negotiation can pull the same
generic comp, "I found a lower comp" beats "trust my higher one." A
live-research pass found the real study closest to this claim — Fu,
Jin & Liu (NBER WP 29880) plus a 2025 Marketing Science paper on
Zillow's Zestimate — shows the opposite distribution: automated
valuation transparency raised **both** buyer surplus (~6%) and seller
profit (~4%+), with the largest gains in lower-information markets. The
honest version: price transparency tends to look like a **shared gain
from reduced friction/uncertainty**, not a one-sided transfer to
whichever side has the comp. The floor-compression logic may still hold
narrowly — a live two-party haggle over one specific item with
unresolved idiosyncratic risk is a different setting than a published
AVM feeding an entire market — but it shouldn't be stated as a general
law. Idaho auction bidding (many bidders, a real close, no
back-and-forth haggle) is closer to the AVM case than the haggle case,
which is worth remembering before assuming this project's own tooling
mechanically favors Jeremy as a bidder.

**The idiosyncratic-risk buffer, and why it's adverse selection.** A
generic comp prices the *category*, not the unit — it has no way to know
whether a specific item carries hidden risk (undisclosed damage, a bad
title, a rolled-back odometer). Buyers who can't verify that apply a
blanket discount below the floor as insurance against the unknown.
That's a strictly negative-margin outcome for any honest seller, since
they're discounted for a risk they don't actually carry — the market
prices toward the worst plausible unit in the category, not the specific
one actually on offer.

**De-fungibilization is the real edge, not a better number.** The way
out, for either side: don't try to out-guess the shared comp, retire the
specific risk the comp can't see. A verified VIN, a documented service
history, a frame inspection, a condition report — proof that *this* unit
isn't the worst-case one the floor price assumes — is worth more than any
haggling over the generic number, because it's selling certainty the
other side's cheap tool can't give them. This project already does this
structurally, not just in theory: `vin_check.py` against NHTSA, the
`/garage/` frame-rust/timing-belt checklist, `miles_per_year` instead of
raw odometer — every one of these is "verify something specific the
cheap comp assumes away," the same move a CPO premium or a professional
appraisal makes, just automated.

**Personal-use value is the other escape hatch.** If an item is worth
more *to a specific buyer* than to the general market — a project
vehicle, a sentimental piece — the resale comp is irrelevant, because
that buyer isn't pricing for an exit. It doesn't help build a pricing
*model*, but it's the real reason `value_it.py`'s "worth to me" field
(THESIS H7) exists as something separate from `estimated_value_mid`.

**This doesn't shrink the opportunity, it relocates it.** As casual AI
valuation gets cheap and ambient for everyone, the gap between a careful
buyer and an eyeballing one compresses toward zero. What doesn't
compress: owning data nobody else has (this project's first-party
close-price history, Phase 3) and verifying specific risk nobody else
bothered to check (VIN checks, condition history, Session V). That's the
actual long-run case for Phase 1 and Phase 3 mattering beyond
convenience — not "AI gives us an edge," but "an edge survives only as
long as it isn't something everyone's cheap AI already does for free."

**Who's actually doing this, casual to pro** (a framing, not a roadmap
item):
1. **Casual, single decision** — "is this a deal," no tooling, a one-off
   prompt on a photo. No lasting infrastructure, no reusable method.
2. **Power user / hobbyist** — a repeatable pipeline for one category.
   This is where Auction Watch and the car/garage finders already live.
3. **Small business** — the valuation is a business input (dealer
   pricing, pawn loan-to-value, a contractor's bid). It needs a visible
   method, not just a number, the moment someone else can check it.
4. **Professional / institutional** — the valuation *is* the deliverable
   and has to survive an adversarial check; every number needs a primary
   source and a grade (see `CLAUDE.md`'s own working rules — the same
   discipline, formalized).
5. **Autonomous agents that act, not just advise** — `business_agent.py`
   (Phase 4, stubbed) is this project's toe in that water, deliberately
   gated on Phase 3 data existing first (Decision 9): acting on a number
   nobody's verified is a worse failure mode than a wrong price estimate.

---

## Related research (verified via live search, 2026-10-03)

The market-mechanics section above was a conversation, not a literature
review. This section is the literature review — four research passes,
each required to confirm citations via live search rather than recall,
and to say plainly when something couldn't be confirmed rather than
invent a source. Confidence is noted per item; re-verify anything going
into a client-facing deliverable rather than trusting this list alone.

**Foundational information-asymmetry theory**
- **Akerlof (1970), "The Market for 'Lemons'," QJE 84(3):488–500.**
  Confirmed against hosted PDFs/RePEc. The direct fit: sellers knowing
  more than buyers about quality causes buyers to discount price for
  lemon-risk, good sellers exit, average quality (and price) spirals
  down. This is the exact failure mode the project's de-fungibilization
  tools (VIN checks, frame inspection) counteract.
- **Spence (1973), "Job Market Signaling," QJE 87(3):355–374.**
  Confirmed (DOI 10.2307/1882010). Partial fit only, worth stating as a
  contrast rather than an analogy: signaling theory is about the
  *informed* party (the seller) credibly revealing quality. A free AI
  valuation tool instead arms the *uninformed* party (the buyer) — closer
  to Stigler's logic below than Spence's.
- **Grossman & Stiglitz (1980), "On the Impossibility of
  Informationally Efficient Markets," AER 70(3):393–408.** Confirmed.
  Double-edged, flagged deliberately: if AI pushes the cost of
  valuation information toward zero, this paradox predicts the
  *incentive to gather or trade on private information collapses* —
  markets could converge on "the AI's number" rather than staying
  informationally rich. A real tension for this project's long-run
  thesis, not a clean win.
- **Stigler (1961), "The Economics of Information," JPE 69(3):213–225.**
  Confirmed (DOI 10.1086/258464). Cleanest fit of the four: price
  dispersion persists because search costs money/time; falling search
  costs predict narrowing dispersion. An AI tool making "what's this
  worth" instant and free is close to a live test of this prediction.

**Auction theory**
- **Capen, Clapp & Campbell (1971), "Competitive Bidding in High-Risk
  Situations," Journal of Petroleum Technology 23(6):641–653.**
  Confirmed. The winner's curse: in common-value auctions, the winning
  bid comes from whoever had the highest *estimate*, which is
  systematically more likely to be an overestimate than the truth. This
  project, observing many closed lots, can measure realized winner's-
  curse bias directly — something a single bidder never could.
- **Vickrey (1961), "Counterspeculation, Auctions, and Competitive
  Sealed Tenders," Journal of Finance 16(1):8–37.** Confirmed, but for
  second-price/truthful-bidding mechanics specifically, not the
  private-vs-common-value taxonomy (that split is standard later
  textbook material, e.g. Milgrom or Krishna's *Auction Theory* — not
  sourced to Vickrey directly). The taxonomy itself matters here: a used
  truck is closer to **private-value** (worth modeling as a distribution,
  buyer use varies), a gold coin or jewelry lot is closer to
  **common-value** (closer to one estimable number, and the winner's-
  curse correction actually applies there, not to the trucks).
- **Wilson (1977), "A Bidding Model of Perfect Competition," Review of
  Economic Studies 44(3):511–518** (bid shading — rational bidders
  underbid their own value estimate to correct for the winner's curse,
  more shading as bidder count rises). Mechanism confirmed; the exact
  page citation was **not** independently re-verified against a primary
  source — re-check before using it beyond this internal doc.
- **Ockenfels & Roth (2006), "Late and Multiple Bidding in Second-Price
  Internet Auctions," Games and Economic Behavior 55(2):297–320.**
  Confirmed. On fixed-deadline platforms, bidders rationally "snipe" —
  bid only in the closing seconds — far more than on auto-extending
  platforms. Directly testable against this project's own full bid-
  timing data (THESIS H6 / Session H), not something to assume.

**Price-transparency empirics — includes the correction logged above**
- **Fu, Jin & Liu, NBER Working Paper 29880 (2022, rev. 2023)** +
  **a 2025 Marketing Science paper** on Zillow's Zestimate. High
  confidence (NBER PDF plus independent press corroboration). Finding:
  raised buyer surplus ~6% **and** seller profit ~4%+, bigger gains in
  lower-information markets — a shared-gain result, not a one-sided
  transfer. This is the source for the correction above.
- **Brown & Goolsbee (2002), "Does the Internet Make Markets More
  Competitive? Evidence from the Life Insurance Industry," JPE
  110(3).** High confidence. Internet comparison tools cut term-life
  prices 8–15%, consumer surplus +$115–215M/year — but dispersion rose
  initially as tools were adopted, then fell as usage spread.
  Non-monotonic; don't assume transparency compresses a market
  instantly rather than over an adoption curve.
- **Carfax / used-car surplus shift: no clean causal study found.**
  Real, relevant background exists (Biglaiser, Li, Murry & Zhou, FTC
  working paper on dealers as information intermediaries; Cho, Frankel
  & Martin, "Law and Lemons," HBS, on Carfax's 1992 mileage-verification
  reports in an Akerlof-disclosure frame) but nothing directly measures
  a buyer/seller surplus shift from Carfax specifically. "Clean Carfax
  as a sellable premium" is a plausible inference, not a stated finding
  — don't cite it as proven.

**Current AI-valuation landscape (2024–2025 — most time-sensitive of
all four passes; re-verify before relying on this in six months)**
- **Shipped, not just announced:** several indie photo-to-value apps
  (WhatsitAI, Appraizely, ResaleScan, and similar) are live on app
  stores. eBay's "AI Price Suggestions" (Seller Hub) analyzes last-30-
  day sold comps but requires seller confirmation — not autonomous.
  CarMax Instant Offer and Carvana's offer flow are both real,
  algorithmic (VIN + condition + market comps; Carvana adds computer-
  vision condition assessment).
- **LLMs specifically for valuation:** arXiv 2506.11812 (2025)
  benchmarks LLMs against traditional automated-valuation models for
  real estate. A 2025/26 Journal of Real Estate Research paper found
  LLM-extracted features improved an XGBoost AVM's RMSE by 24.3%.
- **Algorithmic collusion is a live legal issue, not a hypothetical.**
  *DOJ v. RealPage* reached a proposed settlement Nov 2025 (no
  liability admission, but real constraints: data must be ≥12 months
  old, no real-time lease data, no below-state-level modeling, a
  7-year court-monitored term). The foundational academic paper is
  Calvano, Calzolari, Denicolò & Pastorello, "Artificial Intelligence,
  Algorithmic Pricing, and Collusion," AER 110(10), **2020** (Q-learning
  pricing bots, not LLMs — correcting an earlier draft's wrong year/
  attribution). A 2024 arXiv paper (2404.00806) specifically found LLM
  pricing agents also tacitly collude in repeated-pricing simulations —
  confirmed to exist via search, abstract-level only, not full-text read.
- **Autonomous transacting agents are real and already failing in
  documented ways.** OpenAI's Instant Checkout / Agentic Commerce
  Protocol (Sept 2025) is real and shipped. arXiv 2508.02630 (2025)
  found model-dependent purchasing bias in AI shopping agents. Reported
  (2025 journalism, not yet controlled studies) failure modes: agents
  overbidding in auction formats, inability to weigh winning against
  true value, prompt-injection attacks against agents holding payment
  credentials. Directly relevant to why `business_agent.py` (Phase 4)
  stays gated on real Phase 3 data under Decision 9 — an LLM judgment
  with no price grounding is exactly this failure mode, already
  observed elsewhere.
- **Weakest area: AI tools changing everyday resale/thrifting
  behavior.** Only a self-reported industry figure exists (ThredUp's
  2025 report, via Forbes: 23% resale-market growth in 2024,
  "AI-tool-driven") — an interested party's own number, not
  independently audited. No genuine academic study was found on this
  specific question; treat resale-tech marketing claims ("15x faster
  pricing") as vendor claims, not research.

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
render it locally with `scripts/probe.py` → read the dump in `.debug/` →
write the parser against that real markup → dry-run against the saved HTML
→ ship → one `probe_url` workflow dispatch to confirm it works from CI's IPs
too. (The old route, dispatching `probe_url` for every probe and reading the
public `debug/auction-html` branch, was a cloud-sandbox workaround. It also
helped trip Musick's WAF. Keep probes few; see the handoff block's
"Collection etiquette".)

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

- [x] `normalize_query(title)`: shipped in PR #135, with 36 tests.
- [x] Verdict: the first production run with normalized queries got 403s
      and ~13.6 KB challenge-sized pages from GitHub's IPs. **eBay is
      blocked from CI.** Recorded in the engineering log ("eBay from CI").
- [x] Skip after the first 403 per run: PR #141. **Not evaded.**
- [ ] (Optional, for the record) one local lookup from the PC to confirm
      that residential IPs get real results. That doesn't change the
      pipeline, which runs on CI.
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

### Session B2: Record lots that vanish (recover unsold lots)

**Why:** unsold lots are deleted after close (see the engineering log,
"Unsold lots disappear after close"), so the history is sales-only. The
only recovery is forward: remember lots seen live, and record the ones that
never show up in their closed catalog.

**Built 2026-09-29.**
- [x] Live fetch: `scripts/live_seen.py` finds catalogs closing within
      ~48h (`open_candidates_closing_soon()`, reusing the `?alf1=4` index
      page's not-yet-closed rows) and pages through each whole catalog
      (`?items=100&page=N`, not just page 1). Saves each lot's last
      observed bid, bid count and `observed_at` to
      `research/price_history/_live_seen.jsonl` via
      `price_history.append_live_seen()`.
- [x] Harvester: `price_history.py`'s `harvest_catalog()` now calls
      `find_vanished_lots()` after a **complete** harvest — any lot seen
      live for that catalog but absent from the closed pages gets a row
      `price_kind: "vanished"`, `price: null`, `last_seen_bid`,
      `last_seen_num_bids`, `last_seen_at`. Never a close. Skipped
      entirely on an incomplete harvest (a partial lot_id set would
      false-positive every not-yet-fetched lot as vanished).
      26 new offline unit tests (144 total pass), including an
      end-to-end `harvest_catalog()` integration test with a synthetic
      vanished lot.
- [ ] **Not yet done:** probe one lot seen live and then vanished, to
      confirm the 404 pattern holds across more than one lot. Needs a real
      lot to actually close first — a wait-and-check task, not something
      to force in one session.
- **Caveat, same as every new Musick-facing script before its first real
  run:** the render/page-walking logic in `live_seen.py` is unverified
  against live markup — written without Playwright available locally (see
  its module docstring). The parsing logic itself (`parse_live_lots()`)
  reuses `price_history.py`'s already-verified regexes and is tested
  against the real `musick_catalog_920_open.html` fixture. Wired into
  `.github/workflows/auction-monitor.yml` as its own
  `continue-on-error: true` step — **dispatch manually with
  `debug_html: true` first** and check `_live_seen.jsonl` before trusting
  a scheduled run.

### Session V: VIN checks (free NHTSA data, no Musick load)

**Why:** 18 vehicles in the 2026-09-28 snapshot have VINs, and 10 pass the
candidate filter (under 150k miles, clean title). Nothing checks them. An
offline pass that day (VIN check digit plus model-year code) found two
suspect **candidates**:
- **1996 Toyota Tacoma, 4TANL42N8TZ179445, listed at 51 miles.** On a
  30-year-old truck, that's almost certainly an odometer rollover or unknown
  true mileage. It's a "candidate" only because 51 < 150,000, which is a
  hole in our own filter.
- **Dodge Ram 3500 listed as 1998, 3B7MF33W5VM550364.** The VIN's year code
  `V` means model year **1997**. It may be a registration-year difference,
  but check the title, because model year affects parts and value.
All other check digits were valid and year codes matched.

- [x] `scripts/vin_check.py`, with a check-digit and model-year-code
      validator (offline, pure function, unit-tested in
      `scripts/tests/test_vin_check.py`, 14 tests). The logic already used
      above: transliteration table, weights `8765432X098765432`, and the
      year code at position 10. **Verified 2026-09-29:** re-ran against
      the Tacoma and Ram above, offline, and reproduced both documented
      flags exactly (odometer_suspect at 51mi; year_mismatch 1997 vs 1998).
- [x] NHTSA vPIC decode
      (`https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{VIN}?format=json`,
      free, no key, official public API). Compares decoded year, make and
      model against the listing and flags any mismatch.
      **Run live 2026-09-29 from the PC** against all 18 real VIN'd lots —
      first real NHTSA verification. Caught and fixed a real defect before
      it shipped: Ram-badged trucks decode from vPIC as make `DODGE` (its
      pre-2010 WMI mapping), and listings store the trim number ("1500")
      where vPIC returns the base model name ("Ram") — both would have
      false-positived as suspect on every Dodge/Ram truck in the watchlist
      (4 of 5 "suspects" in the first live run were this, not real issues).
      Fixed: a Ram/Dodge make alias, and model-name mismatches downgraded
      to a `note` (worth a glance, not a red flag) rather than `suspect`.
      Confirmed clean on a second live run.
- [x] Recalls and complaints by make/model/year
      (`https://api.nhtsa.gov/recalls/recallsByVehicle?...`,
      `.../complaints/complaintsByVehicle?...`): counts plus the top few
      recall summaries. **Run live 2026-09-29.** Caught a second real
      defect: NHTSA's recalls/complaints endpoints return **HTTP 400 for a
      legitimate zero-result query**, not just for errors — the body is
      still valid JSON (`{"count":0,...}`). The original error handling
      discarded that as a failure, which would have made "checked, no
      recalls on file" indistinguishable from "couldn't check." Fixed to
      parse the body regardless of status code.
- [x] Plausibility flags: mileage under 1,000 on a vehicle more than 5
      years old flags `odometer_suspect`. Very high miles/year flags
      `high_miles_per_year` (a note, not a suspect flag). **Not yet
      wired to flip `car_candidate: false` in `auction_lots.yaml`** — the
      script currently reports flags standalone; feeding a suspect flag
      back into the pipeline's own candidate filter (and the ✓/⚠ row UI
      below) touches `auction_finder.py` and
      `layouts/partials/auction-lot-table.html` and is a deliberate
      follow-up, not done here.
- [x] Cache per VIN **forever** (`data/.cache/vin_{VIN}.json`) for the
      decode; recall/complaint counts refresh after 30 days since those
      can grow over time. Per Decision 6: key on the item, not the bid.
- [ ] Run for watchlist vehicles only, after the detail enrichment step,
      with polite pacing. Show a small ✓/⚠ with details on each vehicle row.
      (CLI supports `--candidates-only` and paces requests 1.5s apart; the
      pipeline wiring and row UI are the follow-up above.)
- [ ] Doesn't replace a paid Carfax/AutoCheck history (accidents, owners).
      It shortens the list worth paying for.

**Where:** the owner's PC or GitHub Actions. The cloud sandbox's network
policy blocks both NHTSA hosts. **Next actual run should be from the PC**,
since that's where this session is now — `python scripts/vin_check.py`
against the live 18 VIN'd lots, to get the first real NHTSA verification.

### Session P: "worth to me": record personal valuations (THESIS H7)

**Why:** H7 needs a personal valuation recorded **before** the close, to
compare against the market price. Nothing records one today.

**Built and verified 2026-09-29.**
- [x] `data/my_valuations.yaml`: per lot (platform plus lot_id), `my_max`,
      `why` (free text: repair cost, use value, resale plan), `who` (owner,
      grandpa), `we_bid`, and `recorded_at`. Written by
      `scripts/value_it.py LOT_URL MAX "why" [--who owner|grandpa]` (never
      hand-edit an existing entry — see the file's own header).
      `scripts/value_it.py --mark-bid LOT_URL` sets `we_bid: true` on an
      existing entry, for THESIS's observer-effect measure (did recording
      a number change whether we actually bid?).
- [x] The harvester joins these to closes: `price_history.py`'s
      `build_row()` now takes an optional `valuations` dict and adds
      `my_max`/`we_bid` to a close row when a (platform, lot_id) match
      exists — omitted entirely otherwise, same convention as
      `watchlist_matches`. `load_valuations()` reads and caches
      `data/my_valuations.yaml`.
- [x] Never back-filled after the close: `value_it.py` refuses to record
      (or mark a bid on) a lot that's already closed, and refuses to
      overwrite an existing valuation. **Caveat found during smoke
      testing:** the close-time check only works for vehicle lots — most
      categories (coins, jewelry, tools) don't carry an `auction_ends_at`
      field at all. For those, the only guard is "still in the live
      snapshot", which is valid (a closed lot vanishes from the next
      day's fetch) but only as fresh as the last successful pipeline run
      — currently stale, since Musick is still WAF-blocked. Documented in
      `value_it.py`'s `_guard_not_closed()` docstring.
- [x] 30 new offline unit tests (`scripts/tests/test_value_it.py`,
      `ValuationsJoinTests` in `test_price_history.py`) — 117 total pass.
      Smoke-tested live against the real `auction_lots.yaml` (via a
      scratch copy, never touching the real `my_valuations.yaml`): record,
      mark-bid, duplicate-refusal, and the ends_at-missing case all
      behaved as designed.
- [ ] Not yet done: no UI surfaces `my_max`/`we_bid` anywhere (the lot
      table, a history page). Small follow-up once Session D exists.

### Session H: bid-history experiment (THESIS H6)

**Gate:** only after the ToS read and the backfill decision set an
acceptable request budget. Every bid-history page is one more page load.
- [ ] Sampling design first, written into THESIS.md before any fetch:
      watchlist lots plus a small random stratified sample per sale, capped
      at N pages per day.
- [ ] Parse `.../bidding-history/id/{catalog}/lot/{lot}` (verified: a
      two-column table of time and amount, newest first, **no bidder
      identities**, timestamps with **no year**, so borrow it from the
      catalog's `end_date` and handle sales that span New Year).
- [ ] Store bid trails in `research/bid_history/`. Never store identities,
      even if the site starts exposing them.
- [ ] Measures from THESIS H6: share of price movement in the final 10% of
      the auction's duration, and share of bids with snipe-like timing,
      over time.

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
