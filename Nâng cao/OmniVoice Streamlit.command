#!/bin/zsh
# OmniVoice Streamlit UI — double-click trên macOS
cd "$(dirname "$0")/.." || exit 1
export STREAMLIT_SERVER_FILE_WATCHER_TYPE=none
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

OMNI_PY="/opt/homebrew/Caskroom/miniconda/base/envs/omnivoice/bin/python"
APP="${HOME}/Downloads/omni_app.py"
[[ -f "$APP" ]] || APP="${HOME}/omnivoice_app.py"

echo "OmniVoice Streamlit → $APP"
if [[ -x "$OMNI_PY" ]]; then
  exec "$OMNI_PY" -m streamlit run "$APP" --browser.gatherUsageStats false
else
  echo "Canh bao: khong thay env omnivoice — dung streamlit tren PATH"
  exec streamlit run "$APP" --browser.gatherUsageStats false
fi
