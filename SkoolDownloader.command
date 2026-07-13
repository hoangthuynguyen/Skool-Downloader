#!/bin/bash
# ================================================================
#  Skool Downloader — double-click tren macOS de mo app.
# ================================================================
cd "$(dirname "$0")" || exit 1
chmod +x "app/start.sh" 2>/dev/null || true
bash "app/start.sh"
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo ""
  echo "[!] Khong mo duoc app (ma $STATUS)."
  echo "    Bam Enter de dong..."
  read -r _
fi
exit $STATUS
