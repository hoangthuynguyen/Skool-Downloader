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


def test_connection(log=print):
    cfg = load_cloud_settings()
    provider = (cfg.get("provider") or "r2").lower()
    if provider == "r2":
        return R2.test_connection(cfg.get("r2") or {})
    if provider == "gdrive":
        from cloud import gdrive as GD
        return GD.test_connection(cfg.get("gdrive") or {})
    if provider == "onedrive":
        from cloud import onedrive as OD
        return OD.test_connection(cfg.get("onedrive") or {}, log=log)
    return False, f"Provider chưa hỗ trợ: {provider} (r2 | gdrive | onedrive)"


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
    """Upload file theo policy. provider: r2 | gdrive | onedrive."""
    root = Path(root)
    cloud = load_cloud_settings()
    provider = (cloud.get("provider") or "r2").lower()
    mode = mode or cloud.get("mode") or "knowledge"
    course_name = course_name or root.name
    prefix = cloud.get("prefix") or ""
    state = load_sync_state(root)
    files_state = state.setdefault("files", {})

    r2cfg = gdcfg = odcfg = None
    if provider == "r2":
        r2cfg = cloud.get("r2") or {}
        if not (r2cfg.get("bucket") and (r2cfg.get("access_key") or r2cfg.get("secret_key"))):
            raise RuntimeError("Chưa cấu hình R2. Vào Cloud trong app → cloud.r2")
    elif provider == "gdrive":
        gdcfg = cloud.get("gdrive") or {}
        if not (gdcfg.get("service_account_json") or gdcfg.get("client_secrets_json")):
            raise RuntimeError("Chưa cấu hình Google Drive (service_account_json hoặc client_secrets_json).")
        from cloud import gdrive as GD
    elif provider == "onedrive":
        odcfg = cloud.get("onedrive") or {}
        if not odcfg.get("client_id"):
            raise RuntimeError("Chưa cấu hình OneDrive (client_id). Vào Cloud trong app.")
        from cloud import onedrive as OD
    else:
        raise RuntimeError(f"Provider chưa hỗ trợ: {provider} (r2 | gdrive | onedrive)")

    planned = list(iter_upload_files(root, mode=mode))
    stats = {"total": len(planned), "uploaded": 0, "skipped": 0, "failed": 0, "bytes": 0,
             "errors": [], "provider": provider}
    log(f">> Cloud sync [{provider}/{mode}] {course_name}: {len(planned)} file ứng viên")

    for i, path in enumerate(planned, 1):
        rel = path.relative_to(root)
        rel_s = str(rel).replace("\\", "/")
        sig = _file_sig(path)
        prev = files_state.get(rel_s)
        if not force and prev and prev.get("size") == sig["size"] and prev.get("mtime") == sig["mtime"] \
                and prev.get("provider", provider) == provider:
            stats["skipped"] += 1
            continue
        if dry_run:
            if provider == "r2":
                dest = R2.remote_key(course_name, rel_s, prefix=prefix)
            elif provider == "gdrive":
                dest = f"gdrive:courses/{course_name}/{rel_s}"
            else:
                dest = f"onedrive:{(odcfg or {}).get('folder') or 'SkoolDownloader'}/courses/{course_name}/{rel_s}"
            log(f"   [dry] {rel_s} -> {dest}")
            stats["uploaded"] += 1
            continue
        try:
            log(f"   [{i}/{len(planned)}] {rel_s}")
            if provider == "r2":
                key = R2.remote_key(course_name, rel_s, prefix=prefix)
                R2.upload_file(r2cfg, path, key)
                remote_id = key
            elif provider == "gdrive":
                remote_id = GD.upload_file(gdcfg, path, rel_s, course_name=course_name)
            else:
                remote_id = OD.upload_file(odcfg, path, rel_s, course_name=course_name, log=log)
            files_state[rel_s] = {**sig, "key": remote_id, "provider": provider, "ts": int(time.time())}
            stats["uploaded"] += 1
            stats["bytes"] += sig["size"]
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"{rel_s}: {e}")
            log(f"   [LỖI] {rel_s}: {e}")

    if not dry_run:
        state["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        state["mode"] = mode
        state["provider"] = provider
        save_sync_state(root, state)
    log(f">> Xong ({provider}): upload={stats['uploaded']} skip={stats['skipped']} fail={stats['failed']} "
        f"({stats['bytes']} bytes)")
    return stats


def sync_all_courses(mode=None, dry_run=False, force=False, log=print):
    """Sync moi khoa duoi BASE/courses (+ legacy)."""
    import progress as P
    results = []
    for meta in P.list_course_items():
        name = meta.get("course") or "SkoolCourse"
        log(f"\n==== {meta.get('item')} ====")
        try:
            st = sync_course(meta["root"], course_name=name, mode=mode,
                             dry_run=dry_run, force=force, log=log)
            results.append({"item": meta["item"], "ok": True, "stats": st})
        except Exception as e:
            log(f"[FAIL] {e}")
            results.append({"item": meta["item"], "ok": False, "error": str(e)})
    return results


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Sync course to R2 / GDrive / OneDrive")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--all", action="store_true", help="Sync tat ca khoa")
    ap.add_argument("--mode", choices=["knowledge", "full"], default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        ok, msg = test_connection()
        print(("OK: " if ok else "FAIL: ") + msg)
        return
    if a.all:
        sync_all_courses(mode=a.mode, dry_run=a.dry_run, force=a.force)
        return
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    sync_course(C.ROOT, course_name=C.COURSE or C.ROOT.name,
                mode=a.mode, dry_run=a.dry_run, force=a.force)


if __name__ == "__main__":
    main()
