"""FastAPI endpoint tests (CONTRACTS.md section 5) via httpx ASGITransport.

The service layer is faked: readiness flags and twin reads come from
``FakeDittoClient``/lambdas, so no MQTT broker or Ditto instance is needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator

import httpx
import pytest

from egw_controller.app import AppDeps, create_app
from egw_controller.ditto import DittoUnavailableError
from egw_controller.metrics import MetricsCounters
from test_controller_helpers import DEVICE_UUIDS, FakeDittoClient, make_raw_twin

WATCH = DEVICE_UUIDS["smartwatch"]


class FakeMonotonicClock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class MutableFlag:
    def __init__(self, value: bool = True) -> None:
        self.value = value

    def __call__(self) -> bool:
        return self.value


@pytest.fixture
def clock() -> FakeMonotonicClock:
    return FakeMonotonicClock()


@pytest.fixture
def metrics(clock: FakeMonotonicClock) -> MetricsCounters:
    return MetricsCounters(
        monotonic=clock,
        now=lambda: datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def ditto() -> FakeDittoClient:
    return FakeDittoClient(
        twins={WATCH: make_raw_twin(WATCH, last_seq=3, accepted_count=4)}
    )


@pytest.fixture
def mqtt_flag() -> MutableFlag:
    return MutableFlag(True)


@pytest.fixture
def deps(
    metrics: MetricsCounters, ditto: FakeDittoClient, mqtt_flag: MutableFlag
) -> AppDeps:
    return AppDeps(metrics=metrics, ditto=ditto, mqtt_connected=mqtt_flag)


@pytest.fixture
async def client(deps: AppDeps) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(deps)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        yield http


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /ready (200 only with MQTT connected AND Ditto reachable)
# ---------------------------------------------------------------------------


async def test_ready_200_when_mqtt_and_ditto_up(client: httpx.AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "mqtt_connected": True,
        "ditto_ready": True,
    }


async def test_ready_503_when_mqtt_down(
    client: httpx.AsyncClient, mqtt_flag: MutableFlag
) -> None:
    mqtt_flag.value = False
    response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["mqtt_connected"] is False
    assert body["ditto_ready"] is True


async def test_ready_503_when_ditto_down(
    client: httpx.AsyncClient, ditto: FakeDittoClient
) -> None:
    ditto.ready = False
    response = await client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["mqtt_connected"] is True
    assert body["ditto_ready"] is False


async def test_ready_503_when_both_down(
    client: httpx.AsyncClient, ditto: FakeDittoClient, mqtt_flag: MutableFlag
) -> None:
    ditto.ready = False
    mqtt_flag.value = False
    assert (await client.get("/ready")).status_code == 503


# ---------------------------------------------------------------------------
# GET /twins/{device_id}
# ---------------------------------------------------------------------------


async def test_twin_read_is_normalized(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/twins/{WATCH}")
    assert response.status_code == 200
    body = response.json()
    assert body["device_uuid"] == WATCH
    assert body["thing_id"] == f"org.c2dta:{WATCH}"
    assert body["policy_id"] == f"org.c2dta:{WATCH}"
    assert body["device_type"] == "smartwatch"
    assert body["egw_id"] == "egw-01"
    assert body["schema_version"] == "1.0.0"
    assert body["ingestion"]["last_seq"] == 3
    assert body["ingestion"]["accepted_count"] == 4
    assert "ingestion" not in body["features"]


async def test_twin_read_accepts_full_thing_id(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/twins/org.c2dta:{WATCH}")
    assert response.status_code == 200
    assert response.json()["device_uuid"] == WATCH


async def test_twin_read_unknown_device_404(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/twins/{DEVICE_UUIDS['smart_ring']}")
    assert response.status_code == 404


async def test_twin_read_ditto_unavailable_502(
    deps: AppDeps, ditto: FakeDittoClient
) -> None:
    ditto.fail_get = DittoUnavailableError("ditto down", attempts=3)
    app = create_app(deps)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        response = await http.get(f"/twins/{WATCH}")
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# GET /metrics
# ---------------------------------------------------------------------------


async def test_metrics_counts_and_uptime(
    client: httpx.AsyncClient,
    metrics: MetricsCounters,
    clock: FakeMonotonicClock,
) -> None:
    metrics.increment("accepted")
    metrics.increment("accepted")
    metrics.increment("rejected")
    metrics.increment("duplicate")
    metrics.increment("failed")
    clock.value = 160.5  # constructed at 100.0
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.json() == {
        "accepted": 2,
        "rejected": 1,
        "duplicate": 1,
        "failed": 1,
        "started_at": "2026-08-07T12:00:00.000Z",
        "uptime_s": 60.5,
    }


def test_metrics_rejects_unknown_outcome(metrics: MetricsCounters) -> None:
    with pytest.raises(ValueError):
        metrics.increment("lost")
