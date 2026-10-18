"""tools/compare/compare_env.sh: the lifecycle CLI behind the two comparison environments (Yocto vs Debian 13).

The CLI is run as Terraform runs it (one argv, stdin from the null device) against a temporary state root, a scenario
file of its own, fake base artefacts and stub binaries first on PATH: a `qemu-system-aarch64` that, under -daemonize,
leaves a harmless sleeper behind whose command line reads as QEMU and writes its pid to -pidfile; `qemu-img`,
`mkfs.ext4`, `blkid`, `pgrep` and `ss` answering from the environment; an `ssh` whose `poweroff` ends the sleeper
unless the guest is told to ignore it. What these cases show is the script's own contract: the layout and manifest of
`prepare`, the guards and the honest state of `start`, a `stop` that never kills, a `destroy` that keeps bases and
results, and secrets that reach no file and no output. They say nothing about a real guest, QEMU or Terraform.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the comparison scripts are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)
if not Path("/proc/self/cmdline").exists():
    pytest.skip("Linux /proc is needed: the script reads the guest's command line there", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPARE_DIR = REPO_ROOT / "tools" / "compare"
SCRIPT = COMPARE_DIR / "compare_env.sh"
#: The root overlay is named after the base image (lib.sh): <image>.rootfs.qcow2.
ROOT_OVERLAY = "egw-gateway-image-qemuarm64.rootfs.qcow2"
TF_DIR = COMPARE_DIR / "terraform"
SECRET = "stub-secret-value"
STATUS_KEYS = {"scenario", "prepared", "running", "pid", "lock_holder", "started_uptime_s", "root_disk", "data_disk",
               "base_sha256", "manifest"}

QEMU_STUB = r'''#!/usr/bin/env python3
# Stub qemu-system-aarch64: answers --version; otherwise records argv, writes one console line and, as the real
# binary does under -daemonize, leaves a process behind whose command line reads qemu-system-aarch64 followed by
# the full argv (a sleeper) and writes its pid to -pidfile. EGW_STUB_QEMU_FAIL=1 is a machine that could not
# start: error, exit 1, no pid.
import json
import os
import shutil
import sys

argv = sys.argv[1:]
with open(os.environ["EGW_STUB_CALLS"], "a", encoding="utf-8") as log:
    log.write("qemu-system-aarch64 " + json.dumps(argv) + "\n")
if "--version" in argv:
    print("QEMU emulator version 8.2.7")
    sys.exit(0)
pidfile = console = None
daemonize = False
for i, arg in enumerate(argv[:-1]):
    if arg == "-pidfile":
        pidfile = argv[i + 1]
    elif arg == "-serial" and argv[i + 1].startswith("file:"):
        console = argv[i + 1][len("file:"):]
    elif arg == "-daemonize":
        daemonize = True
daemonize = daemonize or argv[-1] == "-daemonize"
if console:
    with open(console, "a", encoding="utf-8") as f:
        f.write("stub console: machine virt, cortex-a76\n")
if os.environ.get("EGW_STUB_QEMU_FAIL") == "1":
    print("qemu-system-aarch64: stub: the machine could not be initialised", file=sys.stderr)
    sys.exit(1)
if not (daemonize and pidfile):
    print("stub qemu: -daemonize and -pidfile are expected, got: " + " ".join(argv), file=sys.stderr)
    sys.exit(1)
pid = os.fork()
if pid == 0:
    os.setsid()
    null = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(null, fd)
    os.closerange(3, 1024)
    os.execv(sys.executable, ["qemu-system-aarch64", "-c", "import time\nwhile True:\n    time.sleep(3600)", *argv])
with open(os.environ["EGW_STUB_SLEEPERS"], "a", encoding="utf-8") as f:
    f.write(f"{pid}\n")
with open(pidfile, "w", encoding="utf-8") as f:
    f.write(f"{pid}\n")
'''

SSH_STUB = r'''#!/usr/bin/env python3
# Stub ssh: records the call; a command holding 'poweroff' ends the guest (the sleeper named in EGW_STUB_PIDFILE)
# unless EGW_STUB_SSH_IGNORE_POWEROFF=1, a guest that does not act on it; anything else succeeds without effect.
# EGW_STUB_SSH_RC, when set, is the exit code of every call (a guest whose sshd does not answer yet).
# EGW_STUB_SSH_EXEC=1 runs the remote command (the last argument) locally with sh -c, so that the guest's
# file system is this machine's: its stdout and exit status are the call's.
import os
import signal
import sys

args = sys.argv[1:]
with open(os.environ["EGW_STUB_CALLS"], "a", encoding="utf-8") as log:
    log.write("ssh " + " ".join(args) + "\n")
if any("poweroff" in a for a in args) and os.environ.get("EGW_STUB_SSH_IGNORE_POWEROFF") != "1":
    try:
        with open(os.environ["EGW_STUB_PIDFILE"], encoding="utf-8") as f:
            os.kill(int(f.read().strip()), signal.SIGTERM)
    except (OSError, ValueError):
        pass
if os.environ.get("EGW_STUB_SSH_RC"):
    sys.exit(int(os.environ["EGW_STUB_SSH_RC"]))
if os.environ.get("EGW_STUB_SSH_EXEC") == "1" and args:
    import subprocess
    sys.exit(subprocess.run(["sh", "-c", args[-1]]).returncode)
sys.exit(0)
'''

SCP_STUB = r'''#!/usr/bin/env python3
# Stub scp: copies local paths (the host part of egw@127.0.0.1:/path is dropped, the guest's file system being this
# machine's). EGW_STUB_SCP_GROW_SRC=1 appends a line to the SOURCE after copying (a log still being written);
# EGW_STUB_SCP_CORRUPT=1 appends a byte to the copy (a transfer that did not deliver the bytes read).
import os
import shutil
import sys

args = [a for a in sys.argv[1:] if not a.startswith("-")]
with open(os.environ["EGW_STUB_CALLS"], "a", encoding="utf-8") as log:
    log.write("scp " + " ".join(sys.argv[1:]) + "\n")
src, dst = (a.split(":", 1)[1] if "@" in a else a for a in args[-2:])
try:
    shutil.copyfile(src, dst)
except OSError as exc:
    print(f"stub scp: {exc}", file=sys.stderr)
    sys.exit(1)
if os.environ.get("EGW_STUB_SCP_GROW_SRC") == "1":
    with open(src, "a", encoding="utf-8") as f:
        f.write("{\"late\": true}\n")
if os.environ.get("EGW_STUB_SCP_CORRUPT") == "1":
    with open(dst, "ab") as f:
        f.write(b"x")
'''

QEMU_IMG_STUB = r'''#!/bin/sh
# Stub qemu-img: 'create' writes a small non-empty output (the last path argument), as the real tool
# writes a qcow2 header; 'info' says nothing.
echo "qemu-img $*" >> "$EGW_STUB_CALLS"
case $1 in
    --version) echo "qemu-img version 8.2.7" ;;
    create) out=; for a in "$@"; do case $a in */*) out=$a ;; esac; done; printf 'QFI stub\n' > "$out" ;;
    info) ;;
    *) echo "stub qemu-img: unsupported $1" >&2; exit 1 ;;
esac
'''

MKFS_STUB = r'''#!/bin/sh
# Stub mkfs.ext4: records the call and makes no file system.
echo "mkfs.ext4 $*" >> "$EGW_STUB_CALLS"
'''

BLKID_STUB = r'''#!/bin/sh
# Stub blkid: the data disk carries the expected label.
echo "blkid $*" >> "$EGW_STUB_CALLS"
echo egw-data
'''

PGREP_STUB = r'''#!/bin/sh
# Stub pgrep: the host's other QEMU processes are the lines of EGW_STUB_OTHER_QEMU (none: exit 1).
echo "pgrep $*" >> "$EGW_STUB_CALLS"
[ -n "${EGW_STUB_OTHER_QEMU:-}" ] || exit 1
printf '%s\n' "$EGW_STUB_OTHER_QEMU"
'''

SS_STUB = r'''#!/bin/sh
# Stub ss: the host's listeners are the lines of EGW_STUB_BUSY_PORTS.
echo "State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process"
[ -z "${EGW_STUB_BUSY_PORTS:-}" ] || printf '%s\n' "$EGW_STUB_BUSY_PORTS"
'''

SCENARIO_ENV = """# shellcheck shell=bash
# Scenario yocto for the tests: fake base artefacts, the pilot's keys otherwise.
SCENARIO=yocto
DISTRO_LABEL="Poky 5.0.19 (scarthgap) egw-gateway-image test"
GUEST_HOSTNAME=egw-qemu-integrated
BASE_KIND=yocto-deploy
BASE_ROOTFS_SRC={rootfs}
BASE_KERNEL_SRC={kernel}
BASE_INITRD_SRC=
ROOT_FORMAT=raw
KERNEL_APPEND="root=/dev/vda rw console=ttyAMA0"
FIRSTBOOT_APPEND=
BASE_IMAGE_URL=
BASE_IMAGE_SHA512=
BASE_IMAGE_FILE=
"""


class Bench:
    """A temporary state root, a scenario of its own and a stub host around runs of the CLI."""

    def __init__(self, tmp_path: Path) -> None:
        self.bin = tmp_path / "bin"
        self.root = tmp_path / "egw-compare"
        self.scenarios = tmp_path / "scenarios"
        self.exec_dir = tmp_path / "egw-exec"
        self.home = tmp_path / "home"
        self.deploy = tmp_path / "deploy"
        for directory in (self.bin, self.root, self.scenarios, self.exec_dir, self.home, self.deploy):
            directory.mkdir()
        for name, text in (("qemu-system-aarch64", QEMU_STUB), ("ssh", SSH_STUB), ("scp", SCP_STUB), ("qemu-img", QEMU_IMG_STUB),
                           ("mkfs.ext4", MKFS_STUB), ("blkid", BLKID_STUB), ("pgrep", PGREP_STUB), ("ss", SS_STUB)):
            path = self.bin / name
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)
        self.rootfs_src = self.deploy / "egw-gateway-image-qemuarm64.rootfs.ext4"
        self.rootfs_src.write_bytes(bytes(range(256)) * 4096)  # 1 MiB
        self.kernel_src = self.deploy / "Image"
        self.kernel_src.write_bytes(b"not a kernel\n" * 512)
        self.key = tmp_path / "egw_campaign"
        self.key.write_text("stub private key\n", encoding="utf-8")
        self.key.chmod(0o600)
        (tmp_path / "egw_campaign.pub").write_text("ssh-ed25519 AAAAstub egw\n", encoding="utf-8")
        self.calls = tmp_path / "calls.log"
        self.sleepers = tmp_path / "sleepers.txt"
        self.s_dir = self.root / "scenarios" / "yocto"
        self.b_dir = self.root / "base" / "yocto"
        self.disks = self.s_dir / "disks"
        self.pidfile = self.s_dir / "state" / "qemu.pid"
        self.manifest = self.s_dir / "manifest.json"
        self.write_scenario()

    def write_scenario(self, rootfs_src: Path | None = None) -> None:
        text = SCENARIO_ENV.format(rootfs=rootfs_src or self.rootfs_src, kernel=self.kernel_src)
        (self.scenarios / "yocto.env").write_text(text, encoding="utf-8")

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return self.run_script(SCRIPT, *args, **env)

    def run_script(self, script: Path, *args: str, **env: str) -> subprocess.CompletedProcess:
        """Run one of the comparison scripts against this bench's stub host and state root."""
        environment = {k: v for k, v in os.environ.items() if not k.startswith("EGW_")}
        environment.update({
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.home),
            "EGW_COMPARE_ROOT": str(self.root),
            "EGW_COMPARE_SCENARIOS_DIR": str(self.scenarios),
            "EGW_COMPARE_QEMU": str(self.bin / "qemu-system-aarch64"),
            "EGW_COMPARE_QEMU_IMG": str(self.bin / "qemu-img"),
            "EGW_COMPARE_SSH_KEY": str(self.key),
            "EGW_COMPARE_STOP_WAIT_S": "3",
            "EGW_EXEC": str(self.exec_dir),
            "EGW_STUB_CALLS": str(self.calls),
            "EGW_STUB_SLEEPERS": str(self.sleepers),
            "EGW_STUB_PIDFILE": str(self.pidfile),
            "EGW_STUB_OTHER_QEMU": "",
            "EGW_STUB_BUSY_PORTS": "",
            "EGW_STUB_QEMU_FAIL": "",
            "EGW_STUB_SSH_IGNORE_POWEROFF": "",
            "EGW_STUB_SSH_RC": "",
            "EGW_STUB_SSH_EXEC": "",
            "EGW_STUB_SCP_GROW_SRC": "",
            "EGW_STUB_SCP_CORRUPT": "",
            "MOSQUITTO_SIMULATOR_PASSWORD": SECRET,
            "EGW_MQTT_PASSWORD": SECRET,
        })
        environment.update(env)
        return subprocess.run(["bash", str(script), *args], env=environment, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=60)

    def ok(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        result = self.run(*args, **env)
        assert result.returncode == 0, _report(result)
        return result

    def status(self) -> dict[str, str]:
        """status: always exit 0, one JSON object whose values are all strings (an `external` data source)."""
        result = self.run("status", "yocto")
        assert result.returncode == 0, _report(result)
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, dict) and STATUS_KEYS <= set(parsed), parsed
        assert all(isinstance(value, str) for value in parsed.values()), parsed
        return parsed

    def log(self) -> list[str]:
        return self.calls.read_text(encoding="utf-8").splitlines() if self.calls.exists() else []

    def qemu_starts(self) -> list[list[str]]:
        """The argv of every QEMU run that was a machine start (not a --version)."""
        return [json.loads(line.split(" ", 1)[1]) for line in self.log()
                if line.startswith("qemu-system-aarch64 ") and "--version" not in line]

    def pid(self) -> int:
        return int(self.pidfile.read_text(encoding="utf-8").strip())

    def spawned(self) -> list[int]:
        return [int(x) for x in self.sleepers.read_text(encoding="utf-8").split()] if self.sleepers.exists() else []

    def files(self) -> list[str]:
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())

    def kill_sleepers(self) -> None:
        for pid in self.spawned():
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.fixture
def bench(tmp_path) -> Bench:
    instance = Bench(tmp_path)
    try:
        yield instance
    finally:
        instance.kill_sleepers()


def _report(result: subprocess.CompletedProcess) -> str:
    return f"exit {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def _cmdline(pid: int) -> list[str]:
    return Path(f"/proc/{pid}/cmdline").read_bytes().decode().split("\0")[:-1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _strings(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _strings(value)
    elif isinstance(obj, str):
        yield obj


def _serial_file(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv[:-1]):
        if arg == "-serial" and argv[i + 1].startswith("file:"):
            return argv[i + 1][len("file:"):]
    return None


def _assert_refused(bench: Bench, result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 2, _report(result)
    assert "STOP:" in result.stderr, _report(result)
    assert bench.qemu_starts() == [] and bench.spawned() == [], "a machine was started despite the guard"
    assert not bench.pidfile.exists()
    status = bench.status()
    assert status["running"] == "false" and status["pid"] == "", status


# --- prepare -----------------------------------------------------------------------------------------------------

def test_prepare_creates_layout_and_manifest(bench) -> None:
    bench.ok("prepare", "yocto")
    rootfs_sha = _sha256(bench.rootfs_src)
    for name in ("Image", "rootfs.ext4", "SHA256SUMS"):
        assert (bench.b_dir / name).is_file(), name
    assert _mode(bench.b_dir / "Image") == 0o444 and _mode(bench.b_dir / "rootfs.ext4") == 0o444
    assert _sha256(bench.b_dir / "rootfs.ext4") == rootfs_sha
    assert rootfs_sha in (bench.b_dir / "SHA256SUMS").read_text(encoding="utf-8")
    for rel in ("disks/" + ROOT_OVERLAY, "disks/data.img", "manifest.json"):
        assert (bench.s_dir / rel).is_file(), rel
    for rel in ("state", "logs", "results"):
        assert (bench.s_dir / rel).is_dir(), rel
    assert (bench.disks / "data.img").stat().st_size == 32 * 1024 ** 3, "the data disk is not 32 GiB"
    # the root disk is an overlay on the immutable copy; the data disk a fresh ext4 labelled egw-data
    creates = [line.split() for line in bench.log() if line.startswith("qemu-img create")]
    assert len(creates) == 1, creates
    for token in ("-f", "qcow2", "-b", str(bench.b_dir / "rootfs.ext4"), "-F", "raw", str(bench.disks / ROOT_OVERLAY)):
        assert token in creates[0], (token, creates[0])
    mkfs = [line for line in bench.log() if line.startswith("mkfs.ext4 ")]
    assert len(mkfs) == 1 and "egw-data" in mkfs[0] and str(bench.disks / "data.img") in mkfs[0], mkfs
    manifest = json.loads(bench.manifest.read_text(encoding="utf-8"))
    assert {"scenario", "distro_label", "base", "qemu", "machine_args", "created_utc"} <= set(manifest), manifest
    assert manifest["scenario"] == "yocto" and manifest["distro_label"].startswith("Poky 5.0.19")
    assert isinstance(manifest["base"], dict) and rootfs_sha in list(_strings(manifest["base"])), manifest["base"]
    assert manifest["qemu"]["path"] == str(bench.bin / "qemu-system-aarch64"), manifest["qemu"]
    assert "8.2.7" in manifest["qemu"]["version"], manifest["qemu"]
    assert "cortex-a76" in json.dumps(manifest["machine_args"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest["created_utc"]), manifest["created_utc"]
    assert bench.qemu_starts() == [], "prepare started a machine"


def test_prepare_is_idempotent(bench) -> None:
    bench.ok("prepare", "yocto")
    watched = [bench.disks / ROOT_OVERLAY, bench.disks / "data.img", bench.manifest,
               bench.b_dir / "Image", bench.b_dir / "rootfs.ext4"]
    files_before = bench.files()
    mtimes_before = [p.stat().st_mtime_ns for p in watched]
    time.sleep(1.1)
    bench.ok("prepare", "yocto")
    assert bench.files() == files_before, "a second prepare created a file"
    assert [p.stat().st_mtime_ns for p in watched] == mtimes_before, "a second prepare rewrote a disk, a base or the manifest"
    assert bench.qemu_starts() == []


def test_prepare_refuses_missing_base(bench) -> None:
    bench.write_scenario(rootfs_src=bench.deploy / "missing.rootfs.ext4")
    result = bench.run("prepare", "yocto")
    assert result.returncode == 2, _report(result)
    assert "STOP:" in result.stderr and "missing.rootfs.ext4" in result.stderr, _report(result)
    assert not (bench.disks / ROOT_OVERLAY).exists() and not bench.manifest.exists()
    assert not (bench.b_dir / "rootfs.ext4").exists()
    assert bench.status()["prepared"] == "false"


# --- start -------------------------------------------------------------------------------------------------------

def test_start_refuses_other_qemu(bench) -> None:
    bench.ok("prepare", "yocto")
    other = "4242 /usr/bin/qemu-system-aarch64 -machine virt -m 8192"
    _assert_refused(bench, bench.run("start", "yocto", EGW_STUB_OTHER_QEMU=other))


def test_start_refuses_pilot_session(bench) -> None:
    bench.ok("prepare", "yocto")
    (bench.exec_dir / "current_session").write_text("s1\n", encoding="utf-8")
    _assert_refused(bench, bench.run("start", "yocto"))


@pytest.mark.parametrize("port", ["2222", "8883"])
def test_start_refuses_busy_port(bench, port) -> None:
    bench.ok("prepare", "yocto")
    busy = f"LISTEN 0 128 127.0.0.1:{port} 0.0.0.0:*"
    _assert_refused(bench, bench.run("start", "yocto", EGW_STUB_BUSY_PORTS=busy))


def test_start_writes_pid_and_status_running(bench) -> None:
    bench.ok("prepare", "yocto")
    bench.ok("start", "yocto")
    pid = bench.pid()
    assert _alive(pid) and _cmdline(pid)[0] == "qemu-system-aarch64"
    starts = bench.qemu_starts()
    assert len(starts) == 1, starts
    argv = starts[0]
    assert "-daemonize" in argv and argv[argv.index("-pidfile") + 1] == str(bench.pidfile), argv
    console = _serial_file(argv)
    assert console is not None and Path(console).is_relative_to(bench.s_dir / "logs") and Path(console).is_file(), argv
    joined = " ".join(argv)
    for token in ("-cpu cortex-a76", "-smp 4", "-m 8192", "hostfwd=tcp:127.0.0.1:2222-:22",
                  "hostfwd=tcp:127.0.0.1:8883-:8883", str(bench.disks / ROOT_OVERLAY), str(bench.disks / "data.img"),
                  str(bench.b_dir / "Image")):
        assert token in joined, (token, joined)
    status = bench.status()
    assert status["running"] == "true" and status["pid"] == str(pid) and status["prepared"] == "true", status
    assert status["lock_holder"] == "yocto" and float(status["started_uptime_s"]) > 0, status
    assert (bench.root / "lock" / "active" / "holder").read_text(encoding="utf-8").strip() == "yocto"
    assert (bench.s_dir / "state" / "argv.txt").is_file() and (bench.s_dir / "state" / "started").is_file()


def test_pid_file_naming_another_qemu_is_not_claimed(bench) -> None:
    """A pid reused by a QEMU that is not this scenario's (no -pidfile of ours in its argv) is never ours:
    status says not running, stop touches nothing and the foreign process lives on."""
    bench.ok("prepare", "yocto")
    foreign = subprocess.Popen(["qemu-system-aarch64", "-c", "import time\nwhile True:\n    time.sleep(3600)",
                                "-machine", "virt", "-pidfile", "/elsewhere/qemu.pid"], executable=sys.executable,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        bench.pidfile.write_text(f"{foreign.pid}\n", encoding="utf-8")
        assert _cmdline(foreign.pid)[0] == "qemu-system-aarch64"
        assert bench.status()["running"] == "false"
        result = bench.ok("stop", "yocto")
        assert "not running" in result.stdout
        assert "poweroff" not in bench.calls.read_text(encoding="utf-8") if bench.calls.exists() else True
        assert foreign.poll() is None, "the tool acted on a process that is not its guest"
    finally:
        foreign.kill()
        foreign.wait()


def test_zombie_counts_as_gone(bench) -> None:
    """A guest that exited but was not reaped (state Z) is gone: own_pid denies it and wait_gone returns at once."""
    bench.ok("prepare", "yocto")
    pid = os.fork()
    if pid == 0:  # pragma: no cover - the child exits immediately and is left unreaped
        os._exit(0)
    try:
        for _ in range(100):
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            if state == "Z":
                break
            time.sleep(0.05)
        assert state == "Z"
        bench.pidfile.write_text(f"{pid}\n", encoding="utf-8")
        assert bench.status()["running"] == "false"
        probe = bench.bin / "wait_gone_probe.sh"
        probe.write_text('. "$1/lib.sh"; scenario_load yocto; wait_gone "$2" 10\n', encoding="utf-8")
        t0 = time.monotonic()
        result = bench.run_script(probe, str(COMPARE_DIR), str(pid))
        assert result.returncode == 0, _report(result)
        assert time.monotonic() - t0 < 5, "wait_gone waited for a zombie"
    finally:
        os.waitpid(pid, 0)


def test_start_twice_is_noop(bench) -> None:
    bench.ok("prepare", "yocto")
    bench.ok("start", "yocto")
    pid = bench.pid()
    bench.ok("start", "yocto")
    assert bench.pid() == pid and len(bench.qemu_starts()) == 1 and bench.spawned() == [pid]
    assert bench.status()["pid"] == str(pid)


def test_start_reports_a_machine_that_failed_to_start(bench) -> None:
    bench.ok("prepare", "yocto")
    result = bench.run("start", "yocto", EGW_STUB_QEMU_FAIL="1")
    assert result.returncode == 5, _report(result)
    assert "STOP:" in result.stderr, _report(result)
    assert bench.spawned() == [] and (not bench.pidfile.exists() or bench.pidfile.read_text().strip() == "")
    status = bench.status()
    assert status["running"] == "false" and status["pid"] == "" and status["lock_holder"] == "", status


# --- status and manifest -----------------------------------------------------------------------------------------

def test_status_before_prepare_is_honest(bench) -> None:
    status = bench.status()
    assert status["scenario"] == "yocto" and status["prepared"] == "false" and status["running"] == "false", status
    assert status["pid"] == "" and status["lock_holder"] == "", status


def test_status_after_prepare_names_the_artefacts(bench) -> None:
    bench.ok("prepare", "yocto")
    status = bench.status()
    assert status["prepared"] == "true" and status["running"] == "false" and status["pid"] == "", status
    assert Path(status["root_disk"]).resolve() == (bench.disks / ROOT_OVERLAY).resolve(), status
    assert Path(status["data_disk"]).resolve() == (bench.disks / "data.img").resolve(), status
    assert Path(status["manifest"]).resolve() == bench.manifest.resolve(), status
    manifest = json.loads(bench.manifest.read_text(encoding="utf-8"))
    assert re.fullmatch(r"[0-9a-f]{64}", status["base_sha256"]), status
    assert status["base_sha256"] in list(_strings(manifest["base"])), (status, manifest["base"])
    result = bench.ok("manifest", "yocto")
    assert Path(result.stdout.strip()).resolve() == bench.manifest.resolve(), _report(result)


# --- stop --------------------------------------------------------------------------------------------------------

def test_stop_when_not_running_does_nothing(bench) -> None:
    bench.ok("prepare", "yocto")
    result = bench.ok("stop", "yocto")
    assert "not running" in result.stdout + result.stderr, _report(result)
    assert not any(line.startswith("ssh ") for line in bench.log()), bench.log()
    assert bench.status()["running"] == "false"


def test_stop_powers_off_and_clears(bench) -> None:
    bench.ok("prepare", "yocto")
    bench.ok("start", "yocto")
    pid = bench.pid()
    bench.ok("stop", "yocto")
    poweroffs = [line for line in bench.log() if line.startswith("ssh ") and "poweroff" in line]
    assert poweroffs and "egw@127.0.0.1" in poweroffs[0], bench.log()
    assert not _alive(pid)
    assert not bench.pidfile.exists(), "the pid file was kept after a controlled stop"
    assert not (bench.root / "lock" / "active").exists(), "the lock was kept after a controlled stop"
    status = bench.status()
    assert status["running"] == "false" and status["pid"] == "" and status["lock_holder"] == "", status
    assert status["prepared"] == "true", status
    # a stop preserves the disks
    assert (bench.disks / ROOT_OVERLAY).is_file() and (bench.disks / "data.img").is_file()


def test_stop_never_kills_when_guest_ignores_poweroff(bench) -> None:
    bench.ok("prepare", "yocto")
    bench.ok("start", "yocto")
    pid = bench.pid()
    t0 = time.monotonic()
    result = bench.run("stop", "yocto", EGW_STUB_SSH_IGNORE_POWEROFF="1")
    assert result.returncode == 5, _report(result)
    assert "STOP:" in result.stderr, _report(result)
    assert time.monotonic() - t0 >= 2.5, "the stop did not wait for the guest"
    assert any("poweroff" in line for line in bench.log() if line.startswith("ssh ")), bench.log()
    assert _alive(pid), "the tool killed the guest"
    assert bench.pid() == pid, "the pid file was not kept"
    status = bench.status()
    assert status["running"] == "true" and status["pid"] == str(pid), status


# --- destroy -----------------------------------------------------------------------------------------------------

def test_destroy_refuses_while_running(bench) -> None:
    bench.ok("prepare", "yocto")
    bench.ok("start", "yocto")
    pid = bench.pid()
    result = bench.run("destroy", "yocto")
    assert result.returncode == 5, _report(result)
    assert "STOP:" in result.stderr, _report(result)
    assert _alive(pid) and bench.pid() == pid
    for rel in ("disks/" + ROOT_OVERLAY, "disks/data.img", "manifest.json", "state/argv.txt"):
        assert (bench.s_dir / rel).is_file(), rel
    assert bench.status()["running"] == "true"


def test_destroy_keeps_bases_and_results(bench) -> None:
    bench.ok("prepare", "yocto")
    bench.ok("start", "yocto")
    bench.ok("stop", "yocto")
    kept = bench.s_dir / "results" / "r01" / "check.json"
    kept.parent.mkdir(parents=True)
    kept.write_text('{"ok": true}\n', encoding="utf-8")
    bases = {p.name: _sha256(p) for p in bench.b_dir.iterdir()}
    logs_before = {p.name for p in (bench.s_dir / "logs").iterdir()}
    bench.ok("destroy", "yocto")
    assert not (bench.disks / ROOT_OVERLAY).exists() and not (bench.disks / "data.img").exists()
    state = bench.s_dir / "state"
    assert not state.exists() or [p for p in state.rglob("*") if p.is_file()] == [], "state files were kept"
    assert {p.name: _sha256(p) for p in bench.b_dir.iterdir()} == bases, "a base changed"
    assert _mode(bench.b_dir / "rootfs.ext4") == 0o444 and _mode(bench.b_dir / "Image") == 0o444
    assert kept.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert logs_before <= {p.name for p in (bench.s_dir / "logs").iterdir()}
    assert json.loads(bench.manifest.read_text(encoding="utf-8"))["scenario"] == "yocto"
    status = bench.status()
    assert status["running"] == "false" and status["prepared"] == "false", status
    bench.ok("destroy", "yocto")
    assert {p.name: _sha256(p) for p in bench.b_dir.iterdir()} == bases


# --- secrets, usage, static checks -------------------------------------------------------------------------------

def test_no_secret_in_status_or_manifest(bench) -> None:
    bench.ok("prepare", "yocto")
    bench.ok("start", "yocto")
    status_out = bench.ok("status", "yocto").stdout
    manifest_out = bench.ok("manifest", "yocto").stdout
    bench.run("stop", "yocto")
    assert SECRET not in status_out and SECRET not in manifest_out
    leaks = [str(p) for p in bench.root.rglob("*")
             if p.is_file() and p.stat().st_size <= 16 * 1024 ** 2 and SECRET.encode() in p.read_bytes()]
    assert leaks == [], leaks


@pytest.mark.parametrize("args", [(), ("start",), ("reboot", "yocto"), ("start", "fedora")])
def test_usage_and_unknown_scenario_exit_2(bench, args) -> None:
    result = bench.run(*args)
    assert result.returncode == 2, _report(result)
    assert bench.qemu_starts() == [] and not bench.pidfile.exists()


def test_shellcheck_clean() -> None:
    shellcheck = shutil.which("shellcheck") or str(Path(sys.executable).parent / "shellcheck")
    if not Path(shellcheck).is_file():
        pytest.skip("shellcheck is not installed")
    scripts = [str(COMPARE_DIR / name) for name in ("compare_env.sh", "lib.sh", "tf.sh")]
    result = subprocess.run([shellcheck, "-S", "error", *scripts], capture_output=True, text=True)
    assert result.returncode == 0, _report(result)


def test_terraform_fmt_check() -> None:
    terraform = shutil.which("terraform")
    if terraform is None:
        pytest.skip("terraform is not installed")
    result = subprocess.run([terraform, "fmt", "-check", "-diff", "-recursive", str(TF_DIR)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, _report(result)


def test_terraform_validate() -> None:
    terraform = shutil.which("terraform")
    if terraform is None or os.environ.get("EGW_COMPARE_TF_INIT") != "1":
        pytest.skip("needs terraform and EGW_COMPARE_TF_INIT=1 (init downloads the pinned providers)")
    env = {**os.environ, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0"}
    init = subprocess.run([terraform, f"-chdir={TF_DIR}", "init", "-backend=false", "-input=false"],
                          capture_output=True, text=True, env=env, timeout=600)
    assert init.returncode == 0, _report(init)
    result = subprocess.run([terraform, f"-chdir={TF_DIR}", "validate"], capture_output=True, text=True, env=env,
                            timeout=120)
    assert result.returncode == 0, _report(result)
