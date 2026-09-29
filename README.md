# Vimeo Downloader

Скачивает видео с Vimeo прямо в папку. Подходит для сбора референсов и мудбордов.

## Установка (один раз)

```bash
pip install -r requirements.txt
# ffmpeg нужен, чтобы склеить видео и звук в один mp4:
brew install ffmpeg        # macOS
winget install ffmpeg      # Windows
```

## Как пользоваться

```bash
# одно видео в ./downloads
python3 vimeo_downloader.py https://vimeo.com/76979871

# пачка ссылок из файла в свою папку, максимум 1080p, с постером и описанием
python3 vimeo_downloader.py -o ~/Refs/Nike_Moodboard -q 1080 --thumbnail --info links.txt

# видео под паролем
python3 vimeo_downloader.py -p mypassword https://vimeo.com/123456789

# приватное видео, встроенное на сайт
python3 vimeo_downloader.py --referer https://site.com/page https://player.vimeo.com/video/123456789

# видео, доступное только после входа в аккаунт
python3 vimeo_downloader.py --cookies-from-browser chrome https://vimeo.com/showcase/1234
```

Ссылки, которые уже скачаны, пропускаются: список хранится в `.downloaded.txt` внутри папки.

## Через Claude Code

В репозитории есть агент `.claude/agents/vimeo-downloader.md`. Открой Claude Code в этой папке на своём компьютере и напиши, например:

> скачай эти ролики в ~/Refs/Food: https://vimeo.com/..., https://vimeo.com/...

Claude передаст задачу агенту, тот скачает видео и покажет, что получилось.

Скачивай только то, на что у тебя есть права: свои работы, ролики с включённой кнопкой Download, материалы для личного референса.
