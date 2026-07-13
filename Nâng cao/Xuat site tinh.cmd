@echo off
REM Xuat HTML offline vao courses\_site
title Skool Downloader - Export site
cd /d "%~dp0..\app"
python export_site.py --open %*
echo.
pause
