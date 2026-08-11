"""End-to-end pipeline tests for egw_controller.service with a fake Ditto client.

Covers all four outcomes (``accepted``/``rejected``/``duplicate``/``failed``),
first-contact twin creation, dedupe seeding from an existing twin, latency
semantics (ack and latency null unless accepted) and the metrics counters.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Iterator

import pytest

from egw_controller import schema as schema_module
from egw_controller import service as service_module
from egw_controller.dedupe import DedupeCache
from egw_controller.ditto import DittoUnavailableError
from egw_controller.events import EVENT_FIELDS, EventLogger
from egw_controller.metrics import MetricsCounters
from egw_controller.schema import SchemaRepository
from egw_controller.service import ControllerService, InboundMessage
from test_controller_helpers import (
    DEVICE_UUIDS,
    EGW_UUID_NAMESPACE,
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


def test_inbound_message_is_immutable() -> None:
    message = InboundMessage(topic="t", payload=b"x", received_monotonic_ns=1)
    with pytest.raises(AttributeError):
        message.topic = "other"  # type: ignore[misc]
