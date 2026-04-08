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

async def check_roster_status(
    session: aiohttp.ClientSession,
    player_name: str,
    team_id: int,
) -> dict:
    """
    Returns a status dict describing where the player actually is:

      {"status": "active"}                          — on 26-man active roster ✓
      {"status": "il"}                              — on 40-man/fullRoster but not active (IL)
      {"status": "wrong_team",
       "actual_team": str, "actual_team_id": int,
       "actual_team_abbr": str}                     — found in MLB but on a different team
      {"status": "not_found"}                       — not found in MLB search at all
      {"status": "api_error"}                       — API call failed

    Uses /people/search first (team-agnostic, IL-safe), then confirms active
    roster status with a second call.  This replaces the old active-roster-only
    check that false-errored on IL players (e.g. Soto, Betts hit 0 games_checked).
    """
    target = _clean(player_name)

    # Step 1: name search to find the player and their actual current team
    name_encoded = player_name.replace(" ", "+")
    search_url = f"{MLB_API_BASE}/people/search?names={name_encoded}&sportId=1"
    try:
        async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except Exception:
        return {"status": "api_error"}

    mlb_id = None
    for person in data.get("people", []):
        full = _clean(person.get("fullName", ""))
        if target == full or target in full or full in target:
            mlb_id = person.get("id")
            live_team = person.get("currentTeam", {})
            live_tid = live_team.get("id")
            # If currentTeam is present and differs from picks → wrong team
            if live_tid and live_tid != team_id:
                return {
                    "status": "wrong_team",
                    "actual_team": live_team.get("name", "Unknown"),
                    "actual_team_id": live_tid,
                    "actual_team_abbr": live_team.get("abbreviation", "?"),
                }
            break  # Found player, team matches (or currentTeam not in response)

    if mlb_id is None:
        return {"status": "not_found"}

    # Step 2: confirm active vs IL — use fullRoster (includes IL) then active
    full_url = f"{MLB_API_BASE}/teams/{team_id}/roster?rosterType=fullRoster&hydrate=person"
    try:
        async with session.get(full_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            full_data = await resp.json()
    except Exception:
        # Couldn't confirm but found via search — treat as active (don't false-error)
        return {"status": "active"}

    on_full_roster = any(
        target == _clean(e.get("person", {}).get("fullName", ""))
        or target in _clean(e.get("person", {}).get("fullName", ""))
        or _clean(e.get("person", {}).get("fullName", "")) in target
        for e in full_data.get("roster", [])
    )
    if not on_full_roster:
        # Name search found them but they're not on this team's 40-man — likely wrong team
        return {"status": "not_found"}

    # Check active roster to distinguish active from IL
    active_url = f"{MLB_API_BASE}/teams/{team_id}/roster?rosterType=active&hydrate=person"
    try:
        async with session.get(active_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            active_data = await resp.json()
    except Exception:
        return {"status": "il"}  # On 40-man but couldn't confirm active

    on_active = any(
        target == _clean(e.get("person", {}).get("fullName", ""))
        or target in _clean(e.get("person", {}).get("fullName", ""))
        or _clean(e.get("person", {}).get("fullName", "")) in target
        for e in active_data.get("roster", [])
    )
    return {"status": "active" if on_active else "il"}


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
                    tasks.append(check_roster_status(session, name, team_id))
                    task_meta.append((member["name"], name, team_abbr, team_id))

        if check_roster and tasks:
            results = await asyncio.gather(*tasks)
            for (member_name, name, team_abbr, team_id), result in zip(task_meta, results):
                status = result["status"]
                if status == "api_error":
                    issues.append({
                        "member":  member_name,
                        "player":  name,
                        "team":    team_abbr,
                        "level":   "warning",
                        "message": f"Roster check failed for '{name}' (team_id={team_id}) — API unavailable.",
                    })
                elif status == "wrong_team":
                    issues.append({
                        "member":  member_name,
                        "player":  name,
                        "team":    team_abbr,
                        "level":   "error",
                        "message": (
                            f"Wrong team in picks file: listed as {team_abbr} (id={team_id}) "
                            f"but '{name}' is actually on {result['actual_team']} "
                            f"({result['actual_team_abbr']}, id={result['actual_team_id']}). "
                            f"Update picks file."
                        ),
                    })
                elif status == "not_found":
                    issues.append({
                        "member":  member_name,
                        "player":  name,
                        "team":    team_abbr,
                        "level":   "warning",
                        "message": f"'{name}' not found in MLB search — check spelling or team.",
                    })
                elif status == "il":
                    issues.append({
                        "member":  member_name,
                        "player":  name,
                        "team":    team_abbr,
                        "level":   "warning",
                        "message": (
                            f"'{name}' is on {team_abbr}'s 40-man roster but NOT on the active roster "
                            f"(likely on IL). Pick is valid but expect 0 points while inactive."
                        ),
                    })
                # status == "active": no issue

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
