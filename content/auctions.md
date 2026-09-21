---
title: "Auction Watch"
type: "auctions"
layout: "single"
description: "Monitoring Boise-metro government and police surplus auctions — currently Musick Auction Co. — and flagging lots where the current bid is well under what the thing would actually resell for."
tabTitle: "🔨 AUCTION WATCH"
---

Grandpa already runs the Meridian-area circuit in person via **Musick Auction
Co.** (Nampa/Meridian, ID) — this watches that same source and does the boring
part, reading every sale's fine print, automatically. Musick posts upcoming
*auction events* (not individual lots) on its own site — real dates, locations,
and category-rich titles ("TRUCKS, CARS, GUNS, AMMO..."), each linking out to
a separate bidding subdomain for the actual line items. (Four more platforms —
PublicSurplus, GovDeals, Municibid, PropertyRoom — are built but currently
switched off; see `docs/AUCTION-MONITORING.md` if that net needs widening
again later.)

The page below is split in two: **Vehicles** first — every car, truck, or
motorcycle lot found, across every platform and agency, for Grandpa to check —
then **everything else, grouped by category**. That second half is the actual
point of automating this: tools, electronics, jewelry, unclaimed property, the
stuff a casual bidder scrolls past because it's buried on page 6 of a listing
site. Those are exactly the lots most likely to be overlooked and undervalued.

Grandpa also fixes small engines and appliances — mostly vacuums — so that
category gets its own dedicated feed too: **[Grandpa's Shop](/grandpas-shop/)**.

Everything below re-derives from `scripts/auction_finder.py` (pulls lots) and
`scripts/auction_value.py` (estimates resale value with Claude and scores the gap
against the current bid). See `docs/AUCTION-MONITORING.md` for how it's wired up,
what it's watching, and its known rough edges.
