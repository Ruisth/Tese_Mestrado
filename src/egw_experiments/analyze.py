"""Single reproducible analysis entrypoint (plan 5.8, 7.2, 7.3, 9.1).

``analyze(base_dir, plan_path=None)`` regenerates EVERYTHING under
``results/processed/`` and ``results/figures/`` from ``results/raw/`` alone
("processados e figuras sao sempre regenerados por um unico script", plan
5.8). It never modifies
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
                  clock domain and comes from the run manifest's
                  ``confirmation_deadline_monotonic_ns`` whenever
                  ``confirmation_deadline_clock_domain == "controller"``
                  (sprint P5, report 5.2): the harness reads the
                  controller's confirmation marker (``GET /metrics``
                  ``monotonic_ns``, CONTRACTS 5) immediately after the
                  measured simulator process exits and adds
                  ``confirmation_window_s``, so the deadline is in the same
                  clock domain as the events AND independent of them.
                  Without that marker the deadline can only be derived from
                  the events themselves (max ``received_monotonic_ns`` +
                  window), which is CIRCULAR — a late message pushes its own
                  deadline forward and can never be counted as lost. Such
                  runs are still aggregated but every one of them gets a
                  loud per-run warning naming the run as
                  LEGACY/UNVERIFIABLE. The 60 s window value itself is
                  identical on both paths (plan 7.3); only the end instant
                  stops being inferred from the events. ``per_run.csv``
                  records the path taken in ``confirmation_deadline_source``
                  (``controller-marker``, ``event-derived-legacy``,
                  ``manifest-other-domain-legacy`` or ``none``).
                  Repeated confirmations of
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

HEAD GAP (report 5.4 "Soak ignora o gap inicial", sprint P5):
``sampling_stats`` also reports ``head_gap_s`` — measured-window start to
the FIRST valid in-window sample — exposed per run as
``resources_head_gap_s`` / ``metrics_head_gap_s``. An interior
``max_gap_s`` can never reveal a series that only started sampling hours
into the window, so the head gap is now part of the criteria themselves,
using the SAME documented constants: ``SOAK_MAX_SAMPLING_GAP_S`` for the
soak coverage/cadence criteria and ``MAX_SAMPLE_GAP_S`` for the
saturation sufficiency rule. No new threshold is introduced.

Saturation evidence sufficiency (work order P1b; extended in sprint P5):
a load's verdict is decided ONLY when the planned number of valid runs
exists at that load AND every run carries the required instrumentation:
host-CPU criterion evaluable; resources AND controller-metrics coverage
each >= SATURATION_MIN_RESOURCE_COVERAGE_PCT (the same documented
minimum, now also required of controller_metrics.csv — a load whose
metrics coverage is insufficient is insufficient-evidence, never
"not saturated"); resources and metrics head gaps <= MAX_SAMPLE_GAP_S;
at least MIN_SERIES_DISTINCT_INSTANTS valid distinct sample instants in
each series; controller metrics present for the queue-growth criterion.
Otherwise the load's ``verdict`` in ``saturation.json`` is
``"insufficient-evidence"`` (with per-run detail) — never
``"not-saturated"``. The threshold-crossing logic itself is unchanged
(stop-condition rule: no material change to the statistical criteria
beyond completeness).

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
  IDENTITY-BASED completeness (report 5.4 "Completude por contagem",
  sprint P5): when a campaign plan is supplied (``analyze(plan_path=...)``
  or the ``EGW_CAMPAIGN_PLAN`` environment variable), ``runs_complete``
  compares the exact SET of run identities — ``run_id`` plus
  ``repetition``, ``seed`` and ``rate_msg_s`` — against the plan instead
  of comparing counts; missing, unexpected, duplicated or mismatched
  identities FAIL the criterion and are named in the detail. For
  ``load_sweep`` the comparison is done per rate level. Without a plan
  the legacy count check is kept and the detail states that identity
  checking was NOT performed.
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
  restart via the twin ingestion feature, CONTRACTS 4). RECOVERY EVIDENCE
  (report 5.4 "C12 nao demonstra recuperacao", sprint P5): a hook that
  exited 0 proves a command ran, not that the controller went down and
  came back, so further criteria are computed around the manifest restart
  timestamps (:func:`restart_recovery_evidence`): (a) downtime evidence — a
  controller-metrics sampling gap > MAX_SAMPLE_GAP_S straddling the
  restart (a failed poll writes no row, so holes ARE the unavailability
  evidence) or an accepted-counter reset across it; (b) ENDPOINT recovery —
  the first controller-metrics sample after the restart finished lands
  within ``RESTART_RECOVERY_MAX_S`` (protocol.py, PENDING ADVISOR
  SIGN-OFF); (c) FUNCTIONAL recovery, the readiness criterion; (d) progress
  — the accepted counter grows after the restart. When the series or the
  restart record is missing the criteria FAIL with 'insufficient
  instrumentation', never blank.

  ENDPOINT vs FUNCTIONAL readiness (sprint P5.4). A controller_metrics.csv
  row exists only when ``GET /metrics`` answered, so criterion (b) asserts
  "the HTTP endpoint replied" and says nothing about MQTT/Ditto ingestion;
  it is reported as ``restart_metrics_endpoint_recovery_within_bound`` and
  the per-run column is ``restart_metrics_endpoint_recovery_s`` (named
  ``restart_recovery_s`` before, which invited exactly that confusion).
  Criterion (d) is last-minus-first over ALL post-restart samples and only
  tests > 0, so an acceptance 400 s after the restart passed like one at
  +3 s; it is kept, explicitly, as an UNBOUNDED liveness observation.
  The BOUNDED functional criterion
  ``restart_functional_recovery_within_bound`` is the readiness gate: the
  FIRST evidence that ingestion actually resumed must fall within the same
  ``RESTART_RECOVERY_MAX_S``. That evidence is, preferred when available,
  the first ``accepted`` event of ``events.jsonl`` whose controller-domain
  ``received_monotonic_ns`` follows the restart — the restart instant is
  mapped into the controller's clock domain with the manifest's
  ``controller_marker`` anchor pair (:func:`controller_monotonic_ns_at`) —
  and otherwise the first post-restart controller_metrics sample whose
  ``accepted`` counter exceeds the last pre-restart value (or, when the
  counters reset across the restart, the first post-restart value). Two
  failure modes are reported separately and neither is blank: instrumented
  but NO post-restart evidence of resumed ingestion, and no instrumentation
  at all ('insufficient instrumentation'). ``per_run.csv`` records
  ``restart_functional_recovery_s`` and
  ``restart_functional_recovery_source``.
- ``soak`` (C13) Definition of Done (thresholds in protocol.py, pending
  advisor sign-off): measured window >= 24 h; resources.csv AND
  controller_metrics.csv each cover >= 99% of the measured window with no
  sampling gap > 60 s AND no head gap > 60 s (sprint P5: a series that
  only starts sampling well into the window is not continuous evidence)
  and at least MIN_SERIES_DISTINCT_INSTANTS valid distinct instants; no
  unrecovered interruption (no controller-metrics gap > 120 s and last
  sample within 120 s of the window end); delivery reported descriptively
  per plan 7.3 (no CI, as before).
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

Evidence integrity (report 5.4 "Integridade nao e verificada", sprint P5)
-------------------------------------------------------------------------

Before a run dir is used for anything, its ``SHA256SUMS`` is verified with
the shared ``egw_experiments.checksums`` implementation (never
re-implemented here). ``per_run.csv`` gains an ``integrity_ok`` column:

- ``true``     : sealed and every listed file verifies;
- ``false``    : sealed but the directory does NOT verify (digest
  mismatch, a listed file missing, a malformed line, or a file on disk
  the sums do not list) — an EVIDENCE INTEGRITY FAILURE. The run is
  excluded from summaries, saturation, acceptance and figures with a loud
  warning; it stays listed in ``per_run.csv``;
- ``unsealed`` : no ``SHA256SUMS`` at all, so nothing can be verified.
  Unsealed runs of TIMED conditions (protocol.py TIMED_CONDITION_IDS) are
  likewise excluded from aggregation with a loud warning; unsealed runs
  of other/unknown conditions are only flagged.

External runs (``timings.json``) are verified with the same implementation,
and since sprint P5.4 with the same STRICTNESS: only a run whose seal
VERIFIES (``integrity_ok`` true) may contribute to the duration statistics
(mean/stdev/CI95/median/min/max). An integrity FAILURE and an UNSEALED
directory (no ``SHA256SUMS`` at all, so nothing can be checked) are both
excluded and both get a loud warning; previously only failures were
excluded, so an unsealed external cold_start/twin_creation run entered the
statistics silently. Excluded external runs stay listed in
``external_runs.csv`` with their ``integrity_ok`` flag.

Semantic validation of sampled series (report 5.4 "Validacao superficial")
--------------------------------------------------------------------------

``resources.csv`` and ``controller_metrics.csv`` are read through
:func:`read_resources_csv_validated` /
:func:`read_controller_metrics_csv_validated`, which drop any row that is
not a usable sample and COUNT the reason: ``missing_column``,
``empty_field``, ``unparseable_ts``, ``non_numeric``, ``decreasing_ts``
(time must be non-decreasing in file order) and, for the metrics series,
``no_counters``.

NUMERIC STRICTNESS (sprint P5.4): every numeric field of both series goes
through the shared :func:`parse_series_number`, which additionally rejects
``non_finite`` (``inf``/``nan``) and ``negative`` values for ``cpu_pct``,
``mem_pct``, ``mem_bytes`` and the six controller counters, and
``non_integral`` values for the counters themselves
(``accepted``/``rejected``/``duplicate``/``failed``/``dropped``/
``queue_depth`` are counts of messages). The parse is guarded against
``ValueError``, ``OverflowError`` and ``TypeError``: a ``mem_bytes`` of
``inf`` previously raised an uncaught ``OverflowError`` in
``int(float(...))`` and killed the whole analysis run, an ``inf`` cpu
sample made ``host_cpu_utilization`` infinite and declared host-CPU
saturation on its own, and a ``nan`` made ``max()`` order-dependent and
every threshold comparison False, so saturation could silently never fire.
Rejected values are counted in the SAME drop report as the structural
reasons, so they surface as per-run warnings instead of vanishing. (The
ingest-time counterpart lives in ``egw_experiments.resources`` and
``egw_experiments.controller_metrics``; both sides apply the same rule.)

Drops surface per run in the ``warnings`` column and in
``resources_rows_dropped`` / ``metrics_rows_dropped``. Coverage, cadence
and every sustained-window computation see only the VALID rows, and are
measured over DISTINCT sample instants INSIDE the measured window
(``resources_distinct_instants`` / ``metrics_distinct_instants``): N rows
sharing one timestamp across containers are one instant, not N samples.
A criterion that needs a series with fewer than
``MIN_SERIES_DISTINCT_INSTANTS`` valid instants, or with insufficient
covered duration, FAILS — it never silently passes. (The ingest-time
counterpart lives in ``egw_experiments.resources``.)

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
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .checksums import SUMS_FILENAME, verify_sha256sums
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
    RESTART_RECOVERY_MAX_S,
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
    TIMED_CONDITION_IDS,
)
from .run import DEFAULT_RESULTS_BASE

#: Environment variable consulted by ``analyze()`` when no ``plan_path``
#: keyword argument is supplied. Since sprint P5.4 the shipped
#: ``analyze`` subcommand also carries ``--plan`` (defaulting to the frozen
#: plan, cli.py), so identity checking is the default behaviour; this
#: variable remains the documented fallback for a tree analyzed before the
#: plan exists at the default path.
CAMPAIGN_PLAN_ENV_VAR = "EGW_CAMPAIGN_PLAN"

#: Values of the per-run ``integrity_ok`` column (per_run.csv).
INTEGRITY_OK = "true"
INTEGRITY_FAILED = "false"
INTEGRITY_UNSEALED = "unsealed"

#: Minimum number of VALID DISTINCT sample instants a series must contain
#: before any coverage/cadence claim can be made about it (report 5.4
#: "Validacao superficial"). This is the arithmetic minimum — two instants
#: are needed to measure a single gap — not a tunable threshold, so it
#: needs no advisor sign-off of its own; the substantive thresholds stay
#: the documented protocol.py constants.
MIN_SERIES_DISTINCT_INSTANTS = 2

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


#: Semantic-validation report of one sampled series (report 5.4
#: "Validacao superficial"). ``rows_total`` counts data rows read from the
#: file, ``rows_dropped`` those rejected by the semantic rules,
#: ``distinct_instants`` the number of DISTINCT timestamps among the kept
#: rows (N rows sharing one instant across containers are one instant, not
#: N samples), and ``reasons`` the per-reason drop counts.
def _empty_series_report() -> dict[str, Any]:
    return {
        "rows_total": 0,
        "rows_dropped": 0,
        "distinct_instants": 0,
        "reasons": {},
    }


def _count_drop(report: dict[str, Any], reason: str) -> None:
    report["rows_dropped"] += 1
    report["reasons"][reason] = report["reasons"].get(reason, 0) + 1


def series_report_summary(report: dict[str, Any]) -> str:
    """Human-readable ``reason=count`` listing for the warnings column."""
    return ", ".join(
        f"{reason}={count}" for reason, count in sorted(report["reasons"].items())
    )


#: Drop reasons produced by :func:`parse_series_number` (sprint P5.4). They
#: feed the SAME per-run drop report as the structural reasons, so a
#: rejected value surfaces as a warning instead of vanishing.
NUMERIC_DROP_REASONS = ("non_numeric", "non_finite", "negative", "non_integral")


def parse_series_number(
    raw: Any, *, integral: bool = False
) -> tuple[float | None, str | None]:
    """Strict numeric parser shared by both sampled-series readers.

    Returns ``(value, None)`` for a usable measurement or ``(None, reason)``
    with one of :data:`NUMERIC_DROP_REASONS`. A value is usable only when it

    - parses as a number at all (``non_numeric``; the conversion is guarded
      against ``ValueError``, ``OverflowError`` AND ``TypeError`` — bare
      ``float()``/``int()`` raise all three on the inputs a CSV can carry,
      and an uncaught ``OverflowError`` used to abort the whole analysis);
    - is FINITE (``non_finite``): ``inf``/``nan`` are not measurements.
      ``inf`` propagates through ``fmean``/``max`` and would declare host-CPU
      saturation on its own; ``nan`` makes every threshold comparison False
      and ``max()`` order-dependent, so a saturated run could pass silently.
      Both would also be written verbatim into the aggregate CSVs and read
      back by the plotting path;
    - is NON-NEGATIVE (``negative``): CPU/memory usage and monotonic
      counters cannot be below zero;
    - and, with ``integral`` (the controller counters), is a whole number
      (``non_integral``): ``accepted``/``rejected``/``duplicate``/``failed``/
      ``dropped``/``queue_depth`` are counts of messages, not rates.

    The ingest-side counterpart lives in ``egw_experiments.resources`` /
    ``egw_experiments.controller_metrics``; both sides apply the same rule.
    """
    try:
        value = float(raw)
    except (ValueError, OverflowError, TypeError):
        return None, "non_numeric"
    if not math.isfinite(value):
        return None, "non_finite"
    if value < 0:
        return None, "negative"
    if integral and value != int(value):
        return None, "non_integral"
    return value, None


def read_resources_csv_validated(
    path: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Read resources.csv with SEMANTIC row validation (report 5.4).

    Returns ``({container: [sample, ...]}, report)``. A row is kept only
    when ALL of the following hold; otherwise it is dropped and counted in
    ``report["reasons"]`` (never silently tolerated):

    - ``missing_column``: every required column of the schema is present in
      the row (short/truncated rows are rejected). Required:
      ``ts_utc,container,cpu_pct,mem_bytes,mem_pct``; ``host`` is optional
      (legacy 5-column header, see below).
    - ``empty_field``: none of the required fields is empty.
    - ``unparseable_ts``: ``ts_utc`` parses as RFC 3339.
    - ``non_numeric`` / ``non_finite`` / ``negative``: ``cpu_pct``,
      ``mem_pct`` and ``mem_bytes`` go through :func:`parse_series_number`,
      so each must parse as a number AND be finite AND be non-negative
      (sprint P5.4). ``mem_bytes`` is then truncated to an integer count —
      previously ``int(float(...))`` on an ``inf`` raised an uncaught
      ``OverflowError`` that aborted the whole analysis run.
    - ``decreasing_ts``: within a container, time is non-decreasing in FILE
      order — a row older than the previous kept row of the same container
      cannot be a later sample.

    Header tolerance (documented, work order P1 fix 3): this READER accepts
    BOTH the new 6-column header and the legacy 5-column one WITHOUT
    ``host`` — old fixtures and pre-P1 raw runs must stay analyzable, and
    the ``host`` provenance column does not enter any aggregate. RUN-TIME
    ingestion is the strict side: ``run/collect --resources-from`` accepts
    only the new header (``egw_experiments.resources.validate_resources_csv``).
    """
    required = ("ts_utc", "container", "cpu_pct", "mem_bytes", "mem_pct")
    by_container: dict[str, list[dict[str, Any]]] = {}
    report = _empty_series_report()
    last_ts: dict[str, datetime] = {}
    instants: set[datetime] = set()
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            report["rows_total"] += 1
            if any(row.get(key) is None for key in required):
                _count_drop(report, "missing_column")
                continue
            values = {key: str(row[key]).strip() for key in required}
            if any(not value for value in values.values()):
                _count_drop(report, "empty_field")
                continue
            ts = _parse_ts(values["ts_utc"])
            if ts is None:
                _count_drop(report, "unparseable_ts")
                continue
            numbers: dict[str, float] = {}
            reason: str | None = None
            for key in ("cpu_pct", "mem_pct", "mem_bytes"):
                number, reason = parse_series_number(values[key])
                if reason is not None:
                    break
                numbers[key] = number
            if reason is not None:
                _count_drop(report, reason)
                continue
            cpu_pct = numbers["cpu_pct"]
            mem_pct = numbers["mem_pct"]
            # Truncated only AFTER the value is known finite: int() on an
            # inf raises OverflowError (sprint P5.4).
            mem_bytes = int(numbers["mem_bytes"])
            container = values["container"]
            previous = last_ts.get(container)
            if previous is not None and ts < previous:
                _count_drop(report, "decreasing_ts")
                continue
            last_ts[container] = ts
            instants.add(ts)
            by_container.setdefault(container, []).append(
                {
                    "ts": ts,
                    "cpu_pct": cpu_pct,
                    "mem_bytes": mem_bytes,
                    "mem_pct": mem_pct,
                }
            )
    for samples in by_container.values():
        samples.sort(key=lambda s: s["ts"] or _EPOCH)
    report["distinct_instants"] = len(instants)
    return by_container, report


def read_resources_csv(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Read resources.csv into ``{container: [sample, ...]}`` sorted by time.

    Thin wrapper over :func:`read_resources_csv_validated` for callers that
    do not need the validation report; the semantic rules are identical.
    """
    series, _report = read_resources_csv_validated(path)
    return series


#: Counter columns of controller_metrics.csv (written by
#: ``egw_experiments.controller_metrics.ControllerMetricsSampler``).
CONTROLLER_METRIC_FIELDS = (
    "accepted",
    "rejected",
    "duplicate",
    "failed",
    "dropped",
    "queue_depth",
)


def read_controller_metrics_csv_validated(
    path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read controller_metrics.csv with SEMANTIC row validation (report 5.4).

    Returns ``(samples, report)``; each sample is ``{ts, accepted,
    rejected, duplicate, failed, dropped, queue_depth}``. A row is kept only
    when every schema column is present in the row (``missing_column``),
    ``ts_utc`` is non-empty (``empty_field``) and parses as RFC 3339
    (``unparseable_ts``), time is non-decreasing in FILE order
    (``decreasing_ts``), and every NON-EMPTY counter is a usable counter
    value per :func:`parse_series_number` with ``integral=True``: it parses
    as a number (``non_numeric``), is finite (``non_finite``), is
    non-negative (``negative``) and is a whole number (``non_integral``).
    These six fields are counts of messages (sprint P5.4): 1.5, -3, ``nan``
    and ``inf`` used to be accepted with no check at all and then propagated
    into the aggregates, the reconciliation and the written CSVs. An empty
    counter stays None: the sampler writes "" for a field the controller did
    not report, which degrades that field only. A row whose counters are ALL
    empty carries no measurement and is dropped (``no_counters``).
    """
    samples: list[dict[str, Any]] = []
    report = _empty_series_report()
    previous: datetime | None = None
    instants: set[datetime] = set()
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            report["rows_total"] += 1
            if row.get("ts_utc") is None or any(
                row.get(key) is None for key in CONTROLLER_METRIC_FIELDS
            ):
                _count_drop(report, "missing_column")
                continue
            raw_ts = str(row["ts_utc"]).strip()
            if not raw_ts:
                _count_drop(report, "empty_field")
                continue
            ts = _parse_ts(raw_ts)
            if ts is None:
                _count_drop(report, "unparseable_ts")
                continue
            if previous is not None and ts < previous:
                _count_drop(report, "decreasing_ts")
                continue
            sample: dict[str, Any] = {"ts": ts}
            bad_reason: str | None = None
            for key in CONTROLLER_METRIC_FIELDS:
                raw = str(row[key]).strip()
                if not raw:
                    sample[key] = None
                    continue
                value, bad_reason = parse_series_number(raw, integral=True)
                if bad_reason is not None:
                    break
                sample[key] = value
            if bad_reason is not None:
                _count_drop(report, bad_reason)
                continue
            if all(sample[key] is None for key in CONTROLLER_METRIC_FIELDS):
                _count_drop(report, "no_counters")
                continue
            previous = ts
            instants.add(ts)
            samples.append(sample)
    samples.sort(key=lambda s: s["ts"] or _EPOCH)
    report["distinct_instants"] = len(instants)
    return samples, report


def read_controller_metrics_csv(path: Path) -> list[dict[str, Any]]:
    """Read controller_metrics.csv (1 Hz GET /metrics samples) sorted by time.

    Thin wrapper over :func:`read_controller_metrics_csv_validated` for
    callers that do not need the validation report.
    """
    samples, _report = read_controller_metrics_csv_validated(path)
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

    Returns ``{"coverage_pct", "max_gap_s", "head_gap_s", "tail_gap_s"}``:

    - ``coverage_pct``: percentage of the window covered, where each sample
      covers from its timestamp until the next sample or for ``max_gap_s``
      seconds, whichever is shorter (the last sample covers up to the
      window end, same cap). Time before the first sample is uncovered.
      With nominal 1 Hz sampling and no holes this is 100%.
    - ``max_gap_s``: largest distance between consecutive in-window samples
      (interior gaps only; head/tail truncation is captured by
      ``head_gap_s``/``tail_gap_s``). 0.0 for a single sample.
    - ``head_gap_s``: first in-window sample minus the window start (report
      5.4 "Soak ignora o gap inicial"): a series that only starts sampling
      hours into the window is not continuous evidence, and the interior
      ``max_gap_s`` alone can never show it.
    - ``tail_gap_s``: window end minus the last in-window sample.

    All four are None when ``window`` is None (no measured_window_utc) or
    has zero span. An empty in-window series yields coverage 0.0 with the
    gap fields None (no sample exists to measure a gap from).
    """
    none_stats: dict[str, float | None] = {
        "coverage_pct": None,
        "max_gap_s": None,
        "head_gap_s": None,
        "tail_gap_s": None,
    }
    if window is None:
        return none_stats
    start, end = window
    span = (end - start).total_seconds()
    if span <= 0:
        return none_stats
    ts = sorted({t for t in timestamps if t is not None and start <= t <= end})
    if not ts:
        return {
            "coverage_pct": 0.0,
            "max_gap_s": None,
            "head_gap_s": None,
            "tail_gap_s": None,
        }
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
        "head_gap_s": max(0.0, (ts[0] - start).total_seconds()),
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
    "integrity_ok",
    "resource_source",
    "confirmation_deadline_source",
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
    "resources_head_gap_s",
    "resources_rows_dropped",
    "resources_distinct_instants",
    "resources_per_container_sufficient",
    "metrics_coverage_pct",
    "metrics_max_gap_s",
    "metrics_head_gap_s",
    "metrics_tail_gap_s",
    "metrics_rows_dropped",
    "metrics_distinct_instants",
    "events_accepted_total",
    "metrics_accepted_delta",
    "dropout_disconnects",
    "buffered_dropout",
    "restart_hook_ok",
    "restart_downtime_evidence",
    # ENDPOINT observation (a controller_metrics row exists only when GET
    # /metrics answered), deliberately NOT named 'recovery' on its own.
    "restart_metrics_endpoint_recovery_s",
    # BOUNDED functional readiness: when ingestion itself resumed.
    "restart_functional_recovery_s",
    "restart_functional_recovery_source",
    "restart_accepted_progress",
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
    "coverage_pct",
    "max_gap_s",
    "head_gap_s",
    "tail_gap_s",
    "coverage_sufficient",
]


def check_run_integrity(run_dir: str | Path) -> tuple[str, list[str]]:
    """Verify the run directory's ``SHA256SUMS`` (report 5.4).

    Returns ``(integrity_ok, problems)`` where ``integrity_ok`` is one of:

    - ``"true"``     : SHA256SUMS present and every listed file verifies;
    - ``"false"``    : SHA256SUMS present but the directory does NOT verify
      (digest mismatch, listed file missing, malformed line, or a file on
      disk that the sums do not list) — evidence integrity failure;
    - ``"unsealed"`` : no SHA256SUMS at all (never sealed by
      ``run``/``collect``), so nothing can be verified.

    The verification itself is the shared ``egw_experiments.checksums``
    implementation (the same one ``verify-checksums`` uses); this analysis
    never re-implements it.
    """
    run_dir = Path(run_dir)
    if not (run_dir / SUMS_FILENAME).is_file():
        return INTEGRITY_UNSEALED, []
    problems = verify_sha256sums(run_dir)
    return (INTEGRITY_FAILED if problems else INTEGRITY_OK), problems


#: Fields that make up a run IDENTITY for the completeness check (report
#: 5.4 "Completude por contagem"): counting runs cannot detect a repeated,
#: re-seeded or mis-rated run, so the exact set is compared instead.
RUN_IDENTITY_FIELDS = ("run_id", "repetition", "seed", "rate_msg_s")


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def run_identity(entry: dict[str, Any]) -> tuple[str, int | None, int | None, float | None]:
    """Normalized ``(run_id, repetition, seed, rate_msg_s)`` identity tuple.

    Works for both a campaign-plan entry and a per-run row: both carry the
    same field names (plan_gen._run_entry / the run manifest).
    """
    return (
        str(entry.get("run_id")),
        _as_int(entry.get("repetition")),
        _as_int(entry.get("seed")),
        _as_float(entry.get("rate_msg_s")),
    )


def load_campaign_plan_for_analysis(
    plan_path: str | Path | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load the campaign plan used for identity-based completeness.

    ``plan_path`` None falls back to the ``EGW_CAMPAIGN_PLAN`` environment
    variable (``CAMPAIGN_PLAN_ENV_VAR``), so identity checking is usable
    whether or not the CLI passes a flag. Returns ``(plan, problem)``: a
    problem string (never an exception) when the path is set but the file
    is missing, unreadable or has no ``runs`` list — analysis must degrade
    to the legacy count check with a warning, never crash.
    """
    source = plan_path if plan_path is not None else os.environ.get(
        CAMPAIGN_PLAN_ENV_VAR
    )
    if not source:
        return None, None
    path = Path(source)
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"campaign plan {path} could not be read: {exc}"
    if not isinstance(plan, dict) or not isinstance(plan.get("runs"), list):
        return None, f"campaign plan {path} has no 'runs' list"
    return plan, None


def plan_identities_by_condition(
    plan: dict[str, Any] | None
) -> dict[str, list[tuple[str, int | None, int | None, float | None]]]:
    """Planned run identities per condition id (simulator runs only).

    External conditions are operator-measured and are not evaluated by
    :func:`evaluate_acceptance`, so they are skipped here too.
    """
    out: dict[str, list[tuple[str, int | None, int | None, float | None]]] = {}
    if not plan:
        return out
    for entry in plan.get("runs", []):
        if not isinstance(entry, dict):
            continue
        cid = entry.get("condition_id")
        if not isinstance(cid, str):
            continue
        condition = CONDITIONS_BY_ID.get(cid)
        if condition is not None and condition.runner != "simulator":
            continue
        out.setdefault(cid, []).append(run_identity(entry))
    return out


def compare_run_identities(
    expected: list[tuple[str, int | None, int | None, float | None]],
    observed: list[tuple[str, int | None, int | None, float | None]],
) -> tuple[bool, str]:
    """Compare the SET of run identities against the plan (report 5.4).

    Returns ``(ok, detail)``. The comparison is exact: a run is accounted
    for only when its ``run_id`` is planned AND its ``repetition``,
    ``seed`` and ``rate_msg_s`` match the plan. Duplicated, missing,
    unexpected and mismatched identities are all failures and every
    offending id is named in ``detail`` (never just a count).
    """
    expected_by_id = {ident[0]: ident for ident in expected}
    observed_by_id: dict[str, list[tuple[Any, ...]]] = {}
    for ident in observed:
        observed_by_id.setdefault(ident[0], []).append(ident)

    duplicated = sorted(rid for rid, items in observed_by_id.items() if len(items) > 1)
    missing = sorted(set(expected_by_id) - set(observed_by_id))
    unexpected = sorted(set(observed_by_id) - set(expected_by_id))
    mismatched: list[str] = []
    for rid in sorted(set(expected_by_id) & set(observed_by_id)):
        want = expected_by_id[rid]
        got = observed_by_id[rid][0]
        diffs = [
            f"{field}={got[i]!r} (plan {want[i]!r})"
            for i, field in enumerate(RUN_IDENTITY_FIELDS)
            if i > 0 and got[i] != want[i]
        ]
        if diffs:
            mismatched.append(f"{rid}: " + ", ".join(diffs))

    problems: list[str] = []
    if missing:
        problems.append(f"missing {', '.join(missing)}")
    if unexpected:
        problems.append(f"unexpected {', '.join(unexpected)}")
    if duplicated:
        problems.append(f"duplicated {', '.join(duplicated)}")
    if mismatched:
        problems.append("mismatched " + "; ".join(mismatched))
    if problems:
        return False, "identity mismatch vs campaign plan: " + "; ".join(problems)
    return True, f"{len(observed)}/{len(expected)} planned run identities matched"


def compare_run_identities_per_rate(
    expected: list[tuple[str, int | None, int | None, float | None]],
    observed: list[tuple[str, int | None, int | None, float | None]],
) -> tuple[bool, str]:
    """Per-rate identity comparison, used for ``load_sweep`` (report 5.4).

    The sweep's completeness is meaningful only per load level: ten runs
    at 10 msg/s and none at 250 msg/s must never look complete.
    """
    rates = sorted(
        {ident[3] for ident in expected} | {ident[3] for ident in observed},
        key=lambda r: (r is None, r),
    )
    ok = True
    details: list[str] = []
    for rate in rates:
        rate_expected = [i for i in expected if i[3] == rate]
        rate_observed = [i for i in observed if i[3] == rate]
        rate_ok, detail = compare_run_identities(rate_expected, rate_observed)
        ok = ok and rate_ok
        label = "rate n/a" if rate is None else f"rate {rate:g} msg/s"
        details.append(f"{label}: {detail}")
    return ok, " | ".join(details) if details else "no planned rates"


def controller_monotonic_ns_at(
    controller_marker: Any, wall: datetime
) -> int | None:
    """Map a harness wall-clock instant into the CONTROLLER's clock domain.

    The manifest's ``controller_marker`` (run.py, sprint P5) is an anchor
    PAIR read from a single ``GET /metrics``: the controller's own
    ``monotonic_ns`` and its own ``wall_utc`` at that same instant. With it,
    a wall-clock instant such as the restart's ``finished_utc`` can be
    expressed in the controller's monotonic domain, which is the only domain
    ``events.jsonl`` timestamps live in::

        controller_ns(wall) = marker.monotonic_ns
                              + (wall - marker.wall_utc) * 1e9

    Returns None whenever the anchor is absent or unusable — the caller then
    has no bridge and must fall back to the counter series.

    Documented assumptions (same ones the confirmation-deadline marker
    already makes, plan 5.1 / report 5.2): (1) the harness host and the SUT
    are NTP-synchronized, which is the accepted precision for placing 1 Hz
    samples and a wall-clock restart instant — never for latency; (2) the
    controller's monotonic clock is boot-relative, so it survives a
    container/process restart within the run.
    """
    if not isinstance(controller_marker, dict) or not controller_marker.get("ok"):
        return None
    monotonic_ns = controller_marker.get("monotonic_ns")
    if isinstance(monotonic_ns, bool) or not isinstance(monotonic_ns, (int, float)):
        return None
    anchor = _parse_ts(str(controller_marker.get("wall_utc") or ""))
    if anchor is None:
        return None
    return int(monotonic_ns + (wall - anchor).total_seconds() * 1_000_000_000)


def restart_recovery_evidence(
    restart_record: Any,
    metric_samples: list[dict[str, Any]],
    max_gap_s: float = MAX_SAMPLE_GAP_S,
    *,
    events: list[dict[str, Any]] | None = None,
    controller_marker: Any = None,
) -> dict[str, Any]:
    """Evidence that the controller really went down and came back (C12).

    Report 5.4 ("C12 nao demonstra recuperacao"): a restart hook that
    returned 0 proves a command ran, not that the controller was
    interrupted and recovered. This computes, from the manifest restart
    record (``started_utc``/``finished_utc``), the controller_metrics.csv
    samples and the run's ``events.jsonl``:

    - ``downtime_evidence``: True when the series shows either a sampling
      gap longer than ``max_gap_s`` straddling the restart (a failed poll
      writes NO row, so holes are the unavailability evidence,
      controller_metrics.py) or a counter reset (the first ``accepted``
      value after the restart is lower than the last one before it);
    - ``metrics_endpoint_recovery_s``: seconds from ``finished_utc`` to the
      first controller_metrics sample after it. A row exists only when
      ``GET /metrics`` answered, so this observes THE HTTP ENDPOINT coming
      back — NOT functional readiness. It was called ``recovery_s`` until
      sprint P5.4, which is exactly the confusion the rename removes: an
      endpoint that replies says nothing about MQTT/Ditto ingestion;
    - ``functional_recovery_s`` / ``functional_recovery_source``: the
      BOUNDED functional criterion (sprint P5.4) — seconds from
      ``finished_utc`` to the FIRST evidence that ingestion actually
      resumed, and which instrumentation produced it:

      * ``"events-accepted-monotonic"`` (PREFERRED, used whenever
        available): the first ``accepted`` event of ``events.jsonl`` whose
        controller-domain ``received_monotonic_ns`` follows the restart. It
        needs the manifest's ``controller_marker`` to place the restart in
        the controller's clock domain (:func:`controller_monotonic_ns_at`);
      * ``"metrics-accepted-counter"``: the first post-restart sample whose
        ``accepted`` counter EXCEEDS the last pre-restart value. When the
        counters reset across the restart (a restarted controller starts at
        zero) the first post-restart value is the baseline instead, since
        the pre-restart total is no longer comparable;
      * ``None``: neither instrumentation existed — insufficient
        instrumentation.

      ``functional_recovery_s`` is None when the chosen source found NO
      post-restart evidence of resumed ingestion. That is a FAILURE of the
      criterion, distinct from (and reported apart from) missing
      instrumentation; neither is ever blank;
    - ``accepted_progress``: ``accepted`` delta over the samples after the
      restart (None when unmeasurable). It is an UNBOUNDED liveness
      observation only — an acceptance 400 s after the restart moves it just
      like one at +3 s — which is why the bounded functional criterion above
      exists.

    Every field is None when the restart record is unusable, and every
    metrics-derived field is None when the series is missing: the C12
    criteria then fail as 'insufficient instrumentation', never blank.
    """
    unknown: dict[str, Any] = {
        "downtime_evidence": None,
        "metrics_endpoint_recovery_s": None,
        "accepted_progress": None,
        "functional_recovery_s": None,
        "functional_recovery_source": None,
    }
    if not isinstance(restart_record, dict):
        return unknown
    started = _parse_ts(str(restart_record.get("started_utc") or ""))
    finished = _parse_ts(str(restart_record.get("finished_utc") or ""))
    if started is None or finished is None:
        return unknown

    evidence = dict(unknown)
    evidence.update(
        _functional_recovery_from_events(events, controller_marker, finished)
    )

    ordered = [s for s in metric_samples if s.get("ts") is not None]
    if not ordered:
        return evidence

    before = [s for s in ordered if s["ts"] <= started]
    after = [s for s in ordered if s["ts"] >= finished]

    gap_evidence = False
    for previous, current in zip(ordered, ordered[1:]):
        # A pair straddling the restart interval: the earlier sample starts
        # no later than the restart ended and the later one lands no
        # earlier than the restart began.
        if previous["ts"] <= finished and current["ts"] >= started:
            if (current["ts"] - previous["ts"]).total_seconds() > max_gap_s:
                gap_evidence = True
                break

    reset_evidence = False
    before_accepted = [s["accepted"] for s in before if s.get("accepted") is not None]
    after_accepted = [s["accepted"] for s in after if s.get("accepted") is not None]
    if before_accepted and after_accepted:
        reset_evidence = float(after_accepted[0]) < float(before_accepted[-1])

    if after:
        evidence["metrics_endpoint_recovery_s"] = max(
            0.0, (after[0]["ts"] - finished).total_seconds()
        )

    if len(after_accepted) >= 2:
        evidence["accepted_progress"] = float(after_accepted[-1]) - float(
            after_accepted[0]
        )

    evidence["downtime_evidence"] = bool(gap_evidence or reset_evidence)

    if evidence["functional_recovery_source"] is None and after_accepted:
        # Counter baseline: the last pre-restart total, unless the counters
        # reset across the restart (then that total is not comparable and
        # the controller's own restarted count is the baseline).
        baseline = float(after_accepted[0])
        if before_accepted and float(before_accepted[-1]) <= baseline:
            baseline = float(before_accepted[-1])
        evidence["functional_recovery_source"] = "metrics-accepted-counter"
        for sample in after:
            value = sample.get("accepted")
            if value is not None and float(value) > baseline:
                evidence["functional_recovery_s"] = max(
                    0.0, (sample["ts"] - finished).total_seconds()
                )
                break

    return evidence


def _functional_recovery_from_events(
    events: list[dict[str, Any]] | None,
    controller_marker: Any,
    finished: datetime,
) -> dict[str, Any]:
    """First accepted event after the restart, in the controller's domain.

    The PREFERRED functional-recovery evidence (sprint P5.4): an ``accepted``
    event proves a message went all the way through MQTT ingestion to a
    Ditto patch, and its ``received_monotonic_ns`` is already in the
    controller's clock domain. Returns ``{}`` when the bridge or the events
    are missing, so the caller falls back to the counter series.
    """
    if not events:
        return {}
    finished_ns = controller_monotonic_ns_at(controller_marker, finished)
    if finished_ns is None:
        return {}
    received = sorted(
        int(ev["received_monotonic_ns"])
        for ev in events
        if ev.get("outcome") == "accepted"
        and isinstance(ev.get("received_monotonic_ns"), (int, float))
        and not isinstance(ev.get("received_monotonic_ns"), bool)
    )
    if not received:
        return {}
    after = [ns for ns in received if ns >= finished_ns]
    return {
        "functional_recovery_source": "events-accepted-monotonic",
        "functional_recovery_s": (
            max(0.0, (after[0] - finished_ns) / 1_000_000_000) if after else None
        ),
    }


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

    # --- evidence integrity (report 5.4) ----------------------------------
    # Verified BEFORE any file of the run is used. A failure does not stop
    # the row from being computed (per_run.csv must keep listing the run),
    # but analyze() removes such runs from every aggregate.
    integrity_ok, integrity_problems = check_run_integrity(run_dir)
    if integrity_ok == INTEGRITY_FAILED:
        warnings.append(
            "evidence integrity failure: "
            f"{SUMS_FILENAME} does not verify ({'; '.join(integrity_problems)}); "
            "the run is excluded from every aggregate (report 5.4)"
        )
    elif integrity_ok == INTEGRITY_UNSEALED:
        warnings.append(
            f"evidence integrity unverifiable: no {SUMS_FILENAME} in the run "
            "directory (never sealed by run/collect), so nothing can be "
            "checked (report 5.4)"
        )

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
    # AUTHORITATIVE PATH (report 5.2, sprint P5): when the manifest carries
    # confirmation_deadline_clock_domain == 'controller', the deadline was
    # anchored on the controller's own confirmation marker (GET /metrics
    # monotonic_ns, read right after the measured simulator process exited
    # and before the confirmation wait). That value is in the same clock
    # domain as the events AND is independent of them, so it is used
    # verbatim.
    #
    # LEGACY FALLBACK: without that marker the deadline can only be derived
    # from the events themselves — max received_monotonic_ns plus
    # confirmation_window_s — which is CIRCULAR: a message received late
    # pushes its own deadline forward and can never be counted as lost. Such
    # runs are aggregated but loudly flagged as legacy/unverifiable.
    # The 60 s window itself is unchanged in both paths (plan 7.3).
    manifest_deadline_ns = manifest.get("confirmation_deadline_monotonic_ns")
    clock_domain = manifest.get("confirmation_deadline_clock_domain")
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
    deadline_source = "none"
    controller_deadline = (
        clock_domain == "controller"
        and isinstance(manifest_deadline_ns, (int, float))
        and not isinstance(manifest_deadline_ns, bool)
    )
    if controller_deadline:
        deadline_ns = int(manifest_deadline_ns)
        deadline_source = "controller-marker"
        # Plausibility guard (kept from v1.1, adapted): the marker is read
        # AFTER the measured process exits, so deadline = marker + window
        # can never precede the last event the controller received. If it
        # does, the manifest is mislabelled (a foreign clock domain) — say
        # so loudly instead of silently counting everything lost.
        if received_values and deadline_ns < int(max(received_values)):
            warnings.append(
                f"IMPLAUSIBLE controller confirmation marker for run {run_id}: "
                f"the manifest deadline ({deadline_ns}) precedes the last "
                f"received_monotonic_ns ({int(max(received_values))}) although "
                "it claims clock_domain 'controller'; the deadline is used as "
                "recorded but the run's clock domain is suspect (report 5.2)"
            )
    elif received_values:
        max_received_ns = int(max(received_values))
        deadline_ns = max_received_ns + window_ns
        deadline_source = "event-derived-legacy"
        warnings.append(
            f"LEGACY/UNVERIFIABLE confirmation deadline for run {run_id}: "
            "the manifest has no controller-domain confirmation marker "
            f"(confirmation_deadline_clock_domain={clock_domain!r}), so the "
            "deadline was derived from the run's own events "
            "(max received_monotonic_ns + confirmation window). That rule "
            "is circular — a late message extends its own deadline and can "
            "never be counted as lost; delivery for this run is not "
            "verifiable evidence (report 5.2)"
        )
    elif isinstance(manifest_deadline_ns, (int, float)) and not isinstance(
        manifest_deadline_ns, bool
    ):
        deadline_ns = int(manifest_deadline_ns)
        deadline_source = "manifest-other-domain-legacy"
        warnings.append(
            f"LEGACY/UNVERIFIABLE confirmation deadline for run {run_id}: no "
            "controller events with received_monotonic_ns; falling back to "
            "the manifest confirmation_deadline_monotonic_ns whose "
            f"clock_domain is {clock_domain!r}, not 'controller' (monotonic "
            "clocks are not comparable across hosts, plan 5.1)"
        )
    else:
        deadline_source = "none"
        warnings.append(
            f"LEGACY/UNVERIFIABLE confirmation deadline for run {run_id}: no "
            "confirmation deadline available (no controller marker, no "
            "controller events and no manifest deadline); all confirmations "
            "in events.jsonl counted as in-window"
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
        "coverage_pct": None,
        "max_gap_s": None,
        "head_gap_s": None,
        "tail_gap_s": None,
    }
    metrics_stats: dict[str, float | None] = dict(res_stats)
    # Semantic-validation reports of the two sampled series (report 5.4)
    # and their count of VALID DISTINCT in-window sample instants.
    res_report = _empty_series_report()
    metrics_report = _empty_series_report()
    resources_distinct_instants = 0
    resources_per_container_sufficient: bool | None = None
    metrics_distinct_instants = 0
    resources_path = run_dir / "resources.csv"
    if resources_path.is_file():
        by_container_all, res_report = read_resources_csv_validated(resources_path)
        if res_report["rows_dropped"]:
            warnings.append(
                f"resources.csv: {res_report['rows_dropped']}/"
                f"{res_report['rows_total']} row(s) dropped by semantic "
                f"validation ({series_report_summary(res_report)})"
            )
        by_container = {
            container: filter_samples_to_window(samples, window)
            for container, samples in by_container_all.items()
        }
        # DISTINCT valid instants inside the measured window: N container
        # rows sharing one timestamp are one sample instant, not N
        # (report 5.4). Coverage and cadence are computed on this set.
        res_instants = sorted(
            {
                s["ts"]
                for samples in by_container.values()
                for s in samples
                if s.get("ts") is not None
            }
        )
        resources_distinct_instants = len(res_instants)
        res_stats = sampling_stats(res_instants, window)
        container_sufficiency: list[bool] = []
        for container in sorted(by_container):
            samples = by_container[container]
            container_instants = sorted(
                {s["ts"] for s in samples if s.get("ts") is not None}
            )
            container_stats = sampling_stats(container_instants, window)
            container_coverage = container_stats["coverage_pct"]
            container_gap = container_stats["max_gap_s"]
            container_head_gap = container_stats["head_gap_s"]
            container_tail_gap = container_stats["tail_gap_s"]
            container_sufficient = (
                window is not None
                and container_coverage is not None
                and container_coverage
                >= SATURATION_MIN_RESOURCE_COVERAGE_PCT
                and len(container_instants) >= MIN_SERIES_DISTINCT_INSTANTS
                and (container_gap is None or container_gap <= MAX_SAMPLE_GAP_S)
                and (
                    container_head_gap is None
                    or container_head_gap <= MAX_SAMPLE_GAP_S
                )
                and (
                    container_tail_gap is None
                    or container_tail_gap <= MAX_SAMPLE_GAP_S
                )
            )
            container_sufficiency.append(container_sufficient)
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
                    "coverage_pct": container_coverage,
                    "max_gap_s": container_gap,
                    "head_gap_s": container_head_gap,
                    "tail_gap_s": container_tail_gap,
                    "coverage_sufficient": container_sufficient,
                }
            )
            if not container_sufficient:
                warnings.append(
                    f"resources.csv container {container!r} has insufficient "
                    "measured-window coverage/cadence; its per-container "
                    "resource aggregates are not admissible evidence"
                )
            resource_samples += len(samples)
            if cpus:
                cpu_max_overall = max(cpu_max_overall or 0.0, max(cpus))
            if mems:
                mem_max_overall = max(mem_max_overall or 0, max(mems))
            cpu_sustained_max = max(cpu_sustained_max, sustained)
        resources_per_container_sufficient = bool(container_sufficiency) and all(
            container_sufficiency
        )
        # Host-level CPU normalization (audit 9.7): needs the SUT's nproc
        # from sut_environment.json. The values remain visible for audit even
        # when a container series is sparse, but the propagated sufficiency
        # flag prevents saturation/claims from consuming that run.
        if nproc:
            series = host_cpu_series(by_container, nproc)
            if series:
                host_util_max = max(p["host_cpu_utilization"] for p in series)
                host_sustained = host_cpu_sustained_seconds(series)
            if resources_per_container_sufficient is False:
                warnings.append(
                    "host-level CPU aggregates are audit-only because at "
                    "least one container has insufficient measured-window "
                    "sampling"
                )
        elif container_sufficiency:
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
    metric_samples: list[dict[str, Any]] = []
    metrics_path = run_dir / "controller_metrics.csv"
    if metrics_path.is_file():
        all_metric_samples, metrics_report = read_controller_metrics_csv_validated(
            metrics_path
        )
        if metrics_report["rows_dropped"]:
            warnings.append(
                f"controller_metrics.csv: {metrics_report['rows_dropped']}/"
                f"{metrics_report['rows_total']} row(s) dropped by semantic "
                f"validation ({series_report_summary(metrics_report)})"
            )
        metric_samples = filter_samples_to_window(all_metric_samples, window)
        controller_metric_samples = len(metric_samples)
        depths = [
            s["queue_depth"] for s in metric_samples if s["queue_depth"] is not None
        ]
        if depths:
            queue_depth_max = max(depths)
        queue_growth_sustained = queue_growth_sustained_seconds(metric_samples)
        metrics_instants = sorted(
            {s["ts"] for s in metric_samples if s.get("ts") is not None}
        )
        metrics_distinct_instants = len(metrics_instants)
        metrics_stats = sampling_stats(metrics_instants, window)
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

    # Recovery evidence (report 5.4, claim C12): computed from the
    # controller_metrics.csv samples around the manifest restart timestamps.
    # The same window-filtered, semantically validated series every other
    # criterion uses — the restart is triggered inside the measured window
    # (--restart-at-s), so the downtime hole and the resumption both fall
    # inside it, and a hole is evidence precisely because no row exists.
    # Sprint P5.4: the run's events and the manifest's controller marker are
    # passed in too, so functional readiness (when ingestion resumed) can be
    # read from the controller's own clock domain when that anchor exists.
    recovery = restart_recovery_evidence(
        restart_record,
        metric_samples,
        events=events,
        controller_marker=manifest.get("controller_marker"),
    )
    if (
        manifest.get("condition_id") == "controller_restart"
        and recovery["downtime_evidence"] is None
    ):
        warnings.append(
            "controller_restart run without usable recovery evidence "
            "(restart timestamps and/or controller_metrics.csv samples "
            "missing): the C12 recovery criteria fail as 'insufficient "
            "instrumentation' for this run (report 5.4)"
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
        "integrity_ok": integrity_ok,
        "resource_source": resource_source,
        "confirmation_deadline_source": deadline_source,
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
        "resources_head_gap_s": res_stats["head_gap_s"],
        "resources_rows_dropped": res_report["rows_dropped"],
        "resources_distinct_instants": resources_distinct_instants,
        "resources_per_container_sufficient": resources_per_container_sufficient,
        "metrics_coverage_pct": metrics_stats["coverage_pct"],
        "metrics_max_gap_s": metrics_stats["max_gap_s"],
        "metrics_head_gap_s": metrics_stats["head_gap_s"],
        "metrics_tail_gap_s": metrics_stats["tail_gap_s"],
        "metrics_rows_dropped": metrics_report["rows_dropped"],
        "metrics_distinct_instants": metrics_distinct_instants,
        "events_accepted_total": events_accepted_total,
        "metrics_accepted_delta": metrics_accepted_delta,
        "dropout_disconnects": dropout_disconnects,
        "buffered_dropout": buffered_dropout,
        "restart_hook_ok": restart_hook_ok,
        "restart_downtime_evidence": recovery["downtime_evidence"],
        "restart_metrics_endpoint_recovery_s": recovery[
            "metrics_endpoint_recovery_s"
        ],
        "restart_functional_recovery_s": recovery["functional_recovery_s"],
        "restart_functional_recovery_source": recovery[
            "functional_recovery_source"
        ],
        "restart_accepted_progress": recovery["accepted_progress"],
        "warnings": " | ".join(warnings),
        "_resources": resources_rows,
    }


# ---------------------------------------------------------------------------
# External runs (audit 9.6, claim C15)
# ---------------------------------------------------------------------------

EXTERNAL_RUNS_COLUMNS = [
    "run_id",
    "condition_id",
    "integrity_ok",
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

    Returns ``{run_id, condition_id, integrity_ok, excluded, sample_rows,
    duration_mean_s}`` or None when timings.json is absent/unreadable
    (notice on stderr). ``duration_mean_s`` is the per-run value used as
    the unit of analysis (mean of the run's samples; normally one sample
    per run).

    ``integrity_ok`` is the SHA256SUMS verdict of the run directory
    (report 5.4); only a run with a VERIFIED seal (``INTEGRITY_OK``) feeds
    :func:`summarize_external_durations` — both an integrity FAILURE and an
    UNSEALED directory get a loud stderr warning here and are dropped from
    the duration statistics (sprint P5.4), while staying listed with their
    flag in ``external_runs.csv``.
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
    integrity_ok, integrity_problems = check_run_integrity(run_dir)
    if integrity_ok == INTEGRITY_FAILED:
        print(
            f"[analyze] evidence integrity failure in external run {run_id}: "
            f"{'; '.join(integrity_problems)}; excluded from the duration "
            "statistics (report 5.4)",
            file=sys.stderr,
        )
    elif integrity_ok == INTEGRITY_UNSEALED:
        # Sprint P5.4: an unsealed external run was never sealed by
        # run/collect, so NOTHING about it can be verified. It used to enter
        # the duration statistics silently; it is now excluded and said so
        # as loudly as an outright failure.
        print(
            f"[analyze] evidence integrity unverifiable in external run "
            f"{run_id}: no {SUMS_FILENAME} in the run directory (never sealed "
            "by run/collect), so its duration is excluded from the duration "
            "statistics (report 5.4)",
            file=sys.stderr,
        )
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
                "integrity_ok": integrity_ok,
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
        "integrity_ok": integrity_ok,
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

    Evidence integrity (report 5.4, tightened in sprint P5.4): contributing
    to a mean/stdev/CI95 requires a VERIFIED seal — ``integrity_ok`` must be
    ``INTEGRITY_OK``. A directory that does not verify (``INTEGRITY_FAILED``)
    and one that was never sealed at all (``INTEGRITY_UNSEALED``, no
    SHA256SUMS, so nothing can be checked) are BOTH excluded; the earlier
    rule excluded only the former, letting an unverifiable external run set
    the statistics. Excluded runs stay listed in ``external_runs.csv`` with
    their flag.
    """
    out: list[dict[str, Any]] = []
    for condition_id in EXTERNAL_DURATION_CONDITIONS:
        values = [
            float(r["duration_mean_s"])
            for r in external_rows
            if r.get("condition_id") == condition_id
            and not r.get("excluded")
            and r.get("integrity_ok") == INTEGRITY_OK
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


def evaluate_acceptance(
    rows: list[dict[str, Any]], plan: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Acceptance evaluation for ALL planned simulator conditions.

    ``rows`` are the INCLUDED per-run rows (valid, non-excluded); a
    defensive re-filter is applied anyway. The function iterates over the
    protocol's planned simulator conditions — NOT over the conditions found
    in raw/ — so a planned condition with zero runs still yields FAILED
    rows (work order P1b): ``passed`` is None ONLY for the explicitly
    informational/descriptive criteria.

    Completeness gate: each condition gets a ``runs_complete`` row and
    every substantive criterion is gated on it (passed False whenever the
    condition is incomplete, with the detail in the observed column).

    With ``plan`` (a loaded ``campaign_plan.json``) completeness is
    IDENTITY-based (report 5.4): the exact set of ``run_id`` +
    ``repetition`` + ``seed`` + ``rate_msg_s`` is compared against the
    plan — per rate level for ``load_sweep`` — and missing, unexpected,
    duplicated or mismatched identities fail the criterion, naming the
    offending ids. Without a plan the legacy count check (n_valid ==
    planned repetitions; repetitions x rates for the sweep) is kept and
    the detail states that identity checking was not performed.
    """
    plan_identities = plan_identities_by_condition(plan)
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

        # Identity-based completeness (report 5.4): the SET of run
        # identities decides, not the count. A duplicated or re-seeded run
        # keeps the count right while the campaign is wrong.
        identity_detail = (
            "identity checking NOT performed (no campaign plan supplied; pass "
            f"analyze(plan_path=...) or set {CAMPAIGN_PLAN_ENV_VAR})"
        )
        if plan is not None:
            planned = plan_identities.get(cid, [])
            observed_identities = [run_identity(r) for r in valid]
            if condition.rates_msg_s:
                identity_ok, identity_detail = compare_run_identities_per_rate(
                    planned, observed_identities
                )
            else:
                identity_ok, identity_detail = compare_run_identities(
                    planned, observed_identities
                )
            if len(planned) != expected:
                identity_ok = False
                identity_detail += (
                    f"; the campaign plan lists {len(planned)} run(s) for this "
                    f"condition, the frozen protocol plans {expected}"
                )
            complete = identity_ok
            if not identity_ok:
                note += "; run identities do not match the campaign plan"

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
        observed = f"{n_valid}/{expected} valid runs"
        if not_counted:
            observed += f" ({not_counted} excluded/invalid run(s) not counted)"
        observed += f"; {identity_detail}"
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

            # RECOVERY EVIDENCE (report 5.4): the hook exiting 0 proves a
            # command ran, not that the controller went down and came
            # back. All three criteria are computed from
            # controller_metrics.csv around the manifest restart
            # timestamps; a run without that instrumentation FAILS with
            # 'insufficient instrumentation', never blank.
            def _uninstrumented(key: str) -> int:
                return count_ok(lambda r, k=key: r.get(k) is None)

            downtime_ok = count_ok(
                lambda r: r.get("restart_downtime_evidence") is True
            )
            missing = _uninstrumented("restart_downtime_evidence")
            observed = (
                f"{downtime_ok}/{n_valid} run(s) with controller downtime "
                f"evidence (metrics gap > {MAX_SAMPLE_GAP_S:g} s straddling "
                "the restart, or an accepted-counter reset across it)"
            )
            if missing:
                observed += (
                    f"; insufficient instrumentation in {missing} run(s) "
                    "(restart timestamps and/or controller_metrics.csv "
                    "missing)"
                )
            passed, observed = gate(downtime_ok == n_valid, observed)
            add("restart_downtime_evidence_every_run", observed, passed)

            # ENDPOINT observation: a controller_metrics row exists only
            # when GET /metrics answered, so this says the HTTP endpoint
            # replied again — nothing about MQTT/Ditto ingestion. Kept
            # (it is real evidence of the process being back up) but named
            # so it can no longer be read as readiness (sprint P5.4).
            recovered_ok = count_ok(
                lambda r: r.get("restart_metrics_endpoint_recovery_s") is not None
                and float(r["restart_metrics_endpoint_recovery_s"])
                <= RESTART_RECOVERY_MAX_S
            )
            missing = _uninstrumented("restart_metrics_endpoint_recovery_s")
            observed = (
                f"{recovered_ok}/{n_valid} run(s) with the controller "
                f"/metrics endpoint answering again within "
                f"{RESTART_RECOVERY_MAX_S:g} s of the restart finishing "
                "(endpoint availability only, NOT functional readiness; "
                "PENDING ADVISOR SIGN-OFF, protocol.py "
                "RESTART_RECOVERY_MAX_S)"
            )
            if missing:
                observed += (
                    f"; insufficient instrumentation in {missing} run(s) "
                    "(no controller-metrics sample after the restart)"
                )
            passed, observed = gate(recovered_ok == n_valid, observed)
            add("restart_metrics_endpoint_recovery_within_bound", observed, passed)

            # BOUNDED FUNCTIONAL readiness (sprint P5.4): the first evidence
            # that ingestion actually resumed — an accepted event in the
            # controller's own clock domain when the manifest carries the
            # marker, otherwise the first post-restart sample whose accepted
            # counter exceeds the pre-restart baseline — must fall within
            # the SAME documented bound. Two distinct failure modes are
            # reported separately and neither is ever blank: no post-restart
            # evidence at all, and no instrumentation to look at.
            functional_ok = count_ok(
                lambda r: r.get("restart_functional_recovery_s") is not None
                and float(r["restart_functional_recovery_s"])
                <= RESTART_RECOVERY_MAX_S
            )
            missing = _uninstrumented("restart_functional_recovery_source")
            no_evidence = count_ok(
                lambda r: r.get("restart_functional_recovery_source") is not None
                and r.get("restart_functional_recovery_s") is None
            )
            observed = (
                f"{functional_ok}/{n_valid} run(s) with ingestion shown to "
                f"resume within {RESTART_RECOVERY_MAX_S:g} s of the restart "
                "finishing (first accepted event in the controller clock "
                "domain, or the first post-restart accepted-counter growth; "
                "PENDING ADVISOR SIGN-OFF, protocol.py "
                "RESTART_RECOVERY_MAX_S)"
            )
            if no_evidence:
                observed += (
                    f"; no post-restart evidence of resumed ingestion in "
                    f"{no_evidence} run(s)"
                )
            if missing:
                observed += (
                    f"; insufficient instrumentation in {missing} run(s) "
                    "(no accepted events with a controller-domain anchor and "
                    "no post-restart accepted counter)"
                )
            passed, observed = gate(functional_ok == n_valid, observed)
            add("restart_functional_recovery_within_bound", observed, passed)

            # UNBOUNDED liveness observation: the counter moved at some
            # point after the restart. Deliberately kept as a separate,
            # weaker check — the bound lives in the functional criterion
            # above (sprint P5.4).
            progress_ok = count_ok(
                lambda r: r.get("restart_accepted_progress") is not None
                and float(r["restart_accepted_progress"]) > 0
            )
            missing = _uninstrumented("restart_accepted_progress")
            observed = (
                f"{progress_ok}/{n_valid} run(s) with accepted-counter "
                "progress after the restart (unbounded in time; the bound is "
                "restart_functional_recovery_within_bound)"
            )
            if missing:
                observed += (
                    f"; insufficient instrumentation in {missing} run(s) "
                    "(fewer than two controller-metrics samples carrying "
                    "'accepted' after the restart)"
                )
            passed, observed = gate(progress_ok == n_valid, observed)
            add("restart_accepted_progress_after", observed, passed)

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

            # Coverage AND cadence AND head gap (report 5.4 "Soak ignora o
            # gap inicial"): a series that only starts sampling well into
            # the window is not continuous evidence, and the interior
            # max_gap_s can never reveal it. The head gap uses the SAME
            # documented soak constant as the interior gap. A series with
            # fewer than MIN_SERIES_DISTINCT_INSTANTS valid distinct
            # instants cannot support any cadence claim and fails.
            for cov_key, gap_key, head_key, inst_key, criterion in (
                (
                    "resources_coverage_pct",
                    "resources_max_gap_s",
                    "resources_head_gap_s",
                    "resources_distinct_instants",
                    "resources_coverage_and_cadence",
                ),
                (
                    "metrics_coverage_pct",
                    "metrics_max_gap_s",
                    "metrics_head_gap_s",
                    "metrics_distinct_instants",
                    "controller_metrics_coverage_and_cadence",
                ),
            ):
                ok = count_ok(
                    lambda r, ck=cov_key, gk=gap_key, hk=head_key, ik=inst_key: (
                        r.get(ck) is not None
                        and float(r[ck]) >= SOAK_MIN_COVERAGE_PCT
                        and r.get(gk) is not None
                        and float(r[gk]) <= SOAK_MAX_SAMPLING_GAP_S
                        and r.get(hk) is not None
                        and float(r[hk]) <= SOAK_MAX_SAMPLING_GAP_S
                        and int(r.get(ik) or 0) >= MIN_SERIES_DISTINCT_INSTANTS
                    )
                )
                details = ", ".join(
                    f"coverage {_fmt_val(r.get(cov_key), '%')} / max gap "
                    f"{_fmt_val(r.get(gap_key), ' s')} / head gap "
                    f"{_fmt_val(r.get(head_key), ' s')} / "
                    f"{int(r.get(inst_key) or 0)} valid distinct instant(s)"
                    for r in valid
                )
                observed = (
                    f"{ok}/{n_valid} run(s) with coverage >= "
                    f"{SOAK_MIN_COVERAGE_PCT:g}%, no sampling gap > "
                    f"{SOAK_MAX_SAMPLING_GAP_S:g} s, head gap <= "
                    f"{SOAK_MAX_SAMPLING_GAP_S:g} s and >= "
                    f"{MIN_SERIES_DISTINCT_INSTANTS} valid distinct instants "
                    f"(observed: {details or 'none'})"
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
            if r.get("resources_per_container_sufficient") is not True:
                insufficiency.append(
                    f"run {rid}: at least one per-container resource series "
                    "has insufficient measured-window coverage/cadence"
                )
            if r.get("host_cpu_sustained_gt090_s") is None:
                insufficiency.append(
                    f"run {rid}: host CPU criterion not evaluable (missing "
                    "nproc or SUT resources)"
                )
            # Minimum sampling coverage — the SAME documented minimum for
            # BOTH series (sprint P5): controller metrics that cover a
            # fraction of the window can no more decide a load than sparse
            # resources can.
            for label, cov_key, head_key, inst_key in (
                (
                    "resources",
                    "resources_coverage_pct",
                    "resources_head_gap_s",
                    "resources_distinct_instants",
                ),
                (
                    "controller metrics",
                    "metrics_coverage_pct",
                    "metrics_head_gap_s",
                    "metrics_distinct_instants",
                ),
            ):
                coverage = r.get(cov_key)
                if (
                    coverage is None
                    or float(coverage) < SATURATION_MIN_RESOURCE_COVERAGE_PCT
                ):
                    observed_cov = (
                        "n/a" if coverage is None else f"{float(coverage):.1f}%"
                    )
                    insufficiency.append(
                        f"run {rid}: {label} coverage {observed_cov} below the "
                        f"{SATURATION_MIN_RESOURCE_COVERAGE_PCT:g}% minimum"
                    )
                head_gap = r.get(head_key)
                if head_gap is None or float(head_gap) > MAX_SAMPLE_GAP_S:
                    observed_head = (
                        "n/a" if head_gap is None else f"{float(head_gap):.1f} s"
                    )
                    insufficiency.append(
                        f"run {rid}: {label} head gap {observed_head} exceeds "
                        f"the {MAX_SAMPLE_GAP_S:g} s sampling-cadence cap "
                        "(sampling started late in the measured window)"
                    )
                instants = int(r.get(inst_key) or 0)
                if instants < MIN_SERIES_DISTINCT_INSTANTS:
                    insufficiency.append(
                        f"run {rid}: {label} has {instants} valid distinct "
                        f"sample instant(s), fewer than the "
                        f"{MIN_SERIES_DISTINCT_INSTANTS} needed to measure "
                        "cadence"
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
            "min_metrics_coverage_pct": SATURATION_MIN_RESOURCE_COVERAGE_PCT,
            "max_head_gap_s": MAX_SAMPLE_GAP_S,
            "min_series_distinct_instants": MIN_SERIES_DISTINCT_INSTANTS,
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
            "criterion evaluable; resources AND controller-metrics "
            "coverage each >= min_resource_coverage_pct; neither series "
            "starting later than max_head_gap_s into the measured window; "
            "at least min_series_distinct_instants valid distinct sample "
            "instants per series; controller metrics present); otherwise "
            "the verdict is 'insufficient-evidence', never "
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


def admissible_resource_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only per-container aggregates admissible for scientific use.

    ``resources_by_run.csv`` deliberately retains insufficient rows for audit,
    but figures and claims must never consume them.  Requiring the value to be
    exactly ``True`` also keeps historical rows without the new flag out of
    scientific outputs until they are re-analysed from sealed raw evidence.
    """
    return [
        resource
        for resource in row.get("_resources", [])
        if resource.get("coverage_sufficient") is True
    ]


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
        for res in admissible_resource_rows(row):
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


def analyze(
    base_dir: str | Path | None = None, plan_path: str | Path | None = None
) -> int:
    """Regenerate ``processed/`` and ``figures/`` from ``raw/``.

    ``plan_path`` is an optional ``campaign_plan.json``. When supplied (or
    when the ``EGW_CAMPAIGN_PLAN`` environment variable names one — the
    documented fallback so identity checking works with or without a CLI
    flag), the acceptance completeness criterion compares the exact SET of
    run identities against the plan instead of counting runs (report 5.4).
    An unreadable or malformed plan degrades to the legacy count check
    with a loud warning; it never aborts the analysis.

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

    plan, plan_problem = load_campaign_plan_for_analysis(plan_path)
    if plan_problem:
        print(f"[analyze] WARNING: {plan_problem}", file=sys.stderr)
    if plan is None:
        print(
            "[analyze] WARNING: no campaign plan supplied; run completeness "
            "is checked BY COUNT ONLY — duplicated, re-seeded, mis-rated or "
            "swapped runs cannot be detected (report 5.4). Pass "
            f"analyze(plan_path=...) or set {CAMPAIGN_PLAN_ENV_VAR}."
        )

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

    # Evidence-integrity gate (report 5.4): a run whose SHA256SUMS does not
    # verify is not evidence at all; an UNSEALED timed run cannot be
    # verified either, and timed runs are exactly the ones that carry the
    # performance claims. Both stay listed in per_run.csv.
    def _integrity_blocks(row: dict[str, Any]) -> bool:
        integrity = row.get("integrity_ok")
        if integrity == INTEGRITY_FAILED:
            return True
        return (
            integrity == INTEGRITY_UNSEALED
            and row.get("condition_id") in TIMED_CONDITION_IDS
        )

    invalid_rows = [r for r in rows if _invalid_validity(r)]
    tampered_rows = [r for r in rows if r.get("integrity_ok") == INTEGRITY_FAILED]
    unsealed_rows = [
        r
        for r in rows
        if r.get("integrity_ok") == INTEGRITY_UNSEALED and _integrity_blocks(r)
    ]
    included = [
        r
        for r in rows
        if not r["excluded"]
        and not _invalid_validity(r)
        and not _integrity_blocks(r)
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
    if tampered_rows:
        tampered_ids = ", ".join(str(r.get("run_id")) for r in tampered_rows)
        print(
            f"[analyze] EVIDENCE INTEGRITY FAILURE in {len(tampered_rows)} "
            f"run(s): {tampered_ids}. {SUMS_FILENAME} does not verify "
            "(mismatch, missing listed file or unlisted file); these runs are "
            "removed from summaries, saturation, acceptance and figures and "
            "must not support any claim (report 5.4)."
        )
    if unsealed_rows:
        unsealed_ids = ", ".join(str(r.get("run_id")) for r in unsealed_rows)
        print(
            f"[analyze] EVIDENCE INTEGRITY UNVERIFIABLE in {len(unsealed_rows)} "
            f"timed run(s): {unsealed_ids}. No {SUMS_FILENAME} in the run "
            "directory, so nothing can be verified; these runs are removed "
            "from summaries, saturation, acceptance and figures (report 5.4)."
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
        evaluate_acceptance(included, plan),
    )

    (processed_dir / "saturation.json").write_text(
        json.dumps(detect_saturation(included), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    figures = generate_figures(figures_dir, included)

    print(
        f"[analyze] {len(rows)} message run(s) processed "
        f"({len(included)} included, {excluded_count} excluded, "
        f"{len(invalid_rows)} invalid, {len(tampered_rows)} integrity "
        f"failure(s), {len(unsealed_rows)} unsealed timed run(s)); "
        f"{len(external_rows)} external run(s); "
        f"{len(figures)} figure(s) written to {figures_dir}"
    )
    return 0
