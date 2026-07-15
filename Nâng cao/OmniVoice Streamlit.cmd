@echo off
REM OmniVoice Streamlit UI (conda env: omnivoice)
setlocal
set STREAMLIT_SERVER_FILE_WATCHER_TYPE=none
set PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

set OMNI_PY=/opt/homebrew/Caskroom/miniconda/base/envs/omnivoice/bin/python
set ST_APP=%USERPROFILE%\Downloads\omni_app.py
if not exist "%ST_APP%" set ST_APP=%USERPROFILE%\omnivoice_app.py

if exist "%OMNI_PY%" (
  "%OMNI_PY%" -m streamlit run "%ST_APP%" --browser.gatherUsageStats false
) else (
  echo [!] Chua tim thay env omnivoice. Chay: conda activate omnivoice
  streamlit run "%ST_APP%" --browser.gatherUsageStats false
)
endlocal
