"""Configuration, loaded entirely from environment variables (with an
optional .env file for local dev). Nothing here should ever point at
anything on the home side of the two-site setup -- this app talks to the
office-LAN ESP32 sensor node directly and nothing else.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv is a convenience for local dev; it's fine if it's
    # missing in the container, since real deployments set env vars
    # directly (see docker-compose.yml).
    pass


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ESP32/BME680 sensor node's /env endpoint. Same static-ish IP the kiosk's
# CFG_ENV_SENSOR_URL config points at -- confirm this hasn't changed before
# relying on it in production.
ESP32_ENV_URL: str = _env_str("ESP32_ENV_URL", "http://192.168.64.20/env")

# Poll cadence. This app is about long-term trends, not instant reaction,
# so it deliberately polls slower than the kiosk's live display does.
POLL_INTERVAL_SECONDS: int = _env_int("POLL_INTERVAL_SECONDS", 15)

# HTTP timeout for a single poll request, in seconds. Kept short so one
# unreachable-sensor poll never backs up the next one.
POLL_TIMEOUT_SECONDS: float = float(_env_str("POLL_TIMEOUT_SECONDS", "5"))

# SQLite database file path.
DB_PATH: str = _env_str("DB_PATH", "./data/env.db")

# Rolling retention window. A daily prune job deletes readings older than
# this many days.
RETENTION_DAYS: int = _env_int("RETENTION_DAYS", 30)

# How often the retention prune job runs, in seconds. Default: once a day.
PRUNE_INTERVAL_SECONDS: int = _env_int("PRUNE_INTERVAL_SECONDS", 24 * 60 * 60)

# Uvicorn listen port.
# TODO before deploying to Proteus: check what's already listening there
# (the kiosk itself, Gatus, Glances, Bambu stats, etc.) so there's no
# collision -- this was not checked/confirmed as of this handoff.
PORT: int = _env_int("PORT", 8090)

# Host to bind to. 0.0.0.0 so it's reachable on the LAN like everything
# else on Proteus (no special access restriction was requested).
HOST: str = _env_str("HOST", "0.0.0.0")

# Directory containing the built frontend (served as static files).
FRONTEND_DIR: Path = Path(_env_str("FRONTEND_DIR", str(Path(__file__).resolve().parents[2] / "frontend")))

# Max number of raw rows a single /history request will return before the
# response starts being downsampled/bucketed. Keeps big ranges (e.g. 30d
# at a 15s cadence -> ~172k rows) from shipping an enormous JSON payload.
HISTORY_MAX_POINTS: int = _env_int("HISTORY_MAX_POINTS", 2000)
