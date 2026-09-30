"""tools/session/fetch_started_at.sh: the StartedAt read of decision 1a (adopted 2026-09-30).

The harness's --fetch-started-at-cmd hook, run as the harness runs it (one argv, no shell, stdin from the null
device), against a stub ssh that runs the guest command on this machine - under the gateway image's busybox when
EGW_TEST_BUSYBOX_DIR names the wrappers of tools/test/make-busybox-wrappers.sh (PATH then holds nothing else but the
guest stubs), under sh otherwise - with a stub docker (inspect only, answering from the environment) and a stub date.
Every stub call is logged in order, so the cases see one ssh session, both inspect reads and the guest clock after
them. What these cases show is the script's own behaviour: the four lines written once, and no file, a non-zero exit
and a reason on stderr whenever a value is missing or malformed. They say nothing about a real guest or engine.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the session scripts are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "session" / "fetch_started_at.sh"
CID = "9c" * 32
STARTED = "2026-09-30T10:05:01.123456789Z"
EPOCH = "1790763999"

SSH_STUB = """#!/usr/bin/env python3
# Stub ssh: 'ssh HOST COMMAND...' runs COMMAND on this machine under the guest's shell, the guest stubs first on
# PATH; EGW_STUB_SSH_RC answers that status without running anything (a session that could not be opened).
import os
import subprocess
import sys

args = [a for a in sys.argv[1:] if not a.startswith("-")]
with open(os.environ["EGW_STUB_CALLS"], "a", encoding="utf-8") as log:
    log.write("ssh " + args[0] + "\\n")
if os.environ.get("EGW_STUB_SSH_RC"):
    print("ssh: connect to host 127.0.0.1 port 2222: Connection refused", file=sys.stderr)
    sys.exit(int(os.environ["EGW_STUB_SSH_RC"]))
env = dict(os.environ)
busybox = os.environ.get("EGW_TEST_BUSYBOX_DIR")
env["PATH"] = os.environ["EGW_STUB_GUEST_BIN"] + os.pathsep + (busybox or os.environ["PATH"])
shell = os.path.join(busybox, "sh") if busybox else "sh"
sys.exit(subprocess.run([shell, "-c", " ".join(args[1:])], env=env).returncode)
"""

DOCKER_STUB = """#!/bin/sh
# Stub docker of the guest: 'docker inspect -f TEMPLATE NAME' answers the id or StartedAt from the environment.
echo "docker $*" >> "$EGW_STUB_CALLS"
[ "$1" = inspect ] || { echo "stub docker: nothing to do for $1" >&2; exit 1; }
[ "$4" = "$EGW_STUB_CONTAINER" ] || { echo "Error: No such object: $4" >&2; exit 1; }
case $3 in
    '{{.Id}}') [ "${EGW_STUB_FAIL:-}" != id ] || { echo "Error response from daemon: stub" >&2; exit 1; }
               printf '%s\\n' "$EGW_STUB_CID" ;;
    '{{.State.StartedAt}}') [ "${EGW_STUB_FAIL:-}" != started ] || { echo "Error response from daemon: stub" >&2; exit 1; }
               printf '%s\\n' "$EGW_STUB_STARTED" ;;
    *) echo "stub docker: template $3" >&2; exit 1 ;;
esac
"""

DATE_STUB = """#!/bin/sh
# Stub date of the guest: 'date +%s' answers EGW_STUB_EPOCH.
echo "date $*" >> "$EGW_STUB_CALLS"
[ "${EGW_STUB_FAIL:-}" != date ] || { echo "date: stub failure" >&2; exit 1; }
[ "$1" = +%s ] || { echo "stub date: unsupported $*" >&2; exit 1; }
printf '%s\\n' "$EGW_STUB_EPOCH"
"""


class Bench:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"
        self.guest_bin = tmp_path / "gbin"
        for directory in (self.bin, self.guest_bin):
            directory.mkdir()
        for path, text in ((self.bin / "ssh", SSH_STUB), (self.guest_bin / "docker", DOCKER_STUB),
                           (self.guest_bin / "date", DATE_STUB)):
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)
        self.calls = tmp_path / "calls.log"
        self.sut = tmp_path / "run" / "logs" / "sut"
        self.sut.mkdir(parents=True)
        self.dest = self.sut / "controller-started-at.txt"

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        environment = dict(os.environ)
        environment.update({
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "EGW_STUB_CALLS": str(self.calls),
            "EGW_STUB_GUEST_BIN": str(self.guest_bin),
            "EGW_STUB_CONTAINER": "egw-controller-1",
            "EGW_STUB_CID": CID,
            "EGW_STUB_STARTED": STARTED,
            "EGW_STUB_EPOCH": EPOCH,
        })
        environment.update(env)
        argv = ["bash", str(SCRIPT), *(args if args else (str(self.dest),))]
        return subprocess.run(argv, env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=60)

    def log(self) -> list[str]:
        return self.calls.read_text(encoding="utf-8").splitlines() if self.calls.exists() else []

    def leftovers(self) -> list[str]:
        return sorted(p.name for p in self.sut.iterdir() if p.name != self.dest.name)


@pytest.fixture
def bench(tmp_path) -> Bench:
    return Bench(tmp_path)


def _report(result: subprocess.CompletedProcess) -> str:
    return f"exit {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_one_session_reads_the_id_and_started_at_then_the_guest_clock_and_writes_the_record_once(bench) -> None:
    result = bench.run()
    assert result.returncode == 0, _report(result)
    assert bench.dest.read_text(encoding="utf-8") == (
        f"container=egw-controller-1\ncontainer_id={CID}\nstarted_at={STARTED}\nguest_epoch={EPOCH}\n"
    )
    assert bench.log() == [
        "ssh egw-tcg",
        "docker inspect -f {{.Id}} egw-controller-1",
        "docker inspect -f {{.State.StartedAt}} egw-controller-1",
        "date +%s",
    ]
    assert bench.leftovers() == [], "a temporary file was left beside the record"
    assert "STOP" not in result.stderr, _report(result)


def test_the_container_argument_is_the_one_read_and_named(bench) -> None:
    result = bench.run(str(bench.dest), "egw-mongodb-1", EGW_STUB_CONTAINER="egw-mongodb-1")
    assert result.returncode == 0, _report(result)
    assert bench.dest.read_text(encoding="utf-8").splitlines()[0] == "container=egw-mongodb-1"
    assert "docker inspect -f {{.Id}} egw-mongodb-1" in bench.log()


def test_an_existing_record_is_refused_and_nothing_is_read(bench) -> None:
    bench.dest.write_text("earlier\n", encoding="utf-8")
    result = bench.run()
    assert result.returncode != 0
    assert bench.dest.read_text(encoding="utf-8") == "earlier\n"
    assert bench.log() == [], "the guest was reached although the record exists"
    assert "STOP: fetch_started_at: " in result.stderr and "write-once" in result.stderr, _report(result)


@pytest.mark.parametrize("env, says", [
    ({"EGW_STUB_SSH_RC": "255"}, "ssh egw-tcg exit 255"),
    ({"EGW_STUB_FAIL": "id"}, ".Id"),
    ({"EGW_STUB_FAIL": "started"}, ".State.StartedAt"),
    ({"EGW_STUB_FAIL": "date"}, "guest clock"),
    ({"EGW_STUB_STARTED": ""}, "started_at"),
    ({"EGW_STUB_STARTED": "2026-09-30T10:05:01.123456789+00:00"}, "started_at"),
    ({"EGW_STUB_STARTED": "2026-09-30T10:05:01.1234567891Z"}, "started_at"),
    ({"EGW_STUB_CID": "9c" * 31}, "container_id"),
    ({"EGW_STUB_CID": "9C" * 32}, "container_id"),
    ({"EGW_STUB_EPOCH": "1790763999.5"}, "guest_epoch"),
    ({"EGW_STUB_EPOCH": ""}, "guest_epoch"),
])
def test_anything_missing_or_malformed_leaves_no_file_a_non_zero_exit_and_a_reason(bench, env, says) -> None:
    result = bench.run(**env)
    assert result.returncode != 0, _report(result)
    assert not bench.dest.exists()
    assert bench.leftovers() == [], "a temporary file was left behind"
    assert "STOP: fetch_started_at: " in result.stderr and says in result.stderr, _report(result)


@pytest.mark.parametrize("args", [(), ("a", "b", "c")])
def test_a_usage_error_reads_nothing(bench, args) -> None:
    argv = ["bash", str(SCRIPT), *args]
    result = subprocess.run(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                            env={**os.environ, "PATH": f"{bench.bin}{os.pathsep}{os.environ['PATH']}",
                                 "EGW_STUB_CALLS": str(bench.calls)})
    assert result.returncode == 2, _report(result)
    assert "usage: fetch_started_at.sh DEST [CONTAINER]" in result.stderr
    assert bench.log() == []


def test_a_container_name_that_is_not_plain_is_refused_before_the_guest(bench) -> None:
    result = bench.run(str(bench.dest), "egw;reboot")
    assert result.returncode == 2, _report(result)
    assert bench.log() == [] and not bench.dest.exists()


def test_the_script_is_shellcheck_clean_at_error_severity() -> None:
    shellcheck = shutil.which("shellcheck") or str(Path(sys.executable).parent / "shellcheck")
    if not Path(shellcheck).is_file():
        pytest.skip("shellcheck is not installed")
    result = subprocess.run([shellcheck, "-S", "error", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, _report(result)


def test_the_guest_reads_are_the_ones_proof_restart_controller_makes() -> None:
    """The StartedAt read mirrors the proof's (proof_restart_controller.sh read_script): one 'docker inspect -f' per
    field, no sudo, and the guest clock read with 'date +%s'."""
    proof = (REPO_ROOT / "tools" / "session" / "proof_restart_controller.sh").read_text(encoding="utf-8")
    text = SCRIPT.read_text(encoding="utf-8")
    for read in ("docker inspect -f '{{.Id}}'", "docker inspect -f '{{.State.StartedAt}}'", "date +%s"):
        assert read in proof and read in text, read
    assert "sudo" not in text
