import logging
from typing import Dict, Any
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    brier_score_loss,
)

logger = logging.getLogger(__name__)


def evaluate_classifier(y_true: pd.Series, y_prob: np.ndarray, threshold: float = 0.5) -> Dict[str, Any]:
    """Calculates comprehensive classification metrics for imbalanced bunching evaluation."""
    y_pred = (y_prob >= threshold).astype(int)

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    try:
        roc_auc = roc_auc_score(y_true, y_prob)
    except Exception:
        roc_auc = 0.5

    try:
        pr_auc = average_precision_score(y_true, y_prob)
    except Exception:
        pr_auc = float(np.mean(y_true))

    brier = brier_score_loss(y_true, y_prob)
    cm = confusion_matrix(y_true, y_pred).tolist()

    return {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "brier_score": round(float(brier), 4),
        "confusion_matrix": cm,
    }
