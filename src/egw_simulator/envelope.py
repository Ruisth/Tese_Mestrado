"""Common telemetry envelope helpers (CONTRACTS.md section 2, plan section 5.3).

Every telemetry payload carries the common envelope fields defined by
``schemas/telemetry-envelope-v1.schema.json``. ``message_id`` is a UUID v5 in
the project namespace, derived from ``run_id``, ``device_uuid`` and ``seq`` so
that any party can recompute it and detect duplicates.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

#: Envelope schema version (semver, CONTRACTS.md section 2).
SCHEMA_VERSION = "1.0.0"

#: Protocol version recorded in each run manifest (CONTRACTS.md section 7).
PROTOCOL_VERSION = "1.0"

#: Project-wide UUID v5 namespace (CONTRACTS.md section 2). Normative value;
#: never change without a coordinated contract update.
EGW_UUID_NAMESPACE = uuid.UUID("6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0")


def make_message_id(run_id: str, device_uuid: str, seq: int) -> str:
    """Return the UUID v5 message id for (run_id, device_uuid, seq).

    Name string is exactly ``"{run_id}:{device_uuid}:{seq}"`` per
    CONTRACTS.md section 2.
    """
    return str(uuid.uuid5(EGW_UUID_NAMESPACE, f"{run_id}:{device_uuid}:{seq}"))


def rfc3339_utc_ms(dt: datetime | None = None) -> str:
    """Format a datetime as RFC 3339 UTC with millisecond resolution and 'Z'.

    Example: ``2026-08-07T12:34:56.789Z``. Naive datetimes are rejected to
    avoid silent local-time bugs; pass timezone-aware values only.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        raise ValueError("rfc3339_utc_ms() requires a timezone-aware datetime")
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{dt.microsecond // 1000:03d}Z"


def build_envelope(
    *,
    run_id: str,
    egw_id: str,
    device_uuid: str,
    device_type: str,
    seq: int,
    ts: str | None = None,
) -> dict:
    """Build the common envelope dict for one telemetry event.

    ``ts`` may be injected (already formatted RFC 3339 UTC 'Z' string) for
    deterministic tests; when ``None`` the current UTC time is used.
    """
    if seq < 0:
        raise ValueError("seq must be >= 0")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "message_id": make_message_id(run_id, device_uuid, seq),
        "seq": seq,
        "ts": ts if ts is not None else rfc3339_utc_ms(),
        "egw_id": egw_id,
        "device_uuid": device_uuid,
        "device_type": device_type,
    }
