"""
Email verification and password reset database operations.
"""

from config.database import query_one, execute
from datetime import datetime


async def create_email_verification(user_id: str, code: str, expires_at: datetime) -> None:
    """Create an email verification record."""
    await execute(
        "INSERT INTO email_verifications (user_id, verification_code, expires_at) VALUES ($1::uuid, $2, $3)",
        [user_id, code, expires_at]
    )


async def consume_email_verification(user_id: str, code: str) -> bool:
    """
    Consume (delete) a valid verification code.
    Returns True if a matching, non-expired code was found and deleted.
    """
    result = await query_one(
        "DELETE FROM email_verifications WHERE user_id = $1::uuid AND verification_code = $2 AND expires_at > NOW() RETURNING *",
        [user_id, code]
    )
    return result is not None


async def create_password_reset(user_id: str, code: str, expires_at: datetime) -> None:
    """Create a password reset record."""
    await execute(
        "INSERT INTO password_resets (user_id, reset_code, expires_at) VALUES ($1::uuid, $2, $3)",
        [user_id, code, expires_at]
    )


async def consume_password_reset(user_id: str, code: str) -> bool:
    """
    Consume (delete) a valid password reset code.
    Returns True if a matching, non-expired code was found and deleted.
    """
    result = await query_one(
        "DELETE FROM password_resets WHERE user_id = $1::uuid AND reset_code = $2 AND expires_at > NOW() RETURNING *",
        [user_id, code]
    )
    return result is not None
