"""tools/compare/measure_run.sh and measure_series.sh: the guards that keep a measured execution from
starting on the wrong footing. On the bench of test_compare_env.py (stub host); nothing here runs a
harness, a tunnel or a guest beyond the stub QEMU - the sequence itself is exercised on the real host.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the comparison scripts are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)
if not Path("/proc/uptime").exists():
    pytest.skip("needs a Linux /proc", allow_module_level=True)

from test_compare_env import COMPARE_DIR, Bench, _report, bench  # noqa: E402,F401

MEASURE_RUN = COMPARE_DIR / "measure_run.sh"
MEASURE_SERIES = COMPARE_DIR / "measure_series.sh"


def _plan(path: Path, status: str = "planned", scenario: str = "yocto") -> Path:
    plan = {
        "plan_version": "1.0",
        "runs": [{"run_id": "cmp-p1-yocto", "condition_id": "nominal", "seed": 4242, "status": status,
                  "duration_s": 600, "warmup_s": 120, "rate_msg_s": 11.2}],
        "comparison": {"runs": {"cmp-p1-yocto": {"scenario": scenario, "pair": 1, "order_in_pair": 1}}},
    }
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _host_files(bench: Bench) -> dict[str, str]:
    """A venv python that answers the import probes, a secrets file and a helper file: the host side."""
    venv = bench.exec_dir / "venv" / "bin"
    venv.mkdir(parents=True)
    py = venv / "python"
    py.write_text("#!/bin/sh\n[ \"$1\" = -c ] && exit 0\nexit 1\n", encoding="utf-8")
    py.chmod(0o755)
    secrets = bench.home / "egw.env"
    secrets.write_text("MOSQUITTO_SIMULATOR_PASSWORD=stub-secret-value\n", encoding="utf-8")
    helpers = bench.home / "itest-helpers.sh"
    helpers.write_text("drained() { echo 'drained: queue_depth 0 stub'; }\n", encoding="utf-8")
    return {"EGW_COMPARE_SECRETS_ENV": str(secrets), "EGW_COMPARE_RUNBOOK_HELPERS": str(helpers)}


def _measured_base(bench: Bench) -> Path:
    base = bench.root / "measure" / "base" / "yocto"
    base.mkdir(parents=True)
    (base / "root.qcow2").write_bytes(b"QFI stub base\n")
    (base / "data.img").write_bytes(b"data stub base\n")
    import hashlib
    lines = []
    for name in ("root.qcow2", "data.img"):
        lines.append(f"{hashlib.sha256((base / name).read_bytes()).hexdigest()}  {name}")
    (base / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (base / "base.json").write_text("{}", encoding="utf-8")
    return base


def test_refuses_an_entry_that_is_not_planned(bench, tmp_path) -> None:
    plan = _plan(tmp_path / "plan.json", status="completed")
    result = bench.run_script(MEASURE_RUN, "yocto", "cmp-p1-yocto", str(plan), **_host_files(bench))
    assert result.returncode == 2, _report(result)
    assert "not planned" in result.stderr and "never a repetition" in result.stderr
    assert not (bench.root / "measure" / "runs").exists()


def test_refuses_an_entry_of_the_other_scenario(bench, tmp_path) -> None:
    plan = _plan(tmp_path / "plan.json", scenario="debian13")
    result = bench.run_script(MEASURE_RUN, "yocto", "cmp-p1-yocto", str(plan), **_host_files(bench))
    assert result.returncode == 2, _report(result)
    assert "belongs to scenario 'debian13'" in result.stderr


def test_refuses_without_a_measured_base(bench, tmp_path) -> None:
    plan = _plan(tmp_path / "plan.json")
    result = bench.run_script(MEASURE_RUN, "yocto", "cmp-p1-yocto", str(plan), **_host_files(bench))
    assert result.returncode == 2, _report(result)
    assert "no measured base" in result.stderr
    assert not (bench.root / "measure" / "runs").exists()


def test_refuses_while_the_guest_runs_and_starts_nothing(bench, tmp_path) -> None:
    plan = _plan(tmp_path / "plan.json")
    _measured_base(bench)
    bench.ok("prepare", "yocto")
    bench.ok("start", "yocto")
    pid = bench.pid()
    result = bench.run_script(MEASURE_RUN, "yocto", "cmp-p1-yocto", str(plan), **_host_files(bench))
    assert result.returncode == 2, _report(result)
    assert "running already" in result.stderr
    assert bench.pid() == pid and len(bench.qemu_starts()) == 1
    assert not (bench.root / "measure" / "runs").exists()


def test_series_skips_entries_already_run_and_refuses_an_unreadable_plan(bench, tmp_path) -> None:
    result = bench.run_script(MEASURE_SERIES, str(tmp_path / "absent.json"))
    assert result.returncode == 2, _report(result)
    # A working plan whose only entry is completed: nothing runs, the analysis step is reached and fails
    # harmlessly on the stub host (no venv), the summary is attempted; the entry is reported as skipped.
    plan = _plan(tmp_path / "plan.json", status="completed")
    result = bench.run_script(MEASURE_SERIES, str(plan))
    assert "status 'completed', skipped" in result.stdout, _report(result)
    assert len(bench.qemu_starts()) == 0
