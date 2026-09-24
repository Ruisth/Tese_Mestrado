"""Async processing pipeline: validate -> dedupe -> Ditto update -> event log.

Outcome semantics (CONTRACTS.md sections 5 and 9):

- ``accepted``  - validated, fresh and confirmed by a Ditto 2xx;
- ``rejected``  - failed topic/JSON/schema/consistency validation (no Ditto
  call). Consistency covers the topic-versus-payload identity fields and the
  ``message_id`` derivation of CONTRACTS.md section 2;
- ``duplicate`` - repeated ``message_id``, or non-increasing ``seq`` within
  the same ``run_id`` (CONTRACTS.md section 4, v1.1 run scoping);
- ``failed``    - valid and fresh, but not confirmed: the Ditto update (or
  first-contact seeding) failed after bounded retries, or any other
  exception was raised before the PATCH request returned (ADR 0011, item 8;
  the line names the exception).

Every delivery the consumer takes ends in exactly one outcome line, with
four exceptions that leave no line: the event log cannot be written, the
consumer is cancelled, the process dies, or an exception is raised after
the Ditto 2xx (a ``failed`` line would misreport an applied twin). Those
are the ``processing_errors`` of CONTRACTS 5.

Acknowledgement (ADR 0011): the consumer requests the PUBACK of a QoS 1
delivery only after its line was written, from the flag ``_emit`` sets after
``EventLogger.log`` returned, and before it takes the next delivery. A
delivery that ends without a line closes acknowledgement on its connection
(``end_connection``); the bridge then ends the connection so that the broker
resends every unacknowledged delivery. Deliveries of an ended connection are
purged from the queue (``purge``) and, when one is still taken, skipped;
both are counted ``dropped``, which means "left for redelivery at the next
session resumption". ``stop`` queues nothing: the delivery in progress is
processed to its line and PUBACK, then the consumer exits and the rest of
the queue is left unacknowledged.

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
    """One raw MQTT message bridged into the asyncio pipeline.

    ``mid``, ``qos`` and ``dup`` are the packet identifier, the QoS and the
    DUP flag of the PUBLISH; ``connection`` identifies the bridge connection
    that delivered it. All four are stamped on the network thread (ADR
    0011, item 2). The defaults describe a QoS 0 delivery of no connection.
    """

    topic: str
    payload: bytes
    received_monotonic_ns: int
    mid: int = 0
    qos: int = 0
    dup: bool = False
    connection: int = 0


@dataclass(frozen=True, slots=True)
class _Decision:
    """The outcome decided for one delivery, before its line is written."""

    identity: Mapping[str, Any]
    outcome: str
    attempts: int
    error: str | None
    device_uuid: str | None
    payload: Mapping[str, Any] | None


def _no_acknowledge(message: InboundMessage) -> bool:
    return False


def _no_end_connection(cause: str, message: InboundMessage | None) -> None:
    return None


def _attempts_of(exc: BaseException) -> int:
    """``attempts`` carried by an exception, or 0 (event records need >= 0)."""
    attempts = getattr(exc, "attempts", 0)
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
        return 0
    return attempts


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
        acknowledge: Callable[[InboundMessage], bool] | None = None,
        end_connection: Callable[[str, InboundMessage | None], None] | None = None,
    ) -> None:
        self._repository = repository
        self._dedupe = dedupe
        self._ditto = ditto
        self._events = events
        self._metrics = metrics
        self._monotonic_ns = monotonic_ns
        self._queue: asyncio.Queue[InboundMessage] = asyncio.Queue(
            maxsize=queue_maxsize
        )
        # The bridge's ``ack`` and ``end_connection``; no-ops when unwired.
        self._acknowledge = acknowledge if acknowledge is not None else _no_acknowledge
        self._end_connection = (
            end_connection if end_connection is not None else _no_end_connection
        )
        # Deliveries of a connection below this one are skipped when taken;
        # ``purge`` moves it forward. 0 admits every unstamped delivery.
        self._current_connection = 0
        self._stop_requested = asyncio.Event()
        # Set by submit and stop; the consumer waits on it when the queue is
        # empty instead of on the queue itself (see run).
        self._wake = asyncio.Event()

    def submit(self, message: InboundMessage) -> None:
        """Enqueue a message; called on the event loop via call_soon_threadsafe.

        This is the counting point of ``received`` (CONTRACTS 5): once per
        call, before the capacity decision, so a message dropped on a full
        queue is counted as ``received`` and as ``dropped``. A drop ends
        acknowledgement on the delivery's connection (ADR 0011, item 12): it
        is left for redelivery at the next session resumption.
        """
        self._metrics.increment_received()
        try:
            self._queue.put_nowait(message)
            self._wake.set()
        except asyncio.QueueFull:
            self._metrics.increment_dropped()
            logger.warning(
                "inbound queue full; delivery left for redelivery",
                extra={
                    "context": {
                        "topic": message.topic,
                        "mid": message.mid,
                        "connection": message.connection,
                    }
                },
            )
            self._end_connection("overflow", message)

    def purge(self, ended_connection: int) -> None:
        """Remove the queued deliveries of an ended connection (loop thread).

        Scheduled by the bridge's socket-close handler before any delivery
        of the next connection is submitted. Each removed delivery is
        counted ``dropped`` (the broker resends it); the others keep their
        order. Deliveries of ``ended_connection`` still taken afterwards are
        skipped by :meth:`run`.
        """
        kept: list[InboundMessage] = []
        removed = 0
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if item.connection == ended_connection:
                removed += 1
            else:
                kept.append(item)
        for item in kept:
            self._queue.put_nowait(item)
        for _ in range(removed):
            self._metrics.increment_dropped()
        self._current_connection = max(
            self._current_connection, ended_connection + 1
        )
        logger.info(
            "MQTT connection ended; queued deliveries purged",
            extra={
                "context": {
                    "connection": ended_connection,
                    "purged": removed,
                    "kept": len(kept),
                }
            },
        )

    def queue_depth(self) -> int:
        """Current number of queued inbound messages (for ``GET /metrics``)."""
        return self._queue.qsize()

    async def run(self) -> None:
        """Consume the queue until :meth:`stop` is requested.

        A taken message is ``in_progress`` until its processing ends, however
        it ends; one that ends without an outcome counter having moved is a
        ``processing_errors`` (CONTRACTS 5). A delivery of an ended
        connection is skipped (counted ``dropped``, never in progress). A
        QoS 1 delivery whose line was written is acknowledged before the
        next one is taken; one without a line ends acknowledgement on its
        connection. After the stop request the delivery already taken is
        finished and the loop exits; the queue is left as it is.
        """
        while not self._stop_requested.is_set():
            # The take is synchronous, in the same stretch as the skip or
            # processing_started() below: a reader on the loop never sees a
            # delivery out of queue_depth and in no other term, and a
            # cancellation while waiting takes nothing.
            try:
                message = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                await self._wake.wait()
                self._wake.clear()
                continue
            if message.connection < self._current_connection:
                self._metrics.increment_dropped()
                logger.info(
                    "delivery of an ended connection skipped",
                    extra={
                        "context": {
                            "topic": message.topic,
                            "mid": message.mid,
                            "connection": message.connection,
                            "current_connection": self._current_connection,
                        }
                    },
                )
                continue
            # Before the try, with no await since the removal from the
            # queue: the finally below runs if and only if this call ran.
            self._metrics.processing_started()
            try:
                line = await self.process(message)
                if line:
                    if message.qos == 1:
                        self._acknowledge(message)
                else:
                    self._end_connection("no-outcome-line", message)
            except Exception:  # noqa: BLE001 - keep the pipeline alive
                logger.exception(
                    "unhandled error while processing message",
                    extra={"context": {"topic": message.topic, "mid": message.mid}},
                )
                self._end_connection("no-outcome-line", message)
            finally:
                self._metrics.processing_finished()

    async def stop(self) -> None:
        """Request the consumer to exit after the delivery in progress.

        Nothing is queued (ADR 0011, item 13): the queue keeps its capacity
        and whatever it holds stays unacknowledged for the next process.
        """
        self._stop_requested.set()
        self._wake.set()

    async def _decide(self, message: InboundMessage) -> _Decision:
        """Every stage up to and including the PATCH request.

        Any exception raised here, in the Ditto exchange or elsewhere, ends
        in a ``failed`` decision naming it (ADR 0011, item 8); the four
        exceptions of the module docstring happen outside this method.
        """
        identity = _extract_identity(None)
        try:
            try:
                decoded: Any = json.loads(
                    message.payload.decode("utf-8"),
                    parse_constant=_reject_json_constant,
                )
            except (ValueError, RecursionError) as exc:
                # UnicodeDecodeError, JSONDecodeError and the non-standard
                # constant are all ValueErrors; the digit limit of int
                # conversion is one too; nesting exhausts the stack.
                return _Decision(
                    identity, "rejected", 0, f"invalid JSON payload: {exc}", None, None
                )
            identity = _extract_identity(decoded)

            try:
                topic = parse_topic(message.topic)
            except TopicError as exc:
                return _Decision(identity, "rejected", 0, str(exc), None, None)

            try:
                self._repository.validate(decoded)
            except SchemaValidationError as exc:
                return _Decision(identity, "rejected", 0, str(exc), None, None)
            payload: Mapping[str, Any] = decoded

            mismatch = self._topic_payload_mismatch(
                topic.egw_id, topic.device_uuid, payload
            )
            if mismatch is not None:
                return _Decision(identity, "rejected", 0, mismatch, None, None)

            device_uuid: str = payload["device_uuid"]

            # The schema only proves message_id has the shape of a UUID v5;
            # the contract requires it to BE the UUID v5 of
            # run_id:device_uuid:seq (CONTRACTS.md section 2). Recompute it
            # before the dedupe cache is consulted and before any twin is
            # seeded or patched: replay detection assumes message_id is a
            # pure function of those three fields, so an arbitrary
            # valid-looking id would defeat it.
            forgery = self._message_id_mismatch(payload)
            if forgery is not None:
                return _Decision(identity, "rejected", 0, forgery, None, None)

            # First event for this device since startup: rebuild the dedupe
            # state from the twin's ingestion feature (CONTRACTS.md section
            # 4), creating policy + thing on true first contact.
            if not self._dedupe.known_device(device_uuid):
                try:
                    await self._seed_device(device_uuid, payload)
                except DittoError as exc:
                    return _Decision(
                        identity, "failed", exc.attempts, str(exc), device_uuid, payload
                    )

            reason = self._dedupe.check(
                device_uuid, payload["message_id"], payload["seq"], payload["run_id"]
            )
            if reason is not None:
                return _Decision(identity, "duplicate", 0, reason, device_uuid, payload)

            patch = build_merge_patch(
                payload, self._dedupe.accepted_count(device_uuid) + 1
            )
            try:
                attempts = await self._ditto.patch_thing(device_uuid, patch)
            except DittoError as exc:
                return _Decision(
                    identity, "failed", exc.attempts, str(exc), device_uuid, payload
                )
            return _Decision(identity, "accepted", attempts, None, device_uuid, payload)
        except Exception as exc:  # noqa: BLE001 - one failed line, named
            logger.exception(
                "unhandled error before the Ditto update",
                extra={
                    "context": {
                        "topic": message.topic,
                        "mid": message.mid,
                        "device_uuid": identity["device_uuid"],
                        "seq": identity["seq"],
                    }
                },
            )
            return _Decision(
                identity,
                "failed",
                _attempts_of(exc),
                f"{type(exc).__name__}: {exc}",
                None,
                None,
            )

    async def process(self, message: InboundMessage) -> bool:
        """Run one message through validate -> dedupe -> Ditto -> event log.

        Returns ``True`` once the delivery's outcome line was written (the
        flag :meth:`_emit` sets after ``EventLogger.log`` returned). The
        clock read, the dedupe record and the write run after the decision:
        an exception there is raised with no line (ADR 0011, A1).

        A direct call bypasses the queue accounting: only :meth:`submit` and
        :meth:`run` move ``received``, ``in_progress`` and
        ``processing_errors``.
        """
        received = message.received_monotonic_ns
        decision = await self._decide(message)
        if decision.outcome != "accepted":
            return self._emit(
                identity=decision.identity,
                received=received,
                outcome=decision.outcome,
                attempts=decision.attempts,
                error=decision.error,
            )
        # An accepted decision always carries both (set with the outcome).
        payload: Mapping[str, Any] = decision.payload  # type: ignore[assignment]
        device_uuid: str = decision.device_uuid  # type: ignore[assignment]
        ack = self._monotonic_ns()
        self._dedupe.record(
            device_uuid, payload["message_id"], payload["seq"], payload["run_id"]
        )
        return self._emit(
            identity=decision.identity,
            received=received,
            outcome="accepted",
            attempts=decision.attempts,
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
    ) -> bool:
        """Write the outcome line, count the outcome and return ``True``.

        The flag is set after ``EventLogger.log`` returned, never inferred
        from the absence of an exception: a write that raises leaves it
        unset and propagates.
        """
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
        written = False
        self._events.log(event)
        written = True
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
        return written
