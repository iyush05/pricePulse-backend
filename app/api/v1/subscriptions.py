from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionResponse,
    SubscriptionUpdateRequest,
    PaginatedSubscriptionsResponse,
)
from app.services.subscription_service import subscription_service

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("", response_model=PaginatedSubscriptionsResponse)
async def list_subscriptions(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List subscriptions belonging to current user."""
    items, total = await subscription_service.list_user_subscriptions(
        db, current_user, is_active=is_active, page=page, limit=limit
    )
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    return PaginatedSubscriptionsResponse(
        items=[SubscriptionResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/{id}", response_model=SubscriptionResponse)
async def get_subscription(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get single subscription by ID."""
    sub = await subscription_service.get_subscription(db, current_user, id)
    return SubscriptionResponse.model_validate(sub)


@router.patch("/{id}", response_model=SubscriptionResponse)
async def update_subscription(
    id: str,
    data: SubscriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update target price or toggle active tracking state."""
    sub = await subscription_service.update_subscription(db, current_user, id, data)
    return SubscriptionResponse.model_validate(sub)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unsubscribe from price tracking (soft delete)."""
    await subscription_service.delete_subscription(db, current_user, id)
    return None
