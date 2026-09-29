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


def build_options(args, out_dir):
    opts = {
        "format": QUALITY_FORMATS[args.quality],
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(uploader,channel|Unknown)s - %(title)s [%(id)s].%(ext)s"),
        "restrictfilenames": False,
        "windowsfilenames": True,
        "download_archive": str(out_dir / ".downloaded.txt"),
        "ignoreerrors": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "writethumbnail": args.thumbnail,
        "writesubtitles": args.subs,
        "subtitleslangs": ["all"],
        "writedescription": args.info,
        "writeinfojson": args.info,
        "quiet": False,
        "no_warnings": False,
    }
    if args.password:
        opts["videopassword"] = args.password
    if args.cookies_from_browser:
        opts["cookiesfrombrowser"] = (args.cookies_from_browser,)
    if args.cookies:
        opts["cookiefile"] = str(Path(args.cookies).expanduser())
    if args.referer:
        # Needed for videos that are only allowed to play embedded on a specific site.
        opts["http_headers"] = {"Referer": args.referer}
    if args.audio_only:
        opts["format"] = "bestaudio/best"
        opts.pop("merge_output_format")
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
    return opts


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
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving {len(urls)} link(s) to {out_dir}")

    with yt_dlp.YoutubeDL(build_options(args, out_dir)) as ydl:
        code = ydl.download(urls)

    print("Done." if code == 0 else "Finished with errors - see messages above.")
    sys.exit(code)


if __name__ == "__main__":
    main()
