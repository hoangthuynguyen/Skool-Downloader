#!/usr/bin/env python3
"""
Publish packs: Skool-ready tree, YouTube season, email nurture, lead magnets,
sales pack, gumroad zip, license note.

  python course_publish.py --course X --all
  python course_publish.py --course X --skool --youtube --email --leads --zip
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import config as C
import course_ops as OPS

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
PUB = "_publish"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _lessons(root: Path) -> List[Path]:
    dest = Path(root) / UPGRADE
    if not dest.is_dir():
        return []
    return sorted(
        {p.parent for p in dest.rglob("lesson.md") if "locales" not in p.parts}
    )


def publish_skool_tree(root: Path, log: LogFn = print) -> Path:
    """Cây mô tả sẵn sàng copy/paste lên Skool classroom."""
    root = Path(root)
    out = root / PUB / "skool_export"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    lessons = _lessons(root)
    index = ["# Skool export", "", f"Generated: {_now()}", "", "## Classroom outline", ""]
    for ldir in lessons:
        try:
            rel = ldir.relative_to(root / UPGRADE)
        except ValueError:
            rel = Path(ldir.name)
        dest = out / rel
        dest.mkdir(parents=True, exist_ok=True)
        # description for skool post
        body = _read(ldir / "lesson.md") or _read(ldir / "description.md")
        summary = _read(ldir / "summary.md")
        resources = _read(ldir / "resources.md")
        post = f"# {ldir.name.split(' - ',1)[-1]}\n\n{body}\n\n---\n\n{summary}\n\n## Resources\n\n{resources}\n"
        (dest / "post.md").write_text(post, encoding="utf-8")
        # copy resources folder if any
        for name in ("quiz.json", "talking_script.md", "workshop.md"):
            src = ldir / name
            if src.exists():
                shutil.copy2(src, dest / name)
        index.append(f"- `{rel}`")
    (out / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    _log(f">> Skool export → {out}", log)
    return out


def publish_youtube_pack(root: Path, log: LogFn = print) -> Path:
    root = Path(root)
    out = root / PUB / "youtube_season"
    out.mkdir(parents=True, exist_ok=True)
    rows = ["#\tTitle\tDescription\tTags\tChapters"]
    md = ["# YouTube season pack", "", f"Generated: {_now()}", ""]
    for i, ldir in enumerate(_lessons(root), 1):
        title = ldir.name.split(" - ", 1)[-1]
        summary = _read(ldir / "summary.md")[:1500]
        script = _read(ldir / "talking_script.md")
        # fake chapters every ~minute of script
        words = len(re.findall(r"\w+", script))
        mins = max(1, words // 140)
        chapters = "0:00 Intro"
        t = 0
        for c in range(1, min(6, mins + 1)):
            t += max(1, mins // 5)
            chapters += f" | {t//60}:{t%60:02d} Part {c}"
        tags = "course,tutorial,ai," + title.replace(" ", "").lower()[:40]
        desc = f"{title}\n\n{summary}\n\n#course #ai"
        rows.append(f"{i}\t{title}\t{desc.replace(chr(9),' ')}\t{tags}\t{chapters}")
        md.append(f"## {i:02d}. {title}\n\n{desc}\n\nChapters: {chapters}\n")
    (out / "youtube_bulk.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (out / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    _log(f">> YouTube pack → {out}", log)
    return out


def publish_email_nurture(root: Path, log: LogFn = print) -> Path:
    root = Path(root)
    out = root / PUB / "email_nurture"
    out.mkdir(parents=True, exist_ok=True)
    lessons = _lessons(root)[:14]
    lines = ["# Email nurture sequence", "", f"Generated: {_now()}", ""]
    for i, ldir in enumerate(lessons, 1):
        title = ldir.name.split(" - ", 1)[-1]
        summary = _read(ldir / "summary.md")[:800]
        body = (
            f"Subject: Day {i}: {title}\n\n"
            f"Hi {{first_name}},\n\n"
            f"Today's focus: **{title}**\n\n"
            f"{summary}\n\n"
            f"Reply with your biggest question.\n\n— Team\n"
        )
        (out / f"day_{i:02d}.md").write_text(body, encoding="utf-8")
        lines.append(f"- day_{i:02d}.md — {title}")
    (out / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _log(f">> Email nurture → {out} ({len(lessons)} mails)", log)
    return out


def publish_lead_magnets(root: Path, log: LogFn = print) -> Path:
    root = Path(root)
    out = root / PUB / "lead_magnets"
    out.mkdir(parents=True, exist_ok=True)
    # one checklist per top-level chapter
    dest = root / UPGRADE
    chapters = sorted([d for d in dest.iterdir() if d.is_dir() and re.match(r"\d+", d.name)])
    for ch in chapters:
        title = ch.name.split(" - ", 1)[-1]
        checks = [f"# Checklist: {title}", "", f"As of {datetime.now().date()}", ""]
        for les in sorted([d for d in ch.iterdir() if d.is_dir()]):
            lt = les.name.split(" - ", 1)[-1]
            checks.append(f"## {lt}")
            # pull todos from summary if any
            sm = _read(les / "summary.md")
            todos = re.findall(r"^[\-\*]\s+(.+)$", sm, re.M)
            if not todos:
                todos = [f"Complete lesson: {lt}", "Apply one action today"]
            for t in todos[:8]:
                checks.append(f"- [ ] {t}")
            checks.append("")
        (out / f"checklist_{ch.name[:40]}.md").write_text("\n".join(checks), encoding="utf-8")
    _log(f">> Lead magnets → {out}", log)
    return out


def publish_sales_pack(root: Path, locale: str = "en", log: LogFn = print) -> Path:
    root = Path(root)
    out = root / PUB / f"sales_{locale}"
    out.mkdir(parents=True, exist_ok=True)
    name = root.name
    structure = ""
    sp = root / "_Upgrade_New_Structure.md"
    if sp.exists():
        structure = sp.read_text(encoding="utf-8", errors="replace")[:4000]
    page = f"""# {name} — Updated Course

## Promise
Master the modern workflows covered in this curriculum — updated for today.

## Who it's for
Builders who want practical, current playbooks (not outdated screenshots).

## What's inside
{structure or '(structure pending)'}

## Guarantee
Learn by doing. Complete the workshops. Keep the templates.

## CTA
Enroll today — {locale.upper()} edition.

---
Generated: {_now()}
"""
    (out / "sales_page.md").write_text(page, encoding="utf-8")
    ads = f"""# Ads hooks ({locale})

1. Still using outdated automations? This course was rebuilt for {_now()[:4]}.
2. From messy notes to a full modern curriculum — with workshops.
3. Scripts, checklists, and use-cases you can ship this week.

# Keywords
online course, automation, ai, {name}
"""
    (out / "ads_hooks.md").write_text(ads, encoding="utf-8")
    _log(f">> Sales pack → {out}", log)
    return out


def publish_zip(root: Path, log: LogFn = print) -> Path:
    root = Path(root)
    pub = root / PUB
    pub.mkdir(exist_ok=True)
    ver = OPS.bump_version(root, note="publish zip pack")
    zpath = pub / f"{root.name}_{ver.get('version','pack')}.zip"
    # Never pack media / archives (zip-into-self was a 12GB runaway bug)
    skip_ext = {
        ".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v",
        ".mp3", ".wav", ".aiff", ".m4a", ".flac",
        ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2",
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".psd",
        ".iso", ".dmg",
    }
    max_file = 8 * 1024 * 1024  # 8MB per file safety
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        # upgrade text packs only
        up = root / UPGRADE
        if up.is_dir():
            for f in up.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix.lower() in skip_ext:
                    continue
                if f.resolve() == zpath.resolve():
                    continue
                try:
                    if f.stat().st_size > max_file:
                        continue
                except OSError:
                    continue
                z.write(f, f.relative_to(root).as_posix())
        # publish subfolders EXCEPT the zip itself / nested zips
        if pub.is_dir():
            for f in pub.rglob("*"):
                if not f.is_file():
                    continue
                if f.resolve() == zpath.resolve():
                    continue
                if f.suffix.lower() in skip_ext:
                    continue
                try:
                    if f.stat().st_size > max_file:
                        continue
                except OSError:
                    continue
                z.write(f, f.relative_to(root).as_posix())
        for name in (
            "_Upgrade_New_Structure.md",
            "_Upgrade_Research_Report.md",
            "CHANGELOG.md",
            "_course_glossary.json",
        ):
            p = root / name
            if p.exists():
                z.write(p, name)
        lic = (
            f"LICENSE NOTICE\n"
            f"Course pack generated { _now() }.\n"
            f"Student license: personal learning only.\n"
            f"Seller license: redistribution requires your own rights to source materials.\n"
        )
        z.writestr("LICENSE.txt", lic)
    size_mb = zpath.stat().st_size / (1024 * 1024)
    _log(f">> Zip → {zpath.name} ({size_mb:.1f} MB)", log)
    return zpath


def publish_skool_clipboard(root: Path, log: LogFn = print) -> Path:
    """
    1 pack copy-paste: mỗi bài 1 block post + HTML helper copy button.
    """
    import html as H

    root = Path(root)
    out = root / PUB / "skool_clipboard"
    out.mkdir(parents=True, exist_ok=True)
    lessons = _lessons(root)
    all_md = [f"# Skool clipboard pack — {root.name}", "", f"Generated: {_now()}", ""]
    cards = []
    for i, ldir in enumerate(lessons, 1):
        title = ldir.name.split(" - ", 1)[-1]
        body = _read(ldir / "lesson.md") or _read(ldir / "description.md")
        summary = _read(ldir / "summary.md")
        resources = _read(ldir / "resources.md")
        post = (
            f"# {title}\n\n{body.strip()}\n\n---\n\n"
            f"{summary.strip()}\n\n## Resources\n\n{resources.strip()}\n"
        )
        safe_name = re.sub(r"[^\w\-]+", "_", title)[:40]
        (out / f"{i:02d}_{safe_name}.md").write_text(post, encoding="utf-8")
        all_md.append(f"\n\n===== LESSON {i}: {title} =====\n\n{post}")
        safe = H.escape(post)
        cards.append(
            f"""<section class="card"><h2>{i}. {H.escape(title)}</h2>
<textarea id="t{i}" rows="12">{safe}</textarea>
<button type="button" onclick="copyT('t{i}', this)">Copy post</button></section>"""
        )
    (out / "ALL_POSTS.md").write_text("\n".join(all_md) + "\n", encoding="utf-8")
    html_page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Skool clipboard — {H.escape(root.name)}</title>
<style>
body{{font-family:system-ui;background:#0f172a;color:#f8fafc;padding:1.5rem;max-width:900px;margin:auto}}
.card{{background:#1e293b;border-radius:12px;padding:1rem;margin:0 0 1rem}}
textarea{{width:100%;background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:.6rem;font-size:12px}}
button{{margin-top:.5rem;background:#38bdf8;color:#0f172a;border:0;border-radius:8px;padding:.5rem 1rem;font-weight:600;cursor:pointer}}
button.ok{{background:#34d399}}
</style></head><body>
<h1>Skool clipboard</h1>
<p>Copy từng post → dán classroom Skool. Generated {_now()}</p>
{''.join(cards)}
<script>
function copyT(id, btn){{
  const el=document.getElementById(id);
  el.select();
  navigator.clipboard.writeText(el.value).then(()=>{{btn.textContent='Copied ✓';btn.classList.add('ok');}});
}}
</script></body></html>"""
    hp = out / "clipboard.html"
    hp.write_text(html_page, encoding="utf-8")
    _log(f">> Skool clipboard → {out} ({len(lessons)} posts)", log)
    return out


def publish_sales_html(root: Path, locale: str = "en", log: LogFn = print) -> Path:
    """Landing page HTML tĩnh từ sales pack + structure."""
    import html as H

    root = Path(root)
    # ensure md exists
    md_dir = publish_sales_pack(root, locale=locale, log=log)
    name = H.escape(root.name)
    structure = ""
    sp = root / "_Upgrade_New_Structure.md"
    if sp.exists():
        structure = sp.read_text(encoding="utf-8", errors="replace")[:5000]
    # crude md→html lines
    body_lines = []
    for ln in structure.splitlines()[:80]:
        if ln.startswith("# "):
            body_lines.append(f"<h2>{H.escape(ln[2:])}</h2>")
        elif ln.startswith("## "):
            body_lines.append(f"<h3>{H.escape(ln[3:])}</h3>")
        elif ln.startswith("- "):
            body_lines.append(f"<li>{H.escape(ln[2:])}</li>")
        elif ln.strip():
            body_lines.append(f"<p>{H.escape(ln)}</p>")
    page = f"""<!DOCTYPE html>
<html lang="{H.escape(locale)}"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name} — Course</title>
<style>
:root{{--bg:#0b1220;--fg:#f8fafc;--acc:#38bdf8;--card:#111827}}
*{{box-sizing:border-box}} body{{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);line-height:1.5}}
.hero{{padding:4rem 1.5rem 2rem;text-align:center;background:linear-gradient(160deg,#0f172a,#1e3a5f)}}
.hero h1{{font-size:clamp(1.8rem,4vw,2.8rem);margin:0 0 .5rem}}
.hero p{{color:#cbd5e1;max-width:640px;margin:.5rem auto 1.5rem}}
.cta{{display:inline-block;background:var(--acc);color:#0f172a;padding:.85rem 1.4rem;border-radius:10px;font-weight:700;text-decoration:none}}
.wrap{{max-width:800px;margin:0 auto;padding:2rem 1.25rem 4rem}}
.card{{background:var(--card);border:1px solid #1f2937;border-radius:14px;padding:1.25rem 1.5rem;margin:1rem 0}}
h2,h3{{color:var(--acc)}} li{{margin:.25rem 0}}
footer{{text-align:center;color:#64748b;padding:2rem;font-size:.85rem}}
</style></head><body>
<section class="hero">
  <h1>{name}</h1>
  <p>Curriculum rebuilt for today — workshops, scripts, and practical playbooks.</p>
  <a class="cta" href="#curriculum">See curriculum</a>
</section>
<div class="wrap" id="curriculum">
  <div class="card">
    <h2>What's inside</h2>
    {''.join(body_lines) or '<p>Structure pending — run course upgrade first.</p>'}
  </div>
  <div class="card">
    <h2>Promise</h2>
    <p>Master modern workflows covered in this course — updated, not recycled screenshots.</p>
  </div>
</div>
<footer>Generated {_now()} · locale {H.escape(locale)} · Course OS</footer>
</body></html>"""
    out = Path(md_dir) / "sales_page.html"
    out.write_text(page, encoding="utf-8")
    _log(f">> Sales HTML → {out}", log)
    return out


def publish_youtube_upload_helper(root: Path, log: LogFn = print) -> Path:
    """
    Script helper + README cho YouTube draft upload (user tự gắn OAuth).
    Không gọi API thật (cần credentials user).
    """
    root = Path(root)
    ydir = publish_youtube_pack(root, log=log)
    helper = ydir / "upload_drafts_HELPER.py"
    helper.write_text(
        '''#!/usr/bin/env python3
"""
YouTube draft upload HELPER — yêu cầu Google API credentials.

Cài:
  pip install google-api-python-client google-auth-oauthlib

1) Tạo OAuth client (Desktop) trên Google Cloud, tải client_secret.json
2) Đặt cạnh script: client_secret.json
3) Đặt video file theo tên lesson (tuỳ chỉnh PATHS)
4) python upload_drafts_HELPER.py

Script mặc định upload privacyStatus=private (draft-like).
"""
from __future__ import annotations
import csv
from pathlib import Path

# --- cấu hình user ---
TSV = Path(__file__).with_name("youtube_bulk.tsv")
CLIENT_SECRET = Path(__file__).with_name("client_secret.json")
# map index -> video path (điền tay)
VIDEO_PATHS = {
    # 1: Path("/path/to/video1.mp4"),
}


def main():
    if not CLIENT_SECRET.exists():
        print("Thiếu client_secret.json — xem README trong thư mục này.")
        return 2
    if not VIDEO_PATHS:
        print("Điền VIDEO_PATHS trong script trước khi upload.")
        print(f"Metadata sẵn: {TSV}")
        return 2
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("pip install google-api-python-client google-auth-oauthlib")
        return 2
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), scopes)
    creds = flow.run_local_server(port=0)
    yt = build("youtube", "v3", credentials=creds)
    rows = list(csv.DictReader(TSV.open(encoding="utf-8"), delimiter="\\t"))
    for row in rows:
        try:
            idx = int(row.get("#") or 0)
        except ValueError:
            continue
        path = VIDEO_PATHS.get(idx)
        if not path or not Path(path).exists():
            print(f"skip {idx}: no video")
            continue
        body = {
            "snippet": {
                "title": (row.get("Title") or "")[:100],
                "description": row.get("Description") or "",
                "tags": [t for t in (row.get("Tags") or "").split(",") if t],
                "categoryId": "27",
            },
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(str(path), chunksize=-1, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        print(f"uploading {idx}…")
        res = None
        while res is None:
            status, res = req.next_chunk()
            if status:
                print(f"  {int(status.progress()*100)}%")
        print("  id=", res.get("id"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
        encoding="utf-8",
    )
    (ydir / "UPLOAD_README.md").write_text(
        f"""# YouTube draft upload

1. Pack metadata: `youtube_bulk.tsv` (đã generate)
2. Render video (course_video) → map path vào `upload_drafts_HELPER.py` → `VIDEO_PATHS`
3. Google Cloud OAuth Desktop client → `client_secret.json`
4. `pip install google-api-python-client google-auth-oauthlib`
5. `python upload_drafts_HELPER.py` → upload **private** (draft)

Generated: {_now()}
""",
        encoding="utf-8",
    )
    _log(f">> YouTube upload helper → {helper.name}", log)
    return ydir


def publish_all(root: Path, log: LogFn = print) -> dict:
    root = Path(root)
    paths = {
        "skool": str(publish_skool_tree(root, log=log)),
        "skool_clipboard": str(publish_skool_clipboard(root, log=log)),
        "youtube": str(publish_youtube_upload_helper(root, log=log)),
        "email": str(publish_email_nurture(root, log=log)),
        "leads": str(publish_lead_magnets(root, log=log)),
        "sales": str(publish_sales_pack(root, log=log)),
        "sales_html": str(publish_sales_html(root, log=log)),
        "zip": str(publish_zip(root, log=log)),
        "version": OPS.bump_version(root, note="publish_all"),
    }
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish packs for upgraded course")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--skool", action="store_true")
    ap.add_argument("--clipboard", action="store_true", help="Skool copy-paste HTML pack")
    ap.add_argument("--youtube", action="store_true")
    ap.add_argument("--email", action="store_true")
    ap.add_argument("--leads", action="store_true")
    ap.add_argument("--sales", action="store_true")
    ap.add_argument("--sales-html", action="store_true")
    ap.add_argument("--zip", action="store_true")
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    flags = [
        args.skool, args.clipboard, args.youtube, args.email,
        args.leads, args.sales, args.sales_html, args.zip,
    ]
    if args.all or not any(flags):
        print(json.dumps(publish_all(root), ensure_ascii=False, indent=2))
        return 0
    if args.skool:
        publish_skool_tree(root)
    if args.clipboard:
        publish_skool_clipboard(root)
    if args.youtube:
        publish_youtube_upload_helper(root)
    if args.email:
        publish_email_nurture(root)
    if args.leads:
        publish_lead_magnets(root)
    if args.sales:
        publish_sales_pack(root)
    if args.sales_html:
        publish_sales_html(root)
    if args.zip:
        publish_zip(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
