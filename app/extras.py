"""
Luu toan bo noi dung bai hoc (khong chi video):

Moi folder bai:
  description.md   — mo ta / body bai (markdown)
  lesson.json      — metadata day du (title, video url, links, resources, ids)
  links.md         — tat ca link rut ra (Notion, Gemini, PDF URL, ...)
  resources/       — file tai ve (pdf, zip, anh...) + _links.txt

Chay sau folders.py (va sau dump meta_*.json).
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

import common as K
import config as C

# link trong mo ta / JSON
_URL_RE = re.compile(r"https?://[^\s\"'<>\]]+", re.I)
# bo query tracking dai / truncated markdown
_SKIP_HOST_FRAG = ("google.com/recaptcha", "facebook.com/tr", "doubleclick")


def score(nodes):
    sc = 0
    for n in nodes:
        if (n.get("desc_md") or "").strip():
            sc += 10
        sc += len(n.get("resources") or [])
        sc += len(n.get("links") or [])
        sc += score(n.get("children") or [])
    return sc


def _safe_name(name: str, default: str = "file") -> str:
    return K.san_file(name) or default


def extract_urls(*texts) -> list[str]:
    found = []
    seen = set()
    for t in texts:
        if not t:
            continue
        for m in _URL_RE.findall(str(t)):
            u = m.rstrip(").,;]}>\"'")
            # un-escape common JSON
            u = u.replace("\\u0026", "&").replace("\\/", "/")
            low = u.lower()
            if any(s in low for s in _SKIP_HOST_FRAG):
                continue
            if u not in seen:
                seen.add(u)
                found.append(u)
    return found


def parse_resources(raw) -> list[dict]:
    """resources co the la list hoac JSON string '[]' / '[{...}]'."""
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            raw = json.loads(s)
        except Exception:
            # plain URL list
            return [{"type": "link", "file_name": "link", "url": u} for u in extract_urls(s)]
    if not isinstance(raw, list):
        return []
    out = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        item = dict(r)
        # chuan hoa
        if not item.get("type"):
            if item.get("link") or (item.get("url") and not item.get("file_id")):
                item["type"] = "link"
                item.setdefault("url", item.get("link") or item.get("url"))
                item.setdefault("file_name", item.get("title") or "link")
            elif item.get("file_id") or item.get("file_name"):
                item["type"] = "file"
        if item.get("link") and not item.get("url"):
            item["url"] = item["link"]
        out.append(item)
    return out


def dl(url, target: Path, timeout=90):
    last = None
    for a in range(4):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r, open(target, "wb") as out:
                out.write(r.read())
            if target.stat().st_size > 0:
                return True
        except Exception as e:
            last = e
            try:
                if target.exists() and target.stat().st_size == 0:
                    target.unlink()
            except Exception:
                pass
            time.sleep(2 * (a + 1))
    if last:
        raise last
    return False


def _guess_filename(url: str, fallback: str) -> str:
    try:
        path = unquote(urlparse(url).path)
        name = Path(path).name
        if name and "." in name and len(name) < 180:
            return _safe_name(name)
    except Exception:
        pass
    return _safe_name(fallback)


def write_lesson_pack(folder: Path, node: dict, log=print) -> dict:
    """Ghi day du noi dung 1 bai vao folder. Tra ve stats dict."""
    stats = {
        "desc": 0, "lesson_json": 0, "links_md": 0,
        "file_dl": 0, "file_skip": 0, "file_fail": 0, "link_n": 0,
        "image_dl": 0,
    }
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    title = (node.get("title") or folder.name).strip()
    desc = (node.get("desc_md") or node.get("desc") or "").strip()
    resources = parse_resources(node.get("resources"))
    # links da rut san tu dump (neu co)
    extra_links = node.get("links") or []
    video_url = (node.get("url") or node.get("video_url") or "").strip()
    video_id = node.get("video_id") or node.get("videoId")

    # 1) description.md
    if desc:
        (folder / "description.md").write_text(desc, encoding="utf-8")
        stats["desc"] = 1
    elif not (folder / "description.md").exists():
        # placeholder de biet bai da xu ly
        (folder / "description.md").write_text(
            f"# {title}\n\n_(Khong co mo ta text tu Skool.)_\n",
            encoding="utf-8",
        )

    # 2) thu thap moi link
    all_urls = []
    all_urls.extend(extract_urls(desc, json.dumps(resources, ensure_ascii=False)))
    for u in extra_links:
        if isinstance(u, str):
            all_urls.extend(extract_urls(u))
        elif isinstance(u, dict) and u.get("url"):
            all_urls.append(u["url"])
    for r in resources:
        if r.get("url"):
            all_urls.append(r["url"])
        if r.get("link"):
            all_urls.append(r["link"])
    # unique keep order
    seen = set()
    uniq_urls = []
    for u in all_urls:
        if u and u not in seen:
            seen.add(u)
            uniq_urls.append(u)

    # phan loai: file truc tiep vs link
    file_exts = (
        ".pdf", ".zip", ".rar", ".7z", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".csv", ".txt", ".md", ".json", ".png", ".jpg",
        ".jpeg", ".gif", ".webp", ".mp3", ".wav", ".mp4", ".mov",
    )
    asset_hosts = ("assets.skool.com", "cdn.skool.com")

    link_lines = []
    if video_url:
        link_lines.append(f"- **Video:** {video_url}")
    for u in uniq_urls:
        low = u.lower()
        kind = "link"
        if any(low.split("?")[0].endswith(ext) for ext in file_exts):
            kind = "file"
        elif any(h in low for h in asset_hosts):
            kind = "image/asset"
        elif "notion.so" in low:
            kind = "notion"
        elif "drive.google" in low or "docs.google" in low:
            kind = "google"
        elif "youtube.com" in low or "youtu.be" in low:
            kind = "youtube"
        elif "loom.com" in low:
            kind = "loom"
        link_lines.append(f"- **{kind}:** {u}")
        stats["link_n"] += 1

    if link_lines:
        (folder / "links.md").write_text(
            f"# Links — {title}\n\n" + "\n".join(link_lines) + "\n",
            encoding="utf-8",
        )
        stats["links_md"] = 1

    # 3) resources/
    rdir = folder / "resources"
    need_rdir = bool(resources) or any(
        any(u.lower().split("?")[0].endswith(ext) for ext in file_exts)
        or any(h in u.lower() for h in asset_hosts)
        for u in uniq_urls
    )
    if need_rdir:
        rdir.mkdir(exist_ok=True)
        # _links.txt cho resource links
        only_links = [
            r for r in resources
            if (r.get("type") == "link") or (r.get("url") and not r.get("file_id"))
        ]
        if only_links or uniq_urls:
            lines = []
            for r in only_links:
                lines.append(f"- {r.get('file_name') or r.get('title') or 'link'}: {r.get('url') or r.get('link')}")
            for u in uniq_urls:
                if not any(u in (ln or "") for ln in lines):
                    lines.append(f"- link: {u}")
            (rdir / "_links.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

        # tai file co url truc tiep tu resources
        for r in resources:
            url = (r.get("url") or r.get("link") or "").strip()
            if not url:
                continue
            # link-only (notion/gemini) — khong tai
            if r.get("type") == "link" and not any(
                url.lower().split("?")[0].endswith(ext) for ext in file_exts
            ):
                continue
            if "notion.so" in url or "gemini.google" in url or "docs.google" in url:
                continue
            fname = _guess_filename(url, r.get("file_name") or r.get("title") or "file")
            tgt = rdir / fname
            if tgt.exists() and tgt.stat().st_size > 0:
                stats["file_skip"] += 1
                continue
            try:
                dl(url, tgt)
                stats["file_dl"] += 1
                log(f"   [file] {folder.name}/{tgt.name}")
            except Exception as e:
                stats["file_fail"] += 1
                log(f"   [LOI file] {fname}: {e}")

        # tai anh skool assets nho (thumbnail / illustration trong bai) — bo -md thumb
        for u in uniq_urls:
            low = u.lower()
            if not any(h in low for h in asset_hosts):
                continue
            if "-md." in low or "-sm." in low:
                continue
            if not any(low.split("?")[0].endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                continue
            fname = _guess_filename(u, "image.jpg")
            tgt = rdir / fname
            if tgt.exists() and tgt.stat().st_size > 0:
                stats["file_skip"] += 1
                continue
            try:
                dl(u, tgt)
                stats["image_dl"] += 1
            except Exception:
                stats["file_fail"] += 1

    # 4) lesson.json — toan bo metadata de dump/search sau
    lesson_doc = {
        "title": title,
        "folder": str(folder),
        "video_url": video_url or None,
        "video_id": video_id,
        "has_video": bool(video_url),
        "description_file": "description.md" if desc else None,
        "links_file": "links.md" if link_lines else None,
        "links": uniq_urls,
        "resources": resources,
        "raw": {
            k: node.get(k)
            for k in (
                "title", "url", "video_url", "video_id", "videoId",
                "desc_md", "resources", "links", "unit_type", "unitType",
                "hasAccess", "native", "host",
            )
            if node.get(k) is not None
        },
    }
    (folder / "lesson.json").write_text(
        json.dumps(lesson_doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    stats["lesson_json"] = 1
    return stats


def run(log=print):
    print("=== SAVE EXTRAS (mo ta + links + resources + lesson.json) ===")
    if C.DRY_RUN:
        print("DRY_RUN: bo qua extras\n")
        return
    chapters = K.load_best(C.META_PATTERN, score) or K.load_best(C.VID_PATTERN, score)
    if not chapters:
        print("Khong co meta_*.json / vid_*.json -> bo qua\n")
        return

    tot = {
        "desc": 0, "lesson_json": 0, "links_md": 0,
        "file_dl": 0, "file_skip": 0, "file_fail": 0, "link_n": 0,
        "image_dl": 0, "miss": 0, "lessons": 0,
    }
    for ct, f, course in chapters:
        chap = K.find_chapter_folder(ct)
        if chap is None:
            print(f"[!] khong khop folder '{ct}'\n")
            continue
        # merge vid url vao node neu meta thieu
        vid_map = {}
        try:
            for ct2, vf, vcourse in K.load_best(C.VID_PATTERN, lambda n: 1):
                if K.san(ct2) != K.san(ct):
                    continue
                for folder, node in K.walk(vcourse.get("children") or [], chap):
                    if node.get("url"):
                        vid_map[str(folder)] = node.get("url")
        except Exception:
            pass

        lessons = K.walk(course.get("children") or [], chap)
        print(f"[{chap.name}] {len(lessons)} bai")
        for folder, node in lessons:
            try:
                if not folder.exists():
                    folder.mkdir(parents=True, exist_ok=True)
                # bo sung url tu vid dump
                if not (node.get("url") or "").strip():
                    u = vid_map.get(str(folder))
                    if u:
                        node = dict(node)
                        node["url"] = u
                st = write_lesson_pack(folder, node, log=print)
                for k, v in st.items():
                    tot[k] = tot.get(k, 0) + v
                tot["lessons"] += 1
            except Exception as e:
                tot["file_fail"] += 1
                print(f"   [BO QUA] {folder.name}: {e}")
        print()

    print(
        f"--- EXTRAS: lessons={tot['lessons']} desc={tot['desc']} "
        f"lesson.json={tot['lesson_json']} links.md={tot['links_md']} "
        f"file_dl={tot['file_dl']} img={tot['image_dl']} skip={tot['file_skip']} "
        f"fail={tot['file_fail']} urls={tot['link_n']} ---\n"
    )
    if tot["file_fail"]:
        print("Mot so file loi (link het han 8h?) — dump lai meta roi chay extras.\n")


if __name__ == "__main__":
    run()
