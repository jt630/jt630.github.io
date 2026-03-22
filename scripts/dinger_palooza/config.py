"""
Dinger Palooza — shared configuration for all agents.
"""

import os
from datetime import date, timedelta

# ── Candidate sluggers ────────────────────────────────────────────────────────
# team_id from the MLB Stats API (/api/v1/teams)
PLAYERS = [
    {"name": "Cal Raleigh",       "team": "Seattle Mariners",      "team_id": 136, "team_abbr": "SEA", "mlb_id": None},
    {"name": "Aaron Judge",       "team": "New York Yankees",      "team_id": 147, "team_abbr": "NYY", "mlb_id": None},
    {"name": "Kyle Schwarber",    "team": "Philadelphia Phillies", "team_id": 143, "team_abbr": "PHI", "mlb_id": None},
    {"name": "Shohei Ohtani",     "team": "Los Angeles Dodgers",   "team_id": 119, "team_abbr": "LAD", "mlb_id": None},
    {"name": "Junior Caminero",   "team": "Tampa Bay Rays",        "team_id": 139, "team_abbr": "TB",  "mlb_id": None},
    {"name": "Juan Soto",         "team": "New York Mets",         "team_id": 121, "team_abbr": "NYM", "mlb_id": None},
    {"name": "Ronald Acuna Jr",   "team": "Atlanta Braves",        "team_id": 144, "team_abbr": "ATL", "mlb_id": None},
    {"name": "Bobby Witt Jr",     "team": "Kansas City Royals",    "team_id": 118, "team_abbr": "KC",  "mlb_id": None},
    {"name": "Jose Ramirez",      "team": "Cleveland Guardians",   "team_id": 114, "team_abbr": "CLE", "mlb_id": None},
    {"name": "Pete Alonso",       "team": "New York Mets",         "team_id": 121, "team_abbr": "NYM", "mlb_id": None},
]

# Stadium locations for weather lookups (city, state/country for OWM query)
STADIUM_LOCATIONS = {
    136: {"city": "Seattle",       "state": "WA", "owm_q": "Seattle,US"},
    147: {"city": "New York",      "state": "NY", "owm_q": "New York,US"},
    143: {"city": "Philadelphia",  "state": "PA", "owm_q": "Philadelphia,US"},
    119: {"city": "Los Angeles",   "state": "CA", "owm_q": "Los Angeles,US"},
    139: {"city": "St. Petersburg","state": "FL", "owm_q": "Saint Petersburg,US"},
    121: {"city": "New York",      "state": "NY", "owm_q": "New York,US"},
    144: {"city": "Atlanta",       "state": "GA", "owm_q": "Atlanta,US"},
    118: {"city": "Kansas City",   "state": "MO", "owm_q": "Kansas City,US"},
    114: {"city": "Cleveland",     "state": "OH", "owm_q": "Cleveland,US"},
}

# ── API endpoints ─────────────────────────────────────────────────────────────
MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
OWM_API_BASE = "https://api.openweathermap.org/data/2.5"

# Set via env var (GitHub Actions secret)
OWM_API_KEY = os.environ.get("OWM_API_KEY", "")

# ── Scoring weights ───────────────────────────────────────────────────────────
WEIGHTS = {
    "schedule": 0.35,   # games played this week
    "pitcher":  0.30,   # matchup favorability
    "park":     0.20,   # stadium HR park factor
    "weather":  0.15,   # HR-friendly conditions
}

# ── League rules ─────────────────────────────────────────────────────────────
# Scoring system (points per HR in a single game):
#   1st HR in a game  → 1 pt  (2 pts if 3- or 4-run HR)
#   2nd HR in a game  → +1 bonus  (3 pts total that game, assuming solo HRs)
#   3rd HR in a game  → +2 bonus  (6 pts total that game, assuming solo HRs)
#   Pattern: nth HR = n pts  →  game total = triangular(n) = n*(n+1)/2
#
# Keep cost (points deducted from your score):
#   Weeks held:  1  2  3  4  5  6  ...
#   Keep cost:   0  1  2  3  4  5  ...  (cost = weeks_held - 1)
#
# Roster: 5 players per team
# Draft: every Sunday, traditional (not snake), lowest score picks first
# Cannot re-pick a player you dropped that same week
ROSTER_SIZE = 5
DRAFT_DAY = 6        # Sunday (weekday index: Mon=0 … Sun=6)

def keep_cost(weeks_held: int) -> int:
    """Points deducted to retain a player for another week. Free the first week."""
    return max(0, weeks_held - 1)

def hr_game_points(hr_count: int, run_values: list[int] | None = None) -> int:
    """
    Calculate points from `hr_count` home runs in a single game.
    run_values: list of RBI counts per HR (2-run=2, 3-run=3, 4-run=4).
    If not provided, assumes solo HRs (1 RBI each).
    """
    if hr_count <= 0:
        return 0
    # Base: nth HR in game = n points (triangular numbers)
    base = hr_count * (hr_count + 1) // 2
    # 3/4-run HR bonus: +1 extra point per qualifying HR
    bonus = 0
    if run_values:
        bonus = sum(1 for r in run_values if r >= 3)
    return base + bonus

# ── Week target ───────────────────────────────────────────────────────────────
def get_target_week() -> tuple[date, date]:
    """Returns (monday, sunday) for the current draft week (Mon–Sun)."""
    today = date.today()
    # Week runs Mon–Sun; draft/scoring deadline is Sunday
    days_since_monday = today.weekday()  # Mon=0
    monday = today - timedelta(days=days_since_monday)
    sunday = monday + timedelta(days=6)
    return monday, sunday

# ── Thresholds ────────────────────────────────────────────────────────────────
HIGH_OPPORTUNITY_GAMES = 6       # flag player if games >= this
RAIN_RISK_PCT = 60               # flag game if rain chance >= this
LEAGUE_AVG_HR9 = 1.25            # flag pitcher if HR/9 >= this (league avg ~1.1–1.3)
WIND_OUT_SPEED_MPH = 10          # flag "wind out" if wind >= this in favorable direction

# ── Park factors (HR index, league average = 100) ────────────────────────────
# Source: multi-year park factor averages. Values > 100 favor hitters.
# Keyed by home team_id.
PARK_FACTORS: dict[int, dict] = {
    # team_id: {hr_factor, park_name, notes}
    108: {"hr_factor": 98,  "park": "Angel Stadium",         "notes": "Neutral, marine layer"},
    109: {"hr_factor": 106, "park": "Chase Field",           "notes": "Retractable roof, warm"},
    110: {"hr_factor": 102, "park": "Camden Yards",          "notes": "Slight hitter lean"},
    111: {"hr_factor": 97,  "park": "Fenway Park",           "notes": "Green Monster helps LHH; hurts RHH"},
    112: {"hr_factor": 95,  "park": "Wrigley Field",         "notes": "Wind-dependent; can be great or awful"},
    113: {"hr_factor": 103, "park": "Great American Ball Park","notes": "Hitter-friendly; short porch RF"},
    114: {"hr_factor": 98,  "park": "Progressive Field",     "notes": "Neutral"},
    115: {"hr_factor": 124, "park": "Coors Field",           "notes": "ELITE: altitude adds ~20% HR rate"},
    116: {"hr_factor": 99,  "park": "Comerica Park",         "notes": "Neutral"},
    117: {"hr_factor": 110, "park": "Minute Maid Park",      "notes": "Short left field Crawford Boxes"},
    118: {"hr_factor": 103, "park": "Kauffman Stadium",      "notes": "Slight hitter lean"},
    119: {"hr_factor": 104, "park": "Dodger Stadium",        "notes": "Slight hitter lean, warm air"},
    120: {"hr_factor": 97,  "park": "Nationals Park",        "notes": "Slight pitcher lean"},
    121: {"hr_factor": 97,  "park": "Citi Field",            "notes": "Slight pitcher lean"},
    133: {"hr_factor": 108, "park": "Oakland Coliseum",      "notes": "Foul territory hurts; decent HR"},
    134: {"hr_factor": 98,  "park": "PNC Park",              "notes": "Neutral"},
    135: {"hr_factor": 98,  "park": "Petco Park",            "notes": "Marine layer; pitcher-friendly"},
    136: {"hr_factor": 97,  "park": "T-Mobile Park",         "notes": "Marine layer; pitcher-friendly"},
    137: {"hr_factor": 87,  "park": "Oracle Park",           "notes": "TOUGH: best pitcher's park in MLB"},
    138: {"hr_factor": 100, "park": "Busch Stadium",         "notes": "Neutral"},
    139: {"hr_factor": 99,  "park": "Tropicana Field",       "notes": "Dome; no weather factor"},
    140: {"hr_factor": 108, "park": "Globe Life Field",      "notes": "Hitter-friendly; retractable roof"},
    141: {"hr_factor": 100, "park": "Rogers Centre",         "notes": "Dome; neutral HR factor"},
    142: {"hr_factor": 100, "park": "Target Field",          "notes": "Neutral"},
    143: {"hr_factor": 107, "park": "Citizens Bank Park",    "notes": "Hitter-friendly; loud crowd"},
    144: {"hr_factor": 101, "park": "Truist Park",           "notes": "Slight hitter lean"},
    145: {"hr_factor": 99,  "park": "Guaranteed Rate Field", "notes": "Neutral"},
    146: {"hr_factor": 99,  "park": "loanDepot Park",        "notes": "Dome; neutral HR factor"},
    147: {"hr_factor": 111, "park": "Yankee Stadium",        "notes": "Short RF porch; elite for LHH sluggers"},
    158: {"hr_factor": 102, "park": "American Family Field", "notes": "Retractable roof; slight hitter lean"},
}

def park_factor_score(home_team_id: int) -> float:
    """Convert HR park factor (index ~87–124) to 0–100 agent score."""
    pf = PARK_FACTORS.get(home_team_id, {}).get("hr_factor", 100)
    # Map: 87 → 20, 100 → 50, 124 → 100
    return round(max(0, min(100, (pf - 87) / (124 - 87) * 80 + 20)), 1)

# ── Output paths ─────────────────────────────────────────────────────────────
# Relative to repo root — GH Actions runs from there
OUTPUT_DIR = "data/dinger_palooza"
OUTPUT_FILE = f"{OUTPUT_DIR}/draft_board.json"
INTERMEDIATE_DIR = f"{OUTPUT_DIR}/intermediate"
