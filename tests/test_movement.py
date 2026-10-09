import unittest
import pandas as pd
from src.processing.movement import (
    haversine_distance_meters,
    calculate_bearing,
    calculate_speed_kmh,
    MovementReconstructor,
)
from src.ingestion.gtfs_loader import GTFSFeed


class TestMovement(unittest.TestCase):
    def test_haversine_distance(self):
        # Distance between Saket (28.525, 77.210) and Nehru Place (28.550, 77.250) ~ 4.7km
        dist = haversine_distance_meters(28.525, 77.210, 28.550, 77.250)
        self.assertTrue(4500 < dist < 5000)

    def test_calculate_bearing(self):
        # Due north
        bearing_north = calculate_bearing(28.0, 77.0, 29.0, 77.0)
        self.assertAlmostEqual(bearing_north, 0.0, delta=1.0)

        # Due east
        bearing_east = calculate_bearing(28.0, 77.0, 28.0, 78.0)
        self.assertAlmostEqual(bearing_east, 90.0, delta=1.0)

    def test_calculate_speed_kmh(self):
        # 1000m in 60s = 60 km/h
        # 1 degree lat ~ 111,139m. 0.009 deg ~ 1000m
        t1, t2 = 1000, 1060
        lat1, lon1 = 28.000, 77.000
        lat2, lon2 = 28.009, 77.000
        speed = calculate_speed_kmh(lat1, lon1, t1, lat2, lon2, t2)
        self.assertIsNotNone(speed)
        self.assertTrue(50 < speed < 70)

    def test_movement_reconstructor_gtfs_matching(self):
        # Mock GTFSFeed with a simple trip
        agency = pd.DataFrame([{"agency_id": "DTC"}])
        calendar = pd.DataFrame([{"service_id": "1"}])
        routes = pd.DataFrame([{"route_id": "534"}])
        stops = pd.DataFrame([
            {"stop_id": "S1", "stop_name": "Mehrauli", "stop_lat": 28.520, "stop_lon": 77.180},
            {"stop_id": "S2", "stop_name": "Saket", "stop_lat": 28.525, "stop_lon": 77.210},
            {"stop_id": "S3", "stop_name": "Nehru Place", "stop_lat": 28.550, "stop_lon": 77.250},
        ])
        trips = pd.DataFrame([{"route_id": "534", "trip_id": "T101"}])
        stop_times = pd.DataFrame([
            {"trip_id": "T101", "stop_id": "S1", "stop_sequence": 1},
            {"trip_id": "T101", "stop_id": "S2", "stop_sequence": 2},
            {"trip_id": "T101", "stop_id": "S3", "stop_sequence": 3},
        ])
        feed = GTFSFeed(agency, calendar, routes, stops, trips, stop_times)

        reconstructor = MovementReconstructor(feed)
        obs = {
            "vehicle_id": "BUS_01",
            "trip_id": "T101",
            "route_id": "534",
            "latitude": 28.525,
            "longitude": 77.210,
            "current_stop_sequence": 2,
        }

        matched = reconstructor.match_trip_progress(obs)
        self.assertEqual(matched["stop_id"], "S2")
        self.assertEqual(matched["stop_name"], "Saket")
        self.assertAlmostEqual(matched["route_progress"], 0.5, places=2)


if __name__ == "__main__":
    unittest.main()
