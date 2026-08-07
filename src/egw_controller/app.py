"""FastAPI observability API (CONTRACTS.md section 5, port ``EGW_HTTP_PORT``).

- ``GET /health``            -> ``{"status": "ok"}`` (process alive);
- ``GET /ready``             -> 200 only when MQTT is connected AND Ditto answers,
  503 otherwise;
- ``GET /twins/{device_id}`` -> twin read, normalized by the controller;
- ``GET /metrics``           -> outcome counters + uptime (JSON).

``create_app`` takes injected dependencies (used directly by tests);
``create_app_from_env`` wires the full service + MQTT bridge from ``EGW_*``
environment variables inside a lifespan context.
"""

from __future__ import annotations

import asyncio
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


class TwinReader(Protocol):
    """What the HTTP layer needs from the Ditto client (injectable in tests)."""

    async def get_twin(self, device_uuid: str) -> Mapping[str, Any] | None: ...

    async def is_ready(self) -> bool: ...


@dataclass(slots=True)
class AppDeps:
    """Runtime dependencies of the HTTP endpoints."""

    metrics: MetricsCounters
    ditto: TwinReader
    mqtt_connected: Callable[[], bool]


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
        return deps.metrics.snapshot()

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
    service = ControllerService(
        repository=repository,
        dedupe=dedupe,
        ditto=ditto,
        events=events,
        metrics=metrics,
    )
    bridge = MqttBridge(settings, service.submit)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pipeline_task = asyncio.create_task(service.run())
        bridge.start(asyncio.get_running_loop())
        try:
            yield
        finally:
            bridge.stop()
            await service.stop()
            await pipeline_task
            await ditto.aclose()
            events.close()

    deps = AppDeps(
        metrics=metrics,
        ditto=ditto,
        mqtt_connected=lambda: bridge.connected,
    )
    return create_app(deps, lifespan=lifespan)
