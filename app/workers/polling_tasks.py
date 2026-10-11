import asyncio
from datetime import datetime, timedelta, timezone
import random
import numpy as np
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.price_history import PriceHistory
from app.config import settings

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.workers.polling_tasks.recalculate_poll_cadence")
def recalculate_poll_cadence(product_id: str):
    """
    Dynamically adjusts polling interval after an observation based on:
    - Trailing coefficient of variation (v = sigma_30 / MA_30)
    - Proximity to nearest subscriber target price (g = (p_t - target) / p_t)
    - Inactivity / zero active subscribers for 30 days (dormancy)
    - Anti-synchronization jitter
    """
    async def _recalculate():
        async with AsyncSessionLocal() as db:
            product = await db.get(Product, product_id)
            if not product:
                return

            now = datetime.now(timezone.utc)
            current_price = float(product.last_price or 0.0)

            # Check active subscribers
            subs_query = select(Subscription).where(
                Subscription.product_id == product_id,
                Subscription.is_active == True,
            )
            subs_res = await db.execute(subs_query)
            active_subs = subs_res.scalars().all()

            # Rule 5: If zero active subscribers for 30 days, mark dormant and set to MAX_INTERVAL
            if len(active_subs) == 0:
                # Check last subscription date or product first seen
                days_since_seen = (now - product.first_seen_at).days
                if days_since_seen >= settings.DORMANCY_THRESHOLD_DAYS:
                    product.is_dormant = True
                    product.poll_interval_s = settings.MAX_POLL_INTERVAL_S
                    jitter = random.uniform(0.9, 1.1)
                    product.next_poll_at = now + timedelta(seconds=int(settings.MAX_POLL_INTERVAL_S * jitter))
                    await db.commit()
                    logger.info("Marked product dormant due to zero subscribers", product_id=product_id)
                    return

            # Compute trailing 30-observation prices
            hist_query = (
                select(PriceHistory.price, PriceHistory.observed_at)
                .where(PriceHistory.product_id == product_id)
                .order_by(PriceHistory.observed_at.desc())
                .limit(30)
            )
            hist_res = await db.execute(hist_query)
            recent_rows = hist_res.all()
            prices = [float(r.price) for r in recent_rows]

            interval = product.poll_interval_s

            if len(prices) >= 5:
                ma_30 = float(np.mean(prices))
                sigma_30 = float(np.std(prices))
                # 1. Trailing coefficient of variation
                v = (sigma_30 / ma_30) if ma_30 > 0 else 0.0

                # 2. Gap to closest subscriber target price
                target_prices = [float(s.target_price) for s in active_subs if s.target_price is not None]
                if target_prices and current_price > 0:
                    closest_target = min(target_prices, key=lambda t: abs(current_price - t))
                    g = abs(current_price - closest_target) / current_price
                else:
                    g = 1.0  # No close target

                # 3. If volatile (v > v_hi) or close to target (g < 0.05), halve interval down to min bound
                if v > settings.V_HI or g < settings.TARGET_PROXIMITY_THRESHOLD:
                    interval = max(settings.MIN_POLL_INTERVAL_S, interval // 2)
                    logger.info("Shortened polling interval due to volatility/target proximity", interval=interval, v=v, g=g)

                # 4. If stable (v < v_lo) and unchanged for 14 days, double interval up to max bound
                elif v < settings.V_LO:
                    # Check if prices have remained flat
                    is_flat = max(prices) == min(prices)
                    if is_flat and len(prices) >= 14:
                        interval = min(settings.MAX_POLL_INTERVAL_S, interval * 2)
                        logger.info("Lengthened polling interval due to price stability", interval=interval, v=v)

            # 6. Apply jitter (+/- 10%) to prevent synchronized polling spikes
            jitter_factor = random.uniform(0.90, 1.10)
            scheduled_seconds = int(interval * jitter_factor)

            product.poll_interval_s = interval
            product.next_poll_at = now + timedelta(seconds=scheduled_seconds)
            await db.commit()
            logger.info("Updated product poll schedule", product_id=product_id, next_poll=product.next_poll_at)

    asyncio.run(_recalculate())


@celery_app.task(name="app.workers.polling_tasks.schedule_due_scrapes")
def schedule_due_scrapes():
    """
    Periodic task (run every 60s by Celery Beat):
    Finds products due for polling and triggers scrape_product tasks.
    """
    from app.workers.scrape_tasks import scrape_product

    async def _schedule():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            query = select(Product.id).where(
                Product.next_poll_at <= now,
                Product.is_dormant == False,
            ).limit(100)
            res = await db.execute(query)
            due_ids = res.scalars().all()
            for pid in due_ids:
                scrape_product.delay(pid)
            logger.info(f"Dispatched {len(due_ids)} due scrape tasks.")

    asyncio.run(_schedule())
