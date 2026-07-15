#!/usr/bin/env python3
"""
Competitor / market course scan — DDG snippets + optional LLM gap analysis.

  python course_competitor.py --course X
  python course_competitor.py --course X --queries "ai agents course,n8n automation course"
  python course_competitor.py --course X --llm
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable, List, Optional

import config as C
import course_upgrade as CU

LogFn = Callable[[str], None]
OUT_JSON = "_competitor_scan.json"
OUT_MD = "_Competitor_Scan.md"


def _log(msg: str, log: LogFn = print):
    log(msg)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def default_queries(root: Path) -> List[str]:
    root = Path(root)
    name = root.name
    software = []
    inv_p = root / CU.INVENTORY_JSON
    if inv_p.exists():
        try:
            inv = json.loads(inv_p.read_text(encoding="utf-8"))
            software = [x.get("name") for x in (inv.get("software_mentioned") or [])[:6]]
        except Exception:
            pass
    year = date.today().year
    qs = [
        f"{name} course alternative {year}",
        f"best {name} online course review",
        f"{name} skool community curriculum",
    ]
    for s in software[:4]:
        if s:
            qs.append(f"{s} course online {year}")
            qs.append(f"{s} tutorial curriculum outline")
    # de-dupe
    seen = set()
    out = []
    for q in qs:
        k = q.lower()
        if k not in seen:
            seen.add(k)
            out.append(q)
    return out[:12]


def scan_competitors(
    root: Path,
    *,
    queries: Optional[List[str]] = None,
    use_llm: bool = False,
    log: LogFn = print,
) -> dict:
    root = Path(root)
    queries = queries or default_queries(root)
    hits = []
    _log(f">> Competitor scan ({len(queries)} queries)…", log)
    for q in queries:
        rows = CU._simple_web_snippets(q, max_results=5)
        hits.append({"query": q, "results": rows})
        _log(f"   «{q[:50]}…» → {len(rows)} hits", log)
        time.sleep(0.3)

    # flatten unique urls
    seen_url = set()
    flat = []
    for block in hits:
        for r in block.get("results") or []:
            u = (r.get("url") or "").strip()
            if not u or u in seen_url:
                continue
            seen_url.add(u)
            flat.append(r)

    analysis_md = ""
    if use_llm and flat:
        titles = "\n".join(
            f"- {x.get('title')} | {x.get('url')}\n  {x.get('snippet','')[:200]}"
            for x in flat[:25]
        )
        # our structure summary
        st = ""
        sp = root / CU.STRUCTURE_MD
        if sp.exists():
            st = sp.read_text(encoding="utf-8", errors="replace")[:3000]
        system = (
            "You are a course market analyst. Write Vietnamese markdown. "
            "Be concrete about curriculum gaps. Do not invent URLs."
        )
        user = f"""# Competitor signals for course «{root.name}»

## Web hits
{titles}

## Our structure (if any)
{st or '(none yet)'}

## Write report
## 1. Competitive landscape
## 2. Common curriculum themes
## 3. Gaps we should fill
## 4. Positioning angles
## 5. Risks / undifferentiated topics to avoid over-investing
"""
        _log(">> LLM gap analysis…", log)
        analysis_md = CU._llm(system, user, log=log, max_tokens=4000, task="research")

    data = {
        "at": _now(),
        "course": root.name,
        "queries": queries,
        "unique_results": len(flat),
        "hits": hits,
        "flat": flat[:80],
        "analysis_md": analysis_md,
        "llm": use_llm,
    }
    (root / OUT_JSON).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        f"# Competitor scan — {root.name}",
        f"",
        f"Generated: {data['at']}",
        f"Unique results: **{data['unique_results']}**",
        f"",
        f"## Queries",
        f"",
    ]
    for q in queries:
        md.append(f"- {q}")
    md += ["", "## Top results", ""]
    for r in flat[:40]:
        md.append(f"- [{r.get('title')}]({r.get('url')})")
        if r.get("snippet"):
            md.append(f"  - {r.get('snippet')[:240]}")
    if analysis_md:
        md += ["", "---", "", analysis_md]
    else:
        md += [
            "",
            "> Chạy lại với `--llm` để sinh gap analysis.",
        ]
    (root / OUT_MD).write_text("\n".join(md) + "\n", encoding="utf-8")
    _log(f">> Competitor scan → {OUT_MD} ({data['unique_results']} urls)", log)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="Competitor course market scan")
    ap.add_argument("--course")
    ap.add_argument("--root")
    ap.add_argument("--queries", help="Comma-separated custom queries")
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args(argv)
    if args.root:
        C.set_root(args.root)
    elif args.course:
        C.set_course(args.course)
    qs = None
    if args.queries:
        qs = [x.strip() for x in args.queries.split(",") if x.strip()]
    data = scan_competitors(Path(C.ROOT), queries=qs, use_llm=args.llm)
    print(
        json.dumps(
            {
                "at": data.get("at"),
                "unique_results": data.get("unique_results"),
                "queries": data.get("queries"),
                "llm": data.get("llm"),
                "report": OUT_MD,
            },
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
