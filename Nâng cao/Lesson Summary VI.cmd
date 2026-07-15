@echo off
chcp 65001 >nul
cd /d "%~dp0..\app"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" lesson_summary.py %*
) else (
  python lesson_summary.py %*
)
echo.
pause
