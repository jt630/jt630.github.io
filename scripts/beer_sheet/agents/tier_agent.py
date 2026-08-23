"""
Tier Agent — groups each position into draft-day tiers by VOR.

Tiers are computed WITHIN a position (RB1, RB2, ... not "overall tier 7").
Players in a position group are sorted by vor descending, then walked in
order tracking the gap to the next player.

── Root cause of the "every tier has exactly 2 players" bug ──────────────
The old algorithm computed ONE global threshold per position: the MEDIAN
gap across the ENTIRE group, including the hundreds of deep sub-replacement
players every position carries (bench/waiver fodder with VOR clustered
near, at, or below zero and near-zero consecutive gaps). That long flat
tail dragged the median gap down to something tiny, so `threshold =
median_gap * gap_multiplier` came out tiny too -- small enough that almost
EVERY gap among the actually-draftable players exceeded it, real cliffs
and 1-point noise alike.

With the gap test satisfied almost everywhere, the only thing left
deciding where breaks actually landed was `min_tier_size`. That guardrail
was written as "close the tier the instant it reaches N members and the
gap test passes" rather than as a floor on how small a tier is ALLOWED to
be -- so with a gap test that was satisfied on turn 1 (n=1, gate blocks)
and turn 2 (n=2, gate opens) essentially every time, it fired like
clockwork every 2 players regardless of whether the gap was 30.7 (a real
cliff) or 1.1 (noise). `max_tiers_per_position` was mostly a non-factor in
this failure -- the pairing was already locked in well before the cap.

── Fix ─────────────────────────────────────────────────────────────────
1. VOR gaps are large at the top of a position and compress toward the
   bottom, so a single global (even non-median) threshold can't serve both
   ends -- a gap that's a huge cliff at the bottom of the board is tiny
   next to the RB1/RB2 gap. Breaks are now decided by a RELATIVE gap: the
   raw gap divided by a buffer-shifted VOR scale local to that pair, not a
   single number compared against the whole group.
2. The long sub-replacement tail is excluded from tier-break math
   entirely, not just down-weighted. Players are "relevant" (roughly
   positive VOR, plus a buffer -- see tail_buffer_fraction) or they are
   not; irrelevant players are bucketed into one final tier ("this is the
   waiver wire, not draft rounds") instead of being allowed to warp the
   threshold for the players who matter.
3. `min_tier_size` is now a genuine floor, not a trigger: a borderline
   break (just over threshold) is suppressed if it would leave a tier
   smaller than the floor. A HARD cliff (>= hard_cliff_multiplier x
   threshold) always breaks regardless of the floor -- a real 30-point
   cliff must never be hidden just because the tier above it is short.

── Round 2: the gap test alone isn't enough ──────────────────────────────
The gap test only ever looks at the space BETWEEN two neighbors. A long
run of gaps that each individually fall under the relative threshold can
still chain together into a tier that spans a huge VOR range -- e.g. a
14-player RB tier running from VOR 127.8 down to 66.5 (a ~45-60 point
spread), where the top and bottom of that "tier" are not remotely
interchangeable even though no single gap inside it looked like a cliff.
A tier is supposed to mean "roughly indifferent, safe to wait" -- a wide
spread breaks that promise even with zero individual bad breaks.

So after the gap test forms initial tiers, each one is checked against
`max_tier_spread_fraction` (a fraction of the position's top VOR): if a
tier's spread (max vor - min vor) exceeds that, it's recursively split at
its OWN largest internal gap -- not the relative threshold, just "cut
where this group is least cohesive" -- until every resulting tier fits
the spread cap or can't be split further (single player). This is what
pulls Achane out of a tier with Josh Jacobs even though the individual
Achane-Cook gap (15.0) was a borderline, non-hard-cliff call under the
gap test alone.

Splitting for spread naturally produces MORE tiers in the draftable
range, so `max_tiers_per_position` was raised (12 -> 20) to stop it from
fighting the spread constraint. If a position still ends up over the cap
after both passes, adjacent tiers are merged back together starting at
whichever boundary has the SMALLEST gap, until the count fits -- i.e. the
cap gives up the least-justified breaks first.

`min_tier_size` (the floor) only governs the gap-test pass; the spread
split intentionally overrides it, including down to singletons, because a
tier that's provably too wide is a bigger error than a tier that's short.

tier_label is "<POS><tier number>", e.g. "RB1", "RB2" -- position-relative,
never an overall rank. tier_break_after=true marks the last player of a
tier; the sheet layout draws a divider line there.

Output: data/beer_sheet/intermediate/tiers.json
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import INTERMEDIATE_DIR, TIERS

logger = logging.getLogger("tier_agent")


def _relevant_count(vors: list) -> tuple[int, float]:
    """
    Split a position group (sorted by vor descending) into a "relevant"
    prefix and a sub-replacement tail.

    A player is relevant if their VOR is above -(buffer), where buffer is
    a fraction of the group's top VOR (tail_buffer_fraction). This keeps
    the cutoff proportional to how big this position's value spread is,
    rather than one fixed point value that would be huge for RB/WR and
    meaningless for K/DST.

    Returns (relevant_count, buffer_vor).
    """
    if not vors:
        return 0, 1.0

    top_vor = vors[0]
    buffer_vor = max(top_vor * TIERS["tail_buffer_fraction"], 1.0) if top_vor > 0 else 1.0
    cutoff = -buffer_vor

    relevant_count = len(vors)
    for idx, v in enumerate(vors):
        if v <= cutoff:
            relevant_count = idx
            break

    # Always keep at least the top player "relevant" even in a degenerate
    # all-negative group.
    return max(relevant_count, 1), buffer_vor


def _gap_test_breaks(vors: list, relevant_count: int, buffer_vor: float) -> set:
    """
    Pass 1: the relative-gap test. Returns a set of break indices `i`
    meaning "break after ordered[i]", restricted to the relevant prefix
    [0, relevant_count).
    """
    shift = buffer_vor + 1.0
    threshold = TIERS["gap_relative_threshold"]
    hard_mult = TIERS["hard_cliff_multiplier"]
    min_size = TIERS["min_tier_size"]

    breaks = set()
    current_tier_start = 0
    for i in range(relevant_count - 1):
        gap = vors[i] - vors[i + 1]
        denom = vors[i + 1] + shift
        rel_gap = gap / denom if denom > 0 else 0.0

        current_tier_size = i - current_tier_start + 1
        remaining_relevant = relevant_count - (i + 1)
        is_hard_cliff = rel_gap >= threshold * hard_mult
        meets_threshold = rel_gap > threshold

        # min_tier_size is a FLOOR: a borderline break is skipped if the
        # tier being closed is still under the floor. A hard cliff always
        # wins -- a real cliff is never hidden to satisfy a size floor.
        would_break = meets_threshold and (current_tier_size >= min_size or is_hard_cliff)
        # Likewise, don't open a new tier we can't fill to the floor with
        # what's left in the relevant range, unless it's a hard cliff or
        # we're at the very end of the relevant range (a short final tier
        # there is fine).
        would_break = would_break and (
            remaining_relevant >= min_size or remaining_relevant == 0 or is_hard_cliff
        )

        if would_break:
            breaks.add(i)
            current_tier_start = i + 1

    return breaks


def _split_for_spread(vors: list, start: int, end: int, max_spread: float, breaks: set) -> None:
    """
    Pass 2: recursively add break indices to `breaks` so that the VOR
    spread of every sub-range within [start, end] (inclusive indices) is
    at most max_spread. Splits at the LARGEST internal gap each time --
    not the relative threshold from pass 1 -- because the goal here isn't
    "is this gap a cliff," it's "cut this group wherever it's least
    cohesive until it's narrow enough to call interchangeable."
    """
    if end <= start:
        return
    spread = vors[start] - vors[end]
    if spread <= max_spread:
        return

    split_at = max(range(start, end), key=lambda i: vors[i] - vors[i + 1])
    breaks.add(split_at)
    _split_for_spread(vors, start, split_at, max_spread, breaks)
    _split_for_spread(vors, split_at + 1, end, max_spread, breaks)


def _enforce_max_tiers(vors: list, break_list: list, max_tiers: int) -> list:
    """
    Pass 3 (safety valve): if the two passes above produced more tiers
    than max_tiers_per_position allows, merge adjacent tiers back
    together -- always removing whichever break has the SMALLEST actual
    VOR gap first, so the cap gives up the least-justified break before
    touching a real cliff.
    """
    breaks = sorted(break_list)
    while len(breaks) + 1 > max_tiers and breaks:
        weakest = min(breaks, key=lambda i: vors[i] - vors[i + 1])
        breaks.remove(weakest)
    return breaks


def tier_position_group(players: list) -> list:
    """
    Assign tiers within one position group.

    `players` is a list of dicts each with at least player_id and vor,
    already belonging to a single position, in any order. Returns the same
    players sorted by vor descending, each annotated with tier,
    tier_break_after, and tier_gap (gap to next player, for the summary).
    """
    ordered = sorted(players, key=lambda p: p["vor"], reverse=True)
    n = len(ordered)
    if n == 0:
        return []

    vors = [p["vor"] for p in ordered]
    relevant_count, buffer_vor = _relevant_count(vors)
    max_tiers = TIERS["max_tiers_per_position"]
    max_spread = max(vors[0], 0.0) * TIERS["max_tier_spread_fraction"] if vors[0] > 0 else 0.0

    breaks = set()
    if relevant_count > 1:
        breaks |= _gap_test_breaks(vors, relevant_count, buffer_vor)

        # Apply the spread cap within each tier the gap test just formed
        # (not across the whole relevant range at once -- a break the gap
        # test already made is real and must be preserved).
        if max_spread > 0:
            tier_starts = [0] + [b + 1 for b in sorted(breaks)]
            tier_ends = sorted(breaks) + [relevant_count - 1]
            for start, end in zip(tier_starts, tier_ends):
                _split_for_spread(vors, start, end, max_spread, breaks)

    # relevant_count - 1 is the last index of the relevant range; if a
    # tail exists, that boundary is always a break (falling off the
    # draftable range is a real cliff by definition), independent of
    # max_tiers -- it's added after the cap so it can never be merged
    # away.
    has_tail = relevant_count < n
    breaks = _enforce_max_tiers(vors, list(breaks), max_tiers)
    breaks = set(breaks)
    if has_tail and relevant_count >= 1:
        breaks.add(relevant_count - 1)

    tier_num = 1
    for i, player in enumerate(ordered):
        player["tier"] = tier_num
        player["tier_break_after"] = False

        is_last_overall = i == n - 1
        if is_last_overall:
            player["tier_gap"] = 0.0
            break

        gap = vors[i] - vors[i + 1]
        player["tier_gap"] = round(gap, 1)

        if i >= relevant_count:
            # Sub-replacement players never split further -- they ride
            # out the final tier together, however many there are.
            continue

        if i in breaks:
            player["tier_break_after"] = True
            tier_num += 1

    return ordered


def _summarize(position: str, tiered_players: list) -> list:
    """Build the tier_summary entries for one position: tier/count/vor_range."""
    summary = []
    by_tier: dict[int, list] = {}
    for p in tiered_players:
        by_tier.setdefault(p["tier"], []).append(p["vor"])

    for tier_num in sorted(by_tier):
        vors = by_tier[tier_num]
        summary.append({
            "tier": tier_num,
            "count": len(vors),
            "vor_range": [round(min(vors), 1), round(max(vors), 1)],
        })

    logger.info(
        "%s: %d tiers -> %s",
        position, len(summary),
        ", ".join(f"T{s['tier']}(n={s['count']}, {s['vor_range']})" for s in summary),
    )
    return summary


def run(projections: dict, values: dict) -> dict:
    """
    Tier every player within their position by VOR and write
    intermediate/tiers.json in the PlayerTier shape.
    """
    position_by_id = {p["player_id"]: p["position"] for p in projections.get("players", [])}
    value_by_id = {v["player_id"]: v for v in values.get("players", [])}

    groups: dict[str, list] = {}
    for player_id, position in position_by_id.items():
        val = value_by_id.get(player_id)
        if val is None:
            continue
        groups.setdefault(position, []).append({
            "player_id": player_id,
            "vor": val.get("vor", 0.0),
        })

    all_players = []
    tier_summary: dict[str, list] = {}

    for position, group in groups.items():
        tiered = tier_position_group(group)
        for p in tiered:
            all_players.append({
                "player_id": p["player_id"],
                "tier": p["tier"],
                "tier_label": f"{position}{p['tier']}",
                "tier_break_after": p["tier_break_after"],
            })
        tier_summary[position] = _summarize(position, tiered)

    out_payload = {"players": all_players, "tier_summary": tier_summary}

    out = INTERMEDIATE_DIR / "tiers.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, indent=2)
    logger.info("Saved %d tiered players across %d positions -> %s",
                len(all_players), len(tier_summary), out)

    return out_payload


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    proj_path = INTERMEDIATE_DIR / "projections.json"
    values_path = INTERMEDIATE_DIR / "values.json"
    with open(proj_path, encoding="utf-8") as f:
        projections_in = json.load(f)
    with open(values_path, encoding="utf-8") as f:
        values_in = json.load(f)
    run(projections_in, values_in)
