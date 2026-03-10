# Markets — Project Spec

A Hugo page at `/markets` that displays live economic and market data from public APIs.
The goal is a clean, readable dashboard for tracking macro conditions: Fed policy,
inflation, labor, housing, credit, and equity markets.

**Status:** Spec only — no code written yet.

---

## North Star

> A single-page macro dashboard. No sign-up, no paywall, no broker account needed.
> Pull from trusted public sources. Refresh on page load. Tell a story with the numbers.

---

## Data Sources

### 1. FRED (Federal Reserve Bank of St. Louis)
**Base URL:** `https://api.stlouisfed.org/fred/series/observations`
**Auth:** Free API key, register at fred.stlouisfed.org
**Docs:** https://fred.stlouisfed.org/docs/api/fred/

The core source. Every series below has a FRED series ID.

| Category | Name | FRED Series ID | Notes |
|---|---|---|---|
| **Inflation** | PCE Price Index | `PCEPI` | Fed's preferred inflation gauge |
| **Inflation** | Core PCE (ex food & energy) | `PCEPILFE` | The one the Fed actually watches |
| **Inflation** | CPI All Items | `CPIAUCSL` | Headline CPI, monthly |
| **Inflation** | Core CPI | `CPILFESL` | CPI ex food & energy |
| **Fed Policy** | Effective Federal Funds Rate | `FEDFUNDS` | Actual overnight rate |
| **Fed Policy** | Fed Balance Sheet (Total Assets) | `WALCL` | Millions of $, weekly |
| **Fed Policy** | M2 Money Supply | `M2SL` | Seasonally adjusted |
| **Labor** | Unemployment Rate | `UNRATE` | U-3, headline number |
| **Labor** | Nonfarm Payrolls | `PAYEMS` | Monthly job adds (thousands) |
| **Labor** | Labor Force Participation Rate | `CIVPART` | Prime-age cohort tells deeper story |
| **Labor** | Initial Jobless Claims | `ICSA` | Weekly, leading indicator |
| **Labor** | JOLTS Job Openings | `JTSJOL` | Demand side of labor market |
| **Housing** | 30-Year Fixed Mortgage Rate | `MORTGAGE30US` | Weekly, Freddie Mac survey |
| **Housing** | 15-Year Fixed Mortgage Rate | `MORTGAGE15US` | |
| **Housing** | Housing Starts | `HOUST` | New residential construction |
| **Housing** | Existing Home Sales | `EXHOSLUSM495S` | Monthly |
| **Credit** | 10-Year Treasury Yield | `DGS10` | Risk-free benchmark |
| **Credit** | 2-Year Treasury Yield | `DGS2` | Most sensitive to Fed rate |
| **Credit** | 10Y-2Y Yield Spread (Yield Curve) | `T10Y2Y` | Recession signal when negative |
| **Credit** | BBB Corporate Spread | `BAMLC0A4CBBB` | Investment grade credit stress |
| **Credit** | High Yield Spread | `BAMLH0A0HYM2` | Risk appetite gauge |
| **Output** | Real GDP | `GDPC1` | Quarterly, seasonally adjusted |
| **Output** | Industrial Production Index | `INDPRO` | Monthly activity |
| **Consumer** | Retail Sales | `RSXFS` | ex autos, monthly |
| **Consumer** | Consumer Sentiment (U of M) | `UMCSENT` | Soft data, leads hard data |

---

### 2. U.S. Treasury (treasury.gov / fiscaldata.treasury.gov)
**Free, no key required**
**Docs:** https://fiscaldata.treasury.gov/api-documentation/

| Data | What It Shows |
|---|---|
| Debt to the Penny | Real-time total US national debt |
| Average Interest Rate on Debt | Cost of carrying the debt |
| Treasury Auction Results | What the market demanded at auction |

Use the Fiscal Data API: `https://api.fiscaldata.treasury.gov/services/api/v1/`

---

### 3. Bureau of Labor Statistics (BLS)
**Free, public API — key optional but increases rate limit**
**Docs:** https://www.bls.gov/developers/

Overlaps with FRED (which often re-publishes BLS data). Prefer FRED for consistency,
but BLS is the authoritative source for releases. Useful for:
- Pulling the latest CPI release detail (all sub-components)
- Producer Price Index (PPI) — upstream inflation pressure
- Employment Cost Index (ECI) — wage inflation

---

### 4. CME FedWatch (market-implied probabilities)
**No official public API — scrape the published table or use a proxy**
**URL:** https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html

Shows the market's current probability distribution for Fed rate changes at
upcoming FOMC meetings. This is one of the most forward-looking data points
available — it's what traders are actually pricing in, not lagging survey data.

**Note:** CME doesn't offer a free API. Options:
- Scrape the page (fragile)
- Use a financial data aggregator that republishes it (Quandl, Alpaca, etc.)
- Skip for V1, add in V2 when a clean source is found

---

### 5. Stock & Market Indexes
**Options (all have some free tier):**

| Source | What You Get | Key Consideration |
|---|---|---|
| **Yahoo Finance (unofficial)** | S&P 500, Dow, NASDAQ, VIX, sector ETFs | No official API — community wrappers exist |
| **Alpha Vantage** | Indexes, individual stocks, forex, crypto | Free tier: 25 requests/day |
| **Polygon.io** | Excellent, well-documented | Free tier limited to previous day's data |
| **Quandl / Nasdaq Data Link** | Strong macro + equities | Some datasets paywalled |
| **CBOE (cboe.com)** | VIX data directly from source | Official, free, XML/CSV |

**Recommended starting point:** Alpha Vantage for V1 — free key, clean JSON, covers
S&P 500 (`SPY`), NASDAQ (`QQQ`), Dow (`DIA`), VIX (`^VIX`).

**Series to show:**
- S&P 500 (price + % change)
- NASDAQ Composite
- Dow Jones Industrial Average
- VIX (volatility index — "fear gauge")
- Gold (GLD) — inflation hedge signal
- 10Y Treasury price (TLT) — inverse of yield, shows bond market stress

---

### 6. CBOE — VIX (direct source)
**Free, no key**
**URL:** https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv

CSV of full VIX history. Good for charting. Also provides term structure data
(VIX9D, VIX1M, VIX3M, VIX6M) which tells you whether near-term or long-term
fear is elevated.

---

## Page Layout

```
/markets

┌─────────────────────────────────────────────────────────┐
│  MARKETS                              Last updated: 3:42p│
│  macro dashboard                                         │
└─────────────────────────────────────────────────────────┘

┌── Fed & Rates ──────────────────────────────────────────┐
│  Fed Funds Rate  5.25%   ▼ from 5.50%                   │
│  10Y Treasury    4.31%   ↑ +0.04                        │
│  2Y Treasury     4.68%   ↑ +0.02                        │
│  Yield Curve    -0.37%   (inverted — watch this)         │
│  Fed Balance   $7.1T     (down from $8.9T peak)          │
└─────────────────────────────────────────────────────────┘

┌── Inflation ────────────────────────────────────────────┐
│  Core PCE       2.8% YoY  (Feb 2025)  Fed target: 2.0%  │
│  CPI            3.2% YoY                                │
│  Core CPI       3.8% YoY                                │
└─────────────────────────────────────────────────────────┘

┌── Labor ────────────────────────────────────────────────┐
│  Unemployment     3.9%                                  │
│  Payrolls       +275k  (Mar 2025)                        │
│  Jobless Claims  214k  weekly                           │
│  Job Openings    8.8M  (JOLTS)                          │
└─────────────────────────────────────────────────────────┘

┌── Housing ──────────────────────────────────────────────┐
│  30Y Mortgage   7.12%                                   │
│  Housing Starts  1.35M annualized                       │
└─────────────────────────────────────────────────────────┘

┌── Markets ──────────────────────────────────────────────┐
│  S&P 500   5,412  ▲ +0.4%                               │
│  NASDAQ   17,129  ▲ +0.6%                               │
│  VIX         14.2  ▼ (calm)                             │
│  Gold     $2,340  ▲ +0.8%                               │
└─────────────────────────────────────────────────────────┘

[ Optional: sparkline mini-charts for each series ]
[ Optional: brief editorial note — "What to watch" ]
```

---

## Technical Architecture — Decision to Make

This is the biggest design question. Hugo is a static site generator — it doesn't
run server code. There are three viable approaches:

### Option A: Client-Side JS (simplest for V1)
Page loads → JavaScript fetches APIs in browser → renders data into DOM.

**Pros:** No build complexity. Data is always current on page load. Easy to iterate.
**Cons:** Exposes API keys in client-side JS. Rate limits per user browser.
Fails gracefully but visibly if API is down.
**Key constraint:** FRED API key cannot be in client-side JS. Must use a proxy or
restrict key by domain.

**Verdict:** Good for V1 if FRED key is domain-restricted and treated as semi-public.
FRED explicitly allows this use case for non-commercial personal sites.

### Option B: Build-Time Data (GitHub Actions fetch at deploy)
A GitHub Actions step fetches all data → writes to `data/markets.yaml` → Hugo renders static HTML.

**Pros:** No API keys in browser. Fast page loads. Data cached between builds.
**Cons:** Data is only as fresh as your last deploy. Need to set up scheduled GitHub Actions run.
**Key constraint:** Need a cron GitHub Actions job (e.g., every 6 hours) to keep data fresh.

**Verdict:** Better for production. More complex to set up. Perfect V2 target.

### Option C: Hybrid
Static data for slow-moving series (monthly FRED data) fetched at build time.
Client-side JS for real-time market prices (S&P, VIX, etc.) which change by the minute.

**Verdict:** Best UX, most work. V3 target.

**Recommendation:** Start with Option A for the spec/prototype. Graduate to Option B
once the layout and data set is finalized.

---

## Data Refresh Strategy

| Series Type | Frequency | Fetch Strategy |
|---|---|---|
| FRED macro (PCE, unemployment, etc.) | Monthly / weekly | Build-time (Option B) or client on load |
| Fed balance sheet | Weekly | Same as above |
| Treasury yields (DGS10, DGS2) | Daily | Client-side or daily GH Actions run |
| Mortgage rates | Weekly | Build-time |
| Market indexes (S&P, VIX) | Real-time / end of day | Client-side JS |
| Gold | Real-time / end of day | Client-side JS |

---

## Hugo Content Structure

```
content/markets.md          ← page definition (like books.md, music.md)
layouts/markets/single.html ← or layouts/page/markets.html
data/markets_cache.yaml     ← build-time cached values (Option B)
assets/js/markets.js        ← client-side fetch logic (Option A/C)
```

Front matter for `content/markets.md`:
```yaml
---
title: "Markets"
description: "Macro economic dashboard — FRED, Treasury, and market data"
layout: "markets"
---
```

---

## Questions to Resolve Before Building

### Data & API
- [ ] **FRED API key:** Register at fred.stlouisfed.org. Is domain restriction sufficient
  for client-side use, or do we need a proxy? Decision affects entire architecture.
- [ ] **Alpha Vantage key:** Register at alphavantage.co for stock indexes. Same question.
- [ ] **CME FedWatch:** Is there a clean, free, programmatic source for implied rate
  probabilities? Or skip for V1?
- [ ] **Data freshness target:** Is end-of-day OK for most data, or do we want intraday?
  End-of-day dramatically simplifies the architecture.
- [ ] **Historical depth:** Show only current values, or sparkline charts with 6-12 months
  of history? Charts require more data and a charting library decision.

### Design
- [ ] **Charting library:** If sparklines/charts are desired, which library?
  - Chart.js — popular, ~60kb, easy
  - Lightweight Charts (TradingView) — gorgeous, built for finance, free open source
  - D3.js — powerful but heavyweight, overkill for simple sparklines
  - Plain SVG — no library, works in Hugo templates, limited interactivity
- [ ] **Color system:** Use existing hot pink / gold theme, or break convention with
  a more "terminal/financial" aesthetic (green/black)? Both are defensible.
- [ ] **Mobile layout:** Cards stack vertically? Horizontal scroll for data tables?
- [ ] **"What to watch" editorial block:** Manually curated text on the page, or skip?

### Architecture
- [ ] **Option A vs B:** Settle this before writing any code. The answer changes everything.
- [ ] **Error states:** What does the page show if an API is down or key is invalid?
- [ ] **Rate limits:** FRED allows 120 requests/minute. Alpha Vantage free tier is 25/day.
  With ~25 FRED series, even a single page load hits limits if done naively.
  Solution: batch requests, cache, or use FRED's "release" endpoints.

---

## Session Build Plan

Work in this order. Each session should be self-contained and leave the build passing.

### Session 1 — Skeleton & Static Data
- Create `content/markets.md`
- Create `layouts/markets/` (or adapt `layouts/page/`)
- Hard-code 5-6 representative values as static HTML
- Style the cards using existing CSS patterns
- Confirm page renders at `/markets` and is linked from nav
- **Success criteria:** Page exists, looks good, build passes

### Session 2 — FRED Client-Side Fetch (Option A)
- Register FRED API key (user action — outside Claude's scope)
- Add key to Hugo config params or a data file (not committed — use `.gitignore`)
- Write `assets/js/markets.js`:
  - Fetch last observation for each FRED series
  - Populate DOM elements by ID
  - Add loading states and error fallback
- Test with real data in browser
- **Success criteria:** Live FRED data populates the page

### Session 3 — Stock Index Data
- Register Alpha Vantage key (user action)
- Add S&P 500, NASDAQ, VIX, Gold fetches to `markets.js`
- Handle end-of-day vs. market-hours difference
- **Success criteria:** Market section populates with real prices

### Session 4 — Build-Time Fetch Migration (Option B)
- Write a Python or Node script: `scripts/fetch_markets.py`
  - Calls FRED + Alpha Vantage
  - Writes results to `data/markets_cache.yaml`
- Add a GitHub Actions job that runs the script on a cron schedule (every 6 hours)
- Update Hugo templates to render from cache, fall back to "last updated" timestamp
- **Success criteria:** Data refreshes without browser API calls

### Session 5 — Charts (Optional V2)
- Decide on charting library
- Add sparklines for key series (Core PCE, 10Y yield, S&P 500)
- Pull 12 months of FRED history per series
- **Success criteria:** Visual trend lines per card

### Session 6 — Polish & Editorial
- Add "What to watch" blurb (manually edited markdown block on the page)
- Add last-updated timestamp
- Mobile layout pass
- Accessibility: aria labels for data values
- **Success criteria:** Publishable quality

---

## Reputable Public Data Sources — Extended List

For future expansion beyond FRED:

| Source | URL | What It Offers | Key |
|---|---|---|---|
| **World Bank** | data.worldbank.org/indicator | Global GDP, inflation, trade | None |
| **IMF Data** | imf.org/en/Data | Global financial stability data | None |
| **ECB Data Portal** | data.ecb.europa.eu | Euro area rates and inflation | None |
| **Bank of Japan** | stat.boj.or.jp | Japanese rates, QE programs | None |
| **Quandl / Nasdaq Data Link** | data.nasdaq.com | Commodities, rates, futures | Free tier |
| **EIA (Energy Info Admin)** | api.eia.gov | Oil, natural gas, gasoline prices | Free key |
| **Census Bureau** | census.gov/data/developers | Housing, retail, business activity | Free key |
| **SEC EDGAR** | efts.sec.gov/LATEST/search-index | 13F filings, insider activity | None |
| **CFTC** | cftc.gov/MarketReports | Commitment of Traders (COT) | None |
| **BIS** | bis.org/statistics | Global credit, FX, derivatives | None |

**Near-term additions that pair well with FRED:**
- **EIA:** Oil price (WTI, Brent), gasoline prices. Inflation story is incomplete without energy.
- **Census Bureau:** Housing starts, retail sales breakdowns (FRED re-publishes but Census is more granular)
- **Commitment of Traders (CFTC):** Who is long/short in futures markets — tells you what institutional
  money is positioned for. Very useful for gold, crude, Treasury futures.

---

## Best Practices for Future Sessions

1. **Read this file first.** Just like MONKEYS.md — every markets session starts here.
   The architecture choice (Option A/B/C) must be consistent across sessions.

2. **Never commit API keys.** FRED key, Alpha Vantage key, etc. go in a `.env` file
   (gitignored) or Hugo `config/_default/params.toml` with the file gitignored.
   For GitHub Actions, use repository secrets.

3. **Batch FRED requests.** FRED supports fetching multiple series in one call via
   their "category" and "release" endpoints. Don't make 25 individual API calls per
   page load — your rate limit will be gone in minutes.

4. **Use FRED's `sort_order=desc&limit=1`** to fetch only the latest observation.
   Full history is only needed if you're charting.

5. **Degrade gracefully.** If an API call fails, show the last cached value with a
   "data unavailable" flag — don't show a broken empty card.

6. **Sparklines before full charts.** A simple SVG polyline built from 12 data points
   requires no library and loads fast. Add a chart library only when you've confirmed
   the page works and looks right without one.

7. **Separate concerns.** Data fetching (JS or Python script), data storage (YAML cache),
   and rendering (Hugo templates) should be independent. This makes each layer
   testable and replaceable.

8. **Label your numbers.** Always show: value, unit, timeframe, and source.
   "3.2%" is ambiguous. "CPI: 3.2% YoY (Jan 2026, BLS via FRED)" is not.

---

*Last updated: 2026-03-10. Spec only — implementation begins in Session 1.*
