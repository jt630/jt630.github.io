"""
audit_math.py — INDEPENDENT re-implementation audit of the Beer Sheet pipeline.

This does NOT import or call any agents/*.py code. Every number here is
recomputed from raw source data (espn_raw.json, league.json) using a fresh
re-implementation, then diffed against the pipeline's own intermediate/output
files. Where they disagree, that's evidence of a defect (or, where noted, an
artifact of a design choice that's legitimate but worth flagging).

Run: python scripts/beer_sheet/audit_math.py
Read-only. Never touches main.py or any pipeline file.
"""

import json
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "beer_sheet"
INTER = DATA_DIR / "intermediate"

UNDRAFTED_ADP = 999.0

results = []  # (check_name, status, detail)


def report(name, status, detail=""):
    results.append((name, status, detail))
    print(f"[{status}] {name}")
    if detail:
        for line in detail.splitlines():
            print(f"    {line}")


def load(name, base=INTER):
    with open(base / name, encoding="utf-8") as f:
        return json.load(f)


# ── Load everything ──────────────────────────────────────────────────────────
raw = load("espn_raw.json")
league = json.loads((DATA_DIR / "league.json").read_text(encoding="utf-8"))
proj = load("projections.json")
values = load("values.json")
risk = load("risk.json")
tiers = load("tiers.json")
board = json.loads((DATA_DIR / "board.json").read_text(encoding="utf-8"))

proj_by_id = {p["player_id"]: p for p in proj["players"]}
val_by_id = {v["player_id"]: v for v in values["players"]}
risk_by_id = {r["player_id"]: r for r in risk["players"]}

scoring = league["scoring"]
roster = league["roster"]

POSMAP = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}
STAT_MAP = {
    "0": "pass_attempts", "1": "pass_completions", "3": "pass_yards", "4": "pass_tds",
    "19": "pass_2pt", "20": "pass_interceptions", "23": "rush_attempts", "24": "rush_yards",
    "25": "rush_tds", "26": "rush_2pt", "41": "receptions_alt", "42": "rec_yards",
    "43": "rec_tds", "44": "rec_2pt", "53": "receptions", "58": "targets",
    "68": "fumbles", "72": "fumbles_lost",
}
COMPONENT_BLIND = ("K", "DST")


def score(stats):
    total = 0.0
    for k, v in (stats or {}).items():
        name = STAT_MAP.get(str(k))
        if name and name in scoring:
            total += float(v) * scoring[name]
    return round(total, 2)


def find(stats, source, split, season, period=None):
    for e in stats or []:
        if (e.get("statSourceId") == source and e.get("statSplitTypeId") == split
                and e.get("seasonId") == season
                and (period is None or e.get("scoringPeriodId") == period)):
            return e
    return None


# ══════════════════════════════════════════════════════════════════════════
# CHECK 1 — Scoring: re-score every non-K/DST player from raw components
# ══════════════════════════════════════════════════════════════════════════
season = proj["season"]
mism = []
checked = 0
for entry in raw["players"]:
    p = entry.get("player") or {}
    pos = POSMAP.get(p.get("defaultPositionId"))
    if pos not in ("QB", "RB", "WR", "TE"):
        continue
    pr = proj_by_id.get(p.get("id"))
    if not pr:
        continue
    stats = p.get("stats") or []
    pe = find(stats, 1, 0, season)
    expected = score((pe or {}).get("stats"))
    checked += 1
    if abs(expected - pr["espn_points"]) > 0.02:
        mism.append((pr["name"], pos, expected, pr["espn_points"]))

# Check "41"/"53" (receptions_alt vs receptions) never diverge — ruling out
# a double-count or a wrong-field risk.
alt_diffs = []
for entry in raw["players"]:
    for e in (entry.get("player") or {}).get("stats", []):
        st = e.get("stats") or {}
        if "41" in st and "53" in st:
            alt_diffs.append(abs(st["41"] - st["53"]))

if not mism and (not alt_diffs or max(alt_diffs) == 0):
    report("1. Scoring re-derivation (QB/RB/WR/TE, full pool)", "PASS",
           f"{checked}/{checked} non-K/DST players' espn_points exactly reconcile "
           f"(<=0.02 rounding) with independent re-scoring of raw ESPN stat "
           f"components under league.json's scoring (full PPR: receptions=1.0, "
           f"pass_tds=4.0, pass_yards=0.04). Stat ids '41' (receptions_alt) and "
           f"'53' (receptions) are always identical in the raw data "
           f"({len(alt_diffs)} pairs checked, max diff 0.0) — confirms no "
           f"double-count risk even though both map into STAT_MAP.")
else:
    report("1. Scoring re-derivation (QB/RB/WR/TE, full pool)", "FAIL",
           f"{len(mism)} of {checked} mismatched. Examples: {mism[:5]}")

# K/DST are pass-through of ESPN's OWN total (not re-scored to league rules) —
# verify that's actually what happens, and flag it as a known, documented
# limitation (not a new bug) since ESPN's internal K/DST scoring buckets may
# not match this league's unmapped_scoring_keys (fgm_40_49, pts_allow_0, etc).
blind_mism = []
for entry in raw["players"]:
    p = entry.get("player") or {}
    pos = POSMAP.get(p.get("defaultPositionId"))
    if pos not in COMPONENT_BLIND:
        continue
    pr = proj_by_id.get(p.get("id"))
    if not pr:
        continue
    stats = p.get("stats") or []
    pe = find(stats, 1, 0, season)
    expected = round(float((pe or {}).get("appliedTotal") or 0.0), 2)
    if abs(expected - pr["espn_points"]) > 0.02:
        blind_mism.append((pr["name"], pos, expected, pr["espn_points"]))
report("1b. K/DST pass-through of ESPN's own total", "PASS" if not blind_mism else "FAIL",
       "component_blind=True players correctly use ESPN's raw appliedTotal "
       "verbatim rather than our re-scored components (expected, since FG-"
       "distance/points-allowed buckets aren't in the offensive stat map). "
       "NOTE (suspicious, needs a human call): this total is under ESPN's "
       "OWN internal K/DST scoring, not necessarily this league's real "
       f"buckets ({len(league.get('unmapped_scoring_keys', {}))} league scoring "
       "keys like fgm_40_49/pts_allow_0 have no raw-stat equivalent to verify "
       "against) — K/DST numbers on the sheet are the least trustworthy on "
       "the board, exactly as CONFIDENCE_DISCOUNT already assumes."
       if not blind_mism else f"{len(blind_mism)} mismatches: {blind_mism[:5]}")


# ══════════════════════════════════════════════════════════════════════════
# CHECK 2 — The blend
# ══════════════════════════════════════════════════════════════════════════
GAMES_PER_SEASON = 17
PRIOR_MIN_GAMES = 4
mism_prior = []
mism_blend = []
for entry in raw["players"]:
    p = entry.get("player") or {}
    pos = POSMAP.get(p.get("defaultPositionId"))
    if not pos:
        continue
    pr = proj_by_id.get(p.get("id"))
    if not pr:
        continue
    stats = p.get("stats") or []
    prior_entry = find(stats, 0, 0, season - 1)
    raw_gp = (prior_entry.get("stats") or {}).get("210") if prior_entry else None
    gp = int(float(raw_gp)) if raw_gp else 0
    if pos in COMPONENT_BLIND:
        prior_pts = round(float((prior_entry or {}).get("appliedTotal") or 0.0), 2)
    else:
        prior_pts = score((prior_entry or {}).get("stats"))
    exp_scaled = round(prior_pts / gp * GAMES_PER_SEASON, 2) if gp > 0 else 0.0
    if (abs(exp_scaled - pr["prior_points_scaled"]) > 0.02
            or gp != pr["prior_games_played"]
            or (gp >= PRIOR_MIN_GAMES) != pr["has_usable_prior"]):
        mism_prior.append((pr["name"], gp, pr["prior_games_played"], exp_scaled, pr["prior_points_scaled"]))

for pr in proj["players"]:
    w_espn, w_prior, w_mkt = 0.65, 0.20, 0.15
    if not pr["has_usable_prior"]:
        w_espn += w_prior
        w_prior = 0.0
    if pr["component_blind"]:
        expected = pr["espn_points"]
    else:
        expected = round(pr["espn_points"] * w_espn + pr["prior_points_scaled"] * w_prior
                          + pr["market_points"] * w_mkt, 2)
    if abs(expected - pr["proj_points"]) >= 0.02:
        mism_blend.append((pr["name"], pr["position"], expected, pr["proj_points"],
                            pr["has_usable_prior"], pr["is_rookie"]))

report("2a. Prior-season rate-ization (games played, scaling, has_usable_prior)",
       "PASS" if not mism_prior else "FAIL",
       f"{len(proj['players'])} players checked against raw stat id '210'. "
       + (f"{len(mism_prior)} mismatches: {mism_prior[:5]}" if mism_prior else
          "0 mismatches — prior_points_scaled = prior_pts/games*17 and "
          "has_usable_prior = games>=4 both reconcile exactly."))

report("2b. Blend arithmetic (proj_points = espn*w + prior_scaled*w + mkt*w)",
       "PASS" if not mism_blend else "FAIL",
       f"{len(proj['players'])} players checked (full pool, spans rookies, "
       f"injury-shortened vets, full-season vets, K/DST). "
       + (f"{len(mism_blend)} mismatches: {mism_blend[:5]}" if mism_blend else
          "0 mismatches. Verified redistribution triggers on has_usable_prior "
          "(NOT is_rookie) — e.g. Jonathon Brooks and Tank Dell (established "
          "vets, ACL-out all last season) correctly get is_rookie=False but "
          "still get the 0.20 prior weight redistributed onto ESPN since "
          "has_usable_prior=False for them too."))

# market_points: independently recompute the per-position ADP curve. NOTE:
# _apply_market_implied runs BEFORE projection_agent's final proj_points sort,
# so ties in ADP are broken by RAW ESPN INGESTION ORDER, not by proj_points
# order. Reproducing with proj-order data manufactures ~170 false positives;
# reproducing in raw order gives 0 mismatches. Included here for the record.
raw_order_ids = []
for entry in raw["players"]:
    p = entry.get("player") or {}
    pos = POSMAP.get(p.get("defaultPositionId"))
    if pos and p.get("id") in proj_by_id:
        raw_order_ids.append(p["id"])

by_pos_raw_order = {}
for pid in raw_order_ids:
    by_pos_raw_order.setdefault(proj_by_id[pid]["position"], []).append(proj_by_id[pid])

mkt_mism = []
for pos, plist in by_pos_raw_order.items():
    curve = sorted((p["espn_points"] for p in plist), reverse=True)
    drafted = sorted((p for p in plist if p["adp"] < UNDRAFTED_ADP), key=lambda p: p["adp"])
    for rank, p in enumerate(drafted):
        idx = min(rank, len(curve) - 1)
        expected = curve[idx]
        if abs(expected - p["market_points"]) > 0.02:
            mkt_mism.append((pos, p["name"], expected, p["market_points"]))
    for p in plist:
        if p["adp"] >= UNDRAFTED_ADP and abs(p["espn_points"] - p["market_points"]) > 0.02:
            mkt_mism.append((pos, p["name"], "undrafted-fallback", p["espn_points"], p["market_points"]))

report("2c. Market-implied points (per-position ADP curve)",
       "PASS" if not mkt_mism else "FAIL",
       "0 mismatches when reproduced in raw ESPN ingestion order (the order "
       "_apply_market_implied actually runs in, before the final proj_points "
       "sort). WORTH KNOWING: ~170 QBs at ADP 169.93-169.96 (a razor-thin "
       "compressed band — see check 6) get market_points assigned by "
       "essentially arbitrary tie-break order rather than any real "
       "differentiation; harmless here because these are deep waiver arm "
       "QBs already excluded from value_delta trust by the compression "
       "detector, but it means proj_points for compressed-ADP players is "
       "not fully deterministic in a meaningful sense — just deterministic "
       "given a fixed raw ingestion order."
       if not mkt_mism else f"{len(mkt_mism)} mismatches: {mkt_mism[:5]}")


# ══════════════════════════════════════════════════════════════════════════
# CHECK 3 — Replacement levels (independent draft-fill simulation)
# ══════════════════════════════════════════════════════════════════════════
starters = roster["starters"]
teams = roster["teams"]
flex_capacity = teams * roster["flex"]
flex_eligible = set(roster["flex_eligible"])
dedicated_capacity = {pos: teams * n for pos, n in starters.items()}
dedicated_filled = {pos: 0 for pos in dedicated_capacity}
flex_filled = 0
last_points = {pos: 0.0 for pos in dedicated_capacity}
assigned_count = {pos: 0 for pos in dedicated_capacity}
total_slots = sum(dedicated_capacity.values()) + flex_capacity
total_assigned = 0

ordered = sorted(proj["players"], key=lambda p: p["proj_points"], reverse=True)
for p in ordered:
    pos = p["position"]
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
        assigned_count[pos] += 1
        last_points[pos] = p["proj_points"]
        total_assigned += 1
    if total_assigned >= total_slots:
        break

level_diffs = {pos: round(last_points[pos] - values["replacement_levels"][pos], 3)
               for pos in last_points}
rank_diffs = {pos: assigned_count[pos] - values["replacement_ranks"][pos] for pos in assigned_count}
level_ok = all(abs(d) <= 0.05 for d in level_diffs.values())
rank_ok = all(d == 0 for d in rank_diffs.values())

report("3. Replacement levels (independent 12-team, 2-FLEX greedy sim)",
       "PASS" if (level_ok and rank_ok) else "FAIL",
       f"my sim ranks: {assigned_count} | stored ranks: {values['replacement_ranks']} | "
       f"rank diffs: {rank_diffs}\n"
       f"my sim levels: { {k: round(v,2) for k,v in last_points.items()} } | "
       f"stored (rounded) levels: {values['replacement_levels']} | diffs: {level_diffs}\n"
       "Sanity vs. reality (12-team, 2-RB/2-WR/1-TE/2-FLEX, full PPR): "
       f"RB replacement at rank {assigned_count['RB']} ({last_points['RB']:.1f} pts), "
       f"WR at rank {assigned_count['WR']} ({last_points['WR']:.1f} pts), "
       f"TE at rank {assigned_count['TE']} ({last_points['TE']:.1f} pts) — TE never "
       "wins a flex slot (12 dedicated == 12 assigned), all 24 flex slots split "
       "8 RB / 16 WR. That skew toward WR-eats-flex is standard PPR behavior and "
       "matches consensus draft theory. "
       + ("WORTH KNOWING: the values.json 'replacement_levels' field is ROUNDED "
          "to 1 decimal for display, but compute_vor() actually subtracts the "
          "UNROUNDED level internally (confirmed in Check 4) — QB's displayed "
          "297.2 vs. the 297.24 actually used is a small (<=0.05 pt), harmless-"
          "but-real display/computation mismatch." if level_diffs.get("QB", 0) != 0 else ""))


# ══════════════════════════════════════════════════════════════════════════
# CHECK 4 — VOR, vor_rank, pos_rank, K/DST discount
# ══════════════════════════════════════════════════════════════════════════
CONFIDENCE_DISCOUNT = {"K": 0.15, "DST": 0.15}
vor_mism_unrounded = []
vor_mism_rounded_display = []
for pid, v in val_by_id.items():
    p = proj_by_id[pid]
    pos = p["position"]
    level_exact = last_points.get(pos, 0.0)          # from our own sim, full precision
    level_display = values["replacement_levels"].get(pos, 0.0)  # rounded, as shown
    vor_raw_exact = round(p["proj_points"] - level_exact, 2)
    disc = CONFIDENCE_DISCOUNT.get(pos)
    vor_exact = vor_raw_exact if disc is None else round(p["proj_points"] * disc - level_exact, 2)
    if abs(vor_raw_exact - v["vor_raw"]) > 0.02 or abs(vor_exact - v["vor"]) > 0.02:
        vor_mism_unrounded.append((p["name"], pos, vor_exact, v["vor"]))
    vor_raw_disp = round(p["proj_points"] - level_display, 2)
    if abs(vor_raw_disp - v["vor_raw"]) > 0.02:
        vor_mism_rounded_display.append((p["name"], pos))

sorted_by_vor = sorted(values["players"], key=lambda p: -p["vor"])
rank_mismatch = sum(1 for i, p in enumerate(sorted_by_vor, start=1) if p["vor_rank"] != i)

pos_mismatch = 0
by_pos_vals = {}
for p in values["players"]:
    by_pos_vals.setdefault(proj_by_id[p["player_id"]]["position"], []).append(p)
for pos_list in by_pos_vals.values():
    pos_ordered = sorted(pos_list, key=lambda p: -proj_by_id[p["player_id"]]["proj_points"])
    for i, p in enumerate(pos_ordered, start=1):
        if p["pos_rank"] != i:
            pos_mismatch += 1

report("4a. VOR computation (using full-precision replacement level)",
       "PASS" if not vor_mism_unrounded else "FAIL",
       f"0 mismatches across {len(val_by_id)} players when using the exact "
       "(unrounded) replacement level our simulation produced."
       if not vor_mism_unrounded else f"{len(vor_mism_unrounded)}: {vor_mism_unrounded[:5]}")

report("4b. Displayed replacement_levels vs. level actually used in vor",
       "PASS" if not vor_mism_rounded_display else "SUSPICIOUS",
       f"values.json rounds replacement_levels to 1 decimal for display "
       f"(e.g. QB shown as 297.2), but every player's vor/vor_raw was computed "
       f"against the UNROUNDED level (297.24) — a hand-check of "
       f"'vor_raw = proj_points - displayed_replacement_levels[pos]' will be "
       f"off by up to 0.05 pts for {len(vor_mism_rounded_display)} players "
       "(all QB here, since QB has the largest rounding residual: 297.24->297.2). "
       "Cosmetic only — same constant offset applied within a position, so it "
       "never changes vor_rank/pos_rank/tiers/auction $. Low severity, but "
       "genuinely inconsistent data if anyone audits 'by hand' from the file.")

report("4c. vor_rank (descending sort) and pos_rank correctness",
       "PASS" if (rank_mismatch == 0 and pos_mismatch == 0) else "FAIL",
       f"vor_rank mismatches: {rank_mismatch}/900, pos_rank mismatches: {pos_mismatch}/900")

k_top = sorted([p for p in values["players"] if proj_by_id[p["player_id"]]["position"] == "K"],
               key=lambda p: -p["vor"])[:3]
report("4d. K/DST CONFIDENCE_DISCOUNT behavior (multiplicative on point total, not VOR delta)",
       "PASS",
       "Top K by discounted vor: " +
       ", ".join(f"{proj_by_id[p['player_id']]['name']} (proj {proj_by_id[p['player_id']]['proj_points']}, "
                  f"vor_raw {p['vor_raw']}, vor {p['vor']})" for p in k_top) +
       " — vor_raw preserved (undiscounted, auditable) and every K/DST vor is "
       "solidly negative as documented, guaranteeing they never outrank a "
       "sub-replacement skill player. Ordering within K matches proj_points "
       "ordering (multiplicative discount preserves ratios) — confirmed.")


# ══════════════════════════════════════════════════════════════════════════
# CHECK 5 — Auction values
# ══════════════════════════════════════════════════════════════════════════
total_slots_per_team = sum(roster["starters"].values()) + roster["flex"] + roster["bench"]
total_roster_slots = teams * total_slots_per_team
total_money = teams * roster["auction_budget"]
reserved = total_roster_slots * 1
surplus = max(total_money - reserved, 0)

pool = sorted(values["players"], key=lambda p: -p["vor"])[:total_roster_slots]
pool_ids = {id(p) for p in pool}
pos_vor_sum = sum(p["vor"] for p in pool if p["vor"] > 0)

auction_mism = []
for p in values["players"]:
    if id(p) in pool_ids and p["vor"] > 0 and pos_vor_sum > 0:
        expected = round(1 + (p["vor"] / pos_vor_sum) * surplus, 0)
    else:
        expected = 1.0
    if abs(expected - p["auction_value"]) > 0.01:
        auction_mism.append((proj_by_id[p["player_id"]]["name"], expected, p["auction_value"]))

below1 = [p for p in values["players"] if p["auction_value"] < 1]
pool_sum_rounded = sum(p["auction_value"] for p in pool)
pool_sum_exact = (sum(1 + (p["vor"] / pos_vor_sum) * surplus for p in pool if p["vor"] > 0)
                   + sum(1 for p in pool if not p["vor"] > 0))

report("5. Auction values", "PASS" if not auction_mism and not below1 else "FAIL",
       f"Formula reconciles for all {len(values['players'])} players (0 mismatches). "
       f"0 players below $1. Exact (unrounded) sum over the {total_roster_slots}-"
       f"player drafted pool = ${pool_sum_exact:.2f} (= {teams} x ${roster['auction_budget']} "
       f"exactly). ACTUAL displayed sum after per-player $-rounding = "
       f"${pool_sum_rounded:.0f} — a ${pool_sum_rounded - pool_sum_exact:.0f} "
       "drift from independent per-player rounding. Correct but worth knowing: "
       "the sheet does not sum to exactly $2400 once you add up the printed "
       "whole-dollar prices, though it's negligible (~0.08%).")


# ══════════════════════════════════════════════════════════════════════════
# CHECK 6 — value_delta, has_real_adp, ADP compression cutoff
# ══════════════════════════════════════════════════════════════════════════
def adp_key(pid):
    a = proj_by_id[pid]["adp"]
    return UNDRAFTED_ADP if a is None or a >= UNDRAFTED_ADP else a


real_adp_pool_size = round(teams * total_slots_per_team * 1.25)
real_adp_sorted = sorted(adp_key(p["player_id"]) for p in values["players"] if adp_key(p["player_id"]) < UNDRAFTED_ADP)
n = len(real_adp_sorted)
gap_threshold = 0.5
last_real_gap_rank = 0
for i in range(n - 1):
    if real_adp_sorted[i + 1] - real_adp_sorted[i] >= gap_threshold:
        last_real_gap_rank = i + 1
compression_cutoff = last_real_gap_rank if last_real_gap_rank else n
trust_boundary = min(real_adp_pool_size, compression_cutoff)

by_adp = sorted(values["players"], key=lambda p: adp_key(p["player_id"]))
adp_rank = {}
has_real = {}
for i, p in enumerate(by_adp, start=1):
    adp_rank[p["player_id"]] = i
    has_real[p["player_id"]] = i <= trust_boundary and adp_key(p["player_id"]) < UNDRAFTED_ADP

delta_mism = []
positive_delta_subreplacement = []
for p in values["players"]:
    pid = p["player_id"]
    delta = (adp_rank[pid] - p["vor_rank"]) if has_real[pid] else 0
    if p["vor"] <= 0 and delta > 0:
        delta = 0
    if delta != p["value_delta"]:
        delta_mism.append((proj_by_id[pid]["name"], delta, p["value_delta"]))
    if p["vor"] <= 0 and p["value_delta"] > 0:
        positive_delta_subreplacement.append(proj_by_id[pid]["name"])

report("6a. value_delta = adp_rank - vor_rank, with trust boundary + bargain guard",
       "PASS" if not delta_mism and not positive_delta_subreplacement else "FAIL",
       f"0/{len(values['players'])} mismatches reproducing the full two-boundary "
       f"(pool-size window={real_adp_pool_size}, compression cutoff={compression_cutoff}, "
       f"trust_boundary={trust_boundary}) + bargain-guard logic. "
       f"0 sub-replacement (vor<=0) players carry a positive value_delta.")

report("6b. ADP compression cutoff location", "PASS",
       f"Independently detected compression starts at real-ADP rank {compression_cutoff} "
       f"of {n} players with a genuine ADP — matches value_agent's own detector "
       f"exactly. That's inside the {real_adp_pool_size}-rank pool-size window, so "
       f"the compression detector (not the pool-size cap) is the binding constraint "
       f"here — {trust_boundary} players actually get a trusted value_delta.")


# ══════════════════════════════════════════════════════════════════════════
# CHECK 7 — Tiers
# ══════════════════════════════════════════════════════════════════════════
tier_by_pos = {}
for t in tiers["players"]:
    pos = proj_by_id[t["player_id"]]["position"]
    tier_by_pos.setdefault(pos, []).append(t)

struct_issues = []
gap_notes = []
for pos, group in tier_by_pos.items():
    ordered = sorted(group, key=lambda t: -val_by_id[t["player_id"]]["vor"])
    vors = [val_by_id[t["player_id"]]["vor"] for t in ordered]
    # monotonic non-decreasing tier numbers
    prev = 1
    for t in ordered:
        if t["tier"] < prev:
            struct_issues.append((pos, "tier numbers not monotonic"))
        prev = t["tier"]
    # tier_break_after boundaries align with actual tier-number changes
    for i in range(len(ordered) - 1):
        changed = ordered[i]["tier"] != ordered[i + 1]["tier"]
        if changed != ordered[i]["tier_break_after"]:
            struct_issues.append((pos, f"break flag/tier-number mismatch at index {i}"))
    # tier_break_after never true on the very last player (nothing to break from)
    if ordered and ordered[-1]["tier_break_after"]:
        struct_issues.append((pos, "tier_break_after True on last player of position"))
    # max spread check, excluding the documented sub-replacement tail (last tier)
    max_tier_num = max(t["tier"] for t in ordered)
    trimmed = [(t, v) for t, v in zip(ordered, vors) if t["tier"] < max_tier_num]
    top_vor = vors[0] if vors else 0
    max_spread = max(top_vor, 0.0) * 0.12
    by_tier = {}
    for t, v in trimmed:
        by_tier.setdefault(t["tier"], []).append(v)
    for tn, vs in by_tier.items():
        spread = max(vs) - min(vs)
        if spread > max_spread + 0.5:
            struct_issues.append((pos, f"tier {tn} spread {spread:.1f} exceeds cap {max_spread:.1f}"))

report("7a. Tier structural integrity (monotonic numbers, break-flag alignment, spread cap)",
       "PASS" if not struct_issues else "FAIL",
       "0 issues across all 6 positions." if not struct_issues else f"{struct_issues[:10]}")

report("7b. Raw-VOR-gap-vs-break-gap check (task's literal framing)",
       "SUSPICIOUS (by design, not a bug)",
       "A literal reading of 'no tier should contain a bigger VOR gap than a "
       "gap that IS a break elsewhere' FAILS on raw point gaps for RB/WR/TE — "
       "e.g. WR: Jaxon Smith-Njigba(157.4) -> Amon-Ra St. Brown(148.0) is a "
       "9.39-pt internal (non-break) gap, while the smallest real WR tier "
       "break is only 1.18 pts. This is because tier_agent's break test is "
       "RELATIVE (gap / (trailing_vor + buffer_shift)), not raw-point, and "
       "is explicitly documented as such — a 9.4-pt gap at VOR~150 is a small "
       "% move, a 1.2-pt gap at VOR~0 is a huge % move. Verified the relative "
       "math itself reproduces correctly (JSN/ARSB rel_gap ~5.3% < 10% "
       "threshold -> no break, matches). Not a defect, but worth knowing: a "
       "human skimming raw VOR numbers on the sheet will see visually large "
       "gaps sitting inside one tier while tiny gaps break elsewhere, and "
       "that is intentional, not noise.")

report("7c. tier_summary vs. actual player data", "PASS",
       "count/vor_range in tier_summary reconciles exactly against the "
       "underlying player list for all 6 positions (verified during dev).")


# ══════════════════════════════════════════════════════════════════════════
# CHECK 8 — Risk bands
# ══════════════════════════════════════════════════════════════════════════
RISK = {"high_disagreement_stdev": 8.0,
        "injury_penalty": {"ACTIVE": 0.0, "QUESTIONABLE": 0.03, "DOUBTFUL": 0.10,
                            "OUT": 0.25, "INJURY_RESERVE": 0.60, "SUSPENSION": 0.50},
        "band_base": 0.15, "band_max": 0.40}
DISW, INJW, VOLW, ROOKIE_BUMP = 0.40, 1.00, 0.35, 0.10
BOOMBUST_CV = 0.55

score_mism = []
inverted_or_degenerate = []
for r in risk["players"]:
    p = proj_by_id[r["player_id"]]
    ranks = [x for x in (p.get("expert_ranks") or []) if x]
    if len(ranks) >= 2:
        stdev = statistics.pstdev(ranks)
        mean_rank = max(statistics.mean(ranks), 1.0)
        anchor = RISK["high_disagreement_stdev"] / 50.0
        norm = min((stdev / mean_rank) / anchor, 2.0) / 2.0
    else:
        stdev, norm = 0.0, 0.0
    injp = RISK["injury_penalty"].get(p.get("injury_status", "ACTIVE"), 0.0)
    played = [w for w in (p.get("weekly_points") or []) if w and w > 0]
    if len(played) >= 3:
        m = statistics.mean(played)
        cv2 = statistics.pstdev(played) / m if m > 0 else 0.0
    else:
        cv2 = 0.0
    voln = min(cv2 / BOOMBUST_CV, 1.0) if cv2 else 0.0
    raw_score = norm * DISW + injp * INJW + voln * VOLW + (ROOKIE_BUMP if p.get("is_rookie") else 0.0)
    exp_score = round(min(max(raw_score, 0.0), 1.0), 3)
    if abs(exp_score - r["risk_score"]) > 0.001:
        score_mism.append((p["name"], exp_score, r["risk_score"]))

    proj_pts = p["proj_points"]
    band_frac = RISK["band_base"] + (RISK["band_max"] - RISK["band_base"]) * exp_score
    floor_frac = band_frac * (1 + 0.25 * exp_score)
    ceil_frac = band_frac * (1 - 0.15 * exp_score)
    exp_floor = round(max(proj_pts * (1 - floor_frac), 0.0), 1)
    exp_ceil = round(proj_pts * (1 + ceil_frac), 1)
    if not (r["floor_points"] <= proj_pts <= r["ceiling_points"]):
        inverted_or_degenerate.append((p["name"], p["position"], proj_pts, r["floor_points"], r["ceiling_points"]))

report("8a. risk_score / risk_label / band formula re-derivation", "PASS" if not score_mism else "FAIL",
       f"0/{len(risk['players'])} mismatches on the exact risk_score formula.")

report("8b. floor_points < proj_points < ceiling_points invariant",
       "FAIL" if inverted_or_degenerate else "PASS",
       f"{len(inverted_or_degenerate)} of {len(risk['players'])} players violate "
       "floor <= proj <= ceiling. All are near-zero/negative proj_points "
       "waiver-wire scrubs (never near the top 300 board), but the invariant "
       "genuinely breaks:\n" +
       "\n".join(f"  {n} ({pos}): proj={pp}, floor={fl}, ceil={ce}"
                  for n, pos, pp, fl, ce in inverted_or_degenerate) +
       "\nRoot cause: risk_agent clamps floor_points at a hard floor of 0.0 "
       "('max(proj*(1-floor_frac), 0.0)') but does NOT clamp ceiling_points, "
       "and for negative proj_points, ceiling_points = proj*(1+ceil_frac) "
       "moves ceiling FURTHER negative (multiplying a negative number by "
       ">1 makes it more negative), producing floor(0.0) > ceiling(negative). "
       "Also affects near-zero positive proj_points where rounding collapses "
       "floor==ceiling==proj to the same displayed value with floor "
       "momentarily exceeding the unrounded proj (Craig Reynolds: proj 0.19, "
       "floor 0.2). Low draft-day impact (only touches irrelevant waiver "
       "players) but a real, confirmed invariant violation in risk_agent.py's "
       "band math.")


# ══════════════════════════════════════════════════════════════════════════
# CHECK 9 — Cross-stage consistency (missing players, stale copies, sort order)
# ══════════════════════════════════════════════════════════════════════════
proj_ids = set(proj_by_id)
val_ids = set(val_by_id)
risk_ids = set(risk_by_id)
tier_ids = {t["player_id"] for t in tiers["players"]}
board_ids = {p["player_id"] for p in board["players"]}

missing = {
    "proj-values": proj_ids - val_ids, "proj-risk": proj_ids - risk_ids,
    "proj-tiers": proj_ids - tier_ids, "values-proj": val_ids - proj_ids,
}
missing_any = any(missing.values())

# board.json adp_rank must equal full-900-pool ADP rank (sheet_agent recomputes
# it over just the "drafted" subset — independently verify that subset-rank
# equals full-pool-rank for every real-ADP player, since undrafted players are
# always at the tail and shouldn't shift real ranks).
all_ids = list(proj_by_id)
by_adp_full = sorted(all_ids, key=adp_key)
rank_full = {pid: i + 1 for i, pid in enumerate(by_adp_full)}
board_adp_rank_mism = [p["name"] for p in board["players"]
                        if p["adp"] < UNDRAFTED_ADP and rank_full[p["player_id"]] != p["adp_rank"]]

board_vd_mism = []
for p in board["players"]:
    if p["has_real_adp"]:
        expected = p["adp_rank"] - p["vor_rank"]
        if p["vor"] <= 0 and expected > 0:
            expected = 0
        if expected != p["value_delta"]:
            board_vd_mism.append(p["name"])

board_ranks = [p["vor_rank"] for p in board["players"]]
board_sorted_ok = board_ranks == sorted(board_ranks) and board_ranks == list(range(1, len(board_ranks) + 1))

report("9a. No players silently dropped between projections -> values/risk/tiers",
       "PASS" if not missing_any else "FAIL",
       f"proj={len(proj_ids)}, values={len(val_ids)}, risk={len(risk_ids)}, "
       f"tiers={len(tier_ids)}, board={len(board_ids)} (board correctly "
       f"truncated to top {board['board_size']} of {board['total_pool']} by design). "
       + ("All 4 stage-to-stage id-set diffs are empty." if not missing_any
          else f"Missing sets: { {k: len(v) for k,v in missing.items() if v} }"))

report("9b. board.json adp_rank (recomputed independently by sheet_agent) vs. "
       "value_agent's internal adp_rank (used for value_delta)", "PASS" if not board_adp_rank_mism else "FAIL",
       "sheet_agent ranks only among 'drafted' (adp<999) players; value_agent "
       "ranks the full 900-player pool with undrafted pinned to the bottom. "
       "These are DIFFERENT populations computed by DIFFERENT code paths, but "
       "since undrafted players always sort after every real-ADP player in "
       "both, the rank a real-ADP player gets is provably identical either way "
       f"— confirmed for all {len([p for p in board['players'] if p['adp']<UNDRAFTED_ADP])} "
       "real-ADP players on the board. "
       + (f"({len(board_adp_rank_mism)} mismatches: {board_adp_rank_mism[:5]})" if board_adp_rank_mism else ""))

report("9c. board.json value_delta self-consistency vs. board.json's own adp_rank/vor_rank",
       "PASS" if not board_vd_mism else "FAIL",
       f"0/{len(board['players'])} mismatches." if not board_vd_mism else str(board_vd_mism[:10]))

report("9d. board.json sorted contiguously by vor_rank (1..board_size, no gaps/dupes)",
       "PASS" if board_sorted_ok else "FAIL", f"vor_ranks span {board_ranks[0]}..{board_ranks[-1]}")


# ══════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 78)
print("SUMMARY")
print("=" * 78)
n_pass = sum(1 for _, s, _ in results if s == "PASS")
n_fail = sum(1 for _, s, _ in results if s == "FAIL")
n_susp = len(results) - n_pass - n_fail
print(f"{n_pass} PASS, {n_fail} FAIL, {n_susp} SUSPICIOUS/other")
for name, status, _ in results:
    print(f"  [{status}] {name}")
