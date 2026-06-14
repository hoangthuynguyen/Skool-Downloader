# === Skool Archiver - chay bang 1 lenh ===
# Vi du:
#   .\run.ps1 --course "AI Automations by Jack"
#   .\run.ps1 --course "AI Automations by Jack" --transcribe
#   .\run.ps1 --list-courses
#   .\run.ps1 --course "X" --only audit
# Moi tham so deu chuyen thang sang main.py (xem: .\run.ps1 --help)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition   # ...\Archiver\app
Set-Location $here
$archiver = Split-Path -Parent $here                            # ...\Archiver
$base = Split-Path -Parent $archiver                            # ...\SkoolProject

# UTF-8 cho ca console lan file log (tranh crash ten folder co ky tu la nhu '▶')
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# --- Tim python co yt_dlp: uu tien venv cua Archiver, roi whisper/venv, roi PATH ---
function Test-YtDlp($py) {
    if (-not (Test-Path $py)) { return $false }
    & $py -c "import yt_dlp" 2>$null
    return $LASTEXITCODE -eq 0
}
$candidates = @(
    "$here\venv\Scripts\python.exe",
    "$base\whisper\venv\Scripts\python.exe",
    "python"
)
$py = $null
foreach ($c in $candidates) {
    $resolved = if ($c -eq "python") { (Get-Command python -ErrorAction SilentlyContinue).Source } else { $c }
    if ($resolved -and (Test-YtDlp $resolved)) { $py = $resolved; break }
}
if (-not $py) {
    Write-Host "[LOI] Khong tim thay Python co yt-dlp. Chay setup.cmd truoc." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $py" -ForegroundColor DarkGray

# --- Canh bao neu thieu Node/Deno (YouTube se bi chan bot) ---
$hasNode = [bool](Get-Command node -ErrorAction SilentlyContinue)
$hasDeno = [bool](Get-Command deno -ErrorAction SilentlyContinue)
if (-not $hasNode -and -not $hasDeno) {
    Write-Host "[CANH BAO] Khong thay Node.js/Deno -> video YouTube co the bi 'Sign in to confirm you're not a bot'." -ForegroundColor Yellow
    Write-Host "           Cai Node: https://nodejs.org  roi chay lai." -ForegroundColor Yellow
}

# --- Log co dau thoi gian ---
$logDir = "$archiver\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "$logDir\run_$stamp.log"
Write-Host "Log: $log" -ForegroundColor DarkGray
Write-Host ""

# --- Chay main.py, vua hien console vua ghi log ---
& $py main.py @args 2>&1 | Tee-Object -FilePath $log
exit $LASTEXITCODE
