"""
Dinger Palooza — Weekly MLB Home Run Draft Assistant
=====================================================

Runs a multi-agent pipeline:
  1. Schedule Agent  → counts games per player (40% weight)
  2. Weather Agent   → forecasts for each game (25% weight)
  3. Pitcher Agent   → matchup quality for each game (35% weight)
  4. Scorer Agent    → weighted rank, reasoning, final board

Outputs:
  data/dinger_palooza/draft_board.json          ← Hugo reads this
  data/dinger_palooza/intermediate/schedule.json
  data/dinger_palooza/intermediate/weather.json
  data/dinger_palooza/intermediate/pitcher.json

Usage:
  python main.py                    # uses next Monday–Sunday
  python main.py --week 2026-04-07  # start date of target week (Monday)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Allow running as a script from its own directory
sys.path.insert(0, str(Path(__file__).parent))

from config import get_target_week, OUTPUT_FILE, INTERMEDIATE_DIR
import agents.schedule_agent as schedule_agent
import agents.weather_agent as weather_agent
import agents.pitcher_agent as pitcher_agent
from agents.scorer_agent import build_draft_board

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def save_json(data: dict | list, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved → {path}")


async def run_pipeline(week_start: date, week_end: date) -> dict:
    season = week_start.year

    # ── 1. Schedule Agent ─────────────────────────────────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info(f"SCHEDULE AGENT  {week_start} → {week_end}")
    logger.info(f"{'='*60}")
    players = await schedule_agent.run(week_start, week_end)
    save_json(players, f"{INTERMEDIATE_DIR}/schedule.json")

    # ── 2. Weather + Pitcher agents run concurrently ──────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info(f"WEATHER + PITCHER AGENTS (parallel)")
    logger.info(f"{'='*60}")

    players_wx, players_p = await asyncio.gather(
        weather_agent.run(players),
        pitcher_agent.run(players, season),
    )
    save_json(players_wx, f"{INTERMEDIATE_DIR}/weather.json")
    save_json(players_p, f"{INTERMEDIATE_DIR}/pitcher.json")

    # ── 3. Merge weather + pitcher back onto players ───────────────────────────
    # Both agents return a player list in the same order; merge by player name.
    wx_map = {p["name"]: p for p in players_wx}
    p_map  = {p["name"]: p for p in players_p}

    merged = []
    for player in players:
        wx = wx_map.get(player["name"], {})
        pt = p_map.get(player["name"], {})
        merged.append({
            **player,
            # Weather fields
            "weather_score":  wx.get("weather_score",  50),
            "rain_risk_games": wx.get("rain_risk_games", 0),
            # Pitcher fields
            "pitcher_score":  pt.get("pitcher_score",  50),
            "favorable_matchups": pt.get("favorable_matchups", 0),
            # Merge per-game data (prefer pitcher-enriched games as base,
            # then layer in weather data by date)
            "games": _merge_games(
                player.get("games", []),
                wx.get("games", []),
                pt.get("games", []),
            ),
        })

    # ── 4. Scorer / Ranker Agent ──────────────────────────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info("SCORER AGENT")
    logger.info(f"{'='*60}")
    generated_at = datetime.now(timezone.utc).isoformat()
    draft_board = build_draft_board(merged, week_start, week_end, generated_at)
    save_json(draft_board, OUTPUT_FILE)

    return draft_board


def _merge_games(
    base_games: list[dict],
    wx_games: list[dict],
    pitch_games: list[dict],
) -> list[dict]:
    """
    Merge per-game weather and pitcher data back into the base game list.
    All three lists are in the same order (same games, same player).
    """
    wx_by_date  = {g["date"]: g for g in wx_games}
    pt_by_date  = {g["date"]: g for g in pitch_games}

    merged = []
    for game in base_games:
        d = game["date"]
        wx = wx_by_date.get(d, {})
        pt = pt_by_date.get(d, {})
        merged.append({
            **game,
            "weather":              wx.get("weather", {}),
            "weather_score":        wx.get("weather_score"),
            "pitcher_stats":        pt.get("pitcher_stats"),
            "pitcher_matchup_score": pt.get("pitcher_matchup_score", 50),
            "pitcher_matchup_label": pt.get("pitcher_matchup_label", "TBD"),
        })
    return merged


def print_board(draft_board: dict) -> None:
    """Pretty-print the final draft board to stdout."""
    print(f"\n{'🎯 DINGER PALOOZA DRAFT BOARD':^60}")
    print(f"{'Week of ' + draft_board['week_start'] + ' → ' + draft_board['week_end']:^60}")
    print("=" * 60)
    print(f"{'#':>3}  {'Player':<22} {'Score':>5}  {'Sched':>5}  {'Pitch':>5}  {'Wx':>5}  {'G':>2}")
    print("-" * 60)
    for p in draft_board["players"]:
        flags = ""
        if p["high_opportunity"]:
            flags += "🔥"
        if p["rain_risk_games"] >= 2:
            flags += "🌧"
        print(
            f"{p['rank']:>3}. {p['name']:<22} {p['overall_score']:>5.1f}"
            f"  {p['schedule_score']:>5.1f}  {p['pitcher_score']:>5.1f}"
            f"  {p['weather_score']:>5.1f}  {p['games_this_week']:>2} {flags}"
        )
        print(f"      └─ {p['reasoning']}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dinger Palooza draft assistant")
    parser.add_argument(
        "--week",
        type=str,
        default=None,
        help="Start date of target week as YYYY-MM-DD (must be a Monday). "
             "Defaults to next Monday.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.week:
        week_start = date.fromisoformat(args.week)
        if week_start.weekday() != 0:
            logger.warning(f"{args.week} is not a Monday — adjusting to nearest upcoming Monday")
            week_start += timedelta(days=(7 - week_start.weekday()) % 7)
        week_end = week_start + timedelta(days=6)
    else:
        week_start, week_end = get_target_week()

    logger.info(f"Target week: {week_start} → {week_end}")
    draft_board = asyncio.run(run_pipeline(week_start, week_end))
    print_board(draft_board)
    logger.info(f"\nDraft board saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
