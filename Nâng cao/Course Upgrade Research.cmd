@echo off
chcp 65001 >nul
cd /d "%~dp0..\app"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" course_upgrade.py %*
) else (
  python course_upgrade.py %*
)
echo.
pause
