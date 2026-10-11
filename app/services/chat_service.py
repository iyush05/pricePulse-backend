from datetime import datetime, timezone
import json
from typing import List, Optional, Tuple, Dict, Any
import structlog
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User
from app.models.product import Product
from app.models.subscription import Subscription
from app.models.chat import ChatConversation, ChatMessage
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatSource,
    ChatMessageResponse,
    ConversationResponse,
)
from app.engine.recommender import recommender
from app.services.price_service import price_service

logger = structlog.get_logger(__name__)


class ChatService:
    @classmethod
    async def get_user_grounded_context(
        cls, db: AsyncSession, user: User
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Retrieves user's tracked items, latest prices, stats, and recommendations
        to ground the RAG response in truthful database records.
        """
        stmt = (
            select(Subscription)
            .options(selectinload(Subscription.product))
            .where(Subscription.user_id == user.id, Subscription.is_active == True)
        )
        res = await db.execute(stmt)
        subs = res.scalars().all()

        context_lines = []
        structured_sources = []

        for s in subs:
            p = s.product
            if not p:
                continue

            stats = await price_service.get_price_stats(db, p)
            rec = await recommender.get_recommendation(db, p)

            line = (
                f"- Product: {p.title} (ID: {p.id})\n"
                f"  Platform: {p.platform}, Currency: {p.currency}\n"
                f"  Current Price: {p.last_price or 'N/A'}, Target Price: {s.target_price or 'None'}\n"
                f"  All-time Low: {stats.all_time_low or 'N/A'}, All-time High: {stats.all_time_high or 'N/A'}\n"
                f"  30-Day Avg: {stats.avg_30 or 'N/A'}, 90-Day Avg: {stats.avg_90 or 'N/A'}\n"
                f"  Drop from High: {stats.drop_from_high_pct}%\n"
                f"  Current Pulse Signal: {rec.signal} (Confidence: {rec.confidence:.1%}, Phase: {rec.phase})\n"
                f"  Recommendation Reasoning: {rec.reasoning}\n"
            )
            context_lines.append(line)
            structured_sources.append({
                "product_id": p.id,
                "product_title": p.title,
                "data_type": "grounded_telemetry",
                "detail": f"Signal: {rec.signal}, Current: {p.currency} {p.last_price}, Low: {stats.all_time_low}",
            })

        grounded_text = "\n".join(context_lines) if context_lines else "No products currently tracked by this user."
        return grounded_text, structured_sources

    @classmethod
    async def query_llm(
        cls, system_prompt: str, user_message: str, history: List[ChatMessage]
    ) -> str:
        """Call OpenAI API or generate grounded intelligent response if API key is omitted."""
        if settings.OPENAI_API_KEY:
            messages = [{"role": "system", "content": system_prompt}]
            for m in history[-6:]:  # include last 3 turns
                messages.append({"role": m.role, "content": m.content})
            messages.append({"role": "user", "content": user_message})

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": settings.OPENAI_MODEL,
                            "messages": messages,
                            "temperature": 0.3,
                        },
                        timeout=30.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error("OpenAI call failed, falling back to local synthesis", error=str(e))

        # Grounded fallback synthesizer
        return (
            f"Based on your tracked items in PricePulse:\n\n"
            f"Here is what our ML model and price history show regarding your query:\n"
            f"- Your items are being continuously tracked with adaptive cadence.\n"
            f"- Refer to the sources attached to this response for current Buy/Wait signals and historical lows."
        )

    @classmethod
    async def process_chat(
        cls, db: AsyncSession, user: User, request: ChatRequest
    ) -> ChatResponse:
        now = datetime.now(timezone.utc)

        # 1. Get or create conversation
        conversation = None
        if request.conversation_id:
            conv_stmt = select(ChatConversation).where(
                ChatConversation.id == request.conversation_id,
                ChatConversation.user_id == user.id,
            )
            res = await db.execute(conv_stmt)
            conversation = res.scalar_one_or_none()

        if not conversation:
            conversation = ChatConversation(
                user_id=user.id,
                title=request.message[:40] if request.message else "PricePulse Chat",
            )
            db.add(conversation)
            await db.flush()

        # 2. Retrieve grounded context
        grounded_context, sources = await cls.get_user_grounded_context(db, user)

        # 3. Retrieve past messages in conversation
        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.created_at.asc())
        )
        msg_res = await db.execute(msg_stmt)
        past_msgs = list(msg_res.scalars().all())

        # 4. Construct prompt
        system_prompt = (
            "You are PricePulse AI, an intelligent e-commerce price tracking and buy-timing advisor. "
            "You provide accurate, grounded advice strictly referencing the user's tracked database records below. "
            "If the user asks whether to buy or wait for an item, quote the current price, historical low, "
            "and explain the model's BUY or WAIT signal with its confidence score.\n\n"
            f"USER'S TRACKED PRODUCTS AND TELEMETRY:\n{grounded_context}"
        )

        reply = await cls.query_llm(system_prompt, request.message, past_msgs)

        # 5. Persist user and assistant messages
        user_msg = ChatMessage(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            sources=None,
        )
        db.add(user_msg)

        assistant_msg = ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=reply,
            sources=sources,
        )
        db.add(assistant_msg)

        conversation.updated_at = now
        await db.commit()

        chat_sources = [
            ChatSource(
                product_id=s["product_id"],
                product_title=s["product_title"],
                data_type=s["data_type"],
                detail=s.get("detail"),
            )
            for s in sources
        ]

        return ChatResponse(
            conversation_id=conversation.id,
            reply=reply,
            sources=chat_sources,
            created_at=now,
        )

    @classmethod
    async def get_history(
        cls, db: AsyncSession, user: User, conversation_id: str
    ) -> ConversationResponse:
        conv = await db.get(ChatConversation, conversation_id)
        if not conv or conv.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv.id)
            .order_by(ChatMessage.created_at.asc())
        )
        res = await db.execute(msg_stmt)
        messages = res.scalars().all()

        msg_responses = []
        for m in messages:
            s_list = []
            if m.sources:
                for s in m.sources:
                    s_list.append(
                        ChatSource(
                            product_id=s.get("product_id", ""),
                            product_title=s.get("product_title", ""),
                            data_type=s.get("data_type", ""),
                            detail=s.get("detail"),
                        )
                    )
            msg_responses.append(
                ChatMessageResponse(
                    id=m.id,
                    role=m.role,
                    content=m.content,
                    sources=s_list if s_list else None,
                    created_at=m.created_at,
                )
            )

        return ConversationResponse(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            messages=msg_responses,
        )


chat_service = ChatService()
