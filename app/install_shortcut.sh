#!/usr/bin/env bash
# Cai shortcut Desktop (+ Applications) — Skool Downloader
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
LAUNCHER="$ROOT/SkoolDownloader.command"
START_SH="$HERE/start.sh"
chmod +x "$LAUNCHER" "$START_SH" "$ROOT/SkoolDownloader.command" 2>/dev/null || true

DESKTOP="${HOME}/Desktop"
for d in "${HOME}/Desktop" "${HOME}/desktop" "${HOME}/Bàn làm việc"; do
  [ -d "$d" ] && DESKTOP="$d" && break
done

echo "===== Cai shortcut Skool Downloader ====="
echo "Repo: $ROOT"

if [ -d "$DESKTOP" ]; then
  SHORT_CMD="${DESKTOP}/Skool Downloader.command"
  cat > "$SHORT_CMD" <<INNER
#!/bin/bash
cd "$ROOT" || exit 1
exec bash "$LAUNCHER"
INNER
  chmod +x "$SHORT_CMD"
  xattr -dr com.apple.quarantine "$SHORT_CMD" 2>/dev/null || true
  # remove legacy name (pre-rename)
  rm -f "${DESKTOP}/Skool Archiver.command" 2>/dev/null || true
  echo "✓ Desktop: $SHORT_CMD"
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  mkdir -p "${HOME}/Applications"
  # remove legacy name (pre-rename)
  rm -rf "${HOME}/Applications/Skool Archiver.app"
  APP_DIR="${HOME}/Applications/Skool Downloader.app"
  rm -rf "$APP_DIR"
  mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
  cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Skool Downloader</string>
  <key>CFBundleDisplayName</key><string>Skool Downloader</string>
  <key>CFBundleIdentifier</key><string>local.skool.downloader</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>SkoolDownloader</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
  cat > "$APP_DIR/Contents/MacOS/SkoolDownloader" <<INNER
#!/bin/bash
cd "$ROOT" || exit 1
exec bash "$ROOT/app/start.sh"
INNER
  chmod +x "$APP_DIR/Contents/MacOS/SkoolDownloader"
  xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null || true
  echo "✓ Applications: $APP_DIR"
fi

if [[ "$(uname -s)" == "Linux" ]]; then
  APP_DIR_L="${HOME}/.local/share/applications"
  mkdir -p "$APP_DIR_L"
  cat > "${APP_DIR_L}/skool-downloader.desktop" <<INNER
[Desktop Entry]
Type=Application
Name=Skool Downloader
Comment=Download and archive Skool courses offline
Exec=bash "$ROOT/app/start.sh"
Path=$ROOT/app
Terminal=false
Categories=Education;Utility;
INNER
  chmod +x "${APP_DIR_L}/skool-downloader.desktop"
  echo "✓ Linux: ${APP_DIR_L}/skool-downloader.desktop"
fi

echo ""
echo "Xong. Mo app: Desktop → «Skool Downloader»  hoac  $LAUNCHER"
