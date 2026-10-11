import os
import math
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
import structlog

from app.config import settings
from app.engine.features import compute_feature_vector, FEATURE_NAMES
from app.engine.training.labeler import labeler

logger = structlog.get_logger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml_models")
MODEL_PATH = os.path.join(MODEL_DIR, "gbdt_v1.joblib")


def generate_synthetic_training_dataset(num_series: int = 50, days_per_series: int = 120) -> pd.DataFrame:
    """
    Generates realistic historical price series with promotional cycles,
    markdown trends, and seasonal dips for training the baseline model.
    """
    records = []
    base_date = pd.Timestamp("2025-01-01")

    for s_id in range(num_series):
        base_price = np.random.uniform(50.0, 1500.0)
        volatility = np.random.uniform(0.01, 0.08)
        discount_cadence_days = np.random.randint(14, 45)

        for day in range(days_per_series):
            current_date = base_date + pd.Timedelta(days=day)
            # Periodic discounts
            is_discount = (day % discount_cadence_days) < np.random.randint(2, 5)
            discount_pct = np.random.uniform(0.08, 0.25) if is_discount else 0.0

            # Noise and trend
            noise = np.random.normal(0, volatility)
            price = base_price * (1.0 - discount_pct) * (1.0 + noise)
            price = max(5.0, round(price, 2))

            records.append({
                "series_id": s_id,
                "observed_at": current_date,
                "price": price,
                "availability": np.random.rand() > 0.03,
            })

    return pd.DataFrame(records)


def train_model(save_path: str = MODEL_PATH) -> LGBMClassifier:
    """Train histogram-based GBDT model with specified hyperparameters."""
    logger.info("Generating training data and building features...")
    df_raw = generate_synthetic_training_dataset()

    X_list = []
    y_list = []

    for series_id, group in df_raw.groupby("series_id"):
        labeled_group = labeler.generate_labels(group)
        for i in range(len(labeled_group)):
            target = labeled_group["target"].iloc[i]
            if target is None or pd.isna(target):
                continue

            # Historical sub-slice up to time t
            history_slice = labeled_group.iloc[: i + 1]
            if len(history_slice) < 5:
                continue

            sub_records = history_slice[["observed_at", "price", "availability"]].to_dict("records")
            feat_dict = compute_feature_vector(sub_records)
            row = [feat_dict[k] for k in FEATURE_NAMES]
            X_list.append(row)
            y_list.append(int(target))

    X = np.array(X_list)
    y = np.array(y_list)

    logger.info(f"Training dataset assembled: {X.shape[0]} samples, {X.shape[1]} features.")

    clf = LGBMClassifier(
        n_estimators=settings.GBDT_N_ESTIMATORS,
        max_depth=settings.GBDT_MAX_DEPTH,
        num_leaves=32,
        learning_rate=settings.GBDT_LEARNING_RATE,
        reg_lambda=settings.GBDT_REG_LAMBDA,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
    )
    clf.fit(X, y)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    joblib.dump(clf, save_path)
    logger.info("Model saved successfully", path=save_path)
    return clf


if __name__ == "__main__":
    train_model()
