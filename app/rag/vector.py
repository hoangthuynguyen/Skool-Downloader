"""
TF-IDF vector retrieval thuan Python (Phase 2) — khong can numpy/torch.

Build luc index: .rag/tfidf.json
Query: cosine similarity tren sparse vectors.
"""
from __future__ import annotations

import json, math, re
from pathlib import Path
from collections import Counter

from rag.index import _rag_dir, _tokens, load_catalog, build_catalog


def _tf(tokens):
    c = Counter(tokens)
    n = sum(c.values()) or 1
    return {t: v / n for t, v in c.items()}


def _idf(docs_tokens):
    """docs_tokens: list[list[str]]"""
    N = len(docs_tokens) or 1
    df = Counter()
    for toks in docs_tokens:
        for t in set(toks):
            df[t] += 1
    return {t: math.log((N + 1) / (df[t] + 1)) + 1.0 for t in df}


def _tfidf_vec(tf, idf):
    return {t: w * idf.get(t, 0.0) for t, w in tf.items() if idf.get(t, 0) > 0}


def _cosine(a, b):
    if not a or not b:
        return 0.0
    # dot
    if len(a) > len(b):
        a, b = b, a
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values())) or 1.0
    nb = math.sqrt(sum(v * v for v in b.values())) or 1.0
    return dot / (na * nb)


def build_tfidf(root, log=print):
    """Xay TF-IDF tu catalog_full. Tra ve meta."""
    root = Path(root)
    cat = load_catalog(root, full=True)
    lessons = cat.get("lessons") or []
    docs_tokens = []
    ids = []
    for i, L in enumerate(lessons):
        text = " ".join([
            L.get("title") or "",
            L.get("chapter") or "",
            L.get("section") or "",
            L.get("text") or "",
        ])
        toks = _tokens(text)
        docs_tokens.append(toks)
        ids.append(i)
    idf = _idf(docs_tokens)
    vectors = []
    for toks in docs_tokens:
        vec = _tfidf_vec(_tf(toks), idf)
        # chi giu top 400 term de file nhe
        if len(vec) > 400:
            top = sorted(vec.items(), key=lambda x: -x[1])[:400]
            vec = dict(top)
        vectors.append(vec)
    payload = {
        "course": cat.get("course"),
        "n": len(vectors),
        "idf": idf,
        "ids": ids,
        # vectors sparse: list of {term: weight}
        "vectors": vectors,
    }
    out = _rag_dir(root) / "tfidf.json"
    # idf co the lon — van OK cho khoa vua
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    log(f">> TF-IDF: {len(vectors)} docs → {out}")
    return {"n": len(vectors), "path": str(out)}


def load_tfidf(root):
    p = _rag_dir(root) / "tfidf.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def retrieve_vector(root, query, top_k=4, chapter=None, max_chars=14000):
    """Retrieve bang TF-IDF. Fallback keyword neu chua co index vector."""
    root = Path(root)
    data = load_tfidf(root)
    cat = load_catalog(root, full=True)
    lessons = cat.get("lessons") or []
    if chapter:
        ch = chapter.lower()
        allowed = {i for i, L in enumerate(lessons)
                   if ch in (L.get("chapter") or "").lower()}
    else:
        allowed = None

    if not data or not data.get("vectors"):
        from rag.index import _retrieve_keyword
        return _retrieve_keyword(root, query, top_k=top_k, chapter=chapter, max_chars=max_chars)

    idf = data.get("idf") or {}
    qvec = _tfidf_vec(_tf(_tokens(query)), idf)
    scored = []
    for i, vec in enumerate(data["vectors"]):
        if allowed is not None and i not in allowed:
            continue
        if i >= len(lessons):
            continue
        s = _cosine(qvec, vec)
        if s > 0:
            scored.append((s, i))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        from rag.index import _retrieve_keyword
        return _retrieve_keyword(root, query, top_k=top_k, chapter=chapter, max_chars=max_chars)

    picked_idx = [i for _, i in scored[:top_k]]
    parts, used, sources = [], 0, []
    for i in picked_idx:
        L = lessons[i]
        header = f"### [{cat.get('course')}] {L.get('section') or L.get('chapter')} — {L.get('title')}"
        body = L.get("text") or ""
        chunk = header + "\n" + body
        if used + len(chunk) > max_chars:
            remain = max_chars - used - len(header) - 20
            if remain < 400:
                break
            chunk = header + "\n" + body[:remain] + "\n…"
        parts.append(chunk)
        used += len(chunk)
        sc = next(s for s, j in scored if j == i)
        sources.append({
            "title": L.get("title"),
            "chapter": L.get("chapter"),
            "section": L.get("section"),
            "path": L.get("path"),
            "course": cat.get("course"),
            "score": round(sc, 4),
            "method": "tfidf",
        })
    return {
        "course": cat.get("course"),
        "context": "\n\n---\n\n".join(parts),
        "sources": sources,
        "n_indexed": cat.get("n_lessons") or 0,
        "method": "tfidf",
    }


def retrieve_multi(roots, query, top_k=6, max_chars=16000):
    """Tim tren nhieu khoa — gop score, lay top_k toan cuc."""
    all_scored = []  # (score, course, lesson, method)
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        data = load_tfidf(root)
        cat = load_catalog(root, full=True)
        lessons = cat.get("lessons") or []
        course = cat.get("course") or root.name
        if data and data.get("vectors"):
            idf = data.get("idf") or {}
            qvec = _tfidf_vec(_tf(_tokens(query)), idf)
            for i, vec in enumerate(data["vectors"]):
                if i >= len(lessons):
                    continue
                s = _cosine(qvec, vec)
                if s > 0.02:
                    all_scored.append((s, course, lessons[i], "tfidf"))
        else:
            from rag.index import score_lesson
            for L in lessons:
                s = score_lesson(query, L)
                if s > 0:
                    all_scored.append((s / 20.0, course, L, "keyword"))  # scale ve ~0-1
    all_scored.sort(key=lambda x: -x[0])
    picked = all_scored[:top_k]
    parts, used, sources = [], 0, []
    for sc, course, L, method in picked:
        header = f"### [{course}] {L.get('section') or L.get('chapter')} — {L.get('title')}"
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
            "course": course,
            "score": round(sc, 4),
            "method": method,
        })
    return {
        "course": " · ".join(sorted({s["course"] for s in sources})) or "multi",
        "context": "\n\n---\n\n".join(parts),
        "sources": sources,
        "n_indexed": len(all_scored),
        "method": "multi",
    }
