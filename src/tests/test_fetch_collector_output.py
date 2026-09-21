"""Cases for deployment/scripts/fetch-collector-output.sh, the harness's fetch hook.

The script under test is the repository file itself, run unmodified under every
POSIX shell available on the host. ``ssh`` and ``scp`` are replaced through
``EGW_FETCH_SSH`` / ``EGW_FETCH_SCP`` by two small fakes in which the "guest" is
this machine: the fake ssh runs the remote command locally, the fake scp copies
the local file named after ``host:``. Each fake logs its arguments, and switches
in the environment make it fail or corrupt one copy.

What these cases show is the script's own logic: which files it asks for, how it
checks them, what it prints, which exit status it returns and that it never
overwrites a local file. They say nothing about OpenSSH, the guest or the
network. The last case feeds the output of the real collector (a self-test run
on a synthetic cgroup tree) through the script to the harness's inspection, so
the diagnostics format the harness parses is the one the collector writes.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from egw_experiments import run as run_mod

if sys.platform == "win32":
    pytest.skip("fetch-collector-output.sh is POSIX sh for the harness host", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "src" / "deployment" / "scripts" / "fetch-collector-output.sh"
COLLECTOR = REPO_ROOT / "src" / "deployment" / "scripts" / "collect-resources.sh"

SHELLS = [
    pytest.param(name, marks=pytest.mark.skipif(shutil.which(name) is None, reason=f"{name} is not installed"))
    for name in ("sh", "dash", "bash")
]

FAKE_SSH = """#!/bin/sh
# fake ssh: the guest is this machine; the last argument is the remote command.
echo "ssh $*" >> "$FAKE_LOG"
if [ -n "${FAKE_SSH_FAIL:-}" ]; then
    echo "ssh: connect to host guest port 22: Connection refused" >&2
    exit 255
fi
while [ $# -gt 1 ]; do shift; done
exec sh -c "$1"
"""

FAKE_SCP = """#!/bin/sh
# fake scp: copies the local file named after 'host:' to the last argument.
echo "scp $*" >> "$FAKE_LOG"
src=
dst=
for a in "$@"; do src=$dst; dst=$a; done
path=${src#*:}
case "$path" in
    *"${FAKE_SCP_FAIL:-//none//}") echo "scp: stub transfer failure" >&2; exit 1 ;;
esac
cp "$path" "$dst" || exit 1
case "$path" in
    *"${FAKE_SCP_CORRUPT:-//none//}") printf 'x' >> "$dst" ;;
esac
exit 0
"""

MANDATORY = ("", ".diagnostics.log", ".lifecycle.csv")


class Bench:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        for name, text in (("ssh", FAKE_SSH), ("scp", FAKE_SCP)):
            path = self.bin / name
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)
        self.log = tmp_path / "fake.log"
        self.guest = tmp_path / "guest-tmp"
        self.guest.mkdir()
        self.remote = self.guest / "resources-nominal-r01.csv"
        self.local_dir = tmp_path / "results" / "raw" / "nominal-r01" / "logs" / "collector"
        self.local_dir.mkdir(parents=True)
        self.local = self.local_dir / "resources-nominal-r01.csv"

    def put(self, suffix: str, text: str | None = None) -> Path:
        path = Path(f"{self.remote}{suffix}")
        path.write_text(text if text is not None else f"content of {suffix or 'csv'}\n", encoding="utf-8")
        return path

    def put_all(self) -> None:
        for suffix in MANDATORY:
            self.put(suffix)

    def run(self, shell: str, *args: str, local: Path | None = None, **env: str) -> subprocess.CompletedProcess[str]:
        argv = [shell, str(SCRIPT), *(args or ("guest", str(self.remote), str(local or self.local)))]
        full_env = {
            **os.environ,
            "EGW_FETCH_SSH": str(self.bin / "ssh"),
            "EGW_FETCH_SCP": str(self.bin / "scp"),
            "FAKE_LOG": str(self.log),
            **env,
        }
        return subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False, env=full_env)

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []


@pytest.fixture
def bench(tmp_path: Path) -> Bench:
    return Bench(tmp_path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("shell", SHELLS)
def test_every_mandatory_file_is_fetched_and_verified(bench: Bench, shell: str) -> None:
    bench.put_all()
    result = bench.run(shell)
    assert result.returncode == 0, result.stdout + result.stderr
    for suffix in MANDATORY:
        local = Path(f"{bench.local}{suffix}")
        assert local.read_bytes() == Path(f"{bench.remote}{suffix}").read_bytes()
        assert f"fetch: resources-nominal-r01.csv{suffix} present sha256={sha(local)} verified" in result.stdout
    assert "fetch: resources-nominal-r01.csv.self-test absent (optional)" in result.stdout
    assert not Path(f"{bench.local}.self-test").exists()
    assert result.stdout.splitlines()[-1].startswith("fetch: result exit=0")
    # Every ssh and scp call is non-interactive and bounded.
    calls = bench.calls()
    assert calls and all("-o BatchMode=yes -o ConnectTimeout=10" in call for call in calls)
    assert sum(call.startswith("scp -q ") for call in calls) == 3


@pytest.mark.parametrize("shell", SHELLS)
def test_a_local_path_with_spaces_is_handled(bench: Bench, shell: str) -> None:
    bench.put_all()
    local_dir = bench.tmp / "Projeto Mestrado" / "raw dir" / "logs" / "collector"
    local_dir.mkdir(parents=True)
    local = local_dir / "resources-nominal-r01.csv"
    result = bench.run(shell, local=local)
    assert result.returncode == 0, result.stdout + result.stderr
    for suffix in MANDATORY:
        assert Path(f"{local}{suffix}").read_bytes() == Path(f"{bench.remote}{suffix}").read_bytes()


@pytest.mark.parametrize("shell", SHELLS)
def test_a_missing_mandatory_companion_exits_3_and_keeps_the_other_files(bench: Bench, shell: str) -> None:
    bench.put("")
    bench.put(".diagnostics.log")
    result = bench.run(shell)
    assert result.returncode == 3, result.stdout + result.stderr
    assert "fetch: resources-nominal-r01.csv.lifecycle.csv absent (mandatory)" in result.stdout
    assert Path(f"{bench.local}").is_file()
    assert Path(f"{bench.local}.diagnostics.log").is_file()
    assert not Path(f"{bench.local}.lifecycle.csv").exists()


@pytest.mark.parametrize("shell", SHELLS)
def test_a_copy_that_differs_from_the_guest_exits_4(bench: Bench, shell: str) -> None:
    bench.put_all()
    result = bench.run(shell, FAKE_SCP_CORRUPT=".lifecycle.csv")
    assert result.returncode == 4, result.stdout + result.stderr
    remote_sum = sha(Path(f"{bench.remote}.lifecycle.csv"))
    local = Path(f"{bench.local}.lifecycle.csv")
    assert (
        f"fetch: resources-nominal-r01.csv.lifecycle.csv present sha256={remote_sum} "
        f"local_sha256={sha(local)} MISMATCH"
    ) in result.stdout
    # The mismatched copy is left in place for inspection; the others verify.
    assert local.is_file()
    assert "fetch: resources-nominal-r01.csv.diagnostics.log present sha256=" in result.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_the_optional_self_test_marker_is_fetched_and_reported_without_changing_the_status(
    bench: Bench, shell: str
) -> None:
    bench.put_all()
    bench.put(".self-test", "self_test=1\n")
    result = bench.run(shell)
    assert result.returncode == 0, result.stdout + result.stderr
    local = Path(f"{bench.local}.self-test")
    assert local.read_text(encoding="utf-8") == "self_test=1\n"
    assert (
        f"fetch: resources-nominal-r01.csv.self-test present sha256={sha(local)} verified "
        "(self-test marker: this output is NOT a measurement)"
    ) in result.stdout


@pytest.mark.parametrize("shell", SHELLS)
def test_an_existing_local_file_is_never_overwritten(bench: Bench, shell: str) -> None:
    bench.put_all()
    existing = Path(f"{bench.local}.diagnostics.log")
    existing.write_text("earlier evidence\n", encoding="utf-8")
    result = bench.run(shell)
    assert result.returncode == 6, result.stdout + result.stderr
    assert existing.read_text(encoding="utf-8") == "earlier evidence\n"
    assert not bench.local.exists()
    assert bench.calls() == []  # refused before the guest is contacted


@pytest.mark.parametrize("shell", SHELLS)
def test_a_failed_transfer_exits_5(bench: Bench, shell: str) -> None:
    bench.put_all()
    result = bench.run(shell, FAKE_SCP_FAIL=".diagnostics.log")
    assert result.returncode == 5, result.stdout + result.stderr
    assert "fetch: resources-nominal-r01.csv.diagnostics.log transfer failed (scp exit 1)" in result.stdout
    assert Path(f"{bench.local}.lifecycle.csv").is_file()


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unreachable_guest_exits_5_and_fetches_nothing(bench: Bench, shell: str) -> None:
    bench.put_all()
    result = bench.run(shell, FAKE_SSH_FAIL="1")
    assert result.returncode == 5, result.stdout + result.stderr
    assert "ssh exit 255" in result.stdout
    assert list(bench.local_dir.iterdir()) == []


@pytest.mark.parametrize("shell", SHELLS)
def test_the_most_serious_failure_decides_the_status(bench: Bench, shell: str) -> None:
    """An absent companion (3) and a mismatched CSV (4): 4 is returned."""
    bench.put("")
    bench.put(".diagnostics.log")
    result = bench.run(shell, FAKE_SCP_CORRUPT=".csv")
    assert result.returncode == 4, result.stdout + result.stderr
    assert "absent (mandatory)" in result.stdout
    assert "MISMATCH" in result.stdout


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize(
    "args",
    [
        ("guest", "/tmp/resources-x.csv"),
        ("guest", "tmp/resources-x.csv", "LOCAL"),
        ("guest", "/tmp/resources x.csv", "LOCAL"),
        ("guest", "/tmp/resources-x.csv'; rm -rf /tmp/y '", "LOCAL"),
        ("-oProxyCommand=x", "/tmp/resources-x.csv", "LOCAL"),
        ("guest", "/tmp/resources-x.csv", "MISSING_DIR"),
    ],
)
def test_usage_errors_exit_2_before_the_guest_is_contacted(bench: Bench, shell: str, args: tuple[str, ...]) -> None:
    mapped = tuple(
        str(bench.local) if a == "LOCAL" else str(bench.tmp / "no-such-dir" / "x.csv") if a == "MISSING_DIR" else a
        for a in args
    )
    result = bench.run(shell, *mapped)
    assert result.returncode == 2, result.stdout + result.stderr
    assert bench.calls() == []


# --------------------------------------------------------------------------
# The real collector's output, fetched by the script, read by the harness
# --------------------------------------------------------------------------
CONTAINERS = {
    "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90": "egw-controller-1",
    "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c4b5a69788796a5b4c3d2e1f0": "egw-mosquitto-1",
}


def _synthetic_tree(root: Path, usage_usec: int, uptime_s: float) -> None:
    for cid, name in CONTAINERS.items():
        cg = root / "cgroup" / "system.slice" / f"docker-{cid}.scope"
        cg.mkdir(parents=True, exist_ok=True)
        (cg / "cpu.stat").write_text(f"usage_usec {usage_usec}\nuser_usec 1\nsystem_usec 2\n", encoding="utf-8")
        (cg / "memory.current").write_text(f"{200 * 1024 * 1024}\n", encoding="utf-8")
        (cg / "memory.stat").write_text(f"anon 1\ninactive_file {50 * 1024 * 1024}\n", encoding="utf-8")
        (cg / "memory.max").write_text(f"{768 * 1024 * 1024}\n", encoding="utf-8")
        conf = root / "docker" / "containers" / cid / "config.v2.json"
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text('{"ID":"%s","Name":"/%s"}' % (cid, name), encoding="utf-8")
    (root / "uptime").write_text(f"{uptime_s:.2f} {uptime_s * 4:.2f}\n", encoding="utf-8")
    (root / "meminfo").write_text("MemTotal:        8000000 kB\n", encoding="utf-8")


def _collect_once(root: Path, out: Path, stamp: int, expect: str) -> None:
    result = subprocess.run(
        [
            "sh", str(COLLECTOR), str(out), "--self-test",
            "--cgroup-root", str(root / "cgroup"), "--docker-root", str(root / "docker"),
            "--uptime-from", str(root / "uptime"), "--meminfo-from", str(root / "meminfo"),
            "--no-docker", "--source", "cgroup", "--state-file", str(root / "collector.state"),
            "--max-samples", "1", "--stamp-epoch", str(stamp), "--expect-services", expect,
        ],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("sh") is None or not Path("/proc").is_dir(), reason="needs sh and a Linux host")
def test_the_harness_reads_what_the_real_collector_writes(bench: Bench) -> None:
    """Collector (self-test) -> fetch script -> harness inspection.

    The first collector run only primes the CPU deltas (into a separate output
    that shares the state file); the second, into the output that is fetched,
    writes one row per container, one start line, the inventory and the stop
    line, and the .self-test marker a self-test run always leaves.
    """
    expect = "egw-controller-1,egw-mosquitto-1"
    root = bench.tmp / "tree"
    _synthetic_tree(root, usage_usec=0, uptime_s=100.0)
    _collect_once(root, bench.guest / "priming.csv", 1_789_779_000, expect)
    _synthetic_tree(root, usage_usec=500_000, uptime_s=101.0)
    _collect_once(root, bench.remote, 1_789_779_001, expect)

    result = bench.run("sh")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "self-test present" in result.stdout

    inspection = run_mod.inspect_collector_outputs(bench.local, expect.split(","))
    assert inspection["deployed_sha256"] == hashlib.sha256(COLLECTOR.read_bytes()).hexdigest()
    assert inspection["start_line_count"] == 1
    assert inspection["declared_expected_services"] == expect
    assert inspection["inventory_missing"] == []
    assert " inventory: observed=egw-controller-1,egw-mosquitto-1 " in inspection["inventory"]
    assert inspection["stop_line"] is not None
    assert inspection["rows_per_expected_service"] == {"egw-controller-1": 1, "egw-mosquitto-1": 1}
    assert inspection["self_test_present"] is True
    # The problem a self-test run must always raise, and then whichever of the
    # two shapes this capsule has: a run that began and ended inside one
    # wall-clock second carries the same stamp in its start and stop records,
    # so they bound no window and nothing can be reconciled against them (the
    # preflight half has refused that shape since it was written; the harness
    # half refuses it in the same words since 2026-09-20), while the same run
    # across a second boundary bounds a window and raises nothing more. Which
    # of the two it is depends on how busy the machine is, so the test asserts
    # the rule rather than the timing.
    problems = inspection["problems"]
    assert "NOT a measurement" in problems[0], problems
    empty_window = [p for p in problems if "the measured window is reversed or empty" in p]
    if inspection["window_seconds"] is None:
        assert empty_window, problems
        assert len(problems) == 2, problems
    else:
        assert not empty_window, problems
        assert len(problems) == 1, problems
        assert inspection["window_seconds"] >= 0
    for key in ("csv", "diagnostics", "lifecycle", "self_test"):
        assert inspection["files"][key]["present"] is True
