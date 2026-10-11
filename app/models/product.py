import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.config import settings


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    canonical_key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    region: Mapped[str] = mapped_column(String(10), default="US", nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    poll_interval_s: Mapped[int] = mapped_column(
        Integer, default=settings.DEFAULT_POLL_INTERVAL_S, nullable=False
    )
    next_poll_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )
    is_dormant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Denormalized aggregates for sub-millisecond retrieval
    last_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    all_time_low: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    all_time_high: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    last_observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="product", cascade="all, delete-orphan")
    price_records = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
