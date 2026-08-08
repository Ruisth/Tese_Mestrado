"""Execute one planned run from the harness host, OFF the ARM VM
(plan 5.1/5.8, CONTRACTS 5/7).

Plan 5.1 requires the simulator to run off the ARM VM during benchmarks, so
this harness (which drives the simulator as a subprocess) runs off the VM
too: ``--broker`` is the VM's address and the connection uses port 8883
with TLS (CONTRACTS 1). The controller writes its per-run ``events.jsonl``
ON the VM (under its ``EGW_EVENT_LOG_DIR``); after each run that file must
be fetched into the local event-log directory before events collection,
e.g.::

    scp vm:/path/to/data/events/<run_id>/events.jsonl <local EGW_EVENT_LOG_DIR>/<run_id>/events.jsonl

Produces exactly the plan 5.8 raw structure::

    results/raw/<run_id>/
      events.jsonl      # controller log collected from EGW_EVENT_LOG_DIR
      resources.csv     # 1 Hz docker stats samples
      manifest.json     # scenario, seed, commit, image digests, env ref,
                        # config echo, timestamps, protocol version, exclusion
      logs/             # simulator stdout/stderr, warmup artifacts,
                        # simulator manifest + raw output
      SHA256SUMS        # written last, covers every file above
      + sent_events.jsonl and environment.json (documented extras needed by
        the analysis; plan 5.8 lists the minimum contents)

Flow: refuse to reuse an existing run dir (raw is immutable evidence),
capture environment, start resource sampling, optionally run a warm-up
simulator invocation (separate ``<run_id>.warmup`` run id so its messages
never mix with the measured run), run the measured simulator invocation per
CONTRACTS 7, wait the 60 s confirmation window (plan 7.3), collect the
controller's events.jsonl and the simulator's sent_events.jsonl, write the
manifest and finally SHA256SUMS.

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
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .checksums import write_sha256sums
from .environment import utc_now_iso, write_environment
from .plan_gen import load_campaign_plan, plan_to_json
from .protocol import CONFIRMATION_WINDOW_S, PROTOCOL_VERSION
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
    if entry.get("runner") != "simulator":
        print(
            f"error: run {run_id!r} belongs to condition "
            f"{entry.get('condition_id')!r}, which is not driven by the "
            "simulator (cold starts, twin creations and QEMU boots are "
            "measured by the deployment/platform procedures; attach their "
            "evidence to results/raw/<run_id>/ manually and update the plan "
            "status).",
            file=sys.stderr,
        )
        return 2

    egw_id = egw_id or os.environ.get("EGW_ID", "egw-01")
    event_log_dir = Path(
        event_log_dir
        if event_log_dir is not None
        else os.environ.get("EGW_EVENT_LOG_DIR", "./data/events")
    )
    if post_run_wait_s is None:
        post_run_wait_s = float(CONFIRMATION_WINDOW_S)

    base = Path(base_dir) if base_dir is not None else DEFAULT_RESULTS_BASE
    run_dir = base / "raw" / run_id
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

    print(f"[harness] run {run_id}: created {run_dir}", flush=True)
    update_plan_status(plan_path, run_id, "running")

    write_environment(run_dir / "environment.json")
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

    started_utc = utc_now_iso()
    sim_output_dir = logs_dir / "simulator"
    sim_returncode: int | None = None
    warmup_returncode: int | None = None

    sampler = ResourceSampler(run_dir / "resources.csv")
    with sampler:
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
        finished_monotonic_ns = time.monotonic_ns()
        finished_utc = utc_now_iso()

    if sampler.error:
        warnings.append(f"resource sampling degraded: {sampler.error}")
        print(f"[harness] warning: {sampler.error}", flush=True)
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

    events_source = collect_controller_events(
        event_log_dir, run_id, run_dir / "events.jsonl"
    )
    if events_source is None:
        expected_local = event_log_dir / run_id / "events.jsonl"
        missing_events_msg = (
            f"controller events.jsonl for run_id {run_id!r} not found under "
            f"{event_log_dir} (expected e.g. {expected_local}). The "
            "controller writes events.jsonl ON the ARM VM (under its "
            "EGW_EVENT_LOG_DIR) while this harness runs OFF the VM (plan "
            "5.1); fetch the file from the VM into the local event-log "
            "directory before events collection, e.g.: "
            f"scp vm:/path/to/data/events/{run_id}/events.jsonl "
            f"{expected_local}"
        )
        warnings.append(missing_events_msg)
        print(f"[harness] error: {missing_events_msg}", file=sys.stderr, flush=True)

    ok = sim_returncode == 0 and events_source is not None

    manifest: dict[str, Any] = {
        "manifest_version": "1.0",
        "protocol_version": PROTOCOL_VERSION,
        "plan_master_seed": plan.get("master_seed"),
        "run_id": run_id,
        "condition_id": entry.get("condition_id"),
        "scenario": scenario,
        "repetition": entry.get("repetition"),
        "seed": seed,
        "rate_msg_s": rate_msg_s,
        "duration_s": duration_s,
        "warmup_s": 0 if skip_warmup else warmup_s,
        "cooldown_s": cooldown_s,
        "commit": commit,
        "image_digests": image_digests,
        "environment_ref": "environment.json",
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
            },
        },
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "finished_monotonic_ns": finished_monotonic_ns,
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
        "resource_samples_written": sampler.samples_written,
        "resource_sampling_error": sampler.error,
        # Exclusion criteria (plan 5.8/7.3): filled in manually, with a
        # documented cause, only for proven cloud/instrumentation/config
        # failures. A slow run is never excluded for its result alone.
        "exclusion": None,
        "warnings": warnings,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # SHA256SUMS is written last so it covers every file in the run dir.
    write_sha256sums(run_dir)

    update_plan_status(
        plan_path,
        run_id,
        "completed" if ok else "failed",
        result_dir=str(run_dir),
        finished_utc=finished_utc,
    )

    # Cooldown between load-sweep runs (plan 7.1). Part of it was already
    # spent waiting for the confirmation window.
    remaining_cooldown = max(0.0, cooldown_s - post_run_wait_s)
    if remaining_cooldown > 0 and not skip_cooldown:
        print(f"[harness] cooldown: {remaining_cooldown:.0f} s", flush=True)
        time.sleep(remaining_cooldown)

    print(f"[harness] run {run_id} {'completed' if ok else 'FAILED'}", flush=True)
    return 0 if ok else 1
