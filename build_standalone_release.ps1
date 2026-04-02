$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python environment not found at .venv\Scripts\python.exe"
}

Write-Host "Checking PyInstaller..."
& $pythonExe -m pip install --disable-pip-version-check pyinstaller | Out-Host

Write-Host "Building standalone executable..."
& $pythonExe -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name "Banking Compliance Source Finder" `
    desktop_app.py | Out-Host

$releaseDir = Join-Path $PSScriptRoot "release\BankingComplianceSourceFinder"
if (Test-Path $releaseDir) {
    Remove-Item $releaseDir -Recurse -Force
}
New-Item -ItemType Directory -Path $releaseDir | Out-Null

Copy-Item -Path (Join-Path $PSScriptRoot "dist\Banking Compliance Source Finder.exe") -Destination $releaseDir -Force
if (Test-Path (Join-Path $PSScriptRoot "discovery_config.json")) {
    Copy-Item -Path (Join-Path $PSScriptRoot "discovery_config.json") -Destination $releaseDir -Force
}

$shareNotes = @"
Banking Compliance Source Finder - Share Package

How to use:
1. Double-click 'Banking Compliance Source Finder.exe'
2. Click 'Run Now'
3. Click 'Export Findings CSV'

Notes:
- First run may show a Windows SmartScreen prompt. Click 'More info' then 'Run anyway'.
- Output files are created in the same folder where the app is launched.
"@

Set-Content -Path (Join-Path $releaseDir "README-SHARE.txt") -Value $shareNotes -Encoding UTF8

Write-Host "Release package created at: $releaseDir"
