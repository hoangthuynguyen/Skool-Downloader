#!/usr/bin/env python3
"""
RAG Chat v1 — hierarchical retrieval + Claude.

  python -m rag.chat --course "X" --ask "bài nào nói về webhook?"
  python -m rag.chat --course "X" --index
"""
from __future__ import annotations

import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as C
from rag.index import build_catalog, load_catalog, list_chapters, retrieve


SYS_CHAT = (
    "Bạn là trợ lý học tập cho khóa học đã lưu trữ offline. "
    "Chỉ trả lời dựa trên NGỮ CẢNH được cung cấp (mô tả bài + lời giảng). "
    "Nếu không đủ thông tin, nói rõ là chưa có trong dữ liệu đã tải. "
    "Trả lời bằng tiếng Việt, ngắn gọn, có gạch đầu dòng khi phù hợp. "
    "Cuối câu trả lời, nêu nguồn: tên chương / bài (từ ngữ cảnh)."
)


def answer(root, question, chapter=None, top_k=4, log=print):
    """Tra loi 1 cau hoi. Can Claude API (ai_tools)."""
    import ai_tools
    if not ai_tools.have_api():
        raise RuntimeError(
            "Chat cần API key Claude. Vào Xuất & Báo cáo (hoặc màn Chat) để dán key."
        )
    root = Path(root)
    got = retrieve(root, question, top_k=top_k, chapter=chapter)
    if not got["context"].strip():
        return {
            "answer": "Khóa này chưa có mô tả/lời giảng để chat. Hãy tải bài + tạo phụ đề (video.txt) rồi Index lại.",
            "sources": [],
            "n_indexed": got.get("n_indexed") or 0,
        }
    user = (
        f"Câu hỏi: {question}\n\n"
        f"NGỮ CẢNH (trích từ khóa «{got.get('course') or root.name}»):\n\n"
        f"{got['context']}"
    )
    log(f"RAG: {len(got['sources'])} nguồn, {len(got['context'])} ký tự context")
    text = ai_tools._claude(
        [{"role": "user", "content": user}],
        system=SYS_CHAT,
        max_tokens=2000,
    )
    return {
        "answer": text,
        "sources": got["sources"],
        "n_indexed": got.get("n_indexed") or 0,
        "course": got.get("course"),
    }


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="RAG chat over archived course")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--index", action="store_true", help="Chi xay catalog")
    ap.add_argument("--ask", help="Cau hoi")
    ap.add_argument("--chapter", help="Gioi han 1 chuong")
    ap.add_argument("--list-chapters", action="store_true")
    a = ap.parse_args()
    if a.root:
        C.set_root(a.root)
    elif a.course:
        C.set_course(a.course)
    root = C.ROOT
    if a.index:
        build_catalog(root)
        return
    if a.list_chapters:
        for ch in list_chapters(root):
            print(" -", ch)
        return
    if not a.ask:
        ap.error("Can --ask hoac --index")
    r = answer(root, a.ask, chapter=a.chapter)
    print(r["answer"])
    print("\nNguồn:")
    for s in r.get("sources") or []:
        print(f"  · {s.get('chapter')} / {s.get('title')}")


if __name__ == "__main__":
    main()
