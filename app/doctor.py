#!/usr/bin/env python3
"""
Doctor — kiem tra toan bo moi truong + Phase 1-5 (Phase 6 hardening).

  python doctor.py
  python doctor.py --json
  python doctor.py --fix-base /path/to/SkoolProject
"""
from __future__ import annotations

import argparse, importlib.util, json, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as C
import common as K

OK, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"


def has_mod(m):
    return importlib.util.find_spec(m) is not None


def run_doctor(fix_base=None):
    if fix_base:
        C.set_base(fix_base, persist=False)

    rows = []

    def add(cat, name, status, detail, fix=""):
        rows.append({"category": cat, "name": name, "status": status,
                     "detail": detail, "fix": fix})

    # --- Core ---
    v = sys.version_info
    add("core", "Python", OK if v >= (3, 9) else FAIL,
        f"{v.major}.{v.minor}.{v.micro}", "Can Python >= 3.9" if v < (3, 9) else "")
    add("core", "yt-dlp", OK if has_mod("yt_dlp") else FAIL,
        "ok" if has_mod("yt_dlp") else "thieu", "pip install -U yt-dlp")
    node, deno = shutil.which("node"), shutil.which("deno")
    add("core", "JS runtime", OK if (node or deno) else WARN,
        f"node={bool(node)} deno={bool(deno)}",
        "Cai Node.js neu tai YouTube")
    ff = None
    try:
        ff = K.ffmpeg_bin() or K.ffmpeg_dir() or (shutil.which("ffmpeg") and "PATH")
    except Exception:
        ff = shutil.which("ffmpeg")
    add("core", "ffmpeg", OK if ff else FAIL, str(ff or "thieu"),
        "brew install ffmpeg  |  python -m ffmpeg_downloader install -y")
    add("core", "faster-whisper",
        OK if has_mod("faster_whisper") else (WARN if has_mod("whisper") else WARN),
        "ok" if has_mod("faster_whisper") else "thieu (chi can khi phu de)",
        "pip install faster-whisper")
    add("core", "customtkinter", OK if has_mod("customtkinter") else WARN,
        "ok" if has_mod("customtkinter") else "thieu GUI", "pip install customtkinter")
    add("core", "playwright", OK if has_mod("playwright") else WARN,
        "ok" if has_mod("playwright") else "thieu (dump browser)", "pip install playwright && playwright install chromium")

    # --- Paths ---
    info = C.base_info()
    add("path", "BASE", OK, f"{info['base']}  ({info['source']})")
    add("path", "Downloader", INFO, info["archiver"])
    add("path", "courses/", OK if info["courses_exists"] else WARN,
        info["courses"],
        "Chua co — se tao khi import khoa, hoac dat SKOOL_BASE / settings skool_base")
    try:
        free_gb = shutil.disk_usage(C.BASE).free / (1024 ** 3)
        add("path", "Dia trong", OK if free_gb >= 20 else WARN, f"{free_gb:.1f} GB")
    except Exception as e:
        add("path", "Dia trong", WARN, str(e))

    n_courses = 0
    try:
        import progress as P
        n_courses = len(P.list_course_items())
        add("path", "So khoa", OK if n_courses else WARN, str(n_courses))
    except Exception as e:
        add("path", "So khoa", WARN, str(e))

    # --- Optional Phase features ---
    add("optional", "boto3 (R2)", OK if has_mod("boto3") else WARN,
        "ok" if has_mod("boto3") else "thieu — cloud R2 tat", "pip install boto3")
    add("optional", "google-api (GDrive)",
        OK if has_mod("googleapiclient") else WARN,
        "ok" if has_mod("googleapiclient") else "thieu", "pip install google-api-python-client google-auth")
    add("optional", "msal (OneDrive)", OK if has_mod("msal") else WARN,
        "ok" if has_mod("msal") else "thieu", "pip install msal")
    add("optional", "sentence-transformers",
        OK if has_mod("sentence_transformers") else INFO,
        "dense RAG" if has_mod("sentence_transformers") else "dung TF-IDF (du)",
        "pip install sentence-transformers")
    add("optional", "pystray (tray)", OK if has_mod("pystray") else INFO,
        "ok" if has_mod("pystray") else "thieu tray", "pip install pystray pillow")
    add("optional", "requests", OK if has_mod("requests") else WARN, "Claude/API")
    add("optional", "python-docx", OK if has_mod("docx") else INFO, "xuat Word")
    add("optional", "deep-translator", OK if has_mod("deep_translator") else INFO, "dich free")
    add("optional", "send2trash", OK if has_mod("send2trash") else INFO, "xoa an toan")

    # --- Modules import ---
    for mod in (
        "queue_engine", "updates", "search_lib", "health_check",
        "web_viewer", "export_site", "rag.index", "rag.vector", "cloud.sync",
        "knowledge_pack", "notify", "session_state", "anki_export", "quiz",
        "progress_live", "learn_playlist", "content_diff", "vault_export",
        "tools_fix", "notes", "disk_report", "study_plan", "cloud.pack_backup",
        "llm_prompt", "llm_providers",
    ):
        try:
            __import__(mod)
            add("modules", mod, OK, "import ok")
        except Exception as e:
            add("modules", mod, FAIL, str(e)[:120])

    # Cloud config present?
    try:
        from cloud.sync import load_cloud_settings
        cfg = load_cloud_settings() or {}
        prov = cfg.get("provider") or "(chua chon)"
        add("cloud", "provider", INFO, str(prov))
    except Exception as e:
        add("cloud", "settings", WARN, str(e))

    nfail = sum(1 for r in rows if r["status"] == FAIL)
    nwarn = sum(1 for r in rows if r["status"] == WARN)
    return {
        "base": info,
        "courses": n_courses,
        "fail": nfail,
        "warn": nwarn,
        "rows": rows,
    }


def print_report(rep):
    print("\n===== SKOOL DOWNLOADER DOCTOR =====")
    print(f"BASE: {rep['base']['base']}  [{rep['base']['source']}]")
    print(f"Khóa: {rep['courses']}")
    cur = None
    for r in rep["rows"]:
        if r["category"] != cur:
            cur = r["category"]
            print(f"\n-- {cur} --")
        print(f"  [{r['status']:4}] {r['name']}: {r['detail']}")
        if r.get("fix") and r["status"] in (FAIL, WARN):
            print(f"         -> {r['fix']}")
    print(f"\n  Ket qua: {rep['fail']} FAIL, {rep['warn']} WARN")
    if rep["fail"]:
        print("  => Sua FAIL truoc khi chay production.\n")
    else:
        print("  => Core san sang.\n")


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Doctor — full environment check")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix-base", help="Thu BASE khac (khong ghi settings)")
    ap.add_argument("--set-base", help="Dat va luu BASE vao settings.json")
    ap.add_argument("--fix", action="store_true",
                    help="Sprint S: one-click fix (yt-dlp -U + pip goi thieu)")
    ap.add_argument("--fix-ytdlp", action="store_true", help="Chi cap nhat yt-dlp")
    a = ap.parse_args()
    if a.set_base:
        p = C.set_base(a.set_base, persist=True)
        print(f"Da luu skool_base = {p}")
    if a.fix or a.fix_ytdlp:
        import tools_fix as TF
        if a.fix_ytdlp:
            print(TF.update_ytdlp())
        else:
            r = TF.fix_all(yt_dlp=True, from_doctor=True)
            print(f"fix ok={r.get('ok')}")
        # re-run doctor after fix
    rep = run_doctor(fix_base=a.fix_base)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print_report(rep)
    return 1 if rep["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
