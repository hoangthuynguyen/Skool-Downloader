"""
Cau hinh trung tam cho Skool Downloader.

Mac dinh: layout 1-khoa cu  ->  BASE/SkoolCourse  (giu nguyen cho khoa da tai).
Khi chay  --course "Ten khoa"  ->  BASE/courses/Ten khoa/   (JSON dump + output deu o day).

Override (uu tien giam dan):
  1) bien moi truong SKOOL_BASE
  2) app/.settings.json -> "skool_base"
  3) tu dong: parent co courses/  (layout SkoolProject/Skool-Downloader)
     hoac chinh thu muc repo neu co courses/ ben trong
  4) fallback: parent cua repo (layout classic)
"""
import json
import os
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
_REPO_DIR = _APP_DIR.parent  # repo / Skool-Downloader
_SETTINGS_FILE = _APP_DIR / ".settings.json"


def _read_settings():
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_base():
    """Chon BASE thong minh — tuong thich may Windows (SkoolProject) va clone repo don."""
    env = (os.environ.get("SKOOL_BASE") or "").strip()
    if env:
        return Path(env).expanduser().resolve()

    s = _read_settings()
    saved = (s.get("skool_base") or "").strip()
    if saved:
        return Path(saved).expanduser().resolve()

    parent = _REPO_DIR.parent
    # Classic: .../SkoolProject/courses  +  .../SkoolProject/Skool-Downloader/app
    if (parent / "courses").is_dir() or (parent / "SkoolCourse").is_dir():
        return parent.resolve()
    # Repo-local: courses nam trong chinh repo
    if (_REPO_DIR / "courses").is_dir() or (_REPO_DIR / "SkoolCourse").is_dir():
        return _REPO_DIR.resolve()
    # Mac dinh classic (tao courses o canh Skool-Downloader)
    return parent.resolve()


# ===================== DUONG DAN =====================
BASE = resolve_base()

# Mac dinh = khoa cu (1 thu muc SkoolCourse). set_course()/set_root() se doi cac gia tri nay.
COURSE = None
ROOT = BASE / "SkoolCourse"
DUMP_ROOT = BASE


def set_base(path, persist=False):
    """Doi BASE runtime. persist=True -> ghi app/.settings.json."""
    global BASE, COURSE, ROOT, DUMP_ROOT
    BASE = Path(path).expanduser().resolve()
    COURSE = None
    ROOT = BASE / "SkoolCourse"
    DUMP_ROOT = BASE
    if persist:
        s = _read_settings()
        s["skool_base"] = str(BASE)
        _SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return BASE


def set_course(name: str):
    """Tro pipeline vao 1 khoa cu the duoi BASE/courses/<name>/."""
    global COURSE, ROOT, DUMP_ROOT
    COURSE = name
    ROOT = BASE / "courses" / name
    DUMP_ROOT = ROOT
    ROOT.mkdir(parents=True, exist_ok=True)


def set_root(path):
    """Override truc tiep thu muc lam viec (ca JSON lan output deu o day)."""
    global ROOT, DUMP_ROOT
    ROOT = Path(path)
    DUMP_ROOT = Path(path)


def base_info():
    """Mo ta nguon BASE (de doctor / GUI)."""
    env = (os.environ.get("SKOOL_BASE") or "").strip()
    if env:
        source = "env:SKOOL_BASE"
    elif (_read_settings().get("skool_base") or "").strip():
        source = "settings.json"
    elif (BASE / "courses").is_dir() or (BASE / "SkoolCourse").is_dir():
        source = "auto-detect"
    else:
        source = "default-parent"
    return {
        "base": str(BASE),
        "source": source,
        "archiver": str(_REPO_DIR),  # legacy key (doctor/GUI)
        "repo": str(_REPO_DIR),
        "courses": str(BASE / "courses"),
        "courses_exists": (BASE / "courses").is_dir(),
    }


# ===================== PATTERN JSON =====================
VID_PATTERN = "vid_*.json"
META_PATTERN = "meta_*.json"
CHAP_PATTERN = "Chap*.json"
STRIP_EMOJI = True

# ===================== VIDEO =====================
DRY_RUN = False
ONLY_HOSTS = []
ONLY_CHAPTER = None          # 1 chuong (ten da san)
ONLY_CHAPTERS = None         # set ten chuong (san) — multi-chapter delta
ONLY_LESSON = None
ONLY_FAILED = False          # True: chi tai lai folder co trong video_fails.json
ONLY_MISSING = False         # True: chi bai chua co video (smart update)
FAIL_CODES = None            # None = moi code; set(["rate","network"]) de loc
JS_RUNTIME = "node"
YT_COOKIES_FILE = ""
YT_COOKIES_BROWSER = ""
MAX_TRIES = 6
RETRY_WAIT = 8
VIDEO_WORKERS = 1            # Sprint E: so bai tai song song trong 1 khoa (1-4)
ADAPTIVE_WORKERS = True      # Sprint J: tu ha workers khi gap 429/rate-limit
AUTO_INDEX = True            # sau pipeline: build RAG index (catalog + tfidf)
NOTIFY_ON_DONE = True        # Sprint F: toast sau pipeline / het fail

# ===================== TRANSCRIBE =====================
WHISPER_ENGINE = "faster-whisper"
WHISPER_MODEL = "distil-large-v3"
WHISPER_LANG = "en"
WHISPER_TASK = "transcribe"
WHISPER_DEVICE = "auto"
WHISPER_COMPUTE = "int8"
WATCH_INTERVAL = 90
WATCH_MIN_AGE = 60

VIDEXT = (".mp4", ".webm", ".mkv", ".mov")
