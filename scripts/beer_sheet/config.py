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

# Hand-edited "do not draft" list. See blacklist_agent.py for the tiny YAML
# subset it supports, and the file itself for how to add a player.
BLACKLIST_FILE   = DATA_DIR / "blacklist.yaml"

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

# Players with no usable prior-season sample redistribute prior_actual weight
# onto espn_projection, since there is nothing reliable to regress toward.
# (This is keyed on has_usable_prior, NOT is_rookie — a veteran who missed
# last season to injury has no usable prior sample either, and needs the
# same redistribution a rookie gets. See projection_agent.py.)

# ── Prior-season regression ──────────────────────────────────────────────────
# prior_points (the season TOTAL) conflates two different things: how well a
# player performed per game, and how many games he was healthy enough to
# play. A player who missed half the season to injury has a depressed total
# for a reason that has nothing to do with his talent or role, and blending
# that total straight into next season's projection punishes him twice for
# the same injury. We instead rate-ize: prior total / games played * a full
# expected season, so an elite player who got hurt is compared on a
# per-game basis like everyone else. Stat id "210" in ESPN's raw stat
# component map has been verified (see projection_agent.py investigation)
# to carry games played for the prior season.
GAMES_PER_SEASON = 17          # NFL regular-season length; the scale target for the rate.
PRIOR_SEASON_MIN_GAMES = 4     # Below this many games, the per-game rate is mostly noise —
                                # has_usable_prior goes False and the blend falls back to
                                # redistributing that weight onto the ESPN projection instead.

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

# ── Blacklist defaults ────────────────────────────────────────────────────────
# Used by blacklist_agent when data/beer_sheet/blacklist.yaml omits an
# `auto_flag:` block (or leaves a field out of it). These are injury
# designations severe enough to auto-suppress a player without the owner
# having to remember to type the name in by hand on draft morning.
BLACKLIST_AUTO_FLAG_STATUSES = ["OUT", "INJURY_RESERVE", "SUSPENSION"]
BLACKLIST_AUTO_FLAG_SEVERITY = "FADE"

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

# The pool-size window above catches "too deep to matter" — it does NOT catch
# the case where hundreds of barely-drafted players fall INSIDE that window
# but their raw ADP values are indistinguishable from each other (a real pull
# had ~30 players spanning ADP 167.9-169.7, a ~0.1-0.3 point spread per
# player). Within a band that thin, ESPN's ordering is arbitrary noise, not a
# market signal, and diffing vor_rank against it manufactures huge fake
# "value" deltas for unrosterable players. value_agent detects where that
# compression starts empirically each run (see
# value_agent._detect_adp_compression_cutoff) rather than hardcoding a
# season-specific ADP value or rank — this constant only defines how thin
# consecutive ADP spacing has to get, and stay, before it's "too thin to
# trust." 0.5 ADP points leaves real (if tight) market disagreement between
# neighboring picks intact while catching the multi-hundred-player compressed
# tail, which spaces players well under 0.3 points apart.
ADP_COMPRESSION_GAP = 0.5

# ── Depth chart ───────────────────────────────────────────────────────────────
# Sleeper's depth_chart_order is a raw ordinal (1 = first team) that means a
# different thing per position — a #1 RB and a #1 WR both "start," but a #3 WR
# often still plays a full snap share in 3-WR sets while a #3 RB is a healthy
# scratch most weeks. This maps (position, depth_chart_order) -> role bucket.
# depth_chart_order values not covered by a position's ranges fall through to
# the highest-listed bucket (e.g. RB order 5 still hits "BENCH" via the 3+ rule
# below, handled in code as >= the last key rather than an exact match).
DEPTH_CHART_ROLE = {
    "QB":  {1: "STARTER", 2: "COMMITTEE"},           # 3+ -> BENCH
    "RB":  {1: "STARTER", 2: "COMMITTEE"},           # 3+ -> BENCH
    "WR":  {1: "STARTER", 2: "STARTER", 3: "STARTER", 4: "COMMITTEE"},  # 5+ -> BENCH
    "TE":  {1: "STARTER", 2: "COMMITTEE"},           # 3+ -> BENCH
    "K":   {1: "STARTER"},                            # else -> UNKNOWN
    "DST": {1: "STARTER"},                            # else -> UNKNOWN
}
# Position-specific "everything past the mapped keys" fallback. QB/RB/TE/WR
# fall through to BENCH (there IS a depth chart, the player is just deep on
# it); K/DST fall through to UNKNOWN (Sleeper rarely orders placekickers /
# team defenses meaningfully past 1, so absence of data beats a fake bucket).
DEPTH_CHART_OVERFLOW_ROLE = {
    "QB": "BENCH", "RB": "BENCH", "WR": "BENCH", "TE": "BENCH",
    "K": "UNKNOWN", "DST": "UNKNOWN",
}

# Team abbreviation mismatches between ESPN (used everywhere else in this
# pipeline) and Sleeper. Only entries that actually differ need to be listed;
# everything else matches byte-for-byte.
SLEEPER_TEAM_ALIASES = {
    "WAS": "WSH",   # Washington: Sleeper says WAS, ESPN says WSH
    "OAK": "LV",    # stale Raiders code that still shows up on old records
    "JAC": "JAX",
}

# ── Tiering ───────────────────────────────────────────────────────────────────
# See tier_agent.py's module docstring for the full rationale (this used to
# be a single global "median gap x multiplier" threshold, which a long
# sub-replacement tail deflated to near-zero, making min_tier_size --
# meant as a floor -- the real decider and producing uniform 2-player
# tiers). The current approach is a RELATIVE gap test scoped to the
# "relevant" (roughly positive-VOR) part of each position, computed
# pairwise so it adapts to gaps compressing toward the bottom of the
# position instead of comparing everything to one number.
TIERS = {
    # A tier break is declared when a gap exceeds this fraction of the
    # buffer-shifted VOR of the trailing player in the pair (see
    # tier_agent._relevant_count / shift). 0.10 = a 10%+ relative drop.
    "gap_relative_threshold": 0.10,
    # A gap at or above (gap_relative_threshold * hard_cliff_multiplier)
    # is a "hard" cliff: it always breaks the tier, even if that would
    # violate min_tier_size or leave a short leftover group. Prevents a
    # genuine cliff (e.g. a 30-point VOR gap) from ever being hidden
    # inside a tier just to satisfy the size floor below.
    "hard_cliff_multiplier": 1.5,
    # Floor on tier size: a borderline (non-hard-cliff) break is skipped
    # if it would leave the tier being closed, or the tier being opened,
    # smaller than this. Hard cliffs always override the floor.
    "min_tier_size": 2,
    # Once a position has this many tiers, adjacent tiers are merged
    # (starting at the smallest boundary gap) until the count fits. Raised
    # from 12 -> 20 alongside max_tier_spread_fraction below: capping the
    # spread of a tier legitimately produces MORE tiers in the draftable
    # range (that's the point -- a 45-point-wide 14-player tier was the
    # bug), so the old cap of 12 was already binding on RB/WR before the
    # spread constraint existed and would fight it afterward.
    "max_tiers_per_position": 20,
    # Maximum VOR spread allowed within a single tier, as a fraction of
    # the position's top VOR. The gap test alone only checks the space
    # BETWEEN neighbors -- a long run of small (sub-threshold) gaps can
    # still add up to a tier so wide that its members aren't actually
    # interchangeable (e.g. Achane at 127.8 sharing a tier with Jacobs at
    # 83.1 -- nobody drafting is indifferent between them). After the gap
    # test forms initial tiers, any tier whose spread exceeds this
    # fraction of the position's top VOR is recursively split at its own
    # largest internal gap until every resulting tier fits. Scaled by
    # top VOR for the same reason tail_buffer_fraction is: a fixed point
    # value would be huge for RB/WR and meaningless for K/DST.
    "max_tier_spread_fraction": 0.12,
    # Sub-replacement cutoff: players more than this fraction of the
    # position's TOP VOR below replacement (vor = 0) are "irrelevant" --
    # bucketed into one final tier instead of participating in the gap
    # math above, so their compressed near-zero gaps (there are hundreds
    # of them at every position) can't distort thresholds for the
    # draftable range. Scaled by the position's own top VOR rather than a
    # fixed point value so it means the same thing for RB/WR (huge VOR
    # spread) as it does for K/DST (tiny VOR spread).
    "tail_buffer_fraction": 0.15,
}
