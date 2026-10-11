from datetime import timedelta
import structlog
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.config import settings

logger = structlog.get_logger(__name__)


class AuthService:
    @staticmethod
    async def register(db: AsyncSession, data: RegisterRequest) -> Tuple[User, TokenResponse]:
        # Check if email is already taken
        existing = await db.execute(select(User).where(User.email == data.email.lower()))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists",
            )

        hashed = hash_password(data.password)
        user = User(
            email=data.email.lower(),
            password_hash=hashed,
            locale=data.locale or "en-US",
            notification_prefs={"email": True, "push": False, "webhook": False},
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        token_response = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return user, token_response

    @staticmethod
    async def login(db: AsyncSession, data: LoginRequest) -> Tuple[User, TokenResponse]:
        result = await db.execute(select(User).where(User.email == data.email.lower()))
        user = result.scalar_one_or_none()
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        token_response = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return user, token_response

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
        payload = decode_token(refresh_token_str, expected_type="refresh")
        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token or inactive user",
            )

        new_access_token = create_access_token(user.id)
        # Keep same refresh token or issue new one
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token_str,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    async def logout(redis_client: Optional[aioredis.Redis], token: str) -> None:
        if redis_client:
            try:
                # Blacklist token for duration of access token expiry
                ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
                await redis_client.set(f"blacklist:{token}", "1", ex=ttl)
            except Exception as e:
                logger.warning("Failed to blacklist token in Redis", error=str(e))
