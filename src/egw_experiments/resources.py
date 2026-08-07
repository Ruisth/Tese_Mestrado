"""Per-second container resource sampling into ``resources.csv`` (plan 7.1).

Samples ``docker stats --no-stream`` once per second in a background thread
and appends one row per container to ``resources.csv`` with the columns
``ts_utc, container, cpu_pct, mem_bytes, mem_pct``.

Notes:

- The stats format used is ``--format '{{json .}}'``, which produces one
  JSON object per line and is equivalent to ``--format json`` on newer
  Docker CLIs while remaining compatible with older ones.
- ``docker stats --no-stream`` itself needs time to collect a sample, so the
  effective cadence can be slightly below 1 Hz under load; the real sample
  timestamps are recorded in ``ts_utc`` and the analysis uses them as-is.
- Docker's ``CPUPerc`` is expressed as a percentage of a single CPU and can
  exceed 100% for multi-threaded containers. Normalization to host
  utilization (dividing by the CPU count from environment.json) happens in
  the analysis, not here.
- Degrades gracefully: when docker is absent or the daemon is unreachable,
  the sampler records a clear error message, writes only the CSV header and
  never raises out of the context manager.
"""

from __future__ import annotations

import csv
import json
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .protocol import RESOURCE_SAMPLE_INTERVAL_S

CSV_HEADER = ["ts_utc", "container", "cpu_pct", "mem_bytes", "mem_pct"]

DOCKER_STATS_CMD = ["docker", "stats", "--no-stream", "--format", "{{json .}}"]

_SIZE_MULTIPLIERS = {
    "b": 1,
    "kb": 10**3,
    "kib": 2**10,
    "mb": 10**6,
    "mib": 2**20,
    "gb": 10**9,
    "gib": 2**30,
    "tb": 10**12,
    "tib": 2**40,
}


class DockerUnavailableError(RuntimeError):
    """Raised when the docker CLI or daemon cannot be used for sampling."""


def parse_percent(value: str) -> float | None:
    """Parse docker's percentage strings, e.g. ``"12.34%"`` -> 12.34."""
    try:
        return float(value.strip().rstrip("%"))
    except (AttributeError, ValueError):
        return None


def parse_size(value: str) -> int | None:
    """Parse docker size strings, e.g. ``"23.5MiB"`` -> 24641536 (bytes)."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    i = 0
    while i < len(s) and (s[i].isdigit() or s[i] in ".+-eE"):
        i += 1
    num, unit = s[:i], s[i:].strip().lower()
    try:
        mult = _SIZE_MULTIPLIERS[unit] if unit else 1
        return int(float(num) * mult)
    except (KeyError, ValueError):
        return None


def parse_mem_usage(value: str) -> int | None:
    """Parse the used part of docker's ``MemUsage`` (``"used / limit"``)."""
    if not isinstance(value, str):
        return None
    return parse_size(value.split("/", 1)[0])


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def sample_docker_stats(timeout_s: float = 20.0) -> list[dict[str, Any]]:
    """Take one ``docker stats --no-stream`` sample.

    Returns one dict per container: ``{container, cpu_pct, mem_bytes,
    mem_pct}``. Raises :class:`DockerUnavailableError` when docker is not
    usable at all; transient timeouts return an empty list.
    """
    try:
        proc = subprocess.run(
            DOCKER_STATS_CMD,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        raise DockerUnavailableError(
            "docker CLI not found on PATH; resource sampling is disabled. "
            "Install docker or run without resource metrics."
        ) from exc
    except OSError as exc:
        raise DockerUnavailableError(f"docker could not be executed: {exc}") from exc
    except subprocess.TimeoutExpired:
        return []  # transient; the caller keeps sampling

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip().splitlines()
        detail = stderr[0] if stderr else f"exit code {proc.returncode}"
        raise DockerUnavailableError(
            f"'docker stats' failed ({detail}); resource sampling is disabled."
        )

    rows: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append(
            {
                "container": obj.get("Name") or obj.get("Container") or "",
                "cpu_pct": parse_percent(obj.get("CPUPerc", "")),
                "mem_bytes": parse_mem_usage(obj.get("MemUsage", "")),
                "mem_pct": parse_percent(obj.get("MemPerc", "")),
            }
        )
    return rows


class ResourceSampler:
    """Context manager sampling docker stats into a CSV file.

    Usage (as in run.py)::

        with ResourceSampler(run_dir / "resources.csv") as sampler:
            ...  # timed run
        if sampler.error:
            ...  # degraded: no docker; error message available

    The CSV (header included) is always created, even when docker is
    unavailable, so the run directory structure stays uniform (plan 5.8).
    """

    def __init__(
        self,
        csv_path: str | Path,
        interval_s: float = RESOURCE_SAMPLE_INTERVAL_S,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.interval_s = interval_s
        self.error: str | None = None
        self.samples_written = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fh = None
        self._writer = None
        self._lock = threading.Lock()

    # -- internals ---------------------------------------------------------

    def _write_rows(self, rows: list[dict[str, Any]]) -> None:
        ts = _utc_now_iso()
        with self._lock:
            for row in rows:
                self._writer.writerow(
                    [
                        ts,
                        row["container"],
                        "" if row["cpu_pct"] is None else row["cpu_pct"],
                        "" if row["mem_bytes"] is None else row["mem_bytes"],
                        "" if row["mem_pct"] is None else row["mem_pct"],
                    ]
                )
                self.samples_written += 1
            self._fh.flush()

    def _loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                rows = sample_docker_stats()
            except DockerUnavailableError as exc:
                self.error = str(exc)
                return
            if rows:
                self._write_rows(rows)
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.0, self.interval_s - elapsed))

    # -- context manager ---------------------------------------------------

    def __enter__(self) -> "ResourceSampler":
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.csv_path, "w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._fh)
        self._writer.writerow(CSV_HEADER)
        self._fh.flush()

        # Probe once synchronously so an absent docker degrades immediately
        # with a clear error instead of a silent empty file.
        try:
            rows = sample_docker_stats()
        except DockerUnavailableError as exc:
            self.error = str(exc)
            return self
        if rows:
            self._write_rows(rows)

        self._thread = threading.Thread(
            target=self._loop, name="resource-sampler", daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30.0)
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        return None
