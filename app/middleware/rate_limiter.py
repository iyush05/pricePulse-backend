import time
import structlog
from typing import Optional, Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import redis.asyncio as aioredis
from app.config import settings

logger = structlog.get_logger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._in_memory_buckets: Dict[str, list] = {}
        self._redis_client: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        if self._redis_client is None:
            try:
                self._redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1.0,
                )
            except Exception:
                self._redis_client = None
        return self._redis_client

    async def dispatch(self, request: Request, call_next) -> Response:
        # Exclude documentation and health endpoints
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Identify client by IP or auth header
        client_ip = request.client.host if request.client else "unknown"
        auth_header = request.headers.get("Authorization", "")
        identifier = f"ratelimit:{auth_header[:30] if auth_header else client_ip}:{request.url.path}"

        now = int(time.time())
        allowed = True
        remaining = self.max_requests

        redis = await self._get_redis()
        if redis:
            try:
                pipe = redis.pipeline()
                current_window = now // self.window_seconds
                key = f"{identifier}:{current_window}"
                pipe.incr(key)
                pipe.expire(key, self.window_seconds * 2)
                res = await pipe.execute()
                current_count = res[0]
                if current_count > self.max_requests:
                    allowed = False
                remaining = max(0, self.max_requests - current_count)
            except Exception as e:
                # Fall back to allowing request if Redis has a transient error
                logger.debug("Redis rate limiting error, passing through", error=str(e))
        else:
            # Simple in-memory sliding window
            timestamps = self._in_memory_buckets.get(identifier, [])
            cutoff = now - self.window_seconds
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self.max_requests:
                allowed = False
            else:
                timestamps.append(now)
            self._in_memory_buckets[identifier] = timestamps
            remaining = max(0, self.max_requests - len(timestamps))

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after_seconds": self.window_seconds,
                },
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
