"""Cases for tools/compare/measure_summary.py, the table builder of the comparison
measurement.

A synthetic measurement root is built with six runs (three per scenario, in the
Y-D-D-Y-Y-D pair order) whose timelines, sampler files and df records carry values
chosen so that every derived figure is known in advance: the host-monotonic deltas,
the KiB-to-MiB conversion, the medians and min-max per scenario, the parsing of the two
df mount points, and the join with a per-run CSV written under the harness analyser's
own column list (imported, so that a renamed column breaks these cases rather than the
tool silently). One run lacks its load-phase sampler file and its `ready` instant, and
one has no per-run row: their cells must be empty, never zero, with a WARNING naming
the missing input. The tool runs under this interpreter on any host; nothing here
touches a guest or a real measurement.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from egw_experiments.analyze import PER_RUN_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "tools" / "compare" / "measure_summary.py"


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("measure_summary", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()

MIB_KB = 1024
PROBES = {"ssh": 2, "ready": 5, "accept": 1}


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


def meminfo_text(used_kb: list[int], total_kb: int = 8_012_000) -> str:
    rows = ["ts_utc,epoch_s,mem_total_kb,mem_available_kb,mem_used_kb"]
    for i, used in enumerate(used_kb):
        rows.append(f"2026-10-20T10:00:{i:02d}Z,{1_792_490_400 + i},{total_kb},{total_kb - used},{used}")
    rows.append(f"# end epoch_s={1_792_490_400 + len(used_kb)} samples={len(used_kb)}")
    return "\n".join(rows) + "\n"


# scenario, run_id, pair, order, seed, (ssh_ok, ready, func_twin) relative to launch,
# drain seconds, rest MiB, load MiB (None = file missing), df (root, docker), drain result,
# harness exit, harness run id (None = no per-run row).
RUNS: list[dict[str, Any]] = [
    dict(scenario="yocto", run_id="cmp-yocto-p1", pair=1, order=1, seed=101, launch=10.0,
         ssh=22.5, ready=383.0, func=399.0, drain=60.5, rest=[400, 410, 420], load=[1024, 1126, 1076],
         df=(352256, 2097152), drain_result="quiet", harness_exit=0, harness_id="nominal-yocto-p1"),
    dict(scenario="debian13", run_id="cmp-debian13-p1", pair=1, order=2, seed=101, launch=20.0,
         ssh=46.0, ready=376.0, func=401.1, drain=61.0, rest=[600, 610, 620], load=[1200, 1210, 1220],
         df=(1572864, 2097152), drain_result="quiet", harness_exit=0, harness_id="nominal-debian13-p1"),
    dict(scenario="debian13", run_id="cmp-debian13-p2", pair=2, order=1, seed=102, launch=5.0,
         ssh=47.5, ready=380.0, func=402.0, drain=59.0, rest=[590, 600, 610], load=[1190, 1200, 1210],
         df=(1572900, 2097200), drain_result="quiet", harness_exit=0, harness_id=None),
    dict(scenario="yocto", run_id="cmp-yocto-p2", pair=2, order=2, seed=102, launch=5.0,
         ssh=23.0, ready=390.0, func=405.0, drain=60.0, rest=[420, 430, 440], load=[1026, 1036, 1046],
         df=(352300, 2097300), drain_result="quiet", harness_exit=0, harness_id="nominal-yocto-p2"),
    dict(scenario="yocto", run_id="cmp-yocto-p3", pair=3, order=1, seed=103, launch=7.0,
         ssh=21.0, ready=None, func=None, drain=58.0, rest=[440, 450, 460], load=None,
         df=(352400, 2097400), drain_result="gave-up", harness_exit=1, harness_id="nominal-yocto-p3"),
    dict(scenario="debian13", run_id="cmp-debian13-p3", pair=3, order=2, seed=103, launch=9.0,
         ssh=45.0, ready=378.0, func=399.5, drain=62.0, rest=[610, 620, 630], load=[1210, 1220, 1500.5],
         df=(1573000, None), drain_result="quiet", harness_exit=0, harness_id="nominal-debian13-p3"),
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


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def timeline(run: dict[str, Any]) -> dict[str, Any]:
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
        "harness": {"run_id": run["harness_id"] or run["run_id"] + "-harness", "exit": run["harness_exit"]},
    }


def build_root(root: Path) -> Path:
    """The measurement root with six runs and the per-run CSV; returns the CSV path."""
    for run in RUNS:
        d = root / "runs" / run["run_id"]
        write(d / "timeline.json", json.dumps(timeline(run), indent=1))
        write(d / "meminfo-rest.csv", meminfo_text(mib(run["rest"])))
        if run["load"] is not None:
            write(d / "meminfo-load.csv", meminfo_text(mib(run["load"])))
        write(d / "df-before-load.txt", df_text(*run["df"]))
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


def test_harness_columns_exist_in_the_analyser() -> None:
    assert set(tool.HARNESS_COLUMNS.values()) <= set(PER_RUN_COLUMNS)
    assert tool.HARNESS_COLUMNS["latency_samples"] == "latency_count"


def test_summary_csv_has_one_row_per_run_in_pair_order(outputs: dict[str, Any]) -> None:
    with (outputs["out"] / "summary.csv").open(encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == tool.COLUMNS
    assert [r["run_id"] for r in outputs["rows"]] == [
        "cmp-yocto-p1", "cmp-debian13-p1", "cmp-debian13-p2", "cmp-yocto-p2", "cmp-yocto-p3", "cmp-debian13-p3",
    ]
    assert {r["scenario"] for r in outputs["rows"]} == {"yocto", "debian13"}


def test_deltas_memory_df_and_harness_cells_of_a_complete_run(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p1"]
    assert (row["pair"], row["order_in_pair"], row["seed"]) == ("1", "1", "101")
    assert row["boot_ssh_s"] == "22.5"
    assert row["stack_ready_s"] == "383.0"
    assert row["gateway_functional_s"] == "399.0"
    assert row["drain_s"] == "60.5"
    assert (row["mem_rest_median_mib"], row["mem_rest_max_mib"], row["mem_rest_samples"]) == ("410.0", "420.0", "3")
    assert (row["mem_load_median_mib"], row["mem_load_max_mib"], row["mem_load_samples"]) == ("1076.0", "1126.0", "3")
    assert (row["df_root_used_kib"], row["df_docker_used_kib"]) == ("352256", "2097152")
    assert row["sent_valid"] == "6720" and row["published_rate_msg_s"] == "11.20"
    assert row["delivered_unique"] == "6700" and row["accepted_rate_msg_s"] == "11.17"
    assert row["delivery_rate"] == "0.9970"
    assert (row["lost"], row["late_confirmations"], row["duplicates"], row["double_accepted"]) == ("20", "3", "1", "0")
    assert (row["latency_ms_p50"], row["latency_ms_p95"], row["latency_samples"]) == ("123.4", "456.7", "6700")
    assert (row["drain_result"], row["harness_exit"]) == ("quiet", "0")


def test_fractional_mib_and_df_without_the_docker_line(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-debian13-p3"]
    assert row["mem_load_max_mib"] == "1500.5"
    assert row["mem_load_median_mib"] == "1220.0"
    assert row["df_root_used_kib"] == "1573000"
    assert row["df_docker_used_kib"] == ""
    assert "df-before-load.txt: no line for /var/lib/docker" in outputs["stderr"]


def test_missing_inputs_leave_cells_empty_with_a_warning(outputs: dict[str, Any]) -> None:
    row = outputs["by_id"]["cmp-yocto-p3"]
    assert row["stack_ready_s"] == "" and row["gateway_functional_s"] == ""
    assert row["boot_ssh_s"] == "21.0"
    assert (row["mem_load_median_mib"], row["mem_load_max_mib"], row["mem_load_samples"]) == ("", "", "")
    assert row["mem_rest_median_mib"] == "450.0"
    assert (row["drain_result"], row["harness_exit"]) == ("gave-up", "1")
    assert "WARNING" in outputs["stderr"]
    assert "cmp-yocto-p3" in outputs["stderr"] and "meminfo-load.csv" in outputs["stderr"]
    # No per-run row for this harness id: the harness cells stay empty, nothing is zero.
    row = outputs["by_id"]["cmp-debian13-p2"]
    for column in list(tool.HARNESS_COLUMNS) + ["published_rate_msg_s", "accepted_rate_msg_s"]:
        assert row[column] == "", column
    assert "cmp-debian13-p2-harness" in outputs["stderr"]
    assert "0" not in {row[c] for c in tool.HARNESS_COLUMNS}


def test_json_rows_and_scenario_aggregates(outputs: dict[str, Any]) -> None:
    doc = outputs["json"]
    assert doc["columns"] == tool.COLUMNS
    assert len(doc["runs"]) == 6 and doc["runs"][0]["run_id"] == "cmp-yocto-p1"
    assert doc["runs"][0]["mem_rest_median_mib"] == 410.0 and doc["runs"][0]["pair"] == 1
    assert doc["runs"][4]["stack_ready_s"] is None and doc["runs"][4]["mem_load_samples"] is None
    yocto, debian = doc["scenarios"]["yocto"], doc["scenarios"]["debian13"]
    assert yocto["n_runs"] == 3 and debian["n_runs"] == 3
    assert yocto["metrics"]["mem_rest_median_mib"] == {"median": 430.0, "min": 410.0, "max": 450.0, "n": 3}
    assert yocto["metrics"]["boot_ssh_s"] == {"median": 22.5, "min": 21.0, "max": 23.0, "n": 3}
    # Two values only: the median of what exists is their mean, and n says so.
    assert yocto["metrics"]["stack_ready_s"] == {"median": 386.5, "min": 383.0, "max": 390.0, "n": 2}
    assert yocto["metrics"]["mem_load_median_mib"] == {"median": 1056.0, "min": 1036.0, "max": 1076.0, "n": 2}
    assert debian["metrics"]["mem_load_max_mib"] == {"median": 1220.0, "min": 1210.0, "max": 1500.5, "n": 3}
    assert debian["metrics"]["df_docker_used_kib"] == {"median": 2097176.0, "min": 2097152, "max": 2097200, "n": 2}
    assert debian["metrics"]["lost"] == {"median": 3.0, "min": 2, "max": 4, "n": 2}
    assert yocto["metrics"]["lost"] == {"median": 20, "min": 10, "max": 30, "n": 3}
    assert doc["load_window_s"] == 600
    assert any("latency_count" in note for note in doc["notes"])
    assert doc["warnings"] and all(isinstance(w, str) for w in doc["warnings"])


def test_table_shows_both_scenarios_runs_medians_ranges_and_notes(outputs: dict[str, Any]) -> None:
    table = outputs["table"]
    assert "n=3 per scenario" in table and "one QEMU/TCG profile" in table
    assert "no statistical significance claimed" in table
    assert "Yocto median" in table and "Debian 13 median" in table and "Debian 13 min–max" in table
    rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]]
            for line in table.splitlines() if line.startswith("| ") and "`" in line}
    mem_rest = rows["Guest memory used at rest, median, MiB (`mem_rest_median_mib`)"]
    assert mem_rest == ["410.0 / 430.0 / 450.0", "430.0", "410.0–450.0",
                        "610.0 / 600.0 / 620.0", "610.0", "600.0–620.0"]
    ready = rows["Launch to stack ready (/ready 200), s (`stack_ready_s`)"]
    assert ready[:3] == ["383.0 / 390.0 / —", "386.5", "383.0–390.0"]
    lost = rows["Lost (no confirmation within the deadline) (`lost`)"]
    assert lost == ["20 / 10 / 30", "20", "10–30", "2 / — / 4", "3", "2–4"]
    drain = rows["Drain result (`drain_result`)"]
    assert drain == ["quiet / quiet / gave-up", "—", "—", "quiet / quiet / quiet", "—", "—"]
    for phrase in ("Probe cadences: ssh 2 s, ready 5 s, accept 1 s", "host-monotonic",
                   "controller reception → Ditto confirmation", "no confirmation within the harness's deadline",
                   "whole gateway guest", "latency_count", "sent_valid / 600"):
        assert phrase in table, phrase
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
    assert len(rows) == 6 and all(r["sent_valid"] == "" for r in rows)
    assert all(r["boot_ssh_s"] != "" for r in rows)
    proc = run_tool(good, None, tmp_path / "out5")
    assert proc.returncode == 0 and "no --per-run-csv" in proc.stderr


def test_in_process_entry_point_returns_the_exit_code(tmp_path: Path) -> None:
    per_run = build_root(tmp_path)
    assert tool.main(["--measure-root", str(tmp_path), "--per-run-csv", str(per_run), "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "table.md").is_file()
    assert tool.main(["--measure-root", str(tmp_path / "nowhere"), "--out", str(tmp_path / "o2")]) == 2
