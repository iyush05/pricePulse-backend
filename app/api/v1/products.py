from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.product import (
    TrackProductRequest,
    ProductResponse,
    PaginatedProductsResponse,
)
from app.schemas.price import PriceStatsResponse
from app.schemas.recommendation import TrackProductResponse, RecommendationResponse
from app.services.product_service import ProductService
from app.services.price_service import price_service
from app.engine.recommender import recommender

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("/track", response_model=TrackProductResponse, status_code=status.HTTP_200_OK)
async def track_product(
    data: TrackProductRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Core submission endpoint:
    Resolves canonical key, scrapes prospectively if new, subscribes user,
    evaluates decision logic (Heuristic or GBDT), and returns product + recommendation.
    """
    return await ProductService.track_product(db, current_user, data)


@router.get("", response_model=PaginatedProductsResponse)
async def list_products(
    platform: Optional[str] = Query(None, description="Filter by platform (amazon, flipkart, etc.)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all tracked products with optional filtering and pagination."""
    items, total = await ProductService.list_products(
        db, platform=platform, category=category, page=page, limit=limit
    )
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    return PaginatedProductsResponse(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/{id}", response_model=ProductResponse)
async def get_product(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a single tracked product."""
    product = await ProductService.get_product_by_id(db, id)
    return ProductResponse.model_validate(product)


@router.get("/{id}/stats", response_model=PriceStatsResponse)
async def get_product_stats(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get statistical baselines and extrema for a product (current, low, high, 30d/90d averages)."""
    product = await ProductService.get_product_by_id(db, id)
    return await price_service.get_price_stats(db, product)


@router.get("/{id}/recommendation", response_model=RecommendationResponse)
async def get_product_recommendation(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluate and retrieve the latest BUY/WAIT recommendation
    and confidence score using Heuristic or GBDT model.
    """
    product = await ProductService.get_product_by_id(db, id)
    return await recommender.get_recommendation(db, product)
