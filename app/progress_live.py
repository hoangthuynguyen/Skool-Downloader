#!/usr/bin/env python3
"""
Sprint O — doc _download_progress.json de hien ETA live tren GUI.
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
