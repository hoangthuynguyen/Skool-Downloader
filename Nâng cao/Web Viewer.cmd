@echo off
REM Mo web knowledge viewer local http://127.0.0.1:8765
title Skool Downloader - Web Viewer
cd /d "%~dp0..\app"
python web_viewer.py %*
