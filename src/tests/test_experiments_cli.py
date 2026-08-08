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
    # Nothing was created: the refusal happens before any side effect.
    assert not (tmp_path / "results").exists()
