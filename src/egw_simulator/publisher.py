"""Publisher interface and implementations (CONTRACTS.md sections 1 and 7).

``Publisher`` is the minimal protocol the runner publishes through, so the
run loop is testable without a broker. ``PahoPublisher`` is the production
implementation (paho-mqtt 2.x, TLS server-auth, username/password, QoS 1,
automatic reconnect with backoff); ``InMemoryPublisher`` records messages in
memory for tests.

PUBACK capture is best-effort (CONTRACTS.md section 7, v1.1): ``publish()``
never blocks the publishing schedule. The caller passes a ``wait_budget_s``
(the free time until its next scheduled event, possibly 0); if the QoS 1
acknowledgement arrives within that budget the puback instant is recorded,
otherwise it is ``None`` and the loop moves on. paho's network thread keeps
handling QoS 1 retransmission regardless. ``drain()`` gives the last
in-flight message(s) a bounded window at end of run. No primary metric
(plan section 7.3) depends on the puback field.

paho-mqtt is imported lazily inside ``PahoPublisher`` so that tests using
only ``InMemoryPublisher`` do not require the dependency at import time.

Lifecycle contract: the caller (CLI) invokes ``connect()`` before handing the
publisher to the runner and ``close()`` after the run finishes; the runner
calls ``publish()`` during the run and ``drain()`` once at the end.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

#: Default bound of the end-of-run drain, aligned with the 60 s post-run
#: confirmation window of plan section 7.3.
DEFAULT_DRAIN_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class PublishResult:
    """Timing evidence for one published message.

    ``publish_monotonic_ns`` is captured immediately before the client
    publish call; ``puback_monotonic_ns`` after the QoS 1 acknowledgement
    (``None`` when the acknowledgement was not observed within the caller's
    wait budget — best-effort capture, CONTRACTS.md section 7).
    """

    publish_monotonic_ns: int
    puback_monotonic_ns: int | None


@runtime_checkable
class Publisher(Protocol):
    """Minimal publishing interface used by the runner."""

    def connect(self) -> None: ...

    def publish(
        self, topic: str, payload: bytes, *, wait_budget_s: float = 0.0
    ) -> PublishResult: ...

    def drain(self, timeout_s: float = DEFAULT_DRAIN_TIMEOUT_S) -> bool: ...

    def close(self) -> None: ...


class InMemoryPublisher:
    """Test double: records (topic, payload, monotonic_ns) tuples in memory.

    ``records`` preserves publish order. Payloads are stored as decoded
    UTF-8 strings for convenient assertions. An optional clock object with a
    ``monotonic_ns()`` method may be injected; the default is
    ``time.monotonic_ns``. Acknowledgement is instantaneous: the puback is
    always captured regardless of the wait budget, and ``drain()`` succeeds
    immediately.
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

    def publish(
        self, topic: str, payload: bytes, *, wait_budget_s: float = 0.0
    ) -> PublishResult:
        now_ns = self._now_ns()
        self.records.append((topic, payload.decode("utf-8"), now_ns))
        return PublishResult(publish_monotonic_ns=now_ns, puback_monotonic_ns=now_ns)

    def drain(self, timeout_s: float = DEFAULT_DRAIN_TIMEOUT_S) -> bool:
        return True

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
    - QoS 1 by default; puback capture is best-effort: ``publish()`` waits
      for the acknowledgement at most ``wait_budget_s`` (the caller's free
      time until its next scheduled event), so publishing throughput is
      never capped by the broker round-trip. Unacknowledged messages stay
      in paho's outgoing queue and are retransmitted by the network thread.
    - ``drain(timeout_s)`` waits (bounded) for the still-unacknowledged
      in-flight messages at end of run; records written with a ``null``
      puback are never revisited (CONTRACTS.md section 7).
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
        reconnect_min_delay_s: float = 1.0,
        reconnect_max_delay_s: float = 30.0,
    ) -> None:
        import paho.mqtt.client as mqtt  # lazy: only needed for real runs

        self.host = host
        self.port = port
        self.qos = qos
        self._keepalive_s = keepalive_s
        self._connect_timeout_s = connect_timeout_s
        self._connected = threading.Event()
        # In-flight MQTTMessageInfo objects, oldest first, pruned on every
        # publish; only drain() ever waits on them. Memory stays negligible
        # next to paho's own outgoing-message queue for the same backlog.
        self._pending: deque = deque()

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

    def _prune_pending(self) -> None:
        """Drop leading pending entries that are acked or permanently failed.

        ``is_published()`` raises RuntimeError/ValueError for messages that
        failed permanently or could not be queued; those will never be
        acknowledged, so they are settled for draining purposes too.
        """
        while self._pending:
            try:
                if not self._pending[0].is_published():
                    break
            except (RuntimeError, ValueError):
                pass  # permanently failed: nothing further to wait for
            self._pending.popleft()

    def publish(
        self, topic: str, payload: bytes, *, wait_budget_s: float = 0.0
    ) -> PublishResult:
        """Publish and capture the puback only if it fits the wait budget.

        Never waits longer than ``wait_budget_s`` (may be 0), so the
        caller's schedule is never delayed by the broker round-trip; QoS 1
        delivery of unacknowledged messages continues in paho's network
        thread (best-effort capture, CONTRACTS.md section 7).
        """
        publish_ns = time.monotonic_ns()
        info = self._client.publish(topic, payload, qos=self.qos)
        self._prune_pending()
        self._pending.append(info)
        acked = False
        try:
            if wait_budget_s > 0.0:
                info.wait_for_publish(timeout=wait_budget_s)
            acked = info.is_published()
        except (RuntimeError, ValueError):
            # Message failed permanently or could not be queued (e.g.
            # queue full while offline): no acknowledgement will come.
            pass
        return PublishResult(
            publish_monotonic_ns=publish_ns,
            puback_monotonic_ns=time.monotonic_ns() if acked else None,
        )

    def drain(self, timeout_s: float = DEFAULT_DRAIN_TIMEOUT_S) -> bool:
        """Bounded end-of-run wait for the remaining in-flight message(s).

        Returns True when every tracked message was acknowledged before the
        shared deadline. Never raises; a False return simply means some
        QoS 1 messages were still unacknowledged when the budget ran out
        (their sent_events records already hold a null puback).
        """
        deadline = time.monotonic() + max(0.0, timeout_s)
        self._prune_pending()
        while self._pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            info = self._pending[0]
            try:
                info.wait_for_publish(timeout=remaining)
                acked = info.is_published()
            except (RuntimeError, ValueError):
                self._pending.popleft()  # permanently failed: settled
                continue
            if not acked:
                break  # deadline hit while waiting on this message
            self._pending.popleft()
        self._prune_pending()
        return not self._pending

    def close(self) -> None:
        """Clean shutdown: DISCONNECT, then stop the network loop thread."""
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()
            self._connected.clear()
