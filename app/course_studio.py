#!/usr/bin/env python3
"""
Course Studio — nhà máy nội dung khóa v2.

1) Lesson Asset Pack: từ _upgrade_new_structure.json sinh từng bài
   lesson.md, talking_script.md, workshop.md, use_cases.md, resources.md,
   quiz.json, broll_cues.md, slide_outline.md, summary.md

2) Master language: vi | en (settings course_master_lang)

3) Locale hub: dịch pack sang 10+ ngôn ngữ thương mại → locales/<code>/

CLI:
  python course_studio.py --course X --assets
  python course_studio.py --course X --assets --lang en
  python course_studio.py --course X --localize --locales "es,ja,ko,zh-CN"
  python course_studio.py --course X --assets --localize --full-pack
  python course_studio.py --list-locales
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import config as C

# Reuse upgrade paths / LLM
import course_upgrade as CU

STRUCTURE_JSON = CU.STRUCTURE_JSON
UPGRADE_DIR = CU.UPGRADE_DIR
REPORT_MD = CU.REPORT_MD
USER_NOTES = CU.USER_NOTES

# Files in each lesson asset pack
ASSET_FILES = (
    "lesson.md",
    "talking_script.md",
    "workshop.md",
    "use_cases.md",
    "resources.md",
    "broll_cues.md",
    "slide_outline.md",
    "summary.md",
    "quiz.json",
)

# Commercial locales (T1 + common) — ~40 for future; hub starts with subset
LOCALE_CATALOG: Dict[str, str] = {
    "en": "English",
    "vi": "Vietnamese",
    "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "pt-BR": "Portuguese (Brazil)",
    "pt-PT": "Portuguese (Portugal)",
    "id": "Indonesian",
    "hi": "Hindi",
    "ar": "Arabic",
    "fr": "French",
    "de": "German",
    "th": "Thai",
    "ms": "Malay",
    "tl": "Filipino (Tagalog)",
    "tr": "Turkish",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "uk": "Ukrainian",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "he": "Hebrew",
    "fa": "Persian",
    "bn": "Bengali",
    "ur": "Urdu",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "sw": "Swahili",
    "ro": "Romanian",
    "cs": "Czech",
    "el": "Greek",
    "hu": "Hungarian",
}

LogFn = Callable[[str], None]


def _log(msg: str, log: LogFn = print):
    log(msg)


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def _san(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "", s or "")
    s = re.sub(r"\s+", " ", s).strip()[:100]
    return s or "untitled"


def master_lang() -> str:
    try:
        return C.get_course_master_lang()
    except Exception:
        return getattr(C, "COURSE_MASTER_LANG", "vi") or "vi"


def lang_label(code: str) -> str:
    return LOCALE_CATALOG.get(code, code)


def lang_instruction(code: str) -> str:
    if code == "vi":
        return "Viết TOÀN BỘ bằng TIẾNG VIỆT tự nhiên, chuyên nghiệp. Giữ tên tool/API tiếng Anh."
    if code == "en":
        return "Write EVERYTHING in clear professional ENGLISH. Keep product/tool names as-is."
    name = lang_label(code)
    return (
        f"Write ALL user-facing content in {name} ({code}). "
        f"Keep software/tool/API names in English (Claude, n8n, Make, etc.). "
        f"Natural native style, not literal machine tone."
    )


def load_structure(root: Path) -> dict:
    root = Path(root)
    p = root / STRUCTURE_JSON
    if not p.exists():
        # fallback inside upgrade dir
        p2 = root / UPGRADE_DIR / "_structure.json"
        if p2.exists():
            p = p2
        else:
            raise FileNotFoundError(
                f"Chưa có {STRUCTURE_JSON}. Chạy course_upgrade --structure-only trước."
            )
    data = json.loads(_read(p) or "{}")
    if not data.get("chapters"):
        raise ValueError("Structure JSON không có chapters")
    return data


def upgrade_root(root: Path) -> Path:
    d = Path(root) / UPGRADE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def iter_lessons(data: dict):
    for ch in data.get("chapters") or []:
        for les in ch.get("lessons") or []:
            yield ch, les


def lesson_dir(dest: Path, ch: dict, les: dict) -> Path:
    cn = int(ch.get("number") or 0)
    ln = int(les.get("number") or 0)
    cname = f"{cn:02d} - {_san(ch.get('title') or f'Chapter {cn}')}"
    lname = f"{ln:02d} - {_san(les.get('title') or f'Lesson {ln}')}"
    return dest / cname / lname


def bootstrap_assets_from_dump(
    root: Path,
    *,
    force: bool = False,
    limit: int = 0,
    log: LogFn = print,
) -> dict:
    """
    Offline asset packs: copy description/transcript từ dump → _upgrade_v2/
    Không gọi LLM. Đủ để ship slides/pptx/portal/publish local.
    """
    root = Path(root)
    data = load_structure(root)
    dest = upgrade_root(root)
    lang = master_lang()
    _write(
        dest / "README.md",
        f"# {data.get('course_title') or root.name}\n\n"
        f"- mode: **offline bootstrap**\n"
        f"- master_lang: {lang}\n"
        f"- generated: {_now()}\n",
    )
    _write(dest / "_structure.json", json.dumps(data, ensure_ascii=False, indent=2))
    _write(dest / "_master_lang.txt", lang + "\n")

    lessons = list(iter_lessons(data))
    if limit > 0:
        lessons = lessons[:limit]
    ok = fail = 0
    for i, (ch, les) in enumerate(lessons, 1):
        try:
            ldir = lesson_dir(dest, ch, les)
            ldir.mkdir(parents=True, exist_ok=True)
            if (ldir / "lesson.md").exists() and not force:
                ok += 1
                continue
            src_rel = les.get("source_path") or les.get("replace_old") or ""
            src = root / src_rel if src_rel else None
            desc = tr = ""
            if src and src.is_dir():
                for name in ("description.md", "Description.md"):
                    p = src / name
                    if p.exists():
                        desc = _read(p)
                        break
                for name in ("transcript.txt", "video.txt", "all transcript.txt"):
                    p = src / name
                    if p.exists():
                        tr = _read(p)
                        break
                # nested lesson folder
                if not desc:
                    for p in src.rglob("description.md"):
                        desc = _read(p)
                        break
            title = les.get("title") or "Lesson"
            purpose = les.get("purpose") or f"Learn {title}"
            body = desc.strip() or tr.strip() or f"# {title}\n\n{purpose}\n"
            lesson_md = (
                f"# {title}\n\n"
                f"**Purpose:** {purpose}\n\n"
                f"{body}\n"
            )
            script = (
                f"# Talking script — {title}\n\n"
                f"Welcome. Today we cover {title}.\n\n"
                f"[PAUSE]\n\n"
                f"{(desc or tr or purpose)[:4000]}\n\n"
                f"[PAUSE]\n\n"
                f"That's a wrap — apply one action from this lesson today.\n"
            )
            summary = (
                f"# Summary — {title}\n\n"
                f"## Purpose\n{purpose}\n\n"
                f"## Key points\n- {title}\n\n"
                f"## Next step\nPractice the workshop steps.\n"
            )
            workshop = (
                f"# Workshop — {title}\n\n"
                f"## Objective\nApply: {purpose}\n\n"
                f"## Steps\n1. Review the lesson notes\n2. Complete one hands-on task\n"
                f"3. Write a 3-bullet recap\n\n## Deliverable\nChecklist completed\n"
            )
            _write(ldir / "lesson.md", lesson_md)
            _write(ldir / "talking_script.md", script)
            _write(ldir / "summary.md", summary)
            _write(ldir / "workshop.md", workshop)
            _write(ldir / "use_cases.md", f"# Use cases — {title}\n\n1. Apply in your workflow\n")
            _write(ldir / "resources.md", f"# Resources — {title}\n\n- Original dump: `{src_rel}`\n")
            _write(ldir / "broll_cues.md", f"# B-roll — {title}\n\n- Screen recording of steps\n")
            _write(
                ldir / "slide_outline.md",
                f"# {title}\n\n## Agenda\n- Why it matters\n- Steps\n- Practice\n- Recap\n",
            )
            _write(
                ldir / "quiz.json",
                json.dumps(
                    [
                        {
                            "q": f"What is the focus of «{title}»?",
                            "choices": [purpose[:80] or title, "Unrelated topic", "Skip lesson", "None"],
                            "answer": 0,
                            "explain": purpose[:200],
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            meta = {
                "title": title,
                "chapter": ch.get("title"),
                "mode": "offline_bootstrap",
                "source_path": src_rel,
                "lang": lang,
                "at": _now(),
            }
            _write(ldir / "lesson.json", json.dumps(meta, ensure_ascii=False, indent=2))
            ok += 1
            if i % 20 == 0:
                _log(f"   bootstrap {i}/{len(lessons)}…", log)
        except Exception as e:
            fail += 1
            _log(f"   ✗ bootstrap {les.get('title')}: {e}", log)
    _log(f"--- OFFLINE ASSETS ok={ok} fail={fail} → {dest} ---", log)
    return {"ok": ok, "fail": fail, "dir": str(dest), "mode": "offline"}


# ----------------------------- 1) Asset pack -----------------------------
def generate_lesson_asset_pack(
    root: Path,
    ch: dict,
    les: dict,
    *,
    lang: Optional[str] = None,
    force: bool = False,
    log: LogFn = print,
) -> Path:
    """Sinh full asset pack cho 1 bài (master lang)."""
    lang = lang or master_lang()
    dest = upgrade_root(root)
    ldir = lesson_dir(dest, ch, les)
    ldir.mkdir(parents=True, exist_ok=True)

    marker = ldir / "lesson.md"
    if marker.exists() and marker.stat().st_size > 200 and not force:
        # still ensure other files if missing
        missing = [f for f in ASSET_FILES if not (ldir / f).exists()]
        if not missing:
            _log(f"   skip (exists) {ldir.relative_to(dest)}", log)
            return ldir

    report_snip = _read(Path(root) / REPORT_MD)[:10000]
    notes = _read(Path(root) / USER_NOTES)[:3000]
    qa = CU.format_answers_for_prompt(root=Path(root))[:3000]
    as_of = _today()
    title = les.get("title") or "Lesson"
    try:
        import course_ops as OPS
        gloss = OPS.glossary_prompt_block(Path(root))
        style = OPS.style_prompt_block(Path(root))
    except Exception:
        gloss = style = ""

    system = (
        f"You are a senior course creator and instructional designer. Today is {as_of}.\n"
        f"{lang_instruction(lang)}\n"
        f"{gloss}{style}"
        "Be practical, updated, actionable. Do NOT invent product features you are unsure about; "
        "mark uncertain claims as 'verify'. Output valid structured sections as requested."
    )

    user = f"""Create a COMPLETE lesson asset pack for a modern online course.

## Lesson meta
- Chapter: {ch.get('title')}
- Chapter goal: {ch.get('goal')}
- Lesson title: {title}
- Purpose: {les.get('purpose')}
- Must cover: {json.dumps(les.get('must_cover') or [], ensure_ascii=False)}
- Software: {json.dumps(les.get('software') or [], ensure_ascii=False)}
- Source: {les.get('source')} | replaces: {les.get('replace_old') or '—'}
- Est. minutes: {les.get('est_minutes') or 15}
- Master language code: {lang}

## User questionnaire / wishes
{qa or '(none)'}

## Research report excerpt
{report_snip or '(none)'}

## User notes
{notes or '(none)'}

## REQUIRED OUTPUT FORMAT
Return ONE markdown document with these exact level-1 headings (in English as labels):

# PACK

## lesson.md
(full teaching content: intro, concepts, steps, pitfalls, recap)

## talking_script.md
(spoken script for AI avatar/TTS, natural speech, short paragraphs, optional [PAUSE] markers, ~{int(les.get('est_minutes') or 12)*140} words target)

## workshop.md
(hands-on workshop 15-45 min: objective, setup, steps, deliverable, success criteria)

## use_cases.md
(3-5 realistic updated use cases)

## resources.md
(tools, templates, checklists, official docs — mark verify if unsure)

## broll_cues.md
(list of visual/screen cues timed roughly)

## slide_outline.md
(slide titles + bullets)

## summary.md
(Purpose, Key takeaways, Todo list)

## quiz.json
(valid JSON array of 5-8 objects: {{"q":"...","choices":["A","B","C","D"],"answer":0,"explain":"..."}} inside a fenced json block)

Write content body under each heading. No extra commentary outside PACK.
"""

    _log(f"   assets [{lang}] {ch.get('title')} / {title}", log)
    raw = CU._llm(system, user, log=log, max_tokens=9000, task="assets")
    parts = _split_pack_sections(raw)

    # write each file
    defaults = {
        "lesson.md": f"# {title}\n\n{les.get('purpose') or ''}\n",
        "talking_script.md": f"# Script — {title}\n\n",
        "workshop.md": f"# Workshop — {title}\n\n",
        "use_cases.md": f"# Use cases — {title}\n\n",
        "resources.md": f"# Resources — {title}\n\n",
        "broll_cues.md": f"# B-roll — {title}\n\n",
        "slide_outline.md": f"# Slides — {title}\n\n",
        "summary.md": f"# Summary — {title}\n\n",
    }
    for name, default in defaults.items():
        body = (parts.get(name) or "").strip()
        _write(ldir / name, body if body else default)

    # quiz.json
    quiz_raw = parts.get("quiz.json") or parts.get("quiz") or "[]"
    quiz_data = _extract_json_array(quiz_raw)
    _write(ldir / "quiz.json", json.dumps(quiz_data, ensure_ascii=False, indent=2))

    # meta + description.md alias for compatibility
    meta = {
        "title": title,
        "purpose": les.get("purpose"),
        "must_cover": les.get("must_cover"),
        "software": les.get("software"),
        "source": les.get("source"),
        "replace_old": les.get("replace_old"),
        "est_minutes": les.get("est_minutes"),
        "master_lang": lang,
        "asset_pack": True,
        "generated_at": _now(),
        "as_of": as_of,
    }
    _write(ldir / "lesson.json", json.dumps(meta, ensure_ascii=False, indent=2))
    # keep description.md = lesson.md for older tools
    if (ldir / "lesson.md").exists():
        _write(ldir / "description.md", _read(ldir / "lesson.md"))

    return ldir


def _split_pack_sections(text: str) -> Dict[str, str]:
    """Parse ## filename sections from LLM pack output."""
    text = text or ""
    # normalize
    text = re.sub(r"^#\s*PACK\s*", "", text.strip(), flags=re.I)
    keys = [
        "lesson.md",
        "talking_script.md",
        "workshop.md",
        "use_cases.md",
        "resources.md",
        "broll_cues.md",
        "slide_outline.md",
        "summary.md",
        "quiz.json",
    ]
    # find headings like ## lesson.md or ## `lesson.md`
    pattern = re.compile(
        r"^##\s*`?(" + "|".join(re.escape(k) for k in keys) + r"|quiz)`?\s*$",
        re.I | re.M,
    )
    matches = list(pattern.finditer(text))
    out: Dict[str, str] = {}
    if not matches:
        # whole text as lesson
        out["lesson.md"] = text
        return out
    for i, m in enumerate(matches):
        key = m.group(1).lower()
        if key == "quiz":
            key = "quiz.json"
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[key] = text[start:end].strip()
    return out


def _extract_json_array(text: str) -> list:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        data = json.loads(t)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "questions" in data:
            return data["questions"]
    except Exception:
        pass
    m = re.search(r"\[[\s\S]*\]", t)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def regenerate_one_lesson(
    root: Path,
    lesson_rel: str,
    *,
    lang: Optional[str] = None,
    log: LogFn = print,
) -> Path:
    """Sinh lại asset pack cho 1 bài (path tương đối trong structure hoặc folder name)."""
    root = Path(root)
    data = load_structure(root)
    lang = lang or master_lang()
    target = None
    for ch, les in iter_lessons(data):
        ldir = lesson_dir(upgrade_root(root), ch, les)
        rel = str(ldir.relative_to(upgrade_root(root)))
        title = les.get("title") or ""
        if (
            lesson_rel in rel
            or lesson_rel == title
            or lesson_rel in (les.get("title") or "")
            or Path(lesson_rel).name in rel
        ):
            target = (ch, les)
            break
    if not target:
        raise FileNotFoundError(f"Không tìm thấy bài: {lesson_rel}")
    ch, les = target
    return generate_lesson_asset_pack(root, ch, les, lang=lang, force=True, log=log)


def generate_all_assets(
    root: Path,
    *,
    lang: Optional[str] = None,
    force: bool = False,
    limit: int = 0,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    lang = lang or master_lang()
    data = load_structure(root)
    dest = upgrade_root(root)
    title = data.get("course_title") or root.name
    _write(
        dest / "README.md",
        f"# {title}\n\n"
        f"- as_of: {data.get('as_of') or _today()}\n"
        f"- master_lang: **{lang}** ({lang_label(lang)})\n"
        f"- generated: {_now()}\n"
        f"- asset_pack: lesson + talking_script + workshop + use_cases + resources + quiz…\n",
    )
    _write(dest / "_structure.json", json.dumps(data, ensure_ascii=False, indent=2))
    _write(dest / "_master_lang.txt", lang + "\n")

    lessons = list(iter_lessons(data))
    if limit > 0:
        lessons = lessons[:limit]
    ok = fail = 0
    errors = []
    for i, (ch, les) in enumerate(lessons, 1):
        _log(f"[{i}/{len(lessons)}] Asset pack…", log)
        try:
            generate_lesson_asset_pack(root, ch, les, lang=lang, force=force, log=log)
            ok += 1
            time.sleep(0.25)
        except Exception as e:
            fail += 1
            errors.append(f"{les.get('title')}: {e}")
            _log(f"   ✗ {e}", log)
    _log(f"--- ASSETS: ok={ok} fail={fail} lang={lang} → {dest} ---", log)
    return {"ok": ok, "fail": fail, "dir": str(dest), "lang": lang, "errors": errors}


# ----------------------------- 3) Locale hub -----------------------------
def list_locales() -> Dict[str, str]:
    return dict(LOCALE_CATALOG)


def localize_text_files(
    src_dir: Path,
    dest_dir: Path,
    *,
    target_lang: str,
    source_lang: Optional[str] = None,
    course_root: Optional[Path] = None,
    force: bool = False,
    log: LogFn = print,
) -> int:
    """Dịch các file .md trong 1 lesson folder sang locale."""
    import course_ops as OPS

    source_lang = source_lang or master_lang()
    dest_dir.mkdir(parents=True, exist_ok=True)
    # resolve course root
    if course_root is None:
        cr = Path(dest_dir)
        while cr.name not in ("_upgrade_v2", "") and cr.parent != cr:
            if cr.name == "_upgrade_v2":
                break
            cr = cr.parent
        course_root = cr.parent if cr.name == "_upgrade_v2" else Path(src_dir)
    course_root = Path(course_root)
    n = 0
    md_files = [p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md"]
    quiz_src = src_dir / "quiz.json"
    gloss = OPS.glossary_prompt_block(course_root, locale=target_lang)
    style = OPS.style_prompt_block(course_root)
    for fp in sorted(md_files):
        if fp.name.lower() in ("readme.md",):
            continue
        out = dest_dir / fp.name
        if out.exists() and out.stat().st_size > 50 and not force:
            continue
        body = _read(fp)
        if not body.strip():
            continue
        cached = OPS.tm_lookup(course_root, target_lang, body[:8000])
        if cached and not force:
            _write(out, cached)
            n += 1
            continue

        system = (
            f"You are a professional course localizer.\n"
            f"Source language: {source_lang}. Target: {target_lang} ({lang_label(target_lang)}).\n"
            f"{lang_instruction(target_lang)}\n"
            f"{gloss}{style}"
            "Preserve Markdown structure and headings. Do not invent new sections. "
            "Keep tool names, URLs, code, and JSON keys unchanged."
        )
        user = f"Translate the following course file `{fp.name}`:\n\n{body[:14000]}"
        try:
            translated = CU._llm(system, user, log=log, max_tokens=7000, task="localize")
            text = translated.strip()
            _write(out, text)
            OPS.tm_store(course_root, target_lang, body[:8000], text)
            n += 1
            time.sleep(0.2)
        except Exception as e:
            _log(f"   [loc fail] {fp.name}: {e}", log)
    if quiz_src.exists():
        out_q = dest_dir / "quiz.json"
        if force or not out_q.exists():
            try:
                quiz = json.loads(_read(quiz_src) or "[]")
                system = (
                    f"Translate quiz JSON to {target_lang} ({lang_label(target_lang)}). "
                    "Return ONLY a JSON array. Keep answer index numbers. Translate q, choices, explain."
                )
                user = json.dumps(quiz, ensure_ascii=False)[:12000]
                raw = CU._llm(system, user, log=log, max_tokens=4000, task="localize")
                data = _extract_json_array(raw)
                if data:
                    _write(out_q, json.dumps(data, ensure_ascii=False, indent=2))
                    n += 1
            except Exception as e:
                _log(f"   [quiz loc] {e}", log)
    # copy lesson.json with locale tag
    meta_src = src_dir / "lesson.json"
    if meta_src.exists():
        try:
            meta = json.loads(_read(meta_src) or "{}")
            meta["locale"] = target_lang
            meta["source_lang"] = source_lang
            _write(dest_dir / "lesson.json", json.dumps(meta, ensure_ascii=False, indent=2))
        except Exception:
            pass
    return n


def run_localize(
    root: Path,
    *,
    locales: Optional[List[str]] = None,
    force: bool = False,
    limit_lessons: int = 0,
    only_lessons: Optional[List[str]] = None,
    log: LogFn = print,
) -> dict:
    """
    Localize asset packs.
    only_lessons: substring filters on relative path or title (selective).
    """
    root = Path(root)
    dest = upgrade_root(root)
    if not dest.exists() or not any(dest.iterdir()):
        raise FileNotFoundError(
            f"Chưa có {UPGRADE_DIR}/ với asset pack. Chạy --assets trước."
        )
    locales = locales or C.get_course_locales()
    # never re-translate master onto itself as "locale" unless different folder needed
    master = master_lang()
    locales = [x for x in locales if x and x != master]
    # validate
    unknown = [x for x in locales if x not in LOCALE_CATALOG]
    if unknown:
        _log(f"⚠ locale chưa trong catalog (vẫn chạy): {unknown}", log)

    hub = dest / "locales"
    hub.mkdir(exist_ok=True)
    _write(
        hub / "README.md",
        f"# Locale hub\n\nMaster: **{master}**\n\n"
        f"Locales: {', '.join(locales)}\n\nGenerated: {_now()}\n",
    )

    # find all lesson dirs under dest (have lesson.md)
    lesson_dirs = sorted(
        {p.parent for p in dest.rglob("lesson.md") if "locales" not in p.parts}
    )
    filters = [x.strip().lower() for x in (only_lessons or []) if x and x.strip()]
    if filters:
        filtered = []
        for ldir in lesson_dirs:
            try:
                rel = str(ldir.relative_to(dest)).lower()
            except ValueError:
                rel = ldir.name.lower()
            if any(f in rel or f in ldir.name.lower() for f in filters):
                filtered.append(ldir)
        _log(
            f">> Selective localize: {len(filtered)}/{len(lesson_dirs)} lessons "
            f"match {filters}",
            log,
        )
        lesson_dirs = filtered
    if limit_lessons > 0:
        lesson_dirs = lesson_dirs[:limit_lessons]

    stats = {loc: 0 for loc in locales}
    for loc in locales:
        _log(f">> Localize → {loc} ({lang_label(loc)}) · {len(lesson_dirs)} lessons", log)
        for ldir in lesson_dirs:
            try:
                rel = ldir.relative_to(dest)
            except ValueError:
                rel = Path(ldir.name)
            out = hub / loc / rel
            n = localize_text_files(
                ldir,
                out,
                target_lang=loc,
                source_lang=master,
                course_root=root,
                force=force,
                log=log,
            )
            stats[loc] = stats.get(loc, 0) + n
        _log(f"   {loc}: wrote ~{stats[loc]} files", log)

    summary = {
        "master": master,
        "locales": locales,
        "lessons": len(lesson_dirs),
        "only_filter": filters,
        "files_written": stats,
        "hub": str(hub),
    }
    _write(hub / "_localize_summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    _log(f"--- LOCALIZE done → {hub} ---", log)
    return summary


# ----------------------------- CLI -----------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Course Studio: assets + master lang + locale hub")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--assets", action="store_true", help="Sinh lesson asset packs")
    ap.add_argument("--localize", action="store_true", help="Dịch sang locales")
    ap.add_argument("--full-pack", action="store_true", help="assets + localize")
    ap.add_argument("--lang", help="Master language vi|en (ghi settings)")
    ap.add_argument("--locales", help="Comma list: es,ja,ko,zh-CN,...")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Giới hạn số bài (test)")
    ap.add_argument(
        "--only",
        action="append",
        default=[],
        help="Chỉ localize/assets bài khớp substring (lặp lại được). VD: --only Intro --only MCP",
    )
    ap.add_argument("--list-locales", action="store_true")
    ap.add_argument("--regen", help="Sinh lại 1 bài (tên hoặc path tương đối)")
    args = ap.parse_args(argv)

    if args.list_locales:
        for code, name in LOCALE_CATALOG.items():
            print(f"  {code:8}  {name}")
        print(f"\nDefault hub: {', '.join(C.COURSE_LOCALES_DEFAULT)}")
        return 0

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.lang:
        C.set_course_master_lang(args.lang)
        print(f"master_lang = {C.get_course_master_lang()}")

    if args.locales:
        C.set_course_locales(args.locales)

    if args.regen:
        p = regenerate_one_lesson(
            root, args.regen, lang=C.get_course_master_lang()
        )
        print(f"Regenerated → {p}")
        return 0

    do_assets = args.assets or args.full_pack
    do_loc = args.localize or args.full_pack
    if not do_assets and not do_loc:
        ap.print_help()
        print("\nCần --assets và/hoặc --localize (hoặc --full-pack / --regen)")
        return 2

    only = list(args.only or [])
    if do_assets:
        generate_all_assets(
            root, lang=C.get_course_master_lang(), force=args.force, limit=args.limit
        )
    if do_loc:
        locs = C.get_course_locales()
        if args.locales:
            locs = [x.strip() for x in args.locales.split(",") if x.strip()]
        run_localize(
            root,
            locales=locs,
            force=args.force,
            limit_lessons=args.limit,
            only_lessons=only or None,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        raise SystemExit(1)
