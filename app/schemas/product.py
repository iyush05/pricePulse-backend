from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, HttpUrl, ConfigDict


class TrackProductRequest(BaseModel):
    url: str
    target_price: Optional[float] = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    canonical_key: str
    platform: str
    url: str
    title: str
    image_url: Optional[str] = None
    currency: str
    region: str
    category: Optional[str] = None
    first_seen_at: datetime
    poll_interval_s: int
    next_poll_at: datetime
    is_dormant: bool
    last_price: Optional[float] = None
    all_time_low: Optional[float] = None
    all_time_high: Optional[float] = None
    last_observed_at: Optional[datetime] = None


class ProductSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    canonical_key: str
    platform: str
    title: str
    image_url: Optional[str] = None
    currency: str
    last_price: Optional[float] = None
    all_time_low: Optional[float] = None
    all_time_high: Optional[float] = None


class PaginatedProductsResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    limit: int
    total_pages: int
