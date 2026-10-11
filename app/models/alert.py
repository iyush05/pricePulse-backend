import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    trigger_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), default="email", nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(50), default="target_cross", nullable=False
    )  # "target_cross", "trailing_drop", "buy_signal"
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    # Relationships
    subscription = relationship("Subscription", back_populates="alerts")
