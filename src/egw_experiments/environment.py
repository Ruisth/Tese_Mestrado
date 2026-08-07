"""Host environment capture for run manifests (plan 5.1/5.8).

Captures platform metadata (OS, kernel via ``platform.uname``, CPU count,
Python version) and, best-effort, the Docker client/server versions via
subprocess. Everything is optional-degrading: a missing docker CLI never
fails the capture, it is simply recorded as unavailable.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
    """Capture host metadata as a JSON-safe dict."""
    uname = platform.uname()
    return {
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


def write_environment(path: str | Path) -> Path:
    """Capture the environment and write it to ``environment.json``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(capture_environment(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
