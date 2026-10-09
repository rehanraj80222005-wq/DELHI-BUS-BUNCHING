import unittest
import time
from google.transit import gtfs_realtime_pb2
from src.ingestion.protobuf_parser import ProtobufParser


class TestProtobufParser(unittest.TestCase):
    def create_synthetic_protobuf(self) -> bytes:
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(time.time())

        entity = feed.entity.add()
        entity.id = "DL1PD1234"
        entity.vehicle.trip.route_id = "534"
        entity.vehicle.trip.trip_id = "T101"
        entity.vehicle.vehicle.id = "BUS_534_01"
        entity.vehicle.position.latitude = 28.5250
        entity.vehicle.position.longitude = 77.2100
        entity.vehicle.position.bearing = 180.0
        entity.vehicle.position.speed = 12.5
        entity.vehicle.current_status = gtfs_realtime_pb2.VehiclePosition.VehicleStopStatus.IN_TRANSIT_TO
        entity.vehicle.current_stop_sequence = 5
        entity.vehicle.stop_id = "S_SAKET"
        entity.vehicle.timestamp = int(time.time())

        return feed.SerializeToString()

    def test_parse_valid_feed(self):
        raw_bytes = self.create_synthetic_protobuf()
        header, records = ProtobufParser.parse_feed_message(raw_bytes)

        self.assertEqual(header["gtfs_realtime_version"], "2.0")
        self.assertEqual(len(records), 1)

        rec = records[0]
        self.assertEqual(rec["entity_id"], "DL1PD1234")
        self.assertEqual(rec["vehicle_id"], "BUS_534_01")
        self.assertEqual(rec["route_id"], "534")
        self.assertEqual(rec["trip_id"], "T101")
        self.assertAlmostEqual(rec["latitude"], 28.5250, places=4)
        self.assertAlmostEqual(rec["longitude"], 77.2100, places=4)
        self.assertEqual(rec["current_status"], "IN_TRANSIT_TO")
        self.assertEqual(rec["current_stop_sequence"], 5)
        self.assertEqual(rec["stop_id"], "S_SAKET")

    def test_to_dataframe(self):
        raw_bytes = self.create_synthetic_protobuf()
        _, records = ProtobufParser.parse_feed_message(raw_bytes)
        df = ProtobufParser.to_dataframe(records)

        self.assertEqual(len(df), 1)
        self.assertIn("vehicle_id", df.columns)
        self.assertIn("latitude", df.columns)
        self.assertEqual(df["route_id"].iloc[0], "534")

    def test_corrupt_protobuf_raises_value_error(self):
        corrupt_bytes = b"NOT_A_VALID_PROTOBUF_DATA"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_feed_message(corrupt_bytes)


if __name__ == "__main__":
    unittest.main()
