"""SQLite storage layer.

Uses the stdlib sqlite3 module in a small async wrapper (run in a thread
via asyncio.to_thread) rather than pulling in a full ORM/async-DB
dependency -- this app's write pattern is trivial (one insert every
poll interval) and doesn't need more than that.
"""
from __future__ import annotations

import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

from . import config
from .models import SensorReading, StoredReading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    iaq REAL,
    iaq_accuracy INTEGER,
    co2_equivalent_ppm REAL,
    breath_voc_equivalent_ppm REAL,
    temperature_c REAL,
    humidity_pct REAL,
    pressure_hpa REAL,
    gas_resistance_ohm REAL,
    stabilization_status INTEGER,
    run_in_status INTEGER,
    age_ms INTEGER,
    uptime_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings (ts);
"""

_FIELDS = [
    "iaq",
    "iaq_accuracy",
    "co2_equivalent_ppm",
    "breath_voc_equivalent_ppm",
    "temperature_c",
    "humidity_pct",
    "pressure_hpa",
    "gas_resistance_ohm",
    "stabilization_status",
    "run_in_status",
    "age_ms",
    "uptime_ms",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Database:
    def __init__(self, path: str = config.DB_PATH):
        self.path = path
        Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # -- sync implementations, wrapped by async methods below --

    def _insert_sync(self, reading: SensorReading) -> int:
        ts = _utc_now_iso()
        values = [getattr(reading, f) for f in _FIELDS]
        with self._connect() as conn:
            cur = conn.execute(
                f"INSERT INTO readings (ts, {', '.join(_FIELDS)}) "
                f"VALUES (?, {', '.join(['?'] * len(_FIELDS))})",
                [ts, *values],
            )
            return cur.lastrowid

    def _history_sync(
        self, since_iso: str, until_iso: Optional[str], max_points: int
    ) -> list[StoredReading]:
        with self._connect() as conn:
            if until_iso:
                cur = conn.execute(
                    "SELECT * FROM readings WHERE ts >= ? AND ts <= ? ORDER BY ts ASC",
                    (since_iso, until_iso),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM readings WHERE ts >= ? ORDER BY ts ASC",
                    (since_iso,),
                )
            rows = cur.fetchall()

        if len(rows) > max_points:
            # Even downsampling: keep every Nth row so the chart still
            # spans the full requested range instead of getting cut off.
            step = len(rows) / max_points
            rows = [rows[int(i * step)] for i in range(max_points)]

        return [StoredReading(ok=True, **dict(row)) for row in rows]

    def _prune_sync(self, retention_days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3] + "Z"
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM readings WHERE ts < ?", (cutoff,))
            return cur.rowcount

    def _latest_sync(self) -> Optional[StoredReading]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 1")
            row = cur.fetchone()
        return StoredReading(ok=True, **dict(row)) if row else None

    # -- async-facing API --

    async def insert(self, reading: SensorReading) -> int:
        return await asyncio.to_thread(self._insert_sync, reading)

    async def history(
        self, since_iso: str, until_iso: Optional[str] = None, max_points: int = config.HISTORY_MAX_POINTS
    ) -> list[StoredReading]:
        return await asyncio.to_thread(self._history_sync, since_iso, until_iso, max_points)

    async def prune(self, retention_days: int = config.RETENTION_DAYS) -> int:
        return await asyncio.to_thread(self._prune_sync, retention_days)

    async def latest(self) -> Optional[StoredReading]:
        return await asyncio.to_thread(self._latest_sync)
