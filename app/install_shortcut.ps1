# Cai shortcut Desktop + Start Menu cho Skool Archiver (Windows).
# Chay: Right-click → Run with PowerShell  hoac  Nâng cao\Tao shortcut Desktop.cmd
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition   # ...\app
$root = Split-Path -Parent $here                                 # repo root
$cmd  = Join-Path $root "SkoolArchiver.cmd"

if (-not (Test-Path $cmd)) {
    Write-Host "Khong thay SkoolArchiver.cmd tai $cmd" -ForegroundColor Red
    exit 1
}

$Wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"

function New-SAShortcut($path) {
    $sc = $Wsh.CreateShortcut($path)
    $sc.TargetPath = $cmd
    $sc.WorkingDirectory = $root
    $sc.WindowStyle = 1
    $sc.Description = "Skool Archiver — mo giao dien luu tru khoa Skool"
    # icon: pythonw neu co, else default
    $icon = Join-Path $here "venv\Scripts\pythonw.exe"
    if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
    $sc.Save()
    Write-Host "  ✓ $path" -ForegroundColor Green
}

Write-Host ""
Write-Host "===== Cai shortcut Skool Archiver =====" -ForegroundColor Cyan
Write-Host "Repo: $root"

$deskLnk = Join-Path $desktop "Skool Archiver.lnk"
New-SAShortcut $deskLnk

if (-not (Test-Path $startMenu)) { New-Item -ItemType Directory -Path $startMenu -Force | Out-Null }
$startLnk = Join-Path $startMenu "Skool Archiver.lnk"
New-SAShortcut $startLnk

Write-Host ""
Write-Host "Xong. Bam double-click «Skool Archiver» tren Desktop de mo app." -ForegroundColor Cyan
Write-Host ""
