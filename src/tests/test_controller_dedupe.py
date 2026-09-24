"""Tests for egw_controller.dedupe (CONTRACTS.md section 4 idempotency, v1.1).

Reject repeated ``message_id`` (across runs) and non-increasing ``seq``
**within the same** ``run_id``; a differing ``run_id`` resets the seq floor.
State (including ``last_run_id``) is seeded from the twin's ``ingestion``
feature after a controller restart.
"""

from __future__ import annotations

import pytest

from egw_controller.dedupe import DedupeCache, UnknownDeviceError
from test_controller_helpers import DEVICE_UUIDS, make_message_id, make_raw_twin

DEVICE = DEVICE_UUIDS["smartwatch"]
RUN = "dedupe-run"
WARMUP_RUN = f"{RUN}.warmup"


def mid(seq: int, run_id: str = RUN) -> str:
    return make_message_id(run_id, DEVICE, seq)


def test_unknown_device_before_seeding() -> None:
    cache = DedupeCache()
    assert not cache.known_device(DEVICE)
    with pytest.raises(UnknownDeviceError):
        cache.check(DEVICE, mid(0), 0, RUN)
    with pytest.raises(UnknownDeviceError):
        cache.record(DEVICE, mid(0), 0, RUN)
    with pytest.raises(UnknownDeviceError):
        cache.accepted_count(DEVICE)


def test_seed_with_none_twin_starts_empty() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    assert cache.known_device(DEVICE)
    assert cache.last_seq(DEVICE) is None
    assert cache.last_run_id(DEVICE) is None
    assert cache.accepted_count(DEVICE) == 0
    assert cache.check(DEVICE, mid(0), 0, RUN) is None  # seq 0 fresh on a new twin


def test_fresh_message_then_replay_is_duplicate() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    assert cache.check(DEVICE, mid(0), 0, RUN) is None
    cache.record(DEVICE, mid(0), 0, RUN)
    reason = cache.check(DEVICE, mid(0), 0, RUN)
    assert reason is not None and "message_id" in reason


def test_seq_regression_within_same_run_is_duplicate() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    cache.record(DEVICE, mid(5), 5, RUN)
    # equal seq, same run
    assert cache.check(DEVICE, mid(105), 5, RUN) is not None
    # lower seq, same run
    assert cache.check(DEVICE, mid(103), 3, RUN) is not None
    # strictly higher seq is fresh
    assert cache.check(DEVICE, mid(6), 6, RUN) is None


def test_record_advances_state() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    cache.record(DEVICE, mid(0), 0, RUN)
    cache.record(DEVICE, mid(1), 1, RUN)
    assert cache.last_seq(DEVICE) == 1
    assert cache.last_run_id(DEVICE) == RUN
    assert cache.accepted_count(DEVICE) == 2


def test_record_never_decreases_last_seq_within_run() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    cache.record(DEVICE, mid(5), 5, RUN)
    cache.record(DEVICE, mid(2), 2, RUN)  # defensive: out-of-order record
    assert cache.last_seq(DEVICE) == 5


# ---------------------------------------------------------------------------
# Run scoping (CONTRACTS 4, v1.1)
# ---------------------------------------------------------------------------


def test_warmup_then_measured_run_restarts_seq_at_zero() -> None:
    """Same device: run 'X.warmup' seqs 0..N, then run 'X' seq 0 is accepted."""
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    for seq in range(5):
        assert cache.check(DEVICE, mid(seq, WARMUP_RUN), seq, WARMUP_RUN) is None
        cache.record(DEVICE, mid(seq, WARMUP_RUN), seq, WARMUP_RUN)
    assert cache.last_seq(DEVICE) == 4
    # Measured run restarts at seq 0: NOT a duplicate (run_id differs).
    assert cache.check(DEVICE, mid(0), 0, RUN) is None
    cache.record(DEVICE, mid(0), 0, RUN)
    assert cache.last_run_id(DEVICE) == RUN
    assert cache.last_seq(DEVICE) == 0  # floor reset to the new run's seq
    # Monotonicity now enforced within the measured run.
    assert cache.check(DEVICE, mid(1), 1, RUN) is None
    cache.record(DEVICE, mid(1), 1, RUN)
    assert cache.check(DEVICE, mid(101), 1, RUN) is not None
    assert cache.check(DEVICE, mid(100), 0, RUN) is not None
    assert cache.check(DEVICE, mid(2), 2, RUN) is None


def test_replayed_message_id_still_duplicate_across_run_switch() -> None:
    """The message_id LRU is run-agnostic: an old run's message stays caught."""
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    warmup_mid = mid(3, WARMUP_RUN)
    cache.record(DEVICE, warmup_mid, 3, WARMUP_RUN)
    cache.record(DEVICE, mid(0), 0, RUN)  # switch to the measured run
    # QoS 1 redelivery of the warm-up message after the run switch.
    reason = cache.check(DEVICE, warmup_mid, 3, WARMUP_RUN)
    assert reason is not None and "message_id" in reason


def test_consecutive_runs_each_restart_at_zero() -> None:
    """10 consecutive smoke runs, same devices, each restarting seq at 0."""
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    for n in range(10):
        run_id = f"smoke-{n:02d}"
        for seq in range(3):
            message_id = make_message_id(run_id, DEVICE, seq)
            assert cache.check(DEVICE, message_id, seq, run_id) is None
            cache.record(DEVICE, message_id, seq, run_id)
    assert cache.accepted_count(DEVICE) == 30


def test_seed_from_twin_restores_ingestion_state_same_run() -> None:
    """Twin last_run_id equals the incoming run: the seq floor is enforced."""
    last_id = mid(5)
    twin = make_raw_twin(
        DEVICE, last_message_id=last_id, last_seq=5, last_run_id=RUN,
        accepted_count=6,
    )
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, twin)
    assert cache.last_seq(DEVICE) == 5
    assert cache.last_run_id(DEVICE) == RUN
    assert cache.accepted_count(DEVICE) == 6
    # replayed last_message_id is a duplicate
    assert cache.check(DEVICE, last_id, 6, RUN) is not None
    # non-increasing seq within the same run is a duplicate
    assert cache.check(DEVICE, mid(104), 4, RUN) is not None
    assert cache.check(DEVICE, mid(105), 5, RUN) is not None
    # the next seq is fresh
    assert cache.check(DEVICE, mid(6), 6, RUN) is None


def test_seed_from_twin_different_incoming_run_resets_floor() -> None:
    """Twin last_run_id differs from the incoming run: seq 0 is fresh."""
    twin = make_raw_twin(
        DEVICE,
        last_message_id=mid(9, WARMUP_RUN),
        last_seq=9,
        last_run_id=WARMUP_RUN,
        accepted_count=10,
    )
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, twin)
    assert cache.check(DEVICE, mid(0), 0, RUN) is None
    cache.record(DEVICE, mid(0), 0, RUN)
    assert cache.last_seq(DEVICE) == 0
    assert cache.last_run_id(DEVICE) == RUN
    # but the twin's last_message_id remains caught across the switch
    assert cache.check(DEVICE, mid(9, WARMUP_RUN), 9, WARMUP_RUN) is not None


def test_seed_from_legacy_twin_without_last_run_id_is_safe() -> None:
    """Legacy twin (no last_run_id): unknown run, so the floor never binds."""
    last_id = mid(7)
    twin = make_raw_twin(
        DEVICE, last_message_id=last_id, last_seq=7, accepted_count=8
    )
    del twin["features"]["ingestion"]["properties"]["last_run_id"]
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, twin)
    assert cache.last_run_id(DEVICE) is None
    assert cache.accepted_count(DEVICE) == 8
    # The seq floor only binds within a proven-identical run_id; with an
    # unknown last_run_id a new run's seq 0 must not be rejected.
    assert cache.check(DEVICE, mid(0), 0, RUN) is None
    # The seeded last_message_id is still caught.
    assert cache.check(DEVICE, last_id, 7, RUN) is not None
    # First accept establishes the run and re-arms the floor.
    cache.record(DEVICE, mid(0), 0, RUN)
    assert cache.last_run_id(DEVICE) == RUN
    assert cache.check(DEVICE, mid(100), 0, RUN) is not None


def test_seed_from_twin_with_empty_ingestion_is_unknown_state() -> None:
    twin = make_raw_twin(DEVICE)  # ingestion nulls, accepted_count 0
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, twin)
    assert cache.last_seq(DEVICE) is None
    assert cache.last_run_id(DEVICE) is None
    assert cache.accepted_count(DEVICE) == 0
    assert cache.check(DEVICE, mid(0), 0, RUN) is None


def test_seed_from_twin_tolerates_malformed_ingestion() -> None:
    for twin in (
        {},  # no features at all
        {"features": None},
        {"features": {"ingestion": None}},
        {"features": {"ingestion": {"properties": None}}},
        {"features": {"ingestion": {"properties": {"last_seq": "5"}}}},  # wrong type
        {"features": {"ingestion": {"properties": {"last_seq": True}}}},  # bool
        {"features": {"ingestion": {"properties": {"last_run_id": 42}}}},  # wrong type
        {"features": {"ingestion": {"properties": {"last_run_id": ""}}}},  # empty
    ):
        cache = DedupeCache()
        cache.seed_from_twin(DEVICE, twin)
        assert cache.last_seq(DEVICE) is None
        assert cache.last_run_id(DEVICE) is None
        assert cache.check(DEVICE, mid(0), 0, RUN) is None


@pytest.mark.parametrize(
    "twin",
    [
        pytest.param({"features": [1]}, id="features-list"),
        pytest.param({"features": "ingestion"}, id="features-string"),
        pytest.param({"features": 7}, id="features-number"),
        pytest.param({"features": True}, id="features-bool"),
        pytest.param({"features": {"ingestion": [1]}}, id="ingestion-list"),
        pytest.param({"features": {"ingestion": "properties"}}, id="ingestion-string"),
        pytest.param({"features": {"ingestion": 7}}, id="ingestion-number"),
        pytest.param(
            {"features": {"ingestion": {"properties": [1]}}}, id="properties-list"
        ),
        pytest.param(
            {"features": {"ingestion": {"properties": "last_seq"}}},
            id="properties-string",
        ),
        pytest.param(
            {"features": {"ingestion": {"properties": 7}}}, id="properties-number"
        ),
    ],
)
def test_seed_from_twin_treats_non_mapping_container_as_empty(twin: dict) -> None:
    """A container that is not a JSON object is read as empty, never raised on.

    A truthy non-mapping at ``features``, ``ingestion`` or ``properties`` used
    to escape as an ``AttributeError`` and left the delivery without an
    outcome line (ADR 0011, item 7); the tolerance the docstring promises for
    missing and null values now covers it. Nothing is inferred from such a
    twin: the device is seeded with unknown state.
    """
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, twin)
    assert cache.known_device(DEVICE)
    assert cache.last_seq(DEVICE) is None
    assert cache.last_run_id(DEVICE) is None
    assert cache.accepted_count(DEVICE) == 0
    assert cache.check(DEVICE, mid(0), 0, RUN) is None


def test_message_id_lru_is_bounded() -> None:
    cache = DedupeCache(message_id_capacity=2)
    cache.seed_from_twin(DEVICE, None)
    cache.record(DEVICE, mid(1), 1, RUN)
    cache.record(DEVICE, mid(2), 2, RUN)
    cache.record(DEVICE, mid(3), 3, RUN)  # evicts mid(1)
    # evicted id is no longer caught by the LRU (seq rule would still apply
    # for seq <= last_seq; use a higher seq to isolate the LRU behaviour)
    assert cache.check(DEVICE, mid(1), 10, RUN) is None
    # still-cached ids are caught even with a fresh seq
    assert cache.check(DEVICE, mid(3), 10, RUN) is not None


def test_devices_are_independent() -> None:
    other = DEVICE_UUIDS["smart_ring"]
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    cache.seed_from_twin(other, None)
    cache.record(DEVICE, mid(7), 7, RUN)
    assert cache.last_seq(other) is None
    assert cache.check(other, make_message_id(RUN, other, 0), 0, RUN) is None


def test_invalid_capacity_raises() -> None:
    with pytest.raises(ValueError):
        DedupeCache(message_id_capacity=0)
