"""
User profile endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from models.schemas import UserResponse, UpdateUserRequest, MessageResponse
from models.user import find_user_by_id, update_user_profile
from utils.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    db_user = await find_user_by_id(user["id"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(db_user["id"]),
        "name": db_user["name"],
        "email": db_user["email"],
        "avatarUrl": db_user.get("avatar_url"),
        "isVerified": db_user["is_verified"],
        "createdAt": db_user["created_at"].isoformat() if db_user.get("created_at") else None,
    }


@router.patch("/me")
async def update_me(body: UpdateUserRequest, user: dict = Depends(get_current_user)):
    """Update the current user's profile (name)."""
    updates = {}
    if body.name:
        updates["name"] = body.name.strip()

    db_user = await update_user_profile(user["id"], updates)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(db_user["id"]),
        "name": db_user["name"],
        "email": db_user["email"],
        "avatarUrl": db_user.get("avatar_url"),
        "isVerified": db_user["is_verified"],
        "createdAt": db_user["created_at"].isoformat() if db_user.get("created_at") else None,
    }
