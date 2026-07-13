$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$root = Split-Path -Parent $here
$cmd  = Join-Path $root "SkoolDownloader.cmd"
if (-not (Test-Path $cmd)) { $cmd = Join-Path $root "SkoolArchiver.cmd" }
if (-not (Test-Path $cmd)) { Write-Host "Khong thay launcher" -ForegroundColor Red; exit 1 }
$Wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
function New-SAShortcut($path) {
    $sc = $Wsh.CreateShortcut($path)
    $sc.TargetPath = $cmd
    $sc.WorkingDirectory = $root
    $sc.WindowStyle = 1
    $sc.Description = "Skool Downloader — mo app tai khoa Skool"
    $icon = Join-Path $here "venv\Scripts\pythonw.exe"
    if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
    $sc.Save()
    Write-Host "  ✓ $path" -ForegroundColor Green
}
Write-Host "===== Cai shortcut Skool Downloader =====" -ForegroundColor Cyan
New-SAShortcut (Join-Path $desktop "Skool Downloader.lnk")
if (-not (Test-Path $startMenu)) { New-Item -ItemType Directory -Path $startMenu -Force | Out-Null }
New-SAShortcut (Join-Path $startMenu "Skool Downloader.lnk")
# remove legacy name (pre-rename)
Remove-Item (Join-Path $desktop "Skool Archiver.lnk") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $startMenu "Skool Archiver.lnk") -ErrorAction SilentlyContinue
Write-Host "Xong. Bam «Skool Downloader» tren Desktop." -ForegroundColor Cyan
