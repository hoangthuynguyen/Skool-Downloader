@echo off
REM Xuat Anki TSV. Vi du:
REM   "Anki export.cmd" --course "Ten khoa"
REM   "Anki export.cmd" --course "X" --cloze --max 100
title Skool Downloader - Anki export
cd /d "%~dp0..\app"
python anki_export.py %*
echo.
pause
