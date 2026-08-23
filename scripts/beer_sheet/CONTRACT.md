# Beer Sheet — Inter-Agent Data Contract

Every agent is a pure transform over these shapes. Do not invent fields; do not
rename fields. If you need a new field, it goes in this file first.

Pipeline order:

    fetch_agent      → intermediate/espn_raw.json
    sleeper_agent    → league.json                (exact scoring + roster)
    projection_agent → intermediate/projections.json
    value_agent      → intermediate/values.json
    risk_agent       → intermediate/risk.json     (keyed by player_id)
    tier_agent       → intermediate/tiers.json    (keyed by player_id)
    sheet_agent      → board.json                 (Hugo reads ONLY this)

---

## PlayerProjection — `intermediate/projections.json`

```json
{
  "season": 2026,
  "scoring_name": "sleeper:1234567890",
  "players": [
    {
      "player_id": 4429795,
      "name": "Jahmyr Gibbs",
      "position": "RB",
      "team": "DET",
      "bye_week": 8,
      "injury_status": "ACTIVE",
      "age": null,

      "proj_points": 312.4,          // OUR blended projection, league scoring
      "espn_points": 318.9,          // ESPN projection re-scored to our rules
      "prior_points": 301.2,         // last season's actuals, our rules (0.0 if rookie)
      "market_points": 305.0,        // ADP-implied points
      "is_rookie": false,

      "stats": {"rush_yards": 1372.6, "receptions": 67.8},  // projected components
      "weekly_points": [18.2, 19.1],  // 17 entries, index 0 = week 1; 0.0 = bye/unknown

      "adp": 1.47,                   // 999.0 when undrafted/unranked
      "auction_value_market": 65.47,
      "expert_ranks": [1, 2, 1, 2],  // per-source ranks, for disagreement
      "outlook": "Gibbs has finished..."
    }
  ]
}
```

Rules:
- `proj_points` is ALWAYS in the league's scoring. Never ESPN's default.
- Missing/absent numeric data → `0.0`, never `null`.
- `position` is one of QB RB WR TE K DST.

## PlayerValue — `intermediate/values.json`

```json
{
  "replacement_levels": {"QB": 241.0, "RB": 118.5, "WR": 131.2, "TE": 92.0, "K": 120.0, "DST": 100.0},
  "replacement_ranks":  {"QB": 14, "RB": 41, "WR": 47, "TE": 13},
  "players": [
    {
      "player_id": 4429795,
      "vor": 193.9,              // proj_points - replacement_levels[position]
      "vor_rank": 1,             // 1 = most valuable overall
      "pos_rank": 1,             // rank within position by proj_points
      "auction_value": 62.0,     // our $ price, calibrated to budget x teams
      "value_delta": 0.5         // adp_rank - vor_rank. POSITIVE = market underrates
    }
  ]
}
```

Rules:
- Replacement level with flex > 0 MUST be solved by draft simulation, not a
  fixed cutoff. See value_agent docstring.
- `value_delta` is the sheet's headline column. Positive = a bargain.

## PlayerRisk — `intermediate/risk.json`

```json
{
  "players": [
    {
      "player_id": 4429795,
      "risk_score": 0.18,        // 0.0 = bankable, 1.0 = coin flip
      "risk_label": "SAFE",      // SAFE | MODERATE | VOLATILE
      "floor_points": 265.0,
      "ceiling_points": 355.0,
      "rank_disagreement": 1.4,  // stdev of expert_ranks
      "risk_notes": ["consensus top-3", "no injury designation"]
    }
  ]
}
```

## PlayerTier — `intermediate/tiers.json`

```json
{
  "players": [
    {"player_id": 4429795, "tier": 1, "tier_label": "RB1", "tier_break_after": false}
  ],
  "tier_summary": {"RB": [{"tier": 1, "count": 3, "vor_range": [150.0, 193.9]}]}
}
```

## board.json — the ONLY file Hugo reads

```json
{
  "generated_at": "2026-08-22T22:00:00Z",
  "season": 2026,
  "league": {"name": "...", "teams": 12, "scoring_summary": "Full PPR", "starters": "QB/2RB/2WR/TE/2FLEX/K/DST"},
  "replacement_levels": {"RB": 118.5},
  "tier_summary": {},
  "players": [ /* every field above, flattened into one record per player, sorted by vor_rank */ ]
}
```
