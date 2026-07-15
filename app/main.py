#!/usr/bin/env python3
"""
Skool Downloader - pipeline luu tru khoa hoc Skool bang 1 lenh.

  python main.py --course "AI Automations by Jack"            # folders->extras->video->audit
  python main.py --course "AI Automations by Jack"            # folders->extras->video->transcribe(auto)->audit
  python main.py --course "X" --no-transcribe                 # tat Whisper (mac dinh AUTO_TRANSCRIBE=True)
  python main.py --course "X" --only videos                   # tai video (+ auto transcript neu bat)
  python main.py --course "X" --only transcribe               # chi Whisper + all transcript.txt
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
    ap = argparse.ArgumentParser(description="Skool course downloader")
    ap.add_argument("--version", action="store_true", help="In phien ban roi thoat.")
    ap.add_argument("--course", help="Ten khoa duoi BASE/courses/. Bo trong = dung BASE/SkoolCourse (cu).")
    ap.add_argument("--root", help="Override truc tiep thu muc lam viec (thay cho --course).")
    ap.add_argument("--only", choices=list(STEPS), help="Chi chay 1 buoc.")
    ap.add_argument(
        "--transcribe",
        action="store_true",
        help="Ep chay Whisper (mac dinh da AUTO_TRANSCRIBE=True).",
    )
    ap.add_argument(
        "--no-transcribe",
        action="store_true",
        help="Tat Whisper / all transcript.txt (override AUTO_TRANSCRIBE).",
    )
    ap.add_argument(
        "--lesson-summary",
        action="store_true",
        help="Ep chay summary.vi.md tung bai (LLM VI) sau pipeline.",
    )
    ap.add_argument(
        "--no-lesson-summary",
        action="store_true",
        help="Tat auto lesson summary (override AUTO_LESSON_SUMMARY).",
    )
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
    ap.add_argument("--workers", type=int, default=None,
                    help="Sprint E: so bai video tai song song (1-4). Mac dinh VIDEO_WORKERS.")
    ap.add_argument("--no-adaptive", action="store_true",
                    help="Sprint J: tat adaptive workers (khong ha workers khi 429).")
    ap.add_argument("--notify", action="store_true",
                    help="Sprint F: toast he thong sau khi xong (mac dinh bat neu NOTIFY_ON_DONE).")
    ap.add_argument("--no-notify", action="store_true", help="Tat toast.")
    ap.add_argument("--resume", action="store_true",
                    help="Sprint G: dung last_course trong .settings.json.")
    ap.add_argument("--index", action="store_true", help="Sau pipeline: build RAG index (catalog+tfidf).")
    ap.add_argument("--no-index", action="store_true", help="Tat auto index sau pipeline.")
    ap.add_argument("--smart-batch", action="store_true",
                    help="Sprint L: enqueue smart-update moi khoa con thieu roi (tuy chon) chay.")
    ap.add_argument("--smart-batch-run", action="store_true",
                    help="Voi --smart-batch: chay queue ngay.")
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
            print("Skool Downloader")
        return

    if a.list_courses:
        list_courses(); return

    # Sprint L: smart-batch multi-course
    if a.smart_batch:
        import updates as U
        created, batch = U.enqueue_smart_batch(until_clean=True)
        print(f"Smart batch: {len(created)} job / {len(batch)} khoa")
        for j in created:
            print(f"  + {j.get('label')}")
        if a.smart_batch_run and created:
            import queue_engine as QE
            n = QE.QueueRunner().run_all()
            print(f"=== Queue xong ({n} job) ===")
        return

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

    if a.resume and not a.course and not a.root:
        try:
            import session_state as SS
            lc, _ = SS.get_last_course()
            if lc:
                print(f"(resume) last_course={lc}")
                C.set_course(lc)
            else:
                print("(resume) chua co last_course — dung SkoolCourse")
        except Exception as e:
            print(f"[resume] {e}")
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
    if a.workers is not None:
        C.VIDEO_WORKERS = max(1, min(int(a.workers), 4))
    if a.no_adaptive:
        C.ADAPTIVE_WORKERS = False
    do_index = bool(a.index) or (getattr(C, "AUTO_INDEX", True) and not a.no_index and not a.only)
    do_notify = bool(a.notify) or (getattr(C, "NOTIFY_ON_DONE", True) and not a.no_notify)
    # Mac dinh tu dong plain-text transcript (faster-whisper, auto-detect ngon ngu)
    # Settings auto_transcribe > config AUTO_TRANSCRIBE; --no-transcribe / --transcribe override
    if hasattr(C, "get_auto_transcribe"):
        auto_ts = bool(C.get_auto_transcribe())
    else:
        auto_ts = bool(getattr(C, "AUTO_TRANSCRIBE", True))
    if a.no_transcribe:
        do_transcribe = False
    elif a.transcribe:
        do_transcribe = True
    else:
        do_transcribe = auto_ts

    if hasattr(C, "get_auto_lesson_summary"):
        auto_sum = bool(C.get_auto_lesson_summary())
    else:
        auto_sum = bool(getattr(C, "AUTO_LESSON_SUMMARY", True))
    if a.no_lesson_summary:
        do_lesson_summary = False
    elif a.lesson_summary:
        do_lesson_summary = True
    else:
        do_lesson_summary = auto_sum

    # ghi last_course (Sprint G)
    try:
        import session_state as SS
        SS.set_last_course(C.COURSE)
    except Exception:
        pass

    print(f"=== KHOA: {C.COURSE or C.ROOT.name}  ({C.ROOT}) ===\n")
    video_fails = None

    if a.only:
        if a.only == "videos":
            if a.chapter or a.chapters or a.lesson or a.retry_failed or a.missing_only or a.smart_update:
                folders.run()   # bao dam co folder truoc khi tai chon loc
            video_fails = run_videos(until_clean=a.until_clean, rounds=a.rounds, wait=a.round_wait)
            # Mac dinh: transcript plain text ngay sau khi tai (va ghep all transcript.txt)
            if do_transcribe and not a.dry_run:
                print("\n(auto) TRANSCRIBE sau videos…")
                transcribe.run()
            if do_lesson_summary and not a.dry_run:
                _maybe_lesson_summary()
        elif a.only == "transcribe":
            STEPS["transcribe"]()
            if do_lesson_summary and not a.dry_run:
                _maybe_lesson_summary()
        else:
            STEPS[a.only]()
        # --only: chi index khi user goi --index (AUTO_INDEX chi full pipeline)
        if a.index:
            _maybe_index()
        if do_notify and a.only in ("videos", None):
            _maybe_notify(video_fails)
        return

    if not a.skip_preflight:
        if preflight.run_checks(check_json=True) > 0:
            print("Dung lai do preflight co loi FAIL. Sua roi chay lai (hoac --skip-preflight de bo qua).")
            return

    folders.run()
    extras.run()                 # resource het han 8h -> lam som
    video_fails = run_videos(until_clean=a.until_clean, rounds=a.rounds, wait=a.round_wait)
    if do_transcribe and not a.dry_run:
        print("\n(auto) TRANSCRIBE (plain text + all transcript.txt)…")
        transcribe.run()
    if do_lesson_summary and not a.dry_run:
        _maybe_lesson_summary()
    audit.run()
    if do_index or a.index:
        _maybe_index()
    print("=== HOAN TAT PIPELINE ===")
    if do_notify:
        _maybe_notify(video_fails)


def _maybe_index():
    """Build RAG catalog + TF-IDF (Sprint A incremental knowledge)."""
    try:
        from rag.index import build_catalog
        print("\n=== RAG INDEX ===")
        build_catalog(C.ROOT)
    except Exception as e:
        print(f"[index] bo qua: {e}")


def _maybe_lesson_summary():
    """Summary.vi.md tung bai (LLM VI) — mac dinh DeepSeek, fallback Gemini."""
    try:
        import lesson_summary as LS
        print("\n(auto) LESSON SUMMARY (VI)…")
        LS.run(C.ROOT, force=False, missing_only=True, combine=True)
    except Exception as e:
        print(f"[lesson-summary] bo qua: {e}")


def _maybe_notify(fails):
    """Sprint F: toast khi xong / sach fail."""
    try:
        import notify as N
        # fails la list tuple (folder, code, msg, fix) tu videos.run
        n = 0 if fails is None else len(fails)
        N.notify_pipeline_result(C.COURSE or C.ROOT.name, fails=[] if fails is None else fails)
        if n == 0:
            print("(notify) sach fail / hoan tat")
    except Exception as e:
        print(f"[notify] {e}")

if __name__ == "__main__":
    main()
