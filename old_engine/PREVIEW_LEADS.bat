@echo off
title Outreach Machine - Lead Research & AI Copy Preview
cd /d "%~dp0"
python preview_leads.py
echo.
echo Press any key to close this preview...
pause >nul
