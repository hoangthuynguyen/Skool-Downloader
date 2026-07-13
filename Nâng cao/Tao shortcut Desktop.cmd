@echo off
title Skool Archiver - Tao shortcut Desktop
cd /d "%~dp0..\app"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\app\install_shortcut.ps1"
echo.
pause
