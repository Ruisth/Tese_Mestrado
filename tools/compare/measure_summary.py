#!/usr/bin/env python3
"""Summarise the runs of the Yocto-vs-Debian-13 comparison into one table.

    measure_summary.py --measure-root DIR [--per-run-csv FILE] --out DIR

What it reads. Under ``DIR/runs/<run-id>/``: ``timeline.json``, the comparison driver's
record of one run (scenario, pair and order within the pair, seed, commit, probe cadences,
the host-monotonic instant of every step, the drain and harness results);
``meminfo-rest.csv`` and ``meminfo-load.csv``, the guest sampler's lines (one per second,
``#`` lines skipped); ``df-before-load.txt``, the raw ``df -P -k / /var/lib/docker`` of the
guest. Across runs, ``--per-run-csv`` names the harness analyser's ``processed/per_run.csv``,
from which the delivery and latency figures are taken by the harness run id recorded in the
timeline, exactly as the analyser wrote them.

What it writes to ``--out``: ``summary.csv`` (one row per run, the columns of ``COLUMNS``),
``table.md`` (the two scenarios side by side: the runs in pair order, the median and the
min–max per scenario, a first line that states the exploratory character and the notes a
reader needs to read the numbers) and ``summary.json`` (the same rows with numbers, plus
the per-scenario aggregates with their ``n``).

Why a separate tool: the harness analyser knows nothing of the guest's memory, of the boot
timeline or of the two scenarios, and this tool re-derives none of its figures. It only
joins, subtracts (durations from one host-monotonic clock), converts KiB to MiB and takes
medians, minima and maxima. Three runs per scenario under one emulated machine profile
support no statistical claim, and the table says so before any number. A value that is not
available is an empty cell and a ``null``, never a zero: a zero would be a measurement.

Exit codes: 0 written; 2 no run directory under the root, or a timeline unreadable. A
missing optional file (a meminfo CSV, the df record, the per-run CSV or one of its rows) is
one WARNING line on stderr, empty cells, and exit 0.
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

#: The nominal condition's measured window, by which the two rates divide.
LOAD_WINDOW_S = 600

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

#: (column, label for the table, decimals; 0 = a count). Table and aggregate order.
METRICS: list[tuple[str, str, int]] = [
    ("boot_ssh_s", "Boot to first ssh answer, s", 1),
    ("stack_ready_s", "Launch to stack ready (/ready 200), s", 1),
    ("gateway_functional_s", "Launch to gateway functional (twin read back), s", 1),
    ("mem_rest_median_mib", "Guest memory used at rest, median, MiB", 1),
    ("mem_rest_max_mib", "Guest memory used at rest, max, MiB", 1),
    ("mem_load_median_mib", "Guest memory used under load, median, MiB", 1),
    ("mem_load_max_mib", "Guest memory used under load, max, MiB", 1),
    ("mem_rest_samples", "Memory samples at rest", 0),
    ("mem_load_samples", "Memory samples under load", 0),
    ("df_root_used_kib", "Root filesystem used before load, KiB", 0),
    ("df_docker_used_kib", "/var/lib/docker used before load, KiB", 0),
    ("sent_valid", "Valid messages sent", 0),
    ("published_rate_msg_s", "Published rate, msg/s", 2),
    ("delivered_unique", "Delivered unique (accepted)", 0),
    ("accepted_rate_msg_s", "Accepted rate, msg/s", 2),
    ("delivery_rate", "Delivery rate", 4),
    ("lost", "Lost (no confirmation within the deadline)", 0),
    ("late_confirmations", "Late confirmations", 0),
    ("duplicates", "Duplicates", 0),
    ("double_accepted", "Double accepted", 0),
    ("latency_ms_p50", "Latency p50, ms", 1),
    ("latency_ms_p95", "Latency p95, ms", 1),
    ("latency_samples", "Latency samples", 0),
    ("drain_s", "Drain, s", 1),
]
DECIMALS = {column: decimals for column, _label, decimals in METRICS}
CATEGORICAL: list[tuple[str, str]] = [("drain_result", "Drain result"), ("harness_exit", "Harness exit")]

COLUMNS = [
    "scenario", "run_id", "pair", "order_in_pair", "seed",
    "boot_ssh_s", "stack_ready_s", "gateway_functional_s",
    "mem_rest_median_mib", "mem_rest_max_mib", "mem_load_median_mib", "mem_load_max_mib",
    "mem_rest_samples", "mem_load_samples", "df_root_used_kib", "df_docker_used_kib",
    "sent_valid", "published_rate_msg_s", "delivered_unique", "accepted_rate_msg_s",
    "delivery_rate", "lost", "late_confirmations", "duplicates", "double_accepted",
    "latency_ms_p50", "latency_ms_p95", "latency_samples",
    "drain_s", "drain_result", "harness_exit",
]

MEMINFO_USED = "mem_used_kb"
DF_MOUNTS = {"/": "df_root_used_kib", "/var/lib/docker": "df_docker_used_kib"}


class SummaryError(Exception):
    """A condition the summary cannot proceed from (exit 2)."""


WARNINGS: list[str] = []


def warn(message: str) -> None:
    WARNINGS.append(message)
    print(f"WARNING: {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Reading one run
# ---------------------------------------------------------------------------

def number(text: Any) -> int | float | None:
    """An int or a float from a CSV/JSON cell; None for empty, missing or non-numeric."""
    if text is None or isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return text
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
    return value if value == value else None  # NaN is not a value


def rounded(value: float | None, decimals: int) -> int | float | None:
    if value is None:
        return None
    if decimals == 0:
        return int(value) if float(value).is_integer() else round(value, 1)
    return round(value, decimals)


def read_timeline(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SummaryError(f"{path}: unreadable timeline ({exc})") from exc
    if not isinstance(data, dict):
        raise SummaryError(f"{path}: timeline is not a JSON object")
    return data


def delta(uptime: dict[str, Any], end: str, start: str) -> float | None:
    """end − start on the host-monotonic clock; None when either instant is missing."""
    a, b = number(uptime.get(start)), number(uptime.get(end))
    if a is None or b is None:
        return None
    return float(b) - float(a)


def read_meminfo_csv(path: Path) -> list[int] | None:
    """The sampler's mem_used_kb values; None when the file is missing or has no header."""
    if not path.is_file():
        warn(f"{path}: missing; memory cells left empty")
        return None
    header: list[str] | None = None
    used: list[int] = []
    skipped = 0
    with path.open(encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split(",")
            if header is None:
                header = fields
                continue
            try:
                value = int(fields[header.index(MEMINFO_USED)])
            except (ValueError, IndexError):
                skipped += 1
                continue
            used.append(value)
    if header is None or MEMINFO_USED not in header:
        warn(f"{path}: no '{MEMINFO_USED}' header; memory cells left empty")
        return None
    if skipped:
        warn(f"{path}: {skipped} malformed line(s) skipped")
    return used


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


def build_row(run_dir: Path, per_run: dict[str, dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
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
    for phase in ("rest", "load"):
        used = read_meminfo_csv(run_dir / f"meminfo-{phase}.csv")
        if used is None:
            continue
        row[f"mem_{phase}_samples"] = len(used)
        if used:
            row[f"mem_{phase}_median_mib"] = round(statistics.median(used) / 1024, 1)
            row[f"mem_{phase}_max_mib"] = round(max(used) / 1024, 1)
    for mount, value in read_df(run_dir / "df-before-load.txt").items():
        row[DF_MOUNTS[mount]] = value
    harness_id = harness.get("run_id") or row["run_id"]
    source = per_run.get(harness_id)
    if per_run and source is None:
        warn(f"{run_dir.name}: harness run id '{harness_id}' not in the per-run CSV; harness cells left empty")
    if source is not None:
        for column, name in HARNESS_COLUMNS.items():
            row[column] = rounded(number(source.get(name)), DECIMALS[column])
        for column, base in (("published_rate_msg_s", "sent_valid"), ("accepted_rate_msg_s", "delivered_unique")):
            if row[base] is not None:
                row[column] = round(row[base] / LOAD_WINDOW_S, 2)
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
        "sample per second (`mem_*_samples` says how many); median and max over the rest and the load "
        "windows. It is not the containers' memory and not the host QEMU process.",
        f"published_rate_msg_s = sent_valid / {LOAD_WINDOW_S} and accepted_rate_msg_s = delivered_unique / "
        f"{LOAD_WINDOW_S}, the nominal measured window; they are not measured throughput.",
        "sent_valid, delivered_unique, delivery_rate, lost, late_confirmations, duplicates, double_accepted "
        "and the latency percentiles are the harness analyser's per_run.csv values, joined by the harness "
        "run id; latency_samples is its `latency_count`.",
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
    lines += ["", "Notes:", ""] + [f"- {note}" for note in notes(timelines)]
    if WARNINGS:
        lines += ["", "Warnings while summarising:", ""] + [f"- {w}" for w in WARNINGS]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, rows: list[dict[str, Any]], aggregates: dict[str, dict[str, Any]],
               timelines: list[dict[str, Any]], generated: str, measure_root: Path) -> None:
    document = {
        "generated_utc": generated,
        "measure_root": str(measure_root),
        "character": header_line(aggregates),
        "load_window_s": LOAD_WINDOW_S,
        "columns": COLUMNS,
        "runs": rows,
        "scenarios": aggregates,
        "notes": notes(timelines),
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
            row, timeline = build_row(run_dir, per_run)
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
    parser.add_argument("--measure-root", required=True, type=Path, help="directory holding runs/<run-id>/")
    parser.add_argument("--per-run-csv", type=Path, default=None, help="the harness analyser's processed/per_run.csv")
    parser.add_argument("--out", required=True, type=Path, help="output directory (created)")
    args = parser.parse_args(argv)
    WARNINGS.clear()
    return summarise(args.measure_root, args.per_run_csv, args.out)


if __name__ == "__main__":
    sys.exit(main())
