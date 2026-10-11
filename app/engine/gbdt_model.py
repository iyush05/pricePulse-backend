import os
from typing import Dict, Any, Tuple
import joblib
import numpy as np
import structlog

from app.config import settings
from app.engine.features import FEATURE_NAMES

logger = structlog.get_logger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "ml_models")
MODEL_PATH = os.path.join(MODEL_DIR, "gbdt_v1.joblib")


class GBDTModel:
    def __init__(self, model_path: str = MODEL_PATH):
        self.model_path = model_path
        self._model = None

    def load_model(self):
        if self._model is not None:
            return self._model

        candidate_paths = [
            self.model_path,
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml_models", "gbdt_v1.joblib"),
            os.path.join(os.getcwd(), "ml_models", "gbdt_v1.joblib"),
            os.path.join(os.getcwd(), "app", "ml_models", "gbdt_v1.joblib"),
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                try:
                    self._model = joblib.load(p)
                    logger.info("Loaded trained GBDT model from disk", path=p)
                    return self._model
                except Exception as e:
                    logger.warning("Failed loading model from candidate path", path=p, error=str(e))

        # If model does not exist yet, import and train
        from app.engine.training.trainer import train_model
        self._model = train_model(self.model_path)
        return self._model

    def predict(self, feature_dict: Dict[str, float]) -> Tuple[str, float, str]:
        """
        Predict purchase timing.
        Returns: (signal, confidence, reasoning)
        """
        model = self.load_model()
        row = [feature_dict.get(k, 0.0) for k in FEATURE_NAMES]
        X = np.array([row])

        probs = model.predict_proba(X)[0]
        # Label 1 is BUY (no significantly cheaper price within H days)
        buy_prob = float(probs[1]) if len(probs) > 1 else float(probs[0])

        tau = settings.CLASSIFICATION_THRESHOLD_TAU
        if buy_prob >= tau:
            signal = "BUY"
            reasoning = (
                f"GBDT Recommendation: BUY (confidence {buy_prob:.1%}). "
                f"Model predicts a low probability of a meaningfully better price within the next {settings.HORIZON_H} days."
            )
        else:
            signal = "WAIT"
            reasoning = (
                f"GBDT Recommendation: WAIT (buy probability {buy_prob:.1%}). "
                f"Model identifies high likelihood of a price drop or promotional discount within {settings.HORIZON_H} days."
            )

        return signal, round(buy_prob, 4), reasoning


gbdt_model = GBDTModel()
