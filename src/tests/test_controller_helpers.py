"""Shared builders and fakes for the controller test suite (no tests here)."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Mapping

from egw_controller.events import ControllerEvent, EventLogger
from egw_controller.service import InboundMessage

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"

# CONTRACTS.md section 2: project-wide UUID v5 namespace.
EGW_UUID_NAMESPACE = uuid.UUID("6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0")

RUN_ID = "run-2026-08-07-0001"
EGW_ID = "egw-01"
TS = "2026-08-07T12:00:00.000Z"

# Fixed lowercase UUID v4 literals (version nibble 4, variant in [89ab]).
DEVICE_UUIDS: dict[str, str] = {
    "smartwatch": "1b46a1f5-9a3e-4c2d-8f6b-2d9e5a7c1b3d",
    "smart_ring": "3f9d2c81-5e4a-4b7f-9a1c-6d8e0f2b4a6c",
    "smart_clothing": "7a5c3e91-2b8d-4f6a-b3e5-9c1d7f0a2e4b",
}

_MEASUREMENTS: dict[str, dict[str, Any]] = {
    "smartwatch": {"heart_rate_bpm": 72, "lat": 38.7369, "lon": -9.1427},
    "smart_ring": {"skin_temp_c": 33.5, "spo2_pct": 98},
    "smart_clothing": {
        "accel_x": 0.12,
        "accel_y": -0.34,
        "accel_z": 9.81,
        "breathing_rpm": 15.0,
    },
}


def make_message_id(run_id: str, device_uuid: str, seq: int) -> str:
    """UUID v5 exactly as the simulator derives it (CONTRACTS.md section 2)."""
    return str(uuid.uuid5(EGW_UUID_NAMESPACE, f"{run_id}:{device_uuid}:{seq}"))


def make_payload(
    device_type: str = "smartwatch",
    *,
    seq: int = 0,
    run_id: str = RUN_ID,
    device_uuid: str | None = None,
    egw_id: str = EGW_ID,
    **overrides: Any,
) -> dict[str, Any]:
    device_uuid = device_uuid or DEVICE_UUIDS[device_type]
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "message_id": make_message_id(run_id, device_uuid, seq),
        "seq": seq,
        "ts": TS,
        "egw_id": egw_id,
        "device_uuid": device_uuid,
        "device_type": device_type,
    }
    payload.update(_MEASUREMENTS[device_type])
    payload.update(overrides)
    return payload


def topic_for(payload: Mapping[str, Any]) -> str:
    return f"c2dt/{payload['egw_id']}/{payload['device_uuid']}/telemetry"


def make_inbound(
    payload: Mapping[str, Any] | bytes,
    *,
    topic: str | None = None,
    received_monotonic_ns: int = 1_000_000,
) -> InboundMessage:
    if isinstance(payload, bytes):
        raw = payload
        if topic is None:
            raise ValueError("topic is required for raw byte payloads")
    else:
        raw = json.dumps(payload).encode("utf-8")
        topic = topic or topic_for(payload)
    return InboundMessage(
        topic=topic, payload=raw, received_monotonic_ns=received_monotonic_ns
    )


def make_raw_twin(
    device_uuid: str,
    *,
    device_type: str = "smartwatch",
    egw_id: str = EGW_ID,
    last_message_id: str | None = None,
    last_seq: int | None = None,
    last_run_id: str | None = None,
    accepted_count: int = 0,
    extra_features: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Raw Ditto thing JSON as returned by GET /api/2/things/{thingId}."""
    features: dict[str, Any] = {
        "ingestion": {
            "properties": {
                "last_message_id": last_message_id,
                "last_seq": last_seq,
                "last_run_id": last_run_id,
                "last_ts": TS if last_seq is not None else None,
                "accepted_count": accepted_count,
            }
        }
    }
    if extra_features:
        features.update(extra_features)
    return {
        "thingId": f"org.c2dta:{device_uuid}",
        "policyId": f"org.c2dta:{device_uuid}",
        "attributes": {
            "device_type": device_type,
            "egw_id": egw_id,
            "schema_version": "1.0.0",
        },
        "features": features,
    }


class FakeClock:
    """Deterministic monotonic_ns stand-in."""

    def __init__(self, value_ns: int = 0) -> None:
        self.value_ns = value_ns

    def advance(self, delta_ns: int) -> None:
        self.value_ns += delta_ns

    def __call__(self) -> int:
        return self.value_ns


class FakeDittoClient:
    """In-memory DittoClientLike implementation with call recording."""

    def __init__(
        self,
        *,
        twins: dict[str, dict[str, Any]] | None = None,
        patch_attempts: int = 1,
        fail_patch: Exception | None = None,
        fail_get: Exception | None = None,
        ready: bool = True,
    ) -> None:
        self.twins: dict[str, dict[str, Any]] = dict(twins or {})
        self.patch_attempts = patch_attempts
        self.fail_patch = fail_patch
        self.fail_get = fail_get
        self.ready = ready
        self.get_calls: list[str] = []
        self.ensure_calls: list[dict[str, str]] = []
        self.patch_calls: list[tuple[str, dict[str, Any]]] = []

    async def get_twin(self, device_uuid: str) -> dict[str, Any] | None:
        self.get_calls.append(device_uuid)
        if self.fail_get is not None:
            raise self.fail_get
        return self.twins.get(device_uuid)

    async def ensure_twin(
        self,
        *,
        device_uuid: str,
        device_type: str,
        egw_id: str,
        schema_version: str,
    ) -> int:
        self.ensure_calls.append(
            {
                "device_uuid": device_uuid,
                "device_type": device_type,
                "egw_id": egw_id,
                "schema_version": schema_version,
            }
        )
        self.twins[device_uuid] = make_raw_twin(
            device_uuid, device_type=device_type, egw_id=egw_id
        )
        return 2  # one PUT policy + one PUT thing

    async def patch_thing(
        self, device_uuid: str, patch: Mapping[str, Any]
    ) -> int:
        self.patch_calls.append((device_uuid, dict(patch)))
        if self.fail_patch is not None:
            raise self.fail_patch
        return self.patch_attempts

    async def is_ready(self) -> bool:
        return self.ready


class GatedDittoClient(FakeDittoClient):
    """FakeDittoClient whose ``patch_thing`` waits until the test releases it.

    ``entered`` is set when the pipeline reaches the Ditto update; the call
    then blocks on ``release``, which stands for a slow Ditto or for retries
    in progress.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def patch_thing(
        self, device_uuid: str, patch: Mapping[str, Any]
    ) -> int:
        self.entered.set()
        await self.release.wait()
        return await super().patch_thing(device_uuid, patch)


class FailingEventLogger(EventLogger):
    """EventLogger whose first ``failures`` writes raise ``OSError``."""

    def __init__(self, log_dir: Path | str, *, failures: int = 1) -> None:
        super().__init__(log_dir)
        self.failures_left = failures

    def log(self, event: ControllerEvent) -> None:
        if self.failures_left > 0:
            self.failures_left -= 1
            raise OSError("simulated event log write failure")
        super().log(event)


_TERMINAL_AND_HOLDING = (
    "accepted",
    "rejected",
    "duplicate",
    "failed",
    "dropped",
    "processing_errors",
    "in_progress",
)


def accounting_gap(
    reading: Mapping[str, Any], queue_depth: int | None = None
) -> int:
    """``received`` minus the right-hand side of the identity (CONTRACTS 5).

    0 while the controller runs; -1 exactly while the shutdown marker of
    ``ControllerService.stop`` is queued, because ``queue_depth`` counts it.
    ``queue_depth`` defaults to ``reading["queue_depth"]`` (a ``/metrics``
    body); pass it for a bare ``MetricsCounters.snapshot()``, in the same
    synchronous stretch as the snapshot.
    """
    if queue_depth is None:
        queue_depth = reading["queue_depth"]
    held = sum(reading[name] for name in _TERMINAL_AND_HOLDING) + queue_depth
    return reading["received"] - held


def read_events(log_dir: Path, run_id: str = RUN_ID) -> list[dict[str, Any]]:
    events_file = log_dir / run_id / "events.jsonl"
    if not events_file.exists():
        return []
    with events_file.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
