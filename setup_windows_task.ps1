param(
    [string]$TaskName = "BankingComplianceSourceCheck",
    [string]$PythonExe = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectDir $PythonExe
$scriptPath = Join-Path $projectDir "scheduled_checks.py"
$cmdPath = Join-Path $projectDir "run_check_once.cmd"

if (-not (Test-Path $pythonPath)) {
    throw "Python executable not found at: $pythonPath"
}

if (-not (Test-Path $scriptPath)) {
    throw "scheduled_checks.py not found at: $scriptPath"
}

if (-not (Test-Path $cmdPath)) {
    throw "run_check_once.cmd not found at: $cmdPath"
}

$startTime = (Get-Date).AddMinutes(2).ToString("HH:mm")
$taskCommand = '"' + $cmdPath + '"'

$createArgs = @(
    "/Create",
    "/TN", $TaskName,
    "/SC", "HOURLY",
    "/MO", "6",
    "/ST", $startTime,
    "/TR", $taskCommand,
    "/F"
)

$process = Start-Process -FilePath "schtasks.exe" -ArgumentList $createArgs -NoNewWindow -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "Failed to register scheduled task. schtasks exit code: $($process.ExitCode)"
}

Write-Host "Scheduled task '$TaskName' registered to run every 6 hours."
Write-Host "Start time: $startTime"
Write-Host "Run now with: Start-ScheduledTask -TaskName '$TaskName'"
