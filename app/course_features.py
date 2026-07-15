#!/usr/bin/env python3
"""
Course OS feature registry — verify mọi module/tính năng đã ship.

  python course_features.py
  python course_features.py --json
  python course_features.py --write   # ghi FEATURE_CHECK.md vào app/docs? → course root BASE
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# (id, title, module, callable_or_None, notes)
FEATURES: List[Tuple[str, str, str, str, str]] = [
    ("upgrade", "Research → structure", "course_upgrade", "research_market", "core"),
    ("studio", "Assets + localize", "course_studio", "generate_all_assets", "core"),
    ("wizard", "End-to-end wizard", "course_wizard", "run_wizard", "core"),
    ("video", "Video queue + render", "course_video", "prepare_video_jobs", "core"),
    ("publish", "Publish packs", "course_publish", "publish_all", "core"),
    ("qa", "QA + golden eval", "course_qa", "eval_golden", "core"),
    ("ops", "Glossary/budget/ops", "course_ops", "cost_dashboard", "core"),
    ("review", "Locale review", "course_review", "build_review_queue", "core"),
    ("schedule", "Scheduled re-upgrade", "course_schedule", "list_schedules", "core"),
    ("board", "Curriculum board DnD", "course_board", "export_html_board", "core"),
    ("status", "Pipeline status", "course_status", "collect_status", "core"),
    ("slides", "HTML slides", "course_slides", "export_slides", "gtm"),
    ("pptx", "PPTX export", "course_pptx", "export_pptx_pack", "gtm"),
    ("thumbs", "Thumbnails PNG", "course_thumbs", "export_thumbs", "gtm"),
    ("portal", "Student portal", "course_portal", "build_portal", "gtm"),
    ("ab", "A/B titles", "course_ab", "generate_ab", "gtm"),
    ("portfolio", "Multi-course portfolio", "course_portfolio", "collect_portfolio", "gtm"),
    ("competitor", "Competitor scan", "course_competitor", "scan_competitors", "gtm"),
    ("notion", "Notion + webhook", "course_notion", "export_notion_pack", "gtm"),
    ("incremental", "Incremental upgrade", "course_incremental", "run_incremental", "ops"),
    ("finish", "Finish-all orchestrator", "course_finish", "finish", "ops"),
    ("omnivoice", "OmniVoice local TTS", "course_omnivoice", "render_lesson", "media"),
]


def check_features() -> Dict[str, Any]:
    rows = []
    ok = fail = 0
    for fid, title, mod, attr, group in FEATURES:
        try:
            m = importlib.import_module(mod)
            if attr and not hasattr(m, attr):
                raise AttributeError(f"missing {attr}")
            # optional light callables
            rows.append(
                {
                    "id": fid,
                    "title": title,
                    "module": mod,
                    "attr": attr,
                    "group": group,
                    "status": "OK",
                }
            )
            ok += 1
        except Exception as e:
            rows.append(
                {
                    "id": fid,
                    "title": title,
                    "module": mod,
                    "attr": attr,
                    "group": group,
                    "status": "FAIL",
                    "error": str(e)[:200],
                }
            )
            fail += 1
    return {
        "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(FEATURES),
        "ok": ok,
        "fail": fail,
        "complete": fail == 0,
        "features": rows,
        "external_manual": [
            "YouTube OAuth upload (user credentials)",
            "HeyGen/Synthesia/ElevenLabs paid render (API keys)",
            "Skool live classroom post (manual clipboard)",
            "faster-whisper install for local STT",
        ],
    }


def write_report(data: dict, path: Path) -> Path:
    lines = [
        f"# Course OS feature check",
        f"",
        f"- at: {data['at']}",
        f"- modules: **{data['ok']}/{data['total']} OK**",
        f"- complete: **{data['complete']}**",
        f"",
        f"| Status | ID | Title | Module |",
        f"|--------|----|-------|--------|",
    ]
    for r in data.get("features") or []:
        lines.append(
            f"| {r['status']} | `{r['id']}` | {r['title']} | `{r['module']}` |"
        )
    lines += ["", "## External (not automated)", ""]
    for x in data.get("external_manual") or []:
        lines.append(f"- {x}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Course OS feature registry check")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    data = check_features()
    if args.write:
        # app parent docs + BASE
        app = Path(__file__).resolve().parent
        write_report(data, app.parent / "docs" / "COURSE_OS_FEATURE_CHECK.md")
        try:
            import config as C

            write_report(data, Path(C.BASE) / "_course_os_feature_check.md")
        except Exception:
            pass
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Course OS features: {data['ok']}/{data['total']} OK · complete={data['complete']}")
        for r in data["features"]:
            mark = "✓" if r["status"] == "OK" else "✗"
            print(f"  {mark} {r['id']:14} {r['title']}")
        if data["fail"]:
            for r in data["features"]:
                if r["status"] == "FAIL":
                    print(f"    FAIL {r['module']}: {r.get('error')}")
    return 0 if data["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
