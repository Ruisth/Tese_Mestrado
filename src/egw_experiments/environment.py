"""Environment capture for run manifests (plan 5.1/5.8, audit 9.2).

Two distinct environments are recorded per run (audit recommendation:
"sut_environment.json capturado na VM ARM; loadgen_environment.json
capturado no host do simulador; ambos referenciados pelo manifest"):

- ``loadgen_environment.json`` — captured HERE, on the host running the
  harness and the simulator (the load generator, which runs OFF the ARM VM
  per plan 5.1). This is what :func:`write_loadgen_environment` writes.
- ``sut_environment.json`` — captured ON the ARM VM (the system under
  test) by ``src/deployment/scripts/capture-sut-environment.sh`` and
  fetched to the harness host; the runner ingests it with
  ``--sut-env-from``. It carries the plan 5.1 normative fields: provider,
  region, instance type and the shared-vCPU caveat (``EGW_PROVIDER``,
  ``EGW_REGION``, ``EGW_INSTANCE_TYPE``, ``EGW_SHARED_VCPU_NOTE``), plus
  ``nproc`` which the analysis uses to normalize docker-stats CPU
  percentages to host-level utilization.

The load-generator capture records platform metadata (OS, kernel via
``platform.uname``, CPU count, Python version) and, best-effort, the Docker
client/server versions via subprocess. Everything is optional-degrading: a
missing docker CLI never fails the capture, it is simply recorded as
unavailable.

The G4 core provenance (plan 655-661) adds a third record and the checks
that bind the three together:

- ``hypervisor_environment.json`` — also captured HERE, by reading the
  ``/proc`` of the load-generator host, where QEMU runs beside the harness:
  the single ``qemu-system-aarch64`` process, its exact command line, the
  identity of its executable, kernel and rootfs, the accelerator derived
  from the command line and the process, whether the load generator is
  co-located and whether the generator's target is this guest. One snapshot
  at the start of the run and one at its end
  (:func:`capture_hypervisor_snapshot`, :func:`write_hypervisor_environment`).
- The execution mode is DECLARED by the operator and never inferred:
  :func:`provenance_checks` compares the declaration with the three records,
  and :func:`provenance_problems` turns each failed check into one validity
  reason. The guest's free-text labels only corroborate.

Every ``/proc`` read goes through a ``proc_root`` argument, so the tests read
a fake tree. A value that cannot be read is recorded as null with the reason
in the snapshot's ``problems``; nothing is guessed.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from .checksums import sha256_file

#: File names inside a raw run directory (audit 9.2).
SUT_ENVIRONMENT_FILENAME = "sut_environment.json"
LOADGEN_ENVIRONMENT_FILENAME = "loadgen_environment.json"
HYPERVISOR_ENVIRONMENT_FILENAME = "hypervisor_environment.json"

#: The execution modes an operator may declare (runbook section 9, item 1:
#: docs/setup/qemu_integrated_gateway.md). The declaration has no default;
#: only ``tcg-emulated`` can be evidenced by this harness, which has no
#: native provenance capture.
EXECUTION_MODES: tuple[str, ...] = ("tcg-emulated", "native-kvm", "native-metal")

#: The label stamped beside each mode. The emulated one is the plan's
#: wording verbatim (INTEGRATED_DEVELOPMENT_PLAN_2026.md, section 4.3,
#: condition 1 "Labelling", lines 590-591).
EXECUTION_MODE_LABELS: dict[str, str] = {
    "tcg-emulated": "ARM64 emulated by QEMU/TCG on an x86-64 host",
    "native-kvm": "ARM64 native under KVM",
    "native-metal": "ARM64 native, bare metal",
}

#: The rule the provenance checks implement; recorded in the manifest.
PROVENANCE_RULE = "G4 core provenance (plan 655-661)"

#: The shape of ``hypervisor_environment.json``.
HYPERVISOR_RECORD_VERSION = 1
HYPERVISOR_CAPTURE = "harness /proc read on the load-generator host"

#: Where the host's process table and kernel facts are read.
PROC_ROOT = Path("/proc")

#: The guest's emulator: the executable at the start of the command line,
#: as the session drivers find it (QEMU_EXE_RE, tools/session/guest_common.sh).
QEMU_EXECUTABLE = "qemu-system-aarch64"
KVM_DEVICE = "/dev/kvm"
QEMU_VERSION_TIMEOUT_S = 10.0

#: Command-line flags whose value is never written to a record (plan 9.2).
SECRET_FLAGS: tuple[str, ...] = ("--password",)
REDACTED = "<redacted>"

#: The guest record's free-text labels (capture-sut-environment.sh) and the
#: case-insensitive fragments by which one states emulation.
EMULATION_LABEL_KEYS: tuple[str, ...] = (
    "provider",
    "region",
    "instance_type",
    "shared_vcpu_note",
)
EMULATION_LABEL_TOKENS: tuple[str, ...] = ("emulat", "tcg")

#: The hostname of the emulated integrated guest, chosen so that emulated
#: and native evidence can never be confused (2026-09-17 image audit).
INTEGRATED_GUEST_NODE = "egw-qemu-integrated"

NO_NATIVE_CAPTURE = "no native provenance capture exists in this harness"

#: Required content of a usable sut_environment.json (work order P1 fix 4).
#: Presence of the file alone is NOT enough: a timed run whose SUT manifest
#: cannot identify the host, its CPU count or its OS describes nothing and
#: is marked validity 'invalid' (override: --allow-missing-sut-env, which
#: records a protocol deviation). Each entry maps a logical requirement to
#: the accepted JSON keys (the first non-empty one wins):
#:
#: - ``node/hostname``: the SUT's hostname — also cross-checked against the
#:   ``host`` provenance column of resources.csv at ingest time;
#: - ``nproc``: positive integer — required by the audit 9.7 host-level CPU
#:   normalization;
#: - ``os identification``: uname/os-release identification of the SUT
#:   (``uname_a``/``os_pretty_name`` as written by
#:   deployment/scripts/capture-sut-environment.sh; ``uname``/``os``/
#:   ``kernel_release`` accepted for hand-written manifests).
REQUIRED_SUT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("node/hostname", ("node", "hostname")),
    ("nproc", ("nproc",)),
    (
        "os identification",
        ("uname_a", "os_pretty_name", "uname", "os", "kernel_release"),
    ),
)


def utc_now_iso() -> str:
    """RFC 3339 UTC timestamp with Z suffix, millisecond resolution."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _run_capture(cmd: list[str], timeout_s: float = 10.0) -> str | None:
    """Run a command and return stripped stdout, or None on any failure."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def redact_argv(
    argv: Sequence[str], secret_flags: tuple[str, ...] = SECRET_FLAGS
) -> list[str]:
    """A copy of ``argv`` with the value of every secret flag replaced by
    ``"<redacted>"``, in both forms ``--password VALUE`` and
    ``--password=VALUE`` (the manifest's echo redacts the same value, plan
    9.2). The caller's list is not changed; a secret flag with nothing after
    it is kept as it is."""
    out: list[str] = []
    redact_next = False
    for arg in argv:
        if redact_next:
            out.append(REDACTED)
            redact_next = False
            continue
        flag, eq, _ = arg.partition("=")
        if eq and flag in secret_flags:
            out.append(f"{flag}={REDACTED}")
            continue
        out.append(arg)
        redact_next = arg in secret_flags
    return out


# ---------------------------------------------------------------------------
# /proc readers: each returns (value, None) or (None, the reason)
# ---------------------------------------------------------------------------


def _proc_value(
    path: Path, parse: Callable[[str], Any], what: str
) -> tuple[Any, str | None]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, f"cannot read {path}: {exc}"
    value = parse(text)
    if value is None:
        return None, f"no {what} in {path}"
    return value, None


def _parse_boot_id(text: str) -> str | None:
    return text.strip() or None


def _parse_mem_total_kb(text: str) -> int | None:
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            fields = line.split()
            if len(fields) >= 2 and fields[1].isdigit():
                return int(fields[1])
    return None


def _parse_cpu_model(text: str) -> str | None:
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "model name" and value.strip():
            return value.strip()
    return None


def _parse_btime(text: str) -> int | None:
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == "btime" and fields[1].isdigit():
            return int(fields[1])
    return None


def _parse_starttime(text: str) -> int | None:
    # "pid (comm) state ppid ...": the name may hold spaces and ')', so the
    # fields are read after the LAST ')'. The start time (clock ticks after
    # the boot) is field 22 of proc(5), the 20th after the name.
    _, sep, rest = text.rpartition(")")
    fields = rest.split()
    if not sep or len(fields) < 20 or not fields[19].isdigit():
        return None
    return int(fields[19])


def _cpu_affinity_count() -> int | None:
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is None:
        return None
    try:
        return len(getaffinity(0))
    except OSError:
        return None


def _clock_ticks_per_second() -> int | None:
    try:
        return int(os.sysconf("SC_CLK_TCK"))
    except (AttributeError, ValueError, OSError):
        return None


def capture_host_record(
    proc_root: Path = PROC_ROOT, problems: list[str] | None = None
) -> dict[str, Any]:
    """The identity and size of the host the harness runs on: uname, the
    boot id, the CPU count and the CPUs this process may use, ``MemTotal``,
    the first CPU model name, and whether the kernel is WSL's. A value that
    cannot be read is None, and the reason is appended to ``problems`` (when
    given) as ``host.<field>: <reason>``."""
    if problems is None:
        problems = []
    uname = platform.uname()
    boot_id, boot_problem = _proc_value(
        proc_root / "sys" / "kernel" / "random" / "boot_id", _parse_boot_id, "boot id"
    )
    mem_total_kb, mem_problem = _proc_value(
        proc_root / "meminfo", _parse_mem_total_kb, "MemTotal"
    )
    cpu_model, model_problem = _proc_value(
        proc_root / "cpuinfo", _parse_cpu_model, "model name"
    )
    affinity = _cpu_affinity_count()
    for field, problem in (
        ("boot_id", boot_problem),
        ("mem_total_kb", mem_problem),
        ("cpu_model", model_problem),
    ):
        if problem:
            problems.append(f"host.{field}: {problem}")
    if affinity is None:
        problems.append("host.cpu_affinity_count: the CPU affinity cannot be read here")
    return {
        "node": uname.node,
        "kernel_release": uname.release,
        "machine": uname.machine,
        "boot_id": boot_id,
        "cpu_count": os.cpu_count(),
        "cpu_affinity_count": affinity,
        "mem_total_kb": mem_total_kb,
        "cpu_model": cpu_model,
        "wsl": "microsoft" in uname.release.lower(),
    }


def capture_environment(
    *,
    simulator_argv: Sequence[str] | None = None,
    warmup_argv: Sequence[str] | None = None,
    proc_root: Path = PROC_ROOT,
) -> dict[str, Any]:
    """Capture load-generator host metadata as a JSON-safe dict.

    ``simulator_argv``/``warmup_argv`` are the simulator invocations of the
    measured run and of the warm-up, recorded with the password redacted;
    each is null when not given (``warmup_argv`` when there is no warm-up).
    """
    uname = platform.uname()
    # Host facts read from /proc; null when unreadable (this record keeps
    # no problem list: the hypervisor snapshot names the reasons).
    host = capture_host_record(proc_root)
    return {
        # This file describes the LOAD GENERATOR (harness+simulator host),
        # never the system under test (audit 9.2).
        "role": "loadgen",
        "captured_utc": utc_now_iso(),
        "platform": platform.platform(),
        "system": uname.system,
        "node": uname.node,
        # Kernel release/version as reported by uname (e.g. Linux kernel
        # release on the ARM64 VM; Windows build on a dev host).
        "kernel_release": uname.release,
        "kernel_version": uname.version,
        "machine": uname.machine,
        "processor": uname.processor,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "cpu_count": os.cpu_count(),
        # Best-effort; None when the docker CLI or daemon is unavailable.
        "docker_client_version": _run_capture(["docker", "--version"]),
        "docker_server_version": _run_capture(
            ["docker", "version", "--format", "{{.Server.Version}}"]
        ),
        # G4 core provenance: the boot id binds this record to the
        # hypervisor record (co-location), and the invocations say exactly
        # what the generator ran.
        "boot_id": host["boot_id"],
        "cpu_affinity_count": host["cpu_affinity_count"],
        "mem_total_kb": host["mem_total_kb"],
        "cpu_model": host["cpu_model"],
        "python_executable": sys.executable,
        "simulator_argv": (
            redact_argv(simulator_argv) if simulator_argv is not None else None
        ),
        "warmup_argv": redact_argv(warmup_argv) if warmup_argv is not None else None,
    }


def write_loadgen_environment(
    path: str | Path,
    *,
    simulator_argv: Sequence[str] | None = None,
    warmup_argv: Sequence[str] | None = None,
    proc_root: Path = PROC_ROOT,
) -> Path:
    """Capture the load-generator environment and write it to ``path``
    (normally ``<run_dir>/loadgen_environment.json``)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    env = capture_environment(
        simulator_argv=simulator_argv, warmup_argv=warmup_argv, proc_root=proc_root
    )
    path.write_text(
        json.dumps(env, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


# Backwards-compatible alias (pre-audit name). The file it should target is
# now loadgen_environment.json; do not use it for the SUT.
write_environment = write_loadgen_environment


def read_environment_record(
    run_dir: str | Path, filename: str
) -> dict[str, Any] | None:
    """Read one environment record (``filename``) from a run directory.

    Returns the parsed dict, or None when the file is absent, unreadable or
    not a JSON object (the caller decides whether that invalidates the run).
    """
    path = Path(run_dir) / filename
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def read_sut_environment(run_dir: str | Path) -> dict[str, Any] | None:
    """Read ``sut_environment.json`` from a run directory.

    Returns the parsed dict, or None when the file is absent or unreadable
    (the caller decides whether that invalidates the run).
    """
    return read_environment_record(run_dir, SUT_ENVIRONMENT_FILENAME)


# ---------------------------------------------------------------------------
# The QEMU process: discovery, command line, snapshot
# ---------------------------------------------------------------------------


def find_qemu_processes(
    proc_root: Path = PROC_ROOT, executable: str = QEMU_EXECUTABLE
) -> tuple[list[int], str | None]:
    """The pids whose ``argv[0]`` basename is ``executable``, ascending, and
    an error when the scan could not answer.

    The rule is the session drivers' (``QEMU_EXE_RE``,
    tools/session/guest_common.sh): the EXECUTABLE at the start of the
    command line. A shell whose command line merely mentions the name is not
    QEMU, and the process name Linux keeps (15 characters) can never hold
    the 19-character executable name. A process that ends during the scan is
    skipped. The error is None when every command line was read; otherwise
    it says why the answer is indeterminate, beside the pids found so far.
    """
    try:
        pids_listed = sorted(
            int(entry.name)
            for entry in proc_root.iterdir()
            if entry.name.isascii() and entry.name.isdigit()
        )
    except OSError as exc:
        return [], f"cannot list {proc_root}: {exc}"
    found: list[int] = []
    unreadable: list[int] = []
    for pid in pids_listed:
        try:
            raw = (proc_root / str(pid) / "cmdline").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            continue  # the process ended during the scan
        except OSError:
            unreadable.append(pid)
            continue
        argv0 = raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")
        if argv0.rsplit("/", 1)[-1] == executable:
            found.append(pid)
    if unreadable:
        listed = ", ".join(str(pid) for pid in unreadable)
        return found, (
            f"the command lines of {len(unreadable)} process(es) could not be "
            f"read (pids {listed}); the scan is indeterminate"
        )
    return found, None


def read_argv(pid: int, proc_root: Path = PROC_ROOT) -> tuple[list[str], str]:
    """The argv the kernel holds for ``pid`` (``/proc/<pid>/cmdline`` split
    on NUL) and the SHA-256 of those raw bytes. Raises OSError when the file
    cannot be read."""
    raw = (proc_root / str(pid) / "cmdline").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    body = raw[:-1] if raw.endswith(b"\0") else raw
    argv = (
        [part.decode("utf-8", errors="backslashreplace") for part in body.split(b"\0")]
        if raw
        else []
    )
    return argv, digest


#: The QEMU options whose value the checks read; every other option is
#: stepped over one token at a time.
_QEMU_VALUE_OPTIONS = frozenset(
    {"-machine", "-M", "-cpu", "-smp", "-m", "-kernel", "-append", "-drive",
     "-netdev", "-nic", "-net", "-accel"}
)


def _qemu_option_items(value: str) -> list[tuple[str | None, str]]:
    """Split a QEMU option value (``key=value,...``, where ``,,`` is a
    literal comma) into (key, value) pairs; an element without ``=`` has the
    key None (the option's implied key, e.g. the machine type)."""
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == ",":
            if value[i + 1:i + 2] == ",":
                buf.append(",")
                i += 2
                continue
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    items: list[tuple[str | None, str]] = []
    for part in parts:
        if not part:
            continue
        key, eq, val = part.partition("=")
        items.append((key, val) if eq else (None, part))
    return items


def _port_number(text: str) -> int | None:
    return int(text) if text.isascii() and text.isdigit() else None


def _parse_hostfwd(rule: str) -> dict[str, Any]:
    """One ``hostfwd=[tcp|udp]:[hostaddr]:hostport-[guestaddr]:guestport``
    rule; the fields are None when the rule does not have that form."""
    entry: dict[str, Any] = {
        "rule": rule,
        "protocol": None,
        "host_addr": None,
        "host_port": None,
        "guest_addr": None,
        "guest_port": None,
    }
    host_part, sep, guest_part = rule.partition("-")
    protocol, sep_proto, host_rest = host_part.partition(":")
    host_addr, sep_host, host_port = host_rest.rpartition(":")
    guest_addr, sep_guest, guest_port = guest_part.rpartition(":")
    if not (sep and sep_proto and sep_host and sep_guest):
        return entry
    entry.update(
        protocol=protocol.lower(),
        host_addr=host_addr,
        host_port=_port_number(host_port),
        guest_addr=guest_addr,
        guest_port=_port_number(guest_port),
    )
    return entry


def parse_qemu_argv(argv: Sequence[str]) -> dict[str, Any]:
    """The facts of a QEMU command line the provenance checks read.

    ``machine`` (the machine type), ``cpu``, ``smp`` (the CPU count as an
    int, or None), ``memory`` (the ``-m`` value as given), ``kernel``,
    ``append``, ``drives`` (every ``-drive file=``), ``hostfwd`` (every
    forward of ``-netdev``/``-nic``/``-net``), ``accel_requests`` (from
    ``-enable-kvm``, ``-accel`` and ``-machine accel=``, in order) and
    ``kvm_requested``. Options may be written with one or two dashes; a
    later value of the same option wins, as in QEMU.
    """
    parsed: dict[str, Any] = {
        "machine": None,
        "cpu": None,
        "smp": None,
        "memory": None,
        "kernel": None,
        "append": None,
        "drives": [],
        "hostfwd": [],
        "kvm_requested": False,
        "accel_requests": [],
    }
    i = 1
    while i < len(argv):
        token = argv[i]
        name = "-" + token.lstrip("-") if token.startswith("-") else None
        if name == "-enable-kvm":
            parsed["accel_requests"].append("kvm")
            i += 1
            continue
        if name not in _QEMU_VALUE_OPTIONS or i + 1 >= len(argv):
            i += 1
            continue
        value = argv[i + 1]
        i += 2
        items = _qemu_option_items(value)
        if name in ("-machine", "-M"):
            for key, val in items:
                if key in (None, "type"):
                    parsed["machine"] = val
                elif key == "accel":
                    parsed["accel_requests"].extend(a for a in val.split(":") if a)
        elif name == "-accel":
            parsed["accel_requests"].extend(
                val for key, val in items if key in (None, "accel") and val
            )
        elif name == "-smp":
            for key, val in items:
                if key in (None, "cpus"):
                    parsed["smp"] = _port_number(val)
                    break
        elif name == "-cpu":
            parsed["cpu"] = value
        elif name == "-m":
            parsed["memory"] = value
        elif name == "-kernel":
            parsed["kernel"] = value
        elif name == "-append":
            parsed["append"] = value
        elif name == "-drive":
            parsed["drives"].extend(val for key, val in items if key == "file")
        else:  # -netdev, -nic, -net
            parsed["hostfwd"].extend(
                _parse_hostfwd(val) for key, val in items if key == "hostfwd"
            )
    parsed["kvm_requested"] = "kvm" in parsed["accel_requests"]
    return parsed


def _qemu_version_line(exe_path: str) -> tuple[str | None, str | None]:
    """The first line ``<exe_path> --version`` prints (no shell, stdin from
    the null device, a 10 s timeout), or None and the reason."""
    try:
        proc = subprocess.run(
            [exe_path, "--version"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=QEMU_VERSION_TIMEOUT_S,
            check=False,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return None, f"{exe_path} --version could not be run: {exc}"
    if proc.returncode != 0:
        return None, f"{exe_path} --version exited with status {proc.returncode}"
    for line in proc.stdout.splitlines():
        if line.strip():
            return line.strip(), None
    return None, f"{exe_path} --version printed nothing"


def _is_x86_64(machine: Any) -> bool:
    return isinstance(machine, str) and machine.lower() in ("x86_64", "amd64")


def _derive_accelerator(
    parsed: dict[str, Any],
    kvm_device_open: bool | None,
    host_machine: Any,
    target_arch: str | None,
) -> tuple[str | None, list[str], str | None]:
    """(accelerator, basis, problem). The accelerator is derived from the
    command line and the process, not read from QEMU (no monitor socket):
    ``kvm`` when /dev/kvm is open in the process; ``tcg`` only when KVM is
    not requested and either /dev/kvm is seen not open or the host cannot
    run the target under KVM (an x86-64 host, an aarch64 target); None
    otherwise."""
    requested = parsed.get("accel_requests") or []
    unknown = sorted({a for a in requested if a not in ("tcg", "kvm")})
    if unknown:
        return None, [], (
            f"accelerator(s) {', '.join(unknown)} requested in the argv; only "
            "tcg and kvm are recognised"
        )
    if kvm_device_open is True:
        basis = [f"{KVM_DEVICE} is open in the QEMU process"]
        if parsed.get("kvm_requested"):
            basis.append("KVM is requested in the argv")
        return "kvm", basis, None
    if parsed.get("kvm_requested"):
        return None, [], (
            f"KVM is requested in the argv but {KVM_DEVICE} was not seen open "
            "in the QEMU process; the accelerator is not determined"
        )
    basis = [
        "KVM is not requested in the argv (no -enable-kvm, -accel kvm or accel=kvm)"
    ]
    if "tcg" in requested:
        basis.append("TCG is requested in the argv")
    if kvm_device_open is False:
        basis.append(f"{KVM_DEVICE} is not open in the QEMU process")
    cross = _is_x86_64(host_machine) and target_arch == "aarch64"
    if cross:
        basis.append(
            f"cross-architecture: a {host_machine} host cannot run an "
            f"{target_arch} guest under KVM"
        )
    if kvm_device_open is False or cross:
        return "tcg", basis, None
    return None, [], (
        "the QEMU process's file descriptors could not be read and the host "
        "could run the target under KVM; the accelerator is not determined"
    )


def _iso_utc(epoch_s: int, ticks: int, hz: int) -> str:
    stamp = datetime.fromtimestamp(epoch_s, timezone.utc) + timedelta(
        microseconds=ticks * 1_000_000 // hz
    )
    return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _empty_qemu_record() -> dict[str, Any]:
    return {
        "found": 0,
        "pids": [],
        "error": None,
        "pid": None,
        "starttime_ticks": None,
        "start_utc": None,
        "exe_path": None,
        "exe_sha256": None,
        "version_line": None,
        "argv": None,
        "argv_sha256": None,
        "parsed": None,
        "kernel_sha256": None,
        "rootfs_path": None,
        "rootfs_image_name": None,
        "kvm_device_open": None,
        "accelerator": None,
        "accelerator_basis": [],
        "target_arch": None,
    }


def _capture_qemu(
    proc_root: Path, host_machine: Any, problems: list[str]
) -> dict[str, Any]:
    qemu = _empty_qemu_record()
    pids, error = find_qemu_processes(proc_root)
    qemu["found"] = len(pids)
    qemu["pids"] = pids
    if error is None and not pids:
        error = f"no {QEMU_EXECUTABLE} process found"
    elif error is None and len(pids) > 1:
        listed = ", ".join(str(pid) for pid in pids)
        error = (
            f"{len(pids)} {QEMU_EXECUTABLE} processes found (pids {listed}); "
            "none is chosen"
        )
    if error is not None:
        qemu["error"] = error
        problems.append(f"qemu: {error}")
        return qemu

    pid = pids[0]
    pid_dir = proc_root / str(pid)
    qemu["pid"] = pid

    def note(field: str, problem: str) -> None:
        problems.append(f"qemu.{field}: {problem}")

    # The process's identity: its start, in clock ticks after the boot and
    # in UTC (btime + ticks / SC_CLK_TCK).
    ticks, problem = _proc_value(
        pid_dir / "stat", _parse_starttime, "start time (field 22)"
    )
    qemu["starttime_ticks"] = ticks
    if problem:
        note("starttime_ticks", problem)
        note("start_utc", "no process start time")
    else:
        btime, problem = _proc_value(proc_root / "stat", _parse_btime, "btime")
        hz = _clock_ticks_per_second()
        if problem:
            note("start_utc", problem)
        elif not hz:
            note("start_utc", "the clock tick rate (SC_CLK_TCK) cannot be read")
        else:
            qemu["start_utc"] = _iso_utc(btime, ticks, hz)

    # The exact command line the kernel holds (not runqemu's print of it).
    parsed: dict[str, Any] | None = None
    try:
        argv, digest = read_argv(pid, proc_root)
    except OSError as exc:
        note("argv", f"cannot read {pid_dir / 'cmdline'}: {exc}")
    else:
        parsed = parse_qemu_argv(argv)
        qemu["argv"] = argv
        qemu["argv_sha256"] = digest
        qemu["parsed"] = parsed
        name = argv[0].rsplit("/", 1)[-1] if argv else ""
        if name.startswith("qemu-system-"):
            qemu["target_arch"] = name[len("qemu-system-"):]

    # The executable the process runs, hashed through /proc/<pid>/exe (the
    # running binary even if the file on disk was replaced since), and the
    # version line of the file at that path.
    exe = pid_dir / "exe"
    try:
        qemu["exe_path"] = os.readlink(exe)
    except OSError as exc:
        note("exe_path", f"cannot read the link {exe}: {exc}")
    try:
        qemu["exe_sha256"] = sha256_file(exe)
    except OSError as exc:
        note("exe_sha256", f"cannot read {exe}: {exc}")
    if qemu["exe_path"]:
        line, problem = _qemu_version_line(qemu["exe_path"])
        qemu["version_line"] = line
        if problem:
            note("version_line", problem)
    else:
        note("version_line", "no executable path to run --version on")

    # The image: the kernel file hashed as it is on disk now, and the rootfs
    # drive named after the Yocto image (<image>-<machine>.rootfs-<date>.<type>);
    # the rootfs is booted in place and changes, so it is named, not hashed.
    if parsed is None:
        note("kernel_sha256", "no command line was read")
        note("rootfs_path", "no command line was read")
    else:
        kernel = parsed["kernel"]
        if not kernel:
            note("kernel_sha256", "no -kernel in the command line")
        elif not kernel.startswith("/"):
            note("kernel_sha256", f"the -kernel path {kernel!r} is relative")
        else:
            try:
                qemu["kernel_sha256"] = sha256_file(kernel)
            except OSError as exc:
                note("kernel_sha256", f"cannot read {kernel}: {exc}")
        rootfs = [d for d in parsed["drives"] if ".rootfs" in d.rsplit("/", 1)[-1]]
        if len(rootfs) == 1:
            base = rootfs[0].rsplit("/", 1)[-1]
            stem, dot, suffix = base.rpartition(".")
            qemu["rootfs_path"] = rootfs[0]
            # The image name is the file name without its type suffix.
            keep_whole = not (dot and stem) or "rootfs" in suffix
            qemu["rootfs_image_name"] = base if keep_whole else stem
        elif not rootfs:
            note("rootfs_path", "no -drive file is named as a rootfs image")
        else:
            note(
                "rootfs_path",
                f"{len(rootfs)} -drive files are named as a rootfs image "
                f"({', '.join(rootfs)}); none is chosen",
            )

    # The accelerator: whether /dev/kvm is open in the process, and the
    # command line's requests.
    fd_dir = pid_dir / "fd"
    try:
        fd_links = list(fd_dir.iterdir())
    except OSError as exc:
        note("kvm_device_open", f"cannot list {fd_dir}: {exc}")
    else:
        qemu["kvm_device_open"] = False
        for link in fd_links:
            try:
                target = os.readlink(link)
            except OSError:
                continue  # closed during the scan
            if target == KVM_DEVICE:
                qemu["kvm_device_open"] = True
                break
    if parsed is None:
        note("accelerator", "no command line was read")
    else:
        accelerator, basis, problem = _derive_accelerator(
            parsed, qemu["kvm_device_open"], host_machine, qemu["target_arch"]
        )
        qemu["accelerator"] = accelerator
        qemu["accelerator_basis"] = basis
        if problem:
            note("accelerator", problem)
    return qemu


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_loopback(host: Any) -> bool:
    if not isinstance(host, str) or not host:
        return False
    if host.lower() == "localhost":  # RFC 6761: always a loopback address
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _forwarded_rules(hostfwd: Any, port: Any) -> list[str]:
    """The TCP forwards of ``hostfwd`` that a connection to a loopback
    address on ``port`` enters: host address loopback or empty (every
    address)."""
    if not isinstance(hostfwd, list) or not _is_int(port):
        return []
    rules: list[str] = []
    for rule in hostfwd:
        if not isinstance(rule, dict) or rule.get("protocol") not in ("tcp", ""):
            continue
        if not _is_int(rule.get("host_port")) or rule.get("host_port") != port:
            continue
        addr = rule.get("host_addr")
        if addr == "" or _is_loopback(addr):
            rules.append(str(rule.get("rule")))
    return rules


def capture_hypervisor_snapshot(
    *,
    loadgen_env: dict[str, Any] | None = None,
    broker: str | None = None,
    port: int | None = None,
    proc_root: Path = PROC_ROOT,
) -> dict[str, Any]:
    """One snapshot of the hypervisor side, read from this host's ``/proc``.

    ``host`` is :func:`capture_host_record`; ``qemu`` describes the single
    ``qemu-system-aarch64`` process (0 or 2 and more matches: ``found``,
    ``pids`` and ``error`` are set and no process is chosen). Two facts are
    derived, never assumed: ``colocated_with_loadgen`` (the QEMU process is
    in this host's process table, and this host's boot id equals the boot id
    of ``loadgen_env``, captured by the same harness) and
    ``generator_target_is_this_guest`` (``broker`` is a loopback address and
    a forward of this QEMU takes the generator's ``port``). A value that
    cannot be read or derived is None, with the reason in ``problems``.
    """
    problems: list[str] = []
    captured_utc = utc_now_iso()
    captured_monotonic_ns = time.monotonic_ns()
    host = capture_host_record(proc_root, problems)
    qemu = _capture_qemu(proc_root, host["machine"], problems)

    colocated: bool | None = None
    lg_boot = loadgen_env.get("boot_id") if isinstance(loadgen_env, dict) else None
    if qemu["pid"] is None:
        problems.append(
            "colocated_with_loadgen: not determined: no single QEMU process "
            "was found in this host's process table"
        )
    elif not (_text(host["boot_id"]) and _text(lg_boot)):
        problems.append(
            "colocated_with_loadgen: not determined: the boot id of this host "
            "or of the load-generator record is missing"
        )
    else:
        colocated = host["boot_id"] == lg_boot

    target: bool | None = None
    if qemu["parsed"] is None:
        problems.append(
            "generator_target_is_this_guest: not determined: no QEMU command "
            "line was read"
        )
    elif broker is None or not _is_int(port):
        problems.append(
            "generator_target_is_this_guest: not determined: the generator's "
            "broker or port is not given"
        )
    else:
        target = _is_loopback(broker) and bool(
            _forwarded_rules(qemu["parsed"]["hostfwd"], port)
        )

    return {
        "captured_utc": captured_utc,
        "captured_monotonic_ns": captured_monotonic_ns,
        "host": host,
        "qemu": qemu,
        "colocated_with_loadgen": colocated,
        "generator_target_is_this_guest": target,
        "problems": problems,
    }


def write_hypervisor_environment(
    path: str | Path, start: dict[str, Any], end: dict[str, Any] | None
) -> Path:
    """Write ``hypervisor_environment.json`` once: the start snapshot and
    the end snapshot (None when the end was not captured). An existing file
    is never replaced (FileExistsError)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "role": "hypervisor",
        "record_version": HYPERVISOR_RECORD_VERSION,
        "capture": HYPERVISOR_CAPTURE,
        "start": start,
        "end": end,
    }
    with path.open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return path


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def image_identity_record(
    hypervisor_env: dict[str, Any] | None,
    configuration_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The run's image identity, built from the hypervisor record's START
    snapshot and, when given, the configuration identity's controller image
    id. Nothing is inferred: an absent value is None. The five pulled
    container digests stay in the manifest's ``image_digests``, referenced
    by name."""
    qemu = _as_dict(_as_dict(_as_dict(hypervisor_env).get("start")).get("qemu"))
    return {
        "qemu_exe_sha256": _text(qemu.get("exe_sha256")),
        "qemu_version_line": _text(qemu.get("version_line")),
        "kernel_sha256": _text(qemu.get("kernel_sha256")),
        "rootfs_path": _text(qemu.get("rootfs_path")),
        "rootfs_image_name": _text(qemu.get("rootfs_image_name")),
        "image_digests_ref": "image_digests",
        "controller_image_id": _text(
            _as_dict(configuration_identity).get("controller_image_id")
        ),
    }


# ---------------------------------------------------------------------------
# The provenance checks (pure: shared by the run and the analysis)
# ---------------------------------------------------------------------------


def _check(check: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"check": check, "ok": bool(ok), "detail": detail}


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else None


def _emulation_labels(sut_env: dict[str, Any] | None) -> list[str]:
    """The guest labels that state emulation (case-insensitive)."""
    labels = _as_dict(sut_env)
    return [
        key
        for key in EMULATION_LABEL_KEYS
        if isinstance(labels.get(key), str)
        and any(token in labels[key].lower() for token in EMULATION_LABEL_TOKENS)
    ]


def _emulated_checks(
    sut_env: dict[str, Any] | None,
    loadgen_env: dict[str, Any] | None,
    hypervisor_env: dict[str, Any] | None,
    broker: str | None,
    port: int | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(check: str, ok: bool, detail: str) -> None:
        checks.append(_check(check, ok, detail))

    hv = _as_dict(hypervisor_env)
    start = _as_dict(hv.get("start"))
    end = hv.get("end")
    sq = _as_dict(start.get("qemu"))
    shost = _as_dict(start.get("host"))
    parsed = _as_dict(sq.get("parsed"))
    sut = sut_env if isinstance(sut_env, dict) else None
    lg = _as_dict(loadgen_env)

    # H1: the hypervisor record holds exactly one QEMU at the start.
    if not hv:
        add("H1", False, f"no hypervisor record ({HYPERVISOR_ENVIRONMENT_FILENAME})")
    elif hv.get("role") != "hypervisor":
        add("H1", False, f"the record's role is {hv.get('role')!r}, not 'hypervisor'")
    elif sq.get("found") != 1 or not _is_int(sq.get("pid")):
        reason = sq.get("error") or "no QEMU process is recorded"
        add("H1", False, f"the start snapshot holds no single QEMU process: {reason}")
    else:
        add("H1", True, f"the start snapshot found one QEMU process (pid {sq['pid']})")

    # H2: the same QEMU process at the end of the run.
    if not isinstance(end, dict):
        add("H2", False, "no end snapshot: QEMU at the end of the run is unknown")
    else:
        eq, ehost = _as_dict(end.get("qemu")), _as_dict(end.get("host"))
        pairs = (
            ("pid", sq.get("pid"), eq.get("pid")),
            ("starttime_ticks", sq.get("starttime_ticks"), eq.get("starttime_ticks")),
            ("boot_id", shost.get("boot_id"), ehost.get("boot_id")),
            ("argv_sha256", sq.get("argv_sha256"), eq.get("argv_sha256")),
        )
        changed = [
            f"{name} {a!r} -> {b!r}"
            for name, a, b in pairs
            if a is None or b is None or a != b
        ]
        if changed:
            add(
                "H2",
                False,
                "QEMU is not shown to be the same process at the end: "
                + "; ".join(changed),
            )
        else:
            add("H2", True, "the same pid, start time, boot id and argv at both ends")

    # H3: TCG, and KVM not requested.
    accelerator = sq.get("accelerator")
    kvm_requested = parsed.get("kvm_requested")
    if accelerator == "tcg" and kvm_requested is False:
        add("H3", True, "accelerator tcg, KVM not requested")
    else:
        add(
            "H3",
            False,
            f"accelerator {accelerator!r}, kvm_requested {kvm_requested!r}: "
            "the run is not shown to be TCG-emulated",
        )

    # H4: co-location recorded as a boolean that the boot ids bear out.
    colocated = start.get("colocated_with_loadgen")
    hv_boot, lg_boot = _text(shost.get("boot_id")), _text(lg.get("boot_id"))
    if not isinstance(colocated, bool):
        add("H4", False, f"colocated_with_loadgen is {colocated!r}, not a boolean")
    elif not (hv_boot and lg_boot):
        add("H4", False, "a boot id is missing: co-location cannot be confirmed")
    elif colocated != (hv_boot == lg_boot):
        relation = "equal" if hv_boot == lg_boot else "differ"
        add(
            "H4",
            False,
            f"colocated_with_loadgen is {colocated} but the boot ids {relation} "
            f"(hypervisor {hv_boot}, load generator {lg_boot})",
        )
    else:
        add("H4", True, f"colocated_with_loadgen is {colocated}, as the boot ids say")

    # H5: the generator's traffic enters this QEMU.
    flag = start.get("generator_target_is_this_guest")
    rules = _forwarded_rules(parsed.get("hostfwd"), port)
    target = f"{broker}:{port}"
    if flag is True and _is_loopback(broker) and rules:
        add("H5", True, f"the generator's target {target} is forwarded by {rules[0]}")
    else:
        add(
            "H5",
            False,
            f"the generator's target {target} is not shown to enter the recorded "
            f"QEMU (loopback broker: {_is_loopback(broker)}; forwards of the port: "
            f"{', '.join(rules) or 'none'}; recorded flag: {flag!r})",
        )

    # G1-G5: the guest record describes this guest.
    if sut is None:
        add("G1", False, f"no guest record ({SUT_ENVIRONMENT_FILENAME})")
    elif sut.get("role") != "sut":
        add("G1", False, f"the guest record's role is {sut.get('role')!r}, not 'sut'")
    else:
        add("G1", True, "the guest record's role is 'sut'")

    uname_a = (sut or {}).get("uname_a")
    if isinstance(uname_a, str) and "aarch64" in uname_a:
        add("G2", True, "the guest's uname_a states aarch64")
    else:
        add("G2", False, f"the guest's uname_a {uname_a!r} does not state aarch64")

    nproc, smp = sut_nproc(sut), parsed.get("smp")
    if nproc is not None and _is_int(smp) and nproc == smp:
        add("G3", True, f"the guest's nproc equals -smp ({smp})")
    else:
        add("G3", False, f"the guest's nproc {nproc!r} differs from -smp {smp!r}")

    labels = _emulation_labels(sut)
    if labels:
        add("G4", True, "the guest label(s) " + ", ".join(labels) + " state emulation")
    else:
        keys = ", ".join(EMULATION_LABEL_KEYS)
        add("G4", False, f"no guest label ({keys}) states emulation")

    captured_utc, start_utc = (sut or {}).get("captured_utc"), sq.get("start_utc")
    captured, started = _parse_utc(captured_utc), _parse_utc(start_utc)
    if captured is None or started is None:
        add(
            "G5",
            False,
            f"the guest capture time {captured_utc!r} or the QEMU start "
            f"{start_utc!r} is not a UTC timestamp",
        )
    elif captured < started:
        add(
            "G5",
            False,
            f"the guest record ({captured_utc}) predates this QEMU process "
            f"({start_utc}): it describes another guest instance",
        )
    else:
        add("G5", True, f"the guest record ({captured_utc}) follows QEMU's start")

    # L1: the load generator runs on the hypervisor's host machine.
    lg_role, lg_machine = lg.get("role"), lg.get("machine")
    hv_machine = shost.get("machine")
    if lg_role == "loadgen" and _text(lg_machine) and lg_machine == hv_machine:
        add("L1", True, f"the load generator and the hypervisor host are {hv_machine}")
    else:
        add(
            "L1",
            False,
            f"the load-generator record (role {lg_role!r}, machine {lg_machine!r}) "
            f"does not match the hypervisor host (machine {hv_machine!r})",
        )

    # I1: the image identity is established.
    fields = ("exe_sha256", "kernel_sha256", "rootfs_image_name")
    missing = [field for field in fields if not _text(sq.get(field))]
    if missing:
        add("I1", False, "the image identity lacks " + ", ".join(missing))
    else:
        add("I1", True, f"QEMU, kernel and image {sq['rootfs_image_name']} identified")
    return checks


def _native_checks(
    execution_mode: str,
    sut_env: dict[str, Any] | None,
    hypervisor_env: dict[str, Any] | None,
    broker: str | None,
    port: int | None,
) -> list[dict[str, Any]]:
    declared = f"contradicting the declared {execution_mode!r}"
    checks = [
        _check("N0", False, f"{NO_NATIVE_CAPTURE}; {execution_mode!r} is declared")
    ]
    # N1: a local QEMU takes the generator's traffic.
    hv = _as_dict(hypervisor_env)
    forwards: list[str] = []
    if _is_loopback(broker):
        for label in ("start", "end"):
            qemu = _as_dict(_as_dict(hv.get(label)).get("qemu"))
            rules = _forwarded_rules(_as_dict(qemu.get("parsed")).get("hostfwd"), port)
            if rules:
                forwards.append(f"{label}: pid {qemu.get('pid')} " + ", ".join(rules))
    if forwards:
        checks.append(_check(
            "N1",
            False,
            f"a local {QEMU_EXECUTABLE} takes the generator's traffic to "
            f"{broker}:{port} ({'; '.join(forwards)}), {declared}",
        ))
    else:
        checks.append(_check(
            "N1", True, f"no recorded local QEMU takes the traffic to {broker}:{port}"
        ))
    # N2: a guest label states emulation.
    labels = _emulation_labels(sut_env)
    if labels:
        checks.append(_check(
            "N2",
            False,
            f"the guest label(s) {', '.join(labels)} state emulation, {declared}",
        ))
    else:
        checks.append(_check("N2", True, "no guest label states emulation"))
    # N3: the guest is the emulated integrated guest.
    node = sut_env_node(sut_env if isinstance(sut_env, dict) else None)
    if node == INTEGRATED_GUEST_NODE:
        checks.append(_check(
            "N3", False, f"the guest node is {node!r}, the emulated guest, {declared}"
        ))
    else:
        checks.append(_check(
            "N3", True, f"the guest node {node!r} is not the emulated guest"
        ))
    return checks


def provenance_checks(
    *,
    execution_mode: str | None,
    sut_env: dict[str, Any] | None,
    loadgen_env: dict[str, Any] | None,
    hypervisor_env: dict[str, Any] | None,
    broker: str | None,
    port: int | None,
) -> list[dict[str, Any]]:
    """The G4 core provenance checks (plan 655-661) of one run, from its
    own records: a list of ``{"check", "ok", "detail"}`` in a fixed order.

    - P0: the execution mode is declared and known. Unset or unknown, P0 is
      the only check: no mode is ever inferred, from the labels or anything
      else.
    - ``tcg-emulated``: H1 the hypervisor record holds exactly one QEMU at
      the start; H2 the same process (pid, start time, boot id, command
      line) at the end; H3 the accelerator is TCG and KVM is not requested;
      H4 co-location is recorded as a boolean consistent with the two boot
      ids; H5 the generator's target is a loopback address forwarded into
      this QEMU; G1 the guest record's role is ``sut``; G2 its uname states
      aarch64; G3 its nproc equals ``-smp``; G4 a guest label states
      emulation; G5 the guest record was captured after this QEMU started;
      L1 the load-generator record runs on the hypervisor's host machine;
      I1 the QEMU executable, the kernel and the rootfs image are
      identified.
    - ``native-kvm``/``native-metal``: N0 always fails (no native capture
      exists here), and N1 (a local QEMU takes the generator's port), N2 (a
      guest label states emulation) and N3 (the guest is the emulated
      integrated guest) name each contradiction found.
    """
    if execution_mode is None:
        return [_check(
            "P0",
            False,
            "execution_mode is not set: it has no default, and an unset value "
            "invalidates the run",
        )]
    if execution_mode not in EXECUTION_MODES:
        known = ", ".join(EXECUTION_MODES)
        return [_check(
            "P0", False, f"execution_mode {execution_mode!r} is not one of {known}"
        )]
    label = EXECUTION_MODE_LABELS[execution_mode]
    checks = [_check("P0", True, f"execution_mode {execution_mode!r} ({label})")]
    if execution_mode == "tcg-emulated":
        checks += _emulated_checks(sut_env, loadgen_env, hypervisor_env, broker, port)
    else:
        checks += _native_checks(execution_mode, sut_env, hypervisor_env, broker, port)
    return checks


def provenance_problems(checks: list[dict[str, Any]]) -> list[str]:
    """One validity reason per failed check: ``provenance: <check>: <detail>``."""
    return [
        f"provenance: {check.get('check')}: {check.get('detail')}"
        for check in checks
        if not check.get("ok")
    ]


def sut_env_node(sut_env: dict[str, Any] | None) -> str | None:
    """The SUT's node/hostname from sut_environment.json, or None.

    Accepts either the ``node`` or the ``hostname`` key (first non-empty
    string wins). Used to cross-check the ``host`` provenance column of the
    SUT collector's resources.csv (work order P1 fix 3).
    """
    if not sut_env:
        return None
    for key in ("node", "hostname"):
        value = sut_env.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def validate_sut_environment(sut_env: dict[str, Any] | None) -> list[str]:
    """Check a sut_environment.json dict against REQUIRED_SUT_FIELDS.

    Returns the list of missing logical fields (empty when the manifest is
    usable). ``None`` (absent/unreadable file) reports every field missing;
    the caller distinguishes "file absent" from "file present but unusable"
    itself. ``nproc`` must parse as a positive int (see :func:`sut_nproc`);
    the other fields need a non-empty string under any accepted key.
    """
    missing: list[str] = []
    for logical_name, keys in REQUIRED_SUT_FIELDS:
        if logical_name == "nproc":
            if sut_nproc(sut_env) is None:
                missing.append("nproc (positive integer)")
            continue
        if sut_env is None or not any(
            isinstance(sut_env.get(key), str) and sut_env.get(key).strip()
            for key in keys
        ):
            accepted = "/".join(keys)
            missing.append(f"{logical_name} (accepted keys: {accepted})")
    return missing


def sut_nproc(sut_env: dict[str, Any] | None) -> int | None:
    """The SUT's CPU count from sut_environment.json, or None.

    Used by the analysis to normalize docker-stats ``cpu_pct`` (single-CPU
    basis) to host-level utilization (audit 9.7):
    ``host_cpu_utilization = sum(container cpu_pct) / (100 * nproc)``.
    """
    if not sut_env:
        return None
    value = sut_env.get("nproc")
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None
