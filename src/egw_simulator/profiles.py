"""Deterministic measurement profiles for the three wearables (CONTRACTS.md section 3).

Each profile owns a private ``random.Random`` seeded from (run seed,
device_uuid), so streams are reproducible per device and independent of each
other. Generated values are ALWAYS inside the JSON Schema bounds; the
profiles deliberately operate on narrower physiological ranges and clamp
before rounding.
"""

from __future__ import annotations

import random
from typing import Protocol

#: Reference walk centre: Lisbon (plan scenario context).
LISBON_LAT = 38.7369
LISBON_LON = -9.1427

#: Measurement fields per device type (top-level, next to the envelope).
MEASUREMENT_FIELDS: dict[str, tuple[str, ...]] = {
    "smartwatch": ("heart_rate_bpm", "lat", "lon"),
    "smart_ring": ("skin_temp_c", "spo2_pct"),
    "smart_clothing": ("accel_x", "accel_y", "accel_z", "breathing_rpm"),
}


def _clamp(value, lo, hi):
    return lo if value < lo else hi if value > hi else value


class MeasurementProfile(Protocol):
    """A stateful deterministic generator of measurement dicts."""

    def next(self) -> dict: ...


class SmartwatchProfile:
    """Bounded random walk: heart rate 55-185 bpm + small geo walk near Lisbon.

    Schema bounds are wider (25-250 bpm, full lat/lon range), so values are
    always valid. Latitude/longitude are rounded to 6 decimals (~0.1 m).
    """

    DEVICE_TYPE = "smartwatch"
    HR_MIN, HR_MAX = 55, 185
    GEO_RADIUS_DEG = 0.01

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._hr = rng.randint(60, 100)
        self._lat = LISBON_LAT + rng.uniform(-0.005, 0.005)
        self._lon = LISBON_LON + rng.uniform(-0.005, 0.005)

    def next(self) -> dict:
        rng = self._rng
        self._hr = _clamp(self._hr + rng.randint(-3, 3), self.HR_MIN, self.HR_MAX)
        self._lat = _clamp(
            self._lat + rng.uniform(-2e-4, 2e-4),
            LISBON_LAT - self.GEO_RADIUS_DEG,
            LISBON_LAT + self.GEO_RADIUS_DEG,
        )
        self._lon = _clamp(
            self._lon + rng.uniform(-2e-4, 2e-4),
            LISBON_LON - self.GEO_RADIUS_DEG,
            LISBON_LON + self.GEO_RADIUS_DEG,
        )
        return {
            "heart_rate_bpm": self._hr,
            "lat": round(self._lat, 6),
            "lon": round(self._lon, 6),
        }


class SmartRingProfile:
    """Skin temperature walk 35.5-37.8 C with correlated-ish SpO2 90-100 %.

    SpO2 performs its own small integer walk, biased downwards while skin
    temperature is elevated (>= 37.3 C). Schema bounds (30-43 C, 50-100 %)
    are never violated.
    """

    DEVICE_TYPE = "smart_ring"
    TEMP_MIN, TEMP_MAX = 35.5, 37.8
    SPO2_MIN, SPO2_MAX = 90, 100

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._temp = rng.uniform(36.2, 37.0)
        self._spo2 = rng.randint(95, 99)

    def next(self) -> dict:
        rng = self._rng
        self._temp = _clamp(
            self._temp + rng.uniform(-0.06, 0.06), self.TEMP_MIN, self.TEMP_MAX
        )
        bias = -1 if (self._temp >= 37.3 and rng.random() < 0.5) else 0
        self._spo2 = _clamp(
            self._spo2 + rng.choice((-1, 0, 0, 0, 1)) + bias,
            self.SPO2_MIN,
            self.SPO2_MAX,
        )
        return {
            "skin_temp_c": round(self._temp, 2),
            "spo2_pct": self._spo2,
        }


class SmartClothingProfile:
    """Activity-modulated 3-axis acceleration + breathing rate 10-40 rpm.

    A slowly drifting activity level in [0, 1] scales the acceleration noise
    amplitude (Gaussian around 0 for x/y, around gravity for z) and shifts
    the breathing rate. Final values are clamped to well inside the schema
    bounds (accel +/-78 m/s^2, breathing 4-60 rpm).
    """

    DEVICE_TYPE = "smart_clothing"
    ACCEL_LIMIT = 78.0
    GRAVITY = 9.81
    BREATH_MIN, BREATH_MAX = 10.0, 40.0

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._activity = rng.uniform(0.1, 0.6)

    def next(self) -> dict:
        rng = self._rng
        self._activity = _clamp(self._activity + rng.uniform(-0.03, 0.03), 0.0, 1.0)
        amp = 0.4 + 24.0 * self._activity
        sigma = amp / 3.0
        ax = _clamp(rng.gauss(0.0, sigma), -self.ACCEL_LIMIT, self.ACCEL_LIMIT)
        ay = _clamp(rng.gauss(0.0, sigma), -self.ACCEL_LIMIT, self.ACCEL_LIMIT)
        az = _clamp(
            self.GRAVITY + rng.gauss(0.0, sigma), -self.ACCEL_LIMIT, self.ACCEL_LIMIT
        )
        breathing = _clamp(
            10.0 + 28.0 * self._activity + rng.uniform(-1.5, 1.5),
            self.BREATH_MIN,
            self.BREATH_MAX,
        )
        return {
            "accel_x": round(ax, 3),
            "accel_y": round(ay, 3),
            "accel_z": round(az, 3),
            "breathing_rpm": round(breathing, 1),
        }


_PROFILE_CLASSES = {
    "smartwatch": SmartwatchProfile,
    "smart_ring": SmartRingProfile,
    "smart_clothing": SmartClothingProfile,
}


def profile_rng(seed: int, device_uuid: str) -> random.Random:
    """Dedicated deterministic RNG stream for one device's measurements."""
    return random.Random(f"egw-profile:{seed}:{device_uuid}")


def make_profile(device_type: str, seed: int, device_uuid: str) -> MeasurementProfile:
    """Build the measurement profile for a device, seeded deterministically."""
    try:
        cls = _PROFILE_CLASSES[device_type]
    except KeyError:
        raise ValueError(
            f"unknown device type {device_type!r}; valid: {', '.join(_PROFILE_CLASSES)}"
        ) from None
    return cls(profile_rng(seed, device_uuid))
