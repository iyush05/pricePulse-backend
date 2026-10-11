from typing import List, Optional, Dict, Any
import structlog
import meilisearch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.config import settings
from app.models.product import Product
from app.schemas.search import SearchResultItem, SearchResponse

logger = structlog.get_logger(__name__)


class SearchService:
    def __init__(self):
        self._client: Optional[meilisearch.Client] = None

    def get_client(self) -> Optional[meilisearch.Client]:
        if self._client is None:
            try:
                self._client = meilisearch.Client(
                    settings.MEILISEARCH_URL,
                    settings.MEILISEARCH_KEY,
                )
                # Ensure index exists and configure settings
                try:
                    index = self._client.index(settings.MEILISEARCH_INDEX_PRODUCTS)
                    index.update_searchable_attributes(["title", "platform", "category"])
                    index.update_filterable_attributes(["platform", "category", "region"])
                    index.update_sortable_attributes(["last_price", "all_time_low"])
                except Exception:
                    pass
            except Exception as e:
                logger.warning("Could not connect to Meilisearch", error=str(e))
                self._client = None
        return self._client

    def index_product(self, product: Product) -> None:
        client = self.get_client()
        if not client:
            return
        try:
            doc = {
                "id": str(product.id),
                "canonical_key": product.canonical_key,
                "platform": product.platform,
                "title": product.title,
                "image_url": product.image_url,
                "currency": product.currency,
                "region": product.region,
                "category": product.category,
                "last_price": float(product.last_price) if product.last_price else None,
                "all_time_low": float(product.all_time_low) if product.all_time_low else None,
                "all_time_high": float(product.all_time_high) if product.all_time_high else None,
            }
            client.index(settings.MEILISEARCH_INDEX_PRODUCTS).add_documents([doc])
        except Exception as e:
            logger.warning("Failed indexing product to Meilisearch", error=str(e))

    def remove_product(self, product_id: str) -> None:
        client = self.get_client()
        if not client:
            return
        try:
            client.index(settings.MEILISEARCH_INDEX_PRODUCTS).delete_document(product_id)
        except Exception as e:
            logger.warning("Failed removing product from Meilisearch", error=str(e))

    async def search(
        self,
        db: AsyncSession,
        query: str,
        platform_filter: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> SearchResponse:
        client = self.get_client()
        results: List[SearchResultItem] = []
        total = 0

        # 1. Try Meilisearch typo-tolerant search
        if client:
            try:
                filter_str = f"platform = '{platform_filter}'" if platform_filter else None
                offset = (page - 1) * limit
                search_params = {
                    "limit": limit,
                    "offset": offset,
                    "filter": filter_str,
                }
                res = client.index(settings.MEILISEARCH_INDEX_PRODUCTS).search(query, search_params)
                hits = res.get("hits", [])
                total = res.get("estimatedTotalHits", len(hits))

                for h in hits:
                    results.append(
                        SearchResultItem(
                            id=h["id"],
                            canonical_key=h.get("canonical_key", ""),
                            platform=h.get("platform", ""),
                            title=h.get("title", ""),
                            image_url=h.get("image_url"),
                            currency=h.get("currency", "USD"),
                            last_price=h.get("last_price"),
                            all_time_low=h.get("all_time_low"),
                            all_time_high=h.get("all_time_high"),
                            category=h.get("category"),
                        )
                    )
                return SearchResponse(
                    query=query, results=results, total=total, page=page, limit=limit
                )
            except Exception as e:
                logger.warning("Meilisearch search failed, falling back to database query", error=str(e))

        # 2. Database Fallback (SQL ILIKE / LIKE)
        stmt = select(Product)
        if query:
            stmt = stmt.where(
                or_(
                    Product.title.ilike(f"%{query}%"),
                    Product.canonical_key.ilike(f"%{query}%"),
                )
            )
        if platform_filter:
            stmt = stmt.where(Product.platform == platform_filter)

        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)
        db_res = await db.execute(stmt)
        products = db_res.scalars().all()

        for p in products:
            results.append(
                SearchResultItem(
                    id=p.id,
                    canonical_key=p.canonical_key,
                    platform=p.platform,
                    title=p.title,
                    image_url=p.image_url,
                    currency=p.currency,
                    last_price=float(p.last_price) if p.last_price else None,
                    all_time_low=float(p.all_time_low) if p.all_time_low else None,
                    all_time_high=float(p.all_time_high) if p.all_time_high else None,
                    category=p.category,
                )
            )

        return SearchResponse(
            query=query, results=results, total=len(results), page=page, limit=limit
        )


search_service = SearchService()
