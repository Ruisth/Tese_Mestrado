"""Publisher interface and implementations (CONTRACTS.md section 1).

``Publisher`` is the minimal protocol the runner publishes through, so the
run loop is testable without a broker. ``PahoPublisher`` is the production
implementation (paho-mqtt 2.x, TLS server-auth, username/password, QoS 1,
automatic reconnect with backoff); ``InMemoryPublisher`` records messages in
memory for tests.

paho-mqtt is imported lazily inside ``PahoPublisher`` so that tests using
only ``InMemoryPublisher`` do not require the dependency at import time.

Lifecycle contract: the caller (CLI) invokes ``connect()`` before handing the
publisher to the runner and ``close()`` after the run finishes; the runner
itself only calls ``publish()``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PublishResult:
    """Timing evidence for one published message.

    ``publish_monotonic_ns`` is captured immediately before the client
    publish call; ``puback_monotonic_ns`` after the QoS 1 acknowledgement
    (``None`` when no acknowledgement arrived within the timeout).
    """

    publish_monotonic_ns: int
    puback_monotonic_ns: int | None


@runtime_checkable
class Publisher(Protocol):
    """Minimal publishing interface used by the runner."""

    def connect(self) -> None: ...

    def publish(self, topic: str, payload: bytes) -> PublishResult: ...

    def close(self) -> None: ...


class InMemoryPublisher:
    """Test double: records (topic, payload, monotonic_ns) tuples in memory.

    ``records`` preserves publish order. Payloads are stored as decoded
    UTF-8 strings for convenient assertions. An optional clock object with a
    ``monotonic_ns()`` method may be injected; the default is
    ``time.monotonic_ns``.
    """

    def __init__(self, clock=None) -> None:
        self.records: list[tuple[str, str, int]] = []
        self.connected = False
        self._clock = clock

    def _now_ns(self) -> int:
        if self._clock is not None:
            return self._clock.monotonic_ns()
        return time.monotonic_ns()

    def connect(self) -> None:
        self.connected = True

    def publish(self, topic: str, payload: bytes) -> PublishResult:
        now_ns = self._now_ns()
        self.records.append((topic, payload.decode("utf-8"), now_ns))
        return PublishResult(publish_monotonic_ns=now_ns, puback_monotonic_ns=now_ns)

    def close(self) -> None:
        self.connected = False

    def decoded_payloads(self) -> list[dict]:
        """All recorded payloads parsed back into dicts (publish order)."""
        import json

        return [json.loads(payload) for _, payload, _ in self.records]


class PahoPublisher:
    """MQTT publisher backed by paho-mqtt 2.x (CONTRACTS.md section 1).

    - TLS server authentication with an optional CA file (``--ca-cert``);
      plain TCP only when ``tls=False`` (dev/localhost profile).
    - Username/password authentication (Mosquitto ``password_file``).
    - QoS 1 by default; ``wait_for_publish`` captures the puback instant.
    - Automatic reconnect with exponential backoff between
      ``reconnect_min_delay_s`` and ``reconnect_max_delay_s`` (paho network
      loop thread); QoS 1 messages published while disconnected are queued
      by the client and flushed on reconnect.
    - ``close()`` performs a clean DISCONNECT and stops the loop thread.
    """

    def __init__(
        self,
        host: str,
        port: int = 8883,
        *,
        username: str | None = None,
        password: str | None = None,
        ca_cert: str | None = None,
        tls: bool = True,
        qos: int = 1,
        client_id: str = "egw-simulator",
        keepalive_s: int = 30,
        connect_timeout_s: float = 15.0,
        publish_timeout_s: float = 30.0,
        reconnect_min_delay_s: float = 1.0,
        reconnect_max_delay_s: float = 30.0,
    ) -> None:
        import paho.mqtt.client as mqtt  # lazy: only needed for real runs

        self.host = host
        self.port = port
        self.qos = qos
        self._keepalive_s = keepalive_s
        self._connect_timeout_s = connect_timeout_s
        self._publish_timeout_s = publish_timeout_s
        self._connected = threading.Event()

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        if username is not None:
            client.username_pw_set(username, password)
        if tls:
            if ca_cert:
                client.tls_set(ca_certs=str(ca_cert))
            else:
                client.tls_set()  # system trust store
        client.reconnect_delay_set(
            min_delay=int(reconnect_min_delay_s), max_delay=int(reconnect_max_delay_s)
        )
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        self._client = client

    # paho v2 (CallbackAPIVersion.VERSION2) callback signatures.
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if not reason_code.is_failure:
            self._connected.set()

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ):
        self._connected.clear()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def connect(self) -> None:
        """Connect and start the network loop; raise on timeout/refusal."""
        self._client.connect(self.host, self.port, keepalive=self._keepalive_s)
        self._client.loop_start()
        if not self._connected.wait(self._connect_timeout_s):
            self._client.loop_stop()
            raise ConnectionError(
                f"MQTT connect to {self.host}:{self.port} not acknowledged "
                f"within {self._connect_timeout_s:.0f} s"
            )

    def publish(self, topic: str, payload: bytes) -> PublishResult:
        publish_ns = time.monotonic_ns()
        info = self._client.publish(topic, payload, qos=self.qos)
        puback_ns: int | None = None
        try:
            info.wait_for_publish(timeout=self._publish_timeout_s)
        except (RuntimeError, ValueError):
            # Message could not be queued (e.g. queue full while offline).
            pass
        if info.is_published():
            puback_ns = time.monotonic_ns()
        return PublishResult(
            publish_monotonic_ns=publish_ns, puback_monotonic_ns=puback_ns
        )

    def close(self) -> None:
        """Clean shutdown: DISCONNECT, then stop the network loop thread."""
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()
            self._connected.clear()
