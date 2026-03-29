"""
Dinger Palooza — Results Checker
==================================
Fetches actual MLB game results for all picked players during a given week.

For each picked player:
  - Finds all games their team played (Regular Season only)
  - Checks play-by-play for home runs by that player
  - Flags multi-HR games (2X+) and 3-run / grand-slam HRs (3R/GS)
  - Computes points using the league scoring system from config.py

Outputs:
  data/dinger_palooza/results/week_NN.json   ← Hugo reads this
  data/dinger_palooza/standings.json         ← updated cumulative leaderboard

Usage:
  python check_results.py                          # current week (uses active picks file)
  python check_results.py --week 01                # week number
  python check_results.py --week 01 --picks picks/week_01.yaml
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import unicodedata
import yaml
from datetime import date, datetime, timezone
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).parent))
from config import MLB_API_BASE, hr_game_points

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("check_results")

DATA_DIR = "data/dinger_palooza"
PICKS_DIR = f"{DATA_DIR}/picks"
RESULTS_DIR = f"{DATA_DIR}/results"
STANDINGS_FILE = f"{DATA_DIR}/standings.json"

# MLB team abbreviation → team_id (MLB Stats API)
TEAM_ID_MAP = {
    "LAA": 108, "ARI": 109, "BAL": 110, "BOS": 111,
    "CHC": 112, "CIN": 113, "CLE": 114, "COL": 115,
    "DET": 116, "HOU": 117, "KC":  118, "LAD": 119,
    "WSH": 120, "NYM": 121, "ATH": 133, "PIT": 134,
    "SD":  135, "SEA": 136, "SF":  137, "STL": 138,
    "TB":  139, "TEX": 140, "TOR": 141, "MIN": 142,
    "PHI": 143, "ATL": 144, "CWS": 145, "MIA": 146,
    "NYY": 147, "MIL": 158,
}


# ── Player ID resolution ──────────────────────────────────────────────────────

def _clean_name(s: str) -> str:
    """Normalize a player name for fuzzy matching.
    Strips accents, punctuation, suffixes like Jr/Sr, and lowercases.
    """
    # Decompose unicode → strip accent marks (combining characters)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return (
        s.lower()
        .replace(".", "")
        .replace(",", "")
        .replace("'", "")
        .replace("'", "")
        .replace(" jr", "")
        .replace(" sr", "")
        .strip()
    )


async def resolve_player_id(
    session: aiohttp.ClientSession,
    player_name: str,
    team_id: int,
) -> int | None:
    """Look up MLB person ID via active roster for the given team."""
    url = f"{MLB_API_BASE}/teams/{team_id}/roster?rosterType=active&hydrate=person"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except Exception as e:
        logger.warning(f"Roster lookup failed (team {team_id}): {e}")
        return None

    target = _clean_name(player_name)
    for entry in data.get("roster", []):
        person = entry.get("person", {})
        full = _clean_name(person.get("fullName", ""))
        if target == full or target in full or full in target:
            pid = person.get("id")
            logger.info(f"Resolved '{player_name}' → MLB ID {pid}")
            return pid

    logger.warning(f"'{player_name}' not found on team {team_id} roster")
    return None


# ── Schedule / game fetching ──────────────────────────────────────────────────

async def fetch_player_game_log(
    session: aiohttp.ClientSession,
    mlb_id: int,
    start: str,
    end: str,
    season: int,
) -> list[dict]:
    """
    Fetch per-game hitting stats for a player using the game log endpoint.
    Returns only games that are Final, keyed with gamePk and homeRun/rbi counts.
    This is far lighter than fetching full play-by-play for every game.
    """
    url = (
        f"{MLB_API_BASE}/people/{mlb_id}/stats"
        f"?stats=gameLog&group=hitting&season={season}"
        f"&startDate={start}&endDate={end}&gameType=R"
    )
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except Exception as e:
        logger.warning(f"Game log fetch failed (player {mlb_id}): {e}")
        return []

    games = []
    for stat_group in data.get("stats", []):
        for split in stat_group.get("splits", []):
            stat = split.get("stat", {})
            game_info = split.get("game", {})
            games.append({
                "game_pk":  game_info.get("gamePk"),
                "date":     split.get("date", ""),
                "home_runs": int(stat.get("homeRuns", 0)),
                "rbi":       int(stat.get("rbi", 0)),
                "is_home":  split.get("isHome", True),
                "opponent": split.get("opponent", {}).get("name", ""),
            })
    return games


async def fetch_player_hrs_in_game(
    session: aiohttp.ClientSession,
    game_pk: int,
    mlb_id: int,
) -> list[dict]:
    """
    Fetch play-by-play for ONE game and extract only this player's HR plays.
    Called only when the game log already confirms the player hit at least one HR.
    """
    url = f"{MLB_API_BASE}/game/{game_pk}/playByPlay"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
    except Exception as e:
        logger.warning(f"Play-by-play fetch failed (game {game_pk}): {e}")
        return []

    hrs = []
    for play in data.get("allPlays", []):
        result = play.get("result", {})
        batter = play.get("matchup", {}).get("batter", {})
        if result.get("eventType") == "home_run" and batter.get("id") == mlb_id:
            hrs.append({
                "rbi":         result.get("rbi", 1),
                "inning":      play.get("about", {}).get("inning"),
                "description": result.get("description", ""),
            })
    return hrs


# ── Per-player results ────────────────────────────────────────────────────────

async def check_player_results(
    session: aiohttp.ClientSession,
    player: dict,
    week_start: str,
    week_end: str,
) -> dict:
    """
    For one picked player, find their HR production across the week.

    Optimized two-step approach:
      1. Fetch player game log (lightweight — just totals per game).
         Skip play-by-play entirely for games with 0 HRs.
      2. For games WITH HRs, fetch play-by-play to get per-HR RBI counts
         (needed to detect 3-run / grand-slam bonus).
    """
    mlb_id = player.get("mlb_id")
    team_id = player["team_id"]
    name = player["player"]
    season = int(str(week_start).split("-")[0])

    # Resolve MLB ID if not cached
    if not mlb_id:
        mlb_id = await resolve_player_id(session, name, team_id)
        player["mlb_id"] = mlb_id

    if not mlb_id:
        logger.warning(f"Skipping {name} — no MLB ID")
        return _empty_result(player)

    # Step 1: lightweight game log — HRs and RBIs per game
    game_log = await fetch_player_game_log(session, mlb_id, week_start, week_end, season)
    games_with_hrs = [g for g in game_log if g["home_runs"] > 0]
    total_games = len(game_log)

    logger.info(
        f"{name}: {total_games} games in log, "
        f"{len(games_with_hrs)} with HRs — "
        f"fetching play-by-play for {len(games_with_hrs)} game(s) only"
    )

    if not games_with_hrs:
        return _empty_result(player, games_checked=total_games)

    # Step 2: play-by-play only for games where a HR was hit
    pbp_tasks = [
        fetch_player_hrs_in_game(session, g["game_pk"], mlb_id)
        for g in games_with_hrs
    ]
    all_hr_details = await asyncio.gather(*pbp_tasks)

    # Process each HR game
    hr_games = []
    total_hrs = 0
    total_points = 0
    has_multi_hr_game = False
    has_3run_or_gs = False

    for game, hr_details in zip(games_with_hrs, all_hr_details):
        hr_count = game["home_runs"]

        # Fall back to game-log totals if play-by-play returned nothing
        # (edge case: game just finished, PBP not yet indexed)
        if not hr_details:
            run_values = [game["rbi"]] if hr_count == 1 else [1] * hr_count
        else:
            run_values = [h["rbi"] for h in hr_details]

        game_pts = hr_game_points(hr_count, run_values)
        total_hrs += hr_count
        total_points += game_pts

        if hr_count >= 2:
            has_multi_hr_game = True
        if any(r >= 3 for r in run_values):
            has_3run_or_gs = True

        hr_games.append({
            "date":        game["date"],
            "opponent":    game["opponent"],
            "home_away":   "home" if game["is_home"] else "away",
            "hrs_in_game": hr_count,
            "game_points": game_pts,
            "hr_details": [
                {
                    "inning":          h.get("inning"),
                    "rbi":             h["rbi"],
                    "is_3run_or_more": h["rbi"] >= 3,
                    "description":     h.get("description", ""),
                }
                for h in hr_details
            ] if hr_details else [{"rbi": rv, "is_3run_or_more": rv >= 3} for rv in run_values],
        })

    return {
        "player":         name,
        "team":           player["team"],
        "team_id":        team_id,
        "mlb_id":         mlb_id,
        "draft_pick":     player.get("draft_pick"),
        "proj_hr":        player.get("proj_hr"),
        "hrs":            total_hrs,
        "multi_hr_game":  has_multi_hr_game,
        "has_3run_or_gs": has_3run_or_gs,
        "points":         total_points,
        "hr_games":       hr_games,
        "games_checked":  total_games,
        "games_live":     0,   # game log only returns completed games
    }


def _empty_result(player: dict, games_checked: int = 0) -> dict:
    return {
        "player":         player["player"],
        "team":           player["team"],
        "team_id":        player["team_id"],
        "mlb_id":         player.get("mlb_id"),
        "draft_pick":     player.get("draft_pick"),
        "proj_hr":        player.get("proj_hr"),
        "hrs":            0,
        "multi_hr_game":  False,
        "has_3run_or_gs": False,
        "points":         0,
        "hr_games":       [],
        "games_checked":  games_checked,
        "games_live":     0,
    }


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_results_check(
    picks_data: dict,
    week_number: int,
) -> dict:
    week_start = picks_data["week_start"]
    week_end   = picks_data["week_end"]

    logger.info(f"Checking results: week {week_number} ({week_start} → {week_end})")

    async with aiohttp.ClientSession() as session:
        member_tasks = []
        for member in picks_data["members"]:
            picks = member["picks"]
            # Resolve all player IDs concurrently within the member
            player_tasks = [
                check_player_results(session, dict(p), week_start, week_end)
                for p in picks
            ]
            member_tasks.append((member["name"], player_tasks))

        # Gather all members concurrently
        all_member_futures = []
        member_names = []
        for member_name, tasks in member_tasks:
            member_names.append(member_name)
            all_member_futures.append(asyncio.gather(*tasks))

        all_results = await asyncio.gather(*all_member_futures)

    # Build output
    members_out = []
    for member_name, pick_results in zip(member_names, all_results):
        week_points = sum(r["points"] for r in pick_results)
        total_hrs   = sum(r["hrs"] for r in pick_results)
        members_out.append({
            "name":         member_name,
            "week_points":  week_points,
            "total_hrs":    total_hrs,
            "picks":        list(pick_results),
        })

    # Sort by points descending for display
    members_out.sort(key=lambda m: m["week_points"], reverse=True)

    # Determine if week is complete:
    #   - If today <= week_end, games remain → in_progress
    #   - If today > week_end AND no live games → final
    today = date.today()
    week_end_date = date.fromisoformat(str(week_end))
    any_live = any(
        r.get("games_live", 0) > 0
        for m in members_out
        for r in m["picks"]
    )
    if today <= week_end_date or any_live:
        status = "in_progress"
    else:
        status = "final"

    return {
        "week_number":   week_number,
        "week_start":    str(week_start),
        "week_end":      str(week_end),
        "checked_at":    datetime.now(timezone.utc).isoformat(),
        "source":        "mlb_api",
        "status":        status,
        "members":       members_out,
    }


def update_standings(results: dict) -> dict:
    """Load standings.json, upsert this week's points, re-rank, and save."""
    standings_path = STANDINGS_FILE
    os.makedirs(os.path.dirname(standings_path), exist_ok=True)

    if os.path.exists(standings_path):
        with open(standings_path) as f:
            standings = json.load(f)
    else:
        standings = {
            "season": date.today().year,
            "last_updated": "",
            "total_weeks": 0,
            "members": [],
        }

    # Build lookup
    week_idx = results["week_number"] - 1   # 0-based index
    member_map = {m["name"]: m for m in standings["members"]}

    for result_member in results["members"]:
        name = result_member["name"]
        pts  = result_member["week_points"]

        if name not in member_map:
            member_map[name] = {
                "name":          name,
                "total_points":  0,
                "rank":          0,
                "weekly_points": [],
            }

        entry = member_map[name]
        weekly = entry.setdefault("weekly_points", [])

        # Extend list if needed, fill gaps with 0
        while len(weekly) <= week_idx:
            weekly.append(0)

        # Update this week's points (overwrite on re-run)
        old_pts = weekly[week_idx]
        weekly[week_idx] = pts
        entry["total_points"] = entry.get("total_points", 0) - old_pts + pts

    # Re-rank
    member_list = sorted(member_map.values(), key=lambda m: m["total_points"], reverse=True)
    rank = 1
    for i, m in enumerate(member_list):
        if i > 0 and m["total_points"] < member_list[i - 1]["total_points"]:
            rank = i + 1
        m["rank"] = rank

    standings["members"]      = member_list
    standings["last_updated"] = datetime.now(timezone.utc).isoformat()
    standings["total_weeks"]  = max(standings.get("total_weeks", 0), results["week_number"])

    with open(standings_path, "w") as f:
        json.dump(standings, f, indent=2, default=str)
    logger.info(f"Standings updated → {standings_path}")

    return standings


def save_results(results: dict, week_number: int) -> str:
    path = f"{RESULTS_DIR}/week_{week_number:02d}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Results saved → {path}")
    return path


def load_picks(week_number: int, picks_override: str | None = None) -> dict:
    if picks_override:
        path = picks_override
    else:
        path = f"{PICKS_DIR}/week_{week_number:02d}.yaml"

    if not os.path.exists(path):
        raise FileNotFoundError(f"Picks file not found: {path}")

    with open(path) as f:
        return yaml.safe_load(f)


def print_results(results: dict) -> None:
    print(f"\n{'DINGER PALOOZA — WEEK ' + str(results['week_number']) + ' RESULTS':^60}")
    print(f"{results['week_start']} → {results['week_end']}  |  {results['status'].upper()}")
    print("=" * 60)
    print(f"{'Member':<12} {'Pts':>4}  {'HRs':>4}  Picks")
    print("-" * 60)
    for m in results["members"]:
        hr_players = [
            f"{p['player'].split()[-1]}({p['hrs']}HR"
            + ("/3R" if p["has_3run_or_gs"] else "")
            + ("/2X" if p["multi_hr_game"] else "")
            + ")"
            for p in m["picks"] if p["hrs"] > 0
        ]
        print(f"{m['name']:<12} {m['week_points']:>4}  {m['total_hrs']:>4}  {', '.join(hr_players) or '—'}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dinger Palooza results checker")
    parser.add_argument(
        "--week",
        type=int,
        default=None,
        help="Week number (e.g. 1). Defaults to current week from picks files.",
    )
    parser.add_argument(
        "--picks",
        type=str,
        default=None,
        help="Path to picks YAML file (overrides default location).",
    )
    parser.add_argument(
        "--no-standings-update",
        action="store_true",
        help="Skip updating standings.json (dry-run mode).",
    )
    return parser.parse_args()


def _latest_week_number() -> int:
    """Find the highest week number with an existing picks file."""
    picks_dir = Path(PICKS_DIR)
    if not picks_dir.exists():
        return 1
    files = sorted(picks_dir.glob("week_*.yaml"))
    if not files:
        return 1
    # Extract number from filename: week_01.yaml → 1
    return int(files[-1].stem.split("_")[1])


def main() -> None:
    args = parse_args()

    week_num = args.week or _latest_week_number()
    picks = load_picks(week_num, args.picks)

    results = asyncio.run(run_results_check(picks, week_num))

    save_results(results, week_num)

    if not args.no_standings_update:
        update_standings(results)

    print_results(results)
    logger.info("Done.")


if __name__ == "__main__":
    main()
