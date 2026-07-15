#!/usr/bin/env python3
"""
Xuất slide pack từ slide_outline.md (+ lesson title) → HTML deck đơn giản.

  python course_slides.py --course X
  python course_slides.py --course X --limit 3
  python course_slides.py --course X --open
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import config as C

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
OUT = "_slides"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def outline_to_slides(outline: str, title: str) -> List[str]:
    """Parse markdown outline → list of slide HTML bodies."""
    slides = [f"<h1>{html.escape(title)}</h1><p class='sub'>Course OS · {_now()}</p>"]
    text = outline or ""
    # Prefer ## headings as slide breaks
    parts = re.split(r"(?m)^##\s+", text)
    if len(parts) <= 1:
        # bullet groups
        bullets = re.findall(r"(?m)^[\-\*]\s+(.+)$", text)
        if bullets:
            chunk = []
            for b in bullets:
                chunk.append(b)
                if len(chunk) >= 5:
                    lis = "".join(f"<li>{html.escape(x)}</li>" for x in chunk)
                    slides.append(f"<h2>{html.escape(title)}</h2><ul>{lis}</ul>")
                    chunk = []
            if chunk:
                lis = "".join(f"<li>{html.escape(x)}</li>" for x in chunk)
                slides.append(f"<h2>{html.escape(title)}</h2><ul>{lis}</ul>")
        else:
            body = html.escape(text[:2000]).replace("\n", "<br>")
            slides.append(f"<h2>{html.escape(title)}</h2><p>{body}</p>")
        return slides

    for block in parts[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        h = lines[0].strip()
        rest = "\n".join(lines[1:]).strip()
        bullets = re.findall(r"(?m)^[\-\*]\s+(.+)$", rest)
        if bullets:
            lis = "".join(f"<li>{html.escape(x)}</li>" for x in bullets[:12])
            slides.append(f"<h2>{html.escape(h)}</h2><ul>{lis}</ul>")
        else:
            para = html.escape(rest[:1500]).replace("\n", "<br>") if rest else ""
            slides.append(f"<h2>{html.escape(h)}</h2><p>{para}</p>")
    return slides


def deck_html(title: str, slides: List[str], *, rtl: bool = False) -> str:
    bodies = []
    for i, s in enumerate(slides):
        bodies.append(f'<section class="slide" id="s{i}">{s}</section>')
    dir_attr = 'dir="rtl"' if rtl else 'dir="auto"'
    return f"""<!DOCTYPE html>
<html lang="en" {dir_attr}>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>
  :root {{ --bg:#0f172a; --fg:#f8fafc; --acc:#38bdf8; --muted:#94a3b8; }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; height:100%; background:var(--bg); color:var(--fg);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Tahoma, sans-serif; }}
  html[dir=rtl] body {{ font-family: "Segoe UI", Tahoma, "Noto Naskh Arabic", sans-serif; }}
  .deck {{ height:100%; display:flex; flex-direction:column; }}
  .slide {{ display:none; flex:1; padding:6vh 8vw; flex-direction:column;
    justify-content:center; max-width:1100px; margin:0 auto; width:100%; }}
  .slide.active {{ display:flex; }}
  h1 {{ font-size:clamp(2rem,5vw,3.2rem); margin:0 0 .4em; }}
  h2 {{ font-size:clamp(1.6rem,4vw,2.4rem); color:var(--acc); margin:0 0 .6em; }}
  p, li {{ font-size:clamp(1.05rem,2.2vw,1.35rem); line-height:1.45; color:#e2e8f0; }}
  ul {{ padding-inline-start:1.2em; }}
  li {{ margin:.35em 0; }}
  .sub {{ color:var(--muted); font-size:1rem; }}
  .bar {{ display:flex; justify-content:space-between; align-items:center;
    padding:10px 16px; border-top:1px solid #1e293b; color:var(--muted); font-size:13px; }}
  button {{ background:#1e293b; color:var(--fg); border:1px solid #334155; border-radius:8px;
    padding:8px 14px; cursor:pointer; font-size:14px; }}
  button:hover {{ border-color:var(--acc); }}
</style>
</head>
<body>
<div class="deck">
  {''.join(bodies)}
  <div class="bar">
    <span id="pos">1 / {len(slides)}</span>
    <span>
      <button type="button" onclick="go(-1)">← Prev</button>
      <button type="button" onclick="go(1)">Next →</button>
    </span>
  </div>
</div>
<script>
let i=0; const slides=[...document.querySelectorAll('.slide')];
function show(){{ slides.forEach((s,n)=>s.classList.toggle('active',n===i));
  document.getElementById('pos').textContent=(i+1)+' / '+slides.length; }}
function go(d){{ i=Math.max(0,Math.min(slides.length-1,i+d)); show(); }}
document.addEventListener('keydown',e=>{{
  if(e.key==='ArrowRight'||e.key===' ') go(1);
  if(e.key==='ArrowLeft') go(-1);
}});
show();
</script>
</body>
</html>
"""


def find_lessons(root: Path) -> List[Path]:
    dest = Path(root) / UPGRADE
    if not dest.is_dir():
        return []
    # prefer dirs with slide_outline.md, else lesson.md
    with_outline = sorted(
        {
            p.parent
            for p in dest.rglob("slide_outline.md")
            if "locales" not in p.parts
        }
    )
    if with_outline:
        return with_outline
    return sorted(
        {p.parent for p in dest.rglob("lesson.md") if "locales" not in p.parts}
    )


def export_slides(
    root: Path,
    *,
    limit: int = 0,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    lessons = find_lessons(root)
    if limit > 0:
        lessons = lessons[:limit]
    if not lessons:
        raise FileNotFoundError(
            f"Không thấy lesson/slide_outline trong {UPGRADE}/ — chạy --assets trước."
        )
    out_root = root / OUT
    out_root.mkdir(parents=True, exist_ok=True)
    index = [
        f"# Slides pack — {root.name}",
        "",
        f"Generated: {_now()}",
        "",
        "## Decks",
        "",
    ]
    n = 0
    first = None
    for ldir in lessons:
        title = ldir.name.split(" - ", 1)[-1]
        outline = _read(ldir / "slide_outline.md")
        if not outline.strip():
            # fallback: first headings of lesson.md
            lesson = _read(ldir / "lesson.md")
            outline = "\n".join(
                ln for ln in lesson.splitlines() if ln.startswith("#") or ln.startswith("-")
            )[:3000]
        slides = outline_to_slides(outline, title)
        try:
            rel = ldir.relative_to(root / UPGRADE)
        except ValueError:
            rel = Path(ldir.name)
        dest = out_root / rel
        dest.mkdir(parents=True, exist_ok=True)
        html_path = dest / "slides.html"
        # RTL if path under ar/he locales (when exporting from locale trees later)
        rtl = any(x in str(rel).lower() for x in ("/ar/", "/he/", "\\ar\\", "\\he\\"))
        html_path.write_text(deck_html(title, slides, rtl=rtl), encoding="utf-8")
        # also plain md deck
        md_lines = [f"# {title}", ""]
        for i, s in enumerate(slides, 1):
            plain = re.sub(r"<[^>]+>", "", s)
            plain = html.unescape(plain)
            md_lines.append(f"## Slide {i}")
            md_lines.append(plain.strip())
            md_lines.append("")
        (dest / "slides.md").write_text("\n".join(md_lines), encoding="utf-8")
        index.append(f"- [{rel}]({rel.as_posix()}/slides.html) ({len(slides)} slides)")
        n += 1
        if first is None:
            first = html_path
        _log(f"   slides: {rel} · {len(slides)} pages", log)

    (out_root / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    # hub index html
    links = []
    for ldir in lessons:
        try:
            rel = ldir.relative_to(root / UPGRADE)
        except ValueError:
            rel = Path(ldir.name)
        links.append(
            f'<li><a href="{html.escape(rel.as_posix())}/slides.html">'
            f"{html.escape(str(rel))}</a></li>"
        )
    (out_root / "index.html").write_text(
        f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Slides — {html.escape(root.name)}</title>
<style>body{{font-family:system-ui;background:#0f172a;color:#f8fafc;padding:2rem}}
a{{color:#38bdf8}} li{{margin:.4rem 0}}</style></head>
<body><h1>Slides — {html.escape(root.name)}</h1><ul>{''.join(links)}</ul></body></html>""",
        encoding="utf-8",
    )
    _log(f">> Slides pack: {n} decks → {out_root}", log)
    return {"decks": n, "dir": str(out_root), "first": str(first) if first else ""}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export HTML slide decks from outline")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--open", action="store_true", help="Mở index.html")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)
    res = export_slides(root, limit=args.limit)
    if args.open:
        idx = Path(res["dir"]) / "index.html"
        webbrowser.open(idx.as_uri())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        raise SystemExit(1)
