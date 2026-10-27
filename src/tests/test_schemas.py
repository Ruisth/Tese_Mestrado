"""Contract tests for the JSON Schemas in src/schemas.

Binding references: CONTRACTS.md sections 2 (common envelope) and 3 (per-device
measurement fields and bounds); plan section 5.3. All schemas are JSON Schema
draft 2020-12 and device schemas compose the envelope via allOf + $ref, closed
with unevaluatedProperties: false.
"""

import json
import uuid

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from conftest import SCHEMA_DIR

DRAFT_2020_12_URI = "https://json-schema.org/draft/2020-12/schema"

ENVELOPE_FILE = "telemetry-envelope-v1.schema.json"

DEVICE_SCHEMA_FILES = {
    "smartwatch": "smartwatch-v1.schema.json",
    "smart_ring": "smart-ring-v1.schema.json",
    "smart_clothing": "smart-clothing-v1.schema.json",
}

ALL_SCHEMA_FILES = [ENVELOPE_FILE, *DEVICE_SCHEMA_FILES.values()]

# CONTRACTS.md section 2 — exact required field list of the common envelope.
CONTRACTS_ENVELOPE_REQUIRED = [
    "schema_version",
    "run_id",
    "message_id",
    "seq",
    "ts",
    "egw_id",
    "device_uuid",
    "device_type",
]

# CONTRACTS.md section 2 — project UUID v5 namespace
# (egw_simulator.envelope.EGW_UUID_NAMESPACE).
EGW_UUID_NAMESPACE = uuid.UUID("6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0")

RUN_ID = "test-run-001"

# Fixed, syntactically valid UUID v4 literals (version nibble 4, variant 89ab).
DEVICE_UUIDS = {
    "smartwatch": "2f6a1c1e-3d4b-4a5e-9b6f-1a2b3c4d5e6f",
    "smart_ring": "7c8d9e0f-1a2b-4c3d-8e4f-5a6b7c8d9e0f",
    "smart_clothing": "0a1b2c3d-4e5f-4a6b-ac7d-8e9f0a1b2c3d",
}

# In-range measurement values per CONTRACTS.md section 3.
GOOD_MEASUREMENTS = {
    "smartwatch": {"heart_rate_bpm": 72, "lat": 38.7369, "lon": -9.1427},
    "smart_ring": {"skin_temp_c": 33.5, "spo2_pct": 97},
    "smart_clothing": {
        "accel_x": 0.12,
        "accel_y": -0.34,
        "accel_z": 9.81,
        "breathing_rpm": 15.0,
    },
}


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))


def make_message_id(run_id: str, device_uuid: str, seq: int) -> str:
    """UUID v5 derivation mandated by CONTRACTS.md section 2."""
    return str(uuid.uuid5(EGW_UUID_NAMESPACE, f"{run_id}:{device_uuid}:{seq}"))


def make_sample(device_type: str, seq: int = 0) -> dict:
    device_uuid = DEVICE_UUIDS[device_type]
    sample = {
        "schema_version": "1.0.0",
        "run_id": RUN_ID,
        "message_id": make_message_id(RUN_ID, device_uuid, seq),
        "seq": seq,
        "ts": "2026-08-07T12:00:00.000Z",
        "egw_id": "egw-01",
        "device_uuid": device_uuid,
        "device_type": device_type,
    }
    sample.update(GOOD_MEASUREMENTS[device_type])
    return sample


@pytest.fixture(scope="module")
def schemas() -> dict:
    return {name: _load_schema(name) for name in ALL_SCHEMA_FILES}


@pytest.fixture(scope="module")
def registry(schemas) -> Registry:
    """2020-12 registry so the envelope $id resolves without network access."""
    return Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema))
        for schema in schemas.values()
    )


@pytest.fixture(scope="module")
def validators(schemas, registry) -> dict:
    return {
        device_type: Draft202012Validator(schemas[filename], registry=registry)
        for device_type, filename in DEVICE_SCHEMA_FILES.items()
    }


# ---------------------------------------------------------------------------
# Schema files parse and are valid draft 2020-12 schemas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename", ALL_SCHEMA_FILES)
def test_schema_parses_and_is_valid_2020_12(filename):
    schema = _load_schema(filename)
    assert schema["$schema"] == DRAFT_2020_12_URI
    assert schema["$id"].startswith("https://c2dta.org/egw/schemas/")
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("device_type", sorted(DEVICE_SCHEMA_FILES))
def test_device_schema_is_closed_and_refs_envelope(schemas, device_type):
    schema = schemas[DEVICE_SCHEMA_FILES[device_type]]
    assert schema["unevaluatedProperties"] is False
    refs = [entry["$ref"] for entry in schema["allOf"]]
    assert schemas[ENVELOPE_FILE]["$id"] in refs


# ---------------------------------------------------------------------------
# Envelope required list matches CONTRACTS.md section 2
# ---------------------------------------------------------------------------


def test_envelope_required_matches_contracts(schemas):
    envelope = schemas[ENVELOPE_FILE]
    assert sorted(envelope["required"]) == sorted(CONTRACTS_ENVELOPE_REQUIRED)
    # every required field is also declared as a property
    assert set(CONTRACTS_ENVELOPE_REQUIRED) <= set(envelope["properties"])


# ---------------------------------------------------------------------------
# Known-good samples validate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("device_type", sorted(DEVICE_SCHEMA_FILES))
def test_known_good_sample_validates(validators, device_type):
    validators[device_type].validate(make_sample(device_type))


# ---------------------------------------------------------------------------
# Out-of-range measurement values are rejected (CONTRACTS.md section 3 bounds)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("device_type", "field", "bad_value"),
    [
        ("smartwatch", "heart_rate_bpm", 24),
        ("smartwatch", "heart_rate_bpm", 251),
        ("smartwatch", "heart_rate_bpm", 72.5),  # non-integer
        ("smartwatch", "lat", -90.1),
        ("smartwatch", "lat", 90.1),
        ("smartwatch", "lon", -180.5),
        ("smartwatch", "lon", 180.5),
        ("smart_ring", "skin_temp_c", 29.9),
        ("smart_ring", "skin_temp_c", 43.1),
        ("smart_ring", "spo2_pct", 49),
        ("smart_ring", "spo2_pct", 101),
        ("smart_ring", "spo2_pct", 97.5),  # non-integer
        ("smart_clothing", "accel_x", -78.5),
        ("smart_clothing", "accel_y", 78.5),
        ("smart_clothing", "accel_z", 100.0),
        ("smart_clothing", "breathing_rpm", 3.9),
        ("smart_clothing", "breathing_rpm", 60.1),
    ],
)
def test_out_of_range_value_rejected(validators, device_type, field, bad_value):
    sample = make_sample(device_type)
    sample[field] = bad_value
    assert not validators[device_type].is_valid(sample)


# ---------------------------------------------------------------------------
# Extra fields are rejected (unevaluatedProperties: false)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("device_type", sorted(DEVICE_SCHEMA_FILES))
def test_extra_field_rejected(validators, device_type):
    sample = make_sample(device_type)
    sample["unexpected_field"] = 1
    assert not validators[device_type].is_valid(sample)


@pytest.mark.parametrize(
    ("device_type", "foreign_field", "value"),
    [
        # measurement field belonging to another device type
        ("smartwatch", "spo2_pct", 97),
        ("smart_ring", "heart_rate_bpm", 72),
        ("smart_clothing", "skin_temp_c", 33.5),
    ],
)
def test_foreign_measurement_field_rejected(validators, device_type, foreign_field, value):
    sample = make_sample(device_type)
    sample[foreign_field] = value
    assert not validators[device_type].is_valid(sample)


# ---------------------------------------------------------------------------
# Missing fields are rejected (measurement and envelope)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("device_type", "missing_field"),
    [
        ("smartwatch", "heart_rate_bpm"),
        ("smartwatch", "lat"),
        ("smartwatch", "lon"),
        ("smart_ring", "skin_temp_c"),
        ("smart_ring", "spo2_pct"),
        ("smart_clothing", "accel_x"),
        ("smart_clothing", "accel_y"),
        ("smart_clothing", "accel_z"),
        ("smart_clothing", "breathing_rpm"),
    ],
)
def test_missing_measurement_field_rejected(validators, device_type, missing_field):
    sample = make_sample(device_type)
    del sample[missing_field]
    assert not validators[device_type].is_valid(sample)


@pytest.mark.parametrize("missing_field", CONTRACTS_ENVELOPE_REQUIRED)
@pytest.mark.parametrize("device_type", sorted(DEVICE_SCHEMA_FILES))
def test_missing_envelope_field_rejected(validators, device_type, missing_field):
    sample = make_sample(device_type)
    del sample[missing_field]
    assert not validators[device_type].is_valid(sample)


# ---------------------------------------------------------------------------
# Wrong device_type constant is rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("device_type", sorted(DEVICE_SCHEMA_FILES))
def test_wrong_device_type_rejected(validators, device_type):
    sample = make_sample(device_type)
    other = next(dt for dt in DEVICE_SCHEMA_FILES if dt != device_type)
    sample["device_type"] = other
    assert not validators[device_type].is_valid(sample)


# ---------------------------------------------------------------------------
# message_id / device_uuid UUID version behaviour (v5 vs v4)
# ---------------------------------------------------------------------------


def test_derived_message_id_is_uuid_v5():
    message_id = make_message_id(RUN_ID, DEVICE_UUIDS["smartwatch"], 0)
    assert uuid.UUID(message_id).version == 5
    assert message_id[14] == "5"  # version nibble in canonical form


def test_message_id_must_be_uuid_v5_not_v4(validators):
    sample = make_sample("smartwatch")
    # syntactically valid UUID v4 — wrong version for message_id
    sample["message_id"] = DEVICE_UUIDS["smart_ring"]
    assert not validators["smartwatch"].is_valid(sample)


def test_message_id_uppercase_rejected(validators):
    sample = make_sample("smartwatch")
    sample["message_id"] = sample["message_id"].upper()
    assert not validators["smartwatch"].is_valid(sample)


def test_device_uuid_must_be_uuid_v4_not_v5(validators):
    sample = make_sample("smartwatch")
    # valid UUID v5 — wrong version for device_uuid
    sample["device_uuid"] = make_message_id(RUN_ID, DEVICE_UUIDS["smartwatch"], 0)
    assert not validators["smartwatch"].is_valid(sample)


def test_device_uuid_v4_accepted_in_envelope():
    for device_uuid in DEVICE_UUIDS.values():
        assert uuid.UUID(device_uuid).version == 4
