$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbsPath = Join-Path $projectDir "Launch Banking Compliance Source Finder.vbs"

if (-not (Test-Path $vbsPath)) {
    throw "Launcher file not found: $vbsPath"
}

$shell = New-Object -ComObject WScript.Shell

$desktop = [Environment]::GetFolderPath("Desktop")
$desktopShortcutPath = Join-Path $desktop "Banking Compliance Source Finder.lnk"
$desktopShortcut = $shell.CreateShortcut($desktopShortcutPath)
$desktopShortcut.TargetPath = "wscript.exe"
$desktopShortcut.Arguments = '"' + $vbsPath + '"'
$desktopShortcut.WorkingDirectory = $projectDir
$desktopShortcut.Description = "Launch Banking Compliance Source Finder"
$desktopShortcut.Save()

$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startShortcutPath = Join-Path $startMenu "Banking Compliance Source Finder.lnk"
$startShortcut = $shell.CreateShortcut($startShortcutPath)
$startShortcut.TargetPath = "wscript.exe"
$startShortcut.Arguments = '"' + $vbsPath + '"'
$startShortcut.WorkingDirectory = $projectDir
$startShortcut.Description = "Launch Banking Compliance Source Finder"
$startShortcut.Save()

Write-Host "Created shortcuts:"
Write-Host "- $desktopShortcutPath"
Write-Host "- $startShortcutPath"
