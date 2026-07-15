#!/usr/bin/env python3
"""
Thumbnail / cover pack — PNG cover cho mỗi bài (PIL).

  python course_thumbs.py --course X
  python course_thumbs.py --course X --limit 5 --locale es
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import config as C

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
OUT = "_thumbnails"

# palette variants
PALETTES = [
    ((15, 23, 42), (56, 189, 248), (248, 250, 252)),   # slate / sky
    ((30, 27, 75), (167, 139, 250), (245, 243, 255)),  # indigo / violet
    ((6, 78, 59), (52, 211, 153), (236, 253, 245)),    # emerald
    ((127, 29, 29), (251, 146, 60), (255, 247, 237)),  # red / orange
    ((22, 78, 99), (34, 211, 238), (236, 254, 255)),   # cyan
]


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _wrap(text: str, width: int = 28) -> List[str]:
    return textwrap.wrap(text or "", width=width) or [""]


def render_thumb(
    title: str,
    subtitle: str,
    out_path: Path,
    *,
    size: Tuple[int, int] = (1280, 720),
    palette_idx: int = 0,
) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    bg, accent, fg = PALETTES[palette_idx % len(PALETTES)]
    w, h = size
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    # accent bar
    draw.rectangle([0, 0, 24, h], fill=accent)
    draw.rectangle([0, h - 12, w, h], fill=accent)
    # decorative circle
    draw.ellipse([w - 280, -80, w + 80, 280], outline=accent, width=3)

    def font(sz: int):
        for name in (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "arial.ttf",
        ):
            try:
                return ImageFont.truetype(name, sz)
            except Exception:
                continue
        return ImageFont.load_default()

    f_title = font(54)
    f_sub = font(28)
    f_small = font(22)

    y = 160
    for line in _wrap(title, 26)[:4]:
        draw.text((80, y), line, fill=fg, font=f_title)
        y += 68
    y += 20
    if subtitle:
        draw.text((80, y), subtitle[:80], fill=accent, font=f_sub)
        y += 48
    draw.text((80, h - 70), "Course OS · Skool Downloader", fill=(148, 163, 184), font=f_small)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def find_lessons(root: Path, locale: Optional[str] = None) -> List[Path]:
    root = Path(root)
    if locale:
        base = root / UPGRADE / "locales" / locale
        if not base.is_dir():
            return []
        return sorted({p.parent for p in base.rglob("lesson.md")})
    base = root / UPGRADE
    if not base.is_dir():
        return []
    return sorted(
        {p.parent for p in base.rglob("lesson.md") if "locales" not in p.parts}
    )


def export_thumbs(
    root: Path,
    *,
    limit: int = 0,
    locale: Optional[str] = None,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    lessons = find_lessons(root, locale=locale)
    if limit > 0:
        lessons = lessons[:limit]
    if not lessons:
        raise FileNotFoundError("Không thấy lesson.md — chạy assets trước")

    brand = {}
    bp = root / "_brand_kit.json"
    if bp.exists():
        try:
            brand = json.loads(bp.read_text(encoding="utf-8"))
        except Exception:
            pass
    course_name = brand.get("name") or root.name
    out = root / OUT
    if locale:
        out = out / locale
    out.mkdir(parents=True, exist_ok=True)

    files = []
    for i, ldir in enumerate(lessons):
        title = ldir.name.split(" - ", 1)[-1]
        try:
            base = root / UPGRADE / ("locales" / Path(locale) if locale else Path("."))
            if locale:
                rel = ldir.relative_to(root / UPGRADE / "locales" / locale)
            else:
                rel = ldir.relative_to(root / UPGRADE)
        except ValueError:
            rel = Path(ldir.name)
        dest = out / rel
        dest.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w\-]+", "_", title)[:40] or f"lesson_{i}"
        png = dest / f"{safe}_thumb.png"
        sub = f"{course_name}" + (f" · {locale}" if locale else "")
        render_thumb(title, sub, png, palette_idx=i)
        # also copy into lesson folder for convenience
        try:
            import shutil

            shutil.copy2(png, ldir / "thumbnail.png")
        except Exception:
            pass
        files.append(str(png.relative_to(root)))
        _log(f"   thumb: {rel}", log)

    (out / "INDEX.md").write_text(
        f"# Thumbnails — {root.name}\n\nGenerated: {_now()}\n\n"
        + "\n".join(f"- `{f}`" for f in files)
        + "\n",
        encoding="utf-8",
    )
    _log(f">> Thumbnails: {len(files)} → {out}", log)
    return {"count": len(files), "dir": str(out), "files": files}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export lesson thumbnail PNGs")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--locale", default="")
    args = ap.parse_args(argv)
    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    print(
        json.dumps(
            export_thumbs(
                Path(C.ROOT),
                limit=args.limit,
                locale=(args.locale or None),
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        raise SystemExit(1)
