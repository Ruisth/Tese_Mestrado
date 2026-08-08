"""Tests for egw_controller.mqtt with a fake paho client (no network).

Verifies the latency start point (``received_monotonic_ns`` captured in the
callback at message arrival), the threadsafe bridge into the asyncio queue,
the QoS 1 subscription to the topic filter and the connected flag lifecycle.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from egw_controller.config import Settings
from egw_controller.mqtt import MqttBridge
from egw_controller.service import InboundMessage
from test_controller_helpers import DEVICE_UUIDS, FakeClock

WATCH = DEVICE_UUIDS["smartwatch"]


class FakePahoClient:
    """Records the calls MqttBridge makes on the paho client."""

    def __init__(self) -> None:
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.on_message: Any = None
        self.subscriptions: list[tuple[str, int]] = []
        self.connect_async_calls: list[tuple[str, int, int]] = []
        self.loop_started = False
        self.loop_stopped = False
        self.disconnect_called = False

    def subscribe(self, topic: str, qos: int = 0) -> None:
        self.subscriptions.append((topic, qos))

    def connect_async(self, host: str, port: int, keepalive: int = 60) -> None:
        self.connect_async_calls.append((host, port, keepalive))

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_stopped = True

    def disconnect(self) -> None:
        self.disconnect_called = True


def make_bridge(
    clock: FakeClock | None = None,
) -> tuple[MqttBridge, FakePahoClient, list[InboundMessage]]:
    settings = Settings.from_env({"EGW_MQTT_TLS": "false"})
    received: list[InboundMessage] = []
    fake_client = FakePahoClient()
    bridge = MqttBridge(
        settings,
        received.append,
        monotonic_ns=clock or FakeClock(),
        client=fake_client,  # type: ignore[arg-type]
    )
    return bridge, fake_client, received


def connect_ok(client: FakePahoClient) -> None:
    reason_code = SimpleNamespace(is_failure=False)
    client.on_connect(client, None, {}, reason_code, None)


async def test_start_connects_and_runs_network_loop() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    assert client.connect_async_calls == [("localhost", 8883, 60)]
    assert client.loop_started is True
    bridge.stop()
    assert client.disconnect_called is True
    assert client.loop_stopped is True


async def test_on_connect_subscribes_qos1_and_sets_connected() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    assert bridge.connected is False
    connect_ok(client)
    # CONTRACTS 1: QoS 1 subscription to the controller topic filter.
    assert client.subscriptions == [("c2dt/+/+/telemetry", 1)]
    assert bridge.connected is True
    bridge.stop()
    assert bridge.connected is False


async def test_failed_connect_does_not_subscribe() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    reason_code = SimpleNamespace(is_failure=True)
    client.on_connect(client, None, {}, reason_code, None)
    assert client.subscriptions == []
    assert bridge.connected is False
    bridge.stop()


async def test_disconnect_clears_connected_flag() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    connect_ok(client)
    assert bridge.connected is True
    client.on_disconnect(client, None, {}, SimpleNamespace(is_failure=True), None)
    assert bridge.connected is False
    bridge.stop()


async def test_on_message_bridges_into_event_loop_with_arrival_clock() -> None:
    clock = FakeClock(7_000_000)
    bridge, client, received = make_bridge(clock)
    bridge.start()
    connect_ok(client)

    topic = f"c2dt/egw-01/{WATCH}/telemetry"
    message = SimpleNamespace(topic=topic, payload=b'{"seq": 0}')
    client.on_message(client, None, message)
    # The submit callback runs on the loop via call_soon_threadsafe.
    await asyncio.sleep(0)
    (inbound,) = received
    assert inbound.topic == topic
    assert inbound.payload == b'{"seq": 0}'
    # Latency start point: monotonic_ns captured at callback time.
    assert inbound.received_monotonic_ns == 7_000_000
    bridge.stop()


async def test_message_before_start_is_dropped() -> None:
    bridge, client, received = make_bridge()
    message = SimpleNamespace(topic="c2dt/x/y/telemetry", payload=b"{}")
    client.on_message(client, None, message)  # no loop attached yet
    await asyncio.sleep(0)
    assert received == []


async def test_payload_is_copied_to_bytes() -> None:
    bridge, client, received = make_bridge()
    bridge.start()
    message = SimpleNamespace(topic="c2dt/x/y/telemetry", payload=bytearray(b"abc"))
    client.on_message(client, None, message)
    await asyncio.sleep(0)
    (inbound,) = received
    assert isinstance(inbound.payload, bytes)
    assert inbound.payload == b"abc"
    bridge.stop()
