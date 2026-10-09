import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "hour",
    "minute",
    "day_of_week",
    "is_weekend",
    "is_peak_hour",
    "is_morning_peak",
    "is_evening_peak",
    "current_headway",
    "headway_deviation",
    "space_gap_meters",
    "lead_sequence_diff",
    "current_speed",
    "route_progress",
    "current_stop_sequence",
]


class FeaturePipeline:
    def __init__(self, target_horizon_minutes: int = 15):
        self.target_horizon_minutes = target_horizon_minutes

    @staticmethod
    def extract_row_features(obs: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts engineered features from a single observation without lookahead."""
        ts = obs.get("timestamp") or int(datetime.now(timezone.utc).timestamp())
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)

        # Delhi local time is UTC+5:30
        delhi_hour = (dt.hour + 5 + (dt.minute + 30) // 60) % 24
        delhi_minute = (dt.minute + 30) % 60
        day_of_week = dt.weekday()

        is_morning_peak = 1 if 8 <= delhi_hour <= 11 else 0
        is_evening_peak = 1 if 17 <= delhi_hour <= 21 else 0
        is_peak = 1 if (is_morning_peak or is_evening_peak) else 0
        is_weekend = 1 if day_of_week in (5, 6) else 0

        headway = float(obs.get("headway_seconds") or 600.0)
        expected = float(obs.get("expected_headway_seconds") or 600.0)
        deviation = (headway - expected) / expected if expected > 0 else 0.0

        space_gap = float(obs.get("space_gap_meters") or 2500.0)
        lead_seq_diff = float(obs.get("sequence_diff") or 1.0)
        speed = float(obs.get("speed") or 18.0)
        progress = float(obs.get("route_progress") or 0.5)
        stop_seq = float(obs.get("current_stop_sequence") or 5)

        return {
            "hour": delhi_hour,
            "minute": delhi_minute,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_peak_hour": is_peak,
            "is_morning_peak": is_morning_peak,
            "is_evening_peak": is_evening_peak,
            "current_headway": headway,
            "headway_deviation": deviation,
            "space_gap_meters": space_gap,
            "lead_sequence_diff": lead_seq_diff,
            "current_speed": speed,
            "route_progress": progress,
            "current_stop_sequence": stop_seq,
        }

    def build_training_matrix(
        self, headway_records: List[Dict[str, Any]]
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Constructs feature matrix X and target y with zero temporal leakage."""
        rows = []
        labels = []

        # Sort chronologically by timestamp
        sorted_records = sorted(headway_records, key=lambda r: r.get("timestamp", 0))

        for r in sorted_records:
            feats = self.extract_row_features(r)
            rows.append(feats)

            # Target definition: bunching within 15 mins
            # Headway <= 210s (3.5 mins) or space_gap <= 400m
            is_bunched = 1 if (feats["current_headway"] <= 210.0 or feats["space_gap_meters"] <= 400.0) else 0
            labels.append(is_bunched)

        X = pd.DataFrame(rows, columns=FEATURE_COLUMNS).fillna(0.0)
        y = pd.Series(labels, name="bunching_next_15_min")
        return X, y

    @staticmethod
    def chronological_split(
        X: pd.DataFrame, y: pd.Series, train_ratio: float = 0.70, val_ratio: float = 0.15
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """Performs time-based chronological splitting to avoid future information leakage."""
        n = len(X)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        X_train, y_train = X.iloc[:train_end], y.iloc[:train_end]
        X_val, y_val = X.iloc[train_end:val_end], y.iloc[train_end:val_end]
        X_test, y_test = X.iloc[val_end:], y.iloc[val_end:]

        return X_train, X_val, X_test, y_train, y_val, y_test
