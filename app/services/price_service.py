from datetime import datetime, timedelta, timezone
from typing import List, Optional
import structlog
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.product import Product
from app.models.price_history import PriceHistory
from app.schemas.price import (
    PricePointResponse,
    PriceHistoryResponse,
    PriceStatsResponse,
)

logger = structlog.get_logger(__name__)


class PriceService:
    @staticmethod
    async def get_price_history(
        db: AsyncSession,
        product: Product,
        range_str: str = "30d",
        granularity: str = "raw",
    ) -> PriceHistoryResponse:
        now = datetime.now(timezone.utc)
        start_time = None

        if range_str == "7d":
            start_time = now - timedelta(days=7)
        elif range_str == "30d":
            start_time = now - timedelta(days=30)
        elif range_str == "90d":
            start_time = now - timedelta(days=90)
        elif range_str == "1y":
            start_time = now - timedelta(days=365)
        # "all" leaves start_time as None

        query = select(PriceHistory).where(PriceHistory.product_id == product.id)
        if start_time:
            query = query.where(PriceHistory.observed_at >= start_time)
        query = query.order_by(PriceHistory.observed_at.asc())

        res = await db.execute(query)
        rows = res.scalars().all()

        points: List[PricePointResponse] = []

        if granularity in ["hourly", "daily"] and len(rows) > 1:
            # Resample / rollup using pandas
            df = pd.DataFrame([
                {
                    "timestamp": r.observed_at,
                    "price": float(r.price),
                    "currency": r.currency,
                    "availability": r.availability,
                }
                for r in rows
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            freq = "1h" if granularity == "hourly" else "1D"
            df = df.set_index("timestamp").resample(freq).agg({
                "price": "mean",
                "availability": "all",
                "currency": "last",
            }).dropna().reset_index()

            for _, row in df.iterrows():
                points.append(
                    PricePointResponse(
                        timestamp=row["timestamp"].to_pydatetime(),
                        price=round(float(row["price"]), 2),
                        currency=row["currency"] or product.currency,
                        availability=bool(row["availability"]),
                    )
                )
        else:
            for r in rows:
                points.append(
                    PricePointResponse(
                        timestamp=r.observed_at,
                        price=float(r.price),
                        currency=r.currency,
                        availability=r.availability,
                    )
                )

        return PriceHistoryResponse(
            product_id=product.id,
            range=range_str,
            granularity=granularity,
            currency=product.currency,
            data=points,
        )

    @staticmethod
    async def get_price_stats(db: AsyncSession, product: Product) -> PriceStatsResponse:
        query = (
            select(PriceHistory.price, PriceHistory.observed_at)
            .where(PriceHistory.product_id == product.id)
            .order_by(PriceHistory.observed_at.asc())
        )
        res = await db.execute(query)
        rows = res.all()

        if not rows:
            return PriceStatsResponse(
                product_id=product.id,
                current_price=float(product.last_price) if product.last_price else None,
                all_time_low=float(product.all_time_low) if product.all_time_low else None,
                all_time_high=float(product.all_time_high) if product.all_time_high else None,
                observation_count=0,
            )

        def _ensure_utc(dt: datetime) -> datetime:
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        prices = [float(r.price) for r in rows]
        timestamps = [_ensure_utc(r.observed_at) for r in rows]

        current_price = prices[-1]
        all_time_low = min(prices)
        all_time_high = max(prices)

        now = datetime.now(timezone.utc)
        cutoff_30 = now - timedelta(days=30)
        cutoff_90 = now - timedelta(days=90)

        prices_30 = [p for p, t in zip(prices, timestamps) if t >= cutoff_30]
        prices_90 = [p for p, t in zip(prices, timestamps) if t >= cutoff_90]

        avg_30 = float(np.mean(prices_30)) if prices_30 else current_price
        avg_90 = float(np.mean(prices_90)) if prices_90 else current_price

        drop_from_high_pct = (
            ((all_time_high - current_price) / all_time_high * 100.0)
            if all_time_high > 0
            else 0.0
        )

        # Days since last price change
        days_since_change = 0
        last_change_time = timestamps[-1]
        for i in range(len(prices) - 2, -1, -1):
            if prices[i] != current_price:
                last_change_time = timestamps[i + 1]
                break
        days_since_change = max(0, (now - last_change_time).days)

        return PriceStatsResponse(
            product_id=product.id,
            current_price=round(current_price, 2),
            all_time_low=round(all_time_low, 2),
            all_time_high=round(all_time_high, 2),
            avg_30=round(avg_30, 2),
            avg_90=round(avg_90, 2),
            drop_from_high_pct=round(drop_from_high_pct, 1),
            days_since_price_change=days_since_change,
            observation_count=len(prices),
        )


price_service = PriceService()
