"""
OAuth callback endpoints — Google and Twitter/X.
"""

import httpx
import base64
from fastapi import APIRouter, HTTPException
from models.schemas import OAuthCallbackRequest
from config.settings import settings
from config.database import query_one, execute
from utils.security import create_jwt

router = APIRouter(prefix="/api/auth", tags=["OAuth"])


def _format_user(user) -> dict:
    return {
        "id": str(user["id"]),
        "name": user["name"],
        "email": user["email"],
        "avatarUrl": user.get("avatar_url"),
        "isVerified": user["is_verified"],
    }


@router.post("/google/callback")
async def google_callback(body: OAuthCallbackRequest):
    """Exchange Google OAuth authorization code for JWT token."""
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google authentication is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )

    try:
        async with httpx.AsyncClient() as client:
            # 1. Exchange code for access token
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                json={
                    "code": body.code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=15.0,
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            # 2. Fetch user profile
            profile_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()

        google_id = profile.get("id")
        email = profile.get("email")
        name = profile.get("name")
        avatar_url = profile.get("picture")

        if not email:
            raise HTTPException(status_code=400, detail="Google account must have an email address.")

        # 3. Upsert user
        user = await query_one(
            "SELECT * FROM users WHERE google_id = $1 OR email = $2",
            [google_id, email]
        )

        if user:
            if not user.get("google_id"):
                await execute(
                    "UPDATE users SET google_id = $1, avatar_url = COALESCE(avatar_url, $2), is_verified = TRUE, updated_at = NOW() WHERE id = $3",
                    [google_id, avatar_url, user["id"]]
                )
        else:
            user = await query_one(
                """INSERT INTO users (name, email, google_id, avatar_url, is_verified)
                   VALUES ($1, $2, $3, $4, TRUE) RETURNING *""",
                [name or "Google User", email.lower(), google_id, avatar_url]
            )

        # 4. Issue JWT
        token = create_jwt(str(user["id"]), user["email"])
        return {"token": token, "user": _format_user(user)}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Google OAuth Error] {e}")
        raise HTTPException(status_code=500, detail="Google authentication failed. Please try again.")


@router.post("/twitter/callback")
async def twitter_callback(body: OAuthCallbackRequest):
    """Exchange Twitter/X OAuth authorization code for JWT token."""
    if not settings.twitter_client_id or not settings.twitter_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Twitter/X authentication is not configured. Please set TWITTER_CLIENT_ID and TWITTER_CLIENT_SECRET.",
        )

    try:
        credentials = base64.b64encode(
            f"{settings.twitter_client_id}:{settings.twitter_client_secret}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            # Exchange code for token
            token_resp = await client.post(
                "https://api.twitter.com/2/oauth2/token",
                data={
                    "code": body.code,
                    "grant_type": "authorization_code",
                    "client_id": settings.twitter_client_id,
                    "redirect_uri": settings.twitter_redirect_uri,
                    "code_verifier": body.codeVerifier or "challenge",
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {credentials}",
                },
                timeout=15.0,
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            # Fetch user profile
            me_resp = await client.get(
                "https://api.twitter.com/2/users/me?user.fields=profile_image_url,username",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            me_resp.raise_for_status()
            tw_data = me_resp.json()["data"]

        twitter_id = tw_data.get("id")
        name = tw_data.get("name")
        username = tw_data.get("username")
        avatar_url = tw_data.get("profile_image_url")
        mock_email = f"{username or twitter_id}@x.videonotes.ai"

        # Upsert user
        user = await query_one(
            "SELECT * FROM users WHERE twitter_id = $1 OR email = $2",
            [twitter_id, mock_email]
        )

        if user:
            if not user.get("twitter_id"):
                await execute(
                    "UPDATE users SET twitter_id = $1, avatar_url = COALESCE(avatar_url, $2), is_verified = TRUE, updated_at = NOW() WHERE id = $3",
                    [twitter_id, avatar_url, user["id"]]
                )
        else:
            user = await query_one(
                """INSERT INTO users (name, email, twitter_id, avatar_url, is_verified)
                   VALUES ($1, $2, $3, $4, TRUE) RETURNING *""",
                [name or "X User", mock_email, twitter_id, avatar_url]
            )

        token = create_jwt(str(user["id"]), user["email"])
        return {"token": token, "user": _format_user(user)}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Twitter/X OAuth Error] {e}")
        raise HTTPException(status_code=500, detail="Twitter/X authentication failed. Please try again.")
