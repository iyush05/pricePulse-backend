from typing import List, Optional
from pydantic import BaseModel
from app.schemas.product import ProductResponse


class SearchResultItem(BaseModel):
    id: str
    canonical_key: str
    platform: str
    title: str
    image_url: Optional[str] = None
    currency: str
    last_price: Optional[float] = None
    all_time_low: Optional[float] = None
    all_time_high: Optional[float] = None
    category: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    total: int
    page: int
    limit: int
