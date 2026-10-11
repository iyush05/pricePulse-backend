import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_track_product_workflow(client: AsyncClient, auth_headers):
    # 1. Track Amazon product URL
    resp = await client.post(
        "/api/v1/products/track",
        json={"url": "https://www.amazon.in/dp/B09V3KXJPB?tag=affiliate", "target_price": 89.99},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "product" in data
    assert "subscription" in data
    assert "recommendation" in data
    assert data["product"]["platform"] == "amazon"
    assert data["product"]["canonical_key"] == "amazon:IN:B09V3KXJPB"
    assert data["is_newly_tracked"] is True
    assert data["subscription"]["target_price"] == 89.99
    assert data["recommendation"]["signal"] in ["BUY", "WAIT"]

    prod_id = data["product"]["id"]

    # 2. Subsequent tracking of the same product by same/different user de-duplicates!
    resp2 = await client.post(
        "/api/v1/products/track",
        json={"url": "https://www.amazon.in/dp/B09V3KXJPB", "target_price": 85.00},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["is_newly_tracked"] is False
    assert data2["product"]["id"] == prod_id

    # 3. Get single product detail
    get_resp = await client.get(f"/api/v1/products/{prod_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == prod_id

    # 4. Get product stats
    stats_resp = await client.get(f"/api/v1/products/{prod_id}/stats", headers=auth_headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "current_price" in stats
    assert "all_time_low" in stats

    # 5. Get product prices
    prices_resp = await client.get(f"/api/v1/products/{prod_id}/prices?range=30d&granularity=raw", headers=auth_headers)
    assert prices_resp.status_code == 200
    prices_data = prices_resp.json()
    assert "data" in prices_data
    assert len(prices_data["data"]) >= 1

    # 6. Get recommendation directly
    rec_resp = await client.get(f"/api/v1/products/{prod_id}/recommendation", headers=auth_headers)
    assert rec_resp.status_code == 200
    assert rec_resp.json()["signal"] in ["BUY", "WAIT"]
