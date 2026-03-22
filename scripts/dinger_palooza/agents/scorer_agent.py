"""
Scorer / Ranker Agent — combines all agent outputs into a final draft board.

Weights (updated to include park factor):
  Schedule     35%  (games played)
  Pitcher      30%  (matchup favorability)
  Park factor  20%  (stadium HR index)
  Weather      15%  (HR-friendly conditions)

Scoring system reminder (for reasoning labels):
  1st HR in a game  → 1 pt  (+1 if 3- or 4-run HR)
  2nd HR in a game  → 3 pts total (triangular bonus)
  3rd HR in a game  → 6 pts total
  Keep cost: weeks_held - 1 pts deducted per week you retain a player
"""

import logging
from datetime import date

from config import WEIGHTS, keep_cost

logger = logging.getLogger(__name__)


def build_reasoning(player: dict) -> str:
    """Generate a brief human-readable reasoning string for a player's rank."""
    parts = []
    games = player["games_this_week"]
    pitch_score = player.get("pitcher_score", 50)
    park_score = player.get("park_score", 50)
    wx_score = player.get("weather_score", 50)

    # Schedule blurb
    if player.get("high_opportunity"):
        parts.append(f"{games} games (premium schedule)")
    else:
        parts.append(f"{games} games")

    # Park factor blurb — highlight if notably good or bad
    best_park = player.get("best_park_game", "")
    best_pf = player.get("best_park_factor", 100)
    if park_score >= 65:
        note = f" incl. {best_park} (PF {best_pf})" if best_park and best_pf >= 110 else ""
        parts.append(f"hitter-friendly parks{note}")
    elif park_score < 40:
        parts.append("tough pitcher's parks")
    else:
        parts.append("neutral parks")

    # Pitcher blurb + platoon + multi-HR bonus callout
    favorable = player.get("favorable_matchups", 0)
    platoon_adv = player.get("platoon_advantages", 0)
    if pitch_score >= 65:
        platoon_str = f", {platoon_adv} platoon advantage{'s' if platoon_adv != 1 else ''}" if platoon_adv else ""
        parts.append(f"{favorable} favorable matchup{'s' if favorable != 1 else ''}{platoon_str} (multi-HR bonus potential)")
    elif pitch_score < 40:
        parts.append("tough pitching schedule")
    else:
        platoon_str = f", {platoon_adv} platoon advantage{'s' if platoon_adv != 1 else ''}" if platoon_adv else ""
        parts.append(f"neutral pitching schedule{platoon_str}")

    # Weather blurb
    rain_risk = player.get("rain_risk_games", 0)
    wind_out_games = sum(
        1 for g in player.get("games", [])
        if g.get("weather", {}).get("wind_out")
    )
    if wx_score >= 70:
        if wind_out_games:
            parts.append(f"wind out in {wind_out_games} game{'s' if wind_out_games != 1 else ''}")
        else:
            parts.append("clean weather")
    elif rain_risk >= 2:
        parts.append(f"rain risk in {rain_risk} games")
    elif rain_risk == 1:
        parts.append("1 game with rain risk")
    else:
        parts.append("clear skies")

    return "; ".join(parts) + "."


def score_player(player: dict) -> dict:
    """Compute the weighted overall score for a player."""
    s = player.get("schedule_score", 50)
    p = player.get("pitcher_score", 50)
    k = player.get("park_score", 50)
    w = player.get("weather_score", 50)

    overall = (
        s * WEIGHTS["schedule"]
        + p * WEIGHTS["pitcher"]
        + k * WEIGHTS["park"]
        + w * WEIGHTS["weather"]
    )

    return {
        **player,
        "overall_score": round(overall, 1),
        "reasoning": build_reasoning(player),
    }


def keep_recommendation(player: dict, weeks_held: int = 1) -> dict:
    """
    Given a player and how many weeks they've been held, compute keep cost
    and a simple keep/drop recommendation based on their draft score.
    """
    cost = keep_cost(weeks_held)
    # Rough break-even: expected points this week > keep cost
    # We use overall_score as a proxy for expected output (scaled to pts)
    # A score of 70+ ≈ likely to get 2+ HRs in the week
    expected_pts_proxy = round(player.get("overall_score", 50) / 25, 1)  # rough scale
    net = round(expected_pts_proxy - cost, 1)
    return {
        "weeks_held": weeks_held,
        "keep_cost_pts": cost,
        "expected_pts_proxy": expected_pts_proxy,
        "net_value": net,
        "recommendation": "KEEP" if net > 0 else "DROP",
    }


def rank_players(players: list[dict]) -> list[dict]:
    """Score all players, sort by overall_score descending, assign ranks."""
    scored = [score_player(p) for p in players]
    scored.sort(key=lambda p: p["overall_score"], reverse=True)
    for i, player in enumerate(scored, start=1):
        player["rank"] = i
    return scored


def build_draft_board(
    players: list[dict],
    week_start: date,
    week_end: date,
    generated_at: str,
) -> dict:
    """Final output structure consumed by the Hugo template."""
    ranked = rank_players(players)

    clean = []
    for p in ranked:
        games_clean = []
        for g in p.get("games", []):
            games_clean.append({
                "date": g["date"],
                "home_away": g["home_away"],
                "opponent": g["opponent"],
                "venue": g.get("venue", ""),
                "park_factor": g.get("park_factor", 100),
                "park_notes": g.get("park_notes", ""),
                "probable_pitcher_name": (g.get("probable_pitcher") or {}).get("name", "TBD"),
                "pitcher_hand": g.get("pitcher_hand"),
                "platoon_label": g.get("platoon_label", "neutral"),
                "platoon_delta": g.get("platoon_delta", 0.0),
                "pitcher_matchup_label": g.get("pitcher_matchup_label", "TBD"),
                "pitcher_matchup_score": g.get("pitcher_matchup_score", 50),
                "weather": g.get("weather", {}),
            })

        clean.append({
            "rank": p["rank"],
            "name": p["name"],
            "team": p["team"],
            "team_abbr": p["team_abbr"],
            "overall_score": p["overall_score"],
            "schedule_score": p.get("schedule_score", 50),
            "pitcher_score": p.get("pitcher_score", 50),
            "park_score": p.get("park_score", 50),
            "weather_score": p.get("weather_score", 50),
            "games_this_week": p["games_this_week"],
            "high_opportunity": p.get("high_opportunity", False),
            "favorable_matchups": p.get("favorable_matchups", 0),
            "platoon_advantages": p.get("platoon_advantages", 0),
            "rain_risk_games": p.get("rain_risk_games", 0),
            "best_park_game": p.get("best_park_game", ""),
            "best_park_factor": p.get("best_park_factor", 100),
            "reasoning": p["reasoning"],
            "games": games_clean,
        })

    return {
        "generated_at": generated_at,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "weights": WEIGHTS,
        "rules": {
            "roster_size": 5,
            "draft_day": "Sunday",
            "draft_order": "Traditional (not snake), lowest score picks first",
            "no_redraft_same_week": True,
            "scoring": {
                "hr_base": "1 pt per HR",
                "grand_slam_or_3run": "2 pts instead of 1",
                "multi_hr_same_game": "triangular bonus: 2nd HR in a game = 3 pts total; 3rd = 6 pts total",
                "formula": "nth HR in a game = n pts, so total = n*(n+1)/2"
            },
            "keep_cost": {
                "week_1": 0,
                "week_2": 1,
                "week_3": 2,
                "week_4": 3,
                "note": "Cost = weeks_held - 1. Deducted from your score."
            }
        },
        "players": clean,
    }
