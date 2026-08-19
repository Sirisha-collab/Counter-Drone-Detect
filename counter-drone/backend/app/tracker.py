"""
The tracking system.

A *detection* is a single instant. A *track* is the story of one Track ID over
time: where it is now, everywhere it has been, how fast it has been going, and
what the classifier thinks it is.

This class is the in-memory source of truth for the dashboard. PostgreSQL keeps
the permanent record; the tracker keeps what's on screen right now.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .association import CONFIRM_AFTER_REPORTS, MAX_COAST_TICKS, associate
from .config import settings
from .geo import compass_label
from .ml.classifier import classifier
from .priority import (
    calibrate_confidence,
    closing_rate,
    score_priority,
    summarise_priority,
)
from .schemas import (
    ConfidenceBasis,
    EventOut,
    EvidenceItem,
    ScoreFactor,
    TrackOut,
    TrackPoint,
)


# How often to rebuild a track's evidence, in ticks. At the default 2 s tick
# that is roughly every 10 seconds per track.
EXPLAIN_EVERY_N_TICKS = 5


@dataclass
class Track:
    track_id: str
    first_seen: datetime
    last_seen: datetime
    ground_truth: str

    latest: dict = field(default_factory=dict)
    # Ring buffer of previous *reports* — drives both the map trail and the
    # per-channel sparklines, so it holds the whole detection, not just x/y.
    history: deque = field(default_factory=lambda: deque(maxlen=settings.history_length))
    # Recent full detections, used to build the ML feature vector.
    samples: deque = field(default_factory=lambda: deque(maxlen=settings.history_length))

    status: str = "active"
    # Set by the tracker itself, never read from a detection.
    confirmed: bool = False
    coasted_ticks: int = 0
    # The simulated object this track is currently following. Used ONLY to
    # score ID switches — the association logic must never look at it.
    truth_id: str = ""
    classification: str = "unknown"
    confidence: float = 0.0
    evidence: list = field(default_factory=list)
    evidence_summary: str = ""
    ticks_since_explain: int = 99

    # Rolling record of past verdicts — feeds the stability term in the
    # calibrated confidence.
    label_history: deque = field(default_factory=lambda: deque(maxlen=10))
    confidence_calibrated: float = 0.0
    confidence_basis: list = field(default_factory=list)
    priority_score: int = 0
    priority_level: str = "routine"
    priority_summary: str = ""
    priority_factors: list = field(default_factory=list)
    detection_count: int = 0
    closest_approach_m: float = float("inf")
    max_speed_mps: float = 0.0
    alerted: bool = False
    escalated: bool = False

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
            confirmed=self.confirmed,
            coasted_ticks=self.coasted_ticks,
            classification=self.classification,
            confidence=round(self.confidence, 3),
            confidence_calibrated=round(self.confidence_calibrated, 3),
            confidence_basis=[ConfidenceBasis(**item) for item in self.confidence_basis],
            priority_score=self.priority_score,
            priority_level=self.priority_level,
            priority_summary=self.priority_summary,
            priority_factors=[ScoreFactor(**item) for item in self.priority_factors],
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
            evidence=[EvidenceItem(**item) for item in self.evidence],
            evidence_summary=self.evidence_summary,
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

        # Sequential rather than random, so the numbering shows how many
        # tracks the system has opened over its life — a useful sanity check
        # when association is misbehaving and churning IDs.
        self._next_id = 1
        self.id_switches = 0
        self.last_association: dict = {"gated_pairs": 0, "method": "none", "contested": 0}
        # {detection index -> track id} for the tick just processed. The
        # database needs it: detections arrive anonymous, so the only record of
        # which track claimed which blip is the association result.
        self.assigned_ids: dict[int, str] = {}

    def _next_track_id(self) -> str:
        track_id = f"TRK-{self._next_id:04d}"
        self._next_id += 1
        return track_id

    # ------------------------------------------------------------- update
    def update(self, detections: list[dict]) -> list[EventOut]:
        """
        Fold this tick's detections into the track picture.

        Detections arrive anonymous. The work of deciding which one continues
        which track happens in `association.associate` — everything after that
        is bookkeeping.
        """
        events: list[EventOut] = []
        self.total_detections += len(detections)
        self.assigned_ids = {}

        existing = list(self.tracks.values())
        result = associate(existing, detections, settings.tick_seconds)
        self.last_association = result["stats"]

        touched: list[Track] = []

        # --- 1. Continue matched tracks --------------------------------------
        for track_index, detection_index in result["matches"].items():
            track = existing[track_index]
            d = detections[detection_index]

            # An ID switch: this detection came from a different simulated
            # object than the one this track has been following. The tracker
            # cannot know this — we only detect it because the simulator tells
            # us the truth, purely so the dashboard can report its own error
            # rate honestly.
            if track.truth_id and d.get("truth_id") and track.truth_id != d["truth_id"]:
                self.id_switches += 1
                events.append(
                    EventOut(
                        timestamp=d["timestamp"],
                        track_id=track.track_id,
                        event_type="id_switch",
                        severity="caution",
                        message=(
                            f"{track.track_id} swapped onto a different object — "
                            "two contacts crossed inside the gate"
                        ),
                    )
                )
            track.truth_id = d.get("truth_id", "")

            if track.latest:
                track.history.append(track.latest)

            track.latest = d
            track.last_seen = d["timestamp"]
            track.status = "active"
            track.coasted_ticks = 0
            track.detection_count += 1
            track.samples.append(d)
            track.closest_approach_m = min(track.closest_approach_m, d["distance_m"])
            track.max_speed_mps = max(track.max_speed_mps, d["speed_mps"])
            track.ground_truth = d.get("ground_truth", track.ground_truth)

            if not track.confirmed and track.detection_count >= CONFIRM_AFTER_REPORTS:
                track.confirmed = True
                self.tracks_opened += 1
                events.append(
                    EventOut(
                        timestamp=d["timestamp"],
                        track_id=track.track_id,
                        event_type="track_confirmed",
                        severity="info",
                        message=(
                            f"{track.track_id} confirmed at {d['distance_m']:.0f} m, "
                            f"bearing {d['bearing_deg']:.0f}°"
                        ),
                    )
                )

            self.assigned_ids[detection_index] = track.track_id
            touched.append(track)

        # --- 2. Birth: detections nothing claimed ----------------------------
        for detection_index in result["unmatched_detections"]:
            d = detections[detection_index]
            track = Track(
                track_id=self._next_track_id(),
                first_seen=d["timestamp"],
                last_seen=d["timestamp"],
                ground_truth=d.get("ground_truth", "unknown"),
                truth_id=d.get("truth_id", ""),
            )
            track.latest = d
            track.samples.append(d)
            track.detection_count = 1
            track.closest_approach_m = d["distance_m"]
            track.max_speed_mps = d["speed_mps"]
            self.tracks[track.track_id] = track
            self.assigned_ids[detection_index] = track.track_id
            touched.append(track)

        # --- 3. Coast: tracks nothing matched --------------------------------
        # They are not deleted yet. A sensor missing one report is normal, so a
        # track is allowed to survive on prediction alone for a few ticks.
        for track_index in result["unmatched_tracks"]:
            track = existing[track_index]
            track.coasted_ticks += 1
            track.status = "coasting"

        # --- 4. Classify, in one batch ---------------------------------------
        # One stacked prediction rather than one call per track: scikit-learn's
        # overhead is per-call, so looping here cost 110 ms a tick against 12 ms
        # batched.
        previous_labels = [t.classification for t in touched]
        verdicts = classifier.predict_many([list(t.samples) for t in touched])

        for track, previous, (label, confidence) in zip(touched, previous_labels, verdicts):
            track.classification = label
            track.confidence = confidence
            d = track.latest
            tid = track.track_id

            # Evidence costs a walk down every tree in the forest, so it is
            # rebuilt on a verdict change or every few ticks — not every report.
            # Confidence jitters by a percent or two each tick, which is not
            # worth re-explaining.
            track.ticks_since_explain += 1
            if label != previous or track.ticks_since_explain >= EXPLAIN_EVERY_N_TICKS:
                track.evidence = classifier.explain(list(track.samples), label)
                track.evidence_summary = classifier.summarise(
                    label, confidence, track.evidence
                )
                track.ticks_since_explain = 0

            # --- calibrated confidence and priority ------------------------
            track.label_history.append(label)
            track.confidence_calibrated, track.confidence_basis = calibrate_confidence(
                confidence, label, track.detection_count, track.label_history
            )
            track.priority_score, track.priority_level, track.priority_factors = (
                score_priority(
                    label=label,
                    calibrated_confidence=track.confidence_calibrated,
                    distance_m=d["distance_m"],
                    n_reports=track.detection_count,
                    approach_mps=closing_rate(list(track.samples)),
                    alert_radius_m=settings.alert_radius_m,
                    detection_range_m=settings.detection_range_m,
                )
            )
            track.priority_summary = summarise_priority(
                track.priority_level, track.priority_score, track.priority_factors
            )

            if track.priority_level == "urgent" and not track.escalated:
                track.escalated = True
                events.append(
                    EventOut(
                        timestamp=d["timestamp"],
                        track_id=tid,
                        event_type="priority_urgent",
                        severity="alert",
                        message=f"{tid} priority {track.priority_score}/100 — {track.priority_summary.split('— ')[-1]}",
                    )
                )
            elif track.priority_level != "urgent":
                track.escalated = False

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
        """
        Retire tracks that have coasted too long or gone stale.

        `departed` now lists *simulated object* IDs that left coverage. It is
        no longer used to delete tracks directly — the tracker must notice
        objects leaving by not being able to match them, exactly as a real
        system would. The parameter is kept so the signature is stable.
        """
        events: list[EventOut] = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=settings.track_timeout_seconds)

        for tid in list(self.tracks):
            track = self.tracks[tid]

            too_long_coasting = track.coasted_ticks > MAX_COAST_TICKS
            stale = track.last_seen < cutoff
            if not (too_long_coasting or stale):
                continue

            # An unconfirmed track that dies was probably never real — a single
            # stray detection. It is dropped quietly rather than reported, or
            # the event log fills with noise.
            if not track.confirmed:
                del self.tracks[tid]
                continue

            track.status = "lost"
            self.tracks_lost += 1
            reason = (
                f"no match for {track.coasted_ticks} ticks"
                if too_long_coasting
                else "no updates"
            )
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
        return sorted(
            (t for t in self.tracks.values() if t.confirmed),
            key=lambda t: t.track_id,          # was: (-t.priority_score, t.latest.get("distance_m", 1e9))
        )

    def snapshot(self) -> list[TrackOut]:
        return [t.to_schema() for t in self.active() if t.latest]

    def counts(self) -> dict:
        active = [t for t in self.tracks.values() if t.latest and t.confirmed]
        return {
            "total_detections": self.total_detections,
            "active_tracks": len(active),
            "drone_tracks": sum(1 for t in active if t.classification == "drone"),
            "alerts_active": sum(1 for t in active if t.in_alert_zone),
            "top_priority": max((t.priority_score for t in active), default=0),
            "priority_tracks": sum(
                1 for t in active if t.priority_level in ("elevated", "urgent")
            ),
            "tracks_opened": self.tracks_opened,
            "tracks_lost": self.tracks_lost,
            "id_switches": self.id_switches,
            "tentative_tracks": sum(1 for t in self.tracks.values() if not t.confirmed),
            "coasting_tracks": sum(1 for t in active if t.status == "coasting"),
            "association_method": self.last_association.get("method", "none"),
            "contested_detections": self.last_association.get("contested", 0),
        }


track_manager = TrackManager()
