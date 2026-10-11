from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel
from app.schemas.product import ProductResponse
from app.schemas.subscription import SubscriptionResponse


class RecommendationResponse(BaseModel):
    product_id: str
    signal: Literal["BUY", "WAIT"]
    confidence: float
    phase: Literal["heuristic", "learned"]
    reasoning: str
    features_summary: Optional[Dict[str, Any]] = None
    evaluated_at: datetime


class TrackProductResponse(BaseModel):
    product: ProductResponse
    subscription: SubscriptionResponse
    recommendation: RecommendationResponse
    is_newly_tracked: bool
