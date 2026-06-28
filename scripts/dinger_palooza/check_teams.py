"""
check_teams.py — Validate that every player in config.py is on their listed team.

When mlb_id is set in config (all players should have it), goes directly to
/people/{id}?hydrate=currentTeam — no name search, no fuzzy matching.

Falls back to /people/search + fuzzy match only for players with mlb_id: None.

Outputs:
  - PASS: player is on their listed team
  - STALE: player is on a different team (config needs updating)
  - NOTFOUND: player not found in MLB search (retired, minors, name mismatch)
  - INACTIVE: soft flag for free agents / players marked inactive: True in config

Exit code 1 if any STALE or NOTFOUND entries exist, so CI can catch it.
"""

import asyncio
import json
import os
import re
import sys
import unicodedata

import aiohttp

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from config import PLAYERS, MLB_API_BASE, TEAM_ABBR


def normalize(s: str) -> str:
    """Lowercase, strip accents, remove punctuation for fuzzy matching."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # strip combining marks
    return s.lower().replace(".", "").replace(",", "").replace(" jr", "").replace(" sr", "").strip()


async def get_current_team(session: aiohttp.ClientSession, mlb_id: int) -> dict:
    """Fetch a player's current team via /people/{id}?hydrate=currentTeam."""
    url = f"{MLB_API_BASE}/people/{mlb_id}?hydrate=currentTeam"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        resp.raise_for_status()
        data = await resp.json()
    people = data.get("people", [])
    if not people:
        return {}
    return people[0].get("currentTeam", {})


def _team_status(player: dict, mlb_id: int, current_team: dict) -> dict:
    """Compute result dict from a live currentTeam API response."""
    live_team_id = current_team.get("id")
    live_team = current_team.get("name", "Unknown")
    live_abbr = current_team.get("abbreviation") or TEAM_ABBR.get(live_team_id, "???")

    # Non-MLB team ID → minor-league rehab assignment; player still on MLB parent club
    if live_team_id not in TEAM_ABBR and live_team_id is not None:
        status = "PASS"
        detail = f"✓ {player['team']} ({player['team_abbr']}) — API returned minor-league team {live_team} (id={live_team_id}), likely rehab assignment"
    elif live_team_id == player["team_id"]:
        status = "PASS"
        detail = f"✓ {live_team} ({live_abbr})"
    else:
        status = "STALE"
        detail = (
            f"config={player['team']} ({player['team_abbr']}, id={player['team_id']})  "
            f"→  actual={live_team} ({live_abbr}, id={live_team_id})"
        )

    if status == "STALE" and player.get("inactive"):
        status = "INACTIVE"
        detail = f"free agent / inactive — last config team: {player['team']} ({player['team_abbr']}); currently: {live_team}"

    return {
        **player,
        "status": status,
        "detail": detail,
        "live_team": live_team,
        "live_team_id": live_team_id,
        "live_abbr": live_abbr,
        "mlb_id": mlb_id,
    }


async def check_player(session: aiohttp.ClientSession, player: dict) -> dict:
    name = player["name"]
    mlb_id = player.get("mlb_id")

    if mlb_id:
        # Direct lookup by ID — no fuzzy name search
        try:
            current_team = await get_current_team(session, mlb_id)
        except Exception as exc:
            return {**player, "status": "ERROR", "detail": str(exc), "live_team": None, "live_team_id": None}
        return _team_status(player, mlb_id, current_team)

    # Fallback: name search (only reached if mlb_id is missing from config)
    name_encoded = name.replace(" ", "+")
    url = f"{MLB_API_BASE}/people/search?names={name_encoded}&sportId=1"

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except Exception as exc:
        return {**player, "status": "ERROR", "detail": str(exc), "live_team": None, "live_team_id": None}

    people = data.get("people", [])
    target = normalize(name)

    for person in people:
        full_name = normalize(person.get("fullName", ""))
        if target in full_name or full_name in target or target == full_name:
            found_id = person.get("id")
            try:
                current_team = await get_current_team(session, found_id)
            except Exception:
                current_team = {}
            return _team_status(player, found_id, current_team)

    if player.get("inactive"):
        return {
            **player,
            "status": "INACTIVE",
            "detail": "free agent / inactive — not found in MLB search (expected)",
            "live_team": None,
            "live_team_id": None,
        }

    return {
        **player,
        "status": "NOTFOUND",
        "detail": f"No match in MLB search for '{name}'",
        "live_team": None,
        "live_team_id": None,
    }


async def run_checks() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        tasks = [check_player(session, p) for p in PLAYERS]
        results = await asyncio.gather(*tasks)
    return list(results)


def print_report(results: list[dict], fmt: str = "text") -> int:
    stale = [r for r in results if r["status"] == "STALE"]
    notfound = [r for r in results if r["status"] == "NOTFOUND"]
    inactive = [r for r in results if r["status"] == "INACTIVE"]
    errors = [r for r in results if r["status"] == "ERROR"]
    passing = [r for r in results if r["status"] == "PASS"]

    if fmt == "gha":
        lines = []
        lines.append("# Dinger Palooza — Team Config Audit\n")
        lines.append(f"Checked {len(results)} players against live MLB API.\n")

        if not stale and not notfound:
            lines.append("## ✅ All active players match their configured teams\n")
        else:
            lines.append(f"## Summary: {len(stale)} stale · {len(notfound)} not found · {len(inactive)} inactive · {len(errors)} errors · {len(passing)} OK\n")

        if stale:
            lines.append("## 🔄 Stale team assignments — update config.py\n")
            lines.append("| Player | Config team | Actual team | Config team_id | New team_id |")
            lines.append("|--------|-------------|-------------|----------------|-------------|")
            for r in stale:
                lines.append(
                    f"| **{r['name']}** | {r['team']} ({r['team_abbr']}) "
                    f"| {r['live_team']} ({r.get('live_abbr','?')}) "
                    f"| {r['team_id']} | {r['live_team_id']} |"
                )
            lines.append("")

        if notfound:
            lines.append("## ❓ Players not found in MLB search\n")
            lines.append("| Player | Config team |")
            lines.append("|--------|-------------|")
            for r in notfound:
                lines.append(f"| {r['name']} | {r['team']} ({r['team_abbr']}) |")
            lines.append("")

        if inactive:
            lines.append("## 💤 Inactive / free agents (soft flag — not counted as failures)\n")
            for r in inactive:
                lines.append(f"- **{r['name']}** — {r['detail']}")
            lines.append("")

        if errors:
            error_pct = round(100 * len(errors) / max(len(results), 1))
            if error_pct >= 50:
                lines.append(f"## 🚨 MLB API unreachable — {len(errors)}/{len(results)} players failed ({error_pct}%)\n")
                lines.append("Audit result is invalid. Check network/proxy access to statsapi.mlb.com.\n")
            else:
                lines.append(f"## ⚠ API errors (transient — rerun to confirm)\n")
            for r in errors:
                lines.append(f"- {r['name']}: {r['detail']}")
            lines.append("")

        if passing:
            lines.append(f"<details><summary>✅ Passing players ({len(passing)})</summary>\n")
            for r in passing:
                lines.append(f"- {r['name']} — {r['detail']}")
            lines.append("</details>")

        output = "\n".join(lines)
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_file:
            with open(summary_file, "w") as f:
                f.write(output)
            print("Job summary written.")
        else:
            print(output)

    else:
        print(f"\n{'='*60}")
        print(f"  Dinger Palooza Team Config Audit — {len(results)} players")
        print(f"{'='*60}")
        sort_key = lambda x: (x["status"] != "STALE", x["status"] != "NOTFOUND", x["status"] != "INACTIVE", x["name"])
        for r in sorted(results, key=sort_key):
            icon = {"PASS": "✓", "STALE": "✗", "NOTFOUND": "?", "INACTIVE": "~", "ERROR": "!"}.get(r["status"], " ")
            print(f"  {icon} {r['name']:<25}  {r['status']:<10}  {r['detail']}")
        print(f"\n  Results: {len(passing)} OK · {len(stale)} stale · {len(notfound)} not found · {len(inactive)} inactive · {len(errors)} errors")
        if stale or notfound:
            print("\n  → Run with --fix to auto-patch config.py for stale team assignments.\n")

    # Fail if MLB API was unreachable (>= 50% errors means the audit is invalid)
    total_active = len(results) - len(inactive)
    if total_active > 0 and len(errors) / total_active >= 0.5:
        return 1
    return 1 if (stale or notfound) else 0


def build_patch(results: list[dict]) -> dict:
    return {
        r["name"]: {
            "team": r["live_team"],
            "team_id": r["live_team_id"],
            "team_abbr": r.get("live_abbr", r["team_abbr"]),
        }
        for r in results
        if r["status"] == "STALE"
    }


def apply_patch(results: list[dict]) -> int:
    """
    Write STALE team updates directly into config.py and return the count of changes.
    Each player's team/team_id/team_abbr fields are updated in-place; all other
    fields (mlb_id, bats, inactive, etc.) are left untouched.
    """
    patch = build_patch(results)
    if not patch:
        return 0

    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    with open(config_path) as f:
        lines = f.readlines()

    count = 0
    for i, line in enumerate(lines):
        for name, updates in patch.items():
            if f'"name": "{name}"' not in line:
                continue
            orig = line
            line = re.sub(r'"team":\s*"[^"]*"', f'"team": "{updates["team"]}"', line, count=1)
            line = re.sub(r'"team_id":\s*\d+', f'"team_id": {updates["team_id"]}', line, count=1)
            line = re.sub(r'"team_abbr":\s*"[^"]*"', f'"team_abbr": "{updates["team_abbr"]}"', line, count=1)
            if line != orig:
                lines[i] = line
                count += 1
                print(f"  config.py fixed: {name} → {updates['team']} ({updates['team_abbr']}, id={updates['team_id']})")
            else:
                print(f"  WARNING: could not patch config.py for {name!r}")

    with open(config_path, "w") as f:
        f.writelines(lines)

    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Audit Dinger Palooza player-team config")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--gha", action="store_true", help="Write GitHub Actions job summary")
    parser.add_argument("--fix", action="store_true", help="Auto-update config.py for STALE players")
    args = parser.parse_args()

    results = asyncio.run(run_checks())

    if args.json:
        print(json.dumps(results, indent=2))
        sys.exit(0)

    fmt = "gha" if args.gha else "text"
    exit_code = print_report(results, fmt=fmt)

    if args.fix:
        fixed = apply_patch(results)
        if fixed:
            print(f"\nApplied {fixed} fix(es) to config.py.")

    sys.exit(exit_code)
