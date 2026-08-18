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
    """
    One past report. Carries every sensor channel, not just position, so the
    dashboard can draw a sparkline for each channel without a second request.
    """

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
    """One reason behind a classification, with the number it rests on."""

    feature: str          # machine name, e.g. "heading_std_deg"
    label: str            # human name, e.g. "Turn per report"
    value: float
    display_value: str    # pre-formatted with its unit
    contribution: float   # how far it moved the predicted probability
    direction: str        # "supports" | "opposes"
    statement: str        # a sentence the operator can check


class ScoreFactor(BaseModel):
    """One component of the priority score, with the points it contributed."""

    name: str
    points: float
    max: float
    note: str


class ConfidenceBasis(BaseModel):
    """One input to the calibrated confidence."""

    name: str
    value: float
    note: str


class TrackOut(BaseModel):
    """A live track as shown on the map and in the track list."""

    track_id: str
    status: str            # active | coasting
    confirmed: bool
    coasted_ticks: int
    classification: str
    confidence: float             # raw model probability
    confidence_calibrated: float  # tempered by track maturity and stability
    confidence_basis: list[ConfidenceBasis]

    priority_score: int           # 0-100, how much operator attention is due
    priority_level: str           # routine | watch | elevated | urgent
    priority_summary: str
    priority_factors: list[ScoreFactor]

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
    top_priority: int
    priority_tracks: int   # tracks at "elevated" or above

    # Data-association health
    id_switches: int            # times a track swapped onto a different object
    tentative_tracks: int       # seen once, not yet confirmed
    coasting_tracks: int        # predicted through a missed detection
    association_method: str
    contested_detections: int   # detections inside more than one track's gate
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
    """The payload pushed over the WebSocket on every tick."""

    type: str = "frame"
    timestamp: datetime
    sensor: SensorInfo
    stats: Stats
    tracks: list[TrackOut]
    events: list[EventOut]
    model_ready: bool
