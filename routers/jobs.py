"""
Job listing and detail endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from services.video_service import list_jobs_for_user, get_job_for_user, get_stats
from utils.security import get_current_user

router = APIRouter(tags=["Jobs"])


@router.get("/api/jobs")
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """List all jobs for the current user."""
    jobs = await list_jobs_for_user(user["id"], limit)
    return {"jobs": jobs}


@router.get("/api/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    """Get detailed job status including output and notes."""
    job = await get_job_for_user(user["id"], job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# Also mount under /api/videos/jobs for backward compatibility
@router.get("/api/videos/jobs")
async def list_jobs_compat(
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """List all jobs (backward compatible path)."""
    jobs = await list_jobs_for_user(user["id"], limit)
    return {"jobs": jobs}


@router.get("/api/videos/jobs/{job_id}")
async def get_job_compat(job_id: str, user: dict = Depends(get_current_user)):
    """Get job details (backward compatible path)."""
    job = await get_job_for_user(user["id"], job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """Get dashboard statistics for the current user."""
    stats = await get_stats(user["id"])
    return stats
