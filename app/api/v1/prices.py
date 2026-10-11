from typing import Literal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.price import PriceHistoryResponse
from app.services.product_service import ProductService
from app.services.price_service import price_service

router = APIRouter(prefix="/products", tags=["Prices"])


@router.get("/{id}/prices", response_model=PriceHistoryResponse)
async def get_price_history(
    id: str,
    range: Literal["7d", "30d", "90d", "1y", "all"] = Query("30d", description="Time range horizon"),
    granularity: Literal["raw", "hourly", "daily"] = Query("raw", description="Aggregation granularity"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve historical price observations and rollups for interactive frontend charts.
    """
    product = await ProductService.get_product_by_id(db, id)
    return await price_service.get_price_history(
        db, product, range_str=range, granularity=granularity
    )
