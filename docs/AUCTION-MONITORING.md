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

## A second, separate concern: Terms of Service

This fetches public pages at a polite rate (one request every 2s, browser
`User-Agent`, no login, no CAPTCHA-solving) — the same posture as this repo's
existing `car_finder.py` against Craigslist/Cars.com. It's still worth a read
of Musick's ToS before leaning on this long-term. If they push back (blocks,
rate-limits, or their ToS turns out to explicitly bar automated access),
drop `"musick"` from `PLATFORMS` rather than working around the block.

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

Requires an `ANTHROPIC_API_KEY` repo secret (Settings → Secrets and variables →
Actions) for the AI-fallback half; the eBay-comps half needs no key or secret
at all, just network access. Without `ANTHROPIC_API_KEY`, lots with 3+ eBay
comps are still valued (comps-only, no note); everything else keeps null
estimates and renders with just current bid, close time, and link.

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
