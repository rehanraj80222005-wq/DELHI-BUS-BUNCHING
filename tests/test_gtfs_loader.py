import unittest
import tempfile
import shutil
from pathlib import Path
import pandas as pd

from src.ingestion.gtfs_loader import GTFSFeed, GTFSLoader


class TestGTFSLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.path = Path(self.temp_dir)

        agency_csv = "agency_id,agency_name,agency_url,agency_timezone\nDIMTS,Delhi Integrated Multi-Modal,http://dimts.in,Asia/Kolkata\n"
        calendar_csv = "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,1,1,20240101,20251231\n"
        routes_csv = "route_id,agency_id,route_short_name,route_long_name,route_type\n534,DIMTS,534,Mehrauli to Anand Vihar,3\n"
        stops_csv = "stop_id,stop_name,stop_lat,stop_lon\nS1,Mehrauli,28.5200,77.1800\nS2,Saket,28.5250,77.2100\nS3,Nehru Place,28.5500,77.2500\n"
        trips_csv = "route_id,service_id,trip_id,trip_headsign,direction_id\n534,1,T101,Anand Vihar,0\n"
        stop_times_csv = "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT101,08:00:00,08:00:00,S1,1\nT101,08:15:00,08:15:00,S2,2\nT101,08:35:00,08:35:00,S3,3\n"

        (self.path / "agency.txt").write_text(agency_csv, encoding="utf-8")
        (self.path / "calendar.txt").write_text(calendar_csv, encoding="utf-8")
        (self.path / "routes.txt").write_text(routes_csv, encoding="utf-8")
        (self.path / "stops.txt").write_text(stops_csv, encoding="utf-8")
        (self.path / "trips.txt").write_text(trips_csv, encoding="utf-8")
        (self.path / "stop_times.txt").write_text(stop_times_csv, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gtfs_loader_success(self):
        loader = GTFSLoader(self.path)
        feed = loader.load()

        self.assertIsInstance(feed, GTFSFeed)
        summary = feed.summary()
        self.assertEqual(summary["routes"], 1)
        self.assertEqual(summary["trips"], 1)
        self.assertEqual(summary["stops"], 3)
        self.assertEqual(summary["stop_times"], 3)

    def test_gtfs_loader_missing_file(self):
        empty_dir = tempfile.mkdtemp()
        try:
            (Path(empty_dir) / "routes.txt").write_text("route_id\n1\n", encoding="utf-8")
            loader = GTFSLoader(empty_dir)
            with self.assertRaises(FileNotFoundError):
                loader.load()
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_gtfs_feed_methods(self):
        feed = GTFSLoader(self.path).load()

        route = feed.get_route("534")
        self.assertIsNotNone(route)
        self.assertEqual(route["route_short_name"], "534")

        trips = feed.get_route_trips("534")
        self.assertEqual(len(trips), 1)
        self.assertEqual(trips.iloc[0]["trip_id"], "T101")

        stops = feed.get_trip_stops("T101")
        self.assertEqual(len(stops), 3)
        self.assertEqual(list(stops["stop_sequence"]), [1, 2, 3])
        self.assertEqual(list(stops["stop_name"]), ["Mehrauli", "Saket", "Nehru Place"])


if __name__ == "__main__":
    unittest.main()
