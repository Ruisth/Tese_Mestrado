"""Tests for egw_experiments.campaign (work order P1 item 12).

A tiny synthetic plan (three simulator runs + one external condition, one
cooldown) is driven end-to-end with the fake simulator subprocess. No
broker, no docker, no network; time.sleep is recorded, never slept.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from egw_experiments import campaign as campaign_mod
from egw_experiments import cli
from egw_experiments import run as run_mod

SUT_NODE = "sut-vm"
RESOURCES_HEADER = "ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"

SIM_RUN_IDS = ["smoke-r01", "smoke-r02", "smoke-r03"]
EXTERNAL_RUN_ID = "cold-r01"
PLAN_ORDER = ["smoke-r01", EXTERNAL_RUN_ID, "smoke-r02", "smoke-r03"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sim_entry(run_id: str, order: int, cooldown_s: int) -> dict:
    return {
        "run_id": run_id,
        "condition_id": "smoke_sequence",
        "runner": "simulator",
        "scenario": "smoke",
        "repetition": order,
        "rate_msg_s": 11.2,
        "duration_s": 30,
        "warmup_s": 0,
        "cooldown_s": cooldown_s,
        "seed": 100 + order,
        "status": "planned",
        "order": order,
    }


@pytest.fixture
def plan_path(tmp_path: Path) -> Path:
    """Synthetic frozen plan: sim (cooldown 90) -> external -> sim -> sim."""
    runs = [
        _sim_entry("smoke-r01", 1, cooldown_s=90),
        {
            "run_id": EXTERNAL_RUN_ID,
            "condition_id": "cold_start",
            "runner": "external",
            "scenario": None,
            "repetition": 1,
            "rate_msg_s": None,
            "duration_s": None,
            "warmup_s": 0,
            "cooldown_s": 0,
            "seed": 200,
            "status": "planned",
            "order": 2,
        },
        _sim_entry("smoke-r02", 3, cooldown_s=0),
        _sim_entry("smoke-r03", 4, cooldown_s=0),
    ]
    plan = {
        "plan_version": "1.0",
        "protocol_version": "1.0.0",
        "master_seed": 7,
        "conditions": [],
        "runs": runs,
    }
    path = tmp_path / "campaign_plan.json"
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", "utf-8")
    return path


@pytest.fixture
def fake_env(monkeypatch, tmp_path: Path) -> SimpleNamespace:
    """Fake simulator (REAL <output>/<run_id>/ layout), recorded sleeps,
    per-run evidence files and the common campaign kwargs."""
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def fake_subprocess(cmd, log_path, timeout_s):
        calls.append(list(cmd))
        out_dir = Path(cmd[cmd.index("--output") + 1])
        run_id = cmd[cmd.index("--run-id") + 1]
        sim_run_dir = out_dir / run_id  # real layout (egw_simulator.runner)
        sim_run_dir.mkdir(parents=True, exist_ok=True)
        (sim_run_dir / "sent_events.jsonl").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "message_id": "00000000-0000-5000-8000-000000000001",
                    "seq": 0,
                    "intended_invalid": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (sim_run_dir / "manifest.json").write_text(
            json.dumps({"run_id": run_id}) + "\n", encoding="utf-8"
        )
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_text("fake simulator\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(run_mod, "_run_subprocess", fake_subprocess)
    monkeypatch.setattr(
        run_mod,
        "write_loadgen_environment",
        lambda path: Path(path).write_text('{"role": "loadgen"}\n', "utf-8"),
    )
    monkeypatch.setattr(run_mod, "read_git_commit", lambda *a, **k: "test-commit")
    monkeypatch.setattr(run_mod.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.delenv(run_mod.FETCH_EVENTS_CMD_ENV, raising=False)
    monkeypatch.delenv(run_mod.SUT_ENV_FILE_ENV, raising=False)

    # Per-run controller events (local dev fallback layout).
    event_log_dir = tmp_path / "event-log"
    for rid in SIM_RUN_IDS:
        per_run = event_log_dir / rid
        per_run.mkdir(parents=True, exist_ok=True)
        (per_run / "events.jsonl").write_text(
            json.dumps({"run_id": rid, "outcome": "accepted"}) + "\n", "utf-8"
        )

    sut_env = tmp_path / "sut_environment.json"
    sut_env.write_text(
        json.dumps(
            {
                "role": "sut",
                "node": SUT_NODE,
                "nproc": 4,
                "uname_a": "Linux sut-vm 6.8.0 aarch64",
                "os_pretty_name": "fixture",
            }
        )
        + "\n",
        "utf-8",
    )

    # Per-run SUT resources, addressed by a {run_id} template.
    for rid in SIM_RUN_IDS:
        lines = [RESOURCES_HEADER]
        for i in range(40):
            lines.append(
                f"2026-09-07T10:00:{i % 60:02d}Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
            )
        (tmp_path / f"resources-{rid}.csv").write_text(
            "\n".join(lines) + "\n", "utf-8"
        )

    base = tmp_path / "results"
    kwargs = dict(
        results_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=event_log_dir,
        sut_env_from=sut_env,
        resources_from=(tmp_path / "resources-{run_id}.csv").as_posix(),
    )
    return SimpleNamespace(
        calls=calls, sleeps=sleeps, base=base, kwargs=kwargs, tmp_path=tmp_path
    )


def _log_lines(base: Path) -> list[dict]:
    log = base / campaign_mod.CAMPAIGN_LOG_FILENAME
    if not log.is_file():
        return []
    return [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _executed_run_ids(calls: list[list[str]]) -> list[str]:
    return [cmd[cmd.index("--run-id") + 1] for cmd in calls]


def _manifest(base: Path, run_id: str) -> dict:
    return json.loads(
        (base / "raw" / run_id / "manifest.json").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Order, logging, external checklist
# ---------------------------------------------------------------------------


def test_campaign_executes_plan_in_frozen_order_and_logs(
    plan_path, fake_env, capsys
) -> None:
    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 0
    # Frozen order preserved; the external run is never executed.
    assert _executed_run_ids(fake_env.calls) == SIM_RUN_IDS
    lines = _log_lines(fake_env.base)
    assert [line["run_id"] for line in lines] == PLAN_ORDER
    assert [line["outcome"] for line in lines] == [
        "completed",
        "external",
        "completed",
        "completed",
    ]
    for line in lines:
        assert set(line) == {
            "run_id",
            "condition",
            "started_utc",
            "finished_utc",
            "outcome",
            "validity",
            "note",
        }
    external = lines[1]
    assert external["condition"] == "cold_start"
    assert external["validity"] is None
    assert "--external-timings" in external["note"]
    out = capsys.readouterr().out
    assert f"EXTERNAL {EXTERNAL_RUN_ID}" in out
    # Every executed run went through the full run wiring (valid + sealed).
    for rid in SIM_RUN_IDS:
        assert _manifest(fake_env.base, rid)["validity"] == "valid"
        assert (fake_env.base / "raw" / rid / "SHA256SUMS").is_file()


def test_campaign_dry_run_executes_nothing(plan_path, fake_env, capsys) -> None:
    rc = campaign_mod.run_campaign(plan_path, dry_run=True, **fake_env.kwargs)
    assert rc == 0
    assert fake_env.calls == []
    assert _log_lines(fake_env.base) == []
    assert not (fake_env.base / "raw").exists()
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    for rid in PLAN_ORDER:
        assert rid in out
    assert "EXTERNAL" in out


# ---------------------------------------------------------------------------
# Resumability
# ---------------------------------------------------------------------------


def test_campaign_resume_skips_sealed_and_valid_runs(
    plan_path, fake_env, capsys
) -> None:
    assert campaign_mod.run_campaign(plan_path, **fake_env.kwargs) == 0
    first_round_calls = len(fake_env.calls)
    capsys.readouterr()

    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 0
    # Nothing re-executed: every simulator run is sealed AND valid.
    assert len(fake_env.calls) == first_round_calls
    lines = _log_lines(fake_env.base)[-4:]
    assert [line["outcome"] for line in lines] == [
        "skipped",
        "external",
        "skipped",
        "skipped",
    ]
    assert all(
        line["validity"] == "valid"
        for line in lines
        if line["outcome"] == "skipped"
    )
    assert "skip smoke-r01" in capsys.readouterr().out


def test_campaign_start_from_resumes_midway(plan_path, fake_env) -> None:
    rc = campaign_mod.run_campaign(
        plan_path, start_from="smoke-r02", **fake_env.kwargs
    )
    assert rc == 0
    assert _executed_run_ids(fake_env.calls) == ["smoke-r02", "smoke-r03"]
    assert [line["run_id"] for line in _log_lines(fake_env.base)] == [
        "smoke-r02",
        "smoke-r03",
    ]


def test_campaign_start_from_unknown_run_id_exits_2(
    plan_path, fake_env, capsys
) -> None:
    rc = campaign_mod.run_campaign(
        plan_path, start_from="nope-r99", **fake_env.kwargs
    )
    assert rc == 2
    assert "not in the plan" in capsys.readouterr().err
    assert fake_env.calls == []


def test_campaign_only_conditions_filters_without_reordering(
    plan_path, fake_env
) -> None:
    rc = campaign_mod.run_campaign(
        plan_path, only_conditions=["smoke_sequence"], **fake_env.kwargs
    )
    assert rc == 0
    assert _executed_run_ids(fake_env.calls) == SIM_RUN_IDS
    assert [line["run_id"] for line in _log_lines(fake_env.base)] == SIM_RUN_IDS


def test_campaign_only_conditions_unknown_exits_2(
    plan_path, fake_env, capsys
) -> None:
    rc = campaign_mod.run_campaign(
        plan_path, only_conditions=["not_a_condition"], **fake_env.kwargs
    )
    assert rc == 2
    assert "unknown condition" in capsys.readouterr().err
    assert fake_env.calls == []


# ---------------------------------------------------------------------------
# Stop-on-invalid vs --continue-on-invalid
# ---------------------------------------------------------------------------


def _make_first_run_invalid(fake_env) -> None:
    """Remove smoke-r01's SUT resources: its timed run becomes INVALID."""
    (fake_env.tmp_path / "resources-smoke-r01.csv").unlink()


def test_campaign_stops_at_first_invalid_run(plan_path, fake_env, capsys) -> None:
    _make_first_run_invalid(fake_env)
    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 1
    # Only the first run was attempted; the campaign stopped there.
    assert _executed_run_ids(fake_env.calls) == ["smoke-r01"]
    lines = _log_lines(fake_env.base)
    assert len(lines) == 1
    assert lines[0]["run_id"] == "smoke-r01"
    assert lines[0]["outcome"] == "invalid"
    assert lines[0]["validity"] == "invalid"
    assert "stopping at smoke-r01" in capsys.readouterr().err


def test_campaign_continue_on_invalid_records_and_moves_on(
    plan_path, fake_env
) -> None:
    _make_first_run_invalid(fake_env)
    rc = campaign_mod.run_campaign(
        plan_path, continue_on_invalid=True, **fake_env.kwargs
    )
    assert rc == 1  # finished, but NOT clean
    assert _executed_run_ids(fake_env.calls) == SIM_RUN_IDS
    lines = _log_lines(fake_env.base)
    assert [line["outcome"] for line in lines] == [
        "invalid",
        "external",
        "completed",
        "completed",
    ]


# ---------------------------------------------------------------------------
# Cooldown handling
# ---------------------------------------------------------------------------


def test_campaign_honors_plan_cooldown(plan_path, fake_env) -> None:
    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 0
    # smoke-r01's 90 s cooldown, minus the 0 s post-run wait, was slept via
    # the run wiring; the cooldown-less runs added no sleep.
    assert 90.0 in fake_env.sleeps
    # No manifest carries a skipped-cooldown deviation.
    for rid in SIM_RUN_IDS:
        kinds = {d["kind"] for d in _manifest(fake_env.base, rid)["deviations"]}
        assert "cooldown_skipped" not in kinds
        assert "cooldown_skipped_before_run" not in kinds


def test_campaign_no_cooldown_skips_sleep_and_records_deviation_on_following_run(
    plan_path, fake_env
) -> None:
    rc = campaign_mod.run_campaign(plan_path, no_cooldown=True, **fake_env.kwargs)
    assert rc == 0
    assert 90.0 not in fake_env.sleeps
    # The deviation lands on the FOLLOWING executed run (smoke-r02; the
    # external entry in between is not executed), not on smoke-r03.
    deviations = {
        rid: {d["kind"]: d for d in _manifest(fake_env.base, rid)["deviations"]}
        for rid in SIM_RUN_IDS
    }
    assert "cooldown_skipped" in deviations["smoke-r01"]  # run-level record
    following = deviations["smoke-r02"]["cooldown_skipped_before_run"]
    assert following["authorized_by_flag"] == "--no-cooldown"
    assert "smoke-r01" in following["detail"]
    assert "cooldown_skipped_before_run" not in deviations["smoke-r03"]
    # The deviation is recorded but does not invalidate the run.
    assert _manifest(fake_env.base, "smoke-r02")["validity"] == "valid"


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_cli_campaign_dry_run(plan_path, fake_env, capsys) -> None:
    rc = cli.main(
        [
            "campaign",
            "--plan",
            str(plan_path),
            "--results-dir",
            str(fake_env.base),
            "--only-conditions",
            "smoke_sequence,cold_start",
            "--no-tls",
            "--post-run-wait",
            "0",
            "--dry-run",
        ]
    )
    assert rc == 0
    assert fake_env.calls == []
    assert "DRY-RUN" in capsys.readouterr().out


def test_cli_campaign_parser_accepts_run_level_passthrough() -> None:
    args = cli.build_parser().parse_args(
        [
            "campaign",
            "--broker",
            "vm.local",
            "--controller-url",
            "http://127.0.0.1:8000",
            "--fetch-events-cmd",
            "scp vm:/opt/egw/data/events/{run_id}/events.jsonl {dest}",
            "--resources-from",
            "fetched/resources-{run_id}.csv",
            "--restart-cmd",
            "ssh vm restart-controller {run_id}",
            "--start-from",
            "nominal-r03",
            "--continue-on-invalid",
            "--no-cooldown",
        ]
    )
    assert args.broker == "vm.local"
    assert args.controller_url == "http://127.0.0.1:8000"
    assert "{run_id}" in args.resources_from
    assert args.start_from == "nominal-r03"
    assert args.continue_on_invalid is True
    assert args.no_cooldown is True
