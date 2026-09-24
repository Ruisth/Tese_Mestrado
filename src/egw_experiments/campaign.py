"""Campaign batch runner: execute the frozen plan end-to-end (work order
P1 item 12).

``python -m egw_experiments campaign`` iterates ``campaign_plan.json`` IN
ITS FROZEN ORDER (the plan's ``runs`` list; never reshuffled — the
load-sweep randomization is already baked into the plan by ``plan_gen``)
and drives every simulator-runner condition through EXACTLY the same code
path as the ``run`` subcommand (:func:`egw_experiments.run.execute_run`);
no run logic is duplicated here.

Behaviour:

- resumability: a run whose raw directory is already sealed (SHA256SUMS
  present) AND valid is skipped with a log line — re-running the campaign
  after an interruption continues where it stopped. Before skipping, the
  directory's SHA256SUMS is VERIFIED (sprint P5, report 5.4 "Integridade
  não é verificada no resume"): evidence altered after sealing must never
  be silently skipped and later analysed, so a mismatch ABORTS the
  campaign (exit 2) naming the run and the offending file;
- an existing run directory that is NOT sealed-and-valid blocks the
  campaign (outcome ``blocked``): an unsealed dir needs the ``collect``
  recovery, a sealed-but-invalid dir needs a NEW versioned run_id;
- external conditions (qemu_boots, cold_start, twin_creation) are NOT
  executed: a checklist line tells the operator what to produce (an
  operator ``timings.json`` ingested via ``run --external-timings``) and
  the campaign continues — but a FULL campaign (no ``--only-conditions``
  filter) that ends with external evidence still missing is INCOMPLETE:
  each pending run is logged with outcome ``incomplete`` and the campaign
  exits 1 with a summary (sprint P5, report 5.4 "Condições externas não
  impedem exit 0"). A filtered campaign may still exit 0 while stating
  what remains. The accounting covers the WHOLE plan, not only the
  executed slice (sprint P5.4 defect 6): ``--start-from`` moves the
  execution cursor, so the external runs it jumps over are never
  classified by the loop — they nevertheless keep owing their evidence
  until their run directory is sealed AND valid, and they are listed in
  the same summary;
- SUT collector hooks: ``--collector-start-cmd`` (before the warm-up),
  ``--collector-stop-cmd`` (after the measured run) and
  ``--collector-fetch-cmd`` (after the confirmation window) are passed
  through per run, so a fresh campaign produces its own resources.csv
  instead of requiring a pre-fetched one (sprint P5, report 5.3), and so is
  ``--expect-services`` (the services every run's collector output must
  account for, whether a hook fetched it or ``--resources-from`` names it;
  the ``{expect_services}`` placeholder of the hooks);
- ADR 0011 item 18: the SUT log fetches (``--fetch-broker-log-cmd``,
  ``--fetch-controller-log-cmd``, ``--fetch-docker-events-cmd``) and
  ``--config-identity-from`` (which, like ``--resources-from``, may carry a
  ``{run_id}`` placeholder) are passed through to every run; the
  restart-evidence steps ``--twin-snapshot-cmd``, ``--drain-cmd`` and
  ``--post-drain-fetch-cmd`` reach ONLY the ``controller_restart`` runs, as
  ``--restart-cmd`` does;
- cooldowns: the plan's ``cooldown_s`` is honored by the run wiring itself
  (``execute_run`` sleeps the remaining cooldown after the confirmation
  window). ``--no-cooldown`` suppresses it and records a protocol
  deviation on the FOLLOWING executed run (kind
  ``cooldown_skipped_before_run``): a skipped cooldown compromises the
  settling of the run that comes AFTER it;
- the first run that ends invalid or failed STOPS the campaign unless
  ``--continue-on-invalid`` records it and moves on;
- one JSONL line per visited run is appended to
  ``<results-dir>/campaign_log.jsonl``: {run_id, condition, started_utc,
  finished_utc, outcome, validity, note};
- ``--dry-run`` prints the ordered execution table (including skips)
  without executing anything and without writing the campaign log.

Exit codes: 0 = everything done and clean; 1 = stopped on (or, with
``--continue-on-invalid``, finished with) an invalid/failed/blocked run,
or a full campaign left incomplete by pending external runs; 2 = usage or
plan errors, or a sealed run directory that fails integrity verification.

A per-run resources file may be templated like the fetch command:
``--resources-from 'fetched/resources-{run_id}.csv'`` substitutes
``{run_id}`` for each run before the normal ingest validation runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .checksums import SUMS_FILENAME, verify_sha256sums
from .environment import utc_now_iso
from .plan_gen import load_campaign_plan
from .run import (
    DEFAULT_RESULTS_BASE,
    execute_run,
    format_cmd_template,
    run_dir_is_sealed,
)

CAMPAIGN_LOG_FILENAME = "campaign_log.jsonl"

#: The only condition whose runs receive the --restart-cmd/--restart-at-s
#: passthrough: firing a mid-run restart on any other condition would
#: deviate from the frozen protocol.
RESTART_CONDITION_ID = "controller_restart"


def _append_log(log_path: Path, record: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _is_sealed_and_valid(run_dir: Path) -> bool:
    """Cheap sealed-and-valid probe used for runs the campaign never visits.

    Deliberately WITHOUT the SHA256SUMS verification :func:`_classify` does:
    this decides whether an unvisited run still OWES its evidence, and a
    campaign must not silently verify (or fail on) directories outside the
    slice it was asked to execute. A visited run always goes through
    :func:`_classify` and its integrity check.
    """
    return run_dir_is_sealed(run_dir) and _read_manifest_validity(run_dir) == "valid"


def _read_manifest_validity(run_dir: Path) -> str | None:
    """The run manifest's validity value, or None when unreadable/absent."""
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        obj = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    validity = obj.get("validity") if isinstance(obj, dict) else None
    return validity if isinstance(validity, str) else None


def _external_checklist(run_id: str, condition: str) -> str:
    return (
        f"operator checklist: measure condition {condition!r} with the "
        "deployment/platform procedure (see the experiments README), "
        "produce its timings.json, then ingest with: "
        f"python -m egw_experiments run --run-id {run_id} "
        "--external-timings <timings.json> [--external-logs <dir>]"
    )


def _classify(entry: dict[str, Any], base: Path) -> tuple[str, str]:
    """Decide what the campaign does with one plan entry.

    Returns (action, note) with action one of ``skip`` (sealed, valid AND
    integrity-verified: resume), ``integrity`` (sealed and valid but the
    checksums no longer verify), ``blocked`` (directory exists but is not
    sealed-and-valid), ``external`` (operator-measured condition) or
    ``run``.
    """
    run_id = str(entry.get("run_id"))
    run_dir = base / "raw" / run_id
    sealed = run_dir_is_sealed(run_dir)
    validity = _read_manifest_validity(run_dir)
    if sealed and validity == "valid":
        # Resume integrity (sprint P5, report 5.4): presence of SHA256SUMS
        # and validity 'valid' is not enough — a directory altered after
        # sealing must never be silently skipped and then analysed.
        problems = verify_sha256sums(run_dir)
        if problems:
            return (
                "integrity",
                f"sealed run directory {run_dir} FAILS {SUMS_FILENAME} "
                "verification: " + "; ".join(problems),
            )
        return (
            "skip",
            "already sealed, valid and integrity-verified; skipped (resume)",
        )
    if run_dir.exists():
        if sealed:
            return (
                "blocked",
                f"existing run dir is sealed but validity is "
                f"{validity!r}; a repeat requires a NEW versioned run_id "
                "(document the exclusion of the old one)",
            )
        return (
            "blocked",
            "existing run dir is not sealed (incomplete collection); "
            f"recover with: python -m egw_experiments collect --run-id "
            f"{run_id}",
        )
    if entry.get("runner") != "simulator":
        return "external", _external_checklist(
            run_id, str(entry.get("condition_id"))
        )
    return "run", ""


def run_campaign(
    plan_path: str | Path,
    *,
    results_dir: str | Path | None = None,
    only_conditions: list[str] | None = None,
    start_from: str | None = None,
    dry_run: bool = False,
    continue_on_invalid: bool = False,
    no_cooldown: bool = False,
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
    fetch_events_cmd: str | None = None,
    sut_env_from: str | Path | None = None,
    resources_from: str | None = None,
    controller_url: str | None = None,
    restart_cmd: str | None = None,
    restart_at_s: float | None = None,
    collector_start_cmd: str | None = None,
    collector_stop_cmd: str | None = None,
    collector_fetch_cmd: str | None = None,
    expect_services: list[str] | None = None,
    fetch_broker_log_cmd: str | None = None,
    fetch_controller_log_cmd: str | None = None,
    fetch_docker_events_cmd: str | None = None,
    twin_snapshot_cmd: str | None = None,
    drain_cmd: str | None = None,
    post_drain_fetch_cmd: str | None = None,
    config_identity_from: str | None = None,
    allow_missing_restart_evidence: bool = False,
    allow_missing_sut_env: bool = False,
    allow_missing_resources: bool = False,
    allow_warmup_failure: bool = False,
    allow_protocol_deviation: bool = False,
    allow_missing_controller_marker: bool = False,
) -> int:
    """Execute the frozen campaign plan in order. Returns an exit code."""
    plan_path = Path(plan_path)
    try:
        plan = load_campaign_plan(plan_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"error: cannot read campaign plan {plan_path}: {exc}",
            file=sys.stderr,
        )
        return 2
    entries = plan.get("runs")
    if not isinstance(entries, list) or not entries:
        print(
            f"error: campaign plan {plan_path} has no runs", file=sys.stderr
        )
        return 2

    base = Path(results_dir) if results_dir is not None else DEFAULT_RESULTS_BASE

    # Selection NEVER reorders: the plan's list order is the frozen
    # execution order (plan 7.1; the load-sweep shuffle is already baked
    # into the plan).
    selected = list(entries)
    if start_from is not None:
        ids = [str(e.get("run_id")) for e in selected]
        if start_from not in ids:
            print(
                f"error: --start-from run_id {start_from!r} is not in the "
                f"plan {plan_path}",
                file=sys.stderr,
            )
            return 2
        selected = selected[ids.index(start_from):]
    if only_conditions:
        known = {str(e.get("condition_id")) for e in entries}
        unknown = sorted(set(only_conditions) - known)
        if unknown:
            print(
                "error: --only-conditions names unknown condition(s): "
                + ", ".join(unknown)
                + "; plan conditions: "
                + ", ".join(sorted(known)),
                file=sys.stderr,
            )
            return 2
        keep = set(only_conditions)
        selected = [e for e in selected if e.get("condition_id") in keep]
    if not selected:
        print("[campaign] nothing to do after --start-from/--only-conditions")
        return 0

    if dry_run:
        print(
            f"[campaign] DRY-RUN: {len(selected)} of {len(entries)} planned "
            f"runs selected from {plan_path} (frozen plan order; nothing is "
            "executed)"
        )
        for i, entry in enumerate(selected, start=1):
            action, note = _classify(entry, base)
            cooldown_s = int(entry.get("cooldown_s") or 0)
            cooldown = (
                f" cooldown={cooldown_s}s"
                + (" (SKIPPED: --no-cooldown)" if no_cooldown else "")
                if cooldown_s > 0 and action == "run"
                else ""
            )
            print(
                f"[campaign] {i:>3} {action.upper():<8} "
                f"{entry.get('run_id')}  condition={entry.get('condition_id')}"
                f"{cooldown}"
                + (f"  {note}" if note else "")
            )
        return 0

    # External evidence owed by runs OUTSIDE the selected slice (sprint P5.4
    # defect 6). --start-from only moves the execution cursor: an external
    # run earlier in the frozen order is never classified by the loop below,
    # so counting only the selected slice let a campaign that never produced
    # a single QEMU boot / cold start / twin creation exit 0 as 'clean'.
    # Owed evidence is a property of the WHOLE plan, so it is accounted for
    # here; runs already sealed-and-valid owe nothing.
    selected_ids = {str(entry.get("run_id")) for entry in selected}
    skipped_external: list[str] = [
        str(entry.get("run_id"))
        for entry in entries
        if str(entry.get("run_id")) not in selected_ids
        and entry.get("runner") != "simulator"
        and not _is_sealed_and_valid(base / "raw" / str(entry.get("run_id")))
    ]

    log_path = base / CAMPAIGN_LOG_FILENAME
    any_bad = False
    # External conditions still missing their operator evidence. A FULL
    # campaign that ends with any of these is INCOMPLETE, never clean
    # (sprint P5, report 5.4).
    pending_external: list[str] = []
    # Deviation owed to the NEXT executed run after a --no-cooldown skip
    # (the cooldown protects the run that FOLLOWS it).
    pending_deviation: list[dict[str, Any]] | None = None

    for entry in selected:
        run_id = str(entry.get("run_id"))
        condition = str(entry.get("condition_id"))
        run_dir = base / "raw" / run_id
        action, note = _classify(entry, base)

        if action == "skip":
            print(f"[campaign] skip {run_id}: {note}", flush=True)
            now = utc_now_iso()
            _append_log(
                log_path,
                {
                    "run_id": run_id,
                    "condition": condition,
                    "started_utc": now,
                    "finished_utc": now,
                    "outcome": "skipped",
                    "validity": _read_manifest_validity(run_dir),
                    "note": note,
                },
            )
            continue

        if action == "integrity":
            print(
                f"[campaign] INTEGRITY FAILURE {run_id}: {note}",
                file=sys.stderr,
                flush=True,
            )
            now = utc_now_iso()
            _append_log(
                log_path,
                {
                    "run_id": run_id,
                    "condition": condition,
                    "started_utc": now,
                    "finished_utc": now,
                    "outcome": "integrity-failed",
                    "validity": _read_manifest_validity(run_dir),
                    "note": note,
                },
            )
            print(
                f"[campaign] aborting at {run_id}: sealed raw evidence was "
                "altered after sealing. The campaign never silently skips "
                "or re-runs a tampered run directory; investigate it, "
                "document the exclusion and repeat the run under a NEW "
                "versioned run_id.",
                file=sys.stderr,
            )
            return 2

        if action == "external":
            # Not executed here; still PENDING until its timings.json is
            # ingested (then the directory is sealed and it is 'skipped').
            pending_external.append(run_id)
            print(
                f"[campaign] INCOMPLETE {run_id}: external condition not "
                f"executed - {note}",
                flush=True,
            )
            now = utc_now_iso()
            _append_log(
                log_path,
                {
                    "run_id": run_id,
                    "condition": condition,
                    "started_utc": now,
                    "finished_utc": now,
                    "outcome": "incomplete",
                    "validity": None,
                    "note": note,
                },
            )
            continue

        if action == "blocked":
            print(f"[campaign] BLOCKED {run_id}: {note}", file=sys.stderr, flush=True)
            now = utc_now_iso()
            _append_log(
                log_path,
                {
                    "run_id": run_id,
                    "condition": condition,
                    "started_utc": now,
                    "finished_utc": now,
                    "outcome": "blocked",
                    "validity": _read_manifest_validity(run_dir),
                    "note": note,
                },
            )
            any_bad = True
            if not continue_on_invalid:
                print(
                    f"[campaign] stopping at {run_id} (blocked); fix the "
                    "run directory ('collect' when it is unsealed, a NEW "
                    "versioned run_id when it is sealed-but-invalid), or "
                    "record it and carry on with --continue-on-invalid. "
                    "--start-from moves the execution cursor past a run, it "
                    "does NOT settle it: the runs it jumps over still owe "
                    "their evidence, and any external run left behind keeps "
                    "the campaign INCOMPLETE (exit 1).",
                    file=sys.stderr,
                )
                return 1
            continue

        # action == "run": same code path as the 'run' subcommand.
        started_utc = utc_now_iso()
        rc = execute_run(
            plan_path,
            run_id,
            base_dir=base,
            broker=broker,
            port=port,
            username=username,
            password=password,
            ca_cert=ca_cert,
            no_tls=no_tls,
            qos=qos,
            egw_id=egw_id,
            event_log_dir=event_log_dir,
            post_run_wait_s=post_run_wait_s,
            skip_cooldown=no_cooldown,
            fetch_events_cmd=fetch_events_cmd,
            sut_env_from=sut_env_from,
            resources_from=(
                format_cmd_template(resources_from, run_id)
                if resources_from
                else None
            ),
            collector_start_cmd=collector_start_cmd,
            collector_stop_cmd=collector_stop_cmd,
            collector_fetch_cmd=collector_fetch_cmd,
            expect_services=expect_services,
            allow_missing_sut_env=allow_missing_sut_env,
            allow_missing_restart_evidence=allow_missing_restart_evidence,
            allow_missing_resources=allow_missing_resources,
            allow_warmup_failure=allow_warmup_failure,
            allow_protocol_deviation=allow_protocol_deviation,
            allow_missing_controller_marker=allow_missing_controller_marker,
            controller_url=controller_url,
            restart_cmd=(
                restart_cmd if condition == RESTART_CONDITION_ID else None
            ),
            restart_at_s=(
                restart_at_s if condition == RESTART_CONDITION_ID else None
            ),
            # ADR 0011 item 18: the log fetches and the configuration
            # identity reach every run; the restart evidence steps only the
            # controller_restart runs, like the restart hook.
            fetch_broker_log_cmd=fetch_broker_log_cmd,
            fetch_controller_log_cmd=fetch_controller_log_cmd,
            fetch_docker_events_cmd=fetch_docker_events_cmd,
            config_identity_from=(
                format_cmd_template(config_identity_from, run_id)
                if config_identity_from
                else None
            ),
            twin_snapshot_cmd=(
                twin_snapshot_cmd if condition == RESTART_CONDITION_ID else None
            ),
            drain_cmd=drain_cmd if condition == RESTART_CONDITION_ID else None,
            post_drain_fetch_cmd=(
                post_drain_fetch_cmd
                if condition == RESTART_CONDITION_ID
                else None
            ),
            extra_deviations=pending_deviation,
        )
        finished_utc = utc_now_iso()
        pending_deviation = None
        validity = _read_manifest_validity(run_dir)
        if rc == 0:
            outcome = "completed"
            run_note = ""
        elif rc == 1:
            outcome = "invalid" if validity == "invalid" else "failed"
            run_note = (
                "run ended invalid (see manifest validity_reasons)"
                if outcome == "invalid"
                else "run failed (simulator exit or evidence collection)"
            )
        else:
            outcome = "error"
            run_note = f"run subcommand exited {rc} (usage/plan error)"
        _append_log(
            log_path,
            {
                "run_id": run_id,
                "condition": condition,
                "started_utc": started_utc,
                "finished_utc": finished_utc,
                "outcome": outcome,
                "validity": validity,
                "note": run_note,
            },
        )
        # A skipped cooldown deviates the protocol of the FOLLOWING
        # executed run; owe it a manifest deviation entry.
        cooldown_s = int(entry.get("cooldown_s") or 0)
        if no_cooldown and cooldown_s > 0:
            pending_deviation = [
                {
                    "kind": "cooldown_skipped_before_run",
                    "detail": (
                        f"the planned {cooldown_s} s cooldown after run "
                        f"{run_id} was skipped via campaign --no-cooldown; "
                        "this run started without the frozen protocol's "
                        "settling period (plan 7.1)"
                    ),
                    "authorized_by_flag": "--no-cooldown",
                }
            ]
        if rc == 2:
            print(
                f"[campaign] stopping at {run_id}: {run_note}",
                file=sys.stderr,
            )
            return 2
        if rc != 0:
            any_bad = True
            if not continue_on_invalid:
                print(
                    f"[campaign] stopping at {run_id} (outcome {outcome}); "
                    "resume later with --start-from, or record-and-continue "
                    "with --continue-on-invalid",
                    file=sys.stderr,
                )
                return 1

    # Pending external evidence (sprint P5, report 5.4; whole-plan accounting
    # since P5.4 defect 6). A FULL campaign cannot be "clean" while QEMU
    # boots, cold starts or twin creations are still unmeasured — including
    # the ones --start-from jumped over, which are owed exactly as much as the
    # ones the loop visited. A FILTERED campaign (--only-conditions)
    # legitimately covers a subset and only states what remains.
    owed = set(pending_external) | set(skipped_external)
    owed_external = [
        str(entry.get("run_id"))
        for entry in entries
        if str(entry.get("run_id")) in owed
    ]
    incomplete = bool(owed_external) and not only_conditions
    if owed_external:
        print(
            f"[campaign] {len(owed_external)} external run(s) still "
            "pending (evidence not ingested): "
            + ", ".join(owed_external),
            file=sys.stderr if incomplete else None,
            flush=True,
        )
        if skipped_external:
            print(
                f"[campaign] {len(skipped_external)} of them "
                f"({', '.join(skipped_external)}) were NOT visited in this "
                "pass because --start-from/--only-conditions skipped them; "
                "skipping a run does not discharge the evidence it owes",
                file=sys.stderr if incomplete else None,
                flush=True,
            )
        print(
            "[campaign] produce each timings.json with the deployment/"
            "platform procedure and ingest it with: python -m "
            "egw_experiments run --run-id <run_id> --external-timings "
            "<timings.json>",
            file=sys.stderr if incomplete else None,
            flush=True,
        )
    status = "clean"
    if any_bad:
        status = "finished WITH invalid/failed runs"
    if incomplete:
        status = (
            "INCOMPLETE"
            if not any_bad
            else "INCOMPLETE and finished WITH invalid/failed runs"
        )
    print(f"[campaign] done: {status}; log: {log_path}", flush=True)
    return 1 if (any_bad or incomplete) else 0
