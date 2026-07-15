#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OmniVoice TTS cho Course OS — clone giọng từ ref.wav (local MPS).

Yêu cầu env conda `omnivoice` (hoặc PYTHON có omnivoice + torch MPS).

  # 1 bài
  python course_omnivoice.py --course X --lesson "01 - Chap/01 - Lesson"

  # toàn khóa (chỉ bài tts_enabled)
  python course_omnivoice.py --course X --all --limit 5

  # bật/tắt TTS cho 1 bài hoặc cả khóa
  python course_omnivoice.py --course X --enable-all
  python course_omnivoice.py --course X --disable-all
  python course_omnivoice.py --course X --enable-lesson "path/rel"
  python course_omnivoice.py --course X --disable-lesson "path/rel"

  # mở Streamlit UI
  python course_omnivoice.py --streamlit
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import config as C

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
TTS_FLAG = "tts_enabled"
TTS_META = "tts_omnivoice.json"
DEFAULT_REF = Path.home() / "Downloads" / "ref.wav"
OMNI_PY = Path("/opt/homebrew/Caskroom/miniconda/base/envs/omnivoice/bin/python")
STREAMLIT_APP = Path.home() / "Downloads" / "omni_app.py"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _settings() -> dict:
    p = Path(__file__).resolve().parent / ".settings.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def _save_settings(data: dict):
    p = Path(__file__).resolve().parent / ".settings.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_tts_config() -> dict:
    s = _settings()
    cfg = dict(s.get("omnivoice") or {})
    cfg.setdefault("enabled_default", False)  # default TẮT — chỉ TTS khi bật tường minh
    cfg.setdefault("ref_wav", str(DEFAULT_REF))
    cfg.setdefault("language", "vi")
    cfg.setdefault("speed", 1.0)
    cfg.setdefault("ref_text", "")
    cfg.setdefault("python", str(OMNI_PY) if OMNI_PY.exists() else sys.executable)
    return cfg


def set_tts_config(**kwargs) -> dict:
    s = _settings()
    cfg = dict(s.get("omnivoice") or {})
    cfg.update({k: v for k, v in kwargs.items() if v is not None})
    s["omnivoice"] = cfg
    _save_settings(s)
    return cfg


def find_lessons(root: Path) -> List[Path]:
    dest = Path(root) / UPGRADE
    if not dest.is_dir():
        return []
    return sorted(
        {
            p.parent
            for p in dest.rglob("talking_script.md")
            if "locales" not in p.parts
        }
    )


def lesson_flag_path(ldir: Path) -> Path:
    return Path(ldir) / "tts_flag.json"


def is_tts_enabled(ldir: Path, default: Optional[bool] = None) -> bool:
    if default is None:
        default = bool(get_tts_config().get("enabled_default", False))
    fp = lesson_flag_path(ldir)
    if not fp.exists():
        return default
    try:
        return bool(json.loads(fp.read_text(encoding="utf-8")).get(TTS_FLAG, default))
    except Exception:
        return default


def set_tts_enabled(ldir: Path, on: bool) -> None:
    fp = lesson_flag_path(ldir)
    data = {TTS_FLAG: bool(on), "updated_at": _now()}
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_all_lessons(root: Path, on: bool, log: LogFn = print) -> int:
    n = 0
    for ldir in find_lessons(root):
        set_tts_enabled(ldir, on)
        n += 1
    set_tts_config(enabled_default=bool(on))
    _log(f">> TTS {'ON' if on else 'OFF'} cho {n} bài (default={on})", log)
    return n


def script_text(ldir: Path) -> str:
    for name in ("talking_script.plain.txt", "talking_script.md", "lesson.md", "summary.md"):
        p = Path(ldir) / name
        if p.exists():
            t = p.read_text(encoding="utf-8", errors="replace")
            if name.endswith(".md"):
                # strip simple headings
                lines = []
                for ln in t.splitlines():
                    if ln.startswith("#"):
                        continue
                    lines.append(ln)
                t = "\n".join(lines)
            t = t.strip()
            if t:
                return t
    return ""


def _resolve_python() -> str:
    cfg = get_tts_config()
    py = Path(cfg.get("python") or "")
    if py.exists():
        return str(py)
    if OMNI_PY.exists():
        return str(OMNI_PY)
    return sys.executable


def synthesize(
    text: str,
    out_wav: Path,
    *,
    ref_wav: Optional[str] = None,
    ref_text: Optional[str] = None,
    language: str = "vi",
    speed: float = 1.0,
    log: LogFn = print,
) -> Path:
    """
    Gọi OmniVoice qua subprocess python env omnivoice (tránh conflict với venv app).
    """
    cfg = get_tts_config()
    ref = ref_wav or cfg.get("ref_wav") or str(DEFAULT_REF)
    if not Path(ref).exists():
        raise FileNotFoundError(f"Thiếu ref.wav: {ref}")
    text = (text or "").strip()
    if not text:
        raise ValueError("Text rỗng")
    # truncate for stability
    if len(text) > 3500:
        text = text[:3500]
        _log("   (cắt text ~3500 ký tự để ổn định)", log)

    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    py = _resolve_python()
    worker = r'''
# -*- coding: utf-8 -*-
import json, sys
from pathlib import Path
import torch, soundfile as sf
from omnivoice import OmniVoice

args = json.loads(sys.argv[1])
model = OmniVoice.from_pretrained(
    "k2-fsa/OmniVoice",
    device_map="mps" if torch.backends.mps.is_available() else "cpu",
    dtype=torch.float32,
    low_cpu_mem_usage=True,
    trust_remote_code=True,
)
audios = model.generate(
    text=args["text"],
    ref_audio=args["ref"],
    ref_text=args.get("ref_text") or None,
    language=args.get("language") or None,
    speed=float(args.get("speed") or 1.0),
)
sr = model.sampling_rate or 24000
sf.write(args["out"], audios[0], sr)
print(args["out"])
'''
    payload = {
        "text": text,
        "ref": ref,
        "ref_text": ref_text if ref_text is not None else (cfg.get("ref_text") or ""),
        "language": language if language != "auto" else None,
        "speed": speed,
        "out": str(out_wav),
    }
    env = os.environ.copy()
    env.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
    _log(f"   OmniVoice → {out_wav.name} ({len(text)} chars)…", log)
    proc = subprocess.run(
        [py, "-c", worker, json.dumps(payload, ensure_ascii=False)],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-800:]
        raise RuntimeError(f"OmniVoice failed: {err}")
    if not out_wav.exists():
        raise RuntimeError("OmniVoice không tạo file output")
    return out_wav


def render_lesson(
    ldir: Path,
    *,
    force: bool = False,
    log: LogFn = print,
) -> Optional[Path]:
    ldir = Path(ldir)
    if not is_tts_enabled(ldir):
        _log(f"   skip (TTS off): {ldir.name}", log)
        return None
    out = ldir / "tts_omnivoice.wav"
    if out.exists() and out.stat().st_size > 1000 and not force:
        _log(f"   skip exists: {out.name}", log)
        return out
    text = script_text(ldir)
    if not text:
        raise FileNotFoundError(f"Không có script/lesson text: {ldir}")
    cfg = get_tts_config()
    path = synthesize(
        text,
        out,
        ref_wav=cfg.get("ref_wav"),
        ref_text=cfg.get("ref_text") or None,
        language=cfg.get("language") or "vi",
        speed=float(cfg.get("speed") or 1.0),
        log=log,
    )
    meta = {
        "at": _now(),
        "path": str(path),
        "chars": len(text),
        "ref_wav": cfg.get("ref_wav"),
        "language": cfg.get("language"),
        "speed": cfg.get("speed"),
    }
    (ldir / TTS_META).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def render_course(
    root: Path,
    *,
    only_enabled: bool = True,
    force: bool = False,
    limit: int = 0,
    log: LogFn = print,
) -> dict:
    lessons = find_lessons(root)
    ok = fail = skip = 0
    errors = []
    n = 0
    for ldir in lessons:
        if only_enabled and not is_tts_enabled(ldir):
            skip += 1
            continue
        if limit and n >= limit:
            break
        n += 1
        try:
            render_lesson(ldir, force=force, log=log)
            ok += 1
        except Exception as e:
            fail += 1
            errors.append(f"{ldir.name}: {e}")
            _log(f"   ✗ {ldir.name}: {e}", log)
    summary = {
        "ok": ok,
        "fail": fail,
        "skip": skip,
        "errors": errors[:20],
        "at": _now(),
    }
    (Path(root) / UPGRADE / "_tts_omnivoice_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _log(f"--- OmniVoice TTS ok={ok} fail={fail} skip={skip} ---", log)
    return summary


def export_playlist(root: Path, log: LogFn = print) -> Path:
    """HTML playlist of all tts_omnivoice.wav under _upgrade_v2."""
    import html as H
    import shutil

    root = Path(root)
    dest = root / UPGRADE
    out_dir = dest / "_tts_playlist"
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(exist_ok=True)
    items = []
    for i, ldir in enumerate(find_lessons(root), 1):
        wav = ldir / "tts_omnivoice.wav"
        if not wav.exists():
            continue
        try:
            rel = str(ldir.relative_to(dest))
        except ValueError:
            rel = ldir.name
        safe = re.sub(r"[^\w\-]+", "_", rel)[:80]
        name = f"{i:03d}_{safe}.wav"
        try:
            shutil.copy2(wav, audio_dir / name)
        except Exception:
            continue
        title = ldir.name.split(" - ", 1)[-1]
        items.append(
            f'<li><strong>{H.escape(title)}</strong><br/>'
            f'<code>{H.escape(rel)}</code><br/>'
            f'<audio controls preload="none" src="audio/{H.escape(name)}"></audio></li>'
        )
    page = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"/>
<title>OmniVoice playlist — {H.escape(root.name)}</title>
<style>
body{{font-family:system-ui;background:#0f172a;color:#f8fafc;padding:1.25rem;max-width:900px;margin:auto}}
li{{margin:1rem 0;padding:1rem;background:#1e293b;border-radius:12px;list-style:none}}
ul{{padding:0}} audio{{width:100%;margin-top:.5rem}}
code{{font-size:11px;color:#94a3b8}} h1{{font-size:1.4rem}}
</style></head><body>
<h1>🎧 OmniVoice playlist — {H.escape(root.name)}</h1>
<p>{len(items)} tracks · {_now()}</p>
<ul>{''.join(items) or '<li>Chưa có WAV — chạy --all --limit 3</li>'}</ul>
</body></html>"""
    out = out_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    (out_dir / "playlist.json").write_text(
        json.dumps({"course": root.name, "tracks": len(items), "at": _now()}, indent=2),
        encoding="utf-8",
    )
    _log(f">> TTS playlist → {out} ({len(items)} tracks)", log)
    return out


def export_toggle_board(root: Path, log: LogFn = print) -> Path:
    """HTML board: bật/tắt TTS từng bài + trạng thái WAV (download JSON apply)."""
    import html as H

    root = Path(root)
    lessons = find_lessons(root)
    rows = []
    for ldir in lessons:
        try:
            rel = str(ldir.relative_to(root / UPGRADE))
        except ValueError:
            rel = ldir.name
        on = is_tts_enabled(ldir)
        wav = (ldir / "tts_omnivoice.wav").exists()
        rows.append(
            f'<tr data-rel="{H.escape(rel)}">'
            f'<td><input type="checkbox" class="on" {"checked" if on else ""}/></td>'
            f'<td class="wav">{"✅" if wav else "—"}</td>'
            f'<td><code>{H.escape(rel)}</code></td></tr>'
        )
    page = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"/>
<title>OmniVoice TTS toggles — {H.escape(root.name)}</title>
<style>
body{{font-family:system-ui;background:#0f172a;color:#f8fafc;padding:1rem}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid #334155;padding:.45rem .5rem;text-align:left}}
th{{color:#38bdf8;position:sticky;top:0;background:#0f172a}}
button{{background:#38bdf8;color:#0f172a;border:0;border-radius:8px;padding:.5rem .9rem;font-weight:600;margin:.25rem;cursor:pointer}}
.bar{{position:sticky;top:0;background:#0f172acc;padding:.75rem;margin-bottom:.75rem;backdrop-filter:blur(6px)}}
code{{font-size:11px;color:#cbd5e1}}
.hint{{color:#94a3b8;font-size:12px}}
</style></head><body>
<div class="bar">
  <button type="button" id="allOn">Bật tất cả</button>
  <button type="button" id="allOff">Tắt tất cả</button>
  <button type="button" id="dl">Download flags JSON</button>
  <span class="hint">Apply:
  <code>python course_omnivoice.py --course "{H.escape(root.name)}" --import-flags flags.json</code>
  </span>
</div>
<table>
<thead><tr><th>TTS</th><th>WAV</th><th>Lesson</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
<script>
const rows=[...document.querySelectorAll('tbody tr')];
document.getElementById('allOn').onclick=()=>rows.forEach(r=>r.querySelector('.on').checked=true);
document.getElementById('allOff').onclick=()=>rows.forEach(r=>r.querySelector('.on').checked=false);
document.getElementById('dl').onclick=()=>{{
  const items=rows.map(r=>({{
    lesson:r.getAttribute('data-rel'),
    tts_enabled:r.querySelector('.on').checked
  }}));
  const blob=new Blob([JSON.stringify({{items}},null,2)],{{type:'application/json'}});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob); a.download='tts_flags.json'; a.click();
}};
</script>
</body></html>"""
    out = root / UPGRADE / "_tts_toggle_board.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    _log(f">> TTS toggle board → {out}", log)
    return out


def import_flags(root: Path, path: Path, log: LogFn = print) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items") or data
    n = 0
    for it in items:
        rel = it.get("lesson") or it.get("path") or ""
        on = bool(it.get("tts_enabled", it.get("on", True)))
        ldir = Path(root) / UPGRADE / rel
        if not ldir.is_dir():
            hits = [x for x in find_lessons(root) if rel in str(x)]
            if not hits:
                continue
            ldir = hits[0]
        set_tts_enabled(ldir, on)
        n += 1
    _log(f">> Imported TTS flags: {n}", log)
    return n


def open_streamlit(log: LogFn = print) -> None:
    app = STREAMLIT_APP if STREAMLIT_APP.exists() else Path.home() / "omnivoice_app.py"
    if not app.exists():
        raise FileNotFoundError(f"Không thấy Streamlit app: {app}")
    py_dir = Path(_resolve_python()).parent
    st_bin = py_dir / "streamlit"
    cmd = [
        str(st_bin if st_bin.exists() else "streamlit"),
        "run",
        str(app),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    env = os.environ.copy()
    env["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    env.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
    _log(f">> Streamlit: {' '.join(cmd)}", log)
    subprocess.Popen(cmd, env=env, cwd=str(app.parent))


def main(argv=None):
    ap = argparse.ArgumentParser(description="OmniVoice TTS for Course OS")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--all", action="store_true", help="TTS toàn khóa (bài enabled)")
    ap.add_argument("--lesson", help="Path tương đối bài trong _upgrade_v2")
    ap.add_argument("--enable-all", action="store_true")
    ap.add_argument("--disable-all", action="store_true")
    ap.add_argument("--enable-lesson")
    ap.add_argument("--disable-lesson")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ref-wav", help="Override ref.wav path")
    ap.add_argument("--language", default="")
    ap.add_argument("--speed", type=float, default=0)
    ap.add_argument("--streamlit", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--toggle-board", action="store_true", help="HTML bật/tắt TTS từng bài")
    ap.add_argument("--playlist", action="store_true", help="HTML playlist các WAV đã render")
    ap.add_argument("--import-flags", help="Import JSON từ toggle board")
    args = ap.parse_args(argv)

    if args.streamlit:
        open_streamlit()
        print("Streamlit launched (check http://localhost:8501)")
        return 0

    if args.ref_wav or args.language or args.speed:
        kw = {}
        if args.ref_wav:
            kw["ref_wav"] = args.ref_wav
        if args.language:
            kw["language"] = args.language
        if args.speed:
            kw["speed"] = args.speed
        set_tts_config(**kw)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.toggle_board:
        print(export_toggle_board(root))
        return 0
    if args.playlist:
        print(export_playlist(root))
        return 0
    if args.import_flags:
        print(import_flags(root, Path(args.import_flags)))
        return 0

    if args.enable_all:
        set_all_lessons(root, True)
        return 0
    if args.disable_all:
        set_all_lessons(root, False)
        return 0
    if args.enable_lesson:
        p = root / UPGRADE / args.enable_lesson
        if not p.is_dir():
            # try match
            hits = [x for x in find_lessons(root) if args.enable_lesson in str(x)]
            p = hits[0] if hits else p
        set_tts_enabled(p, True)
        print(f"ON {p}")
        return 0
    if args.disable_lesson:
        p = root / UPGRADE / args.disable_lesson
        hits = [x for x in find_lessons(root) if args.disable_lesson in str(x)]
        p = hits[0] if hits else p
        set_tts_enabled(p, False)
        print(f"OFF {p}")
        return 0

    if args.status:
        lessons = find_lessons(root)
        on = sum(1 for x in lessons if is_tts_enabled(x))
        done = sum(1 for x in lessons if (x / "tts_omnivoice.wav").exists())
        print(
            json.dumps(
                {
                    "lessons": len(lessons),
                    "tts_on": on,
                    "tts_off": len(lessons) - on,
                    "wav_done": done,
                    "config": get_tts_config(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.lesson:
        ldir = root / UPGRADE / args.lesson
        if not ldir.is_dir():
            hits = [x for x in find_lessons(root) if args.lesson in str(x)]
            if not hits:
                print(f"Không thấy bài: {args.lesson}", file=sys.stderr)
                return 1
            ldir = hits[0]
        set_tts_enabled(ldir, True)
        p = render_lesson(ldir, force=args.force)
        print(p)
        return 0

    if args.all:
        print(json.dumps(render_course(root, force=args.force, limit=args.limit), indent=2))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
