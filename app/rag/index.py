"""
Xay catalog text theo chuong/bai (khong can vector DB — Phase 1 hierarchical).
"""
from __future__ import annotations

import json, re, time
from pathlib import Path

import export as E


def _rag_dir(root: Path) -> Path:
    d = Path(root) / ".rag"
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_catalog(root, log=print):
    """Gom description + transcript theo bai. Luu .rag/catalog.json."""
    root = Path(root)
    title, blocks = E.gather_course(root)
    lessons = []
    current_section = []
    for b in blocks:
        if b["kind"] == "section":
            # cap nhat breadcrumb
            depth = b["depth"]
            current_section = current_section[: max(0, depth - 1)]
            current_section.append(b["title"])
            continue
        # lesson
        chapter = current_section[0] if current_section else (b["title"] or "Khác")
        section_path = " / ".join(current_section) if current_section else chapter
        text_parts = []
        if b.get("desc"):
            text_parts.append(b["desc"])
        if b.get("transcript"):
            text_parts.append(b["transcript"])
        body = "\n\n".join(text_parts).strip()
        if not body:
            continue
        lessons.append({
            "title": b["title"],
            "chapter": chapter,
            "section": section_path,
            "path": str(b.get("path") or ""),
            "chars": len(body),
            "preview": body[:240].replace("\n", " "),
            "text": body,
        })
    cat = {
        "course": title,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "lessons": lessons,
        "n_lessons": len(lessons),
        "n_chars": sum(L["chars"] for L in lessons),
    }
    out = _rag_dir(root) / "catalog.json"
    # luu ban nhe (khong text) + ban day du
    light = {**cat, "lessons": [
        {k: v for k, v in L.items() if k != "text"} for L in lessons
    ]}
    out.write_text(json.dumps(light, ensure_ascii=False, indent=2), encoding="utf-8")
    full = _rag_dir(root) / "catalog_full.json"
    full.write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    log(f">> RAG index: {len(lessons)} bài, {cat['n_chars']} ký tự → {out}")
    # Phase 2: TF-IDF vector index (best-effort)
    try:
        from rag.vector import build_tfidf
        build_tfidf(root, log=log)
    except Exception as e:
        log(f"[rag vector] skip: {e}")
    return cat


def load_catalog(root, full=True):
    root = Path(root)
    path = _rag_dir(root) / ("catalog_full.json" if full else "catalog.json")
    if not path.exists():
        return build_catalog(root, log=lambda *_: None)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return build_catalog(root, log=lambda *_: None)


def list_chapters(root):
    cat = load_catalog(root, full=False)
    seen = []
    for L in cat.get("lessons") or []:
        ch = L.get("chapter") or "?"
        if ch not in seen:
            seen.append(ch)
    return seen


def _tokens(s):
    s = (s or "").lower()
    # tach tu: chu+so, bo stopword ngan
    words = re.findall(r"[a-z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ_]{2,}", s, re.I)
    stop = {"the", "and", "for", "with", "this", "that", "from", "are", "was", "what",
            "how", "các", "của", "và", "là", "cho", "một", "những", "trong", "với",
            "có", "được", "không", "này", "khi", "về", "bài", "học"}
    return [w for w in words if w not in stop]


def score_lesson(query, lesson):
    q = _tokens(query)
    if not q:
        return 0.0
    hay = " ".join([
        lesson.get("title") or "",
        lesson.get("chapter") or "",
        lesson.get("section") or "",
        (lesson.get("text") or lesson.get("preview") or "")[:8000],
    ]).lower()
    score = 0.0
    for w in q:
        if w in (lesson.get("title") or "").lower():
            score += 4
        if w in (lesson.get("chapter") or "").lower():
            score += 2
        c = hay.count(w)
        if c:
            score += min(c, 5) * 1.0
    # bonus neu ca cum tu ngan
    ql = (query or "").lower().strip()
    if len(ql) >= 4 and ql in hay:
        score += 6
    return score


def retrieve(root, query, top_k=4, chapter=None, max_chars=14000, method="auto"):
    """Lay top-k bai lien quan. method: auto|tfidf|keyword."""
    if method in ("auto", "tfidf"):
        try:
            from rag.vector import load_tfidf, retrieve_vector
            if method == "tfidf" or load_tfidf(root):
                return retrieve_vector(root, query, top_k=top_k, chapter=chapter,
                                       max_chars=max_chars)
        except Exception:
            pass
    return _retrieve_keyword(root, query, top_k=top_k, chapter=chapter, max_chars=max_chars)


def _retrieve_keyword(root, query, top_k=4, chapter=None, max_chars=14000):
    """Keyword scoring (Phase 1)."""
    cat = load_catalog(root, full=True)
    lessons = cat.get("lessons") or []
    if chapter:
        ch_san = chapter.lower()
        lessons = [L for L in lessons if ch_san in (L.get("chapter") or "").lower()]
    scored = []
    for L in lessons:
        s = score_lesson(query, L)
        if s > 0:
            scored.append((s, L))
    scored.sort(key=lambda x: -x[0])
    if not scored and lessons:
        picked = lessons[: min(top_k, 2)]
    else:
        picked = [L for _, L in scored[:top_k]]

    parts = []
    used = 0
    sources = []
    for L in picked:
        header = f"### {L.get('section') or L.get('chapter')} — {L.get('title')}"
        body = L.get("text") or ""
        chunk = header + "\n" + body
        if used + len(chunk) > max_chars:
            remain = max_chars - used - len(header) - 20
            if remain < 400:
                break
            chunk = header + "\n" + body[:remain] + "\n…"
        parts.append(chunk)
        used += len(chunk)
        sources.append({
            "title": L.get("title"),
            "chapter": L.get("chapter"),
            "section": L.get("section"),
            "path": L.get("path"),
            "course": cat.get("course"),
            "score": score_lesson(query, L),
            "method": "keyword",
        })
    return {
        "course": cat.get("course"),
        "context": "\n\n---\n\n".join(parts),
        "sources": sources,
        "n_indexed": cat.get("n_lessons") or 0,
        "method": "keyword",
    }
