"""
Tier Agent — groups each position into draft-day tiers by VOR.

Tiers are computed WITHIN a position (RB1, RB2, ... not "overall tier 7").
Players in a position group are sorted by vor descending, then walked in
order tracking the gap to the next player. A tier break is declared when
that gap exceeds TIERS["gap_multiplier"] x the MEDIAN gap within the whole
position group — using the median (not mean) keeps one huge outlier gap
(e.g. the QB1/QB2 chasm) from inflating the threshold used everywhere else
in the group.

Two guardrails keep the algorithm from producing a useless tier list:
  - min_tier_size:          a break is skipped if it would leave the tier
                             being closed smaller than this floor. Prevents
                             singleton tiers from one noisy VOR gap.
  - max_tiers_per_position: once this many tiers exist, remaining breaks are
                             suppressed and everyone left rides out the last
                             tier. Keeps deep positions (WR/RB) from
                             fragmenting into 20 one-player "tiers" past the
                             point where the distinctions are meaningful.

tier_label is "<POS><tier number>", e.g. "RB1", "RB2" — position-relative,
never an overall rank. tier_break_after=true marks the last player of a
tier; the sheet layout draws a divider line there.

Output: data/beer_sheet/intermediate/tiers.json
"""

import json
import logging
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import INTERMEDIATE_DIR, TIERS

logger = logging.getLogger("tier_agent")


def _median_gap(sorted_vors: list) -> float:
    """Median of consecutive VOR gaps within a position group."""
    gaps = [sorted_vors[i] - sorted_vors[i + 1] for i in range(len(sorted_vors) - 1)]
    gaps = [g for g in gaps if g >= 0]
    if not gaps:
        return 0.0
    return statistics.median(gaps)


def tier_position_group(players: list) -> list:
    """
    Assign tiers within one position group.

    `players` is a list of dicts each with at least player_id and vor,
    already belonging to a single position, in any order. Returns the same
    players sorted by vor descending, each annotated with tier,
    tier_break_after, and tier_gap (gap to next player, for the summary).
    """
    ordered = sorted(players, key=lambda p: p["vor"], reverse=True)
    if not ordered:
        return []

    vors = [p["vor"] for p in ordered]
    median_gap = _median_gap(vors)
    threshold = median_gap * TIERS["gap_multiplier"]

    min_size = TIERS["min_tier_size"]
    max_tiers = TIERS["max_tiers_per_position"]

    tier_num = 1
    current_tier_start = 0
    for i, player in enumerate(ordered):
        player["tier"] = tier_num
        player["tier_break_after"] = False

        is_last = i == len(ordered) - 1
        if is_last:
            player["tier_gap"] = 0.0
            break

        gap = vors[i] - vors[i + 1]
        player["tier_gap"] = round(gap, 1)

        current_tier_size = i - current_tier_start + 1
        remaining_players = len(ordered) - (i + 1)

        would_break = gap > threshold and current_tier_size >= min_size
        # Don't open a new tier we can't fill to min_size, unless we're at
        # the very end of the group (a short final tier is fine).
        would_break = would_break and (
            remaining_players >= min_size or remaining_players == 0
        )
        can_open_new_tier = tier_num < max_tiers

        if would_break and can_open_new_tier:
            player["tier_break_after"] = True
            tier_num += 1
            current_tier_start = i + 1

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
