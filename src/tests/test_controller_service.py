"""End-to-end pipeline tests for egw_controller.service with a fake Ditto client.

Covers all four outcomes (``accepted``/``rejected``/``duplicate``/``failed``),
first-contact twin creation, dedupe seeding from an existing twin, latency
semantics (ack and latency null unless accepted) and the metrics counters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from egw_controller.dedupe import DedupeCache
from egw_controller.ditto import DittoUnavailableError
from egw_controller.events import EVENT_FIELDS, EventLogger
from egw_controller.metrics import MetricsCounters
from egw_controller.schema import SchemaRepository
from egw_controller.service import ControllerService, InboundMessage
from test_controller_helpers import (
    DEVICE_UUIDS,
    RUN_ID,
    SCHEMA_DIR,
    FakeClock,
    FakeDittoClient,
    make_inbound,
    make_message_id,
    make_payload,
    make_raw_twin,
    read_events,
    topic_for,
)

WATCH = DEVICE_UUIDS["smartwatch"]


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
    # Twin already exists with last_seq=5: a replayed seq must be duplicate
    # without recreating the twin, and the next seq resumes the count.
    last_id = make_message_id(RUN_ID, WATCH, 5)
    ditto.twins[WATCH] = make_raw_twin(
        WATCH, last_message_id=last_id, last_seq=5, accepted_count=6
    )

    await service.process(make_inbound(make_payload("smartwatch", seq=5)))
    await service.process(make_inbound(make_payload("smartwatch", seq=6)))

    assert ditto.ensure_calls == []  # twin existed; never recreated
    (device_uuid, patch) = ditto.patch_calls[0]
    assert device_uuid == WATCH
    assert patch["features"]["ingestion"]["properties"]["last_seq"] == 6
    assert patch["features"]["ingestion"]["properties"]["accepted_count"] == 7

    records = read_events(tmp_path)
    assert [record["outcome"] for record in records] == ["duplicate", "accepted"]


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
    # fresh message_id but non-increasing seq
    stale = make_payload(
        "smartwatch", seq=4, message_id=make_message_id(RUN_ID, WATCH, 400)
    )
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


async def test_run_drains_queue_until_stop(
    service: ControllerService, tmp_path: Path, metrics: MetricsCounters
) -> None:
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    service.submit(make_inbound(make_payload("smartwatch", seq=1)))
    await service.stop()  # sentinel queued after the two messages
    await service.run()
    assert len(read_events(tmp_path)) == 2
    assert metrics.snapshot()["accepted"] == 2


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


def test_queue_full_drops_message(
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
    service.submit(make_inbound(make_payload("smartwatch", seq=0)))
    # Queue is full now: the second submit is dropped without raising.
    service.submit(make_inbound(make_payload("smartwatch", seq=1)))
    assert service._queue.qsize() == 1


def test_inbound_message_is_immutable() -> None:
    message = InboundMessage(topic="t", payload=b"x", received_monotonic_ns=1)
    with pytest.raises(AttributeError):
        message.topic = "other"  # type: ignore[misc]
