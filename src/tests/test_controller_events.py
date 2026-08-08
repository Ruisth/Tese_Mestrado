"""Tests for egw_controller.events (CONTRACTS.md section 5; plan 5.8/7.3).

The ``events.jsonl`` lines must carry exactly the contract field set;
``rejected``/``duplicate``/``failed`` events have ``ditto_ack_monotonic_ns``
and ``latency_ms`` null; each line is flushed immediately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest

from egw_controller.events import (
    EVENT_FIELDS,
    EVENTS_FILENAME,
    OUTCOMES,
    UNKNOWN_RUN_BUCKET,
    ControllerEvent,
    EventLogger,
)
from test_controller_helpers import DEVICE_UUIDS, RUN_ID, make_message_id

DEVICE = DEVICE_UUIDS["smartwatch"]


def make_event(**overrides: object) -> ControllerEvent:
    base: dict = {
        "run_id": RUN_ID,
        "message_id": make_message_id(RUN_ID, DEVICE, 0),
        "device_uuid": DEVICE,
        "device_type": "smartwatch",
        "seq": 0,
        "received_monotonic_ns": 1_000_000,
        "ditto_ack_monotonic_ns": 4_500_000,
        "latency_ms": 3.5,
        "outcome": "accepted",
        "attempts": 1,
        "error": None,
    }
    base.update(overrides)
    return ControllerEvent(**base)


@pytest.fixture
def logger(tmp_path: Path) -> Iterator[EventLogger]:
    with EventLogger(tmp_path) as event_logger:
        yield event_logger


def read_lines(tmp_path: Path, bucket: str = RUN_ID) -> list[dict]:
    events_file = tmp_path / bucket / EVENTS_FILENAME
    with events_file.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_contract_field_set_is_exact() -> None:
    assert EVENT_FIELDS == (
        "run_id",
        "message_id",
        "device_uuid",
        "device_type",
        "seq",
        "received_monotonic_ns",
        "ditto_ack_monotonic_ns",
        "latency_ms",
        "outcome",
        "attempts",
        "error",
    )
    assert OUTCOMES == ("accepted", "rejected", "duplicate", "failed")


def test_accepted_event_line_has_exact_fields(
    logger: EventLogger, tmp_path: Path
) -> None:
    logger.log(make_event())
    (record,) = read_lines(tmp_path)
    assert list(record) == list(EVENT_FIELDS)  # exact keys, contract order
    assert record["run_id"] == RUN_ID
    assert record["seq"] == 0
    assert record["received_monotonic_ns"] == 1_000_000
    assert record["ditto_ack_monotonic_ns"] == 4_500_000
    assert record["latency_ms"] == 3.5
    assert record["outcome"] == "accepted"
    assert record["attempts"] == 1
    assert record["error"] is None


@pytest.mark.parametrize("outcome", ["rejected", "duplicate", "failed"])
def test_non_accepted_events_have_null_ack_and_latency(
    logger: EventLogger, tmp_path: Path, outcome: str
) -> None:
    logger.log(
        make_event(
            outcome=outcome,
            ditto_ack_monotonic_ns=None,
            latency_ms=None,
            attempts=0 if outcome != "failed" else 3,
            error="some reason",
        )
    )
    (record,) = read_lines(tmp_path)
    assert record["outcome"] == outcome
    assert record["ditto_ack_monotonic_ns"] is None
    assert record["latency_ms"] is None
    assert record["error"] == "some reason"


def test_malformed_payload_event_serializes_null_identity(
    logger: EventLogger, tmp_path: Path
) -> None:
    logger.log(
        make_event(
            run_id=None,
            message_id=None,
            device_uuid=None,
            device_type=None,
            seq=None,
            outcome="rejected",
            ditto_ack_monotonic_ns=None,
            latency_ms=None,
            attempts=0,
            error="invalid JSON payload",
        )
    )
    (record,) = read_lines(tmp_path, bucket=UNKNOWN_RUN_BUCKET)
    for field in ("run_id", "message_id", "device_uuid", "device_type", "seq"):
        assert record[field] is None


@pytest.mark.parametrize("bad_run_id", ["..", "a/b", "x" * 65, "run id"])
def test_unsafe_run_id_goes_to_unknown_bucket(
    logger: EventLogger, tmp_path: Path, bad_run_id: str
) -> None:
    logger.log(
        make_event(
            run_id=bad_run_id,
            outcome="rejected",
            ditto_ack_monotonic_ns=None,
            latency_ms=None,
            attempts=0,
            error="bad run_id",
        )
    )
    assert (tmp_path / UNKNOWN_RUN_BUCKET / EVENTS_FILENAME).exists()


def test_one_file_per_run_id(logger: EventLogger, tmp_path: Path) -> None:
    logger.log(make_event(run_id="run-a"))
    logger.log(make_event(run_id="run-b"))
    logger.log(make_event(run_id="run-a", seq=1))
    assert len(read_lines(tmp_path, "run-a")) == 2
    assert len(read_lines(tmp_path, "run-b")) == 1


def test_lines_are_flushed_while_file_stays_open(
    logger: EventLogger, tmp_path: Path
) -> None:
    # Readable before close() because every line is flushed on write.
    logger.log(make_event())
    assert len(read_lines(tmp_path)) == 1
    logger.log(make_event(seq=1))
    assert len(read_lines(tmp_path)) == 2


def test_reopen_after_close_appends(tmp_path: Path) -> None:
    with EventLogger(tmp_path) as logger:
        logger.log(make_event())
    with EventLogger(tmp_path) as logger:
        logger.log(make_event(seq=1))
    records = read_lines(tmp_path)
    assert [record["seq"] for record in records] == [0, 1]


def test_invalid_outcome_raises(logger: EventLogger) -> None:
    with pytest.raises(ValueError):
        logger.log(make_event(outcome="dropped"))


def test_accepted_without_ack_raises(logger: EventLogger) -> None:
    with pytest.raises(ValueError):
        logger.log(make_event(ditto_ack_monotonic_ns=None, latency_ms=None))


def test_rejected_with_ack_raises(logger: EventLogger) -> None:
    with pytest.raises(ValueError):
        logger.log(make_event(outcome="rejected", attempts=0, error="x"))
