@echo off
title Autonomous Outreach - Background Scheduler
cd /d "%~dp0"
echo ============================================================
echo   STARTING 24/7 BACKGROUND OUTREACH SCHEDULER
echo ============================================================
echo.
echo This window will stay open and run your outreach engine
echo automatically every morning at 09:00 AM.
echo.
echo You can minimize this window to your taskbar.
echo.
python scheduler.py
pause
