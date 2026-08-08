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

from egw_experiments import checksums, plan_gen
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
    the argv built by _simulator_cmd) and reproduces the REAL simulator
    output layout: egw_simulator.runner writes manifest.json and
    sent_events.jsonl under ``<output>/<run_id>/`` (deliberately hardcoded
    here as ``out_dir / run_id``, mirroring the runner, so a harness-side
    layout regression cannot hide behind a shared helper — P1c fix F0).
    """
    calls: list[list[str]] = []

    def fake_subprocess(cmd, log_path, timeout_s, _calls=calls):
        calls.append(list(cmd))
        out_dir = Path(cmd[cmd.index("--output") + 1])
        run_id = cmd[cmd.index("--run-id") + 1]
        # REAL layout (egw_simulator/runner.py): <output_dir>/<run_id>/.
        sim_run_dir = out_dir / run_id
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
            json.dumps(
                {
                    "run_id": run_id,
                    "totals": {
                        "sent": 1,
                        "intended_invalid": 0,
                        "buffered_dropout": 0,
                        "dropout_disconnects": 0,
                    },
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
        # Per-call exit codes (e.g. warm-up fails, measured run succeeds):
        # pop from 'returncodes' when set; else the scalar 'returncode'.
        rc_list = getattr(fake_subprocess, "returncodes", None)
        if rc_list:
            return rc_list.pop(0)
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


SUT_NODE = "sut-vm"

RESOURCES_HEADER = "ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"


def _sut_env_file(tmp_path: Path, **overrides) -> Path:
    """A sut_environment.json satisfying REQUIRED_SUT_FIELDS (fix 4)."""
    env = {
        "role": "sut",
        "node": SUT_NODE,
        "nproc": 4,
        "uname_a": "Linux sut-vm 6.8.0 aarch64",
        "os_pretty_name": "fixture",
    }
    env.update(overrides)
    env = {k: v for k, v in env.items() if v is not None}
    path = tmp_path / "sut_environment.json"
    path.write_text(json.dumps(env) + "\n", "utf-8")
    return path


def _resources_file(
    tmp_path: Path,
    *,
    rows: int = 40,
    host: str = SUT_NODE,
    header: str = RESOURCES_HEADER,
    name: str = "resources.csv",
) -> Path:
    """A SUT collector resources.csv passing the ingest validation (fix 3):
    exact 6-column header with host provenance, >= MIN_RESOURCE_SAMPLES
    rows, every host equal to the SUT node."""
    path = tmp_path / name
    lines = [header]
    for i in range(rows):
        lines.append(
            f"2026-09-07T10:00:{i % 60:02d}Z,egw-controller,10.0,1024,1.0,{host}"
        )
    path.write_text("\n".join(lines) + "\n", "utf-8")
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
    # Work order P1 fix 5: the overrides are valid ONLY together with an
    # explicit deviation record in the manifest.
    kinds = {d["kind"]: d for d in manifest["deviations"]}
    assert (
        kinds["missing_sut_environment"]["authorized_by_flag"]
        == "--allow-missing-sut-env"
    )
    assert (
        kinds["missing_sut_resources"]["authorized_by_flag"]
        == "--allow-missing-resources"
    )


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
# Work order P1: resources ingest validation, SUT-env quality, protocol
# deviations and exit-code validity rules
# ---------------------------------------------------------------------------


class _StubSampler:
    """Replacement for ResourceSampler: no docker, header-only CSV."""

    def __init__(self, csv_path, *args, **kwargs) -> None:
        self.csv_path = Path(csv_path)
        self.error = None
        self.samples_written = 0

    def __enter__(self) -> "_StubSampler":
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.csv_path.write_text(RESOURCES_HEADER + "\n", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_ingest_resources_validation_rejects_bad_files(tmp_path) -> None:
    """Run-time ingest accepts only a content-valid SUT collector CSV:
    presence alone is never evidence (work order P1 fix 3)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "sut_environment.json").write_text(
        json.dumps({"node": SUT_NODE, "nproc": 4, "uname_a": "Linux sut-vm"})
        + "\n",
        "utf-8",
    )

    def attempt(source):
        warnings: list[str] = []
        ok = run_mod.ingest_resources(run_dir, source, warnings)
        return ok, " ".join(warnings)

    # Missing file.
    ok, msg = attempt(tmp_path / "nope.csv")
    assert ok is False and "not found" in msg
    assert not (run_dir / "resources.csv").exists()

    # Entirely empty file.
    empty = tmp_path / "empty.csv"
    empty.write_text("", "utf-8")
    ok, msg = attempt(empty)
    assert ok is False and "REJECTED" in msg

    # Header-only file.
    header_only = tmp_path / "header-only.csv"
    header_only.write_text(RESOURCES_HEADER + "\n", "utf-8")
    ok, msg = attempt(header_only)
    assert ok is False and "no data rows" in msg

    # Wrong header: the legacy 5-column schema is not ingestible (the
    # analysis still READS it for old fixtures, see analyze tests).
    legacy = tmp_path / "legacy.csv"
    legacy.write_text(
        "ts_utc,container,cpu_pct,mem_bytes,mem_pct\n"
        + "2026-09-07T10:00:00Z,egw-controller,10.0,1024,1.0\n" * 40,
        "utf-8",
    )
    ok, msg = attempt(legacy)
    assert ok is False and "header" in msg

    # Too few samples.
    short = _resources_file(tmp_path, rows=5, name="short.csv")
    ok, msg = attempt(short)
    assert ok is False and "MIN_RESOURCE_SAMPLES" in msg

    # Host mismatch against sut_environment.json's node.
    wrong_host = _resources_file(
        tmp_path, host="loadgen-laptop", name="wrong-host.csv"
    )
    ok, msg = attempt(wrong_host)
    assert ok is False and "do not match" in msg
    assert not (run_dir / "resources.csv").exists()

    # A valid file is copied into the run dir.
    ok, msg = attempt(_resources_file(tmp_path))
    assert ok is True
    assert (run_dir / "resources.csv").is_file()


def test_ingest_resources_without_sut_node_skips_host_match(tmp_path) -> None:
    """The host equality check applies only when sut_environment.json
    provides a node/hostname (work order P1 fix 3)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    warnings: list[str] = []
    src = _resources_file(tmp_path, host="whatever-host")
    assert run_mod.ingest_resources(run_dir, src, warnings) is True
    assert warnings == []


def test_local_resources_timed_run_is_invalid(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """--local-resources samples the load generator (dev only): a timed run
    with resource_source 'local-dev' is INVALID without an override
    (work order P1 fix 2)."""
    monkeypatch.setattr(run_mod, "ResourceSampler", _StubSampler)
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        local_resources=True,
    )
    assert rc == 1
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["resource_source"] == "local-dev"
    assert manifest["validity"] == "invalid"
    reasons = " ".join(manifest["validity_reasons"])
    assert "local-dev" in reasons
    assert "LOAD GENERATOR" in reasons


def test_local_resources_with_override_is_valid_and_recorded(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """--allow-missing-resources keeps a local-dev timed run valid ONLY
    together with the recorded override deviation (fixes 2+5); the
    analysis still surfaces the wrong provenance per run."""
    from egw_experiments import analyze as analyze_mod

    monkeypatch.setattr(run_mod, "ResourceSampler", _StubSampler)
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        local_resources=True,
        allow_missing_resources=True,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert manifest["resource_source"] == "local-dev"
    deviation = next(
        d for d in manifest["deviations"] if d["kind"] == "missing_sut_resources"
    )
    assert deviation["authorized_by_flag"] == "--allow-missing-resources"
    assert "local-dev" in deviation["detail"]

    # The analysis keeps the run aggregatable (validity 'valid') but warns
    # about the provenance and lists the recorded deviation.
    assert analyze_mod.analyze(base_dir=base) == 0
    import csv as _csv

    with open(
        base / "processed" / "per_run.csv", encoding="utf-8", newline=""
    ) as fh:
        row = next(iter(_csv.DictReader(fh)))
    assert row["run_id"] == "smoke_sequence-r01"
    assert row["validity"] == "valid"
    assert row["resource_source"] == "local-dev"
    assert "not 'sut-collector'" in row["warnings"]
    assert "protocol deviation(s) recorded" in row["warnings"]
    assert "missing_sut_resources" in row["warnings"]


def test_sut_env_missing_required_fields_is_invalid(
    tmp_path, plan_path, fast_run
) -> None:
    """File presence is not enough: a sut_environment.json without the
    REQUIRED_SUT_FIELDS invalidates a timed run (work order P1 fix 4)."""
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path, node=None, nproc=None),
        resources_from=_resources_file(tmp_path),
    )
    assert rc == 1
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "invalid"
    missing = " ".join(manifest["sut_environment_missing_fields"])
    assert "node/hostname" in missing
    assert "nproc" in missing
    reasons = " ".join(manifest["validity_reasons"])
    assert "missing required field(s)" in reasons
    assert "--allow-missing-sut-env" in reasons


def test_sut_env_missing_fields_override_records_deviation(
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
        sut_env_from=_sut_env_file(tmp_path, node=None, nproc=None),
        resources_from=_resources_file(tmp_path),
        allow_missing_sut_env=True,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    deviation = next(
        d
        for d in manifest["deviations"]
        if d["kind"] == "missing_sut_environment"
    )
    assert deviation["authorized_by_flag"] == "--allow-missing-sut-env"
    assert "missing" in deviation["detail"]


def test_simulator_nonzero_exit_is_invalid(tmp_path, plan_path, fast_run) -> None:
    """A non-zero simulator exit invalidates the run outright; there is no
    override for a failed measured run (work order P1 fix 5)."""
    fast_run.returncode = 3
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
    assert rc == 1
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["simulator_returncode"] == 3
    assert manifest["validity"] == "invalid"
    assert any(
        "simulator exited with code 3" in reason
        for reason in manifest["validity_reasons"]
    )


def test_warmup_failure_is_invalid_without_allow_flag(
    tmp_path, plan_path, fast_run
) -> None:
    fast_run.returncodes = [1, 0]  # warm-up fails, measured run succeeds
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
    assert rc == 1
    manifest = _manifest(base, "nominal-r01")
    assert manifest["warmup_returncode"] == 1
    assert manifest["simulator_returncode"] == 0
    assert manifest["validity"] == "invalid"
    assert any(
        "warm-up exited with code 1" in reason
        for reason in manifest["validity_reasons"]
    )
    # The unauthorized deviation is still recorded (authorized_by_flag None).
    deviation = next(
        d for d in manifest["deviations"] if d["kind"] == "warmup_nonzero_exit"
    )
    assert deviation["authorized_by_flag"] is None


def test_warmup_failure_with_allow_flag_is_valid_with_deviation(
    tmp_path, plan_path, fast_run
) -> None:
    fast_run.returncodes = [1, 0]
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
        allow_warmup_failure=True,
    )
    assert rc == 0
    manifest = _manifest(base, "nominal-r01")
    assert manifest["validity"] == "valid"
    assert manifest["allow_warmup_failure"] is True
    deviation = next(
        d for d in manifest["deviations"] if d["kind"] == "warmup_nonzero_exit"
    )
    assert deviation["authorized_by_flag"] == "--allow-warmup-failure"
    assert "code 1" in deviation["detail"]


def test_skip_warmup_on_nominal_is_invalid_without_authorization(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "nominal-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        skip_warmup=True,
        event_log_dir=_local_events(tmp_path, "nominal-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    assert rc == 1
    manifest = _manifest(base, "nominal-r01")
    assert manifest["validity"] == "invalid"
    assert any(
        "--skip-warmup" in reason for reason in manifest["validity_reasons"]
    )
    deviation = next(
        d for d in manifest["deviations"] if d["kind"] == "skip_warmup"
    )
    assert deviation["authorized_by_flag"] is None
    # Only the measured run was invoked.
    assert len(fast_run.calls) == 1


def test_skip_warmup_with_allow_protocol_deviation_is_valid(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "nominal-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        skip_warmup=True,
        event_log_dir=_local_events(tmp_path, "nominal-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
        allow_protocol_deviation=True,
    )
    assert rc == 0
    manifest = _manifest(base, "nominal-r01")
    assert manifest["validity"] == "valid"
    assert manifest["allow_protocol_deviation"] is True
    kinds = {d["kind"]: d for d in manifest["deviations"]}
    assert (
        kinds["skip_warmup"]["authorized_by_flag"] == "--allow-protocol-deviation"
    )
    # The shortened confirmation window (post_run_wait_s=0 vs the 60 s
    # protocol window) is recorded as a deviation too (fix 5).
    assert "confirmation_window_override" in kinds


def test_skip_warmup_on_smoke_records_deviation_but_stays_valid(
    tmp_path, plan_path, fast_run
) -> None:
    """smoke_sequence is not in SKIP_WARMUP_STRICT_CONDITIONS (its planned
    warm-up is 0 s): --skip-warmup is recorded but does not invalidate."""
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        skip_warmup=True,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert any(d["kind"] == "skip_warmup" for d in manifest["deviations"])


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


# ---------------------------------------------------------------------------
# Simulator output layout (work order P1c fix F0)
# ---------------------------------------------------------------------------


def test_sent_events_collected_from_real_simulator_layout(
    tmp_path, plan_path, fast_run
) -> None:
    """The real simulator writes under <output>/<run_id>/
    (egw_simulator.runner); the harness must collect from exactly that
    path. The expected path is derived from the SAME helper the invocation
    uses (run_mod.simulator_run_dir), while the fake simulator hardcodes
    the real layout independently — so a divergence fails here."""
    base = tmp_path / "results"
    run_id = "smoke_sequence-r01"
    rc = run_mod.execute_run(
        plan_path,
        run_id,
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, run_id),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    assert rc == 0
    run_dir = base / "raw" / run_id
    # The helper encodes the simulator's documented contract.
    assert run_mod.simulator_run_dir(Path("out"), "rid") == Path("out") / "rid"
    sim_src = run_mod.simulator_run_dir(run_dir / "logs" / "simulator", run_id)
    assert (sim_src / "sent_events.jsonl").is_file()
    # Collection copied the simulator log byte-for-byte to the run root.
    assert (run_dir / "sent_events.jsonl").read_text(encoding="utf-8") == (
        sim_src / "sent_events.jsonl"
    ).read_text(encoding="utf-8")
    manifest = _manifest(base, run_id)
    assert not any(
        "sent_events.jsonl not found" in w for w in manifest["warnings"]
    )
    # The analysis's tolerant probing finds the simulator's own manifest in
    # the real layout (logs/simulator/<run_id>/manifest.json).
    from egw_experiments.analyze import read_simulator_manifest

    sim_manifest = read_simulator_manifest(run_dir, run_id)
    assert sim_manifest is not None
    assert sim_manifest["run_id"] == run_id


# ---------------------------------------------------------------------------
# Sealed raw run directories (work order P1 item 11)
# ---------------------------------------------------------------------------


def _sealed_valid_run(
    tmp_path: Path, plan_path: Path, run_id: str = "smoke_sequence-r01", **kwargs
) -> Path:
    """Execute one valid run end-to-end; its dir is sealed afterwards."""
    base = tmp_path / "results"
    defaults = dict(
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, run_id),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
    )
    defaults.update(kwargs)
    assert run_mod.execute_run(plan_path, run_id, **defaults) == 0
    assert (base / "raw" / run_id / "SHA256SUMS").is_file()
    return base


def test_run_refuses_sealed_run_dir(tmp_path, plan_path, fast_run, capsys) -> None:
    """(d) 'run' never reuses a run identity whose dir is sealed."""
    base = _sealed_valid_run(tmp_path, plan_path)
    capsys.readouterr()
    rc = run_mod.execute_run(
        plan_path, "smoke_sequence-r01", base_dir=base, no_tls=True
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "sealed" in err
    assert "SHA256SUMS" in err
    assert "NEW run identity" in err


def test_collect_refuses_resources_overwrite_with_different_content(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    base = _sealed_valid_run(tmp_path, plan_path)
    run_dir = base / "raw" / "smoke_sequence-r01"
    before = (run_dir / "resources.csv").read_bytes()
    different = _resources_file(tmp_path, rows=55, name="different.csv")
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=base,
        plan_path=plan_path,
        resources_from=different,
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "refusing to overwrite resources.csv" in err
    assert "sealed" in err
    assert "NEW run identity" in err
    # The raw evidence is untouched and still verifies.
    assert (run_dir / "resources.csv").read_bytes() == before
    assert checksums.verify_sha256sums(run_dir) == []


def test_collect_identical_resources_recopy_is_noop(
    tmp_path, plan_path, fast_run
) -> None:
    base = _sealed_valid_run(tmp_path, plan_path)
    run_dir = base / "raw" / "smoke_sequence-r01"
    identical = _resources_file(tmp_path, name="same-content.csv")
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=base,
        plan_path=plan_path,
        resources_from=identical,
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 0
    assert checksums.verify_sha256sums(run_dir) == []
    # Nothing was added, so no sealed-dir collection_history entry appears.
    manifest = _manifest(base, "smoke_sequence-r01")
    assert "collection_history" not in manifest


def test_collect_refuses_events_refetch_with_different_content(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    base = _sealed_valid_run(tmp_path, plan_path)
    run_dir = base / "raw" / "smoke_sequence-r01"
    before = (run_dir / "events.jsonl").read_bytes()
    script = _write_script(
        tmp_path,
        "different_fetch.py",
        """\
        import sys
        from pathlib import Path
        Path(sys.argv[1]).write_text('{"outcome": "DIFFERENT"}\\n', encoding="utf-8")
        """,
    )
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=base,
        plan_path=plan_path,
        fetch_events_cmd=f'"{PY}" "{script.as_posix()}" {{dest}}',
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "refusing to overwrite events.jsonl" in err
    assert "sealed" in err
    assert "NEW run identity" in err
    assert (run_dir / "events.jsonl").read_bytes() == before
    assert checksums.verify_sha256sums(run_dir) == []


def test_collect_identical_events_refetch_is_noop(
    tmp_path, plan_path, fast_run
) -> None:
    base = _sealed_valid_run(tmp_path, plan_path)
    run_dir = base / "raw" / "smoke_sequence-r01"
    # The sealed events.jsonl came from the local per-run fallback; a
    # re-fetch producing byte-identical content is a no-op.
    script = _write_script(
        tmp_path,
        "identical_fetch.py",
        """\
        import json, sys
        from pathlib import Path
        Path(sys.argv[1]).write_text(
            json.dumps({"run_id": "smoke_sequence-r01", "outcome": "accepted"})
            + "\\n",
            encoding="utf-8",
        )
        """,
    )
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=base,
        plan_path=plan_path,
        fetch_events_cmd=f'"{PY}" "{script.as_posix()}" {{dest}}',
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 0
    assert checksums.verify_sha256sums(run_dir) == []
    history = _manifest(base, "smoke_sequence-r01")["collect_history"]
    assert any(
        "re-fetch identical" in action
        for entry in history
        for action in entry["actions"]
    )


def test_collect_on_tampered_sealed_dir_refuses_naming_path(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    base = _sealed_valid_run(tmp_path, plan_path)
    run_dir = base / "raw" / "smoke_sequence-r01"
    (run_dir / "resources.csv").write_text("tampered\n", encoding="utf-8")
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=base,
        plan_path=plan_path,
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "sealed" in err
    assert "fails integrity verification" in err
    assert "mismatch: resources.csv" in err


def test_collect_adds_missing_file_to_sealed_dir_with_history(
    tmp_path, plan_path, fast_run
) -> None:
    """(b) a genuinely missing file may be ADDED to a sealed dir only via
    'collect': checksums verified first, SHA256SUMS rewritten, and the
    addition recorded as collection_history {when_utc, added_files}."""
    # Sealed WITHOUT resources.csv (deliberate --allow-missing-resources).
    base = _sealed_valid_run(
        tmp_path,
        plan_path,
        resources_from=None,
        allow_missing_resources=True,
    )
    run_dir = base / "raw" / "smoke_sequence-r01"
    assert not (run_dir / "resources.csv").exists()

    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=base,
        plan_path=plan_path,
        resources_from=_resources_file(tmp_path),
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 0
    assert (run_dir / "resources.csv").is_file()
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["resource_source"] == "sut-collector"
    history = manifest["collection_history"]
    assert len(history) == 1
    assert history[0]["added_files"] == ["resources.csv"]
    assert history[0]["when_utc"]
    # The rewritten SHA256SUMS covers the addition and verifies cleanly.
    assert checksums.verify_sha256sums(run_dir) == []

    # (c) idempotent re-collect: same inputs again => no-op, no new entry.
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=base,
        plan_path=plan_path,
        resources_from=_resources_file(tmp_path, name="same-again.csv"),
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert len(manifest["collection_history"]) == 1
    assert checksums.verify_sha256sums(run_dir) == []


def test_external_reingest_refused_mentions_sealed(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    """External timings are never re-ingested over an existing (sealed)
    external run directory."""
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "cold_start-r01",
        base_dir=base,
        external_timings=_timings_file(tmp_path, "cold_start-r01", "cold_start"),
    )
    assert rc == 0
    assert (base / "raw" / "cold_start-r01" / "SHA256SUMS").is_file()
    capsys.readouterr()

    different = tmp_path / "different-timings.json"
    different.write_text(
        json.dumps(
            {
                "run_id": "cold_start-r01",
                "condition": "cold_start",
                "samples": [
                    {
                        "label": "cold_start-r01",
                        "started_utc": "2026-09-07T11:00:00Z",
                        "ended_utc": "2026-09-07T11:01:00Z",
                        "duration_s": 60,
                    }
                ],
                "method": "different measurement",
            }
        )
        + "\n",
        "utf-8",
    )
    rc = run_mod.execute_run(
        plan_path, "cold_start-r01", base_dir=base, external_timings=different
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "sealed" in err
    assert "NEW run identity" in err
