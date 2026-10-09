import unittest
from fastapi.testclient import TestClient
from src.api.main import app


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("records_stored", data)

    def test_get_routes(self):
        response = self.client.get("/routes")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("routes", data)

    def test_get_vehicles_live(self):
        response = self.client.get("/vehicles/live?limit=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_get_route_prediction(self):
        response = self.client.get("/routes/534/prediction")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("bunching_probability", data)
        self.assertIn("risk_level", data)
        self.assertIn("top_contributing_factors", data)

    def test_get_alerts(self):
        response = self.client.get("/alerts")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("alerts", data)


if __name__ == "__main__":
    unittest.main()
