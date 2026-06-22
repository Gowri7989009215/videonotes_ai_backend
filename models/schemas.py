"""
Pydantic request/response schemas for FastAPI endpoints.
These automatically generate Swagger documentation.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime


# ============================================================
# Auth Schemas
# ============================================================

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's display name")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=1, description="User's password")


class LoginResponse(BaseModel):
    token: str
    user: dict


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, description="6-digit reset code")
    password: str = Field(..., min_length=8, max_length=128)


class OAuthCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Authorization code from OAuth provider")
    codeVerifier: Optional[str] = Field(None, description="PKCE code verifier (Twitter)")


# ============================================================
# User Schemas
# ============================================================

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    avatarUrl: Optional[str] = None
    isVerified: bool
    createdAt: Optional[str] = None


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


# ============================================================
# Video / Job Schemas
# ============================================================

class YouTubeJobRequest(BaseModel):
    youtubeUrl: str = Field(..., description="YouTube video URL")
    mode: str = Field(..., description="Processing mode: 'frames' or 'frames+transcript'")
    intervalSeconds: int = Field(3, ge=1, le=30, description="Frame extraction interval in seconds")


class JobOutputResponse(BaseModel):
    id: str
    pdfUrl: str
    frameCount: int
    createdAt: Optional[str] = None


class NoteResponse(BaseModel):
    id: str
    type: str
    content: Any
    aiProvider: Optional[str] = None
    aiModel: Optional[str] = None
    createdAt: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    mode: str
    intervalSeconds: int
    status: str
    progress: Optional[int] = 0
    createdAt: Optional[str] = None
    completedAt: Optional[str] = None
    videoId: Optional[str] = None
    errorMessage: Optional[str] = None
    output: Optional[JobOutputResponse] = None
    notes: Optional[List[NoteResponse]] = None


class JobListResponse(BaseModel):
    jobs: List[JobResponse]


class CreateJobResponse(BaseModel):
    jobId: str


# ============================================================
# Health Schemas
# ============================================================

class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    timestamp: str


# ============================================================
# Generic Message
# ============================================================

class MessageResponse(BaseModel):
    message: str
