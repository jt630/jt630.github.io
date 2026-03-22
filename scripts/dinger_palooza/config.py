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
    "schedule": 0.40,   # games played this week
    "pitcher":  0.35,   # matchup favorability
    "weather":  0.25,   # HR-friendly conditions
}

# ── Week target ───────────────────────────────────────────────────────────────
def get_target_week() -> tuple[date, date]:
    """Returns (monday, sunday) for the upcoming MLB week."""
    today = date.today()
    # Next Monday (or today if it's Monday)
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    monday = today + timedelta(days=days_until_monday)
    sunday = monday + timedelta(days=6)
    return monday, sunday

# ── Thresholds ────────────────────────────────────────────────────────────────
HIGH_OPPORTUNITY_GAMES = 6       # flag player if games >= this
RAIN_RISK_PCT = 60               # flag game if rain chance >= this
LEAGUE_AVG_HR9 = 1.25            # flag pitcher if HR/9 >= this (league avg ~1.1–1.3)
WIND_OUT_SPEED_MPH = 10          # flag "wind out" if wind >= this in favorable direction

# ── Output paths ─────────────────────────────────────────────────────────────
# Relative to repo root — GH Actions runs from there
OUTPUT_DIR = "data/dinger_palooza"
OUTPUT_FILE = f"{OUTPUT_DIR}/draft_board.json"
INTERMEDIATE_DIR = f"{OUTPUT_DIR}/intermediate"
