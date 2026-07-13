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
import argparse, time
import config as C
import common as K
import folders, extras, videos, transcribe, audit, preflight

STEPS = {"folders": folders.run, "extras": extras.run, "videos": videos.run,
         "transcribe": transcribe.run, "audit": audit.run}

NATIVE_HOST = "stream.video.skool.com"
# Loi CO THE thu lai tu dong (mang chap chon / YouTube chan bot / loi la). Cac loi
# khac (token het han, video rieng tu...) can nguoi can thiep -> khong loop vo ich.
RECOVERABLE = {"network", "unknown", "bot", "rate"}

def run_videos_two_pass():
    """Native (token 24h, de het han) tai truoc, roi Loom/YouTube. Tra ve list fails."""
    orig = C.ONLY_HOSTS
    if orig:
        return videos.run() or []
    print(">> Luot 1: video NATIVE (token 24h) truoc")
    C.ONLY_HOSTS = [NATIVE_HOST]; f1 = videos.run() or []
    print(">> Luot 2: Loom + YouTube")
    C.ONLY_HOSTS = []; f2 = videos.run() or []
    C.ONLY_HOSTS = orig
    return f1 + f2

def run_videos(until_clean=False, rounds=5, wait=300):
    """Tai video. Neu until_clean: lap lai cho den khi khong con bai NAO co the thu lai
       (vd YouTube bi gioi han toc do -> cho roi tai tiep), toi da `rounds` vong."""
    fails = run_videos_two_pass()
    if not until_clean:
        return fails
    rnd = 1
    while rnd < rounds:
        recover = [f for f in fails if f[1] in RECOVERABLE]
        if not recover:
            print(f">> SACH: khong con bai nao can thu lai (sau {rnd} vong).")
            return fails
        print(f">> Con {len(recover)} bai co the thu lai. Nghi {wait}s roi thu vong {rnd+1}/{rounds}...")
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            print(">> Da dung vong thu lai."); return fails
        fails = run_videos_two_pass()
        rnd += 1
    left = [f for f in fails if f[1] in RECOVERABLE]
    if left:
        print(f">> Het {rounds} vong, van con {len(left)} bai chua tai duoc (thu lai sau).")
    return fails

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
    ap.add_argument("--version", action="store_true", help="In phien ban roi thoat.")
    ap.add_argument("--course", help="Ten khoa duoi BASE/courses/. Bo trong = dung BASE/SkoolCourse (cu).")
    ap.add_argument("--root", help="Override truc tiep thu muc lam viec (thay cho --course).")
    ap.add_argument("--only", choices=list(STEPS), help="Chi chay 1 buoc.")
    ap.add_argument("--transcribe", action="store_true", help="Chay Whisper transcribe o cuoi.")
    ap.add_argument("--dry-run", action="store_true", help="Video chi liet ke, khong tai.")
    ap.add_argument("--list-courses", action="store_true", help="Liet ke cac khoa roi thoat.")
    ap.add_argument("--skip-preflight", action="store_true", help="Bo qua kiem tra moi truong dau.")
    ap.add_argument("--until-clean", action="store_true", help="Tu thu lai cho den khi tai du (cho neu bi gioi han).")
    ap.add_argument("--rounds", type=int, default=5, help="So vong toi da khi --until-clean (mac dinh 5).")
    ap.add_argument("--round-wait", type=int, default=300, help="Giay nghi giua cac vong --until-clean (mac dinh 300).")
    ap.add_argument("--native-only", action="store_true", help="Chi tai video native Skool (de cuu bai het token).")
    ap.add_argument("--chapter", help="Chi tai 1 chuong (ten chuong da san). Dung cho GUI tai theo chuong.")
    ap.add_argument("--chapters", help="Nhieu chuong (ten san, cach bang ||). Sprint B chapter delta.")
    ap.add_argument("--lesson", help="Chi tai 1 bai (duong dan tuong doi vs course root).")
    ap.add_argument("--retry-failed", action="store_true",
                    help="Chi tai lai bai co trong video_fails.json (fail-driven).")
    ap.add_argument("--fail-codes", help="Loc code fail, vd: rate,network,token (mac dinh: tat ca).")
    ap.add_argument("--missing-only", action="store_true",
                    help="Chi tai bai chua co video (diff-only).")
    ap.add_argument("--smart-update", action="store_true",
                    help="Smart update: missing-only + uu tien chuong moi tu _update_diff.json.")
    ap.add_argument("--index", action="store_true", help="Sau pipeline: build RAG index (catalog+tfidf).")
    ap.add_argument("--no-index", action="store_true", help="Tat auto index sau pipeline.")
    # multi-course queue (S2) — uy thac queue_engine
    ap.add_argument("--queue", help="Them nhieu khoa vao hang doi (ten cach nhau bang dau phay) roi chay.")
    ap.add_argument("--queue-add", help="Chi them vao hang doi, khong chay (ten cach nhau bang dau phay).")
    ap.add_argument("--queue-run", action="store_true", help="Chay het job dang queued.")
    ap.add_argument("--queue-status", action="store_true", help="In trang thai hang doi.")
    # override config nhanh
    ap.add_argument("--js-runtime", help="JS runtime cho yt-dlp (node/deno). '' de tat.")
    ap.add_argument("--cookies-file", help="Duong dan cookies.txt cho yt-dlp.")
    ap.add_argument("--cookies-browser", help="Lay cookies tu trinh duyet (firefox).")
    a = ap.parse_args()

    if a.version:
        try:
            import version as V
            print(V.version_string())
        except Exception:
            print("Skool Archiver")
        return

    if a.list_courses:
        list_courses(); return

    # ---- hang doi multi-course ----
    if a.queue_status or a.queue_run or a.queue or a.queue_add:
        import queue_engine as QE
        names = []
        raw = a.queue or a.queue_add or ""
        if raw.strip():
            names = [x.strip() for x in raw.split(",") if x.strip()]
        if names:
            courses = [None if n.lower() in ("skoolcourse", "legacy") else n for n in names]
            QE.add_jobs(courses, kind="full", until_clean=bool(a.until_clean or a.queue))
            print(f"Da them {len(courses)} job vao queue.")
        if a.queue_status or (not a.queue and not a.queue_run and a.queue_add):
            QE.print_status()
        if a.queue or a.queue_run:
            def _ev(ev):
                t = ev.get("type")
                if t == "start":
                    print(f"\n>>> {ev['job'].get('label')}")
                elif t == "log":
                    print(ev.get("line") or "")
                elif t == "end":
                    print(f"<<< {ev['job'].get('status')} rc={ev['job'].get('returncode')}")
            runner = QE.QueueRunner(on_event=_ev)
            n = runner.run_all()
            print(f"=== Queue xong ({n} job) ===")
        return

    if a.root:        C.set_root(a.root)
    elif a.course:    C.set_course(a.course)
    if a.dry_run:               C.DRY_RUN = True
    if a.js_runtime is not None: C.JS_RUNTIME = a.js_runtime
    if a.cookies_file:          C.YT_COOKIES_FILE = a.cookies_file
    if a.cookies_browser:       C.YT_COOKIES_BROWSER = a.cookies_browser
    if a.native_only:           C.ONLY_HOSTS = [NATIVE_HOST]
    if a.chapter:               C.ONLY_CHAPTER = a.chapter
    if a.chapters:
        parts = [x.strip() for x in a.chapters.split("||") if x.strip()]
        if parts:
            C.ONLY_CHAPTERS = set(parts)
    if a.lesson:                C.ONLY_LESSON = a.lesson
    if a.retry_failed:
        C.ONLY_FAILED = True
        if a.fail_codes:
            C.FAIL_CODES = {x.strip().lower() for x in a.fail_codes.split(",") if x.strip()}
    if a.missing_only:
        C.ONLY_MISSING = True
    if a.smart_update:
        try:
            import updates as U
            plan = U.apply_smart_update_flags(C.ROOT, prefer_new_chapters=True)
            print(f"(smart-update) {plan.get('summary')}")
            if plan.get("chapter_filter"):
                print(f"  chapter_filter: {plan['chapter_filter']}")
        except Exception as e:
            print(f"[smart-update] fallback missing-only: {e}")
            C.ONLY_MISSING = True
    do_index = bool(a.index) or (getattr(C, "AUTO_INDEX", True) and not a.no_index and not a.only)

    print(f"=== KHOA: {C.COURSE or C.ROOT.name}  ({C.ROOT}) ===\n")

    if a.only:
        if a.only == "videos":
            if a.chapter or a.chapters or a.lesson or a.retry_failed or a.missing_only or a.smart_update:
                folders.run()   # bao dam co folder truoc khi tai chon loc
            run_videos(until_clean=a.until_clean, rounds=a.rounds, wait=a.round_wait)
        else:
            STEPS[a.only]()
        # --only: chi index khi user goi --index (AUTO_INDEX chi full pipeline)
        if a.index:
            _maybe_index()
        return

    if not a.skip_preflight:
        if preflight.run_checks(check_json=True) > 0:
            print("Dung lai do preflight co loi FAIL. Sua roi chay lai (hoac --skip-preflight de bo qua).")
            return

    folders.run()
    extras.run()                 # resource het han 8h -> lam som
    run_videos(until_clean=a.until_clean, rounds=a.rounds, wait=a.round_wait)  # native 24h truoc, roi loom/youtube
    if a.transcribe: transcribe.run()
    audit.run()
    if do_index or a.index:
        _maybe_index()
    print("=== HOAN TAT PIPELINE ===")


def _maybe_index():
    """Build RAG catalog + TF-IDF (Sprint A incremental knowledge)."""
    try:
        from rag.index import build_catalog
        print("\n=== RAG INDEX ===")
        build_catalog(C.ROOT)
    except Exception as e:
        print(f"[index] bo qua: {e}")

if __name__ == "__main__":
    main()
