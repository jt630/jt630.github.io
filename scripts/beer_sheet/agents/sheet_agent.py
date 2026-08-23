"""
Sheet Agent — merges every upstream stage into the single file Hugo reads.

Downstream of this there is no more logic: the template renders exactly what
lands in board.json. So this is where we decide what a person staring at a
draft board actually needs, and where we throw away everything else.

Two deliberate reductions happen here:

  1. Only the top N players by VOR survive. The projection stage carries 900
     players because replacement level has to be computed against the full
     pool, but nobody drafts the 700th-ranked tight end.

  2. Per-week projections are dropped. They did their job upstream (the risk
     agent turned them into a volatility measure); shipping 18 floats per
     player to the browser would only make the page slower.

Output: data/beer_sheet/board.json  (see CONTRACT.md)
"""

import json
import logging
from datetime import datetime, timezone

from config import DATA_DIR, OUTPUT_FILE
import agents.blacklist_agent as blacklist_agent

logger = logging.getLogger("sheet_agent")

# How many players make the printed sheet. 12 teams x 15 roster spots = 180
# actually drafted; the extra covers waiver-bait and late-round dart throws.
BOARD_SIZE = 300

UNDRAFTED_ADP = 999.0


def scoring_summary(league: dict) -> str:
    """One-line, human-readable description of the league's scoring."""
    scoring = league.get("scoring") or {}
    rec = scoring.get("receptions", 0.0)
    label = {1.0: "Full PPR", 0.5: "Half PPR", 0.0: "Standard"}.get(rec, f"{rec}/rec")

    bits = [label]
    if scoring.get("pass_tds"):
        bits.append(f"{scoring['pass_tds']:.0f}pt pass TD")
    if scoring.get("pass_yards"):
        bits.append(f"1pt / {round(1 / scoring['pass_yards'])} pass yds")

    overrides = league.get("position_scoring_override") or {}
    for pos, rates in overrides.items():
        if "receptions" in rates and rates["receptions"] != rec:
            bits.append(f"{pos} premium ({rates['receptions']}/rec)")

    return " · ".join(bits)


def starters_summary(roster: dict) -> str:
    """e.g. QB / 2RB / 2WR / TE / 2FLEX / K / DST"""
    starters = roster.get("starters") or {}
    order = ["QB", "RB", "WR", "TE", "K", "DST"]
    parts = []
    for pos in order:
        count = starters.get(pos, 0)
        if count:
            parts.append(pos if count == 1 else f"{count}{pos}")
    flex = roster.get("flex", 0)
    if flex:
        # Flex sits between the skill slots and K/DST on a real lineup card.
        insert_at = len([p for p in parts if not p.endswith(("K", "DST"))])
        parts.insert(insert_at, "FLEX" if flex == 1 else f"{flex}FLEX")
    return " / ".join(parts)


def run(projections: dict, values: dict, risk: dict, tiers: dict,
        league: dict, board_size: int = BOARD_SIZE,
        depth: dict | None = None) -> dict:
    by_id = {p["player_id"]: p for p in projections["players"]}
    value_by_id = {v["player_id"]: v for v in values["players"]}
    risk_by_id = {r["player_id"]: r for r in risk["players"]}
    tier_by_id = {t["player_id"]: t for t in tiers["players"]}
    depth_players = (depth or {}).get("players") or {}
    depth_by_id = {int(k): v for k, v in depth_players.items()} if depth_players else {}

    # ADP rank is what value_delta is measured against, so the sheet should be
    # able to show it directly rather than making the reader infer it.
    drafted = sorted((p for p in projections["players"] if p["adp"] < UNDRAFTED_ADP),
                     key=lambda p: p["adp"])
    adp_rank_by_id = {p["player_id"]: i + 1 for i, p in enumerate(drafted)}

    merged = []
    for pid, proj in by_id.items():
        value = value_by_id.get(pid)
        if not value:
            continue
        r = risk_by_id.get(pid, {})
        t = tier_by_id.get(pid, {})

        merged.append({
            "player_id": pid,
            "name": proj["name"],
            "position": proj["position"],
            "team": proj["team"],
            "bye_week": proj["bye_week"],
            "injury_status": proj["injury_status"],
            "is_rookie": proj["is_rookie"],
            "component_blind": proj["component_blind"],

            "proj_points": proj["proj_points"],
            "espn_points": proj["espn_points"],
            "prior_points": proj["prior_points"],
            "market_points": proj["market_points"],
            "stats": proj["stats"],
            "outlook": proj["outlook"][:280],

            "vor": value["vor"],
            # Undiscounted VOR, preserved so the K/DST confidence discount
            # stays auditable rather than silently rewriting the number.
            "vor_raw": value.get("vor_raw", value["vor"]),
            "vor_rank": value["vor_rank"],
            "pos_rank": value["pos_rank"],
            "auction_value": value["auction_value"],
            "value_delta": value["value_delta"],

            "adp": proj["adp"],
            "adp_rank": adp_rank_by_id.get(pid, 0),
            # False when ADP is untrustworthy (outside the pool window, or
            # inside ESPN's compressed band). value_delta is meaningless then.
            "has_real_adp": value.get("has_real_adp", False),
            "auction_value_market": proj["auction_value_market"],

            "risk_score": r.get("risk_score", 0.0),
            "risk_label": r.get("risk_label", "MODERATE"),
            "floor_points": r.get("floor_points", 0.0),
            "ceiling_points": r.get("ceiling_points", 0.0),
            "rank_disagreement": r.get("rank_disagreement", 0.0),
            "risk_notes": r.get("risk_notes", []),

            # Depth chart: does he actually have a job? A backup with a good
            # projection and a starter with the same projection are not the
            # same asset.
            "role": depth_by_id.get(pid, {}).get("role", "UNKNOWN"),
            "depth_chart_order": depth_by_id.get(pid, {}).get("depth_chart_order"),
            "sleeper_injury_status": depth_by_id.get(pid, {}).get("sleeper_injury_status"),
            "injury_body_part": depth_by_id.get(pid, {}).get("injury_body_part"),
            "practice_participation": depth_by_id.get(pid, {}).get("practice_participation"),
            "age": depth_by_id.get(pid, {}).get("age"),

            "tier": t.get("tier", 0),
            "tier_label": t.get("tier_label", ""),
            "tier_break_after": t.get("tier_break_after", False),
        })

    merged.sort(key=lambda p: p["vor_rank"])

    # Blacklist runs BEFORE truncation: an EXCLUDE drops a player from the
    # pool entirely so a real player is promoted into the board rather than
    # leaving a hole at the bottom. FADE players stay in `merged` (flagged)
    # and ride along through truncation normally.
    merged, blacklist_summary = blacklist_agent.apply(merged)

    board_players = merged[:board_size]

    # A tier break on the last surviving player of a truncated list is a lie —
    # there is no next tier to divide from.
    if board_players:
        board_players[-1]["tier_break_after"] = False

    roster = league.get("roster") or {}
    board = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season": projections["season"],
        "scoring_name": projections["scoring_name"],
        "blend": projections.get("blend", {}),
        "league": {
            "name": league.get("league_name", "Unknown League"),
            "teams": roster.get("teams", 12),
            "scoring_summary": scoring_summary(league),
            "starters": starters_summary(roster),
            "bench": roster.get("bench", 0),
        },
        "replacement_levels": values["replacement_levels"],
        "replacement_ranks": values.get("replacement_ranks", {}),
        "tier_summary": tiers.get("tier_summary", {}),
        "team_tendency": (depth or {}).get("team_tendency", {}),
        "board_size": len(board_players),
        "total_pool": len(merged),
        "blacklist_summary": blacklist_summary,
        "players": board_players,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(board, f, indent=2)

    _log_summary(board)
    logger.info("Saved %d players -> %s", len(board_players), OUTPUT_FILE)
    return board


def _log_summary(board: dict) -> None:
    players = board["players"]
    logger.info("League: %s | %s | %s",
                board["league"]["name"], board["league"]["scoring_summary"],
                board["league"]["starters"])
    logger.info("Replacement levels: %s",
                {k: round(v, 1) for k, v in board["replacement_levels"].items()})

    logger.info("Top 15 by VOR:")
    for p in players[:15]:
        logger.info("  %2d. %-24s %-3s %-4s  VOR %6.1f  $%3d  ADP %5.1f  delta %+5d  %s",
                    p["vor_rank"], p["name"], p["position"], p["team"],
                    p["vor"], p["auction_value"], p["adp"], p["value_delta"],
                    p["tier_label"])

    # Both lists are restricted to above-replacement players (vor > 0). A
    # value_delta can only be a "bargain" or a "reach" for someone worth
    # rostering in the first place — being under/overrated relative to other
    # players nobody should draft either is not a signal, it's noise dressed
    # up as one. See value_agent.compute_value_delta for the matching guard
    # applied to the data itself (positive deltas are clamped to 0 for
    # sub-replacement players so the rendered board can't highlight them
    # green as buy signals).
    # A blacklisted (faded) player is never a "value" — they're on the board
    # but deliberately negated, so they're excluded from both lists here even
    # though they remain in `players` (see blacklist_agent).
    startable = [p for p in players[:150]
                if p["adp"] < UNDRAFTED_ADP and p["vor"] > 0 and not p.get("blacklisted")]

    bargains = sorted(startable, key=lambda p: -p["value_delta"])[:10]
    logger.info("Biggest values vs. market (positive = market underrates, above-replacement only):")
    for p in bargains:
        logger.info("  %-24s %-3s  our #%-3d  ADP #%-3d  delta %+d",
                    p["name"], p["position"], p["vor_rank"], p["adp_rank"], p["value_delta"])

    reaches = sorted(startable, key=lambda p: p["value_delta"])[:10]
    logger.info("Biggest reaches vs. market (negative = market overrates, above-replacement only):")
    for p in reaches:
        logger.info("  %-24s %-3s  our #%-3d  ADP #%-3d  delta %+d",
                    p["name"], p["position"], p["vor_rank"], p["adp_rank"], p["value_delta"])
