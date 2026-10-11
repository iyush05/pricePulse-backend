from typing import Optional, Dict
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.alert import AlertResponse, PaginatedAlertsResponse
from app.schemas.product import ProductSummaryResponse
from app.services.alert_service import alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _serialize_alert(a) -> AlertResponse:
    prod_summary = None
    if a.subscription and a.subscription.product:
        p = a.subscription.product
        prod_summary = ProductSummaryResponse(
            id=p.id,
            canonical_key=p.canonical_key,
            platform=p.platform,
            title=p.title,
            image_url=p.image_url,
            currency=p.currency,
            last_price=float(p.last_price) if p.last_price else None,
            all_time_low=float(p.all_time_low) if p.all_time_low else None,
            all_time_high=float(p.all_time_high) if p.all_time_high else None,
        )

    return AlertResponse(
        id=a.id,
        subscription_id=a.subscription_id,
        fired_at=a.fired_at,
        trigger_price=float(a.trigger_price),
        channel=a.channel,
        trigger_type=a.trigger_type,
        is_read=a.is_read,
        product=prod_summary,
    )


@router.get("", response_model=PaginatedAlertsResponse)
async def list_alerts(
    unread: bool = Query(False, description="Filter for unread alerts only"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List price drop alerts fired for the authenticated user."""
    items, total, unread_count = await alert_service.list_alerts(
        db, current_user, unread_only=unread, page=page, limit=limit
    )
    return PaginatedAlertsResponse(
        items=[_serialize_alert(a) for a in items],
        total=total,
        unread_count=unread_count,
        page=page,
        limit=limit,
    )


@router.get("/{id}", response_model=AlertResponse)
async def get_alert(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details for a specific alert."""
    alert = await alert_service.get_alert(db, current_user, id)
    return _serialize_alert(alert)


@router.patch("/{id}/read", response_model=AlertResponse)
async def mark_alert_read(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark single alert notification as read."""
    alert = await alert_service.mark_read(db, current_user, id)
    return _serialize_alert(alert)


@router.post("/mark-all-read")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, int]:
    """Bulk mark all alerts as read."""
    count = await alert_service.mark_all_read(db, current_user)
    return {"marked_read_count": count}
