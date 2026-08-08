"""Tests for egw_experiments.cli exit codes and user-facing messages.

Stdlib-only fixtures; no docker, no network, no broker. Only fail-fast code
paths are driven (existing plan file, tampered checksums, external-condition
run ids), so no simulator subprocess is ever spawned.
"""
from __future__ import annotations

from pathlib import Path

from egw_experiments import checksums, cli, plan_gen


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
