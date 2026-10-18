"""Cases for tools/compare/measure_summary.py, the table builder of the comparison
measurement.

A synthetic measurement root is built with six runs (three per scenario, in the
Y-D-D-Y-Y-D pair order) whose inputs carry values chosen so that every derived figure
is known in advance: the host-monotonic deltas; the KiB-to-MiB conversion; a harness
manifest with a 600 s measured window and a controller-metrics counter that climbs by a
known step per second across it, so the accepted count inside the window is exact; a
non-zero (and once negative) guest-minus-host clock offset, with sampler lines placed
before, inside and after the converted window so that only the inside ones may count;
accounting buckets with distinct values; the two df mount points; and a per-run CSV
written under the harness analyser's own column list (imported, so that a renamed
column breaks these cases rather than the tool silently). Runs with a missing sampler
file, a null `ready`, no clock offset, no harness raw directory, no per-run row, no
accounting, or an accounting whose post-drain tail was not read must leave the cells
concerned empty, never zero, with a WARNING naming the missing input. The tool runs
under this interpreter on any host; nothing here touches a guest or a real measurement.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
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
# The harness's measured window, harness-host UTC, 600 s.
WINDOW_START = datetime(2026, 10, 20, 10, 2, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 10, 20, 10, 12, 0, tzinfo=timezone.utc)
S = WINDOW_START.timestamp()
E = WINDOW_END.timestamp()
OUTSIDE_MIB = 2000
PARTIAL_NOTE = ("the post-drain event log is on disk but its fetch did not succeed: what it "
                "holds may be a partial tail, and no figure is claimed from it")


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


def meminfo_text(samples: list[tuple[int, int]]) -> str:
    """The sampler's file for (guest epoch, used kB) samples, with its closing line."""
    rows = ["ts_utc,epoch_s,mem_total_kb,mem_available_kb,mem_used_kb"]
    for epoch, used in samples:
        rows.append(f"{utc_s(epoch)},{epoch},{MEM_TOTAL_KB},{MEM_TOTAL_KB - used},{used}")
    rows.append(f"# end epoch_s={samples[-1][0] + 1} samples={len(samples)}")
    return "\n".join(rows) + "\n"


def load_samples(offset: float, inside_mib: list[float]) -> tuple[list[tuple[int, int]], list[int]]:
    """Seven guest-stamped samples: two before the converted window, three inside, two after.

    Returns (samples, the three inside epochs)."""
    lo, hi = math.ceil(S + offset), math.floor(E + offset)
    inside = [lo, (lo + hi) // 2, hi]
    outside_before, outside_after = [lo - 10, lo - 1], [hi + 1, hi + 10]
    samples = [(t, OUTSIDE_MIB * MIB_KB) for t in outside_before]
    samples += list(zip(inside, mib(inside_mib)))
    samples += [(t, OUTSIDE_MIB * MIB_KB) for t in outside_after]
    return samples, inside


def metrics_text(step: int, base: int = 100) -> str:
    """1 Hz controller metrics whose cumulative `accepted` climbs by `step` per sample.

    Sample k is stamped S - 10.6 + k, so the last sample at or before the window start is
    k=10 (S - 0.6) and the last at or before its end is k=610 (S + 599.4): 600 s apart,
    600*step accepted between them, while samples after the window keep climbing."""
    header = ("ts_utc,accepted,rejected,duplicate,failed,dropped,queue_depth,received,in_progress,"
              "processing_errors,unacked,mqtt_connection,mqtt_subscribed,started_at,wall_utc,uptime_s,monotonic_ns")
    rows = [header]
    for k in range(0, 621):
        t = S - 10.6 + k
        accepted = base + step * k
        rows.append(f"{utc_ms(t)},{accepted},0,0,0,0,3,{accepted + 5},1,0,4,1,true,"
                    f"{utc_ms(S - 300)},{utc_ms(t + 0.3)},{300 + k:.3f},{int((300 + k) * 1e9)}")
    return "\n".join(rows) + "\n"


def manifest_doc(harness_id: str) -> dict[str, Any]:
    return {
        "run_id": harness_id,
        "measured_window_utc": {"start": utc_ms(S), "end": utc_ms(E)},
        "measured_window_clock": "harness-host wall clock; used ONLY to window 1 Hz samples",
        "duration_s": 600,
        "warmup_s": 120,
        "confirmation_window_s": 60,
        "started_utc": utc_ms(S - 120.2),
        "finished_utc": utc_ms(E + 60.4),
    }


# scenario, run_id, pair, order, seed, launch, (ssh_ok, ready, func_twin) relative to launch,
# drain seconds, rest MiB, load MiB inside the window (None = file missing), df (root, docker),
# drain result, harness exit, harness run id (None = no per-run row), clock offset
# (None = clock_offset.json missing) and uncertainty, metrics step (None = no harness raw
# directory), whether the raw directory lives elsewhere and is only declared by the timeline,
# accounting ("full", "sparse", "tail-not-read" or None = file missing).
RUNS: list[dict[str, Any]] = [
    dict(scenario="yocto", run_id="cmp-yocto-p1", pair=1, order=1, seed=101, launch=10.0,
         ssh=22.5, ready=383.0, func=399.0, drain=60.5, rest=[400, 410, 420], load=[1100, 1120, 1110],
         df=(352256, 2097152), drain_result="quiet", harness_exit=0, harness_id="nominal-yocto-p1",
         offset=3.5, uncertainty=0.05, step=7, raw_elsewhere=False, accounting="full"),
    dict(scenario="debian13", run_id="cmp-debian13-p1", pair=1, order=2, seed=101, launch=20.0,
         ssh=46.0, ready=376.0, func=401.1, drain=61.0, rest=[600, 610, 620], load=[1200, 1500.5, 1210],
         df=(1572864, 2097152), drain_result="quiet", harness_exit=0, harness_id="nominal-debian13-p1",
         offset=-2.25, uncertainty=0.04, step=8, raw_elsewhere=False, accounting="sparse"),
    dict(scenario="debian13", run_id="cmp-debian13-p2", pair=2, order=1, seed=102, launch=5.0,
         ssh=47.5, ready=380.0, func=402.0, drain=59.0, rest=[590, 600, 610], load=[1190, 1200, 1210],
         df=(1572900, 2097200), drain_result="quiet", harness_exit=0, harness_id=None,
         offset=1.0, uncertainty=0.06, step=None, raw_elsewhere=False, accounting="full"),
    dict(scenario="yocto", run_id="cmp-yocto-p2", pair=2, order=2, seed=102, launch=5.0,
         ssh=23.0, ready=390.0, func=405.0, drain=60.0, rest=[420, 430, 440], load=[1000, 1020, 1010],
         df=(352300, 2097300), drain_result="quiet", harness_exit=0, harness_id="nominal-yocto-p2",
         offset=0.5, uncertainty=0.05, step=7, raw_elsewhere=False, accounting="tail-not-read"),
    dict(scenario="yocto", run_id="cmp-yocto-p3", pair=3, order=1, seed=103, launch=7.0,
         ssh=21.0, ready=None, func=None, drain=58.0, rest=[440, 450, 460], load=None,
         df=(352400, 2097400), drain_result="gave-up", harness_exit=1, harness_id="nominal-yocto-p3",
         offset=0.75, uncertainty=0.05, step=6, raw_elsewhere=False, accounting=None),
    dict(scenario="debian13", run_id="cmp-debian13-p3", pair=3, order=2, seed=103, launch=9.0,
         ssh=45.0, ready=378.0, func=399.5, drain=62.0, rest=[610, 620, 630], load=[1210, 1500.5, 1220],
         df=(1573000, None), drain_result="quiet", harness_exit=0, harness_id="nominal-debian13-p3",
         offset=None, uncertainty=None, step=8, raw_elsewhere=True, accounting="full"),
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


def build_root(root: Path) -> Path:
    """The measurement root with six runs, their harness raw directories and the per-run CSV."""
    for run in RUNS:
        d = root / "runs" / run["run_id"]
        write(d / "timeline.json", json.dumps(timeline(root, run), indent=1))
        rest = [(int(S) - 700 + i, used) for i, used in enumerate(mib(run["rest"]))]
        write(d / "meminfo-rest.csv", meminfo_text(rest))
        if run["load"] is not None:
            samples, _inside = load_samples(run["offset"] or 0.0, run["load"])
            write(d / "meminfo-load.csv", meminfo_text(samples))
        write(d / "df-before-load.txt", df_text(*run["df"]))
        if run["offset"] is not None:
            write(d / "clock_offset.json", json.dumps({
                "utc": utc_ms(S - 900), "host_epoch_before_s": S - 900.01, "guest_epoch_s": int(S - 900 + run["offset"]),
                "host_epoch_after_s": S - 899.99, "offset_guest_minus_host_s": run["offset"],
                "uncertainty_s": run["uncertainty"], "note": "guest `date +%s` between two host readings"}))
        if run["step"] is not None:
            raw = raw_dir_of(root, run)
            write(raw / "manifest.json", json.dumps(manifest_doc(harness_id_of(run))))
            write(raw / "controller_metrics.csv", metrics_text(run["step"]))
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


def run_tool(root: Path, per_run: Path | None, out: Path) -> subprocess.CompletedProcess:
    args = [sys.executable, "-I", str(TOOL), "--measure-root", str(root), "--out", str(out)]
    if per_run is not None:
        args += ["--per-run-csv", str(per_run)]
    return subprocess.run(args, capture_output=True, text=True, timeout=120)


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


def test_harness_columns_exist_in_the_analyser() -> None:
    assert set(tool.HARNESS_COLUMNS.values()) <= set(PER_RUN_COLUMNS)
    assert tool.HARNESS_COLUMNS["latency_samples"] == "latency_count"


def test_accounting_buckets_are_named_as_the_accounting_script_writes_them() -> None:
    source = NOMINAL_ACCOUNT.read_text(encoding="utf-8")
    for bucket in set(tool.FETCH_BUCKETS.values()) | set(tool.DRAIN_BUCKETS.values()):
        assert f'"{bucket}"' in source, bucket
    for key in ("at_harness_fetch", "after_drain", "after_drain_fetch", "after_drain_note"):
        assert f'"{key}"' in source, key


def test_summary_csv_has_one_row_per_run_in_pair_order(outputs: dict[str, Any]) -> None:
    with (outputs["out"] / "summary.csv").open(encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == tool.COLUMNS
    assert [r["run_id"] for r in outputs["rows"]] == [
        "cmp-yocto-p1", "cmp-debian13-p1", "cmp-debian13-p2", "cmp-yocto-p2", "cmp-yocto-p3", "cmp-debian13-p3",
    ]
    assert {r["scenario"] for r in outputs["rows"]} == {"yocto", "debian13"}
    # delivered_unique is no longer divided by anything; the window figures replace that column.
    assert not hasattr(tool, "LOAD_WINDOW_S")
    for column in ("accepted_in_window", "accepted_rate_span_s", "accepted_rate_msg_s", "published_rate_msg_s",
                   "mem_load_window_start_utc", "mem_load_window_end_utc", "clock_offset_s",
                   "clock_offset_uncertainty_s", "mem_loadfile_median_mib", "mem_loadfile_max_mib",
                   "mem_loadfile_samples", "fetch_accepted_in_time", "fetch_accepted_late", "fetch_no_outcome",
                   "drain_accepted_in_time", "drain_accepted_late", "drain_accepted_no_ack", "drain_no_outcome",
                   "drain_fetch_claim"):
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


def test_load_memory_counts_only_the_samples_inside_the_converted_window(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p1"]
    # Offset +3.5 s: the window [S, E] on the host is [S+3.5, E+3.5] on the guest.
    assert row["clock_offset_s"] == "3.500" and row["clock_offset_uncertainty_s"] == "0.050"
    assert row["mem_load_window_start_utc"] == "2026-10-20T10:02:03.500Z"
    assert row["mem_load_window_end_utc"] == "2026-10-20T10:12:03.500Z"
    # Three of the seven samples fall inside; the four outside are 2000 MiB and never count.
    assert (row["mem_load_samples"], row["mem_load_median_mib"], row["mem_load_max_mib"]) == ("3", "1110.0", "1120.0")
    # The whole file is reported apart and shows the difference.
    assert (row["mem_loadfile_samples"], row["mem_loadfile_median_mib"], row["mem_loadfile_max_mib"]) == ("7", "2000.0", "2000.0")
    # A negative offset moves the window the other way; the inside count stays three.
    row = outputs["by_id"]["cmp-debian13-p1"]
    assert row["clock_offset_s"] == "-2.250" and row["clock_offset_uncertainty_s"] == "0.040"
    assert row["mem_load_window_start_utc"] == "2026-10-20T10:01:57.750Z"
    assert row["mem_load_window_end_utc"] == "2026-10-20T10:11:57.750Z"
    # The fractional MiB value (1536512 kB) is inside this window and is its maximum.
    assert (row["mem_load_samples"], row["mem_load_median_mib"], row["mem_load_max_mib"]) == ("3", "1210.0", "1500.5")
    assert (row["mem_loadfile_samples"], row["mem_loadfile_median_mib"], row["mem_loadfile_max_mib"]) == ("7", "2000.0", "2000.0")


def test_rates_come_from_the_window_and_the_manifest_duration(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p1"]
    # Counter step 7 per second: last sample <= start is S-0.6, last <= end is S+599.4.
    assert (row["accepted_in_window"], row["accepted_rate_span_s"], row["accepted_rate_msg_s"]) == ("4200", "600.0", "7.00")
    assert row["published_rate_msg_s"] == "11.20"
    row = outputs["by_id"]["cmp-debian13-p1"]
    assert (row["accepted_in_window"], row["accepted_rate_span_s"], row["accepted_rate_msg_s"]) == ("4800", "600.0", "8.00")
    # The raw directory found only through the timeline's harness.raw_dir still gives the figures.
    row = outputs["by_id"]["cmp-debian13-p3"]
    assert (row["accepted_in_window"], row["accepted_rate_msg_s"], row["published_rate_msg_s"]) == ("4800", "8.00", "11.20")


def test_reconciliation_columns_follow_the_accounting_buckets(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p1"]
    assert (row["fetch_accepted_in_time"], row["fetch_accepted_late"], row["fetch_no_outcome"]) == ("6690", "5", "25")
    assert (row["drain_accepted_in_time"], row["drain_accepted_late"], row["drain_accepted_no_ack"],
            row["drain_no_outcome"]) == ("6690", "28", "1", "1")
    assert row["drain_fetch_claim"] == "fetched"
    # Buckets absent from the counter are zero by construction.
    row = outputs["by_id"]["cmp-debian13-p1"]
    assert (row["fetch_accepted_in_time"], row["fetch_accepted_late"], row["fetch_no_outcome"]) == ("6718", "0", "2")
    assert (row["drain_accepted_in_time"], row["drain_accepted_late"], row["drain_accepted_no_ack"],
            row["drain_no_outcome"]) == ("6718", "2", "0", "0")
    assert row["drain_fetch_claim"] == "unstated"
    # The deadline accounting of the analyser is untouched by the reconciliation.
    assert (row["delivered_unique"], row["lost"], row["late_confirmations"]) == ("6718", "2", "0")


def test_missing_inputs_leave_cells_empty_with_a_warning(outputs: dict[str, Any]) -> None:
    stderr = outputs["stderr"]
    assert "WARNING" in stderr
    # No load-phase sampler file, a null `ready`, no accounting: the window bounds still exist.
    row = outputs["by_id"]["cmp-yocto-p3"]
    assert row["stack_ready_s"] == "" and row["gateway_functional_s"] == ""
    assert row["boot_ssh_s"] == "21.0"
    for column in ("mem_load_median_mib", "mem_load_max_mib", "mem_load_samples",
                   "mem_loadfile_median_mib", "mem_loadfile_max_mib", "mem_loadfile_samples"):
        assert row[column] == "", column
    assert row["mem_load_window_start_utc"] == "2026-10-20T10:02:00.750Z"
    assert row["mem_rest_median_mib"] == "450.0"
    assert (row["accepted_in_window"], row["accepted_rate_msg_s"]) == ("3600", "6.00")
    for column in list(tool.FETCH_BUCKETS) + list(tool.DRAIN_BUCKETS) + ["drain_fetch_claim"]:
        assert row[column] == "", column
    assert (row["drain_result"], row["harness_exit"]) == ("gave-up", "1")
    assert "cmp-yocto-p3" in stderr and "meminfo-load.csv" in stderr and "accounting.json" in stderr
    # No clock offset: the whole file is reported, the window figure is NOT (no fallback).
    row = outputs["by_id"]["cmp-debian13-p3"]
    for column in ("mem_load_median_mib", "mem_load_max_mib", "mem_load_samples", "mem_load_window_start_utc",
                   "mem_load_window_end_utc", "clock_offset_s", "clock_offset_uncertainty_s"):
        assert row[column] == "", column
    assert (row["mem_loadfile_samples"], row["mem_loadfile_median_mib"]) == ("7", "2000.0")
    assert "cmp-debian13-p3" in stderr and "clock_offset.json" in stderr
    # No harness raw directory and no per-run row: nothing of the window or the harness, no zero.
    row = outputs["by_id"]["cmp-debian13-p2"]
    for column in list(tool.HARNESS_COLUMNS) + ["published_rate_msg_s", "accepted_in_window", "accepted_rate_span_s",
                                                 "accepted_rate_msg_s", "mem_load_median_mib", "mem_load_max_mib",
                                                 "mem_load_samples", "mem_load_window_start_utc"]:
        assert row[column] == "", column
    assert row["clock_offset_s"] == "1.000" and row["mem_loadfile_samples"] == "7"
    assert row["fetch_accepted_in_time"] == "6690"
    assert "cmp-debian13-p2: no harness raw directory" in stderr
    assert "cmp-debian13-p2-harness" in stderr
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


def test_json_rows_and_scenario_aggregates(outputs: dict[str, Any]) -> None:
    doc = outputs["json"]
    assert doc["columns"] == tool.COLUMNS
    assert len(doc["runs"]) == 6 and doc["runs"][0]["run_id"] == "cmp-yocto-p1"
    assert doc["runs"][0]["mem_load_median_mib"] == 1110.0 and doc["runs"][0]["accepted_in_window"] == 4200
    assert doc["runs"][0]["clock_offset_s"] == 3.5 and doc["runs"][0]["pair"] == 1
    assert doc["runs"][4]["stack_ready_s"] is None and doc["runs"][4]["mem_load_samples"] is None
    assert doc["runs"][5]["clock_offset_s"] is None and doc["runs"][5]["mem_load_samples"] is None
    yocto, debian = doc["scenarios"]["yocto"], doc["scenarios"]["debian13"]
    assert yocto["n_runs"] == 3 and debian["n_runs"] == 3
    assert yocto["metrics"]["mem_rest_median_mib"] == {"median": 430.0, "min": 410.0, "max": 450.0, "n": 3}
    assert yocto["metrics"]["boot_ssh_s"] == {"median": 22.5, "min": 21.0, "max": 23.0, "n": 3}
    # Two values only: the median of what exists is their mean, and n says so.
    assert yocto["metrics"]["stack_ready_s"] == {"median": 386.5, "min": 383.0, "max": 390.0, "n": 2}
    assert yocto["metrics"]["mem_load_median_mib"] == {"median": 1060.0, "min": 1010.0, "max": 1110.0, "n": 2}
    assert yocto["metrics"]["accepted_rate_msg_s"] == {"median": 7.0, "min": 6.0, "max": 7.0, "n": 3}
    assert yocto["metrics"]["accepted_in_window"] == {"median": 4200, "min": 3600, "max": 4200, "n": 3}
    assert debian["metrics"]["accepted_rate_msg_s"] == {"median": 8.0, "min": 8.0, "max": 8.0, "n": 2}
    # Pair 2 has no window (no harness raw directory) and pair 3 no offset: one value only.
    assert debian["metrics"]["mem_load_median_mib"] == {"median": 1210.0, "min": 1210.0, "max": 1210.0, "n": 1}
    assert debian["metrics"]["mem_load_max_mib"] == {"median": 1500.5, "min": 1500.5, "max": 1500.5, "n": 1}
    assert debian["metrics"]["mem_loadfile_max_mib"] == {"median": 2000.0, "min": 2000.0, "max": 2000.0, "n": 3}
    assert debian["metrics"]["clock_offset_s"] == {"median": -0.625, "min": -2.25, "max": 1.0, "n": 2}
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
    assert mem_load == ["1110.0 / 1010.0 / —", "1060.0", "1010.0–1110.0", "1210.0 / — / —", "1210.0", "1210.0–1210.0"]
    loadfile = rows["Whole load-phase sampler file, samples (`mem_loadfile_samples`)"]
    assert loadfile[:3] == ["7 / 7 / —", "7", "7–7"]
    ready = rows["Launch to stack ready (/ready 200), s (`stack_ready_s`)"]
    assert ready[:3] == ["383.0 / 390.0 / —", "386.5", "383.0–390.0"]
    rate = rows["Accepted rate inside the measured window, msg/s (`accepted_rate_msg_s`)"]
    assert rate == ["7.00 / 7.00 / 6.00", "7.00", "6.00–7.00", "8.00 / — / 8.00", "8.00", "8.00–8.00"]
    assert rows["Accepted inside the measured window (counter difference) (`accepted_in_window`)"][:2] == ["4200 / 4200 / 3600", "4200"]
    assert rows["Published rate, msg/s (sent_valid / duration_s) (`published_rate_msg_s`)"][3:] == ["11.20 / — / 11.20", "11.20", "11.20–11.20"]
    assert rows["Clock offset guest − host, s (`clock_offset_s`)"] == ["3.500 / 0.500 / 0.750", "0.750", "0.500–3.500",
                                                                       "-2.250 / 1.000 / —", "-0.625", "-2.250–1.000"]
    assert rows["After the drain: accepted late (`drain_accepted_late`)"] == ["28 / — / —", "28", "28–28", "2 / 28 / 28", "28", "2–28"]
    assert rows["Lost (no confirmation within the deadline) (`lost`)"] == ["20 / 10 / 30", "20", "10–30", "2 / — / 4", "3", "2–4"]
    assert rows["Measured window start, guest clock (`mem_load_window_start_utc`)"] == [
        "2026-10-20T10:02:03.500Z / 2026-10-20T10:02:00.500Z / 2026-10-20T10:02:00.750Z", "—", "—",
        "2026-10-20T10:01:57.750Z / — / —", "—", "—"]
    assert rows["Post-drain event log fetch, as the driver said (`drain_fetch_claim`)"] == [
        "fetched / not-fetched / —", "—", "—", "unstated / fetched / fetched", "—", "—"]
    assert rows["Drain result (`drain_result`)"] == ["quiet / quiet / gave-up", "—", "—", "quiet / quiet / quiet", "—", "—"]
    for phrase in (
        # The earlier notes, all kept.
        "Probe cadences: ssh 2 s, ready 5 s, accept 1 s", "host-monotonic",
        "controller reception → Ditto confirmation", "no confirmation within the harness's deadline",
        "whole gateway guest", "latency_count", "df -P -k", "Median: the middle value of three",
        "An empty cell is an unavailable value, never a zero",
        # The window, the offset and its uncertainty values.
        "bounded to the harness's measured window", "measured_window_utc", "offset_guest_minus_host_s",
        "uncertainty_s seen: 0.040, 0.050, 0.060 s", "window start <= epoch_s <= window end",
        "Warm-up, the confirmation window and the drain are outside it", "transparency only",
        # The counter difference inside the window, and the publications over duration_s.
        "difference of the controller's cumulative `accepted` counter", "`accepted_rate_span_s`",
        "not what arrived after it", "sent_valid / the manifest's duration_s",
        "the simulator's publications during the measured run",
        # The reconciliation, apart from the deadline accounting.
        "reported apart from the deadline accounting", "accepted_no_ack_time", "zero by construction",
        "`drain_fetch_claim`",
    ):
        assert phrase in table, phrase
    assert "delivered_unique / 600" not in table
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
    with (tmp_path / "out4" / "summary.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 6 and all(r["sent_valid"] == "" and r["published_rate_msg_s"] == "" for r in rows)
    assert all(r["boot_ssh_s"] != "" for r in rows)
    assert rows[0]["accepted_rate_msg_s"] == "7.00"  # the window figures do not need the per-run CSV
    proc = run_tool(good, None, tmp_path / "out5")
    assert proc.returncode == 0 and "no --per-run-csv" in proc.stderr
    # A manifest without a usable window: the window-bounded cells stay empty, the rest is written.
    windowless = tmp_path / "windowless"
    build_root(windowless)
    manifest = windowless / "harness" / "raw" / "nominal-yocto-p1" / "manifest.json"
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["measured_window_utc"] = {"start": doc["measured_window_utc"]["start"]}
    write(manifest, json.dumps(doc))
    proc = run_tool(windowless, windowless / "processed" / "per_run.csv", tmp_path / "out6")
    assert proc.returncode == 0 and "measured_window_utc without usable start/end" in proc.stderr
    with (tmp_path / "out6" / "summary.csv").open(encoding="utf-8", newline="") as fh:
        row = {r["run_id"]: r for r in csv.DictReader(fh)}["cmp-yocto-p1"]
    assert row["mem_load_samples"] == "" and row["accepted_rate_msg_s"] == "" and row["mem_load_window_start_utc"] == ""
    assert row["published_rate_msg_s"] == "11.20" and row["mem_loadfile_samples"] == "7" and row["clock_offset_s"] == "3.500"


def test_in_process_entry_point_returns_the_exit_code(tmp_path: Path) -> None:
    per_run = build_root(tmp_path)
    assert tool.main(["--measure-root", str(tmp_path), "--per-run-csv", str(per_run), "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "table.md").is_file()
    assert tool.main(["--measure-root", str(tmp_path / "nowhere"), "--out", str(tmp_path / "o2")]) == 2
