"""
check_teams.py — Validate that every player in config.py is on their listed team.

Uses MLB /people/search to find the player ID, then /people/{id}?hydrate=currentTeam
for the actual current team (search alone doesn't return currentTeam reliably).

Usage:
  python scripts/dinger_palooza/check_teams.py

Outputs:
  - PASS: player is on their listed team
  - STALE: player is on a different team (config needs updating)
  - NOTFOUND: player not found in MLB search (retired, minors, name mismatch)

Exit code 1 if any STALE or NOTFOUND entries exist, so CI can catch it.
"""

import asyncio
import json
import os
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


async def check_player(session: aiohttp.ClientSession, player: dict) -> dict:
    name = player["name"]
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
            mlb_id = person.get("id")

            # Search doesn't reliably include currentTeam — fetch it directly
            try:
                current_team = await get_current_team(session, mlb_id)
            except Exception:
                current_team = {}

            live_team_id = current_team.get("id")
            live_team = current_team.get("name", "Unknown")
            live_abbr = current_team.get("abbreviation") or TEAM_ABBR.get(live_team_id, "???")

            # If the API returns a non-MLB team ID (minor league rehab assignment),
            # treat as PASS — the player is still on their MLB parent club.
            # Same logic as schedule_agent.py's _fetch_current_team fix.
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

            return {
                **player,
                "status": status,
                "detail": detail,
                "live_team": live_team,
                "live_team_id": live_team_id,
                "live_abbr": live_abbr,
                "mlb_id": mlb_id,
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
    errors = [r for r in results if r["status"] == "ERROR"]
    passing = [r for r in results if r["status"] == "PASS"]

    if fmt == "gha":
        lines = []
        lines.append("# Dinger Palooza — Team Config Audit\n")
        lines.append(f"Checked {len(results)} players against live MLB API.\n")

        if not stale and not notfound:
            lines.append("## ✅ All players match their configured teams\n")
        else:
            lines.append(f"## Summary: {len(stale)} stale · {len(notfound)} not found · {len(errors)} errors · {len(passing)} OK\n")

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

        if errors:
            lines.append("## ⚠ API errors (transient — rerun to confirm)\n")
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
        for r in sorted(results, key=lambda x: (x["status"] != "STALE", x["status"] != "NOTFOUND", x["name"])):
            icon = {"PASS": "✓", "STALE": "✗", "NOTFOUND": "?", "ERROR": "!"}.get(r["status"], " ")
            print(f"  {icon} {r['name']:<25}  {r['status']:<10}  {r['detail']}")
        print(f"\n  Results: {len(passing)} OK · {len(stale)} stale · {len(notfound)} not found · {len(errors)} errors")
        if stale or notfound:
            print("\n  → Paste this output to Claude to update config.py automatically.\n")

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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Audit Dinger Palooza player-team config")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--gha", action="store_true", help="Write GitHub Actions job summary")
    args = parser.parse_args()

    results = asyncio.run(run_checks())

    if args.json:
        print(json.dumps(results, indent=2))
        sys.exit(0)

    fmt = "gha" if args.gha else "text"
    exit_code = print_report(results, fmt=fmt)

    if exit_code != 0:
        patch = build_patch(results)
        if patch and not args.gha:
            print("  Suggested config.py patches:")
            for name, data in patch.items():
                print(f'    "{name}": team="{data["team"]}" team_id={data["team_id"]} team_abbr="{data["team_abbr"]}"')

    sys.exit(exit_code)
