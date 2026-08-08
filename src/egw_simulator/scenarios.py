"""Scenario registry, disconnect windows and invalid-payload injection.

Implements the six normative scenarios of CONTRACTS.md section 7 / plan
section 4.3: smoke, nominal, load-sweep, dropout-reconnect, invalid-payload
and soak. Everything here is deterministic for a given seed (plan section
5.6); wall-clock time never enters window or injection decisions.

dropout-reconnect (plan section 7.2): windows are run-level disconnect
windows — the runner drops the MQTT connection at each window start, keeps
generating (and buffering) events on schedule, and reconnects/flushes in
order at window end. See ``DROPOUT_SCOPE_NOTE`` for the binding statement
recorded in the run manifest.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .devices import NOMINAL_AGGREGATE_RATE_HZ
from .profiles import MEASUREMENT_FIELDS

#: Default injection ratio for invalid-payload: 1 event in 20 per device.
DEFAULT_INVALID_RATIO = 20

#: Scope statement recorded in the manifest of every dropout-reconnect run.
#: The scenario performs a REAL client-side disconnect/reconnect cycle with
#: device-side buffering (plan section 7.2 'recuperacao apos
#: restart/reconnect'). The harness reads this note verbatim for its dropout
#: acceptance rule: keep the text precise.
DROPOUT_SCOPE_NOTE = (
    "dropout-reconnect performs a real client disconnect with buffered "
    "redelivery: at each deterministic window the simulator drops its MQTT "
    "connection (client disconnect, socket closed); events scheduled inside "
    "the window are still generated on schedule and buffered locally in "
    "order; at window end the client reconnects and flushes the buffer in "
    "order before resuming live publishing. Every generated event is "
    "published exactly once, seq stays strictly monotonic and gap-free, and "
    "buffered events carry a late publish_monotonic_ns (the actual publish "
    "instant). PUBACK capture stays best-effort (CONTRACTS.md section 7, "
    "v1.1). Broker-side/network-level faults remain test-harness territory."
)

#: Mutation kinds applied to intentionally invalid events.
INVALID_MUTATION_KINDS: tuple[str, ...] = (
    "out_of_range",
    "missing_field",
    "wrong_type",
)

#: One guaranteed-out-of-range value per measurement field (outside the
#: bounds of the corresponding JSON Schema).
OUT_OF_RANGE_VALUES: dict[str, object] = {
    "heart_rate_bpm": 999,      # schema max 250
    "lat": 123.456,             # schema max 90
    "lon": 250.0,               # schema max 180
    "skin_temp_c": 99.9,        # schema max 43.0
    "spo2_pct": 101,            # schema max 100
    "accel_x": 500.0,           # schema max 78.0
    "accel_y": 500.0,
    "accel_z": 500.0,
    "breathing_rpm": 0.5,       # schema min 4.0
}


@dataclass(frozen=True)
class ScenarioSpec:
    """Static description of one scenario.

    ``default_rate_hz`` of ``None`` means the aggregate rate must come from
    ``--rate`` (load-sweep). ``invalid_ratio`` of 0 disables injection.
    """

    name: str
    description: str
    default_duration_s: float
    default_rate_hz: float | None
    invalid_ratio: int = 0
    dropout: bool = False


SCENARIOS: dict[str, ScenarioSpec] = {
    spec.name: spec
    for spec in (
        ScenarioSpec(
            "smoke",
            "Short functional check: 3 devices at nominal rates for 30 s",
            30.0,
            NOMINAL_AGGREGATE_RATE_HZ,
        ),
        ScenarioSpec(
            "nominal",
            "Nominal aggregate load, 11.2 msg/s for 600 s (plan section 7.1)",
            600.0,
            NOMINAL_AGGREGATE_RATE_HZ,
        ),
        ScenarioSpec(
            "load-sweep",
            "Nominal profile at an operator-chosen aggregate rate "
            "(--rate required); five-minute executions per plan section 7.1",
            300.0,
            None,
        ),
        ScenarioSpec(
            "dropout-reconnect",
            "Nominal load with deterministic disconnect windows: real MQTT "
            "client disconnect, device-side buffering, reconnect and "
            "in-order flush at window end (see DROPOUT_SCOPE_NOTE)",
            600.0,
            NOMINAL_AGGREGATE_RATE_HZ,
            dropout=True,
        ),
        ScenarioSpec(
            "invalid-payload",
            "Nominal load with a deterministic 1-in-20 invalid-event injection",
            600.0,
            NOMINAL_AGGREGATE_RATE_HZ,
            invalid_ratio=DEFAULT_INVALID_RATIO,
        ),
        ScenarioSpec(
            "soak",
            "24-hour nominal stability run (plan section 7.1)",
            86400.0,
            NOMINAL_AGGREGATE_RATE_HZ,
        ),
    )
}


def dropout_windows(
    seed: int,
    duration_s: float,
    *,
    mean_period_s: float = 60.0,
    min_len_s: float = 2.0,
    max_len_s: float = 8.0,
) -> list[tuple[float, float]]:
    """Deterministic run-level disconnect windows for dropout-reconnect.

    Roughly one window per ``mean_period_s`` of run time (at least one),
    each 2-8 s long (capped at half its segment), placed uniformly inside
    consecutive equal segments so windows never overlap and stay ordered.
    Fully determined by (seed, duration_s).

    Windows are run-level, not per-device: the simulator holds ONE MQTT
    connection for all simulated wearables, so a window means the client
    disconnects at the window start and reconnects at the window end (see
    ``DROPOUT_SCOPE_NOTE``). Events scheduled inside a window keep being
    generated and are buffered by the runner, then flushed in order on
    reconnect.
    """
    if duration_s <= 0:
        return []
    rng = random.Random(f"egw-dropout:{seed}")
    n_windows = max(1, int(duration_s // mean_period_s))
    seg_len = duration_s / n_windows
    windows: list[tuple[float, float]] = []
    for i in range(n_windows):
        seg_start = i * seg_len
        length = min(rng.uniform(min_len_s, max_len_s), seg_len * 0.5)
        start = seg_start + rng.uniform(0.0, max(0.0, seg_len - length))
        windows.append((round(start, 3), round(start + length, 3)))
    return windows


def window_index(t_s: float, windows) -> int | None:
    """Index of the half-open window containing ``t_s``, or ``None``.

    Windows are ``(start, end)`` pairs with ``start <= t < end`` membership.
    Shared by the runner and the tests so both sides agree exactly.
    """
    for i, (start, end) in enumerate(windows):
        if start <= t_s < end:
            return i
    return None


def in_window(t_s: float, windows) -> bool:
    """True when scheduled time ``t_s`` falls inside any half-open window."""
    return window_index(t_s, windows) is not None


class InvalidInjector:
    """Deterministic invalid-event injection for one device.

    One event in ``ratio`` is made invalid: the flagged sequence numbers are
    ``seq % ratio == offset`` with an offset derived from (seed,
    device_uuid). The mutation applied at a given seq is itself derived from
    (seed, device_uuid, seq), so re-runs with the same seed flag the same
    positions and produce byte-identical mutations. The invalid marker lives
    only in the simulator's own record (``intended_invalid``), never in the
    payload (plan section 5.6).
    """

    def __init__(
        self, seed: int, device_uuid: str, ratio: int = DEFAULT_INVALID_RATIO
    ) -> None:
        if ratio < 2:
            raise ValueError("invalid-injection ratio must be >= 2")
        self.seed = seed
        self.device_uuid = device_uuid
        self.ratio = ratio
        self.offset = random.Random(
            f"egw-invalid-offset:{seed}:{device_uuid}"
        ).randrange(ratio)

    def is_invalid(self, seq: int) -> bool:
        """True when the event with this seq must be published invalid."""
        return seq % self.ratio == self.offset

    def mutate(self, payload: dict, seq: int) -> dict:
        """Return a mutated copy of ``payload`` guaranteed to fail validation.

        Mutations only touch measurement fields (never the envelope), so the
        controller exercises its schema-validation path rather than parsing
        errors. Kinds: out-of-range value, missing required field, wrong type.
        """
        rng = random.Random(
            f"egw-invalid-mutation:{self.seed}:{self.device_uuid}:{seq}"
        )
        device_type = payload["device_type"]
        field = rng.choice(MEASUREMENT_FIELDS[device_type])
        kind = rng.choice(INVALID_MUTATION_KINDS)
        mutated = dict(payload)
        if kind == "out_of_range":
            mutated[field] = OUT_OF_RANGE_VALUES[field]
        elif kind == "missing_field":
            del mutated[field]
        else:  # wrong_type
            mutated[field] = "not-a-number"
        return mutated
