"""Append-only ``events.jsonl`` writer (CONTRACTS.md section 5; plan 5.8/7.3).

One file per ``run_id``: ``{EGW_EVENT_LOG_DIR}/{run_id}/events.jsonl``, matching
the evidence layout ``results/raw/<run_id>/events.jsonl``. Every record carries
exactly the contract field set.

Each line is one ``write`` call of the encoded bytes on an unbuffered,
append-only handle (ADR 0011, item 9): when ``log`` returns the line has been
handed to the kernel, and when it raises nothing of that line stays in a
userspace buffer for a later flush or close. A write that raises ``OSError``
or returns fewer bytes than the line (reported as ``OSError(EIO)``) closes
and forgets the handle; the next line opens the file again. A short write can
leave a partial line on disk; it is terminated with a newline at the next
open, so the following line never merges with it, and readers skip a line
that is not JSON.
"""

from __future__ import annotations

import errno
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

EVENT_FIELDS: tuple[str, ...] = (
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

OUTCOMES: tuple[str, ...] = ("accepted", "rejected", "duplicate", "failed")

EVENTS_FILENAME = "events.jsonl"

# Bucket used when a payload was too malformed to yield a usable run_id.
UNKNOWN_RUN_BUCKET = "unknown"

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@dataclass(frozen=True, slots=True)
class ControllerEvent:
    """One processed telemetry message, with the exact contract field set.

    Identity fields are ``None`` when the inbound payload was too malformed to
    extract them (the JSON then serializes them as ``null``).
    """

    run_id: str | None
    message_id: str | None
    device_uuid: str | None
    device_type: str | None
    seq: int | None
    received_monotonic_ns: int
    ditto_ack_monotonic_ns: int | None
    latency_ms: float | None
    outcome: str
    attempts: int
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in EVENT_FIELDS}


class EventLogger:
    """Thread-safe append-only writer of per-run ``events.jsonl`` files."""

    def __init__(self, log_dir: Path | str) -> None:
        self._log_dir = Path(log_dir)
        self._files: dict[str, IO[bytes]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _bucket(run_id: str | None) -> str:
        if (
            run_id is None
            or run_id in (".", "..")
            or not _RUN_ID_RE.fullmatch(run_id)
        ):
            return UNKNOWN_RUN_BUCKET
        return run_id

    @staticmethod
    def _validate(event: ControllerEvent) -> None:
        if event.outcome not in OUTCOMES:
            raise ValueError(
                f"outcome must be one of {OUTCOMES}, got {event.outcome!r}"
            )
        if event.attempts < 0:
            raise ValueError("attempts must be >= 0")
        if event.outcome == "accepted":
            if event.ditto_ack_monotonic_ns is None or event.latency_ms is None:
                raise ValueError(
                    "accepted events require ditto_ack_monotonic_ns and latency_ms"
                )
        elif event.ditto_ack_monotonic_ns is not None or event.latency_ms is not None:
            raise ValueError(
                f"{event.outcome} events must have null ditto_ack_monotonic_ns "
                "and latency_ms"
            )

    @staticmethod
    def _ends_without_newline(path: Path) -> bool:
        """True when the file exists, is not empty and lacks a final newline
        (a partial line left by a short write or by a process that died)."""
        try:
            if path.stat().st_size == 0:
                return False
            with path.open("rb") as probe:
                probe.seek(-1, 2)
                return probe.read(1) != b"\n"
        except FileNotFoundError:
            return False

    def _open(self, bucket: str) -> IO[bytes]:
        fh = self._files.get(bucket)
        if fh is None or fh.closed:
            run_dir = self._log_dir / bucket
            run_dir.mkdir(parents=True, exist_ok=True)
            path = run_dir / EVENTS_FILENAME
            terminate = self._ends_without_newline(path)
            fh = path.open("ab", buffering=0)
            if terminate:
                try:
                    fh.write(b"\n")
                except OSError:
                    self._drop(bucket, fh)
                    raise
            self._files[bucket] = fh
        return fh

    def _drop(self, bucket: str, fh: IO[bytes]) -> None:
        """Forget a handle whose write failed; its close may fail too."""
        self._files.pop(bucket, None)
        try:
            fh.close()
        except OSError:
            pass

    def log(self, event: ControllerEvent) -> None:
        """Append one event line with one unbuffered write.

        Raises ``OSError`` when the line was not written whole; the handle is
        then closed and forgotten, so nothing is left for a later flush.
        """
        self._validate(event)
        line = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
        data = (line + "\n").encode("utf-8")
        with self._lock:
            bucket = self._bucket(event.run_id)
            fh = self._open(bucket)
            try:
                written = fh.write(data)
            except OSError:
                self._drop(bucket, fh)
                raise
            if written is None or written < len(data):
                self._drop(bucket, fh)
                raise OSError(
                    errno.EIO,
                    f"short write to {EVENTS_FILENAME}: {written} of "
                    f"{len(data)} bytes written",
                )

    def close(self) -> None:
        with self._lock:
            for fh in self._files.values():
                if not fh.closed:
                    fh.close()
            self._files.clear()

    def __enter__(self) -> "EventLogger":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
