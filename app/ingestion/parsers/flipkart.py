import json
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)


class FlipkartParser:
    @staticmethod
    def parse(html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")

        title = ""
        raw_price = None
        image_url = None
        availability = True
        category = None

        # 1. First priority: Schema.org JSON-LD (Rock-solid structured metadata)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "Product":
                        title = item.get("name") or title
                        category = item.get("category") or category
                        img = item.get("image")
                        if img:
                            image_url = img[0] if isinstance(img, list) else img

                        offers = item.get("offers", {})
                        if isinstance(offers, list) and offers:
                            offers = offers[0]
                        if isinstance(offers, dict):
                            p = offers.get("price")
                            if p:
                                raw_price = f"₹{p}"
                            avail = str(offers.get("availability", ""))
                            if "outofstock" in avail.lower():
                                availability = False
                        break
            except Exception:
                continue

        # 2. Fallback: Title extraction from DOM
        if not title:
            title_el = (
                soup.select_one("span.B_NuCI")
                or soup.select_one(".VU-ZEz")
                or soup.select_one("span.VU-ZEz")
                or soup.select_one("h1")
            )
            if title_el:
                title = title_el.get_text(strip=True)
            if not title:
                og_title = soup.find("meta", property="og:title")
                if og_title and og_title.get("content"):
                    title = og_title["content"]

        # 3. Fallback: Price extraction from DOM selectors
        if not raw_price:
            price_selectors = [
                "div.Nx9bqj.CxhGGd",
                "div._30jeq3._16Jk6d",
                "div.Nx9bqj",
                "div._30jeq3",
                "div.v1zwn20",
                "div._1psv1zeb9._1psv1ze0",
                "div.css-g5y9jx",
            ]
            for sel in price_selectors:
                el = soup.select_one(sel)
                if el and re.search(r"[₹$€£]\s*[0-9,]+", el.get_text()):
                    raw_price = el.get_text(strip=True)
                    break

        if not raw_price:
            for tag in soup.find_all(lambda t: t.text and re.match(r"^[₹$€£]\s*[0-9,]+(?:\.[0-9]{2})?$", t.text.strip())):
                raw_price = tag.text.strip()
                break

        if not raw_price:
            og_price = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")
            if og_price and og_price.get("content"):
                raw_price = og_price["content"]

        # 4. Fallback: Image extraction
        if not image_url:
            img_el = (
                soup.select_one("img._396cs4._2amPTt._3qGmMb")
                or soup.select_one("img.DByuf4")
                or soup.select_one("img._53J4C-")
                or soup.select_one("img._396cs4")
            )
            if img_el:
                image_url = img_el.get("src")
            if not image_url:
                og_img = soup.find("meta", property="og:image")
                if og_img and og_img.get("content"):
                    image_url = og_img["content"]

        # 5. Availability checks
        avail_el = soup.select_one("div._16FRp0") or soup.select_one("div._1dVc8W")
        if avail_el:
            text = avail_el.get_text(strip=True).lower()
            if any(term in text for term in ["sold out", "currently out of stock", "coming soon", "not available"]):
                availability = False

        # 6. Category
        if not category:
            cat_items = soup.select("div._1MR4o5 a._2whKao")
            if cat_items:
                category = cat_items[-1].get_text(strip=True)

        return {
            "title": title or "Flipkart Product",
            "raw_price": raw_price,
            "image_url": image_url,
            "availability": availability,
            "category": category,
        }
