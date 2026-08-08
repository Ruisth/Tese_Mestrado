"""Core simulator tests: envelope, devices, rate split, profiles, scenarios.

Binding references: CONTRACTS.md sections 2 (envelope, UUID v5 namespace),
3 (measurement fields, bounds, 1:0.2:10 rate split) and 7 (scenarios,
determinism); plan section 5.6. No broker is needed.
"""

import re
import uuid
from datetime import datetime, timezone

import pytest

from egw_simulator.devices import (
    DEVICE_TYPES,
    NOMINAL_RATES_HZ,
    make_devices,
    split_rate,
)
from egw_simulator.envelope import (
    EGW_UUID_NAMESPACE,
    SCHEMA_VERSION,
    build_envelope,
    make_message_id,
    rfc3339_utc_ms,
)
from egw_simulator.profiles import LISBON_LAT, LISBON_LON, make_profile
from egw_simulator.scenarios import (
    DEFAULT_INVALID_RATIO,
    SCENARIOS,
    InvalidInjector,
    dropout_windows,
    in_window,
)
from egw_simulator.validation import SchemaValidator

UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
UUID5_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

FIXED_TS = "2026-01-01T00:00:00.000Z"
STREAM_N = 50


@pytest.fixture(scope="module")
def validator() -> SchemaValidator:
    return SchemaValidator()


def payload_streams(seed: int, run_id: str = "det-run-1", egw_id: str = "egw-01",
                    n: int = STREAM_N) -> dict:
    """Deterministic per-device payload streams with a fixed ts."""
    streams = {}
    for dev in make_devices(seed):
        profile = make_profile(dev.device_type, seed, dev.device_uuid)
        payloads = []
        for seq in range(n):
            payload = build_envelope(
                run_id=run_id,
                egw_id=egw_id,
                device_uuid=dev.device_uuid,
                device_type=dev.device_type,
                seq=seq,
                ts=FIXED_TS,
            )
            payload.update(profile.next())
            payloads.append(payload)
        streams[dev.device_type] = payloads
    return streams


# ---------------------------------------------------------------- envelope

def test_uuid_namespace_exact_contract_value():
    assert str(EGW_UUID_NAMESPACE) == "6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0"


def test_message_id_is_reproducible_uuid5():
    device_uuid = "2f6a1c1e-3d4b-4a5e-9b6f-1a2b3c4d5e6f"
    mid = make_message_id("run-1", device_uuid, 5)
    assert UUID5_RE.fullmatch(mid)
    parsed = uuid.UUID(mid)
    assert parsed.version == 5
    assert parsed == uuid.uuid5(EGW_UUID_NAMESPACE, f"run-1:{device_uuid}:5")
    # Reproducible: same inputs, same id; different seq, different id.
    assert make_message_id("run-1", device_uuid, 5) == mid
    assert make_message_id("run-1", device_uuid, 6) != mid


def test_rfc3339_utc_ms_format():
    dt = datetime(2026, 8, 7, 12, 34, 56, 789499, tzinfo=timezone.utc)
    assert rfc3339_utc_ms(dt) == "2026-08-07T12:34:56.789Z"
    assert TS_RE.fullmatch(rfc3339_utc_ms())


def test_rfc3339_utc_ms_rejects_naive_datetime():
    with pytest.raises(ValueError):
        rfc3339_utc_ms(datetime(2026, 8, 7, 12, 0, 0))


def test_build_envelope_fields():
    device_uuid = "2f6a1c1e-3d4b-4a5e-9b6f-1a2b3c4d5e6f"
    env = build_envelope(
        run_id="run-1",
        egw_id="egw-01",
        device_uuid=device_uuid,
        device_type="smartwatch",
        seq=3,
        ts=FIXED_TS,
    )
    assert env == {
        "schema_version": SCHEMA_VERSION,
        "run_id": "run-1",
        "message_id": make_message_id("run-1", device_uuid, 3),
        "seq": 3,
        "ts": FIXED_TS,
        "egw_id": "egw-01",
        "device_uuid": device_uuid,
        "device_type": "smartwatch",
    }
    with pytest.raises(ValueError):
        build_envelope(
            run_id="run-1",
            egw_id="egw-01",
            device_uuid=device_uuid,
            device_type="smartwatch",
            seq=-1,
        )


# ----------------------------------------------------------------- devices

def test_device_uuids_stable_for_same_seed():
    first = make_devices(123)
    second = make_devices(123)
    assert first == second
    assert [d.device_type for d in first] == list(DEVICE_TYPES)
    for dev in first:
        assert UUID4_RE.fullmatch(dev.device_uuid)


def test_device_uuids_differ_across_seeds():
    uuids_a = {d.device_uuid for d in make_devices(1)}
    uuids_b = {d.device_uuid for d in make_devices(2)}
    assert uuids_a.isdisjoint(uuids_b)


def test_rate_split_contract_example():
    split = split_rate(11.2)
    assert split["smartwatch"] == pytest.approx(1.0)
    assert split["smart_ring"] == pytest.approx(0.2)
    assert split["smart_clothing"] == pytest.approx(10.0)
    assert sum(split.values()) == pytest.approx(11.2)


def test_rate_split_is_proportional():
    split = split_rate(112.0)
    assert split["smartwatch"] == pytest.approx(10.0)
    assert split["smart_ring"] == pytest.approx(2.0)
    assert split["smart_clothing"] == pytest.approx(100.0)


def test_rate_split_subset_renormalised():
    split = split_rate(5.5, ["smartwatch", "smart_clothing"])
    assert set(split) == {"smartwatch", "smart_clothing"}
    assert split["smartwatch"] == pytest.approx(0.5)
    assert split["smart_clothing"] == pytest.approx(5.0)


def test_rate_split_rejects_bad_input():
    with pytest.raises(ValueError):
        split_rate(0.0)
    with pytest.raises(ValueError):
        split_rate(-1.0)
    with pytest.raises(ValueError):
        split_rate(1.0, ["drone"])
    with pytest.raises(ValueError):
        split_rate(1.0, [])


def test_nominal_rates_match_contract():
    assert NOMINAL_RATES_HZ == {
        "smartwatch": 1.0,
        "smart_ring": 0.2,
        "smart_clothing": 10.0,
    }


# ---------------------------------------------------------------- profiles

def test_payload_streams_identical_for_same_seed():
    assert payload_streams(7) == payload_streams(7)


def test_payload_streams_differ_across_seeds():
    streams_a = payload_streams(7)
    streams_b = payload_streams(8)
    assert streams_a != streams_b
    uuids_a = {p[0]["device_uuid"] for p in streams_a.values()}
    uuids_b = {p[0]["device_uuid"] for p in streams_b.values()}
    assert uuids_a.isdisjoint(uuids_b)


def test_all_nominal_payloads_validate_against_schemas(validator):
    streams = payload_streams(11)
    assert sorted(streams) == sorted(DEVICE_TYPES)
    for device_type, payloads in streams.items():
        assert len(payloads) == STREAM_N
        for payload in payloads:
            validator.validate(payload)  # raises on any violation


def test_measurement_values_stay_inside_design_bounds():
    streams = payload_streams(19, n=200)
    for payload in streams["smartwatch"]:
        assert isinstance(payload["heart_rate_bpm"], int)
        assert 55 <= payload["heart_rate_bpm"] <= 185
        assert abs(payload["lat"] - LISBON_LAT) <= 0.01
        assert abs(payload["lon"] - LISBON_LON) <= 0.01
    for payload in streams["smart_ring"]:
        assert 35.5 <= payload["skin_temp_c"] <= 37.8
        assert isinstance(payload["spo2_pct"], int)
        assert 90 <= payload["spo2_pct"] <= 100
    for payload in streams["smart_clothing"]:
        for axis in ("accel_x", "accel_y", "accel_z"):
            assert -78.0 <= payload[axis] <= 78.0
        assert 10.0 <= payload["breathing_rpm"] <= 40.0


# --------------------------------------------------------------- scenarios

def test_scenario_registry_matches_contract():
    assert set(SCENARIOS) == {
        "smoke",
        "nominal",
        "load-sweep",
        "dropout-reconnect",
        "invalid-payload",
        "soak",
    }
    assert SCENARIOS["smoke"].default_duration_s == 30.0
    assert SCENARIOS["smoke"].default_rate_hz == pytest.approx(11.2)
    assert SCENARIOS["nominal"].default_duration_s == 600.0
    assert SCENARIOS["nominal"].default_rate_hz == pytest.approx(11.2)
    assert SCENARIOS["load-sweep"].default_rate_hz is None
    # Ten five-minute executions per load (plan section 7.1).
    assert SCENARIOS["load-sweep"].default_duration_s == 300.0
    assert SCENARIOS["dropout-reconnect"].dropout is True
    assert SCENARIOS["invalid-payload"].invalid_ratio == DEFAULT_INVALID_RATIO == 20
    assert SCENARIOS["soak"].default_duration_s == 86400.0
    for name, spec in SCENARIOS.items():
        assert spec.name == name
        if name != "invalid-payload":
            assert spec.invalid_ratio == 0
        if name != "dropout-reconnect":
            assert spec.dropout is False


def test_dropout_windows_deterministic_and_bounded():
    device_uuid = "2f6a1c1e-3d4b-4a5e-9b6f-1a2b3c4d5e6f"
    windows = dropout_windows(42, device_uuid, 600.0)
    assert windows == dropout_windows(42, device_uuid, 600.0)
    assert len(windows) == 10  # one per 60 s of run time
    previous_end = 0.0
    rounding_tol = 0.002  # windows are rounded to 3 decimals
    for start, end in windows:
        assert 0.0 <= start < end <= 600.0 + rounding_tol
        assert end - start <= 8.0 + rounding_tol
        assert start >= previous_end - rounding_tol  # non-overlapping, ordered
        previous_end = end


def test_dropout_windows_vary_with_seed_and_device():
    device_a = "2f6a1c1e-3d4b-4a5e-9b6f-1a2b3c4d5e6f"
    device_b = "7c8d9e0f-1a2b-4c3d-8e4f-5a6b7c8d9e0f"
    assert dropout_windows(42, device_a, 600.0) != dropout_windows(42, device_b, 600.0)
    assert dropout_windows(42, device_a, 600.0) != dropout_windows(43, device_a, 600.0)


def test_in_window_half_open_membership():
    windows = [(0.5, 2.0), (10.0, 12.0)]
    assert in_window(0.5, windows) is True
    assert in_window(1.999, windows) is True
    assert in_window(2.0, windows) is False
    assert in_window(0.499, windows) is False
    assert in_window(11.0, windows) is True


def test_invalid_injector_positions_deterministic():
    device_uuid = "2f6a1c1e-3d4b-4a5e-9b6f-1a2b3c4d5e6f"
    injector = InvalidInjector(42, device_uuid)
    again = InvalidInjector(42, device_uuid)
    assert injector.ratio == DEFAULT_INVALID_RATIO
    assert injector.offset == again.offset
    assert 0 <= injector.offset < injector.ratio
    flagged = {seq for seq in range(200) if injector.is_invalid(seq)}
    assert flagged == {
        seq for seq in range(200) if seq % injector.ratio == injector.offset
    }
    assert len(flagged) == 10  # exactly 1 in 20 over 200 events


def test_invalid_mutations_fail_validation_and_are_deterministic(validator):
    seed = 42
    streams = payload_streams(seed)
    for dev in make_devices(seed):
        injector = InvalidInjector(seed, dev.device_uuid)
        flagged = [seq for seq in range(STREAM_N) if injector.is_invalid(seq)]
        assert flagged  # at least offset and offset+20 are below 50
        for seq in flagged:
            original = streams[dev.device_type][seq]
            assert validator.is_valid(original)
            mutated = injector.mutate(original, seq)
            assert mutated != original
            assert not validator.is_valid(mutated)
            # Marker never goes into the payload (CONTRACTS.md section 7).
            assert "intended_invalid" not in mutated
            # Envelope untouched; deterministic byte-identical mutation.
            assert mutated["message_id"] == original["message_id"]
            assert injector.mutate(original, seq) == mutated
            # mutate() must not modify its input.
            assert validator.is_valid(original)
