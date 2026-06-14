#!/usr/bin/env python3
"""
Skool Archiver - pipeline luu tru khoa hoc Skool bang 1 lenh.

  python main.py --course "AI Automations by Jack"            # folders->extras->video->audit
  python main.py --course "AI Automations by Jack" --transcribe   # + Whisper o cuoi
  python main.py --course "X" --only videos                   # chay 1 buoc: folders|extras|videos|transcribe|audit
  python main.py --course "X" --dry-run                       # video chi liet ke, khong tai
  python main.py --list-courses                               # liet ke cac khoa duoi BASE/courses

Khong truyen --course  ->  dung layout cu BASE/SkoolCourse (khoa da tai).
Truoc khi chay: dump JSON bang extractor.js (xem README) va dat vao thu muc khoa.
Cau hinh mac dinh o config.py; cac co duoi day de override nhanh.
"""
import argparse
import config as C
import common as K
import folders, extras, videos, transcribe, audit, preflight

STEPS = {"folders": folders.run, "extras": extras.run, "videos": videos.run,
         "transcribe": transcribe.run, "audit": audit.run}

def run_videos_two_pass():
    """Native (token 24h, de het han) tai truoc, roi Loom/YouTube."""
    orig = C.ONLY_HOSTS
    if orig:
        videos.run(); return
    print(">> Luot 1: video NATIVE (token 24h) truoc")
    C.ONLY_HOSTS = ["stream.video.skool.com"]; videos.run()
    print(">> Luot 2: Loom + YouTube")
    C.ONLY_HOSTS = []; videos.run()
    C.ONLY_HOSTS = orig

def list_courses():
    base = C.BASE / "courses"
    if not base.exists():
        print(f"Chua co thu muc {base}"); return
    items = sorted(p.name for p in base.iterdir() if p.is_dir())
    print(f"Cac khoa duoi {base}:")
    for n in items: print("   -", n)
    if not items: print("   (trong)")

def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Skool course archiver")
    ap.add_argument("--course", help="Ten khoa duoi BASE/courses/. Bo trong = dung BASE/SkoolCourse (cu).")
    ap.add_argument("--root", help="Override truc tiep thu muc lam viec (thay cho --course).")
    ap.add_argument("--only", choices=list(STEPS), help="Chi chay 1 buoc.")
    ap.add_argument("--transcribe", action="store_true", help="Chay Whisper transcribe o cuoi.")
    ap.add_argument("--dry-run", action="store_true", help="Video chi liet ke, khong tai.")
    ap.add_argument("--list-courses", action="store_true", help="Liet ke cac khoa roi thoat.")
    ap.add_argument("--skip-preflight", action="store_true", help="Bo qua kiem tra moi truong dau.")
    # override config nhanh
    ap.add_argument("--js-runtime", help="JS runtime cho yt-dlp (node/deno). '' de tat.")
    ap.add_argument("--cookies-file", help="Duong dan cookies.txt cho yt-dlp.")
    ap.add_argument("--cookies-browser", help="Lay cookies tu trinh duyet (firefox).")
    a = ap.parse_args()

    if a.list_courses:
        list_courses(); return

    if a.root:        C.set_root(a.root)
    elif a.course:    C.set_course(a.course)
    if a.dry_run:               C.DRY_RUN = True
    if a.js_runtime is not None: C.JS_RUNTIME = a.js_runtime
    if a.cookies_file:          C.YT_COOKIES_FILE = a.cookies_file
    if a.cookies_browser:       C.YT_COOKIES_BROWSER = a.cookies_browser

    print(f"=== KHOA: {C.COURSE or C.ROOT.name}  ({C.ROOT}) ===\n")

    if a.only:
        (run_videos_two_pass if a.only == "videos" else STEPS[a.only])()
        return

    if not a.skip_preflight:
        if preflight.run_checks(check_json=True) > 0:
            print("Dung lai do preflight co loi FAIL. Sua roi chay lai (hoac --skip-preflight de bo qua).")
            return

    folders.run()
    extras.run()                 # resource het han 8h -> lam som
    run_videos_two_pass()        # native 24h truoc, roi loom/youtube
    if a.transcribe: transcribe.run()
    audit.run()
    print("=== HOAN TAT PIPELINE ===")

if __name__ == "__main__":
    main()
