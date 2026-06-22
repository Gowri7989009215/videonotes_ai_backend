"""
YouTube utility functions — URL parsing, metadata fetching, transcript fetching.
"""

import re
import httpx
from typing import Optional, List, Dict
from urllib.parse import urlparse, parse_qs


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various URL formats:
    - https://youtube.com/watch?v=...
    - https://youtu.be/...
    - https://youtube.com/shorts/...
    - https://youtube.com/embed/...
    - https://www.youtube.com/watch?v=...&list=...
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        host = host.replace("www.", "")

        # youtu.be/VIDEO_ID
        if host == "youtu.be":
            path = parsed.path.lstrip("/")
            return path.split("/")[0] if path else None

        if host in ("youtube.com", "m.youtube.com"):
            # /watch?v=VIDEO_ID
            params = parse_qs(parsed.query)
            if "v" in params:
                return params["v"][0]

            # /shorts/VIDEO_ID
            match = re.match(r"/shorts/([a-zA-Z0-9_-]+)", parsed.path)
            if match:
                return match.group(1)

            # /embed/VIDEO_ID
            match = re.match(r"/embed/([a-zA-Z0-9_-]+)", parsed.path)
            if match:
                return match.group(1)

            # /v/VIDEO_ID (old format)
            match = re.match(r"/v/([a-zA-Z0-9_-]+)", parsed.path)
            if match:
                return match.group(1)

        return None
    except Exception:
        return None


def is_valid_youtube_url(url: str) -> bool:
    """Validate that a URL is a supported YouTube URL."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").replace("www.", "")
        return host in ("youtube.com", "youtu.be", "m.youtube.com")
    except Exception:
        return False


async def fetch_video_metadata(video_id: str) -> Dict:
    """
    Fetch video metadata using YouTube's oEmbed API (no API key needed).
    """
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        async with httpx.AsyncClient() as client:
            resp = await client.get(oembed_url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return {
                "title": data.get("title", "Untitled Video"),
                "author": data.get("author_name", "Unknown"),
                "thumbnailUrl": data.get("thumbnail_url", f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"),
                "duration": 0,  # oEmbed doesn't provide duration
            }
    except Exception:
        return {
            "title": "Untitled Video",
            "author": "Unknown",
            "thumbnailUrl": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            "duration": 0,
        }


def fetch_youtube_transcript_sync(video_id: str) -> List[Dict]:
    """
    Fetch YouTube transcript using youtube-transcript-api (synchronous).
    Falls back to empty list if transcript unavailable.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        else:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)

        # Try to find English transcript first, then any available
        try:
            transcript = transcript_list.find_transcript(['en'])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except Exception:
                # Get any available transcript
                for t in transcript_list:
                    transcript = t
                    break
                else:
                    return []

        items = transcript.fetch()
        return [
            {
                "start": getattr(item, "start", item.get("start", item.get("offset", 0) / 1000 if isinstance(item, dict) and "offset" in item else 0) if isinstance(item, dict) else 0),
                "end": getattr(item, "start", item.get("start", 0) if isinstance(item, dict) else 0) + getattr(item, "duration", item.get("duration", 0) if isinstance(item, dict) else 0),
                "text": getattr(item, "text", item.get("text", "") if isinstance(item, dict) else ""),
            }
            for item in items
        ]
    except Exception as e:
        print(f"[YouTube] Transcript unavailable for {video_id}: {e}")
        return []
