#!/usr/bin/env python3
"""
Sprint V — xuat ke hoach hoc ICS (calendar) tu learn playlist.

  python study_plan.py --all --days 14
  python study_plan.py --course "X" --per-day 2 --write
"""
from __future__ import annotations

import argparse, sys, time, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import common as K
import learn_playlist as LP


def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _dt_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(playlist, start=None, per_day=1, hour=19, duration_min=45, calendar_name="Skool Learn"):
    """Tao noi dung .ics tu playlist items."""
    items = list(playlist.get("items") or [])
    if not items:
        return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
    start = start or datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
    if start.tzinfo is None:
        # local naive ok for floating times; export as UTC-ish local
        pass
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Skool Downloader//Study Plan//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(calendar_name)}",
    ]
    day = 0
    slot = 0
    for it in items:
        if it.get("done"):
            continue
        if slot >= per_day:
            slot = 0
            day += 1
        event_start = start + timedelta(days=day, hours=0)
        # stagger same day by duration
        event_start = event_start + timedelta(minutes=slot * (duration_min + 15))
        event_end = event_start + timedelta(minutes=duration_min)
        uid = f"{it.get('id') or uuid.uuid4().hex}@skool-downloader"
        title = f"[Skool] {it.get('title') or 'Lesson'}"
        desc = f"Course: {it.get('course')}\nPath: {it.get('path')}\n{it.get('reason') or ''}"
        loc = it.get("path") or ""
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_dt_utc(datetime.now(timezone.utc))}",
            f"DTSTART:{event_start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{event_end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{_ics_escape(title)}",
            f"DESCRIPTION:{_ics_escape(desc)}",
            f"LOCATION:{_ics_escape(loc)}",
            "END:VEVENT",
        ]
        slot += 1
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def export_plan(course=None, days=None, per_day=1, hour=19, out=None, log=print):
    pl = LP.build_playlist(course=course, include_done=False)
    # limit by days * per_day if days set
    if days:
        pl = dict(pl)
        pl["items"] = (pl.get("items") or [])[: max(1, int(days) * int(per_day))]
        pl["n"] = len(pl["items"])
    ics = build_ics(pl, per_day=per_day, hour=hour,
                    calendar_name=f"Skool — {course or 'all'}")
    if out is None:
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in str(course or "all")).strip()
        out = C.BASE / "courses" / f"_Study_Plan_{safe}.ics"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ics, encoding="utf-8")
    # also md summary
    md = out.with_suffix(".md")
    LP.save_playlist(pl, course=course or "all")
    log(f">> Study plan ICS: {pl.get('n')} events → {out}")
    return {"path": str(out), "n": pl.get("n"), "playlist": pl}


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Study plan ICS (Sprint V)")
    ap.add_argument("--course")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--per-day", type=int, default=1)
    ap.add_argument("--hour", type=int, default=19)
    ap.add_argument("--out")
    ap.add_argument("--write", action="store_true", default=True)
    a = ap.parse_args()
    course = None if a.all else a.course
    r = export_plan(course=course, days=a.days, per_day=a.per_day, hour=a.hour, out=a.out)
    print(r["path"], f"({r['n']} events)")


if __name__ == "__main__":
    main()
