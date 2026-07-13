import os, sys, time, subprocess
from collections import deque
from pathlib import Path
import common as K
import config as C

def passes(url):
    return bool(url) and (not C.ONLY_HOSTS or any(h in url for h in C.ONLY_HOSTS))

def chap_ok(ct):
    """Loc 1 chuong (ONLY_CHAPTER) hoac nhieu chuong (ONLY_CHAPTERS — Sprint B)."""
    if C.ONLY_CHAPTER and ct != C.ONLY_CHAPTER:
        return False
    chapters = getattr(C, "ONLY_CHAPTERS", None)
    if chapters:
        # chap titles trong plan da san (K.san)
        want = {str(x).strip().lower() for x in chapters if str(x).strip()}
        if not want:
            return True
        return (ct or "").strip().lower() in want or (ct or "") in chapters
    return True

def _norm_path(p):
    try:
        return str(Path(p).resolve()).replace("\\", "/").lower()
    except Exception:
        return str(p).replace("\\", "/").lower()


def failed_folder_set(root=None):
    """Tap folder (absolute norm) tu video_fails.json, loc theo C.FAIL_CODES neu co."""
    try:
        import cleanup as CL
        fails = CL.load_fails(root or C.ROOT)
    except Exception:
        fails = []
    codes = C.FAIL_CODES
    if codes:
        codes = {str(c).lower() for c in codes}
        fails = [f for f in fails if (f.get("code") or "").lower() in codes]
    out = set()
    for f in fails:
        fp = f.get("folder") or ""
        if not fp:
            continue
        out.add(_norm_path(fp))
        # them basename path de match linh hoat
        try:
            out.add(Path(fp).name.lower())
        except Exception:
            pass
    return out


_FAILED_CACHE = None


def _failed_set():
    global _FAILED_CACHE
    if not C.ONLY_FAILED:
        return None
    if _FAILED_CACHE is None:
        _FAILED_CACHE = failed_folder_set()
    return _FAILED_CACHE


def reset_failed_cache():
    global _FAILED_CACHE
    _FAILED_CACHE = None


def in_failed_set(folder, fset):
    if not fset:
        return False
    n = _norm_path(folder)
    if n in fset:
        return True
    # match neu fail path la prefix/suffix
    for f in fset:
        if not f:
            continue
        if n.endswith("/" + f) or n.endswith(f) or f.endswith(n):
            return True
        try:
            if Path(n).name.lower() == Path(f).name.lower() and Path(n).name:
                # ten folder bai trung (yeu) — chi khi cung parent name
                if Path(n).parent.name.lower() == Path(f).parent.name.lower():
                    return True
        except Exception:
            pass
    return False


def lesson_ok(folder):
    """So khop duong dan bai — ONLY_FAILED / ONLY_MISSING / ONLY_LESSON."""
    if C.ONLY_FAILED:
        fset = _failed_set()
        if not fset:
            return False
        if not in_failed_set(folder, fset):
            return False
    if getattr(C, "ONLY_MISSING", False):
        # chi bai chua co video (diff-only / smart update)
        if done_file(folder):
            return False
    if not C.ONLY_LESSON:
        return True
    only = str(C.ONLY_LESSON).replace("\\", "/").strip("/").lower()
    try:
        rel = Path(folder).resolve().relative_to(Path(C.ROOT).resolve())
        got = str(rel).replace("\\", "/").strip("/").lower()
        return got == only
    except Exception:
        rel = str(folder).replace(str(C.ROOT) + os.sep, "").replace(str(C.ROOT) + "/", "")
        return rel.replace("\\", "/").strip("/").lower() == only

def count_urls(nodes):
    c = 0
    for n in nodes:
        if n.get("url"): c += 1
        c += count_urls(n.get("children") or [])
    return c

def done_file(folder):
    for ext in C.VIDEXT:
        p = folder / ("video" + ext)
        try:
            if p.exists() and p.stat().st_size > 0: return True
        except OSError: pass
    return False

FFDIR = K.ffmpeg_dir()

def ytdlp_cmd(url, folder):
    cmd = [sys.executable, "-m", "yt_dlp", "-o", str(folder / "video.%(ext)s"),
           "--no-playlist", "--continue", "--no-overwrites",
           "--retries", "10", "--fragment-retries", "20", "--retry-sleep", "5",
           "--socket-timeout", "30", "--newline"]
    if FFDIR: cmd += ["--ffmpeg-location", FFDIR]
    if C.JS_RUNTIME: cmd += ["--js-runtimes", C.JS_RUNTIME]   # vuot YouTube bot-check
    if C.YT_COOKIES_FILE and Path(C.YT_COOKIES_FILE).exists():
        cmd += ["--cookies", C.YT_COOKIES_FILE]
    elif C.YT_COOKIES_BROWSER:
        cmd += ["--cookies-from-browser", C.YT_COOKIES_BROWSER]
    cmd.append(url)
    return cmd

# Phan loai loi -> (ma, mo ta, viec can lam).  RECOVER = loi co the retry; con lai dung som.
RECOVER = {"network", "unknown", "rate"}


def classify(text, url):
    t = (text or "").lower()
    host = url.split("/")[2].lower() if "://" in url else ""
    if "403" in t and "forbidden" in t:
        if "skool" in host:
            return ("token", "Token native Skool het han (403)", "Dump lai vid_*.json roi chay: --only videos")
        return ("forbidden", "Bi tu choi truy cap (403)", "Link can dang nhap (--cookies-file) hoac da het han")
    if "429" in t or "too many requests" in t or "rate-limit" in t or "rate limit" in t:
        return ("rate", "Bi gioi han toc do (429)", "Cho 1-5 phut roi chay lai / bat --until-clean")
    if "not a bot" in t or "confirm you" in t or "sign in to confirm" in t:
        return ("bot", "YouTube chan bot (thieu JS runtime)", "Cai Node.js (nodejs.org) -> tu dung --js-runtimes node")
    if "unsupported url" in t or "no video formats" in t or "no media found" in t:
        return ("unsupported", "Host video khong duoc ho tro", "Kiem tra link; yt-dlp chua ho tro host nay")
    if any(k in t for k in ("private video", "video unavailable", "members-only",
                            "been removed", "no longer available", "account associated")):
        return ("unavailable", "Video rieng tu / da go / can quyen", "Khong tai duoc - bo qua hoac xin link khac")
    if any(k in t for k in ("getaddrinfo", "timed out", "timeout", "connection",
                            "unable to download", "temporary failure", "network is unreachable",
                            "connection reset", "broken pipe", "ssl")):
        return ("network", "Loi mang", "Kiem tra ket noi; chay lai se tiep tuc tu cho dang do")
    if "ffmpeg" in t:
        return ("ffmpeg", "Thieu/loi ffmpeg", "Chay setup.ps1 (ffdl install --add-path)")
    return ("unknown", "Loi khong xac dinh", "Xem log o tren; chay lai. Lap lai -> bao ky thuat")

def _run_ytdlp(url, folder):
    """Chay yt-dlp, vua hien live vua giu lai phan duoi (de phan loai loi). Tra ve (rc, tail_text)."""
    try:
        proc = subprocess.Popen(ytdlp_cmd(url, folder), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1)
    except Exception as e:
        return -1, f"[loi goi yt-dlp] {e}"
    tail = deque(maxlen=80)
    for line in proc.stdout:
        sys.stdout.write(line)
        tail.append(line)
    proc.wait()
    return proc.returncode, "".join(tail)

def download(url, folder):
    """Tra ve (ok: bool, reason: (ma, mo ta, fix) | None)."""
    folder.mkdir(parents=True, exist_ok=True)
    last = ("unknown", "Loi khong xac dinh", "Chay lai")
    for attempt in range(1, C.MAX_TRIES + 1):
        K.wait_online()
        rc, tail = _run_ytdlp(url, folder)
        if rc == 0 and done_file(folder):
            return True, None
        last = classify(tail, url)
        if last[0] not in RECOVER:
            print(f"   [{last[1]}] -> {last[2]}", flush=True)
            break
        if attempt < C.MAX_TRIES:
            print(f"   [thu lai {attempt}/{C.MAX_TRIES}] {last[1]}; nghi {C.RETRY_WAIT}s...", flush=True)
            time.sleep(C.RETRY_WAIT)
    return False, last

def _warn_expired_tokens(plan):
    """Canh bao truoc khi tai neu co native JWT da het han (tranh spam 403)."""
    try:
        import progress as P
        now = time.time()
        n = 0
        for chap, lessons, ct in plan:
            if chap is None:
                continue
            for folder, node in lessons:
                url = node.get("url") or ""
                if not url or not passes(url) or not lesson_ok(folder):
                    continue
                if done_file(folder):
                    continue
                if not P.is_native(url):
                    continue
                exp = P.native_token_exp(url)
                if exp is not None and exp < now:
                    n += 1
        if n:
            print(f"!! CANH BAO: {n} bai native co token JWT da het han.")
            print("   Dump lai chuong (GUI: Cuu bai native / Cap nhat) truoc khi tai se hieu qua hon.\n")
        return n
    except Exception:
        return 0


def run():
    reset_failed_cache()
    print(f"=== TAI VIDEO === (ONLY_HOSTS={C.ONLY_HOSTS or 'TAT CA'})")
    if C.ONLY_FAILED:
        fset = _failed_set() or set()
        codes = C.FAIL_CODES or "all"
        print(f"(retry-failed: {len(fset)} folder · codes={codes})")
        if not fset:
            print("Khong co video_fails.json / khong khop code -> bo qua\n")
            return []
    if getattr(C, "ONLY_MISSING", False):
        print("(smart/missing-only: chi bai chua co video)")
    if getattr(C, "ONLY_CHAPTERS", None):
        print(f"(chapters delta: {len(C.ONLY_CHAPTERS)} chuong)")
    chapters = K.load_best(C.VID_PATTERN, count_urls)
    if not chapters: print("Khong co vid_*.json -> bo qua\n"); return []
    plan = []; total = 0
    for ct, f, course in chapters:
        if not chap_ok(ct): continue
        chap = K.find_chapter_folder(ct)
        lessons = K.walk(course.get("children") or [], chap or C.ROOT)
        total += sum(1 for fd, n in lessons if passes(n.get("url")) and lesson_ok(fd))
        plan.append((chap, lessons, ct))
    if C.ONLY_CHAPTER or C.ONLY_LESSON or getattr(C, "ONLY_CHAPTERS", None):
        ch_disp = C.ONLY_CHAPTER or (
            f"{len(C.ONLY_CHAPTERS)} ch." if getattr(C, "ONLY_CHAPTERS", None) else "tat ca"
        )
        print(f"(loc: chuong={ch_disp} bai={C.ONLY_LESSON or 'tat ca'})")
    print(f"Tong video luot nay: {total}\n")
    _warn_expired_tokens(plan)
    idx = tai = skip = loi = miss = 0
    fails = []   # (folder, ma, mo ta, fix)
    try:
        for chap, lessons, ct in plan:
            if chap is None:
                n = sum(1 for _, x in lessons if passes(x.get("url")))
                idx += n; miss += n; print(f"[!] khong khop folder '{ct}' -> bo {n}\n"); continue
            print(f"=== [{chap.name}] ===")
            for folder, node in lessons:
                url = node.get("url")
                if not url or not passes(url) or not lesson_ok(folder): continue
                idx += 1
                pct = round(idx * 100 / total, 1) if total else 0
                host = url.split("/")[2] if "://" in url else url[:24]
                print(f"[{idx}/{total} = {pct}%] {folder.name}  <{host}>", flush=True)
                if done_file(folder): skip += 1; print("   da co -> skip", flush=True); continue
                if C.DRY_RUN: continue
                ok, reason = download(url, folder)
                if ok: tai += 1
                else:
                    loi += 1
                    ma, mo, fix = reason
                    fails.append((str(folder), ma, mo, fix))
                    print(f"   [THAT BAI] {mo}", flush=True)
            print()
    except KeyboardInterrupt:
        print("\n[Dung] - chay lai se resume.\n")

    print(f"--- VIDEO: tai={tai} skip={skip} loi={loi} folder-thieu={miss} ({idx}/{total}) ---")
    if fails:
        # gom theo nguyen nhan -> in cach xu ly 1 lan moi nhom
        groups = {}
        for folder, ma, mo, fix in fails:
            groups.setdefault((ma, mo, fix), []).append(folder)
        print(f"\n>> {len(fails)} bai THAT BAI, theo nguyen nhan:")
        for (ma, mo, fix), folders in sorted(groups.items(), key=lambda x: -len(x[1])):
            print(f"\n  [{mo}]  x{len(folders)}")
            print(f"     -> Can lam: {fix}")
            for x in folders[:30]: print(f"     - {x}")
            if len(folders) > 30: print(f"     ... va {len(folders)-30} bai nua")
        # ghi de GUI / lan chay sau doc
        try:
            import json
            out = Path(C.ROOT) / "video_fails.json"
            payload = [{"folder": f, "code": ma, "message": mo, "fix": fix}
                       for f, ma, mo, fix in fails]
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n>> Chi tiet: {out}")
        except Exception as e:
            print(f"[warn] khong ghi video_fails.json: {e}")
    else:
        # xoa file fails cu neu lan nay sach
        try:
            p = Path(C.ROOT) / "video_fails.json"
            if p.exists():
                p.unlink()
        except Exception:
            pass
    print()
    return fails
