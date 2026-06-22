"""
Auth API endpoints — register, login, verify, reset.
"""

from fastapi import APIRouter, HTTPException
from models.schemas import (
    RegisterRequest,
    LoginRequest,
    LoginResponse,
    VerifyEmailRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from services.auth_service import (
    register_user,
    login_user,
    verify_email,
    resend_verification,
    request_password_reset,
    reset_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(body: RegisterRequest):
    """Register a new user account. A verification email will be sent."""
    try:
        await register_user(body.name.strip(), str(body.email).strip().lower(), body.password)
        return {"message": "Registered. Please verify your email."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(body: LoginRequest):
    """Login with email and password. Returns JWT token and user data."""
    try:
        result = await login_user(str(body.email).strip().lower(), body.password)
        user = result["user"]
        return {
            "token": result["token"],
            "user": {
                "id": str(user["id"]),
                "name": user["name"],
                "email": user["email"],
                "isVerified": user["is_verified"],
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email_endpoint(body: VerifyEmailRequest):
    """Verify email address with 6-digit code."""
    try:
        await verify_email(str(body.email).strip().lower(), body.code)
        return {"message": "Email verified"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification_endpoint(body: ResendVerificationRequest):
    """Resend verification code to email."""
    try:
        await resend_verification(str(body.email).strip().lower())
        return {"message": "If the email exists, a new code was sent."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest):
    """Request a password reset code."""
    try:
        await request_password_reset(str(body.email).strip().lower())
        return {"message": "If the email exists, a reset code was sent."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password_endpoint(body: ResetPasswordRequest):
    """Reset password using a valid reset code."""
    try:
        await reset_password(str(body.email).strip().lower(), body.code, body.password)
        return {"message": "Password updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
