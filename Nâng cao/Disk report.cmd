@echo off
title Skool Archiver - Disk report
cd /d "%~dp0..\app"
python disk_report.py --write %*
echo.
pause
