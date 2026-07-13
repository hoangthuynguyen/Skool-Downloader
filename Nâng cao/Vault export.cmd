@echo off
REM Export Obsidian / Notion. Vi du:
REM   "Vault export.cmd" --course "X"
REM   "Vault export.cmd" --course "X" --format notion
title Skool Archiver - Vault export
cd /d "%~dp0..\app"
python vault_export.py %*
echo.
pause
