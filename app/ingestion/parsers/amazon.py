import json
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)


class AmazonParser:
    @staticmethod
    def parse(html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")

        # 1. Title
        title = ""
        title_el = soup.select_one("#productTitle") or soup.select_one("#title") or soup.select_one("h1#title span")
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"]

        # 2. Price
        raw_price = None
        price_selectors = [
            ".apexPriceToPay .a-offscreen",
            "#priceblock_dealprice",
            "#priceblock_ourprice",
            "#priceblock_saleprice",
            ".priceToPay .a-offscreen",
            "#corePrice_desktop .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "span.a-price.aok-align-center .a-offscreen",
            ".a-price.a-text-price.header-price .a-offscreen",
            "#apex_desktop .a-offscreen",
            ".a-price .a-offscreen",
            "#price_inside_buybox",
            "#newBuyBoxPrice",
        ]
        for sel in price_selectors:
            price_el = soup.select_one(sel)
            if price_el and price_el.get_text(strip=True):
                txt = price_el.get_text(strip=True)
                if re.search(r"\d+", txt):
                    raw_price = txt
                    break

        # Fallback: a-price-whole and a-price-fraction
        if not raw_price:
            whole_el = soup.select_one(".a-price .a-price-whole") or soup.select_one(".priceToPay .a-price-whole")
            if whole_el:
                whole = whole_el.get_text(strip=True).rstrip(".")
                sym_el = soup.select_one(".a-price .a-price-symbol")
                sym = sym_el.get_text(strip=True) if sym_el else ""
                fract_el = soup.select_one(".a-price .a-price-fraction")
                fract = fract_el.get_text(strip=True) if fract_el else "00"
                raw_price = f"{sym}{whole}.{fract}"

        # Fallback: regex search for currency pattern in buybox / price blocks
        if not raw_price:
            price_box = soup.select_one("#desktop_buybox") or soup.select_one("#centerCol") or soup
            box_text = price_box.get_text(" ", strip=True) if price_box else ""
            m = re.search(r"([₹$€£]\s*[0-9,]+(?:\.[0-9]{2})?)", box_text)
            if m:
                raw_price = m.group(1)

        # Fallback: embedded JSON script tags
        if not raw_price:
            for script in soup.find_all("script", type=["text/javascript", "a-state"]):
                text = script.string or ""
                if "priceAmount" in text or "buyingPrice" in text:
                    m = re.search(r'\"(?:priceAmount|buyingPrice|price)\":\s*\"?([0-9,.]+)\"?', text)
                    if m:
                        raw_price = m.group(1)
                        break

        # 3. Availability
        availability = True
        avail_el = soup.select_one("#availability") or soup.select_one("#outOfStock")
        if avail_el:
            avail_text = avail_el.get_text(strip=True).lower()
            if any(term in avail_text for term in ["currently unavailable", "out of stock", "we don't know when", "temporarily out"]):
                availability = False

        # 4. Image
        image_url = None
        img_el = (
            soup.select_one("#landingImage")
            or soup.select_one("#imgBlkFront")
            or soup.select_one("#main-image")
            or soup.select_one("img.a-dynamic-image")
        )
        if img_el:
            dyn = img_el.get("data-a-dynamic-image")
            if dyn and dyn.startswith("{"):
                try:
                    dyn_dict = json.loads(dyn)
                    if dyn_dict:
                        image_url = list(dyn_dict.keys())[0]
                except Exception:
                    pass
            if not image_url:
                image_url = img_el.get("data-old-hires") or img_el.get("src")

        if not image_url:
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                image_url = og_img["content"]

        # 5. Category
        category = None
        cat_el = soup.select("#wayfinding-breadcrumbs_feature_div ul li span.a-list-item a")
        if cat_el:
            category = cat_el[-1].get_text(strip=True)

        return {
            "title": title or "Amazon Product",
            "raw_price": raw_price,
            "image_url": image_url,
            "availability": availability,
            "category": category,
        }
