from typing import List, Optional, Tuple
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.subscription import Subscription
from app.models.product import Product
from app.models.user import User
from app.schemas.subscription import SubscriptionUpdateRequest

logger = structlog.get_logger(__name__)


class SubscriptionService:
    @staticmethod
    async def list_user_subscriptions(
        db: AsyncSession,
        user: User,
        is_active: Optional[bool] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Subscription], int]:
        stmt = (
            select(Subscription)
            .options(selectinload(Subscription.product))
            .where(Subscription.user_id == user.id)
        )
        count_stmt = select(func.count(Subscription.id)).where(Subscription.user_id == user.id)

        if is_active is not None:
            stmt = stmt.where(Subscription.is_active == is_active)
            count_stmt = count_stmt.where(Subscription.is_active == is_active)

        offset = (page - 1) * limit
        stmt = stmt.order_by(Subscription.created_at.desc()).offset(offset).limit(limit)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        res = await db.execute(stmt)
        items = res.scalars().all()
        return list(items), total

    @staticmethod
    async def get_subscription(
        db: AsyncSession, user: User, subscription_id: str
    ) -> Subscription:
        stmt = (
            select(Subscription)
            .options(selectinload(Subscription.product))
            .where(Subscription.id == subscription_id, Subscription.user_id == user.id)
        )
        res = await db.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found",
            )
        return sub

    @staticmethod
    async def update_subscription(
        db: AsyncSession,
        user: User,
        subscription_id: str,
        update_data: SubscriptionUpdateRequest,
    ) -> Subscription:
        sub = await SubscriptionService.get_subscription(db, user, subscription_id)
        if update_data.target_price is not None:
            sub.target_price = update_data.target_price
        if update_data.is_active is not None:
            sub.is_active = update_data.is_active

        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return sub

    @staticmethod
    async def delete_subscription(
        db: AsyncSession, user: User, subscription_id: str
    ) -> None:
        sub = await SubscriptionService.get_subscription(db, user, subscription_id)
        sub.is_active = False
        db.add(sub)
        await db.commit()


subscription_service = SubscriptionService()
