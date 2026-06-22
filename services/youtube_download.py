"""
YouTube video download service using yt-dlp.
This replaces the Node.js youtube-dl-exec which was causing failures.
"""

import os
import yt_dlp


def download_youtube_video(video_url: str, output_path: str) -> None:
    """
    Download a YouTube video using yt-dlp.
    Much more reliable than youtube-dl-exec.
    """
    print(f"[Download] Starting download from {video_url}")

    ydl_opts = {
    "cookiefile": "cookies.txt",
    "format": "18/best",
    "outtmpl": output_path,
    "noplaylist": True,
    "quiet": False,
    "merge_output_format": "mp4",
}


    print("cookies exists:", os.path.exists("cookies.txt"))
    print("starting yt-dlp download")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        print("Available formats:")
        for f in info.get("formats", []):
            print(f.get("format_id"), f.get("ext"))

    # Verify file was created
    # yt-dlp may add extension, try common patterns
    actual_path = output_path
    if not os.path.exists(actual_path):
        # Try with .mp4 extension if not already
        if not actual_path.endswith(".mp4"):
            if os.path.exists(actual_path + ".mp4"):
                actual_path = actual_path + ".mp4"
                os.rename(actual_path, output_path)

    if not os.path.exists(output_path):
        # Check if file exists with different extension
        base = os.path.splitext(output_path)[0]
        for ext in [".mp4", ".mkv", ".webm"]:
            candidate = base + ext
            if os.path.exists(candidate):
                os.rename(candidate, output_path)
                break

    if not os.path.exists(output_path):
        raise RuntimeError("Download failed - file not created")

    file_size = os.path.getsize(output_path)
    print(f"[Download] Download complete: {output_path} ({file_size / 1024 / 1024:.2f} MB)")

    # Check if file is too small (likely failed download)
    if file_size < 500 * 1024:  # 500KB
        raise RuntimeError(
            f"Downloaded file too small ({file_size / 1024:.2f} KB) - "
            "likely a failed download or corrupted video"
        )


def get_video_info(video_url: str) -> dict:
    """Get video metadata using yt-dlp."""
    print(f"[Download] Getting video info for {video_url}")

    ydl_opts = {
        "no_check_certificate": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnail", ""),
        }
