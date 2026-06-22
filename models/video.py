"""
Video, Job, Output, and Note database CRUD operations.
"""

from typing import Optional, List, Any
from config.database import query, query_one, execute
from urllib.parse import quote
import json


# ============================================================
# Video CRUD
# ============================================================

async def create_video(
    user_id: str,
    input_type: str,
    source_url: Optional[str],
    file_path: str,
    extra: Optional[dict] = None
):
    """Create a new video record."""
    extra = extra or {}
    return await query_one(
        """INSERT INTO videos (user_id, input_type, source_url, file_path, title, youtube_url, thumbnail_url, duration_seconds)
           VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8) RETURNING *""",
        [
            user_id,
            input_type,
            source_url,
            file_path,
            extra.get("title"),
            extra.get("youtube_url"),
            extra.get("thumbnail_url"),
            extra.get("duration_seconds"),
        ]
    )


# ============================================================
# Job CRUD
# ============================================================

async def create_job(user_id: str, video_id: str, mode: str, interval_seconds: int):
    """Create a new processing job."""
    return await query_one(
        "INSERT INTO jobs (user_id, video_id, mode, interval_seconds, status) VALUES ($1::uuid, $2::uuid, $3, $4, $5) RETURNING *",
        [user_id, video_id, mode, interval_seconds, "pending"]
    )


async def update_job_status(job_id: str, status: str, error_message: Optional[str] = None):
    """Update job status and optionally set completed_at."""
    if status in ("completed", "failed"):
        await execute(
            "UPDATE jobs SET status = $1, error_message = $2, completed_at = NOW() WHERE id = $3::uuid",
            [status, error_message, job_id]
        )
    else:
        await execute(
            "UPDATE jobs SET status = $1, error_message = $2 WHERE id = $3::uuid",
            [status, error_message, job_id]
        )


async def update_job_progress(job_id: str, progress: int):
    """Update job progress (0-100)."""
    clamped = max(0, min(100, progress))
    await execute(
        "UPDATE jobs SET progress = $1 WHERE id = $2::uuid",
        [clamped, job_id]
    )


# ============================================================
# Output CRUD
# ============================================================

async def create_output(job_id: str, pdf_path: str, frame_count: int):
    """Create an output record for a completed job."""
    return await query_one(
        "INSERT INTO outputs (job_id, pdf_path, frame_count) VALUES ($1::uuid, $2, $3) RETURNING *",
        [job_id, pdf_path, frame_count]
    )


# ============================================================
# Notes CRUD
# ============================================================

async def create_note(
    job_id: str,
    user_id: str,
    note_type: str,
    content: Any,
    ai_provider: Optional[str] = None,
    ai_model: Optional[str] = None
):
    """Create a note record."""
    content_json = json.dumps(content) if not isinstance(content, str) else content
    return await query_one(
        """INSERT INTO notes (job_id, user_id, note_type, content, ai_provider, ai_model)
           VALUES ($1::uuid, $2::uuid, $3, $4::jsonb, $5, $6) RETURNING *""",
        [job_id, user_id, note_type, content_json, ai_provider, ai_model]
    )


async def find_notes_by_job_id(job_id: str):
    """Find all notes for a job."""
    return await query(
        "SELECT * FROM notes WHERE job_id = $1::uuid ORDER BY created_at",
        [job_id]
    )


# ============================================================
# Query helpers
# ============================================================

async def find_jobs_for_user(user_id: str, limit: Optional[int] = None):
    """Find all jobs for a user with their output info."""
    safe_limit = limit if limit and limit > 0 else 50
    rows = await query(
        """SELECT DISTINCT j.*, o.id as output_id, o.pdf_path, o.frame_count, o.created_at as output_created_at
           FROM jobs j
           LEFT JOIN outputs o ON o.job_id = j.id
           WHERE j.user_id = $1::uuid
           ORDER BY j.created_at DESC
           LIMIT $2""",
        [user_id, safe_limit]
    )
    return [_format_job_row(row) for row in rows]


async def find_job_by_id_for_user(user_id: str, job_id: str):
    """Find a single job for a user with output info."""
    row = await query_one(
        """SELECT j.*, o.id as output_id, o.pdf_path, o.frame_count, o.created_at as output_created_at
           FROM jobs j
           LEFT JOIN outputs o ON o.job_id = j.id
           WHERE j.user_id = $1::uuid AND j.id = $2::uuid""",
        [user_id, job_id]
    )
    if not row:
        return None
    return _format_job_row(row)


def _format_job_row(row) -> dict:
    """Format a job database row into API-friendly dict."""
    output = None
    if row.get("output_id"):
        pdf_path = row.get("pdf_path", "")
        output = {
            "id": str(row["output_id"]),
            "pdfUrl": f"/api/files/{quote(pdf_path, safe='')}" if pdf_path else "",
            "frameCount": row.get("frame_count", 0),
            "createdAt": row["output_created_at"].isoformat() if row.get("output_created_at") else None,
        }

    return {
        "id": str(row["id"]),
        "mode": row["mode"],
        "intervalSeconds": row["interval_seconds"],
        "status": row["status"],
        "progress": row.get("progress", 0),
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
        "completedAt": row["completed_at"].isoformat() if row.get("completed_at") else None,
        "videoId": str(row["video_id"]) if row.get("video_id") else None,
        "errorMessage": row.get("error_message"),
        "output": output,
    }


# ============================================================
# Stats (for dashboard)
# ============================================================

async def get_user_stats(user_id: str) -> dict:
    """Get dashboard stats for a user."""
    results = await query(
        """SELECT
             (SELECT COUNT(*) FROM videos WHERE user_id = $1::uuid) as total_videos,
             (SELECT COUNT(*) FROM jobs WHERE user_id = $1::uuid) as total_jobs,
             (SELECT COUNT(*) FROM jobs WHERE user_id = $1::uuid AND status = 'completed') as completed_jobs,
             (SELECT COUNT(*) FROM notes WHERE user_id = $1::uuid) as total_notes""",
        [user_id]
    )
    row = results[0] if results else None
    if not row:
        return {"totalVideos": 0, "totalJobs": 0, "completedJobs": 0, "totalNotes": 0}
    return {
        "totalVideos": int(row["total_videos"]),
        "totalJobs": int(row["total_jobs"]),
        "completedJobs": int(row["completed_jobs"]),
        "totalNotes": int(row["total_notes"]),
    }
