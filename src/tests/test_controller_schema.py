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


def test_error_carries_json_paths(repository: SchemaRepository) -> None:
    payload = make_payload("smartwatch")
    payload["heart_rate_bpm"] = 24
    with pytest.raises(SchemaValidationError) as excinfo:
        repository.validate(payload)
    assert excinfo.value.errors  # at least one path:message entry recorded


def test_missing_schema_dir_raises() -> None:
    with pytest.raises(OSError):
        SchemaRepository(SCHEMA_DIR / "does-not-exist")
