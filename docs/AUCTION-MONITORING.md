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

The Boise PD auction alone runs dozens of lots at a time; Ada County, Canyon County,
Meridian, and Nampa each run their own on top of that. Reading every listing's fine
print by hand across five sites, every few days, doesn't scale. This automates the
boring part — pull everything, filter to the Treasure Valley, ask Claude what each
lot would actually resell for, and surface the gap.

Grandpa already runs the Meridian-area circuit in person and knows that turf well.
This casts a wider net on purpose — Boise PD, Ada County, and Canyon County lots
that aren't on anyone's regular rounds — rather than duplicating it.

## ⚠️ Known limitation: unverified against live markup

This was built in a sandboxed dev session whose network egress policy blocks
`publicsurplus.com`, `govdeals.com`, `municibid.com`, `propertyroom.com`, and
`musickauction.com` outright (confirmed via the proxy status endpoint, not
guessed). **None of the fetch/parse code in `auction_finder.py` has run
against real HTML from these sites.** The search URLs and the reliance on
embedded JSON-LD are informed guesses based on how these platforms and
similar auction sites are generally built, not verified endpoints.

`musickauction.com` carries an extra layer of uncertainty on top of that:
it's a **guessed domain**, not just an unverified one. "Musick" + a Boise
police-auction context strongly suggests **Musick Auction Co.**, a
Nampa-based Idaho auction house that runs a lot of the actual in-person
Treasure Valley law-enforcement sales — but that inference hasn't been
confirmed against the real site. If `musickauction.com` turns out to be
wrong (or dead), fix `MUSICK_BASE` in `auction_finder.py` to the real URL.

Treat the first real run as a debugging session, the same way `car_finder.py`
needed a few passes to nail down Craigslist's markup and Cars.com's Akamai
block:

1. Run the `Auction Watch — refresh lots` workflow manually (Actions tab →
   `workflow_dispatch`) — a GitHub-hosted runner has open internet, unlike this
   dev sandbox.
2. Read the **Fetch lots** step's log. Each `(platform, agency term)` pair prints
   a note: how many rows came back, or why none did (`403 BLOCKED`, `empty`, or
   `no json-ld found`).
3. For any platform reporting `0 rows` across the board, view one of its search
   pages by hand in a browser, check whether it has `<script
   type="application/ld+json">` blocks at all, and if not, add a
   platform-specific regex parser (see `PLATFORM_FALLBACK` comment stub in
   `auction_finder.py` — follow the shape of `car_finder.py`'s `carscom_parse`
   for the pattern: read the real markup, write a targeted parser, cache
   successful runs as a fallback for when the site blocks the next request).

Until that pass happens, `/auctions/` will most likely show "no lots tracked
yet" or a thin result. That's expected, not broken.

## A second, separate concern: Terms of Service

This fetches public search-result pages at a polite rate (one request every 2s,
browser `User-Agent`, no login, no CAPTCHA-solving) — the same posture as this
repo's existing `car_finder.py` against Craigslist/Cars.com. It's still worth a
read of each site's ToS before leaning on this long-term. If a platform pushes
back (blocks, rate-limits, or its ToS turns out to explicitly bar automated
access), drop it from `PLATFORMS` in `auction_finder.py` rather than working
around the block.

## Platforms

| Platform | Why it's here | Search strategy |
|---|---|---|
| **PublicSurplus.com** | Most Idaho city/county/PD auctions run through this — including Boise PD, Ada County, Meridian. | Keyword search per agency name, `s=id` (state filter). |
| **GovDeals.com** | Larger municipal/county surplus; some ID agencies list here instead of PublicSurplus. | Keyword search, `locState=ID`. |
| **Municibid.com** | Zip-radius search around Boise (83702) catches smaller cities a keyword search on agency name would miss. | `zipcode=83702`, 60mi radius, plus keyword. |
| **PropertyRoom.com** | Police/sheriff evidence and seized-property auctions specifically. | Keyword search per agency name. |
| **MusickAuction.com** *(domain guessed)* | Nampa-based Idaho auction house running actual in-person Treasure Valley law-enforcement/government sales — the circuit Grandpa already runs. | Single local auctioneer, not a national keyword-search platform — scans a handful of likely listing pages (`/`, `/auctions`, `/current-auctions`, ...) instead of searching per agency. Exempt from the geo filter (see below) since being on their site at all is the local signal. |

Agencies searched (`AGENCY_TERMS` in `auction_finder.py`): Boise PD, City of Boise,
Ada County, City/PD of Meridian, Canyon County, City/PD of Nampa, Idaho State
Police, City of Caldwell, Garden City, City of Eagle. Add more there as they come
up — e.g. Kuna, Star, Emmett, Middleton, or a specific school district or fire
district that runs its own surplus sales.

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

## Value estimation

`auction_value.py` sends each lot's title/category/description (no photos yet) to
Claude Haiku in batches of 12, asking for a conservative resale-range estimate and
a one-line note — explicitly told to flag "as-is", "evidence", "salvage", etc. in
the note, and to return `null` rather than guess when there isn't enough
information. `deal_score` is `estimated_value_mid − current_bid`; a lot is
`flagged` when that gap is ≥30% of the estimated value and the estimate is at
least $20 (to skip noise on trivially cheap lots).

Requires an `ANTHROPIC_API_KEY` repo secret (Settings → Secrets and variables →
Actions). Without it, `auction_value.py` no-ops and lots render with just their
current bid, close time, and link — no ranking, no flag.

**This is a text-only estimate, not an appraisal.** It doesn't look at photos, the
item's actual condition, or completeness. Treat a flagged lot as "worth a second
look," not "safe to bid against sight unseen." A future pass could feed the lot's
photo(s) to a vision-capable Claude call for a better estimate — not built yet.

## Running it manually

```bash
python scripts/auction_finder.py             # fetch, filter, write data/auction_lots.yaml
python scripts/auction_finder.py --dry-run    # fetch + print notes, don't write

ANTHROPIC_API_KEY=sk-... python scripts/auction_value.py           # fill in estimates
ANTHROPIC_API_KEY=sk-... python scripts/auction_value.py --dry-run  # preview, don't write
ANTHROPIC_API_KEY=sk-... python scripts/auction_value.py --all      # re-estimate every lot
```

Then `hugo --minify` to confirm the page builds, or `hugo server` to look at
`/auctions/` locally.
