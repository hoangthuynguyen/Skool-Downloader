#!/usr/bin/env python3
"""
Web knowledge viewer local (Phase 4) — chi stdlib, khong can Flask.

  python web_viewer.py                  # http://127.0.0.1:8765
  python web_viewer.py --port 9000
  python web_viewer.py --host 0.0.0.0   # LAN (can than: chi local knowledge)

Duyet khoa / chuong / bai (mo ta + transcript), tim kiem, xem health.
"""
from __future__ import annotations

import argparse, html, json, re, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as C
import progress as P
import search_lib as S
from rag.index import load_catalog

HOST_DEFAULT = "127.0.0.1"
PORT_DEFAULT = 8765


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _layout(title, body, q=""):
    return f"""<!DOCTYPE html>
<html lang="vi"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{_esc(title)} · Skool Downloader</title>
<style>
:root {{ --bg:#f4f4f5; --card:#fff; --text:#18181b; --muted:#71717a; --line:#e4e4e7; --pri:#111114; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family: ui-sans-serif, system-ui, Segoe UI, sans-serif;
  background:var(--bg); color:var(--text); line-height:1.5; -webkit-text-size-adjust:100%; }}
header {{ background:var(--pri); color:#fff; padding:12px 16px; display:flex; gap:12px;
  align-items:center; flex-wrap:wrap; position:sticky; top:0; z-index:20; }}
header a {{ color:#e4e4e7; text-decoration:none; font-size:14px; padding:4px 0; }}
header a:hover {{ color:#fff; }}
header .brand {{ font-weight:700; font-size:16px; margin-right:8px; color:#fff; }}
main {{ max-width:960px; margin:0 auto; padding:16px 14px 48px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:14px 16px; margin:10px 0; }}
.card h2, .card h3 {{ margin:0 0 6px; font-size:16px; }}
.muted {{ color:var(--muted); font-size:13px; }}
.badge {{ display:inline-block; font-size:12px; font-weight:600; padding:2px 8px;
  border-radius:999px; background:#ececee; }}
.search {{ display:flex; gap:8px; margin:0 0 0 auto; min-width:min(100%,280px); flex:1; }}
.search input {{ flex:1; padding:10px 12px; border:1px solid var(--line); border-radius:9px;
  font-size:16px; min-width:0; }}
.search button, .btn {{ padding:10px 14px; border:0; border-radius:9px; background:var(--pri);
  color:#fff; font-weight:600; cursor:pointer; font-size:13px; text-decoration:none;
  display:inline-block; min-height:44px; }}
pre, .body {{ white-space:pre-wrap; font-size:15px; background:#fafafa; padding:12px;
  border-radius:8px; border:1px solid var(--line); max-height:70vh; overflow:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ text-align:left; padding:10px 6px; border-bottom:1px solid var(--line); }}
a.link {{ color:var(--pri); font-weight:600; text-decoration:none; }}
a.link:hover {{ text-decoration:underline; }}
@media (max-width:640px) {{
  header {{ padding:10px 12px; }}
  main {{ padding:12px 10px 40px; }}
  table {{ font-size:12px; }}
  .search {{ margin:8px 0 0; width:100%; flex-basis:100%; }}
}}
</style>
<link rel="manifest" href="/manifest.webmanifest"/>
<meta name="theme-color" content="#111114"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
</head><body>
<header>
  <a class="brand" href="/">📦 Skool Downloader</a>
  <a href="/">Khóa học</a>
  <a href="/health">Health</a>
  <a href="/api/health">API</a>
  <form class="search" action="/search" method="get" style="margin:0 0 0 auto; min-width:240px;">
    <input name="q" value="{_esc(q)}" placeholder="Tìm transcript…"/>
    <button type="submit">Tìm</button>
  </form>
</header>
<main>{body}</main>
</body></html>"""


def list_courses_data():
    out = []
    for meta in P.list_course_items():
        try:
            s = P.scan(meta["root"])
            badge = P.status_badge(s)
        except Exception:
            s, badge = {}, {"label": "?"}
        out.append({
            "item": meta["item"],
            "course": meta["course"],
            "root": str(meta["root"]),
            "done": s.get("done") or 0,
            "total": s.get("total") or 0,
            "size": s.get("size") or 0,
            "badge": badge.get("label"),
        })
    return out


def course_root_by_key(key):
    """key = course name or 'legacy'."""
    key = unquote(key or "")
    if key in ("legacy", "SkoolCourse", "_legacy"):
        return C.BASE / "SkoolCourse", None
    p = C.BASE / "courses" / key
    if p.exists():
        return p, key
    # try match item display
    for meta in P.list_course_items():
        if meta["item"] == key or str(meta["course"]) == key:
            return meta["root"], meta["course"]
    return None, None


class Handler(BaseHTTPRequestHandler):
    server_version = "SkoolDownloaderWeb/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code, body, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False, indent=2),
                   "application/json; charset=utf-8")

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path or "/"
        qs = parse_qs(u.query)

        try:
            if path == "/":
                return self._home()
            if path == "/health":
                return self._health_page()
            if path == "/search":
                return self._search(qs.get("q", [""])[0])
            if path.startswith("/course/"):
                return self._course(path[len("/course/"):], qs)
            if path == "/api/courses":
                return self._json(list_courses_data())
            if path == "/api/health":
                import health_check as H
                return self._json(H.run_health())
            if path == "/api/search":
                q = qs.get("q", [""])[0]
                return self._json(S.search_all(q, top_k=int(qs.get("top", ["20"])[0] or 20)))
            if path == "/manifest.webmanifest":
                return self._send(200, json.dumps({
                    "name": "Skool Downloader",
                    "short_name": "Skool",
                    "start_url": "/",
                    "display": "standalone",
                    "background_color": "#f4f4f5",
                    "theme_color": "#111114",
                }), "application/manifest+json; charset=utf-8")
            self._send(404, _layout("404", f"<div class='card'><h2>404</h2><p>{_esc(path)}</p></div>"))
        except Exception as e:
            self._send(500, _layout("Lỗi", f"<div class='card'><h2>Lỗi</h2><pre>{_esc(e)}</pre></div>"))

    def _home(self):
        rows = []
        for c in list_courses_data():
            key = c["course"] or "legacy"
            href = "/course/" + quote(str(key), safe="")
            rows.append(
                f"<tr><td><a class='link' href='{href}'>{_esc(c['item'])}</a></td>"
                f"<td>{c['done']}/{c['total']}</td>"
                f"<td><span class='badge'>{_esc(c['badge'])}</span></td></tr>"
            )
        body = (
            "<h1>Kho khóa học</h1>"
            "<p class='muted'>Xem mô tả + lời giảng đã lưu trên máy (local only).</p>"
            "<div class='card'><table><thead><tr><th>Khóa</th><th>Tiến độ</th><th>Trạng thái</th></tr></thead>"
            f"<tbody>{''.join(rows) or '<tr><td colspan=3 class=muted>(trống)</td></tr>'}</tbody></table></div>"
        )
        self._send(200, _layout("Khóa học", body))

    def _health_page(self):
        import health_check as H
        r = H.run_health()
        sm = r["summary"]
        rows = []
        for c in r["courses"]:
            badge = (c.get("badge") or {}).get("label") if isinstance(c.get("badge"), dict) else ""
            rows.append(
                f"<tr><td>{_esc(c.get('item'))}</td><td>{c.get('done')}/{c.get('total')}</td>"
                f"<td>{c.get('missing')}</td><td>{c.get('expired')}</td>"
                f"<td>{_esc(badge)}</td></tr>"
            )
        body = (
            f"<h1>Health</h1><p class='muted'>{_esc(r.get('checked_at'))}</p>"
            f"<div class='card'><p><b>{sm['n_courses']}</b> khóa · "
            f"<b>{sm['done']}/{sm['total']}</b> bài · thiếu <b>{sm['missing']}</b> · "
            f"hết hạn <b>{sm['expired']}</b> · cần chú ý <b>{sm['needs_attention']}</b></p></div>"
            "<div class='card'><table><thead><tr><th>Khóa</th><th>Tiến độ</th><th>Thiếu</th>"
            "<th>Hết hạn</th><th>Badge</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
        self._send(200, _layout("Health", body))

    def _search(self, q):
        hits = S.search_all(q, top_k=30) if q.strip() else []
        items = []
        for h in hits:
            key = h.get("course") or "legacy"
            items.append(
                f"<div class='card'><h3><a class='link' href='/course/{_esc(key)}'>"
                f"[{_esc(h.get('course'))}] {_esc(h.get('chapter'))} / {_esc(h.get('title'))}</a></h3>"
                f"<p class='muted'>score={_esc(h.get('score'))} · {_esc(h.get('method'))}</p>"
                f"<p>{_esc(h.get('preview'))}</p></div>"
            )
        body = (
            f"<h1>Tìm: {_esc(q)}</h1>"
            f"<p class='muted'>{len(hits)} kết quả</p>"
            + ("".join(items) or "<div class='card muted'>Không có kết quả. Index RAG trước nếu mới tải.</div>")
        )
        self._send(200, _layout("Tìm kiếm", body, q=q))

    def _course(self, rest, qs):
        rest = rest.strip("/")
        parts = rest.split("/") if rest else []
        key = parts[0] if parts else ""
        root, course = course_root_by_key(key)
        if not root or not root.exists():
            self._send(404, _layout("404", f"<div class='card'>Không thấy khóa {_esc(key)}</div>"))
            return
        cat = load_catalog(root, full=True)
        lessons = cat.get("lessons") or []
        # lesson detail? ?i=N
        if "i" in qs:
            try:
                idx = int(qs["i"][0])
            except Exception:
                idx = -1
            if 0 <= idx < len(lessons):
                L = lessons[idx]
                body = (
                    f"<p><a class='link' href='/course/{_esc(key)}'>← {_esc(cat.get('course'))}</a></p>"
                    f"<h1>{_esc(L.get('title'))}</h1>"
                    f"<p class='muted'>{_esc(L.get('section') or L.get('chapter'))}</p>"
                    f"<div class='body'>{_esc(L.get('text') or '(trống)')}</div>"
                )
                self._send(200, _layout(L.get("title") or "Bài", body))
                return

        # group by chapter
        by_ch = {}
        for i, L in enumerate(lessons):
            ch = L.get("chapter") or "Khác"
            by_ch.setdefault(ch, []).append((i, L))
        blocks = [f"<h1>{_esc(cat.get('course') or key)}</h1>"
                  f"<p class='muted'>{len(lessons)} bài có text · {_esc(root)}</p>"]
        for ch, items in by_ch.items():
            lis = "".join(
                f"<li><a class='link' href='/course/{_esc(key)}?i={i}'>{_esc(L.get('title'))}</a>"
                f" <span class='muted'>({L.get('chars') or 0} ký tự)</span></li>"
                for i, L in items
            )
            blocks.append(f"<div class='card'><h2>{_esc(ch)}</h2><ul>{lis}</ul></div>")
        if not lessons:
            blocks.append("<div class='card muted'>Chưa có mô tả/transcript. Tải bài + tạo phụ đề, rồi Index RAG.</div>")
        self._send(200, _layout(cat.get("course") or key, "".join(blocks)))


def serve(host=HOST_DEFAULT, port=PORT_DEFAULT, open_browser=True):
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"Skool Downloader Web Viewer → {url}")
    print("Ctrl+C để dừng.")
    if open_browser and host in ("127.0.0.1", "localhost"):
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Local web knowledge viewer")
    ap.add_argument("--host", default=HOST_DEFAULT)
    ap.add_argument("--port", type=int, default=PORT_DEFAULT)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    serve(host=a.host, port=a.port, open_browser=not a.no_browser)


if __name__ == "__main__":
    main()
