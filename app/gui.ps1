# Mo giao dien (GUI) Skool Downloader. Duoc GiaoDien.cmd goi.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition   # ...\Skool-Downloader\app
$base = Split-Path -Parent (Split-Path -Parent $here)           # ...\SkoolProject

function Test-Tk($py) {
    if (-not (Test-Path $py)) { return $false }
    & $py -c "import customtkinter" 2>$null
    return $LASTEXITCODE -eq 0
}
$cands = @("$here\venv\Scripts\python.exe", "$base\whisper\venv\Scripts\python.exe", "python")
$py = $null
foreach ($c in $cands) {
    $r = if ($c -eq "python") { (Get-Command python -ErrorAction SilentlyContinue).Source } else { $c }
    if ($r -and (Test-Tk $r)) { $py = $r; break }
}
if (-not $py) {
    [System.Windows.Forms.MessageBox]::Show("Khong tim thay Python co tkinter. Chay setup.cmd truoc.") | Out-Null
    exit 1
}
# dung pythonw.exe de khong hien cua so console
$pyw = $py -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $py }
Start-Process -FilePath $pyw -ArgumentList "gui.py" -WorkingDirectory $here
