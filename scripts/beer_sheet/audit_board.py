#!/usr/bin/env python3
"""
Read-only data-quality audit for the beer sheet draft board.

Checks board.json (300-player final board), intermediate/projections.json
(900-player upstream), and league.json (real Sleeper league settings) for
anything that would embarrass or mislead a human drafter mid-draft.

Usage: python scripts/beer_sheet/audit_board.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data", "beer_sheet")

BOARD_PATH = os.path.join(DATA, "board.json")
PROJ_PATH = os.path.join(DATA, "intermediate", "projections.json")
LEAGUE_PATH = os.path.join(DATA, "league.json")

RESULTS = []  # (severity, check_name, message)

VALID_POS = {"QB", "RB", "WR", "TE", "K", "DST"}
VALID_TEAMS = {
    "ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB",
    "HOU","IND","JAX","KC","LAC","LAR","LV","MIA","MIN","NE","NO","NYG",
    "NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS","FA",
}

# Single-season fantasy point records (rough, generous ceilings, full-PPR-ish)
# to flag "above historical record pace" projections.
RECORD_PACE = {
    "QB": 450.0,   # Lamar/Allen peak seasons ~400-420 in most formats
    "RB": 450.0,   # McCaffrey 2023 ~400 in PPR
    "WR": 420.0,   # peak WR seasons ~380-400
    "TE": 350.0,   # Kelce peak ~300
    "K": 200.0,
    "DST": 220.0,
}


def sev(level, check, msg):
    RESULTS.append((level, check, msg))


def load(path, label):
    if not os.path.exists(path):
        sev("FAIL", label, f"File missing: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_duplicates(players, label):
    by_id = Counter(p["player_id"] for p in players)
    dupe_ids = {pid: c for pid, c in by_id.items() if c > 1}
    if dupe_ids:
        examples = []
        for pid, c in list(dupe_ids.items())[:10]:
            names = [p["name"] for p in players if p["player_id"] == pid]
            examples.append(f"id={pid} x{c} ({names[0]})")
        sev("FAIL", f"Duplicates [{label}]",
            f"{len(dupe_ids)} player_id(s) appear more than once: " + "; ".join(examples))
    else:
        sev("PASS", f"Duplicates (by id) [{label}]", "No duplicate player_id values.")

    by_name_pos = Counter((p["name"], p["position"]) for p in players)
    dupe_np = {k: c for k, c in by_name_pos.items() if c > 1}
    if dupe_np:
        examples = [f"{name} ({pos}) x{c}" for (name, pos), c in list(dupe_np.items())[:10]]
        sev("FAIL", f"Duplicates by name+position [{label}]",
            f"{len(dupe_np)} name+position pair(s) repeat (possible ESPN id churn): " + "; ".join(examples))
    else:
        sev("PASS", f"Duplicates (by name+position) [{label}]", "No duplicate name+position pairs.")


def check_bye_weeks(players, label):
    bad = []
    for p in players:
        team = p.get("team", "")
        bye = p.get("bye_week", None)
        if team == "FA" or not team:
            continue  # free agents legitimately have no bye
        if bye is None or bye == 0:
            bad.append(f"{p['name']} ({p['position']}, {team}) bye_week={bye}")
        elif not (1 <= bye <= 18):
            bad.append(f"{p['name']} ({p['position']}, {team}) bye_week={bye} (out of range 1-18)")
    if bad:
        top = players_sorted_by_rank(players)
        bad_ranked = [b for b in bad if any(b.startswith(p["name"]) for p in top[:150])]
        level = "FAIL" if bad_ranked else "WARN"
        sev(level, f"Bye weeks [{label}]",
            f"{len(bad)} player(s) with real NFL teams have missing/invalid bye_week. "
            f"{len(bad_ranked)} of those are in the top-150 (draft-day traps). Examples: " + "; ".join(bad[:15]))
    else:
        sev("PASS", f"Bye weeks [{label}]", "All rostered (non-FA) players have a bye week in 1-18.")

    # unknown team codes
    unknown_teams = sorted({p.get("team", "") for p in players if p.get("team", "") not in VALID_TEAMS})
    if unknown_teams:
        sev("WARN", f"Unknown team codes [{label}]",
            f"Team codes not in known NFL set (or 'FA'): {unknown_teams}")


def check_position_sanity(players, label):
    issues = []
    for p in players:
        pos = p["position"]
        stats = p.get("stats", {}) or {}
        pass_yd = stats.get("pass_yards", 0) or 0
        pass_att = stats.get("pass_attempts", 0) or 0
        rec_yd = stats.get("rec_yards", 0) or 0
        rec = stats.get("receptions", 0) or 0
        rush_yd = stats.get("rush_yards", 0) or 0
        rush_att = stats.get("rush_attempts", 0) or 0

        if pos == "QB":
            if rec_yd > 50 or rec > 5:
                issues.append(f"{p['name']} (QB) has rec_yards={rec_yd} receptions={rec} (receiving-dominant for a QB)")
            if pass_att < 5 and pass_yd < 50 and (rush_att > 20 or rush_yd > 100):
                # rushing QB with almost no passing at all is suspicious unless a pure gadget/rookie
                pass  # too noisy to flag hard; skip
        elif pos in ("RB", "WR", "TE"):
            if pass_yd > 50 or pass_att > 3:
                issues.append(f"{p['name']} ({pos}) has pass_yards={pass_yd} pass_attempts={pass_att} (passing stats on a non-QB)")
        if pos not in VALID_POS:
            issues.append(f"{p['name']} has invalid position '{pos}'")

    if issues:
        sev("FAIL" if len(issues) else "WARN", f"Position sanity [{label}]",
            f"{len(issues)} player(s) with stats contradicting their listed position: " + "; ".join(issues[:15]))
    else:
        sev("PASS", f"Position sanity [{label}]", "No QB/RB/WR/TE stat-position contradictions found.")


def check_projection_sanity(players, label, is_board):
    negatives = [p for p in players if p.get("proj_points", 0) < 0]
    if negatives:
        sev("FAIL", f"Negative projections [{label}]",
            f"{len(negatives)} player(s) with negative proj_points: " +
            "; ".join(f"{p['name']} ({p['proj_points']})" for p in negatives[:10]))
    else:
        sev("PASS", f"Negative projections [{label}]", "No negative proj_points.")

    over_record = []
    for p in players:
        cap = RECORD_PACE.get(p["position"])
        if cap and p.get("proj_points", 0) > cap:
            over_record.append(f"{p['name']} ({p['position']}) proj_points={p['proj_points']} > record-pace cap {cap}")
    if over_record:
        sev("WARN", f"Above historical record pace [{label}]",
            f"{len(over_record)} player(s) projected above a generous single-season record ceiling: " +
            "; ".join(over_record[:10]))
    else:
        sev("PASS", f"Above historical record pace [{label}]", "No projections exceed generous record-pace ceilings.")

    if is_board:
        ranked = players_sorted_by_rank(players)
        top200 = ranked[:200]
        zero_top200 = [p for p in top200 if p.get("proj_points", 0) == 0]
        if zero_top200:
            sev("FAIL", f"Zero projection in top 200 [{label}]",
                f"{len(zero_top200)} player(s) rank in the top 200 but have proj_points == 0: " +
                "; ".join(f"{p['name']} (vor_rank={p.get('vor_rank')})" for p in zero_top200[:10]))
        else:
            sev("PASS", f"Zero projection in top 200 [{label}]", "No top-200 player has proj_points == 0.")


def players_sorted_by_rank(players):
    if all("vor_rank" in p for p in players):
        return sorted(players, key=lambda p: p.get("vor_rank", 10**9))
    return sorted(players, key=lambda p: -(p.get("proj_points") or 0))


def check_injury_status(players, label):
    ranked = players_sorted_by_rank(players)
    top150 = ranked[:150]
    non_active = [p for p in top150 if p.get("injury_status", "ACTIVE") not in ("ACTIVE", None, "")]
    if non_active:
        examples = [f"{p['name']} ({p['position']}, rank={p.get('vor_rank', '?')}) status={p['injury_status']}" for p in non_active]
        sev("WARN" if len(non_active) < 5 else "FAIL", f"Injury status in top 150 [{label}]",
            f"{len(non_active)} non-ACTIVE player(s) in top 150 with no visual flag guaranteed on the sheet: " +
            "; ".join(examples[:20]))
    else:
        sev("PASS", f"Injury status in top 150 [{label}]", "All top-150 players are ACTIVE.")


def check_coverage(board_players, league):
    starters = league["roster"]["starters"]
    flex = league["roster"].get("flex", 0)
    flex_eligible = set(league["roster"].get("flex_eligible", []))
    teams = league["roster"]["teams"]

    pos_counts = defaultdict(int)
    for p in board_players:
        if p.get("proj_points", 0) > 0 and p.get("vor", -1) is not None:
            pos_counts[p["position"]] += 1

    problems = []
    for pos, need in starters.items():
        required_pool = teams * need
        have = pos_counts.get(pos, 0)
        # positive-VOR players specifically
        positive_vor = sum(1 for p in board_players if p["position"] == pos and (p.get("vor") or -1) > 0)
        if have < required_pool:
            problems.append(f"{pos}: need >= {required_pool} draftable ({teams} teams x {need} starters), board has {have} with proj_points>0 ({positive_vor} with positive VOR)")

    if flex and flex_eligible:
        flex_pool = sum(pos_counts.get(pos, 0) for pos in flex_eligible)
        flex_starters_pool = sum(teams * starters.get(pos, 0) for pos in flex_eligible)
        needed_for_flex = flex_starters_pool + teams * flex
        if flex_pool < needed_for_flex:
            problems.append(f"FLEX ({'/'.join(sorted(flex_eligible))}): need >= {needed_for_flex} combined ({teams} teams x {flex} flex + dedicated starters), board has {flex_pool}")

    if problems:
        sev("FAIL", "Positional coverage", "; ".join(problems))
    else:
        detail = ", ".join(f"{pos}={pos_counts.get(pos,0)}" for pos in ("QB","RB","WR","TE","K","DST"))
        sev("PASS", "Positional coverage", f"Enough draftable players at every starting position for {teams} teams. Counts: {detail}")


def check_rookies(players, label):
    rookies = [p for p in players if p.get("is_rookie")]
    by_pos = Counter(p["position"] for p in rookies)
    n = len(rookies)
    # A typical NFL draft class is ~260 picks across all rounds/positions that
    # matter for fantasy (QB/RB/WR/TE) is usually 60-110 fantasy-relevant rookies
    # show up in a 900-player pool; sanity band is wide on purpose.
    level = "PASS"
    note = ""
    if n == 0:
        level = "FAIL"
        note = " Zero rookies flagged is implausible for a fresh 2026 class — likely a missing/broken is_rookie flag upstream."
    elif n > 250:
        level = "WARN"
        note = " Unusually high rookie count for this pool size — check is_rookie logic for false positives."
    sev(level, f"Rookie count [{label}]",
        f"{n} players flagged is_rookie=true out of {len(players)}. By position: {dict(by_pos)}.{note}")


def check_weekly_points_length(players, label):
    lengths = Counter(len(p.get("weekly_points", [])) for p in players)
    if len(lengths) > 1 or (lengths and 17 not in lengths):
        sev("WARN", f"weekly_points length [{label}]",
            f"CONTRACT.md specifies 17 entries (one per week) but observed length distribution: {dict(lengths)}. "
            f"Off-by-one here would misalign week-of-bye zeroing.")
    else:
        sev("PASS", f"weekly_points length [{label}]", "weekly_points arrays match contract length.")


def main():
    board = load(BOARD_PATH, "board.json")
    proj = load(PROJ_PATH, "projections.json")
    league = load(LEAGUE_PATH, "league.json")

    if board:
        bp = board["players"]
        check_duplicates(bp, "board")
        check_bye_weeks(bp, "board")
        check_position_sanity(bp, "board")
        check_projection_sanity(bp, "board", is_board=True)
        check_injury_status(bp, "board")
        check_rookies(bp, "board")
        if league:
            check_coverage(bp, league)

    if proj:
        pp = proj["players"]
        check_duplicates(pp, "projections")
        check_bye_weeks(pp, "projections")
        check_position_sanity(pp, "projections")
        check_projection_sanity(pp, "projections", is_board=False)
        check_weekly_points_length(pp, "projections")

    # Print report
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    RESULTS.sort(key=lambda r: order[r[0]])
    print("=" * 100)
    print("BEER SHEET DATA-QUALITY AUDIT")
    print("=" * 100)
    for level, check, msg in RESULTS:
        print(f"\n[{level}] {check}")
        print(f"  {msg}")

    n_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
    n_warn = sum(1 for r in RESULTS if r[0] == "WARN")
    n_pass = sum(1 for r in RESULTS if r[0] == "PASS")
    print("\n" + "=" * 100)
    print(f"SUMMARY: {n_fail} FAIL, {n_warn} WARN, {n_pass} PASS")
    print("=" * 100)


if __name__ == "__main__":
    main()
