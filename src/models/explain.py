import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from src.features.engineering import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


class PredictionExplainer:
    """Calculates local feature contributions for bunching predictions without claiming causality."""

    def __init__(self, model: Any, feature_columns: List[str] = FEATURE_COLUMNS):
        self.model = model
        self.feature_columns = feature_columns
        self._tree_explainer = None
        self._init_explainer()

    def _init_explainer(self) -> None:
        try:
            import shap
            self._tree_explainer = shap.TreeExplainer(self.model)
            logger.debug("Initialized SHAP TreeExplainer successfully.")
        except Exception as exc:
            logger.debug("SHAP TreeExplainer not available or failed (%s). Using gradient/weight fallback.", exc)

    def explain_prediction(
        self, feature_row: pd.DataFrame, top_k: int = 5
    ) -> Dict[str, Any]:
        """Returns top feature contributions explaining why bunching was or wasn't predicted."""
        if isinstance(feature_row, dict):
            feature_row = pd.DataFrame([feature_row])[self.feature_columns]

        contributions: List[Dict[str, Any]] = []

        if self._tree_explainer is not None:
            try:
                shap_values = self._tree_explainer.shap_values(feature_row)
                if isinstance(shap_values, list):
                    vals = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
                elif len(shap_values.shape) == 2:
                    vals = shap_values[0]
                else:
                    vals = shap_values

                for col, val in zip(self.feature_columns, vals):
                    contributions.append({
                        "feature": col,
                        "contribution": round(float(val), 4),
                        "value": float(feature_row[col].iloc[0]),
                    })
            except Exception as exc:
                logger.debug("TreeExplainer evaluation failed (%s). Falling back to tree importance.", exc)

        # Fallback heuristic: feature importance * normalized deviation
        if not contributions:
            importances = getattr(self.model, "feature_importances_", None)
            if importances is None:
                importances = np.ones(len(self.feature_columns)) / len(self.feature_columns)

            for col, imp in zip(self.feature_columns, importances):
                val = float(feature_row[col].iloc[0])
                # Positive contribution if headway is small or deviation is negative
                sign = 1.0 if col in ("current_headway", "space_gap_meters") and val < 300 else 0.5
                contributions.append({
                    "feature": col,
                    "contribution": round(float(imp * sign), 4),
                    "value": val,
                })

        contributions.sort(key=lambda c: abs(c["contribution"]), reverse=True)
        top_positive = [c for c in contributions if c["contribution"] > 0][:top_k]
        top_negative = [c for c in contributions if c["contribution"] <= 0][:top_k]

        return {
            "top_positive_factors": top_positive,
            "top_negative_factors": top_negative,
            "all_contributions": contributions,
            "disclaimer": "Feature attributions reflect model mathematical contributions, not proven real-world causality.",
        }
