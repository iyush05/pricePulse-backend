from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
)
from app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["RAG Chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def send_chat_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    RAG Chat endpoint:
    Answers user queries grounded in real database price telemetry,
    historical lows, and model recommendation signals.
    """
    return await chat_service.process_chat(db, current_user, request)


@router.get("/history", response_model=ConversationResponse)
async def get_conversation_history(
    conversation_id: str = Query(..., description="ID of the conversation to retrieve"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full message history and grounded citations for a conversation."""
    return await chat_service.get_history(db, current_user, conversation_id)
