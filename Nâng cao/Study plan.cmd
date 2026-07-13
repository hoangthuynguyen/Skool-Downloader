@echo off
REM Xuat ICS lich hoc tu playlist
title Skool Archiver - Study plan
cd /d "%~dp0..\app"
if "%~1"=="" (
  python study_plan.py --all --days 14
) else (
  python study_plan.py %*
)
echo.
pause
