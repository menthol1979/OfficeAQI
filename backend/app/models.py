"""Pydantic schemas for the ESP32 payload and API responses."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SensorReading(BaseModel):
    """Shape of the ESP32's /env JSON payload.

    All sensor fields are optional because a real-world reading can be
    missing individual fields (e.g. mid-calibration); only `ok` is
    required to decide whether to trust/store the payload at all.
    """

    ok: bool
    iaq: Optional[float] = None
    iaq_accuracy: Optional[int] = None
    co2_equivalent_ppm: Optional[float] = None
    breath_voc_equivalent_ppm: Optional[float] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None
    gas_resistance_ohm: Optional[float] = None
    stabilization_status: Optional[int] = None
    run_in_status: Optional[int] = None
    age_ms: Optional[int] = None
    uptime_ms: Optional[int] = None


class StoredReading(SensorReading):
    """A reading as stored/returned by this app, with our own timestamp
    and row id attached."""

    id: int
    ts: str  # ISO-8601 UTC, e.g. "2026-08-27T12:34:56.789Z"


class PollerStatus(BaseModel):
    """Live status of the background poller, used by /health."""

    last_success_ts: Optional[str] = None
    last_attempt_ts: Optional[str] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    esp32_url: str
