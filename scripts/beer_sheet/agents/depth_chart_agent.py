"""
Depth Chart Agent — does this player actually have a job?

proj_points alone can't tell a lead back from his backup if a projection
system splits touches conservatively — a bell-cow RB1 and his handcuff can
land within a few points of each other despite one of them being a real
weekly start and the other a bye-week/injury flier. This agent joins Sleeper's
free player database (which carries depth_chart_order, injury detail, age and
years of experience — none of which ESPN's projection feed exposes) onto our
existing player pool by NAME, since Sleeper and ESPN don't share an id space.

  GET https://api.sleeper.app/v1/players/nfl   -> ~12,200 players, ~14MB, no
  auth required. Fetched once and cached to
  intermediate/sleeper_players.json (pass force_refresh=True to re-pull).

THE JOIN. Sleeper full_name and ESPN name diverge on suffixes (Jr/Sr/II/III),
punctuation and apostrophes (Ja'Marr Chase), accents, and team defenses
("Texans D/ST" vs a Sleeper DEF record keyed by team code). We normalize both
sides (unicodedata NFD strip, drop punctuation, strip suffix tokens, casefold)
and match in three passes, each strictly more permissive than the last:

  1. team defenses: matched directly on team abbreviation (Sleeper keys DEF
     players by team code, so there's no name join to do at all).
  2. normalized_name + team, exact.
  3. normalized_name alone, but ONLY if it resolves to exactly one Sleeper
     candidate. An ambiguous name-only match (two Sleeper players share a
     normalized name) is left UNMATCHED rather than guessed — a wrong join
     here silently mislabels a starter as a backup, which is worse than no
     label at all.

Anyone who clears none of those passes gets role=UNKNOWN with every Sleeper
field null. That is a deliberate, visible "we don't know" rather than a
guess.

ROLE mapping is position-aware (config.DEPTH_CHART_ROLE /
DEPTH_CHART_OVERFLOW_ROLE) because depth_chart_order means a different thing
per position: a Sleeper #3 WR is usually still on the field in 11-personnel,
a #3 RB or TE almost never is, and Sleeper rarely bothers ordering K/DST past
1 at all so "not 1" reads UNKNOWN rather than BENCH there.

TEAM TENDENCY (team_tendency key) is DESCRIPTIVE, not an independent signal:
it is computed entirely from stat components already inside our own
projections.json (pass_attempts / rush_attempts, summed per team), so it
restates what ESPN's own projections assume about each offense's split — it
does not add outside information. Where the same players' prior-season raw
stat lines are available (pulled from intermediate/espn_raw.json, which
fetch_agent already produced), we also compute the prior-year ACTUAL pass
rate so the two can be compared; a big gap between "projected" and "prior
actual" for a team means the projection is pricing in a scheme change (new
OC, personnel turnover, a rookie QB who runs more) rather than reflecting an
independent read on offensive philosophy.

Output: data/beer_sheet/intermediate/depth.json
  {
    "players": {"<player_id>": {role, depth_chart_order, depth_chart_position,
                                 sleeper_injury_status, injury_body_part,
                                 practice_participation, age, years_exp,
                                 sleeper_status}, ...},
    "match_stats": {...},
    "team_tendency": {"<TEAM>": {"projected_pass_rate": .., "prior_actual_pass_rate": ..|null,
                                  "projected_pass_attempts": .., "projected_rush_attempts": ..}, ...}
  }
"""

import json
import logging
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    INTERMEDIATE_DIR, DEPTH_CHART_ROLE, DEPTH_CHART_OVERFLOW_ROLE,
    SLEEPER_TEAM_ALIASES, STAT_MAP, SEASON,
)

logger = logging.getLogger("depth_chart_agent")

API = "https://api.sleeper.app/v1/players/nfl"
CACHE_FILE = INTERMEDIATE_DIR / "sleeper_players.json"

SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}

# ESPN name -> normalized-name override for team defenses, so pass 1 (team
# code only) is the ONLY path DST needs; kept here in case a future ESPN
# naming quirk needs a manual nudge.
DST_NAME_RE = re.compile(r"\s*D/ST$", re.IGNORECASE)


# -- Name normalization --------------------------------------------------------
def normalize_name(name: str) -> str:
    """Casefold, strip accents/punctuation, drop suffix tokens, collapse space."""
    if not name:
        return ""
    name = DST_NAME_RE.sub("", name)
    # Strip accents: NFD splits base char + combining mark, then we drop marks.
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.replace("'", "").replace(".", "").replace("-", " ")
    name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    tokens = [t for t in name.lower().split() if t not in SUFFIX_TOKENS]
    return " ".join(tokens)


def normalize_team(team: str | None) -> str:
    if not team:
        return ""
    team = team.upper()
    return SLEEPER_TEAM_ALIASES.get(team, team)


# -- Sleeper fetch / cache -----------------------------------------------------
def fetch_sleeper_players(force_refresh: bool = False) -> dict:
    if not force_refresh and CACHE_FILE.exists():
        logger.info("Using cached Sleeper player pool -> %s", CACHE_FILE)
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)

    logger.info("Fetching Sleeper player pool (one-time ~14MB pull)...")
    req = urllib.request.Request(API)
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    logger.info("Cached %d Sleeper players -> %s", len(data), CACHE_FILE)
    return data


# -- Matching -------------------------------------------------------------------
def build_sleeper_indexes(sleeper: dict) -> tuple[dict, dict, dict]:
    """
    Returns (by_team_defense, by_name_team, by_name).
      by_team_defense: normalized team -> sleeper DEF record
      by_name_team:    (normalized_name, normalized_team) -> sleeper record
      by_name:         normalized_name -> list of sleeper records (for ambiguity check)
    """
    by_team_defense: dict[str, dict] = {}
    by_name_team: dict[tuple[str, str], dict] = {}
    by_name: dict[str, list[dict]] = {}

    for pid, p in sleeper.items():
        if p.get("position") == "DEF":
            team = normalize_team(p.get("team"))
            if team:
                by_team_defense[team] = p
            continue

        full_name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        if not full_name:
            continue
        norm = normalize_name(full_name)
        if not norm:
            continue
        team = normalize_team(p.get("team"))
        if team:
            by_name_team.setdefault((norm, team), p)
        by_name.setdefault(norm, []).append(p)

    return by_team_defense, by_name_team, by_name


def match_player(espn_player: dict, by_team_defense: dict,
                  by_name_team: dict, by_name: dict) -> tuple[dict | None, str]:
    """Returns (sleeper_record_or_None, match_method)."""
    position = espn_player.get("position")
    team = normalize_team(espn_player.get("team"))

    if position == "DST":
        rec = by_team_defense.get(team)
        return (rec, "team_defense") if rec else (None, "unmatched")

    norm = normalize_name(espn_player.get("name", ""))
    if not norm:
        return None, "unmatched"

    rec = by_name_team.get((norm, team))
    if rec:
        return rec, "name_team"

    candidates = by_name.get(norm, [])
    if len(candidates) == 1:
        return candidates[0], "name_only"
    if len(candidates) > 1:
        return None, "ambiguous"

    return None, "unmatched"


# -- Role mapping ---------------------------------------------------------------
def resolve_role(position: str, depth_chart_order) -> str:
    if depth_chart_order is None:
        return "UNKNOWN"
    role_map = DEPTH_CHART_ROLE.get(position)
    if role_map is None:
        return "UNKNOWN"
    try:
        order = int(depth_chart_order)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if order in role_map:
        return role_map[order]
    # Below every mapped key -> UNKNOWN never applies to a positive order we
    # simply don't have a key for; above the highest mapped key -> overflow.
    highest_mapped = max(role_map)
    if order > highest_mapped:
        return DEPTH_CHART_OVERFLOW_ROLE.get(position, "UNKNOWN")
    return "UNKNOWN"


def sleeper_record_to_depth(sleeper_rec: dict) -> dict:
    return {
        "role": resolve_role(sleeper_rec.get("position") or sleeper_rec.get("fantasy_positions", [None])[0],
                              sleeper_rec.get("depth_chart_order")),
        "depth_chart_order": sleeper_rec.get("depth_chart_order"),
        "depth_chart_position": sleeper_rec.get("depth_chart_position"),
        "sleeper_injury_status": sleeper_rec.get("injury_status"),
        "injury_body_part": sleeper_rec.get("injury_body_part"),
        "practice_participation": sleeper_rec.get("practice_participation"),
        "age": sleeper_rec.get("age"),
        "years_exp": sleeper_rec.get("years_exp"),
        "sleeper_status": sleeper_rec.get("status"),
        "match_method": None,  # filled in by caller
    }


UNKNOWN_DEPTH = {
    "role": "UNKNOWN",
    "depth_chart_order": None,
    "depth_chart_position": None,
    "sleeper_injury_status": None,
    "injury_body_part": None,
    "practice_participation": None,
    "age": None,
    "years_exp": None,
    "sleeper_status": None,
    "match_method": "unmatched",
}


# -- Team tendency ----------------------------------------------------------------
def _named_stats(raw_stats: dict | None) -> dict:
    if not raw_stats:
        return {}
    out = {}
    for stat_id, name in STAT_MAP.items():
        if stat_id in raw_stats:
            out[name] = float(raw_stats[stat_id])
    return out


def _prior_actual_attempts_by_team(season: int) -> dict[str, dict[str, float]]:
    """
    Best-effort prior-season pass/rush attempt totals per team, pulled from
    espn_raw.json (already on disk from fetch_agent). Returns {} if the file
    isn't there — team_tendency still works, just without the comparison.
    """
    raw_path = INTERMEDIATE_DIR / "espn_raw.json"
    if not raw_path.exists():
        logger.warning("espn_raw.json not found — skipping prior-actual pass rate.")
        return {}

    from config import POSITION_MAP  # local import to avoid unused warning elsewhere

    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    # Need team abbrev per proTeamId — reuse the same schedule endpoint
    # projection_agent uses, but tolerate failure (offline/rate-limited)
    # since this whole block is a nice-to-have comparison, not core output.
    try:
        req = urllib.request.Request(
            "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
            f"{season}?view=proTeamSchedules_wl")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
        teams = {t["id"]: t.get("abbrev", "FA") for t in payload.get("settings", {}).get("proTeams", [])}
    except Exception as exc:  # noqa: BLE001 - best-effort, never fatal
        logger.warning("Could not fetch team schedule for prior-actual pass rate: %s", exc)
        return {}

    prior_season = season - 1
    totals: dict[str, dict[str, float]] = {}
    for entry in raw.get("players", []):
        p = entry.get("player") or {}
        position = POSITION_MAP.get(p.get("defaultPositionId"))
        if position not in ("QB", "RB", "WR", "TE"):
            continue
        team = normalize_team(teams.get(p.get("proTeamId")))
        if not team or team == "FA":
            continue
        for stat_entry in p.get("stats") or []:
            if (stat_entry.get("statSourceId") == 0
                    and stat_entry.get("statSplitTypeId") == 0
                    and stat_entry.get("seasonId") == prior_season):
                named = _named_stats(stat_entry.get("stats"))
                bucket = totals.setdefault(team, {"pass_attempts": 0.0, "rush_attempts": 0.0})
                bucket["pass_attempts"] += named.get("pass_attempts", 0.0)
                bucket["rush_attempts"] += named.get("rush_attempts", 0.0)
                break
    return totals


def compute_team_tendency(projections: dict, season: int = SEASON) -> dict:
    """
    DESCRIPTIVE ONLY: restates what our own projections already assume about
    each team's offense (pass_attempts vs rush_attempts, summed across all of
    that team's projected players). This is NOT an independent signal — it is
    ESPN's projection mix read back out at the team level. Where prior-season
    actuals are available, we add them purely as a sanity comparison: a large
    gap between projected_pass_rate and prior_actual_pass_rate flags that the
    projections assume a scheme change (new OC, rookie QB, personnel
    overhaul), not that our model has additional information.
    """
    projected: dict[str, dict[str, float]] = {}
    for p in projections.get("players", []):
        if p.get("position") not in ("QB", "RB", "WR", "TE"):
            continue
        team = normalize_team(p.get("team"))
        if not team or team == "FA":
            continue
        stats = p.get("stats") or {}
        bucket = projected.setdefault(team, {"pass_attempts": 0.0, "rush_attempts": 0.0})
        bucket["pass_attempts"] += float(stats.get("pass_attempts", 0.0))
        bucket["rush_attempts"] += float(stats.get("rush_attempts", 0.0))

    prior = _prior_actual_attempts_by_team(season)

    tendency = {}
    for team, bucket in projected.items():
        total = bucket["pass_attempts"] + bucket["rush_attempts"]
        pass_rate = round(bucket["pass_attempts"] / total, 4) if total > 0 else None

        # Prior-season attempts are summed over OUR player pool, not the whole
        # league. A team whose starting QB has since retired or fallen out of
        # the pool loses his pass attempts entirely and reads as absurdly
        # run-heavy (Miami came out at 0.217 before this guard). Rather than
        # publish a number that is right for some teams and badly wrong for
        # others, we only report a prior rate when the team's recovered
        # attempt volume is plausible for a real NFL season.
        prior_bucket = prior.get(team)
        prior_rate = None
        prior_coverage = "missing"
        if prior_bucket:
            prior_total = prior_bucket["pass_attempts"] + prior_bucket["rush_attempts"]
            prior_pass = prior_bucket["pass_attempts"]
            if prior_total >= MIN_PRIOR_TEAM_PLAYS and prior_pass >= MIN_PRIOR_TEAM_PASSES:
                prior_rate = round(prior_pass / prior_total, 4)
                prior_coverage = "ok"
            elif prior_total > 0:
                prior_coverage = "incomplete"

        tendency[team] = {
            "projected_pass_attempts": round(bucket["pass_attempts"], 1),
            "projected_rush_attempts": round(bucket["rush_attempts"], 1),
            "projected_pass_rate": pass_rate,
            "prior_actual_pass_rate": prior_rate,
            "prior_coverage": prior_coverage,
        }
    return tendency


# A real NFL team runs ~1000 offensive plays and throws ~450+ times a season.
# Anything materially below that means our pool simply lost players.
MIN_PRIOR_TEAM_PLAYS = 700
MIN_PRIOR_TEAM_PASSES = 350


# -- Main -----------------------------------------------------------------------
def run(projections: dict, force_refresh: bool = False) -> dict:
    sleeper = fetch_sleeper_players(force_refresh=force_refresh)
    by_team_defense, by_name_team, by_name = build_sleeper_indexes(sleeper)

    players_out: dict[str, dict] = {}
    match_counts = {"team_defense": 0, "name_team": 0, "name_only": 0,
                     "ambiguous": 0, "unmatched": 0}
    unmatched_names = []

    for p in projections.get("players", []):
        pid = str(p.get("player_id"))
        rec, method = match_player(p, by_team_defense, by_name_team, by_name)
        match_counts[method] = match_counts.get(method, 0) + 1

        if rec is None:
            depth = dict(UNKNOWN_DEPTH)
            depth["match_method"] = method
            unmatched_names.append((p.get("name"), p.get("position"), p.get("team")))
        else:
            position = p.get("position")  # trust ESPN's position for role mapping
            depth = sleeper_record_to_depth(rec)
            depth["role"] = resolve_role(position, rec.get("depth_chart_order"))
            depth["match_method"] = method

        players_out[pid] = depth

    total = len(projections.get("players", []))
    matched = total - match_counts["unmatched"] - match_counts["ambiguous"]
    match_rate = round(matched / total, 4) if total else 0.0

    team_tendency = compute_team_tendency(projections)

    result = {
        "players": players_out,
        "match_stats": {
            "total": total,
            "matched": matched,
            "match_rate": match_rate,
            **{k: v for k, v in match_counts.items()},
        },
        "team_tendency": team_tendency,
    }

    out = INTERMEDIATE_DIR / "depth.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info("Matched %d/%d (%.1f%%) — %s", matched, total, match_rate * 100, match_counts)
    if unmatched_names:
        logger.warning("Unmatched (%d): %s", len(unmatched_names),
                        ", ".join(f"{n} ({pos}/{team})" for n, pos, team in unmatched_names[:20]))
    logger.info("Saved -> %s", out)
    return result


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser(description="Join Sleeper depth-chart/injury/age data onto our player pool")
    ap.add_argument("--force-refresh", action="store_true", help="Re-fetch the Sleeper player pool instead of using the cache")
    args = ap.parse_args()

    proj_path = INTERMEDIATE_DIR / "projections.json"
    with open(proj_path, encoding="utf-8") as f:
        projections_in = json.load(f)

    out = run(projections_in, force_refresh=args.force_refresh)

    # -- Verification report --------------------------------------------------
    board_path = INTERMEDIATE_DIR.parent / "board.json"
    top150_ids = set()
    if board_path.exists():
        with open(board_path, encoding="utf-8") as f:
            board = json.load(f)
        top150 = [pl for pl in board["players"] if pl.get("vor_rank", 10**9) <= 150]
        top150_ids = {str(pl["player_id"]) for pl in top150}
        id_to_name = {str(pl["player_id"]): (pl["name"], pl["position"], pl["team"], pl["vor_rank"])
                      for pl in top150}
        misses = [id_to_name[pid] for pid in top150_ids if out["players"][pid]["role"] == "UNKNOWN"]
        misses.sort(key=lambda x: x[3])
        print(f"\nTop-150 (by vor_rank) unmatched/UNKNOWN: {len(misses)} of {len(top150_ids)}")
        for name, pos, team, rank in misses:
            print(f"  #{rank:<4} {name:<25} {pos:<4} {team}")
    else:
        print("board.json not found — skipping top-150 miss report.")

    role_by_pos: dict[str, dict[str, int]] = {}
    for pid, d in out["players"].items():
        pos = None
        for p in projections_in["players"]:
            if str(p["player_id"]) == pid:
                pos = p["position"]
                break
        if pos is None:
            continue
        role_by_pos.setdefault(pos, {}).setdefault(d["role"], 0)
        role_by_pos[pos][d["role"]] += 1

    print("\nRole distribution by position:")
    for pos in sorted(role_by_pos):
        print(f"  {pos:<4} {role_by_pos[pos]}")

    tendency_sorted = sorted(
        ((team, t["projected_pass_rate"]) for team, t in out["team_tendency"].items()
         if t["projected_pass_rate"] is not None),
        key=lambda x: x[1], reverse=True,
    )
    print("\nMost pass-heavy (projected):")
    for team, rate in tendency_sorted[:5]:
        prior = out["team_tendency"][team]["prior_actual_pass_rate"]
        print(f"  {team:<4} {rate:.3f}  (prior actual: {prior})")
    print("Most run-heavy (projected):")
    for team, rate in tendency_sorted[-5:]:
        prior = out["team_tendency"][team]["prior_actual_pass_rate"]
        print(f"  {team:<4} {rate:.3f}  (prior actual: {prior})")
