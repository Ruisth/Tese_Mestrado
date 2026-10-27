"""Device identities and aggregate-rate split (CONTRACTS.md sections 2-3).

Device UUIDs are RFC 4122 version-4 formatted but derived deterministically
from the run seed, so the same ``--seed`` always yields the same stable
``device_uuid`` set (plan section 5.6 determinism requirement) while still
matching the ``device_uuid`` v4 pattern in the envelope schema.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

#: Canonical device types (CONTRACTS.md section 2).
DEVICE_TYPES: tuple[str, ...] = ("smartwatch", "smart_ring", "smart_clothing")

#: Nominal per-device rates in msg/s (CONTRACTS.md section 3). These are also
#: the fixed weights (1 : 0.2 : 10) used to split the aggregate ``--rate``.
NOMINAL_RATES_HZ: dict[str, float] = {
    "smartwatch": 1.0,
    "smart_ring": 0.2,
    "smart_clothing": 10.0,
}

#: Nominal aggregate rate: 1.0 + 0.2 + 10.0 (plan sections 5.6 and 7.3).
NOMINAL_AGGREGATE_RATE_HZ = 11.2


@dataclass(frozen=True)
class DeviceSpec:
    """One simulated wearable: its type and stable UUID."""

    device_type: str
    device_uuid: str


def device_uuid_for(seed: int, device_type: str, index: int = 0) -> str:
    """Deterministic v4-formatted UUID for a device, derived from the seed.

    Uses a dedicated ``random.Random`` stream keyed on (seed, device_type,
    index) so device identity does not perturb the measurement streams.
    """
    rng = random.Random(f"egw-device-uuid:{seed}:{device_type}:{index}")
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def make_devices(
    seed: int, device_types: tuple[str, ...] | list[str] = DEVICE_TYPES
) -> list[DeviceSpec]:
    """Build the deterministic device set for a run."""
    unknown = [t for t in device_types if t not in DEVICE_TYPES]
    if unknown:
        raise ValueError(
            f"unknown device types {unknown!r}; valid: {', '.join(DEVICE_TYPES)}"
        )
    return [DeviceSpec(t, device_uuid_for(seed, t)) for t in device_types]


def split_rate(
    aggregate_rate_hz: float,
    device_types: tuple[str, ...] | list[str] = DEVICE_TYPES,
) -> dict[str, float]:
    """Split the aggregate rate across device types in fixed 1:0.2:10 ratio.

    With all three types, ``--rate 11.2`` yields smartwatch 1.0, smart_ring
    0.2 and smart_clothing 10.0 msg/s (CONTRACTS.md section 3). With a subset
    of types the same weights are renormalised over the selected types.
    """
    if aggregate_rate_hz <= 0:
        raise ValueError("aggregate rate must be positive")
    unknown = [t for t in device_types if t not in NOMINAL_RATES_HZ]
    if unknown:
        raise ValueError(
            f"unknown device types {unknown!r}; valid: {', '.join(DEVICE_TYPES)}"
        )
    if not device_types:
        raise ValueError("at least one device type is required")
    weights = {t: NOMINAL_RATES_HZ[t] for t in device_types}
    total = sum(weights.values())
    return {t: aggregate_rate_hz * w / total for t, w in weights.items()}
