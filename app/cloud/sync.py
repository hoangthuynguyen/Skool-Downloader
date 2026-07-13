#!/usr/bin/env python3
"""
Dong bo 1 khoa len cloud (R2) theo policy knowledge/full.

  python -m cloud.sync --course "X"
  python -m cloud.sync --course "X" --mode knowledge --dry-run
"""
from __future__ import annotations

import argparse, json, hashlib, time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as C
from cloud.policy import iter_upload_files
from cloud import r2 as R2

SETTINGS_FILE = Path(__file__).resolve().parents[1] / ".settings.json"


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cloud_settings():
    return load_settings().get("cloud") or {}


def save_cloud_settings(cloud_cfg):
    s = load_settings()
    s["cloud"] = cloud_cfg
    save_settings(s)


def test_connection():
    cfg = load_cloud_settings()
    if (cfg.get("provider") or "r2").lower() != "r2":
        return False, "Phase 1 chỉ hỗ trợ provider=r2."
    return R2.test_connection(cfg.get("r2") or {})


def _file_sig(path: Path):
    st = path.stat()
    return {"size": st.st_size, "mtime": int(st.st_mtime)}


def _state_path(root: Path):
    return Path(root) / "_cloud_sync.json"


def load_sync_state(root):
    p = _state_path(root)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"files": {}, "last_sync": None}


def save_sync_state(root, state):
    p = _state_path(root)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_course(root, course_name=None, mode=None, dry_run=False, log=print, force=False):
    """Upload file theo policy. Tra ve dict stats."""
    root = Path(root)
    cloud = load_cloud_settings()
    provider = (cloud.get("provider") or "r2").lower()
    mode = mode or cloud.get("mode") or "knowledge"
    if provider != "r2":
        raise RuntimeError(f"Provider chưa hỗ trợ: {provider} (Phase 1: r2)")
    r2cfg = cloud.get("r2") or {}
    if not (r2cfg.get("bucket") and (r2cfg.get("access_key") or r2cfg.get("secret_key"))):
        raise RuntimeError("Chưa cấu hình R2. Vào Cloud trong app hoặc sửa app/.settings.json → cloud.r2")

    course_name = course_name or root.name
    prefix = cloud.get("prefix") or ""
    state = load_sync_state(root)
    files_state = state.setdefault("files", {})

    planned = list(iter_upload_files(root, mode=mode))
    stats = {"total": len(planned), "uploaded": 0, "skipped": 0, "failed": 0, "bytes": 0, "errors": []}
    log(f">> Cloud sync [{mode}] {course_name}: {len(planned)} file ứng viên")

    for i, path in enumerate(planned, 1):
        rel = path.relative_to(root)
        rel_s = str(rel).replace("\\", "/")
        sig = _file_sig(path)
        prev = files_state.get(rel_s)
        if not force and prev and prev.get("size") == sig["size"] and prev.get("mtime") == sig["mtime"]:
            stats["skipped"] += 1
            continue
        key = R2.remote_key(course_name, rel_s, prefix=prefix)
        if dry_run:
            log(f"   [dry] {rel_s} -> {key}")
            stats["uploaded"] += 1
            continue
        try:
            log(f"   [{i}/{len(planned)}] {rel_s}")
            R2.upload_file(r2cfg, path, key)
            files_state[rel_s] = {**sig, "key": key, "ts": int(time.time())}
            stats["uploaded"] += 1
            stats["bytes"] += sig["size"]
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"{rel_s}: {e}")
            log(f"   [LỖI] {rel_s}: {e}")

    if not dry_run:
        state["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        state["mode"] = mode
        state["provider"] = "r2"
        save_sync_state(root, state)
    log(f">> Xong: upload={stats['uploaded']} skip={stats['skipped']} fail={stats['failed']} "
        f"({stats['bytes']} bytes)")
    return stats


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Sync course to R2")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--mode", choices=["knowledge", "full"], default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        ok, msg = test_connection()
        print(("OK: " if ok else "FAIL: ") + msg)
        return
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    sync_course(C.ROOT, course_name=C.COURSE or C.ROOT.name,
                mode=a.mode, dry_run=a.dry_run, force=a.force)


if __name__ == "__main__":
    main()
