"""
Pitcher Agent — fetches season pitching stats for probable starters
and applies platoon split adjustments for each batter.

Data sources (all free, MLB Stats API, no key needed):
  - Pitcher season stats:  /api/v1/people/{id}/stats?stats=season&group=pitching
  - Pitcher handedness:    /api/v1/people/{id}  →  pitchHand.code
  - Batter career splits:  /api/v1/people/{id}/stats?stats=career&group=hitting&sitCodes=vl,vr

Platoon logic:
  - Fetch batter's career HR rate vs. LHP and vs. RHP separately.
  - When the probable pitcher's hand is known, compute:
      platoon_ratio = hr_rate_vs_that_hand / hr_rate_overall
  - ratio > 1.15  →  platoon advantage  (+8 pts on matchup score)
  - ratio < 0.85  →  platoon disadvantage  (−8 pts on matchup score)
  - Switch hitters always bat opposite → treat as neutral (ratio = 1.0)
"""

import asyncio
import logging

import aiohttp

from config import MLB_API_BASE, LEAGUE_AVG_HR9

logger = logging.getLogger(__name__)


# ── Pitcher stats ─────────────────────────────────────────────────────────────

async def fetch_pitcher_stats(
    session: aiohttp.ClientSession,
    pitcher_id: int,
    season: int,
) -> dict | None:
    """Season pitching stats + throwing hand for a pitcher."""
    stats_url = (
        f"{MLB_API_BASE}/people/{pitcher_id}/stats"
        f"?stats=season&group=pitching&season={season}&gameType=R"
    )
    profile_url = f"{MLB_API_BASE}/people/{pitcher_id}"

    stats_resp, profile_resp = await asyncio.gather(
        session.get(stats_url),
        session.get(profile_url),
        return_exceptions=True,
    )

    # Throwing hand
    pitch_hand = None
    if not isinstance(profile_resp, Exception) and profile_resp.status == 200:
        profile_data = await profile_resp.json()
        pitch_hand = (
            profile_data.get("people", [{}])[0]
            .get("pitchHand", {})
            .get("code")  # "L" or "R"
        )

    # Season stats
    if isinstance(stats_resp, Exception) or stats_resp.status != 200:
        return {"pitch_hand": pitch_hand}

    data = await stats_resp.json()
    splits = data.get("stats", [{}])[0].get("splits", [])
    if not splits:
        return {"pitch_hand": pitch_hand}

    s = splits[0].get("stat", {})
    ip = _parse_ip(s.get("inningsPitched", "0.0"))
    hr = int(s.get("homeRuns", 0))
    era_str = s.get("era", "0.00")
    bb = int(s.get("baseOnBalls", 0))
    so = int(s.get("strikeOuts", 0))

    return {
        "pitch_hand": pitch_hand,
        "ip": ip,
        "hr": hr,
        "hr9": round(hr * 9 / ip, 2) if ip > 0 else None,
        "bb9": round(bb * 9 / ip, 2) if ip > 0 else None,
        "k9": round(so * 9 / ip, 2) if ip > 0 else None,
        "era": float(era_str) if era_str else None,
        "innings_pitched": s.get("inningsPitched", "0.0"),
    }


def _parse_ip(ip_str: str) -> float:
    try:
        parts = str(ip_str).split(".")
        return int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 3
    except (ValueError, IndexError):
        return 0.0


# ── Batter platoon splits ─────────────────────────────────────────────────────

async def fetch_batter_splits(
    session: aiohttp.ClientSession,
    batter_id: int,
) -> dict:
    """
    Career HR rate vs. LHP (sitCode=vl) and vs. RHP (sitCode=vr).
    Returns {"vl": hr_per_pa, "vr": hr_per_pa, "overall": hr_per_pa}
    """
    url = (
        f"{MLB_API_BASE}/people/{batter_id}/stats"
        f"?stats=career&group=hitting&sitCodes=vl,vr&gameType=R"
    )
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json()
    except Exception as e:
        logger.warning(f"Batter splits fetch failed for {batter_id}: {e}")
        return {}

    result = {}
    for stat_block in data.get("stats", []):
        for split in stat_block.get("splits", []):
            code = split.get("split", {}).get("code")  # "vl" or "vr"
            s = split.get("stat", {})
            hr = int(s.get("homeRuns", 0))
            pa = int(s.get("plateAppearances", 0))
            if code in ("vl", "vr") and pa > 0:
                result[code] = round(hr / pa, 4)

    # Overall = weighted average if both splits present
    if "vl" in result and "vr" in result:
        result["overall"] = round((result["vl"] + result["vr"]) / 2, 4)

    return result


def platoon_adjustment(
    batter_hand: str,
    pitcher_hand: str | None,
    batter_splits: dict,
) -> tuple[float, str]:
    """
    Returns (score_delta, label) based on the batter/pitcher handedness matchup.

    Platoon advantage:  LHH vs. RHP  or  RHH vs. LHP  (+8 pts)
    Platoon disadvantage: LHH vs. LHP  or  RHH vs. RHP  (−8 pts)
    Switch hitters: always neutral (0 pts)
    Unknown pitcher hand: 0 pts
    """
    if batter_hand == "S" or pitcher_hand is None:
        return 0.0, "neutral"

    # Determine which split applies
    # pitcher_hand "L" → batter faces lefty → use "vl" split
    split_key = "vl" if pitcher_hand == "L" else "vr"
    overall = batter_splits.get("overall")
    matchup_rate = batter_splits.get(split_key)

    if overall and matchup_rate and overall > 0:
        ratio = matchup_rate / overall
        if ratio >= 1.15:
            label = "platoon ✓"
            delta = min(12.0, (ratio - 1.0) * 40)   # cap at +12
        elif ratio <= 0.85:
            label = "platoon ✗"
            delta = max(-12.0, (ratio - 1.0) * 40)  # cap at −12
        else:
            label = "neutral"
            delta = 0.0
    else:
        # Fall back to generic rule when no split data available
        has_advantage = (batter_hand == "L" and pitcher_hand == "R") or \
                        (batter_hand == "R" and pitcher_hand == "L")
        label = "platoon ✓" if has_advantage else "platoon ✗"
        delta = 6.0 if has_advantage else -6.0

    return round(delta, 1), label


# ── Matchup scoring ───────────────────────────────────────────────────────────

def pitcher_matchup_score(
    stats: dict | None,
    platoon_delta: float = 0.0,
) -> tuple[float, str]:
    """
    Score a pitcher matchup 0–100 for HR opportunity (higher = better for hitter).
    Incorporates HR/9, ERA, and platoon adjustment.
    """
    if stats is None or stats.get("ip", 0) < 10:
        base = 50.0 + platoon_delta
        return round(max(0, min(100, base)), 1), "TBD"

    hr9 = stats.get("hr9")
    if hr9 is None:
        base = 50.0 + platoon_delta
        return round(max(0, min(100, base)), 1), "TBD"

    # Base from HR/9 vs. league average
    base = 50.0 + (hr9 - LEAGUE_AVG_HR9) * 50.0

    # ERA bonus
    era = stats.get("era") or 4.00
    base += max(-10, min(10, (era - 4.00) * 3.0))

    # Platoon adjustment
    base += platoon_delta

    score = round(max(0, min(100, base)), 1)
    if score >= 70:
        label = "Favorable"
    elif score >= 45:
        label = "Neutral"
    else:
        label = "Tough"

    return score, label


# ── Main enrichment ───────────────────────────────────────────────────────────

async def enrich_player_pitchers(
    session: aiohttp.ClientSession,
    players: list[dict],
    season: int,
) -> list[dict]:
    """
    Enriches each player's games with pitcher stats, pitcher hand,
    batter splits, and platoon-adjusted matchup scores.
    """
    # Collect unique pitcher IDs
    pitcher_ids: set[int] = set()
    for player in players:
        for game in player.get("games", []):
            pp = game.get("probable_pitcher")
            if pp and pp.get("id"):
                pitcher_ids.add(pp["id"])

    # Collect unique batter IDs (players who have been resolved)
    batter_ids: dict[str, int] = {
        p["name"]: p["mlb_id"]
        for p in players
        if p.get("mlb_id")
    }

    logger.info(
        f"Fetching stats for {len(pitcher_ids)} pitchers, "
        f"splits for {len(batter_ids)} batters"
    )

    # Fetch all pitcher stats + all batter splits concurrently
    pitcher_tasks = {pid: fetch_pitcher_stats(session, pid, season) for pid in pitcher_ids}
    batter_tasks  = {name: fetch_batter_splits(session, bid) for name, bid in batter_ids.items()}

    pitcher_results = await asyncio.gather(*pitcher_tasks.values(), return_exceptions=True)
    batter_results  = await asyncio.gather(*batter_tasks.values(),  return_exceptions=True)

    pitcher_stats: dict[int, dict | None] = {}
    for pid, result in zip(pitcher_tasks.keys(), pitcher_results):
        pitcher_stats[pid] = result if not isinstance(result, Exception) else None

    batter_splits: dict[str, dict] = {}
    for name, result in zip(batter_tasks.keys(), batter_results):
        batter_splits[name] = result if not isinstance(result, Exception) else {}

    # Enrich each player's games
    enriched_players = []
    for player in players:
        batter_hand = player.get("bats", "R")
        splits = batter_splits.get(player["name"], {})
        enriched_games = []
        matchup_scores = []

        for game in player.get("games", []):
            pp = game.get("probable_pitcher")
            stats = None
            pitch_hand = None
            platoon_delta, platoon_label = 0.0, "neutral"
            score, label = 50.0, "TBD"

            if pp and pp.get("id"):
                stats = pitcher_stats.get(pp["id"])
                pitch_hand = (stats or {}).get("pitch_hand")
                platoon_delta, platoon_label = platoon_adjustment(
                    batter_hand, pitch_hand, splits
                )
                score, label = pitcher_matchup_score(stats, platoon_delta)

            matchup_scores.append(score)
            enriched_games.append({
                **game,
                "pitcher_stats": stats,
                "pitcher_hand": pitch_hand,
                "platoon_label": platoon_label,
                "platoon_delta": platoon_delta,
                "pitcher_matchup_score": score,
                "pitcher_matchup_label": label,
            })

        avg_pitcher_score = (
            round(sum(matchup_scores) / len(matchup_scores), 1)
            if matchup_scores else 50.0
        )
        favorable_matchups = sum(1 for s in matchup_scores if s >= 65)
        platoon_advantages = sum(
            1 for g in enriched_games if g.get("platoon_label") == "platoon ✓"
        )

        enriched_players.append({
            **player,
            "games": enriched_games,
            "pitcher_score": avg_pitcher_score,
            "favorable_matchups": favorable_matchups,
            "platoon_advantages": platoon_advantages,
            "batter_splits": splits,
        })
        logger.info(
            f"{player['name']} ({batter_hand}): avg pitcher score {avg_pitcher_score}, "
            f"{favorable_matchups} favorable, {platoon_advantages} platoon advantages"
        )

    return enriched_players


async def run(players: list[dict], season: int) -> list[dict]:
    """Main entry point."""
    async with aiohttp.ClientSession() as session:
        return await enrich_player_pitchers(session, players, season)
