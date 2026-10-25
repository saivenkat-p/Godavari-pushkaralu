@echo off
echo Starting Godavari Pushkaralu Telegram Bot...
cd /d "%~dp0"
.\.venv\Scripts\python.exe backend\app\services\telegram_bot.py
pause
