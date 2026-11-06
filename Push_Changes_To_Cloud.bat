@echo off
title Push Updates to Cloud (TradeX 24/7)
cd /d "%~dp0"
echo =======================================================
echo  PUSHING TRADEX UPDATES TO GITHUB & CLOUD HOST
echo =======================================================
echo.
git status --short
echo.
set /p msg="Enter commit message (or press Enter for default): "
if "%msg%"=="" set msg=Update TradeX algorithms and chart sync

git add -A
git commit -m "%msg%"
git push origin main
echo.
echo =======================================================
echo  SUCCESS! Changes pushed to GitHub.
echo  Your 24/7 cloud server will automatically redeploy!
echo =======================================================
pause
