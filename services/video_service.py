"""
Video service — job creation and queue submission.
"""

import os
from config.settings import settings
from models.video import (
    create_video,
    create_job,
    create_output,
    update_job_status,
    find_jobs_for_user,
    find_job_by_id_for_user,
    find_notes_by_job_id,
    get_user_stats,
)
from services.youtube_service import is_valid_youtube_url, extract_video_id, fetch_video_metadata
from utils.background import submit_job


def ensure_storage():
    """Ensure storage directories exist."""
    root = settings.storage_root
    dirs = [
        root,
        os.path.join(root, "uploads"),
        os.path.join(root, "temp"),
        os.path.join(root, "pdfs"),
        os.path.join(root, "frames"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


async def create_video_job_from_upload(
    user_id: str,
    file_path: str,
    mode: str,
    interval_seconds: int,
) -> dict:
    """Create a video processing job from an uploaded file."""
    ensure_storage()
    video = await create_video(user_id, "upload", None, file_path)
    job = await create_job(user_id, str(video["id"]), mode, interval_seconds)

    submit_job("process_video", {
        "jobId": str(job["id"]),
        "videoPath": file_path,
        "mode": mode,
        "intervalSeconds": interval_seconds,
        "userId": user_id,
    })

    return {"id": str(job["id"])}


async def create_video_job_from_youtube(
    user_id: str,
    youtube_url: str,
    mode: str,
    interval_seconds: int,
) -> dict:
    """Create a video processing job from a YouTube URL."""
    ensure_storage()

    if not is_valid_youtube_url(youtube_url):
        raise ValueError("Invalid YouTube URL. Please provide a valid youtube.com or youtu.be link.")

    video_id = extract_video_id(youtube_url)
    if not video_id:
        raise ValueError("Could not extract video ID from the YouTube URL.")

    # Fetch metadata (no API key needed)
    title = "YouTube Video"
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    try:
        metadata = await fetch_video_metadata(video_id)
        title = metadata["title"]
        thumbnail_url = metadata["thumbnailUrl"]
    except Exception:
        pass  # Metadata fetch is non-critical

    placeholder_path = f"youtube:{video_id}"
    video = await create_video(user_id, "youtube", youtube_url, placeholder_path, {
        "title": title,
        "youtube_url": youtube_url,
        "thumbnail_url": thumbnail_url,
    })

    job = await create_job(user_id, str(video["id"]), mode, interval_seconds)

    submit_job("process_video", {
        "jobId": str(job["id"]),
        "videoPath": placeholder_path,
        "youtubeUrl": youtube_url,
        "mode": mode,
        "intervalSeconds": interval_seconds,
        "userId": user_id,
        "title": title,
    })

    return {"id": str(job["id"])}


async def list_jobs_for_user(user_id: str, limit: int = None):
    """List jobs for a user."""
    return await find_jobs_for_user(user_id, limit)


async def get_job_for_user(user_id: str, job_id: str):
    """Get a single job for a user, including notes."""
    job = await find_job_by_id_for_user(user_id, job_id)
    if not job:
        return None

    # Fetch associated notes
    notes = await find_notes_by_job_id(job_id)
    job["notes"] = [
        {
            "id": str(n["id"]),
            "type": n["note_type"],
            "content": n["content"],
            "aiProvider": n.get("ai_provider"),
            "aiModel": n.get("ai_model"),
            "createdAt": n["created_at"].isoformat() if n.get("created_at") else None,
        }
        for n in notes
    ]

    return job


async def get_stats(user_id: str):
    """Get dashboard stats."""
    return await get_user_stats(user_id)


async def mark_job_processing(job_id: str):
    await update_job_status(job_id, "processing")


async def mark_job_failed(job_id: str, error_message: str = None):
    await update_job_status(job_id, "failed", error_message)


async def mark_job_completed(job_id: str, pdf_path: str, frame_count: int):
    await update_job_status(job_id, "completed")
    await create_output(job_id, pdf_path, frame_count)
