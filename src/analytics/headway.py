import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict
from src.processing.movement import haversine_distance_meters

logger = logging.getLogger(__name__)

DEFAULT_EXPECTED_HEADWAY_SECONDS = 600.0  # 10 minutes


class HeadwayEngine:
    def __init__(self, default_expected_headway: float = DEFAULT_EXPECTED_HEADWAY_SECONDS):
        self.default_expected_headway = default_expected_headway

    def calculate_headways_for_snapshot(
        self, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Computes observed headway between consecutive buses running on each route."""
        # 1. Group active observations by route_id
        route_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in records:
            r_id = str(r.get("route_id", ""))
            if r_id:
                route_groups[r_id].append(r)

        headway_observations: List[Dict[str, Any]] = []

        for route_id, buses in route_groups.items():
            if len(buses) < 2:
                continue

            # 2. Sort buses by stop sequence along their trip (from head to tail)
            sorted_buses = sorted(
                buses,
                key=lambda b: (b.get("current_stop_sequence") or 0, b.get("timestamp") or 0),
                reverse=True,
            )

            # 3. Calculate headways between consecutive pairs
            for idx in range(len(sorted_buses) - 1):
                leading_bus = sorted_buses[idx]
                trailing_bus = sorted_buses[idx + 1]

                lead_seq = leading_bus.get("current_stop_sequence") or 0
                trail_seq = trailing_bus.get("current_stop_sequence") or 0

                # Space gap in meters
                space_gap_m = haversine_distance_meters(
                    float(leading_bus["latitude"]),
                    float(leading_bus["longitude"]),
                    float(trailing_bus["latitude"]),
                    float(trailing_bus["longitude"]),
                )

                # Estimate time headway:
                # If buses are at different stop sequences, headway can be estimated using speed
                # or reference schedule. In Delhi city traffic, avg bus speed ~ 15-20 km/h (~4.5 m/s).
                avg_speed_mps = 4.5
                lead_speed = leading_bus.get("speed")
                trail_speed = trailing_bus.get("speed")
                if lead_speed and lead_speed > 5:
                    avg_speed_mps = lead_speed / 3.6
                elif trail_speed and trail_speed > 5:
                    avg_speed_mps = trail_speed / 3.6

                time_gap_seconds = max(30.0, space_gap_m / max(1.0, avg_speed_mps))

                expected = self.default_expected_headway
                headway_deviation = (time_gap_seconds - expected) / expected

                headway_obs = {
                    "timestamp": trailing_bus["timestamp"],
                    "route_id": route_id,
                    "stop_id": trailing_bus.get("stop_id") or leading_bus.get("stop_id") or f"SEQ_{trail_seq}",
                    "vehicle_id": trailing_bus["vehicle_id"],
                    "previous_vehicle_id": leading_bus["vehicle_id"],
                    "headway_seconds": round(time_gap_seconds, 1),
                    "space_gap_meters": round(space_gap_m, 1),
                    "expected_headway_seconds": round(expected, 1),
                    "headway_deviation": round(headway_deviation, 4),
                    "lead_sequence": lead_seq,
                    "trail_sequence": trail_seq,
                    "sequence_diff": lead_seq - trail_seq,
                }
                headway_observations.append(headway_obs)

        return headway_observations
