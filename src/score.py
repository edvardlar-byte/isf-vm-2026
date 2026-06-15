"""
Score every participant's predictions against the actual results and produce
a standings table.

Reads:
    data/predictions/*.json   (from parse_predictions.py)
    data/results.json         (actual results, see fetch_results.py)
Returns / writes:
    data/standings.json
"""
from __future__ import annotations

import glob
import json
import os
import re
import unicodedata

import config as C


def _sign(a, b):
    return (a > b) - (a < b)


def _norm_name(s):
    """Lowercase, strip accents and punctuation -> set of name tokens."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return set(t for t in s.split() if t)


def _scorer_match(guess, actual):
    """
    True if a (possibly partial) guess names the actual top scorer.
    Matches when one name's tokens are a subset of the other's — so "Mbappé"
    matches "Kylian Mbappé", and "Mikel Oyarzabal" matches "Oyarzabal".
    """
    g, a = _norm_name(guess), _norm_name(actual)
    if not g or not a:
        return False
    return g <= a or a <= g


def load_results():
    if not os.path.exists(C.RESULTS_FILE):
        return {
            "last_updated": None,
            "group_scores": {},
            "group_winners": {},
            "group_runners": {},
            "bracket": {r: [] for r in C.KO_ROUNDS},
            "champion": None,
            "top_scorer": None,
        }
    with open(C.RESULTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_predictions():
    preds = []
    for path in sorted(glob.glob(os.path.join(C.PREDICTIONS_DIR, "*.json"))):
        with open(path, encoding="utf-8") as f:
            preds.append(json.load(f))
    return preds


def score_one(pred, results):
    """Return a points breakdown dict for a single participant."""
    bd = {k: 0 for k in (
        "group_outcome", "group_exact", "group_winner", "group_runner_up",
        "reach_R32", "reach_R16", "reach_QF", "reach_SF", "reach_Final",
        "champion", "top_scorer",
    )}
    detail = {"exact_scores": [], "correct_outcomes": 0}

    # --- group matches ---
    actual_scores = results.get("group_scores", {})
    for mno, res in actual_scores.items():
        pg = pred.get("group_scores", {}).get(mno)
        if not pg:
            continue
        ph, pa = pg
        rh, ra = res
        if _sign(ph, pa) == _sign(rh, ra):
            bd["group_outcome"] += C.POINTS["group_outcome"]
            detail["correct_outcomes"] += 1
            if ph == rh and pa == ra:
                bd["group_exact"] += C.POINTS["group_exact"]
                detail["exact_scores"].append(mno)

    # --- group winners / runners-up ---
    for grp, team in results.get("group_winners", {}).items():
        if team and pred.get("group_winners", {}).get(grp) == team:
            bd["group_winner"] += C.POINTS["group_winner"]
    for grp, team in results.get("group_runners", {}).items():
        if team and pred.get("group_runners", {}).get(grp) == team:
            bd["group_runner_up"] += C.POINTS["group_runner_up"]

    # --- knockout rounds (per correctly predicted team that actually reached) ---
    for rnd in C.KO_ROUNDS:
        actual = set(results.get("bracket", {}).get(rnd, []) or [])
        if not actual:
            continue
        predicted = set(pred.get("bracket", {}).get(rnd, []) or [])
        hits = len(predicted & actual)
        bd[C.KO_POINTS_KEY[rnd]] += hits * C.POINTS[C.KO_POINTS_KEY[rnd]]

    # --- champion ---
    champ = results.get("champion")
    if champ and pred.get("champion") == champ:
        bd["champion"] += C.POINTS["champion"]

    # --- top scorer (case-insensitive) ---
    ts = results.get("top_scorer")
    if ts and pred.get("top_scorer") and _scorer_match(pred["top_scorer"], ts):
        bd["top_scorer"] += C.POINTS["top_scorer"]

    total = sum(bd.values())
    return {
        "participant": pred["participant"],
        "total": total,
        "breakdown": bd,
        "detail": detail,
    }


def build_standings(preds=None, results=None):
    preds = preds if preds is not None else load_predictions()
    results = results if results is not None else load_results()

    scored = [score_one(p, results) for p in preds]
    # Sort by total desc, then exact-score count desc, then name.
    scored.sort(key=lambda s: (-s["total"], -len(s["detail"]["exact_scores"]),
                               s["participant"].lower()))

    # Dense-ish ranking with shared ranks for ties on total.
    rank = 0
    prev_total = None
    for i, s in enumerate(scored):
        if s["total"] != prev_total:
            rank = i + 1
            prev_total = s["total"]
        s["rank"] = rank

    return {
        "last_updated": results.get("last_updated"),
        "max_possible": C.MAX_POSSIBLE,
        "points_decided": _points_decided(results),
        "standings": scored,
    }


def _points_decided(results):
    """How many points are even possible to have earned so far."""
    p = 0
    p += len(results.get("group_scores", {})) * (C.POINTS["group_outcome"] + C.POINTS["group_exact"])
    p += len(results.get("group_winners", {})) * C.POINTS["group_winner"]
    p += len(results.get("group_runners", {})) * C.POINTS["group_runner_up"]
    for rnd in C.KO_ROUNDS:
        n = len(results.get("bracket", {}).get(rnd, []) or [])
        p += n * C.POINTS[C.KO_POINTS_KEY[rnd]]
    if results.get("champion"):
        p += C.POINTS["champion"]
    if results.get("top_scorer"):
        p += C.POINTS["top_scorer"]
    return p


def main():
    standings = build_standings()
    out = os.path.join(C.DATA_DIR, "standings.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(standings, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out}")
    print(f"  {len(standings['standings'])} participants, "
          f"{standings['points_decided']}/{standings['max_possible']} points decided")
    for s in standings["standings"][:10]:
        print(f"   #{s['rank']:<2} {s['participant']:<20} {s['total']}")


if __name__ == "__main__":
    main()
