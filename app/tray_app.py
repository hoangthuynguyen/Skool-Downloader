#!/usr/bin/env python3
"""
System tray (Phase 5, tuy chon) — can: pip install pystray pillow

  python tray_app.py

Menu: Web Viewer · Health · Dashboard (GUI) · Quit
"""
from __future__ import annotations

import os, subprocess, sys, threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable.replace("pythonw.exe", "python.exe")
NO_WIN = 0x08000000 if os.name == "nt" else 0
_web = None


def _run(args, cwd=None):
    return subprocess.Popen(
        [PY] + args, cwd=str(cwd or HERE),
        creationflags=NO_WIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def start_web(icon=None, item=None):
    global _web
    if _web and _web.poll() is None:
        _open("http://127.0.0.1:8765/")
        return
    _web = _run(["web_viewer.py", "--port", "8765", "--no-browser"])
    threading.Timer(0.8, lambda: _open("http://127.0.0.1:8765/")).start()


def stop_web(icon=None, item=None):
    global _web
    if _web and _web.poll() is None:
        try:
            _web.terminate()
        except Exception:
            pass
    _web = None


def run_health(icon=None, item=None):
    _run(["health_check.py", "--write", "--notify"])


def open_gui(icon=None, item=None):
    _run(["gui.py"])


def _open(url):
    import webbrowser
    webbrowser.open(url)


def quit_app(icon, item=None):
    stop_web()
    icon.stop()


def main():
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("Can: pip install pystray pillow")
        print("Fallback: python gui.py")
        sys.exit(1)

    # icon monochrome 64x64
    img = Image.new("RGB", (64, 64), "#111114")
    d = ImageDraw.Draw(img)
    d.rectangle((12, 12, 52, 52), outline="#ffffff", width=3)
    d.rectangle((22, 24, 42, 40), fill="#ffffff")

    menu = pystray.Menu(
        pystray.MenuItem("Web Viewer", start_web, default=True),
        pystray.MenuItem("Dừng Web", stop_web),
        pystray.MenuItem("Health check", run_health),
        pystray.MenuItem("Mở GUI", open_gui),
        pystray.MenuItem("Thoát", quit_app),
    )
    icon = pystray.Icon("skool_archiver", img, "Skool Archiver", menu)
    icon.run()


if __name__ == "__main__":
    main()
