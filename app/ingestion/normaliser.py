import re
from typing import Optional, Dict, Any
from dataclasses import dataclass
import structlog
from app.config import settings

logger = structlog.get_logger(__name__)

CURRENCY_SYMBOL_MAP = {
    "$": "USD",
    "₹": "INR",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "C$": "CAD",
    "A$": "AUD",
}


@dataclass
class NormalisedObservation:
    price: float
    currency: str
    availability: bool
    is_quarantined: bool
    quarantine_reason: Optional[str] = None


class Normaliser:
    @staticmethod
    def extract_currency(raw_str: str, default_currency: str = "USD") -> str:
        for symbol, code in CURRENCY_SYMBOL_MAP.items():
            if symbol in raw_str:
                return code
        # Check standard 3-letter codes
        code_match = re.search(r"\b(USD|INR|EUR|GBP|CAD|AUD|JPY)\b", raw_str, re.IGNORECASE)
        if code_match:
            return code_match.group(1).upper()
        return default_currency

    @staticmethod
    def clean_price_number(raw_str: str) -> Optional[float]:
        if not raw_str:
            return None
        # Remove currency symbols and non-numeric characters except digits, dot, comma
        cleaned = re.sub(r"[^\d.,]", "", raw_str).strip()
        if not cleaned:
            return None

        # Handle European decimal formatting where comma is decimal separator (e.g., "1.299,00")
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                # comma is decimal: "1.299,50" -> "1299.50"
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # dot is decimal: "1,299.50" -> "1299.50"
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # If only comma present: "1299,50" vs "1,299"
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) == 2:
                # likely decimal separator: "1299,50" -> 1299.50
                cleaned = cleaned.replace(",", ".")
            else:
                # likely thousand separator: "1,299" -> 1299
                cleaned = cleaned.replace(",", "")

        try:
            val = float(cleaned)
            return round(val, 2)
        except ValueError:
            return None

    @classmethod
    def normalise(
        cls,
        raw_price_str: Optional[str],
        availability: bool,
        last_known_price: Optional[float] = None,
        default_currency: str = "USD",
    ) -> NormalisedObservation:
        """Standardise price, currency, availability, and apply quarantine rules."""
        if not raw_price_str:
            return NormalisedObservation(
                price=0.0,
                currency=default_currency,
                availability=False,
                is_quarantined=True,
                quarantine_reason="Missing price string",
            )

        currency = cls.extract_currency(raw_price_str, default_currency)
        price = cls.clean_price_number(raw_price_str)

        if price is None or price <= 0:
            return NormalisedObservation(
                price=0.0,
                currency=currency,
                availability=False,
                is_quarantined=True,
                quarantine_reason="Non-positive or invalid parsed price value",
            )

        # Quarantine check: implausible jump (>50% deviation from last price)
        if last_known_price and last_known_price > 0:
            pct_change = abs(price - last_known_price) / last_known_price
            if pct_change > settings.MAX_PRICE_DEVIATION:
                logger.warning(
                    "Price flagged for quarantine due to extreme deviation",
                    price=price,
                    last_known_price=last_known_price,
                    deviation=pct_change,
                )
                return NormalisedObservation(
                    price=price,
                    currency=currency,
                    availability=availability,
                    is_quarantined=True,
                    quarantine_reason=f"Extreme deviation of {pct_change:.1%} exceeds threshold",
                )

        return NormalisedObservation(
            price=price,
            currency=currency,
            availability=availability,
            is_quarantined=False,
            quarantine_reason=None,
        )


normaliser = Normaliser()
