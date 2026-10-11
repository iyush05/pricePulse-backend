import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Optional, Tuple
from dataclasses import dataclass
import httpx
import structlog

logger = structlog.get_logger(__name__)

TRACKING_PARAM_PATTERNS = [
    r"^utm_.*",
    r"^ref.*",
    r"^tag$",
    r"^linkCode$",
    r"^camp$",
    r"^creative$",
    r"^creativeASIN$",
    r"^ascsubtag$",
    r"^pf_rd_.*",
    r"^pd_rd_.*",
    r"^qid$",
    r"^sr$",
    r"^keywords$",
    r"^_encoding$",
    r"^sprefix$",
    r"^crid$",
]

SHORT_DOMAINS = [
    "amzn.in",
    "amzn.to",
    "amzn.eu",
    "amzn.asia",
    "a.co",
    "dl.flipkart.com",
    "fkrt.it",
    "fkrt.co",
    "bit.ly",
    "tinyurl.com",
]


@dataclass
class ResolvedURL:
    canonical_key: str
    platform: str
    clean_url: str
    product_identifier: str
    region: str


class URLResolver:
    @staticmethod
    def strip_tracking_parameters(raw_url: str) -> str:
        """Strip query parameters commonly used for analytics, affiliates, or search sessions."""
        parsed = urlparse(raw_url)
        query_params = parse_qs(parsed.query, keep_blank_values=False)

        cleaned_params = {}
        for k, v in query_params.items():
            is_tracking = any(re.match(pattern, k, re.IGNORECASE) for pattern in TRACKING_PARAM_PATTERNS)
            if not is_tracking:
                cleaned_params[k] = v

        new_query = urlencode(cleaned_params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))

    @classmethod
    async def unshorten_url(cls, raw_url: str) -> str:
        """Follow redirects for short links (e.g. amzn.in/d/..., dl.flipkart.com/s/...)."""
        parsed = urlparse(raw_url)
        hostname = (parsed.hostname or "").lower()

        is_short = any(hostname == sd or hostname.endswith("." + sd) for sd in SHORT_DOMAINS)
        is_short = is_short or (hostname == "dl.flipkart.com") or ("/s/" in parsed.path and "flipkart" in hostname)

        if is_short:
            try:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-IN,en;q=0.9",
                }
                async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=10.0) as client:
                    resp = await client.get(raw_url)
                    final_url = str(resp.url)
                    if resp.status_code < 400 and final_url != raw_url:
                        logger.info("Unshortened product URL", original=raw_url, final=final_url)
                        return final_url
            except Exception as e:
                logger.warning("Failed to unshorten URL, using original", url=raw_url, error=str(e))

        return raw_url

    @classmethod
    def resolve_sync(cls, raw_url: str) -> ResolvedURL:
        """Resolve canonical product identifier, marketplace host, and clean URL."""
        clean_url = cls.strip_tracking_parameters(raw_url)
        parsed = urlparse(clean_url)
        hostname = (parsed.hostname or "").lower()

        # 1. Amazon detection
        if "amazon." in hostname or "amzn." in hostname or hostname == "a.co":
            platform = "amazon"
            region = "US"
            if hostname.endswith(".in") or "amzn.in" in hostname:
                region = "IN"
            elif hostname.endswith(".co.uk"):
                region = "GB"
            elif hostname.endswith(".de"):
                region = "DE"
            elif hostname.endswith(".ca"):
                region = "CA"

            # Extract ASIN (10 alphanumeric chars)
            asin_match = re.search(r"/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})", parsed.path, re.IGNORECASE)
            if asin_match:
                asin = asin_match.group(1).upper()
                canonical_key = f"amazon:{region}:{asin}"
                canonical_clean_url = f"{parsed.scheme or 'https'}://{hostname}/dp/{asin}"
                return ResolvedURL(
                    canonical_key=canonical_key,
                    platform=platform,
                    clean_url=canonical_clean_url,
                    product_identifier=asin,
                    region=region,
                )

        # 2. Flipkart detection
        if "flipkart." in hostname or "fkrt." in hostname:
            platform = "flipkart"
            region = "IN"
            # Pattern: /p/itm... or pid=...
            pid_match = re.search(r"/p/(itm[a-zA-Z0-9]+)", parsed.path, re.IGNORECASE)
            if pid_match:
                pid = pid_match.group(1)
            else:
                query_params = parse_qs(parsed.query)
                pid = query_params.get("pid", [""])[0]
                if not pid:
                    pid = parsed.path.strip("/").split("/")[-1]

            canonical_key = f"flipkart:{pid}"
            return ResolvedURL(
                canonical_key=canonical_key,
                platform=platform,
                clean_url=clean_url,
                product_identifier=pid,
                region=region,
            )

        # 3. Generic fallback
        platform = hostname.replace("www.", "").split(".")[0] or "generic"
        region = "GLOBAL"
        safe_path = re.sub(r"[^a-zA-Z0-9_-]", "_", parsed.path.strip("/"))
        pid = safe_path[:64] or "item"
        canonical_key = f"generic:{hostname}:{pid}"

        return ResolvedURL(
            canonical_key=canonical_key,
            platform=platform,
            clean_url=clean_url,
            product_identifier=pid,
            region=region,
        )

    @classmethod
    def resolve(cls, raw_url: str) -> ResolvedURL:
        """Synchronously resolve canonical product key."""
        return cls.resolve_sync(raw_url)

    @classmethod
    async def resolve_async(cls, raw_url: str) -> ResolvedURL:
        """Asynchronously unshorten and resolve canonical product key."""
        expanded_url = await cls.unshorten_url(raw_url)
        return cls.resolve_sync(expanded_url)
