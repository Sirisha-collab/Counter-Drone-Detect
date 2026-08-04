# Counter-Drone Detection Dashboard

A real-time monitoring dashboard for a **simulated** passive counter-UAS sensor.

> **Scope.** Passive detection, simulation, monitoring, and learning only. The
> project observes and displays. It contains nothing that interferes with,
> jams, disables, or otherwise acts on any aircraft, and it does not connect to
> hardware that could.
---

## Features

**Simulated sensor feed**
- Four object profiles — quadcopter, fixed-wing UAS, bird flock, ground clutter
- A new detection report for every object, every tick (2 s by default)
- Each report carries a unique **Track ID**, range, bearing, altitude, speed,
  heading, signal strength, and timestamp

**Tracking**
- One track per Track ID, holding the current position plus a ring buffer of
  every previous position

**Classification**
- A random forest sorts each track into drone / bird / clutter from six
  features derived from its recent history
- Confidence shown alongside every verdict

**Dashboard**
- Live interactive map with labelled range rings, cardinal bearing marks, an
  alert ring, fading track trails, and heading stubs
- Click any track on the map or in the list to highlight it in both

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

**Why a WebSocket rather than polling.** 
Pushing one frame per tick means the browser never asks a question it doesn't need answered, and every
client sees the same picture at the same time.

---
###  Backend

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

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
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
