@echo off
REM Smart update multi-course. Vi du:
REM   "Smart batch.cmd" --smart-batch
REM   "Smart batch.cmd" --smart-batch --smart-batch-run
title Skool Archiver - Smart batch
cd /d "%~dp0..\app"
if "%~1"=="" (
  python main.py --smart-batch
) else (
  python main.py %*
)
echo.
pause
