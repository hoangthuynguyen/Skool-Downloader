"""
Dense embedding local (Phase 5, tuy chon).

Neu co sentence-transformers: dung model nhe multilingual.
Khong co: tra None — RAG van dung TF-IDF.

  pip install sentence-transformers
Model mac dinh: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
Override: SKOOL_EMBED_MODEL=...
"""
from __future__ import annotations

import json, math, os
from pathlib import Path

from rag.index import _rag_dir, load_catalog


_MODEL = None
_MODEL_NAME = None


def available():
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


def model_name():
    return os.environ.get(
        "SKOOL_EMBED_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )


def _get_model(log=print):
    global _MODEL, _MODEL_NAME
    name = model_name()
    if _MODEL is not None and _MODEL_NAME == name:
        return _MODEL
    from sentence_transformers import SentenceTransformer
    log(f">> Loading embed model: {name} (lan dau co the tai model)…")
    _MODEL = SentenceTransformer(name)
    _MODEL_NAME = name
    return _MODEL


def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def build_embeddings(root, log=print, batch_size=32):
    """Xay .rag/embeddings.json. Tra ve meta hoac None neu thieu lib."""
    if not available():
        log("[embed] sentence-transformers chua cai — bo qua dense index")
        return None
    root = Path(root)
    cat = load_catalog(root, full=True)
    lessons = cat.get("lessons") or []
    if not lessons:
        return {"n": 0}
    texts = []
    for L in lessons:
        texts.append("\n".join([
            L.get("title") or "",
            L.get("chapter") or "",
            (L.get("text") or "")[:4000],
        ]))
    model = _get_model(log=log)
    vectors = model.encode(texts, batch_size=batch_size, show_progress_bar=False,
                           normalize_embeddings=True)
    payload = {
        "model": model_name(),
        "n": len(lessons),
        "dim": int(len(vectors[0])) if len(vectors) else 0,
        "vectors": [v.tolist() if hasattr(v, "tolist") else list(v) for v in vectors],
    }
    out = _rag_dir(root) / "embeddings.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    log(f">> Dense embeddings: {payload['n']} × {payload['dim']} → {out}")
    return {"n": payload["n"], "dim": payload["dim"], "path": str(out)}


def load_embeddings(root):
    p = _rag_dir(root) / "embeddings.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def retrieve_dense(root, query, top_k=4, chapter=None, max_chars=14000):
    """Retrieve bang dense cosine. Fallback None neu thieu data/model."""
    if not available():
        return None
    data = load_embeddings(root)
    if not data or not data.get("vectors"):
        return None
    cat = load_catalog(root, full=True)
    lessons = cat.get("lessons") or []
    model = _get_model(log=lambda *_: None)
    qv = model.encode([query], normalize_embeddings=True)[0]
    qv = qv.tolist() if hasattr(qv, "tolist") else list(qv)

    allowed = None
    if chapter:
        ch = chapter.lower()
        allowed = {i for i, L in enumerate(lessons)
                   if ch in (L.get("chapter") or "").lower()}

    scored = []
    for i, vec in enumerate(data["vectors"]):
        if i >= len(lessons):
            break
        if allowed is not None and i not in allowed:
            continue
        s = _cosine(qv, vec)
        if s > 0.15:
            scored.append((s, i))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return None

    parts, used, sources = [], 0, []
    for s, i in scored[:top_k]:
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
        sources.append({
            "title": L.get("title"),
            "chapter": L.get("chapter"),
            "section": L.get("section"),
            "path": L.get("path"),
            "course": cat.get("course"),
            "score": round(float(s), 4),
            "method": "dense",
        })
    return {
        "course": cat.get("course"),
        "context": "\n\n---\n\n".join(parts),
        "sources": sources,
        "n_indexed": cat.get("n_lessons") or 0,
        "method": "dense",
    }
