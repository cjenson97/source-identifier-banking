param(
    [string]$TaskName = "BankingComplianceSourceCheck"
)

$ErrorActionPreference = "Stop"

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
Start-ScheduledTask -InputObject $task
Write-Host "Started scheduled task '$TaskName'."
