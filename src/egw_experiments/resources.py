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
- The proved-down interval of decision 1a (adopted 2026-09-30, prospective):
  given a :class:`ProvedDownInterval` (``proved_down=``), the validator
  judges the restarted container's gap across its restart by the interval's
  edges instead of as one gap (:func:`proved_down_outcomes`). Only the
  harness's run-time ingest of a ``controller_restart`` run given the
  StartedAt read passes one (``egw_experiments.proved_down``); without it
  every result and every problem text is the one the file always had.
- The restart transition rule (:data:`TRANSITION_RULE`; option A of the T6
  page, qualified, adopted by the student on 2026-10-05, prospective): given
  a :class:`LifecycleWitness` as well (``transition_witness=``), the
  restarted container's rows stamped after ``sec(D)`` and at or before
  ``sec(S)`` (never past ``sec(E)``) are admitted, not rejected, when the
  collector's own lifecycle record shows that container's id disappear and
  then appear at the positions the rule names (:func:`transition_outcomes`);
  they are reported apart. Only the harness's run-time ingest passes one, and
  only when ``run --restart-transition-rule`` asks for it.
"""

from __future__ import annotations

import csv
import json
import math
import platform
import subprocess
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .protocol import (
    MAX_SAMPLE_GAP_S,
    RESOURCE_SAMPLE_INTERVAL_S,
    RESTART_RECOVERY_MAX_S,
)

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


_NS_PER_S = 1_000_000_000
_RESTART_RECOVERY_MAX_NS = round(RESTART_RECOVERY_MAX_S * _NS_PER_S)


def whole_second(ns: int) -> datetime:
    """``sec(x)`` of decision 1a: the whole UTC second containing the instant
    ``ns`` (integer nanoseconds since the epoch, floored), the resolution of
    the collector's rows, which it stamps in whole seconds."""
    return datetime.fromtimestamp(ns // _NS_PER_S, tz=timezone.utc)


def ns_utc_text(ns: int) -> str:
    """An instant in integer nanoseconds as RFC 3339 UTC text with nine
    fractional digits (``2026-10-01T10:01:00.400000000Z``)."""
    return whole_second(ns).strftime("%Y-%m-%dT%H:%M:%S") + f".{ns % _NS_PER_S:09d}Z"


@dataclass(frozen=True)
class ProvedDownInterval:
    """The proved-down interval of one restarted container (decision 1a,
    adopted 2026-09-30, prospective): the Docker ``die`` (D) and ``start``
    (S) of ``container``, both in integer nanoseconds on the GUEST clock,
    the clock of the resource rows. ``egw_experiments.proved_down`` derives
    it from a run's complete events capture and its StartedAt read; the
    validator is only ever handed one that derivation established.

    The effective end is E = min(S, D + RESTART_RECOVERY_MAX_S): the
    ordinary rule resumes from E even when S is later (``capped``)."""

    container: str
    die_ns: int
    start_ns: int

    @property
    def effective_end_ns(self) -> int:
        return min(self.start_ns, self.die_ns + _RESTART_RECOVERY_MAX_NS)

    @property
    def capped(self) -> bool:
        return self.start_ns > self.die_ns + _RESTART_RECOVERY_MAX_NS


def proved_down_outcomes(
    instants: Iterable[datetime], interval: ProvedDownInterval
) -> dict[str, Any]:
    """What the proved-down interval does to one container's sample instants
    (decision 1a), in whole seconds: ``sec(D)``, ``sec(S)`` and ``sec(E)``
    (:func:`whole_second`) against the rows.

    - the rows stamped at or before ``sec(D)`` (the last of them opens the
      edge before), those strictly between ``sec(D)`` and ``sec(S)`` (no
      instance was running to measure), those in ``sec(S)`` itself (less than
      one sampling interval, :data:`RESOURCE_SAMPLE_INTERVAL_S`, after S) and
      those at least one sampling interval after ``sec(S)`` (the first of
      them closes the edge after);
    - the interval applies only when the container has a row on both sides:
      at or before ``sec(D)`` and after ``sec(S)``. Otherwise ``applies`` is
      False with ``why_not``, and the ordinary rule decides the file;
    - when it applies, the one pair (last row before, first row after) is
      replaced by two gaps: ``edge_gap_before_s`` = ``sec(D)`` - the last
      row before and ``edge_gap_after_s`` = the first row after - ``sec(E)``
      (the ordinary rule resumes from E, so when capped the time from
      D + RESTART_RECOVERY_MAX_S to S is part of the edge after); the rows
      between and in ``sec(S)`` are ``rejected_rows``.

    Pure: no row is added, removed, zero-filled or interpolated.
    """
    ordered = sorted(set(instants))
    sec_d = whole_second(interval.die_ns)
    sec_s = whole_second(interval.start_ns)
    sec_e = whole_second(interval.effective_end_ns)
    one_interval = timedelta(seconds=RESOURCE_SAMPLE_INTERVAL_S)
    before = [t for t in ordered if t <= sec_d]
    between = [t for t in ordered if sec_d < t < sec_s]
    in_start_second = [t for t in ordered if sec_s <= t < sec_s + one_interval]
    after = [t for t in ordered if t >= sec_s + one_interval]
    outcome: dict[str, Any] = {
        "container": interval.container,
        "applies": False,
        "why_not": None,
        "capped": interval.capped,
        "interval_s": (interval.start_ns - interval.die_ns) / _NS_PER_S,
        "exempt_s": (interval.effective_end_ns - interval.die_ns) / _NS_PER_S,
        "die_second_utc": sec_d.isoformat(),
        "start_second_utc": sec_s.isoformat(),
        "effective_end_second_utc": sec_e.isoformat(),
        "last_row_before_die": before[-1].isoformat() if before else None,
        "first_row_after_start": after[0].isoformat() if after else None,
        "edge_gap_before_s": None,
        "edge_gap_after_s": None,
        "rows_between": [t.isoformat() for t in between],
        "rows_in_start_second": [t.isoformat() for t in in_start_second],
        "rejected_rows": [],
    }
    if interval.start_ns <= interval.die_ns:
        outcome["why_not"] = "the start is not after the die"
    elif not before:
        outcome["why_not"] = (
            f"container {interval.container!r} has no row stamped at or before "
            f"the die's second {sec_d.isoformat()}"
        )
    elif not after:
        outcome["why_not"] = (
            f"container {interval.container!r} has no row stamped after the "
            f"start's second {sec_s.isoformat()}"
        )
    else:
        outcome["applies"] = True
        outcome["edge_gap_before_s"] = (sec_d - before[-1]).total_seconds()
        outcome["edge_gap_after_s"] = (after[0] - sec_e).total_seconds()
        outcome["rejected_rows"] = [
            t.isoformat() for t in sorted(set(between) | set(in_start_second))
        ]
    return outcome


#: The identity of the restart transition rule: option A of the T6 page
#: (docs/governance/proposals/2026-10-03-t6-sampling-versus-restart-events.md),
#: with the Project Manager's conditions, adopted by the student on
#: 2026-10-05 for the new G3 T6 run, prospective. A run that applies it names
#: it (``run --restart-transition-rule``, the manifest's
#: ``resources_transition_rows.rule``); no other rule has a name here.
TRANSITION_RULE = "1a-option-a-2026-10-05"


@dataclass(frozen=True)
class LifecycleRecord:
    """One row of the collector's ``.lifecycle.csv`` (collect-resources.sh):
    the whole UTC second of the sample that noticed it, the event
    (``appeared``, ``disappeared``, ``counter_reset`` or ``named``), the
    container id and the name, as written."""

    stamp: datetime
    event: str
    container_id: str
    name: str


@dataclass(frozen=True)
class LifecycleWitness:
    """What the collector's own lifecycle record of a run says of the
    restarted ``container``: its rows naming ``container_id`` (the id of the
    die/start pair) or the container's name, in file order. ``problem`` says
    why the record could not be read as the collector writes it (missing,
    unreadable, malformed, out of order, or no id to match); a witness with a
    problem grants nothing. ``egw_experiments.proved_down`` reads it.

    The record is the same instrument's, not independent proof: it shows
    when the collector stopped and started finding the container's cgroup."""

    container: str
    container_id: str | None
    records: tuple[LifecycleRecord, ...] = ()
    problem: str | None = None


def transition_outcomes(
    instants: Iterable[datetime],
    interval: ProvedDownInterval,
    witness: LifecycleWitness,
) -> dict[str, Any]:
    """What the restart transition rule (:data:`TRANSITION_RULE`) makes of
    one container's sample instants, in whole seconds.

    The candidate *transition rows* are the instants ``t`` with
    ``sec(D) < t <= min(sec(S), sec(E))``, and only when ``sec(S) > sec(D)``:
    a die and a start in one second leave that second's row rejected, as
    decision 1a always did. They are admitted only when the proved-down
    interval applies (a row at or before ``sec(D)`` and one at least a
    sampling interval after ``sec(S)``) and the witness, read without a
    problem, holds between the last row at or before ``sec(D)`` (excluded)
    and the first row after the start (included) exactly two rows of the
    container: its id ``disappeared``, then the same id ``appeared``, both
    under the container's name, the ``appeared`` at or before the first
    candidate; and no row naming the container under another id. Anything
    else - missing, wrong, late, inconsistent or unreadable - admits
    nothing. The values of a row play no part: a zero alone proves nothing.

    Admitted rows neither open nor close an edge, the edges, D, S, E and the
    120 s cap stay decision 1a's, and nothing is added, removed or filled.
    Returns ``rule``, ``container``, ``container_id``, ``admitted``,
    ``why_not``, ``after_second_utc`` (``sec(D)``), ``through_second_utc``,
    the candidates' ``instants`` and the pair's ``disappeared_utc`` and
    ``appeared_utc`` (None until found). Pure."""
    ordered = sorted(set(instants))
    sec_d = whole_second(interval.die_ns)
    sec_s = whole_second(interval.start_ns)
    through = min(sec_s, whole_second(interval.effective_end_ns))
    one_interval = timedelta(seconds=RESOURCE_SAMPLE_INTERVAL_S)
    name, cid = interval.container, witness.container_id
    outcome: dict[str, Any] = {
        "rule": TRANSITION_RULE,
        "container": name,
        "container_id": cid,
        "admitted": False,
        "why_not": None,
        "after_second_utc": sec_d.isoformat(),
        "through_second_utc": through.isoformat(),
        "instants": [],
        "disappeared_utc": None,
        "appeared_utc": None,
    }

    def no(why: str) -> dict[str, Any]:
        outcome["why_not"] = why
        return outcome

    if sec_s <= sec_d:
        return no(
            f"the die and the start of {name!r} fall in one whole second "
            f"({sec_d.isoformat()}): no row is a transition row (sec(S) > "
            "sec(D) is required), and that second's row stays rejected, as "
            "decision 1a's conservative case"
        )
    candidates = [t for t in ordered if sec_d < t <= through]
    outcome["instants"] = [t.isoformat() for t in candidates]
    before = [t for t in ordered if t <= sec_d]
    after = [t for t in ordered if t >= sec_s + one_interval]
    if not before or not after:
        return no(
            f"the proved-down interval does not apply to {name!r} (no row at "
            "or before the die's second, or none after the start's), so no row "
            "is a transition row"
        )
    if not candidates:
        return no(
            f"no row of {name!r} is stamped after the die's second "
            f"{sec_d.isoformat()} and at or before {through.isoformat()}"
        )
    if witness.problem is not None:
        return no(witness.problem)
    last_before, first_after, first_row = before[-1], after[0], candidates[0]
    span = [r for r in witness.records if last_before < r.stamp <= first_after]
    between = (
        f"between its last row before the die ({last_before.isoformat()}) and "
        f"its first row after the start ({first_after.isoformat()})"
    )
    foreign = [r for r in span if r.container_id != cid]
    if foreign:
        return no(
            f"the collector's lifecycle record names {name!r} under another "
            f"container id ({foreign[0].container_id}) {between}: inconsistent, "
            "so it grants nothing"
        )
    events = [r.event for r in span]
    if events != ["disappeared", "appeared"]:
        return no(
            f"the collector's lifecycle record of container id {cid} {between} "
            f"is {events or 'empty'}, not exactly one 'disappeared' then one "
            "'appeared': no unambiguous pair, so it grants nothing"
        )
    gone, back = span
    outcome["disappeared_utc"] = gone.stamp.isoformat()
    outcome["appeared_utc"] = back.stamp.isoformat()
    misnamed = [r.name for r in span if r.name != name]
    if misnamed:
        return no(
            f"the collector's lifecycle record of container id {cid} names it "
            f"{misnamed[0]!r}, not {name!r}, {between}: inconsistent, so it "
            "grants nothing"
        )
    if not gone.stamp < back.stamp:
        return no(
            f"the collector's lifecycle record has container id {cid} disappear "
            f"and appear in one second ({gone.stamp.isoformat()}): inconsistent, "
            "so it grants nothing"
        )
    if back.stamp > first_row:
        return no(
            f"the collector's lifecycle record has container id {cid} appear at "
            f"{back.stamp.isoformat()}, after the first transition row "
            f"{first_row.isoformat()}: late, so it grants nothing"
        )
    outcome["admitted"] = True
    return outcome


def _series_pairs(
    ordered: list[datetime],
    span: tuple[datetime, datetime] | None = None,
    edges: tuple[tuple[str, float], ...] = (),
):
    """The consecutive pairs of one container's ordered instants as
    ``(label, left, right, gap_s)``. With ``span`` (the proved-down
    interval's last row before the die and first row after the start) the
    pairs inside it are replaced, in their place, by ``edges`` (the two edge
    gaps, labelled), which share the span's bounds for the window test.
    Without it, exactly the pairs and labels the validator always judged."""
    for left, right in zip(ordered, ordered[1:]):
        if span is not None and span[0] <= left and right <= span[1]:
            if left == span[0]:
                for label, gap in edges:
                    yield label, span[0], span[1], gap
            continue
        yield (
            f"{left.isoformat()} to {right.isoformat()}",
            left,
            right,
            (right - left).total_seconds(),
        )


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
    proved_down: ProvedDownInterval | None = None,
    proved_down_outcome: dict[str, Any] | None = None,
    transition_witness: LifecycleWitness | None = None,
    transition_outcome: dict[str, Any] | None = None,
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

    ``proved_down`` (keyword-only; decision 1a, adopted 2026-09-30): the
    proved-down interval of the one container a ``controller_restart`` run
    restarted, established from the run's events capture and StartedAt read
    (``egw_experiments.proved_down``). When that container has a row on both
    sides of it (:func:`proved_down_outcomes`), its one gap across the
    restart is judged as two edge gaps against ``max_sample_gap_s``, and its
    rows between the die and the start, or in the start's own second, are
    each a problem; every other check, gap and container is unchanged. With
    ``proved_down_outcome`` (a dict) the outcomes are written into it. With
    ``proved_down`` None (the default) the code path and every problem text
    are the ones the validator always had.

    ``transition_witness`` (keyword-only; the restart transition rule,
    :data:`TRANSITION_RULE`, adopted 2026-10-05): with ``proved_down``, the
    collector's lifecycle record of the restarted container. The rows
    :func:`transition_outcomes` admits are no longer problems of the
    proved-down interval; every other check stands, and the rows count, as
    every row always did, for the distinct instants, the coverage and the
    gaps (inside the interval's span, where the two edges replace the pairs).
    With ``transition_outcome`` (a dict) the rule's outcomes are written into
    it, with the candidate rows' raw cells (``rows``: line, ``ts_utc``,
    ``cpu_pct``, ``mem_bytes``, ``mem_pct``) and their ``count``, and
    ``proved_down_outcome``'s ``rejected_rows`` lists only the rows still
    rejected. Without ``proved_down`` it is ignored; None (the default) is the
    validator of decision 1a, problem for problem.
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
    # The restarted container's rows as written (stamp, line, raw cells), kept
    # only for the transition rule's report.
    restarted_rows: list[tuple[datetime, int, str, str, str, str]] | None = (
        [] if proved_down is not None and transition_witness is not None else None
    )
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
                if (
                    restarted_rows is not None
                    and container_name == proved_down.container
                ):
                    restarted_rows.append(
                        (stamp, lineno, ts_raw, cpu_pct, mem_bytes, mem_pct)
                    )
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

    # The proved-down interval (decision 1a): the restarted container's rows
    # against it, its own problems, and the span whose one pair its two edge
    # gaps replace below. None of this runs without an interval.
    pd_span: tuple[datetime, datetime] | None = None
    pd_edges: tuple[tuple[str, float], ...] = ()
    if proved_down is not None:
        pd_outcome = proved_down_outcomes(
            container_instants.get(proved_down.container, ()), proved_down
        )
        # The restart transition rule (adopted 2026-10-05): the rows it
        # admits leave decision 1a's rejections; nothing else changes.
        admitted: set[str] = set()
        if transition_witness is not None:
            t_outcome = transition_outcomes(
                container_instants.get(proved_down.container, ()),
                proved_down,
                transition_witness,
            )
            candidates = set(t_outcome["instants"])
            t_outcome["rows"] = [
                {
                    "line": lineno,
                    "ts_utc": ts_raw,
                    "cpu_pct": cpu,
                    "mem_bytes": mem,
                    "mem_pct": pct,
                }
                for stamp, lineno, ts_raw, cpu, mem, pct in restarted_rows or ()
                if stamp.isoformat() in candidates
            ]
            t_outcome["count"] = len(t_outcome["rows"])
            if t_outcome["admitted"]:
                admitted = candidates
                pd_outcome["rejected_rows"] = [
                    t for t in pd_outcome["rejected_rows"] if t not in admitted
                ]
            if transition_outcome is not None:
                transition_outcome.update(t_outcome)
        if proved_down_outcome is not None:
            proved_down_outcome.update(pd_outcome)
        if pd_outcome["applies"]:
            pd_name = proved_down.container
            die_text = ns_utc_text(proved_down.die_ns)
            start_text = ns_utc_text(proved_down.start_ns)
            rows_between = [t for t in pd_outcome["rows_between"] if t not in admitted]
            rows_in_start_second = [
                t for t in pd_outcome["rows_in_start_second"] if t not in admitted
            ]
            if rows_between:
                problems.append(
                    f"{len(rows_between)} row(s) of container "
                    f"{pd_name!r} stamped between the die at {die_text} and "
                    f"the start at {start_text}, when no instance of it was "
                    "running to measure (the proved-down interval, decision "
                    "1a): rejected whatever their values: "
                    + _head(rows_between)
                )
            if rows_in_start_second:
                problems.append(
                    f"{len(rows_in_start_second)} row(s) of "
                    f"container {pd_name!r} stamped in the second of the start "
                    f"at {start_text}, less than one sampling interval "
                    f"(RESOURCE_SAMPLE_INTERVAL_S, {RESOURCE_SAMPLE_INTERVAL_S:g} "
                    "s) after it: the first row after the proved-down interval "
                    "(decision 1a) must be at least one sampling interval "
                    "after the start's second: "
                    + _head(rows_in_start_second)
                )
            last_before = parse_csv_timestamp(pd_outcome["last_row_before_die"])
            first_after = parse_csv_timestamp(pd_outcome["first_row_after_start"])
            assert last_before is not None and first_after is not None
            pd_span = (last_before, first_after)
            pd_edges = (
                (
                    f"{pd_outcome['last_row_before_die']} to the die's second "
                    f"{pd_outcome['die_second_utc']} (edge before the "
                    "proved-down interval, decision 1a)",
                    pd_outcome["edge_gap_before_s"],
                ),
                (
                    f"the effective end's second "
                    f"{pd_outcome['effective_end_second_utc']} to "
                    f"{pd_outcome['first_row_after_start']} (edge after the "
                    "proved-down interval, decision 1a"
                    + (
                        ", resumed from the die plus RESTART_RECOVERY_MAX_S"
                        if proved_down.capped
                        else ""
                    )
                    + ")",
                    pd_outcome["edge_gap_after_s"],
                ),
            )

    if max_sample_gap_s <= 0:
        problems.append("max_sample_gap_s must be positive")
    else:
        gaps: list[tuple[str, float]] = []
        series_by_name = container_instants or {"all containers": instants}
        for container_name, series_instants in sorted(series_by_name.items()):
            ordered_instants = sorted(series_instants)
            prefix = f"container {container_name!r}: "
            span = (
                pd_span
                if proved_down is not None and container_name == proved_down.container
                else None
            )
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
                for label, left, right, gap in _series_pairs(
                    ordered_instants, span, pd_edges
                ):
                    if right < window_start or left > window_end:
                        continue
                    gaps.append((prefix + label, gap))
                if series_last < window_end:
                    gaps.append(
                        (
                            prefix + "last sample to measured-window end",
                            (window_end - series_last).total_seconds(),
                        )
                    )
            elif not valid_window_bounds:
                gaps.extend(
                    (prefix + label, gap)
                    for label, _left, _right, gap in _series_pairs(
                        ordered_instants, span, pd_edges
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
