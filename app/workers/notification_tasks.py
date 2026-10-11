import asyncio
import structlog
from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.alert import Alert
from app.models.subscription import Subscription
from app.models.user import User
from app.models.product import Product
from app.notifications import email_notifier, push_notifier, webhook_notifier

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.workers.notification_tasks.dispatch_alert_notification")
def dispatch_alert_notification(alert_id: str):
    async def _dispatch():
        async with AsyncSessionLocal() as db:
            alert = await db.get(Alert, alert_id)
            if not alert:
                return

            sub = await db.get(Subscription, alert.subscription_id)
            if not sub:
                return

            user = await db.get(User, sub.user_id)
            product = await db.get(Product, sub.product_id)
            if not user or not product:
                return

            prefs = user.notification_prefs or {}

            # Email dispatch
            if prefs.get("email", True):
                await email_notifier.send_alert_email(
                    to_email=user.email,
                    product_title=product.title,
                    current_price=float(product.last_price or alert.trigger_price),
                    trigger_price=float(alert.trigger_price),
                    currency=product.currency,
                    trigger_type=alert.trigger_type,
                )

            # Push dispatch
            if prefs.get("push", False):
                await push_notifier.send_push_notification(
                    user_id=user.id,
                    title="Price Drop Alert!",
                    body=f"{product.title[:40]} reached {product.currency} {float(alert.trigger_price):.2f}",
                )

    asyncio.run(_dispatch())
