#!/usr/bin/env python3
"""
Nâng cấp / làm mới khóa học đã tải → phiên bản cập nhật đến HÔM NAY.

Luồng:
  0) (Mặc định BẬT) Questionnaire — user trả lời mong muốn cập nhật
  1) Phân tích khóa local (cấu trúc, chủ đề, phần mềm được nhắc)
  2) (Tuỳ chọn) Nghiên cứu thị trường / tính năng mới nhất (LLM + gợi ý web)
  3) Xuất report DOCX + MD toàn diện (_Upgrade_Research_Report.*)
  4) Người dùng có thể bổ sung ghi chú vào _Upgrade_User_Notes.md
  5) LLM (chính + fallback) sinh cấu trúc khóa MỚI (loại bài cũ lỗi thời)
  6) (Tuỳ chọn) Sinh outline nội dung từng bài mới

CLI:
  python course_upgrade.py --course "TenKhoa" --research
  python course_upgrade.py --course "X" --research --no-web
  python course_upgrade.py --course "X" --no-questionnaire
  python course_upgrade.py --course "X" --answers-file path.json
  python course_upgrade.py --course "X" --structure-only   # đã có report, chỉ sinh structure
  python course_upgrade.py --course "X" --generate-lessons # sinh outline bài từ structure
  python course_upgrade.py --course "X" --full             # research + structure + lessons
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import config as C

# ---- file names under course root ----
INVENTORY_JSON = "_upgrade_inventory.json"
RESEARCH_JSON = "_upgrade_research.json"
REPORT_MD = "_Upgrade_Research_Report.md"
REPORT_DOCX = "_Upgrade_Research_Report.docx"
USER_NOTES = "_Upgrade_User_Notes.md"
ANSWERS_JSON = "_upgrade_questionnaire.json"
ANSWERS_MD = "_Upgrade_Questionnaire.md"
STRUCTURE_JSON = "_upgrade_new_structure.json"
STRUCTURE_MD = "_Upgrade_New_Structure.md"
UPGRADE_DIR = "_upgrade_v2"  # scaffold khóa mới

# Câu hỏi gợi ý trước khi research / sinh cấu trúc (id ổn định)
UPGRADE_QUESTIONS: List[Dict[str, str]] = [
    {
        "id": "learner",
        "q": "Đối tượng học mục tiêu của phiên bản mới là ai? (ví dụ: founder 1 người, agency, giáo viên…)",
    },
    {
        "id": "outcomes",
        "q": "Sau khóa mới, học viên phải LÀM ĐƯỢC gì cụ thể? (3–7 outcomes)",
    },
    {
        "id": "must_keep",
        "q": "Chủ đề / bài nào trong khóa CŨ bắt buộc GIỮ (dù chỉnh nhẹ)?",
    },
    {
        "id": "must_drop",
        "q": "Chủ đề / tool / bài nào chắc chắn muốn LOẠI (lỗi thời, không còn dùng)?",
    },
    {
        "id": "tools_priority",
        "q": "Phần mềm / stack ưu tiên cho bản mới? (vd: Claude + n8n + Make; bỏ Zapier cũ…)",
    },
    {
        "id": "new_features",
        "q": "Tính năng / xu hướng mới cần đưa vào (AI agent, MCP, ads 2026, v.v.)?",
    },
    {
        "id": "depth",
        "q": "Độ sâu mong muốn? (overview nhanh / hands-on chi tiết / production-ready)",
    },
    {
        "id": "duration",
        "q": "Độ dài khóa mục tiêu? (số chương, số bài, hoặc số giờ học ước lượng)",
    },
    {
        "id": "format",
        "q": "Định dạng ưu tiên? (video ngắn + checklist / project cuối khóa / template tải về…)",
    },
    {
        "id": "constraints",
        "q": "Ràng buộc đặc biệt? (ngân sách tool, không code, thị trường VN/EN, tuân thủ…)",
    },
    {
        "id": "extra",
        "q": "Thông tin / mong muốn khác bạn muốn AI tính đến khi thiết kế cấu trúc mới?",
    },
]

# software / tool patterns (mở rộng dần)
SOFT_PATTERNS = [
    r"\b(?:Claude|ChatGPT|GPT-?[45o]|Gemini|Grok|Copilot|Cursor|Windsurf)\b",
    r"\b(?:OpenAI|Anthropic|xAI|DeepSeek|Qwen|Llama|Mistral)\b",
    r"\b(?:Make\.com|Zapier|n8n|Airtable|Notion|ClickUp|Asana|Trello)\b",
    r"\b(?:Shopify|Stripe|HubSpot|Mailchimp|Klaviyo|GoHighLevel|GHL)\b",
    r"\b(?:Figma|Canva|Midjourney|Runway|ElevenLabs|Descript)\b",
    r"\b(?:Python|JavaScript|TypeScript|Node\.?js|React|Next\.?js)\b",
    r"\b(?:AWS|GCP|Azure|Vercel|Supabase|Firebase|Docker)\b",
    r"\b(?:Excel|Google Sheets|Power BI|Tableau)\b",
    r"\b(?:Instagram|TikTok|YouTube|LinkedIn|Facebook|Meta Ads|Google Ads)\b",
    r"\b(?:Whisper|LangChain|LlamaIndex|RAG|MCP|Agent)\b",
    r"\b(?:Skool|Discord|Circle|Mighty Networks)\b",
]

TOPIC_STOP = {
    "the", "and", "for", "with", "this", "that", "from", "your", "you", "are",
    "how", "what", "when", "will", "can", "lesson", "video", "chapter", "day",
    "step", "intro", "introduction", "welcome", "overview", "part", "module",
}


LogFn = Callable[[str], None]


def _log(msg: str, log: LogFn = print):
    log(msg)


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ----------------------------- questionnaire -----------------------------
def questionnaire_enabled() -> bool:
    try:
        if hasattr(C, "get_course_upgrade_questionnaire"):
            return bool(C.get_course_upgrade_questionnaire())
    except Exception:
        pass
    return bool(getattr(C, "COURSE_UPGRADE_QUESTIONNAIRE", True))


def get_questions() -> List[Dict[str, str]]:
    return [dict(q) for q in UPGRADE_QUESTIONS]


def load_answers(root: Path) -> dict:
    root = Path(root)
    p = root / ANSWERS_JSON
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_answers(root: Path, answers: dict, log: LogFn = print) -> dict:
    """
    answers: {question_id: answer_text} hoặc list [{id,q,a},...]
    Ghi JSON + MD; đồng thời merge vào USER_NOTES.
    """
    root = Path(root)
    # normalize
    by_id: Dict[str, str] = {}
    if isinstance(answers, dict) and "answers" in answers:
        raw = answers.get("answers")
        if isinstance(raw, dict):
            by_id = {str(k): str(v or "").strip() for k, v in raw.items()}
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("id"):
                    by_id[str(item["id"])] = str(item.get("a") or item.get("answer") or "").strip()
    elif isinstance(answers, dict):
        # flat id->text (skip meta keys)
        meta = {"as_of", "course", "generated_at", "enabled", "questions"}
        for k, v in answers.items():
            if k in meta:
                continue
            if isinstance(v, str):
                by_id[str(k)] = v.strip()
            elif isinstance(v, dict) and ("a" in v or "answer" in v):
                by_id[str(k)] = str(v.get("a") or v.get("answer") or "").strip()

    qmap = {q["id"]: q["q"] for q in UPGRADE_QUESTIONS}
    items = []
    for q in UPGRADE_QUESTIONS:
        qid = q["id"]
        items.append({"id": qid, "q": q["q"], "a": by_id.get(qid, "")})
    # extra free keys not in catalog
    for qid, a in by_id.items():
        if qid not in qmap:
            items.append({"id": qid, "q": qid, "a": a})

    payload = {
        "as_of": _today(),
        "course": getattr(C, "COURSE", None) or root.name,
        "generated_at": _now(),
        "enabled": True,
        "answers": {it["id"]: it["a"] for it in items},
        "items": items,
    }
    _write(root / ANSWERS_JSON, json.dumps(payload, ensure_ascii=False, indent=2))

    md_lines = [
        f"# Questionnaire nâng cấp khóa — {payload['course']}",
        f"",
        f"- as_of: {payload['as_of']}",
        f"- sinh: {payload['generated_at']}",
        f"",
        f"## Câu trả lời người dùng",
        f"",
    ]
    for it in items:
        md_lines.append(f"### {it['id']}. {it['q']}")
        md_lines.append("")
        md_lines.append(it["a"] if it["a"] else "_(chưa trả lời)_")
        md_lines.append("")
    _write(root / ANSWERS_MD, "\n".join(md_lines))

    # merge vào user notes
    notes_path = root / USER_NOTES
    block = format_answers_for_prompt(payload)
    existing = _read(notes_path)
    marker = "## Questionnaire (tự động)"
    if marker in existing:
        # replace block
        pre, _, rest = existing.partition(marker)
        # drop old questionnaire section until next ## at start or EOF
        rest2 = re.sub(
            r"^## Questionnaire \(tự động\)[\s\S]*?(?=^## |\Z)",
            "",
            marker + rest,
            flags=re.M,
        )
        existing = pre.rstrip() + "\n\n"
    if not existing.strip():
        existing = (
            f"# Ghi chú bổ sung cho nâng cấp khóa «{payload['course']}»\n\n"
            f"(Ngày {_today()})\n\n"
        )
    _write(
        notes_path,
        existing.rstrip()
        + f"\n\n{marker}\n\n"
        + block
        + "\n",
    )
    _log(f">> Questionnaire → {ANSWERS_JSON} + {ANSWERS_MD} + merge {USER_NOTES}", log)
    return payload


def format_answers_for_prompt(answers_payload: Optional[dict] = None, root: Optional[Path] = None) -> str:
    """Chuỗi đưa vào LLM research / structure."""
    data = answers_payload
    if data is None and root is not None:
        data = load_answers(root)
    if not data:
        return "(không có questionnaire)"
    items = data.get("items")
    if not items and isinstance(data.get("answers"), dict):
        qmap = {q["id"]: q["q"] for q in UPGRADE_QUESTIONS}
        items = [
            {"id": k, "q": qmap.get(k, k), "a": v}
            for k, v in data["answers"].items()
        ]
    lines = []
    for it in items or []:
        a = (it.get("a") or "").strip()
        if not a:
            continue
        lines.append(f"**{it.get('id')}: {it.get('q')}**\n{a}")
    return "\n\n".join(lines) if lines else "(đã bật questionnaire nhưng chưa có câu trả lời)"


def interactive_cli_questionnaire(root: Path, log: LogFn = print) -> dict:
    """Hỏi trên terminal (khi không dùng GUI)."""
    _log("=== QUESTIONNAIRE nâng cấp khóa (Enter = bỏ qua câu) ===", log)
    answers = {}
    for q in UPGRADE_QUESTIONS:
        try:
            print(f"\n[{q['id']}] {q['q']}")
            ans = input("→ ").strip()
        except EOFError:
            ans = ""
        answers[q["id"]] = ans
    return save_answers(root, answers, log=log)


# ----------------------------- inventory -----------------------------
def extract_software(text: str) -> List[str]:
    found = set()
    for pat in SOFT_PATTERNS:
        for m in re.finditer(pat, text or "", flags=re.I):
            found.add(m.group(0).strip())
    return sorted(found, key=str.lower)


def extract_keywords(text: str, top_n: int = 40) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}", text or "")
    c = Counter(w for w in words if w.lower() not in TOPIC_STOP and not w.isdigit())
    return [w for w, _ in c.most_common(top_n)]


def build_inventory(root: Path, log: LogFn = print) -> dict:
    import export as E

    root = Path(root)
    blocks = E.lesson_blocks(root)
    lessons = []
    all_text = []
    soft_counter: Counter = Counter()

    for b in blocks:
        if b["kind"] != "lesson":
            continue
        path = Path(b["path"])
        try:
            rel = str(path.relative_to(root))
        except Exception:
            rel = path.name
        desc = b.get("desc") or ""
        tr = b.get("transcript") or ""
        body = f"{b.get('title','')}\n{desc}\n{tr}"
        softs = extract_software(body)
        for s in softs:
            soft_counter[s] += 1
        all_text.append(body[:8000])
        lessons.append(
            {
                "title": b.get("title") or path.name,
                "path": rel,
                "has_desc": bool(desc.strip()),
                "has_transcript": bool(tr.strip()),
                "chars": len(desc) + len(tr),
                "software": softs,
                "summary_snip": (desc or tr)[:280].replace("\n", " "),
            }
        )

    sections = [
        {"title": b.get("title"), "path": str(Path(b["path"]).relative_to(root)) if b.get("path") else ""}
        for b in blocks
        if b["kind"] == "section"
    ]

    blob = "\n".join(all_text)
    inv = {
        "course": getattr(C, "COURSE", None) or root.name,
        "root": str(root),
        "as_of": _today(),
        "generated_at": _now(),
        "stats": {
            "lessons": len(lessons),
            "sections": len(sections),
            "with_transcript": sum(1 for x in lessons if x["has_transcript"]),
            "with_desc": sum(1 for x in lessons if x["has_desc"]),
        },
        "software_mentioned": [
            {"name": n, "mentions": c} for n, c in soft_counter.most_common(50)
        ],
        "keywords": extract_keywords(blob, 50),
        "sections": sections,
        "lessons": lessons,
    }
    out = root / INVENTORY_JSON
    _write(out, json.dumps(inv, ensure_ascii=False, indent=2))
    _log(f">> Inventory: {len(lessons)} bài, {len(soft_counter)} phần mềm/công cụ → {out.name}", log)
    return inv


# ----------------------------- research -----------------------------
# Known official docs / changelog hubs (best-effort; not exhaustive)
OFFICIAL_DOCS: Dict[str, List[str]] = {
    "openai": ["https://platform.openai.com/docs", "https://openai.com/index/"],
    "chatgpt": ["https://help.openai.com/en/", "https://platform.openai.com/docs"],
    "anthropic": ["https://docs.anthropic.com/", "https://www.anthropic.com/news"],
    "claude": ["https://docs.anthropic.com/", "https://www.anthropic.com/news"],
    "gemini": ["https://ai.google.dev/gemini-api/docs", "https://developers.googleblog.com/"],
    "google": ["https://ai.google.dev/docs"],
    "deepseek": ["https://api-docs.deepseek.com/"],
    "midjourney": ["https://docs.midjourney.com/"],
    "stable diffusion": ["https://stability.ai/news", "https://platform.stability.ai/docs"],
    "runway": ["https://docs.dev.runwayml.com/", "https://runwayml.com/changelog"],
    "heygen": ["https://docs.heygen.com/"],
    "elevenlabs": ["https://elevenlabs.io/docs"],
    "synthesia": ["https://docs.synthesia.io/"],
    "notion": ["https://www.notion.so/help", "https://developers.notion.com/"],
    "zapier": ["https://help.zapier.com/", "https://zapier.com/blog/"],
    "make": ["https://www.make.com/en/help"],
    "n8n": ["https://docs.n8n.io/"],
    "airtable": ["https://support.airtable.com/"],
    "figma": ["https://help.figma.com/", "https://www.figma.com/release-notes/"],
    "canva": ["https://www.canva.com/help/"],
    "shopify": ["https://help.shopify.com/", "https://shopify.dev/docs"],
    "stripe": ["https://docs.stripe.com/", "https://stripe.com/blog"],
    "hubspot": ["https://developers.hubspot.com/docs", "https://knowledge.hubspot.com/"],
    "wordpress": ["https://wordpress.org/documentation/"],
    "webflow": ["https://university.webflow.com/", "https://developers.webflow.com/"],
    "framer": ["https://www.framer.com/developers/", "https://www.framer.com/help/"],
    "bubble": ["https://manual.bubble.io/"],
    "replit": ["https://docs.replit.com/"],
    "cursor": ["https://docs.cursor.com/"],
    "github copilot": ["https://docs.github.com/en/copilot"],
    "langchain": ["https://python.langchain.com/docs/"],
    "llamaindex": ["https://docs.llamaindex.ai/"],
    "pinecone": ["https://docs.pinecone.io/"],
    "supabase": ["https://supabase.com/docs"],
    "firebase": ["https://firebase.google.com/docs"],
    "aws": ["https://docs.aws.amazon.com/"],
    "azure": ["https://learn.microsoft.com/azure/"],
    "vercel": ["https://vercel.com/docs"],
    "next.js": ["https://nextjs.org/docs"],
    "react": ["https://react.dev/blog"],
    "python": ["https://docs.python.org/3/whatsnew/"],
    "ffmpeg": ["https://ffmpeg.org/documentation.html"],
    "obs": ["https://obsproject.com/kb/"],
    "descript": ["https://help.descript.com/"],
    "capcut": ["https://www.capcut.com/resource"],
}


def _simple_web_snippets(query: str, max_results: int = 5) -> List[dict]:
    """
    Tra cứu nhẹ (DuckDuckGo HTML) — best-effort, không phụ thuộc API key.
    Trả list {title, url, snippet}. Fail → [].
    """
    results = []
    try:
        q = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        req = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            },
        )
        with urlopen(req, timeout=18) as r:
            html = r.read().decode("utf-8", errors="replace")
        # crude parse
        for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
            html,
            flags=re.I | re.S,
        ):
            href, title, snip = m.group(1), m.group(2), m.group(3)
            title = re.sub(r"<[^>]+>", "", title).strip()
            snip = re.sub(r"<[^>]+>", "", snip).strip()
            if title:
                results.append({"title": title[:200], "url": href[:300], "snippet": snip[:400]})
            if len(results) >= max_results:
                break
        if not results:
            # alternate pattern
            for m in re.finditer(r'result__a.*?href="([^"]+)".*?>(.*?)</a>', html, re.I | re.S):
                href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if title:
                    results.append({"title": title[:200], "url": href[:300], "snippet": ""})
                if len(results) >= max_results:
                    break
    except Exception:
        return []
    return results


def _html_to_text(html: str, max_chars: int = 3500) -> str:
    """Strip tags/scripts roughly for LLM context."""
    if not html:
        return ""
    t = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"(?is)<!--.*?-->", " ", t)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</p>", "\n", t)
    t = re.sub(r"(?i)</h[1-6]>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;", " ", t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"&lt;", "<", t)
    t = re.sub(r"&gt;", ">", t)
    t = re.sub(r"&#\d+;", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()[:max_chars]


def _fetch_page_text(url: str, timeout: int = 16) -> str:
    try:
        req = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SkoolDownloader/2.24",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urlopen(req, timeout=timeout) as r:
            raw = r.read()
            # skip huge binaries
            if len(raw) > 2_500_000:
                return ""
            html = raw.decode("utf-8", errors="replace")
        return _html_to_text(html)
    except Exception:
        return ""


def resolve_docs_urls(tool_name: str) -> List[str]:
    """Map tool name → known official docs URLs."""
    key = (tool_name or "").strip().lower()
    if not key:
        return []
    if key in OFFICIAL_DOCS:
        return list(OFFICIAL_DOCS[key])
    # partial match
    for k, urls in OFFICIAL_DOCS.items():
        if k in key or key in k:
            return list(urls)
    return []


def crawl_official_docs(
    software: List[str],
    *,
    max_tools: int = 8,
    max_pages_per_tool: int = 2,
    log: LogFn = print,
) -> Dict[str, List[dict]]:
    """
    Crawl official docs / changelog pages for tools mentioned in the course.
    Falls back to DuckDuckGo site:docs / changelog queries when no map entry.
    Returns {tool: [{url, title, excerpt}]}.
    """
    out: Dict[str, List[dict]] = {}
    year = date.today().year
    for name in (software or [])[:max_tools]:
        pages: List[dict] = []
        urls = resolve_docs_urls(name)
        if not urls:
            # discover via web
            for q in (
                f"{name} official documentation site:docs",
                f"{name} changelog {year}",
                f"{name} release notes {year}",
            ):
                hits = _simple_web_snippets(q, max_results=2)
                for h in hits:
                    u = h.get("url") or ""
                    if u and u not in {p.get("url") for p in pages}:
                        pages.append(
                            {
                                "url": u,
                                "title": h.get("title") or name,
                                "excerpt": (h.get("snippet") or "")[:500],
                                "source": "ddg",
                            }
                        )
                if len(pages) >= max_pages_per_tool:
                    break
                time.sleep(0.25)
        # fetch full text for known + discovered URLs
        fetch_urls = urls[:max_pages_per_tool] if urls else [
            p["url"] for p in pages[:max_pages_per_tool]
        ]
        fetched: List[dict] = []
        for u in fetch_urls:
            _log(f"   docs crawl «{name}»: {u[:70]}…", log)
            text = _fetch_page_text(u)
            title = name
            if text:
                # first non-empty line as title-ish
                for line in text.splitlines():
                    if len(line.strip()) > 8:
                        title = line.strip()[:120]
                        break
                fetched.append(
                    {
                        "url": u,
                        "title": title,
                        "excerpt": text[:3200],
                        "source": "official_docs",
                    }
                )
            else:
                # keep ddg snippet if any
                for p in pages:
                    if p.get("url") == u:
                        fetched.append(p)
                        break
                else:
                    fetched.append(
                        {
                            "url": u,
                            "title": name,
                            "excerpt": "",
                            "source": "official_docs_failed",
                        }
                    )
            time.sleep(0.3)
        if not fetched and pages:
            fetched = pages[:max_pages_per_tool]
        out[name] = fetched
        _log(f"   docs «{name}»: {len(fetched)} pages", log)
    return out


def _llm(
    system: str,
    user: str,
    log: LogFn = print,
    max_tokens: int = 8000,
    task: str = "research",
) -> str:
    """Gọi LLM theo task routing (Dashboard: research/structure/summary/assets/…)."""
    import llm_providers as PROV

    # budget gate (best-effort, per course ROOT)
    try:
        import course_ops as OPS

        chars = len(system or "") + len(user or "") + int(max_tokens or 0) * 2
        root = Path(getattr(C, "ROOT", ".") or ".")
        if root.is_dir() and not OPS.budget_charge(root, chars, model=task, log=log):
            raise RuntimeError(
                f"Vượt LLM budget cho khóa {root.name}. "
                f"Tăng cap: python course_ops.py --course … --budget-cap 50"
            )
    except RuntimeError:
        raise
    except Exception:
        pass

    if hasattr(PROV, "complete_for_task"):
        text, used = PROV.complete_for_task(
            task, system, user, max_tokens=max_tokens, log=log
        )
        _log(f"   [llm task={task} via {used}]", log)
        return text or ""

    # fallback cũ
    llm_cfg = {}
    try:
        if hasattr(C, "get_lesson_summary_llm"):
            llm_cfg = C.get_lesson_summary_llm() or {}
    except Exception:
        pass
    provider = llm_cfg.get("provider") or "deepseek"
    model = llm_cfg.get("model") or "deepseek-chat"
    text, used = PROV.complete_with_fallback(
        system, user, provider=provider, fallback=True, model=model, max_tokens=max_tokens, log=log
    )
    _log(f"   [llm via {used}]", log)
    return text or ""


def research_market(
    inv: dict,
    *,
    do_web: bool = True,
    user_answers: Optional[dict] = None,
    root: Optional[Path] = None,
    log: LogFn = print,
) -> dict:
    """
    Nghiên cứu: web snippets (tuỳ chọn) + LLM tổng hợp cập nhật đến as_of.
    Ưu tiên mong muốn user từ questionnaire.
    """
    as_of = inv.get("as_of") or _today()
    software = [x["name"] for x in inv.get("software_mentioned") or []][:20]
    keywords = inv.get("keywords") or []
    course = inv.get("course") or "Course"
    lessons = inv.get("lessons") or []
    qa_text = format_answers_for_prompt(user_answers, root=root)

    web_hits: Dict[str, List[dict]] = {}
    docs_hits: Dict[str, List[dict]] = {}
    if do_web and software:
        _log(f">> Web research ({len(software)} tools)…", log)
        for name in software[:12]:
            q = f"{name} new features {date.today().year} changelog updates"
            hits = _simple_web_snippets(q, max_results=4)
            web_hits[name] = hits
            _log(f"   web «{name}»: {len(hits)} hits", log)
            time.sleep(0.35)
        _log(f">> Official docs crawl (top tools)…", log)
        try:
            docs_hits = crawl_official_docs(software, max_tools=8, max_pages_per_tool=2, log=log)
        except Exception as e:
            _log(f"   [docs crawl skip] {e}", log)
            docs_hits = {}

    # sample lesson titles for context
    titles = [L["title"] for L in lessons[:80]]
    web_blob = json.dumps(web_hits, ensure_ascii=False, indent=2)[:12000]
    # docs excerpts can be large — keep compact
    docs_compact: Dict[str, List[dict]] = {}
    for k, pages in (docs_hits or {}).items():
        docs_compact[k] = [
            {
                "url": p.get("url"),
                "title": (p.get("title") or "")[:120],
                "excerpt": (p.get("excerpt") or "")[:1800],
                "source": p.get("source"),
            }
            for p in (pages or [])[:2]
        ]
    docs_blob = json.dumps(docs_compact, ensure_ascii=False, indent=2)[:16000]

    system = f"""Bạn là chuyên gia thiết kế khóa học & nghiên cứu thị trường công nghệ.
Hôm nay là {as_of}. Mọi đánh giá phải hướng tới kiến thức / tính năng **còn đúng và hữu dụng tại thời điểm này**.
Viết bằng TIẾNG VIỆT, Markdown rõ ràng, trung thực:
- **Ưu tiên câu trả lời / mong muốn của người dùng** (questionnaire) khi mâu thuẫn với khóa cũ.
- Ưu tiên **official docs / changelog** hơn web snippets chung (nếu có).
- Ghi rõ khi thông tin dựa trên suy luận chung vs tín hiệu web/docs (có thể thiếu).
- Không bịa URL; nếu không chắc, nói "cần xác minh".
- Ưu tiên loại bỏ nội dung lỗi thời, trùng lặp, đã bị thay bằng workflow/tool mới."""

    user = f"""# Nhiệm vụ
Phân tích khóa học đã tải «{course}» và lập **báo cáo nghiên cứu cập nhật** đến {as_of}.

## Mong muốn người dùng (questionnaire — ƯU TIÊN CAO)
{qa_text}

## Thống kê khóa gốc
- Số bài: {inv.get('stats',{}).get('lessons')}
- Có transcript: {inv.get('stats',{}).get('with_transcript')}
- Phần mềm/công cụ được nhắc nhiều: {', '.join(software) or '(ít nhận diện được)'}
- Keywords: {', '.join(keywords[:30])}

## Danh sách bài (mẫu, tối đa 80)
{chr(10).join(f'- {t}' for t in titles)}

## Official docs / changelog excerpts (ƯU TIÊN — nếu có)
```json
{docs_blob}
```

## Web snippets (tham khảo phụ, có thể nhiễu)
```json
{web_blob}
```

## Yêu cầu báo cáo (Markdown, đúng thứ tự heading)

# Báo cáo nghiên cứu cập nhật khóa học — {course}
## 1. Tóm tắt điều hành
## 2. Bối cảnh & mục tiêu người học hiện tại ({as_of})
## 2b. Tóm tắt yêu cầu từ questionnaire (user)
## 3. Bản đồ phần mềm / công cụ trong khóa
### 3.1 Còn phù hợp
### 3.2 Đã lỗi thời / nên thay
### 3.3 Cần bổ sung (xu hướng mới)
## 4. Tính năng mới nhất / thay đổi quan trọng (theo từng tool chính — cite docs URL nếu có)
## 5. Khoảng trống kiến thức so với thị trường hiện tại
## 6. Bài học cũ NÊN LOẠI BỎ (liệt kê rõ lý do)
## 7. Bài / chủ đề NÊN GIỮ (cập nhật nhẹ)
## 8. Bài / chủ đề NÊN THÊM MỚI
## 9. Đề xuất cấu trúc khóa phiên bản mới (outline chương → bài)
## 10. Rủi ro, giả định & việc cần xác minh thêm
## 11. Checklist triển khai nâng cấp

Ghi chú: Mục 6–9 là quan trọng nhất cho bước sinh cấu trúc LLM sau này.
"""

    _log(">> LLM tổng hợp báo cáo nghiên cứu…", log)
    report_md = _llm(system, user, log=log, max_tokens=10000, task="research")

    research = {
        "as_of": as_of,
        "course": course,
        "web_enabled": do_web,
        "software": software,
        "web_hits": web_hits,
        "docs_hits": docs_compact,
        "questionnaire": qa_text[:2000],
        "report_md": report_md,
        "generated_at": _now(),
    }
    return research


# ----------------------------- reports -----------------------------
def write_reports(root: Path, inv: dict, research: dict, log: LogFn = print) -> dict:
    root = Path(root)
    as_of = research.get("as_of") or _today()
    course = inv.get("course") or root.name
    body = research.get("report_md") or ""

    header = (
        f"# Báo cáo nghiên cứu cập nhật khóa học\n\n"
        f"- **Khóa gốc:** {course}\n"
        f"- **Cập nhật đến:** {as_of}\n"
        f"- **Sinh lúc:** {research.get('generated_at') or _now()}\n"
        f"- **Bài gốc:** {inv.get('stats',{}).get('lessons')}\n"
        f"- **Web research:** {'bật' if research.get('web_enabled') else 'tắt'}\n"
        f"- **Phần mềm chính:** {', '.join(research.get('software') or [])}\n\n"
        f"> Người dùng có thể bổ sung ý kiến vào file `{USER_NOTES}` rồi chạy lại "
        f"`--structure-only` để sinh cấu trúc khóa mới.\n\n---\n\n"
    )
    md_path = root / REPORT_MD
    _write(md_path, header + body)
    _log(f">> Report MD → {md_path.name}", log)

    # user notes stub
    notes = root / USER_NOTES
    if not notes.exists():
        _write(
            notes,
            f"# Ghi chú bổ sung cho nâng cấp khóa «{course}»\n\n"
            f"(Ngày {_today()}) Viết thêm yêu cầu, case study, tool bắt buộc, "
            f"đối tượng học… vào đây trước khi sinh cấu trúc khóa mới.\n\n"
            f"## Ý muốn thêm\n\n- \n\n## Nội dung bắt buộc giữ\n\n- \n\n"
            f"## Nội dung bắt buộc loại\n\n- \n",
        )

    docx_path = root / REPORT_DOCX
    try:
        import report_docx as RD

        title_lines = [
            ("Skool Downloader — Course Upgrade Research", 13, True),
            (f"Báo cáo cập nhật: {course}", 28, True),
            (f"Cập nhật đến {as_of} · sinh {_now()}", 13, False),
            ("Nghiên cứu thị trường + đề xuất cấu trúc khóa mới", 10, False),
        ]
        RD.build(docx_path, title_lines, body, toc=True)
        _log(f">> Report DOCX → {docx_path.name}", log)
    except Exception as e:
        docx_path = None
        _log(f"[docx] bỏ qua ({e}) — vẫn có bản .md", log)

    (root / RESEARCH_JSON).write_text(
        json.dumps(
            {
                "as_of": as_of,
                "course": course,
                "web_enabled": research.get("web_enabled"),
                "software": research.get("software"),
                "web_hits": research.get("web_hits"),
                "generated_at": research.get("generated_at"),
                "report_md_file": REPORT_MD,
                "report_docx_file": REPORT_DOCX if docx_path else None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"md": str(md_path), "docx": str(docx_path) if docx_path else None, "notes": str(notes)}


# ----------------------------- new structure -----------------------------
def structure_from_dump(root: Path, log: LogFn = print) -> dict:
    """
    Offline structure: map chapter folders + lessons từ dump local (không LLM).
    Dùng khi chưa có research report / chưa có API key.
    """
    root = Path(root)
    inv = {}
    ip = root / INVENTORY_JSON
    if ip.exists():
        try:
            inv = json.loads(ip.read_text(encoding="utf-8"))
        except Exception:
            inv = {}
    if not inv.get("lessons"):
        inv = build_inventory(root, log=log)

    # group lessons by top-level chapter folder
    chapters_map: Dict[str, List[dict]] = {}
    for L in inv.get("lessons") or []:
        rel = (L.get("path") or "").replace("\\", "/")
        parts = [p for p in rel.split("/") if p]
        if len(parts) >= 2:
            ch_name = parts[0]
            title = L.get("title") or parts[-1]
        else:
            ch_name = "General"
            title = L.get("title") or rel or "Lesson"
        chapters_map.setdefault(ch_name, []).append(
            {
                "title": re.sub(r"^\d+\s*-\s*", "", title).strip() or title,
                "path": rel,
                "software": L.get("software") or [],
                "purpose": (L.get("summary_snip") or "")[:200] or f"Learn {title}",
                "source": "kept",
            }
        )

    # also use sections if present
    if not chapters_map:
        chapters_map["01 - Course"] = [
            {
                "title": L.get("title") or "Lesson",
                "path": L.get("path") or "",
                "software": L.get("software") or [],
                "purpose": L.get("summary_snip") or "",
                "source": "kept",
            }
            for L in inv.get("lessons") or []
        ]

    chapters = []
    for i, (ch_name, lessons) in enumerate(sorted(chapters_map.items()), 1):
        clean_ch = re.sub(r"^\d+\s*-\s*", "", ch_name).strip() or ch_name
        les_out = []
        for j, L in enumerate(lessons, 1):
            les_out.append(
                {
                    "number": j,
                    "title": L["title"],
                    "purpose": L.get("purpose") or f"Learn {L['title']}",
                    "must_cover": [],
                    "software": L.get("software") or [],
                    "est_minutes": 12,
                    "source": "kept",
                    "replace_old": L.get("title"),
                    "source_path": L.get("path") or "",
                }
            )
        chapters.append(
            {
                "number": i,
                "title": clean_ch,
                "goal": f"Master {clean_ch}",
                "lessons": les_out,
            }
        )

    data = {
        "version": "2.0-offline",
        "as_of": _today(),
        "course_title": inv.get("course") or root.name,
        "course_subtitle": "Offline structure from local dump (no LLM)",
        "target_learner": "Learners of the original course",
        "outcomes": [
            "Follow the original curriculum mapped to upgrade folders",
            "Use asset packs bootstrapped from existing descriptions",
        ],
        "removed_lessons": [],
        "kept_updated": [],
        "chapters": chapters,
        "notes_for_writers": "Generated offline from dump. Run --research + LLM structure later to modernize.",
        "source_course": inv.get("course") or root.name,
        "generated_at": _now(),
        "mode": "offline_dump",
    }
    _write(root / STRUCTURE_JSON, json.dumps(data, ensure_ascii=False, indent=2))
    _write(root / STRUCTURE_MD, _structure_to_md(data))
    # offline research stub so status can move past research if desired
    if not (root / REPORT_MD).exists():
        soft = ", ".join(
            x.get("name") for x in (inv.get("software_mentioned") or [])[:12]
        )
        stub = (
            f"# Báo cáo nghiên cứu (offline stub)\n\n"
            f"- Course: {data['course_title']}\n"
            f"- as_of: {data['as_of']}\n"
            f"- Lessons: {inv.get('stats',{}).get('lessons')}\n"
            f"- Software seen: {soft or '—'}\n\n"
            f"> Stub offline — chưa crawl market. Chạy `--research` khi có LLM API.\n"
        )
        _write(root / REPORT_MD, stub)
        _write(
            root / RESEARCH_JSON,
            json.dumps(
                {
                    "as_of": data["as_of"],
                    "course": data["course_title"],
                    "web_enabled": False,
                    "mode": "offline_stub",
                    "report_md": stub,
                    "generated_at": _now(),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    _log(
        f">> Offline structure: {len(chapters)} chapters / "
        f"{sum(len(c['lessons']) for c in chapters)} lessons → {STRUCTURE_JSON}",
        log,
    )
    return data


def generate_new_structure(root: Path, log: LogFn = print) -> dict:
    root = Path(root)
    report = _read(root / REPORT_MD)
    if not report.strip():
        # offline fallback
        _log("Không có research report — dùng structure_from_dump (offline)", log)
        return structure_from_dump(root, log=log)
    notes = _read(root / USER_NOTES)
    inv = {}
    try:
        inv = json.loads(_read(root / INVENTORY_JSON) or "{}")
    except Exception:
        pass
    as_of = _today()
    course = inv.get("course") or root.name

    system = f"""Bạn là kiến trúc sư khóa học (instructional designer) chuyên làm mới curriculum.
Hôm nay: {as_of}.
Nguyên tắc:
1) CHỈ giữ bài còn hữu dụng với công cụ/kiến thức hiện tại.
2) LOẠI bài đã lỗi thời, trùng, hoặc đã được thay bằng workflow/tool mới.
3) THÊM bài cho tính năng/xu hướng mới.
4) Cấu trúc rõ: Chapter → Lesson, đánh số 01, 02…
5) Output JSON hợp lệ (không markdown fence), schema bên dưới.
6) Tiêu đề bài bằng tiếng Việt (có thể giữ tên tool EN)."""

    qa = format_answers_for_prompt(root=root)
    user = f"""Dựa trên BÁO CÁO NGHIÊN CỨU + QUESTIONNAIRE + GHI CHÚ NGƯỜI DÙNG + inventory khóa gốc «{course}»,
hãy sinh CẤU TRÚC KHÓA HỌC MỚI (phiên bản cập nhật).

## Questionnaire / mong muốn user (ƯU TIÊN CAO NHẤT)
{qa[:6000]}

## Ghi chú người dùng (file notes)
{notes[:6000] or '(trống)'}

## Báo cáo nghiên cứu (rút gọn nếu dài)
{report[:26000]}

## Inventory tóm tắt
- Lessons gốc: {inv.get('stats',{}).get('lessons')}
- Software: {json.dumps(inv.get('software_mentioned') or [], ensure_ascii=False)[:2000]}

## Schema JSON bắt buộc
{{
  "version": "2.0",
  "as_of": "{as_of}",
  "course_title": "...",
  "course_subtitle": "...",
  "target_learner": "...",
  "outcomes": ["..."],
  "removed_lessons": [{{"title": "...", "reason": "..."}}],
  "kept_updated": [{{"old_title": "...", "new_title": "...", "reason": "..."}}],
  "chapters": [
    {{
      "number": 1,
      "title": "...",
      "goal": "...",
      "lessons": [
        {{
          "number": 1,
          "title": "...",
          "purpose": "...",
          "must_cover": ["..."],
          "software": ["..."],
          "est_minutes": 15,
          "source": "new|updated|kept",
          "replace_old": "tên bài cũ nếu có"
        }}
      ]
    }}
  ],
  "notes_for_writers": "..."
}}

Chỉ trả về JSON thuần."""

    _log(">> LLM sinh cấu trúc khóa mới…", log)
    raw = _llm(system, user, log=log, max_tokens=10000, task="structure")
    data = _parse_json_loose(raw)
    if not data or "chapters" not in data:
        raise RuntimeError("LLM không trả JSON cấu trúc hợp lệ. Xem log / chạy lại.")

    data.setdefault("as_of", as_of)
    data.setdefault("source_course", course)
    data["generated_at"] = _now()

    jp = root / STRUCTURE_JSON
    _write(jp, json.dumps(data, ensure_ascii=False, indent=2))

    # human readable md
    md = _structure_to_md(data)
    _write(root / STRUCTURE_MD, md)
    _log(f">> Cấu trúc mới → {STRUCTURE_JSON} + {STRUCTURE_MD}", log)
    return data


def _parse_json_loose(text: str) -> Optional[dict]:
    t = (text or "").strip()
    if not t:
        return None
    # strip fences
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def _structure_to_md(data: dict) -> str:
    lines = [
        f"# Cấu trúc khóa học mới — {data.get('course_title') or ''}",
        f"",
        f"- **as_of:** {data.get('as_of')}",
        f"- **subtitle:** {data.get('course_subtitle') or ''}",
        f"- **đối tượng:** {data.get('target_learner') or ''}",
        f"",
        f"## Outcomes",
    ]
    for o in data.get("outcomes") or []:
        lines.append(f"- {o}")
    lines += ["", "## Đã loại bỏ"]
    for r in data.get("removed_lessons") or []:
        if isinstance(r, dict):
            lines.append(f"- **{r.get('title')}** — {r.get('reason')}")
        else:
            lines.append(f"- {r}")
    lines += ["", "## Cấu trúc chương"]
    for ch in data.get("chapters") or []:
        lines.append(f"\n### {int(ch.get('number') or 0):02d} — {ch.get('title')}")
        if ch.get("goal"):
            lines.append(f"_{ch.get('goal')}_")
        for les in ch.get("lessons") or []:
            lines.append(
                f"- **{int(les.get('number') or 0):02d}. {les.get('title')}** "
                f"({les.get('source') or 'new'}, ~{les.get('est_minutes') or '?'}') — "
                f"{les.get('purpose') or ''}"
            )
    if data.get("notes_for_writers"):
        lines += ["", "## Ghi chú cho người viết", data["notes_for_writers"]]
    return "\n".join(lines) + "\n"


def scaffold_and_generate_lessons(
    root: Path,
    *,
    generate_content: bool = True,
    log: LogFn = print,
) -> Path:
    """
    Tạo folder _upgrade_v2 theo cấu trúc mới.
    Nếu generate_content: dùng Course Studio asset pack (script, workshop, use cases…).
    """
    root = Path(root)
    data = json.loads(_read(root / STRUCTURE_JSON) or "{}")
    if not data.get("chapters"):
        raise FileNotFoundError(f"Chưa có {STRUCTURE_JSON}")

    dest = root / UPGRADE_DIR
    dest.mkdir(parents=True, exist_ok=True)

    # Full asset pack via course_studio (preferred)
    if generate_content:
        try:
            import course_studio as CS

            use_pack = True
            try:
                if hasattr(C, "get_course_asset_pack"):
                    use_pack = bool(C.get_course_asset_pack())
            except Exception:
                pass
            if use_pack:
                _log(">> Sinh Lesson Asset Pack (studio)…", log)
                CS.generate_all_assets(root, force=False, log=log)
                _log(f">> Scaffold + assets → {dest}", log)
                return dest
        except Exception as e:
            _log(f"[studio] fallback outline đơn giản: {e}", log)

    title = data.get("course_title") or (getattr(C, "COURSE", None) or root.name) + " (Updated)"
    _write(
        dest / "README.md",
        f"# {title}\n\n"
        f"Phiên bản nâng cấp · as_of {data.get('as_of')} · sinh {data.get('generated_at')}\n\n"
        f"Nguồn: khóa gốc `{root.name}` + research report.\n",
    )
    _write(dest / "_structure.json", json.dumps(data, ensure_ascii=False, indent=2))

    report_snip = _read(root / REPORT_MD)[:12000]
    notes = _read(root / USER_NOTES)[:4000]
    try:
        lang = C.get_course_master_lang() if hasattr(C, "get_course_master_lang") else "vi"
    except Exception:
        lang = "vi"

    total = sum(len(ch.get("lessons") or []) for ch in data.get("chapters") or [])
    n = 0
    for ch in data.get("chapters") or []:
        cn = int(ch.get("number") or 0)
        cname = f"{cn:02d} - {_san(ch.get('title') or f'Chapter {cn}')}"
        cdir = dest / cname
        cdir.mkdir(exist_ok=True)
        _write(cdir / "chapter.md", f"# {ch.get('title')}\n\n{ch.get('goal') or ''}\n")
        for les in ch.get("lessons") or []:
            n += 1
            ln = int(les.get("number") or 0)
            lname = f"{ln:02d} - {_san(les.get('title') or f'Lesson {ln}')}"
            ldir = cdir / lname
            ldir.mkdir(exist_ok=True)
            meta = {
                "title": les.get("title"),
                "purpose": les.get("purpose"),
                "must_cover": les.get("must_cover"),
                "software": les.get("software"),
                "source": les.get("source"),
                "replace_old": les.get("replace_old"),
                "est_minutes": les.get("est_minutes"),
                "master_lang": lang,
            }
            _write(ldir / "lesson.json", json.dumps(meta, ensure_ascii=False, indent=2))
            if not generate_content:
                _write(
                    ldir / "description.md",
                    f"# {les.get('title')}\n\n## Purpose\n{les.get('purpose') or ''}\n\n"
                    f"## Must cover\n"
                    + "\n".join(f"- {x}" for x in (les.get("must_cover") or []))
                    + "\n",
                )
                continue
            _log(f"[{n}/{total}] Viết outline: {ch.get('title')} / {les.get('title')}", log)
            lang_note = "TIẾNG VIỆT" if lang == "vi" else "ENGLISH"
            system = (
                f"Bạn là giáo viên thiết kế bài học. Hôm nay {_today()}. "
                f"Viết {lang_note}, Markdown, thực tế, cập nhật. Không bịa tính năng tool không chắc."
            )
            user = f"""Viết nội dung bài học đầy đủ cho khóa cập nhật.

## Bài
- Chương: {ch.get('title')}
- Bài: {les.get('title')}
- Purpose: {les.get('purpose')}
- Must cover: {json.dumps(les.get('must_cover') or [], ensure_ascii=False)}
- Software: {json.dumps(les.get('software') or [], ensure_ascii=False)}
- Source: {les.get('source')} (thay bài cũ: {les.get('replace_old') or '—'})

## Ngữ cảnh report (rút gọn)
{report_snip[:6000]}

## Ghi chú user
{notes[:1500]}

## Cấu trúc bài bắt buộc
# {les.get('title')}
## Purpose of the video
## Bối cảnh & tại sao quan trọng ({_today()})
## Nội dung chính (chi tiết, actionable)
## Step-by-step thực hành
## Key takeaways
## Todo list
## Resources / tools
## Những gì đã lỗi thời (không làm nữa)
"""
            try:
                body = _llm(system, user, log=log, max_tokens=6000, task="assets")
            except Exception as e:
                body = f"# {les.get('title')}\n\n_(Lỗi LLM: {e})_\n"
            _write(ldir / "description.md", body.strip() + "\n")
            _write(ldir / "lesson.md", body.strip() + "\n")
            time.sleep(0.25)

    _log(f">> Scaffold khóa mới → {dest}", log)
    return dest


def _san(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "", s or "")
    s = re.sub(r"\s+", " ", s).strip()[:100]
    return s or "untitled"


# ----------------------------- pipeline -----------------------------
def research_enabled() -> bool:
    try:
        if hasattr(C, "get_course_upgrade_research"):
            return bool(C.get_course_upgrade_research())
    except Exception:
        pass
    return bool(getattr(C, "COURSE_UPGRADE_RESEARCH", True))


def run_upgrade(
    root: Path,
    *,
    do_research: bool = True,
    do_web: bool = True,
    do_structure: bool = True,
    do_lessons: bool = False,
    do_questionnaire: Optional[bool] = None,
    answers: Optional[dict] = None,
    interactive_questions: bool = False,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(root)

    result = {"root": str(root), "as_of": _today()}

    # 0) Questionnaire
    use_q = questionnaire_enabled() if do_questionnaire is None else bool(do_questionnaire)
    if answers is not None:
        save_answers(root, answers, log=log)
        result["questionnaire"] = str(root / ANSWERS_JSON)
    elif use_q:
        if interactive_questions:
            interactive_cli_questionnaire(root, log=log)
            result["questionnaire"] = str(root / ANSWERS_JSON)
        elif (root / ANSWERS_JSON).exists():
            _log(f">> Dùng questionnaire có sẵn: {ANSWERS_JSON}", log)
            result["questionnaire"] = str(root / ANSWERS_JSON)
        else:
            _log(
                f">> Questionnaire BẬT nhưng chưa có {ANSWERS_JSON} "
                f"— GUI nên hỏi trước; CLI: --interactive-questions hoặc --answers-file",
                log,
            )
    else:
        _log(">> Questionnaire TẮT — bỏ qua câu hỏi user", log)

    inv = build_inventory(root, log=log)
    result["inventory"] = str(root / INVENTORY_JSON)

    if do_research:
        if not research_enabled() and do_research:
            _log("(research toggle off in settings — vẫn chạy vì được gọi tường minh)", log)
        research = research_market(
            inv, do_web=do_web, user_answers=load_answers(root), root=root, log=log
        )
        paths = write_reports(root, inv, research, log=log)
        result.update(paths)
    else:
        _log(">> Bỏ qua research (dùng report có sẵn)", log)

    if do_structure:
        data = generate_new_structure(root, log=log)
        result["structure"] = str(root / STRUCTURE_JSON)
        result["chapters"] = len(data.get("chapters") or [])
        result["lessons"] = sum(len(c.get("lessons") or []) for c in data.get("chapters") or [])

    if do_lessons:
        dest = scaffold_and_generate_lessons(root, generate_content=True, log=log)
        result["upgrade_dir"] = str(dest)

    _log("=== UPGRADE XONG ===", log)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Nâng cấp khóa học: questionnaire → research → DOCX → cấu trúc mới")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--research", action="store_true", help="Chạy inventory + research + report")
    ap.add_argument("--no-web", action="store_true", help="Research không gọi web snippets")
    ap.add_argument("--structure-only", action="store_true", help="Chỉ sinh cấu trúc từ report + notes")
    ap.add_argument("--generate-lessons", action="store_true", help="Sinh outline bài vào _upgrade_v2/")
    ap.add_argument("--full", action="store_true", help="research + structure + generate lessons")
    ap.add_argument("--inventory-only", action="store_true")
    ap.add_argument(
        "--no-questionnaire",
        action="store_true",
        help="Tắt questionnaire (không hỏi / không bắt buộc answers)",
    )
    ap.add_argument(
        "--interactive-questions",
        action="store_true",
        help="Hỏi questionnaire trên terminal trước research",
    )
    ap.add_argument(
        "--answers-file",
        help="JSON answers {id: text} hoặc full payload — ghi vào khóa rồi chạy",
    )
    ap.add_argument(
        "--questionnaire-only",
        action="store_true",
        help="Chỉ lưu answers-file / interactive, không research",
    )
    args = ap.parse_args(argv)

    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    root = Path(C.ROOT)

    answers = None
    if args.answers_file:
        p = Path(args.answers_file).expanduser()
        answers = json.loads(p.read_text(encoding="utf-8"))
        save_answers(root, answers)
        if args.questionnaire_only:
            return 0

    if args.inventory_only:
        build_inventory(root)
        return 0

    do_q = False if args.no_questionnaire else None

    if args.full:
        run_upgrade(
            root,
            do_research=True,
            do_web=not args.no_web,
            do_structure=True,
            do_lessons=True,
            do_questionnaire=do_q,
            answers=answers,
            interactive_questions=args.interactive_questions,
        )
        return 0

    if args.structure_only:
        run_upgrade(
            root,
            do_research=False,
            do_structure=True,
            do_lessons=args.generate_lessons,
            do_questionnaire=do_q,
            answers=answers,
            interactive_questions=False,
        )
        return 0

    if args.generate_lessons and not args.research:
        scaffold_and_generate_lessons(root, generate_content=True)
        return 0

    if args.questionnaire_only:
        if args.interactive_questions:
            interactive_cli_questionnaire(root)
        return 0

    # default: research (+ structure)
    do_res = args.research or not (args.structure_only or args.generate_lessons)
    run_upgrade(
        root,
        do_research=do_res or args.research,
        do_web=not args.no_web,
        do_structure=True,
        do_lessons=args.generate_lessons,
        do_questionnaire=do_q,
        answers=answers,
        interactive_questions=args.interactive_questions,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        raise SystemExit(1)
