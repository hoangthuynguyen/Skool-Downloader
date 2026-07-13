@echo off
REM Dich / cap nhat noi dung theo prompt LLM.
REM Vi du:
REM   "LLM Prompt.cmd" --list-presets
REM   "LLM Prompt.cmd" --course "X" --preset translate_vi
REM   "LLM Prompt.cmd" --course "X" --user-prompt "Dich sang VI, ngan gon"
title Skool Downloader - LLM Prompt
cd /d "%~dp0..\app"
python llm_prompt.py %*
echo.
pause
