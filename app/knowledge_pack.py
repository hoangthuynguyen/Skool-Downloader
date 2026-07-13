#!/usr/bin/env python3
"""
Knowledge pack — zip text/knowledge de gui sep / USB (Sprint A).

  python knowledge_pack.py --course "X"
  python knowledge_pack.py --course "X" --out D:/pack.zip
  python knowledge_pack.py --all

Mac dinh: description, transcript, srt, md tong hop, audit, resources (nho),
KHONG gom video.
"""
from __future__ import annotations

import argparse, json, sys, time, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import progress as P

# ten file / pattern knowledge
INCLUDE_NAMES = {
    "description.md", "video.txt", "video.srt",
    "_TongHop.md", "_TongHop.vi.md", "_TomTat.md",
    "Transcript_VI.md", "PhuDe_SongNgu.srt",
    "_chapters.json", "video_audit.txt", "video_fails.json",
    "_health.json", "_update_diff.json",
}
INCLUDE_SUFFIXES = {".md", ".txt", ".srt", ".json"}
SKIP_PARTS = {".rag", "__pycache__", ".git", "_site"}
SKIP_VIDEO = {".mp4", ".webm", ".mkv", ".mov", ".part", ".ytdl"}
MAX_RESOURCE_BYTES = 25 * 1024 * 1024  # 25MB / file resources


def should_pack(path: Path, root: Path) -> bool:
    path = Path(path)
    root = Path(root)
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    parts_l = {p.lower() for p in rel.parts}
    if parts_l & {s.lower() for s in SKIP_PARTS}:
        return False
    if path.suffix.lower() in SKIP_VIDEO:
        return False
    if path.name in INCLUDE_NAMES:
        return True
    if path.suffix.lower() in INCLUDE_SUFFIXES and path.name.startswith("_"):
        return True
    # resources/*
    if "resources" in parts_l and path.is_file():
        try:
            if path.stat().st_size <= MAX_RESOURCE_BYTES:
                return True
        except OSError:
            return False
    # lesson text
    if path.name in ("description.md", "video.txt", "video.srt"):
        return True
    if path.suffix.lower() in {".md", ".txt", ".srt"} and path.is_file():
        # bo log lon
        if path.stat().st_size > MAX_RESOURCE_BYTES:
            return False
        return True
    return False


def iter_pack_files(root: Path):
    root = Path(root)
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file() and should_pack(p, root):
            yield p


def build_manifest(root, files, course_name=None):
    n = len(files)
    size = sum(f.stat().st_size for f in files)
    try:
        scan = __import__("progress", fromlist=["scan"]).scan(root)
        progress = {
            "done": scan.get("done"), "total": scan.get("total"),
            "size_video": scan.get("size"),
        }
    except Exception:
        progress = {}
    return {
        "course": course_name or root.name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "files": n,
        "bytes": size,
        "progress": progress,
        "note": "Knowledge pack — text/resources only, no video.",
    }


def pack_course(root, course_name=None, out_path=None, log=print):
    """Tao zip knowledge. Tra ve Path zip."""
    root = Path(root)
    course_name = course_name or root.name
    files = list(iter_pack_files(root))
    if out_path is None:
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in course_name).strip() or "course"
        out_dir = C.BASE / "courses"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{safe}_KnowledgePack.zip"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(root, files, course_name=course_name)
    log(f">> Knowledge pack: {len(files)} file → {out_path}")

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("_pack_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        readme = (
            f"# Knowledge Pack — {course_name}\n\n"
            f"- Files: {manifest['files']}\n"
            f"- Created: {manifest['created_at']}\n"
            f"- Progress: {manifest.get('progress')}\n\n"
            "No video included. Open `_TongHop.md` / `_TomTat.md` for overview.\n"
        )
        zf.writestr("README.md", readme)
        for f in files:
            try:
                rel = f.relative_to(root)
            except ValueError:
                continue
            arc = str(Path(course_name) / rel).replace("\\", "/")
            try:
                zf.write(f, arcname=arc)
            except Exception as e:
                log(f"  [skip] {rel}: {e}")
    log(f">> Xong: {out_path} ({out_path.stat().st_size} bytes)")
    return out_path


def pack_all(log=print):
    outs = []
    for meta in P.list_course_items():
        name = meta.get("course") or meta.get("item") or "course"
        log(f"\n==== {name} ====")
        try:
            outs.append(pack_course(meta["root"], course_name=name, log=log))
        except Exception as e:
            log(f"[FAIL] {e}")
    return outs


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Export knowledge pack zip")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--out", help="Duong dan .zip")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        pack_all()
        return
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    pack_course(C.ROOT, course_name=C.COURSE or C.ROOT.name, out_path=a.out)


if __name__ == "__main__":
    main()
