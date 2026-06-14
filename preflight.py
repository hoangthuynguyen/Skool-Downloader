#!/usr/bin/env python3
"""Kiem tra moi truong TRUOC khi chay -> giam toi da loi luc tai.
   In bang PASS / WARN / FAIL kem cach sua. Exit 1 neu co FAIL (thieu thu thiet yeu).

   python preflight.py                 # kiem tra chung
   python preflight.py --course "X"    # + kiem tra da co JSON dump cua khoa
"""
import argparse, importlib.util, shutil, sys
from pathlib import Path
import config as C
import common as K

OK, WARN, FAIL = "PASS", "WARN", "FAIL"

def has_mod(m):
    return importlib.util.find_spec(m) is not None

def run_checks(check_json=False):
    """Kiem tra moi truong theo C hien tai. In bang. Tra ve so loi FAIL."""
    rows = []
    def add(name, status, detail, fix=""):
        rows.append((name, status, detail, fix))

    # 1) Python
    v = sys.version_info
    if v >= (3, 9): add("Python", OK, f"{v.major}.{v.minor}.{v.micro}")
    else: add("Python", FAIL, f"{v.major}.{v.minor}", "Can Python >= 3.9")

    # 2) yt-dlp (tai video)
    if has_mod("yt_dlp"): add("yt-dlp", OK, "da cai")
    else: add("yt-dlp", FAIL, "thieu", "Chay setup.ps1  (pip install -U yt-dlp)")

    # 3) Node / Deno (vuot YouTube bot-check)
    node = shutil.which("node"); deno = shutil.which("deno")
    if node or deno: add("JS runtime", OK, f"node={bool(node)} deno={bool(deno)}")
    else: add("JS runtime", WARN, "khong co Node/Deno",
              "Cai Node.js (nodejs.org) - neu khong, video YouTube se bi chan bot")

    # 4) ffmpeg (ghep video native/loom)
    ff = K.ffmpeg_dir() or (shutil.which("ffmpeg") and "PATH")
    if ff: add("ffmpeg", OK, str(ff))
    else: add("ffmpeg", FAIL, "thieu", "Chay setup.ps1  (ffdl install --add-path)")

    # 5) faster-whisper (chi can khi transcribe)
    if has_mod("faster_whisper"): add("faster-whisper", OK, "da cai")
    elif has_mod("whisper"): add("faster-whisper", WARN, "chua co, nhung co openai-whisper",
                                  "pip install -U faster-whisper (nhanh hon) hoac doi WHISPER_ENGINE")
    else: add("transcribe", WARN, "chua co engine transcribe nao",
              "pip install -U faster-whisper  (chi can neu muon phu de)")

    # 6) Dung luong dia
    try:
        free_gb = shutil.disk_usage(C.BASE).free / (1024**3)
        st = OK if free_gb >= 20 else WARN
        add("Dia trong", st, f"{free_gb:.1f} GB o {C.BASE.drive or C.BASE}",
            "Video khoa lon co the >100GB - don bot dia" if st == WARN else "")
    except Exception as e:
        add("Dia trong", WARN, f"khong do duoc: {e}")

    # 7) JSON dump cua khoa (chi khi chi dinh course/root)
    if check_json:
        vids = list(C.DUMP_ROOT.rglob(C.VID_PATTERN))
        if vids: add("JSON dump", OK, f"{len(vids)} file vid_*.json o {C.DUMP_ROOT}")
        else: add("JSON dump", FAIL, f"khong thay vid_*.json trong {C.DUMP_ROOT}",
                  "Dump bang extractor.js (xem README) roi dat vao thu muc khoa")

    # In bang
    print(f"\n===== PREFLIGHT  (khoa: {C.COURSE or C.ROOT.name}) =====")
    width = max(len(r[0]) for r in rows)
    for name, status, detail, fix in rows:
        print(f"  [{status}] {name.ljust(width)}  {detail}")
        if fix and status != OK:
            print(f"         -> {fix}")
    nfail = sum(1 for r in rows if r[1] == FAIL)
    nwarn = sum(1 for r in rows if r[1] == WARN)
    print(f"\n  Ket qua: {nfail} FAIL, {nwarn} WARN")
    if nfail:
        print("  => Co loi THIET YEU, hay sua FAIL truoc khi chay.\n")
    else:
        print("  => San sang chay.\n")
    return nfail

def main():
    K.setup_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--course"); ap.add_argument("--root")
    a = ap.parse_args()
    if a.root: C.set_root(a.root)
    elif a.course: C.set_course(a.course)
    return 1 if run_checks(check_json=bool(a.course or a.root)) else 0

if __name__ == "__main__":
    sys.exit(main())
