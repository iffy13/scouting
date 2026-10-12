@echo off
cd /d "%~dp0"
title Start Autopilot automatically when you log in
schtasks /create /tn "ScoutingAutopilot" /tr "\"%~dp0START_AUTOPILOT.bat\"" /sc onlogon /rl limited /f
if %ERRORLEVEL% EQU 0 (
    echo.
    echo Done. The autopilot window will open by itself each time you log in to Windows.
    echo To undo:  schtasks /delete /tn "ScoutingAutopilot" /f
)
pause
