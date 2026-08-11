"""Tests for egw_experiments.cli exit codes and user-facing messages.

Stdlib-only fixtures; no docker, no network, no broker. Only fail-fast code
paths are driven (existing plan file, tampered checksums, external-condition
run ids), so no simulator subprocess is ever spawned.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from egw_experiments import checksums, cli, plan_gen
from egw_experiments.analyze import CAMPAIGN_PLAN_ENV_VAR
from egw_experiments.run import DEFAULT_PLAN_PATH


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def test_plan_twice_without_force_exits_2(tmp_path, capsys) -> None:
    out = tmp_path / "campaign_plan.json"
    assert cli.main(["plan", "--master-seed", "42", "--output", str(out)]) == 0
    # The plan tracks run statuses: overwriting must be deliberate.
    assert cli.main(["plan", "--master-seed", "42", "--output", str(out)]) == 2
    err = capsys.readouterr().err
    assert "already exists" in err
    assert "--force" in err
    # --force overwrites deliberately.
    assert (
        cli.main(["plan", "--master-seed", "42", "--output", str(out), "--force"])
        == 0
    )


# ---------------------------------------------------------------------------
# verify-checksums
# ---------------------------------------------------------------------------


def _make_verified_run(base: Path) -> Path:
    run_dir = base / "raw" / "nominal-r01"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"run_id": "nominal-r01"}\n', "utf-8")
    (run_dir / "events.jsonl").write_text('{"outcome": "accepted"}\n', "utf-8")
    checksums.write_sha256sums(run_dir)
    return run_dir


def test_verify_checksums_exits_1_on_tampered_run_dir(tmp_path) -> None:
    base = tmp_path / "results"
    run_dir = _make_verified_run(base)
    assert cli.main(["verify-checksums", "--base-dir", str(base)]) == 0
    (run_dir / "events.jsonl").write_text('{"outcome": "tampered"}\n', "utf-8")
    assert cli.main(["verify-checksums", "--base-dir", str(base)]) == 1


def test_verify_checksums_exits_2_on_missing_base_dir(tmp_path, capsys) -> None:
    missing = tmp_path / "does-not-exist"
    assert cli.main(["verify-checksums", "--base-dir", str(missing)]) == 2
    assert "does not exist" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# run (external conditions are never driven by the simulator harness)
# ---------------------------------------------------------------------------


def test_run_with_external_condition_run_id_exits_2(tmp_path, capsys) -> None:
    plan_path = tmp_path / "campaign_plan.json"
    plan_gen.write_campaign_plan(plan_gen.generate_campaign_plan(42), plan_path)
    rc = cli.main(
        [
            "run",
            "--run-id",
            "qemu_boot-r01",
            "--plan",
            str(plan_path),
            "--base-dir",
            str(tmp_path / "results"),
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "not driven by the simulator" in err
    # The refusal points to the ingestion path for external evidence.
    assert "--external-timings" in err
    # Nothing was created: the refusal happens before any side effect.
    assert not (tmp_path / "results").exists()


# ---------------------------------------------------------------------------
# run: new collection/validity flags parse (audit 9.1-9.7)
# ---------------------------------------------------------------------------


def test_run_parser_accepts_collection_and_hook_flags() -> None:
    args = cli.build_parser().parse_args(
        [
            "run",
            "--run-id",
            "nominal-r01",
            "--fetch-events-cmd",
            "scp vm:/opt/egw/data/events/{run_id}/events.jsonl {dest}",
            "--sut-env-from",
            "sut_environment.json",
            "--resources-from",
            "resources.csv",
            "--allow-missing-sut-env",
            "--allow-missing-resources",
            "--controller-url",
            "http://127.0.0.1:8000",
            "--restart-cmd",
            "ssh vm docker compose restart controller",
            "--restart-at-s",
            "300",
            "--external-timings",
            "timings.json",
            "--external-logs",
            "logs",
            "--local-resources",
            "--allow-warmup-failure",
            "--allow-protocol-deviation",
        ]
    )
    assert args.fetch_events_cmd.endswith("{dest}")
    assert args.sut_env_from == "sut_environment.json"
    assert args.resources_from == "resources.csv"
    assert args.allow_missing_sut_env is True
    assert args.allow_missing_resources is True
    assert args.controller_url == "http://127.0.0.1:8000"
    assert args.restart_at_s == 300.0
    assert args.external_timings == "timings.json"
    assert args.local_resources is True
    # Work order P1 fix 5: deviation-authorization flags.
    assert args.allow_warmup_failure is True
    assert args.allow_protocol_deviation is True


def test_run_parser_deviation_flags_default_false() -> None:
    args = cli.build_parser().parse_args(["run", "--run-id", "nominal-r01"])
    assert args.allow_warmup_failure is False
    assert args.allow_protocol_deviation is False


# ---------------------------------------------------------------------------
# run/campaign: sprint P5 flags (collector hooks, confirmation marker)
# ---------------------------------------------------------------------------


COLLECTOR_START = (
    "ssh vm 'systemd-run --unit egw-resources-{run_id} --collect sh "
    "/opt/egw/src/deployment/scripts/collect-resources.sh "
    "/tmp/resources-{run_id}.csv --duration {duration_s}'"
)
COLLECTOR_STOP = "ssh vm 'systemctl stop egw-resources-{run_id}'"
COLLECTOR_FETCH = "scp vm:/tmp/resources-{run_id}.csv {dest}"


def test_run_parser_accepts_collector_hooks_and_marker_override() -> None:
    args = cli.build_parser().parse_args(
        [
            "run",
            "--run-id",
            "nominal-r01",
            "--collector-start-cmd",
            COLLECTOR_START,
            "--collector-stop-cmd",
            COLLECTOR_STOP,
            "--collector-fetch-cmd",
            COLLECTOR_FETCH,
            "--allow-missing-controller-marker",
        ]
    )
    assert "{duration_s}" in args.collector_start_cmd
    assert "{run_id}" in args.collector_stop_cmd
    assert args.collector_fetch_cmd.endswith("{dest}")
    assert args.allow_missing_controller_marker is True


def test_campaign_parser_accepts_collector_hooks_and_marker_override() -> None:
    args = cli.build_parser().parse_args(
        [
            "campaign",
            "--collector-start-cmd",
            COLLECTOR_START,
            "--collector-stop-cmd",
            COLLECTOR_STOP,
            "--collector-fetch-cmd",
            COLLECTOR_FETCH,
            "--allow-missing-controller-marker",
        ]
    )
    assert "{duration_s}" in args.collector_start_cmd
    assert args.collector_fetch_cmd.endswith("{dest}")
    assert args.allow_missing_controller_marker is True


def test_p5_flags_default_to_off() -> None:
    parser = cli.build_parser()
    run_args = parser.parse_args(["run", "--run-id", "nominal-r01"])
    assert run_args.collector_start_cmd is None
    assert run_args.collector_stop_cmd is None
    assert run_args.collector_fetch_cmd is None
    assert run_args.allow_missing_controller_marker is False
    camp_args = parser.parse_args(["campaign"])
    assert camp_args.collector_fetch_cmd is None
    assert camp_args.allow_missing_controller_marker is False
    # 'collect' can re-apply the authorization but never re-measures the
    # marker, so it takes the flag without the hooks.
    col_args = parser.parse_args(["collect", "--run-id", "nominal-r01"])
    assert col_args.allow_missing_controller_marker is False
    assert not hasattr(col_args, "collector_start_cmd")


# ---------------------------------------------------------------------------
# analyze: identity completeness needs the plan on the OFFICIAL command
# ---------------------------------------------------------------------------


def test_analyze_parser_takes_plan_defaulting_to_the_frozen_plan() -> None:
    """The shipped 'analyze' must be able to do identity completeness: the
    subcommand carries --plan with the SAME default as run/campaign/collect,
    so the frozen plan is used automatically when it exists (sprint P5.4)."""
    args = cli.build_parser().parse_args(["analyze"])
    assert args.plan == DEFAULT_PLAN_PATH
    explicit = cli.build_parser().parse_args(["analyze", "--plan", "other.json"])
    assert explicit.plan == Path("other.json")


def test_analyze_usage_and_help_document_plan_and_env_fallback(capsys) -> None:
    # The usage docstring is the shipped documentation of the subcommand.
    assert "analyze [--base-dir PATH] [--plan PATH]" in (cli.__doc__ or "")
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["analyze", "--help"])
    help_text = capsys.readouterr().out
    assert "--plan" in help_text
    # The environment-variable fallback of analyze() must be documented
    # where the operator looks for it.
    assert CAMPAIGN_PLAN_ENV_VAR in help_text
    assert "IDENTITY-based" in help_text


def _empty_results_tree(tmp_path: Path) -> Path:
    base = tmp_path / "results"
    (base / "raw").mkdir(parents=True)
    return base


def _acceptance_rows(base: Path) -> list[dict]:
    text = (base / "processed" / "acceptance_by_condition.csv").read_text("utf-8")
    return list(csv.DictReader(text.splitlines()))


def test_analyze_cli_forwards_plan_to_identity_completeness(tmp_path, capsys) -> None:
    base = _empty_results_tree(tmp_path)
    plan_path = tmp_path / "campaign_plan.json"
    plan_gen.write_campaign_plan(plan_gen.generate_campaign_plan(42), plan_path)

    assert cli.main(["analyze", "--base-dir", str(base), "--plan", str(plan_path)]) == 0

    out = capsys.readouterr().out
    assert "BY COUNT ONLY" not in out
    complete = next(
        r
        for r in _acceptance_rows(base)
        if r["condition_id"] == "smoke_sequence" and r["criterion"] == "runs_complete"
    )
    # Identity checking really ran: the missing runs are named, not counted.
    assert "identity mismatch vs campaign plan" in complete["observed"]
    assert "identity checking NOT performed" not in complete["observed"]


def test_analyze_cli_without_an_existing_plan_degrades_to_counts(
    tmp_path, capsys
) -> None:
    """A missing plan file degrades to count-only completeness with the
    existing warning; the analysis never fails because of it."""
    base = _empty_results_tree(tmp_path)
    missing = tmp_path / "campaign_plan.json"

    assert cli.main(["analyze", "--base-dir", str(base), "--plan", str(missing)]) == 0

    captured = capsys.readouterr()
    assert "could not be read" in captured.err
    assert "BY COUNT ONLY" in captured.out
    complete = next(
        r
        for r in _acceptance_rows(base)
        if r["condition_id"] == "smoke_sequence" and r["criterion"] == "runs_complete"
    )
    assert "identity checking NOT performed" in complete["observed"]


def test_analyze_cli_absent_default_plan_falls_back_to_env_var(
    tmp_path, monkeypatch, capsys
) -> None:
    """A results tree analyzed before the plan is frozen is not an operator
    error: the absent DEFAULT plan degrades to counts quietly and the
    documented EGW_CAMPAIGN_PLAN fallback stays reachable."""
    base = _empty_results_tree(tmp_path)
    plan_path = tmp_path / "env_campaign_plan.json"
    plan_gen.write_campaign_plan(plan_gen.generate_campaign_plan(42), plan_path)
    monkeypatch.setattr(cli, "DEFAULT_PLAN_PATH", tmp_path / "absent_plan.json")

    monkeypatch.delenv(CAMPAIGN_PLAN_ENV_VAR, raising=False)
    assert cli.main(["analyze", "--base-dir", str(base)]) == 0
    captured = capsys.readouterr()
    assert "BY COUNT ONLY" in captured.out
    assert "could not be read" not in captured.err

    monkeypatch.setenv(CAMPAIGN_PLAN_ENV_VAR, str(plan_path))
    assert cli.main(["analyze", "--base-dir", str(base)]) == 0
    assert "BY COUNT ONLY" not in capsys.readouterr().out
    complete = next(
        r
        for r in _acceptance_rows(base)
        if r["condition_id"] == "smoke_sequence" and r["criterion"] == "runs_complete"
    )
    assert "identity mismatch vs campaign plan" in complete["observed"]


# ---------------------------------------------------------------------------
# collect (recovery path, audit 9.3)
# ---------------------------------------------------------------------------


def test_collect_on_missing_run_dir_exits_2(tmp_path, capsys) -> None:
    plan_path = tmp_path / "campaign_plan.json"
    plan_gen.write_campaign_plan(plan_gen.generate_campaign_plan(42), plan_path)
    rc = cli.main(
        [
            "collect",
            "--run-id",
            "nominal-r01",
            "--plan",
            str(plan_path),
            "--base-dir",
            str(tmp_path / "results"),
        ]
    )
    assert rc == 2
    assert "only recovers runs already executed" in capsys.readouterr().err
