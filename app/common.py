import json, os, re, socket, sys, time
from pathlib import Path
import config as C

def setup_console():
    """Ep stdout/stderr sang UTF-8 de in ten folder co ky tu la (vd '▶') khong crash
       tren Windows (console mac dinh cp1252). Goi 1 lan o dau chuong trinh."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def ensure_tool_path():
    """Bo sung PATH cho node/ffmpeg khi mo tu Finder/.app (PATH mac dinh thieu Homebrew).

    Goi som o gui.py / main.py / start.sh. Idempotent.
    """
    extra = []
    # Homebrew (Apple Silicon + Intel)
    for d in ("/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", "/usr/local/sbin"):
        if Path(d).is_dir():
            extra.append(d)
    # nvm (neu co ban active)
    nvm = Path.home() / ".nvm" / "versions" / "node"
    if nvm.is_dir():
        try:
            versions = sorted(nvm.iterdir(), key=lambda p: p.name, reverse=True)
            for v in versions:
                b = v / "bin"
                if (b / "node").exists() or (b / "node.exe").exists():
                    extra.append(str(b))
                    break
        except Exception:
            pass
    # ffmpeg-downloader user install
    for d in (
        Path.home() / "Library" / "Application Support" / "ffmpeg-downloader" / "ffmpeg",
        Path.home() / "AppData" / "Local" / "ffmpeg-downloader" / "ffmpeg",
    ):
        if d.is_dir():
            extra.append(str(d))
    # fnm / volta / asdf common
    for d in (
        Path.home() / ".fnm" / "current" / "bin",
        Path.home() / ".volta" / "bin",
        Path.home() / ".local" / "bin",
    ):
        if d.is_dir():
            extra.append(str(d))
    cur = os.environ.get("PATH") or ""
    parts = [p for p in cur.split(os.pathsep) if p]
    for d in reversed(extra):
        if d not in parts:
            parts.insert(0, d)
    os.environ["PATH"] = os.pathsep.join(parts)
    return os.environ["PATH"]


# Tu dong khi import (GUI/pipeline deu huong loi)
try:
    ensure_tool_path()
except Exception:
    pass

EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
                   "\u2190-\u21FF\u2B00-\u2BFF\u2300-\u23FF\uFE0F\u200D]")

def san(s):
    s = s or ""
    if C.STRIP_EMOJI: s = EMOJI.sub("", s)
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "", s)
    s = re.sub(r"\s+", " ", s).strip()[:120]
    return s.rstrip(" .") or "untitled"

def san_file(name):
    name = name or "file"
    if C.STRIP_EMOJI: name = EMOJI.sub("", name)
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:150].rstrip(" .") or "file"

def one_chapter(roots):
    if not roots: return {"title": "", "children": []}   # file vid_*.json rong ([]) -> bo qua an toan
    withkids = [r for r in roots if r.get("children")]
    main = withkids[0] if withkids else roots[0]
    for e in [r for r in roots if r is not main]:
        main.setdefault("children", []).append(e)
    return main

def walk(nodes, base, lessons=None):
    if lessons is None: lessons = []
    for i, n in enumerate(nodes, 1):
        folder = base / f"{i:02d} - {san(n['title'])}"
        kids = n.get("children") or []
        if kids: walk(kids, folder, lessons)
        else: lessons.append((folder, n))
    return lessons

def find_chapter_folder(ctitle):
    if not C.ROOT.exists(): return None
    for d in sorted([p for p in C.ROOT.iterdir() if p.is_dir()]):
        nm = d.name.split(" - ", 1)[-1] if " - " in d.name else d.name
        if nm == ctitle: return d
    return None

def chapter_order_map(root=None):
    """{ten_chuong_san: stt 1-based} tu _chapters.json / folder 'NN - ...' / ten file meta__NN_."""
    root = Path(root) if root is not None else Path(C.DUMP_ROOT or C.ROOT or ".")
    order = {}
    # 1) _chapters.json (thu tu chuan Skool dump)
    for nm in ("_chapters.json", "_chapters.txt"):
        p = root / nm
        if not p.exists():
            continue
        try:
            if nm.endswith(".json"):
                arr = json.loads(p.read_bytes().decode("utf-8-sig"))
                titles = [san(x["title"] if isinstance(x, dict) else x) for x in arr]
            else:
                titles = [san(t) for t in p.read_text(encoding="utf-8-sig").splitlines() if t.strip()]
            for i, t in enumerate(titles, 1):
                order.setdefault(t, i)
            if order:
                return order
        except Exception:
            pass
    # 2) folder "01 - Ten"
    try:
        for d in root.iterdir():
            if not d.is_dir() or d.name.startswith(("_", ".")):
                continue
            m = re.match(r"^\s*(\d+)\s*-\s*(.+)$", d.name)
            if m:
                order.setdefault(san(m.group(2)), int(m.group(1)))
    except Exception:
        pass
    # 3) meta__01_Ten.json / vid__01_Ten.json
    for f in list(root.glob("meta__*.json")) + list(root.glob("vid__*.json")):
        m = re.match(r"^(?:meta|vid)__(\d+)_(.+)\.json$", f.name, re.I)
        if not m:
            continue
        # ten file da san_file; van map so
        order.setdefault(san(m.group(2).replace("_", " ")), int(m.group(1)))
    return order


def chapter_sort_key(title, order_map=None, folder_name=None):
    """Key sap xep: stt trong order_map / so prefix folder / ten."""
    t = san(title or "")
    om = order_map if order_map is not None else chapter_order_map()
    if t in om:
        return (0, om[t], t.lower())
    # thu ten goc (chua san)
    raw = (title or "").strip()
    if raw in om:
        return (0, om[raw], t.lower())
    if folder_name:
        m = re.match(r"^\s*(\d+)\s*-", folder_name)
        if m:
            return (0, int(m.group(1)), t.lower())
    m2 = re.match(r"^\s*(\d+)\s*-", raw)
    if m2:
        return (0, int(m2.group(1)), t.lower())
    return (1, 10**9, t.lower())


def sort_chapter_titles(titles, root=None):
    om = chapter_order_map(root)
    return sorted(titles, key=lambda t: chapter_sort_key(t, om))


def load_best(pattern, score_fn):
    """Doc tat ca file khop pattern (de quy duoi DUMP_ROOT cua khoa), loai trung lap:
       moi chuong giu ban diem cao nhat. Tra ve list (ctitle, path, course_root)
       theo thu tu 1,2,3... (_chapters.json / so folder)."""
    best = {}
    for f in sorted(C.DUMP_ROOT.rglob(pattern)):
        try:
            d = json.loads(f.read_bytes().decode("utf-8-sig"))
        except Exception as e:
            print(f"[skip] {f.name}: {e}"); continue
        if isinstance(d, dict): d = [d]
        course = one_chapter(d); ct = san(course["title"])
        sc = score_fn(course.get("children") or [])
        if ct not in best or sc > best[ct][0]:
            best[ct] = (sc, f, course)
    om = chapter_order_map(C.DUMP_ROOT)
    return sorted(
        [(ct, v[1], v[2]) for ct, v in best.items()],
        key=lambda it: chapter_sort_key(it[0], om),
    )

# ---- mang ----
def online():
    try: socket.create_connection(("1.1.1.1", 53), timeout=4).close()
    except OSError: return False
    try: socket.gethostbyname("www.youtube.com"); return True
    except OSError: return False

def wait_online():
    if online(): return
    print("   [MANG] Mat ket noi - tam dung, cho mang...", flush=True)
    t = 0
    while not online():
        time.sleep(10); t += 10
        if t % 60 == 0: print(f"   [MANG] Van chua co mang... ({t}s)", flush=True)
    print("   [MANG] Co mang lai - tiep tuc.", flush=True)

def _first_existing(*cands):
    for c in cands:
        if not c:
            continue
        p = Path(c)
        if p.is_file():
            return str(p)
    return None


def node_bin():
    """Duong dan node (JS runtime cho yt-dlp/YouTube), hoac None."""
    import shutil
    try:
        ensure_tool_path()
    except Exception:
        pass
    w = shutil.which("node")
    if w:
        return w
    # nvm latest
    nvm = Path.home() / ".nvm" / "versions" / "node"
    nvm_node = None
    if nvm.is_dir():
        try:
            for v in sorted(nvm.iterdir(), key=lambda p: p.name, reverse=True):
                cand = v / "bin" / "node"
                if cand.is_file():
                    nvm_node = str(cand)
                    break
        except Exception:
            pass
    return _first_existing(
        nvm_node,
        "/opt/homebrew/bin/node",
        "/usr/local/bin/node",
        str(Path.home() / ".volta" / "bin" / "node"),
        str(Path.home() / ".local" / "bin" / "node"),
        r"C:\Program Files\nodejs\node.exe",
    )


def ffmpeg_bin():
    """Duong dan executable ffmpeg, hoac None."""
    import shutil
    try:
        ensure_tool_path()
    except Exception:
        pass
    # 1) ffmpeg-downloader (cai trong user data — hoat dong ca khi PATH thieu)
    try:
        import ffmpeg_downloader as ffdl
        p = getattr(ffdl, "ffmpeg_path", None)
        if p and Path(p).is_file():
            return str(Path(p))
        if callable(getattr(ffdl, "installed", None)) and ffdl.installed():
            try:
                from ffmpeg_downloader._path import get_dir
                cand = Path(get_dir()) / "ffmpeg" / "ffmpeg"
                if cand.is_file():
                    return str(cand)
            except Exception:
                pass
            for cand in (
                Path.home() / "AppData" / "Local" / "ffmpeg-downloader" / "ffmpeg" / "ffmpeg.exe",
                Path.home() / "Library" / "Application Support" / "ffmpeg-downloader" / "ffmpeg" / "ffmpeg",
            ):
                if cand.is_file():
                    return str(cand)
    except Exception:
        pass
    # 2) PATH (da ensure_tool_path)
    w = shutil.which("ffmpeg")
    if w:
        return w
    # 3) vi tri mac dinh
    return _first_existing(
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    )


def ffmpeg_dir():
    """Thu muc chua binary ffmpeg (de yt-dlp --ffmpeg-location), hoac None."""
    b = ffmpeg_bin()
    if b:
        return str(Path(b).parent)
    return None

# ---- tao + danh so folder chuong (cho khoa moi chua co folder nao) ----
def _existing_chapter_max():
    """So thu tu lon nhat trong cac folder chuong dang co (de danh so chuong moi tiep theo)."""
    mx = 0
    if not C.ROOT.exists(): return 0
    for d in C.ROOT.iterdir():
        if d.is_dir():
            m = re.match(r"\s*(\d+)\s*-", d.name)
            if m: mx = max(mx, int(m.group(1)))
    return mx

def load_chapter_order():
    """Thu tu chuong de danh so {ten chuong (da san) -> so}. Uu tien:
       1) file _chapters.json / _chapters.txt do extractor xuat (1 ten chuong / dong, dung thu tu)
       2) so trong ten file Chap<N>.json  (Chap1_.. -> chuong 1)
       3) {} (se danh so theo thu tu phat hien)."""
    # 1) _chapters.json / .txt
    for nm in ("_chapters.json", "_chapters.txt"):
        p = C.DUMP_ROOT / nm
        if p.exists():
            try:
                if nm.endswith(".json"):
                    arr = json.loads(p.read_bytes().decode("utf-8-sig"))
                    titles = [san(x["title"] if isinstance(x, dict) else x) for x in arr]
                else:
                    titles = [san(t) for t in p.read_text(encoding="utf-8-sig").splitlines() if t.strip()]
                return {t: i for i, t in enumerate(titles, 1)}
            except Exception:
                pass
    # 2) Chap<N>_*.json
    order = {}
    for f in sorted(C.DUMP_ROOT.rglob(C.CHAP_PATTERN)):
        m = re.search(r"Chap(\d+)", f.name)
        if not m: continue
        try:
            d = json.loads(f.read_bytes().decode("utf-8-sig"))
            if isinstance(d, dict): d = [d]
            ct = san(one_chapter(d)["title"])
            order.setdefault(ct, int(m.group(1)))
        except Exception:
            pass
    return order

def ensure_chapter_folder(ctitle, order):
    """Tra ve folder chuong; tao moi neu chua co (danh so theo order hoac tiep noi so lon nhat)."""
    chap = find_chapter_folder(ctitle)
    if chap is not None:
        return chap, False
    num = order.get(ctitle)
    if num is None:
        num = _existing_chapter_max() + 1
    chap = C.ROOT / f"{num:02d} - {ctitle}"
    chap.mkdir(parents=True, exist_ok=True)
    return chap, True