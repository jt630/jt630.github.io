"""
Projection Agent — turns raw ESPN stat components into OUR league's points.

This is the stage that makes the sheet league-specific. ESPN hands us projected
stat COMPONENTS (pass yards, receptions, rushing TDs) rather than a finished
points total, so we re-score every player under the exact scoring read from
Sleeper. Change the league, change one dict, and every number downstream moves.

The projection itself is a HYBRID of three signals:

  espn_projection  (65%)  Forward-looking. Accounts for team changes, depth
                          chart moves and coaching that last year's box score
                          cannot know about.
  prior_actual     (20%)  Last season's real production, re-scored to our
                          rules. Anchors the model to proven usage and pulls
                          back projections that assume a leap.
  market_implied   (15%)  What the ADP crowd believes. Thousands of drafters
                          collectively price in beat-writer noise and camp
                          reports faster than any single projection source.

PRIOR-SEASON PRODUCTION IS RATE-BASED, NOT A SEASON TOTAL. A raw season point
total conflates two different things: how well a player produced per game,
and how many games he was healthy enough to play. Those are not the same
signal, and only the first one belongs in a forward-looking projection — a
player's per-game rate says something about his talent and role next season;
the games he missed to injury already happened and, barring a lingering
issue reflected in his current injury_status, tell us nothing about next
season. Blending the raw total in punishes an elite player a second time for
an injury that is already in the past: a back who was RB1-good for 10 games
and then tore an ACL ends up looking, by season total, like a mediocre
committee back, which is a strictly worse estimate of his 2026 per-game
value than just measuring the 10 healthy games. So `prior_points` (the raw
season total, kept for auditability) is converted to a per-game rate and
scaled back up to a full expected season (config.GAMES_PER_SEASON) before
it enters the blend, stored separately as `prior_points_scaled`. Games
played comes from ESPN raw stat component id "210" on the prior-season
actual entry — verified empirically against known players (iron men show
17, players with well-documented season-ending injuries show a low count
matching reported games missed; see the investigation in `run()`/git
history for the evidence).

A tiny sample is mostly noise, not signal — a player with 1-2 games played
has a per-game rate that swings wildly on small-sample variance, so
`config.PRIOR_SEASON_MIN_GAMES` gates whether the rate is trusted at all.
`has_usable_prior` records whether a player cleared that bar, and it is
what actually drives the blend redistribution below (NOT `is_rookie` —
those are different questions: `is_rookie` means "no NFL history", which
this module now infers from the presence of any prior-season stat entry at
all rather than from a zero point total. The old `prior_points <= 0.0`
definition wrongly called a healthy veteran a rookie whenever he missed a
full season to injury — Jonathon Brooks and Tank Dell, both several years
into their careers and both out all of last season on the same ACL, are
real examples in this data. `has_usable_prior` is the correct trigger for
redistribution because it also catches an established veteran who simply
didn't play enough last season to trust a rate from, which `is_rookie`
never could.

Players with no usable prior sample (rookies AND injury-shortened
veterans alike) have nothing reliable to regress toward, so their
prior_actual weight is redistributed onto the ESPN projection rather than
counted as zero — otherwise they would be systematically crushed by a
signal that isn't there.

Kickers and defenses are a different animal: their scoring is field-goal
distance and points-allowed tiers, which are not present in the offensive
component data. For those two positions we fall back to ESPN's own projected
total and mark the record so the sheet can show a lower confidence.

Output: data/beer_sheet/intermediate/projections.json  (see CONTRACT.md)
"""

import json
import logging
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    SEASON, DATA_DIR, INTERMEDIATE_DIR, STAT_MAP, POSITION_MAP,
    SCORING, DEFAULT_SCORING, BLEND, GAMES_PER_SEASON, PRIOR_SEASON_MIN_GAMES,
)

logger = logging.getLogger("projection_agent")

TEAMS_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
    "{season}?view=proTeamSchedules_wl"
)

# Positions we cannot rebuild from offensive stat components.
COMPONENT_BLIND = ("K", "DST")

UNDRAFTED_ADP = 999.0

# ESPN raw stat component id that carries games played on a season-actual
# entry. Verified empirically (not documented by ESPN): iron-man players
# (Christian McCaffrey, Ja'Marr Chase, Travis Kelce, Chase Brown — all
# played every game in 2025) show exactly 17 here, while players with
# well-documented season-altering injuries show a proportionally lower
# count (Tyreek Hill, ACL Week 4 2025: 4; Justice Hill, missed roughly
# half the season: 10; Chase Edmonds, active for almost none of it: 3).
# That gradient — full-season players clustering at 17, injured players
# landing at values matching their real games-missed counts — is what
# confirms id 210 is games played rather than some other counting stat.
GAMES_PLAYED_STAT_ID = "210"


# -- Team / bye lookup --------------------------------------------------------
def fetch_teams(season: int = SEASON) -> dict[int, dict]:
    req = urllib.request.Request(TEAMS_URL.format(season=season))
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    teams = payload.get("settings", {}).get("proTeams", [])
    return {
        t["id"]: {"abbrev": t.get("abbrev", "FA"), "bye": t.get("byeWeek", 0)}
        for t in teams
    }


# -- Scoring ------------------------------------------------------------------
def score_stats(stats: dict, scoring: dict, position: str,
                overrides: dict | None = None) -> float:
    """Apply a scoring dict to a raw ESPN stat-component map."""
    rates = dict(scoring)
    if overrides and position in overrides:
        rates.update(overrides[position])

    total = 0.0
    for stat_id, value in (stats or {}).items():
        name = STAT_MAP.get(str(stat_id))
        if name and name in rates:
            total += float(value) * rates[name]
    return round(total, 2)


def named_stats(stats: dict) -> dict:
    """Raw ESPN id-keyed stats -> human-readable names, for display."""
    return {
        STAT_MAP[str(k)]: round(float(v), 1)
        for k, v in (stats or {}).items()
        if str(k) in STAT_MAP
    }


# -- Stat entry selection -----------------------------------------------------
def _find(stats: list[dict], *, source: int, split: int,
          season: int, period: int | None = None) -> dict | None:
    for entry in stats or []:
        if (entry.get("statSourceId") == source
                and entry.get("statSplitTypeId") == split
                and entry.get("seasonId") == season
                and (period is None or entry.get("scoringPeriodId") == period)):
            return entry
    return None


def _weekly(stats: list[dict], season: int, scoring: dict,
            position: str, overrides: dict) -> list[float]:
    """Per-week projected points, index 0 = week 1. 0.0 for bye/unknown."""
    weeks = []
    for period in range(1, 19):
        entry = _find(stats, source=1, split=1, season=season, period=period)
        if entry is None:
            weeks.append(0.0)
            continue
        if position in COMPONENT_BLIND:
            weeks.append(round(float(entry.get("appliedTotal") or 0.0), 2))
        else:
            weeks.append(score_stats(entry.get("stats"), scoring, position, overrides))
    return weeks


def _games_played(prior_entry: dict | None) -> int:
    """Games played on the prior-season actual entry (see GAMES_PLAYED_STAT_ID)."""
    if not prior_entry:
        return 0
    raw = (prior_entry.get("stats") or {}).get(GAMES_PLAYED_STAT_ID)
    return int(float(raw)) if raw else 0


def _has_prior_history(stats: list[dict], prior_season: int) -> bool:
    """
    Best available "has NFL history" signal. ESPN's raw player payload has no
    years_exp/draft-year field, so we fall back to: did this player have ANY
    prior-season stat entry at all (regardless of source/split)? True 2026
    rookies have zero entries for seasonId 2025 in this dataset. Crucially,
    this is NOT the same test as "prior_points > 0" — an established veteran
    who missed the entire prior season to injury (Jonathon Brooks, Tank
    Dell) still has a prior-season entry recorded (with empty component
    stats), so this correctly does NOT call them rookies, unlike the old
    `prior_points <= 0.0` definition.
    """
    return any(e.get("seasonId") == prior_season for e in (stats or []))


def _expert_ranks(player: dict, rank_type: str = "PPR") -> list[int]:
    """Individual expert source ranks — the raw material for disagreement."""
    ranks = []
    for entries in (player.get("rankings") or {}).values():
        for entry in entries:
            if (entry.get("rankType") == rank_type
                    and entry.get("rankSourceId")      # 0 = the average, not a source
                    and entry.get("rank")):
                ranks.append(int(entry["rank"]))
    return ranks


# -- Main ---------------------------------------------------------------------
def run(season: int = SEASON, league: dict | None = None) -> dict:
    raw_path = INTERMEDIATE_DIR / "espn_raw.json"
    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    # League scoring is authoritative when present; presets are the fallback.
    if league is None:
        league_path = DATA_DIR / "league.json"
        league = json.loads(league_path.read_text(encoding="utf-8")) if league_path.exists() else {}

    scoring = league.get("scoring") or SCORING[DEFAULT_SCORING]
    overrides = league.get("position_scoring_override") or {}
    scoring_name = (f"sleeper:{league['league_id']}" if league.get("league_id")
                    else f"preset:{DEFAULT_SCORING}")
    logger.info("Scoring source: %s (reception = %s pts)",
                scoring_name, scoring.get("receptions"))

    teams = fetch_teams(season)
    prior_season = season - 1

    players: list[dict] = []
    for entry in raw["players"]:
        p = entry.get("player") or {}
        position = POSITION_MAP.get(p.get("defaultPositionId"))
        if not position:
            continue

        team = teams.get(p.get("proTeamId"), {"abbrev": "FA", "bye": 0})
        stats = p.get("stats") or []
        blind = position in COMPONENT_BLIND

        proj_entry = _find(stats, source=1, split=0, season=season)
        prior_entry = _find(stats, source=0, split=0, season=prior_season)

        if blind:
            espn_points = round(float((proj_entry or {}).get("appliedTotal") or 0.0), 2)
            prior_points = round(float((prior_entry or {}).get("appliedTotal") or 0.0), 2)
            proj_stats = {}
        else:
            espn_points = score_stats((proj_entry or {}).get("stats"), scoring, position, overrides)
            prior_points = score_stats((prior_entry or {}).get("stats"), scoring, position, overrides)
            proj_stats = named_stats((proj_entry or {}).get("stats"))

        # Rate-ize the prior season: total / games played * a full expected
        # season, so injury-shortened production is compared on the same
        # per-game basis as an iron-man's. See module docstring.
        prior_games_played = _games_played(prior_entry)
        has_usable_prior = prior_games_played >= PRIOR_SEASON_MIN_GAMES
        prior_points_scaled = (
            round(prior_points / prior_games_played * GAMES_PER_SEASON, 2)
            if prior_games_played > 0 else 0.0
        )
        is_rookie = not _has_prior_history(stats, prior_season)

        ownership = p.get("ownership") or {}
        adp = ownership.get("averageDraftPosition")
        adp = float(adp) if adp and float(adp) > 0 else UNDRAFTED_ADP

        players.append({
            "player_id": p.get("id"),
            "name": p.get("fullName", "Unknown"),
            "position": position,
            "team": team["abbrev"],
            "bye_week": team["bye"],
            "injury_status": p.get("injuryStatus", "ACTIVE"),
            "age": None,
            "espn_points": espn_points,
            "prior_points": prior_points,               # raw prior-season TOTAL, kept for audit
            "prior_points_scaled": prior_points_scaled,  # per-game rate scaled to a full season — blend input
            "prior_games_played": prior_games_played,
            "has_usable_prior": has_usable_prior,
            "market_points": 0.0,     # filled in second pass
            "proj_points": 0.0,       # filled in second pass
            "is_rookie": is_rookie,
            "component_blind": blind,
            "stats": proj_stats,
            "weekly_points": _weekly(stats, season, scoring, position, overrides),
            "adp": adp,
            "auction_value_market": round(float(ownership.get("auctionValueAverage") or 0.0), 2),
            "percent_owned": round(float(ownership.get("percentOwned") or 0.0), 1),
            "expert_ranks": _expert_ranks(p),
            "outlook": (p.get("seasonOutlook") or "")[:400],
        })

    _apply_market_implied(players)
    _blend(players)

    players.sort(key=lambda x: x["proj_points"], reverse=True)

    result = {
        "season": season,
        "scoring_name": scoring_name,
        "blend": BLEND,
        "count": len(players),
        "players": players,
    }

    out = INTERMEDIATE_DIR / "projections.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    _log_summary(players)
    logger.info("Saved %d players -> %s", len(players), out)
    return result


def _apply_market_implied(players: list[dict]) -> None:
    """
    Convert ADP into a points estimate — WITHIN each position.

    The market says a player is the Nth-best pick AT HIS POSITION (that is how
    drafters actually think: "he's my QB2", "third RB off the board"), so we
    ask a position-scoped question: what does the Nth-best player AT THAT
    POSITION actually score? That is the market's implied points for him — an
    opinion expressed in the same units as his own projection, which is the
    only way to blend the two.

    This MUST be done per-position rather than against one league-wide points
    curve. A single curve is dominated at the top by quarterbacks, who
    outscore every other position under standard scoring. Ranking a player by
    his overall ADP and reading off the league-wide curve at that index maps
    "drafted 22nd overall" to "22nd-highest scorer leaguewide" — which is
    almost always a QB, regardless of what position was actually drafted 22nd.
    A running back taken 22nd overall would then get assigned a QB-inflated
    market_points figure, making him look like the market disagrees wildly
    with his own (RB-scaled) projection, when the mismatch is really just an
    artifact of QBs sitting atop the raw points curve. Scoping the curve to
    the player's own position keeps market_points and espn_points/proj_points
    on the same positional scale, so any gap between them reflects genuine
    market opinion, not the shape of the position's scoring curve.
    """
    by_position: dict[str, list[dict]] = {}
    for player in players:
        by_position.setdefault(player["position"], []).append(player)

    for position, pos_players in by_position.items():
        points_curve = sorted(
            (p["espn_points"] for p in pos_players), reverse=True
        )
        if not points_curve:
            continue

        drafted = sorted(
            (p for p in pos_players if p["adp"] < UNDRAFTED_ADP),
            key=lambda p: p["adp"],
        )
        for market_rank, player in enumerate(drafted):
            # Short curves (K, DST, or any position with few drafted players)
            # simply clamp to the last available rank instead of indexing
            # past the end.
            idx = min(market_rank, len(points_curve) - 1)
            player["market_points"] = points_curve[idx]

    # Undrafted players get no market opinion; fall back to the ESPN projection.
    for player in players:
        if player["adp"] >= UNDRAFTED_ADP:
            player["market_points"] = player["espn_points"]


def _blend(players: list[dict]) -> None:
    for p in players:
        w = dict(BLEND)
        if not p["has_usable_prior"]:
            # Not enough prior-season sample to trust a rate — hand that
            # weight to the projection. Triggers on has_usable_prior, NOT
            # is_rookie: an injury-shortened veteran season needs the same
            # redistribution a rookie's blank slate does. See module docstring.
            w["espn_projection"] += w["prior_actual"]
            w["prior_actual"] = 0.0
        if p["component_blind"]:
            # K/DST: ESPN's total is all we have that respects distance/tier scoring.
            p["proj_points"] = p["espn_points"]
            continue

        p["proj_points"] = round(
            p["espn_points"] * w["espn_projection"]
            + p["prior_points_scaled"] * w["prior_actual"]
            + p["market_points"] * w["market_implied"],
            2,
        )


def _log_summary(players: list[dict]) -> None:
    counts = Counter(p["position"] for p in players)
    logger.info("Positions: %s", dict(sorted(counts.items())))
    logger.info("Top 12 by our blended projection:")
    for p in players[:12]:
        logger.info("  %-24s %-4s %-3s  proj %6.1f  (espn %6.1f  prior_scaled %6.1f [gp=%2d]  mkt %6.1f)  ADP %5.1f",
                    p["name"], p["team"], p["position"], p["proj_points"],
                    p["espn_points"], p["prior_points_scaled"], p["prior_games_played"],
                    p["market_points"], p["adp"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    run()
