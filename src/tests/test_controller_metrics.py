"""Unit tests for egw_controller.metrics: the progress counters (CONTRACTS 5).

Pure ``MetricsCounters`` tests, no service and no HTTP layer: the three
additive fields ``received``/``in_progress``/``processing_errors``, the
residual rule behind ``processing_errors`` and its documented limitation,
the locking discipline of the updates and the restart rule (a new process
starts from zero with a new ``started_at``).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

import pytest

from egw_controller.events import OUTCOMES
from egw_controller.metrics import MetricsCounters
from test_controller_helpers import accounting_gap

PROGRESS_FIELDS = ("received", "in_progress", "processing_errors")


def test_progress_counters_start_at_zero_as_plain_integers() -> None:
    """CONTRACTS 5: the three fields are JSON integers, zero at process start
    (never a boolean, null or a floating-point number)."""
    snapshot = MetricsCounters().snapshot()
    for name in PROGRESS_FIELDS:
        assert name in snapshot
        assert type(snapshot[name]) is int
        assert snapshot[name] == 0
    # The harness rejects non-finite numbers anywhere in the body.
    json.dumps(snapshot, allow_nan=False)


def test_snapshot_key_order_is_a_convention_kept_stable() -> None:
    """NOT a contract assertion: a JSON object is unordered, CONTRACTS 5
    states no key order and every consumer reads the fields by name. This
    pins a convention of ``metrics.py`` only (the additive keys sit directly
    after ``dropped`` and no pre-existing key moved), so that a serialised
    body stays comparable line by line. A new additive field may change the
    list below without any contract change."""
    assert list(MetricsCounters().snapshot()) == [
        "accepted",
        "rejected",
        "duplicate",
        "failed",
        "dropped",
        "received",
        "in_progress",
        "processing_errors",
        "started_at",
        "uptime_s",
        "monotonic_ns",
        "wall_utc",
    ]


def test_snapshot_carries_exactly_the_documented_fields() -> None:
    """Closed key SET of a snapshot (``queue_depth`` is added by the HTTP
    handler): the three additive fields beside every pre-existing one."""
    assert set(MetricsCounters().snapshot()) == {
        "accepted",
        "rejected",
        "duplicate",
        "failed",
        "dropped",
        "received",
        "in_progress",
        "processing_errors",
        "started_at",
        "uptime_s",
        "monotonic_ns",
        "wall_utc",
    }


def test_processing_with_outcome_is_not_an_error() -> None:
    metrics = MetricsCounters()
    metrics.processing_started()
    assert metrics.snapshot()["in_progress"] == 1
    metrics.increment("accepted")
    metrics.processing_finished()
    snapshot = metrics.snapshot()
    assert snapshot["in_progress"] == 0
    assert snapshot["processing_errors"] == 0
    assert snapshot["accepted"] == 1


def test_processing_without_outcome_counts_processing_error() -> None:
    """Residual rule: processing that ends with no outcome counter having
    moved is a ``processing_errors``."""
    metrics = MetricsCounters()
    metrics.processing_started()
    metrics.processing_finished()
    snapshot = metrics.snapshot()
    assert snapshot["processing_errors"] == 1
    assert snapshot["in_progress"] == 0
    for outcome in OUTCOMES:
        assert snapshot[outcome] == 0


def test_outcome_counted_before_processing_does_not_mask_an_error() -> None:
    """The rule is "no outcome counter moved DURING this message", not "no
    outcome was ever counted"."""
    metrics = MetricsCounters()
    metrics.increment("rejected")  # nothing in progress
    metrics.processing_started()
    metrics.processing_finished()  # no outcome: one processing error
    metrics.processing_started()
    metrics.increment("accepted")
    metrics.processing_finished()  # outcome counted: not an error
    snapshot = metrics.snapshot()
    assert snapshot["processing_errors"] == 1
    assert snapshot["in_progress"] == 0
    assert snapshot["rejected"] == 1
    assert snapshot["accepted"] == 1


def test_foreign_outcome_increment_masks_a_processing_error() -> None:
    """Documented LIMITATION of the residual rule, pinned so that it stays
    explicit: an outcome counted from elsewhere while a message is being
    processed (another thread, or a direct ``process()`` call) is taken for
    the message's own outcome. The failed message is then reported under that
    outcome, no ``processing_errors`` is counted, and the identity still
    reads 0. The single consumer of ``ControllerService`` excludes it."""
    metrics = MetricsCounters()
    metrics.increment_received()
    metrics.processing_started()
    foreign = threading.Thread(target=metrics.increment, args=("accepted",))
    foreign.start()
    foreign.join()
    metrics.processing_finished()  # the taken message itself had no outcome
    snapshot = metrics.snapshot()
    assert snapshot["processing_errors"] == 0
    assert snapshot["accepted"] == 1
    assert snapshot["in_progress"] == 0
    assert accounting_gap(snapshot, queue_depth=0) == 0


def test_unmatched_processing_finished_is_refused_and_changes_nothing() -> None:
    """``in_progress`` is non-negative (CONTRACTS 5): ending a processing that
    never started is a programming error, not a ``processing_errors``."""
    metrics = MetricsCounters()
    with pytest.raises(RuntimeError):
        metrics.processing_finished()
    metrics.processing_started()
    metrics.increment("accepted")
    metrics.processing_finished()
    with pytest.raises(RuntimeError):
        metrics.processing_finished()
    snapshot = metrics.snapshot()
    assert snapshot["in_progress"] == 0
    assert snapshot["processing_errors"] == 0
    assert snapshot["accepted"] == 1


def test_in_progress_counts_messages_rather_than_flagging_activity() -> None:
    """``in_progress`` is a count: 0 or 1 only because ``ControllerService``
    has a single consumer."""
    metrics = MetricsCounters()
    metrics.processing_started()
    metrics.processing_started()
    assert metrics.snapshot()["in_progress"] == 2
    metrics.increment("accepted")
    metrics.processing_finished()
    assert metrics.snapshot()["in_progress"] == 1
    metrics.processing_finished()
    assert metrics.snapshot()["in_progress"] == 0


def test_progress_names_are_not_event_outcomes() -> None:
    """The progress counters never enter ``events.OUTCOMES``: they have their
    own methods and no event record carries them."""
    metrics = MetricsCounters()
    for name in PROGRESS_FIELDS:
        with pytest.raises(ValueError):
            metrics.increment(name)
    assert tuple(OUTCOMES) == ("accepted", "rejected", "duplicate", "failed")
    snapshot = metrics.snapshot()
    for name in PROGRESS_FIELDS:
        assert snapshot[name] == 0


_GUARDED_STATE = (
    "_counts",
    "_dropped",
    "_received",
    "_in_progress",
    "_processing_errors",
    "_outcomes_at_start",
)


class _SpyLock:
    """Stands in for ``MetricsCounters._lock``: counts the acquisitions and
    tells whether the lock is held."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.acquisitions = 0
        self.held = False

    def __enter__(self) -> "_SpyLock":
        self._lock.acquire()
        self.acquisitions += 1
        self.held = True
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.held = False
        self._lock.release()


_LOCKED_OPERATIONS = {
    "increment": lambda metrics: metrics.increment("accepted"),
    "increment_dropped": lambda metrics: metrics.increment_dropped(),
    "increment_received": lambda metrics: metrics.increment_received(),
    "processing_started": lambda metrics: metrics.processing_started(),
    "processing_finished_with_outcome": lambda metrics: (
        metrics.processing_finished()
    ),
    "processing_finished_without_outcome": lambda metrics: (
        metrics.processing_finished()
    ),
    "snapshot": lambda metrics: metrics.snapshot(),
}


@pytest.mark.parametrize("operation", sorted(_LOCKED_OPERATIONS))
def test_each_operation_touches_the_counters_in_one_lock_acquisition(
    operation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins the locking discipline the module docstring states, which no
    black-box test can see on an interpreter with a global lock: every
    operation is ONE acquisition of the lock (so ``processing_finished``
    lowers ``in_progress`` and raises ``processing_errors`` atomically, and
    ``snapshot`` copies every counter at one instant) and never reads or
    writes the counter state outside it. Implementation-level by necessity:
    it knows the private names of ``MetricsCounters``."""
    metrics = MetricsCounters()
    if operation.startswith("processing_finished"):
        metrics.processing_started()
        if operation.endswith("with_outcome"):
            metrics.increment("accepted")
    spy = _SpyLock()
    metrics._lock = spy  # type: ignore[assignment]
    unlocked: list[str] = []
    plain_get = MetricsCounters.__getattribute__
    plain_set = MetricsCounters.__setattr__

    def watched_get(self: MetricsCounters, name: str) -> object:
        if name in _GUARDED_STATE and not spy.held:
            unlocked.append(f"read {name}")
        return plain_get(self, name)

    def watched_set(self: MetricsCounters, name: str, value: object) -> None:
        if name in _GUARDED_STATE and not spy.held:
            unlocked.append(f"write {name}")
        plain_set(self, name, value)

    monkeypatch.setattr(MetricsCounters, "__getattribute__", watched_get)
    monkeypatch.setattr(MetricsCounters, "__setattr__", watched_set)
    _LOCKED_OPERATIONS[operation](metrics)
    monkeypatch.undo()

    assert spy.acquisitions == 1
    assert unlocked == []
    assert not spy.held
    expected_errors = 1 if operation.endswith("without_outcome") else 0
    assert metrics.snapshot()["processing_errors"] == expected_errors


def test_concurrent_updates_from_threads_lose_nothing() -> None:
    """Smoke test with real threads: the totals are exact and no reading
    shows a value out of range. It does NOT prove the lock (on an
    interpreter with a global lock the updates are not interrupted with or
    without it); the locking discipline is pinned by
    ``test_each_operation_touches_the_counters_in_one_lock_acquisition``.
    The lock never gives a foreign thread the identity (module docstring of
    ``metrics.py``)."""
    metrics = MetricsCounters()
    per_thread = 50_000
    barrier = threading.Barrier(3)

    def receive() -> None:
        barrier.wait()
        for _ in range(per_thread):
            metrics.increment_received()

    def start_and_finish() -> None:
        barrier.wait()
        for _ in range(per_thread):
            metrics.processing_started()
            metrics.processing_finished()

    threads = [
        threading.Thread(target=receive),
        threading.Thread(target=receive),
        threading.Thread(target=start_and_finish),
    ]
    for thread in threads:
        thread.start()
    last_received = 0
    while any(thread.is_alive() for thread in threads):
        snapshot = metrics.snapshot()
        assert snapshot["in_progress"] in (0, 1)
        assert snapshot["received"] >= last_received
        last_received = snapshot["received"]
    for thread in threads:
        thread.join()

    final = metrics.snapshot()
    assert final["received"] == 2 * per_thread
    assert final["processing_errors"] == per_thread
    assert final["in_progress"] == 0


def test_new_process_starts_from_zero_with_a_new_started_at() -> None:
    """Restart rule (CONTRACTS 5): all counters restart from zero with the
    process and ``started_at`` differs, so differences and sums are taken
    inside one process only."""
    old = MetricsCounters(
        now=lambda: datetime(2026, 9, 18, 9, 30, 0, tzinfo=timezone.utc)
    )
    old.increment_received()
    old.increment_received()
    old.increment_dropped()
    old.processing_started()
    old.increment("accepted")
    old.processing_finished()
    before = old.snapshot()
    assert before["received"] == 2

    new = MetricsCounters(
        now=lambda: datetime(2026, 9, 18, 9, 45, 0, tzinfo=timezone.utc)
    )
    after = new.snapshot()
    for name in (*OUTCOMES, "dropped", *PROGRESS_FIELDS):
        assert after[name] == 0
    assert after["started_at"] == "2026-09-18T09:45:00.000Z"
    assert after["started_at"] != before["started_at"]
    # How a reader detects and handles a restart between two readings is a
    # reader-side rule (CONTRACTS 5); no controller code implements it, so
    # nothing more is executable here.
    assert accounting_gap(after, queue_depth=0) == 0
