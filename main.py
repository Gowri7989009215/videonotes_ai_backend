"""
VideoNotes AI — FastAPI Backend
================================
Main application entry point with Swagger UI enabled.

Swagger UI:  http://localhost:4000/docs
ReDoc:       http://localhost:4000/redoc
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load .env BEFORE importing settings
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from config.settings import settings
from config.database import get_pool, close_pool
from utils.background import register_handler, shutdown as shutdown_background
from workers.video_processor import process_video_job

# Import routers
from routers.auth import router as auth_router
from routers.oauth import router as oauth_router
from routers.users import router as users_router
from routers.videos import router as videos_router
from routers.jobs import router as jobs_router
from routers.files import router as files_router
from routers.health import router as health_router




load_dotenv()

cookies = os.getenv("YOUTUBE_COOKIES")

if cookies:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    print("=" * 60)
    print("  VideoNotes AI — FastAPI Backend Starting")
    print("=" * 60)

    # Initialize database pool
    try:
        await get_pool()
        print("[Startup] Database connection pool initialized.")
    except Exception as e:
        print(f"[Startup] WARNING: Database connection failed: {e}")

    # Register background worker
    register_handler("process_video", process_video_job)
    print("[Startup] Background video processing worker registered.")

    # Ensure storage directories exist
    root = settings.storage_root
    for d in [root, f"{root}/uploads", f"{root}/temp", f"{root}/pdfs", f"{root}/frames"]:
        os.makedirs(d, exist_ok=True)
    print(f"[Startup] Storage directories ensured at: {os.path.abspath(root)}")

    print(f"[Startup] Swagger UI: http://localhost:{settings.port}/docs")
    print(f"[Startup] ReDoc:      http://localhost:{settings.port}/redoc")
    print(f"[Startup] API base:   http://localhost:{settings.port}/api")
    print("=" * 60)

    yield

    # Shutdown
    print("[Shutdown] Closing connections...")
    shutdown_background()
    await close_pool()
    print("[Shutdown] Complete.")


# Create FastAPI app with Swagger UI
app = FastAPI(
    title="VideoNotes AI API",
    description="""
**VideoNotes AI** turns long-form videos into concise visual notes.

## Features
- 🎥 Upload videos or paste YouTube links
- 📸 Extract frames at configurable intervals
- 📝 AI-generated transcripts and notes
- 📄 PDF generation with frames + transcripts
- 🤖 AI summaries, flashcards, quizzes, and more

## Authentication
All protected endpoints require a JWT token in the `Authorization: Bearer <token>` header.
Get a token by calling `POST /api/auth/login`.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for better error messages
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return JSON error responses instead of HTML for unhandled exceptions."""
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"message": str(exc)},
    )


# Register all routers
app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(users_router)
app.include_router(videos_router)
app.include_router(jobs_router)
app.include_router(files_router)
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level="info",
    )
