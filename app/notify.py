#!/usr/bin/env python3
"""
Sprint F — thong bao he thong da-nen (Windows / macOS / Linux).

  from notify import notify
  notify("Skool Downloader", "Da tai xong — 0 fail", level="info")
"""
from __future__ import annotations

import os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "NOTIFICATIONS.log"


def _log(title, message, level="info"):
    try:
        from datetime import datetime
        line = f"{datetime.now().isoformat(timespec='seconds')}  [{level}] {title} - {message}\n"
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def notify(title: str, message: str, level: str = "info") -> bool:
    """Gui thong bao he thong. Tra ve True neu co kenh nao thanh cong."""
    title = (title or "Skool Downloader")[:80]
    message = (message or "")[:240]
    level = level if level in ("info", "error", "warn") else "info"
    _log(title, message, level)
    ok = False
    if sys.platform == "darwin":
        ok = _mac(title, message) or ok
    elif os.name == "nt":
        ok = _windows(title, message, level) or ok
    else:
        ok = _linux(title, message) or ok
    return ok


def _mac(title, message):
    try:
        # escape for AppleScript
        t = title.replace("\\", "\\\\").replace('"', '\\"')
        m = message.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{m}" with title "{t}"'
        subprocess.run(["osascript", "-e", script], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        return True
    except Exception:
        return False


def _windows(title, message, level):
    ps1 = HERE / "notify.ps1"
    try:
        if ps1.exists():
            lv = "error" if level == "error" else "info"
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(ps1), "-Title", title, "-Message", message, "-Level", lv],
                creationflags=0x08000000 if os.name == "nt" else 0,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
    except Exception:
        pass
    # fallback balloon
    try:
        from health_check import notify_windows
        notify_windows(title, message)
        return True
    except Exception:
        return False


def _linux(title, message):
    try:
        r = subprocess.run(
            ["notify-send", title, message],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def notify_pipeline_result(course_name, fails=None, downloaded=None, extra=""):
    """Thong bao sau tai video / pipeline."""
    n_fail = len(fails) if fails is not None else None
    name = course_name or "SkoolCourse"
    if n_fail == 0:
        msg = f"«{name}» sạch — 0 bài fail"
        if downloaded is not None:
            msg += f" · tải mới {downloaded}"
        if extra:
            msg += f" · {extra}"
        return notify("Skool Downloader — Xong", msg, level="info")
    if n_fail and n_fail > 0:
        msg = f"«{name}»: {n_fail} bài fail"
        if extra:
            msg += f" · {extra}"
        return notify("Skool Downloader — Còn fail", msg, level="warn")
    msg = f"«{name}» hoàn tất pipeline"
    if extra:
        msg += f" · {extra}"
    return notify("Skool Downloader", msg, level="info")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("title", nargs="?", default="Skool Downloader")
    ap.add_argument("message", nargs="?", default="Test notification")
    ap.add_argument("--level", default="info")
    a = ap.parse_args()
    print("ok" if notify(a.title, a.message, a.level) else "fallback-log-only")
