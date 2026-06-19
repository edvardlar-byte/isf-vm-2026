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
PHOTO_DIR = os.path.join(C.DOCS_DIR, "photos")


def _esc(s):
    return html.escape(str(s)) if s is not None else ""


def _avatar(name):
    """Round profile photo if we have one, else an initials placeholder."""
    slug = C.slugify(name)
    if os.path.exists(os.path.join(PHOTO_DIR, f"{slug}.jpg")):
        return f'<img class="avatar" src="photos/{slug}.jpg" alt="" loading="lazy">'
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    return f'<span class="avatar avatar-ph">{_esc(initials)}</span>'


def _row(s, leader_total, has_result):
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
    rares = det.get("rare_hits", [])
    bar = int(round(100 * s["total"] / leader_total)) if leader_total else 0
    medal = MEDAL.get(s["rank"], "")
    rank_cls = f"rank-{s['rank']}" if s["rank"] <= 3 else ""

    # 🔥 current streak (2+ correct results in a row).
    streak_badge = (f'<span class="streak" title="{cur_streak} riktige resultater på rad nå">'
                    f'🔥{cur_streak}</span>') if cur_streak >= 2 else ""

    # 🏆 awards (shared on ties): most correct results / exact scores / diamonds.
    award_defs = [
        ("award_results", "✅", "Flest riktige resultater!"),
        ("award_scores", "🎯", "Flest riktige scores!"),
        ("award_diamonds", "👑", "Flest diamanter!"),
    ]
    award_badges = "".join(
        f'<span class="award" title="{label}">{emoji}</span>'
        for key, emoji, label in award_defs if det.get(key)
    )

    # 💎 rare-hit collection: one hoverable diamond per exact score almost
    # nobody else got — a running "precognition" side contest.
    diamond_strip = ""
    if rares:
        gems = "".join(
            f'<span class="d" title="{_esc(r["label"])} {r["score"][0]}–{r["score"][1]} '
            f'· {r["hitters"]} traff">💎</span>'
            for r in rares
        )
        diamond_strip = (f'<div class="dstrip" title="{len(rares)} sjeldne treff">'
                         f'{gems}</div>')

    # Latest guess for the most recent finished match.
    lg = det.get("latest_guess") or {"status": "none", "pred": None}
    sub_html = ""
    if has_result:
        if lg.get("pred"):
            ph, pa = lg["pred"]
            cls = {"exact": "ok", "result": "partial", "wrong": "miss"}.get(lg["status"], "")
            mark = {"exact": "✓", "result": "~", "wrong": "✗"}.get(lg["status"], "")
            sub_html = f'<div class="sub">Siste tipp: <span class="{cls}">{ph}–{pa} {mark}</span></div>'
        else:
            sub_html = '<div class="sub">Siste tipp: <span class="miss">ikke tippet</span></div>'

    # Per-category breakdown chips for the expandable detail.
    chips = []
    for key, emoji, label in award_defs:
        if det.get(key):
            chips.append(f'<span class="chip award-chip">{emoji} {_esc(label)}</span>')
    for key, label in CATEGORY_LABELS:
        if bd[key]:
            chips.append(f'<span class="chip">{_esc(label)}: <b>{bd[key]}</b>&nbsp;p</span>')
    for r in rares:
        chips.append(f'<span class="chip rare-chip">💎 {_esc(r["label"])} '
                     f'{r["score"][0]}–{r["score"][1]} '
                     f'<b>({r["hitters"]} traff)</b></span>')
    if cur_streak >= 2:
        chips.append(f'<span class="chip">Gjeldende streak: <b>{cur_streak}</b> på rad</span>')
    if longest >= 2:
        chips.append(f'<span class="chip">Beste streak: <b>{longest}</b> på rad</span>')
    chips_html = "".join(chips) or '<span class="chip muted">Ingen poeng ennå</span>'

    return f"""
      <tr class="prow {rank_cls}">
        <td class="rank">{medal}<span>{s['rank']}</span></td>
        <td class="name"><div class="nm">{_avatar(s['participant'])}<span class="who">{_esc(s['participant'])}</span>{streak_badge}{award_badges}</div>{sub_html}{diamond_strip}</td>
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
    _lr = standings.get("last_result")
    has_result = bool(_lr and _lr.get("home") and _lr.get("away"))
    body = "".join(_row(s, leader_total, has_result) for s in rows) or \
        '<tr><td colspan="7" class="empty">Ingen deltakerark er lest inn ennå.</td></tr>'

    updated = standings.get("last_updated") or "ikke oppdatert ennå"
    maxp = standings["max_possible"]
    played = standings.get("games_played", 0)
    total_games = standings.get("games_total", 104)
    pct = int(round(100 * played / total_games)) if total_games else 0

    lr = standings.get("last_result")
    if lr and lr.get("home") and lr.get("away"):
        lh, la = lr["score"]
        last_result_html = f'{_esc(lr["home"])} <b>{lh}–{la}</b> {_esc(lr["away"])}'
    else:
        last_result_html = "—"

    return f"""<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#ffffff">
<meta name="robots" content="noindex, nofollow">
<title>ISF VM 2026 — Tippekonkurranse</title>
<style>
  :root {{
    --bg:#ffffff; --card:#f6f7f3; --line:#e4e6df; --txt:#141414; --muted:#6b7280;
    --accent:#2e9e3f; --accent2:#141414; --bar:#8ace00; --brat:#8ace00;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
    font:15px/1.45 Arial, Helvetica, sans-serif; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:24px 16px 64px; }}
  header {{ background:var(--brat); border-radius:16px; padding:16px 22px 18px;
    margin-bottom:18px; }}
  header h1 {{ margin:.12em 0 .12em; font-size:1.75rem; font-weight:700;
    letter-spacing:-.6px; text-transform:lowercase; color:#0c0c0c; }}
  header p {{ margin:0; color:#1f3d05; text-transform:lowercase; }}
  .meta {{ display:flex; flex-wrap:wrap; gap:10px; margin:18px 0 10px; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:10px 14px; flex:1; min-width:150px; }}
  .stat b {{ display:block; font-size:1.3rem; }}
  .stat span {{ color:var(--muted); font-size:.82rem; }}
  .progress {{ height:8px; background:var(--line); border-radius:6px; overflow:hidden; margin-top:8px; }}
  .progress i {{ display:block; height:100%; background:var(--bar); }}
  table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
  thead th {{ text-align:left; font-size:.74rem; text-transform:uppercase; letter-spacing:.6px;
    color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--line); }}
  th.num, th.tick, th.total {{ text-align:right; }}
  .prow td {{ padding:12px 10px; border-bottom:1px solid var(--line); vertical-align:middle; }}
  .rank {{ width:54px; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .rank span {{ margin-left:4px; }}
  .name {{ font-weight:600; }}
  .nm {{ display:flex; align-items:center; flex-wrap:wrap; gap:2px; }}
  .who {{ margin-right:1px; }}
  .avatar {{ width:34px; height:34px; border-radius:50%; object-fit:cover; margin-right:9px;
    border:1.5px solid var(--brat); flex:0 0 auto; background:#e9ece3; }}
  .avatar-ph {{ display:inline-flex; align-items:center; justify-content:center;
    font-size:.72rem; font-weight:700; color:#3d5212; }}
  .sub {{ font-size:.72rem; color:var(--muted); margin-top:3px; font-weight:400; margin-left:43px; }}
  .dstrip {{ margin-left:43px; }}
  .sub .ok {{ color:#1b8a2b; font-weight:700; }}
  .sub .partial {{ color:#b07900; font-weight:700; }}
  .sub .miss {{ color:#c0392b; }}
  .streak {{ margin-left:7px; font-size:.78rem; font-weight:700; color:#7a5d00;
    background:#fff7d6; border:1px solid #e6cf7a; border-radius:20px; padding:1px 7px;
    white-space:nowrap; }}
  .dstrip {{ display:flex; flex-wrap:wrap; gap:1px; margin-top:3px; }}
  .dstrip .d {{ font-size:.82rem; cursor:default; line-height:1; }}
  .dstrip .d:hover {{ filter:brightness(1.15); }}
  .rare-chip {{ background:#eef7ff; border-color:#bcdcf2; color:#1666a3; }}
  .rare-chip b {{ color:#141414; }}
  .award {{ margin-left:5px; font-size:.8rem; line-height:1; background:#f3f7e6;
    border:1px solid #c4d98a; border-radius:20px; padding:1px 6px; cursor:default; }}
  .award-chip {{ background:#f3f7e6; border-color:#c4d98a; color:#3d5212; font-weight:600; }}
  .rare-chip b {{ color:#bfeaff; }}
  .num, .total {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .num small {{ display:block; color:var(--muted); font-size:.7rem; }}
  .tick {{ text-align:center; color:var(--accent); font-weight:700; }}
  .total {{ font-size:1.15rem; font-weight:700; min-width:120px; }}
  .bar {{ height:5px; background:var(--line); border-radius:4px; margin-top:5px; }}
  .bar i {{ display:block; height:100%; background:var(--bar); border-radius:4px; }}
  .rank-1 .total {{ color:#3a9d00; }}
  .prow {{ cursor:pointer; }}
  .prow:hover td {{ background:rgba(0,0,0,.035); }}
  tbody.collapsed .detail {{ display:none; }}
  tbody.collapsed .detail.show {{ display:table-row; }}
  .detail td {{ padding:0 10px 12px; border-bottom:1px solid var(--line); }}
  .chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .chip {{ background:#f1f2ee; border:1px solid var(--line); border-radius:20px;
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
    <h1>Tippekonkurranse — Braut Summer 2026</h1>
    <p>Hvem leder kontorets VM-konkurranse?</p>
  </header>

  <div class="meta">
    <div class="stat"><b style="font-size:1.05rem">{last_result_html}</b><span>siste resultat</span></div>
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
    <br>🔥&nbsp;= riktige resultater på rad nå · 💎&nbsp;= traff en eksakt score nesten ingen andre tok ·
    ✅&nbsp;flest riktige resultater · 🎯&nbsp;flest riktige scores · 👑&nbsp;flest diamanter.
    Trykk på en rad for detaljer. {len(rows)}&nbsp;deltakere · oppdateres automatisk hver morgen.
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
