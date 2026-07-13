#!/usr/bin/env python3
"""
Sprint U — bao cao dung luong kho + bai lon nhat.

  python disk_report.py
  python disk_report.py --course "X"
  python disk_report.py --write
  python disk_report.py --top 20
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import common as K
import progress as P

VIDEXT = {".mp4", ".webm", ".mkv", ".mov"}


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _fmt(n: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


def scan_course(root, course_name=None, top=15):
    root = Path(root)
    course_name = course_name or root.name
    videos = []
    other = 0
    n_vid = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            sz = p.stat().st_size
        except OSError:
            continue
        if p.suffix.lower() in VIDEXT and p.stem == "video":
            n_vid += 1
            try:
                rel = str(p.parent.relative_to(root)).replace("\\", "/")
            except ValueError:
                rel = str(p.parent)
            videos.append({"rel": rel, "path": str(p), "size": sz, "name": p.parent.name})
        else:
            other += sz
    videos.sort(key=lambda x: -x["size"])
    vsum = sum(v["size"] for v in videos)
    return {
        "course": course_name,
        "root": str(root),
        "video_bytes": vsum,
        "other_bytes": other,
        "total_bytes": vsum + other,
        "n_videos": n_vid,
        "top_lessons": videos[:top],
    }


def scan_warehouse(base=None, top=15):
    base = Path(base or C.BASE)
    courses = []
    for meta in P.list_course_items(base):
        try:
            rec = scan_course(meta["root"], course_name=meta.get("course") or meta.get("item"), top=top)
            rec["item"] = meta.get("item")
            courses.append(rec)
        except Exception as e:
            courses.append({"item": meta.get("item"), "error": str(e), "total_bytes": 0})
    courses.sort(key=lambda x: -(x.get("total_bytes") or 0))
    total = sum(c.get("total_bytes") or 0 for c in courses)
    # top lessons across warehouse
    all_lessons = []
    for c in courses:
        for L in c.get("top_lessons") or []:
            all_lessons.append({**L, "course": c.get("course") or c.get("item")})
    all_lessons.sort(key=lambda x: -x["size"])
    return {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base": str(base),
        "n_courses": len(courses),
        "total_bytes": total,
        "total_human": _fmt(total),
        "courses": courses,
        "top_lessons": all_lessons[:top],
    }


def write_report(rep, base=None):
    base = Path(base or C.BASE)
    out_dir = base / "courses"
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / "_Disk_Report.json"
    jp.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Disk report — {rep.get('checked_at')}",
        "",
        f"- Khóa: **{rep.get('n_courses')}**",
        f"- Tổng: **{rep.get('total_human')}** ({rep.get('total_bytes')} bytes)",
        "",
        "## Theo khóa",
        "",
        "| Khóa | Video | Khác | Tổng | #vid |",
        "|------|-------|------|------|------|",
    ]
    for c in rep.get("courses") or []:
        if c.get("error"):
            lines.append(f"| {c.get('item')} | ERR | - | - | - |")
            continue
        lines.append(
            f"| {c.get('item') or c.get('course')} | {_fmt(c.get('video_bytes') or 0)} | "
            f"{_fmt(c.get('other_bytes') or 0)} | {_fmt(c.get('total_bytes') or 0)} | "
            f"{c.get('n_videos') or 0} |"
        )
    lines += ["", "## Bài lớn nhất", ""]
    for i, L in enumerate(rep.get("top_lessons") or [], 1):
        lines.append(f"{i}. **{_fmt(L['size'])}** — [{L.get('course')}] {L.get('rel') or L.get('name')}")
    lines.append("")
    mp = out_dir / "_Disk_Report.md"
    mp.write_text("\n".join(lines), encoding="utf-8")
    return jp, mp


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Disk usage report (Sprint U)")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.root or a.course:
        if a.root:
            C.set_root(a.root)
        else:
            C.set_course(a.course)
        rep = {
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "base": str(C.BASE),
            "n_courses": 1,
            "courses": [scan_course(C.ROOT, course_name=C.COURSE or C.ROOT.name, top=a.top)],
            "top_lessons": [],
        }
        rep["total_bytes"] = rep["courses"][0]["total_bytes"]
        rep["total_human"] = _fmt(rep["total_bytes"])
        rep["top_lessons"] = [
            {**L, "course": rep["courses"][0]["course"]}
            for L in rep["courses"][0].get("top_lessons") or []
        ]
    else:
        rep = scan_warehouse(top=a.top)
    if a.write:
        jp, mp = write_report(rep)
        print(f">> {jp}")
        print(f">> {mp}")
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return
    print(f"Disk @ {rep.get('checked_at')}")
    print(f"  {rep.get('n_courses')} khóa · {rep.get('total_human')}")
    for c in (rep.get("courses") or [])[:20]:
        if c.get("error"):
            print(f"  ! {c.get('item')}: {c['error']}")
        else:
            print(f"  - {c.get('item') or c.get('course')}: {_fmt(c.get('total_bytes') or 0)} "
                  f"({c.get('n_videos') or 0} vid)")
    print("  Top lessons:")
    for L in (rep.get("top_lessons") or [])[:8]:
        print(f"    {_fmt(L['size']):>10}  [{L.get('course')}] {L.get('rel')}")


if __name__ == "__main__":
    main()
