#!/usr/bin/env python3
"""Summarise the runs of the Yocto-vs-Debian-13 comparison into one table.

    measure_summary.py --measure-root DIR [--per-run-csv FILE] [--plan FILE] --out DIR

Which runs. Without ``--plan``, every ``DIR/runs/<run-id>/`` directory, in pair order. With
``--plan`` (the sealed or working plan JSON), only the run ids of ``plan["runs"]`` and in the
plan's order: a planned run without a directory is a WARNING and no row, a directory not in
the plan is ignored and named once in a note line, and the plan's path and sha256 are recorded
in ``summary.json`` and in the table's header line, so a table can always be tied to the
series it summarises and never to a stray attempt left beside it.

What it reads. Under ``DIR/runs/<run-id>/``: ``timeline.json``, the comparison driver's
record of one run (scenario, pair and order within the pair, seed, probe cadences, the
host-monotonic instant of every step, the drain and harness results, the harness run id and
raw directory); ``meminfo-rest.csv`` and ``meminfo-load.csv``, the guest sampler's lines
(``uptime_s`` = the guest's /proc/uptime, its CLOCK_BOOTTIME, equal to the controller's
CLOCK_MONOTONIC while the guest never suspends; ``#`` lines skipped); ``df-before-load.txt``,
the raw ``df -P -k / /var/lib/docker`` of the guest; ``accounting/accounting.json``, the
per-identity reconciliation at the harness fetch and after the drain. Under
``DIR/harness/raw/<harness run id>/`` (``harness.raw_dir`` of the timeline as a fallback):
``manifest.json``, the harness's record with the measured window on the host's monotonic
clock (``measured_started_monotonic_ns``, ``finished_monotonic_ns``), the controller marker
polled at the run end (``controller_marker``, ``controller_monotonic_at_run_end_ns``: the
guest's monotonic instant paired with ``finished_monotonic_ns``) and the UTC window;
``controller_metrics.csv``, the 1 Hz samples of the controller's cumulative counters with
their guest ``monotonic_ns``; ``sent_events.jsonl`` (host, ``publish_monotonic_ns``) and
``events.jsonl`` (guest, ``received_monotonic_ns``), whose shared message ids give an
independent host-guest correspondence. Across runs, ``--per-run-csv`` names the harness
analyser's ``processed/per_run.csv``, from which the delivery and latency figures are taken by
the harness run id, exactly as the analyser wrote them.

Two rules bound the window-dependent figures, and nothing else does. The measured window
lives on MONOTONIC clocks: its duration is ``finished − measured_started`` on the host; its
end on the guest clock is the controller's monotonic instant polled at the run end, accepted
only when the marker is ok and its lag within tolerance; its start is that end minus the
duration; and the pairing is cross-checked against the event pairs (the minimum of
``received − publish`` over at least ``MIN_PAIRS`` message ids must place the window end
within ``PAIRING_TOLERANCE_S`` of the marker). When any of this fails the window is
unavailable, with a reason, and every window-dependent cell is empty: 600 s is never
assumed, the UTC window is never a duration or a bound (the host wall clock steps), and the
two monotonic clocks are never subtracted without the pairing. Memory "under load" is the
sampler's lines whose ``uptime_s`` falls inside that window; the whole file is reported apart,
as ``mem_loadfile_*``, for transparency. The accepted rate is an ESTIMATE between the two
boundary samples of ``controller_metrics.csv`` (the last row at or before each bound, each
within ``RATE_BOUND_PROXIMITY_S`` of it, rows strictly time-ordered, counter not decreasing),
with both gaps reported; it is not an exact count inside the window. The published rate is
``sent_valid`` over the monotonic duration: the simulator's publications during the measured
run. The post-drain reconciliation has columns of its own, apart from the analyser's deadline
accounting (``delivered_unique``, ``lost``, ``late_confirmations``).

What it writes to ``--out``: ``summary.csv`` (one row per run, the columns of ``COLUMNS``),
``table.md`` (the two scenarios side by side: the runs in pair order, the median and the
min–max per scenario, a first line that states the exploratory character and the notes a
reader needs to read the numbers) and ``summary.json`` (the same rows with numbers, plus the
per-scenario aggregates with their ``n``).

Why a separate tool: the harness analyser knows nothing of the guest's memory, of the boot
timeline, of the two clocks or of the two scenarios, and this tool re-derives none of its
figures. It only joins, subtracts, converts KiB to MiB and takes medians, minima and maxima.
Three runs per scenario under one emulated machine profile support no statistical claim, and
the table says so before any number. A value that is not available is an empty cell and a
``null``, never a zero: a zero would be a measurement.

Exit codes: 0 written; 2 no run directory under the root (none of the planned ones, with a
plan), a timeline unreadable, or a plan given but unreadable. A missing optional input (a
sampler CSV, the df record, the harness manifest, metrics or event logs, the accounting, the
per-run CSV or one of its rows, a planned run's directory) is one WARNING line on stderr
naming it, empty cells or no row, and exit 0.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCENARIOS = ("yocto", "debian13")
SCENARIO_LABELS = {"yocto": "Yocto", "debian13": "Debian 13"}

#: Host-guest event pairs needed for the clock cross-check, and how far the pairs' window
#: end may lie from the marker's.
MIN_PAIRS = 100
PAIRING_TOLERANCE_S = 1.0
#: How close (before its bound) a boundary metrics sample must be for the rate estimate.
RATE_BOUND_PROXIMITY_S = 5.0
NS = 1e9

#: summary column -> per_run.csv column (the analyser's PER_RUN_COLUMNS names).
HARNESS_COLUMNS = {
    "sent_valid": "sent_valid",
    "delivered_unique": "delivered_unique",
    "delivery_rate": "delivery_rate",
    "lost": "lost",
    "late_confirmations": "late_confirmations",
    "duplicates": "duplicates",
    "double_accepted": "double_accepted",
    "latency_ms_p50": "latency_ms_p50",
    "latency_ms_p95": "latency_ms_p95",
    "latency_samples": "latency_count",
}

#: summary column -> bucket of accounting.json's ``at_harness_fetch`` / ``after_drain``
#: (the keys tools/session/nominal_account.py classify() writes). The buckets are a
#: Counter over every published valid identity, so one absent from the object is zero.
FETCH_BUCKETS = {
    "fetch_accepted_in_time": "accepted_in_time",
    "fetch_accepted_late": "accepted_late",
    "fetch_no_outcome": "no_outcome",
}
DRAIN_BUCKETS = {
    "drain_accepted_in_time": "accepted_in_time",
    "drain_accepted_late": "accepted_late",
    "drain_accepted_no_ack": "accepted_no_ack_time",
    "drain_no_outcome": "no_outcome",
}

#: (column, label for the table, decimals; 0 = a count). Table and aggregate order.
METRICS: list[tuple[str, str, int]] = [
    ("boot_ssh_s", "Boot to first ssh answer, s", 1),
    ("stack_ready_s", "Launch to stack ready (/ready 200), s", 1),
    ("gateway_functional_s", "Launch to gateway functional (twin read back), s", 1),
    ("mem_rest_median_mib", "Guest memory used at rest, median, MiB", 1),
    ("mem_rest_max_mib", "Guest memory used at rest, max, MiB", 1),
    ("mem_rest_samples", "Memory samples at rest", 0),
    ("load_duration_monotonic_s", "Measured window on the host monotonic clock, s", 3),
    ("load_window_utc_span_s", "Measured window as a UTC span (informational), s", 3),
    ("wall_clock_step_s", "Host wall-clock step inside the window: UTC span − monotonic duration, s", 3),
    ("clock_pairing_marker_lag_s", "Controller marker lag at the run end, s", 3),
    ("clock_pairing_pairs", "Host–guest event pairs in the clock cross-check", 0),
    ("clock_pairing_discrepancy_s", "Clock cross-check: window end from the pairs − from the marker, s", 3),
    ("mem_load_window_start_guest_s", "Measured window start on the guest monotonic clock, s", 3),
    ("mem_load_window_end_guest_s", "Measured window end on the guest monotonic clock, s", 3),
    ("mem_load_median_mib", "Guest memory used inside the measured window, median, MiB", 1),
    ("mem_load_max_mib", "Guest memory used inside the measured window, max, MiB", 1),
    ("mem_load_samples", "Memory samples inside the measured window", 0),
    ("mem_loadfile_median_mib", "Whole load-phase sampler file, median, MiB (transparency only)", 1),
    ("mem_loadfile_max_mib", "Whole load-phase sampler file, max, MiB (transparency only)", 1),
    ("mem_loadfile_samples", "Whole load-phase sampler file, samples", 0),
    ("df_root_used_kib", "Root filesystem used before load, KiB", 0),
    ("df_docker_used_kib", "/var/lib/docker used before load, KiB", 0),
    ("sent_valid", "Valid messages sent", 0),
    ("published_rate_msg_s", "Published rate, msg/s (sent_valid / load_duration_monotonic_s)", 2),
    ("delivered_unique", "Delivered unique (accepted within the deadline)", 0),
    ("accepted_between_samples", "Accepted between the two boundary samples (counter difference)", 0),
    ("accepted_rate_span_s", "Span between the two boundary samples, s", 3),
    ("accepted_rate_start_gap_s", "Window start − start boundary sample, s", 3),
    ("accepted_rate_end_gap_s", "Window end − end boundary sample, s", 3),
    ("accepted_rate_est_msg_s", "Estimated accepted rate between the boundary samples, msg/s", 2),
    ("delivery_rate", "Delivery rate", 4),
    ("lost", "Lost (no confirmation within the deadline)", 0),
    ("late_confirmations", "Late confirmations", 0),
    ("duplicates", "Duplicates", 0),
    ("double_accepted", "Double accepted", 0),
    ("latency_ms_p50", "Latency p50, ms", 1),
    ("latency_ms_p95", "Latency p95, ms", 1),
    ("latency_samples", "Latency samples", 0),
    ("fetch_accepted_in_time", "At the harness fetch: accepted in time", 0),
    ("fetch_accepted_late", "At the harness fetch: accepted late", 0),
    ("fetch_no_outcome", "At the harness fetch: no outcome", 0),
    ("drain_accepted_in_time", "After the drain: accepted in time", 0),
    ("drain_accepted_late", "After the drain: accepted late", 0),
    ("drain_accepted_no_ack", "After the drain: accepted without an ack instant", 0),
    ("drain_no_outcome", "After the drain: no outcome", 0),
    ("drain_s", "Drain, s", 1),
]
DECIMALS = {column: decimals for column, _label, decimals in METRICS}
CATEGORICAL: list[tuple[str, str]] = [
    ("load_window_reason", "Why the measured window is unavailable"),
    ("accepted_rate_reason", "Why the rate estimate is unavailable"),
    ("drain_fetch_claim", "Post-drain event log fetch, as the driver said"),
    ("drain_result", "Drain result"),
    ("harness_exit", "Harness exit"),
]

COLUMNS = [
    "scenario", "run_id", "pair", "order_in_pair", "seed",
    "boot_ssh_s", "stack_ready_s", "gateway_functional_s",
    "mem_rest_median_mib", "mem_rest_max_mib", "mem_rest_samples",
    "load_duration_monotonic_s", "load_window_utc_span_s", "wall_clock_step_s",
    "clock_pairing_marker_lag_s", "clock_pairing_pairs", "clock_pairing_discrepancy_s", "load_window_reason",
    "mem_load_window_start_guest_s", "mem_load_window_end_guest_s",
    "mem_load_median_mib", "mem_load_max_mib", "mem_load_samples",
    "mem_loadfile_median_mib", "mem_loadfile_max_mib", "mem_loadfile_samples",
    "df_root_used_kib", "df_docker_used_kib",
    "sent_valid", "published_rate_msg_s", "delivered_unique",
    "accepted_between_samples", "accepted_rate_span_s", "accepted_rate_start_gap_s", "accepted_rate_end_gap_s",
    "accepted_rate_est_msg_s", "accepted_rate_reason",
    "delivery_rate", "lost", "late_confirmations", "duplicates", "double_accepted",
    "latency_ms_p50", "latency_ms_p95", "latency_samples",
    "fetch_accepted_in_time", "fetch_accepted_late", "fetch_no_outcome",
    "drain_accepted_in_time", "drain_accepted_late", "drain_accepted_no_ack", "drain_no_outcome", "drain_fetch_claim",
    "drain_s", "drain_result", "harness_exit",
]

MEMINFO_UPTIME = "uptime_s"
MEMINFO_USED = "mem_used_kb"
METRICS_MONO = "monotonic_ns"
METRICS_ACCEPTED = "accepted"
DF_MOUNTS = {"/": "df_root_used_kib", "/var/lib/docker": "df_docker_used_kib"}
WINDOW_UNAVAILABLE = "measured window unavailable"


class SummaryError(Exception):
    """A condition the summary cannot proceed from (exit 2)."""


WARNINGS: list[str] = []


def warn(message: str) -> None:
    WARNINGS.append(message)
    print(f"WARNING: {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Small conversions
# ---------------------------------------------------------------------------

def number(text: Any) -> int | float | None:
    """An int or a float from a CSV/JSON cell; None for empty, missing or non-numeric."""
    if text is None or isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return text if text == text else None  # NaN is not a value
    s = str(text).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        value = float(s)
    except ValueError:
        return None
    return value if value == value else None


def rounded(value: float | None, decimals: int) -> int | float | None:
    """value rounded for its column; a negative zero (from a difference) reads as 0."""
    if value is None:
        return None
    if decimals == 0:
        result = int(value) if float(value).is_integer() else round(value, 1)
    else:
        result = round(value, decimals)
    return result + 0 if result == 0 else result


def parse_utc(text: Any) -> float | None:
    """Epoch seconds of an ISO-8601 UTC stamp such as 2026-10-18T20:00:40.738Z; None otherwise."""
    if not isinstance(text, str) or not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.timestamp()


def mem_stats(used_kb: list[int]) -> tuple[float | None, float | None]:
    """(median, max) in MiB with one decimal; (None, None) for no samples."""
    if not used_kb:
        return None, None
    return round(statistics.median(used_kb) / 1024, 1), round(max(used_kb) / 1024, 1)


# ---------------------------------------------------------------------------
# Reading one run's inputs
# ---------------------------------------------------------------------------

def read_timeline(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SummaryError(f"{path}: unreadable timeline ({exc})") from exc
    if not isinstance(data, dict):
        raise SummaryError(f"{path}: timeline is not a JSON object")
    return data


def read_json_object(path: Path, what: str, consequence: str) -> dict[str, Any] | None:
    """A JSON object, or None with a WARNING naming the file and what stays empty."""
    if not path.is_file():
        warn(f"{path}: missing; {consequence}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        warn(f"{path}: unreadable {what} ({exc}); {consequence}")
        return None
    if not isinstance(data, dict):
        warn(f"{path}: {what} is not a JSON object; {consequence}")
        return None
    return data


def read_jsonl(path: Path, consequence: str) -> list[dict[str, Any]] | None:
    """The JSON objects of a JSON-lines file; None with a WARNING when it is missing."""
    if not path.is_file():
        warn(f"{path}: missing; {consequence}")
        return None
    records: list[dict[str, Any]] = []
    bad = 0
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(record, dict):
                records.append(record)
            else:
                bad += 1
    if bad:
        warn(f"{path}: {bad} unreadable line(s) skipped")
    return records


def delta(uptime: dict[str, Any], end: str, start: str) -> float | None:
    """end − start on the host-monotonic clock; None when either instant is missing."""
    a, b = number(uptime.get(start)), number(uptime.get(end))
    if a is None or b is None:
        return None
    return float(b) - float(a)


def read_csv_lines(path: Path, required: tuple[str, ...]) -> tuple[list[str], list[list[str]]] | None:
    """(header, data rows) of a CSV whose '#' and blank lines are skipped; None when unusable."""
    header: list[str] | None = None
    rows: list[list[str]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if header is None:
                header = line.split(",")
                continue
            rows.append(line.split(","))
    if header is None or any(name not in header for name in required):
        warn(f"{path}: header without {', '.join(required)}; its cells left empty")
        return None
    return header, rows


def read_meminfo_csv(path: Path) -> tuple[list[tuple[float | None, int]], bool] | None:
    """((uptime_s or None, mem_used_kb) per line, whether the file has uptime_s); None when unusable."""
    if not path.is_file():
        warn(f"{path}: missing; its memory cells left empty")
        return None
    parsed = read_csv_lines(path, (MEMINFO_USED,))
    if parsed is None:
        return None
    header, rows = parsed
    has_uptime = MEMINFO_UPTIME in header
    i_used = header.index(MEMINFO_USED)
    i_up = header.index(MEMINFO_UPTIME) if has_uptime else None
    samples: list[tuple[float | None, int]] = []
    skipped = 0
    for fields in rows:
        try:
            used = int(fields[i_used])
            up = float(fields[i_up]) if i_up is not None else None
        except (ValueError, IndexError):
            skipped += 1
            continue
        samples.append((up, used))
    if skipped:
        warn(f"{path}: {skipped} malformed line(s) skipped")
    if not has_uptime:
        warn(f"{path}: no {MEMINFO_UPTIME} column (an older sampler); in-window memory cells left empty")
    return samples, has_uptime


def read_controller_metrics(path: Path) -> list[tuple[float, int]] | None:
    """(guest monotonic seconds, cumulative accepted) per sample, in file order; None when unusable."""
    if not path.is_file():
        warn(f"{path}: missing; rate-estimate cells left empty")
        return None
    parsed = read_csv_lines(path, (METRICS_MONO, METRICS_ACCEPTED))
    if parsed is None:
        return None
    header, rows = parsed
    i_mono, i_acc = header.index(METRICS_MONO), header.index(METRICS_ACCEPTED)
    samples: list[tuple[float, int]] = []
    skipped = 0
    for fields in rows:
        try:
            samples.append((int(fields[i_mono]) / NS, int(fields[i_acc])))
        except (ValueError, IndexError):
            skipped += 1
    if skipped:
        warn(f"{path}: {skipped} malformed line(s) skipped")
    return samples


def read_df(path: Path) -> dict[str, int]:
    """Used KiB per mount point from a POSIX `df -P -k` record; {} when missing."""
    if not path.is_file():
        warn(f"{path}: missing; df cells left empty")
        return {}
    out: dict[str, int] = {}
    for raw in path.read_text(encoding="utf-8").splitlines()[1:]:
        fields = raw.split()
        if len(fields) < 6:
            continue
        used, mount = number(fields[2]), fields[-1]
        if isinstance(used, int) and mount in DF_MOUNTS and mount not in out:
            out[mount] = used
    for mount in DF_MOUNTS:
        if mount not in out:
            warn(f"{path}: no line for {mount}; its cell left empty")
    return out


def read_per_run(path: Path | None) -> dict[str, dict[str, str]]:
    """per_run.csv rows by run_id; {} (with a WARNING) when not given or unreadable."""
    if path is None:
        warn("no --per-run-csv given; harness columns left empty")
        return {}
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            missing = sorted(set(HARNESS_COLUMNS.values()) - set(header))
            if missing:
                warn(f"{path}: columns not found: {', '.join(missing)}; their cells left empty")
            return {row["run_id"]: row for row in reader if row.get("run_id")}
    except (OSError, KeyError) as exc:
        warn(f"{path}: unreadable ({exc}); harness columns left empty")
        return {}


def harness_raw_dir(measure_root: Path, harness_id: str, declared: Any, run_name: str) -> Path | None:
    """The harness raw directory of a run: under the measurement root, else as the timeline declares."""
    candidates = [measure_root / "harness" / "raw" / harness_id]
    if isinstance(declared, str) and declared and Path(declared) not in candidates:
        candidates.append(Path(declared))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    warn(f"{run_name}: no harness raw directory at {' or '.join(str(c) for c in candidates)}; "
         "measured window, published rate, rate estimate and in-window memory cells left empty")
    return None


# ---------------------------------------------------------------------------
# The measured window on monotonic clocks
# ---------------------------------------------------------------------------

def event_pairs(raw_dir: Path, harness_id: str) -> tuple[int, float | None]:
    """(paired message ids, min of received − publish in s) from the host and guest event logs.

    Each message id pairs the host's publish_monotonic_ns (sent_events.jsonl) with the guest's
    earliest received_monotonic_ns (events.jsonl); records of another run id are ignored. The
    minimum over the pairs is the guest-minus-host offset plus the smallest transit delay."""
    sent = read_jsonl(raw_dir / "sent_events.jsonl", "clock cross-check impossible")
    events = read_jsonl(raw_dir / "events.jsonl", "clock cross-check impossible")
    if sent is None or events is None:
        return 0, None

    def mine(record: dict[str, Any]) -> bool:
        return record.get("run_id") in (None, harness_id)

    publish: dict[str, float] = {}
    for record in sent:
        mid, value = record.get("message_id"), number(record.get("publish_monotonic_ns"))
        if isinstance(mid, str) and value is not None and mine(record) and mid not in publish:
            publish[mid] = float(value)
    received: dict[str, float] = {}
    for record in events:
        mid, value = record.get("message_id"), number(record.get("received_monotonic_ns"))
        if isinstance(mid, str) and value is not None and mine(record) and mid in publish:
            received[mid] = min(float(value), received.get(mid, float(value)))
    offsets = [(received[mid] - publish[mid]) / NS for mid in received]
    return len(offsets), (min(offsets) if offsets else None)


def load_window(manifest: dict[str, Any] | None, raw_dir: Path | None, harness_id: str, where: str) -> dict[str, Any]:
    """The measured window on the two monotonic clocks, or the reason it is unavailable.

    Keys: duration_s (host monotonic), utc_span_s and step_s (informational), marker_lag_s,
    pairs, discrepancy_s, start_guest_s, end_guest_s (guest monotonic; None when unavailable)
    and reason (None when available)."""
    window: dict[str, Any] = {key: None for key in (
        "duration_s", "utc_span_s", "step_s", "marker_lag_s", "pairs", "discrepancy_s",
        "start_guest_s", "end_guest_s", "reason")}
    if manifest is None or raw_dir is None:
        window["reason"] = "harness manifest.json missing"
        return window
    started_ns = number(manifest.get("measured_started_monotonic_ns"))
    finished_ns = number(manifest.get("finished_monotonic_ns"))
    if started_ns is not None and finished_ns is not None and finished_ns > started_ns:
        window["duration_s"] = (finished_ns - started_ns) / NS
    utc = manifest.get("measured_window_utc")
    if isinstance(utc, dict):
        start_utc, end_utc = parse_utc(utc.get("start")), parse_utc(utc.get("end"))
        if start_utc is not None and end_utc is not None:
            window["utc_span_s"] = end_utc - start_utc
    if window["duration_s"] is not None and window["utc_span_s"] is not None:
        window["step_s"] = window["utc_span_s"] - window["duration_s"]
    marker = manifest.get("controller_marker")
    marker = marker if isinstance(marker, dict) else {}
    lag, tolerance = number(marker.get("lag_s")), number(marker.get("lag_tolerance_s"))
    window["marker_lag_s"] = lag
    end_ns = number(manifest.get("controller_monotonic_at_run_end_ns"))
    window["pairs"], offset_pairs = event_pairs(raw_dir, harness_id)

    reasons: list[str] = []
    if window["duration_s"] is None:
        reasons.append("manifest without usable measured_started_monotonic_ns/finished_monotonic_ns")
    if marker.get("ok") is not True:
        reasons.append("controller marker not ok")
    elif lag is None or tolerance is None:
        reasons.append("controller marker without lag_s/lag_tolerance_s")
    elif lag > tolerance:
        reasons.append(f"controller marker lag {lag:.3f} s above its tolerance {tolerance:.3f} s")
    if end_ns is None:
        reasons.append("manifest without controller_monotonic_at_run_end_ns")
    if window["pairs"] < MIN_PAIRS:
        reasons.append(f"only {window['pairs']} host-guest event pairs (fewer than {MIN_PAIRS})")
    end_guest = end_ns / NS if end_ns is not None else None
    if end_guest is not None and offset_pairs is not None and finished_ns is not None:
        window["discrepancy_s"] = finished_ns / NS + offset_pairs - end_guest
        if abs(window["discrepancy_s"]) > PAIRING_TOLERANCE_S:
            reasons.append(f"pairing discrepancy {window['discrepancy_s']:.3f} s exceeds {PAIRING_TOLERANCE_S:.1f} s")
    if reasons:
        window["reason"] = "; ".join(reasons)
        warn(f"{where}: {WINDOW_UNAVAILABLE}: {window['reason']}; window-dependent cells left empty")
    else:
        window["end_guest_s"] = end_guest
        window["start_guest_s"] = end_guest - window["duration_s"]
    return window


def rate_between_samples(metrics: list[tuple[float, int]], start: float, end: float) -> tuple[dict[str, float | int] | None, str | None]:
    """The rate estimate between the boundary samples of the window, or the reason there is none."""
    monos = [mono for mono, _accepted in metrics]
    if any(later <= earlier for earlier, later in zip(monos, monos[1:])):
        return None, "metrics not time-ordered"
    before_start = [sample for sample in metrics if sample[0] <= start]
    before_end = [sample for sample in metrics if sample[0] <= end]
    if not before_start:
        return None, "no metrics sample at or before the window start"
    if not before_end:
        return None, "no metrics sample at or before the window end"
    (t0, a0), (t1, a1) = before_start[-1], before_end[-1]
    start_gap, end_gap = start - t0, end - t1
    if start_gap > RATE_BOUND_PROXIMITY_S:
        return None, (f"last metrics sample before the window start is {start_gap:.3f} s before it "
                      f"(more than {RATE_BOUND_PROXIMITY_S:.1f} s)")
    if end_gap > RATE_BOUND_PROXIMITY_S:
        return None, (f"last metrics sample before the window end is {end_gap:.3f} s before it "
                      f"(more than {RATE_BOUND_PROXIMITY_S:.1f} s)")
    if t1 <= t0:
        return None, "the two boundary samples do not span a positive interval"
    if a1 < a0:
        return None, f"the accepted counter decreased between the boundary samples ({a0} -> {a1})"
    return {"between": a1 - a0, "span_s": t1 - t0, "start_gap_s": start_gap, "end_gap_s": end_gap,
            "rate": (a1 - a0) / (t1 - t0)}, None


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------

def build_row(run_dir: Path, measure_root: Path, per_run: dict[str, dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The summary row of one run directory, and the timeline it was built from."""
    timeline = read_timeline(run_dir / "timeline.json")
    uptime = timeline.get("uptime_s") or {}
    drain = timeline.get("drain") or {}
    harness = timeline.get("harness") or {}
    row: dict[str, Any] = {column: None for column in COLUMNS}
    row.update(
        scenario=timeline.get("scenario"),
        run_id=timeline.get("run_id") or run_dir.name,
        pair=number(timeline.get("pair")),
        order_in_pair=number(timeline.get("order_in_pair")),
        seed=number(timeline.get("seed")),
        boot_ssh_s=rounded(delta(uptime, "ssh_ok", "launch"), 1),
        stack_ready_s=rounded(delta(uptime, "ready", "launch"), 1),
        gateway_functional_s=rounded(delta(uptime, "func_twin", "launch"), 1),
        drain_s=rounded(delta(uptime, "drain_end", "drain_start"), 1),
        drain_result=drain.get("result"),
        harness_exit=number(harness.get("exit")),
    )
    name = run_dir.name

    # Memory at rest: the whole rest-phase file. Disk use before the load.
    rest = read_meminfo_csv(run_dir / "meminfo-rest.csv")
    if rest is not None:
        row["mem_rest_samples"] = len(rest[0])
        row["mem_rest_median_mib"], row["mem_rest_max_mib"] = mem_stats([used for _up, used in rest[0]])
    for mount, value in read_df(run_dir / "df-before-load.txt").items():
        row[DF_MOUNTS[mount]] = value

    # The measured window on the two monotonic clocks.
    harness_id = str(harness.get("run_id") or row["run_id"])
    raw_dir = harness_raw_dir(measure_root, harness_id, harness.get("raw_dir"), name)
    manifest = None
    if raw_dir is not None:
        manifest = read_json_object(raw_dir / "manifest.json", "harness manifest",
                                    "measured window, published rate, rate estimate and in-window memory cells left empty")
    window = load_window(manifest, raw_dir, harness_id, name)
    row["load_duration_monotonic_s"] = rounded(window["duration_s"], 3)
    row["load_window_utc_span_s"] = rounded(window["utc_span_s"], 3)
    row["wall_clock_step_s"] = rounded(window["step_s"], 3)
    row["clock_pairing_marker_lag_s"] = rounded(window["marker_lag_s"], 3)
    row["clock_pairing_pairs"] = window["pairs"] if raw_dir is not None else None
    row["clock_pairing_discrepancy_s"] = rounded(window["discrepancy_s"], 3)
    row["load_window_reason"] = window["reason"]
    available = window["reason"] is None
    if available:
        row["mem_load_window_start_guest_s"] = rounded(window["start_guest_s"], 3)
        row["mem_load_window_end_guest_s"] = rounded(window["end_guest_s"], 3)

    # Memory under load: the whole file for transparency, the window (by uptime_s) for the figure.
    load = read_meminfo_csv(run_dir / "meminfo-load.csv")
    if load is not None:
        samples, has_uptime = load
        row["mem_loadfile_samples"] = len(samples)
        row["mem_loadfile_median_mib"], row["mem_loadfile_max_mib"] = mem_stats([used for _up, used in samples])
        if available and has_uptime:
            start, end = window["start_guest_s"], window["end_guest_s"]
            inside = [used for up, used in samples if up is not None and start <= up <= end]
            row["mem_load_samples"] = len(inside)
            row["mem_load_median_mib"], row["mem_load_max_mib"] = mem_stats(inside)
            if not inside:
                warn(f"{name}: no sampler line with uptime_s inside [{start:.3f}, {end:.3f}] s; "
                     "in-window memory median/max left empty")

    # The analyser's per-run figures, and the published rate over the monotonic duration.
    source = per_run.get(harness_id)
    if per_run and source is None:
        warn(f"{name}: harness run id '{harness_id}' not in the per-run CSV; harness cells left empty")
    if source is not None:
        for column, source_name in HARNESS_COLUMNS.items():
            row[column] = rounded(number(source.get(source_name)), DECIMALS[column])
    if row["sent_valid"] is not None and window["duration_s"] is not None:
        row["published_rate_msg_s"] = round(row["sent_valid"] / window["duration_s"], 2)

    # The rate estimate between the boundary samples of the window (guest monotonic clock).
    if not available:
        row["accepted_rate_reason"] = WINDOW_UNAVAILABLE
    else:
        metrics = read_controller_metrics(raw_dir / "controller_metrics.csv")
        if metrics is None:
            row["accepted_rate_reason"] = "controller_metrics.csv missing or unusable"
        else:
            estimate, reason = rate_between_samples(metrics, window["start_guest_s"], window["end_guest_s"])
            if estimate is None:
                row["accepted_rate_reason"] = reason
                warn(f"{name}: rate estimate unavailable: {reason}; its cells left empty")
            else:
                row["accepted_between_samples"] = estimate["between"]
                row["accepted_rate_span_s"] = round(estimate["span_s"], 3)
                row["accepted_rate_start_gap_s"] = round(estimate["start_gap_s"], 3)
                row["accepted_rate_end_gap_s"] = round(estimate["end_gap_s"], 3)
                row["accepted_rate_est_msg_s"] = round(estimate["rate"], 2)

    # Reconciliation at the harness fetch and after the drain (accounting.json).
    accounting = read_json_object(run_dir / "accounting" / "accounting.json", "accounting",
                                  "fetch/drain reconciliation cells left empty")
    if accounting is not None:
        at_fetch = accounting.get("at_harness_fetch")
        if isinstance(at_fetch, dict):
            for column, bucket in FETCH_BUCKETS.items():
                row[column] = number(at_fetch.get(bucket, 0))
        else:
            warn(f"{name}: accounting.json: at_harness_fetch is not an object; fetch cells left empty")
        row["drain_fetch_claim"] = accounting.get("after_drain_fetch")
        after = accounting.get("after_drain")
        if isinstance(after, dict):
            for column, bucket in DRAIN_BUCKETS.items():
                row[column] = number(after.get(bucket, 0))
        else:
            note = accounting.get("after_drain_note")
            warn(f"{name}: accounting.json: after_drain is null (after_drain_fetch={row['drain_fetch_claim']!r}"
                 f"{'; ' + str(note) if note else ''}); drain bucket cells left empty")
    return row, timeline


# ---------------------------------------------------------------------------
# Aggregates and formatting
# ---------------------------------------------------------------------------

def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row["pair"] if row["pair"] is not None else 1 << 30,
            row["order_in_pair"] if row["order_in_pair"] is not None else 1 << 30,
            str(row["run_id"]))


def aggregate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per scenario: n runs and, per metric, median/min/max/n over the available values."""
    out: dict[str, dict[str, Any]] = {}
    for scenario in SCENARIOS:
        mine = [row for row in rows if row["scenario"] == scenario]
        metrics: dict[str, dict[str, Any]] = {}
        for column, _label, decimals in METRICS:
            values = [row[column] for row in mine if row[column] is not None]
            metrics[column] = {
                "median": rounded(statistics.median(values), decimals) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "n": len(values),
            }
        out[scenario] = {"n_runs": len(mine), "run_ids": [row["run_id"] for row in mine], "metrics": metrics}
    return out


def fmt(value: Any, decimals: int | None = None) -> str:
    """A cell: '' for None; counts without decimals; otherwise the metric's decimals."""
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if decimals is None:
        return str(value)
    if decimals == 0:
        return str(int(value)) if float(value).is_integer() else f"{value:.1f}"
    return f"{value:.{decimals}f}"


def probe_cadences(timelines: list[dict[str, Any]]) -> str:
    seen: list[str] = []
    for timeline in timelines:
        cadence = timeline.get("probe_cadence_s") or {}
        text = ", ".join(f"{k} {fmt(number(v))} s" for k, v in cadence.items()) or "not recorded"
        if text not in seen:
            seen.append(text)
    return "; ".join(seen) if seen else "not recorded"


def notes(timelines: list[dict[str, Any]]) -> list[str]:
    return [
        f"Probe cadences: {probe_cadences(timelines)}. The start times carry that cadence as their resolution.",
        "boot_ssh_s, stack_ready_s and gateway_functional_s are host-monotonic seconds from the instant "
        "recorded just before the QEMU launch (one clock, the host's /proc/uptime) to the first ssh answer, "
        "to the controller's /ready 200 and to the twin read back after the functional event.",
        "Latency is controller reception → Ditto confirmation, as the controller measures it; it is not "
        "simulator → Ditto and does not include the broker leg.",
        "`lost` means no confirmation within the harness's deadline, not definitive loss; `late_confirmations` "
        "counts confirmations that arrived after it.",
        "Memory is of the whole gateway guest: MemTotal − MemAvailable from the guest's /proc/meminfo, one "
        "sample per second (`mem_*_samples` says how many); median and max. It is not the containers' memory "
        "and not the host QEMU process. Each sampler line carries `uptime_s`, the guest's /proc/uptime "
        "(CLOCK_BOOTTIME, equal to the controller's CLOCK_MONOTONIC while the guest never suspends).",
        "The measured window lives on MONOTONIC clocks and on nothing else. Its duration is the harness "
        "manifest's finished_monotonic_ns − measured_started_monotonic_ns on the harness host "
        "(`load_duration_monotonic_s`). Its end on the guest clock is the controller's CLOCK_MONOTONIC instant "
        "polled at the run end (controller_monotonic_at_run_end_ns, paired with finished_monotonic_ns), accepted "
        "only when the controller marker is ok and its lag is within its tolerance (`clock_pairing_marker_lag_s`); "
        "its start is that end minus the duration (`mem_load_window_start_guest_s`, `mem_load_window_end_guest_s`). "
        "The pairing is cross-checked against the host-guest event pairs of sent_events.jsonl/events.jsonl: the "
        f"minimum of received − publish over at least {MIN_PAIRS} message ids (`clock_pairing_pairs`) must place "
        f"the window end within {PAIRING_TOLERANCE_S:.1f} s of the marker's (`clock_pairing_discrepancy_s`). When "
        "any of this fails the window is unavailable (`load_window_reason`) and every window-dependent cell is "
        "empty: 600 s is never assumed, and the two monotonic clocks are never subtracted without this pairing.",
        "measured_window_utc is never used as the duration or the bounds: the host wall clock can step during a "
        "run (it did, by about −13 s, in the first real run). `load_window_utc_span_s` and `wall_clock_step_s` "
        "(UTC span − monotonic duration) are informational only.",
        "Load memory (`mem_load_*`) is bounded to that window: a sampler line counts when window start <= "
        "uptime_s <= window end on the guest clock. Warm-up, the confirmation window and the drain are outside "
        "it. `mem_loadfile_*` describe the whole load-phase file, including warm-up, confirmation and drain, for "
        "transparency only and are not the load figure.",
        "accepted_rate_est_msg_s is an estimated rate between the two boundary samples (gaps reported), not an "
        "exact count inside the window: controller_metrics.csv rows are placed by their guest monotonic_ns; the "
        "boundary samples are the last row at or before the window start and the last at or before its end, each "
        f"required within {RATE_BOUND_PROXIMITY_S:.1f} s before its bound (`accepted_rate_start_gap_s`, "
        "`accepted_rate_end_gap_s`), with the rows strictly time-ordered and the counter not decreasing; "
        "`accepted_between_samples` is the counter difference and `accepted_rate_span_s` the monotonic span "
        "between the two rows. `accepted_rate_reason` says why the estimate is unavailable.",
        "published_rate_msg_s = sent_valid / load_duration_monotonic_s: the simulator's publications during the "
        "measured run, not an acceptance rate. delivered_unique keeps the analyser's meaning (accepted within "
        "the deadline) and is not divided by anything here.",
        "sent_valid, delivered_unique, delivery_rate, lost, late_confirmations, duplicates, double_accepted "
        "and the latency percentiles are the harness analyser's per_run.csv values, joined by the harness "
        "run id; latency_samples is its `latency_count`.",
        "The post-drain reconciliation is reported apart from the deadline accounting: `fetch_*` are "
        "accounting.json's buckets at the harness fetch and `drain_*` its buckets after the drain, per "
        "published valid identity (accepted_in_time, accepted_late, accepted_no_ack_time, no_outcome; a bucket "
        "absent from the counter is zero by construction); `drain_fetch_claim` is what the driver said about "
        "the post-drain event log, and the drain buckets are empty when that log was not read completely. "
        "None of these changes delivered_unique, lost or late_confirmations.",
        "df_*_used_kib are the Used column of `df -P -k` on the guest for / and /var/lib/docker, before the load.",
        "Median: the middle value of three; with two values their mean; with one, that value. min–max are "
        "the extremes of the values available; n says how many. An empty cell is an unavailable value, never a zero.",
    ]


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([fmt(row[column], DECIMALS.get(column)) for column in COLUMNS])


def header_line(aggregates: dict[str, dict[str, Any]]) -> str:
    counts = {scenario: aggregates[scenario]["n_runs"] for scenario in SCENARIOS}
    if len(set(counts.values())) == 1:
        n_text = f"n={next(iter(counts.values()))} per scenario"
    else:
        n_text = " and ".join(f"n={n} ({SCENARIO_LABELS[s]})" for s, n in counts.items())
    return f"Exploratory comparison: {n_text}, one QEMU/TCG profile, no statistical significance claimed."


def plan_line(plan: dict[str, Any] | None) -> str:
    if plan is None:
        return "No plan given: every run directory under the root."
    return f"Plan `{plan['path']}` (sha256 `{plan['sha256']}`), {len(plan['run_ids'])} planned run(s)."


def plan_notes(plan: dict[str, Any] | None) -> list[str]:
    if plan is None:
        return []
    notes_: list[str] = []
    if plan["ignored_not_in_plan"]:
        notes_.append("ignored, not in the plan: " + ", ".join(plan["ignored_not_in_plan"]))
    if plan["missing_directories"]:
        notes_.append("planned without a run directory (no row): " + ", ".join(plan["missing_directories"]))
    return notes_


def write_table(path: Path, rows: list[dict[str, Any]], aggregates: dict[str, dict[str, Any]],
                timelines: list[dict[str, Any]], generated: str, plan: dict[str, Any] | None) -> None:
    # The rows arrive in their final order (the plan's, or pair order): the table keeps it.
    by_scenario = {s: [r for r in rows if r["scenario"] == s] for s in SCENARIOS}
    order = "plan order" if plan is not None else "pair order"
    head = ["Metric"]
    for scenario in SCENARIOS:
        label = SCENARIO_LABELS[scenario]
        head += [f"{label}: runs in {order}", f"{label} median", f"{label} min–max"]
    lines = ["# Yocto image vs Debian 13 — measurement summary", "",
             f"**{header_line(aggregates)}** Generated {generated} from {len(rows)} run(s). {plan_line(plan)}", "",
             "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]

    def cells(column: str, decimals: int | None, aggregated: bool) -> list[str]:
        out: list[str] = []
        for scenario in SCENARIOS:
            runs = by_scenario[scenario]
            out.append(" / ".join(fmt(r[column], decimals) or "—" for r in runs) or "—")
            if aggregated:
                agg = aggregates[scenario]["metrics"][column]
                out.append(fmt(agg["median"], decimals) or "—")
                span = ""
                if agg["min"] is not None:
                    span = f"{fmt(agg['min'], decimals)}–{fmt(agg['max'], decimals)}"
                out.append(span or "—")
            else:
                out += ["—", "—"]
        return out

    for column, label in (("run_id", "Run id"), ("pair", "Pair"), ("order_in_pair", "Order in pair"), ("seed", "Seed")):
        lines.append("| " + " | ".join([label] + cells(column, None, False)) + " |")
    for column, label, decimals in METRICS:
        lines.append("| " + " | ".join([f"{label} (`{column}`)"] + cells(column, decimals, True)) + " |")
    for column, label in CATEGORICAL:
        lines.append("| " + " | ".join([f"{label} (`{column}`)"] + cells(column, None, False)) + " |")
    lines += ["", "Notes:", ""] + [f"- {note}" for note in notes(timelines) + plan_notes(plan)]
    if WARNINGS:
        lines += ["", "Warnings while summarising:", ""] + [f"- {w}" for w in WARNINGS]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, rows: list[dict[str, Any]], aggregates: dict[str, dict[str, Any]],
               timelines: list[dict[str, Any]], generated: str, measure_root: Path,
               plan: dict[str, Any] | None) -> None:
    document = {
        "generated_utc": generated,
        "measure_root": str(measure_root),
        "character": header_line(aggregates),
        "plan": plan,
        "rules": {"min_pairs": MIN_PAIRS, "pairing_tolerance_s": PAIRING_TOLERANCE_S,
                  "rate_bound_proximity_s": RATE_BOUND_PROXIMITY_S},
        "columns": COLUMNS,
        "runs": rows,
        "scenarios": aggregates,
        "notes": notes(timelines) + plan_notes(plan),
        "warnings": list(WARNINGS),
    }
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def read_plan(path: Path) -> dict[str, Any]:
    """The plan's run ids in its order, with the file's path and sha256 for the record.

    ``plan["runs"]`` entries are objects with a ``run_id`` (the harness plan) or plain ids."""
    try:
        raw = path.read_bytes()
        plan = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise SummaryError(f"{path}: unreadable plan ({exc})") from exc
    entries = plan.get("runs") if isinstance(plan, dict) else None
    if not isinstance(entries, list):
        raise SummaryError(f"{path}: plan without a 'runs' list")
    run_ids: list[str] = []
    for entry in entries:
        run_id = entry.get("run_id") if isinstance(entry, dict) else entry
        if not isinstance(run_id, str) or not run_id:
            raise SummaryError(f"{path}: a plan entry without a run_id: {entry!r}")
        if run_id not in run_ids:
            run_ids.append(run_id)
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "run_ids": run_ids,
            "ignored_not_in_plan": [], "missing_directories": []}


def select_run_dirs(runs_dir: Path, plan: dict[str, Any] | None) -> list[Path]:
    """The run directories to summarise: every one in pair order, or the plan's in its order."""
    present = sorted(p for p in runs_dir.iterdir() if p.is_dir()) if runs_dir.is_dir() else []
    if plan is None:
        return present
    names = {p.name for p in present}
    chosen: list[Path] = []
    for run_id in plan["run_ids"]:
        if run_id in names:
            chosen.append(runs_dir / run_id)
        else:
            plan["missing_directories"].append(run_id)
            warn(f"planned run {run_id}: no directory at {runs_dir / run_id}; no row")
    plan["ignored_not_in_plan"] = [p.name for p in present if p.name not in plan["run_ids"]]
    return chosen


def summarise(measure_root: Path, per_run_csv: Path | None, out_dir: Path, plan_path: Path | None = None) -> int:
    runs_dir = measure_root / "runs"
    try:
        plan = read_plan(plan_path) if plan_path is not None else None
    except SummaryError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    run_dirs = select_run_dirs(runs_dir, plan)
    if not run_dirs:
        print(f"STOP: no {'planned ' if plan else ''}run directory under {runs_dir}", file=sys.stderr)
        return 2
    per_run = read_per_run(per_run_csv)
    rows: list[dict[str, Any]] = []
    timelines: list[dict[str, Any]] = []
    try:
        for run_dir in run_dirs:
            row, timeline = build_row(run_dir, measure_root, per_run)
            rows.append(row)
            timelines.append(timeline)
    except SummaryError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    for row in rows:
        if row["scenario"] not in SCENARIOS:
            warn(f"{row['run_id']}: scenario '{row['scenario']}' is not one of {', '.join(SCENARIOS)}; listed, not aggregated")
    if plan is None:
        rows.sort(key=sort_key)
    aggregates = aggregate(rows)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "summary.csv", rows)
    write_table(out_dir / "table.md", rows, aggregates, timelines, generated, plan)
    write_json(out_dir / "summary.json", rows, aggregates, timelines, generated, measure_root, plan)
    for note in plan_notes(plan):
        print(f"note: {note}")
    print(f"summary: {len(rows)} run(s) -> {out_dir / 'summary.csv'}, table.md, summary.json"
          + (f"; {len(WARNINGS)} warning(s)" if WARNINGS else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--measure-root", required=True, type=Path, help="directory holding runs/<run-id>/ and harness/raw/")
    parser.add_argument("--per-run-csv", type=Path, default=None, help="the harness analyser's processed/per_run.csv")
    parser.add_argument("--plan", type=Path, default=None,
                        help="sealed or working plan JSON: only its runs, in its order; others ignored")
    parser.add_argument("--out", required=True, type=Path, help="output directory (created)")
    args = parser.parse_args(argv)
    WARNINGS.clear()
    return summarise(args.measure_root, args.per_run_csv, args.out, args.plan)


if __name__ == "__main__":
    sys.exit(main())
