"""Tests for egw_controller.schema (CONTRACTS.md sections 2-3, draft 2020-12).

The repository must accept in-contract payloads for every device_type and
reject out-of-range values, missing fields, extra fields (closed by
``unevaluatedProperties: false``) and wrong/unknown ``device_type`` claims.
"""

from __future__ import annotations

from typing import Any

import pytest

from egw_controller.schema import SchemaRepository, SchemaValidationError
from test_controller_helpers import SCHEMA_DIR, make_payload

DEVICE_TYPES = ("smartwatch", "smart_ring", "smart_clothing")


@pytest.fixture(scope="module")
def repository() -> SchemaRepository:
    return SchemaRepository(SCHEMA_DIR)


def test_repository_knows_all_device_types(repository: SchemaRepository) -> None:
    assert sorted(repository.device_types) == sorted(DEVICE_TYPES)


@pytest.mark.parametrize("device_type", DEVICE_TYPES)
def test_valid_payload_accepted(
    repository: SchemaRepository, device_type: str
) -> None:
    repository.validate(make_payload(device_type))


@pytest.mark.parametrize(
    ("device_type", "field", "bad_value"),
    [
        ("smartwatch", "heart_rate_bpm", 24),
        ("smartwatch", "heart_rate_bpm", 251),
        ("smartwatch", "lat", 90.5),
        ("smartwatch", "lon", -180.5),
        ("smart_ring", "skin_temp_c", 29.9),
        ("smart_ring", "spo2_pct", 101),
        ("smart_clothing", "accel_x", 78.5),
        ("smart_clothing", "breathing_rpm", 3.9),
    ],
)
def test_out_of_range_value_rejected(
    repository: SchemaRepository, device_type: str, field: str, bad_value: Any
) -> None:
    payload = make_payload(device_type)
    payload[field] = bad_value
    with pytest.raises(SchemaValidationError):
        repository.validate(payload)


@pytest.mark.parametrize(
    ("device_type", "missing_field"),
    [
        ("smartwatch", "heart_rate_bpm"),
        ("smartwatch", "run_id"),
        ("smart_ring", "spo2_pct"),
        ("smart_ring", "message_id"),
        ("smart_clothing", "breathing_rpm"),
        ("smart_clothing", "seq"),
    ],
)
def test_missing_field_rejected(
    repository: SchemaRepository, device_type: str, missing_field: str
) -> None:
    payload = make_payload(device_type)
    del payload[missing_field]
    with pytest.raises(SchemaValidationError):
        repository.validate(payload)


@pytest.mark.parametrize("device_type", DEVICE_TYPES)
def test_extra_field_rejected_by_unevaluated_properties(
    repository: SchemaRepository, device_type: str
) -> None:
    payload = make_payload(device_type)
    payload["unexpected_field"] = 1
    with pytest.raises(SchemaValidationError):
        repository.validate(payload)


def test_wrong_device_type_claim_rejected(repository: SchemaRepository) -> None:
    # A smartwatch payload claiming to be a ring fails the ring schema:
    # missing ring fields plus unevaluated smartwatch fields.
    payload = make_payload("smartwatch")
    payload["device_type"] = "smart_ring"
    with pytest.raises(SchemaValidationError):
        repository.validate(payload)


def test_unknown_device_type_rejected(repository: SchemaRepository) -> None:
    payload = make_payload("smartwatch")
    payload["device_type"] = "drone"
    with pytest.raises(SchemaValidationError, match="unknown device_type"):
        repository.validate(payload)


def test_missing_device_type_rejected(repository: SchemaRepository) -> None:
    payload = make_payload("smartwatch")
    del payload["device_type"]
    with pytest.raises(SchemaValidationError):
        repository.validate(payload)


@pytest.mark.parametrize(
    "device_type",
    [[], {}, 42, None, True, 1.5],
    ids=["list", "object", "int", "null", "bool", "float"],
)
def test_non_string_device_type_rejected(
    repository: SchemaRepository, device_type: Any
) -> None:
    """A non-string ``device_type`` fails validation with a message naming its type.

    A JSON array or object here used to escape the validator lookup as a
    ``TypeError`` (unhashable) and left the delivery without an outcome line
    (ADR 0011, item 6). The check is on the type, before the lookup, so the
    message says what was wrong rather than "unknown device_type []".
    """
    payload = make_payload("smartwatch")
    payload["device_type"] = device_type
    with pytest.raises(SchemaValidationError, match="device_type") as excinfo:
        repository.validate(payload)
    assert type(device_type).__name__ in str(excinfo.value)


@pytest.mark.parametrize("payload", [None, 42, "text", ["list"]])
def test_non_object_payload_rejected(
    repository: SchemaRepository, payload: Any
) -> None:
    with pytest.raises(SchemaValidationError):
        repository.validate(payload)


def test_bad_schema_version_rejected(repository: SchemaRepository) -> None:
    payload = make_payload("smartwatch")
    payload["schema_version"] = "2.0.0"
    with pytest.raises(SchemaValidationError):
        repository.validate(payload)


# ---------------------------------------------------------------------------
# ts: RFC 3339 UTC (CONTRACTS.md section 2)
# ---------------------------------------------------------------------------


def test_date_time_format_is_asserted_not_merely_annotated(
    repository: SchemaRepository,
) -> None:
    """Every validator must carry a format checker that knows ``date-time``.

    Without one, ``"format": "date-time"`` is a bare annotation. Note that
    ``jsonschema``'s stock ``FormatChecker`` does not register ``date-time``
    unless the optional ``rfc3339-validator`` package is installed, which we
    must not depend on, so the repository supplies its own checker.
    """
    for device_type in DEVICE_TYPES:
        checker = repository.validator_for(device_type).format_checker
        assert checker is not None, f"{device_type} validator has no format checker"
        assert "date-time" in checker.checkers


@pytest.mark.parametrize(
    "ts",
    [
        "2026-08-07T12:00:00Z",  # no fractional seconds
        "2026-08-07T12:00:00.7Z",  # tenths
        "2026-08-07T12:00:00.789Z",  # milliseconds, the simulator's resolution
        "2026-08-07T12:00:00.123456Z",  # microseconds, the pattern's maximum
        "2024-02-29T23:59:59.999Z",  # leap day in a leap year
        "2026-12-31T00:00:00Z",
    ],
)
@pytest.mark.parametrize("device_type", DEVICE_TYPES)
def test_valid_rfc3339_timestamp_accepted(
    repository: SchemaRepository, device_type: str, ts: str
) -> None:
    repository.validate(make_payload(device_type, ts=ts))


@pytest.mark.parametrize(
    "ts",
    [
        "2026-99-40T25:61:61Z",  # impossible month, day, hour, minute, second
        "2026-13-01T00:00:00Z",  # month 13
        "2026-00-10T00:00:00Z",  # month 0
        "2026-02-30T12:00:00Z",  # 30 February never exists
        "2025-02-29T12:00:00Z",  # 2025 is not a leap year
        "2026-04-31T12:00:00Z",  # April has 30 days
        "2026-08-00T12:00:00Z",  # day 0
        "2026-08-07T24:00:00Z",  # hour 24
        "2026-08-07T12:60:00Z",  # minute 60
        "2026-08-07T12:00:61Z",  # second 61
    ],
)
def test_impossible_calendar_or_clock_timestamp_rejected(
    repository: SchemaRepository, ts: str
) -> None:
    """These all satisfy the envelope's digit pattern but are not real instants."""
    with pytest.raises(SchemaValidationError):
        repository.validate(make_payload("smartwatch", ts=ts))


@pytest.mark.parametrize(
    "ts",
    [
        "2026-08-07T12:00:00",  # no zone designator
        "2026-08-07T12:00:00+01:00",  # non-UTC offset
        "2026-08-07T12:00:00z",  # lowercase suffix
        "2026-08-07 12:00:00Z",  # space instead of 'T'
        "2026-08-07T12:00:00.Z",  # empty fraction
        "2026-08-07T12:00:00.1234567Z",  # more than six fractional digits
        "not-a-timestamp",
    ],
)
def test_non_rfc3339_utc_timestamp_rejected(
    repository: SchemaRepository, ts: str
) -> None:
    with pytest.raises(SchemaValidationError):
        repository.validate(make_payload("smartwatch", ts=ts))


def test_error_carries_json_paths(repository: SchemaRepository) -> None:
    payload = make_payload("smartwatch")
    payload["heart_rate_bpm"] = 24
    with pytest.raises(SchemaValidationError) as excinfo:
        repository.validate(payload)
    assert excinfo.value.errors  # at least one path:message entry recorded


def test_missing_schema_dir_raises() -> None:
    with pytest.raises(OSError):
        SchemaRepository(SCHEMA_DIR / "does-not-exist")
