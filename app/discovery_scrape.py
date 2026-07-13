"""
Cào danh sách community / khóa học công khai trên Skool Discovery.

Nguồn: https://www.skool.com/discovery (Next.js pageProps.groups)
Query params (từ UI Skool):
  p     page (1-based)
  c     category id (topic)
  lang  all | english | vietnamese | …
  pr    free | paid | free-trial
  ty    private | public
  srt   trending | top

Lưu SQLite + CSV dưới BASE/skool_discovery/
Dùng Playwright để vượt AWS WAF.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode

import config as C

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

PAGE_SIZE = 30
DEFAULT_DELAY = 0.35

# Fallback tĩnh (đồng bộ với Skool discovery UI) — cập nhật runtime khi scrape
STATIC_LANGUAGES = [
    ("all", "All"),
    ("english", "English"),
    ("german", "German"),
    ("spanish", "Spanish"),
    ("french", "French"),
    ("chinese", "Chinese"),
    ("italian", "Italian"),
    ("dutch", "Dutch"),
    ("vietnamese", "Vietnamese"),
    ("arabic", "Arabic"),
    ("hebrew", "Hebrew"),
    ("danish", "Danish"),
    ("romanian", "Romanian"),
    ("turkish", "Turkish"),
    ("polish", "Polish"),
    ("czech", "Czech"),
    ("hungarian", "Hungarian"),
    ("swedish", "Swedish"),
    ("portuguese", "Portuguese"),
    ("bulgarian", "Bulgarian"),
    ("norwegian", "Norwegian"),
    ("finnish", "Finnish"),
    ("croatian", "Croatian"),
    ("latvian", "Latvian"),
    ("slovak", "Slovak"),
    ("serbian", "Serbian"),
    ("mongolian", "Mongolian"),
    ("haitian", "Haitian"),
    ("thai", "Thai"),
    ("slovenian", "Slovenian"),
    ("russian", "Russian"),
    ("lithuanian", "Lithuanian"),
    ("amharic", "Amharic"),
    ("malay", "Malay"),
    ("estonian", "Estonian"),
    ("greek", "Greek"),
    ("ukrainian", "Ukrainian"),
    ("swahili", "Swahili"),
    ("japanese", "Japanese"),
    ("filipino", "Filipino"),
    ("persian", "Persian"),
    ("welsh", "Welsh"),
    ("korean", "Korean"),
    ("cantonese", "Cantonese"),
    ("indonesian", "Indonesian"),
    ("latin", "Latin"),
    ("bengali", "Bengali"),
    ("catalan", "Catalan"),
    ("hindi", "Hindi"),
]

STATIC_CATEGORIES = [
    # id cập nhật khi mở discovery; name hiển thị
    ("", "All topics"),
]

PRICE_FILTERS = [
    ("", "All prices"),
    ("free", "Free"),
    ("paid", "Paid"),
    ("free-trial", "Free trial"),
]

TYPE_FILTERS = [
    ("", "All types"),
    ("private", "Private"),
    ("public", "Public"),
]

SORT_FILTERS = [
    ("trending", "Trending"),
    ("top", "Top"),
]

# membershipModel (từ JS Skool)
# Free=1, Paid subscription≈2/4, Freemium=3, OneTime=5, Tiers=…
MODEL_FREE = {0, 1, 3}


def data_dir() -> Path:
    d = Path(C.BASE) / "skool_discovery"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "courses.db"


def csv_path() -> Path:
    return data_dir() / "courses.csv"


def meta_path() -> Path:
    return data_dir() / "meta.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path()))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(con)
    return con


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id TEXT PRIMARY KEY,
            slug TEXT,
            display_name TEXT,
            description TEXT,
            language TEXT,
            topic TEXT,
            category_id TEXT,
            members INTEGER,
            price TEXT,
            price_amount INTEGER,
            price_currency TEXT,
            price_interval TEXT,
            membership_model INTEGER,
            price_kind TEXT,
            type_kind TEXT,
            sort_kind TEXT,
            url TEXT,
            logo_url TEXT,
            filter_language TEXT,
            filter_price TEXT,
            filter_type TEXT,
            filter_sort TEXT,
            filter_topic TEXT,
            first_seen_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_courses_slug ON courses(slug);
        CREATE INDEX IF NOT EXISTS idx_courses_lang ON courses(language);
        CREATE INDEX IF NOT EXISTS idx_courses_topic ON courses(topic);
        CREATE INDEX IF NOT EXISTS idx_courses_members ON courses(members);
        CREATE INDEX IF NOT EXISTS idx_courses_price_kind ON courses(price_kind);
        """
    )
    con.commit()


def format_price(display_price: Any, membership_model: Any) -> Tuple[str, Optional[int], str, str, str]:
    """
    Trả về (price_label, amount_cents, currency, interval, price_kind).
    Free → $0/tháng, kind Free.
    """
    model = membership_model
    try:
        model_i = int(model) if model is not None else None
    except (TypeError, ValueError):
        model_i = None

    raw = display_price
    data = None
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str) and raw.strip() and raw.strip().lower() not in ("null", "none"):
        try:
            data = json.loads(raw)
        except Exception:
            data = None

    if data and isinstance(data, dict) and data.get("amount") is not None:
        try:
            amount = int(data.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0
        currency = (data.get("currency") or "usd").upper()
        interval = (data.get("recurring_interval") or data.get("interval") or "month").lower()
        symbol = "$" if currency in ("USD", "") else f"{currency} "
        major = amount / 100.0
        if major == int(major):
            money = f"{symbol}{int(major)}"
        else:
            money = f"{symbol}{major:.2f}"
        if interval in ("month", "monthly"):
            label = f"{money}/tháng"
            iv = "month"
        elif interval in ("year", "yearly", "annual"):
            label = f"{money}/năm"
            iv = "year"
        elif interval in ("one_time", "onetime", "once"):
            label = f"{money} (một lần)"
            iv = "one_time"
        else:
            label = f"{money}/{interval}"
            iv = interval
        kind = "Free" if amount == 0 else "Paid"
        if model_i in MODEL_FREE and amount == 0:
            kind = "Free"
        return label, amount, currency or "USD", iv, kind

    # Không có displayPrice → free
    if model_i in MODEL_FREE or model_i is None or not data:
        return "$0/tháng", 0, "USD", "month", "Free"
    return "$0/tháng", 0, "USD", "month", "Free"


def normalize_group(
    item: dict,
    *,
    language: str = "all",
    topic: str = "",
    category_id: str = "",
    filter_price: str = "",
    filter_type: str = "",
    filter_sort: str = "trending",
) -> Optional[dict]:
    if not item:
        return None
    g = item.get("group") if isinstance(item, dict) and "group" in item else item
    if not isinstance(g, dict):
        return None
    md = g.get("metadata") or {}
    if not isinstance(md, dict):
        md = {}
    gid = str(g.get("id") or "").strip()
    slug = (g.get("name") or "").strip()
    if not gid and not slug:
        return None
    if not gid:
        gid = slug
    display = (md.get("displayName") or slug or gid).strip()
    desc = (md.get("description") or "").strip()
    try:
        members = int(md.get("totalMembers") or 0)
    except (TypeError, ValueError):
        members = 0
    model = md.get("membershipModel")
    try:
        model_i = int(model) if model is not None else None
    except (TypeError, ValueError):
        model_i = None
    price_label, amount, currency, interval, price_kind = format_price(
        md.get("displayPrice"), model_i
    )
    # Free trial: chỉ biết qua filter scrape (API không gắn flag rõ trên group)
    if filter_price == "free-trial":
        price_kind_store = "Free trial"
    else:
        price_kind_store = price_kind

    lang_label = language if language and language != "all" else (language or "all")
    type_kind = filter_type or ""
    topic_label = topic or ""
    return {
        "id": gid,
        "slug": slug,
        "display_name": display,
        "description": desc,
        "language": lang_label,
        "topic": topic_label,
        "category_id": category_id or "",
        "members": members,
        "price": price_label,
        "price_amount": amount if amount is not None else 0,
        "price_currency": currency or "USD",
        "price_interval": interval or "month",
        "membership_model": model_i,
        "price_kind": price_kind_store,
        "type_kind": type_kind,
        "sort_kind": filter_sort or "trending",
        "url": f"https://www.skool.com/{slug}" if slug else "",
        "logo_url": (md.get("logoUrl") or md.get("coverSmallUrl") or "") or "",
        "filter_language": language or "all",
        "filter_price": filter_price or "",
        "filter_type": filter_type or "",
        "filter_sort": filter_sort or "trending",
        "filter_topic": topic_label,
        "updated_at": _now(),
    }


def upsert_courses(rows: Iterable[dict]) -> int:
    rows = [r for r in rows if r]
    if not rows:
        return 0
    con = connect()
    n = 0
    try:
        for r in rows:
            existing = con.execute(
                "SELECT first_seen_at FROM courses WHERE id = ?", (r["id"],)
            ).fetchone()
            first = (existing["first_seen_at"] if existing else None) or r.get("updated_at") or _now()
            con.execute(
                """
                INSERT INTO courses (
                    id, slug, display_name, description, language, topic, category_id,
                    members, price, price_amount, price_currency, price_interval,
                    membership_model, price_kind, type_kind, sort_kind, url, logo_url,
                    filter_language, filter_price, filter_type, filter_sort, filter_topic,
                    first_seen_at, updated_at
                ) VALUES (
                    :id, :slug, :display_name, :description, :language, :topic, :category_id,
                    :members, :price, :price_amount, :price_currency, :price_interval,
                    :membership_model, :price_kind, :type_kind, :sort_kind, :url, :logo_url,
                    :filter_language, :filter_price, :filter_type, :filter_sort, :filter_topic,
                    :first_seen_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    slug=excluded.slug,
                    display_name=excluded.display_name,
                    description=excluded.description,
                    language=CASE
                        WHEN excluded.language IS NOT NULL AND excluded.language != '' AND excluded.language != 'all'
                        THEN excluded.language ELSE courses.language END,
                    topic=CASE
                        WHEN excluded.topic IS NOT NULL AND excluded.topic != ''
                        THEN excluded.topic ELSE courses.topic END,
                    category_id=CASE
                        WHEN excluded.category_id IS NOT NULL AND excluded.category_id != ''
                        THEN excluded.category_id ELSE courses.category_id END,
                    members=excluded.members,
                    price=excluded.price,
                    price_amount=excluded.price_amount,
                    price_currency=excluded.price_currency,
                    price_interval=excluded.price_interval,
                    membership_model=excluded.membership_model,
                    price_kind=excluded.price_kind,
                    type_kind=CASE
                        WHEN excluded.type_kind IS NOT NULL AND excluded.type_kind != ''
                        THEN excluded.type_kind ELSE courses.type_kind END,
                    sort_kind=excluded.sort_kind,
                    url=excluded.url,
                    logo_url=excluded.logo_url,
                    filter_language=excluded.filter_language,
                    filter_price=excluded.filter_price,
                    filter_type=excluded.filter_type,
                    filter_sort=excluded.filter_sort,
                    filter_topic=excluded.filter_topic,
                    updated_at=excluded.updated_at
                """,
                {**r, "first_seen_at": first},
            )
            n += 1
        con.commit()
    finally:
        con.close()
    return n


def export_csv(path: Optional[Path] = None) -> Path:
    path = path or csv_path()
    con = connect()
    try:
        cur = con.execute(
            """
            SELECT display_name, slug, language, topic, members, price, price_kind,
                   type_kind, sort_kind, url, description, filter_language, filter_price,
                   filter_type, filter_sort, filter_topic, membership_model, updated_at, id
            FROM courses
            ORDER BY members DESC, display_name COLLATE NOCASE
            """
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in rows:
            w.writerow([row[c] for c in cols])
    return path


def count_courses() -> int:
    con = connect()
    try:
        return int(con.execute("SELECT COUNT(*) FROM courses").fetchone()[0])
    finally:
        con.close()


def query_courses(
    *,
    q: str = "",
    language: str = "",
    topic: str = "",
    price_kind: str = "",
    type_kind: str = "",
    limit: int = 500,
    offset: int = 0,
    order: str = "members",
) -> List[dict]:
    clauses = []
    args: list = []
    if q:
        clauses.append(
            "(display_name LIKE ? OR slug LIKE ? OR description LIKE ? OR topic LIKE ?)"
        )
        like = f"%{q}%"
        args.extend([like, like, like, like])
    if language and language not in ("", "all", "All"):
        clauses.append("language LIKE ?")
        args.append(f"%{language}%")
    if topic and topic not in ("", "All", "All topics"):
        clauses.append("topic LIKE ?")
        args.append(f"%{topic}%")
    if price_kind and price_kind not in ("", "All", "All prices"):
        clauses.append("price_kind = ?")
        args.append(price_kind)
    if type_kind and type_kind not in ("", "All", "All types"):
        clauses.append("type_kind = ?")
        args.append(type_kind)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    order_sql = {
        "members": "members DESC, display_name COLLATE NOCASE",
        "name": "display_name COLLATE NOCASE",
        "price": "price_amount ASC, display_name COLLATE NOCASE",
        "updated": "updated_at DESC",
    }.get(order, "members DESC, display_name COLLATE NOCASE")
    sql = f"SELECT * FROM courses{where} ORDER BY {order_sql} LIMIT ? OFFSET ?"
    args.extend([int(limit), int(offset)])
    con = connect()
    try:
        rows = con.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def save_meta(meta: dict) -> None:
    path = meta_path()
    old = {}
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    old.update(meta)
    old["saved_at"] = _now()
    path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")


def load_meta() -> dict:
    path = meta_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def languages_for_ui() -> List[Tuple[str, str]]:
    meta = load_meta()
    langs = meta.get("languages")
    if isinstance(langs, list) and langs:
        out = [("all", "All")]
        for L in langs:
            if isinstance(L, dict):
                name = (L.get("name") or "").lower()
                disp = L.get("displayName") or L.get("name") or name
                if name:
                    out.append((name, disp))
            elif isinstance(L, (list, tuple)) and len(L) >= 2:
                out.append((str(L[0]), str(L[1])))
        # unique
        seen = set()
        uniq = []
        for k, v in out:
            if k in seen:
                continue
            seen.add(k)
            uniq.append((k, v))
        return uniq
    return list(STATIC_LANGUAGES)


def categories_for_ui() -> List[Tuple[str, str]]:
    meta = load_meta()
    cats = meta.get("categories")
    out = [("", "All topics")]
    if isinstance(cats, list):
        for c in cats:
            if isinstance(c, dict) and c.get("id"):
                out.append((str(c["id"]), str(c.get("name") or c["id"])))
    return out if len(out) > 1 else list(STATIC_CATEGORIES)


def build_query(
    *,
    page: int = 1,
    language: str = "all",
    price: str = "",
    type_kind: str = "",
    sort: str = "trending",
    category_id: str = "",
) -> dict:
    q: Dict[str, Any] = {"p": max(1, int(page))}
    if language:
        q["lang"] = language
    if price:
        q["pr"] = price
    if type_kind:
        q["ty"] = type_kind
    if sort:
        q["srt"] = sort
    if category_id:
        q["c"] = category_id
    return q


class DiscoveryScraper:
    """Scrape discovery qua Playwright (headless). Có thể stop an toàn."""

    def __init__(self, delay: float = DEFAULT_DELAY, headless: bool = True):
        self.delay = max(0.1, float(delay))
        self.headless = headless
        self._stop = threading.Event()
        self._browser = None
        self._page = None
        self._pw = None
        self.build_id: Optional[str] = None
        self.categories: List[dict] = []
        self.languages: List[dict] = []

    def stop(self) -> None:
        self._stop.set()

    def stopped(self) -> bool:
        return self._stop.is_set()

    def _log(self, cb: Optional[Callable], msg: str) -> None:
        if cb:
            try:
                cb(msg)
            except Exception:
                pass

    def open(self) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        ctx = self._browser.new_context(user_agent=UA, locale="en-US")
        self._page = ctx.new_page()
        # WAF có thể navigate nhiều lần — retry + bắt lỗi context destroyed
        last_err = None
        info = None
        for attempt in range(4):
            if self.stopped():
                return
            try:
                self._page.goto(
                    "https://www.skool.com/discovery",
                    wait_until="domcontentloaded",
                    timeout=90000,
                )
                # chờ WAF / __NEXT_DATA__
                for _ in range(25):
                    if self.stopped():
                        return
                    try:
                        has = self._page.evaluate(
                            "() => !!document.getElementById('__NEXT_DATA__')"
                        )
                    except Exception as e:
                        last_err = e
                        # navigation giữa chừng (WAF challenge)
                        self._page.wait_for_timeout(1200)
                        continue
                    if has:
                        break
                    self._page.wait_for_timeout(800)
                try:
                    info = self._page.evaluate(
                        """() => {
                          const el = document.getElementById('__NEXT_DATA__');
                          if (!el) return null;
                          const d = JSON.parse(el.textContent);
                          const pp = d.props.pageProps || {};
                          return {
                            buildId: d.buildId,
                            categories: pp.categories || [],
                            languages: pp.languages || [],
                            numGroups: pp.numGroups
                          };
                        }"""
                    )
                except Exception as e:
                    last_err = e
                    info = None
                if info and info.get("buildId"):
                    break
                self._page.wait_for_timeout(1500)
            except Exception as e:
                last_err = e
                self._page.wait_for_timeout(1500)
        if not info or not info.get("buildId"):
            raise RuntimeError(
                "Không lấy được trang Discovery (WAF/network). "
                f"Thử lại hoặc --headed. Chi tiết: {last_err}"
            )
        self.build_id = info.get("buildId")
        self.categories = info.get("categories") or []
        self.languages = info.get("languages") or []
        save_meta(
            {
                "build_id": self.build_id,
                "categories": self.categories,
                "languages": self.languages,
                "num_groups_sample": info.get("numGroups"),
            }
        )

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._page = None
        self._pw = None

    def fetch_page(self, query: dict) -> dict:
        """Trả về pageProps dict (groups, numGroups, …)."""
        if not self._page or not self.build_id:
            raise RuntimeError("Scraper chưa open()")
        qs = urlencode({k: v for k, v in query.items() if v is not None and v != ""})
        path = f"/_next/data/{self.build_id}/discovery.json?{qs}"
        last_err = None
        for _ in range(3):
            try:
                result = self._page.evaluate(
                    """async (path) => {
                      try {
                        const res = await fetch(path, {headers: {'x-nextjs-data': '1'}});
                        if (!res.ok) {
                          return {ok: false, status: res.status, groups: [], numGroups: 0};
                        }
                        const j = await res.json();
                        return {ok: true, status: res.status, ...(j.pageProps || {})};
                      } catch (e) {
                        return {ok: false, status: 0, error: String(e), groups: [], numGroups: 0};
                      }
                    }""",
                    path,
                )
                return result or {"ok": False, "groups": [], "numGroups": 0}
            except Exception as e:
                last_err = e
                try:
                    self._page.wait_for_timeout(800)
                except Exception:
                    pass
        return {
            "ok": False,
            "status": 0,
            "error": str(last_err),
            "groups": [],
            "numGroups": 0,
        }

    def scrape_filter(
        self,
        *,
        language: str = "all",
        price: str = "",
        type_kind: str = "",
        sort: str = "trending",
        category_id: str = "",
        topic_name: str = "",
        max_pages: int = 200,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """
        Cào hết page cho 1 bộ filter. Upsert DB.
        """
        total_rows = 0
        pages_ok = 0
        pages_empty = 0
        topic = topic_name
        if not topic and category_id:
            for c in self.categories:
                if str(c.get("id")) == str(category_id):
                    topic = c.get("name") or ""
                    break

        for page in range(1, max_pages + 1):
            if self.stopped():
                self._log(on_progress, "⏹ Đã dừng theo yêu cầu.")
                break
            q = build_query(
                page=page,
                language=language or "all",
                price=price or "",
                type_kind=type_kind or "",
                sort=sort or "trending",
                category_id=category_id or "",
            )
            data = self.fetch_page(q)
            if not data.get("ok"):
                # top sort đôi khi 500 — bỏ qua
                self._log(
                    on_progress,
                    f"⚠ page {page} lỗi status={data.get('status')} {data.get('error') or ''}".strip(),
                )
                if page == 1 and (sort or "") == "top":
                    self._log(on_progress, "→ Thử lại với sort=trending…")
                    sort = "trending"
                    continue
                pages_empty += 1
                if pages_empty >= 2:
                    break
                time.sleep(self.delay)
                continue

            groups = data.get("groups") or []
            num = data.get("numGroups")
            if not groups:
                self._log(
                    on_progress,
                    f"· page {page}: hết dữ liệu (numGroups={num})",
                )
                break

            rows = []
            for item in groups:
                row = normalize_group(
                    item,
                    language=language or "all",
                    topic=topic or "",
                    category_id=category_id or "",
                    filter_price=price or "",
                    filter_type=type_kind or "",
                    filter_sort=sort or "trending",
                )
                if row:
                    rows.append(row)
            n = upsert_courses(rows)
            total_rows += n
            pages_ok += 1
            pages_empty = 0
            self._log(
                on_progress,
                f"· page {page}: +{n} khóa (num≈{num}, lang={language or 'all'}, "
                f"topic={topic or 'All'}, pr={price or 'all'}, ty={type_kind or 'all'})",
            )
            if len(groups) < PAGE_SIZE:
                break
            # numGroups cap ~1000 → ~34 pages
            if num and page * PAGE_SIZE >= int(num) and len(groups) < PAGE_SIZE:
                break
            time.sleep(self.delay)

        export_csv()
        return {
            "pages": pages_ok,
            "upserted": total_rows,
            "db_total": count_courses(),
            "csv": str(csv_path()),
        }

    def scrape_combo(
        self,
        *,
        languages: Optional[List[str]] = None,
        category_ids: Optional[List[Optional[str]]] = None,
        prices: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        sort: str = "trending",
        max_pages: int = 200,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """
        Cào nhiều tổ hợp filter.
        languages=None → ['all']
        category_ids=None → [''] (all topics)
        prices=None → ['']
        types=None → ['']
        """
        langs = languages if languages is not None else ["all"]
        cats = category_ids if category_ids is not None else [""]
        prs = prices if prices is not None else [""]
        tys = types if types is not None else [""]
        cat_map = {str(c.get("id")): c.get("name") or "" for c in (self.categories or [])}

        summary = {"combos": 0, "upserted": 0, "errors": 0}
        for lang in langs:
            for cat in cats:
                for pr in prs:
                    for ty in tys:
                        if self.stopped():
                            self._log(on_progress, "⏹ Dừng.")
                            summary["db_total"] = count_courses()
                            summary["csv"] = str(csv_path())
                            return summary
                        cat_id = cat or ""
                        topic = cat_map.get(str(cat_id), "") if cat_id else ""
                        self._log(
                            on_progress,
                            f"▶ Cào lang={lang} topic={topic or 'All'} "
                            f"price={pr or 'all'} type={ty or 'all'} sort={sort}",
                        )
                        try:
                            r = self.scrape_filter(
                                language=lang or "all",
                                price=pr or "",
                                type_kind=ty or "",
                                sort=sort or "trending",
                                category_id=cat_id,
                                topic_name=topic,
                                max_pages=max_pages,
                                on_progress=on_progress,
                            )
                            summary["combos"] += 1
                            summary["upserted"] += int(r.get("upserted") or 0)
                        except Exception as e:
                            summary["errors"] += 1
                            self._log(on_progress, f"[lỗi combo] {e}")
        export_csv()
        summary["db_total"] = count_courses()
        summary["csv"] = str(csv_path())
        save_meta({"last_scrape": summary, "last_scrape_at": _now()})
        return summary


def run_scrape(
    mode: str = "filter",
    *,
    language: str = "all",
    price: str = "",
    type_kind: str = "",
    sort: str = "trending",
    category_id: str = "",
    all_languages: bool = False,
    all_topics: bool = False,
    max_pages: int = 200,
    delay: float = DEFAULT_DELAY,
    headless: bool = True,
    on_progress: Optional[Callable[[str], None]] = None,
    stop_event: Optional[threading.Event] = None,
) -> dict:
    """
    Entry point cho GUI / CLI.
    mode=filter: 1 bộ filter hiện tại
    mode=full: quét ngôn ngữ × chủ đề (và optional price/type đang chọn)
    """
    sc = DiscoveryScraper(delay=delay, headless=headless)
    if stop_event is not None:
        # poll stop_event
        def _watch():
            while not sc.stopped():
                if stop_event.is_set():
                    sc.stop()
                    break
                time.sleep(0.2)

        threading.Thread(target=_watch, daemon=True).start()

    try:
        sc.open()
        if on_progress:
            on_progress(
                f"Discovery OK — buildId={sc.build_id}, "
                f"{len(sc.categories)} topics, {len(sc.languages)} languages"
            )
        if mode == "full" or all_languages or all_topics:
            langs = (
                [L.get("name") for L in sc.languages if L.get("name")]
                if all_languages
                else [language or "all"]
            )
            if not langs:
                langs = ["all"]
            cats: List[Optional[str]]
            if all_topics:
                cats = [""] + [c.get("id") for c in sc.categories if c.get("id")]
            else:
                cats = [category_id or ""]
            return sc.scrape_combo(
                languages=langs,
                category_ids=cats,
                prices=[price or ""],
                types=[type_kind or ""],
                sort=sort or "trending",
                max_pages=max_pages,
                on_progress=on_progress,
            )
        return sc.scrape_filter(
            language=language or "all",
            price=price or "",
            type_kind=type_kind or "",
            sort=sort or "trending",
            category_id=category_id or "",
            max_pages=max_pages,
            on_progress=on_progress,
        )
    finally:
        sc.close()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Skool Discovery scraper")
    ap.add_argument("--mode", choices=["filter", "full"], default="filter")
    ap.add_argument("--lang", default="all")
    ap.add_argument("--price", default="", help="free|paid|free-trial")
    ap.add_argument("--type", dest="type_kind", default="", help="private|public")
    ap.add_argument("--sort", default="trending")
    ap.add_argument("--category", default="")
    ap.add_argument("--all-languages", action="store_true")
    ap.add_argument("--all-topics", action="store_true")
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    def _p(m):
        print(m, flush=True)

    r = run_scrape(
        mode=args.mode,
        language=args.lang,
        price=args.price,
        type_kind=args.type_kind,
        sort=args.sort,
        category_id=args.category,
        all_languages=args.all_languages,
        all_topics=args.all_topics,
        max_pages=args.max_pages,
        headless=not args.headed,
        on_progress=_p,
    )
    print("RESULT", r)
    print("DB", db_path(), "rows", count_courses())
    print("CSV", csv_path())
