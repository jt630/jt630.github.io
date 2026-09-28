# Auction Watch — field notes

Monitors Boise-metro government and police surplus auctions and flags lots where
the current bid is well under what the thing would actually resell for. Renders at
[`/auctions/`](../content/auctions.md).

Written 2026-09-18. The tooling is
[`scripts/auction_finder.py`](../scripts/auction_finder.py) (pulls lots) +
[`scripts/auction_value.py`](../scripts/auction_value.py) (AI resale estimate + deal
score), scheduled by
[`.github/workflows/auction-monitor.yml`](../.github/workflows/auction-monitor.yml).

## Why bother

Reading a local auctioneer's listings by hand every few days doesn't scale.
This automates the boring part — pull what's coming up, ask Claude (and eBay
sold comps) what each lot would actually resell for, and surface the gap.
Grandpa already runs the Meridian-area circuit in person via Musick Auction
Co.; this watches that same source and adds the value-checking he wouldn't
otherwise have time for.

## Scope is currently narrowed to Musick alone

`PLATFORMS` in `auction_finder.py` is `("musick",)` by explicit request —
Musick Auction Co. is the one platform actually tied to Grandpa's real
auction circuit, not a national listing site he'd otherwise never visit. The
other four (`_DISABLED_PLATFORMS`: PublicSurplus, GovDeals, Municibid,
PropertyRoom) still have working fetch code, just not in the active
`PLATFORMS` tuple — add any back to re-enable. They remain **unverified
against live markup** (this dev sandbox's network policy blocks all of
them), unlike Musick below.

## Musick, verified against real markup (2026-09-21)

`musickauction.com` was a domain *guess* ("musick" + Boise-auction context →
Musick Auction Co., Nampa/Meridian, ID) - confirmed correct via a live
GitHub Actions run whose raw HTML landed on the `debug/auction-html` branch
(see `.github/workflows/auction-monitor.yml`'s `debug_html` dispatch input).
What that run found, and what `auction_finder.py` now does with it:

- **musickauction.com is a WordPress/Divi marketing site, not the bidding
  platform.** It carries zero price/bid data. `/`, `/auctions`, and
  `/upcoming-auctions` all 200; `/current-auctions`, `/online-auctions`, and
  `/law-enforcement` all 404 — "Current Auctions" in the nav just links to
  `/auctions/`. `MUSICK_PATHS` is now `["/auctions", "/upcoming-auctions"]`
  (the homepage has no listings at all; both remaining paths embed the
  identical widget, kept as a fallback pair rather than trimmed to one).
- **Each upcoming sale is one AUCTION EVENT, not one lot** — a Divi "Query
  Wrapper" widget renders a `<div class="query-row">` per event, each with a
  `.qw-title` (the sale's headline, e.g. *"MERIDIAN - 942 - TRUCKS, CARS,
  GUNS, AMMO, DJI DRONE, PROJECTOR, TOOLS, FURNITURE AND MORE!!"*), a date, a
  location (Meridian or Nampa), a photo, and a link out to
  **`bid.musickauction.com/auctions/catalog/id/N`** — a separate subdomain
  that (presumably) has the real per-item lot/bid data.
  `parse_musick_events()` in `auction_finder.py` parses this widget's exact
  markup, and is now confirmed working **live in production**, not just
  against a saved sample: the `debug_html: true` run on the merged code
  extracted all 6 currently-upcoming events with correct titles, dates,
  locations, and category classification (3 Vehicles, 1 Heavy Equipment,
  1 Firearms, 1 Other) — matching a local dry-run against the same saved
  HTML exactly. `data/auction_lots.yaml` on `main` now holds this real data,
  and it's live on `/auctions/`.
- **`bid.musickauction.com` does not respond to a plain GET** —
  `fetch_musick_catalog()` tried all 6 discovered catalog links; every one
  came back `HTTP 202` with an **empty body**. That pattern (a "request
  accepted" status with nothing to parse) is the signature of a JavaScript-
  rendered single-page bidding app — the kind of thing `urllib` fundamentally
  can't see into, no matter how the parser is written, since the real content
  never arrives in that initial response at all.
- **`scripts/musick_render.py`** is the fix for that: it loads a catalog URL
  in a real headless browser (Playwright + Chromium) and waits for the
  network to go idle before reading the rendered HTML, so JS has had a
  chance to actually populate the page. `fetch_musick_catalog()` now tries
  this first and only falls back to the old plain-`fetch()` path (which
  won't produce real data, per above) if Playwright genuinely isn't
  available. `.github/workflows/auction-monitor.yml`'s "Install Playwright's
  Chromium" step (`playwright install --with-deps chromium`) is what
  actually provides the browser in production.
  Confirmed **live** via a `debug_html: true` run against the actual
  target (workflow run `35563823234`): Chromium rendered real catalog
  content for all 6 events, 41KB–216KB each, saved to
  `debug_html/musick_catalog__914.html` through `__919.html` on the
  `debug/auction-html` branch.
- **No hidden JSON API — the SPA doesn't need one.** Both hunts (the
  passive XHR/fetch log in `render_catalog_page()` and the ~15-pattern
  `brute_force_musick_api()` guess probe) came back empty-handed: the only
  XHR/fetch call the page makes while loading is
  `POST https://bid.musickauction.com/sync/lot`, which just live-updates
  bids in place *after* the page has already rendered — the initial page
  load is server-rendered with every lot's data already in the markup, so
  there was never a lighter endpoint to find. `brute_force_musick_api()`
  and its 15 guessed URL patterns are kept in the code as a cheap
  reconnaissance pass (still logs `[musick-api-probe] ...` every run) in
  case that ever changes, but the real answer turned out to be "render
  once, the data's already there."
- **`parse_musick_lots()` now extracts real per-item lots** from that
  rendered markup — CONFIRMED against all 6 real saved catalog pages, not
  guessed. Each lot lives in
  `<li id="blkLotItemMain{lotId}" class="item-block">…</li>`, with a lot
  number, title + detail-page link, current bid (`item-currentbid`),
  asking bid (`item-askingbid`), bid count (`Bidding history(N bids)`),
  and time left. A lot nobody has bid on yet shows `item-starting-bid`
  ("Starting") instead of a current bid — those are kept with
  `current_bid: None` (a minimum isn't a real bid — same rule
  `auction_value.py` already applies) and their starting price/time-left
  folded into the description instead, rather than being dropped.
  `fetch_musick_catalog()` tries `jsonld_to_lot()` first (cheap, and correct
  if the site ever adds real JSON-LD) and falls back to this real parser —
  which is what actually fires today, since Musick's rendered markup has no
  JSON-LD at all.
  **Only page 1 of each catalog is fetched** (the pager shows "Viewing items
  1-50 of N" — up to 1087 for the biggest sale seen so far), so this covers
  the first 50 lots per auction, not the full catalog; paging through
  `?page=N` is future work if that proves worth the extra Playwright
  renders.
- **Real numbers from that run**, across the 6 currently-upcoming sales: 251
  real per-lot rows total (50 each from 5 sales, 1 from the single-lot
  "OFFSITE — manufactured home" sale), spanning real current bids from $8
  (a 6-pack of LED flashlights) up to $5,200 (a 2017 Infiniti QX60), including
  several actual police-surplus vehicles in the Meridian government-surplus
  sale ("2020 FORD EXPLORER - LOCAL POLICE AGENCY!", "2010 DODGE CHARGER -
  GOVERNMENT SURPLUS!"). This is real, per-item, currently-live bid data —
  not the event-level placeholder rows this file used to be stuck at.
- The event titles are genuinely category-rich text ("TRUCKS, CARS, GUNS,
  AMMO..."), which is what motivated switching `guess_category()`'s matching
  from a plain substring check to `\bword s?\b` (word-boundary, optional
  trailing s) — a bare substring match on short words like "car" or "gun"
  would have false-positived on "scar"/"cargo"/"gunmetal" etc. Also added
  "car", "truck", "vehicle", and "gun" as keywords once that was safe.

## Closed lots, verified against real markup (2026-09-28)

Session A of `PRICE-DISCOVERY.md`'s build plan, answered by four live `probe_url`
dispatches against `bid.musickauction.com` (raw dumps landed on `debug/auction-html`,
read and discarded, never committed — see that file's build plan for the loop).

**Already verified going into this session** (2026-09-21/23, kept here for one place
to look): catalog 914 closed 09/23/2026 9:22 PM MDT, is gone from the upcoming list,
but a plain GET still renders it — `<span class="auction-closed">Closed</span>`, and
`start-end-dates` shows absolute start/end ("09/09/2026 5:00 PM MDT - 09/23/2026 9:22
PM MDT"). A closed lot lives in `<li id="blkLotItemMain{lotId}" class="item-block">`
with `<li class="item-win-bid"><span class="title">Winning Bid</span>...<span
class="exratetip" data-lid="511357">4,000</span>` and `<li id="item-status"
class="item-status">...<span class="ended sold">Sold</span>`. A live (open) lot uses
`item-currentbid`/`item-askingbid`/`item-starting-bid` and an empty `item-status`
instead.

**A. Is there an enumerable index of closed catalogs, and how far back?** Yes, and
it's better than expected. `https://bid.musickauction.com/auctions/?alf1=4` (the
"Closed" option in the filter `<select name="alf1">`, `data-id="5"` — the earlier
guess of `?status=2&auctioneer=3` was wrong: `auctioneer` isn't a real param at all,
it happened to collide with a *different* filter, `alf9` (Location), whose
`data-id="3"` is "Real Estate" — that's why the first probe silently returned "No
results found" for a location with almost no auctions, not because closed auctions
don't exist) returns a page whose embedded JSON (`data-server="server-data-json"`,
key `auctionRows`) lists **827 total auctions**, sorted by `end_date` descending, 50
per page (`?page=N`, page 17 is the last). Each row is structured data, not just
markup to scrape:
```json
{"id":"914","name":"MERIDIAN - 938 - CONSTRUCTION SALE! ...","end_date":"2026-09-24 03:22:00",
 "start_date":"2026-09-09 23:00:00","status":"3","total_lots":"493","timezone_location":"America/Denver"}
```
`status` is `"3"` for a catalog that has actually closed (end_date in the past) and
`"1"` for one still upcoming — despite the `alf1=4` filter, page 1 still mixes in a
handful of not-yet-closed auctions (the 7 newest-`end_date` rows on page 1 all had
`status: "1"`), so the filter narrows the sort/default view but the harvester should
check `status`/`end_date` itself rather than trust the URL param alone. `end_date` is
an absolute timestamp **in UTC**, despite the `timezone_location: "America/Denver"`
field sitting next to it (that field is the sale's display zone, not the timestamp's).
Cross-checked in review against each catalog page's own `start-end-dates` text: 914's
`2026-09-24 03:22:00` is "09/23/2026 9:22 PM MDT", and 920's `2026-09-28 23:07:00` is
"09/28/2026 5:07 PM MDT", both exactly UTC−6. Reading it as Denver time would put
every close 6 hours late. Also note `total_lots` (493 for 914) doesn't match the
catalog page's own "of 470" count; likely withdrawn lots, so page until empty rather
than trusting `total_lots`. This is a materially better source of "when did this close" than parsing
`start-end-dates` text off each catalog page individually, since it comes for free
for all 827 catalogs in one render. This page is itself a decent target for the
`_pending.json` harvester: one render of `?alf1=4&page=1` gives id + end_date +
total_lots for the 50 newest sales without touching a single catalog page.

Catalog IDs are **not perfectly sequential but close** — one page of results spanned
ids 866–923 (58-wide range for 50 rows), with gaps for single-lot "OFFSITE"/real-estate
sales interleaved in the same numbering (e.g. 866 "REAL ESTATE AUCTION", 892/893
"OFFSITE" sales sit between normal Meridian/Nampa sale ids). So walking `catalog/id/N`
sequentially is viable as a *supplement* — it will hit real catalogs most of the time
but needs to tolerate gaps and the occasional single-lot/real-estate sale — but the
`?alf1=4` index above is the better primary source since it hands over id + end_date
+ total_lots directly, no guessing which N values exist.

**B. Does the bidding-history page persist the full bid trail, and is there personal
data?** Yes to persistence, no personal data found. `https://bid.musickauction.com
/auctions/bidding-history/id/914/lot/511357` (title: "Bidding history on lot 800 in
sale 2173" — the lot's *display* number, 800, is different from its internal id,
511357) rendered a `<table class="footable foolarge">` with **exactly two columns,
Date/Time and Bid Amount** — 35 bid rows plus a header (matching the catalog's
"Bidding history(35 bids)"), **newest first**: winning $4000 at "09/23 1:41:12 PM MDT"
in the top row (matching `item-win-bid` on the catalog page exactly) down to the
opening $500 at "09/10 12:28:06 PM MDT". The timestamps carry **no year**, so the
parser has to borrow it from the catalog's `end_date` (and handle a sale that spans
New Year). No bidder ID, handle, name, or any other identifying field
appears anywhere in the table or its markup — the harvester can record the full bid
trail (amount + absolute timestamp per bid) with zero risk of storing bidder
identities, because the site itself doesn't expose them here.

**C. Does `?items=N` page a closed catalog, and what do low-value/unsold lots look
like?** `https://bid.musickauction.com/auctions/catalog/id/914?items=100&page=5`
confirmed **`items=100` is honored** — the item-count `<select>` shows
`data-id="100" selected="selected"`, and the page rendered exactly 70 lots, which is
`470 − (4 × 100)` — i.e. lots 401–470, the correct tail of the 470-lot catalog at
page size 100. **All 70 lots on this page were `<span class="ended sold">Sold</span>`**,
with winning bids from $5 up to $185 — still no unsold/passed/no-bid lot observed in
either sample page (page 1 high-value, this page 5 low-value). The site's own JS
translation strings do define `langUnsold: "Unsold"` and `langReserveNotMet:
"Reserve not met"` (found in a `<script>` config block, not in any rendered lot), so
the markup for a genuinely unsold lot almost certainly exists and is worth grabbing a
real sample of before the harvester's parser hard-codes "ended sold" as the only
closed state — **not yet verified against a real unsold lot**, flagged here rather
than guessed.

**D. Lot-detail page** — not probed this session (budget spent on A–C, which were
higher priority for the harvester design); the vehicle-detail enrichment section
above already confirms lot-detail pages carry a clean-title status timestamp
(`auction_ends_at` computed from a countdown at fetch time) for **live** vehicle
lots, but whether the same page shows a winning bid / absolute close timestamp after
close is still open. Worth one probe in Session B before relying on it.

### Architecture implication for the harvester

**Closed catalogs stay reachable at their normal catalog URL — there is no race
against the upcoming-list rotation.** A catalog that has closed and dropped off
`/auctions/` or `/upcoming-auctions/` still renders fully at
`bid.musickauction.com/auctions/catalog/id/{N}`, with every lot's final state
(`item-win-bid` + `item-status` "ended sold") in the same markup shape as a live
render, just with different CSS classes. So `scripts/price_history.py` (Session B)
doesn't need to catch a catalog in the act of closing — it can:

1. Track known catalog ids + their `end_date` in `_pending.json` (populated cheaply
   either from each catalog's own page, or — better, since it's already fetched as
   structured JSON for many catalogs at once — from `?alf1=4&page=1`'s `auctionRows`).
2. Once `end_date` has passed, re-render the catalog page (paged with `?items=100`,
   confirmed honored above, to cover all lots — a 470-lot catalog needs 5 renders at
   `items=100` instead of 10 at the default 50) and parse `item-win-bid` /
   `item-status` per lot.
3. No second cron run "timed near close" is needed — the catalog page doesn't go
   away or change shape at close, it just flips from `item-currentbid`/empty-status
   to `item-win-bid`/`ended sold`.

The `?alf1=4` index is also a viable backstop/backfill path independent of
`_pending.json`: it can enumerate closed catalogs the harvester never even knew to
track (e.g. a catalog whose `auction_finder.py` run was skipped that day), going back
as far as page 17 (827 total auctions) without walking ids blind.

## Unsold lots disappear after close (survivorship bias, 2026-09-28)

The first production harvest (5 closed sales, 2,638 lots) came back **100%
`ended sold`, with zero unsold**. That's suspicious for a real auction.
Evidence that unsold lots are removed, not just absent:

- **Small scattered gaps in lot numbering**, always between vehicles. In
  catalog 911, lots 904, 908 and 910 are missing while 903/905/907/909 are
  present. Catalog 913 is missing 303, 306, etc.
- **Lot IDs are sequential with lot numbers** (903 = 509409, 905 = 509411),
  so the missing lot 904 must be ID 509410.
- **A control probe settled it:**
  `lot-details/index/catalog/911/lot/509409` (lot 903, present) loads fine
  **without** the title slug (57 KB, "2020 FORD F-150 - 4X4!", 27 bids),
  while `.../lot/509410` (the missing 904) returns **404 Not Found**. The
  URL format is valid, and the lot itself is gone.
- The index's `total_lots` (493 for catalog 914) exceeds the catalog's own
  visible count (470) by 23, consistent with removed lots.

**What this means:** closed catalogs keep only lots that sold. The history
file is sales-only, which is survivorship bias. Price statistics skew
high, and "nobody wanted this at $X" (a passed or reserve-not-met lot) is
invisible. The cluster between vehicles suggests reserve-not-met trucks,
but we can't tell unsold from withdrawn, since the page is simply gone.
**One confirmed lot so far**; treat it as strong evidence, not proof.

**The only way to recover them is to see them while they're alive.** A lot
that was observed live (in `auction_lots.yaml`) but never appears in its
closed catalog can be recorded as `price_kind: "vanished"` with its last
observed bid. That's a lower bound, never a close. It needs the live fetch
to cover whole catalogs near close, not just page 1. Not built: see
PRICE-DISCOVERY.md.

## Close-price history

`scripts/price_history.py` (Phase 1 of `PRICE-DISCOVERY.md`, the highest-priority
piece of the whole project) turns the findings above into a real, permanent,
append-only record — see its module docstring for the full rationale. Short
version:

- **Schema.** One compact JSON object per line in `research/price_history/YYYY-MM.jsonl`
  (grouped by the catalog's `catalog_closed_at` month), keys in this exact order:
  `platform, catalog_id, lot_id, lot_no, title, category, watchlist_matches
  (list, key omitted entirely when empty), price_kind ("close"|"unknown"), price
  (int cents-free dollars, or null), num_bids (int or null), catalog_closed_at
  (the catalog's own end_date, UTC ISO-8601 "…T…Z"), observed_at (UTC ISO now),
  status_raw (present ONLY when price_kind is "unknown")`. Deduped on
  `(platform, lot_id)` across every month file — a re-run never appends a
  duplicate. `research/price_history/_harvested.json` tracks which catalog ids are
  already fully recorded, `{"catalogs": {"914": {"end_date", "lots",
  "harvested_at"}}}`.
- **The `price_kind` honesty rule.** A row is `"close"` only when the lot's own
  status span is exactly `ended sold` AND a real `item-win-bid` was parsed.
  Anything else — a status class this parser hasn't matched before, a missing
  win-bid — becomes `price_kind: "unknown"`, `price: null`, and the raw status
  class+text goes in `status_raw`. **No real unsold/passed lot has ever been
  observed** across every real sample so far (this session's synthesized-fixture
  test aside), so `"unknown"` is currently the only fallback kind — never
  invent a price for it. A lot that's still genuinely live (an empty
  `item-status`, e.g. on an open catalog) isn't recorded as a row at all; it
  hasn't concluded yet.
- **Daily vs. backfill.** The daily GitHub Actions run (`auction-monitor.yml`,
  between "Fetch lots" and "Estimate value", `continue-on-error: true` so a
  harvest bug can never block the lots refresh) only harvests NEW closes: it
  reads the closed-catalogs index page 1 (page 2 too if every closed catalog on
  page 1 turns out to be new), and harvests up to 5 not-yet-recorded catalogs.
  No backfill runs in CI. A one-time full backfill runs locally: `python
  scripts/price_history.py --backfill` walks every index page, prints a size
  estimate (catalogs, total lots, estimated renders, estimated JSONL MB at a
  MEASURED bytes/row, estimated runtime) and exits — add `--yes` to actually
  run it, `--since YYYY-MM-DD` to limit it. The backfill is resumable: state
  saves after each catalog, so a Ctrl-C loses at most the catalog in progress.

## A second, separate concern: Terms of Service

This fetches public pages at a polite rate (one request every 2s, browser
`User-Agent`, no login, no CAPTCHA-solving) — the same posture as this repo's
existing `car_finder.py` against Craigslist/Cars.com. It's still worth a read
of Musick's ToS before leaning on this long-term. If they push back (blocks,
rate-limits, or their ToS turns out to explicitly bar automated access),
drop `"musick"` from `PLATFORMS` rather than working around the block.

**Update 2026-09-28: it happened.** See "Bot protection: Musick is behind AWS
WAF" below. Reading the ToS is now the first task of the next session.

## Bot protection: Musick is behind AWS WAF, and pushed back (2026-09-28)

Every Playwright render of `bid.musickauction.com` calls out to AWS WAF's
bot-protection service (`token.awswaf.com/.../inputs` and `.../mp_verify`,
visible in the XHR log). That had never been noticed or mattered before.

On 2026-09-28 at 18:00 UTC, after a heavy day of probing from GitHub's IPs
(about 10 `probe_url` runs, two full pipeline runs, plus agent probes), a
production run got **blocked partway through**:
- Catalogs 920, 921 and 916 rendered normally (50 lots each).
- 918, 919, 922 and 923 each returned a **212-byte page with no lots**.
  The old code logged that as "markup may have changed", which was wrong.
- The harvester then logged `0 catalog(s) attempted` in 1.5s. Its index
  render was very likely blocked too, but it didn't log what came back.
- `auction_lots.yaml` was **overwritten with the 48 lots that did load**, so
  4 sales silently disappeared from `/auctions/`.

The 212-byte page was never saved, so we don't know if it's a CAPTCHA, a
403, or a challenge. Treat the diagnosis as "blocked, very likely rate-based"
rather than verified markup.

**Policy, per the Terms of Service section above and PRICE-DISCOVERY.md's
non-negotiables: back off, never work around it.** No user-agent tricks, no
proxies, no challenge-solving. The fix (PR #141):
- `looks_blocked()` recognises a block (tiny page or challenge markers).
- A circuit breaker stops all Musick renders on the first block.
- The live lots file is **not rewritten** on a run that hit a block
  (yesterday's complete snapshot beats today's partial one).
- The harvester logs what its index page returned, stops on a block, and
  runs slower (5s between renders, at most 3 catalogs a day).

**Consequence for the backfill:** WAF rate limits are per IP. Thousands of
renders from the owner's home connection could get **that IP blocked from
the site the owner and grandpa actually bid on.** The bulk backfill is on
hold until Musick's ToS has been read and a very slow, resumable schedule
exists (see PRICE-DISCOVERY.md's handoff block).

## eBay from CI: blocked (Session C verdict, 2026-09-28)

The same run was the first to use the normalized search queries (PR #135)
against eBay from GitHub Actions. Of 46 lookups, about 25 returned
**`403 BLOCKED`**. The rest returned **~13.6 KB pages that parse to "0
prices found"**. Real eBay results pages are far larger, so these are almost
certainly its bot-challenge page. That page isn't saved, so it's
unconfirmed. Conclusion: **eBay sold-comps can't work from GitHub's
datacenter IPs.** That's the datacenter-IP block predicted in Decision 8,
and it can't be fixed by changing the parser. PR #141 stops lookups after
the first 403 instead of burning ~46 × 2s on a wall. What's left of
Session C is one local comparison from a residential IP, for the record
only, since the pipeline runs on CI.

## Platforms

| Platform | Status | Why it's here | Search strategy |
|---|---|---|---|
| **MusickAuction.com** | **Active, verified** | Nampa/Meridian, ID auction house running the actual in-person sales Grandpa already attends. | See "Musick, verified against real markup" above. |
| **PublicSurplus.com** | Disabled, unverified | Most Idaho city/county/PD auctions run through this — including Boise PD, Ada County, Meridian. | Keyword search per agency name, `s=id` (state filter). |
| **GovDeals.com** | Disabled, unverified | Larger municipal/county surplus; some ID agencies list here instead of PublicSurplus. | Keyword search, `locState=ID`. |
| **Municibid.com** | Disabled, unverified | Zip-radius search around Boise (83702) catches smaller cities a keyword search on agency name would miss. | `zipcode=83702`, 60mi radius, plus keyword. |
| **PropertyRoom.com** | Disabled, unverified | Police/sheriff evidence and seized-property auctions specifically. | Keyword search per agency name. |

"Disabled" means the code is intact but not in the `PLATFORMS` tuple — these
were built as a wider net beyond Grandpa's usual rounds, but the current
focus is Musick. `AGENCY_TERMS` in `auction_finder.py` (Boise PD, Ada
County, Meridian, Nampa, Canyon County, Idaho State Police, Caldwell,
Garden City, Eagle) only matters for those four, not Musick.

## Category split — Vehicles, Grandpa's Shop, and everything else

Jeremy's grandpa specifically wants two things: cars/trucks, and small engines
& appliances — he fixes those, mostly vacuums. Everything else is the "casual
bidder overlooks this" net. So every lot gets keyword-classified into a broad
category (`CATEGORY_KEYWORDS` / `guess_category()` in `auction_finder.py`):
**Small Engines & Appliances**, Heavy Equipment, **Vehicles**, Firearms,
Electronics, Jewelry & Valuables, Tools & Equipment, Bikes & Recreation,
Office & Furniture, Other. This runs locally on title/description text — no
API call, works even without `ANTHROPIC_API_KEY`.

- `/auctions/` renders **Vehicles** as its own section up top, then groups
  everything else (including Small Engines & Appliances) by category below it.
- `/grandpas-shop/` is a separate, dedicated page — just the Small Engines &
  Appliances category, nothing else, meant to be bookmarked/shared directly.

Small Engines & Appliances is listed **first** in `CATEGORY_KEYWORDS` on
purpose: mower/chainsaw/generator/etc. live only there, not in Heavy Equipment
or Tools & Equipment, so a "Toro push mower" or "Honda generator" doesn't get
siphoned off into a different bucket before grandpa's page ever sees it.
Classification is still keyword-based and will misfile the occasional lot (a
brand name like "Ford" only appears in the Vehicles list, so a hypothetical
"Ford generator" is caught correctly by Small Engines & Appliances first —
but tune the keyword lists as real mis-classifications turn up). It doesn't
need to be perfect, just good enough that neither Vehicles nor Small Engines &
Appliances misses the real thing or fills up with junk from the other bucket.

## The personal watchlist — "dial in the search"

`data/auction_watchlist.yaml` is Jeremy's cross-cutting personal-interest
list — trucks & off-road/4x4, a commuter car for his sister, old project
cars, cheap motorcycles, nice jetskis, little campers, a lightweight
backcountry pistol, a bird shotgun, a deer rifle, yellow gold/fossil/
meteorite jewelry, fly fishing gear, mining equipment — layered **on top
of** category (`guess_category()`), not a replacement for it. A lot can
match zero, one, or several groups regardless of category: a "2017 Jeep
Wrangler 4x4" is `category: Vehicles` **and** `watchlist_matches:
["Trucks & Off-Road/4x4"]`; a "Glock 43 9mm" is `category: Firearms`
**and** `watchlist_matches: ["Backcountry Pistol"]`.

Matched by `match_watchlist()` in `auction_finder.py`, same word-boundary
convention as `guess_category()`, with one addition: a keyword starting or
ending in punctuation (a caliber like `.308`) needs `(?<!\w)`/`(?!\w)`
instead of a plain `\b` on that side — `\b` only fires between a word
character and a non-word character, so two non-word characters in a row
(a space next to a literal `.`) never form a boundary and `\b\.308\b`
silently matches **nothing**, not even a real `.308` in a listing. This
was CONFIRMED actually happening during development - every caliber
keyword matched zero real listings until fixed.

Editing `data/auction_watchlist.yaml` needs no code change - it's read
fresh on every run. Three real false positives turned up testing against
live data and are worth knowing about before adding more keywords:
- A bare `truck` matched a truck **toolbox** listing, not a truck -
  narrowed to `pickup` plus specific models.
- Bare `tundra`/`sierra`/`colorado`/`ram` risked colliding with a YETI
  Tundra cooler, Sierra-brand ammo (a real risk on a gun-heavy auction
  site), the state of Colorado, and computer RAM respectively - narrowed
  to the actual model phrase (`toyota tundra`, `gmc sierra`, etc.).
- Bare `308`/`30-06`/`30-30` (before the punctuation-boundary fix above)
  would have matched a **lot number** (`Lot #308: ...`) once the boundary
  bug was fixed and plain `\b` started working on the digits-only form -
  the leading period is required specifically to rule that out.

**Testing keywords before shipping them (2026-09-28).** Every false positive
above was found after it shipped. Now `scripts/watchlist_test.py` tests
draft keywords against every real title in `research/price_history/` plus
the live snapshot (2,384 unique titles at the time of writing), using the
exact live matcher, and shows what a change ADDS and DROPS. Groups can also
carry an `exclude:` list that vetoes a match, for collisions a keyword
can't dodge on its own. `/refine-search` wraps the whole loop, and
`data/search_profiles/` keeps the reasoning behind each group.
`scripts/tests/test_watchlist.py` holds collision *guard rules*: any group
using bare "hellcat", "g29" or "pistol" must exclude the real collisions.
It never pins exact keywords, because it runs in the daily bot's
pre-commit gate and must never block the owner's own edits.

First run of the tester found:
- The old bare `pistol / revolver / handgun` group matched 21 titles, 5 of
  them junk (a sprayer's "Pistol Grip Wand", mixed ammo lots, reloading
  bullets, a "Pistol belt" bundled with a DVD player). It's now split
  into `pistol_backcountry` (the owner's exact targets) and
  `handguns_other` (the broad net, junk excluded, all 16 real handguns
  kept).
- **"Gold/Fossil/Meteorite Jewelry" matches 0 of 2,384 real titles**, even
  though these sales included 118 jewelry lots. That's the next group to
  put through `/refine-search`.

Rendered as: a dedicated "🎯 On your watchlist" section on `/auctions/`
(above the Vehicles section, all matches regardless of category), plus a
small 🎯-prefixed chip on any lot row wherever it appears, anywhere on the
site.

### The watchlist is now the keep bar, not just a highlight

Originally this project's whole point was "flag any objectively good deal
anywhere" - a broad net over everything. As the watchlist above came
together, the ask changed explicitly: **drop what doesn't match, as early
as possible, so this can scale to more sources without scaling the noise
along with it.** So `main()` in `auction_finder.py` now keeps a lot only
if it's `category: Small Engines & Appliances` (grandpa's original core
interest - always kept, watchlist or not) **or** `watchlist_matches` is
non-empty. Everything else is dropped before it's ever written to
`data/auction_lots.yaml` or rendered - not filtered out visually, gone
from the file entirely. Confirmed against the real live 301-lot dataset:
91 survive.

The same rule gates the expensive step, not just the final output:
`fetch_musick_catalog()` now only fetches a Vehicles-category lot's
detail page (VIN/mileage/title - see below) when that lot **already**
matches the watchlist on title alone. Confirmed: 47 of 114 real vehicles
this run, cutting the single most expensive part of the whole pipeline
(a second Playwright render per lot) by over half. This is the actual
lever for adding more sources (PublicSurplus, GovDeals, Municibid,
PropertyRoom are built but disabled - see Platforms below) without the
per-run cost and page size scaling with the number of sites fetched: the
watchlist bounds it, not the source count.

**Trade-off, stated plainly:** this means a genuinely great deal sitting
in a category nobody's watching for (some $5 lot secretly worth $200,
outside every current keyword group) will never be seen or scored -
gone before `auction_value.py` even runs. That's the deliberate cost of
"no room for mid." If a category should always get a look regardless of
the watchlist, add it as an `ALWAYS_KEEP_CATEGORY`-style exception the
way Small Engines & Appliances already is, or add keywords broad enough
to catch it.

**Parked for later** (explicitly deferred, not built): a way to sample a
couple of lots from categories *outside* the active watchlist each run -
a small "discovery" pick so something interesting outside the current
search terms doesn't stay permanently invisible. Needs actual design
(how many, how picked, where shown) before building.

## Vehicle detail enrichment — VIN, mileage, title status

The catalog LISTING page (parsed above) never carries this — just title, bid,
thumbnail. Real vehicle specs sit on a completely separate page: each lot's
own **lot-DETAIL page** (`.../lot-details/index/catalog/{auctionId}/lot/{lotId}/...`
— the exact URL already saved as the lot's `url` field, no new URL construction
needed). CONFIRMED via a live `probe_url` debug run against a real listing
(a 2017 Jeep Wrangler): the detail page has a clean, consistent
`<span class="cat-header">Label:</span> value<br>` block with **year, make,
model, mileage, color, VIN, engine, cylinders, transmission, drivetrain,
body, and title status** — everything `auction_value.py`'s vehicle-caveat
prompt already says a bidder has to go find for themselves.

`fetch_musick_vehicle_detail()` in `auction_finder.py` fetches this page (a
**second** Playwright render, separate from the one catalog-page render per
auction) for every lot `guess_category()` classifies as **Vehicles** — only
that category, to keep the extra render cost scoped to where it matters.
Adds these fields to the lot: `vin`, `mileage`, `title_status`, `year`,
`make`, `model`, `color`, `engine`, `cylinders`, `transmission`,
`drivetrain`, `body`, `auction_ends_at` (an absolute ISO timestamp computed
from the page's own relative "9d 20h 36m 50s"-style countdown, read at the
moment that specific lot's detail page was actually fetched), `clean_title`
(bool), `miles_per_year` (mileage ÷ vehicle age, for ranking "unusually low
miles for the year" higher), and `car_candidate` — **true only when mileage
is under 150,000 AND `title_status` is "Clear"/"Clean"**, both required. A
lot with no mileage on file, or any title status other than clean (Salvage,
Rebuilt, Bill of Sale, or simply missing) is NOT a candidate — unknown stays
unknown rather than assuming the best case, same rule as every other
estimate in this file. Non-vehicle lots never get these fields at all (no
render, no keys) rather than nulls.

**Cost tradeoff, gone in eyes open:** this roughly doubles Musick's render
work — from ~7 catalog-page loads per run to ~7 + one per vehicle lot found
(over 100 on a run with several vehicle-heavy auctions live at once). Worth
it for what it unlocks (real Carfax-style facts instead of "check the
listing yourself"), but it's the reason vehicles specifically, not every
category, get the second render.

**What this does NOT give you: an actual accident-history report.** A real
Carfax/AutoCheck pull is a paid, per-VIN service — there's no free API for
it, so this pipeline can't fetch one automatically any more than it can
call a paid valuation API without a key. What it *does* give you for free:
a clean title-status flag straight from the listing itself, and a VIN
worth pasting into NHTSA's free vPIC decoder or a Carfax/AutoCheck lookup
by hand for anything that clears the mileage+title filter — a much shorter
list to spend real money checking than all 100+ vehicles at once.

**Vehicles still have no automated target price.** eBay comps
(`auction_value.py`) don't carry real sold data for used cars, so
`estimated_value_mid` stays null for Vehicles even after PR #128's
eBay-independent-of-key fix — that gap isn't something more scraping closes
by itself, and the owner doesn't want an `ANTHROPIC_API_KEY` secret added to
close it via the Claude fallback either. Open question, not yet built: some
way to get a recurring target-price judgment onto `car_candidate` lots
without a paid key — the leading idea is a scheduled Claude Code session
(a Routine) doing that reasoning directly and publishing the result,
instead of a raw API call.

## Geo filter

A lot is kept only if its agency/title/description/url mentions a recognized
Treasure Valley name (`NEAR` in `auction_finder.py`) — Boise, Meridian, Eagle,
Nampa, Caldwell, Garden City, Kuna, Star, Middleton, Emmett, Mountain Home, Ada
County, Canyon County, or "Idaho" generally. Unlike `car_finder.py`'s Craigslist
search (which defaults to *keep* on unknown location), this defaults to *drop* —
these auction searches aren't reliably geo-scoped the way a Craigslist regional
subdomain is, so an unrecognized row is more likely noise than a real Boise-area
lot.

**Musick is exempt** from this filter (`in_region()` short-circuits to `True`
for `platform == "musick"`) — it's a single Nampa, ID auction house, so
everything on its site is already local by construction, and its listings
won't reliably repeat a city name in the title the way a national platform's
would.

## Value estimation — real eBay comps first, AI text guess as fallback

Jeremy asked, in essence, "is there a good way to value lots — eBay
transactions?" Yes, and it's the primary source now, not just a Claude guess:

1. **`scripts/ebay_comps.py`** looks up each lot's title against eBay's
   **SOLD + completed listings** search (`LH_Sold=1&LH_Complete=1`) — real
   transaction prices, not asking prices. eBay retired its free completed-items
   API years ago (the replacement, Marketplace Insights, is partner-gated), so
   this works the same way every other source in this file does: fetch the
   public search page, parse it (JSON-LD first, a markup-specific regex
   fallback second), same resilience pattern (cache the last good result,
   never crash, log a note).
2. **`auction_value.py`** still sends each lot's title/category/description to
   Claude Haiku (batches of 12) — but now also includes the eBay comp stats
   when found, and instructs Claude to treat them as the primary anchor and
   use its note to explain how *this specific lot's* condition/completeness
   should move a buyer within that range (e.g. "described as non-functional,
   price toward the bottom of the $40–90 eBay range").
3. **Whichever number actually gets used, though, is decided in Python, not by
   Claude:** when a lot has **`EBAY_MIN_COMPS` (3) or more** real sold comps,
   `estimated_value_low/high/mid` come directly from those comps (`mid` is the
   observed *median* sale price, not a synthetic midpoint of the low/high
   band — those aren't the same number for a skewed price distribution, and
   an earlier version of this code got that wrong before a test caught it).
   `value_source` is recorded as `"ebay"`. Claude's own low/high is simply not
   used in that case — only its note is kept, for context. When there aren't
   enough comps (or eBay is unreachable), it falls back to Claude's own
   estimate as before, with `value_source: "ai"`. Every lot also carries
   `ebay_n` / `ebay_median` regardless of which source won, so the page can
   show "found N comps, didn't use them" transparently.

`deal_score` is `estimated_value_mid − current_bid` either way; a lot is
`flagged` when that gap is ≥30% of the estimated value and the estimate is at
least $20 (to skip noise on trivially cheap lots). **The lot tables sort
eBay-backed estimates above AI-only ones** (each group still ranked by
deal_score within itself) — a real comp beats a bigger *nominal* gap from a
pure guess, which is the actual point of "objectively best deals": a lot
flagged off 5 real sales is more trustworthy than one flagged off Claude's
read of a title alone, even if the second one's dollar gap looks bigger on
paper. The page marks each estimate with **"✓ N sold"** (eBay-backed, green)
or **"AI est."** (text-only, dimmer) so that distinction is visible, not just
baked into the sort order.

**A third gate on `flagged`, beyond the 30%/$20 thresholds: the lot has to be
"matured"** — `_lot_is_matured()` in `auction_value.py` requires either 3+
real bids, or being within 24h of `auction_ends_at`. A lot that just opened
at its floor price with 0 bids and 9 days left isn't a deal yet, no matter
how big the nominal gap against its estimate looks — it hasn't had any real
chance to be bid up, and normally will be well before it closes. This is
explicitly about **noise**, not accuracy: `deal_score`/`deal_pct` still show
the real numeric gap either way (so an unmatured lot with a huge gap still
sorts near the top and is visible to browse), only the "🔥 Deal" badge and
the email digest require maturity. The client-side deal-threshold slider
(`auction-dial-in.html`'s `isMatured()`) mirrors this exactly, reading
`data-num-bids` / `data-ends-at` off each row, so dragging the slider can't
un-gate an unmatured lot the Python side already excluded.

Requires an `ANTHROPIC_API_KEY` repo secret (Settings → Secrets and variables →
Actions) for the AI-fallback half; the eBay-comps half needs no key or secret
at all, just network access. Without `ANTHROPIC_API_KEY`, lots with 3+ eBay
comps are still valued (comps-only, no note); everything else keeps null
estimates and renders with just current bid, close time, and link.

**That was the intent from day one, but the code didn't actually do it** —
`main()` bailed out entirely the moment `ANTHROPIC_API_KEY` was missing,
before `estimate()` (and therefore the eBay-comps lookup) ever ran. Since
the repo has never had that secret set, every scheduled run through the
first real per-lot data (see "Musick, verified against real markup" above)
silently valued nothing at all - not because eBay comps didn't help, but
because they were never even tried. Fixed: the API-key check now only
gates the Claude fallback call itself, inside `estimate()`'s per-batch
loop, so a missing key no longer blocks the free half too - confirmed
against the case that was actually broken (mocked eBay comps, no key set:
the comp-covered lot gets priced and flagged, the one without comps stays
null exactly as before).

**Neither source is an appraisal.** eBay comps are for "a similar item," not
necessarily this exact lot's condition — that's what Claude's note is for.
Treat a flagged lot as "worth a second look," not "safe to bid against sight
unseen." Same live-markup caveat as the rest of this file applies to eBay too:
this dev sandbox's network policy blocks ebay.com, so `ebay_comps.py` hasn't
run against a real eBay page yet — same debugging path as everything else
(dispatch the workflow, read the fetch notes, adjust the regex if `0 prices
found` shows up).

## Dialing in the search — live threshold slider + email digest

Both `/auctions/` and `/grandpas-shop/` have a control panel (rendered by
`layouts/partials/auction-dial-in.html`) right under the summary stats:

- **A "Deal threshold" slider (5%–60%, default 30%)** — purely client-side. It
  re-reads the `data-deal-pct` / `data-est-mid` attributes `auction-lot-table.html`
  already puts on every row and recomputes which rows are flagged, live, with no
  page reload and no rebuild. This is deliberately *not* baked into a fixed
  backend setting — Jeremy and his grandpa can each try different thresholds in
  their own browser to see what turns up more or fewer lots before agreeing on
  where to leave it.
- **An "Email this digest" link** — builds a `mailto:` link (recipients from
  `data/auction_contacts.yaml`, subject + a plain-text list of whatever's
  currently flagged at the slider's threshold, capped at the top 15 by gap
  size) and keeps its `href` live-synced as the slider moves. Clicking it opens
  the visitor's own mail app with everything pre-filled — **nothing is sent
  automatically**, no SMTP credentials or API keys are stored anywhere. Jeremy
  reviews and hits send himself, to himself and his grandpa both.

To include grandpa in the digest, set `grandpa_email` in
`data/auction_contacts.yaml` (currently blank — the page shows a note
reminding you it's blank, and the "To" field just addresses Jeremy alone
until it's filled in).

**A gotcha that bit this exact feature during development**, worth knowing if
you touch this partial: `auction-dial-in.html` is invoked from inside a
`{{ with $L }}` block in both page templates, which rebinds `.` to the lots
data — so `.Permalink` inside that block silently resolves to `nil`, not the
page. Use `$.Permalink` (root context) instead. A real-browser test (Playwright)
caught this as `pageURL` literally rendering as the string `"null"` in the
built email body.

Second gotcha, also only caught by testing against real rendered output: piping
a value through `| jsonify` inside a `<script>` block and *not* following it
with `| safeJS` causes Hugo's `html/template` contextual auto-escaper to
JSON-encode the already-quoted output a second time — the literal characters
`"..."` end up embedded inside the JS string itself. This silently turned an
*empty* `grandpa_email` into the two-character string `""`, which is
non-empty and therefore `truthy` in JS, so a blank recipient slipped into the
"To" field even though `.filter(Boolean)` was supposed to drop it. Always
pipe `| jsonify | safeJS` together when assigning a Hugo value to a JS
variable inside `<script>`.

## Running it manually

```bash
python scripts/auction_finder.py             # fetch, filter, write data/auction_lots.yaml
python scripts/auction_finder.py --dry-run    # fetch + print notes, don't write

ANTHROPIC_API_KEY=sk-... python scripts/auction_value.py           # fill in estimates
ANTHROPIC_API_KEY=sk-... python scripts/auction_value.py --dry-run  # preview, don't write
ANTHROPIC_API_KEY=sk-... python scripts/auction_value.py --all      # re-estimate every lot

python scripts/ebay_comps.py "Kirby G6 vacuum"   # test the eBay comp lookup on its own

# needs: pip install playwright && playwright install chromium
python scripts/musick_render.py "https://bid.musickauction.com/auctions/catalog/id/915"
```

Then `hugo --minify` to confirm the page builds, or `hugo server` to look at
`/auctions/` locally.

## Probing live markup: local first, CI to confirm

Workflow for anything new (a lot-detail page, a different auction site, a
field that might not be on the catalog page): run `scripts/probe.py` on your
own machine, read what lands in `.debug/`, write the parser against that
real markup, dry-run it, then ship.

Local is the default now because it's faster (no workflow-dispatch round
trip, no waiting on a GitHub-hosted runner), it lets you probe several URLs
in one sitting instead of one per dispatch, and the raw dumps - which can
carry other bidders' handles - stay in a gitignored folder on your own disk
instead of landing on a public `debug/auction-html` branch. That branch was
only ever a workaround for a dev-sandbox network policy that blocked the
auction sites outright; probing from a normal residential connection has no
such problem.

The caveat: local success isn't production success. The daily pipeline runs
on GitHub Actions' own IPs, which are datacenter IPs, not residential ones -
and eBay in particular is believed to 403 datacenter traffic while allowing
residential. So before shipping a parser built against a local probe, do one
`probe_url` workflow-dispatch run to confirm it still works from CI. This
matters most for eBay comps; Musick's own pages have been less finicky about
it so far, but check anyway.

```bash
pip install playwright && playwright install chromium

# a closed catalog, to see what that markup looks like
python scripts/probe.py "https://bid.musickauction.com/auctions/catalog/id/914"

# several URLs in one run, written to a custom folder
python scripts/probe.py URL1 URL2 URL3 --out .debug/2026-09-28

# read the dump
ls .debug/ && cat .debug/probe.log
```
