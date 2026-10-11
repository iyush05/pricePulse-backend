import uuid
from urllib.parse import urlparse
from typing import Dict, Any, Optional
import httpx
import structlog
from app.ingestion.proxy_manager import proxy_manager
from app.ingestion.parsers import AmazonParser, FlipkartParser, GenericParser

logger = structlog.get_logger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.google.com/",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class ScraperPool:
    @staticmethod
    async def fetch_html_httpx(url: str, proxy: Optional[str] = None) -> tuple[str, str]:
        """Fetches page HTML and returns (html, final_url)."""
        timeout = httpx.Timeout(20.0, connect=7.0)
        async with httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            timeout=timeout,
            proxy=proxy,
            verify=False,
        ) as client:
            response = await client.get(url)
            # Do not immediately raise if status is 200 or 404 (some pages include html)
            if response.status_code >= 400 and not response.text:
                response.raise_for_status()
            return response.text, str(response.url)

    @classmethod
    async def scrape(cls, url: str, platform: str) -> Dict[str, Any]:
        source_run_id = str(uuid.uuid4())
        proxy = proxy_manager.get_proxy()
        html = None
        final_url = url

        # 1. Fetch page HTML
        try:
            html, final_url = await cls.fetch_html_httpx(url, proxy=proxy)
        except Exception as e:
            if proxy:
                proxy_manager.mark_failed(proxy)
            logger.warning("httpx request failed, attempting direct fetch", url=url, error=str(e))
            try:
                html, final_url = await cls.fetch_html_httpx(url, proxy=None)
            except Exception as direct_err:
                logger.error("Direct fetch failed as well", url=url, error=str(direct_err))
                raise

        # Check if redirection changed platform
        final_hostname = urlparse(final_url).hostname or ""
        resolved_platform = platform
        if "amazon." in final_hostname or "amzn." in final_hostname:
            resolved_platform = "amazon"
        elif "flipkart." in final_hostname:
            resolved_platform = "flipkart"

        # 2. Parse using platform parser
        if resolved_platform == "amazon":
            parsed = AmazonParser.parse(html)
        elif resolved_platform == "flipkart":
            parsed = FlipkartParser.parse(html)
        else:
            parsed = GenericParser.parse(html)

        parsed["source_run_id"] = source_run_id
        parsed["platform"] = resolved_platform
        parsed["url"] = final_url
        return parsed


scraper_pool = ScraperPool()
