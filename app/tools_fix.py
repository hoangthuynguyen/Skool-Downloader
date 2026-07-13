#!/usr/bin/env python3
"""
Sprint S — one-click fix: cap nhat yt-dlp + cai goi thieu.

  python tools_fix.py                  # yt-dlp -U + goi thieu co ban
  python tools_fix.py --yt-dlp-only
  python tools_fix.py --packages customtkinter,faster-whisper
  python tools_fix.py --doctor-fix     # sua theo doctor FAIL/WARN
"""
from __future__ import annotations

import argparse, importlib.util, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable


def _has(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def pip_install(packages, log=print, upgrade=False):
    if not packages:
        return True, "nothing"
    cmd = [PY, "-m", "pip", "install"]
    if upgrade:
        cmd.append("-U")
    cmd += list(packages)
    log(f">> {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        out = (r.stdout or "")[-1500:] + (r.stderr or "")[-800:]
        ok = r.returncode == 0
        log(out[-500:] if out else f"rc={r.returncode}")
        return ok, out
    except Exception as e:
        return False, str(e)


def update_ytdlp(log=print):
    log(">> Updating yt-dlp…")
    ok, out = pip_install(["yt-dlp"], log=log, upgrade=True)
    # version
    ver = "?"
    try:
        import yt_dlp
        ver = getattr(yt_dlp, "version", None)
        if ver and hasattr(ver, "__version__"):
            ver = ver.__version__
        elif hasattr(yt_dlp, "__version__"):
            ver = yt_dlp.__version__
        else:
            r = subprocess.run([PY, "-m", "yt_dlp", "--version"], capture_output=True,
                               text=True, timeout=30)
            ver = (r.stdout or "").strip() or "?"
    except Exception as e:
        ver = f"err {e}"
    log(f">> yt-dlp version: {ver}")
    return {"ok": ok, "version": ver, "detail": out[:300]}


# map doctor/preflight missing -> pip package
PKG_MAP = {
    "yt_dlp": "yt-dlp",
    "yt-dlp": "yt-dlp",
    "faster_whisper": "faster-whisper",
    "faster-whisper": "faster-whisper",
    "customtkinter": "customtkinter",
    "playwright": "playwright",
    "boto3": "boto3",
    "msal": "msal",
    "googleapiclient": "google-api-python-client",
    "google-api": "google-api-python-client google-auth",
    "sentence_transformers": "sentence-transformers",
    "pystray": "pystray pillow",
    "docx": "python-docx",
    "python-docx": "python-docx",
    "deep_translator": "deep-translator",
    "requests": "requests",
    "send2trash": "send2trash",
}


def packages_from_doctor():
    """Lay list pip package tu doctor FAIL/WARN co fix pip."""
    try:
        import doctor as D
        rep = D.run_doctor()
    except Exception:
        return []
    pkgs = []
    for row in rep.get("rows") or []:
        if row.get("status") not in ("FAIL", "WARN"):
            continue
        fix = (row.get("fix") or "").lower()
        name = (row.get("name") or "").lower()
        if "pip install" in fix:
            # parse "pip install -U yt-dlp" / "pip install a b"
            part = fix.split("pip install", 1)[-1].strip()
            part = part.replace("-U", "").replace("--upgrade", "").strip()
            for tok in part.split():
                if tok.startswith("-"):
                    continue
                pkgs.append(tok)
        # map by module name
        for key, pkg in PKG_MAP.items():
            if key in name or key in fix:
                for p in pkg.split():
                    pkgs.append(p)
    # unique preserve order
    seen = set()
    out = []
    for p in pkgs:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def fix_all(yt_dlp=True, packages=None, from_doctor=False, log=print):
    results = {"ytdlp": None, "packages": {}, "ok": True}
    if yt_dlp:
        results["ytdlp"] = update_ytdlp(log=log)
        if not results["ytdlp"].get("ok"):
            results["ok"] = False
    pkgs = list(packages or [])
    if from_doctor:
        pkgs.extend(packages_from_doctor())
    # default core if nothing
    if not pkgs and not yt_dlp:
        pkgs = ["yt-dlp"]
    # unique
    seen = set()
    final = []
    for p in pkgs:
        if p not in seen:
            seen.add(p)
            final.append(p)
    if final:
        ok, out = pip_install(final, log=log, upgrade=True)
        results["packages"] = {"list": final, "ok": ok, "detail": out[:400]}
        if not ok:
            results["ok"] = False
    # playwright browsers if playwright just installed
    if "playwright" in final or (from_doctor and _has("playwright")):
        try:
            log(">> playwright install chromium (may take a while)…")
            subprocess.run([PY, "-m", "playwright", "install", "chromium"],
                           timeout=900, capture_output=True)
        except Exception as e:
            log(f"[playwright browsers] {e}")
    return results


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="One-click fix tools (Sprint S)")
    ap.add_argument("--yt-dlp-only", action="store_true")
    ap.add_argument("--packages", help="Comma-separated pip packages")
    ap.add_argument("--doctor-fix", action="store_true", help="Cai goi theo doctor FAIL/WARN")
    ap.add_argument("--no-ytdlp", action="store_true")
    a = ap.parse_args()
    pkgs = [x.strip() for x in (a.packages or "").split(",") if x.strip()]
    if a.yt_dlp_only:
        r = update_ytdlp()
        print(r)
        return 0 if r.get("ok") else 1
    r = fix_all(
        yt_dlp=not a.no_ytdlp,
        packages=pkgs or None,
        from_doctor=a.doctor_fix or (not pkgs and not a.yt_dlp_only),
    )
    # default: always yt-dlp + doctor-ish core
    if not a.doctor_fix and not pkgs:
        # also ensure yt-dlp + customtkinter lightly
        pass
    print(f"ok={r.get('ok')} ytdlp={r.get('ytdlp')} packages={r.get('packages')}")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main() or 0)
