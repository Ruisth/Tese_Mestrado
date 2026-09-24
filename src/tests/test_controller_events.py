"""Tests for egw_controller.events (CONTRACTS.md section 5; plan 5.8/7.3).

The ``events.jsonl`` lines must carry exactly the contract field set;
``rejected``/``duplicate``/``failed`` events have ``ditto_ack_monotonic_ns``
and ``latency_ms`` null; each line is written unbuffered in one call, and a
failed write leaves nothing behind for a later flush (ADR 0011, item 9).
"""

from __future__ import annotations

import errno
import io
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


# ---------------------------------------------------------------------------
# A failed write leaves nothing behind for a later flush (ADR 0011, item 9)
# ---------------------------------------------------------------------------


class _RawFileStandIn:
    """Wraps the logger's open handle; ``write`` fails as the test decides."""

    def __init__(self, inner: object, *, raise_error: bool, short_by: int = 0) -> None:
        self._inner = inner
        self.raise_error = raise_error
        self.short_by = short_by
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> int:
        self.writes.append(bytes(data))
        if self.raise_error:
            raise OSError(28, "No space left on device")
        # A short write puts the partial line on disk, as a kernel would.
        partial = data[: len(data) - self.short_by]
        self._inner.write(partial)  # type: ignore[attr-defined]
        return len(partial)

    def close(self) -> None:
        self.closed = True
        self._inner.close()  # type: ignore[attr-defined]

    def flush(self) -> None:
        raise AssertionError("nothing may be flushed after a failed write")


def _install_stand_in(logger: EventLogger, **kwargs: object) -> _RawFileStandIn:
    logger.log(make_event())  # opens the bucket's handle
    stand_in = _RawFileStandIn(logger._files[RUN_ID], **kwargs)  # type: ignore[arg-type]
    logger._files[RUN_ID] = stand_in  # type: ignore[assignment]
    return stand_in


def test_lines_are_written_unbuffered_in_one_call(logger: EventLogger) -> None:
    """One ``write`` call per line, bytes already encoded, on an unbuffered
    binary handle: the line is on disk or the call has raised, and nothing
    stays in a userspace buffer for a later flush or close."""
    stand_in = _install_stand_in(logger, raise_error=False)
    logger.log(make_event(seq=1))
    (data,) = stand_in.writes
    assert data.endswith(b"\n")
    assert json.loads(data)["seq"] == 1
    inner = stand_in._inner
    assert getattr(inner, "mode", "") == "ab"
    assert isinstance(inner, io.RawIOBase)


def test_failed_write_raises_drops_the_handle_and_leaves_no_late_line(
    logger: EventLogger, tmp_path: Path
) -> None:
    """A write that raises: the error propagates as ``OSError``, the handle
    is closed and forgotten, and the failed line never appears later, not
    even after the next successful write and ``close()``."""
    stand_in = _install_stand_in(logger, raise_error=True)
    with pytest.raises(OSError):
        logger.log(make_event(seq=7))
    assert stand_in.closed is True
    assert RUN_ID not in logger._files
    # Recovery: the next line opens a fresh handle and is written whole.
    logger.log(make_event(seq=8))
    logger.close()
    assert [record["seq"] for record in read_lines(tmp_path)] == [0, 8]


def test_short_write_is_reported_as_eio_and_the_handle_is_dropped(
    logger: EventLogger, tmp_path: Path
) -> None:
    """A write that returns fewer bytes than the line is an ``OSError``
    (``EIO``) naming both counts; the handle is dropped; the partial line
    stays on disk, terminated at the next open so the next line is intact."""
    stand_in = _install_stand_in(logger, raise_error=False, short_by=5)
    with pytest.raises(OSError) as raised:
        logger.log(make_event(seq=7))
    assert raised.value.errno == errno.EIO
    assert "bytes" in str(raised.value)
    assert stand_in.closed is True
    assert RUN_ID not in logger._files
    logger.log(make_event(seq=8))
    logger.close()
    raw = (tmp_path / RUN_ID / EVENTS_FILENAME).read_bytes()
    lines = raw.split(b"\n")
    assert lines[-1] == b""
    records = [json.loads(line) for line in lines[:-1] if _is_json(line)]
    assert [record["seq"] for record in records] == [0, 8]
    # Exactly one non-JSON line: the partial one, which a reader skips.
    assert sum(1 for line in lines[:-1] if not _is_json(line)) == 1


def _is_json(line: bytes) -> bool:
    try:
        json.loads(line)
    except ValueError:
        return False
    return True


def test_open_after_a_partial_line_terminates_it_first(tmp_path: Path) -> None:
    """A file left without its final newline (a short write, a crash) is
    terminated before the next line is appended, so the two never merge."""
    run_dir = tmp_path / RUN_ID
    run_dir.mkdir()
    (run_dir / EVENTS_FILENAME).write_bytes(b'{"run_id": "run-2026')
    with EventLogger(tmp_path) as logger:
        logger.log(make_event(seq=3))
    raw = (run_dir / EVENTS_FILENAME).read_bytes()
    assert raw.startswith(b'{"run_id": "run-2026\n{')
    lines = raw.split(b"\n")
    assert lines[-1] == b""
    (record,) = [json.loads(line) for line in lines[:-1] if _is_json(line)]
    assert record["seq"] == 3
