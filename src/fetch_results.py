"""
Fetch real World Cup results from the vmfantasy.tv2.no open API and merge them
into data/results.json.

Data source
-----------
The TV2 "VM Fantasy" site (https://vmfantasy.tv2.no) is a SvelteKit app backed by
a public JSON API at https://vm-fantasyapi-production.up.railway.app. No token is
required. We use:
    GET /livescore/matches      -> every match: teams, status, score, goal events
    GET /livescore/top-scorers  -> players ranked by FANTASY points (not goals)

What is automated
-----------------
* Group-match scores               (matched onto our fixtures by team name)
* Group winners / runners-up        (computed from finished group results)
* Round-of-32 qualifier set         (top 2 of each group + 8 best third-placed)
* Current top goalscorer            (counted from goal events; overridable)
* A goal leaderboard                (for transparency)

What stays manual (for now)
---------------------------
The /livescore/matches feed currently contains only the 72 group matches and
carries no round/stage label, so the deeper knockout rounds (R16, QF, SF, Final)
and the eventual Champion can't yet be read automatically. Those fields in
results.json are PRESERVED by this script — fill them in by hand as the
tournament progresses, or extend `_derive_knockout()` once the knockout fixtures
appear in the feed.

Design: additive and safe. A network failure leaves results.json untouched
(apart from the timestamp); manually-entered values are never discarded.

Run:
    python src/fetch_results.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter, defaultdict

import config as C


def _empty_results():
    return {
        "last_updated": None,
        "group_scores": {},
        "group_winners": {},
        "group_runners": {},
        "bracket": {r: [] for r in C.KO_ROUNDS},
        "champion": None,
        "top_scorer": None,
        "goal_leaderboard": [],
        "games_played": 0,
        "games_total": 104,   # full WC 2026 has 104 matches
    }


def load_results():
    base = _empty_results()
    if os.path.exists(C.RESULTS_FILE):
        with open(C.RESULTS_FILE, encoding="utf-8") as f:
            base.update(json.load(f))
    for r in C.KO_ROUNDS:
        base.setdefault("bracket", {}).setdefault(r, [])
    return base


def load_fixtures():
    with open(C.FIXTURES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _api_get(path):
    req = urllib.request.Request(C.API_BASE + path, headers={"Origin": C.API_ORIGIN})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _fixture_index(fixtures):
    idx = {}
    for m in fixtures["group_matches"]:
        idx[(m["home"], m["away"])] = str(m["match_no"])
        idx[(m["away"], m["home"])] = str(m["match_no"])
    return idx


def _compute_group_tables(fixtures, group_scores):
    """
    Compute final group winners/runners-up and the Round-of-32 qualifier set,
    but ONLY for groups whose 6 matches are all finished.

    Ranking: points, then goal difference, then goals for (FIFA criteria 1-3;
    head-to-head is omitted — rare for an office pool, and any edge case can be
    corrected by hand in results.json).
    """
    # Map each match_no -> (home, away, group).
    match_meta = {}
    team_group = {}
    for grp, teams in fixtures["groups"].items():
        for t in teams:
            team_group[t] = grp
    for m in fixtures["group_matches"]:
        grp = team_group.get(m["home"]) or team_group.get(m["away"])
        match_meta[str(m["match_no"])] = (m["home"], m["away"], grp)

    # Tally finished matches per group.
    stats = defaultdict(lambda: {"pts": 0, "gf": 0, "ga": 0})
    played = defaultdict(int)
    for mno, (home, away, grp) in match_meta.items():
        if mno not in group_scores:
            continue
        hg, ag = group_scores[mno]
        played[grp] += 1
        sh, sa = stats[home], stats[away]
        sh["gf"] += hg; sh["ga"] += ag
        sa["gf"] += ag; sa["ga"] += hg
        if hg > ag:
            sh["pts"] += 3
        elif ag > hg:
            sa["pts"] += 3
        else:
            sh["pts"] += 1; sa["pts"] += 1

    winners, runners, thirds = {}, {}, []
    for grp, teams in fixtures["groups"].items():
        if played.get(grp, 0) < 6:  # group not complete yet
            continue
        ranked = sorted(
            teams,
            key=lambda t: (stats[t]["pts"], stats[t]["gf"] - stats[t]["ga"], stats[t]["gf"]),
            reverse=True,
        )
        winners[grp] = ranked[0]
        runners[grp] = ranked[1]
        third = ranked[2]
        thirds.append((third, stats[third]["pts"],
                       stats[third]["gf"] - stats[third]["ga"], stats[third]["gf"]))

    # Round of 32 = all winners + all runners-up + 8 best third-placed.
    # Only meaningful once ALL 12 groups are complete.
    r32 = []
    if len(winners) == C.GROUP_BLOCK_COUNT:
        r32 = list(winners.values()) + list(runners.values())
        thirds.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
        r32 += [t[0] for t in thirds[:8]]

    return winners, runners, sorted(r32)


def fetch_and_merge(results, now_iso=None):
    fixtures = load_fixtures()
    fidx = _fixture_index(fixtures)

    matches = _api_get(C.API_MATCHES)

    results["games_played"] = sum(1 for m in matches if m.get("status") == "FINISHED")
    results["games_total"] = len(matches)

    goals = Counter()
    for m in matches:
        home = C.canonical_team((m.get("homeTeam") or {}).get("name"))
        away = C.canonical_team((m.get("awayTeam") or {}).get("name"))
        hg, ag = m.get("homeScore"), m.get("awayScore")

        if m.get("status") == "FINISHED" and isinstance(hg, int) and isinstance(ag, int):
            mno = fidx.get((home, away))
            if mno:
                results["group_scores"][mno] = [hg, ag]

        for ev in m.get("fantasyEvents") or []:
            if ev.get("type") in C.GOAL_EVENT_TYPES:
                player = (ev.get("player") or {}).get("name")
                if player:
                    goals[player] += 1

    # Group winners / runners-up / R32 qualifiers (only for complete groups).
    winners, runners, r32 = _compute_group_tables(fixtures, results["group_scores"])
    if winners:
        results["group_winners"] = winners
        results["group_runners"] = runners
    if r32:
        # union, so a manually-entered set is never shrunk
        existing = set(results["bracket"].get("R32", []) or [])
        results["bracket"]["R32"] = sorted(existing | set(r32))

    # Goal leaderboard (informational). We deliberately do NOT auto-set the
    # official `top_scorer` from this: the goal-event feed is sparse mid-
    # tournament, and the 20-point golden-boot prize is only decided at the end.
    # Set results["top_scorer"] by hand once the winner is known — the goal
    # leaderboard below tells you who's leading.
    if goals:
        lead = goals.most_common(15)
        results["goal_leaderboard"] = [{"player": p, "goals": g} for p, g in lead]
        results["current_goal_leader"] = lead[0][0]

    if now_iso:
        results["last_updated"] = now_iso
    return results


def main():
    results = load_results()
    now_iso = os.environ.get("RUN_TIMESTAMP")
    try:
        results = fetch_and_merge(results, now_iso=now_iso)
        n_done = len(results["group_scores"])
        print(f"Fetched from vmfantasy.tv2.no — {n_done} match scores, "
              f"top scorer: {results.get('top_scorer')}")
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: result fetch failed ({e}). Keeping existing results.json.",
              file=sys.stderr)
    _save(results)


def _save(results):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    with open(C.RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Wrote {C.RESULTS_FILE}")


if __name__ == "__main__":
    main()
