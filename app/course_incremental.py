#!/usr/bin/env python3
"""
Incremental re-upgrade — chỉ xử lý bài high-risk / missing assets, không full regenerate.

  python course_incremental.py --course X --scan
  python course_incremental.py --course X --run          # assets cho bài obsolete/missing
  python course_incremental.py --course X --run --research-quick
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import config as C
import course_ops as OPS
import course_upgrade as CU

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
PLAN = "_incremental_plan.json"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def scan_plan(root: Path, log: LogFn = print) -> dict:
    """
    Lập plan incremental:
    - inventory obsolescence high_risk
    - structure lessons missing asset pack
    - locale incomplete (from loc QA if present)
    """
    root = Path(root)
    inv_p = root / CU.INVENTORY_JSON
    if inv_p.exists():
        inv = json.loads(inv_p.read_text(encoding="utf-8"))
        inv = OPS.score_inventory_lessons(inv)
    else:
        inv = CU.build_inventory(root, log=log)
        inv = OPS.score_inventory_lessons(inv)
        inv_p.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")

    obsolete = []
    for L in inv.get("lessons") or []:
        obs = L.get("obsolescence") or {}
        if obs.get("likely_obsolete") or (obs.get("score") or 0) >= 45:
            obsolete.append(
                {
                    "title": L.get("title"),
                    "path": L.get("path") or L.get("dir") or "",
                    "score": obs.get("score"),
                    "hits": obs.get("hits"),
                    "reason": "obsolescence",
                }
            )

    missing_assets = []
    st_p = root / CU.STRUCTURE_JSON
    structure_lessons = []
    if st_p.exists():
        st = json.loads(st_p.read_text(encoding="utf-8"))
        dest = root / UPGRADE
        for ch in st.get("chapters") or []:
            for les in ch.get("lessons") or []:
                structure_lessons.append((ch, les))
                # expected dir naming similar to studio
                try:
                    import course_studio as ST

                    ldir = ST.lesson_dir(dest, ch, les) if dest.exists() else None
                except Exception:
                    ldir = None
                if ldir is None or not (ldir / "lesson.md").exists():
                    missing_assets.append(
                        {
                            "title": les.get("title"),
                            "chapter": ch.get("title"),
                            "reason": "missing_asset_pack",
                        }
                    )
                elif not (ldir / "talking_script.md").exists():
                    missing_assets.append(
                        {
                            "title": les.get("title"),
                            "chapter": ch.get("title"),
                            "reason": "missing_script",
                        }
                    )

    loc_issues = []
    lqa = root / UPGRADE / "_localization_qa.json"
    if lqa.exists():
        try:
            data = json.loads(lqa.read_text(encoding="utf-8"))
            loc_issues = (data.get("issues") or [])[:100]
        except Exception:
            pass

    plan = {
        "at": _now(),
        "course": root.name,
        "obsolete_count": len(obsolete),
        "missing_assets_count": len(missing_assets),
        "loc_issues_count": len(loc_issues),
        "obsolete": obsolete[:80],
        "missing_assets": missing_assets[:80],
        "loc_issues": loc_issues[:40],
        "recommended": [],
    }
    if obsolete:
        plan["recommended"].append("research-quick + structure-only (tool đã cũ)")
    if missing_assets:
        plan["recommended"].append("regenerate assets for missing lessons")
    if loc_issues:
        plan["recommended"].append("relocalize incomplete locales")
    if not plan["recommended"]:
        plan["recommended"].append("nothing critical — optional full refresh")

    (root / PLAN).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        f"# Incremental plan — {root.name}",
        f"",
        f"Generated: {plan['at']}",
        f"",
        f"- Obsolete / high-risk lessons: **{plan['obsolete_count']}**",
        f"- Missing asset packs: **{plan['missing_assets_count']}**",
        f"- Loc QA issues: **{plan['loc_issues_count']}**",
        f"",
        f"## Recommended",
        f"",
    ]
    for r in plan["recommended"]:
        md.append(f"- {r}")
    md += ["", "## Obsolete (top)", ""]
    for o in plan["obsolete"][:30]:
        md.append(f"- {o.get('title')} (score={o.get('score')})")
    md += ["", "## Missing assets", ""]
    for m in plan["missing_assets"][:30]:
        md.append(f"- {m.get('title')} — {m.get('reason')}")
    (root / "_incremental_plan.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    _log(
        f">> Incremental plan: obsolete={plan['obsolete_count']} "
        f"missing={plan['missing_assets_count']} loc={plan['loc_issues_count']}",
        log,
    )
    return plan


def run_incremental(
    root: Path,
    *,
    research_quick: bool = False,
    force_assets: bool = False,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    plan = scan_plan(root, log=log)
    result = {"plan": plan, "actions": []}

    if research_quick or plan["obsolete_count"] >= 3:
        _log(">> Quick research refresh…", log)
        inv = json.loads((root / CU.INVENTORY_JSON).read_text(encoding="utf-8"))
        research = CU.research_market(
            inv,
            do_web=True,
            user_answers=CU.load_answers(root),
            root=root,
            log=log,
        )
        # mark depth
        research["report_md"] = (research.get("report_md") or "") + (
            "\n\n## Incremental mode\nChỉ refresh nhanh do obsolescence.\n"
        )
        CU.write_reports(root, inv, research, log=log)
        result["actions"].append("research-quick")

    # regenerate missing asset packs only
    missing_titles = [m.get("title") for m in plan.get("missing_assets") or [] if m.get("title")]
    if missing_titles or force_assets:
        import course_studio as ST

        if not (root / CU.STRUCTURE_JSON).exists():
            _log("   (chưa có structure — bỏ assets incremental)", log)
        else:
            # regenerate each missing by title
            for title in missing_titles[:40]:
                try:
                    ST.regenerate_one_lesson(root, title, log=log)
                    result["actions"].append(f"asset:{title}")
                    _log(f"   asset regen: {title}", log)
                except Exception as e:
                    _log(f"   skip asset {title}: {e}", log)
                    result["actions"].append(f"fail:{title}:{e}")

    # optional: if many obsolete but structure exists, append notes
    if plan["obsolete_count"]:
        notes_p = root / CU.USER_NOTES
        note_block = (
            f"\n\n## Incremental flags ({_now()})\n"
            f"High-risk lessons: {plan['obsolete_count']}. "
            f"Xem `_incremental_plan.md`.\n"
        )
        try:
            prev = notes_p.read_text(encoding="utf-8") if notes_p.exists() else ""
            if "Incremental flags" not in prev[-800:]:
                notes_p.write_text(prev + note_block, encoding="utf-8")
        except Exception:
            pass
        result["actions"].append("user_notes_flag")

    result["at"] = _now()
    (root / "_incremental_last_run.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _log(f"--- INCREMENTAL done actions={len(result['actions'])} ---", log)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Incremental course re-upgrade")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--research-quick", action="store_true")
    ap.add_argument("--force-assets", action="store_true")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.run:
        print(json.dumps(run_incremental(
            root,
            research_quick=args.research_quick,
            force_assets=args.force_assets,
        ), ensure_ascii=False, indent=2)[:4000])
        return 0
    # default scan
    print(json.dumps(scan_plan(root), ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
