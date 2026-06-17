"""
Central configuration for the ISF World Cup prediction competition.

Everything that might need tweaking lives here: file paths, the scoring
table, the layout of the Excel template, and the team-name normalisation
map used to reconcile the spreadsheet's names with the football API's names.
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTICIPANTS_DIR = os.path.join(ROOT, "participants")
DATA_DIR = os.path.join(ROOT, "data")
PREDICTIONS_DIR = os.path.join(DATA_DIR, "predictions")
DOCS_DIR = os.path.join(ROOT, "docs")

FIXTURES_FILE = os.path.join(DATA_DIR, "fixtures.json")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
TOPSCORERS_FILE = os.path.join(DATA_DIR, "topscorers.csv")

# The reference workbook whose fixture list is treated as canonical.
# Every participant is assumed to predict against this same set of fixtures.
REFERENCE_WORKBOOK = os.path.join(PARTICIPANTS_DIR, "edvard_tipping.xlsx")

# --------------------------------------------------------------------------
# Scoring table  (from the competition rules — "Poengsanking")
# --------------------------------------------------------------------------
POINTS = {
    "group_outcome": 1,     # correct W/D/L in a group match
    "group_exact": 2,       # correct exact score — ADDED on top of the outcome point
                            # (so a perfect scoreline = 1 + 2 = 3 points)
    "group_winner": 5,      # correct group winner
    "group_runner_up": 7,   # correct group runner-up
    "reach_R32": 5,         # per team correctly predicted to reach Round of 32
    "reach_R16": 8,         # per team correctly predicted to reach Round of 16
    "reach_QF": 16,         # per team correctly predicted to reach Quarterfinal
    "reach_SF": 32,         # per team correctly predicted to reach Semifinal
    "reach_Final": 20,      # per team correctly predicted to reach Final
    "champion": 40,         # correct World Champion
    "top_scorer": 20,       # correct top scorer
}

# The cumulative knockout rounds, ordered shallow -> deep.
KO_ROUNDS = ["R32", "R16", "QF", "SF", "Final"]
KO_POINTS_KEY = {r: f"reach_{r}" for r in KO_ROUNDS}

# Max possible (sanity check — should total 1004)
MAX_POSSIBLE = (
    72 * POINTS["group_outcome"]      # 72  (outcome is implied by exact, see scoring note)
    + 72 * POINTS["group_exact"]      # 144
    + 12 * POINTS["group_winner"]     # 60
    + 12 * POINTS["group_runner_up"]  # 84
    + 32 * POINTS["reach_R32"]        # 160
    + 16 * POINTS["reach_R16"]        # 128
    + 8 * POINTS["reach_QF"]          # 128
    + 4 * POINTS["reach_SF"]          # 128
    + 2 * POINTS["reach_Final"]       # 40
    + POINTS["champion"]              # 40
    + POINTS["top_scorer"]            # 20
)  # = 1004

# --------------------------------------------------------------------------
# Excel template layout  (verified against the excely.com 2026 template)
# Sheet "2026 World Cup"
# --------------------------------------------------------------------------
SHEET_NAME = "2026 World Cup"

# Group-stage schedule + predicted scores: rows 7..78 (72 matches).
SCHEDULE_FIRST_ROW = 7
GROUP_MATCH_COUNT = 72
COL_MATCH_NO = "A"
COL_DATE = "C"
COL_TIME = "D"
COL_HOME = "E"
COL_HOME_GOALS = "F"
COL_AWAY_GOALS = "G"
COL_AWAY = "H"

# Group standings table: blocks of 4 rows starting at row 8, step 6.
# Within a block, column AD = place (1..4), AE = team name.
GROUP_BLOCK_FIRST_ROW = 8
GROUP_BLOCK_STEP = 6
GROUP_BLOCK_COUNT = 12
COL_GROUP_LABEL = "J"     # holds "Group A".."Group L" on the block's first row
COL_PLACE = "AD"
COL_PLACE_TEAM = "AE"

# Knockout bracket: (team-name column) for each round region, scanned rows 7..110.
KO_TEAM_COLUMNS = {
    "R32": "BL",
    "R16": "BS",
    "QF": "BZ",
    "SF": "CG",
}
# The Final region (CM header / CN teams) also contains the third-place
# play-off, so it is parsed specially.
COL_FINAL_HEADER = "CM"
COL_FINAL_TEAM = "CN"
COL_FINAL_SCORE = "CO"
FINAL_HEADER_TEXT = "Final"
THIRD_PLACE_HEADER_TEXT = "Third-Place Play-Off"

SCAN_LAST_ROW = 110

# A "rare hit" 💎 = a correct EXACT scoreline that at most this fraction of
# participants also got (min 1). With ~24 players, 0.10 -> at most 2 people.
RARE_HIT_FRACTION = 0.10

# Optional cell where a participant may have typed their top-scorer pick.
# The parser scans the whole sheet for a label matching TOPSCORER_LABELS and
# reads the cell immediately to its right. Falls back to data/topscorers.csv.
TOPSCORER_LABELS = ("toppscorer", "top scorer", "topscorer", "golden boot")

# --------------------------------------------------------------------------
# Results data source — vmfantasy.tv2.no open API (no token required)
# Discovered from the site's JS bundle; these endpoints return public JSON.
# --------------------------------------------------------------------------
API_BASE = "https://vm-fantasyapi-production.up.railway.app"
API_MATCHES = "/livescore/matches"          # all matches + scores + goal events
API_TOPSCORERS = "/livescore/top-scorers"   # (ranked by fantasy points, not goals)
API_ORIGIN = "https://vmfantasy.tv2.no"     # sent as Origin header
GOAL_EVENT_TYPES = ("GOAL", "PENALTY_GOAL")

# --------------------------------------------------------------------------
# Team-name normalisation
# Maps spelling variants (from the API or from typos) to the canonical name
# used in the Excel template. Extend freely as needed.
# --------------------------------------------------------------------------
TEAM_ALIASES = {
    "south korea": "Korea Republic",
    "korea, republic of": "Korea Republic",
    "republic of korea": "Korea Republic",
    "usa": "United States",
    "united states of america": "United States",
    "czechia": "Czech Republic",
    "ivory coast": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "côte d'ivoire": "Ivory Coast",
    "dr congo": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "congo dr": "DR Congo",
    "bosnia": "Bosnia and Herzegovina",
    "bosnia & herzegovina": "Bosnia and Herzegovina",
    "curacao": "Curaçao",
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "cape verde islands": "Cape Verde",
    "cabo verde": "Cape Verde",
    "iran, islamic republic of": "Iran",
    # --- vmfantasy.tv2.no spellings ---
    "bosnia-hercegovina": "Bosnia and Herzegovina",
    "dr kongo": "DR Congo",
    "ir iran": "Iran",
    "sverige": "Sweden",
}


def canonical_team(name):
    """Return the canonical team name for any spelling variant."""
    if name is None:
        return None
    s = str(name).strip()
    return TEAM_ALIASES.get(s.lower(), s)
