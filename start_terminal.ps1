# NSE Quant Studio - PowerShell Launcher
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "          NSE QUANT STUDIO & TRADINGVIEW PINE TERMINAL" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] $pyVersion detected." -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python was not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://python.org" -ForegroundColor Yellow
    exit 1
}

$port = 8080
Write-Host "[INFO] Starting server on http://localhost:$port..." -ForegroundColor Yellow

# Auto open browser
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8080/"
} | Out-Null

python server.py --port $port
