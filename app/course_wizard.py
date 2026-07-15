#!/usr/bin/env python3
"""
Course OS Wizard — chạy pipeline end-to-end với gate.

Steps:
  1 inventory (+ obsolescence)
  2 research (optional depth)
  3 structure (needs report; optional approve flag file)
  4 assets (lesson packs)
  5 captions + video prepare
  6 localize (optional)
  7 publish packs
  8 version bump

  python course_wizard.py --course X --full
  python course_wizard.py --course X --from structure --to publish
  python course_wizard.py --course X --approve-research   # ghi approve flag
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import config as C
import course_ops as OPS
import course_upgrade as CU

LogFn = Callable[[str], None]
APPROVE = "_upgrade_research_approved.json"
WIZARD_STATE = "_wizard_state.json"

STEPS = [
    "inventory",
    "research",
    "structure",
    "assets",
    "video",
    "localize",
    "publish",
    "version",
]


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def approve_research(root: Path, note: str = "") -> Path:
    p = Path(root) / APPROVE
    data = {"approved": True, "at": _now(), "note": note}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def is_research_approved(root: Path) -> bool:
    p = Path(root) / APPROVE
    if not p.exists():
        return False
    try:
        return bool(json.loads(p.read_text(encoding="utf-8")).get("approved"))
    except Exception:
        return False


def run_wizard(
    root: Path,
    *,
    steps: Optional[List[str]] = None,
    research_depth: str = "standard",
    do_web: bool = True,
    require_approve: bool = False,
    locales: Optional[str] = None,
    master_lang: Optional[str] = None,
    skip_localize: bool = False,
    skip_video: bool = False,
    skip_publish: bool = False,
    answers_file: Optional[str] = None,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    steps = steps or list(STEPS)
    if master_lang:
        C.set_course_master_lang(master_lang)
    state = {"started": _now(), "steps": {}, "root": str(root)}

    # questionnaire answers
    if answers_file:
        p = Path(answers_file)
        CU.save_answers(root, json.loads(p.read_text(encoding="utf-8")), log=log)

    if "inventory" in steps:
        _log("=== [1/8] INVENTORY + obsolescence ===", log)
        inv = CU.build_inventory(root, log=log)
        inv = OPS.score_inventory_lessons(inv)
        (root / CU.INVENTORY_JSON).write_text(
            json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        state["steps"]["inventory"] = inv.get("stats")

    if "research" in steps:
        _log(f"=== [2/8] RESEARCH depth={research_depth} ===", log)
        inv = json.loads((root / CU.INVENTORY_JSON).read_text(encoding="utf-8"))
        # cache key
        cache_key = f"research:{inv.get('course')}:{research_depth}:{inv.get('as_of')}"
        cached = OPS.cache_get(root, cache_key, max_age_days=7)
        if cached and cached.get("report_md"):
            _log("   dùng research cache (≤7 ngày)", log)
            research = cached
        else:
            # depth: quick = no web + fewer tools implied; deep = web
            use_web = do_web and research_depth != "quick"
            research = CU.research_market(
                inv,
                do_web=use_web,
                user_answers=CU.load_answers(root),
                root=root,
                log=log,
            )
            if research_depth == "deep":
                research["report_md"] = (research.get("report_md") or "") + (
                    "\n\n## Deep mode notes\n"
                    "Đã bật research sâu (web + phân tích mở rộng). "
                    "Nên fact-check tool changelog trước khi publish.\n"
                )
            OPS.cache_set(root, cache_key, research)
        paths = CU.write_reports(root, inv, research, log=log)
        state["steps"]["research"] = paths
        # auto-create style + glossary
        OPS.load_style(root)
        OPS.load_glossary(root)

    if "structure" in steps:
        _log("=== [3/8] STRUCTURE ===", log)
        if require_approve and not is_research_approved(root):
            raise RuntimeError(
                f"Chưa approve research. Chạy: course_wizard.py --approve-research "
                f"hoặc tạo {APPROVE}"
            )
        data = CU.generate_new_structure(root, log=log)
        state["steps"]["structure"] = {
            "chapters": len(data.get("chapters") or []),
            "lessons": sum(len(c.get("lessons") or []) for c in data.get("chapters") or []),
        }

    if "assets" in steps:
        _log("=== [4/8] ASSET PACKS ===", log)
        import course_studio as CS

        r = CS.generate_all_assets(
            root, lang=C.get_course_master_lang(), force=False, log=log
        )
        # captions for all
        dest = root / CU.UPGRADE_DIR
        for srt_n, ldir in enumerate(
            {p.parent for p in dest.rglob("talking_script.md") if "locales" not in p.parts},
            1,
        ):
            OPS.write_captions_for_lesson(ldir, log=log)
        state["steps"]["assets"] = r

    if "video" in steps and not skip_video:
        _log("=== [5/8] VIDEO PREPARE ===", log)
        import course_video as CV

        q = CV.prepare_video_jobs(root, provider="heygen", log=log)
        state["steps"]["video"] = {
            "jobs": q.get("jobs"),
            "usd_est": q.get("usd_est_total"),
        }

    if "localize" in steps and not skip_localize:
        _log("=== [6/8] LOCALIZE ===", log)
        import course_studio as CS

        locs = None
        if locales:
            locs = [x.strip() for x in locales.split(",") if x.strip()]
        r = CS.run_localize(root, locales=locs, log=log)
        # QA
        from course_qa import localization_qa

        qa = localization_qa(root, log=log)
        state["steps"]["localize"] = {"hub": r.get("hub"), "qa": qa.get("summary")}

    if "publish" in steps and not skip_publish:
        _log("=== [7/8] PUBLISH ===", log)
        import course_publish as CP

        state["steps"]["publish"] = CP.publish_all(root, log=log)

    if "version" in steps:
        _log("=== [8/8] VERSION ===", log)
        state["steps"]["version"] = OPS.bump_version(root, note="wizard full run")

    state["finished"] = _now()
    # pipeline status snapshot
    try:
        import course_status as ST

        st = ST.collect_status(root)
        ST.write_md(root, st)
        state["status"] = st.get("progress")
        state["next"] = st.get("next")
    except Exception as e:
        state["status_error"] = str(e)[:200]

    # optional webhook (settings / env)
    try:
        import course_notion as CN

        wh = CN.resolve_webhook()
        if wh:
            state["webhook"] = CN.notify_pipeline(root, wh, log=log)
    except Exception as e:
        state["webhook_error"] = str(e)[:200]

    (root / WIZARD_STATE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _log("=== WIZARD DONE ===", log)
    return state


def main(argv=None):
    ap = argparse.ArgumentParser(description="Course OS full wizard")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--full", action="store_true", help="Chạy tất cả steps")
    ap.add_argument("--from", dest="from_step", help="Bắt đầu từ step")
    ap.add_argument("--to", dest="to_step", help="Dừng sau step")
    ap.add_argument("--depth", default="standard", choices=["quick", "standard", "deep"])
    ap.add_argument("--no-web", action="store_true")
    ap.add_argument("--require-approve", action="store_true")
    ap.add_argument("--approve-research", action="store_true")
    ap.add_argument("--locales", help="es,ja,ko,...")
    ap.add_argument("--lang", help="master vi|en")
    ap.add_argument("--skip-localize", action="store_true")
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--skip-publish", action="store_true")
    ap.add_argument("--answers-file")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.approve_research:
        p = approve_research(root, note="CLI approve")
        print(f"Approved → {p}")
        return 0

    steps = list(STEPS)
    if args.from_step or args.to_step:
        fr = STEPS.index(args.from_step) if args.from_step in STEPS else 0
        to = STEPS.index(args.to_step) if args.to_step in STEPS else len(STEPS) - 1
        steps = STEPS[fr : to + 1]
    elif not args.full and not (args.from_step or args.to_step):
        # default full if no range
        steps = list(STEPS)

    try:
        state = run_wizard(
            root,
            steps=steps,
            research_depth=args.depth,
            do_web=not args.no_web,
            require_approve=args.require_approve,
            locales=args.locales,
            master_lang=args.lang,
            skip_localize=args.skip_localize,
            skip_video=args.skip_video,
            skip_publish=args.skip_publish,
            answers_file=args.answers_file,
        )
        print(json.dumps(state, ensure_ascii=False, indent=2)[:3000])
        return 0
    except Exception as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
