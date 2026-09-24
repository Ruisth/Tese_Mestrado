"""Tests for egw_experiments.campaign (work order P1 item 12).

A tiny synthetic plan (three simulator runs + one external condition, one
cooldown) is driven end-to-end with the fake simulator subprocess. No
broker, no docker, no network; time.sleep is recorded, never slept.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from egw_experiments import campaign as campaign_mod
from egw_experiments import cli
from egw_experiments import run as run_mod

SUT_NODE = "sut-vm"
RESOURCES_HEADER = "ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"

SIM_RUN_IDS = ["smoke-r01", "smoke-r02", "smoke-r03"]
#: The one service of the per-run resources fixtures (--expect-services).
FIXTURE_SERVICES = ["egw-controller"]
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
    # Align the real measured_window_utc bounds with the fixed resources CSVs.
    # Every call advances so start/end are ordered while all three synthetic
    # runs remain within the fixture's 40-second sample interval.
    utc_tick = 0

    def fake_utc_now_iso() -> str:
        nonlocal utc_tick
        stamp = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc) + timedelta(
            milliseconds=100 * utc_tick
        )
        utc_tick += 1
        return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    monkeypatch.setattr(run_mod, "utc_now_iso", fake_utc_now_iso)
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

    # Per-run SUT resources, addressed by a {run_id} template, each with the
    # collector's companions beside it: the manual path is accounted for
    # like the fetch hook's output (manifest 1.4).
    for rid in SIM_RUN_IDS:
        lines = [RESOURCES_HEADER]
        for i in range(40):
            lines.append(
                f"2026-09-07T10:00:{i % 60:02d}Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
            )
        csv_path = tmp_path / f"resources-{rid}.csv"
        csv_path.write_text("\n".join(lines) + "\n", "utf-8")
        Path(f"{csv_path}.diagnostics.log").write_text(
            f"2026-09-07T09:59:59Z start: collector_sha256={'cd' * 32} "
            "host=sut-vm interval=1s duration=42s; expected services: "
            "egw-controller\n"
            "2026-09-07T10:00:41Z inventory: observed=egw-controller "
            "expected=egw-controller missing=none unnamed_ids=0\n"
            "2026-09-07T10:00:41Z stop: samples=41 utc_gap_seconds=0 "
            "withheld_samples=0 withheld_elapsed_s=0.00 "
            "withheld_runs_unmeasured=0 withheld_open_at_stop=0 "
            "calibrations=1 pacing=wall-clock\n",
            "utf-8",
        )
        Path(f"{csv_path}.lifecycle.csv").write_text(
            "ts_utc,event,container_id,name\n", "utf-8"
        )

    base = tmp_path / "results"
    kwargs = dict(
        results_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=event_log_dir,
        sut_env_from=sut_env,
        resources_from=(tmp_path / "resources-{run_id}.csv").as_posix(),
        expect_services=FIXTURE_SERVICES,
        # No controller is reachable in a unit test, so the run end cannot
        # be stamped in the controller's clock domain (sprint P5, report
        # 5.2). The campaign tests are about batch behaviour, so the
        # absence is authorized explicitly and recorded as a deviation.
        allow_missing_controller_marker=True,
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
    # Exit 1, not 0: every simulator run completed, but this FULL campaign
    # still has an external condition without evidence (sprint P5, report
    # 5.4 "Condições externas não impedem exit 0").
    assert rc == 1
    # Frozen order preserved; the external run is never executed.
    assert _executed_run_ids(fake_env.calls) == SIM_RUN_IDS
    lines = _log_lines(fake_env.base)
    assert [line["run_id"] for line in lines] == PLAN_ORDER
    assert [line["outcome"] for line in lines] == [
        "completed",
        "incomplete",
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
    captured = capsys.readouterr()
    out = captured.out
    assert f"INCOMPLETE {EXTERNAL_RUN_ID}" in out
    # The final summary names every pending external run.
    assert EXTERNAL_RUN_ID in captured.err
    assert "INCOMPLETE" in out
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
    # rc 1 on both passes: the external condition stays pending throughout.
    assert campaign_mod.run_campaign(plan_path, **fake_env.kwargs) == 1
    first_round_calls = len(fake_env.calls)
    capsys.readouterr()

    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 1
    # Nothing re-executed: every simulator run is sealed AND valid.
    assert len(fake_env.calls) == first_round_calls
    lines = _log_lines(fake_env.base)[-4:]
    assert [line["outcome"] for line in lines] == [
        "skipped",
        "incomplete",
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
    # Exit 1: the selection resumes correctly, but the external run earlier
    # in the frozen order was skipped and still owes its evidence (P5.4
    # defect 6) - only the SELECTION is what this test asserts.
    assert rc == 1
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


def test_campaign_accounts_for_each_resources_from_file_like_the_fetch_hook(
    plan_path, fake_env
) -> None:
    """The per-run --resources-from file (the manual path) and its
    companions are copied, inspected against --expect-services and sealed."""
    rc = campaign_mod.run_campaign(
        plan_path, only_conditions=["smoke_sequence"], **fake_env.kwargs
    )
    assert rc == 0
    for rid in SIM_RUN_IDS:
        collector = _manifest(fake_env.base, rid)["collector"]
        assert collector["source"] == "--resources-from"
        assert collector["source_path"] == (
            fake_env.tmp_path / f"resources-{rid}.csv"
        ).as_posix()
        assert collector["expected_services"] == FIXTURE_SERVICES
        assert collector["problems"] == []
        kept = (
            fake_env.base / "raw" / rid / "logs" / "collector" / "resources-from"
        )
        assert (kept / f"resources-{rid}.csv.diagnostics.log").is_file()


def test_campaign_resources_from_without_expect_services_is_invalid(
    plan_path, fake_env
) -> None:
    kwargs = dict(fake_env.kwargs)
    kwargs.pop("expect_services")
    rc = campaign_mod.run_campaign(
        plan_path, only_conditions=["smoke_sequence"], **kwargs
    )
    assert rc == 1
    manifest = _manifest(fake_env.base, "smoke-r01")
    assert manifest["validity"] == "invalid"
    assert "--expect-services was not given" in " ".join(
        manifest["validity_reasons"]
    )


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
        "incomplete",
        "completed",
        "completed",
    ]


# ---------------------------------------------------------------------------
# Cooldown handling
# ---------------------------------------------------------------------------


def test_campaign_honors_plan_cooldown(plan_path, fake_env) -> None:
    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 1  # every simulator run clean; the external one is pending
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
    assert rc == 1  # every simulator run clean; the external one is pending
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
# P5.1 item 2 (report 5.3): the campaign drives the SUT collector itself
# ---------------------------------------------------------------------------


#: The six Compose container names of the gateway stack (runbook 6.1).
SIX_SERVICES = [
    "egw-mosquitto-1",
    "egw-mongodb-1",
    "egw-ditto-policies-1",
    "egw-ditto-things-1",
    "egw-ditto-gateway-1",
    "egw-controller-1",
]

# The fetch hook writes what collect-resources.sh leaves beside its CSV: the
# CSV (40 instants of every service in {expect_services}), the diagnostics
# with a start line declaring that list, a clean inventory and the closing
# summary, and the lifecycle file.
HOOK_SCRIPT = """\
import sys
from pathlib import Path

record, label, run_id, duration_s, dest, mode, rc, expect = sys.argv[1:9]
with Path(record).open("a", encoding="utf-8") as fh:
    fh.write(" ".join((label, run_id, duration_s, expect or "-")) + "\\n")
if mode == "write":
    services = expect.split(",") if expect else ["egw-controller"]
    rows = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"]
    for i in range(40):
        for name in services:
            rows.append(
                "2026-09-07T10:00:%02dZ,%s,10.0,1024,1.0,sut-vm" % (i, name)
            )
    Path(dest).write_text("\\n".join(rows) + "\\n", encoding="utf-8")
    Path(dest + ".diagnostics.log").write_text(
        "2026-09-07T09:59:59Z start: collector_sha256=" + "ab" * 32
        + " host=sut-vm interval=1s duration=42s; expected services: "
        + (expect or "none declared") + "\\n"
        + "2026-09-07T10:00:41Z inventory: observed=" + ",".join(sorted(services))
        + " expected=" + (expect or "none-declared") + " missing=none unnamed_ids=0\\n"
        + "2026-09-07T10:00:41Z stop: samples=41 utc_gap_seconds=0 "
        + "withheld_samples=0 withheld_elapsed_s=0.00 "
        + "withheld_runs_unmeasured=0 withheld_open_at_stop=0 "
        + "calibrations=1 pacing=wall-clock\\n",
        encoding="utf-8",
    )
    Path(dest + ".lifecycle.csv").write_text(
        "ts_utc,event,container_id,name\\n", encoding="utf-8"
    )
sys.exit(int(rc))
"""


def _hook_templates(tmp_path: Path, *, fetch_rc: int = 0):
    """(record_path, {collector_*_cmd kwargs}) for the three campaign hooks."""
    script = tmp_path / "collector_hook.py"
    script.write_text(HOOK_SCRIPT, encoding="utf-8")
    record = tmp_path / "campaign-hooks.txt"
    py = Path(sys.executable).as_posix()

    def tpl(label: str, mode: str, rc: int) -> str:
        return (
            f'"{py}" "{script.as_posix()}" "{record.as_posix()}" {label} '
            '{run_id} {duration_s} "{dest}" ' + f"{mode} {rc}"
            + ' "{expect_services}"'
        )

    return record, dict(
        collector_start_cmd=tpl("start", "noop", 0),
        collector_stop_cmd=tpl("stop", "noop", 0),
        collector_fetch_cmd=tpl("fetch", "write", fetch_rc),
        expect_services=SIX_SERVICES,
    )


def test_campaign_drives_the_collector_hooks_per_run(
    plan_path, fake_env, tmp_path
) -> None:
    """A FRESH campaign produces its own resources.csv: the hooks are
    executed per run, in order, and the fetched CSV goes through the normal
    validated ingest (report 5.3 — a --resources-from template pointing at a
    file that must already exist is not end-to-end)."""
    record, hooks = _hook_templates(tmp_path)
    kwargs = dict(fake_env.kwargs)
    kwargs.pop("resources_from")  # nothing pre-fetched exists
    kwargs.pop("expect_services")  # the hooks carry their own list
    rc = campaign_mod.run_campaign(
        plan_path, only_conditions=["smoke_sequence"], **kwargs, **hooks
    )
    assert rc == 0
    labels = [
        line.split()
        for line in record.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # Three hooks per simulator run, in order, each seeing its own run_id
    # and the --expect-services list passed through by the campaign.
    assert [entry[0] for entry in labels] == ["start", "stop", "fetch"] * 3
    assert [entry[1] for entry in labels[:3]] == ["smoke-r01"] * 3
    assert {entry[3] for entry in labels} == {",".join(SIX_SERVICES)}
    for rid in SIM_RUN_IDS:
        manifest = _manifest(fake_env.base, rid)
        assert [h["hook"] for h in manifest["collector_hooks"]] == [
            "start",
            "stop",
            "fetch",
        ]
        assert all(h["returncode"] == 0 for h in manifest["collector_hooks"])
        assert manifest["resource_source"] == "sut-collector"
        assert manifest["validity"] == "valid"
        assert (fake_env.base / "raw" / rid / "resources.csv").is_file()
        collector = manifest["collector"]
        assert collector["expected_services"] == SIX_SERVICES
        assert collector["problems"] == []
        assert collector["rows_per_expected_service"] == {
            name: 40 for name in SIX_SERVICES
        }
        collector_dir = fake_env.base / "raw" / rid / "logs" / "collector"
        assert (collector_dir / f"resources-{rid}.csv.diagnostics.log").is_file()
        assert (collector_dir / f"resources-{rid}.csv.lifecycle.csv").is_file()


def test_campaign_without_expect_services_marks_hooked_runs_invalid(
    plan_path, fake_env, tmp_path
) -> None:
    """The expected services are data the campaign must pass on: hooks
    without them never report complete collection."""
    _record, hooks = _hook_templates(tmp_path)
    hooks.pop("expect_services")
    kwargs = dict(fake_env.kwargs)
    kwargs.pop("resources_from")
    kwargs.pop("expect_services")
    rc = campaign_mod.run_campaign(
        plan_path, only_conditions=["smoke_sequence"], **kwargs, **hooks
    )
    assert rc == 1
    manifest = _manifest(fake_env.base, "smoke-r01")
    assert manifest["validity"] == "invalid"
    assert "--expect-services was not given" in " ".join(manifest["validity_reasons"])


def test_campaign_stops_when_a_collector_hook_fails(
    plan_path, fake_env, tmp_path, capsys
) -> None:
    record, hooks = _hook_templates(tmp_path, fetch_rc=4)
    kwargs = dict(fake_env.kwargs)
    kwargs.pop("resources_from")
    kwargs.pop("expect_services")
    rc = campaign_mod.run_campaign(
        plan_path, only_conditions=["smoke_sequence"], **kwargs, **hooks
    )
    assert rc == 1
    assert _executed_run_ids(fake_env.calls) == ["smoke-r01"]
    manifest = _manifest(fake_env.base, "smoke-r01")
    assert manifest["validity"] == "invalid"
    reasons = " ".join(manifest["validity_reasons"])
    assert "--collector-fetch-cmd" in reasons
    assert "exit code 4" in reasons
    assert "stopping at smoke-r01" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# P5.1 item 4 (report 5.4): resume verifies integrity, never only presence
# ---------------------------------------------------------------------------


def test_campaign_resume_verifies_checksums_before_skipping(
    plan_path, fake_env, capsys
) -> None:
    """A sealed+valid run whose evidence was altered after sealing must
    never be silently skipped and then analysed."""
    assert campaign_mod.run_campaign(plan_path, **fake_env.kwargs) == 1
    calls_before = len(fake_env.calls)
    tampered = fake_env.base / "raw" / "smoke-r02" / "events.jsonl"
    tampered.write_text('{"outcome": "tampered"}\n', encoding="utf-8")
    capsys.readouterr()

    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 2
    # Aborted at the tampered run: nothing re-executed, nothing skipped past.
    assert len(fake_env.calls) == calls_before
    err = capsys.readouterr().err
    assert "smoke-r02" in err
    assert "SHA256SUMS" in err
    assert "mismatch: events.jsonl" in err
    entry = _log_lines(fake_env.base)[-1]
    assert entry["run_id"] == "smoke-r02"
    assert entry["outcome"] == "integrity-failed"


def test_campaign_resume_integrity_failure_ignores_continue_on_invalid(
    plan_path, fake_env, capsys
) -> None:
    assert campaign_mod.run_campaign(plan_path, **fake_env.kwargs) == 1
    (fake_env.base / "raw" / "smoke-r01" / "resources.csv").write_text(
        "tampered\n", encoding="utf-8"
    )
    capsys.readouterr()
    rc = campaign_mod.run_campaign(
        plan_path, continue_on_invalid=True, **fake_env.kwargs
    )
    assert rc == 2
    assert "mismatch: resources.csv" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# P5.1 item 6 (report 5.4): pending external runs make a full campaign
# INCOMPLETE, never exit 0
# ---------------------------------------------------------------------------


def _ingest_external(plan_path: Path, fake_env, tmp_path: Path) -> None:
    timings = tmp_path / f"timings-{EXTERNAL_RUN_ID}.json"
    timings.write_text(
        json.dumps(
            {
                "run_id": EXTERNAL_RUN_ID,
                "condition": "cold_start",
                "samples": [
                    {
                        "label": EXTERNAL_RUN_ID,
                        "started_utc": "2026-09-07T10:00:00Z",
                        "ended_utc": "2026-09-07T10:00:42Z",
                        "duration_s": 42,
                    }
                ],
                "method": "fixture",
            }
        )
        + "\n",
        "utf-8",
    )
    assert (
        run_mod.execute_run(
            plan_path,
            EXTERNAL_RUN_ID,
            base_dir=fake_env.base,
            external_timings=timings,
        )
        == 0
    )


def test_full_campaign_with_pending_external_runs_exits_1(
    plan_path, fake_env, capsys
) -> None:
    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 1
    captured = capsys.readouterr()
    assert "1 external run(s) still pending" in captured.err
    assert EXTERNAL_RUN_ID in captured.err
    assert "--external-timings" in captured.err
    assert "done: INCOMPLETE" in captured.out
    # Every simulator run itself was clean: only the missing external
    # evidence makes the campaign incomplete.
    for rid in SIM_RUN_IDS:
        assert _manifest(fake_env.base, rid)["validity"] == "valid"


def test_filtered_campaign_may_exit_0_while_stating_what_remains(
    plan_path, fake_env, capsys
) -> None:
    rc = campaign_mod.run_campaign(
        plan_path, only_conditions=["smoke_sequence"], **fake_env.kwargs
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "done: clean" in out
    # The external condition was filtered out, so it is not even visited.
    assert EXTERNAL_RUN_ID not in [
        line["run_id"] for line in _log_lines(fake_env.base)
    ]


# ---------------------------------------------------------------------------
# P5.4 defect 6: --start-from must not silently discharge owed external
# evidence - the accounting covers the WHOLE plan, not the selected slice
# ---------------------------------------------------------------------------


def test_start_from_does_not_discharge_the_external_runs_it_skips(
    plan_path, fake_env, capsys
) -> None:
    """cold-r01 sits BEFORE smoke-r02 in the frozen order: resuming past it
    leaves its evidence unproduced, so the campaign is INCOMPLETE."""
    rc = campaign_mod.run_campaign(
        plan_path, start_from="smoke-r02", **fake_env.kwargs
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert "1 external run(s) still pending" in captured.err
    assert EXTERNAL_RUN_ID in captured.err
    assert "--start-from" in captured.err
    assert "done: INCOMPLETE" in captured.out
    # The skipped external run is NOT visited: it is accounted for, not
    # re-classified or logged as if the campaign had reached it.
    assert EXTERNAL_RUN_ID not in [
        line["run_id"] for line in _log_lines(fake_env.base)
    ]


def test_start_from_is_clean_once_the_skipped_external_evidence_is_sealed(
    plan_path, fake_env, tmp_path, capsys
) -> None:
    """Only runs that are NOT sealed-and-valid stay owed."""
    _ingest_external(plan_path, fake_env, tmp_path)
    capsys.readouterr()
    rc = campaign_mod.run_campaign(
        plan_path, start_from="smoke-r02", **fake_env.kwargs
    )
    assert rc == 0
    assert "done: clean" in capsys.readouterr().out


def test_blocked_run_guidance_does_not_imply_start_from_discharges_the_work(
    plan_path, fake_env, capsys
) -> None:
    (fake_env.base / "raw" / "smoke-r01").mkdir(parents=True)
    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 1
    err = capsys.readouterr().err
    assert "stopping at smoke-r01" in err
    assert "--start-from" in err
    assert "still owe their evidence" in err


def test_campaign_is_clean_once_the_external_evidence_is_ingested(
    plan_path, fake_env, tmp_path, capsys
) -> None:
    assert campaign_mod.run_campaign(plan_path, **fake_env.kwargs) == 1
    _ingest_external(plan_path, fake_env, tmp_path)
    capsys.readouterr()

    rc = campaign_mod.run_campaign(plan_path, **fake_env.kwargs)
    assert rc == 0
    outcomes = [line["outcome"] for line in _log_lines(fake_env.base)[-4:]]
    assert outcomes == ["skipped", "skipped", "skipped", "skipped"]
    assert "done: clean" in capsys.readouterr().out


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


# ---------------------------------------------------------------------------
# ADR 0011 item 18: the log fetches and the configuration identity reach
# every run; the drain, the twin snapshots and the post-drain fetch only the
# controller_restart runs (as --restart-cmd does)
# ---------------------------------------------------------------------------


RESTART_RUN_ID = "restart-r01"

ITEM18_RUN_FLAGS = {
    "fetch_broker_log_cmd": "broker {run_id} {dest}",
    "fetch_controller_log_cmd": "controller {run_id} {dest}",
    "fetch_docker_events_cmd": "events {run_id} {dest}",
}

ITEM18_RESTART_FLAGS = {
    "twin_snapshot_cmd": "snap {run_id} {dest}",
    "drain_cmd": "drain {run_id}",
    "post_drain_fetch_cmd": "post {run_id} {dest}",
    "restart_cmd": "restart {run_id}",
    "restart_at_s": 15.0,
}


def _add_restart_entry(plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    entry = _sim_entry(RESTART_RUN_ID, 5, cooldown_s=0)
    entry["condition_id"] = campaign_mod.RESTART_CONDITION_ID
    entry["scenario"] = "nominal"
    plan["runs"].append(entry)
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", "utf-8")


def test_campaign_passes_the_item_18_flags_and_gates_the_restart_steps(
    plan_path, fake_env, tmp_path, monkeypatch
) -> None:
    _add_restart_entry(plan_path)
    seen: dict[str, dict] = {}

    def fake_execute_run(plan_path_, run_id, **kwargs):
        seen[run_id] = kwargs
        return 0

    monkeypatch.setattr(campaign_mod, "execute_run", fake_execute_run)
    identity_template = (tmp_path / "identity-{run_id}.json").as_posix()
    rc = campaign_mod.run_campaign(
        plan_path,
        **fake_env.kwargs,
        only_conditions=["smoke_sequence", campaign_mod.RESTART_CONDITION_ID],
        config_identity_from=identity_template,
        **ITEM18_RUN_FLAGS,
        **ITEM18_RESTART_FLAGS,
    )
    assert rc == 0
    assert set(seen) == {*SIM_RUN_IDS, RESTART_RUN_ID}
    for run_id, kwargs in seen.items():
        for key, value in ITEM18_RUN_FLAGS.items():
            assert kwargs[key] == value, (run_id, key)
        # The identity file may be addressed per run, like --resources-from.
        assert kwargs["config_identity_from"] == (
            tmp_path / f"identity-{run_id}.json"
        ).as_posix()
        restart = run_id == RESTART_RUN_ID
        for key, value in ITEM18_RESTART_FLAGS.items():
            assert kwargs[key] == (value if restart else None), (run_id, key)


def test_cli_campaign_passes_the_item_18_flags_through(monkeypatch) -> None:
    seen: dict = {}

    def fake_run_campaign(plan_path, **kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(cli, "run_campaign", fake_run_campaign)
    rc = cli.main(
        [
            "campaign",
            "--fetch-broker-log-cmd",
            "broker {dest}",
            "--fetch-controller-log-cmd",
            "controller {dest}",
            "--fetch-docker-events-cmd",
            "events {dest}",
            "--twin-snapshot-cmd",
            "snap {dest}",
            "--drain-cmd",
            "drain {run_id}",
            "--post-drain-fetch-cmd",
            "post {dest}",
            "--config-identity-from",
            "identity-{run_id}.json",
        ]
    )
    assert rc == 0
    assert seen["fetch_broker_log_cmd"] == "broker {dest}"
    assert seen["fetch_controller_log_cmd"] == "controller {dest}"
    assert seen["fetch_docker_events_cmd"] == "events {dest}"
    assert seen["twin_snapshot_cmd"] == "snap {dest}"
    assert seen["drain_cmd"] == "drain {run_id}"
    assert seen["post_drain_fetch_cmd"] == "post {dest}"
    assert seen["config_identity_from"] == "identity-{run_id}.json"
