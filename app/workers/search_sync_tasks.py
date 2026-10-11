import asyncio
import structlog
from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.product import Product
from app.services.search_service import search_service

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.workers.search_sync_tasks.sync_product_to_search")
def sync_product_to_search(product_id: str):
    async def _sync():
        async with AsyncSessionLocal() as db:
            prod = await db.get(Product, product_id)
            if prod:
                search_service.index_product(prod)
                logger.info("Synced product to search index", product_id=product_id)

    asyncio.run(_sync())
