import json
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)


class GenericParser:
    @staticmethod
    def parse(html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        title = ""
        raw_price = None
        image_url = None
        availability = True
        category = None

        # 1. Try JSON-LD Schema.org Product
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                if isinstance(data, list):
                    items = data
                else:
                    items = [data]

                for item in items:
                    if item.get("@type") == "Product":
                        title = item.get("name", title)
                        image = item.get("image")
                        if isinstance(image, list) and image:
                            image_url = image[0]
                        elif isinstance(image, str):
                            image_url = image

                        offers = item.get("offers", {})
                        if isinstance(offers, list) and offers:
                            offers = offers[0]
                        if isinstance(offers, dict):
                            raw_price = str(offers.get("price", ""))
                            avail_str = str(offers.get("availability", "")).lower()
                            if "outofstock" in avail_str:
                                availability = False
                        break
            except Exception:
                continue

        # 2. OpenGraph Meta Tags fallback
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"]

        if not raw_price:
            og_price = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")
            if og_price and og_price.get("content"):
                raw_price = og_price["content"]

        if not image_url:
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                image_url = og_img["content"]

        # 3. Fallback to standard HTML tags
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else (soup.title.string if soup.title else "Product")

        return {
            "title": title or "Product",
            "raw_price": raw_price,
            "image_url": image_url,
            "availability": availability,
            "category": category,
        }
