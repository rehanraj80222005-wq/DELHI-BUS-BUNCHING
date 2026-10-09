import logging
from typing import Dict, Any
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)


class BaselineLogisticModel:
    def __init__(self, class_weight: str = "balanced"):
        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(class_weight=class_weight, random_state=42, max_iter=1000)),
        ])

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaselineLogisticModel":
        self.pipeline.fit(X, y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(X)[:, 1]

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        probas = self.predict_proba(X)
        return (probas >= threshold).astype(int)
