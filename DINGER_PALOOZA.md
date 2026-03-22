# Dinger Palooza — Project Spec & Season Roadmap

Weekly MLB home run draft assistant hosted at **almondfarm.us/dinger-palooza/**.
Read this file before any Dinger Palooza session. It is the persistent memory across sessions.

---

## League Rules (source of truth)

> "Each Sunday, you draft 5 hitters who are yours for the week. Every home run they hit that week you get a point. If it's a 3/4 run home run you get 2 points. If they hit a 2nd home run in a game you pick up a bonus point (so 3 total), a 3rd an additional 2 bonus points (so 6 total). By Sunday afternoon you have to declare if you are going to keep the player or drop them. To keep them for a 2nd week costs you 1 point. The 3rd week will cost you 2 points, 4th 3 points, and on and on. After players are dropped, we'll redraft to fill holes. Traditional draft (not snake) starting with the lowest total score team each week. You can not pick a player you dropped that week. $100 cash prize for the winner."

### Scoring formula
| HRs in a game | Points |
|---|---|
| 1 | 1 (2 if 3- or 4-run HR) |
| 2 | 3 total |
| 3 | 6 total |
| n | n×(n+1)/2 total |

### Keep cost
| Weeks held | Cost |
|---|---|
| 1st | Free |
| 2nd | −1 pt |
| 3rd | −2 pts |
| 4th | −3 pts |
| nth | −(n−1) pts |

---

## Architecture

```
scripts/dinger_palooza/
├── main.py                    # orchestrator — runs full pipeline, saves JSON
├── config.py                  # players, park factors, weights, scoring rules
├── requirements.txt
└── agents/
    ├── schedule_agent.py      # MLB Stats API → games/player, park factor per game
    ├── weather_agent.py       # OpenWeatherMap → rain%, temp, wind-out
    ├── pitcher_agent.py       # MLB Stats API → HR/9 matchup score
    └── scorer_agent.py        # 4-factor weighted rank + reasoning

data/dinger_palooza/
├── draft_board.json           # Hugo reads this — updated weekly by GH Actions
└── intermediate/              # raw agent outputs for debugging
    ├── schedule.json
    ├── weather.json
    └── pitcher.json

layouts/dinger-palooza/single.html   # custom Hugo layout
content/dinger-palooza.md            # page front matter
assets/css/main.css                  # DP styles appended at bottom
.github/workflows/dinger-palooza.yml # Monday 8am ET cron → commits JSON → triggers deploy
```

### Scoring weights (current)
| Factor | Weight | Source |
|---|---|---|
| Schedule (games) | 35% | MLB Stats API |
| Pitcher matchup | 30% | MLB Stats API (HR/9) |
| Park factor | 20% | Hardcoded multi-year averages in config.py |
| Weather | 15% | OpenWeatherMap |

---

## Candidate Sluggers

**TODO: Owner to confirm final list of 6–8 players before season starts.**

Current placeholder list (10 players — trim to confirmed list):
- Cal Raleigh (SEA)
- Aaron Judge (NYY)
- Kyle Schwarber (PHI)
- Shohei Ohtani (LAD)
- Junior Caminero (TB)
- Juan Soto (NYM)
- Ronald Acuna Jr (ATL)
- Bobby Witt Jr (KC)
- Jose Ramirez (CLE)
- Pete Alonso (NYM)

To update: edit `PLAYERS` list in `scripts/dinger_palooza/config.py`.

---

## Season Roadmap & Todo List

### 🔴 Must do before first draft (Week 1)

- [ ] **Confirm player list** — owner to give final 6–8 sluggers; update `config.py`
- [ ] **Add OWM_API_KEY secret** to GitHub repo (Settings → Secrets → Actions → `OWM_API_KEY`)
- [ ] **Test pipeline manually** — run `python main.py` from a machine with internet access (not this sandbox); verify JSON output looks correct
- [ ] **First week is 1.5 weeks** — GH Actions cron may need a manual trigger for week 1 (use workflow_dispatch in GitHub Actions UI)

---

### 🟡 Short-term improvements (first few weeks)

#### Data quality
- [ ] **Batter handedness vs. park splits** — Yankee Stadium is elite for LHH (Judge, Schwarber) but neutral for RHH. Add `bats` field to PLAYERS config and adjust park score accordingly. MLB API has handedness on `/api/v1/people/{id}`.
- [ ] **Platoon splits** — most sluggers have 20–40% HR rate gap vs. LHP/RHP. MLB Stats API has `group=hitting&sitCode=vr` splits. Add to pitcher agent.
- [ ] **Recent form (last 14 days)** — a player mid-streak is likely to continue. Pull `stats=lastXGames&gameType=R` from MLB Stats API. Add a 5th "form" factor or use as a tiebreaker.
- [ ] **Injury/IL status check** — a player on the IL is worth 0 pts. Add a quick roster status check to schedule_agent before counting games. MLB API: `/api/v1/teams/{teamId}/roster?rosterType=active`.
- [ ] **Batting order position** — cleanup hitters (3/4/5) face more runners on base → more 3/4-run HR chances (+1 bonus pt). MLB API: `/api/v1/game/{gamePk}/boxscore` or `/api/v1/teams/{teamId}/lineup`. Add to game-level data.

#### Scoring model
- [ ] **Multi-HR bonus weight in draft score** — players with high HR/game rate (not just HR/season) are disproportionately valuable because of the triangular bonus. Consider factoring in HR/G from recent history as a multiplier on overall score.
- [ ] **Keep cost decision support** — surface `keep_recommendation()` from scorer_agent on the page. Show: "Keep cost: 1pt. Expected pts: ~2.1. Recommended: KEEP."

---

### 🟢 Mid-season improvements (weeks 3–8)

#### Results tracking
- [ ] **Weekly results data** — add `data/dinger_palooza/results/week_XX.json` tracking actual HRs hit, pts scored, keep/drop decisions. Update manually or via a separate script.
- [ ] **Season leaderboard page** — `content/dinger-palooza-standings.md` + layout reading from results JSON. Shows cumulative points, keep history per player.
- [ ] **Projection vs. actual comparison** — after each week, compare the agent's predicted rank to actual HR output. Useful for tuning weights.

#### Advanced stats
- [ ] **Baseball Savant barrel %** — barrel rate predicts HR better than raw HR count. CSV export endpoint: `https://baseballsavant.mlb.com/statcast_search/csv?type=batter&...`. Add to pitcher agent or as a standalone agent.
- [ ] **ISO (isolated slugging)** — slugging minus batting avg. Strong predictor of HR power. Available from MLB Stats API advanced stats endpoint.
- [ ] **Team OBP/wOBA context** — a slugger on a high-OBP lineup gets more 3/4-run HR chances. Pull team offensive stats and use as a small multiplier.

---

### 🔵 Nice-to-have (later in season / offseason)

- [ ] **Interactive keep/drop calculator** — JavaScript widget on the page: enter "weeks held" and "last week's score", outputs keep cost, break-even, recommendation
- [ ] **Email/SMS notification** — GitHub Actions sends a summary when board updates. Could use a free SendGrid or Mailgun webhook.
- [ ] **Wrigley Field wind flag** — Wrigley's park factor swings wildly based on wind direction. Already have wind data from weather agent; add specific Wrigley logic (wind out = PF ~115, wind in = PF ~80).
- [ ] **Coors Field fatigue correction** — players return from Coors with a "Coors hangover" the following series. Minor edge case but real.
- [ ] **Historical head-to-head batter vs. pitcher** — MLB Stats API has career matchup data. Very useful for close calls.
- [ ] **Mobile-friendly game grid** — current table is cramped on small screens; consider a card-per-game layout for mobile.
- [ ] **Draft order helper** — page section showing current draft order for the week based on standings input.

---

## Weight Tuning Log

Track weight changes here so we can see what we tried and why.

| Date | Schedule | Pitcher | Park | Weather | Reason |
|---|---|---|---|---|---|
| 2026-03-22 | 35% | 30% | 20% | 15% | Initial values; added park factor |

---

## Session Notes

### 2026-03-22 (Session 1)
- Built full 4-agent pipeline (schedule, weather, pitcher, scorer)
- Hugo page live at /dinger-palooza/ with rules panel, park factor, keep cost table
- GitHub Actions cron configured (Monday 8am ET)
- Park factors hardcoded for all 30 parks with notes
- Multi-HR bonus logic documented in config.py (`hr_game_points()`)
- **Blocked**: MLB Stats API + OpenWeatherMap blocked from sandbox; pipeline must run via GH Actions or locally
- **Pending**: owner to confirm player list + add OWM_API_KEY secret

---

## Known Issues

- The sandbox environment (Claude Code on the web) cannot reach `statsapi.mlb.com` or `api.openweathermap.org` due to proxy restrictions. The pipeline only runs in GitHub Actions or locally.
- `get_target_week()` now returns the current Mon–Sun week (not next week). Adjust if you want the *next* week's data generated on the current week.
- Park factors are multi-year averages (circa 2023–2025). Chase Field moved to a new ballpark in 2024 — verify that data is current.
