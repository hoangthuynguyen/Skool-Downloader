@echo off
chcp 65001 >nul
cd /d "%~dp0..\app"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" course_studio.py %*
) else (
  python course_studio.py %*
)
echo.
pause
