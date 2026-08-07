"""Async Ditto HTTP client (CONTRACTS.md sections 4-6).

- ``thingId`` = ``policyId`` = ``org.c2dta:{device_uuid}``.
- First contact: ``PUT /api/2/policies/{policyId}`` then ``PUT /api/2/things/{thingId}``.
- Telemetry: ``PATCH /api/2/things/{thingId}`` with ``application/merge-patch+json``.
- Bounded retries: only timeouts, connection errors and 5xx are retried, never
  4xx; exponential backoff with base ``EGW_RETRY_BACKOFF_MS`` and at most
  ``EGW_RETRY_MAX`` attempts in total.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Mapping

import httpx

from .config import Settings

THING_NAMESPACE = "org.c2dta"
MERGE_PATCH_CONTENT_TYPE = "application/merge-patch+json"
PREAUTH_HEADER = "x-ditto-pre-authenticated"
DEFAULT_TIMEOUT_S = 10.0

# Well-formed UUID v4 used only to probe API reachability in is_ready();
# any HTTP answer (including 404) proves the Ditto gateway is up.
_READINESS_PROBE_UUID = "00000000-0000-4000-8000-000000000000"

# CONTRACTS.md section 4: feature -> top-level payload fields, per device_type.
FEATURE_PROPERTY_MAP: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "smartwatch": {
        "vitals": ("heart_rate_bpm",),
        "location": ("lat", "lon"),
    },
    "smart_ring": {
        "thermo": ("skin_temp_c",),
        "oximetry": ("spo2_pct",),
    },
    "smart_clothing": {
        "motion": ("accel_x", "accel_y", "accel_z"),
        "respiration": ("breathing_rpm",),
    },
}


def thing_id_for(device_uuid: str) -> str:
    return f"{THING_NAMESPACE}:{device_uuid}"


def build_merge_patch(
    payload: Mapping[str, Any], accepted_count: int
) -> dict[str, Any]:
    """Build the merge-patch body for one validated telemetry payload.

    ``accepted_count`` is the post-update total of confirmed messages for the
    device (the controller tracks it locally, seeded from the twin).
    """
    device_type = payload["device_type"]
    try:
        feature_map = FEATURE_PROPERTY_MAP[device_type]
    except KeyError:
        raise ValueError(f"unknown device_type {device_type!r}") from None
    features: dict[str, Any] = {
        feature: {"properties": {prop: payload[prop] for prop in props}}
        for feature, props in feature_map.items()
    }
    features["ingestion"] = {
        "properties": {
            "last_message_id": payload["message_id"],
            "last_seq": payload["seq"],
            "last_ts": payload["ts"],
            "accepted_count": accepted_count,
        }
    }
    return {"features": features}


def normalize_twin(device_uuid: str, twin: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a raw Ditto thing for ``GET /twins/{device_id}`` responses."""
    attributes = twin.get("attributes") or {}
    raw_features = twin.get("features") or {}
    features = {
        name: (feature or {}).get("properties") or {}
        for name, feature in raw_features.items()
    }
    ingestion = features.pop("ingestion", {})
    return {
        "device_uuid": device_uuid,
        "thing_id": twin.get("thingId", thing_id_for(device_uuid)),
        "policy_id": twin.get("policyId"),
        "device_type": attributes.get("device_type"),
        "egw_id": attributes.get("egw_id"),
        "schema_version": attributes.get("schema_version"),
        "features": features,
        "ingestion": ingestion,
    }


class DittoError(Exception):
    """Base error for Ditto interactions; carries attempt count and last status."""

    def __init__(
        self, message: str, *, attempts: int, status: int | None = None
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.status = status


class DittoClientError(DittoError):
    """A 4xx response: the request is wrong and must never be retried."""


class DittoUnavailableError(DittoError):
    """Transient failures (timeout/connect/5xx) persisting after all retries."""


def _body_snippet(response: httpx.Response, limit: int = 200) -> str:
    try:
        return response.text[:limit]
    except Exception:  # pragma: no cover - defensive
        return "<unreadable body>"


class DittoClient:
    """httpx.AsyncClient wrapper implementing the controller's Ditto contract.

    The HTTP client, the backoff sleep function and all knobs are injectable
    for tests (httpx.MockTransport, recorded sleeps).
    """

    def __init__(
        self,
        *,
        base_url: str,
        auth_mode: str = "pre",
        preauth_subject: str = "pre:egw-controller",
        username: str | None = None,
        password: str | None = None,
        retry_max: int = 3,
        retry_backoff_ms: int = 200,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if auth_mode not in ("pre", "basic"):
            raise ValueError(f"auth_mode must be 'pre' or 'basic', got {auth_mode!r}")
        if auth_mode == "basic" and not (username and password):
            raise ValueError("basic auth_mode requires username and password")
        if retry_max < 1:
            raise ValueError("retry_max must be >= 1")
        self._auth_mode = auth_mode
        self._preauth_subject = preauth_subject
        self._username = username
        self._retry_max = retry_max
        self._retry_backoff_ms = retry_backoff_ms
        self._sleep = sleep
        self._auth = (
            httpx.BasicAuth(username or "", password or "")
            if auth_mode == "basic"
            else None
        )
        self._client = client or httpx.AsyncClient(
            base_url=base_url, timeout=timeout_s
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> "DittoClient":
        return cls(
            base_url=settings.ditto_base_url,
            auth_mode=settings.ditto_auth_mode,
            preauth_subject=settings.ditto_preauth_subject,
            username=settings.ditto_username,
            password=settings.ditto_password,
            retry_max=settings.retry_max,
            retry_backoff_ms=settings.retry_backoff_ms,
            client=client,
            sleep=sleep,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- request plumbing ---------------------------------------------------

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._auth_mode == "pre":
            headers[PREAUTH_HEADER] = self._preauth_subject
        if extra:
            headers.update(extra)
        return headers

    def _backoff_s(self, failed_attempt: int) -> float:
        return (self._retry_backoff_ms / 1000.0) * (2 ** (failed_attempt - 1))

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        content_type: str | None = None,
    ) -> tuple[httpx.Response, int]:
        """Perform one logical request with bounded retries.

        Returns ``(response, attempts)`` on any non-4xx success; raises
        :class:`DittoClientError` on 4xx (no retry) and
        :class:`DittoUnavailableError` once retries are exhausted.
        """
        content: bytes | None = None
        extra_headers: dict[str, str] = {}
        if json_body is not None:
            content = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            extra_headers["content-type"] = content_type or "application/json"
        headers = self._headers(extra_headers)
        auth = self._auth if self._auth is not None else httpx.USE_CLIENT_DEFAULT
        last_error = "unknown error"
        last_status: int | None = None
        for attempt in range(1, self._retry_max + 1):
            try:
                response = await self._client.request(
                    method, path, content=content, headers=headers, auth=auth
                )
            except httpx.TransportError as exc:
                # Covers timeouts and connection-level errors (retryable).
                last_error = f"{type(exc).__name__}: {exc}"
                last_status = None
            else:
                if response.status_code < 400:
                    return response, attempt
                if response.status_code < 500:
                    raise DittoClientError(
                        f"{method} {path} returned {response.status_code}: "
                        f"{_body_snippet(response)}",
                        attempts=attempt,
                        status=response.status_code,
                    )
                last_error = f"HTTP {response.status_code}: {_body_snippet(response)}"
                last_status = response.status_code
            if attempt < self._retry_max:
                await self._sleep(self._backoff_s(attempt))
        raise DittoUnavailableError(
            f"{method} {path} failed after {self._retry_max} attempt(s): {last_error}",
            attempts=self._retry_max,
            status=last_status,
        )

    # -- twin lifecycle -----------------------------------------------------

    def _policy_document(self) -> dict[str, Any]:
        if self._auth_mode == "pre":
            subject_id = self._preauth_subject
            subject_type = "pre-authenticated"
        else:
            subject_id = f"nginx:{self._username}"
            subject_type = "basic"
        return {
            "entries": {
                "egw-controller": {
                    "subjects": {subject_id: {"type": subject_type}},
                    "resources": {
                        "thing:/": {"grant": ["READ", "WRITE"], "revoke": []},
                        "policy:/": {"grant": ["READ", "WRITE"], "revoke": []},
                    },
                }
            }
        }

    def _initial_thing(
        self, device_uuid: str, device_type: str, egw_id: str, schema_version: str
    ) -> dict[str, Any]:
        return {
            "policyId": thing_id_for(device_uuid),
            "attributes": {
                "device_type": device_type,
                "egw_id": egw_id,
                "schema_version": schema_version,
            },
            "features": {
                "ingestion": {
                    "properties": {
                        "last_message_id": None,
                        "last_seq": None,
                        "last_ts": None,
                        "accepted_count": 0,
                    }
                }
            },
        }

    async def ensure_twin(
        self,
        *,
        device_uuid: str,
        device_type: str,
        egw_id: str,
        schema_version: str,
    ) -> int:
        """Create policy + thing for a first-contact device; return total attempts."""
        thing_id = thing_id_for(device_uuid)
        _, policy_attempts = await self._request(
            "PUT", f"/api/2/policies/{thing_id}", json_body=self._policy_document()
        )
        _, thing_attempts = await self._request(
            "PUT",
            f"/api/2/things/{thing_id}",
            json_body=self._initial_thing(
                device_uuid, device_type, egw_id, schema_version
            ),
        )
        return policy_attempts + thing_attempts

    async def get_twin(self, device_uuid: str) -> dict[str, Any] | None:
        """Fetch the raw thing JSON, or ``None`` when the twin does not exist."""
        try:
            response, _ = await self._request(
                "GET", f"/api/2/things/{thing_id_for(device_uuid)}"
            )
        except DittoClientError as exc:
            if exc.status == 404:
                return None
            raise
        return response.json()

    async def patch_thing(
        self, device_uuid: str, patch: Mapping[str, Any]
    ) -> int:
        """Apply a merge-patch to the twin; return the number of attempts used."""
        _, attempts = await self._request(
            "PATCH",
            f"/api/2/things/{thing_id_for(device_uuid)}",
            json_body=patch,
            content_type=MERGE_PATCH_CONTENT_TYPE,
        )
        return attempts

    async def is_ready(self) -> bool:
        """Single non-retried probe: any HTTP answer < 500 means Ditto is reachable."""
        auth = self._auth if self._auth is not None else httpx.USE_CLIENT_DEFAULT
        try:
            response = await self._client.request(
                "GET",
                f"/api/2/things/{thing_id_for(_READINESS_PROBE_UUID)}",
                headers=self._headers(),
                auth=auth,
            )
        except httpx.HTTPError:
            return False
        return response.status_code < 500
