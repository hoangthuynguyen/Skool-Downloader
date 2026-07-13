#!/usr/bin/env bash
# Skool Archiver — launcher macOS/Linux (tuong duong start.ps1).
# Goi boi: ../SkoolArchiver.command  hoac  ./start.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"          # .../app
ROOT="$(cd "$HERE/.." && pwd)"                # .../Skool-Downloader (repo)

cd "$HERE"

has_gui() {
  local py="$1"
  [ -x "$py" ] || return 1
  "$py" -c "import customtkinter" 2>/dev/null
}

echo ""
echo "  ===== Skool Archiver ====="
echo "  Dang kiem tra moi truong..."

# 1) Tim Python co customtkinter
PY=""
for c in \
  "$HERE/venv/bin/python" \
  "$HERE/venv/bin/python3" \
  "$ROOT/../whisper/venv/bin/python" \
  "$ROOT/../whisper/venv/bin/python3"
do
  if has_gui "$c"; then PY="$c"; break; fi
done

# system python
if [ -z "$PY" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && has_gui "$(command -v "$c")"; then
      PY="$(command -v "$c")"
      break
    fi
  done
fi

# 2) Chua co → tao venv + cai requirements
if [ -z "$PY" ]; then
  echo ""
  echo "  Lan dau tren may nay — dang CAI DAT (can mang, co the vai phut)..."
  SYS=""
  if command -v python3 >/dev/null 2>&1; then SYS=python3
  elif command -v python >/dev/null 2>&1; then SYS=python
  fi
  if [ -z "$SYS" ]; then
    echo "  [!] Chua cai Python 3.11+."
    echo "      macOS:  brew install python"
    echo "      hoac:  https://www.python.org/downloads/"
    if command -v osascript >/dev/null 2>&1; then
      osascript -e 'display dialog "Chưa cài Python 3.11+.\n\nCài bằng: brew install python\nhoặc python.org — rồi mở lại SkoolArchiver." buttons {"OK"} default button 1 with title "Skool Archiver"'
    fi
    exit 1
  fi
  VENV="$HERE/venv"
  if [ ! -x "$VENV/bin/python" ] && [ ! -x "$VENV/bin/python3" ]; then
    echo "  Tao moi truong ao (venv)..."
    "$SYS" -m venv "$VENV"
  fi
  VPY="$VENV/bin/python3"
  [ -x "$VPY" ] || VPY="$VENV/bin/python"
  echo "  Nang pip..."
  "$VPY" -m pip install --upgrade pip --quiet
  echo "  Cai thu vien (customtkinter, yt-dlp, ... )..."
  "$VPY" -m pip install -r "$HERE/requirements.txt"
  echo "  (tuychon) playwright chromium..."
  "$VPY" -m playwright install chromium 2>/dev/null || echo "  (playwright: cai sau khi can)"
  if has_gui "$VPY"; then
    PY="$VPY"
    echo "  Cai dat xong!"
  else
    echo "  [!] Cai xong nhung thieu customtkinter — xem log tren."
    exit 1
  fi
fi

# 3) Mo GUI
echo "  Dang mo giao dien..."
echo "  Python: $PY"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
# macOS: mo trong process rieng de co the dong Terminal neu muon
if [[ "$(uname -s)" == "Darwin" ]]; then
  # nohup de khong bi kill khi dong terminal cua .command (tuy chon)
  nohup "$PY" gui.py >/tmp/skool-archiver-gui.log 2>&1 &
  sleep 0.6
  # neu fail ngay, hien log
  if ! kill -0 $! 2>/dev/null; then
    echo "  [!] GUI khong chay. Log: /tmp/skool-archiver-gui.log"
    tail -30 /tmp/skool-archiver-gui.log 2>/dev/null || true
    exit 1
  fi
  echo "  Da mo app (log: /tmp/skool-archiver-gui.log)."
else
  exec "$PY" gui.py
fi
