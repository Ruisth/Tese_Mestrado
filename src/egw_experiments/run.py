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

Validity (audit: warning-only is NOT acceptable): timed runs (every
simulator-driven condition) REQUIRE ``sut_environment.json`` and SUT
resources in the run directory; otherwise the manifest is marked
``validity: 'invalid'`` with explicit reasons. The only overrides are the
explicit ``--allow-missing-sut-env`` / ``--allow-missing-resources`` flags,
which record that decision in the manifest.

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
analysis script covers them (claim C15).

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
                               # validity, protocol version, exclusion
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
controller's (monotonic clocks are per-host). The manifest's
``confirmation_deadline_monotonic_ns`` is therefore informational only
(``confirmation_deadline_clock_domain: "harness-host"``); the analysis
derives the effective deadline in the controller's clock domain from the
run's own events (max ``received_monotonic_ns`` plus
``confirmation_window_s``).
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .checksums import write_sha256sums
from .controller_metrics import ControllerMetricsSampler
from .environment import (
    LOADGEN_ENVIRONMENT_FILENAME,
    SUT_ENVIRONMENT_FILENAME,
    utc_now_iso,
    write_loadgen_environment,
)
from .plan_gen import load_campaign_plan, plan_to_json
from .protocol import (
    CONFIRMATION_WINDOW_S,
    PROTOCOL_VERSION,
    TIMED_CONDITION_IDS,
)
from .resources import ResourceSampler

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

MANIFEST_VERSION = "1.1"

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
# SUT environment / resources ingestion (audit 9.1/9.2)
# ---------------------------------------------------------------------------


def ingest_sut_environment(
    run_dir: Path, sut_env_from: str | Path | None, warnings: list[str]
) -> bool:
    """Copy the operator-fetched sut_environment.json into the run dir.

    Returns True when ``sut_environment.json`` is present in the run dir
    afterwards. A source path that does not exist is a warning (the
    validity rules then apply).
    """
    dest = run_dir / SUT_ENVIRONMENT_FILENAME
    if sut_env_from is not None:
        src = Path(sut_env_from)
        if src.is_file():
            shutil.copyfile(src, dest)
        else:
            warnings.append(f"--sut-env-from file not found: {src}")
    return dest.is_file()


def ingest_resources(
    run_dir: Path, resources_from: str | Path | None, warnings: list[str]
) -> bool:
    """Copy the fetched SUT resources.csv into the run dir.

    Returns True on success. A source path that does not exist is a
    warning (the validity rules then apply).
    """
    if resources_from is None:
        return False
    src = Path(resources_from)
    if not src.is_file():
        warnings.append(f"--resources-from file not found: {src}")
        return False
    shutil.copyfile(src, run_dir / "resources.csv")
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
) -> tuple[str, list[str]]:
    """Evaluate the run-validity rules; returns (validity, reasons).

    Timed runs (every simulator-driven condition) without the SUT
    environment manifest or without SUT resources are INVALID — CPU/RAM on
    the SUT are essential for RQ3 and an environment file captured on the
    wrong host describes the wrong system (audit 9.1/9.2). The explicit
    allow flags suppress the corresponding reason but are recorded in the
    manifest as a deliberate decision.
    """
    reasons: list[str] = []
    if timed:
        if not sut_env_present and not allow_missing_sut_env:
            reasons.append(
                "sut_environment.json missing: timed runs require the SUT "
                "environment captured ON the VM "
                "(deployment/scripts/capture-sut-environment.sh, ingested "
                "via --sut-env-from); override only with "
                "--allow-missing-sut-env"
            )
        if resource_source == "none" and not allow_missing_resources:
            reasons.append(
                "no SUT resources: timed runs require the VM-side collector "
                "output (deployment/scripts/collect-resources.sh, ingested "
                "via --resources-from); CPU/RAM on the SUT are essential "
                "for RQ3; override only with --allow-missing-resources"
            )
        if restart_required and not restart_ok:
            reasons.append(
                "controller_restart condition without a successfully "
                "executed --restart-cmd: the run cannot evidence claim C12"
            )
    return ("valid" if not reasons else "invalid"), reasons


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


def load_external_timings(path: str | Path) -> dict[str, Any]:
    """Load and structurally validate an operator-produced timings.json.

    Expected shape (documented in the experiments README)::

        {"run_id": "...", "condition": "...",
         "samples": [{"label": "...", "started_utc": "...",
                      "ended_utc": "...", "duration_s": 12.3}, ...],
         "method": "...", "notes": "..."}

    Raises ValueError with a human-readable message on any problem.
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
    for i, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"timings.json sample {i} is not an object")
        duration = sample.get("duration_s")
        if not isinstance(duration, (int, float)) or duration < 0:
            raise ValueError(
                f"timings.json sample {i} needs a numeric duration_s >= 0"
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
    try:
        timings = load_external_timings(external_timings)
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
    condition_id = entry.get("condition_id")
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
        print(
            f"error: {run_dir} already exists. Raw run directories are "
            "immutable evidence (plan 5.8); to repeat a run use a new "
            "versioned run_id and document the exclusion of the old one.",
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
        "validity": "valid",
        "validity_reasons": [],
        "exclusion": None,
        "warnings": warnings,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Collection succeeded by construction (the timings file is the
    # evidence), so SHA256SUMS is written now.
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
    controller_url: str | None = None,
    restart_cmd: str | None = None,
    restart_at_s: float | None = None,
    external_timings: str | Path | None = None,
    external_logs: str | Path | None = None,
) -> int:
    """Execute one planned run end-to-end. Returns a process exit code."""
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
    if resources_from is not None and local_resources:
        print(
            "error: --resources-from and --local-resources are mutually "
            "exclusive (the manifest records exactly one resource_source).",
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
        print(
            f"error: {run_dir} already exists. Raw run directories are "
            "immutable evidence (plan 5.8); to repeat a run use a new "
            "versioned run_id and document the exclusion of the old one. "
            "To re-attempt COLLECTION for this existing run use: "
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
    # (--resources-from); the local sampler measures THIS host and is a
    # dev-only opt-in (audit 9.1).
    local_sampler = (
        ResourceSampler(run_dir / "resources.csv") if local_resources else None
    )
    metrics_sampler = (
        ControllerMetricsSampler(run_dir / "controller_metrics.csv", controller_url)
        if controller_url
        else None
    )

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
    if sim_returncode != 0:
        warnings.append(f"simulator exited with code {sim_returncode}")

    # Confirmation window (plan 7.3): confirmations arriving up to 60 s after
    # the end of the run still count; wait before collecting the event log.
    if post_run_wait_s > 0:
        print(
            f"[harness] waiting {post_run_wait_s:.0f} s confirmation window",
            flush=True,
        )
        time.sleep(post_run_wait_s)

    # Simulator outputs: sent_events.jsonl to the run root (the analysis
    # joins on it); the simulator manifest stays under logs/simulator/.
    sent_src = sim_output_dir / "sent_events.jsonl"
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

    # SUT resources ingestion (audit 9.1).
    if ingest_resources(run_dir, resources_from, warnings):
        resource_source = "sut-collector"
    elif local_resources:
        resource_source = "local-dev"
    else:
        resource_source = "none"

    restart_ok = (
        restart_record is not None and restart_record.get("returncode") == 0
    )
    validity, validity_reasons = compute_validity(
        timed=timed,
        sut_env_present=sut_env_present,
        allow_missing_sut_env=allow_missing_sut_env,
        resource_source=resource_source,
        allow_missing_resources=allow_missing_resources,
        restart_required=condition_id == "controller_restart",
        restart_ok=restart_ok,
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
        "allow_missing_sut_env": allow_missing_sut_env,
        "resource_source": resource_source,
        "allow_missing_resources": allow_missing_resources,
        "controller_metrics": (
            {
                "url": controller_url,
                "samples_written": metrics_sampler.samples_written,
                "poll_errors": metrics_sampler.poll_errors,
                "last_error": metrics_sampler.last_error,
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
                "controller_url": controller_url,
                "restart_cmd": restart_cmd,
                "restart_at_s": restart_at_s,
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
        # Informational only (CONTRACTS v1.1): captured on the harness host,
        # which runs off the ARM VM (plan 5.1), so this value is not
        # comparable with the controller's monotonic timestamps. The
        # analysis derives the effective deadline in the controller's clock
        # domain from the run's own events.
        "confirmation_deadline_monotonic_ns": finished_monotonic_ns
        + CONFIRMATION_WINDOW_S * 1_000_000_000,
        "confirmation_deadline_clock_domain": "harness-host",
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
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # SHA256SUMS is written last so it covers every file in the run dir —
    # and ONLY after successful events collection (audit 9.3): an
    # incomplete run directory must not look like sealed evidence. The
    # 'collect' subcommand re-attempts collection and writes it then.
    if events_source is not None:
        write_sha256sums(run_dir)

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
) -> int:
    """Re-attempt evidence collection for an EXISTING run directory.

    Recovery path for runs whose post-run collection failed (audit 9.3):
    instead of refusing to reuse the run_id, this re-attempts the
    events/resources/SUT-environment collection, recomputes validity,
    updates the manifest (with a ``collect_history`` audit trail) and
    (re)writes SHA256SUMS — but ONLY after successful collection. Intended
    for use BEFORE the data freeze; after ``data-v1`` raw directories are
    immutable.
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

    # Events: only re-attempted while missing (raw evidence is never
    # overwritten once present).
    events_dest = run_dir / "events.jsonl"
    if events_dest.is_file():
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

    # SUT environment: ingest when provided and still missing.
    if not (run_dir / SUT_ENVIRONMENT_FILENAME).is_file() and sut_env_from:
        if ingest_sut_environment(run_dir, sut_env_from, warnings):
            actions.append(f"ingested {SUT_ENVIRONMENT_FILENAME}")
    sut_env_present = (run_dir / SUT_ENVIRONMENT_FILENAME).is_file()
    manifest["sut_environment_present"] = sut_env_present
    refs = manifest.get("environment_refs")
    if isinstance(refs, dict):
        refs["sut"] = SUT_ENVIRONMENT_FILENAME if sut_env_present else None

    # Resources: ingest the SUT collector output when provided.
    if resources_from is not None:
        if ingest_resources(run_dir, resources_from, warnings):
            manifest["resource_source"] = "sut-collector"
            actions.append("ingested resources.csv (sut-collector)")
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
    manifest["allow_missing_sut_env"] = allow_missing_sut_env
    manifest["allow_missing_resources"] = allow_missing_resources

    timed = manifest.get("runner", "simulator") == "simulator"
    restart_record = manifest.get("restart")
    validity, validity_reasons = compute_validity(
        timed=timed,
        sut_env_present=sut_env_present,
        allow_missing_sut_env=allow_missing_sut_env,
        resource_source=resource_source,
        allow_missing_resources=allow_missing_resources,
        restart_required=manifest.get("condition_id") == "controller_restart",
        restart_ok=isinstance(restart_record, dict)
        and restart_record.get("returncode") == 0,
    )
    manifest["validity"] = validity
    manifest["validity_reasons"] = validity_reasons
    if warnings:
        manifest.setdefault("warnings", [])
        manifest["warnings"] = list(manifest["warnings"]) + warnings
    history = manifest.get("collect_history")
    if not isinstance(history, list):
        history = []
    history.append({"utc": utc_now_iso(), "actions": actions})
    manifest["collect_history"] = history

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    collected = events_dest.is_file() if timed else True
    for action in actions:
        print(f"[collect] {action}", flush=True)
    if validity == "invalid":
        for reason in validity_reasons:
            print(f"[collect] INVALID: {reason}", file=sys.stderr, flush=True)

    if not collected:
        print(
            f"[collect] run {run_id}: events.jsonl still missing; "
            "SHA256SUMS withheld",
            file=sys.stderr,
            flush=True,
        )
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
