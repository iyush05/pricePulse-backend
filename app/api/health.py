from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
import redis.asyncio as aioredis
from app.database import get_db
from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    # Check Database
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # Check Redis
    redis_ok = False
    try:
        client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=1.0)
        await client.ping()
        await client.aclose()
        redis_ok = True
    except Exception:
        redis_ok = False

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "version": "1.0.0",
        "service": settings.APP_NAME,
    }
