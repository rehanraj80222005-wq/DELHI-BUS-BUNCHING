import logging
import time
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass
from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CleaningReport:
    total_received: int = 0
    valid_count: int = 0
    missing_fields_dropped: int = 0
    out_of_bounds_dropped: int = 0
    duplicates_dropped: int = 0
    stale_dropped: int = 0

    def print_summary(self) -> None:
        print("\nData Cleaning Report:")
        print(f"  - Total Ingested       : {self.total_received:>6,}")
        print(f"  - Valid & Accepted     : {self.valid_count:>6,} ({(self.valid_count / max(1, self.total_received)) * 100:.1f}%)")
        print(f"  - Out-of-bounds Dropped: {self.out_of_bounds_dropped:>6,}")
        print(f"  - Missing Keys Dropped : {self.missing_fields_dropped:>6,}")
        print(f"  - Duplicates Dropped   : {self.duplicates_dropped:>6,}")
        print(f"  - Stale Dropped        : {self.stale_dropped:>6,}")


class TelemetryCleaner:
    def __init__(
        self,
        lat_min: float = settings.geo.lat_min,
        lat_max: float = settings.geo.lat_max,
        lon_min: float = settings.geo.lon_min,
        lon_max: float = settings.geo.lon_max,
        max_age_seconds: int = 1800,  # 30 mins
    ):
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.max_age_seconds = max_age_seconds

    def clean(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], CleaningReport]:
        report = CleaningReport(total_received=len(records))
        cleaned: List[Dict[str, Any]] = []
        seen_keys = set()

        if not records:
            return cleaned, report

        feed_max_time = max((r.get("timestamp") or 0) for r in records)
        current_time = int(time.time())
        ref_time = max(feed_max_time, current_time)

        for r in records:
            # 1. Missing essential keys check
            v_id = r.get("vehicle_id")
            r_id = r.get("route_id")
            ts = r.get("timestamp")
            lat = r.get("latitude")
            lon = r.get("longitude")

            if not (v_id and r_id and ts and lat is not None and lon is not None):
                report.missing_fields_dropped += 1
                continue

            try:
                lat = float(lat)
                lon = float(lon)
                ts = int(ts)
            except (ValueError, TypeError):
                report.missing_fields_dropped += 1
                continue

            # 2. Coordinate boundary check (NCR)
            if not (self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max):
                report.out_of_bounds_dropped += 1
                continue

            # 3. Deduplication check (same vehicle, timestamp, and position)
            dedup_key = (v_id, ts, round(lat, 5), round(lon, 5))
            if dedup_key in seen_keys:
                report.duplicates_dropped += 1
                continue
            seen_keys.add(dedup_key)

            # 4. Stale observation check
            if ref_time - ts > self.max_age_seconds:
                report.stale_dropped += 1
                continue

            cleaned.append(r)

        report.valid_count = len(cleaned)
        return cleaned, report
