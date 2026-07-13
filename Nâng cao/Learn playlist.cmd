@echo off
REM Playlist Hoc tiep tu bookmarks + quiz
title Skool Archiver - Learn playlist
cd /d "%~dp0..\app"
if "%~1"=="" (
  python learn_playlist.py --all --write
) else (
  python learn_playlist.py %*
)
echo.
pause
