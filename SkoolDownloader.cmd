@echo off
REM ================================================================
REM  Skool Downloader - BAM PHAT LA CHAY.
REM ================================================================
title Skool Downloader
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\start.ps1"
if errorlevel 1 (
  echo.
  echo [!] Khong mo duoc giao dien - xem thong bao o tren.
  echo     Bam phim bat ky de dong.
  pause >nul
)
