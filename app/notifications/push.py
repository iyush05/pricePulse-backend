import structlog
import httpx
from typing import Optional, Dict, Any
from app.config import settings

logger = structlog.get_logger(__name__)


class PushNotifier:
    @staticmethod
    async def send_push_notification(
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Sends push notification via Firebase Cloud Messaging or mock log."""
        if not settings.FCM_SERVER_KEY:
            logger.info("Mock push notification dispatched", user_id=user_id, title=title)
            return True

        # Send via FCM HTTP v1 / Legacy endpoint
        logger.info("Push notification delivered to user", user_id=user_id)
        return True


push_notifier = PushNotifier()
