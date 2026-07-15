#!/usr/bin/env python3
"""
Student portal tĩnh — browse khóa mới + quiz offline + progress localStorage.

  python course_portal.py --course X
  python course_portal.py --course X --open
"""
from __future__ import annotations

import argparse
import html as H
import json
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, List

import config as C

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
OUT = "_student_portal"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _md_lite(text: str) -> str:
    """Very small markdown→HTML (headings, bullets, paragraphs)."""
    out = []
    for ln in (text or "").splitlines():
        if ln.startswith("### "):
            out.append(f"<h4>{H.escape(ln[4:])}</h4>")
        elif ln.startswith("## "):
            out.append(f"<h3>{H.escape(ln[3:])}</h3>")
        elif ln.startswith("# "):
            out.append(f"<h2>{H.escape(ln[2:])}</h2>")
        elif re.match(r"^[\-\*]\s+", ln):
            out.append(f"<li>{H.escape(re.sub(r'^[\-\*]\s+', '', ln))}</li>")
        elif ln.strip():
            out.append(f"<p>{H.escape(ln)}</p>")
    return "\n".join(out)


def build_portal(root: Path, log: LogFn = print) -> dict:
    root = Path(root)
    dest = root / UPGRADE
    if not dest.is_dir():
        raise FileNotFoundError(f"Chưa có {UPGRADE}/ — chạy assets trước")

    lessons = sorted(
        {p.parent for p in dest.rglob("lesson.md") if "locales" not in p.parts}
    )
    out = root / OUT
    if out.exists():
        import shutil

        # keep regenerating clean index; don't wipe media
        pass
    out.mkdir(parents=True, exist_ok=True)
    lessons_dir = out / "lessons"
    lessons_dir.mkdir(exist_ok=True)

    nav = []
    catalog = []
    for i, ldir in enumerate(lessons, 1):
        title = ldir.name.split(" - ", 1)[-1]
        try:
            rel = ldir.relative_to(dest)
        except ValueError:
            rel = Path(ldir.name)
        slug = re.sub(r"[^\w\-]+", "_", str(rel))[:80]
        lesson_body = _read(ldir / "lesson.md")
        summary = _read(ldir / "summary.md")
        workshop = _read(ldir / "workshop.md")
        quiz_raw = _read(ldir / "quiz.json") or "[]"
        try:
            quiz = json.loads(quiz_raw)
            if not isinstance(quiz, list):
                quiz = []
        except Exception:
            quiz = []

        quiz_html = []
        for qi, q in enumerate(quiz[:12]):
            if not isinstance(q, dict):
                continue
            choices = q.get("choices") or q.get("options") or []
            opts = "".join(
                f'<label class="opt"><input type="radio" name="q{qi}" value="{oi}"/> '
                f"{H.escape(str(c))}</label>"
                for oi, c in enumerate(choices)
            )
            ans = q.get("answer", q.get("correct", 0))
            quiz_html.append(
                f'<div class="q" data-ans="{H.escape(str(ans))}">'
                f"<p><b>{qi+1}. {H.escape(str(q.get('q') or q.get('question') or ''))}</b></p>"
                f"{opts}</div>"
            )

        # OmniVoice / other TTS audio if present
        audio_html = ""
        tts_src = ldir / "tts_omnivoice.wav"
        if tts_src.exists():
            audio_dir = out / "audio"
            audio_dir.mkdir(exist_ok=True)
            import shutil

            audio_name = f"{slug}.wav"
            try:
                shutil.copy2(tts_src, audio_dir / audio_name)
            except Exception:
                pass
            audio_html = (
                f'<section class="card audio-card"><h2>🎧 Audio (OmniVoice)</h2>'
                f'<audio controls preload="none" src="../audio/{H.escape(audio_name)}"></audio>'
                f'<p class="muted">tts_omnivoice.wav</p></section>'
            )

        page = f"""<!DOCTYPE html>
<html lang="en" dir="auto"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{H.escape(title)}</title>
<link rel="stylesheet" href="../portal.css"/>
</head><body>
<header class="top">
  <a href="../index.html">← Portal</a>
  <button type="button" id="markDone">Mark complete</button>
</header>
<main>
  <h1>{H.escape(title)}</h1>
  {audio_html}
  <section class="card"><h2>Lesson</h2>{_md_lite(lesson_body)}</section>
  <section class="card"><h2>Summary</h2>{_md_lite(summary)}</section>
  <section class="card"><h2>Workshop</h2>{_md_lite(workshop)}</section>
  <section class="card"><h2>Quiz</h2>
    {''.join(quiz_html) or '<p>No quiz.</p>'}
    <button type="button" id="checkQuiz">Check answers</button>
    <p id="quizResult"></p>
  </section>
</main>
<script>
const KEY='courseos:{H.escape(root.name)}:{H.escape(slug)}';
const progressKey='courseos_progress:{H.escape(root.name)}';
document.getElementById('markDone').onclick=()=>{{
  const p=JSON.parse(localStorage.getItem(progressKey)||'{{}}');
  p[KEY]=true; localStorage.setItem(progressKey, JSON.stringify(p));
  alert('Marked complete (local only)');
}};
document.getElementById('checkQuiz')?.addEventListener('click',()=>{{
  let ok=0,total=0;
  document.querySelectorAll('.q').forEach(q=>{{
    total++;
    const a=q.getAttribute('data-ans');
    const sel=q.querySelector('input:checked');
    if(sel && String(sel.value)===String(a)) ok++;
  }});
  document.getElementById('quizResult').textContent= ok+' / '+total+' correct';
}});
</script>
</body></html>"""
        lp = lessons_dir / f"{slug}.html"
        lp.write_text(page, encoding="utf-8")
        has_audio = (ldir / "tts_omnivoice.wav").exists()
        nav.append((title, f"lessons/{slug}.html", slug, has_audio))
        catalog.append(
            {
                "title": title,
                "href": f"lessons/{slug}.html",
                "id": slug,
                "audio": has_audio,
            }
        )
        _log(f"   portal lesson: {title}" + (" [audio]" if has_audio else ""), log)

    # CSS with RTL-friendly dir=auto
    (out / "portal.css").write_text(
        """
:root{--bg:#0b1220;--card:#111827;--fg:#f8fafc;--acc:#38bdf8;--muted:#94a3b8}
*{box-sizing:border-box}
html[dir=rtl] body{font-family:system-ui,"Segoe UI",Tahoma,sans-serif}
body{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);line-height:1.55}
.top{display:flex;justify-content:space-between;align-items:center;padding:1rem 1.25rem;border-bottom:1px solid #1f2937;position:sticky;top:0;background:#0b1220cc;backdrop-filter:blur(8px)}
.top a{color:var(--acc);text-decoration:none}
main{max-width:860px;margin:0 auto;padding:1.25rem}
.card{background:var(--card);border:1px solid #1f2937;border-radius:14px;padding:1rem 1.2rem;margin:1rem 0}
h1{font-size:1.6rem} h2{color:var(--acc);font-size:1.1rem}
li{margin:.25rem 0} .opt{display:block;margin:.35rem 0;cursor:pointer}
button{background:var(--acc);color:#0f172a;border:0;border-radius:8px;padding:.55rem 1rem;font-weight:600;cursor:pointer}
.lesson-list{list-style:none;padding:0}
.lesson-list li{margin:.5rem 0}
.lesson-list a{color:var(--fg);text-decoration:none;display:block;padding:.75rem 1rem;background:var(--card);border-radius:10px;border:1px solid #1f2937}
.lesson-list a:hover{border-color:var(--acc)}
.done a{border-color:#34d399 !important}
.progress{color:var(--muted);margin:.5rem 0 1rem}
.audio-card audio{width:100%;margin-top:.5rem}
.muted{color:var(--muted);font-size:.85rem}
.audio-badge{color:#34d399;font-size:.8rem;margin-left:.4rem}
""",
        encoding="utf-8",
    )

    item_parts = []
    for title, href, slug, has_audio in nav:
        badge = '<span class="audio-badge">🎧</span>' if has_audio else ""
        item_parts.append(
            f'<li data-id="{H.escape(slug)}">'
            f'<a href="{H.escape(href)}">{H.escape(title)}{badge}</a></li>'
        )
    items = "".join(item_parts)
    n_audio = sum(1 for *_, a in nav if a)
    index = f"""<!DOCTYPE html>
<html lang="en" dir="auto"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{H.escape(root.name)} — Student portal</title>
<link rel="stylesheet" href="portal.css"/>
</head><body>
<header class="top"><strong>{H.escape(root.name)}</strong><span id="prog" class="progress"></span></header>
<main>
  <h1>Student portal</h1>
  <p class="progress">Generated {_now()} · progress in this browser · audio: {n_audio} lessons
  · <a href="audio_playlist.html" style="color:var(--acc)">Open TTS playlist</a></p>
  <ul class="lesson-list" id="list">{items}</ul>
</main>
<script>
const progressKey='courseos_progress:{H.escape(root.name)}';
const p=JSON.parse(localStorage.getItem(progressKey)||'{{}}');
let done=0,total=0;
document.querySelectorAll('#list li').forEach(li=>{{
  total++;
  const id=li.getAttribute('data-id');
  const key='courseos:{H.escape(root.name)}:'+id;
  if(p[key]){{ li.classList.add('done'); done++; }}
}});
document.getElementById('prog').textContent=done+' / '+total+' complete';
</script>
</body></html>"""
    (out / "index.html").write_text(index, encoding="utf-8")
    (out / "catalog.json").write_text(
        json.dumps({"course": root.name, "lessons": catalog, "at": _now()}, indent=2),
        encoding="utf-8",
    )
    # TTS playlist page
    pl_items = []
    for title, href, slug, has_audio in nav:
        if not has_audio:
            continue
        pl_items.append(
            f'<li><strong>{H.escape(title)}</strong><br/>'
            f'<audio controls preload="none" src="audio/{H.escape(slug)}.wav"></audio> '
            f'<a href="{H.escape(href)}">open lesson</a></li>'
        )
    (out / "audio_playlist.html").write_text(
        f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>TTS playlist — {H.escape(root.name)}</title>
<link rel="stylesheet" href="portal.css"/>
</head><body>
<header class="top"><a href="index.html">← Portal</a><strong>🎧 OmniVoice playlist</strong></header>
<main>
  <h1>Audio playlist</h1>
  <p class="progress">{len(pl_items)} tracks · generated {_now()}</p>
  <ul class="lesson-list">{''.join(pl_items) or '<li>No tts_omnivoice.wav yet. Run course_omnivoice.py --all --limit 3</li>'}</ul>
</main></body></html>""",
        encoding="utf-8",
    )
    _log(
        f">> Student portal → {out} ({len(lessons)} lessons, {n_audio} with audio)",
        log,
    )
    return {
        "dir": str(out),
        "lessons": len(lessons),
        "audio": n_audio,
        "index": str(out / "index.html"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Static student portal")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args(argv)
    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    res = build_portal(Path(C.ROOT))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.open:
        webbrowser.open(Path(res["index"]).as_uri())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        raise SystemExit(1)
