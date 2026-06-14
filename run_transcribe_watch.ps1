# Runner cho watcher transcribe (duoc Task Scheduler goi, hoac chay tay).
# Vi du:  .\run_transcribe_watch.ps1 --all
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $here
$base = Split-Path -Parent $here

[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"

function Test-YtOrFW($py) {
    if (-not (Test-Path $py)) { return $false }
    & $py -c "import faster_whisper" 2>$null
    return $LASTEXITCODE -eq 0
}
$candidates = @("$here\venv\Scripts\python.exe", "$base\whisper\venv\Scripts\python.exe", "python")
$py = $null
foreach ($c in $candidates) {
    $r = if ($c -eq "python") { (Get-Command python -ErrorAction SilentlyContinue).Source } else { $c }
    if ($r -and (Test-YtOrFW $r)) { $py = $r; break }
}
if (-not $py) {
    Write-Host "[LOI] Khong tim thay Python co faster-whisper. Chay: pip install -U faster-whisper" -ForegroundColor Red
    exit 1
}

$logDir = "$here\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "$logDir\transcribe_$stamp.log"

& $py transcribe_watch.py @args 2>&1 | Tee-Object -FilePath $log
exit $LASTEXITCODE
