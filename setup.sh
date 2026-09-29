#!/usr/bin/env bash
# One-time setup for macOS / Linux: installs dependencies and creates .env.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "Нужен Python 3.9+: https://www.python.org/downloads/"; exit 1
fi

if ! command -v ffmpeg >/dev/null; then
  echo "Ставлю ffmpeg..."
  if command -v brew >/dev/null; then brew install ffmpeg
  elif command -v apt-get >/dev/null; then sudo apt-get update && sudo apt-get install -y ffmpeg
  else echo "Установи ffmpeg вручную: https://ffmpeg.org/download.html"; fi
fi

python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
echo "Зависимости установлены."

if [ ! -f .env ]; then
  cp .env.example .env
  read -r -p "Вставь токен бота от @BotFather (Enter, чтобы пропустить): " token
  read -r -p "Твой Telegram ID (Enter, если не знаешь: бот скажет его на /id): " uid
  read -r -p "Папка для видео (Enter = ./downloads): " dir
  python3 - "$token" "$uid" "$dir" <<'PY'
import sys, pathlib
p = pathlib.Path(".env"); text = p.read_text()
for key, val in zip(("BOT_TOKEN", "ALLOWED_USER_IDS", "DOWNLOAD_DIR"), sys.argv[1:]):
    if val:
        text = text.replace(f"{key}=\n", f"{key}={val}\n", 1)
p.write_text(text)
PY
fi

chmod +x run_bot.sh
echo
echo "Готово. Запуск бота: ./run_bot.sh"
echo "Скачать без бота:   .venv/bin/python vimeo_downloader.py <ссылка>"
