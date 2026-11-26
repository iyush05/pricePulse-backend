from typing import AsyncGenerator
import structlog
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from app.config import settings

logger = structlog.get_logger(__name__)

Base = declarative_base()

# Attempt primary database connection (PostgreSQL/TimescaleDB), fallback to SQLite if unavailable/configured
db_url = settings.DATABASE_URL
if settings.SQLITE_DEV_FALLBACK and "sqlite" in settings.DATABASE_URL:
    db_url = settings.SQLITE_URL

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _ensure_missing_columns(sync_conn) -> None:
    """Apply lightweight additive column migrations for existing databases."""
    inspector = inspect(sync_conn)
    if "products" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("products")}
        if "is_available" not in columns:
            sync_conn.execute(
                text("ALTER TABLE products ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT true")
            )


async def init_db() -> None:
    """Create tables if they don't exist yet and ensure new columns exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_missing_columns)
