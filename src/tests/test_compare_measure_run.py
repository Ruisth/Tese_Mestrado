"""tools/compare/measure_run.sh and measure_series.sh: the guards that keep a measured execution from
starting on the wrong footing. On the bench of test_compare_env.py (stub host); nothing here runs a
harness, a tunnel or a guest beyond the stub QEMU - the sequence itself is exercised on the real host.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
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
from test_compare_meminfo_sampler import busybox_dir  # noqa: E402,F401  (the image's busybox, when available)

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
    # Answers every `-c` probe (imports; the seed derivation prints a number).
    py.write_text("#!/bin/sh\n[ \"$1\" = -c ] && { echo 1234; exit 0; }\nexit 1\n", encoding="utf-8")
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


# --- the batch after the first measured execution: permissions, fetches, drain environment, seal ------------

DRAIN_HOOK = COMPARE_DIR / "drain_hook.sh"
FETCH_PROBE = """#!/bin/bash
. "$1/lib.sh"; scenario_load yocto; shift
"$@"
"""


def _fetch(bench: Bench, fn: str, remote: Path, local: Path, **env: str):
    probe = bench.bin / "fetch_probe.sh"
    probe.write_text(FETCH_PROBE, encoding="utf-8")
    return bench.run_script(probe, str(COMPARE_DIR), fn, str(remote), str(local), EGW_STUB_SSH_EXEC="1", **env)


def test_guest_fetch_live_verifies_the_prefix_of_a_growing_file(bench, tmp_path) -> None:
    remote = tmp_path / "events.jsonl"
    remote.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    local = tmp_path / "copy.jsonl"
    result = _fetch(bench, "guest_fetch_live", remote, local, EGW_STUB_SCP_GROW_SRC="1")
    assert result.returncode == 0, _report(result)
    assert local.read_text(encoding="utf-8") == '{"a": 1}\n{"a": 2}\n'
    assert "prefix verified" in result.stdout and f"held {len(remote.read_bytes())} bytes" in result.stdout


def test_guest_fetch_live_fails_on_an_empty_copy_and_on_a_failed_read(bench, tmp_path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_bytes(b"")
    result = _fetch(bench, "guest_fetch_live", empty, tmp_path / "copy1")
    assert result.returncode == 1 and "is empty (0 bytes)" in result.stdout, _report(result)
    remote = tmp_path / "events.jsonl"
    remote.write_text("line\n", encoding="utf-8")
    result = _fetch(bench, "guest_fetch_live", remote, tmp_path / "copy2", EGW_STUB_SSH_RC="1")
    assert result.returncode == 1 and "could not read the first 5 bytes" in result.stdout, _report(result)


def test_guest_fetch_file_fails_when_the_copy_differs(bench, tmp_path) -> None:
    remote = tmp_path / "meminfo.csv"
    remote.write_text("ts,a\n1,2\n", encoding="utf-8")
    ok = _fetch(bench, "guest_fetch_file", remote, tmp_path / "ok.csv")
    assert ok.returncode == 0 and "copied and verified" in ok.stdout, _report(ok)
    bad = _fetch(bench, "guest_fetch_file", remote, tmp_path / "bad.csv", EGW_STUB_SCP_CORRUPT="1")
    assert bad.returncode == 1 and "sha256 differs" in bad.stdout, _report(bad)


def test_drain_hook_runs_with_the_environment_file_exported(bench, tmp_path) -> None:
    secrets = tmp_path / "egw.env"
    secrets.write_text("MOSQUITTO_SIMULATOR_PASSWORD=stub-secret-value\nOTHER=1\n", encoding="utf-8")
    hook = tmp_path / "hook.sh"
    hook.write_text('#!/bin/sh\n[ -n "${MOSQUITTO_SIMULATOR_PASSWORD:-}" ] && echo "has_env=yes rid=$1" || echo has_env=no\n'
                    'echo "quiet=${DRAIN_QUIET_S:-unset}"\nexit 3\n', encoding="utf-8")
    result = bench.run_script(DRAIN_HOOK, str(secrets), str(hook), "cmp-p1-yocto", DRAIN_QUIET_S="130")
    assert result.returncode == 3, _report(result)
    assert "has_env=yes rid=cmp-p1-yocto" in result.stdout and "quiet=130" in result.stdout
    assert "stub-secret-value" not in result.stdout + result.stderr
    missing = bench.run_script(DRAIN_HOOK, str(tmp_path / "absent.env"), str(hook), "cmp-p1-yocto")
    assert missing.returncode == 97 and "not readable" in missing.stderr


def _measured_base_readonly(bench: Bench) -> Path:
    base = _measured_base(bench)
    for name in ("root.qcow2", "data.img"):
        (base / name).chmod(0o444)
    return base


def test_restore_gives_writable_work_copies_and_the_record_is_sealed_after_the_log(bench, tmp_path) -> None:
    """The integrated offline path: prerequisites pass, the disks are restored from a read-only base (new
    destination and a stale existing one), the apply fails on this bench (no Terraform), the guest is closed,
    the record is written and sealed AFTER the log is finished, and the seal verifies."""
    plan = _plan(tmp_path / "plan.json")
    base = _measured_base_readonly(bench)
    bench.ok("prepare", "yocto")
    root_disk = bench.disks / "egw-gateway-image-qemuarm64.rootfs.qcow2"
    root_disk.write_bytes(b"stale overlay\n")          # an existing destination, writable
    (bench.disks / "data.img").unlink()                 # and a destination that does not exist
    result = bench.run_script(MEASURE_RUN, "yocto", "cmp-p1-yocto", str(plan), **_host_files(bench))
    assert result.returncode in (1, 5), _report(result)
    for name, disk in (("root.qcow2", root_disk), ("data.img", bench.disks / "data.img")):
        assert disk.read_bytes() == (base / name).read_bytes(), name
        assert disk.stat().st_mode & 0o200, f"{name} must be writable for QEMU"
        assert not (base / name).stat().st_mode & 0o222, f"the base {name} stays read-only"
    run = bench.root / "measure" / "runs" / "cmp-p1-yocto"
    steps = (run / "steps.tsv").read_text(encoding="utf-8")
    assert "\trestore-disks\t0\t" in steps and "\ttf-apply\t0\t" not in steps
    timeline = json.loads((run / "timeline.json").read_text(encoding="utf-8"))
    assert timeline["instrumentation_failed"] == 1 and timeline["uptime_s"]["launch"] is None
    assert timeline["functional"]["seed"] == 1234 and timeline["stop_exit"] == 2
    log = (run / "measure.log").read_text(encoding="utf-8")
    assert "MEASURE yocto cmp-p1-yocto: result=apply-failed" in log, "the last lines reach the log before the seal"
    seal = subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=run, capture_output=True, text=True)
    assert seal.returncode == 0, seal.stdout + seal.stderr
    assert "measure.log" in (run / "SHA256SUMS").read_text(encoding="utf-8")
    assert len(bench.qemu_starts()) == 0


def test_guest_fetch_live_under_the_image_busybox(bench, tmp_path, busybox_dir) -> None:
    """The remote side of the live fetch runs on the guest's own shell and tools: under the gateway image's
    busybox (head has no -c there, the reason the first series stopped), dd reads the prefix and the copy
    verifies; the stub ssh runs the remote command with the busybox sh and applets first on PATH."""
    directory, reason = busybox_dir
    if directory is None:
        pytest.skip(reason)
    remote = tmp_path / "events.jsonl"
    remote.write_text('{"a": 1}\n' * 300, encoding="utf-8")
    local = tmp_path / "copy.jsonl"
    path = f"{directory}{os.pathsep}{bench.bin}{os.pathsep}{os.environ['PATH']}"
    result = _fetch(bench, "guest_fetch_live", remote, local, EGW_STUB_SCP_GROW_SRC="1", PATH=path)
    assert result.returncode == 0, _report(result)
    assert local.read_bytes() == b'{"a": 1}\n' * 300 and "prefix verified" in result.stdout
    probe = subprocess.run(["sh", "-c", "head -c 1 /dev/null"], env={**os.environ, "PATH": path}, capture_output=True, text=True)
    assert probe.returncode != 0, "this busybox is expected to lack head -c (otherwise the case proves less)"


def test_series_runs_every_planned_entry_even_when_the_driver_reads_stdin(bench, tmp_path) -> None:
    """The second series ended after its second execution: the driver inherited the loop's stdin and a
    tool inside it swallowed the remaining entries. The loop now feeds the driver /dev/null; a stub driver
    that drains its stdin must still be called once per planned entry, in order."""
    plan = {
        "plan_version": "1.0",
        "runs": [{"run_id": r, "condition_id": "nominal", "seed": 1, "status": s, "duration_s": 600, "warmup_s": 120,
                  "rate_msg_s": 11.2} for r, s in (("a", "completed"), ("b", "planned"), ("c", "planned"), ("d", "planned"))],
        "comparison": {"runs": {r: {"scenario": "yocto", "pair": 1, "order_in_pair": 1} for r in "abcd"}},
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    stub = bench.bin / "measure_run_stub.sh"
    stub.write_text("#!/bin/sh\ncat > /dev/null\necho \"stub run $2\" >> \"$EGW_STUB_CALLS\"\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    result = bench.run_script(MEASURE_SERIES, str(path), EGW_COMPARE_MEASURE_RUN=str(stub))
    calls = [line for line in bench.calls.read_text(encoding="utf-8").splitlines() if line.startswith("stub run")]
    assert calls == ["stub run b", "stub run c", "stub run d"], (calls, _report(result))
    assert "status 'completed', skipped" in result.stdout
