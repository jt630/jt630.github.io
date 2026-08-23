"""
Value Agent — converts projections into replacement-level VOR and auction $.

The whole point of this agent is that replacement level is NOT "the Nth best
player at each position." With flex spots, some of the players who fill flex
slots are RBs or WRs who would otherwise have been drafted well past a naive
per-position cutoff — that pushes true replacement level deeper than the
naive cutoff suggests, and by a different amount at each flex-eligible
position (RB tends to eat more flex slots than TE, for example, because RB
depth degrades faster).

`solve_replacement_levels` finds the real cutoff with a greedy starter-fill
simulation instead of guessing:

  1. Sort every player league-wide by proj_points, descending.
  2. Walk the list once. Each player fills the highest-priority open slot
     they're eligible for across the whole league:
       - a dedicated slot at their position first (teams x starters[pos]
         total slots per position), then
       - a flex slot (teams x flex total slots), if their position is
         flex-eligible and a dedicated slot wasn't open.
     A player who fits neither is not a starter — they're waiver/bench
     fodder and don't touch replacement level.
  3. Stop once every dedicated slot and every flex slot is full (or players
     run out). Because it's one league-wide sort, this reproduces what 12
     teams drafting starters would do WITHOUT needing to model 12 separate
     rosters or a draft order — the slot math is identical either way.
  4. For each position, replacement level = proj_points of the LAST player
     who filled a slot (dedicated or flex) at that position. Positional
     rank = how many players of that position were consumed as starters
     (dedicated + flex) to get there.

K and DST never touch flex (FLEX_ELIGIBLE excludes them), so their
replacement level is always just "the Nth kicker/defense," identical to the
naive cutoff. QB is flex-eligible only in superflex rosters; in a standard
1-QB league it also collapses to the naive cutoff for the same reason.

`--baseline` runs the naive fixed-cutoff version for comparison: replacement
rank is always exactly teams x starters[pos], with no flex-driven bump for
RB/WR/TE. Both are logged so the difference is visible.

Auction dollars: total league money is teams x auction_budget. Every
rosterable slot (starters + flex + bench, across all teams) is reserved $1
first — that's the CONTRACT's roster-price floor. Whatever's left over
("surplus") is handed out to the drafted pool (the top teams x total_slots
players by VOR) in proportion to positive VOR. Players outside that
draftable pool, or with VOR <= 0 inside it, are $1 players.

K/DST confidence discount: raw VOR for K and DST is real but not
actionable — see config.CONFIDENCE_DISCOUNT for why. `compute_vor` shrinks
their projected point total by that discount before subtracting the
(undiscounted) replacement level, to produce the `vor` field actually used
for ranking/pricing, while keeping the undiscounted number in `vor_raw` so
nothing is silently lost. The shrink is multiplicative, so it doesn't
disturb the ordering (and therefore tiering) within K or within DST.

ADP reliability: `compute_value_delta` only diffs vor_rank against ADP rank
for players within a realistic draft pool (see config.REAL_ADP_POOL_MULTIPLIER).
Players outside it get value_delta = 0 instead of a manufactured signal —
see that function's docstring for why ranking against the full player pool
is dishonest.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import INTERMEDIATE_DIR, ROSTER, DEFAULT_ROSTER, CONFIDENCE_DISCOUNT, REAL_ADP_POOL_MULTIPLIER

logger = logging.getLogger("value_agent")

UNDRAFTED_ADP = 999.0


# ── Replacement level ───────────────────────────────────────────────────────

def solve_replacement_levels(projections: dict, roster: dict) -> tuple[dict, dict]:
    """
    Greedy starter-fill simulation (see module docstring). Returns
    (replacement_levels, replacement_ranks), both keyed by position.
    """
    players = projections["players"]
    starters: dict = roster["starters"]
    flex_capacity = roster["teams"] * roster["flex"]
    flex_eligible = set(roster["flex_eligible"])

    dedicated_capacity = {pos: roster["teams"] * n for pos, n in starters.items()}
    dedicated_filled = {pos: 0 for pos in dedicated_capacity}
    flex_filled = 0

    assigned_count = {pos: 0 for pos in dedicated_capacity}
    last_points = {pos: 0.0 for pos in dedicated_capacity}

    total_slots = sum(dedicated_capacity.values()) + flex_capacity
    total_assigned = 0

    ordered = sorted(players, key=lambda p: p["proj_points"], reverse=True)

    for p in ordered:
        pos = p["position"]
        if pos not in dedicated_capacity:
            continue  # position not in this roster format at all

        assigned = False
        if dedicated_filled[pos] < dedicated_capacity[pos]:
            dedicated_filled[pos] += 1
            assigned = True
        elif pos in flex_eligible and flex_filled < flex_capacity:
            flex_filled += 1
            assigned = True

        if assigned:
            assigned_count[pos] += 1
            last_points[pos] = p["proj_points"]
            total_assigned += 1

        if total_assigned >= total_slots:
            break

    if total_assigned < total_slots:
        logger.warning(
            "Player pool exhausted before starting lineups filled (%d/%d slots). "
            "Replacement levels for shallow positions may be unreliable.",
            total_assigned, total_slots,
        )

    return last_points, assigned_count


def solve_replacement_levels_naive(projections: dict, roster: dict) -> tuple[dict, dict]:
    """
    Fixed-cutoff baseline: replacement rank is always exactly
    teams x starters[pos], with flex slots ignored entirely. Provided for
    comparison against the flex-aware simulation via --baseline.
    """
    players = projections["players"]
    starters: dict = roster["starters"]
    by_pos: dict[str, list[float]] = {}
    for p in players:
        by_pos.setdefault(p["position"], []).append(p["proj_points"])

    levels, ranks = {}, {}
    for pos, n in starters.items():
        pts = sorted(by_pos.get(pos, []), reverse=True)
        cutoff_rank = roster["teams"] * n
        idx = min(cutoff_rank, len(pts)) - 1
        levels[pos] = pts[idx] if idx >= 0 else 0.0
        ranks[pos] = min(cutoff_rank, len(pts))
    return levels, ranks


# ── VOR, ranks, auction $ ───────────────────────────────────────────────────

def _adp_sort_key(p: dict) -> float:
    adp = p.get("adp", UNDRAFTED_ADP)
    return UNDRAFTED_ADP if adp is None or adp >= UNDRAFTED_ADP else adp


def compute_vor(players: list[dict], replacement_levels: dict) -> list[dict]:
    """
    Attach vor, vor_rank, pos_rank to each player (new dicts, not mutated).

    `vor_raw` is proj_points - replacement_levels[position], full stop — the
    textbook definition. `vor` is what's actually used for ranking and
    auction pricing: for every position except K/DST it's identical to
    vor_raw. For K/DST, config.CONFIDENCE_DISCOUNT shrinks the PROJECTED
    POINT TOTAL first, then subtracts the (undiscounted) replacement level:
    (proj_points x discount) - level. See config.py for why that has to
    apply to the point total rather than the VOR delta to reliably sort
    K/DST below the skill-position pool. Keeping vor_raw around means the
    discount is auditable instead of a silent overwrite.
    """
    out = []
    for p in players:
        pos = p["position"]
        level = replacement_levels.get(pos, 0.0)
        vor_raw = round(p["proj_points"] - level, 2)
        discount = CONFIDENCE_DISCOUNT.get(pos)
        if discount is None:
            vor = vor_raw
        else:
            vor = round(p["proj_points"] * discount - level, 2)
        out.append({**p, "vor_raw": vor_raw, "vor": vor})

    out.sort(key=lambda p: p["vor"], reverse=True)
    for i, p in enumerate(out, start=1):
        p["vor_rank"] = i

    by_pos: dict[str, list[dict]] = {}
    for p in out:
        by_pos.setdefault(p["position"], []).append(p)
    for pos_players in by_pos.values():
        pos_players.sort(key=lambda p: p["proj_points"], reverse=True)
        for i, p in enumerate(pos_players, start=1):
            p["pos_rank"] = i

    return out


def compute_auction_values(players: list[dict], roster: dict) -> None:
    """
    Mutate `players` in place, adding auction_value. Reserves $1/slot across
    the whole league, then distributes the surplus to the draftable pool
    (top total_slots players by VOR) proportional to positive VOR.
    """
    teams = roster["teams"]
    total_slots_per_team = sum(roster["starters"].values()) + roster["flex"] + roster["bench"]
    total_roster_slots = teams * total_slots_per_team

    total_money = teams * roster["auction_budget"]
    reserved = total_roster_slots * 1
    surplus = max(total_money - reserved, 0)

    pool = sorted(players, key=lambda p: p["vor"], reverse=True)[:total_roster_slots]
    pool_ids = {id(p) for p in pool}
    pos_vor_sum = sum(p["vor"] for p in pool if p["vor"] > 0)

    for p in players:
        if id(p) in pool_ids and p["vor"] > 0 and pos_vor_sum > 0:
            share = p["vor"] / pos_vor_sum
            p["auction_value"] = round(1 + share * surplus, 0)
        else:
            p["auction_value"] = 1.0


def compute_value_delta(players: list[dict], roster: dict) -> None:
    """
    Mutate `players` in place, adding value_delta = adp_rank - vor_rank.

    Ranking the FULL player pool (~900) by ADP is dishonest: ESPN reports
    some averageDraftPosition-derived number for nearly every player, but
    past real draft depth it degenerates into a smooth, essentially
    meaningless curve where hundreds of players compress into a narrow band
    (a real pull had ~750 of 900 players packed into a 20-point ADP range).
    Their relative order among themselves is noise, not signal, so diffing
    it against vor_rank manufactures huge fake "value" deltas (a kicker
    nobody will draft "our #128 vs ADP #836" reads as a massive buy signal
    and isn't one).

    Fix: adp_rank is still computed across the whole pool (cheap, and other
    code may want it), but value_delta is only populated for players who
    fall within a realistic draft pool — config.REAL_ADP_POOL_MULTIPLIER x
    the league's own roster capacity (teams x total roster slots). That
    caps how deep a "real" market signal is trusted to go, with headroom
    past the exact roster count for legitimate late-round/waiver signal
    (handcuffs, rookie sleepers). Players outside that window get
    value_delta = 0 (no signal, not a fabricated one) and
    has_real_adp = False, so the sheet can tell the difference.
    """
    total_slots_per_team = sum(roster["starters"].values()) + roster["flex"] + roster["bench"]
    real_adp_pool_size = round(roster["teams"] * total_slots_per_team * REAL_ADP_POOL_MULTIPLIER)

    by_adp = sorted(players, key=_adp_sort_key)
    for i, p in enumerate(by_adp, start=1):
        p["adp_rank"] = i
        p["has_real_adp"] = i <= real_adp_pool_size and _adp_sort_key(p) < UNDRAFTED_ADP

    for p in players:
        p["value_delta"] = (p["adp_rank"] - p["vor_rank"]) if p["has_real_adp"] else 0


# ── Entry point ──────────────────────────────────────────────────────────────

def run(projections: dict, roster: dict, use_baseline: bool = False) -> dict:
    """
    Build the PlayerValue output (see CONTRACT.md). Always logs both the
    flex-aware simulation and the naive baseline for comparison; `use_baseline`
    controls which one is actually used to compute VOR/auction values.
    """
    sim_levels, sim_ranks = solve_replacement_levels(projections, roster)
    naive_levels, naive_ranks = solve_replacement_levels_naive(projections, roster)

    logger.info("Replacement levels — flex-aware simulation vs. naive fixed cutoff:")
    for pos in sim_levels:
        logger.info(
            "  %-4s sim: %6.1f pts @ rank %-3d   naive: %6.1f pts @ rank %-3d   (+%d players deep)",
            pos, sim_levels[pos], sim_ranks[pos],
            naive_levels.get(pos, 0.0), naive_ranks.get(pos, 0),
            sim_ranks[pos] - naive_ranks.get(pos, 0),
        )

    replacement_levels, replacement_ranks = (naive_levels, naive_ranks) if use_baseline else (sim_levels, sim_ranks)

    valued = compute_vor(projections["players"], replacement_levels)
    compute_auction_values(valued, roster)
    compute_value_delta(valued, roster)

    out_players = [
        {
            "player_id": p["player_id"],
            "vor": p["vor"],
            "vor_raw": p["vor_raw"],
            "vor_rank": p["vor_rank"],
            "pos_rank": p["pos_rank"],
            "auction_value": p["auction_value"],
            "value_delta": p["value_delta"],
            "has_real_adp": p["has_real_adp"],
        }
        for p in valued
    ]
    out_players.sort(key=lambda p: p["vor_rank"])

    # replacement_ranks in CONTRACT.md's example only lists the 4 skill
    # positions (QB/RB/WR/TE) — K/DST are included too since they're computed
    # the same way and downstream agents may want them.
    result = {
        "replacement_levels": {pos: round(v, 1) for pos, v in replacement_levels.items()},
        "replacement_ranks": replacement_ranks,
        "players": out_players,
    }

    out = INTERMEDIATE_DIR / "values.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info("Saved %d player values -> %s", len(out_players), out)

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser(description="Solve replacement levels and compute VOR / auction values")
    ap.add_argument("--projections", default=str(INTERMEDIATE_DIR / "projections.json"),
                     help="Path to intermediate/projections.json")
    ap.add_argument("--roster", default=DEFAULT_ROSTER, choices=sorted(ROSTER),
                     help="Roster preset from config.ROSTER")
    ap.add_argument("--baseline", action="store_true",
                     help="Use the naive fixed-cutoff replacement levels instead of the flex-aware simulation")
    args = ap.parse_args()

    with open(args.projections, encoding="utf-8") as f:
        loaded_projections = json.load(f)

    run(loaded_projections, ROSTER[args.roster], use_baseline=args.baseline)
