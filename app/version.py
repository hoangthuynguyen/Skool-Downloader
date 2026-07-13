"""Phien ban Skool Archiver (Phase ship)."""
__version__ = "1.9.0"
__codename__ = "fail-ux"

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
)


def version_string():
    return f"Skool Archiver {__version__} ({__codename__})"
