"""Command-line interface of the experiment harness.

Subcommands (plan 5.8/9.1 'Reprodutibilidade'; audit 2026-08-08 section 9)::

    python -m egw_experiments plan --master-seed 42 [--output PATH] [--force]
    python -m egw_experiments campaign [--plan PATH] [--results-dir DIR] ...
    python -m egw_experiments run --run-id nominal-r01 [--plan PATH] ...
    python -m egw_experiments collect --run-id nominal-r01 [...]
    python -m egw_experiments analyze [--base-dir PATH]
    python -m egw_experiments verify-checksums [--base-dir PATH] [--run-id ID]

``plan`` writes the fully enumerated deterministic campaign plan;
``campaign`` (work order P1 item 12) is the OFFICIAL way to execute the
frozen plan end-to-end: it iterates the plan in its frozen order, runs
every simulator condition through the same code path as ``run``, skips
runs already sealed and valid (resume), prints an operator checklist for
external conditions and appends one JSONL line per run to
``<results-dir>/campaign_log.jsonl``. ``run``
executes exactly one planned run from the harness host, OFF the ARM VM
(plan 5.1: the simulator never runs on the VM during benchmarks;
``--broker`` is the VM's address, port 8883 with TLS). After the 60 s
confirmation window the runner collects the controller's ``events.jsonl``
AUTOMATICALLY via ``--fetch-events-cmd`` (or env ``EGW_FETCH_EVENTS_CMD``),
a command template with ``{run_id}`` and ``{dest}`` placeholders, retried
3 times with backoff; without a template it falls back to the local
event-log directory (dev only). External conditions (QEMU boots, cold
starts, twin creations) are ingested with ``--external-timings``.
``collect`` is the recovery path: it re-attempts events/resources/SUT
environment collection for an EXISTING run directory and (re)writes
SHA256SUMS only after successful collection. ``analyze`` regenerates
everything under ``results/processed`` and ``results/figures`` from
``results/raw``; ``verify-checksums`` re-verifies the SHA256SUMS of raw
run directories (evidence integrity, plan 5.8).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyze import analyze
from .campaign import run_campaign
from .checksums import verify_sha256sums
from .plan_gen import generate_campaign_plan, write_campaign_plan
from .run import (
    DEFAULT_PLAN_PATH,
    DEFAULT_RESULTS_BASE,
    FETCH_EVENTS_CMD_ENV,
    SUT_ENV_FILE_ENV,
    collect_run,
    execute_run,
)


def _add_collection_arguments(
    parser: argparse.ArgumentParser, *, resources_template: bool = False
) -> None:
    """Arguments shared by ``run``, ``collect`` and ``campaign``
    (audit 9.1-9.3). With ``resources_template`` (campaign) the
    ``--resources-from`` value may contain a ``{run_id}`` placeholder
    substituted per run."""
    parser.add_argument(
        "--fetch-events-cmd",
        default=None,
        help="command template that fetches the controller's events.jsonl "
        "from the VM; {run_id} and {dest} are substituted, e.g. "
        "'scp vm:/opt/egw/data/events/{run_id}/events.jsonl {dest}'. "
        "Executed after the confirmation window with 3 attempts and "
        f"exponential backoff (default: env {FETCH_EVENTS_CMD_ENV}). "
        "Without it the runner falls back to the local --event-log-dir "
        "lookup (dev only)",
    )
    parser.add_argument(
        "--event-log-dir",
        default=None,
        help="local fallback directory holding the controller's "
        "events.jsonl when no --fetch-events-cmd is configured "
        "(default: EGW_EVENT_LOG_DIR env or ./data/events)",
    )
    parser.add_argument(
        "--sut-env-from",
        default=None,
        help="path of the sut_environment.json captured ON the ARM VM by "
        "deployment/scripts/capture-sut-environment.sh and fetched here "
        f"(default: env {SUT_ENV_FILE_ENV}). Timed runs without it are "
        "marked validity 'invalid'",
    )
    parser.add_argument(
        "--resources-from",
        default=None,
        help="path of the resources.csv produced ON the ARM VM by "
        "deployment/scripts/collect-resources.sh and fetched here. The "
        "file is content-validated before ingestion (exact "
        "ts_utc,container,cpu_pct,mem_bytes,mem_pct,host header; at least "
        "30 sample rows; every host value matching the sut_environment "
        "node/hostname); a rejected file is treated as missing. Timed runs "
        "without SUT resources are marked validity 'invalid'"
        + (
            ". May contain a {run_id} placeholder substituted per run, "
            "e.g. 'fetched/resources-{run_id}.csv'"
            if resources_template
            else ""
        ),
    )
    parser.add_argument(
        "--allow-missing-sut-env",
        action="store_true",
        help="deliberately accept a timed run without sut_environment.json; "
        "the decision is recorded in the manifest (audit 9.2)",
    )
    parser.add_argument(
        "--allow-missing-resources",
        action="store_true",
        help="deliberately accept a timed run without SUT resources; the "
        "decision is recorded in the manifest (audit 9.1)",
    )


def _add_run_level_arguments(parser: argparse.ArgumentParser) -> None:
    """Run-level flags shared by ``run`` and ``campaign`` (same wiring)."""
    parser.add_argument(
        "--broker",
        default="localhost",
        help="MQTT broker host: the ARM VM's address (the harness and the "
        "simulator run off the VM during benchmarks, plan 5.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8883, help="MQTT port (default 8883, TLS)"
    )
    parser.add_argument("--username", default=None, help="MQTT username")
    parser.add_argument("--password", default=None, help="MQTT password")
    parser.add_argument("--ca-cert", default=None, help="CA certificate path (TLS)")
    parser.add_argument(
        "--no-tls",
        action="store_true",
        help="disable TLS; allowed only against localhost and never in "
        "benchmarks (CONTRACTS 1)",
    )
    parser.add_argument("--qos", type=int, default=1, help="MQTT QoS (default 1)")
    parser.add_argument(
        "--egw-id", default=None, help="gateway id (default: EGW_ID env or egw-01)"
    )
    parser.add_argument(
        "--post-run-wait",
        type=float,
        default=None,
        help="seconds to wait after the run for late confirmations "
        "(default: the 60 s confirmation window of plan 7.3)",
    )
    parser.add_argument(
        "--allow-warmup-failure",
        action="store_true",
        help="keep a timed run valid when the warm-up subprocess exits "
        "non-zero; the decision is recorded as a protocol deviation in the "
        "manifest (without this flag the run is marked validity 'invalid')",
    )
    parser.add_argument(
        "--allow-protocol-deviation",
        action="store_true",
        help="authorize an explicit protocol deviation (currently: "
        "--skip-warmup on nominal/load_sweep/soak); the deviation is "
        "recorded in the manifest (without this flag such a run is marked "
        "validity 'invalid')",
    )
    parser.add_argument(
        "--controller-url",
        default=None,
        help="controller base URL for 1 Hz GET /metrics sampling into "
        "controller_metrics.csv (queue growth, audit 9.7). Port 8000 is "
        "loopback-only on the VM: open an SSH tunnel first, e.g. "
        "'ssh -N -L 8000:127.0.0.1:8000 <vm>' then use "
        "http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--restart-cmd",
        default=None,
        help="command template ({run_id} placeholder) executed exactly once "
        "mid-run for the controller_restart condition (claim C12), e.g. "
        "'ssh vm docker compose -f /opt/egw/compose.yaml restart "
        "controller'; recorded in the manifest with timestamps. The "
        "campaign subcommand applies it ONLY to controller_restart runs",
    )
    parser.add_argument(
        "--restart-at-s",
        type=float,
        default=None,
        help="offset in seconds into the measured run at which "
        "--restart-cmd fires (default: half the run duration)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="egw_experiments",
        description="EGW experiment harness: plan, run, collect, analyze, verify.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # plan ------------------------------------------------------------------
    p_plan = sub.add_parser(
        "plan", help="generate the deterministic campaign_plan.json"
    )
    p_plan.add_argument(
        "--master-seed",
        type=int,
        required=True,
        help="campaign master seed; the same seed always yields the same plan",
    )
    p_plan.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"output path (default: {DEFAULT_PLAN_PATH})",
    )
    p_plan.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing plan (statuses in it are lost)",
    )

    # run -------------------------------------------------------------------
    p_run = sub.add_parser(
        "run",
        help="execute one planned run from the harness host, OFF the ARM VM "
        "(plan 5.1): --broker is the VM's address (port 8883, TLS). Events "
        "are collected automatically via --fetch-events-cmd; SUT "
        "environment and resources are ingested via --sut-env-from / "
        "--resources-from; external conditions via --external-timings",
    )
    p_run.add_argument("--run-id", required=True, help="run_id from the plan")
    p_run.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"campaign plan path (default: {DEFAULT_PLAN_PATH})",
    )
    p_run.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE})",
    )
    _add_run_level_arguments(p_run)
    p_run.add_argument(
        "--skip-warmup",
        action="store_true",
        help="skip the planned warm-up. Recorded as a protocol deviation; "
        "on nominal/load_sweep/soak the run is marked validity 'invalid' "
        "unless --allow-protocol-deviation is also given",
    )
    p_run.add_argument(
        "--skip-cooldown",
        action="store_true",
        help="skip the planned cooldown (recorded as a protocol deviation "
        "when the condition prescribes one)",
    )
    _add_collection_arguments(p_run)
    p_run.add_argument(
        "--local-resources",
        action="store_true",
        help="DEV ONLY: sample docker stats on THIS host (the load "
        "generator, NOT the SUT) into resources.csv; mutually exclusive "
        "with --resources-from; recorded as resource_source 'local-dev'",
    )
    p_run.add_argument(
        "--external-timings",
        default=None,
        help="operator-produced timings.json for external conditions "
        "(qemu_boots, cold_start, twin_creation): {run_id, condition, "
        "samples:[{label, started_utc, ended_utc, duration_s}], method, "
        "notes}; see deployment/scripts/measure-cold-start.sh",
    )
    p_run.add_argument(
        "--external-logs",
        default=None,
        help="optional directory of operator logs copied into the external "
        "run's logs/ directory",
    )

    # campaign (batch runner, work order P1 item 12) --------------------------
    p_camp = sub.add_parser(
        "campaign",
        help="execute the frozen campaign plan end-to-end IN PLAN ORDER: "
        "the OFFICIAL way to run the campaign. Simulator conditions run "
        "through the same code path as 'run'; sealed+valid runs are "
        "skipped (resume); external conditions print an operator "
        "checklist; one JSONL line per run is appended to "
        "<results-dir>/campaign_log.jsonl",
    )
    p_camp.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"campaign plan path (default: {DEFAULT_PLAN_PATH})",
    )
    p_camp.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE}); "
        "runs land in <results-dir>/raw/<run_id>/ and the batch log in "
        "<results-dir>/campaign_log.jsonl",
    )
    p_camp.add_argument(
        "--only-conditions",
        default=None,
        help="comma-separated condition ids to execute (e.g. "
        "'smoke_sequence,nominal'); the frozen plan order among them is "
        "preserved",
    )
    p_camp.add_argument(
        "--start-from",
        default=None,
        help="skip every run BEFORE this run_id in the plan order (resume "
        "an interrupted campaign; sealed+valid runs are skipped anyway)",
    )
    p_camp.add_argument(
        "--dry-run",
        action="store_true",
        help="print the ordered execution table (including skips and "
        "external checklists) without executing anything",
    )
    p_camp.add_argument(
        "--continue-on-invalid",
        action="store_true",
        help="record an invalid/failed/blocked run in campaign_log.jsonl "
        "and move on instead of stopping at it (the exit code still "
        "reports the failure)",
    )
    p_camp.add_argument(
        "--no-cooldown",
        action="store_true",
        help="skip the plan's cooldown_s between runs; recorded as a "
        "protocol deviation (kind cooldown_skipped_before_run) in the "
        "manifest of the FOLLOWING executed run",
    )
    _add_run_level_arguments(p_camp)
    _add_collection_arguments(p_camp, resources_template=True)

    # collect (recovery, audit 9.3) ------------------------------------------
    p_col = sub.add_parser(
        "collect",
        help="re-attempt events/resources/SUT-environment collection for an "
        "EXISTING run directory and (re)write SHA256SUMS after successful "
        "collection (recovery path; raw evidence is never overwritten)",
    )
    p_col.add_argument("--run-id", required=True, help="existing raw run_id")
    p_col.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"campaign plan path (default: {DEFAULT_PLAN_PATH})",
    )
    p_col.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE})",
    )
    _add_collection_arguments(p_col)

    # analyze ---------------------------------------------------------------
    p_an = sub.add_parser(
        "analyze",
        help="regenerate processed/ and figures/ from raw/ (single script)",
    )
    p_an.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE})",
    )

    # verify-checksums ------------------------------------------------------
    p_ver = sub.add_parser(
        "verify-checksums", help="verify SHA256SUMS of raw run directories"
    )
    p_ver.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE})",
    )
    p_ver.add_argument(
        "--run-id", default=None, help="verify only this run directory"
    )

    return parser


def _cmd_plan(args: argparse.Namespace) -> int:
    output: Path = args.output
    if output.exists() and not args.force:
        print(
            f"error: {output} already exists; it contains run statuses. "
            "Use --force to overwrite deliberately.",
            file=sys.stderr,
        )
        return 2
    plan = generate_campaign_plan(args.master_seed)
    write_campaign_plan(plan, output)
    print(
        f"wrote {output} (protocol {plan['protocol_version']}, "
        f"master seed {plan['master_seed']}, {len(plan['runs'])} runs)"
    )
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    return execute_run(
        args.plan,
        args.run_id,
        base_dir=args.base_dir,
        broker=args.broker,
        port=args.port,
        username=args.username,
        password=args.password,
        ca_cert=args.ca_cert,
        no_tls=args.no_tls,
        qos=args.qos,
        egw_id=args.egw_id,
        event_log_dir=args.event_log_dir,
        post_run_wait_s=args.post_run_wait,
        skip_warmup=args.skip_warmup,
        skip_cooldown=args.skip_cooldown,
        fetch_events_cmd=args.fetch_events_cmd,
        sut_env_from=args.sut_env_from,
        resources_from=args.resources_from,
        local_resources=args.local_resources,
        allow_missing_sut_env=args.allow_missing_sut_env,
        allow_missing_resources=args.allow_missing_resources,
        allow_warmup_failure=args.allow_warmup_failure,
        allow_protocol_deviation=args.allow_protocol_deviation,
        controller_url=args.controller_url,
        restart_cmd=args.restart_cmd,
        restart_at_s=args.restart_at_s,
        external_timings=args.external_timings,
        external_logs=args.external_logs,
    )


def _cmd_campaign(args: argparse.Namespace) -> int:
    only_conditions = None
    if args.only_conditions:
        only_conditions = [
            c.strip() for c in args.only_conditions.split(",") if c.strip()
        ]
        if not only_conditions:
            print(
                "error: --only-conditions given but names no condition",
                file=sys.stderr,
            )
            return 2
    return run_campaign(
        args.plan,
        results_dir=args.results_dir,
        only_conditions=only_conditions,
        start_from=args.start_from,
        dry_run=args.dry_run,
        continue_on_invalid=args.continue_on_invalid,
        no_cooldown=args.no_cooldown,
        broker=args.broker,
        port=args.port,
        username=args.username,
        password=args.password,
        ca_cert=args.ca_cert,
        no_tls=args.no_tls,
        qos=args.qos,
        egw_id=args.egw_id,
        event_log_dir=args.event_log_dir,
        post_run_wait_s=args.post_run_wait,
        fetch_events_cmd=args.fetch_events_cmd,
        sut_env_from=args.sut_env_from,
        resources_from=args.resources_from,
        controller_url=args.controller_url,
        restart_cmd=args.restart_cmd,
        restart_at_s=args.restart_at_s,
        allow_missing_sut_env=args.allow_missing_sut_env,
        allow_missing_resources=args.allow_missing_resources,
        allow_warmup_failure=args.allow_warmup_failure,
        allow_protocol_deviation=args.allow_protocol_deviation,
    )


def _cmd_collect(args: argparse.Namespace) -> int:
    return collect_run(
        args.run_id,
        base_dir=args.base_dir,
        plan_path=args.plan,
        fetch_events_cmd=args.fetch_events_cmd,
        event_log_dir=args.event_log_dir,
        sut_env_from=args.sut_env_from,
        resources_from=args.resources_from,
        allow_missing_sut_env=args.allow_missing_sut_env,
        allow_missing_resources=args.allow_missing_resources,
    )


def _cmd_verify(args: argparse.Namespace) -> int:
    base = args.base_dir if args.base_dir is not None else DEFAULT_RESULTS_BASE
    raw_dir = Path(base) / "raw"
    if not raw_dir.is_dir():
        print(f"error: {raw_dir} does not exist", file=sys.stderr)
        return 2

    if args.run_id is not None:
        run_dirs = [raw_dir / args.run_id]
        if not run_dirs[0].is_dir():
            print(f"error: {run_dirs[0]} does not exist", file=sys.stderr)
            return 2
    else:
        run_dirs = sorted(p for p in raw_dir.iterdir() if p.is_dir())

    if not run_dirs:
        print(f"no run directories under {raw_dir}")
        return 0

    failures = 0
    for run_dir in run_dirs:
        problems = verify_sha256sums(run_dir)
        if problems:
            failures += 1
            print(f"FAIL {run_dir.name}")
            for problem in problems:
                print(f"  {problem}")
        else:
            print(f"OK   {run_dir.name}")

    if failures:
        print(f"{failures} of {len(run_dirs)} run directories failed verification")
        return 1
    print(f"all {len(run_dirs)} run directories verified")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        return _cmd_plan(args)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "campaign":
        return _cmd_campaign(args)
    if args.command == "collect":
        return _cmd_collect(args)
    if args.command == "analyze":
        return analyze(base_dir=args.base_dir)
    if args.command == "verify-checksums":
        return _cmd_verify(args)
    raise AssertionError(f"unhandled command {args.command!r}")
