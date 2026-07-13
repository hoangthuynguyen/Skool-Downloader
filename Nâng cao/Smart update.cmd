@echo off
REM Chi tai bai thieu (diff-only / smart-update). Vi du:
REM   "Smart update.cmd" --course "Ten khoa" --only videos --smart-update --until-clean
title Skool Archiver - Smart update
cd /d "%~dp0..\app"
if "%~1"=="" (
  python updates.py --smart-plan %*
) else (
  python main.py %*
)
echo.
pause
