"""Thread-safe counters and uptime for ``GET /metrics`` (CONTRACTS.md 5).

The four contract counters (``accepted``/``rejected``/``duplicate``/``failed``)
are incremented via :meth:`MetricsCounters.increment`. ``dropped`` is an
additive operational counter incremented via
:meth:`MetricsCounters.increment_dropped`; it is not an event outcome. Since
ADR 0011 it means "left for redelivery at the next session resumption": a
delivery discarded on inbound queue overflow (before any processing), one
purged from the queue when its connection ended, or one skipped when taken
because its connection had ended. None of them is acknowledged, so the
broker resends each on the persistent session.

Progress counters (CONTRACTS 5, additive, 2026-09-18), none of them an event
outcome:

- ``received`` (cumulative, :meth:`MetricsCounters.increment_received`):
  messages handed to the processing pipeline, counted once per
  ``ControllerService.submit`` call BEFORE the queue-capacity decision, so it
  includes every message later counted as ``dropped``;
- ``in_progress`` (gauge, 0 or 1 with the single consumer): messages removed
  from the inbound queue whose processing has not ended yet, Ditto retries
  and back-off included (:meth:`MetricsCounters.processing_started` /
  :meth:`MetricsCounters.processing_finished`);
- ``processing_errors`` (cumulative): messages removed from the inbound queue
  whose processing ended WITHOUT any outcome counter having been incremented.
  Since ADR 0011 (item 8) every other exception ends in a ``failed`` line, so
  these are exactly the deliveries that end with no line: the event log
  could not be written, the consumer was cancelled, or an exception was
  raised after the Ditto 2xx. It means "no outcome was recorded", not "not
  applied": the twin may already have been updated.

The three bridge fields of ``GET /metrics`` (``mqtt_subscribed``,
``mqtt_connection``, ``unacked``; ADR 0011, item 14) are NOT kept here: they
are updated on the MQTT network thread, which may touch nothing in this
class, so the bridge keeps them under its own lock and the HTTP handler
reads them beside the snapshot. ``unacked`` is not a term of the identity.

``processing_errors`` is a RESIDUAL, not an error handler:
``processing_finished`` raises it, in the same lock acquisition that lowers
``in_progress``, when the sum of the four outcome counters has not moved
since ``processing_started``. A message whose outcome was counted and whose
processing then raised is therefore an outcome, never counted twice. The
rule assumes the single consumer of ``ControllerService``: an ``increment``
made from elsewhere while a message is being processed (another thread, or
a direct ``ControllerService.process`` call while ``run`` holds a message)
would mask an error, and the identity below would still hold. A
``processing_finished`` with no message in progress is a programming error
and raises ``RuntimeError`` with every counter untouched, so ``in_progress``
is never negative.

Accounting identity, for one ``GET /metrics`` response of a running
controller, ``queue_depth`` being added by the HTTP handler::

    received == accepted + rejected + duplicate + failed
              + dropped + processing_errors
              + in_progress + queue_depth

The lock gives every thread lost-update-free counters and a mutually
consistent copy in :meth:`MetricsCounters.snapshot`. It does NOT give a
reader on another thread the identity: the outcome increment and the
``in_progress`` decrement are two acquisitions, and ``queue_depth`` lives
outside the lock. The identity is guaranteed for readers on the controller's
event loop only, because every term is written there in synchronous
stretches (no ``await`` between the two updates that move a message from one
term to another) and the ``/metrics`` handler, the only production caller of
``snapshot``, reads there too. Nothing may update these counters from the
MQTT network thread. The counters describe the internal state of one
process; they never replace the reconciliation, by identity, of messages
sent with outcomes recorded in ``events.jsonl`` (CONTRACTS 5).

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

    Also holds ``dropped`` and the progress counters ``received``,
    ``in_progress`` and ``processing_errors`` (see module docstring for the
    accounting identity, the residual rule behind ``processing_errors`` and
    the event-loop confinement the identity depends on). All counters start
    at zero with the process; ``started_at`` identifies the process.

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
        self._received = 0
        self._in_progress = 0
        self._processing_errors = 0
        # Sum of the outcome counters when the current message was taken.
        self._outcomes_at_start = 0
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

    def increment_received(self) -> None:
        """Count one message handed to the pipeline (before the capacity decision)."""
        with self._lock:
            self._received += 1

    def processing_started(self) -> None:
        """Mark one message as taken from the inbound queue by the consumer."""
        with self._lock:
            self._in_progress += 1
            self._outcomes_at_start = sum(self._counts.values())

    def processing_finished(self) -> None:
        """Mark the end of processing of the message taken last.

        One lock acquisition lowers ``in_progress`` and, when no outcome
        counter moved since :meth:`processing_started`, raises
        ``processing_errors`` (residual rule, see module docstring).

        Raises ``RuntimeError``, changing nothing, when no message is in
        progress; ``ControllerService.run`` cannot reach that case.
        """
        with self._lock:
            if self._in_progress <= 0:
                raise RuntimeError(
                    "processing_finished() without a matching processing_started()"
                )
            self._in_progress -= 1
            if sum(self._counts.values()) == self._outcomes_at_start:
                self._processing_errors += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = dict(self._counts)
            dropped = self._dropped
            received = self._received
            in_progress = self._in_progress
            processing_errors = self._processing_errors
        started_at = self._started_at.isoformat(timespec="milliseconds")
        # Confirmation marker: both clocks read at snapshot time, i.e. while
        # the /metrics request is handled (see module docstring).
        marker_ns = int(self._monotonic_ns())
        marker_wall = self._now().isoformat(timespec="milliseconds")
        return {
            **counts,
            "dropped": dropped,
            "received": received,
            "in_progress": in_progress,
            "processing_errors": processing_errors,
            "started_at": started_at.replace("+00:00", "Z"),
            "uptime_s": self._monotonic() - self._started_monotonic,
            "monotonic_ns": marker_ns,
            "wall_utc": marker_wall.replace("+00:00", "Z"),
        }
