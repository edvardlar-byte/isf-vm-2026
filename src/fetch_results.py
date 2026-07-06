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


# Knockout bracket sizes for the 48-team format, shallow -> deep. The last
# chunk holds the 3rd-place play-off + the final (2 matches).
KO_ROUND_SIZES = [("R32", 16), ("R16", 8), ("QF", 4), ("SF", 2), ("Final", 2)]


def _derive_knockout(matches, fidx):
    """
    Classify knockout matches into rounds by kickoff order (the feed carries no
    round label, but adds matches in bracket order). Returns the set of teams
    reaching each round, plus the champion (winner of the final).

    A match is 'knockout' if its team pairing isn't one of the 72 group fixtures.
    """
    def ch(x):
        return C.canonical_team((x.get("homeTeam") or {}).get("name"))

    def ca(x):
        return C.canonical_team((x.get("awayTeam") or {}).get("name"))

    def kickoff(x):
        return x.get("kickoffAt") or ""

    ko = [x for x in matches if (ch(x), ca(x)) not in fidx]
    ko.sort(key=kickoff)

    rounds, champion, i = {}, None, 0
    for name, size in KO_ROUND_SIZES:
        chunk = ko[i:i + size]
        i += size
        if not chunk:
            continue
        if name != "Final":
            teams = sorted({t for x in chunk for t in (ch(x), ca(x)) if t})
            if teams:
                rounds[name] = teams
        else:
            # Chunk = 3rd-place play-off + final; the final is the latest match.
            final = max(chunk, key=kickoff)
            finalists = [t for t in (ch(final), ca(final)) if t]
            if finalists:
                rounds["Final"] = finalists
            hs, as_ = final.get("homeScore"), final.get("awayScore")
            if final.get("status") == "FINISHED" and isinstance(hs, int) and isinstance(as_, int):
                champion = ch(final) if hs > as_ else ca(final) if as_ > hs else None
    return rounds, champion


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

    # Group winners / runners-up (computed once each group is complete).
    winners, runners, r32 = _compute_group_tables(fixtures, results["group_scores"])
    if winners:
        results["group_winners"] = winners
        results["group_runners"] = runners

    # Most recent finished match overall (group OR knockout), for the "last
    # result" bar. Ordering by kickoff so knockout games show once played.
    finished = [m for m in matches
                if m.get("status") == "FINISHED"
                and isinstance(m.get("homeScore"), int) and isinstance(m.get("awayScore"), int)]
    if finished:
        last = max(finished, key=lambda x: x.get("kickoffAt") or "")
        lh = C.canonical_team((last.get("homeTeam") or {}).get("name"))
        la = C.canonical_team((last.get("awayTeam") or {}).get("name"))
        results["last_match"] = {
            "home": lh, "away": la,
            "home_score": last["homeScore"], "away_score": last["awayScore"],
            "is_group": (lh, la) in fidx,
        }

    # Knockout rounds from the actual knockout fixtures (ground truth). Falls
    # back to the group-standings R32 estimate before knockout matches exist.
    ko_rounds, champion = _derive_knockout(matches, fidx)
    if not ko_rounds.get("R32") and r32:
        ko_rounds["R32"] = r32
    for rnd, teams in ko_rounds.items():
        if teams:
            results["bracket"][rnd] = sorted(teams) if rnd != "Final" else teams
    if champion:
        results["champion"] = champion

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
