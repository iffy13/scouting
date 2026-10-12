@echo off
title Register Daily Outreach Scheduled Task
cd /d "%~dp0"
echo ============================================================
echo   REGISTERING DAILY OUTREACH WINDOWS SCHEDULED TASK
echo ============================================================
echo.
echo Setting task to run automatically every day at 09:00 AM...
echo.

schtasks /create /tn "AutonomousColdOutreach" /tr "\"%~dp0RUN_OUTREACH.bat\"" /sc daily /st 09:00 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Windows Task 'AutonomousColdOutreach' created successfully!
    echo It will trigger automatically every day at 9:00 AM in the background.
) else (
    echo.
    echo [NOTE] If permission was denied, right-click this file and choose 'Run as administrator'.
)

echo.
echo ============================================================
pause
