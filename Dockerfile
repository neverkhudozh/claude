FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg rclone ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY vimeo_downloader.py bot.py ./
ENV DOWNLOAD_DIR=/downloads
# Update yt-dlp on every start: Vimeo changes its player often.
CMD pip install -q --upgrade yt-dlp && python bot.py
