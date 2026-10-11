from typing import List, Dict, Any, Tuple
import pandas as pd
from app.config import settings


class Labeler:
    @staticmethod
    def generate_labels(
        df_series: pd.DataFrame,
        horizon_days: int = settings.HORIZON_H,
        delta: float = settings.TOLERANCE_DELTA,
    ) -> pd.DataFrame:
        """
        Label yt = 1 (BUY) if min_{u in (t, t+H]} p_u >= (1 - delta) * pt, else 0 (WAIT).
        df_series must have ['observed_at', 'price'].
        """
        df = df_series.sort_values("observed_at").copy().reset_index(drop=True)
        df["price"] = df["price"].astype(float)
        df["observed_at"] = pd.to_datetime(df["observed_at"])
        n = len(df)

        labels = []
        valid_indices = []

        for i in range(n):
            current_t = df["observed_at"].iloc[i]
            current_p = df["price"].iloc[i]
            cutoff_t = current_t + pd.Timedelta(days=horizon_days)

            # Future slice within horizon H
            future_mask = (df["observed_at"] > current_t) & (df["observed_at"] <= cutoff_t)
            future_prices = df.loc[future_mask, "price"]

            if len(future_prices) == 0:
                # Horizon extends beyond observed dataset
                labels.append(None)
            else:
                min_future = future_prices.min()
                # If the lowest future price is >= (1 - delta) * current_price:
                # No meaningfully cheaper price is coming -> BUY
                if min_future >= (1.0 - delta) * current_p:
                    labels.append(1)
                else:
                    labels.append(0)
                valid_indices.append(i)

        df["target"] = labels
        return df


labeler = Labeler()
