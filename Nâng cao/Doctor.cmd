@echo off
REM Kiem tra moi truong + BASE + module Phase
title Skool Downloader - Doctor
cd /d "%~dp0..\app"
python doctor.py %*
echo.
pause
