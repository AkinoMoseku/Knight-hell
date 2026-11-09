$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "Run 'uv sync' before building the demo executable."
}

& ".\.venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm `
    --clean `
    "packaging\flowremote_demo.spec"

Write-Host ""
Write-Host "Built: $((Resolve-Path 'dist\FlowRemoteDemo.exe').Path)"
