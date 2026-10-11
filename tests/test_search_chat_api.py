import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_and_chat_workflow(client: AsyncClient, auth_headers):
    # Track product so catalog has data
    track_resp = await client.post(
        "/api/v1/products/track",
        json={"url": "https://www.amazon.com/dp/B07PGL2ZSL", "target_price": 40.0},
        headers=auth_headers,
    )
    assert track_resp.status_code == 200

    # 1. Search products
    search_resp = await client.get("/api/v1/search?q=Amazon", headers=auth_headers)
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert "results" in search_data
    assert search_data["total"] >= 1

    # 2. Send RAG chat message
    chat_resp = await client.post(
        "/api/v1/chat",
        json={"message": "Should I buy my tracked item now or wait?"},
        headers=auth_headers,
    )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "reply" in chat_data
    assert "conversation_id" in chat_data
    assert "sources" in chat_data
    assert len(chat_data["sources"]) >= 1

    conv_id = chat_data["conversation_id"]

    # 3. Retrieve conversation history
    hist_resp = await client.get(f"/api/v1/chat/history?conversation_id={conv_id}", headers=auth_headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["id"] == conv_id
    assert len(hist_data["messages"]) >= 2  # user + assistant
