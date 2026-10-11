from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.schemas.product import ProductSummaryResponse


class SubscriptionCreateRequest(BaseModel):
    product_id: str
    target_price: Optional[float] = None


class SubscriptionUpdateRequest(BaseModel):
    target_price: Optional[float] = None
    is_active: Optional[bool] = None


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    product_id: str
    target_price: Optional[float] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    product: Optional[ProductSummaryResponse] = None


class PaginatedSubscriptionsResponse(BaseModel):
    items: List[SubscriptionResponse]
    total: int
    page: int
    limit: int
    total_pages: int
