#!/usr/bin/env python3
"""Telegram bot: send it Vimeo links, it downloads them into a folder
on this machine and sends the videos back to the chat.

Config lives in .env next to this file (see .env.example).
"""

import asyncio
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import vimeo_downloader as vd

ROOT = Path(__file__).resolve().parent
VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
AUDIO_EXTS = {".mp3", ".m4a", ".ogg", ".opus"}

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("vimeo-bot")


# ---------- config ----------

def load_env(path=ROOT / ".env"):
    """Minimal .env reader so we don't need python-dotenv."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALLOWED_USERS = {int(x) for x in re.findall(r"-?\d+", os.environ.get("ALLOWED_USER_IDS", ""))}
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR") or ROOT / "downloads").expanduser().resolve()
SEND_TO_CHAT = os.environ.get("SEND_TO_CHAT", "true").lower() in ("1", "true", "yes", "да")
TELEGRAM_API_URL = os.environ.get("TELEGRAM_API_URL", "").rstrip("/")
# The public Bot API caps uploads at 50 MB; a local Bot API server raises it to 2000 MB.
MAX_SEND_MB = int(os.environ.get("MAX_SEND_MB") or (2000 if TELEGRAM_API_URL else 50))
RCLONE_REMOTE = os.environ.get("RCLONE_REMOTE", "").rstrip("/")
COOKIES_FROM_BROWSER = os.environ.get("COOKIES_FROM_BROWSER") or None
COOKIES_FILE = os.environ.get("COOKIES_FILE") or None
SETTINGS_FILE = Path(os.environ.get("SETTINGS_FILE") or ROOT / "bot_settings.json").expanduser()


# ---------- per-user settings ----------

DEFAULTS = {"folder": "", "quality": "best", "audio_only": False}


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


SETTINGS = load_settings()


def user_settings(user_id):
    return {**DEFAULTS, **SETTINGS.get(str(user_id), {})}


def save_user_setting(user_id, key, value):
    SETTINGS.setdefault(str(user_id), {})[key] = value
    SETTINGS_FILE.write_text(json.dumps(SETTINGS, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_folder(name):
    """Keep folder names inside DOWNLOAD_DIR: no slashes, no '..', no control chars."""
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name).strip(" .")
    return name[:80]


def target_dir(user_id):
    folder = user_settings(user_id)["folder"]
    return DOWNLOAD_DIR / folder if folder else DOWNLOAD_DIR


def parse_request(text):
    """Split a chat message into links + optional password / referer."""
    password = referer = None
    m = re.search(r"(?:пароль|password|pass|pwd)\s*[:=]\s*(\S+)", text, re.IGNORECASE)
    if m:
        password = m.group(1)
    m = re.search(r"(?:сайт|referer|site)\s*[:=]\s*(https?://\S+)", text, re.IGNORECASE)
    if m:
        referer = m.group(1)
        text = text.replace(m.group(0), " ")
    return vd.find_vimeo_urls(text), password, referer


# ---------- access control ----------

def allowed(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in ALLOWED_USERS)


async def deny(update: Update):
    uid = update.effective_user.id if update.effective_user else "?"
    await update.effective_message.reply_text(
        f"⛔ Нет доступа.\nТвой Telegram ID: {uid}\n"
        "Добавь его в ALLOWED_USER_IDS в файле .env и перезапусти бота."
    )


# ---------- commands ----------

HELP = (
    "🎬 <b>Vimeo → папка</b>\n\n"
    "Просто пришли одну или несколько ссылок на Vimeo, я скачаю их и пришлю видео сюда.\n\n"
    "Видео под паролем: <code>https://vimeo.com/123 пароль: secret</code>\n"
    "Приватное видео с сайта: <code>https://player.vimeo.com/video/123 сайт: https://site.com</code>\n\n"
    "<b>Команды</b>\n"
    "/folder <i>Название</i>: складывать в подпапку (пустой /folder вернёт в корень)\n"
    "/quality best | 2160 | 1080 | 720 | 480: максимальное разрешение\n"
    "/audio: переключить режим «только звук mp3»\n"
    "/list: что лежит в текущей папке\n"
    "/settings: текущие настройки\n"
    "/id: показать твой Telegram ID"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return await deny(update)
    await update.message.reply_text(HELP, parse_mode=ParseMode.HTML)


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой Telegram ID: {update.effective_user.id}")


async def cmd_folder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return await deny(update)
    name = safe_folder(" ".join(context.args))
    save_user_setting(update.effective_user.id, "folder", name)
    await update.message.reply_text(f"📁 Папка: {target_dir(update.effective_user.id)}")


async def cmd_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return await deny(update)
    q = (context.args or [""])[0].lower().rstrip("p")
    if q not in vd.QUALITY_FORMATS:
        return await update.message.reply_text("Варианты: " + ", ".join(vd.QUALITY_FORMATS))
    save_user_setting(update.effective_user.id, "quality", q)
    await update.message.reply_text(f"🎞 Качество: {q}")


async def cmd_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return await deny(update)
    uid = update.effective_user.id
    value = not user_settings(uid)["audio_only"]
    save_user_setting(uid, "audio_only", value)
    await update.message.reply_text("🎧 Только звук (mp3)" if value else "🎬 Видео + звук")


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return await deny(update)
    s = user_settings(update.effective_user.id)
    await update.message.reply_text(
        f"📁 Папка: {target_dir(update.effective_user.id)}\n"
        f"🎞 Качество: {s['quality']}\n"
        f"🎧 Только звук: {'да' if s['audio_only'] else 'нет'}\n"
        f"📤 Присылать в чат: {'да' if SEND_TO_CHAT else 'нет'} (до {MAX_SEND_MB} МБ)\n"
        f"☁️ Облако: {RCLONE_REMOTE or 'выключено'}"
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return await deny(update)
    folder = target_dir(update.effective_user.id)
    files = sorted(
        (p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS | AUDIO_EXTS),
        key=lambda p: p.stat().st_mtime, reverse=True,
    ) if folder.exists() else []
    if not files:
        return await update.message.reply_text(f"В {folder} пока пусто.")
    lines = [f"• {p.name} ({p.stat().st_size / 1e6:.0f} МБ)" for p in files[:30]]
    more = f"\n…и ещё {len(files) - 30}" if len(files) > 30 else ""
    await update.message.reply_text(f"📁 {folder}\n\n" + "\n".join(lines) + more)


# ---------- downloading ----------

DOWNLOAD_LOCK = asyncio.Lock()  # one download at a time keeps bandwidth and disk sane


class Progress:
    """Throttled progress updates from yt-dlp's worker thread into a chat message."""

    def __init__(self, loop, status_msg, total):
        self.loop, self.msg, self.total = loop, status_msg, total
        self.index, self.last = 1, 0.0

    def hook(self, d):
        now = time.monotonic()
        if d.get("status") != "downloading" or now - self.last < 4:
            return
        self.last = now
        done = d.get("downloaded_bytes") or 0
        size = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        pct = f"{done / size * 100:.0f}%" if size else f"{done / 1e6:.0f} МБ"
        title = (d.get("info_dict") or {}).get("title") or ""
        text = f"⬇️ Скачиваю {self.index}/{self.total}: {pct}\n{title[:80]}"
        asyncio.run_coroutine_threadsafe(self._edit(text), self.loop)

    async def _edit(self, text):
        try:
            await self.msg.edit_text(text)
        except Exception:  # "message is not modified" and similar are harmless
            pass


async def upload_to_cloud(path: Path, folder: str):
    """Copy a file with rclone and return a share link if the remote supports it."""
    if not RCLONE_REMOTE or not shutil.which("rclone"):
        return None
    dest = f"{RCLONE_REMOTE}/{folder}" if folder else RCLONE_REMOTE
    proc = await asyncio.create_subprocess_exec(
        "rclone", "copy", str(path), dest,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        log.warning("rclone copy failed: %s", err.decode(errors="ignore"))
        return "⚠️ не удалось загрузить в облако"
    proc = await asyncio.create_subprocess_exec(
        "rclone", "link", f"{dest}/{path.name}",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    link = out.decode().strip()
    return link if proc.returncode == 0 and link else f"☁️ загружено в {dest}"


async def send_file(update: Update, path: Path):
    size_mb = path.stat().st_size / 1e6
    if not SEND_TO_CHAT or size_mb > MAX_SEND_MB:
        return False
    chat = update.effective_chat
    with path.open("rb") as fh:
        if path.suffix.lower() in VIDEO_EXTS:
            await chat.send_video(fh, caption=path.stem[:1000], supports_streaming=True)
        elif path.suffix.lower() in AUDIO_EXTS:
            await chat.send_audio(fh, caption=path.stem[:1000])
        else:
            await chat.send_document(fh, caption=path.stem[:1000])
    return True


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return await deny(update)
    text = update.message.text or update.message.caption or ""
    urls, password, referer = parse_request(text)
    if not urls:
        return await update.message.reply_text("Не вижу ссылок на Vimeo. /help покажет, как пользоваться.")

    uid = update.effective_user.id
    s = user_settings(uid)
    out_dir = target_dir(uid)
    queued = DOWNLOAD_LOCK.locked()
    status = await update.message.reply_text(
        ("⏳ В очереди, жду предыдущую загрузку…" if queued else "⬇️ Начинаю…")
        + f"\nСсылок: {len(urls)} → {out_dir}"
    )

    async with DOWNLOAD_LOCK:
        loop = asyncio.get_running_loop()
        progress = Progress(loop, status, len(urls))
        all_files, all_errors = [], []
        for i, url in enumerate(urls, 1):
            progress.index = i
            files, errors = await asyncio.to_thread(
                vd.download, [url], out_dir,
                progress_hook=progress.hook, echo=False,
                quality=s["quality"], audio_only=s["audio_only"],
                password=password, referer=referer,
                cookies_from_browser=COOKIES_FROM_BROWSER, cookies=COOKIES_FILE,
                archive=False,  # the bot re-sends files that are already on disk
            )
            all_files += [f for f in files if f not in all_files]
            all_errors += [f"{url}\n   {e}" for e in errors]

    lines = [f"✅ Готово: {len(all_files)} файл(ов) в {out_dir}"]
    for path in all_files:
        note = []
        try:
            if not await send_file(update, path):
                if SEND_TO_CHAT:
                    note.append(f"больше {MAX_SEND_MB} МБ, в чат не отправил")
        except Exception as exc:
            log.exception("send failed")
            note.append(f"не отправился в чат: {exc}")
        cloud = await upload_to_cloud(path, s["folder"])
        if cloud:
            note.append(cloud)
        size = path.stat().st_size / 1e6
        lines.append(f"• {path.name} ({size:.0f} МБ)" + (f"\n   {'; '.join(note)}" if note else ""))
    if all_errors:
        lines.append("\n❌ Не получилось:")
        lines += [f"• {e[:400]}" for e in all_errors]
        lines.append("\nЕсли видео приватное: добавь «пароль: …» или «сайт: …» к ссылке.")
    await status.edit_text("\n".join(lines)[:4000], disable_web_page_preview=True)


# ---------- startup ----------

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("help", "как пользоваться"),
        BotCommand("folder", "подпапка для загрузок"),
        BotCommand("quality", "максимальное разрешение"),
        BotCommand("audio", "только звук mp3 вкл/выкл"),
        BotCommand("list", "файлы в текущей папке"),
        BotCommand("settings", "текущие настройки"),
        BotCommand("id", "мой Telegram ID"),
    ])


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан. Запусти setup или заполни .env (см. .env.example).")
    if not shutil.which("ffmpeg"):
        log.warning("ffmpeg не найден: видео и звук не смогут склеиться в один mp4.")
    if not ALLOWED_USERS:
        log.warning("ALLOWED_USER_IDS пуст: бот будет только сообщать людям их ID. "
                    "Напиши боту /id, добавь число в .env и перезапусти.")
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    builder = (
        ApplicationBuilder().token(BOT_TOKEN).post_init(post_init)
        .connect_timeout(30).read_timeout(600).write_timeout(600).media_write_timeout(600)
        .concurrent_updates(True)
    )
    if TELEGRAM_API_URL:
        builder = (builder.base_url(f"{TELEGRAM_API_URL}/bot")
                   .base_file_url(f"{TELEGRAM_API_URL}/file/bot").local_mode(True))
    app = builder.build()

    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("folder", cmd_folder))
    app.add_handler(CommandHandler("quality", cmd_quality))
    app.add_handler(CommandHandler("audio", cmd_audio))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, on_message))

    log.info("Бот запущен. Папка загрузок: %s", DOWNLOAD_DIR)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
