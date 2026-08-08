"""Single reproducible analysis entrypoint (plan 5.8, 7.2, 7.3, 9.1).

``analyze(base_dir)`` regenerates EVERYTHING under ``results/processed/`` and
``results/figures/`` from ``results/raw/`` alone ("processados e figuras sao
sempre regenerados por um unico script", plan 5.8). It never modifies
``results/raw/``. Since the 2026-08-08 audit (section 9.6, claim C15) this
includes the EXTERNAL conditions (QEMU boots, cold starts, twin creations)
ingested by ``run --external-timings``: no run type needs a second analysis
tool.

Metric definitions (plan 7.3 / CONTRACTS 9, applied verbatim)
-------------------------------------------------------------

- ``sent``      : valid message handed to the MQTT publish, i.e. a line of the
                  simulator's ``sent_events.jsonl`` with ``intended_invalid``
                  false. Intentionally invalid payloads are excluded from the
                  delivery-rate denominator.
- ``delivered`` : unique Ditto confirmations, i.e. distinct ``message_id``
                  values with an ``accepted`` controller event whose
                  ``ditto_ack_monotonic_ns`` falls within the confirmation
                  window. The window deadline lives in the CONTROLLER's
                  clock domain: max ``received_monotonic_ns`` over the run's
                  controller events plus ``confirmation_window_s`` from the
                  run manifest (default 60 s). The manifest's
                  ``confirmation_deadline_monotonic_ns`` was captured on the
                  harness host, which runs OFF the ARM VM (plan 5.1), and
                  monotonic clocks are not comparable across hosts; it is
                  informational only (clock_domain ``harness-host``) and is
                  used as a last-resort fallback only when the run has zero
                  controller events. A plausibility check flags manifest
                  deadlines outside [max(received), max(received) +
                  2*window] with a loud warning. Repeated confirmations of
                  the same ``message_id`` count once; every repeat past the
                  first is counted in ``double_accepted`` (a repeat means the
                  twin was patched more than once for the same message — the
                  defect the ``controller_restart`` acceptance rules out).
- ``lost``      : valid sent message without a unique confirmation within the
                  window. Late confirmations (past the deadline) do not
                  rescue a message: it is counted lost and the late
                  confirmation is reported separately.
- ``duplicate`` / ``rejected`` / ``failed`` are counted separately from the
  controller's ``outcome`` field and never enter the delivery rate.
- Intentionally invalid events that were correctly rejected are successes of
  validation: they are excluded from the denominator and are never losses.
  An intentionally invalid event that was *accepted* is a validation defect
  and is reported in its own column (``intended_invalid_accepted``).
- Delivery rate = ``delivered`` / ``sent`` (unique confirmations / valid
  sent). Loss rate = ``lost`` / ``sent``.
- Primary latency = the controller's ``latency_ms``
  (``(ditto_ack_monotonic_ns - received_monotonic_ns)/1e6``, same process);
  per-run statistics are p50/p95/p99 plus mean over the unique in-window
  confirmations of valid sent messages.

Dropout-reconnect accounting (claim C10, documented assumptions)
----------------------------------------------------------------

The simulator's ``dropout-reconnect`` scenario performs a REAL client
disconnect with device-side buffering; buffered events are flushed after
reconnect with a zero PUBACK wait budget, so their ``sent_events.jsonl``
records carry ``puback_monotonic_ns: null``. The delivery accounting above
is already tolerant of that late buffered redelivery: a buffered message
counts as delivered as long as its unique Ditto confirmation lands within
the confirmation window (controller clock domain), and
``puback_monotonic_ns`` never enters any primary metric (CONTRACTS 7).
Assumptions: (1) disconnect windows are short relative to the run so
flushed messages can still be confirmed in-window; (2) QoS 1 redelivery
after reconnect may produce broker-level duplicates, which the controller
counts as ``duplicate`` — they never inflate ``delivered`` (unique
``message_id`` set) and are not acceptance failures; a failure is a
``double_accepted`` message (twin patched twice).

Measured window (audit 9.4)
---------------------------

Timed-run manifests record ``measured_window_utc`` {start, end}: harness
wall-clock stamps around the measured simulator invocation (NTP-sync
assumption between the harness host and the VM — acceptable for windowing
1 Hz samples, NEVER used for latency). Before aggregating, the analysis
filters ``resources.csv`` AND ``controller_metrics.csv`` rows to this
window, so warm-up and cooldown samples cannot contaminate the measured
aggregates (the warm-up alone would otherwise add 120 s of load to every
nominal run's CPU/RAM). ``events.jsonl`` needs no such filtering: the
warm-up publishes under ``run_id`` ``<run_id>.warmup``, so the measured
run's event log contains only measured-run events. Runs without a
``measured_window_utc`` (older manifests, dev fixtures) are aggregated
unfiltered and flagged with a warning.

Statistics (plan 7.3)
---------------------

- The unit of analysis is the run, never the message. Cross-run summaries
  aggregate one value per run.
- Reported per condition (and per load for the sweep): n, mean, stdev, 95%
  confidence interval, median, p25/p75, min, max.
- The 95% CI uses the Student t-distribution. Documented choice: a small
  hardcoded table of two-sided 95% critical values for df 1..30 (standard
  mathematical constants); for df > 30 the df=30 value (2.042) is used,
  which is conservative (slightly wider intervals). scipy is deliberately
  not used; the core analysis is standard-library only.
- Percentiles use linear interpolation between closest ranks on the sorted
  sample (rank = (n-1)*p/100), the same convention as numpy's default.
- The soak run is analyzed descriptively only: it appears in
  ``per_run.csv`` and in ``summary_by_condition.csv`` without CI columns
  (plan 7.3: no confidence interval of its own).

External conditions (audit 9.6, claim C15)
------------------------------------------

Raw run directories containing ``timings.json`` (ingested by
``run --external-timings``) are analyzed here too:

- ``cold_start`` and ``twin_creation``: descriptive statistics plus
  mean/stdev/CI95 of the per-run duration (per-run value = mean of that
  run's ``duration_s`` samples; normally one sample per run; unit of
  analysis = run) go into ``summary_by_condition.csv`` as metric
  ``duration_s``.
- ``qemu_boots``: strictly a functional pass/fail listing in
  ``external_runs.csv`` — NO performance statistics are computed, per plan
  5.1 (QEMU results never support performance conclusions). Each sample's
  ``outcome`` field ("pass"/"fail") is listed as provided by the operator;
  samples without it are listed as ``unspecified``, never inferred.

CPU semantics (audit 9.7)
-------------------------

``docker stats`` ``CPUPerc`` is expressed relative to a SINGLE CPU (a busy
4-thread container can read 400%). Per-container values are reported raw in
``resources_by_run.csv``. For host-level saturation the analysis normalizes
by the SUT's CPU count (``nproc`` from ``sut_environment.json``, captured ON
the VM):

    host_cpu_utilization = sum(container cpu_pct) / (100 * nproc)   per sample

Saturation (plan 7.3, completed per audit 9.7)
----------------------------------------------

Operational saturation is the first (lowest) load of the sweep at which at
least one criterion holds:

- loss criterion: across-run mean loss rate > 1%;
- latency criterion: across-run mean p95 > 1 s;
- CPU criterion (host-level): host_cpu_utilization > 0.90 sustained for at
  least 60 s within a run; the criterion holds at a load when at least half
  of the runs at that load show such an event (run-fraction rule, unit of
  analysis = run). The legacy per-container ``cpu_pct > 90`` sustained span
  is still reported per run/container but is NOT a saturation criterion.
- queue-growth criterion: the controller's ``queue_depth`` (GET /metrics,
  CONTRACTS v1.1, sampled at 1 Hz into ``controller_metrics.csv``) shows
  persistent growth within a run: a window of consecutive samples spanning
  >= 60 s in which queue_depth is strictly increasing sample-to-sample AND
  every sample is above the floor of 100 messages (the floor suppresses
  small-queue noise). Same >= 0.5 run-fraction rule.

PENDING ADVISOR SIGN-OFF BEFORE exp-v1 (audit R23): the host-CPU
normalization threshold (0.90/60 s), the exact queue-growth rule
(strictly increasing, 60 s, floor 100) and the >= 0.5 run-fraction rule
must be confirmed with the advisor before the protocol freeze (G4); they
must not change afterwards. ``saturation.json`` echoes this notice.

Sampling cadence and coverage (work order P1b)
----------------------------------------------

Both sustained-window detectors (host CPU > 0.90 for 60 s; persistent
queue growth over 60 s) BREAK the streak whenever the distance between
consecutive samples exceeds ``MAX_SAMPLE_GAP_S`` (protocol.py, default
5 s, pending advisor sign-off): continuity above a threshold cannot be
claimed across an unobserved interval, so two samples minutes apart can
never fake a sustained minute. Every run additionally gets sampling
coverage of the measured window in ``per_run.csv``
(``resources_coverage_pct`` / ``metrics_coverage_pct``): each sample
covers from its timestamp until the next sample or for MAX_SAMPLE_GAP_S,
whichever is shorter (the last sample covers up to the window end, same
cap); time before the first sample is uncovered.

Saturation evidence sufficiency (work order P1b): a load's verdict is
decided ONLY when the planned number of valid runs exists at that load
AND every run carries the required instrumentation (host-CPU criterion
evaluable, resources coverage >= SATURATION_MIN_RESOURCE_COVERAGE_PCT,
controller metrics present for the queue-growth criterion). Otherwise the
load's ``verdict`` in ``saturation.json`` is ``"insufficient-evidence"``
(with per-run detail) — never ``"not-saturated"``. The threshold-crossing
logic itself is unchanged (stop-condition rule: no material change to the
statistical criteria beyond completeness).

Per-condition acceptance (audit 9.5, claims C10-C14; work order P1b)
--------------------------------------------------------------------

``acceptance_by_condition.csv`` evaluates acceptance for EVERY planned
simulator condition of the frozen protocol (iterating over protocol.py
CONDITIONS, not only over conditions found in raw/), over the INCLUDED
(valid, non-excluded) runs:

- Completeness gate: every condition gets an explicit ``runs_complete``
  row (n_valid == planned repetitions; for load_sweep, repetitions x
  number of swept rates). Every substantive criterion is gated on it:
  ``passed`` is False when n_valid == 0 or n_valid != expected (the
  detail shows 'n_valid/expected valid runs'); the substantive check
  applies only on top of completeness. A planned condition with zero
  runs therefore yields FAILED rows, never blanks.
- ``smoke_sequence`` (C14): zero lost valid messages across all runs.
- ``invalid_payload`` (C11): every ``intended_invalid`` event rejected;
  zero ``intended_invalid`` accepted; the valid-message delivery rate is
  reported informationally under the plan 7.3 accounting (invalid events
  never enter the denominator).
- ``dropout_reconnect`` (C10): zero lost valid messages (the accounting is
  tolerant of late buffered redelivery within the confirmation window, see
  above); zero double-accepted message_ids; every run's SIMULATOR manifest
  (logs/simulator/) must report totals ``dropout_disconnects >= 1`` AND
  ``buffered_dropout >= 1`` — a "dropout" run in which no disconnect
  actually happened must not pass as C10 evidence.
- ``controller_restart`` (C12): every run's manifest must carry the
  restart-hook record with executed timestamps and exit code 0 (no error);
  delivery across the restart (zero lost valid messages within the
  window); zero double-accepted message_ids (dedupe state survives the
  restart via the twin ingestion feature, CONTRACTS 4).
- ``soak`` (C13) Definition of Done (thresholds in protocol.py, pending
  advisor sign-off): measured window >= 24 h; resources.csv AND
  controller_metrics.csv each cover >= 99% of the measured window with no
  sampling gap > 60 s; no unrecovered interruption (no controller-metrics
  gap > 120 s and last sample within 120 s of the window end); delivery
  reported descriptively per plan 7.3 (no CI, as before).
- Controller-metrics reconciliation (dropout_reconnect, load_sweep, soak —
  mandated instrumentation): per run, the accepted-counter delta over the
  measured window must match the events.jsonl accepted count within
  max(METRICS_RECONCILIATION_TOLERANCE_ABS, _FRAC * count); a run without
  controller metrics FAILS this criterion (detail 'controller metrics
  missing'), it is never blank.

Exclusions and validity (plan 7.3; work order P1)
-------------------------------------------------

A run is excluded only for a proven cloud/instrumentation/configuration
failure, with the cause documented in the run manifest's ``exclusion``
field. Excluded runs still appear in ``per_run.csv`` (flagged) but are
removed from summaries, saturation, acceptance and figures. A slow run is
never excluded for its result alone.

Validity gate (work order P1 fix 1): the same removal applies to any run
whose manifest ``validity`` is present and not ``'valid'`` — invalid runs
must never contaminate summaries, saturation, acceptance or figures. A
manifest WITHOUT a validity key (legacy fixtures/raw runs) is treated as
valid; a present non-'valid' value always excludes. Every run stays listed
in ``per_run.csv`` with its validity flag, its ``resource_source`` and a
warning listing any recorded protocol ``deviations``.

Outputs
-------

- ``processed/per_run.csv``              one row per raw message run;
- ``processed/resources_by_run.csv``     per-run, per-container resource
                                         aggregates (measured window only);
- ``processed/summary_by_condition.csv`` cross-run statistics, long format,
                                         including external cold_start /
                                         twin_creation durations;
- ``processed/external_runs.csv``        per-sample listing of external
                                         runs (incl. qemu boot pass/fail);
- ``processed/acceptance_by_condition.csv`` acceptance evaluation above;
- ``processed/saturation.json``          saturation evaluation per load;
- ``figures/*.png``                      only when matplotlib is importable
                                         (optional dependency); otherwise a
                                         clear notice is printed and the
                                         exit code stays 0.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .environment import read_sut_environment, sut_nproc
from .protocol import (
    CONDITION_CLAIMS,
    CONDITION_ORDER,
    CONDITIONS,
    CONDITIONS_BY_ID,
    CONFIRMATION_WINDOW_S,
    MAX_SAMPLE_GAP_S,
    METRICS_RECONCILIATION_TOLERANCE_ABS,
    METRICS_RECONCILIATION_TOLERANCE_FRAC,
    PROTOCOL_VERSION,
    SATURATION_CPU_PCT,
    SATURATION_CPU_SUSTAIN_S,
    SATURATION_HOST_CPU_UTILIZATION,
    SATURATION_LOSS_RATE,
    SATURATION_MIN_RESOURCE_COVERAGE_PCT,
    SATURATION_P95_MS,
    SATURATION_QUEUE_DEPTH_FLOOR,
    SATURATION_QUEUE_GROWTH_SUSTAIN_S,
    SOAK_MAX_INTERRUPTION_GAP_S,
    SOAK_MAX_SAMPLING_GAP_S,
    SOAK_MIN_COVERAGE_PCT,
    SOAK_MIN_WINDOW_S,
)
from .run import DEFAULT_RESULTS_BASE

# ---------------------------------------------------------------------------
# Statistics helpers (stdlib only; documented in the module docstring)
# ---------------------------------------------------------------------------

#: Two-sided 95% critical values of the Student t-distribution for df 1..30.
#: Standard mathematical constants (identical to any printed t-table).
T_TABLE_95: dict[int, float] = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def t_critical_95(df: int) -> float:
    """Two-sided 95% t critical value; df > 30 uses the conservative df=30
    value (see module docstring for the documented choice)."""
    if df < 1:
        raise ValueError("degrees of freedom must be >= 1")
    return T_TABLE_95.get(df, T_TABLE_95[30])


def percentile(values: list[float], p: float) -> float | None:
    """Percentile with linear interpolation between closest ranks.

    rank = (n-1) * p/100 on the sorted sample (numpy's default convention).
    Returns None for an empty sample.
    """
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    rank = (len(s) - 1) * (p / 100.0)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(s[lo])
    return float(s[lo] + (s[hi] - s[lo]) * (rank - lo))


def ci95(values: list[float]) -> tuple[float | None, float | None, float | None]:
    """(mean, stdev, ci95_half_width) across runs.

    Sample stdev (n-1 denominator); half-width = t_{0.975,n-1} * stdev/sqrt(n).
    With n < 2 the stdev and CI are undefined and returned as None.
    """
    n = len(values)
    if n == 0:
        return None, None, None
    mean = statistics.fmean(values)
    if n < 2:
        return mean, None, None
    stdev = statistics.stdev(values)
    half = t_critical_95(n - 1) * stdev / math.sqrt(n)
    return mean, stdev, half


# ---------------------------------------------------------------------------
# Raw-file readers
# ---------------------------------------------------------------------------

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    return records


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def read_resources_csv(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Read resources.csv into ``{container: [sample, ...]}`` sorted by time.

    Each sample: ``{ts, cpu_pct, mem_bytes, mem_pct}`` (ts is a datetime;
    unparseable fields become None). The current CSV schema
    (``ts_utc,container,cpu_pct,mem_bytes,mem_pct,host``, work order P1) is
    shared by the local dev sampler (resources.py) and the SUT-side
    collector (``deployment/scripts/collect-resources.sh``).

    Header tolerance (documented, work order P1 fix 3): this READER accepts
    BOTH the new 6-column header and the legacy 5-column one WITHOUT
    ``host`` — old fixtures and pre-P1 raw runs must stay analyzable, and
    the ``host`` provenance column does not enter any aggregate. RUN-TIME
    ingestion is the strict side: ``run/collect --resources-from`` accepts
    only the new header (``egw_experiments.resources.validate_resources_csv``).
    """
    by_container: dict[str, list[dict[str, Any]]] = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            container = (row.get("container") or "").strip()
            if not container:
                continue

            def _num(key: str, cast: Any) -> Any:
                raw = (row.get(key) or "").strip()
                if not raw:
                    return None
                try:
                    return cast(float(raw)) if cast is int else cast(raw)
                except ValueError:
                    return None

            by_container.setdefault(container, []).append(
                {
                    "ts": _parse_ts(row.get("ts_utc") or ""),
                    "cpu_pct": _num("cpu_pct", float),
                    "mem_bytes": _num("mem_bytes", int),
                    "mem_pct": _num("mem_pct", float),
                }
            )
    for samples in by_container.values():
        # Unparseable timestamps sort first without ever comparing None.
        samples.sort(key=lambda s: s["ts"] or _EPOCH)
    return by_container


def read_controller_metrics_csv(path: Path) -> list[dict[str, Any]]:
    """Read controller_metrics.csv (1 Hz GET /metrics samples) sorted by time.

    Each sample: ``{ts, accepted, rejected, duplicate, failed, dropped,
    queue_depth}`` — numbers or None. Schema written by
    ``egw_experiments.controller_metrics.ControllerMetricsSampler``.
    """
    samples: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sample: dict[str, Any] = {"ts": _parse_ts(row.get("ts_utc") or "")}
            for key in ("accepted", "rejected", "duplicate", "failed", "dropped", "queue_depth"):
                raw = (row.get(key) or "").strip()
                try:
                    sample[key] = float(raw) if raw else None
                except ValueError:
                    sample[key] = None
            samples.append(sample)
    samples.sort(key=lambda s: s["ts"] or _EPOCH)
    return samples


# ---------------------------------------------------------------------------
# Measured window (audit 9.4)
# ---------------------------------------------------------------------------


def measured_window(manifest: dict[str, Any]) -> tuple[datetime, datetime] | None:
    """Parse the manifest's ``measured_window_utc`` into (start, end).

    Returns None when the manifest has no usable window (older manifests);
    the caller then aggregates unfiltered and warns.
    """
    win = manifest.get("measured_window_utc")
    if not isinstance(win, dict):
        return None
    start = _parse_ts(win.get("start") or "")
    end = _parse_ts(win.get("end") or "")
    if start is None or end is None or end < start:
        return None
    return start, end


def filter_samples_to_window(
    samples: list[dict[str, Any]], window: tuple[datetime, datetime] | None
) -> list[dict[str, Any]]:
    """Keep only samples whose ``ts`` lies inside [start, end] (inclusive).

    With ``window`` None the list is returned unchanged (no filtering
    possible). Samples with an unparseable ``ts`` are dropped when a window
    is active: they cannot be placed inside or outside it.
    """
    if window is None:
        return samples
    start, end = window
    return [
        s for s in samples if s.get("ts") is not None and start <= s["ts"] <= end
    ]


# ---------------------------------------------------------------------------
# Sustained-condition helpers (1 Hz series)
# ---------------------------------------------------------------------------


def _sustained_seconds(
    points: list[dict[str, Any]],
    key: str,
    threshold: float,
    max_gap_s: float = MAX_SAMPLE_GAP_S,
) -> float:
    """Longest span (seconds) of consecutive samples with ``key`` > threshold.

    The span is the timestamp distance from the first to the last sample of
    the streak, so with 1 Hz sampling, 61 consecutive samples above the
    threshold yield 60 s.

    Cadence cap (work order P1b): a gap between consecutive samples larger
    than ``max_gap_s`` (protocol.py MAX_SAMPLE_GAP_S, default 5 s, pending
    advisor sign-off before exp-v1) BREAKS the streak — continuity above
    the threshold cannot be claimed across an unobserved interval, so two
    samples minutes apart can never fake a sustained window.
    """
    best = 0.0
    streak_start: datetime | None = None
    prev_ts: datetime | None = None
    for point in points:
        value = point.get(key)
        ts = point.get("ts")
        if value is not None and ts is not None and value > threshold:
            if (
                prev_ts is not None
                and (ts - prev_ts).total_seconds() > max_gap_s
            ):
                # Cadence gap: the streak restarts at this sample.
                streak_start = ts
            if streak_start is None:
                streak_start = ts
            best = max(best, (ts - streak_start).total_seconds())
            prev_ts = ts
        else:
            streak_start = None
            prev_ts = None
    return best


def sustained_cpu_seconds(
    samples: list[dict[str, Any]], threshold_pct: float = SATURATION_CPU_PCT
) -> float:
    """Longest span (seconds) of consecutive samples with cpu_pct > threshold.

    Per-container, raw docker-stats basis (single CPU). Reported per run and
    container; NOT a saturation criterion (see host_cpu_sustained_seconds).
    """
    return _sustained_seconds(samples, "cpu_pct", threshold_pct)


def host_cpu_series(
    by_container: dict[str, list[dict[str, Any]]], nproc: int
) -> list[dict[str, Any]]:
    """Host-level utilization series from per-container docker-stats samples.

    Per sample timestamp: ``host_cpu_utilization = sum(container cpu_pct) /
    (100 * nproc)`` (audit 9.7). Docker-stats cpu_pct is single-CPU based,
    so the sum over containers divided by 100*nproc is the fraction of the
    whole SUT the stack is using (1.0 = all CPUs busy). Samples missing ts
    or cpu_pct are skipped.
    """
    totals: dict[datetime, float] = {}
    for samples in by_container.values():
        for s in samples:
            ts = s.get("ts")
            cpu = s.get("cpu_pct")
            if ts is None or cpu is None:
                continue
            totals[ts] = totals.get(ts, 0.0) + float(cpu)
    return [
        {"ts": ts, "host_cpu_utilization": total / (100.0 * nproc)}
        for ts, total in sorted(totals.items())
    ]


def host_cpu_sustained_seconds(
    host_series: list[dict[str, Any]],
    threshold: float = SATURATION_HOST_CPU_UTILIZATION,
) -> float:
    """Longest span (s) with host_cpu_utilization > threshold (default 0.90).

    PENDING ADVISOR SIGN-OFF BEFORE exp-v1 (audit R23): threshold and 60 s
    sustain window must be confirmed before the G4 protocol freeze.
    """
    return _sustained_seconds(host_series, "host_cpu_utilization", threshold)


def queue_growth_sustained_seconds(
    samples: list[dict[str, Any]],
    floor: float = SATURATION_QUEUE_DEPTH_FLOOR,
    max_gap_s: float = MAX_SAMPLE_GAP_S,
) -> float:
    """Longest span (seconds) of persistent queue growth (audit 9.7).

    Documented rule — PENDING ADVISOR SIGN-OFF BEFORE exp-v1 (audit R23):
    persistent growth is a window of consecutive 1 Hz samples in which
    ``queue_depth`` is strictly increasing from sample to sample AND every
    sample in the window (including the first) is above ``floor`` (default
    100 messages; the floor suppresses small-queue noise). The span is the
    timestamp distance from the first to the last sample of the window;
    >= 60 s of span marks the run as showing persistent queue growth.

    Cadence cap (work order P1b): a gap between consecutive samples larger
    than ``max_gap_s`` (protocol.py MAX_SAMPLE_GAP_S, default 5 s, pending
    advisor sign-off before exp-v1) BREAKS the window — growth cannot be
    claimed continuous across an unobserved interval.
    """
    best = 0.0
    streak_start: datetime | None = None
    prev_ts: datetime | None = None
    prev_depth: float | None = None
    for sample in samples:
        depth = sample.get("queue_depth")
        ts = sample.get("ts")
        if depth is None or ts is None or depth <= floor:
            streak_start = None
            prev_ts = None
            prev_depth = None
            continue
        if prev_ts is not None and (ts - prev_ts).total_seconds() > max_gap_s:
            # Cadence gap: continuity restarts at this sample.
            streak_start = None
            prev_ts = ts
            prev_depth = depth
            continue
        if prev_depth is not None and depth > prev_depth:
            if streak_start is None:
                streak_start = prev_ts
            best = max(best, (ts - streak_start).total_seconds())
        else:
            streak_start = None
        prev_ts = ts
        prev_depth = depth
    return best


def sampling_stats(
    timestamps: list[datetime],
    window: tuple[datetime, datetime] | None,
    max_gap_s: float = MAX_SAMPLE_GAP_S,
) -> dict[str, float | None]:
    """Coverage and gap statistics of a sample series over the measured window.

    Returns ``{"coverage_pct", "max_gap_s", "tail_gap_s"}``:

    - ``coverage_pct``: percentage of the window covered, where each sample
      covers from its timestamp until the next sample or for ``max_gap_s``
      seconds, whichever is shorter (the last sample covers up to the
      window end, same cap). Time before the first sample is uncovered.
      With nominal 1 Hz sampling and no holes this is 100%.
    - ``max_gap_s``: largest distance between consecutive in-window samples
      (interior gaps only; head/tail truncation is captured by
      ``coverage_pct`` and ``tail_gap_s``). 0.0 for a single sample.
    - ``tail_gap_s``: window end minus the last in-window sample.

    All three are None when ``window`` is None (no measured_window_utc) or
    has zero span. An empty in-window series yields coverage 0.0 with gap
    fields None.
    """
    none_stats: dict[str, float | None] = {
        "coverage_pct": None, "max_gap_s": None, "tail_gap_s": None
    }
    if window is None:
        return none_stats
    start, end = window
    span = (end - start).total_seconds()
    if span <= 0:
        return none_stats
    ts = sorted({t for t in timestamps if t is not None and start <= t <= end})
    if not ts:
        return {"coverage_pct": 0.0, "max_gap_s": None, "tail_gap_s": None}
    covered = 0.0
    interior_max = 0.0
    for i, t in enumerate(ts):
        nxt = ts[i + 1] if i + 1 < len(ts) else end
        gap = (nxt - t).total_seconds()
        covered += min(gap, max_gap_s)
        if i + 1 < len(ts):
            interior_max = max(interior_max, gap)
    return {
        "coverage_pct": min(100.0, 100.0 * covered / span),
        "max_gap_s": interior_max,
        "tail_gap_s": max(0.0, (end - ts[-1]).total_seconds()),
    }


# ---------------------------------------------------------------------------
# Per-run metrics
# ---------------------------------------------------------------------------

PER_RUN_COLUMNS = [
    "run_id",
    "condition_id",
    "scenario",
    "rate_msg_s",
    "duration_s",
    "seed",
    "repetition",
    "validity",
    "excluded",
    "exclusion_reason",
    "resource_source",
    "sent_total",
    "sent_valid",
    "intended_invalid_sent",
    "delivered_unique",
    "lost",
    "delivery_rate",
    "loss_rate",
    "duplicates",
    "double_accepted",
    "rejected_valid",
    "rejected_intended_invalid",
    "rejected_unmatched",
    "failed",
    "late_confirmations",
    "intended_invalid_accepted",
    "confirmed_unmatched",
    "latency_count",
    "latency_ms_mean",
    "latency_ms_p50",
    "latency_ms_p95",
    "latency_ms_p99",
    "latency_ms_min",
    "latency_ms_max",
    "resource_samples",
    "cpu_pct_max",
    "cpu_sustained_gt90_s",
    "mem_bytes_max",
    "nproc",
    "host_cpu_utilization_max",
    "host_cpu_sustained_gt090_s",
    "controller_metric_samples",
    "queue_depth_max",
    "queue_growth_sustained_s",
    "measured_window_s",
    "resources_coverage_pct",
    "resources_max_gap_s",
    "metrics_coverage_pct",
    "metrics_max_gap_s",
    "metrics_tail_gap_s",
    "events_accepted_total",
    "metrics_accepted_delta",
    "dropout_disconnects",
    "buffered_dropout",
    "restart_hook_ok",
    "warnings",
]

RESOURCES_BY_RUN_COLUMNS = [
    "run_id",
    "container",
    "samples",
    "cpu_pct_mean",
    "cpu_pct_max",
    "mem_bytes_mean",
    "mem_bytes_max",
    "cpu_sustained_gt90_s",
]


def read_simulator_manifest(
    run_dir: Path, run_id: str
) -> dict[str, Any] | None:
    """Read the SIMULATOR's own manifest.json from the run directory.

    The harness keeps the simulator outputs under ``logs/simulator/`` (see
    egw_experiments.run); the simulator itself writes its manifest under
    ``<output>/<run_id>/manifest.json`` (egw_simulator.runner). Both
    layouts are probed, plus any single-level subdirectory, so pre-P1b raw
    runs stay readable. Returns None when no readable simulator manifest
    exists. Used by the C10 acceptance to verify the dropout scenario
    really disconnected (totals ``dropout_disconnects``/``buffered_dropout``).
    """
    sim_dir = run_dir / "logs" / "simulator"
    candidates = [
        sim_dir / run_id / "manifest.json",
        sim_dir / "manifest.json",
    ]
    if sim_dir.is_dir():
        candidates.extend(
            sorted(
                child / "manifest.json"
                for child in sim_dir.iterdir()
                if child.is_dir()
            )
        )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(obj, dict):
            return obj
    return None


def compute_run_metrics(run_dir: str | Path) -> dict[str, Any] | None:
    """Compute the per-run metrics row for one ``results/raw/<run_id>/`` dir.

    Returns None (with a notice on stderr) when the directory has no
    ``sent_events.jsonl``: external conditions (cold starts, twin creations,
    QEMU boots) are not message runs — ``analyze()`` handles their
    ``timings.json`` separately (audit 9.6).

    The returned dict has the PER_RUN_COLUMNS keys plus ``"_resources"``:
    the rows destined for ``resources_by_run.csv``.
    """
    run_dir = Path(run_dir)
    warnings: list[str] = []

    manifest: dict[str, Any] = {}
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"unreadable manifest.json: {exc}")
    else:
        warnings.append("manifest.json missing")

    sent_path = run_dir / "sent_events.jsonl"
    if not sent_path.is_file():
        print(
            f"[analyze] notice: {run_dir.name} has no sent_events.jsonl; "
            "skipped as a message run (external condition or incomplete run)",
            file=sys.stderr,
        )
        return None

    run_id = manifest.get("run_id") or run_dir.name

    # --- sent side (simulator, CONTRACTS 7) -------------------------------
    sent_records = _read_jsonl(sent_path)
    valid_ids: set[str] = set()
    intended_ids: set[str] = set()
    sent_total = 0
    for rec in sent_records:
        mid = rec.get("message_id")
        if not mid:
            warnings.append("sent event without message_id ignored")
            continue
        sent_total += 1
        if rec.get("intended_invalid"):
            intended_ids.add(mid)
        else:
            valid_ids.add(mid)
    if len(valid_ids) + len(intended_ids) != sent_total:
        warnings.append("duplicate message_id values in sent_events.jsonl")

    # --- controller side (CONTRACTS 5) ------------------------------------
    events_path = run_dir / "events.jsonl"
    events: list[dict[str, Any]] = []
    if events_path.is_file():
        events = _read_jsonl(events_path)
    else:
        warnings.append("events.jsonl missing: no confirmations recorded")

    # --- confirmation deadline (controller clock domain; plan 5.1) --------
    # The harness and simulator run OFF the ARM VM (plan 5.1), so the
    # manifest's confirmation_deadline_monotonic_ns was captured on a
    # different host than the controller's monotonic timestamps, and
    # cross-host monotonic values are incomparable. The effective deadline
    # is therefore derived in the CONTROLLER's clock domain: max
    # received_monotonic_ns over the run's controller events plus the
    # manifest's confirmation_window_s (default 60 s). The manifest
    # deadline (clock_domain 'harness-host') is informational only and is
    # used as a last-resort fallback when the run has zero controller
    # events.
    manifest_deadline_ns = manifest.get("confirmation_deadline_monotonic_ns")
    window_s = manifest.get("confirmation_window_s")
    if not isinstance(window_s, (int, float)) or window_s <= 0:
        window_s = CONFIRMATION_WINDOW_S
    window_ns = int(window_s * 1_000_000_000)
    received_values = [
        ev["received_monotonic_ns"]
        for ev in events
        if isinstance(ev.get("received_monotonic_ns"), (int, float))
    ]
    deadline_ns: int | None = None
    if received_values:
        max_received_ns = int(max(received_values))
        deadline_ns = max_received_ns + window_ns
        if manifest_deadline_ns is None:
            warnings.append(
                "confirmation_deadline_monotonic_ns missing from manifest "
                "(informational only; deadline derived from controller "
                "events)"
            )
        elif not (
            max_received_ns
            <= manifest_deadline_ns
            <= max_received_ns + 2 * window_ns
        ):
            warnings.append(
                "IMPLAUSIBLE manifest confirmation_deadline_monotonic_ns "
                f"({manifest_deadline_ns}): outside "
                f"[{max_received_ns}, {max_received_ns + 2 * window_ns}] "
                "(max received_monotonic_ns to max + 2x confirmation "
                "window). The manifest deadline is captured on the harness "
                "host, which runs off the ARM VM (plan 5.1), and monotonic "
                "clocks are not comparable across hosts; using the "
                "event-derived deadline in the controller's clock domain"
            )
    elif manifest_deadline_ns is not None:
        deadline_ns = manifest_deadline_ns
        warnings.append(
            "no controller events with received_monotonic_ns; falling back "
            "to the manifest confirmation_deadline_monotonic_ns "
            "(clock_domain harness-host, informational only)"
        )
    else:
        warnings.append(
            "no confirmation deadline available (no controller events and "
            "no manifest deadline); all confirmations in events.jsonl "
            "counted as in-window"
        )

    confirmed_in_window: set[str] = set()
    first_latency: dict[str, float] = {}
    late_confirmations = 0
    duplicates = 0
    double_accepted = 0
    failed = 0
    rejected_valid = 0
    rejected_intended = 0
    rejected_unmatched = 0
    # Raw count of 'accepted' outcome records (late and repeated included):
    # the counterpart of the controller's cumulative accepted counter on
    # GET /metrics, used by the reconciliation acceptance (work order P1b).
    events_accepted_total = 0

    for ev in events:
        outcome = ev.get("outcome")
        mid = ev.get("message_id")
        if outcome == "accepted":
            events_accepted_total += 1
            ack = ev.get("ditto_ack_monotonic_ns")
            if ack is None:
                # CONTRACTS 5 violation: accepted events must carry the
                # Ditto ack timestamp. Still counted as a confirmation
                # (as before), but flagged.
                warnings.append("accepted event without ditto_ack_monotonic_ns")
            elif deadline_ns is not None and ack > deadline_ns:
                late_confirmations += 1
                continue
            if mid is None:
                warnings.append("accepted event without message_id ignored")
                continue
            if mid in confirmed_in_window:
                # The twin was patched more than once for the same message:
                # the exact defect the controller_restart acceptance (claim
                # C12) must rule out. Broker-level QoS 1 redeliveries that
                # the controller correctly deduplicates appear as outcome
                # 'duplicate', never here.
                double_accepted += 1
                warnings.append(f"repeated accepted event for message_id {mid}")
                continue
            confirmed_in_window.add(mid)
            latency = ev.get("latency_ms")
            if latency is not None:
                first_latency[mid] = float(latency)
        elif outcome == "duplicate":
            duplicates += 1
        elif outcome == "failed":
            failed += 1
        elif outcome == "rejected":
            if mid in intended_ids:
                rejected_intended += 1
            elif mid in valid_ids:
                rejected_valid += 1
            else:
                rejected_unmatched += 1
        else:
            warnings.append(f"unknown outcome {outcome!r} ignored")

    sent_valid = len(valid_ids)
    delivered_unique = len(confirmed_in_window & valid_ids)
    intended_invalid_accepted = len(confirmed_in_window & intended_ids)
    confirmed_unmatched = len(confirmed_in_window - valid_ids - intended_ids)
    if confirmed_unmatched:
        warnings.append(
            f"{confirmed_unmatched} confirmation(s) for message_ids absent "
            "from sent_events.jsonl"
        )
    if intended_invalid_accepted:
        warnings.append(
            f"validation defect: {intended_invalid_accepted} intentionally "
            "invalid event(s) were accepted"
        )
    lost = sent_valid - delivered_unique
    delivery_rate = delivered_unique / sent_valid if sent_valid else None
    loss_rate = lost / sent_valid if sent_valid else None

    # Latency sample: unique in-window confirmations of valid sent messages.
    latencies = [first_latency[m] for m in sorted(first_latency) if m in valid_ids]

    # --- measured window (audit 9.4) ---------------------------------------
    window = measured_window(manifest)
    measured_window_s = (
        (window[1] - window[0]).total_seconds() if window is not None else None
    )
    if window is None:
        warnings.append(
            "manifest has no usable measured_window_utc; resources.csv and "
            "controller_metrics.csv aggregated UNFILTERED (warm-up/cooldown "
            "samples may contaminate the aggregates, audit 9.4)"
        )

    # --- resources (SUT collector output; filtered to the measured window) -
    resources_rows: list[dict[str, Any]] = []
    resource_samples = 0
    cpu_max_overall: float | None = None
    mem_max_overall: int | None = None
    cpu_sustained_max = 0.0
    nproc = sut_nproc(read_sut_environment(run_dir))
    host_util_max: float | None = None
    host_sustained: float | None = None
    # Sampling coverage of the measured window (work order P1b): exposed in
    # per_run.csv and consumed by the soak DoD and saturation sufficiency.
    res_stats: dict[str, float | None] = {
        "coverage_pct": None, "max_gap_s": None, "tail_gap_s": None
    }
    metrics_stats: dict[str, float | None] = {
        "coverage_pct": None, "max_gap_s": None, "tail_gap_s": None
    }
    resources_path = run_dir / "resources.csv"
    if resources_path.is_file():
        by_container_all = read_resources_csv(resources_path)
        by_container = {
            container: filter_samples_to_window(samples, window)
            for container, samples in by_container_all.items()
        }
        res_stats = sampling_stats(
            sorted(
                {
                    s["ts"]
                    for samples in by_container.values()
                    for s in samples
                    if s.get("ts") is not None
                }
            ),
            window,
        )
        for container in sorted(by_container):
            samples = by_container[container]
            cpus = [s["cpu_pct"] for s in samples if s["cpu_pct"] is not None]
            mems = [s["mem_bytes"] for s in samples if s["mem_bytes"] is not None]
            sustained = sustained_cpu_seconds(samples)
            resources_rows.append(
                {
                    "run_id": run_id,
                    "container": container,
                    "samples": len(samples),
                    "cpu_pct_mean": statistics.fmean(cpus) if cpus else None,
                    "cpu_pct_max": max(cpus) if cpus else None,
                    "mem_bytes_mean": statistics.fmean(mems) if mems else None,
                    "mem_bytes_max": max(mems) if mems else None,
                    "cpu_sustained_gt90_s": sustained,
                }
            )
            resource_samples += len(samples)
            if cpus:
                cpu_max_overall = max(cpu_max_overall or 0.0, max(cpus))
            if mems:
                mem_max_overall = max(mem_max_overall or 0, max(mems))
            cpu_sustained_max = max(cpu_sustained_max, sustained)
        # Host-level CPU normalization (audit 9.7): needs the SUT's nproc
        # from sut_environment.json; without it the host-level values stay
        # None and the saturation CPU criterion is not evaluable.
        if nproc:
            series = host_cpu_series(by_container, nproc)
            if series:
                host_util_max = max(p["host_cpu_utilization"] for p in series)
                host_sustained = host_cpu_sustained_seconds(series)
        elif resource_samples:
            warnings.append(
                "sut_environment.json nproc unavailable: host-level CPU "
                "utilization not computed (audit 9.7); the saturation CPU "
                "criterion cannot be evaluated for this run"
            )
    else:
        warnings.append("resources.csv missing")

    # --- controller metrics (queue growth, audit 9.7) ----------------------
    controller_metric_samples = 0
    queue_depth_max: float | None = None
    queue_growth_sustained: float | None = None
    metrics_accepted_delta: float | None = None
    metrics_path = run_dir / "controller_metrics.csv"
    if metrics_path.is_file():
        metric_samples = filter_samples_to_window(
            read_controller_metrics_csv(metrics_path), window
        )
        controller_metric_samples = len(metric_samples)
        depths = [
            s["queue_depth"] for s in metric_samples if s["queue_depth"] is not None
        ]
        if depths:
            queue_depth_max = max(depths)
        queue_growth_sustained = queue_growth_sustained_seconds(metric_samples)
        metrics_stats = sampling_stats(
            [s["ts"] for s in metric_samples if s.get("ts") is not None],
            window,
        )
        # Accepted-counter delta over the measured window (work order P1b):
        # the /metrics 'accepted' field is cumulative, so last - first is
        # the number of accepts the controller itself counted during the
        # window; the reconciliation acceptance compares it against the
        # events.jsonl accepted count within a documented tolerance.
        accepted_series = [
            s["accepted"] for s in metric_samples if s.get("accepted") is not None
        ]
        if accepted_series:
            metrics_accepted_delta = float(
                accepted_series[-1] - accepted_series[0]
            )
    else:
        warnings.append(
            "controller_metrics.csv missing: queue growth not measurable "
            "for this run (audit 9.7; use --controller-url)"
        )

    exclusion = manifest.get("exclusion")

    # Resource provenance (work order P1 fix 2): every message run is a
    # timed run, and timed runs require the SUT-side collector. A
    # non-'sut-collector' source (local-dev sampler, none, or a legacy
    # manifest without the key) is flagged loudly so it can never pass
    # silently as SUT evidence.
    resource_source = manifest.get("resource_source")
    if resource_source != "sut-collector":
        warnings.append(
            f"resource_source {resource_source!r} is not 'sut-collector': "
            "resources.csv (if any) was NOT collected on the SUT VM for "
            "this timed run (audit 9.1)"
        )

    # Protocol deviations (work order P1 fix 5): recorded by the runner in
    # the manifest; listed here per run so no deviation stays invisible in
    # the processed outputs.
    deviations = manifest.get("deviations")
    if isinstance(deviations, list) and deviations:
        listed = "; ".join(
            str(d.get("kind", "unknown"))
            + (
                f" (authorized by {d.get('authorized_by_flag')})"
                if d.get("authorized_by_flag")
                else " (no authorizing flag)"
            )
            for d in deviations
            if isinstance(d, dict)
        )
        warnings.append(f"protocol deviation(s) recorded: {listed}")

    # Simulator-manifest totals (work order P1b, claim C10): the simulator
    # records how many disconnect/reconnect cycles actually happened and
    # how many events were buffered during disconnects. The dropout
    # acceptance requires both >= 1 in every included dropout run — a
    # "dropout" run without a real disconnect is not C10 evidence.
    dropout_disconnects: int | None = None
    buffered_dropout: int | None = None
    sim_manifest = read_simulator_manifest(run_dir, str(run_id))
    if sim_manifest is not None:
        totals = sim_manifest.get("totals")
        if isinstance(totals, dict):
            dd = totals.get("dropout_disconnects")
            bd = totals.get("buffered_dropout")
            if isinstance(dd, (int, float)) and not isinstance(dd, bool):
                dropout_disconnects = int(dd)
            if isinstance(bd, (int, float)) and not isinstance(bd, bool):
                buffered_dropout = int(bd)
    if (
        manifest.get("condition_id") == "dropout_reconnect"
        or manifest.get("scenario") == "dropout-reconnect"
    ) and (dropout_disconnects is None or buffered_dropout is None):
        warnings.append(
            "dropout run without simulator-manifest totals "
            "(logs/simulator/.../manifest.json): dropout_disconnects and "
            "buffered_dropout not verifiable; the C10 acceptance criterion "
            "fails for this run (work order P1b)"
        )

    # Restart-hook record (work order P1b, claim C12): the harness records
    # the --restart-cmd execution in the manifest with timestamps and exit
    # code. OK means: executed, both timestamps present, exit code 0, no
    # error. None when the manifest has no restart record at all.
    restart_record = manifest.get("restart")
    restart_hook_ok: bool | None = None
    if isinstance(restart_record, dict):
        restart_hook_ok = bool(
            restart_record.get("executed")
            and restart_record.get("started_utc")
            and restart_record.get("finished_utc")
            and restart_record.get("returncode") == 0
            and not restart_record.get("error")
        )
    if (
        manifest.get("condition_id") == "controller_restart"
        and restart_hook_ok is not True
    ):
        warnings.append(
            "controller_restart run without a successfully executed "
            "restart-hook record (executed timestamps + exit 0) in the "
            "manifest; the C12 acceptance criterion fails for this run "
            "(work order P1b)"
        )

    return {
        "run_id": run_id,
        "condition_id": manifest.get("condition_id"),
        "scenario": manifest.get("scenario"),
        "rate_msg_s": manifest.get("rate_msg_s"),
        "duration_s": manifest.get("duration_s"),
        "seed": manifest.get("seed"),
        "repetition": manifest.get("repetition"),
        "validity": manifest.get("validity"),
        "excluded": exclusion is not None,
        "exclusion_reason": (
            json.dumps(exclusion, ensure_ascii=False)
            if isinstance(exclusion, (dict, list))
            else exclusion
        ),
        "resource_source": resource_source,
        "sent_total": sent_total,
        "sent_valid": sent_valid,
        "intended_invalid_sent": len(intended_ids),
        "delivered_unique": delivered_unique,
        "lost": lost,
        "delivery_rate": delivery_rate,
        "loss_rate": loss_rate,
        "duplicates": duplicates,
        "double_accepted": double_accepted,
        "rejected_valid": rejected_valid,
        "rejected_intended_invalid": rejected_intended,
        "rejected_unmatched": rejected_unmatched,
        "failed": failed,
        "late_confirmations": late_confirmations,
        "intended_invalid_accepted": intended_invalid_accepted,
        "confirmed_unmatched": confirmed_unmatched,
        "latency_count": len(latencies),
        "latency_ms_mean": statistics.fmean(latencies) if latencies else None,
        "latency_ms_p50": percentile(latencies, 50),
        "latency_ms_p95": percentile(latencies, 95),
        "latency_ms_p99": percentile(latencies, 99),
        "latency_ms_min": min(latencies) if latencies else None,
        "latency_ms_max": max(latencies) if latencies else None,
        "resource_samples": resource_samples,
        "cpu_pct_max": cpu_max_overall,
        "cpu_sustained_gt90_s": cpu_sustained_max,
        "mem_bytes_max": mem_max_overall,
        "nproc": nproc,
        "host_cpu_utilization_max": host_util_max,
        "host_cpu_sustained_gt090_s": host_sustained,
        "controller_metric_samples": controller_metric_samples,
        "queue_depth_max": queue_depth_max,
        "queue_growth_sustained_s": queue_growth_sustained,
        "measured_window_s": measured_window_s,
        "resources_coverage_pct": res_stats["coverage_pct"],
        "resources_max_gap_s": res_stats["max_gap_s"],
        "metrics_coverage_pct": metrics_stats["coverage_pct"],
        "metrics_max_gap_s": metrics_stats["max_gap_s"],
        "metrics_tail_gap_s": metrics_stats["tail_gap_s"],
        "events_accepted_total": events_accepted_total,
        "metrics_accepted_delta": metrics_accepted_delta,
        "dropout_disconnects": dropout_disconnects,
        "buffered_dropout": buffered_dropout,
        "restart_hook_ok": restart_hook_ok,
        "warnings": " | ".join(warnings),
        "_resources": resources_rows,
    }


# ---------------------------------------------------------------------------
# External runs (audit 9.6, claim C15)
# ---------------------------------------------------------------------------

EXTERNAL_RUNS_COLUMNS = [
    "run_id",
    "condition_id",
    "sample_label",
    "started_utc",
    "ended_utc",
    "duration_s",
    "outcome",
]

#: External conditions whose per-run duration gets full cross-run statistics.
#: qemu_boots is deliberately absent: plan 5.1 forbids performance inference
#: from QEMU; its runs get a strictly functional pass/fail listing only.
EXTERNAL_DURATION_CONDITIONS = ("cold_start", "twin_creation")


def compute_external_run(run_dir: str | Path) -> dict[str, Any] | None:
    """Read one external run (``timings.json`` ingested by the runner).

    Returns ``{run_id, condition_id, excluded, sample_rows, duration_mean_s}``
    or None when timings.json is absent/unreadable (notice on stderr).
    ``duration_mean_s`` is the per-run value used as the unit of analysis
    (mean of the run's samples; normally one sample per run).
    """
    run_dir = Path(run_dir)
    timings_path = run_dir / "timings.json"
    if not timings_path.is_file():
        return None
    try:
        timings = json.loads(timings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[analyze] notice: {run_dir.name} has an unreadable "
            f"timings.json ({exc}); skipped",
            file=sys.stderr,
        )
        return None
    manifest: dict[str, Any] = {}
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    run_id = manifest.get("run_id") or timings.get("run_id") or run_dir.name
    condition_id = manifest.get("condition_id") or timings.get("condition")
    samples = timings.get("samples")
    if not isinstance(samples, list):
        samples = []

    sample_rows: list[dict[str, Any]] = []
    durations: list[float] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        duration = sample.get("duration_s")
        if isinstance(duration, (int, float)):
            durations.append(float(duration))
        else:
            duration = None
        # qemu boot samples carry a functional outcome ("pass"/"fail")
        # provided by the operator; it is listed verbatim, never inferred.
        outcome = sample.get("outcome")
        sample_rows.append(
            {
                "run_id": run_id,
                "condition_id": condition_id,
                "sample_label": sample.get("label"),
                "started_utc": sample.get("started_utc"),
                "ended_utc": sample.get("ended_utc"),
                "duration_s": duration,
                "outcome": outcome if isinstance(outcome, str) else "unspecified",
            }
        )

    return {
        "run_id": run_id,
        "condition_id": condition_id,
        "excluded": manifest.get("exclusion") is not None,
        "sample_rows": sample_rows,
        "duration_mean_s": statistics.fmean(durations) if durations else None,
    }


def summarize_external_durations(
    external_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Cross-run duration statistics for cold_start and twin_creation.

    Unit of analysis = run (plan 7.3): one duration value per run
    (``duration_mean_s``). Output rows use the SUMMARY_COLUMNS schema with
    metric ``duration_s``. qemu_boots is deliberately excluded (plan 5.1:
    no performance statistics from QEMU).
    """
    out: list[dict[str, Any]] = []
    for condition_id in EXTERNAL_DURATION_CONDITIONS:
        values = [
            float(r["duration_mean_s"])
            for r in external_rows
            if r.get("condition_id") == condition_id
            and not r.get("excluded")
            and r.get("duration_mean_s") is not None
        ]
        if not values:
            continue
        mean, stdev, half = ci95(values)
        record: dict[str, Any] = {
            "condition_id": condition_id,
            "rate_msg_s": None,
            "metric": "duration_s",
            "n_runs": len(values),
            "mean": mean,
            "stdev": stdev,
            "ci95_lo": None,
            "ci95_hi": None,
            "median": percentile(values, 50),
            "p25": percentile(values, 25),
            "p75": percentile(values, 75),
            "min": min(values),
            "max": max(values),
        }
        if half is not None and mean is not None:
            record["ci95_lo"] = mean - half
            record["ci95_hi"] = mean + half
        out.append(record)
    return out


# ---------------------------------------------------------------------------
# Cross-run summary (unit of analysis = run, plan 7.3)
# ---------------------------------------------------------------------------

SUMMARY_METRICS = [
    "delivery_rate",
    "loss_rate",
    "latency_ms_mean",
    "latency_ms_p50",
    "latency_ms_p95",
    "latency_ms_p99",
    "cpu_pct_max",
    "host_cpu_utilization_max",
    "queue_depth_max",
    "mem_bytes_max",
]

SUMMARY_COLUMNS = [
    "condition_id",
    "rate_msg_s",
    "metric",
    "n_runs",
    "mean",
    "stdev",
    "ci95_lo",
    "ci95_hi",
    "median",
    "p25",
    "p75",
    "min",
    "max",
]


def summarize_by_condition(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Long-format cross-run statistics grouped by (condition, rate).

    Excluded runs must already be filtered out by the caller. The soak
    condition is summarized descriptively: its CI columns stay empty
    (plan 7.3).
    """
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row.get("condition_id"), row.get("rate_msg_s")), []).append(row)

    def _group_key(key: tuple[Any, Any]) -> tuple[int, float, str]:
        condition_id, rate = key
        return (
            CONDITION_ORDER.get(condition_id, len(CONDITION_ORDER)),
            rate if isinstance(rate, (int, float)) else -1.0,
            str(condition_id),
        )

    out: list[dict[str, Any]] = []
    for key in sorted(groups, key=_group_key):
        condition_id, rate = key
        member_rows = groups[key]
        descriptive_only = condition_id == "soak"
        for metric in SUMMARY_METRICS:
            values = [
                float(r[metric]) for r in member_rows if r.get(metric) is not None
            ]
            if not values:
                continue
            mean, stdev, half = ci95(values)
            record: dict[str, Any] = {
                "condition_id": condition_id,
                "rate_msg_s": rate,
                "metric": metric,
                "n_runs": len(values),
                "mean": mean,
                "stdev": None if descriptive_only else stdev,
                "ci95_lo": None,
                "ci95_hi": None,
                "median": percentile(values, 50),
                "p25": percentile(values, 25),
                "p75": percentile(values, 75),
                "min": min(values),
                "max": max(values),
            }
            if not descriptive_only and half is not None and mean is not None:
                record["ci95_lo"] = mean - half
                record["ci95_hi"] = mean + half
            out.append(record)
    return out


# ---------------------------------------------------------------------------
# Per-condition acceptance (audit 9.5, claims C10/C11/C12/C14)
# ---------------------------------------------------------------------------

ACCEPTANCE_COLUMNS = [
    "condition_id",
    "claims",
    "criterion",
    "expected_runs",
    "n_runs",
    "observed",
    "passed",
]


def _metrics_reconciled(row: dict[str, Any]) -> bool:
    """Per-run controller-metrics reconciliation (work order P1b).

    The /metrics accepted-counter delta over the measured window must match
    the events.jsonl accepted count within max(ABS, FRAC * count)
    (protocol.py, pending advisor sign-off). Missing metrics never
    reconcile: mandated instrumentation must be present, not tolerated.
    """
    delta = row.get("metrics_accepted_delta")
    total = row.get("events_accepted_total")
    if delta is None or total is None:
        return False
    tolerance = max(
        METRICS_RECONCILIATION_TOLERANCE_ABS,
        METRICS_RECONCILIATION_TOLERANCE_FRAC * float(total),
    )
    return abs(float(delta) - float(total)) <= tolerance


def evaluate_acceptance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Acceptance evaluation for ALL planned simulator conditions.

    ``rows`` are the INCLUDED per-run rows (valid, non-excluded); a
    defensive re-filter is applied anyway. The function iterates over the
    protocol's planned simulator conditions — NOT over the conditions found
    in raw/ — so a planned condition with zero runs still yields FAILED
    rows (work order P1b): ``passed`` is None ONLY for the explicitly
    informational/descriptive criteria.

    Completeness gate: each condition gets a ``runs_complete`` row
    (n_valid == planned repetitions; for load_sweep repetitions x number of
    swept rates), and every substantive criterion is gated on it — passed
    is False whenever n_valid == 0 or n_valid != expected, with the
    'n_valid/expected valid runs' detail in the observed column.
    """
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        cid = row.get("condition_id")
        if isinstance(cid, str):
            by_condition.setdefault(cid, []).append(row)

    def _total(members: list[dict[str, Any]], key: str) -> int:
        return sum(int(r.get(key) or 0) for r in members)

    out: list[dict[str, Any]] = []

    for condition in CONDITIONS:
        if condition.runner != "simulator":
            continue
        cid = condition.id
        claims = " ".join(CONDITION_CLAIMS.get(cid, ()))
        members = by_condition.get(cid, [])
        # Defensive re-filter (the caller already passes included rows):
        # only valid, non-excluded runs may satisfy acceptance criteria.
        valid = [
            r
            for r in members
            if not r.get("excluded") and r.get("validity") in (None, "valid")
        ]
        not_counted = len(members) - len(valid)
        expected = condition.repetitions * (
            len(condition.rates_msg_s) if condition.rates_msg_s else 1
        )
        n_valid = len(valid)
        complete = n_valid == expected
        note = f"{n_valid}/{expected} valid runs"

        def add(criterion: str, observed: str, passed: bool | None) -> None:
            out.append(
                {
                    "condition_id": cid,
                    "claims": claims,
                    "criterion": criterion,
                    "expected_runs": expected,
                    "n_runs": n_valid,
                    "observed": observed,
                    "passed": passed,
                }
            )

        def gate(substantive_ok: bool, observed: str) -> tuple[bool, str]:
            """Completeness-gate a substantive criterion (never None)."""
            if not complete:
                return False, f"{observed}; INCOMPLETE: {note}"
            return bool(substantive_ok), f"{observed}; {note}"

        def count_ok(pred: Any) -> int:
            return sum(1 for r in valid if pred(r))

        # Explicit per-condition completeness row (work order P1b): the
        # CSV shows completeness separately from the substantive criteria.
        observed = note
        if not_counted:
            observed += f" ({not_counted} excluded/invalid run(s) not counted)"
        add("runs_complete", observed, complete)

        if cid == "smoke_sequence":
            # C14: zero lost valid messages across all runs.
            lost = _total(valid, "lost")
            passed, observed = gate(lost == 0, f"{lost} lost")
            add("zero_lost", observed, passed)

        elif cid == "invalid_payload":
            # C11.
            sent_invalid = _total(valid, "intended_invalid_sent")
            rejected_invalid = _total(valid, "rejected_intended_invalid")
            accepted_invalid = _total(valid, "intended_invalid_accepted")
            passed, observed = gate(
                sent_invalid > 0 and rejected_invalid == sent_invalid,
                f"{rejected_invalid}/{sent_invalid} rejected",
            )
            add("all_intended_invalid_rejected", observed, passed)
            passed, observed = gate(
                accepted_invalid == 0, f"{accepted_invalid} accepted"
            )
            add("zero_intended_invalid_accepted", observed, passed)
            # Informational: valid messages keep the plan 7.3 delivery
            # accounting (intended_invalid never enters the denominator);
            # no pass threshold of its own here — C06 owns the >= 99%
            # nominal target. Deliberately passed=None (informational).
            delivery_values = [
                float(r["delivery_rate"])
                for r in valid
                if r.get("delivery_rate") is not None
            ]
            add(
                "valid_delivery_rate_mean_informational",
                (
                    f"{statistics.fmean(delivery_values):.6f}; {note}"
                    if delivery_values
                    else f"no data; {note}"
                ),
                None,
            )

        elif cid == "dropout_reconnect":
            # C10: accounting tolerant of late buffered redelivery within
            # the window (module docstring assumptions).
            lost = _total(valid, "lost")
            double = _total(valid, "double_accepted")
            passed, observed = gate(
                lost == 0,
                f"{lost} lost (buffered redelivery counted when confirmed "
                "in-window)",
            )
            add("zero_lost_within_window", observed, passed)
            passed, observed = gate(double == 0, f"{double} double-accepted")
            add("zero_double_accepted", observed, passed)
            # The dropout scenario must have DONE something (work order
            # P1b): every run's simulator manifest totals must show at
            # least one real disconnect and at least one buffered event.
            for key, criterion in (
                ("dropout_disconnects", "dropout_disconnects_ge_1_every_run"),
                ("buffered_dropout", "buffered_dropout_ge_1_every_run"),
            ):
                ok = count_ok(
                    lambda r, k=key: isinstance(r.get(k), (int, float))
                    and r.get(k) >= 1
                )
                missing = count_ok(lambda r, k=key: r.get(k) is None)
                observed = f"{ok}/{n_valid} run(s) with {key} >= 1"
                if missing:
                    observed += (
                        f"; simulator manifest totals missing in {missing} "
                        "run(s)"
                    )
                passed, observed = gate(ok == n_valid, observed)
                add(criterion, observed, passed)

        elif cid == "controller_restart":
            # C12: the restart hook must actually have run (executed
            # timestamps + exit 0 in the manifest record, work order P1b),
            # delivery across the restart, zero double-accepted.
            hook_ok = count_ok(lambda r: r.get("restart_hook_ok") is True)
            observed = (
                f"{hook_ok}/{n_valid} run(s) with executed restart hook "
                "(timestamps + exit 0)"
            )
            passed, observed = gate(hook_ok == n_valid, observed)
            add("restart_hook_executed_every_run", observed, passed)
            lost = _total(valid, "lost")
            double = _total(valid, "double_accepted")
            passed, observed = gate(lost == 0, f"{lost} lost")
            add("delivery_across_restart_zero_lost", observed, passed)
            passed, observed = gate(double == 0, f"{double} double-accepted")
            add("zero_double_accepted", observed, passed)

        elif cid == "soak":
            # C13 Definition of Done (work order P1b; thresholds in
            # protocol.py, pending advisor sign-off before exp-v1).
            def _fmt_val(value: Any, suffix: str = "") -> str:
                if value is None:
                    return "n/a"
                return f"{float(value):.2f}{suffix}"

            win_ok = count_ok(
                lambda r: r.get("measured_window_s") is not None
                and float(r["measured_window_s"]) >= SOAK_MIN_WINDOW_S
            )
            windows = ", ".join(
                _fmt_val(r.get("measured_window_s"), " s") for r in valid
            )
            observed = (
                f"{win_ok}/{n_valid} run(s) with measured window >= "
                f"{SOAK_MIN_WINDOW_S} s (observed: {windows or 'none'})"
            )
            passed, observed = gate(win_ok == n_valid, observed)
            add("measured_window_ge_24h", observed, passed)

            for cov_key, gap_key, criterion in (
                (
                    "resources_coverage_pct",
                    "resources_max_gap_s",
                    "resources_coverage_and_cadence",
                ),
                (
                    "metrics_coverage_pct",
                    "metrics_max_gap_s",
                    "controller_metrics_coverage_and_cadence",
                ),
            ):
                ok = count_ok(
                    lambda r, ck=cov_key, gk=gap_key: (
                        r.get(ck) is not None
                        and float(r[ck]) >= SOAK_MIN_COVERAGE_PCT
                        and r.get(gk) is not None
                        and float(r[gk]) <= SOAK_MAX_SAMPLING_GAP_S
                    )
                )
                details = ", ".join(
                    f"coverage {_fmt_val(r.get(cov_key), '%')} / max gap "
                    f"{_fmt_val(r.get(gap_key), ' s')}"
                    for r in valid
                )
                observed = (
                    f"{ok}/{n_valid} run(s) with coverage >= "
                    f"{SOAK_MIN_COVERAGE_PCT:g}% and no sampling gap > "
                    f"{SOAK_MAX_SAMPLING_GAP_S:g} s (observed: "
                    f"{details or 'none'})"
                )
                passed, observed = gate(ok == n_valid, observed)
                add(criterion, observed, passed)

            interruption_ok = count_ok(
                lambda r: (
                    r.get("metrics_max_gap_s") is not None
                    and float(r["metrics_max_gap_s"])
                    <= SOAK_MAX_INTERRUPTION_GAP_S
                    and r.get("metrics_tail_gap_s") is not None
                    and float(r["metrics_tail_gap_s"])
                    <= SOAK_MAX_INTERRUPTION_GAP_S
                )
            )
            tails = ", ".join(
                f"max gap {_fmt_val(r.get('metrics_max_gap_s'), ' s')} / "
                f"tail gap {_fmt_val(r.get('metrics_tail_gap_s'), ' s')}"
                for r in valid
            )
            observed = (
                f"{interruption_ok}/{n_valid} run(s) with no "
                f"controller-metrics gap > {SOAK_MAX_INTERRUPTION_GAP_S:g} s "
                f"and last sample within {SOAK_MAX_INTERRUPTION_GAP_S:g} s "
                f"of the window end (observed: {tails or 'none'})"
            )
            passed, observed = gate(interruption_ok == n_valid, observed)
            add("no_unrecovered_interruption", observed, passed)

            # Delivery stays descriptive per plan 7.3 (no CI of its own):
            # deliberately passed=None (descriptive), unchanged by P1b.
            delivered = _total(valid, "delivered_unique")
            sent_valid_total = _total(valid, "sent_valid")
            lost = _total(valid, "lost")
            add(
                "delivery_descriptive",
                f"delivered {delivered}/{sent_valid_total} valid sent, "
                f"{lost} lost (descriptive, no CI, plan 7.3); {note}",
                None,
            )

        # Controller-metrics reconciliation (work order P1b): mandated
        # instrumentation for dropout_reconnect, load_sweep and soak. A
        # run without metrics FAILS the criterion — never blank.
        if cid in ("dropout_reconnect", "load_sweep", "soak"):
            ok = count_ok(_metrics_reconciled)
            missing = count_ok(
                lambda r: r.get("metrics_accepted_delta") is None
                or r.get("events_accepted_total") is None
            )
            observed = (
                f"{ok}/{n_valid} run(s) with |accepted-counter delta - "
                f"events accepted| <= max("
                f"{METRICS_RECONCILIATION_TOLERANCE_ABS:g}, "
                f"{METRICS_RECONCILIATION_TOLERANCE_FRAC:.0%})"
            )
            if missing:
                observed += f"; controller metrics missing in {missing} run(s)"
            passed, observed = gate(ok == n_valid, observed)
            add("controller_metrics_reconciled", observed, passed)

    return out


# ---------------------------------------------------------------------------
# Saturation (plan 7.3; audit 9.7)
# ---------------------------------------------------------------------------


def detect_saturation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate the plan 7.3 saturation criteria on load-sweep runs.

    ``rows`` are non-excluded per-run rows; only ``condition_id ==
    "load_sweep"`` entries are used (a defensive validity re-filter is
    applied). See the module docstring for the documented decision rule.
    The CPU criterion is host-level (audit 9.7) and the queue-growth
    criterion uses the controller_metrics.csv samples; both, plus the
    >= 0.5 run-fraction rule, are PENDING ADVISOR SIGN-OFF BEFORE exp-v1
    (G4) and must not change after the protocol freeze. A criterion
    evaluates to None (not evaluable) at a load where no run carries the
    required instrumentation (missing nproc or missing
    controller_metrics.csv) — never silently to False.

    Evidence sufficiency (work order P1b): every PLANNED sweep load is
    listed, and a load's ``verdict`` ("saturated" / "not-saturated" /
    "insufficient-evidence") is decided only when the planned number of
    valid runs exists AND every run carries the required instrumentation
    (host-CPU criterion evaluable; resources coverage >=
    SATURATION_MIN_RESOURCE_COVERAGE_PCT; controller metrics present).
    Anything less yields "insufficient-evidence" with per-run detail —
    never "not-saturated". ``first_saturated_load_msg_s`` considers only
    loads with verdict "saturated". The per-load ``saturated`` flag keeps
    the raw threshold-crossing outcome over the available runs
    (stop-condition rule: the statistical criteria are unchanged beyond
    completeness).
    """
    sweep_condition = CONDITIONS_BY_ID.get("load_sweep")
    expected_per_load = (
        sweep_condition.repetitions if sweep_condition is not None else 0
    )
    planned_rates = [
        float(rate)
        for rate in (
            sweep_condition.rates_msg_s
            if sweep_condition is not None and sweep_condition.rates_msg_s
            else ()
        )
    ]

    sweep = [
        r
        for r in rows
        if r.get("condition_id") == "load_sweep"
        and isinstance(r.get("rate_msg_s"), (int, float))
        # Defensive re-filter (work order P1b): saturation may only ever
        # see valid, non-excluded runs.
        and not r.get("excluded")
        and r.get("validity") in (None, "valid")
    ]
    by_rate: dict[float, list[dict[str, Any]]] = {}
    for row in sweep:
        by_rate.setdefault(float(row["rate_msg_s"]), []).append(row)

    def _run_fraction(
        member_rows: list[dict[str, Any]], key: str, sustain_s: float
    ) -> float | None:
        """Fraction of evaluable runs with a sustained event >= sustain_s."""
        evaluable = [r for r in member_rows if r.get(key) is not None]
        if not evaluable:
            return None
        flags = [1 if float(r[key]) >= sustain_s else 0 for r in evaluable]
        return statistics.fmean(flags)

    loads: list[dict[str, Any]] = []
    first_saturated: float | None = None
    for rate in sorted(set(planned_rates) | set(by_rate)):
        member_rows = by_rate.get(rate, [])
        loss_values = [
            float(r["loss_rate"]) for r in member_rows if r.get("loss_rate") is not None
        ]
        p95_values = [
            float(r["latency_ms_p95"])
            for r in member_rows
            if r.get("latency_ms_p95") is not None
        ]
        loss_mean = statistics.fmean(loss_values) if loss_values else None
        p95_mean = statistics.fmean(p95_values) if p95_values else None
        host_cpu_fraction = _run_fraction(
            member_rows, "host_cpu_sustained_gt090_s", SATURATION_CPU_SUSTAIN_S
        )
        queue_fraction = _run_fraction(
            member_rows, "queue_growth_sustained_s", SATURATION_QUEUE_GROWTH_SUSTAIN_S
        )
        triggered = {
            "loss_rate": loss_mean is not None and loss_mean > SATURATION_LOSS_RATE,
            "p95_latency": p95_mean is not None and p95_mean > SATURATION_P95_MS,
            "host_cpu_sustained": (
                None if host_cpu_fraction is None else host_cpu_fraction >= 0.5
            ),
            "queue_growth": (
                None if queue_fraction is None else queue_fraction >= 0.5
            ),
        }
        saturated = any(v for v in triggered.values() if v is not None)

        # Evidence sufficiency (work order P1b): a subset of runs, or runs
        # without the mandated instrumentation, must never decide a load's
        # verdict.
        insufficiency: list[str] = []
        if len(member_rows) != expected_per_load:
            insufficiency.append(
                f"{len(member_rows)}/{expected_per_load} valid runs"
            )
        for r in member_rows:
            rid = r.get("run_id") or "?"
            if r.get("host_cpu_sustained_gt090_s") is None:
                insufficiency.append(
                    f"run {rid}: host CPU criterion not evaluable (missing "
                    "nproc or SUT resources)"
                )
            coverage = r.get("resources_coverage_pct")
            if (
                coverage is None
                or float(coverage) < SATURATION_MIN_RESOURCE_COVERAGE_PCT
            ):
                observed_cov = (
                    "n/a" if coverage is None else f"{float(coverage):.1f}%"
                )
                insufficiency.append(
                    f"run {rid}: resources coverage {observed_cov} below the "
                    f"{SATURATION_MIN_RESOURCE_COVERAGE_PCT:g}% minimum"
                )
            if r.get("queue_growth_sustained_s") is None:
                insufficiency.append(
                    f"run {rid}: controller metrics missing (queue-growth "
                    "criterion not evaluable)"
                )
        if insufficiency:
            verdict = "insufficient-evidence"
        elif saturated:
            verdict = "saturated"
        else:
            verdict = "not-saturated"

        loads.append(
            {
                "rate_msg_s": rate,
                "n_runs": len(member_rows),
                "expected_runs": expected_per_load,
                "loss_rate_mean": loss_mean,
                "latency_ms_p95_mean": p95_mean,
                "host_cpu_sustained_run_fraction": host_cpu_fraction,
                "queue_growth_run_fraction": queue_fraction,
                "triggered": triggered,
                "saturated": saturated,
                "evidence_sufficient": not insufficiency,
                "insufficient_evidence_detail": insufficiency,
                "verdict": verdict,
            }
        )
        if verdict == "saturated" and first_saturated is None:
            first_saturated = rate

    return {
        "generated_by": "egw_experiments.analyze",
        "protocol_version": PROTOCOL_VERSION,
        "criteria": {
            "loss_rate_gt": SATURATION_LOSS_RATE,
            "latency_ms_p95_gt": SATURATION_P95_MS,
            "host_cpu_utilization_gt": SATURATION_HOST_CPU_UTILIZATION,
            "host_cpu_sustain_s": SATURATION_CPU_SUSTAIN_S,
            "queue_depth_floor": SATURATION_QUEUE_DEPTH_FLOOR,
            "queue_growth_sustain_s": SATURATION_QUEUE_GROWTH_SUSTAIN_S,
            "run_fraction_gte": 0.5,
            "max_sample_gap_s": MAX_SAMPLE_GAP_S,
            "expected_runs_per_load": expected_per_load,
            "min_resource_coverage_pct": SATURATION_MIN_RESOURCE_COVERAGE_PCT,
        },
        "decision_rule": (
            "Unit of analysis is the run (plan 7.3). A load is saturated "
            "when the across-run mean loss rate exceeds 1%, OR the "
            "across-run mean p95 latency exceeds 1000 ms, OR at least half "
            "of the evaluable runs at that load sustain host-level CPU "
            "utilization above 0.90 for at least 60 s "
            "(host_cpu_utilization = sum of container docker-stats cpu_pct "
            "/ (100 * nproc from sut_environment.json)), OR at least half "
            "of the evaluable runs show persistent queue growth: "
            "controller queue_depth (1 Hz GET /metrics samples) strictly "
            "increasing across consecutive samples for a span of at least "
            "60 s with every sample above the floor of 100 messages. "
            "Sustained windows break across sampling gaps larger than "
            "max_sample_gap_s (work order P1b). A load's verdict is "
            "decided ONLY when the planned number of valid runs exists and "
            "every run carries the required instrumentation (host-CPU "
            "criterion evaluable, resources coverage >= "
            "min_resource_coverage_pct, controller metrics present); "
            "otherwise the verdict is 'insufficient-evidence', never "
            "'not-saturated'. Saturation is the first (lowest) load with "
            "verdict 'saturated'."
        ),
        "pending_advisor_signoff": (
            "PENDING ADVISOR SIGN-OFF BEFORE exp-v1 (audit R23): the "
            "host-level CPU rule (> 0.90 utilization sustained 60 s), the "
            "queue-growth rule (strictly increasing over >= 60 s, floor "
            "100), the >= 0.5 run-fraction rule, the 5 s sampling-cadence "
            "cap (MAX_SAMPLE_GAP_S) and the 90% minimum resources coverage "
            "(SATURATION_MIN_RESOURCE_COVERAGE_PCT) must be confirmed with "
            "the advisor before the protocol freeze (G4); they must not "
            "change afterwards."
        ),
        "loads": loads,
        "first_saturated_load_msg_s": first_saturated,
    }


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


def _fmt(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return round(value, 6)
    return value


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_fmt(row.get(col)) for col in columns])


def _clean_dir(path: Path) -> None:
    """Delete everything inside ``path`` except ``.gitkeep`` (regeneration)."""
    path.mkdir(parents=True, exist_ok=True)
    for child in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if child.name == ".gitkeep":
            continue
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir() and not any(child.iterdir()):
            child.rmdir()


def _run_sort_key(row: dict[str, Any]) -> tuple[int, float, int, str]:
    rate = row.get("rate_msg_s")
    rep = row.get("repetition")
    return (
        CONDITION_ORDER.get(row.get("condition_id"), len(CONDITION_ORDER)),
        float(rate) if isinstance(rate, (int, float)) else -1.0,
        int(rep) if isinstance(rep, int) else 0,
        str(row.get("run_id")),
    )


def _summary_sort_key(row: dict[str, Any]) -> tuple[int, float]:
    rate = row.get("rate_msg_s")
    return (
        CONDITION_ORDER.get(row.get("condition_id"), len(CONDITION_ORDER)),
        float(rate) if isinstance(rate, (int, float)) else -1.0,
    )


# ---------------------------------------------------------------------------
# Figures (optional matplotlib; guarded import)
# ---------------------------------------------------------------------------

MATPLOTLIB_NOTICE = (
    "notice: matplotlib is not installed; figures were skipped. Processed "
    "tables were fully regenerated. To generate figures install the "
    "optional analysis extra: pip install -e src[analysis]"
)


def generate_figures(
    figures_dir: Path, rows: list[dict[str, Any]]
) -> list[Path]:
    """Generate the campaign figures from non-excluded per-run rows.

    Returns the list of written files. Prints a clear notice and returns an
    empty list when matplotlib is unavailable (optional dependency) or when
    there is no load-sweep data yet.
    """
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        print(MATPLOTLIB_NOTICE)
        return []

    sweep = [
        r
        for r in rows
        if r.get("condition_id") == "load_sweep"
        and isinstance(r.get("rate_msg_s"), (int, float))
    ]
    if not sweep:
        print(
            "notice: no load_sweep runs in results/raw yet; figures skipped"
        )
        return []

    by_rate: dict[float, list[dict[str, Any]]] = {}
    for row in sweep:
        by_rate.setdefault(float(row["rate_msg_s"]), []).append(row)
    rates = sorted(by_rate)

    def _mean_of(metric: str, rate: float) -> float | None:
        values = [
            float(r[metric]) for r in by_rate[rate] if r.get(metric) is not None
        ]
        return statistics.fmean(values) if values else None

    written: list[Path] = []

    # 1. Latency percentiles vs load.
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for metric, label in (
        ("latency_ms_p50", "p50"),
        ("latency_ms_p95", "p95"),
        ("latency_ms_p99", "p99"),
    ):
        ys = [_mean_of(metric, rate) for rate in rates]
        ax.plot(rates, ys, marker="o", label=label)
    ax.set_xlabel("Offered load (msg/s)")
    ax.set_ylabel("Latency (ms), mean of per-run percentiles")
    ax.set_title("MQTT-to-Ditto latency percentiles vs load")
    ax.legend()
    ax.grid(True, alpha=0.3)
    path = figures_dir / "latency_percentiles_vs_load.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    # 2. Delivery rate vs load (with CI95 error bars when defined).
    fig, ax = plt.subplots(figsize=(7, 4.5))
    means: list[float] = []
    errors: list[float] = []
    for rate in rates:
        values = [
            float(r["delivery_rate"])
            for r in by_rate[rate]
            if r.get("delivery_rate") is not None
        ]
        mean, _stdev, half = ci95(values)
        means.append(mean if mean is not None else float("nan"))
        errors.append(half if half is not None else 0.0)
    ax.errorbar(rates, means, yerr=errors, marker="o", capsize=4)
    ax.set_xlabel("Offered load (msg/s)")
    ax.set_ylabel("Delivery rate (unique confirmations / valid sent)")
    ax.set_title("Delivery rate vs load (mean across runs, CI95)")
    ax.grid(True, alpha=0.3)
    path = figures_dir / "delivery_rate_vs_load.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    # 3. Resource usage vs load (per-container mean CPU across runs).
    containers: dict[str, dict[float, list[float]]] = {}
    for row in sweep:
        rate = float(row["rate_msg_s"])
        for res in row.get("_resources", []):
            if res.get("cpu_pct_mean") is None:
                continue
            containers.setdefault(res["container"], {}).setdefault(rate, []).append(
                float(res["cpu_pct_mean"])
            )
    if containers:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for container in sorted(containers):
            ys = [
                statistics.fmean(containers[container][rate])
                if containers[container].get(rate)
                else None
                for rate in rates
            ]
            ax.plot(rates, ys, marker="o", label=container)
        ax.set_xlabel("Offered load (msg/s)")
        ax.set_ylabel("CPU (%, single-CPU basis, mean across runs)")
        ax.set_title("Container CPU usage vs load")
        ax.legend(fontsize="small")
        ax.grid(True, alpha=0.3)
        path = figures_dir / "resource_usage_vs_load.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        written.append(path)

    return written


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def analyze(base_dir: str | Path | None = None) -> int:
    """Regenerate ``processed/`` and ``figures/`` from ``raw/``.

    Returns 0 on success (including when matplotlib is absent and figures
    are skipped with a notice) and 2 when ``results/raw`` does not exist.
    """
    base = Path(base_dir) if base_dir is not None else DEFAULT_RESULTS_BASE
    raw_dir = base / "raw"
    processed_dir = base / "processed"
    figures_dir = base / "figures"

    if not raw_dir.is_dir():
        print(f"error: {raw_dir} does not exist", file=sys.stderr)
        return 2

    _clean_dir(processed_dir)
    _clean_dir(figures_dir)

    rows: list[dict[str, Any]] = []
    external_rows: list[dict[str, Any]] = []
    for run_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        # External runs (audit 9.6): timings.json marks an operator-measured
        # run ingested by 'run --external-timings'; analyzed here so a
        # single script covers every run type (claim C15).
        if (run_dir / "timings.json").is_file():
            ext = compute_external_run(run_dir)
            if ext is not None:
                external_rows.append(ext)
            continue
        row = compute_run_metrics(run_dir)
        if row is not None:
            rows.append(row)
    rows.sort(key=_run_sort_key)
    external_rows.sort(
        key=lambda r: (
            CONDITION_ORDER.get(r.get("condition_id"), len(CONDITION_ORDER)),
            str(r.get("run_id")),
        )
    )

    resources_rows: list[dict[str, Any]] = []
    for row in rows:
        resources_rows.extend(row.get("_resources", []))

    # Aggregation gate (work order P1 fix 1): a run enters summaries,
    # saturation, acceptance and figures only when it is NOT excluded AND
    # its validity is 'valid'. A missing/None validity is tolerated ONLY
    # for legacy manifests without the key; any present non-'valid' value
    # always excludes the run from aggregation. per_run.csv keeps every
    # run listed with its validity flag (visibility without contamination).
    def _invalid_validity(row: dict[str, Any]) -> bool:
        validity = row.get("validity")
        return validity is not None and validity != "valid"

    invalid_rows = [r for r in rows if _invalid_validity(r)]
    included = [
        r for r in rows if not r["excluded"] and not _invalid_validity(r)
    ]
    excluded_count = sum(1 for r in rows if r["excluded"])
    if excluded_count:
        print(
            f"[analyze] {excluded_count} run(s) excluded per manifest "
            "'exclusion' (documented cause required, plan 7.3); they remain "
            "listed in per_run.csv"
        )
    if invalid_rows:
        invalid_ids = ", ".join(str(r.get("run_id")) for r in invalid_rows)
        print(
            f"[analyze] {len(invalid_rows)} run(s) with validity != 'valid' "
            "removed from summaries, saturation, acceptance and figures; "
            f"they remain listed in per_run.csv: {invalid_ids}"
        )

    _write_csv(processed_dir / "per_run.csv", PER_RUN_COLUMNS, rows)
    _write_csv(
        processed_dir / "resources_by_run.csv",
        RESOURCES_BY_RUN_COLUMNS,
        resources_rows,
    )

    summary_rows = summarize_by_condition(included)
    summary_rows.extend(summarize_external_durations(external_rows))
    summary_rows.sort(key=_summary_sort_key)
    _write_csv(
        processed_dir / "summary_by_condition.csv", SUMMARY_COLUMNS, summary_rows
    )

    external_sample_rows: list[dict[str, Any]] = []
    for ext in external_rows:
        external_sample_rows.extend(ext["sample_rows"])
    _write_csv(
        processed_dir / "external_runs.csv",
        EXTERNAL_RUNS_COLUMNS,
        external_sample_rows,
    )

    _write_csv(
        processed_dir / "acceptance_by_condition.csv",
        ACCEPTANCE_COLUMNS,
        evaluate_acceptance(included),
    )

    (processed_dir / "saturation.json").write_text(
        json.dumps(detect_saturation(included), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    figures = generate_figures(figures_dir, included)

    print(
        f"[analyze] {len(rows)} message run(s) processed "
        f"({len(included)} included, {excluded_count} excluded, "
        f"{len(invalid_rows)} invalid); "
        f"{len(external_rows)} external run(s); "
        f"{len(figures)} figure(s) written to {figures_dir}"
    )
    return 0
