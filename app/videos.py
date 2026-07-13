import os, sys, time, subprocess, threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import common as K
import config as C

_PRINT_LOCK = threading.Lock()


def _plog(*args, **kwargs):
    """Print an toan khi parallel workers."""
    with _PRINT_LOCK:
        print(*args, **kwargs)
        sys.stdout.flush()

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

def _run_ytdlp(url, folder, quiet=False):
    """Chay yt-dlp. quiet=True: khong stream live (parallel). Tra ve (rc, tail_text)."""
    try:
        proc = subprocess.Popen(ytdlp_cmd(url, folder), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1)
    except Exception as e:
        return -1, f"[loi goi yt-dlp] {e}"
    tail = deque(maxlen=80)
    for line in proc.stdout:
        if not quiet:
            with _PRINT_LOCK:
                sys.stdout.write(line)
                sys.stdout.flush()
        tail.append(line)
    proc.wait()
    return proc.returncode, "".join(tail)

def download(url, folder, quiet=False):
    """Tra ve (ok: bool, reason: (ma, mo ta, fix) | None)."""
    folder.mkdir(parents=True, exist_ok=True)
    last = ("unknown", "Loi khong xac dinh", "Chay lai")
    for attempt in range(1, C.MAX_TRIES + 1):
        K.wait_online()
        rc, tail = _run_ytdlp(url, folder, quiet=quiet)
        if rc == 0 and done_file(folder):
            return True, None
        last = classify(tail, url)
        if last[0] not in RECOVER:
            _plog(f"   [{last[1]}] -> {last[2]}")
            break
        if attempt < C.MAX_TRIES:
            _plog(f"   [thu lai {attempt}/{C.MAX_TRIES}] {last[1]}; nghi {C.RETRY_WAIT}s...")
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
    workers = max(1, min(int(getattr(C, "VIDEO_WORKERS", 1) or 1), 4))
    print(f"Tong video luot nay: {total}" + (f"  · workers={workers}" if workers > 1 else "") + "\n")
    _warn_expired_tokens(plan)

    # gop danh sach viec (Sprint E parallel)
    jobs = []  # (folder, url, chap_name)
    miss = 0
    for chap, lessons, ct in plan:
        if chap is None:
            n = sum(1 for _, x in lessons if passes(x.get("url")))
            miss += n
            print(f"[!] khong khop folder '{ct}' -> bo {n}\n")
            continue
        for folder, node in lessons:
            url = node.get("url")
            if not url or not passes(url) or not lesson_ok(folder):
                continue
            jobs.append((folder, url, chap.name))

    total_jobs = len(jobs)
    idx = tai = skip = loi = 0
    fails = []   # (folder, ma, mo ta, fix)
    adaptive = bool(getattr(C, "ADAPTIVE_WORKERS", True))
    t0 = time.time()
    bytes_done = [0]
    rate_hits = [0]
    cur_workers = [workers]
    progress_path = Path(C.ROOT) / "_download_progress.json"

    def _eta_line(n, total, extra=""):
        """Sprint K: ETA + toc do bai/phut."""
        elapsed = max(0.001, time.time() - t0)
        rate = n / elapsed  # jobs/sec
        left = max(0, total - n)
        eta_s = int(left / rate) if rate > 0 else 0
        if eta_s >= 3600:
            eta = f"{eta_s // 3600}h{(eta_s % 3600) // 60}m"
        elif eta_s >= 60:
            eta = f"{eta_s // 60}m{eta_s % 60}s"
        else:
            eta = f"{eta_s}s"
        jpm = rate * 60
        mb = bytes_done[0] / (1024 * 1024)
        return f"ETA~{eta} · {jpm:.1f} bai/phut · {mb:.1f}MB{extra}"

    def _write_progress(n, total, status="running", workers_now=1):
        try:
            payload = {
                "status": status,
                "done": n, "total": total,
                "tai": tai, "skip": skip, "loi": loi,
                "workers": workers_now,
                "eta": _eta_line(n, total),
                "elapsed_s": int(time.time() - t0),
                "bytes": bytes_done[0],
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            progress_path.write_text(
                __import__("json").dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _one(item, quiet=True):
        folder, url, chap_name = item
        host = url.split("/")[2] if "://" in url else url[:24]
        if done_file(folder):
            return ("skip", folder, chap_name, host, None, 0)
        if C.DRY_RUN:
            return ("dry", folder, chap_name, host, None, 0)
        ok, reason = download(url, folder, quiet=quiet)
        sz = 0
        if ok:
            try:
                for ext in C.VIDEXT:
                    p = folder / ("video" + ext)
                    if p.exists():
                        sz = p.stat().st_size
                        break
            except OSError:
                pass
            return ("ok", folder, chap_name, host, None, sz)
        return ("fail", folder, chap_name, host, reason, 0)

    def _handle_result(status, folder, chap_name, host, reason, sz, n, total_jobs, workers_now):
        nonlocal tai, skip, loi
        tag = folder.name if hasattr(folder, "name") else str(folder)
        pct = round(n * 100 / total_jobs, 1) if total_jobs else 0
        eta = _eta_line(n, total_jobs, f" · w={workers_now}" if workers_now > 1 else "")
        if status == "skip":
            skip += 1
            _plog(f"[{n}/{total_jobs} = {pct}%] skip  {tag}  | {eta}")
        elif status == "dry":
            _plog(f"[{n}/{total_jobs} = {pct}%] dry   {tag}")
        elif status == "ok":
            tai += 1
            bytes_done[0] += sz or 0
            _plog(f"[{n}/{total_jobs} = {pct}%] OK    {tag}  <{host}>  | {eta}")
        else:
            loi += 1
            ma, mo, fix = reason or ("unknown", "?", "?")
            fails.append((str(folder), ma, mo, fix))
            _plog(f"[{n}/{total_jobs} = {pct}%] FAIL  {tag}  {mo}  | {eta}")
            # Sprint J: adaptive — ha workers khi rate-limit
            if adaptive and ma == "rate":
                rate_hits[0] += 1
                if rate_hits[0] >= 2 and cur_workers[0] > 1:
                    cur_workers[0] = max(1, cur_workers[0] - 1)
                    rate_hits[0] = 0
                    _plog(f"!! Adaptive: rate-limit x2 → workers={cur_workers[0]} (nghi 15s)")
                    time.sleep(15)
            elif ma != "rate":
                rate_hits[0] = 0
        _write_progress(n, total_jobs, workers_now=workers_now)

    try:
        if workers <= 1:
            last_chap = None
            for folder, url, chap_name in jobs:
                if chap_name != last_chap:
                    print(f"=== [{chap_name}] ===")
                    last_chap = chap_name
                host = url.split("/")[2] if "://" in url else url[:24]
                print(f"→ {folder.name}  <{host}>", flush=True)
                status, _fd, _ch, _host, reason, sz = _one((folder, url, chap_name), quiet=False)
                idx += 1
                _handle_result(status, folder, chap_name, host, reason, sz, idx, total_jobs, 1)
            if last_chap:
                print()
        else:
            # Sprint E+J: parallel theo lo, adaptive workers
            adaptive_on = "adaptive" if adaptive else "fixed"
            print(f">> Parallel download workers={workers} ({adaptive_on}, log gon + ETA)\n")
            pending = list(jobs)
            n_done = 0
            while pending:
                w = cur_workers[0]
                batch = pending[:w]
                pending = pending[w:]
                with ThreadPoolExecutor(max_workers=w) as pool:
                    futs = {pool.submit(_one, j, True): j for j in batch}
                    for fut in as_completed(futs):
                        try:
                            status, folder, chap_name, host, reason, sz = fut.result()
                        except Exception as e:
                            j = futs[fut]
                            loi += 1
                            fails.append((str(j[0]), "unknown", str(e), "Chay lai"))
                            n_done += 1
                            _plog(f"[ERR] {j[0].name}: {e}")
                            continue
                        n_done += 1
                        _handle_result(status, folder, chap_name, host, reason, sz,
                                       n_done, total_jobs, w)
                        # neu adaptive ha workers, phan con lai cua batch van chay xong
            idx = n_done
    except KeyboardInterrupt:
        print("\n[Dung] - chay lai se resume.\n")
        _write_progress(idx, total_jobs, status="stopped", workers_now=cur_workers[0])

    final_w = cur_workers[0]
    _write_progress(idx or total_jobs, total_jobs, status="done", workers_now=final_w)
    print(f"--- VIDEO: tai={tai} skip={skip} loi={loi} folder-thieu={miss} "
          f"({idx or total_jobs}/{total_jobs or total}) workers={final_w}"
          f"{' (adaptive)' if adaptive and final_w != workers else ''} ---")
    print(f"    {_eta_line(idx or total_jobs, total_jobs or 1)} · elapsed={int(time.time()-t0)}s")
    if fails:
        groups = {}
        for folder, ma, mo, fix in fails:
            groups.setdefault((ma, mo, fix), []).append(folder)
        print(f"\n>> {len(fails)} bai THAT BAI, theo nguyen nhan:")
        for (ma, mo, fix), folders in sorted(groups.items(), key=lambda x: -len(x[1])):
            print(f"\n  [{mo}]  x{len(folders)}")
            print(f"     -> Can lam: {fix}")
            for x in folders[:30]:
                print(f"     - {x}")
            if len(folders) > 30:
                print(f"     ... va {len(folders)-30} bai nua")
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
        try:
            p = Path(C.ROOT) / "video_fails.json"
            if p.exists():
                p.unlink()
                print(">> Da xoa video_fails.json (sach fail)")
        except Exception:
            pass
    print()
    return fails
