@echo off
REM Backup / restore knowledge pack. Vi du:
REM   "Pack backup.cmd" --course "X" --backup
REM   "Pack backup.cmd" --course "X" --backup --upload
REM   "Pack backup.cmd" --list
REM   "Pack backup.cmd" --restore "..\courses\_backups\X_....zip" --course "X"
title Skool Archiver - Pack backup
cd /d "%~dp0..\app"
python -m cloud.pack_backup %*
echo.
pause
