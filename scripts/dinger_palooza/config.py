"""
Dinger Palooza — shared configuration for all agents.
"""

import os
from datetime import date, timedelta

# ── Candidate sluggers ────────────────────────────────────────────────────────
# team_id from the MLB Stats API (/api/v1/teams)
#
# bats: "L" = left-handed, "R" = right-handed, "S" = switch hitter
# Switch hitters always bat from the favorable side → treat as neutral for platoon.
#
# NOTE: Team assignments are the *seed* used for initial lookup. The schedule
# agent now uses MLB people/search to auto-detect the player's current team and
# will override team_id/team/team_abbr at runtime if a trade occurred.
# Players with a stale team show a ⚠ TEAM? badge on the draft board.
# If a player shows 0 pitcher matchup data, verify their team_id here and update.
PLAYERS = [
    # ── Elite tier ────────────────────────────────────────────────────────────
    {"name": "Cal Raleigh",          "team": "Seattle Mariners",        "team_id": 136, "team_abbr": "SEA", "mlb_id": None, "bats": "L"},
    {"name": "Aaron Judge",          "team": "New York Yankees",        "team_id": 147, "team_abbr": "NYY", "mlb_id": None, "bats": "R"},
    {"name": "Kyle Schwarber",       "team": "Philadelphia Phillies",   "team_id": 143, "team_abbr": "PHI", "mlb_id": None, "bats": "L"},
    {"name": "Shohei Ohtani",        "team": "Los Angeles Dodgers",     "team_id": 119, "team_abbr": "LAD", "mlb_id": None, "bats": "L"},
    {"name": "Junior Caminero",      "team": "Tampa Bay Rays",          "team_id": 139, "team_abbr": "TB",  "mlb_id": None, "bats": "R"},
    {"name": "Juan Soto",            "team": "New York Mets",           "team_id": 121, "team_abbr": "NYM", "mlb_id": None, "bats": "L"},
    {"name": "Ronald Acuna Jr",      "team": "Atlanta Braves",          "team_id": 144, "team_abbr": "ATL", "mlb_id": None, "bats": "R"},
    {"name": "Bobby Witt Jr",        "team": "Kansas City Royals",      "team_id": 118, "team_abbr": "KC",  "mlb_id": None, "bats": "R"},
    {"name": "Jose Ramirez",         "team": "Cleveland Guardians",     "team_id": 114, "team_abbr": "CLE", "mlb_id": None, "bats": "S"},
    {"name": "Pete Alonso",          "team": "New York Mets",           "team_id": 121, "team_abbr": "NYM", "mlb_id": None, "bats": "R"},
    # ── 35–45 HR tier ─────────────────────────────────────────────────────────
    {"name": "Yordan Alvarez",       "team": "Houston Astros",          "team_id": 117, "team_abbr": "HOU", "mlb_id": None, "bats": "L"},
    {"name": "Matt Olson",           "team": "Atlanta Braves",          "team_id": 144, "team_abbr": "ATL", "mlb_id": None, "bats": "L"},
    {"name": "Bryce Harper",         "team": "Philadelphia Phillies",   "team_id": 143, "team_abbr": "PHI", "mlb_id": None, "bats": "L"},
    {"name": "Giancarlo Stanton",    "team": "New York Yankees",        "team_id": 147, "team_abbr": "NYY", "mlb_id": None, "bats": "R"},
    {"name": "Manny Machado",        "team": "San Diego Padres",        "team_id": 135, "team_abbr": "SD",  "mlb_id": None, "bats": "R"},
    {"name": "Rafael Devers",        "team": "Boston Red Sox",          "team_id": 111, "team_abbr": "BOS", "mlb_id": None, "bats": "L"},
    {"name": "Gunnar Henderson",     "team": "Baltimore Orioles",       "team_id": 110, "team_abbr": "BAL", "mlb_id": None, "bats": "L"},
    {"name": "Corey Seager",         "team": "Texas Rangers",           "team_id": 140, "team_abbr": "TEX", "mlb_id": None, "bats": "L"},
    {"name": "Vladimir Guerrero Jr", "team": "Toronto Blue Jays",       "team_id": 141, "team_abbr": "TOR", "mlb_id": None, "bats": "R"},
    {"name": "Fernando Tatis Jr",    "team": "San Diego Padres",        "team_id": 135, "team_abbr": "SD",  "mlb_id": None, "bats": "R"},
    {"name": "Austin Riley",         "team": "Atlanta Braves",          "team_id": 144, "team_abbr": "ATL", "mlb_id": None, "bats": "R"},
    {"name": "Marcell Ozuna",        "team": "Atlanta Braves",          "team_id": 144, "team_abbr": "ATL", "mlb_id": None, "bats": "R"},
    {"name": "Jazz Chisholm Jr",     "team": "New York Yankees",        "team_id": 147, "team_abbr": "NYY", "mlb_id": None, "bats": "L"},
    {"name": "Cody Bellinger",       "team": "New York Yankees",        "team_id": 147, "team_abbr": "NYY", "mlb_id": None, "bats": "L"},
    {"name": "Brent Rooker",         "team": "Athletics",               "team_id": 133, "team_abbr": "ATH", "mlb_id": None, "bats": "R"},
    {"name": "Kyle Tucker",          "team": "Chicago Cubs",            "team_id": 112, "team_abbr": "CHC", "mlb_id": None, "bats": "L"},
    # ── 25–35 HR tier ─────────────────────────────────────────────────────────
    {"name": "Julio Rodriguez",      "team": "Seattle Mariners",        "team_id": 136, "team_abbr": "SEA", "mlb_id": None, "bats": "R"},
    {"name": "Randy Arozarena",      "team": "Seattle Mariners",        "team_id": 136, "team_abbr": "SEA", "mlb_id": None, "bats": "R"},
    {"name": "Freddie Freeman",      "team": "Los Angeles Dodgers",     "team_id": 119, "team_abbr": "LAD", "mlb_id": None, "bats": "L"},
    {"name": "Mookie Betts",         "team": "Los Angeles Dodgers",     "team_id": 119, "team_abbr": "LAD", "mlb_id": None, "bats": "R"},
    {"name": "Teoscar Hernandez",    "team": "Los Angeles Dodgers",     "team_id": 119, "team_abbr": "LAD", "mlb_id": None, "bats": "R"},
    {"name": "Max Muncy",            "team": "Los Angeles Dodgers",     "team_id": 119, "team_abbr": "LAD", "mlb_id": None, "bats": "L"},
    {"name": "Will Smith",           "team": "Los Angeles Dodgers",     "team_id": 119, "team_abbr": "LAD", "mlb_id": None, "bats": "R"},
    {"name": "Francisco Lindor",     "team": "New York Mets",           "team_id": 121, "team_abbr": "NYM", "mlb_id": None, "bats": "S"},
    {"name": "Mark Vientos",         "team": "New York Mets",           "team_id": 121, "team_abbr": "NYM", "mlb_id": None, "bats": "R"},
    {"name": "Marcus Semien",        "team": "New York Mets",           "team_id": 121, "team_abbr": "NYM", "mlb_id": None, "bats": "R"},
    {"name": "Trea Turner",          "team": "Philadelphia Phillies",   "team_id": 143, "team_abbr": "PHI", "mlb_id": None, "bats": "R"},
    {"name": "Alec Bohm",            "team": "Philadelphia Phillies",   "team_id": 143, "team_abbr": "PHI", "mlb_id": None, "bats": "R"},
    {"name": "J.T. Realmuto",        "team": "Philadelphia Phillies",   "team_id": 143, "team_abbr": "PHI", "mlb_id": None, "bats": "R"},
    {"name": "Nick Castellanos",     "team": "Philadelphia Phillies",   "team_id": 143, "team_abbr": "PHI", "mlb_id": None, "bats": "R"},
    {"name": "Tyler O'Neill",        "team": "Baltimore Orioles",       "team_id": 110, "team_abbr": "BAL", "mlb_id": None, "bats": "R"},
    {"name": "Triston Casas",        "team": "Boston Red Sox",          "team_id": 111, "team_abbr": "BOS", "mlb_id": None, "bats": "L"},
    {"name": "Jarren Duran",         "team": "Boston Red Sox",          "team_id": 111, "team_abbr": "BOS", "mlb_id": None, "bats": "L"},
    {"name": "Alex Bregman",         "team": "Boston Red Sox",          "team_id": 111, "team_abbr": "BOS", "mlb_id": None, "bats": "R"},
    {"name": "Adley Rutschman",      "team": "Baltimore Orioles",       "team_id": 110, "team_abbr": "BAL", "mlb_id": None, "bats": "S"},
    {"name": "Anthony Santander",    "team": "Baltimore Orioles",       "team_id": 110, "team_abbr": "BAL", "mlb_id": None, "bats": "S"},
    {"name": "Ryan Mountcastle",     "team": "Baltimore Orioles",       "team_id": 110, "team_abbr": "BAL", "mlb_id": None, "bats": "R"},
    {"name": "Colton Cowser",        "team": "Baltimore Orioles",       "team_id": 110, "team_abbr": "BAL", "mlb_id": None, "bats": "L"},
    {"name": "Adolis Garcia",        "team": "Texas Rangers",           "team_id": 140, "team_abbr": "TEX", "mlb_id": None, "bats": "R"},
    {"name": "Nathaniel Lowe",       "team": "Texas Rangers",           "team_id": 140, "team_abbr": "TEX", "mlb_id": None, "bats": "L"},
    {"name": "Evan Carter",          "team": "Texas Rangers",           "team_id": 140, "team_abbr": "TEX", "mlb_id": None, "bats": "L"},
    {"name": "Josh Jung",            "team": "Texas Rangers",           "team_id": 140, "team_abbr": "TEX", "mlb_id": None, "bats": "R"},
    {"name": "Luis Robert Jr",       "team": "Chicago White Sox",       "team_id": 145, "team_abbr": "CWS", "mlb_id": None, "bats": "R"},
    {"name": "Andrew Vaughn",        "team": "Chicago White Sox",       "team_id": 145, "team_abbr": "CWS", "mlb_id": None, "bats": "R"},
    {"name": "Spencer Torkelson",    "team": "Detroit Tigers",          "team_id": 116, "team_abbr": "DET", "mlb_id": None, "bats": "R"},
    {"name": "Riley Greene",         "team": "Detroit Tigers",          "team_id": 116, "team_abbr": "DET", "mlb_id": None, "bats": "L"},
    {"name": "Christian Yelich",     "team": "Milwaukee Brewers",       "team_id": 158, "team_abbr": "MIL", "mlb_id": None, "bats": "L"},
    {"name": "William Contreras",    "team": "Milwaukee Brewers",       "team_id": 158, "team_abbr": "MIL", "mlb_id": None, "bats": "R"},
    {"name": "Willy Adames",         "team": "Milwaukee Brewers",       "team_id": 158, "team_abbr": "MIL", "mlb_id": None, "bats": "R"},
    {"name": "Jackson Chourio",      "team": "Milwaukee Brewers",       "team_id": 158, "team_abbr": "MIL", "mlb_id": None, "bats": "R"},
    {"name": "Ryan McMahon",         "team": "Colorado Rockies",        "team_id": 115, "team_abbr": "COL", "mlb_id": None, "bats": "L"},
    {"name": "Nolan Jones",          "team": "Colorado Rockies",        "team_id": 115, "team_abbr": "COL", "mlb_id": None, "bats": "L"},
    {"name": "Ezequiel Tovar",       "team": "Colorado Rockies",        "team_id": 115, "team_abbr": "COL", "mlb_id": None, "bats": "R"},
    {"name": "Hunter Goodman",       "team": "Colorado Rockies",        "team_id": 115, "team_abbr": "COL", "mlb_id": None, "bats": "R"},
    {"name": "Mike Trout",           "team": "Los Angeles Angels",      "team_id": 108, "team_abbr": "LAA", "mlb_id": None, "bats": "R"},
    {"name": "Taylor Ward",          "team": "Los Angeles Angels",      "team_id": 108, "team_abbr": "LAA", "mlb_id": None, "bats": "R"},
    {"name": "Zach Neto",            "team": "Los Angeles Angels",      "team_id": 108, "team_abbr": "LAA", "mlb_id": None, "bats": "R"},
    {"name": "Salvador Perez",       "team": "Kansas City Royals",      "team_id": 118, "team_abbr": "KC",  "mlb_id": None, "bats": "R"},
    {"name": "Vinnie Pasquantino",   "team": "Kansas City Royals",      "team_id": 118, "team_abbr": "KC",  "mlb_id": None, "bats": "L"},
    {"name": "MJ Melendez",          "team": "Kansas City Royals",      "team_id": 118, "team_abbr": "KC",  "mlb_id": None, "bats": "L"},
    {"name": "Yandy Diaz",           "team": "Tampa Bay Rays",          "team_id": 139, "team_abbr": "TB",  "mlb_id": None, "bats": "R"},
    {"name": "Brandon Lowe",         "team": "Tampa Bay Rays",          "team_id": 139, "team_abbr": "TB",  "mlb_id": None, "bats": "L"},
    {"name": "Josh Naylor",          "team": "Cleveland Guardians",     "team_id": 114, "team_abbr": "CLE", "mlb_id": None, "bats": "L"},
    {"name": "Kyle Manzardo",        "team": "Cleveland Guardians",     "team_id": 114, "team_abbr": "CLE", "mlb_id": None, "bats": "L"},
    {"name": "Rhys Hoskins",         "team": "Cleveland Guardians",     "team_id": 114, "team_abbr": "CLE", "mlb_id": None, "bats": "R"},
    {"name": "Jake Cronenworth",     "team": "San Diego Padres",        "team_id": 135, "team_abbr": "SD",  "mlb_id": None, "bats": "L"},
    {"name": "Xander Bogaerts",      "team": "San Diego Padres",        "team_id": 135, "team_abbr": "SD",  "mlb_id": None, "bats": "R"},
    {"name": "Jorge Soler",          "team": "Miami Marlins",           "team_id": 146, "team_abbr": "MIA", "mlb_id": None, "bats": "R"},
    {"name": "Dylan Crews",          "team": "Washington Nationals",    "team_id": 120, "team_abbr": "WSH", "mlb_id": None, "bats": "R"},
    {"name": "James Wood",           "team": "Washington Nationals",    "team_id": 120, "team_abbr": "WSH", "mlb_id": None, "bats": "L"},
    {"name": "CJ Abrams",            "team": "Washington Nationals",    "team_id": 120, "team_abbr": "WSH", "mlb_id": None, "bats": "L"},
    {"name": "Keibert Ruiz",         "team": "Washington Nationals",    "team_id": 120, "team_abbr": "WSH", "mlb_id": None, "bats": "S"},
    {"name": "Elly De La Cruz",      "team": "Cincinnati Reds",         "team_id": 113, "team_abbr": "CIN", "mlb_id": None, "bats": "S"},
    {"name": "Spencer Steer",        "team": "Cincinnati Reds",         "team_id": 113, "team_abbr": "CIN", "mlb_id": None, "bats": "R"},
    {"name": "Jeimer Candelario",    "team": "Cincinnati Reds",         "team_id": 113, "team_abbr": "CIN", "mlb_id": None, "bats": "S"},
    {"name": "Lawrence Butler",      "team": "Athletics",               "team_id": 133, "team_abbr": "ATH", "mlb_id": None, "bats": "L"},
    {"name": "Seiya Suzuki",         "team": "Chicago Cubs",            "team_id": 112, "team_abbr": "CHC", "mlb_id": None, "bats": "R"},
    {"name": "Ian Happ",             "team": "Chicago Cubs",            "team_id": 112, "team_abbr": "CHC", "mlb_id": None, "bats": "S"},
    {"name": "Nolan Arenado",        "team": "St. Louis Cardinals",     "team_id": 138, "team_abbr": "STL", "mlb_id": None, "bats": "R"},
    {"name": "Nolan Gorman",         "team": "St. Louis Cardinals",     "team_id": 138, "team_abbr": "STL", "mlb_id": None, "bats": "L"},
    {"name": "Paul Goldschmidt",     "team": "St. Louis Cardinals",     "team_id": 138, "team_abbr": "STL", "mlb_id": None, "bats": "R"},
    {"name": "Michael Harris II",    "team": "Atlanta Braves",          "team_id": 144, "team_abbr": "ATL", "mlb_id": None, "bats": "L"},
    {"name": "Matt Chapman",         "team": "San Francisco Giants",    "team_id": 137, "team_abbr": "SF",  "mlb_id": None, "bats": "R"},
    {"name": "Heliot Ramos",         "team": "San Francisco Giants",    "team_id": 137, "team_abbr": "SF",  "mlb_id": None, "bats": "R"},
    {"name": "Christian Walker",     "team": "Houston Astros",          "team_id": 117, "team_abbr": "HOU", "mlb_id": None, "bats": "R"},
    {"name": "Anthony Volpe",        "team": "New York Yankees",        "team_id": 147, "team_abbr": "NYY", "mlb_id": None, "bats": "R"},
    {"name": "Royce Lewis",          "team": "Minnesota Twins",         "team_id": 142, "team_abbr": "MIN", "mlb_id": None, "bats": "R"},
    {"name": "Carlos Correa",        "team": "Minnesota Twins",         "team_id": 142, "team_abbr": "MIN", "mlb_id": None, "bats": "R"},
    {"name": "Byron Buxton",         "team": "Minnesota Twins",         "team_id": 142, "team_abbr": "MIN", "mlb_id": None, "bats": "R"},
    {"name": "Jo Adell",             "team": "Los Angeles Angels",      "team_id": 108, "team_abbr": "LAA", "mlb_id": None, "bats": "R"},
]

# Stadium locations for weather lookups (city, state/country for OWM query)
# Covers all 30 MLB home venues.
STADIUM_LOCATIONS = {
    108: {"city": "Anaheim",        "state": "CA", "owm_q": "Anaheim,US"},
    109: {"city": "Phoenix",        "state": "AZ", "owm_q": "Phoenix,US"},
    110: {"city": "Baltimore",      "state": "MD", "owm_q": "Baltimore,US"},
    111: {"city": "Boston",         "state": "MA", "owm_q": "Boston,US"},
    112: {"city": "Chicago",        "state": "IL", "owm_q": "Chicago,US"},
    113: {"city": "Cincinnati",     "state": "OH", "owm_q": "Cincinnati,US"},
    114: {"city": "Cleveland",      "state": "OH", "owm_q": "Cleveland,US"},
    115: {"city": "Denver",         "state": "CO", "owm_q": "Denver,US"},
    116: {"city": "Detroit",        "state": "MI", "owm_q": "Detroit,US"},
    117: {"city": "Houston",        "state": "TX", "owm_q": "Houston,US"},
    118: {"city": "Kansas City",    "state": "MO", "owm_q": "Kansas City,US"},
    119: {"city": "Los Angeles",    "state": "CA", "owm_q": "Los Angeles,US"},
    120: {"city": "Washington",     "state": "DC", "owm_q": "Washington,US"},
    121: {"city": "New York",       "state": "NY", "owm_q": "New York,US"},
    133: {"city": "Sacramento",     "state": "CA", "owm_q": "Sacramento,US"},
    134: {"city": "Pittsburgh",     "state": "PA", "owm_q": "Pittsburgh,US"},
    135: {"city": "San Diego",      "state": "CA", "owm_q": "San Diego,US"},
    136: {"city": "Seattle",        "state": "WA", "owm_q": "Seattle,US"},
    137: {"city": "San Francisco",  "state": "CA", "owm_q": "San Francisco,US"},
    138: {"city": "St. Louis",      "state": "MO", "owm_q": "Saint Louis,US"},
    139: {"city": "St. Petersburg", "state": "FL", "owm_q": "Saint Petersburg,US"},
    140: {"city": "Arlington",      "state": "TX", "owm_q": "Arlington,US"},
    141: {"city": "Toronto",        "state": "ON", "owm_q": "Toronto,CA"},
    142: {"city": "Minneapolis",    "state": "MN", "owm_q": "Minneapolis,US"},
    143: {"city": "Philadelphia",   "state": "PA", "owm_q": "Philadelphia,US"},
    144: {"city": "Atlanta",        "state": "GA", "owm_q": "Atlanta,US"},
    145: {"city": "Chicago",        "state": "IL", "owm_q": "Chicago,US"},
    146: {"city": "Miami",          "state": "FL", "owm_q": "Miami,US"},
    147: {"city": "New York",       "state": "NY", "owm_q": "New York,US"},
    158: {"city": "Milwaukee",      "state": "WI", "owm_q": "Milwaukee,US"},
}

# ── API endpoints ─────────────────────────────────────────────────────────────
MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
OWM_API_BASE = "https://api.openweathermap.org/data/2.5"

# Set via env var (GitHub Actions secret)
OWM_API_KEY = os.environ.get("OWM_API_KEY", "")

# ── Scoring weights ───────────────────────────────────────────────────────────
WEIGHTS = {
    "schedule": 0.40,   # effective games (rain-risk games discounted)
    "pitcher":  0.30,   # matchup favorability
    "park":     0.30,   # stadium HR park factor
}

# Rain-risk games reduce effective_games by this fraction each.
# 0.5 = a rain-risk game is worth half a game opportunity.
RAIN_GAME_DISCOUNT = 0.5

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
    """
    Returns (monday, sunday) for the UPCOMING draft week.

    Draft runs Sunday → next Mon–Sun:
      - Triggered on Sunday (cron day): returns NEXT Monday through NEXT Sunday.
      - Triggered any other day: returns the current Monday–Sunday.
    Use --week YYYY-MM-DD to override (e.g. opening week partial).
    """
    today = date.today()
    days_since_monday = today.weekday()  # Mon=0 … Sun=6
    this_monday = today - timedelta(days=days_since_monday)
    if today.weekday() == 6:  # Sunday — draft day, look ahead
        monday = this_monday + timedelta(days=7)
    else:
        monday = this_monday
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
