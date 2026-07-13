"""Phien ban Skool Archiver (Phase ship)."""
__version__ = "2.14.0"
__codename__ = "easy-launch"

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
)


def version_string():
    return f"Skool Archiver {__version__} ({__codename__})"
