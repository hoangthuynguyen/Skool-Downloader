#!/usr/bin/env bash
# Cai shortcut Desktop (+ Applications) de mo Skool Archiver bang 1 click (macOS/Linux).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
LAUNCHER="$ROOT/SkoolArchiver.command"
START_SH="$HERE/start.sh"

chmod +x "$LAUNCHER" "$START_SH" 2>/dev/null || true

# Dam bao .command co quyen execute (macOS Gatekeeper: lan dau co the can Right-click → Open)
chmod +x "$LAUNCHER"

DESKTOP="${HOME}/Desktop"
[ -d "$DESKTOP" ] || DESKTOP="${HOME}/Desktop"
# macOS Vietnamese locale
[ -d "${HOME}/Desktop" ] || true
if [ ! -d "$DESKTOP" ] && [ -d "${HOME}/Máy tính" ]; then
  DESKTOP="${HOME}/Máy tính"
fi
# Vietnamese "Desktop" folder name on some systems
if [ ! -d "$DESKTOP" ]; then
  for d in "${HOME}/Desktop" "${HOME}/desktop" "${HOME}/Bàn làm việc"; do
    [ -d "$d" ] && DESKTOP="$d" && break
  done
fi

NAME="Skool Archiver"
SHORT_CMD="${DESKTOP}/Skool Archiver.command"
SHORT_APP="${HOME}/Applications/Skool Archiver.app"

echo "===== Cai shortcut Skool Archiver ====="
echo "Repo: $ROOT"

# --- Desktop .command ---
if [ -d "$DESKTOP" ]; then
  cat > "$SHORT_CMD" <<EOF
#!/bin/bash
# Shortcut → Skool Archiver
cd "$ROOT" || exit 1
exec bash "$LAUNCHER"
EOF
  chmod +x "$SHORT_CMD"
  # Clear quarantine on macOS so double-click works more easily
  if command -v xattr >/dev/null 2>&1; then
    xattr -dr com.apple.quarantine "$SHORT_CMD" 2>/dev/null || true
    xattr -dr com.apple.quarantine "$LAUNCHER" 2>/dev/null || true
    xattr -dr com.apple.quarantine "$START_SH" 2>/dev/null || true
  fi
  echo "✓ Desktop: $SHORT_CMD"
else
  echo "! Khong thay thu muc Desktop — bo qua shortcut Desktop"
fi

# --- macOS: simple .app bundle in ~/Applications ---
if [[ "$(uname -s)" == "Darwin" ]]; then
  mkdir -p "${HOME}/Applications"
  APP_DIR="${HOME}/Applications/Skool Archiver.app"
  rm -rf "$APP_DIR"
  mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
  cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Skool Archiver</string>
  <key>CFBundleDisplayName</key><string>Skool Archiver</string>
  <key>CFBundleIdentifier</key><string>local.skool.archiver</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>SkoolArchiver</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
  cat > "$APP_DIR/Contents/MacOS/SkoolArchiver" <<EOF
#!/bin/bash
cd "$ROOT" || exit 1
exec bash "$ROOT/app/start.sh"
EOF
  chmod +x "$APP_DIR/Contents/MacOS/SkoolArchiver"
  xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null || true
  echo "✓ Applications: $APP_DIR"
  echo "  (Mo Launchpad / Finder → Applications → Skool Archiver)"
fi

# --- Linux .desktop ---
if [[ "$(uname -s)" == "Linux" ]] && [ -d "${HOME}/.local/share/applications" ] || [[ "$(uname -s)" == "Linux" ]]; then
  APP_DIR_L="${HOME}/.local/share/applications"
  mkdir -p "$APP_DIR_L"
  DESKTOP_FILE="${APP_DIR_L}/skool-archiver.desktop"
  cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Skool Archiver
Comment=Archive Skool courses offline
Exec=bash "$ROOT/app/start.sh"
Path=$ROOT/app
Terminal=false
Categories=Education;Utility;
EOF
  chmod +x "$DESKTOP_FILE"
  if [ -d "$DESKTOP" ]; then
    cp "$DESKTOP_FILE" "$DESKTOP/skool-archiver.desktop" 2>/dev/null || true
    chmod +x "$DESKTOP/skool-archiver.desktop" 2>/dev/null || true
  fi
  echo "✓ Linux desktop entry: $DESKTOP_FILE"
fi

echo ""
echo "Xong. Cach mo app:"
echo "  1) Double-click: Desktop → «Skool Archiver»"
echo "  2) Double-click: $LAUNCHER"
echo "  3) Terminal: bash \"$LAUNCHER\""
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "  4) App: ~/Applications/Skool Archiver.app"
  echo ""
  echo "Neu macOS bao 'khong mo duoc': chuot phai → Open (lan dau)."
fi
