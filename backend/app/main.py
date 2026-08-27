"""FastAPI app: REST history endpoint, live WebSocket stream, and the
static frontend -- all served from this one process/container.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import Database
from .models import PollerStatus, StoredReading
from .poller import Poller
from .pruner import Pruner
from .ws import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("env_dashboard")

db = Database()
manager = ConnectionManager()
poller = Poller(db, broadcast=manager.broadcast)
pruner = Pruner(db)

# Range shorthands accepted by /history's `range` query param.
_RANGE_TO_TIMEDELTA = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting poller (esp32=%s, interval=%ss)", config.ESP32_ENV_URL, config.POLL_INTERVAL_SECONDS)
    poller.start()
    pruner.start()
    try:
        yield
    finally:
        log.info("shutting down poller/pruner")
        await poller.stop()
        await pruner.stop()


app = FastAPI(title="OfficeLab-Pi5 Env Dashboard", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    latest = await db.latest()
    return {
        "status": "ok",
        "poller": poller.status.model_dump(),
        "latest_reading_ts": latest.ts if latest else None,
    }


@app.get("/api/history", response_model=list[StoredReading])
async def history(
    range: str = "24h",
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    """Returns stored readings for a time window.

    Either pass `range` (one of 1h/6h/24h/7d/30d, default 24h) or an
    explicit `since` (and optional `until`) ISO-8601 timestamp.
    """
    if since:
        since_iso = since
    else:
        delta = _RANGE_TO_TIMEDELTA.get(range)
        if delta is None:
            raise HTTPException(
                status_code=400,
                detail=f"invalid range '{range}'; expected one of {sorted(_RANGE_TO_TIMEDELTA)} or use ?since=",
            )
        since_iso = (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    rows = await db.history(since_iso, until)
    return rows


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # This app doesn't need anything from the client, but we
            # still need to await something so a client disconnect is
            # detected promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)


# Static frontend last, so it doesn't shadow the /api and /ws routes above.
app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
