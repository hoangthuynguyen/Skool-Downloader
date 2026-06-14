@echo off
REM Cai dat moi truong (double-click chay duoc).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
pause
