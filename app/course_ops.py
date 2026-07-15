#!/usr/bin/env python3
"""
Tiện ích Course OS: glossary/term-lock, translation memory, style guide,
budget token ước lượng, research cache, versioning, obsolescence score.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import config as C

LogFn = Callable[[str], None]

GLOSSARY_FILE = "_course_glossary.json"
STYLE_FILE = "_course_style.json"
TM_DIR = "_translation_memory"
CACHE_DIR = "_research_cache"
BUDGET_FILE = "_llm_budget.json"
VERSION_FILE = "_course_version.json"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today() -> str:
    return date.today().isoformat()


def _read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _write_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---- Glossary / term lock ----
DEFAULT_GLOSSARY = {
    "terms": [
        {"en": "Claude", "lock": True},
        {"en": "ChatGPT", "lock": True},
        {"en": "n8n", "lock": True},
        {"en": "Make.com", "lock": True},
        {"en": "Zapier", "lock": True},
        {"en": "API", "lock": True},
        {"en": "RAG", "lock": True},
        {"en": "MCP", "lock": True},
        {"en": "LLM", "lock": True},
        {"en": "Skool", "lock": True},
    ],
    "updated_at": None,
}


def load_glossary(root: Path) -> dict:
    root = Path(root)
    p = root / GLOSSARY_FILE
    if not p.exists():
        data = dict(DEFAULT_GLOSSARY)
        data["updated_at"] = _now()
        _write_json(p, data)
        return data
    return _read_json(p, DEFAULT_GLOSSARY)


def save_glossary(root: Path, data: dict) -> Path:
    data = dict(data or {})
    data["updated_at"] = _now()
    p = Path(root) / GLOSSARY_FILE
    _write_json(p, data)
    return p


def glossary_lock_list(root: Path) -> List[str]:
    g = load_glossary(root)
    out = []
    for t in g.get("terms") or []:
        if isinstance(t, dict) and t.get("lock") and t.get("en"):
            out.append(str(t["en"]))
        elif isinstance(t, str):
            out.append(t)
    return out


def glossary_prompt_block(root: Path, locale: Optional[str] = None) -> str:
    locks = glossary_lock_list(root)
    parts = []
    if locks:
        parts.append(
            "TERM LOCK — never translate these product/tech names: "
            + ", ".join(locks)
            + "."
        )
    # per-locale preferred translations for non-locked teaching terms
    g = load_glossary(root)
    loc_map = (g.get("locale_terms") or {}).get(locale or "") or {}
    if loc_map:
        pairs = [f"{k} → {v}" for k, v in list(loc_map.items())[:40]]
        parts.append("Preferred translations for this locale: " + "; ".join(pairs) + ".")
    if not parts:
        return ""
    return " ".join(parts) + "\n"


def set_locale_term(root: Path, locale: str, source: str, target: str) -> dict:
    """Ghi glossary locale_terms[locale][source]=target."""
    g = load_glossary(root)
    lt = dict(g.get("locale_terms") or {})
    bucket = dict(lt.get(locale) or {})
    bucket[(source or "").strip()] = (target or "").strip()
    lt[locale] = bucket
    g["locale_terms"] = lt
    save_glossary(root, g)
    return g


def export_locale_glossary_md(root: Path, log: LogFn = print) -> Path:
    g = load_glossary(root)
    lines = [
        f"# Glossary — {Path(root).name}",
        f"",
        f"Updated: {g.get('updated_at') or _now()}",
        f"",
        f"## Locked terms (do not translate)",
        f"",
    ]
    for t in g.get("terms") or []:
        if isinstance(t, dict):
            lines.append(f"- **{t.get('en')}**" + (" (lock)" if t.get("lock") else ""))
        else:
            lines.append(f"- {t}")
    lines += ["", "## Locale preferred translations", ""]
    for loc, mp in (g.get("locale_terms") or {}).items():
        lines.append(f"### {loc}")
        for k, v in (mp or {}).items():
            lines.append(f"- {k} → {v}")
        lines.append("")
    out = Path(root) / "_course_glossary.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f">> Glossary MD → {out.name}")
    return out


# ---- Style guide ----
DEFAULT_STYLE = {
    "tone": "professional, practical, friendly mentor",
    "address": "you / bạn",
    "forbid": ["get rich quick", "guaranteed income", "100% passive"],
    "cta": "Encourage practice, not hype",
    "master_lang": "vi",
}


def load_style(root: Path) -> dict:
    p = Path(root) / STYLE_FILE
    if not p.exists():
        d = dict(DEFAULT_STYLE)
        try:
            d["master_lang"] = C.get_course_master_lang()
        except Exception:
            pass
        _write_json(p, d)
        return d
    return _read_json(p, DEFAULT_STYLE)


def style_prompt_block(root: Path) -> str:
    s = load_style(root)
    return (
        f"STYLE: tone={s.get('tone')}; address={s.get('address')}; "
        f"forbid={s.get('forbid')}; cta={s.get('cta')}.\n"
    )


# ---- Translation memory ----
def tm_path(root: Path, locale: str) -> Path:
    return Path(root) / TM_DIR / f"{locale}.jsonl"


def tm_lookup(root: Path, locale: str, source: str) -> Optional[str]:
    p = tm_path(root, locale)
    if not p.exists():
        return None
    key = hashlib.sha256(source.strip().encode("utf-8")).hexdigest()
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("hash") == key:
                return rec.get("target")
    except Exception:
        return None
    return None


def tm_store(root: Path, locale: str, source: str, target: str):
    p = tm_path(root, locale)
    p.parent.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(source.strip().encode("utf-8")).hexdigest()
    rec = {"hash": key, "source": source[:500], "target": target, "at": _now()}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---- Research cache ----
def cache_get(root: Path, key: str, max_age_days: int = 7) -> Optional[dict]:
    p = Path(root) / CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:24]}.json"
    if not p.exists():
        return None
    data = _read_json(p, None)
    if not data:
        return None
    try:
        ts = datetime.strptime(data.get("at", "2000-01-01"), "%Y-%m-%d %H:%M")
        if datetime.now() - ts > timedelta(days=max_age_days):
            return None
    except Exception:
        return None
    return data.get("payload")


def cache_set(root: Path, key: str, payload: dict):
    d = Path(root) / CACHE_DIR
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{hashlib.sha256(key.encode()).hexdigest()[:24]}.json"
    _write_json(p, {"at": _now(), "key": key[:200], "payload": payload})


# ---- Budget ----
def load_budget(root: Path) -> dict:
    p = Path(root) / BUDGET_FILE
    if not p.exists():
        data = {
            "usd_cap": float(getattr(C, "LLM_BUDGET_USD", 20.0) or 20.0),
            "spent_usd": 0.0,
            "calls": 0,
            "tokens_est": 0,
            "updated_at": _now(),
        }
        _write_json(p, data)
        return data
    return _read_json(p, {"usd_cap": 20.0, "spent_usd": 0.0})


def estimate_cost_usd(chars: int, model: str = "") -> float:
    """Ước lượng thô $/1M tokens (~4 chars/token)."""
    tokens = max(1, chars // 4)
    # rough averages
    per_m = 0.5
    m = (model or "").lower()
    if "gpt-4o" in m or "claude" in m or "sonnet" in m or "opus" in m:
        per_m = 5.0
    elif "flash" in m or "mini" in m or "deepseek" in m:
        per_m = 0.3
    return round(tokens / 1_000_000 * per_m, 6)


def budget_charge(root: Path, chars: int, model: str = "", log: LogFn = print) -> bool:
    """Trừ budget; False nếu vượt cap."""
    b = load_budget(root)
    cost = estimate_cost_usd(chars, model)
    if b.get("spent_usd", 0) + cost > float(b.get("usd_cap") or 20):
        log(f"[budget] VƯỢT cap ${b.get('usd_cap')} (spent={b.get('spent_usd'):.4f} +{cost})")
        return False
    b["spent_usd"] = round(float(b.get("spent_usd") or 0) + cost, 6)
    b["calls"] = int(b.get("calls") or 0) + 1
    b["tokens_est"] = int(b.get("tokens_est") or 0) + max(1, chars // 4)
    b["updated_at"] = _now()
    _write_json(Path(root) / BUDGET_FILE, b)
    return True


def video_cost_estimate(minutes: float, provider: str = "heygen") -> dict:
    """Ước lượng chi phí video AI (tham khảo, cập nhật tay)."""
    rates = {
        "heygen": 1.0,      # $/min ballpark
        "synthesia": 1.2,
        "elevenlabs_tts": 0.05,  # audio only
        "local": 0.0,
    }
    rate = rates.get((provider or "").lower(), 0.8)
    return {
        "provider": provider,
        "minutes": minutes,
        "usd_est": round(minutes * rate, 2),
        "note": "Ước lượng — kiểm tra pricing provider trước khi render",
        "as_of": _today(),
    }


# ---- Versioning ----
def bump_version(root: Path, note: str = "") -> dict:
    p = Path(root) / VERSION_FILE
    data = _read_json(p, {"version": "0.0.0", "history": []})
    today = date.today()
    ver = f"v{today.strftime('%Y.%m')}"
    # if same month, suffix
    hist = data.get("history") or []
    same = [h for h in hist if str(h.get("version", "")).startswith(ver)]
    if same:
        ver = f"{ver}.{len(same)+1}"
    rec = {"version": ver, "at": _now(), "note": note or "upgrade"}
    hist.insert(0, rec)
    data["version"] = ver
    data["history"] = hist[:50]
    data["updated_at"] = _now()
    _write_json(p, data)
    # public changelog md
    lines = [f"# Changelog — {Path(root).name}\n"]
    for h in data["history"][:20]:
        lines.append(f"## {h.get('version')} — {h.get('at')}\n\n{h.get('note')}\n")
    (Path(root) / "CHANGELOG.md").write_text("\n".join(lines), encoding="utf-8")
    return data


# ---- Obsolescence heuristic ----
OBSOLETE_HINTS = [
    r"\b2019\b", r"\b2020\b", r"\b2021\b", r"\b2022\b",
    r"zapier classic", r"gpt-3\b", r"davinci", r"playground\.openai",
    r"facebook blue app", r"instapage", r"clickfunnels 1\.0",
    r"chrome extension only", r"no-code is dead",
]


def obsolescence_score(title: str, text: str) -> dict:
    """0=fresh, 100=likely obsolete (heuristic)."""
    blob = f"{title}\n{text}".lower()
    score = 0
    hits = []
    for pat in OBSOLETE_HINTS:
        if re.search(pat, blob, re.I):
            score += 15
            hits.append(pat)
    # year mentions
    years = [int(y) for y in re.findall(r"\b(20[12][0-9])\b", blob)]
    if years:
        oldest = min(years)
        age = date.today().year - oldest
        if age >= 3:
            score += min(40, age * 8)
            hits.append(f"old_year:{oldest}")
    score = min(100, score)
    return {"score": score, "hits": hits, "likely_obsolete": score >= 45}


def score_inventory_lessons(inventory: dict) -> dict:
    lessons = inventory.get("lessons") or []
    for L in lessons:
        snip = L.get("summary_snip") or ""
        L["obsolescence"] = obsolescence_score(L.get("title") or "", snip)
    inventory["obsolescence_summary"] = {
        "high_risk": sum(
            1 for L in lessons if (L.get("obsolescence") or {}).get("likely_obsolete")
        ),
        "as_of": _today(),
    }
    return inventory


# ---- Captions from script ----
def script_to_srt(script: str, wpm: int = 140) -> str:
    """Chia script thành SRT thô theo tốc độ nói."""
    text = re.sub(r"\[PAUSE\]", " ", script or "", flags=re.I)
    text = re.sub(r"#+\s*", "", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        paras = [text.strip()] if text.strip() else ["(empty)"]
    lines = []
    t = 0.0
    idx = 1
    for para in paras:
        words = para.split()
        if not words:
            continue
        # chunk ~12 words
        for i in range(0, len(words), 12):
            chunk = " ".join(words[i : i + 12])
            dur = max(1.5, len(chunk.split()) / wpm * 60)
            start, end = t, t + dur
            lines.append(
                f"{idx}\n{_ts(start)} --> {_ts(end)}\n{chunk}\n"
            )
            idx += 1
            t = end + 0.2
    return "\n".join(lines)


def _ts(sec: float) -> str:
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_captions_for_lesson(lesson_dir: Path, log: LogFn = print) -> Optional[Path]:
    script_p = Path(lesson_dir) / "talking_script.md"
    if not script_p.exists():
        return None
    srt = script_to_srt(script_p.read_text(encoding="utf-8", errors="replace"))
    out = Path(lesson_dir) / "talking_script.srt"
    out.write_text(srt, encoding="utf-8")
    vtt = srt.replace(",", ".")
    # crude vtt
    (Path(lesson_dir) / "talking_script.vtt").write_text(
        "WEBVTT\n\n" + re.sub(r"(\d+)\n", r"\1\n", vtt), encoding="utf-8"
    )
    log(f"   captions → {out.name}")
    return out


def add_glossary_term(root: Path, term: str, lock: bool = True) -> dict:
    g = load_glossary(root)
    terms = list(g.get("terms") or [])
    en = (term or "").strip()
    if not en:
        raise ValueError("term rỗng")
    for t in terms:
        if isinstance(t, dict) and (t.get("en") or "").lower() == en.lower():
            t["lock"] = lock
            save_glossary(root, g)
            return g
        if isinstance(t, str) and t.lower() == en.lower():
            return g
    terms.append({"en": en, "lock": lock})
    g["terms"] = terms
    save_glossary(root, g)
    return g


def set_budget_cap(root: Path, usd: float) -> dict:
    b = load_budget(root)
    b["usd_cap"] = float(usd)
    b["updated_at"] = _now()
    _write_json(Path(root) / BUDGET_FILE, b)
    return b


def reset_budget_spent(root: Path) -> dict:
    b = load_budget(root)
    b["spent_usd"] = 0.0
    b["calls"] = 0
    b["tokens_est"] = 0
    b["updated_at"] = _now()
    _write_json(Path(root) / BUDGET_FILE, b)
    return b


def init_ops(root: Path, log: LogFn = print) -> dict:
    """Tạo glossary + style + budget + brand stub nếu thiếu."""
    root = Path(root)
    g = load_glossary(root)
    s = load_style(root)
    b = load_budget(root)
    brand_p = root / "_brand_kit.json"
    if not brand_p.exists():
        brand = {
            "name": root.name,
            "primary_color": "#1E40AF",
            "voice": "default",
            "eleven_voice_id": "21m00Tcm4TlvDq8ikWAM",
            "locale_voices": {"en": "21m00Tcm4TlvDq8ikWAM", "vi": "21m00Tcm4TlvDq8ikWAM"},
        }
        _write_json(brand_p, brand)
        log(f">> brand kit → {brand_p.name}")
    log(f">> glossary terms={len(g.get('terms') or [])}")
    log(f">> style tone={s.get('tone')}")
    log(f">> budget cap=${b.get('usd_cap')} spent=${b.get('spent_usd')}")
    return {"glossary": g, "style": s, "budget": b}


def cost_dashboard(root: Path, log: LogFn = print) -> dict:
    """
    Tổng hợp chi phí LLM + video estimate → _cost_dashboard.md/.json
    """
    root = Path(root)
    b = load_budget(root)
    video = {"jobs": 0, "usd_est_total": 0, "minutes_total": 0, "provider": ""}
    vq = root / "_upgrade_v2" / "_video_queue.json"
    if vq.exists():
        try:
            video = json.loads(vq.read_text(encoding="utf-8"))
        except Exception:
            pass
    rendered = 0
    for it in video.get("items") or []:
        if it.get("status") == "rendered":
            rendered += 1
    data = {
        "at": _now(),
        "course": root.name,
        "llm": {
            "usd_cap": b.get("usd_cap"),
            "spent_usd": b.get("spent_usd"),
            "calls": b.get("calls"),
            "tokens_est": b.get("tokens_est"),
            "remaining_usd": round(
                float(b.get("usd_cap") or 0) - float(b.get("spent_usd") or 0), 4
            ),
        },
        "video": {
            "provider": video.get("provider"),
            "jobs": video.get("jobs"),
            "rendered": rendered,
            "minutes_total": video.get("minutes_total"),
            "usd_est_total": video.get("usd_est_total"),
        },
        "total_est_usd": round(
            float(b.get("spent_usd") or 0) + float(video.get("usd_est_total") or 0), 4
        ),
    }
    _write_json(root / "_cost_dashboard.json", data)
    md = [
        f"# Cost dashboard — {root.name}",
        f"",
        f"Generated: {data['at']}",
        f"",
        f"## LLM",
        f"",
        f"- Cap: **${data['llm']['usd_cap']}**",
        f"- Spent: **${data['llm']['spent_usd']}**",
        f"- Remaining: **${data['llm']['remaining_usd']}**",
        f"- Calls: {data['llm']['calls']} · tokens est: {data['llm']['tokens_est']}",
        f"",
        f"## Video (estimate)",
        f"",
        f"- Provider: {data['video']['provider'] or '—'}",
        f"- Jobs: {data['video']['jobs']} · rendered: {data['video']['rendered']}",
        f"- Minutes: {data['video']['minutes_total']}",
        f"- USD est: **${data['video']['usd_est_total']}**",
        f"",
        f"## Total (LLM spent + video est)",
        f"",
        f"**${data['total_est_usd']}**",
        f"",
        f"> Video numbers are estimates until providers invoice.",
    ]
    (root / "_cost_dashboard.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log(f">> Cost dashboard → _cost_dashboard.md (total ~${data['total_est_usd']})")
    return data


def main(argv=None):
    """CLI: glossary / style / budget / init."""
    import argparse
    import sys

    import config as Cfg

    ap = argparse.ArgumentParser(description="Course ops: glossary, style, budget")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--init", action="store_true", help="Tạo glossary+style+budget+brand")
    ap.add_argument("--glossary-show", action="store_true")
    ap.add_argument("--glossary-add", help="Thêm term lock (EN)")
    ap.add_argument(
        "--glossary-locale",
        nargs=3,
        metavar=("LOCALE", "SOURCE", "TARGET"),
        help="Preferred translation: --glossary-locale es Workshop Taller",
    )
    ap.add_argument("--glossary-md", action="store_true")
    ap.add_argument("--style-show", action="store_true")
    ap.add_argument("--budget-show", action="store_true")
    ap.add_argument("--budget-cap", type=float, help="Đặt USD cap")
    ap.add_argument("--budget-reset", action="store_true", help="Reset spent về 0")
    ap.add_argument("--cost-dashboard", action="store_true", help="LLM + video cost report")
    ap.add_argument("--version-bump", nargs="?", const="upgrade", help="Bump course version")
    args = ap.parse_args(argv)

    if args.root:
        Cfg.set_root(args.root)
    elif args.course:
        Cfg.set_course(args.course)
    root = Path(Cfg.ROOT)

    if args.init:
        init_ops(root)
        return 0
    if args.glossary_add:
        g = add_glossary_term(root, args.glossary_add, lock=True)
        print(f"Glossary: {len(g.get('terms') or [])} terms")
        return 0
    if args.glossary_locale:
        g = set_locale_term(
            root, args.glossary_locale[0], args.glossary_locale[1], args.glossary_locale[2]
        )
        print(json.dumps(g.get("locale_terms"), ensure_ascii=False, indent=2))
        return 0
    if args.glossary_md:
        print(export_locale_glossary_md(root))
        return 0
    if args.glossary_show:
        print(json.dumps(load_glossary(root), ensure_ascii=False, indent=2))
        return 0
    if args.style_show:
        print(json.dumps(load_style(root), ensure_ascii=False, indent=2))
        return 0
    if args.budget_cap is not None:
        print(json.dumps(set_budget_cap(root, args.budget_cap), indent=2))
        return 0
    if args.budget_reset:
        print(json.dumps(reset_budget_spent(root), indent=2))
        return 0
    if args.budget_show:
        print(json.dumps(load_budget(root), ensure_ascii=False, indent=2))
        return 0
    if args.cost_dashboard:
        print(json.dumps(cost_dashboard(root), ensure_ascii=False, indent=2))
        return 0
    if args.version_bump is not None:
        print(json.dumps(bump_version(root, note=args.version_bump or "upgrade"), indent=2))
        return 0
    # default: show compact
    init_ops(root)
    b = load_budget(root)
    print(
        f"budget ${b.get('spent_usd')}/${b.get('usd_cap')} · "
        f"glossary {len(load_glossary(root).get('terms') or [])} terms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
