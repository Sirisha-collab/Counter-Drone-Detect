# the only source of data in this project.

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .config import settings
from .geo import destination_point

PROFILES: dict[str, dict] = {
    "quadcopter": {
        "truth": "drone",
        "speed": (8.0, 18.0),
        "altitude": (40.0, 140.0),
        "rssi_ref": -56.0,
        "turn": 6.0,
        "homing": 0.14,
        "speed_jitter": 0.9,
        "alt_jitter": 2.0,
        "rssi_jitter": 2.0,
    },
    "fixed_wing_uas": {
        "truth": "drone",
        "speed": (18.0, 26.0),
        "altitude": (120.0, 220.0),
        "rssi_ref": -60.0,
        "turn": 4.0,
        "homing": 0.10,
        "speed_jitter": 1.0,
        "alt_jitter": 2.5,
        "rssi_jitter": 2.2,
    },
    "bird_flock": {
        "truth": "bird",
        "speed": (5.0, 14.0),
        "altitude": (20.0, 90.0),
        "rssi_ref": -78.0,
        "turn": 34.0,
        "homing": 0.03,
        "speed_jitter": 2.2,
        "alt_jitter": 5.0,
        "rssi_jitter": 4.5,
    },
    "ground_clutter": {
        "truth": "clutter",
        "speed": (0.5, 8.0),
        "altitude": (5.0, 45.0),
        "rssi_ref": -87.0,
        "turn": 50.0,
        "homing": 0.0,
        "speed_jitter": 3.2,
        "alt_jitter": 6.0,
        "rssi_jitter": 9.0,
    },
}


REVERSION = 0.3

PATH_LOSS_DB_PER_DECADE = 15.0

PROFILE_WEIGHTS = [0.34, 0.16, 0.28, 0.22]


@dataclass
class SimulatedObject:
    track_id: str
    profile: str
    truth: str
    distance_m: float
    bearing_deg: float
    altitude_m: float
    speed_mps: float
    heading_deg: float
    rssi_dbm: float
    cruise_speed_mps: float
    cruise_altitude_m: float
    outbound: bool = False
    born_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _new_track_id() -> str:
    return f"TRK-{uuid.uuid4().hex[:4].upper()}"


class DroneSimulator:

    def __init__(self, realtime: bool = True) -> None:

        self.realtime = realtime
        self.clock = datetime.now(timezone.utc)
        self.objects: dict[str, SimulatedObject] = {}
        self.total_spawned = 0
        for _ in range(settings.min_active_objects):
            self.spawn()

    def _now(self) -> datetime:
        if self.realtime:
            return datetime.now(timezone.utc)
        self.clock += timedelta(seconds=settings.tick_seconds)
        return self.clock

    # ------------------------------------------------------------- spawn
    def spawn(self) -> SimulatedObject:
        name = random.choices(list(PROFILES), weights=PROFILE_WEIGHTS, k=1)[0]
        p = PROFILES[name]

        bearing = random.uniform(0, 360)

        distance = random.uniform(
            settings.detection_range_m * 0.40, settings.detection_range_m * 0.95
        )
        cruise_speed = random.uniform(*p["speed"])
        cruise_alt = random.uniform(*p["altitude"])

        obj = SimulatedObject(
            track_id=_new_track_id(),
            profile=name,
            truth=p["truth"],
            distance_m=distance,
            bearing_deg=bearing,
            altitude_m=cruise_alt,
            speed_mps=cruise_speed,
            heading_deg=(bearing + 180 + random.uniform(-45, 45)) % 360,
            rssi_dbm=p["rssi_ref"],
            cruise_speed_mps=cruise_speed,
            cruise_altitude_m=cruise_alt,
        )
        self.objects[obj.track_id] = obj
        self.total_spawned += 1
        return obj

    # -------------------------------------------------------------- tick
    def tick(self) -> tuple[list[dict], list[str]]:

        now = self._now()
        dt = settings.tick_seconds
        detections: list[dict] = []
        departed: list[str] = []

        for obj in list(self.objects.values()):
            p = PROFILES[obj.profile]


            obj.heading_deg = (obj.heading_deg + random.gauss(0, p["turn"])) % 360

            if p["homing"]:

                if obj.distance_m < 300.0:
                    obj.outbound = True
                target = obj.bearing_deg if obj.outbound else (obj.bearing_deg + 180.0) % 360.0
                error = (target - obj.heading_deg + 540.0) % 360.0 - 180.0
                obj.heading_deg = (obj.heading_deg + p["homing"] * error) % 360
            obj.speed_mps = max(
                0.4,
                obj.speed_mps
                + REVERSION * (obj.cruise_speed_mps - obj.speed_mps)
                + random.gauss(0, p["speed_jitter"]),
            )
            obj.altitude_m = max(
                3.0,
                obj.altitude_m
                + REVERSION * (obj.cruise_altitude_m - obj.altitude_m)
                + random.gauss(0, p["alt_jitter"]),
            )

            travelled = obj.speed_mps * dt
            lat, lon = destination_point(
                settings.sensor_lat, settings.sensor_lon, obj.bearing_deg, obj.distance_m
            )
            new_lat, new_lon = destination_point(
                lat, lon, obj.heading_deg, travelled
            )
            obj.distance_m, obj.bearing_deg = self._to_polar(new_lat, new_lon)

            # --- signal strength ---------------------------------------

            km = max(0.05, obj.distance_m / 1000.0)
            falloff = PATH_LOSS_DB_PER_DECADE * math.log10(km)
            obj.rssi_dbm = round(
                p["rssi_ref"] - falloff + random.gauss(0, p["rssi_jitter"]), 1
            )

            # --- did it leave coverage? ---------------------------------
            if obj.distance_m > settings.detection_range_m:
                departed.append(obj.track_id)
                del self.objects[obj.track_id]
                continue

            detections.append(
                {
                    "track_id": obj.track_id,
                    "timestamp": now,
                    "distance_m": round(obj.distance_m, 1),
                    "bearing_deg": round(obj.bearing_deg, 1),
                    "altitude_m": round(obj.altitude_m, 1),
                    "speed_mps": round(obj.speed_mps, 2),
                    "heading_deg": round(obj.heading_deg, 1),
                    "rssi_dbm": obj.rssi_dbm,
                    "lat": new_lat,
                    "lon": new_lon,
                    "ground_truth": obj.truth,
                }
            )

        # --- top the airspace back up -----------------------------------
        if len(self.objects) < settings.min_active_objects or (
            len(self.objects) < settings.max_active_objects
            and random.random() < settings.spawn_chance
        ):
            self.spawn()

        return detections, departed

    # ------------------------------------------------------------ helper
    @staticmethod
    def _to_polar(lat: float, lon: float) -> tuple[float, float]:
        
        lat1 = math.radians(settings.sensor_lat)
        lat2 = math.radians(lat)
        dlon = math.radians(lon - settings.sensor_lon)

        # Haversine for range
        dlat = lat2 - lat1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance = 6_371_000.0 * 2 * math.asin(min(1.0, math.sqrt(a)))

        # Forward azimuth for bearing
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = (math.degrees(math.atan2(y, x)) + 360) % 360

        return distance, bearing
