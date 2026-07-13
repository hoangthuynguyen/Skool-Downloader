"""
Google Drive upload (Phase 2).

Hai che do:
  1) Service Account — file JSON + folder_id (share folder cho email SA).
  2) OAuth user — client_secrets.json (Desktop) + token luu local.

Can: pip install google-api-python-client google-auth google-auth-oauthlib
"""
from __future__ import annotations

import json
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
HERE = Path(__file__).resolve().parents[1]
TOKEN_FILE = HERE / ".gdrive_token.json"


def _have_libs():
    try:
        import google.auth  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
        return True
    except Exception:
        return False


def missing_deps_msg():
    return ("Thiếu thư viện Google Drive. Chạy:\n"
            "  pip install google-api-python-client google-auth google-auth-oauthlib")


def _service_from_cfg(cfg):
    """cfg = cloud.gdrive dict."""
    if not _have_libs():
        raise RuntimeError(missing_deps_msg())
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    mode = (cfg.get("auth") or "service_account").lower()
    if mode == "service_account":
        sa = (cfg.get("service_account_json") or "").strip()
        if not sa or not Path(sa).exists():
            raise RuntimeError("Chưa có service_account_json (đường dẫn file JSON).")
        creds = service_account.Credentials.from_service_account_file(sa, scopes=SCOPES)
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    # OAuth user
    secrets = (cfg.get("client_secrets_json") or "").strip()
    if not secrets or not Path(secrets).exists():
        raise RuntimeError("Chưa có client_secrets_json (OAuth Desktop client).")
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def test_connection(cfg):
    try:
        svc = _service_from_cfg(cfg)
        folder_id = (cfg.get("folder_id") or "").strip()
        if folder_id:
            f = svc.files().get(fileId=folder_id, fields="id,name",
                                supportsAllDrives=True).execute()
            return True, f"OK — folder «{f.get('name')}» ({f.get('id')})"
        about = svc.about().get(fields="user").execute()
        email = (about.get("user") or {}).get("emailAddress") or "?"
        return True, f"OK — đăng nhập {email} (chưa set folder_id → upload vào My Drive root)"
    except Exception as e:
        return False, str(e)


def _find_child(svc, parent_id, name):
    q = (f"name = '{name.replace(chr(39), chr(92)+chr(39))}' and "
         f"'{parent_id}' in parents and trashed = false")
    res = svc.files().list(q=q, spaces="drive", fields="files(id,name)",
                           pageSize=5, supportsAllDrives=True,
                           includeItemsFromAllDrives=True).execute()
    files = res.get("files") or []
    return files[0]["id"] if files else None


def ensure_folder(svc, parent_id, name):
    existing = _find_child(svc, parent_id, name) if parent_id else None
    if existing:
        return existing
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    f = svc.files().create(body=meta, fields="id", supportsAllDrives=True).execute()
    return f["id"]


def ensure_path(svc, root_folder_id, parts):
    """Tao cay folder theo parts; tra ve folder id cuoi."""
    cur = root_folder_id or "root"
    for p in parts:
        if not p or p in (".",):
            continue
        cur = ensure_folder(svc, cur, p)
    return cur


def upload_file(cfg, local_path, rel_path, course_name="course"):
    """Upload 1 file. rel_path relative trong khoa. Tra ve drive file id."""
    from googleapiclient.http import MediaFileUpload

    svc = _service_from_cfg(cfg)
    root_id = (cfg.get("folder_id") or "").strip() or "root"
    local_path = Path(local_path)
    rel = Path(str(rel_path).replace("\\", "/"))
    # courses/<course>/<rel dirs>
    folder_parts = ["courses", course_name or "SkoolCourse"] + list(rel.parent.parts)
    if str(rel.parent) in (".", ""):
        folder_parts = ["courses", course_name or "SkoolCourse"]
    parent = ensure_path(svc, root_id, folder_parts)
    name = rel.name

    existing = _find_child(svc, parent, name)
    media = MediaFileUpload(str(local_path), resumable=True)
    if existing:
        f = svc.files().update(fileId=existing, media_body=media,
                               supportsAllDrives=True).execute()
        return f.get("id") or existing
    meta = {"name": name, "parents": [parent]}
    f = svc.files().create(body=meta, media_body=media, fields="id",
                           supportsAllDrives=True).execute()
    return f.get("id")
