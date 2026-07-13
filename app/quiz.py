#!/usr/bin/env python3
"""
Sprint N — offline quiz tu knowledge (khong can API).

  python quiz.py --course "X"              # tao + in 5 cau
  python quiz.py --course "X" --build      # ghi _quiz.json
  python quiz.py --course "X" --play       # choi interactive CLI
  python quiz.py --course "X" --n 10
"""
from __future__ import annotations

import argparse, hashlib, json, random, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import common as K

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[A-Za-zÀ-ỹ][A-Za-zÀ-ỹ'’\-]{4,}")
STOP = {
    "that", "this", "with", "from", "have", "will", "your", "they", "them",
    "what", "when", "where", "which", "about", "into", "than", "then", "also",
    "just", "like", "make", "need", "want", "know", "more", "some", "very",
    "there", "their", "would", "could", "should", "being", "been", "were",
    "these", "those", "other", "after", "before", "because", "while", "using",
}


def _load_lessons(root):
    root = Path(root)
    try:
        from rag.index import load_catalog, build_catalog
        full = root / ".rag" / "catalog_full.json"
        if not full.exists():
            try:
                build_catalog(root, log=lambda *_: None)
            except Exception:
                pass
        cat = load_catalog(root, full=True)
        return cat.get("lessons") or []
    except Exception:
        return []


def _sentences(text):
    for s in _SENT_SPLIT.split(text or ""):
        s = re.sub(r"\s+", " ", s).strip()
        if 50 <= len(s) <= 260:
            yield s


def _keywords(sentence):
    words = [w for w in _WORD.findall(sentence) if w.lower() not in STOP]
    words.sort(key=len, reverse=True)
    return words


def build_quiz(root, n=10, seed=None):
    """Tao list cau hoi MCQ offline."""
    lessons = _load_lessons(root)
    rng = random.Random(seed if seed is not None else time.time())
    pool = []
    all_words = []
    for L in lessons:
        text = L.get("text") or L.get("preview") or ""
        for s in _sentences(text):
            kws = _keywords(s)
            if not kws:
                continue
            ans = kws[0]
            pool.append({
                "sentence": s,
                "answer": ans,
                "chapter": L.get("chapter") or "",
                "title": L.get("title") or "",
                "path": L.get("path") or "",
            })
            all_words.extend(kws[:3])
    if not pool:
        return {"questions": [], "n": 0, "course": Path(root).name}

    all_words = list({w.lower(): w for w in all_words}.values())
    rng.shuffle(pool)
    questions = []
    for item in pool:
        if len(questions) >= n:
            break
        ans = item["answer"]
        blank = re.sub(re.escape(ans), "______", item["sentence"], count=1, flags=re.I)
        # distractors
        distractors = [w for w in all_words if w.lower() != ans.lower()]
        rng.shuffle(distractors)
        opts = [ans] + distractors[:3]
        while len(opts) < 4:
            opts.append(f"option{len(opts)}")
        rng.shuffle(opts)
        correct_idx = opts.index(ans) if ans in opts else 0
        qid = hashlib.md5((item["sentence"] + ans).encode()).hexdigest()[:10]
        questions.append({
            "id": qid,
            "prompt": f"Điền từ còn thiếu:\n{blank}",
            "options": opts,
            "answer_index": correct_idx,
            "answer": ans,
            "explanation": item["sentence"],
            "chapter": item["chapter"],
            "title": item["title"],
            "path": item["path"],
        })
    return {
        "course": Path(root).name,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n": len(questions),
        "questions": questions,
    }


def save_quiz(root, quiz):
    root = Path(root)
    path = root / "_quiz.json"
    path.write_text(json.dumps(quiz, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_quiz(root):
    p = Path(root) / "_quiz.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def grade(quiz, answers: dict):
    """answers: {qid: option_index}. Tra ve score dict."""
    qs = quiz.get("questions") or []
    ok = 0
    detail = []
    for q in qs:
        qid = q["id"]
        chosen = answers.get(qid)
        correct = chosen == q.get("answer_index")
        if correct:
            ok += 1
        detail.append({
            "id": qid, "correct": correct,
            "chosen": chosen, "answer_index": q.get("answer_index"),
            "answer": q.get("answer"),
        })
    total = len(qs) or 1
    return {"score": ok, "total": len(qs), "pct": round(100 * ok / total, 1), "detail": detail}


def play_cli(quiz):
    qs = quiz.get("questions") or []
    if not qs:
        print("Khong co cau hoi. Chay --build truoc (can transcript).")
        return
    print(f"=== QUIZ: {quiz.get('course')} — {len(qs)} cau ===\n")
    answers = {}
    for i, q in enumerate(qs, 1):
        print(f"Câu {i}/{len(qs)}")
        print(q["prompt"])
        for j, opt in enumerate(q.get("options") or []):
            print(f"  {j + 1}. {opt}")
        try:
            raw = input("Chọn (1-4, Enter=bỏ): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[dừng]")
            break
        if raw.isdigit() and 1 <= int(raw) <= 4:
            answers[q["id"]] = int(raw) - 1
        print()
    r = grade(quiz, answers)
    print(f"--- Kết quả: {r['score']}/{r['total']} ({r['pct']}%) ---")
    for d in r["detail"]:
        if not d["correct"]:
            print(f"  ✗ {d['id']}: đúng = {d['answer']}")
    return r


def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Offline quiz from course knowledge")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--play", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    root = C.ROOT
    quiz = build_quiz(root, n=a.n, seed=a.seed)
    if a.build or not a.play:
        path = save_quiz(root, quiz)
        print(f">> Quiz: {quiz['n']} câu → {path}")
    if a.json:
        print(json.dumps(quiz, ensure_ascii=False, indent=2))
        return
    if a.play:
        if quiz["n"] == 0:
            print("Khong tao duoc cau (can transcript/index).")
            return
        play_cli(quiz)
    elif not a.build:
        for i, q in enumerate(quiz.get("questions") or [], 1):
            print(f"{i}. {q['prompt'][:120]}…")
            print(f"   → {q['answer']}  [{q.get('title')}]")
            print()


if __name__ == "__main__":
    main()
