import datetime
from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    DateTime,
    Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class VehiclePositionRaw(Base):
    __tablename__ = "vehicle_positions_raw"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, nullable=False, index=True)
    vehicle_id = Column(String(64), nullable=False, index=True)
    trip_id = Column(String(128), nullable=True, index=True)
    route_id = Column(String(64), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    bearing = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    current_stop_sequence = Column(Integer, nullable=True)
    stop_id = Column(String(64), nullable=True, index=True)
    vehicle_status = Column(String(32), nullable=True)
    ingestion_timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_vehicle_time", "vehicle_id", "timestamp"),
        Index("idx_route_time", "route_id", "timestamp"),
    )


class HeadwayObservation(Base):
    __tablename__ = "headway_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, nullable=False, index=True)
    route_id = Column(String(64), nullable=False, index=True)
    stop_id = Column(String(64), nullable=True, index=True)
    vehicle_id = Column(String(64), nullable=False, index=True)
    previous_vehicle_id = Column(String(64), nullable=False)
    headway_seconds = Column(Float, nullable=False)
    space_gap_meters = Column(Float, nullable=True)
    expected_headway_seconds = Column(Float, nullable=False)
    headway_deviation = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_headway_route_time", "route_id", "timestamp"),
    )


class BunchingEvent(Base):
    __tablename__ = "bunching_events"

    event_id = Column(String(64), primary_key=True)
    route_id = Column(String(64), nullable=False, index=True)
    stop_id = Column(String(64), nullable=True, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    leading_vehicle_id = Column(String(64), nullable=False)
    trailing_vehicle_id = Column(String(64), nullable=False)
    observed_headway = Column(Float, nullable=False)
    following_gap = Column(Float, nullable=True)
    expected_headway = Column(Float, nullable=False)
    severity = Column(String(16), nullable=False)  # NORMAL, LOW, MODERATE, HIGH, SEVERE
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_bunching_route_severity", "route_id", "severity"),
    )
