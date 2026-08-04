"""
FastAPI entry point.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import SessionLocal, get_session, init_db
from .ml.classifier import classifier
from .models import Detection, Event, Track
from .schemas import DetectionOut, EventOut, LiveFrame, SensorInfo, Stats, TrackOut
from .simulator import DroneSimulator
from .tracker import track_manager
from .ws_manager import manager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(name)s: %(message)s"
)
log = logging.getLogger("cuas")

simulator = DroneSimulator()
STARTED_AT = time.time()
RECENT_EVENTS: list[EventOut] = []  # small in-memory ring for new clients


def sensor_info() -> SensorInfo:
    return SensorInfo(
        name=settings.sensor_name,
        lat=settings.sensor_lat,
        lon=settings.sensor_lon,
        range_m=settings.detection_range_m,
        alert_radius_m=settings.alert_radius_m,
        tick_seconds=settings.tick_seconds,
    )


def build_frame(events: list[EventOut]) -> LiveFrame:
    counts = track_manager.counts()
    return LiveFrame(
        timestamp=datetime.now(timezone.utc),
        sensor=sensor_info(),
        stats=Stats(**counts, uptime_seconds=round(time.time() - STARTED_AT, 1)),
        tracks=track_manager.snapshot(),
        events=events,
        model_ready=classifier.ready,
    )


# ---------------------------------------------------------------- persistence
async def persist(detections: list[dict], events: list[EventOut]) -> None:

    try:
        async with SessionLocal() as session:
            for d in detections:
                session.add(
                    Detection(
                        track_id=d["track_id"],
                        timestamp=d["timestamp"],
                        distance_m=d["distance_m"],
                        bearing_deg=d["bearing_deg"],
                        altitude_m=d["altitude_m"],
                        speed_mps=d["speed_mps"],
                        heading_deg=d["heading_deg"],
                        rssi_dbm=d["rssi_dbm"],
                        lat=d["lat"],
                        lon=d["lon"],
                    )
                )

            # Upsert the track summary rows.
            for d in detections:
                t = track_manager.tracks.get(d["track_id"])
                if not t:
                    continue
                stmt = pg_insert(Track).values(
                    track_id=t.track_id,
                    first_seen=t.first_seen,
                    last_seen=t.last_seen,
                    status=t.status,
                    classification=t.classification,
                    confidence=t.confidence,
                    detection_count=t.detection_count,
                    closest_approach_m=t.closest_approach_m,
                    max_speed_mps=t.max_speed_mps,
                    ground_truth=t.ground_truth,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[Track.track_id],
                    set_={
                        "last_seen": stmt.excluded.last_seen,
                        "status": stmt.excluded.status,
                        "classification": stmt.excluded.classification,
                        "confidence": stmt.excluded.confidence,
                        "detection_count": stmt.excluded.detection_count,
                        "closest_approach_m": stmt.excluded.closest_approach_m,
                        "max_speed_mps": stmt.excluded.max_speed_mps,
                    },
                )
                await session.execute(stmt)

            for e in events:
                session.add(
                    Event(
                        timestamp=e.timestamp,
                        track_id=e.track_id,
                        event_type=e.event_type,
                        severity=e.severity,
                        message=e.message,
                    )
                )

            await session.commit()
    except Exception:
        log.exception("Could not write this tick to the database.")


# ------------------------------------------------------------ simulation loop
async def simulation_loop() -> None:
    log.info(
        "Simulator running — a tick every %.1f s around %s",
        settings.tick_seconds,
        settings.sensor_name,
    )
    while True:
        try:
            detections, departed = simulator.tick()
            events = track_manager.update(detections)
            events += track_manager.prune(departed)

            RECENT_EVENTS.extend(events)
            del RECENT_EVENTS[:-60]  # keep the last 60

            if events or detections:
                asyncio.create_task(persist(detections, events))

            frame = build_frame(events)
            await manager.broadcast(frame.model_dump_json())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Simulation tick failed; continuing.")

        await asyncio.sleep(settings.tick_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        log.info("Database ready.")
    except Exception:
        log.exception(
            "Database unavailable — the dashboard will run, but nothing is saved. "
            "Check DATABASE_URL and that PostgreSQL is up."
        )

    task = asyncio.create_task(simulation_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Counter-Drone Detection Dashboard",
    description=(
        "A simulation-only counter-UAS monitoring dashboard. All detections are "
        "generated by a software simulator — no radar or RF hardware is involved."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------- routes
@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "simulated": True,
        "clients": manager.count,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
    }


@app.get("/api/sensor", response_model=SensorInfo)
async def get_sensor() -> SensorInfo:
    return sensor_info()


@app.get("/api/stats", response_model=Stats)
async def get_stats() -> Stats:
    return Stats(
        **track_manager.counts(), uptime_seconds=round(time.time() - STARTED_AT, 1)
    )


@app.get("/api/tracks/active", response_model=list[TrackOut])
async def get_active_tracks() -> list[TrackOut]:
    return track_manager.snapshot()


@app.get("/api/tracks/{track_id}/history", response_model=list[DetectionOut])
async def get_track_history(
    track_id: str,
    limit: int = Query(200, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[DetectionOut]:
    result = await session.execute(
        select(Detection)
        .where(Detection.track_id == track_id)
        .order_by(desc(Detection.timestamp))
        .limit(limit)
    )
    return [DetectionOut.model_validate(row) for row in result.scalars().all()]


@app.get("/api/detections", response_model=list[DetectionOut])
async def get_detections(
    limit: int = Query(100, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[DetectionOut]:
    result = await session.execute(
        select(Detection).order_by(desc(Detection.timestamp)).limit(limit)
    )
    return [DetectionOut.model_validate(row) for row in result.scalars().all()]


@app.get("/api/events", response_model=list[EventOut])
async def get_events(
    limit: int = Query(50, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[EventOut]:
    result = await session.execute(
        select(Event).order_by(desc(Event.timestamp)).limit(limit)
    )
    return [EventOut.model_validate(row) for row in result.scalars().all()]


@app.get("/api/model")
async def get_model_info() -> dict:
    return classifier.info()


@app.post("/api/model/reload")
async def reload_model() -> dict:
    """Pick up a freshly trained model without restarting the server."""
    classifier.load()
    return classifier.info()


# ------------------------------------------------------------------ websocket
@app.websocket("/ws/live")
async def live_feed(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        # Send the current picture immediately so the map isn't empty while
        # the client waits for the next tick.
        opening = build_frame(RECENT_EVENTS[-15:])
        opening.type = "snapshot"
        await manager.send_to(websocket, opening.model_dump_json())

        while True:
            # We don't expect client messages; this keeps the socket open and
            # notices when the browser goes away.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
