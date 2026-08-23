# Beer Sheet — Pre-Draft Valuation Spec & Build Plan

One-shot fantasy football pre-draft valuation sheet hosted at **almondfarm.us/beer-sheet/**.
Read this file before any Beer Sheet session. It is the persistent memory across sessions.

---

## Project Overview

**Beer Sheets** are expert-curated pre-draft rankings that convert **projected points into dollar values** and **value tiers**. Unlike Dinger Palooza (a weekly re-rank), this is a **single snapshot**: before draft day, project every draftable player under the league's exact scoring settings, compute value over replacement (VOR), price via auction-dollars-per-point, detect tier breaks, and publish one authoritative board.

The sheet is the answer to: *"Which players are bargains at ADP? Which are overvalued? Should I reach for this guy?"*

**Key questions the sheet answers:**
- What's each player's projected output under OUR scoring rules?
- What's the "replacement level" (the productivity floor for starters)?
- Which players overdeliver relative to ADP? (value_delta > 0)
- Which tier should I target in each round?

---

## League Settings (Source of Truth)

**Format:** 12-team, snake draft, full PPR

**Starters per week:** 1 QB, 2 RB, 2 WR, 1 TE, 2 FLEX (RB/WR/TE), 1 K, 1 DST

**Bench:** 6 players (total roster = 15)

**Scoring:** Read live from **Sleeper** league via `sleeper_agent.py`. The Sleeper API is fully public — no credentials needed, just a league ID or username. If Sleeper is unavailable, config.py presets are the fallback (currently: full PPR, standard ADP values).

**Roster positions:** 1QB / 2RB / 2WR / 1TE / 2FLEX / K / DST

---

## Architecture

```
scripts/beer_sheet/
├── config.py                  # league settings, scoring presets, blend weights
├── agents/
│   ├── __init__.py
│   ├── fetch_agent.py         # ESPN kona_player_info → espn_raw.json
│   ├── sleeper_agent.py       # Sleeper /v1/league/{id} → league.json
│   ├── projection_agent.py    # blend ESPN + prior + market → projections.json (TO BE BUILT)
│   ├── value_agent.py         # solve replacement_levels, VOR → values.json (TO BE BUILT)
│   ├── risk_agent.py          # injury + expert disagreement → risk.json
│   └── tier_agent.py          # tier breaks via VOR gaps → tiers.json
└── main.py                    # orchestrator (TO BE BUILT)

data/beer_sheet/
├── board.json                 # FINAL OUTPUT — what Hugo renders
├── league.json                # Sleeper scoring + roster (authoritative, replaces config presets)
├── intermediate/              # raw agent outputs (for debugging)
│   ├── espn_raw.json          # fetch_agent output: raw stats + ADP + rankings
│   ├── projections.json       # projection_agent: blended proj, weekly breakdown, outlook
│   ├── values.json            # value_agent: VOR, replacement_levels, auction prices
│   ├── risk.json              # risk_agent: risk_score, floor/ceiling, expert disagreement
│   └── tiers.json             # tier_agent: tier breaks + summary per position
└── [week_02_snapshot.json]    # optional: archive pre-draft snapshots by week

layouts/beer-sheet/
├── single.html                # draft board page (TO BE BUILT)
└── components/                # optional: card macros, tier view, etc.

content/
└── beer-sheet.md              # landing page front matter (TO BE BUILT)
```

---

## Data Flow: Seven-Stage Pipeline

Each stage is a pure transform over the data contract. Pipeline order is strict (each stage consumes the previous stage's output).

| Stage | Agent | Input | Output | Purpose |
|-------|-------|-------|--------|---------|
| 1. **Fetch** | `fetch_agent.py` | ESPN kona_player_info API | `intermediate/espn_raw.json` | Raw player universe: projections as stat components, ADP, auction values, 8 expert ranks |
| 2. **League** | `sleeper_agent.py` | Sleeper /v1/league/{id} API | `league.json` | Exact scoring settings + roster config from the league (replaces config.py presets) |
| 3. **Project** | `projection_agent.py` | espn_raw.json + league.json | `intermediate/projections.json` | Blend ESPN projection (65%) + last season actuals (20%) + market implied (15%); re-score under league rules |
| 4. **Value** | `value_agent.py` | projections.json + league.json | `intermediate/values.json` | Solve replacement_levels by simulation (given 2 flex spots), compute VOR and auction $, rank by value_delta |
| 5. **Risk** | `risk_agent.py` | projections.json + espn_raw.json | `intermediate/risk.json` | Injury penalties, expert rank disagreement, floor/ceiling bands |
| 6. **Tier** | `tier_agent.py` | values.json + risk.json | `intermediate/tiers.json` | Detect tier breaks when VOR gap > 1.75× median gap; label RB1, RB2, etc. |
| 7. **Sheet** | `sheet_agent.py` (optional) or final merge | all intermediates | `board.json` | Flatten all fields into single player records; sort by vor_rank; add league metadata |

---

## The Model Explained

### Why Value Over Replacement (VOR)?

A 300-point QB is worthless if the 12th-best QB also scores 290 points. **VOR isolates the unique contribution each player brings.**

`VOR = projected_points - replacement_level[position]`

Replacement level is **not a fixed cutoff** (e.g., "top 50 RBs"). It's solved by simulation:
1. Simulate the draft: 12 teams, snake, each picking their best available player
2. Track what the 13th player at each position scores (the first bench player drafted, if flex allows)
3. That becomes the replacement level for starters

With 2 flex spots, the replacement level for RB is higher than for WR, because flex allows reaching into the next tier.

### Why Blend Three Projections?

No single source is perfect. Our hybrid projection uses:
- **ESPN 65%** — forward-looking, accounts for team changes mid-offseason
- **Prior season actuals 20%** — anchors on proven usage and role
- **Market implied 15%** — ADP-backed wisdom of the crowd

For rookies, prior_actual weight (20%) is redistributed onto ESPN (now 80% / 20% split), since there's no last season to regress toward.

### value_delta: The Headline Column

`value_delta = adp_rank - vor_rank`

- **Positive value_delta**: the market ranks this player lower than our VOR rank. A bargain. Buy low.
- **Negative value_delta**: the market overrates this player. Avoid in early rounds; target late as value corrects.
- **Zero**: perfectly efficient market pricing.

This is why the sheet exists: to find the delta.

### Scoring Re-scoring Under Any Ruleset

ESPN returns raw stat COMPONENTS (pass_yards, rush_tds, receptions, etc.) for every player, indexed by ESPN's numeric stat IDs. See `config.STAT_MAP`. This lets us:
1. Ignore ESPN's default PPR total
2. Compute points using only our league's exact scoring rules
3. Support half-PPR, standard, TE premium, superflex, etc. — just change the scoring config

---

## Data Sources

| Source | Endpoint | What We Use | Authority Level |
|--------|----------|-------------|-----------------|
| **ESPN Fantasy** | `lm-api-reads.fantasy.espn.com/v3/games/ffl/seasons/{season}/segments/0/leaguedefaults/3?view=kona_player_info` | Player projections as raw stat components; ADP; auction values; 8 expert rank sources | Forward-looking projections; market data |
| **Sleeper** | `https://api.sleeper.app/v1/league/{league_id}` | Exact scoring_settings; roster_positions; league metadata | **Authoritative** — scoring rules and roster config replace config.py presets |
| **MLB Stats API** (if needed) | `https://statsapi.mlb.com/` | Rest-of-season schedules, strength-of-schedule, playoff weeks | Optional for advanced filtering |

**Note:** Sleeper's read API requires no authentication. Pass `--league LEAGUE_ID` (or `--username SLEEPER_USERNAME`) and sleeper_agent auto-resolves to league JSON.

---

## Configuration & Presets

See `scripts/beer_sheet/config.py`:

**Scoring presets (fallback if Sleeper unavailable):**
- `ppr`: full point-per-reception
- `half_ppr`: 0.5 points per reception
- `standard`: 0 points per reception
- `te_premium`: full PPR + TE reception bonus

**Roster presets:**
- `12_2flex`: 12 teams, 2 flex spots (DEFAULT)
- `12_1flex`: 12 teams, 1 flex spot
- `12_superflex`: 12 teams, 2 flex spots that include QB

**Blend weights (locked):**
```python
BLEND = {
    "espn_projection": 0.65,
    "prior_actual": 0.20,
    "market_implied": 0.15,
}
```

**Risk constants:**
- Injury penalty: +0.60 for IR, +0.25 for OUT, +0.03 for QUESTIONABLE
- Volatility threshold: stdev of expert ranks > 8.0 → "VOLATILE"
- Band width: ±15% of projected points (scaled by disagreement, capped at 40%)

**Tier breaks:**
- Gap multiplier: 1.75× median within-position gap → tier break
- Min tier size: 2 players
- Max tiers per position: 12

---

## Build Checklist & Roadmap

### 🔴 Must Do Before Draft (MVP)

- [x] **Data contract defined** — CONTRACT.md specifies every JSON shape and field
- [x] **fetch_agent.py** — ESPN kona_player_info endpoint working
- [x] **sleeper_agent.py** — Sleeper API working; outputs league.json
- [x] **config.py** — scoring, roster, blend, risk, tier constants in place
- [ ] **projection_agent.py** — blends ESPN + prior + market; re-scores under league rules
- [ ] **value_agent.py** — solves replacement_levels by simulation; computes VOR and auction $
- [ ] **sheet_agent.py** or final merge — produces board.json ready for Hugo
- [ ] **board.json schema** — validated against CONTRACT.md
- [ ] **Hugo layout** — `/beer-sheet/` page renders board.json with sortable columns
- [ ] **Hugo content** — `beer-sheet.md` landing page with rule explanations
- [ ] **Manual test** — run full pipeline, spot-check 5 player VORs against expert sheets
- [ ] **GitHub Actions** — optional cron to refresh board weekly (if desired)

### 🟡 Short-term Improvements (First Draft)

#### Data quality
- [ ] **Weekly strength-of-schedule** — pull playoff weeks (15-17) matchups; factor into projections
- [ ] **Playoff week schedule** — detect bye weeks 1-14; boost flex value if multiple bye weeks
- [ ] **Handcuff detection** — RB + backup RB pair on same team; show correlation/stack suggestions
- [ ] **Expert consensus** — show which sources rank this player highest/lowest; flag outliers
- [ ] **Injury tracker check** — if a player is on IR, drop their projection to 0 or risk score to 1.0
- [ ] **Target share trend** — does this WR's target share trend up or down season-to-date (live updates)

#### Scoring model
- [ ] **Playoff-weeks weighting** — playoff projections (weeks 15-17) carry 1.5× weight vs. regular season
- [ ] **Bye week impact** — factor bye week density into flex value
- [ ] **Handcuff value calculation** — show value of drafting RB duo vs. single RB + WR

### 🟢 Mid-Season Enhancements (After Week 4)

#### Results tracking
- [ ] **Projection accuracy** — compare pre-draft board vs. actual weekly points; track drift per position
- [ ] **VOR calibration** — post-draft, recompute replacement_levels based on actual draft patterns
- [ ] **Re-ranking for mid-season waiver wire** — weekly updates to board.json with fresh projections
- [ ] **Trade value calculator** — given two players, show win-value of the swap

#### Advanced stats
- [ ] **Snap count trends** — does a RB's snap count increase/decrease each week?
- [ ] **Red zone touches** — RB/TE red zone touch rate (from nflverse data)
- [ ] **QB pressure rate** — higher pressure → more incompletions → fewer TDs
- [ ] **Pass defense DVOA** — rank offenses by defensive strength faced; adjust WR projections

### 🔵 Nice-to-have (Later / Offseason)

- [ ] **Auction dollar history** — archive ADP + auction values by week to show market shift
- [ ] **One-pager PDF export** — downloadable Beer Sheet for offline pre-draft prep
- [ ] **Comparison mode** — side-by-side your board vs. 2025 vs. 2024
- [ ] **Mobile-first card layout** — cramped table on phone; switch to cards per position
- [ ] **Dark mode CSS** — already site-wide; ensure board table is readable in dark
- [ ] **Superflex calculator** — toggle between 2-flex and superflex; see how draft order shifts
- [ ] **TE premium variant** — toggle TE premium scoring; see WR/TE tier shifts
- [ ] **Playoff schedule radar** — visual calendar of bye weeks + playoff matchups
- [ ] **AI-generated commentary** — Claude API summaries per position ("RB class is elite this year")
- [ ] **Live draft tracker** — read Sleeper draft API as picks happen; show value_delta in real-time
- [ ] **Email/Slack alerts** — notify when a value player falls to a certain round

---

## Session Notes

### 2026-08-22 (Session 1 — Documentation & Wiring)

**What was done:**
- Created `BEER_SHEET.md` — comprehensive spec and cross-session memory document
- Defined project scope: one-shot pre-draft valuation sheet (not weekly re-rank like Dinger Palooza)
- Documented full data pipeline: 7 stages from fetch → board.json
- Encoded league settings: 12-team, snake, full PPR, 2 flex, 6 bench
- Documented model: why VOR, why blend three projections, what value_delta means
- Reviewed data contract (CONTRACT.md) and config presets (config.py)
- Reviewed existing agents: fetch_agent.py pulls ESPN, sleeper_agent.py pulls Sleeper
- Added nav entry to hugo.toml under "Ops" menu

**Existing code reviewed:**
- `config.py` — scoring presets, roster presets, blend weights, risk + tier constants
- `scripts/beer_sheet/agents/fetch_agent.py` — ESPN kona_player_info endpoint (reads raw stats, ADP, rankings)
- `scripts/beer_sheet/agents/sleeper_agent.py` — Sleeper /v1/league/ API (authoritative scoring rules)
- `scripts/beer_sheet/agents/risk_agent.py` — injury penalties + expert disagreement
- `scripts/beer_sheet/agents/tier_agent.py` — tier break detection
- `scripts/beer_sheet/CONTRACT.md` — strict JSON schema for all pipeline stages

**Still to build (other agents own this):**
- `projection_agent.py` — blend ESPN + prior + market under league scoring
- `value_agent.py` — solve replacement_levels, compute VOR and auction values
- `sheet_agent.py` or final merge — produce board.json
- Hugo layout at `layouts/beer-sheet/single.html`
- Content stub at `content/beer-sheet.md`
- GitHub Actions workflow (optional cron refresh)

**Architecture decisions locked in:**
- Sleeper read API as authoritative source (no credentials needed; league_id or username)
- VOR must account for flex eligibility via simulation, not fixed cutoff
- Projection blend: ESPN 65% / prior 20% / market 15%
- Value_delta as headline column (positive = bargain)
- Seven-stage pipeline with strict data contracts between stages
- board.json as the only file Hugo reads

**Blocked/Pending:**
- None — documentation is complete. Builds can proceed in parallel.

---

## Known Issues & Caveats

- ESPN's kona_player_info API is read-only but may rate-limit or return partial data during peak draft week. Cache aggressively.
- Sleeper's API is fully public but may lag by a few seconds during live drafts. Sleeper league_id is required; username lookup adds one extra API call.
- Replacement level changes if the roster format or flex eligibility changes. Must re-simulate if rules change mid-season.
- Projected points are ALWAYS in the league's scoring. If switching between half-PPR and full-PPR leagues, re-run projection_agent with the new scoring config.
- VOR is only meaningful for rounds 1-10. Beyond bench cutoff, VOR collapses (everyone projects close to 0).
- Expert ranks from ESPN may omit rookies or late-round lottery picks (stdev data unavailable). Fallback to generic risk band.
