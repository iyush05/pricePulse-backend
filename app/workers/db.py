from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.database import db_url


@asynccontextmanager
async def worker_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a NullPool async session scoped to a single Celery asyncio.run() loop."""
    worker_engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(
        bind=worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    try:
        async with session_factory() as session:
            yield session
    finally:
        await worker_engine.dispose()

