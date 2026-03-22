"""
Pitcher Agent — fetches season pitching stats for probable starters.

Uses MLB Stats API for HR/9 and basic ratios (free, no key needed).
Falls back gracefully if a pitcher hasn't been announced yet.
"""

import asyncio
import logging

import aiohttp

from config import MLB_API_BASE, LEAGUE_AVG_HR9

logger = logging.getLogger(__name__)


async def fetch_pitcher_stats(
    session: aiohttp.ClientSession,
    pitcher_id: int,
    season: int,
) -> dict | None:
    """
    Pull a pitcher's season stats from the MLB Stats API.
    Returns a normalized stats dict or None.
    """
    url = (
        f"{MLB_API_BASE}/people/{pitcher_id}/stats"
        f"?stats=season"
        f"&group=pitching"
        f"&season={season}"
        f"&gameType=R"
    )
    async with session.get(url) as resp:
        if resp.status != 200:
            return None
        data = await resp.json()

    splits = (
        data.get("stats", [{}])[0]
            .get("splits", [])
    )
    if not splits:
        return None

    s = splits[0].get("stat", {})
    ip_str = s.get("inningsPitched", "0.0")
    ip = _parse_ip(ip_str)

    hr = int(s.get("homeRuns", 0))
    bb = int(s.get("baseOnBalls", 0))
    so = int(s.get("strikeOuts", 0))
    bf = int(s.get("battersFaced", 0))
    h  = int(s.get("hits", 0))
    era_str = s.get("era", "0.00")

    hr9 = round((hr * 9 / ip), 2) if ip > 0 else None
    bb9 = round((bb * 9 / ip), 2) if ip > 0 else None
    k9  = round((so * 9 / ip), 2) if ip > 0 else None
    era = float(era_str) if era_str else None

    return {
        "ip": ip,
        "hr": hr,
        "hr9": hr9,
        "bb9": bb9,
        "k9": k9,
        "era": era,
        "innings_pitched": ip_str,
    }


def _parse_ip(ip_str: str) -> float:
    """Convert '6.2' (6 full innings + 2 outs) to decimal innings."""
    try:
        parts = str(ip_str).split(".")
        full = int(parts[0])
        outs = int(parts[1]) if len(parts) > 1 else 0
        return full + outs / 3
    except (ValueError, IndexError):
        return 0.0


def pitcher_matchup_score(stats: dict | None) -> tuple[float, str]:
    """
    Score a pitcher matchup 0–100 for slugger HR opportunity.
    Higher = more favorable for the hitter.

    Returns (score, label).
    """
    if stats is None or stats.get("ip", 0) < 10:
        # Too few innings or unknown — neutral score
        return 50.0, "TBD"

    hr9 = stats.get("hr9")
    if hr9 is None:
        return 50.0, "TBD"

    # Base score from HR/9 relative to league average
    # League avg ~1.25 → score 50. Each 0.1 above avg → +5 pts (favor hitter).
    base = 50.0 + (hr9 - LEAGUE_AVG_HR9) * 50.0

    # ERA bonus: high ERA pitchers are softer matchups
    era = stats.get("era") or 4.00
    era_bonus = max(-10, min(10, (era - 4.00) * 3.0))
    base += era_bonus

    score = round(max(0, min(100, base)), 1)

    if score >= 70:
        label = "Favorable"
    elif score >= 45:
        label = "Neutral"
    else:
        label = "Tough"

    return score, label


async def enrich_player_pitchers(
    session: aiohttp.ClientSession,
    players: list[dict],
    season: int,
) -> list[dict]:
    """
    For each game with a known probable pitcher, fetch their stats
    and score the matchup. Attaches pitcher_score to each player.
    """
    # Collect all unique pitcher IDs across all games
    pitcher_ids: set[int] = set()
    for player in players:
        for game in player.get("games", []):
            pp = game.get("probable_pitcher")
            if pp and pp.get("id"):
                pitcher_ids.add(pp["id"])

    logger.info(f"Fetching stats for {len(pitcher_ids)} pitchers")

    # Fetch all pitcher stats concurrently
    tasks = {pid: fetch_pitcher_stats(session, pid, season) for pid in pitcher_ids}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    pitcher_stats: dict[int, dict | None] = {}
    for pid, result in zip(tasks.keys(), results):
        pitcher_stats[pid] = result if not isinstance(result, Exception) else None
        if isinstance(result, Exception):
            logger.warning(f"Error fetching pitcher {pid}: {result}")

    # Enrich games
    enriched_players = []
    for player in players:
        enriched_games = []
        matchup_scores = []

        for game in player.get("games", []):
            pp = game.get("probable_pitcher")
            stats = None
            score, label = 50.0, "TBD"

            if pp and pp.get("id"):
                stats = pitcher_stats.get(pp["id"])
                score, label = pitcher_matchup_score(stats)

            matchup_scores.append(score)
            enriched_games.append({
                **game,
                "pitcher_stats": stats,
                "pitcher_matchup_score": score,
                "pitcher_matchup_label": label,
            })

        avg_pitcher_score = (
            round(sum(matchup_scores) / len(matchup_scores), 1)
            if matchup_scores else 50.0
        )
        favorable_matchups = sum(1 for s in matchup_scores if s >= 65)

        enriched_players.append({
            **player,
            "games": enriched_games,
            "pitcher_score": avg_pitcher_score,
            "favorable_matchups": favorable_matchups,
        })
        logger.info(
            f"{player['name']}: avg pitcher score {avg_pitcher_score}, "
            f"{favorable_matchups} favorable matchups"
        )

    return enriched_players


async def run(players: list[dict], season: int) -> list[dict]:
    """Main entry point. Returns players enriched with pitcher matchup data."""
    async with aiohttp.ClientSession() as session:
        return await enrich_player_pitchers(session, players, season)
