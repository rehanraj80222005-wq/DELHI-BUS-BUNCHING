import logging
from typing import Any, Dict, List
import pandas as pd
from sqlalchemy.orm import Session
from src.database.models import BunchingEvent, HeadwayObservation

logger = logging.getLogger(__name__)


class HistoricalAnalytics:
    def __init__(self, session: Session):
        self.session = session

    def get_route_bunching_rankings(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns routes ordered by frequency of bunching incidents."""
        events = self.session.query(BunchingEvent).all()
        if not events:
            return []

        df = pd.DataFrame([{
            "route_id": e.route_id,
            "severity": e.severity,
            "observed_headway": e.observed_headway,
        } for e in events])

        grouped = df.groupby("route_id").agg(
            total_events=("severity", "count"),
            severe_events=("severity", lambda s: (s == "SEVERE").sum()),
            high_events=("severity", lambda s: (s == "HIGH").sum()),
            avg_bunching_headway=("observed_headway", "mean"),
        ).reset_index()

        ranked = grouped.sort_values(by=["severe_events", "total_events"], ascending=False).head(limit)
        return ranked.to_dict(orient="records")

    def get_stop_hotspots(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Returns stop IDs and sequences with recurring bunching."""
        events = self.session.query(BunchingEvent).all()
        if not events:
            return []

        df = pd.DataFrame([{
            "route_id": e.route_id,
            "stop_id": e.stop_id or "UNKNOWN",
            "severity": e.severity,
        } for e in events])

        grouped = df.groupby(["stop_id", "route_id"]).size().reset_index(name="incident_count")
        ranked = grouped.sort_values(by="incident_count", ascending=False).head(limit)
        return ranked.to_dict(orient="records")

    def get_time_of_day_distribution(self) -> Dict[int, int]:
        """Returns hourly counts of bunching occurrences."""
        events = self.session.query(BunchingEvent).all()
        distribution = {h: 0 for h in range(24)}
        for e in events:
            if e.start_time:
                hour = e.start_time.hour
                distribution[hour] = distribution.get(hour, 0) + 1
        return distribution

    def get_headway_summary_statistics(self) -> Dict[str, float]:
        """Empirical summary stats across recorded headways."""
        observations = self.session.query(HeadwayObservation).all()
        if not observations:
            return {"count": 0, "mean": 0.0, "median": 0.0, "std": 0.0}

        headways = [o.headway_seconds for o in observations]
        s = pd.Series(headways)
        return {
            "count": int(s.count()),
            "mean": round(float(s.mean()), 1),
            "median": round(float(s.median()), 1),
            "std": round(float(s.std()), 1),
            "min": round(float(s.min()), 1),
            "max": round(float(s.max()), 1),
        }
