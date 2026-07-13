@echo off
REM One-click fix: yt-dlp + pip packages thieu
title Skool Archiver - Doctor fix
cd /d "%~dp0..\app"
python doctor.py --fix %*
echo.
pause
