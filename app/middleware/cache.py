import hashlib
import json
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import redis.asyncio as aioredis
from app.config import settings


class CacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_ttl_seconds: int = 60):
        super().__init__(app)
        self.default_ttl = default_ttl_seconds
        self._redis_client: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        if self._redis_client is None:
            try:
                self._redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=False,
                    socket_connect_timeout=1.0,
                )
            except Exception:
                self._redis_client = None
        return self._redis_client

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        # Only cache read-heavy catalog/search endpoints; do not cache subscriptions, alerts, users, chat, auth
        if not any(request.url.path.startswith(p) for p in ["/api/v1/products", "/api/v1/search"]):
            return await call_next(request)
        if any(request.url.path.startswith(p) for p in ["/api/v1/subscriptions", "/api/v1/alerts", "/api/v1/chat", "/api/v1/users", "/api/v1/auth"]):
            return await call_next(request)

        # Check Cache-Control request header
        if request.headers.get("Cache-Control") == "no-cache":
            return await call_next(request)

        redis = await self._get_redis()
        if not redis:
            return await call_next(request)

        # Build cache key from path, query params, and Authorization hash
        auth_header = request.headers.get("Authorization", "")
        key_raw = f"{request.url.path}:{request.url.query}:{auth_header}"
        cache_key = f"httpcache:{hashlib.sha256(key_raw.encode()).hexdigest()}"

        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                cached_obj = json.loads(cached_data.decode("utf-8"))
                return Response(
                    content=cached_obj["body"].encode("utf-8"),
                    status_code=cached_obj["status_code"],
                    headers={
                        **cached_obj["headers"],
                        "X-Cache": "HIT",
                    },
                    media_type=cached_obj.get("media_type", "application/json"),
                )
        except Exception:
            pass

        response = await call_next(request)

        # Only cache successful 200 JSON responses
        if response.status_code == 200 and "application/json" in response.headers.get("content-type", ""):
            try:
                # Consume response body to cache it
                body = [section async for section in response.body_iterator]
                response.body_iterator = _iterate_in_chunks(body)
                full_body = b"".join(body).decode("utf-8")

                cached_payload = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": full_body,
                    "media_type": response.media_type,
                }
                await redis.set(cache_key, json.dumps(cached_payload), ex=self.default_ttl)
                response.headers["X-Cache"] = "MISS"
            except Exception:
                pass

        return response


async def _iterate_in_chunks(chunks):
    for chunk in chunks:
        yield chunk
