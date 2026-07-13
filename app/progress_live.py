#!/usr/bin/env python3
"""
Sprint O / 2.15 — doc _download_progress.json de hien ETA + chi tiet bai live tren GUI.
"""
from __future__ import annotations

import json
from pathlib import Path


def progress_path(root) -> Path:
    return Path(root) / "_download_progress.json"


def read_download_progress(root):
    """Tra ve dict progress hoac None."""
    p = progress_path(root)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def format_eta_line(data) -> str:
    if not data:
        return ""
    done = data.get("done") or 0
    total = data.get("total") or 0
    eta = data.get("eta") or ""
    st = data.get("status") or "running"
    w = data.get("workers") or 1
    tai = data.get("tai")
    loi = data.get("loi")
    parts = [f"{done}/{total}"]
    if eta:
        parts.append(str(eta))
    if w and int(w) > 1:
        parts.append(f"w={w}")
    if tai is not None:
        parts.append(f"ok={tai}")
    if loi:
        parts.append(f"fail={loi}")
    parts.append(st)
    return " · ".join(parts)


def progress_fraction(data) -> float:
    if not data:
        return 0.0
    total = data.get("total") or 0
    done = data.get("done") or 0
    if total <= 0:
        return 0.0
    return min(1.0, max(0.0, done / total))


def short_path(path, max_len=64) -> str:
    s = str(path or "")
    if len(s) <= max_len:
        return s
    return "…" + s[-(max_len - 1):]


def state_label(state: str) -> str:
    s = (state or "").lower()
    return {
        "ok": "✓ Xong",
        "skip": "↷ Bỏ qua",
        "dry": "· Dry",
        "fail": "✗ Lỗi",
        "downloading": "⏳ Đang tải",
        "pending": "• Chờ",
        "done": "✓ Xong",
        "stopped": "■ Dừng",
        "running": "⏳ Đang chạy",
    }.get(s, s or "?")


def format_detail_lines(data) -> list[str]:
    """Cac dong mo ta cho panel UI: khoa, folder, video, bai hien tai."""
    if not data:
        return []
    lines = []
    course = data.get("course") or ""
    root = data.get("root") or ""
    done = data.get("done") or 0
    total = data.get("total") or 0
    pending = data.get("pending")
    if pending is None:
        pending = max(0, total - done)
    tai = data.get("tai")
    skip = data.get("skip")
    loi = data.get("loi")
    st = data.get("status") or ""
    lines.append(f"Khóa: {course or '(?)'}")
    if root:
        lines.append(f"Folder: {short_path(root, 72)}")
    parts = [f"Video: {done}/{total}"]
    if pending:
        parts.append(f"chờ {pending}")
    if tai is not None:
        parts.append(f"ok {tai}")
    if skip:
        parts.append(f"skip {skip}")
    if loi:
        parts.append(f"fail {loi}")
    parts.append(state_label(st))
    lines.append(" · ".join(parts))
    cur = data.get("current") or {}
    if cur:
        ch = cur.get("chapter") or ""
        les = cur.get("lesson") or cur.get("folder_name") or ""
        stc = state_label(cur.get("state") or "downloading")
        if ch or les:
            lines.append(f"Bài: [{ch}] {les}  —  {stc}" if ch else f"Bài: {les}  —  {stc}")
            if cur.get("folder"):
                lines.append(f"  ↳ {short_path(cur.get('folder'), 70)}")
    eta = data.get("eta") or ""
    if eta:
        lines.append(eta)
    return lines


def status_buckets(data):
    """Tra ve (done_items, active_items, pending_items) de ve UI list."""
    if not data:
        return [], [], []
    recent = list(data.get("recent") or [])
    current = data.get("current") or {}
    pending = list(data.get("pending_preview") or [])
    done_items = [r for r in recent if (r.get("state") or "") in ("ok", "skip", "dry")]
    fail_items = [r for r in recent if (r.get("state") or "") == "fail"]
    active = []
    if current and (current.get("state") or "") == "downloading":
        active = [current]
    elif data.get("status") == "running" and current and current not in done_items:
        if (current.get("state") or "") not in ("ok", "skip", "dry", "fail"):
            active = [current]
    return done_items[-8:], active + fail_items[-3:], pending[:8]
