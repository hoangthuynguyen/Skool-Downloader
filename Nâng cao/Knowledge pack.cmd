@echo off
REM Zip knowledge (text) 1 khoa. Vi du:
REM   "Knowledge pack.cmd" --course "Ten khoa"
title Skool Downloader - Knowledge pack
cd /d "%~dp0..\app"
python knowledge_pack.py %*
echo.
pause
