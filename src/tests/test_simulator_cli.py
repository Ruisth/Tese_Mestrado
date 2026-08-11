"""CLI tests: exact reference flags of CONTRACTS.md section 7 and defaults.

Parsing and config resolution are exercised directly; ``main()`` is
exercised end-to-end with a recording fake monkeypatched over
``egw_simulator.cli.PahoPublisher``, so no broker is ever contacted.
"""

import json
import re
import time

import pytest

import egw_simulator.cli as cli
from egw_simulator.cli import (
    RUN_ID_RE,
    build_parser,
    config_from_args,
    default_run_id,
    main,
)
from egw_simulator.devices import DEVICE_TYPES
from egw_simulator.publisher import PublishResult
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
    # Five-minute executions per load (plan section 7.1).
    assert config.duration_s == 300.0


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


# --------------------------------------------------------------- main() tests

def install_fake_publisher(monkeypatch, *, connect_exc=None, interrupt_after=None):
    """Monkeypatch cli.PahoPublisher with a recording, broker-free fake.

    ``connect_exc``: exception instance raised by ``connect()``.
    ``interrupt_after``: raise KeyboardInterrupt on publish number N+1
    (after N successful publishes), emulating Ctrl-C mid-run.
    """

    class RecordingPublisher:
        instances: list = []

        def __init__(self, host, port=8883, **kwargs):
            self.host = host
            self.port = port
            self.kwargs = kwargs
            self.connected = False
            self.closed = False
            self.published: list[tuple[str, bytes]] = []
            self.drain_calls: list[float] = []
            type(self).instances.append(self)

        def connect(self):
            if connect_exc is not None:
                raise connect_exc
            self.connected = True

        def publish(self, topic, payload, *, wait_budget_s=0.0):
            if interrupt_after is not None and len(self.published) >= interrupt_after:
                raise KeyboardInterrupt
            self.published.append((topic, payload))
            now = time.monotonic_ns()
            return PublishResult(now, now)  # instant ack

        def drain(self, timeout_s=60.0):
            self.drain_calls.append(timeout_s)
            return True

        def close(self):
            self.closed = True

    monkeypatch.setattr(cli, "PahoPublisher", RecordingPublisher)
    return RecordingPublisher


def main_argv(tmp_path, run_id, *extra):
    """Short smoke run (3 events, all at t=0) writing under tmp_path."""
    return [
        "run",
        "--scenario", "smoke",
        "--seed", "42",
        "--duration", "0.05",
        "--run-id", run_id,
        "--output", str(tmp_path),
        *extra,
    ]


def test_main_passes_flags_to_publisher_and_closes_it(tmp_path, monkeypatch, capsys):
    fake_cls = install_fake_publisher(monkeypatch)
    rc = main(
        main_argv(
            tmp_path,
            "cli-success",
            "--broker", "broker.example.org",
            "--port", "8884",
            "--username", "egw-simulator",
            "--password", "secret",
            "--ca-cert", "ca.crt",
            "--qos", "1",
        )
    )
    assert rc == 0
    (publisher,) = fake_cls.instances
    # Constructor receives exactly the connection flags (CONTRACTS section 7).
    assert publisher.host == "broker.example.org"
    assert publisher.port == 8884
    assert publisher.kwargs["username"] == "egw-simulator"
    assert publisher.kwargs["password"] == "secret"
    assert publisher.kwargs["ca_cert"] == "ca.crt"
    assert publisher.kwargs["tls"] is True
    assert publisher.kwargs["qos"] == 1
    assert publisher.kwargs["client_id"] == "egw-simulator-cli-success"
    # Lifecycle: connected, drained once, closed on the finally path.
    assert publisher.connected is True
    assert publisher.closed is True
    assert publisher.drain_calls == [60.0]
    assert len(publisher.published) == 3  # one event per device at t=0
    # Outputs written; run dir printed on stdout; no secrets in outputs.
    run_dir = tmp_path / "cli-success"
    assert capsys.readouterr().out.strip() == str(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["completed"] is True
    assert "secret" not in (run_dir / "manifest.json").read_text(encoding="utf-8")


def test_main_no_tls_flag_reaches_publisher(tmp_path, monkeypatch):
    fake_cls = install_fake_publisher(monkeypatch)
    rc = main(main_argv(tmp_path, "cli-notls", "--broker", "localhost", "--no-tls"))
    assert rc == 0
    (publisher,) = fake_cls.instances
    assert publisher.host == "localhost"
    assert publisher.kwargs["tls"] is False


def test_main_returns_nonzero_on_connect_failure(tmp_path, monkeypatch, capsys):
    fake_cls = install_fake_publisher(
        monkeypatch, connect_exc=ConnectionError("refused")
    )
    rc = main(main_argv(tmp_path, "cli-noconnect"))
    assert rc == 1
    (publisher,) = fake_cls.instances
    assert publisher.published == []
    assert "connection failed" in capsys.readouterr().err
    # The run never started, so no run directory may exist.
    assert not (tmp_path / "cli-noconnect").exists()


def test_main_keyboard_interrupt_exits_130_with_partial_outputs(
    tmp_path, monkeypatch
):
    fake_cls = install_fake_publisher(monkeypatch, interrupt_after=1)
    rc = main(main_argv(tmp_path, "cli-kbint"))
    assert rc == 130
    (publisher,) = fake_cls.instances
    assert publisher.closed is True  # finally path still closes the publisher
    run_dir = tmp_path / "cli-kbint"
    # Partial outputs are written: manifest flags the incomplete run and
    # sent_events.jsonl holds the records published before the interrupt.
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["completed"] is False
    lines = [
        json.loads(line)
        for line in (run_dir / "sent_events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert len(lines) == len(publisher.published) == 1
