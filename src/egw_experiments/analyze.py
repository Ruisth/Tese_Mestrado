"""Single reproducible analysis entrypoint (plan 5.8, 7.2, 7.3, 9.1).

``analyze(base_dir)`` regenerates EVERYTHING under ``results/processed/`` and
``results/figures/`` from ``results/raw/`` alone ("processados e figuras sao
sempre regenerados por um unico script", plan 5.8). It never modifies
``results/raw/``.

Metric definitions (plan 7.3 / CONTRACTS 9, applied verbatim)
-------------------------------------------------------------

- ``sent``      : valid message handed to the MQTT publish, i.e. a line of the
                  simulator's ``sent_events.jsonl`` with ``intended_invalid``
                  false. Intentionally invalid payloads are excluded from the
                  delivery-rate denominator.
- ``delivered`` : unique Ditto confirmations, i.e. distinct ``message_id``
                  values with an ``accepted`` controller event whose
                  ``ditto_ack_monotonic_ns`` falls within the confirmation
                  window (60 s after run end; ``confirmation_deadline_
                  monotonic_ns`` in the run manifest). Repeated confirmations
                  of the same ``message_id`` count once.
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

Saturation (plan 7.3)
---------------------

Operational saturation is the first (lowest) load of the sweep at which at
least one criterion holds:

- loss criterion: across-run mean loss rate > 1%;
- latency criterion: across-run mean p95 > 1 s;
- CPU criterion: CPU sustained above 90% for at least 60 s (a per-run event,
  evaluated per container on the raw ``docker stats`` ``cpu_pct``, which is
  expressed relative to a single CPU); the criterion holds at a load when at
  least half of the runs at that load show such an event;
- queue-growth criterion: TODO — persistent queue growth is not measurable
  with the current instrumentation; recorded as such in ``saturation.json``.

The decision rule (means across runs for loss/p95, run-fraction >= 0.5 for
CPU) follows plan 7.3's unit-of-analysis rule (the run) and is echoed in
``saturation.json`` so the thesis text can cite it exactly.

Exclusions (plan 7.3)
---------------------

A run is excluded only for a proven cloud/instrumentation/configuration
failure, with the cause documented in the run manifest's ``exclusion``
field. Excluded runs still appear in ``per_run.csv`` (flagged) but are
removed from summaries, saturation and figures. A slow run is never
excluded for its result alone.

Outputs
-------

- ``processed/per_run.csv``            one row per raw run;
- ``processed/resources_by_run.csv``   per-run, per-container resource
                                       aggregates (mean/max cpu, mean/max
                                       mem);
- ``processed/summary_by_condition.csv`` cross-run statistics, long format;
- ``processed/saturation.json``        saturation evaluation per load;
- ``figures/*.png``                    only when matplotlib is importable
                                       (optional dependency); otherwise a
                                       clear notice is printed and the exit
                                       code stays 0.
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

from .protocol import (
    CONDITION_ORDER,
    PROTOCOL_VERSION,
    SATURATION_CPU_PCT,
    SATURATION_CPU_SUSTAIN_S,
    SATURATION_LOSS_RATE,
    SATURATION_P95_MS,
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
    unparseable fields become None).
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
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    for samples in by_container.values():
        # Unparseable timestamps sort first without ever comparing None.
        samples.sort(key=lambda s: s["ts"] or epoch)
    return by_container


def sustained_cpu_seconds(
    samples: list[dict[str, Any]], threshold_pct: float = SATURATION_CPU_PCT
) -> float:
    """Longest span (seconds) of consecutive samples with cpu_pct > threshold.

    The span is the timestamp distance from the first to the last sample of
    the streak, so with 1 Hz sampling, 61 consecutive samples above the
    threshold yield 60 s.
    """
    best = 0.0
    streak_start: datetime | None = None
    last_in_streak: datetime | None = None
    for sample in samples:
        cpu = sample.get("cpu_pct")
        ts = sample.get("ts")
        if cpu is not None and ts is not None and cpu > threshold_pct:
            if streak_start is None:
                streak_start = ts
            last_in_streak = ts
            best = max(best, (last_in_streak - streak_start).total_seconds())
        else:
            streak_start = None
            last_in_streak = None
    return best


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
    "excluded",
    "exclusion_reason",
    "sent_total",
    "sent_valid",
    "intended_invalid_sent",
    "delivered_unique",
    "lost",
    "delivery_rate",
    "loss_rate",
    "duplicates",
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


def compute_run_metrics(run_dir: str | Path) -> dict[str, Any] | None:
    """Compute the per-run metrics row for one ``results/raw/<run_id>/`` dir.

    Returns None (with a notice on stderr) when the directory has no
    ``sent_events.jsonl``: external conditions (cold starts, twin creations,
    QEMU boots) are not message runs and their evidence is analyzed by the
    deployment/platform procedures.

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
            "skipped (external condition or incomplete run)",
            file=sys.stderr,
        )
        return None

    run_id = manifest.get("run_id") or run_dir.name
    deadline_ns = manifest.get("confirmation_deadline_monotonic_ns")
    if deadline_ns is None:
        warnings.append(
            "confirmation_deadline_monotonic_ns missing from manifest; "
            "all confirmations in events.jsonl counted as in-window"
        )

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

    confirmed_in_window: set[str] = set()
    first_latency: dict[str, float] = {}
    late_confirmations = 0
    duplicates = 0
    failed = 0
    rejected_valid = 0
    rejected_intended = 0
    rejected_unmatched = 0

    for ev in events:
        outcome = ev.get("outcome")
        mid = ev.get("message_id")
        if outcome == "accepted":
            ack = ev.get("ditto_ack_monotonic_ns")
            if deadline_ns is not None and ack is not None and ack > deadline_ns:
                late_confirmations += 1
                continue
            if mid is None:
                warnings.append("accepted event without message_id ignored")
                continue
            if mid in confirmed_in_window:
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

    # --- resources ---------------------------------------------------------
    resources_rows: list[dict[str, Any]] = []
    resource_samples = 0
    cpu_max_overall: float | None = None
    mem_max_overall: int | None = None
    cpu_sustained_max = 0.0
    resources_path = run_dir / "resources.csv"
    if resources_path.is_file():
        by_container = read_resources_csv(resources_path)
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
    else:
        warnings.append("resources.csv missing")

    exclusion = manifest.get("exclusion")

    return {
        "run_id": run_id,
        "condition_id": manifest.get("condition_id"),
        "scenario": manifest.get("scenario"),
        "rate_msg_s": manifest.get("rate_msg_s"),
        "duration_s": manifest.get("duration_s"),
        "seed": manifest.get("seed"),
        "repetition": manifest.get("repetition"),
        "excluded": exclusion is not None,
        "exclusion_reason": (
            json.dumps(exclusion, ensure_ascii=False)
            if isinstance(exclusion, (dict, list))
            else exclusion
        ),
        "sent_total": sent_total,
        "sent_valid": sent_valid,
        "intended_invalid_sent": len(intended_ids),
        "delivered_unique": delivered_unique,
        "lost": lost,
        "delivery_rate": delivery_rate,
        "loss_rate": loss_rate,
        "duplicates": duplicates,
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
        "warnings": " | ".join(warnings),
        "_resources": resources_rows,
    }


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
# Saturation (plan 7.3)
# ---------------------------------------------------------------------------


def detect_saturation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate the plan 7.3 saturation criteria on load-sweep runs.

    ``rows`` are non-excluded per-run rows; only ``condition_id ==
    "load_sweep"`` entries are used. See the module docstring for the
    documented decision rule.
    """
    sweep = [
        r
        for r in rows
        if r.get("condition_id") == "load_sweep"
        and isinstance(r.get("rate_msg_s"), (int, float))
    ]
    by_rate: dict[float, list[dict[str, Any]]] = {}
    for row in sweep:
        by_rate.setdefault(float(row["rate_msg_s"]), []).append(row)

    loads: list[dict[str, Any]] = []
    first_saturated: float | None = None
    for rate in sorted(by_rate):
        member_rows = by_rate[rate]
        loss_values = [
            float(r["loss_rate"]) for r in member_rows if r.get("loss_rate") is not None
        ]
        p95_values = [
            float(r["latency_ms_p95"])
            for r in member_rows
            if r.get("latency_ms_p95") is not None
        ]
        sustained_flags = [
            1 if (r.get("cpu_sustained_gt90_s") or 0.0) >= SATURATION_CPU_SUSTAIN_S else 0
            for r in member_rows
        ]
        loss_mean = statistics.fmean(loss_values) if loss_values else None
        p95_mean = statistics.fmean(p95_values) if p95_values else None
        cpu_fraction = (
            statistics.fmean(sustained_flags) if sustained_flags else None
        )
        triggered = {
            "loss_rate": loss_mean is not None and loss_mean > SATURATION_LOSS_RATE,
            "p95_latency": p95_mean is not None and p95_mean > SATURATION_P95_MS,
            "cpu_sustained": cpu_fraction is not None and cpu_fraction >= 0.5,
            "queue_growth": None,  # TODO: not measurable, see below
        }
        saturated = any(v for v in triggered.values() if v is not None)
        loads.append(
            {
                "rate_msg_s": rate,
                "n_runs": len(member_rows),
                "loss_rate_mean": loss_mean,
                "latency_ms_p95_mean": p95_mean,
                "cpu_sustained_run_fraction": cpu_fraction,
                "triggered": triggered,
                "saturated": saturated,
            }
        )
        if saturated and first_saturated is None:
            first_saturated = rate

    return {
        "generated_by": "egw_experiments.analyze",
        "protocol_version": PROTOCOL_VERSION,
        "criteria": {
            "loss_rate_gt": SATURATION_LOSS_RATE,
            "latency_ms_p95_gt": SATURATION_P95_MS,
            "cpu_pct_gt": SATURATION_CPU_PCT,
            "cpu_sustain_s": SATURATION_CPU_SUSTAIN_S,
            "queue_growth": (
                "TODO: persistent queue growth is not measurable with the "
                "current instrumentation and is not evaluated"
            ),
        },
        "decision_rule": (
            "Unit of analysis is the run (plan 7.3). A load is saturated "
            "when the across-run mean loss rate exceeds 1%, OR the "
            "across-run mean p95 latency exceeds 1000 ms, OR at least half "
            "of the runs at that load show CPU above 90% (docker stats "
            "cpu_pct, single-CPU basis, per container) sustained for at "
            "least 60 s. Saturation is the first (lowest) saturated load."
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
    for run_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        row = compute_run_metrics(run_dir)
        if row is not None:
            rows.append(row)
    rows.sort(key=_run_sort_key)

    resources_rows: list[dict[str, Any]] = []
    for row in rows:
        resources_rows.extend(row.get("_resources", []))

    included = [r for r in rows if not r["excluded"]]
    excluded_count = len(rows) - len(included)
    if excluded_count:
        print(
            f"[analyze] {excluded_count} run(s) excluded per manifest "
            "'exclusion' (documented cause required, plan 7.3); they remain "
            "listed in per_run.csv"
        )

    _write_csv(processed_dir / "per_run.csv", PER_RUN_COLUMNS, rows)
    _write_csv(
        processed_dir / "resources_by_run.csv",
        RESOURCES_BY_RUN_COLUMNS,
        resources_rows,
    )
    _write_csv(
        processed_dir / "summary_by_condition.csv",
        SUMMARY_COLUMNS,
        summarize_by_condition(included),
    )
    (processed_dir / "saturation.json").write_text(
        json.dumps(detect_saturation(included), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    figures = generate_figures(figures_dir, included)

    print(
        f"[analyze] {len(rows)} run(s) processed "
        f"({len(included)} included, {excluded_count} excluded); "
        f"{len(figures)} figure(s) written to {figures_dir}"
    )
    return 0
