import structlog
import httpx
from typing import Dict, Any
from app.config import settings

logger = structlog.get_logger(__name__)


class WebhookNotifier:
    @staticmethod
    async def send_webhook(webhook_url: str, payload: Dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
                )
                return res.status_code < 400
        except Exception as e:
            logger.warning("Webhook dispatch failed", url=webhook_url, error=str(e))
            return False


webhook_notifier = WebhookNotifier()
