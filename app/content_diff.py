#!/usr/bin/env python3
"""
Sprint Q — phat hien noi dung bai thay doi (description / transcript) sau re-dump.

  python content_diff.py --course "X" --snapshot   # luu hash hien tai
  python content_diff.py --course "X"              # so sanh vs snapshot
  python content_diff.py --course "X" --write      # ghi _content_diff.json
"""
from __future__ import annotations

import argparse, hashlib, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import common as K

WATCH_NAMES = ("description.md", "video.txt", "video.srt")


def _file_hash(path: Path) -> str:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return ""


def build_snapshot(root) -> dict:
    """Hash text files theo rel path."""
    root = Path(root)
    files = {}
    for name in WATCH_NAMES:
        for p in root.rglob(name):
            if not p.is_file():
                continue
            try:
                rel = str(p.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            if any(x in rel for x in (".rag/", "__pycache__", "_site/")):
                continue
            files[rel] = {
                "hash": _file_hash(p),
                "size": p.stat().st_size,
                "mtime": int(p.stat().st_mtime),
            }
    return {
        "course": root.name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_files": len(files),
        "files": files,
    }


def snapshot_path(root) -> Path:
    return Path(root) / "_content_snapshot.json"


def diff_path(root) -> Path:
    return Path(root) / "_content_diff.json"


def save_snapshot(root, snap=None):
    root = Path(root)
    snap = snap or build_snapshot(root)
    p = snapshot_path(root)
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return p, snap


def load_snapshot(root):
    p = snapshot_path(root)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def compare(root, old=None):
    """So sanh snapshot cu vs hien tai.

    Tra ve {added, removed, changed, unchanged, summary, has_changes}
    """
    root = Path(root)
    old = old if old is not None else load_snapshot(root)
    new = build_snapshot(root)
    old_files = (old or {}).get("files") or {}
    new_files = new.get("files") or {}
    old_keys = set(old_files)
    new_keys = set(new_files)
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    changed = []
    for k in sorted(old_keys & new_keys):
        if (old_files[k].get("hash") or "") != (new_files[k].get("hash") or ""):
            changed.append({
                "path": k,
                "old_size": old_files[k].get("size"),
                "new_size": new_files[k].get("size"),
            })
    n_u = len(old_keys & new_keys) - len(changed)
    parts = []
    if added:
        parts.append(f"+{len(added)} file mới")
    if removed:
        parts.append(f"-{len(removed)} file mất")
    if changed:
        parts.append(f"~{len(changed)} file đổi")
    if not parts:
        parts.append("Không đổi so với snapshot" if old else "Chưa có snapshot — chỉ scan hiện tại")
    return {
        "course": root.name,
        "compared_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "had_snapshot": bool(old),
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": n_u,
        "n_current": len(new_files),
        "summary": " · ".join(parts),
        "has_changes": bool(added or removed or changed),
        "snapshot_now": new,
    }


def write_diff(root, result=None):
    root = Path(root)
    result = result or compare(root)
    # bo snapshot_now de file nhe (tuy chon giu)
    out = {k: v for k, v in result.items() if k != "snapshot_now"}
    p = diff_path(root)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return p, out


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Content snapshot / diff (Sprint Q)")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--snapshot", action="store_true", help="Luu snapshot hash hien tai")
    ap.add_argument("--write", action="store_true", help="Ghi _content_diff.json")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    root = C.ROOT
    if a.snapshot:
        p, snap = save_snapshot(root)
        print(f">> Snapshot: {snap['n_files']} file → {p}")
        return
    r = compare(root)
    if a.write:
        p, _ = write_diff(root, r)
        print(f">> Diff → {p}")
    if a.json:
        print(json.dumps({k: v for k, v in r.items() if k != "snapshot_now"},
                         ensure_ascii=False, indent=2))
    else:
        print(r["summary"])
        for c in (r.get("changed") or [])[:20]:
            print(f"  ~ {c['path']}  ({c.get('old_size')} → {c.get('new_size')})")
        for x in (r.get("added") or [])[:10]:
            print(f"  + {x}")
        for x in (r.get("removed") or [])[:10]:
            print(f"  - {x}")
        if not r.get("had_snapshot"):
            print("  (goi --snapshot de co baseline lan sau)")


if __name__ == "__main__":
    main()
