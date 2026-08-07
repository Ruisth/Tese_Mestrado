"""Frozen experimental protocol (plan section 7.1) expressed as data.

This module is the single source of truth for the experimental conditions.
After gate G4 ("protocolo congelado", tag ``exp-v1``) any change here is a
protocol change and requires a new ``PROTOCOL_VERSION`` plus a LOG entry;
metrics, conditions and exclusion criteria must not change after G4.

Conditions (plan 7.1):

- ``qemu_boots``     : 5 QEMU boots, functional consistency only, never a
                       source of performance claims (plan 5.1).
- ``cold_start``     : 10 cold starts of the ARM stack (time to readiness).
- ``twin_creation``  : 10 independent twin creations.
- ``nominal``        : 10 runs x 600 s at the nominal aggregate rate
                       (~11.2 msg/s, plan 7.3) after 120 s warm-up.
- ``load_sweep``     : rates 10/50/100/250 msg/s, 10 runs x 300 s per rate,
                       randomized execution order (derived from the campaign
                       master seed), 120 s cooldown between runs.
- ``soak``           : 1 x 24 h nominal run, analyzed descriptively only
                       (no confidence interval, plan 7.3).

CPU and RAM are sampled every second in every timed run (plan 7.1).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

# Version of the frozen protocol implemented by this package. Bump only via a
# documented protocol change (see module docstring).
PROTOCOL_VERSION = "1.0.0"

# Nominal aggregate rate treated as the nominal scenario, never as a
# previously demonstrated maximum capacity (plan 7.3, CONTRACTS 3:
# smartwatch 1.0 + smart_ring 0.2 + smart_clothing 10.0 msg/s).
NOMINAL_RATE_MSG_S = 11.2

# A valid sent message without a unique Ditto confirmation within this window
# after the end of the run counts as lost (plan 7.3, CONTRACTS 9).
CONFIRMATION_WINDOW_S = 60

# CPU/RAM sampling cadence for all timed runs (plan 7.1).
RESOURCE_SAMPLE_INTERVAL_S = 1.0

# Operational saturation criteria (plan 7.3): first load with at least one of
# loss > 1%, persistent queue growth, p95 > 1 s, or CPU sustained above 90%
# for 60 s. Queue growth is not measurable with the current instrumentation
# and is marked TODO in the analysis output.
SATURATION_LOSS_RATE = 0.01
SATURATION_P95_MS = 1000.0
SATURATION_CPU_PCT = 90.0
SATURATION_CPU_SUSTAIN_S = 60


@dataclass(frozen=True)
class Condition:
    """One experimental condition of the frozen protocol."""

    id: str
    # "simulator": executed by egw_experiments.run via the simulator CLI
    # (CONTRACTS 7). "external": measured by deployment/platform procedures
    # (cold start timing, twin creation, QEMU boots); the harness only plans
    # and tracks these runs.
    runner: str
    # Simulator scenario name (CONTRACTS 7) or None for external conditions.
    scenario: str | None
    repetitions: int
    duration_s: int | None
    warmup_s: int
    cooldown_s: int
    # For load_sweep: the swept aggregate rates. None otherwise.
    rates_msg_s: tuple[float, ...] | None
    # Fixed aggregate rate for non-sweep simulator conditions.
    rate_msg_s: float | None
    # Metrics collected for this condition (plan 7.2).
    metrics: tuple[str, ...]
    # False for QEMU: functional validation only, no performance inference.
    performance_claims_allowed: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict (tuples become lists)."""
        d = asdict(self)
        if d["rates_msg_s"] is not None:
            d["rates_msg_s"] = list(d["rates_msg_s"])
        d["metrics"] = list(d["metrics"])
        return d


# Conditions in campaign execution order (functional platform checks first,
# then timed conditions, soak last).
CONDITIONS: tuple[Condition, ...] = (
    Condition(
        id="qemu_boots",
        runner="external",
        scenario=None,
        repetitions=5,
        duration_s=None,
        warmup_s=0,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=None,
        metrics=("boot_functional", "systemd_reached", "container_runtime_ok"),
        performance_claims_allowed=False,
        notes=(
            "Five QEMU boots for functional consistency only; QEMU results "
            "never support performance conclusions (plan 5.1/7.1)."
        ),
    ),
    Condition(
        id="cold_start",
        runner="external",
        scenario=None,
        repetitions=10,
        duration_s=None,
        warmup_s=0,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=None,
        metrics=("time_to_readiness_s", "cpu_pct_per_container", "mem_bytes_per_container"),
        performance_claims_allowed=True,
        notes=(
            "Ten cold starts of the ARM stack; time until the controller "
            "/ready endpoint reports 200 (plan 7.1/7.2, CONTRACTS 5)."
        ),
    ),
    Condition(
        id="twin_creation",
        runner="external",
        scenario=None,
        repetitions=10,
        duration_s=None,
        warmup_s=0,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=None,
        metrics=("twin_creation_time_ms",),
        performance_claims_allowed=True,
        notes="Ten independent twin creations (policy + thing, CONTRACTS 4).",
    ),
    Condition(
        id="nominal",
        runner="simulator",
        scenario="nominal",
        repetitions=10,
        duration_s=600,
        warmup_s=120,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=NOMINAL_RATE_MSG_S,
        metrics=(
            "latency_ms_p50_p95_p99",
            "delivery_counts",
            "delivery_rate",
            "cpu_pct_per_container",
            "mem_bytes_per_container",
        ),
        performance_claims_allowed=True,
        notes="Ten nominal runs of ten minutes after two minutes of warm-up (plan 7.1).",
    ),
    Condition(
        id="load_sweep",
        runner="simulator",
        scenario="load-sweep",
        repetitions=10,
        duration_s=300,
        warmup_s=0,
        cooldown_s=120,
        rates_msg_s=(10.0, 50.0, 100.0, 250.0),
        rate_msg_s=None,
        metrics=(
            "latency_ms_p50_p95_p99",
            "delivery_counts",
            "delivery_rate",
            "sustainable_throughput",
            "saturation",
            "cpu_pct_per_container",
            "mem_bytes_per_container",
        ),
        performance_claims_allowed=True,
        notes=(
            "10/50/100/250 msg/s, ten five-minute runs per load, randomized "
            "execution order from the campaign master seed, 120 s cooldown "
            "between runs (plan 7.1)."
        ),
    ),
    Condition(
        id="soak",
        runner="simulator",
        scenario="soak",
        repetitions=1,
        duration_s=86_400,
        warmup_s=0,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=NOMINAL_RATE_MSG_S,
        metrics=(
            "stability_descriptive",
            "latency_ms_p50_p95_p99",
            "delivery_counts",
            "delivery_rate",
            "cpu_pct_per_container",
            "mem_bytes_per_container",
        ),
        performance_claims_allowed=True,
        notes=(
            "One 24 h nominal soak; analyzed descriptively, no confidence "
            "interval of its own (plan 7.1/7.3)."
        ),
    ),
)

CONDITIONS_BY_ID: dict[str, Condition] = {c.id: c for c in CONDITIONS}

# Execution-order index used by the analysis for stable output ordering.
CONDITION_ORDER: dict[str, int] = {c.id: i for i, c in enumerate(CONDITIONS)}
