"""Thread-safe outcome counters and uptime for ``GET /metrics`` (CONTRACTS.md 5)."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .events import OUTCOMES


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MetricsCounters:
    """Counters ``accepted``/``rejected``/``duplicate``/``failed`` plus uptime.

    Clocks are injectable for tests: ``monotonic`` feeds ``uptime_s`` and
    ``now`` stamps ``started_at``.
    """

    def __init__(
        self,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {outcome: 0 for outcome in OUTCOMES}
        self._monotonic = monotonic
        self._started_monotonic = monotonic()
        self._started_at = now()

    def increment(self, outcome: str) -> None:
        with self._lock:
            if outcome not in self._counts:
                raise ValueError(
                    f"outcome must be one of {OUTCOMES}, got {outcome!r}"
                )
            self._counts[outcome] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = dict(self._counts)
        started_at = self._started_at.isoformat(timespec="milliseconds")
        return {
            **counts,
            "started_at": started_at.replace("+00:00", "Z"),
            "uptime_s": self._monotonic() - self._started_monotonic,
        }
