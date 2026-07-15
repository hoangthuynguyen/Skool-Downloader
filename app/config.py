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
# Mac dinh: sau khi tai video se tu chay faster-whisper -> video.txt (+ .srt)
# va ghi file tong hop "all transcript.txt" o goc khoa (thu tu bai 1→cuoi).
# Tat bang --no-transcribe, GUI bo tick, hoac settings auto_transcribe=false.
AUTO_TRANSCRIBE = True
ALL_TRANSCRIPT_NAME = "all transcript.txt"  # file tong hop o C.ROOT
WHISPER_ENGINE = "faster-whisper"
WHISPER_MODEL = "distil-large-v3"
# "auto" = Whisper tu detect ngon ngu video; hoac "en"/"vi"/...
WHISPER_LANG = "auto"
WHISPER_TASK = "transcribe"
WHISPER_DEVICE = "auto"
WHISPER_COMPUTE = "int8"
# Ghep description.md (gioi thieu bai) vao video.txt + all transcript.txt
TRANSCRIPT_INCLUDE_INTRO = True
WATCH_INTERVAL = 90
WATCH_MIN_AGE = 60

VIDEXT = (".mp4", ".webm", ".mkv", ".mov")

# ===================== TAI BAI / NOI DUNG BO SUNG =====================
# Mac dinh: tai thumbnail bai + ghi link resources. Tat bang GUI / settings / --no-*.
DOWNLOAD_THUMBNAILS = True
FETCH_RESOURCE_LINKS = True

# ===================== LESSON SUMMARY (LLM, VI) =====================
# Mac dinh BẬT — sau khi tai+transcript co the chay summary.vi.md tung bai.
# Tat: GUI bo tick, settings auto_lesson_summary=false, CLI --no-lesson-summary.
AUTO_LESSON_SUMMARY = True
# LLM mac dinh cho summary (co the doi trong GUI / settings)
LESSON_SUMMARY_PROVIDER = "deepseek"          # DeepSeek (chat / V3+)
LESSON_SUMMARY_MODEL = "deepseek-chat"
LESSON_SUMMARY_FALLBACK = ["gemini"]          # Gemini Flash
LESSON_SUMMARY_FALLBACK_MODEL = "gemini-2.0-flash"

# ===================== COURSE UPGRADE / MARKET RESEARCH =====================
# Nghiên cứu cập nhật khóa (web + LLM) → report DOCX → cấu trúc khóa mới.
# as_of = ngày mở/chạy phần mềm (date.today()).
COURSE_UPGRADE_RESEARCH = True       # bật nghiên cứu thị trường (có thể tắt)
COURSE_UPGRADE_WEB = True            # gọi web snippets (DuckDuckGo HTML)
# Trước research: hỏi user câu hỏi bổ sung mong muốn cập nhật (mặc định BẬT)
COURSE_UPGRADE_QUESTIONNAIRE = True

# ===================== COURSE STUDIO (v2 content factory) =====================
# Ngôn ngữ master khi sinh bài / script (vi | en)
COURSE_MASTER_LANG = "vi"
# Sinh full asset pack (script, workshop, use cases…) mặc định BẬT khi generate lessons
COURSE_ASSET_PACK = True
# Locales mặc định cho hub (T1 commercial)
COURSE_LOCALES_DEFAULT = [
    "en", "vi", "zh-CN", "ja", "ko", "es", "pt-BR", "id", "hi", "fr", "de", "ar",
]
# Ước lượng chi phí LLM / khóa (USD) — course_ops budget
LLM_BUDGET_USD = 25.0


def _settings_bool(key: str, default: bool) -> bool:
    s = _read_settings()
    if key in s:
        return bool(s.get(key))
    return bool(default)


def _settings_set(key: str, value) -> None:
    s = _read_settings()
    s[key] = value
    try:
        _SETTINGS_FILE.write_text(
            json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def get_auto_transcribe() -> bool:
    """True neu can tu dong transcript (settings > config default)."""
    return _settings_bool("auto_transcribe", AUTO_TRANSCRIBE)


def set_auto_transcribe(on: bool) -> bool:
    _settings_set("auto_transcribe", bool(on))
    return bool(on)


def get_auto_lesson_summary() -> bool:
    return _settings_bool("auto_lesson_summary", AUTO_LESSON_SUMMARY)


def set_auto_lesson_summary(on: bool) -> bool:
    _settings_set("auto_lesson_summary", bool(on))
    return bool(on)


def get_download_thumbnails() -> bool:
    return _settings_bool("download_thumbnails", DOWNLOAD_THUMBNAILS)


def set_download_thumbnails(on: bool) -> bool:
    _settings_set("download_thumbnails", bool(on))
    return bool(on)


def get_fetch_resource_links() -> bool:
    return _settings_bool("fetch_resource_links", FETCH_RESOURCE_LINKS)


def set_fetch_resource_links(on: bool) -> bool:
    _settings_set("fetch_resource_links", bool(on))
    return bool(on)


def get_lesson_summary_llm() -> dict:
    """Cau hinh LLM chinh + fallback cho summary tung bai."""
    s = _read_settings()
    primary = (s.get("lesson_summary_provider") or LESSON_SUMMARY_PROVIDER or "deepseek").strip().lower()
    model = (s.get("lesson_summary_model") or LESSON_SUMMARY_MODEL or "deepseek-chat").strip()
    fb = s.get("lesson_summary_fallback")
    if isinstance(fb, str):
        fallback = [x.strip() for x in fb.split(",") if x.strip()]
    elif isinstance(fb, list):
        fallback = [str(x).strip() for x in fb if str(x).strip()]
    else:
        fallback = list(LESSON_SUMMARY_FALLBACK or ["gemini"])
    fb_model = (s.get("lesson_summary_fallback_model") or LESSON_SUMMARY_FALLBACK_MODEL or "gemini-2.0-flash").strip()
    return {
        "provider": primary,
        "model": model,
        "fallback": fallback,
        "fallback_model": fb_model,
    }


def set_lesson_summary_llm(provider=None, model=None, fallback=None, fallback_model=None) -> dict:
    s = _read_settings()
    if provider is not None:
        s["lesson_summary_provider"] = str(provider).strip().lower()
    if model is not None:
        s["lesson_summary_model"] = str(model).strip()
    if fallback is not None:
        if isinstance(fallback, str):
            s["lesson_summary_fallback"] = [x.strip() for x in fallback.split(",") if x.strip()]
        else:
            s["lesson_summary_fallback"] = list(fallback)
    if fallback_model is not None:
        s["lesson_summary_fallback_model"] = str(fallback_model).strip()
    try:
        _SETTINGS_FILE.write_text(
            json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
    return get_lesson_summary_llm()


def whisper_language_arg():
    """None = auto-detect; nguoc lai ma ngon ngu ISO (en, vi, ...)."""
    lang = (WHISPER_LANG or "auto").strip().lower()
    if lang in ("", "auto", "detect", "none", "null"):
        return None
    return lang


def get_course_upgrade_research() -> bool:
    return _settings_bool("course_upgrade_research", COURSE_UPGRADE_RESEARCH)


def set_course_upgrade_research(on: bool) -> bool:
    _settings_set("course_upgrade_research", bool(on))
    return bool(on)


def get_course_upgrade_web() -> bool:
    return _settings_bool("course_upgrade_web", COURSE_UPGRADE_WEB)


def set_course_upgrade_web(on: bool) -> bool:
    _settings_set("course_upgrade_web", bool(on))
    return bool(on)


def get_course_upgrade_questionnaire() -> bool:
    return _settings_bool("course_upgrade_questionnaire", COURSE_UPGRADE_QUESTIONNAIRE)


def set_course_upgrade_questionnaire(on: bool) -> bool:
    _settings_set("course_upgrade_questionnaire", bool(on))
    return bool(on)


def get_course_master_lang() -> str:
    s = _read_settings()
    lang = (s.get("course_master_lang") or COURSE_MASTER_LANG or "vi").strip().lower()
    if lang in ("vn", "vie", "vietnamese"):
        lang = "vi"
    if lang in ("eng", "english"):
        lang = "en"
    return lang if lang in ("vi", "en") else "vi"


def set_course_master_lang(lang: str) -> str:
    lang = (lang or "vi").strip().lower()
    if lang in ("vn", "vie", "vietnamese"):
        lang = "vi"
    if lang in ("eng", "english"):
        lang = "en"
    if lang not in ("vi", "en"):
        lang = "vi"
    _settings_set("course_master_lang", lang)
    return lang


def get_course_asset_pack() -> bool:
    return _settings_bool("course_asset_pack", COURSE_ASSET_PACK)


def set_course_asset_pack(on: bool) -> bool:
    _settings_set("course_asset_pack", bool(on))
    return bool(on)


def get_course_locales() -> list:
    s = _read_settings()
    raw = s.get("course_locales")
    if isinstance(raw, list) and raw:
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [x.strip() for x in raw.split(",") if x.strip()]
    return list(COURSE_LOCALES_DEFAULT)


def set_course_locales(locales) -> list:
    if isinstance(locales, str):
        items = [x.strip() for x in locales.split(",") if x.strip()]
    else:
        items = [str(x).strip() for x in (locales or []) if str(x).strip()]
    _settings_set("course_locales", items)
    return items


def parse_skool_course_url(url: str) -> dict:
    """
    Parse URL Skool → {slug, classroom_url, about_url, ok, error}.
    Chap nhan:
      https://www.skool.com/ten-khoa
      https://www.skool.com/ten-khoa/classroom
      https://www.skool.com/ten-khoa/classroom/xxxx
    """
    import re
    from urllib.parse import urlparse

    raw = (url or "").strip()
    if not raw:
        return {"ok": False, "error": "URL trống", "slug": "", "classroom_url": ""}
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw.lstrip("/")
    try:
        u = urlparse(raw)
    except Exception as e:
        return {"ok": False, "error": str(e), "slug": "", "classroom_url": ""}
    host = (u.netloc or "").lower()
    if "skool.com" not in host:
        return {"ok": False, "error": "URL phải là skool.com/…", "slug": "", "classroom_url": ""}
    parts = [p for p in (u.path or "").split("/") if p]
    skip = {"www", "settings", "@me", "discovery", "signin", "signup", "login"}
    slug = ""
    for p in parts:
        if p.lower() in skip:
            continue
        slug = p
        break
    if not slug:
        return {"ok": False, "error": "Không thấy tên khóa (slug) trong URL", "slug": "", "classroom_url": ""}
    classroom = f"https://www.skool.com/{slug}/classroom"
    return {
        "ok": True,
        "error": "",
        "slug": slug,
        "classroom_url": classroom,
        "about_url": f"https://www.skool.com/{slug}/about",
        "url": raw,
    }
