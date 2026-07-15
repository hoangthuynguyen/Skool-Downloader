#!/usr/bin/env python3
"""
Xuất PowerPoint (.pptx) từ slide_outline.md / lesson — pure OOXML zip (không cần python-pptx).

  python course_pptx.py --course X
  python course_pptx.py --course X --limit 3
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from xml.sax.saxutils import escape

import config as C

LogFn = Callable[[str], None]
UPGRADE = "_upgrade_v2"
OUT = "_pptx"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def outline_to_slide_texts(outline: str, title: str) -> List[Tuple[str, List[str]]]:
    """→ list of (heading, bullets)."""
    slides: List[Tuple[str, List[str]]] = [(title, [f"Course OS · {_now()}"])]
    text = outline or ""
    parts = re.split(r"(?m)^##\s+", text)
    if len(parts) <= 1:
        bullets = re.findall(r"(?m)^[\-\*]\s+(.+)$", text)
        if bullets:
            for i in range(0, len(bullets), 6):
                slides.append((title, bullets[i : i + 6]))
        elif text.strip():
            slides.append((title, [text.strip()[:400]]))
        return slides
    for block in parts[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        h = lines[0].strip()
        rest = "\n".join(lines[1:])
        bullets = re.findall(r"(?m)^[\-\*]\s+(.+)$", rest)
        if not bullets and rest.strip():
            bullets = [rest.strip()[:500]]
        slides.append((h, bullets[:12] or ["(empty)"]))
    return slides


def _a_para(text: str, size_hundredths: int = 2800, bold: bool = False) -> str:
    t = escape(text or "")
    b = '<a:rPr lang="en-US" sz="%d" b="1" dirty="0"/>' % size_hundredths if bold else (
        '<a:rPr lang="en-US" sz="%d" dirty="0"/>' % size_hundredths
    )
    return (
        f'<a:p><a:pPr marL="0" indent="0"><a:defRPr/></a:pPr>'
        f'<a:r>{b}<a:t>{t}</a:t></a:r></a:p>'
    )


def _slide_xml(heading: str, bullets: List[str]) -> str:
    paras = [_a_para(heading, 3600, bold=True)]
    for b in bullets:
        paras.append(_a_para(f"• {b}", 2200, bold=False))
    body = "".join(paras)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="0F172A"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>
        <a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Content"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="457200" y="457200"/><a:ext cx="8229600" cy="5715000"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square" rtlCol="0"/><a:lstStyle/>
          {body}
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"""


def _content_types(n_slides: int) -> str:
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for i in range(1, n_slides + 1):
        overrides.append(
            f'<Override PartName="/ppt/slides/slide{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(overrides)
        + "</Types>"
    )


def _presentation_xml(n_slides: int) -> str:
    sld_ids = "".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i}"/>' for i in range(1, n_slides + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 saveSubsetFonts="1">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId0"/></p:sldMasterIdLst>
  <p:sldIdLst>{sld_ids}</p:sldIdLst>
  <p:sldSz cx="9144000" cy="6858000"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>
"""


def _pres_rels(n_slides: int) -> str:
    rels = [
        '<Relationship Id="rId0" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    for i in range(1, n_slides + 1):
        rels.append(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        )
    rels.append(
        f'<Relationship Id="rId{n_slides + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )


THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="CourseOS">
  <a:themeElements>
    <a:clrScheme name="CourseOS">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="0F172A"/></a:dk2>
      <a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>
      <a:accent1><a:srgbClr val="38BDF8"/></a:accent1>
      <a:accent2><a:srgbClr val="818CF8"/></a:accent2>
      <a:accent3><a:srgbClr val="34D399"/></a:accent3>
      <a:accent4><a:srgbClr val="FBBF24"/></a:accent4>
      <a:accent5><a:srgbClr val="F472B6"/></a:accent5>
      <a:accent6><a:srgbClr val="A78BFA"/></a:accent6>
      <a:hlink><a:srgbClr val="38BDF8"/></a:hlink>
      <a:folHlink><a:srgbClr val="818CF8"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="CourseOS">
      <a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
      <a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="CourseOS">
      <a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
        <a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
        <a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>
"""

MASTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="0F172A"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2"
   accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>
"""

LAYOUT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr/>
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""


def write_pptx(path: Path, slides: List[Tuple[str, List[str]]], title: str = "Course"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = max(1, len(slides))
    core = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>Skool Downloader Course OS</dc:creator>
  <cp:lastModifiedBy>Course OS</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}</dcterms:modified>
</cp:coreProperties>
"""
    app = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <TotalTime>0</TotalTime><Words>0</Words><Application>SkoolDownloader</Application>
  <PresentationFormat>On-screen Show (4:3)</PresentationFormat>
  <Paragraphs>0</Paragraphs><Slides>{n}</Slides><Notes>0</Notes>
</Properties>
"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""
    master_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>
"""
    layout_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>
"""
    slide_rel = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _content_types(n))
        z.writestr("_rels/.rels", root_rels)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)
        z.writestr("ppt/presentation.xml", _presentation_xml(n))
        z.writestr("ppt/_rels/presentation.xml.rels", _pres_rels(n))
        z.writestr("ppt/theme/theme1.xml", THEME)
        z.writestr("ppt/slideMasters/slideMaster1.xml", MASTER)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", LAYOUT)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", layout_rels)
        for i, (h, bullets) in enumerate(slides, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", _slide_xml(h, bullets))
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rel)
    return path


def find_lessons(root: Path) -> List[Path]:
    dest = Path(root) / UPGRADE
    if not dest.is_dir():
        return []
    with_o = sorted(
        {p.parent for p in dest.rglob("slide_outline.md") if "locales" not in p.parts}
    )
    if with_o:
        return with_o
    return sorted(
        {p.parent for p in dest.rglob("lesson.md") if "locales" not in p.parts}
    )


def export_pptx_pack(root: Path, *, limit: int = 0, log: LogFn = print) -> dict:
    root = Path(root)
    lessons = find_lessons(root)
    if limit > 0:
        lessons = lessons[:limit]
    if not lessons:
        raise FileNotFoundError(f"Không thấy lesson trong {UPGRADE}/")
    out_root = root / OUT
    out_root.mkdir(parents=True, exist_ok=True)
    n = 0
    files = []
    for ldir in lessons:
        title = ldir.name.split(" - ", 1)[-1]
        outline = _read(ldir / "slide_outline.md")
        if not outline.strip():
            lesson = _read(ldir / "lesson.md")
            outline = "\n".join(
                ln
                for ln in lesson.splitlines()
                if ln.startswith("#") or ln.startswith("-")
            )[:4000]
        slides = outline_to_slide_texts(outline, title)
        try:
            rel = ldir.relative_to(root / UPGRADE)
        except ValueError:
            rel = Path(ldir.name)
        dest = out_root / rel
        dest.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w\-]+", "_", title)[:50] or "slides"
        pptx_path = dest / f"{safe}.pptx"
        write_pptx(pptx_path, slides, title=title)
        files.append(str(pptx_path.relative_to(root)))
        n += 1
        _log(f"   pptx: {rel} · {len(slides)} slides", log)
    (out_root / "INDEX.md").write_text(
        f"# PPTX pack — {root.name}\n\nGenerated: {_now()}\n\n"
        + "\n".join(f"- `{f}`" for f in files)
        + "\n",
        encoding="utf-8",
    )
    _log(f">> PPTX pack: {n} files → {out_root}", log)
    return {"decks": n, "dir": str(out_root), "files": files}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export PPTX decks (pure OOXML)")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    print(export_pptx_pack(Path(C.ROOT), limit=args.limit))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        raise SystemExit(1)
