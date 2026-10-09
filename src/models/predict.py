import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import pandas as pd

from src.config import settings
from src.features.engineering import FeaturePipeline, FEATURE_COLUMNS
from src.models.explain import PredictionExplainer

logger = logging.getLogger(__name__)


class BunchingPredictor:
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or (settings.paths.project_root / "models" / "bunching_predictor.joblib")
        self.artifact = self._load_or_train()
        self.model = self.artifact["model"]
        self.feature_columns = self.artifact.get("feature_columns", FEATURE_COLUMNS)
        self.explainer = PredictionExplainer(self.model, self.feature_columns)

    def _load_or_train(self) -> Dict[str, Any]:
        if self.model_path.exists():
            try:
                artifact = joblib.load(self.model_path)
                logger.info("Loaded champion model from %s", self.model_path)
                return artifact
            except Exception as exc:
                logger.warning("Failed to load model from %s (%s). Re-training...", self.model_path, exc)

        logger.info("No trained model found. Executing training pipeline...")
        from src.models.train import train_models
        train_models()
        return joblib.load(self.model_path)

    @staticmethod
    def map_risk_level(probability: float) -> str:
        if probability >= 0.80:
            return "SEVERE"
        if probability >= 0.60:
            return "HIGH"
        if probability >= 0.40:
            return "MODERATE"
        if probability >= 0.20:
            return "LOW"
        return "NORMAL"

    def predict_observation(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        """Generates real-time bunching probability and explanation for a single headway observation."""
        feat_dict = FeaturePipeline.extract_row_features(obs)
        X = pd.DataFrame([feat_dict])[self.feature_columns]

        if hasattr(self.model, "predict_proba"):
            prob = float(self.model.predict_proba(X)[0][1])
        else:
            prob = float(self.model.predict(X)[0])

        risk_level = self.map_risk_level(prob)
        explanations = self.explainer.explain_prediction(X, top_k=4)

        return {
            "route_id": str(obs.get("route_id", "UNKNOWN")),
            "stop_id": str(obs.get("stop_id", "UNKNOWN")),
            "bunching_probability": round(prob, 4),
            "bunching_percentage": f"{round(prob * 100, 1)}%",
            "risk_level": risk_level,
            "prediction_horizon_minutes": 15,
            "top_contributing_factors": explanations["top_positive_factors"],
            "mitigating_factors": explanations["top_negative_factors"],
            "disclaimer": explanations["disclaimer"],
        }
