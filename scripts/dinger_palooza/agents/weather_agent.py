"""
Weather Agent — fetches 5-day forecasts for each game's stadium city.

Uses OpenWeatherMap free tier (5-day / 3-hour forecast).
API key required: set OWM_API_KEY env var.
"""

import asyncio
import logging
from datetime import date, datetime, timezone

import aiohttp

from config import OWM_API_BASE, OWM_API_KEY, STADIUM_LOCATIONS, RAIN_RISK_PCT, WIND_OUT_SPEED_MPH

logger = logging.getLogger(__name__)

# Wind directions considered "out to center/left-center" (HR-friendly at most parks)
# Roughly: S, SW, SSW, WSW — depends on park orientation but this is a good proxy
WIND_OUT_BEARINGS = range(135, 270)  # degrees: SE through W


async def fetch_forecast(
    session: aiohttp.ClientSession,
    owm_q: str,
) -> list[dict] | None:
    """
    Fetch 5-day / 3-hour forecast for a city query string (e.g. 'Seattle,US').
    Returns list of 3-hour forecast blocks, or None on error.
    """
    if not OWM_API_KEY:
        logger.error("OWM_API_KEY not set — weather data unavailable")
        return None

    url = (
        f"{OWM_API_BASE}/forecast"
        f"?q={owm_q}"
        f"&appid={OWM_API_KEY}"
        f"&units=imperial"  # Fahrenheit, mph
        f"&cnt=40"          # up to 5 days × 8 blocks/day
    )
    async with session.get(url) as resp:
        if resp.status != 200:
            text = await resp.text()
            logger.warning(f"OWM {owm_q}: HTTP {resp.status} — {text[:100]}")
            return None
        return (await resp.json()).get("list", [])


def blocks_for_date(forecast_blocks: list[dict], target_date: str) -> list[dict]:
    """Filter forecast blocks to those on the given date (YYYY-MM-DD)."""
    return [
        b for b in forecast_blocks
        if b.get("dt_txt", "").startswith(target_date)
    ]


def summarize_game_weather(blocks: list[dict]) -> dict:
    """
    Summarize weather for a game day from its forecast blocks.
    Returns a dict with rain_pct, temp_f, wind_mph, wind_deg, wind_out, rain_risk.
    """
    if not blocks:
        return {
            "rain_pct": None,
            "temp_f": None,
            "wind_mph": None,
            "wind_deg": None,
            "wind_out": False,
            "rain_risk": False,
            "conditions": "Unknown",
        }

    # Rain %: max pop (probability of precipitation) across blocks, as integer pct
    rain_pct = round(max(b.get("pop", 0) for b in blocks) * 100)

    # Temperature: average during game-time blocks (noon–9pm local ≈ 12:00–21:00 UTC-ish)
    # Use mid-day blocks if available, else all blocks
    midday = [b for b in blocks if "12:00" in b.get("dt_txt", "") or "15:00" in b.get("dt_txt", "")]
    temp_blocks = midday if midday else blocks
    temp_f = round(sum(b["main"]["temp"] for b in temp_blocks) / len(temp_blocks), 1)

    # Wind: use worst-case (highest wind speed block during game time)
    wind_block = max(temp_blocks, key=lambda b: b.get("wind", {}).get("speed", 0))
    wind_mph = round(wind_block.get("wind", {}).get("speed", 0), 1)
    wind_deg = wind_block.get("wind", {}).get("deg", 0)

    # "Wind out" = wind blowing toward OF at good speed (rough approximation)
    wind_out = (
        wind_mph >= WIND_OUT_SPEED_MPH
        and wind_deg in WIND_OUT_BEARINGS
    )

    # Dominant condition label
    conditions = blocks[0].get("weather", [{}])[0].get("main", "Unknown")

    return {
        "rain_pct": rain_pct,
        "temp_f": temp_f,
        "wind_mph": wind_mph,
        "wind_deg": wind_deg,
        "wind_out": wind_out,
        "rain_risk": rain_pct >= RAIN_RISK_PCT,
        "conditions": conditions,
    }


def weather_score(game_weather: dict) -> float:
    """
    Score a single game 0–100 for HR-friendliness based on weather.
    - Rain risk: big penalty
    - Wind out: bonus
    - Temperature: warmer = slight bonus (ball carries better)
    """
    if game_weather["rain_pct"] is None:
        return 50.0  # neutral if unknown

    score = 100.0

    # Rain penalty: 0% = no penalty, 60% = -40 pts, 100% = -70 pts
    rain_pct = game_weather["rain_pct"]
    if rain_pct >= RAIN_RISK_PCT:
        score -= 40 + (rain_pct - RAIN_RISK_PCT) * 0.75
    else:
        score -= rain_pct * 0.3

    # Wind out bonus
    if game_weather["wind_out"]:
        score += min(15, game_weather["wind_mph"] * 1.0)

    # Temperature: baseline 70°F; bonus up to +5 at 90°F, penalty down to -5 at 40°F
    temp = game_weather.get("temp_f") or 70
    score += max(-5, min(5, (temp - 70) * 0.25))

    return round(max(0, min(100, score)), 1)


async def enrich_player_weather(
    session: aiohttp.ClientSession,
    players: list[dict],
) -> list[dict]:
    """
    For each player's games, attach weather data.
    Fetches one forecast per unique city (not per game).
    """
    # Collect unique cities needed
    city_set: dict[str, str] = {}  # team_id → owm_q
    for player in players:
        tid = player["team_id"]
        loc = STADIUM_LOCATIONS.get(tid)
        if loc:
            city_set[tid] = loc["owm_q"]
        # Also check opponent cities
        for game in player.get("games", []):
            opp_tid = game.get("opponent_team_id")
            if opp_tid and opp_tid not in city_set:
                opp_loc = STADIUM_LOCATIONS.get(opp_tid)
                if opp_loc:
                    city_set[opp_tid] = opp_loc["owm_q"]

    # Fetch all forecasts concurrently
    logger.info(f"Fetching weather for {len(city_set)} cities")
    tasks = {tid: fetch_forecast(session, q) for tid, q in city_set.items()}
    forecasts: dict[int, list[dict] | None] = {}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for tid, result in zip(tasks.keys(), results):
        forecasts[tid] = result if not isinstance(result, Exception) else None

    # Enrich each player's games with weather
    enriched_players = []
    for player in players:
        enriched_games = []
        game_scores = []

        for game in player.get("games", []):
            # Weather is at the home team's stadium
            home_tid = (
                player["team_id"] if game["home_away"] == "home"
                else game.get("opponent_team_id")
            )
            forecast = forecasts.get(home_tid) or []
            blocks = blocks_for_date(forecast, game["date"])
            wx = summarize_game_weather(blocks)
            gs = weather_score(wx)
            game_scores.append(gs)
            enriched_games.append({**game, "weather": wx, "weather_score": gs})

        avg_wx_score = round(sum(game_scores) / len(game_scores), 1) if game_scores else 50.0
        rain_risk_games = sum(1 for g in enriched_games if g["weather"].get("rain_risk"))

        enriched_players.append({
            **player,
            "games": enriched_games,
            "weather_score": avg_wx_score,
            "rain_risk_games": rain_risk_games,
        })
        logger.info(f"{player['name']}: avg weather score {avg_wx_score}, rain risk in {rain_risk_games} games")

    return enriched_players


async def run(players: list[dict]) -> list[dict]:
    """Main entry point. Returns players enriched with weather data."""
    async with aiohttp.ClientSession() as session:
        return await enrich_player_weather(session, players)
