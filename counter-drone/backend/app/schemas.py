"""Pydantic models — these define the exact JSON shape the frontend receives."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: str
    timestamp: datetime
    distance_m: float
    bearing_deg: float
    altitude_m: float
    speed_mps: float
    heading_deg: float
    rssi_dbm: float
    lat: float
    lon: float


class TrackPoint(BaseModel):

    lat: float
    lon: float
    timestamp: datetime

    distance_m: float
    bearing_deg: float
    altitude_m: float
    speed_mps: float
    heading_deg: float
    rssi_dbm: float


class EvidenceItem(BaseModel):

    feature: str          # machine name, e.g. "heading_std_deg"
    label: str            # human name, e.g. "Turn per report"
    value: float
    display_value: str    # pre-formatted with its unit
    contribution: float   # how far it moved the predicted probability
    direction: str        # "supports" | "opposes"
    statement: str        # a sentence the operator can check


class TrackOut(BaseModel):

    track_id: str
    status: str
    classification: str
    confidence: float

    lat: float
    lon: float
    distance_m: float
    bearing_deg: float
    compass: str
    altitude_m: float
    speed_mps: float
    heading_deg: float
    rssi_dbm: float

    first_seen: datetime
    last_seen: datetime
    detection_count: int
    closest_approach_m: float
    in_alert_zone: bool

    # Why the classifier decided what it decided.
    evidence: list[EvidenceItem]
    evidence_summary: str

    history: list[TrackPoint]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    timestamp: datetime
    track_id: str | None
    event_type: str
    severity: str
    message: str


class Stats(BaseModel):
    total_detections: int      # every detection since the server started
    active_tracks: int
    drone_tracks: int
    alerts_active: int
    tracks_opened: int
    tracks_lost: int
    uptime_seconds: float


class SensorInfo(BaseModel):
    name: str
    lat: float
    lon: float
    range_m: float
    alert_radius_m: float
    tick_seconds: float


class LiveFrame(BaseModel):

    type: str = "frame"
    timestamp: datetime
    sensor: SensorInfo
    stats: Stats
    tracks: list[TrackOut]
    events: list[EventOut]
    model_ready: bool
