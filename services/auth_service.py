"""
Authentication service — register, login, verify, reset.
"""

import random
from datetime import datetime, timedelta, timezone
from utils.security import hash_password, verify_password, create_jwt
from models.user import find_user_by_email, create_user, mark_user_verified
from models.auth import (
    create_email_verification,
    consume_email_verification,
    create_password_reset,
    consume_password_reset,
)
from utils.email import send_verification_email, send_password_reset_email
from config.database import execute

EMAIL_CODE_TTL_MINUTES = 15


def _generate_code() -> str:
    """Generate a 6-digit verification code."""
    return str(random.randint(100000, 999999))


async def register_user(name: str, email: str, password: str):
    """Register a new user, send verification email."""
    existing = await find_user_by_email(email)
    if existing:
        raise ValueError("Email already registered")

    password_hash = hash_password(password)
    user = await create_user(name, email, password_hash)

    code = _generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=EMAIL_CODE_TTL_MINUTES)
    await create_email_verification(str(user["id"]), code, expires_at)
    await send_verification_email(user["email"], code)

    return user


async def login_user(email: str, password: str) -> dict:
    """Authenticate a user and return a JWT + user data."""
    user = await find_user_by_email(email)
    if not user:
        raise ValueError("Invalid email or password")

    if not user.get("password_hash"):
        raise ValueError("Invalid email or password")

    if not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid email or password")

    if not user["is_verified"]:
        raise ValueError("Please verify your email before logging in")

    token = create_jwt(str(user["id"]), user["email"])
    return {
        "user": user,
        "token": token,
    }


async def verify_email(email: str, code: str):
    """Verify a user's email with a 6-digit code."""
    user = await find_user_by_email(email)
    if not user:
        raise ValueError("User not found")
    ok = await consume_email_verification(str(user["id"]), code)
    if not ok:
        raise ValueError("Invalid or expired verification code")
    await mark_user_verified(str(user["id"]))


async def resend_verification(email: str):
    """Resend verification code to user's email."""
    user = await find_user_by_email(email)
    if not user:
        return  # Silently ignore for security

    code = _generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=EMAIL_CODE_TTL_MINUTES)
    await create_email_verification(str(user["id"]), code, expires_at)
    await send_verification_email(user["email"], code)


async def request_password_reset(email: str):
    """Send password reset code to user's email."""
    user = await find_user_by_email(email)
    if not user:
        return  # Silently ignore for security

    code = _generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=EMAIL_CODE_TTL_MINUTES)
    await create_password_reset(str(user["id"]), code, expires_at)
    await send_password_reset_email(user["email"], code)


async def reset_password(email: str, code: str, new_password: str):
    """Reset user's password using a valid reset code."""
    user = await find_user_by_email(email)
    if not user:
        raise ValueError("User not found")

    ok = await consume_password_reset(str(user["id"]), code)
    if not ok:
        raise ValueError("Invalid or expired reset code")

    new_hash = hash_password(new_password)
    await execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2::uuid",
        [new_hash, str(user["id"])]
    )
