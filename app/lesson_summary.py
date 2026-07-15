#!/usr/bin/env python3
"""
Tóm tắt từng bài học / video bằng LLM — tiếng Việt.

Mỗi bài (folder có description.md hoặc video.txt) → summary.vi.md:

  - Purpose of the video (Mục đích)
  - Summary (độ dài theo nguồn: ngắn 500 / TB 700 / dài 1000 / siêu dài 1500 từ)
  - Key takeaways
  - Todo list chi tiết, từng bước
  - Quotes
  - Resources

  python lesson_summary.py --course "TenKhoa"
  python lesson_summary.py --course "X" --lesson "01 - A/02 - B"
  python lesson_summary.py --course "X" --force          # ghi đè summary đã có
  python lesson_summary.py --course "X" --missing-only   # mặc định: chỉ bài chưa có
  python lesson_summary.py --course "X" --combine-only   # chỉ gộp _All_Summaries.vi.md
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import config as C

OUT_NAME = "summary.vi.md"
ALL_NAME = "_All_Summaries.vi.md"
SOURCE_NAMES = ("description.md", "video.txt", "notes.md", "links.md")

SYSTEM = """Bạn là trợ lý đào tạo chuyên nghiệp. Viết HOÀN TOÀN bằng TIẾNG VIỆT rõ ràng, tự nhiên.
Dựa CHỈ trên nội dung nguồn được cung cấp — không bịa thông tin, số liệu hay link không có trong nguồn.
Nếu thiếu dữ liệu cho một mục, ghi "(không có trong nguồn)" thay vì bịa.
Giữ thuật ngữ kỹ thuật tiếng Anh khi cần (kèm giải thích ngắn).
Định dạng Markdown."""

PROMPT_TEMPLATE = """Hãy tạo bản tóm tắt học tập cho BÀI HỌC sau.

## Thông tin bài
- Khóa: {course}
- Đường dẫn bài: {lesson_path}
- Tiêu đề: {title}
- Độ dài nguồn (ước lượng): ~{source_words} từ
- **Độ dài Summary yêu cầu: khoảng {target_words} từ** (±15% chấp nhận được)

## Cấu trúc BẮT BUỘC (đúng thứ tự, tiêu đề tiếng Anh như dưới, nội dung tiếng Việt)

# {title}

## Purpose of the video
Mục đích video / bài học: người học sẽ đạt được gì sau khi xem (3–6 câu).

## Summary
Tóm tắt nội dung chính, mạch lạc, khoảng **{target_words} từ**.
Viết thành đoạn văn hoặc mục nhỏ — đủ chi tiết theo độ dài yêu cầu (không cắt quá ngắn nếu nguồn dài).

## Key takeaways
5–12 ý then chốt (gạch đầu dòng). Mỗi ý 1–2 câu, actionable.

## Todo list (step by step)
Danh sách việc cần làm sau bài, **chi tiết từng bước**:
1. Bước lớn
   - Việc con 1
   - Việc con 2
2. ...
Càng cụ thể càng tốt (công cụ, thứ tự, checklist).

## Quotes
Trích dẫn đáng nhớ từ nguồn (nếu có). Format:
> "…"
— ngữ cảnh ngắn
Nếu không có: (không có trong nguồn)

## Resources
Tài nguyên / link / file / công cụ được nhắc trong nguồn (mô tả tiếng Việt + giữ URL gốc).
Nếu không có: (không có trong nguồn)

---

## NỘI DUNG NGUỒN

{content}
"""


def _log(msg: str, log: Callable = print):
    log(msg)


def estimate_words(text: str) -> int:
    """Ước số từ (hỗ trợ EN + khoảng trắng; CJK đếm theo ký tự/2)."""
    t = (text or "").strip()
    if not t:
        return 0
    # latin words
    latin = re.findall(r"[A-Za-z0-9']+", t)
    # strip latin for cjk-ish
    rest = re.sub(r"[A-Za-z0-9\s\W]+", "", t)
    cjk = max(0, len(rest) // 2)
    return len(latin) + cjk


def summary_tier(source_words: int) -> Tuple[str, int]:
    """
    Trả (nhãn_tier, target_words) cho phần Summary.
    ngắn 500 · TB 700 · dài 1000 · siêu dài 1500
    """
    w = max(0, int(source_words or 0))
    if w < 800:
        return "ngắn", 500
    if w < 2500:
        return "trung bình", 700
    if w < 6000:
        return "dài", 1000
    return "siêu dài", 1500


def list_lesson_folders(root: Path) -> List[Path]:
    """Folder bài = có description.md hoặc video.* hoặc video.txt."""
    root = Path(root)
    if not root.is_dir():
        return []
    found = []
    for p in root.rglob("*"):
        if not p.is_dir():
            continue
        if p.name.startswith((".", "_")):
            continue
        # skip resource-only deep folders named resources
        if p.name.lower() == "resources":
            continue
        has = (
            (p / "description.md").is_file()
            or (p / "video.txt").is_file()
            or any(
                (p / f"video{ext}").is_file()
                for ext in getattr(C, "VIDEXT", (".mp4", ".webm", ".mkv", ".mov"))
            )
        )
        if has:
            found.append(p)
    # natural order by relative path
    def nat_key(path: Path):
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        parts = re.split(r"(\d+)", rel.replace("\\", "/").lower())
        return [int(x) if x.isdigit() else x for x in parts]

    return sorted(found, key=nat_key)


def load_lesson_content(folder: Path) -> Tuple[str, int]:
    """Ghép description + transcript + notes + links. Trả (text, word_count)."""
    parts = []
    for name in SOURCE_NAMES:
        f = folder / name
        if f.is_file():
            try:
                body = f.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                body = ""
            if body:
                parts.append(f"### {name}\n\n{body}")
    # resources/_links.txt
    links = folder / "resources" / "_links.txt"
    if links.is_file():
        try:
            body = links.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            body = ""
        if body:
            parts.append(f"### resources/_links.txt\n\n{body}")
    text = "\n\n".join(parts).strip()
    return text, estimate_words(text)


def lesson_title(folder: Path) -> str:
    name = folder.name
    if " - " in name:
        return name.split(" - ", 1)[-1].strip() or name
    return name


def summary_path(folder: Path) -> Path:
    return folder / OUT_NAME


def has_summary(folder: Path) -> bool:
    p = summary_path(folder)
    try:
        return p.is_file() and p.stat().st_size > 80
    except OSError:
        return False


def _truncate_for_llm(text: str, max_chars: int = 48000) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-(max_chars // 2) :]
    return head + "\n\n…[nội dung giữa đã rút gọn]…\n\n" + tail


def generate_one(
    folder: Path,
    root: Path,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    fallback: bool = True,
    log: Callable = print,
) -> Path:
    import llm_providers as PROV

    content, words = load_lesson_content(folder)
    if not content.strip():
        raise FileNotFoundError(f"Không có description/transcript trong {folder}")

    tier, target = summary_tier(words)
    title = lesson_title(folder)
    try:
        rel = str(folder.relative_to(root))
    except ValueError:
        rel = folder.name
    course = getattr(C, "COURSE", None) or root.name

    content_use = _truncate_for_llm(content)
    user = PROMPT_TEMPLATE.format(
        course=course,
        lesson_path=rel,
        title=title,
        source_words=words,
        target_words=target,
        content=content_use,
    )
    log(f"   tier={tier} target≈{target} từ | nguồn≈{words} từ | {rel}")

    # Ưu tiên task router (Dashboard chọn model theo tác vụ)
    if hasattr(PROV, "complete_for_task"):
        text, used = PROV.complete_for_task(
            "summary",
            SYSTEM,
            user,
            max_tokens=min(8000, max(2500, target * 4)),
            log=log,
        )
    else:
        text, used = PROV.complete_with_fallback(
            SYSTEM,
            user,
            provider=provider,
            fallback=fallback,
            model=model,
            max_tokens=min(8000, max(2500, target * 4)),
            log=log,
        )
    if not (text or "").strip():
        raise RuntimeError("LLM trả về rỗng")

    # meta footer
    footer = (
        f"\n\n---\n"
        f"_Sinh lúc {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        f"provider={used} · tier={tier} · target≈{target} từ · nguồn≈{words} từ_\n"
    )
    out = summary_path(folder)
    out.write_text(text.strip() + footer, encoding="utf-8")
    log(f"   ✓ {out.relative_to(root) if root in out.parents else out}")
    return out


def combine_all(root: Path, log: Callable = print) -> Path:
    root = Path(root)
    folders = list_lesson_folders(root)
    blocks = []
    n = 0
    for i, fd in enumerate(folders, 1):
        sp = summary_path(fd)
        if not sp.is_file():
            continue
        try:
            body = sp.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if not body:
            continue
        try:
            rel = str(fd.relative_to(root))
        except ValueError:
            rel = fd.name
        blocks.append(f"{'=' * 72}\n{i}. {rel}\n{'=' * 72}\n\n{body}")
        n += 1
    out = root / ALL_NAME
    meta = (
        f"ALL LESSON SUMMARIES (VI) — {getattr(C, 'COURSE', None) or root.name}\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Summaries: {n}/{len(folders)}\n"
        f"{'=' * 72}\n\n"
    )
    out.write_text(meta + ("\n\n\n".join(blocks)) + ("\n" if blocks else ""), encoding="utf-8")
    log(f">> Gộp {n} summary → {out.name}")
    return out


def run(
    root: Path,
    *,
    lesson: Optional[str] = None,
    force: bool = False,
    missing_only: bool = True,
    combine: bool = True,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    fallback: bool = True,
    limit: int = 0,
    log: Callable = print,
) -> dict:
    root = Path(root)
    import llm_providers as PROV

    # Task routing (Dashboard): summary
    if hasattr(PROV, "get_task_llm"):
        tcfg = PROV.get_task_llm("summary")
        provider = provider or tcfg.get("provider")
        model = model or tcfg.get("model")
        llm_cfg = tcfg
    else:
        llm_cfg = {}
        try:
            if hasattr(C, "get_lesson_summary_llm"):
                llm_cfg = C.get_lesson_summary_llm() or {}
        except Exception:
            pass
        provider = provider or llm_cfg.get("provider") or "deepseek"
        model = model or llm_cfg.get("model") or "deepseek-chat"
        if fallback and llm_cfg.get("fallback"):
            try:
                chain = [provider] + [p for p in llm_cfg["fallback"] if p != provider]
                PROV.set_fallback_chain(chain)
            except Exception:
                pass

    st = PROV.providers_status()
    if not st.get("ready_count"):
        raise RuntimeError(
            "Chưa cấu hình LLM API key. Vào Dashboard — dán key DeepSeek/Gemini… "
            "và chọn model cho tác vụ Summary."
        )
    log(
        f"LLM summary: primary={provider} model={model} "
        f"fallback={llm_cfg.get('fallback') or PROV.get_fallback_chain()[:4]}"
    )
    # stash for generate_one
    run._task_provider = provider  # type: ignore
    run._task_model = model  # type: ignore
    run._use_task_router = hasattr(PROV, "complete_for_task")  # type: ignore

    if lesson:
        folder = Path(lesson)
        if not folder.is_dir():
            folder = root / lesson
        if not folder.is_dir():
            raise FileNotFoundError(f"Không thấy bài: {lesson}")
        folders = [folder]
    else:
        folders = list_lesson_folders(root)

    todo = []
    for fd in folders:
        if force or not missing_only or not has_summary(fd):
            # cần có nội dung nguồn
            content, _ = load_lesson_content(fd)
            if content.strip():
                todo.append(fd)
            else:
                log(f"   [skip empty] {fd.relative_to(root) if root in fd.parents else fd}")

    if limit and limit > 0:
        todo = todo[:limit]

    log(
        f"=== LESSON SUMMARY (VI) ===\n"
        f"Khóa: {root}\n"
        f"Bài có nguồn: {len(folders)} | cần sinh: {len(todo)} "
        f"(force={force} missing_only={missing_only})"
    )

    ok = fail = 0
    errors = []
    for i, fd in enumerate(todo, 1):
        try:
            rel = fd.relative_to(root)
        except ValueError:
            rel = fd
        log(f"[{i}/{len(todo)}] {rel}")
        try:
            generate_one(
                fd, root, provider=provider, model=model, fallback=fallback, log=log
            )
            ok += 1
            time.sleep(0.3)
        except Exception as e:
            fail += 1
            errors.append(f"{rel}: {e}")
            log(f"   ✗ {e}")

    combined = None
    if combine:
        try:
            combined = combine_all(root, log=log)
        except Exception as e:
            log(f"[combine] {e}")

    log(f"--- XONG: ok={ok} fail={fail} ---")
    return {
        "ok": ok,
        "fail": fail,
        "todo": len(todo),
        "folders": len(folders),
        "combined": str(combined) if combined else None,
        "errors": errors,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tóm tắt từng bài học (VI) bằng LLM")
    ap.add_argument("--course", help="Tên khóa dưới BASE/courses/")
    ap.add_argument("--root", help="Đường dẫn tuyệt đối tới thư mục khóa")
    ap.add_argument("--lesson", help="1 bài (path tương đối vs root)")
    ap.add_argument("--force", action="store_true", help="Ghi đè summary.vi.md đã có")
    ap.add_argument(
        "--missing-only",
        action="store_true",
        default=True,
        help="Chỉ bài chưa có summary (mặc định)",
    )
    ap.add_argument("--all", action="store_true", help="Tất cả bài (kể cả đã có) — giống --force")
    ap.add_argument("--combine-only", action="store_true", help="Chỉ gộp _All_Summaries.vi.md")
    ap.add_argument("--no-combine", action="store_true", help="Không gộp file tổng")
    ap.add_argument("--provider", help="LLM provider id (grok, anthropic, …)")
    ap.add_argument("--model", help="Model override")
    ap.add_argument("--no-fallback", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Giới hạn số bài (test)")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.combine_only:
        combine_all(root)
        return 0

    force = bool(args.force or args.all)
    try:
        r = run(
            root,
            lesson=args.lesson,
            force=force,
            missing_only=not force,
            combine=not args.no_combine,
            provider=args.provider,
            model=args.model,
            fallback=not args.no_fallback,
            limit=args.limit,
        )
    except Exception as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1
    return 0 if r.get("fail", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
