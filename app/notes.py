#!/usr/bin/env python3
"""
Sprint T — ghi chu ca nhan tren bai (notes.md canh lesson).

  python notes.py --course "X" --list
  python notes.py --course "X" --path "01 - C/01 - L" --set "Ghi chu cua toi"
  python notes.py --course "X" --path "..." --get
  python notes.py --course "X" --export
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import common as K

NOTE_NAME = "notes.md"
INDEX_NAME = "_notes_index.json"


def note_path(folder: Path) -> Path:
    return Path(folder) / NOTE_NAME


def read_note(folder) -> str:
    p = note_path(folder)
    try:
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except Exception:
        return ""


def write_note(folder, text: str) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    p = note_path(folder)
    body = (text or "").rstrip() + ("\n" if text else "")
    p.write_text(body, encoding="utf-8")
    return p


def append_note(folder, line: str) -> Path:
    old = read_note(folder).rstrip()
    stamp = time.strftime("%Y-%m-%d %H:%M")
    chunk = f"\n\n<!-- {stamp} -->\n{(line or '').strip()}\n"
    return write_note(folder, (old + chunk).strip() + "\n")


def list_notes(root) -> list:
    """[{rel, path, chars, preview, mtime}]"""
    root = Path(root)
    out = []
    for p in sorted(root.rglob(NOTE_NAME)):
        if not p.is_file():
            continue
        try:
            rel = str(p.parent.relative_to(root)).replace("\\", "/")
            text = p.read_text(encoding="utf-8", errors="replace")
            out.append({
                "rel": rel,
                "path": str(p.parent),
                "file": str(p),
                "chars": len(text),
                "preview": " ".join(text.split())[:120],
                "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)),
            })
        except Exception:
            continue
    return out


def build_index(root) -> dict:
    items = list_notes(root)
    return {
        "course": Path(root).name,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n": len(items),
        "notes": items,
    }


def export_notes_md(root, out_path=None) -> Path:
    root = Path(root)
    idx = build_index(root)
    if out_path is None:
        out_path = root / "_Notes_All.md"
    out_path = Path(out_path)
    lines = [f"# Notes — {idx['course']}", "", f"_{idx['n']} bài có ghi chú · {idx['built_at']}_", ""]
    for n in idx["notes"]:
        lines += [f"## {n['rel']}", "", read_note(n["path"]).strip() or "_(trống)_", "", "---", ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    (root / INDEX_NAME).write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def resolve_lesson(root, path_or_rel: str) -> Path:
    root = Path(root)
    p = Path(path_or_rel)
    if p.is_dir() and p.exists():
        return p
    cand = root / path_or_rel
    if cand.is_dir():
        return cand
    # fuzzy: basename match
    name = p.name
    for d in root.rglob(name):
        if d.is_dir():
            return d
    raise FileNotFoundError(path_or_rel)


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Lesson notes (Sprint T)")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--path", help="Folder bai (abs hoac rel)")
    ap.add_argument("--get", action="store_true")
    ap.add_argument("--set", metavar="TEXT", help="Ghi de notes.md")
    ap.add_argument("--append", metavar="TEXT")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--export", action="store_true")
    a = ap.parse_args()
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    root = C.ROOT
    if a.list or a.export:
        items = list_notes(root)
        if a.export:
            p = export_notes_md(root)
            print(f">> {p} ({len(items)} notes)")
        else:
            print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not a.path:
        ap.error("Can --path (hoac --list / --export)")
    folder = resolve_lesson(root, a.path)
    if a.set is not None:
        p = write_note(folder, a.set)
        print(f">> wrote {p}")
        return
    if a.append:
        p = append_note(folder, a.append)
        print(f">> append {p}")
        return
    print(read_note(folder) or "(trống)")


if __name__ == "__main__":
    main()
