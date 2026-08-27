"""Minimal WebSocket connection manager: tracks connected clients and
broadcasts live readings to all of them."""
from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

from .models import SensorReading

log = logging.getLogger("env_dashboard.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, reading: SensorReading, ts: str) -> None:
        payload = {"type": "reading", "ts": ts, **reading.model_dump()}
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)
