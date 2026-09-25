"""End-to-end pipeline tests for egw_controller.service with a fake Ditto client.

Covers all four outcomes (``accepted``/``rejected``/``duplicate``/``failed``),
first-contact twin creation, dedupe seeding from an existing twin, latency
semantics (ack and latency null unless accepted), the metrics counters and
the accounting identity of the progress counters (CONTRACTS 5), asserted
after every step of scripted runs and on the fault paths; and, for ADR 0011,
the acknowledgement point (a PUBACK is requested by the consumer only after
the delivery's line was written, for QoS 1 only), the connection end on a
delivery without a line, the purge and skip of an ended connection's
deliveries, the residual ``failed`` line before the PATCH and the stop
order without a queue marker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import pytest

from egw_controller import schema as schema_module
from egw_controller import service as service_module
from egw_controller.dedupe import DedupeCache
from egw_controller.ditto import DittoUnavailableError
from egw_controller.events import EVENT_FIELDS, ControllerEvent, EventLogger
from egw_controller.metrics import MetricsCounters
from egw_controller.schema import SchemaRepository
from egw_controller.service import ControllerService, InboundMessage
from test_controller_helpers import (
    DEVICE_UUIDS,
    EGW_UUID_NAMESPACE,
    RUN_ID,
    SCHEMA_DIR,
    FailingEventLogger,
    FakeClock,
    FakeDittoClient,
    GatedDittoClient,
    accounting_gap,
    make_inbound,
    make_message_id,
    make_payload,
    make_raw_twin,
    read_events,
    topic_for,
    until,
)

WATCH = DEVICE_UUIDS["smartwatch"]


class _BridgeRecorder:
    """Stands in for the bridge's ``ack`` and ``end_connection`` callables."""

    def __init__(self, *, ack_result: bool = True) -> None:
        self.acks: list[InboundMessage] = []
        self.ends: list[tuple[str, InboundMessage | None]] = []
        self.ack_result = ack_result
        self.queue_depth: Callable[[], int] | None = None
        self.depth_at_ack: list[int] = []
        self.order: list[tuple[str, int]] = []

    def acknowledge(self, message: InboundMessage) -> bool:
        self.acks.append(message)
        self.order.append(("ack", message.mid))
        if self.queue_depth is not None:
            self.depth_at_ack.append(self.queue_depth())
        return self.ack_result

    def end_connection(self, cause: str, message: InboundMessage | None) -> None:
        self.ends.append((cause, message))


class _OrderRecordingEventLogger(EventLogger):
    """Appends ``("line", seq)`` to a shared order list when a line is written."""

    def __init__(self, log_dir: Path, order: list[tuple[str, int]]) -> None:
        super().__init__(log_dir)
        self.order = order

    def log(self, event: ControllerEvent) -> None:
        super().log(event)
        self.order.append(("line", event.seq if event.seq is not None else -1))


async def _run_until_idle_then_stop(
    service: ControllerService, metrics: MetricsCounters
) -> None:
    """Consume the submitted backlog, then request the stop and wait for the
    consumer to exit (the stop request drains nothing by itself)."""
    task = asyncio.create_task(service.run())
    await until(
        lambda: metrics.snapshot()["in_progress"] == 0 and service.queue_depth() == 0
    )
    await service.stop()
    await task


@pytest.fixture(scope="module")
def repository() -> SchemaRepository:
    return SchemaRepository(SCHEMA_DIR)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(5_000_000)


@pytest.fixture
def ditto() -> FakeDittoClient:
    return FakeDittoClient()


@pytest.fixture
def events(tmp_path: Path) -> Iterator[EventLogger]:
    with EventLogger(tmp_path) as logger:
        yield logger


@pytest.fixture
def metrics() -> MetricsCounters:
    return MetricsCounters()


@pytest.fixture
def service(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
    clock: FakeClock,
) -> ControllerService:
    return ControllerService(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
        monotonic_ns=clock,
    )


# ---------------------------------------------------------------------------
# accepted
# ---------------------------------------------------------------------------


async def test_accepted_first_contact_creates_twin(
    service: ControllerService,
    ditto: FakeDittoClient,
    tmp_path: Path,
    metrics: MetricsCounters,
) -> None:
    payload = make_payload("smartwatch", seq=0)
    await service.process(make_inbound(payload, received_monotonic_ns=1_000_000))

    # First contact: twin looked up, then policy+thing created.
    assert ditto.get_calls == [WATCH]
    assert ditto.ensure_calls == [
        {
            "device_uuid": WATCH,
            "device_type": "smartwatch",
            "egw_id": "egw-01",
            "schema_version": "1.0.0",
        }
    ]
    (device_uuid, patch) = ditto.patch_calls[0]
    assert device_uuid == WATCH
    assert patch["features"]["ingestion"]["properties"]["accepted_count"] == 1
    assert patch["features"]["vitals"]["properties"]["heart_rate_bpm"] == (
        payload["heart_rate_bpm"]
    )

    (record,) = read_events(tmp_path)
    assert list(record) == list(EVENT_FIELDS)
    assert record["outcome"] == "accepted"
    assert record["run_id"] == RUN_ID
    assert record["message_id"] == payload["message_id"]
    assert record["device_uuid"] == WATCH
    assert record["device_type"] == "smartwatch"
    assert record["seq"] == 0
    assert record["received_monotonic_ns"] == 1_000_000
    assert record["ditto_ack_monotonic_ns"] == 5_000_000  # FakeClock value
    assert record["latency_ms"] == pytest.approx(4.0)  # (5e6 - 1e6) / 1e6
    assert record["attempts"] == 1
    assert record["error"] is None
    assert metrics.snapshot()["accepted"] == 1


async def test_accepted_sequence_increments_ingestion_count(
    service: ControllerService, ditto: FakeDittoClient
) -> None:
    for seq in range(3):
        await service.process(make_inbound(make_payload("smartwatch", seq=seq)))
    counts = [
        patch["features"]["ingestion"]["properties"]["accepted_count"]
        for _, patch in ditto.patch_calls
    ]
    assert counts == [1, 2, 3]
    # ensure_twin only on first contact
    assert len(ditto.ensure_calls) == 1


async def test_accepted_all_device_types(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    for device_type in ("smartwatch", "smart_ring", "smart_clothing"):
        await service.process(make_inbound(make_payload(device_type)))
    assert len(ditto.patch_calls) == 3
    records = read_events(tmp_path)
    assert [record["outcome"] for record in records] == ["accepted"] * 3


async def test_seeding_from_existing_twin_restores_dedupe(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    # Twin already exists with last_seq=5 in the SAME run: a replayed seq must
    # be duplicate without recreating the twin, and the next seq resumes.
    last_id = make_message_id(RUN_ID, WATCH, 5)
    ditto.twins[WATCH] = make_raw_twin(
        WATCH, last_message_id=last_id, last_seq=5, last_run_id=RUN_ID,
        accepted_count=6,
    )

    await service.process(make_inbound(make_payload("smartwatch", seq=5)))
    await service.process(make_inbound(make_payload("smartwatch", seq=6)))

    assert ditto.ensure_calls == []  # twin existed; never recreated
    (device_uuid, patch) = ditto.patch_calls[0]
    assert device_uuid == WATCH
    assert patch["features"]["ingestion"]["properties"]["last_seq"] == 6
    assert patch["features"]["ingestion"]["properties"]["last_run_id"] == RUN_ID
    assert patch["features"]["ingestion"]["properties"]["accepted_count"] == 7

    records = read_events(tmp_path)
    assert [record["outcome"] for record in records] == ["duplicate", "accepted"]


# ---------------------------------------------------------------------------
# run scoping (CONTRACTS 4, v1.1)
# ---------------------------------------------------------------------------


async def test_warmup_then_measured_run_first_seq_accepted(
    service: ControllerService,
    ditto: FakeDittoClient,
    tmp_path: Path,
    metrics: MetricsCounters,
) -> None:
    # Warm-up run: same device (same seed), seqs 0..2 all accepted.
    warmup_run = f"{RUN_ID}.warmup"
    for seq in range(3):
        await service.process(
            make_inbound(make_payload("smartwatch", seq=seq, run_id=warmup_run))
        )
    warmup_records = read_events(tmp_path, warmup_run)
    assert [record["outcome"] for record in warmup_records] == ["accepted"] * 3

    # Measured run restarts seq at 0: accepted, NOT duplicate (v1.1).
    await service.process(make_inbound(make_payload("smartwatch", seq=0)))
    await service.process(make_inbound(make_payload("smartwatch", seq=3)))
    measured_records = read_events(tmp_path)
    assert [record["outcome"] for record in measured_records] == [
        "accepted",
        "accepted",
    ]
    # Monotonicity binds within the measured run: a never-seen seq below the
    # floor is duplicate. Its message_id is the contract-derived one, so the
    # LRU cannot be what catches it - the run-scoped seq floor is.
    stale = make_payload("smartwatch", seq=1)
    await service.process(make_inbound(stale))
    assert read_events(tmp_path)[-1]["outcome"] == "duplicate"
    assert metrics.snapshot()["accepted"] == 5
    # The measured run's patches carry its run_id in the ingestion feature.
    last_patch = ditto.patch_calls[-2][1]  # last accepted patch
    assert last_patch["features"]["ingestion"]["properties"]["last_run_id"] == (
        RUN_ID
    )


async def test_replayed_message_id_rejected_across_run_switch(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    warmup_run = f"{RUN_ID}.warmup"
    warmup_payload = make_payload("smartwatch", seq=2, run_id=warmup_run)
    await service.process(make_inbound(warmup_payload))
    await service.process(make_inbound(make_payload("smartwatch", seq=0)))
    # QoS 1 redelivery of the warm-up message after the run switch.
    await service.process(make_inbound(warmup_payload))
    warmup_records = read_events(tmp_path, warmup_run)
    assert [record["outcome"] for record in warmup_records] == [
        "accepted",
        "duplicate",
    ]
    assert "message_id" in warmup_records[1]["error"]
    assert len(ditto.patch_calls) == 2  # the replay never reached Ditto


async def test_seeding_from_twin_of_other_run_resets_floor(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    # Restart scenario: the twin holds warm-up state; the incoming run
    # differs, so its seq 0 must be accepted (floor reset), never duplicate.
    warmup_run = f"{RUN_ID}.warmup"
    ditto.twins[WATCH] = make_raw_twin(
        WATCH,
        last_message_id=make_message_id(warmup_run, WATCH, 9),
        last_seq=9,
        last_run_id=warmup_run,
        accepted_count=10,
    )
    await service.process(make_inbound(make_payload("smartwatch", seq=0)))
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "accepted"
    assert ditto.ensure_calls == []


async def test_seeding_from_legacy_twin_without_last_run_id(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    # Legacy twin (pre-v1.1, no last_run_id): unknown run, so a new run's
    # seq 0 is accepted and the twin gains last_run_id on the first accept.
    twin = make_raw_twin(WATCH, last_seq=7, accepted_count=8)
    del twin["features"]["ingestion"]["properties"]["last_run_id"]
    ditto.twins[WATCH] = twin
    await service.process(make_inbound(make_payload("smartwatch", seq=0)))
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "accepted"
    (_, patch) = ditto.patch_calls[0]
    assert patch["features"]["ingestion"]["properties"]["last_run_id"] == RUN_ID


# ---------------------------------------------------------------------------
# rejected
# ---------------------------------------------------------------------------


async def test_rejected_invalid_json_has_null_identity(
    service: ControllerService,
    ditto: FakeDittoClient,
    tmp_path: Path,
    metrics: MetricsCounters,
) -> None:
    topic = topic_for(make_payload("smartwatch"))
    await service.process(
        make_inbound(b"{not json", topic=topic, received_monotonic_ns=42)
    )
    records = read_events(tmp_path, "unknown")
    (record,) = records
    assert record["outcome"] == "rejected"
    for field in ("run_id", "message_id", "device_uuid", "device_type", "seq"):
        assert record[field] is None
    assert record["received_monotonic_ns"] == 42
    assert record["ditto_ack_monotonic_ns"] is None
    assert record["latency_ms"] is None
    assert record["attempts"] == 0
    assert "invalid JSON" in record["error"]
    assert ditto.get_calls == [] and ditto.patch_calls == []
    assert metrics.snapshot()["rejected"] == 1


async def test_rejected_schema_violation_no_ditto_calls(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    payload = make_payload("smartwatch", heart_rate_bpm=999)  # out of range
    await service.process(make_inbound(payload))
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "rejected"
    assert record["message_id"] == payload["message_id"]  # identity still logged
    assert record["latency_ms"] is None
    assert "schema validation failed" in record["error"]
    assert ditto.get_calls == [] and ditto.patch_calls == []


async def test_rejected_bad_topic(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    payload = make_payload("smartwatch")
    await service.process(
        make_inbound(payload, topic=f"c2dt/egw-01/{WATCH}/events")
    )
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "rejected"
    assert ditto.patch_calls == []


async def test_rejected_topic_payload_device_mismatch(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    payload = make_payload("smartwatch")
    other = DEVICE_UUIDS["smart_ring"]
    await service.process(
        make_inbound(payload, topic=f"c2dt/egw-01/{other}/telemetry")
    )
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "rejected"
    assert "device_uuid mismatch" in record["error"]
    assert ditto.get_calls == []


async def test_rejected_topic_payload_egw_mismatch(
    service: ControllerService, tmp_path: Path
) -> None:
    payload = make_payload("smartwatch")
    await service.process(
        make_inbound(payload, topic=f"c2dt/egw-99/{WATCH}/telemetry")
    )
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "rejected"
    assert "egw_id mismatch" in record["error"]


# ---------------------------------------------------------------------------
# rejected: non-standard JSON numeric constants
# ---------------------------------------------------------------------------


def _payload_with_raw_lat(literal: str) -> bytes:
    """Encode a valid smartwatch payload with ``lat`` replaced by a raw literal.

    ``json.dumps`` cannot emit these constants for us without also accepting
    them back, so the substitution is done on the encoded text.
    """
    payload = make_payload("smartwatch", seq=0)
    encoded = json.dumps(payload)
    marker = f'"lat": {payload["lat"]}'
    assert marker in encoded, "test builder no longer matches the encoded payload"
    return encoded.replace(marker, f'"lat": {literal}').encode("utf-8")


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
async def test_rejected_non_standard_json_constant(
    service: ControllerService,
    ditto: FakeDittoClient,
    tmp_path: Path,
    metrics: MetricsCounters,
    literal: str,
) -> None:
    """NaN/Infinity are not JSON and must never reach Ditto.

    Python's decoder accepts them by default, and a non-finite float then
    slips past every schema bound because all comparisons with NaN are false.
    The contracted outcome is ``rejected`` with no Ditto call at all.
    """
    topic = f"c2dt/egw-01/{WATCH}/telemetry"
    await service.process(
        make_inbound(
            _payload_with_raw_lat(literal), topic=topic, received_monotonic_ns=42
        )
    )

    (record,) = read_events(tmp_path, "unknown")
    assert record["outcome"] == "rejected"
    assert record["received_monotonic_ns"] == 42
    assert record["ditto_ack_monotonic_ns"] is None
    assert record["latency_ms"] is None
    assert record["attempts"] == 0
    assert "invalid JSON" in record["error"]
    assert ditto.get_calls == []
    assert ditto.ensure_calls == []
    assert ditto.patch_calls == []
    assert metrics.snapshot()["rejected"] == 1


async def test_non_standard_json_constant_never_reaches_the_twin(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    """A NaN event must not be persisted, and must not seed the device either."""
    topic = f"c2dt/egw-01/{WATCH}/telemetry"
    await service.process(make_inbound(_payload_with_raw_lat("NaN"), topic=topic))
    # A well-formed follow-up is still the device's first contact.
    await service.process(make_inbound(make_payload("smartwatch", seq=0)))
    assert len(ditto.ensure_calls) == 1
    assert [record["outcome"] for record in read_events(tmp_path)] == ["accepted"]
    (_, patch) = ditto.patch_calls[0]
    assert patch["features"]["location"]["properties"]["lat"] == 38.7369


# ---------------------------------------------------------------------------
# rejected: message_id not derived from run_id:device_uuid:seq (CONTRACTS 2)
# ---------------------------------------------------------------------------


def test_namespace_matches_the_simulator_constant() -> None:
    """The controller mirrors the namespace; the two must never drift apart.

    The controller must not import ``egw_simulator`` at runtime (separate
    deliverables; only the controller ships in the deployment image), so the
    constant is duplicated and pinned by this test instead.
    """
    from egw_simulator.envelope import EGW_UUID_NAMESPACE as simulator_namespace

    assert service_module.EGW_UUID_NAMESPACE == simulator_namespace
    assert service_module.EGW_UUID_NAMESPACE == EGW_UUID_NAMESPACE
    # The normative literal from CONTRACTS.md section 2.
    assert service_module.EGW_UUID_NAMESPACE == uuid.UUID(
        "6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0"
    )


def test_controller_does_not_import_the_simulator_at_runtime() -> None:
    """Guard the deliverable boundary that forces the duplicated namespace."""
    for module in (service_module, schema_module):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert not re.search(
            r"^\s*(from|import)\s+egw_simulator\b", source, re.MULTILINE
        ), f"{module.__name__} imports egw_simulator"


def test_derived_message_id_matches_the_simulator_derivation() -> None:
    assert service_module.derive_message_id(RUN_ID, WATCH, 7) == make_message_id(
        RUN_ID, WATCH, 7
    )


@pytest.mark.parametrize(
    ("label", "forged"),
    [
        # Shape-valid UUID v5 for a different seq in the same run.
        ("other_seq", make_message_id(RUN_ID, WATCH, 900)),
        # Shape-valid UUID v5 for a different run.
        ("other_run", make_message_id("some-other-run", WATCH, 0)),
        # Shape-valid UUID v5 for a different device.
        ("other_device", make_message_id(RUN_ID, DEVICE_UUIDS["smart_ring"], 0)),
        # Shape-valid UUID v5 from an entirely foreign namespace.
        ("foreign_namespace", str(uuid.uuid5(uuid.NAMESPACE_DNS, "forged"))),
    ],
)
async def test_rejected_message_id_not_derived_from_envelope(
    service: ControllerService,
    ditto: FakeDittoClient,
    tmp_path: Path,
    metrics: MetricsCounters,
    label: str,
    forged: str,
) -> None:
    """Schema validation only proves the shape; the value must be recomputed.

    ``message_id`` is contractually ``uuid5(namespace, "run:device:seq")``
    (CONTRACTS.md section 2) and the dedupe cache relies on that determinism,
    so an arbitrary valid-looking UUID v5 must be rejected before any twin is
    seeded or patched.
    """
    payload = make_payload("smartwatch", seq=0, message_id=forged)
    await service.process(make_inbound(payload, received_monotonic_ns=42))

    (record,) = read_events(tmp_path)
    assert record["outcome"] == "rejected", label
    assert record["message_id"] == forged  # identity still logged as received
    assert record["received_monotonic_ns"] == 42
    assert record["ditto_ack_monotonic_ns"] is None
    assert record["latency_ms"] is None
    assert record["attempts"] == 0
    assert "message_id" in record["error"]
    assert ditto.get_calls == []
    assert ditto.ensure_calls == []
    assert ditto.patch_calls == []
    assert metrics.snapshot()["rejected"] == 1


async def test_forged_message_id_rejected_before_dedupe_and_seeding(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    """The check precedes the dedupe cache, so a forgery cannot poison it.

    An existing twin makes seeding observable: a rejected event must leave the
    device unknown, so the next genuine event still performs first contact.
    """
    ditto.twins[WATCH] = make_raw_twin(
        WATCH, last_message_id=make_message_id(RUN_ID, WATCH, 3), last_seq=3,
        last_run_id=RUN_ID, accepted_count=4,
    )
    forged = make_payload(
        "smartwatch", seq=4, message_id=make_message_id(RUN_ID, WATCH, 900)
    )
    await service.process(make_inbound(forged))
    assert ditto.get_calls == []  # never seeded

    await service.process(make_inbound(make_payload("smartwatch", seq=4)))
    assert ditto.get_calls == [WATCH]
    assert [record["outcome"] for record in read_events(tmp_path)] == [
        "rejected",
        "accepted",
    ]


async def test_genuine_message_id_still_accepted_for_every_device_type(
    service: ControllerService, tmp_path: Path
) -> None:
    """Regression guard: the new check must not reject contract-conformant ids."""
    for device_type in ("smartwatch", "smart_ring", "smart_clothing"):
        for seq in range(2):
            await service.process(
                make_inbound(make_payload(device_type, seq=seq))
            )
    outcomes = [record["outcome"] for record in read_events(tmp_path)]
    assert outcomes == ["accepted"] * 6


# ---------------------------------------------------------------------------
# duplicate
# ---------------------------------------------------------------------------


async def test_duplicate_message_id_replay(
    service: ControllerService,
    ditto: FakeDittoClient,
    tmp_path: Path,
    metrics: MetricsCounters,
) -> None:
    payload = make_payload("smartwatch", seq=0)
    await service.process(make_inbound(payload))
    await service.process(make_inbound(payload))  # exact replay
    records = read_events(tmp_path)
    assert [record["outcome"] for record in records] == ["accepted", "duplicate"]
    duplicate = records[1]
    assert duplicate["ditto_ack_monotonic_ns"] is None
    assert duplicate["latency_ms"] is None
    assert duplicate["attempts"] == 0
    assert "message_id" in duplicate["error"]
    assert len(ditto.patch_calls) == 1  # replay never reached Ditto
    snapshot = metrics.snapshot()
    assert snapshot["accepted"] == 1 and snapshot["duplicate"] == 1


async def test_duplicate_seq_regression(
    service: ControllerService, ditto: FakeDittoClient, tmp_path: Path
) -> None:
    await service.process(make_inbound(make_payload("smartwatch", seq=5)))
    # Never-seen message_id (seq 4 was skipped) but non-increasing seq.
    stale = make_payload("smartwatch", seq=4)
    await service.process(make_inbound(stale))
    records = read_events(tmp_path)
    assert [record["outcome"] for record in records] == ["accepted", "duplicate"]
    assert "last_seq" in records[1]["error"]
    assert len(ditto.patch_calls) == 1


# ---------------------------------------------------------------------------
# failed
# ---------------------------------------------------------------------------


async def test_failed_patch_after_retries(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    ditto = FakeDittoClient(
        fail_patch=DittoUnavailableError(
            "PATCH failed after 3 attempt(s)", attempts=3, status=503
        )
    )
    service = ControllerService(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
    )
    await service.process(make_inbound(make_payload("smartwatch", seq=0)))
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "failed"
    assert record["attempts"] == 3
    assert record["ditto_ack_monotonic_ns"] is None
    assert record["latency_ms"] is None
    assert "PATCH failed" in record["error"]
    assert metrics.snapshot()["failed"] == 1


async def test_failed_patch_does_not_mark_message_as_seen(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    ditto = FakeDittoClient(
        fail_patch=DittoUnavailableError("unavailable", attempts=3)
    )
    service = ControllerService(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
    )
    payload = make_payload("smartwatch", seq=0)
    await service.process(make_inbound(payload))
    # Ditto back up: the same message must now be accepted, not duplicate.
    ditto.fail_patch = None
    await service.process(make_inbound(payload))
    records = read_events(tmp_path)
    assert [record["outcome"] for record in records] == ["failed", "accepted"]


async def test_failed_seeding_get_twin(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    ditto = FakeDittoClient(
        fail_get=DittoUnavailableError("GET twin failed", attempts=3)
    )
    service = ControllerService(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
    )
    await service.process(make_inbound(make_payload("smartwatch")))
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "failed"
    assert record["attempts"] == 3
    assert ditto.patch_calls == []


# ---------------------------------------------------------------------------
# queue lifecycle and mixed batch
# ---------------------------------------------------------------------------


async def test_run_processes_the_backlog_then_exits_on_the_stop_request(
    service: ControllerService, tmp_path: Path, metrics: MetricsCounters
) -> None:
    """``stop`` queues no marker (ADR 0011, item 13): the consumer processes
    what it takes while running and exits once the stop is requested."""
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    service.submit(make_inbound(make_payload("smartwatch", seq=1)))
    await _run_until_idle_then_stop(service, metrics)
    assert len(read_events(tmp_path)) == 2
    assert metrics.snapshot()["accepted"] == 2
    assert service.queue_depth() == 0


async def test_stop_requested_before_run_processes_nothing(
    service: ControllerService, tmp_path: Path, metrics: MetricsCounters
) -> None:
    """The backlog is left for redelivery, unacknowledged, when the stop
    was requested before the consumer took anything."""
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    await service.stop()
    await service.run()
    assert read_events(tmp_path) == []
    snapshot = metrics.snapshot()
    assert (snapshot["received"], service.queue_depth(), snapshot["accepted"]) == (
        1,
        1,
        0,
    )
    assert _gap(metrics, service) == 0


async def test_mixed_batch_counts_all_four_outcomes(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    ditto = FakeDittoClient()
    service = ControllerService(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
    )
    accepted = make_payload("smartwatch", seq=0)
    await service.process(make_inbound(accepted))  # accepted
    await service.process(make_inbound(accepted))  # duplicate
    await service.process(  # rejected
        make_inbound(make_payload("smartwatch", seq=1, heart_rate_bpm=999))
    )
    ditto.fail_patch = DittoUnavailableError("down", attempts=3)
    await service.process(  # failed
        make_inbound(make_payload("smartwatch", seq=2))
    )
    snapshot = metrics.snapshot()
    assert snapshot["accepted"] == 1
    assert snapshot["rejected"] == 1
    assert snapshot["duplicate"] == 1
    assert snapshot["failed"] == 1
    outcomes = sorted(record["outcome"] for record in read_events(tmp_path))
    assert outcomes == ["accepted", "duplicate", "failed", "rejected"]


def test_queue_full_drops_message_and_counts_dropped(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    service = ControllerService(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
        queue_maxsize=1,
    )
    assert service.queue_depth() == 0
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    assert service.queue_depth() == 1
    assert metrics.snapshot()["dropped"] == 0
    # Queue is full now: the second submit is dropped without raising,
    # incrementing the dropped counter only.
    service.submit(make_inbound(make_payload("smartwatch", seq=1)))
    service.submit(make_inbound(make_payload("smartwatch", seq=2)))
    assert service.queue_depth() == 1
    snapshot = metrics.snapshot()
    assert snapshot["dropped"] == 2
    # The four contract counters are untouched by drops.
    assert snapshot["accepted"] == 0
    assert snapshot["rejected"] == 0
    assert snapshot["duplicate"] == 0
    assert snapshot["failed"] == 0


# ---------------------------------------------------------------------------
# progress counters and the accounting identity (CONTRACTS 5)
# ---------------------------------------------------------------------------


def _make_service(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
    **kwargs: Any,
) -> ControllerService:
    return ControllerService(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
        **kwargs,
    )


def _gap(metrics: MetricsCounters, service: ControllerService) -> int:
    """Identity gap of one reading taken as ``GET /metrics`` takes it: the
    snapshot and the queue depth in one synchronous stretch on the loop."""
    return accounting_gap(metrics.snapshot(), service.queue_depth())


class _GapRecordingDittoClient(GatedDittoClient):
    """Gated client that also records the identity gap at every Ditto update,
    i.e. from inside the processing of each message."""

    def __init__(self) -> None:
        super().__init__()
        self.gaps: list[int] = []
        self.probe: Callable[[], int] | None = None

    async def patch_thing(
        self, device_uuid: str, patch: Mapping[str, Any]
    ) -> int:
        if self.probe is not None:
            self.gaps.append(self.probe())
        return await super().patch_thing(device_uuid, patch)


async def test_identity_holds_after_every_step_of_a_scripted_run(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """``received == outcomes + dropped + processing_errors + in_progress +
    queue_depth`` after every step: enqueue, drop on a full queue, a message
    held by a slow Ditto, and a stop requested with work in progress. The
    stop request takes no queue slot, so the gap is 0 at every instant; the
    delivery in progress completes and the queued one is left in
    ``queue_depth`` for redelivery (ADR 0011, item 13)."""
    ditto = _GapRecordingDittoClient()
    service = _make_service(repository, ditto, events, metrics, queue_maxsize=2)
    ditto.probe = lambda: _gap(metrics, service)
    assert _gap(metrics, service) == 0

    for seq in range(3):
        service.submit(make_inbound(make_payload("smartwatch", seq=seq)))
        assert _gap(metrics, service) == 0
    snapshot = metrics.snapshot()
    assert (snapshot["received"], service.queue_depth(), snapshot["dropped"]) == (
        3,
        2,
        1,
    )

    task = asyncio.create_task(service.run())
    await ditto.entered.wait()
    snapshot = metrics.snapshot()
    # The message being processed is in in_progress, not in queue_depth.
    assert (
        snapshot["in_progress"],
        service.queue_depth(),
        snapshot["accepted"],
    ) == (1, 1, 0)
    assert _gap(metrics, service) == 0

    await service.stop()  # no marker: the queue is untouched
    assert service.queue_depth() == 1
    assert _gap(metrics, service) == 0

    ditto.release.set()
    await task
    snapshot = metrics.snapshot()
    assert (
        snapshot["in_progress"],
        service.queue_depth(),
        snapshot["accepted"],
        snapshot["processing_errors"],
    ) == (0, 1, 1, 0)
    assert snapshot["received"] == 3
    assert snapshot["dropped"] == 1
    assert _gap(metrics, service) == 0
    # Seen from inside processing: 0 for the only message processed.
    assert ditto.gaps == [0]
    assert len(read_events(tmp_path)) == 1


def test_received_includes_messages_dropped_on_a_full_queue(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    """``received`` is counted whatever the capacity decision: once for a
    queued message and once, never twice, for one counted as ``dropped``.
    The ORDER inside ``submit`` is a separate property, pinned by
    ``test_received_is_counted_before_dropped_inside_submit``."""
    service = _make_service(repository, ditto, events, metrics, queue_maxsize=1)
    for seq in range(3):
        service.submit(make_inbound(make_payload("smartwatch", seq=seq)))
    snapshot = metrics.snapshot()
    assert snapshot["received"] == 3
    assert snapshot["dropped"] == 2
    assert service.queue_depth() == 1
    assert snapshot["in_progress"] == 0
    assert snapshot["processing_errors"] == 0
    for outcome in ("accepted", "rejected", "duplicate", "failed"):
        assert snapshot[outcome] == 0
    assert _gap(metrics, service) == 0


def test_received_is_counted_before_dropped_inside_submit(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
) -> None:
    """``submit`` is a plain function, so a reader on the loop cannot see the
    order of its two increments; a reader on another thread can. Counting
    ``received`` first keeps ``dropped <= received`` true for every reader:
    at the instant a message is counted as ``dropped`` it is already in
    ``received``."""
    received_when_dropped: list[int] = []

    class RecordingCounters(MetricsCounters):
        def increment_dropped(self) -> None:
            received_when_dropped.append(self.snapshot()["received"])
            super().increment_dropped()

    metrics = RecordingCounters()
    service = _make_service(repository, ditto, events, metrics, queue_maxsize=1)
    for seq in range(3):
        service.submit(make_inbound(make_payload("smartwatch", seq=seq)))
    # The second and the third message were dropped.
    assert received_when_dropped == [2, 3]
    assert metrics.snapshot()["dropped"] == 2


async def test_process_exception_counts_processing_error_and_keeps_pipeline_alive(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    metrics: MetricsCounters,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed event-record write escapes ``process()``: no outcome counter
    and no event record exist for that message, so it is a
    ``processing_errors``. It means "no outcome was recorded", not "not
    applied": the twin WAS updated."""
    with FailingEventLogger(tmp_path, failures=1) as events:
        service = _make_service(repository, ditto, events, metrics)
        service.submit(make_inbound(make_payload("smartwatch", seq=0)))
        service.submit(make_inbound(make_payload("smartwatch", seq=1)))
        with caplog.at_level(logging.ERROR, logger="egw_controller.service"):
            # Returns: the pipeline stayed alive after the failed write.
            await _run_until_idle_then_stop(service, metrics)

    snapshot = metrics.snapshot()
    assert snapshot["received"] == 2
    assert snapshot["processing_errors"] == 1
    assert snapshot["accepted"] == 1
    assert snapshot["in_progress"] == 0
    assert _gap(metrics, service) == 0
    (record,) = read_events(tmp_path)
    assert record["seq"] == 1
    # Both twins updates happened, the one with no recorded outcome included.
    assert [
        patch["features"]["ingestion"]["properties"]["last_seq"]
        for _, patch in ditto.patch_calls
    ] == [0, 1]
    assert "unhandled error while processing message" in caplog.text


async def test_outcome_counted_then_failure_is_not_a_processing_error(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    """Residual rule: an exception AFTER the outcome was counted must not
    count the message a second time."""

    class RaisesAfterOutcome(ControllerService):
        async def process(self, message: InboundMessage) -> bool:
            await super().process(message)
            raise RuntimeError("after the outcome was counted")

    service = RaisesAfterOutcome(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
    )
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    await _run_until_idle_then_stop(service, metrics)
    snapshot = metrics.snapshot()
    assert snapshot["accepted"] == 1
    assert snapshot["processing_errors"] == 0
    assert snapshot["in_progress"] == 0
    assert _gap(metrics, service) == 0


async def test_process_returning_without_outcome_counts_processing_error(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    """A message that leaves processing silently still reaches a final
    counter: no exit path is on neither side of the identity."""

    class ReturnsWithoutOutcome(ControllerService):
        async def process(self, message: InboundMessage) -> bool:
            return False

    recorder = _BridgeRecorder()
    service = ReturnsWithoutOutcome(
        repository=repository,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
        acknowledge=recorder.acknowledge,
        end_connection=recorder.end_connection,
    )
    message = make_inbound(make_payload("smartwatch", seq=0), mid=4, qos=1)
    service.submit(message)
    await _run_until_idle_then_stop(service, metrics)
    snapshot = metrics.snapshot()
    assert snapshot["received"] == 1
    assert snapshot["processing_errors"] == 1
    assert snapshot["in_progress"] == 0
    assert _gap(metrics, service) == 0
    # No line, so no PUBACK, and acknowledgement ends on that connection.
    assert recorder.acks == []
    assert recorder.ends == [("no-outcome-line", message)]


async def test_identity_holds_for_mixed_batch_through_the_queue(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """All four outcomes through ``submit`` + ``run``: each message lands in
    exactly one outcome counter, and the event records are unchanged (none
    of the progress names enters an event)."""

    class FailsSecondPatch(FakeDittoClient):
        async def patch_thing(
            self, device_uuid: str, patch: Mapping[str, Any]
        ) -> int:
            if len(self.patch_calls) == 1:
                self.fail_patch = DittoUnavailableError("down", attempts=3)
            return await super().patch_thing(device_uuid, patch)

    ditto = FailsSecondPatch()
    service = _make_service(repository, ditto, events, metrics)
    accepted = make_payload("smartwatch", seq=0)
    service.submit(make_inbound(accepted))  # accepted
    service.submit(make_inbound(accepted))  # duplicate
    service.submit(  # rejected
        make_inbound(make_payload("smartwatch", seq=1, heart_rate_bpm=999))
    )
    service.submit(make_inbound(make_payload("smartwatch", seq=2)))  # failed
    assert _gap(metrics, service) == 0
    await _run_until_idle_then_stop(service, metrics)

    snapshot = metrics.snapshot()
    assert snapshot["received"] == 4
    assert snapshot["accepted"] == 1
    assert snapshot["rejected"] == 1
    assert snapshot["duplicate"] == 1
    assert snapshot["failed"] == 1
    assert snapshot["dropped"] == 0
    assert snapshot["processing_errors"] == 0
    assert snapshot["in_progress"] == 0
    assert _gap(metrics, service) == 0
    records = read_events(tmp_path)
    assert [record["outcome"] for record in records] == [
        "accepted",
        "duplicate",
        "rejected",
        "failed",
    ]
    for record in records:
        assert list(record) == list(EVENT_FIELDS)


async def test_cancelled_consumer_counts_in_flight_message_and_still_raises(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cancellation with a message in flight: the message has no outcome, so
    it is a ``processing_errors``; the backlog stays in ``queue_depth``; the
    cancellation still propagates (the ``finally`` swallows nothing) and,
    ``CancelledError`` not being an ``Exception``, leaves no log record."""
    ditto = GatedDittoClient()
    service = _make_service(repository, ditto, events, metrics)
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    service.submit(make_inbound(make_payload("smartwatch", seq=1)))
    task = asyncio.create_task(service.run())
    await ditto.entered.wait()
    assert metrics.snapshot()["in_progress"] == 1

    with caplog.at_level(logging.DEBUG, logger="egw_controller"):
        task.cancel()
        # Bounded wait: a consumer that swallowed the cancellation would take
        # the second message and block on the gate for ever. The bound only
        # turns that hang into a failure.
        done, _ = await asyncio.wait({task}, timeout=5.0)
        if not done:  # clean-up only, the test has already failed
            ditto.release.set()
            await service.stop()
            await asyncio.wait({task}, timeout=5.0)
    assert task in done, "the consumer swallowed the cancellation"
    assert task.cancelled()
    assert caplog.records == []
    snapshot = metrics.snapshot()
    assert (
        snapshot["in_progress"],
        snapshot["processing_errors"],
        service.queue_depth(),
    ) == (0, 1, 1)
    assert snapshot["received"] == 2
    assert _gap(metrics, service) == 0
    assert read_events(tmp_path) == []


async def test_consumer_cancelled_before_taking_a_message_counts_nothing(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    """Cancellation delivered while the consumer waits in ``get()``, after
    ``submit`` woke it but before it resumed: nothing was taken, so the
    message stays in ``queue_depth`` and no gauge moves."""
    service = _make_service(repository, ditto, events, metrics)
    task = asyncio.create_task(service.run())
    await asyncio.sleep(0)  # the consumer is now parked in get()
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    snapshot = metrics.snapshot()
    assert (
        snapshot["received"],
        snapshot["in_progress"],
        snapshot["processing_errors"],
        service.queue_depth(),
    ) == (1, 0, 0, 1)
    assert _gap(metrics, service) == 0
    assert ditto.patch_calls == []


async def test_idle_consumer_cancelled_leaves_every_counter_at_zero(
    service: ControllerService, metrics: MetricsCounters
) -> None:
    task = asyncio.create_task(service.run())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    snapshot = metrics.snapshot()
    assert (
        snapshot["received"],
        snapshot["in_progress"],
        snapshot["processing_errors"],
        service.queue_depth(),
    ) == (0, 0, 0, 0)
    assert _gap(metrics, service) == 0


class _YieldingFaultyDittoClient(FakeDittoClient):
    """Every call gives the loop back several times, as a real HTTP round
    trip does; ``faults`` maps the number of a ``patch_thing`` call (from 1)
    to the exception it raises after the twin was touched."""

    def __init__(self, faults: Mapping[int, Exception]) -> None:
        super().__init__()
        self.faults = dict(faults)

    async def get_twin(self, device_uuid: str) -> dict[str, Any] | None:
        await asyncio.sleep(0)
        twin = await super().get_twin(device_uuid)
        await asyncio.sleep(0)
        return twin

    async def ensure_twin(self, **kwargs: str) -> int:
        await asyncio.sleep(0)
        requests = await super().ensure_twin(**kwargs)
        await asyncio.sleep(0)
        return requests

    async def patch_thing(
        self, device_uuid: str, patch: Mapping[str, Any]
    ) -> int:
        await asyncio.sleep(0)
        attempts = await super().patch_thing(device_uuid, patch)
        await asyncio.sleep(0)
        fault = self.faults.get(len(self.patch_calls))
        if fault is not None:
            raise fault
        return attempts


async def test_identity_holds_at_every_loop_iteration_while_messages_arrive(
    repository: SchemaRepository,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """A reader on the loop evaluates the identity at EVERY loop iteration
    while messages arrive and the consumer is suspended inside Ditto calls
    that end in an update, in a ``DittoError``, in an exception raised by
    the PATCH call that is not a ``DittoError`` (a ``failed`` line since
    ADR 0011, item 8) and, for the very first message, in an event-write
    failure after the twin was updated (no line: a ``processing_errors``):
    the gap is 0 every time, and the reader does see a message in progress.
    An ``await`` inside one of the transitions of ``run`` (taken -> in
    progress, outcome -> finished) would show here."""
    ditto = _YieldingFaultyDittoClient(
        {
            2: DittoUnavailableError("down", attempts=3),  # -> failed
            3: RuntimeError("raised by the PATCH call"),  # -> failed (item 8)
        }
    )
    events = FailingEventLogger(tmp_path, failures=1)  # first line: no line
    service = _make_service(repository, ditto, events, metrics, queue_maxsize=3)
    readings: list[tuple[int, int]] = []
    probing = True

    async def probe() -> None:
        while probing:
            snapshot = metrics.snapshot()
            readings.append(
                (
                    accounting_gap(snapshot, service.queue_depth()),
                    snapshot["in_progress"],
                )
            )
            await asyncio.sleep(0)

    async def until_idle() -> None:
        for _ in range(10_000):  # loop iterations; a hang guard only
            if (
                metrics.snapshot()["in_progress"] == 0
                and service.queue_depth() == 0
            ):
                return
            await asyncio.sleep(0)
        raise AssertionError("the consumer never became idle")

    probe_task = asyncio.create_task(probe())
    run_task = asyncio.create_task(service.run())
    invalid = make_inbound(
        b"{", topic=topic_for(make_payload("smartwatch", seq=0))
    )
    # A burst larger than the queue: exactly three are queued, two dropped.
    for seq in range(5):
        service.submit(make_inbound(make_payload("smartwatch", seq=seq)))
    # Then one arrival per loop iteration, while the consumer is inside Ditto.
    for seq in range(5, 15):
        await asyncio.sleep(0)
        service.submit(
            invalid
            if seq % 3 == 0
            else make_inbound(make_payload("smartwatch", seq=seq))
        )
    await until_idle()
    # Room is certain now: one rejection and one more update.
    service.submit(invalid)
    service.submit(make_inbound(make_payload("smartwatch", seq=15)))
    await until_idle()
    probing = False
    await probe_task
    await service.stop()
    await run_task
    events.close()

    assert {gap for gap, _ in readings} == {0}
    assert {in_progress for _, in_progress in readings} == {0, 1}
    snapshot = metrics.snapshot()
    assert snapshot["received"] == 17
    assert snapshot["failed"] == 2
    assert snapshot["processing_errors"] == 1
    # Every PATCH call but the two faulted ones and the one whose line
    # failed to be written ended accepted.
    assert snapshot["accepted"] == len(ditto.patch_calls) - 3
    assert snapshot["accepted"] >= 2
    assert snapshot["rejected"] >= 1
    assert snapshot["dropped"] >= 2
    assert snapshot["duplicate"] == 0
    assert _gap(metrics, service) == 0
    failed = [
        record for record in read_events(tmp_path) if record["outcome"] == "failed"
    ]
    assert sorted(record["error"] for record in failed) == [
        "RuntimeError: raised by the PATCH call",
        "down",
    ]


async def test_stop_request_takes_no_queue_slot(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    """The stop request is a flag, not a queued marker (ADR 0011, item 13):
    the queue keeps its full capacity for deliveries and the gap is 0."""
    service = _make_service(repository, ditto, events, metrics, queue_maxsize=2)
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    await service.stop()
    service.submit(make_inbound(make_payload("smartwatch", seq=1)))
    snapshot = metrics.snapshot()
    assert (snapshot["received"], snapshot["dropped"]) == (2, 0)
    assert service.queue_depth() == 2
    assert _gap(metrics, service) == 0
    await service.run()  # exits at once: nothing is drained after a stop
    snapshot = metrics.snapshot()
    assert (snapshot["accepted"], snapshot["dropped"]) == (0, 0)
    assert service.queue_depth() == 2
    assert _gap(metrics, service) == 0


async def test_direct_process_call_touches_no_progress_counter(
    service: ControllerService, metrics: MetricsCounters
) -> None:
    """A direct ``process()`` call bypasses the queue, hence the accounting
    boundary: only ``submit`` and ``run`` move the progress counters."""
    await service.process(make_inbound(make_payload("smartwatch", seq=0)))
    snapshot = metrics.snapshot()
    assert snapshot["accepted"] == 1
    assert snapshot["received"] == 0
    assert snapshot["in_progress"] == 0
    assert snapshot["processing_errors"] == 0


async def test_message_submitted_after_the_stop_request_stays_in_queue_depth(
    service: ControllerService, metrics: MetricsCounters, tmp_path: Path
) -> None:
    """A message enqueued after the stop request during teardown is counted
    by ``submit`` and never taken: it stays in ``queue_depth``, left to the
    broker for redelivery."""
    await service.stop()
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    await service.run()  # sees the stop request first and ends
    snapshot = metrics.snapshot()
    assert snapshot["received"] == 1
    assert service.queue_depth() == 1
    assert snapshot["in_progress"] == 0
    assert snapshot["processing_errors"] == 0
    for outcome in ("accepted", "rejected", "duplicate", "failed"):
        assert snapshot[outcome] == 0
    assert _gap(metrics, service) == 0
    assert read_events(tmp_path) == []


def test_inbound_message_is_immutable() -> None:
    message = InboundMessage(topic="t", payload=b"x", received_monotonic_ns=1)
    with pytest.raises(AttributeError):
        message.topic = "other"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        message.mid = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ADR 0011: delivery identity, acknowledgement point, connection end, purge,
# skip, residual handler, stop order
# ---------------------------------------------------------------------------


def test_inbound_message_carries_the_delivery_identity_with_defaults() -> None:
    """Item 2: ``mid``, ``qos``, ``dup`` and ``connection`` travel with the
    delivery; the defaults keep every existing constructor call valid and
    describe a QoS 0 delivery, which is never acknowledged."""
    message = InboundMessage(topic="t", payload=b"x", received_monotonic_ns=1)
    assert (message.mid, message.qos, message.dup, message.connection) == (
        0,
        0,
        False,
        0,
    )
    stamped = InboundMessage(
        topic="t", payload=b"x", received_monotonic_ns=1, mid=7, qos=1, dup=True,
        connection=3,
    )
    assert (stamped.mid, stamped.qos, stamped.dup, stamped.connection) == (
        7,
        1,
        True,
        3,
    )


@pytest.mark.parametrize(
    ("label", "raw"),
    [
        ("deeply_nested_document", b"[" * 100_000),
        ("five_thousand_digit_integer", b'{"seq": ' + b"9" * 5_000 + b"}"),
    ],
    ids=["deeply_nested_document", "five_thousand_digit_integer"],
)
async def test_decode_failures_beyond_json_errors_are_rejected(
    service: ControllerService,
    ditto: FakeDittoClient,
    tmp_path: Path,
    metrics: MetricsCounters,
    label: str,
    raw: bytes,
) -> None:
    """Item 5: a ``RecursionError`` from a deeply nested document and the
    ``ValueError`` of the integer-digit limit end in a ``rejected`` line,
    with no Ditto call, like any other malformed payload."""
    topic = topic_for(make_payload("smartwatch"))
    written = await service.process(make_inbound(raw, topic=topic))
    assert written is True
    (record,) = read_events(tmp_path, "unknown")
    assert record["outcome"] == "rejected", label
    assert "invalid JSON payload" in record["error"]
    assert record["attempts"] == 0
    assert ditto.get_calls == [] and ditto.patch_calls == []
    assert metrics.snapshot()["rejected"] == 1


@pytest.mark.parametrize(
    ("label", "kwargs", "expected_error", "expected_attempts"),
    [
        ("get_twin_raises", {"fail_get": RuntimeError("twin body unusable")},
         "RuntimeError: twin body unusable", 0),
        ("patch_raises_non_ditto_error", {"fail_patch": ValueError("odd body")},
         "ValueError: odd body", 0),
    ],
)
async def test_unexpected_exception_before_the_patch_returned_is_a_failed_line(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    label: str,
    kwargs: dict[str, Any],
    expected_error: str,
    expected_attempts: int,
) -> None:
    """Item 8: any exception raised before the PATCH returned, in the Ditto
    exchange or elsewhere, ends in one ``failed`` line naming the exception,
    with the identity of the envelope and null ack and latency."""
    ditto = FakeDittoClient(**kwargs)
    service = _make_service(repository, ditto, events, metrics)
    payload = make_payload("smartwatch", seq=0)
    with caplog.at_level(logging.ERROR, logger="egw_controller.service"):
        written = await service.process(make_inbound(payload, received_monotonic_ns=42))
    assert written is True
    (record,) = read_events(tmp_path)
    assert record["outcome"] == "failed", label
    assert record["error"] == expected_error
    assert record["attempts"] == expected_attempts
    assert record["message_id"] == payload["message_id"]
    assert record["received_monotonic_ns"] == 42
    assert record["ditto_ack_monotonic_ns"] is None
    assert record["latency_ms"] is None
    assert metrics.snapshot()["failed"] == 1
    assert "unhandled error before the Ditto update" in caplog.text


async def test_residual_failed_line_carries_the_exceptions_attempts(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """An exception that carries a usable ``attempts`` keeps it; a negative
    or non-integer one is replaced by 0 (the event record requires >= 0)."""

    class CountingError(Exception):
        attempts = 2

    class OddError(Exception):
        attempts = -4

    for exc, expected in ((CountingError("x"), 2), (OddError("y"), 0)):
        ditto = FakeDittoClient(fail_patch=exc)
        service = _make_service(repository, ditto, events, metrics)
        await service.process(make_inbound(make_payload("smartwatch", seq=0)))
    assert [record["attempts"] for record in read_events(tmp_path)] == [2, 0]


async def test_exception_after_the_ditto_2xx_leaves_no_line_and_no_puback(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A1's fourth exception (T06): raised after the twin was updated, it
    propagates with no line (a ``failed`` line would misreport an applied
    twin), no PUBACK is requested and the connection is ended."""

    class RecordFails(DedupeCache):
        def record(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("after the 2xx")

    recorder = _BridgeRecorder()
    service = ControllerService(
        repository=repository,
        dedupe=RecordFails(),
        ditto=ditto,
        events=events,
        metrics=metrics,
        acknowledge=recorder.acknowledge,
        end_connection=recorder.end_connection,
    )
    message = make_inbound(make_payload("smartwatch", seq=0), mid=9, qos=1)
    service.submit(message)
    with caplog.at_level(logging.ERROR, logger="egw_controller.service"):
        await _run_until_idle_then_stop(service, metrics)
    assert len(ditto.patch_calls) == 1  # the twin was updated
    assert read_events(tmp_path) == []
    assert recorder.acks == []
    assert recorder.ends == [("no-outcome-line", message)]
    snapshot = metrics.snapshot()
    assert (snapshot["processing_errors"], snapshot["failed"]) == (1, 0)
    assert "unhandled error while processing message" in caplog.text


@pytest.mark.parametrize("outcome", ["accepted", "rejected", "duplicate", "failed"])
async def test_process_returns_true_only_once_the_line_is_written(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
    outcome: str,
) -> None:
    """Item 4: ``process`` reports a written line from a flag set after
    ``EventLogger.log`` returned, for every outcome; when ``log`` raises,
    no flag is set and the exception propagates."""
    ditto = FakeDittoClient()
    service = _make_service(repository, ditto, events, metrics)
    payload = make_payload("smartwatch", seq=0)
    if outcome == "duplicate":
        await service.process(make_inbound(payload))
    elif outcome == "rejected":
        payload = make_payload("smartwatch", seq=0, heart_rate_bpm=999)
    elif outcome == "failed":
        ditto.fail_patch = DittoUnavailableError("down", attempts=3)
    assert await service.process(make_inbound(payload)) is True
    assert read_events(tmp_path)[-1]["outcome"] == outcome

    failing = _make_service(
        repository, FakeDittoClient(), FailingEventLogger(tmp_path, failures=1),
        MetricsCounters(),
    )
    with pytest.raises(OSError):
        await failing.process(make_inbound(make_payload("smartwatch", seq=1)))


async def test_run_requests_the_puback_after_the_line_and_before_the_next_take(
    repository: SchemaRepository,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """T01, T02, T24 at the pipeline level: exactly one acknowledgement per
    QoS 1 delivery, requested after its line was written and before the
    next delivery is taken (receipt order; the next one still queued),
    across the four outcomes."""

    class FailsSecondPatch(FakeDittoClient):
        async def patch_thing(
            self, device_uuid: str, patch: Mapping[str, Any]
        ) -> int:
            if len(self.patch_calls) == 1:
                self.fail_patch = DittoUnavailableError("down", attempts=3)
            return await super().patch_thing(device_uuid, patch)

    ditto = FailsSecondPatch()
    order: list[tuple[str, int]] = []
    recorder = _BridgeRecorder()
    recorder.order = order
    with _OrderRecordingEventLogger(tmp_path, order) as events:
        service = ControllerService(
            repository=repository,
            dedupe=DedupeCache(),
            ditto=ditto,
            events=events,
            metrics=metrics,
            acknowledge=recorder.acknowledge,
            end_connection=recorder.end_connection,
        )
        recorder.queue_depth = service.queue_depth
        accepted = make_payload("smartwatch", seq=0)
        service.submit(make_inbound(accepted, mid=11, qos=1))  # accepted
        service.submit(make_inbound(accepted, mid=12, qos=1))  # duplicate
        service.submit(  # rejected
            make_inbound(make_payload("smartwatch", seq=1, heart_rate_bpm=999),
                         mid=13, qos=1)
        )
        service.submit(  # failed
            make_inbound(make_payload("smartwatch", seq=2), mid=14, qos=1)
        )
        await _run_until_idle_then_stop(service, metrics)
    assert [record["outcome"] for record in read_events(tmp_path)] == [
        "accepted",
        "duplicate",
        "rejected",
        "failed",
    ]
    assert [message.mid for message in recorder.acks] == [11, 12, 13, 14]
    assert order == [
        ("line", 0), ("ack", 11),
        ("line", 0), ("ack", 12),
        ("line", 1), ("ack", 13),
        ("line", 2), ("ack", 14),
    ]
    # The next delivery was still queued when each PUBACK was requested.
    assert recorder.depth_at_ack == [3, 2, 1, 0]
    assert recorder.ends == []


async def test_run_never_acknowledges_a_qos0_delivery(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """T09: a QoS 0 delivery obtains its line and no PUBACK."""
    recorder = _BridgeRecorder()
    service = _make_service(
        repository, ditto, events, metrics,
        acknowledge=recorder.acknowledge, end_connection=recorder.end_connection,
    )
    service.submit(make_inbound(make_payload("smartwatch", seq=0), mid=0, qos=0))
    await _run_until_idle_then_stop(service, metrics)
    assert [record["outcome"] for record in read_events(tmp_path)] == ["accepted"]
    assert recorder.acks == []
    assert recorder.ends == []


async def test_run_ends_the_connection_when_process_raises(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    metrics: MetricsCounters,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T03 at the pipeline level: a failed event write leaves no line, no
    PUBACK, and ends acknowledgement on the delivery's connection; the
    consumer stays alive and later deliveries still obtain their lines."""
    recorder = _BridgeRecorder()
    with FailingEventLogger(tmp_path, failures=1) as events:
        service = _make_service(
            repository, ditto, events, metrics,
            acknowledge=recorder.acknowledge,
            end_connection=recorder.end_connection,
        )
        first = make_inbound(make_payload("smartwatch", seq=0), mid=1, qos=1)
        second = make_inbound(make_payload("smartwatch", seq=1), mid=2, qos=1)
        service.submit(first)
        service.submit(second)
        with caplog.at_level(logging.ERROR, logger="egw_controller.service"):
            await _run_until_idle_then_stop(service, metrics)
    assert recorder.ends == [("no-outcome-line", first)]
    # The pipeline asks the bridge for the second one's PUBACK; whether it
    # is sent is the bridge's decision (acknowledgement is closed there).
    assert [message.mid for message in recorder.acks] == [2]
    assert [record["seq"] for record in read_events(tmp_path)] == [1]


async def test_cancelled_consumer_requests_no_puback(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """T04 and F3: cancellation with a delivery in flight: no line, no
    PUBACK, the connection ended with the cause ``consumer-cancelled`` and
    the delivery in progress named; the cancellation propagates and the
    service reports that it no longer consumes."""
    ditto = GatedDittoClient()
    recorder = _BridgeRecorder()
    service = _make_service(
        repository, ditto, events, metrics,
        acknowledge=recorder.acknowledge, end_connection=recorder.end_connection,
    )
    inbound = make_inbound(make_payload("smartwatch", seq=0), mid=1, qos=1)
    service.submit(inbound)
    assert service.consuming is False
    task = asyncio.create_task(service.run())
    await ditto.entered.wait()
    assert service.consuming is True
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert recorder.acks == []
    assert recorder.ends == [("consumer-cancelled", inbound)]
    assert read_events(tmp_path) == []
    assert service.consuming is False


async def test_idle_consumer_cancelled_ends_the_connection_with_no_delivery(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    """F3: a consumer cancelled while waiting ends the connection too (no
    delivery in progress), so the bridge halts rather than staying
    subscribed with nothing consuming."""
    recorder = _BridgeRecorder()
    service = _make_service(
        repository, ditto, events, metrics, end_connection=recorder.end_connection
    )
    task = asyncio.create_task(service.run())
    await asyncio.sleep(0)
    assert service.consuming is True
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert recorder.ends == [("consumer-cancelled", None)]
    assert service.consuming is False


async def test_a_retired_connection_never_applies_a_later_seq_before_the_resent_one(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """F1: seq 0 fails its PATCH and the write of its failed line also
    fails, so the connection is ended; the queued seq 1 of the same device
    must not be processed before the socket closes — it is skipped and left
    to the broker — so that the resent seq 0 is accepted, never read as a
    duplicate of a later seq applied ahead of it."""
    from egw_controller.ditto import DittoUnavailableError

    ditto = FakeDittoClient(
        fail_patch=DittoUnavailableError("ditto down", attempts=3, status=503)
    )
    failing_events = FailingEventLogger(tmp_path, failures=1)
    ends: list[tuple[str, InboundMessage | None]] = []

    def end_connection(cause: str, message: InboundMessage | None) -> int | None:
        ends.append((cause, message))
        return message.connection if message is not None else None

    acks: list[InboundMessage] = []
    service = _make_service(
        repository, ditto, failing_events, metrics,
        acknowledge=lambda m: acks.append(m) or True,
        end_connection=end_connection,
    )
    first = make_inbound(make_payload("smartwatch", seq=0), mid=1, qos=1, connection=1)
    second = make_inbound(make_payload("smartwatch", seq=1), mid=2, qos=1, connection=1)
    service.submit(first)
    service.submit(second)
    task = asyncio.create_task(service.run())
    await until(lambda: service.queue_depth() == 0 and metrics.snapshot()["in_progress"] == 0)
    # seq 0: PATCH failed, its failed line could not be written: the
    # connection is ended and retired; seq 1 is skipped, not applied.
    assert ends == [("no-outcome-line", first)]
    assert ditto.patch_calls == [] or all(
        patch["features"]["ingestion"]["properties"]["last_seq"] == 0
        for _, patch in ditto.patch_calls
    )
    assert metrics.snapshot()["dropped"] == 1
    assert acks == []
    # The socket closes and the broker resends both on the next connection.
    service.purge(1)
    ditto.fail_patch = None
    resent_first = make_inbound(
        make_payload("smartwatch", seq=0), mid=1, qos=1, dup=True, connection=2
    )
    resent_second = make_inbound(
        make_payload("smartwatch", seq=1), mid=2, qos=1, dup=True, connection=2
    )
    service.submit(resent_first)
    service.submit(resent_second)
    await until(lambda: len(acks) == 2)
    await service.stop()
    await task
    outcomes = [(r["seq"], r["outcome"]) for r in read_events(tmp_path)]
    assert outcomes == [(0, "accepted"), (1, "accepted")]
    assert [m.mid for m in acks] == [1, 2]
    assert [p["features"]["ingestion"]["properties"]["last_seq"] for _, p in ditto.patch_calls][-2:] == [0, 1]


def test_queue_overflow_ends_the_connection_after_counting_dropped(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    """Item 12 (T07): a delivery dropped on a full queue is counted
    ``received`` and ``dropped`` and then ends acknowledgement on its
    connection with the cause ``overflow``; it is never acknowledged."""
    ends: list[tuple[str, InboundMessage | None]] = []
    dropped_at_end: list[int] = []
    acks: list[InboundMessage] = []

    def end_connection(cause: str, message: InboundMessage | None) -> None:
        ends.append((cause, message))
        dropped_at_end.append(metrics.snapshot()["dropped"])

    def acknowledge(message: InboundMessage) -> bool:
        acks.append(message)
        return True

    service = _make_service(
        repository, ditto, events, metrics, queue_maxsize=1,
        acknowledge=acknowledge, end_connection=end_connection,
    )
    kept = make_inbound(make_payload("smartwatch", seq=0), mid=1, qos=1)
    overflowed = make_inbound(make_payload("smartwatch", seq=1), mid=2, qos=1)
    service.submit(kept)
    service.submit(overflowed)
    assert ends == [("overflow", overflowed)]
    assert dropped_at_end == [1]
    assert acks == []
    assert _gap(metrics, service) == 0


async def test_purge_removes_the_ended_connections_deliveries_in_order(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
) -> None:
    """Item 3 (T20): the purge drains the queue, keeps the other connections'
    deliveries in their order, counts each removed one as ``dropped`` (left
    for redelivery) and keeps the identity."""
    service = _make_service(repository, ditto, events, metrics)
    for mid, connection in ((1, 1), (2, 2), (3, 1), (4, 2), (5, 1)):
        service.submit(
            make_inbound(make_payload("smartwatch", seq=mid), mid=mid, qos=1,
                         connection=connection)
        )
    assert service.queue_depth() == 5
    service.purge(1)
    snapshot = metrics.snapshot()
    assert (service.queue_depth(), snapshot["dropped"], snapshot["received"]) == (
        2,
        3,
        5,
    )
    assert _gap(metrics, service) == 0
    remaining = [service._queue.get_nowait().mid for _ in range(2)]
    assert remaining == [2, 4]


async def test_run_skips_a_delivery_of_an_ended_connection_without_processing(
    repository: SchemaRepository,
    ditto: FakeDittoClient,
    events: EventLogger,
    tmp_path: Path,
) -> None:
    """Item 4: a delivery of an ended connection taken after the purge (it
    arrived late) is counted ``dropped`` with no line, no PUBACK and no
    ``processing_started``; one of the current connection is processed."""
    started: list[int] = []

    class SpyCounters(MetricsCounters):
        def processing_started(self) -> None:
            started.append(1)
            super().processing_started()

    metrics = SpyCounters()
    recorder = _BridgeRecorder()
    service = _make_service(
        repository, ditto, events, metrics,
        acknowledge=recorder.acknowledge, end_connection=recorder.end_connection,
    )
    service.purge(1)  # connection 1 ended; the current one is 2
    stale = make_inbound(make_payload("smartwatch", seq=0), mid=1, qos=1, connection=1)
    fresh = make_inbound(make_payload("smartwatch", seq=0), mid=1, qos=1, dup=True,
                         connection=2)
    service.submit(stale)
    service.submit(fresh)
    await _run_until_idle_then_stop(service, metrics)
    snapshot = metrics.snapshot()
    assert (snapshot["dropped"], snapshot["accepted"], snapshot["processing_errors"]) == (
        1,
        1,
        0,
    )
    assert started == [1]
    assert recorder.acks == [fresh]
    assert [record["seq"] for record in read_events(tmp_path)] == [0]
    assert _gap(metrics, service) == 0


async def test_stop_completes_the_delivery_in_progress_and_leaves_the_rest(
    repository: SchemaRepository,
    events: EventLogger,
    metrics: MetricsCounters,
    tmp_path: Path,
) -> None:
    """Item 13 (T28, pipeline half): after the stop request the delivery in
    progress is recorded and acknowledged, the consumer exits, and the rest
    of the queue stays unacknowledged for the next process."""
    ditto = GatedDittoClient()
    recorder = _BridgeRecorder()
    service = _make_service(
        repository, ditto, events, metrics,
        acknowledge=recorder.acknowledge, end_connection=recorder.end_connection,
    )
    first = make_inbound(make_payload("smartwatch", seq=0), mid=1, qos=1)
    second = make_inbound(make_payload("smartwatch", seq=1), mid=2, qos=1)
    service.submit(first)
    task = asyncio.create_task(service.run())
    await ditto.entered.wait()
    service.submit(second)
    await service.stop()
    ditto.release.set()
    await task
    assert [record["seq"] for record in read_events(tmp_path)] == [0]
    assert recorder.acks == [first]
    assert service.queue_depth() == 1
    assert recorder.ends == []
    assert _gap(metrics, service) == 0


class _ApplyingDittoClient(FakeDittoClient):
    """Fake twin that applies each PATCH's ingestion properties, so that a
    new process seeds its dedupe state from what the last one wrote."""

    async def patch_thing(
        self, device_uuid: str, patch: Mapping[str, Any]
    ) -> int:
        attempts = await super().patch_thing(device_uuid, patch)
        twin = self.twins[device_uuid]
        twin["features"]["ingestion"]["properties"].update(
            patch["features"]["ingestion"]["properties"]
        )
        return attempts


async def test_redelivery_after_a_simulated_restart(
    repository: SchemaRepository,
    events: EventLogger,
    tmp_path: Path,
) -> None:
    """T29: the broker resends the unacknowledged deliveries to the next
    process; those applied to the twin end ``duplicate``, the one not
    applied ends ``accepted``, ``last_seq`` never regresses and the
    per-device order is preserved."""
    ditto = _ApplyingDittoClient()
    first_process = _make_service(repository, ditto, events, MetricsCounters())
    for seq in range(3):
        await first_process.process(
            make_inbound(make_payload("smartwatch", seq=seq), mid=seq + 1, qos=1)
        )
    # The process died before the PUBACKs of seq 1 and 2 were written, and
    # seq 3 was published while it was away.
    second_process = _make_service(repository, ditto, events, MetricsCounters())
    for seq in (1, 2, 3):
        await second_process.process(
            make_inbound(make_payload("smartwatch", seq=seq), mid=seq + 1, qos=1,
                         dup=seq < 3)
        )
    outcomes = [record["outcome"] for record in read_events(tmp_path)]
    assert outcomes == ["accepted"] * 3 + ["duplicate", "duplicate", "accepted"]
    last_seqs = [
        patch["features"]["ingestion"]["properties"]["last_seq"]
        for _, patch in ditto.patch_calls
    ]
    assert last_seqs == [0, 1, 2, 3]
    assert ditto.twins[WATCH]["features"]["ingestion"]["properties"]["last_seq"] == 3
    assert ditto.twins[WATCH]["features"]["ingestion"]["properties"]["accepted_count"] == 4
