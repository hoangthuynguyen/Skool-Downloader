"""Transcribe video -> video.txt + video.srt (dat CUNG folder voi video).

Engine mac dinh: faster-whisper (CTranslate2).
- Ngon ngu: mac dinh AUTO-DETECT (WHISPER_LANG=auto).
- Ghep gioi thieu bai (description.md) vao plain text.
- Mac dinh pipeline: AUTO_TRANSCRIBE=True (tat bang --no-transcribe / GUI).
- Sau moi lan run: ghep "all transcript.txt" o goc khoa (thu tu bai).
"""
from __future__ import annotations

import os
import re
import time
import warnings
from datetime import datetime
from pathlib import Path

import common as K
import config as C

_MODEL = None
_ENGINE_LOADED = None


def _resolve_device():
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
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def load_model():
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
        print(
            f"   [model] faster-whisper '{C.WHISPER_MODEL}' device={device} "
            f"compute={compute} lang={C.WHISPER_LANG or 'auto'} "
            f"(lan dau tai model hoi lau)...",
            flush=True,
        )
        _MODEL = WhisperModel(C.WHISPER_MODEL, device=device, compute_type=compute)
    else:
        import whisper
        ff = K.ffmpeg_dir()
        if ff:
            os.environ["PATH"] = ff + os.pathsep + os.environ["PATH"]
        print(
            f"   [model] openai-whisper '{C.WHISPER_MODEL}' "
            f"lang={C.WHISPER_LANG or 'auto'}...",
            flush=True,
        )
        _MODEL = whisper.load_model(C.WHISPER_MODEL)
    _ENGINE_LOADED = engine
    return engine, _MODEL


def read_lesson_intro(video: Path) -> str:
    """Doc gioi thieu bai (description.md canh video)."""
    if not getattr(C, "TRANSCRIPT_INCLUDE_INTRO", True):
        return ""
    folder = video.parent if video.suffix else video
    # video la file path
    if video.is_file() or video.suffix:
        folder = video.parent
    for name in ("description.md", "Description.md", "intro.md"):
        p = folder / name
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8", errors="replace").strip()
                return text
            except OSError:
                pass
    return ""


def _compose_plain_text(intro: str, transcript: str, lang: str | None) -> str:
    """Ghep intro + transcript plain text (co nhan de doc)."""
    parts = []
    if intro:
        parts.append("## Giới thiệu bài\n\n" + intro.strip())
    lang_note = f" (ngôn ngữ: {lang})" if lang else " (auto-detect)"
    body = (transcript or "").strip()
    if body:
        parts.append(f"## Transcript{lang_note}\n\n" + body)
    elif not intro:
        parts.append(f"## Transcript{lang_note}\n\n")
    else:
        parts.append(f"## Transcript{lang_note}\n\n(chưa có lời thoại / không audio)")
    return "\n\n".join(parts).strip() + "\n"


def _write_outputs(video, segments, lang: str | None = None, intro: str = ""):
    """Ghi video.txt (intro + plain transcript) + video.srt (chi speech)."""
    txt = video.with_suffix(".txt")
    srt = video.with_suffix(".srt")
    txt_tmp = video.with_suffix(".txt.part")
    srt_tmp = video.with_suffix(".srt.part")

    speech = "\n".join(t.strip() for _, _, t in segments if t.strip())
    plain = _compose_plain_text(intro, speech, lang)
    txt_tmp.write_text(plain, encoding="utf-8")

    lines = []
    for i, (st, en, t) in enumerate(segments, 1):
        if not t.strip():
            continue
        lines.append(f"{i}\n{_fmt_ts(st)} --> {_fmt_ts(en)}\n{t.strip()}\n")
    srt_tmp.write_text("\n".join(lines), encoding="utf-8")
    os.replace(txt_tmp, txt)
    os.replace(srt_tmp, srt)

    # luu ngon ngu detect (phu)
    try:
        if lang:
            video.with_suffix(".lang").write_text(str(lang).strip() + "\n", encoding="utf-8")
    except OSError:
        pass


def _language_kw():
    """Arg ngon ngu cho whisper: None = auto-detect."""
    if hasattr(C, "whisper_language_arg"):
        return C.whisper_language_arg()
    lang = (getattr(C, "WHISPER_LANG", None) or "auto").strip().lower()
    if lang in ("", "auto", "detect", "none", "null"):
        return None
    return lang


def transcribe_file(video):
    """Transcribe 1 video -> video.txt (+ intro) + video.srt. Raise neu loi."""
    engine, model = load_model()
    lang = _language_kw()
    intro = read_lesson_intro(video)
    detected = None

    if engine == "faster-whisper":
        # language=None -> Whisper auto-detect
        segs, info = model.transcribe(
            str(video),
            language=lang,
            task=C.WHISPER_TASK,
            vad_filter=True,
        )
        segments = [(s.start, s.end, s.text) for s in segs]
        detected = getattr(info, "language", None) or lang
        if detected:
            print(f"      [lang] detected={detected}", flush=True)
    else:
        kwargs = {"task": C.WHISPER_TASK, "verbose": False}
        if lang:
            kwargs["language"] = lang
        r = model.transcribe(str(video), **kwargs)
        segments = [(s["start"], s["end"], s["text"]) for s in r.get("segments", [])]
        detected = r.get("language") or lang
        if detected:
            print(f"      [lang] detected={detected}", flush=True)

    _write_outputs(video, segments, lang=detected, intro=intro)
    return True


def done_txt(video):
    t = video.with_suffix(".txt")
    try:
        return t.exists() and t.stat().st_size > 0
    except OSError:
        return False


def _marker(video):
    return video.with_suffix(".notranscribe")


def skipped(video):
    try:
        return _marker(video).exists()
    except OSError:
        return False


def write_skip(video, reason):
    try:
        _marker(video).write_text(str(reason), encoding="utf-8")
    except OSError:
        pass


def _has_audio(video):
    try:
        import av
        with av.open(str(video)) as c:
            return any(s.type == "audio" for s in c.streams)
    except Exception:
        return True


def _classify_err(e):
    s = f"{type(e).__name__}: {e}".lower()
    if any(
        k in s
        for k in (
            "index out of range",
            "no audio",
            "moov",
            "invalid data",
            "codec",
            "decode",
            "corrupt",
            "does not contain",
        )
    ):
        return True, "Video loi / khong co audio", "Da danh dau .notranscribe - bo qua"
    if "out of memory" in s or "alloc" in s:
        return False, "Het RAM", "Doi WHISPER_MODEL nho hon hoac WHISPER_COMPUTE=int8"
    if any(k in s for k in ("connect", "huggingface", "download", "url", "timeout", "ssl")):
        return False, "Loi mang khi tai model", "Kiem tra mang; se thu lai vong sau"
    if "no module named" in s or "faster_whisper" in s:
        return False, "Thieu faster-whisper", "pip install -U faster-whisper"
    return False, type(e).__name__, "Xem log; se thu lai"


def transcribe_or_skip(video):
    if not _has_audio(video):
        # van ghi intro neu co
        intro = read_lesson_intro(video)
        if intro:
            try:
                plain = _compose_plain_text(intro, "", None)
                video.with_suffix(".txt").write_text(plain, encoding="utf-8")
            except OSError:
                pass
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


def _nat_key(s: str):
    parts = re.split(r"(\d+)", str(s).replace("\\", "/").lower())
    out = []
    for p in parts:
        if p.isdigit():
            out.append(int(p))
        else:
            out.append(p)
    return out


def list_videos(root=None):
    root = Path(root) if root is not None else Path(C.ROOT)
    if not root.exists():
        return []
    vids = [
        p
        for p in root.rglob("video.*")
        if p.suffix.lower() in C.VIDEXT and p.stem == "video"
    ]
    return sorted(vids, key=lambda p: _nat_key(str(p.relative_to(root))))


def lesson_label(video: Path, root=None) -> str:
    root = Path(root) if root is not None else Path(C.ROOT)
    try:
        rel = video.parent.relative_to(root)
    except ValueError:
        rel = video.parent
    parts = [p for p in Path(rel).parts if p and p not in (".",)]
    return " / ".join(parts) if parts else video.parent.name


def all_transcript_path(root=None) -> Path:
    root = Path(root) if root is not None else Path(C.ROOT)
    name = getattr(C, "ALL_TRANSCRIPT_NAME", None) or "all transcript.txt"
    return root / name


def _read_existing_txt(video: Path) -> str:
    p = video.with_suffix(".txt")
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def write_all_transcript(root=None) -> Path:
    """
    Ghep tat ca bai theo thu tu -> 'all transcript.txt'.
    Moi bai: tieu de + gioi thieu (description.md) + transcript, cach 3 dong trang.
    """
    root = Path(root) if root is not None else Path(C.ROOT)
    out = all_transcript_path(root)
    vids = list_videos(root)
    blocks = []
    n_ok = 0
    n_missing = 0
    for i, v in enumerate(vids, 1):
        label = lesson_label(v, root)
        header = f"{'=' * 72}\n{i}. {label}\n{'=' * 72}"

        # uu tien noi dung video.txt da ghep (intro+transcript)
        existing = _read_existing_txt(v)
        if existing:
            body = existing
            # co section Transcript voi noi dung that?
            if "## Transcript" in existing:
                # bo placeholder
                after = existing.split("## Transcript", 1)[-1]
                if "(chưa có" not in after and after.strip() not in ("", ":"):
                    n_ok += 1
                else:
                    n_missing += 1
            else:
                n_ok += 1
        else:
            intro = read_lesson_intro(v)
            body = _compose_plain_text(
                intro, "(chưa có transcript — video chưa chạy Whisper hoặc bị bỏ qua)", None
            ).strip()
            n_missing += 1

        blocks.append(f"{header}\n\n{body.strip()}")

    course_name = getattr(C, "COURSE", None) or root.name
    meta = (
        f"ALL TRANSCRIPTS — {course_name}\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Videos: {len(vids)} | có transcript: {n_ok} | thiếu/rỗng: {n_missing}\n"
        f"Engine: {getattr(C, 'WHISPER_ENGINE', 'faster-whisper')} "
        f"/ model: {getattr(C, 'WHISPER_MODEL', '')} "
        f"/ lang: {getattr(C, 'WHISPER_LANG', 'auto')}\n"
        f"Mỗi bài gồm: Giới thiệu (description.md) + Transcript (auto-detect ngôn ngữ)\n"
        f"{'=' * 72}\n"
    )
    body = ("\n\n\n").join(blocks)
    text = meta + "\n" + body + ("\n" if body else "")
    tmp = out.with_suffix(out.suffix + ".part")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, out)
    except OSError:
        out.write_text(text, encoding="utf-8")
    print(
        f"   [all transcript] {out.name} — {n_ok}/{len(vids)} bai co text → {out}",
        flush=True,
    )
    return out


def pending_videos(root=None, min_age=0):
    out = []
    now = time.time()
    for v in list_videos(root):
        if done_txt(v) or skipped(v):
            continue
        try:
            if min_age and (now - v.stat().st_mtime) < min_age:
                continue
        except OSError:
            continue
        out.append(v)
    return out


def missing_count(root=None):
    return len(pending_videos(root or C.ROOT, min_age=0))


def run(missing_only=True, write_combined=True):
    print("=== TRANSCRIBE ===" + (" (chi thieu)" if missing_only else ""))
    lang = _language_kw()
    print(
        f"Lang: {'auto-detect' if lang is None else lang} | "
        f"include intro (description.md): {bool(getattr(C, 'TRANSCRIPT_INCLUDE_INTRO', True))}",
        flush=True,
    )
    vids = list_videos()
    if missing_only:
        todo = [v for v in vids if not done_txt(v) and not skipped(v)]
    else:
        todo = list(vids)
    already = len(vids) - len(todo) if missing_only else 0
    print(
        f"Tong video: {len(vids)} | can transcribe: {len(todo)} | da co plain text: {already}",
        flush=True,
    )
    done = noaudio = skip = retry = 0
    if todo:
        for i, v in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {v.relative_to(C.ROOT)}", flush=True)
            status, detail = transcribe_or_skip(v)
            if status == "ok":
                done += 1
            elif status == "noaudio":
                noaudio += 1
                print("   [bo qua] khong co audio (van ghi intro neu co)", flush=True)
            elif status == "skip":
                skip += 1
                print(f"   [bo qua] {detail}", flush=True)
            else:
                retry += 1
                print(f"   [LOI tam] {detail}", flush=True)
    else:
        print("--- TRANSCRIBE: khong con bai thieu ---", flush=True)

    combined = None
    if write_combined:
        try:
            combined = write_all_transcript()
        except Exception as e:
            print(f"   [all transcript] loi: {e}", flush=True)

    print(
        f"--- TRANSCRIBE: done={done} noaudio={noaudio} skip={skip} loi-tam={retry} "
        f"da-co={already} ---\n",
        flush=True,
    )
    return {
        "done": done,
        "todo": len(todo),
        "already": already,
        "noaudio": noaudio,
        "skip": skip,
        "retry": retry,
        "all_transcript": str(combined) if combined else None,
    }
