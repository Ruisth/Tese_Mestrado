"""Thread-safe outcome counters and uptime for ``GET /metrics`` (CONTRACTS.md 5).

The four contract counters (``accepted``/``rejected``/``duplicate``/``failed``)
are incremented via :meth:`MetricsCounters.increment`. ``dropped`` is an
additive operational counter (messages discarded on inbound queue overflow,
before any processing) incremented via
:meth:`MetricsCounters.increment_dropped`; it is not an event outcome.

Confirmation marker (CONTRACTS 5, sprint P5): every snapshot also carries
``monotonic_ns`` (``time.monotonic_ns()`` read while the snapshot is taken,
i.e. at request handling) and ``wall_utc`` (the same instant on the wall
clock, RFC 3339 UTC). ``monotonic_ns`` is in the SAME clock domain as the
``received_monotonic_ns`` / ``ditto_ack_monotonic_ns`` stamps of
``events.jsonl`` (one process, one clock), so the harness can anchor the
end-of-run confirmation deadline in the controller's own time base instead
of deriving it from the events it is supposed to judge. It is NOT part of
any latency computation: latency stays ``(ditto_ack - received)/1e6``.
"""

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

    Clocks are injectable for tests: ``monotonic`` feeds ``uptime_s``,
    ``now`` stamps ``started_at`` (and ``wall_utc``) and ``monotonic_ns``
    feeds the confirmation marker ``monotonic_ns`` (see module docstring).
    """

    def __init__(
        self,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = _utc_now,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {outcome: 0 for outcome in OUTCOMES}
        self._dropped = 0
        self._monotonic = monotonic
        self._monotonic_ns = monotonic_ns
        self._started_monotonic = monotonic()
        self._started_at = now()
        self._now = now

    def increment(self, outcome: str) -> None:
        with self._lock:
            if outcome not in self._counts:
                raise ValueError(
                    f"outcome must be one of {OUTCOMES}, got {outcome!r}"
                )
            self._counts[outcome] += 1

    def increment_dropped(self) -> None:
        """Count one message dropped on inbound queue overflow (never processed)."""
        with self._lock:
            self._dropped += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = dict(self._counts)
            dropped = self._dropped
        started_at = self._started_at.isoformat(timespec="milliseconds")
        # Confirmation marker: both clocks read at snapshot time, i.e. while
        # the /metrics request is handled (see module docstring).
        marker_ns = int(self._monotonic_ns())
        marker_wall = self._now().isoformat(timespec="milliseconds")
        return {
            **counts,
            "dropped": dropped,
            "started_at": started_at.replace("+00:00", "Z"),
            "uptime_s": self._monotonic() - self._started_monotonic,
            "monotonic_ns": marker_ns,
            "wall_utc": marker_wall.replace("+00:00", "Z"),
        }
