#!/usr/bin/env bash
# Skool Downloader — launcher macOS/Linux (tuong duong start.ps1).
# Goi boi: ../SkoolDownloader.command  hoac  ./start.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"          # .../app
ROOT="$(cd "$HERE/.." && pwd)"                # .../Skool-Downloader (repo)

cd "$HERE"

# True neu Python co customtkinter VA Tk khong bi treo (macOS CLT Python 3.9 hang).
has_gui() {
  local py="$1"
  [ -x "$py" ] || return 1
  # Reject Apple Command Line Tools Python — Tk/update hang, GUI khong hien.
  case "$(readlink "$py" 2>/dev/null || true) $(readlink -f "$py" 2>/dev/null || true) $py" in
    *CommandLineTools*|*Library/Developer/CommandLineTools*) return 1 ;;
  esac
  # realpath of venv python often points at CLT
  local real
  real="$(python_real_path "$py" 2>/dev/null || true)"
  case "$real" in
    *CommandLineTools*) return 1 ;;
  esac
  "$py" -c "import customtkinter, tkinter as tk; r=tk.Tk(); r.withdraw(); r.update_idletasks(); r.destroy()" 2>/dev/null
}

python_real_path() {
  local py="$1"
  "$py" -c "import sys; print(sys.executable)" 2>/dev/null
}

pick_system_python() {
  # uu tien Homebrew / python.org framework, tranh /usr/bin/python3 (CLT stub)
  local c
  for c in \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    "$HOME/.local/bin/python3" \
    python3 \
    python
  do
    if [[ "$c" == /* ]]; then
      [ -x "$c" ] || continue
      if has_gui "$c" || "$c" -c "import sys" 2>/dev/null; then
        # even without ctk yet, prefer homebrew for venv creation
        if [[ "$c" == *homebrew* ]] || [[ "$c" == *local* ]]; then
          echo "$c"; return 0
        fi
        # only accept if not CLT
        local real
        real="$("$c" -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
        case "$real" in
          *CommandLineTools*) continue ;;
        esac
        echo "$c"; return 0
      fi
    else
      if command -v "$c" >/dev/null 2>&1; then
        local p
        p="$(command -v "$c")"
        case "$p" in
          *CommandLineTools*) continue ;;
        esac
        # /usr/bin/python3 on macOS is often CLT — skip if real path is CLT
        local real
        real="$("$p" -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
        case "$real" in
          *CommandLineTools*) continue ;;
        esac
        echo "$p"; return 0
      fi
    fi
  done
  return 1
}

echo ""
echo "  ===== Skool Downloader ====="
echo "  Dang kiem tra moi truong..."

# 1) Tim Python co customtkinter (uu tien venv du an)
PY=""
for c in \
  "$HERE/venv/bin/python" \
  "$HERE/venv/bin/python3" \
  "$ROOT/../whisper/venv/bin/python" \
  "$ROOT/../whisper/venv/bin/python3" \
  /opt/homebrew/bin/python3 \
  /usr/local/bin/python3
do
  if has_gui "$c"; then PY="$c"; break; fi
done

# system python (co customtkinter)
if [ -z "$PY" ]; then
  for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 python; do
    if [[ "$c" == /* ]]; then
      if has_gui "$c"; then PY="$c"; break; fi
    elif command -v "$c" >/dev/null 2>&1 && has_gui "$(command -v "$c")"; then
      PY="$(command -v "$c")"
      break
    fi
  done
fi

# 2) Chua co → tao venv + cai requirements (dung Python TOT, khong CLT)
if [ -z "$PY" ]; then
  echo ""
  echo "  Lan dau tren may nay — dang CAI DAT (can mang, co the vai phut)..."
  SYS=""
  SYS="$(pick_system_python || true)"
  if [ -z "$SYS" ]; then
    echo "  [!] Chua co Python phu hop (can Python 3.11+ co Tk hoat dong)."
    echo "      macOS:  brew install python python-tk"
    echo "      hoac:  https://www.python.org/downloads/"
    echo "      LUU Y: khong dung Python cua Xcode Command Line Tools (Tk bi treo)."
    if command -v osascript >/dev/null 2>&1; then
      osascript -e 'display dialog "Chưa cài Python phù hợp (cần Tk hoạt động).\n\nCài: brew install python\nhoặc python.org — rồi mở lại SkoolDownloader.\n\nKhông dùng Python của Xcode CLT." buttons {"OK"} default button 1 with title "Skool Downloader"'
    fi
    exit 1
  fi
  VENV="$HERE/venv"
  # neu venv cu tro vao CLT — xoa de tao lai
  if [ -x "$VENV/bin/python" ] || [ -x "$VENV/bin/python3" ]; then
    OLD="$VENV/bin/python3"
    [ -x "$OLD" ] || OLD="$VENV/bin/python"
    if ! has_gui "$OLD"; then
      echo "  Venv cu (Python CLT/Tk hong) — tao lai..."
      rm -rf "$VENV"
    fi
  fi
  if [ ! -x "$VENV/bin/python" ] && [ ! -x "$VENV/bin/python3" ]; then
    echo "  Tao moi truong ao (venv) bang: $SYS"
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
    echo "  [!] Cai xong nhung GUI van khong chay duoc (Tk/customtkinter)."
    echo "      macOS: brew install python && xoa app/venv roi mo lai."
    exit 1
  fi
fi

# 3) Mo GUI
echo "  Dang mo giao dien..."
echo "  Python: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || true))"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
# macOS: mo trong process rieng de co the dong Terminal neu muon
if [[ "$(uname -s)" == "Darwin" ]]; then
  # nohup de khong bi kill khi dong terminal cua .command
  nohup "$PY" gui.py >/tmp/skool-downloader-gui.log 2>&1 &
  GPID=$!
  sleep 1.2
  # neu fail ngay, hien log
  if ! kill -0 "$GPID" 2>/dev/null; then
    echo "  [!] GUI khong chay. Log: /tmp/skool-downloader-gui.log"
    tail -40 /tmp/skool-downloader-gui.log 2>/dev/null || true
    exit 1
  fi
  # kiem tra process con song sau them 1s (crash cham)
  sleep 0.8
  if ! kill -0 "$GPID" 2>/dev/null; then
    echo "  [!] GUI thoat som. Log: /tmp/skool-downloader-gui.log"
    tail -40 /tmp/skool-downloader-gui.log 2>/dev/null || true
    exit 1
  fi
  echo "  Da mo app (log: /tmp/skool-downloader-gui.log)."
  echo "  Neu khong thay cua so: check Dock (Python) hoac mo lai sau khi cap quyen man hinh."
else
  exec "$PY" gui.py
fi
