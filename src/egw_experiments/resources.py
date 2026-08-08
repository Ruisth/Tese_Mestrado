"""Per-second container resource sampling into ``resources.csv`` (plan 7.1).

DEV-ONLY LOCAL SAMPLER (audit 9.1): this samples the Docker daemon reachable
from THIS host — the load generator, NOT the ARM VM under test. During the
campaign, SUT resources are collected ON the VM by
``src/deployment/scripts/collect-resources.sh`` (same CSV schema) and
ingested with ``run --resources-from``. This local sampler is opt-in via
``run --local-resources`` and its output is recorded as ``resource_source:
'local-dev'`` in the manifest.

Samples ``docker stats --no-stream`` once per second in a background thread
and appends one row per container to ``resources.csv`` with the columns
``ts_utc, container, cpu_pct, mem_bytes, mem_pct, host``. The ``host``
column records the hostname of the machine the sample was taken on (host
provenance, work order P1): for this local dev sampler that is the LOAD
GENERATOR host, which is exactly why run-time ingestion
(:func:`egw_experiments.run.ingest_resources` via
:func:`validate_resources_csv`) can detect that a CSV was not produced on
the SUT.

Notes:

- The stats format used is ``--format '{{json .}}'``, which produces one
  JSON object per line and is equivalent to ``--format json`` on newer
  Docker CLIs while remaining compatible with older ones.
- ``docker stats --no-stream`` itself needs time to collect a sample, so the
  effective cadence can be slightly below 1 Hz under load; the real sample
  timestamps are recorded in ``ts_utc`` and the analysis uses them as-is.
- Docker's ``CPUPerc`` is expressed as a percentage of a single CPU and can
  exceed 100% for multi-threaded containers. Normalization to host
  utilization (dividing by 100 * nproc from sut_environment.json, audit
  9.7) happens in the analysis, not here.
- Degrades gracefully: when docker is absent or the daemon is unreachable,
  the sampler records a clear error message, writes only the CSV header and
  never raises out of the context manager.
"""

from __future__ import annotations

import csv
import json
import platform
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .protocol import RESOURCE_SAMPLE_INTERVAL_S

#: Canonical resources.csv schema (work order P1: host provenance column).
#: Written by BOTH producers: this local dev sampler and the SUT-side
#: collector ``src/deployment/scripts/collect-resources.sh``. Run-time
#: ingestion (``run/collect --resources-from``) accepts ONLY this header;
#: the analysis reader additionally tolerates the pre-P1 5-column header
#: for old fixtures/raw runs (see ``egw_experiments.analyze.read_resources_csv``).
CSV_HEADER = ["ts_utc", "container", "cpu_pct", "mem_bytes", "mem_pct", "host"]

#: Legacy pre-P1 header (no host provenance): readable by the analysis for
#: old fixtures, but NOT ingestible for new runs.
LEGACY_CSV_HEADER = ["ts_utc", "container", "cpu_pct", "mem_bytes", "mem_pct"]

#: Minimum number of data rows a resources.csv must carry to be ingested as
#: SUT evidence (work order P1 fix 3). Rationale: the collector samples at
#: 1 Hz and every timed condition lasts at least 30 s (smoke runs), so even
#: the shortest valid run yields >= 30 rows for a single container; a file
#: with fewer rows is header-only noise or a collector that died early and
#: cannot support the RQ3 CPU/RAM aggregates.
MIN_RESOURCE_SAMPLES = 30

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


def validate_resources_csv(
    path: str | Path,
    *,
    expected_host: str | None = None,
    min_samples: int = MIN_RESOURCE_SAMPLES,
) -> list[str]:
    """Validate a resources.csv before RUN-TIME ingestion (work order P1).

    Returns a list of human-readable problems; an empty list means the file
    is ingestible. Checks, in order:

    - the file exists and has a header line;
    - the header matches :data:`CSV_HEADER` EXACTLY (the 6-column schema
      with the ``host`` provenance column; the legacy 5-column schema is
      readable by the analysis for old fixtures but never ingestible for
      new runs);
    - at least ``min_samples`` (:data:`MIN_RESOURCE_SAMPLES`) data rows;
    - every row carries a non-empty ``host`` value;
    - when ``expected_host`` is given (the SUT's node/hostname from
      sut_environment.json), every distinct ``host`` value equals it —
      a mismatch means the CSV was collected on the wrong machine.
    """
    path = Path(path)
    if not path.is_file():
        return [f"resources file not found: {path}"]
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            try:
                header = next(reader)
            except StopIteration:
                return [f"resources file is empty (not even a header): {path}"]
            if header != CSV_HEADER:
                return [
                    f"resources header {header!r} does not match the "
                    f"required schema {CSV_HEADER!r} "
                    "(collect-resources.sh with the host provenance column; "
                    "legacy 5-column files are readable by the analysis but "
                    "not ingestible for new runs)"
                ]
            data_rows = 0
            empty_host_rows = 0
            hosts: set[str] = set()
            for row in reader:
                if not row or not any(cell.strip() for cell in row):
                    continue
                data_rows += 1
                host = row[5].strip() if len(row) > 5 else ""
                if host:
                    hosts.add(host)
                else:
                    empty_host_rows += 1
    except OSError as exc:
        return [f"resources file unreadable: {exc}"]

    problems: list[str] = []
    if data_rows == 0:
        problems.append("no data rows beyond the header")
    elif data_rows < min_samples:
        problems.append(
            f"only {data_rows} sample row(s); at least {min_samples} "
            "required (MIN_RESOURCE_SAMPLES: 1 Hz collector over the "
            "shortest 30 s timed run)"
        )
    if empty_host_rows:
        problems.append(
            f"{empty_host_rows} row(s) without a host value (host "
            "provenance is mandatory)"
        )
    if expected_host is not None and hosts and hosts != {expected_host}:
        problems.append(
            f"host value(s) {sorted(hosts)!r} do not match the SUT "
            f"node/hostname {expected_host!r} from sut_environment.json "
            "(the CSV was collected on the wrong machine)"
        )
    return problems


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
        # Host provenance (work order P1): the hostname of THIS machine —
        # the load generator, since this sampler is the dev-only local one.
        self.host = platform.node()
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
                        self.host,
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
