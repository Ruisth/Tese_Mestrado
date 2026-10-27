"""Tests for egw_controller.ditto (CONTRACTS.md sections 4-6).

Covers retry behaviour against ``httpx.MockTransport`` (success, 4xx never
retried, 5xx retried then success, retries exhausted, connect errors), the
first-contact policy+thing creation, the merge-patch body shape for every
device_type (features per CONTRACTS 4 including ``ingestion``), the
normalized twin read, and the two exchange faults that ADR 0011 (item 7)
turns into a ``DittoError`` rather than an escaping exception: a 2xx whose
body is not a JSON object, and an ``httpx`` error outside the transport
layer, neither of which is retried.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

import httpx
import pytest

from egw_controller.ditto import (
    MERGE_PATCH_CONTENT_TYPE,
    PREAUTH_HEADER,
    DittoClient,
    DittoClientError,
    DittoError,
    DittoProtocolError,
    DittoUnavailableError,
    build_merge_patch,
    normalize_twin,
    thing_id_for,
)
from test_controller_helpers import (
    DEVICE_UUIDS,
    make_payload,
    make_raw_twin,
)

DEVICE = DEVICE_UUIDS["smartwatch"]
BASE_URL = "http://ditto-gateway:8080"


class SleepRecorder:
    """Injectable backoff sleep that records requested delays."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    sleep: SleepRecorder | None = None,
    **kwargs: Any,
) -> DittoClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(base_url=BASE_URL, transport=transport)
    return DittoClient(
        base_url=BASE_URL,
        client=http,
        sleep=sleep or SleepRecorder(),
        **kwargs,
    )


class ScriptedHandler:
    """Returns/raises scripted results in order; records every request."""

    def __init__(self, *results: httpx.Response | Exception) -> None:
        self.results = list(results)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        result = self.results.pop(0) if self.results else httpx.Response(204)
        if isinstance(result, Exception):
            raise result
        return result


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


async def test_patch_success_first_attempt() -> None:
    handler = ScriptedHandler(httpx.Response(204))
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    attempts = await client.patch_thing(DEVICE, {"features": {}})
    assert attempts == 1
    assert sleep.delays == []
    request = handler.requests[0]
    assert request.method == "PATCH"
    assert request.url.path == f"/api/2/things/{thing_id_for(DEVICE)}"
    assert request.headers["content-type"] == MERGE_PATCH_CONTENT_TYPE
    assert request.headers[PREAUTH_HEADER] == "pre:egw-controller"


async def test_4xx_is_never_retried() -> None:
    handler = ScriptedHandler(httpx.Response(400, text="bad request"))
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    with pytest.raises(DittoClientError) as excinfo:
        await client.patch_thing(DEVICE, {"features": {}})
    assert excinfo.value.attempts == 1
    assert excinfo.value.status == 400
    assert len(handler.requests) == 1  # exactly one HTTP call
    assert sleep.delays == []


async def test_5xx_retried_then_success() -> None:
    handler = ScriptedHandler(httpx.Response(503), httpx.Response(204))
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    attempts = await client.patch_thing(DEVICE, {"features": {}})
    assert attempts == 2
    assert len(handler.requests) == 2
    assert sleep.delays == [0.2]  # one backoff at the 200 ms base


async def test_retries_exhausted_raises_unavailable() -> None:
    handler = ScriptedHandler(
        httpx.Response(500), httpx.Response(502), httpx.Response(503)
    )
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    with pytest.raises(DittoUnavailableError) as excinfo:
        await client.patch_thing(DEVICE, {"features": {}})
    assert excinfo.value.attempts == 3  # EGW_RETRY_MAX default
    assert excinfo.value.status == 503
    assert len(handler.requests) == 3
    # exponential backoff: base, base*2 (no sleep after the final attempt)
    assert sleep.delays == [0.2, 0.4]


async def test_connect_errors_are_retried() -> None:
    handler = ScriptedHandler(
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("timed out"),
        httpx.Response(204),
    )
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    attempts = await client.patch_thing(DEVICE, {"features": {}})
    assert attempts == 3
    assert sleep.delays == [0.2, 0.4]


async def test_connect_errors_exhausted() -> None:
    handler = ScriptedHandler(
        httpx.ConnectError("refused"),
        httpx.ConnectError("refused"),
        httpx.ConnectError("refused"),
    )
    client = make_client(handler)
    with pytest.raises(DittoUnavailableError) as excinfo:
        await client.patch_thing(DEVICE, {"features": {}})
    assert excinfo.value.attempts == 3
    assert excinfo.value.status is None


async def test_custom_retry_knobs() -> None:
    handler = ScriptedHandler(
        httpx.Response(500), httpx.Response(500), httpx.Response(500),
        httpx.Response(500), httpx.Response(500),
    )
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep, retry_max=5, retry_backoff_ms=100)
    with pytest.raises(DittoUnavailableError) as excinfo:
        await client.patch_thing(DEVICE, {"features": {}})
    assert excinfo.value.attempts == 5
    assert sleep.delays == [0.1, 0.2, 0.4, 0.8]


# ---------------------------------------------------------------------------
# Auth modes
# ---------------------------------------------------------------------------


async def test_pre_auth_header_present_and_no_basic() -> None:
    handler = ScriptedHandler(httpx.Response(204))
    client = make_client(handler, preauth_subject="pre:egw-controller")
    await client.patch_thing(DEVICE, {"features": {}})
    request = handler.requests[0]
    assert request.headers[PREAUTH_HEADER] == "pre:egw-controller"
    assert "authorization" not in request.headers


async def test_basic_auth_header_present_and_no_preauth() -> None:
    handler = ScriptedHandler(httpx.Response(204))
    client = make_client(
        handler, auth_mode="basic", username="ditto", password="secret"
    )
    await client.patch_thing(DEVICE, {"features": {}})
    request = handler.requests[0]
    assert request.headers["authorization"].startswith("Basic ")
    assert PREAUTH_HEADER not in request.headers


def test_basic_auth_requires_credentials() -> None:
    with pytest.raises(ValueError):
        DittoClient(base_url=BASE_URL, auth_mode="basic")


# ---------------------------------------------------------------------------
# First contact: PUT policy then PUT thing (CONTRACTS 4)
# ---------------------------------------------------------------------------


async def test_ensure_twin_puts_policy_then_thing() -> None:
    handler = ScriptedHandler(httpx.Response(201), httpx.Response(201))
    client = make_client(handler)
    attempts = await client.ensure_twin(
        device_uuid=DEVICE,
        device_type="smartwatch",
        egw_id="egw-01",
        schema_version="1.0.0",
    )
    assert attempts == 2
    thing_id = thing_id_for(DEVICE)
    assert thing_id == f"org.c2dta:{DEVICE}"

    policy_req, thing_req = handler.requests
    assert policy_req.method == "PUT"
    assert policy_req.url.path == f"/api/2/policies/{thing_id}"
    policy = json.loads(policy_req.content)
    entry = policy["entries"]["egw-controller"]
    assert "pre:egw-controller" in entry["subjects"]
    assert entry["resources"]["thing:/"]["grant"] == ["READ", "WRITE"]
    assert entry["resources"]["policy:/"]["grant"] == ["READ", "WRITE"]

    assert thing_req.method == "PUT"
    assert thing_req.url.path == f"/api/2/things/{thing_id}"
    thing = json.loads(thing_req.content)
    assert thing["policyId"] == thing_id
    assert thing["attributes"] == {
        "device_type": "smartwatch",
        "egw_id": "egw-01",
        "schema_version": "1.0.0",
    }
    assert thing["features"]["ingestion"]["properties"] == {
        "last_message_id": None,
        "last_seq": None,
        "last_run_id": None,
        "last_ts": None,
        "accepted_count": 0,
    }


async def test_ensure_twin_policy_4xx_stops_before_thing() -> None:
    handler = ScriptedHandler(httpx.Response(403, text="forbidden"))
    client = make_client(handler)
    with pytest.raises(DittoClientError):
        await client.ensure_twin(
            device_uuid=DEVICE,
            device_type="smartwatch",
            egw_id="egw-01",
            schema_version="1.0.0",
        )
    assert len(handler.requests) == 1  # the thing PUT never happened


# ---------------------------------------------------------------------------
# get_twin / is_ready
# ---------------------------------------------------------------------------


async def test_get_twin_returns_json() -> None:
    twin = make_raw_twin(DEVICE, last_seq=3, accepted_count=4)
    handler = ScriptedHandler(httpx.Response(200, json=twin))
    client = make_client(handler)
    result = await client.get_twin(DEVICE)
    assert result == twin
    assert handler.requests[0].method == "GET"
    assert handler.requests[0].url.path == f"/api/2/things/{thing_id_for(DEVICE)}"


async def test_get_twin_404_returns_none() -> None:
    handler = ScriptedHandler(httpx.Response(404))
    client = make_client(handler)
    assert await client.get_twin(DEVICE) is None


async def test_get_twin_other_4xx_raises() -> None:
    handler = ScriptedHandler(httpx.Response(401))
    client = make_client(handler)
    with pytest.raises(DittoClientError):
        await client.get_twin(DEVICE)


async def test_is_ready_true_on_http_answer() -> None:
    # 404 for the probe thing still proves the API answers.
    for status in (200, 404):
        client = make_client(ScriptedHandler(httpx.Response(status)))
        assert await client.is_ready() is True


async def test_is_ready_false_on_5xx_or_transport_error() -> None:
    client = make_client(ScriptedHandler(httpx.Response(503)))
    assert await client.is_ready() is False
    client = make_client(ScriptedHandler(httpx.ConnectError("refused")))
    assert await client.is_ready() is False


# ---------------------------------------------------------------------------
# Twin body that is not a JSON object (ADR 0011, item 7a)
# ---------------------------------------------------------------------------


def _assert_exchange_fault(error: DittoError) -> None:
    """The fault is a ``DittoProtocolError``: a ``DittoError`` (so the service's
    ``except DittoError`` sees it) that is neither a 4xx nor an exhausted retry."""
    assert isinstance(error, DittoError)
    assert isinstance(error, DittoProtocolError)
    assert not isinstance(error, (DittoClientError, DittoUnavailableError))


async def test_get_twin_non_json_body_raises_ditto_error() -> None:
    """A 200 with an HTML body (a proxy page) is a fault, not a twin."""
    handler = ScriptedHandler(
        httpx.Response(
            200, content=b"<html>proxy</html>", headers={"content-type": "text/html"}
        )
    )
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    with pytest.raises(DittoError) as excinfo:
        await client.get_twin(DEVICE)
    _assert_exchange_fault(excinfo.value)
    assert excinfo.value.attempts == 1
    assert excinfo.value.status == 200
    assert "non-JSON body" in str(excinfo.value)
    assert len(handler.requests) == 1  # a 200 with an unusable body is not retried
    assert sleep.delays == []


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"{\xff}", id="invalid-utf8"),
        pytest.param(b"[" * 200_000, id="deeply-nested"),
    ],
)
async def test_get_twin_undecodable_body_raises_ditto_error(body: bytes) -> None:
    """The decoder's other faults (UnicodeDecodeError, RecursionError) end the same way."""
    handler = ScriptedHandler(
        httpx.Response(200, content=body, headers={"content-type": "application/json"})
    )
    client = make_client(handler)
    with pytest.raises(DittoError) as excinfo:
        await client.get_twin(DEVICE)
    _assert_exchange_fault(excinfo.value)
    assert excinfo.value.attempts == 1
    assert excinfo.value.status == 200
    assert "non-JSON body" in str(excinfo.value)


async def test_get_twin_oversized_integer_body_raises_ditto_error() -> None:
    """An integer beyond the interpreter's digit limit raises a plain ValueError."""
    limit = sys.get_int_max_str_digits()
    if limit == 0:
        pytest.skip("integer string conversion limit is disabled here")
    body = b'{"seq": ' + b"1" * (limit + 1) + b"}"
    handler = ScriptedHandler(
        httpx.Response(200, content=body, headers={"content-type": "application/json"})
    )
    client = make_client(handler)
    with pytest.raises(DittoError) as excinfo:
        await client.get_twin(DEVICE)
    _assert_exchange_fault(excinfo.value)
    assert excinfo.value.attempts == 1
    assert excinfo.value.status == 200


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"null", id="null"),
        pytest.param(b"[]", id="array"),
        pytest.param(b'"x"', id="string"),
        pytest.param(b"42", id="number"),
        pytest.param(b"true", id="bool"),
    ],
)
async def test_get_twin_non_object_json_body_raises_ditto_error(body: bytes) -> None:
    """Only a 404 means "no twin": a 200 ``null`` is a fault, never a first contact.

    Reading ``null`` as "no twin" made the service re-create the thing with
    an empty ingestion feature over whatever the twin held.
    """
    handler = ScriptedHandler(
        httpx.Response(200, content=body, headers={"content-type": "application/json"})
    )
    client = make_client(handler)
    with pytest.raises(DittoError) as excinfo:
        await client.get_twin(DEVICE)
    _assert_exchange_fault(excinfo.value)
    assert excinfo.value.attempts == 1
    assert excinfo.value.status == 200
    assert "non-object JSON body" in str(excinfo.value)
    assert type(json.loads(body)).__name__ in str(excinfo.value)


async def test_get_twin_unusable_body_keeps_attempt_count() -> None:
    """The attempt count of the GET is reported, not discarded (retried 503 then 200)."""
    handler = ScriptedHandler(httpx.Response(503), httpx.Response(200, content=b"[]"))
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    with pytest.raises(DittoError) as excinfo:
        await client.get_twin(DEVICE)
    assert excinfo.value.attempts == 2
    assert excinfo.value.status == 200
    assert len(handler.requests) == 2
    assert sleep.delays == [0.2]


# ---------------------------------------------------------------------------
# httpx errors that are not transport errors (ADR 0011, item 7b)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(httpx.DecodingError("bad content-encoding"), id="decoding"),
        pytest.param(httpx.TooManyRedirects("redirect loop"), id="redirects"),
    ],
)
async def test_non_transport_httpx_error_is_not_retried(error: httpx.HTTPError) -> None:
    """An ``httpx.HTTPError`` outside the transport layer ends the exchange at once."""
    assert not isinstance(error, httpx.TransportError)  # the premise of the test
    handler = ScriptedHandler(error)
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    with pytest.raises(DittoError) as excinfo:
        await client.patch_thing(DEVICE, {"features": {}})
    _assert_exchange_fault(excinfo.value)
    assert excinfo.value.attempts == 1
    assert excinfo.value.status is None
    assert type(error).__name__ in str(excinfo.value)
    assert excinfo.value.__cause__ is error
    assert len(handler.requests) == 1
    assert sleep.delays == []


async def test_non_transport_httpx_error_after_retried_failure_keeps_attempt_count() -> None:
    handler = ScriptedHandler(
        httpx.Response(503), httpx.DecodingError("bad content-encoding")
    )
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    with pytest.raises(DittoError) as excinfo:
        await client.patch_thing(DEVICE, {"features": {}})
    assert excinfo.value.attempts == 2
    assert excinfo.value.status is None
    assert len(handler.requests) == 2
    assert sleep.delays == [0.2]


async def test_get_twin_non_transport_httpx_error_raises_ditto_error() -> None:
    handler = ScriptedHandler(httpx.DecodingError("bad content-encoding"))
    client = make_client(handler)
    with pytest.raises(DittoError) as excinfo:
        await client.get_twin(DEVICE)
    _assert_exchange_fault(excinfo.value)
    assert excinfo.value.attempts == 1
    assert len(handler.requests) == 1


async def test_ensure_twin_non_transport_httpx_error_after_policy_put() -> None:
    handler = ScriptedHandler(
        httpx.Response(201), httpx.DecodingError("bad content-encoding")
    )
    client = make_client(handler)
    with pytest.raises(DittoError) as excinfo:
        await client.ensure_twin(
            device_uuid=DEVICE,
            device_type="smartwatch",
            egw_id="egw-01",
            schema_version="1.0.0",
        )
    _assert_exchange_fault(excinfo.value)
    assert excinfo.value.attempts == 1  # the thing PUT's own count
    assert len(handler.requests) == 2  # policy PUT succeeded, thing PUT faulted


async def test_non_httpx_exception_from_the_transport_propagates_unchanged() -> None:
    """What is not an ``httpx`` error is not an exchange fault of this client.

    It is left to the pipeline's residual handler (ADR 0011, item 8), so it
    must reach the caller as raised: not wrapped, not retried.
    """
    error = RuntimeError("boom")
    handler = ScriptedHandler(error)
    sleep = SleepRecorder()
    client = make_client(handler, sleep=sleep)
    with pytest.raises(RuntimeError) as excinfo:
        await client.patch_thing(DEVICE, {"features": {}})
    assert excinfo.value is error
    assert len(handler.requests) == 1
    assert sleep.delays == []


# ---------------------------------------------------------------------------
# Merge-patch body shape (CONTRACTS 4 feature layout)
# ---------------------------------------------------------------------------


def test_merge_patch_shape_smartwatch() -> None:
    payload = make_payload("smartwatch", seq=7)
    patch = build_merge_patch(payload, accepted_count=8)
    assert patch == {
        "features": {
            "vitals": {"properties": {"heart_rate_bpm": payload["heart_rate_bpm"]}},
            "location": {
                "properties": {"lat": payload["lat"], "lon": payload["lon"]}
            },
            "ingestion": {
                "properties": {
                    "last_message_id": payload["message_id"],
                    "last_seq": 7,
                    "last_run_id": payload["run_id"],
                    "last_ts": payload["ts"],
                    "accepted_count": 8,
                }
            },
        }
    }


def test_merge_patch_shape_smart_ring() -> None:
    payload = make_payload("smart_ring", seq=2)
    patch = build_merge_patch(payload, accepted_count=3)
    assert patch == {
        "features": {
            "thermo": {"properties": {"skin_temp_c": payload["skin_temp_c"]}},
            "oximetry": {"properties": {"spo2_pct": payload["spo2_pct"]}},
            "ingestion": {
                "properties": {
                    "last_message_id": payload["message_id"],
                    "last_seq": 2,
                    "last_run_id": payload["run_id"],
                    "last_ts": payload["ts"],
                    "accepted_count": 3,
                }
            },
        }
    }


def test_merge_patch_shape_smart_clothing() -> None:
    payload = make_payload("smart_clothing", seq=0)
    patch = build_merge_patch(payload, accepted_count=1)
    assert patch == {
        "features": {
            "motion": {
                "properties": {
                    "accel_x": payload["accel_x"],
                    "accel_y": payload["accel_y"],
                    "accel_z": payload["accel_z"],
                }
            },
            "respiration": {
                "properties": {"breathing_rpm": payload["breathing_rpm"]}
            },
            "ingestion": {
                "properties": {
                    "last_message_id": payload["message_id"],
                    "last_seq": 0,
                    "last_run_id": payload["run_id"],
                    "last_ts": payload["ts"],
                    "accepted_count": 1,
                }
            },
        }
    }


def test_merge_patch_unknown_device_type_raises() -> None:
    payload = make_payload("smartwatch")
    payload["device_type"] = "drone"
    with pytest.raises(ValueError):
        build_merge_patch(payload, accepted_count=1)


# ---------------------------------------------------------------------------
# Normalized twin read (GET /twins/{device_id})
# ---------------------------------------------------------------------------


def test_normalize_twin_shape() -> None:
    raw = make_raw_twin(
        DEVICE,
        last_message_id="00000000-0000-5000-8000-000000000000",
        last_seq=9,
        last_run_id="run-2026-08-07-0001",
        accepted_count=10,
        extra_features={
            "vitals": {"properties": {"heart_rate_bpm": 72}},
            "location": {"properties": {"lat": 38.7, "lon": -9.1}},
        },
    )
    normalized = normalize_twin(DEVICE, raw)
    assert normalized == {
        "device_uuid": DEVICE,
        "thing_id": f"org.c2dta:{DEVICE}",
        "policy_id": f"org.c2dta:{DEVICE}",
        "device_type": "smartwatch",
        "egw_id": "egw-01",
        "schema_version": "1.0.0",
        "features": {
            "vitals": {"heart_rate_bpm": 72},
            "location": {"lat": 38.7, "lon": -9.1},
        },
        "ingestion": {
            "last_message_id": "00000000-0000-5000-8000-000000000000",
            "last_seq": 9,
            "last_run_id": "run-2026-08-07-0001",
            "last_ts": raw["features"]["ingestion"]["properties"]["last_ts"],
            "accepted_count": 10,
        },
    }


def test_normalize_twin_tolerates_missing_sections() -> None:
    normalized = normalize_twin(DEVICE, {"thingId": thing_id_for(DEVICE)})
    assert normalized["features"] == {}
    assert normalized["ingestion"] == {}
    assert normalized["device_type"] is None
