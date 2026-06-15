"""
Render the standings into a single self-contained HTML page: docs/index.html.

No external libraries, no network calls — safe to host on GitHub Pages or open
straight from disk. Re-run whenever scores change.

Run:
    python src/build_site.py
"""
from __future__ import annotations

import html
import json
import os

import config as C
import score as scoring

CATEGORY_LABELS = [
    ("group_outcome", "Group result"),
    ("group_exact", "Exact score"),
    ("group_winner", "Group winners"),
    ("group_runner_up", "Runners-up"),
    ("reach_R32", "Round of 32"),
    ("reach_R16", "Round of 16"),
    ("reach_QF", "Quarterfinals"),
    ("reach_SF", "Semifinals"),
    ("reach_Final", "Final"),
    ("champion", "Champion"),
    ("top_scorer", "Top scorer"),
]

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


def _esc(s):
    return html.escape(str(s)) if s is not None else ""


def _row(s, leader_total):
    bd = s["breakdown"]
    group_pts = bd["group_outcome"] + bd["group_exact"]
    ko_pts = sum(bd[f"reach_{r}"] for r in C.KO_ROUNDS)
    champ = bd["champion"] > 0
    tops = bd["top_scorer"] > 0
    exacts = len(s["detail"]["exact_scores"])
    bar = int(round(100 * s["total"] / leader_total)) if leader_total else 0
    medal = MEDAL.get(s["rank"], "")
    rank_cls = f"rank-{s['rank']}" if s["rank"] <= 3 else ""

    # Per-category breakdown chips for the expandable detail.
    chips = []
    for key, label in CATEGORY_LABELS:
        if bd[key]:
            chips.append(f'<span class="chip">{_esc(label)}: <b>{bd[key]}</b></span>')
    chips_html = "".join(chips) or '<span class="chip muted">No points yet</span>'

    return f"""
      <tr class="prow {rank_cls}">
        <td class="rank">{medal}<span>{s['rank']}</span></td>
        <td class="name">{_esc(s['participant'])}</td>
        <td class="num">{group_pts}<small>{exacts}&nbsp;exact</small></td>
        <td class="num">{ko_pts}</td>
        <td class="tick">{'✓' if champ else '–'}</td>
        <td class="tick">{'✓' if tops else '–'}</td>
        <td class="total">{s['total']}
          <div class="bar"><i style="width:{bar}%"></i></div>
        </td>
      </tr>
      <tr class="detail"><td colspan="7"><div class="chips">{chips_html}</div></td></tr>
    """


def render(standings):
    rows = standings["standings"]
    leader_total = rows[0]["total"] if rows else 0
    body = "".join(_row(s, leader_total) for s in rows) or \
        '<tr><td colspan="7" class="empty">No participant sheets parsed yet.</td></tr>'

    updated = standings.get("last_updated") or "not yet updated"
    decided = standings["points_decided"]
    maxp = standings["max_possible"]
    pct = int(round(100 * decided / maxp)) if maxp else 0

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ISF World Cup 2026 — Prediction Standings</title>
<style>
  :root {{
    --bg:#0e1116; --card:#171c24; --line:#262d38; --txt:#e6eaf0; --muted:#8b94a3;
    --accent:#36c98b; --accent2:#f5c451; --bar:#36c98b;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
    font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:24px 16px 64px; }}
  header h1 {{ margin:.2em 0 .1em; font-size:1.7rem; letter-spacing:.2px; }}
  header p {{ margin:0; color:var(--muted); }}
  .meta {{ display:flex; flex-wrap:wrap; gap:10px; margin:18px 0 10px; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:10px 14px; flex:1; min-width:150px; }}
  .stat b {{ display:block; font-size:1.3rem; }}
  .stat span {{ color:var(--muted); font-size:.82rem; }}
  .progress {{ height:8px; background:var(--line); border-radius:6px; overflow:hidden; margin-top:8px; }}
  .progress i {{ display:block; height:100%; background:var(--accent2); }}
  table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
  thead th {{ text-align:left; font-size:.74rem; text-transform:uppercase; letter-spacing:.6px;
    color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--line); }}
  th.num, th.tick, th.total {{ text-align:right; }}
  .prow td {{ padding:12px 10px; border-bottom:1px solid var(--line); vertical-align:middle; }}
  .rank {{ width:54px; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .rank span {{ margin-left:4px; }}
  .name {{ font-weight:600; }}
  .num, .total {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .num small {{ display:block; color:var(--muted); font-size:.7rem; }}
  .tick {{ text-align:center; color:var(--accent); font-weight:700; }}
  .total {{ font-size:1.15rem; font-weight:700; min-width:120px; }}
  .bar {{ height:5px; background:var(--line); border-radius:4px; margin-top:5px; }}
  .bar i {{ display:block; height:100%; background:var(--bar); border-radius:4px; }}
  .rank-1 .total {{ color:var(--accent2); }}
  .prow {{ cursor:pointer; }}
  .prow:hover td {{ background:#1b212b; }}
  tbody.collapsed .detail {{ display:none; }}
  tbody.collapsed .detail.show {{ display:table-row; }}
  .detail td {{ padding:0 10px 12px; border-bottom:1px solid var(--line); }}
  .chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .chip {{ background:#10151c; border:1px solid var(--line); border-radius:20px;
    padding:3px 10px; font-size:.78rem; color:var(--muted); }}
  .chip b {{ color:var(--txt); }}
  .chip.muted {{ font-style:italic; }}
  .empty {{ text-align:center; color:var(--muted); padding:30px; }}
  footer {{ margin-top:28px; color:var(--muted); font-size:.8rem; }}
  @media (max-width:560px) {{
    th.num, td.num, th.tick, td.tick {{ display:none; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p>ISF · Verdensmesterskapet i fotball 2026</p>
    <h1>⚽ Prediction Standings</h1>
    <p>Who's leading the office World Cup competition</p>
  </header>

  <div class="meta">
    <div class="stat"><b>{len(rows)}</b><span>participants</span></div>
    <div class="stat"><b>{decided}<span style="font-size:.9rem"> / {maxp}</span></b>
      <span>points decided so far</span>
      <div class="progress"><i style="width:{pct}%"></i></div>
    </div>
    <div class="stat"><b style="font-size:.95rem">{_esc(updated)}</b><span>last updated</span></div>
  </div>

  <table>
    <thead>
      <tr>
        <th class="rank">#</th><th>Participant</th>
        <th class="num">Group</th><th class="num">Knockout</th>
        <th class="tick">Champ</th><th class="tick">Scorer</th>
        <th class="total">Total</th>
      </tr>
    </thead>
    <tbody id="tb">{body}</tbody>
  </table>

  <script>
    // Progressive enhancement: collapse detail rows, expand on click.
    var tb = document.getElementById('tb');
    tb.classList.add('collapsed');
    tb.addEventListener('click', function (e) {{
      var row = e.target.closest('tr.prow');
      if (!row) return;
      var d = row.nextElementSibling;
      if (d && d.classList.contains('detail')) d.classList.toggle('show');
    }});
  </script>

  <footer>
    Scoring: 1&nbsp;pt correct group result · +2&nbsp;exact score · 5&nbsp;group winner ·
    7&nbsp;runner-up · 5/8/16/32/20&nbsp;per team reaching R32/R16/QF/SF/Final ·
    40&nbsp;champion · 20&nbsp;top scorer · max&nbsp;1004.
    <br>Rows expand to show each category. Updated automatically every morning.
  </footer>
</div>
</body>
</html>
"""


def main():
    standings = scoring.build_standings()
    os.makedirs(C.DOCS_DIR, exist_ok=True)
    out = os.path.join(C.DOCS_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(standings))
    # also drop the raw json next to it for transparency / debugging
    with open(os.path.join(C.DOCS_DIR, "standings.json"), "w", encoding="utf-8") as f:
        json.dump(standings, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
