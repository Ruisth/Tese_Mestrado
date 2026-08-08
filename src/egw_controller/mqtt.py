"""MQTT bridge: paho-mqtt v2 client feeding the asyncio pipeline.

The paho network loop runs on its own thread (``loop_start``); the on_message
callback captures ``time.monotonic_ns()`` at arrival (the latency start point,
CONTRACTS.md section 5) and hands the message to the asyncio queue via
``loop.call_soon_threadsafe``. QoS 1 subscription to ``EGW_MQTT_TOPIC_FILTER``,
TLS + username/password per CONTRACTS.md section 1, automatic reconnect.

Readiness: the ``connected`` flag is set only after the broker's SUBACK grants
the subscription at QoS 0 or 1 (``on_subscribe``). A connection whose SUBACK is
denied (reason code >= 0x80, e.g. by broker ACLs) never becomes ready.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable

from paho.mqtt.client import MQTT_ERR_SUCCESS, CallbackAPIVersion, Client

from .config import Settings
from .service import InboundMessage

logger = logging.getLogger("egw_controller.mqtt")

_RECONNECT_MIN_DELAY_S = 1
_RECONNECT_MAX_DELAY_S = 30
_KEEPALIVE_S = 60

# MQTT SUBACK reason codes: granted QoS 0/1 (we request QoS 1, so the broker
# may grant 1 or downgrade to 0); values >= 0x80 are failures.
_GRANTED_QOS = (0, 1)
_SUBACK_FAILURE_FLOOR = 0x80


def _reason_value(reason_code: Any) -> int:
    """Best-effort integer value of a paho ReasonCode (or plain int)."""
    value = getattr(reason_code, "value", reason_code)
    try:
        return int(value)
    except (TypeError, ValueError):
        return _SUBACK_FAILURE_FLOOR


class MqttBridge:
    """Owns the paho client thread and bridges messages into the event loop."""

    def __init__(
        self,
        settings: Settings,
        submit: Callable[[InboundMessage], None],
        *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        client: Client | None = None,
    ) -> None:
        self._settings = settings
        self._submit = submit
        self._monotonic_ns = monotonic_ns
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = threading.Event()
        self._sub_mid: int | None = None
        self._client = client if client is not None else self._build_client()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.on_subscribe = self._on_subscribe

    def _build_client(self) -> Client:
        settings = self._settings
        client = Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=f"egw-controller-{settings.egw_id}",
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
        # Not ready yet: the connected flag is only set once the SUBACK
        # grants the subscription (see _on_subscribe).
        logger.info(
            "MQTT connected; subscription requested",
            extra={
                "context": {
                    "host": self._settings.mqtt_host,
                    "port": self._settings.mqtt_port,
                    "topic_filter": self._settings.mqtt_topic_filter,
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
        if value in _GRANTED_QOS:
            self._connected.set()
            logger.info(
                "MQTT subscription granted; bridge ready",
                extra={
                    "context": {
                        "granted_qos": value,
                        "topic_filter": self._settings.mqtt_topic_filter,
                    }
                },
            )
        else:
            self._connected.clear()
            logger.error(
                "MQTT subscription denied; staying not ready",
                extra={
                    "context": {
                        "reason_code": value,
                        "topic_filter": self._settings.mqtt_topic_filter,
                    }
                },
            )

    def _on_disconnect(
        self,
        client: Client,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        self._connected.clear()
        self._sub_mid = None
        logger.warning(
            "MQTT disconnected",
            extra={"context": {"reason_code": str(reason_code)}},
        )

    def _on_message(self, client: Client, userdata: Any, message: Any) -> None:
        # Latency measurement starts here, on the network thread, at arrival.
        received_monotonic_ns = self._monotonic_ns()
        loop = self._loop
        if loop is None or loop.is_closed():
            logger.warning("message received before bridge start; dropping")
            return
        inbound = InboundMessage(
            topic=message.topic,
            payload=bytes(message.payload),
            received_monotonic_ns=received_monotonic_ns,
        )
        loop.call_soon_threadsafe(self._submit, inbound)

    # -- lifecycle (event-loop thread) ---------------------------------------

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Attach to the running event loop and start the network thread."""
        self._loop = loop if loop is not None else asyncio.get_running_loop()
        self._client.connect_async(
            self._settings.mqtt_host, self._settings.mqtt_port, keepalive=_KEEPALIVE_S
        )
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()
            self._connected.clear()
            self._sub_mid = None

    @property
    def connected(self) -> bool:
        return self._connected.is_set()
