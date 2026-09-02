"""ModelCallGate — the single concurrency cap for provider (model) calls.

Built C7 / audit R8 (2026-08-18). Before this there was NO concurrency limiting
anywhere: every provider call is a synchronous SDK call offloaded to the default
asyncio thread pool (min(32, cpu+4)), and a streaming NPC holds a thread for its
whole stream, so N concurrent NPCs could exhaust that pool, the DB connection
pool, and the provider's rate limit at once. This gate is the one ceiling.

Two primitives, one cap:
  - an asyncio.Semaphore(cap) bounds the LOGICAL in-flight count exactly and
    makes each call's queue wait measurable at the seam (instrument-at-the-seam);
  - a bounded ThreadPoolExecutor(max_workers=cap) so the default pool never
    becomes the binding constraint when the cap is raised, and so the local NLP
    passes + startup warm-up keep the default pool to themselves.

Process-level: one gate per process, carried on the Providers bundle (the
existing injection vehicle) so every seam and worker reaches it as
`providers.gate`. It caps MODEL calls only — the local spaCy/fastcoref NLP
passes stay on the default pool (CPU-bound, already bounded there, and not what
`TWICETOLD_MAX_CONCURRENT_MODEL_CALLS` names).
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

_T = TypeVar("_T")


def _ms(seconds: float) -> float:
    """Milliseconds, 2 dp — the seam convention (ingest/dialogue/reconstruction)."""
    return round(seconds * 1000, 2)


class ModelCallGate:
    """Bounds concurrent provider calls to `max_concurrent`. One per process."""

    def __init__(self, max_concurrent: int) -> None:
        if max_concurrent < 1:
            raise ValueError(f"max_concurrent must be >= 1, got {max_concurrent}")
        self._max = max_concurrent
        self._sem = asyncio.Semaphore(max_concurrent)
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent, thread_name_prefix="modelcall"
        )

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def executor(self) -> ThreadPoolExecutor:
        """The bounded executor. The streaming prose leg submits its whole-stream
        producer here directly — it holds one slot for the stream's lifetime."""
        return self._executor

    async def acquire(self) -> float:
        """Take a slot, returning the wait (ms) spent queued. The caller MUST
        release() in a finally. Used by the streaming prose leg, which holds the
        slot across the whole stream and surfaces the wait as gate_wait_ms."""
        t0 = time.perf_counter()
        await self._sem.acquire()
        return _ms(time.perf_counter() - t0)

    def release(self) -> None:
        self._sem.release()

    async def run(self, fn: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
        """Run a blocking provider call under the cap on the bounded executor —
        the near-drop-in for `asyncio.to_thread(fn, ...)`. Exceptions from `fn`
        propagate; the slot is always released."""
        await self._sem.acquire()
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._executor, lambda: fn(*args, **kwargs)
            )
        finally:
            self._sem.release()

    def shutdown(self) -> None:
        """Teardown: stop accepting work and drop queued futures. In-flight sync
        calls finish in the background (a running thread can't be cancelled).
        Called from the two construction sites' teardown, before the pool
        closes."""
        self._executor.shutdown(wait=False, cancel_futures=True)
