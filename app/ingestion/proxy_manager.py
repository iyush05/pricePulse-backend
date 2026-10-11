import time
from typing import List, Optional
import structlog

logger = structlog.get_logger(__name__)


class ProxyManager:
    def __init__(self, proxies: Optional[List[str]] = None, cooldown_seconds: int = 300):
        self.proxies = proxies or []
        self.cooldown_seconds = cooldown_seconds
        self.failed_proxies: dict[str, float] = {}
        self._index = 0

    def get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None

        now = time.time()
        # Clean expired cool-downs
        self.failed_proxies = {p: ts for p, ts in self.failed_proxies.items() if now - ts < self.cooldown_seconds}

        available = [p for p in self.proxies if p not in self.failed_proxies]
        if not available:
            logger.warning("All proxies are cooling down, attempting first available proxy")
            return self.proxies[0]

        proxy = available[self._index % len(available)]
        self._index = (self._index + 1) % len(available)
        return proxy

    def mark_failed(self, proxy: str) -> None:
        if proxy in self.proxies:
            logger.info("Marking proxy as failed, initiating cooldown", proxy=proxy)
            self.failed_proxies[proxy] = time.time()


proxy_manager = ProxyManager()
