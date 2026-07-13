"""Phien ban Skool Downloader (Phase ship)."""
__version__ = "2.17.0"
__codename__ = "discovery-scrape"

# Phase milestones (gan dung commit history)
HISTORY = (
    "1.0 dashboard/queue/rag",
    "1.2 parallel+gdrive+tfidf",
    "1.3 onedrive+search",
    "1.4 web+health",
    "1.5 static site+embed+tray",
    "1.6 smart BASE+doctor",
    "1.7 download reliability",
    "1.8 fail UX+cleanup",
    "1.9 version+selftest+dash fails",
    "1.9.1 health fails count + dash fail button",
    "2.0.0 UI v2 — sidebar, stat cards, accent theme",
    "2.1.0 dark mode + queue/chat/manager polish",
    "2.2.0 wizard dump + env check + remaining screens",
    "2.3.0 density compact/comfortable + doctor polish",
    "2.4.0 fail-driven retry + knowledge pack + auto-index",
    "2.5.0 smart update + search highlight + pack backup/restore",
    "2.6.0 parallel workers + notify + resume/BM + digests",
    "2.7.0 adaptive workers + ETA + smart-batch + anki + quiz",
    "2.8.0 live ETA + learn playlist + content diff + vault + fix",
    "2.9.0 notes + disk report + study ICS + dash download strip",
    "2.10.0 notes search + sync badge + favorites + shortcuts + alias",
    "2.11.0 LLM custom prompt translate/update (Claude + OpenAI-compat)",
    "2.12.0 multi-LLM: Gemini/OpenRouter/GLM/Qwen/Kimi/… + fallback chain",
    "2.13.0 Grok (xAI) provider + features/workflows user guide",
    "2.14.0 one-click launchers + Desktop shortcuts (macOS/Win/Linux)",
    "2.14.1 rename display name to Skool Downloader",
    "2.14.2 fix macOS GUI hang (CLT Tk) + full SkoolDownloader rename",
    "2.15.0 pick output folder + live download progress (course/folder/video/lesson)",
    "2.15.1 video stats on UI (size/host/status) + usage guide update",
    "2.15.2 Finder/.app PATH fix for node+ffmpeg + Downloads shortcut refresh",
    "2.15.3 robust Skool browser recover + better chapter list (no blank lessons)",
    "2.15.4 browser via storage_state (fix closed-page on list chapters)",
    "2.15.5 classroom UX: keep Chrome open, live URL, auto-list chapters",
    "2.15.6 show all lessons (not only with URL) + better video extract",
    "2.16.0 full lesson pack: description/links/resources/lesson.json per folder",
    "2.16.1 chapters sorted 1,2,3 from _chapters.json / folder numbers",
    "2.17.0 Discovery scrape: all pages/languages/topics → SQLite+CSV table",
)


def version_string():
    return f"Skool Downloader {__version__} ({__codename__})"
