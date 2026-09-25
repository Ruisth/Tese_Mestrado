"""MQTT bridge: paho-mqtt v2 client feeding the asyncio pipeline.

The paho network loop runs on its own thread (``loop_start``); the on_message
callback captures ``time.monotonic_ns()`` at arrival (the latency start point,
CONTRACTS.md section 5), stamps the delivery identity (packet identifier,
QoS, DUP flag and the bridge's current connection) and hands the message to
the asyncio queue via ``loop.call_soon_threadsafe``. QoS 1 subscription to
``EGW_MQTT_TOPIC_FILTER``, TLS + username/password per CONTRACTS.md section 1,
automatic reconnect.

Session and acknowledgement (ADR 0011): the client is built with a
persistent session (``clean_session=False``) and manual acknowledgement
(``manual_ack=True``), both in the constructor. The PUBACK of a QoS 1
delivery is sent by :meth:`MqttBridge.ack`, called by the consumer after the
delivery's outcome line was written, and only while the delivery's connection
is the current one and acknowledgement is still open on it. The connection
identity advances in ``on_socket_close``, which paho runs on every close path
before it clears its queued packets; the identity check and the ``client.ack``
call happen under the one lock the close handler also takes, so no PUBACK for
an ended connection reaches the next one. The close handler schedules the
purge of the ended connection's queued deliveries onto the event loop.

Ending a connection (A3(a), in process): :meth:`MqttBridge.end_connection`
closes acknowledgement on the current connection, records the occurrence and
wakes the supervisor thread, which runs ``disconnect()``, ``loop_stop()``, a
back-off, ``connect_async()`` and ``loop_start()``; the broker then resends
every unacknowledged delivery on the resumed session. The repetition is
bounded: beyond ``A5_BOUND`` consecutive ends without an acknowledged
delivery the client is left disconnected, in a visible state (``/ready``
503, ``mqtt_subscribed`` false, ``/metrics`` still served).

Readiness: ``connected`` is true only after the broker's SUBACK grants the
subscription at QoS 1 (``on_subscribe``). A QoS 0 grant would silently
disable every acknowledgement, so it leaves the bridge not ready; a denied
SUBACK (reason code >= 0x80, e.g. by broker ACLs) never becomes ready.

``state()`` gives ``/metrics`` its three additive fields: ``mqtt_subscribed``,
``mqtt_connection`` (successful CONNACKs of this process) and ``unacked``
(QoS 1 deliveries handed to the client on the current connection for which
no PUBACK has been requested), all kept under the bridge's own lock because
nothing may update ``MetricsCounters`` from the network thread.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Mapping

from paho.mqtt.client import MQTT_ERR_SUCCESS, CallbackAPIVersion, Client

from .config import Settings
from .service import InboundMessage

logger = logging.getLogger("egw_controller.mqtt")

_RECONNECT_MIN_DELAY_S = 1
_RECONNECT_MAX_DELAY_S = 30
_KEEPALIVE_S = 60

# MQTT SUBACK reason codes: we request QoS 1 and accept only a QoS 1 grant
# (ADR 0011, item 11); a QoS 0 downgrade keeps the bridge not ready; values
# >= 0x80 are failures.
_GRANTED_QOS = (1,)
_SUBACK_FAILURE_FLOOR = 0x80

#: Consecutive connection ends (with no delivery acknowledged in between)
#: after which the supervisor leaves the client disconnected (A5).
A5_BOUND = 10

_SUPERVISOR_THREAD_NAME = "egw-mqtt-supervisor"

#: Causes of a connection end, as recorded in the log line.
END_CAUSES = (
    "no-outcome-line",
    "overflow",
    "no-event-loop",
    "on-message-error",
    "consumer-cancelled",
    "stop",
)


def default_backoff_s(occurrence: int) -> float:
    """Back-off before the n-th consecutive reconnection: 1, 2, 4 ... 30 s."""
    return float(
        min(_RECONNECT_MIN_DELAY_S * 2 ** (max(occurrence, 1) - 1), _RECONNECT_MAX_DELAY_S)
    )


def _reason_value(reason_code: Any) -> int:
    """Best-effort integer value of a paho ReasonCode (or plain int)."""
    value = getattr(reason_code, "value", reason_code)
    try:
        return int(value)
    except (TypeError, ValueError):
        return _SUBACK_FAILURE_FLOOR


def _delivery_context(identity: Mapping[str, Any] | InboundMessage | None) -> Any:
    """The identity in progress, as the connection-end record carries it."""
    if identity is None:
        return None
    if isinstance(identity, InboundMessage):
        return {
            "topic": identity.topic,
            "mid": identity.mid,
            "qos": identity.qos,
            "dup": identity.dup,
            "connection": identity.connection,
            "received_monotonic_ns": identity.received_monotonic_ns,
        }
    return dict(identity)


class MqttBridge:
    """Owns the paho client thread and bridges messages into the event loop."""

    def __init__(
        self,
        settings: Settings,
        submit: Callable[[InboundMessage], None],
        *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        client: Client | None = None,
        purge: Callable[[int], None] | None = None,
        backoff_s: Callable[[int], float] = default_backoff_s,
        end_bound: int = A5_BOUND,
    ) -> None:
        self._settings = settings
        self._submit = submit
        self._purge = purge
        self._monotonic_ns = monotonic_ns
        self._backoff_s = backoff_s
        self._end_bound = end_bound
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sub_mid: int | None = None
        # Connection state, all under one lock (D-2): the identity of the
        # current connection (1 before the first CONNACK; advanced at every
        # socket close), whether a PUBACK may still be requested on it, the
        # deliveries handed over on it without a PUBACK, the successful
        # CONNACKs of the process, the subscription grant, and the count
        # of consecutive connection ends (reset by an acknowledged delivery).
        # Re-entrant because ack() calls client.ack under it: with the
        # network thread absent paho writes on the caller's thread and a
        # write error would run on_socket_close on that same thread.
        self._state_lock = threading.RLock()
        self._conn = 1
        self._ack_open = True
        self._unacked = 0
        self._connections = 0
        self._subscribed = False
        self._ends_in_a_row = 0
        # Set when the consumer was cancelled: the supervisor then leaves the
        # client disconnected, since nothing consumes any more.
        self._halted = False
        # The supervisor thread runs the A3(a) sequence off the loop and off
        # the network thread (loop_stop joins the latter).
        self._signal = threading.Event()
        self._stopping = threading.Event()
        self._supervisor: threading.Thread | None = None
        self._client = client if client is not None else self._build_client()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.on_subscribe = self._on_subscribe
        self._client.on_socket_close = self._on_socket_close

    def _build_client(self) -> Client:
        settings = self._settings
        client = Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=f"egw-controller-{settings.egw_id}",
            # Persistent session and manual acknowledgement, in the
            # constructor (ADR 0011, item 1): the broker keeps every
            # unacknowledged QoS 1 delivery for the next session resumption.
            clean_session=False,
            manual_ack=True,
        )
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            # ca_certs=None falls back to the system trust store.
            client.tls_set(ca_certs=settings.mqtt_ca_cert)
        client.reconnect_delay_set(
            min_delay=_RECONNECT_MIN_DELAY_S, max_delay=_RECONNECT_MAX_DELAY_S
        )
        return client

    # -- paho callbacks (network thread) ------------------------------------

    def _on_connect(
        self,
        client: Client,
        userdata: Any,
        connect_flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        if bool(getattr(reason_code, "is_failure", False)):
            logger.error(
                "MQTT connect failed",
                extra={"context": {"reason_code": str(reason_code)}},
            )
            return
        with self._state_lock:
            self._connections += 1
            connections = self._connections
        session_present = getattr(connect_flags, "session_present", None)
        result, mid = client.subscribe(self._settings.mqtt_topic_filter, qos=1)
        if result != MQTT_ERR_SUCCESS:
            logger.error(
                "MQTT subscribe request failed; staying not ready",
                extra={
                    "context": {
                        "result": int(result),
                        "topic_filter": self._settings.mqtt_topic_filter,
                    }
                },
            )
            return
        self._sub_mid = mid
        # Not ready yet: the subscribed flag is only set once the SUBACK
        # grants the subscription at QoS 1 (see _on_subscribe).
        logger.info(
            "MQTT connected; subscription requested",
            extra={
                "context": {
                    "host": self._settings.mqtt_host,
                    "port": self._settings.mqtt_port,
                    "topic_filter": self._settings.mqtt_topic_filter,
                    "mqtt_connection": connections,
                    "session_present": session_present,
                }
            },
        )

    def _on_subscribe(
        self,
        client: Client,
        userdata: Any,
        mid: int,
        reason_codes: Any,
        properties: Any = None,
    ) -> None:
        if self._sub_mid is not None and mid != self._sub_mid:
            logger.warning(
                "SUBACK for unexpected mid; ignoring",
                extra={"context": {"mid": mid, "expected_mid": self._sub_mid}},
            )
            return
        codes = (
            list(reason_codes)
            if isinstance(reason_codes, (list, tuple))
            else [reason_codes]
        )
        value = _reason_value(codes[0]) if codes else _SUBACK_FAILURE_FLOOR
        context = {
            "granted_qos": value,
            "topic_filter": self._settings.mqtt_topic_filter,
        }
        if value in _GRANTED_QOS:
            with self._state_lock:
                self._subscribed = True
            logger.info(
                "MQTT subscription granted; bridge ready", extra={"context": context}
            )
        elif value < _SUBACK_FAILURE_FLOOR:
            with self._state_lock:
                self._subscribed = False
            logger.error(
                "MQTT subscription granted at QoS 0; staying not ready",
                extra={"context": context},
            )
        else:
            with self._state_lock:
                self._subscribed = False
            logger.error(
                "MQTT subscription denied; staying not ready",
                extra={"context": {"reason_code": value, **context}},
            )

    def _on_disconnect(
        self,
        client: Client,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        with self._state_lock:
            self._subscribed = False
        self._sub_mid = None
        logger.warning(
            "MQTT disconnected",
            extra={"context": {"reason_code": str(reason_code)}},
        )

    def _on_socket_close(self, client: Client, userdata: Any, sock: Any) -> None:
        """Advance the connection identity; paho runs this on every close
        path, before it clears its queued packets. It never raises: an
        exception here would kill the network thread."""
        try:
            with self._state_lock:
                ended = self._conn
                self._conn += 1
                self._ack_open = True
                self._unacked = 0
                self._subscribed = False
            self._sub_mid = None
            loop = self._loop
            if self._purge is not None and loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(self._purge, ended)
            logger.info(
                "MQTT socket closed; connection ended",
                extra={"context": {"connection": ended, "next_connection": ended + 1}},
            )
        except Exception:  # noqa: BLE001 - the handler must never raise
            logger.exception("MQTT on_socket_close failed")

    def _on_message(self, client: Client, userdata: Any, message: Any) -> None:
        """Stamp the delivery and hand it to the loop; never raises (item 10)."""
        try:
            # Latency measurement starts here, on the network thread, at
            # arrival. The delivery is counted in unacked as soon as it is
            # in the client's hands, before anything that could fail.
            received_monotonic_ns = self._monotonic_ns()
            qos = int(message.qos)
            with self._state_lock:
                connection = self._conn
                if qos == 1:
                    self._unacked += 1
            loop = self._loop
            if loop is None or loop.is_closed():
                logger.warning(
                    "message received without an event loop; left for redelivery",
                    extra={"context": {"mid": int(message.mid), "qos": qos}},
                )
                self.end_connection("no-event-loop", None)
                return
            inbound = InboundMessage(
                topic=message.topic,
                payload=bytes(message.payload),
                received_monotonic_ns=received_monotonic_ns,
                mid=int(message.mid),
                qos=qos,
                dup=bool(message.dup),
                connection=connection,
            )
            loop.call_soon_threadsafe(self._submit, inbound)
        except Exception:  # noqa: BLE001 - the callback must never raise
            logger.exception("MQTT on_message failed")
            with self._state_lock:
                self._subscribed = False
            self.end_connection("on-message-error", None)

    # -- acknowledgement and connection end (any thread) ---------------------

    def ack(self, delivery: InboundMessage) -> bool:
        """Request the PUBACK of ``delivery``; True when it was queued.

        Sends nothing unless the delivery is QoS 1, of the current
        connection, and acknowledgement is still open on it. ``client.ack``
        is one unlocked deque append plus a loopback byte with the network
        thread alive: it takes no paho mutex, so it is called under the
        bridge lock, the same lock the close handler takes.
        """
        with self._state_lock:
            if not (
                delivery.qos == 1
                and delivery.connection == self._conn
                and self._ack_open
            ):
                return False
            rc = self._client.ack(delivery.mid, 1)
            if self._unacked > 0:
                self._unacked -= 1
            self._ends_in_a_row = 0
            unacked = self._unacked
        logger.debug(
            "PUBACK requested",
            extra={
                "context": {
                    "mid": delivery.mid,
                    "connection": delivery.connection,
                    "rc": int(rc),
                    "unacked": unacked,
                }
            },
        )
        return True

    def end_connection(
        self, cause: str, identity: Mapping[str, Any] | InboundMessage | None
    ) -> int | None:
        """Close acknowledgement on the current connection and end it.

        Returns the number of the connection it closed, or None when
        acknowledgement was already closed on it. Records the occurrence,
        schedules the purge of that connection's queued deliveries onto
        the event loop at once — before the socket closes, so no later
        delivery of the ended connection is processed — and wakes the
        supervisor, which reconnects after a back-off or, beyond the
        bound, leaves the client disconnected. One connection counts one
        occurrence (A5): the first call closes acknowledgement on it and
        requests the end; a later call on the same connection — a further
        delivery that could not be acknowledged before the socket closed —
        is logged and changes nothing. The cause ``consumer-cancelled``
        halts the bridge: the supervisor disconnects and does not
        reconnect, since nothing consumes any more. The cause ``stop``
        (graceful) only closes acknowledgement: it is recorded at INFO and
        counts no occurrence.
        """
        with self._state_lock:
            was_open = self._ack_open
            self._ack_open = False
            connection = self._conn
            if cause != "stop" and was_open:
                self._ends_in_a_row += 1
            if cause == "consumer-cancelled":
                # The consumer is gone whatever the connection's state:
                # the supervisor must not reconnect, even if an earlier
                # end request already closed acknowledgement here.
                self._halted = True
            occurrence = self._ends_in_a_row
        if cause != "stop" and not was_open:
            logger.info(
                "MQTT connection end already requested; acknowledgement closed",
                extra={
                    "context": {
                        "cause": cause,
                        "connection": connection,
                        "identity": _delivery_context(identity),
                        "occurrence": occurrence,
                    }
                },
            )
            if cause == "consumer-cancelled":
                # No new occurrence, but the supervisor is woken so that
                # a reconnection already under way, or completed, is
                # undone: nothing consumes any more.
                self._signal.set()
            return None
        # The ended connection's queued deliveries are retired now, not only
        # at the socket close: the consumer must not advance the twin or
        # the cache with a later delivery of a connection whose earlier
        # delivery is left to the broker to resend.
        loop = self._loop
        if (
            cause != "stop"
            and self._purge is not None
            and loop is not None
            and not loop.is_closed()
        ):
            loop.call_soon_threadsafe(self._purge, connection)
        context = {
            "cause": cause,
            "connection": connection,
            "identity": _delivery_context(identity),
            "occurrence": occurrence,
            "backoff_s": self._backoff_s(occurrence) if cause != "stop" else 0.0,
        }
        if cause == "stop":
            logger.info(
                "MQTT connection ended by the controller", extra={"context": context}
            )
            return connection
        logger.error(
            "MQTT connection ended by the controller", extra={"context": context}
        )
        self._signal.set()
        return connection

    # -- supervisor thread ---------------------------------------------------

    def _supervise(self) -> None:
        while not self._stopping.is_set():
            self._signal.wait()
            self._signal.clear()
            if self._stopping.is_set():
                return
            try:
                self._reconnect_once()
            except Exception:  # noqa: BLE001 - the supervisor must survive
                logger.exception("MQTT supervisor failed")

    def _reconnect_once(self) -> None:
        with self._state_lock:
            occurrence = self._ends_in_a_row
            connection = self._conn
        context = {
            "occurrence": occurrence,
            "bound": self._end_bound,
            "connection": connection,
        }
        # disconnect() queues the DISCONNECT behind every PUBACK already
        # queued; loop_stop() joins the network thread, which writes them
        # in order and exits. paho does not reconnect after a client
        # disconnect, so the reconnection is explicit below.
        self._client.disconnect()
        self._client.loop_stop()
        with self._state_lock:
            self._subscribed = False
            halted = self._halted
        if halted:
            logger.error(
                "MQTT consumer gone; staying disconnected",
                extra={"context": context},
            )
            return
        if occurrence > self._end_bound:
            logger.error(
                "MQTT reconnection bound reached; staying disconnected",
                extra={"context": context},
            )
            return
        delay = self._backoff_s(occurrence)
        if delay > 0 and self._stopping.wait(delay):
            return
        with self._state_lock:
            halted = self._halted
        if halted:
            # The consumer was cancelled during the back-off.
            logger.error(
                "MQTT consumer gone; staying disconnected",
                extra={"context": context},
            )
            return
        self._client.connect_async(
            self._settings.mqtt_host, self._settings.mqtt_port, keepalive=_KEEPALIVE_S
        )
        self._client.loop_start()
        logger.info(
            "MQTT reconnection requested",
            extra={"context": {**context, "backoff_s": delay}},
        )

    # -- lifecycle (event-loop thread) ---------------------------------------

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Attach to the running event loop and start the network thread."""
        self._loop = loop if loop is not None else asyncio.get_running_loop()
        self._stopping.clear()
        with self._state_lock:
            self._halted = False
        if self._supervisor is None or not self._supervisor.is_alive():
            self._supervisor = threading.Thread(
                target=self._supervise, name=_SUPERVISOR_THREAD_NAME, daemon=True
            )
            self._supervisor.start()
        self._client.connect_async(
            self._settings.mqtt_host, self._settings.mqtt_port, keepalive=_KEEPALIVE_S
        )
        self._client.loop_start()

    def stop(self) -> None:
        """Stop the supervisor, disconnect and stop the network thread.

        ``loop_stop`` joins the network thread; the caller runs this off the
        event loop (``run_in_executor``) so the join never blocks it. Called
        after the consumer exited, so the PUBACK of the delivery in progress
        is queued before the DISCONNECT.
        """
        self._stopping.set()
        self._signal.set()
        supervisor = self._supervisor
        if supervisor is not None and supervisor.is_alive():
            if threading.current_thread() is not supervisor:
                supervisor.join()
        self.end_connection("stop", None)
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()
            with self._state_lock:
                self._subscribed = False
            self._sub_mid = None

    def state(self) -> dict[str, Any]:
        """The three additive ``/metrics`` fields, read under the lock."""
        with self._state_lock:
            return {
                "mqtt_subscribed": self._subscribed,
                "mqtt_connection": self._connections,
                "unacked": self._unacked,
            }

    @property
    def connected(self) -> bool:
        with self._state_lock:
            return self._subscribed
