"""Execute one planned run from the harness host, OFF the ARM VM
(plan 5.1/5.8, CONTRACTS 5/7; audit 2026-08-08 section 9 corrections).

Plan 5.1 requires the simulator to run off the ARM VM during benchmarks, so
this harness (which drives the simulator as a subprocess) runs off the VM
too: ``--broker`` is the VM's address and the connection uses port 8883
with TLS (CONTRACTS 1).

Evidence collection topology (audit 9.1-9.3):

- The controller writes its per-run ``events.jsonl`` ON the VM (under its
  ``EGW_EVENT_LOG_DIR``). After the 60 s confirmation window the runner
  collects it AUTOMATICALLY via a configurable fetch command template
  (``--fetch-events-cmd`` or env ``EGW_FETCH_EVENTS_CMD``) with
  ``{run_id}`` and ``{dest}`` placeholders, executed with up to 3 attempts
  and exponential backoff, e.g.::

      --fetch-events-cmd "scp vm:/opt/egw/data/events/{run_id}/events.jsonl {dest}"

  When no template is configured the runner falls back to the local
  event-log directory lookup (dev only). If collection still fails the run
  is recoverable with the ``collect`` subcommand (below) — SHA256SUMS is
  only written after successful collection.
- SUT resources are collected ON the VM by
  ``src/deployment/scripts/collect-resources.sh`` (1 Hz docker stats CSV)
  and ingested with ``--resources-from <fetched file>``. The LOCAL
  ``ResourceSampler`` is opt-in via ``--local-resources`` and is for dev
  only: it measures the load-generator host, NOT the SUT (audit 9.1). The
  manifest records ``resource_source`` ('sut-collector' | 'local-dev' |
  'none').
- The SUT environment is captured ON the VM by
  ``src/deployment/scripts/capture-sut-environment.sh`` and ingested with
  ``--sut-env-from`` (or env ``EGW_SUT_ENV_FILE``); the harness host's own
  capture is written as ``loadgen_environment.json`` (audit 9.2). The
  manifest references BOTH files.
- The controller's ``GET /metrics`` (CONTRACTS v1.1: includes ``dropped``
  and ``queue_depth``) is sampled at 1 Hz into ``controller_metrics.csv``
  when ``--controller-url`` is given (port 8000 is loopback-only on the
  VM; use an SSH tunnel, see the deployment README).

Validity (audit: warning-only is NOT acceptable; hardened by work order
P1): timed runs (every simulator-driven condition) REQUIRE

- a usable ``sut_environment.json`` (present AND carrying the
  REQUIRED_SUT_FIELDS of ``environment.py``: node/hostname, positive
  ``nproc``, OS identification);
- SUT resources with ``resource_source == 'sut-collector'`` — the
  ``--local-resources`` dev sampler measures the load generator and makes
  a timed run INVALID; the ingested CSV is content-validated (exact
  6-column header with ``host`` provenance, >= MIN_RESOURCE_SAMPLES rows,
  every ``host`` matching the SUT's node) or it is treated as missing;
- a clean simulator exit (non-zero exit => invalid, no override);
- a clean warm-up exit (non-zero => invalid unless
  ``--allow-warmup-failure``, which records a protocol deviation);
- the planned warm-up: ``--skip-warmup`` on nominal/load_sweep/soak =>
  invalid unless ``--allow-protocol-deviation`` (deviation recorded).

Otherwise the manifest is marked ``validity: 'invalid'`` with explicit
reasons. The only overrides are the explicit ``--allow-missing-sut-env`` /
``--allow-missing-resources`` / ``--allow-warmup-failure`` /
``--allow-protocol-deviation`` flags; every override that takes effect is
recorded in the manifest's ``deviations`` list ({kind, detail,
authorized_by_flag}), alongside shortened confirmation windows or skipped
cooldowns. The analysis surfaces the deviations per run and aggregates
ONLY runs with ``validity == 'valid'``.

Measured window (audit 9.4): the manifest records ``measured_window_utc``
{start, end} — harness wall-clock stamps taken immediately around the
measured simulator invocation — plus ``measured_started_monotonic_ns``.
The wall-clock window assumes NTP-synchronized clocks between the harness
host and the VM; that is acceptable for windowing 1 Hz resource/metrics
samples (sub-second error against a >=300 s window) and is NEVER used for
latency, which stays monotonic and single-host (CONTRACTS 5). The analysis
filters ``resources.csv`` and ``controller_metrics.csv`` to this window;
``events.jsonl`` needs no such filtering because the warm-up runs under a
different ``run_id`` (``<run_id>.warmup``).

External conditions (audit 9.6): ``cold_start``, ``twin_creation`` and
``qemu_boot`` runs are ingested with ``--external-timings <timings.json>``
(operator-produced: ``{run_id, condition, samples:[{label, started_utc,
ended_utc, duration_s}], method, notes}``) plus optional ``--external-logs
<dir>``, producing the standard manifest + SHA256SUMS so the single
analysis script covers them (claim C15). The samples are validated before
anything is written: each ``duration_s`` must be a real, finite,
non-negative number (a bool is not a number and ``nan``/``inf`` are not
measurements), and each sample of a FUNCTIONAL external condition
(``qemu_boots``, which plan 5.1 keeps functional-only) must carry an
``outcome`` of ``"pass"``/``"fail"`` — the boot result IS the measurement,
so a sample without one seals no evidence.

Controller restart hook (audit 9.5, claim C12): ``--restart-cmd`` is a
command template (``{run_id}`` placeholder) executed exactly once,
``--restart-at-s`` seconds into the measured run, via subprocess; the
attempt is recorded in the manifest with timestamps and exit code.

Produces the plan 5.8 raw structure::

    results/raw/<run_id>/
      events.jsonl             # controller log (fetched from the VM)
      sent_events.jsonl        # simulator log
      resources.csv            # 1 Hz SUT docker stats (ingested)
      controller_metrics.csv   # 1 Hz controller /metrics samples
      manifest.json            # scenario, seed, commit, digests, env refs,
                               # config echo, timestamps, measured window,
                               # validity, deviations, protocol version,
                               # exclusion
      sut_environment.json     # captured ON the VM (ingested)
      loadgen_environment.json # captured here (harness host)
      logs/                    # simulator stdout/stderr, warmup artifacts
      SHA256SUMS               # written last, ONLY after successful
                               # collection; covers every file above

Warm-up note (CONTRACTS >= v1.1): the warm-up reuses the run's seed, hence
the same ``device_uuid`` set as the measured run. This is intentional: it
warms the real twins the measured run will patch. The measured run then
restarts ``seq`` at 0 under a distinct ``run_id``, which is safe only with
a controller implementing CONTRACTS >= v1.1 run-scoped dedupe (section 4:
the ``seq`` floor applies only within the same ``run_id`` and resets when
``run_id`` changes). With an older controller the measured run's first
messages would be misclassified as duplicates, corrupting the delivery
rate.

Clock-domain note (CONTRACTS v1.1): because the harness runs off the ARM
VM, its ``time.monotonic_ns()`` values are NOT comparable with the
controller's (monotonic clocks are per-host). The confirmation deadline is
therefore anchored on a CONTROLLER-side marker (sprint P5, report 5.2):
immediately after the measured simulator process exits and BEFORE the
confirmation window, the runner polls ``GET {controller_url}/metrics`` with
a plain stdlib request and records

- ``controller_monotonic_at_run_end_ns`` — the controller's own
  ``monotonic_ns`` at that instant;
- ``confirmation_deadline_monotonic_ns`` — that value plus the UNCHANGED
  60 s window;
- ``confirmation_deadline_clock_domain: "controller"``.

Anchoring the deadline this way makes it independent of the events it
judges (deriving it from ``max(received_monotonic_ns)`` is circular: a very
late message becomes the new maximum and pushes its own deadline 60 s
further out). The 60 s window value itself never changes. When the
controller cannot be polled the two fields are null, the clock domain is
``"unavailable"``, a ``confirmation_marker_unavailable`` deviation is
recorded, and the timed run is INVALID unless
``--allow-missing-controller-marker`` authorizes it.

SUT collector hooks (sprint P5, report 5.3) make ``run`` — and hence the
``campaign`` batch runner, which drives this same function — end-to-end:
``--collector-start-cmd`` runs BEFORE the warm-up, ``--collector-stop-cmd``
AFTER the measured run and before the confirmation window, and
``--collector-fetch-cmd`` AFTER the confirmation window, producing the
local CSV that then goes through the EXISTING validated ingest path. The
templates accept ``{run_id}``, ``{duration_s}`` (warm-up + measured window
+ confirmation window + margin) and ``{dest}``. Every hook's command, exit
code and start/end timestamps are recorded in the manifest
(``collector_hooks``); a hook exiting non-zero makes the run INVALID with a
reason naming the flag — never a silent warning.

Collector output accounting (2026-09-19): ``--expect-services NAME,...``
names the services the collector must account for; the same list reaches the
start hook through the ``{expect_services}`` placeholder. The fetch hook
(``src/deployment/scripts/fetch-collector-output.sh``) puts the collector's
CSV and its ``.diagnostics.log`` / ``.lifecycle.csv`` companions (and a
``.self-test`` marker, if any) in ``logs/collector/``. Right after the fetch
hook, and before anything is sealed, :func:`inspect_collector_outputs` records
per file presence, size and sha256, the deployed collector's hash, the
collector's service inventory and the rows per expected service in the
manifest (``collector``). Every ``collector.problems`` entry (a missing
companion, a self-test marker, no expected services, an expected service
without rows, an inventory naming a missing service, a collector that did not
stop cleanly, ...) makes a timed run INVALID. The full stdout and stderr of
every hook are kept as ``logs/collector/hook-<hook>.stdout.txt`` /
``.stderr.txt``.

Mandatory artefacts (sprint P5, report 5.4): each condition kind declares
the evidence a completed run MUST carry (simulator: manifest.json,
sent_events.jsonl, events.jsonl, resources.csv, plus
controller_metrics.csv where ``/metrics`` sampling is mandated
instrumentation; external: manifest.json + timings.json). A missing
mandatory artefact marks the run invalid AND withholds SHA256SUMS: an
incomplete run must never look like sealed evidence.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .checksums import (
    SUMS_FILENAME,
    sha256_file,
    verify_sha256sums,
    write_sha256sums,
)
from .controller_metrics import ControllerMetricsSampler
from .environment import (
    LOADGEN_ENVIRONMENT_FILENAME,
    SUT_ENVIRONMENT_FILENAME,
    read_sut_environment,
    sut_env_node,
    utc_now_iso,
    validate_sut_environment,
    write_loadgen_environment,
)
from .plan_gen import load_campaign_plan, plan_to_json
from .protocol import (
    CONDITIONS,
    CONFIRMATION_WINDOW_S,
    PROTOCOL_VERSION,
    TIMED_CONDITION_IDS,
)
from .resources import ResourceSampler, validate_resources_csv

# Repository root: <repo>/src/egw_experiments/run.py -> parents[2] == <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
DEFAULT_RESULTS_BASE = REPO_ROOT / "experiments" / "results"
DEFAULT_PLAN_PATH = REPO_ROOT / "experiments" / "campaign_plan.json"
IMAGES_LOCK_PATH = SRC_DIR / "deployment" / "images.lock.env"

# Grace added on top of the nominal duration before the simulator subprocess
# is considered hung and killed.
SUBPROCESS_GRACE_S = 300

# Fetch-command retry policy (audit 9.3): up to FETCH_ATTEMPTS attempts with
# exponential backoff FETCH_BACKOFF_BASE_S * 2**(attempt-1) between them.
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_BASE_S = 2.0
FETCH_TIMEOUT_S = 300.0

# Environment variables consulted when the corresponding CLI flag is absent.
FETCH_EVENTS_CMD_ENV = "EGW_FETCH_EVENTS_CMD"
SUT_ENV_FILE_ENV = "EGW_SUT_ENV_FILE"

# 1.4 (collector output accounting, 2026-09-19; additive, no reader change
# needed): adds 'collector' ({expected_services, hooks_in_use} and, when a
# collector hook is configured, the inspection of logs/collector/: 'files'
# (csv/diagnostics/lifecycle/self_test: path, present, size, sha256),
# 'deployed_sha256', 'start_line_count', 'declared_expected_services',
# 'inventory', 'inventory_missing', 'stop_line', 'self_test_present',
# 'rows_per_expected_service', 'unexpected_services', 'problems'); every
# 'collector_hooks' record gains 'stdout_file'/'stderr_file' (the hook's full
# output under logs/collector/); 'config.cli' gains 'expect_services'.
# 'collector.problems' are validity reasons of a timed run.
# 1.3 (sprint P5.4, additive within the version — no reader change needed):
# 'controller_marker' gains 'lag_s'/'lag_tolerance_s' and 'controller_metrics'
# gains 'invalid_values'/'last_invalid_value'.
# 1.3 (sprint P5): adds 'collector_hooks', 'controller_marker',
# 'controller_monotonic_at_run_end_ns', 'missing_mandatory_artifacts',
# 'allow_missing_controller_marker'; 'confirmation_deadline_monotonic_ns'
# moves to the CONTROLLER clock domain (or null when unavailable).
# 1.2 (work order P1): adds 'deviations', 'sut_environment_missing_fields',
# 'allow_warmup_failure', 'allow_protocol_deviation'; hardens validity.
MANIFEST_VERSION = "1.4"

MANIFEST_FILENAME = "manifest.json"

# Timeout of the confirmation-marker poll (sprint P5, report 5.2). Short by
# design: it runs between the measured run and the confirmation window, and a
# controller that does not answer within it is recorded as unavailable rather
# than delaying the protocol timing.
CONTROLLER_MARKER_TIMEOUT_S = 5.0

#: Tolerated delay between the end of the measured window (``finished_utc``)
#: and the confirmation-marker poll (sprint P5.4 defect 5). The marker fixes
#: the instant the CONFIRMATION_WINDOW_S window is counted from, so every
#: second between the measured end and the poll is a second of EXTRA grace:
#: the effective window becomes 60 + lag s and confirmations the protocol
#: says are lost get counted in-window. The poll therefore happens
#: immediately after the run-end stamp — before the samplers are joined and
#: before any hook — and this tolerance only bounds what is considered
#: normal instrumentation jitter (one local HTTP request against a
#: CONTROLLER_MARKER_TIMEOUT_S budget). Above it the run records a warning
#: AND a 'confirmation_marker_lag' deviation so the analysis can see that
#: the deadline of that run is anomalous. The 60 s window value itself is
#: NOT affected by this constant.
CONTROLLER_MARKER_LAG_TOLERANCE_S = 2.0

#: Mandatory evidence per condition kind (sprint P5, report 5.4
#: "sent_events.jsonl ausente pode produzir run selado"). A missing mandatory
#: artefact makes the run INVALID and WITHHOLDS SHA256SUMS: an incomplete run
#: directory must never look like sealed evidence. ``manifest.json`` is part
#: of the declared set but is written unconditionally right after the check,
#: so it is never probed on disk.
SIMULATOR_MANDATORY_ARTIFACTS: tuple[str, ...] = (
    MANIFEST_FILENAME,
    "sent_events.jsonl",
    "events.jsonl",
    "resources.csv",
)
EXTERNAL_MANDATORY_ARTIFACTS: tuple[str, ...] = (MANIFEST_FILENAME, "timings.json")

#: Functional outcome vocabulary of an external sample, spelled EXACTLY as
#: ``egw_experiments.analyze`` reads it: that module lists ``outcome``
#: verbatim in ``external_runs.csv`` and turns anything it does not
#: recognise into ``"unspecified"``. A value outside this tuple is therefore
#: no boot result at all, and the runner must not seal it.
EXTERNAL_FUNCTIONAL_OUTCOMES: tuple[str, ...] = ("pass", "fail")

#: External conditions whose evidence is FUNCTIONAL rather than timed, i.e.
#: whose measurement IS the pass/fail outcome. Derived from the frozen
#: protocol so it cannot drift from it: an external condition that may not
#: support performance claims (plan 5.1 — ``qemu_boots``) is measured by its
#: outcome, and a sample without one discharges nothing. Gate G1 is
#: evidenced by exactly these runs.
FUNCTIONAL_EXTERNAL_CONDITION_IDS: frozenset[str] = frozenset(
    c.id
    for c in CONDITIONS
    if c.runner == "external" and not c.performance_claims_allowed
)

#: Conditions for which GET /metrics sampling is MANDATED instrumentation
#: (protocol.py, "Controller-metrics reconciliation": dropout_reconnect,
#: load_sweep and soak). For these, ``controller_metrics.csv`` joins the
#: mandatory artefact set — the analysis fails their acceptance criteria
#: without it, so a run lacking it is incomplete, not merely degraded.
METRICS_MANDATORY_CONDITION_IDS: frozenset[str] = frozenset(
    {"dropout_reconnect", "load_sweep", "soak"}
)

#: Collector hook labels in execution order, with the CLI flag that
#: configures each (sprint P5, report 5.3).
COLLECTOR_HOOK_FLAGS: dict[str, str] = {
    "start": "--collector-start-cmd",
    "stop": "--collector-stop-cmd",
    "fetch": "--collector-fetch-cmd",
}

#: Extra seconds added to the {duration_s} placeholder handed to the collector
#: hooks, on top of warm-up + measured run + confirmation window. The stop
#: hook ends the collector anyway; the margin only prevents a self-terminating
#: collector (``collect-resources.sh --duration``) from dying early because
#: the harness lost a few seconds to subprocess start-up.
COLLECTOR_DURATION_MARGIN_S = 60

#: Sub-directory of the run's logs/ holding the raw artefact produced by the
#: --collector-fetch-cmd hook, BEFORE it passes the ingest validation. Keeping
#: it means a rejected collector file is still inspectable next to the run it
#: belongs to (the validated copy lands at <run_dir>/resources.csv).
COLLECTOR_FETCH_SUBDIR = "collector"

#: What the SUT collector writes beside its CSV (collect-resources.sh, "Files
#: written beside <output.csv>"), as {key: (suffix, mandatory)}. The fetch hook
#: (src/deployment/scripts/fetch-collector-output.sh) copies them next to the
#: fetched CSV in logs/collector/, so the run's SHA256SUMS covers them. A
#: ``.self-test`` marker is optional: it exists only when the collector ran on
#: substituted inputs, and its presence makes the output NOT a measurement.
COLLECTOR_OUTPUT_FILES: dict[str, tuple[str, bool]] = {
    "csv": ("", True),
    "diagnostics": (".diagnostics.log", True),
    "lifecycle": (".lifecycle.csv", True),
    "self_test": (".self-test", False),
}

#: Characters of one service (container) name, the same set the collector
#: accepts for --expect-services (collect-resources.sh, argument checks).
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

#: A diagnostics line of the collector is "<UTC second>Z <message>".
_DIAG_LINE_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ (.*)$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

#: Conditions on which --skip-warmup invalidates the run unless explicitly
#: authorized with --allow-protocol-deviation (work order P1 fix 5). These
#: are the performance conditions whose protocol timing (warm-up/cooldown
#: structure, plan 7.1) underpins the RQ2/RQ3 claims.
SKIP_WARMUP_STRICT_CONDITIONS: frozenset[str] = frozenset(
    {"nominal", "load_sweep", "soak"}
)

MEASURED_WINDOW_CLOCK_NOTE = (
    "harness-host wall clock; assumes NTP-synchronized clocks between the "
    "harness host and the SUT VM. Used ONLY to window 1 Hz resource and "
    "controller-metrics samples (sub-second NTP error is negligible against "
    "the >=300 s measured windows); NEVER used for latency (CONTRACTS 5: "
    "latency is monotonic, single-host, in the controller)."
)


def parse_images_lock(path: str | Path = IMAGES_LOCK_PATH) -> dict[str, str]:
    """Parse ``images.lock.env`` (KEY=value lines) into a dict. Best-effort:
    a missing file returns an empty dict (recorded as a manifest warning)."""
    path = Path(path)
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def read_git_commit(repo_root: str | Path = REPO_ROOT) -> str | None:
    """Current git commit hash, or None when unavailable (best-effort)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_root),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


# ---------------------------------------------------------------------------
# Raw immutability (work order P1 item 11)
# ---------------------------------------------------------------------------


class SealedRunError(RuntimeError):
    """Refusal to replace raw run evidence (work order P1 item 11).

    Raised by the ingest/collection paths when a destination file already
    exists with DIFFERENT content. Raw run directories are write-once:
    once ``SHA256SUMS`` exists the directory is sealed, and recording
    different evidence requires a NEW run identity.
    """


def run_dir_is_sealed(run_dir: str | Path) -> bool:
    """True when the run directory carries SHA256SUMS (sealed evidence)."""
    return (Path(run_dir) / SUMS_FILENAME).is_file()


def ingest_copy(src: str | Path, dest: str | Path, run_dir: str | Path) -> bool:
    """Copy ``src`` into the run dir under the raw-immutability rules.

    - destination absent: plain copy;
    - destination present with IDENTICAL content: no-op (idempotent
      re-collection);
    - destination present with DIFFERENT content: :class:`SealedRunError`
      — raw evidence is never overwritten; a different measurement needs a
      new run identity.

    Returns True when ``dest`` holds ``src``'s content afterwards.
    """
    src = Path(src)
    dest = Path(dest)
    if dest.is_file():
        if sha256_file(src) == sha256_file(dest):
            return True
        sealed_note = (
            f"this run directory is sealed ({SUMS_FILENAME} present)"
            if run_dir_is_sealed(run_dir)
            else "raw run evidence is write-once"
        )
        raise SealedRunError(
            f"refusing to overwrite {dest.name} in {run_dir}: the existing "
            f"raw file's content differs from {src}; {sealed_note}. "
            "Recording different evidence requires a NEW run identity: "
            "repeat the run under a new versioned run_id and document the "
            "exclusion of the old one (plan 5.8)."
        )
    shutil.copyfile(src, dest)
    return True


# ---------------------------------------------------------------------------
# Simulator output layout (CONTRACTS 7; work order P1c fix F0)
# ---------------------------------------------------------------------------


def simulator_run_dir(output_dir: str | Path, run_id: str) -> Path:
    """Directory the simulator ACTUALLY writes into for a given --output.

    ``egw_simulator.runner`` writes ``manifest.json`` and
    ``sent_events.jsonl`` under ``<output_dir>/<run_id>/`` (its module
    docstring and ``--output`` help). The harness passes ``--output
    logs/simulator``, so the real outputs land at
    ``logs/simulator/<run_id>/`` — collection MUST use this same mapping
    (probing ``<output_dir>/sent_events.jsonl`` directly would silently
    lose the simulator log of every real run). The analysis side
    (``analyze.read_simulator_manifest``) probes this layout first.
    """
    return Path(output_dir) / run_id


# ---------------------------------------------------------------------------
# Events collection (audit 9.3)
# ---------------------------------------------------------------------------


def format_cmd_template(template: str, run_id: str, dest: str | Path | None = None) -> str:
    """Substitute ``{run_id}`` and ``{dest}`` placeholders literally.

    Plain string replacement (not ``str.format``) so any other brace
    construct in the operator's command survives untouched.
    """
    out = template.replace("{run_id}", run_id)
    if dest is not None:
        out = out.replace("{dest}", str(dest))
    return out


def fetch_events_via_cmd(
    template: str,
    run_id: str,
    dest: str | Path,
    *,
    attempts: int = FETCH_ATTEMPTS,
    backoff_base_s: float | None = None,
    timeout_s: float = FETCH_TIMEOUT_S,
    sleep=time.sleep,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """Run the fetch command template with retries and backoff.

    The template's ``{run_id}`` and ``{dest}`` placeholders are substituted
    (``{dest}`` always with forward slashes, so POSIX splitting never eats
    Windows backslashes), the command is split POSIX-style (``shlex.split``;
    quote arguments that contain spaces, use forward slashes in paths) and
    executed WITHOUT a shell. Success requires exit code 0 AND ``dest``
    existing afterwards.

    Returns ``(ok, formatted_cmd, attempt_records)``.
    """
    if backoff_base_s is None:
        backoff_base_s = FETCH_BACKOFF_BASE_S
    dest = Path(dest)
    cmd_str = format_cmd_template(template, run_id, dest.as_posix())
    argv = shlex.split(cmd_str, posix=True)
    records: list[dict[str, Any]] = []
    for attempt in range(1, attempts + 1):
        record: dict[str, Any] = {"attempt": attempt, "started_utc": utc_now_iso()}
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
            record["returncode"] = proc.returncode
            stderr_tail = (proc.stderr or "").strip()
            if stderr_tail:
                record["stderr_tail"] = stderr_tail[-500:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            record["returncode"] = None
            record["error"] = str(exc)
        record["dest_exists"] = dest.is_file()
        records.append(record)
        if record.get("returncode") == 0 and record["dest_exists"]:
            return True, cmd_str, records
        if attempt < attempts:
            sleep(backoff_base_s * 2 ** (attempt - 1))
    return False, cmd_str, records


def find_controller_events(event_log_dir: str | Path, run_id: str) -> Path | None:
    """Locate the controller's per-run events.jsonl in EGW_EVENT_LOG_DIR.

    CONTRACTS 5 fixes one events.jsonl per run_id inside EGW_EVENT_LOG_DIR
    but not the exact file layout, so several plausible layouts are tried.
    """
    d = Path(event_log_dir)
    candidates = [
        d / run_id / "events.jsonl",
        d / f"{run_id}.events.jsonl",
        d / f"{run_id}.jsonl",
        d / f"events-{run_id}.jsonl",
        d / f"events_{run_id}.jsonl",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def collect_controller_events(
    event_log_dir: str | Path, run_id: str, dest: str | Path
) -> str | None:
    """Copy the run's controller events.jsonl into the run directory.

    Returns a description of the source used, or None when nothing was
    found. Falls back to filtering a shared ``events.jsonl`` by run_id.
    """
    dest = Path(dest)
    source = find_controller_events(event_log_dir, run_id)
    if source is not None:
        shutil.copyfile(source, dest)
        return str(source)

    shared = Path(event_log_dir) / "events.jsonl"
    if shared.is_file():
        matched: list[str] = []
        with open(shared, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("run_id") == run_id:
                    matched.append(line)
        if matched:
            dest.write_text("\n".join(matched) + "\n", encoding="utf-8")
            return f"{shared} (filtered by run_id)"
    return None


def collect_events(
    *,
    run_id: str,
    dest: Path,
    fetch_events_cmd: str | None,
    event_log_dir: Path,
    warnings: list[str],
    fetch_info: dict[str, Any],
) -> str | None:
    """Full events-collection step: fetch command first, local fallback.

    Records the fetch attempts in ``fetch_info`` and human-readable
    problems in ``warnings``. Returns the ``events_source`` description or
    None when collection failed entirely.
    """
    if fetch_events_cmd:
        ok, cmd_str, attempt_records = fetch_events_via_cmd(
            fetch_events_cmd, run_id, dest
        )
        fetch_info["template"] = fetch_events_cmd
        fetch_info["command"] = cmd_str
        fetch_info["attempts"] = attempt_records
        fetch_info["ok"] = ok
        if ok:
            return f"fetch-cmd: {cmd_str}"
        warnings.append(
            f"fetch-events-cmd failed after {len(attempt_records)} "
            f"attempt(s): {cmd_str}"
        )
    source = collect_controller_events(event_log_dir, run_id, dest)
    if source is None and fetch_events_cmd is None:
        warnings.append(
            f"controller events.jsonl for run_id {run_id!r} not found under "
            f"{event_log_dir} and no --fetch-events-cmd/"
            f"{FETCH_EVENTS_CMD_ENV} configured. The controller writes "
            "events.jsonl ON the ARM VM (plan 5.1); configure a fetch "
            "command template, e.g. --fetch-events-cmd "
            "'scp vm:/opt/egw/data/events/{run_id}/events.jsonl {dest}', "
            "or recover later with: python -m egw_experiments collect "
            f"--run-id {run_id} --fetch-events-cmd '...'"
        )
    elif source is None:
        warnings.append(
            f"local event-log fallback also failed (looked under "
            f"{event_log_dir}); recover with: python -m egw_experiments "
            f"collect --run-id {run_id} --fetch-events-cmd '...'"
        )
    return source


# ---------------------------------------------------------------------------
# Confirmation marker in the CONTROLLER's clock domain (sprint P5, report 5.2)
# ---------------------------------------------------------------------------


def _http_get_json(url: str, timeout_s: float) -> Any:
    """One plain stdlib HTTP GET returning the parsed JSON body.

    Deliberately ``urllib`` only: the harness core is standard-library
    only, and this single request must never pull an HTTP client into the
    dependency set. Raises on any network/HTTP/JSON failure; callers record
    the failure instead of propagating it.
    """
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        body = resp.read()
    return json.loads(body.decode("utf-8"))


def poll_controller_marker(
    controller_url: str | None,
    *,
    timeout_s: float = CONTROLLER_MARKER_TIMEOUT_S,
) -> dict[str, Any]:
    """Read the controller's confirmation marker right after the run ends.

    The controller's ``GET /metrics`` carries (CONTRACTS, sprint P5) an
    additive ``monotonic_ns`` field — ``time.monotonic_ns()`` in the
    CONTROLLER's clock domain at request handling — plus an RFC 3339
    ``wall_utc``. Anchoring the 60 s confirmation deadline on that value
    makes the deadline independent of the events themselves (report 5.2:
    deriving it from ``max(received_monotonic_ns)`` is circular, because a
    very late message becomes the new maximum and pushes its own deadline).

    The 60 s window itself is NOT touched here; only the instrumentation
    that fixes the END INSTANT is.

    Returns ``{url, polled_utc, ok, monotonic_ns, wall_utc, error}``; never
    raises — an unreachable or too-old controller is recorded, and the
    caller applies the validity rules.
    """
    record: dict[str, Any] = {
        "url": None,
        "polled_utc": None,
        "ok": False,
        "monotonic_ns": None,
        "wall_utc": None,
        "error": None,
    }
    if not controller_url:
        record["error"] = (
            "no --controller-url configured: the confirmation deadline "
            "cannot be anchored in the controller's clock domain"
        )
        return record
    url = str(controller_url).rstrip("/") + "/metrics"
    record["url"] = url
    record["polled_utc"] = utc_now_iso()
    try:
        payload = _http_get_json(url, timeout_s)
    except (OSError, ValueError) as exc:
        record["error"] = f"GET {url} failed: {exc}"
        return record
    if not isinstance(payload, dict):
        record["error"] = f"GET {url} did not return a JSON object"
        return record
    monotonic_ns = payload.get("monotonic_ns")
    if isinstance(monotonic_ns, bool) or not isinstance(monotonic_ns, int):
        record["error"] = (
            f"GET {url} response carries no integer 'monotonic_ns' field: "
            "this controller predates the confirmation-marker contract, so "
            "the deadline cannot be anchored in its clock domain"
        )
        return record
    wall_utc = payload.get("wall_utc")
    record["monotonic_ns"] = monotonic_ns
    record["wall_utc"] = wall_utc if isinstance(wall_utc, str) else None
    record["ok"] = True
    return record


# ---------------------------------------------------------------------------
# SUT collector hooks (sprint P5, report 5.3: 'campaign' must be end-to-end)
# ---------------------------------------------------------------------------


def parse_expected_services(value: str) -> list[str]:
    """Parse ``--expect-services NAME,NAME,...`` into a list of names.

    Each name must use only the characters the collector itself accepts
    (``A-Za-z0-9_.-``, :data:`SERVICE_NAME_RE`); an empty element (``a,,b``,
    a trailing comma, an empty value) and a repeated name are refused. Raises
    ``ValueError`` with a message naming the offending element.
    """
    names = value.split(",")
    return validate_expected_services(names)


def validate_expected_services(names: list[str]) -> list[str]:
    """Check a list of expected service names; returns it unchanged.

    Raises ``ValueError`` when the list is empty, holds an empty or repeated
    name, or a name with a character outside ``A-Za-z0-9_.-``.
    """
    if not names:
        raise ValueError("--expect-services names no service")
    seen: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not SERVICE_NAME_RE.match(name):
            raise ValueError(
                f"--expect-services: invalid service name {name!r} (only "
                "A-Z a-z 0-9 _ . - are allowed, as in collect-resources.sh; "
                "names are separated by single commas)"
            )
        if name in seen:
            raise ValueError(f"--expect-services: {name!r} is given twice")
        seen.add(name)
    return list(names)


def format_collector_template(
    template: str,
    run_id: str,
    *,
    duration_s: int,
    dest: str | Path,
    expect_services: list[str] | None = None,
) -> str:
    """Substitute ``{run_id}``, ``{dest}``, ``{duration_s}`` and
    ``{expect_services}`` literally.

    Same plain-replacement rule as :func:`format_cmd_template` (any other
    brace construct in the operator's command survives untouched);
    ``{dest}`` is always rendered with forward slashes so POSIX splitting
    never eats Windows backslashes. ``{expect_services}`` is the
    ``--expect-services`` list joined with commas (empty when unset), so the
    start hook hands the collector the same list the harness enforces.
    """
    out = format_cmd_template(template, run_id, Path(dest).as_posix())
    out = out.replace("{expect_services}", ",".join(expect_services or []))
    return out.replace("{duration_s}", str(duration_s))


def _as_bytes(data: bytes | str | None) -> bytes:
    if data is None:
        return b""
    if isinstance(data, str):
        return data.encode("utf-8", errors="replace")
    return data


def execute_collector_hook(
    hook: str,
    template: str,
    run_id: str,
    *,
    duration_s: int,
    dest: str | Path,
    expect_services: list[str] | None = None,
    log_dir: str | Path | None = None,
    timeout_s: float = FETCH_TIMEOUT_S,
) -> dict[str, Any]:
    """Execute one collector hook and return its manifest record.

    The record is ``{hook, flag, template, command, started_utc,
    finished_utc, returncode}`` (plus ``stderr_tail``/``error`` when
    applicable). A non-zero (or absent) return code is NEVER a silent
    warning: the caller turns it into a validity reason naming the hook.

    With ``log_dir`` the hook's FULL stdout and stderr are written, byte for
    byte, to ``<log_dir>/hook-<hook>.stdout.txt`` and ``.stderr.txt``
    whenever the command ran (also when it timed out); the record then
    carries their paths as ``stdout_path``/``stderr_path``. The 500-character
    ``stderr_tail`` stays in the record for a quick read of the manifest.
    """
    cmd_str = format_collector_template(
        template,
        run_id,
        duration_s=duration_s,
        dest=dest,
        expect_services=expect_services,
    )
    record: dict[str, Any] = {
        "hook": hook,
        "flag": COLLECTOR_HOOK_FLAGS[hook],
        "template": template,
        "command": cmd_str,
        "started_utc": utc_now_iso(),
        "returncode": None,
    }
    stdout: bytes | None = None
    stderr: bytes | None = None
    try:
        proc = subprocess.run(
            shlex.split(cmd_str, posix=True),
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        record["returncode"] = proc.returncode
        stdout, stderr = _as_bytes(proc.stdout), _as_bytes(proc.stderr)
    except subprocess.TimeoutExpired as exc:
        record["error"] = str(exc)
        stdout, stderr = _as_bytes(exc.stdout), _as_bytes(exc.stderr)
    except (OSError, ValueError) as exc:
        record["error"] = str(exc)
    if stderr is not None:
        stderr_tail = stderr.decode("utf-8", errors="replace").strip()
        if stderr_tail:
            record["stderr_tail"] = stderr_tail[-500:]
    if log_dir is not None and stdout is not None and stderr is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        for stream, data in (("stdout", stdout), ("stderr", stderr)):
            path = log_dir / f"hook-{hook}.{stream}.txt"
            path.write_bytes(data)
            record[f"{stream}_path"] = str(path)
    record["finished_utc"] = utc_now_iso()
    return record


def collector_hook_failures(
    collector_hooks: list[dict[str, Any]] | None,
) -> list[str]:
    """Human-readable failure reasons for the hooks that did not exit 0."""
    reasons: list[str] = []
    for record in collector_hooks or []:
        if record.get("returncode") == 0:
            continue
        flag = record.get("flag") or COLLECTOR_HOOK_FLAGS.get(
            str(record.get("hook")), "collector hook"
        )
        detail = record.get("error")
        reasons.append(
            f"collector hook {flag} failed with exit code "
            f"{record.get('returncode')}"
            + (f" ({detail})" if detail else "")
            + ": the SUT resource collector was not driven as the protocol "
            "prescribes, so this run's CPU/RAM evidence cannot be trusted"
        )
    return reasons


def _diagnostic_message(line: str) -> str:
    """The message of one collector diagnostics line (timestamp removed)."""
    match = _DIAG_LINE_RE.match(line)
    return match.group(1) if match else line


def _inventory_fields(message: str) -> dict[str, str]:
    """``key=value`` fields of an ``inventory:`` message (values hold no
    spaces: service names are limited to ``A-Za-z0-9_.-``)."""
    fields: dict[str, str] = {}
    for token in message[len("inventory:"):].split():
        key, sep, value = token.partition("=")
        if sep:
            fields[key] = value
    return fields


def inspect_collector_outputs(
    collector_dest: str | Path,
    expect_services: list[str] | None,
    *,
    run_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Account for the SUT collector's fetched output (collector hooks).

    ``collector_dest`` is the fetched CSV (``logs/collector/resources-
    <run_id>.csv``); its companions sit beside it with the suffixes of
    :data:`COLLECTOR_OUTPUT_FILES`. Nothing is modified: the files are read
    and hashed where the fetch hook put them, BEFORE the run directory is
    sealed. Returns the manifest's ``collector`` record:

    - ``files``: per key (``csv``, ``diagnostics``, ``lifecycle``,
      ``self_test``) ``{path, present, size, sha256}`` (``path`` relative to
      ``run_dir`` when given);
    - ``deployed_sha256``: the ``collector_sha256`` of the diagnostics'
      ``start:`` line (the collector that actually ran on the guest), else
      None; ``start_line_count``;
    - ``declared_expected_services``: the start line's ``expected services:``
      value as the collector wrote it;
    - ``inventory``: the last ``inventory:`` line, raw, and
      ``inventory_missing``: its ``missing=`` names (``[]`` for ``none``);
      ``stop_line``: the last ``stop:`` line, raw;
    - ``self_test_present``;
    - ``rows_per_expected_service``: data rows of each expected service in
      the fetched CSV's ``container`` column; ``unexpected_services``: the
      other names found there (a warning only);
    - ``problems``: every reason why the output cannot be accounted for.
      The caller turns each into a validity reason of a timed run.

    The ingest validation of the CSV (header, instants, coverage, gaps) is
    NOT repeated here; it stays in :func:`ingest_resources`.
    """
    collector_dest = Path(collector_dest)
    run_dir = Path(run_dir) if run_dir is not None else None
    problems: list[str] = []
    files: dict[str, dict[str, Any]] = {}
    for key, (suffix, _mandatory) in COLLECTOR_OUTPUT_FILES.items():
        path = collector_dest.with_name(collector_dest.name + suffix)
        shown = (
            path.relative_to(run_dir).as_posix()
            if run_dir is not None and path.is_relative_to(run_dir)
            else path.name
        )
        present = path.is_file()
        files[key] = {
            "path": shown,
            "present": present,
            "size": path.stat().st_size if present else None,
            "sha256": sha256_file(path) if present else None,
        }

    csv_name = collector_dest.name
    if not files["csv"]["present"]:
        problems.append(
            f"collector CSV {csv_name} is absent from logs/{COLLECTOR_FETCH_SUBDIR}/"
            ": the fetch hook did not deliver the collector's output"
        )
    for key, (suffix, mandatory) in COLLECTOR_OUTPUT_FILES.items():
        if key != "csv" and mandatory and not files[key]["present"]:
            problems.append(
                f"mandatory collector companion {csv_name}{suffix} is absent: "
                "without it the collector's rows cannot be explained or "
                "attributed (fetch it with "
                "src/deployment/scripts/fetch-collector-output.sh)"
            )
    self_test_present = bool(files["self_test"]["present"])
    if self_test_present:
        problems.append(
            f"{csv_name}.self-test is present: the collector ran in self-test "
            "mode on substituted inputs, so this output is NOT a measurement"
        )
    if not expect_services:
        problems.append(
            "--expect-services was not given: the services the collector must "
            "account for are unknown, so a service without a single row would "
            "go unnoticed"
        )

    # Diagnostics: the deployed collector's hash, the expected set it was
    # given, its inventory and closing summary.
    deployed_sha256: str | None = None
    declared: str | None = None
    inventory: str | None = None
    inventory_missing: list[str] | None = None
    stop_line: str | None = None
    start_lines = 0
    if files["diagnostics"]["present"]:
        diag_path = collector_dest.with_name(csv_name + ".diagnostics.log")
        first_start: str | None = None
        for raw in diag_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            line = raw.rstrip("\r")
            message = _diagnostic_message(line)
            if message.startswith("start: "):
                start_lines += 1
                if first_start is None:
                    first_start = message
            elif message.startswith("inventory:"):
                inventory = line
                fields = _inventory_fields(message)
                missing = fields.get("missing")
                inventory_missing = (
                    None
                    if missing is None
                    else [] if missing == "none" else missing.split(",")
                )
            elif message.startswith("stop: "):
                stop_line = line
        if first_start is None:
            problems.append(
                "the collector diagnostics hold no 'start:' line: the sha256 "
                "of the collector that ran on the guest is unknown"
            )
        else:
            match = re.search(r"\bcollector_sha256=(\S+)", first_start)
            candidate = match.group(1) if match else None
            if candidate is not None and _SHA256_HEX_RE.match(candidate):
                deployed_sha256 = candidate
            else:
                problems.append(
                    "the collector's 'start:' line carries no usable "
                    f"collector_sha256 ({candidate!r}): the sha256 of the "
                    "collector that ran on the guest is unknown"
                )
            _, sep, value = first_start.rpartition("expected services: ")
            declared = value.strip() if sep else None
            declared_set = (
                set()
                if declared in (None, "", "none declared")
                else set(declared.split(","))
            )
            if expect_services and declared_set != set(expect_services):
                problems.append(
                    "the collector's 'start:' line declares expected services "
                    f"{declared!r}, the harness expects "
                    f"{','.join(expect_services)!r}: the start hook did not "
                    "pass --expect-services {expect_services} to the collector"
                )
        if start_lines > 1:
            problems.append(
                f"the collector diagnostics hold {start_lines} 'start:' lines: "
                "more than one collector wrote this output (a run_id reused "
                "within one guest boot appends to the same files)"
            )
        if inventory is None:
            problems.append(
                "the collector diagnostics hold no 'inventory:' line: the "
                "collector did not stop cleanly (it writes the inventory when "
                "the stop hook's SIGTERM ends it)"
            )
        elif inventory_missing:
            problems.append(
                "the collector's inventory reports expected service(s) never "
                "observed: " + ", ".join(inventory_missing)
            )
        elif inventory_missing is None:
            problems.append(
                "the collector's 'inventory:' line has no 'missing=' field: "
                f"{inventory!r}"
            )

    # Rows per expected service in the fetched CSV ('container' column).
    rows_per_service: dict[str, int] | None = None
    unexpected: list[str] = []
    if files["csv"]["present"]:
        counts: dict[str, int] = {}
        container_col: int | None = None
        read_error: str | None = None
        try:
            with open(
                collector_dest, "r", encoding="utf-8", errors="replace", newline=""
            ) as fh:
                reader = csv.reader(fh)
                header = next(reader, None)
                if header is not None and "container" in header:
                    container_col = header.index("container")
                    for row in reader:
                        if len(row) <= container_col:
                            continue
                        name = row[container_col].strip()
                        if name:
                            counts[name] = counts.get(name, 0) + 1
        except (OSError, csv.Error) as exc:
            read_error = str(exc)
        if read_error is not None:
            problems.append(
                f"collector CSV {csv_name} could not be read to count the rows "
                f"per service: {read_error}"
            )
        elif container_col is None:
            problems.append(
                f"collector CSV {csv_name} has no 'container' column: the rows "
                "cannot be attributed to services"
            )
        elif expect_services:
            rows_per_service = {name: counts.get(name, 0) for name in expect_services}
            for name, rows in rows_per_service.items():
                if rows == 0:
                    problems.append(
                        f"expected service {name!r} has no rows in the fetched "
                        f"collector CSV {csv_name}"
                    )
            unexpected = sorted(set(counts) - set(expect_services))

    return {
        "files": files,
        "deployed_sha256": deployed_sha256,
        "start_line_count": start_lines,
        "declared_expected_services": declared,
        "inventory": inventory,
        "inventory_missing": inventory_missing,
        "stop_line": stop_line,
        "self_test_present": self_test_present,
        "rows_per_expected_service": rows_per_service,
        "unexpected_services": unexpected,
        "problems": problems,
    }


def collector_problem_reasons(problems: list[str] | None) -> list[str]:
    """Validity reasons for the ``collector.problems`` of a run."""
    return [
        f"collector output not accounted for: {problem}; this run's CPU/RAM "
        "evidence cannot be trusted"
        for problem in problems or []
    ]


# ---------------------------------------------------------------------------
# Mandatory artefacts per condition kind (sprint P5, report 5.4)
# ---------------------------------------------------------------------------


def mandatory_artifacts(
    condition_id: str | None,
    *,
    runner: str = "simulator",
    allow_missing_resources: bool = False,
) -> list[str]:
    """The evidence files a completed run of this kind MUST carry.

    Simulator conditions: manifest.json, sent_events.jsonl, events.jsonl,
    resources.csv — plus controller_metrics.csv on the conditions where
    ``GET /metrics`` sampling is mandated instrumentation
    (:data:`METRICS_MANDATORY_CONDITION_IDS`). External conditions:
    manifest.json plus the ingested timings file.

    ``--allow-missing-resources`` drops resources.csv from the set: an
    absence explicitly authorized (and recorded as a deviation) is a
    documented decision, not an incomplete run.
    """
    if runner != "simulator":
        return list(EXTERNAL_MANDATORY_ARTIFACTS)
    names = [
        name
        for name in SIMULATOR_MANDATORY_ARTIFACTS
        if not (name == "resources.csv" and allow_missing_resources)
    ]
    if condition_id in METRICS_MANDATORY_CONDITION_IDS:
        names.append("controller_metrics.csv")
    return names


def missing_mandatory_artifacts(
    run_dir: str | Path,
    condition_id: str | None,
    *,
    runner: str = "simulator",
    allow_missing_resources: bool = False,
) -> list[str]:
    """Mandatory artefacts absent from ``run_dir`` (report 5.4).

    ``manifest.json`` is skipped: it is written unconditionally by the
    caller immediately after this check, so probing it here would always
    report it missing.
    """
    run_dir = Path(run_dir)
    missing: list[str] = []
    for name in mandatory_artifacts(
        condition_id,
        runner=runner,
        allow_missing_resources=allow_missing_resources,
    ):
        if name == MANIFEST_FILENAME:
            continue
        if not (run_dir / name).is_file():
            missing.append(name)
    return missing


# ---------------------------------------------------------------------------
# SUT environment / resources ingestion (audit 9.1/9.2)
# ---------------------------------------------------------------------------


def ingest_sut_environment(
    run_dir: Path, sut_env_from: str | Path | None, warnings: list[str]
) -> bool:
    """Copy the operator-fetched sut_environment.json into the run dir.

    Returns True when ``sut_environment.json`` is present in the run dir
    afterwards. A source path that does not exist is a warning (the
    validity rules then apply). An already-ingested file is never
    overwritten with different content (raises :class:`SealedRunError`);
    an identical re-copy is a no-op (work order P1 item 11).
    """
    dest = run_dir / SUT_ENVIRONMENT_FILENAME
    if sut_env_from is not None:
        src = Path(sut_env_from)
        if src.is_file():
            ingest_copy(src, dest, run_dir)
        else:
            warnings.append(f"--sut-env-from file not found: {src}")
    return dest.is_file()


def ingest_resources(
    run_dir: Path,
    resources_from: str | Path | None,
    warnings: list[str],
    *,
    expected_window_s: float | None = None,
    expected_window_start_utc: str | None = None,
    expected_window_end_utc: str | None = None,
    source_label: str = "--resources-from",
) -> bool:
    """Validate and copy the fetched SUT resources.csv into the run dir.

    Work order P1 fix 3: file presence alone is NOT evidence. The source is
    content-validated (:func:`egw_experiments.resources.validate_resources_csv`):
    exact 6-column header including ``host`` provenance, at least
    MIN_RESOURCE_SAMPLES data rows, and — when the run dir already holds a
    sut_environment.json with a node/hostname — every distinct ``host``
    value must equal it. Sprint P5 (report 5.4) adds the SEMANTIC checks:
    parseable RFC 3339 timestamps, non-decreasing time, numeric cpu/mem
    fields, per-row column completeness, a minimum number of DISTINCT
    sample instants and — when the real measured-window UTC bounds are given
    — actual overlap, coverage and sampling continuity inside that window.
    ``expected_window_s`` remains the fallback for historical manifests that
    do not have those bounds. Any problem rejects the ingest with a clear
    warning and the run's resources are treated as missing (the validity
    rules then apply). Returns True only on a successful, validated copy.
    An existing ``resources.csv`` is never overwritten with different
    content (raises :class:`SealedRunError`); an identical re-copy is a
    no-op (work order P1 item 11). ``source_label`` names where the file
    came from in the warnings (``--resources-from`` or the output of the
    ``--collector-fetch-cmd`` hook).
    """
    if resources_from is None:
        return False
    src = Path(resources_from)
    if not src.is_file():
        warnings.append(f"{source_label} file not found: {src}")
        return False
    expected_host = sut_env_node(read_sut_environment(run_dir))
    problems = validate_resources_csv(
        src,
        expected_host=expected_host,
        expected_window_s=expected_window_s,
        expected_window_start_utc=expected_window_start_utc,
        expected_window_end_utc=expected_window_end_utc,
    )
    if problems:
        warnings.append(
            f"{source_label} {src} REJECTED (SUT resources treated as "
            "missing): " + "; ".join(problems)
        )
        return False
    ingest_copy(src, run_dir / "resources.csv", run_dir)
    return True


# ---------------------------------------------------------------------------
# Validity (audit: warning-only is not acceptable)
# ---------------------------------------------------------------------------


def compute_validity(
    *,
    timed: bool,
    sut_env_present: bool,
    allow_missing_sut_env: bool,
    resource_source: str,
    allow_missing_resources: bool,
    restart_required: bool,
    restart_ok: bool,
    sut_env_missing_fields: list[str] | None = None,
    simulator_returncode: int | None = 0,
    warmup_returncode: int | None = None,
    allow_warmup_failure: bool = False,
    skip_warmup: bool = False,
    condition_id: str | None = None,
    allow_protocol_deviation: bool = False,
    confirmation_marker_ok: bool = True,
    allow_missing_controller_marker: bool = False,
    collector_hooks: list[dict[str, Any]] | None = None,
    missing_artifacts: list[str] | None = None,
    collector_problems: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Evaluate the run-validity rules; returns (validity, reasons).

    Timed runs (every simulator-driven condition) without a USABLE SUT
    environment manifest or without SUT-collector resources are INVALID —
    CPU/RAM on the SUT are essential for RQ3 and an environment file
    captured on the wrong host describes the wrong system (audit 9.1/9.2).
    Work order P1 hardening:

    - ``resource_source`` must be exactly ``'sut-collector'``: the
      ``--local-resources`` dev sampler measures the LOAD GENERATOR host
      and never evidences the SUT (override: --allow-missing-resources,
      recorded as a deviation);
    - a present sut_environment.json failing REQUIRED_SUT_FIELDS
      validation is as invalid as a missing one (override:
      --allow-missing-sut-env, recorded as a deviation);
    - a non-zero simulator exit invalidates the run outright (no
      override: the measured run itself failed);
    - a non-zero warm-up exit invalidates the run unless
      --allow-warmup-failure (recorded as a deviation);
    - --skip-warmup on the SKIP_WARMUP_STRICT_CONDITIONS invalidates the
      run unless --allow-protocol-deviation (recorded as a deviation).

    Sprint P5 hardening:

    - the confirmation deadline must be anchored in the CONTROLLER's clock
      domain (``confirmation_marker_ok``, report 5.2): without the marker
      the 60 s window cannot be verified, so the run is invalid unless
      --allow-missing-controller-marker (recorded as a deviation);
    - every configured collector hook must exit 0 (report 5.3): a failed
      start/stop/fetch hook is never a silent warning;
    - the mandatory artefacts of the condition kind must be present
      (report 5.4): a run missing one is INVALID and is not sealed.

    Collector output accounting (2026-09-19): every ``collector_problems``
    entry (:func:`inspect_collector_outputs`) is a reason of a timed run —
    a missing companion, a self-test marker, no ``--expect-services``, an
    expected service without rows, an inventory naming a missing service, a
    collector that did not stop cleanly. No allow flag suppresses them. They
    do NOT withhold SHA256SUMS: the fetched files are sealed as they are, so
    the invalid run's evidence stays verifiable.

    The explicit allow flags suppress the corresponding reason but are
    recorded in the manifest (``deviations``) as a deliberate decision.
    """
    reasons: list[str] = []
    missing_fields = list(sut_env_missing_fields or [])
    if timed:
        if not sut_env_present and not allow_missing_sut_env:
            reasons.append(
                "sut_environment.json missing: timed runs require the SUT "
                "environment captured ON the VM "
                "(deployment/scripts/capture-sut-environment.sh, ingested "
                "via --sut-env-from); override only with "
                "--allow-missing-sut-env"
            )
        elif sut_env_present and missing_fields and not allow_missing_sut_env:
            reasons.append(
                "sut_environment.json unusable, missing required field(s): "
                + ", ".join(missing_fields)
                + " (REQUIRED_SUT_FIELDS, egw_experiments/environment.py); "
                "a SUT manifest without host identity, CPU count and OS "
                "identification cannot support RQ3; override only with "
                "--allow-missing-sut-env"
            )
        if resource_source != "sut-collector" and not allow_missing_resources:
            if resource_source == "local-dev":
                reasons.append(
                    "resource_source 'local-dev': --local-resources samples "
                    "docker stats on the LOAD GENERATOR host, not the SUT "
                    "(dev only, audit 9.1); timed runs require the VM-side "
                    "collector output "
                    "(deployment/scripts/collect-resources.sh, ingested via "
                    "--resources-from); override only with "
                    "--allow-missing-resources"
                )
            else:
                reasons.append(
                    "no SUT resources: timed runs require the VM-side "
                    "collector output "
                    "(deployment/scripts/collect-resources.sh, ingested "
                    "via --resources-from); CPU/RAM on the SUT are "
                    "essential for RQ3; override only with "
                    "--allow-missing-resources"
                )
        if restart_required and not restart_ok:
            reasons.append(
                "controller_restart condition without a successfully "
                "executed --restart-cmd: the run cannot evidence claim C12"
            )
        if simulator_returncode not in (0, None):
            reasons.append(
                f"simulator exited with code {simulator_returncode}: the "
                "measured run did not complete cleanly; there is no "
                "override for a failed measured run"
            )
        if warmup_returncode not in (0, None) and not allow_warmup_failure:
            reasons.append(
                f"warm-up exited with code {warmup_returncode}: the twins "
                "were not warmed as the protocol prescribes; override only "
                "with --allow-warmup-failure (records a protocol deviation)"
            )
        if (
            skip_warmup
            and condition_id in SKIP_WARMUP_STRICT_CONDITIONS
            and not allow_protocol_deviation
        ):
            reasons.append(
                f"--skip-warmup on condition {condition_id!r}: the frozen "
                "protocol (plan 7.1) prescribes this condition's "
                "warm-up/cooldown structure; override only with "
                "--allow-protocol-deviation (records a protocol deviation)"
            )
        if not confirmation_marker_ok and not allow_missing_controller_marker:
            reasons.append(
                "no controller confirmation marker: the run end was not "
                "stamped in the controller's clock domain (GET /metrics "
                "'monotonic_ns' via --controller-url), so the "
                f"{CONFIRMATION_WINDOW_S} s confirmation deadline cannot be "
                "verified independently of the events themselves (report "
                "5.2); override only with --allow-missing-controller-marker "
                "(records a protocol deviation and leaves the analysis on "
                "the legacy event-derived deadline)"
            )
        reasons.extend(collector_hook_failures(collector_hooks))
        reasons.extend(collector_problem_reasons(collector_problems))
    if missing_artifacts:
        reasons.append(
            "mandatory artefact(s) missing from the run directory: "
            + ", ".join(missing_artifacts)
            + " — the run is incomplete for its condition kind, so it is "
            "marked invalid and NOT sealed (no SHA256SUMS); recover the "
            "missing evidence with 'collect' or repeat the run under a new "
            "run identity"
        )
    return ("valid" if not reasons else "invalid"), reasons


def _append_deviation(
    deviations: list[dict[str, Any]],
    kind: str,
    detail: str,
    authorized_by_flag: str | None,
) -> None:
    """Append a protocol-deviation record, once per kind (work order P1).

    Entries are ``{kind, detail, authorized_by_flag}``;
    ``authorized_by_flag`` is None for a deviation that happened WITHOUT an
    explicit authorizing flag (those normally also produce a validity
    reason). Deduplicated by ``kind`` so repeated 'collect' passes never
    stack duplicates.
    """
    if any(d.get("kind") == kind for d in deviations):
        return
    deviations.append(
        {"kind": kind, "detail": detail, "authorized_by_flag": authorized_by_flag}
    )


def update_plan_status(
    plan_path: str | Path, run_id: str, status: str, **extra: Any
) -> bool:
    """Best-effort update of the run's status inside campaign_plan.json."""
    try:
        plan = load_campaign_plan(plan_path)
        for entry in plan.get("runs", []):
            if entry.get("run_id") == run_id:
                entry["status"] = status
                entry.update(extra)
                break
        else:
            return False
        Path(plan_path).write_text(plan_to_json(plan), encoding="utf-8")
        return True
    except (OSError, json.JSONDecodeError):
        return False


def _simulator_cmd(
    *,
    scenario: str,
    seed: int,
    duration_s: int,
    rate_msg_s: float,
    output_dir: Path,
    run_id: str,
    broker: str,
    port: int,
    egw_id: str,
    qos: int,
    username: str | None,
    password: str | None,
    ca_cert: str | None,
    no_tls: bool,
) -> list[str]:
    """Build the simulator invocation exactly per CONTRACTS 7."""
    cmd = [
        sys.executable,
        "-m",
        "egw_simulator",
        "run",
        "--scenario",
        scenario,
        "--seed",
        str(seed),
        "--broker",
        broker,
        "--port",
        str(port),
        "--duration",
        str(duration_s),
        "--rate",
        str(rate_msg_s),
        "--output",
        str(output_dir),
        "--egw-id",
        egw_id,
        "--run-id",
        run_id,
        "--qos",
        str(qos),
    ]
    if no_tls:
        cmd.append("--no-tls")
    else:
        if username:
            cmd += ["--username", username]
        if password:
            cmd += ["--password", password]
        if ca_cert:
            cmd += ["--ca-cert", ca_cert]
    return cmd


def _run_subprocess(cmd: list[str], log_path: Path, timeout_s: float) -> int:
    """Run a subprocess, teeing stdout+stderr into a log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log_fh:
        try:
            proc = subprocess.run(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                cwd=str(SRC_DIR),
                timeout=timeout_s,
                check=False,
            )
            return proc.returncode
        except subprocess.TimeoutExpired:
            log_fh.write("\n[harness] simulator subprocess timed out and was killed\n")
            return -1
        except FileNotFoundError:
            log_fh.write("\n[harness] python executable not found\n")
            return -2


# ---------------------------------------------------------------------------
# Controller restart hook (audit 9.5, claim C12)
# ---------------------------------------------------------------------------


def _execute_restart_cmd(template: str, run_id: str, record: dict[str, Any]) -> None:
    """Execute the restart command once and record the outcome in-place."""
    cmd_str = format_cmd_template(template, run_id)
    record["command"] = cmd_str
    record["executed"] = True
    record["started_utc"] = utc_now_iso()
    record["started_monotonic_ns"] = time.monotonic_ns()
    try:
        proc = subprocess.run(
            shlex.split(cmd_str, posix=True),
            capture_output=True,
            text=True,
            timeout=FETCH_TIMEOUT_S,
            check=False,
        )
        record["returncode"] = proc.returncode
        stderr_tail = (proc.stderr or "").strip()
        if stderr_tail:
            record["stderr_tail"] = stderr_tail[-500:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        record["returncode"] = None
        record["error"] = str(exc)
    record["finished_utc"] = utc_now_iso()


# ---------------------------------------------------------------------------
# External conditions ingestion (audit 9.6, claim C15)
# ---------------------------------------------------------------------------


def _duration_defect(value: Any) -> str | None:
    """Classify a ``duration_s`` value; None means it is acceptable.

    Strict rule (sprint P5.4 defect 4, extended to this third path): a
    duration must be a REAL number — ``bool`` is a subclass of ``int``, so
    ``isinstance(value, (int, float))`` alone accepts ``True``/``False`` —
    that is FINITE (``json.loads`` reads the bare ``NaN``/``Infinity``
    tokens a hand-written file may carry, and neither ``nan < 0`` nor
    ``inf < 0`` is True, so a bare comparison lets both through) and
    NON-NEGATIVE. The analysis readers and the resources ingest already
    apply exactly these semantics.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "not a number"
    try:
        number = float(value)
    except (OverflowError, ValueError):
        # JSON integers are unbounded; one too large for a float is not a
        # duration either (and float() on it raises rather than returning inf).
        return "not finite (too large)"
    if not math.isfinite(number):
        return "not finite"
    if number < 0:
        return "negative"
    return None


def _is_functional_external_condition(condition: Any) -> bool:
    """True when ``condition`` names a functional (outcome-measured) one.

    Accepts the plan condition_id and its run-id prefix alike (the operator
    files say ``qemu_boot``, the plan says ``qemu_boots``), reusing the same
    tolerance as the condition match itself.
    """
    return any(
        _condition_matches(condition, functional_id)
        for functional_id in FUNCTIONAL_EXTERNAL_CONDITION_IDS
    )


def load_external_timings(
    path: str | Path, *, condition_id: str | None = None
) -> dict[str, Any]:
    """Load and validate an operator-produced timings.json.

    Expected shape (documented in the experiments README)::

        {"run_id": "...", "condition": "...",
         "samples": [{"label": "...", "started_utc": "...",
                      "ended_utc": "...", "duration_s": 12.3}, ...],
         "method": "...", "notes": "..."}

    Every sample needs a real, finite, non-negative ``duration_s``
    (:func:`_duration_defect`). Samples of a FUNCTIONAL external condition
    (:data:`FUNCTIONAL_EXTERNAL_CONDITION_IDS` — QEMU boots, which plan 5.1
    keeps functional-only, so pass/fail IS the measurement) additionally
    need an ``outcome`` from :data:`EXTERNAL_FUNCTIONAL_OUTCOMES`; without
    one the run carries no boot result and must never be sealed as evidence
    of a boot. ``condition_id`` is the PLAN's condition for this run and
    takes precedence over the file's own ``condition`` field; when it is
    omitted (direct calls) the file's field decides.

    Raises ValueError with a human-readable message on any problem: the
    message names the offending sample and value.
    """
    path = Path(path)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read timings file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"timings file {path} is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("timings.json must be a JSON object")
    for key in ("run_id", "condition", "samples"):
        if key not in obj:
            raise ValueError(f"timings.json missing required key {key!r}")
    samples = obj["samples"]
    if not isinstance(samples, list) or not samples:
        raise ValueError("timings.json 'samples' must be a non-empty list")
    condition = condition_id if condition_id is not None else obj["condition"]
    functional = _is_functional_external_condition(condition)
    for i, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"timings.json sample {i} is not an object")
        duration = sample.get("duration_s")
        defect = _duration_defect(duration)
        if defect is not None:
            raise ValueError(
                f"timings.json sample {i} needs a numeric duration_s >= 0: "
                f"{duration!r} is {defect}"
            )
        if functional:
            outcome = sample.get("outcome")
            if outcome not in EXTERNAL_FUNCTIONAL_OUTCOMES:
                raise ValueError(
                    f"timings.json sample {i} "
                    f"(label {sample.get('label')!r}) of functional condition "
                    f"{condition!r} needs an 'outcome' of "
                    + "/".join(repr(o) for o in EXTERNAL_FUNCTIONAL_OUTCOMES)
                    + f", got {outcome!r}: the boot result IS the measurement "
                    "(plan 5.1), and any other value is read by the analysis "
                    "as 'unspecified', i.e. as no result at all"
                )
    return obj


def _condition_matches(timings_condition: Any, condition_id: str) -> bool:
    """Accept the plan condition_id or its run-id prefix (qemu_boot[s])."""
    if not isinstance(timings_condition, str):
        return False
    if timings_condition == condition_id:
        return True
    # plan condition 'qemu_boots' enumerates run_ids 'qemu_boot-rNN'.
    return timings_condition.rstrip("s") == condition_id.rstrip("s")


def execute_external_run(
    plan_path: Path,
    entry: dict[str, Any],
    *,
    base_dir: Path,
    external_timings: str | Path,
    external_logs: str | Path | None,
    sut_env_from: str | Path | None,
) -> int:
    """Ingest an operator-measured external run (audit 9.6).

    Copies timings.json (+ optional logs/) into the standard raw run
    directory, captures the load-generator environment, writes the
    standard manifest and SHA256SUMS, and marks the plan entry completed.
    """
    run_id = entry["run_id"]
    condition_id = entry.get("condition_id")
    try:
        # The PLAN's condition decides which rules apply to the samples: a
        # functional condition (QEMU boots) needs a pass/fail outcome per
        # sample, a timed one (cold_start, twin_creation) does not.
        timings = load_external_timings(
            external_timings,
            condition_id=condition_id if isinstance(condition_id, str) else None,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if timings["run_id"] != run_id:
        print(
            f"error: timings.json run_id {timings['run_id']!r} does not "
            f"match --run-id {run_id!r}",
            file=sys.stderr,
        )
        return 2
    if not _condition_matches(timings["condition"], str(condition_id)):
        print(
            f"error: timings.json condition {timings['condition']!r} does "
            f"not match the plan condition {condition_id!r} for run "
            f"{run_id!r}",
            file=sys.stderr,
        )
        return 2

    run_dir = base_dir / "raw" / run_id
    if run_dir.exists():
        sealed_note = (
            f" The directory is sealed ({SUMS_FILENAME} present)."
            if run_dir_is_sealed(run_dir)
            else ""
        )
        print(
            f"error: {run_dir} already exists.{sealed_note} Raw run "
            "directories are immutable evidence (plan 5.8); a repeat "
            "requires a NEW run identity: use a new versioned run_id and "
            "document the exclusion of the old one.",
            file=sys.stderr,
        )
        return 2
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)
    warnings: list[str] = []

    print(f"[harness] external run {run_id}: created {run_dir}", flush=True)
    update_plan_status(plan_path, run_id, "running")

    write_loadgen_environment(run_dir / LOADGEN_ENVIRONMENT_FILENAME)
    sut_env_present = ingest_sut_environment(run_dir, sut_env_from, warnings)
    shutil.copyfile(external_timings, run_dir / "timings.json")
    if external_logs is not None:
        logs_src = Path(external_logs)
        if logs_src.is_dir():
            shutil.copytree(logs_src, logs_dir, dirs_exist_ok=True)
        else:
            warnings.append(f"--external-logs directory not found: {logs_src}")

    commit = read_git_commit()
    if commit is None:
        warnings.append("git commit unavailable")
    image_digests = parse_images_lock()
    if not image_digests:
        warnings.append(f"images.lock.env missing or empty at {IMAGES_LOCK_PATH}")

    # Mandatory artefacts of an external run (sprint P5, report 5.4):
    # manifest.json plus the ingested timings file. Both are produced above
    # by construction; the check guards against a failed copy leaving a
    # directory that would otherwise be sealed as if it were complete.
    missing_artifacts = missing_mandatory_artifacts(
        run_dir, condition_id, runner="external"
    )
    external_reasons = (
        [
            "mandatory artefact(s) missing from the run directory: "
            + ", ".join(missing_artifacts)
            + " — an incomplete external run is never sealed"
        ]
        if missing_artifacts
        else []
    )

    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "condition_id": condition_id,
        "runner": "external",
        "scenario": None,
        "repetition": entry.get("repetition"),
        "seed": entry.get("seed"),
        "commit": commit,
        "image_digests": image_digests,
        "environment_refs": {
            "loadgen": LOADGEN_ENVIRONMENT_FILENAME,
            "sut": SUT_ENVIRONMENT_FILENAME if sut_env_present else None,
        },
        "sut_environment_present": sut_env_present,
        "external_timings_ref": "timings.json",
        "external_method": timings.get("method"),
        "external_notes": timings.get("notes"),
        "external_sample_count": len(timings["samples"]),
        "ingested_utc": utc_now_iso(),
        # External runs are operator-measured; the timed-run SUT
        # env/resource requirements do not apply (audit 9.6). The SUT
        # environment is still recommended for cold_start/twin_creation.
        "validity": "invalid" if external_reasons else "valid",
        "validity_reasons": external_reasons,
        "missing_mandatory_artifacts": missing_artifacts,
        "exclusion": None,
        "warnings": warnings,
    }
    (run_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if missing_artifacts:
        for reason in external_reasons:
            print(f"[harness] INVALID: {reason}", file=sys.stderr, flush=True)
        update_plan_status(
            plan_path,
            run_id,
            "failed",
            result_dir=str(run_dir),
            finished_utc=manifest["ingested_utc"],
            validity="invalid",
        )
        return 1
    # Collection succeeded (the timings file is the evidence), so
    # SHA256SUMS is written now.
    write_sha256sums(run_dir)
    update_plan_status(
        plan_path,
        run_id,
        "completed",
        result_dir=str(run_dir),
        finished_utc=manifest["ingested_utc"],
        validity="valid",
    )
    print(f"[harness] external run {run_id} completed", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Timed (simulator-driven) runs
# ---------------------------------------------------------------------------


def execute_run(
    plan_path: str | Path,
    run_id: str,
    *,
    base_dir: str | Path | None = None,
    broker: str = "localhost",
    port: int = 8883,
    username: str | None = None,
    password: str | None = None,
    ca_cert: str | None = None,
    no_tls: bool = False,
    qos: int = 1,
    egw_id: str | None = None,
    event_log_dir: str | Path | None = None,
    post_run_wait_s: float | None = None,
    skip_warmup: bool = False,
    skip_cooldown: bool = False,
    fetch_events_cmd: str | None = None,
    sut_env_from: str | Path | None = None,
    resources_from: str | Path | None = None,
    local_resources: bool = False,
    allow_missing_sut_env: bool = False,
    allow_missing_resources: bool = False,
    allow_warmup_failure: bool = False,
    allow_protocol_deviation: bool = False,
    allow_missing_controller_marker: bool = False,
    controller_url: str | None = None,
    restart_cmd: str | None = None,
    restart_at_s: float | None = None,
    collector_start_cmd: str | None = None,
    collector_stop_cmd: str | None = None,
    collector_fetch_cmd: str | None = None,
    expect_services: list[str] | None = None,
    external_timings: str | Path | None = None,
    external_logs: str | Path | None = None,
    extra_deviations: list[dict[str, Any]] | None = None,
) -> int:
    """Execute one planned run end-to-end. Returns a process exit code.

    ``extra_deviations`` lets a caller that manages protocol structure
    ACROSS runs (the campaign batch runner, work order P1 item 12) record
    deviations it is responsible for — e.g. the skipped cooldown BEFORE
    this run — in this run's manifest; entries are {kind, detail,
    authorized_by_flag} and are deduplicated by kind like every other
    deviation.

    The optional collector hooks (sprint P5, report 5.3) make a single run
    — and therefore the campaign batch runner, which uses this same code
    path — end-to-end: ``collector_start_cmd`` runs BEFORE the warm-up,
    ``collector_stop_cmd`` AFTER the measured run and before the
    confirmation window, ``collector_fetch_cmd`` AFTER the confirmation
    window, producing the local resources.csv that then goes through the
    EXISTING validated ingest path. Each template accepts the ``{run_id}``,
    ``{duration_s}``, ``{dest}`` and ``{expect_services}`` placeholders.

    ``expect_services`` (``--expect-services``) names the services the
    collector must account for; it requires at least one collector hook
    (exit 2 otherwise, before anything is written). Whenever a collector
    hook is configured, :func:`inspect_collector_outputs` runs right after
    the fetch hook and its ``problems`` invalidate the timed run.
    """
    plan_path = Path(plan_path)
    try:
        plan = load_campaign_plan(plan_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read campaign plan {plan_path}: {exc}", file=sys.stderr)
        return 2

    entry = next(
        (r for r in plan.get("runs", []) if r.get("run_id") == run_id), None
    )
    if entry is None:
        print(f"error: run_id {run_id!r} not found in {plan_path}", file=sys.stderr)
        return 2

    base = Path(base_dir) if base_dir is not None else DEFAULT_RESULTS_BASE

    if entry.get("runner") != "simulator":
        if external_timings is None:
            print(
                f"error: run {run_id!r} belongs to condition "
                f"{entry.get('condition_id')!r}, which is not driven by the "
                "simulator. External runs (cold starts, twin creations, "
                "QEMU boots) are measured by the deployment/platform "
                "procedures and ingested with --external-timings "
                "<timings.json> [--external-logs <dir>] so the single "
                "analysis script covers them (see the experiments README "
                "and deployment/scripts/measure-cold-start.sh).",
                file=sys.stderr,
            )
            return 2
        return execute_external_run(
            plan_path,
            entry,
            base_dir=base,
            external_timings=external_timings,
            external_logs=external_logs,
            sut_env_from=(
                sut_env_from
                if sut_env_from is not None
                else os.environ.get(SUT_ENV_FILE_ENV)
            ),
        )
    if external_timings is not None:
        print(
            f"error: --external-timings is only valid for external "
            f"conditions; run {run_id!r} is simulator-driven.",
            file=sys.stderr,
        )
        return 2
    resource_inputs = [
        flag
        for flag, configured in (
            ("--resources-from", resources_from is not None),
            ("--collector-fetch-cmd", collector_fetch_cmd is not None),
            ("--local-resources", local_resources),
        )
        if configured
    ]
    if len(resource_inputs) > 1:
        print(
            "error: " + " and ".join(resource_inputs) + " are mutually "
            "exclusive (the manifest records exactly one resource_source).",
            file=sys.stderr,
        )
        return 2
    collector_hooks_in_use = any(
        (collector_start_cmd, collector_stop_cmd, collector_fetch_cmd)
    )
    if expect_services is not None:
        try:
            expect_services = (
                parse_expected_services(expect_services)
                if isinstance(expect_services, str)
                else validate_expected_services(list(expect_services))
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not collector_hooks_in_use:
            print(
                "error: --expect-services is enforced against the output the "
                "collector hooks fetch (--collector-start-cmd / "
                "--collector-stop-cmd / --collector-fetch-cmd); it cannot be "
                "used without them.",
                file=sys.stderr,
            )
            return 2

    if fetch_events_cmd is None:
        fetch_events_cmd = os.environ.get(FETCH_EVENTS_CMD_ENV) or None
    if sut_env_from is None:
        sut_env_from = os.environ.get(SUT_ENV_FILE_ENV) or None

    egw_id = egw_id or os.environ.get("EGW_ID", "egw-01")
    event_log_dir = Path(
        event_log_dir
        if event_log_dir is not None
        else os.environ.get("EGW_EVENT_LOG_DIR", "./data/events")
    )
    if post_run_wait_s is None:
        post_run_wait_s = float(CONFIRMATION_WINDOW_S)

    run_dir = base / "raw" / run_id
    if run_dir.exists():
        sealed_note = (
            f" The directory is sealed ({SUMS_FILENAME} present)."
            if run_dir_is_sealed(run_dir)
            else ""
        )
        print(
            f"error: {run_dir} already exists.{sealed_note} Raw run "
            "directories are immutable evidence (plan 5.8); a repeat "
            "requires a NEW run identity: use a new versioned run_id and "
            "document the exclusion of the old one. To re-attempt "
            "COLLECTION for this existing run use: "
            f"python -m egw_experiments collect --run-id {run_id}",
            file=sys.stderr,
        )
        return 2

    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)
    warnings: list[str] = []

    print(f"[harness] run {run_id}: created {run_dir}", flush=True)
    update_plan_status(plan_path, run_id, "running")

    # Two environments (audit 9.2): the harness host capture is the LOAD
    # GENERATOR; the SUT capture comes from the VM via --sut-env-from.
    write_loadgen_environment(run_dir / LOADGEN_ENVIRONMENT_FILENAME)
    sut_env_present = ingest_sut_environment(run_dir, sut_env_from, warnings)
    # SUT environment QUALITY (work order P1 fix 4): presence alone is not
    # enough; a manifest without the REQUIRED_SUT_FIELDS is unusable.
    sut_env_missing_fields: list[str] = []
    if sut_env_present:
        sut_env_missing_fields = validate_sut_environment(
            read_sut_environment(run_dir)
        )
        if sut_env_missing_fields:
            warnings.append(
                "sut_environment.json missing required field(s): "
                + ", ".join(sut_env_missing_fields)
            )

    commit = read_git_commit()
    if commit is None:
        warnings.append("git commit unavailable")
    image_digests = parse_images_lock()
    if not image_digests:
        warnings.append(f"images.lock.env missing or empty at {IMAGES_LOCK_PATH}")

    scenario: str = entry["scenario"]
    seed: int = int(entry["seed"])
    duration_s: int = int(entry["duration_s"])
    rate_msg_s: float = float(entry["rate_msg_s"])
    warmup_s: int = int(entry.get("warmup_s") or 0)
    cooldown_s: int = int(entry.get("cooldown_s") or 0)
    condition_id = entry.get("condition_id")
    timed = condition_id in TIMED_CONDITION_IDS or entry.get("runner") == "simulator"

    started_utc = utc_now_iso()
    sim_output_dir = logs_dir / "simulator"
    sim_returncode: int | None = None
    warmup_returncode: int | None = None

    # Restart hook (claim C12): scheduled relative to the measured run start.
    restart_record: dict[str, Any] | None = None
    restart_timer: threading.Timer | None = None
    if restart_cmd is not None:
        if restart_at_s is None:
            restart_at_s = duration_s / 2.0
        restart_record = {
            "template": restart_cmd,
            "requested_at_s": restart_at_s,
            "executed": False,
            "returncode": None,
        }

    # Resource sampling: SUT collector output is ingested AFTER the run
    # (--resources-from or the --collector-fetch-cmd hook); the local
    # sampler measures THIS host and is a dev-only opt-in (audit 9.1).
    local_sampler = (
        ResourceSampler(run_dir / "resources.csv") if local_resources else None
    )
    metrics_sampler = (
        ControllerMetricsSampler(run_dir / "controller_metrics.csv", controller_url)
        if controller_url
        else None
    )

    # SUT collector hooks (sprint P5, report 5.3). The collector must cover
    # the whole protocol structure of this run: warm-up + measured window +
    # confirmation window (plus a start-up margin), which is what the
    # {duration_s} placeholder carries to a self-terminating collector.
    collector_hooks: list[dict[str, Any]] = []
    collector_window_s = (
        (0 if skip_warmup else warmup_s)
        + duration_s
        + int(post_run_wait_s)
        + COLLECTOR_DURATION_MARGIN_S
    )
    collector_dest = (
        logs_dir / COLLECTOR_FETCH_SUBDIR / f"resources-{run_id}.csv"
    )

    def _run_collector_hook(hook: str, template: str | None) -> None:
        if not template:
            return
        print(
            f"[harness] collector hook {COLLECTOR_HOOK_FLAGS[hook]}",
            flush=True,
        )
        record = execute_collector_hook(
            hook,
            template,
            run_id,
            duration_s=collector_window_s,
            dest=collector_dest,
            expect_services=expect_services,
            log_dir=collector_dest.parent,
        )
        # The full hook output is kept beside the fetched files (sealed with
        # them); the manifest names it relative to the run directory.
        for stream in ("stdout", "stderr"):
            path = record.pop(f"{stream}_path", None)
            if path is not None:
                record[f"{stream}_file"] = (
                    Path(path).relative_to(run_dir).as_posix()
                )
        collector_hooks.append(record)
        if record.get("returncode") != 0:
            print(
                f"[harness] collector hook {COLLECTOR_HOOK_FLAGS[hook]} "
                f"FAILED (exit {record.get('returncode')})",
                file=sys.stderr,
                flush=True,
            )

    if collector_hooks_in_use:
        collector_dest.parent.mkdir(parents=True, exist_ok=True)
    # Started BEFORE the warm-up so the collector covers the whole run.
    _run_collector_hook("start", collector_start_cmd)

    try:
        if local_sampler is not None:
            local_sampler.__enter__()
        if metrics_sampler is not None:
            metrics_sampler.__enter__()

        if warmup_s > 0 and not skip_warmup:
            print(f"[harness] warm-up: {warmup_s} s", flush=True)
            warmup_returncode = _run_subprocess(
                _simulator_cmd(
                    scenario=scenario,
                    seed=seed,
                    duration_s=warmup_s,
                    rate_msg_s=rate_msg_s,
                    output_dir=logs_dir / "warmup",
                    run_id=f"{run_id}.warmup",
                    broker=broker,
                    port=port,
                    egw_id=egw_id,
                    qos=qos,
                    username=username,
                    password=password,
                    ca_cert=ca_cert,
                    no_tls=no_tls,
                ),
                logs_dir / "warmup.log",
                timeout_s=warmup_s + SUBPROCESS_GRACE_S,
            )
            if warmup_returncode != 0:
                warnings.append(f"warm-up exited with code {warmup_returncode}")

        print(f"[harness] measured run: {duration_s} s at {rate_msg_s} msg/s", flush=True)
        # Measured window (audit 9.4): wall-clock stamps immediately around
        # the measured simulator invocation; see MEASURED_WINDOW_CLOCK_NOTE.
        measured_start_utc = utc_now_iso()
        measured_started_monotonic_ns = time.monotonic_ns()
        if restart_record is not None:
            restart_timer = threading.Timer(
                float(restart_at_s),
                _execute_restart_cmd,
                args=(restart_cmd, run_id, restart_record),
            )
            restart_timer.daemon = True
            restart_timer.start()
        sim_returncode = _run_subprocess(
            _simulator_cmd(
                scenario=scenario,
                seed=seed,
                duration_s=duration_s,
                rate_msg_s=rate_msg_s,
                output_dir=sim_output_dir,
                run_id=run_id,
                broker=broker,
                port=port,
                egw_id=egw_id,
                qos=qos,
                username=username,
                password=password,
                ca_cert=ca_cert,
                no_tls=no_tls,
            ),
            logs_dir / "simulator.log",
            timeout_s=duration_s + SUBPROCESS_GRACE_S,
        )
        if restart_timer is not None:
            restart_timer.cancel()
            restart_timer.join(timeout=FETCH_TIMEOUT_S + 30.0)
        finished_monotonic_ns = time.monotonic_ns()
        finished_utc = utc_now_iso()
        measured_end_utc = finished_utc

        # Confirmation marker (sprint P5, report 5.2; timing corrected in
        # P5.4 defect 5): stamp the run end in the CONTROLLER's clock domain
        # HERE — immediately after finished_utc, still inside the try, BEFORE
        # the samplers are joined and before any hook. Anything done first
        # would push the marker later and silently widen the confirmation
        # window: joining the samplers alone can wait on an in-flight 20 s
        # docker-stats call or a 5 s /metrics fetch (each __exit__ joins with
        # a 30 s timeout), and the analysis trusts the resulting deadline
        # verbatim. The 60 s value itself is unchanged; only the instant it
        # is counted from is fixed correctly.
        controller_marker = poll_controller_marker(controller_url)
        controller_marker_polled_monotonic_ns = time.monotonic_ns()
    finally:
        if metrics_sampler is not None:
            metrics_sampler.__exit__(None, None, None)
        if local_sampler is not None:
            local_sampler.__exit__(None, None, None)

    if restart_record is not None and not restart_record["executed"]:
        warnings.append(
            f"--restart-cmd was scheduled at {restart_at_s} s but the "
            "measured run ended before it fired; no restart was executed"
        )
    if local_sampler is not None and local_sampler.error:
        warnings.append(f"local resource sampling degraded: {local_sampler.error}")
        print(f"[harness] warning: {local_sampler.error}", flush=True)
    if metrics_sampler is not None and metrics_sampler.poll_errors:
        warnings.append(
            f"controller metrics sampler had {metrics_sampler.poll_errors} "
            f"failed poll(s); last error: {metrics_sampler.last_error}"
        )
    if metrics_sampler is not None and metrics_sampler.invalid_values:
        # Strict numeric rule (P5.4 defect 4): refused counter values are
        # empty cells in controller_metrics.csv, never 'inf'/'nan'/'-1'.
        warnings.append(
            f"controller metrics sampler refused "
            f"{metrics_sampler.invalid_values} counter value(s) that are not "
            f"non-negative integers; last: {metrics_sampler.last_invalid}"
        )
    if sim_returncode != 0:
        warnings.append(f"simulator exited with code {sim_returncode}")

    # Marker lag (P5.4 defect 5): how long after the end of the measured
    # window the marker was actually read. The window it anchors is
    # effectively CONFIRMATION_WINDOW_S + lag, so the lag is recorded with
    # the marker and an excess is reported as a warning AND a deviation.
    # Measured on the harness monotonic clock (same domain as
    # finished_monotonic_ns), which is the elapsed wall time between
    # finished_utc and the marker poll without wall-clock step risk.
    controller_marker_lag_s = max(
        0.0,
        (controller_marker_polled_monotonic_ns - finished_monotonic_ns) / 1e9,
    )
    controller_marker["lag_s"] = round(controller_marker_lag_s, 6)
    controller_marker["lag_tolerance_s"] = CONTROLLER_MARKER_LAG_TOLERANCE_S
    marker_lag_exceeded = (
        controller_marker_lag_s > CONTROLLER_MARKER_LAG_TOLERANCE_S
    )
    if marker_lag_exceeded:
        warnings.append(
            f"the confirmation marker was polled {controller_marker_lag_s:.3f} "
            f"s after the end of the measured window, above the "
            f"{CONTROLLER_MARKER_LAG_TOLERANCE_S:.3f} s tolerance "
            f"(CONTROLLER_MARKER_LAG_TOLERANCE_S): the {CONFIRMATION_WINDOW_S} "
            "s confirmation window is anchored on that later instant, so its "
            "effective grace was longer than the protocol prescribes"
        )
    if controller_marker["ok"]:
        controller_monotonic_at_run_end_ns = int(controller_marker["monotonic_ns"])
        confirmation_deadline_monotonic_ns: int | None = (
            controller_monotonic_at_run_end_ns
            + CONFIRMATION_WINDOW_S * 1_000_000_000
        )
        confirmation_deadline_clock_domain = "controller"
    else:
        controller_monotonic_at_run_end_ns = None
        confirmation_deadline_monotonic_ns = None
        confirmation_deadline_clock_domain = "unavailable"
        warnings.append(
            "controller confirmation marker unavailable: "
            f"{controller_marker['error']}"
        )

    # Collector stop hook: AFTER the measured run, BEFORE the confirmation
    # window (the collector must not keep sampling the idle system).
    _run_collector_hook("stop", collector_stop_cmd)

    # Confirmation window (plan 7.3): confirmations arriving up to 60 s after
    # the end of the run still count; wait before collecting the event log.
    if post_run_wait_s > 0:
        print(
            f"[harness] waiting {post_run_wait_s:.0f} s confirmation window",
            flush=True,
        )
        time.sleep(post_run_wait_s)

    # Collector fetch hook: AFTER the confirmation window, producing the
    # local CSV that goes through the EXISTING validated ingest path below,
    # with the collector's companions beside it in logs/collector/.
    _run_collector_hook("fetch", collector_fetch_cmd)
    resources_ingest_from: str | Path | None = resources_from
    resources_source_label = "--resources-from"
    if collector_fetch_cmd:
        resources_source_label = "--collector-fetch-cmd output"
        if collector_dest.is_file():
            resources_ingest_from = collector_dest
        else:
            warnings.append(
                f"--collector-fetch-cmd produced no file at {collector_dest}"
            )

    # Collector output accounting (2026-09-19), right after the fetch and
    # long before the seal: which files arrived, which collector produced
    # them, whether it stopped cleanly and whether every expected service
    # has rows. Every problem is a validity reason of the timed run.
    collector_record: dict[str, Any] = {
        "expected_services": expect_services,
        "hooks_in_use": collector_hooks_in_use,
    }
    collector_problems: list[str] = []
    if collector_hooks_in_use:
        inspection = inspect_collector_outputs(
            collector_dest, expect_services, run_dir=run_dir
        )
        if not collector_fetch_cmd:
            inspection["problems"].insert(
                0,
                "collector hooks are configured without --collector-fetch-cmd: "
                "the collector's CSV and companions were not fetched into "
                f"logs/{COLLECTOR_FETCH_SUBDIR}/",
            )
        collector_record.update(inspection)
        collector_problems = list(inspection["problems"])
        for problem in collector_problems:
            warnings.append(f"collector output problem: {problem}")
        if inspection["unexpected_services"]:
            warnings.append(
                "collector CSV holds rows of services outside "
                "--expect-services (not a validity problem): "
                + ", ".join(inspection["unexpected_services"])
            )
        for problem in collector_problems:
            print(
                f"[harness] collector output problem: {problem}",
                file=sys.stderr,
                flush=True,
            )

    # Simulator outputs: sent_events.jsonl to the run root (the analysis
    # joins on it); the simulator's own manifest stays where the simulator
    # wrote it, logs/simulator/<run_id>/ (P1c fix F0: the simulator writes
    # under <output>/<run_id>/, never directly into <output>/ — see
    # simulator_run_dir and egw_simulator.runner).
    sent_src = simulator_run_dir(sim_output_dir, run_id) / "sent_events.jsonl"
    if sent_src.is_file():
        shutil.copyfile(sent_src, run_dir / "sent_events.jsonl")
    else:
        warnings.append(f"simulator sent_events.jsonl not found at {sent_src}")

    # Events collection (audit 9.3): fetch command first, local fallback.
    fetch_info: dict[str, Any] = {}
    events_source = collect_events(
        run_id=run_id,
        dest=run_dir / "events.jsonl",
        fetch_events_cmd=fetch_events_cmd,
        event_log_dir=event_log_dir,
        warnings=warnings,
        fetch_info=fetch_info,
    )
    if events_source is None:
        print(
            f"[harness] error: events.jsonl for {run_id!r} was NOT "
            "collected; SHA256SUMS is withheld. Recover with: "
            f"python -m egw_experiments collect --run-id {run_id} "
            "--fetch-events-cmd '...'",
            file=sys.stderr,
            flush=True,
        )

    # SUT resources ingestion (audit 9.1), content- AND semantically
    # validated against this run's measured window (sprint P5, report 5.4).
    measured_window_s = max(
        0.0, (finished_monotonic_ns - measured_started_monotonic_ns) / 1e9
    )
    if ingest_resources(
        run_dir,
        resources_ingest_from,
        warnings,
        expected_window_s=measured_window_s,
        expected_window_start_utc=measured_start_utc,
        expected_window_end_utc=measured_end_utc,
        source_label=resources_source_label,
    ):
        resource_source = "sut-collector"
    elif local_resources:
        resource_source = "local-dev"
    else:
        resource_source = "none"

    restart_ok = (
        restart_record is not None and restart_record.get("returncode") == 0
    )

    # Protocol-deviation record (work order P1 fix 5): every departure from
    # the frozen protocol is written down, whether authorized by an explicit
    # flag (authorized_by_flag set) or not (None; those normally also
    # produce a validity reason).
    deviations: list[dict[str, Any]] = []
    for extra in extra_deviations or []:
        _append_deviation(
            deviations,
            str(extra.get("kind")),
            str(extra.get("detail")),
            extra.get("authorized_by_flag"),
        )
    if skip_warmup:
        _append_deviation(
            deviations,
            "skip_warmup",
            f"planned warm-up ({warmup_s} s) skipped via --skip-warmup on "
            f"condition {condition_id!r}",
            "--allow-protocol-deviation" if allow_protocol_deviation else None,
        )
    if warmup_returncode not in (0, None):
        _append_deviation(
            deviations,
            "warmup_nonzero_exit",
            f"warm-up simulator subprocess exited with code "
            f"{warmup_returncode}",
            "--allow-warmup-failure" if allow_warmup_failure else None,
        )
    if float(post_run_wait_s) != float(CONFIRMATION_WINDOW_S):
        _append_deviation(
            deviations,
            "confirmation_window_override",
            f"post-run wait {post_run_wait_s} s differs from the protocol "
            f"confirmation window {CONFIRMATION_WINDOW_S} s (plan 7.3)",
            "--post-run-wait",
        )
    if skip_cooldown and cooldown_s > 0:
        _append_deviation(
            deviations,
            "cooldown_skipped",
            f"planned cooldown ({cooldown_s} s) skipped via --skip-cooldown",
            "--skip-cooldown",
        )
    if (
        timed
        and allow_missing_sut_env
        and (not sut_env_present or sut_env_missing_fields)
    ):
        _append_deviation(
            deviations,
            "missing_sut_environment",
            "timed run without a usable sut_environment.json accepted"
            + (
                f" (present but missing: {', '.join(sut_env_missing_fields)})"
                if sut_env_present
                else " (file absent)"
            ),
            "--allow-missing-sut-env",
        )
    if timed and allow_missing_resources and resource_source != "sut-collector":
        _append_deviation(
            deviations,
            "missing_sut_resources",
            "timed run without SUT-collector resources accepted "
            f"(resource_source: {resource_source})",
            "--allow-missing-resources",
        )
    if marker_lag_exceeded:
        _append_deviation(
            deviations,
            "confirmation_marker_lag",
            f"the confirmation marker was polled {controller_marker_lag_s:.3f} "
            "s after the end of the measured window (tolerance "
            f"{CONTROLLER_MARKER_LAG_TOLERANCE_S:.3f} s): the "
            f"{CONFIRMATION_WINDOW_S} s confirmation window of this run was "
            "counted from an instant later than the true run end, so late "
            "confirmations may have been accepted in-window",
            None,
        )
    if timed and not controller_marker["ok"]:
        _append_deviation(
            deviations,
            "confirmation_marker_unavailable",
            "the run end was not stamped in the controller's clock domain "
            f"({controller_marker['error']}); the analysis must fall back to "
            "the legacy event-derived confirmation deadline",
            (
                "--allow-missing-controller-marker"
                if allow_missing_controller_marker
                else None
            ),
        )

    # Mandatory artefacts per condition kind (sprint P5, report 5.4): an
    # incomplete run is INVALID and is never sealed.
    missing_artifacts = missing_mandatory_artifacts(
        run_dir,
        condition_id,
        runner="simulator",
        allow_missing_resources=allow_missing_resources,
    )

    validity, validity_reasons = compute_validity(
        timed=timed,
        sut_env_present=sut_env_present,
        allow_missing_sut_env=allow_missing_sut_env,
        resource_source=resource_source,
        allow_missing_resources=allow_missing_resources,
        restart_required=condition_id == "controller_restart",
        restart_ok=restart_ok,
        sut_env_missing_fields=sut_env_missing_fields,
        simulator_returncode=sim_returncode,
        warmup_returncode=warmup_returncode,
        allow_warmup_failure=allow_warmup_failure,
        skip_warmup=skip_warmup,
        condition_id=condition_id,
        allow_protocol_deviation=allow_protocol_deviation,
        confirmation_marker_ok=bool(controller_marker["ok"]),
        allow_missing_controller_marker=allow_missing_controller_marker,
        collector_hooks=collector_hooks,
        missing_artifacts=missing_artifacts,
        collector_problems=collector_problems,
    )
    if validity == "invalid":
        for reason in validity_reasons:
            print(f"[harness] INVALID: {reason}", file=sys.stderr, flush=True)

    ok = sim_returncode == 0 and events_source is not None and validity == "valid"

    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "plan_master_seed": plan.get("master_seed"),
        "run_id": run_id,
        "condition_id": condition_id,
        "runner": "simulator",
        "scenario": scenario,
        "repetition": entry.get("repetition"),
        "seed": seed,
        "rate_msg_s": rate_msg_s,
        "duration_s": duration_s,
        "warmup_s": 0 if skip_warmup else warmup_s,
        "cooldown_s": cooldown_s,
        "commit": commit,
        "image_digests": image_digests,
        # Two environments (audit 9.2): sut = the system under test (ARM
        # VM), loadgen = the harness/simulator host.
        "environment_refs": {
            "loadgen": LOADGEN_ENVIRONMENT_FILENAME,
            "sut": SUT_ENVIRONMENT_FILENAME if sut_env_present else None,
        },
        "sut_environment_present": sut_env_present,
        "sut_environment_missing_fields": sut_env_missing_fields,
        "allow_missing_sut_env": allow_missing_sut_env,
        "resource_source": resource_source,
        "allow_missing_resources": allow_missing_resources,
        "allow_warmup_failure": allow_warmup_failure,
        "allow_protocol_deviation": allow_protocol_deviation,
        "allow_missing_controller_marker": allow_missing_controller_marker,
        # Protocol deviations (work order P1 fix 5): {kind, detail,
        # authorized_by_flag} entries; the analysis lists them per run.
        "deviations": deviations,
        # SUT collector hooks (sprint P5, report 5.3): every hook's command,
        # exit code and start/end timestamps, in execution order.
        "collector_hooks": collector_hooks,
        # Collector output accounting (manifest 1.4): what the fetch hook
        # delivered, which collector produced it, its inventory, the rows
        # per expected service and the problems that invalidate the run.
        "collector": collector_record,
        # Mandatory evidence of this condition kind that is absent (report
        # 5.4). Non-empty => validity 'invalid' AND no SHA256SUMS.
        "missing_mandatory_artifacts": missing_artifacts,
        "controller_metrics": (
            {
                "url": controller_url,
                "samples_written": metrics_sampler.samples_written,
                "poll_errors": metrics_sampler.poll_errors,
                "last_error": metrics_sampler.last_error,
                # Strict numeric rule (P5.4 defect 4): counter values that
                # are not non-negative integers are written as empty cells.
                "invalid_values": metrics_sampler.invalid_values,
                "last_invalid_value": metrics_sampler.last_invalid,
            }
            if metrics_sampler is not None
            else None
        ),
        # Config echo: the plan entry plus the effective CLI parameters.
        # Secrets are never echoed (plan 9.2).
        "config": {
            "plan_entry": entry,
            "cli": {
                "broker": broker,
                "port": port,
                "no_tls": no_tls,
                "qos": qos,
                "egw_id": egw_id,
                "username": username,
                "password": "<redacted>" if password else None,
                "ca_cert": ca_cert,
                "event_log_dir": str(event_log_dir),
                "post_run_wait_s": post_run_wait_s,
                "skip_warmup": skip_warmup,
                "skip_cooldown": skip_cooldown,
                "fetch_events_cmd": fetch_events_cmd,
                "sut_env_from": str(sut_env_from) if sut_env_from else None,
                "resources_from": str(resources_from) if resources_from else None,
                "local_resources": local_resources,
                "allow_missing_sut_env": allow_missing_sut_env,
                "allow_missing_resources": allow_missing_resources,
                "allow_warmup_failure": allow_warmup_failure,
                "allow_protocol_deviation": allow_protocol_deviation,
                "allow_missing_controller_marker": (
                    allow_missing_controller_marker
                ),
                "controller_url": controller_url,
                "restart_cmd": restart_cmd,
                "restart_at_s": restart_at_s,
                "collector_start_cmd": collector_start_cmd,
                "collector_stop_cmd": collector_stop_cmd,
                "collector_fetch_cmd": collector_fetch_cmd,
                "expect_services": expect_services,
            },
        },
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "finished_monotonic_ns": finished_monotonic_ns,
        # Measured window (audit 9.4): the analysis filters resources.csv
        # and controller_metrics.csv to this window so warm-up/cooldown
        # samples never contaminate the measured aggregates. events.jsonl
        # needs no such filtering: the warm-up runs under run_id
        # '<run_id>.warmup', so the measured run's event log contains only
        # measured-run events.
        "measured_window_utc": {
            "start": measured_start_utc,
            "end": measured_end_utc,
        },
        "measured_started_monotonic_ns": measured_started_monotonic_ns,
        "measured_window_clock": MEASURED_WINDOW_CLOCK_NOTE,
        "confirmation_window_s": CONFIRMATION_WINDOW_S,
        # Confirmation deadline (sprint P5, report 5.2). Anchored on the
        # controller's own monotonic clock, read from GET /metrics
        # immediately after the run-end stamp — before the samplers are
        # joined and before any hook (P5.4 defect 5) — and BEFORE the
        # confirmation window, so the deadline is independent of the late
        # events it judges. Null (clock domain 'unavailable') when the
        # controller could not be polled; the analysis then falls back to
        # the legacy event-derived deadline and says so loudly. The record
        # carries 'lag_s' (seconds between the end of the measured window
        # and the poll) and the 'lag_tolerance_s' it is judged against.
        "controller_marker": controller_marker,
        "controller_monotonic_at_run_end_ns": controller_monotonic_at_run_end_ns,
        "confirmation_deadline_monotonic_ns": confirmation_deadline_monotonic_ns,
        "confirmation_deadline_clock_domain": confirmation_deadline_clock_domain,
        "simulator_returncode": sim_returncode,
        "warmup_returncode": warmup_returncode,
        "events_source": events_source,
        "events_fetch": fetch_info or None,
        "restart": restart_record,
        "resource_samples_written": (
            local_sampler.samples_written if local_sampler is not None else None
        ),
        "resource_sampling_error": (
            local_sampler.error if local_sampler is not None else None
        ),
        "validity": validity,
        "validity_reasons": validity_reasons,
        # Exclusion criteria (plan 5.8/7.3): filled in manually, with a
        # documented cause, only for proven cloud/instrumentation/config
        # failures. A slow run is never excluded for its result alone.
        "exclusion": None,
        "warnings": warnings,
    }
    (run_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # SHA256SUMS is written last so it covers every file in the run dir —
    # and ONLY when the run is COMPLETE (audit 9.3, hardened in sprint P5 /
    # report 5.4): an incomplete run directory must never look like sealed
    # evidence, so any missing mandatory artefact (events.jsonl among them)
    # withholds the seal. The 'collect' subcommand re-attempts collection
    # and writes it then. Collector output problems invalidate the run but
    # do not withhold the seal: the files in logs/collector/ (fetched output,
    # companions, full hook output) are sealed exactly as they arrived, so
    # the reasons recorded in the manifest stay verifiable.
    if not missing_artifacts:
        write_sha256sums(run_dir)
    else:
        print(
            f"[harness] error: run {run_id!r} is missing mandatory "
            "artefact(s) " + ", ".join(missing_artifacts) + "; SHA256SUMS "
            "is withheld. Recover with: python -m egw_experiments collect "
            f"--run-id {run_id} ...",
            file=sys.stderr,
            flush=True,
        )

    update_plan_status(
        plan_path,
        run_id,
        "completed" if ok else "failed",
        result_dir=str(run_dir),
        finished_utc=finished_utc,
        validity=validity,
    )

    # Cooldown between load-sweep runs (plan 7.1). Part of it was already
    # spent waiting for the confirmation window.
    remaining_cooldown = max(0.0, cooldown_s - post_run_wait_s)
    if remaining_cooldown > 0 and not skip_cooldown:
        print(f"[harness] cooldown: {remaining_cooldown:.0f} s", flush=True)
        time.sleep(remaining_cooldown)

    print(f"[harness] run {run_id} {'completed' if ok else 'FAILED'}", flush=True)
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Recovery: the 'collect' subcommand (audit 9.3)
# ---------------------------------------------------------------------------


def collect_run(
    run_id: str,
    *,
    base_dir: str | Path | None = None,
    plan_path: str | Path | None = None,
    fetch_events_cmd: str | None = None,
    event_log_dir: str | Path | None = None,
    sut_env_from: str | Path | None = None,
    resources_from: str | Path | None = None,
    allow_missing_sut_env: bool = False,
    allow_missing_resources: bool = False,
    allow_missing_controller_marker: bool = False,
) -> int:
    """Re-attempt evidence collection for an EXISTING run directory.

    Recovery path for runs whose post-run collection failed (audit 9.3):
    instead of refusing to reuse the run_id, this re-attempts the
    events/resources/SUT-environment collection, recomputes validity,
    updates the manifest (with a ``collect_history`` audit trail) and
    (re)writes SHA256SUMS — but ONLY after successful collection. Intended
    for use BEFORE the data freeze; after ``data-v1`` raw directories are
    immutable.

    Sealed-raw rules (work order P1 item 11): a run dir with SHA256SUMS is
    sealed. This subcommand is the ONLY path allowed to ADD a genuinely
    missing file to a sealed dir — it first verifies every existing
    checksum (refusing on any mismatch), then adds the file, records
    {when_utc, added_files} in the manifest's ``collection_history`` and
    rewrites SHA256SUMS. Existing raw files are NEVER overwritten with
    different content (SealedRunError => exit 2); identical re-copies are
    no-ops, so re-running collect is idempotent.
    """
    base = Path(base_dir) if base_dir is not None else DEFAULT_RESULTS_BASE
    plan_path = Path(plan_path) if plan_path is not None else DEFAULT_PLAN_PATH
    run_dir = base / "raw" / run_id
    manifest_path = run_dir / "manifest.json"
    if not run_dir.is_dir() or not manifest_path.is_file():
        print(
            f"error: {run_dir} does not exist or has no manifest.json; "
            "'collect' only recovers runs already executed by 'run'.",
            file=sys.stderr,
        )
        return 2
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read {manifest_path}: {exc}", file=sys.stderr)
        return 2

    # Sealed-raw rules (work order P1 item 11): once SHA256SUMS exists the
    # directory is sealed. Adding a genuinely MISSING file is allowed only
    # here, and only after every existing checksum verifies — tampered or
    # inconsistent evidence is never silently resealed.
    sealed = run_dir_is_sealed(run_dir)
    if sealed:
        problems = verify_sha256sums(run_dir)
        if problems:
            print(
                f"error: {run_dir} is sealed ({SUMS_FILENAME} present) but "
                "fails integrity verification; collection refused. A sealed "
                "run directory whose checksums no longer verify cannot be "
                "extended — problems: " + "; ".join(problems),
                file=sys.stderr,
            )
            return 2
    pre_files = {
        p.relative_to(run_dir).as_posix()
        for p in run_dir.rglob("*")
        if p.is_file()
    }

    if fetch_events_cmd is None:
        fetch_events_cmd = os.environ.get(FETCH_EVENTS_CMD_ENV) or None
    if sut_env_from is None:
        sut_env_from = os.environ.get(SUT_ENV_FILE_ENV) or None
    event_log_dir = Path(
        event_log_dir
        if event_log_dir is not None
        else os.environ.get("EGW_EVENT_LOG_DIR", "./data/events")
    )

    warnings: list[str] = []
    actions: list[str] = []

    try:
        # Events: re-attempted while missing; raw evidence already present
        # is never overwritten. When events.jsonl exists AND a fetch
        # template is given, the fetch runs against a scratch destination
        # and the result is compared: identical => no-op (idempotent
        # collect), different => refused (work order P1 item 11).
        events_dest = run_dir / "events.jsonl"
        if events_dest.is_file():
            if fetch_events_cmd:
                with tempfile.TemporaryDirectory() as tmp:
                    probe = Path(tmp) / "events.jsonl"
                    ok, _cmd_str, _attempts = fetch_events_via_cmd(
                        fetch_events_cmd, run_id, probe
                    )
                    if not ok:
                        actions.append(
                            "events.jsonl already present (re-fetch failed; "
                            "existing raw copy kept)"
                        )
                    elif sha256_file(probe) == sha256_file(events_dest):
                        actions.append(
                            "events.jsonl already present (re-fetch "
                            "identical; no-op)"
                        )
                    else:
                        sealed_note = (
                            f"this run directory is sealed ({SUMS_FILENAME} "
                            "present)"
                            if sealed
                            else "raw run evidence is write-once"
                        )
                        raise SealedRunError(
                            f"refusing to overwrite events.jsonl in "
                            f"{run_dir}: the re-fetched content differs "
                            f"from the existing raw file; {sealed_note}. "
                            "Recording different evidence requires a NEW "
                            "run identity: repeat the run under a new "
                            "versioned run_id and document the exclusion "
                            "of the old one (plan 5.8)."
                        )
            else:
                actions.append("events.jsonl already present")
        else:
            fetch_info: dict[str, Any] = {}
            events_source = collect_events(
                run_id=run_id,
                dest=events_dest,
                fetch_events_cmd=fetch_events_cmd,
                event_log_dir=event_log_dir,
                warnings=warnings,
                fetch_info=fetch_info,
            )
            if events_source is not None:
                manifest["events_source"] = events_source
                if fetch_info:
                    manifest["events_fetch"] = fetch_info
                actions.append(f"collected events.jsonl from {events_source}")
            else:
                actions.append("events.jsonl collection failed again")

        # SUT environment: ingest when provided; ingest_copy makes an
        # identical re-ingest a no-op and refuses a differing one.
        if sut_env_from:
            was_present = (run_dir / SUT_ENVIRONMENT_FILENAME).is_file()
            if (
                ingest_sut_environment(run_dir, sut_env_from, warnings)
                and not was_present
            ):
                actions.append(f"ingested {SUT_ENVIRONMENT_FILENAME}")
    except SealedRunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sut_env_present = (run_dir / SUT_ENVIRONMENT_FILENAME).is_file()
    manifest["sut_environment_present"] = sut_env_present
    refs = manifest.get("environment_refs")
    if isinstance(refs, dict):
        refs["sut"] = SUT_ENVIRONMENT_FILENAME if sut_env_present else None

    # Resources: ingest the SUT collector output when provided (identical
    # re-ingest is a no-op; differing content is refused, P1 item 11). The
    # semantic window check reuses the measured window recorded by 'run'.
    measured_started_ns = manifest.get("measured_started_monotonic_ns")
    finished_ns = manifest.get("finished_monotonic_ns")
    expected_window_s = (
        max(0.0, (finished_ns - measured_started_ns) / 1e9)
        if isinstance(measured_started_ns, int) and isinstance(finished_ns, int)
        else None
    )
    measured_window = manifest.get("measured_window_utc")
    expected_window_start_utc = (
        measured_window.get("start") if isinstance(measured_window, dict) else None
    )
    expected_window_end_utc = (
        measured_window.get("end") if isinstance(measured_window, dict) else None
    )
    if resources_from is not None:
        try:
            if ingest_resources(
                run_dir,
                resources_from,
                warnings,
                expected_window_s=expected_window_s,
                expected_window_start_utc=expected_window_start_utc,
                expected_window_end_utc=expected_window_end_utc,
            ):
                manifest["resource_source"] = "sut-collector"
                actions.append("ingested resources.csv (sut-collector)")
        except SealedRunError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    resource_source = manifest.get("resource_source") or (
        "sut-collector" if (run_dir / "resources.csv").is_file() else "none"
    )
    manifest["resource_source"] = resource_source

    allow_missing_sut_env = allow_missing_sut_env or bool(
        manifest.get("allow_missing_sut_env")
    )
    allow_missing_resources = allow_missing_resources or bool(
        manifest.get("allow_missing_resources")
    )
    allow_missing_controller_marker = allow_missing_controller_marker or bool(
        manifest.get("allow_missing_controller_marker")
    )
    manifest["allow_missing_sut_env"] = allow_missing_sut_env
    manifest["allow_missing_resources"] = allow_missing_resources
    manifest["allow_missing_controller_marker"] = allow_missing_controller_marker

    # SUT environment quality (work order P1 fix 4): re-validate the file
    # currently in the run dir against REQUIRED_SUT_FIELDS.
    sut_env_missing_fields: list[str] = []
    if sut_env_present:
        sut_env_missing_fields = validate_sut_environment(
            read_sut_environment(run_dir)
        )
    manifest["sut_environment_missing_fields"] = sut_env_missing_fields

    timed = manifest.get("runner", "simulator") == "simulator"
    restart_record = manifest.get("restart")
    cli_echo = (manifest.get("config") or {}).get("cli") or {}
    allow_warmup_failure = bool(manifest.get("allow_warmup_failure"))
    allow_protocol_deviation = bool(manifest.get("allow_protocol_deviation"))
    skip_warmup = bool(cli_echo.get("skip_warmup"))
    # The confirmation marker is a RUN-TIME measurement: 'collect' can never
    # recover it after the fact, it can only re-apply the authorization.
    confirmation_marker_ok = (
        manifest.get("confirmation_deadline_clock_domain") == "controller"
    )
    collector_hooks = manifest.get("collector_hooks")
    if not isinstance(collector_hooks, list):
        collector_hooks = []
    # The collector output was inspected at run time, right after the fetch
    # hook; 'collect' cannot re-fetch it (guest /tmp does not survive a
    # power-off), so its problems are re-applied as recorded, never dropped.
    collector_record = manifest.get("collector")
    collector_problems = (
        [str(p) for p in collector_record.get("problems") or []]
        if isinstance(collector_record, dict)
        else []
    )
    missing_artifacts = missing_mandatory_artifacts(
        run_dir,
        manifest.get("condition_id"),
        runner="simulator" if timed else "external",
        allow_missing_resources=allow_missing_resources,
    )
    manifest["missing_mandatory_artifacts"] = missing_artifacts
    validity, validity_reasons = compute_validity(
        timed=timed,
        sut_env_present=sut_env_present,
        allow_missing_sut_env=allow_missing_sut_env,
        resource_source=resource_source,
        allow_missing_resources=allow_missing_resources,
        restart_required=manifest.get("condition_id") == "controller_restart",
        restart_ok=isinstance(restart_record, dict)
        and restart_record.get("returncode") == 0,
        sut_env_missing_fields=sut_env_missing_fields,
        simulator_returncode=manifest.get("simulator_returncode", 0),
        warmup_returncode=manifest.get("warmup_returncode"),
        allow_warmup_failure=allow_warmup_failure,
        skip_warmup=skip_warmup,
        condition_id=manifest.get("condition_id"),
        allow_protocol_deviation=allow_protocol_deviation,
        confirmation_marker_ok=confirmation_marker_ok,
        allow_missing_controller_marker=allow_missing_controller_marker,
        collector_hooks=collector_hooks,
        missing_artifacts=missing_artifacts,
        collector_problems=collector_problems,
    )
    manifest["validity"] = validity
    manifest["validity_reasons"] = validity_reasons

    # Overrides taking effect at collect time must leave the same recorded
    # deviation entries a 'run' would (work order P1 fix 5); deduplicated
    # by kind so repeated collect passes never stack duplicates.
    deviations = manifest.get("deviations")
    if not isinstance(deviations, list):
        deviations = []
    if (
        timed
        and allow_missing_sut_env
        and (not sut_env_present or sut_env_missing_fields)
    ):
        _append_deviation(
            deviations,
            "missing_sut_environment",
            "timed run without a usable sut_environment.json accepted"
            + (
                f" (present but missing: {', '.join(sut_env_missing_fields)})"
                if sut_env_present
                else " (file absent)"
            ),
            "--allow-missing-sut-env",
        )
    if timed and allow_missing_resources and resource_source != "sut-collector":
        _append_deviation(
            deviations,
            "missing_sut_resources",
            "timed run without SUT-collector resources accepted "
            f"(resource_source: {resource_source})",
            "--allow-missing-resources",
        )
    if timed and not confirmation_marker_ok:
        _append_deviation(
            deviations,
            "confirmation_marker_unavailable",
            "the run end was not stamped in the controller's clock domain; "
            "the analysis must fall back to the legacy event-derived "
            "confirmation deadline",
            (
                "--allow-missing-controller-marker"
                if allow_missing_controller_marker
                else None
            ),
        )
    manifest["deviations"] = deviations
    if warnings:
        manifest.setdefault("warnings", [])
        manifest["warnings"] = list(manifest["warnings"]) + warnings
    history = manifest.get("collect_history")
    if not isinstance(history, list):
        history = []
    history.append({"utc": utc_now_iso(), "actions": actions})
    manifest["collect_history"] = history

    # Sealed-dir additions (work order P1 item 11b): the only legitimate
    # change to a sealed run directory is ADDING a genuinely missing file
    # here, after the up-front checksum verification; each such addition is
    # recorded as {when_utc, added_files} and SHA256SUMS is rewritten below
    # to cover the final state.
    if sealed:
        added_files = sorted(
            p.relative_to(run_dir).as_posix()
            for p in run_dir.rglob("*")
            if p.is_file()
            and p.relative_to(run_dir).as_posix() not in pre_files
        )
        if added_files:
            collection_history = manifest.get("collection_history")
            if not isinstance(collection_history, list):
                collection_history = []
            collection_history.append(
                {"when_utc": utc_now_iso(), "added_files": added_files}
            )
            manifest["collection_history"] = collection_history

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    collected = events_dest.is_file() if timed else True
    for action in actions:
        print(f"[collect] {action}", flush=True)
    if validity == "invalid":
        for reason in validity_reasons:
            print(f"[collect] INVALID: {reason}", file=sys.stderr, flush=True)

    def _keep_existing_seal_consistent() -> None:
        """Refresh SHA256SUMS of an ALREADY sealed directory.

        This pass rewrote manifest.json, so a directory that was sealed
        BEFORE the collect attempt would otherwise fail its own checksum
        verification. It never creates a new seal for an incomplete run —
        that happens only on the success path below.
        """
        if sealed:
            write_sha256sums(run_dir)

    if not collected:
        print(
            f"[collect] run {run_id}: events.jsonl still missing; "
            "SHA256SUMS withheld",
            file=sys.stderr,
            flush=True,
        )
        _keep_existing_seal_consistent()
        return 1
    # An incomplete run directory must never look sealed (report 5.4).
    if missing_artifacts:
        print(
            f"[collect] run {run_id}: mandatory artefact(s) still missing: "
            + ", ".join(missing_artifacts)
            + "; SHA256SUMS withheld",
            file=sys.stderr,
            flush=True,
        )
        _keep_existing_seal_consistent()
        return 1

    # Collection succeeded: (re)write SHA256SUMS covering the final state.
    write_sha256sums(run_dir)
    ok = manifest.get("simulator_returncode", 0) == 0 and validity == "valid"
    update_plan_status(
        plan_path,
        run_id,
        "completed" if ok else "failed",
        result_dir=str(run_dir),
        validity=validity,
    )
    print(
        f"[collect] run {run_id} collection complete; SHA256SUMS written "
        f"(validity: {validity})",
        flush=True,
    )
    return 0 if ok else 1
