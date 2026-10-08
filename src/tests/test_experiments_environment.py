"""Tests for egw_experiments.environment: the three environment records of a
run and the G4 core provenance checks (plan 655-661).

Most cases read a fake ``/proc`` tree under ``tmp_path``, built by
:class:`FakeProc` with only the files the capture reads: command lines held
as NUL-separated bytes, a ``stat`` line whose process name holds spaces and
``)``, ``exe`` and ``fd`` links, the boot id, ``btime``, ``MemTotal`` and the
CPU model. The QEMU command line is modelled on the one runqemu printed in
session S10 (``boot/s1.log:35``): ``-machine virt -cpu cortex-a76 -smp 4
-m 8192``, the rootfs drive named after the image and the broker forward
``hostfwd=tcp:127.0.0.1:8883-:8883``. The guest record is modelled on the
sealed one of test 6 (``sut_environment.json``, captured on the guest).

The checks are pure: each case builds the three records once, alters one
fact and reads which check names it. The last cases read the real ``/proc``
of a Linux host: a Python interpreter reached through a symbolic link named
``qemu-system-aarch64`` stands in for the guest, beside a shell that merely
mentions the name (as ``tests/test_qemu_process_guard.py`` does with
``sleep``).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import re
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from egw_experiments import environment as env_mod

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_DOC = REPO_ROOT / "docs" / "governance" / "INTEGRATED_DEVELOPMENT_PLAN_2026.md"

BOOT_ID = "6f1b8d0e-2c55-4c43-9a0e-3f4a5b6c7d8e"
#: 2026-10-07T11:00:00Z: the boot of the fake host.
BTIME = 1791370800
CLK_TCK = 100
#: The QEMU process started 1234.56 s after the boot: 11:20:34.560Z.
QEMU_STARTTIME = 123456
QEMU_START_UTC = "2026-10-07T11:20:34.560Z"
QEMU_PID = 4242
QEMU_VERSION = "QEMU emulator version 8.2.7"
ROOTFS_NAME = "egw-gateway-image-qemuarm64.rootfs-20260918120819"
BROKER = "127.0.0.1"
PORT = 8883
TCG_CHECKS = ["P0", "H1", "H2", "H3", "H4", "H5", "G1", "G2", "G3", "G4", "G5", "L1", "I1"]
NATIVE_CHECKS = ["P0", "N0", "N1", "N2", "N3"]


# ---------------------------------------------------------------------------
# The fake /proc tree
# ---------------------------------------------------------------------------


def _symlink(target: str | Path, link: Path) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - Windows without the privilege
        pytest.skip(f"symbolic links cannot be created here: {exc}")


class FakeProc:
    """A /proc tree under ``root``: the files the capture reads, nothing else."""

    def __init__(self, root: Path, *, boot_id: str = BOOT_ID, btime: int = BTIME) -> None:
        self.root = root
        random_dir = root / "sys" / "kernel" / "random"
        random_dir.mkdir(parents=True)
        (random_dir / "boot_id").write_text(boot_id + "\n", encoding="utf-8")
        (root / "stat").write_text(
            "cpu  10 0 10 1000 0 0 0 0 0 0\nintr 0\nctxt 0\n"
            f"btime {btime}\nprocesses 99\n",
            encoding="utf-8",
        )
        (root / "meminfo").write_text(
            "MemTotal:       16323456 kB\nMemFree:         1048576 kB\n", encoding="utf-8"
        )
        (root / "cpuinfo").write_text(
            "processor\t: 0\nvendor_id\t: GenuineIntel\n"
            "model name\t: Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz\n\n"
            "processor\t: 1\nmodel name\t: Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz\n",
            encoding="utf-8",
        )
        # Entries that are not processes are never read as one.
        (root / "self").mkdir()
        (root / "sys" / "fs").mkdir()

    def add(
        self,
        pid: int,
        argv: list[str],
        *,
        comm: str | None = None,
        starttime: int = 1000,
        exe: Path | None = None,
        fds: tuple[str, ...] = ("/dev/null", "pipe:[1234]", "socket:[5678]"),
        cmdline: bytes | None = None,
    ) -> Path:
        directory = self.root / str(pid)
        (directory / "fd").mkdir(parents=True)
        raw = cmdline if cmdline is not None else b"".join(a.encode() + b"\0" for a in argv)
        (directory / "cmdline").write_bytes(raw)
        if comm is None:
            comm = Path(argv[0]).name[:15] if argv else "kworker/0:1"
        # Fields 3 to 52 after the name; field 22 is the start time.
        rest = ["S"] + ["0"] * 18 + [str(starttime)] + ["0"] * 30
        (directory / "stat").write_text(f"{pid} ({comm}) " + " ".join(rest) + "\n", encoding="utf-8")
        if exe is not None:
            _symlink(exe, directory / "exe")
        for number, target in enumerate(fds):
            _symlink(target, directory / "fd" / str(number))
        return directory


def qemu_argv(images: Path, *, smp: str = "4", hostfwd: str | None = None, extra: tuple[str, ...] = ()) -> list[str]:
    """The S10 command line (boot/s1.log:35) over the fake image files."""
    if hostfwd is None:
        hostfwd = f"hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:127.0.0.1:{PORT}-:8883"
    return [
        "/opt/qemu/usr/bin/qemu-system-aarch64",
        "-device", "virtio-net-pci,netdev=net0,mac=52:54:00:12:35:02",
        "-netdev", f"user,id=net0,{hostfwd}",
        "-object", "rng-random,filename=/dev/urandom,id=rng0",
        "-device", "virtio-rng-pci,rng=rng0",
        "-drive", f"id=disk0,file={images / (ROOTFS_NAME + '.ext4')},if=none,format=raw",
        "-device", "virtio-blk-pci,drive=disk0",
        "-machine", "virt", "-cpu", "cortex-a76", "-smp", smp, "-m", "8192",
        "-drive", f"id=disk1,file={images / 'egw-data.img'},if=none,format=raw",
        "-device", "virtio-blk-pci,drive=disk1",
        "-serial", "mon:stdio", "-serial", "null", "-nographic",
        "-device", "virtio-gpu-pci",
        "-kernel", str(images / "Image"),
        "-append", "root=/dev/vda rw  mem=8192M ip=dhcp console=ttyAMA0 console=hvc0 swiotlb=0 ",
        *extra,
    ]


def _uname(machine: str = "x86_64", release: str = "6.6.87.2-microsoft-standard-WSL2") -> Any:
    return platform.uname_result("Linux", "Ruisth-Desktop", release, "#1 SMP PREEMPT_DYNAMIC", machine)


@pytest.fixture
def host(tmp_path, monkeypatch):
    """The fake host: /proc, the image files, uname, the clock tick and QEMU's --version."""
    fake = FakeProc(tmp_path / "proc")
    images = tmp_path / "images"
    images.mkdir()
    (images / "Image").write_bytes(b"arm64 kernel image\n")
    (images / (ROOTFS_NAME + ".ext4")).write_bytes(b"ext4\n")
    (images / "egw-data.img").write_bytes(b"data\n")
    (images / "qemu-system-aarch64").write_bytes(b"qemu binary\n")
    monkeypatch.setattr(env_mod.platform, "uname", lambda: _uname())
    monkeypatch.setattr(env_mod, "_clock_ticks_per_second", lambda: CLK_TCK)
    monkeypatch.setattr(env_mod, "_qemu_version_line", lambda exe_path: (QEMU_VERSION, None))
    # No docker CLI is consulted by these cases.
    monkeypatch.setattr(env_mod, "_run_capture", lambda *a, **k: None)
    fake.images = images  # type: ignore[attr-defined]
    return fake


def add_qemu(host: FakeProc, pid: int = QEMU_PID, **kwargs: Any) -> Path:
    argv = kwargs.pop("argv", None) or qemu_argv(host.images)  # type: ignore[attr-defined]
    kwargs.setdefault("starttime", QEMU_STARTTIME)
    kwargs.setdefault("exe", host.images / "qemu-system-aarch64")  # type: ignore[attr-defined]
    return host.add(pid, argv, **kwargs)


def add_bystanders(host: FakeProc) -> None:
    """Processes that are not QEMU: a shell mentioning it, a kernel thread, the harness."""
    host.add(100, ["bash", "-c", "echo qemu-system-aarch64 -machine virt; sleep 60; echo done"])
    host.add(2, [], cmdline=b"", comm="kthreadd")
    host.add(101, ["/usr/bin/python3", "-m", "egw_experiments", "run"])
    host.add(102, ["/usr/bin/qemu-system-aarch64-wrapper", "-machine", "virt"])
    host.add(103, ["/usr/bin/qemu-system-x86_64", "-machine", "q35"])


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_execution_modes_are_the_documented_tokens() -> None:
    assert env_mod.EXECUTION_MODES == ("tcg-emulated", "native-kvm", "native-metal")
    assert set(env_mod.EXECUTION_MODE_LABELS) == set(env_mod.EXECUTION_MODES)
    assert env_mod.HYPERVISOR_ENVIRONMENT_FILENAME == "hypervisor_environment.json"
    assert env_mod.PROVENANCE_RULE == "G4 core provenance (plan 655-661)"


def test_the_emulated_label_is_the_plans_wording_verbatim() -> None:
    label = env_mod.EXECUTION_MODE_LABELS["tcg-emulated"]
    assert label == "ARM64 emulated by QEMU/TCG on an x86-64 host"
    plan = " ".join(PLAN_DOC.read_text(encoding="utf-8").split())
    assert f"the emulation label: {label}; never native ARM64, never KVM." in plan


# ---------------------------------------------------------------------------
# Redaction and the load-generator record
# ---------------------------------------------------------------------------


def test_redact_argv_replaces_the_password_value_only() -> None:
    argv = ["python", "-m", "egw_simulator", "run", "--username", "sim", "--password", "s3cret", "--qos", "1"]
    assert env_mod.redact_argv(argv) == [
        "python", "-m", "egw_simulator", "run", "--username", "sim", "--password", "<redacted>", "--qos", "1",
    ]
    assert argv[7] == "s3cret", "the caller's list is not changed"
    assert env_mod.redact_argv(["x", "--password=s3cret"]) == ["x", "--password=<redacted>"]
    assert env_mod.redact_argv(["x", "--password"]) == ["x", "--password"]
    assert env_mod.redact_argv(["x", "--token", "t"], secret_flags=("--token",)) == ["x", "--token", "<redacted>"]
    assert env_mod.redact_argv([]) == []


def test_capture_environment_keeps_its_keys_and_adds_the_host_and_the_argv(host) -> None:
    sim = ["/venv/bin/python", "-m", "egw_simulator", "run", "--password", "s3cret", "--port", "8883"]
    env = env_mod.capture_environment(simulator_argv=sim, proc_root=host.root)
    for key in (
        "role", "captured_utc", "platform", "system", "node", "kernel_release", "kernel_version", "machine",
        "processor", "python_version", "python_implementation", "cpu_count", "docker_client_version",
        "docker_server_version",
    ):
        assert key in env, key
    assert env["role"] == "loadgen"
    assert env["machine"] == "x86_64"
    assert env["boot_id"] == BOOT_ID
    assert env["mem_total_kb"] == 16323456
    assert env["cpu_model"] == "Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz"
    assert env["python_executable"] == sys.executable
    assert env["cpu_affinity_count"] is None or env["cpu_affinity_count"] >= 1
    assert env["simulator_argv"] == ["/venv/bin/python", "-m", "egw_simulator", "run", "--password", "<redacted>",
                                     "--port", "8883"]
    assert env["warmup_argv"] is None
    assert "s3cret" not in json.dumps(env)


def test_write_loadgen_environment_keeps_its_old_signature(host, tmp_path) -> None:
    path = env_mod.write_loadgen_environment(tmp_path / "run" / "loadgen_environment.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["role"] == "loadgen"
    assert doc["simulator_argv"] is None and doc["warmup_argv"] is None


def test_write_loadgen_environment_records_both_argv_redacted(host, tmp_path) -> None:
    path = env_mod.write_loadgen_environment(
        tmp_path / "loadgen_environment.json",
        simulator_argv=["py", "--password", "a"],
        warmup_argv=["py", "--password", "b", "--duration", "30"],
        proc_root=host.root,
    )
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    doc = json.loads(raw.decode("utf-8"))
    assert doc["simulator_argv"] == ["py", "--password", "<redacted>"]
    assert doc["warmup_argv"] == ["py", "--password", "<redacted>", "--duration", "30"]
    assert doc["boot_id"] == BOOT_ID


def test_capture_environment_degrades_to_null_without_proc(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(env_mod, "_run_capture", lambda *a, **k: None)
    env = env_mod.capture_environment(proc_root=tmp_path / "absent")
    assert env["boot_id"] is None and env["mem_total_kb"] is None and env["cpu_model"] is None


# ---------------------------------------------------------------------------
# Reading the records back
# ---------------------------------------------------------------------------


def test_read_environment_record(tmp_path) -> None:
    assert env_mod.read_environment_record(tmp_path, "loadgen_environment.json") is None
    (tmp_path / "loadgen_environment.json").write_text("[1, 2]\n", encoding="utf-8")
    assert env_mod.read_environment_record(tmp_path, "loadgen_environment.json") is None
    (tmp_path / "loadgen_environment.json").write_text("{not json", encoding="utf-8")
    assert env_mod.read_environment_record(tmp_path, "loadgen_environment.json") is None
    (tmp_path / "loadgen_environment.json").write_text('{"role": "loadgen"}\n', encoding="utf-8")
    assert env_mod.read_environment_record(tmp_path, "loadgen_environment.json") == {"role": "loadgen"}
    (tmp_path / "sut_environment.json").write_text('{"role": "sut", "nproc": 4}\n', encoding="utf-8")
    assert env_mod.read_sut_environment(tmp_path) == {"role": "sut", "nproc": 4}
    assert env_mod.read_environment_record(tmp_path, env_mod.SUT_ENVIRONMENT_FILENAME) == {"role": "sut", "nproc": 4}


# ---------------------------------------------------------------------------
# Discovery and the command line
# ---------------------------------------------------------------------------


def test_discovery_finds_no_qemu_among_bystanders(host) -> None:
    add_bystanders(host)
    assert env_mod.find_qemu_processes(host.root) == ([], None)


def test_discovery_finds_the_one_qemu_and_not_the_shell_mentioning_it(host) -> None:
    add_bystanders(host)
    add_qemu(host)
    assert env_mod.find_qemu_processes(host.root) == ([QEMU_PID], None)


def test_discovery_matches_a_bare_executable_name(host) -> None:
    host.add(77, ["qemu-system-aarch64", "-machine", "virt"])
    assert env_mod.find_qemu_processes(host.root) == ([77], None)


def test_discovery_lists_two_qemu_processes_in_pid_order(host) -> None:
    add_bystanders(host)
    add_qemu(host, pid=5000)
    add_qemu(host, pid=4000)
    assert env_mod.find_qemu_processes(host.root) == ([4000, 5000], None)


def test_discovery_that_cannot_list_proc_says_so(tmp_path) -> None:
    pids, error = env_mod.find_qemu_processes(tmp_path / "absent")
    assert pids == []
    assert error and "cannot list" in error


def test_read_argv_splits_on_nul_and_hashes_the_raw_bytes(host) -> None:
    argv = ["/opt/qemu-system-aarch64", "-append", "root=/dev/vda rw  console=ttyAMA0 ", ""]
    raw = b"".join(a.encode() + b"\0" for a in argv)
    host.add(55, argv, cmdline=raw)
    got, digest = env_mod.read_argv(55, host.root)
    assert got == argv
    assert digest == _sha(raw)


def test_parse_qemu_argv_reads_the_s10_command_line() -> None:
    line = (
        "/x/qemu-system-aarch64 -device virtio-net-pci,netdev=net0,mac=52:54:00:12:35:02 -netdev "
        "user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:127.0.0.1:8883-:8883 -object "
        "rng-random,filename=/dev/urandom,id=rng0 -device virtio-rng-pci,rng=rng0 -drive "
        "id=disk0,file=/d/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4,if=none,format=raw -device "
        "virtio-blk-pci,drive=disk0   -machine virt -cpu cortex-a76 -smp 4 -m 8192  -drive "
        "id=disk1,file=/home/ruisth/yocto/egw-integrated/egw-data.img,if=none,format=raw -device "
        "virtio-blk-pci,drive=disk1 -serial mon:stdio -serial null -nographic -device virtio-gpu-pci -kernel "
        "/d/Image -append 'root=/dev/vda rw  mem=8192M ip=dhcp console=ttyAMA0 console=hvc0 swiotlb=0 '"
    )
    parsed = env_mod.parse_qemu_argv(shlex.split(line))
    assert parsed["machine"] == "virt"
    assert parsed["cpu"] == "cortex-a76"
    assert parsed["smp"] == 4
    assert parsed["memory"] == "8192"
    assert parsed["kernel"] == "/d/Image"
    assert parsed["append"] == "root=/dev/vda rw  mem=8192M ip=dhcp console=ttyAMA0 console=hvc0 swiotlb=0 "
    assert parsed["drives"] == [
        "/d/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4",
        "/home/ruisth/yocto/egw-integrated/egw-data.img",
    ]
    assert [r["rule"] for r in parsed["hostfwd"]] == ["tcp:127.0.0.1:2222-:22", "tcp:127.0.0.1:8883-:8883"]
    assert parsed["hostfwd"][1] == {
        "rule": "tcp:127.0.0.1:8883-:8883", "protocol": "tcp", "host_addr": "127.0.0.1", "host_port": 8883,
        "guest_addr": "", "guest_port": 8883,
    }
    assert parsed["kvm_requested"] is False
    assert parsed["accel_requests"] == []


@pytest.mark.parametrize(
    ("extra", "requests", "kvm"),
    [
        (["-enable-kvm"], ["kvm"], True),
        (["--enable-kvm"], ["kvm"], True),
        (["-machine", "virt,accel=kvm"], ["kvm"], True),
        (["-M", "type=virt,accel=kvm:tcg"], ["kvm", "tcg"], True),
        (["-accel", "kvm"], ["kvm"], True),
        (["-accel", "tcg,thread=multi"], ["tcg"], False),
        (["--accel", "accel=tcg"], ["tcg"], False),
    ],
)
def test_parse_qemu_argv_reads_accelerator_requests(extra, requests, kvm) -> None:
    parsed = env_mod.parse_qemu_argv(["qemu-system-aarch64", "-machine", "virt", *extra])
    assert parsed["accel_requests"] == requests
    assert parsed["kvm_requested"] is kvm
    assert parsed["machine"] == "virt"


def test_parse_qemu_argv_reads_option_forms() -> None:
    parsed = env_mod.parse_qemu_argv([
        "qemu-system-aarch64", "--smp", "cpus=2,sockets=1", "-drive", "file=/a,,b.img,if=virtio",
        "-nic", "user,hostfwd=tcp::8883-:8883", "-netdev", "user,id=n1,hostfwd=udp:10.0.0.1:53-:53",
    ])
    assert parsed["smp"] == 2
    assert parsed["drives"] == ["/a,b.img"]
    assert parsed["hostfwd"][0]["host_addr"] == "" and parsed["hostfwd"][0]["host_port"] == 8883
    assert parsed["hostfwd"][1]["protocol"] == "udp"
    assert parsed["machine"] is None and parsed["kernel"] is None
    assert env_mod.parse_qemu_argv(["qemu-system-aarch64", "-smp", "many"])["smp"] is None


# ---------------------------------------------------------------------------
# The host record and the hypervisor snapshot
# ---------------------------------------------------------------------------


def test_capture_host_record_reads_proc_and_uname(host) -> None:
    problems: list[str] = []
    record = env_mod.capture_host_record(host.root, problems)
    assert set(record) == {
        "node", "kernel_release", "machine", "boot_id", "cpu_count", "cpu_affinity_count", "mem_total_kb",
        "cpu_model", "wsl",
    }
    assert record["node"] == "Ruisth-Desktop"
    assert record["machine"] == "x86_64"
    assert record["boot_id"] == BOOT_ID
    assert record["mem_total_kb"] == 16323456
    assert record["cpu_model"] == "Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz"
    assert record["wsl"] is True
    assert record["cpu_count"] == os.cpu_count()


def test_capture_host_record_names_what_it_could_not_read(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(env_mod.platform, "uname", lambda: _uname(release="6.8.0-45-generic"))
    problems: list[str] = []
    record = env_mod.capture_host_record(tmp_path / "absent", problems)
    assert record["boot_id"] is None and record["mem_total_kb"] is None and record["cpu_model"] is None
    assert record["wsl"] is False
    assert any(p.startswith("host.boot_id:") for p in problems)
    assert any(p.startswith("host.mem_total_kb:") for p in problems)
    assert any(p.startswith("host.cpu_model:") for p in problems)


def _snapshot(host: FakeProc, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("loadgen_env", {"role": "loadgen", "boot_id": BOOT_ID, "machine": "x86_64"})
    kwargs.setdefault("broker", BROKER)
    kwargs.setdefault("port", PORT)
    return env_mod.capture_hypervisor_snapshot(proc_root=host.root, **kwargs)


def test_snapshot_of_the_one_tcg_guest(host) -> None:
    add_bystanders(host)
    add_qemu(host, comm="qemu) (x y")
    snap = _snapshot(host)
    assert set(snap) == {
        "captured_utc", "captured_monotonic_ns", "host", "qemu", "colocated_with_loadgen",
        "generator_target_is_this_guest", "problems",
    }
    q = snap["qemu"]
    images = host.images  # type: ignore[attr-defined]
    assert q["found"] == 1 and q["pids"] == [QEMU_PID] and q["error"] is None
    assert q["pid"] == QEMU_PID
    assert q["starttime_ticks"] == QEMU_STARTTIME
    assert q["start_utc"] == QEMU_START_UTC
    # The basis of start_utc is recorded: the host's btime read at THIS
    # snapshot and the clock tick rate (G5 compares the guest's clock with it).
    assert q["btime"] == BTIME and q["clock_ticks_per_second"] == CLK_TCK
    assert q["exe_path"] == str(images / "qemu-system-aarch64")
    assert q["exe_sha256"] == _sha(b"qemu binary\n")
    assert q["version_line"] == QEMU_VERSION
    argv = qemu_argv(images)
    assert q["argv"] == argv
    assert q["argv_sha256"] == _sha(b"".join(a.encode() + b"\0" for a in argv))
    assert q["parsed"]["smp"] == 4 and q["parsed"]["machine"] == "virt"
    assert q["kernel_sha256"] == _sha(b"arm64 kernel image\n")
    # The kernel hash describes the file on disk when the snapshot is taken,
    # not proven to be the bytes QEMU loaded at its start.
    assert q["kernel_hash_basis"] == "file on disk at capture"
    assert q["rootfs_path"] == str(images / (ROOTFS_NAME + ".ext4"))
    assert q["rootfs_image_name"] == ROOTFS_NAME
    assert q["kvm_device_open"] is False
    assert q["accelerator"] == "tcg"
    assert any("not requested" in b for b in q["accelerator_basis"])
    assert any("/dev/kvm" in b for b in q["accelerator_basis"])
    assert q["target_arch"] == "aarch64"
    assert snap["host"]["boot_id"] == BOOT_ID
    assert snap["colocated_with_loadgen"] is True
    assert snap["generator_target_is_this_guest"] is True
    assert snap["problems"] == []
    json.dumps(snap)  # JSON-safe


@pytest.mark.parametrize("pids", [[], [4000, 5000]])
def test_snapshot_without_exactly_one_qemu_chooses_none(host, pids) -> None:
    add_bystanders(host)
    for pid in pids:
        add_qemu(host, pid=pid)
    snap = _snapshot(host)
    q = snap["qemu"]
    assert q["found"] == len(pids) and q["pids"] == pids
    assert q["error"]
    for key in ("pid", "starttime_ticks", "start_utc", "btime", "clock_ticks_per_second", "exe_path",
                "exe_sha256", "version_line", "argv", "argv_sha256", "parsed", "kernel_sha256",
                "kernel_hash_basis", "rootfs_path", "rootfs_image_name", "accelerator"):
        assert q[key] is None, key
    assert snap["colocated_with_loadgen"] is None
    assert snap["generator_target_is_this_guest"] is None
    assert any(p.startswith("qemu:") for p in snap["problems"])


def test_snapshot_reads_kvm_when_requested_and_dev_kvm_is_open(host) -> None:
    add_qemu(host, argv=qemu_argv(host.images, extra=("-enable-kvm",)),  # type: ignore[attr-defined]
             fds=("/dev/null", "/dev/kvm", "anon_inode:kvm-vm"))
    q = _snapshot(host)["qemu"]
    assert q["parsed"]["kvm_requested"] is True
    assert q["kvm_device_open"] is True
    assert q["accelerator"] == "kvm"


def test_snapshot_does_not_guess_when_kvm_is_requested_but_not_seen(host) -> None:
    add_qemu(host, argv=qemu_argv(host.images, extra=("-machine", "virt,accel=kvm")))  # type: ignore[attr-defined]
    snap = _snapshot(host)
    assert snap["qemu"]["parsed"]["kvm_requested"] is True
    assert snap["qemu"]["accelerator"] is None
    assert any(p.startswith("qemu.accelerator:") for p in snap["problems"])


def test_snapshot_with_unreadable_fds_rests_on_the_cross_architecture(host, monkeypatch) -> None:
    directory = add_qemu(host)
    for link in (directory / "fd").iterdir():
        link.unlink()
    (directory / "fd").rmdir()
    snap = _snapshot(host)
    assert snap["qemu"]["kvm_device_open"] is None
    assert snap["qemu"]["accelerator"] == "tcg"
    assert any("cross-architecture" in b for b in snap["qemu"]["accelerator_basis"])
    assert any(p.startswith("qemu.kvm_device_open:") for p in snap["problems"])
    # On an aarch64 host the same facts do not determine the accelerator.
    monkeypatch.setattr(env_mod.platform, "uname", lambda: _uname(machine="aarch64"))
    snap = _snapshot(host)
    assert snap["qemu"]["accelerator"] is None
    assert any(p.startswith("qemu.accelerator:") for p in snap["problems"])


def test_snapshot_records_co_location_from_the_boot_ids(host) -> None:
    add_qemu(host)
    other = {"role": "loadgen", "boot_id": "00000000-0000-0000-0000-000000000000"}
    assert _snapshot(host, loadgen_env=other)["colocated_with_loadgen"] is False
    snap = _snapshot(host, loadgen_env=None)
    assert snap["colocated_with_loadgen"] is None
    assert any(p.startswith("colocated_with_loadgen:") for p in snap["problems"])


@pytest.mark.parametrize(
    ("broker", "port", "hostfwd", "expected"),
    [
        ("127.0.0.1", PORT, None, True),
        ("127.0.0.1", PORT, f"hostfwd=tcp::{PORT}-:8883", True),
        # 0.0.0.0 is every address, as the empty host address is: QEMU's
        # slirp listens on loopback too, so the generator's connection enters.
        ("127.0.0.1", PORT, f"hostfwd=tcp:0.0.0.0:{PORT}-:8883", True),
        # A host name (localhost included) is never matched to a forward:
        # F3_DESTINATIONS below. Without a forward of the port it enters none.
        ("localhost", PORT, f"hostfwd=tcp:127.0.0.1:{PORT + 1}-:8883", False),
        ("127.0.0.1", 1883, None, False),
        ("10.0.0.5", PORT, None, False),
        ("127.0.0.1", PORT, f"hostfwd=tcp:192.168.1.2:{PORT}-:8883", False),
        ("127.0.0.1", PORT, f"hostfwd=udp:127.0.0.1:{PORT}-:8883", False),
        (None, PORT, None, None),
        ("127.0.0.1", None, None, None),
    ],
)
def test_snapshot_records_whether_the_generator_targets_this_guest(host, broker, port, hostfwd, expected) -> None:
    add_qemu(host, argv=qemu_argv(host.images, hostfwd=hostfwd))  # type: ignore[attr-defined]
    snap = _snapshot(host, broker=broker, port=port)
    assert snap["generator_target_is_this_guest"] is expected
    if expected is None:
        assert any(p.startswith("generator_target_is_this_guest:") for p in snap["problems"])


def test_snapshot_names_unreadable_identity_files(host, monkeypatch) -> None:
    images = host.images  # type: ignore[attr-defined]
    argv = [a for a in qemu_argv(images)]
    argv[argv.index("-kernel") + 1] = str(images / "missing-Image")
    add_qemu(host, argv=argv, exe=images / "gone-qemu-system-aarch64")
    monkeypatch.setattr(env_mod, "_qemu_version_line", lambda exe_path: (None, f"{exe_path} --version failed"))
    snap = _snapshot(host)
    q = snap["qemu"]
    assert q["exe_sha256"] is None and q["kernel_sha256"] is None and q["version_line"] is None
    assert q["kernel_hash_basis"] is None  # no hash, so no basis is stated
    for prefix in ("qemu.exe_sha256:", "qemu.kernel_sha256:", "qemu.version_line:"):
        assert any(p.startswith(prefix) for p in snap["problems"]), prefix


def test_snapshot_needs_one_rootfs_drive_and_an_absolute_kernel(host) -> None:
    images = host.images  # type: ignore[attr-defined]
    argv = qemu_argv(images)
    argv[argv.index("-kernel") + 1] = "Image"
    argv = [a.replace(ROOTFS_NAME + ".ext4", "plain.ext4") for a in argv]
    add_qemu(host, argv=argv)
    snap = _snapshot(host)
    assert snap["qemu"]["rootfs_path"] is None and snap["qemu"]["rootfs_image_name"] is None
    assert snap["qemu"]["kernel_sha256"] is None
    assert any(p.startswith("qemu.rootfs_path:") for p in snap["problems"])
    assert any(p.startswith("qemu.kernel_sha256:") for p in snap["problems"])


def test_snapshot_does_not_choose_between_two_rootfs_drives(host) -> None:
    images = host.images  # type: ignore[attr-defined]
    add_qemu(host, argv=qemu_argv(images, extra=("-drive", f"file={images / 'other.rootfs-1.ext4'},if=none")))
    snap = _snapshot(host)
    assert snap["qemu"]["rootfs_path"] is None and snap["qemu"]["rootfs_image_name"] is None
    assert any(p.startswith("qemu.rootfs_path:") for p in snap["problems"])


def test_write_hypervisor_environment_is_write_once(host, tmp_path) -> None:
    add_qemu(host)
    start = _snapshot(host)
    path = env_mod.write_hypervisor_environment(tmp_path / "hypervisor_environment.json", start, None)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    doc = json.loads(raw.decode("utf-8"))
    assert doc == {
        "role": "hypervisor", "record_version": 1, "capture": "harness /proc read on the load-generator host",
        "start": start, "end": None,
    }
    with pytest.raises(FileExistsError):
        env_mod.write_hypervisor_environment(path, start, start)


def test_image_identity_record_comes_from_the_start_snapshot(host) -> None:
    add_qemu(host)
    start = _snapshot(host)
    hv = {"role": "hypervisor", "start": start, "end": None}
    identity = env_mod.image_identity_record(hv, {"controller_image_id": "sha256:" + "ab" * 32})
    assert identity == {
        "qemu_exe_sha256": _sha(b"qemu binary\n"),
        "qemu_version_line": QEMU_VERSION,
        "kernel_sha256": _sha(b"arm64 kernel image\n"),
        "rootfs_path": str(host.images / (ROOTFS_NAME + ".ext4")),  # type: ignore[attr-defined]
        "rootfs_image_name": ROOTFS_NAME,
        "image_digests_ref": "image_digests",
        "controller_image_id": "sha256:" + "ab" * 32,
    }
    empty = env_mod.image_identity_record(None, None)
    assert empty["image_digests_ref"] == "image_digests"
    assert all(v is None for k, v in empty.items() if k != "image_digests_ref")


# ---------------------------------------------------------------------------
# The provenance checks
# ---------------------------------------------------------------------------


def _guest_record() -> dict[str, Any]:
    """The sealed guest record of test 6 (captured on the guest)."""
    return {
        "role": "sut",
        "captured_utc": "2026-10-07T12:08:26Z",
        "node": "egw-qemu-integrated",
        "uname_a": "Linux egw-qemu-integrated 6.6.142-yocto-standard #1 SMP PREEMPT Tue Jun 23 17:26:44 UTC 2026 "
                   "aarch64 GNU/Linux",
        "os_pretty_name": "Poky (Yocto Project Reference Distro) 5.0.19 (scarthgap)",
        "nproc": 4,
        "cpu_model": "0xd0b",
        "mem_total_kb": 8204356,
        "provider": "QEMU 8.2.7 TCG (qemu-system-native) on WSL2 Ubuntu-24.04, Windows 11 x86-64",
        "region": "local-workstation",
        "instance_type": "qemu -machine virt -cpu cortex-a76 -smp 4 -m 8192; ARM64 EMULATED",
        "shared_vcpu_note": "TCG emulation on a shared x86-64 host; load generator co-located; never native ARM64",
    }


@pytest.fixture
def records(host, tmp_path) -> dict[str, Any]:
    """The three records of a consistent tcg-emulated run, as read back from its files."""
    add_bystanders(host)
    add_qemu(host)
    run_dir = tmp_path / "run"
    env_mod.write_loadgen_environment(
        run_dir / "loadgen_environment.json", simulator_argv=["py", "--port", str(PORT)], proc_root=host.root,
    )
    loadgen = env_mod.read_environment_record(run_dir, "loadgen_environment.json")
    start = _snapshot(host, loadgen_env=loadgen)
    end = _snapshot(host, loadgen_env=loadgen)
    env_mod.write_hypervisor_environment(run_dir / "hypervisor_environment.json", start, end)
    return {
        "execution_mode": "tcg-emulated",
        "sut_env": _guest_record(),
        "loadgen_env": loadgen,
        "hypervisor_env": env_mod.read_environment_record(run_dir, "hypervisor_environment.json"),
        "broker": BROKER,
        "port": PORT,
    }


def _by_id(checks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {c["check"]: c for c in checks}


def test_a_consistent_tcg_run_passes_every_check(records) -> None:
    checks = env_mod.provenance_checks(**records)
    assert [c["check"] for c in checks] == TCG_CHECKS
    for check in checks:
        # G5 alone is advisory and says so; every other check keeps the shape.
        advisory = {"advisory"} if check["check"] == "G5" else set()
        assert set(check) == {"check", "ok", "detail"} | advisory, check
        assert check["ok"] is True, check
        assert isinstance(check["detail"], str) and check["detail"]
    assert _by_id(checks)["G5"]["advisory"] is True
    assert env_mod.provenance_problems(checks) == []


def test_an_unset_mode_fails_p0_alone_and_nothing_is_inferred(records) -> None:
    checks = env_mod.provenance_checks(**{**records, "execution_mode": None})
    assert [c["check"] for c in checks] == ["P0"]
    assert checks[0]["ok"] is False
    problems = env_mod.provenance_problems(checks)
    assert len(problems) == 1 and problems[0].startswith("provenance: P0: ")
    assert "not set" in problems[0]


def test_an_unknown_mode_fails_p0(records) -> None:
    checks = env_mod.provenance_checks(**{**records, "execution_mode": "emulated-qemu-tcg"})
    assert [(c["check"], c["ok"]) for c in checks] == [("P0", False)]
    assert "emulated-qemu-tcg" in checks[0]["detail"]


def _set(path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    """Set the dotted ``path`` (record.key.key...) of the records to ``value``; None at the record drops it."""
    def apply(rec: dict[str, Any]) -> None:
        keys = path.split(".")
        if len(keys) == 1:
            rec[keys[0]] = value
            return
        target = rec[keys[0]]
        for key in keys[1:-1]:
            target = target[key]
        target[keys[-1]] = value
    return apply


def _apply_all(*changes: Callable[[dict[str, Any]], None]) -> Callable[[dict[str, Any]], None]:
    def apply(rec: dict[str, Any]) -> None:
        for change in changes:
            change(rec)
    return apply


FAILURES = [
    ("H1", "no hypervisor record", _set("hypervisor_env", None)),
    ("H1", "the record is not the hypervisor's", _set("hypervisor_env.role", "loadgen")),
    ("H1", "no QEMU at start", _apply_all(_set("hypervisor_env.start.qemu.found", 0),
                                          _set("hypervisor_env.start.qemu.pid", None))),
    ("H1", "two QEMU at start", _apply_all(_set("hypervisor_env.start.qemu.found", 2),
                                           _set("hypervisor_env.start.qemu.pid", None))),
    ("H2", "no end snapshot", _set("hypervisor_env.end", None)),
    ("H2", "another pid at the end", _set("hypervisor_env.end.qemu.pid", 9999)),
    ("H2", "another start time at the end", _set("hypervisor_env.end.qemu.starttime_ticks", 1)),
    ("H2", "another boot at the end", _set("hypervisor_env.end.host.boot_id", "other")),
    ("H2", "another argv at the end", _set("hypervisor_env.end.qemu.argv_sha256", "0" * 64)),
    ("H3", "kvm accelerator", _set("hypervisor_env.start.qemu.accelerator", "kvm")),
    ("H3", "undetermined accelerator", _set("hypervisor_env.start.qemu.accelerator", None)),
    ("H3", "kvm requested", _set("hypervisor_env.start.qemu.parsed.kvm_requested", True)),
    ("H4", "co-location not recorded", _set("hypervisor_env.start.colocated_with_loadgen", None)),
    ("H4", "co-location against the boot ids", _set("hypervisor_env.start.colocated_with_loadgen", False)),
    # Review of PR #60: a record that says the load generator was NOT
    # co-located fails, even when the boot ids bear the flag out.
    ("H4", "not co-located, as the boot ids say", _apply_all(
        _set("hypervisor_env.start.colocated_with_loadgen", False), _set("loadgen_env.boot_id", "other"))),
    ("H4", "another load-generator boot", _set("loadgen_env.boot_id", "other")),
    ("H4", "no load-generator boot id", _set("loadgen_env.boot_id", None)),
    ("H5", "a remote broker", _set("broker", "10.0.0.5")),
    ("H5", "another port", _set("port", 1883)),
    ("H5", "the recorded flag is false", _set("hypervisor_env.start.generator_target_is_this_guest", False)),
    ("H5", "no forward to loopback", _set("hypervisor_env.start.qemu.parsed.hostfwd", [])),
    ("G1", "no guest record", _set("sut_env", None)),
    ("G1", "a load-generator capture given as the guest's", _set("sut_env.role", "loadgen")),
    ("G2", "an x86-64 guest", _set("sut_env.uname_a", "Linux box 6.6.87 #1 SMP x86_64 GNU/Linux")),
    ("G3", "nproc differs from -smp", _set("sut_env.nproc", 2)),
    ("G3", "no -smp", _set("hypervisor_env.start.qemu.parsed.smp", None)),
    ("G4", "no label states emulation", _apply_all(
        _set("sut_env.provider", "Raspberry Pi 5"), _set("sut_env.instance_type", "8 GB"),
        _set("sut_env.shared_vcpu_note", "dedicated cores"))),
    ("L1", "the load-generator record is not one", _set("loadgen_env.role", "sut")),
    ("L1", "another machine", _set("loadgen_env.machine", "aarch64")),
    ("L1", "no load-generator record", _set("loadgen_env", None)),
    ("I1", "no QEMU executable hash", _set("hypervisor_env.start.qemu.exe_sha256", None)),
    ("I1", "no kernel hash", _set("hypervisor_env.start.qemu.kernel_sha256", None)),
    ("I1", "no rootfs image name", _set("hypervisor_env.start.qemu.rootfs_image_name", None)),
]


@pytest.mark.parametrize(("check", "case", "change"), FAILURES, ids=[f"{c}-{d}" for c, d, _ in FAILURES])
def test_each_tcg_check_fails_on_its_own_fact(records, check, case, change) -> None:
    rec = copy.deepcopy(records)
    change(rec)
    checks = env_mod.provenance_checks(**rec)
    assert [c["check"] for c in checks] == TCG_CHECKS
    failed = {c["check"] for c in checks if not c["ok"]}
    assert check in failed, (case, checks)
    problems = env_mod.provenance_problems(checks)
    assert any(p.startswith(f"provenance: {check}: ") for p in problems)
    # One reason per failed check, the advisory G5 excepted (a missing guest
    # or hypervisor record also fails G5, which is never a reason).
    assert len(problems) == len(failed - set(env_mod.ADVISORY_CHECKS))


#: G5's facts. Its QEMU start is derived from the host's btime read at the
#: snapshot, which moves with every host wall-clock step since QEMU started
#: (WSL2: -5.1 % to +3.0 % against uptime over a session), so a good run can
#: fail it and a stale record can pass it: G5 is advisory.
G5_FAILURES = [
    ("a guest capture older than this QEMU", _set("sut_env.captured_utc", "2026-10-07T11:20:00Z")),
    # The 2026-10-07 margin (QEMU 12:03:59Z, guest 12:08:26Z) overtaken by a
    # forward drift of the host's wall clock: the derived start passes the capture.
    ("a QEMU start drifted past the capture", _set("hypervisor_env.start.qemu.start_utc", "2026-10-07T12:08:27.000Z")),
    ("no guest capture time", _set("sut_env.captured_utc", None)),
    ("an unreadable QEMU start", _set("hypervisor_env.start.qemu.start_utc", "yesterday")),
]


@pytest.mark.parametrize(("case", "change"), G5_FAILURES, ids=[c for c, _ in G5_FAILURES])
def test_g5_is_advisory_and_never_a_validity_reason(records, case, change) -> None:
    rec = copy.deepcopy(records)
    change(rec)
    checks = env_mod.provenance_checks(**rec)
    assert [c["check"] for c in checks] == TCG_CHECKS
    g5 = _by_id(checks)["G5"]
    assert g5["ok"] is False and g5["advisory"] is True, case
    assert "advisory" in g5["detail"]
    assert [c["check"] for c in checks if not c["ok"]] == ["G5"]
    assert env_mod.provenance_problems(checks) == []


def test_g5_names_the_clock_basis_of_the_qemu_start(records) -> None:
    g5 = _by_id(env_mod.provenance_checks(**records))["G5"]
    assert g5["ok"] is True
    assert f"btime {BTIME}" in g5["detail"] and f"{CLK_TCK} Hz" in g5["detail"]
    assert QEMU_START_UTC in g5["detail"] and "advisory" in g5["detail"]
    # A snapshot that does not record its btime is named as such, never guessed.
    rec = copy.deepcopy(records)
    del rec["hypervisor_env"]["start"]["qemu"]["btime"]
    g5 = _by_id(env_mod.provenance_checks(**rec))["G5"]
    assert g5["ok"] is True and "btime not recorded" in g5["detail"]


def test_g4_reads_the_labels_case_insensitively(records) -> None:
    rec = copy.deepcopy(records)
    for key in ("provider", "instance_type", "shared_vcpu_note"):
        rec["sut_env"][key] = "native board"
    rec["sut_env"]["region"] = "lab, Qemu/Tcg"
    assert _by_id(env_mod.provenance_checks(**rec))["G4"]["ok"] is True
    rec["sut_env"]["region"] = "lab, fully EMULATED"
    assert _by_id(env_mod.provenance_checks(**rec))["G4"]["ok"] is True


@pytest.mark.parametrize("host_addr", ["", "0.0.0.0"])
def test_h5_accepts_a_forward_on_every_address(records, host_addr) -> None:
    rec = copy.deepcopy(records)
    rec["hypervisor_env"]["start"]["qemu"]["parsed"]["hostfwd"] = [{
        "rule": f"tcp:{host_addr}:{PORT}-:8883", "protocol": "tcp", "host_addr": host_addr, "host_port": PORT,
        "guest_addr": "", "guest_port": 8883,
    }]
    assert _by_id(env_mod.provenance_checks(**rec))["H5"]["ok"] is True


def test_the_wrong_provenance_regression_names_n0_n1_and_n2(records) -> None:
    """A run declared native-kvm with an emulated guest record and a local
    QEMU forwarding the broker port is rejected, and says why."""
    checks = env_mod.provenance_checks(**{**records, "execution_mode": "native-kvm"})
    assert [c["check"] for c in checks] == NATIVE_CHECKS
    by_id = _by_id(checks)
    assert by_id["P0"]["ok"] is True
    for check in ("N0", "N1", "N2", "N3"):
        assert by_id[check]["ok"] is False, check
    assert "no native provenance capture exists in this harness" in by_id["N0"]["detail"]
    problems = env_mod.provenance_problems(checks)
    for check in ("N0", "N1", "N2"):
        assert any(p.startswith(f"provenance: {check}: ") for p in problems), check
    assert str(QEMU_PID) in by_id["N1"]["detail"]


def test_n1_names_a_local_qemu_forwarding_the_port_on_every_address(records) -> None:
    """A forward bound to 0.0.0.0 takes the generator's loopback traffic as
    much as one bound to 127.0.0.1: N1 names it."""
    rec = copy.deepcopy(records)
    rec["execution_mode"] = "native-kvm"
    rule = f"tcp:0.0.0.0:{PORT}-:8883"
    for snapshot in ("start", "end"):
        rec["hypervisor_env"][snapshot]["qemu"]["parsed"]["hostfwd"] = [env_mod._parse_hostfwd(rule)]
    n1 = _by_id(env_mod.provenance_checks(**rec))["N1"]
    assert n1["ok"] is False
    assert rule in n1["detail"] and str(QEMU_PID) in n1["detail"]


def test_a_native_run_without_contradictions_still_fails_n0(records) -> None:
    rec = copy.deepcopy(records)
    rec["execution_mode"] = "native-metal"
    rec["broker"] = "10.0.0.5"
    rec["sut_env"] = {
        "role": "sut", "captured_utc": "2026-10-07T12:00:00Z", "node": "egw-pi5", "nproc": 4,
        "uname_a": "Linux egw-pi5 6.6 #1 SMP aarch64 GNU/Linux", "provider": "Raspberry Pi 5",
        "region": "lab", "instance_type": "8 GB", "shared_vcpu_note": "dedicated cores",
    }
    checks = env_mod.provenance_checks(**rec)
    assert [(c["check"], c["ok"]) for c in checks] == [
        ("P0", True), ("N0", False), ("N1", True), ("N2", True), ("N3", True),
    ]
    assert [p.split(":")[1].strip() for p in env_mod.provenance_problems(checks)] == ["N0"]
    # Without any hypervisor record no local QEMU contradiction can be shown; N0 still fails.
    rec["hypervisor_env"] = None
    assert [(c["check"], c["ok"]) for c in env_mod.provenance_checks(**rec)][:3] == [
        ("P0", True), ("N0", False), ("N1", True),
    ]


@pytest.mark.parametrize(
    ("check", "change"),
    [
        ("N1", _set("broker", "10.0.0.5")),
        ("N2", _apply_all(_set("sut_env.provider", "board"), _set("sut_env.instance_type", "board"),
                          _set("sut_env.shared_vcpu_note", "dedicated"))),
        ("N3", _set("sut_env.node", "egw-pi5")),
    ],
)
def test_each_native_contradiction_rests_on_its_own_fact(records, check, change) -> None:
    # Remove one contradiction from the regression's records: that check
    # passes, and the declaration is still rejected by N0.
    rec = copy.deepcopy(records)
    rec["execution_mode"] = "native-kvm"
    change(rec)
    by_id = _by_id(env_mod.provenance_checks(**rec))
    assert by_id[check]["ok"] is True
    assert by_id["N0"]["ok"] is False


# ---------------------------------------------------------------------------
# F3 (review of PR #60, 2026-10-08): the generator's destination is matched to
# the forward's bind, address and family; a wildcard only where it applies
# ---------------------------------------------------------------------------

#: (case, the generator's broker, the forward's host address, whether the
#: generator's connection is shown to enter that forward: True, False, or
#: None when the records cannot decide it). QEMU 8.2.7 reads the host address
#: with inet_aton (net/slirp.c, slirp_hostfwd): IPv4 only, the empty address
#: keeping INADDR_ANY; it cannot express an IPv6 address or a host name.
F3_DESTINATIONS = [
    # The canonical route and the two wildcards.
    ("127.0.0.1 to a 127.0.0.1 bind", "127.0.0.1", "127.0.0.1", True),
    ("127.0.0.1 to the empty wildcard", "127.0.0.1", "", True),
    ("127.0.0.1 to the 0.0.0.0 wildcard", "127.0.0.1", "0.0.0.0", True),
    # Another loopback address, or the IPv6 family, against an exact bind.
    ("127.0.0.2 to a 127.0.0.1 bind", "127.0.0.2", "127.0.0.1", False),
    ("::1 to a 127.0.0.1 bind", "::1", "127.0.0.1", False),
    # An IPv4 wildcard takes every IPv4 loopback address, never IPv6.
    ("127.0.0.2 to the empty wildcard", "127.0.0.2", "", True),
    ("127.0.0.2 to the 0.0.0.0 wildcard", "127.0.0.2", "0.0.0.0", True),
    ("::1 to the empty wildcard", "::1", "", False),
    ("::1 to the 0.0.0.0 wildcard", "::1", "0.0.0.0", False),
    # A host name is not an address: it is never matched to a bind.
    ("localhost to a 127.0.0.1 bind", "localhost", "127.0.0.1", None),
    ("localhost to the empty wildcard", "localhost", "", None),
    ("localhost to the 0.0.0.0 wildcard", "localhost", "0.0.0.0", None),
    ("a bracketed [::1]", "[::1]", "127.0.0.1", None),
    # A dual-stack socket may carry an IPv4-mapped address to an IPv4 forward.
    ("an IPv4-mapped ::ffff:127.0.0.1", "::ffff:127.0.0.1", "127.0.0.1", None),
    # A bind that is not a dotted-quad IPv4 address, nor a wildcard, is not read.
    ("a bind written 127.1", "127.0.0.1", "127.1", None),
    ("an IPv6 bind QEMU cannot express", "::1", "[::1]", None),
    # Whether another IPv4 address is this host's is not recorded.
    ("a non-loopback address to the wildcard", "10.0.0.5", "0.0.0.0", None),
    ("a non-loopback address to its own bind", "192.168.1.2", "192.168.1.2", True),
]
F3_IDS = [case for case, *_ in F3_DESTINATIONS]


@pytest.mark.parametrize(("case", "broker", "bind", "takes"), F3_DESTINATIONS, ids=F3_IDS)
def test_f3_the_snapshot_matches_the_destination_to_the_bind(host, case, broker, bind, takes) -> None:
    add_qemu(host, argv=qemu_argv(host.images, hostfwd=f"hostfwd=tcp:{bind}:{PORT}-:8883"))  # type: ignore[attr-defined]
    snap = _snapshot(host, broker=broker)
    assert snap["generator_target_is_this_guest"] is takes, (case, snap["problems"])
    undecided = [p for p in snap["problems"] if p.startswith("generator_target_is_this_guest:")]
    assert bool(undecided) is (takes is None), (case, snap["problems"])


def _forwarding(records: dict[str, Any], broker: str, bind: str, mode: str) -> dict[str, Any]:
    """The records with ``broker`` as the generator's target and one forward
    of the port bound to ``bind`` in both snapshots. The recorded flag stays
    true, as a record of the earlier rule could hold it: the checks match the
    destination to the recorded command line themselves."""
    rec = copy.deepcopy(records)
    rec["execution_mode"] = mode
    rec["broker"] = broker
    rule = env_mod._parse_hostfwd(f"tcp:{bind}:{PORT}-:8883")
    for snapshot in ("start", "end"):
        rec["hypervisor_env"][snapshot]["qemu"]["parsed"]["hostfwd"] = [rule]
        rec["hypervisor_env"][snapshot]["generator_target_is_this_guest"] = True
    return rec


@pytest.mark.parametrize(("case", "broker", "bind", "takes"), F3_DESTINATIONS, ids=F3_IDS)
def test_f3_h5_needs_a_forward_that_takes_the_loopback_destination(records, case, broker, bind, takes) -> None:
    checks = env_mod.provenance_checks(**_forwarding(records, broker, bind, "tcg-emulated"))
    h5 = _by_id(checks)["H5"]
    # H5 keeps its IPv4 loopback target: a forward that takes another address
    # (its own exact bind) still fails it.
    assert h5["ok"] is (takes is True and broker.startswith("127.")), (case, h5)
    # The destination is H5's fact alone.
    assert [c["check"] for c in checks if not c["ok"]] == ([] if h5["ok"] else ["H5"])
    if not h5["ok"]:
        assert f"{broker}:{PORT}" in h5["detail"]


@pytest.mark.parametrize(("case", "broker", "bind", "takes"), F3_DESTINATIONS, ids=F3_IDS)
def test_f3_n1_passes_only_when_no_forward_can_take_the_traffic(records, case, broker, bind, takes) -> None:
    checks = env_mod.provenance_checks(**_forwarding(records, broker, bind, "native-kvm"))
    n1 = _by_id(checks)["N1"]
    assert n1["ok"] is (takes is False), (case, n1)
    if takes is None:
        assert "cannot be decided" in n1["detail"], n1
    if takes is not False:
        assert f"tcp:{bind}:{PORT}-:8883" in n1["detail"] and str(QEMU_PID) in n1["detail"]
    assert _by_id(checks)["N0"]["ok"] is False


def test_provenance_problems_format() -> None:
    checks = [
        {"check": "P0", "ok": True, "detail": "declared"},
        {"check": "H1", "ok": False, "detail": "no hypervisor record"},
        {"check": "G5", "ok": False, "detail": "too early", "advisory": True},
        {"check": "I1", "ok": False, "detail": "no kernel hash", "advisory": False},
    ]
    # An advisory check is recorded with its verdict and is never a reason.
    assert env_mod.provenance_problems(checks) == [
        "provenance: H1: no hypervisor record",
        "provenance: I1: no kernel hash",
    ]
    assert env_mod.provenance_problems([]) == []


def test_checks_survive_malformed_records(records) -> None:
    rec = copy.deepcopy(records)
    rec["hypervisor_env"] = {"role": "hypervisor", "start": "garbage", "end": ["x"]}
    rec["sut_env"] = {"role": "sut", "nproc": "four"}
    rec["loadgen_env"] = {"role": "loadgen", "boot_id": 7}
    checks = env_mod.provenance_checks(**rec)
    assert [c["check"] for c in checks] == TCG_CHECKS
    assert [c["check"] for c in checks if c["ok"]] == ["P0", "G1"]


# ---------------------------------------------------------------------------
# The real /proc of a Linux host
# ---------------------------------------------------------------------------

linux_only = pytest.mark.skipif(
    sys.platform != "linux" or not Path("/proc/self/cmdline").is_file(),
    reason="reads the real /proc of a Linux host",
)


def _wait_for(pid: int, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if pid in env_mod.find_qemu_processes()[0]:
            return
        time.sleep(0.05)


@pytest.fixture
def python_as_qemu(tmp_path):
    """A Python interpreter reached through a symbolic link named
    qemu-system-aarch64, with QEMU-like arguments after its own."""
    link = tmp_path / "bin" / "qemu-system-aarch64"
    link.parent.mkdir()
    _symlink(os.path.realpath(sys.executable), link)
    images = tmp_path / "images"
    images.mkdir()
    (images / "Image").write_bytes(b"kernel\n")
    (images / (ROOTFS_NAME + ".ext4")).write_bytes(b"rootfs\n")
    argv = [
        str(link), "-c", "import time; time.sleep(60)",
        "-netdev", "user,id=net0,hostfwd=tcp:127.0.0.1:18883-:8883",
        "-drive", f"id=disk0,file={images / (ROOTFS_NAME + '.ext4')},if=none,format=raw",
        "-machine", "virt", "-cpu", "cortex-a76", "-smp", "4", "-m", "8192",
        "-kernel", str(images / "Image"), "-append", "root=/dev/vda rw",
    ]
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL)
    try:
        _wait_for(proc.pid)
        yield proc, argv
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)


@pytest.fixture
def mentioning_shell():
    """A shell whose command line holds the name and is not QEMU (see test_qemu_process_guard)."""
    proc = subprocess.Popen(["bash", "-c", "echo qemu-system-aarch64 -machine virt; sleep 60; echo done"],
                            stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    time.sleep(0.3)
    try:
        yield proc
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)


@linux_only
def test_real_proc_finds_the_executable_and_not_the_mentioning_shell(python_as_qemu, mentioning_shell) -> None:
    proc, argv = python_as_qemu
    pids, error = env_mod.find_qemu_processes()
    assert error is None
    assert proc.pid in pids
    assert mentioning_shell.pid not in pids
    got, digest = env_mod.read_argv(proc.pid)
    assert got == argv
    assert digest == _sha(Path(f"/proc/{proc.pid}/cmdline").read_bytes())


@linux_only
def test_real_proc_snapshot_of_the_stand_in(python_as_qemu, monkeypatch) -> None:
    proc, argv = python_as_qemu
    if env_mod.find_qemu_processes()[0] != [proc.pid]:
        pytest.skip("another qemu-system-aarch64 runs on this host")
    # No docker CLI is consulted by this case.
    monkeypatch.setattr(env_mod, "_run_capture", lambda *a, **k: None)
    loadgen = env_mod.capture_environment()
    snap = env_mod.capture_hypervisor_snapshot(loadgen_env=loadgen, broker="127.0.0.1", port=18883)
    q = snap["qemu"]
    real = os.path.realpath(sys.executable)
    assert q["pid"] == proc.pid
    assert q["argv"] == argv
    assert q["exe_path"] == real
    assert q["exe_sha256"] == hashlib.sha256(Path(real).read_bytes()).hexdigest()
    assert q["version_line"] and q["version_line"].startswith("Python ")
    assert q["kernel_sha256"] == _sha(b"kernel\n")
    assert q["rootfs_image_name"] == ROOTFS_NAME
    assert q["parsed"]["smp"] == 4
    assert q["kvm_device_open"] is False
    assert q["accelerator"] == "tcg"
    assert q["target_arch"] == "aarch64"
    stat_fields = Path(f"/proc/{proc.pid}/stat").read_text().rsplit(")", 1)[1].split()
    assert q["starttime_ticks"] == int(stat_fields[19])
    started = datetime.fromisoformat(q["start_utc"].replace("Z", "+00:00"))
    assert abs(started - datetime.now(timezone.utc)) < timedelta(minutes=10)
    assert snap["host"]["boot_id"] == loadgen["boot_id"]
    assert snap["colocated_with_loadgen"] is True
    assert snap["generator_target_is_this_guest"] is True
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", q["start_utc"])
