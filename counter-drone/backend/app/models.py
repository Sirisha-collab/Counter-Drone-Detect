
# Three tables:

#   detections — one row per object, per tick. The raw firehose.
#   tracks     — one row per Track ID. The rolled-up summary.
#   events     — notable moments 

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[str] = mapped_column(String(16), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Polar report, as a sensor would give it
    distance_m: Mapped[float] = mapped_column(Float)
    bearing_deg: Mapped[float] = mapped_column(Float)
    altitude_m: Mapped[float] = mapped_column(Float)
    speed_mps: Mapped[float] = mapped_column(Float)
    heading_deg: Mapped[float] = mapped_column(Float)
    rssi_dbm: Mapped[float] = mapped_column(Float)

    # Same position, converted for the map
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    __table_args__ = (Index("ix_detections_track_time", "track_id", "timestamp"),)


class Track(Base):
    __tablename__ = "tracks"

    track_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    status: Mapped[str] = mapped_column(String(16), default="active")  # active | lost
    classification: Mapped[str] = mapped_column(String(24), default="unknown")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    detection_count: Mapped[int] = mapped_column(Integer, default=0)
    closest_approach_m: Mapped[float] = mapped_column(Float, default=0.0)
    max_speed_mps: Mapped[float] = mapped_column(Float, default=0.0)

    # Kept only so you can compare the model's guess against the truth while
    # learning. A real sensor never gets this column.
    ground_truth: Mapped[str] = mapped_column(String(24), default="unknown")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    track_id: Mapped[str | None] = mapped_column(
        ForeignKey("tracks.track_id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info | caution | alert
    message: Mapped[str] = mapped_column(String(255))
