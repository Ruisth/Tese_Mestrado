"""Per-second controller /metrics sampling into ``controller_metrics.csv``
(audit 9.7: queue growth must be measured, not TODO).

Polls the controller's ``GET /metrics`` endpoint (CONTRACTS 5; since
CONTRACTS v1.1 the snapshot includes ``dropped`` and ``queue_depth``) once
per second during timed runs and appends one CSV row per sample::

    ts_utc,accepted,rejected,duplicate,failed,dropped,queue_depth

Access note: port 8000 is bound to loopback ON the ARM VM (deployment
security notes), so the harness host reaches it through an SSH tunnel::

    ssh -N -L 8000:127.0.0.1:8000 <vm>   # then --controller-url http://127.0.0.1:8000

Failure tolerance: a failed poll NEVER stops the sampler — the controller
is expected to be briefly unreachable during the ``controller_restart``
condition. Failed polls are counted (``poll_errors``) and the last error
message is kept; no row is written for a failed poll, so gaps in
``controller_metrics.csv`` are themselves evidence of unavailability.

Standard library only (``urllib.request``); timestamps are the harness
host's wall clock (same NTP-sync assumption as the measured window: good
enough for 1 Hz windowing, never used for latency).
"""

from __future__ import annotations

import csv
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .protocol import RESOURCE_SAMPLE_INTERVAL_S

CSV_HEADER = [
    "ts_utc",
    "accepted",
    "rejected",
    "duplicate",
    "failed",
    "dropped",
    "queue_depth",
]

#: Counter fields copied from the /metrics JSON snapshot, in column order.
METRIC_FIELDS = ("accepted", "rejected", "duplicate", "failed", "dropped", "queue_depth")


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def fetch_metrics(url: str, timeout_s: float = 5.0) -> dict[str, Any]:
    """One GET <url>/metrics poll; returns the parsed JSON dict.

    Raises on any network/HTTP/JSON failure; the sampler catches and counts.
    """
    metrics_url = url.rstrip("/") + "/metrics"
    with urllib.request.urlopen(metrics_url, timeout=timeout_s) as resp:
        body = resp.read()
    obj = json.loads(body.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("metrics response is not a JSON object")
    return obj


class ControllerMetricsSampler:
    """Context manager sampling the controller /metrics into a CSV file.

    Usage (as in run.py)::

        with ControllerMetricsSampler(run_dir / "controller_metrics.csv",
                                      "http://127.0.0.1:8000") as sampler:
            ...  # timed run
        sampler.samples_written / sampler.poll_errors / sampler.last_error

    The CSV (header included) is always created so the run directory
    structure stays uniform (plan 5.8).
    """

    def __init__(
        self,
        csv_path: str | Path,
        url: str,
        interval_s: float = RESOURCE_SAMPLE_INTERVAL_S,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.url = url
        self.interval_s = interval_s
        self.samples_written = 0
        self.poll_errors = 0
        self.last_error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fh = None
        self._writer = None
        self._lock = threading.Lock()

    # -- internals ---------------------------------------------------------

    def _sample_once(self) -> None:
        try:
            snapshot = fetch_metrics(self.url)
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            self.poll_errors += 1
            self.last_error = str(exc)
            return
        row = [_utc_now_iso()]
        for field in METRIC_FIELDS:
            value = snapshot.get(field)
            row.append("" if not isinstance(value, (int, float)) else value)
        with self._lock:
            self._writer.writerow(row)
            self.samples_written += 1
            self._fh.flush()

    def _loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            self._sample_once()
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.0, self.interval_s - elapsed))

    # -- context manager ---------------------------------------------------

    def __enter__(self) -> "ControllerMetricsSampler":
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.csv_path, "w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._fh)
        self._writer.writerow(CSV_HEADER)
        self._fh.flush()
        self._sample_once()
        self._thread = threading.Thread(
            target=self._loop, name="controller-metrics-sampler", daemon=True
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
