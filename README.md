# Vimeo → папка + Telegram-бот

Кидаешь боту в Telegram ссылки на Vimeo. Он скачивает их в папку на компьютере или сервере и присылает видео обратно в чат. Подходит для референсов и мудбордов.

## Запуск за 5 минут

### 1. Создай бота в Telegram
1. Открой [@BotFather](https://t.me/BotFather) → `/newbot` → придумай имя.
2. Скопируй токен вида `123456789:AA...`.

### 2. Установи
**Mac / Linux:** открой Терминал в папке проекта и выполни
```bash
./setup.sh
```
**Windows:** дважды кликни `setup.bat`.

Установщик поставит Python-зависимости и ffmpeg, спросит токен, твой Telegram ID и папку для видео. Если ID не знаешь, пропусти этот шаг: бот сам покажет ID в ответ на `/id`.

### 3. Запусти
- Mac / Linux: `./run_bot.sh`
- Windows: `run_bot.bat`

Бот работает, пока открыто окно. Если ID не вписал при установке: напиши боту `/id`, вставь число в `ALLOWED_USER_IDS` в файле `.env` и перезапусти бота.

## Как пользоваться ботом

| Что пишешь | Что происходит |
|---|---|
| `https://vimeo.com/76979871` | скачает и пришлёт видео |
| несколько ссылок в одном сообщении | скачает все по очереди |
| `https://vimeo.com/123 пароль: secret` | видео под паролем |
| `https://player.vimeo.com/video/123 сайт: https://site.com` | приватное видео, встроенное на сайт |
| `/folder Nike Moodboard` | дальше складывать в подпапку |
| `/folder` | вернуться в основную папку |
| `/quality 1080` | ограничить разрешение (best, 2160, 1080, 720, 480) |
| `/audio` | переключить режим «только звук mp3» |
| `/list` | что лежит в текущей папке |
| `/settings` | текущие настройки |

Если видео уже есть в папке, бот не качает его заново, а просто присылает.

## Большие файлы (больше 50 МБ)

Обычный Telegram Bot API отправляет файлы до 50 МБ. Более тяжёлые видео всё равно скачиваются в папку, бот просто напишет, где они лежат. Отправлять в чат файлы до 2 ГБ можно двумя способами:

**Через Docker (проще всего):**
1. Получи `api_id` и `api_hash` на https://my.telegram.org → API development tools.
2. Допиши в `.env`:
   ```
   TELEGRAM_API_ID=...
   TELEGRAM_API_HASH=...
   TELEGRAM_API_URL=http://telegram-bot-api:8081
   ```
3. Запусти `docker compose --profile bigfiles up -d --build`.

**Или загружай в облако** (следующий раздел) и получай ссылку.

## Загрузка в Google Drive / Яндекс Диск / Dropbox

1. Установи [rclone](https://rclone.org/install/) и выполни `rclone config`. Создай подключение, например `gdrive` (тип Google Drive).
2. В `.env` укажи `RCLONE_REMOTE=gdrive:Vimeo`.

После этого каждое видео будет копироваться в облако, в ту же подпапку, что выбрана через `/folder`. Бот пришлёт ссылку на файл.

## Бот без выключений (сервер / NAS)

Чтобы бот работал круглосуточно без твоего компьютера, подойдёт любой VPS с Docker:
```bash
git clone <этот репозиторий> && cd <папка>
cp .env.example .env && nano .env      # токен и ID
docker compose up -d --build
```
Видео будут лежать в `./downloads` на сервере. Для rclone положи `rclone.conf` в `./rclone/`.

## Без бота: из терминала

```bash
.venv/bin/python vimeo_downloader.py https://vimeo.com/76979871
.venv/bin/python vimeo_downloader.py -o ~/Refs/Food -q 1080 --thumbnail --info links.txt
.venv/bin/python vimeo_downloader.py -p mypassword https://vimeo.com/123456789
.venv/bin/python vimeo_downloader.py --cookies-from-browser chrome https://vimeo.com/showcase/1234
```

## Через Claude Code

Агент `.claude/agents/vimeo-downloader.md` скачивает ссылки прямо из разговора с Claude Code. Открой Claude Code в этой папке и напиши: *«скачай в ~/Refs/Food: https://vimeo.com/...»*.

## Если что-то не качается

- **«Private video» / «login required»**: добавь `пароль:` или `сайт:` к ссылке, либо включи `COOKIES_FROM_BROWSER=chrome` в `.env` (для видео, доступных только после входа в твой аккаунт).
- **Всё перестало качаться**: Vimeo меняет плеер, а `run_bot` обновляет yt-dlp при каждом запуске. Просто перезапусти бота.
- **Видео без звука или два отдельных файла**: не установлен ffmpeg.

Качай только то, на что у тебя есть права: свои работы, ролики с кнопкой Download, референсы для личного использования.
