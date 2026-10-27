"""Cases for qemu_procs (tools/session/guest_common.sh): how the session drivers
tell a running QEMU from a shell that merely mentions it.

Real, harmless Linux processes stand in for the guest: a 'sleep' reached
through a symbolic link named qemu-system-aarch64 (an executable of that
name, with the 19-character name Linux cuts to 15 in the process name), a
shell whose command line holds the string, and nothing at all. The two
obvious tests are shown wrong on the same processes: 'pgrep -f' takes the
shell for a guest, 'pgrep -x' cannot see the guest.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

if sys.platform == "win32" or shutil.which("pgrep") is None or shutil.which("bash") is None:
    pytest.skip("pgrep, bash and Linux process names are needed", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
GUEST_COMMON = REPO_ROOT / "tools" / "session" / "guest_common.sh"


def _qemu_procs(env: dict | None = None) -> subprocess.CompletedProcess:
    script = f'EXEC="{os.environ.get("TMPDIR", "/tmp")}/egw-guard-test"; . "{GUEST_COMMON}"; qemu_procs; echo "rc=$?"'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30, env=env)


def _rc(result: subprocess.CompletedProcess) -> int:
    return int(result.stdout.strip().rsplit("rc=", 1)[1])


@pytest.fixture
def fake_qemu(tmp_path: Path):
    """A process whose executable is named qemu-system-aarch64: 'sleep' through a symlink."""
    link = tmp_path / "bin" / "qemu-system-aarch64"
    link.parent.mkdir()
    link.symlink_to(shutil.which("sleep"))
    proc = subprocess.Popen([str(link), "60"])
    time.sleep(0.3)
    try:
        yield proc
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)


@pytest.fixture
def mentioning_shell():
    """A shell whose command line holds the string and is not QEMU.

    The 'sleep' is not the last command: bash replaces itself with the last
    simple command of a '-c' string, and the shell would then be gone with
    its command line. This shell stays, waiting, as the one that invoked the
    close driver on 2026-09-23 did.
    """
    proc = subprocess.Popen(["bash", "-c", "echo qemu-system-aarch64 -machine virt; sleep 60; echo done"],
                            stdout=subprocess.DEVNULL)
    time.sleep(0.3)
    try:
        yield proc
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)


def test_a_running_qemu_executable_is_present(fake_qemu):
    result = _qemu_procs()
    assert _rc(result) == 0, result.stdout
    assert str(fake_qemu.pid) in result.stdout.split()[0], result.stdout
    # the process name Linux keeps is cut at 15 characters: an exact-name
    # match never sees this process, which is what commit 86fc50d had relied on
    name = Path(f"/proc/{fake_qemu.pid}/comm").read_text().strip()
    assert name == "qemu-system-aar"
    assert subprocess.run(["pgrep", "-x", "qemu-system-aarch64"], capture_output=True).returncode == 1


def test_a_shell_that_merely_mentions_qemu_is_absent(mentioning_shell):
    result = _qemu_procs()
    assert _rc(result) == 1, result.stdout
    assert str(mentioning_shell.pid) not in result.stdout
    # the whole-command-line match, which the drivers used before, takes it for a guest
    assert subprocess.run(["pgrep", "-f", "qemu-system-aarch64"], capture_output=True).returncode == 0


def test_a_qemu_beside_a_mentioning_shell_lists_only_the_qemu(fake_qemu, mentioning_shell):
    result = _qemu_procs()
    assert _rc(result) == 0
    pids = [ln.split()[0] for ln in result.stdout.splitlines() if ln and not ln.startswith("rc=")]
    assert str(fake_qemu.pid) in pids and str(mentioning_shell.pid) not in pids, result.stdout


def test_nothing_running_is_absent():
    result = _qemu_procs()
    assert _rc(result) == 1, result.stdout


def test_a_pgrep_that_cannot_answer_is_indeterminate(tmp_path):
    # no pgrep on PATH at all: the answer is neither present nor absent
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("bash", "cat", "cut", "head"):
        real = shutil.which(tool)
        if real:
            (bin_dir / tool).symlink_to(real)
    env = dict(os.environ)
    env["PATH"] = str(bin_dir)
    result = _qemu_procs(env)
    assert _rc(result) >= 2, result.stdout + result.stderr
