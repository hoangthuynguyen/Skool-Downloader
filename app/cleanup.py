#!/usr/bin/env python3
"""
Don rac tai do + doc video_fails (Phase 8).

  python cleanup.py --course "X"              # liet ke .part/.ytdl
  python cleanup.py --course "X" --apply      # xoa file do
  python cleanup.py --course "X" --fails      # in video_fails.json
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C

STALE_SUFFIXES = (".part", ".ytdl", ".temp", ".tmp")
STALE_GLOBS = ("*.part", "*.ytdl", "*.part-Frag*", "video.f*.mp4", "video.f*.webm")


def load_fails(root):
    """Doc video_fails.json. Tra ve list dict {folder,code,message,fix}."""
    p = Path(root) / "video_fails.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def summarize_fails(fails):
    """Gom theo code -> {code, message, fix, count, samples}."""
    groups = {}
    for f in fails or []:
        code = f.get("code") or "unknown"
        g = groups.setdefault(code, {
            "code": code,
            "message": f.get("message") or code,
            "fix": f.get("fix") or "",
            "count": 0,
            "samples": [],
        })
        g["count"] += 1
        if len(g["samples"]) < 5:
            g["samples"].append(f.get("folder") or "")
    return sorted(groups.values(), key=lambda x: -x["count"])


def find_stale_downloads(root, min_age_sec=0):
    """Tim file tai do / fragment. min_age_sec: chi file cu hon N giay."""
    root = Path(root)
    if not root.exists():
        return []
    now = time.time()
    found = []
    seen = set()
    patterns = ["**/*.part", "**/*.ytdl", "**/*Frag*", "**/*.part-Frag*"]
    for pat in patterns:
        for p in root.glob(pat):
            if not p.is_file():
                continue
            key = str(p)
            if key in seen:
                continue
            # bo resources
            if any(x.lower() == "resources" for x in p.parts):
                continue
            try:
                age = now - p.stat().st_mtime
                size = p.stat().st_size
            except OSError:
                continue
            if age < min_age_sec:
                continue
            seen.add(key)
            found.append({"path": p, "size": size, "age_sec": int(age)})
    return sorted(found, key=lambda x: str(x["path"]))


def cleanup_stale(root, apply=False, min_age_sec=120, log=print):
    """Xoa file tai do. Mac dinh chi file > 2 phut (tranh xoa dang tai)."""
    items = find_stale_downloads(root, min_age_sec=min_age_sec)
    if not items:
        log("Khong co file .part/.ytdl thua.")
        return {"found": 0, "deleted": 0, "bytes": 0}
    total = sum(i["size"] for i in items)
    log(f"Tim thay {len(items)} file rac (~{total} bytes)"
        + ("" if apply else " — dry-run, them --apply de xoa"))
    deleted = 0
    freed = 0
    for i in items:
        log(f"  {'DEL' if apply else '   '} {i['path']}  ({i['size']} B, age {i['age_sec']}s)")
        if apply:
            try:
                i["path"].unlink()
                deleted += 1
                freed += i["size"]
            except Exception as e:
                log(f"  [!] {e}")
    return {"found": len(items), "deleted": deleted, "bytes": freed}


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Cleanup partial downloads / show fails")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--apply", action="store_true", help="Xoa file rac (mac dinh chi liet ke)")
    ap.add_argument("--min-age", type=int, default=120, help="Chi xoa file cu hon N giay")
    ap.add_argument("--fails", action="store_true", help="In video_fails.json")
    a = ap.parse_args()
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    root = C.ROOT
    if a.fails:
        fails = load_fails(root)
        if not fails:
            print("(khong co video_fails.json)")
        else:
            print(f"{len(fails)} bai fail:")
            for g in summarize_fails(fails):
                print(f"  [{g['code']}] x{g['count']}  {g['message']}")
                print(f"     -> {g['fix']}")
        return
    cleanup_stale(root, apply=a.apply, min_age_sec=a.min_age)


if __name__ == "__main__":
    main()
