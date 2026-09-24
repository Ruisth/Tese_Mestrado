"""Tests for egw_controller.mqtt with a fake paho client (no network).

Verifies the latency start point (``received_monotonic_ns`` captured in the
callback at message arrival), the threadsafe bridge into the asyncio queue,
the QoS 1 subscription to the topic filter, the SUBACK-gated readiness
(connected only after the broker grants the subscription at QoS 1), the
TLS/credential wiring of the self-built paho client (persistent session and
manual acknowledgement in the constructor), the counting point of the
``received`` progress counter relative to the bridge (CONTRACTS 5), and,
for ADR 0011: the delivery identity stamped on the network thread, the
connection identity advanced in ``on_socket_close`` under the bridge lock,
``ack`` sending only for the current connection while acknowledgement is
open, the purge scheduled onto the loop, the connection end driven by the
supervisor thread with its recorded and bounded repetition, the
``unacked`` gauge and the graceful stop order.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from egw_controller.config import Settings
from egw_controller.dedupe import DedupeCache
from egw_controller.events import ControllerEvent, EventLogger
from egw_controller.metrics import MetricsCounters
from egw_controller.mqtt import MqttBridge
from egw_controller.schema import SchemaRepository
from egw_controller.service import ControllerService, InboundMessage
from test_controller_helpers import (
    DEVICE_UUIDS,
    SCHEMA_DIR,
    FailingEventLogger,
    FakeClock,
    FakeDittoClient,
    GatedDittoClient,
    accounting_gap,
    make_payload,
    read_events,
    topic_for,
    until,
)

WATCH = DEVICE_UUIDS["smartwatch"]
MQTT_LOGGER = "egw_controller.mqtt"


class FakePahoClient:
    """Records the calls MqttBridge makes on the paho client, in order."""

    def __init__(self) -> None:
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.on_message: Any = None
        self.on_subscribe: Any = None
        self.on_socket_close: Any = None
        self.subscriptions: list[tuple[str, int]] = []
        self.connect_async_calls: list[tuple[str, int, int]] = []
        self.acks: list[tuple[int, int]] = []
        self.calls: list[str] = []
        self.ack_result = 0  # MQTT_ERR_SUCCESS
        self.loop_started = False
        self.loop_stopped = False
        self.disconnect_called = False
        self.subscribe_result = 0  # MQTT_ERR_SUCCESS
        self.last_mid: int | None = None
        self._mid = 0

    def subscribe(self, topic: str, qos: int = 0) -> tuple[int, int | None]:
        self.subscriptions.append((topic, qos))
        if self.subscribe_result != 0:
            return (self.subscribe_result, None)
        self._mid += 1
        self.last_mid = self._mid
        return (self.subscribe_result, self.last_mid)

    def connect_async(self, host: str, port: int, keepalive: int = 60) -> None:
        self.connect_async_calls.append((host, port, keepalive))
        self.calls.append("connect_async")

    def loop_start(self) -> None:
        self.loop_started = True
        self.calls.append("loop_start")

    def loop_stop(self) -> None:
        self.loop_stopped = True
        self.calls.append("loop_stop")

    def disconnect(self) -> None:
        self.disconnect_called = True
        self.calls.append("disconnect")

    def ack(self, mid: int, qos: int) -> int:
        self.acks.append((mid, qos))
        self.calls.append(f"ack:{mid}")
        return self.ack_result

    def count(self, call: str) -> int:
        return self.calls.count(call)


def _no_backoff(occurrence: int) -> float:
    return 0.0


def make_bridge(
    clock: FakeClock | None = None,
    *,
    purge: Callable[[int], None] | None = None,
    end_bound: int = 10,
) -> tuple[MqttBridge, FakePahoClient, list[InboundMessage]]:
    settings = Settings.from_env({"EGW_MQTT_TLS": "false"})
    received: list[InboundMessage] = []
    fake_client = FakePahoClient()
    bridge = MqttBridge(
        settings,
        received.append,
        monotonic_ns=clock or FakeClock(),
        client=fake_client,  # type: ignore[arg-type]
        purge=purge,
        backoff_s=_no_backoff,
        end_bound=end_bound,
    )
    return bridge, fake_client, received


def connect_ok(client: FakePahoClient, *, session_present: bool = False) -> None:
    """Fire on_connect with a successful CONNACK (subscribe is requested)."""
    reason_code = SimpleNamespace(is_failure=False)
    flags = SimpleNamespace(session_present=session_present)
    client.on_connect(client, None, flags, reason_code, None)


def suback(
    client: FakePahoClient, value: int = 1, mid: int | None = None
) -> None:
    """Fire on_subscribe with one granted/denied reason code."""
    reason_code = SimpleNamespace(value=value)
    client.on_subscribe(
        client,
        None,
        mid if mid is not None else client.last_mid,
        [reason_code],
        None,
    )


def connect_and_grant(client: FakePahoClient, granted_qos: int = 1) -> None:
    connect_ok(client)
    suback(client, value=granted_qos)


def socket_close(client: FakePahoClient) -> None:
    """Fire on_socket_close as paho does on every close path."""
    client.on_socket_close(client, None, None)


def message_for(
    payload: Any = b'{"seq": 0}',
    *,
    topic: str | None = None,
    mid: int = 1,
    qos: int = 1,
    dup: bool = False,
) -> SimpleNamespace:
    """A paho ``MQTTMessage`` stand-in with the delivery identity fields."""
    if not isinstance(payload, (bytes, bytearray)):
        topic = topic or topic_for(payload)
        payload = json.dumps(payload).encode("utf-8")
    return SimpleNamespace(
        topic=topic or f"c2dt/egw-01/{WATCH}/telemetry",
        payload=payload,
        mid=mid,
        qos=qos,
        dup=dup,
    )


def deliver(client: FakePahoClient, message: SimpleNamespace) -> None:
    client.on_message(client, None, message)


def _ends(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [
        record.context  # type: ignore[attr-defined]
        for record in caplog.records
        if record.getMessage() == "MQTT connection ended by the controller"
    ]


# ---------------------------------------------------------------------------
# start / stop, subscription and readiness
# ---------------------------------------------------------------------------


async def test_start_connects_and_runs_network_loop() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    assert client.connect_async_calls == [("localhost", 8883, 60)]
    assert client.loop_started is True
    supervisor = [
        thread for thread in threading.enumerate()
        if thread.name == "egw-mqtt-supervisor"
    ]
    assert len(supervisor) == 1 and supervisor[0].daemon is True
    bridge.stop()
    assert client.disconnect_called is True
    assert client.loop_stopped is True
    assert client.calls[-2:] == ["disconnect", "loop_stop"]
    assert supervisor[0].is_alive() is False


async def test_on_connect_subscribes_qos1_but_not_ready_before_suback() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    assert bridge.connected is False
    connect_ok(client)
    # CONTRACTS 1: QoS 1 subscription to the controller topic filter.
    assert client.subscriptions == [("c2dt/+/+/telemetry", 1)]
    # Not ready yet: the SUBACK has not been received.
    assert bridge.connected is False
    bridge.stop()


async def test_suback_granted_at_qos1_sets_connected() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    connect_ok(client)
    suback(client, value=1)
    assert bridge.connected is True
    assert bridge.state()["mqtt_subscribed"] is True
    bridge.stop()
    assert bridge.connected is False
    assert bridge.state()["mqtt_subscribed"] is False


async def test_suback_granted_at_qos0_keeps_not_ready(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T23 (item 11): a QoS 0 grant would silently disable every PUBACK, so
    the bridge stays not ready and says why."""
    bridge, client, _ = make_bridge()
    bridge.start()
    connect_ok(client)
    with caplog.at_level(logging.INFO, logger=MQTT_LOGGER):
        suback(client, value=0)
    assert bridge.connected is False
    assert bridge.state()["mqtt_subscribed"] is False
    assert "MQTT subscription granted at QoS 0; staying not ready" in caplog.text
    bridge.stop()


async def test_suback_denied_stays_not_ready() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    connect_ok(client)
    suback(client, value=0x80)  # unspecified error / not authorized family
    assert bridge.connected is False
    bridge.stop()


async def test_suback_for_unexpected_mid_is_ignored() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    connect_ok(client)
    suback(client, value=1, mid=(client.last_mid or 0) + 99)
    assert bridge.connected is False
    suback(client, value=1)  # the real SUBACK still works afterwards
    assert bridge.connected is True
    bridge.stop()


async def test_subscribe_request_failure_stays_not_ready() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    client.subscribe_result = 4  # MQTT_ERR_NO_CONN
    connect_ok(client)
    assert client.subscriptions == [("c2dt/+/+/telemetry", 1)]
    assert bridge.connected is False
    bridge.stop()


async def test_failed_connect_does_not_subscribe_nor_count_a_connection() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    reason_code = SimpleNamespace(is_failure=True)
    client.on_connect(client, None, {}, reason_code, None)
    assert client.subscriptions == []
    assert bridge.connected is False
    assert bridge.state()["mqtt_connection"] == 0
    bridge.stop()


async def test_connack_counts_connections_and_logs_session_present(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Item 14: ``mqtt_connection`` counts the successful CONNACKs of the
    process; the CONNACK's ``session_present`` flag is logged (D-10)."""
    bridge, client, _ = make_bridge()
    bridge.start()
    with caplog.at_level(logging.INFO, logger=MQTT_LOGGER):
        connect_ok(client, session_present=False)
        connect_ok(client, session_present=True)
    assert bridge.state()["mqtt_connection"] == 2
    flags = [
        record.context["session_present"]  # type: ignore[attr-defined]
        for record in caplog.records
        if record.getMessage() == "MQTT connected; subscription requested"
    ]
    assert flags == [False, True]
    bridge.stop()


async def test_disconnect_clears_connected_flag() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    connect_and_grant(client)
    assert bridge.connected is True
    client.on_disconnect(client, None, {}, SimpleNamespace(is_failure=True), None)
    assert bridge.connected is False
    bridge.stop()


def test_state_starts_from_the_documented_zero_values() -> None:
    bridge, _, _ = make_bridge()
    assert bridge.state() == {
        "mqtt_subscribed": False,
        "mqtt_connection": 0,
        "unacked": 0,
    }


# ---------------------------------------------------------------------------
# on_message: delivery identity, hand-over, discard, never raises
# ---------------------------------------------------------------------------


async def test_on_message_bridges_into_event_loop_with_arrival_clock() -> None:
    clock = FakeClock(7_000_000)
    bridge, client, received = make_bridge(clock)
    bridge.start()
    connect_and_grant(client)

    topic = f"c2dt/egw-01/{WATCH}/telemetry"
    deliver(client, message_for(b'{"seq": 0}', topic=topic, mid=42, qos=1, dup=True))
    # The submit callback runs on the loop via call_soon_threadsafe.
    await asyncio.sleep(0)
    (inbound,) = received
    assert inbound.topic == topic
    assert inbound.payload == b'{"seq": 0}'
    # Latency start point: monotonic_ns captured at callback time.
    assert inbound.received_monotonic_ns == 7_000_000
    # Item 2: the delivery identity, stamped on the network thread; the
    # first connection is 1.
    assert (inbound.mid, inbound.qos, inbound.dup, inbound.connection) == (
        42,
        1,
        True,
        1,
    )
    bridge.stop()


async def test_message_before_start_is_discarded_counted_and_ends_the_connection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T08 and T32 (item 12): a delivery that reaches the callback with no
    event loop is not handed over, gets no PUBACK, is counted in ``unacked``
    (it was handed to the client) and ends acknowledgement on that
    connection with the cause ``no-event-loop``."""
    bridge, client, received = make_bridge()
    with caplog.at_level(logging.ERROR, logger=MQTT_LOGGER):
        deliver(client, message_for(mid=3, qos=1))  # no loop attached yet
    await asyncio.sleep(0)
    assert received == []
    assert client.acks == []
    assert bridge.state()["unacked"] == 1
    (end,) = _ends(caplog)
    assert end["cause"] == "no-event-loop"
    assert end["connection"] == 1
    assert bridge.ack(
        InboundMessage(topic="t", payload=b"", received_monotonic_ns=0, mid=3, qos=1,
                       connection=1)
    ) is False


async def test_payload_is_copied_to_bytes() -> None:
    bridge, client, received = make_bridge()
    bridge.start()
    deliver(client, message_for(bytearray(b"abc"), topic="c2dt/x/y/telemetry"))
    await asyncio.sleep(0)
    (inbound,) = received
    assert isinstance(inbound.payload, bytes)
    assert inbound.payload == b"abc"
    bridge.stop()


async def test_qos0_delivery_is_handed_over_but_never_counted_unacked() -> None:
    """T09 (bridge half): a QoS 0 delivery carries ``mid`` 0 and is never a
    candidate for a PUBACK, so it is not counted in ``unacked``."""
    bridge, client, received = make_bridge()
    bridge.start()
    deliver(client, message_for(mid=0, qos=0))
    await asyncio.sleep(0)
    (inbound,) = received
    assert (inbound.mid, inbound.qos) == (0, 0)
    assert bridge.state()["unacked"] == 0
    assert bridge.ack(inbound) is False
    assert client.acks == []
    bridge.stop()


async def test_on_message_exception_ends_the_connection_not_the_thread(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T22 (item 10): an exception inside the callback never leaves it (paho
    would let the network thread die with ``/ready`` still true); it is
    logged, readiness is cleared and the connection is ended."""
    bridge, client, received = make_bridge()
    bridge.start()
    connect_and_grant(client)

    class BrokenTopic:
        payload = b"{}"
        mid = 5
        qos = 1
        dup = False

        @property
        def topic(self) -> str:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    with caplog.at_level(logging.ERROR, logger=MQTT_LOGGER):
        deliver(client, BrokenTopic())  # returns: nothing propagates
    await asyncio.sleep(0)
    assert received == []
    assert "MQTT on_message failed" in caplog.text
    assert [end["cause"] for end in _ends(caplog)] == ["on-message-error"]
    assert bridge.connected is False
    assert bridge.state()["unacked"] == 1  # handed to the client, no PUBACK
    bridge.stop()


# ---------------------------------------------------------------------------
# Connection identity, ack, socket close and purge (items 3 and 14)
# ---------------------------------------------------------------------------


async def test_ack_sends_only_for_the_current_connection_and_qos1() -> None:
    """D-3: ``ack`` calls ``client.ack(mid, 1)`` under the bridge lock only
    for a QoS 1 delivery of the current connection while acknowledgement
    is open; it lowers ``unacked`` and reports the return code."""
    bridge, client, received = make_bridge()
    bridge.start()
    deliver(client, message_for(mid=7, qos=1))
    deliver(client, message_for(mid=8, qos=1))
    await asyncio.sleep(0)
    first, second = received
    assert bridge.state()["unacked"] == 2
    assert bridge.ack(first) is True
    assert client.acks == [(7, 1)]
    assert bridge.state()["unacked"] == 1
    # A delivery of another connection is not acknowledged.
    stale = InboundMessage(
        topic=first.topic, payload=first.payload, received_monotonic_ns=0,
        mid=9, qos=1, connection=first.connection + 1,
    )
    assert bridge.ack(stale) is False
    assert client.acks == [(7, 1)]
    assert bridge.state()["unacked"] == 1
    bridge.stop()


async def test_puback_requested_after_the_identity_advanced_is_not_sent() -> None:
    """T19 and T30: ``on_socket_close`` advances the connection identity and
    resets ``unacked`` under the same lock ``ack`` takes, so a PUBACK
    requested for the ended connection never reaches the next one."""
    purged: list[int] = []
    bridge, client, received = make_bridge(purge=purged.append)
    bridge.start()
    connect_and_grant(client)
    deliver(client, message_for(mid=7, qos=1))
    await asyncio.sleep(0)
    (delivery,) = received
    assert bridge.state()["unacked"] == 1

    socket_close(client)
    assert bridge.connected is False
    assert bridge.state()["unacked"] == 0
    assert bridge.ack(delivery) is False
    assert client.acks == []
    await asyncio.sleep(0)  # the purge was scheduled onto the loop
    assert purged == [1]

    # The next connection stamps the next identity and starts from zero.
    deliver(client, message_for(mid=7, qos=1, dup=True))
    await asyncio.sleep(0)
    resent = received[-1]
    assert resent.connection == 2
    assert bridge.state()["unacked"] == 1
    assert bridge.ack(resent) is True
    assert client.acks == [(7, 1)]
    assert bridge.state()["unacked"] == 0
    bridge.stop()


async def test_socket_close_never_raises(caplog: pytest.LogCaptureFixture) -> None:
    """A raising close handler would kill paho's network thread: whatever
    fails after the identity advanced is logged and swallowed."""
    bridge, client, received = make_bridge(purge=lambda ended: None)
    bridge.start()

    class BrokenLoop:
        def is_closed(self) -> bool:
            raise RuntimeError("loop gone")

    bridge._loop = BrokenLoop()  # type: ignore[assignment]
    with caplog.at_level(logging.ERROR, logger=MQTT_LOGGER):
        socket_close(client)  # returns
    assert "MQTT on_socket_close failed" in caplog.text
    assert bridge.state()["mqtt_subscribed"] is False
    # The identity advanced before the failure.
    bridge._loop = asyncio.get_running_loop()
    deliver(client, message_for(mid=1, qos=1))
    await asyncio.sleep(0)
    assert received[-1].connection == 2
    bridge.stop()


async def test_socket_close_is_counted_once_per_close_and_clears_readiness() -> None:
    bridge, client, received = make_bridge()
    bridge.start()
    connect_and_grant(client)
    for _ in range(3):
        socket_close(client)
    deliver(client, message_for(mid=1, qos=1))
    await asyncio.sleep(0)
    assert received[-1].connection == 4
    assert bridge.connected is False
    bridge.stop()


# ---------------------------------------------------------------------------
# end_connection, the supervisor thread, A5 (items 4, 10, 12)
# ---------------------------------------------------------------------------


async def test_end_connection_closes_ack_records_and_reconnects_in_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T25 (A3(a)): ``end_connection`` closes acknowledgement at once,
    records the occurrence with its cause, connection and identity, and the
    supervisor runs disconnect, loop_stop, the back-off, connect_async and
    loop_start; readiness is false meanwhile."""
    bridge, client, received = make_bridge()
    bridge.start()
    connect_and_grant(client)
    deliver(client, message_for(mid=7, qos=1))
    await asyncio.sleep(0)
    (delivery,) = received
    with caplog.at_level(logging.ERROR, logger=MQTT_LOGGER):
        bridge.end_connection("no-outcome-line", delivery)
        assert bridge.ack(delivery) is False
        assert client.acks == []
        await until(lambda: client.count("loop_start") == 2)
    assert client.calls == [
        "connect_async",
        "loop_start",
        "disconnect",
        "loop_stop",
        "connect_async",
        "loop_start",
    ]
    assert bridge.connected is False
    (end,) = _ends(caplog)
    assert end["cause"] == "no-outcome-line"
    assert end["connection"] == 1
    assert end["occurrence"] == 1
    assert end["backoff_s"] == 0.0
    assert end["identity"]["mid"] == 7
    assert end["identity"]["topic"] == delivery.topic
    bridge.stop()


async def test_repeated_connection_ends_are_recorded_and_bounded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T26 (A5): every occurrence is recorded; beyond the bound the bridge
    stays disconnected in a visible state (not ready, ``mqtt_subscribed``
    false) instead of reconnecting for ever."""
    bridge, client, _ = make_bridge(end_bound=2)
    bridge.start()
    connect_and_grant(client)
    with caplog.at_level(logging.ERROR, logger=MQTT_LOGGER):
        bridge.end_connection("no-outcome-line", None)
        await until(lambda: client.count("loop_start") == 2)
        connect_and_grant(client)
        bridge.end_connection("no-outcome-line", None)
        await until(lambda: client.count("loop_start") == 3)
        connect_and_grant(client)
        assert bridge.connected is True
        bridge.end_connection("no-outcome-line", None)  # the third: > bound
        await until(
            lambda: "MQTT reconnection bound reached; staying disconnected"
            in caplog.text
        )
        await asyncio.sleep(0.05)  # no reconnection follows
    assert [end["occurrence"] for end in _ends(caplog)] == [1, 2, 3]
    assert client.count("connect_async") == 3
    assert client.calls[-2:] == ["disconnect", "loop_stop"]
    assert bridge.connected is False
    assert bridge.state()["mqtt_subscribed"] is False
    bridge.stop()


async def test_an_acknowledged_delivery_resets_the_occurrence_counter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bridge, client, received = make_bridge(end_bound=1)
    bridge.start()
    connect_and_grant(client)
    with caplog.at_level(logging.ERROR, logger=MQTT_LOGGER):
        bridge.end_connection("overflow", None)
        await until(lambda: client.count("loop_start") == 2)
        socket_close(client)  # paho closes the socket on the disconnect
        connect_and_grant(client)
        deliver(client, message_for(mid=1, qos=1))
        await asyncio.sleep(0)
        assert bridge.ack(received[-1]) is True
        bridge.end_connection("overflow", None)
        await until(lambda: client.count("loop_start") == 3)
    assert [end["occurrence"] for end in _ends(caplog)] == [1, 1]
    bridge.stop()


async def test_backoff_grows_with_the_occurrence_and_is_capped() -> None:
    from egw_controller.mqtt import default_backoff_s

    assert [default_backoff_s(n) for n in (1, 2, 3, 4, 5, 6, 7)] == [
        1, 2, 4, 8, 16, 30, 30,
    ]


async def test_stop_records_the_cause_and_closes_acknowledgement(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bridge, client, received = make_bridge()
    bridge.start()
    connect_and_grant(client)
    deliver(client, message_for(mid=1, qos=1))
    await asyncio.sleep(0)
    with caplog.at_level(logging.INFO, logger=MQTT_LOGGER):
        bridge.stop()
    assert bridge.ack(received[-1]) is False
    assert client.acks == []
    stops = [
        record for record in caplog.records
        if record.getMessage() == "MQTT connection ended by the controller"
    ]
    assert [record.levelno for record in stops] == [logging.INFO]
    assert stops[0].context["cause"] == "stop"  # type: ignore[attr-defined]
    assert client.count("loop_start") == 1  # no reconnection after a stop


# ---------------------------------------------------------------------------
# Counting point of ``received`` (CONTRACTS 5, progress counters)
# ---------------------------------------------------------------------------


def make_bridged_service(
    tmp_path: Path,
    *,
    events: EventLogger | None = None,
    ditto: FakeDittoClient | None = None,
    queue_maxsize: int = 100,
    end_bound: int = 10,
) -> tuple[
    MqttBridge, FakePahoClient, ControllerService, MetricsCounters, EventLogger
]:
    """Bridge and service wired as ``create_app_from_env`` wires them."""
    metrics = MetricsCounters()
    events = events if events is not None else EventLogger(tmp_path)
    fake_client = FakePahoClient()
    bridge = MqttBridge(
        Settings.from_env({"EGW_MQTT_TLS": "false"}),
        lambda message: service.submit(message),
        client=fake_client,  # type: ignore[arg-type]
        purge=lambda ended: service.purge(ended),
        backoff_s=_no_backoff,
        end_bound=end_bound,
    )
    service = ControllerService(
        repository=SchemaRepository(SCHEMA_DIR),
        dedupe=DedupeCache(),
        ditto=ditto if ditto is not None else FakeDittoClient(),
        events=events,
        metrics=metrics,
        queue_maxsize=queue_maxsize,
        acknowledge=bridge.ack,
        end_connection=bridge.end_connection,
    )
    return bridge, fake_client, service, metrics, events


async def test_message_before_the_loop_exists_reaches_no_counter(
    tmp_path: Path,
) -> None:
    """A message the callback discards because the bridge has no loop yet is
    outside the accounting boundary: it is on neither side of the identity.
    Only the bridge's own ``unacked`` sees it."""
    bridge, client, service, metrics, events = make_bridged_service(tmp_path)
    deliver(client, message_for(b"{}", topic="c2dt/x/y/telemetry"))  # not started
    await asyncio.sleep(0)
    snapshot = metrics.snapshot()
    for name in (
        "accepted",
        "rejected",
        "duplicate",
        "failed",
        "dropped",
        "received",
        "in_progress",
        "processing_errors",
    ):
        assert snapshot[name] == 0
    assert service.queue_depth() == 0
    assert bridge.state()["unacked"] == 1
    events.close()


async def test_bridged_message_is_received_only_after_the_hand_over(
    tmp_path: Path,
) -> None:
    """``received`` is counted in ``submit`` on the event loop, one thread
    hand-over after the callback, together with the enqueue: a message still
    between the two is "not yet received", never received-but-unaccounted;
    ``unacked`` is counted at the callback, so it covers the hand-over
    (T31)."""
    bridge, client, service, metrics, events = make_bridged_service(tmp_path)
    bridge.start()
    deliver(client, message_for(b'{"seq": 0}'))
    before = metrics.snapshot()
    assert (before["received"], service.queue_depth()) == (0, 0)
    assert accounting_gap(before, service.queue_depth()) == 0
    assert bridge.state()["unacked"] == 1

    await asyncio.sleep(0)  # the loop runs the scheduled submit
    after = metrics.snapshot()
    assert (after["received"], service.queue_depth()) == (1, 1)
    assert accounting_gap(after, service.queue_depth()) == 0
    assert bridge.state()["unacked"] == 1
    bridge.stop()
    events.close()


# ---------------------------------------------------------------------------
# Bridge + consumer: the acknowledgement point end to end (ADR 0011)
# ---------------------------------------------------------------------------


class _OrderRecordingEventLogger(EventLogger):
    def __init__(self, log_dir: Path, order: list[str]) -> None:
        super().__init__(log_dir)
        self.order = order

    def log(self, event: ControllerEvent) -> None:
        super().log(event)
        self.order.append(f"line:{event.seq}")


async def _idle(service: ControllerService, metrics: MetricsCounters) -> None:
    """Wait for the hand-over of every fired callback, then for the consumer
    to have emptied the queue and finished the delivery in progress."""
    await asyncio.sleep(0)
    await until(
        lambda: metrics.snapshot()["in_progress"] == 0 and service.queue_depth() == 0
    )


async def test_puback_follows_the_line_once_per_delivery_in_receipt_order(
    tmp_path: Path,
) -> None:
    """T01, T02, T24: over accepted, duplicate, rejected and failed
    deliveries the bridge sends exactly one PUBACK per QoS 1 delivery, each
    after its line and in receipt order."""
    from egw_controller.ditto import DittoUnavailableError

    class FailsSecondPatch(FakeDittoClient):
        async def patch_thing(self, device_uuid: str, patch: Any) -> int:
            if len(self.patch_calls) == 1:
                self.fail_patch = DittoUnavailableError("down", attempts=3)
            return await super().patch_thing(device_uuid, patch)

    order: list[str] = []
    events = _OrderRecordingEventLogger(tmp_path, order)
    bridge, client, service, metrics, _ = make_bridged_service(
        tmp_path, events=events, ditto=FailsSecondPatch()
    )
    client.calls = order  # the fake appends "ack:<mid>" to the same list
    bridge.start()
    connect_and_grant(client)
    order.clear()
    task = asyncio.create_task(service.run())
    accepted = make_payload("smartwatch", seq=0)
    deliver(client, message_for(accepted, mid=11))
    deliver(client, message_for(accepted, mid=12))  # duplicate
    deliver(client, message_for(make_payload("smartwatch", seq=1, heart_rate_bpm=999),
                                mid=13))  # rejected
    deliver(client, message_for(make_payload("smartwatch", seq=2), mid=14))  # failed
    await _idle(service, metrics)
    await service.stop()
    await task
    assert [record["outcome"] for record in read_events(tmp_path)] == [
        "accepted", "duplicate", "rejected", "failed",
    ]
    assert order == [
        "line:0", "ack:11", "line:0", "ack:12", "line:1", "ack:13", "line:2", "ack:14",
    ]
    assert client.acks == [(11, 1), (12, 1), (13, 1), (14, 1)]
    assert bridge.state()["unacked"] == 0
    bridge.stop()
    events.close()


class _FailAtOpenLogger(EventLogger):
    """The first open of a bucket raises ``OSError`` (T16)."""

    def __init__(self, log_dir: Path) -> None:
        super().__init__(log_dir)
        self.failures_left = 1

    def _open(self, bucket: str) -> Any:
        if self.failures_left > 0:
            self.failures_left -= 1
            raise OSError(28, "No space left on device")
        return super()._open(bucket)


class _FailAtWriteLogger(EventLogger):
    """The first write on a bucket's handle raises ``OSError`` (T17)."""

    def __init__(self, log_dir: Path) -> None:
        super().__init__(log_dir)
        self.failures_left = 1

    def _open(self, bucket: str) -> Any:
        fh = super()._open(bucket)
        if self.failures_left > 0:
            self.failures_left -= 1
            logger_self = self

            class Failing:
                closed = False

                def write(self, data: bytes) -> int:
                    raise OSError(28, "No space left on device")

                def close(self) -> None:
                    self.closed = True
                    fh.close()

            failing = Failing()
            logger_self._files[bucket] = failing  # type: ignore[assignment]
            return failing
        return fh


@pytest.mark.parametrize(
    "make_logger", [_FailAtOpenLogger, _FailAtWriteLogger], ids=["open", "write"]
)
async def test_event_write_failure_ends_the_connection_with_no_late_line(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    make_logger: Callable[[Path], EventLogger],
) -> None:
    """T03, T16, T17, T34: a delivery whose line cannot be written gets no
    line and no PUBACK, nor does anything after it on that connection; the
    connection is ended; ``unacked`` stays above 0 while the connection
    lasts; after recovery no late line appears for it, and the copy the
    broker resends on the next connection is acknowledged (T21)."""
    events = make_logger(tmp_path)
    bridge, client, service, metrics, _ = make_bridged_service(tmp_path, events=events)
    bridge.start()
    connect_and_grant(client)
    task = asyncio.create_task(service.run())
    with caplog.at_level(logging.ERROR):
        deliver(client, message_for(make_payload("smartwatch", seq=0), mid=1))
        deliver(client, message_for(make_payload("smartwatch", seq=1), mid=2))
        await _idle(service, metrics)
        await until(lambda: client.count("loop_start") == 2)
        await _idle(service, metrics)
    # seq 0: no line; seq 1: its line, but no PUBACK (acknowledgement closed).
    assert [record["seq"] for record in read_events(tmp_path)] == [1]
    assert client.acks == []  # nothing after the failure on that connection
    assert bridge.state()["unacked"] == 2
    assert [end["cause"] for end in _ends(caplog)] == ["no-outcome-line"]
    assert client.calls[2:] == ["disconnect", "loop_stop", "connect_async", "loop_start"]
    snapshot = metrics.snapshot()
    assert snapshot["processing_errors"] == 1

    # paho closes the socket on the DISCONNECT; the session resumes and the
    # broker resends both deliveries with DUP set.
    socket_close(client)
    await asyncio.sleep(0)  # purge (nothing queued)
    connect_and_grant(client)
    assert bridge.state()["unacked"] == 0
    deliver(client, message_for(make_payload("smartwatch", seq=0), mid=1, dup=True))
    deliver(client, message_for(make_payload("smartwatch", seq=1), mid=2, dup=True))
    await _idle(service, metrics)
    await service.stop()
    await task
    records = read_events(tmp_path)
    # The failed delivery never obtained a late line: seq 0's only line is
    # the resent copy's, a duplicate (the twin was updated the first time);
    # seq 1, recorded but never acknowledged, is resent too.
    assert [(record["seq"], record["outcome"]) for record in records] == [
        (1, "accepted"),
        (0, "duplicate"),
        (1, "duplicate"),
    ]
    assert client.acks == [(1, 1), (2, 1)]
    assert bridge.state()["unacked"] == 0
    bridge.stop()
    events.close()


async def test_overflow_ends_acknowledgement_and_keeps_the_delivery_counted(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T07 and T33: a delivery dropped on a full queue gets no PUBACK and
    ends acknowledgement on its connection, so the earlier one processed
    afterwards is not acknowledged either; both stay in ``unacked``."""
    bridge, client, service, metrics, events = make_bridged_service(
        tmp_path, queue_maxsize=1
    )
    bridge.start()
    connect_and_grant(client)
    with caplog.at_level(logging.ERROR, logger=MQTT_LOGGER):
        deliver(client, message_for(make_payload("smartwatch", seq=0), mid=1))
        deliver(client, message_for(make_payload("smartwatch", seq=1), mid=2))
        await asyncio.sleep(0)
        assert metrics.snapshot()["dropped"] == 1
        task = asyncio.create_task(service.run())
        await _idle(service, metrics)
        await until(lambda: client.count("loop_start") == 2)
    await service.stop()
    await task
    assert [end["cause"] for end in _ends(caplog)] == ["overflow"]
    assert [record["seq"] for record in read_events(tmp_path)] == [0]
    assert client.acks == []
    assert bridge.state()["unacked"] == 2
    bridge.stop()
    events.close()


async def test_purge_leaves_no_delivery_of_the_ended_connection_queued(
    tmp_path: Path,
) -> None:
    """T20 and T21: on the socket close the queued deliveries of the ended
    connection are purged (counted ``dropped``), the identity holds, and
    the copies resent on the next connection are processed and acknowledged."""
    bridge, client, service, metrics, events = make_bridged_service(tmp_path)
    bridge.start()
    connect_and_grant(client)
    for seq in range(3):
        deliver(client, message_for(make_payload("smartwatch", seq=seq), mid=seq + 1))
    await asyncio.sleep(0)
    assert service.queue_depth() == 3
    socket_close(client)
    await asyncio.sleep(0)  # the purge runs before any later submit
    snapshot = metrics.snapshot()
    assert (service.queue_depth(), snapshot["dropped"], snapshot["received"]) == (
        0,
        3,
        3,
    )
    assert accounting_gap(snapshot, service.queue_depth()) == 0
    assert bridge.state()["unacked"] == 0

    connect_and_grant(client)
    for seq in range(3):
        deliver(client, message_for(make_payload("smartwatch", seq=seq), mid=seq + 1,
                                    dup=True))
    task = asyncio.create_task(service.run())
    await _idle(service, metrics)
    await service.stop()
    await task
    assert [record["outcome"] for record in read_events(tmp_path)] == ["accepted"] * 3
    assert client.acks == [(1, 1), (2, 1), (3, 1)]
    assert accounting_gap(metrics.snapshot(), service.queue_depth()) == 0
    bridge.stop()
    events.close()


async def test_graceful_stop_acknowledges_the_delivery_in_progress_then_disconnects(
    tmp_path: Path,
) -> None:
    """T28: the delivery in progress is recorded and acknowledged, the rest
    of the queue is left unacknowledged, and the DISCONNECT is queued after
    that PUBACK (paho writes them in order and none after the DISCONNECT)."""
    ditto = GatedDittoClient()
    bridge, client, service, metrics, events = make_bridged_service(
        tmp_path, ditto=ditto
    )
    bridge.start()
    connect_and_grant(client)
    task = asyncio.create_task(service.run())
    deliver(client, message_for(make_payload("smartwatch", seq=0), mid=1))
    await ditto.entered.wait()
    deliver(client, message_for(make_payload("smartwatch", seq=1), mid=2))
    await asyncio.sleep(0)
    await service.stop()
    ditto.release.set()
    await task
    bridge.stop()
    assert [record["seq"] for record in read_events(tmp_path)] == [0]
    assert client.acks == [(1, 1)]
    assert client.calls[-3:] == ["ack:1", "disconnect", "loop_stop"]
    assert service.queue_depth() == 1
    assert bridge.state()["unacked"] == 1
    events.close()


async def test_deliveries_of_a_process_that_never_consumed_them_get_no_puback(
    tmp_path: Path,
) -> None:
    """T05: deliveries handed to the client by a process that dies before
    the consumer records them are never acknowledged: only the consumer
    requests a PUBACK, after the line, and the bridge sends none on its own,
    not even at stop."""
    bridge, client, service, metrics, events = make_bridged_service(tmp_path)
    bridge.start()
    connect_and_grant(client)
    deliver(client, message_for(make_payload("smartwatch", seq=0), mid=1))
    deliver(client, message_for(make_payload("smartwatch", seq=1), mid=2))
    await asyncio.sleep(0)
    bridge.stop()  # the process ends with the consumer never having run
    assert client.acks == []
    assert bridge.state()["unacked"] == 2
    assert read_events(tmp_path) == []
    events.close()


# ---------------------------------------------------------------------------
# TLS / credential wiring of the self-built client (CONTRACTS 1 and 6)
# ---------------------------------------------------------------------------


class RecordingPahoClient:
    """Constructor-compatible paho Client stand-in recording wiring calls."""

    def __init__(
        self,
        *,
        callback_api_version: Any = None,
        client_id: str = "",
        clean_session: bool | None = None,
        manual_ack: bool = False,
    ) -> None:
        self.callback_api_version = callback_api_version
        self.client_id = client_id
        self.clean_session = clean_session
        self.manual_ack = manual_ack
        self.tls_set_calls: list[dict[str, Any]] = []
        self.username_pw_set_calls: list[tuple[str, str | None]] = []
        self.reconnect_delay_set_calls: list[dict[str, int]] = []
        # Callback attributes assigned by MqttBridge.__init__.
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.on_message: Any = None
        self.on_subscribe: Any = None
        self.on_socket_close: Any = None

    def username_pw_set(self, username: str, password: str | None = None) -> None:
        self.username_pw_set_calls.append((username, password))

    def tls_set(self, ca_certs: str | None = None, **kwargs: Any) -> None:
        self.tls_set_calls.append({"ca_certs": ca_certs, **kwargs})

    def reconnect_delay_set(
        self, min_delay: int = 1, max_delay: int = 120
    ) -> None:
        self.reconnect_delay_set_calls.append(
            {"min_delay": min_delay, "max_delay": max_delay}
        )


def test_build_client_wires_tls_and_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # mqtt.py imports Client from paho.mqtt.client into its own namespace, so
    # the recorder must replace the name used there.
    monkeypatch.setattr("egw_controller.mqtt.Client", RecordingPahoClient)
    settings = Settings.from_env(
        {
            "EGW_MQTT_TLS": "true",
            "EGW_MQTT_CA_CERT": "/certs/mosquitto-ca.crt",
            "EGW_MQTT_USERNAME": "egw-controller",
            "EGW_MQTT_PASSWORD": "dev-secret",
        }
    )
    bridge = MqttBridge(settings, lambda message: None)
    client = bridge._client
    assert isinstance(client, RecordingPahoClient)
    assert client.client_id == "egw-controller-egw-01"
    # T27 (item 1): persistent session and manual acknowledgement, both in
    # the constructor, never through manual_ack_set while connected.
    assert client.clean_session is False
    assert client.manual_ack is True
    assert client.tls_set_calls == [{"ca_certs": "/certs/mosquitto-ca.crt"}]
    assert client.username_pw_set_calls == [("egw-controller", "dev-secret")]
    assert client.reconnect_delay_set_calls == [
        {"min_delay": 1, "max_delay": 30}
    ]
    # The bridge attached its callbacks to the client it built.
    assert client.on_connect is not None
    assert client.on_subscribe is not None
    assert client.on_socket_close is not None


def test_build_client_without_tls_never_calls_tls_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("egw_controller.mqtt.Client", RecordingPahoClient)
    settings = Settings.from_env(
        {
            "EGW_MQTT_TLS": "false",
            "EGW_MQTT_USERNAME": "egw-controller",
            "EGW_MQTT_PASSWORD": "dev-secret",
        }
    )
    bridge = MqttBridge(settings, lambda message: None)
    client = bridge._client
    assert isinstance(client, RecordingPahoClient)
    assert client.tls_set_calls == []
    assert client.username_pw_set_calls == [("egw-controller", "dev-secret")]
