param([string]$TaskName = "SkoolArchiver-Transcribe")
$ErrorActionPreference = "SilentlyContinue"
$t = Get-ScheduledTask -TaskName $TaskName
if ($t) {
    Stop-ScheduledTask -TaskName $TaskName
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Da go task '$TaskName'." -ForegroundColor Green
} else {
    Write-Host "Khong thay task '$TaskName'."
}
