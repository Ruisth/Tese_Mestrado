"""Command-line interface of the simulator (CONTRACTS.md section 7, binding).

Reference invocation:

    python -m egw_simulator run --scenario nominal --seed 42 \\
      --broker <host> --port 8883 --duration 600 --rate 11.2 --output <dir> \\
      [--devices smartwatch,smart_ring,smart_clothing] [--egw-id egw-01] \\
      [--run-id <id>] [--username u --password p --ca-cert ca.crt | --no-tls] \\
      [--qos 1]

Defaults follow CONTRACTS.md section 6 environment variables where they
exist (EGW_ID, EGW_MQTT_HOST, EGW_MQTT_PORT, EGW_MQTT_USERNAME,
EGW_MQTT_PASSWORD, EGW_MQTT_CA_CERT). Secrets are passed to the publisher
only and never written to any output file.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .devices import DEVICE_TYPES
from .runner import RunConfig, run
from .scenarios import SCENARIOS

#: Envelope pattern for run_id and egw_id (CONTRACTS.md section 2).
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

#: Hosts for which the --no-tls dev profile is allowed (CONTRACTS.md section 1).
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

DEFAULT_DEVICES = ",".join(DEVICE_TYPES)
DEFAULT_OUTPUT = "results/raw"


def default_run_id(scenario: str, seed: int, now: datetime | None = None) -> str:
    """Default run id: ``{scenario}-{seed}-{UTC compact timestamp}``."""
    if now is None:
        now = datetime.now(timezone.utc)
    return f"{scenario}-{seed}-{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with the exact reference flags."""
    parser = argparse.ArgumentParser(
        prog="egw_simulator",
        description=(
            "Unified wearable telemetry simulator "
            "(smartwatch, smart_ring, smart_clothing)"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="execute one simulation run")
    run_p.add_argument(
        "--scenario",
        required=True,
        choices=tuple(SCENARIOS),
        help="scenario to execute",
    )
    run_p.add_argument("--seed", type=int, default=42, help="determinism seed")
    run_p.add_argument(
        "--broker",
        default=os.environ.get("EGW_MQTT_HOST", "localhost"),
        help="MQTT broker host (default: $EGW_MQTT_HOST or localhost)",
    )
    run_p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("EGW_MQTT_PORT", "8883")),
        help="MQTT broker port (default: $EGW_MQTT_PORT or 8883)",
    )
    run_p.add_argument(
        "--duration",
        type=float,
        default=None,
        help="run duration in seconds (default: scenario default)",
    )
    run_p.add_argument(
        "--rate",
        type=float,
        default=None,
        help=(
            "aggregate message rate in msg/s, split 1:0.2:10 across "
            "smartwatch:smart_ring:smart_clothing (default: scenario "
            "default; required for load-sweep)"
        ),
    )
    run_p.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"output directory; outputs go to <output>/<run_id>/ "
        f"(default: {DEFAULT_OUTPUT})",
    )
    run_p.add_argument(
        "--devices",
        default=DEFAULT_DEVICES,
        help=f"comma-separated device types (default: {DEFAULT_DEVICES})",
    )
    run_p.add_argument(
        "--egw-id",
        default=os.environ.get("EGW_ID", "egw-01"),
        help="gateway identifier (default: $EGW_ID or egw-01)",
    )
    run_p.add_argument(
        "--run-id",
        default=None,
        help="run identifier (default: {scenario}-{seed}-{UTC timestamp})",
    )
    run_p.add_argument(
        "--username",
        default=os.environ.get("EGW_MQTT_USERNAME"),
        help="MQTT username (default: $EGW_MQTT_USERNAME)",
    )
    run_p.add_argument(
        "--password",
        default=os.environ.get("EGW_MQTT_PASSWORD"),
        help="MQTT password (default: $EGW_MQTT_PASSWORD; never logged)",
    )
    run_p.add_argument(
        "--ca-cert",
        default=os.environ.get("EGW_MQTT_CA_CERT"),
        help="CA certificate file for TLS server auth "
        "(default: $EGW_MQTT_CA_CERT)",
    )
    run_p.add_argument(
        "--no-tls",
        action="store_true",
        help="disable TLS (dev profile; localhost brokers only, never benchmarks)",
    )
    run_p.add_argument(
        "--qos",
        type=int,
        choices=(0, 1, 2),
        default=1,
        help="MQTT QoS (contract default: 1)",
    )
    return parser


def config_from_args(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> RunConfig:
    """Resolve scenario defaults and validate arguments into a RunConfig."""
    spec = SCENARIOS[args.scenario]

    duration = args.duration if args.duration is not None else spec.default_duration_s
    if duration <= 0:
        parser.error("--duration must be positive")

    rate = args.rate if args.rate is not None else spec.default_rate_hz
    if rate is None:
        parser.error(f"--rate is required for scenario '{args.scenario}'")
    if rate <= 0:
        parser.error("--rate must be positive")

    device_types = tuple(t.strip() for t in args.devices.split(",") if t.strip())
    if not device_types:
        parser.error("--devices must name at least one device type")
    unknown = [t for t in device_types if t not in DEVICE_TYPES]
    if unknown:
        parser.error(
            f"unknown device types {','.join(unknown)}; "
            f"valid: {','.join(DEVICE_TYPES)}"
        )
    if len(set(device_types)) != len(device_types):
        parser.error("--devices must not repeat device types")

    run_id = args.run_id or default_run_id(args.scenario, args.seed)
    if not RUN_ID_RE.fullmatch(run_id):
        parser.error(
            "--run-id must match ^[A-Za-z0-9._-]{1,64}$ (CONTRACTS.md section 2)"
        )
    if not RUN_ID_RE.fullmatch(args.egw_id):
        parser.error(
            "--egw-id must match ^[A-Za-z0-9._-]{1,64}$ (CONTRACTS.md section 2)"
        )

    tls = not args.no_tls
    if not tls and args.broker not in LOCAL_HOSTS:
        parser.error(
            "--no-tls is allowed only for localhost brokers and never in "
            "benchmarks (CONTRACTS.md section 1)"
        )

    return RunConfig(
        scenario=args.scenario,
        seed=args.seed,
        run_id=run_id,
        egw_id=args.egw_id,
        duration_s=duration,
        aggregate_rate_hz=rate,
        device_types=device_types,
        qos=args.qos,
        broker_host=args.broker,
        broker_port=args.port,
        tls=tls,
        ca_cert=args.ca_cert,
        output_dir=Path(args.output),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":  # unreachable: subcommand is required
        parser.error(f"unknown command {args.command!r}")
    config = config_from_args(args, parser)

    from .publisher import PahoPublisher  # lazy: needs paho-mqtt

    publisher = PahoPublisher(
        config.broker_host,
        config.broker_port,
        username=args.username,
        password=args.password,
        ca_cert=args.ca_cert,
        tls=config.tls,
        qos=config.qos,
        client_id=f"egw-simulator-{config.run_id}"[:64],
    )
    print(
        f"egw_simulator: scenario={config.scenario} seed={config.seed} "
        f"run_id={config.run_id} broker={config.broker_host}:{config.broker_port} "
        f"tls={config.tls} qos={config.qos} duration={config.duration_s}s "
        f"rate={config.aggregate_rate_hz}msg/s "
        f"devices={','.join(config.device_types)}",
        file=sys.stderr,
    )
    try:
        publisher.connect()
    except (ConnectionError, OSError) as exc:
        print(f"egw_simulator: connection failed: {exc}", file=sys.stderr)
        return 1
    try:
        result = run(config, publisher)
    except KeyboardInterrupt:
        print(
            "egw_simulator: interrupted; partial outputs written "
            "(manifest completed=false)",
            file=sys.stderr,
        )
        return 130
    finally:
        publisher.close()
    print(
        f"egw_simulator: done sent={result.sent} "
        f"intended_invalid={result.intended_invalid} "
        f"skipped_dropout={result.skipped_dropout}",
        file=sys.stderr,
    )
    print(str(result.run_dir))
    return 0
