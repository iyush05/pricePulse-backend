from datetime import datetime, timezone
from typing import Dict, Any, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.product import Product
from app.models.price_history import PriceHistory
from app.engine.features import compute_feature_vector
from app.engine.heuristic import heuristic_recommender
from app.engine.gbdt_model import gbdt_model
from app.schemas.recommendation import RecommendationResponse

logger = structlog.get_logger(__name__)


class Recommender:
    @staticmethod
    async def get_recommendation(
        db: AsyncSession, product: Product
    ) -> RecommendationResponse:
        # Load price history ordered chronologically
        query = (
            select(PriceHistory)
            .where(PriceHistory.product_id == product.id)
            .order_by(PriceHistory.observed_at.asc())
        )
        res = await db.execute(query)
        records = res.scalars().all()

        current_price = float(product.last_price or 0.0)
        all_time_low = float(product.all_time_low or current_price)
        all_time_high = float(product.all_time_high or current_price)
        eval_time = datetime.now(timezone.utc)

        # Convert to serializable dicts
        series = [
            {
                "observed_at": r.observed_at,
                "price": float(r.price),
                "availability": bool(r.availability),
            }
            for r in records
        ]

        # Cold Start check: |S| < W_MIN
        if len(series) < settings.W_MIN:
            # Phase 1: Heuristic
            mean_90 = float(sum(s["price"] for s in series) / len(series)) if series else current_price
            signal, confidence, reasoning = heuristic_recommender.evaluate(
                current_price=current_price,
                all_time_low=all_time_low,
                mean_price_90=mean_90,
                observation_count=len(series),
            )
            return RecommendationResponse(
                product_id=product.id,
                signal=signal,
                confidence=confidence,
                phase="heuristic",
                reasoning=reasoning,
                features_summary={
                    "observation_count": len(series),
                    "w_min_required": settings.W_MIN,
                    "current_price": current_price,
                    "all_time_low": all_time_low,
                    "mean_price": round(mean_90, 2),
                },
                evaluated_at=eval_time,
            )

        # Phase 2: Learned GBDT Model
        features = compute_feature_vector(series, current_time=eval_time)
        signal, confidence, reasoning = gbdt_model.predict(features)

        # Key features summary for frontend UI cards and charts
        summary = {
            "observation_count": len(series),
            "r_30": features.get("r_30"),
            "r_90": features.get("r_90"),
            "gap_to_low": features.get("gap_to_low"),
            "gap_to_high": features.get("gap_to_high"),
            "range_position": features.get("range_position"),
            "cadence_phase": features.get("cadence_phase"),
            "days_since_discount": features.get("days_since_discount"),
            "mean_discount_interval": features.get("mean_discount_interval"),
            "z_90": features.get("z_90"),
            "holt_ratio": features.get("holt_ratio"),
        }

        return RecommendationResponse(
            product_id=product.id,
            signal=signal,
            confidence=confidence,
            phase="learned",
            reasoning=reasoning,
            features_summary=summary,
            evaluated_at=eval_time,
        )


recommender = Recommender()
