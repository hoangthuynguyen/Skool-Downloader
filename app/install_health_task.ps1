<#
  Dang ky Windows Scheduled Task chay health_check hang ngay.
  Vi du:
    .\install_health_task.ps1
    .\install_health_task.ps1 -Hour 9 -Minute 0
  Go: .\uninstall_health_task.ps1
#>
param(
    [string]$TaskName = "SkoolArchiver-Health",
    [int]$Hour = 9,
    [int]$Minute = 0
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$py = Join-Path (Split-Path $here -Parent) "whisper\venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $py = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
}
if (-not $py) { throw "Khong tim thay python." }

$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"& '$py' '$here\health_check.py' --write --notify`""
# Dung python truc tiep gon hon
$action = New-ScheduledTaskAction -Execute $py -Argument "`"$here\health_check.py`" --write --notify" -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour $Hour -Minute $Minute -Second 0)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Da dang ky task '$TaskName' luc ${Hour}:$('{0:D2}' -f $Minute) hang ngay." -ForegroundColor Green
Write-Host "Thu chay ngay: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Go bo: .\uninstall_health_task.ps1"
