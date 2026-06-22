"""
File serving endpoint for generated PDFs.
"""

import os
from urllib.parse import unquote
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/files", tags=["Files"])


@router.get("/{file_path:path}")
async def serve_file(file_path: str):
    """
    Serve a generated file (PDF, etc.) by its encoded path.
    This mirrors the Express static file serving at /api/files/<encoded-path>.
    """
    decoded_path = unquote(file_path)

    # Resolve to absolute path
    if os.path.isabs(decoded_path):
        absolute = decoded_path
    else:
        absolute = os.path.join(os.getcwd(), decoded_path)

    # Normalize and check for directory traversal
    absolute = os.path.normpath(absolute)

    if not os.path.exists(absolute):
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.isfile(absolute):
        raise HTTPException(status_code=400, detail="Not a file")

    # Determine content type
    ext = os.path.splitext(absolute)[1].lower()
    content_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    media_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=absolute,
        media_type=media_type,
        filename=os.path.basename(absolute),
    )
