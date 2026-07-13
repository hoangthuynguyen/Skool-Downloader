#!/usr/bin/env python3
"""
Health check dinh ky toan kho (Phase 4).

  python health_check.py                 # quet + in tom tat
  python health_check.py --json          # in JSON
  python health_check.py --write         # ghi courses/_health.json + report md
  python health_check.py --notify        # (Windows) toast neu can chu y
  python health_check.py --fail-on-issue # exit 1 neu con bai thieu / token het han

Dung voi Task Scheduler / cron / launchd.
"""
from __future__ import annotations

import argparse, json, os, sys, time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as C
import progress as P
import updates as U


def _now():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def run_health(base=None):
    """Quet toan kho. Tra ve dict tong hop."""
    base = Path(base or C.BASE)
    courses = []
    total_missing = total_expired = total_lessons = total_done = total_size = total_fails = 0
    attention = 0
    try:
        import cleanup as CL
    except Exception:
        CL = None
    for meta in P.list_course_items(base):
        try:
            h = U.local_health(meta["root"])
            s = h["scan"]
        except Exception as e:
            courses.append({
                "item": meta["item"], "course": meta["course"],
                "root": str(meta["root"]), "error": str(e),
                "needs_attention": True, "fails": 0,
            })
            attention += 1
            continue
        missing = len(s.get("missing") or [])
        expired = len(s.get("native_expired") or [])
        n_fail = 0
        if CL:
            try:
                n_fail = len(CL.load_fails(meta["root"]))
            except Exception:
                n_fail = 0
        needs = bool(h.get("needs_attention") or n_fail)
        if needs:
            attention += 1
        rec = {
            "item": meta["item"],
            "course": meta["course"],
            "root": str(meta["root"]),
            "done": s.get("done") or 0,
            "total": s.get("total") or 0,
            "size": s.get("size") or 0,
            "missing": missing,
            "expired": expired,
            "fails": n_fail,
            "badge": h.get("badge"),
            "needs_attention": needs,
            "has_data": s.get("has_data"),
        }
        courses.append(rec)
        total_missing += missing
        total_expired += expired
        total_fails += n_fail
        total_lessons += rec["total"]
        total_done += rec["done"]
        total_size += rec["size"]
        # ghi meta nhe de dashboard hien badge
        if needs:
            try:
                U.mark_update_meta(meta["root"], {
                    "summary": f"Còn {missing} bài · {expired} hết hạn"
                               + (f" · {n_fail} fail" if n_fail else ""),
                    "has_updates": True,
                    "new_chapters": [],
                    "missing_lessons": s.get("missing") or [],
                    "native_expired": s.get("native_expired") or [],
                    "scan": {"total": s.get("total"), "done": s.get("done"),
                             "size": s.get("size"), "has_data": s.get("has_data")},
                })
            except Exception:
                pass

    return {
        "checked_at": _now(),
        "base": str(base),
        "courses": courses,
        "summary": {
            "n_courses": len(courses),
            "done": total_done,
            "total": total_lessons,
            "size": total_size,
            "missing": total_missing,
            "expired": total_expired,
            "fails": total_fails,
            "needs_attention": attention,
        },
    }


def write_health(report, base=None):
    base = Path(base or C.BASE)
    out_dir = base / "courses"
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / "_health.json"
    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # markdown
    sm = report["summary"]
    lines = [
        f"# Health check — {report['checked_at']}",
        "",
        f"- Khóa: **{sm['n_courses']}** · Bài **{sm['done']}/{sm['total']}**",
        f"- Thiếu: **{sm['missing']}** · Token hết hạn: **{sm['expired']}** · Fail: **{sm.get('fails', 0)}**",
        f"- Cần chú ý: **{sm['needs_attention']}** khóa",
        "",
        "| Khóa | Tiến độ | Thiếu | Hết hạn | Fail | Badge |",
        "|------|---------|-------|---------|------|-------|",
    ]
    for c in report["courses"]:
        if c.get("error"):
            lines.append(f"| {c['item']} | ERR | - | - | - | {c['error'][:40]} |")
            continue
        badge = (c.get("badge") or {}).get("label") or ""
        lines.append(
            f"| {c['item']} | {c['done']}/{c['total']} | {c['missing']} | {c['expired']} | "
            f"{c.get('fails', 0)} | {badge} |"
        )
    lines.append("")
    mp = out_dir / "_health.md"
    mp.write_text("\n".join(lines), encoding="utf-8")
    return jp, mp


def notify_windows(title, message):
    """Toast nhe — dung PowerShell balloon / msg. Fail im lang."""
    if os.name != "nt":
        return
    try:
        # balloon via PowerShell (khong can them lib)
        ps = (
            f'[void][Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms");'
            f'$n=New-Object System.Windows.Forms.NotifyIcon;'
            f'$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;'
            f'$n.ShowBalloonTip(8000,"{title}","{message}",'
            f'[System.Windows.Forms.ToolTipIcon]::Info);Start-Sleep -Seconds 9;$n.Dispose()'
        )
        import subprocess
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            creationflags=0x08000000,
        )
    except Exception:
        pass


def load_previous_health(base=None):
    p = Path(base or C.BASE) / "courses" / "_health.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def compute_delta(report, prev="__auto__"):
    """Sprint I: so sanh voi health lan truoc.

    prev='__auto__' (mac dinh): doc _health.json cu.
    prev=None: ep khong co snapshot truoc.
    prev=dict: so sanh voi dict do.
    """
    if prev == "__auto__":
        prev = load_previous_health(report.get("base"))
    sm = report["summary"]
    if not prev or not prev.get("summary"):
        return {
            "has_prev": False,
            "d_missing": None, "d_expired": None, "d_fails": None, "d_done": None,
            "improved": [], "worsened": [],
        }
    ps = prev["summary"]
    prev_by = {c.get("item"): c for c in (prev.get("courses") or []) if c.get("item")}
    improved, worsened = [], []
    for c in report.get("courses") or []:
        name = c.get("item")
        if not name or c.get("error"):
            continue
        old = prev_by.get(name) or {}
        d_miss = (c.get("missing") or 0) - (old.get("missing") or 0)
        d_fail = (c.get("fails") or 0) - (old.get("fails") or 0)
        if d_miss < 0 or d_fail < 0:
            improved.append(f"{name}: missing{d_miss:+d} fails{d_fail:+d}")
        if d_miss > 0 or d_fail > 0 or (c.get("expired") or 0) > (old.get("expired") or 0):
            worsened.append(
                f"{name}: missing{d_miss:+d} fails{d_fail:+d} "
                f"expired={(c.get('expired') or 0) - (old.get('expired') or 0):+d}"
            )
    return {
        "has_prev": True,
        "prev_at": prev.get("checked_at"),
        "d_missing": sm.get("missing", 0) - ps.get("missing", 0),
        "d_expired": sm.get("expired", 0) - ps.get("expired", 0),
        "d_fails": sm.get("fails", 0) - ps.get("fails", 0),
        "d_done": sm.get("done", 0) - ps.get("done", 0),
        "improved": improved[:12],
        "worsened": worsened[:12],
    }


def write_digest(report, base=None, prev=None):
    """Sprint I: _Health_Digest.md + delta vs lan truoc."""
    base = Path(base or C.BASE)
    out_dir = base / "courses"
    out_dir.mkdir(parents=True, exist_ok=True)
    # delta truoc khi ghi de so voi file cu
    delta = compute_delta(report, prev=prev if prev is not None else load_previous_health(base))
    sm = report["summary"]
    lines = [
        f"# Health Digest — {report['checked_at']}",
        "",
        "## Tổng quan",
        f"- Khóa: **{sm['n_courses']}** · Bài **{sm['done']}/{sm['total']}**",
        f"- Thiếu: **{sm['missing']}** · Hết hạn: **{sm['expired']}** · Fail: **{sm.get('fails', 0)}**",
        f"- Cần chú ý: **{sm['needs_attention']}** khóa",
        "",
    ]
    if delta.get("has_prev"):
        lines += [
            f"## So với lần trước ({delta.get('prev_at') or '?'})",
            f"- Δ done: **{delta['d_done']:+d}** · Δ missing: **{delta['d_missing']:+d}** · "
            f"Δ expired: **{delta['d_expired']:+d}** · Δ fails: **{delta['d_fails']:+d}**",
            "",
        ]
        if delta.get("improved"):
            lines.append("### Cải thiện")
            for x in delta["improved"]:
                lines.append(f"- ✅ {x}")
            lines.append("")
        if delta.get("worsened"):
            lines.append("### Xấu hơn")
            for x in delta["worsened"]:
                lines.append(f"- ⚠ {x}")
            lines.append("")
    else:
        lines += ["## So với lần trước", "- (chưa có snapshot trước)", ""]

    attention = [c for c in report["courses"] if c.get("needs_attention") or c.get("error")]
    lines += ["## Cần chú ý", ""]
    if not attention:
        lines.append("_Không có khóa cần chú ý._")
    else:
        for c in attention:
            if c.get("error"):
                lines.append(f"- **{c['item']}**: ERROR {c['error']}")
            else:
                lines.append(
                    f"- **{c['item']}**: {c['done']}/{c['total']} · "
                    f"thiếu {c['missing']} · hết hạn {c['expired']} · fail {c.get('fails', 0)}"
                )
    lines += ["", "---", "_Sinh bởi `health_check.py --digest`_", ""]
    dp = out_dir / "_Health_Digest.md"
    dp.write_text("\n".join(lines), encoding="utf-8")
    return dp, delta


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Skool Archiver warehouse health check")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true", help="Ghi _health.json + _health.md")
    ap.add_argument("--digest", action="store_true",
                    help="Sprint I: ghi _Health_Digest.md (co delta vs lan truoc)")
    ap.add_argument("--notify", action="store_true", help="Thong bao neu can chu y")
    ap.add_argument("--fail-on-issue", action="store_true", help="Exit 1 neu can chu y")
    a = ap.parse_args()

    prev = load_previous_health() if a.digest else None
    report = run_health()
    sm = report["summary"]
    if a.write or a.digest or not a.json:
        paths = write_health(report) if (a.write or a.digest) else None
        digest_path = None
        if a.digest:
            digest_path, delta = write_digest(report, prev=prev)
        if not a.json:
            print(f"Health @ {report['checked_at']}")
            print(f"  {sm['n_courses']} khóa · {sm['done']}/{sm['total']} bài · "
                  f"thiếu {sm['missing']} · hết hạn {sm['expired']} · "
                  f"fail {sm.get('fails', 0)} · cần chú ý {sm['needs_attention']}")
            for c in report["courses"]:
                if c.get("needs_attention") or c.get("error"):
                    tag = c.get("error") or (
                        f"missing={c.get('missing')} expired={c.get('expired')}"
                        + (f" fails={c.get('fails')}" if c.get("fails") else "")
                    )
                    print(f"  ! {c['item']}: {tag}")
            if paths:
                print(f"  >> {paths[0]}")
                print(f"  >> {paths[1]}")
            if digest_path:
                print(f"  >> {digest_path}")
                if delta.get("has_prev"):
                    print(f"  delta: done{delta['d_done']:+d} missing{delta['d_missing']:+d} "
                          f"fails{delta['d_fails']:+d}")
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if a.notify and sm["needs_attention"] > 0:
        msg = (
            f"{sm['needs_attention']} khóa cần chú ý "
            f"(thiếu {sm['missing']}, hết hạn {sm['expired']}, fail {sm.get('fails', 0)})"
        )
        try:
            import notify as N
            N.notify("Skool Archiver — Health", msg, level="warn")
        except Exception:
            notify_windows("Skool Archiver", msg)
        print("  (đã gửi thông báo)")

    if a.fail_on_issue and sm["needs_attention"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
