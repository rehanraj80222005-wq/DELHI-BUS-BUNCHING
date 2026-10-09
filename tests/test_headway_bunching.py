import unittest
from src.analytics.headway import HeadwayEngine
from src.analytics.bunching import BunchingDetector


class TestHeadwayAndBunching(unittest.TestCase):
    def setUp(self):
        self.headway_engine = HeadwayEngine(default_expected_headway=600.0)
        self.detector = BunchingDetector()

    def test_normal_headway_spacing(self):
        # 3 buses spaced ~2,700m apart (~10 min at 4.5 m/s)
        snapshot = [
            {"vehicle_id": "BUS_A", "route_id": "534", "latitude": 28.550, "longitude": 77.250, "current_stop_sequence": 10, "timestamp": 1000},
            {"vehicle_id": "BUS_B", "route_id": "534", "latitude": 28.530, "longitude": 77.230, "current_stop_sequence": 7, "timestamp": 1000},
            {"vehicle_id": "BUS_C", "route_id": "534", "latitude": 28.510, "longitude": 77.210, "current_stop_sequence": 4, "timestamp": 1000},
        ]

        headways = self.headway_engine.calculate_headways_for_snapshot(snapshot)
        self.assertEqual(len(headways), 2)

        events = self.detector.detect_bunching_events(headways)
        self.assertEqual(len(events), 0)  # No bunching

    def test_bunched_buses_detected(self):
        # Bus A and Bus B are right on top of each other (100m apart, ~20 sec headway)
        # Bus C is far behind (5,000m apart, ~20 min headway)
        # Classic 2 min / 22 min bunching pattern
        snapshot = [
            {"vehicle_id": "BUS_A", "route_id": "534", "latitude": 28.5500, "longitude": 77.2500, "current_stop_sequence": 10, "timestamp": 1000},
            {"vehicle_id": "BUS_B", "route_id": "534", "latitude": 28.5495, "longitude": 77.2495, "current_stop_sequence": 10, "timestamp": 1000},
            {"vehicle_id": "BUS_C", "route_id": "534", "latitude": 28.5000, "longitude": 77.2000, "current_stop_sequence": 2, "timestamp": 1000},
        ]

        headways = self.headway_engine.calculate_headways_for_snapshot(snapshot)
        self.assertEqual(len(headways), 2)

        # First pair: BUS_A and BUS_B
        pair_ab = headways[0]
        self.assertTrue(pair_ab["space_gap_meters"] < 200.0)

        events = self.detector.detect_bunching_events(headways)
        self.assertTrue(len(events) >= 1)
        self.assertIn(events[0]["severity"], ("HIGH", "SEVERE"))
        self.assertEqual(events[0]["leading_vehicle_id"], "BUS_A")
        self.assertEqual(events[0]["trailing_vehicle_id"], "BUS_B")


if __name__ == "__main__":
    unittest.main()
