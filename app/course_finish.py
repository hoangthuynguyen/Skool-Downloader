#!/usr/bin/env python3
"""
Course OS FINISH — hoàn tất mọi bước còn thiếu (core + GTM pack).

  python course_finish.py --course X --dry-run
  python course_finish.py --course X --finish
  python course_finish.py --course X --ship-only
  python course_finish.py --course X --finish --skip-localize --provider local
  python course_finish.py --course X --offline   # không cần LLM API

Core: inventory → research → structure → assets → (localize) → review → video prepare → publish
Ship pack: ops, slides, pptx, thumbs, portal, ab, notion, cost, golden, status, board html, competitor(opt)
Offline: inventory + structure_from_dump + bootstrap assets + ship (no LLM)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import config as C

LogFn = Callable[[str], None]


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


CORE_KEYS = {
    "inventory",
    "research",
    "approve",
    "structure",
    "assets",
    "localize",
    "review",
    "video",
    "publish",
}


def plan_missing(root: Path) -> Dict[str, Any]:
    import course_status as ST

    st = ST.collect_status(root)
    missing_all = [s["key"] for s in st.get("steps") or [] if not s.get("done")]
    missing_core = [k for k in missing_all if k in CORE_KEYS]
    # ship artifacts (ops pack beyond core pipeline)
    ship = {
        "ops": (root / "_course_glossary.json").exists(),
        "slides": (root / "_slides").is_dir() and any((root / "_slides").iterdir()),
        "pptx": (root / "_pptx").is_dir() and any((root / "_pptx").rglob("*.pptx")),
        "thumbs": (root / "_thumbnails").is_dir()
        and any((root / "_thumbnails").rglob("*.png")),
        "portal": (root / "_student_portal" / "index.html").exists(),
        "ab": (root / "_ab_titles" / "ab_titles.json").exists(),
        "notion": (root / "_notion_export" / "README.md").exists(),
        "cost": (root / "_cost_dashboard.md").exists(),
        "golden": (root / "_upgrade_v2" / "_eval_golden.json").exists()
        or (root / "_upgrade_v2" / "_eval_sample.json").exists(),
        "board_html": (root / "_curriculum_board.html").exists(),
        "competitor": (root / "_Competitor_Scan.md").exists(),
        "status_md": (root / "_course_status.md").exists(),
    }
    # also treat status ship_* keys as ship missing
    for k in missing_all:
        if k.startswith("ship_"):
            short = k.replace("ship_", "")
            if short in ("slides", "pptx", "thumbs", "portal", "notion", "ops"):
                ship[short] = False
    missing_ship = [k for k, ok in ship.items() if not ok]
    return {
        "core_missing": missing_core,
        "ship_missing": missing_ship,
        "ship_done": ship,
        "status": st,
        "pct": st.get("progress", {}).get("pct"),
    }


def run_core_step(
    root: Path,
    key: str,
    *,
    provider: str = "local",
    skip_localize: bool = False,
    offline: bool = False,
    log: LogFn = print,
) -> str:
    import course_ops as OPS
    import course_upgrade as CU
    import course_wizard as W

    if key == "inventory":
        inv = CU.build_inventory(root, log=log)
        inv = OPS.score_inventory_lessons(inv)
        (root / CU.INVENTORY_JSON).write_text(
            json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return "inventory"
    if key == "research":
        if offline:
            # structure_from_dump also writes research stub if missing
            return "research-offline-deferred"
        inv = json.loads((root / CU.INVENTORY_JSON).read_text(encoding="utf-8"))
        research = CU.research_market(
            inv,
            do_web=True,
            user_answers=CU.load_answers(root),
            root=root,
            log=log,
        )
        CU.write_reports(root, inv, research, log=log)
        OPS.load_glossary(root)
        OPS.load_style(root)
        return "research"
    if key == "approve":
        # auto-approve on finish (user asked complete all)
        note = "auto-approve offline" if offline else "auto-approve via course_finish"
        W.approve_research(root, note=note)
        return "approve"
    if key == "structure":
        if offline:
            CU.structure_from_dump(root, log=log)
        else:
            CU.generate_new_structure(root, log=log)
        return "structure"
    if key == "assets":
        import course_studio as CS

        if offline:
            CS.bootstrap_assets_from_dump(root, force=False, log=log)
        else:
            CS.generate_all_assets(
                root, lang=C.get_course_master_lang(), force=False, log=log
            )
        return "assets"
    if key == "localize":
        if skip_localize or offline:
            return "localize-skipped"
        import course_studio as CS

        CS.run_localize(root, log=log)
        return "localize"
    if key == "review":
        import course_review as CR

        CR.build_review_queue(root, log=log)
        try:
            CR.export_side_by_side(root, status_filter="pending", limit=30, log=log)
        except Exception as e:
            _log(f"   side-by-side skip: {e}", log)
        return "review"
    if key == "video":
        import course_video as CV

        CV.prepare_video_jobs(root, provider=provider, log=log)
        # do not auto-run paid APIs; local can run 0 limit prepare only
        return "video"
    if key == "publish":
        import course_publish as CP

        CP.publish_all(root, log=log)
        return "publish"
    return f"unknown:{key}"


def run_ship_item(root: Path, key: str, log: LogFn = print) -> str:
    if key == "ops":
        import course_ops as OPS

        OPS.init_ops(root, log=log)
        return "ops"
    if key == "slides":
        import course_slides as SL

        SL.export_slides(root, log=log)
        return "slides"
    if key == "pptx":
        import course_pptx as PX

        PX.export_pptx_pack(root, log=log)
        return "pptx"
    if key == "thumbs":
        import course_thumbs as TH

        TH.export_thumbs(root, log=log)
        return "thumbs"
    if key == "portal":
        import course_portal as PO

        PO.build_portal(root, log=log)
        return "portal"
    if key == "ab":
        import course_ab as AB

        AB.generate_ab(root, log=log)
        return "ab"
    if key == "notion":
        import course_notion as CN

        CN.export_notion_pack(root, log=log)
        return "notion"
    if key == "cost":
        import course_ops as OPS

        OPS.cost_dashboard(root, log=log)
        return "cost"
    if key == "golden":
        import course_qa as QA

        QA.eval_sample(root, n=8, log=log)
        QA.eval_golden(root, n=8, save_baseline=True, log=log)
        return "golden"
    if key == "board_html":
        import course_board as CB

        if (root / "_upgrade_new_structure.json").exists():
            CB.export_html_board(root, CB.load(root))
        return "board_html"
    if key == "competitor":
        import course_competitor as CC

        CC.scan_competitors(root, use_llm=False, log=log)
        return "competitor"
    if key == "status_md":
        import course_status as ST

        st = ST.collect_status(root)
        ST.write_md(root, st)
        return "status_md"
    return f"unknown-ship:{key}"


def finish(
    root: Path,
    *,
    ship_only: bool = False,
    skip_localize: bool = False,
    skip_competitor: bool = False,
    skip_video_run: bool = True,
    provider: str = "local",
    offline: bool = False,
    dry_run: bool = False,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    plan = plan_missing(root)
    actions: List[str] = []
    errors: List[str] = []
    if offline:
        skip_localize = True

    _log(
        f">> FINISH plan offline={offline} core={plan['core_missing']} "
        f"ship={plan['ship_missing']}",
        log,
    )
    if dry_run:
        return {"dry_run": True, "offline": offline, "plan": plan, "at": _now()}

    # core pipeline order
    CORE_ORDER = [
        "inventory",
        "research",
        "approve",
        "structure",
        "assets",
        "localize",
        "review",
        "video",
        "publish",
    ]
    if not ship_only:
        for key in CORE_ORDER:
            if key not in plan["core_missing"]:
                continue
            if key == "localize" and (skip_localize or offline):
                # mark so status can count complete offline
                try:
                    d = root / "_upgrade_v2" / "locales"
                    d.mkdir(parents=True, exist_ok=True)
                    (d / "_SKIPPED_OFFLINE.txt").write_text(
                        f"Localize skipped at {_now()} "
                        f"(offline={offline} skip_flag={skip_localize})\n"
                        "Run: python course_studio.py --course … --localize\n",
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                actions.append("localize-skipped")
                continue
            if offline and key == "research":
                # research stub written by structure_from_dump
                continue
            try:
                _log(f"=== CORE · {key} ===", log)
                actions.append(
                    run_core_step(
                        root,
                        key,
                        provider=provider,
                        skip_localize=skip_localize,
                        offline=offline,
                        log=log,
                    )
                )
            except Exception as e:
                errors.append(f"{key}: {e}")
                _log(f"   ✗ {key}: {e}", log)
                if key in ("structure", "assets", "research") and not offline:
                    break

    # re-plan ship after core
    plan2 = plan_missing(root)
    SHIP_ORDER = [
        "ops",
        "board_html",
        "slides",
        "pptx",
        "thumbs",
        "portal",
        "ab",
        "golden",
        "cost",
        "notion",
        "competitor",
        "status_md",
    ]
    for key in SHIP_ORDER:
        if key not in plan2["ship_missing"] and key != "status_md":
            # always refresh status at end
            if key != "status_md":
                continue
        if key == "competitor" and skip_competitor:
            continue
        # if already done and not status, skip
        if key != "status_md" and key not in plan2["ship_missing"]:
            continue
        try:
            _log(f"=== SHIP · {key} ===", log)
            actions.append(run_ship_item(root, key, log=log))
        except Exception as e:
            errors.append(f"{key}: {e}")
            _log(f"   ✗ {key}: {e}", log)

    # ensure publish if assets exist but publish missing
    plan3 = plan_missing(root)
    if "publish" in plan3["core_missing"] and (root / "_upgrade_v2").is_dir():
        try:
            import course_publish as CP

            CP.publish_all(root, log=log)
            actions.append("publish-retry")
        except Exception as e:
            errors.append(f"publish: {e}")

    # final status + completion stamp
    import course_status as ST
    import course_ops as OPS

    final = ST.collect_status(root)
    ST.write_md(root, final)
    try:
        OPS.cost_dashboard(root, log=log)
    except Exception:
        pass

    stamp = {
        "at": _now(),
        "actions": actions,
        "errors": errors,
        "progress": final.get("progress"),
        "next": final.get("next"),
        "complete": final.get("progress", {}).get("pct") == 100 and not errors,
    }
    (root / "_course_finish.json").write_text(
        json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # human checklist
    lines = [
        f"# Course OS finish report — {root.name}",
        f"",
        f"- at: {stamp['at']}",
        f"- progress: {stamp['progress']}",
        f"- next: {stamp['next']}",
        f"- complete_flag: {stamp['complete']}",
        f"",
        f"## Actions",
        f"",
    ]
    for a in actions:
        lines.append(f"- {a}")
    if errors:
        lines += ["", "## Errors", ""]
        for e in errors:
            lines.append(f"- {e}")
    lines += [
        "",
        "## External (user credentials — not auto-run)",
        "",
        "- YouTube OAuth upload: `_publish/youtube_season/upload_drafts_HELPER.py`",
        "- HeyGen/Synthesia/ElevenLabs full render: set media keys + `course_video --run-queue`",
        "- Skool live post: open `_publish/skool_clipboard/clipboard.html`",
        "",
    ]
    (root / "_course_finish.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _log(
        f"--- FINISH done actions={len(actions)} errors={len(errors)} "
        f"pct={final.get('progress',{}).get('pct')} ---",
        log,
    )
    # webhook
    try:
        import course_notion as CN

        wh = CN.resolve_webhook()
        if wh:
            stamp["webhook"] = CN.notify_pipeline(root, wh, log=log)
    except Exception as e:
        stamp["webhook_error"] = str(e)[:200]

    return stamp


def main(argv=None):
    ap = argparse.ArgumentParser(description="Finish all remaining Course OS steps")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--finish", action="store_true", help="Chạy core + ship")
    ap.add_argument("--ship-only", action="store_true", help="Chỉ GTM/ops pack")
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Không LLM: inventory + structure dump + bootstrap assets + ship",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-localize", action="store_true")
    ap.add_argument("--skip-competitor", action="store_true")
    ap.add_argument("--provider", default="local", help="Video prepare provider")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if not (args.finish or args.ship_only or args.offline or args.dry_run):
        # default: dry-run plan
        args.dry_run = True
    if args.offline:
        args.finish = True  # offline implies full finish path

    res = finish(
        root,
        ship_only=args.ship_only,
        skip_localize=args.skip_localize or args.offline,
        skip_competitor=args.skip_competitor,
        provider=args.provider,
        offline=args.offline,
        dry_run=args.dry_run and not (args.finish or args.ship_only or args.offline),
    )
    print(json.dumps(res, ensure_ascii=False, indent=2)[:5000])
    return 0 if not res.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
