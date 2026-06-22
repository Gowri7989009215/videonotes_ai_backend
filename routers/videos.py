"""
Video upload and YouTube job creation endpoints.
"""

import os
import time
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from models.schemas import YouTubeJobRequest, CreateJobResponse
from services.video_service import (
    create_video_job_from_upload,
    create_video_job_from_youtube,
    ensure_storage,
)
from utils.security import get_current_user
from config.settings import settings

router = APIRouter(prefix="/api/videos", tags=["Videos"])


@router.post("/upload", response_model=CreateJobResponse, status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    mode: str = Form(...),
    intervalSeconds: str = Form("3"),
    user: dict = Depends(get_current_user),
):
    """Upload a video file for processing."""
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Only video files are allowed")

    interval = int(intervalSeconds)
    if mode not in ("frames", "frames+transcript"):
        raise HTTPException(status_code=400, detail="Invalid mode")

    ensure_storage()

    # Save uploaded file
    upload_dir = os.path.join(settings.storage_root, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    unique = hex(int(time.time() * 1000))[2:]
    filename = f"{unique}-{file.filename}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        job = await create_video_job_from_upload(user["id"], file_path, mode, interval)
        return {"jobId": job["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/youtube", response_model=CreateJobResponse, status_code=201)
async def create_youtube_job(
    body: YouTubeJobRequest,
    user: dict = Depends(get_current_user),
):
    """Create a processing job from a YouTube URL."""
    if body.mode not in ("frames", "frames+transcript"):
        raise HTTPException(status_code=400, detail="Invalid mode")

    try:
        job = await create_video_job_from_youtube(
            user["id"], body.youtubeUrl, body.mode, body.intervalSeconds
        )
        return {"jobId": job["id"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
