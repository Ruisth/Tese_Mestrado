"""FastAPI endpoint tests (CONTRACTS.md section 5) via httpx ASGITransport.

The service layer is faked: readiness flags and twin reads come from
``FakeDittoClient``/lambdas, so no MQTT broker or Ditto instance is needed.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator

import httpx
import pytest

from egw_controller.app import AppDeps, create_app
from egw_controller.config import Settings
from egw_controller.dedupe import DedupeCache
from egw_controller.ditto import DittoUnavailableError
from egw_controller.events import EventLogger
from egw_controller.metrics import MetricsCounters
from egw_controller.mqtt import MqttBridge
from egw_controller.schema import SchemaRepository
from egw_controller.service import ControllerService
from test_controller_helpers import (
    DEVICE_UUIDS,
    SCHEMA_DIR,
    FakeDittoClient,
    GatedDittoClient,
    accounting_gap,
    make_inbound,
    make_payload,
    make_raw_twin,
    topic_for,
)

WATCH = DEVICE_UUIDS["smartwatch"]


class FakeMonotonicClock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class MutableFlag:
    def __init__(self, value: bool = True) -> None:
        self.value = value

    def __call__(self) -> bool:
        return self.value


@pytest.fixture
def clock() -> FakeMonotonicClock:
    return FakeMonotonicClock()


@pytest.fixture
def metrics(clock: FakeMonotonicClock) -> MetricsCounters:
    return MetricsCounters(
        monotonic=clock,
        now=lambda: datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def ditto() -> FakeDittoClient:
    return FakeDittoClient(
        twins={WATCH: make_raw_twin(WATCH, last_seq=3, accepted_count=4)}
    )


@pytest.fixture
def mqtt_flag() -> MutableFlag:
    return MutableFlag(True)


@pytest.fixture
def deps(
    metrics: MetricsCounters, ditto: FakeDittoClient, mqtt_flag: MutableFlag
) -> AppDeps:
    return AppDeps(metrics=metrics, ditto=ditto, mqtt_connected=mqtt_flag)


@pytest.fixture
async def client(deps: AppDeps) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(deps)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        yield http


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /ready (200 only with MQTT connected AND Ditto reachable)
# ---------------------------------------------------------------------------


async def test_ready_200_when_mqtt_and_ditto_up(client: httpx.AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "mqtt_connected": True,
        "ditto_ready": True,
    }


async def test_ready_503_when_mqtt_down(
    client: httpx.AsyncClient, mqtt_flag: MutableFlag
) -> None:
    mqtt_flag.value = False
    response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["mqtt_connected"] is False
    assert body["ditto_ready"] is True


async def test_ready_503_when_ditto_down(
    client: httpx.AsyncClient, ditto: FakeDittoClient
) -> None:
    ditto.ready = False
    response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["mqtt_connected"] is True
    assert body["ditto_ready"] is False


async def test_ready_503_when_both_down(
    client: httpx.AsyncClient, ditto: FakeDittoClient, mqtt_flag: MutableFlag
) -> None:
    ditto.ready = False
    mqtt_flag.value = False
    assert (await client.get("/ready")).status_code == 503


# ---------------------------------------------------------------------------
# GET /twins/{device_id}
# ---------------------------------------------------------------------------


async def test_twin_read_is_normalized(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/twins/{WATCH}")
    assert response.status_code == 200
    body = response.json()
    assert body["device_uuid"] == WATCH
    assert body["thing_id"] == f"org.c2dta:{WATCH}"
    assert body["policy_id"] == f"org.c2dta:{WATCH}"
    assert body["device_type"] == "smartwatch"
    assert body["egw_id"] == "egw-01"
    assert body["schema_version"] == "1.0.0"
    assert body["ingestion"]["last_seq"] == 3
    assert body["ingestion"]["accepted_count"] == 4
    assert "ingestion" not in body["features"]


async def test_twin_read_accepts_full_thing_id(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/twins/org.c2dta:{WATCH}")
    assert response.status_code == 200
    assert response.json()["device_uuid"] == WATCH


async def test_twin_read_unknown_device_404(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/twins/{DEVICE_UUIDS['smart_ring']}")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "device_id",
    [
        "not-a-uuid",
        "1B46A1F5-9A3E-4C2D-8F6B-2D9E5A7C1B3D",  # uppercase is invalid
        "1b46a1f5-9a3e-1c2d-8f6b-2d9e5a7c1b3d",  # version nibble != 4
        "1b46a1f5-9a3e-4c2d-0f6b-2d9e5a7c1b3d",  # variant not in [89ab]
        "org.c2dta:not-a-uuid",
        "1b46a1f59a3e4c2d8f6b2d9e5a7c1b3d",  # missing dashes
        "1b46a1f5-9a3e-4c2d-8f6b-2d9e5a7c1b3d0",  # one char too long
    ],
)
async def test_twin_read_malformed_id_404_without_ditto_call(
    client: httpx.AsyncClient, ditto: FakeDittoClient, device_id: str
) -> None:
    response = await client.get(f"/twins/{device_id}")
    assert response.status_code == 404
    assert "invalid device id" in response.json()["detail"]
    # Malformed ids never reach Ditto: 502 stays reserved for real failures.
    assert ditto.get_calls == []


async def test_twin_read_ditto_unavailable_502(
    deps: AppDeps, ditto: FakeDittoClient
) -> None:
    ditto.fail_get = DittoUnavailableError("ditto down", attempts=3)
    app = create_app(deps)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        response = await http.get(f"/twins/{WATCH}")
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# GET /metrics
# ---------------------------------------------------------------------------


async def test_metrics_counts_and_uptime(
    client: httpx.AsyncClient,
    metrics: MetricsCounters,
    clock: FakeMonotonicClock,
) -> None:
    metrics.increment("accepted")
    metrics.increment("accepted")
    metrics.increment("rejected")
    metrics.increment("duplicate")
    metrics.increment("failed")
    clock.value = 160.5  # constructed at 100.0
    response = await client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    # The confirmation marker is additive (CONTRACTS 5, sprint P5): every
    # pre-existing field keeps its exact value and meaning.
    marker_ns = body.pop("monotonic_ns")
    wall_utc = body.pop("wall_utc")
    # So are the progress counters (CONTRACTS 5, 2026-09-18). increment()
    # alone, outside the queue, moves none of them.
    assert body.pop("received") == 0
    assert body.pop("in_progress") == 0
    assert body.pop("processing_errors") == 0
    # And the bridge fields (ADR 0011, item 14): no bridge here, so the
    # zero values.
    assert body.pop("mqtt_subscribed") is False
    assert body.pop("mqtt_connection") == 0
    assert body.pop("unacked") == 0
    assert body == {
        "accepted": 2,
        "rejected": 1,
        "duplicate": 1,
        "failed": 1,
        "dropped": 0,
        "queue_depth": 0,
        "started_at": "2026-08-07T12:00:00.000Z",
        "uptime_s": 60.5,
    }
    assert isinstance(marker_ns, int)
    # The fixture pins `now`; wall_utc is that instant in RFC 3339 UTC.
    assert wall_utc == "2026-08-07T12:00:00.000Z"


# ---------------------------------------------------------------------------
# GET /metrics confirmation marker (CONTRACTS 5, sprint P5, report 5.2)
# ---------------------------------------------------------------------------


class FakeMonotonicNs:
    """Injectable time.monotonic_ns() with an explicit call counter."""

    def __init__(self, value: int = 1_000_000_000) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        return self.value


async def test_metrics_confirmation_marker_read_at_request_time(
    ditto: FakeDittoClient,
) -> None:
    """``monotonic_ns`` is read WHILE the request is handled, not frozen at
    construction: the harness needs the instant the measured run ended, and
    it must advance between polls."""
    monotonic_ns = FakeMonotonicNs(5_000_000_000)
    metrics = MetricsCounters(
        monotonic=FakeMonotonicClock(),
        now=lambda: datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc),
        monotonic_ns=monotonic_ns,
    )
    assert monotonic_ns.calls == 0  # nothing read at construction
    app = create_app(
        AppDeps(metrics=metrics, ditto=ditto, mqtt_connected=lambda: True)
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        first = (await http.get("/metrics")).json()
        assert first["monotonic_ns"] == 5_000_000_000
        monotonic_ns.value = 65_000_000_000  # 60 s later, in nanoseconds
        second = (await http.get("/metrics")).json()
    assert second["monotonic_ns"] == 65_000_000_000
    assert second["monotonic_ns"] - first["monotonic_ns"] == 60 * 1_000_000_000
    assert monotonic_ns.calls == 2


async def test_metrics_marker_uses_the_process_monotonic_clock_by_default(
    client: httpx.AsyncClient,
) -> None:
    """Without injection the marker is the real ``time.monotonic_ns()`` of
    the controller process — the SAME clock domain as the events.jsonl
    ``received_monotonic_ns`` / ``ditto_ack_monotonic_ns`` stamps, which is
    the whole point of the marker (report 5.2)."""
    before = time.monotonic_ns()
    body = (await client.get("/metrics")).json()
    after = time.monotonic_ns()
    assert before <= body["monotonic_ns"] <= after


async def test_metrics_marker_does_not_touch_latency_fields(
    client: httpx.AsyncClient,
) -> None:
    """The marker is an end-of-run anchor, never a latency measurement:
    /metrics exposes no latency field and the counters stay the contract
    four plus the operational extras and the progress counters
    (CONTRACTS 5/9)."""
    body = (await client.get("/metrics")).json()
    assert set(body) == {
        "accepted",
        "rejected",
        "duplicate",
        "failed",
        "dropped",
        "received",
        "in_progress",
        "processing_errors",
        "queue_depth",
        "started_at",
        "uptime_s",
        "monotonic_ns",
        "wall_utc",
        "mqtt_subscribed",
        "mqtt_connection",
        "unacked",
    }
    assert not [key for key in body if "latency" in key]


# ---------------------------------------------------------------------------
# GET /metrics bridge fields (ADR 0011, item 14)
# ---------------------------------------------------------------------------


async def test_metrics_bridge_fields_default_to_not_subscribed_and_zero(
    client: httpx.AsyncClient,
) -> None:
    """Without a bridge the three additive fields are present with their
    zero values, typed as the contract states: a boolean and two
    non-negative integers, never absent."""
    body = (await client.get("/metrics")).json()
    assert body["mqtt_subscribed"] is False
    assert type(body["mqtt_connection"]) is int and body["mqtt_connection"] == 0
    assert type(body["unacked"]) is int and body["unacked"] == 0
    assert accounting_gap(body) == 0  # unacked is not a term of the identity


async def test_metrics_reads_the_bridge_state_live(
    metrics: MetricsCounters, ditto: FakeDittoClient
) -> None:
    state = {"mqtt_subscribed": True, "mqtt_connection": 3, "unacked": 7}
    reads = 0

    def bridge_state() -> dict[str, Any]:
        nonlocal reads
        reads += 1
        return dict(state)

    app = create_app(
        AppDeps(
            metrics=metrics,
            ditto=ditto,
            mqtt_connected=lambda: True,
            bridge_state=bridge_state,
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        body = (await http.get("/metrics")).json()
        assert (body["mqtt_subscribed"], body["mqtt_connection"], body["unacked"]) == (
            True,
            3,
            7,
        )
        state.update(mqtt_subscribed=False, mqtt_connection=4, unacked=0)
        body = (await http.get("/metrics")).json()
        assert (body["mqtt_subscribed"], body["mqtt_connection"], body["unacked"]) == (
            False,
            4,
            0,
        )
    assert reads == 2  # read at request time, once per response
    # The bridge fields never shadow a counter or the queue depth.
    assert body["queue_depth"] == 0
    assert body["received"] == 0


async def test_metrics_wall_utc_is_rfc3339_zulu(client: httpx.AsyncClient) -> None:
    """``wall_utc`` is the same instant on the wall clock, RFC 3339 UTC with
    a Z suffix and millisecond resolution (CONTRACTS 5)."""
    body = (await client.get("/metrics")).json()
    wall_utc = body["wall_utc"]
    assert wall_utc.endswith("Z")
    parsed = datetime.fromisoformat(wall_utc.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


async def test_metrics_reports_dropped_and_live_queue_depth(
    metrics: MetricsCounters, ditto: FakeDittoClient
) -> None:
    depth = 7
    deps = AppDeps(
        metrics=metrics,
        ditto=ditto,
        mqtt_connected=lambda: True,
        queue_depth=lambda: depth,
    )
    metrics.increment_dropped()
    metrics.increment_dropped()
    app = create_app(deps)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        body = (await http.get("/metrics")).json()
        assert body["dropped"] == 2
        assert body["queue_depth"] == 7
        # The four contract counters are untouched by drops.
        assert body["accepted"] == 0
        assert body["rejected"] == 0
        assert body["duplicate"] == 0
        assert body["failed"] == 0
        depth = 3  # live read on each request, not a construction-time copy
        assert (await http.get("/metrics")).json()["queue_depth"] == 3


def test_metrics_rejects_unknown_outcome(metrics: MetricsCounters) -> None:
    with pytest.raises(ValueError):
        metrics.increment("lost")
    # "dropped" is not an event outcome; it has its own increment method.
    with pytest.raises(ValueError):
        metrics.increment("dropped")


# ---------------------------------------------------------------------------
# GET /metrics progress counters and the accounting identity (CONTRACTS 5)
# ---------------------------------------------------------------------------

PROGRESS_FIELDS = ("received", "in_progress", "processing_errors")


class MinimalPahoClient:
    """The few paho client members ``MqttBridge`` touches (no network)."""

    def __init__(self) -> None:
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.on_message: Any = None
        self.on_subscribe: Any = None
        self.on_socket_close: Any = None
        self.acks: list[tuple[int, int]] = []

    def connect_async(self, host: str, port: int, keepalive: int = 60) -> None:
        return None

    def loop_start(self) -> None:
        return None

    def loop_stop(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def ack(self, mid: int, qos: int) -> int:
        self.acks.append((mid, qos))
        return 0


def make_real_service(
    ditto: FakeDittoClient,
    events: EventLogger,
    metrics: MetricsCounters,
    *,
    queue_maxsize: int = 100,
) -> ControllerService:
    return ControllerService(
        repository=SchemaRepository(SCHEMA_DIR),
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
        queue_maxsize=queue_maxsize,
    )


async def test_metrics_progress_counters_are_additive_integers(
    client: httpx.AsyncClient,
) -> None:
    """The three progress counters are non-negative JSON integers and every
    pre-existing field keeps its type (additive change, CONTRACTS 5)."""
    body = (await client.get("/metrics")).json()
    for name in PROGRESS_FIELDS:
        assert type(body[name]) is int
        assert body[name] >= 0
    for name in ("accepted", "rejected", "duplicate", "failed", "dropped"):
        assert type(body[name]) is int
    assert type(body["queue_depth"]) is int
    assert type(body["monotonic_ns"]) is int
    assert isinstance(body["uptime_s"], float)
    assert isinstance(body["started_at"], str)
    assert isinstance(body["wall_utc"], str)
    assert accounting_gap(body) == 0


async def test_metrics_reports_in_progress_while_ditto_is_slow(
    metrics: MetricsCounters, tmp_path: Path
) -> None:
    """One reading tells busy from idle: a message held by a slow Ditto
    (retries and back-off included) is outside ``queue_depth`` and outside
    every outcome counter, and ``in_progress`` shows it."""
    ditto = GatedDittoClient()
    with EventLogger(tmp_path) as events:
        service = make_real_service(ditto, events, metrics)
        app = create_app(
            AppDeps(
                metrics=metrics,
                ditto=ditto,
                mqtt_connected=lambda: True,
                queue_depth=service.queue_depth,
            )
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as http:
            task = asyncio.create_task(service.run())
            service.submit(make_inbound(make_payload("smartwatch", seq=0)))
            await ditto.entered.wait()
            busy = (await http.get("/metrics")).json()

            ditto.release.set()
            await service.stop()
            await task
            idle = (await http.get("/metrics")).json()

    assert (busy["in_progress"], busy["queue_depth"], busy["accepted"]) == (1, 0, 0)
    assert busy["received"] == 1
    assert accounting_gap(busy) == 0
    assert (idle["in_progress"], idle["queue_depth"], idle["accepted"]) == (0, 0, 1)
    assert idle["received"] == 1
    assert idle["processing_errors"] == 0
    assert accounting_gap(idle) == 0


def test_metrics_endpoint_runs_on_the_event_loop(deps: AppDeps) -> None:
    """The handler must stay a coroutine: a plain function would be run in a
    thread pool, and a reader on another thread is not guaranteed the
    identity (see the module docstring of ``metrics.py``). A structural
    guard on the shape of the route, not a behaviour test: the handler was a
    coroutine before the progress counters existed, so it passes there too."""
    app = create_app(deps)
    (route,) = [
        route for route in app.routes if getattr(route, "path", None) == "/metrics"
    ]
    assert inspect.iscoroutinefunction(route.endpoint)


def test_metrics_handler_never_gives_the_loop_back(deps: AppDeps) -> None:
    """One response is one snapshot only if nothing else runs on the loop
    between ``snapshot()`` and ``queue_depth()``: driven by hand, the handler
    coroutine must finish on its first step, without suspending once."""
    app = create_app(deps)
    (route,) = [
        route for route in app.routes if getattr(route, "path", None) == "/metrics"
    ]
    coroutine = route.endpoint()
    try:
        with pytest.raises(StopIteration) as finished:
            coroutine.send(None)
    finally:
        coroutine.close()
    body = finished.value.value
    assert body["queue_depth"] == 0
    assert accounting_gap(body) == 0


async def test_every_metrics_response_is_one_snapshot_under_a_second_thread(
    metrics: MetricsCounters, tmp_path: Path
) -> None:
    """A real second thread fires the MQTT callback, with messages that are
    rejected and messages that go through Ditto, while ``/metrics`` is
    polled. Pinned here: every response satisfies the identity under that
    pressure (no ``await`` inside a transition of the consumer or between
    ``snapshot()`` and ``queue_depth()`` in the handler); a response does
    show the message held by Ditto, the first one being held until a
    response has shown it; and ``submit``, the counting point of
    ``received`` and ``dropped``, only ever runs on the loop thread, the
    bridge having handed each message over. The bridge's own ``unacked``
    is read in the same stretch; it is not a term of the identity."""
    total = 3000
    paho = MinimalPahoClient()
    ditto = GatedDittoClient()
    loop_thread = threading.get_ident()
    submit_threads: set[int] = set()
    with EventLogger(tmp_path) as events:
        service = make_real_service(ditto, events, metrics, queue_maxsize=50)

        def submit(message: Any) -> None:
            submit_threads.add(threading.get_ident())
            service.submit(message)

        bridge = MqttBridge(
            Settings.from_env({"EGW_MQTT_TLS": "false"}),
            submit,
            client=paho,  # type: ignore[arg-type]
        )
        app = create_app(
            AppDeps(
                metrics=metrics,
                ditto=ditto,
                mqtt_connected=lambda: True,
                queue_depth=service.queue_depth,
                bridge_state=bridge.state,
            )
        )
        # Invalid JSON: rejected with no Ditto call and no retries. QoS 0:
        # the pipeline requests no PUBACK (the bridge is not wired to it).
        invalid = SimpleNamespace(
            topic="c2dt/egw-01/x/telemetry", payload=b"{", mid=0, qos=0, dup=False
        )

        def valid(seq: int) -> SimpleNamespace:
            payload = make_payload("smartwatch", seq=seq)
            return SimpleNamespace(
                topic=topic_for(payload),
                payload=json.dumps(payload).encode("utf-8"),
                mid=seq + 1,
                qos=1,
                dup=False,
            )

        # Every tenth message goes through Ditto, the very first included.
        messages = [
            valid(index // 10) if index % 10 == 0 else invalid
            for index in range(total)
        ]

        producer_errors: list[BaseException] = []

        def fire() -> None:
            try:
                for message in messages:
                    paho.on_message(paho, None, message)
            except BaseException as exc:  # noqa: BLE001 - reported below
                producer_errors.append(exc)

        producer = threading.Thread(target=fire, daemon=True)
        task = asyncio.create_task(service.run())
        bridge.start(asyncio.get_running_loop())
        last_received = 0
        seen_in_progress: set[int] = set()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as http:
            producer.start()
            # Bounded by the message count; the deadline only turns a hang
            # into a failure.
            deadline = time.monotonic() + 120.0
            while True:
                body = (await http.get("/metrics")).json()
                # Every response, not only the last one.
                assert accounting_gap(body) == 0, body
                assert type(body["unacked"]) is int and body["unacked"] >= 0
                assert submit_threads <= {loop_thread}
                # A callback that failed on the producer thread would
                # otherwise only show as the deadline below.
                assert producer_errors == []
                assert body["received"] >= last_received
                last_received = body["received"]
                seen_in_progress.add(body["in_progress"])
                if body["in_progress"] == 1:
                    # Ditto held the first message until a response showed it.
                    ditto.release.set()
                if (
                    body["received"] == total
                    and body["in_progress"] == 0
                    and body["queue_depth"] == 0
                ):
                    break
                assert time.monotonic() < deadline, body
                await asyncio.sleep(0)
        producer.join()
        bridge.stop()
        await service.stop()
        await task

    final = body
    assert seen_in_progress == {0, 1}
    assert submit_threads == {loop_thread}
    assert final["accepted"] >= 1
    assert final["accepted"] + final["rejected"] + final["dropped"] == total
    assert final["processing_errors"] == 0
    assert final["duplicate"] == final["failed"] == 0
    # The QoS 1 deliveries were handed to the client and, the pipeline not
    # being wired to the bridge here, never acknowledged.
    assert final["unacked"] == total // 10
    assert paho.acks == []


# ---------------------------------------------------------------------------
# create_app_from_env: wiring and the stop order (ADR 0011, items 3 and 13)
# ---------------------------------------------------------------------------


class _RecordingBridge:
    """Stands in for ``MqttBridge`` in ``create_app_from_env``."""

    instances: list["_RecordingBridge"] = []
    order: list[str] = []

    def __init__(self, settings: Settings, submit: Any, **kwargs: Any) -> None:
        self.settings = settings
        self.submit = submit
        self.kwargs = kwargs
        self.stop_thread: int | None = None
        self.acked: list[Any] = []
        self.ends: list[tuple[str, Any]] = []
        _RecordingBridge.instances.append(self)

    def start(self, loop: Any = None) -> None:
        _RecordingBridge.order.append("bridge.start")

    def stop(self) -> None:
        self.stop_thread = threading.get_ident()
        _RecordingBridge.order.append("bridge.stop")

    def ack(self, delivery: Any) -> bool:
        self.acked.append(delivery)
        return True

    def end_connection(self, cause: str, identity: Any) -> int | None:
        self.ends.append((cause, identity))
        return getattr(identity, "connection", None) if identity is not None else 1

    def state(self) -> dict[str, Any]:
        return {"mqtt_subscribed": True, "mqtt_connection": 2, "unacked": 5}

    @property
    def connected(self) -> bool:
        return True


async def test_a_cancelled_consumer_leaves_the_app_not_ready_and_shutdown_still_cleans_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F3: when the pipeline task is cancelled while the app runs, the
    connection is ended with the cause ``consumer-cancelled``, ``/ready`` is
    503 although the bridge says it is subscribed, and the lifespan's shutdown
    still stops the bridge, closes Ditto and closes the event log, in that
    order, without raising."""
    import egw_controller.app as app_module
    from egw_controller.ditto import DittoClient

    order: list[str] = []

    class TaskRecordingService(ControllerService):
        instances: list["TaskRecordingService"] = []

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.task: asyncio.Task[None] | None = None
            TaskRecordingService.instances.append(self)

        async def run(self) -> None:
            self.task = asyncio.current_task()
            await super().run()

    class RecordingEvents(EventLogger):
        def close(self) -> None:
            order.append("events.close")
            super().close()

    class RecordingDitto(DittoClient):
        async def aclose(self) -> None:
            order.append("ditto.aclose")
            await super().aclose()

    monkeypatch.setattr("egw_controller.mqtt.MqttBridge", _RecordingBridge)
    monkeypatch.setattr(app_module, "ControllerService", TaskRecordingService)
    monkeypatch.setattr(app_module, "EventLogger", RecordingEvents)
    monkeypatch.setattr(app_module, "DittoClient", RecordingDitto)
    monkeypatch.setattr(app_module, "configure_logging", lambda: None)
    monkeypatch.setenv("EGW_MQTT_TLS", "false")
    monkeypatch.setenv("EGW_SCHEMA_DIR", str(SCHEMA_DIR))
    monkeypatch.setenv("EGW_EVENT_LOG_DIR", str(tmp_path))
    _RecordingBridge.instances.clear()
    _RecordingBridge.order = order
    TaskRecordingService.instances.clear()

    app = app_module.create_app_from_env()
    (bridge,) = _RecordingBridge.instances
    (service,) = TaskRecordingService.instances
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0)
        assert service.task is not None and service.consuming is True
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as http:
            # Ditto is not reachable here, so /ready is 503 throughout; the
            # MQTT half of readiness is what the consumer's state changes.
            assert (await http.get("/ready")).json()["mqtt_connected"] is True
            service.task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await service.task
            assert service.consuming is False
            assert bridge.ends == [("consumer-cancelled", None)]
            # The bridge still claims a subscription; readiness needs the
            # consumer as well, so the MQTT half reports not connected.
            ready = await http.get("/ready")
            assert ready.status_code == 503
            assert ready.json()["mqtt_connected"] is False
        order.clear()
    assert order == ["bridge.stop", "ditto.aclose", "events.close"]


async def test_create_app_from_env_wires_the_bridge_and_stops_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The bridge receives ``submit`` and ``purge``; the service receives
    the bridge's ``ack`` and ``end_connection``; ``/metrics`` reads the
    bridge state; and the lifespan stops in the order of the Decision: the
    consumer first (its PUBACK queued), then the bridge off the loop thread
    (the DISCONNECT last, the join never blocking the loop), then Ditto and
    the event log."""
    import egw_controller.app as app_module
    from egw_controller.ditto import DittoClient

    order: list[str] = []

    class RecordingService(ControllerService):
        instances: list["RecordingService"] = []

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.kwargs = kwargs
            RecordingService.instances.append(self)

        async def run(self) -> None:
            await super().run()
            order.append("pipeline.exit")

        async def stop(self) -> None:
            order.append("service.stop")
            await super().stop()

    class RecordingEvents(EventLogger):
        def close(self) -> None:
            order.append("events.close")
            super().close()

    class RecordingDitto(DittoClient):
        async def aclose(self) -> None:
            order.append("ditto.aclose")
            await super().aclose()

    monkeypatch.setattr("egw_controller.mqtt.MqttBridge", _RecordingBridge)
    monkeypatch.setattr(app_module, "ControllerService", RecordingService)
    monkeypatch.setattr(app_module, "EventLogger", RecordingEvents)
    monkeypatch.setattr(app_module, "DittoClient", RecordingDitto)
    monkeypatch.setattr(app_module, "configure_logging", lambda: None)
    monkeypatch.setenv("EGW_MQTT_TLS", "false")
    monkeypatch.setenv("EGW_SCHEMA_DIR", str(SCHEMA_DIR))
    monkeypatch.setenv("EGW_EVENT_LOG_DIR", str(tmp_path))
    _RecordingBridge.instances.clear()
    _RecordingBridge.order = order
    RecordingService.instances.clear()

    app = app_module.create_app_from_env()
    (bridge,) = _RecordingBridge.instances
    (service,) = RecordingService.instances
    assert service.kwargs["acknowledge"] == bridge.ack
    assert service.kwargs["end_connection"] == bridge.end_connection
    loop_thread = threading.get_ident()
    async with app.router.lifespan_context(app):
        assert order == ["bridge.start"]
        # The bridge's submit and purge reach the service.
        bridge.submit(make_inbound(make_payload("smartwatch", seq=0), connection=1))
        assert service.queue_depth() == 1
        bridge.kwargs["purge"](1)
        assert service.queue_depth() == 0
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as http:
            body = (await http.get("/metrics")).json()
        assert (body["mqtt_subscribed"], body["mqtt_connection"], body["unacked"]) == (
            True,
            2,
            5,
        )
        assert body["dropped"] == 1  # the purged delivery
        order.clear()
    assert order == [
        "service.stop",
        "pipeline.exit",
        "bridge.stop",
        "ditto.aclose",
        "events.close",
    ]
    assert bridge.stop_thread is not None and bridge.stop_thread != loop_thread
