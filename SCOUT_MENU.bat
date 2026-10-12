@echo off
cd /d "%~dp0"
title Scouting Menu
:menu
cls
echo ============================================
echo   SCOUTING MENU
echo ============================================
echo  1. Check mailboxes
echo  2. Connect a mailbox (sign in to Gmail)
echo  3. Scout WhatsApp API leads
echo  4. Scout AI receptionist leads
echo  5. Preview messages (nothing is sent)
echo  6. Approve leads
echo  7. Send approved leads (asks y/n for each)
echo  8. Check replies now (alerts to Telegram)
echo  9. Watch for replies (keeps checking)
echo  T. Test Telegram
echo  R. Send status report to Telegram
echo  0. Exit
echo.
set /p c=Choose: 
if "%c%"=="1" python outreach.py check
if "%c%"=="2" (set /p s=Service name, whatsapp_api or receptionist or book_trailer: & python outreach.py connect --service %s%)
if "%c%"=="3" python scout.py --service whatsapp_api --max 40
if "%c%"=="4" python scout.py --service receptionist --max 40
if "%c%"=="5" (set /p s=Service name: & python outreach.py preview --service %s% --n 3)
if "%c%"=="6" (set /p s=Service name: & set /p m=Minimum score, for example 70: & python outreach.py approve --service %s% --min-score %m%)
if "%c%"=="7" (set /p s=Service name: & python outreach.py send --service %s% --limit 10)
if "%c%"=="8" python outreach.py replies
if "%c%"=="9" python outreach.py replies --watch
if /i "%c%"=="T" python outreach.py telegram
if /i "%c%"=="R" python outreach.py report
if "%c%"=="0" exit
echo.
pause
goto menu
