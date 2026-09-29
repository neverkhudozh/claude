#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -d .venv ] || ./setup.sh
.venv/bin/pip install -q --upgrade yt-dlp   # Vimeo changes often; fresh yt-dlp keeps working
exec .venv/bin/python bot.py
