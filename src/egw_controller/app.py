"""FastAPI observability API (CONTRACTS.md section 5, port ``EGW_HTTP_PORT``).

- ``GET /health``            -> ``{"status": "ok"}`` (process alive);
- ``GET /ready``             -> 200 only when MQTT is connected AND Ditto answers,
  503 otherwise;
- ``GET /twins/{device_id}`` -> twin read, normalized by the controller;
- ``GET /metrics``           -> outcome and progress counters + uptime + the
  confirmation marker ``monotonic_ns``/``wall_utc`` (JSON).

``GET /metrics`` carries, additively (existing fields unchanged), the
CONFIRMATION MARKER: ``monotonic_ns`` (``time.monotonic_ns()`` read while
the request is handled) and ``wall_utc`` (the same instant, RFC 3339 UTC).
``monotonic_ns`` shares the clock domain of the ``events.jsonl`` stamps, so
the harness can anchor the end-of-run confirmation deadline on the
controller's clock instead of on the events being judged. It is not a
latency measurement and never enters ``latency_ms`` (CONTRACTS 5).

``GET /metrics`` also carries, additively (2026-09-18, existing fields
unchanged), the PROGRESS COUNTERS ``received``, ``in_progress`` and
``processing_errors``. One response is one snapshot, in which
``received == accepted + rejected + duplicate + failed + dropped +
processing_errors + in_progress + queue_depth`` while the controller runs.
They show the internal state of one controller process only and never
replace reconciliation by identity (CONTRACTS 5; ``metrics.py``).

``GET /metrics`` further carries, additively (ADR 0011, item 14), the three
BRIDGE FIELDS read from the MQTT bridge in the same synchronous stretch:
``mqtt_subscribed`` (boolean: the subscription is granted at QoS 1 on the
current connection), ``mqtt_connection`` (integer: successful CONNACKs of
this process) and ``unacked`` (integer gauge: QoS 1 deliveries handed to
the client on the current connection with no PUBACK requested yet).
``unacked`` is not a term of the accounting identity. Each field is scoped
to one process and never read as zero when absent.

``create_app`` takes injected dependencies (used directly by tests);
``create_app_from_env`` wires the full service + MQTT bridge from ``EGW_*``
environment variables inside a lifespan context. The lifespan stops in the
order of ADR 0011: the consumer first (the delivery in progress recorded
and its PUBACK queued), then the bridge off the event-loop thread (the
DISCONNECT queued after that PUBACK; the join of the network thread never
blocks the loop), then the Ditto client and the event log.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Mapping, Protocol

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .config import Settings
from .dedupe import DedupeCache
from .ditto import THING_NAMESPACE, DittoClient, DittoError, normalize_twin
from .events import EventLogger
from .logging_config import configure_logging
from .metrics import MetricsCounters
from .schema import SchemaRepository
from .service import ControllerService
from .topic import UUID4_RE

logger = logging.getLogger("egw_controller.app")


class TwinReader(Protocol):
    """What the HTTP layer needs from the Ditto client (injectable in tests)."""

    async def get_twin(self, device_uuid: str) -> Mapping[str, Any] | None: ...

    async def is_ready(self) -> bool: ...


def _zero_queue_depth() -> int:
    return 0


def _no_bridge_state() -> Mapping[str, Any]:
    """The bridge fields of a process with no bridge (tests): zero values."""
    return {"mqtt_subscribed": False, "mqtt_connection": 0, "unacked": 0}


@dataclass(slots=True)
class AppDeps:
    """Runtime dependencies of the HTTP endpoints."""

    metrics: MetricsCounters
    ditto: TwinReader
    mqtt_connected: Callable[[], bool]
    queue_depth: Callable[[], int] = _zero_queue_depth
    bridge_state: Callable[[], Mapping[str, Any]] = _no_bridge_state


def create_app(deps: AppDeps, lifespan: Any | None = None) -> FastAPI:
    app = FastAPI(title="egw-controller", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        mqtt_connected = deps.mqtt_connected()
        ditto_ready = await deps.ditto.is_ready()
        is_ready = mqtt_connected and ditto_ready
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={
                "status": "ready" if is_ready else "not_ready",
                "mqtt_connected": mqtt_connected,
                "ditto_ready": ditto_ready,
            },
        )

    @app.get("/twins/{device_id}")
    async def get_twin(device_id: str) -> dict[str, Any]:
        device_uuid = device_id.removeprefix(f"{THING_NAMESPACE}:")
        # Validate before any Ditto call: a malformed id can never name a twin
        # (404); 502 is reserved for genuine Ditto failures.
        if not UUID4_RE.fullmatch(device_uuid):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"invalid device id {device_id!r}: expected a lowercase "
                    f"UUID v4, optionally prefixed with '{THING_NAMESPACE}:'"
                ),
            )
        try:
            twin = await deps.ditto.get_twin(device_uuid)
        except DittoError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if twin is None:
            raise HTTPException(
                status_code=404, detail=f"twin not found for device {device_uuid}"
            )
        return normalize_twin(device_uuid, twin)

    @app.get("/metrics")
    async def metrics() -> dict[str, Any]:
        # snapshot() reads the confirmation marker (monotonic_ns/wall_utc)
        # here, at request handling time (CONTRACTS 5).
        # One response is one snapshot: every term of the accounting
        # identity is written on this event loop, so this handler must stay
        # a coroutine (a plain function would run in a thread pool) with no
        # await between snapshot(), bridge_state() and queue_depth().
        return {
            **deps.metrics.snapshot(),
            **deps.bridge_state(),
            "queue_depth": deps.queue_depth(),
        }

    return app


def create_app_from_env() -> FastAPI:
    """Build the fully wired application from ``EGW_*`` environment variables."""
    # Imported lazily so the HTTP layer stays importable without paho-mqtt.
    from .mqtt import MqttBridge

    configure_logging()
    settings = Settings.from_env()
    repository = SchemaRepository(Path(settings.schema_dir))
    dedupe = DedupeCache()
    metrics = MetricsCounters()
    events = EventLogger(Path(settings.event_log_dir))
    ditto = DittoClient.from_settings(settings)
    # The bridge and the service refer to each other: the bridge hands
    # deliveries and purges to the service, the service acknowledges and
    # ends connections through the bridge. The service's methods are bound
    # late, once it exists.
    bridge = MqttBridge(
        settings,
        lambda message: service.submit(message),
        purge=lambda ended_connection: service.purge(ended_connection),
    )
    service = ControllerService(
        repository=repository,
        dedupe=dedupe,
        ditto=ditto,
        events=events,
        metrics=metrics,
        acknowledge=bridge.ack,
        end_connection=bridge.end_connection,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        pipeline_task = asyncio.create_task(service.run())
        bridge.start(loop)
        try:
            yield
        finally:
            # ADR 0011, item 13: the consumer exits after the delivery in
            # progress (its PUBACK queued), then the bridge disconnects (the
            # DISCONNECT behind that PUBACK) off the loop, since loop_stop
            # joins the network thread; the rest of the queue is left to
            # the broker.
            await service.stop()
            try:
                await pipeline_task
            except asyncio.CancelledError:
                # Awaiting a task that is cancelled raises here, and so
                # does a cancellation of this shutdown itself — which
                # cancels the awaited pipeline too, so the pipeline's
                # state cannot tell the two apart. The shutdown's own
                # cancellation is pending on the current task and
                # propagates after the clean-up below; a pipeline
                # cancelled earlier (A1's second exception; the bridge
                # is halted) is logged and the shutdown goes on.
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise
                logger.error(
                    "the consumer had been cancelled before shutdown; "
                    "nothing was consumed since"
                )
            finally:
                # Each clean-up runs whatever the previous one raised.
                try:
                    await loop.run_in_executor(None, bridge.stop)
                finally:
                    try:
                        await ditto.aclose()
                    finally:
                        events.close()

    deps = AppDeps(
        metrics=metrics,
        ditto=ditto,
        # Ready only with a live consumer: a bridge that is subscribed
        # while nothing consumes would report readiness falsely.
        mqtt_connected=lambda: bridge.connected and service.consuming,
        queue_depth=service.queue_depth,
        bridge_state=bridge.state,
    )
    return create_app(deps, lifespan=lifespan)
