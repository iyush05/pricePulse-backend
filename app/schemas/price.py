from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict


class PricePointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    price: float
    currency: str
    availability: bool


class PriceHistoryResponse(BaseModel):
    product_id: str
    range: str
    granularity: str
    currency: str
    data: List[PricePointResponse]


class PriceStatsResponse(BaseModel):
    product_id: str
    current_price: Optional[float] = None
    all_time_low: Optional[float] = None
    all_time_high: Optional[float] = None
    avg_30: Optional[float] = None
    avg_90: Optional[float] = None
    drop_from_high_pct: Optional[float] = None
    days_since_price_change: Optional[int] = None
    observation_count: int = 0
