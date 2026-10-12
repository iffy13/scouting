@echo off
title Deliverability & Inbox Placement Audit
cd /d "%~dp0"
echo ======================================================================
echo       TESTING GMAIL INBOX PLACEMENT & SPAM FILTER HEALTH
echo ======================================================================
python test_deliverability.py
echo.
pause
