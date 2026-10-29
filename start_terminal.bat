@echo off
title NSE Quant Studio - Trading Terminal
cd /d "%~dp0"
cls
echo =====================================================================
echo           NSE QUANT STUDIO & TRADINGVIEW PINE TERMINAL
echo =====================================================================
echo.
echo Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python is ready.
echo Starting Quantitative Server on http://localhost:8080 ...
echo.

:: Launch browser in background after 2 seconds
start "" powershell -NoProfile -Command "Start-Sleep -Milliseconds 1500; Start-Process 'http://localhost:8080/'"

:: Run the server
python server.py --port 8080

if errorlevel 1 (
    echo.
    echo Server stopped or port 8080 was busy. Trying alternate port 8085...
    start "" powershell -NoProfile -Command "Start-Sleep -Milliseconds 1500; Start-Process 'http://localhost:8085/'"
    python server.py --port 8085
)

pause
