@echo off
title Skool Archiver - Selftest
cd /d "%~dp0..\app"
python selftest.py %*
echo.
pause
