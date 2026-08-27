"""Daily retention prune job: deletes readings older than RETENTION_DAYS."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from . import config
from .db import Database

log = logging.getLogger("env_dashboard.pruner")


class Pruner:
    def __init__(self, db: Database):
        self.db = db
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="env-pruner")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                deleted = await self.db.prune(config.RETENTION_DAYS)
                if deleted:
                    log.info("pruned %d readings older than %d days", deleted, config.RETENTION_DAYS)
            except Exception:
                log.exception("prune job failed")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=config.PRUNE_INTERVAL_SECONDS
                )
            except asyncio.TimeoutError:
                pass
