#!/usr/bin/env python3
"""
Sprint G — session state: last course + bookmarks.

Luu trong app/.settings.json:
  last_course: str | null
  last_opened_at: iso
  bookmarks: [{id, course, path, title, note, created_at}]
"""
from __future__ import annotations

import json, time, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETTINGS = HERE / ".settings.json"
MAX_BOOKMARKS = 50


def _load():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data):
    SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_last_course():
    s = _load()
    return s.get("last_course"), s.get("last_opened_at")


def set_last_course(course_name):
    """course_name: str | None (None = SkoolCourse legacy)."""
    s = _load()
    s["last_course"] = course_name
    s["last_opened_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save(s)
    return s["last_course"]


def list_bookmarks():
    s = _load()
    bm = s.get("bookmarks") or []
    return list(bm) if isinstance(bm, list) else []


def add_bookmark(course, path, title="", note=""):
    s = _load()
    bm = list(s.get("bookmarks") or [])
    # de-dupe by course+path
    path_s = str(path or "")
    bm = [b for b in bm if not (b.get("course") == course and b.get("path") == path_s)]
    rec = {
        "id": uuid.uuid4().hex[:10],
        "course": course,
        "path": path_s,
        "title": title or Path(path_s).name if path_s else "",
        "note": note or "",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    bm.insert(0, rec)
    s["bookmarks"] = bm[:MAX_BOOKMARKS]
    _save(s)
    return rec


def remove_bookmark(bookmark_id):
    s = _load()
    bm = [b for b in (s.get("bookmarks") or []) if b.get("id") != bookmark_id]
    s["bookmarks"] = bm
    _save(s)
    return len(bm)


def clear_bookmarks():
    s = _load()
    s["bookmarks"] = []
    _save(s)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Session / bookmarks")
    ap.add_argument("--last", action="store_true")
    ap.add_argument("--set-last", metavar="COURSE")
    ap.add_argument("--list-bm", action="store_true")
    ap.add_argument("--add-bm", nargs=2, metavar=("COURSE", "PATH"))
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    if a.set_last is not None:
        set_last_course(a.set_last or None)
        print("last_course =", get_last_course()[0])
        return
    if a.last:
        c, t = get_last_course()
        print(json.dumps({"last_course": c, "last_opened_at": t}, ensure_ascii=False, indent=2))
        return
    if a.add_bm:
        r = add_bookmark(a.add_bm[0], a.add_bm[1], title=a.title)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    if a.list_bm or True:
        print(json.dumps(list_bookmarks(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
