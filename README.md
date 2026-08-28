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
| `PORT` | `8090` | Uvicorn's listen port *inside* the container. Left at 8090 — the host-side port is what actually needed to change (see below). |

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
DB, and exposes the app on host port **8095** (`ports: "8095:8090"` in
`docker-compose.yml`). 8090 and 8091 were already taken on Proteus by
other services (confirmed via `ss -tlnp`), so 8095 was picked instead —
the container still listens on 8090 *internally*, only the host-side
mapping changed. Adjust the left side of that mapping if 8095 ever
collides with something else.

## Status: deployed and running

This has moved past scaffolding — it's live on Proteus, polling the
real ESP32 successfully:

- Running in Docker on Proteus at `http://<proteus-ip>:8095`, built via
  `docker compose up -d --build`.
- Poller confirmed hitting the real ESP32 at `192.168.64.20/env`,
  `GET /api/health` showing `consecutive_failures: 0` against live
  hardware (not just the mock sensor used during initial development).
- Fail-clean behavior verified: killing the sensor mid-run causes the
  poller to log failures and climb `consecutive_failures` without
  writing bad rows or crashing, and it recovers cleanly once the sensor
  comes back.
- Frontend visually reviewed (screenshotted, not just reasoned about):
  temperature/humidity enlarged on top, IAQ/CO2/pressure on the bottom
  row, plus a status panel below the header showing live connection
  state, ESP32 host, uptime, calibration status, and a ticking
  "Updated: X secs ago".

Still open:
- Import this stack into Portainer (Stacks → Add stack → Repository →
  this repo's URL) so it's managed alongside whatever else runs there.

## Repo

Pushed to [`menthol1979/OfficeAQI`](https://github.com/menthol1979/OfficeAQI)
(this project is the repo root, not a subfolder — the suggested
`OfficeLab-Pi5-Env-Dashboard` naming ended up as the repo's local
directory name on each machine, not the GitHub repo name itself).
