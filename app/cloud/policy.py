"""
Quy tac chon file de upload (knowledge vs full mirror).
"""
from pathlib import Path

# knowledge: van ban + tai lieu, KHONG video (tranh 170GB)
KNOWLEDGE_NAMES = {
    "description.md", "video.txt", "video.srt",
    "_TongHop.md", "_TongHop.vi.md", "_TomTat.md",
    "Transcript_VI.md", "PhuDe_SongNgu.srt",
    "_chapters.json", "video_audit.txt",
}
KNOWLEDGE_GLOBS = (
    "resources/*",
    "**/*.md",
    "**/*.txt",
    "**/*.srt",
)
SKIP_PARTS = {".rag", "__pycache__", ".git"}
SKIP_SUFFIXES = {".part", ".ytdl", ".temp", ".tmp"}
SKIP_NAMES = {".settings.json", "queue_state.json", "cookies.txt"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov"}


def should_upload(path: Path, root: Path, mode: str = "knowledge") -> bool:
    """path la file thuc; root la goc khoa."""
    path = Path(path)
    root = Path(root)
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    parts_lower = {p.lower() for p in rel.parts}
    if parts_lower & {s.lower() for s in SKIP_PARTS}:
        return False
    if path.name in SKIP_NAMES or path.name.startswith("."):
        # cho phep _TongHop / _TomTat (bat dau bang _)
        if not path.name.startswith("_"):
            return False
        if path.name in SKIP_NAMES:
            return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    # file dang tai do
    if path.name.endswith(".part") or ".part." in path.name:
        return False

    mode = (mode or "knowledge").lower()
    if mode == "full":
        # full: moi file hop le tru skip
        return path.is_file()

    # knowledge
    if path.name in KNOWLEDGE_NAMES:
        return True
    if path.suffix.lower() in VIDEO_SUFFIXES:
        return False
    # resources/*
    if "resources" in parts_lower:
        return path.is_file()
    # md/txt/srt bat ky (tru video.txt da cover)
    if path.suffix.lower() in {".md", ".txt", ".srt", ".json"}:
        # bo vid_/meta_ dump lon? van upload json dump de backup cau truc
        return True
    return False


def iter_upload_files(root: Path, mode: str = "knowledge"):
    root = Path(root)
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file() and should_upload(p, root, mode):
            yield p
