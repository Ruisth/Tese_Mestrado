"""tools/compare/up.sh: the start-wait-provision sequence behind `tf.sh <scenario> apply`.

Runs on the bench of test_compare_env.py (stub QEMU, ssh, pgrep, ss, qemu-img ...); the provisioning
script is replaced by a stub named in EGW_COMPARE_PROVISION_SCRIPT, so this file tests the sequence
and its exit codes, not the stack.
"""
from __future__ import annotations

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

from test_compare_env import REPO_ROOT, Bench, _report, bench  # noqa: E402,F401

UP = REPO_ROOT / "tools" / "compare" / "up.sh"

PROVISION_STUB = """#!/bin/sh
# Stub provisioning: records the call, answers EGW_STUB_PROVISION_RC (default 0).
echo "provision $*" >> "$EGW_STUB_CALLS"
exit "${EGW_STUB_PROVISION_RC:-0}"
"""


def _up(bench: Bench, **env: str):
    stub = bench.bin / "provision_stub.sh"
    stub.write_text(PROVISION_STUB, encoding="utf-8")
    stub.chmod(0o755)
    base = {"EGW_COMPARE_PROVISION_SCRIPT": str(stub), "EGW_COMPARE_SSH_LIMIT_S": "3"}
    base.update(env)
    return bench.run_script(UP, "yocto", **base)


def test_up_starts_waits_for_ssh_provisions_and_leaves_the_guest_running(bench) -> None:
    bench.ok("prepare", "yocto")
    result = _up(bench)
    assert result.returncode == 0, _report(result)
    assert "ENVIRONMENT READY: yocto" in result.stdout
    calls = bench.calls.read_text(encoding="utf-8")
    assert calls.count("provision yocto") == 1
    status = bench.status()
    assert status["running"] == "true" and status["pid"], status
    assert list((bench.s_dir / "logs").glob("up-*.log")), "the up transcript is kept"


def test_up_on_a_running_guest_starts_nothing_twice(bench) -> None:
    bench.ok("prepare", "yocto")
    first = _up(bench)
    assert first.returncode == 0, _report(first)
    pid = bench.status()["pid"]
    second = _up(bench)
    assert second.returncode == 0, _report(second)
    assert bench.status()["pid"] == pid, "a second up must not start another QEMU"
    assert len(bench.qemu_starts()) == 1


def test_up_reports_exit_1_and_keeps_the_guest_when_ssh_never_answers(bench) -> None:
    bench.ok("prepare", "yocto")
    result = _up(bench, EGW_STUB_SSH_RC="255")
    assert result.returncode == 1, _report(result)
    assert "no ssh answer" in result.stdout and "left running" in result.stdout
    assert "provision yocto" not in bench.calls.read_text(encoding="utf-8")
    assert bench.status()["running"] == "true"


def test_up_passes_the_provisioning_exit_code_through(bench) -> None:
    bench.ok("prepare", "yocto")
    result = _up(bench, EGW_STUB_PROVISION_RC="3")
    assert result.returncode == 3, _report(result)
    assert "provisioning failed" in result.stdout
    assert bench.status()["running"] == "true", "the guest is left for inspection"


def test_up_refuses_when_start_is_refused(bench) -> None:
    bench.ok("prepare", "yocto")
    result = _up(bench, EGW_STUB_OTHER_QEMU="4242 /usr/bin/qemu-system-aarch64 -machine virt")
    assert result.returncode == 2, _report(result)
    assert "nothing more is done" in result.stdout
    assert "provision yocto" not in bench.calls.read_text(encoding="utf-8")
