"""
Risk Agent — quantifies how much to trust each player's projection.

A single `risk_score` (0.0 = bankable, 1.0 = coin flip) is a blend of four
independent uncertainty signals, each contributing an additive penalty:

  1. Expert disagreement  (weight-leading signal)
     stdev(expert_ranks), normalized RELATIVE to the player's own mean rank.
     A stdev of 8 means something very different at rank 5 (total chaos —
     nobody agrees who this player even is) than at rank 200 (background
     noise in a sea of replacement-level guys). We express disagreement as
     a coefficient of variation on rank (stdev / mean_rank) so it's
     comparable across the whole board, then map that onto RISK's
     high_disagreement_stdev threshold scaled to the player's own rank.

  2. Injury status       — flat lookup, RISK["injury_penalty"].

  3. Weekly volatility    — coefficient of variation (stdev / mean) of the
     player's non-zero weekly_points. Two players can share a season total
     and differ completely in weekly shape; this is the only signal that
     catches that. Bye/zero weeks are excluded so a bye doesn't masquerade
     as a "bad week."

  4. Rookie flag          — a flat bump. Rookies have no prior_points to
     anchor a projection to, so even a confident scouting profile carries
     more unknown-unknowns than a proven vet with the same box-score line.

The four penalties are summed and clamped to [0, 1]. risk_label buckets the
final score. floor/ceiling points widen a band around proj_points sized
between RISK["band_base"] and RISK["band_max"] of proj_points, scaled by
risk_score — SAFE players get a tight band, VOLATILE players get a wide one.
Higher risk also skews the band slightly downside-heavy (more to lose than
to gain), since bust risk in fantasy is usually more available than boom
upside for players who already grade out as shaky.

Output: data/beer_sheet/intermediate/risk.json
"""

import json
import logging
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import INTERMEDIATE_DIR, RISK

logger = logging.getLogger("risk_agent")

# Weight given to each raw penalty before summing (must roughly balance so
# no single signal alone can saturate risk_score to 1.0).
DISAGREEMENT_WEIGHT = 0.40
INJURY_WEIGHT       = 1.00  # injury_penalty values are already final-scale
VOLATILITY_WEIGHT   = 0.35
ROOKIE_BUMP         = 0.10

# Weekly CV above this reads as "boom/bust"; below this reads as "steady."
VOLATILITY_BOOM_BUST_CV = 0.55
VOLATILITY_STEADY_CV    = 0.20

RISK_LABEL_THRESHOLDS = (
    (0.33, "SAFE"),
    (0.66, "MODERATE"),
)  # anything above the last threshold is VOLATILE


def _rank_disagreement(expert_ranks: list) -> tuple[float, float]:
    """
    Returns (raw_stdev, normalized_disagreement) for a player's expert ranks.

    normalized_disagreement is the rank stdev expressed relative to the
    player's own mean rank (coefficient of variation on rank), then scaled
    against RISK["high_disagreement_stdev"] so a CV that would be "high" for
    an early-round player also reads as high near the back of the board.
    """
    ranks = [r for r in (expert_ranks or []) if r]
    if len(ranks) < 2:
        return 0.0, 0.0
    stdev = statistics.pstdev(ranks)
    mean_rank = max(statistics.mean(ranks), 1.0)
    cv = stdev / mean_rank
    # A flat stdev of RISK["high_disagreement_stdev"] at mean rank ~50 is our
    # calibration anchor (roughly where CV history clusters for "volatile").
    anchor_cv = RISK["high_disagreement_stdev"] / 50.0
    normalized = min(cv / anchor_cv, 2.0) / 2.0  # clamp to [0, 1]
    return round(stdev, 1), normalized


def _weekly_volatility(weekly_points: list) -> float:
    """Coefficient of variation of non-zero weekly points, or 0.0 if too few."""
    played = [w for w in (weekly_points or []) if w and w > 0]
    if len(played) < 3:
        return 0.0
    mean = statistics.mean(played)
    if mean <= 0:
        return 0.0
    stdev = statistics.pstdev(played)
    return stdev / mean


def _risk_label(score: float) -> str:
    for threshold, label in RISK_LABEL_THRESHOLDS:
        if score < threshold:
            return label
    return "VOLATILE"


def _band_fraction(risk_score: float) -> float:
    """Interpolate band width between band_base and band_max by risk_score."""
    base, max_ = RISK["band_base"], RISK["band_max"]
    return base + (max_ - base) * risk_score


def _build_notes(
    expert_ranks: list,
    rank_stdev: float,
    disagreement_norm: float,
    injury_status: str,
    injury_pen: float,
    weekly_cv: float,
    is_rookie: bool,
) -> list[str]:
    notes = []

    ranks = [r for r in (expert_ranks or []) if r]
    if ranks and disagreement_norm >= 0.35:
        notes.append(f"experts split: ranks {min(ranks)}-{max(ranks)}")
    elif ranks and disagreement_norm < 0.12 and len(ranks) >= 2:
        notes.append("experts in lockstep")

    if injury_pen >= 0.10:
        notes.append(f"injury flag: {injury_status.replace('_', ' ').title()}")
    elif injury_status and injury_status != "ACTIVE" and injury_pen > 0:
        notes.append(f"injury watch: {injury_status.replace('_', ' ').title()}")

    if weekly_cv >= VOLATILITY_BOOM_BUST_CV:
        notes.append("boom/bust weekly profile")
    elif 0 < weekly_cv <= VOLATILITY_STEADY_CV:
        notes.append("steady week-to-week producer")

    if is_rookie:
        notes.append("rookie — no prior-season anchor")

    return notes


def score_player(player: dict) -> dict:
    """Compute the full PlayerRisk record for one PlayerProjection entry."""
    proj_points = player.get("proj_points", 0.0) or 0.0
    expert_ranks = player.get("expert_ranks", [])
    injury_status = player.get("injury_status", "ACTIVE") or "ACTIVE"
    is_rookie = bool(player.get("is_rookie", False))

    rank_stdev, disagreement_norm = _rank_disagreement(expert_ranks)
    injury_pen = RISK["injury_penalty"].get(injury_status, 0.0)
    weekly_cv = _weekly_volatility(player.get("weekly_points", []))
    volatility_norm = min(weekly_cv / VOLATILITY_BOOM_BUST_CV, 1.0) if weekly_cv else 0.0

    raw_score = (
        disagreement_norm * DISAGREEMENT_WEIGHT
        + injury_pen * INJURY_WEIGHT
        + volatility_norm * VOLATILITY_WEIGHT
        + (ROOKIE_BUMP if is_rookie else 0.0)
    )
    risk_score = round(min(max(raw_score, 0.0), 1.0), 3)
    label = _risk_label(risk_score)

    band_frac = _band_fraction(risk_score)
    # Skew the band downside-heavy as risk climbs: riskier players lose a bit
    # more on the floor than they gain on the ceiling.
    floor_frac = band_frac * (1.0 + 0.25 * risk_score)
    ceiling_frac = band_frac * (1.0 - 0.15 * risk_score)
    # The floor was clamped at zero but the ceiling was not, so a player with
    # a negative projection ended up with a ceiling BELOW his floor (Jamal
    # Agnew: floor 0.0, ceiling -0.7). Anchor the band on a non-negative base
    # and enforce floor <= proj <= ceiling explicitly rather than relying on
    # the arithmetic to preserve it.
    base = max(proj_points, 0.0)
    base_r = round(base, 1)
    floor_points = min(round(base * (1.0 - floor_frac), 1), base_r)
    ceiling_points = max(round(base * (1.0 + ceiling_frac), 1), floor_points)

    notes = _build_notes(
        expert_ranks, rank_stdev, disagreement_norm,
        injury_status, injury_pen, weekly_cv, is_rookie,
    )

    return {
        "player_id": player["player_id"],
        "risk_score": risk_score,
        "risk_label": label,
        "floor_points": floor_points,
        "ceiling_points": ceiling_points,
        "rank_disagreement": rank_stdev,
        "risk_notes": notes,
    }


def run(projections: dict) -> dict:
    """
    Score every player in a PlayerProjection payload and write
    intermediate/risk.json in the PlayerRisk shape.
    """
    players = projections.get("players", [])
    scored = [score_player(p) for p in players]

    label_counts: dict[str, int] = {}
    for p in scored:
        label_counts[p["risk_label"]] = label_counts.get(p["risk_label"], 0) + 1
    logger.info("Scored %d players — %s", len(scored), label_counts)

    out_payload = {"players": scored}

    out = INTERMEDIATE_DIR / "risk.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, indent=2)
    logger.info("Saved %d risk records -> %s", len(scored), out)

    return out_payload


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    proj_path = INTERMEDIATE_DIR / "projections.json"
    with open(proj_path, encoding="utf-8") as f:
        projections_in = json.load(f)
    run(projections_in)
