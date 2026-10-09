import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from src.database.models import VehiclePositionRaw, HeadwayObservation, BunchingEvent

logger = logging.getLogger(__name__)


class TransitRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_vehicle_positions(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0

        entities = []
        for r in records:
            entities.append(
                VehiclePositionRaw(
                    timestamp=r["timestamp"],
                    vehicle_id=r["vehicle_id"],
                    trip_id=r.get("trip_id"),
                    route_id=r["route_id"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    bearing=r.get("bearing"),
                    speed=r.get("speed"),
                    current_stop_sequence=r.get("current_stop_sequence"),
                    stop_id=r.get("stop_id"),
                    vehicle_status=r.get("current_status"),
                )
            )

        self.session.bulk_save_objects(entities)
        self.session.commit()
        logger.debug("Committed %d vehicle positions to database", len(entities))
        return len(entities)

    def get_latest_positions(self, limit: int = 5000) -> List[VehiclePositionRaw]:
        return (
            self.session.query(VehiclePositionRaw)
            .order_by(desc(VehiclePositionRaw.timestamp))
            .limit(limit)
            .all()
        )

    def get_route_latest_positions(self, route_id: str) -> List[VehiclePositionRaw]:
        return (
            self.session.query(VehiclePositionRaw)
            .filter(VehiclePositionRaw.route_id == str(route_id))
            .order_by(desc(VehiclePositionRaw.timestamp))
            .all()
        )

    def get_vehicle_history(self, vehicle_id: str, limit: int = 50) -> List[VehiclePositionRaw]:
        return (
            self.session.query(VehiclePositionRaw)
            .filter(VehiclePositionRaw.vehicle_id == str(vehicle_id))
            .order_by(desc(VehiclePositionRaw.timestamp))
            .limit(limit)
            .all()
        )

    def save_headway_observations(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        valid_cols = {c.name for c in HeadwayObservation.__table__.columns}
        entities = [
            HeadwayObservation(**{k: v for k, v in r.items() if k in valid_cols})
            for r in records
        ]
        self.session.bulk_save_objects(entities)
        self.session.commit()
        return len(entities)

    def save_bunching_events(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        valid_cols = {c.name for c in BunchingEvent.__table__.columns}
        entities = [
            BunchingEvent(**{k: v for k, v in r.items() if k in valid_cols})
            for r in records
        ]
        self.session.bulk_save_objects(entities)
        self.session.commit()
        return len(entities)

    def get_recent_bunching_events(self, limit: int = 50) -> List[BunchingEvent]:
        return (
            self.session.query(BunchingEvent)
            .order_by(desc(BunchingEvent.start_time))
            .limit(limit)
            .all()
        )
