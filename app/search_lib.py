#!/usr/bin/env python3
"""
Tim kiem toan kho khoa (Phase 3) — khong can Claude.

  python search_lib.py "webhook"
  python search_lib.py "automation" --course "X" --top 10
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as C
import progress as P
from rag.index import load_catalog, score_lesson, build_catalog
from rag.vector import load_tfidf, retrieve_multi


def ensure_indexed(root, log=lambda *_: None):
    root = Path(root)
    full = root / ".rag" / "catalog_full.json"
    if not full.exists():
        try:
            build_catalog(root, log=log)
        except Exception as e:
            log(f"[index skip] {root.name}: {e}")


def search_all(query, top_k=12, course=None, ensure_index=False, log=print):
    """Tim tren 1 hoac moi khoa. Tra ve list hit dict."""
    query = (query or "").strip()
    if not query:
        return []

    if course:
        if str(course).lower() in ("skoolcourse", "legacy", "none"):
            roots = [C.BASE / "SkoolCourse"]
        else:
            roots = [C.BASE / "courses" / course]
        roots = [r for r in roots if r.exists()]
    else:
        roots = [m["root"] for m in P.list_course_items()]

    if ensure_index:
        for r in roots:
            ensure_indexed(r, log=log)

    # uu tien multi TF-IDF
    try:
        got = retrieve_multi(roots, query, top_k=top_k, max_chars=50_000)
        hits = []
        for s in got.get("sources") or []:
            hits.append({
                "course": s.get("course"),
                "chapter": s.get("chapter"),
                "title": s.get("title"),
                "section": s.get("section"),
                "path": s.get("path"),
                "score": s.get("score"),
                "method": s.get("method"),
                "preview": "",
            })
        # bo sung preview tu catalog
        by_path = {}
        for r in roots:
            try:
                cat = load_catalog(r, full=True)
                for L in cat.get("lessons") or []:
                    by_path[str(L.get("path") or "")] = L.get("preview") or (L.get("text") or "")[:200]
            except Exception:
                pass
        for h in hits:
            h["preview"] = (by_path.get(h.get("path") or "") or "")[:200]
        if hits:
            return hits
    except Exception as e:
        log(f"[search multi] {e}")

    # fallback keyword tung khoa
    scored = []
    for r in roots:
        try:
            cat = load_catalog(r, full=True)
        except Exception:
            continue
        course_name = cat.get("course") or r.name
        for L in cat.get("lessons") or []:
            s = score_lesson(query, L)
            if s > 0:
                scored.append((s, {
                    "course": course_name,
                    "chapter": L.get("chapter"),
                    "title": L.get("title"),
                    "section": L.get("section"),
                    "path": L.get("path"),
                    "score": s,
                    "method": "keyword",
                    "preview": (L.get("preview") or "")[:200],
                }))
    scored.sort(key=lambda x: -x[0])
    return [h for _, h in scored[:top_k]]


def warehouse_report(base=None):
    """Bao cao markdown tien do toan kho."""
    entries = P.scan_all(base)
    st = P.warehouse_stats(entries)
    lines = [
        "# Skool Archiver — Báo cáo kho khóa",
        "",
        f"- Số khóa: **{st['courses']}**",
        f"- Bài: **{st['done']}/{st['total']}**",
        f"- Dung lượng video: **{st['size']} bytes**",
        f"- Còn thiếu: **{st['missing']}** · Native hết hạn: **{st['expired']}**",
        "",
        "| Khóa | Tiến độ | Dung lượng | Badge |",
        "|------|---------|------------|-------|",
    ]
    for e in entries:
        s = e.get("scan") or {}
        b = e.get("badge") or {}
        tot = s.get("total") or 0
        done = s.get("done") or 0
        size = s.get("size") or 0
        lines.append(
            f"| {e.get('item')} | {done}/{tot} | {size} | {b.get('label','')} |"
        )
    lines.append("")
    return "\n".join(lines), entries


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Search archived Skool courses")
    ap.add_argument("query", nargs="?", help="Tu khoa / cau hoi ngan")
    ap.add_argument("--course", help="Chi 1 khoa")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--index", action="store_true", help="Index thieu truoc khi tim")
    ap.add_argument("--report", action="store_true", help="Xuat bao cao tien do markdown")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.report:
        md, _ = warehouse_report()
        out = C.BASE / "courses" / "_Warehouse_Report.md"
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md, encoding="utf-8")
            print(md)
            print(f"\n>> {out}")
        except Exception:
            print(md)
        return
    if not a.query:
        ap.error("Can query hoac --report")
    hits = search_all(a.query, top_k=a.top, course=a.course, ensure_index=a.index)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return
    print(f"Tìm «{a.query}» — {len(hits)} kết quả:\n")
    for i, h in enumerate(hits, 1):
        print(f"{i}. [{h.get('course')}] {h.get('chapter')} / {h.get('title')}")
        print(f"   score={h.get('score')} method={h.get('method')}")
        if h.get("preview"):
            print(f"   {h['preview'][:160]}…")
        print()


if __name__ == "__main__":
    main()
