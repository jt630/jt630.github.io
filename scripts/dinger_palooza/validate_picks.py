"""
Dinger Palooza — Picks Validator
==================================
Validates a week's picks file against known sluggers and live MLB rosters.

Checks per pick:
  1. Player is in config.PLAYERS (recognized HR threat)
  2. Team matches config.PLAYERS entry (no stale team assignments)
  3. Player is on the team's active MLB roster right now

Exit code 0 = all clean. Non-zero = warnings/errors found.

Usage:
  python validate_picks.py                         # latest picks file
  python validate_picks.py --week 01               # specific week
  python validate_picks.py --picks picks/week_01.yaml
  python validate_picks.py --no-roster-check       # skip live API calls
"""

import argparse
import asyncio
import sys
import unicodedata
from pathlib import Path

import aiohttp
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from config import MLB_API_BASE, PLAYERS

DATA_DIR = "data/dinger_palooza"
PICKS_DIR = f"{DATA_DIR}/picks"

# Build lookup: normalized name → player entry from config
def _clean(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return (
        s.lower()
        .replace(".", "").replace(",", "")
        .replace("'", "").replace("'", "")
        .replace(" jr", "").replace(" sr", "")
        .strip()
    )

PLAYER_INDEX: dict[str, dict] = {_clean(p["name"]): p for p in PLAYERS}


# ── Roster check via MLB API ──────────────────────────────────────────────────

async def is_on_active_roster(
    session: aiohttp.ClientSession,
    player_name: str,
    team_id: int,
) -> bool | None:
    """
    Returns True if player is on the team's active roster, False if not found,
    None if the API call failed.
    """
    url = f"{MLB_API_BASE}/teams/{team_id}/roster?rosterType=active&hydrate=person"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except Exception as e:
        return None

    target = _clean(player_name)
    for entry in data.get("roster", []):
        full = _clean(entry.get("person", {}).get("fullName", ""))
        if target == full or target in full or full in target:
            return True
    return False


# ── Validation logic ──────────────────────────────────────────────────────────

async def validate_picks(picks_data: dict, check_roster: bool = True) -> list[dict]:
    """
    Validate all picks. Returns a list of issue dicts:
      {member, player, team, level: "error"|"warning", message}
    """
    issues: list[dict] = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        task_meta = []  # (member_name, pick)

        for member in picks_data["members"]:
            for pick in member["picks"]:
                name = pick["player"]
                team_abbr = pick["team"]
                team_id = pick["team_id"]
                key = _clean(name)

                # Check 1: Is the player in our known slugger list?
                config_entry = PLAYER_INDEX.get(key)
                if config_entry is None:
                    issues.append({
                        "member":  member["name"],
                        "player":  name,
                        "team":    team_abbr,
                        "level":   "warning",
                        "message": f"'{name}' is not in the known slugger list — may not be a top HR threat.",
                    })
                else:
                    # Check 2: Does the team match?
                    if config_entry["team_id"] != team_id:
                        issues.append({
                            "member":  member["name"],
                            "player":  name,
                            "team":    team_abbr,
                            "level":   "error",
                            "message": (
                                f"Team mismatch: pick says {team_abbr} (id={team_id}) "
                                f"but config has {config_entry['team_abbr']} "
                                f"({config_entry['team']}, id={config_entry['team_id']})."
                            ),
                        })

                # Check 3: Live roster check (uses pick's team_id as source of truth)
                if check_roster:
                    tasks.append(is_on_active_roster(session, name, team_id))
                    task_meta.append((member["name"], name, team_abbr, team_id))

        if check_roster and tasks:
            results = await asyncio.gather(*tasks)
            for (member_name, name, team_abbr, team_id), on_roster in zip(task_meta, results):
                if on_roster is None:
                    issues.append({
                        "member":  member_name,
                        "player":  name,
                        "team":    team_abbr,
                        "level":   "warning",
                        "message": f"Roster check failed for '{name}' (team_id={team_id}) — API unavailable.",
                    })
                elif not on_roster:
                    issues.append({
                        "member":  member_name,
                        "player":  name,
                        "team":    team_abbr,
                        "level":   "error",
                        "message": f"'{name}' was NOT found on the active roster for {team_abbr} (team_id={team_id}).",
                    })

    return issues


def print_report(picks_data: dict, issues: list[dict], week_number: int) -> None:
    week_start = picks_data["week_start"]
    week_end   = picks_data["week_end"]

    print(f"\n{'DINGER PALOOZA — PICKS VALIDATION':^60}")
    print(f"Week {week_number}  |  {week_start} → {week_end}")
    print("=" * 60)

    if not issues:
        print("  All picks look good.")
        print("=" * 60)
        return

    errors   = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]

    for issue in errors + warnings:
        tag = "ERROR  " if issue["level"] == "error" else "WARNING"
        print(f"[{tag}] {issue['member']} / {issue['player']} ({issue['team']})")
        print(f"         {issue['message']}")

    print("=" * 60)
    print(f"  {len(errors)} error(s), {len(warnings)} warning(s)")
    print("=" * 60)


def load_picks(week_number: int, picks_override: str | None = None) -> dict:
    path = picks_override or f"{PICKS_DIR}/week_{week_number:02d}.yaml"
    if not Path(path).exists():
        raise FileNotFoundError(f"Picks file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def _latest_week_number() -> int:
    picks_dir = Path(PICKS_DIR)
    if not picks_dir.exists():
        return 1
    files = sorted(picks_dir.glob("week_*.yaml"))
    return int(files[-1].stem.split("_")[1]) if files else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Dinger Palooza picks")
    parser.add_argument("--week", type=int, default=None, help="Week number (e.g. 1)")
    parser.add_argument("--picks", type=str, default=None, help="Path to picks YAML file")
    parser.add_argument(
        "--no-roster-check",
        action="store_true",
        help="Skip live MLB roster API calls (faster, offline-safe)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    week_num = args.week or _latest_week_number()
    picks = load_picks(week_num, args.picks)

    issues = asyncio.run(validate_picks(picks, check_roster=not args.no_roster_check))
    print_report(picks, issues, week_num)

    errors = [i for i in issues if i["level"] == "error"]
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
