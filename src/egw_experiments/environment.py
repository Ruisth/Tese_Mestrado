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
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: File names inside a raw run directory (audit 9.2).
SUT_ENVIRONMENT_FILENAME = "sut_environment.json"
LOADGEN_ENVIRONMENT_FILENAME = "loadgen_environment.json"

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


def capture_environment() -> dict[str, Any]:
    """Capture load-generator host metadata as a JSON-safe dict."""
    uname = platform.uname()
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
    }


def write_loadgen_environment(path: str | Path) -> Path:
    """Capture the load-generator environment and write it to ``path``
    (normally ``<run_dir>/loadgen_environment.json``)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(capture_environment(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


# Backwards-compatible alias (pre-audit name). The file it should target is
# now loadgen_environment.json; do not use it for the SUT.
write_environment = write_loadgen_environment


def read_sut_environment(run_dir: str | Path) -> dict[str, Any] | None:
    """Read ``sut_environment.json`` from a run directory.

    Returns the parsed dict, or None when the file is absent or unreadable
    (the caller decides whether that invalidates the run).
    """
    path = Path(run_dir) / SUT_ENVIRONMENT_FILENAME
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


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
