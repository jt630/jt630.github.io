"""
Sweep Agent — re-derives boards from a snapshot's frozen inputs under
alternative configurations, scores each with evaluate.py's metrics, and
ranks them WITH an honest uncertainty estimate.

Re-derivation logic (recompute_proj_points, recompute_vor) is a deliberate
COPY of the relevant pieces of projection_agent.py / value_agent.py, not an
import — those files are being actively edited by other agents this
session, and a sweep needs to be reproducible from the FROZEN snapshot
inputs regardless of what the live agents look like today or next month.
See each function's docstring for exactly which upstream formula it mirrors.

WHAT CAN BE SWEPT TODAY: BLEND weights (espn_projection / prior_actual /
market_implied), via `blend_grid()`. proj_points for each player is
recombined from the snapshot's already-frozen espn_points /
prior_points_scaled / market_points scalars — those three inputs don't
depend on BLEND, so no re-fetching or re-scoring is needed to sweep this
axis.

STRUCTURED FOR LATER: `recompute_vor` takes a `roster` dict and a
`replacement_fn` (defaults to the flex-aware greedy simulation, mirroring
value_agent.solve_replacement_levels) so a future session can add a sweep
axis over replacement-level method (flex-aware vs. naive) or roster
presets without touching the metric/bootstrap plumbing. TIERS parameters
are not consumed by any metric in evaluate.py (tiers are a display concept,
not a scoring one), so a tier sweep is out of scope here by design — the
hook point would be `config_constants["TIERS"]` in the snapshot, already
carried through unmodified for a future session that wants it.

STATISTICAL HONESTY: one season is n≈1 at the level that matters (~150-180
relevant, mutually correlated players, all drawn from the same NFL season).
That sample size cannot reliably distinguish "65/20/15 is better than
60/25/15" — the difference between two nearby configurations is very often
smaller than the noise from which specific players got hurt, benched, or
had a career year. Every comparison in this module reports a bootstrap
confidence interval (resampling PLAYERS with replacement — not weeks or
stats, so the correlation structure between a player's own numbers stays
intact) alongside the point estimate, and configurations whose intervals
overlap are explicitly flagged as statistically indistinguishable. Sorting
configs by point estimate and reporting the top one as "the winner" without
that caveat would launder noise into false confidence — which is worse than
having no harness at all, because a false winner gets acted on.

STATUS: written and self-tested (see `--self-test`) against SYNTHETIC
actuals derived from the real August 2026 snapshot. It has not been run
against a real completed season — that can't happen until January 2027.
"""

import argparse
import json
import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("sweep")


# ── Re-derivation (frozen-input copies of projection_agent.py / value_agent.py) ──

def recompute_proj_points(players: list[dict], blend: dict) -> list[dict]:
    """
    Recombine each player's ALREADY-FROZEN espn_points / prior_points_scaled
    (falls back to prior_points if a snapshot predates that field) /
    market_points under a new BLEND weighting. Mirrors
    projection_agent._blend's redistribution rule: players without a usable
    prior season (has_usable_prior False, or is_rookie True as a fallback
    for older snapshots) get prior_actual's weight folded into
    espn_projection rather than multiplied by zero and lost.

    Returns NEW dicts (does not mutate the snapshot's player list) with
    `proj_points` overwritten to reflect the new blend.
    """
    out = []
    for p in players:
        q = dict(p)
        if q.get("component_blind"):
            # K/DST: proj_points has always just been ESPN's own total, blend-independent.
            q["proj_points"] = q.get("espn_points", q.get("proj_points", 0.0))
            out.append(q)
            continue

        w = dict(blend)
        has_usable_prior = q.get("has_usable_prior")
        if has_usable_prior is None:
            has_usable_prior = not q.get("is_rookie", False)
        if not has_usable_prior:
            w["espn_projection"] = w.get("espn_projection", 0.0) + w.get("prior_actual", 0.0)
            w["prior_actual"] = 0.0

        prior = q.get("prior_points_scaled", q.get("prior_points", 0.0)) or 0.0
        espn_pts = q.get("espn_points", 0.0) or 0.0
        market = q.get("market_points", espn_pts) or 0.0

        q["proj_points"] = round(
            espn_pts * w.get("espn_projection", 0.0)
            + prior * w.get("prior_actual", 0.0)
            + market * w.get("market_implied", 0.0),
            2,
        )
        out.append(q)
    return out


def solve_replacement_levels(players: list[dict], roster: dict) -> dict[str, float]:
    """
    Flex-aware greedy starter-fill simulation — a deliberate copy of
    value_agent.solve_replacement_levels. See that function's docstring
    (read at the time this module was written) for the full rationale;
    summary: sort the whole pool by proj_points, walk it once, each player
    fills the highest-priority open slot they're eligible for (dedicated
    position slot first, then flex if eligible), replacement level per
    position = proj_points of the last player who filled a slot there.
    """
    starters: dict = roster.get("starters", {})
    flex_capacity = roster.get("teams", 12) * roster.get("flex", 0)
    flex_eligible = set(roster.get("flex_eligible", ()))

    dedicated_capacity = {pos: roster.get("teams", 12) * n for pos, n in starters.items()}
    dedicated_filled = {pos: 0 for pos in dedicated_capacity}
    flex_filled = 0
    last_points = {pos: 0.0 for pos in dedicated_capacity}
    total_slots = sum(dedicated_capacity.values()) + flex_capacity
    total_assigned = 0

    ordered = sorted(players, key=lambda p: p.get("proj_points", 0.0) or 0.0, reverse=True)
    for p in ordered:
        pos = p.get("position")
        if pos not in dedicated_capacity:
            continue
        assigned = False
        if dedicated_filled[pos] < dedicated_capacity[pos]:
            dedicated_filled[pos] += 1
            assigned = True
        elif pos in flex_eligible and flex_filled < flex_capacity:
            flex_filled += 1
            assigned = True
        if assigned:
            last_points[pos] = p.get("proj_points", 0.0) or 0.0
            total_assigned += 1
        if total_assigned >= total_slots:
            break
    return last_points


def recompute_vor(players: list[dict], roster: dict, confidence_discount: dict,
                  replacement_fn=solve_replacement_levels) -> tuple[list[dict], dict]:
    """
    Attach fresh vor / vor_rank to each player given their (possibly just
    recomputed) proj_points. Mirrors value_agent.compute_vor's K/DST
    confidence-discount treatment: shrink the point total before subtracting
    replacement level, not the VOR delta — see config.CONFIDENCE_DISCOUNT
    for why that ordering matters. Returns (players_with_vor, replacement_levels).
    """
    replacement_levels = replacement_fn(players, roster)
    out = []
    for p in players:
        q = dict(p)
        pos = q.get("position")
        level = replacement_levels.get(pos, 0.0)
        proj = q.get("proj_points", 0.0) or 0.0
        discount = confidence_discount.get(pos)
        q["vor"] = round(proj * discount - level, 2) if discount is not None else round(proj - level, 2)
        out.append(q)
    out.sort(key=lambda p: p["vor"], reverse=True)
    for i, p in enumerate(out, start=1):
        p["vor_rank"] = i
    return out, replacement_levels


def derive_snapshot_variant(snapshot: dict, blend: dict) -> dict:
    """Full frozen-input re-derivation: new BLEND -> new proj_points -> new VOR/vor_rank."""
    roster = (snapshot.get("league") or {}).get("roster") or {}
    confidence_discount = (snapshot.get("config_constants") or {}).get("CONFIDENCE_DISCOUNT") or {}
    players = recompute_proj_points(snapshot["players"], blend)
    players, replacement_levels = recompute_vor(players, roster, confidence_discount)
    variant = dict(snapshot)
    variant["players"] = players
    variant["replacement_levels"] = replacement_levels
    return variant


# ── Sweep grid ─────────────────────────────────────────────────────────────

def blend_grid(center: dict | None = None, step: float = 0.10) -> list[dict]:
    """
    A small, named grid of BLEND weight configurations around the locked
    default (or a supplied center), all summing to 1.0. Kept small
    deliberately: more configs means more multiple-comparison risk against
    an already-thin single season of data (see module docstring).
    """
    base = dict(center or config.BLEND)
    grid = [
        {"name": "current (locked)", **base},
        {"name": "espn-heavier", "espn_projection": base["espn_projection"] + step,
         "prior_actual": max(base["prior_actual"] - step / 2, 0.0),
         "market_implied": max(base["market_implied"] - step / 2, 0.0)},
        {"name": "prior-heavier", "espn_projection": max(base["espn_projection"] - step, 0.0),
         "prior_actual": base["prior_actual"] + step, "market_implied": base["market_implied"]},
        {"name": "market-heavier", "espn_projection": max(base["espn_projection"] - step, 0.0),
         "prior_actual": base["prior_actual"], "market_implied": base["market_implied"] + step},
        {"name": "espn-only", "espn_projection": 1.0, "prior_actual": 0.0, "market_implied": 0.0},
    ]
    for g in grid:
        total = g["espn_projection"] + g["prior_actual"] + g["market_implied"]
        if abs(total - 1.0) > 1e-9:
            # Renormalize so every config is a valid blend (sums to 1.0), a
            # cheap safety net for hand-edited step values.
            g["espn_projection"] /= total
            g["prior_actual"] /= total
            g["market_implied"] /= total
    return grid


# ── Bootstrap ──────────────────────────────────────────────────────────────

def bootstrap_ci(joined_pids: list[int], metric_fn, n_boot: int = 1000,
                 seed: int | None = None) -> tuple[float, float, float]:
    """
    Percentile bootstrap over PLAYERS (resampled with replacement), not over
    weeks or stat lines — this keeps each player's own internal correlation
    structure (their projection and their outcome are the same person)
    intact, which resampling at a finer grain would break.

    metric_fn(pid_list) -> float computes the summary statistic for one
    resample. Returns (point_estimate, ci_low, ci_high) using the 2.5th and
    97.5th percentiles (95% CI).
    """
    rng = random.Random(seed)
    point = metric_fn(joined_pids)
    n = len(joined_pids)
    if n < 10:
        return point, point, point
    samples = []
    for _ in range(n_boot):
        resample = [joined_pids[rng.randrange(n)] for _ in range(n)]
        samples.append(metric_fn(resample))
    samples.sort()
    lo = samples[int(0.025 * n_boot)]
    hi = samples[min(int(0.975 * n_boot), n_boot - 1)]
    return point, lo, hi


def _weighted_mae_metric_fn(proj_by_pid: dict, actual_by_pid: dict, vor_rank_by_pid: dict):
    def metric(pids: list[int]) -> float:
        pairs = [
            (proj_by_pid[pid], actual_by_pid[pid], evaluate.value_weight(vor_rank_by_pid[pid]))
            for pid in pids
        ]
        _, w = evaluate.weighted_mae(pairs)
        return w
    return metric


# ── Sweep runner ─────────────────────────────────────────────────────────

def run_sweep(snapshot: dict, actuals: dict[int, dict], configs: list[dict] | None = None,
             n_boot: int = 1000, seed: int | None = 42) -> list[dict]:
    configs = configs or blend_grid()
    rows = []
    for cfg in configs:
        blend = {k: v for k, v in cfg.items() if k != "name"}
        variant = derive_snapshot_variant(snapshot, blend)
        report = evaluate.evaluate(variant, actuals)

        proj_by_pid = {p["player_id"]: p.get("proj_points", 0.0) or 0.0 for p in variant["players"]}
        vor_rank_by_pid = {p["player_id"]: p["vor_rank"] for p in variant["players"] if p.get("vor_rank")}
        actual_by_pid = {pid: a["actual_points"] for pid, a in actuals.items()}
        joined_pids = [pid for pid in vor_rank_by_pid if pid in actual_by_pid]

        metric_fn = _weighted_mae_metric_fn(proj_by_pid, actual_by_pid, vor_rank_by_pid)
        point, lo, hi = bootstrap_ci(joined_pids, metric_fn, n_boot=n_boot, seed=seed)

        rows.append({
            "name": cfg.get("name", str(blend)),
            "blend": blend,
            "weighted_mae": report["weighted_mae"],
            "weighted_mae_ci": (round(lo, 3), round(hi, 3)),
            "spearman_drafted_range": report["spearman_drafted_range"],
            "head_to_head_verdict": report["head_to_head_verdict"],
        })
    return rows


def print_sweep_table(rows: list[dict]) -> None:
    print("=" * 96)
    print("SWEEP: BLEND weight configurations, ranked by value-weighted MAE (lower = better)")
    print("=" * 96)
    ranked = sorted(rows, key=lambda r: r["weighted_mae"])
    baseline = next((r for r in rows if "current" in r["name"]), ranked[0])
    baseline_lo, baseline_hi = baseline["weighted_mae_ci"]

    print(f"{'config':<18} {'blend (espn/prior/mkt)':<26} {'w.MAE':>8} {'95% CI':>18} {'spearman':>9}  distinguishable from baseline?")
    print("-" * 96)
    for r in ranked:
        b = r["blend"]
        blend_str = f"{b['espn_projection']:.2f}/{b['prior_actual']:.2f}/{b['market_implied']:.2f}"
        lo, hi = r["weighted_mae_ci"]
        overlap = not (hi < baseline_lo or lo > baseline_hi)
        verdict = "NO — within noise of baseline" if (overlap or r is baseline) else "yes (CIs do not overlap)"
        if r is baseline:
            verdict = "(this IS the baseline)"
        print(f"{r['name']:<18} {blend_str:<26} {r['weighted_mae']:>8.2f} "
              f"[{lo:>7.2f}, {hi:>7.2f}] {r['spearman_drafted_range'] if r['spearman_drafted_range'] is not None else float('nan'):>9.3f}  {verdict}")
    print("-" * 96)
    print(
        "READ THIS BEFORE PICKING A WINNER: with ~150-180 relevant players in one season, "
        "these confidence intervals are WIDE. A config with a lower point estimate whose CI "
        "still overlaps the baseline's is NOT established as better — it's indistinguishable "
        "from the current weights given this much data. Only trust a gap that survives "
        "non-overlapping CIs, and even then, this is one season (n=1 at the level that "
        "matters) — treat it as a weak prior for next season, not a verdict."
    )
    print("=" * 96)


# ── Self-test ────────────────────────────────────────────────────────────

def _self_test() -> None:
    """
    Proves (a) re-derivation actually changes the board under a different
    blend, (b) the bootstrap CI widens as synthetic noise increases, and (c)
    an extreme, clearly-bad config (espn-only, discarding real signal) is
    at least reported alongside its uncertainty rather than silently
    declared a winner or loser without one.
    """
    snap_files = sorted((config.DATA_DIR / "snapshots").glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not snap_files:
        raise SystemExit("No snapshot found to self-test against. Run snapshot.py first.")
    with open(snap_files[-1], encoding="utf-8") as f:
        snapshot = json.load(f)

    # (a) re-derivation changes something
    default_blend = snapshot.get("config_constants", {}).get("BLEND", config.BLEND)
    alt_blend = {"espn_projection": 1.0, "prior_actual": 0.0, "market_implied": 0.0}
    variant = derive_snapshot_variant(snapshot, alt_blend)
    original_top = sorted(snapshot["players"], key=lambda p: p.get("vor_rank") or 10**9)[0]["name"]
    variant_proj = {p["player_id"]: p["proj_points"] for p in variant["players"]}
    original_proj = {p["player_id"]: p.get("proj_points") for p in snapshot["players"]}
    changed = sum(1 for pid in variant_proj if abs(variant_proj[pid] - (original_proj.get(pid) or 0.0)) > 0.01)
    assert changed > 0, "espn-only blend should change proj_points for at least some players vs. the locked blend"
    logger.info("[self-test] PASS: re-derivation under an alternate blend changed proj_points for %d players", changed)

    # (b) bootstrap CI widens with more noise
    low_noise_actuals = evaluate.build_synthetic_actuals(snapshot, noise_std_frac=0.05, seed=1)
    high_noise_actuals = evaluate.build_synthetic_actuals(snapshot, noise_std_frac=0.40, seed=1)

    def _ci_width(actuals: dict) -> float:
        variant = derive_snapshot_variant(snapshot, default_blend)
        proj_by_pid = {p["player_id"]: p.get("proj_points", 0.0) or 0.0 for p in variant["players"]}
        vor_rank_by_pid = {p["player_id"]: p["vor_rank"] for p in variant["players"] if p.get("vor_rank")}
        actual_by_pid = {pid: a["actual_points"] for pid, a in actuals.items()}
        joined_pids = [pid for pid in vor_rank_by_pid if pid in actual_by_pid]
        metric_fn = _weighted_mae_metric_fn(proj_by_pid, actual_by_pid, vor_rank_by_pid)
        _, lo, hi = bootstrap_ci(joined_pids, metric_fn, n_boot=300, seed=7)
        return hi - lo

    low_width = _ci_width(low_noise_actuals)
    high_width = _ci_width(high_noise_actuals)
    assert high_width > low_width, (
        f"bootstrap CI should widen as synthetic noise increases, got low={low_width:.3f} high={high_width:.3f}"
    )
    logger.info("[self-test] PASS: bootstrap CI widens with noise (0.05 std -> width %.2f; 0.40 std -> width %.2f)",
                low_width, high_width)

    # (c) full sweep runs end-to-end and produces a table without crashing
    actuals = evaluate.build_synthetic_actuals(snapshot, noise_std_frac=0.15, seed=3)
    rows = run_sweep(snapshot, actuals, n_boot=200, seed=3)
    assert len(rows) >= 3, "sweep should evaluate multiple configs"
    assert all("weighted_mae_ci" in r for r in rows), "every config must report a CI, not just a point estimate"
    logger.info("[self-test] PASS: sweep produced %d configs, each with a bootstrap CI", len(rows))

    logger.info("[self-test] ALL CHECKS PASSED (synthetic actuals only — see module docstring)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Sweep BLEND configurations over a frozen snapshot and rank them with uncertainty")
    ap.add_argument("--snapshot", help="Path to a snapshot.py output. Defaults to the most recent one.")
    ap.add_argument("--live", action="store_true", help="Fetch real actuals from ESPN for the snapshot's season")
    ap.add_argument("--n-boot", type=int, default=1000, help="Bootstrap resamples per config")
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
        actuals = evaluate.fetch_actuals(season, scoring, overrides)
    else:
        logger.warning("No --live flag — using SYNTHETIC actuals (noise_std_frac=0.15). "
                       "Pass --live for a real sweep once the season is over.")
        actuals = evaluate.build_synthetic_actuals(snapshot, noise_std_frac=0.15)

    rows = run_sweep(snapshot, actuals, n_boot=args.n_boot)
    print_sweep_table(rows)


if __name__ == "__main__":
    main()
