"""Tests for egw_controller.dedupe (CONTRACTS.md section 4 idempotency).

Reject repeated ``message_id`` and non-increasing ``seq``; state is seeded
from the twin's ``ingestion`` feature after a controller restart.
"""

from __future__ import annotations

import pytest

from egw_controller.dedupe import DedupeCache, UnknownDeviceError
from test_controller_helpers import DEVICE_UUIDS, make_message_id, make_raw_twin

DEVICE = DEVICE_UUIDS["smartwatch"]
RUN = "dedupe-run"


def mid(seq: int) -> str:
    return make_message_id(RUN, DEVICE, seq)


def test_unknown_device_before_seeding() -> None:
    cache = DedupeCache()
    assert not cache.known_device(DEVICE)
    with pytest.raises(UnknownDeviceError):
        cache.check(DEVICE, mid(0), 0)
    with pytest.raises(UnknownDeviceError):
        cache.record(DEVICE, mid(0), 0)
    with pytest.raises(UnknownDeviceError):
        cache.accepted_count(DEVICE)


def test_seed_with_none_twin_starts_empty() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    assert cache.known_device(DEVICE)
    assert cache.last_seq(DEVICE) is None
    assert cache.accepted_count(DEVICE) == 0
    assert cache.check(DEVICE, mid(0), 0) is None  # seq 0 is fresh on a new twin


def test_fresh_message_then_replay_is_duplicate() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    assert cache.check(DEVICE, mid(0), 0) is None
    cache.record(DEVICE, mid(0), 0)
    reason = cache.check(DEVICE, mid(0), 0)
    assert reason is not None and "message_id" in reason


def test_seq_regression_is_duplicate_even_with_new_message_id() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    cache.record(DEVICE, mid(5), 5)
    # equal seq
    assert cache.check(DEVICE, mid(105), 5) is not None
    # lower seq
    assert cache.check(DEVICE, mid(103), 3) is not None
    # strictly higher seq is fresh
    assert cache.check(DEVICE, mid(6), 6) is None


def test_record_advances_state() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    cache.record(DEVICE, mid(0), 0)
    cache.record(DEVICE, mid(1), 1)
    assert cache.last_seq(DEVICE) == 1
    assert cache.accepted_count(DEVICE) == 2


def test_record_never_decreases_last_seq() -> None:
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    cache.record(DEVICE, mid(5), 5)
    cache.record(DEVICE, mid(2), 2)  # defensive: out-of-order record
    assert cache.last_seq(DEVICE) == 5


def test_seed_from_twin_restores_ingestion_state() -> None:
    last_id = mid(5)
    twin = make_raw_twin(
        DEVICE, last_message_id=last_id, last_seq=5, accepted_count=6
    )
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, twin)
    assert cache.last_seq(DEVICE) == 5
    assert cache.accepted_count(DEVICE) == 6
    # replayed last_message_id is a duplicate
    assert cache.check(DEVICE, last_id, 6) is not None
    # non-increasing seq is a duplicate
    assert cache.check(DEVICE, mid(104), 4) is not None
    assert cache.check(DEVICE, mid(105), 5) is not None
    # the next seq is fresh
    assert cache.check(DEVICE, mid(6), 6) is None


def test_seed_from_twin_with_empty_ingestion_is_unknown_state() -> None:
    twin = make_raw_twin(DEVICE)  # ingestion nulls, accepted_count 0
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, twin)
    assert cache.last_seq(DEVICE) is None
    assert cache.accepted_count(DEVICE) == 0
    assert cache.check(DEVICE, mid(0), 0) is None


def test_seed_from_twin_tolerates_malformed_ingestion() -> None:
    for twin in (
        {},  # no features at all
        {"features": None},
        {"features": {"ingestion": None}},
        {"features": {"ingestion": {"properties": None}}},
        {"features": {"ingestion": {"properties": {"last_seq": "5"}}}},  # wrong type
        {"features": {"ingestion": {"properties": {"last_seq": True}}}},  # bool
    ):
        cache = DedupeCache()
        cache.seed_from_twin(DEVICE, twin)
        assert cache.last_seq(DEVICE) is None
        assert cache.check(DEVICE, mid(0), 0) is None


def test_message_id_lru_is_bounded() -> None:
    cache = DedupeCache(message_id_capacity=2)
    cache.seed_from_twin(DEVICE, None)
    cache.record(DEVICE, mid(1), 1)
    cache.record(DEVICE, mid(2), 2)
    cache.record(DEVICE, mid(3), 3)  # evicts mid(1)
    # evicted id is no longer caught by the LRU (seq rule would still apply
    # for seq <= last_seq; use a higher seq to isolate the LRU behaviour)
    assert cache.check(DEVICE, mid(1), 10) is None
    # still-cached ids are caught even with a fresh seq
    assert cache.check(DEVICE, mid(3), 10) is not None


def test_devices_are_independent() -> None:
    other = DEVICE_UUIDS["smart_ring"]
    cache = DedupeCache()
    cache.seed_from_twin(DEVICE, None)
    cache.seed_from_twin(other, None)
    cache.record(DEVICE, mid(7), 7)
    assert cache.last_seq(other) is None
    assert cache.check(other, make_message_id(RUN, other, 0), 0) is None


def test_invalid_capacity_raises() -> None:
    with pytest.raises(ValueError):
        DedupeCache(message_id_capacity=0)
