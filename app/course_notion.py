#!/usr/bin/env python3
"""
Notion-ready export + optional webhook notify khi pipeline xong.

  python course_notion.py --course X --export
  python course_notion.py --course X --webhook https://hooks.example/xxx
  python course_notion.py --course X --export --webhook-file ~/.course_webhook_url
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import config as C
import course_status as ST

LogFn = Callable[[str], None]
OUT = "_notion_export"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def export_notion_pack(root: Path, log: LogFn = print) -> dict:
    """
    Export markdown files easy to import into Notion (drag-drop).
    """
    root = Path(root)
    out = root / OUT
    out.mkdir(parents=True, exist_ok=True)

    status = ST.collect_status(root)
    ST.write_md(root, status)

    # index
    index = [
        f"# {root.name} — Course OS",
        f"",
        f"Synced: {_now()}",
        f"Progress: {status['progress']['pct']}% · next: {status.get('next')}",
        f"",
        f"## Pages",
        f"",
        f"- [[00_Status]]",
        f"- [[01_Structure]]",
        f"- [[02_Research]]",
        f"- [[03_Changelog]]",
        f"- [[04_Cost]]",
        f"- [[05_Lessons_Index]]",
        f"",
    ]
    (out / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")

    pages = {
        "00_Status.md": _read(root / "_course_status.md")
        or json.dumps(status, ensure_ascii=False, indent=2),
        "01_Structure.md": _read(root / "_Upgrade_New_Structure.md")
        or "(no structure yet)",
        "02_Research.md": _read(root / "_Upgrade_Research_Report.md")[:50000]
        or "(no research yet)",
        "03_Changelog.md": _read(root / "CHANGELOG.md") or "(no changelog)",
        "04_Cost.md": _read(root / "_cost_dashboard.md") or "(run cost dashboard)",
    }
    for name, body in pages.items():
        (out / name).write_text(
            f"# {name.replace('.md','').replace('_',' ')}\n\n{body}\n",
            encoding="utf-8",
        )

    # lessons index + one file per lesson (summary only to keep small)
    dest = root / "_upgrade_v2"
    lines = [f"# Lessons index — {root.name}", ""]
    n = 0
    if dest.is_dir():
        lessons = sorted(
            {p.parent for p in dest.rglob("lesson.md") if "locales" not in p.parts}
        )
        les_dir = out / "lessons"
        les_dir.mkdir(exist_ok=True)
        for ldir in lessons:
            title = ldir.name.split(" - ", 1)[-1]
            summary = _read(ldir / "summary.md") or _read(ldir / "lesson.md")[:3000]
            safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)[:60]
            fp = les_dir / f"{safe}.md"
            fp.write_text(f"# {title}\n\n{summary}\n", encoding="utf-8")
            lines.append(f"- [[{safe}]]")
            n += 1
    (out / "05_Lessons_Index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # database-ish CSV for Notion import
    csv_rows = ["title,status,next,pct,path"]
    csv_rows.append(
        f"\"{root.name}\",\"{status.get('next')}\",\"{status.get('next')}\","
        f"{status['progress']['pct']},\"{root}\""
    )
    (out / "course_row.csv").write_text("\n".join(csv_rows) + "\n", encoding="utf-8")

    meta = {
        "at": _now(),
        "dir": str(out),
        "lessons": n,
        "progress_pct": status["progress"]["pct"],
        "next": status.get("next"),
    }
    (out / "_export_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _log(f">> Notion pack → {out} ({n} lesson notes)", log)
    return meta


def post_webhook(
    url: str,
    payload: dict,
    log: LogFn = print,
    timeout: int = 20,
) -> dict:
    """POST JSON to webhook (Slack/Discord/Make/n8n/Notion automation)."""
    url = (url or "").strip()
    if not url:
        raise ValueError("Empty webhook URL")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "SkoolDownloader-CourseOS/2.28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")[:500]
            _log(f">> Webhook OK HTTP {r.status}", log)
            return {"ok": True, "status": r.status, "body": body}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:400]
        _log(f">> Webhook HTTP {e.code}: {err}", log)
        return {"ok": False, "status": e.code, "body": err}
    except Exception as e:
        _log(f">> Webhook error: {e}", log)
        return {"ok": False, "error": str(e)}


def notify_pipeline(root: Path, webhook_url: str, log: LogFn = print) -> dict:
    root = Path(root)
    st = ST.collect_status(root)
    payload = {
        "text": (
            f"Course OS · {root.name}\n"
            f"Progress {st['progress']['pct']}% · next={st.get('next')}\n"
            f"{st.get('next_hint')}"
        ),
        "course": root.name,
        "progress": st["progress"],
        "next": st.get("next"),
        "next_hint": st.get("next_hint"),
        "at": _now(),
        "root": str(root),
    }
    # Discord-friendly
    payload["content"] = payload["text"]
    return post_webhook(webhook_url, payload, log=log)


def resolve_webhook(cli_url: str = "", file_path: str = "") -> str:
    if cli_url:
        return cli_url.strip()
    if file_path:
        p = Path(file_path).expanduser()
        if p.exists():
            return p.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    env = (os.environ.get("COURSE_OS_WEBHOOK") or "").strip()
    if env:
        return env
    # settings
    try:
        s = json.loads(
            (Path(__file__).resolve().parent / ".settings.json").read_text(encoding="utf-8")
        )
        return (s.get("course_webhook_url") or "").strip()
    except Exception:
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Notion export + webhook notify")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--webhook", default="", help="Webhook URL")
    ap.add_argument("--webhook-file", default="", help="File chứa 1 dòng URL")
    ap.add_argument(
        "--set-webhook",
        default="",
        help="Lưu webhook URL vào .settings.json",
    )
    args = ap.parse_args(argv)

    if args.set_webhook:
        path = Path(__file__).resolve().parent / ".settings.json"
        try:
            s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            s = {}
        s["course_webhook_url"] = args.set_webhook.strip()
        path.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved course_webhook_url → {path}")
        return 0

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    did = False
    if args.export or not (args.webhook or args.webhook_file):
        print(json.dumps(export_notion_pack(root), ensure_ascii=False, indent=2))
        did = True

    wh = resolve_webhook(args.webhook, args.webhook_file)
    if args.webhook or args.webhook_file or (wh and args.export):
        if wh:
            print(json.dumps(notify_pipeline(root, wh), ensure_ascii=False, indent=2))
            did = True
        elif args.webhook or args.webhook_file:
            print("No webhook URL resolved", file=sys.stderr)
            return 2
    if not did:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
