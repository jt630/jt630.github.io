"""
Fetch Agent — pulls the raw player universe from ESPN's fantasy API.

Uses stdlib urllib ONLY. No pip install should ever be required to run the
sheet on draft day.

ESPN's `kona_player_info` view returns, per player:
  - stats[]  statSourceId=1, statSplitTypeId=0  → season PROJECTIONS as raw
             stat components (this is what lets us re-score any ruleset)
  - stats[]  statSourceId=0, prior season       → last year's ACTUALS
  - stats[]  statSplitTypeId=1                  → weekly projections
  - ownership.averageDraftPosition / auctionValueAverage → the market
  - rankings{}                                  → 8 expert sources, for disagreement
  - draftRanksByRankType                        → PPR / STANDARD / SUPERFLEX

Output: data/beer_sheet/intermediate/espn_raw.json
"""

import json
import logging
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import SEASON, INTERMEDIATE_DIR

logger = logging.getLogger("fetch_agent")

BASE_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
    "{season}/segments/0/leaguedefaults/3?view=kona_player_info"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}

PAGE_SIZE = 300


def _filter_header(limit: int, offset: int) -> str:
    """Build the x-fantasy-filter header ESPN uses for paging and sorting."""
    return json.dumps({
        "players": {
            "limit": limit,
            "offset": offset,
            "sortDraftRanks": {
                "sortPriority": 100,
                "sortAsc": True,
                "value": "PPR",
            },
        }
    })


def _get(season: int, limit: int, offset: int) -> list[dict]:
    req = urllib.request.Request(BASE_URL.format(season=season))
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header("x-fantasy-filter", _filter_header(limit, offset))
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    return payload.get("players", [])


def run(season: int = SEASON, max_players: int = 900) -> list[dict]:
    """Page through the player universe, ordered by PPR draft rank."""
    collected: list[dict] = []
    seen: set[int] = set()

    for offset in range(0, max_players, PAGE_SIZE):
        try:
            page = _get(season, PAGE_SIZE, offset)
        except urllib.error.HTTPError as exc:
            logger.error("ESPN returned HTTP %s at offset %s", exc.code, offset)
            break
        if not page:
            logger.info("No more players at offset %s — stopping", offset)
            break

        new = 0
        for entry in page:
            pid = entry.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            collected.append(entry)
            new += 1

        logger.info("offset %-4d → %d players (%d new, %d total)",
                    offset, len(page), new, len(collected))

        # ESPN silently repeats the first page when offset runs past the end.
        if new == 0:
            break

    out = INTERMEDIATE_DIR / "espn_raw.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"season": season, "count": len(collected), "players": collected}, f)
    logger.info("Saved %d players → %s", len(collected), out)
    return collected


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    run()
