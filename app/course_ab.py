#!/usr/bin/env python3
"""
A/B lesson titles & hooks — variants cho YouTube / Skool / ads.

  python course_ab.py --course X
  python course_ab.py --course X --limit 5 --llm
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import config as C

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
OUT = "_ab_titles"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def rule_variants(title: str, purpose: str = "") -> dict:
    t = (title or "Lesson").strip()
    p = (purpose or "").strip()
    base = re.sub(r"^\d+[\.\-\s]*", "", t).strip() or t
    return {
        "original": t,
        "variants": [
            f"How to {base}" if not base.lower().startswith("how") else base,
            f"{base} (step-by-step)",
            f"Stop guessing: {base}",
            f"{base} in 2026",
            f"The practical guide to {base}",
        ],
        "hooks": [
            f"Most people get {base} wrong — here's the fix.",
            f"In 10 minutes: {base}.",
            f"If you only learn one thing today: {base}.",
            f"Workshop-ready: {base}.",
        ],
        "skool_post_title": f"📘 {base}",
        "youtube_title": f"{base} | Full Tutorial",
        "purpose": p[:200],
    }


def llm_variants(title: str, summary: str, log: LogFn = print) -> Optional[dict]:
    try:
        import course_upgrade as CU
    except Exception:
        return None
    system = (
        "You write high-converting course lesson titles. "
        "Return ONLY JSON: "
        '{"variants":["...5 titles"],"hooks":["...4 hooks"],'
        '"skool_post_title":"...","youtube_title":"..."}'
    )
    user = f"Lesson title: {title}\n\nSummary excerpt:\n{summary[:2000]}"
    try:
        raw = CU._llm(system, user, log=log, max_tokens=800, task="assets")
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if not m:
            return None
        data = json.loads(m.group(0))
        data["original"] = title
        return data
    except Exception as e:
        _log(f"   [ab llm skip] {e}", log)
        return None


def generate_ab(
    root: Path,
    *,
    limit: int = 0,
    use_llm: bool = False,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    dest = root / UPGRADE
    lessons = sorted(
        {p.parent for p in dest.rglob("lesson.md") if "locales" not in p.parts}
    ) if dest.is_dir() else []
    if not lessons:
        # fallback structure
        sp = root / "_upgrade_new_structure.json"
        rows = []
        if sp.exists():
            st = json.loads(sp.read_text(encoding="utf-8"))
            for ch in st.get("chapters") or []:
                for les in ch.get("lessons") or []:
                    title = les.get("title") or "Lesson"
                    v = rule_variants(title, les.get("purpose") or "")
                    rows.append(v)
        if limit:
            rows = rows[:limit]
    else:
        if limit:
            lessons = lessons[:limit]
        rows = []
        for ldir in lessons:
            title = ldir.name.split(" - ", 1)[-1]
            summary = _read(ldir / "summary.md") or _read(ldir / "lesson.md")
            if use_llm:
                v = llm_variants(title, summary, log=log) or rule_variants(title)
            else:
                v = rule_variants(title)
            v["path"] = str(ldir.relative_to(dest)) if dest in ldir.parents or True else ldir.name
            try:
                v["path"] = str(ldir.relative_to(dest))
            except Exception:
                v["path"] = ldir.name
            rows.append(v)
            _log(f"   ab: {title}", log)

    out = root / OUT
    out.mkdir(parents=True, exist_ok=True)
    data = {"at": _now(), "course": root.name, "count": len(rows), "items": rows}
    (out / "ab_titles.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [f"# A/B titles — {root.name}", f"", f"Generated: {_now()}", ""]
    tsv = ["path\toriginal\tyoutube\tskool\tvariant1\tvariant2\thook1"]
    for it in rows:
        md.append(f"## {it.get('original')}")
        for v in it.get("variants") or []:
            md.append(f"- {v}")
        md.append(f"- YT: {it.get('youtube_title')}")
        md.append(f"- Skool: {it.get('skool_post_title')}")
        md.append("")
        vars_ = it.get("variants") or ["", ""]
        hooks = it.get("hooks") or [""]
        tsv.append(
            f"{it.get('path','')}\t{it.get('original')}\t{it.get('youtube_title')}\t"
            f"{it.get('skool_post_title')}\t{vars_[0] if vars_ else ''}\t"
            f"{vars_[1] if len(vars_)>1 else ''}\t{hooks[0] if hooks else ''}"
        )
    (out / "ab_titles.md").write_text("\n".join(md), encoding="utf-8")
    (out / "ab_titles.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    _log(f">> A/B titles: {len(rows)} → {out}", log)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="A/B lesson titles & hooks")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--llm", action="store_true", help="Dùng LLM (tốn token)")
    args = ap.parse_args(argv)
    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    print(
        json.dumps(
            generate_ab(Path(C.ROOT), limit=args.limit, use_llm=args.llm),
            ensure_ascii=False,
            indent=2,
        )[:3000]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
