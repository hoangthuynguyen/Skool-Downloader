#!/bin/bash
# ================================================================
#  Skool Archiver — double-click tren macOS de mo app.
#  Lan dau co the cai venv (can mang). Cac lan sau mo GUI ngay.
# ================================================================
cd "$(dirname "$0")" || exit 1
chmod +x "app/start.sh" 2>/dev/null || true
bash "app/start.sh"
# Neu chay tu Terminal, giu cua so 1s; double-click .command se tu dong
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo ""
  echo "[!] Khong mo duoc app (ma $STATUS). Xem thong bao o tren."
  echo "    Bam Enter de dong..."
  read -r _
fi
exit $STATUS
