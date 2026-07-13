@echo off
title Skool Downloader - Selftest
cd /d "%~dp0..\app"
python selftest.py %*
echo.
pause
