# ISF World Cup 2026 — Prediction Competition

Turns each employee's filled-in Excel prediction sheet into a live, shareable
standings page. Results refresh automatically every morning.

```
participants/        ← drop each person's filled-in .xlsx here
data/
  fixtures.json      ← canonical match list (extracted from the template)
  results.json       ← actual scores / bracket / champion / top scorer
  topscorers.csv     ← each participant's top-scorer pick (no cell for it in the sheet)
  predictions/*.json ← auto-generated, one per participant
  standings.json     ← auto-generated scores
docs/index.html      ← the standings page (this is what GitHub Pages serves)
src/                 ← the code (see below)
run_update.py        ← the morning job: fetch → parse → score → build
```

## How scoring works (from the competition rules)

| Item | Points | Max |
|---|---|---|
| Correct group-match result (W/D/L) | 1 | 72 |
| Correct exact score (added on top) | +2 | 144 |
| Correct group winner | 5 | 60 |
| Correct group runner-up | 7 | 84 |
| Each correct team reaching Round of 32 | 5 | 160 |
| Each correct team reaching Round of 16 | 8 | 128 |
| Each correct team reaching Quarterfinal | 16 | 128 |
| Each correct team reaching Semifinal | 32 | 128 |
| Each correct team reaching Final | 20 | 40 |
| Correct World Champion | 40 | 40 |
| Correct Top Scorer | 20 | 20 |
| **Total possible** | | **1004** |

A perfectly predicted scoreline earns **3** points (1 for the result + 2 for the exact score).

## One-time setup

1. **Install Python deps:** `pip install -r requirements.txt`
2. **Add participant sheets:** put every filled-in `*.xlsx` in `participants/`.
   The filename becomes the displayed name (`anne_tipping.xlsx` → "Anne").
3. **Top-scorer picks:** the template has no top-scorer cell, so list each
   person's pick in `data/topscorers.csv`. (Alternatively, if a participant
   typed a cell labelled "Toppscorer" in their sheet, it's picked up
   automatically.)
4. **Results source — vmfantasy.tv2.no (open, no token):**
   Results come from TV2's public "VM Fantasy" API
   (`https://vm-fantasyapi-production.up.railway.app/livescore/matches`).
   Nothing to configure — no API key, no secret. If the API is ever
   unreachable the pipeline still runs and keeps the last `data/results.json`.

## Running it

```bash
python run_update.py          # parse sheets → fetch results → score → rebuild docs/index.html
```

Run the individual steps if you need to:

```bash
python src/extract_fixtures.py   # only if the fixture list changes
python src/parse_predictions.py  # re-read participant sheets
python src/fetch_results.py      # pull live results
python src/score.py              # recompute standings
python src/build_site.py         # rebuild the HTML
```

Preview the page locally: open `docs/index.html`, or
`python -m http.server 8131 --directory docs` then visit <http://localhost:8131>.

## Publishing & the daily auto-update (GitHub Pages)

1. Create a GitHub repo and push this folder to it.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Done. The workflow in `.github/workflows/update.yml`:
   - runs every morning at **05:30 UTC (07:30 Norwegian summer time)**,
   - also runs whenever you push (e.g. after adding a new sheet) or when you
     click *Run workflow* in the **Actions** tab,
   - fetches results, recomputes, and deploys to your Pages URL
     (`https://<you>.github.io/<repo>/`). Share that link with participants.

**Prefer to run it on this PC instead?** Use `update_local.ps1` with Windows
Task Scheduler (instructions are in that file).

## When the tournament moves on

`data/results.json` is filled progressively. The scorer only awards points for
fields that are filled in, so the page is always correct for "as far as the
tournament has got."

Automated from the TV2 API every morning:
- **Group scores** — for every finished match.
- **Group winners / runners-up** — computed once a group's 6 matches are done
  (ranked by points → goal difference → goals for; head-to-head is not applied,
  so double-check a tied group and override in `results.json` if needed).
- **Round-of-32 qualifiers** — the 24 group qualifiers + 8 best third-placed,
  filled once all 12 groups are complete.
- **Goal leaderboard** (`goal_leaderboard` / `current_goal_leader`) — who's
  leading the golden-boot race so far.

Fill in by hand as the knockout stage plays out (the morning job preserves
whatever you enter):
- **`bracket.R16` / `QF` / `SF` / `Final`** — the teams reaching each round.
  (The TV2 `/livescore/matches` feed currently lists only group matches with no
  round labels; once the knockout fixtures appear there, `_derive_knockout()` in
  `src/fetch_results.py` can be extended to automate this too.)
- **`champion`** — the winner, once the final is played.
- **`top_scorer`** — the golden-boot winner. It's only worth setting at the end;
  use `current_goal_leader` / `goal_leaderboard` as your guide. Partial guesses
  match generously (e.g. "Mbappé" matches "Kylian Mbappé").

## Adapting it

- **Scoring tweaks:** edit the `POINTS` table in `src/config.py`.
- **A team name mismatch between the API and the sheet:** add it to
  `TEAM_ALIASES` in `src/config.py`.
- **A different results provider:** replace `src/fetch_results.py` — it only has
  to write `data/results.json` in the documented shape.
