"""
OneDrive upload via Microsoft Graph (Phase 3).

Auth: MSAL device-code (lan dau mo browser/code) hoac refresh_token da luu.
Can: pip install msal requests

Cau hinh cloud.onedrive:
  client_id   — Azure app (public client, personal/work)
  tenant      — "consumers" (ca nhan) | "common" | "organizations" | tenant id
  folder      — ten folder goc tren OneDrive (mac dinh SkoolDownloader)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
TOKEN_FILE = HERE / ".onedrive_token.json"
GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Files.ReadWrite", "User.Read", "offline_access"]


def _have_msal():
    try:
        import msal  # noqa: F401
        import requests  # noqa: F401
        return True
    except Exception:
        return False


def missing_deps_msg():
    return "Thiếu msal/requests. Chạy: pip install msal requests"


def _app(cfg):
    import msal
    client_id = (cfg.get("client_id") or "").strip()
    if not client_id:
        raise RuntimeError("Chưa có onedrive.client_id (Azure App registration — public client).")
    tenant = (cfg.get("tenant") or "consumers").strip()
    authority = f"https://login.microsoftonline.com/{tenant}"
    return msal.PublicClientApplication(client_id, authority=authority)


def _load_token():
    try:
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_token(data):
    TOKEN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_access_token(cfg, interactive=True, log=print):
    """Lay access_token; device code neu can dang nhap."""
    if not _have_msal():
        raise RuntimeError(missing_deps_msg())
    app = _app(cfg)
    cache = _load_token()
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result and cache.get("refresh_token"):
        result = app.acquire_token_by_refresh_token(cache["refresh_token"], scopes=SCOPES)
    if not result or "access_token" not in result:
        if not interactive:
            raise RuntimeError("Chưa đăng nhập OneDrive. Chạy Test kết nối (device code) một lần.")
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow lỗi: {flow}")
        msg = flow.get("message") or f"Mở {flow.get('verification_uri')} — code: {flow.get('user_code')}"
        log(msg)
        result = app.acquire_token_by_device_flow(flow)
    if not result or "access_token" not in result:
        raise RuntimeError(result.get("error_description") or result.get("error") or "Auth OneDrive thất bại")
    # luu refresh
    tok = {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token") or cache.get("refresh_token"),
        "expires_at": int(time.time()) + int(result.get("expires_in") or 3600) - 60,
    }
    _save_token(tok)
    return tok["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_connection(cfg, log=print):
    try:
        import requests
        token = get_access_token(cfg, interactive=True, log=log)
        r = requests.get(f"{GRAPH}/me", headers=_headers(token), timeout=30)
        if r.status_code != 200:
            return False, f"{r.status_code}: {r.text[:200]}"
        name = (r.json().get("displayName") or r.json().get("userPrincipalName") or "?")
        folder = (cfg.get("folder") or "SkoolDownloader").strip()
        return True, f"OK — OneDrive user «{name}» · folder root «{folder}»"
    except Exception as e:
        return False, str(e)


def _ensure_folder_path(token, parts):
    """Tao / me/drive/root:/a/b:/  tung cap. Tra ve item id folder cuoi."""
    import requests
    # bat dau tu root
    parent_id = "root"
    for name in parts:
        if not name or name in (".",):
            continue
        # list children
        if parent_id == "root":
            url = f"{GRAPH}/me/drive/root/children"
        else:
            url = f"{GRAPH}/me/drive/items/{parent_id}/children"
        r = requests.get(url, headers=_headers(token),
                         params={"$filter": f"name eq '{name.replace(chr(39), '')}'"},
                         timeout=60)
        found = None
        if r.status_code == 200:
            for it in (r.json().get("value") or []):
                if it.get("name") == name and "folder" in it:
                    found = it["id"]
                    break
        if found:
            parent_id = found
            continue
        # create
        if parent_id == "root":
            curl = f"{GRAPH}/me/drive/root/children"
        else:
            curl = f"{GRAPH}/me/drive/items/{parent_id}/children"
        body = {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
        cr = requests.post(curl, headers={**_headers(token), "Content-Type": "application/json"},
                           json=body, timeout=60)
        if cr.status_code in (200, 201):
            parent_id = cr.json()["id"]
        elif cr.status_code == 409:
            # race — list again
            r2 = requests.get(url, headers=_headers(token), timeout=60)
            for it in (r2.json().get("value") or []):
                if it.get("name") == name:
                    parent_id = it["id"]
                    break
            else:
                raise RuntimeError(f"Tạo folder OneDrive thất bại: {name} {cr.text[:200]}")
        else:
            raise RuntimeError(f"Tạo folder OneDrive: {cr.status_code} {cr.text[:200]}")
    return parent_id


def upload_file(cfg, local_path, rel_path, course_name="course", log=print):
    """Upload file (simple <4MB put, lon hon -> upload session). Tra ve drive item id."""
    import requests
    local_path = Path(local_path)
    token = get_access_token(cfg, interactive=False, log=log)
    root_folder = (cfg.get("folder") or "SkoolDownloader").strip() or "SkoolDownloader"
    rel = Path(str(rel_path).replace("\\", "/"))
    folder_parts = [root_folder, "courses", course_name or "SkoolCourse"] + list(rel.parent.parts)
    if str(rel.parent) in (".", ""):
        folder_parts = [root_folder, "courses", course_name or "SkoolCourse"]
    parent_id = _ensure_folder_path(token, folder_parts)
    name = rel.name
    size = local_path.stat().st_size

    # simple upload < 4 MiB
    if size < 4 * 1024 * 1024:
        url = f"{GRAPH}/me/drive/items/{parent_id}:/{name}:/content"
        with open(local_path, "rb") as f:
            r = requests.put(url, headers={**_headers(token),
                                           "Content-Type": "application/octet-stream"},
                             data=f, timeout=300)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"OneDrive upload {name}: {r.status_code} {r.text[:200]}")
        return r.json().get("id") or name

    # upload session for larger files
    url = f"{GRAPH}/me/drive/items/{parent_id}:/{name}:/createUploadSession"
    r = requests.post(url, headers={**_headers(token), "Content-Type": "application/json"},
                      json={"item": {"@microsoft.graph.conflictBehavior": "replace", "name": name}},
                      timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"createUploadSession: {r.status_code} {r.text[:200]}")
    upload_url = r.json()["uploadUrl"]
    chunk = 5 * 1024 * 1024
    with open(local_path, "rb") as f:
        start = 0
        while start < size:
            data = f.read(chunk)
            end = start + len(data) - 1
            headers = {
                "Content-Length": str(len(data)),
                "Content-Range": f"bytes {start}-{end}/{size}",
            }
            ur = requests.put(upload_url, headers=headers, data=data, timeout=600)
            if ur.status_code not in (200, 201, 202):
                raise RuntimeError(f"chunk upload: {ur.status_code} {ur.text[:200]}")
            start = end + 1
            if ur.status_code in (200, 201):
                return ur.json().get("id") or name
    return name
