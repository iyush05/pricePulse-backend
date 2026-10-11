from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.recommendation import RecommendationResponse
from app.services.product_service import ProductService
from app.engine.recommender import recommender

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/{product_id}", response_model=RecommendationResponse)
async def get_recommendation(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get BUY or WAIT recommendation with confidence score and feature summary
    for any tracked product.
    """
    product = await ProductService.get_product_by_id(db, product_id)
    return await recommender.get_recommendation(db, product)
