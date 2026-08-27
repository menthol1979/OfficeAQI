"""Background poller: hits the ESP32's /env endpoint on an interval,
writes successful readings to SQLite, and broadcasts them to any
connected WebSocket clients.

Fails clean, matching the kiosk's convention: if the ESP32 is
unreachable or reports ok=false, we skip the write entirely (no
nulls/zeros inserted) and keep serving the last-known values to
clients rather than pushing a "gap" or a fake reading.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import httpx
from pydantic import ValidationError

from . import config
from .db import Database
from .models import PollerStatus, SensorReading

log = logging.getLogger("env_dashboard.poller")

BroadcastFn = Callable[[SensorReading, str], Awaitable[None]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Poller:
    def __init__(self, db: Database, broadcast: Optional[BroadcastFn] = None):
        self.db = db
        self.broadcast = broadcast
        self.status = PollerStatus(esp32_url=config.ESP32_ENV_URL)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="env-poller")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        async with httpx.AsyncClient(timeout=config.POLL_TIMEOUT_SECONDS) as client:
            while not self._stop_event.is_set():
                await self._poll_once(client)
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=config.POLL_INTERVAL_SECONDS
                    )
                except asyncio.TimeoutError:
                    pass  # normal case: interval elapsed, loop again

    async def _poll_once(self, client: httpx.AsyncClient) -> None:
        self.status.last_attempt_ts = _utc_now_iso()
        try:
            resp = await client.get(config.ESP32_ENV_URL)
            resp.raise_for_status()
            reading = SensorReading.model_validate(resp.json())
        except (httpx.HTTPError, ValidationError, ValueError) as exc:
            self.status.consecutive_failures += 1
            self.status.last_error = f"{type(exc).__name__}: {exc}"
            log.warning("poll failed (%d consecutive): %s", self.status.consecutive_failures, exc)
            return

        if not reading.ok:
            self.status.consecutive_failures += 1
            self.status.last_error = "sensor reported ok=false"
            log.warning("sensor reported ok=false; skipping write")
            return

        # Success: reset failure streak, persist, and push to live clients.
        self.status.consecutive_failures = 0
        self.status.last_error = None
        self.status.last_success_ts = self.status.last_attempt_ts

        ts = await self.db.insert(reading)
        log.debug("stored reading id=%s", ts)

        if self.broadcast:
            await self.broadcast(reading, self.status.last_success_ts)
