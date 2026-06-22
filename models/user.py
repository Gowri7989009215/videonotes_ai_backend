"""
User database CRUD operations.
"""

from typing import Optional, Dict, Any
from config.database import query_one, execute


async def find_user_by_email(email: str):
    """Find a user by email (case-insensitive)."""
    return await query_one(
        "SELECT * FROM users WHERE email = $1",
        [email.lower()]
    )


async def find_user_by_id(user_id: str):
    """Find a user by UUID."""
    return await query_one(
        "SELECT * FROM users WHERE id = $1::uuid",
        [user_id]
    )


async def create_user(name: str, email: str, password_hash: str):
    """Create a new user and return the record."""
    return await query_one(
        "INSERT INTO users (name, email, password_hash) VALUES ($1, $2, $3) RETURNING *",
        [name, email.lower(), password_hash]
    )


async def mark_user_verified(user_id: str) -> None:
    """Mark a user's email as verified."""
    await execute(
        "UPDATE users SET is_verified = true, updated_at = NOW() WHERE id = $1::uuid",
        [user_id]
    )


async def update_user_profile(user_id: str, updates: Dict[str, Any]):
    """Update user profile fields (name, avatar_url)."""
    sets = []
    params = []
    idx = 1

    if updates.get("name"):
        sets.append(f"name = ${idx}")
        params.append(updates["name"])
        idx += 1

    if updates.get("avatar_url"):
        sets.append(f"avatar_url = ${idx}")
        params.append(updates["avatar_url"])
        idx += 1

    if not sets:
        return await find_user_by_id(user_id)

    sets.append("updated_at = NOW()")
    params.append(user_id)

    sql = f"UPDATE users SET {', '.join(sets)} WHERE id = ${idx}::uuid RETURNING *"
    return await query_one(sql, params)
