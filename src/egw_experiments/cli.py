"""Command-line interface of the experiment harness.

Subcommands (plan 5.8/9.1 'Reprodutibilidade')::

    python -m egw_experiments plan --master-seed 42 [--output PATH] [--force]
    python -m egw_experiments run --run-id nominal-r01 [--plan PATH] ...
    python -m egw_experiments analyze [--base-dir PATH]
    python -m egw_experiments verify-checksums [--base-dir PATH] [--run-id ID]

``plan`` writes the fully enumerated deterministic campaign plan; ``run``
executes exactly one planned simulator run on the VM (CONTRACTS 7); ``analyze``
regenerates everything under ``results/processed`` and ``results/figures``
from ``results/raw``; ``verify-checksums`` re-verifies the SHA256SUMS of raw
run directories (evidence integrity, plan 5.8).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyze import analyze
from .checksums import verify_sha256sums
from .plan_gen import generate_campaign_plan, write_campaign_plan
from .run import DEFAULT_PLAN_PATH, DEFAULT_RESULTS_BASE, execute_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="egw_experiments",
        description="EGW experiment harness: plan, run, analyze, verify.",
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
        "run", help="execute one planned simulator run on the VM"
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
    p_run.add_argument("--broker", default="localhost", help="MQTT broker host")
    p_run.add_argument(
        "--port", type=int, default=8883, help="MQTT port (default 8883, TLS)"
    )
    p_run.add_argument("--username", default=None, help="MQTT username")
    p_run.add_argument("--password", default=None, help="MQTT password")
    p_run.add_argument("--ca-cert", default=None, help="CA certificate path (TLS)")
    p_run.add_argument(
        "--no-tls",
        action="store_true",
        help="disable TLS; allowed only against localhost and never in "
        "benchmarks (CONTRACTS 1)",
    )
    p_run.add_argument("--qos", type=int, default=1, help="MQTT QoS (default 1)")
    p_run.add_argument(
        "--egw-id", default=None, help="gateway id (default: EGW_ID env or egw-01)"
    )
    p_run.add_argument(
        "--event-log-dir",
        default=None,
        help="controller EGW_EVENT_LOG_DIR (default: env or ./data/events)",
    )
    p_run.add_argument(
        "--post-run-wait",
        type=float,
        default=None,
        help="seconds to wait after the run for late confirmations "
        "(default: the 60 s confirmation window of plan 7.3)",
    )
    p_run.add_argument(
        "--skip-warmup", action="store_true", help="skip the planned warm-up"
    )
    p_run.add_argument(
        "--skip-cooldown", action="store_true", help="skip the planned cooldown"
    )

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
    if args.command == "analyze":
        return analyze(base_dir=args.base_dir)
    if args.command == "verify-checksums":
        return _cmd_verify(args)
    raise AssertionError(f"unhandled command {args.command!r}")
