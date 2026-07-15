#!/bin/zsh
# Course OS OmniVoice — status + goi y lenh (TTS default OFF)
cd "$(dirname "$0")/.." || exit 1
APP_DIR="$(pwd)/app"
export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"

echo "=== OmniVoice Course TTS (default OFF) ==="
echo "Thu muc app: $APP_DIR"
echo ""
echo "Vi du:"
echo "  python3 app/course_omnivoice.py --course \"TenKhoa\" --status"
echo "  python3 app/course_omnivoice.py --course \"TenKhoa\" --toggle-board"
echo "  python3 app/course_omnivoice.py --course \"TenKhoa\" --enable-all"
echo "  python3 app/course_omnivoice.py --course \"TenKhoa\" --all --limit 3"
echo "  python3 app/course_omnivoice.py --course \"TenKhoa\" --disable-all"
echo "  python3 app/course_omnivoice.py --streamlit"
echo ""
if [[ -n "${1:-}" ]]; then
  python3 app/course_omnivoice.py --course "$1" --status
else
  python3 app/course_omnivoice.py --help | head -40
fi
echo ""
read -k 1 "?Nhan phim bat ky de dong…"
