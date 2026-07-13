param([string]$TaskName = "SkoolDownloader-Health")
$ErrorActionPreference = "SilentlyContinue"
foreach ($n in @($TaskName, "SkoolArchiver-Health")) {
    Unregister-ScheduledTask -TaskName $n -Confirm:$false
    Write-Host "Da go task '$n' (neu co)."
}
