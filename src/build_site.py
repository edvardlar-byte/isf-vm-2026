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
    ("group_outcome", "Riktig resultat"),
    ("group_exact", "Riktig score"),
    ("group_winner", "Gruppevinner"),
    ("group_runner_up", "Annenplass i gruppe"),
    ("reach_R32", "16-delsfinale"),
    ("reach_R16", "Åttendelsfinale"),
    ("reach_QF", "Kvartfinale"),
    ("reach_SF", "Semifinale"),
    ("reach_Final", "Finale"),
    ("champion", "Verdensmester"),
    ("top_scorer", "Toppscorer"),
]

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


def _esc(s):
    return html.escape(str(s)) if s is not None else ""


def _row(s, leader_total):
    bd = s["breakdown"]
    det = s["detail"]
    group_pts = bd["group_outcome"] + bd["group_exact"]
    ko_pts = sum(bd[f"reach_{r}"] for r in C.KO_ROUNDS)
    champ = bd["champion"] > 0
    tops = bd["top_scorer"] > 0
    n_res = det.get("correct_outcomes", 0)         # correct W/D/L (incl. exact)
    n_exact = len(det.get("exact_scores", []))     # exact scorelines
    cur_streak = det.get("current_streak", 0)
    longest = det.get("longest_streak", 0)
    bar = int(round(100 * s["total"] / leader_total)) if leader_total else 0
    medal = MEDAL.get(s["rank"], "")
    rank_cls = f"rank-{s['rank']}" if s["rank"] <= 3 else ""

    # 🔥 streak badge next to the name = best run of correct results (3+).
    streak_badge = (f'<span class="streak" title="Beste streak: {longest} riktige resultater på rad">'
                    f'🔥{longest}</span>') if longest >= 3 else ""

    # Per-category breakdown chips for the expandable detail.
    chips = []
    for key, label in CATEGORY_LABELS:
        if bd[key]:
            chips.append(f'<span class="chip">{_esc(label)}: <b>{bd[key]}</b>&nbsp;p</span>')
    if longest >= 2:
        chips.append(f'<span class="chip">Beste streak: <b>{longest}</b> på rad</span>')
    if cur_streak >= 2:
        chips.append(f'<span class="chip">Gjeldende streak: <b>{cur_streak}</b> på rad</span>')
    chips_html = "".join(chips) or '<span class="chip muted">Ingen poeng ennå</span>'

    return f"""
      <tr class="prow {rank_cls}">
        <td class="rank">{medal}<span>{s['rank']}</span></td>
        <td class="name">{_esc(s['participant'])}{streak_badge}</td>
        <td class="num">{group_pts}
          <small>{n_res}&nbsp;riktig resultat</small>
          <small>{n_exact}&nbsp;riktig score</small>
        </td>
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
        '<tr><td colspan="7" class="empty">Ingen deltakerark er lest inn ennå.</td></tr>'

    updated = standings.get("last_updated") or "ikke oppdatert ennå"
    maxp = standings["max_possible"]
    played = standings.get("games_played", 0)
    total_games = standings.get("games_total", 104)
    pct = int(round(100 * played / total_games)) if total_games else 0

    return f"""<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ISF VM 2026 — Tippekonkurranse</title>
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
  .streak {{ margin-left:7px; font-size:.78rem; font-weight:700; color:var(--accent2);
    background:#2a210e; border:1px solid #4a3a12; border-radius:20px; padding:1px 7px;
    white-space:nowrap; }}
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
    <h1>⚽ Tippekonkurranse</h1>
    <p>Hvem leder kontorets VM-konkurranse?</p>
  </header>

  <div class="meta">
    <div class="stat"><b>{len(rows)}</b><span>deltakere</span></div>
    <div class="stat"><b>{played}<span style="font-size:.9rem"> / {total_games}</span></b>
      <span>kamper spilt</span>
      <div class="progress"><i style="width:{pct}%"></i></div>
    </div>
    <div class="stat"><b style="font-size:.95rem">{_esc(updated)}</b><span>sist oppdatert</span></div>
  </div>

  <table>
    <thead>
      <tr>
        <th class="rank">#</th><th>Deltaker</th>
        <th class="num">Gruppe</th><th class="num">Sluttspill</th>
        <th class="tick">Mester</th><th class="tick">Toppsc.</th>
        <th class="total">Totalt</th>
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
    Poeng: 1&nbsp;riktig resultat · +2&nbsp;riktig score · 5&nbsp;gruppevinner ·
    7&nbsp;annenplass · 5/8/16/32/20&nbsp;per lag til 16-/åttende-/kvart-/semi-/finale ·
    40&nbsp;verdensmester · 20&nbsp;toppscorer · maks&nbsp;1004.
    <br>🔥&nbsp;= beste streak med riktige resultater på rad. Trykk på en rad for detaljer.
    Oppdateres automatisk hver morgen.
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
