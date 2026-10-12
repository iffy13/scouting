@echo off
title Outreach Machine - Live Status Dashboard
cd /d "%~dp0"
python status.py
echo.
echo Press any key to close this dashboard...
pause >nul
