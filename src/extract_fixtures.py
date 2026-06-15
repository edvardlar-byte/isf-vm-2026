"""
Extract the canonical fixture list from the reference workbook.

The fixture list (which teams play in each of the 72 group matches, on which
date) is treated as the single source of truth. Every participant predicts
against this same schedule, and real results are matched back onto it.

Run once (and re-run only if the reference schedule changes):

    python src/extract_fixtures.py

Produces data/fixtures.json.
"""
from __future__ import annotations

import json

import openpyxl
from openpyxl.utils import column_index_from_string as ci

import config as C


def _cell(ws, col_letter, row):
    return ws.cell(row=row, column=ci(col_letter)).value


def extract_fixtures(workbook_path=C.REFERENCE_WORKBOOK):
    wb = openpyxl.load_workbook(workbook_path, data_only=True)
    ws = wb[C.SHEET_NAME]

    matches = []
    for i in range(C.GROUP_MATCH_COUNT):
        row = C.SCHEDULE_FIRST_ROW + i
        no = _cell(ws, C.COL_MATCH_NO, row)
        home = C.canonical_team(_cell(ws, C.COL_HOME, row))
        away = C.canonical_team(_cell(ws, C.COL_AWAY, row))
        date = _cell(ws, C.COL_DATE, row)
        time = _cell(ws, C.COL_TIME, row)
        if not home or not away:
            continue
        matches.append({
            "match_no": int(no) if no is not None else i + 1,
            "stage": "group",
            "date": str(date) if date is not None else None,
            "time": str(time) if time is not None else None,
            "home": home,
            "away": away,
        })

    # Which teams belong to which group (from the standings blocks).
    groups = {}
    for b in range(C.GROUP_BLOCK_COUNT):
        first = C.GROUP_BLOCK_FIRST_ROW + b * C.GROUP_BLOCK_STEP
        label = _cell(ws, C.COL_GROUP_LABEL, first)  # e.g. "Group A"
        teams = []
        for r in range(first, first + 4):
            team = C.canonical_team(_cell(ws, C.COL_PLACE_TEAM, r))
            if team:
                teams.append(team)
        if label and str(label).lower().startswith("group"):
            groups[str(label)] = sorted(teams)

    fixtures = {
        "source": "extracted from reference workbook",
        "group_matches": matches,
        "groups": groups,
    }
    return fixtures


def main():
    fixtures = extract_fixtures()
    with open(C.FIXTURES_FILE, "w", encoding="utf-8") as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)
    print(f"Wrote {C.FIXTURES_FILE}")
    print(f"  {len(fixtures['group_matches'])} group matches, "
          f"{len(fixtures['groups'])} groups")


if __name__ == "__main__":
    main()
