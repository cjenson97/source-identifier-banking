param(
    [string]$TaskName = "BankingComplianceSourceFinderAutoStart"
)

$ErrorActionPreference = "Stop"

$startupFolder = [Environment]::GetFolderPath("Startup")
$startupShortcut = Join-Path $startupFolder "Banking Compliance Source Finder.lnk"

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "Auto-start task not found: $TaskName"
}
else {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Disabled auto-start task: $TaskName"
}

if (Test-Path $startupShortcut) {
    Remove-Item -Path $startupShortcut -Force
    Write-Host "Removed Startup shortcut: $startupShortcut"
}
else {
    Write-Host "Startup shortcut not found: $startupShortcut"
}
