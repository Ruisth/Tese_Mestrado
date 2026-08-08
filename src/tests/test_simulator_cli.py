"""CLI tests: exact reference flags of CONTRACTS.md section 7 and defaults.

Only parsing and config resolution are exercised; no broker connection is
made (``main()`` is not called).
"""

import re

import pytest

from egw_simulator.cli import (
    RUN_ID_RE,
    build_parser,
    config_from_args,
    default_run_id,
)
from egw_simulator.devices import DEVICE_TYPES
from egw_simulator.runner import RunConfig

ENV_VARS = (
    "EGW_ID",
    "EGW_MQTT_HOST",
    "EGW_MQTT_PORT",
    "EGW_MQTT_USERNAME",
    "EGW_MQTT_PASSWORD",
    "EGW_MQTT_CA_CERT",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Isolate CLI defaults from the host environment."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def parse(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    return parser, args


REFERENCE_ARGV = [
    "run",
    "--scenario", "nominal",
    "--seed", "42",
    "--broker", "broker.example.org",
    "--port", "8883",
    "--duration", "600",
    "--rate", "11.2",
    "--output", "results/raw",
    "--devices", "smartwatch,smart_ring,smart_clothing",
    "--egw-id", "egw-01",
    "--run-id", "nominal-42-manual",
    "--username", "egw-simulator",
    "--password", "secret",
    "--ca-cert", "ca.crt",
    "--qos", "1",
]


def test_reference_command_parses_with_exact_flags():
    _parser, args = parse(REFERENCE_ARGV)
    assert args.command == "run"
    assert args.scenario == "nominal"
    assert args.seed == 42
    assert args.broker == "broker.example.org"
    assert args.port == 8883
    assert args.duration == 600.0
    assert args.rate == 11.2
    assert args.output == "results/raw"
    assert args.devices == "smartwatch,smart_ring,smart_clothing"
    assert args.egw_id == "egw-01"
    assert args.run_id == "nominal-42-manual"
    assert args.username == "egw-simulator"
    assert args.password == "secret"
    assert args.ca_cert == "ca.crt"
    assert args.no_tls is False
    assert args.qos == 1


def test_reference_command_resolves_to_config():
    parser, args = parse(REFERENCE_ARGV)
    config = config_from_args(args, parser)
    assert isinstance(config, RunConfig)
    assert config.scenario == "nominal"
    assert config.seed == 42
    assert config.run_id == "nominal-42-manual"
    assert config.egw_id == "egw-01"
    assert config.duration_s == 600.0
    assert config.aggregate_rate_hz == pytest.approx(11.2)
    assert config.device_types == DEVICE_TYPES
    assert config.qos == 1
    assert config.broker_host == "broker.example.org"
    assert config.broker_port == 8883
    assert config.tls is True
    assert config.ca_cert == "ca.crt"
    from pathlib import Path

    assert Path(config.output_dir) == Path("results/raw")


def test_defaults_and_generated_run_id():
    parser, args = parse(["run", "--scenario", "nominal"])
    config = config_from_args(args, parser)
    assert args.seed == 42
    assert config.broker_host == "localhost"
    assert config.broker_port == 8883
    assert config.duration_s == 600.0  # scenario default
    assert config.aggregate_rate_hz == pytest.approx(11.2)  # scenario default
    assert config.egw_id == "egw-01"
    assert config.qos == 1
    assert config.tls is True
    # Default run id: {scenario}-{seed}-{UTC compact timestamp}.
    assert re.fullmatch(r"nominal-42-\d{8}T\d{6}Z", config.run_id)
    assert RUN_ID_RE.fullmatch(config.run_id)


def test_default_run_id_shape_is_stable():
    from datetime import datetime, timezone

    now = datetime(2026, 8, 7, 12, 34, 56, tzinfo=timezone.utc)
    assert default_run_id("smoke", 7, now) == "smoke-7-20260807T123456Z"


@pytest.mark.parametrize(
    ("scenario", "duration"),
    [("smoke", 30.0), ("nominal", 600.0), ("soak", 86400.0)],
)
def test_scenario_default_durations(scenario, duration):
    parser, args = parse(["run", "--scenario", scenario])
    config = config_from_args(args, parser)
    assert config.duration_s == duration
    assert config.aggregate_rate_hz == pytest.approx(11.2)


def test_load_sweep_requires_rate():
    parser, args = parse(["run", "--scenario", "load-sweep"])
    with pytest.raises(SystemExit):
        config_from_args(args, parser)
    parser, args = parse(["run", "--scenario", "load-sweep", "--rate", "100"])
    config = config_from_args(args, parser)
    assert config.aggregate_rate_hz == 100.0
    assert config.duration_s == 600.0


def test_no_tls_allowed_only_for_localhost():
    parser, args = parse(["run", "--scenario", "smoke", "--no-tls"])
    config = config_from_args(args, parser)
    assert config.tls is False
    assert config.broker_host == "localhost"

    parser, args = parse(
        ["run", "--scenario", "smoke", "--broker", "broker.example.org", "--no-tls"]
    )
    with pytest.raises(SystemExit):
        config_from_args(args, parser)


def test_device_subset_and_rejections():
    parser, args = parse(
        ["run", "--scenario", "nominal", "--devices", "smartwatch,smart_ring"]
    )
    config = config_from_args(args, parser)
    assert config.device_types == ("smartwatch", "smart_ring")

    parser, args = parse(["run", "--scenario", "nominal", "--devices", "drone"])
    with pytest.raises(SystemExit):
        config_from_args(args, parser)

    parser, args = parse(
        ["run", "--scenario", "nominal", "--devices", "smartwatch,smartwatch"]
    )
    with pytest.raises(SystemExit):
        config_from_args(args, parser)


def test_invalid_run_id_and_scenario_rejected():
    parser, args = parse(["run", "--scenario", "nominal", "--run-id", "bad run id"])
    with pytest.raises(SystemExit):
        config_from_args(args, parser)

    parser = build_parser()
    with pytest.raises(SystemExit):  # argparse choices guard
        parser.parse_args(["run", "--scenario", "unknown-scenario"])
    with pytest.raises(SystemExit):  # QoS outside choices
        parser.parse_args(["run", "--scenario", "nominal", "--qos", "3"])
