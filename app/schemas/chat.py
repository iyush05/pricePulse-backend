from datetime import datetime
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatSource(BaseModel):
    product_id: str
    product_title: str
    data_type: str  # "price_history", "recommendation", "stats"
    detail: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    sources: List[ChatSource] = []
    created_at: datetime


class ChatMessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: Optional[List[ChatSource]] = None
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []
