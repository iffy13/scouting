@echo off
cd /d "%~dp0"
title Outreach Autopilot - close this window to stop
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
:loop
%PY% autopilot_local.py
echo.
echo Autopilot exited. Restarting in 60 seconds. Close this window to stop for good.
timeout /t 60 /nobreak >nul
goto loop
