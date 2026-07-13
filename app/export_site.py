#!/usr/bin/env python3
"""
Xuat knowledge site tinh HTML (Phase 5) — mo bang file:// hoac bat ky static host.

  python export_site.py                     # -> BASE/courses/_site/
  python export_site.py --out D:/site
  python export_site.py --course "X"        # chi 1 khoa
  python export_site.py --open              # mo index trong browser

Khong can server. Tim kiem client-side (JS) tren index nhe.
"""
from __future__ import annotations

import argparse, html, json, re, sys, webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as C
import progress as P
from rag.index import load_catalog, build_catalog


def esc(s):
    return html.escape(str(s or ""), quote=True)


def slug(s):
    s = re.sub(r"[^\w\s-]", "", (s or ""), flags=re.U)
    s = re.sub(r"[-\s]+", "-", s.strip()).strip("-").lower()
    return (s or "item")[:80]


CSS = """
:root{--bg:#f4f4f5;--card:#fff;--text:#18181b;--muted:#71717a;--line:#e4e4e7;--pri:#111114}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--text);line-height:1.55}
header{background:var(--pri);color:#fff;padding:12px 16px;position:sticky;top:0;z-index:10}
header a{color:#e4e4e7;text-decoration:none;margin-right:12px;font-size:14px}
header .brand{font-weight:700;color:#fff;margin-right:16px}
main{max-width:900px;margin:0 auto;padding:16px 14px 48px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:10px 0}
.muted{color:var(--muted);font-size:13px}
a.link{color:var(--pri);font-weight:600;text-decoration:none}
a.link:hover{text-decoration:underline}
.body{white-space:pre-wrap;background:#fafafa;border:1px solid var(--line);border-radius:8px;padding:12px;font-size:14px}
input#q{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:9px;font-size:15px;margin:8px 0}
#hits .card{cursor:pointer}
@media(max-width:600px){main{padding:12px 10px 40px}header{padding:10px 12px}}
"""


def page(title, body, rel_prefix=""):
    home = rel_prefix + "index.html"
    search = rel_prefix + "search.html"
    return f"""<!DOCTYPE html>
<html lang="vi"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="theme-color" content="#111114"/>
<link rel="manifest" href="{rel_prefix}manifest.webmanifest"/>
<title>{esc(title)} · Skool Archive</title>
<style>{CSS}</style>
</head><body>
<header>
  <a class="brand" href="{home}">📦 Skool Archive</a>
  <a href="{home}">Khóa</a>
  <a href="{search}">Tìm</a>
</header>
<main>{body}</main>
</body></html>
"""


def ensure_catalog(root, log=print):
    full = Path(root) / ".rag" / "catalog_full.json"
    if not full.exists():
        try:
            build_catalog(root, log=log)
        except Exception as e:
            log(f"[index] {root}: {e}")
    return load_catalog(root, full=True)


def export_site(out_dir=None, course=None, log=print):
    out = Path(out_dir or (C.BASE / "courses" / "_site"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(exist_ok=True)

    # collect courses
    metas = P.list_course_items()
    if course:
        metas = [m for m in metas if m.get("course") == course or m.get("item") == course
                 or (course.lower() in ("legacy", "skoolcourse") and m.get("is_legacy"))]
    search_index = []
    course_cards = []

    for meta in metas:
        root = Path(meta["root"])
        key = meta.get("course") or "legacy"
        cslug = slug(key if key else "legacy")
        cat = ensure_catalog(root, log=log)
        title = cat.get("course") or meta["item"]
        lessons = cat.get("lessons") or []
        cdir = out / "c" / cslug
        cdir.mkdir(parents=True, exist_ok=True)

        # lessons
        by_ch = {}
        lesson_links = []
        for i, L in enumerate(lessons):
            ch = L.get("chapter") or "Khác"
            by_ch.setdefault(ch, []).append((i, L))
            fname = f"l{i:04d}.html"
            lesson_links.append((i, L, fname))
            body = (
                f'<p><a class="link" href="index.html">← {esc(title)}</a></p>'
                f'<h1>{esc(L.get("title"))}</h1>'
                f'<p class="muted">{esc(L.get("section") or ch)}</p>'
                f'<div class="body">{esc(L.get("text") or "(trống)")}</div>'
            )
            (cdir / fname).write_text(page(L.get("title") or "Bài", body, rel_prefix="../../"), encoding="utf-8")
            search_index.append({
                "course": title,
                "chapter": ch,
                "title": L.get("title"),
                "href": f"c/{cslug}/{fname}",
                "preview": (L.get("preview") or "")[:180],
                "text": " ".join([
                    title, ch, L.get("title") or "", (L.get("text") or "")[:2000]
                ]).lower(),
            })

        # course index
        blocks = [f"<h1>{esc(title)}</h1><p class='muted'>{len(lessons)} bài</p>"]
        for ch, items in by_ch.items():
            lis = "".join(
                f'<li><a class="link" href="l{i:04d}.html">{esc(L.get("title"))}</a></li>'
                for i, L in items
            )
            blocks.append(f'<div class="card"><h2>{esc(ch)}</h2><ul>{lis}</ul></div>')
        if not lessons:
            blocks.append('<div class="card muted">Chưa có transcript/mô tả.</div>')
        (cdir / "index.html").write_text(
            page(title, "".join(blocks), rel_prefix="../../"), encoding="utf-8")

        try:
            scan = P.scan(root)
            badge = P.status_badge(scan).get("label")
            prog = f"{scan.get('done',0)}/{scan.get('total',0)}"
        except Exception:
            badge, prog = "", f"{len(lessons)} text"
        course_cards.append(
            f'<div class="card"><h2><a class="link" href="c/{cslug}/index.html">{esc(title)}</a></h2>'
            f'<p class="muted">{esc(prog)} · {esc(badge)} · {len(lessons)} bài text</p></div>'
        )

    # root index
    (out / "index.html").write_text(page(
        "Kho khóa học",
        "<h1>Kho khóa học (offline)</h1>"
        "<p class='muted'>Site tĩnh — mở file này bằng trình duyệt, không cần server.</p>"
        + "".join(course_cards or ["<div class='card muted'>(Không có khóa)</div>"]),
        rel_prefix="",
    ), encoding="utf-8")

    # search page + data
    (out / "search_index.json").write_text(
        json.dumps(search_index, ensure_ascii=False), encoding="utf-8")
    search_js = r"""
async function boot(){
  const res = await fetch('search_index.json');
  const data = await res.json();
  const q = document.getElementById('q');
  const hits = document.getElementById('hits');
  function run(){
    const t = (q.value||'').trim().toLowerCase();
    hits.innerHTML = '';
    if(!t){ hits.innerHTML = '<p class="muted">Nhập từ khóa…</p>'; return; }
    const terms = t.split(/\s+/).filter(Boolean);
    const scored = [];
    for(const d of data){
      let s = 0;
      for(const w of terms){ if((d.text||'').includes(w)) s += 1; if((d.title||'').toLowerCase().includes(w)) s += 3; }
      if(s>0) scored.push([s,d]);
    }
    scored.sort((a,b)=>b[0]-a[0]);
    hits.innerHTML = scored.slice(0,40).map(([s,d])=>
      `<div class="card" onclick="location.href='${d.href}'"><h3>${d.course} · ${d.chapter} / ${d.title}</h3>
       <p class="muted">score ${s}</p><p>${(d.preview||'').replace(/</g,'&lt;')}</p></div>`
    ).join('') || '<p class="muted">Không thấy.</p>';
  }
  q.addEventListener('input', run);
  run();
}
boot();
"""
    (out / "search.js").write_text(search_js, encoding="utf-8")
    search_body = """
<h1>Tìm kiếm offline</h1>
<input id="q" placeholder="Từ khóa trong transcript / mô tả…" autofocus/>
<div id="hits"></div>
<script src="search.js"></script>
"""
    (out / "search.html").write_text(page("Tìm kiếm", search_body, ""), encoding="utf-8")

    # PWA bits
    (out / "manifest.webmanifest").write_text(json.dumps({
        "name": "Skool Archive",
        "short_name": "Skool",
        "start_url": "index.html",
        "display": "standalone",
        "background_color": "#f4f4f5",
        "theme_color": "#111114",
        "lang": "vi",
    }, indent=2), encoding="utf-8")

    log(f">> Static site: {out} ({len(metas)} khóa, {len(search_index)} bài)")
    return out


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Export static knowledge HTML site")
    ap.add_argument("--out", help="Thu muc output (mac dinh courses/_site)")
    ap.add_argument("--course", help="Chi 1 khoa")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    out = export_site(out_dir=a.out, course=a.course)
    if a.open:
        webbrowser.open(out.joinpath("index.html").as_uri())


if __name__ == "__main__":
    main()
