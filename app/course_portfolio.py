#!/usr/bin/env python3
"""
Multi-course portfolio — % complete Course OS cho mọi khóa dưới BASE/courses/.

  python course_portfolio.py
  python course_portfolio.py --html
  python course_portfolio.py --json
"""
from __future__ import annotations

import argparse
import html as H
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import config as C
import course_status as ST


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def list_course_roots(base: Path | None = None) -> List[Path]:
    base = Path(base or C.BASE)
    courses = base / "courses"
    out: List[Path] = []
    if courses.is_dir():
        for d in sorted(courses.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                out.append(d)
    # legacy single course
    sk = base / "SkoolCourse"
    if sk.is_dir() and sk not in out:
        out.append(sk)
    return out


def collect_portfolio(base: Path | None = None) -> dict:
    roots = list_course_roots(base)
    rows = []
    for root in roots:
        try:
            st = ST.collect_status(root)
            rows.append(
                {
                    "course": root.name,
                    "path": str(root),
                    "pct": st["progress"]["pct"],
                    "done": st["progress"]["done"],
                    "total": st["progress"]["total"],
                    "next": st.get("next"),
                    "next_hint": st.get("next_hint"),
                    "locales": (st.get("meta") or {}).get("locales") or [],
                    "assets": (st.get("meta") or {}).get("asset_lessons") or 0,
                    "version": (st.get("meta") or {}).get("version"),
                }
            )
        except Exception as e:
            rows.append(
                {
                    "course": root.name,
                    "path": str(root),
                    "pct": 0,
                    "error": str(e)[:200],
                }
            )
    rows.sort(key=lambda r: (-(r.get("pct") or 0), r.get("course") or ""))
    avg = round(sum(r.get("pct") or 0 for r in rows) / max(1, len(rows)), 1)
    return {
        "at": _now(),
        "base": str(base or C.BASE),
        "courses": len(rows),
        "avg_pct": avg,
        "rows": rows,
    }


def write_reports(data: dict, out_dir: Path | None = None) -> dict:
    out_dir = Path(out_dir or C.BASE)
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / "_course_portfolio.json"
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Course portfolio",
        f"",
        f"- Generated: {data['at']}",
        f"- Base: `{data['base']}`",
        f"- Courses: **{data['courses']}** · avg complete **{data['avg_pct']}%**",
        f"",
        f"| Course | % | Done | Next | Assets | Locales |",
        f"|--------|---|------|------|--------|---------|",
    ]
    for r in data.get("rows") or []:
        locs = ",".join(r.get("locales") or []) or "—"
        lines.append(
            f"| {r.get('course')} | {r.get('pct')}% | "
            f"{r.get('done')}/{r.get('total')} | {r.get('next')} | "
            f"{r.get('assets')} | {locs} |"
        )
    mp = out_dir / "_course_portfolio.md"
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(jp), "md": str(mp)}


def write_html(data: dict, out_path: Path | None = None) -> Path:
    out_path = Path(out_path or (Path(C.BASE) / "_course_portfolio.html"))
    cards = []
    for r in data.get("rows") or []:
        pct = int(r.get("pct") or 0)
        color = "#34d399" if pct >= 80 else ("#38bdf8" if pct >= 40 else "#fbbf24")
        err = r.get("error")
        cards.append(
            f"""
<div class="card">
  <div class="top">
    <h2>{H.escape(str(r.get('course')))}</h2>
    <span class="pct" style="color:{color}">{pct}%</span>
  </div>
  <div class="bar"><div class="fill" style="width:{pct}%;background:{color}"></div></div>
  <p class="meta">Next: <b>{H.escape(str(r.get('next') or '—'))}</b>
    · assets {r.get('assets') or 0}
    · locales {H.escape(','.join(r.get('locales') or []) or '—')}</p>
  <p class="hint">{H.escape(str(r.get('next_hint') or err or ''))}</p>
  <code class="path">{H.escape(str(r.get('path') or ''))}</code>
</div>"""
        )
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Course portfolio</title>
<style>
:root{{--bg:#0f172a;--card:#1e293b;--fg:#f8fafc;--muted:#94a3b8}}
body{{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);padding:1.5rem}}
h1{{margin:0 0 .25rem}} .sub{{color:var(--muted);margin-bottom:1.5rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem}}
.card{{background:var(--card);border:1px solid #334155;border-radius:14px;padding:1rem 1.1rem}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:.5rem}}
h2{{font-size:1.05rem;margin:0}} .pct{{font-weight:700;font-size:1.2rem}}
.bar{{height:8px;background:#0f172a;border-radius:99px;margin:.7rem 0;overflow:hidden}}
.fill{{height:100%;border-radius:99px}}
.meta{{font-size:.9rem;margin:.3rem 0}} .hint{{color:var(--muted);font-size:.8rem}}
.path{{display:block;font-size:10px;color:#64748b;margin-top:.5rem;word-break:break-all}}
</style></head><body>
<h1>Course portfolio</h1>
<p class="sub">{data['courses']} courses · avg <b>{data['avg_pct']}%</b> · {H.escape(data['at'])}</p>
<div class="grid">{''.join(cards) or '<p>No courses found.</p>'}</div>
</body></html>"""
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Multi-course Course OS portfolio")
    ap.add_argument("--base", help="Override BASE")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--md", action="store_true", default=True)
    args = ap.parse_args(argv)

    if args.base:
        C.set_base(args.base)
    data = collect_portfolio()
    paths = write_reports(data)
    if args.html or not args.json:
        hp = write_html(data)
        paths["html"] = str(hp)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Courses: {data['courses']} · avg {data['avg_pct']}%")
        for r in data.get("rows") or []:
            print(f"  {r.get('pct'):3}%  {r.get('course')}  → {r.get('next')}")
        print(f"→ {paths.get('md')}")
        if paths.get("html"):
            print(f"→ {paths['html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
