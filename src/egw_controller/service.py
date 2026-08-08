"""Async processing pipeline: validate -> dedupe -> Ditto update -> event log.

Outcome semantics (CONTRACTS.md sections 5 and 9):

- ``accepted``  - validated, fresh and confirmed by a Ditto 2xx;
- ``rejected``  - failed topic/JSON/schema/consistency validation (no Ditto call);
- ``duplicate`` - repeated ``message_id``, or non-increasing ``seq`` within
  the same ``run_id`` (CONTRACTS.md section 4, v1.1 run scoping);
- ``failed``    - valid and fresh, but the Ditto update (or first-contact
  seeding) failed after bounded retries.

Latency: ``received_monotonic_ns`` is captured in the MQTT callback thread at
message arrival; ``ditto_ack_monotonic_ns`` after the 2xx response;
``latency_ms = (ack - received) / 1e6``. Non-accepted events carry null ack
and latency.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from .dedupe import DedupeCache
from .ditto import DittoError, build_merge_patch
from .events import ControllerEvent, EventLogger
from .metrics import MetricsCounters
from .schema import SchemaRepository, SchemaValidationError
from .topic import TopicError, parse_topic

logger = logging.getLogger("egw_controller.service")

DEFAULT_QUEUE_MAXSIZE = 10000

_IDENTITY_STR_FIELDS = ("run_id", "message_id", "device_uuid", "device_type")


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """One raw MQTT message bridged into the asyncio pipeline."""

    topic: str
    payload: bytes
    received_monotonic_ns: int


class DittoClientLike(Protocol):
    """The subset of the Ditto client the pipeline depends on (injectable)."""

    async def get_twin(self, device_uuid: str) -> Mapping[str, Any] | None: ...

    async def ensure_twin(
        self,
        *,
        device_uuid: str,
        device_type: str,
        egw_id: str,
        schema_version: str,
    ) -> int: ...

    async def patch_thing(
        self, device_uuid: str, patch: Mapping[str, Any]
    ) -> int: ...

    async def is_ready(self) -> bool: ...


def _extract_identity(decoded: Any) -> dict[str, Any]:
    """Best-effort extraction of envelope identity fields for event records."""
    identity: dict[str, Any] = {field: None for field in _IDENTITY_STR_FIELDS}
    identity["seq"] = None
    if isinstance(decoded, Mapping):
        for field in _IDENTITY_STR_FIELDS:
            value = decoded.get(field)
            if isinstance(value, str):
                identity[field] = value
        seq = decoded.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            identity["seq"] = seq
    return identity


class ControllerService:
    """Single-consumer pipeline draining the MQTT bridge queue.

    All collaborators (Ditto client, event logger, metrics, clock) are
    dependency-injected; the class holds no global state.
    """

    def __init__(
        self,
        *,
        repository: SchemaRepository,
        dedupe: DedupeCache,
        ditto: DittoClientLike,
        events: EventLogger,
        metrics: MetricsCounters,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        queue_maxsize: int = DEFAULT_QUEUE_MAXSIZE,
    ) -> None:
        self._repository = repository
        self._dedupe = dedupe
        self._ditto = ditto
        self._events = events
        self._metrics = metrics
        self._monotonic_ns = monotonic_ns
        self._queue: asyncio.Queue[InboundMessage | None] = asyncio.Queue(
            maxsize=queue_maxsize
        )

    def submit(self, message: InboundMessage) -> None:
        """Enqueue a message; called on the event loop via call_soon_threadsafe."""
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            self._metrics.increment_dropped()
            logger.warning(
                "inbound queue full; dropping message",
                extra={"context": {"topic": message.topic}},
            )

    def queue_depth(self) -> int:
        """Current number of queued inbound messages (for ``GET /metrics``)."""
        return self._queue.qsize()

    async def run(self) -> None:
        """Drain the queue until :meth:`stop` enqueues the shutdown sentinel."""
        while True:
            message = await self._queue.get()
            if message is None:
                break
            try:
                await self.process(message)
            except Exception:  # noqa: BLE001 - keep the pipeline alive
                logger.exception(
                    "unhandled error while processing message",
                    extra={"context": {"topic": message.topic}},
                )

    async def stop(self) -> None:
        """Request shutdown after the already-queued backlog is drained."""
        await self._queue.put(None)

    async def process(self, message: InboundMessage) -> None:
        """Run one message through validate -> dedupe -> Ditto -> event log."""
        received = message.received_monotonic_ns

        try:
            decoded: Any = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._emit(
                identity=_extract_identity(None),
                received=received,
                outcome="rejected",
                attempts=0,
                error=f"invalid JSON payload: {exc}",
            )
            return
        identity = _extract_identity(decoded)

        try:
            topic = parse_topic(message.topic)
        except TopicError as exc:
            self._emit(
                identity=identity,
                received=received,
                outcome="rejected",
                attempts=0,
                error=str(exc),
            )
            return

        try:
            self._repository.validate(decoded)
        except SchemaValidationError as exc:
            self._emit(
                identity=identity,
                received=received,
                outcome="rejected",
                attempts=0,
                error=str(exc),
            )
            return
        payload: Mapping[str, Any] = decoded

        mismatch = self._topic_payload_mismatch(topic.egw_id, topic.device_uuid, payload)
        if mismatch is not None:
            self._emit(
                identity=identity,
                received=received,
                outcome="rejected",
                attempts=0,
                error=mismatch,
            )
            return

        device_uuid: str = payload["device_uuid"]

        # First event for this device since startup: rebuild the dedupe state
        # from the twin's ingestion feature (CONTRACTS.md section 4), creating
        # policy + thing on true first contact.
        if not self._dedupe.known_device(device_uuid):
            try:
                await self._seed_device(device_uuid, payload)
            except DittoError as exc:
                self._emit(
                    identity=identity,
                    received=received,
                    outcome="failed",
                    attempts=exc.attempts,
                    error=str(exc),
                )
                return

        reason = self._dedupe.check(
            device_uuid, payload["message_id"], payload["seq"], payload["run_id"]
        )
        if reason is not None:
            self._emit(
                identity=identity,
                received=received,
                outcome="duplicate",
                attempts=0,
                error=reason,
            )
            return

        patch = build_merge_patch(
            payload, self._dedupe.accepted_count(device_uuid) + 1
        )
        try:
            attempts = await self._ditto.patch_thing(device_uuid, patch)
        except DittoError as exc:
            self._emit(
                identity=identity,
                received=received,
                outcome="failed",
                attempts=exc.attempts,
                error=str(exc),
            )
            return

        ack = self._monotonic_ns()
        self._dedupe.record(
            device_uuid, payload["message_id"], payload["seq"], payload["run_id"]
        )
        self._emit(
            identity=identity,
            received=received,
            outcome="accepted",
            attempts=attempts,
            error=None,
            ack=ack,
            latency_ms=(ack - received) / 1e6,
        )

    @staticmethod
    def _topic_payload_mismatch(
        topic_egw_id: str, topic_device_uuid: str, payload: Mapping[str, Any]
    ) -> str | None:
        if payload["device_uuid"] != topic_device_uuid:
            return (
                f"device_uuid mismatch: topic {topic_device_uuid!r} vs "
                f"payload {payload['device_uuid']!r}"
            )
        if payload["egw_id"] != topic_egw_id:
            return (
                f"egw_id mismatch: topic {topic_egw_id!r} vs "
                f"payload {payload['egw_id']!r}"
            )
        return None

    async def _seed_device(
        self, device_uuid: str, payload: Mapping[str, Any]
    ) -> None:
        twin = await self._ditto.get_twin(device_uuid)
        if twin is None:
            await self._ditto.ensure_twin(
                device_uuid=device_uuid,
                device_type=payload["device_type"],
                egw_id=payload["egw_id"],
                schema_version=payload["schema_version"],
            )
            self._dedupe.seed_from_twin(device_uuid, None)
        else:
            self._dedupe.seed_from_twin(device_uuid, twin)

    def _emit(
        self,
        *,
        identity: Mapping[str, Any],
        received: int,
        outcome: str,
        attempts: int,
        error: str | None,
        ack: int | None = None,
        latency_ms: float | None = None,
    ) -> None:
        event = ControllerEvent(
            run_id=identity["run_id"],
            message_id=identity["message_id"],
            device_uuid=identity["device_uuid"],
            device_type=identity["device_type"],
            seq=identity["seq"],
            received_monotonic_ns=received,
            ditto_ack_monotonic_ns=ack,
            latency_ms=latency_ms,
            outcome=outcome,
            attempts=attempts,
            error=error,
        )
        self._events.log(event)
        self._metrics.increment(outcome)
        log = logger.debug if outcome == "accepted" else logger.info
        log(
            "telemetry event processed",
            extra={
                "context": {
                    "outcome": outcome,
                    "device_uuid": identity["device_uuid"],
                    "seq": identity["seq"],
                    "attempts": attempts,
                    "error": error,
                }
            },
        )
