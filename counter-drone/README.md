# Counter-Drone Detection Dashboard

A real-time monitoring dashboard for a **simulated** passive counter-UAS sensor.
Detections are generated entirely in software — there is no radar, no RF
receiver, and no hardware interface anywhere in this project. It exists to
practise the parts that are hard to learn without a sensor: streaming telemetry,
multi-object tracking, classification, and an operator display that stays
readable while it changes.

> **Scope.** Passive detection, simulation, monitoring, and learning only. The
> project observes and displays. It contains nothing that interferes with,
> jams, disables, or otherwise acts on any aircraft, and it does not connect to
> hardware that could.

---

## Table of contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Architecture](#architecture)
- [How the simulation works](#how-the-simulation-works)
- [The machine learning piece](#the-machine-learning-piece)
- [Setup](#setup)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Project layout](#project-layout)
- [Things to try next](#things-to-try-next)

---

## Features

**Simulated sensor feed**
- Four object profiles — quadcopter, fixed-wing UAS, bird flock, ground clutter
- A new detection report for every object, every tick (2 s by default)
- Each report carries a unique **Track ID**, range, bearing, altitude, speed,
  heading, signal strength, and timestamp
- Believable physics: speed and altitude wobble around a cruise value, signal
  strength follows log-distance path loss, and purposeful contacts fly inbound,
  overfly the site, and depart

**Tracking**
- One track per Track ID, holding the current position plus a ring buffer of
  every previous position
- Tracks open on first detection, update on every report, and retire when the
  object leaves coverage or stops reporting
- Running per-track statistics: detection count, closest approach, top speed

**Classification**
- A random forest sorts each track into drone / bird / clutter from six
  features derived from its recent history
- Confidence shown alongside every verdict
- Falls back to a readable rule if no model file is present, so the dashboard
  never sits blank

**Dashboard**
- Live interactive map with labelled range rings, cardinal bearing marks, an
  alert ring, fading track trails, and heading stubs
- Real-time detection counter plus active tracks, drone count, alert count,
  lifecycle totals, and uptime
- Active track list sorted nearest-first, each row carrying a miniature
  plan-position dial
- Event log for track opened / classified / alert-ring entry / track lost
- Click any track on the map or in the list to highlight it in both
- Responsive down to a phone; keyboard focus visible throughout; honours
  `prefers-reduced-motion`

**Plumbing**
- WebSocket push — one frame per tick, no polling
- Automatic reconnect with exponential backoff
- Every detection, track summary, and event written to PostgreSQL
- The dashboard keeps running if the database is down; it just stops recording

---

## Screenshots

Drop your captures into `docs/screenshots/` using these filenames.

| | |
|---|---|
| **Dashboard** | ![Full dashboard](docs/screenshots/dashboard.png) |
| **Map panel** | ![Map with range rings and tracks](docs/screenshots/map.png) |
| **Active tracks** | ![Active track list](docs/screenshots/tracks.png) |
| **Event log** | ![Event log](docs/screenshots/events.png) |
| **Model training** | ![Training output](docs/screenshots/training.png) |

---

## Architecture

```
┌──────────────────────────── BACKEND (FastAPI) ────────────────────────────┐
│                                                                           │
│   simulator.py          tracker.py              ml/classifier.py          │
│   ┌───────────┐         ┌────────────┐          ┌──────────────┐          │
│   │ 4 object  │  detec- │ Track ID → │ recent   │ RandomForest │          │
│   │ profiles  │ ─tions─▶│ current +  │ ─history▶│ drone / bird │          │
│   │ move each │         │ previous   │◀──label──│ / clutter    │          │
│   │ tick      │         │ positions  │          └──────────────┘          │
│   └───────────┘         └─────┬──────┘                                    │
│                               │                                           │
│                    ┌──────────┴──────────┐                                │
│                    ▼                     ▼                                │
│            ws_manager.py           models.py                              │
│            broadcast frame         SQLAlchemy ──▶ ┌────────────┐          │
│                    │                              │ PostgreSQL │          │
│                    │                              │ detections │          │
│                    │                              │ tracks     │          │
│                    │                              │ events     │          │
│                    │                              └────────────┘          │
└────────────────────┼──────────────────────────────────────────────────────┘
                     │  WebSocket  ws://…/ws/live      REST  /api/*
                     ▼
┌──────────────────────── FRONTEND (React + TypeScript) ────────────────────┐
│                                                                           │
│   useLiveFeed()  ──frame──▶  App.tsx                                      │
│   reconnecting               │                                            │
│   socket                     ├─▶ StatStrip    detection counter, totals   │
│                              ├─▶ MapPanel     Leaflet, rings, trails      │
│                              ├─▶ TrackList    active tracks + dials       │
│                              └─▶ EventLog     lifecycle events            │
└───────────────────────────────────────────────────────────────────────────┘
```

**Why a WebSocket rather than polling.** The backend already knows the exact
moment the picture changes — it's the thing changing it. Pushing one frame per
tick means the browser never asks a question it doesn't need answered, and every
client sees the same picture at the same time.

**Why the tracker lives in memory.** PostgreSQL holds the permanent record;
the tracker holds what's on screen. Keeping them separate means a slow or
missing database never stalls the display loop.

---

## How the simulation works

Every tick, `DroneSimulator.tick()` does four things per object:

1. **Turn.** Heading takes a random walk whose spread depends on the profile —
   a fixed-wing UAS throws away 4° per report, a bird flock 34°, ground clutter
   50°. This turn rate ends up being the single most useful classification
   feature.
2. **Steer.** Drones pull back toward the sensor site each tick, so they
   actually arrive. Birds barely do. Clutter doesn't at all. Once a contact gets
   within 300 m it flips outbound and leaves — which is what eventually retires
   the track.
3. **Settle.** Speed and altitude are pulled back toward the object's cruise
   value before jitter is added. Without this everything random-walks until all
   four profiles look identical.
4. **Report.** Signal strength comes from a log-distance path loss model
   referenced to 1 km, so a contact reads roughly 15 dB louder at the inner ring
   than the outer edge, with per-profile noise on top.

The result is a full lifecycle you can watch: a contact is acquired near the
edge, classified after a few reports, crosses the alert ring, overflies the
site, and drops off the far side.

The tracker never sees which profile produced a detection. The ground truth is
stored in the `tracks` table only so you can grade the model while learning.

---

## The machine learning piece

**Six features**, computed from each track's recent history:

| Feature | Why it separates the classes |
|---|---|
| `mean_speed_mps` | Drones cruise faster than birds, slower than aircraft |
| `speed_std` | Birds and clutter wobble; a drone holds a steady speed |
| `mean_altitude_m` | Small drones fly low, but not ground-level |
| `heading_std_deg` | Birds turn constantly; a drone flies straight legs |
| `mean_rssi_dbm` | A powered RF emitter is louder than a passive return |
| `rssi_std` | Clutter flickers; a real emitter is stable |

**Training.** There's no dataset to download. `train.py` samples each class from
a distribution matching how that object behaves, then lets a random forest find
the boundaries:

```bash
cd backend
python -m app.ml.train
```

You'll get a classification report, a confusion matrix, and feature
importances. On the shipped configuration it scores about **98%** on held-out
data, with the residual confusion between bird and clutter — which is honest,
since those two genuinely overlap.

```
Which features mattered most:
  heading_std_deg      0.277
  rssi_std             0.232
  mean_rssi_dbm        0.184
  mean_speed_mps       0.112
  mean_altitude_m      0.099
  speed_std            0.096
```

A model ships in `backend/models/classifier.joblib` so the dashboard works on
first run. Retrain it any time — `POST /api/model/reload` picks up the new file
without restarting the server.

**To use real data instead,** replace `synthesize_dataset()` with a loader for
your own labelled tracks. Nothing else in the project has to change, as long as
the feature order in `ml/features.py` stays the same on both sides.

---

## Setup

**You'll need:** Python 3.11+, Node 20+, and PostgreSQL 14+ (or Docker).

The stack is on current majors: **FastAPI + Pydantic v2 + SQLAlchemy 2.0** on the
backend, **React 19 + Vite 7 + Tailwind CSS v4** on the frontend. Tailwind v4 is
configured in CSS rather than JavaScript, so there is no `tailwind.config.js`
and no `postcss.config.js` — the design tokens live in `src/index.css` under
`@theme`.

### 1. Database

```bash
docker compose up -d
```

That starts PostgreSQL on port 5432 with user/password/database all set to
`cuas`. Already running your own Postgres? Create the database and point
`DATABASE_URL` at it instead — the tables are created automatically on first
boot.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # edit if your database differs
python -m app.ml.train             # optional — a model is already included

uvicorn app.main:app --reload --port 8000
```

Check it's alive at <http://localhost:8000/api/health>, and browse the
auto-generated API docs at <http://localhost:8000/docs>.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open <http://localhost:5173>. Within a few seconds the map fills with contacts.

### Troubleshooting

| Symptom | Cause |
|---|---|
| Header says *Feed lost — retrying* | Backend isn't up on port 8000. Start it; the frontend reconnects on its own. |
| Header says *Model: fallback rule* | No `classifier.joblib` found. Run `python -m app.ml.train`, then `curl -X POST localhost:8000/api/model/reload`. |
| Backend logs *Database unavailable* | Postgres isn't reachable. The dashboard still runs, but nothing is recorded. |
| `ModuleNotFoundError: asyncpg` | `DATABASE_URL` must use the async driver: `postgresql+asyncpg://…` |
| `pip install` fails on `asyncpg` | Needs a C toolchain on some systems. On Debian/Ubuntu: `sudo apt install build-essential python3-dev` |
| Tailwind classes have no effect | v4 needs the Vite plugin. Check `@tailwindcss/vite` is in `devDependencies` and listed in `vite.config.ts`. |
| Map tiles are blank | The tile layer needs internet access. |

---

## Configuration

Everything below is an environment variable in `backend/.env`.

| Variable | Default | What it changes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://cuas:cuas@localhost:5432/cuas` | Where records go |
| `SENSOR_NAME` | `SENTINEL-1` | Shown in the header |
| `SENSOR_LAT` / `SENSOR_LON` | `37.7749` / `-122.4194` | Where the map centres |
| `DETECTION_RANGE_M` | `3000` | Coverage radius; the outer ring |
| `ALERT_RADIUS_M` | `900` | The inner ring that raises alerts |
| `TICK_SECONDS` | `2.0` | How often detections are produced |
| `MIN_ACTIVE_OBJECTS` / `MAX_ACTIVE_OBJECTS` | `3` / `9` | How busy the airspace gets |
| `SPAWN_CHANCE` | `0.35` | Chance per tick of adding a contact |
| `HISTORY_LENGTH` | `40` | How long the map trails are |
| `TRACK_TIMEOUT_SECONDS` | `12` | Silence before a track is retired |
| `MIN_POINTS_FOR_CLASSIFICATION` | `4` | Reports needed before the model is asked |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Who may call the API |

Frontend variables live in `frontend/.env`: `VITE_API_URL` and `VITE_WS_URL`.

---

## API reference

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/health` | Liveness, connected client count, uptime |
| `GET` | `/api/sensor` | Sensor site, coverage, alert radius, tick rate |
| `GET` | `/api/stats` | Detection counter and track totals |
| `GET` | `/api/tracks/active` | Every held track with its position history |
| `GET` | `/api/tracks/{track_id}/history` | Stored detections for one Track ID |
| `GET` | `/api/detections?limit=` | Most recent detections |
| `GET` | `/api/events?limit=` | Most recent events |
| `GET` | `/api/model` | Which classifier is loaded, and its features |
| `POST` | `/api/model/reload` | Reload the model file from disk |
| `WS` | `/ws/live` | One frame per tick |

A frame looks like this:

```jsonc
{
  "type": "frame",
  "timestamp": "2026-08-02T14:22:31.004Z",
  "sensor":  { "name": "SENTINEL-1", "lat": 37.7749, "range_m": 3000, ... },
  "stats":   { "total_detections": 3501, "active_tracks": 9, "drone_tracks": 2, ... },
  "tracks":  [ { "track_id": "TRK-4A1F", "classification": "drone",
                 "confidence": 0.98, "distance_m": 1204.3, "bearing_deg": 47.2,
                 "history": [ { "lat": …, "lon": …, "timestamp": … } ] } ],
  "events":  [ { "event_type": "alert_zone_entry", "severity": "alert", ... } ],
  "model_ready": true
}
```

The first message after connecting has `"type": "snapshot"` and carries the
current picture, so a browser that joins mid-run doesn't start empty.

---

## Project layout

```
counter-drone-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app, REST routes, WebSocket, sim loop
│   │   ├── simulator.py      The fake sensor — object profiles and motion
│   │   ├── tracker.py        Track IDs, current + previous positions, alerts
│   │   ├── models.py         detections / tracks / events tables
│   │   ├── schemas.py        The JSON contract with the frontend
│   │   ├── database.py       Async engine and session
│   │   ├── geo.py            Bearing/range ↔ lat/lon
│   │   ├── config.py         Every tunable, from the environment
│   │   ├── ws_manager.py     Broadcast to connected browsers
│   │   └── ml/
│   │       ├── features.py   The six features, defined once
│   │       ├── train.py      Build a dataset, fit, evaluate, save
│   │       └── classifier.py Load, predict, fall back
│   ├── models/               Trained model lands here
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.tsx           Layout and shared selection state
│       ├── types.ts          Mirrors schemas.py
│       ├── hooks/useLiveFeed.ts    Socket, reconnect, event buffer
│       ├── lib/              Formatting and geodesy helpers
│       ├── index.css         Tailwind v4 @theme tokens + global styles
│       └── components/       Header, StatStrip, MapPanel, TrackList,
│                             EventLog, BearingDial
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts        React + Tailwind v4 plugins
│   └── .env.example
├── docs/screenshots/
└── docker-compose.yml        PostgreSQL
```

---

## Things to try next

Roughly in order of difficulty:

1. **Break the classifier on purpose.** Set `MIN_POINTS_FOR_CLASSIFICATION=1`
   and watch verdicts flip while a track is still new. It's the clearest
   demonstration of why the feature window matters.
2. **Add a fifth object profile** in `simulator.py` — a hovering drone, say —
   and see whether the existing model handles it or needs retraining.
3. **Swap the model.** `train.py` fits a `RandomForestClassifier`; try gradient
   boosting or a small MLP and compare the confusion matrices.
4. **Add track prediction.** You have every previous position — extrapolate the
   next one and draw it as a ghost marker.
5. **Replay from the database.** Every detection is stored with a timestamp,
   so a scrubber that replays the last hour is mostly a query and a slider.
6. **Handle detection gaps.** Real sensors drop reports. Add a chance of a
   missed detection and give the tracker a coast-and-reacquire behaviour.

---

## A note on scope

This is a learning and monitoring project. It simulates detection so the
interesting engineering problems — streaming, tracking, classification,
operator display — can be worked on without hardware. Real counter-UAS
deployment is regulated in most jurisdictions, and anything that interferes
with an aircraft is a different category of activity entirely and deliberately
out of scope here.

## License

MIT. Do something interesting with it.
