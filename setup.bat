@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul || (echo Нужен Python 3.9+: https://www.python.org/downloads/ ^(поставь галочку "Add to PATH"^) & pause & exit /b 1)
where ffmpeg >nul 2>nul || (echo Ставлю ffmpeg... & winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements)

python -m venv .venv
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\pip install -q -r requirements.txt
echo Зависимости установлены.

if not exist .env (
  copy .env.example .env >nul
  echo Открываю .env: впиши BOT_TOKEN и ALLOWED_USER_IDS, сохрани и закрой блокнот.
  notepad .env
)
echo.
echo Готово. Запуск бота: run_bot.bat
pause
