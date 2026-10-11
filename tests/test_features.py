from datetime import datetime, timedelta, timezone
import pytest
from app.engine.features import compute_feature_vector, FEATURE_NAMES
from app.engine.heuristic import HeuristicRecommender
from app.engine.gbdt_model import gbdt_model


def test_feature_vector_computation():
    base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    series = [
        {"observed_at": base_time + timedelta(days=i), "price": 100.0 - (i % 5), "availability": True}
        for i in range(40)
    ]
    features = compute_feature_vector(series)

    for name in FEATURE_NAMES:
        assert name in features
        assert isinstance(features[name], (int, float))

    assert features["gap_to_low"] >= 0.0
    assert features["range_position"] >= 0.0
    assert features["range_position"] <= 1.0


def test_heuristic_buy_signal():
    # Price is 90, average is 100, low is 88 (90 <= 1.05 * 88 = 92.4) -> BUY
    signal, conf, reason = HeuristicRecommender.evaluate(
        current_price=90.0,
        all_time_low=88.0,
        mean_price_90=100.0,
        observation_count=5,
    )
    assert signal == "BUY"
    assert conf == 0.35


def test_heuristic_wait_signal():
    # Price is 110, average is 100 -> above mean -> WAIT
    signal, conf, reason = HeuristicRecommender.evaluate(
        current_price=110.0,
        all_time_low=85.0,
        mean_price_90=100.0,
        observation_count=5,
    )
    assert signal == "WAIT"


def test_gbdt_model_inference():
    base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    series = [
        {"observed_at": base_time + timedelta(days=i), "price": 100.0 + i, "availability": True}
        for i in range(35)
    ]
    features = compute_feature_vector(series)
    signal, prob, reason = gbdt_model.predict(features)
    assert signal in ["BUY", "WAIT"]
    assert 0.0 <= prob <= 1.0
    assert "GBDT" in reason
