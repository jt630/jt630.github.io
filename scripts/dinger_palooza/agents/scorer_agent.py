"""
Scorer / Ranker Agent — combines all agent outputs into a final draft board.

Weights:
  Schedule  40%  (games played)
  Pitcher   35%  (matchup favorability)
  Weather   25%  (HR-friendly conditions)
"""

import logging
from datetime import date

from config import WEIGHTS

logger = logging.getLogger(__name__)


def build_reasoning(player: dict) -> str:
    """Generate a brief human-readable reasoning string for a player's rank."""
    parts = []
    games = player["games_this_week"]
    sched_score = player.get("schedule_score", 50)
    pitch_score = player.get("pitcher_score", 50)
    wx_score = player.get("weather_score", 50)

    # Schedule blurb
    if player.get("high_opportunity"):
        parts.append(f"{games} games this week (premium schedule)")
    else:
        parts.append(f"{games} games this week")

    # Pitcher blurb
    favorable = player.get("favorable_matchups", 0)
    if pitch_score >= 65:
        parts.append(f"{favorable} favorable pitcher matchup{'s' if favorable != 1 else ''}")
    elif pitch_score < 40:
        parts.append("tough pitching schedule")
    else:
        parts.append("neutral pitching schedule")

    # Weather blurb
    rain_risk = player.get("rain_risk_games", 0)
    if wx_score >= 70:
        wind_out_games = sum(
            1 for g in player.get("games", [])
            if g.get("weather", {}).get("wind_out")
        )
        if wind_out_games:
            parts.append(f"wind blowing out in {wind_out_games} game{'s' if wind_out_games != 1 else ''}")
        else:
            parts.append("clean weather forecast")
    elif rain_risk >= 2:
        parts.append(f"rain risk in {rain_risk} games")
    elif rain_risk == 1:
        parts.append("1 game with rain risk")
    else:
        parts.append("minimal weather concerns")

    return "; ".join(parts) + "."


def score_player(player: dict) -> dict:
    """Compute the weighted overall score for a player."""
    s = player.get("schedule_score", 50)
    p = player.get("pitcher_score", 50)
    w = player.get("weather_score", 50)

    overall = (
        s * WEIGHTS["schedule"]
        + p * WEIGHTS["pitcher"]
        + w * WEIGHTS["weather"]
    )

    return {
        **player,
        "overall_score": round(overall, 1),
        "reasoning": build_reasoning(player),
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
    """
    Final output structure consumed by the Hugo template.
    """
    ranked = rank_players(players)

    # Strip bulky per-game pitcher_stats from top-level output
    # (keep it in intermediate files, not the Hugo data file)
    clean = []
    for p in ranked:
        games_clean = []
        for g in p.get("games", []):
            games_clean.append({
                "date": g["date"],
                "home_away": g["home_away"],
                "opponent": g["opponent"],
                "venue": g.get("venue", ""),
                "probable_pitcher_name": (g.get("probable_pitcher") or {}).get("name", "TBD"),
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
            "weather_score": p.get("weather_score", 50),
            "games_this_week": p["games_this_week"],
            "high_opportunity": p.get("high_opportunity", False),
            "favorable_matchups": p.get("favorable_matchups", 0),
            "rain_risk_games": p.get("rain_risk_games", 0),
            "reasoning": p["reasoning"],
            "games": games_clean,
        })

    return {
        "generated_at": generated_at,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "weights": WEIGHTS,
        "players": clean,
    }
