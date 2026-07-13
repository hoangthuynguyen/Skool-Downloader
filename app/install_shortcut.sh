#!/usr/bin/env bash
# Cai shortcut Desktop + Applications + Downloads — Skool Downloader
# Wrapper luon bo sung PATH (Homebrew/node/ffmpeg) de mo tu Finder khong bao "thieu".
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
LAUNCHER="$ROOT/SkoolDownloader.command"
START_SH="$HERE/start.sh"
chmod +x "$LAUNCHER" "$START_SH" "$ROOT/SkoolDownloader.command" 2>/dev/null || true

# Snippet bash: PATH bootstrap (dung chung cho .command / .app)
path_bootstrap() {
  cat <<'BOOT'
# PATH bootstrap — Finder macOS chi co /usr/bin:/bin
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"
if [ -d "${HOME}/.nvm/versions/node" ]; then
  _nvm_bin="$(ls -1d "${HOME}/.nvm/versions/node"/*/bin 2>/dev/null | tail -1 || true)"
  [ -n "${_nvm_bin:-}" ] && [ -x "${_nvm_bin}/node" ] && export PATH="${_nvm_bin}:${PATH}"
fi
_ffdl="${HOME}/Library/Application Support/ffmpeg-downloader/ffmpeg"
[ -x "${_ffdl}/ffmpeg" ] && export PATH="${_ffdl}:${PATH}"
export PATH
BOOT
}

write_command_shortcut() {
  local dest="$1"
  cat > "$dest" <<INNER
#!/bin/bash
$(path_bootstrap)
cd "$ROOT" || exit 1
chmod +x "$START_SH" "$LAUNCHER" 2>/dev/null || true
exec bash "$LAUNCHER"
INNER
  chmod +x "$dest"
  xattr -dr com.apple.quarantine "$dest" 2>/dev/null || true
}

write_app_bundle() {
  local APP_DIR="$1"
  local BUNDLE_ID="${2:-local.skool.downloader}"
  rm -rf "$APP_DIR"
  mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
  cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Skool Downloader</string>
  <key>CFBundleDisplayName</key><string>Skool Downloader</string>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleVersion</key><string>1.1</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>SkoolDownloader</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
  cat > "$APP_DIR/Contents/MacOS/SkoolDownloader" <<INNER
#!/bin/bash
$(path_bootstrap)
cd "$ROOT" || exit 1
exec bash "$ROOT/app/start.sh"
INNER
  chmod +x "$APP_DIR/Contents/MacOS/SkoolDownloader"
  xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null || true
}

echo "===== Cai shortcut Skool Downloader ====="
echo "Repo: $ROOT"

DESKTOP="${HOME}/Desktop"
for d in "${HOME}/Desktop" "${HOME}/desktop" "${HOME}/Bàn làm việc"; do
  [ -d "$d" ] && DESKTOP="$d" && break
done

if [ -d "$DESKTOP" ]; then
  write_command_shortcut "${DESKTOP}/Skool Downloader.command"
  rm -f "${DESKTOP}/Skool Archiver.command" 2>/dev/null || true
  echo "✓ Desktop: ${DESKTOP}/Skool Downloader.command"
fi

DOWNLOADS="${HOME}/Downloads"
if [ -d "$DOWNLOADS" ]; then
  write_command_shortcut "${DOWNLOADS}/Skool Downloader.command"
  echo "✓ Downloads: ${DOWNLOADS}/Skool Downloader.command"
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  mkdir -p "${HOME}/Applications"
  rm -rf "${HOME}/Applications/Skool Archiver.app" 2>/dev/null || true
  write_app_bundle "${HOME}/Applications/Skool Downloader.app" "local.skool.downloader"
  echo "✓ Applications: ${HOME}/Applications/Skool Downloader.app"

  if [ -d "$DOWNLOADS" ]; then
    write_app_bundle "${DOWNLOADS}/Skool Downloader.app" "local.skool.downloader.downloads"
    echo "✓ Downloads: ${DOWNLOADS}/Skool Downloader.app"
  fi
fi

if [[ "$(uname -s)" == "Linux" ]]; then
  APP_DIR_L="${HOME}/.local/share/applications"
  mkdir -p "$APP_DIR_L"
  cat > "${APP_DIR_L}/skool-downloader.desktop" <<INNER
[Desktop Entry]
Type=Application
Name=Skool Downloader
Comment=Download and archive Skool courses offline
Exec=bash -lc 'export PATH=/usr/local/bin:/opt/homebrew/bin:\$PATH; bash "$ROOT/app/start.sh"'
Path=$ROOT/app
Terminal=false
Categories=Education;Utility;
INNER
  chmod +x "${APP_DIR_L}/skool-downloader.desktop"
  echo "✓ Linux: ${APP_DIR_L}/skool-downloader.desktop"
fi

echo ""
echo "Xong. Mo app tu:"
echo "  • Desktop → Skool Downloader"
echo "  • Downloads → Skool Downloader.app"
echo "  • ~/Applications/Skool Downloader.app"
echo "  • $LAUNCHER"
echo ""
echo "Neu van bao thieu node:  brew install node"
echo "Neu van bao thieu ffmpeg: brew install ffmpeg"
echo "  hoac:  $ROOT/app/venv/bin/python -m ffmpeg_downloader install -y"
