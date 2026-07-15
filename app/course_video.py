#!/usr/bin/env python3
"""
Video lab: talking_script → captions/SSML → render queue.

Providers (nếu có API key trong env / .settings.json → media_keys):
  - elevenlabs  : TTS → audio.mp3  (ELEVENLABS_API_KEY)
  - heygen      : avatar video     (HEYGEN_API_KEY)
  - synthesia   : avatar video     (SYNTHESIA_API_KEY)
  - local       : macOS `say` + ffmpeg (nếu có) → m4a/aiff

  python course_video.py --course X --prepare
  python course_video.py --course X --prepare --provider elevenlabs
  python course_video.py --course X --run-queue --limit 2
  python course_video.py --course X --queue-status
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import config as C
import course_ops as OPS

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
QUEUE = "_video_queue.json"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _settings() -> dict:
    try:
        return json.loads(
            (Path(__file__).resolve().parent / ".settings.json").read_text(encoding="utf-8")
        )
    except Exception:
        return {}


def media_key(provider: str) -> str:
    s = _settings()
    mk = s.get("media_keys") or {}
    env_map = {
        "elevenlabs": ("ELEVENLABS_API_KEY", "elevenlabs_api_key"),
        "heygen": ("HEYGEN_API_KEY", "heygen_api_key"),
        "synthesia": ("SYNTHESIA_API_KEY", "synthesia_api_key"),
    }
    p = (provider or "").lower()
    if p in env_map:
        env, sett = env_map[p]
        return (
            (os.environ.get(env) or "").strip()
            or (s.get(sett) or "").strip()
            or (mk.get(p) or "").strip()
        )
    return (mk.get(p) or "").strip()


def save_media_key(provider: str, key: str):
    path = Path(__file__).resolve().parent / ".settings.json"
    try:
        s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        s = {}
    mk = dict(s.get("media_keys") or {})
    mk[provider] = (key or "").strip()
    s["media_keys"] = mk
    # also legacy flat keys
    flat = {
        "elevenlabs": "elevenlabs_api_key",
        "heygen": "heygen_api_key",
        "synthesia": "synthesia_api_key",
    }
    if provider in flat:
        s[flat[provider]] = key
    path.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def find_lessons(root: Path) -> List[Path]:
    dest = Path(root) / UPGRADE
    if not dest.is_dir():
        return []
    return sorted(
        {p.parent for p in dest.rglob("talking_script.md") if "locales" not in p.parts}
    )


def script_plain(script: str) -> str:
    text = re.sub(r"#+\s*", "", script or "")
    text = re.sub(r"\[PAUSE\]", ". ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def script_to_ssml(script: str, voice: str = "default", lang: str = "en-US") -> str:
    text = re.sub(r"#+\s*", "", script or "")
    parts = re.split(r"\[PAUSE\]", text, flags=re.I)
    body = ""
    for i, p in enumerate(parts):
        p = re.sub(r"\s+", " ", p).strip()
        if not p:
            continue
        body += f"<p>{_xml_escape(p)}</p>"
        if i < len(parts) - 1:
            body += '<break time="600ms"/>'
    return (
        f'<speak version="1.0" xml:lang="{_xml_escape(lang)}">'
        f'<voice name="{_xml_escape(voice)}">{body}</voice></speak>'
    )


def _xml_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def estimate_minutes(script: str, wpm: int = 140) -> float:
    words = len(re.findall(r"\w+", script or ""))
    return round(max(0.5, words / wpm), 2)


def find_locale_lessons(root: Path, locale: str) -> List[Path]:
    hub = Path(root) / UPGRADE / "locales" / locale
    if not hub.is_dir():
        return []
    return sorted({p.parent for p in hub.rglob("talking_script.md")})


def voice_for_locale(brand: dict, locale: Optional[str]) -> str:
    """Pick ElevenLabs (or brand) voice id for a locale."""
    lv = brand.get("locale_voices") or {}
    if locale:
        if locale in lv and lv[locale]:
            return lv[locale]
        # language prefix: zh-CN → zh
        base = locale.split("-")[0]
        if base in lv and lv[base]:
            return lv[base]
    return brand.get("eleven_voice_id") or brand.get("voice") or "21m00Tcm4TlvDq8ikWAM"


def prepare_video_jobs(
    root: Path,
    *,
    provider: str = "elevenlabs",
    force: bool = False,
    limit: int = 0,
    locale: Optional[str] = None,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    if locale:
        lessons = find_locale_lessons(root, locale)
        base_for_rel = root / UPGRADE / "locales" / locale
    else:
        lessons = find_lessons(root)
        base_for_rel = root / UPGRADE
    if limit > 0:
        lessons = lessons[:limit]
    if not lessons:
        raise FileNotFoundError(
            f"Không thấy talking_script.md trong {UPGRADE}/"
            + (f"/locales/{locale}" if locale else "")
            + " — chạy course_studio --assets/--localize trước."
        )

    brand = _load_brand(root)
    voice_id = voice_for_locale(brand, locale)
    # stamp selected voice into brand copy for this queue
    brand = dict(brand)
    brand["eleven_voice_id"] = voice_id
    brand["active_locale"] = locale or (brand.get("master_lang") or "master")
    prov_l = (provider or "").lower()
    if prov_l in ("local", "omnivoice", "omni") or "omni" in prov_l:
        key_ok = True
        if "omni" in prov_l:
            # default ref for omnivoice
            ref = Path.home() / "Downloads" / "ref.wav"
            if not ref.exists():
                key_ok = False
    else:
        key_ok = bool(media_key(provider))
    jobs = []
    total_min = 0.0
    for ldir in lessons:
        script_p = ldir / "talking_script.md"
        script = script_p.read_text(encoding="utf-8", errors="replace")
        mins = estimate_minutes(script)
        total_min += mins
        OPS.write_captions_for_lesson(ldir, log=log)
        ssml_p = ldir / "talking_script.ssml"
        if force or not ssml_p.exists():
            ssml_p.write_text(
                script_to_ssml(
                    script,
                    voice=voice_id,
                    lang=(locale or "en-US"),
                ),
                encoding="utf-8",
            )
        plain_p = ldir / "talking_script.plain.txt"
        plain_p.write_text(script_plain(script), encoding="utf-8")
        try:
            rel = str(ldir.relative_to(base_for_rel))
        except ValueError:
            rel = ldir.name
        if locale:
            rel = f"locales/{locale}/{rel}"
        job = {
            "lesson": rel,
            "dir": str(ldir),
            "locale": locale or "",
            "voice_id": voice_id,
            "script": "talking_script.md",
            "plain": "talking_script.plain.txt",
            "ssml": "talking_script.ssml",
            "srt": "talking_script.srt",
            "minutes_est": mins,
            "provider": provider,
            "status": "ready" if key_ok else "need_api_key",
            "output": f"video_ai.{_ext_for(provider)}",
            "brand": brand,
            "cost": OPS.video_cost_estimate(mins, provider),
            "updated_at": _now(),
            "render_hint": _render_hint(provider, ldir),
            "error": "" if key_ok else f"Thiếu API key cho {provider}",
        }
        meta_p = ldir / "video_job.json"
        meta_p.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        jobs.append(job)
        _log(
            f"   video job: {job['lesson']} ~{mins}m ${job['cost']['usd_est']} "
            f"voice={voice_id[:12]}… [{job['status']}]",
            log,
        )

    queue = {
        "provider": provider,
        "locale": locale or "",
        "voice_id": voice_id,
        "api_configured": key_ok,
        "jobs": len(jobs),
        "minutes_total": round(total_min, 2),
        "usd_est_total": round(sum(j["cost"]["usd_est"] for j in jobs), 2),
        "items": jobs,
        "updated_at": _now(),
        "note": "Chạy --run-queue để render (cần API key hoặc provider=local).",
    }
    _save_queue(root, queue)
    _write_queue_md(root, queue)
    _log(
        f">> Video prepare: {len(jobs)} jobs · ~{queue['minutes_total']}m · "
        f"${queue['usd_est_total']} · api={key_ok}",
        log,
    )
    return queue


def _save_queue(root: Path, queue: dict):
    qp = Path(root) / UPGRADE / QUEUE
    qp.parent.mkdir(parents=True, exist_ok=True)
    qp.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_queue_md(root: Path, queue: dict):
    md = [
        f"# Video queue — {Path(root).name}",
        f"",
        f"- Provider: **{queue.get('provider')}**",
        f"- API configured: {queue.get('api_configured')}",
        f"- Jobs: {queue.get('jobs')}",
        f"- Minutes est: {queue.get('minutes_total')}",
        f"- Cost est: **${queue.get('usd_est_total')}**",
        f"- Updated: {queue.get('updated_at')}",
        f"",
        f"## Jobs",
        f"",
    ]
    for j in queue.get("items") or []:
        md.append(
            f"- `{j['lesson']}` — {j['minutes_est']}m — ${j['cost']['usd_est']} — "
            f"**{j['status']}** {j.get('error') or ''}"
        )
    (Path(root) / UPGRADE / "_video_queue.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def _ext_for(provider: str) -> str:
    p = (provider or "").lower()
    if "omni" in p:
        return "wav"
    if "eleven" in p or "tts" in p or p == "local":
        return "mp3"
    return "mp4"


def _load_brand(root: Path) -> dict:
    p = Path(root) / "_brand_kit.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    brand = {
        "name": Path(root).name,
        "primary_color": "#1E40AF",
        "logo": "",
        "intro_seconds": 3,
        "outro_seconds": 3,
        "voice": "default",
        "eleven_voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel default public
        "heygen_avatar_id": "",
        "heygen_voice_id": "",
        "synthesia_avatar": "anna_costume1_cameraA",
        "watermark": "",
        "locale_voices": {
            "en": "21m00Tcm4TlvDq8ikWAM",
            "vi": "21m00Tcm4TlvDq8ikWAM",
            "ja": "21m00Tcm4TlvDq8ikWAM",
            "es": "21m00Tcm4TlvDq8ikWAM",
            "zh-CN": "21m00Tcm4TlvDq8ikWAM",
            "ko": "21m00Tcm4TlvDq8ikWAM",
        },
    }
    p.write_text(json.dumps(brand, ensure_ascii=False, indent=2), encoding="utf-8")
    return brand


def _render_hint(provider: str, ldir: Path) -> str:
    p = (provider or "").lower()
    if "omni" in p:
        return "OmniVoice local clone (ref.wav / conda omnivoice / MPS)"
    if "eleven" in p:
        return "elevenlabs TTS API (text-to-speech)"
    if "heygen" in p:
        return "HeyGen v2 video generate API"
    if "synthesia" in p:
        return "Synthesia videos API"
    if "local" in p:
        return "macOS say / espeak + optional ffmpeg"
    return f"provider {provider}"


def queue_status(root: Path) -> dict:
    p = Path(root) / UPGRADE / QUEUE
    if not p.exists():
        return {"jobs": 0, "message": "Chưa prepare"}
    return json.loads(p.read_text(encoding="utf-8"))


def preview_voice(
    root: Path,
    *,
    provider: str = "elevenlabs",
    locale: Optional[str] = None,
    text: Optional[str] = None,
    log: LogFn = print,
) -> Path:
    """
    Sinh audio preview ngắn (~15–20s) để nghe voice trước khi full render.
    """
    root = Path(root)
    brand = _load_brand(root)
    voice = voice_for_locale(brand, locale)
    sample = text or (
        "Xin chào. Đây là bản xem trước giọng đọc Course OS. "
        "Hello — this is a Course OS voice preview for locale testing."
        if (locale or "").startswith("vi") or not locale
        else "Hello. This is a Course OS voice preview for your selected locale."
    )
    sample = sample[:400]
    out_dir = root / UPGRADE / "_voice_previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = (locale or "master").replace("/", "_")
    provider = (provider or "elevenlabs").lower()

    if provider == "local" or ("eleven" not in provider and provider != "elevenlabs"):
        if provider not in ("local", "elevenlabs") and "eleven" not in provider:
            # force local for unknown
            pass
    if provider == "local" or not media_key("elevenlabs"):
        out = out_dir / f"preview_{tag}.aiff"
        try:
            subprocess.run(
                ["say", "-o", str(out), sample],
                check=True,
                capture_output=True,
            )
            _log(f">> Voice preview (local say) → {out}", log)
            return out
        except Exception as e:
            # try espeak
            out = out_dir / f"preview_{tag}.wav"
            try:
                subprocess.run(
                    ["espeak", "-w", str(out), sample],
                    check=True,
                    capture_output=True,
                )
                _log(f">> Voice preview (espeak) → {out}", log)
                return out
            except Exception as e2:
                raise RuntimeError(f"Local preview failed: {e} / {e2}") from e2

    # ElevenLabs short TTS
    key = media_key("elevenlabs")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    headers = {
        "xi-api-key": key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body = {
        "text": sample,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
    }
    _log(f">> Voice preview elevenlabs voice={voice[:12]}… locale={tag}", log)
    data = _http_json("POST", url, headers, body, timeout=90, raw=True)
    out = out_dir / f"preview_{tag}.mp3"
    if isinstance(data, (bytes, bytearray)):
        out.write_bytes(data)
    else:
        raise RuntimeError("Unexpected preview response")
    _log(f">> Voice preview → {out}", log)
    meta = {
        "locale": locale or "",
        "voice_id": voice,
        "provider": "elevenlabs",
        "path": str(out),
        "at": _now(),
        "text": sample,
    }
    (out_dir / f"preview_{tag}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


# -------------------- render providers --------------------
def _http_json(
    method: str,
    url: str,
    headers: dict,
    body: Optional[dict] = None,
    timeout: int = 120,
    raw: bool = False,
):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers = dict(headers)
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw_b = r.read()
        if raw:
            return raw_b
        if not raw_b:
            return {}
        return json.loads(raw_b.decode("utf-8", errors="replace"))


def render_elevenlabs(ldir: Path, job: dict, log: LogFn = print) -> Path:
    key = media_key("elevenlabs")
    if not key:
        raise RuntimeError("Thiếu ELEVENLABS_API_KEY / media_keys.elevenlabs")
    brand = job.get("brand") or {}
    voice = (
        job.get("voice_id")
        or voice_for_locale(brand, job.get("locale"))
        or brand.get("eleven_voice_id")
        or "21m00Tcm4TlvDq8ikWAM"
    )
    plain = (ldir / "talking_script.plain.txt").read_text(encoding="utf-8", errors="replace")
    if not plain.strip():
        plain = script_plain((ldir / "talking_script.md").read_text(encoding="utf-8", errors="replace"))
    # truncate for API safety
    plain = plain[:4800]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    headers = {
        "xi-api-key": key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body = {
        "text": plain,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
    }
    _log(f"   elevenlabs TTS {ldir.name}…", log)
    audio = _http_json("POST", url, headers, body, timeout=180, raw=True)
    out = ldir / "video_ai.mp3"
    out.write_bytes(audio)
    return out


def render_local(ldir: Path, job: dict, log: LogFn = print) -> Path:
    """macOS `say` → aiff, optional ffmpeg → mp3."""
    plain_p = ldir / "talking_script.plain.txt"
    if not plain_p.exists():
        plain_p.write_text(
            script_plain((ldir / "talking_script.md").read_text(encoding="utf-8", errors="replace")),
            encoding="utf-8",
        )
    aiff = ldir / "video_ai.aiff"
    out_mp3 = ldir / "video_ai.mp3"
    _log(f"   local TTS (say) {ldir.name}…", log)
    # macOS say
    try:
        subprocess.run(
            ["say", "-f", str(plain_p), "-o", str(aiff)],
            check=True,
            capture_output=True,
            timeout=600,
        )
    except FileNotFoundError:
        # espeak fallback
        wav = ldir / "video_ai.wav"
        subprocess.run(
            ["espeak", "-f", str(plain_p), "-w", str(wav)],
            check=True,
            capture_output=True,
            timeout=600,
        )
        aiff = wav
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"say failed: {e.stderr}") from e

    # ffmpeg to mp3 if available
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(aiff), str(out_mp3)],
            check=True,
            capture_output=True,
            timeout=300,
        )
        return out_mp3
    except Exception:
        return aiff


def render_heygen(ldir: Path, job: dict, log: LogFn = print) -> Path:
    key = media_key("heygen")
    if not key:
        raise RuntimeError("Thiếu HEYGEN_API_KEY")
    brand = job.get("brand") or {}
    plain = (ldir / "talking_script.plain.txt").read_text(encoding="utf-8", errors="replace")[:4000]
    avatar = brand.get("heygen_avatar_id") or ""
    voice = brand.get("heygen_voice_id") or ""
    if not avatar:
        # list default: still need avatar — create job with text only avatar_style
        raise RuntimeError(
            "Đặt heygen_avatar_id trong _brand_kit.json (lấy từ HeyGen dashboard)."
        )
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "input_text": plain,
                    **({"voice_id": voice} if voice else {}),
                },
            }
        ],
        "dimension": {"width": 1280, "height": 720},
    }
    _log(f"   heygen create {ldir.name}…", log)
    try:
        resp = _http_json(
            "POST",
            "https://api.heygen.com/v2/video/generate",
            headers,
            payload,
            timeout=120,
        )
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HeyGen HTTP {e.code}: {err}") from e
    data = resp.get("data") or resp
    video_id = data.get("video_id") or data.get("id")
    if not video_id:
        raise RuntimeError(f"HeyGen no video_id: {resp}")
    # poll
    for _ in range(60):
        time.sleep(5)
        st = _http_json(
            "GET",
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            {"X-Api-Key": key},
            timeout=60,
        )
        d = st.get("data") or st
        status = (d.get("status") or "").lower()
        _log(f"   heygen status={status}", log)
        if status in ("completed", "done", "success"):
            vurl = d.get("video_url") or d.get("url")
            if not vurl:
                raise RuntimeError(f"No video_url: {st}")
            out = ldir / "video_ai.mp4"
            req = urllib.request.Request(vurl, headers={"User-Agent": "SkoolDownloader/2.23"})
            with urllib.request.urlopen(req, timeout=300) as r:
                out.write_bytes(r.read())
            return out
        if status in ("failed", "error"):
            raise RuntimeError(f"HeyGen failed: {d}")
    raise RuntimeError("HeyGen timeout polling")


def render_synthesia(ldir: Path, job: dict, log: LogFn = print) -> Path:
    key = media_key("synthesia")
    if not key:
        raise RuntimeError("Thiếu SYNTHESIA_API_KEY")
    brand = job.get("brand") or {}
    plain = (ldir / "talking_script.plain.txt").read_text(encoding="utf-8", errors="replace")[:4000]
    avatar = brand.get("synthesia_avatar") or "anna_costume1_cameraA"
    headers = {"Authorization": key, "Content-Type": "application/json"}
    payload = {
        "test": True,
        "title": ldir.name[:80],
        "input": [
            {
                "avatar": avatar,
                "scriptText": plain,
                "avatarSettings": {"voice": "en-US"},
            }
        ],
    }
    _log(f"   synthesia create {ldir.name}…", log)
    try:
        resp = _http_json(
            "POST",
            "https://api.synthesia.io/v2/videos",
            headers,
            payload,
            timeout=120,
        )
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Synthesia HTTP {e.code}: {err}") from e
    vid = resp.get("id")
    if not vid:
        raise RuntimeError(f"Synthesia no id: {resp}")
    for _ in range(60):
        time.sleep(5)
        st = _http_json(
            "GET",
            f"https://api.synthesia.io/v2/videos/{vid}",
            headers,
            timeout=60,
        )
        status = (st.get("status") or "").lower()
        _log(f"   synthesia status={status}", log)
        if status == "complete":
            vurl = st.get("download") or st.get("url")
            if not vurl:
                # download endpoint
                raise RuntimeError(f"No download url yet: {st}")
            out = ldir / "video_ai.mp4"
            req = urllib.request.Request(vurl, headers={"Authorization": key})
            with urllib.request.urlopen(req, timeout=300) as r:
                out.write_bytes(r.read())
            return out
        if status in ("rejected", "failed", "error"):
            raise RuntimeError(f"Synthesia failed: {st}")
    raise RuntimeError("Synthesia timeout")


def run_queue(
    root: Path,
    *,
    limit: int = 0,
    only_status: str = "ready",
    log: LogFn = print,
) -> dict:
    root = Path(root)
    q = queue_status(root)
    items = q.get("items") or []
    if not items:
        # rebuild from prepare if missing
        raise FileNotFoundError("Queue trống — chạy --prepare trước")
    done = fail = skip = 0
    n = 0
    for job in items:
        if only_status and job.get("status") not in (only_status, "failed", "need_api_key"):
            if job.get("status") == "rendered":
                skip += 1
            continue
        if limit and n >= limit:
            break
        n += 1
        ldir = Path(job.get("dir") or (root / UPGRADE / job["lesson"]))
        provider = (job.get("provider") or q.get("provider") or "local").lower()
        try:
            if "omni" in provider:
                import course_omnivoice as OV

                # respect per-lesson toggle
                if not OV.is_tts_enabled(ldir):
                    job["status"] = "skipped"
                    job["error"] = "TTS off for lesson"
                    skip += 1
                    continue
                out = OV.render_lesson(ldir, force=False, log=log)
                if out is None:
                    job["status"] = "skipped"
                    skip += 1
                    continue
            elif "eleven" in provider:
                out = render_elevenlabs(ldir, job, log=log)
            elif "heygen" in provider:
                out = render_heygen(ldir, job, log=log)
            elif "synthesia" in provider:
                out = render_synthesia(ldir, job, log=log)
            elif provider == "local":
                out = render_local(ldir, job, log=log)
            else:
                raise RuntimeError(f"Provider không hỗ trợ run-queue: {provider}")
            job["status"] = "rendered"
            job["output_path"] = str(out)
            job["error"] = ""
            job["updated_at"] = _now()
            done += 1
            _log(f"   ✓ rendered {job['lesson']} → {out.name}", log)
        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)[:500]
            job["updated_at"] = _now()
            fail += 1
            _log(f"   ✗ {job['lesson']}: {e}", log)
        # persist per-lesson
        try:
            (ldir / "video_job.json").write_text(
                json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
    q["items"] = items
    q["updated_at"] = _now()
    q["last_run"] = {"done": done, "fail": fail, "skip": skip, "at": _now()}
    _save_queue(root, q)
    _write_queue_md(root, q)
    _log(f"--- RUN QUEUE done={done} fail={fail} skip={skip} ---", log)
    return q["last_run"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Video lab + render queue")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--run-queue", action="store_true")
    ap.add_argument("--provider", default="elevenlabs",
                    help="elevenlabs|heygen|synthesia|local|omnivoice")
    ap.add_argument("--locale", default="", help="Dùng scripts trong locales/<code>/ + voice map")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--queue-status", action="store_true")
    ap.add_argument("--set-key", nargs=2, metavar=("PROVIDER", "KEY"),
                    help="Lưu media API key: --set-key elevenlabs sk_xxx")
    ap.add_argument(
        "--set-voice",
        nargs=2,
        metavar=("LOCALE", "VOICE_ID"),
        help="Ghi brand locale_voices: --set-voice ja xxxVoiceId",
    )
    ap.add_argument(
        "--preview-voice",
        action="store_true",
        help="Sinh audio preview ngắn (~15s) để nghe voice",
    )
    ap.add_argument(
        "--preview-text",
        default="",
        help="Text preview (mặc định sample EN/VI)",
    )
    args = ap.parse_args(argv)

    if args.set_key:
        save_media_key(args.set_key[0], args.set_key[1])
        print(f"Saved media key for {args.set_key[0]}")
        return 0

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.set_voice:
        brand = _load_brand(root)
        lv = dict(brand.get("locale_voices") or {})
        lv[args.set_voice[0]] = args.set_voice[1]
        brand["locale_voices"] = lv
        (root / "_brand_kit.json").write_text(
            json.dumps(brand, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Voice {args.set_voice[0]} → {args.set_voice[1]}")
        return 0

    if args.queue_status:
        print(json.dumps(queue_status(root), ensure_ascii=False, indent=2)[:4000])
        return 0
    loc = (args.locale or "").strip() or None
    if args.preview_voice:
        out = preview_voice(
            root,
            provider=args.provider,
            locale=loc,
            text=(args.preview_text or None),
        )
        print(f"Preview → {out}")
        return 0
    if args.prepare:
        prepare_video_jobs(
            root,
            provider=args.provider,
            force=args.force,
            limit=args.limit,
            locale=loc,
        )
        return 0
    if args.run_queue:
        # ensure prepared
        if not (root / UPGRADE / QUEUE).exists():
            prepare_video_jobs(
                root, provider=args.provider, force=args.force, locale=loc
            )
        run_queue(root, limit=args.limit)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
