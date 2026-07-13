#!/usr/bin/env python3
"""
Sprint M — xuat flashcards Anki (TSV) tu transcript / description.

  python anki_export.py --course "X"
  python anki_export.py --course "X" --out cards.tsv --max 200
  python anki_export.py --course "X" --cloze

Anki: File → Import → chon TSV, Front/Back (hoac Text cloze).
"""
from __future__ import annotations

import argparse, csv, hashlib, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import common as K

# cau huu ich: do dai hop ly, co chu
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[A-Za-zÀ-ỹ][A-Za-zÀ-ỹ'’\-]{3,}")


def _lesson_texts(root: Path):
    """Yield (chapter, title, path, text)."""
    root = Path(root)
    # uu tien catalog
    try:
        from rag.index import load_catalog
        cat = load_catalog(root, full=True)
        for L in cat.get("lessons") or []:
            text = (L.get("text") or L.get("preview") or "").strip()
            if text:
                yield L.get("chapter") or "", L.get("title") or "", L.get("path") or "", text
        if cat.get("lessons"):
            return
    except Exception:
        pass
    for p in sorted(root.rglob("video.txt")):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not text.strip():
            continue
        rel = p.parent.relative_to(root)
        parts = rel.parts
        chapter = parts[0] if parts else ""
        title = p.parent.name
        yield chapter, title, str(p.parent), text
    for p in sorted(root.rglob("description.md")):
        if (p.parent / "video.txt").exists():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if len(text.strip()) < 40:
            continue
        rel = p.parent.relative_to(root)
        parts = rel.parts
        yield (parts[0] if parts else ""), p.parent.name, str(p.parent), text


def _sentences(text: str):
    for s in _SENT_SPLIT.split(text or ""):
        s = re.sub(r"\s+", " ", s).strip()
        if 40 <= len(s) <= 280:
            yield s


def _key_word(sentence: str):
    """Chon tu dai de cloze (tranh the/a/is)."""
    stop = {
        "that", "this", "with", "from", "have", "will", "your", "they", "them",
        "what", "when", "where", "which", "about", "into", "than", "then", "also",
        "just", "like", "make", "need", "want", "know", "more", "some", "very",
        "there", "their", "would", "could", "should", "being", "been", "were",
    }
    words = _WORD.findall(sentence)
    cands = [w for w in words if w.lower() not in stop and len(w) >= 5]
    if not cands:
        return None
    # uu tien tu dai nhat (thuong la thuat ngu)
    return max(cands, key=len)


def make_cards(root, max_cards=150, cloze=False, min_per_lesson=1, max_per_lesson=3):
    """Tao list card dict {front, back, tags, source}."""
    cards = []
    seen = set()
    for chapter, title, path, text in _lesson_texts(root):
        sents = list(_sentences(text))
        if not sents:
            continue
        # lay cau o giua bai (noi dung chinh)
        mid = sents[len(sents) // 4: max(len(sents) // 4 + 1, 3 * len(sents) // 4)]
        if not mid:
            mid = sents
        n = 0
        for s in mid:
            if n >= max_per_lesson or len(cards) >= max_cards:
                break
            h = hashlib.md5(s.encode("utf-8")).hexdigest()[:12]
            if h in seen:
                continue
            seen.add(h)
            tags = f"{K.san(chapter) or 'course'} {K.san(title)[:40]}".replace(" ", "_")
            if cloze:
                w = _key_word(s)
                if not w:
                    continue
                front = re.sub(re.escape(w), "{{c1::" + w + "}}", s, count=1)
                back = s
                cards.append({
                    "front": front, "back": back, "tags": tags,
                    "source": title, "chapter": chapter, "type": "cloze",
                })
            else:
                # Basic: Q = cau co blank, A = tu
                w = _key_word(s)
                if not w:
                    # fallback: front = tieu de, back = cau
                    front = f"[{chapter}] {title}\n\nKey idea?"
                    back = s
                else:
                    blank = re.sub(re.escape(w), "______", s, count=1)
                    front = f"Fill in:\n{blank}"
                    back = f"{w}\n\nFull: {s}"
                cards.append({
                    "front": front, "back": back, "tags": tags,
                    "source": title, "chapter": chapter, "type": "basic",
                })
            n += 1
            if n < min_per_lesson and len(mid) > n:
                continue
        if len(cards) >= max_cards:
            break
    return cards


def write_tsv(cards, out_path: Path, cloze=False):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Anki import: tab-separated, no header preferred for simple decks
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n",
                       quoting=csv.QUOTE_MINIMAL)
        for c in cards:
            tags = c.get("tags") or ""
            w.writerow([c["front"], c["back"], tags])
    # readme
    readme = out_path.with_suffix(".md")
    readme.write_text(
        f"# Anki import\n\n"
        f"- File: `{out_path.name}`\n"
        f"- Cards: {len(cards)}\n"
        f"- Type: {'cloze' if cloze else 'basic (Front/Back)'}\n\n"
        f"Anki → File → Import → chọn TSV → Field 1=Front, Field 2=Back, Field 3=Tags.\n"
        f"Nếu cloze: dùng note type Cloze, map field Text = Field 1.\n",
        encoding="utf-8",
    )
    return out_path


def export_course(root, course_name=None, out=None, max_cards=150, cloze=False, log=print):
    root = Path(root)
    course_name = course_name or root.name
    cards = make_cards(root, max_cards=max_cards, cloze=cloze)
    if out is None:
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in course_name).strip()
        out = C.BASE / "courses" / f"{safe}_Anki.tsv"
    out = Path(out)
    write_tsv(cards, out, cloze=cloze)
    log(f">> Anki: {len(cards)} cards → {out}")
    return {"path": str(out), "cards": len(cards), "cloze": cloze}


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Export Anki TSV flashcards")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--out")
    ap.add_argument("--max", type=int, default=150)
    ap.add_argument("--cloze", action="store_true")
    a = ap.parse_args()
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    r = export_course(C.ROOT, course_name=C.COURSE or C.ROOT.name,
                      out=a.out, max_cards=a.max, cloze=a.cloze)
    print(r)


if __name__ == "__main__":
    main()
