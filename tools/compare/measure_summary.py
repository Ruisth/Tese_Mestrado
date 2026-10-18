#!/usr/bin/env python3
"""Summarise the runs of the Yocto-vs-Debian-13 comparison into one table.

    measure_summary.py --measure-root DIR [--per-run-csv FILE] --out DIR

What it reads. Under ``DIR/runs/<run-id>/``: ``timeline.json``, the comparison driver's
record of one run (scenario, pair and order within the pair, seed, probe cadences, the
host-monotonic instant of every step, the drain and harness results, the harness run id and
raw directory); ``meminfo-rest.csv`` and ``meminfo-load.csv``, the guest sampler's lines,
stamped with the GUEST clock (``epoch_s``; ``#`` lines skipped); ``clock_offset.json``, the
driver's guest-minus-host clock offset and its uncertainty; ``df-before-load.txt``, the raw
``df -P -k / /var/lib/docker`` of the guest; ``accounting/accounting.json``, the per-identity
reconciliation at the harness fetch and after the drain. Under ``DIR/harness/raw/<harness
run id>/`` (``harness.raw_dir`` of the timeline as a fallback): ``manifest.json``, the
harness's record with the measured window in harness-host UTC and ``duration_s``, and
``controller_metrics.csv``, the 1 Hz samples of the controller's cumulative counters. Across
runs, ``--per-run-csv`` names the harness analyser's ``processed/per_run.csv``, from which the
delivery and latency figures are taken by the harness run id, exactly as the analyser wrote
them.

Three figures are bounded to the harness's measured window and to nothing else. Memory
"under load" is the sampler's lines inside that window only — never warm-up, the confirmation
window or the drain: the window's host-UTC bounds become guest epoch seconds by adding the
offset, and a line counts when start <= epoch_s <= end. Without the manifest or the offset the
load-memory cells stay empty (the whole file is never a stand-in; it is reported apart, as
``mem_loadfile_*``, for transparency). The accepted rate is the difference of the controller's
cumulative ``accepted`` counter between the last metrics sample at or before the window start
and the last at or before its end, over the seconds between those two samples: what was
accepted inside the window, not what arrived after it. The published rate is ``sent_valid``
over the manifest's ``duration_s``: the simulator's publications during the measured run. The
post-drain reconciliation has columns of its own, apart from the analyser's deadline
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

Exit codes: 0 written; 2 no run directory under the root, or a timeline unreadable. A missing
optional input (a sampler CSV, the clock offset, the df record, the harness manifest or
metrics, the accounting, the per-run CSV or one of its rows) is one WARNING line on stderr
naming it, empty cells, and exit 0.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCENARIOS = ("yocto", "debian13")
SCENARIO_LABELS = {"yocto": "Yocto", "debian13": "Debian 13"}

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
    ("mem_load_median_mib", "Guest memory used inside the measured window, median, MiB", 1),
    ("mem_load_max_mib", "Guest memory used inside the measured window, max, MiB", 1),
    ("mem_load_samples", "Memory samples inside the measured window", 0),
    ("clock_offset_s", "Clock offset guest − host, s", 3),
    ("clock_offset_uncertainty_s", "Clock offset uncertainty, s", 3),
    ("mem_loadfile_median_mib", "Whole load-phase sampler file, median, MiB (transparency only)", 1),
    ("mem_loadfile_max_mib", "Whole load-phase sampler file, max, MiB (transparency only)", 1),
    ("mem_loadfile_samples", "Whole load-phase sampler file, samples", 0),
    ("df_root_used_kib", "Root filesystem used before load, KiB", 0),
    ("df_docker_used_kib", "/var/lib/docker used before load, KiB", 0),
    ("sent_valid", "Valid messages sent", 0),
    ("published_rate_msg_s", "Published rate, msg/s (sent_valid / duration_s)", 2),
    ("delivered_unique", "Delivered unique (accepted within the deadline)", 0),
    ("accepted_in_window", "Accepted inside the measured window (counter difference)", 0),
    ("accepted_rate_span_s", "Span between the two counter samples, s", 1),
    ("accepted_rate_msg_s", "Accepted rate inside the measured window, msg/s", 2),
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
    ("mem_load_window_start_utc", "Measured window start, guest clock"),
    ("mem_load_window_end_utc", "Measured window end, guest clock"),
    ("drain_fetch_claim", "Post-drain event log fetch, as the driver said"),
    ("drain_result", "Drain result"),
    ("harness_exit", "Harness exit"),
]

COLUMNS = [
    "scenario", "run_id", "pair", "order_in_pair", "seed",
    "boot_ssh_s", "stack_ready_s", "gateway_functional_s",
    "mem_rest_median_mib", "mem_rest_max_mib", "mem_rest_samples",
    "mem_load_median_mib", "mem_load_max_mib", "mem_load_samples",
    "mem_load_window_start_utc", "mem_load_window_end_utc", "clock_offset_s", "clock_offset_uncertainty_s",
    "mem_loadfile_median_mib", "mem_loadfile_max_mib", "mem_loadfile_samples",
    "df_root_used_kib", "df_docker_used_kib",
    "sent_valid", "published_rate_msg_s", "delivered_unique",
    "accepted_in_window", "accepted_rate_span_s", "accepted_rate_msg_s",
    "delivery_rate", "lost", "late_confirmations", "duplicates", "double_accepted",
    "latency_ms_p50", "latency_ms_p95", "latency_samples",
    "fetch_accepted_in_time", "fetch_accepted_late", "fetch_no_outcome",
    "drain_accepted_in_time", "drain_accepted_late", "drain_accepted_no_ack", "drain_no_outcome", "drain_fetch_claim",
    "drain_s", "drain_result", "harness_exit",
]

MEMINFO_EPOCH = "epoch_s"
MEMINFO_USED = "mem_used_kb"
METRICS_TS = "ts_utc"
METRICS_ACCEPTED = "accepted"
DF_MOUNTS = {"/": "df_root_used_kib", "/var/lib/docker": "df_docker_used_kib"}


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
    if value is None:
        return None
    if decimals == 0:
        return int(value) if float(value).is_integer() else round(value, 1)
    return round(value, decimals)


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


def utc_ms(epoch: float) -> str:
    """An epoch as the sampler would stamp it, with milliseconds: 2026-10-18T20:00:44.238Z."""
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


def read_meminfo_csv(path: Path) -> list[tuple[int, int]] | None:
    """The sampler's (epoch_s, mem_used_kb) pairs; None when the file is missing or unusable."""
    if not path.is_file():
        warn(f"{path}: missing; its memory cells left empty")
        return None
    parsed = read_csv_lines(path, (MEMINFO_EPOCH, MEMINFO_USED))
    if parsed is None:
        return None
    header, rows = parsed
    i_epoch, i_used = header.index(MEMINFO_EPOCH), header.index(MEMINFO_USED)
    samples: list[tuple[int, int]] = []
    skipped = 0
    for fields in rows:
        try:
            samples.append((int(fields[i_epoch]), int(fields[i_used])))
        except (ValueError, IndexError):
            skipped += 1
    if skipped:
        warn(f"{path}: {skipped} malformed line(s) skipped")
    return samples


def read_controller_metrics(path: Path) -> list[tuple[float, int]] | None:
    """(harness-host epoch, cumulative accepted) per sample, in file order; None when unusable."""
    if not path.is_file():
        warn(f"{path}: missing; accepted-in-window cells left empty")
        return None
    parsed = read_csv_lines(path, (METRICS_TS, METRICS_ACCEPTED))
    if parsed is None:
        return None
    header, rows = parsed
    i_ts, i_acc = header.index(METRICS_TS), header.index(METRICS_ACCEPTED)
    samples: list[tuple[float, int]] = []
    skipped = 0
    for fields in rows:
        try:
            ts, accepted = parse_utc(fields[i_ts]), int(fields[i_acc])
        except (ValueError, IndexError):
            ts = None
        if ts is None:
            skipped += 1
            continue
        samples.append((ts, accepted))
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
         "manifest window, published rate, accepted-in-window and load-memory cells left empty")
    return None


def measured_window(manifest: dict[str, Any] | None, where: str) -> tuple[float, float] | None:
    """(start, end) harness-host epoch of the manifest's measured_window_utc; None with a WARNING."""
    if manifest is None:
        return None
    window = manifest.get("measured_window_utc")
    start = parse_utc(window.get("start")) if isinstance(window, dict) else None
    end = parse_utc(window.get("end")) if isinstance(window, dict) else None
    if start is None or end is None or end <= start:
        warn(f"{where}: measured_window_utc without usable start/end; window-bounded cells left empty")
        return None
    return start, end


def read_clock_offset(path: Path) -> tuple[float, float | None] | None:
    """(offset_guest_minus_host_s, uncertainty_s) from clock_offset.json; None with a WARNING."""
    data = read_json_object(path, "clock offset", "load-memory (window) cells left empty")
    if data is None:
        return None
    offset = number(data.get("offset_guest_minus_host_s"))
    if offset is None:
        warn(f"{path}: offset_guest_minus_host_s is not a number; load-memory (window) cells left empty")
        return None
    return float(offset), number(data.get("uncertainty_s"))


def accepted_in_window(samples: list[tuple[float, int]], start: float, end: float, where: str) -> tuple[int, float] | None:
    """(counter difference, span seconds) between the last sample <= start and the last <= end."""
    before_start = [s for s in samples if s[0] <= start]
    before_end = [s for s in samples if s[0] <= end]
    if not before_start or not before_end:
        warn(f"{where}: no controller-metrics sample at or before the window "
             f"{'start' if not before_start else 'end'}; accepted-in-window cells left empty")
        return None
    (t0, a0), (t1, a1) = before_start[-1], before_end[-1]
    if t1 <= t0:
        warn(f"{where}: the two counter samples do not span a positive interval; accepted-in-window cells left empty")
        return None
    if a1 < a0:
        warn(f"{where}: the accepted counter went backwards inside the window ({a0} -> {a1}); "
             "accepted-in-window cells left empty")
        return None
    return a1 - a0, t1 - t0


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
        row["mem_rest_samples"] = len(rest)
        row["mem_rest_median_mib"], row["mem_rest_max_mib"] = mem_stats([used for _epoch, used in rest])
    for mount, value in read_df(run_dir / "df-before-load.txt").items():
        row[DF_MOUNTS[mount]] = value

    # The harness's measured window (harness-host UTC) and the guest clock offset.
    harness_id = str(harness.get("run_id") or row["run_id"])
    raw_dir = harness_raw_dir(measure_root, harness_id, harness.get("raw_dir"), name)
    manifest = None
    if raw_dir is not None:
        manifest = read_json_object(raw_dir / "manifest.json", "harness manifest",
                                    "manifest window, published rate, accepted-in-window and load-memory cells left empty")
    window = measured_window(manifest, f"{name}: manifest.json")
    offset = read_clock_offset(run_dir / "clock_offset.json")
    if offset is not None:
        row["clock_offset_s"] = rounded(offset[0], 3)
        row["clock_offset_uncertainty_s"] = rounded(offset[1], 3)

    # Memory under load: the whole file for transparency, and the window only for the figure.
    load = read_meminfo_csv(run_dir / "meminfo-load.csv")
    if load is not None:
        row["mem_loadfile_samples"] = len(load)
        row["mem_loadfile_median_mib"], row["mem_loadfile_max_mib"] = mem_stats([used for _epoch, used in load])
    if window is not None and offset is not None:
        start_guest, end_guest = window[0] + offset[0], window[1] + offset[0]
        row["mem_load_window_start_utc"], row["mem_load_window_end_utc"] = utc_ms(start_guest), utc_ms(end_guest)
        if load is not None:
            inside = [used for epoch, used in load if start_guest <= epoch <= end_guest]
            row["mem_load_samples"] = len(inside)
            row["mem_load_median_mib"], row["mem_load_max_mib"] = mem_stats(inside)
            if not inside:
                warn(f"{name}: no sampler line inside the measured window "
                     f"[{row['mem_load_window_start_utc']}, {row['mem_load_window_end_utc']}] (guest clock); "
                     "load-memory median/max left empty")

    # The analyser's per-run figures, and the published rate over the manifest's duration.
    source = per_run.get(harness_id)
    if per_run and source is None:
        warn(f"{name}: harness run id '{harness_id}' not in the per-run CSV; harness cells left empty")
    if source is not None:
        for column, source_name in HARNESS_COLUMNS.items():
            row[column] = rounded(number(source.get(source_name)), DECIMALS[column])
    duration = number(manifest.get("duration_s")) if manifest is not None else None
    if row["sent_valid"] is not None and manifest is not None and not (isinstance(duration, (int, float)) and duration > 0):
        warn(f"{name}: manifest.json without a positive duration_s; published rate left empty")
    if row["sent_valid"] is not None and isinstance(duration, (int, float)) and duration > 0:
        row["published_rate_msg_s"] = round(row["sent_valid"] / duration, 2)

    # Accepted inside the window: the controller's cumulative counter, harness-host clock.
    if raw_dir is not None and window is not None:
        metrics = read_controller_metrics(raw_dir / "controller_metrics.csv")
        if metrics is not None:
            found = accepted_in_window(metrics, window[0], window[1], f"{name}: controller_metrics.csv")
            if found is not None:
                row["accepted_in_window"], row["accepted_rate_span_s"] = found[0], round(found[1], 1)
                row["accepted_rate_msg_s"] = round(found[0] / found[1], 2)

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


def values_seen(rows: list[dict[str, Any]], column: str, decimals: int) -> str:
    seen = sorted({row[column] for row in rows if row[column] is not None})
    return ", ".join(fmt(v, decimals) for v in seen) + " s" if seen else "none read"


def notes(timelines: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[str]:
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
        "and not the host QEMU process.",
        "Load memory (`mem_load_*`) is bounded to the harness's measured window and to nothing else: the "
        "manifest's measured_window_utc (harness-host UTC) is converted to the guest clock by adding "
        "clock_offset.json's offset_guest_minus_host_s (`clock_offset_s`; uncertainty_s seen: "
        f"{values_seen(rows, 'clock_offset_uncertainty_s', 3)}), and a sampler line counts when "
        "window start <= epoch_s <= window end (`mem_load_window_*_utc` are those bounds on the guest clock). "
        "Warm-up, the confirmation window and the drain are outside it. Without the manifest or the offset "
        "the cells stay empty; `mem_loadfile_*` describe the whole load-phase file, including warm-up, "
        "confirmation and drain, for transparency only and are not the load figure.",
        "accepted_rate_msg_s is the difference of the controller's cumulative `accepted` counter between the "
        "last controller_metrics.csv sample at or before the window start and the last at or before the window "
        "end (`accepted_in_window`), divided by the seconds between those two samples (`accepted_rate_span_s`), "
        "both on the harness-host clock of the window: what was accepted inside the window, not what arrived "
        "after it.",
        "published_rate_msg_s = sent_valid / the manifest's duration_s: the simulator's publications during the "
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


def write_table(path: Path, rows: list[dict[str, Any]], aggregates: dict[str, dict[str, Any]],
                timelines: list[dict[str, Any]], generated: str) -> None:
    by_scenario = {s: sorted((r for r in rows if r["scenario"] == s), key=sort_key) for s in SCENARIOS}
    head = ["Metric"]
    for scenario in SCENARIOS:
        label = SCENARIO_LABELS[scenario]
        head += [f"{label}: runs in pair order", f"{label} median", f"{label} min–max"]
    lines = ["# Yocto image vs Debian 13 — measurement summary", "",
             f"**{header_line(aggregates)}** Generated {generated} from {len(rows)} run(s).", "",
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
    lines += ["", "Notes:", ""] + [f"- {note}" for note in notes(timelines, rows)]
    if WARNINGS:
        lines += ["", "Warnings while summarising:", ""] + [f"- {w}" for w in WARNINGS]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, rows: list[dict[str, Any]], aggregates: dict[str, dict[str, Any]],
               timelines: list[dict[str, Any]], generated: str, measure_root: Path) -> None:
    document = {
        "generated_utc": generated,
        "measure_root": str(measure_root),
        "character": header_line(aggregates),
        "columns": COLUMNS,
        "runs": rows,
        "scenarios": aggregates,
        "notes": notes(timelines, rows),
        "warnings": list(WARNINGS),
    }
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def summarise(measure_root: Path, per_run_csv: Path | None, out_dir: Path) -> int:
    runs_dir = measure_root / "runs"
    run_dirs = sorted(p for p in runs_dir.iterdir() if p.is_dir()) if runs_dir.is_dir() else []
    if not run_dirs:
        print(f"STOP: no run directory under {runs_dir}", file=sys.stderr)
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
    rows.sort(key=sort_key)
    aggregates = aggregate(rows)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "summary.csv", rows)
    write_table(out_dir / "table.md", rows, aggregates, timelines, generated)
    write_json(out_dir / "summary.json", rows, aggregates, timelines, generated, measure_root)
    print(f"summary: {len(rows)} run(s) -> {out_dir / 'summary.csv'}, table.md, summary.json"
          + (f"; {len(WARNINGS)} warning(s)" if WARNINGS else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--measure-root", required=True, type=Path, help="directory holding runs/<run-id>/ and harness/raw/")
    parser.add_argument("--per-run-csv", type=Path, default=None, help="the harness analyser's processed/per_run.csv")
    parser.add_argument("--out", required=True, type=Path, help="output directory (created)")
    args = parser.parse_args(argv)
    WARNINGS.clear()
    return summarise(args.measure_root, args.per_run_csv, args.out)


if __name__ == "__main__":
    sys.exit(main())
