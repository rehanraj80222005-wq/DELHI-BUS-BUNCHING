import unittest
import pandas as pd

from src.ingestion.gtfs_loader import GTFSFeed
from src.processing.validation import GTFSValidator


def create_sample_feed(
    stop_lats=(28.52, 28.55),
    stop_lons=(77.20, 77.25),
    trip_route_id="534",
    st_trip_id="T1",
    st_stop_id="S1",
    sequences=(1, 2)
) -> GTFSFeed:
    agency = pd.DataFrame([{"agency_id": "DIMTS", "agency_name": "Delhi Transit"}])
    calendar = pd.DataFrame([{"service_id": "1"}])
    routes = pd.DataFrame([{"route_id": "534", "route_short_name": "534"}])
    stops = pd.DataFrame([
        {"stop_id": "S1", "stop_name": "Stop 1", "stop_lat": stop_lats[0], "stop_lon": stop_lons[0]},
        {"stop_id": "S2", "stop_name": "Stop 2", "stop_lat": stop_lats[1], "stop_lon": stop_lons[1]},
    ])
    trips = pd.DataFrame([{"route_id": trip_route_id, "trip_id": "T1", "service_id": "1"}])
    stop_times = pd.DataFrame([
        {"trip_id": st_trip_id, "stop_id": st_stop_id, "stop_sequence": sequences[0]},
        {"trip_id": st_trip_id, "stop_id": "S2", "stop_sequence": sequences[1]},
    ])
    return GTFSFeed(
        agency=agency,
        calendar=calendar,
        routes=routes,
        stops=stops,
        trips=trips,
        stop_times=stop_times
    )


class TestValidation(unittest.TestCase):
    def test_validator_clean_feed(self):
        feed = create_sample_feed()
        validator = GTFSValidator(feed)
        report = validator.validate()

        self.assertTrue(report.is_valid)
        self.assertEqual(report.coordinate_anomalies, 0)
        self.assertEqual(report.orphaned_trips, 0)
        self.assertEqual(report.orphaned_stop_times, 0)
        self.assertEqual(report.missing_stop_references, 0)
        self.assertEqual(report.sequence_errors, 0)

    def test_validator_coordinate_anomaly(self):
        feed = create_sample_feed(stop_lats=(12.97, 28.55))
        validator = GTFSValidator(feed)
        report = validator.validate()

        self.assertEqual(report.coordinate_anomalies, 1)
        self.assertTrue(any("bounding box" in w for w in report.warnings))

    def test_validator_orphaned_trips(self):
        feed = create_sample_feed(trip_route_id="999")
        validator = GTFSValidator(feed)
        report = validator.validate()

        self.assertFalse(report.is_valid)
        self.assertEqual(report.orphaned_trips, 1)

    def test_validator_orphaned_stop_times(self):
        feed = create_sample_feed(st_trip_id="T_UNKNOWN")
        validator = GTFSValidator(feed)
        report = validator.validate()

        self.assertFalse(report.is_valid)
        self.assertEqual(report.orphaned_stop_times, 2)

    def test_validator_sequence_error(self):
        feed = create_sample_feed(sequences=(2, 1))
        validator = GTFSValidator(feed)
        report = validator.validate()

        self.assertEqual(report.sequence_errors, 1)


if __name__ == "__main__":
    unittest.main()
