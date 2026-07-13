param(
    [string]$Title = "Skool Downloader",
    [string]$Message = "",
    [ValidateSet("info","error")] [string]$Level = "info"
)
# Thong bao Windows, nhieu lop du phong de chay duoc tren moi may (ke ca Win Home).
$ErrorActionPreference = "SilentlyContinue"

# 1) BurntToast (toast dep, neu da cai module)
if (Get-Module -ListAvailable -Name BurntToast) {
    Import-Module BurntToast
    New-BurntToastNotification -Text $Title, $Message
    if ($?) { return }
}

# 2) Balloon qua NotifyIcon (.NET - co san moi may, hien vai giay)
try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $ni = New-Object System.Windows.Forms.NotifyIcon
    $ni.Icon = [System.Drawing.SystemIcons]::Information
    $ni.Visible = $true
    $icon = if ($Level -eq "error") { [System.Windows.Forms.ToolTipIcon]::Error } else { [System.Windows.Forms.ToolTipIcon]::Info }
    $ni.ShowBalloonTip(15000, $Title, $Message, $icon)
    Start-Sleep -Seconds 12
    $ni.Dispose()
    return
} catch {}

# 3) Cuoi cung: ghi ra file de van con dau vet
"$((Get-Date).ToString('s'))  [$Level] $Title - $Message" |
    Out-File -FilePath (Join-Path $PSScriptRoot "NOTIFICATIONS.log") -Append -Encoding utf8
