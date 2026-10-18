"""Cases for tools/compare/measure_summary.py, the table builder of the comparison
measurement.

A synthetic measurement root is built with six runs (three per scenario, in the
Y-D-D-Y-Y-D pair order) whose inputs carry values chosen so that every derived figure
is known in advance. The measured window is built on the two monotonic clocks the tool
pairs: a harness manifest with host monotonic start/finish 600.1 s apart, a controller
marker giving the guest's monotonic instant at the run end, and host/guest event logs
whose 120 shared message ids reproduce that correspondence to 5 ms; the sampler's lines
carry `uptime_s` values before, inside and after the window so that only the inside ones
may count, and the controller metrics climb by a known step per second, so that the
estimate between the boundary rows and both gaps are exact. One run has a UTC window 13 s
shorter than the monotonic one (the host wall clock stepped back), which must leave the
window available and be reported; one has a marker that is not ok and one a pairing
discrepancy of 2 s (window unavailable, with the reason); one has a 20 s hole in the
metrics before the window end (rate unavailable, memory still bounded). Further cases
mutate a complete run for each remaining refusal: marker lag above tolerance, fewer than
100 pairs, missing monotonic fields, a hole before the window start, unordered metrics, a
decreasing counter. The per-run CSV is written under the harness analyser's own column
list (imported, so that a renamed column breaks these cases rather than the tool
silently) and the accounting buckets are checked against the names the accounting script
writes. Missing inputs must leave the cells concerned empty, never zero, with a WARNING
naming them. The tool runs under this interpreter on any host; nothing here touches a
guest or a real measurement.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from egw_experiments.analyze import PER_RUN_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "tools" / "compare" / "measure_summary.py"
NOMINAL_ACCOUNT = REPO_ROOT / "tools" / "session" / "nominal_account.py"


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("measure_summary", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()

MIB_KB = 1024
MEM_TOTAL_KB = 8_012_000
PROBES = {"ssh": 2, "ready": 5, "accept": 1}
OUTSIDE_MIB = 2000
PARTIAL_NOTE = ("the post-drain event log is on disk but its fetch did not succeed: what it "
                "holds may be a partial tail, and no figure is claimed from it")

# The measured window. Host CLOCK_MONOTONIC (ns): measured start and finish 600.1 s apart.
# Guest CLOCK_MONOTONIC (ns): the controller's instant polled at the run end, 1108.0 s.
# So the window on the guest clock is [507.9, 1108.0] s and the true guest-minus-host
# offset is G_END - FIN = -4492.1 s.
H0_NS = 5_000_000_000_000
D_NS = 600_100_000_000
FIN_NS = H0_NS + D_NS
G_END_NS = 1_108_000_000_000
OFFSET_NS = G_END_NS - FIN_NS
START_GUEST_S = 507.9
END_GUEST_S = 1108.0
UTC_START = datetime(2026, 10, 20, 10, 2, 0, tzinfo=timezone.utc).timestamp()
# Guest uptime_s of the seven load-phase sampler lines: two before, three inside, two after.
LOAD_UPTIMES_BEFORE = [507.0, 507.5]
LOAD_UPTIMES_INSIDE = [508.0, 800.0, 1107.5]
LOAD_UPTIMES_AFTER = [1108.5, 1200.0]
# Controller metrics: row k at guest 500.4 + k s, so the boundary rows are k=7 (507.4 s,
# 0.5 s before the start) and k=607 (1107.4 s, 0.6 s before the end), 600.0 s apart.
METRICS_BASE_NS = 500_400_000_000
METRICS_ROWS = 621
START_ROW, END_ROW = 7, 607


def utc_ms(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def utc_s(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mib(values: list[float]) -> list[int]:
    return [int(v * MIB_KB) for v in values]


def df_text(root_used: int, docker_used: int | None) -> str:
    lines = [
        "Filesystem     1024-blocks    Used Available Capacity Mounted on",
        f"/dev/vda           2493696 {root_used:7d}   2124800      15% /",
    ]
    if docker_used is not None:
        lines.append(f"/dev/vdb          32888848 {docker_used:7d}  29098220       7% /var/lib/docker")
    return "\n".join(lines) + "\n"


def meminfo_text(samples: list[tuple[float, int]], *, with_uptime: bool = True) -> str:
    """The sampler's file for (guest uptime_s, used kB) samples, with its closing line."""
    header = "ts_utc,epoch_s,uptime_s,mem_total_kb,mem_available_kb,mem_used_kb"
    rows = [header if with_uptime else header.replace("uptime_s,", "")]
    epoch = 1_792_490_000
    for i, (up, used) in enumerate(samples):
        cells = [utc_s(epoch + i), str(epoch + i)] + ([f"{up:.2f}"] if with_uptime else [])
        cells += [str(MEM_TOTAL_KB), str(MEM_TOTAL_KB - used), str(used)]
        rows.append(",".join(cells))
    rows.append(f"# end epoch_s={epoch + len(samples)} samples={len(samples)}")
    return "\n".join(rows) + "\n"


def load_samples(inside_mib: list[float]) -> list[tuple[float, int]]:
    samples = [(up, OUTSIDE_MIB * MIB_KB) for up in LOAD_UPTIMES_BEFORE]
    samples += list(zip(LOAD_UPTIMES_INSIDE, mib(inside_mib)))
    samples += [(up, OUTSIDE_MIB * MIB_KB) for up in LOAD_UPTIMES_AFTER]
    return samples


def metrics_text(step: int, *, omit: frozenset[int] = frozenset(), swap: bool = False,
                 decrease_at: int | None = None, base: int = 100) -> str:
    """1 Hz controller metrics whose cumulative `accepted` climbs by `step` per row.

    omit drops rows (a hole); swap exchanges rows 300 and 301 (not time-ordered); decrease_at
    forces that row's counter below the start boundary's value."""
    header = ("ts_utc,accepted,rejected,duplicate,failed,dropped,queue_depth,received,in_progress,"
              "processing_errors,unacked,mqtt_connection,mqtt_subscribed,started_at,wall_utc,uptime_s,monotonic_ns")
    rows = []
    for k in range(METRICS_ROWS):
        if k in omit:
            continue
        mono_ns = METRICS_BASE_NS + k * 1_000_000_000
        accepted = base + step * k if k != decrease_at else base - 1
        rows.append(f"{utc_ms(UTC_START - 7.5 + k)},{accepted},0,0,0,0,3,{accepted + 5},1,0,4,1,true,"
                    f"{utc_ms(UTC_START - 300)},{utc_ms(UTC_START - 7.2 + k)},{500.4 + k:.3f},{mono_ns}")
    if swap:
        rows[300], rows[301] = rows[301], rows[300]
    return "\n".join([header] + rows) + "\n"


def manifest_doc(harness_id: str, *, utc_span_s: float = 600.1, marker_ok: bool = True, lag_s: float = 0.03,
                 tolerance_s: float = 2.0, started_ns: int | None = H0_NS, finished_ns: int | None = FIN_NS,
                 end_ns: int | None = G_END_NS) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "run_id": harness_id,
        "measured_window_utc": {"start": utc_ms(UTC_START), "end": utc_ms(UTC_START + utc_span_s)},
        "measured_window_clock": "harness-host wall clock; used ONLY to window 1 Hz samples",
        "duration_s": 600, "warmup_s": 120, "confirmation_window_s": 60,
        "started_utc": utc_ms(UTC_START - 120.2), "finished_utc": utc_ms(UTC_START + utc_span_s),
        "measured_started_monotonic_ns": started_ns, "finished_monotonic_ns": finished_ns,
        "controller_monotonic_at_run_end_ns": end_ns,
        "controller_marker": {"error": None, "lag_s": lag_s, "lag_tolerance_s": tolerance_s, "monotonic_ns": end_ns,
                              "ok": marker_ok, "polled_utc": utc_ms(UTC_START + utc_span_s),
                              "url": "http://127.0.0.1:8000/metrics", "wall_utc": utc_ms(UTC_START + utc_span_s - 0.3)},
        "confirmation_deadline_monotonic_ns": (end_ns or 0) + 60_000_000_000,
        "confirmation_deadline_clock_domain": "controller",
    }
    for key in ("measured_started_monotonic_ns", "finished_monotonic_ns", "controller_monotonic_at_run_end_ns"):
        if doc[key] is None:
            del doc[key]
    return doc


def event_logs(harness_id: str, *, pairs: int = 120, extra_offset_ns: int = 0) -> tuple[str, str]:
    """(sent_events.jsonl, events.jsonl) with `pairs` shared message ids.

    The guest receives each message OFFSET_NS + extra_offset_ns + (5 + i % 7) ms after the host
    published it, so the minimum of received − publish is the true offset plus 5 ms."""
    sent, events = [], []
    for i in range(pairs):
        publish = H0_NS + i * 5_000_000_000
        mid = f"00000000-0000-5000-8000-{i:012d}"
        sent.append({"run_id": harness_id, "message_id": mid, "device_uuid": "dev-1", "device_type": "smartwatch",
                     "seq": i, "publish_monotonic_ns": publish, "puback_monotonic_ns": None, "intended_invalid": False})
        received = publish + OFFSET_NS + extra_offset_ns + 5_000_000 + (i % 7) * 1_000_000
        events.append({"run_id": harness_id, "message_id": mid, "device_uuid": "dev-1", "device_type": "smartwatch",
                       "seq": i, "received_monotonic_ns": received, "ditto_ack_monotonic_ns": received + 150_000_000,
                       "latency_ms": 150.0, "outcome": "accepted", "attempts": 1, "error": None})
    # One record of another run, which must be ignored.
    events.append({"run_id": "warmup-other", "message_id": sent[0]["message_id"], "received_monotonic_ns": 1,
                   "outcome": "accepted"})
    dump = lambda records: "".join(json.dumps(r) + "\n" for r in records)  # noqa: E731
    return dump(sent), dump(events)


# scenario, run_id, pair, order, seed, launch, (ssh_ok, ready, func_twin) relative to launch,
# drain seconds, rest MiB, load MiB inside the window (None = file missing), df (root, docker),
# drain result, harness exit, harness run id (None = no per-run row), metrics step (None = no
# harness raw directory), whether the raw directory lives elsewhere and is only declared by the
# timeline, manifest keyword overrides, metrics keyword overrides, event-log keyword overrides,
# accounting ("full", "sparse", "tail-not-read" or None = file missing).
RUNS: list[dict[str, Any]] = [
    dict(scenario="yocto", run_id="cmp-yocto-p1", pair=1, order=1, seed=101, launch=10.0,
         ssh=22.5, ready=383.0, func=399.0, drain=60.5, rest=[400, 410, 420], load=[1100, 1120, 1110],
         df=(352256, 2097152), drain_result="quiet", harness_exit=0, harness_id="nominal-yocto-p1",
         step=7, raw_elsewhere=False, manifest={}, metrics={}, events={}, accounting="full"),
    # The host wall clock stepped back 13 s during the run: the UTC window is 587.1 s long.
    dict(scenario="debian13", run_id="cmp-debian13-p1", pair=1, order=2, seed=101, launch=20.0,
         ssh=46.0, ready=376.0, func=401.1, drain=61.0, rest=[600, 610, 620], load=[1200, 1500.5, 1210],
         df=(1572864, 2097152), drain_result="quiet", harness_exit=0, harness_id="nominal-debian13-p1",
         step=8, raw_elsewhere=False, manifest={"utc_span_s": 587.1}, metrics={}, events={}, accounting="sparse"),
    dict(scenario="debian13", run_id="cmp-debian13-p2", pair=2, order=1, seed=102, launch=5.0,
         ssh=47.5, ready=380.0, func=402.0, drain=59.0, rest=[590, 600, 610], load=[1190, 1200, 1210],
         df=(1572900, 2097200), drain_result="quiet", harness_exit=0, harness_id=None,
         step=None, raw_elsewhere=False, manifest={}, metrics={}, events={}, accounting="full"),
    # The controller marker is not ok: no correspondence between the clocks.
    dict(scenario="yocto", run_id="cmp-yocto-p2", pair=2, order=2, seed=102, launch=5.0,
         ssh=23.0, ready=390.0, func=405.0, drain=60.0, rest=[420, 430, 440], load=[1000, 1020, 1010],
         df=(352300, 2097300), drain_result="quiet", harness_exit=0, harness_id="nominal-yocto-p2",
         step=7, raw_elsewhere=False, manifest={"marker_ok": False}, metrics={}, events={}, accounting="tail-not-read"),
    # The event pairs disagree with the marker by 2 s.
    dict(scenario="yocto", run_id="cmp-yocto-p3", pair=3, order=1, seed=103, launch=7.0,
         ssh=21.0, ready=None, func=None, drain=58.0, rest=[440, 450, 460], load=None,
         df=(352400, 2097400), drain_result="gave-up", harness_exit=1, harness_id="nominal-yocto-p3",
         step=6, raw_elsewhere=False, manifest={}, metrics={}, events={"extra_offset_ns": 2_000_000_000},
         accounting=None),
    # A 20 s hole in the metrics before the window end (rows 588..607 missing).
    dict(scenario="debian13", run_id="cmp-debian13-p3", pair=3, order=2, seed=103, launch=9.0,
         ssh=45.0, ready=378.0, func=399.5, drain=62.0, rest=[610, 620, 630], load=[1210, 1230, 1220],
         df=(1573000, None), drain_result="quiet", harness_exit=0, harness_id="nominal-debian13-p3",
         step=8, raw_elsewhere=True, manifest={}, metrics={"omit": frozenset(range(588, 608))}, events={},
         accounting="full"),
]

HARNESS_ROWS: dict[str, dict[str, Any]] = {
    "nominal-yocto-p1": dict(sent_valid=6720, delivered_unique=6700, lost=20, delivery_rate=0.997,
                             duplicates=1, double_accepted=0, late_confirmations=3,
                             latency_ms_p50=123.44, latency_ms_p95=456.66, latency_count=6700),
    "nominal-yocto-p2": dict(sent_valid=6720, delivered_unique=6710, lost=10, delivery_rate=0.9985,
                             duplicates=0, double_accepted=0, late_confirmations=1,
                             latency_ms_p50=120.0, latency_ms_p95=430.0, latency_count=6710),
    "nominal-yocto-p3": dict(sent_valid=6720, delivered_unique=6690, lost=30, delivery_rate=0.9955,
                             duplicates=2, double_accepted=1, late_confirmations=5,
                             latency_ms_p50=130.0, latency_ms_p95=480.0, latency_count=6690),
    "nominal-debian13-p1": dict(sent_valid=6720, delivered_unique=6718, lost=2, delivery_rate=0.9997,
                                duplicates=0, double_accepted=0, late_confirmations=0,
                                latency_ms_p50=100.0, latency_ms_p95=300.0, latency_count=6718),
    "nominal-debian13-p3": dict(sent_valid=6720, delivered_unique=6716, lost=4, delivery_rate=0.9994,
                                duplicates=0, double_accepted=0, late_confirmations=1,
                                latency_ms_p50=110.0, latency_ms_p95=320.0, latency_count=6716),
}

ACCOUNTING: dict[str, dict[str, Any]] = {
    "full": {
        "at_harness_fetch": {"accepted_in_time": 6690, "accepted_late": 5, "accepted_no_ack_time": 0, "no_outcome": 25},
        "after_drain": {"accepted_in_time": 6690, "accepted_late": 28, "accepted_no_ack_time": 1, "no_outcome": 1},
        "after_drain_fetch": "fetched", "after_drain_note": None,
    },
    # A bucket absent from the counter (accepted_late at the fetch) is zero by construction.
    "sparse": {
        "at_harness_fetch": {"accepted_in_time": 6718, "no_outcome": 2},
        "after_drain": {"accepted_in_time": 6718, "accepted_late": 2},
        "after_drain_fetch": "unstated", "after_drain_note": "nothing was said about the fetch",
    },
    "tail-not-read": {
        "at_harness_fetch": {"accepted_in_time": 6705, "accepted_late": 5, "no_outcome": 10},
        "after_drain": None, "after_drain_per_device": None,
        "after_drain_fetch": "not-fetched", "after_drain_note": PARTIAL_NOTE,
    },
}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def harness_id_of(run: dict[str, Any]) -> str:
    return run["harness_id"] or run["run_id"] + "-harness"


def raw_dir_of(root: Path, run: dict[str, Any]) -> Path:
    if run["raw_elsewhere"]:
        return root / "elsewhere" / "raw" / harness_id_of(run)
    return root / "harness" / "raw" / harness_id_of(run)


def timeline(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    launch = run["launch"]
    rel = lambda v: None if v is None else launch + v  # noqa: E731
    drain_start = launch + 1800.0
    return {
        "scenario": run["scenario"], "run_id": run["run_id"], "pair": run["pair"],
        "order_in_pair": run["order"], "seed": run["seed"], "commit": "0123abcd",
        "probe_cadence_s": dict(PROBES),
        "uptime_s": {
            "launch": launch, "ssh_ok": rel(run["ssh"]), "healthy": rel(200.0), "ready": rel(run["ready"]),
            "func_accepted": rel(run["func"] and run["func"] - 1.0), "func_twin": rel(run["func"]),
            "rest_start": rel(420.0), "rest_end": rel(1020.0), "load_start": rel(1030.0), "load_end": rel(1790.0),
            "drain_start": drain_start, "drain_end": drain_start + run["drain"],
            "stop_requested": drain_start + run["drain"] + 1.0, "qemu_gone": drain_start + run["drain"] + 50.0,
        },
        "drain": {"result": run["drain_result"], "exit": 0 if run["drain_result"] == "quiet" else 1},
        "harness": {"run_id": harness_id_of(run), "exit": run["harness_exit"],
                    "raw_dir": str(raw_dir_of(root, run))},
    }


def write_raw(root: Path, run: dict[str, Any], *, manifest: dict[str, Any] | None = None,
              metrics: dict[str, Any] | None = None, events: dict[str, Any] | None = None) -> None:
    """The harness raw directory of a run: manifest, metrics and the two event logs."""
    raw = raw_dir_of(root, run)
    hid = harness_id_of(run)
    write(raw / "manifest.json", json.dumps(manifest_doc(hid, **(manifest if manifest is not None else run["manifest"]))))
    write(raw / "controller_metrics.csv", metrics_text(run["step"], **(metrics if metrics is not None else run["metrics"])))
    sent, received = event_logs(hid, **(events if events is not None else run["events"]))
    write(raw / "sent_events.jsonl", sent)
    write(raw / "events.jsonl", received)


def build_root(root: Path) -> Path:
    """The measurement root with six runs, their harness raw directories and the per-run CSV."""
    for run in RUNS:
        d = root / "runs" / run["run_id"]
        write(d / "timeline.json", json.dumps(timeline(root, run), indent=1))
        rest = [(100.0 + i, used) for i, used in enumerate(mib(run["rest"]))]
        write(d / "meminfo-rest.csv", meminfo_text(rest))
        if run["load"] is not None:
            write(d / "meminfo-load.csv", meminfo_text(load_samples(run["load"])))
        write(d / "df-before-load.txt", df_text(*run["df"]))
        if run["step"] is not None:
            write_raw(root, run)
        if run["accounting"] is not None:
            doc = {"run_id": harness_id_of(run), "label": "diagnostic accounting", **ACCOUNTING[run["accounting"]]}
            write(d / "accounting" / "accounting.json", json.dumps(doc, indent=1))
    per_run = root / "processed" / "per_run.csv"
    per_run.parent.mkdir(parents=True)
    with per_run.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=PER_RUN_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for run_id, values in HARNESS_ROWS.items():
            row = {column: "" for column in PER_RUN_COLUMNS}
            row.update(run_id=run_id, condition_id="nominal", scenario="nominal", validity="valid")
            row.update(values)
            writer.writerow(row)
    return per_run


def run_tool(root: Path, per_run: Path | None, out: Path, plan: Path | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, "-I", str(TOOL), "--measure-root", str(root), "--out", str(out)]
    if per_run is not None:
        args += ["--per-run-csv", str(per_run)]
    if plan is not None:
        args += ["--plan", str(plan)]
    return subprocess.run(args, capture_output=True, text=True, timeout=120)


def summary_rows(out: Path) -> dict[str, dict[str, str]]:
    with (out / "summary.csv").open(encoding="utf-8", newline="") as fh:
        return {row["run_id"]: row for row in csv.DictReader(fh)}


@pytest.fixture(scope="module")
def outputs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("measure")
    per_run = build_root(root)
    out = root / "summary"
    proc = run_tool(root, per_run, out)
    assert proc.returncode == 0, proc.stderr
    with (out / "summary.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {
        "root": root, "out": out, "stderr": proc.stderr, "rows": rows,
        "by_id": {row["run_id"]: row for row in rows},
        "table": (out / "table.md").read_text(encoding="utf-8"),
        "json": json.loads((out / "summary.json").read_text(encoding="utf-8")),
    }


def table_rows(table: str) -> dict[str, list[str]]:
    return {line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]]
            for line in table.splitlines() if line.startswith("| ") and "`" in line}


WINDOW_COLUMNS = ("mem_load_window_start_guest_s", "mem_load_window_end_guest_s", "mem_load_median_mib",
                  "mem_load_max_mib", "mem_load_samples")
RATE_COLUMNS = ("accepted_between_samples", "accepted_rate_span_s", "accepted_rate_start_gap_s",
                "accepted_rate_end_gap_s", "accepted_rate_est_msg_s")


def test_harness_columns_exist_in_the_analyser() -> None:
    assert set(tool.HARNESS_COLUMNS.values()) <= set(PER_RUN_COLUMNS)
    assert tool.HARNESS_COLUMNS["latency_samples"] == "latency_count"


def test_accounting_buckets_are_named_as_the_accounting_script_writes_them() -> None:
    source = NOMINAL_ACCOUNT.read_text(encoding="utf-8")
    for bucket in set(tool.FETCH_BUCKETS.values()) | set(tool.DRAIN_BUCKETS.values()):
        assert f'"{bucket}"' in source, bucket
    for key in ("at_harness_fetch", "after_drain", "after_drain_fetch", "after_drain_note"):
        assert f'"{key}"' in source, key


def test_rule_constants() -> None:
    assert (tool.MIN_PAIRS, tool.PAIRING_TOLERANCE_S, tool.RATE_BOUND_PROXIMITY_S) == (100, 1.0, 5.0)


def test_summary_csv_has_one_row_per_run_in_pair_order(outputs: dict[str, Any]) -> None:
    with (outputs["out"] / "summary.csv").open(encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == tool.COLUMNS
    assert [r["run_id"] for r in outputs["rows"]] == [
        "cmp-yocto-p1", "cmp-debian13-p1", "cmp-debian13-p2", "cmp-yocto-p2", "cmp-yocto-p3", "cmp-debian13-p3",
    ]
    assert {r["scenario"] for r in outputs["rows"]} == {"yocto", "debian13"}
    for gone in ("accepted_rate_msg_s", "accepted_in_window", "clock_offset_s", "clock_offset_uncertainty_s",
                 "mem_load_window_start_utc", "mem_load_window_end_utc"):
        assert gone not in tool.COLUMNS, gone
    for column in ("load_duration_monotonic_s", "load_window_utc_span_s", "wall_clock_step_s",
                   "clock_pairing_marker_lag_s", "clock_pairing_pairs", "clock_pairing_discrepancy_s",
                   "load_window_reason", "accepted_rate_reason", "published_rate_msg_s",
                   "mem_loadfile_median_mib", "mem_loadfile_max_mib", "mem_loadfile_samples") + WINDOW_COLUMNS + RATE_COLUMNS:
        assert column in tool.COLUMNS, column


def test_deltas_memory_df_and_harness_cells_of_a_complete_run(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p1"]
    assert (row["pair"], row["order_in_pair"], row["seed"]) == ("1", "1", "101")
    assert row["boot_ssh_s"] == "22.5"
    assert row["stack_ready_s"] == "383.0"
    assert row["gateway_functional_s"] == "399.0"
    assert row["drain_s"] == "60.5"
    assert (row["mem_rest_median_mib"], row["mem_rest_max_mib"], row["mem_rest_samples"]) == ("410.0", "420.0", "3")
    assert (row["df_root_used_kib"], row["df_docker_used_kib"]) == ("352256", "2097152")
    assert row["sent_valid"] == "6720" and row["delivered_unique"] == "6700"
    assert row["delivery_rate"] == "0.9970"
    assert (row["lost"], row["late_confirmations"], row["duplicates"], row["double_accepted"]) == ("20", "3", "1", "0")
    assert (row["latency_ms_p50"], row["latency_ms_p95"], row["latency_samples"]) == ("123.4", "456.7", "6700")
    assert (row["drain_result"], row["harness_exit"]) == ("quiet", "0")


def test_window_on_monotonic_clocks_and_memory_inside_it(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p1"]
    assert row["load_duration_monotonic_s"] == "600.100"
    assert row["load_window_utc_span_s"] == "600.100" and row["wall_clock_step_s"] == "0.000"
    assert row["clock_pairing_marker_lag_s"] == "0.030"
    assert row["clock_pairing_pairs"] == "120"
    assert row["clock_pairing_discrepancy_s"] == "0.005"   # the pairs' 5 ms minimum transit
    assert row["load_window_reason"] == ""
    assert (row["mem_load_window_start_guest_s"], row["mem_load_window_end_guest_s"]) == ("507.900", "1108.000")
    # Three of the seven lines have uptime_s inside [507.9, 1108.0]; the four outside are 2000 MiB.
    assert (row["mem_load_samples"], row["mem_load_median_mib"], row["mem_load_max_mib"]) == ("3", "1110.0", "1120.0")
    assert (row["mem_loadfile_samples"], row["mem_loadfile_median_mib"], row["mem_loadfile_max_mib"]) == ("7", "2000.0", "2000.0")
    # The fractional MiB value (1536512 kB) inside the Debian pair-1 window.
    row = outputs["by_id"]["cmp-debian13-p1"]
    assert (row["mem_load_samples"], row["mem_load_median_mib"], row["mem_load_max_mib"]) == ("3", "1210.0", "1500.5")


def test_wall_clock_step_is_reported_and_leaves_the_window_available(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-debian13-p1"]
    assert row["load_duration_monotonic_s"] == "600.100"
    assert row["load_window_utc_span_s"] == "587.100"
    assert row["wall_clock_step_s"] == "-13.000"
    assert row["load_window_reason"] == ""
    assert (row["mem_load_window_start_guest_s"], row["mem_load_window_end_guest_s"]) == ("507.900", "1108.000")
    assert (row["accepted_between_samples"], row["accepted_rate_span_s"], row["accepted_rate_est_msg_s"]) == ("4800", "600.000", "8.00")
    assert row["published_rate_msg_s"] == "11.20"   # 6720 / 600.1, not / 587.1 and not / 600


def test_rate_is_an_estimate_between_the_boundary_samples(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p1"]
    # Row 7 (507.4 s) is the last at or before 507.9; row 607 (1107.4 s) the last at or before 1108.0.
    assert row["accepted_between_samples"] == str(7 * (END_ROW - START_ROW))
    assert row["accepted_rate_span_s"] == "600.000"
    assert (row["accepted_rate_start_gap_s"], row["accepted_rate_end_gap_s"]) == ("0.500", "0.600")
    assert row["accepted_rate_est_msg_s"] == "7.00"
    assert row["accepted_rate_reason"] == ""
    assert row["published_rate_msg_s"] == "11.20"
    # The raw directory found only through the timeline's harness.raw_dir: window and memory
    # available, but a 20 s hole before the window end refuses the estimate.
    row = outputs["by_id"]["cmp-debian13-p3"]
    assert row["load_window_reason"] == "" and row["mem_load_samples"] == "3"
    for column in RATE_COLUMNS:
        assert row[column] == "", column
    assert "20.600 s before it" in row["accepted_rate_reason"] and "window end" in row["accepted_rate_reason"]
    assert row["published_rate_msg_s"] == "11.20"
    assert "cmp-debian13-p3: rate estimate unavailable" in outputs["stderr"]


def test_window_unavailable_when_the_clocks_cannot_be_paired(outputs: dict[str, Any]) -> None:
    # Marker not ok: the duration and the pairs are still reported, nothing window-bounded is.
    row = outputs["by_id"]["cmp-yocto-p2"]
    assert row["load_window_reason"] == "controller marker not ok"
    assert row["load_duration_monotonic_s"] == "600.100" and row["clock_pairing_pairs"] == "120"
    for column in WINDOW_COLUMNS + RATE_COLUMNS:
        assert row[column] == "", column
    assert row["accepted_rate_reason"] == "measured window unavailable"
    assert (row["mem_loadfile_samples"], row["mem_loadfile_median_mib"]) == ("7", "2000.0")
    assert row["published_rate_msg_s"] == "11.20"
    assert "cmp-yocto-p2: measured window unavailable: controller marker not ok" in outputs["stderr"]
    # Pairing discrepancy of 2 s: reported, and the window refused.
    row = outputs["by_id"]["cmp-yocto-p3"]
    assert row["clock_pairing_discrepancy_s"] == "2.005"
    assert row["load_window_reason"] == "pairing discrepancy 2.005 s exceeds 1.0 s"
    for column in WINDOW_COLUMNS + RATE_COLUMNS:
        assert row[column] == "", column
    assert row["accepted_rate_reason"] == "measured window unavailable"


def test_reconciliation_columns_follow_the_accounting_buckets(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p1"]
    assert (row["fetch_accepted_in_time"], row["fetch_accepted_late"], row["fetch_no_outcome"]) == ("6690", "5", "25")
    assert (row["drain_accepted_in_time"], row["drain_accepted_late"], row["drain_accepted_no_ack"],
            row["drain_no_outcome"]) == ("6690", "28", "1", "1")
    assert row["drain_fetch_claim"] == "fetched"
    row = outputs["by_id"]["cmp-debian13-p1"]
    assert (row["fetch_accepted_in_time"], row["fetch_accepted_late"], row["fetch_no_outcome"]) == ("6718", "0", "2")
    assert (row["drain_accepted_in_time"], row["drain_accepted_late"], row["drain_accepted_no_ack"],
            row["drain_no_outcome"]) == ("6718", "2", "0", "0")
    assert row["drain_fetch_claim"] == "unstated"
    assert (row["delivered_unique"], row["lost"], row["late_confirmations"]) == ("6718", "2", "0")


def test_missing_inputs_leave_cells_empty_with_a_warning(outputs: dict[str, Any]) -> None:
    stderr = outputs["stderr"]
    assert "WARNING" in stderr
    # No load-phase sampler file, a null `ready`, no accounting.
    row = outputs["by_id"]["cmp-yocto-p3"]
    assert row["stack_ready_s"] == "" and row["gateway_functional_s"] == ""
    assert row["boot_ssh_s"] == "21.0"
    for column in ("mem_load_median_mib", "mem_load_max_mib", "mem_load_samples",
                   "mem_loadfile_median_mib", "mem_loadfile_max_mib", "mem_loadfile_samples"):
        assert row[column] == "", column
    assert row["mem_rest_median_mib"] == "450.0"
    for column in list(tool.FETCH_BUCKETS) + list(tool.DRAIN_BUCKETS) + ["drain_fetch_claim"]:
        assert row[column] == "", column
    assert (row["drain_result"], row["harness_exit"]) == ("gave-up", "1")
    assert "cmp-yocto-p3" in stderr and "meminfo-load.csv" in stderr and "accounting.json" in stderr
    # No harness raw directory and no per-run row: nothing of the window or the harness, no zero.
    row = outputs["by_id"]["cmp-debian13-p2"]
    for column in list(tool.HARNESS_COLUMNS) + ["published_rate_msg_s", "load_duration_monotonic_s",
                                                 "load_window_utc_span_s", "wall_clock_step_s",
                                                 "clock_pairing_marker_lag_s", "clock_pairing_pairs",
                                                 "clock_pairing_discrepancy_s"] + list(WINDOW_COLUMNS) + list(RATE_COLUMNS):
        assert row[column] == "", column
    assert row["load_window_reason"] == "harness manifest.json missing"
    assert row["accepted_rate_reason"] == "measured window unavailable"
    assert row["mem_loadfile_samples"] == "7" and row["fetch_accepted_in_time"] == "6690"
    assert "cmp-debian13-p2: no harness raw directory" in stderr and "cmp-debian13-p2-harness" in stderr
    # The post-drain tail was not read completely: the drain buckets stay empty, the claim is shown.
    row = outputs["by_id"]["cmp-yocto-p2"]
    assert (row["fetch_accepted_in_time"], row["fetch_accepted_late"], row["fetch_no_outcome"]) == ("6705", "5", "10")
    for column in tool.DRAIN_BUCKETS:
        assert row[column] == "", column
    assert row["drain_fetch_claim"] == "not-fetched"
    assert "cmp-yocto-p2: accounting.json: after_drain is null" in stderr and "not-fetched" in stderr
    # The df record without the docker line.
    assert outputs["by_id"]["cmp-debian13-p3"]["df_docker_used_kib"] == ""
    assert "df-before-load.txt: no line for /var/lib/docker" in stderr
    # A clock_offset.json from the earlier rule is ignored without a word.
    assert "clock_offset" not in stderr


@pytest.mark.parametrize("case, manifest, events, reason, duration", [
    ("lag above tolerance", {"lag_s": 2.5}, {}, "controller marker lag 2.500 s above its tolerance 2.000 s", "600.100"),
    ("marker not ok", {"marker_ok": False}, {}, "controller marker not ok", "600.100"),
    ("fewer than 100 pairs", {}, {"pairs": 50}, "only 50 host-guest event pairs (fewer than 100)", "600.100"),
    ("pairing discrepancy", {}, {"extra_offset_ns": 2_000_000_000}, "pairing discrepancy 2.005 s exceeds 1.0 s", "600.100"),
    ("no monotonic start", {"started_ns": None}, {}, "measured_started_monotonic_ns/finished_monotonic_ns", ""),
    ("no guest instant", {"end_ns": None}, {}, "manifest without controller_monotonic_at_run_end_ns", "600.100"),
])
def test_each_pairing_failure_makes_the_window_unavailable(tmp_path: Path, case: str, manifest: dict[str, Any],
                                                            events: dict[str, Any], reason: str, duration: str) -> None:
    per_run = build_root(tmp_path)
    write_raw(tmp_path, RUNS[0], manifest=manifest, events=events)
    proc = run_tool(tmp_path, per_run, tmp_path / "out")
    assert proc.returncode == 0, proc.stderr
    row = summary_rows(tmp_path / "out")["cmp-yocto-p1"]
    assert reason in row["load_window_reason"], (case, row["load_window_reason"])
    assert row["load_duration_monotonic_s"] == duration, case
    for column in WINDOW_COLUMNS + RATE_COLUMNS:
        assert row[column] == "", (case, column)
    assert row["accepted_rate_reason"] == "measured window unavailable", case
    assert row["published_rate_msg_s"] == ("11.20" if duration else ""), case
    assert (row["mem_loadfile_samples"], row["mem_rest_median_mib"]) == ("7", "410.0"), case
    assert "cmp-yocto-p1: measured window unavailable" in proc.stderr, case
    # A clock_offset.json from the earlier rule changes nothing and draws no warning.
    write(tmp_path / "runs" / "cmp-yocto-p1" / "clock_offset.json", json.dumps({"offset_guest_minus_host_s": 3.5}))
    proc = run_tool(tmp_path, per_run, tmp_path / "out2")
    assert proc.returncode == 0 and "clock_offset" not in proc.stderr
    assert summary_rows(tmp_path / "out2")["cmp-yocto-p1"] == row


@pytest.mark.parametrize("case, metrics, reason", [
    ("hole before the start", {"omit": frozenset(range(1, 8))},
     "last metrics sample before the window start is 7.500 s before it (more than 5.0 s)"),
    ("hole before the end", {"omit": frozenset(range(588, 608))},
     "last metrics sample before the window end is 20.600 s before it (more than 5.0 s)"),
    ("metrics start after the window", {"omit": frozenset(range(0, 8))}, "no metrics sample at or before the window start"),
    ("not time-ordered", {"swap": True}, "metrics not time-ordered"),
    ("counter decreased", {"decrease_at": END_ROW}, "the accepted counter decreased between the boundary samples (149 -> 99)"),
])
def test_each_boundary_failure_makes_the_rate_unavailable(tmp_path: Path, case: str, metrics: dict[str, Any], reason: str) -> None:
    per_run = build_root(tmp_path)
    write_raw(tmp_path, RUNS[0], metrics=metrics)
    proc = run_tool(tmp_path, per_run, tmp_path / "out")
    assert proc.returncode == 0, proc.stderr
    row = summary_rows(tmp_path / "out")["cmp-yocto-p1"]
    assert row["accepted_rate_reason"] == reason, case
    for column in RATE_COLUMNS:
        assert row[column] == "", (case, column)
    # The window itself, and the memory inside it, do not depend on the metrics.
    assert row["load_window_reason"] == "" and row["mem_load_samples"] == "3", case
    assert row["published_rate_msg_s"] == "11.20", case
    assert "cmp-yocto-p1: rate estimate unavailable" in proc.stderr, case


def test_a_sampler_file_without_uptime_leaves_the_window_memory_empty(tmp_path: Path) -> None:
    per_run = build_root(tmp_path)
    write(tmp_path / "runs" / "cmp-yocto-p1" / "meminfo-load.csv",
          meminfo_text(load_samples([1100, 1120, 1110]), with_uptime=False))
    proc = run_tool(tmp_path, per_run, tmp_path / "out")
    assert proc.returncode == 0, proc.stderr
    row = summary_rows(tmp_path / "out")["cmp-yocto-p1"]
    assert (row["mem_load_samples"], row["mem_load_median_mib"]) == ("", "")
    assert (row["mem_load_window_start_guest_s"], row["mem_loadfile_samples"]) == ("507.900", "7")
    assert "no uptime_s column" in proc.stderr and "cmp-yocto-p1" in proc.stderr


def test_json_rows_and_scenario_aggregates(outputs: dict[str, Any]) -> None:
    doc = outputs["json"]
    assert doc["columns"] == tool.COLUMNS
    assert doc["rules"] == {"min_pairs": 100, "pairing_tolerance_s": 1.0, "rate_bound_proximity_s": 5.0}
    assert len(doc["runs"]) == 6 and doc["runs"][0]["run_id"] == "cmp-yocto-p1"
    first = doc["runs"][0]
    assert first["mem_load_median_mib"] == 1110.0 and first["accepted_between_samples"] == 4200
    assert first["load_duration_monotonic_s"] == 600.1 and first["clock_pairing_discrepancy_s"] == 0.005
    assert first["mem_load_window_start_guest_s"] == 507.9 and first["load_window_reason"] is None
    assert doc["runs"][1]["wall_clock_step_s"] == -13.0
    assert doc["runs"][3]["load_window_reason"] == "controller marker not ok" and doc["runs"][3]["mem_load_samples"] is None
    assert doc["runs"][4]["stack_ready_s"] is None and doc["runs"][4]["mem_load_samples"] is None
    yocto, debian = doc["scenarios"]["yocto"], doc["scenarios"]["debian13"]
    assert yocto["n_runs"] == 3 and debian["n_runs"] == 3
    assert yocto["metrics"]["mem_rest_median_mib"] == {"median": 430.0, "min": 410.0, "max": 450.0, "n": 3}
    assert yocto["metrics"]["boot_ssh_s"] == {"median": 22.5, "min": 21.0, "max": 23.0, "n": 3}
    # Two values only: the median of what exists is their mean, and n says so.
    assert yocto["metrics"]["stack_ready_s"] == {"median": 386.5, "min": 383.0, "max": 390.0, "n": 2}
    # Only the pair-1 Yocto window is available: one value.
    assert yocto["metrics"]["mem_load_median_mib"] == {"median": 1110.0, "min": 1110.0, "max": 1110.0, "n": 1}
    assert yocto["metrics"]["accepted_rate_est_msg_s"] == {"median": 7.0, "min": 7.0, "max": 7.0, "n": 1}
    assert yocto["metrics"]["load_duration_monotonic_s"] == {"median": 600.1, "min": 600.1, "max": 600.1, "n": 3}
    assert yocto["metrics"]["clock_pairing_discrepancy_s"] == {"median": 0.005, "min": 0.005, "max": 2.005, "n": 3}
    assert debian["metrics"]["wall_clock_step_s"] == {"median": -6.5, "min": -13.0, "max": 0.0, "n": 2}
    assert debian["metrics"]["mem_load_median_mib"] == {"median": 1215.0, "min": 1210.0, "max": 1220.0, "n": 2}
    # 1365.25 at one decimal, by round-half-to-even.
    assert debian["metrics"]["mem_load_max_mib"] == {"median": 1365.2, "min": 1230.0, "max": 1500.5, "n": 2}
    assert debian["metrics"]["accepted_rate_est_msg_s"] == {"median": 8.0, "min": 8.0, "max": 8.0, "n": 1}
    assert debian["metrics"]["mem_loadfile_max_mib"] == {"median": 2000.0, "min": 2000.0, "max": 2000.0, "n": 3}
    assert debian["metrics"]["df_docker_used_kib"] == {"median": 2097176.0, "min": 2097152, "max": 2097200, "n": 2}
    assert yocto["metrics"]["drain_accepted_late"] == {"median": 28, "min": 28, "max": 28, "n": 1}
    assert yocto["metrics"]["lost"] == {"median": 20, "min": 10, "max": 30, "n": 3}
    assert any("latency_count" in note for note in doc["notes"])
    assert doc["warnings"] and all(isinstance(w, str) for w in doc["warnings"])


def test_table_shows_both_scenarios_runs_medians_ranges_and_notes(outputs: dict[str, Any]) -> None:
    table = outputs["table"]
    assert "n=3 per scenario" in table and "one QEMU/TCG profile" in table
    assert "no statistical significance claimed" in table
    assert "Yocto median" in table and "Debian 13 median" in table and "Debian 13 min–max" in table
    rows = table_rows(table)
    mem_rest = rows["Guest memory used at rest, median, MiB (`mem_rest_median_mib`)"]
    assert mem_rest == ["410.0 / 430.0 / 450.0", "430.0", "410.0–450.0",
                        "610.0 / 600.0 / 620.0", "610.0", "600.0–620.0"]
    mem_load = rows["Guest memory used inside the measured window, median, MiB (`mem_load_median_mib`)"]
    assert mem_load == ["1110.0 / — / —", "1110.0", "1110.0–1110.0", "1210.0 / — / 1220.0", "1215.0", "1210.0–1220.0"]
    assert rows["Whole load-phase sampler file, samples (`mem_loadfile_samples`)"][:3] == ["7 / 7 / —", "7", "7–7"]
    assert rows["Launch to stack ready (/ready 200), s (`stack_ready_s`)"][:3] == ["383.0 / 390.0 / —", "386.5", "383.0–390.0"]
    assert rows["Measured window on the host monotonic clock, s (`load_duration_monotonic_s`)"] == [
        "600.100 / 600.100 / 600.100", "600.100", "600.100–600.100", "600.100 / — / 600.100", "600.100", "600.100–600.100"]
    assert rows["Host wall-clock step inside the window: UTC span − monotonic duration, s (`wall_clock_step_s`)"][3:] == [
        "-13.000 / — / 0.000", "-6.500", "-13.000–0.000"]
    assert rows["Clock cross-check: window end from the pairs − from the marker, s (`clock_pairing_discrepancy_s`)"][:3] == [
        "0.005 / 0.005 / 2.005", "0.005", "0.005–2.005"]
    assert rows["Measured window start on the guest monotonic clock, s (`mem_load_window_start_guest_s`)"] == [
        "507.900 / — / —", "507.900", "507.900–507.900", "507.900 / — / 507.900", "507.900", "507.900–507.900"]
    assert rows["Estimated accepted rate between the boundary samples, msg/s (`accepted_rate_est_msg_s`)"] == [
        "7.00 / — / —", "7.00", "7.00–7.00", "8.00 / — / —", "8.00", "8.00–8.00"]
    assert rows["Window end − end boundary sample, s (`accepted_rate_end_gap_s`)"][:2] == ["0.600 / — / —", "0.600"]
    assert rows["Published rate, msg/s (sent_valid / load_duration_monotonic_s) (`published_rate_msg_s`)"] == [
        "11.20 / 11.20 / 11.20", "11.20", "11.20–11.20", "11.20 / — / 11.20", "11.20", "11.20–11.20"]
    assert rows["Why the measured window is unavailable (`load_window_reason`)"] == [
        "— / controller marker not ok / pairing discrepancy 2.005 s exceeds 1.0 s", "—", "—",
        "— / harness manifest.json missing / —", "—", "—"]
    assert rows["Why the rate estimate is unavailable (`accepted_rate_reason`)"][0] == \
        "— / measured window unavailable / measured window unavailable"
    assert "20.600 s before it" in rows["Why the rate estimate is unavailable (`accepted_rate_reason`)"][3]
    assert rows["After the drain: accepted late (`drain_accepted_late`)"] == ["28 / — / —", "28", "28–28", "2 / 28 / 28", "28", "2–28"]
    assert rows["Lost (no confirmation within the deadline) (`lost`)"] == ["20 / 10 / 30", "20", "10–30", "2 / — / 4", "3", "2–4"]
    assert rows["Post-drain event log fetch, as the driver said (`drain_fetch_claim`)"] == [
        "fetched / not-fetched / —", "—", "—", "unstated / fetched / fetched", "—", "—"]
    assert rows["Drain result (`drain_result`)"] == ["quiet / quiet / gave-up", "—", "—", "quiet / quiet / quiet", "—", "—"]
    for phrase in (
        # The earlier notes, all kept.
        "Probe cadences: ssh 2 s, ready 5 s, accept 1 s", "host-monotonic",
        "controller reception → Ditto confirmation", "no confirmation within the harness's deadline",
        "whole gateway guest", "latency_count", "df -P -k", "Median: the middle value of three",
        "An empty cell is an unavailable value, never a zero", "reported apart from the deadline accounting",
        "accepted_no_ack_time", "zero by construction", "`drain_fetch_claim`", "transparency only",
        "Warm-up, the confirmation window and the drain are outside it",
        # Rule 1: the window on monotonic clocks.
        "MONOTONIC clocks", "finished_monotonic_ns − measured_started_monotonic_ns",
        "controller_monotonic_at_run_end_ns", "at least 100 message ids", "within 1.0 s of the marker",
        "600 s is never assumed", "never used as the duration or the bounds", "`wall_clock_step_s`",
        "CLOCK_BOOTTIME, equal to the controller's CLOCK_MONOTONIC while the guest never suspends",
        "window start <= uptime_s <= window end",
        # Rule 2: the estimate between boundary samples.
        "estimated rate between the two boundary samples (gaps reported), not an exact count inside the window",
        "within 5.0 s before its bound", "`accepted_rate_reason`",
        "published_rate_msg_s = sent_valid / load_duration_monotonic_s",
        "the simulator's publications during the measured run",
    ):
        assert phrase in table, phrase
    assert "clock_offset.json" not in table and "delivered_unique / 600" not in table
    assert "Warnings while summarising:" in table


def test_exit_codes(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = run_tool(empty, None, tmp_path / "out1")
    assert proc.returncode == 2 and "no run directory" in proc.stderr
    only_files = tmp_path / "files"
    write(only_files / "runs" / "stray.txt", "x\n")
    assert run_tool(only_files, None, tmp_path / "out2").returncode == 2
    broken = tmp_path / "broken"
    build_root(broken)
    write(broken / "runs" / "cmp-yocto-p2" / "timeline.json", "{not json")
    proc = run_tool(broken, broken / "processed" / "per_run.csv", tmp_path / "out3")
    assert proc.returncode == 2 and "timeline" in proc.stderr and "cmp-yocto-p2" in proc.stderr
    assert not (tmp_path / "out3").exists()
    # A per-run CSV that does not exist, or none at all, is a warning and empty harness cells.
    good = tmp_path / "good"
    build_root(good)
    proc = run_tool(good, good / "processed" / "absent.csv", tmp_path / "out4")
    assert proc.returncode == 0 and "WARNING" in proc.stderr and "absent.csv" in proc.stderr
    rows = summary_rows(tmp_path / "out4")
    assert len(rows) == 6 and all(r["sent_valid"] == "" and r["published_rate_msg_s"] == "" for r in rows.values())
    assert all(r["boot_ssh_s"] != "" for r in rows.values())
    assert rows["cmp-yocto-p1"]["accepted_rate_est_msg_s"] == "7.00"  # the window figures do not need the per-run CSV
    proc = run_tool(good, None, tmp_path / "out5")
    assert proc.returncode == 0 and "no --per-run-csv" in proc.stderr
    # Event logs missing: no pairs, the window refused, everything else written.
    unpaired = tmp_path / "unpaired"
    build_root(unpaired)
    (unpaired / "harness" / "raw" / "nominal-yocto-p1" / "events.jsonl").unlink()
    proc = run_tool(unpaired, unpaired / "processed" / "per_run.csv", tmp_path / "out6")
    assert proc.returncode == 0 and "events.jsonl: missing" in proc.stderr
    row = summary_rows(tmp_path / "out6")["cmp-yocto-p1"]
    assert row["clock_pairing_pairs"] == "0" and "only 0 host-guest event pairs" in row["load_window_reason"]
    assert row["mem_load_samples"] == "" and row["load_duration_monotonic_s"] == "600.100"


def plan_text(run_ids: list[Any]) -> str:
    """A plan in the harness's shape: entries are objects with a run_id (a plain id is accepted too)."""
    entries = [rid if isinstance(rid, str) else
               {"run_id": rid["run_id"], "comparison": {"scenario": rid["scenario"], "pair": rid["pair"], "order_in_pair": rid["order"]},
                "condition_id": "nominal", "duration_s": 600, "status": "planned"} for rid in run_ids]
    return json.dumps({"plan_version": 2, "protocol_version": "2.1", "master_seed": 2026101801,
                       "comparison": {"pairs": 3}, "conditions": [], "runs": entries}, indent=1)


def test_plan_selects_the_runs_in_its_order_and_names_the_rest(tmp_path: Path) -> None:
    per_run = build_root(tmp_path)
    # The plan names four runs in its own order; one of them has no directory; the three
    # other directories under runs/ (a stray earlier attempt among them) are not in it.
    plan = tmp_path / "plan-a02.json"
    write(plan, plan_text([RUNS[5], RUNS[0], {"run_id": "cmp-ghost-p9", "scenario": "yocto", "pair": 9, "order": 1},
                           "cmp-debian13-p1"]))
    out = tmp_path / "out"
    proc = run_tool(tmp_path, per_run, out, plan)
    assert proc.returncode == 0, proc.stderr
    with (out / "summary.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["run_id"] for r in rows] == ["cmp-debian13-p3", "cmp-yocto-p1", "cmp-debian13-p1"]
    assert "planned run cmp-ghost-p9: no directory at" in proc.stderr and "no row" in proc.stderr
    assert "cmp-ghost-p9" not in {r["run_id"] for r in rows}
    note = "ignored, not in the plan: cmp-debian13-p2, cmp-yocto-p2, cmp-yocto-p3"
    assert f"note: {note}" in proc.stdout
    for name in ("cmp-debian13-p2", "cmp-yocto-p2", "cmp-yocto-p3"):
        assert name not in proc.stderr  # ignored silently: no warning about their inputs either
    doc = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    sha = hashlib.sha256(plan.read_bytes()).hexdigest()
    assert doc["plan"]["path"] == str(plan) and doc["plan"]["sha256"] == sha
    assert doc["plan"]["run_ids"] == ["cmp-debian13-p3", "cmp-yocto-p1", "cmp-ghost-p9", "cmp-debian13-p1"]
    assert doc["plan"]["ignored_not_in_plan"] == ["cmp-debian13-p2", "cmp-yocto-p2", "cmp-yocto-p3"]
    assert doc["plan"]["missing_directories"] == ["cmp-ghost-p9"]
    assert [r["run_id"] for r in doc["runs"]] == ["cmp-debian13-p3", "cmp-yocto-p1", "cmp-debian13-p1"]
    assert doc["scenarios"]["yocto"]["n_runs"] == 1 and doc["scenarios"]["debian13"]["n_runs"] == 2
    assert note in doc["notes"] and any("cmp-ghost-p9" in w for w in doc["warnings"])
    table = (out / "table.md").read_text(encoding="utf-8")
    assert f"Plan `{plan}` (sha256 `{sha}`), 4 planned run(s)." in table.splitlines()[2]
    assert "n=1 (Yocto) and n=2 (Debian 13)" in table and f"- {note}" in table
    # The table keeps the plan's order within each scenario: Debian pair 3 before pair 1.
    rows_md = table_rows(table)
    assert rows_md["Guest memory used at rest, median, MiB (`mem_rest_median_mib`)"] == [
        "410.0", "410.0", "410.0–410.0", "620.0 / 610.0", "615.0", "610.0–620.0"]
    assert "Debian 13: runs in plan order" in table
    # Without --plan nothing changes: six rows in pair order, no plan record.
    proc = run_tool(tmp_path, per_run, tmp_path / "out-all")
    assert proc.returncode == 0 and "note:" not in proc.stdout
    doc = json.loads((tmp_path / "out-all" / "summary.json").read_text(encoding="utf-8"))
    assert doc["plan"] is None and len(doc["runs"]) == 6
    assert "No plan given: every run directory under the root." in (tmp_path / "out-all" / "table.md").read_text(encoding="utf-8")
    # A plan none of whose runs has a directory, or an unreadable plan, is exit 2.
    write(tmp_path / "plan-none.json", plan_text(["nowhere-1", "nowhere-2"]))
    assert tool.main(["--measure-root", str(tmp_path), "--plan", str(tmp_path / "plan-none.json"), "--out", str(tmp_path / "o3")]) == 2
    write(tmp_path / "plan-bad.json", "{not json")
    assert tool.main(["--measure-root", str(tmp_path), "--plan", str(tmp_path / "plan-bad.json"), "--out", str(tmp_path / "o4")]) == 2
    write(tmp_path / "plan-noruns.json", json.dumps({"plan_version": 2}))
    assert tool.main(["--measure-root", str(tmp_path), "--plan", str(tmp_path / "plan-noruns.json"), "--out", str(tmp_path / "o5")]) == 2


def test_in_process_entry_point_returns_the_exit_code(tmp_path: Path) -> None:
    per_run = build_root(tmp_path)
    assert tool.main(["--measure-root", str(tmp_path), "--per-run-csv", str(per_run), "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "table.md").is_file()
    assert tool.main(["--measure-root", str(tmp_path / "nowhere"), "--out", str(tmp_path / "o2")]) == 2
