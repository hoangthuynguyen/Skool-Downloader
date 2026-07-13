"""Phien ban Skool Archiver (Phase ship)."""
__version__ = "2.3.0"
__codename__ = "ui-v2.3"

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
)


def version_string():
    return f"Skool Archiver {__version__} ({__codename__})"
