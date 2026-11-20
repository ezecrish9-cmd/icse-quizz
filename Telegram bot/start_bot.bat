@echo off
title Academic Quiz Telegram Bot
echo ======================================================
echo Starting Telegram Quiz Bot...
echo ======================================================
cd /d "%~dp0"
"C:\Users\EzeCr\AppData\Local\Python\bin\python.exe" run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bot stopped with an error.
    pause
)
