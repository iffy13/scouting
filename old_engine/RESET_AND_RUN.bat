@echo off
title Reset Queue and Run Outreach Engine
cls
echo ============================================================
echo      RESETTING ROTATION QUEUE TO FRESH STATE
echo ============================================================
python reset_queue.py
echo.
echo ============================================================
echo      STARTING LIVE OUTREACH ENGINE
echo ============================================================
python main.py --action full
echo.
pause
