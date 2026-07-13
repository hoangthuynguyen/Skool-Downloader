#!/usr/bin/env python3
"""
Update checker v2 (S3).

So sanh ban local (vid_*.json + file video) voi danh sach chuong remote
tu SkoolBrowser (list chapters) de biet:
  - chuong MOI
  - chuong da co (co the co bai moi — can re-dump de biet chac)
  - bai local con thieu video
  - bai native het han token

CLI:
  python updates.py --course "X" --chapters-file remote.json
  python updates.py --scan-local --course "X"
"""
from __future__ import annotations

import argparse, json
from pathlib import Path
import common as K
import config as C
import progress as P


def saved_chapter_titles(root):
    """Ten chuong da luu (tu _chapters.json + vid_*.json)."""
    root = Path(root)
    titles = set()
    cj = root / "_chapters.json"
    try:
        if cj.exists():
            for t in json.loads(cj.read_text(encoding="utf-8-sig")):
                titles.add(K.san(t if isinstance(t, str) else t.get("title", "")))
    except Exception:
        pass
    # bo sung tu vid_*.json (truong hop thieu _chapters.json)
    try:
        for ct in P._best_chapters(root):
            titles.add(ct)
    except Exception:
        pass
    return titles


def local_lesson_index(root):
    """Index bai local: {chapter_title: [{title, rel, done, native, url}]}."""
    root = Path(root)
    out = {}
    for ch in P.tree(root):
        ct = ch["title"]
        out[ct] = []
        for L in ch.get("lessons") or []:
            out[ct].append({
                "title": L.get("title") or "",
                "rel": L.get("rel") or "",
                "done": bool(L.get("done")),
                "native": bool(L.get("native")),
                "url": L.get("url") or "",
                "host": L.get("host") or "",
            })
    return out


def diff_remote_chapters(root, remote_chapters):
    """So local vs danh sach chuong remote (tu browser list).

    remote_chapters: list[{id, title}] (hoac list str)
    Tra ve dict:
      new_chapters: chuong remote chua co local
      known_chapters: chuong da co
      missing_lessons: bai local thieu video
      native_expired: bai native het han
      scan: progress.scan
      summary text
    """
    root = Path(root)
    known = saved_chapter_titles(root)
    remote = []
    for c in remote_chapters or []:
        if isinstance(c, str):
            remote.append({"id": "", "title": c})
        else:
            remote.append({"id": c.get("id", ""), "title": c.get("title", "")})

    new_chapters = []
    known_chapters = []
    for c in remote:
        t = K.san(c["title"])
        rec = {"id": c.get("id", ""), "title": c["title"], "san": t}
        if t not in known:
            new_chapters.append(rec)
        else:
            known_chapters.append(rec)

    scan = P.scan(root)
    missing = list(scan.get("missing") or [])
    expired = list(scan.get("native_expired") or [])

    # nhom missing theo chuong
    by_chap = {}
    for m in missing:
        by_chap.setdefault(m.get("chapter") or "?", []).append(m)

    n_new = len(new_chapters)
    n_miss = len(missing)
    n_exp = len(expired)
    parts = []
    if n_new:
        parts.append(f"+ {n_new} chương mới")
    if n_miss:
        parts.append(f"+ {n_miss} bài chưa tải (local)")
    if n_exp:
        parts.append(f"~ {n_exp} native hết hạn")
    if not parts:
        parts.append("Không thấy chương mới; local đủ video" if scan.get("has_data") and not n_miss
                     else "Chưa có dữ liệu local / không so được")

    return {
        "root": str(root),
        "known_titles": sorted(known),
        "remote_count": len(remote),
        "new_chapters": new_chapters,
        "known_chapters": known_chapters,
        "missing_lessons": missing,
        "missing_by_chapter": by_chap,
        "native_expired": expired,
        "scan": {
            "total": scan.get("total"), "done": scan.get("done"),
            "size": scan.get("size"), "has_data": scan.get("has_data"),
        },
        "summary": " · ".join(parts),
        "has_updates": bool(n_new or n_miss or n_exp),
    }


def local_health(root):
    """Kiem tra local-only (khong can browser) — badge dashboard."""
    root = Path(root)
    scan = P.scan(root)
    titles = saved_chapter_titles(root)
    badge = P.status_badge(scan)
    return {
        "root": str(root),
        "chapters_saved": len(titles),
        "scan": scan,
        "badge": badge,
        "needs_attention": bool(
            (scan.get("native_expired") or []) or
            ((scan.get("total") or 0) > (scan.get("done") or 0))
        ),
    }


def mark_update_meta(root, diff):
    """Ghi _update_diff.json de GUI/queue doc lai."""
    root = Path(root)
    payload = {
        "summary": diff.get("summary"),
        "has_updates": diff.get("has_updates"),
        "new_chapters": [
            {"id": c.get("id"), "title": c.get("title")} for c in diff.get("new_chapters") or []
        ],
        "missing_count": len(diff.get("missing_lessons") or []),
        "expired_count": len(diff.get("native_expired") or []),
        "scan": diff.get("scan"),
    }
    path = root / "_update_diff.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_update_meta(root):
    p = Path(root) / "_update_diff.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def plan_smart_update(root):
    """Sprint B: ke hoach tai chi bai thieu / chapter delta.

    Tra ve:
      missing_count, chapters_with_gaps (san titles), new_chapters,
      missing_folders, chapter_filter (None | set titles de ONLY_CHAPTERS),
      summary, has_work
    """
    root = Path(root)
    scan = P.scan(root)
    missing = list(scan.get("missing") or [])
    expired = list(scan.get("native_expired") or [])
    meta = read_update_meta(root) or {}
    new_chaps = []
    for c in meta.get("new_chapters") or []:
        t = c.get("title") if isinstance(c, dict) else str(c)
        if t:
            new_chaps.append(K.san(t))

    by_chap = {}
    folders = []
    for m in missing:
        ct = m.get("chapter") or "?"
        by_chap.setdefault(ct, []).append(m)
        fd = m.get("folder")
        if fd is not None:
            folders.append(str(fd))

    gaps = sorted(by_chap.keys())
    # neu co chuong moi trong meta va chuong do con thieu -> uu tien loc chapter delta
    chapter_filter = None
    if new_chaps:
        # san titles trong gaps co the khac raw — so sanh san
        gap_san = {K.san(g) for g in gaps}
        overlap = [t for t in new_chaps if t in gap_san or t in gaps]
        if overlap:
            chapter_filter = set(overlap)
        elif new_chaps and not missing:
            # dump moi chua scan thieu — van goi y loc chuong moi
            chapter_filter = set(new_chaps)

    n_miss = len(missing)
    parts = []
    if new_chaps:
        parts.append(f"{len(new_chaps)} chương mới (meta)")
    if n_miss:
        parts.append(f"{n_miss} bài thiếu video")
        parts.append(f"{len(gaps)} chương có gap")
    if expired:
        parts.append(f"{len(expired)} native hết hạn")
    if not parts:
        parts.append("Đủ video — không cần smart update")

    return {
        "root": str(root),
        "missing_count": n_miss,
        "expired_count": len(expired),
        "chapters_with_gaps": gaps,
        "missing_by_chapter": {k: len(v) for k, v in by_chap.items()},
        "new_chapters": new_chaps,
        "missing_folders": folders,
        "chapter_filter": sorted(chapter_filter) if chapter_filter else None,
        "summary": " · ".join(parts),
        "has_work": bool(n_miss),
        "scan": {
            "total": scan.get("total"), "done": scan.get("done"),
            "size": scan.get("size"), "has_data": scan.get("has_data"),
        },
    }


def apply_smart_update_flags(root, prefer_new_chapters=True):
    """Set C.ONLY_MISSING (+ optional ONLY_CHAPTERS) theo plan. Tra ve plan."""
    plan = plan_smart_update(root)
    C.ONLY_MISSING = True
    C.ONLY_FAILED = False
    if prefer_new_chapters and plan.get("chapter_filter"):
        C.ONLY_CHAPTERS = set(plan["chapter_filter"])
    else:
        C.ONLY_CHAPTERS = None
    return plan


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Update checker v2 + smart plan (Sprint B)")
    ap.add_argument("--course", help="Ten khoa duoi courses/")
    ap.add_argument("--root", help="Override thu muc khoa")
    ap.add_argument("--chapters-file", help="JSON list chuong remote [{id,title}]")
    ap.add_argument("--scan-local", action="store_true", help="Chi quet local health")
    ap.add_argument("--smart-plan", action="store_true",
                    help="In ke hoach smart update (missing + chapter delta)")
    a = ap.parse_args()
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    root = C.ROOT
    if a.smart_plan:
        p = plan_smart_update(root)
        print(json.dumps({
            "summary": p["summary"],
            "has_work": p["has_work"],
            "missing_count": p["missing_count"],
            "chapters_with_gaps": p["chapters_with_gaps"],
            "new_chapters": p["new_chapters"],
            "chapter_filter": p["chapter_filter"],
            "scan": p["scan"],
        }, ensure_ascii=False, indent=2))
        return
    if a.scan_local or not a.chapters_file:
        h = local_health(root)
        print(json.dumps({
            "chapters_saved": h["chapters_saved"],
            "badge": h["badge"],
            "done": h["scan"].get("done"),
            "total": h["scan"].get("total"),
            "missing": len(h["scan"].get("missing") or []),
            "expired": len(h["scan"].get("native_expired") or []),
            "needs_attention": h["needs_attention"],
        }, ensure_ascii=False, indent=2))
        return
    remote = json.loads(Path(a.chapters_file).read_text(encoding="utf-8"))
    d = diff_remote_chapters(root, remote)
    mark_update_meta(root, d)
    print(d["summary"])
    print(f"  new_chapters: {len(d['new_chapters'])}")
    for c in d["new_chapters"]:
        print(f"    + {c['title']}")
    print(f"  missing_lessons: {len(d['missing_lessons'])}")
    print(f"  native_expired: {len(d['native_expired'])}")


if __name__ == "__main__":
    main()
