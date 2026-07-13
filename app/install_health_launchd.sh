#!/usr/bin/env bash
# macOS: cai LaunchAgent chay health_check moi ngay 09:00
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
LABEL="com.skooldownloader.health"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HERE/../logs" 2>/dev/null || true

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PY}</string>
    <string>${HERE}/health_check.py</string>
    <string>--write</string>
  </array>
  <key>WorkingDirectory</key><string>${HERE}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>9</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>${HERE}/../logs/health_launchd.log</string>
  <key>StandardErrorPath</key><string>${HERE}/../logs/health_launchd.err</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Loaded $PLIST (daily 09:00)"
echo "Unload: launchctl unload $PLIST && rm $PLIST"
