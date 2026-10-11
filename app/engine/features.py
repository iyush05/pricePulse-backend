from datetime import datetime, timezone
import math
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from app.config import settings


FEATURE_NAMES = [
    "ma_7",
    "ma_30",
    "ma_90",
    "r_7",
    "r_30",
    "r_90",
    "sigma_90",
    "z_90",
    "gap_to_low",
    "gap_to_high",
    "range_position",
    "days_since_discount",
    "mean_discount_interval",
    "cadence_phase",
    "day_of_year_sin",
    "day_of_year_cos",
    "day_of_week_sin",
    "day_of_week_cos",
    "holt_ratio",
    "availability_30",
]


def holt_linear_forecast_ratio(prices: np.ndarray, horizon: int = 14, alpha: float = 0.3, beta: float = 0.1) -> float:
    """Holt's linear trend method forecast ratio to current price."""
    if len(prices) < 2:
        return 1.0
    level = prices[0]
    trend = prices[1] - prices[0]
    for p in prices[1:]:
        last_level = level
        level = alpha * p + (1 - alpha) * (level + trend)
        trend = beta * (level - last_level) + (1 - beta) * trend
    forecast = level + horizon * trend
    current = prices[-1]
    if current <= 0:
        return 1.0
    return float(max(0.0, forecast / current))


def compute_feature_vector(
    price_records: List[Dict[str, Any]],
    current_time: Optional[datetime] = None,
) -> Dict[str, float]:
    """
    Computes features strictly from the closed past series.
    price_records must be sorted ascending by timestamp: [{'observed_at': datetime, 'price': float, 'availability': bool}]
    """
    if not price_records:
        return {f: 0.0 for f in FEATURE_NAMES}

    df = pd.DataFrame(price_records)
    df["observed_at"] = pd.to_datetime(df["observed_at"])
    df = df.sort_values("observed_at").reset_index(drop=True)
    df["price"] = df["price"].astype(float)
    df["availability"] = df["availability"].astype(bool)

    current_price = float(df["price"].iloc[-1])
    n = len(df)

    # 1. Statistical Baselines
    ma_7 = float(df["price"].tail(7).mean())
    ma_30 = float(df["price"].tail(30).mean())
    ma_90 = float(df["price"].tail(90).mean())

    r_7 = (current_price / ma_7 - 1.0) if ma_7 > 0 else 0.0
    r_30 = (current_price / ma_30 - 1.0) if ma_30 > 0 else 0.0
    r_90 = (current_price / ma_90 - 1.0) if ma_90 > 0 else 0.0

    series_90 = df["price"].tail(90)
    sigma_90 = float(series_90.std()) if len(series_90) > 1 else 0.0
    if np.isnan(sigma_90) or sigma_90 <= 1e-6:
        sigma_90 = 0.001
    z_90 = (current_price - ma_90) / sigma_90

    # 2. Running Extrema
    all_time_low = float(df["price"].min())
    all_time_high = float(df["price"].max())

    gap_to_low = (current_price / all_time_low - 1.0) if all_time_low > 0 else 0.0
    gap_to_high = (current_price / all_time_high - 1.0) if all_time_high > 0 else 0.0

    range_span = all_time_high - all_time_low
    range_position = ((current_price - all_time_low) / range_span) if range_span > 0 else 0.5

    # 3. Promotional Cadence (High Importance)
    # Detect discount episodes where price dropped > 7% below trailing 14-period max
    discount_onsets = []
    trailing_14_max = df["price"].rolling(window=14, min_periods=1).max()
    for idx in range(n):
        p = df["price"].iloc[idx]
        m = trailing_14_max.iloc[idx]
        if m > 0 and (m - p) / m > settings.DISCOUNT_THRESHOLD:
            # check if previous was not already in discount onset
            if idx == 0 or (trailing_14_max.iloc[idx - 1] - df["price"].iloc[idx - 1]) / trailing_14_max.iloc[idx - 1] <= settings.DISCOUNT_THRESHOLD:
                discount_onsets.append(df["observed_at"].iloc[idx])

    if discount_onsets:
        last_onset = discount_onsets[-1]
        now_dt = df["observed_at"].iloc[-1]
        days_since_discount = max(0.0, (now_dt - last_onset).total_seconds() / 86400.0)
        if len(discount_onsets) > 1:
            gaps = [
                (discount_onsets[i] - discount_onsets[i - 1]).total_seconds() / 86400.0
                for i in range(1, len(discount_onsets))
            ]
            mean_discount_interval = float(np.mean(gaps))
        else:
            mean_discount_interval = 30.0  # prior assumption
        cadence_phase = days_since_discount / (mean_discount_interval if mean_discount_interval > 0 else 30.0)
    else:
        days_since_discount = 90.0
        mean_discount_interval = 45.0
        cadence_phase = 1.0

    # 4. Temporal Features
    eval_time = current_time or df["observed_at"].iloc[-1]
    if hasattr(eval_time, "timetuple"):
        doy = eval_time.timetuple().tm_yday
        dow = eval_time.weekday()
    else:
        doy = 180
        dow = 3

    day_of_year_sin = math.sin(2.0 * math.pi * doy / 365.25)
    day_of_year_cos = math.cos(2.0 * math.pi * doy / 365.25)
    day_of_week_sin = math.sin(2.0 * math.pi * dow / 7.0)
    day_of_week_cos = math.cos(2.0 * math.pi * dow / 7.0)

    # 5. Forecast & Context
    holt_ratio = holt_linear_forecast_ratio(df["price"].values, horizon=settings.HORIZON_H)
    availability_30 = float(df["availability"].tail(30).mean())

    features = {
        "ma_7": round(ma_7, 2),
        "ma_30": round(ma_30, 2),
        "ma_90": round(ma_90, 2),
        "r_7": round(r_7, 4),
        "r_30": round(r_30, 4),
        "r_90": round(r_90, 4),
        "sigma_90": round(sigma_90, 4),
        "z_90": round(z_90, 4),
        "gap_to_low": round(gap_to_low, 4),
        "gap_to_high": round(gap_to_high, 4),
        "range_position": round(range_position, 4),
        "days_since_discount": round(days_since_discount, 2),
        "mean_discount_interval": round(mean_discount_interval, 2),
        "cadence_phase": round(cadence_phase, 4),
        "day_of_year_sin": round(day_of_year_sin, 4),
        "day_of_year_cos": round(day_of_year_cos, 4),
        "day_of_week_sin": round(day_of_week_sin, 4),
        "day_of_week_cos": round(day_of_week_cos, 4),
        "holt_ratio": round(holt_ratio, 4),
        "availability_30": round(availability_30, 4),
    }
    return features
