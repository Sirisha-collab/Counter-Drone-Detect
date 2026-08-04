from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .config import settings
from .geo import compass_label
from .ml.classifier import classifier
from .schemas import EventOut, TrackOut, TrackPoint


@dataclass
class Track:
    track_id: str
    first_seen: datetime
    last_seen: datetime
    ground_truth: str

    latest: dict = field(default_factory=dict)
    history: deque = field(default_factory=lambda: deque(maxlen=settings.history_length))

    samples: deque = field(default_factory=lambda: deque(maxlen=settings.history_length))

    status: str = "active"
    classification: str = "unknown"
    confidence: float = 0.0
    detection_count: int = 0
    closest_approach_m: float = float("inf")
    max_speed_mps: float = 0.0
    alerted: bool = False

    @property
    def in_alert_zone(self) -> bool:
        return (
            self.classification == "drone"
            and self.latest.get("distance_m", 1e9) <= settings.alert_radius_m
        )

    def to_schema(self) -> TrackOut:
        d = self.latest
        return TrackOut(
            track_id=self.track_id,
            status=self.status,
            classification=self.classification,
            confidence=round(self.confidence, 3),
            lat=d["lat"],
            lon=d["lon"],
            distance_m=d["distance_m"],
            bearing_deg=d["bearing_deg"],
            compass=compass_label(d["bearing_deg"]),
            altitude_m=d["altitude_m"],
            speed_mps=d["speed_mps"],
            heading_deg=d["heading_deg"],
            rssi_dbm=d["rssi_dbm"],
            first_seen=self.first_seen,
            last_seen=self.last_seen,
            detection_count=self.detection_count,
            closest_approach_m=round(self.closest_approach_m, 1),
            in_alert_zone=self.in_alert_zone,
            history=[
                TrackPoint(
                    lat=p["lat"],
                    lon=p["lon"],
                    timestamp=p["timestamp"],
                    distance_m=p["distance_m"],
                    bearing_deg=p["bearing_deg"],
                    altitude_m=p["altitude_m"],
                    speed_mps=p["speed_mps"],
                    heading_deg=p["heading_deg"],
                    rssi_dbm=p["rssi_dbm"],
                )
                for p in self.history
            ],
        )


class TrackManager:
    def __init__(self) -> None:
        self.tracks: dict[str, Track] = {}
        self.total_detections = 0
        self.tracks_opened = 0
        self.tracks_lost = 0

    # ------------------------------------------------------------- update
    def update(self, detections: list[dict]) -> list[EventOut]:
        events: list[EventOut] = []

        for d in detections:
            tid = d["track_id"]
            track = self.tracks.get(tid)

            if track is None:
                track = Track(
                    track_id=tid,
                    first_seen=d["timestamp"],
                    last_seen=d["timestamp"],
                    ground_truth=d.get("ground_truth", "unknown"),
                )
                self.tracks[tid] = track
                self.tracks_opened += 1
                events.append(
                    EventOut(
                        timestamp=d["timestamp"],
                        track_id=tid,
                        event_type="track_opened",
                        severity="info",
                        message=(
                            f"{tid} acquired at {d['distance_m']:.0f} m, "
                            f"bearing {d['bearing_deg']:.0f}°"
                        ),
                    )
                )

            # --- current position becomes part of the trail ---------------
            if track.latest:
                track.history.append(track.latest)

            track.latest = d
            track.last_seen = d["timestamp"]
            track.status = "active"
            track.detection_count += 1
            track.samples.append(d)
            track.closest_approach_m = min(track.closest_approach_m, d["distance_m"])
            track.max_speed_mps = max(track.max_speed_mps, d["speed_mps"])
            self.total_detections += 1

            # --- classify -------------------------------------------------
            previous = track.classification
            label, confidence = classifier.predict(list(track.samples))
            track.classification = label
            track.confidence = confidence

            if label != previous and label != "unknown":
                events.append(
                    EventOut(
                        timestamp=d["timestamp"],
                        track_id=tid,
                        event_type="classified",
                        severity="caution" if label == "drone" else "info",
                        message=f"{tid} classified as {label} ({confidence:.0%} confidence)",
                    )
                )

            # --- alert ring -----------------------------------------------
            if track.in_alert_zone and not track.alerted:
                track.alerted = True
                events.append(
                    EventOut(
                        timestamp=d["timestamp"],
                        track_id=tid,
                        event_type="alert_zone_entry",
                        severity="alert",
                        message=(
                            f"{tid} inside {settings.alert_radius_m:.0f} m ring "
                            f"at {d['distance_m']:.0f} m"
                        ),
                    )
                )
            elif not track.in_alert_zone:
                track.alerted = False

        return events

    # --------------------------------------------------------------- prune
    def prune(self, departed: list[str] | None = None) -> list[EventOut]:

        events: list[EventOut] = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=settings.track_timeout_seconds)

        for tid in list(self.tracks):
            track = self.tracks[tid]
            expired = track.last_seen < cutoff
            if not expired and tid not in (departed or []):
                continue

            reason = "left coverage" if tid in (departed or []) else "no updates"
            track.status = "lost"
            self.tracks_lost += 1
            events.append(
                EventOut(
                    timestamp=now,
                    track_id=tid,
                    event_type="track_lost",
                    severity="info",
                    message=(
                        f"{tid} dropped — {reason} after "
                        f"{track.detection_count} detections"
                    ),
                )
            )
            del self.tracks[tid]

        return events

    # ------------------------------------------------------------ readers
    def active(self) -> list[Track]:
        return sorted(self.tracks.values(), key=lambda t: t.latest.get("distance_m", 1e9))

    def snapshot(self) -> list[TrackOut]:
        return [t.to_schema() for t in self.active() if t.latest]

    def counts(self) -> dict:
        active = [t for t in self.tracks.values() if t.latest]
        return {
            "total_detections": self.total_detections,
            "active_tracks": len(active),
            "drone_tracks": sum(1 for t in active if t.classification == "drone"),
            "alerts_active": sum(1 for t in active if t.in_alert_zone),
            "tracks_opened": self.tracks_opened,
            "tracks_lost": self.tracks_lost,
        }


track_manager = TrackManager()
