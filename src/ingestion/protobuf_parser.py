import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from google.transit import gtfs_realtime_pb2

logger = logging.getLogger(__name__)


class ProtobufParser:
    """Decodes GTFS-Realtime Protocol Buffer payloads into structured data."""

    @staticmethod
    def parse_feed_message(raw_bytes: bytes) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        feed = gtfs_realtime_pb2.FeedMessage()
        try:
            feed.ParseFromString(raw_bytes)
        except Exception as exc:
            logger.error("Failed to parse FeedMessage protobuf: %s", exc)
            raise ValueError(f"Malformed GTFS-Realtime protobuf: {exc}") from exc

        header_info = {
            "gtfs_realtime_version": feed.header.gtfs_realtime_version,
            "incrementality": feed.header.incrementality,
            "timestamp": feed.header.timestamp,
            "header_datetime_utc": (
                datetime.fromtimestamp(feed.header.timestamp, tz=timezone.utc).isoformat()
                if feed.header.timestamp
                else None
            ),
        }

        records: List[Dict[str, Any]] = []

        for entity in feed.entity:
            if not entity.HasField("vehicle"):
                continue

            v = entity.vehicle
            record: Dict[str, Any] = {
                "entity_id": entity.id,
                "is_deleted": entity.is_deleted,
                "timestamp": v.timestamp if v.timestamp else feed.header.timestamp,
                "vehicle_id": v.vehicle.id if v.HasField("vehicle") and v.vehicle.id else None,
                "vehicle_label": v.vehicle.label if v.HasField("vehicle") and v.vehicle.label else None,
                "license_plate": (
                    v.vehicle.license_plate if v.HasField("vehicle") and v.vehicle.license_plate else None
                ),
                "trip_id": v.trip.trip_id if v.HasField("trip") and v.trip.trip_id else None,
                "route_id": v.trip.route_id if v.HasField("trip") and v.trip.route_id else None,
                "start_time": v.trip.start_time if v.HasField("trip") and v.trip.start_time else None,
                "start_date": v.trip.start_date if v.HasField("trip") and v.trip.start_date else None,
                "direction_id": (
                    str(v.trip.direction_id) if v.HasField("trip") and v.trip.HasField("direction_id") else None
                ),
                "latitude": v.position.latitude if v.HasField("position") and v.position.latitude else None,
                "longitude": v.position.longitude if v.HasField("position") and v.position.longitude else None,
                "bearing": v.position.bearing if v.HasField("position") and v.position.bearing else None,
                "speed": v.position.speed if v.HasField("position") and v.position.speed else None,
                "current_stop_sequence": (
                    v.current_stop_sequence if v.current_stop_sequence is not None else None
                ),
                "stop_id": v.stop_id if v.stop_id else None,
                "current_status": (
                    gtfs_realtime_pb2.VehiclePosition.VehicleStopStatus.Name(v.current_status)
                    if v.HasField("current_status")
                    else None
                ),
            }

            if record["timestamp"]:
                record["observation_time_utc"] = datetime.fromtimestamp(
                    record["timestamp"], tz=timezone.utc
                ).isoformat()
            else:
                record["observation_time_utc"] = None

            records.append(record)

        return header_info, records

    @classmethod
    def to_dataframe(cls, records: List[Dict[str, Any]]) -> pd.DataFrame:
        if not records:
            return pd.DataFrame(
                columns=[
                    "entity_id",
                    "vehicle_id",
                    "trip_id",
                    "route_id",
                    "latitude",
                    "longitude",
                    "bearing",
                    "speed",
                    "current_stop_sequence",
                    "stop_id",
                    "current_status",
                    "timestamp",
                    "observation_time_utc",
                ]
            )
        df = pd.DataFrame(records)
        str_cols = ["entity_id", "vehicle_id", "trip_id", "route_id", "stop_id"]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype("string")
        return df
