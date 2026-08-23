#!/usr/bin/env python3
"""
Empirical validation of STAT_MAP against ESPN's raw fantasy data.

Tests each ESPN numeric ID mapping by checking whether:
- Top QBs have plausible pass_yards, pass_attempts, rec_yards values
- Top RBs have plausible rush_yards, rush_attempts
- Top WRs have plausible rec_yards, receptions, targets
- Top TEs have similar patterns to WR but lower volume
- TD stats are small positive numbers
- pass_interceptions and fumbles_lost are small positive counts

Also identifies unmapped stat IDs that appear frequently in 2026 projections
and infers their likely meaning based on position and magnitude.
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# Load config
import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import STAT_MAP, POSITION_MAP, SEASON, INTERMEDIATE_DIR


def load_data(data_path: Path) -> Dict:
    """Load the ESPN raw JSON."""
    with open(data_path, 'r') as f:
        return json.load(f)


def extract_stat_entries(data: Dict) -> Tuple[Dict, Dict, Dict]:
    """
    Extract three separate datasets:
    - projections: 2026 season projections (statSourceId=1, seasonId=2026, statSplitTypeId=0)
    - actuals: 2025 actual stats (statSourceId=0, seasonId=2025)
    - all_players: full player objects keyed by id

    Returns: (projections, actuals, all_players)
    """
    projections = {}
    actuals = {}
    all_players = {}

    for entry in data.get('players', []):
        player = entry.get('player', {})
        player_id = player.get('id')
        if not player_id:
            continue

        all_players[player_id] = player

        # player.stats is a list of stat records
        player_stats_list = player.get('stats', [])
        if not isinstance(player_stats_list, list):
            continue

        # Find the right stat record for projections and actuals
        for stat_entry in player_stats_list:
            stat_source_id = stat_entry.get('statSourceId')
            season_id = stat_entry.get('seasonId')
            split_type_id = stat_entry.get('statSplitTypeId')
            stats = stat_entry.get('stats', {})

            # 2026 projections (statSourceId=1, splitTypeId=0)
            if stat_source_id == 1 and season_id == 2026 and split_type_id == 0:
                if isinstance(stats, dict) and player_id not in projections:
                    projections[player_id] = {
                        'player': player,
                        'stats': stats
                    }

            # 2025 actuals (statSourceId=0)
            if stat_source_id == 0 and season_id == 2025:
                if isinstance(stats, dict) and player_id not in actuals:
                    actuals[player_id] = {
                        'player': player,
                        'stats': stats
                    }

    return projections, actuals, all_players


def get_position_name(position_id: int) -> str:
    """Map position ID to name."""
    return POSITION_MAP.get(position_id, f"UNKNOWN({position_id})")


def filter_by_position(data: Dict, position_id: int, top_n: int = 10) -> List[Tuple[int, Dict]]:
    """Get top N players by position, sorted by some heuristic."""
    by_pos = [(pid, entry) for pid, entry in data.items()
              if entry['player'].get('defaultPositionId') == position_id]

    # Sort by ownership percentage as a proxy for elite status
    by_pos.sort(key=lambda x: x[1]['player'].get('ownership', {}).get('percentOwned', 0),
                reverse=True)

    return by_pos[:top_n]


def validate_stat_exists(stat_id: str, stats: Dict, positions_checked: set) -> Tuple[bool, float]:
    """Check if a stat ID exists in the stats dict and return its value."""
    if stat_id in stats:
        val = stats[stat_id]
        if isinstance(val, (int, float)):
            return True, val
    return False, None


def get_unmapped_stat_ids(projections: Dict) -> Dict[str, Dict]:
    """
    Find all stat IDs in projections that are NOT in STAT_MAP.
    Returns dict of {stat_id: {count, example_values, positions_seen}}
    """
    unmapped = defaultdict(lambda: {'count': 0, 'values': [], 'positions': set()})
    mapped_ids = set(STAT_MAP.keys())

    for player_id, entry in projections.items():
        pos_id = entry['player'].get('defaultPositionId')
        pos_name = get_position_name(pos_id)

        for stat_id, value in entry['stats'].items():
            if stat_id not in mapped_ids and isinstance(value, (int, float)):
                unmapped[stat_id]['count'] += 1
                unmapped[stat_id]['positions'].add(pos_name)
                if len(unmapped[stat_id]['values']) < 20:  # Keep first 20 samples
                    unmapped[stat_id]['values'].append((pos_name, value))

    return unmapped


def infer_stat_meaning(stat_id: str, values_by_pos: Dict[str, List[float]]) -> str:
    """Infer what a stat ID likely means based on positions carrying it and typical values."""
    positions = list(values_by_pos.keys())

    # Special handling for K and DST
    if 'K' in positions:
        avg = sum(values_by_pos['K']) / len(values_by_pos['K']) if values_by_pos['K'] else 0
        if 0 < avg < 5:
            return "K: field goal / extra point stat (likely FG makes or similar)"
        if 5 <= avg < 30:
            return "K: points or similar accumulation stat"
        return f"K-specific stat (avg {avg:.1f})"

    if 'DST' in positions:
        avg = sum(values_by_pos['DST']) / len(values_by_pos['DST']) if values_by_pos['DST'] else 0
        if 0 <= avg < 5:
            return "DST: defense stat (sacks, INTs, fumbles recovered, etc.)"
        if 5 <= avg < 30:
            return "DST: points or defensive events"
        return f"DST-specific stat (avg {avg:.1f})"

    # For skill positions
    if all(pos in ['QB', 'RB', 'WR', 'TE'] for pos in positions):
        all_vals = []
        for pos in positions:
            all_vals.extend(values_by_pos[pos])
        if not all_vals:
            return "Unknown (no values)"

        avg = sum(all_vals) / len(all_vals)

        # Heuristics based on value magnitude
        if 0 <= avg < 2:
            return "Small event count (e.g., red zone attempts, first downs)"
        if 2 <= avg < 10:
            return "Moderate event count (e.g., yards after catch, third-down conversions)"
        if 10 <= avg < 100:
            return "Significant stat (e.g., return yards, carry/reception breakdowns)"
        if 100 <= avg < 1000:
            return "High-volume stat (e.g., yards, carries, routes run)"

        # Check if it appears on all positions (likely shared metric)
        if len(positions) >= 3:
            return f"Multi-position stat (appears on {', '.join(positions)}), avg {avg:.1f}"

        return f"Skill position stat (avg {avg:.1f}, positions: {', '.join(positions)})"

    return f"Mixed stat (positions: {', '.join(positions)})"


def print_validation_results(projections: Dict, actuals: Dict) -> None:
    """Run validation tests and print results."""
    print("=" * 100)
    print("ESPN STAT_MAP VALIDATION")
    print("=" * 100)
    print()

    # Test 1: QBs
    print("TEST 1: QUARTERBACK VALIDATION")
    print("-" * 100)
    qbs = filter_by_position(projections, 1, top_n=10)

    if qbs:
        qb_name = qbs[0][1]['player'].get('fullName', 'Unknown')
        qb_stats = qbs[0][1]['stats']

        checks = {
            'pass_yards (ID 3)': (qb_stats.get('3'), 2500, 5500),
            'pass_attempts (ID 0)': (qb_stats.get('0'), 300, 700),
            'rec_yards (ID 42)': (qb_stats.get('42'), -10, 50),  # Should be ~0
        }

        print(f"Top QB: {qb_name}")
        all_pass = True
        for check_name, (val, min_v, max_v) in checks.items():
            if val is not None:
                status = "PASS" if min_v <= val <= max_v else "FAIL"
                if status == "FAIL":
                    all_pass = False
                print(f"  {check_name}: {val:.1f} (expected {min_v}-{max_v}) [{status}]")
            else:
                print(f"  {check_name}: MISSING")
                all_pass = False

        print(f"  Overall: {'PASS' if all_pass else 'FAIL'}")
    else:
        print("  No QB projections found!")

    print()

    # Test 2: RBs
    print("TEST 2: RUNNING BACK VALIDATION")
    print("-" * 100)
    rbs = filter_by_position(projections, 2, top_n=10)

    if rbs:
        rb_name = rbs[0][1]['player'].get('fullName', 'Unknown')
        rb_stats = rbs[0][1]['stats']

        checks = {
            'rush_yards (ID 24)': (rb_stats.get('24'), 500, 2000),
            'rush_attempts (ID 23)': (rb_stats.get('23'), 100, 400),
            'rec_yards (ID 42)': (rb_stats.get('42'), 0, 800),
            'receptions (ID 53)': (rb_stats.get('53'), 10, 100),
        }

        print(f"Top RB: {rb_name}")
        all_pass = True
        for check_name, (val, min_v, max_v) in checks.items():
            if val is not None:
                status = "PASS" if min_v <= val <= max_v else "FAIL"
                if status == "FAIL":
                    all_pass = False
                print(f"  {check_name}: {val:.1f} (expected {min_v}-{max_v}) [{status}]")
            else:
                print(f"  {check_name}: MISSING")

        print(f"  Overall: {'PASS' if all_pass else 'FAIL'}")
    else:
        print("  No RB projections found!")

    print()

    # Test 3: WRs
    print("TEST 3: WIDE RECEIVER VALIDATION")
    print("-" * 100)
    wrs = filter_by_position(projections, 3, top_n=10)

    if wrs:
        wr_name = wrs[0][1]['player'].get('fullName', 'Unknown')
        wr_stats = wrs[0][1]['stats']

        checks = {
            'rec_yards (ID 42)': (wr_stats.get('42'), 400, 1800),
            'receptions (ID 53)': (wr_stats.get('53'), 30, 140),
            'targets (ID 58)': (wr_stats.get('58'), 50, 180),
        }

        print(f"Top WR: {wr_name}")
        all_pass = True
        for check_name, (val, min_v, max_v) in checks.items():
            if val is not None:
                status = "PASS" if min_v <= val <= max_v else "FAIL"
                if status == "FAIL":
                    all_pass = False
                print(f"  {check_name}: {val:.1f} (expected {min_v}-{max_v}) [{status}]")
            else:
                print(f"  {check_name}: MISSING")
                all_pass = False

        # Structural check: targets >= receptions for all WRs
        targets_ge_rec = True
        rec_count = 0
        for pid, entry in wrs:
            stats = entry['stats']
            rec = stats.get('53')
            tgt = stats.get('58')
            if rec is not None and tgt is not None:
                if tgt < rec:
                    targets_ge_rec = False
                    rec_count += 1

        if rec_count > 0:
            print(f"  Structural check (targets >= receptions): FAIL ({rec_count} WRs have targets < receptions)")
            all_pass = False
        else:
            print(f"  Structural check (targets >= receptions): PASS")

        print(f"  Overall: {'PASS' if all_pass else 'FAIL'}")
    else:
        print("  No WR projections found!")

    print()

    # Test 4: TEs
    print("TEST 4: TIGHT END VALIDATION")
    print("-" * 100)
    tes = filter_by_position(projections, 4, top_n=10)

    if tes:
        te_name = tes[0][1]['player'].get('fullName', 'Unknown')
        te_stats = tes[0][1]['stats']

        checks = {
            'rec_yards (ID 42)': (te_stats.get('42'), 200, 1200),
            'receptions (ID 53)': (te_stats.get('53'), 20, 100),
            'targets (ID 58)': (te_stats.get('58'), 30, 130),
        }

        print(f"Top TE: {te_name}")
        all_pass = True
        for check_name, (val, min_v, max_v) in checks.items():
            if val is not None:
                status = "PASS" if min_v <= val <= max_v else "FAIL"
                if status == "FAIL":
                    all_pass = False
                print(f"  {check_name}: {val:.1f} (expected {min_v}-{max_v}) [{status}]")
            else:
                print(f"  {check_name}: MISSING")

        print(f"  Overall: {'PASS' if all_pass else 'FAIL'}")
    else:
        print("  No TE projections found!")

    print()

    # Test 5: TD stats
    print("TEST 5: TOUCHDOWN & TURNOVER STATS (cross-position)")
    print("-" * 100)
    td_stat_ids = {'4': 'pass_tds', '25': 'rush_tds', '43': 'rec_tds', '20': 'pass_interceptions', '72': 'fumbles_lost'}

    all_pass = True
    for stat_id, stat_name in td_stat_ids.items():
        values = []
        for player_id, entry in projections.items():
            val = entry['stats'].get(stat_id)
            if val is not None and isinstance(val, (int, float)):
                values.append(val)

        if values:
            max_val = max(values)
            avg_val = sum(values) / len(values)
            status = "PASS" if max_val < 50 else "FAIL"
            if status == "FAIL":
                all_pass = False
            print(f"  {stat_name} (ID {stat_id}): max={max_val:.1f}, avg={avg_val:.2f} [{status}]")
        else:
            print(f"  {stat_name} (ID {stat_id}): NO DATA")

    print(f"  Overall: {'PASS' if all_pass else 'FAIL'}")

    print()
    print("=" * 100)
    print("UNMAPPED STAT IDS IN 2026 PROJECTIONS")
    print("=" * 100)
    print()

    unmapped = get_unmapped_stat_ids(projections)

    # Group unmapped by position distribution and infer meaning
    if unmapped:
        # Sort by frequency
        sorted_unmapped = sorted(unmapped.items(), key=lambda x: x[1]['count'], reverse=True)

        for stat_id, info in sorted_unmapped:
            positions = info['positions']
            count = info['count']

            # Organize sample values by position
            values_by_pos = defaultdict(list)
            for pos, val in info['values']:
                values_by_pos[pos].append(val)

            inference = infer_stat_meaning(stat_id, dict(values_by_pos))

            print(f"ID {stat_id}:")
            print(f"  Frequency: {count} players")
            print(f"  Positions: {', '.join(sorted(positions))}")
            print(f"  Sample values:")
            for pos, val in info['values'][:5]:
                print(f"    {pos}: {val:.2f}")
            print(f"  Inferred meaning: {inference}")
            print()
    else:
        print("  No unmapped stat IDs found!")

    print("=" * 100)


if __name__ == '__main__':
    data_path = INTERMEDIATE_DIR / 'espn_raw.json'

    if not data_path.exists():
        print(f"ERROR: Data file not found at {data_path}")
        sys.exit(1)

    print(f"Loading data from {data_path}...")
    data = load_data(data_path)

    print(f"Extracting entries...")
    projections, actuals, all_players = extract_stat_entries(data)

    print(f"Found {len(projections)} projection entries and {len(actuals)} actual entries")
    print()

    print_validation_results(projections, actuals)
