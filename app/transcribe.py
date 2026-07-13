"""Transcribe video -> video.txt + video.srt (dat CUNG folder voi video).
Engine mac dinh: faster-whisper (CTranslate2) - nhanh, nhe RAM. Du phong: openai-whisper.
Dung chung cho: chay 1 lan (run) va watcher (transcribe_file)."""
import os, time, warnings
import common as K
import config as C

_MODEL = None          # cache model da nap
_ENGINE_LOADED = None

def _resolve_device():
    """auto -> cuda neu co GPU NVIDIA (qua CTranslate2), nguoc lai cpu."""
    dev = (C.WHISPER_DEVICE or "auto").lower()
    if dev != "auto":
        return dev
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"

def _fmt_ts(sec):
    if sec < 0: sec = 0
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def load_model():
    """Nap model 1 lan. Tra ve ('faster-whisper', model) hoac ('openai-whisper', model)."""
    global _MODEL, _ENGINE_LOADED
    if _MODEL is not None:
        return _ENGINE_LOADED, _MODEL
    warnings.filterwarnings("ignore")
    engine = (C.WHISPER_ENGINE or "faster-whisper").lower()
    if engine == "faster-whisper":
        from faster_whisper import WhisperModel
        device = _resolve_device()
        compute = C.WHISPER_COMPUTE or ("float16" if device == "cuda" else "int8")
        if device == "cuda" and compute == "int8":
            compute = "float16"
        print(f"   [model] faster-whisper '{C.WHISPER_MODEL}' device={device} compute={compute} (lan dau tai model hoi lau)...", flush=True)
        _MODEL = WhisperModel(C.WHISPER_MODEL, device=device, compute_type=compute)
    else:
        import whisper
        ff = K.ffmpeg_dir()
        if ff: os.environ["PATH"] = ff + os.pathsep + os.environ["PATH"]
        print(f"   [model] openai-whisper '{C.WHISPER_MODEL}' (lan dau tai model hoi lau)...", flush=True)
        _MODEL = whisper.load_model(C.WHISPER_MODEL)
    _ENGINE_LOADED = engine
    return engine, _MODEL

def _write_outputs(video, segments):
    """segments: list of (start, end, text). Ghi .txt + .srt canh video (ghi tam roi doi ten -> an toan)."""
    txt = video.with_suffix(".txt"); srt = video.with_suffix(".srt")
    txt_tmp = video.with_suffix(".txt.part"); srt_tmp = video.with_suffix(".srt.part")
    body = "\n".join(t.strip() for _, _, t in segments if t.strip())
    txt_tmp.write_text(body + ("\n" if body else ""), encoding="utf-8")
    lines = []
    for i, (st, en, t) in enumerate(segments, 1):
        if not t.strip(): continue
        lines.append(f"{i}\n{_fmt_ts(st)} --> {_fmt_ts(en)}\n{t.strip()}\n")
    srt_tmp.write_text("\n".join(lines), encoding="utf-8")
    os.replace(txt_tmp, txt); os.replace(srt_tmp, srt)

def transcribe_file(video):
    """Transcribe 1 video -> ghi .txt + .srt. Raise neu loi (de watcher bat & phan loai)."""
    engine, model = load_model()
    if engine == "faster-whisper":
        segs, _info = model.transcribe(str(video), language=C.WHISPER_LANG,
                                       task=C.WHISPER_TASK, vad_filter=True)
        segments = [(s.start, s.end, s.text) for s in segs]   # generator -> chay that su o day
    else:
        r = model.transcribe(str(video), language=C.WHISPER_LANG, task=C.WHISPER_TASK, verbose=False)
        segments = [(s["start"], s["end"], s["text"]) for s in r.get("segments", [])]
    _write_outputs(video, segments)
    return True

def done_txt(video):
    t = video.with_suffix(".txt")
    try: return t.exists() and t.stat().st_size > 0
    except OSError: return False

# --- danh dau video KHONG transcribe duoc (khong audio / hong) de khoi thu lai vo han ---
def _marker(video): return video.with_suffix(".notranscribe")
def skipped(video):
    try: return _marker(video).exists()
    except OSError: return False
def write_skip(video, reason):
    try: _marker(video).write_text(str(reason), encoding="utf-8")
    except OSError: pass

def _has_audio(video):
    try:
        import av
        with av.open(str(video)) as c:
            return any(s.type == "audio" for s in c.streams)
    except Exception:
        return True   # khong chac -> cu thu transcribe

def _classify_err(e):
    """Tra ve (permanent, mo_ta, fix). permanent=True -> danh dau skip, khong thu lai."""
    s = f"{type(e).__name__}: {e}".lower()
    if any(k in s for k in ("index out of range", "no audio", "moov", "invalid data",
                            "codec", "decode", "corrupt", "does not contain")):
        return True, "Video loi / khong co audio", "Da danh dau .notranscribe - bo qua"
    if "out of memory" in s or "alloc" in s:
        return False, "Het RAM", "Doi WHISPER_MODEL nho hon hoac WHISPER_COMPUTE=int8"
    if any(k in s for k in ("connect", "huggingface", "download", "url", "timeout", "ssl")):
        return False, "Loi mang khi tai model", "Kiem tra mang; se thu lai vong sau"
    if "no module named" in s or "faster_whisper" in s:
        return False, "Thieu faster-whisper", "pip install -U faster-whisper"
    return False, type(e).__name__, "Xem log; se thu lai"

def transcribe_or_skip(video):
    """Bao boc an toan cho watcher/run. Tra ve (status, detail).
       status: 'ok' | 'noaudio' | 'skip' (loi vinh vien, da danh dau) | 'retry' (loi tam, se thu lai)."""
    if not _has_audio(video):
        write_skip(video, "no audio stream")
        return "noaudio", "khong co track audio"
    try:
        transcribe_file(video)
        return "ok", ""
    except Exception as e:
        permanent, why, fix = _classify_err(e)
        if permanent:
            write_skip(video, why)
            return "skip", f"{why} -> {fix}"
        return "retry", f"{why} -> {fix}"

def list_videos(root=None):
    root = root or C.ROOT
    if not root.exists(): return []
    return sorted(p for p in root.rglob("video.*")
                  if p.suffix.lower() in C.VIDEXT and p.stem == "video")

def pending_videos(root=None, min_age=0):
    """Video da ghep, chua co .txt, chua bi danh dau skip, va da 'yen' >= min_age giay."""
    out = []
    now = time.time()
    for v in list_videos(root):
        if done_txt(v) or skipped(v): continue
        try:
            if min_age and (now - v.stat().st_mtime) < min_age: continue
        except OSError: continue
        out.append(v)
    return out

def missing_count(root=None):
    """Sprint H: so video con thieu transcript."""
    return len(pending_videos(root or C.ROOT, min_age=0))


def run(missing_only=True):
    """Transcribe. missing_only=True (mac dinh Sprint H): chi video chua co .txt."""
    print("=== TRANSCRIBE ===" + (" (chi thieu)" if missing_only else ""))
    vids = list_videos()
    if missing_only:
        todo = [v for v in vids if not done_txt(v) and not skipped(v)]
    else:
        todo = list(vids)
    already = len(vids) - len(todo) if missing_only else 0
    print(f"Tong video: {len(vids)} | can transcribe: {len(todo)} | da co phu de: {already}")
    if not todo:
        print("--- TRANSCRIBE: khong con bai thieu ---\n")
        return {"done": 0, "todo": 0, "already": already}
    done = noaudio = skip = retry = 0
    for i, v in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {v.relative_to(C.ROOT)}", flush=True)
        status, detail = transcribe_or_skip(v)
        if status == "ok": done += 1
        elif status == "noaudio": noaudio += 1; print("   [bo qua] khong co audio", flush=True)
        elif status == "skip": skip += 1; print(f"   [bo qua] {detail}", flush=True)
        else: retry += 1; print(f"   [LOI tam] {detail}", flush=True)
    print(f"--- TRANSCRIBE: done={done} noaudio={noaudio} skip={skip} loi-tam={retry} "
          f"da-co={already} ---\n")
    return {"done": done, "todo": len(todo), "already": already,
            "noaudio": noaudio, "skip": skip, "retry": retry}
