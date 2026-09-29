#!/usr/bin/env python3
"""Download Vimeo videos straight into a folder.

Thin wrapper around yt-dlp with sensible defaults for building reference
libraries: best quality merged to MP4, readable file names, a download
archive so the same video is never fetched twice, and support for
password-protected / private videos.

Examples:
    python vimeo_downloader.py https://vimeo.com/76979871
    python vimeo_downloader.py -o ~/Refs/Moodboard links.txt
    python vimeo_downloader.py -p secret https://vimeo.com/123456789
    python vimeo_downloader.py --cookies-from-browser chrome https://vimeo.com/showcase/1234
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp is not installed. Run: pip install -r requirements.txt")

QUALITY_FORMATS = {
    "best": "bestvideo*+bestaudio/best",
    "2160": "bestvideo*[height<=2160]+bestaudio/best[height<=2160]",
    "1080": "bestvideo*[height<=1080]+bestaudio/best[height<=1080]",
    "720": "bestvideo*[height<=720]+bestaudio/best[height<=720]",
    "480": "bestvideo*[height<=480]+bestaudio/best[height<=480]",
}

URL_RE = re.compile(r"https?://(?:[\w-]+\.)*vimeo\.com/[^\s<>\"']+", re.IGNORECASE)


def find_vimeo_urls(text):
    """Pull every Vimeo link out of free text (chat messages, notes, emails)."""
    seen, urls = set(), []
    for url in URL_RE.findall(text or ""):
        url = url.rstrip(".,;:!?)]}»")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def collect_urls(sources):
    """Accept URLs directly or text files with one URL per line (# = comment)."""
    urls = []
    for src in sources:
        path = Path(src).expanduser()
        if not src.startswith(("http://", "https://")) and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
        else:
            urls.append(src)
    return urls


class _ErrorCollector:
    """yt-dlp logger that remembers errors so callers can report them."""

    def __init__(self, echo):
        self.echo = echo
        self.errors = []

    def debug(self, msg):
        if self.echo and not msg.startswith("[debug] "):
            print(msg)

    def info(self, msg):
        if self.echo:
            print(msg)

    def warning(self, msg):
        if self.echo:
            print(msg, file=sys.stderr)

    def error(self, msg):
        self.errors.append(re.sub(r"^ERROR:\s*", "", msg))
        if self.echo:
            print(msg, file=sys.stderr)


def build_options(out_dir, quality="best", password=None, referer=None,
                  cookies_from_browser=None, cookies=None, audio_only=False,
                  thumbnail=False, subs=False, info=False, archive=True):
    out_dir = Path(out_dir)
    opts = {
        "format": QUALITY_FORMATS[quality],
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(uploader,channel|Unknown)s - %(title).120B [%(id)s].%(ext)s"),
        "windowsfilenames": True,
        "ignoreerrors": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "writethumbnail": thumbnail,
        "writesubtitles": subs,
        "subtitleslangs": ["all"],
        "writedescription": info,
        "writeinfojson": info,
    }
    if archive:
        opts["download_archive"] = str(out_dir / ".downloaded.txt")
    if password:
        opts["videopassword"] = password
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookies:
        opts["cookiefile"] = str(Path(cookies).expanduser())
    if referer:
        # Needed for videos that are only allowed to play embedded on a specific site.
        opts["http_headers"] = {"Referer": referer}
    if audio_only:
        opts["format"] = "bestaudio/best"
        opts.pop("merge_output_format")
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
    return opts


def _final_paths(info):
    """Walk an extract_info() result (video or playlist) and yield saved files."""
    if not info:
        return
    if info.get("entries"):
        for entry in info["entries"]:
            yield from _final_paths(entry)
        return
    for item in info.get("requested_downloads") or []:
        path = item.get("filepath") or item.get("_filename")
        if path and Path(path).exists():
            yield Path(path)


def download(urls, out_dir, progress_hook=None, echo=True, **options):
    """Download urls into out_dir. Returns (list of saved files, list of error messages)."""
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = build_options(out_dir, **options)
    logger = _ErrorCollector(echo)
    opts["logger"] = logger
    if not echo:
        opts["noprogress"] = True
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    files = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        for url in urls:
            try:
                info = ydl.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError as exc:
                logger.error(str(exc))
                continue
            files.extend(p for p in _final_paths(info) if p not in files)
    return files, logger.errors


def main():
    parser = argparse.ArgumentParser(description="Download Vimeo videos into a folder.")
    parser.add_argument("sources", nargs="+", help="Vimeo URLs and/or .txt files with URLs")
    parser.add_argument("-o", "--output", default="downloads", help="target folder (default: ./downloads)")
    parser.add_argument("-q", "--quality", choices=QUALITY_FORMATS, default="best", help="max resolution")
    parser.add_argument("-p", "--password", help="password for protected videos")
    parser.add_argument("--referer", help="page URL where a private embed is hosted")
    parser.add_argument("--cookies-from-browser", metavar="BROWSER", help="chrome, firefox, safari, edge...")
    parser.add_argument("--cookies", metavar="FILE", help="cookies.txt in Netscape format")
    parser.add_argument("--audio-only", action="store_true", help="save only the soundtrack as mp3")
    parser.add_argument("--thumbnail", action="store_true", help="also save the poster frame")
    parser.add_argument("--subs", action="store_true", help="also save subtitles")
    parser.add_argument("--info", action="store_true", help="also save description + metadata json")
    args = parser.parse_args()

    urls = collect_urls(args.sources)
    if not urls:
        sys.exit("No URLs found.")

    out_dir = Path(args.output).expanduser().resolve()
    print(f"Saving {len(urls)} link(s) to {out_dir}")
    files, errors = download(
        urls, out_dir,
        quality=args.quality, password=args.password, referer=args.referer,
        cookies_from_browser=args.cookies_from_browser, cookies=args.cookies,
        audio_only=args.audio_only, thumbnail=args.thumbnail, subs=args.subs, info=args.info,
    )

    for f in files:
        print(f"  saved: {f.name}")
    if errors:
        print(f"Finished with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
