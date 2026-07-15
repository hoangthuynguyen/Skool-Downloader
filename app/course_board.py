#!/usr/bin/env python3
"""
Curriculum board — chỉnh sửa cấu trúc khóa mới (JSON) bằng CLI đơn giản.

  python course_board.py --course X --show
  python course_board.py --course X --add-chapter "AI Agents 2026"
  python course_board.py --course X --add-lesson 1 "Build MCP tool" --purpose "..."
  python course_board.py --course X --remove-lesson 1 2
  python course_board.py --course X --move-lesson 1 3 --to-chapter 2 --to-index 1
  python course_board.py --course X --export-md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import config as C
import course_upgrade as CU


def load(root: Path) -> dict:
    p = Path(root) / CU.STRUCTURE_JSON
    if not p.exists():
        raise FileNotFoundError(f"Chưa có {CU.STRUCTURE_JSON}")
    return json.loads(p.read_text(encoding="utf-8"))


def save(root: Path, data: dict):
    p = Path(root) / CU.STRUCTURE_JSON
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # refresh md
    md = CU._structure_to_md(data)
    (Path(root) / CU.STRUCTURE_MD).write_text(md, encoding="utf-8")
    print(f"Saved → {p.name} + {CU.STRUCTURE_MD}")


def show(data: dict):
    print(f"Course: {data.get('course_title')} · as_of {data.get('as_of')}")
    for ch in data.get("chapters") or []:
        print(f"\n[{ch.get('number')}] {ch.get('title')}")
        for les in ch.get("lessons") or []:
            print(
                f"   {ch.get('number')}.{les.get('number')}  {les.get('title')}  "
                f"({les.get('source') or 'new'})"
            )


def add_chapter(data: dict, title: str, goal: str = "") -> dict:
    chs = data.setdefault("chapters", [])
    n = max([int(c.get("number") or 0) for c in chs] + [0]) + 1
    chs.append({"number": n, "title": title, "goal": goal, "lessons": []})
    return data


def add_lesson(data: dict, chapter_num: int, title: str, purpose: str = "") -> dict:
    for ch in data.get("chapters") or []:
        if int(ch.get("number") or 0) == int(chapter_num):
            lessons = ch.setdefault("lessons", [])
            n = max([int(l.get("number") or 0) for l in lessons] + [0]) + 1
            lessons.append(
                {
                    "number": n,
                    "title": title,
                    "purpose": purpose or f"Learn {title}",
                    "must_cover": [],
                    "software": [],
                    "source": "new",
                    "est_minutes": 12,
                }
            )
            return data
    raise ValueError(f"Không thấy chapter {chapter_num}")


def remove_lesson(data: dict, chapter_num: int, lesson_num: int) -> dict:
    for ch in data.get("chapters") or []:
        if int(ch.get("number") or 0) == int(chapter_num):
            before = ch.get("lessons") or []
            ch["lessons"] = [
                l for l in before if int(l.get("number") or 0) != int(lesson_num)
            ]
            # renumber
            for i, l in enumerate(ch["lessons"], 1):
                l["number"] = i
            return data
    raise ValueError("Chapter not found")


def move_lesson(
    data: dict, chapter_num: int, lesson_num: int, to_chapter: int, to_index: int
) -> dict:
    moved = None
    for ch in data.get("chapters") or []:
        if int(ch.get("number") or 0) == int(chapter_num):
            keep = []
            for l in ch.get("lessons") or []:
                if int(l.get("number") or 0) == int(lesson_num):
                    moved = l
                else:
                    keep.append(l)
            ch["lessons"] = keep
            for i, l in enumerate(ch["lessons"], 1):
                l["number"] = i
            break
    if not moved:
        raise ValueError("Lesson not found")
    for ch in data.get("chapters") or []:
        if int(ch.get("number") or 0) == int(to_chapter):
            lessons = ch.setdefault("lessons", [])
            idx = max(0, min(len(lessons), int(to_index) - 1))
            lessons.insert(idx, moved)
            for i, l in enumerate(lessons, 1):
                l["number"] = i
            return data
    raise ValueError("Target chapter not found")


def export_html_board(root: Path, data: dict) -> Path:
    """Interactive board with drag-and-drop reorder (lessons + chapters)."""
    import html as H
    import json as J

    root = Path(root)
    payload = J.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    chapters_html = []
    for ch in data.get("chapters") or []:
        les_html = []
        for les in ch.get("lessons") or []:
            les_html.append(
                f'<li class="lesson" draggable="true">'
                f'<span class="handle" title="Drag">⠿</span>'
                f'<div class="fields">'
                f'<input class="ltitle" value="{H.escape(str(les.get("title") or ""))}"/>'
                f'<input class="lpurpose" placeholder="purpose" value="{H.escape(str(les.get("purpose") or ""))}"/>'
                f"</div>"
                f'<button type="button" class="delL secondary" title="Remove">×</button>'
                f"</li>"
            )
        chapters_html.append(
            f'<section class="chapter" draggable="true">'
            f'<div class="ch-head"><span class="handle" title="Drag chapter">⠿</span>'
            f'<div class="ch-meta">'
            f'<h2 contenteditable="true" class="ctitle">{H.escape(str(ch.get("title") or ""))}</h2>'
            f'<p contenteditable="true" class="cgoal muted">{H.escape(str(ch.get("goal") or ""))}</p>'
            f"</div>"
            f'<button type="button" class="delC secondary" title="Remove chapter">×</button></div>'
            f'<ol class="lessons dropzone">{"".join(les_html)}</ol>'
            f'<button type="button" class="addL">+ Lesson</button>'
            f"</section>"
        )
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Curriculum board — {H.escape(root.name)}</title>
<style>
:root{{--bg:#0f172a;--card:#1e293b;--fg:#f8fafc;--acc:#38bdf8;--muted:#94a3b8;--drop:#164e63}}
body{{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);padding:1rem}}
.toolbar{{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin-bottom:1rem;position:sticky;top:0;background:#0f172acc;padding:.75rem;backdrop-filter:blur(8px);z-index:5}}
button{{background:var(--acc);color:#0f172a;border:0;border-radius:8px;padding:.5rem .9rem;font-weight:600;cursor:pointer}}
button.secondary{{background:#334155;color:var(--fg)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem;min-height:40vh}}
.chapter{{background:var(--card);border:1px solid #334155;border-radius:12px;padding:.9rem;transition:outline .15s}}
.chapter.drag-over{{outline:2px dashed var(--acc)}}
.ch-head{{display:flex;gap:.5rem;align-items:flex-start}}
.ch-meta{{flex:1;min-width:0}}
.ctitle{{margin:0 0 .3rem;font-size:1.05rem;outline:none}}
.muted{{color:var(--muted);font-size:.85rem;min-height:1.2em}}
.handle{{cursor:grab;color:var(--muted);user-select:none;padding:.2rem .35rem;font-size:1.1rem}}
.lessons{{padding:0;margin:.6rem 0;list-style:none;min-height:48px;border-radius:8px}}
.lessons.drag-over{{background:var(--drop)}}
.lesson{{display:flex;gap:.4rem;align-items:flex-start;margin:.4rem 0;padding:.45rem;background:#0f172a;border-radius:8px;border:1px solid #1e293b}}
.lesson.dragging,.chapter.dragging{{opacity:.45}}
.fields{{flex:1;min-width:0}}
.lesson input{{width:100%;background:transparent;border:0;color:var(--fg);font-size:.9rem;margin:.1rem 0}}
.lpurpose{{color:var(--muted)!important;font-size:.8rem!important}}
.delL,.delC{{padding:.2rem .55rem;font-size:1rem;line-height:1}}
.hint{{color:var(--muted);font-size:.8rem;margin-top:1rem;line-height:1.5}}
code{{font-size:.75rem;background:#1e293b;padding:.1rem .3rem;border-radius:4px}}
.status{{margin-left:auto;color:var(--muted);font-size:.8rem}}
</style></head><body>
<div class="toolbar">
  <button type="button" id="addCh">+ Chapter</button>
  <button type="button" id="dl">Download JSON</button>
  <button type="button" id="copy" class="secondary">Copy JSON</button>
  <span class="status" id="st">Drag ⠿ to reorder lessons / chapters</span>
</div>
<div class="grid" id="board">{''.join(chapters_html)}</div>
<p class="hint">Apply after download:<br>
<code>python course_board.py --course "{H.escape(root.name)}" --import-json ~/Downloads/_upgrade_new_structure.json</code></p>
<script>
let data = {payload};
let dragLesson=null, dragChapter=null;

function collect(){{
  const chapters=[];
  document.querySelectorAll('#board > .chapter').forEach((sec,i)=>{{
    const lessons=[];
    sec.querySelectorAll('.lesson').forEach((li,j)=>{{
      lessons.push({{
        number:j+1,
        title:(li.querySelector('.ltitle')?.value||'').trim(),
        purpose:(li.querySelector('.lpurpose')?.value||'').trim(),
        source:'board', must_cover:[], software:[], est_minutes:12
      }});
    }});
    chapters.push({{
      number:i+1,
      title:(sec.querySelector('.ctitle')?.innerText||'').trim(),
      goal:(sec.querySelector('.cgoal')?.innerText||'').trim(),
      lessons
    }});
  }});
  data.chapters=chapters;
  return data;
}}
function setStatus(t){{ document.getElementById('st').textContent=t; }}

function wireLesson(li){{
  li.draggable=true;
  li.addEventListener('dragstart',e=>{{
    dragLesson=li; dragChapter=null;
    li.classList.add('dragging');
    e.dataTransfer.effectAllowed='move';
    e.stopPropagation();
  }});
  li.addEventListener('dragend',()=>{{
    li.classList.remove('dragging');
    dragLesson=null;
    document.querySelectorAll('.drag-over').forEach(x=>x.classList.remove('drag-over'));
    setStatus('Order updated — Download JSON to save');
  }});
  li.querySelector('.delL')?.addEventListener('click',()=>li.remove());
}}
function wireChapter(sec){{
  sec.draggable=true;
  sec.addEventListener('dragstart',e=>{{
    if(e.target.closest('.lesson')) return;
    dragChapter=sec; dragLesson=null;
    sec.classList.add('dragging');
    e.dataTransfer.effectAllowed='move';
  }});
  sec.addEventListener('dragend',()=>{{
    sec.classList.remove('dragging');
    dragChapter=null;
    document.querySelectorAll('.drag-over').forEach(x=>x.classList.remove('drag-over'));
    setStatus('Chapter order updated — Download JSON to save');
  }});
  const ol=sec.querySelector('.lessons');
  ol.addEventListener('dragover',e=>{{
    if(!dragLesson) return;
    e.preventDefault();
    ol.classList.add('drag-over');
    const after=getDragAfter(ol, e.clientY);
    if(after==null) ol.appendChild(dragLesson);
    else ol.insertBefore(dragLesson, after);
  }});
  ol.addEventListener('dragleave',()=>ol.classList.remove('drag-over'));
  ol.addEventListener('drop',e=>{{ e.preventDefault(); ol.classList.remove('drag-over'); }});
  sec.querySelector('.addL').onclick=()=>addLesson(sec);
  sec.querySelector('.delC')?.addEventListener('click',()=>{{
    if(confirm('Remove chapter?')) sec.remove();
  }});
  sec.querySelectorAll('.lesson').forEach(wireLesson);
}}
function getDragAfter(container, y){{
  const els=[...container.querySelectorAll('.lesson:not(.dragging)')];
  return els.reduce((closest, child)=>{{
    const box=child.getBoundingClientRect();
    const offset=y - box.top - box.height/2;
    if(offset<0 && offset>closest.offset) return {{offset, element:child}};
    return closest;
  }}, {{offset:Number.NEGATIVE_INFINITY}}).element;
}}
const board=document.getElementById('board');
board.addEventListener('dragover',e=>{{
  if(!dragChapter) return;
  e.preventDefault();
  const after=[...board.querySelectorAll('.chapter:not(.dragging)')].reduce((closest, child)=>{{
    const box=child.getBoundingClientRect();
    const offset=e.clientX - box.left - box.width/2;
    if(offset<0 && offset>closest.offset) return {{offset, element:child}};
    return closest;
  }}, {{offset:Number.NEGATIVE_INFINITY}}).element;
  if(after==null) board.appendChild(dragChapter);
  else board.insertBefore(dragChapter, after);
}});
function addLesson(sec){{
  const ol=sec.querySelector('.lessons');
  const li=document.createElement('li');
  li.className='lesson';
  li.innerHTML=`<span class="handle">⠿</span><div class="fields">
    <input class="ltitle" value="New lesson"/>
    <input class="lpurpose" placeholder="purpose" value=""/></div>
    <button type="button" class="delL secondary">×</button>`;
  ol.appendChild(li);
  wireLesson(li);
}}
document.querySelectorAll('.chapter').forEach(wireChapter);
document.getElementById('addCh').onclick=()=>{{
  const sec=document.createElement('section');
  sec.className='chapter';
  sec.innerHTML=`<div class="ch-head"><span class="handle">⠿</span><div class="ch-meta">
    <h2 contenteditable="true" class="ctitle">New chapter</h2>
    <p contenteditable="true" class="cgoal muted">Goal</p></div>
    <button type="button" class="delC secondary">×</button></div>
    <ol class="lessons dropzone"></ol>
    <button type="button" class="addL">+ Lesson</button>`;
  board.appendChild(sec);
  wireChapter(sec);
}};
document.getElementById('dl').onclick=()=>{{
  const d=collect();
  const blob=new Blob([JSON.stringify(d,null,2)],{{type:'application/json'}});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='_upgrade_new_structure.json';
  a.click();
  setStatus('Downloaded — run --import-json');
}};
document.getElementById('copy').onclick=async()=>{{
  const d=collect();
  await navigator.clipboard.writeText(JSON.stringify(d,null,2));
  setStatus('JSON copied to clipboard');
}};
</script>
</body></html>"""
    out = root / "_curriculum_board.html"
    out.write_text(page, encoding="utf-8")
    print(f"Board HTML (DnD) → {out}")
    return out


def import_json(root: Path, path: Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "chapters" not in data:
        raise ValueError("JSON phải có key chapters")
    save(root, data)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Curriculum board (edit structure JSON)")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--add-chapter")
    ap.add_argument("--goal", default="")
    ap.add_argument("--add-lesson", nargs=2, metavar=("CHAPTER_NUM", "TITLE"))
    ap.add_argument("--purpose", default="")
    ap.add_argument("--remove-lesson", nargs=2, metavar=("CHAPTER_NUM", "LESSON_NUM"))
    ap.add_argument("--move-lesson", nargs=2, metavar=("CHAPTER_NUM", "LESSON_NUM"))
    ap.add_argument("--to-chapter", type=int)
    ap.add_argument("--to-index", type=int, default=1)
    ap.add_argument("--export-md", action="store_true")
    ap.add_argument("--html", action="store_true", help="Interactive HTML board")
    ap.add_argument("--import-json", help="Ghi structure từ file JSON (board download)")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.import_json:
        import_json(root, Path(args.import_json))
        return 0

    data = load(root)

    if args.html:
        export_html_board(root, data)
        return 0
    if args.show or not any(
        [
            args.add_chapter,
            args.add_lesson,
            args.remove_lesson,
            args.move_lesson,
            args.export_md,
        ]
    ):
        show(data)
        return 0
    if args.add_chapter:
        add_chapter(data, args.add_chapter, args.goal)
        save(root, data)
        return 0
    if args.add_lesson:
        add_lesson(data, int(args.add_lesson[0]), args.add_lesson[1], args.purpose)
        save(root, data)
        return 0
    if args.remove_lesson:
        remove_lesson(data, int(args.remove_lesson[0]), int(args.remove_lesson[1]))
        save(root, data)
        return 0
    if args.move_lesson:
        if not args.to_chapter:
            print("Cần --to-chapter")
            return 2
        move_lesson(
            data,
            int(args.move_lesson[0]),
            int(args.move_lesson[1]),
            args.to_chapter,
            args.to_index,
        )
        save(root, data)
        return 0
    if args.export_md:
        save(root, data)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
