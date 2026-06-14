<#
  Dang ky Windows Scheduled Task chay watcher transcribe NGAM.
  - Chay khi dang nhap (song sau reboot/tat may -> bat lai tu chay tiep).
  - Doc lap Claude (tat Claude van chay).
  - Tu tiep tuc khi gap loi (RestartCount), chay ca khi dung pin.
  - Xong (het video & khong con tai) -> tu bao Windows roi thoat.

  Vi du:
    .\install_transcribe_task.ps1 -All          # quet SkoolCourse + tat ca courses/*
    .\install_transcribe_task.ps1 -Course "AI Automations by Jack"
  Go bo:  .\uninstall_transcribe_task.ps1
#>
param(
    [string]$Course = "",
    [switch]$All,
    [string]$TaskName = "SkoolArchiver-Transcribe"
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$runner = Join-Path $here "run_transcribe_watch.ps1"

# Xay dung tham so cho watcher
$watchArgs = if ($All) { "--all" } elseif ($Course) { "--course `"$Course`"" } else { "" }
$psArg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`" $watchArgs"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArg -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
$settings.ExecutionTimeLimit = "PT0S"   # khong gioi han thoi gian chay

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Da dang ky task '$TaskName'." -ForegroundColor Green
Write-Host "  Tham so watcher: $(if($watchArgs){$watchArgs}else{'(SkoolCourse mac dinh)'})"
Write-Host "  Trigger: khi dang nhap (tu chay tiep sau reboot)."
Write-Host ""
Write-Host "Bat dau chay ngay bay gio..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $TaskName
Write-Host "Dang chay nen. Log: $here\logs\transcribe_*.log"
Write-Host "Xem trang thai: Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "Go bo khi xong:  .\uninstall_transcribe_task.ps1"
