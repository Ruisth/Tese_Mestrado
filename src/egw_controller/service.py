"""Async processing pipeline: validate -> dedupe -> Ditto update -> event log.

Outcome semantics (CONTRACTS.md sections 5 and 9):

- ``accepted``  - validated, fresh and confirmed by a Ditto 2xx;
- ``rejected``  - failed topic/JSON/schema/consistency validation (no Ditto
  call). Consistency covers the topic-versus-payload identity fields and the
  ``message_id`` derivation of CONTRACTS.md section 2;
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
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, NoReturn, Protocol

from .dedupe import DedupeCache
from .ditto import DittoError, build_merge_patch
from .events import ControllerEvent, EventLogger
from .metrics import MetricsCounters
from .schema import SchemaRepository, SchemaValidationError
from .topic import TopicError, parse_topic

logger = logging.getLogger("egw_controller.service")

DEFAULT_QUEUE_MAXSIZE = 10000

_IDENTITY_STR_FIELDS = ("run_id", "message_id", "device_uuid", "device_type")

#: Project-wide UUID v5 namespace (CONTRACTS.md section 2). Deliberately
#: restated here rather than imported from ``egw_simulator.envelope``: the
#: simulator is a separate deliverable and only the controller ships in the
#: deployment image, so the controller must not depend on it at runtime. The
#: controller test suite asserts the two constants are identical, which is
#: what stops them drifting apart silently.
EGW_UUID_NAMESPACE = uuid.UUID("6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0")


class NonStandardJSONConstantError(ValueError):
    """Raised for the ``NaN``/``Infinity``/``-Infinity`` literals in a payload."""


def _reject_json_constant(constant: str) -> NoReturn:
    """``json.loads`` hook refusing the non-standard numeric constants.

    Python's decoder accepts ``NaN``, ``Infinity`` and ``-Infinity`` by
    default even though RFC 8259 has no such literals. A resulting ``nan``
    then evades every schema bound, because each comparison against it is
    false, and would be written to the twin as non-finite data (or fail the
    Ditto update). Refusing them during decoding yields the contracted
    ``rejected`` outcome, with no Ditto call at all, exactly as for any other
    malformed payload.
    """
    raise NonStandardJSONConstantError(
        f"non-standard JSON constant {constant!r} is not permitted"
    )


def derive_message_id(run_id: str, device_uuid: str, seq: int) -> str:
    """Return the contracted ``message_id`` for one envelope.

    UUID v5 over :data:`EGW_UUID_NAMESPACE` with the name
    ``"{run_id}:{device_uuid}:{seq}"`` (CONTRACTS.md section 2).
    """
    return str(uuid.uuid5(EGW_UUID_NAMESPACE, f"{run_id}:{device_uuid}:{seq}"))


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
        """Enqueue a message; called on the event loop via call_soon_threadsafe.

        This is the counting point of ``received`` (CONTRACTS 5): once per
        call, before the capacity decision, so a message dropped on a full
        queue is counted as ``received`` and as ``dropped``.
        """
        self._metrics.increment_received()
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
        """Drain the queue until :meth:`stop` enqueues the shutdown sentinel.

        A taken message is ``in_progress`` until its processing ends, however
        it ends; one that ends without an outcome counter having moved is a
        ``processing_errors`` (CONTRACTS 5).
        """
        while True:
            message = await self._queue.get()
            if message is None:
                break
            # Before the try, with no await since the removal from the queue:
            # the finally below runs if and only if this call ran.
            self._metrics.processing_started()
            try:
                await self.process(message)
            except Exception:  # noqa: BLE001 - keep the pipeline alive
                logger.exception(
                    "unhandled error while processing message",
                    extra={"context": {"topic": message.topic}},
                )
            finally:
                self._metrics.processing_finished()

    async def stop(self) -> None:
        """Request shutdown after the already-queued backlog is drained."""
        await self._queue.put(None)

    async def process(self, message: InboundMessage) -> None:
        """Run one message through validate -> dedupe -> Ditto -> event log.

        A direct call bypasses the queue accounting: only :meth:`submit` and
        :meth:`run` move ``received``, ``in_progress`` and
        ``processing_errors``.
        """
        received = message.received_monotonic_ns

        try:
            decoded: Any = json.loads(
                message.payload.decode("utf-8"),
                parse_constant=_reject_json_constant,
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            NonStandardJSONConstantError,
        ) as exc:
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

        # The schema only proves message_id has the shape of a UUID v5; the
        # contract requires it to BE the UUID v5 of run_id:device_uuid:seq
        # (CONTRACTS.md section 2). Recompute it before the dedupe cache is
        # consulted and before any twin is seeded or patched: replay detection
        # assumes message_id is a pure function of those three fields, so an
        # arbitrary valid-looking id would defeat it.
        forgery = self._message_id_mismatch(payload)
        if forgery is not None:
            self._emit(
                identity=identity,
                received=received,
                outcome="rejected",
                attempts=0,
                error=forgery,
            )
            return

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

    @staticmethod
    def _message_id_mismatch(payload: Mapping[str, Any]) -> str | None:
        """Return a rejection reason when ``message_id`` is not the derived one."""
        expected = derive_message_id(
            payload["run_id"], payload["device_uuid"], payload["seq"]
        )
        if payload["message_id"] != expected:
            return (
                f"message_id mismatch: {payload['message_id']!r} is not the "
                f"UUID v5 derived from run_id:device_uuid:seq "
                f"(expected {expected!r})"
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
