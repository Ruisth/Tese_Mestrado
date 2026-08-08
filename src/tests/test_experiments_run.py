"""Tests for egw_experiments.run (audit 2026-08-08 section 9 corrections).

Covers the automated events fetch (command template with retries/backoff),
the two-environment ingestion and validity rules, the measured window, the
controller-restart hook, external-timings ingestion and the 'collect'
recovery subcommand. No broker, no docker, no network: the simulator
subprocess is replaced by a recorded fake, and fetch/restart commands are
real subprocesses running tiny recorded python scripts.
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

from egw_experiments import plan_gen
from egw_experiments import run as run_mod

PY = Path(sys.executable).as_posix()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def plan_path(tmp_path: Path) -> Path:
    path = tmp_path / "campaign_plan.json"
    plan_gen.write_campaign_plan(plan_gen.generate_campaign_plan(42), path)
    return path


@pytest.fixture
def fast_run(monkeypatch, tmp_path: Path):
    """Fake simulator subprocess + fast environment/commit capture.

    The fake honors the CONTRACTS 7 CLI shape (reads --output/--run-id from
    the argv built by _simulator_cmd) and writes a minimal sent_events.jsonl
    exactly where the real simulator would.
    """
    calls: list[list[str]] = []

    def fake_subprocess(cmd, log_path, timeout_s, _calls=calls):
        calls.append(list(cmd))
        out_dir = Path(cmd[cmd.index("--output") + 1])
        run_id = cmd[cmd.index("--run-id") + 1]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "sent_events.jsonl").write_text(
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
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_text("fake simulator\n", encoding="utf-8")
        sleep_s = getattr(fake_subprocess, "sleep_s", 0.0)
        if sleep_s:
            time.sleep(sleep_s)
        return getattr(fake_subprocess, "returncode", 0)

    monkeypatch.setattr(run_mod, "_run_subprocess", fake_subprocess)
    monkeypatch.setattr(
        run_mod,
        "write_loadgen_environment",
        lambda path: Path(path).write_text('{"role": "loadgen"}\n', "utf-8"),
    )
    monkeypatch.setattr(run_mod, "read_git_commit", lambda *a, **k: "test-commit")
    monkeypatch.setattr(run_mod, "FETCH_BACKOFF_BASE_S", 0.0)
    # Keep env-based configuration out of the tests unless set explicitly.
    monkeypatch.delenv(run_mod.FETCH_EVENTS_CMD_ENV, raising=False)
    monkeypatch.delenv(run_mod.SUT_ENV_FILE_ENV, raising=False)
    fake_subprocess.calls = calls
    return fake_subprocess


def _write_script(tmp_path: Path, name: str, body: str) -> Path:
    script = tmp_path / name
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return script


def _sut_env_file(tmp_path: Path) -> Path:
    path = tmp_path / "sut_environment.json"
    path.write_text(
        json.dumps({"role": "sut", "nproc": 4, "os_pretty_name": "fixture"}) + "\n",
        "utf-8",
    )
    return path


def _resources_file(tmp_path: Path) -> Path:
    path = tmp_path / "resources.csv"
    path.write_text(
        "ts_utc,container,cpu_pct,mem_bytes,mem_pct\n"
        "2026-09-07T10:00:00Z,egw-controller,10.0,1024,1.0\n",
        "utf-8",
    )
    return path


def _local_events(tmp_path: Path, run_id: str) -> Path:
    event_log_dir = tmp_path / "event-log"
    per_run = event_log_dir / run_id
    per_run.mkdir(parents=True)
    (per_run / "events.jsonl").write_text(
        json.dumps({"run_id": run_id, "outcome": "accepted"}) + "\n", "utf-8"
    )
    return event_log_dir


def _manifest(base: Path, run_id: str) -> dict:
    return json.loads(
        (base / "raw" / run_id / "manifest.json").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Fetch command template (audit 9.3)
# ---------------------------------------------------------------------------


def test_fetch_events_via_cmd_retries_backoff_and_placeholders(tmp_path) -> None:
    """The fetch template is invoked as a real subprocess with {run_id} and
    {dest} substituted; failures are retried 3 times with exponential
    backoff; every attempt is recorded."""
    script = _write_script(
        tmp_path,
        "fake_fetch.py",
        """\
        import sys
        from pathlib import Path
        record = Path(sys.argv[1])
        counter = record.with_suffix(".count")
        n = int(counter.read_text()) if counter.exists() else 0
        n += 1
        counter.write_text(str(n))
        with record.open("a", encoding="utf-8") as fh:
            fh.write(" ".join(sys.argv[2:]) + "\\n")
        if n < 3:
            sys.exit(1)  # fail the first two attempts
        Path(sys.argv[3]).write_text('{"outcome": "accepted"}\\n', encoding="utf-8")
        """,
    )
    record = tmp_path / "record.txt"
    dest = tmp_path / "events.jsonl"
    template = (
        f'"{PY}" "{script.as_posix()}" "{record.as_posix()}" {{run_id}} {{dest}}'
    )
    sleeps: list[float] = []
    ok, cmd_str, attempts = run_mod.fetch_events_via_cmd(
        template, "nominal-r01", dest, sleep=sleeps.append
    )
    assert ok is True
    assert dest.is_file()
    assert len(attempts) == 3
    assert attempts[0]["returncode"] == 1 and attempts[0]["dest_exists"] is False
    assert attempts[2]["returncode"] == 0 and attempts[2]["dest_exists"] is True
    # Exponential backoff: base * 2**(attempt-1) between attempts.
    assert sleeps == [run_mod.FETCH_BACKOFF_BASE_S, run_mod.FETCH_BACKOFF_BASE_S * 2]
    # Placeholders substituted literally in the executed command.
    assert "{run_id}" not in cmd_str and "{dest}" not in cmd_str
    assert "nominal-r01" in cmd_str
    # The recorded invocations saw the substituted run_id and dest path.
    lines = record.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        args = line.split()
        assert args[0] == "nominal-r01"
        assert Path(args[1]) == dest


def test_fetch_failure_keeps_run_recoverable_no_sha256sums(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    failing = f'"{PY}" -c "import sys; sys.exit(1)"'
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=tmp_path / "empty-event-log",
        fetch_events_cmd=failing,
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    assert rc == 1
    run_dir = base / "raw" / "smoke_sequence-r01"
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["events_source"] is None
    assert manifest["events_fetch"]["ok"] is False
    assert len(manifest["events_fetch"]["attempts"]) == run_mod.FETCH_ATTEMPTS
    # SHA256SUMS only after successful collection (audit 9.3).
    assert not (run_dir / "SHA256SUMS").exists()


def test_fetch_template_from_environment_variable(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    script = _write_script(
        tmp_path,
        "env_fetch.py",
        """\
        import sys
        from pathlib import Path
        Path(sys.argv[1]).write_text('{"outcome": "accepted"}\\n', encoding="utf-8")
        """,
    )
    template = f'"{PY}" "{script.as_posix()}" {{dest}}'
    monkeypatch.setenv(run_mod.FETCH_EVENTS_CMD_ENV, template)
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=tmp_path / "empty-event-log",
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["events_fetch"]["template"] == template
    assert manifest["events_source"].startswith("fetch-cmd:")
    assert (base / "raw" / "smoke_sequence-r01" / "events.jsonl").is_file()


# ---------------------------------------------------------------------------
# Validity rules (audit 9.1/9.2 - never warning-only)
# ---------------------------------------------------------------------------


def test_timed_run_without_sut_env_and_resources_is_invalid(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
    )
    assert rc == 1  # events collected, but the run is INVALID, not a warning
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "invalid"
    reasons = " ".join(manifest["validity_reasons"])
    assert "sut_environment.json" in reasons
    assert "SUT resources" in reasons or "resources" in reasons
    assert manifest["resource_source"] == "none"
    assert manifest["environment_refs"]["sut"] is None
    # Events WERE collected, so the evidence is sealed even though invalid.
    assert (base / "raw" / "smoke_sequence-r01" / "SHA256SUMS").is_file()
    # The plan tracks the failure.
    plan = plan_gen.load_campaign_plan(plan_path)
    entry = next(r for r in plan["runs"] if r["run_id"] == "smoke_sequence-r01")
    assert entry["status"] == "failed"
    assert entry["validity"] == "invalid"


def test_timed_run_with_ingested_sut_evidence_is_valid(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    assert rc == 0
    run_dir = base / "raw" / "smoke_sequence-r01"
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert manifest["validity_reasons"] == []
    assert manifest["resource_source"] == "sut-collector"
    # Two environments referenced by the manifest (audit 9.2).
    assert manifest["environment_refs"] == {
        "loadgen": "loadgen_environment.json",
        "sut": "sut_environment.json",
    }
    assert (run_dir / "sut_environment.json").is_file()
    assert (run_dir / "loadgen_environment.json").is_file()
    assert (run_dir / "resources.csv").is_file()
    # Measured window recorded (audit 9.4).
    window = manifest["measured_window_utc"]
    assert window["start"] <= window["end"]
    assert isinstance(manifest["measured_started_monotonic_ns"], int)
    assert "NTP" in manifest["measured_window_clock"]
    # SHA256SUMS covers the collected evidence.
    sums = (run_dir / "SHA256SUMS").read_text(encoding="utf-8")
    for name in ("events.jsonl", "sent_events.jsonl", "resources.csv",
                 "sut_environment.json", "loadgen_environment.json",
                 "manifest.json"):
        assert name in sums
    plan = plan_gen.load_campaign_plan(plan_path)
    entry = next(r for r in plan["runs"] if r["run_id"] == "smoke_sequence-r01")
    assert entry["status"] == "completed"


def test_allow_missing_flags_record_deliberate_decision(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        allow_missing_sut_env=True,
        allow_missing_resources=True,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert manifest["allow_missing_sut_env"] is True
    assert manifest["allow_missing_resources"] is True


def test_resources_from_and_local_resources_mutually_exclusive(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=tmp_path / "results",
        no_tls=True,
        resources_from=_resources_file(tmp_path),
        local_resources=True,
    )
    assert rc == 2
    assert "mutually exclusive" in capsys.readouterr().err
    assert not (tmp_path / "results").exists()


def test_existing_run_dir_refused_with_collect_hint(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    base = tmp_path / "results"
    (base / "raw" / "smoke_sequence-r01").mkdir(parents=True)
    rc = run_mod.execute_run(
        plan_path, "smoke_sequence-r01", base_dir=base, no_tls=True
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "already exists" in err
    assert "collect" in err


# ---------------------------------------------------------------------------
# Recovery: the collect subcommand (audit 9.3)
# ---------------------------------------------------------------------------


def test_collect_recovers_events_and_writes_sha256sums(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    run_id = "smoke_sequence-r01"
    # First execution: events collection fails (nothing local, no template).
    rc = run_mod.execute_run(
        plan_path,
        run_id,
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=tmp_path / "empty-event-log",
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    run_dir = base / "raw" / run_id
    assert rc == 1
    assert not (run_dir / "SHA256SUMS").exists()

    # Recovery re-attempts collection on the EXISTING directory instead of
    # refusing run_id reuse.
    script = _write_script(
        tmp_path,
        "late_fetch.py",
        """\
        import sys
        from pathlib import Path
        Path(sys.argv[1]).write_text('{"outcome": "accepted"}\\n', encoding="utf-8")
        """,
    )
    rc = run_mod.collect_run(
        run_id,
        base_dir=base,
        plan_path=plan_path,
        fetch_events_cmd=f'"{PY}" "{script.as_posix()}" {{dest}}',
        event_log_dir=tmp_path / "empty-event-log",
    )
    assert rc == 0
    assert (run_dir / "events.jsonl").is_file()
    sums = (run_dir / "SHA256SUMS").read_text(encoding="utf-8")
    assert "events.jsonl" in sums
    manifest = _manifest(base, run_id)
    assert manifest["validity"] == "valid"
    assert manifest["events_source"].startswith("fetch-cmd:")
    assert manifest["collect_history"], "collect must leave an audit trail"
    plan = plan_gen.load_campaign_plan(plan_path)
    entry = next(r for r in plan["runs"] if r["run_id"] == run_id)
    assert entry["status"] == "completed"


def test_collect_still_failing_withholds_sha256sums(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    run_id = "smoke_sequence-r01"
    run_mod.execute_run(
        plan_path,
        run_id,
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=tmp_path / "empty-event-log",
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    rc = run_mod.collect_run(
        run_id,
        base_dir=base,
        plan_path=plan_path,
        event_log_dir=tmp_path / "still-empty",
    )
    assert rc == 1
    assert not (base / "raw" / run_id / "SHA256SUMS").exists()


def test_collect_on_missing_run_dir_exits_2(tmp_path, plan_path, capsys) -> None:
    rc = run_mod.collect_run(
        "smoke_sequence-r09", base_dir=tmp_path / "results", plan_path=plan_path
    )
    assert rc == 2
    assert "only recovers runs already executed" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Controller restart hook (audit 9.5, claim C12)
# ---------------------------------------------------------------------------


def test_restart_cmd_executed_once_and_recorded(
    tmp_path, plan_path, fast_run
) -> None:
    marker = tmp_path / "restart-marker.txt"
    script = _write_script(
        tmp_path,
        "fake_restart.py",
        """\
        import sys
        from pathlib import Path
        Path(sys.argv[1]).write_text("restarted " + sys.argv[2], encoding="utf-8")
        """,
    )
    fast_run.sleep_s = 1.0  # keep the measured run alive while the timer fires
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "controller_restart-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "controller_restart-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
        restart_cmd=f'"{PY}" "{script.as_posix()}" "{marker.as_posix()}" {{run_id}}',
        restart_at_s=0.05,
    )
    assert rc == 0
    assert marker.read_text(encoding="utf-8") == "restarted controller_restart-r01"
    manifest = _manifest(base, "controller_restart-r01")
    restart = manifest["restart"]
    assert restart["executed"] is True
    assert restart["returncode"] == 0
    assert restart["requested_at_s"] == 0.05
    assert restart["started_utc"] and restart["finished_utc"]
    assert manifest["validity"] == "valid"


def test_controller_restart_run_without_fired_restart_is_invalid(
    tmp_path, plan_path, fast_run
) -> None:
    # The measured (fake) run ends before the timer fires: no restart
    # happened, so the run cannot evidence claim C12 and is invalid.
    fast_run.sleep_s = 0.0
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "controller_restart-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "controller_restart-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
        restart_cmd=f'"{PY}" -c "pass"',
        restart_at_s=60.0,
    )
    assert rc == 1
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["validity"] == "invalid"
    assert any("restart" in reason for reason in manifest["validity_reasons"])
    assert manifest["restart"]["executed"] is False
    assert any("restart" in w for w in manifest["warnings"])


# ---------------------------------------------------------------------------
# External conditions ingestion (audit 9.6, claim C15)
# ---------------------------------------------------------------------------


def _timings_file(tmp_path: Path, run_id: str, condition: str) -> Path:
    path = tmp_path / f"timings-{run_id}.json"
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "condition": condition,
                "samples": [
                    {
                        "label": run_id,
                        "started_utc": "2026-09-07T10:00:00Z",
                        "ended_utc": "2026-09-07T10:00:42Z",
                        "duration_s": 42,
                    }
                ],
                "method": "deployment/scripts/measure-cold-start.sh",
                "notes": "fixture",
            }
        )
        + "\n",
        "utf-8",
    )
    return path


def test_external_run_ingested_with_standard_manifest_and_sums(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "cold_start-r01",
        base_dir=base,
        external_timings=_timings_file(tmp_path, "cold_start-r01", "cold_start"),
        sut_env_from=_sut_env_file(tmp_path),
    )
    assert rc == 0
    run_dir = base / "raw" / "cold_start-r01"
    assert (run_dir / "timings.json").is_file()
    manifest = _manifest(base, "cold_start-r01")
    assert manifest["runner"] == "external"
    assert manifest["condition_id"] == "cold_start"
    assert manifest["external_sample_count"] == 1
    assert manifest["validity"] == "valid"
    sums = (run_dir / "SHA256SUMS").read_text(encoding="utf-8")
    assert "timings.json" in sums
    plan = plan_gen.load_campaign_plan(plan_path)
    entry = next(r for r in plan["runs"] if r["run_id"] == "cold_start-r01")
    assert entry["status"] == "completed"
    # The fake simulator must never have been invoked for an external run.
    assert fast_run.calls == []


def test_external_run_id_mismatch_rejected(tmp_path, plan_path, fast_run, capsys) -> None:
    rc = run_mod.execute_run(
        plan_path,
        "cold_start-r02",
        base_dir=tmp_path / "results",
        external_timings=_timings_file(tmp_path, "cold_start-r01", "cold_start"),
    )
    assert rc == 2
    assert "does not match" in capsys.readouterr().err


def test_qemu_boot_run_accepts_singular_condition_prefix(
    tmp_path, plan_path, fast_run
) -> None:
    # Plan condition 'qemu_boots' enumerates run_ids 'qemu_boot-rNN'; the
    # operator's timings may say 'qemu_boot' (the run-id prefix).
    rc = run_mod.execute_run(
        plan_path,
        "qemu_boot-r01",
        base_dir=tmp_path / "results",
        external_timings=_timings_file(tmp_path, "qemu_boot-r01", "qemu_boot"),
    )
    assert rc == 0


def test_external_timings_on_simulator_run_rejected(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    rc = run_mod.execute_run(
        plan_path,
        "nominal-r01",
        base_dir=tmp_path / "results",
        external_timings=_timings_file(tmp_path, "nominal-r01", "nominal"),
    )
    assert rc == 2
    assert "only valid for external conditions" in capsys.readouterr().err


def test_load_external_timings_validates_structure(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"run_id": "x", "condition": "cold_start"}), "utf-8")
    with pytest.raises(ValueError, match="samples"):
        run_mod.load_external_timings(bad)
    bad.write_text(
        json.dumps(
            {
                "run_id": "x",
                "condition": "cold_start",
                "samples": [{"label": "a", "duration_s": -1}],
            }
        ),
        "utf-8",
    )
    with pytest.raises(ValueError, match="duration_s"):
        run_mod.load_external_timings(bad)


# ---------------------------------------------------------------------------
# Warm-up runs under a distinct run_id (measured events uncontaminated)
# ---------------------------------------------------------------------------


def test_warmup_uses_distinct_run_id_and_same_seed(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "nominal-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "nominal-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    assert rc == 0
    assert len(fast_run.calls) == 2  # warm-up + measured
    warmup_cmd, measured_cmd = fast_run.calls

    def _arg(cmd: list[str], flag: str) -> str:
        return cmd[cmd.index(flag) + 1]

    assert _arg(warmup_cmd, "--run-id") == "nominal-r01.warmup"
    assert _arg(measured_cmd, "--run-id") == "nominal-r01"
    # Warm-up reuses the run's seed (same device_uuids warm the real twins).
    assert _arg(warmup_cmd, "--seed") == _arg(measured_cmd, "--seed")
    assert _arg(warmup_cmd, "--duration") == "120"
    assert _arg(measured_cmd, "--duration") == "600"
