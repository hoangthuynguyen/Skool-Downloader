param([string]$TaskName = "SkoolArchiver-Health")
$ErrorActionPreference = "SilentlyContinue"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Da go task '$TaskName' (neu co)."
