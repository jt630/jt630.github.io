#!/usr/bin/env python3
"""Generate era, heights, and type analysis JSON files for Kay's credit list."""

import json, math, urllib.request, datetime
from collections import defaultdict

RCDB_URL = "https://raw.githubusercontent.com/fabianrguez/rcdb-api/main/db/coasters.json"
KAY_PROFILE = "coaster-data/profiles/kay.json"
OUT_DIR = "data/coasters/analysis"
NOW = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# ── fetch RCDB ──────────────────────────────────────────────────────────────
print("Fetching RCDB data…")
with urllib.request.urlopen(RCDB_URL) as r:
    rcdb_list = json.load(r)
rcdb = {c["id"]: c for c in rcdb_list}
print(f"  {len(rcdb)} coasters loaded")

# ── load Kay ────────────────────────────────────────────────────────────────
with open(KAY_PROFILE, encoding="utf-8") as f:
    kay = json.load(f)
credits = kay["credits"]
print(f"  {len(credits)} credits")

# ── join ────────────────────────────────────────────────────────────────────
def safe_height(val):
    """Return float or None — handles arrays like [38.2, 38.2]."""
    if val is None or val == "":
        return None
    if isinstance(val, list):
        val = val[0]
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_year(opened):
    if not opened:
        return None
    try:
        return int(str(opened).split("-")[0])
    except (ValueError, IndexError):
        return None

joined = []
for c in credits:
    rid = c.get("coasterRcdbId")
    r   = rcdb.get(rid) if rid else None
    status = r.get("status", {}) if r else {}
    stats  = r.get("stats",  {}) if r else {}
    joined.append({
        "name":     c.get("coasterName", ""),
        "park":     c.get("parkName", ""),
        "rcdb_id":  rid,
        "year":     safe_year(status.get("date", {}).get("opened") if status else None),
        "height_m": safe_height(stats.get("height") if stats else None),
        "type":     r.get("type") if r else None,
        "design":   r.get("design") if r else None,
        "elements": stats.get("elements", "") if stats else "",
    })

# ════════════════════════════════════════════════════════════════════════════
# 1. ERA
# ════════════════════════════════════════════════════════════════════════════
DECADES = [
    ("Pre-1960",  None, 1960),
    ("1960s",     1960, 1970),
    ("1970s",     1970, 1980),
    ("1980s",     1980, 1990),
    ("1990s",     1990, 2000),
    ("2000s",     2000, 2010),
    ("2010s",     2010, 2020),
    ("2020s",     2020, None),
]

era_buckets = defaultdict(list)
no_year = []
for row in joined:
    y = row["year"]
    if y is None:
        no_year.append(row["name"])
        continue
    placed = False
    for label, lo, hi in DECADES:
        if (lo is None or y >= lo) and (hi is None or y < hi):
            era_buckets[label].append(row)
            placed = True
            break
    if not placed:
        era_buckets["Unknown"].append(row)

by_decade = []
total_with_year = sum(len(v) for v in era_buckets.values())
for label, _, _ in DECADES:
    rows = era_buckets.get(label, [])
    by_decade.append({
        "decade":  label,
        "count":   len(rows),
        "pct":     round(len(rows) / len(credits) * 100, 1),
        "credits": [r["name"] for r in sorted(rows, key=lambda x: x["year"] or 0)],
    })

dated = [r for r in joined if r["year"]]
oldest = min(dated, key=lambda x: x["year"])
newest = max(dated, key=lambda x: x["year"])

era_obs = (
    f"Kay's credit list spans from {oldest['year']} ({oldest['name']}) to "
    f"{newest['year']} ({newest['name']}) — a {newest['year'] - oldest['year']}-year range. "
    f"The 1990s and 2000s are the densest decades, reflecting the East Coast park boom when "
    f"Six Flags, Cedar Fair, and Busch were all building aggressively. "
    f"The 2020s already show {by_decade[7]['count']} credits despite being only a few years in. "
    f"{len(no_year)} credits have no opening year on record."
)

era_data = {
    "skill": "era",
    "profile": "kay",
    "generated_at": NOW,
    "total_credits": len(credits),
    "data": {
        "by_decade": by_decade,
        "oldest": {"coasterName": oldest["name"], "year": oldest["year"], "parkName": oldest["park"]},
        "newest": {"coasterName": newest["name"], "year": newest["year"], "parkName": newest["park"]},
        "span_years": newest["year"] - oldest["year"],
        "no_year_data": no_year,
        "observations": era_obs,
    }
}

# ════════════════════════════════════════════════════════════════════════════
# 2. HEIGHT TIERS
# ════════════════════════════════════════════════════════════════════════════
M_TO_FT = 3.28084

TIERS = [
    ("Under 50ft",  None,  15.24),
    ("50–100ft",   15.24,  30.48),
    ("100–150ft",  30.48,  45.72),
    ("150–200ft",  45.72,  60.96),
    ("200–300ft",  60.96,  91.44),
    ("300ft+",     91.44,  None),
]

height_buckets = defaultdict(list)
no_height = []
for row in joined:
    h = row["height_m"]
    if h is None:
        no_height.append(row["name"])
        continue
    placed = False
    for label, lo, hi in TIERS:
        if (lo is None or h >= lo) and (hi is None or h < hi):
            height_buckets[label].append(row)
            placed = True
            break
    if not placed:
        no_height.append(row["name"])

by_tier = []
for label, _, _ in TIERS:
    rows = height_buckets.get(label, [])
    by_tier.append({
        "tier":    label,
        "count":   len(rows),
        "pct":     round(len(rows) / len(credits) * 100, 1),
        "credits": [{"name": r["name"], "height_ft": round(r["height_m"] * M_TO_FT)} for r in sorted(rows, key=lambda x: x["height_m"], reverse=True)],
    })

with_height = [r for r in joined if r["height_m"] is not None]
tallest  = max(with_height, key=lambda x: x["height_m"])
shortest = min(with_height, key=lambda x: x["height_m"])

ht_obs = (
    f"Most of Kay's credits cluster in the 50–150ft range — the bread-and-butter steel coaster. "
    f"The tallest credit is {tallest['name']} at {round(tallest['height_m'] * M_TO_FT)}ft, "
    f"and the shortest is {shortest['name']} at {round(shortest['height_m'] * M_TO_FT)}ft. "
    f"{len(no_height)} credits have no height data on record."
)

heights_data = {
    "skill": "heights",
    "profile": "kay",
    "generated_at": NOW,
    "total_credits": len(credits),
    "data": {
        "by_tier": by_tier,
        "tallest":  {"coasterName": tallest["name"],  "height_ft": round(tallest["height_m"]  * M_TO_FT), "parkName": tallest["park"]},
        "shortest": {"coasterName": shortest["name"], "height_ft": round(shortest["height_m"] * M_TO_FT), "parkName": shortest["park"]},
        "no_height_data": no_height,
        "observations": ht_obs,
    }
}

# ════════════════════════════════════════════════════════════════════════════
# 3. COASTER TYPE
# ════════════════════════════════════════════════════════════════════════════
DESIGN_ORDER = ["Sit Down", "Inverted", "Wing", "Flying", "Stand Up", "Suspended", "Bobsled", "Unknown"]

wood_count  = sum(1 for r in joined if r["type"] == "Wood")
steel_count = sum(1 for r in joined if r["type"] == "Steel")
other_type  = len(credits) - wood_count - steel_count

wood_vs_steel = [
    {"type": "Steel", "count": steel_count, "pct": round(steel_count / len(credits) * 100, 1)},
    {"type": "Wood",  "count": wood_count,  "pct": round(wood_count  / len(credits) * 100, 1)},
]
if other_type:
    wood_vs_steel.append({"type": "Unknown", "count": other_type, "pct": round(other_type / len(credits) * 100, 1)})

design_buckets = defaultdict(list)
for row in joined:
    d = row["design"] or "Unknown"
    design_buckets[d].append(row["name"])

by_design = []
for key in DESIGN_ORDER:
    rows = design_buckets.get(key, [])
    if rows:
        by_design.append({
            "design":  key,
            "count":   len(rows),
            "pct":     round(len(rows) / len(credits) * 100, 1),
            "credits": rows,
        })
# append any remaining designs not in DESIGN_ORDER
for key, rows in design_buckets.items():
    if key not in DESIGN_ORDER and rows:
        by_design.append({
            "design":  key,
            "count":   len(rows),
            "pct":     round(len(rows) / len(credits) * 100, 1),
            "credits": rows,
        })

launch_credits = [r["name"] for r in joined if "Launch" in (r["elements"] or "")]
lift_credits   = [r["name"] for r in joined if "Launch" not in (r["elements"] or "") and r["elements"]]
no_data_credits = [r["name"] for r in joined if not r["elements"]]

launch_vs_lift = [
    {"propulsion": "Launch",    "count": len(launch_credits), "pct": round(len(launch_credits) / len(credits) * 100, 1), "credits": launch_credits},
    {"propulsion": "Lift Hill", "count": len(lift_credits),   "pct": round(len(lift_credits)   / len(credits) * 100, 1), "credits": lift_credits},
    {"propulsion": "No Data",   "count": len(no_data_credits),"pct": round(len(no_data_credits)/ len(credits) * 100, 1), "credits": no_data_credits},
]

# Wood credits list for observations
wood_credits_list = [r["name"] for r in joined if r["type"] == "Wood"]
inverted_count = len(design_buckets.get("Inverted", []))

type_obs = (
    f"Kay's list skews heavily steel at {steel_count} credits ({round(steel_count/len(credits)*100)}%), "
    f"with {wood_count} wood credits ({round(wood_count/len(credits)*100)}%) — {', '.join(wood_credits_list[:5])} and others. "
    f"Sit-down is the dominant design, but {inverted_count} inverted credits stand out. "
    f"Launch coasters account for {len(launch_credits)} credits ({round(len(launch_credits)/len(credits)*100)}%), "
    f"spanning LIM, LSM, hydraulic, and tire-propelled systems."
)

type_data = {
    "skill": "type",
    "profile": "kay",
    "generated_at": NOW,
    "total_credits": len(credits),
    "data": {
        "wood_vs_steel": wood_vs_steel,
        "by_design": by_design,
        "launch_vs_lift": launch_vs_lift,
        "observations": type_obs,
    }
}

# ── write output ─────────────────────────────────────────────────────────────
import os
os.makedirs(OUT_DIR, exist_ok=True)

for fname, data in [("era-kay.json", era_data), ("heights-kay.json", heights_data), ("type-kay.json", type_data)]:
    path = os.path.join(OUT_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {path}")

# ── summary ──────────────────────────────────────────────────────────────────
print("\n── ERA ──")
for d in by_decade:
    if d["count"]: print(f"  {d['decade']}: {d['count']} ({d['pct']}%)")
print(f"  No year data: {len(no_year)}")

print("\n── HEIGHTS ──")
for t in by_tier:
    if t["count"]: print(f"  {t['tier']}: {t['count']} ({t['pct']}%)")
print(f"  No height data: {len(no_height)}")

print("\n── TYPE ──")
for d in by_design:
    print(f"  {d['design']}: {d['count']} ({d['pct']}%)")
print(f"\n  Launch: {len(launch_credits)} | Lift: {len(lift_credits)} | No data: {len(no_data_credits)}")
print(f"  Wood: {wood_count} | Steel: {steel_count}")
