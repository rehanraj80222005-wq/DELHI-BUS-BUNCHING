import unittest
import numpy as np
import pandas as pd
from src.features.engineering import FEATURE_COLUMNS
from src.models.baseline import BaselineLogisticModel
from src.models.predict import BunchingPredictor
from src.models.explain import PredictionExplainer
from src.models.evaluate import evaluate_classifier


class TestModels(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        n = 100
        self.X = pd.DataFrame(np.random.randn(n, len(FEATURE_COLUMNS)), columns=FEATURE_COLUMNS)
        self.y = pd.Series(np.random.choice([0, 1], size=n, p=[0.75, 0.25]))

    def test_baseline_logistic(self):
        model = BaselineLogisticModel()
        model.fit(self.X, self.y)
        probs = model.predict_proba(self.X)

        self.assertEqual(len(probs), len(self.X))
        self.assertTrue(all(0.0 <= p <= 1.0 for p in probs))

        preds = model.predict(self.X, threshold=0.5)
        self.assertEqual(len(preds), len(self.X))
        self.assertTrue(set(preds).issubset({0, 1}))

    def test_evaluate_classifier(self):
        y_true = pd.Series([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.2, 0.8, 0.9])
        metrics = evaluate_classifier(y_true, y_prob)

        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["f1"], 1.0)
        self.assertEqual(metrics["roc_auc"], 1.0)

    def test_prediction_explainer(self):
        model = BaselineLogisticModel()
        model.fit(self.X, self.y)
        explainer = PredictionExplainer(model.pipeline.named_steps["classifier"], FEATURE_COLUMNS)

        sample = self.X.iloc[[0]]
        explanation = explainer.explain_prediction(sample, top_k=3)

        self.assertIn("top_positive_factors", explanation)
        self.assertIn("disclaimer", explanation)
        self.assertTrue(len(explanation["top_positive_factors"]) <= 3)

    def test_predictor_online_inference(self):
        predictor = BunchingPredictor()
        obs = {
            "route_id": "534",
            "stop_id": "S12",
            "headway_seconds": 90.0,  # severely bunched
            "expected_headway_seconds": 600.0,
            "space_gap_meters": 150.0,
            "speed": 10.0,
            "sequence_diff": 0,
            "current_stop_sequence": 5,
            "route_progress": 0.2,
        }
        res = predictor.predict_observation(obs)

        self.assertIn("bunching_probability", res)
        self.assertIn("risk_level", res)
        self.assertIn("top_contributing_factors", res)
        self.assertEqual(res["route_id"], "534")
        self.assertEqual(res["prediction_horizon_minutes"], 15)


if __name__ == "__main__":
    unittest.main()
