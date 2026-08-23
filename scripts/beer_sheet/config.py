"""
Beer Sheet — shared configuration for all agents.

Everything ruleset-specific lives HERE and nowhere else. To support a new
league format (superflex, TE premium, half-PPR, 10-team), add a SCORING entry
and/or a ROSTER entry and pass --scoring / --roster on the command line. No
agent should ever hardcode a scoring or roster assumption.
"""

import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT        = Path(__file__).resolve().parents[2]
DATA_DIR         = REPO_ROOT / "data" / "beer_sheet"
INTERMEDIATE_DIR = DATA_DIR / "intermediate"
OUTPUT_FILE      = DATA_DIR / "board.json"

SEASON = int(os.environ.get("BEER_SHEET_SEASON", "2026"))

# ── ESPN stat ID map ──────────────────────────────────────────────────────────
# ESPN returns projections as raw stat components keyed by numeric ID. This map
# is what lets us re-score under ANY ruleset instead of trusting ESPN's total.
# Verified against known players (see scripts/beer_sheet/verify_stat_map.py).
STAT_MAP = {
    "0":  "pass_attempts",
    "1":  "pass_completions",
    "3":  "pass_yards",
    "4":  "pass_tds",
    "19": "pass_2pt",
    "20": "pass_interceptions",
    "23": "rush_attempts",
    "24": "rush_yards",
    "25": "rush_tds",
    "26": "rush_2pt",
    "41": "receptions_alt",
    "42": "rec_yards",
    "43": "rec_tds",
    "44": "rec_2pt",
    "53": "receptions",
    "58": "targets",
    "68": "fumbles",
    "72": "fumbles_lost",
}

# ── Positions ─────────────────────────────────────────────────────────────────
POSITION_MAP = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}
SKILL_POSITIONS = ("QB", "RB", "WR", "TE")
FLEX_ELIGIBLE   = ("RB", "WR", "TE")

# ── Scoring presets ───────────────────────────────────────────────────────────
# Points per unit of each stat. Missing key = 0 points.
_BASE = {
    "pass_yards": 0.04, "pass_tds": 4.0, "pass_interceptions": -2.0, "pass_2pt": 2.0,
    "rush_yards": 0.10, "rush_tds": 6.0, "rush_2pt": 2.0,
    "rec_yards":  0.10, "rec_tds":  6.0, "rec_2pt":  2.0,
    "fumbles_lost": -2.0,
}

SCORING = {
    "ppr":       {**_BASE, "receptions": 1.0},
    "half_ppr":  {**_BASE, "receptions": 0.5},
    "standard":  {**_BASE, "receptions": 0.0},
    # TE premium is a per-position override, handled by POSITION_SCORING_OVERRIDE
    "te_premium": {**_BASE, "receptions": 1.0},
}

# Per-position scoring overrides, e.g. TE premium leagues.
POSITION_SCORING_OVERRIDE = {
    "te_premium": {"TE": {"receptions": 1.5}},
}

# ── Roster presets ────────────────────────────────────────────────────────────
# starters: how many of each position START each week (flex counted separately).
# With flex > 0, replacement level CANNOT be a fixed cutoff — it is solved by
# simulating the draft (see value_agent.solve_replacement_levels).
ROSTER = {
    "12_2flex": {
        "teams": 12,
        "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1},
        "flex": 2,
        "flex_eligible": FLEX_ELIGIBLE,
        "bench": 6,
        "draft_type": "snake",
        "auction_budget": 200,
    },
    "12_1flex": {
        "teams": 12,
        "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1},
        "flex": 1,
        "flex_eligible": FLEX_ELIGIBLE,
        "bench": 6,
        "draft_type": "snake",
        "auction_budget": 200,
    },
    "12_superflex": {
        "teams": 12,
        "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1},
        "flex": 2,
        "flex_eligible": ("QB", "RB", "WR", "TE"),
        "bench": 6,
        "draft_type": "snake",
        "auction_budget": 200,
    },
}

DEFAULT_SCORING = "ppr"
DEFAULT_ROSTER  = "12_2flex"

# ── Projection blend weights ──────────────────────────────────────────────────
# Our projection is a HYBRID: ESPN's projection is the base, regressed toward
# last season's actual production, then nudged by what the market believes.
# Weights must sum to 1.0.
BLEND = {
    "espn_projection": 0.65,   # forward-looking, accounts for team changes
    "prior_actual":    0.20,   # last season's real points — anchors on proven usage
    "market_implied":  0.15,   # ADP-implied points — the wisdom of the crowd
}

# Players with no prior-season data (rookies) redistribute prior_actual weight
# onto espn_projection, since there is nothing to regress toward.

# ── Risk model ────────────────────────────────────────────────────────────────
RISK = {
    # Cross-source rank disagreement (stdev of expert ranks) above this is "volatile"
    "high_disagreement_stdev": 8.0,
    "injury_penalty": {
        "ACTIVE": 0.0, "QUESTIONABLE": 0.03, "DOUBTFUL": 0.10,
        "OUT": 0.25, "INJURY_RESERVE": 0.60, "SUSPENSION": 0.50,
    },
    # Band width as a fraction of projected points, scaled by disagreement
    "band_base": 0.15,
    "band_max":  0.40,
}

# ── Confidence discount ────────────────────────────────────────────────────────
# K and DST VOR is real but not actionable. Two things make it unreliable
# relative to every other position on the board:
#   1. projection_agent marks these players component_blind = true — their
#      scoring (FG-distance buckets, points-allowed tiers) can't be rebuilt
#      from ESPN's offensive stat components, so we're passing through
#      ESPN's own total instead of our own re-scored, blended projection.
#      That's a weaker input than everything else on the sheet.
#   2. Even a perfect projection wouldn't help much: the year-over-year gap
#      between (say) K3 and K15 does not reliably persist the way the gap
#      between WR20 and WR45 does. A few points of "edge" at kicker is
#      closer to noise than signal.
# Straight VOR theory says a kicker a few points above K12 is worth the same
# as a WR a few points above replacement — in practice it isn't, because the
# WR's edge is much more likely to still be there in November.
#
# The discount is applied to the PROJECTED POINT TOTAL itself, not to the
# VOR delta: value_agent computes discounted VOR as
# (proj_points x discount) - replacement_level, rather than
# (proj_points - replacement_level) x discount. Those look similar but
# behave very differently at the low end. K/DST replacement level is a big
# number (~90-150 season points) relative to the whole position's VOR
# spread (~15-40 points top to bottom) — shrinking only the VOR delta can
# never push a positive VOR below zero no matter how small the factor is,
# so the single best-projected kicker would still out-rank every
# skill-position player sitting at or below replacement (there are always
# a few, at every position, near the bottom of the startable pool) — which
# is exactly the bug this discount exists to fix. Shrinking the point total
# BEFORE subtracting replacement means even the best kicker's discounted
# points fall far short of replacement, guaranteeing a solidly negative
# score. That's the honest read anyway: we don't trust the point total
# itself very much (component_blind pass-through, weak YoY persistence),
# not just the marginal edge over replacement.
# The discount is still MULTIPLICATIVE, so it preserves the ratios between
# every K's (and every DST's) discounted score — the best kicker still
# out-scores the worst kicker by the same proportion, so tiering within K
# and within DST is unaffected. 0.15 was chosen generously (i.e. NOT
# pushed to a near-zero extreme) — it already produces a comfortable
# 3-figure negative score for the best-projected K/DST while leaving a
# 100+ point discounted range across the position to tier sensibly, and
# was verified against a real pipeline run to keep K/DST out of the top
# 100 overall by a wide margin.
CONFIDENCE_DISCOUNT = {
    "K": 0.15,
    "DST": 0.15,
}

# ── ADP reliability ───────────────────────────────────────────────────────────
# ESPN reports SOME averageDraftPosition-derived number for nearly every
# player in the pool, even ones no one will ever draft — for real, actively
# drafted players it's a genuine market signal, but past actual draft depth
# it degenerates into a smooth but essentially meaningless curve where
# hundreds of players are compressed into a narrow band (e.g. a real pull
# once had ~750 of 900 players packed into a 20-point ADP range). Ranking
# the FULL pool by that number and diffing against vor_rank manufactures
# huge "value" deltas for players who will never be drafted at all.
# Only players within roughly a real draft's worth of picks have an ADP
# trustworthy enough to diff against — this multiplier sets how far past
# the league's own roster capacity (teams x total roster slots) that
# trustworthy window extends, to leave room for legitimate late-round /
# waiver-wire market signal (handcuffs, rookie sleepers) without reaching
# into the noise.
REAL_ADP_POOL_MULTIPLIER = 1.25

# ── Tiering ───────────────────────────────────────────────────────────────────
TIERS = {
    # A tier break is declared when the VOR gap to the next player exceeds
    # gap_multiplier x the median gap within the current position group.
    "gap_multiplier": 1.75,
    "min_tier_size": 2,
    "max_tiers_per_position": 12,
}
