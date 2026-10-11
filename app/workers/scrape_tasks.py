import asyncio
from datetime import datetime, timezone
import structlog
from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.product import Product
from app.models.price_history import PriceHistory
from app.ingestion.scraper_pool import scraper_pool
from app.ingestion.normaliser import normaliser
from app.workers.alert_tasks import evaluate_alerts
from app.workers.polling_tasks import recalculate_poll_cadence
from app.workers.search_sync_tasks import sync_product_to_search

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.workers.scrape_tasks.scrape_product",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def scrape_product(self, product_id: str):
    """
    Executes prospective scrape observation for a product:
    Scrape -> Normalise -> Write DB -> Evaluate Alerts -> Recalculate Polling Cadence.
    """
    async def _execute():
        async with AsyncSessionLocal() as db:
            product = await db.get(Product, product_id)
            if not product:
                return

            logger.info("Executing periodic scrape", product_id=product.id, url=product.url)

            try:
                # 1. Scrape
                raw_extracted = await scraper_pool.scrape(product.url, product.platform)
            except Exception as exc:
                logger.warning("Scrape attempt failed, scheduling retry with backoff", error=str(exc))
                # Exponential backoff with jitter
                countdown = min(300, (2 ** self.request.retries) * 30)
                raise self.retry(exc=exc, countdown=countdown)

            # 2. Normalise
            observation = normaliser.normalise(
                raw_price_str=raw_extracted.get("raw_price"),
                availability=raw_extracted.get("availability", True),
                last_known_price=float(product.last_price) if product.last_price else None,
                default_currency=product.currency,
            )

            # 3. Handle quarantined data
            if observation.is_quarantined:
                logger.warning(
                    "Observation quarantined, skipping database write",
                    reason=observation.quarantine_reason,
                    product_id=product.id,
                )
                return

            # 4. Write observation to price_history
            now = datetime.now(timezone.utc)
            history_record = PriceHistory(
                product_id=product.id,
                observed_at=now,
                price=observation.price,
                currency=observation.currency,
                availability=observation.availability,
                source_run_id=raw_extracted.get("source_run_id"),
            )
            db.add(history_record)

            # Update running extrema on Product model
            product.last_price = observation.price
            product.last_observed_at = now
            if product.all_time_low is None or observation.price < float(product.all_time_low):
                product.all_time_low = observation.price
            if product.all_time_high is None or observation.price > float(product.all_time_high):
                product.all_time_high = observation.price

            # Update title / image if earlier placeholder
            if raw_extracted.get("title") and ("Product" in product.title or len(product.title) < 10):
                product.title = raw_extracted["title"]
            if raw_extracted.get("image_url") and not product.image_url:
                product.image_url = raw_extracted["image_url"]

            await db.commit()

            # 5. Chained downstream tasks
            evaluate_alerts.delay(product.id, observation.price)
            recalculate_poll_cadence.delay(product.id)
            sync_product_to_search.delay(product.id)

    asyncio.run(_execute())
