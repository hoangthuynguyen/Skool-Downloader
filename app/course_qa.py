#!/usr/bin/env python3
"""
QA: localization completeness, fact-check pass (LLM), structure diff,
eval rubric sample.

  python course_qa.py --course X --loc-qa
  python course_qa.py --course X --fact-check --limit 3
  python course_qa.py --course X --diff-structure
  python course_qa.py --course X --eval-sample
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
import course_ops as OPS
import course_upgrade as CU

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def localization_qa(root: Path, log: LogFn = print) -> dict:
    root = Path(root)
    hub = root / UPGRADE / "locales"
    master_lessons = sorted(
        {p.parent for p in (root / UPGRADE).rglob("lesson.md") if "locales" not in p.parts}
    )
    required = ["lesson.md", "talking_script.md", "summary.md"]
    issues = []
    locales = []
    if hub.is_dir():
        locales = [d.name for d in hub.iterdir() if d.is_dir()]
    for loc in locales:
        for ml in master_lessons:
            try:
                rel = ml.relative_to(root / UPGRADE)
            except ValueError:
                continue
            ld = hub / loc / rel
            if not ld.is_dir():
                issues.append({"locale": loc, "path": str(rel), "issue": "missing_lesson_dir"})
                continue
            for f in required:
                if not (ld / f).exists():
                    issues.append(
                        {"locale": loc, "path": str(rel / f), "issue": "missing_file"}
                    )
            # length blow-up vs master lesson.md
            m = ml / "lesson.md"
            t = ld / "lesson.md"
            if m.exists() and t.exists():
                try:
                    ratio = t.stat().st_size / max(1, m.stat().st_size)
                    if ratio > 3.5:
                        issues.append(
                            {
                                "locale": loc,
                                "path": str(rel / "lesson.md"),
                                "issue": f"length_blowup x{ratio:.1f}",
                            }
                        )
                except Exception:
                    pass
    summary = {
        "master_lessons": len(master_lessons),
        "locales": locales,
        "issues": len(issues),
        "as_of": _now(),
    }
    out = {
        "summary": summary,
        "issues": issues[:500],
    }
    p = root / UPGRADE / "_localization_qa.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f">> Loc QA: {summary['issues']} issues · {len(locales)} locales → {p.name}", log)
    return out


def fact_check_lessons(root: Path, limit: int = 5, log: LogFn = print) -> dict:
    root = Path(root)
    report = (root / CU.REPORT_MD).read_text(encoding="utf-8", errors="replace")[:8000] if (root / CU.REPORT_MD).exists() else ""
    lessons = sorted(
        {p.parent for p in (root / UPGRADE).rglob("lesson.md") if "locales" not in p.parts}
    )
    if limit > 0:
        lessons = lessons[:limit]
    results = []
    for ldir in lessons:
        body = (ldir / "lesson.md").read_text(encoding="utf-8", errors="replace")[:6000]
        system = (
            "You are a strict fact-checker for online courses. "
            "Flag claims about software features that may be outdated or invented. "
            "Respond in Vietnamese markdown: ## Verdict (OK|RISK|FAIL), ## Issues, ## Suggestions."
        )
        user = f"Research report excerpt:\n{report[:4000]}\n\nLesson content:\n{body}"
        try:
            text = CU._llm(system, user, log=log, max_tokens=2000, task="research")
        except Exception as e:
            text = f"## Verdict\nRISK\n\n## Issues\n- LLM error: {e}\n"
        (ldir / "fact_check.md").write_text(text, encoding="utf-8")
        verdict = "OK"
        if re.search(r"FAIL", text, re.I):
            verdict = "FAIL"
        elif re.search(r"RISK", text, re.I):
            verdict = "RISK"
        results.append({"lesson": str(ldir.name), "verdict": verdict})
        _log(f"   fact-check {ldir.name}: {verdict}", log)
    out = {"at": _now(), "results": results}
    (root / UPGRADE / "_fact_check_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def diff_structure(root: Path, log: LogFn = print) -> dict:
    """So inventory cũ vs structure mới."""
    root = Path(root)
    inv = {}
    if (root / CU.INVENTORY_JSON).exists():
        inv = json.loads((root / CU.INVENTORY_JSON).read_text(encoding="utf-8"))
    new = {}
    if (root / CU.STRUCTURE_JSON).exists():
        new = json.loads((root / CU.STRUCTURE_JSON).read_text(encoding="utf-8"))
    old_titles = {L.get("title") for L in inv.get("lessons") or []}
    new_titles = set()
    for ch in new.get("chapters") or []:
        for les in ch.get("lessons") or []:
            new_titles.add(les.get("title"))
    removed = sorted(old_titles - new_titles)
    added = sorted(new_titles - old_titles)
    kept = sorted(old_titles & new_titles)
    md = [
        "# Structure diff (old inventory → new structure)",
        f"",
        f"Generated: {_now()}",
        f"",
        f"- Old lessons: {len(old_titles)}",
        f"- New lessons: {len(new_titles)}",
        f"- Kept (same title): {len(kept)}",
        f"- Removed: {len(removed)}",
        f"- Added: {len(added)}",
        f"",
        f"## Removed",
        f"",
    ]
    for t in removed:
        md.append(f"- {t}")
    md += ["", "## Added", ""]
    for t in added:
        md.append(f"- {t}")
    md += ["", "## Explicit remove list (from structure JSON)", ""]
    for r in new.get("removed_lessons") or []:
        if isinstance(r, dict):
            md.append(f"- **{r.get('title')}** — {r.get('reason')}")
        else:
            md.append(f"- {r}")
    path = root / "_Upgrade_Structure_Diff.md"
    path.write_text("\n".join(md) + "\n", encoding="utf-8")
    data = {
        "old": len(old_titles),
        "new": len(new_titles),
        "removed": removed,
        "added": added,
        "kept": kept,
        "path": str(path),
    }
    _log(f">> Diff → {path.name} (−{len(removed)} +{len(added)})", log)
    return data


def eval_sample(root: Path, n: int = 5, log: LogFn = print) -> dict:
    """Rubric thô: đủ file asset + độ dài script."""
    lessons = sorted(
        {p.parent for p in (root / UPGRADE).rglob("lesson.md") if "locales" not in p.parts}
    )[:n]
    required = [
        "lesson.md",
        "talking_script.md",
        "workshop.md",
        "use_cases.md",
        "resources.md",
        "summary.md",
        "quiz.json",
    ]
    rows = []
    for ldir in lessons:
        score = 0
        missing = []
        for f in required:
            if (ldir / f).exists() and (ldir / f).stat().st_size > 40:
                score += 10
            else:
                missing.append(f)
        script_len = 0
        sp = ldir / "talking_script.md"
        if sp.exists():
            script_len = len(sp.read_text(encoding="utf-8", errors="replace").split())
            if script_len >= 200:
                score += 20
            elif script_len >= 80:
                score += 10
        rows.append(
            {
                "lesson": ldir.name,
                "score": score,
                "max": 90,
                "script_words": script_len,
                "missing": missing,
            }
        )
    out = {"at": _now(), "samples": rows}
    p = root / UPGRADE / "_eval_sample.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f">> Eval sample {len(rows)} lessons → {p.name}", log)
    return out


GOLDEN = "_eval_golden.json"


def eval_golden(
    root: Path,
    *,
    n: int = 8,
    save_baseline: bool = False,
    log: LogFn = print,
) -> dict:
    """
    Golden set: chấm cố định N bài đầu (ổn định path), so với baseline.
    --save-baseline ghi _eval_golden.json
    """
    root = Path(root)
    cur = eval_sample(root, n=n, log=log)
    by_lesson = {r["lesson"]: r for r in cur.get("samples") or []}
    avg = 0.0
    if by_lesson:
        avg = round(sum(r["score"] for r in by_lesson.values()) / len(by_lesson), 2)

    gp = root / UPGRADE / GOLDEN
    baseline = None
    if gp.exists() and not save_baseline:
        try:
            baseline = json.loads(gp.read_text(encoding="utf-8"))
        except Exception:
            baseline = None

    deltas = []
    if baseline:
        for r in baseline.get("samples") or []:
            name = r.get("lesson")
            now = by_lesson.get(name)
            if not now:
                deltas.append({"lesson": name, "delta": None, "note": "missing_now"})
                continue
            deltas.append(
                {
                    "lesson": name,
                    "before": r.get("score"),
                    "after": now.get("score"),
                    "delta": (now.get("score") or 0) - (r.get("score") or 0),
                }
            )

    report = {
        "at": _now(),
        "n": n,
        "avg_score": avg,
        "samples": cur.get("samples"),
        "baseline_at": (baseline or {}).get("at") if baseline else None,
        "baseline_avg": (baseline or {}).get("avg_score") if baseline else None,
        "deltas": deltas,
        "improved": sum(1 for d in deltas if isinstance(d.get("delta"), (int, float)) and d["delta"] > 0),
        "regressed": sum(1 for d in deltas if isinstance(d.get("delta"), (int, float)) and d["delta"] < 0),
    }

    if save_baseline or not gp.exists():
        base_doc = {
            "at": _now(),
            "avg_score": avg,
            "samples": cur.get("samples"),
            "note": "golden baseline",
        }
        (root / UPGRADE).mkdir(parents=True, exist_ok=True)
        gp.write_text(json.dumps(base_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        report["baseline_saved"] = True
        _log(f">> Golden baseline saved → {gp.name} avg={avg}", log)
    else:
        report["baseline_saved"] = False

    out_p = root / UPGRADE / "_eval_golden_report.json"
    out_p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        f"# Eval golden — {root.name}",
        f"",
        f"- at: {report['at']}",
        f"- avg now: **{avg}** / 90",
        f"- baseline avg: {report.get('baseline_avg')}",
        f"- improved: {report['improved']} · regressed: {report['regressed']}",
        f"",
        f"## Deltas",
        f"",
    ]
    for d in deltas[:40]:
        md.append(
            f"- {d.get('lesson')}: {d.get('before')} → {d.get('after')} (Δ {d.get('delta')})"
        )
    (root / UPGRADE / "_eval_golden_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    _log(
        f">> Golden eval avg={avg} improved={report['improved']} regressed={report['regressed']}",
        log,
    )
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Course QA tools")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--loc-qa", action="store_true")
    ap.add_argument("--fact-check", action="store_true")
    ap.add_argument("--diff-structure", action="store_true")
    ap.add_argument("--eval-sample", action="store_true")
    ap.add_argument("--eval-golden", action="store_true", help="Chấm + so baseline")
    ap.add_argument("--save-baseline", action="store_true", help="Ghi golden baseline")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.all or not any(
        [
            args.loc_qa,
            args.fact_check,
            args.diff_structure,
            args.eval_sample,
            args.eval_golden,
            args.save_baseline,
        ]
    ):
        args.loc_qa = args.diff_structure = args.eval_sample = True

    if args.diff_structure:
        diff_structure(root)
    if args.loc_qa:
        localization_qa(root)
    if args.eval_sample:
        eval_sample(root, n=args.limit)
    if args.eval_golden or args.save_baseline:
        eval_golden(
            root,
            n=max(args.limit, 8),
            save_baseline=args.save_baseline,
        )
    if args.fact_check:
        fact_check_lessons(root, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
