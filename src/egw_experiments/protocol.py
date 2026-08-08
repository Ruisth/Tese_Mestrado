"""Frozen experimental protocol (plan section 7.1) expressed as data.

This module is the single source of truth for the experimental conditions.
After gate G4 ("protocolo congelado", tag ``exp-v1``) any change here is a
protocol change and requires a new ``PROTOCOL_VERSION`` plus a LOG entry;
metrics, conditions and exclusion criteria must not change after G4.

Conditions (plan 7.1, completed per the 2026-08-08 audit section 9.5 so
claims C10/C11/C12/C14 have a full path through the campaign plan):

- ``qemu_boots``          : 5 QEMU boots, functional consistency only, never
                            a source of performance claims (plan 5.1).
- ``cold_start``          : 10 cold starts of the ARM stack (time to
                            readiness). Claim C04.
- ``twin_creation``       : 10 independent twin creations.
- ``smoke_sequence``      : 10 consecutive smoke runs, all must complete
                            with zero lost messages. Claim C14.
- ``nominal``             : 10 runs x 600 s at the nominal aggregate rate
                            (~11.2 msg/s, plan 7.3) after 120 s warm-up.
                            Claims C06/C07.
- ``load_sweep``          : rates 10/50/100/250 msg/s, 10 runs x 300 s per
                            rate, randomized execution order (derived from
                            the campaign master seed), 120 s cooldown
                            between runs. Claims C08/C09.
- ``invalid_payload``     : 3 runs x 300 s at the nominal aggregate rate
                            with deterministic invalid-event injection.
                            Claim C11.
- ``dropout_reconnect``   : 3 runs x 600 s dropout-reconnect scenario.
                            Claim C10.
- ``controller_restart``  : 3 runs x 600 s nominal with one controller
                            restart mid-run (harness ``--restart-cmd`` /
                            ``--restart-at-s`` hook). Claim C12.
- ``soak``                : 1 x 24 h nominal run, analyzed descriptively
                            only (no confidence interval, plan 7.3).
                            Claim C13.

CPU and RAM are sampled every second in every timed run (plan 7.1), by the
SUT-side collector (``src/deployment/scripts/collect-resources.sh``) whose
output is ingested with ``--resources-from``.
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
# for 60 s.
SATURATION_LOSS_RATE = 0.01
SATURATION_P95_MS = 1000.0
# Legacy per-container docker-stats threshold (single-CPU basis); kept for
# per-container reporting only. The saturation CPU criterion itself is
# host-level: see SATURATION_HOST_CPU_UTILIZATION below.
SATURATION_CPU_PCT = 90.0
SATURATION_CPU_SUSTAIN_S = 60

# Host-level CPU criterion (audit 9.7 / R23): docker-stats cpu_pct is
# expressed relative to a single CPU, so the analysis normalizes it by the
# SUT's nproc (from sut_environment.json):
#   host_cpu_utilization = sum(container cpu_pct) / (100 * nproc)  per sample
# The CPU saturation criterion is host_cpu_utilization > 0.90 sustained for
# at least 60 s within a run; a load saturates on CPU when at least half of
# its runs show such an event (run-fraction rule, unit of analysis = run).
# PENDING ADVISOR SIGN-OFF BEFORE exp-v1: both the host-level normalization
# threshold and the >= 0.5 run-fraction rule must be confirmed with the
# advisor before the protocol freeze (G4); they must not change afterwards.
SATURATION_HOST_CPU_UTILIZATION = 0.90

# Queue-growth criterion (audit 9.7 / R23): the controller exposes
# queue_depth on GET /metrics (CONTRACTS v1.1); the harness samples it at
# 1 Hz into controller_metrics.csv. Persistent queue growth in a run is a
# window of consecutive samples spanning >= 60 s in which queue_depth is
# strictly increasing from sample to sample AND every sample in the window
# is above the floor of 100 messages (the floor suppresses small-queue
# noise). A load saturates on queue growth when at least half of its runs
# show such an event (same run-fraction rule as CPU).
# PENDING ADVISOR SIGN-OFF BEFORE exp-v1: the exact rule (strictly
# increasing, 60 s window, floor 100, run-fraction >= 0.5) must be
# confirmed with the advisor before the protocol freeze (G4).
SATURATION_QUEUE_DEPTH_FLOOR = 100
SATURATION_QUEUE_GROWTH_SUSTAIN_S = 60

# Sampling-cadence cap for sustained-window computations (work order P1b).
# Resources and controller metrics are sampled at 1 Hz (plan 7.1); a gap
# larger than MAX_SAMPLE_GAP_S between consecutive samples BREAKS any
# sustained window (CPU > 90% for 60 s, persistent queue growth over 60 s):
# continuity above a threshold cannot be claimed across an unobserved
# interval, so two samples minutes apart can never fake a sustained minute.
# The same cap bounds how far a single sample extends when computing
# sampling coverage of the measured window (per_run.csv
# resources_coverage_pct / metrics_coverage_pct).
# PENDING ADVISOR SIGN-OFF BEFORE exp-v1: the 5 s cap (5x the nominal 1 s
# cadence) must be confirmed with the advisor before the protocol freeze
# (G4); it must not change afterwards.
MAX_SAMPLE_GAP_S = 5.0

# Saturation evidence sufficiency (work order P1b): a load's saturation
# verdict is decided ONLY when the planned number of valid runs exists AND
# every run carries the required instrumentation, including SUT resources
# covering at least this percentage of the measured window; otherwise the
# verdict is 'insufficient-evidence', never 'not-saturated'.
# PENDING ADVISOR SIGN-OFF BEFORE exp-v1: the 90% minimum coverage must be
# confirmed with the advisor before the protocol freeze (G4).
SATURATION_MIN_RESOURCE_COVERAGE_PCT = 90.0

# Soak Definition of Done (claim C13, work order P1b). The single 24 h soak
# run is accepted only when ALL of the following hold (evaluated in
# acceptance_by_condition.csv, completeness-gated):
# - the measured window spans at least SOAK_MIN_WINDOW_S seconds;
# - resources.csv AND controller_metrics.csv each cover at least
#   SOAK_MIN_COVERAGE_PCT of the measured window with no sampling gap
#   longer than SOAK_MAX_SAMPLING_GAP_S;
# - no unrecovered interruption: no controller-metrics gap longer than
#   SOAK_MAX_INTERRUPTION_GAP_S and the last controller-metrics sample
#   within SOAK_MAX_INTERRUPTION_GAP_S of the window end;
# - events.jsonl delivery reported per plan 7.3 (descriptive, no CI).
# PENDING ADVISOR SIGN-OFF BEFORE exp-v1: the 24 h / 99% / 60 s / 120 s
# thresholds must be confirmed with the advisor before the protocol freeze
# (G4); they must not change afterwards.
SOAK_MIN_WINDOW_S = 86_400
SOAK_MIN_COVERAGE_PCT = 99.0
SOAK_MAX_SAMPLING_GAP_S = 60.0
SOAK_MAX_INTERRUPTION_GAP_S = 120.0

# Controller-metrics reconciliation (work order P1b): for conditions where
# GET /metrics sampling is mandated instrumentation (dropout_reconnect,
# load_sweep, soak) the accepted-counter delta over the measured window
# must match the events.jsonl accepted count within max(ABS, FRAC * count).
# The tolerance absorbs window-edge effects (the sampler starts/stops on
# the harness clock while confirmations land on the controller clock).
# PENDING ADVISOR SIGN-OFF BEFORE exp-v1: the +-1% (floor 1 message)
# tolerance must be confirmed with the advisor before the protocol freeze
# (G4).
METRICS_RECONCILIATION_TOLERANCE_FRAC = 0.01
METRICS_RECONCILIATION_TOLERANCE_ABS = 1.0


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
        id="smoke_sequence",
        runner="simulator",
        scenario="smoke",
        repetitions=10,
        duration_s=30,
        warmup_s=0,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=NOMINAL_RATE_MSG_S,
        metrics=("delivery_counts", "delivery_rate"),
        performance_claims_allowed=False,
        notes=(
            "Ten consecutive smoke runs in the campaign environment (claim "
            "C14): every run must complete (simulator exit 0) with zero "
            "lost valid messages. Functional acceptance only; no "
            "performance inference."
        ),
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
        id="invalid_payload",
        runner="simulator",
        scenario="invalid-payload",
        repetitions=3,
        duration_s=300,
        warmup_s=0,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=NOMINAL_RATE_MSG_S,
        metrics=(
            "delivery_counts",
            "delivery_rate",
            "intended_invalid_rejected",
            "intended_invalid_accepted",
        ),
        performance_claims_allowed=True,
        notes=(
            "Three 300 s runs at the nominal aggregate rate with the "
            "simulator's deterministic invalid-event injection (claim C11): "
            "every intended_invalid event must be rejected by JSON Schema "
            "validation, zero intended_invalid events may be accepted, and "
            "valid messages follow the plan 7.3 delivery accounting."
        ),
    ),
    Condition(
        id="dropout_reconnect",
        runner="simulator",
        scenario="dropout-reconnect",
        repetitions=3,
        duration_s=600,
        warmup_s=0,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=NOMINAL_RATE_MSG_S,
        metrics=(
            "delivery_counts",
            "delivery_rate",
            "reconnect_recovery",
        ),
        performance_claims_allowed=True,
        notes=(
            "Three 600 s dropout-reconnect runs (claim C10). Delivery "
            "accounting tolerates late buffered redelivery inside the 60 s "
            "confirmation window (QoS 1 requeues after reconnect); "
            "sent_events puback_monotonic_ns is null for publishes whose "
            "PUBACK was not observed and never enters the primary metrics."
        ),
    ),
    Condition(
        id="controller_restart",
        runner="simulator",
        scenario="nominal",
        repetitions=3,
        duration_s=600,
        warmup_s=0,
        cooldown_s=0,
        rates_msg_s=None,
        rate_msg_s=NOMINAL_RATE_MSG_S,
        metrics=(
            "delivery_counts",
            "delivery_rate",
            "restart_recovery",
            "duplicate_suppression",
        ),
        performance_claims_allowed=True,
        notes=(
            "Three 600 s nominal runs with one controller restart mid-run "
            "(claim C12), executed by the harness --restart-cmd hook at "
            "--restart-at-s and recorded in the manifest with timestamps. "
            "Acceptance: delivery across the restart and zero "
            "double-accepted message_ids (dedupe state survives via the "
            "twin ingestion feature, CONTRACTS 4)."
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

# Timed conditions (audit 9.1/9.2): every simulator-driven run is a timed
# run. Timed runs REQUIRE sut_environment.json and SUT-side resources in the
# run directory; otherwise the run manifest is marked validity 'invalid'
# (overridable only by the explicit --allow-missing-* flags, which record
# the decision in the manifest). External conditions (qemu_boots,
# cold_start, twin_creation) are operator-measured and exempt.
TIMED_CONDITION_IDS: frozenset[str] = frozenset(
    c.id for c in CONDITIONS if c.runner == "simulator"
)

# Condition -> claim mapping (docs/claim_evidence_matrix.csv). twin_creation
# is a plan 7.1 condition without a dedicated claim id of its own.
CONDITION_CLAIMS: dict[str, tuple[str, ...]] = {
    "qemu_boots": ("C02",),
    "cold_start": ("C04",),
    "twin_creation": (),
    "smoke_sequence": ("C14",),
    "nominal": ("C06", "C07"),
    "load_sweep": ("C08", "C09"),
    "invalid_payload": ("C11",),
    "dropout_reconnect": ("C10",),
    "controller_restart": ("C12",),
    "soak": ("C13",),
}
