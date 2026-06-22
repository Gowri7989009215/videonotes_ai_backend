"""
Application settings loaded from environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """All configuration values for the FastAPI backend."""

    # Server
    port: int = 4000
    node_env: str = "development"  # kept for compat naming

    # Database
    database_url: str = ""

    # JWT
    jwt_secret: str = "changeme-use-long-secret-in-production"
    jwt_refresh_secret: str = "changeme-refresh-secret"
    jwt_expire_days: int = 7

    # Redis (optional)
    redis_url: str = "redis://localhost:6379"

    # CORS
    frontend_url: str = "http://localhost:5173"
    allowed_origins: str = "http://localhost:5173"

    # AI Providers
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:5173/login"

    # Twitter / X OAuth
    twitter_client_id: str = ""
    twitter_client_secret: str = ""
    twitter_redirect_uri: str = "http://localhost:5173/login"

    # Email
    resend_api_key: str = ""
    email_from: str = ""
    gmail_user: str = ""
    gmail_pass: str = ""

    # Storage
    storage_root: str = "storage"

    @property
    def is_prod(self) -> bool:
        return self.node_env == "production"

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def asyncpg_url(self) -> str:
        """Convert postgresql:// to a format asyncpg accepts."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars


# Singleton
settings = Settings()

# Warnings
if not settings.database_url:
    print("[Config] WARNING: DATABASE_URL is not set — database connections will fail.")

if not settings.openai_api_key and not settings.gemini_api_key and not settings.anthropic_api_key:
    print("[Config] WARNING: No AI provider API key set — AI notes generation will be disabled.")
