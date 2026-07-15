#!/usr/bin/env python3
"""
Lên lịch re-upgrade định kỳ (macOS launchd / Linux cron / Windows Task stub).

  python course_schedule.py --course "X" --install --interval weekly
  python course_schedule.py --list
  python course_schedule.py --uninstall --course "X"
  python course_schedule.py --run-now --course "X"   # depth=quick research+structure
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import config as C

APP = Path(__file__).resolve().parent
LABEL_PREFIX = "com.skooldownloader.upgrade"


def _py() -> str:
    v = APP / "venv" / "bin" / "python"
    if v.exists():
        return str(v)
    return sys.executable


def _plist_path(course: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in course)[:60]
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL_PREFIX}.{safe}.plist"


def _cron_line(course: str, interval: str) -> str:
    py = _py()
    script = APP / "course_incremental.py"
    # weekly Monday 9:00; daily 9:00; monthly 1st 9:00
    if interval == "daily":
        sched = "0 9 * * *"
    elif interval == "monthly":
        sched = "0 9 1 * *"
    else:
        sched = "0 9 * * 1"
    log = Path.home() / "Library" / "Logs" / f"skool-upgrade-{course}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    return (
        f"{sched} cd {APP} && {py} {script} --course {json.dumps(course)} "
        f"--run --research-quick >> {log} 2>&1"
    )


def install_launchd(course: str, interval: str = "weekly") -> Path:
    label = f"{LABEL_PREFIX}.{''.join(c if c.isalnum() else '_' for c in course)[:40]}"
    py = _py()
    script = str(APP / "course_incremental.py")
    log = Path.home() / "Library" / "Logs" / f"skool-upgrade-{course.replace(' ','_')}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    # StartCalendarInterval
    if interval == "daily":
        cal = "    <key>Hour</key><integer>9</integer>\n    <key>Minute</key><integer>0</integer>"
    elif interval == "monthly":
        cal = (
            "    <key>Day</key><integer>1</integer>\n"
            "    <key>Hour</key><integer>9</integer>\n"
            "    <key>Minute</key><integer>0</integer>"
        )
    else:
        cal = (
            "    <key>Weekday</key><integer>1</integer>\n"
            "    <key>Hour</key><integer>9</integer>\n"
            "    <key>Minute</key><integer>0</integer>"
        )
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{py}</string>
    <string>{script}</string>
    <string>--course</string>
    <string>{course}</string>
    <string>--run</string>
    <string>--research-quick</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{APP}</string>
  <key>StartCalendarInterval</key>
  <dict>
{cal}
  </dict>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""
    path = _plist_path(course)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plist, encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
    subprocess.run(["launchctl", "load", str(path)], check=False)
    # registry
    reg = APP / ".upgrade_schedules.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else {}
    except Exception:
        data = {}
    data[course] = {
        "interval": interval,
        "plist": str(path),
        "label": label,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "platform": "launchd",
    }
    reg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Installed launchd: {path}")
    print(f"Log: {log}")
    return path


def install_cron(course: str, interval: str = "weekly") -> None:
    line = _cron_line(course, interval)
    # append if missing
    try:
        cur = subprocess.check_output(["crontab", "-l"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        cur = ""
    marker = f"skool-upgrade:{course}"
    lines = [ln for ln in cur.splitlines() if marker not in ln and ln.strip()]
    lines.append(f"# {marker}")
    lines.append(line)
    proc = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    if proc.returncode != 0:
        raise RuntimeError("crontab install failed")
    reg = APP / ".upgrade_schedules.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else {}
    except Exception:
        data = {}
    data[course] = {
        "interval": interval,
        "platform": "cron",
        "line": line,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
    }
    reg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Installed cron entry.")


def uninstall(course: str) -> None:
    reg = APP / ".upgrade_schedules.json"
    data = {}
    if reg.exists():
        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    info = data.pop(course, None) or {}
    if info.get("platform") == "launchd" or sys.platform == "darwin":
        p = Path(info.get("plist") or _plist_path(course))
        if p.exists():
            subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
            p.unlink(missing_ok=True)
            print(f"Removed {p}")
    if info.get("platform") == "cron":
        try:
            cur = subprocess.check_output(["crontab", "-l"], text=True)
            marker = f"skool-upgrade:{course}"
            lines = []
            skip_next = False
            for ln in cur.splitlines():
                if marker in ln:
                    skip_next = True
                    continue
                if skip_next:
                    skip_next = False
                    continue
                lines.append(ln)
            subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
            print("Removed cron entry.")
        except Exception as e:
            print(f"cron uninstall: {e}")
    reg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_schedules():
    reg = APP / ".upgrade_schedules.json"
    if not reg.exists():
        print("(none)")
        return
    print(reg.read_text(encoding="utf-8"))


def install_windows_task(course: str, interval: str = "weekly") -> None:
    """Windows Task Scheduler (schtasks) — best-effort."""
    if sys.platform != "win32":
        raise RuntimeError("install_windows_task chỉ dùng trên Windows")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in course)[:40]
    task_name = f"SkoolUpgrade_{safe}"
    py = _py()
    script = str(APP / "course_incremental.py")
    # Weekly Monday 09:00 / daily / monthly
    if interval == "daily":
        sched = "/SC DAILY /ST 09:00"
    elif interval == "monthly":
        sched = "/SC MONTHLY /D 1 /ST 09:00"
    else:
        sched = "/SC WEEKLY /D MON /ST 09:00"
    tr = f'"{py}" "{script}" --course "{course}" --run --research-quick'
    cmd = f'schtasks /Create /F /TN "{task_name}" {sched} /TR {tr}'
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "schtasks failed")
    reg = APP / ".upgrade_schedules.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else {}
    except Exception:
        data = {}
    data[course] = {
        "interval": interval,
        "platform": "schtasks",
        "task": task_name,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
    }
    reg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Installed Windows task: {task_name}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Schedule course re-upgrade")
    ap.add_argument("--course")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--interval", default="weekly", choices=["daily", "weekly", "monthly"])
    ap.add_argument("--run-now", action="store_true")
    ap.add_argument(
        "--full",
        action="store_true",
        help="Với --run-now: full quick research+structure (mặc định = incremental)",
    )
    ap.add_argument("--cron", action="store_true", help="Dùng cron thay launchd")
    ap.add_argument("--windows", action="store_true", help="Ép schtasks (Windows)")
    args = ap.parse_args(argv)

    if args.list:
        list_schedules()
        return 0
    if not args.course and (args.install or args.uninstall or args.run_now):
        print("Cần --course")
        return 2
    if args.uninstall:
        uninstall(args.course)
        # Windows
        if sys.platform == "win32":
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in args.course)[:40]
            subprocess.run(
                f'schtasks /Delete /F /TN "SkoolUpgrade_{safe}"',
                shell=True,
                capture_output=True,
            )
        return 0
    if args.install:
        if args.windows or sys.platform == "win32":
            install_windows_task(args.course, args.interval)
        elif args.cron or sys.platform != "darwin":
            install_cron(args.course, args.interval)
        else:
            install_launchd(args.course, args.interval)
        return 0
    if args.run_now:
        C.set_course(args.course)
        # Prefer incremental (cheaper) unless --full
        if getattr(args, "full", False):
            from course_wizard import run_wizard

            run_wizard(
                Path(C.ROOT),
                steps=["inventory", "research", "structure"],
                research_depth="quick",
                do_web=True,
                skip_localize=True,
                skip_video=True,
                skip_publish=True,
            )
        else:
            import course_incremental as INC

            INC.run_incremental(
                Path(C.ROOT),
                research_quick=True,
                force_assets=False,
            )
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
