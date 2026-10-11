import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_subscriptions_crud(client: AsyncClient, auth_headers):
    # Track product to create subscription
    track_resp = await client.post(
        "/api/v1/products/track",
        json={"url": "https://www.flipkart.com/laptop/p/itm987654321", "target_price": 50000.0},
        headers=auth_headers,
    )
    assert track_resp.status_code == 200
    sub_id = track_resp.json()["subscription"]["id"]

    # List subscriptions
    list_resp = await client.get("/api/v1/subscriptions", headers=auth_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    assert any(s["id"] == sub_id for s in data["items"])

    # Get single subscription
    get_resp = await client.get(f"/api/v1/subscriptions/{sub_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == sub_id

    # Update subscription target price
    patch_resp = await client.patch(
        f"/api/v1/subscriptions/{sub_id}",
        json={"target_price": 48000.0, "is_active": True},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["target_price"] == 48000.0

    # Delete subscription (soft delete)
    del_resp = await client.delete(f"/api/v1/subscriptions/{sub_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # Verify inactive
    check_resp = await client.get(f"/api/v1/subscriptions/{sub_id}", headers=auth_headers)
    assert check_resp.json()["is_active"] is False
