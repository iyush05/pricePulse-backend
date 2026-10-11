from typing import Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.subscription import Subscription
from app.models.alert import Alert
from app.models.product import Product
from app.schemas.user import UserUpdateRequest, UserStatsResponse

logger = structlog.get_logger(__name__)


class UserService:
    @staticmethod
    async def update_profile(
        db: AsyncSession, user: User, update_data: UserUpdateRequest
    ) -> User:
        if update_data.email:
            user.email = update_data.email.lower()
        if update_data.locale:
            user.locale = update_data.locale
        if update_data.notification_prefs is not None:
            # Merge existing prefs
            prefs = dict(user.notification_prefs or {})
            prefs.update(update_data.notification_prefs)
            user.notification_prefs = prefs

        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def delete_account(db: AsyncSession, user: User) -> None:
        await db.delete(user)
        await db.commit()

    @staticmethod
    async def get_stats(db: AsyncSession, user: User) -> UserStatsResponse:
        # Total tracked subscriptions
        sub_query = select(func.count(Subscription.id)).where(Subscription.user_id == user.id)
        sub_res = await db.execute(sub_query)
        tracked_count = sub_res.scalar() or 0

        # Active subscriptions
        active_sub_query = select(func.count(Subscription.id)).where(
            Subscription.user_id == user.id, Subscription.is_active == True
        )
        active_res = await db.execute(active_sub_query)
        active_count = active_res.scalar() or 0

        # Alerts fired for this user
        alert_query = (
            select(func.count(Alert.id))
            .join(Subscription, Alert.subscription_id == Subscription.id)
            .where(Subscription.user_id == user.id)
        )
        alert_res = await db.execute(alert_query)
        alerts_fired = alert_res.scalar() or 0

        # Estimated savings: for active subscriptions, sum(all_time_high - current_price) if positive
        savings_query = (
            select(
                func.sum(
                    func.coalesce(Product.all_time_high - Product.last_price, 0)
                )
            )
            .join(Subscription, Subscription.product_id == Product.id)
            .where(
                Subscription.user_id == user.id,
                Product.all_time_high.isnot(None),
                Product.last_price.isnot(None),
                Product.all_time_high > Product.last_price,
            )
        )
        savings_res = await db.execute(savings_query)
        savings = savings_res.scalar() or 0.0

        return UserStatsResponse(
            tracked_count=tracked_count,
            alerts_fired=alerts_fired,
            active_subscriptions=active_count,
            savings_estimate=round(float(savings), 2),
        )
