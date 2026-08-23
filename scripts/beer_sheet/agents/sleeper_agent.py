"""
Sleeper Agent — reads the LEAGUE's exact scoring and roster settings.

Sleeper's read API is fully public: no API key, no OAuth, no credentials.
Given a username or a league_id we can pull the authoritative scoring settings
rather than assuming "full PPR" and hoping.

  /v1/user/{username}                      → user_id
  /v1/user/{user_id}/leagues/nfl/{season}  → the user's leagues
  /v1/league/{league_id}                   → scoring_settings + roster_positions

Output: data/beer_sheet/league.json  — becomes the source of truth for scoring,
consumed by projection_agent and value_agent in place of a config preset.
"""

import json
import logging
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import SEASON, DATA_DIR

logger = logging.getLogger("sleeper_agent")

API = "https://api.sleeper.app/v1"

# Sleeper slot name -> our canonical position name.
POSITION_ALIASES = {"DEF": "DST", "DST": "DST", "D/ST": "DST"}

# Sleeper scoring key → our internal stat name (from config.STAT_MAP).
# Sleeper uses a flat key space; only the keys we can project are mapped.
SLEEPER_SCORING_MAP = {
    "pass_yd":   "pass_yards",
    "pass_td":   "pass_tds",
    "pass_int":  "pass_interceptions",
    "pass_2pt":  "pass_2pt",
    "rush_yd":   "rush_yards",
    "rush_td":   "rush_tds",
    "rush_2pt":  "rush_2pt",
    "rec":       "receptions",
    "rec_yd":    "rec_yards",
    "rec_td":    "rec_tds",
    "rec_2pt":   "rec_2pt",
    "fum_lost":  "fumbles_lost",
    "fum":       "fumbles",
}

# Position-specific reception bonuses (TE premium and friends)
POSITION_BONUS_KEYS = {
    "bonus_rec_te": ("TE", "receptions"),
    "bonus_rec_rb": ("RB", "receptions"),
    "bonus_rec_wr": ("WR", "receptions"),
}


def _get(path: str):
    req = urllib.request.Request(f"{API}{path}")
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def resolve_league(username: str | None = None,
                   league_id: str | None = None,
                   season: int = SEASON) -> dict:
    """Return the raw Sleeper league object, from a league_id or a username."""
    if league_id:
        return _get(f"/league/{league_id}")

    if not username:
        raise ValueError("Provide either username or league_id")

    user = _get(f"/user/{username}")
    if not user:
        raise ValueError(f"Sleeper user '{username}' not found")
    leagues = _get(f"/user/{user['user_id']}/leagues/nfl/{season}")
    if not leagues:
        raise ValueError(f"No {season} NFL leagues found for '{username}'")

    if len(leagues) > 1:
        logger.warning("User is in %d leagues — using the first. Pass --league-id to pick:", len(leagues))
        for lg in leagues:
            logger.warning("   %s  %s (%s teams)", lg["league_id"], lg["name"], lg.get("total_rosters"))
    return leagues[0]


def parse_roster(league: dict) -> dict:
    """Turn Sleeper's roster_positions list into our ROSTER config shape."""
    slots = league.get("roster_positions", [])
    starters: dict[str, int] = {}
    flex = 0
    flex_eligible: tuple[str, ...] = ("RB", "WR", "TE")
    bench = 0

    for slot in slots:
        if slot == "BN":
            bench += 1
        elif slot in ("FLEX", "WRRB_FLEX", "REC_FLEX"):
            flex += 1
            if slot == "REC_FLEX":
                flex_eligible = ("WR", "TE")
            elif slot == "WRRB_FLEX":
                flex_eligible = ("RB", "WR")
        elif slot == "SUPER_FLEX":
            flex += 1
            flex_eligible = ("QB", "RB", "WR", "TE")
        elif slot in ("IR", "TAXI"):
            continue
        else:
            # Sleeper calls the defense slot DEF; ESPN calls it D/ST. Canonical = DST.
            slot = POSITION_ALIASES.get(slot, slot)
            starters[slot] = starters.get(slot, 0) + 1

    return {
        "teams": league.get("total_rosters", 12),
        "starters": starters,
        "flex": flex,
        "flex_eligible": flex_eligible,
        "bench": bench,
        "draft_type": (league.get("settings") or {}).get("type_label", "snake"),
        "auction_budget": (league.get("settings") or {}).get("budget", 200),
    }


def parse_scoring(league: dict) -> tuple[dict, dict, dict]:
    """
    Returns (scoring, position_overrides, unmapped).

    `unmapped` holds Sleeper scoring keys we can't project (IDP, special teams,
    distance-based kicking). Surfaced so we never silently ignore league rules.
    """
    raw = league.get("scoring_settings") or {}
    scoring: dict[str, float] = {}
    overrides: dict[str, dict[str, float]] = {}
    unmapped: dict[str, float] = {}

    for key, value in raw.items():
        if key in SLEEPER_SCORING_MAP:
            scoring[SLEEPER_SCORING_MAP[key]] = float(value)
        elif key in POSITION_BONUS_KEYS:
            pos, stat = POSITION_BONUS_KEYS[key]
            base = float(raw.get("rec", 0.0))
            # Only a real override; a 0.0 bonus just restates the base rate.
            if float(value) != 0.0:
                overrides.setdefault(pos, {})[stat] = base + float(value)
        elif float(value) != 0.0:
            unmapped[key] = float(value)

    return scoring, overrides, unmapped


def run(username: str | None = None,
        league_id: str | None = None,
        season: int = SEASON) -> dict:
    league = resolve_league(username, league_id, season)
    scoring, overrides, unmapped = parse_scoring(league)
    roster = parse_roster(league)

    result = {
        "source": "sleeper",
        "league_id": league.get("league_id"),
        "league_name": league.get("name"),
        "season": season,
        "teams": roster["teams"],
        "roster": roster,
        "scoring": scoring,
        "position_scoring_override": overrides,
        "unmapped_scoring_keys": unmapped,
        "raw_roster_positions": league.get("roster_positions", []),
    }

    out = DATA_DIR / "league.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info("League: %s (%s teams)", result["league_name"], result["teams"])
    logger.info("Starters: %s  flex=%s %s  bench=%s",
                roster["starters"], roster["flex"], roster["flex_eligible"], roster["bench"])
    logger.info("PPR value: %s", scoring.get("receptions"))
    if overrides:
        logger.info("Position overrides: %s", overrides)
    if unmapped:
        logger.warning("Unmapped scoring keys (not modeled): %s", sorted(unmapped))
    logger.info("Saved → %s", out)
    return result


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser(description="Read exact league settings from Sleeper")
    ap.add_argument("--username", help="Sleeper username")
    ap.add_argument("--league-id", help="Sleeper league ID (from the league URL)")
    ap.add_argument("--season", type=int, default=SEASON)
    args = ap.parse_args()
    run(args.username, args.league_id, args.season)
