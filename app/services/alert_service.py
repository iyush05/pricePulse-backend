from typing import List, Optional, Tuple
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.alert import Alert
from app.models.subscription import Subscription
from app.models.user import User

logger = structlog.get_logger(__name__)


class AlertService:
    @staticmethod
    async def list_alerts(
        db: AsyncSession,
        user: User,
        unread_only: bool = False,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Alert], int, int]:
        stmt = (
            select(Alert)
            .join(Subscription, Alert.subscription_id == Subscription.id)
            .options(
                selectinload(Alert.subscription).selectinload(Subscription.product)
            )
            .where(Subscription.user_id == user.id)
        )
        count_stmt = (
            select(func.count(Alert.id))
            .join(Subscription, Alert.subscription_id == Subscription.id)
            .where(Subscription.user_id == user.id)
        )
        unread_stmt = (
            select(func.count(Alert.id))
            .join(Subscription, Alert.subscription_id == Subscription.id)
            .where(Subscription.user_id == user.id, Alert.is_read == False)
        )

        if unread_only:
            stmt = stmt.where(Alert.is_read == False)
            count_stmt = count_stmt.where(Alert.is_read == False)

        offset = (page - 1) * limit
        stmt = stmt.order_by(Alert.fired_at.desc()).offset(offset).limit(limit)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        unread_res = await db.execute(unread_stmt)
        unread_count = unread_res.scalar() or 0

        res = await db.execute(stmt)
        alerts = res.scalars().all()
        return list(alerts), total, unread_count

    @staticmethod
    async def get_alert(db: AsyncSession, user: User, alert_id: str) -> Alert:
        stmt = (
            select(Alert)
            .join(Subscription, Alert.subscription_id == Subscription.id)
            .options(
                selectinload(Alert.subscription).selectinload(Subscription.product)
            )
            .where(Alert.id == alert_id, Subscription.user_id == user.id)
        )
        res = await db.execute(stmt)
        alert = res.scalar_one_or_none()
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found",
            )
        return alert

    @staticmethod
    async def mark_read(db: AsyncSession, user: User, alert_id: str) -> Alert:
        alert = await AlertService.get_alert(db, user, alert_id)
        alert.is_read = True
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        return alert

    @staticmethod
    async def mark_all_read(db: AsyncSession, user: User) -> int:
        # Get subscription IDs for this user
        sub_query = select(Subscription.id).where(Subscription.user_id == user.id)
        subs = (await db.execute(sub_query)).scalars().all()
        if not subs:
            return 0

        update_stmt = (
            update(Alert)
            .where(Alert.subscription_id.in_(subs), Alert.is_read == False)
            .values(is_read=True)
        )
        res = await db.execute(update_stmt)
        await db.commit()
        return res.rowcount or 0


alert_service = AlertService()
