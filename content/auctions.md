---
title: "Auction Watch"
type: "auctions"
layout: "single"
description: "Monitoring Boise-metro government and police surplus auctions — PublicSurplus, GovDeals, Municibid, PropertyRoom — and flagging lots where the current bid is well under what the thing would actually resell for."
tabTitle: "🔨 AUCTION WATCH"
---

Boise-metro police and government surplus auctions run deep — the Boise PD auction
alone regularly has dozens of lots, and that's before Ada County, Canyon County,
Meridian, and Nampa get counted. Grandpa already runs the Meridian-area circuit in
person; this casts a wider net across the Treasure Valley and does the boring part —
reading every lot's fine print — automatically.

Everything below re-derives from `scripts/auction_finder.py` (pulls lots) and
`scripts/auction_value.py` (estimates resale value with Claude and scores the gap
against the current bid). See `docs/AUCTION-MONITORING.md` for how it's wired up,
what it's watching, and its known rough edges.
