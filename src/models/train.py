import sys
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.database.connection import get_session
from src.database.models import HeadwayObservation
from src.features.engineering import FeaturePipeline, FEATURE_COLUMNS
from src.models.baseline import BaselineLogisticModel
from src.models.evaluate import evaluate_classifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_training_data() -> Tuple[pd.DataFrame, pd.Series]:
    """Loads recorded headway data from database or generates representative bootstrap dataset."""
    session = get_session()
    obs_list = session.query(HeadwayObservation).all()
    session.close()

    pipeline = FeaturePipeline()

    if len(obs_list) >= 50:
        logger.info("Loading %d headway observations from database...", len(obs_list))
        records = [
            {
                "timestamp": o.timestamp,
                "route_id": o.route_id,
                "stop_id": o.stop_id,
                "headway_seconds": o.headway_seconds,
                "space_gap_meters": o.space_gap_meters or 1500.0,
                "expected_headway_seconds": o.expected_headway_seconds,
                "sequence_diff": 1,
                "speed": 18.0,
                "current_stop_sequence": 5,
                "route_progress": 0.4,
            }
            for o in obs_list
        ]
        return pipeline.build_training_matrix(records)

    logger.info("Insufficient DB observations (%d). Bootstrapping initial synthetic training set...", len(obs_list))
    np.random.seed(42)
    n_samples = 2000
    base_time = 1720000000

    synthetic_records = []
    for i in range(n_samples):
        # 20% bunching scenarios
        is_bunched = np.random.rand() < 0.22
        if is_bunched:
            headway = np.random.uniform(30.0, 180.0)
            space_m = np.random.uniform(50.0, 350.0)
            seq_diff = np.random.choice([0, 1])
            speed = np.random.uniform(5.0, 15.0)
        else:
            headway = np.random.uniform(400.0, 1200.0)
            space_m = np.random.uniform(1500.0, 4500.0)
            seq_diff = np.random.choice([1, 2, 3])
            speed = np.random.uniform(15.0, 35.0)

        t = base_time + (i * 30)
        synthetic_records.append({
            "timestamp": t,
            "route_id": str(np.random.choice([534, 108, 2065, 2459])),
            "stop_id": f"STOP_{np.random.randint(1, 50)}",
            "headway_seconds": headway,
            "space_gap_meters": space_m,
            "expected_headway_seconds": 600.0,
            "sequence_diff": seq_diff,
            "speed": speed,
            "current_stop_sequence": np.random.randint(1, 40),
            "route_progress": np.random.uniform(0.1, 0.9),
        })

    return pipeline.build_training_matrix(synthetic_records)


def train_models() -> Dict[str, Any]:
    print("=" * 65)
    print("DELHI BUS BUNCHING PREDICTOR: MODEL TRAINING PIPELINE")
    print("=" * 65)

    X, y = load_training_data()
    print(f"\n1. Dataset Matrix: {X.shape[0]:,} samples, {X.shape[1]} features.")
    print(f"   Class distribution: {y.sum():,} Bunched ({(y.mean()) * 100:.1f}%), {(len(y) - y.sum()):,} Normal.")

    # Chronological Split (prevents future information leakage)
    X_train, X_val, X_test, y_train, y_val, y_test = FeaturePipeline.chronological_split(X, y)
    print(f"   Chronological Split: Train={len(X_train):,}, Val={len(X_val):,}, Test={len(X_test):,}")

    # Model 1: Baseline Logistic Regression
    print("\n2. Training Model 1: Baseline Logistic Regression...")
    m1 = BaselineLogisticModel()
    m1.fit(X_train, y_train)
    m1_val_prob = m1.predict_proba(X_val)
    m1_test_prob = m1.predict_proba(X_test)
    m1_metrics = evaluate_classifier(y_test, m1_test_prob)

    # Model 2: Random Forest
    print("3. Training Model 2: Random Forest Classifier...")
    m2 = RandomForestClassifier(n_estimators=100, max_depth=6, class_weight="balanced", random_state=42)
    m2.fit(X_train, y_train)
    m2_test_prob = m2.predict_proba(X_test)[:, 1]
    m2_metrics = evaluate_classifier(y_test, m2_test_prob)

    # Model 3: XGBoost (Champion)
    print("4. Training Model 3: XGBoost Classifier...")
    pos_weight = max(1.0, (len(y_train) - y_train.sum()) / max(1, y_train.sum()))
    m3 = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.08,
        scale_pos_weight=pos_weight,
        random_state=42,
        eval_metric="logloss",
    )
    m3.fit(X_train, y_train)
    m3_test_prob = m3.predict_proba(X_test)[:, 1]
    m3_metrics = evaluate_classifier(y_test, m3_test_prob)

    # Comparison Table
    print("\n" + "=" * 65)
    print("MODEL COMPARISON (Test Set Performance):")
    print("=" * 65)
    headers = f"{'Model':<22} {'ROC-AUC':<10} {'PR-AUC':<10} {'F1':<8} {'Precision':<10} {'Recall':<8}"
    print(headers)
    print("-" * 65)
    for name, m in [("Logistic Regression", m1_metrics), ("Random Forest", m2_metrics), ("XGBoost", m3_metrics)]:
        print(f"{name:<22} {m['roc_auc']:<10.4f} {m['pr_auc']:<10.4f} {m['f1']:<8.4f} {m['precision']:<10.4f} {m['recall']:<8.4f}")

    # Serialize champion model (XGBoost)
    model_dir = settings.paths.project_root / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    champion_path = model_dir / "bunching_predictor.joblib"

    artifact = {
        "model": m3,
        "feature_columns": FEATURE_COLUMNS,
        "test_metrics": m3_metrics,
        "model_type": "XGBoost",
    }
    joblib.dump(artifact, champion_path)
    print(f"\nChampion model saved successfully to: {champion_path}")
    print("=" * 65)

    return {
        "logistic": m1_metrics,
        "random_forest": m2_metrics,
        "xgboost": m3_metrics,
        "champion_path": str(champion_path),
    }


if __name__ == "__main__":
    train_models()
