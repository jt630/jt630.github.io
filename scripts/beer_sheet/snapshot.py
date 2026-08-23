"""
Snapshot Agent — freezes a board plus every input needed to re-derive it.

WHY THIS EXISTS: ESPN only serves the CURRENT, continuously-updated version of
"this season's projections." There is no ESPN endpoint that will hand back
"what ESPN projected for 2026 in August 2026" once 2026 is over — by the time
you could evaluate a preseason call, the live API has already moved on to
2027 and the historical number is gone for good. If you don't freeze the
inputs before the season, you cannot honestly evaluate the model after it —
any comparison against a later ESPN pull is lookahead bias (grading a
forecast against information that didn't exist when the forecast was made).
Point-in-time capture is therefore not a nice-to-have; it is the ONLY thing
that makes evaluate.py or sweep.py honest.

A snapshot captures, in one JSON file:
  - snapshot_meta: season, label, captured_at, git commit (if available)
  - league: exact scoring + roster config in effect (from league.json)
  - config_constants: every config.py constant a re-derivation could need
    (BLEND, TIERS, RISK, CONFIDENCE_DISCOUNT, REAL_ADP_POOL_MULTIPLIER,
    ADP_COMPRESSION_GAP, STAT_MAP, scoring/roster presets)
  - replacement_levels / replacement_ranks / tier_summary as computed
  - players: the full ~900-player pool (not just the ~300-player board),
    because replacement level and VOR are computed against the WHOLE pool —
    re-deriving a board under different weights needs the players who never
    made the printed sheet too. Each player record carries:
      * every field projection_agent currently emits (proj_points, the raw
        *projected* stat components in `stats`, espn_points, prior_points /
        prior_points_scaled, market_points, adp, auction_value_market,
        expert_ranks, is_rookie, component_blind, weekly_points, ...) —
        copied through as-is rather than re-keyed field by field, so this
        module doesn't silently drop a field the projection stage adds later
      * `prior_components`: the raw prior-season stat COMPONENTS (not just
        the scalar prior_points total), pulled directly from
        intermediate/espn_raw.json's statSourceId=0/statSplitTypeId=0 entry
        for the prior season. This is the one input CONTRACT.md's
        projections.json does NOT carry forward on its own — without it, a
        future re-score under a different scoring ruleset could redo the
        ESPN-projection and market components but would still be stuck with
        someone else's already-blended prior_points number.
      * whatever board/values/risk/tier stage output exists for that player
        (vor, vor_rank, auction_value, value_delta, floor/ceiling, tier, …),
        present only for the subset that made the ~300-player board.

A year from now, someone must be able to fully reconstruct and re-score this
board from the snapshot file alone, without a working ESPN API call. That is
the test every field in this file is chosen against.

Never overwrites an existing snapshot: `--label` combines with today's date
into the filename, and if that exact file already exists a numeric suffix is
appended (`-2`, `-3`, ...) instead of clobbering it. Pass --refuse to raise
instead of auto-suffixing.

Usage:
  python snapshot.py --label preseason
  python snapshot.py --label week01 --season 2026

STATUS: written and tested against the real (in-progress) 2026 board.json /
projections.json / espn_raw.json on disk as of 2026-08-22. It has NOT been
exercised on a full season's worth of point-in-time snapshots yet — that
can't happen until the 2026 season actually runs its course.
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("snapshot")

SNAPSHOT_DIR = config.DATA_DIR / "snapshots"

# Prior-season actual stat components live in espn_raw.json under this
# (source, split) pair — see fetch_agent.py's module docstring:
#   statSourceId=0, statSplitTypeId=0, seasonId=<prior season> → season TOTAL
PRIOR_SOURCE_ID = 0
PRIOR_SPLIT_ID = 0


def _git_commit_hash() -> str | None:
    """Best-effort. None if git isn't available or this isn't a repo checkout."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=config.REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as exc:
        logger.warning("Could not read git commit hash: %s", exc)
    return None


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _extract_prior_components(espn_raw: dict | None, season: int) -> dict[int, dict]:
    """player_id -> named prior-season raw stat components (config.STAT_MAP).

    This is the piece CONTRACT.md's projections.json throws away (it only
    keeps the already-scored `prior_points` scalar). Pulling it straight from
    espn_raw.json's raw stat entries is what lets a future re-score apply a
    *different* scoring ruleset to last season's actual production, not just
    to this season's projection.
    """
    if not espn_raw:
        return {}
    prior_season = season - 1
    out: dict[int, dict] = {}
    for entry in espn_raw.get("players", []):
        p = entry.get("player") or {}
        pid = p.get("id")
        if pid is None:
            continue
        prior_entry = None
        for s in (p.get("stats") or []):
            if (s.get("statSourceId") == PRIOR_SOURCE_ID
                    and s.get("statSplitTypeId") == PRIOR_SPLIT_ID
                    and s.get("seasonId") == prior_season):
                prior_entry = s
                break
        raw_stats = (prior_entry or {}).get("stats") or {}
        out[pid] = {
            config.STAT_MAP[str(k)]: round(float(v), 2)
            for k, v in raw_stats.items()
            if str(k) in config.STAT_MAP
        }
    return out


def build_snapshot(season: int, label: str) -> dict:
    board = _load_json(config.OUTPUT_FILE)
    projections = _load_json(config.INTERMEDIATE_DIR / "projections.json")
    values = _load_json(config.INTERMEDIATE_DIR / "values.json")
    risk = _load_json(config.INTERMEDIATE_DIR / "risk.json")
    tiers = _load_json(config.INTERMEDIATE_DIR / "tiers.json")
    espn_raw = _load_json(config.INTERMEDIATE_DIR / "espn_raw.json")
    league = _load_json(config.DATA_DIR / "league.json")

    required = {"board.json": board, "projections.json": projections}
    missing = [name for name, payload in required.items() if payload is None]
    if missing:
        raise SystemExit(
            f"Cannot snapshot — missing required pipeline output(s): {missing}. "
            "Run the pipeline (main.py) at least once first."
        )
    if not espn_raw:
        logger.warning(
            "espn_raw.json not found — snapshot will have no prior_components "
            "(re-deriving under a different scoring ruleset won't be possible "
            "for last season's actuals, only for this season's projection)."
        )
    if not league:
        logger.warning("league.json not found — snapshot will have no league scoring/roster block.")

    board_by_id = {p["player_id"]: p for p in board.get("players", [])}
    values_by_id = {v["player_id"]: v for v in (values or {}).get("players", [])}
    risk_by_id = {r["player_id"]: r for r in (risk or {}).get("players", [])}
    tier_by_id = {t["player_id"]: t for t in (tiers or {}).get("players", [])}
    prior_components = _extract_prior_components(espn_raw, season)

    players = []
    for proj in projections.get("players", []):
        pid = proj.get("player_id")
        record = dict(proj)  # carry every field projection_agent emits, whatever they currently are
        record["prior_components"] = prior_components.get(pid, {})

        b = board_by_id.get(pid)
        v = values_by_id.get(pid)
        r = risk_by_id.get(pid)
        t = tier_by_id.get(pid)
        record["on_board"] = b is not None

        # Prefer values.json/risk.json/tiers.json (closer to source) and
        # fall back to board.json's flattened copy of the same numbers.
        record["vor"] = (v or {}).get("vor", (b or {}).get("vor"))
        record["vor_raw"] = (v or {}).get("vor_raw", (b or {}).get("vor_raw"))
        record["vor_rank"] = (v or {}).get("vor_rank", (b or {}).get("vor_rank"))
        record["pos_rank"] = (v or {}).get("pos_rank", (b or {}).get("pos_rank"))
        record["auction_value"] = (v or {}).get("auction_value", (b or {}).get("auction_value"))
        record["value_delta"] = (v or {}).get("value_delta", (b or {}).get("value_delta"))
        record["has_real_adp"] = (v or {}).get("has_real_adp", (b or {}).get("has_real_adp"))
        record["adp_rank"] = (b or {}).get("adp_rank")
        record["risk_score"] = (r or {}).get("risk_score", (b or {}).get("risk_score"))
        record["risk_label"] = (r or {}).get("risk_label", (b or {}).get("risk_label"))
        record["floor_points"] = (r or {}).get("floor_points", (b or {}).get("floor_points"))
        record["ceiling_points"] = (r or {}).get("ceiling_points", (b or {}).get("ceiling_points"))
        record["rank_disagreement"] = (r or {}).get("rank_disagreement", (b or {}).get("rank_disagreement"))
        record["tier"] = (t or {}).get("tier", (b or {}).get("tier"))
        record["tier_label"] = (t or {}).get("tier_label", (b or {}).get("tier_label"))

        # Depth-chart role and blacklist state live ONLY on the board -- they
        # are merged in by sheet_agent and never reach projections.json. They
        # have to be frozen here or they are gone: come evaluation time we
        # want to ask "did the players we labelled STARTER actually outproduce
        # the ones we labelled COMMITTEE?", and that question is unanswerable
        # without the labels as they stood before the season.
        record["role"] = (b or {}).get("role")
        record["depth_chart_order"] = (b or {}).get("depth_chart_order")
        record["sleeper_injury_status"] = (b or {}).get("sleeper_injury_status")
        record["practice_participation"] = (b or {}).get("practice_participation")
        record["blacklisted"] = (b or {}).get("blacklisted", False)
        record["on_board"] = b is not None
        players.append(record)

    config_constants = {
        "BLEND": config.BLEND,
        "TIERS": config.TIERS,
        "RISK": config.RISK,
        "CONFIDENCE_DISCOUNT": config.CONFIDENCE_DISCOUNT,
        "REAL_ADP_POOL_MULTIPLIER": config.REAL_ADP_POOL_MULTIPLIER,
        "ADP_COMPRESSION_GAP": config.ADP_COMPRESSION_GAP,
        "STAT_MAP": config.STAT_MAP,
        "SCORING_PRESETS": config.SCORING,
        "POSITION_SCORING_OVERRIDE": config.POSITION_SCORING_OVERRIDE,
        "ROSTER_PRESETS": config.ROSTER,
    }

    snapshot = {
        "snapshot_meta": {
            "season": season,
            "label": label,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit_hash(),
            "board_generated_at": board.get("generated_at"),
            "notes": (
                "Freeze-and-forget: everything needed to re-derive and re-score "
                "this board lives in this file. The live ESPN endpoint used to "
                "build it will not serve these numbers again."
            ),
        },
        "league": league,
        "config_constants": config_constants,
        "replacement_levels": (values or {}).get("replacement_levels", board.get("replacement_levels")),
        "replacement_ranks": (values or {}).get("replacement_ranks", board.get("replacement_ranks")),
        # Team pass/run tendency as the projections assumed it. Descriptive,
        # not predictive -- but frozen so a later session can ask whether the
        # scheme assumptions baked into this board held up.
        "team_tendency": board.get("team_tendency", {}),
        "tier_summary": (tiers or {}).get("tier_summary", board.get("tier_summary")),
        "board_size": board.get("board_size"),
        "total_pool": len(players),
        "players": players,
    }
    return snapshot


def snapshot_path(season: int, label: str, refuse: bool = False) -> Path:
    """{season}_{label}_{YYYYMMDD}.json under data/beer_sheet/snapshots/.

    Never overwrites: if the exact target already exists, either raise
    (refuse=True) or auto-suffix with -2, -3, ... (default). An overwritten
    snapshot is unrecoverable — the ESPN data behind it moves on — so silent
    clobbering is not an option either way.
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    base = f"{season}_{label}_{date_str}"
    path = SNAPSHOT_DIR / f"{base}.json"
    if not path.exists():
        return path
    if refuse:
        raise SystemExit(
            f"Refusing to overwrite existing snapshot: {path}. "
            "Pick a different --label, wait a day, or drop --refuse to auto-suffix."
        )
    n = 2
    while True:
        candidate = SNAPSHOT_DIR / f"{base}-{n}.json"
        if not candidate.exists():
            logger.warning("%s already exists — writing %s instead", path.name, candidate.name)
            return candidate
        n += 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Freeze the current beer sheet board + inputs for later evaluation")
    ap.add_argument("--label", default="preseason",
                    help="e.g. preseason, week01, week08 — combines with today's date in the filename")
    ap.add_argument("--season", type=int, default=config.SEASON)
    ap.add_argument("--refuse", action="store_true",
                    help="Refuse (instead of auto-suffixing) if today's snapshot for this label already exists")
    args = ap.parse_args()

    snap = build_snapshot(args.season, args.label)
    path = snapshot_path(args.season, args.label, refuse=args.refuse)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)

    on_board = sum(1 for p in snap["players"] if p.get("on_board"))
    logger.info(
        "Snapshot saved -> %s  (%d players in pool, %d on board, git=%s)",
        path, len(snap["players"]), on_board, snap["snapshot_meta"]["git_commit"] or "unknown",
    )


if __name__ == "__main__":
    main()
