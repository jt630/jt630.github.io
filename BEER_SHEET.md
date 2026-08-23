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

**League:** "Show us your TDs" — Sleeper league ID `1361155919865454592`

**Format:** 12-team, snake draft, full PPR (exactly 1.0 pt/reception, no TE premium)

**Starters per week:** 1 QB, 2 RB, 2 WR, 1 TE, 2 FLEX (RB/WR/TE), 1 K, 1 DST

**Bench:** 5 players (total roster = 15: 10 starters incl. flex + K + DST, + 5 BN)

**Scoring:** Read live from **Sleeper** league via `sleeper_agent.py`, cached to `data/beer_sheet/league.json`. The Sleeper API is fully public — no credentials needed, just a league ID or username. If Sleeper is unavailable, a cached `league.json` is the fallback, then config.py presets as the last resort (see `main.load_league`).

**Roster positions:** 1QB / 2RB / 2WR / 1TE / 2FLEX / K / DST

**DEF vs. D/ST — a silent-failure trap:** Sleeper's roster slot is named `DEF`; ESPN's position is named `D/ST`. Neither matches our internal position key. `sleeper_agent.py` normalizes both via `POSITION_ALIASES = {"DEF": "DST", "DST": "DST", "D/ST": "DST"}` to the canonical `DST` used everywhere downstream (config.POSITION_MAP, roster starters, flex eligibility, etc.). If a future change to sleeper_agent.py drops this normalization, the DST starter slot silently stops matching any player position and every defense disappears from the board with no error raised — worth an explicit spot-check after touching that file.

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

Each stage is a pure transform over the data contract. Pipeline order is strict (each stage consumes the previous stage's output). `main.py` runs stages 2 (league resolve) then 1, 3-7 in that order — see `run_pipeline`.

| Stage | Agent | Input | Output | Purpose |
|-------|-------|-------|--------|---------|
| 1. **League** | `sleeper_agent.py` | Sleeper /v1/league/{id} API | `league.json` | Exact scoring settings + roster config from the league (authoritative; cached `league.json` then config.py presets are the fallbacks — see `main.load_league`) |
| 2. **Fetch** | `fetch_agent.py` | ESPN kona_player_info API | `intermediate/espn_raw.json` | Raw player universe (~900 players): projections as stat components, ADP, auction values, expert ranks |
| 3. **Project** | `projection_agent.py` | espn_raw.json + league.json | `intermediate/projections.json` | Blend ESPN projection (65%) + last season actuals (20%) + market implied (15%); re-score under league rules |
| 4. **Value** | `value_agent.py` | projections.json + league (roster) | `intermediate/values.json` | Solve replacement_levels by simulation (given 2 flex spots), compute VOR and auction $, rank by value_delta |
| 5. **Risk** | `risk_agent.py` | projections.json | `intermediate/risk.json` | Injury penalties, expert rank disagreement, floor/ceiling bands |
| 6. **Tier** | `tier_agent.py` | projections.json + values.json | `intermediate/tiers.json` | Detect tier breaks when VOR gap > 1.75× median gap; label RB1, RB2, etc. |
| 7. **Sheet** | `sheet_agent.py` | projections + values + risk + tiers + league | `board.json` | Flatten all fields into single player records; sort by vor_rank; add league metadata |

### Running it

```bash
python scripts/beer_sheet/main.py --league-id 1361155919865454592   # full refresh
python scripts/beer_sheet/main.py --skip-fetch                      # reuse cached espn_raw.json
python scripts/beer_sheet/main.py --username jt630                  # resolve league by Sleeper username
```

CLI flags (`main.parse_args`): `--league-id`, `--username`, `--season` (default from `BEER_SHEET_SEASON` env or 2026), `--skip-fetch` (reuse cached ESPN pull instead of re-downloading), `--max-players` (ESPN pool size, default 900), `--board-size` (final sheet size, default `sheet_agent.BOARD_SIZE`).

---

## The Model Explained

### Why Value Over Replacement (VOR)?

A 300-point QB is worthless if the 12th-best QB also scores 290 points. **VOR isolates the unique contribution each player brings.**

`VOR = projected_points - replacement_level[position]`

Replacement level is **not a fixed cutoff** (e.g., "top 50 RBs"). `value_agent.solve_replacement_levels` finds it with a greedy starter-fill simulation:
1. Sort every player league-wide by proj_points, descending.
2. Walk the list once. Each player fills the highest-priority open slot they're eligible for: their position's dedicated slots first (teams x starters[pos]), then a flex slot (teams x flex) if their position is flex-eligible and no dedicated slot is open.
3. Stop once every dedicated and flex slot is full. Replacement level for a position = proj_points of the last player who filled a slot there (dedicated or flex).

With 2 flex spots, the replacement level for RB ends up higher than for WR, because flex lets RBs get drafted deeper into the pool than a naive per-position cutoff would suggest. `--baseline` on `value_agent.py` runs a naive fixed-cutoff version (ignoring flex entirely) for comparison; both are logged on every run so the flex-driven difference is visible. K and DST never touch flex, so their replacement level always equals the naive cutoff.

### Why Blend Three Projections?

No single source is perfect. Our hybrid projection uses:
- **ESPN 65%** — forward-looking, accounts for team changes mid-offseason
- **Prior season actuals 20%** — anchors on proven usage and role
- **Market implied 15%** — ADP-backed wisdom of the crowd

For rookies, prior_actual weight (20%) is redistributed onto ESPN (now 80% / 20% split), since there's no last season to regress toward.

**Market implied is computed WITHIN position, not league-wide.** `projection_agent._apply_market_implied` ranks each player by ADP against a points curve built only from players at his own position. A single league-wide curve is dominated at the top by QBs, who outscore every other position under standard scoring — indexing "drafted 22nd overall" into a league-wide curve maps that pick to "22nd-highest scorer leaguewide," which is almost always a QB regardless of what position actually went 22nd. That would assign a QB-inflated market_points figure to, say, an RB taken 22nd overall, manufacturing a fake gap between his market opinion and his own RB-scaled projection. Scoping the curve to position keeps market_points on the same scale as espn_points/proj_points, so any blend gap reflects real market disagreement, not the shape of the position's scoring curve.

K/DST and any player with no ADP (undrafted, `adp >= 999.0`) get no market opinion — market_points falls back to their own espn_points.

### value_delta: The Headline Column

`value_delta = adp_rank - vor_rank`

- **Positive value_delta**: the market ranks this player lower than our VOR rank. A bargain. Buy low.
- **Negative value_delta**: the market overrates this player. Avoid in early rounds; target late as value corrects.
- **Zero**: perfectly efficient market pricing — OR the player is outside the real-ADP window (see below); check `has_real_adp` to tell which.

**`value_delta` is only computed inside a real-ADP window.** `value_agent.compute_value_delta` only populates value_delta for players within `config.REAL_ADP_POOL_MULTIPLIER` (1.25) x (teams x total roster slots) of the draft pool — roughly the top ~225 players by ADP in this league. ESPN reports an ADP-derived number for nearly every player in the ~900-player pool, but past real draft depth it degenerates into a smooth, meaningless curve where hundreds of undrafted players compress into a narrow ADP band (a real pull had ~750 of 900 players packed into a 20-point range). Diffing vor_rank against ADP rank inside that band manufactures huge fake "bargains" — a kicker nobody will ever draft showing up as "our #128 vs. ADP #836" reads as a massive buy signal and isn't one. Outside the window, `value_delta = 0` and `has_real_adp = false`, so the sheet can tell "no signal" apart from "zero signal."

### Scoring Re-scoring Under Any Ruleset

ESPN returns raw stat COMPONENTS (pass_yards, rush_tds, receptions, etc.) for every player, indexed by ESPN's numeric stat IDs. See `config.STAT_MAP`. This lets us:
1. Ignore ESPN's default PPR total
2. Compute points using only our league's exact scoring rules
3. Support half-PPR, standard, TE premium, superflex, etc. — just change the scoring config

**K and DST can't be re-scored this way.** Their real Sleeper scoring is field-goal distance buckets and points/yards-allowed tiers — see `unmapped_scoring_keys` in `league.json` for the full list ESPN's offensive component data has no equivalent for (`fgm_0_19` through `fgm_50p`, `pts_allow_0` through `pts_allow_35p`, `yds_allow_0_100` through `yds_allow_550p`, plus IDP-flavored extras like `sack`, `int`, `ff`, `blk_kick`, `safe`, `def_td`, `st_td` that don't apply to this roster format at all). For those two positions, `projection_agent.py` skips re-scoring entirely and passes through ESPN's own `appliedTotal` projection, marking the record `component_blind: true`. Every downstream K/DST number — proj_points, weekly_points, the blend — is really "whatever ESPN's own model says," not our re-scored, three-source blend. Treat K/DST projections as a lower-confidence input than every other position on the board.

**K/DST confidence discount.** Even setting `component_blind` aside, raw VOR at K/DST isn't actionable the way it is elsewhere: the year-over-year gap between (say) K3 and K15 doesn't reliably persist the way the gap between WR20 and WR45 does — it's closer to noise than signal. `config.CONFIDENCE_DISCOUNT` (`{"K": 0.15, "DST": 0.15}`) accounts for this, but the mechanics matter: `value_agent.compute_vor` applies the discount to the **projected point total**, before subtracting replacement level — `(proj_points x discount) - replacement_level` — not to the VOR delta (`(proj_points - replacement_level) x discount`). Those look interchangeable but aren't. K/DST replacement level is large (~90-150 season points) relative to the position's whole VOR spread (~15-40 points top to bottom); shrinking only the delta multiplicatively can never push an always-positive VOR below zero, no matter how small the factor — the single best-projected kicker would still out-rank every skill player sitting at or below replacement. Shrinking the point total first means even the best kicker's discounted total falls well short of replacement, guaranteeing a solidly negative score and keeping K/DST out of the top of the board. The discount is still multiplicative, so it preserves ordering (and tiering) within K and within DST — it just changes where the whole position lands relative to everyone else.

One consequence: for K/DST, the `vor` field used for ranking is no longer literally "points above replacement" — it's a deliberately pessimistic score. `vor_raw` (`proj_points - replacement_level`, the textbook definition, undiscounted) is preserved alongside it on every player record so the honest number isn't lost.

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
- `12_2flex`: 12 teams, 2 flex spots (DEFAULT preset — note its `bench` is still 6 in config.py; the REAL league, read live from Sleeper into `league.json`, has `bench: 5`. Sleeper's league.json is authoritative and always overrides this preset when reachable — see `main.load_league`. Worth reconciling the preset's bench count so the fallback path doesn't quietly disagree with the real league.)
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

**Confidence discount (added after first pipeline run — see "The Model Explained" above for the full rationale):**
```python
CONFIDENCE_DISCOUNT = {"K": 0.15, "DST": 0.15}
```
Shrinks K/DST's projected point total (not the VOR delta) before subtracting replacement level, so low-confidence K/DST projections can't out-rank skill-position players near replacement.

**Real-ADP pool multiplier (added after first pipeline run):**
```python
REAL_ADP_POOL_MULTIPLIER = 1.25
```
Caps how many players (1.25 x teams x total roster slots) are eligible for a real `value_delta`; beyond that window ADP is noise, not signal — see "value_delta: The Headline Column" above.

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
- [x] **projection_agent.py** — blends ESPN + prior + market; re-scores under league rules
- [x] **value_agent.py** — solves replacement_levels by simulation; computes VOR and auction $
- [x] **sheet_agent.py** — produces board.json ready for Hugo
- [x] **board.json schema** — matches CONTRACT.md (see the `weekly_points` 17-vs-18 discrepancy noted below)
- [x] **Hugo layout** — `layouts/beer-sheet/single.html` renders board.json
- [x] **Hugo content** — `content/beer-sheet.md` landing page
- [x] **Manual test / data-quality audit** — full pipeline run against live 2026 ESPN data; top 30 players spot-checked against live sources, no factual errors found; three real modeling defects found and fixed post-run (see Session Notes below)
- [ ] **GitHub Actions** — no beer-sheet refresh workflow exists yet. `refresh-data.yml` is unrelated (cocktails/movies/books). See roadmap item below, modeled on `dinger-palooza.yml`.

### 🟡 Short-term Improvements (First Draft)

#### Data quality
- [ ] **`is_rookie` is defined wrong.** `projection_agent.py` sets `is_rookie = prior_points <= 0.0` — "scored zero fantasy points last season." That also captures real veterans who simply missed the season to injury (Jonathon Brooks, Tank Dell are live examples in the current data), and it matters: `is_rookie=True` redistributes the full prior_actual blend weight (20%) onto ESPN, which is the right move for an actual rookie with no NFL track record but the wrong move for an injured veteran with real career context ESPN's projection may already be leaning on. Consider splitting into two flags — `has_usable_prior` (drives the blend-weight redistribution) vs. a true `is_rookie` (drafted/debuted this season, for display/UX only).
- [ ] **Strength-of-schedule and playoff-weeks (15-17) analysis** — `weekly_points` is already collected per player (see CONTRACT.md) but nothing downstream reads it; a SOS/playoff-weeks pass could use it directly instead of a new fetch.
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
- [ ] **Live draft tracking via Sleeper's draft API** — read picks as they happen during the actual draft; cross off drafted players and recompute value_delta against what's still on the board in real time.
- [ ] **Email/Slack alerts** — notify when a value player falls to a certain round
- [ ] **Scheduled board refresh via GitHub Actions** — no workflow currently refreshes `board.json` automatically; model one on `.github/workflows/dinger-palooza.yml` (cron trigger, run `main.py`, commit the regenerated `data/beer_sheet/` outputs).

---

## Session Notes

### 2026-08-22 (Session 1 — Full Pipeline Built, Run, and Corrected)

**What actually happened:** the full pipeline got built out and run end-to-end against live 2026 ESPN data, not just documented. `main.py` now orchestrates all seven stages for real: Sleeper league resolve → ESPN fetch → projection blend/re-score → VOR/value → risk → tiers → board.json, and that board.json is what `layouts/beer-sheet/single.html` renders at `/beer-sheet/`.

**Data-quality audit:** the top 30 players on the resulting board were spot-checked by hand against live sources (current ADP, injury status, team/depth-chart context). No factual errors were found in that sample.

**Three real modeling defects were found and fixed after the first end-to-end run** — none of these were anticipated when this doc was first written, and all three are now documented in "The Model Explained" and in `config.py`/`value_agent.py`/`projection_agent.py` comments:
1. **Market-implied points were being computed league-wide.** A single points curve is dominated at the top by QBs, so indexing ADP rank into a league-wide curve mapped non-QB picks onto QB-scaled numbers and corrupted the blend. Fixed by scoping the curve to each position (`projection_agent._apply_market_implied`).
2. **K/DST were out-ranking skill players.** Raw VOR for kickers/defenses is technically positive and can't be pushed negative by a multiplicative discount on the delta alone, since K/DST replacement level is large relative to the position's own VOR spread — a discounted delta can still exceed a skill player sitting near replacement. Fixed by adding `config.CONFIDENCE_DISCOUNT` and applying it to the projected point total *before* subtracting replacement level, not to the VOR delta (`value_agent.compute_vor`).
3. **`value_delta` was being computed over noise.** ESPN assigns an ADP-derived number to nearly the full ~900-player pool, but past real draft depth that number compresses hundreds of players into a meaningless narrow band; diffing vor_rank against ADP rank in that band manufactured huge fake "bargains." Fixed by adding `config.REAL_ADP_POOL_MULTIPLIER` and restricting `value_delta` to a realistic draft-pool window, with `has_real_adp` flagging the rest (`value_agent.compute_value_delta`).

**Corrections discovered vs. this doc's original (assumption-based) draft** — this file has now been updated to match, see the sections above:
- League is 15-man rosters with a **5-man bench**, not 6 (real Sleeper roster: QB/RB/RB/WR/WR/TE/FLEX/FLEX/K/DEF + 5 BN).
- Sleeper's `DEF` and ESPN's `D/ST` both normalize to internal `DST` via `POSITION_ALIASES` in `sleeper_agent.py` — undocumented before, and a silent-failure risk if a future edit drops it.
- K/DST are `component_blind`: their real scoring (FG-distance buckets, points/yards-allowed tiers) has no equivalent in ESPN's offensive stat components, so their projections pass through ESPN's own total untouched.
- `CONFIDENCE_DISCOUNT` and `REAL_ADP_POOL_MULTIPLIER` are two new constants in `config.py`, added after the first run specifically to fix defects 2 and 3 above.
- CONTRACT.md's `weekly_points` (documented as 17 entries) is stale — the real 2026 season and the real code both produce 18.

**Blocked/Pending:** none. MVP checklist is essentially complete (pipeline, board.json, Hugo layout/content all exist and run). Remaining open items are the roadmap enhancements above (rookie-flag split, SOS/playoff-weeks analysis, live draft tracking, scheduled refresh via GitHub Actions).

---

## Known Issues & Caveats

- ESPN's kona_player_info API is read-only but may rate-limit or return partial data during peak draft week. Cache aggressively.
- Sleeper's API is fully public but may lag by a few seconds during live drafts. Sleeper league_id is required; username lookup adds one extra API call.
- Replacement level changes if the roster format or flex eligibility changes. Must re-simulate if rules change mid-season.
- Projected points are ALWAYS in the league's scoring. If switching between half-PPR and full-PPR leagues, re-run projection_agent with the new scoring config.
- VOR is only meaningful for rounds 1-10. Beyond bench cutoff, VOR collapses (everyone projects close to 0).
- Expert ranks from ESPN may omit rookies or late-round lottery picks (stdev data unavailable). Fallback to generic risk band.
- **Known doc discrepancy:** `CONTRACT.md` documents `weekly_points` as a 17-entry array. The real 2026 season is 18 weeks (17 games + 1 bye), and `projection_agent._weekly` actually loops `range(1, 19)`, producing 18 entries (index 0 = week 1). CONTRACT.md is not owned by this doc's authors this session and hasn't been corrected — treat "17 entries" in CONTRACT.md as stale until it's updated; the real array length is 18.
