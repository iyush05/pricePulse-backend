import asyncio
from datetime import datetime, timezone
import hashlib
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.product import Product
from app.models.alert import Alert
from app.models.price_history import PriceHistory
from app.workers.notification_tasks import dispatch_alert_notification

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.workers.alert_tasks.evaluate_alerts")
def evaluate_alerts(product_id: str, new_price: float):
    """
    Evaluates target-price crosses and trailing drops with idempotent dispatch rules.
    """
    async def _evaluate():
        async with AsyncSessionLocal() as db:
            product = await db.get(Product, product_id)
            if not product:
                return

            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # 1. Target-Price Crosses
            sub_query = select(Subscription).where(
                Subscription.product_id == product_id,
                Subscription.is_active == True,
                Subscription.target_price.isnot(None),
                Subscription.target_price >= new_price,
            )
            subs_res = await db.execute(sub_query)
            matching_subs = subs_res.scalars().all()

            for sub in matching_subs:
                idem_key = f"target_cross:{sub.id}:{today_str}:{round(new_price, 2)}"
                # Check idempotency
                existing_alert = await db.execute(
                    select(Alert).where(Alert.idempotency_key == idem_key)
                )
                if not existing_alert.scalar_one_or_none():
                    alert = Alert(
                        subscription_id=sub.id,
                        trigger_price=new_price,
                        channel="email",
                        trigger_type="target_cross",
                        idempotency_key=idem_key,
                        is_read=False,
                    )
                    db.add(alert)
                    await db.commit()
                    await db.refresh(alert)
                    # Dispatch notification asynchronously
                    dispatch_alert_notification.delay(alert.id)
                    logger.info("Fired target-price alert", subscription_id=sub.id, price=new_price)

            # 2. Trailing Drops (e.g. price drops >= 10% below 7-day max)
            hist_query = (
                select(PriceHistory.price)
                .where(PriceHistory.product_id == product_id)
                .order_by(PriceHistory.observed_at.desc())
                .limit(28)  # ~7 days of 6-hour polls
            )
            hist_res = await db.execute(hist_query)
            recent_prices = [float(p) for p in hist_res.scalars().all()]

            if recent_prices:
                max_7d = max(recent_prices)
                if max_7d > 0 and (max_7d - new_price) / max_7d >= 0.10:
                    # Notify all active subscribers of this product
                    all_subs_res = await db.execute(
                        select(Subscription).where(
                            Subscription.product_id == product_id,
                            Subscription.is_active == True,
                        )
                    )
                    for sub in all_subs_res.scalars().all():
                        idem_key = f"trailing_drop:{sub.id}:{today_str}:{round(new_price, 2)}"
                        existing_alert = await db.execute(
                            select(Alert).where(Alert.idempotency_key == idem_key)
                        )
                        if not existing_alert.scalar_one_or_none():
                            alert = Alert(
                                subscription_id=sub.id,
                                trigger_price=new_price,
                                channel="email",
                                trigger_type="trailing_drop",
                                idempotency_key=idem_key,
                                is_read=False,
                            )
                            db.add(alert)
                            await db.commit()
                            await db.refresh(alert)
                            dispatch_alert_notification.delay(alert.id)
                            logger.info("Fired trailing-drop alert", subscription_id=sub.id, price=new_price)

    asyncio.run(_evaluate())
