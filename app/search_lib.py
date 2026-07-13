#!/usr/bin/env python3
"""
Tim kiem toan kho khoa (Phase 3) + Sprint C snippet/highlight.

  python search_lib.py "webhook"
  python search_lib.py "automation" --course "X" --top 10
  python search_lib.py "prompt" --snippet
"""
from __future__ import annotations

import argparse, json, re, sys
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


def _tokens(query: str):
    return [t for t in re.split(r"\s+", (query or "").strip().lower()) if len(t) >= 2]


def make_snippet(text: str, query: str, radius: int = 90, mark: str = "**", mark_close: str = None):
    """Trich doan xung quanh match dau tien; boi dam bang mark...mark_close."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    open_m = mark or "**"
    close_m = mark_close if mark_close is not None else open_m
    if not text or not (query or "").strip():
        return {"snippet": (text or "")[: radius * 2], "match": "", "start": -1}
    low = text.lower()
    q = query.strip()
    # uu tien cum tu day du
    idx = low.find(q.lower())
    match = q
    if idx < 0:
        for t in _tokens(q):
            idx = low.find(t)
            if idx >= 0:
                match = text[idx: idx + len(t)]
                break
    if idx < 0:
        plain = " ".join(text.split())
        return {"snippet": plain[: radius * 2], "match": "", "start": -1}
    start = max(0, idx - radius)
    end = min(len(text), idx + len(match) + radius)
    chunk = text[start:end]
    # highlight trong chunk
    rel = idx - start
    highlighted = (
        chunk[:rel]
        + f"{open_m}{chunk[rel: rel + len(match)]}{close_m}"
        + chunk[rel + len(match):]
    )
    highlighted = " ".join(highlighted.split())
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return {
        "snippet": f"{prefix}{highlighted}{suffix}",
        "match": match,
        "start": idx,
    }


def _read_lesson_text(folder: Path, max_chars: int = 120_000) -> str:
    """Gom transcript / description / srt de highlight."""
    parts = []
    for name in ("video.txt", "description.md", "video.srt", "Transcript_VI.md",
                 "PhuDe_SongNgu.srt"):
        p = folder / name
        if p.is_file():
            try:
                parts.append(p.read_text(encoding="utf-8", errors="ignore")[:max_chars // 2])
            except Exception:
                pass
    return "\n".join(parts)[:max_chars]


def resolve_lesson_folder(path_str, roots=None):
    """Tim Path folder bai tu hit path (catalog path hoac abs)."""
    if not path_str:
        return None
    p = Path(path_str)
    if p.is_dir():
        return p
    if p.is_file():
        return p.parent
    # thu ghép voi roots
    for r in roots or []:
        cand = Path(r) / path_str
        if cand.is_dir():
            return cand
        if cand.is_file():
            return cand.parent
        # path co the la rel lesson
        try:
            for hit in Path(r).rglob(p.name):
                if hit.is_dir():
                    return hit
        except Exception:
            pass
    return p if p.exists() else None


def enrich_hit_snippet(hit: dict, query: str, roots=None, mark: str = "**", mark_close: str = None) -> dict:
    """Them snippet, highlight, folder vao hit."""
    h = dict(hit)
    folder = resolve_lesson_folder(h.get("path"), roots=roots)
    if folder is None and h.get("path"):
        folder = Path(h["path"])
    text = ""
    if folder and Path(folder).exists():
        text = _read_lesson_text(Path(folder))
        h["folder"] = str(Path(folder).resolve())
    if not text:
        text = h.get("preview") or ""
    sn = make_snippet(text, query, mark=mark, mark_close=mark_close)
    h["snippet"] = sn["snippet"]
    h["match"] = sn.get("match") or ""
    if not h.get("preview") and sn["snippet"]:
        h["preview"] = sn["snippet"][:200]
    return h


def search_all(query, top_k=12, course=None, ensure_index=False, log=print,
               with_snippet=True, mark="**", mark_close=None):
    """Tim tren 1 hoac moi khoa. Tra ve list hit dict (co snippet neu with_snippet)."""
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

    hits = []
    # uu tien multi TF-IDF
    try:
        got = retrieve_multi(roots, query, top_k=top_k, max_chars=50_000)
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
    except Exception as e:
        log(f"[search multi] {e}")
        hits = []

    if not hits:
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
        hits = [h for _, h in scored[:top_k]]

    if with_snippet:
        hits = [enrich_hit_snippet(h, query, roots=roots, mark=mark, mark_close=mark_close)
                for h in hits]
    return hits[:top_k]


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
    ap.add_argument("--snippet", action="store_true", default=True,
                    help="Hien snippet highlight (mac dinh bat)")
    ap.add_argument("--no-snippet", action="store_true")
    ap.add_argument("--open-first", action="store_true",
                    help="In duong dan folder bai dau (de mo)")
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
    with_snip = not a.no_snippet
    hits = search_all(a.query, top_k=a.top, course=a.course, ensure_index=a.index,
                      with_snippet=with_snip)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return
    print(f"Tìm «{a.query}» — {len(hits)} kết quả:\n")
    for i, h in enumerate(hits, 1):
        print(f"{i}. [{h.get('course')}] {h.get('chapter')} / {h.get('title')}")
        print(f"   score={h.get('score')} method={h.get('method')}")
        sn = h.get("snippet") or h.get("preview") or ""
        if sn:
            print(f"   {sn[:220]}")
        if h.get("folder"):
            print(f"   📁 {h['folder']}")
        print()
    if a.open_first and hits:
        f = hits[0].get("folder") or hits[0].get("path")
        if f:
            print(f"OPEN:{f}")


if __name__ == "__main__":
    main()
