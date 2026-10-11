from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.schemas.product import ProductSummaryResponse


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subscription_id: str
    fired_at: datetime
    trigger_price: float
    channel: str
    trigger_type: str
    is_read: bool
    product: Optional[ProductSummaryResponse] = None


class PaginatedAlertsResponse(BaseModel):
    items: List[AlertResponse]
    total: int
    unread_count: int
    page: int
    limit: int
