param(
    [string]$TaskName = "BankingComplianceSourceFinderAutoStart"
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbsPath = Join-Path $projectDir "Launch Banking Compliance Source Finder.vbs"
$startupFolder = [Environment]::GetFolderPath("Startup")
$startupShortcut = Join-Path $startupFolder "Banking Compliance Source Finder.lnk"

if (-not (Test-Path $vbsPath)) {
    throw "Launcher not found: $vbsPath"
}

try {
    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ('"' + $vbsPath + '"') -WorkingDirectory $projectDir
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force -ErrorAction Stop | Out-Null
    Write-Host "Enabled auto-start via Scheduled Task: $TaskName"
}
catch {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($startupShortcut)
    $shortcut.TargetPath = "wscript.exe"
    $shortcut.Arguments = '"' + $vbsPath + '"'
    $shortcut.WorkingDirectory = $projectDir
    $shortcut.Description = "Launch Banking Compliance Source Finder at login"
    $shortcut.Save()
    Write-Host "Scheduled Task registration failed (likely permissions)."
    Write-Host "Enabled auto-start via Startup shortcut: $startupShortcut"
}
