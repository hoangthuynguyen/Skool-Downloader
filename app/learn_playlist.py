#!/usr/bin/env python3
"""
Sprint P — playlist «Học tiếp» tu bookmarks + quiz scores.

  python learn_playlist.py --course "X"
  python learn_playlist.py --all
  python learn_playlist.py --record-quiz --course X --score 7 --total 10
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import session_state as SS


def record_quiz_score(course, score, total, path=None):
    """Luu diem quiz vao settings (quiz_scores)."""
    s = SS._load()
    scores = s.get("quiz_scores") or {}
    key = course or "SkoolCourse"
    scores[key] = {
        "score": int(score),
        "total": int(total),
        "pct": round(100 * int(score) / max(1, int(total)), 1),
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "last_path": path or "",
    }
    s["quiz_scores"] = scores
    # lich su ngan
    hist = list(s.get("quiz_history") or [])
    hist.insert(0, {"course": key, **scores[key]})
    s["quiz_history"] = hist[:40]
    SS._save(s)
    return scores[key]


def get_quiz_scores():
    s = SS._load()
    return s.get("quiz_scores") or {}


def mark_bookmark_done(bookmark_id, done=True):
    s = SS._load()
    bm = list(s.get("bookmarks") or [])
    for b in bm:
        if b.get("id") == bookmark_id:
            b["done"] = bool(done)
            b["done_at"] = time.strftime("%Y-%m-%dT%H:%M:%S") if done else None
    s["bookmarks"] = bm
    SS._save(s)


def build_playlist(course=None, include_done=False):
    """Ghep bookmarks (+ diem quiz) thanh playlist hoc.

    Item: {rank, course, title, path, id, quiz_pct, reason, done}
    """
    bms = SS.list_bookmarks()
    scores = get_quiz_scores()
    items = []
    for b in bms:
        c = b.get("course")
        if course and c != course and str(course) not in (c or ""):
            continue
        if not include_done and b.get("done"):
            continue
        qs = scores.get(c) or scores.get(course or "") or {}
        pct = qs.get("pct")
        # uu tien: chua hoc, diem quiz thap, moi bookmark
        priority = 0
        if b.get("done"):
            priority += 100
        if pct is not None and pct < 70:
            priority -= 10  # hoc lai
        reason = "bookmark"
        if pct is not None and pct < 70:
            reason = f"quiz {pct}% — ôn lại"
        items.append({
            "id": b.get("id"),
            "course": c,
            "title": b.get("title") or Path(b.get("path") or "").name,
            "path": b.get("path") or "",
            "note": b.get("note") or "",
            "done": bool(b.get("done")),
            "quiz_pct": pct,
            "reason": reason,
            "created_at": b.get("created_at"),
            "priority": priority,
        })
    # sap xep: priority thap hon truoc, roi moi hon
    items.sort(key=lambda x: (x["priority"], x.get("created_at") or ""), reverse=False)
    for i, it in enumerate(items, 1):
        it["rank"] = i
    return {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "course_filter": course,
        "n": len(items),
        "items": items,
        "next": items[0] if items else None,
    }


def save_playlist(playlist, course=None):
    out_dir = C.BASE / "courses"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = course or "all"
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in str(name)).strip() or "all"
    path = out_dir / f"_Learn_Playlist_{safe}.md"
    lines = [
        f"# Học tiếp — {name}",
        "",
        f"_Built: {playlist.get('built_at')}_ · **{playlist.get('n')}** mục",
        "",
    ]
    nxt = playlist.get("next")
    if nxt:
        lines += [
            "## Tiếp theo",
            f"1. **{nxt.get('title')}** (`{nxt.get('course')}`)",
            f"   - {nxt.get('path')}",
            f"   - {nxt.get('reason')}",
            "",
            "## Danh sách",
            "",
        ]
    for it in playlist.get("items") or []:
        mark = "x" if it.get("done") else " "
        q = f" · quiz {it['quiz_pct']}%" if it.get("quiz_pct") is not None else ""
        lines.append(f"- [{mark}] **{it.get('title')}** — {it.get('course')}{q}")
        if it.get("path"):
            lines.append(f"  - `{it['path']}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Learn playlist (Sprint P)")
    ap.add_argument("--course")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--include-done", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--record-quiz", action="store_true")
    ap.add_argument("--score", type=int, default=0)
    ap.add_argument("--total", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.record_quiz:
        if not a.course:
            ap.error("--record-quiz can --course")
        r = record_quiz_score(a.course, a.score, a.total or max(a.score, 1))
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    course = None if a.all else a.course
    pl = build_playlist(course=course, include_done=a.include_done)
    if a.write:
        p = save_playlist(pl, course=course or "all")
        print(f">> {p}")
    if a.json:
        print(json.dumps(pl, ensure_ascii=False, indent=2))
        return
    print(f"Playlist: {pl['n']} mục")
    if pl.get("next"):
        n = pl["next"]
        print(f"  NEXT: [{n.get('course')}] {n.get('title')}")
        print(f"        {n.get('path')}")
        print(f"        ({n.get('reason')})")
    for it in (pl.get("items") or [])[:15]:
        print(f"  {it['rank']}. {it.get('title')} · {it.get('course')} · {it.get('reason')}")


if __name__ == "__main__":
    main()
