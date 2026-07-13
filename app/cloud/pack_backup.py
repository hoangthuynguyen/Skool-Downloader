#!/usr/bin/env python3
"""
Sprint D — Backup / restore knowledge pack (zip text, khong video).

  # Local backup
  python -m cloud.pack_backup --course "X" --backup
  python -m cloud.pack_backup --course "X" --backup --upload   # + cloud neu co
  python -m cloud.pack_backup --list
  python -m cloud.pack_backup --restore path/to.zip --course "X"

Restore chi ghi de file knowledge (md/txt/srt/json nhe); KHONG xoa video.
"""
from __future__ import annotations

import argparse, json, shutil, time, zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as C
import knowledge_pack as KP

# file trong zip duoc phep extract khi restore
SAFE_SUFFIXES = {".md", ".txt", ".srt", ".json", ".csv", ".html", ".vtt"}
SAFE_NAMES = {
    "description.md", "video.txt", "video.srt",
    "_TongHop.md", "_TongHop.vi.md", "_TomTat.md",
    "Transcript_VI.md", "PhuDe_SongNgu.srt",
    "_chapters.json", "video_audit.txt", "video_fails.json",
    "_health.json", "_update_diff.json", "_pack_manifest.json", "README.md",
}
SKIP_PARTS = {".rag", "__pycache__", ".git", "_site", ".ytdl"}
SKIP_SUFFIX = {".mp4", ".webm", ".mkv", ".mov", ".part", ".ytdl", ".exe", ".dll"}


def backups_dir() -> Path:
    d = C.BASE / "courses" / "_backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(course_name: str) -> str:
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in (course_name or "course")).strip() or "course"


def local_backup_path(course_name: str, stamp: str | None = None) -> Path:
    stamp = stamp or time.strftime("%Y%m%d_%H%M%S")
    return backups_dir() / f"{_safe_name(course_name)}_KnowledgePack_{stamp}.zip"


def backup_knowledge(root, course_name=None, out_path=None, upload=False, log=print):
    """Tao zip knowledge pack vao _backups/; optional upload cloud.

    Tra ve dict: {local, uploaded, remote_key, bytes, files}
    """
    root = Path(root)
    course_name = course_name or root.name
    out_path = Path(out_path) if out_path else local_backup_path(course_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    zpath = KP.pack_course(root, course_name=course_name, out_path=str(out_path), log=log)
    zpath = Path(zpath)
    result = {
        "local": str(zpath),
        "course": course_name,
        "bytes": zpath.stat().st_size if zpath.exists() else 0,
        "uploaded": False,
        "remote_key": None,
        "provider": None,
        "error": None,
    }

    # manifest local
    man = {
        "course": course_name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "local": str(zpath),
        "bytes": result["bytes"],
    }
    man_path = zpath.with_suffix(zpath.suffix + ".meta.json")
    try:
        man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    if upload:
        try:
            remote = upload_pack(zpath, course_name=course_name, log=log)
            result["uploaded"] = True
            result["remote_key"] = remote.get("key")
            result["provider"] = remote.get("provider")
            man["remote_key"] = result["remote_key"]
            man["provider"] = result["provider"]
            man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            result["error"] = str(e)
            log(f"[backup upload] {e}")
    return result


def upload_pack(zip_path, course_name=None, log=print):
    """Upload 1 knowledge pack zip len provider dang chon."""
    from cloud.sync import load_cloud_settings
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)
    course_name = course_name or zip_path.stem
    cloud = load_cloud_settings() or {}
    provider = (cloud.get("provider") or "r2").lower()
    prefix = cloud.get("prefix") or ""
    rel = f"_packs/{zip_path.name}"
    log(f">> Upload pack [{provider}] {zip_path.name}")

    if provider == "r2":
        from cloud import r2 as R2
        r2cfg = cloud.get("r2") or {}
        key = R2.remote_key(course_name, rel, prefix=prefix)
        R2.upload_file(r2cfg, zip_path, key)
        return {"provider": "r2", "key": key}
    if provider == "gdrive":
        from cloud import gdrive as GD
        gdcfg = cloud.get("gdrive") or {}
        rid = GD.upload_file(gdcfg, zip_path, rel, course_name=course_name)
        return {"provider": "gdrive", "key": rid}
    if provider == "onedrive":
        from cloud import onedrive as OD
        odcfg = cloud.get("onedrive") or {}
        rid = OD.upload_file(odcfg, zip_path, rel, course_name=course_name, log=log)
        return {"provider": "onedrive", "key": rid}
    raise RuntimeError(f"Provider chưa hỗ trợ upload pack: {provider}")


def list_backups(course_name=None):
    """List zip trong _backups/ (loc theo course neu co)."""
    d = backups_dir()
    items = []
    safe = _safe_name(course_name) if course_name else None
    for p in sorted(d.glob("*_KnowledgePack_*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        if safe and not p.name.startswith(safe):
            continue
        meta = {}
        mp = Path(str(p) + ".meta.json")
        if mp.exists():
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                pass
        items.append({
            "path": str(p),
            "name": p.name,
            "bytes": p.stat().st_size,
            "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)),
            "meta": meta,
        })
    return items


def _is_safe_member(name: str) -> bool:
    name = name.replace("\\", "/").lstrip("/")
    if not name or name.endswith("/"):
        return False
    parts = name.split("/")
    if any(p in SKIP_PARTS or p.startswith(".") and p not in (".", "..") for p in parts if p not in (".",)):
        # cho phep file an nhe nhu .htaccess? khong can
        if any(p in SKIP_PARTS for p in parts):
            return False
    base = Path(name).name
    suf = Path(name).suffix.lower()
    if suf in SKIP_SUFFIX:
        return False
    if base in SAFE_NAMES or suf in SAFE_SUFFIXES:
        return True
    # resources/*
    if "resources" in parts and suf not in SKIP_SUFFIX:
        return True
    return False


def restore_knowledge(zip_path, dest_root, course_name=None, log=print, dry_run=False):
    """Giai nen knowledge pack vao dest_root (an toan — khong video).

    Zip co the co prefix <course>/... hoac flat.
    Tra ve {extracted, skipped, dest}
    """
    zip_path = Path(zip_path)
    dest_root = Path(dest_root)
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)
    dest_root.mkdir(parents=True, exist_ok=True)

    extracted = skipped = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/") or not _is_safe_member(name):
                skipped += 1
                continue
            # bo prefix course neu co
            parts = name.split("/")
            if course_name and parts and parts[0] in (course_name, _safe_name(course_name)):
                rel = "/".join(parts[1:])
            elif parts and parts[0] not in ("resources",) and not parts[0].startswith("_") \
                    and Path(parts[0]).suffix == "" and len(parts) > 1:
                # co the la ten khoa bat ky o root zip
                rel = "/".join(parts[1:]) if parts[1:] else parts[0]
            else:
                rel = name
            if not rel or rel in ("README.md", "_pack_manifest.json"):
                # README pack -> ghi vao _pack_restore_README.md
                if rel == "README.md":
                    rel = "_pack_restore_README.md"
                elif rel == "_pack_manifest.json":
                    rel = "_pack_restore_manifest.json"
            target = dest_root / rel
            # chong path traversal
            try:
                target.resolve().relative_to(dest_root.resolve())
            except ValueError:
                skipped += 1
                continue
            if dry_run:
                log(f"   [dry] {rel}")
                extracted += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted += 1
            log(f"   + {rel}")
    log(f">> Restore: extracted={extracted} skipped={skipped} -> {dest_root}")
    return {"extracted": extracted, "skipped": skipped, "dest": str(dest_root), "zip": str(zip_path)}


def download_pack_r2(remote_key, dest_path, log=print):
    """Tai pack tu R2 ve local (neu provider r2)."""
    from cloud.sync import load_cloud_settings
    from cloud import r2 as R2
    cloud = load_cloud_settings() or {}
    r2cfg = cloud.get("r2") or {}
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    log(f">> Download R2 {remote_key} -> {dest_path}")
    R2.download_file(r2cfg, remote_key, dest_path)
    return dest_path


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Knowledge pack backup / restore (Sprint D)")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--backup", action="store_true")
    ap.add_argument("--upload", action="store_true", help="Upload pack len cloud sau khi zip")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--restore", help="Duong dan .zip de restore")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", help="Duong dan zip output khi backup")
    a = ap.parse_args()

    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)

    if a.list:
        items = list_backups(a.course)
        if not items:
            print("(chua co backup trong courses/_backups/)")
            return
        for it in items:
            print(f"{it['mtime']}  {it['bytes']:>10}  {it['name']}")
            print(f"   {it['path']}")
        return

    if a.restore:
        if a.root:
            dest = Path(a.root)
        elif a.course:
            C.set_course(a.course)
            dest = C.ROOT
        else:
            dest = C.ROOT
        r = restore_knowledge(a.restore, dest, course_name=C.COURSE or dest.name,
                              dry_run=a.dry_run)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    if a.backup:
        r = backup_knowledge(
            C.ROOT, course_name=C.COURSE or C.ROOT.name,
            out_path=a.out, upload=a.upload,
        )
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    ap.error("Can --backup / --list / --restore")


if __name__ == "__main__":
    main()
