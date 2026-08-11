"""Tests for egw_controller.mqtt with a fake paho client (no network).

Verifies the latency start point (``received_monotonic_ns`` captured in the
callback at message arrival), the threadsafe bridge into the asyncio queue,
the QoS 1 subscription to the topic filter, the SUBACK-gated readiness
(connected only after the broker grants the subscription at QoS 0/1) and the
TLS/credential wiring of the self-built paho client.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

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
        self.on_subscribe: Any = None
        self.subscriptions: list[tuple[str, int]] = []
        self.connect_async_calls: list[tuple[str, int, int]] = []
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
    """Fire on_connect with a successful CONNACK (subscribe is requested)."""
    reason_code = SimpleNamespace(is_failure=False)
    client.on_connect(client, None, {}, reason_code, None)


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


async def test_start_connects_and_runs_network_loop() -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    assert client.connect_async_calls == [("localhost", 8883, 60)]
    assert client.loop_started is True
    bridge.stop()
    assert client.disconnect_called is True
    assert client.loop_stopped is True


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


@pytest.mark.parametrize("granted_qos", [0, 1])
async def test_suback_granted_sets_connected(granted_qos: int) -> None:
    bridge, client, _ = make_bridge()
    bridge.start()
    connect_ok(client)
    suback(client, value=granted_qos)
    assert bridge.connected is True
    bridge.stop()
    assert bridge.connected is False


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
    connect_and_grant(client)
    assert bridge.connected is True
    client.on_disconnect(client, None, {}, SimpleNamespace(is_failure=True), None)
    assert bridge.connected is False
    bridge.stop()


async def test_on_message_bridges_into_event_loop_with_arrival_clock() -> None:
    clock = FakeClock(7_000_000)
    bridge, client, received = make_bridge(clock)
    bridge.start()
    connect_and_grant(client)

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


# ---------------------------------------------------------------------------
# TLS / credential wiring of the self-built client (CONTRACTS 1 and 6)
# ---------------------------------------------------------------------------


class RecordingPahoClient:
    """Constructor-compatible paho Client stand-in recording wiring calls."""

    def __init__(
        self, *, callback_api_version: Any = None, client_id: str = ""
    ) -> None:
        self.callback_api_version = callback_api_version
        self.client_id = client_id
        self.tls_set_calls: list[dict[str, Any]] = []
        self.username_pw_set_calls: list[tuple[str, str | None]] = []
        self.reconnect_delay_set_calls: list[dict[str, int]] = []
        # Callback attributes assigned by MqttBridge.__init__.
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.on_message: Any = None
        self.on_subscribe: Any = None

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
    assert client.tls_set_calls == [{"ca_certs": "/certs/mosquitto-ca.crt"}]
    assert client.username_pw_set_calls == [("egw-controller", "dev-secret")]
    assert client.reconnect_delay_set_calls == [
        {"min_delay": 1, "max_delay": 30}
    ]
    # The bridge attached its callbacks to the client it built.
    assert client.on_connect is not None
    assert client.on_subscribe is not None


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
