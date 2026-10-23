"""Bounded, read-only readiness. Never contacts a model provider."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings
from app.db import check_runtime_database


class Worker(Protocol):
    @property
    def is_running(self) -> bool: ...


@dataclass
class Readiness:
    pool: object
    settings: Settings
    workers: tuple[Worker, ...]
    timeout_seconds: float = 2.0

    async def check(self) -> dict:
        checks = {"database": "fail", "workers": "fail"}
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await check_runtime_database(self.pool, self.settings)
            checks["database"] = "pass"
        except Exception:
            # Driver messages can contain credentials and server-controlled text.
            # The doctor provides operator diagnostics; probes expose only status.
            pass
        if self.workers and all(worker.is_running for worker in self.workers):
            checks["workers"] = "pass"
        return {
            "status": "ready"
            if all(v == "pass" for v in checks.values())
            else "not_ready",
            "checks": checks,
        }
