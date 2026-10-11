from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    locale: str
    notification_prefs: Dict[str, Any]
    is_active: bool
    created_at: datetime


class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    locale: Optional[str] = None
    notification_prefs: Optional[Dict[str, bool]] = None


class UserStatsResponse(BaseModel):
    tracked_count: int
    alerts_fired: int
    active_subscriptions: int
    savings_estimate: float
