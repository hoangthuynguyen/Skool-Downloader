@echo off
REM Offline quiz. Vi du:
REM   "Offline quiz.cmd" --course "X" --build
REM   "Offline quiz.cmd" --course "X" --play
title Skool Downloader - Offline quiz
cd /d "%~dp0..\app"
python quiz.py %*
echo.
pause
