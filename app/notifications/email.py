import structlog
import httpx
from typing import Optional
from app.config import settings

logger = structlog.get_logger(__name__)


class EmailNotifier:
    @staticmethod
    async def send_alert_email(
        to_email: str,
        product_title: str,
        current_price: float,
        trigger_price: float,
        currency: str,
        trigger_type: str,
    ) -> bool:
        """Sends price alert notification email via SendGrid or mock log."""
        subject = f"Price Alert: {product_title[:50]} is now {currency} {current_price:.2f}!"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #2563eb;">PricePulse Alert</h2>
            <p>Great news! An item on your watchlist has hit an alert condition.</p>
            <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h3 style="margin-top: 0;">{product_title}</h3>
                <p><strong>Current Price:</strong> {currency} {current_price:.2f}</p>
                <p><strong>Target / Trigger:</strong> {currency} {trigger_price:.2f}</p>
                <p><strong>Trigger Condition:</strong> {trigger_type.replace('_', ' ').title()}</p>
            </div>
            <p style="color: #6b7280; font-size: 12px;">You received this email because you subscribed to PricePulse alerts.</p>
        </body>
        </html>
        """

        if not settings.SENDGRID_API_KEY:
            logger.info(
                "Mock email sent (SENDGRID_API_KEY not configured)",
                to=to_email,
                subject=subject,
                price=current_price,
            )
            return True

        url = "https://api.sendgrid.com/v3/mail/send"
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": settings.EMAIL_FROM},
            "subject": subject,
            "content": [{"type": "text/html", "value": body_html}],
        }
        headers = {
            "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=headers, timeout=10.0)
                return res.status_code in [200, 202]
        except Exception as e:
            logger.error("Failed to send email via SendGrid", error=str(e), to=to_email)
            return False


email_notifier = EmailNotifier()
