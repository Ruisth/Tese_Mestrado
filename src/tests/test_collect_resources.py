"""Cases for the cgroup v2 sampling path of deployment/scripts/collect-resources.sh.

The script under test is the repository file itself, run unmodified under every
POSIX shell available on the host. Nothing here needs Docker, a container or a
cgroup: the collector is pointed at a synthetic ``/sys/fs/cgroup`` tree and at a
synthetic ``/proc/uptime`` with its ``--self-test`` options, so the arithmetic of
one sample is exact and reproducible instead of depending on a running stack.

Those options are refused without ``--self-test`` and a self-test run marks its
own output, which is itself one of the cases below: the collector produces
evidence, so a file read from substituted inputs must never be mistakable for a
measured one.

What these cases show is that the collector reads the kernel's accounting the
way ``docker stats`` reports it, that it writes no row rather than a made-up
number when an input cannot be read, and that its rows satisfy the ingest
contract of ``egw_experiments.resources``. They say nothing about the behaviour
of a real container, about Docker or about the emulated guest.

Background: the previous sampler called ``docker stats --no-stream`` once per
second, which costs 3-5 s idle and about 21 s under load on the emulated ARM64
guest, so timed runs never reached MIN_DISTINCT_SAMPLE_INSTANTS and were
rejected (integration tests 1 and 6 of 2026-09-18).
"""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
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

SHELLS = [
    pytest.param("sh", marks=pytest.mark.skipif(shutil.which("sh") is None, reason="sh is not installed")),
    pytest.param("dash", marks=pytest.mark.skipif(shutil.which("dash") is None, reason="dash is not installed")),
    pytest.param("bash", marks=pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")),
]

# Two containers, one under each cgroup driver layout: the systemd driver's
# scope and the cgroupfs driver's directory.
SCOPE_ID = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
PLAIN_ID = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c4b5a69788796a5b4c3d2e1f0"

MIB = 1024 * 1024


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


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
        usage_usec: int = 1_000_000,
        memory_current: int = 200 * MIB,
        inactive_file: int | None = 50 * MIB,
        memory_max: int | str = 768 * MIB,
    ) -> Path:
        d = self.dir_for(container_id, systemd_driver=systemd_driver)
        write(d / "cpu.stat", f"usage_usec {usage_usec}\nuser_usec 1\nsystem_usec 2\n")
        write(d / "memory.current", f"{memory_current}\n")
        if inactive_file is None:
            (d / "memory.stat").unlink(missing_ok=True)
        else:
            write(d / "memory.stat", f"anon 1\nfile 2\ninactive_file {inactive_file}\nslab 3\n")
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

    def argv(self, shell: str, *args: str, self_test: bool = True) -> list[str]:
        cmd = [shell, str(SCRIPT), str(self.out)]
        if self_test:
            cmd += ["--self-test"]
        cmd += [
            "--no-docker",
            "--cgroup-root",
            str(self.cgroup_root),
            "--docker-root",
            str(self.docker_root),
            "--uptime-from",
            str(self.uptime),
            "--meminfo-from",
            str(self.meminfo),
            "--state-file",
            str(self.state),
            *args,
        ]
        return cmd

    def run(self, shell: str, *args: str, timeout: int = 60, **kw) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self.argv(shell, *args, **kw), capture_output=True, text=True, timeout=timeout, check=False
        )

    def sample(self, shell: str, *args: str) -> subprocess.CompletedProcess[str]:
        return self.run(shell, "--source", "cgroup", "--max-samples", "1", *args)

    def rows(self) -> list[dict[str, str]]:
        with self.out.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))


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

    Half a second of CPU over one second of wall clock is 50 % on docker's
    single-CPU basis; the reported memory is ``memory.current`` minus
    ``inactive_file``, as a percentage of ``memory.max``.
    """
    tree.set_container(SCOPE_ID, usage_usec=1_000_000, memory_current=200 * MIB)
    tree.set_name(SCOPE_ID, "egw-controller")
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(
        SCOPE_ID,
        usage_usec=1_500_000,
        memory_current=300 * MIB,
        inactive_file=100 * MIB,
        memory_max=400 * MIB,
    )
    result = tree.sample(shell)

    assert result.returncode == 0, result.stderr
    rows = tree.rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["container"] == "egw-controller"
    assert float(row["cpu_pct"]) == pytest.approx(50.0, abs=0.01)
    assert int(row["mem_bytes"]) == 200 * MIB
    assert float(row["mem_pct"]) == pytest.approx(50.0, abs=0.01)
    assert row["host"]
    assert row["ts_utc"].endswith("Z")


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


# --------------------------------------------------------------------------
# A failed sample is a hole, never a number
# --------------------------------------------------------------------------


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
    assert "MemTotal" in result.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unreadable_sample_costs_one_row_and_not_two(tree: Tree, shell: str) -> None:
    """The previous reading is kept, so the next delta simply spans two intervals."""
    tree.set_container(SCOPE_ID, usage_usec=1_000_000)
    assert tree.sample(shell).returncode == 0

    # Second sample: cpu.stat unreadable.
    tree.set_uptime(101.0)
    write(tree.dir_for(SCOPE_ID, systemd_driver=True) / "cpu.stat", "user_usec 1\n")
    assert tree.sample(shell).returncode == 0
    assert tree.rows() == []

    # Third sample: readable again, one second later. The delta spans the two
    # seconds since the last good reading: 1.0 s of CPU over 2.0 s is 50 %.
    tree.set_uptime(102.0)
    tree.set_container(SCOPE_ID, usage_usec=2_000_000)

    assert tree.sample(shell).returncode == 0
    rows = tree.rows()
    assert len(rows) == 1
    assert float(rows[0]["cpu_pct"]) == pytest.approx(50.0, abs=0.01)


@pytest.mark.parametrize("shell", SHELLS)
def test_a_counter_that_goes_backwards_is_not_reported(tree: Tree, shell: str) -> None:
    """A recreated cgroup restarts its counter; a negative delta is not a sample."""
    tree.set_container(SCOPE_ID, usage_usec=5_000_000)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=1_000)

    assert tree.sample(shell).returncode == 0
    assert tree.rows() == []


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


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
def test_the_name_falls_back_to_the_short_id(tree: Tree, shell: str) -> None:
    """No config.v2.json and no docker: the row still carries a non-empty name.

    An empty container column would be rejected at ingestion, so losing the
    name must not lose the sample.
    """
    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.sample(shell).returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=10_000)

    assert tree.sample(shell).returncode == 0
    assert tree.rows()[0]["container"] == SCOPE_ID[:12]


@pytest.mark.parametrize("shell", SHELLS)
def test_a_name_that_becomes_readable_later_is_picked_up(tree: Tree, shell: str) -> None:
    """The short id is provisional: it must never be cached as the name.

    A container recreated mid-run, or a collector that only later can read the
    Docker data root, would otherwise carry two series for one container — the
    name before and the id after — and fail the per-container coverage rule for
    the wrong reason.
    """
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


# --------------------------------------------------------------------------
# Evidence integrity
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
def test_substituted_inputs_are_refused_without_self_test(tree: Tree, shell: str) -> None:
    """A measurement never reads its inputs from a path given on the command line."""
    tree.set_container(SCOPE_ID)

    result = tree.run(shell, "--source", "cgroup", "--max-samples", "1", self_test=False)

    assert result.returncode == 2
    assert "self-test" in result.stderr
    assert not tree.out.exists()


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


@pytest.mark.parametrize("shell", SHELLS)
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
        first.wait(timeout=30)

    # The lock is released when the first collector ends.
    assert not Path(f"{tree.out}.lock").exists()
    assert tree.sample(shell).returncode == 0


@pytest.mark.parametrize("shell", SHELLS)
def test_the_state_file_is_replaced_whole(tree: Tree, shell: str) -> None:
    """The state is written to a temporary file and moved, never truncated in place."""
    tree.set_container(SCOPE_ID, usage_usec=1_234_567)
    tree.set_name(SCOPE_ID, "egw-controller")

    assert tree.sample(shell).returncode == 0

    assert not Path(f"{tree.state}.tmp").exists()
    fields = tree.state.read_text(encoding="utf-8").rstrip("\n").split("\t")
    assert fields[0] == SCOPE_ID
    assert fields[1] == "1234567"
    assert float(fields[2]) == pytest.approx(100.0)
    assert fields[3] == "egw-controller"


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
# Source selection and cadence
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shell", SHELLS)
def test_auto_selects_the_cgroup_source_when_a_container_cgroup_exists(
    tree: Tree, shell: str
) -> None:
    """``auto`` is the only source a documented run uses, so it is the one tested."""
    tree.set_container(SCOPE_ID, usage_usec=0)
    tree.set_name(SCOPE_ID, "egw-controller")
    assert tree.run(shell, "--max-samples", "1").returncode == 0

    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=250_000)
    result = tree.run(shell, "--max-samples", "1")

    assert result.returncode == 0
    assert "sampling source: cgroup v2" in result.stderr
    assert float(tree.rows()[0]["cpu_pct"]) == pytest.approx(25.0, abs=0.01)


@pytest.mark.parametrize("shell", SHELLS)
def test_auto_switches_to_cgroup_when_the_containers_appear(tree: Tree, shell: str) -> None:
    """The collector starts before the warm-up: an empty tree must not fix the source.

    With ``--no-docker`` and no container cgroup there is no source at all; the
    run says so and then switches as soon as a cgroup appears.
    """
    empty = tree.run(shell, "--max-samples", "1")
    assert empty.returncode == 0
    assert "no sampling source" in empty.stderr

    tree.set_container(SCOPE_ID, usage_usec=0)
    assert tree.run(shell, "--max-samples", "1").returncode == 0
    tree.set_uptime(101.0)
    tree.set_container(SCOPE_ID, usage_usec=100_000)
    later = tree.run(shell, "--max-samples", "1")

    assert "sampling source: cgroup v2" in later.stderr
    assert len(tree.rows()) == 1


@pytest.mark.skipif(not Path("/proc/uptime").exists(), reason="no /proc/uptime on this host")
@pytest.mark.parametrize("shell", SHELLS)
def test_the_cadence_holds_and_the_output_is_ingestible(tree: Tree, shell: str) -> None:
    """Five samples of two containers at 1 Hz, and the result passes ingestion.

    This is the defect these changes exist for: the period must be the interval,
    not the interval plus the cost of the sample, and consecutive samples of one
    container more than MAX_SAMPLE_GAP_S apart invalidate a run whatever the
    instant count. The real ``/proc/uptime`` is used, because a frozen wall clock
    would make every interval zero-length; the counters stay still, so the
    percentages are zero, which is a valid reading of an idle container.

    Only the two threshold arguments of the validator are relaxed — reaching
    MIN_DISTINCT_SAMPLE_INSTANTS would mean sleeping for 30 s in a unit test —
    so the header, the column completeness, the numeric rules, the timestamp
    ordering, the per-container gaps and the host column are checked as at
    ingestion. The expected host here comes from the file itself, so it shows
    only that the column is consistent; at ingestion it is compared with
    ``sut_environment.json``, which is an independent source.
    """
    tree.uptime = Path("/proc/uptime")
    tree.set_name(SCOPE_ID, "egw-controller")
    tree.set_name(PLAIN_ID, "egw-mosquitto")

    # A build machine that stalls for a second would fail a strict bound on a
    # collector that is in fact paced correctly, so the measurement is allowed
    # one retry; a sampler that really costs more than its interval fails both.
    attempts = []
    for attempt in range(2):
        tree.out = tree.root / f"resources-{attempt}.csv"
        tree.state = tree.root / f"collector-{attempt}.state"
        tree.set_container(SCOPE_ID, usage_usec=0)
        tree.set_container(PLAIN_ID, systemd_driver=False, usage_usec=0)

        started = time.monotonic()
        result = tree.run(shell, "--interval", "1", "--max-samples", "5")
        elapsed = time.monotonic() - started
        assert result.returncode == 0, result.stderr

        rows = tree.rows()
        # Four intervals produce a row per container each, and the instants of
        # a 1 Hz collector are distinct.
        assert len(rows) == 8
        instants = sorted({row["ts_utc"] for row in rows})
        assert len(instants) == 4
        seconds = time.mktime(time.strptime(instants[-1], "%Y-%m-%dT%H:%M:%SZ")) - time.mktime(
            time.strptime(instants[0], "%Y-%m-%dT%H:%M:%SZ")
        )
        # A correctly paced collector spans exactly 3 s here and a sampler
        # with the defect this change removes (about 4 s per sample) spans
        # about 16 s, so the tolerance below separates them with room to
        # spare on a busy build machine, without reaching MAX_SAMPLE_GAP_S
        # per consecutive pair, which the validator checks at the end.
        attempts.append((elapsed, seconds))
        if elapsed < 10 and 3 <= seconds <= 6:
            break
    else:
        pytest.fail(
            "five samples at 1 Hz were not paced in either attempt "
            f"(elapsed, instant span) = {attempts}"
        )

    problems = validate_resources_csv(
        tree.out,
        expected_host=rows[0]["host"],
        min_samples=8,
        min_distinct_instants=4,
    )
    assert problems == []
