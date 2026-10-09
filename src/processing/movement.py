import math
import logging
from typing import Any, Dict, List, Optional
from src.ingestion.gtfs_loader import GTFSFeed

logger = logging.getLogger(__name__)

EARTH_RADIUS_METERS = 6371000.0


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two geographic coordinates in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates forward compass azimuth/bearing from point 1 to point 2 in degrees (0..360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    initial_bearing = math.atan2(y, x)
    return (math.degrees(initial_bearing) + 360.0) % 360.0


def calculate_speed_kmh(
    lat1: float, lon1: float, t1: int, lat2: float, lon2: float, t2: int
) -> Optional[float]:
    delta_t = t2 - t1
    if delta_t <= 0:
        return None
    dist_m = haversine_distance_meters(lat1, lon1, lat2, lon2)
    speed_mps = dist_m / delta_t
    speed_kmh = speed_mps * 3.6
    # Cap unrealistic speed spikes (e.g. GPS jumps > 120 km/h in city traffic)
    return min(speed_kmh, 120.0)


class MovementReconstructor:
    def __init__(self, feed: Optional[GTFSFeed] = None):
        self.feed = feed
        self._trip_stats: Dict[str, Dict[str, int]] = {}
        self._trip_seq_stops: Dict[tuple, str] = {}
        self._stops_info: Dict[str, Dict[str, Any]] = {}

        if feed is not None:
            self._build_indices(feed)

    def _build_indices(self, feed: GTFSFeed) -> None:
        logger.debug("Building spatial lookup indices from GTFS feed...")
        st = feed.stop_times
        stops = feed.stops

        # 1. Stops coordinate & name lookup
        if "stop_id" in stops.columns:
            for _, row in stops.iterrows():
                self._stops_info[str(row["stop_id"])] = {
                    "stop_name": str(row.get("stop_name", "")),
                    "stop_lat": float(row.get("stop_lat", 0.0)),
                    "stop_lon": float(row.get("stop_lon", 0.0)),
                }

        # 2. Trip min, max, total stops stats
        if "trip_id" in st.columns and "stop_sequence" in st.columns:
            trip_stats_df = st.groupby("trip_id")["stop_sequence"].agg(["min", "max", "count"])
            for t_id, row in trip_stats_df.iterrows():
                self._trip_stats[str(t_id)] = {
                    "min": int(row["min"]),
                    "max": int(row["max"]),
                    "count": int(row["count"]),
                }

            # Map (trip_id, sequence) -> stop_id
            for _, row in st[["trip_id", "stop_sequence", "stop_id"]].iterrows():
                self._trip_seq_stops[(str(row["trip_id"]), int(row["stop_sequence"]))] = str(row["stop_id"])

    def reconstruct_kinematics(
        self, prev_obs: Dict[str, Any], curr_obs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculates speed and heading between two consecutive telemetry pings of the same bus."""
        p_lat = prev_obs.get("latitude")
        p_lon = prev_obs.get("longitude")
        p_t = prev_obs.get("timestamp")

        c_lat = curr_obs.get("latitude")
        c_lon = curr_obs.get("longitude")
        c_t = curr_obs.get("timestamp")

        speed = curr_obs.get("speed")
        bearing = curr_obs.get("bearing")

        if p_lat is not None and p_lon is not None and p_t is not None:
            if speed is None or speed == 0.0:
                speed = calculate_speed_kmh(p_lat, p_lon, p_t, c_lat, c_lon, c_t)
            if bearing is None or bearing == 0.0:
                dist = haversine_distance_meters(p_lat, p_lon, c_lat, c_lon)
                if dist > 5.0:  # Only compute heading if vehicle moved > 5 meters
                    bearing = calculate_bearing(p_lat, p_lon, c_lat, c_lon)

        result = dict(curr_obs)
        result["speed"] = speed
        result["bearing"] = bearing
        return result

    def match_trip_progress(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        """Matches observation against static GTFS trip schedule in O(1) time."""
        result = dict(obs)
        trip_id = obs.get("trip_id")
        seq = obs.get("current_stop_sequence")

        if not self._trip_stats or not trip_id:
            return result

        t_str = str(trip_id)
        stats = self._trip_stats.get(t_str)
        if not stats:
            return result

        total_stops = stats["count"]
        if seq is not None and total_stops > 0:
            seq_val = int(seq)
            min_seq = stats["min"]
            max_seq = stats["max"]
            seq_range = max(1, max_seq - min_seq)
            progress_pct = min(1.0, max(0.0, (seq_val - min_seq) / seq_range))
            result["route_progress"] = round(progress_pct, 4)
            result["total_stops"] = total_stops

            # Stop lookup
            stop_id = self._trip_seq_stops.get((t_str, seq_val))
            if stop_id:
                result["stop_id"] = stop_id
                s_info = self._stops_info.get(stop_id)
                if s_info:
                    result["stop_name"] = s_info["stop_name"]
                    s_lat = s_info["stop_lat"]
                    s_lon = s_info["stop_lon"]
                    if s_lat and s_lon and obs.get("latitude") and obs.get("longitude"):
                        result["dist_to_stop_m"] = round(
                            haversine_distance_meters(obs["latitude"], obs["longitude"], s_lat, s_lon), 1
                        )

        return result
