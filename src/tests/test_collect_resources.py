"""Cases for deployment/scripts/collect-resources.sh, the SUT resource collector.

The script under test is the repository file itself, run unmodified under every
POSIX shell available on the host — and, when ``EGW_TEST_BUSYBOX_DIR`` names a
directory of wrappers for the gateway image's own busybox (``sh``, ``awk`` and
the applets the script calls; ``tools/test/make-busybox-wrappers.sh`` builds
them), under that busybox too, which is the shell and awk the guest actually
runs. Eight cases are host-shell only, because they put a fake ``awk`` or
``docker`` ahead of the real one on PATH or run two collectors side by side. Nothing here needs Docker, a container or a cgroup:
the collector is pointed at a synthetic ``/sys/fs/cgroup`` tree, a synthetic
``/proc/uptime`` and, for one-shot samples, a synthetic wall-clock second with
its ``--self-test`` options, so the arithmetic is exact and reproducible.

Those options are refused without ``--self-test`` and a self-test run marks its
own output: the collector produces evidence, so a file read from substituted
inputs must never be mistakable for a measured one. The cases that check pacing
and the production ingest limits use the real clocks.

What these cases show is that the collector reads the kernel's accounting the
way ``docker stats`` reports it, that it writes no row rather than a made-up
number when an input cannot be read, that it never stamps a second twice, that
it records every diagnostic and lifecycle event, and that its rows satisfy the
ingest contract of ``egw_experiments.resources``. They say nothing about the
behaviour of a real container, about Docker or about the emulated guest.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from egw_experiments.resources import CSV_HEADER, validate_resources_csv

if sys.platform == "win32":
    pytest.skip("collect-resources.sh needs a POSIX host (sh, awk)", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "src" / "deployment" / "scripts" / "collect-resources.sh"
if not SCRIPT.is_file():
    pytest.skip(f"{SCRIPT} is not in this tree", allow_module_level=True)

# The gateway image's busybox, when a directory of wrappers for it is given
# (sh, awk, date, grep, sed, head, mv, rm, rmdir, mkdir, hostname, uname,
# sha256sum, cat, sleep, ...). Every command the script runs then resolves to
# that busybox, because PATH holds nothing else.
BUSYBOX_DIR = os.environ.get("EGW_TEST_BUSYBOX_DIR", "")
HAVE_BUSYBOX = bool(BUSYBOX_DIR) and os.access(os.path.join(BUSYBOX_DIR, "sh"), os.X_OK)

SHELLS = [
    pytest.param("sh", marks=pytest.mark.skipif(shutil.which("sh") is None, reason="sh is not installed")),
    pytest.param("dash", marks=pytest.mark.skipif(shutil.which("dash") is None, reason="dash is not installed")),
    pytest.param("bash", marks=pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")),
    pytest.param(
        "busybox",
        marks=pytest.mark.skipif(not HAVE_BUSYBOX, reason="EGW_TEST_BUSYBOX_DIR does not name busybox wrappers"),
    ),
]
HOST_SHELLS = SHELLS[:3]
# One host shell plus the image's busybox for the long real-time cases.
LONG_RUN_SHELLS = [SHELLS[1], SHELLS[3]]


def shell_command(shell: str) -> tuple[list[str], dict[str, str]]:
    """The command prefix and the environment that run the script under a shell."""
    if shell == "busybox":
        return [os.path.join(BUSYBOX_DIR, "sh")], {"PATH": BUSYBOX_DIR, "HOME": "/tmp"}
    return [shell], dict(os.environ)


# Two containers, one under each cgroup driver layout: the systemd driver's
# scope and the cgroupfs driver's directory.
SCOPE_ID = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
PLAIN_ID = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c4b5a69788796a5b4c3d2e1f0"

MIB = 1024 * 1024
BASE_EPOCH = 1_789_779_000
TIMESTAMPED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ")
# The cases that run on the real clocks read /proc/uptime.
NEEDS_PROC = pytest.mark.skipif(not Path("/proc/uptime").exists(), reason="no /proc/uptime on this host")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def utc(epoch: int) -> str:
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Tree:
    """A synthetic cgroup v2 tree the collector can be pointed at."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.cgroup_root = root / "cgroup"
        self.docker_root = root / "docker"
        self.uptime = root / "uptime"
        self.meminfo = root / "meminfo"
        self.state = root / "collector.state"
        self.out = root / "resources.csv"
        self.cgroup_root.mkdir(parents=True, exist_ok=True)
        write(self.meminfo, "MemTotal:        8000000 kB\nMemFree:  1000000 kB\n")
        self.set_uptime(100.0)
        self.next_stamp = BASE_EPOCH

    def dir_for(self, container_id: str, *, systemd_driver: bool) -> Path:
        if systemd_driver:
            return self.cgroup_root / "system.slice" / f"docker-{container_id}.scope"
        return self.cgroup_root / "docker" / container_id

    def set_uptime(self, seconds: float) -> None:
        write(self.uptime, f"{seconds:.2f} {seconds * 4:.2f}\n")

    def set_container(
        self,
        container_id: str,
        *,
        systemd_driver: bool = True,
        usage_usec: int | None = 1_000_000,
        memory_current: int = 200 * MIB,
        inactive_file: int | None = 50 * MIB,
        memory_max: int | str | None = 768 * MIB,
    ) -> Path:
        d = self.dir_for(container_id, systemd_driver=systemd_driver)
        if usage_usec is None:
            write(d / "cpu.stat", "user_usec 1\nsystem_usec 2\n")
        else:
            write(d / "cpu.stat", f"usage_usec {usage_usec}\nuser_usec 1\nsystem_usec 2\n")
        write(d / "memory.current", f"{memory_current}\n")
        if inactive_file is None:
            (d / "memory.stat").unlink(missing_ok=True)
        else:
            write(d / "memory.stat", f"anon 1\nfile 2\ninactive_file {inactive_file}\nslab 3\n")
        if memory_max is None:
            (d / "memory.max").unlink(missing_ok=True)
        else:
            write(d / "memory.max", f"{memory_max}\n")
        return d

    def set_name(self, container_id: str, name: str) -> None:
        # The shape the collector reads: the top-level "Name" of the
        # container's own config.v2.json, with Docker's leading slash.
        write(
            self.docker_root / "containers" / container_id / "config.v2.json",
            '{"StreamConfig":{},"State":{"Running":true},"ID":"%s","Name":"/%s",'
            '"MountPoints":{"d":{"Name":"a-named-volume"}},"Driver":"overlay2"}'
            % (container_id, name),
        )

    def argv(self, shell: str, *args: str, self_test: bool = True, no_docker: bool = True) -> list[str]:
        prefix, _ = shell_command(shell)
        cmd = [*prefix, str(SCRIPT), str(self.out)]
        if self_test:
            cmd += [
                "--self-test",
                "--cgroup-root",
                str(self.cgroup_root),
                "--docker-root",
                str(self.docker_root),
                "--uptime-from",
                str(self.uptime),
                "--meminfo-from",
                str(self.meminfo),
            ]
        if no_docker:
            cmd += ["--no-docker"]
        cmd += ["--state-file", str(self.state), *args]
        return cmd

    def run(
        self,
        shell: str,
        *args: str,
        timeout: int = 120,
        env: dict[str, str] | None = None,
        **kw,
    ) -> subprocess.CompletedProcess[str]:
        _, base_env = shell_command(shell)
        return subprocess.run(
            self.argv(shell, *args, **kw),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**base_env, **(env or {})},
        )

    def one(self, shell: str, *args: str, stamp: int | None = None, **kw) -> subprocess.CompletedProcess[str]:
        """One sample in a given wall-clock second (by default, the next one)."""
        if stamp is None:
            stamp = self.next_stamp
        self.next_stamp = max(self.next_stamp, stamp) + 1
        return self.run(shell, "--max-samples", "1", "--stamp-epoch", str(stamp), *args, **kw)

    def sample(self, shell: str, *args: str, stamp: int | None = None) -> subprocess.CompletedProcess[str]:
        return self.one(shell, "--source", "cgroup", *args, stamp=stamp)

    def rows(self) -> list[dict[str, str]]:
        with self.out.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def diagnostics(self) -> list[str]:
        return Path(f"{self.out}.diagnostics.log").read_text(encoding="utf-8").splitlines()

    def lifecycle(self) -> list[tuple[str, str, str]]:
        with Path(f"{self.out}.lifecycle.csv").open(encoding="utf-8", newline="") as handle:
            return [(row["event"], row["container_id"], row["name"]) for row in csv.DictReader(handle)]

    def state_lines(self) -> list[list[str]]:
        return [line.split("\t") for line in self.state.read_text(encoding="utf-8").splitlines()]


@pytest.fixture()
def tree(tmp_path: Path) -> Tree:
    return Tree(tmp_path)


# --------------------------------------------------------------------------
# What one sample computes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
def test_first_sample_only_primes_the_delta(tree: Tree, shell: str) -> None:
    """A CPU percentage needs two readings, so the first sample writes no row."""
    tree.set_container(SCOPE_ID)
    tree.set_name(SCOPE_ID, "egw-controller")

    result = tree.sample(shell)

    assert result.returncode == 0, result.stderr
    assert tree.out.read_text(encoding="utf-8").splitlines() == [",".join(CSV_HEADER)]
    assert tree.rows() == []


@pytest.mark.parametrize("shell", SHELLS)
def test_second_sample_reports_the_docker_quantities(tree: Tree, shell: str) -> None:
    """Exact arithmetic of one interval, against the definitions docker uses.

    Half a second of CPU over one second of elapsed time is 50 % on docker's
    single-CPU basis; the reported memory is ``memory.current`` minus
    ``inactive_file``, as a percentage of ``memory.max``; the timestamp is the
    sample's wall-clock second.
    """
    tree.set_container(SCOPE_ID, usage_usec=1_000_000, memory_current=200 * MIB)
    tree.set_name(SCOPE_ID, "egw-controller")
    assert tree.sample(shell, stamp=BASE_EPOCH).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(
        SCOPE_ID,
        usage_usec=1_500_000,
        memory_current=300 * MIB,
        inactive_file=100 * MIB,
        memory_max=400 * MIB,
    )
    result = tree.sample(shell, stamp=BASE_EPOCH + 1)

    assert result.returncode == 0, result.stderr
    rows = tree.rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["container"] == "egw-controller"
    assert float(row["cpu_pct"]) == pytest.approx(50.0, abs=0.01)
    assert int(row["mem_bytes"]) == 200 * MIB
    assert float(row["mem_pct"]) == pytest.approx(50.0, abs=0.01)
    assert row["host"]
    assert row["ts_utc"] == utc(BASE_EPOCH + 1)


@pytest.mark.parametrize("shell", SHELLS)
def test_cpu_percentage_exceeds_one_hundred_for_a_multi_threaded_container(
    tree: Tree, shell: str
) -> None:
    """docker's basis is one CPU, so a container using three cores reads 300 %."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(102.0)
    tree.set_container(SCOPE_ID, usage_usec=6_000_000)

    assert tree.sample(shell).returncode == 0
    assert float(tree.rows()[0]["cpu_pct"]) == pytest.approx(300.0, abs=0.01)


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("start", [12345.67, 123456.30, 1234567.89])
def test_a_long_uptime_keeps_its_precision(tree: Tree, shell: str, start: float) -> None:
    """The stored uptime is never re-rounded, however long the guest has been up.

    Written back as an awk number it would be rounded to 0.1 s after 2.8 h, to
    1 s after 27.8 h, and turned into exponent form after 11.6 days — silently
    wrong CPU percentages, then no rows at all.
    """
    tree.set_uptime(start)
    tree.set_container(SCOPE_ID, usage_usec=1_000_000)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(start + 1.0)
    tree.set_container(SCOPE_ID, usage_usec=1_500_000)
    assert tree.sample(shell).returncode == 0

    rows = tree.rows()
    assert len(rows) == 1
    assert float(rows[0]["cpu_pct"]) == pytest.approx(50.0, abs=0.01)
    assert [line for line in tree.state_lines() if line[0] == SCOPE_ID][0][2] == f"{start + 1.0:.2f}"


@pytest.mark.parametrize("shell", SHELLS)
def test_both_cgroup_driver_layouts_are_sampled(tree: Tree, shell: str) -> None:
    """The systemd driver's scope and the cgroupfs driver's directory both count."""
    tree.set_container(SCOPE_ID, systemd_driver=True, usage_usec=0)
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller")
    tree.set_name(PLAIN_ID, "egw-mosquitto")
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, systemd_driver=True, usage_usec=100_000)
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=200_000)

    assert tree.sample(shell).returncode == 0
    assert {row["container"] for row in tree.rows()} == {"egw-controller", "egw-mosquitto"}


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unlimited_cgroup_uses_the_host_memory_total(tree: Tree, shell: str) -> None:
    """``memory.max`` of ``max`` means no limit; the percentage is of MemTotal."""
    tree.set_container(SCOPE_ID, usage_usec=0, memory_max="max")
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(
        SCOPE_ID,
        usage_usec=0,
        memory_current=1_024_000_000,
        inactive_file=24_000_000,
        memory_max="max",
    )

    assert tree.sample(shell).returncode == 0
    row = tree.rows()[0]
    assert int(row["mem_bytes"]) == 1_000_000_000
    # MemTotal is 8000000 kB = 8_192_000_000 bytes.
    assert float(row["mem_pct"]) == pytest.approx(100 * 1_000_000_000 / 8_192_000_000, abs=0.01)


@pytest.mark.parametrize("shell", SHELLS)
def test_inactive_file_above_usage_reports_the_usage_as_docker_does(tree: Tree, shell: str) -> None:
    """The two files are read at different moments; docker then keeps memory.current.

    Clamping to zero would write a zero memory measurement, which is a claim.
    """
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=10_000, memory_current=100 * MIB, inactive_file=120 * MIB)

    assert tree.sample(shell).returncode == 0
    assert int(tree.rows()[0]["mem_bytes"]) == 100 * MIB


# --------------------------------------------------------------------------
# A failed sample is a hole, never a number
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("memory_max", ["", None], ids=["empty", "missing"])
def test_an_unreadable_memory_max_is_not_unlimited(
    tree: Tree, shell: str, memory_max: str | None
) -> None:
    """An empty or missing memory.max is a failed read, never permission to use MemTotal."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=500_000, memory_max=memory_max)

    result = tree.sample(shell)

    assert result.returncode == 0
    assert tree.rows() == []
    assert any("unreadable or empty memory.max" in line for line in tree.diagnostics())


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unreadable_memory_stat_writes_no_row(tree: Tree, shell: str) -> None:
    """Without ``inactive_file`` the used memory is unknown, and a zero would be a claim."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=500_000, inactive_file=None)

    result = tree.sample(shell)

    assert result.returncode == 0
    assert tree.rows() == []
    assert "memory.stat" in result.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unlimited_cgroup_without_memtotal_writes_no_row(tree: Tree, shell: str) -> None:
    """No limit and no MemTotal means no percentage; the row is dropped, not zeroed."""
    tree.set_container(SCOPE_ID, usage_usec=0, memory_max="max")
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=500_000, memory_max="max")
    write(tree.meminfo, "MemFree: 1000000 kB\n")

    result = tree.sample(shell)

    assert result.returncode == 0
    assert tree.rows() == []
    assert any("MemTotal is unreadable" in line for line in tree.diagnostics())


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unreadable_sample_costs_one_row_and_not_two(tree: Tree, shell: str) -> None:
    """The previous reading is kept, so the next delta simply spans two intervals."""
    tree.set_container(SCOPE_ID, usage_usec=1_000_000)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=None)
    assert tree.sample(shell).returncode == 0
    assert tree.rows() == []

    # One second later the delta spans the two seconds since the last good
    # reading: 1.0 s of CPU over 2.0 s is 50 %.
    tree.set_uptime(102.0)
    tree.set_container(SCOPE_ID, usage_usec=2_000_000)

    assert tree.sample(shell).returncode == 0
    rows = tree.rows()
    assert len(rows) == 1
    assert float(rows[0]["cpu_pct"]) == pytest.approx(50.0, abs=0.01)


@pytest.mark.parametrize("shell", SHELLS)
def test_a_counter_that_goes_backwards_is_not_reported(tree: Tree, shell: str) -> None:
    """A recreated cgroup restarts its counter: no row, and a lifecycle event."""
    tree.set_container(SCOPE_ID, usage_usec=5_000_000)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=1_000)

    assert tree.sample(shell).returncode == 0
    assert tree.rows() == []
    assert ("counter_reset", SCOPE_ID, "") in tree.lifecycle()


@pytest.mark.parametrize("shell", SHELLS)
def test_a_container_that_disappears_stops_producing_rows(tree: Tree, shell: str) -> None:
    """A stopped container leaves the tree; the collector keeps going."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=10_000)
    shutil.rmtree(tree.dir_for(PLAIN_ID, systemd_driver=False))

    assert tree.sample(shell).returncode == 0
    assert [row["container"] for row in tree.rows()] == [SCOPE_ID[:12]]


@pytest.mark.parametrize("shell", HOST_SHELLS)
def test_a_failed_sampler_process_is_recorded(tree: Tree, shell: str) -> None:
    """A sample whose awk process dies (killed, OOM, fork failure) leaves a diagnostic, not only a hole."""
    real_awk = shutil.which("awk")
    assert real_awk
    bin_dir = tree.root / "bin"
    flag = tree.root / "kill-sampler"
    write(
        bin_dir / "awk",
        "#!/bin/sh\n"
        "for a in \"$@\"; do case \"$a\" in *PREV_USAGE*) [ -e '%s' ] && kill -KILL $$ ;; esac; done\n"
        "exec '%s' \"$@\"\n" % (flag, real_awk),
    )
    (bin_dir / "awk").chmod(0o755)
    env = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    flag.write_text("1", encoding="utf-8")
    tree.set_uptime(101.0)
    result = tree.run(shell, "--source", "cgroup", "--max-samples", "1", "--stamp-epoch", str(BASE_EPOCH + 5), env=env)

    assert result.returncode == 0, result.stderr
    assert any("the sampler process exited with status" in line for line in tree.diagnostics())


# --------------------------------------------------------------------------
# One stamp per second, and every second accounted for
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
def test_a_second_already_stamped_is_withheld(tree: Tree, shell: str) -> None:
    """Two samples in one wall-clock second: the second one writes nothing."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell, stamp=BASE_EPOCH).returncode == 0
    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=100_000)
    assert tree.sample(shell, stamp=BASE_EPOCH + 1).returncode == 0
    before = tree.state_lines()

    tree.set_uptime(101.5)
    tree.set_container(SCOPE_ID, usage_usec=150_000)
    result = tree.sample(shell, stamp=BASE_EPOCH + 1)

    assert result.returncode == 0
    assert [row["ts_utc"] for row in tree.rows()] == [utc(BASE_EPOCH + 1)]
    assert any("sample withheld at uptime 101.50 s" in line for line in tree.diagnostics())
    after = tree.state_lines()
    assert after[1:] == before[1:], "a withheld sample changed a container's readings"
    # The last stamped second, the gap count and that sample's uptime stay;
    # the sample is counted as withheld, in the current run of them.
    assert after[0][:4] == before[0][:4]
    assert after[0][4:6] == ["1", "1"]


@pytest.mark.parametrize("shell", SHELLS)
def test_a_clock_stepped_back_never_writes_an_earlier_second(tree: Tree, shell: str) -> None:
    """A backward step would make ts_utc go back and the harness reject the whole file."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell, stamp=BASE_EPOCH + 10).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=100_000)
    assert tree.sample(shell, stamp=BASE_EPOCH + 5).returncode == 0

    assert tree.rows() == []
    assert any("stepped back" in line for line in tree.diagnostics())


@pytest.mark.parametrize("shell", SHELLS)
def test_forward_utc_gaps_are_counted(tree: Tree, shell: str) -> None:
    """Every second of UTC left without a stamp is written down and summed in the closing line."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell, stamp=BASE_EPOCH).returncode == 0

    tree.set_uptime(104.0)
    tree.set_container(SCOPE_ID, usage_usec=400_000)
    assert tree.sample(shell, stamp=BASE_EPOCH + 4).returncode == 0

    lines = tree.diagnostics()
    assert any("forward UTC gap: no sample stamped in the 3 second(s) before this one" in line for line in lines)
    stop = [line for line in lines if " stop: " in line][-1]
    assert "utc_gap_seconds=3 withheld_samples=0 withheld_elapsed_s=0.00" in stop
    assert len(tree.rows()) == 1


@pytest.mark.parametrize("shell", SHELLS)
def test_a_clock_stepped_back_then_recovered_is_counted_on_the_elapsed_clock(tree: Tree, shell: str) -> None:
    """The stamps resume at the next second, so the UTC count sees nothing; the elapsed time does.

    Last accepted stamp S at uptime 101 s. The wall clock steps back about
    4 s and stays there: the samples at uptime 102-105 s fall in S-3 .. S and
    are withheld. At 106 s the stamps pass S again and S+1 is accepted: a
    forward UTC gap of zero, but 5 s of elapsed time since the last accepted
    sample, 4 s of them beyond the one-second interval.
    """
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell, stamp=BASE_EPOCH + 10).returncode == 0
    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=100_000)
    assert tree.sample(shell, stamp=BASE_EPOCH + 11).returncode == 0

    for uptime, stamp in ((102.0, 8), (103.0, 9), (104.0, 10), (105.0, 11)):
        tree.set_uptime(uptime)
        assert tree.sample(shell, stamp=BASE_EPOCH + stamp).returncode == 0

    tree.set_uptime(106.0)
    tree.set_container(SCOPE_ID, usage_usec=200_000)
    assert tree.sample(shell, stamp=BASE_EPOCH + 12).returncode == 0

    assert [row["ts_utc"] for row in tree.rows()] == [utc(BASE_EPOCH + 11), utc(BASE_EPOCH + 12)]
    lines = tree.diagnostics()
    assert sum("sample withheld at uptime" in line for line in lines) == 4
    assert not any("forward UTC gap" in line for line in lines)
    assert any(
        "stamps resumed after 4 withheld sample(s): 4.00 s of elapsed time without an accepted sample" in line
        and "(uptime 101.00 s to 106.00 s, less one interval)" in line
        for line in lines
    )
    # A run that ends inside the withheld stretch says so, since no accepted
    # sample has measured it yet.
    assert any("the run ended 1 withheld sample(s) after the last accepted one: 1.00 s" in line for line in lines)
    stops = [line for line in lines if " stop: " in line]
    assert "withheld_open_at_stop=1 " in stops[2]
    assert (
        "utc_gap_seconds=0 withheld_samples=4 withheld_elapsed_s=4.00 withheld_runs_unmeasured=0 "
        "withheld_open_at_stop=0 " in stops[-1]
    )


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize(
    ("resume_uptime", "resume_after_s", "gap", "elapsed"),
    [
        # The clock is corrected forward while samples are withheld: the two
        # missed seconds are UTC gaps, and nothing is left for the other count.
        (104.0, 3, 2, "0.00"),
        # The stamps resume late: 6 s beyond the interval, 3 of them UTC gaps.
        (108.0, 4, 3, "3.00"),
    ],
)
def test_the_two_counts_never_hold_the_same_seconds(
    tree: Tree, shell: str, resume_uptime: float, resume_after_s: int, gap: int, elapsed: str
) -> None:
    """A run of withheld samples that ends with a forward UTC gap: the elapsed figure leaves those seconds out.

    Last accepted stamp S at uptime 101 s; the samples at 102 and 103 s are
    stamped S-3 and S-2 and withheld; the next is accepted in a second more
    than one after S.
    """
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell, stamp=BASE_EPOCH + 10).returncode == 0
    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=100_000)
    assert tree.sample(shell, stamp=BASE_EPOCH + 11).returncode == 0
    for uptime, stamp in ((102.0, 8), (103.0, 9)):
        tree.set_uptime(uptime)
        assert tree.sample(shell, stamp=BASE_EPOCH + stamp).returncode == 0

    tree.set_uptime(resume_uptime)
    tree.set_container(SCOPE_ID, usage_usec=200_000)
    assert tree.sample(shell, stamp=BASE_EPOCH + 11 + resume_after_s).returncode == 0

    lines = tree.diagnostics()
    assert any(f"forward UTC gap: no sample stamped in the {gap} second(s)" in line for line in lines)
    assert any(
        f"stamps resumed after 2 withheld sample(s): {elapsed} s of elapsed time without an accepted sample" in line
        and f"less one interval and the {gap} forward UTC-gap second(s) just counted" in line
        for line in lines
    )
    stop = [line for line in lines if " stop: " in line][-1]
    assert f"utc_gap_seconds={gap} withheld_samples=2 withheld_elapsed_s={elapsed} " in stop


# --------------------------------------------------------------------------
# Names and lifecycle
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
def test_the_name_falls_back_to_the_short_id(tree: Tree, shell: str) -> None:
    """No config.v2.json and no docker: the row still carries a non-empty name."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=10_000)

    assert tree.sample(shell).returncode == 0
    assert tree.rows()[0]["container"] == SCOPE_ID[:12]


@pytest.mark.parametrize("shell", SHELLS)
def test_a_name_that_becomes_readable_later_is_picked_up(tree: Tree, shell: str) -> None:
    """The short id is provisional: it must never be cached as the name."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=10_000)
    assert tree.sample(shell).returncode == 0
    assert tree.rows()[0]["container"] == SCOPE_ID[:12]

    tree.set_name(SCOPE_ID, "egw-controller")
    tree.set_uptime(102.0)
    tree.set_container(SCOPE_ID, usage_usec=20_000)

    assert tree.sample(shell).returncode == 0
    assert [row["container"] for row in tree.rows()] == [SCOPE_ID[:12], "egw-controller"]


@pytest.mark.parametrize("shell", SHELLS)
def test_a_docker_ps_listing_names_a_container_without_its_config_file(
    tree: Tree, shell: str
) -> None:
    """The unprivileged fallback: names read from a cached ``docker ps`` listing."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    write(Path(f"{tree.state}.names"), f"{SCOPE_ID} egw-ditto-things\n")
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=10_000)

    assert tree.sample(shell).returncode == 0
    assert tree.rows()[0]["container"] == "egw-ditto-things"


@pytest.mark.parametrize("shell", HOST_SHELLS)
def test_docker_is_not_called_when_every_container_names_itself(tree: Tree, shell: str) -> None:
    """The Docker CLI costs seconds on the guest: it is used only for a name nothing else gives."""
    bin_dir = tree.root / "bin"
    calls = tree.root / "docker-calls"
    write(bin_dir / "docker", f"#!/bin/sh\necho \"$*\" >> '{calls}'\nexit 1\n")
    (bin_dir / "docker").chmod(0o755)
    env = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller")

    result = tree.run(
        shell, "--source", "cgroup", "--max-samples", "1", "--stamp-epoch", str(BASE_EPOCH), env=env, no_docker=False
    )
    assert result.returncode == 0, result.stderr
    assert not calls.exists(), calls.read_text(encoding="utf-8")

    # A container without its config file does need the listing.
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=0)
    result = tree.run(
        shell, "--source", "cgroup", "--max-samples", "1", "--stamp-epoch", str(BASE_EPOCH + 1), env=env, no_docker=False
    )
    assert result.returncode == 0, result.stderr
    assert calls.read_text(encoding="utf-8").startswith("ps -a")


@NEEDS_PROC
@pytest.mark.parametrize("shell", HOST_SHELLS)
def test_an_id_a_partial_listing_omits_is_asked_for_again(tree: Tree, shell: str) -> None:
    """A ``docker ps`` answer that omits a container leaves it to the next listing, whatever came before.

    One continuous run, because listings are rate-limited within a run (one
    every 10 s at most). The first answer names only A, the second only B,
    the third both. Between the second and the third, A's cgroup is removed
    and recreated under the same id, as a restart does: A comes back unnamed,
    because the listing kept is the second one, and must be named by the
    third. Neither container has a readable config.v2.json.
    """
    tree.uptime = Path("/proc/uptime")
    bin_dir = tree.root / "bin"
    calls = tree.root / "docker-calls"
    write(
        bin_dir / "docker",
        "#!/bin/sh\n"
        '[ "$1" = ps ] || exit 1\n'
        f"echo \"$*\" >> '{calls}'\n"
        f"n=$(wc -l < '{calls}')\n"
        f"[ \"$n\" -ne 2 ] && echo '{SCOPE_ID} egw-a'\n"
        f"[ \"$n\" -ge 2 ] && echo '{PLAIN_ID} egw-b'\n"
        "exit 0\n",
    )
    (bin_dir / "docker").chmod(0o755)
    env = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=0)
    scope = tree.dir_for(SCOPE_ID, systemd_driver=True)

    def restart() -> None:
        # After the second listing (about 10-11 s in), before the third (20 s).
        time.sleep(13.5)
        shutil.rmtree(scope)
        time.sleep(2.0)
        tree.set_container(SCOPE_ID, usage_usec=0)

    thread = threading.Thread(target=restart)
    thread.start()
    result = tree.run(
        shell, "--source", "cgroup", "--interval", "1", "--max-samples", "25", env=env, no_docker=False
    )
    thread.join()

    assert result.returncode == 0, result.stderr
    assert len(calls.read_text(encoding="utf-8").splitlines()) == 3
    events = tree.lifecycle()
    assert ("named", PLAIN_ID, "egw-b") in events
    a_events = [event for event in events if event[1] == SCOPE_ID]
    assert a_events == [
        ("appeared", SCOPE_ID, "egw-a"),
        ("disappeared", SCOPE_ID, "egw-a"),
        ("appeared", SCOPE_ID, ""),
        ("named", SCOPE_ID, "egw-a"),
    ]
    assert tree.rows()[-1]["container"] in {"egw-a", "egw-b"}


@pytest.mark.parametrize("shell", SHELLS)
def test_a_named_volume_does_not_shadow_the_container_name(tree: Tree, shell: str) -> None:
    """``config.v2.json`` also holds mount names; only the container's own has a slash."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-mongodb")
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=10_000)

    assert tree.sample(shell).returncode == 0
    assert tree.rows()[0]["container"] == "egw-mongodb"


@pytest.mark.parametrize("shell", SHELLS)
def test_the_lifecycle_records_the_mapping_and_a_restart(tree: Tree, shell: str) -> None:
    """Appearance, first naming and disappearance, by container id."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller")
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    # The second container becomes nameable; the first one stops.
    tree.set_uptime(101.0)
    tree.set_name(PLAIN_ID, "egw-mosquitto")
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=10_000)
    shutil.rmtree(tree.dir_for(SCOPE_ID, systemd_driver=True))
    assert tree.sample(shell).returncode == 0

    # The first container comes back under the same id.
    tree.set_uptime(102.0)
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=20_000)
    assert tree.sample(shell).returncode == 0

    events = tree.lifecycle()
    # The first sample lists both containers in discovery order; sort that pair.
    assert sorted(events[:2]) == [("appeared", PLAIN_ID, ""), ("appeared", SCOPE_ID, "egw-controller")]
    assert events[2:] == [
        ("named", PLAIN_ID, "egw-mosquitto"),
        ("disappeared", SCOPE_ID, "egw-controller"),
        ("appeared", SCOPE_ID, "egw-controller"),
    ]


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unreadable_first_read_is_one_appearance(tree: Tree, shell: str) -> None:
    """A container whose first reads fail appears once, not once per failed read."""
    tree.set_container(SCOPE_ID, usage_usec=None)
    assert tree.sample(shell).returncode == 0
    tree.set_uptime(101.0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(102.0)
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0
    tree.set_uptime(103.0)
    tree.set_container(SCOPE_ID, usage_usec=100_000)
    assert tree.sample(shell).returncode == 0

    assert [event for event in tree.lifecycle() if event[0] == "appeared"] == [("appeared", SCOPE_ID, "")]
    assert len(tree.rows()) == 1


@pytest.mark.parametrize("shell", SHELLS)
def test_the_service_inventory_is_recorded(tree: Tree, shell: str) -> None:
    """Expected services against the names actually seen, in one line."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller-1")

    result = tree.sample(shell, "--expect-services", "egw-controller-1,egw-mosquitto-1")

    assert result.returncode == 0
    lines = tree.diagnostics()
    inventory = [line for line in lines if " inventory: " in line]
    assert len(inventory) == 1
    assert "observed=egw-controller-1" in inventory[0]
    assert "missing=egw-mosquitto-1" in inventory[0]
    assert any(line.endswith("expected service never observed: egw-mosquitto-1") for line in lines)


@pytest.mark.parametrize("shell", SHELLS)
def test_the_inventory_lists_what_was_observed_without_a_declaration(tree: Tree, shell: str) -> None:
    """With no --expect-services the line still names every service seen."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller-1")
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=0)

    assert tree.sample(shell).returncode == 0

    inventory = [line for line in tree.diagnostics() if " inventory: " in line]
    assert len(inventory) == 1
    assert "observed=egw-controller-1 " in inventory[0]
    assert "expected=none-declared" in inventory[0]
    assert "unnamed_ids=1" in inventory[0]


@pytest.mark.parametrize("shell", HOST_SHELLS)
def test_an_awk_without_systime_is_stamped_by_date(tree: Tree, shell: str) -> None:
    """If awk offers no usable systime(), each sample takes its second from date, not nothing."""
    real_awk = shutil.which("awk")
    assert real_awk
    bin_dir = tree.root / "bin"
    write(
        bin_dir / "awk",
        "#!/bin/sh\n"
        "case \"$1\" in *systime*) case \"$*\" in *PREV_USAGE*) ;; *) exit 1 ;; esac ;; esac\n"
        "exec '%s' \"$@\"\n" % real_awk,
    )
    (bin_dir / "awk").chmod(0o755)
    env = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    tree.uptime = Path("/proc/uptime") if Path("/proc/uptime").exists() else tree.uptime
    tree.set_container(SCOPE_ID, usage_usec=0)

    result = tree.run(shell, "--source", "cgroup", "--interval", "1", "--max-samples", "3", env=env)

    assert result.returncode == 0, result.stderr
    assert any("timestamps: date +%s per sample" in line for line in tree.diagnostics())
    assert len(tree.rows()) == 2
    assert len({row["ts_utc"] for row in tree.rows()}) == 2


# --------------------------------------------------------------------------
# Evidence integrity
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
def test_substituted_inputs_are_refused_without_self_test(tree: Tree, shell: str) -> None:
    """A measurement never reads its inputs from a path given on the command line."""
    tree.set_container(SCOPE_ID)
    prefix, env = shell_command(shell)
    result = subprocess.run(
        [*prefix, str(SCRIPT), str(tree.out), "--cgroup-root", str(tree.cgroup_root), "--max-samples", "1"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )

    assert result.returncode == 2
    assert "self-test" in result.stderr
    assert not tree.out.exists()


@pytest.mark.parametrize("shell", SHELLS)
def test_a_substituted_clock_needs_one_sample_only(tree: Tree, shell: str) -> None:
    result = tree.run(shell, "--max-samples", "2", "--stamp-epoch", str(BASE_EPOCH))
    assert result.returncode == 2


@pytest.mark.parametrize("shell", SHELLS)
def test_a_self_test_run_marks_its_own_output(tree: Tree, shell: str) -> None:
    """The sidecar and the banner are what tell a synthetic file from a measured one."""
    tree.set_container(SCOPE_ID)

    result = tree.sample(shell)

    assert result.returncode == 0
    assert "NOT a measurement" in result.stderr
    sidecar = Path(f"{tree.out}.self-test").read_text(encoding="utf-8")
    assert "self_test=1" in sidecar
    assert str(tree.cgroup_root) in sidecar
    assert str(tree.uptime) in sidecar
    assert "stamp-epoch=" in sidecar


@pytest.mark.parametrize("shell", SHELLS)
def test_every_run_records_the_exact_collector(tree: Tree, shell: str) -> None:
    """The start line carries the collector's own sha256, so no run is bound to the wrong version."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    expected = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    starts = [line for line in tree.diagnostics() if " start: " in line]
    assert len(starts) == 1
    assert f"collector_sha256={expected}" in starts[0]


@pytest.mark.parametrize("shell", SHELLS)
def test_diagnostics_are_timestamped_and_survive_exit(tree: Tree, shell: str) -> None:
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0
    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=None)
    assert tree.sample(shell).returncode == 0

    lines = tree.diagnostics()
    assert lines and all(TIMESTAMPED.match(line) for line in lines), lines
    assert sum(" start: " in line for line in lines) == 2
    assert sum(" stop: " in line for line in lines) == 2
    assert sum("unreadable cpu.stat or memory.current" in line for line in lines) == 1


@pytest.mark.parametrize("shell", HOST_SHELLS)
def test_a_second_collector_on_the_same_output_is_refused(tree: Tree, shell: str) -> None:
    """Two collectors appending to one CSV would duplicate rows that look valid."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    first = subprocess.Popen(
        tree.argv(shell, "--source", "cgroup", "--max-samples", "4", "--interval", "1"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(1.5)
        second = tree.run(
            shell,
            "--source",
            "cgroup",
            "--max-samples",
            "1",
            "--state-file",
            str(tree.root / "other.state"),
        )
        assert second.returncode == 1
        assert "another collector" in second.stderr
    finally:
        first.wait(timeout=60)

    # The lock is released when the first collector ends.
    assert not Path(f"{tree.out}.lock").exists()


@pytest.mark.parametrize("shell", SHELLS)
def test_the_state_file_is_replaced_whole(tree: Tree, shell: str) -> None:
    """The state is written to a temporary file and moved, never truncated in place."""
    tree.set_container(SCOPE_ID, usage_usec=1_234_567)
    tree.set_name(SCOPE_ID, "egw-controller")

    assert tree.sample(shell, stamp=BASE_EPOCH + 7).returncode == 0

    assert not Path(f"{tree.state}.tmp").exists()
    lines = tree.state_lines()
    assert lines[0] == ["#last", str(BASE_EPOCH + 7), "0", "100.00", "0", "0", "0.00", "0"]
    assert lines[1] == [SCOPE_ID, "1234567", "100.00", "egw-controller"]


@pytest.mark.parametrize("shell", SHELLS)
def test_a_corrupt_state_line_is_ignored_rather_than_believed(tree: Tree, shell: str) -> None:
    """A state line that is not numeric re-primes the container instead of scaling a delta."""
    tree.set_container(SCOPE_ID, usage_usec=1_000_000)
    write(tree.state, f"{SCOPE_ID}\tnot-a-number\talso-not\tegw-controller\n")

    assert tree.sample(shell).returncode == 0
    assert tree.rows() == []

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=1_500_000)
    assert tree.sample(shell).returncode == 0
    assert float(tree.rows()[0]["cpu_pct"]) == pytest.approx(50.0, abs=0.01)


@pytest.mark.parametrize("shell", SHELLS)
def test_the_header_of_a_foreign_file_is_refused(tree: Tree, shell: str) -> None:
    """Appending to a file with the legacy 5-column header would mix schemas."""
    tree.set_container(SCOPE_ID)
    write(tree.out, "ts_utc,container,cpu_pct,mem_bytes,mem_pct\n")

    result = tree.sample(shell)

    assert result.returncode == 1
    assert "refusing to append" in result.stderr
    assert not Path(f"{tree.out}.lock").exists()


# --------------------------------------------------------------------------
# Source selection
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
def test_auto_selects_the_cgroup_source_when_a_container_cgroup_exists(
    tree: Tree, shell: str
) -> None:
    """``auto`` is the only source a documented run uses, so it is the one tested."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller")
    assert tree.one(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=250_000)
    result = tree.one(shell)

    assert result.returncode == 0
    assert "sampling source: cgroup v2" in result.stderr
    assert float(tree.rows()[0]["cpu_pct"]) == pytest.approx(25.0, abs=0.01)


@pytest.mark.parametrize("shell", SHELLS)
def test_auto_switches_to_cgroup_when_the_containers_appear(tree: Tree, shell: str) -> None:
    """The collector starts before the warm-up: an empty tree must not fix the source."""
    empty = tree.one(shell)
    assert empty.returncode == 0
    assert "no sampling source" in empty.stderr

    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.one(shell).returncode == 0
    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=100_000)
    later = tree.one(shell)

    assert "sampling source: cgroup v2" in later.stderr
    assert len(tree.rows()) == 1


DOCKER_STATS_LINES = (
    '{"Name":"egw-controller-1","CPUPerc":"1.50%","MemUsage":"10MiB / 768MiB","MemPerc":"1.30%"}\n'
    '{"Name":"egw-mosquitto-1","CPUPerc":"0.25%","MemUsage":"2.5MiB / 256MiB","MemPerc":"0.98%"}\n'
)


def fake_docker(tree: Tree) -> dict[str, str]:
    """A ``docker`` whose ``stats`` prints two containers and whose other commands fail."""
    bin_dir = tree.root / "bin"
    stats = tree.root / "stats.jsonl"
    write(stats, DOCKER_STATS_LINES)
    write(bin_dir / "docker", f"#!/bin/sh\n[ \"$1\" = stats ] && exec cat '{stats}'\nexit 1\n")
    (bin_dir / "docker").chmod(0o755)
    return {"PATH": f"{bin_dir}:{os.environ['PATH']}"}


@pytest.mark.parametrize("shell", HOST_SHELLS)
def test_docker_samples_follow_the_same_stamp_rules(tree: Tree, shell: str) -> None:
    """The docker source withholds a second already stamped and counts the seconds it skipped."""
    env = fake_docker(tree)

    def docker_sample(stamp: int) -> subprocess.CompletedProcess[str]:
        return tree.one(shell, "--source", "docker", stamp=stamp, env=env, no_docker=False)

    assert docker_sample(BASE_EPOCH).returncode == 0
    assert docker_sample(BASE_EPOCH).returncode == 0  # the same second again
    assert docker_sample(BASE_EPOCH - 3).returncode == 0  # a clock stepped back
    result = docker_sample(BASE_EPOCH + 4)

    assert result.returncode == 0, result.stderr
    rows = tree.rows()
    assert [row["ts_utc"] for row in rows] == [utc(BASE_EPOCH)] * 2 + [utc(BASE_EPOCH + 4)] * 2
    assert (rows[0]["container"], rows[0]["cpu_pct"], rows[0]["mem_bytes"]) == ("egw-controller-1", "1.50", str(10 * MIB))
    lines = tree.diagnostics()
    assert sum("sample withheld" in line for line in lines) == 2
    assert any("forward UTC gap: no sample stamped in the 3 second(s) before this one" in line for line in lines)
    assert "utc_gap_seconds=3 withheld_samples=2 " in [line for line in lines if " stop: " in line][-1]


@pytest.mark.parametrize("shell", HOST_SHELLS)
def test_the_inventory_counts_the_services_docker_sampled(tree: Tree, shell: str) -> None:
    """With the docker source the names are only in the CSV; they are observed all the same."""
    env = fake_docker(tree)

    result = tree.one(
        shell,
        "--source",
        "docker",
        "--expect-services",
        "egw-controller-1,egw-mosquitto-1,egw-mongodb-1",
        env=env,
        no_docker=False,
    )

    assert result.returncode == 0, result.stderr
    inventory = [line for line in tree.diagnostics() if " inventory: " in line]
    assert len(inventory) == 1
    assert "observed=egw-controller-1,egw-mosquitto-1 " in inventory[0]
    assert "missing=egw-mongodb-1 " in inventory[0]


@pytest.mark.parametrize("shell", HOST_SHELLS)
def test_the_clean_up_after_the_containers_go_stamps_no_second(tree: Tree, shell: str) -> None:
    """auto: the pass that records the disappearance runs once and cannot withhold a docker sample."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller")
    assert tree.one(shell, stamp=BASE_EPOCH).returncode == 0
    shutil.rmtree(tree.dir_for(SCOPE_ID, systemd_driver=True))

    env = fake_docker(tree)
    result = tree.one(shell, stamp=BASE_EPOCH + 1, env=env, no_docker=False)
    assert result.returncode == 0, result.stderr
    assert tree.one(shell, stamp=BASE_EPOCH + 2, env=env, no_docker=False).returncode == 0

    disappeared = [event for event in tree.lifecycle() if event[0] == "disappeared"]
    assert disappeared == [("disappeared", SCOPE_ID, "egw-controller")]
    assert [row["ts_utc"] for row in tree.rows()] == [utc(BASE_EPOCH + 1)] * 2 + [utc(BASE_EPOCH + 2)] * 2
    assert not any("sample withheld" in line for line in tree.diagnostics())


# --------------------------------------------------------------------------
# Timestamps
# --------------------------------------------------------------------------


CALENDAR_EPOCHS = [
    0,  # 1970-01-01
    68_169_599,  # 1972-02-29T23:59:59, the first leap day after the epoch
    951_782_400,  # 2000-02-29, a leap century
    978_307_199,  # 2000-12-31T23:59:59
    1_709_164_800,  # 2024-02-29
    1_789_779_027,  # 2026-09-19, this project
    1_798_761_599,  # 2026-12-31T23:59:59
    4_102_444_799,  # 2099-12-31T23:59:59
    4_107_542_400,  # 2100-03-01: 2100 is not a leap year
]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("epoch", CALENDAR_EPOCHS)
def test_utc_formatting_matches_the_calendar(tree: Tree, shell: str, epoch: int) -> None:
    """The arithmetic UTC formatting agrees with the calendar, whatever the time zone."""
    prefix, env = shell_command(shell)
    result = subprocess.run(
        [*prefix, str(SCRIPT), str(tree.out), "--self-test", "--format-epoch", str(epoch)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**env, "TZ": "Asia/Kathmandu"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == utc(epoch)
    assert not tree.out.exists(), "formatting an instant writes no output file"


@pytest.mark.parametrize("shell", SHELLS)
def test_format_epoch_needs_self_test(tree: Tree, shell: str) -> None:
    prefix, env = shell_command(shell)
    result = subprocess.run(
        [*prefix, str(SCRIPT), str(tree.out), "--format-epoch", "0"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert result.returncode == 2


# --------------------------------------------------------------------------
# Real clocks: pacing, a failure late in one run, the production limits
# --------------------------------------------------------------------------


@NEEDS_PROC
@pytest.mark.parametrize("shell", SHELLS)
def test_real_time_pacing_stamps_every_second_once(tree: Tree, shell: str) -> None:
    """One sample per wall-clock second: stamps never repeat, and every forward UTC gap is recorded.

    Two earlier versions failed exactly here on the guest: 29 samples gave 26
    distinct instants, and a 600 s run 0.84 instants per second.
    """
    tree.uptime = Path("/proc/uptime")
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller")

    result = tree.run(shell, "--source", "cgroup", "--interval", "1", "--max-samples", "8")

    assert result.returncode == 0, result.stderr
    lines = tree.diagnostics()
    assert any("pacing: wall-clock seconds" in line for line in lines), lines[:2]
    stamps = [datetime.datetime.strptime(row["ts_utc"], "%Y-%m-%dT%H:%M:%SZ") for row in tree.rows()]
    assert len(set(stamps)) == len(stamps), "two rows share a second"
    steps = [int((b - a).total_seconds()) for a, b in zip(stamps, stamps[1:])]
    assert all(step >= 1 for step in steps), steps
    stop = [line for line in lines if " stop: " in line][-1]
    recorded = int(re.search(r"utc_gap_seconds=(\d+)", stop).group(1))
    withheld = sum("sample withheld" in line for line in lines)
    assert len(stamps) + withheld == 7
    assert sum(step - 1 for step in steps) <= recorded


@NEEDS_PROC
@pytest.mark.parametrize("shell", SHELLS)
def test_an_early_and_a_late_failure_in_one_run_are_both_kept(tree: Tree, shell: str) -> None:
    """Within one continuous run, a failure after the stderr excerpt is still written down."""
    tree.uptime = Path("/proc/uptime")
    tree.set_container(SCOPE_ID, usage_usec=0)
    cpu = tree.dir_for(SCOPE_ID, systemd_driver=True) / "cpu.stat"

    def breaker() -> None:
        # Break cpu.stat around the second and again around the sixth sample,
        # each time for two seconds: under emulation and load one sample can
        # take longer than a second, and a one-second window can fall between
        # two samples.
        for delay, broken in ((1.5, True), (2.0, False), (2.0, True), (2.0, False)):
            time.sleep(delay)
            write(cpu, "user_usec 1\n" if broken else "usage_usec 500\nuser_usec 1\n")

    thread = threading.Thread(target=breaker)
    thread.start()
    result = tree.run(shell, "--source", "cgroup", "--interval", "1", "--max-samples", "9")
    thread.join()

    assert result.returncode == 0, result.stderr
    failures = [line for line in tree.diagnostics() if "unreadable cpu.stat or memory.current" in line]
    assert len(failures) >= 2, failures
    assert len({line[:20] for line in failures}) >= 2, "the two failures must carry their own seconds"


@NEEDS_PROC
@pytest.mark.parametrize("shell", LONG_RUN_SHELLS)
def test_a_run_meets_the_production_ingest_limits(tree: Tree, shell: str) -> None:
    """A 33-sample run passes validate_resources_csv with its production thresholds.

    Nothing is relaxed: MIN_RESOURCE_SAMPLES and MIN_DISTINCT_SAMPLE_INSTANTS
    (30 each, pooled and per container), the 90 % window coverage and the 5 s
    edge and interval gaps all apply, against a measured window taken from the
    run's real start and end as the harness takes it, with the priming sample
    inside it. It takes about 34 seconds.
    """
    tree.uptime = Path("/proc/uptime")
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller")
    tree.set_name(PLAIN_ID, "egw-mosquitto")

    # The harness's measured window starts just after its start hook returns
    # and ends just before its stop hook: here, the moment the collector is
    # launched and one second before it ends. The priming sample falls inside
    # the window, as it does for a condition with no warm-up.
    started = datetime.datetime.now(datetime.timezone.utc)
    result = tree.run(shell, "--source", "cgroup", "--interval", "1", "--max-samples", "33", timeout=240)
    ended = datetime.datetime.now(datetime.timezone.utc)

    assert result.returncode == 0, result.stderr
    rows = tree.rows()
    per_container: dict[str, list[str]] = {}
    for row in rows:
        per_container.setdefault(row["container"], []).append(row["ts_utc"])
    assert set(per_container) == {"egw-controller", "egw-mosquitto"}
    for container, stamps in per_container.items():
        assert len(stamps) >= 30, (container, len(stamps))
        assert len(set(stamps)) == len(stamps), f"{container}: duplicate (container, ts) rows"

    start = started
    end = ended - datetime.timedelta(seconds=1)
    problems = validate_resources_csv(
        tree.out,
        expected_host=rows[0]["host"],
        expected_window_s=(end - start).total_seconds(),
        expected_window_start_utc=start,
        expected_window_end_utc=end,
    )
    assert problems == []
