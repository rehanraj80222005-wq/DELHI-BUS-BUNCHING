import unittest
import pandas as pd
from src.features.engineering import FeaturePipeline, FEATURE_COLUMNS


class TestFeaturePipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = FeaturePipeline()

    def test_extract_row_features(self):
        obs = {
            "timestamp": 1720000000,
            "headway_seconds": 150.0,
            "expected_headway_seconds": 600.0,
            "space_gap_meters": 300.0,
            "speed": 12.0,
            "sequence_diff": 0,
            "current_stop_sequence": 8,
            "route_progress": 0.35,
        }
        feats = self.pipeline.extract_row_features(obs)
        for col in FEATURE_COLUMNS:
            self.assertIn(col, feats)

        self.assertEqual(feats["current_headway"], 150.0)
        self.assertEqual(feats["space_gap_meters"], 300.0)
        self.assertAlmostEqual(feats["headway_deviation"], -0.75, places=2)

    def test_chronological_split(self):
        X = pd.DataFrame({"feat": range(100)})
        y = pd.Series([0] * 50 + [1] * 50)

        X_train, X_val, X_test, y_train, y_val, y_test = self.pipeline.chronological_split(
            X, y, train_ratio=0.7, val_ratio=0.15
        )

        self.assertEqual(len(X_train), 70)
        self.assertEqual(len(X_val), 15)
        self.assertEqual(len(X_test), 15)
        # Verify chronological order preservation (no shuffle)
        self.assertEqual(X_train["feat"].iloc[0], 0)
        self.assertEqual(X_train["feat"].iloc[-1], 69)
        self.assertEqual(X_val["feat"].iloc[0], 70)
        self.assertEqual(X_test["feat"].iloc[0], 85)


if __name__ == "__main__":
    unittest.main()
