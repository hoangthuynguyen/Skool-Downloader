#!/usr/bin/env python3
"""
Watcher transcribe chay NGAM: quet video da tai -> sinh video.txt + video.srt canh video.
- Chay song song luc dang tai (bo qua file dang tai & file da co .txt).
- Idempotent: reboot/tat may bat lai -> tu chay tiep phan con lai.
- Khi da transcribe het va 'yen' qua nhieu vong -> bao Windows + thoat.
- Doc lap voi Claude: dung qua Task Scheduler (xem install_transcribe_task.ps1).

  python transcribe_watch.py                      # quet BASE/SkoolCourse (khoa cu)
  python transcribe_watch.py --course "Ten khoa"  # quet 1 khoa
  python transcribe_watch.py --all                # quet tat ca (SkoolCourse + courses/*)
  python transcribe_watch.py --once               # transcribe het roi thoat ngay (khong loop)
"""
import argparse, subprocess, sys, time
from pathlib import Path
import config as C
import common as K
import transcribe as T

def notify(title, message, level="info"):
    ps1 = Path(__file__).with_name("notify.ps1")
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(ps1), "-Title", title, "-Message", message, "-Level", level],
                       timeout=60)
    except Exception as e:
        print(f"   [notify loi] {e}", flush=True)

def roots_to_scan(args):
    if args.all:
        bases = []
        sk = C.BASE / "SkoolCourse"
        if sk.exists(): bases.append(sk)
        cdir = C.BASE / "courses"
        if cdir.exists(): bases += [p for p in cdir.iterdir() if p.is_dir()]
        return bases or [C.ROOT]
    return [C.ROOT]

def pending_all(roots):
    out = []
    for r in roots:
        out += T.pending_videos(r, min_age=C.WATCH_MIN_AGE)
    return out

import re as _re
_PARTIAL = _re.compile(r"\.part$|\.ytdl$|video\.f\d+\.", _re.I)
def downloads_active(roots):
    """Con file tai dang do (.part/.ytdl/fragment) -> dang co download chay -> chua nen ket thuc."""
    for r in roots:
        if not r.exists(): continue
        for p in r.rglob("video.*"):
            if _PARTIAL.search(p.name):
                return True
    return False

def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Watcher transcribe nen")
    ap.add_argument("--course"); ap.add_argument("--root")
    ap.add_argument("--all", action="store_true", help="Quet ca SkoolCourse + tat ca courses/*")
    ap.add_argument("--once", action="store_true", help="Lam het 1 luot roi thoat (khong loop).")
    ap.add_argument("--idle-rounds", type=int, default=3,
                    help="So vong lien tiep khong con video moi thi coi la XONG (mac dinh 3).")
    ap.add_argument("--no-notify", action="store_true")
    a = ap.parse_args()
    if a.root: C.set_root(a.root)
    elif a.course: C.set_course(a.course)

    roots = roots_to_scan(a)
    print(f"=== WATCHER TRANSCRIBE ===")
    print(f"Engine={C.WHISPER_ENGINE} model={C.WHISPER_MODEL} task={C.WHISPER_TASK} lang={C.WHISPER_LANG}")
    print(f"Quet: {', '.join(str(r) for r in roots)}")
    print(f"Chu ky={C.WATCH_INTERVAL}s | min_age={C.WATCH_MIN_AGE}s | idle-rounds={a.idle_rounds} | once={a.once}\n", flush=True)

    total_done = total_skip = total_retry = 0
    idle = 0
    fails = {}   # video -> mo ta loi (de in cuoi)
    try:
        while True:
            todo = pending_all(roots)
            if not todo:
                if a.once:
                    break
                if downloads_active(roots):
                    idle = 0   # con dang tai -> cho video moi, chua ket thuc
                    print(f"[{time.strftime('%H:%M:%S')}] het video chua transcribe, nhung con dang tai -> cho...", flush=True)
                    time.sleep(C.WATCH_INTERVAL); continue
                idle += 1
                if idle >= a.idle_rounds:
                    break
                time.sleep(C.WATCH_INTERVAL); continue
            idle = 0
            print(f"[{time.strftime('%H:%M:%S')}] con {len(todo)} video can transcribe", flush=True)
            for v in todo:
                rel = v
                try: rel = v.relative_to(C.BASE)
                except Exception: pass
                print(f"   -> {rel}", flush=True)
                status, detail = T.transcribe_or_skip(v)
                if status == "ok":
                    total_done += 1
                elif status in ("noaudio", "skip"):
                    total_skip += 1
                    print(f"      [bo qua] {detail}", flush=True)
                else:  # retry: loi tam -> de lan quet sau, KHONG danh dau
                    total_retry += 1
                    fails[str(v)] = detail
                    print(f"      [loi tam, se thu lai] {detail}", flush=True)
    except KeyboardInterrupt:
        print("\n[Dung boi nguoi dung] - chay lai se tiep tuc.\n")

    msg = f"Transcribe xong: {total_done} video"
    if total_skip: msg += f", {total_skip} bo qua (khong audio/hong)"
    if total_retry: msg += f", {total_retry} loi tam"
    print(f"\n=== {msg} ===")
    if fails:
        print("Video loi tam (se thu lai lan sau):")
        for vp, d in fails.items():
            print(f"  - {vp}\n      {d}")
    # Chi bao khi THUC SU co lam viec (tranh lam phien moi lan logon sau khi da xong het)
    if not a.no_notify and (total_done or total_skip or total_retry):
        notify("Skool Downloader - Transcribe", msg,
               level=("error" if total_retry else "info"))
    return 0 if not total_retry else 1

if __name__ == "__main__":
    sys.exit(main())
