import pytest
from httpx import AsyncClient
from app.models.alert import Alert
from app.models.subscription import Subscription
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_alerts_workflow(client: AsyncClient, auth_headers, db_session: AsyncSession, test_user):
    # Track product to create subscription
    track_resp = await client.post(
        "/api/v1/products/track",
        json={"url": "https://www.amazon.com/dp/B08N5WRWNW", "target_price": 500.0},
        headers=auth_headers,
    )
    sub_id = track_resp.json()["subscription"]["id"]

    # Insert a test alert into DB
    alert = Alert(
        subscription_id=sub_id,
        trigger_price=450.0,
        channel="email",
        trigger_type="target_cross",
        is_read=False,
        idempotency_key=f"test_alert_{sub_id}_1",
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)

    # 1. List alerts
    list_resp = await client.get("/api/v1/alerts", headers=auth_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    assert data["unread_count"] >= 1

    # 2. Mark alert as read
    patch_resp = await client.patch(f"/api/v1/alerts/{alert.id}/read", headers=auth_headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_read"] is True

    # 3. Mark all read
    bulk_resp = await client.post("/api/v1/alerts/mark-all-read", headers=auth_headers)
    assert bulk_resp.status_code == 200
