"""Per-second controller /metrics sampling into ``controller_metrics.csv``
(audit 9.7: queue growth must be measured, not TODO).

Polls the controller's ``GET /metrics`` endpoint (CONTRACTS 5; since
CONTRACTS v1.1 the snapshot includes ``dropped`` and ``queue_depth``) once
per second during timed runs and appends one CSV row per sample::

    ts_utc,accepted,rejected,duplicate,failed,dropped,queue_depth,
    received,in_progress,processing_errors,unacked,mqtt_connection,
    mqtt_subscribed,started_at,wall_utc,uptime_s,monotonic_ns

The first seven columns are the historical ones. The ten after
``queue_depth`` are ADR 0011 item 18: the progress fields ``/metrics`` has
carried since ADR 0010 (``received``, ``in_progress``,
``processing_errors``, ``started_at``, ``uptime_s``, ``monotonic_ns``,
``wall_utc``) and the three fields of the bridge (``mqtt_subscribed``,
``mqtt_connection``, ``unacked``), which the sampler used to discard. They
let the analysis tell one controller process from the next
(``started_at``), place a reading in the controller's clock
(``monotonic_ns``/``wall_utc``) and see the session state across a restart.
The analysis reads the CSV by column name, so the addition changes no
reader.

Access note: port 8000 is bound to loopback ON the ARM VM (deployment
security notes), so the harness host reaches it through an SSH tunnel::

    ssh -N -L 8000:127.0.0.1:8000 <vm>   # then --controller-url http://127.0.0.1:8000

Failure tolerance: a failed poll NEVER stops the sampler — the controller
is expected to be briefly unreachable during the ``controller_restart``
condition. A failed poll is a network, HTTP (including a typed
``http.client.HTTPException`` such as ``IncompleteRead`` or
``BadStatusLine``, which is not an ``OSError``: until 2026-09-29 it ended the
sampler's thread, or raised from the entry poll, in the default mode) or JSON
failure. Failed polls are counted (``poll_errors``) and the last error
message is kept; no row is written for a failed poll, so gaps in
``controller_metrics.csv`` are themselves evidence of unavailability.

Two recording rules, one per kind of field. The eleven counters
(:data:`METRIC_FIELDS`) are COUNTS, so a recorded value must be a
non-negative integer (sprint P5.4 defect 4). Two layers enforce it.
:func:`fetch_metrics` refuses the JSON constants
``NaN``/``Infinity``/``-Infinity`` — ``json.loads`` parses them into Python
floats by default, which is how ``inf`` used to reach the CSV — and the
writer refuses any value that is not a non-negative integer, recording an
EMPTY cell instead of ``inf``/``nan``/``-1``/``2.5``. The five raw fields
(:data:`RAW_FIELDS`) are written verbatim when they are of their documented
type (:func:`raw_value`): ``mqtt_subscribed`` as ``true``/``false``,
``started_at`` and ``wall_utc`` as the strings the controller sent,
``uptime_s`` and ``monotonic_ns`` as the numbers it sent; anything else is
an empty cell. Under both rules a field the controller did not send is an
empty cell and never a zero (CONTRACTS 5: absence is not zero). Refusals are
counted (``invalid_values``, ``last_invalid``) so the harness can surface
them in the manifest; an empty cell is missing evidence, a fabricated one
would be worse.

Standard library only (``urllib.request``); timestamps are the harness
host's wall clock (same NTP-sync assumption as the measured window: good
enough for 1 Hz windowing, never used for latency).

Failed-poll retry (the finite proof only, off by default). With
``fast_retry_s`` set, a poll that FAILED is followed, once it has completed,
by the next poll after ``fast_retry_s`` instead of the rest of the
interval; a successful poll returns to the normal cadence. Requests stay
serial (one thread, the same five-second request timeout), the stop event
cancels any wait, and fast retry ends for an uninterrupted failure episode
once ``fast_retry_cap_s`` have elapsed since its first failed request (the
normal cadence then resumes until a success ends the episode). Its purpose
is to observe the first post-restart reading as early as the controller
answers it, so that the kill's band on the controller clock is as narrow as
the controller allows (ADR 0011, the finite proof, E-8); it changes no
reading, adds no interpolated row and never replaces a controller-clock
value by a host instant. Every attempt is written to an attempts log with
its host instants and outcome when ``attempts_path`` is given. The finite
proof's harness command enables it (``--metrics-fast-retry``); every other
run keeps the 1 Hz sampler unchanged.
"""

from __future__ import annotations

import csv
import http.client
import json
import math
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .protocol import RESOURCE_SAMPLE_INTERVAL_S

#: The finite proof's failed-poll retry (PM decision of 2026-09-26, review
#: of r02): the wait after a completed failed poll, and how long one
#: uninterrupted failure episode may be retried at that pace. Instrumentation
#: settings, not acceptance criteria; off unless a caller enables them.
FAST_RETRY_S = 0.05
FAST_RETRY_CAP_S = 60.0

#: The attempts log of the failed-poll retry mode: one row per poll, with
#: the HOST's instants (never the controller clock) and the wait chosen.
ATTEMPTS_HEADER = (
    "attempt",
    "started_utc",
    "started_monotonic_s",
    "finished_monotonic_s",
    "outcome",
    "error",
    "next_wait_s",
)

#: Counter fields copied from the /metrics JSON snapshot under the count
#: rule (:func:`counter_value`), in column order: the six historical ones,
#: then the five integer fields of ADR 0011 item 18.
METRIC_FIELDS = (
    "accepted",
    "rejected",
    "duplicate",
    "failed",
    "dropped",
    "queue_depth",
    "received",
    "in_progress",
    "processing_errors",
    "unacked",
    "mqtt_connection",
)

#: Fields copied verbatim under the raw rule (:func:`raw_value`), in column
#: order after the counters: a truth value, two strings, two numbers.
RAW_FIELDS = (
    "mqtt_subscribed",
    "started_at",
    "wall_utc",
    "uptime_s",
    "monotonic_ns",
)

#: The documented type of each raw field, as the rule checks it.
_RAW_KINDS: dict[str, str] = {
    "mqtt_subscribed": "bool",
    "started_at": "str",
    "wall_utc": "str",
    "uptime_s": "number",
    "monotonic_ns": "number",
}

CSV_HEADER = ["ts_utc", *METRIC_FIELDS, *RAW_FIELDS]


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _reject_json_constant(name: str) -> float:
    """``json.loads`` hook refusing NaN/Infinity/-Infinity (P5.4 defect 4).

    Those are JSON extensions Python accepts by default; a counter snapshot
    carrying one is a broken controller, not a measurement, so the whole
    poll is failed (and counted) instead of writing ``inf`` to the CSV.
    """
    raise ValueError(
        f"metrics response carries the non-finite JSON constant {name!r}: "
        "counters must be finite non-negative integers"
    )


def fetch_metrics(url: str, timeout_s: float = 5.0) -> dict[str, Any]:
    """One GET <url>/metrics poll; returns the parsed JSON dict.

    Raises on any network/HTTP/JSON failure — including a body carrying the
    non-finite JSON constants; the sampler catches and counts.
    """
    metrics_url = url.rstrip("/") + "/metrics"
    with urllib.request.urlopen(metrics_url, timeout=timeout_s) as resp:
        body = resp.read()
    obj = json.loads(body.decode("utf-8"), parse_constant=_reject_json_constant)
    if not isinstance(obj, dict):
        raise ValueError("metrics response is not a JSON object")
    return obj


def counter_value(value: Any) -> int | None:
    """The recordable value of one counter, or None when it is refusable.

    Strict rule (sprint P5.4 defect 4): the :data:`METRIC_FIELDS` are
    COUNTS. Accepted are ``int`` (never ``bool``) and integral finite
    ``float`` values (a JSON ``5.0``), both >= 0. Everything else — ``nan``,
    ``inf``, a negative count, a fractional value or a non-number — returns
    None and is written as an EMPTY cell.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if not math.isfinite(value) or value < 0 or not value.is_integer():
            return None
        return int(value)
    return None


def raw_value(field: str, value: Any) -> str | int | float | None:
    """The recordable value of one raw field, or None when it is refusable.

    Raw rule (ADR 0011 item 18): the field is written verbatim when it is of
    its documented type and refused otherwise. ``mqtt_subscribed`` is a
    truth value, written ``true``/``false`` (a string ``"true"`` is not a
    truth value); ``started_at`` and ``wall_utc`` are strings; ``uptime_s``
    and ``monotonic_ns`` are finite numbers (a ``bool`` is not a number).
    """
    kind = _RAW_KINDS[field]
    if kind == "bool":
        return ("true" if value else "false") if isinstance(value, bool) else None
    if kind == "str":
        return value if isinstance(value, str) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class ControllerMetricsSampler:
    """Context manager sampling the controller /metrics into a CSV file.

    Usage (as in run.py)::

        with ControllerMetricsSampler(run_dir / "controller_metrics.csv",
                                      "http://127.0.0.1:8000") as sampler:
            ...  # timed run
        sampler.samples_written / sampler.poll_errors / sampler.last_error
        sampler.invalid_values / sampler.last_invalid  # refused values

    The CSV (header included) is always created so the run directory
    structure stays uniform (plan 5.8).
    """

    def __init__(
        self,
        csv_path: str | Path,
        url: str,
        interval_s: float = RESOURCE_SAMPLE_INTERVAL_S,
        *,
        fast_retry_s: float | None = None,
        fast_retry_cap_s: float = FAST_RETRY_CAP_S,
        attempts_path: str | Path | None = None,
    ) -> None:
        if fast_retry_s is not None and not 0 < fast_retry_s < interval_s:
            raise ValueError(
                f"fast_retry_s={fast_retry_s!r} must be above 0 and below the interval ({interval_s} s)"
            )
        if not fast_retry_cap_s > 0:
            raise ValueError(f"fast_retry_cap_s={fast_retry_cap_s!r} must be above 0")
        if attempts_path is not None and fast_retry_s is None:
            # The default thread polls at once after the entry poll, so the
            # log would state a wait that never happens.
            raise ValueError("attempts_path is the log of the failed-poll retry mode: it needs fast_retry_s")
        self.csv_path = Path(csv_path)
        self.url = url
        self.interval_s = interval_s
        self.fast_retry_s = fast_retry_s
        self.fast_retry_cap_s = fast_retry_cap_s
        self.attempts_path = None if attempts_path is None else Path(attempts_path)
        # Failed-poll retry figures (all 0 when the mode is off).
        self.fast_retries = 0  # waits of fast_retry_s taken
        self.failure_episodes = 0  # uninterrupted runs of failed polls
        self.cap_reached = 0  # episodes in which the cap ended fast retry
        self._episode_start: float | None = None
        self._episode_capped = False
        self._attempts = 0
        self._attempts_fh = None
        self._attempts_writer = None
        # The wait after the entry poll (__enter__): the thread keeps it in the
        # failed-poll retry mode only; otherwise it polls at once, as it always
        # has, so the default sampler's timing is unchanged.
        self._first_wait = 0.0
        self.samples_written = 0
        self.poll_errors = 0
        self.last_error: str | None = None
        # Values refused by the count rule (P5.4 defect 4) or the raw rule.
        self.invalid_values = 0
        self.last_invalid: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fh = None
        self._writer = None
        self._lock = threading.Lock()

    # -- internals ---------------------------------------------------------

    def _record_invalid(self, field: str, value: Any, expected: str) -> None:
        """Count and log one refused value (P5.4 defect 4; raw rule)."""
        self.invalid_values += 1
        self.last_invalid = (
            f"{field}={value!r} is not {expected}; recorded as an empty cell"
        )
        if self.invalid_values == 1:
            print(
                f"[metrics-sampler] warning: {self.last_invalid}",
                file=sys.stderr,
                flush=True,
            )

    def _sample_once(self) -> str | None:
        """One poll: writes the row of a successful one. Returns None on
        success, else the error of the failed poll (also counted)."""
        try:
            snapshot = fetch_metrics(self.url)
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            self.poll_errors += 1
            self.last_error = str(exc)
            return self.last_error
        except http.client.HTTPException as exc:
            # A typed HTTP failure that is not an OSError - e.g. IncompleteRead,
            # a controller killed between a response's headers and its body.
            # It is a failed poll like any other, in every mode: counted and
            # kept as last_error (and in the attempts log, when the retry mode
            # has one), followed at the mode's cadence, and no row is written.
            # (Until 2026-09-29 the default sampler let it end its thread or
            # raise from the entry poll; LOG #C045, #C046.)
            self.poll_errors += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self.last_error
        row: list[Any] = [_utc_now_iso()]
        for field in METRIC_FIELDS:
            raw = snapshot.get(field)
            value = counter_value(raw)
            if value is None:
                # Refused, never coerced: writing 'inf'/'nan'/'-1' would put
                # a non-measurement into the evidence (P5.4 defect 4). An
                # absent field is missing evidence, not a refusal.
                if raw is not None:
                    self._record_invalid(
                        field, raw, "a non-negative integer counter"
                    )
                row.append("")
            else:
                row.append(value)
        for field in RAW_FIELDS:
            raw = snapshot.get(field)
            value = raw_value(field, raw)
            if value is None:
                if raw is not None:
                    self._record_invalid(field, raw, f"a {_RAW_KINDS[field]}")
                row.append("")
            else:
                row.append(value)
        with self._lock:
            self._writer.writerow(row)
            self.samples_written += 1
            self._fh.flush()
        return None

    def _next_wait(self, ok: bool, started: float, finished: float) -> float:
        """The wait before the next poll, from this poll's outcome and its
        host-monotonic start and end: the rest of the interval, or - in the
        failed-poll retry mode, after a failed poll, while the episode is
        within its cap - ``fast_retry_s``. A success ends the episode."""
        normal = max(0.0, self.interval_s - (finished - started))
        if ok:
            self._episode_start = None
            self._episode_capped = False
            return normal
        if self.fast_retry_s is None:
            return normal
        if self._episode_start is None:
            self._episode_start = started
            self._episode_capped = False
            self.failure_episodes += 1
        if finished - self._episode_start >= self.fast_retry_cap_s:
            if not self._episode_capped:
                self._episode_capped = True
                self.cap_reached += 1
            return normal
        self.fast_retries += 1
        return self.fast_retry_s

    def _poll(self) -> float:
        """One poll and the wait it leaves; the attempts log records both."""
        started_utc = _utc_now_iso()
        started = time.monotonic()
        error = self._sample_once()
        finished = time.monotonic()
        wait = self._next_wait(error is None, started, finished)
        if self._attempts_writer is not None:
            self._attempts += 1
            with self._lock:
                self._attempts_writer.writerow(
                    [
                        self._attempts,
                        started_utc,
                        f"{started:.6f}",
                        f"{finished:.6f}",
                        "ok" if error is None else "error",
                        "" if error is None else " ".join(error.split())[:200],
                        f"{wait:.3f}",
                    ]
                )
                self._attempts_fh.flush()
        return wait

    def _loop(self) -> None:
        if self._first_wait:
            self._stop.wait(self._first_wait)
        while not self._stop.is_set():
            self._stop.wait(self._poll())

    # -- context manager ---------------------------------------------------

    def __enter__(self) -> "ControllerMetricsSampler":
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.csv_path, "w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._fh)
        self._writer.writerow(CSV_HEADER)
        self._fh.flush()
        if self.attempts_path is not None:
            self.attempts_path.parent.mkdir(parents=True, exist_ok=True)
            self._attempts_fh = open(self.attempts_path, "w", encoding="utf-8", newline="")
            self._attempts_writer = csv.writer(self._attempts_fh)
            self._attempts_writer.writerow(ATTEMPTS_HEADER)
            self._attempts_fh.flush()
        first_wait = self._poll()
        self._first_wait = first_wait if self.fast_retry_s is not None else 0.0
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
        if self._attempts_fh is not None:
            self._attempts_fh.close()
            self._attempts_fh = None
            self._attempts_writer = None
        return None
