#!/usr/bin/env python3
"""
Pipeline status cho 1 khóa Course OS — 1 chỗ xem đã xong đến đâu.

  python course_status.py --course X
  python course_status.py --course X --json
  python course_status.py --course X --md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import config as C

UPGRADE = "_upgrade_v2"
PUB = "_publish"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _exists(p: Path) -> bool:
    return p.exists() and (p.is_file() or any(p.iterdir()) if p.is_dir() else True)


def _count_lessons(root: Path) -> int:
    dest = Path(root) / UPGRADE
    if not dest.is_dir():
        return 0
    return len(
        {p.parent for p in dest.rglob("lesson.md") if "locales" not in p.parts}
    )


def _count_scripts(root: Path) -> int:
    dest = Path(root) / UPGRADE
    if not dest.is_dir():
        return 0
    return len(
        {
            p.parent
            for p in dest.rglob("talking_script.md")
            if "locales" not in p.parts
        }
    )


def _locales(root: Path) -> List[str]:
    hub = Path(root) / UPGRADE / "locales"
    if not hub.is_dir():
        return []
    return sorted(d.name for d in hub.iterdir() if d.is_dir())


def _json_safe(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def collect_status(root: Path) -> Dict[str, Any]:
    root = Path(root)
    steps = []

    def step(key: str, label: str, done: bool, detail: str = "", path: str = ""):
        steps.append(
            {
                "key": key,
                "label": label,
                "done": bool(done),
                "detail": detail,
                "path": path,
            }
        )

    inv = root / "_upgrade_inventory.json"
    inv_d = _json_safe(inv) if inv.exists() else None
    step(
        "inventory",
        "Inventory",
        inv.exists(),
        (
            f"lessons={inv_d.get('stats', {}).get('lessons')} · "
            f"obsolete_risk={(inv_d.get('obsolescence_summary') or {}).get('high_risk', '?')}"
            if inv_d
            else ""
        ),
        str(inv.name) if inv.exists() else "",
    )

    rep = root / "_Upgrade_Research_Report.md"
    research_j = root / "_upgrade_research.json"
    step(
        "research",
        "Research report",
        rep.exists() or research_j.exists(),
        f"md={rep.exists()} json={research_j.exists()}",
        rep.name if rep.exists() else "",
    )

    appr = root / "_upgrade_research_approved.json"
    appr_d = _json_safe(appr) if appr.exists() else None
    step(
        "approve",
        "Research approved",
        bool(appr_d and appr_d.get("approved")),
        (appr_d or {}).get("at") or "",
        appr.name if appr.exists() else "",
    )

    st = root / "_upgrade_new_structure.json"
    st_d = _json_safe(st) if st.exists() else None
    n_ch = len((st_d or {}).get("chapters") or []) if st_d else 0
    n_les = (
        sum(len(c.get("lessons") or []) for c in (st_d or {}).get("chapters") or [])
        if st_d
        else 0
    )
    step(
        "structure",
        "New structure",
        st.exists(),
        f"chapters={n_ch} lessons={n_les}" if st_d else "",
        st.name if st.exists() else "",
    )

    n_assets = _count_lessons(root)
    n_scripts = _count_scripts(root)
    step(
        "assets",
        "Asset packs",
        n_assets > 0,
        f"lesson.md={n_assets} talking_script={n_scripts}",
        UPGRADE if n_assets else "",
    )

    locs = _locales(root)
    loc_skip = (root / UPGRADE / "locales" / "_SKIPPED_OFFLINE.txt").exists()
    step(
        "localize",
        "Locale hub",
        bool(locs) or loc_skip,
        (
            f"locales={','.join(locs)}"
            if locs
            else ("skipped offline" if loc_skip else "—")
        ),
        f"{UPGRADE}/locales" if (locs or loc_skip) else "",
    )

    rev = root / UPGRADE / "_locale_review.json"
    rev_d = _json_safe(rev) if rev.exists() else None
    step(
        "review",
        "Locale review",
        bool(rev_d),
        (
            f"pending={rev_d.get('pending')} approved={rev_d.get('approved')} "
            f"rejected={rev_d.get('rejected')}"
            if rev_d
            else ""
        ),
        f"{UPGRADE}/_locale_review.json" if rev.exists() else "",
    )

    vq = root / UPGRADE / "_video_queue.json"
    vq_d = _json_safe(vq) if vq.exists() else None
    rendered = 0
    if vq_d:
        rendered = sum(
            1 for j in (vq_d.get("items") or []) if j.get("status") == "rendered"
        )
    step(
        "video",
        "Video queue",
        bool(vq_d),
        (
            f"jobs={vq_d.get('jobs')} rendered={rendered} "
            f"provider={vq_d.get('provider')} ${vq_d.get('usd_est_total')}"
            if vq_d
            else ""
        ),
        f"{UPGRADE}/_video_queue.md" if vq.exists() else "",
    )

    pub = root / PUB
    pub_ok = pub.is_dir() and any(pub.iterdir())
    pub_kids = [d.name for d in pub.iterdir()] if pub_ok else []
    step(
        "publish",
        "Publish packs",
        pub_ok,
        ", ".join(pub_kids[:8]) if pub_kids else "",
        PUB if pub_ok else "",
    )

    # --- GTM / ship artifacts (count toward full completion) ---
    step(
        "ship_slides",
        "Slides HTML",
        (root / "_slides").is_dir() and any((root / "_slides").rglob("*.html")),
        "",
        "_slides/",
    )
    step(
        "ship_pptx",
        "PPTX decks",
        (root / "_pptx").is_dir() and any((root / "_pptx").rglob("*.pptx")),
        "",
        "_pptx/",
    )
    step(
        "ship_thumbs",
        "Thumbnails",
        (root / "_thumbnails").is_dir() and any((root / "_thumbnails").rglob("*.png")),
        "",
        "_thumbnails/",
    )
    step(
        "ship_portal",
        "Student portal",
        (root / "_student_portal" / "index.html").exists(),
        "",
        "_student_portal/",
    )
    step(
        "ship_notion",
        "Notion export",
        (root / "_notion_export" / "README.md").exists(),
        "",
        "_notion_export/",
    )
    step(
        "ship_ops",
        "Ops (glossary/budget)",
        (root / "_course_glossary.json").exists() and (root / "_llm_budget.json").exists(),
        "",
        "_course_glossary.json",
    )

    gloss = root / "_course_glossary.json"
    style = root / "_course_style.json"
    budget = root / "_llm_budget.json"
    brand = root / "_brand_kit.json"
    ver = root / "_course_version.json"
    ver_d = _json_safe(ver) if ver.exists() else None
    bud_d = _json_safe(budget) if budget.exists() else None

    done_n = sum(1 for s in steps if s["done"])
    total = len(steps)
    pct = round(100 * done_n / max(1, total))

    # next recommended action
    next_key = "done"
    for s in steps:
        if not s["done"]:
            next_key = s["key"]
            break
    NEXT_HINT = {
        "inventory": "python course_upgrade.py --course … --inventory-only  (hoặc wizard)",
        "research": "python course_upgrade.py --course … --research",
        "approve": "python course_wizard.py --course … --approve-research",
        "structure": "python course_upgrade.py --course … --structure-only",
        "assets": "python course_studio.py --course … --assets --lang vi",
        "localize": "python course_studio.py --course … --localize --locales zh-CN,ja,es",
        "review": "python course_review.py --course … --build",
        "video": "python course_video.py --course … --prepare --provider local --run-queue --limit 1",
        "publish": "python course_publish.py --course … --all",
        "ship_slides": "python course_slides.py --course …",
        "ship_pptx": "python course_pptx.py --course …",
        "ship_thumbs": "python course_thumbs.py --course …",
        "ship_portal": "python course_portal.py --course …",
        "ship_notion": "python course_notion.py --course … --export",
        "ship_ops": "python course_ops.py --course … --init",
        "done": "python course_finish.py --course … --finish   # hoặc đã đủ",
    }

    return {
        "course": root.name,
        "root": str(root),
        "as_of": _now(),
        "progress": {"done": done_n, "total": total, "pct": pct},
        "next": next_key,
        "next_hint": NEXT_HINT.get(next_key, ""),
        "steps": steps,
        "meta": {
            "version": (ver_d or {}).get("version"),
            "glossary": gloss.exists(),
            "style": style.exists(),
            "brand_kit": brand.exists(),
            "budget": {
                "cap": (bud_d or {}).get("usd_cap"),
                "spent": (bud_d or {}).get("spent_usd"),
                "calls": (bud_d or {}).get("calls"),
            }
            if bud_d
            else None,
            "locales": locs,
            "asset_lessons": n_assets,
        },
    }


def write_md(root: Path, data: dict) -> Path:
    root = Path(root)
    lines = [
        f"# Course OS status — {data.get('course')}",
        "",
        f"- Generated: **{data.get('as_of')}**",
        f"- Progress: **{data['progress']['done']}/{data['progress']['total']}** "
        f"({data['progress']['pct']}%)",
        f"- Next: **{data.get('next')}** — {data.get('next_hint')}",
        "",
        "## Steps",
        "",
    ]
    for s in data.get("steps") or []:
        mark = "✅" if s.get("done") else "⬜"
        lines.append(
            f"- {mark} **{s.get('label')}**"
            + (f" — {s.get('detail')}" if s.get("detail") else "")
        )
    meta = data.get("meta") or {}
    lines += [
        "",
        "## Meta",
        "",
        f"- Course version: {meta.get('version') or '—'}",
        f"- Glossary: {meta.get('glossary')} · Style: {meta.get('style')} · Brand: {meta.get('brand_kit')}",
        f"- Locales: {', '.join(meta.get('locales') or []) or '—'}",
        f"- Asset lessons: {meta.get('asset_lessons')}",
    ]
    bud = meta.get("budget")
    if bud:
        lines.append(
            f"- LLM budget: spent ${bud.get('spent')} / cap ${bud.get('cap')} "
            f"({bud.get('calls')} calls)"
        )
    out = root / "_course_status.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "_course_status.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def print_status(data: dict):
    p = data["progress"]
    print(f"Course: {data['course']}")
    print(f"Progress: {p['done']}/{p['total']} ({p['pct']}%)")
    print(f"Next: {data['next']} — {data['next_hint']}")
    print("-" * 48)
    for s in data.get("steps") or []:
        mark = "OK" if s["done"] else "··"
        det = f"  {s['detail']}" if s.get("detail") else ""
        print(f"  [{mark}] {s['label']:<22}{det}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Course OS pipeline status")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md", action="store_true", help="Ghi _course_status.md + .json")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)
    data = collect_status(root)

    if args.md or not args.json:
        write_md(root, data)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_status(data)
        print(f"\n→ {root / '_course_status.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
