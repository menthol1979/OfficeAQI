# OfficeLab-Pi5 · Env Dashboard

A standalone, flashy, graph-heavy historical dashboard for the office's
ESP32/BME680 environment sensor node — temperature, humidity, IAQ,
CO2-equivalent, pressure, and (in an advanced view) gas resistance and
breath VOC-equivalent, all with 30 days of history and live updates.

This is a **separate project** from the `OfficeLab-Pi5` kiosk repo (the
LVGL/C++ 1024×600 panel display). The kiosk shows *live* values on one
screen; this app is about *history and trends*, with a nicer visual
treatment. It talks to the same ESP32 sensor directly and does not
depend on the kiosk in any way.

## Hard constraints this app respects

- **No Home Assistant, ever.** Talks to the ESP32 directly.
- **No cross-site traffic.** Everything (ESP32 → backend → browser) stays
  on the office LAN. Nothing here reaches toward the home side of the
  two-site setup.
- **Flashy, not bare-bones.** Dark theme, animated/glowing gradient line
  charts, matching the kiosk's own accent colors (`#01A710` green,
  `#C14B00` orange, `#F87CFC` pink).

## Architecture

```
ESP32 (/env, polled every 15s) --> FastAPI poller --> SQLite (30d retention)
                                          |
                                          +--> WebSocket broadcast --> browser
                                          |
                     GET /api/history <---+---  (REST backfill on page load)
```

- **Backend:** Python, FastAPI + Uvicorn (`backend/app/`).
  - `poller.py` — background async poller. Fails clean: if the ESP32 is
    unreachable or reports `ok: false`, the poll is skipped entirely (no
    nulls/zeros written) and the app keeps serving last-known values.
  - `db.py` — SQLite storage (stdlib `sqlite3`, no ORM), with a daily
    prune job (`pruner.py`) enforcing `RETENTION_DAYS`.
  - `ws.py` — WebSocket connection manager; every successful poll is
    pushed to all connected browser clients immediately.
  - `main.py` — FastAPI app: `GET /api/health`, `GET /api/history`,
    `WS /ws`, and serves the static frontend.
- **Frontend:** `frontend/index.html`, single-page, vanilla JS + [Apache
  ECharts](https://echarts.apache.org/) (bundled locally in
  `frontend/static/echarts.min.js` — **no CDN dependency**, so it works
  even if Proteus has no general internet access). Backfills chart
  history from `/api/history` on load, then appends live points from the
  WebSocket. Range picker: 1h / 6h / 24h / 7d / 30d.
- **Deployment:** single Docker container (`backend/Dockerfile` +
  `docker-compose.yml`), designed to run on Proteus (the same Pi 5 that
  runs the kiosk), with a named volume for the SQLite file.

## Configuration

All config is via environment variables (see `.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `ESP32_ENV_URL` | `http://192.168.64.20/env` | **Confirm this IP is still current** before relying on it — same one the kiosk's `CFG_ENV_SENSOR_URL` uses. |
| `POLL_INTERVAL_SECONDS` | `15` | Trend app, not live display — slower than the kiosk's own poll rate. |
| `DB_PATH` | `./data/env.db` (Docker: `/data/env.db`) | SQLite file; point at the mounted volume in prod. |
| `RETENTION_DAYS` | `30` | Rolling window; prune job runs once a day. |
| `PORT` | `8090` | **TODO: verify this is actually free on Proteus** before deploying — check what's already listening there (kiosk, Gatus, Glances, Bambu stats, etc.). This was picked as a placeholder, not confirmed against the real host. |

## Running locally (dev)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..
export ESP32_ENV_URL=http://192.168.64.20/env   # or a mock, see below
python -m uvicorn backend.app.main:app --reload --port 8090
```

Then open `http://localhost:8090`.

If you don't have LAN access to the real sensor while developing, there's
a throwaway mock at `backend/tests/mock_esp32.py`:

```bash
python backend/tests/mock_esp32.py 9099 &
export ESP32_ENV_URL=http://127.0.0.1:9099/env
```

## Running with Docker

```bash
docker compose up -d --build
```

This builds the single container, mounts a named volume for the SQLite
DB, and exposes port `8090` (confirm/change first — see TODO above).

> **Note:** the Docker build/run path has **not** been verified in the
> environment this project was scaffolded in (no Docker daemon
> available there). The FastAPI app itself *was* tested end-to-end
> (poller → SQLite → REST → WebSocket, including a simulated sensor
> outage to confirm fail-clean behavior) against a mock sensor. Do a
> `docker compose up --build` smoke test on Proteus (or any dev machine
> with Docker) before treating this as deploy-ready.

## What's been verified vs. what hasn't

Verified locally (see commit history / this handoff):
- Poller writes readings to SQLite on a working sensor.
- `GET /api/health` and `GET /api/history` return correct data.
- WebSocket `/ws` broadcasts live readings to connected clients.
- Fail-clean behavior: killed the mock sensor mid-run — poller logged
  failures, `consecutive_failures` climbed, **no bad rows were written**,
  and the app kept serving the last-known reading without crashing.
- Static frontend and bundled `echarts.min.js` are served correctly.

Not yet verified (needs the real environment):
- Docker image build/run (no Docker daemon in the scaffolding sandbox).
- Behavior against the *real* ESP32 at `192.168.64.20` (only tested
  against a mock — confirm the IP/response shape still matches).
- Actual visual review of the charts in a browser (built and reasoned
  about, but not screenshotted/eyeballed).
- Port collision check on Proteus.

## Repo

Suggested name (matching the `OfficeLab-Pi5-ESP32-Sensor` convention):
`menthol1979/OfficeLab-Pi5-Env-Dashboard`. This project was scaffolded
with a local git repo (`git init`) but has **not** been pushed anywhere —
create the GitHub repo and push when ready.
