#!/bin/bash
# Double-click de tao shortcut Desktop (macOS)
cd "$(dirname "$0")" || exit 1
chmod +x "app/install_shortcut.sh" "app/start.sh" "SkoolArchiver.command" 2>/dev/null || true
bash "app/install_shortcut.sh"
echo ""
echo "Bam Enter de dong..."
read -r _
