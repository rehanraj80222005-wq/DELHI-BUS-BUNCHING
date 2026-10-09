import uuid
import datetime
import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class BunchingDetector:
    def __init__(
        self,
        bunching_threshold_ratio: float = 0.35,  # Headway <= 35% of expected
        bunching_distance_meters: float = 400.0,  # Or physical distance < 400m
    ):
        self.bunching_threshold_ratio = bunching_threshold_ratio
        self.bunching_distance_meters = bunching_distance_meters

    def classify_severity(
        self,
        headway_sec: float,
        expected_sec: float,
        space_gap_m: float,
        following_gap_sec: Optional[float] = None,
    ) -> str:
        ratio = headway_sec / max(1.0, expected_sec)
        following_ratio = (following_gap_sec / expected_sec) if following_gap_sec else 1.0

        if ratio <= 0.20 or space_gap_m <= 200.0:
            if following_ratio >= 1.7:
                return "SEVERE"
            return "HIGH"
        elif ratio <= 0.35 or space_gap_m <= 400.0:
            if following_ratio >= 1.4:
                return "HIGH"
            return "MODERATE"
        elif ratio <= 0.50 or space_gap_m <= 750.0:
            return "LOW"
        return "NORMAL"

    def detect_bunching_events(
        self, headway_observations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Scans headway observations to identify bunched vehicle pairs and grade severity."""
        # Group headway observations by route
        route_obs = defaultdict(list)
        for h in headway_observations:
            route_obs[h["route_id"]].append(h)

        events: List[Dict[str, Any]] = []

        for route_id, obs_list in route_obs.items():
            for i, obs in enumerate(obs_list):
                headway = obs["headway_seconds"]
                expected = obs["expected_headway_seconds"]
                space_m = obs.get("space_gap_meters", 1000.0)

                # Lookahead to see subsequent gap behind this trailing bus
                following_gap = None
                if i + 1 < len(obs_list):
                    following_gap = obs_list[i + 1]["headway_seconds"]

                severity = self.classify_severity(headway, expected, space_m, following_gap)

                if severity != "NORMAL":
                    ts = obs.get("timestamp") or int(datetime.datetime.utcnow().timestamp())
                    event = {
                        "event_id": str(uuid.uuid4())[:12],
                        "route_id": str(route_id),
                        "stop_id": obs.get("stop_id"),
                        "start_time": datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).replace(tzinfo=None),
                        "end_time": None,
                        "leading_vehicle_id": obs["previous_vehicle_id"],
                        "trailing_vehicle_id": obs["vehicle_id"],
                        "observed_headway": headway,
                        "following_gap": following_gap,
                        "expected_headway": expected,
                        "severity": severity,
                    }
                    events.append(event)

        return events
