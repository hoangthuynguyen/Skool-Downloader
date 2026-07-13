#!/usr/bin/env python3
"""
Sprint R — export vault Obsidian / Notion-friendly Markdown.

  python vault_export.py --course "X"                 # Obsidian
  python vault_export.py --course "X" --format notion
  python vault_export.py --course "X" --out D:/vault
  python vault_export.py --all
"""
from __future__ import annotations

import argparse, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import common as K
import progress as P


def _safe(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", name or "untitled").strip().strip(".")
    return s[:120] or "untitled"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _lessons_walk(root: Path):
    """Yield (chapter, title, folder) tu tree progress hoac filesystem."""
    found = False
    try:
        for ch in P.tree(root):
            for L in ch.get("lessons") or []:
                folder = L.get("folder")
                if folder is None:
                    continue
                found = True
                yield (ch.get("title") or ch.get("name") or "?",
                       L.get("title") or Path(folder).name, Path(folder))
    except Exception:
        pass
    if found:
        return
    for d in sorted(p for p in root.rglob("*") if p.is_dir()):
        if (d / "description.md").exists() or (d / "video.txt").exists():
            try:
                rel = d.relative_to(root)
            except ValueError:
                continue
            parts = rel.parts
            chapter = parts[0] if len(parts) > 1 else "Root"
            yield chapter, d.name, d


def export_obsidian(root, course_name=None, out_dir=None, log=print):
    """Cay: Vault/Course/Chapter/Lesson.md + index + MOC."""
    root = Path(root)
    course_name = course_name or root.name
    if out_dir is None:
        out_dir = C.BASE / "courses" / f"{_safe(course_name)}_Obsidian"
    out_dir = Path(out_dir)
    course_dir = out_dir / _safe(course_name)
    course_dir.mkdir(parents=True, exist_ok=True)

    by_chap = {}
    n = 0
    for chapter, title, folder in _lessons_walk(root):
        ch_dir = course_dir / _safe(chapter)
        ch_dir.mkdir(parents=True, exist_ok=True)
        desc = _read(folder / "description.md")
        tr = _read(folder / "video.txt")
        body = [
            f"# {title}",
            "",
            f"tags: [skool, {_safe(course_name)}, {_safe(chapter)}]",
            f"source: `{folder}`",
            f"exported: {time.strftime('%Y-%m-%d')}",
            "",
            f"## Chapter",
            f"[[{_safe(chapter)}]]",
            "",
        ]
        if desc:
            body += ["## Description", "", desc, ""]
        if tr:
            body += ["## Transcript", "", tr, ""]
        if not desc and not tr:
            body += ["_No description/transcript yet._", ""]
        fn = ch_dir / f"{_safe(title)}.md"
        fn.write_text("\n".join(body), encoding="utf-8")
        by_chap.setdefault(chapter, []).append(title)
        n += 1
        # resources note
        res = folder / "resources"
        if res.is_dir() and any(res.iterdir()):
            rlines = [f"# Resources — {title}", ""]
            for f in sorted(res.iterdir()):
                if f.is_file():
                    rlines.append(f"- `{f.name}`")
            (ch_dir / f"{_safe(title)}__resources.md").write_text(
                "\n".join(rlines), encoding="utf-8")

    # chapter MOC
    for chapter, titles in by_chap.items():
        ch_dir = course_dir / _safe(chapter)
        moc = [f"# {chapter}", "", f"Course: [[{_safe(course_name)}]]", ""]
        for t in titles:
            moc.append(f"- [[{_safe(t)}|{t}]]")
        (ch_dir / f"{_safe(chapter)}.md").write_text("\n".join(moc) + "\n", encoding="utf-8")

    # course index
    idx = [
        f"# {course_name}",
        "",
        f"Obsidian vault export · {n} lessons · {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Chapters",
        "",
    ]
    for chapter in sorted(by_chap.keys()):
        idx.append(f"### [[{_safe(chapter)}]]")
        for t in by_chap[chapter]:
            idx.append(f"- [[{_safe(t)}|{t}]]")
        idx.append("")
    (course_dir / f"{_safe(course_name)}.md").write_text("\n".join(idx), encoding="utf-8")
    (out_dir / "README.md").write_text(
        f"# Obsidian vault — {course_name}\n\n"
        f"Open this folder as an Obsidian vault.\n"
        f"Start at `{_safe(course_name)}/{_safe(course_name)}.md`.\n",
        encoding="utf-8",
    )
    log(f">> Obsidian: {n} lessons → {out_dir}")
    return {"path": str(out_dir), "lessons": n, "format": "obsidian"}


def export_notion(root, course_name=None, out_dir=None, log=print):
    """Notion import: 1 folder, flat-ish MD (Import → Markdown & CSV)."""
    root = Path(root)
    course_name = course_name or root.name
    if out_dir is None:
        out_dir = C.BASE / "courses" / f"{_safe(course_name)}_Notion"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    index_lines = [f"# {course_name}", "", f"Exported {time.strftime('%Y-%m-%d')}", ""]
    for chapter, title, folder in _lessons_walk(root):
        desc = _read(folder / "description.md")
        tr = _read(folder / "video.txt")
        fname = f"{_safe(chapter)} — {_safe(title)}.md"
        body = [f"# {title}", "", f"**Chapter:** {chapter}", ""]
        if desc:
            body += ["## Description", "", desc, ""]
        if tr:
            body += ["## Transcript", "", tr, ""]
        (out_dir / fname).write_text("\n".join(body), encoding="utf-8")
        index_lines.append(f"- [{title}]({fname})")
        n += 1
    (out_dir / "00_Index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(
        f"# Notion export — {course_name}\n\n"
        "Notion → Import → Markdown & CSV → chọn thư mục này.\n",
        encoding="utf-8",
    )
    log(f">> Notion MD: {n} lessons → {out_dir}")
    return {"path": str(out_dir), "lessons": n, "format": "notion"}


def export_course(root, course_name=None, fmt="obsidian", out=None, log=print):
    fmt = (fmt or "obsidian").lower()
    if fmt in ("notion", "md", "markdown"):
        return export_notion(root, course_name=course_name, out_dir=out, log=log)
    return export_obsidian(root, course_name=course_name, out_dir=out, log=log)


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Export Obsidian/Notion vault (Sprint R)")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--format", choices=["obsidian", "notion"], default="obsidian")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.all:
        for meta in P.list_course_items():
            name = meta.get("course") or meta.get("item")
            print(f"\n==== {name} ====")
            export_course(meta["root"], course_name=name, fmt=a.format)
        return
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    r = export_course(C.ROOT, course_name=C.COURSE or C.ROOT.name, fmt=a.format, out=a.out)
    print(r)


if __name__ == "__main__":
    main()
