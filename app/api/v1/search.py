from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_optional_user
from app.models.user import User
from app.schemas.search import SearchResponse
from app.services.search_service import search_service

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("", response_model=SearchResponse)
async def search_tracked_products(
    q: str = Query(..., min_length=1, description="Search query string"),
    platform: Optional[str] = Query(None, description="Optional filter by platform"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Typo-tolerant search across products already under management
    powered by Meilisearch with database fallback.
    """
    return await search_service.search(
        db=db,
        query=q,
        platform_filter=platform,
        page=page,
        limit=limit,
    )
