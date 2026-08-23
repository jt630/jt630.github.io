"""
Beer Sheet — pre-draft fantasy football valuation board.

Runs the full pipeline:

  1. Sleeper Agent     -> league.json           exact scoring + roster
  2. Fetch Agent       -> espn_raw.json         900-player universe
  3. Projection Agent  -> projections.json      re-scored, blended projections
  4. Value Agent       -> values.json           replacement levels, VOR, auction $
  5. Risk Agent        -> risk.json             floor/ceiling bands
  6. Tier Agent        -> tiers.json            tier breaks
  7. Sheet Agent       -> board.json            <- Hugo reads this

Usage:
  python main.py --league-id 1361155919865454592     # full refresh
  python main.py --skip-fetch                        # reuse cached ESPN pull
  python main.py --username jt630                    # resolve league by user

Everything is stdlib. No pip install, no API key, nothing to break on draft day.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import SEASON, DATA_DIR, INTERMEDIATE_DIR, ROSTER, DEFAULT_ROSTER
import agents.fetch_agent as fetch_agent
import agents.sleeper_agent as sleeper_agent
import agents.projection_agent as projection_agent
import agents.depth_chart_agent as depth_chart_agent
import agents.value_agent as value_agent
import agents.risk_agent as risk_agent
import agents.tier_agent as tier_agent
import agents.sheet_agent as sheet_agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def _banner(text: str) -> None:
    logger.info("")
    logger.info("=" * 64)
    logger.info(text)
    logger.info("=" * 64)


def load_league(args) -> dict:
    """
    Resolve league settings. Sleeper is authoritative; a cached league.json is
    the fallback; a config preset is the last resort.
    """
    cached = DATA_DIR / "league.json"

    if args.league_id or args.username:
        _banner("SLEEPER AGENT — reading exact league settings")
        try:
            return sleeper_agent.run(args.username, args.league_id, args.season)
        except Exception as exc:
            logger.error("Sleeper lookup failed (%s)", exc)
            if not cached.exists():
                raise

    if cached.exists():
        league = json.loads(cached.read_text(encoding="utf-8"))
        logger.info("Using cached league settings: %s", league.get("league_name"))
        return league

    logger.warning("No league settings available — falling back to preset '%s'", DEFAULT_ROSTER)
    return {"roster": ROSTER[DEFAULT_ROSTER], "scoring": None}


def run_pipeline(args) -> dict:
    league = load_league(args)
    roster = league.get("roster") or ROSTER[DEFAULT_ROSTER]

    if args.skip_fetch and (INTERMEDIATE_DIR / "espn_raw.json").exists():
        logger.info("Skipping ESPN fetch — using cached espn_raw.json")
    else:
        _banner("FETCH AGENT — ESPN player universe")
        fetch_agent.run(args.season, args.max_players)

    _banner("PROJECTION AGENT — re-score to league rules, blend signals")
    projections = projection_agent.run(args.season, league)

    _banner("DEPTH CHART AGENT — roles, Sleeper injury detail, team tendency")
    try:
        depth = depth_chart_agent.run(projections, force_refresh=not args.skip_fetch)
    except Exception as exc:
        # A depth-chart failure must never cost us the board on draft day.
        logger.error("Depth chart stage failed (%s) — continuing without roles", exc)
        depth = {"players": {}, "team_tendency": {}}

    _banner("VALUE AGENT — replacement levels, VOR, auction values")
    values = value_agent.run(projections, roster)

    _banner("RISK AGENT — floor/ceiling bands")
    risk = risk_agent.run(projections)

    _banner("TIER AGENT — tier breaks")
    tiers = tier_agent.run(projections, values)

    _banner("SHEET AGENT — final board")
    board = sheet_agent.run(projections, values, risk, tiers, league, args.board_size, depth)

    return board


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Beer Sheet — fantasy football draft board")
    ap.add_argument("--league-id", help="Sleeper league ID (from the league URL)")
    ap.add_argument("--username", help="Sleeper username, if you'd rather not look up the ID")
    ap.add_argument("--season", type=int, default=SEASON)
    ap.add_argument("--skip-fetch", action="store_true",
                    help="Reuse the cached ESPN pull instead of re-downloading")
    ap.add_argument("--max-players", type=int, default=900,
                    help="Size of the ESPN player universe to pull")
    ap.add_argument("--board-size", type=int, default=sheet_agent.BOARD_SIZE,
                    help="How many players make the final sheet")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    board = run_pipeline(args)
    logger.info("")
    logger.info("Board ready: %d players, generated %s",
                board["board_size"], board["generated_at"])


if __name__ == "__main__":
    main()
