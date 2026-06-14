# === Setup moi truong cho Skool Archiver (may moi) ===
# Chay 1 lan:  double-click setup.cmd o thu muc Archiver  (no goi file nay trong app\).
# Luu y: may da co san ..\..\whisper\venv day du thi KHONG can chay setup -
#        run.ps1 se tu dung venv do.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $here

Write-Host "==> Tao venv..." -ForegroundColor Cyan
if (-not (Test-Path ".\venv")) { python -m venv venv }

Write-Host "==> Nang pip..." -ForegroundColor Cyan
& .\venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "==> Cai thu vien (yt-dlp, whisper, ffmpeg-downloader)..." -ForegroundColor Cyan
& .\venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "==> Cai ffmpeg..." -ForegroundColor Cyan
& .\venv\Scripts\ffdl.exe install --add-path

Write-Host "==> Kiem tra yt-dlp..." -ForegroundColor Cyan
& .\venv\Scripts\python.exe -m yt_dlp --version

# Node.js can cho YouTube (vuot bot-check). Thu cai qua winget neu thieu.
if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "==> Node.js: OK ($([string](node --version)))" -ForegroundColor Green
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "==> Cai Node.js qua winget..." -ForegroundColor Cyan
    winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
    Write-Host "    (Mo lai PowerShell de Node vao PATH neu vua cai.)" -ForegroundColor Yellow
} else {
    Write-Host "==> [CANH BAO] Chua co Node.js va khong co winget." -ForegroundColor Yellow
    Write-Host "    Cai tay tai https://nodejs.org (ban LTS) roi mo lai PowerShell -> video YouTube moi tai duoc." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==> Kiem tra moi truong (preflight)..." -ForegroundColor Cyan
& .\venv\Scripts\python.exe preflight.py

Write-Host ""
Write-Host "XONG. Tu gio (o thu muc Archiver) chay:" -ForegroundColor Green
Write-Host '    .\run.cmd --course "Ten khoa"'
Write-Host '    .\run.cmd --list-courses'
Write-Host '    .\install_transcribe_task.cmd -All        (transcribe ngam)'
