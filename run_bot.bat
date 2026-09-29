@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv call setup.bat
.venv\Scripts\pip install -q --upgrade yt-dlp
.venv\Scripts\python bot.py
pause
