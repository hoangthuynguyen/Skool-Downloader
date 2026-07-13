@echo off
REM Quet suc khoe toan kho + ghi _health.json
title Skool Archiver - Health
cd /d "%~dp0..\app"
python health_check.py --write --notify %*
echo.
pause
