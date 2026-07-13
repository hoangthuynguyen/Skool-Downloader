param([string]$TaskName = "SkoolDownloader-Transcribe")
$ErrorActionPreference = "SilentlyContinue"
foreach ($n in @($TaskName, "SkoolArchiver-Transcribe")) {
    $t = Get-ScheduledTask -TaskName $n
    if ($t) {
        Stop-ScheduledTask -TaskName $n
        Unregister-ScheduledTask -TaskName $n -Confirm:$false
        Write-Host "Da go task '$n'." -ForegroundColor Green
    } else {
        Write-Host "Khong thay task '$n'."
    }
}
