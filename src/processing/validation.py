import logging
from typing import Dict, List
from dataclasses import dataclass, field
import pandas as pd

from src.config import settings
from src.ingestion.gtfs_loader import GTFSFeed

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    is_valid: bool = True
    table_counts: Dict[str, int] = field(default_factory=dict)
    coordinate_anomalies: int = 0
    orphaned_trips: int = 0
    orphaned_stop_times: int = 0
    missing_stop_references: int = 0
    sequence_errors: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def print_summary(self) -> None:
        print("=" * 60)
        print("GTFS VALIDATION REPORT")
        print("=" * 60)
        print(f"Overall Status: {'PASSED' if self.is_valid else 'FAILED'}")
        print("\nTable Record Counts:")
        for tbl, count in self.table_counts.items():
            print(f"  - {tbl:<12}: {count:>8,}")

        print("\nIntegrity Checks:")
        print(f"  - Coordinate anomalies (outside NCR bbox) : {self.coordinate_anomalies:>6}")
        print(f"  - Orphaned trips (route_id not in routes) : {self.orphaned_trips:>6}")
        print(f"  - Orphaned stop_times (trip_id not in trips): {self.orphaned_stop_times:>6}")
        print(f"  - Missing stop refs (stop_id not in stops) : {self.missing_stop_references:>6}")
        print(f"  - Stop sequence errors (non-monotonic)   : {self.sequence_errors:>6}")

        if self.warnings:
            print("\nWarnings:")
            for w in self.warnings:
                print(f"  * [WARN] {w}")

        if self.errors:
            print("\nErrors:")
            for e in self.errors:
                print(f"  ! [ERROR] {e}")
        print("=" * 60)


class GTFSValidator:
    def __init__(self, feed: GTFSFeed):
        self.feed = feed

    def validate_coordinates(self, report: ValidationReport) -> None:
        stops = self.feed.stops
        if "stop_lat" not in stops.columns or "stop_lon" not in stops.columns:
            report.errors.append("stops.txt missing stop_lat or stop_lon columns")
            report.is_valid = False
            return

        valid_lat = stops["stop_lat"].between(settings.geo.lat_min, settings.geo.lat_max)
        valid_lon = stops["stop_lon"].between(settings.geo.lon_min, settings.geo.lon_max)
        anomalies = (~valid_lat | ~valid_lon).sum()
        report.coordinate_anomalies = int(anomalies)

        if anomalies > 0:
            report.warnings.append(
                f"{anomalies} stops out of {len(stops)} fall outside Delhi NCR bounding box "
                f"[{settings.geo.lat_min}..{settings.geo.lat_max}, {settings.geo.lon_min}..{settings.geo.lon_max}]"
            )

    def validate_relational_integrity(self, report: ValidationReport) -> None:
        route_ids = set(self.feed.routes["route_id"].unique())
        trip_route_ids = set(self.feed.trips["route_id"].unique())
        orphaned_routes = trip_route_ids - route_ids
        report.orphaned_trips = len(self.feed.trips[self.feed.trips["route_id"].isin(orphaned_routes)])

        if report.orphaned_trips > 0:
            report.errors.append(
                f"Found {report.orphaned_trips} trips referencing {len(orphaned_routes)} unknown route_ids."
            )
            report.is_valid = False

        trip_ids = set(self.feed.trips["trip_id"].unique())
        st_trip_ids = set(self.feed.stop_times["trip_id"].unique())
        orphaned_trips_in_st = st_trip_ids - trip_ids
        report.orphaned_stop_times = len(self.feed.stop_times[self.feed.stop_times["trip_id"].isin(orphaned_trips_in_st)])

        if report.orphaned_stop_times > 0:
            report.errors.append(
                f"Found {report.orphaned_stop_times} stop_times referencing {len(orphaned_trips_in_st)} unknown trip_ids."
            )
            report.is_valid = False

        stop_ids = set(self.feed.stops["stop_id"].unique())
        st_stop_ids = set(self.feed.stop_times["stop_id"].unique())
        missing_stops = st_stop_ids - stop_ids
        report.missing_stop_references = len(self.feed.stop_times[self.feed.stop_times["stop_id"].isin(missing_stops)])

        if report.missing_stop_references > 0:
            report.errors.append(
                f"Found {report.missing_stop_references} stop_times referencing {len(missing_stops)} unknown stop_ids."
            )
            report.is_valid = False

    def validate_sequences(self, report: ValidationReport) -> None:
        st = self.feed.stop_times
        if "trip_id" not in st.columns or "stop_sequence" not in st.columns:
            return

        duplicates = int(st.duplicated(subset=["trip_id", "stop_sequence"]).sum())
        in_order_diff = st.groupby("trip_id", sort=False)["stop_sequence"].diff()
        inversions = int((in_order_diff.dropna() <= 0).sum())

        report.sequence_errors = max(duplicates, inversions)

        if report.sequence_errors > 0:
            report.warnings.append(
                f"Found {report.sequence_errors} sequence anomalies (duplicates or out-of-order steps)."
            )

    def validate(self) -> ValidationReport:
        report = ValidationReport()
        report.table_counts = self.feed.summary()

        self.validate_coordinates(report)
        self.validate_relational_integrity(report)
        self.validate_sequences(report)

        return report
