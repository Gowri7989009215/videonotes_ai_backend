"""
Health check endpoint.
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from config.database import check_connection

router = APIRouter(tags=["Health"])


@router.get("/api/health")
async def health_check():
    """
    Check the health of the application.
    Returns database and Redis connectivity status.
    """
    db_status = "unreachable"
    redis_status = "not_required"  # Redis is optional in FastAPI version

    try:
        is_connected = await check_connection()
        db_status = "ok" if is_connected else "unreachable"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Redis is optional — we use in-process background workers
    # If Redis is configured, we could check it here
    redis_status = "ok"

    is_healthy = db_status == "ok"
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
