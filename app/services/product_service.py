from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.price_history import PriceHistory
from app.schemas.product import TrackProductRequest, ProductResponse
from app.schemas.subscription import SubscriptionResponse
from app.schemas.recommendation import TrackProductResponse, RecommendationResponse
from app.ingestion.url_resolver import URLResolver
from app.ingestion.scraper_pool import scraper_pool
from app.ingestion.normaliser import normaliser
from app.engine.recommender import recommender
from app.services.search_service import search_service

logger = structlog.get_logger(__name__)


class ProductService:
    @staticmethod
    async def track_product(
        db: AsyncSession,
        user: User,
        request: TrackProductRequest,
    ) -> TrackProductResponse:
        """
        Implements Core Algorithm 1: Submission Handling and Prospective Tracking Workflow.
        """
        # 1. Resolve canonical product key (with async unshortening support)
        resolved = await URLResolver.resolve_async(request.url)
        canonical_key = resolved.canonical_key
        platform = resolved.platform
        clean_url = resolved.clean_url

        is_newly_tracked = False

        # 2. Check if product already exists in database
        stmt = select(Product).where(Product.canonical_key == canonical_key)
        res = await db.execute(stmt)
        product = res.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if not product:
            # First submission across entire system!
            is_newly_tracked = True
            logger.info("New product submission, executing initial prospective scrape", canonical_key=canonical_key)

            # Synchronous fetch
            raw_extraction = {}
            try:
                raw_extraction = await scraper_pool.scrape(clean_url, platform)
            except Exception as e:
                logger.warning("Live scrape encountered exception during initial fetch", error=str(e))
                raw_extraction = {
                    "title": f"{platform.title()} Item ({resolved.product_identifier})",
                    "raw_price": None,
                    "availability": False,
                    "image_url": None,
                    "category": None,
                }

            # Use scraped price; if scrape had no price on dummy/offline URL, fallback to target_price if provided
            raw_price_str = raw_extraction.get("raw_price")
            if not raw_price_str and request.target_price is not None:
                raw_price_str = str(request.target_price)

            observation = normaliser.normalise(
                raw_price_str=raw_price_str,
                availability=raw_extraction.get("availability", True),
                default_currency="INR" if resolved.region == "IN" else "USD",
            )

            product = Product(
                canonical_key=canonical_key,
                platform=platform,
                url=clean_url,
                title=raw_extraction.get("title") or f"Product ({canonical_key})",
                image_url=raw_extraction.get("image_url"),
                currency=observation.currency,
                region=resolved.region,
                category=raw_extraction.get("category"),
                first_seen_at=now,
                poll_interval_s=settings.DEFAULT_POLL_INTERVAL_S,
                next_poll_at=now + timedelta(seconds=settings.DEFAULT_POLL_INTERVAL_S),
                is_dormant=False,
                last_price=observation.price if not observation.is_quarantined and observation.price > 0 else None,
                all_time_low=observation.price if not observation.is_quarantined and observation.price > 0 else None,
                all_time_high=observation.price if not observation.is_quarantined and observation.price > 0 else None,
                last_observed_at=now,
            )
            db.add(product)
            await db.flush()

            # Append first price observation to price_history
            if not observation.is_quarantined and observation.price > 0:
                history_record = PriceHistory(
                    product_id=product.id,
                    observed_at=now,
                    price=observation.price,
                    currency=observation.currency,
                    availability=observation.availability,
                    source_run_id=raw_extraction.get("source_run_id") or "initial_sync",
                )
                db.add(history_record)

            await db.commit()
            await db.refresh(product)

            # Sync to search index
            search_service.index_product(product)
        else:
            # Product already tracked by other users; subsequent users inherit the existing history!
            if product.is_dormant:
                product.is_dormant = False
                product.next_poll_at = now + timedelta(seconds=settings.DEFAULT_POLL_INTERVAL_S)
                await db.commit()
                await db.refresh(product)

        # 3. Subscribe user to product (de-duplicated at user-product level)
        sub_stmt = select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.product_id == product.id,
        )
        sub_res = await db.execute(sub_stmt)
        subscription = sub_res.scalar_one_or_none()

        if not subscription:
            subscription = Subscription(
                user_id=user.id,
                product_id=product.id,
                target_price=request.target_price,
                is_active=True,
            )
            db.add(subscription)
            await db.commit()
            await db.refresh(subscription)
        else:
            if not subscription.is_active or request.target_price is not None:
                subscription.is_active = True
                if request.target_price is not None:
                    subscription.target_price = request.target_price
                await db.commit()
                await db.refresh(subscription)

        # 4 & 5 & 6 & 7. Evaluate and return recommendation (Heuristic or GBDT)
        rec = await recommender.get_recommendation(db, product)

        return TrackProductResponse(
            product=ProductResponse.model_validate(product),
            subscription=SubscriptionResponse.model_validate(subscription),
            recommendation=rec,
            is_newly_tracked=is_newly_tracked,
        )

    @staticmethod
    async def get_product_by_id(db: AsyncSession, product_id: str) -> Product:
        product = await db.get(Product, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        return product

    @staticmethod
    async def list_products(
        db: AsyncSession,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Product], int]:
        stmt = select(Product)
        count_stmt = select(func.count(Product.id))

        if platform:
            stmt = stmt.where(Product.platform == platform)
            count_stmt = count_stmt.where(Product.platform == platform)
        if category:
            stmt = stmt.where(Product.category == category)
            count_stmt = count_stmt.where(Product.category == category)

        offset = (page - 1) * limit
        stmt = stmt.order_by(Product.first_seen_at.desc()).offset(offset).limit(limit)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        res = await db.execute(stmt)
        items = res.scalars().all()
        return list(items), total
