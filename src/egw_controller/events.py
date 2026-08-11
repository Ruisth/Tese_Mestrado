"""Append-only ``events.jsonl`` writer (CONTRACTS.md section 5; plan 5.8/7.3).

One file per ``run_id``: ``{EGW_EVENT_LOG_DIR}/{run_id}/events.jsonl``, matching
the evidence layout ``results/raw/<run_id>/events.jsonl``. Every record carries
exactly the contract field set; each line is flushed immediately so the file is
usable while the run is still in progress.
"""

from __future__ import annotations

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
        self._files: dict[str, IO[str]] = {}
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

    def _open(self, bucket: str) -> IO[str]:
        fh = self._files.get(bucket)
        if fh is None or fh.closed:
            run_dir = self._log_dir / bucket
            run_dir.mkdir(parents=True, exist_ok=True)
            fh = (run_dir / EVENTS_FILENAME).open("a", encoding="utf-8", newline="\n")
            self._files[bucket] = fh
        return fh

    def log(self, event: ControllerEvent) -> None:
        """Append one event line and flush it immediately."""
        self._validate(event)
        line = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            fh = self._open(self._bucket(event.run_id))
            fh.write(line + "\n")
            fh.flush()

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
