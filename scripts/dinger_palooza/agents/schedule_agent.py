"""
Schedule Agent — pulls weekly MLB game schedules and counts games per player.

MLB Stats API is free and requires no key.
Endpoint: GET /api/v1/schedule?sportId=1&startDate=...&endDate=...&hydrate=team,probablePitcher
"""

import asyncio
import json
import logging
from datetime import date

import aiohttp

from config import MLB_API_BASE, PLAYERS, HIGH_OPPORTUNITY_GAMES, PARK_FACTORS, park_factor_score

logger = logging.getLogger(__name__)


async def fetch_schedule(
    session: aiohttp.ClientSession,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch all MLB games in the given date range."""
    url = (
        f"{MLB_API_BASE}/schedule"
        f"?sportId=1"
        f"&startDate={start_date.isoformat()}"
        f"&endDate={end_date.isoformat()}"
        f"&hydrate=team,probablePitcher(note)"
        f"&gameType=R"  # regular season only
    )
    logger.info(f"Fetching schedule {start_date} → {end_date}")
    async with session.get(url) as resp:
        resp.raise_for_status()
        data = await resp.json()

    games = []
    for day_entry in data.get("dates", []):
        for game in day_entry.get("games", []):
            games.append({
                "game_pk": game["gamePk"],
                "date": day_entry["date"],
                "home_team_id": game["teams"]["home"]["team"]["id"],
                "home_team_name": game["teams"]["home"]["team"]["name"],
                "away_team_id": game["teams"]["away"]["team"]["id"],
                "away_team_name": game["teams"]["away"]["team"]["name"],
                "home_pitcher": _extract_pitcher(game["teams"]["home"]),
                "away_pitcher": _extract_pitcher(game["teams"]["away"]),
                "venue": game.get("venue", {}).get("name", ""),
                "status": game.get("status", {}).get("detailedState", ""),
            })
    logger.info(f"Found {len(games)} games")
    return games


def _extract_pitcher(team_data: dict) -> dict | None:
    """Extract probable pitcher info from a team game entry."""
    pitcher = team_data.get("probablePitcher")
    if not pitcher:
        return None
    return {
        "id": pitcher.get("id"),
        "name": pitcher.get("fullName", "TBD"),
        "note": pitcher.get("note", ""),
    }


async def resolve_player_ids(
    session: aiohttp.ClientSession,
    players: list[dict],
) -> list[dict]:
    """
    Look up each player's MLB person ID and verify their current team.
    Uses name search so the lookup works even if the player changed teams.
    Updates team_id/team/team_abbr in-place when a mismatch is detected.
    """
    tasks = [_lookup_player(session, p) for p in players]
    resolved = await asyncio.gather(*tasks, return_exceptions=True)

    enriched = []
    for player, result in zip(players, resolved):
        if isinstance(result, Exception):
            logger.warning(f"Could not resolve ID for {player['name']}: {result}")
            enriched.append({**player, "team_stale": False})
        else:
            updates = result or {}
            merged = {**player, **updates}
            # Flag if the live team differs from config so the UI can warn
            merged["team_stale"] = (
                "team_id" in updates and updates["team_id"] != player["team_id"]
            )
            if merged["team_stale"]:
                logger.warning(
                    f"STALE CONFIG: {player['name']} is no longer on "
                    f"{player['team']} — now on {merged['team']} ({merged['team_abbr']}). "
                    f"Update config.py team_id for this player."
                )
            enriched.append(merged)
    return enriched


async def _lookup_player(session: aiohttp.ClientSession, player: dict) -> dict:
    """
    Look up a player via MLB people search (team-agnostic).
    Returns a dict of fields to merge into the player: mlb_id, and optionally
    team_id / team / team_abbr if the player's current team differs from config.

    Falls back to the original roster-based lookup if name search yields nothing.
    """
    name_encoded = player["name"].replace(" ", "+")
    url = f"{MLB_API_BASE}/people/search?names={name_encoded}&sportId=1"

    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()
        people = data.get("people", [])
    except Exception as exc:
        logger.debug(f"Name search failed for {player['name']}: {exc} — falling back to roster")
        people = []

    if people:
        target = player["name"].lower()
        for person in people:
            full_name = person.get("fullName", "").lower()
            if target in full_name or full_name in target or _name_match(target, full_name):
                mlb_id = person.get("id")
                current_team = person.get("currentTeam", {})
                current_team_id = current_team.get("id")
                current_team_name = current_team.get("name", player["team"])
                current_team_abbr = current_team.get("abbreviation", player["team_abbr"])

                result = {"mlb_id": mlb_id}
                if current_team_id and current_team_id != player["team_id"]:
                    result["team_id"] = current_team_id
                    result["team"] = current_team_name
                    result["team_abbr"] = current_team_abbr

                logger.info(f"Resolved {player['name']} → MLB ID {mlb_id} ({current_team_name})")
                return result

    # Fallback: search the configured team's roster (original behavior)
    logger.debug(f"Name search found no match for {player['name']} — trying {player['team']} roster")
    return await _lookup_player_via_roster(session, player)


async def _lookup_player_via_roster(session: aiohttp.ClientSession, player: dict) -> dict:
    """Fallback: fetch the configured team's active roster and match by name."""
    url = (
        f"{MLB_API_BASE}/teams/{player['team_id']}/roster"
        f"?rosterType=active"
        f"&hydrate=person"
    )
    async with session.get(url) as resp:
        resp.raise_for_status()
        data = await resp.json()

    target = player["name"].lower()
    for entry in data.get("roster", []):
        person = entry.get("person", {})
        full_name = person.get("fullName", "").lower()
        if target in full_name or full_name in target or _name_match(target, full_name):
            pid = person.get("id")
            logger.info(f"Resolved {player['name']} → MLB ID {pid} (via roster fallback)")
            return {"mlb_id": pid}

    logger.warning(
        f"Player '{player['name']}' not found on {player['team']} roster. "
        f"They may have been traded — update team_id in config.py."
    )
    return {"mlb_id": None}


def _name_match(a: str, b: str) -> bool:
    """Fuzzy-ish name match ignoring punctuation/suffixes."""
    def clean(s):
        return s.replace(".", "").replace(",", "").replace(" jr", "").replace(" sr", "").strip()
    return clean(a) == clean(b)


def build_player_schedule(players: list[dict], games: list[dict]) -> list[dict]:
    """
    For each player, collect all games their team plays and summarize the week.
    Returns player dicts enriched with schedule data.
    """
    results = []
    for player in players:
        team_id = player["team_id"]
        player_games = [
            g for g in games
            if g["home_team_id"] == team_id or g["away_team_id"] == team_id
        ]

        game_summaries = []
        for g in player_games:
            is_home = g["home_team_id"] == team_id
            opp_team = g["away_team_name"] if is_home else g["home_team_name"]
            opp_team_id = g["away_team_id"] if is_home else g["home_team_id"]
            probable_pitcher = g["away_pitcher"] if is_home else g["home_pitcher"]

            home_team_id = g["home_team_id"]
            pf_data = PARK_FACTORS.get(home_team_id, {})
            game_summaries.append({
                "game_pk": g["game_pk"],
                "date": g["date"],
                "home_away": "home" if is_home else "away",
                "opponent": opp_team,
                "opponent_team_id": opp_team_id,
                "venue": g["venue"],
                "probable_pitcher": probable_pitcher,
                "park_factor": pf_data.get("hr_factor", 100),
                "park_factor_score": park_factor_score(home_team_id),
                "park_notes": pf_data.get("notes", ""),
            })

        game_count = len(game_summaries)
        avg_park_score = (
            round(sum(g["park_factor_score"] for g in game_summaries) / game_count, 1)
            if game_count else 50.0
        )
        best_park = max(game_summaries, key=lambda g: g["park_factor"], default={})
        results.append({
            **player,
            "games_this_week": game_count,
            "high_opportunity": game_count >= HIGH_OPPORTUNITY_GAMES,
            "games": game_summaries,
            # Raw schedule score 0–100 (scales with games, maxes at 7)
            "schedule_score": min(100, round((game_count / 7) * 100)),
            "park_score": avg_park_score,
            "best_park_game": best_park.get("venue", ""),
            "best_park_factor": best_park.get("park_factor", 100),
        })
        logger.info(
            f"{player['name']}: {game_count} games, avg park score {avg_park_score} "
            f"{'🔥 HIGH OPP' if game_count >= HIGH_OPPORTUNITY_GAMES else ''}"
        )

    # Sort by games descending for the intermediate output
    results.sort(key=lambda p: p["games_this_week"], reverse=True)
    return results


async def run(start_date: date, end_date: date) -> list[dict]:
    """
    Main entry point. Returns list of players enriched with schedule data.
    """
    async with aiohttp.ClientSession() as session:
        # Resolve MLB IDs and fetch schedule concurrently
        players_task = resolve_player_ids(session, PLAYERS)
        games_task = fetch_schedule(session, start_date, end_date)

        players, games = await asyncio.gather(players_task, games_task)

    result = build_player_schedule(players, games)
    return result


if __name__ == "__main__":
    from config import get_target_week
    logging.basicConfig(level=logging.INFO)
    start, end = get_target_week()
    data = asyncio.run(run(start, end))
    print(json.dumps(data, indent=2, default=str))
