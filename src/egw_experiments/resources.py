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
- :func:`validate_resources_csv` is the run-time ingest gate for the SUT
  collector's output. Since sprint P5 (report 5.4) it validates the CONTENT
  semantically, not just the row count: parseable RFC 3339 timestamps,
  non-decreasing time, STRICTLY numeric cpu/mem fields (finite and
  non-negative — sprint P5.4 defect 4), per-row column completeness,
  a minimum number of DISTINCT sample instants (one docker-stats sample
  writes one row per container, so 30 rows can be five seconds of six
  containers) and, when the caller knows it, a span consistent with the
  run's measured window.
"""

from __future__ import annotations

import csv
import json
import math
import platform
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .protocol import MAX_SAMPLE_GAP_S, RESOURCE_SAMPLE_INTERVAL_S

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

#: Minimum number of DISTINCT sample instants (sprint P5, report 5.4
#: "Validação superficial de resources.csv"). Counting rows alone is not
#: evidence of a sampled run: one ``docker stats`` sample writes ONE ROW PER
#: CONTAINER, so 30 rows can be five seconds of six containers. The collector
#: samples at 1 Hz and the shortest timed condition lasts 30 s, so a usable
#: file carries at least this many distinct ``ts_utc`` values.
MIN_DISTINCT_SAMPLE_INSTANTS = 30

#: Minimum fraction of the run's MEASURED window that the sampled instants
#: must span when the caller supplies ``expected_window_s`` (sprint P5,
#: report 5.4). The slack absorbs the collector's start/stop edges around
#: the measured simulator invocation (the hooks start it before the warm-up
#: and stop it after the confirmation window, but the first/last sample
#: still land inside the second).
#: PENDING ADVISOR SIGN-OFF BEFORE exp-v1: the 90% minimum span must be
#: confirmed with the advisor before the protocol freeze (G4); it must not
#: change afterwards.
RESOURCE_WINDOW_COVERAGE_MIN_FRAC = 0.90

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


def parse_csv_timestamp(value: str) -> datetime | None:
    """Parse a ``ts_utc`` cell (RFC 3339 / ISO 8601), or return None.

    Accepts the trailing ``Z`` written by both producers as well as an
    explicit UTC offset; a naive timestamp is assumed to be UTC. Anything
    else is unparseable and rejects the file at ingest time.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


#: Defect classes of the strict numeric ingest rule (sprint P5.4 defect 4),
#: in the order they are reported. ``float()`` alone is not a numeric check:
#: it happily parses ``nan``, ``inf``, ``-inf`` and ``Infinity``, and none of
#: those is a measurement; a negative CPU percentage or memory figure is not
#: one either. Both classes are named separately so the rejection reason says
#: WHAT is wrong, not merely that the cell was refused.
NUMERIC_DEFECTS: tuple[str, ...] = ("non-numeric", "non-finite", "negative")


def _numeric_defect(value: str) -> str | None:
    """Classify a numeric resources.csv cell; None means it is acceptable.

    Strict rule (sprint P5.4 defect 4): a ``cpu_pct``/``mem_bytes``/
    ``mem_pct`` cell must parse as a float, be FINITE
    (:func:`math.isfinite` — ``nan``/``inf``/``-inf``/``Infinity`` are
    rejected) and be NON-NEGATIVE. The analysis side applies the same
    semantics.
    """
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return "non-numeric"
    if not math.isfinite(number):
        return "non-finite"
    if number < 0:
        return "negative"
    return None


def validate_resources_csv(
    path: str | Path,
    *,
    expected_host: str | None = None,
    min_samples: int = MIN_RESOURCE_SAMPLES,
    min_distinct_instants: int = MIN_DISTINCT_SAMPLE_INSTANTS,
    expected_window_s: float | None = None,
    expected_window_start_utc: str | datetime | None = None,
    expected_window_end_utc: str | datetime | None = None,
    max_sample_gap_s: float = MAX_SAMPLE_GAP_S,
) -> list[str]:
    """Validate a resources.csv before RUN-TIME ingestion (work order P1,
    hardened semantically in sprint P5 — report 5.4).

    Returns a list of human-readable problems; an empty list means the file
    is ingestible. Row COUNTING is not evidence of a sampled run: one
    ``docker stats`` sample writes one row per container, so 30 rows can be
    five seconds of six containers. Checks, in order:

    - the file exists and has a header line;
    - the header matches :data:`CSV_HEADER` EXACTLY (the 6-column schema
      with the ``host`` provenance column; the legacy 5-column schema is
      readable by the analysis for old fixtures but never ingestible for
      new runs);
    - per-row column completeness: every data row has exactly the six
      columns and a non-empty ``container``;
    - parseable RFC 3339 ``ts_utc`` timestamps;
    - STRICTLY numeric ``cpu_pct``, ``mem_bytes`` and ``mem_pct`` on every
      row: parseable, FINITE and NON-NEGATIVE (sprint P5.4 defect 4 — a bare
      ``float()`` accepts ``nan``/``inf``/``-inf``/``Infinity``, and a
      negative CPU percentage or memory figure is not a measurement either).
      Each rejection names the column and the row;
    - non-decreasing ``ts_utc`` (a collector never goes back in time; an
      out-of-order file means concatenated/edited evidence);
    - at least ``min_samples`` (:data:`MIN_RESOURCE_SAMPLES`) data rows AND
      at least ``min_distinct_instants``
      (:data:`MIN_DISTINCT_SAMPLE_INSTANTS`) DISTINCT sample instants;
    - every row carries a non-empty ``host`` value;
    - when ``expected_host`` is given (the SUT's node/hostname from
      sut_environment.json), every distinct ``host`` value equals it —
      a mismatch means the CSV was collected on the wrong machine;
    - when the real UTC bounds ``expected_window_start_utc`` and
      ``expected_window_end_utc`` are given, the sampled interval must
      overlap that exact measured window and cover at least
      :data:`RESOURCE_WINDOW_COVERAGE_MIN_FRAC` of it for every recorded
      container. The first/last sample and every consecutive pair in each
      container series must also respect
      :data:`~egw_experiments.protocol.MAX_SAMPLE_GAP_S`;
    - ``expected_window_s`` remains a backwards-compatible fallback for old
      manifests/callers that do not carry the real UTC bounds. It checks the
      sampled span, but cannot by itself prove that the CSV belongs to the
      right run;
    - irrespective of which window representation is available, consecutive
      distinct sample instants may not exceed ``max_sample_gap_s`` (the
      protocol's :data:`~egw_experiments.protocol.MAX_SAMPLE_GAP_S` by
      default).
    """
    path = Path(path)
    if not path.is_file():
        return [f"resources file not found: {path}"]
    data_rows = 0
    empty_host_rows = 0
    hosts: set[str] = set()
    instants: set[datetime] = set()
    container_instants: dict[str, set[datetime]] = {}
    bad_columns: list[str] = []
    bad_container: list[str] = []
    bad_timestamps: list[str] = []
    # {defect kind: {column: ["line N: <cell>", ...]}} (sprint P5.4 defect 4).
    bad_numeric: dict[str, dict[str, list[str]]] = {}
    out_of_order: list[str] = []
    first_instant: datetime | None = None
    last_instant: datetime | None = None
    previous: datetime | None = None
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
            for lineno, row in enumerate(reader, start=2):
                if not row or not any(cell.strip() for cell in row):
                    continue
                data_rows += 1
                if len(row) != len(CSV_HEADER):
                    bad_columns.append(f"line {lineno} has {len(row)}")
                    continue
                ts_raw, container, cpu_pct, mem_bytes, mem_pct, host = row
                container_name = container.strip()
                if not container_name:
                    bad_container.append(f"line {lineno}")
                for name, value in (
                    ("cpu_pct", cpu_pct),
                    ("mem_bytes", mem_bytes),
                    ("mem_pct", mem_pct),
                ):
                    defect = _numeric_defect(value)
                    if defect is not None:
                        bad_numeric.setdefault(defect, {}).setdefault(
                            name, []
                        ).append(f"line {lineno}: {value!r}")
                host = host.strip()
                if host:
                    hosts.add(host)
                else:
                    empty_host_rows += 1
                stamp = parse_csv_timestamp(ts_raw)
                if stamp is None:
                    bad_timestamps.append(f"line {lineno}: {ts_raw!r}")
                    continue
                instants.add(stamp)
                if container_name:
                    container_instants.setdefault(container_name, set()).add(stamp)
                if first_instant is None or stamp < first_instant:
                    first_instant = stamp
                if last_instant is None or stamp > last_instant:
                    last_instant = stamp
                if previous is not None and stamp < previous:
                    out_of_order.append(f"line {lineno}: {ts_raw.strip()}")
                previous = stamp
    except OSError as exc:
        return [f"resources file unreadable: {exc}"]

    def _head(items: list[str], limit: int = 3) -> str:
        shown = "; ".join(items[:limit])
        return shown + ("; ..." if len(items) > limit else "")

    problems: list[str] = []
    if bad_columns:
        problems.append(
            f"{len(bad_columns)} row(s) with an incomplete column set "
            f"(every sample needs the {len(CSV_HEADER)} columns "
            f"{','.join(CSV_HEADER)}): {_head(bad_columns)}"
        )
    if bad_container:
        problems.append(
            f"{len(bad_container)} row(s) without a container name: "
            + _head(bad_container)
        )
    if bad_timestamps:
        problems.append(
            f"{len(bad_timestamps)} row(s) with an unparseable RFC 3339 "
            f"ts_utc timestamp: {_head(bad_timestamps)}"
        )
    for defect in NUMERIC_DEFECTS:
        by_column = bad_numeric.get(defect) or {}
        for name in ("cpu_pct", "mem_bytes", "mem_pct"):
            offenders = by_column.get(name)
            if not offenders:
                continue
            problems.append(
                f"{len(offenders)} row(s) with a {defect} {name} value"
                + (
                    " (nan/inf are not measurements)"
                    if defect == "non-finite"
                    else ""
                )
                + ": "
                + _head(offenders)
            )
    if out_of_order:
        problems.append(
            f"ts_utc is not non-decreasing ({len(out_of_order)} row(s) go "
            f"back in time): {_head(out_of_order)}"
        )
    if data_rows == 0:
        problems.append("no data rows beyond the header")
    elif data_rows < min_samples:
        problems.append(
            f"only {data_rows} sample row(s); at least {min_samples} "
            "required (MIN_RESOURCE_SAMPLES: 1 Hz collector over the "
            "shortest 30 s timed run)"
        )
    if data_rows and len(instants) < min_distinct_instants:
        problems.append(
            f"only {len(instants)} distinct sample instant(s) across "
            f"{data_rows} row(s); at least {min_distinct_instants} required "
            "(MIN_DISTINCT_SAMPLE_INSTANTS: one docker-stats sample writes "
            "one row per container, so row count alone is not evidence of a "
            "sampled run)"
        )
    if len(container_instants) > 1:
        for container_name, series_instants in sorted(container_instants.items()):
            if len(series_instants) < min_distinct_instants:
                problems.append(
                    f"container {container_name!r} has only "
                    f"{len(series_instants)} distinct sample instant(s); at "
                    f"least {min_distinct_instants} are required per "
                    "container"
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
    def _window_bound(
        value: str | datetime | None,
    ) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return parse_csv_timestamp(value) if isinstance(value, str) else None

    window_start: datetime | None = None
    window_end: datetime | None = None
    bounds_given = (
        expected_window_start_utc is not None
        or expected_window_end_utc is not None
    )
    valid_window_bounds = False
    if bounds_given:
        if (
            expected_window_start_utc is None
            or expected_window_end_utc is None
        ):
            problems.append(
                "both expected_window_start_utc and expected_window_end_utc "
                "are required to validate the real measured window"
            )
        else:
            window_start = _window_bound(expected_window_start_utc)
            window_end = _window_bound(expected_window_end_utc)
            if window_start is None or window_end is None:
                problems.append(
                    "the expected measured-window UTC bounds are not "
                    "parseable RFC 3339 timestamps"
                )
            elif window_end <= window_start:
                problems.append(
                    "expected_window_end_utc must be later than "
                    "expected_window_start_utc"
                )
            else:
                valid_window_bounds = True

    overlap_s: float | None = None
    if valid_window_bounds:
        assert window_start is not None and window_end is not None
        window_s = (window_end - window_start).total_seconds()
        if first_instant is None or last_instant is None:
            overlap_s = 0.0
        else:
            overlap_start = max(first_instant, window_start)
            overlap_end = min(last_instant, window_end)
            overlap_s = max(0.0, (overlap_end - overlap_start).total_seconds())
        if overlap_s <= 0:
            problems.append(
                "the sampled instants do not effectively overlap the run's "
                "real measured_window_utc"
            )
        required_s = window_s * RESOURCE_WINDOW_COVERAGE_MIN_FRAC
        if overlap_s < required_s:
            problems.append(
                f"resource samples cover only {overlap_s:.1f} s "
                f"({overlap_s / window_s:.1%}) of the run's real measured "
                f"window ({window_s:.1f} s), below the required "
                f"{RESOURCE_WINDOW_COVERAGE_MIN_FRAC:.0%} "
                "(RESOURCE_WINDOW_COVERAGE_MIN_FRAC, pending advisor "
                "sign-off)"
            )
        if len(container_instants) > 1:
            for container_name, series_instants in sorted(
                container_instants.items()
            ):
                series_first = min(series_instants)
                series_last = max(series_instants)
                series_overlap_start = max(series_first, window_start)
                series_overlap_end = min(series_last, window_end)
                series_overlap_s = max(
                    0.0,
                    (series_overlap_end - series_overlap_start).total_seconds(),
                )
                if series_overlap_s < required_s:
                    problems.append(
                        f"container {container_name!r} resource samples cover "
                        f"only {series_overlap_s:.1f} s "
                        f"({series_overlap_s / window_s:.1%}) of the run's "
                        f"real measured window, below the required "
                        f"{RESOURCE_WINDOW_COVERAGE_MIN_FRAC:.0%}"
                    )
    elif not bounds_given and expected_window_s is not None and expected_window_s > 0:
        span_s = (
            (last_instant - first_instant).total_seconds()
            if first_instant is not None and last_instant is not None
            else 0.0
        )
        required_s = float(expected_window_s) * RESOURCE_WINDOW_COVERAGE_MIN_FRAC
        if span_s < required_s:
            problems.append(
                f"the sampled instants span only {span_s:.1f} s, so less "
                f"than {RESOURCE_WINDOW_COVERAGE_MIN_FRAC:.0%} of the run's "
                f"measured window ({float(expected_window_s):.1f} s) is "
                "covered by resource samples "
                "(RESOURCE_WINDOW_COVERAGE_MIN_FRAC, pending advisor "
                "sign-off)"
            )
        if len(container_instants) > 1:
            for container_name, series_instants in sorted(
                container_instants.items()
            ):
                series_span_s = (
                    max(series_instants) - min(series_instants)
                ).total_seconds()
                if series_span_s < required_s:
                    problems.append(
                        f"container {container_name!r} sample instants span "
                        f"only {series_span_s:.1f} s, below the required "
                        f"{RESOURCE_WINDOW_COVERAGE_MIN_FRAC:.0%} of the "
                        "measured window"
                    )

    if max_sample_gap_s <= 0:
        problems.append("max_sample_gap_s must be positive")
    else:
        gaps: list[tuple[str, float]] = []
        series_by_name = container_instants or {"all containers": instants}
        for container_name, series_instants in sorted(series_by_name.items()):
            ordered_instants = sorted(series_instants)
            prefix = f"container {container_name!r}: "
            if valid_window_bounds and ordered_instants:
                assert window_start is not None and window_end is not None
                series_first = ordered_instants[0]
                series_last = ordered_instants[-1]
                series_overlap_s = max(
                    0.0,
                    (
                        min(series_last, window_end)
                        - max(series_first, window_start)
                    ).total_seconds(),
                )
                if series_overlap_s <= 0:
                    continue
                if series_first > window_start:
                    gaps.append(
                        (
                            prefix + "measured-window start to first sample",
                            (series_first - window_start).total_seconds(),
                        )
                    )
                for left, right in zip(
                    ordered_instants, ordered_instants[1:]
                ):
                    if right < window_start or left > window_end:
                        continue
                    gaps.append(
                        (
                            prefix
                            + f"{left.isoformat()} to {right.isoformat()}",
                            (right - left).total_seconds(),
                        )
                    )
                if series_last < window_end:
                    gaps.append(
                        (
                            prefix + "last sample to measured-window end",
                            (window_end - series_last).total_seconds(),
                        )
                    )
            elif not valid_window_bounds:
                gaps.extend(
                    (
                        prefix + f"{left.isoformat()} to {right.isoformat()}",
                        (right - left).total_seconds(),
                    )
                    for left, right in zip(
                        ordered_instants, ordered_instants[1:]
                    )
                )
        excessive = [(label, gap) for label, gap in gaps if gap > max_sample_gap_s]
        if excessive:
            shown = "; ".join(
                f"{label} ({gap:.1f} s)" for label, gap in excessive[:3]
            )
            if len(excessive) > 3:
                shown += "; ..."
            problems.append(
                f"{len(excessive)} sampling gap(s) exceed the protocol "
                f"maximum of {max_sample_gap_s:g} s (MAX_SAMPLE_GAP_S): "
                f"{shown}"
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
