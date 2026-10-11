from typing import Dict, Any, Tuple
from app.config import settings


class HeuristicRecommender:
    @staticmethod
    def evaluate(
        current_price: float,
        all_time_low: float,
        mean_price_90: float,
        observation_count: int,
    ) -> Tuple[str, float, str]:
        """
        Phase 1 Heuristic rule for cold-start history (|S| < W_MIN).
        BUY if r_90(t) < 0 (below mean) AND p_t <= 1.05 * lo(t) (within 5% of all-time low).
        Returns: (signal, confidence, reasoning)
        """
        is_below_mean = current_price < mean_price_90
        within_5pct_low = current_price <= (1.05 * all_time_low)

        confidence = 0.35  # Low confidence due to thin history

        if is_below_mean and within_5pct_low:
            signal = "BUY"
            reasoning = (
                f"Heuristic Buy Signal: The current price ({current_price:.2f}) is below the average "
                f"({mean_price_90:.2f}) and within 5% of the all-time low ({all_time_low:.2f}). "
                f"History has {observation_count} observation(s); confidence is preliminary."
            )
        else:
            signal = "WAIT"
            reasons = []
            if not is_below_mean:
                reasons.append(f"above average ({mean_price_90:.2f})")
            if not within_5pct_low:
                reasons.append(f"more than 5% above the observed low ({all_time_low:.2f})")
            reasoning = (
                f"Heuristic Wait Signal: The price is currently {', '.join(reasons)}. "
                f"Confidence is low ({confidence:.2f}) pending deeper history."
            )

        return signal, confidence, reasoning


heuristic_recommender = HeuristicRecommender()
