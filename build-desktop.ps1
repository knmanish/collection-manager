# Builds the standalone Windows executable (dist\collect.exe).
# Prereqs:  pip install -e ".[package]"
# Usage:    .\build-desktop.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

pyinstaller --onefile --name collect --noconfirm --clean `
  --paths src `
  --collect-submodules collect `
  --add-data "src/collect/web/templates;collect/web/templates" `
  tools/desktop_launcher.py

Write-Host "`nBuilt dist\collect.exe — double-click it to launch the app." -ForegroundColor Green
