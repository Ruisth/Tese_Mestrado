"""Cases for tools/probe/guest/probe_recorder.sh, the guest-side 1 s recorder.

They run the script under the host's POSIX shell (and under the image's own
busybox when EGW_TEST_BUSYBOX_DIR points at the wrappers of
tools/test/make-busybox-wrappers.sh) against a synthetic cgroup tree and a
fake docker on PATH. Nothing here touches a real container or the guest.
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

if sys.platform == "win32":
    pytest.skip("the recorder is a POSIX shell script for the guest", allow_module_level=True)
if shutil.which("sh") is None:
    pytest.skip("sh is not installed", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORDER = REPO_ROOT / "tools" / "probe" / "guest" / "probe_recorder.sh"

FAKE_DOCKER = """#!/bin/sh
# stub docker: the probe container's id and state; an inspect can be slow
case "$*" in
    *"{{.Id}}"*) echo abc123 ;;
    *"{{.State.Status}} {{.RestartCount}}"*)
        [ -z "${FAKE_INSPECT_DELAY_S:-}" ] || sleep "$FAKE_INSPECT_DELAY_S"
        echo "running 0" ;;
    *) exit 1 ;;
esac
"""


def _tree(tmp_path: Path) -> dict:
    cg = tmp_path / "cg" / "docker" / "abc123"
    cg.mkdir(parents=True)
    (cg / "memory.current").write_text("20000000\n")
    (cg / "memory.max").write_text("134217728\n")
    (cg / "memory.peak").write_text("21000000\n")
    (cg / "memory.stat").write_text("anon 10000000\nfile 5000000\nactive_file 1\ninactive_file 2\n")
    (cg / "memory.events").write_text("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n")
    vol = tmp_path / "dk" / "volumes" / "v1" / "_data"
    vol.mkdir(parents=True)
    (vol / "mosquitto.db").write_text("x" * 123)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
    return {"cg": tmp_path / "cg", "dk": tmp_path / "dk", "bin": bin_dir}


def _shell() -> list[str]:
    busybox = os.environ.get("EGW_TEST_BUSYBOX_DIR")
    if busybox:
        return [str(Path(busybox) / "sh")]
    return ["sh"]


def _env(tree: dict) -> dict:
    env = dict(os.environ)
    busybox = os.environ.get("EGW_TEST_BUSYBOX_DIR")
    env["PATH"] = f"{tree['bin']}{os.pathsep}{busybox}" if busybox else f"{tree['bin']}{os.pathsep}{env['PATH']}"
    env["PROBE_CGROUP_ROOT"] = str(tree["cg"])
    env["PROBE_DOCKER_ROOT"] = str(tree["dk"])
    return env


def _rows(out: Path) -> list[list[str]]:
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return [ln.split(",") for ln in lines[1:]]


def test_the_recorder_writes_one_row_per_interval_and_a_closing_line(tmp_path):
    tree = _tree(tmp_path)
    out = tmp_path / "out.csv"
    proc = subprocess.Popen([*_shell(), str(RECORDER), "probe", str(out), "v1", "1", "2"], env=_env(tree))
    time.sleep(3.2)
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=15) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# probe_recorder container=probe id=abc123")
    assert "# stop samples=" in text
    rows = _rows(out)
    assert 2 <= len(rows) <= 5, rows
    for row in rows:
        assert len(row) == 15, row
        assert row[2] == "20000000" and row[3] == "134217728" and row[4] == "21000000"
        assert row[5] == "10000000" and row[12] == "123" and row[13] == "running" and row[14] == "0"
        assert "?" not in row


def test_a_stop_that_interrupts_a_sample_leaves_no_partial_row(tmp_path):
    # the C3 attempt of 2026-09-23: the stop arrived during the 'docker inspect'
    # of a sample, the interrupted read gave '?' and a row of '?' was written
    tree = _tree(tmp_path)
    out = tmp_path / "out.csv"
    env = _env(tree)
    env["FAKE_INSPECT_DELAY_S"] = "3"      # every inspect sample is slow
    proc = subprocess.Popen([*_shell(), str(RECORDER), "probe", str(out), "v1", "1", "1"], env=env)
    time.sleep(1.5)                        # inside the first (slow) inspect
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=20) == 0
    text = out.read_text(encoding="utf-8")
    assert "# stop samples=" in text
    for row in _rows(out):
        assert "?" not in row, row
        assert row[13] == "running" and row[14] == "0", row


def test_the_recorder_refuses_a_container_it_cannot_find(tmp_path):
    tree = _tree(tmp_path)
    (tree["bin"] / "docker").write_text("#!/bin/sh\nexit 1\n")
    result = subprocess.run([*_shell(), str(RECORDER), "probe", str(tmp_path / "out.csv"), "v1"], env=_env(tree),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 2 and "not found" in result.stderr
    assert not (tmp_path / "out.csv").exists()
