@echo off
REM Liet ke / xoa file tai do (.part .ytdl). Vi du:
REM   "Don file do.cmd" --course "Ten khoa"
REM   "Don file do.cmd" --course "Ten khoa" --apply
title Skool Downloader - Cleanup
cd /d "%~dp0..\app"
python cleanup.py %*
echo.
pause
