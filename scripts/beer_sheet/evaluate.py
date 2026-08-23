"""
Evaluate Agent — scores a frozen snapshot against real end-of-season results.

Joins a snapshot.py output to ESPN's post-season "actuals" (statSourceId=0,
statSplitTypeId=0, seasonId=<season>, the same stat-entry shape
projection_agent.py already reads for the PRIOR season — after the season in
the snapshot completes, that same entry exists for the snapshot's own season
too) and reports how good the frozen board actually was. The fetch logic
below is a deliberate COPY of fetch_agent.py's request pattern (URL, headers,
paging), not an import — that file is being actively edited by another agent
this session, and evaluate.py runs long after the season anyway, so it has
no reason to depend on projection_agent.py's current internals.

Metrics reported (see each function's docstring for the exact definition):
  - value-weighted error (and plain MAE, for contrast)
  - Spearman rank correlation, both league-wide and within the drafted range
  - per-position breakdown of both of the above
  - risk-band calibration (floor/ceiling hit rate)
  - head-to-head: our vor_rank vs. the market's adp_rank

STATUS: the 2026 season has not been played. Every metric here has been
validated only against SYNTHETIC actuals derived from the real snapshot
(see `--self-test` / `_self_test()` below) — proving the math behaves
correctly (perfect predictions score near-optimal, corrupted predictions
score worse, calibration reacts to band width) is NOT the same as validating
against real outcomes, which cannot happen before the 2026 season ends. Do
not treat a self-test pass as evidence the MODEL is good; it only proves the
SCORING CODE is not lying to you. Real validation happens in January 2027.
"""

import argparse
import json
import logging
import random
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("evaluate")

# -- ESPN actuals fetch (copied pattern from fetch_agent.py; see module docstring) --
BASE_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
    "{season}/segments/0/leaguedefaults/3?view=kona_player_info"
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}
PAGE_SIZE = 300
ACTUAL_SOURCE_ID = 0
ACTUAL_SPLIT_ID = 0


def _filter_header(limit: int, offset: int) -> str:
    return json.dumps({
        "players": {"limit": limit, "offset": offset,
                    "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "PPR"}}
    })


def fetch_actuals(season: int, scoring: dict, position_overrides: dict | None = None,
                  max_players: int = 900) -> dict[int, dict]:
    """
    Pull completed-season actual production from ESPN and re-score it under
    the FROZEN scoring rules (from the snapshot, not whatever config.py says
    today — a league's scoring can change year to year).

    Returns {player_id: {"actual_points": float, "actual_components": {...}}}.
    Only meaningful once `season` has actually finished.
    """
    collected: list[dict] = []
    seen: set[int] = set()
    for offset in range(0, max_players, PAGE_SIZE):
        req = urllib.request.Request(BASE_URL.format(season=season))
        for k, v in HEADERS.items():
            req.add_header(k, v)
        req.add_header("x-fantasy-filter", _filter_header(PAGE_SIZE, offset))
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            logger.error("ESPN returned HTTP %s at offset %s", exc.code, offset)
            break
        page = payload.get("players", [])
        if not page:
            break
        new = 0
        for entry in page:
            pid = entry.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            collected.append(entry)
            new += 1
        if new == 0:
            break

    out: dict[int, dict] = {}
    overrides = position_overrides or {}
    for entry in collected:
        p = entry.get("player") or {}
        pid = p.get("id")
        if pid is None:
            continue
        position = config.POSITION_MAP.get(p.get("defaultPositionId"))
        actual_entry = None
        for s in (p.get("stats") or []):
            if (s.get("statSourceId") == ACTUAL_SOURCE_ID
                    and s.get("statSplitTypeId") == ACTUAL_SPLIT_ID
                    and s.get("seasonId") == season):
                actual_entry = s
                break
        raw = (actual_entry or {}).get("stats") or {}
        components = {
            config.STAT_MAP[str(k)]: float(v)
            for k, v in raw.items() if str(k) in config.STAT_MAP
        }
        if position in ("K", "DST"):
            points = float((actual_entry or {}).get("appliedTotal") or 0.0)
        else:
            rates = dict(scoring)
            if position in overrides:
                rates.update(overrides[position])
            points = sum(components.get(name, 0.0) * rate for name, rate in rates.items()
                        if name in components)
        out[pid] = {"actual_points": round(points, 2), "actual_components": components}
    return out


# -- Metrics ------------------------------------------------------------------

def value_weight(vor_rank: int) -> float:
    """
    Weight assigned to a player's error when computing value-weighted error.

    weight = 1 / vor_rank  (harmonic decay on OUR rank, not the market's).

    Rationale: a beer sheet's whole purpose is guiding draft picks, and a
    draft pick's cost is not linear in rank — the #3 player is a 1st-round
    decision, the #180 player is "whoever's left on the waiver wire." A flat
    MAE across all 300 players treats a bust at #3 the same as a bust at
    #180, which is exactly backwards for a tool meant to inform early picks.
    1/rank makes that explicit and steep: player #3 gets ~60x the weight of
    player #180 (1/3 vs 1/180), and ~2x the weight of player #6. This is
    harsher than, say, 1/sqrt(rank) — deliberately, because the cost of a
    wrong 1st-round pick (a roster slot, a season) really is that much
    higher than a wrong 15th-round dart throw, not just moderately higher.
    """
    return 1.0 / max(vor_rank, 1)


def weighted_mae(pairs: list[tuple[float, float, float]]) -> tuple[float, float]:
    """pairs = [(predicted, actual, weight), ...]. Returns (plain_mae, weighted_mae)."""
    if not pairs:
        return 0.0, 0.0
    errors = [abs(pred - act) for pred, act, _ in pairs]
    plain = sum(errors) / len(errors)
    total_w = sum(w for _, _, w in pairs)
    weighted = sum(abs(pred - act) * w for pred, act, w in pairs) / total_w if total_w else 0.0
    return round(plain, 3), round(weighted, 3)


def _rank_values(values: dict[int, float], ascending: bool = True) -> dict[int, float]:
    """Average-rank (competition-safe) ranking of a {id: value} dict. Rank 1 = smallest value if ascending."""
    items = sorted(values.items(), key=lambda kv: kv[1], reverse=not ascending)
    ranks: dict[int, float] = {}
    i = 0
    n = len(items)
    while i < n:
        j = i
        while j < n and items[j][1] == items[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0  # average of ranks i+1..j
        for k in range(i, j):
            ranks[items[k][0]] = avg_rank
        i = j
    return ranks


def spearman(a: dict[int, float], b: dict[int, float]) -> float | None:
    """Spearman rank correlation between two {id: value} dicts, over shared ids."""
    ids = sorted(set(a) & set(b))
    if len(ids) < 3:
        return None
    ra = _rank_values({i: a[i] for i in ids})
    rb = _rank_values({i: b[i] for i in ids})
    xs = [ra[i] for i in ids]
    ys = [rb[i] for i in ids]
    if statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
        return None
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom = (sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys)) ** 0.5
    return round(cov / denom, 4) if denom else None


def actual_vor(position: str, actual_points: float, replacement_levels: dict,
               confidence_discount: dict) -> float:
    """
    Actual points converted to the same VOR basis vor_rank was computed on
    (frozen replacement_levels + the K/DST confidence discount from the
    snapshot), so rank correlation compares like with like.

    This matters for two reasons, not one:
      1. Sign: vor_rank is "1 = best" (ascending), while raw actual_points is
         "bigger = better." Correlating those two conventions directly
         inverts the sign of the result — a PERFECT model would show up as
         strongly NEGATIVE, which is backwards and would be read as "the
         model is anti-predictive."
      2. Scale: raw points aren't comparable across positions (a mediocre QB
         outscores a great TE in raw points every year). vor_rank already
         nets out replacement level per position; actual_points does not.
         Ranking predicted VOR against raw actual points would show
         "disagreement" that is really just position scale, not a real
         prediction miss. Putting actual results on the same VOR basis
         removes that artifact.
    """
    level = replacement_levels.get(position, 0.0) if replacement_levels else 0.0
    discount = (confidence_discount or {}).get(position)
    if discount is None:
        return actual_points - level
    return actual_points * discount - level


def drafted_range_size(league: dict | None) -> int:
    """Actual roster capacity (teams x total roster slots) — the real drafted pool, not the ADP-trust window."""
    roster = (league or {}).get("roster") or {}
    if not roster:
        return 180  # 12 teams x 15-man roster, this league's real number, as a fallback
    starters = roster.get("starters", {})
    total_per_team = sum(starters.values()) + roster.get("flex", 0) + roster.get("bench", 0)
    return roster.get("teams", 12) * total_per_team


# Assumed target coverage for risk-band calibration. risk_agent.py's module
# docstring does NOT commit to a specific statistical coverage for
# floor/ceiling (band_base/band_max are heuristic fractions of proj_points,
# not derived from a confidence level) — there is no documented ground truth
# to grade against. 80% is a judgment call made HERE, treating the band as
# roughly analogous to a central 80% interval, a common default when a
# forecaster gives a range without naming a confidence level. Change this
# constant, don't pretend it's more authoritative than it is.
ASSUMED_BAND_COVERAGE = 0.80


def evaluate(snapshot: dict, actuals: dict[int, dict]) -> dict:
    players = snapshot["players"]
    league = snapshot.get("league")
    drafted_size = drafted_range_size(league)

    replacement_levels = snapshot.get("replacement_levels") or {}
    confidence_discount = (snapshot.get("config_constants") or {}).get("CONFIDENCE_DISCOUNT") or {}

    joined = []
    for p in players:
        pid = p.get("player_id")
        a = actuals.get(pid)
        if a is None or p.get("vor_rank") is None:
            continue
        position = p.get("position")
        # Negated so it shares vor_rank/adp_rank's "1 = best, ascending"
        # convention — see actual_vor()'s docstring for why both the sign
        # flip and the VOR conversion (not raw points) matter here.
        neg_actual_vor = -actual_vor(position, a["actual_points"], replacement_levels, confidence_discount)
        joined.append({
            "player_id": pid,
            "name": p.get("name"),
            "position": position,
            "proj_points": p.get("proj_points", 0.0) or 0.0,
            "actual_points": a["actual_points"],
            "neg_actual_vor": neg_actual_vor,
            "vor_rank": p["vor_rank"],
            "adp_rank": p.get("adp_rank"),
            "has_real_adp": p.get("has_real_adp", False),
            "floor_points": p.get("floor_points"),
            "ceiling_points": p.get("ceiling_points"),
        })

    n_total = len(players)
    n_joined = len(joined)
    if n_joined == 0:
        raise SystemExit("No players joined between snapshot and actuals — nothing to evaluate.")

    # -- value-weighted error --------------------------------------------------
    pairs = [(j["proj_points"], j["actual_points"], value_weight(j["vor_rank"])) for j in joined]
    plain_mae, weighted_mae_val = weighted_mae(pairs)

    # -- rank correlation: full pool vs. drafted range --------------------------
    vor_rank_map = {j["player_id"]: j["vor_rank"] for j in joined}
    actual_vor_map = {j["player_id"]: j["neg_actual_vor"] for j in joined}
    spearman_full = spearman(vor_rank_map, actual_vor_map)

    drafted_joined = sorted(joined, key=lambda j: j["vor_rank"])[:drafted_size]
    drafted_vor_map = {j["player_id"]: j["vor_rank"] for j in drafted_joined}
    drafted_actual_map = {j["player_id"]: j["neg_actual_vor"] for j in drafted_joined}
    spearman_drafted = spearman(drafted_vor_map, drafted_actual_map)

    # -- per-position breakdown --------------------------------------------------
    by_position: dict[str, list[dict]] = {}
    for j in joined:
        by_position.setdefault(j["position"], []).append(j)

    position_report = {}
    for pos, plist in sorted(by_position.items()):
        pos_pairs = [(j["proj_points"], j["actual_points"], value_weight(j["vor_rank"])) for j in plist]
        p_mae, p_wmae = weighted_mae(pos_pairs)
        pos_vor = {j["player_id"]: j["vor_rank"] for j in plist}
        pos_actual = {j["player_id"]: j["neg_actual_vor"] for j in plist}
        position_report[pos] = {
            "n": len(plist),
            "mae": p_mae,
            "weighted_mae": p_wmae,
            "spearman": spearman(pos_vor, pos_actual),
        }

    # -- risk band calibration ---------------------------------------------------
    banded = [j for j in joined if j["floor_points"] is not None and j["ceiling_points"] is not None]
    hits = sum(1 for j in banded if j["floor_points"] <= j["actual_points"] <= j["ceiling_points"])
    hit_rate = round(hits / len(banded), 3) if banded else None
    if hit_rate is None:
        calibration_verdict = "no risk-band data to evaluate"
    elif hit_rate > ASSUMED_BAND_COVERAGE + 0.10:
        calibration_verdict = (
            f"bands look TOO WIDE — {hit_rate:.0%} of actuals landed inside the band, "
            f"well above the assumed {ASSUMED_BAND_COVERAGE:.0%} target"
        )
    elif hit_rate < ASSUMED_BAND_COVERAGE - 0.15:
        calibration_verdict = (
            f"bands look TOO NARROW — only {hit_rate:.0%} of actuals landed inside the band, "
            f"well below the assumed {ASSUMED_BAND_COVERAGE:.0%} target"
        )
    else:
        calibration_verdict = f"bands look roughly calibrated ({hit_rate:.0%} vs. assumed {ASSUMED_BAND_COVERAGE:.0%} target)"

    # -- head-to-head: our vor_rank vs. the market's adp_rank -------------------
    h2h_pool = [j for j in drafted_joined if j["has_real_adp"] and j["adp_rank"]]
    our_vor = {j["player_id"]: j["vor_rank"] for j in h2h_pool}
    market_adp = {j["player_id"]: j["adp_rank"] for j in h2h_pool}
    actual_pts = {j["player_id"]: j["neg_actual_vor"] for j in h2h_pool}
    our_corr = spearman(our_vor, actual_pts)
    market_corr = spearman(market_adp, actual_pts)

    if our_corr is None or market_corr is None:
        verdict = "INCONCLUSIVE — not enough players with real ADP in the drafted range"
    else:
        gap = our_corr - market_corr
        if abs(gap) < 0.03:
            verdict = f"TOO CLOSE TO CALL — our correlation {our_corr:+.3f} vs. ADP's {market_corr:+.3f} (n={len(h2h_pool)}, single-season — see sweep.py for bootstrap uncertainty)"
        elif gap > 0:
            verdict = f"WE BEAT ADP — our correlation {our_corr:+.3f} vs. ADP's {market_corr:+.3f} (n={len(h2h_pool)})"
        else:
            verdict = f"ADP BEAT US — market correlation {market_corr:+.3f} vs. ours {our_corr:+.3f} (n={len(h2h_pool)}). The model is decorative if this holds up."

    return {
        "n_total_snapshot_players": n_total,
        "n_joined_with_actuals": n_joined,
        "drafted_range_size": drafted_size,
        "mae": plain_mae,
        "weighted_mae": weighted_mae_val,
        "spearman_full_pool": spearman_full,
        "spearman_drafted_range": spearman_drafted,
        "spearman_gap_note": (
            "spearman_full_pool is typically HIGHER than spearman_drafted_range. "
            "The long sub-replacement tail (ranks past the drafted range) is "
            "compressed near zero for both projection and outcome — everyone "
            "agrees those players are worthless, which inflates whole-pool "
            "correlation without reflecting any real predictive skill where it "
            "matters. spearman_drafted_range is the honest number."
        ),
        "by_position": position_report,
        "risk_band_hit_rate": hit_rate,
        "risk_band_assumed_target": ASSUMED_BAND_COVERAGE,
        "risk_band_verdict": calibration_verdict,
        "head_to_head_our_spearman": our_corr,
        "head_to_head_market_spearman": market_corr,
        "head_to_head_verdict": verdict,
    }


def print_report(report: dict) -> None:
    print("=" * 72)
    print("EVALUATION REPORT")
    print("=" * 72)
    print(f"Players joined to actuals: {report['n_joined_with_actuals']} of {report['n_total_snapshot_players']}")
    print(f"Drafted-range size (real roster capacity): {report['drafted_range_size']}")
    print()
    print(f"MAE (unweighted):        {report['mae']}")
    print(f"Value-weighted MAE:      {report['weighted_mae']}  (weight = 1/vor_rank; see value_weight() docstring)")
    print()
    print(f"Spearman, full pool:     {report['spearman_full_pool']}")
    print(f"Spearman, drafted range: {report['spearman_drafted_range']}")
    print(f"  -> {report['spearman_gap_note']}")
    print()
    print("Per-position:")
    for pos, r in report["by_position"].items():
        print(f"  {pos:4s} n={r['n']:3d}  MAE={r['mae']:7.2f}  weighted_MAE={r['weighted_mae']:7.2f}  spearman={r['spearman']}")
    print()
    print(f"Risk band hit rate: {report['risk_band_hit_rate']}  (assumed target: {report['risk_band_assumed_target']})")
    print(f"  -> {report['risk_band_verdict']}")
    print()
    print("*" * 72)
    print(f"HEAD-TO-HEAD vs ADP: {report['head_to_head_verdict']}")
    print("*" * 72)


# -- Synthetic-actuals self-test (see module docstring) -----------------------

def build_synthetic_actuals(snapshot: dict, noise_std_frac: float = 0.15,
                            corrupt: bool = False, perfect: bool = False,
                            seed: int | None = 42) -> dict[int, dict]:
    """
    Fabricate an "actuals" payload shaped like fetch_actuals()'s output, from
    the snapshot's own proj_points plus controlled noise. Used ONLY to prove
    the metric code behaves correctly — never a substitute for real outcomes.

    perfect=True   -> actual == proj_points exactly (noise_std_frac ignored)
    corrupt=True   -> actual = proj_points scaled by a hostile, rank-scrambling
                       transform (reverses value_delta-style ordering within
                       position) PLUS the requested noise, to simulate "the
                       model was badly wrong"
    otherwise      -> actual = proj_points + Gaussian noise with stdev =
                       noise_std_frac * proj_points
    """
    rng = random.Random(seed)
    out: dict[int, dict] = {}
    by_position: dict[str, list[dict]] = {}
    for p in snapshot["players"]:
        by_position.setdefault(p["position"], []).append(p)

    for pos, plist in by_position.items():
        ordered = sorted(plist, key=lambda p: p.get("proj_points", 0.0) or 0.0, reverse=True)
        n = len(ordered)
        for idx, p in enumerate(ordered):
            proj = p.get("proj_points", 0.0) or 0.0
            if perfect:
                actual = proj
            elif corrupt:
                # Swap this player's point total with the total from the
                # opposite end of the SAME position's projected order, then
                # still add noise. Wrecks rank correlation and error alike.
                mirror = ordered[n - 1 - idx]
                base = mirror.get("proj_points", 0.0) or 0.0
                noise = rng.gauss(0, max(noise_std_frac, 0.15) * max(proj, 1.0))
                actual = max(base + noise, 0.0)
            else:
                noise = rng.gauss(0, noise_std_frac * max(proj, 1.0))
                actual = max(proj + noise, 0.0)
            out[p["player_id"]] = {"actual_points": round(actual, 2), "actual_components": {}}
    return out


def _self_test() -> None:
    """Prove the metrics behave correctly. Raises AssertionError on failure."""
    snap_files = sorted((config.DATA_DIR / "snapshots").glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not snap_files:
        raise SystemExit("No snapshot found to self-test against. Run snapshot.py first.")
    with open(snap_files[-1], encoding="utf-8") as f:
        snapshot = json.load(f)

    perfect_actuals = build_synthetic_actuals(snapshot, perfect=True)
    perfect_report = evaluate(snapshot, perfect_actuals)
    assert perfect_report["mae"] < 0.01, f"perfect predictions should have ~0 MAE, got {perfect_report['mae']}"
    assert perfect_report["weighted_mae"] < 0.01, "perfect predictions should have ~0 weighted MAE"
    # Not exactly 1.0: vor_rank was computed upstream from proj_points values
    # rounded to 2dp at several pipeline stages, so a handful of near-tied
    # players can swap order between the frozen vor_rank and a freshly
    # recomputed actual_vor even though actual == proj exactly. >0.97 is
    # still decisively "near-optimal" for a perfect-information board.
    assert perfect_report["spearman_drafted_range"] > 0.97, (
        f"perfect predictions should have spearman ~1.0, got {perfect_report['spearman_drafted_range']}"
    )
    # >=0.99 rather than exactly 1.0: floor_points/ceiling_points are stored
    # rounded to 1 decimal place while proj_points is rounded to 2, so a
    # handful of near-zero-point waiver-fodder players (proj ~0.1-0.2) can
    # land a rounding hair outside their own band even though actual ==
    # proj_points exactly upstream. That's independent-rounding noise on
    # irrelevant players, not a calibration failure.
    assert perfect_report["risk_band_hit_rate"] >= 0.99, (
        f"actual == proj_points should fall inside the band for ~all players, got hit_rate={perfect_report['risk_band_hit_rate']}"
    )
    logger.info("[self-test] PASS: perfect board scores near-optimal")

    noisy_actuals = build_synthetic_actuals(snapshot, noise_std_frac=0.15)
    noisy_report = evaluate(snapshot, noisy_actuals)
    assert noisy_report["weighted_mae"] > perfect_report["weighted_mae"], (
        "moderate noise should score worse than perfect predictions"
    )
    logger.info("[self-test] PASS: noisy board scores worse than perfect board "
                "(weighted_mae %.2f > %.2f)", noisy_report["weighted_mae"], perfect_report["weighted_mae"])

    corrupt_actuals = build_synthetic_actuals(snapshot, corrupt=True)
    corrupt_report = evaluate(snapshot, corrupt_actuals)
    assert corrupt_report["weighted_mae"] > noisy_report["weighted_mae"], (
        "deliberately corrupted (rank-reversed) board must score worse than merely noisy"
    )
    assert (corrupt_report["spearman_drafted_range"] is None
            or corrupt_report["spearman_drafted_range"] < noisy_report["spearman_drafted_range"]), (
        "corrupted board's rank correlation must be worse than the noisy board's"
    )
    logger.info("[self-test] PASS: corrupted board scores worse than noisy board "
                "(weighted_mae %.2f > %.2f, spearman %.3f < %.3f)",
                corrupt_report["weighted_mae"], noisy_report["weighted_mae"],
                corrupt_report["spearman_drafted_range"] or -1, noisy_report["spearman_drafted_range"] or -1)

    logger.info("[self-test] ALL CHECKS PASSED (synthetic actuals only — see module docstring)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate a beer sheet snapshot against real (or synthetic) outcomes")
    ap.add_argument("--snapshot", help="Path to a snapshot.py output. Defaults to the most recent one.")
    ap.add_argument("--live", action="store_true", help="Fetch real actuals from ESPN for the snapshot's season")
    ap.add_argument("--self-test", action="store_true", help="Run the synthetic-actuals validation suite and exit")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    if args.snapshot:
        snap_path = Path(args.snapshot)
    else:
        snap_files = sorted((config.DATA_DIR / "snapshots").glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not snap_files:
            raise SystemExit("No snapshots found. Run snapshot.py first, or pass --snapshot.")
        snap_path = snap_files[-1]
        logger.info("No --snapshot given, using most recent: %s", snap_path.name)

    with open(snap_path, encoding="utf-8") as f:
        snapshot = json.load(f)

    if args.live:
        season = snapshot["snapshot_meta"]["season"]
        scoring = (snapshot.get("league") or {}).get("scoring") or {}
        overrides = (snapshot.get("league") or {}).get("position_scoring_override") or {}
        logger.info("Fetching real ESPN actuals for season %d ...", season)
        actuals = fetch_actuals(season, scoring, overrides)
    else:
        logger.warning("No --live flag — using SYNTHETIC actuals (noise_std_frac=0.15). "
                       "Pass --live for a real evaluation once the season is over.")
        actuals = build_synthetic_actuals(snapshot, noise_std_frac=0.15)

    report = evaluate(snapshot, actuals)
    print_report(report)


if __name__ == "__main__":
    main()
