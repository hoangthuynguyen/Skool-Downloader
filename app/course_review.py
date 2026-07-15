#!/usr/bin/env python3
"""
Locale human review queue.

  python course_review.py --course X --build
  python course_review.py --course X --status
  python course_review.py --course X --approve es "01 - C/01 - L" --note "ok"
  python course_review.py --course X --reject ja "01 - C/01 - L" --note "bad terms"
  python course_review.py --course X --export-pending
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import config as C

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
REVIEW = "_locale_review.json"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _log(msg: str, log: LogFn = print):
    log(msg)


def build_review_queue(root: Path, log: LogFn = print) -> dict:
    root = Path(root)
    hub = root / UPGRADE / "locales"
    items = []
    if hub.is_dir():
        for loc_dir in sorted([d for d in hub.iterdir() if d.is_dir()]):
            loc = loc_dir.name
            for lesson_md in loc_dir.rglob("lesson.md"):
                ldir = lesson_md.parent
                try:
                    rel = str(ldir.relative_to(loc_dir))
                except ValueError:
                    rel = ldir.name
                items.append(
                    {
                        "locale": loc,
                        "lesson": rel,
                        "path": str(ldir.relative_to(root)),
                        "status": "pending",  # pending | approved | rejected
                        "note": "",
                        "updated_at": "",
                    }
                )
    # merge previous decisions
    prev = {}
    rp = root / UPGRADE / REVIEW
    if rp.exists():
        try:
            old = json.loads(rp.read_text(encoding="utf-8"))
            for it in old.get("items") or []:
                prev[(it.get("locale"), it.get("lesson"))] = it
        except Exception:
            pass
    for it in items:
        key = (it["locale"], it["lesson"])
        if key in prev and prev[key].get("status") in ("approved", "rejected"):
            it["status"] = prev[key]["status"]
            it["note"] = prev[key].get("note") or ""
            it["updated_at"] = prev[key].get("updated_at") or ""

    data = {
        "updated_at": _now(),
        "total": len(items),
        "pending": sum(1 for x in items if x["status"] == "pending"),
        "approved": sum(1 for x in items if x["status"] == "approved"),
        "rejected": sum(1 for x in items if x["status"] == "rejected"),
        "items": items,
    }
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # checklist md
    md = [
        f"# Locale review queue",
        f"",
        f"- total: {data['total']}",
        f"- pending: {data['pending']}",
        f"- approved: {data['approved']}",
        f"- rejected: {data['rejected']}",
        f"",
        f"## Pending",
        f"",
    ]
    for it in items:
        if it["status"] != "pending":
            continue
        md.append(f"- [ ] `{it['locale']}` / `{it['lesson']}`")
    (root / UPGRADE / "_locale_review.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    _log(f">> Review queue: {data['pending']} pending / {data['total']}", log)
    return data


def _load(root: Path) -> dict:
    p = Path(root) / UPGRADE / REVIEW
    if not p.exists():
        return build_review_queue(root)
    return json.loads(p.read_text(encoding="utf-8"))


def _save(root: Path, data: dict):
    data["updated_at"] = _now()
    data["pending"] = sum(1 for x in data.get("items") or [] if x["status"] == "pending")
    data["approved"] = sum(1 for x in data.get("items") or [] if x["status"] == "approved")
    data["rejected"] = sum(1 for x in data.get("items") or [] if x["status"] == "rejected")
    data["total"] = len(data.get("items") or [])
    p = Path(root) / UPGRADE / REVIEW
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_status(root: Path, locale: str, lesson: str, status: str, note: str = "") -> bool:
    data = _load(root)
    ok = False
    for it in data.get("items") or []:
        if it.get("locale") == locale and (
            it.get("lesson") == lesson or lesson in (it.get("lesson") or "")
        ):
            it["status"] = status
            it["note"] = note
            it["updated_at"] = _now()
            ok = True
    if ok:
        _save(root, data)
    return ok


def export_pending(root: Path, log: LogFn = print) -> Path:
    data = _load(root)
    lines = ["locale\tlesson\tpath\tstatus\tnote"]
    for it in data.get("items") or []:
        if it.get("status") != "pending":
            continue
        lines.append(
            f"{it.get('locale')}\t{it.get('lesson')}\t{it.get('path')}\t"
            f"{it.get('status')}\t{it.get('note')}"
        )
    out = Path(root) / UPGRADE / "_locale_review_pending.tsv"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _log(f">> Pending TSV → {out}", log)
    return out


def relocalize_rejected(root: Path, log: LogFn = print) -> dict:
    """
    Re-run localize (force) chỉ cho các bài status=rejected.
    Group theo locale, gọi course_studio.localize_text_files.
    """
    import course_studio as ST

    root = Path(root)
    data = _load(root)
    rejected = [it for it in (data.get("items") or []) if it.get("status") == "rejected"]
    if not rejected:
        _log("Không có item rejected — bỏ qua", log)
        return {"relocalized": 0}

    master = ST.master_lang()
    dest = ST.upgrade_root(root)
    ok = 0
    errors = []
    for it in rejected:
        loc = it.get("locale") or ""
        lesson = it.get("lesson") or ""
        src = dest / lesson  # master path relative
        # lesson path in review is relative to locale hub
        # items path: locales/<loc>/...
        path_hint = it.get("path") or ""
        # master lesson dir = dest / lesson (lesson is rel under locale)
        master_dir = dest / lesson
        out_dir = dest / "locales" / loc / lesson
        if not master_dir.is_dir():
            # try from path
            if path_hint:
                out_dir = root / path_hint
                # strip locales/LOC/
                parts = Path(path_hint).parts
                if "locales" in parts:
                    i = parts.index("locales")
                    if i + 2 <= len(parts):
                        master_dir = dest / Path(*parts[i + 2 :])
        if not master_dir.is_dir():
            errors.append(f"missing master: {lesson}")
            _log(f"   ✗ missing master {lesson}", log)
            continue
        try:
            n = ST.localize_text_files(
                master_dir,
                out_dir,
                target_lang=loc,
                source_lang=master,
                course_root=root,
                force=True,
                log=log,
            )
            set_status(root, loc, lesson, "pending", note="relocalized — re-review")
            ok += 1
            _log(f"   ✓ relocalized {loc}/{lesson} ({n} files)", log)
        except Exception as e:
            errors.append(f"{loc}/{lesson}: {e}")
            _log(f"   ✗ {loc}/{lesson}: {e}", log)
    _log(f"--- RELOCALIZE rejected: ok={ok} err={len(errors)} ---", log)
    return {"relocalized": ok, "errors": errors}


def approve_all_pending(root: Path, note: str = "bulk approve") -> int:
    data = _load(root)
    n = 0
    for it in data.get("items") or []:
        if it.get("status") == "pending":
            it["status"] = "approved"
            it["note"] = note
            it["updated_at"] = _now()
            n += 1
    if n:
        _save(root, data)
    return n


def _read_snip(p: Path, max_chars: int = 2500) -> str:
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return t[:max_chars]


def render_approved(
    root: Path,
    *,
    provider: str = "elevenlabs",
    locale: Optional[str] = None,
    limit: int = 0,
    log: LogFn = print,
) -> dict:
    """
    Pipeline: locale đã approved → prepare video từ locales/<loc>/ → run-queue.
    """
    import course_video as CV

    root = Path(root)
    data = _load(root)
    approved = [
        it
        for it in (data.get("items") or [])
        if it.get("status") == "approved"
        and (not locale or it.get("locale") == locale)
    ]
    if not approved:
        _log("Không có item approved (filter locale?)", log)
        return {"rendered_locales": [], "note": "no approved items"}

    # group by locale
    by_loc: dict = {}
    for it in approved:
        by_loc.setdefault(it.get("locale") or "", []).append(it)

    results = []
    for loc, items in by_loc.items():
        if not loc:
            continue
        _log(f">> Render approved locale={loc} ({len(items)} lessons)", log)
        try:
            CV.prepare_video_jobs(
                root,
                provider=provider,
                force=False,
                limit=limit,
                locale=loc,
                log=log,
            )
            run = CV.run_queue(root, limit=limit, log=log)
            results.append({"locale": loc, "lessons": len(items), "run": run})
        except Exception as e:
            results.append({"locale": loc, "error": str(e)[:300]})
            _log(f"   ✗ {loc}: {e}", log)
    return {"rendered_locales": results, "provider": provider}


def export_side_by_side(
    root: Path,
    *,
    status_filter: str = "pending",
    limit: int = 40,
    log: LogFn = print,
) -> Path:
    """
    HTML side-by-side master vs locale (lesson.md excerpt).
    Mở bằng browser để review nhanh.
    """
    import html as H

    root = Path(root)
    data = _load(root)
    items = data.get("items") or []
    if status_filter and status_filter != "all":
        items = [it for it in items if it.get("status") == status_filter]
    items = items[: max(1, limit)]

    dest_master = root / UPGRADE
    cards = []
    for it in items:
        loc = it.get("locale") or ""
        lesson = it.get("lesson") or ""
        master_p = dest_master / lesson / "lesson.md"
        loc_p = dest_master / "locales" / loc / lesson / "lesson.md"
        if not loc_p.exists() and it.get("path"):
            loc_p = root / it["path"] / "lesson.md"
        m_txt = H.escape(_read_snip(master_p))
        l_txt = H.escape(_read_snip(loc_p))
        st = it.get("status") or "pending"
        cards.append(
            f"""
<section class="card" data-locale="{H.escape(loc)}" data-lesson="{H.escape(lesson)}">
  <header>
    <strong>{H.escape(loc)}</strong> · <code>{H.escape(lesson)}</code>
    <span class="badge {H.escape(st)}">{H.escape(st)}</span>
  </header>
  <div class="cols">
    <div class="col"><h3>Master</h3><pre>{m_txt or '(missing)'}</pre></div>
    <div class="col"><h3>{H.escape(loc)}</h3><pre>{l_txt or '(missing)'}</pre></div>
  </div>
  <div class="actions">
    <p class="hint">CLI: approve →
    <code>python course_review.py --course "{H.escape(root.name)}" --approve {H.escape(loc)} "{H.escape(lesson)}"</code>
    · reject tương tự</p>
  </div>
</section>
"""
        )

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Locale review — {H.escape(root.name)}</title>
<style>
  :root {{ --bg:#0f172a; --card:#1e293b; --fg:#f1f5f9; --muted:#94a3b8; --acc:#38bdf8; --ok:#34d399; --bad:#f87171; }}
  body {{ margin:0; font-family:system-ui,sans-serif; background:var(--bg); color:var(--fg); padding:1.5rem; }}
  h1 {{ font-size:1.4rem; }} .meta {{ color:var(--muted); margin-bottom:1.5rem; }}
  .card {{ background:var(--card); border-radius:12px; padding:1rem 1.2rem; margin:0 0 1.2rem; border:1px solid #334155; }}
  header {{ display:flex; gap:.75rem; align-items:center; flex-wrap:wrap; margin-bottom:.8rem; }}
  .badge {{ font-size:.75rem; padding:.15rem .5rem; border-radius:999px; background:#334155; }}
  .badge.approved {{ background:#064e3b; color:var(--ok); }}
  .badge.rejected {{ background:#7f1d1d; color:var(--bad); }}
  .badge.pending {{ background:#1e3a5f; color:var(--acc); }}
  .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; }}
  @media (max-width:900px) {{ .cols {{ grid-template-columns:1fr; }} }}
  .col h3 {{ margin:0 0 .4rem; font-size:.9rem; color:var(--acc); }}
  pre {{ white-space:pre-wrap; word-break:break-word; background:#0f172a; padding:.8rem;
    border-radius:8px; font-size:12px; line-height:1.4; max-height:420px; overflow:auto; margin:0; }}
  code {{ font-size:11px; color:#cbd5e1; }} .hint {{ color:var(--muted); font-size:12px; }}
</style></head>
<body>
  <h1>Locale review — {H.escape(root.name)}</h1>
  <p class="meta">Filter: <b>{H.escape(status_filter)}</b> · {len(cards)} cards · {_now()}</p>
  {''.join(cards) if cards else '<p>No items. Chạy --build trước.</p>'}
</body></html>
"""
    out = root / UPGRADE / "_locale_review_side_by_side.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    _log(f">> Side-by-side HTML → {out} ({len(cards)} cards)", log)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Locale human review queue")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--approve", nargs=2, metavar=("LOCALE", "LESSON"))
    ap.add_argument("--reject", nargs=2, metavar=("LOCALE", "LESSON"))
    ap.add_argument("--note", default="")
    ap.add_argument("--export-pending", action="store_true")
    ap.add_argument(
        "--side-by-side",
        action="store_true",
        help="HTML master vs locale (mở bằng browser)",
    )
    ap.add_argument("--filter", default="pending", help="pending|approved|rejected|all")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument(
        "--relocalize-rejected",
        action="store_true",
        help="Force re-translate rejected lessons → status pending",
    )
    ap.add_argument(
        "--approve-all-pending",
        action="store_true",
        help="Bulk approve mọi item pending",
    )
    ap.add_argument(
        "--render-approved",
        action="store_true",
        help="Prepare+run video queue cho locale đã approved (1 locale / lần)",
    )
    ap.add_argument("--provider", default="elevenlabs", help="Provider khi --render-approved")
    ap.add_argument("--locale", default="", help="Locale filter cho render-approved")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    if args.build:
        print(json.dumps(build_review_queue(root), ensure_ascii=False, indent=2)[:2000])
        return 0
    if args.status:
        d = _load(root)
        print(
            json.dumps(
                {
                    "total": d.get("total"),
                    "pending": d.get("pending"),
                    "approved": d.get("approved"),
                    "rejected": d.get("rejected"),
                },
                indent=2,
            )
        )
        return 0
    if args.approve:
        ok = set_status(root, args.approve[0], args.approve[1], "approved", args.note)
        print("OK" if ok else "NOT FOUND")
        return 0 if ok else 1
    if args.reject:
        ok = set_status(root, args.reject[0], args.reject[1], "rejected", args.note)
        print("OK" if ok else "NOT FOUND")
        return 0 if ok else 1
    if args.export_pending:
        export_pending(root)
        return 0
    if args.side_by_side:
        if not (root / UPGRADE / REVIEW).exists():
            build_review_queue(root)
        p = export_side_by_side(
            root, status_filter=args.filter, limit=args.limit
        )
        print(p)
        return 0
    if args.relocalize_rejected:
        print(json.dumps(relocalize_rejected(root), ensure_ascii=False, indent=2))
        return 0
    if args.approve_all_pending:
        n = approve_all_pending(root, args.note or "bulk approve")
        print(f"approved {n}")
        return 0
    if args.render_approved:
        print(
            json.dumps(
                render_approved(
                    root,
                    provider=args.provider,
                    locale=(args.locale or None),
                    limit=args.limit,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    # default build
    build_review_queue(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
