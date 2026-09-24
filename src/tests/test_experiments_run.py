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
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from egw_experiments import checksums, plan_gen
from egw_experiments import controller_metrics as metrics_mod
from egw_experiments import resources as resources_mod
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
    # Keep the real measured-window bounds deterministic and aligned with the
    # resources.csv fixtures. A 100 ms tick gives every start/end pair a
    # positive real UTC interval without consuming the fixture's 40 s span.
    utc_tick = 0

    def fake_utc_now_iso() -> str:
        nonlocal utc_tick
        stamp = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc) + timedelta(
            milliseconds=100 * utc_tick
        )
        utc_tick += 1
        return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    monkeypatch.setattr(run_mod, "utc_now_iso", fake_utc_now_iso)
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


#: The one service the resources fixtures carry (``_resources_file``). A
#: timed run fed by --resources-from accounts for the collector's output
#: like the fetch hook's (manifest 1.4), so the fixtures pass this list as
#: ``expect_services`` and write the companions beside the CSV.
FIXTURE_SERVICES = ["egw-controller"]

#: The closing summary of a collector that accounted for every sampling
#: round: the sample count and the four counters of what it could not
#: measure, all of them zero (collect-resources.sh, the closing ``diag``).
CLEAN_STOP = (
    "stop: samples=41 utc_gap_seconds=0 withheld_samples=0 "
    "withheld_elapsed_s=0.00 withheld_runs_unmeasured=0 "
    "withheld_open_at_stop=0 calibrations=1 pacing=wall-clock"
)


def _write_companions(
    csv_path: Path,
    services: list[str] = FIXTURE_SERVICES,
    *,
    missing: str = "none",
) -> None:
    """The .diagnostics.log and .lifecycle.csv collect-resources.sh writes
    beside its CSV: a start line naming the collector's sha256 and the
    expected services, a clean inventory and a closing summary with every
    counter the collector keeps."""
    listed = ",".join(services)
    Path(f"{csv_path}.diagnostics.log").write_text(
        f"2026-09-07T09:59:59Z start: collector_sha256={'cd' * 32} "
        f"host={SUT_NODE} source=cgroup interval=1s duration=0s pacing: "
        f"fixture; timestamps: fixture; expected services: {listed}\n"
        f"2026-09-07T10:00:41Z inventory: observed={','.join(sorted(services))} "
        f"expected={listed} missing={missing} unnamed_ids=0\n"
        f"2026-09-07T10:00:41Z {CLEAN_STOP}\n",
        "utf-8",
    )
    Path(f"{csv_path}.lifecycle.csv").write_text(
        "ts_utc,event,container_id,name\n"
        + "".join(
            f"2026-09-07T09:59:59Z,named,{i:012d},{name}\n"
            for i, name in enumerate(services)
        ),
        "utf-8",
    )


def _resources_file(
    tmp_path: Path,
    *,
    rows: int = 40,
    host: str = SUT_NODE,
    header: str = RESOURCES_HEADER,
    name: str = "resources.csv",
    companions: bool = True,
) -> Path:
    """A SUT collector resources.csv passing the ingest validation (fix 3):
    exact 6-column header with host provenance, >= MIN_RESOURCE_SAMPLES
    rows, every host equal to the SUT node. With ``companions`` (default)
    the collector's .diagnostics.log and .lifecycle.csv for
    :data:`FIXTURE_SERVICES` sit beside it, as the manual path requires."""
    path = tmp_path / name
    lines = [header]
    for i in range(rows):
        lines.append(
            f"2026-09-07T10:00:{i % 60:02d}Z,egw-controller,10.0,1024,1.0,{host}"
        )
    path.write_text("\n".join(lines) + "\n", "utf-8")
    if companions:
        _write_companions(path)
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


#: A configuration identity as a guest-side capture would write it (ADR 0011
#: item 18): the values are placeholders, the keys are the ones the record
#: names. The harness copies the file and embeds its content verbatim.
CONFIG_IDENTITY = {
    "broker_conf_sha256": "ab" * 32,
    "broker_conf_values": {
        "max_inflight_messages": 4999,
        "max_inflight_bytes": 0,
        "max_queued_messages": 1000,
        "max_queued_bytes": 0,
        "persistent_client_expiration": "1h",
        "sys_interval": 10,
    },
    "broker_reloaded": False,
    "stop_grace_period": "130s",
    "controller_image_id": "sha256:" + "cd" * 32,
    "controller_source_commit": "0123abc",
    "paho_version": "2.1.0",
    "a3_choice": "a",
}


def _config_identity_file(tmp_path: Path, name: str = "configuration_identity.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(CONFIG_IDENTITY, indent=2) + "\n", "utf-8")
    return path


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
        expect_services=FIXTURE_SERVICES,
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
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
        allow_missing_controller_marker=True,
    )
    assert rc == 1  # events collected, but the run is INVALID, not a warning
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "invalid"
    reasons = " ".join(manifest["validity_reasons"])
    assert "sut_environment.json" in reasons
    assert "SUT resources" in reasons or "resources" in reasons
    assert manifest["resource_source"] == "none"
    assert manifest["environment_refs"]["sut"] is None
    # Events WERE collected, but resources.csv is a MANDATORY artefact of a
    # simulator condition and was not authorized as missing, so the run is
    # incomplete and must NOT look sealed (sprint P5, report 5.4).
    assert manifest["missing_mandatory_artifacts"] == ["resources.csv"]
    assert not (base / "raw" / "smoke_sequence-r01" / "SHA256SUMS").exists()
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
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
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
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
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_sut_env=True,
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
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
        expect_services=FIXTURE_SERVICES,
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
        expect_services=FIXTURE_SERVICES,
        allow_warmup_failure=True,
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
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
        expect_services=FIXTURE_SERVICES,
        allow_protocol_deviation=True,
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
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
        expect_services=FIXTURE_SERVICES,
        restart_cmd=f'"{PY}" "{script.as_posix()}" "{marker.as_posix()}" {{run_id}}',
        restart_at_s=0.05,
        allow_missing_controller_marker=True,
        # A controller_restart run without its configuration identity is
        # invalid (ADR 0011 item 18), so the fixture carries one; the twin
        # snapshots, the drain and the post-drain events are neither taken
        # by hooks nor ingested here, so the run is invalid (F6: there is no
        # flag that excuses missing restart evidence) while the restart
        # itself is still recorded exactly once.
        config_identity_from=_config_identity_file(tmp_path),
    )
    assert rc == 1
    assert marker.read_text(encoding="utf-8") == "restarted controller_restart-r01"
    manifest = _manifest(base, "controller_restart-r01")
    restart = manifest["restart"]
    assert restart["executed"] is True
    assert restart["returncode"] == 0
    assert restart["requested_at_s"] == 0.05
    assert restart["started_utc"] and restart["finished_utc"]
    assert manifest["validity"] == "invalid"
    assert "allow_missing_restart_evidence" not in manifest
    assert not any(d["kind"] == "missing_restart_evidence" for d in manifest["deviations"])
    # The runbook's test 6 (docs/setup/qemu_integrated_gateway.md) filters
    # the harness's reasons on this phrase to tell the evidence still to be
    # ingested from any other defect: keep it byte-stable.
    assert all(
        "without its restart evidence step" in r for r in manifest["validity_reasons"]
    )


def test_controller_restart_without_the_evidence_steps_is_invalid(
    tmp_path, plan_path, fast_run
) -> None:
    """A controller_restart run that neither took the twin snapshots, the
    drain and the post-drain events with hooks nor ingested them from files
    is invalid, naming each missing step by both routes: the absence of the
    evidence never makes the run valid (ADR 0011; F6)."""
    fast_run.sleep_s = 1.0
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
        expect_services=FIXTURE_SERVICES,
        restart_cmd=f'"{PY}" -c "pass" {{run_id}}',
        restart_at_s=0.05,
        allow_missing_controller_marker=True,
        config_identity_from=_config_identity_file(tmp_path),
    )
    assert rc == 1
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["validity"] == "invalid"
    reasons = manifest["validity_reasons"]
    for step in (
        "--twin-snapshot-cmd or --twins-before-from (twins.before.json)",
        "--twin-snapshot-cmd or --twins-after-from (twins.after.json)",
        "--drain-cmd or --drain-transcript-from (logs/sut/drain.txt)",
        "--post-drain-fetch-cmd or --post-drain-events-from (events.post-drain.jsonl)",
    ):
        assert any(
            step in r and "neither taken by its hook nor ingested" in r for r in reasons
        ), step
    assert not any(d["kind"] == "missing_restart_evidence" for d in manifest["deviations"])
    assert manifest["twin_snapshots"] == []
    assert manifest["drain"] is None and manifest["events_post_drain_fetch"] is None
    # Invalid for the missing evidence only: the run is still sealed, so
    # 'collect' can ingest the artefacts taken outside the harness.
    assert (base / "raw" / "controller_restart-r01" / checksums.SUMS_FILENAME).is_file()


@pytest.mark.parametrize(
    "document, problem",
    [
        ({}, "broker_conf_sha256"),
        ([], "not an object"),
        ("identity", "not an object"),
        ({**CONFIG_IDENTITY, "paho_version": ""}, "paho_version"),
        ({**CONFIG_IDENTITY, "broker_reloaded": "no"}, "broker_reloaded"),
        ({**CONFIG_IDENTITY, "a3_choice": "c"}, "a3_choice"),
        ({**CONFIG_IDENTITY, "controller_image_id": "cd" * 32}, "controller_image_id"),
        (
            {
                **CONFIG_IDENTITY,
                "broker_conf_values": {
                    k: v
                    for k, v in CONFIG_IDENTITY["broker_conf_values"].items()
                    if k != "sys_interval"
                },
            },
            "broker_conf_values.sys_interval",
        ),
    ],
)
def test_an_incomplete_configuration_identity_is_not_embedded(
    tmp_path, document, problem
) -> None:
    """Any JSON that is not a complete identity (an empty object, a list, a
    string, a missing or mistyped field) is refused with a warning naming
    the problem, so a controller_restart run cannot be valid on it."""
    src = tmp_path / "identity.json"
    src.write_text(json.dumps(document), encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    warnings: list[str] = []
    assert run_mod.ingest_configuration_identity(run_dir, src, warnings) is None
    assert (run_dir / "configuration_identity.json").is_file()
    (warning,) = warnings
    assert "not a configuration identity" in warning and problem in warning


def test_a_complete_configuration_identity_is_embedded(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    warnings: list[str] = []
    doc = run_mod.ingest_configuration_identity(
        run_dir, _config_identity_file(tmp_path), warnings
    )
    assert doc == CONFIG_IDENTITY and warnings == []
    assert run_mod.configuration_identity_problems(CONFIG_IDENTITY) == []


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
        expect_services=FIXTURE_SERVICES,
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

#: Sentinel for "this key is absent from the sample" in the fixture below
#: (None is itself a value an operator file can carry).
_ABSENT = object()


def _timings_file(
    tmp_path: Path,
    run_id: str,
    condition: str,
    *,
    outcome: Any = _ABSENT,
    duration_s: Any = 42,
) -> Path:
    """An operator timings.json fixture.

    ``outcome`` is omitted from the sample unless given: the functional
    external conditions (qemu_boots) require it, the timed ones
    (cold_start, twin_creation) do not carry it at all.
    """
    sample: dict[str, Any] = {
        "label": run_id,
        "started_utc": "2026-09-07T10:00:00Z",
        "ended_utc": "2026-09-07T10:00:42Z",
    }
    if duration_s is not _ABSENT:
        sample["duration_s"] = duration_s
    if outcome is not _ABSENT:
        sample["outcome"] = outcome
    path = tmp_path / f"timings-{run_id}.json"
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "condition": condition,
                "samples": [sample],
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
        external_timings=_timings_file(
            tmp_path, "qemu_boot-r01", "qemu_boot", outcome="pass"
        ),
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
# External timings: duration_s must be a REAL, FINITE, non-negative number
# (P2 finding 4 — the same defect class sprint P5.4 fixed in the analysis
# readers and in the resources ingest, which never covered this third path)
# ---------------------------------------------------------------------------


def _write_timings(path: Path, samples: list[dict[str, Any]], condition: str) -> Path:
    """Write an operator timings.json verbatim (NaN/Infinity included).

    ``json.dumps`` emits the bare ``NaN``/``Infinity`` tokens and
    ``json.loads`` reads them back as floats, so such a file really does
    reach the sample loop — it is not a hypothetical input.
    """
    path.write_text(
        json.dumps(
            {
                "run_id": "cold_start-r01",
                "condition": condition,
                "samples": samples,
                "method": "fixture",
            }
        )
        + "\n",
        "utf-8",
    )
    return path


@pytest.mark.parametrize(
    "duration, value_in_message",
    [
        (True, "True"),  # bool is a subclass of int: isinstance() lets it in
        (float("nan"), "nan"),  # nan < 0 is False, so the comparison lets it in
        (float("inf"), "inf"),  # inf < 0 is False likewise
        (float("-inf"), "-inf"),
    ],
)
def test_load_external_timings_rejects_bool_and_non_finite_duration(
    tmp_path, duration, value_in_message
) -> None:
    """Only a real, finite, non-negative duration_s may be sealed.

    An accepted sample seals the external run, after which the analysis
    converts these values to floats and emits nan/inf means, percentiles
    and confidence intervals from them.
    """
    path = _write_timings(
        tmp_path / "bad.json",
        [
            {"label": "good", "duration_s": 1.0},
            {"label": "bad", "duration_s": duration},
        ],
        "cold_start",
    )
    with pytest.raises(ValueError) as excinfo:
        run_mod.load_external_timings(path)
    message = str(excinfo.value)
    assert "duration_s" in message
    assert "sample 1" in message, "the reason must name the offending index"
    assert value_in_message in message, "the reason must name the offending value"


def test_load_external_timings_rejects_duration_too_large_for_a_float(
    tmp_path,
) -> None:
    """JSON integers are unbounded; float() on one raises OverflowError.

    Left unguarded that exception would escape the validator instead of
    rejecting the sample.
    """
    path = _write_timings(
        tmp_path / "huge.json", [{"label": "a", "duration_s": 10**400}], "cold_start"
    )
    with pytest.raises(ValueError, match="duration_s"):
        run_mod.load_external_timings(path)


def test_external_run_with_non_finite_duration_is_never_sealed(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    """The rejection happens before any evidence directory is created."""
    base = tmp_path / "results"
    timings = _write_timings(
        tmp_path / "bad.json",
        [{"label": "cold_start-r01", "duration_s": float("inf")}],
        "cold_start",
    )
    rc = run_mod.execute_run(
        plan_path, "cold_start-r01", base_dir=base, external_timings=timings
    )
    assert rc == 2
    assert "duration_s" in capsys.readouterr().err
    assert not (base / "raw" / "cold_start-r01").exists()
    plan = plan_gen.load_campaign_plan(plan_path)
    entry = next(r for r in plan["runs"] if r["run_id"] == "cold_start-r01")
    assert entry["status"] == "planned"


# ---------------------------------------------------------------------------
# External timings: functional conditions need a pass/fail outcome per sample
# (P2 finding 5 — gate G1 is evidenced by the QEMU boots and plan 5.1 makes
# QEMU functional-only, so pass/fail IS the measurement)
# ---------------------------------------------------------------------------


def _qemu_run_dir(base: Path, run_id: str = "qemu_boot-r01") -> Path:
    return base / "raw" / run_id


def test_qemu_boot_sample_without_outcome_is_rejected(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    """A QEMU boot without a boot result discharges no evidence at all."""
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "qemu_boot-r01",
        base_dir=base,
        external_timings=_timings_file(tmp_path, "qemu_boot-r01", "qemu_boot"),
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "outcome" in err
    assert "sample 0" in err, "the reason must name the offending sample"
    assert not _qemu_run_dir(base).exists()
    plan = plan_gen.load_campaign_plan(plan_path)
    entry = next(r for r in plan["runs"] if r["run_id"] == "qemu_boot-r01")
    assert entry["status"] == "planned"


@pytest.mark.parametrize("outcome", [None, "", "ok", "PASS", "passed", True, 1])
def test_qemu_boot_sample_with_unrecognised_outcome_is_rejected(
    tmp_path, plan_path, fast_run, capsys, outcome
) -> None:
    """Only the vocabulary the analysis recognises counts as a result.

    Anything else is listed by the analysis as ``unspecified``, i.e. as no
    boot result at all, so it must never seal the run.
    """
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "qemu_boot-r01",
        base_dir=base,
        external_timings=_timings_file(
            tmp_path, "qemu_boot-r01", "qemu_boot", outcome=outcome
        ),
    )
    assert rc == 2
    assert "outcome" in capsys.readouterr().err
    assert not _qemu_run_dir(base).exists()


def test_qemu_boot_outcomes_accepted_are_exactly_those_the_analysis_reads(
    tmp_path, plan_path, fast_run
) -> None:
    """Every outcome the runner seals must survive the analysis verbatim.

    The analysis lists an unrecognised outcome as ``unspecified``; this
    pins the runner's vocabulary to the analyser's without touching it.
    """
    from egw_experiments.analyze import compute_external_run

    base = tmp_path / "results"
    for index, outcome in enumerate(run_mod.EXTERNAL_FUNCTIONAL_OUTCOMES, start=1):
        run_id = f"qemu_boot-r{index:02d}"
        rc = run_mod.execute_run(
            plan_path,
            run_id,
            base_dir=base,
            external_timings=_timings_file(
                tmp_path, run_id, "qemu_boot", outcome=outcome
            ),
        )
        assert rc == 0
        run_dir = _qemu_run_dir(base, run_id)
        assert (run_dir / "SHA256SUMS").is_file()
        analysed = compute_external_run(run_dir)
        assert analysed is not None
        assert [row["outcome"] for row in analysed["sample_rows"]] == [outcome]


def test_timed_external_conditions_keep_their_existing_requirements(
    tmp_path, plan_path, fast_run
) -> None:
    """cold_start/twin_creation are timed, not functional: no outcome needed."""
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "twin_creation-r01",
        base_dir=base,
        external_timings=_timings_file(
            tmp_path, "twin_creation-r01", "twin_creation"
        ),
    )
    assert rc == 0
    assert (base / "raw" / "twin_creation-r01" / "SHA256SUMS").is_file()


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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
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
    # The manual-path copy of the collector output (CSV and companions) is
    # added with resources.csv, so the seal covers what was accounted for.
    kept = "logs/collector/resources-from/resources-smoke_sequence-r01.csv"
    assert history[0]["added_files"] == [
        kept,
        kept + ".diagnostics.log",
        kept + ".lifecycle.csv",
        "resources.csv",
    ]
    assert history[0]["when_utc"]
    # The expected services recorded by the run were applied by 'collect'.
    assert manifest["collector"]["source"] == "--resources-from"
    assert manifest["collector"]["expected_services"] == FIXTURE_SERVICES
    assert manifest["collector"]["problems"] == []
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


# ---------------------------------------------------------------------------
# P5.1 item 2 (report 5.3): collector hooks make 'run' end-to-end
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

#: sha256 the fake collector writes into its diagnostics' start line.
FAKE_COLLECTOR_SHA256 = "ab" * 32

# The fake hook stands for all three collector hooks. The fetch hook in mode
# "write[+option...]" writes what collect-resources.sh leaves beside its CSV
# (the CSV, .diagnostics.log with the start/inventory/stop lines,
# .lifecycle.csv) for every service of {expect_services} (a lone
# 'egw-controller' when none is given). Options remove or alter one piece:
# nodiag, nolife, nostart, noinv (neither the inventory nor the closing
# summary: the collector never got that far), nostop (the inventory is there,
# the closing summary is not), dupstop (two closing summaries), badstop (a
# closing summary without its sample count), badcounters (every figure
# 'unknown'), withheld (3 samples withheld, their cost stated), unmeasured
# (elapsed time in neither count), earlystop (the closing summary before the
# start line), selftest, drop:<name>, extra:<name> (rows of one more service),
# missing:<names>, declared:<names>, host:<name>.
HOOK_SCRIPT = """\
import sys
from pathlib import Path

record, label, run_id, duration_s, dest, mode, rc = sys.argv[1:8]
expect = sys.argv[8] if len(sys.argv) > 8 else ""
with Path(record).open("a", encoding="utf-8") as fh:
    fh.write(" ".join((label, run_id, duration_s, expect or "-")) + "\\n")
print(label + " hook stdout")
sys.stderr.write(label + " hook stderr\\n")
flags = mode.split("+")
if flags[0] == "write":
    opts = {}
    for flag in flags[1:]:
        key, _, value = flag.partition(":")
        opts[key] = value
    services = expect.split(",") if expect else ["egw-controller"]
    drop = set(opts.get("drop", "").split(",")) - {""}
    host = opts.get("host") or "sut-vm"
    row_names = services + ([opts["extra"]] if opts.get("extra") else [])
    rows = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"]
    for i in range(40):
        for name in row_names:
            if name not in drop:
                rows.append(
                    "2026-09-07T10:00:%02dZ,%s,10.0,1024,1.0,%s" % (i, name, host)
                )
    Path(dest).write_text("\\n".join(rows) + "\\n", encoding="utf-8")
    diag = []
    # The closing summary, with the figures of what the collector could and
    # could not measure: zero by default, 'unknown' when its last awk could
    # not read the state file ('badcounters'), a run of withheld samples
    # ('withheld': 3 of the 44 rounds, so the 40 instants still reconcile) and
    # elapsed time no accepted sample measured ('unmeasured').
    counters = "unknown" if "badcounters" in opts else "0"
    stop = (
        "2026-09-07T10:00:41Z stop: samples=%s utc_gap_seconds=%s "
        "withheld_samples=%s withheld_elapsed_s=%s "
        "withheld_runs_unmeasured=%s withheld_open_at_stop=%s calibrations=1 "
        "pacing=wall-clock"
        % (
            "unknown" if "badstop" in opts else ("44" if "withheld" in opts else "41"),
            counters,
            "3" if "withheld" in opts else counters,
            "2.00" if "withheld" in opts else ("unknown" if "badcounters" in opts
                                               else "0.00"),
            "2" if "unmeasured" in opts else counters,
            "1" if "unmeasured" in opts else counters,
        )
    )
    if "earlystop" in opts:
        diag.append(stop)
    if "nostart" not in opts:
        diag.append(
            "2026-09-07T09:59:59Z start: collector_sha256=" + "ab" * 32
            + " host=sut-vm source=cgroup interval=1s duration=" + duration_s
            + "s pacing: fake; timestamps: fake; expected services: "
            + (opts.get("declared") or expect or "none declared")
        )
    if "noinv" not in opts:
        inventory = (
            "2026-09-07T10:00:41Z inventory: observed=" + ",".join(sorted(services))
            + " expected=" + (expect or "none-declared")
            + " missing=" + (opts.get("missing") or "none") + " unnamed_ids=0"
        )
        diag.append(inventory)
        if "dupinv" in opts:
            diag.append(inventory)
        if not {"nostop", "earlystop"} & set(opts):
            diag.append(stop)
            if "dupstop" in opts:
                diag.append(stop)
    if "nodiag" not in opts:
        Path(dest + ".diagnostics.log").write_text(
            "\\n".join(diag) + "\\n", encoding="utf-8"
        )
    if "nolife" not in opts:
        life = ["ts_utc,event,container_id,name"]
        for i, name in enumerate(services):
            life.append("2026-09-07T09:59:59Z,named,%012d,%s" % (i, name))
        Path(dest + ".lifecycle.csv").write_text(
            "\\n".join(life) + "\\n", encoding="utf-8"
        )
    if "selftest" in opts:
        Path(dest + ".self-test").write_text("self_test=1\\n", encoding="utf-8")
sys.exit(int(rc))
"""


def _collector_hooks(
    tmp_path: Path,
    *,
    stop_rc: int = 0,
    fetch_rc: int = 0,
    fetch_mode: str = "write",
):
    """(record_path, start_tpl, stop_tpl, fetch_tpl) for the three hooks.

    Every hook appends '<label> <run_id> <duration_s> <expect_services>' to
    the record file, so the ORDER and the placeholder substitution are both
    observable; the fetch hook additionally writes the collector's CSV to
    {dest} and its companions beside it (see HOOK_SCRIPT for ``fetch_mode``).
    """
    script = _write_script(tmp_path, "collector_hook.py", HOOK_SCRIPT)
    record = tmp_path / "collector-hooks.txt"

    def tpl(label: str, mode: str, rc: int) -> str:
        return (
            f'"{PY}" "{script.as_posix()}" "{record.as_posix()}" {label} '
            '{run_id} {duration_s} "{dest}" ' + f"{mode} {rc}"
            + ' "{expect_services}"'
        )

    return (
        record,
        tpl("start", "noop", 0),
        tpl("stop", "noop", stop_rc),
        tpl("fetch", fetch_mode, fetch_rc),
    )


def _hooked_run(
    tmp_path: Path,
    plan_path: Path,
    *,
    run_id: str = "nominal-r01",
    base: Path | None = None,
    expect_services: list[str] | None = SIX_SERVICES,
    **hook_options: Any,
) -> tuple[int, Path, Path]:
    """Execute one run with the three fake collector hooks.

    Returns (exit code, run directory, record file)."""
    record, start_tpl, stop_tpl, fetch_tpl = _collector_hooks(
        tmp_path, **hook_options
    )
    base = base if base is not None else tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        run_id,
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, run_id),
        sut_env_from=_sut_env_file(tmp_path),
        collector_start_cmd=start_tpl,
        collector_stop_cmd=stop_tpl,
        collector_fetch_cmd=fetch_tpl,
        expect_services=expect_services,
        allow_missing_controller_marker=True,
    )
    return rc, base / "raw" / run_id, record


def _sealed_names(run_dir: Path) -> set[str]:
    return {
        line.split("  ", 1)[1]
        for line in (run_dir / checksums.SUMS_FILENAME)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }


def _hook_labels(record: Path) -> list[str]:
    return [
        line.split()[0]
        for line in record.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_collector_hooks_run_in_order_and_produce_ingested_resources(
    tmp_path, plan_path, fast_run
) -> None:
    """The collector is started BEFORE the warm-up, stopped AFTER the
    measured run and fetched AFTER the confirmation window; the fetched CSV
    goes through the EXISTING validated ingest path (report 5.3), and its
    companions are accounted for and sealed with it."""
    rc, run_dir, record = _hooked_run(tmp_path, plan_path)
    base = run_dir.parent.parent
    assert rc == 0
    assert _hook_labels(record) == ["start", "stop", "fetch"]
    manifest = _manifest(base, "nominal-r01")
    assert manifest["manifest_version"] == run_mod.MANIFEST_VERSION == "1.4"
    hooks = manifest["collector_hooks"]
    assert [h["hook"] for h in hooks] == ["start", "stop", "fetch"]
    for hook in hooks:
        assert hook["returncode"] == 0
        assert hook["started_utc"] and hook["finished_utc"]
        assert "{run_id}" not in hook["command"]
        assert "nominal-r01" in hook["command"]
        assert "{expect_services}" not in hook["command"]
        assert ",".join(SIX_SERVICES) in hook["command"]
    # {duration_s} covers warm-up + measured window + confirmation window,
    # and every hook saw the same expected list the harness enforces.
    recorded = [
        line.split() for line in record.read_text(encoding="utf-8").splitlines()
    ]
    assert int(recorded[0][2]) >= 600 + 120
    assert {line[3] for line in recorded} == {",".join(SIX_SERVICES)}
    assert manifest["resource_source"] == "sut-collector"
    assert manifest["validity"] == "valid"
    assert (run_dir / "resources.csv").is_file()

    collector = manifest["collector"]
    assert collector["expected_services"] == SIX_SERVICES
    assert collector["hooks_in_use"] is True
    assert collector["problems"] == []
    assert collector["deployed_sha256"] == FAKE_COLLECTOR_SHA256
    assert collector["declared_expected_services"] == ",".join(SIX_SERVICES)
    assert collector["inventory"].endswith("missing=none unnamed_ids=0")
    assert collector["inventory_missing"] == []
    assert collector["inventory_line_count"] == 1
    assert collector["stop_line"].endswith("calibrations=1 pacing=wall-clock")
    assert collector["stop_line_count"] == 1
    # The collector accounted for every sampling round it took: 41 rounds,
    # the first of which only primes the CPU deltas, and the 40 instants the
    # CSV carries inside its window.
    assert collector["stop_counters"] == {
        "utc_gap_seconds": "0",
        "withheld_samples": "0",
        "withheld_elapsed_s": "0.00",
        "withheld_runs_unmeasured": "0",
        "withheld_open_at_stop": "0",
    }
    assert collector["samples"] == 41
    assert collector["distinct_instants_in_window"] == 40
    # The collector is given the whole run's duration and ended by the stop
    # hook before it: recorded, never a problem (the real nominal-r01 of
    # 2026-09-19 declared duration=840s and closed a 722 s window).
    assert [
        observation
        for observation in collector["observations"]
        if "shorter than the duration=" not in observation
    ] == []
    assert collector["self_test_present"] is False
    assert collector["rows_per_expected_service"] == {
        name: 40 for name in SIX_SERVICES
    }
    assert collector["unexpected_services"] == []
    assert collector["source"] == "--collector-fetch-cmd"
    # The helper the fetch hook ran ('python <script>': the script) is
    # identified by its sha256.
    hook_script = tmp_path / "collector_hook.py"
    assert collector["fetch_helper_path"] == hook_script.as_posix()
    assert collector["fetch_helper_sha256"] == checksums.sha256_file(hook_script)
    assert manifest["config"]["cli"]["expect_services"] == SIX_SERVICES

    # The CSV and its two companions sit in logs/collector/, their record
    # matches the bytes on disk, and the seal covers them.
    csv_rel = "logs/collector/resources-nominal-r01.csv"
    sealed = _sealed_names(run_dir)
    for key, suffix in (
        ("csv", ""),
        ("diagnostics", ".diagnostics.log"),
        ("lifecycle", ".lifecycle.csv"),
    ):
        entry = collector["files"][key]
        assert entry["path"] == csv_rel + suffix
        assert entry["present"] is True
        assert entry["sha256"] == checksums.sha256_file(run_dir / entry["path"])
        assert entry["size"] == (run_dir / entry["path"]).stat().st_size
        assert entry["path"] in sealed
    assert collector["files"]["self_test"]["present"] is False
    assert checksums.verify_sha256sums(run_dir) == []

    # The full output of every hook is kept, sealed, and named in the
    # manifest; the 500-character tail stays for a quick read.
    for hook in hooks:
        label = hook["hook"]
        assert hook["stdout_file"] == f"logs/collector/hook-{label}.stdout.txt"
        assert hook["stderr_file"] == f"logs/collector/hook-{label}.stderr.txt"
        assert (run_dir / hook["stdout_file"]).read_text(
            encoding="utf-8"
        ).strip() == f"{label} hook stdout"
        assert (run_dir / hook["stderr_file"]).read_text(
            encoding="utf-8"
        ).strip() == f"{label} hook stderr"
        assert hook["stderr_tail"] == f"{label} hook stderr"
        assert hook["stdout_file"] in sealed and hook["stderr_file"] in sealed


def test_collector_hook_nonzero_exit_invalidates_run_naming_the_hook(
    tmp_path, plan_path, fast_run
) -> None:
    """A hook that fails is never a silent warning (report 5.3)."""
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, stop_rc=3)
    base = run_dir.parent.parent
    assert rc == 1
    manifest = _manifest(base, "nominal-r01")
    assert manifest["validity"] == "invalid"
    reasons = " ".join(manifest["validity_reasons"])
    assert "--collector-stop-cmd" in reasons
    assert "exit code 3" in reasons
    stop_record = next(
        h for h in manifest["collector_hooks"] if h["hook"] == "stop"
    )
    assert stop_record["returncode"] == 3


def test_collector_fetch_cmd_and_resources_from_are_mutually_exclusive(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    _record, _start, _stop, fetch_tpl = _collector_hooks(tmp_path)
    rc = run_mod.execute_run(
        plan_path,
        "nominal-r01",
        base_dir=tmp_path / "results",
        no_tls=True,
        resources_from=_resources_file(tmp_path),
        expect_services=FIXTURE_SERVICES,
        collector_fetch_cmd=fetch_tpl,
    )
    assert rc == 2
    assert "mutually exclusive" in capsys.readouterr().err
    assert not (tmp_path / "results").exists()


def test_no_collector_hooks_preserves_todays_behaviour(
    tmp_path, plan_path, fast_run
) -> None:
    """Without hooks a pre-fetched --resources-from still works and the
    manifest records an empty hook list (backward compatibility). The
    manual path is accounted for like the fetch hook's output: the CSV and
    its companions are copied into logs/collector/resources-from/, sealed,
    and inspected against --expect-services."""
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["collector_hooks"] == []
    assert manifest["validity"] == "valid"
    collector = manifest["collector"]
    assert collector["hooks_in_use"] is False
    assert collector["source"] == "--resources-from"
    assert collector["source_path"] == str(tmp_path / "resources.csv")
    assert collector["expected_services"] == FIXTURE_SERVICES
    assert collector["problems"] == []
    assert collector["rows_per_expected_service"] == {"egw-controller": 40}
    assert collector["deployed_sha256"] == "cd" * 32
    assert "fetch_helper_sha256" not in collector
    run_dir = base / "raw" / "smoke_sequence-r01"
    kept = "logs/collector/resources-from/resources-smoke_sequence-r01.csv"
    sealed = _sealed_names(run_dir)
    for suffix in ("", ".diagnostics.log", ".lifecycle.csv"):
        assert collector["files"][
            {"": "csv", ".diagnostics.log": "diagnostics",
             ".lifecycle.csv": "lifecycle"}[suffix]
        ]["path"] == kept + suffix
        assert kept + suffix in sealed
        assert (run_dir / (kept + suffix)).read_bytes() == Path(
            f"{tmp_path / 'resources.csv'}{suffix}"
        ).read_bytes()


def test_local_resources_have_no_collector_output_to_account_for(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """--local-resources (dev only) samples the load generator: there is no
    collector output to account for, so no inspection runs (the run is
    invalid for being local-dev anyway)."""
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
        allow_missing_controller_marker=True,
    )
    assert rc == 1
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["resource_source"] == "local-dev"
    assert manifest["collector"] == {
        "expected_services": None,
        "hooks_in_use": False,
        "source": None,
    }
    assert not any("collector output not accounted for" in r for r in manifest["validity_reasons"])


# ---------------------------------------------------------------------------
# Collector output accounting (work order 2026-09-19, 2.C): the six expected
# services and the collector's companions, fetched and checked before sealing
# ---------------------------------------------------------------------------


def _reasons(run_dir: Path) -> str:
    return " ".join(
        json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))[
            "validity_reasons"
        ]
    )


@pytest.mark.parametrize(
    ("fetch_mode", "absent_suffix"),
    [("write+nolife", ".lifecycle.csv"), ("write+nodiag", ".diagnostics.log")],
)
def test_a_missing_companion_invalidates_the_run_and_keeps_the_other_files(
    tmp_path, plan_path, fast_run, fetch_mode, absent_suffix
) -> None:
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, fetch_mode=fetch_mode)
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "nominal-r01")
    assert manifest["validity"] == "invalid"
    assert f"resources-nominal-r01.csv{absent_suffix} is absent" in _reasons(run_dir)
    assert any(
        w.startswith("collector output problem:") and absent_suffix in w
        for w in manifest["warnings"]
    )
    collector_dir = run_dir / "logs" / "collector"
    kept = {".diagnostics.log", ".lifecycle.csv"} - {absent_suffix}
    assert (collector_dir / "resources-nominal-r01.csv").is_file()
    for suffix in kept:
        assert (collector_dir / f"resources-nominal-r01.csv{suffix}").is_file()
    assert not (collector_dir / f"resources-nominal-r01.csv{absent_suffix}").exists()
    # The CSV itself still passed the unchanged ingest, so the run directory
    # is complete and sealed: invalid, but verifiable as it arrived.
    assert manifest["resource_source"] == "sut-collector"
    assert manifest["missing_mandatory_artifacts"] == []
    sealed = _sealed_names(run_dir)
    assert "logs/collector/resources-nominal-r01.csv" in sealed
    for suffix in kept:
        assert f"logs/collector/resources-nominal-r01.csv{suffix}" in sealed
    assert checksums.verify_sha256sums(run_dir) == []


def test_a_failed_fetch_with_a_missing_companion_names_both_and_keeps_what_arrived(
    tmp_path, plan_path, fast_run
) -> None:
    """The fetch script's exit code AND the absent file are both reasons."""
    rc, run_dir, _record = _hooked_run(
        tmp_path, plan_path, fetch_mode="write+nodiag", fetch_rc=3
    )
    assert rc == 1
    reasons = _reasons(run_dir)
    assert "--collector-fetch-cmd failed with exit code 3" in reasons
    assert "resources-nominal-r01.csv.diagnostics.log is absent" in reasons
    collector_dir = run_dir / "logs" / "collector"
    assert (collector_dir / "resources-nominal-r01.csv").is_file()
    assert (collector_dir / "resources-nominal-r01.csv.lifecycle.csv").is_file()
    assert (collector_dir / "hook-fetch.stdout.txt").is_file()


def test_an_expected_service_without_rows_invalidates_although_the_inventory_saw_it(
    tmp_path, plan_path, fast_run
) -> None:
    """The collector counts a service as observed when it is only in the
    lifecycle file, so 'missing=none' does not prove rows: the harness counts
    the rows of every expected service itself."""
    rc, run_dir, _record = _hooked_run(
        tmp_path, plan_path, fetch_mode="write+drop:egw-mongodb-1"
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "nominal-r01")
    collector = manifest["collector"]
    assert collector["inventory_missing"] == []
    assert collector["rows_per_expected_service"]["egw-mongodb-1"] == 0
    assert collector["rows_per_expected_service"]["egw-controller-1"] == 40
    assert "expected service 'egw-mongodb-1' has no rows" in _reasons(run_dir)
    # The other five services still pass the unchanged ingest validation.
    assert manifest["resource_source"] == "sut-collector"


def test_a_self_test_marker_invalidates_the_run(tmp_path, plan_path, fast_run) -> None:
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, fetch_mode="write+selftest")
    assert rc == 1
    collector = _manifest(run_dir.parent.parent, "nominal-r01")["collector"]
    assert collector["self_test_present"] is True
    assert collector["files"]["self_test"]["present"] is True
    assert "NOT a measurement" in _reasons(run_dir)
    assert "logs/collector/resources-nominal-r01.csv.self-test" in _sealed_names(run_dir)


def test_an_inventory_naming_a_missing_service_invalidates_the_run(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, _record = _hooked_run(
        tmp_path, plan_path, fetch_mode="write+missing:egw-ditto-things-1"
    )
    assert rc == 1
    collector = _manifest(run_dir.parent.parent, "nominal-r01")["collector"]
    assert collector["inventory_missing"] == ["egw-ditto-things-1"]
    assert "never observed: egw-ditto-things-1" in _reasons(run_dir)


def test_a_collector_that_did_not_stop_cleanly_invalidates_the_run(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, fetch_mode="write+noinv")
    assert rc == 1
    collector = _manifest(run_dir.parent.parent, "nominal-r01")["collector"]
    assert collector["inventory"] is None
    assert collector["stop_line"] is None
    assert collector["stop_line_count"] == 0
    assert "did not stop cleanly" in _reasons(run_dir)
    assert "no 'stop:' line" in _reasons(run_dir)


def test_an_inventory_without_the_closing_record_invalidates_the_run(
    tmp_path, plan_path, fast_run
) -> None:
    """F3 (project review of 2026-09-19): the case that used to pass.

    The collector wrote its inventory, every expected service has rows and the
    start hash is the wanted one, but the closing summary is missing: the end
    of the measured window and the number of samples kept are unknown, so the
    output cannot be accounted for.
    """
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, fetch_mode="write+nostop")
    assert rc == 1
    collector = _manifest(run_dir.parent.parent, "nominal-r01")["collector"]
    assert collector["inventory_missing"] == []
    assert collector["rows_per_expected_service"] == {name: 40 for name in SIX_SERVICES}
    assert collector["stop_line"] is None
    assert collector["stop_line_count"] == 0
    assert "no 'stop:' line" in _reasons(run_dir)


@pytest.mark.parametrize(
    "option, expected",
    [
        ("dupstop", "2 'stop:' lines"),
        ("badstop", "no integer 'samples=' count"),
        ("earlystop",
         "records are out of order (start line 2, inventory line 3, stop "
         "line 1)"),
        # The closing record's own accounting: a figure the collector could
        # not compute ('unknown': it could not read its state file when it
        # closed) and elapsed time in neither count are problems of their own
        # (2026-09-20).
        ("badcounters", "carries utc_gap_seconds=unknown"),
        ("unmeasured", "the collector reports withheld_runs_unmeasured=2"),
        ("unmeasured", "the collector reports withheld_open_at_stop=1"),
    ],
)
def test_an_unusable_closing_record_invalidates_the_run(
    tmp_path, plan_path, fast_run, option: str, expected: str
) -> None:
    rc, run_dir, _record = _hooked_run(
        tmp_path, plan_path, fetch_mode=f"write+{option}"
    )
    assert rc == 1
    collector = _manifest(run_dir.parent.parent, "nominal-r01")["collector"]
    assert collector["stop_line"] is not None
    assert collector["stop_line_count"] == (2 if option == "dupstop" else 1)
    assert expected in _reasons(run_dir)


def test_withheld_samples_do_not_invalidate_a_measured_run(
    tmp_path, plan_path, fast_run
) -> None:
    """P1 of the review of 2026-09-20, end to end: the collector withheld 3 of
    its 44 rounds (two samples in one wall-clock second, the artefact it
    recalibrates after) and says what they cost. The run's CPU/RAM evidence is
    the 40 instants the CSV carries, which the ingest validates as it always
    does, so the run is valid and the count is recorded in the manifest."""
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, fetch_mode="write+withheld")
    assert rc == 0
    manifest = _manifest(run_dir.parent.parent, "nominal-r01")
    assert manifest["validity"] == "valid"
    collector = manifest["collector"]
    assert collector["problems"] == []
    assert collector["stop_counters"]["withheld_samples"] == "3"
    assert collector["stop_counters"]["withheld_elapsed_s"] == "2.00"
    assert any(
        "the collector reports withheld_samples=3 (2.00 s of elapsed time)"
        in observation
        for observation in collector["observations"]
    ), collector["observations"]


def test_a_second_inventory_line_invalidates_the_run(
    tmp_path, plan_path, fast_run
) -> None:
    """Two inventories are as ambiguous as two closing records (2026-09-20).

    Everything else is in order: the start hash is the wanted one, the CSV
    holds rows for every expected service and the closing record accounts for
    its samples, so the second inventory is the whole difference.
    """
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, fetch_mode="write+dupinv")
    assert rc == 1
    collector = _manifest(run_dir.parent.parent, "nominal-r01")["collector"]
    assert collector["inventory_line_count"] == 2
    assert collector["stop_line_count"] == 1
    assert "2 'inventory:' lines" in _reasons(run_dir)


def test_diagnostics_without_a_start_line_leave_the_collector_hash_unknown(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, fetch_mode="write+nostart")
    assert rc == 1
    collector = _manifest(run_dir.parent.parent, "nominal-r01")["collector"]
    assert collector["deployed_sha256"] is None
    assert collector["start_line_count"] == 0
    assert "no 'start:' line" in _reasons(run_dir)


def test_a_collector_given_another_service_list_invalidates_the_run(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, _record = _hooked_run(
        tmp_path, plan_path, fetch_mode="write+declared:egw-controller-1"
    )
    assert rc == 1
    collector = _manifest(run_dir.parent.parent, "nominal-r01")["collector"]
    assert collector["declared_expected_services"] == "egw-controller-1"
    assert "declares expected services 'egw-controller-1'" in _reasons(run_dir)


def test_collector_hooks_without_expect_services_invalidate_the_run(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, record = _hooked_run(tmp_path, plan_path, expect_services=None)
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "nominal-r01")
    assert manifest["collector"]["expected_services"] is None
    assert manifest["collector"]["rows_per_expected_service"] is None
    assert "--expect-services was not given" in _reasons(run_dir)
    # {expect_services} renders empty when unset.
    assert {line.split()[3] for line in record.read_text("utf-8").splitlines()} == {"-"}


def test_unexpected_services_in_the_csv_are_only_a_warning(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, _record = _hooked_run(
        tmp_path, plan_path, fetch_mode="write+extra:egw-extra-1"
    )
    assert rc == 0
    manifest = _manifest(run_dir.parent.parent, "nominal-r01")
    assert manifest["validity"] == "valid"
    assert manifest["collector"]["problems"] == []
    assert manifest["collector"]["unexpected_services"] == ["egw-extra-1"]
    assert any(
        "outside --expect-services" in w and "egw-extra-1" in w
        for w in manifest["warnings"]
    )


def test_collector_hooks_work_under_a_base_dir_with_spaces(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results with spaces" / "Projeto Mestrado"
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, base=base)
    assert rc == 0
    manifest = _manifest(base, "nominal-r01")
    assert manifest["validity"] == "valid"
    assert manifest["collector"]["problems"] == []
    assert "logs/collector/resources-nominal-r01.csv.lifecycle.csv" in _sealed_names(run_dir)


FETCH_SCRIPT = run_mod.SRC_DIR / "deployment" / "scripts" / "fetch-collector-output.sh"

# ssh/scp stand-ins for the real fetch script: the "guest" is this machine.
FAKE_GUEST_SSH = """#!/bin/sh
while [ $# -gt 1 ]; do shift; done
exec sh -c "$1"
"""
FAKE_GUEST_SCP = """#!/bin/sh
src=
dst=
for a in "$@"; do src=$dst; dst=$a; done
cp "${src#*:}" "$dst"
"""


@pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("sh") is None,
    reason="fetch-collector-output.sh is POSIX sh for the harness host",
)
@pytest.mark.parametrize("lifecycle_on_guest", [True, False])
def test_the_real_fetch_script_as_the_fetch_hook_under_a_base_dir_with_spaces(
    tmp_path, plan_path, fast_run, monkeypatch, lifecycle_on_guest
) -> None:
    """The runbook's fetch hook, end to end: the repository's script copies
    the CSV and its companions into logs/collector/ under a base directory
    whose path holds spaces, the harness accounts for them and seals them.
    Without the lifecycle companion on the guest the script exits 3 and the
    run is invalid for both reasons, with what arrived still sealed."""
    guest = tmp_path / "guest"
    guest.mkdir()
    remote = guest / "resources-nominal-r01.csv"
    script = _write_script(tmp_path, "guest_collector.py", HOOK_SCRIPT)
    subprocess.run(
        [sys.executable, str(script), str(tmp_path / "guest-record.txt"), "fetch",
         "nominal-r01", "840", str(remote), "write", "0", ",".join(SIX_SERVICES)],
        check=True, capture_output=True,
    )
    if not lifecycle_on_guest:
        Path(f"{remote}.lifecycle.csv").unlink()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in (("ssh", FAKE_GUEST_SSH), ("scp", FAKE_GUEST_SCP)):
        (bin_dir / name).write_text(text, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("EGW_FETCH_SSH", str(bin_dir / "ssh"))
    monkeypatch.setenv("EGW_FETCH_SCP", str(bin_dir / "scp"))
    _record, start_tpl, stop_tpl, _fetch = _collector_hooks(tmp_path)
    fetch_tpl = (
        f'sh "{FETCH_SCRIPT.as_posix()}" guest {remote.as_posix()} "{{dest}}"'
    )
    base = tmp_path / "Projeto Mestrado" / "results dir"
    rc = run_mod.execute_run(
        plan_path,
        "nominal-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "nominal-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        collector_start_cmd=start_tpl,
        collector_stop_cmd=stop_tpl,
        collector_fetch_cmd=fetch_tpl,
        expect_services=SIX_SERVICES,
        allow_missing_controller_marker=True,
    )
    run_dir = base / "raw" / "nominal-r01"
    manifest = _manifest(base, "nominal-r01")
    fetch_hook = manifest["collector_hooks"][-1]
    fetch_out = (run_dir / fetch_hook["stdout_file"]).read_text(encoding="utf-8")
    sealed = _sealed_names(run_dir)
    assert "logs/collector/resources-nominal-r01.csv" in sealed
    assert "logs/collector/resources-nominal-r01.csv.diagnostics.log" in sealed
    assert fetch_hook["stdout_file"] in sealed
    # The fetch script that ran is identified by its sha256.
    assert manifest["collector"]["fetch_helper_path"] == FETCH_SCRIPT.as_posix()
    assert manifest["collector"]["fetch_helper_sha256"] == checksums.sha256_file(
        FETCH_SCRIPT
    )
    if lifecycle_on_guest:
        assert rc == 0, manifest["validity_reasons"]
        assert fetch_hook["returncode"] == 0
        assert manifest["validity"] == "valid"
        assert manifest["collector"]["problems"] == []
        assert sum(line.endswith(" verified") for line in fetch_out.splitlines()) == 3
        assert "logs/collector/resources-nominal-r01.csv.lifecycle.csv" in sealed
    else:
        assert rc == 1
        assert fetch_hook["returncode"] == 3
        assert "lifecycle.csv absent (mandatory)" in fetch_out
        reasons = " ".join(manifest["validity_reasons"])
        assert "--collector-fetch-cmd failed with exit code 3" in reasons
        assert "resources-nominal-r01.csv.lifecycle.csv is absent" in reasons


@pytest.mark.parametrize(
    "value",
    [["egw controller"], ["egw-controller-1", "egw-controller-1"], [], ["a;b"]],
)
def test_invalid_expect_services_are_refused_before_anything_is_written(
    tmp_path, plan_path, fast_run, capsys, value
) -> None:
    _record, start_tpl, stop_tpl, fetch_tpl = _collector_hooks(tmp_path)
    rc = run_mod.execute_run(
        plan_path,
        "nominal-r01",
        base_dir=tmp_path / "results",
        no_tls=True,
        collector_start_cmd=start_tpl,
        collector_stop_cmd=stop_tpl,
        collector_fetch_cmd=fetch_tpl,
        expect_services=value,
    )
    assert rc == 2
    assert "--expect-services" in capsys.readouterr().err
    assert not (tmp_path / "results").exists()


# --- the manual path (--resources-from) is accounted for like the hooks ----


def _manual_run(
    tmp_path: Path,
    plan_path: Path,
    resources: Path | None,
    *,
    expect_services: list[str] | None = FIXTURE_SERVICES,
    run_id: str = "smoke_sequence-r01",
) -> tuple[int, Path, dict]:
    """One run fed by --resources-from; returns (rc, run_dir, manifest)."""
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        run_id,
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, run_id),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=resources,
        expect_services=expect_services,
        allow_missing_controller_marker=True,
    )
    return rc, base / "raw" / run_id, _manifest(base, run_id)


def test_manual_path_without_expect_services_is_invalid(
    tmp_path, plan_path, fast_run
) -> None:
    """A timed run whose SUT resources come from the collector, by hook or
    by --resources-from, must say which services it expects."""
    rc, run_dir, manifest = _manual_run(
        tmp_path, plan_path, _resources_file(tmp_path), expect_services=None
    )
    assert rc == 1
    assert manifest["validity"] == "invalid"
    assert "--expect-services was not given" in _reasons(run_dir)
    # The CSV itself still passed the unchanged ingest: only the accounting
    # is missing, and the run directory is sealed as it is.
    assert manifest["resource_source"] == "sut-collector"
    assert checksums.verify_sha256sums(run_dir) == []


def test_manual_path_without_companions_is_invalid_and_seals_what_arrived(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, manifest = _manual_run(
        tmp_path, plan_path, _resources_file(tmp_path, companions=False)
    )
    assert rc == 1
    reasons = _reasons(run_dir)
    assert "resources-smoke_sequence-r01.csv.diagnostics.log is absent" in reasons
    assert "resources-smoke_sequence-r01.csv.lifecycle.csv is absent" in reasons
    kept = "logs/collector/resources-from/resources-smoke_sequence-r01.csv"
    assert manifest["collector"]["files"]["csv"]["path"] == kept
    assert kept in _sealed_names(run_dir)
    assert not (run_dir / (kept + ".diagnostics.log")).exists()


def test_manual_path_expected_service_without_rows_is_invalid(
    tmp_path, plan_path, fast_run
) -> None:
    resources = _resources_file(tmp_path)
    expected = ["egw-controller", "egw-mongodb-1"]
    _write_companions(resources, expected)
    rc, run_dir, manifest = _manual_run(
        tmp_path, plan_path, resources, expect_services=expected
    )
    assert rc == 1
    collector = manifest["collector"]
    assert collector["rows_per_expected_service"] == {
        "egw-controller": 40,
        "egw-mongodb-1": 0,
    }
    assert collector["problems"] == [
        "expected service 'egw-mongodb-1' has no rows in the fetched collector "
        "CSV resources-smoke_sequence-r01.csv"
    ]


def test_manual_path_self_test_marker_is_copied_and_invalidates(
    tmp_path, plan_path, fast_run
) -> None:
    resources = _resources_file(tmp_path)
    Path(f"{resources}.self-test").write_text("self_test=1\n", "utf-8")
    rc, run_dir, manifest = _manual_run(tmp_path, plan_path, resources)
    assert rc == 1
    assert manifest["collector"]["self_test_present"] is True
    assert "NOT a measurement" in _reasons(run_dir)
    assert (
        "logs/collector/resources-from/resources-smoke_sequence-r01.csv.self-test"
        in _sealed_names(run_dir)
    )


def test_manual_path_run_then_collect_is_accounted_like_the_fetch_hook(
    tmp_path, plan_path, fast_run
) -> None:
    """The experiments README's manual path: the run records the expected
    services, the collector output is fetched afterwards and handed to
    'collect', which copies, inspects and seals it."""
    rc, run_dir, manifest = _manual_run(tmp_path, plan_path, None)
    assert rc == 1  # no SUT resources yet: incomplete, not sealed
    assert manifest["collector"]["expected_services"] == FIXTURE_SERVICES
    assert not (run_dir / checksums.SUMS_FILENAME).exists()

    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=run_dir.parent.parent,
        plan_path=plan_path,
        resources_from=_resources_file(tmp_path, name="fetched.csv"),
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 0
    manifest = _manifest(run_dir.parent.parent, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    collector = manifest["collector"]
    assert collector["source"] == "--resources-from"
    assert collector["source_path"] == str(tmp_path / "fetched.csv")
    assert collector["problems"] == []
    assert collector["deployed_sha256"] == "cd" * 32
    # The record the run left is kept in the audit trail.
    assert manifest["collect_history"][-1]["previous_collector"]["source"] is None
    sealed = _sealed_names(run_dir)
    assert "logs/collector/resources-from/resources-smoke_sequence-r01.csv.lifecycle.csv" in sealed
    assert checksums.verify_sha256sums(run_dir) == []


def test_collect_of_a_file_without_companions_is_invalid(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, _manifest_before = _manual_run(tmp_path, plan_path, None)
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=run_dir.parent.parent,
        plan_path=plan_path,
        resources_from=_resources_file(tmp_path, companions=False),
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "smoke_sequence-r01")
    assert manifest["validity"] == "invalid"
    reasons = " ".join(manifest["validity_reasons"])
    assert "resources-smoke_sequence-r01.csv.diagnostics.log is absent" in reasons


def test_collect_supplies_expected_services_for_a_run_that_recorded_none(
    tmp_path, plan_path, fast_run
) -> None:
    resources = _resources_file(tmp_path)
    rc, run_dir, _before = _manual_run(
        tmp_path, plan_path, resources, expect_services=None
    )
    assert rc == 1
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=run_dir.parent.parent,
        plan_path=plan_path,
        resources_from=resources,
        expect_services=FIXTURE_SERVICES,
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 0
    manifest = _manifest(run_dir.parent.parent, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert manifest["collector"]["expected_services"] == FIXTURE_SERVICES
    # Identical copies: nothing was added to the sealed directory.
    assert "collection_history" not in manifest
    assert checksums.verify_sha256sums(run_dir) == []


def test_collect_never_changes_recorded_expected_services(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    resources = _resources_file(tmp_path)
    rc, run_dir, _before = _manual_run(tmp_path, plan_path, resources)
    assert rc == 0
    before = (run_dir / "manifest.json").read_bytes()
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=run_dir.parent.parent,
        plan_path=plan_path,
        resources_from=resources,
        expect_services=["egw-controller", "egw-mongodb-1"],
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 2
    assert "cannot change them" in capsys.readouterr().err
    assert (run_dir / "manifest.json").read_bytes() == before


def test_collect_expect_services_requires_resources_from(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    rc, run_dir, _before = _manual_run(
        tmp_path, plan_path, _resources_file(tmp_path), expect_services=None
    )
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=run_dir.parent.parent,
        plan_path=plan_path,
        expect_services=FIXTURE_SERVICES,
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 2
    assert "give both, or neither" in capsys.readouterr().err


def test_collect_refuses_a_different_manual_copy_before_writing_anything(
    tmp_path, plan_path, fast_run, capsys
) -> None:
    """A companion that differs from the copy the run kept is different
    evidence: refused, and nothing is added to the run directory."""
    resources = _resources_file(tmp_path)
    rc, run_dir, _before = _manual_run(tmp_path, plan_path, resources)
    assert rc == 0
    files_before = sorted(p.as_posix() for p in run_dir.rglob("*"))
    _write_companions(resources, missing="egw-controller")
    rc = run_mod.collect_run(
        "smoke_sequence-r01",
        base_dir=run_dir.parent.parent,
        plan_path=plan_path,
        resources_from=resources,
        event_log_dir=tmp_path / "unused-event-log",
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert (
        "refusing to overwrite logs/collector/resources-from/"
        "resources-smoke_sequence-r01.csv.diagnostics.log"
    ) in err
    assert sorted(p.as_posix() for p in run_dir.rglob("*")) == files_before
    assert checksums.verify_sha256sums(run_dir) == []


# --- a hook that exceeds its timeout takes its whole process group down ----

SLOW_HOOK = """\
import subprocess, sys, time
started, late = sys.argv[1], sys.argv[2]
# A child in the hook's process group (as ssh/scp are for the fetch script)
# that would write after the hook's timeout.
subprocess.Popen([
    sys.executable, "-c",
    "import pathlib, sys, time; pathlib.Path(sys.argv[1]).write_text('child');"
    " time.sleep(4); pathlib.Path(sys.argv[2]).write_text('late')",
    started, late,
])
print("hook started", flush=True)
time.sleep(60)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX")
def test_a_timed_out_hook_is_ended_with_its_whole_process_group(tmp_path) -> None:
    script = _write_script(tmp_path, "slow_hook.py", SLOW_HOOK)
    started = tmp_path / "child-started.txt"
    late = tmp_path / "logs" / "late-write.txt"
    t0 = time.monotonic()
    record = run_mod.execute_collector_hook(
        "fetch",
        f'"{PY}" "{script.as_posix()}" "{started.as_posix()}" "{late.as_posix()}"',
        "r",
        duration_s=1,
        dest=tmp_path / "x.csv",
        log_dir=tmp_path / "logs",
        timeout_s=2.0,
        kill_grace_s=0.5,
    )
    assert time.monotonic() - t0 < 15
    assert record["returncode"] is None
    assert record["timed_out"] is True
    assert "timed out after 2 s" in record["error"]
    assert "process group" in record["error"]
    assert started.is_file()  # the child ran before the timeout ...
    time.sleep(max(0.0, t0 + 7.0 - time.monotonic()))
    assert not late.exists()  # ... and was killed with the hook
    assert (tmp_path / "logs" / "hook-fetch.stdout.txt").read_text(
        encoding="utf-8"
    ).strip() == "hook started"
    # A timed-out hook is a validity reason naming the flag and the timeout.
    reasons = " ".join(run_mod.collector_hook_failures([record]))
    assert "--collector-fetch-cmd" in reasons and "timed out" in reasons


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX")
def test_a_fetch_hook_timeout_leaves_nothing_writing_into_the_sealed_run(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """The defect: on a timeout only the hook process was killed, and its
    children kept writing into logs/collector/ after the seal."""
    monkeypatch.setattr(run_mod, "FETCH_TIMEOUT_S", 2.0)
    monkeypatch.setattr(run_mod, "HOOK_KILL_GRACE_S", 0.5)
    script = _write_script(tmp_path, "slow_hook.py", SLOW_HOOK)
    _record, start_tpl, stop_tpl, _fetch = _collector_hooks(tmp_path)
    fetch_tpl = (
        f'"{PY}" "{script.as_posix()}" "{(tmp_path / "child-started.txt").as_posix()}" '
        '"{dest}.late"'
    )
    base = tmp_path / "results"
    t0 = time.monotonic()
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        collector_start_cmd=start_tpl,
        collector_stop_cmd=stop_tpl,
        collector_fetch_cmd=fetch_tpl,
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
        allow_missing_resources=True,
    )
    assert rc == 1
    run_dir = base / "raw" / "smoke_sequence-r01"
    manifest = _manifest(base, "smoke_sequence-r01")
    fetch = manifest["collector_hooks"][-1]
    assert fetch["hook"] == "fetch" and fetch["timed_out"] is True
    assert "timed out" in " ".join(manifest["validity_reasons"])
    assert (tmp_path / "child-started.txt").is_file()
    time.sleep(max(0.0, t0 + 8.0 - time.monotonic()))
    late = run_dir / "logs" / "collector" / "resources-smoke_sequence-r01.csv.late"
    assert not late.exists()
    # Sealed (resources were explicitly allowed missing) and still intact.
    assert checksums.verify_sha256sums(run_dir) == []


# --- the fetch helper that ran is identified by its sha256 ------------------


def test_identify_hook_helper(tmp_path) -> None:
    script = tmp_path / "helper dir" / "fetch-collector-output.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    digest = checksums.sha256_file(script)
    quoted = f'"{script.as_posix()}"'
    assert run_mod.identify_hook_helper(f"sh {quoted} vm /tmp/x.csv /d") == {
        "path": script.as_posix(),
        "sha256": digest,
    }
    assert run_mod.identify_hook_helper(f"/bin/dash {quoted} a")["sha256"] == digest
    assert run_mod.identify_hook_helper(f"{quoted} a b")["sha256"] == digest
    # Not a local file: named, but not hashed (PATH is never searched).
    assert run_mod.identify_hook_helper("scp vm:/tmp/x.csv /d") == {
        "path": "scp",
        "sha256": None,
    }
    assert run_mod.identify_hook_helper("sh -c 'scp vm:/x /d'") == {
        "path": None,
        "sha256": None,
    }
    missing = tmp_path / "nope.sh"
    assert run_mod.identify_hook_helper(f'sh "{missing.as_posix()}"')["sha256"] is None


def test_a_fetch_helper_that_is_not_a_local_file_is_warned_about(
    tmp_path, plan_path, fast_run
) -> None:
    _record, start_tpl, stop_tpl, _fetch = _collector_hooks(tmp_path)
    base = tmp_path / "results"
    run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        collector_start_cmd=start_tpl,
        collector_stop_cmd=stop_tpl,
        collector_fetch_cmd=f'"{PY}" -c "import sys; sys.exit(0)" "{{dest}}"',
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
    )
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["collector"]["fetch_helper_path"] is None
    assert manifest["collector"]["fetch_helper_sha256"] is None
    assert any(
        "cannot be identified" in w and "--collector-fetch-cmd" in w
        for w in manifest["warnings"]
    )


def test_format_collector_template_substitutes_expect_services() -> None:
    template = "collect {run_id} {duration_s} \"{dest}\" --expect-services {expect_services}"
    rendered = run_mod.format_collector_template(
        template, "nominal-r01", duration_s=840, dest="/r/x.csv",
        expect_services=SIX_SERVICES,
    )
    assert rendered == (
        'collect nominal-r01 840 "/r/x.csv" --expect-services '
        + ",".join(SIX_SERVICES)
    )
    unset = run_mod.format_collector_template(
        template, "nominal-r01", duration_s=840, dest="/r/x.csv"
    )
    assert unset.endswith("--expect-services ")
    # Any other brace construct survives untouched.
    assert run_mod.format_collector_template(
        "echo {other} {expect_services}", "r", duration_s=1, dest="d",
        expect_services=["a"],
    ) == "echo {other} a"


def test_a_rejected_fetched_csv_is_reported_under_the_fetch_hook_not_resources_from(
    tmp_path, plan_path, fast_run
) -> None:
    rc, run_dir, _record = _hooked_run(
        tmp_path, plan_path, fetch_mode="write+host:other-vm"
    )
    assert rc == 1
    warnings = _manifest(run_dir.parent.parent, "nominal-r01")["warnings"]
    rejected = [w for w in warnings if "REJECTED" in w]
    assert len(rejected) == 1
    assert rejected[0].startswith("--collector-fetch-cmd output ")
    assert "--resources-from" not in rejected[0]


def test_collect_keeps_the_collector_problems_of_the_run(
    tmp_path, plan_path, fast_run
) -> None:
    """'collect' recomputes validity but cannot re-fetch the collector
    output: the problems recorded at run time must survive it."""
    rc, run_dir, _record = _hooked_run(tmp_path, plan_path, fetch_mode="write+selftest")
    assert rc == 1
    rc = run_mod.collect_run(
        "nominal-r01", base_dir=run_dir.parent.parent, plan_path=plan_path
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "nominal-r01")
    assert manifest["validity"] == "invalid"
    assert "NOT a measurement" in " ".join(manifest["validity_reasons"])
    assert checksums.verify_sha256sums(run_dir) == []


def test_compute_validity_applies_collector_problems_to_timed_runs_only() -> None:
    common = dict(
        sut_env_present=True,
        allow_missing_sut_env=False,
        resource_source="sut-collector",
        allow_missing_resources=False,
        restart_required=False,
        restart_ok=False,
        collector_problems=["x is absent"],
    )
    validity, reasons = run_mod.compute_validity(timed=True, **common)
    assert validity == "invalid"
    assert reasons == [
        "collector output not accounted for: x is absent; this run's CPU/RAM "
        "evidence cannot be trusted"
    ]
    assert run_mod.compute_validity(timed=False, **common) == ("valid", [])


#: The diagnostics stamps of the inspection fixtures: the collector's own
#: window, which its closing record and its CSV are read against.
INSPECTION_START = "2026-09-07T09:59:59Z"
INSPECTION_STOP = "2026-09-07T10:00:41Z"


def _write_collector_files(
    directory: Path, diagnostics: str, *, instants: int = 40
) -> Path:
    """One fetched collector output whose CSV carries ``instants`` instants.

    The default is the shape of a clean capsule beside :data:`CLEAN_STOP`:
    41 sampling rounds, of which the first only primes each container's CPU
    delta, so 40 instants are stamped inside the collector's window.
    """
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / "resources-r.csv"
    rows = [RESOURCES_HEADER]
    for second in range(instants):
        rows.append(f"2026-09-07T10:00:{second:02d}Z,a,1.0,1,1.0,sut-vm")
    csv_path.write_text("\n".join(rows) + "\n", "utf-8")
    Path(f"{csv_path}.diagnostics.log").write_text(diagnostics, "utf-8")
    Path(f"{csv_path}.lifecycle.csv").write_text("ts_utc,event,container_id,name\n", "utf-8")
    return csv_path


def test_inspection_flags_two_collectors_and_an_unusable_hash(tmp_path) -> None:
    start = (
        f"{INSPECTION_START} start: collector_sha256={{sha}} host=h source=cgroup "
        "interval=1s duration=45s pacing: p; timestamps: t; expected services: a\n"
    )
    inventory = (
        f"{INSPECTION_STOP} inventory: observed=a expected=a missing=none "
        "unnamed_ids=0\n"
    )
    # The closing record each collector writes: complete here, so the only
    # problems left are the ones this case is about.
    stop = f"{INSPECTION_STOP} {CLEAN_STOP}\n"
    csv_path = _write_collector_files(
        tmp_path / "two",
        start.format(sha="c" * 64)
        + inventory
        + stop
        + start.format(sha="d" * 64)
        + inventory
        + stop,
    )
    two = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert two["start_line_count"] == 2
    assert two["deployed_sha256"] == "c" * 64
    assert any("2 'start:' lines" in p for p in two["problems"])

    csv_path = _write_collector_files(
        tmp_path / "unavailable", start.format(sha="unavailable") + inventory + stop
    )
    unusable = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert unusable["deployed_sha256"] is None
    assert unusable["problems"] == [
        p for p in unusable["problems"] if "'stop:'" not in p
    ]
    assert any("no usable collector_sha256" in p for p in unusable["problems"])
    # Paths are basenames when no run directory is given.
    assert unusable["files"]["csv"]["path"] == "resources-r.csv"


#: The start and inventory records of the inspection fixtures, as
#: collect-resources.sh writes them.
INSPECTION_START_LINE = (
    f"{INSPECTION_START} start: collector_sha256=" + "c" * 64 + " host=h "
    "source=cgroup interval=1s duration=42s pacing: p; timestamps: t; "
    "expected services: a\n"
)
INSPECTION_INVENTORY_LINE = (
    f"{INSPECTION_STOP} inventory: observed=a expected=a missing=none "
    "unnamed_ids=0\n"
)
#: Every figure of a clean closing record, in the collector's own words.
CLEAN_COUNTERS = {
    "utc_gap_seconds": "0",
    "withheld_samples": "0",
    "withheld_elapsed_s": "0.00",
    "withheld_runs_unmeasured": "0",
    "withheld_open_at_stop": "0",
}


def test_inspection_reads_a_complete_set_of_diagnostics_records(tmp_path) -> None:
    """The positive case: one start, one inventory and one closing summary, in
    that order, whose counters account for every sampling round, leave the
    diagnostics without a single problem."""
    csv_path = _write_collector_files(
        tmp_path / "complete",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} {CLEAN_STOP}\n",
    )
    complete = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert complete["problems"] == []
    assert complete["observations"] == []
    assert complete["deployed_sha256"] == "c" * 64
    assert complete["stop_line_count"] == 1
    assert complete["inventory_line_count"] == 1
    assert complete["stop_line"].endswith("calibrations=1 pacing=wall-clock")
    assert complete["stop_counters"] == CLEAN_COUNTERS
    # 41 rounds, none withheld: the 40 instants of the CSV are all of them
    # but the priming round, so the record and the CSV agree.
    assert complete["samples"] == 41
    assert complete["distinct_instants_in_window"] == 40
    assert complete["window"] == [INSPECTION_START, INSPECTION_STOP]
    assert complete["window_seconds"] == 42
    assert complete["declared_interval_s"] == 1.0
    assert complete["declared_duration_s"] == 42.0
    assert complete["rounds_the_declared_interval_implies"] == 43


def test_inspection_rejects_a_closing_line_that_states_no_counter(tmp_path) -> None:
    """A closing record that states none of the figures beside its sample
    count -- the shape collect-resources.sh:396-398 documents for a line an
    older collector wrote, and the shape of a truncated or rewritten record.

    The half that seals the measured runs requires the complete closing record
    exactly as ``tools/session/collector_check.py`` does, and in the same
    words: a timed run whose collector cannot say how many samples it withheld
    is not accounted for (2026-09-20).
    """
    csv_path = _write_collector_files(
        tmp_path / "bare",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} stop: samples=41\n",
    )
    bare = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert bare["stop_counters"] == dict.fromkeys(CLEAN_COUNTERS)
    for name in CLEAN_COUNTERS:
        assert any(
            f"the collector's 'stop:' line has no '{name}=' field" in problem
            and "its closing record is incomplete" in problem
            for problem in bare["problems"]
        ), bare["problems"]


@pytest.mark.parametrize(
    "diagnostics, expected",
    [
        # The closing summary never arrived: the collector was killed, or the
        # fetch caught the file before it was written.
        ("start\ninventory", "no 'stop:' line"),
        # Two collectors appended to the same files within one guest boot.
        ("start\ninventory\nstop\nstop", "2 'stop:' lines"),
        # 'samples=' is the count the closing summary exists to carry.
        ("start\ninventory\nbadstop", "no integer 'samples=' count"),
        # Concatenated or edited evidence: the records are out of order. The
        # whole chain is compared -- start, then inventory, then the closing
        # record -- by the function both halves call, so the order this half
        # seals is the order the preflight half refuses (2026-09-20).
        ("stop\nstart\ninventory",
         "records are out of order (start line 2, inventory line 3, stop "
         "line 1)"),
        ("start\nstop\ninventory",
         "records are out of order (start line 1, inventory line 3, stop "
         "line 2)"),
        ("inventory\nstart\nstop",
         "records are out of order (start line 2, inventory line 1, stop "
         "line 3)"),
        # Two inventories: the harness keeps the FIRST one, as the preflight
        # half does (2026-09-20), so the service that one says was never
        # observed is reported and not lost to the second.
        ("start\nmissinginv\ninventory\nstop", "2 'inventory:' lines"),
        ("start\nmissinginv\ninventory\nstop",
         "reports expected service(s) never observed: a"),
        # The closing record cannot account for its own samples: the collector
        # writes 'unknown' when its last awk cannot read the state file.
        ("start\ninventory\nunknownstop", "carries utc_gap_seconds=unknown"),
        ("start\ninventory\nunknownstop", "carries withheld_open_at_stop=unknown"),
        # Elapsed time in neither count: samples no accepted sample measured.
        ("start\ninventory\nunmeasuredstop", "the collector reports "
                                             "withheld_runs_unmeasured=2"),
        ("start\ninventory\nunmeasuredstop", "the collector reports "
                                             "withheld_open_at_stop=1"),
        ("start\ninventory\nunmeasuredstop", "accounted for nowhere"),
        # The fabricated zero: the elapsed figure the closing awk kept is
        # above zero while the count it could not read reads 0.
        ("start\ninventory\ncontradictorystop",
         "withheld_elapsed_s=11.50 while withheld_samples=0"),
        # A record whose leading token is not the collector's own timestamp:
        # its bounds cannot be trusted, so it is a problem of its own and the
        # rules that rest on it are reported as NOT run (2026-09-20).
        ("start\ninventory\nunstampedstop",
         "the 'stop:' line carries no strictly valid leading UTC timestamp"),
        ("start\ninventory\nunstampedstop",
         "the closing record was NOT reconciled with the CSV"),
        ("unstampedstart\ninventory\nstop",
         "the 'start:' line carries no strictly valid leading UTC timestamp"),
        ("start\nunstampedinventory\nstop",
         "the 'inventory:' line carries no strictly valid leading UTC "
         "timestamp"),
    ],
)
def test_inspection_rejects_an_unusable_closing_record(
    tmp_path, diagnostics: str, expected: str
) -> None:
    """An incomplete or ambiguous record is a problem of its own (F3, project
    review of 2026-09-19): the harness never accepts a collector output whose
    window has no usable end, whose inventory is ambiguous, or whose closing
    summary cannot account for the samples it took (2026-09-20)."""
    lines = {
        "start": INSPECTION_START_LINE.rstrip("\n"),
        "inventory": INSPECTION_INVENTORY_LINE.rstrip("\n"),
        "missinginv": f"{INSPECTION_STOP} inventory: observed=none "
                      "expected=a missing=a unnamed_ids=0",
        "stop": f"{INSPECTION_STOP} {CLEAN_STOP}",
        "badstop": f"{INSPECTION_STOP} stop: samples=unknown "
                   "utc_gap_seconds=0 withheld_samples=3 "
                   "withheld_elapsed_s=0.00 withheld_runs_unmeasured=0 "
                   "withheld_open_at_stop=0",
        "unknownstop": f"{INSPECTION_STOP} stop: samples=41 "
                       "utc_gap_seconds=unknown withheld_samples=unknown "
                       "withheld_elapsed_s=unknown "
                       "withheld_runs_unmeasured=unknown "
                       "withheld_open_at_stop=unknown calibrations=1 "
                       "pacing=wall-clock",
        "unmeasuredstop": f"{INSPECTION_STOP} stop: samples=41 "
                          "utc_gap_seconds=7 withheld_samples=0 "
                          "withheld_elapsed_s=0.00 withheld_runs_unmeasured=2 "
                          "withheld_open_at_stop=1 calibrations=1 "
                          "pacing=wall-clock",
        "contradictorystop": f"{INSPECTION_STOP} stop: samples=41 "
                             "utc_gap_seconds=0 withheld_samples=0 "
                             "withheld_elapsed_s=11.50 "
                             "withheld_runs_unmeasured=0 "
                             "withheld_open_at_stop=0 calibrations=1 "
                             "pacing=wall-clock",
        "manystop": f"{INSPECTION_STOP} stop: samples=600 "
                    "utc_gap_seconds=0 withheld_samples=0 "
                    "withheld_elapsed_s=0.00 withheld_runs_unmeasured=0 "
                    "withheld_open_at_stop=0 calibrations=1 "
                    "pacing=wall-clock",
        # Records the collector did not stamp: a line assembled by hand, or
        # one whose timestamp was rewritten after the fetch.
        "unstampedstart": INSPECTION_START_LINE.rstrip("\n")[
            len(INSPECTION_START) + 1:
        ],
        "unstampedinventory": "2026-09-07T10:00:61Z inventory: observed=a "
                              "expected=a missing=none unnamed_ids=0",
        "unstampedstop": CLEAN_STOP,
    }
    csv_path = _write_collector_files(
        tmp_path / diagnostics.replace("\n", "-"),
        "".join(lines[key] + "\n" for key in diagnostics.split("\n")),
    )
    inspection = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert any(expected in problem for problem in inspection["problems"]), (
        inspection["problems"]
    )
    # The hash and the inventory were still read: the closing record is the
    # only thing wrong. Where a kind of record occurs twice, the FIRST one is
    # the one read, in both halves (2026-09-20), so the capsule whose first
    # inventory names a service never observed reports that service.
    assert inspection["deployed_sha256"] == "c" * 64
    assert inspection["inventory_missing"] == (
        ["a"] if "missinginv" in diagnostics else []
    )


def test_inspection_records_rounds_that_wrote_no_row(tmp_path) -> None:
    """The samples-vs-CSV rule in the half that seals the timed runs
    (2026-09-20, corrected the same day): 43 rounds, none withheld, and 40
    instants inside the collector's window.

    Two rounds beyond the priming one wrote no row at all
    (``collect-resources.sh:1100``, ``:1274``, ``:684``, ``:711``: a round
    whose inputs could not be read is counted and writes nothing). That is
    RECORDED, never a verdict of this function's own: the shortfall costs
    spacing and coverage, and those are judged on the real instants by the
    ingest validation, against MAX_SAMPLE_GAP_S and the protocol's coverage
    rule. A threshold here would silently accept less than the protocol
    does -- and both real capsules of 2026-09-19 sit one lost round from it.

    The rounds are a count the collector could have written: 43 stamped
    rounds fit in its own 42 s window, which is what the rule above them is
    about (2026-09-20).
    """
    csv_path = _write_collector_files(
        tmp_path / "short",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} stop: samples=43 utc_gap_seconds=0 "
        "withheld_samples=0 withheld_elapsed_s=0.00 "
        "withheld_runs_unmeasured=0 withheld_open_at_stop=0 calibrations=1 "
        "pacing=wall-clock\n",
    )
    short = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert short["problems"] == []
    assert run_mod.collector_problem_reasons(short["problems"]) == []
    assert short["closing_record_reconciliation"] == "run"
    assert any(
        "the closing record accounts for samples=43 less withheld_samples=0 = "
        "43 stamped sampling round(s), and the CSV carries 40 distinct "
        f"instant(s) inside the collector's window {INSPECTION_START}.."
        f"{INSPECTION_STOP}: 2 round(s)" in observation
        and "wrote no row at all" in observation
        for observation in short["observations"]
    ), short["observations"]


def test_a_lost_round_leaves_a_real_capsule_valid(tmp_path) -> None:
    """P1 of the review of 2026-09-20, on the geometry of nominal-r01.

    The real capsule closed with ``samples=721`` and carries 720 instants:
    exactly the one-round allowance of the rule as it was written. The very
    next run that loses one round anywhere in 720 -- one failed ``docker
    stats`` poll -- would have been sealed INVALID although every spacing is
    2 s and the coverage 99.9 %, far inside what the protocol accepts. It is
    recorded and the run stands.
    """
    start, stop = "2026-09-19T20:00:45Z", "2026-09-19T20:12:47Z"
    begin = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
    rows = [RESOURCES_HEADER]
    for offset in range(1, 721):
        if offset == 300:  # the round whose poll returned nothing
            continue
        stamp = (begin + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append(f"{stamp},a,1.0,1,1.0,sut-vm")
    directory = tmp_path / "lost-round"
    directory.mkdir(parents=True)
    csv_path = directory / "resources-r.csv"
    csv_path.write_text("\n".join(rows) + "\n", "utf-8")
    Path(f"{csv_path}.diagnostics.log").write_text(
        f"{start} start: collector_sha256=" + "c" * 64 + " host=h source=auto "
        "interval=1s duration=840s pacing: wall-clock seconds; timestamps: "
        "awk systime(); expected services: a\n"
        f"{stop} inventory: observed=a expected=a missing=none unnamed_ids=0\n"
        f"{stop} stop: samples=721 utc_gap_seconds=1 withheld_samples=0 "
        "withheld_elapsed_s=0.00 withheld_runs_unmeasured=0 "
        "withheld_open_at_stop=0 calibrations=1 pacing=wall-clock\n",
        "utf-8",
    )
    Path(f"{csv_path}.lifecycle.csv").write_text(
        "ts_utc,event,container_id,name\n", "utf-8"
    )
    lost = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert lost["problems"] == []
    assert lost["distinct_instants_in_window"] == 719
    assert any("wrote no row at all" in o for o in lost["observations"])
    # The rule that IS the authority on the spacing and the coverage.
    assert resources_mod.validate_resources_csv(
        str(csv_path),
        expected_host="sut-vm",
        expected_window_start_utc=start,
        expected_window_end_utc=stop,
    ) == []


def test_withheld_samples_never_invalidate_a_run(tmp_path) -> None:
    """P1 of the review of 2026-09-20: a withheld round must not invalidate a
    run through the count of the rounds the window implies either.

    A withheld sample IS a completed sampling round that stamps no second
    (``collect-resources.sh:422-427``), and ``samples=`` counts it
    (``:1287``), so the count legitimately exceeds what the stamped window
    allows by exactly the withheld count. Eight of them on a 42 s window at
    interval=1s: recorded, and the run stands.
    """
    csv_path = _write_collector_files(
        tmp_path / "withheld-eight",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} stop: samples=49 utc_gap_seconds=0 "
        "withheld_samples=8 withheld_elapsed_s=6.00 "
        "withheld_runs_unmeasured=0 withheld_open_at_stop=0 calibrations=1 "
        "pacing=wall-clock\n",
    )
    withheld = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert withheld["problems"] == []
    assert run_mod.collector_problem_reasons(withheld["problems"]) == []
    observed = " | ".join(withheld["observations"])
    assert (
        "the closing record states samples=49, more rounds than its own 42 s "
        "window at the interval=1s the 'start:' line declares allows (43)"
    ) in observed, observed
    assert "a sampling round that stamped no second" in observed


@pytest.mark.parametrize(
    "samples, withheld, elapsed",
    [
        # No round withheld: the raw count and the accounted one are equal.
        (20, 0, "0.00"),
        # The case the bound of 2026-09-20 let through until today: 42 rounds
        # less the 3 withheld are 39 stamped ones, and the CSV carries 40
        # instants -- one more than any round of this run can have stamped,
        # since a withheld round stamps none at all.
        (42, 3, "2.00"),
    ],
)
def test_inspection_rejects_more_instants_than_sampling_rounds(
    tmp_path, samples: int, withheld: int, elapsed: str
) -> None:
    """Rows that cannot exist: a round stamps at most one instant and a
    withheld round stamps none, so a CSV with more distinct instants inside
    the window than the rounds the record ACCOUNTS FOR holds instants of
    another collector's run, or edited evidence."""
    csv_path = _write_collector_files(
        tmp_path / f"many-instants-{withheld}",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} stop: samples={samples} utc_gap_seconds=0 "
        f"withheld_samples={withheld} withheld_elapsed_s={elapsed} "
        "withheld_runs_unmeasured=0 withheld_open_at_stop=0 calibrations=1 "
        "pacing=wall-clock\n",
    )
    excess = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert any(
        "the CSV carries 40 distinct instant(s) inside the collector's window "
        f"{INSPECTION_START}..{INSPECTION_STOP}, more than the samples="
        f"{samples} less withheld_samples={withheld} = {samples - withheld} "
        "sampling round(s) its closing record accounts for: a round stamps at "
        "most one instant and a withheld round stamps none at all, so the CSV "
        "holds instants the collector did not stamp"
        in problem
        for problem in excess["problems"]
    ), excess["problems"]


def test_inspection_rejects_more_rounds_than_the_stamped_window_can_hold(
    tmp_path,
) -> None:
    """A closing record that cannot be true (P2 of the review of 2026-09-20).

    600 rounds, none of them withheld, inside a stamped window of 42 s. An
    accepted round stamps a second strictly after the last stamped one
    (``collect-resources.sh:422-427`` withholds every other sample and writes
    no rows for it), so at most 43 rounds can have been stamped there, and
    the closing record counts every round it withheld: with
    ``withheld_samples=0`` no mechanism is left by which 600 rounds can have
    been taken in that window. The half that seals the timed runs refuses the
    record instead of going on to trust its other figures.
    """
    csv_path = _write_collector_files(
        tmp_path / "impossible-rounds",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} stop: samples=600 utc_gap_seconds=0 "
        "withheld_samples=0 withheld_elapsed_s=0.00 "
        "withheld_runs_unmeasured=0 withheld_open_at_stop=0 calibrations=1 "
        "pacing=wall-clock\n",
    )
    impossible = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert any(
        "the closing record states samples=600 less withheld_samples=0 = 600 "
        f"stamped sampling round(s) inside its own 42 s window "
        f"{INSPECTION_START}..{INSPECTION_STOP}: an accepted round stamps a "
        "second strictly after the last one, so at most 43 of them can have "
        "been stamped there (one more for the closing record's own stamp), "
        "and the record cannot be true" in problem
        for problem in impossible["problems"]
    ), impossible["problems"]
    # A timed run carrying this record is invalid, not merely annotated.
    assert run_mod.collector_problem_reasons(impossible["problems"]) != []
    # The declared interval is a different matter, and stays an observation.
    assert any(
        "more rounds than its own 42 s window at the interval=1s" in observation
        for observation in impossible["observations"]
    ), impossible["observations"]


def test_inspection_refuses_more_rounds_withheld_than_taken(tmp_path) -> None:
    """P3 of the review of 2026-09-20: a withheld sample IS a completed round.

    ``samples=`` counts every round the loop completed, withheld ones
    included (``collect-resources.sh:1287``), so ``withheld_samples <=
    samples`` holds of every record that can be read at all. A record that
    breaks it is refused and the reconciliation is reported as NOT run: until
    today the negative difference silently switched off both rules that rest
    on it, and a CSV with no instant at all inside the collector's window was
    sealed with an empty problem list.
    """
    csv_path = _write_collector_files(
        tmp_path / "withheld-above-samples",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} stop: samples=41 utc_gap_seconds=0 "
        "withheld_samples=45 withheld_elapsed_s=40.00 "
        "withheld_runs_unmeasured=0 withheld_open_at_stop=0 calibrations=1 "
        "pacing=wall-clock\n",
    )
    rows = [RESOURCES_HEADER] + [
        f"2026-09-07T11:00:{second:02d}Z,a,1.0,1,1.0,sut-vm"
        for second in range(40)
    ]
    csv_path.write_text("\n".join(rows) + "\n", "utf-8")
    unreadable = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert unreadable["closing_record_reconciliation"] == (
        "not run: the closing record states withheld_samples=45 against "
        "samples=41: more rounds withheld than taken, so the record cannot be "
        "read"
    )
    assert any(
        "the closing record was NOT reconciled with the CSV" in problem
        and "more rounds withheld than taken" in problem
        for problem in unreadable["problems"]
    ), unreadable["problems"]


def test_inspection_refuses_a_window_whose_stop_is_not_after_its_start(
    tmp_path,
) -> None:
    """P3 of the review of 2026-09-20: the rule the preflight half had alone.

    A wall clock stepped back between the two records leaves a stop that is
    not after the start. Such a window measures nothing: the harness used to
    seal its arithmetic (a negative ``window_seconds``, a negative count of
    implied rounds and a shortfall computed from both) while
    ``tools/session/collector_check.py`` refused the same output, which is a
    disagreement between the two halves about one collector.
    """
    reversed_stop = "2026-09-07T09:59:34Z"
    csv_path = _write_collector_files(
        tmp_path / "reversed-window",
        INSPECTION_START_LINE
        + f"{reversed_stop} inventory: observed=a expected=a missing=none "
        "unnamed_ids=0\n"
        + f"{reversed_stop} {CLEAN_STOP}\n",
    )
    reversed_window = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert reversed_window["window"] == [INSPECTION_START, reversed_stop]
    assert reversed_window["window_seconds"] is None
    assert reversed_window["rounds_the_declared_interval_implies"] is None
    assert reversed_window["declared_duration_shortfall_s"] is None
    assert reversed_window["closing_record_reconciliation"] == (
        f"not run: the collector's start {INSPECTION_START} is not earlier "
        f"than its stop {reversed_stop}: the measured window is reversed or "
        "empty"
    )
    assert any(
        "the measured window is reversed or empty" in problem
        for problem in reversed_window["problems"]
    ), reversed_window["problems"]
    # The same, with the two records stamped in the same second: a window of
    # no length at all, which one instant on the bound used to hide.
    csv_path = _write_collector_files(
        tmp_path / "zero-window",
        INSPECTION_START_LINE
        + f"{INSPECTION_START} inventory: observed=a expected=a missing=none "
        "unnamed_ids=0\n"
        + f"{INSPECTION_START} {CLEAN_STOP}\n",
    )
    empty_window = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert empty_window["window_seconds"] is None
    assert empty_window["closing_record_reconciliation"].startswith(
        "not run: the collector's start"
    )
    assert any(
        "the measured window is reversed or empty" in problem
        for problem in empty_window["problems"]
    ), empty_window["problems"]


def test_inspection_rejects_a_csv_with_no_instant_in_the_window(tmp_path) -> None:
    """The other contradiction: the record accounts for stamped rounds and the
    CSV carries no instant at all inside the collector's window."""
    csv_path = _write_collector_files(
        tmp_path / "no-instants",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} {CLEAN_STOP}\n",
    )
    rows = [RESOURCES_HEADER] + [
        f"2026-09-07T11:00:{second:02d}Z,a,1.0,1,1.0,sut-vm"
        for second in range(40)
    ]
    csv_path.write_text("\n".join(rows) + "\n", "utf-8")
    empty = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert any(
        "the closing record accounts for samples=41 less withheld_samples=0 = "
        "41 stamped sampling round(s), and the CSV carries no instant at all "
        f"inside the collector's window {INSPECTION_START}..{INSPECTION_STOP}"
        in problem
        for problem in empty["problems"]
    ), empty["problems"]


def test_inspection_reports_a_reconciliation_it_could_not_make(tmp_path) -> None:
    """P2 of the review of 2026-09-20: a rule that cannot run is reported, not
    switched off.

    A CSV without a ``ts_utc`` column carries rows nothing can place in the
    collector's window. The preflight check calls that UNCHECKED; the half
    that seals the measured runs used to leave
    ``distinct_instants_in_window: null`` beside ``problems: []``, i.e. the
    collector output recorded as fully accounted for.
    """
    csv_path = _write_collector_files(
        tmp_path / "no-ts",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} {CLEAN_STOP}\n",
    )
    csv_path.write_text("container,cpu_pct,mem_bytes,mem_pct,host\na,1.0,1,1.0,sut-vm\n", "utf-8")
    blind = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert blind["distinct_instants_in_window"] is None
    assert blind["closing_record_reconciliation"] == (
        "not run: the CSV's instants could not be read"
    )
    assert any(
        "has no 'ts_utc' column" in problem for problem in blind["problems"]
    ), blind["problems"]
    assert any(
        "the closing record was NOT reconciled with the CSV (not run: the "
        "CSV's instants could not be read)" in problem
        for problem in blind["problems"]
    ), blind["problems"]


# ---------------------------------------------------------------------------
# What the collector documents as harmless is recorded, never a verdict
# (P1 of the review of 2026-09-20)
# ---------------------------------------------------------------------------
def test_a_forward_clock_step_leaves_a_timed_run_valid(tmp_path) -> None:
    """``utc_gap_seconds`` is not a measure of lost evidence.

    collect-resources.sh:117-120 says in the collector's own words that a wall
    clock stepped FORWARD adds to this count 'although no time passed
    unsampled'. The CSV here is the clean one with one second missing: the
    widest spacing is 2 s, far inside MAX_SAMPLE_GAP_S, so the run's CPU/RAM
    evidence is intact and inside the protocol's declared tolerance. The count
    is recorded in the manifest, in the collector's words, and the run stands.
    """
    rows = [RESOURCES_HEADER]
    for second in range(41):
        if second != 20:
            rows.append(f"2026-09-07T10:00:{second:02d}Z,a,1.0,1,1.0,sut-vm")
    directory = tmp_path / "stepped"
    directory.mkdir(parents=True)
    csv_path = directory / "resources-r.csv"
    csv_path.write_text("\n".join(rows) + "\n", "utf-8")
    Path(f"{csv_path}.diagnostics.log").write_text(
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} stop: samples=41 utc_gap_seconds=1 "
        "withheld_samples=0 withheld_elapsed_s=0.00 "
        "withheld_runs_unmeasured=0 withheld_open_at_stop=0 calibrations=1 "
        "pacing=wall-clock\n",
        "utf-8",
    )
    Path(f"{csv_path}.lifecycle.csv").write_text(
        "ts_utc,event,container_id,name\n", "utf-8"
    )
    stepped = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert stepped["problems"] == []
    assert run_mod.collector_problem_reasons(stepped["problems"]) == []
    assert stepped["stop_counters"]["utc_gap_seconds"] == "1"
    observed = " | ".join(stepped["observations"])
    assert "the collector reports utc_gap_seconds=1" in observed
    assert "although no time passed unsampled" in observed
    assert "validate_resources_csv against the protocol's MAX_SAMPLE_GAP_S" in observed
    # The same CSV, judged by the rule that IS the authority on the spacing.
    assert resources_mod.validate_resources_csv(
        str(csv_path),
        expected_host="sut-vm",
        expected_window_start_utc=INSPECTION_START,
        expected_window_end_utc=INSPECTION_STOP,
    ) == []


def test_withheld_samples_alone_leave_a_timed_run_valid(tmp_path) -> None:
    """A withheld sample is the pacing artefact the collector recalibrates
    after (two samples in one wall-clock second): it writes no rows and costs
    elapsed time that the record states, so it is recorded, not a verdict.

    44 rounds less the 3 withheld are the 40 instants the CSV carries plus the
    priming round.
    """
    csv_path = _write_collector_files(
        tmp_path / "withheld",
        INSPECTION_START_LINE
        + INSPECTION_INVENTORY_LINE
        + f"{INSPECTION_STOP} stop: samples=44 utc_gap_seconds=0 "
        "withheld_samples=3 withheld_elapsed_s=2.00 "
        "withheld_runs_unmeasured=0 withheld_open_at_stop=0 calibrations=1 "
        "pacing=wall-clock\n",
    )
    withheld = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert withheld["problems"] == []
    assert withheld["stop_counters"]["withheld_samples"] == "3"
    assert withheld["stop_counters"]["withheld_elapsed_s"] == "2.00"
    assert any(
        "the collector reports withheld_samples=3 (2.00 s of elapsed time)"
        in observation
        for observation in withheld["observations"]
    ), withheld["observations"]


#: The figures the collector really wrote on this machine on 2026-09-19,
#: copied from the two capsules the campaign holds: the 45 s preflight and the
#: 120+600 s nominal run. Each closed with one round more than the instants of
#: its CSV, because the first round only primes the CPU deltas. A rule that
#: refuses either of these refuses the evidence the thesis rests on.
REAL_CAPSULES = {
    "preflight-45s": ("2026-09-19T19:37:55Z", "2026-09-19T19:38:40Z", "45s", 46, 45),
    "nominal-r01": ("2026-09-19T20:00:45Z", "2026-09-19T20:12:47Z", "840s", 721, 720),
}


@pytest.mark.parametrize("name", sorted(REAL_CAPSULES))
def test_a_real_capsule_of_2026_09_19_is_accounted_for(tmp_path, name: str) -> None:
    """The regression that binds the rule to the evidence: neither the 45 s
    preflight nor the 120+600 s nominal run may be refused by the half that
    seals the measured runs either."""
    start, stop, duration, samples, instants = REAL_CAPSULES[name]
    begin = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
    rows = [RESOURCES_HEADER]
    for offset in range(1, instants + 1):
        stamp = (begin + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append(f"{stamp},a,1.0,1,1.0,sut-vm")
    directory = tmp_path / name
    directory.mkdir(parents=True)
    csv_path = directory / "resources-r.csv"
    csv_path.write_text("\n".join(rows) + "\n", "utf-8")
    Path(f"{csv_path}.diagnostics.log").write_text(
        f"{start} start: collector_sha256=" + "c" * 64 + " host=h source=auto "
        f"interval=1s duration={duration} pacing: wall-clock seconds; "
        "timestamps: awk systime(); expected services: a\n"
        f"{stop} inventory: observed=a expected=a missing=none unnamed_ids=0\n"
        f"{stop} stop: samples={samples} utc_gap_seconds=0 withheld_samples=0 "
        "withheld_elapsed_s=0.00 withheld_runs_unmeasured=0 "
        "withheld_open_at_stop=0 calibrations=1 pacing=wall-clock\n",
        "utf-8",
    )
    Path(f"{csv_path}.lifecycle.csv").write_text(
        "ts_utc,event,container_id,name\n", "utf-8"
    )
    real = run_mod.inspect_collector_outputs(csv_path, ["a"])
    assert real["problems"] == []
    assert real["samples"] == samples
    assert real["distinct_instants_in_window"] == instants
    assert real["samples"] - real["distinct_instants_in_window"] == 1


def test_inspection_of_a_missing_csv_reports_it_once(tmp_path) -> None:
    missing = run_mod.inspect_collector_outputs(tmp_path / "resources-r.csv", ["a"])
    assert missing["files"]["csv"]["present"] is False
    assert missing["rows_per_expected_service"] is None
    problems = missing["problems"]
    assert any("collector CSV resources-r.csv is absent" in p for p in problems)
    assert not any("has no rows" in p for p in problems)
    assert sum("is absent" in p for p in problems) == 3  # csv + two companions


# ---------------------------------------------------------------------------
# P5.1 item 1 (report 5.2): confirmation marker in the controller's clock
# domain - run-side half of the cross-agent contract
# ---------------------------------------------------------------------------


MARKER_MONOTONIC_NS = 987_654_321_000
MARKER_WALL_UTC = "2026-09-07T10:05:00.000Z"


def _fake_controller_marker(monkeypatch, payload=None):
    """Replace the harness's stdlib HTTP GET with a recorded fake."""
    calls: list[tuple[str, float]] = []
    body = (
        payload
        if payload is not None
        else {
            "accepted": 5,
            "queue_depth": 0,
            "monotonic_ns": MARKER_MONOTONIC_NS,
            "wall_utc": MARKER_WALL_UTC,
        }
    )

    def fake_get(url, timeout_s):
        calls.append((url, timeout_s))
        return body

    monkeypatch.setattr(run_mod, "_http_get_json", fake_get)
    return calls


def test_controller_marker_recorded_and_deadline_is_controller_domain(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    calls = _fake_controller_marker(monkeypatch)
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
        expect_services=FIXTURE_SERVICES,
        controller_url="http://127.0.0.1:8000",
    )
    assert rc == 0
    assert calls and calls[0][0] == "http://127.0.0.1:8000/metrics"
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["controller_monotonic_at_run_end_ns"] == MARKER_MONOTONIC_NS
    assert manifest["confirmation_deadline_clock_domain"] == "controller"
    assert manifest["confirmation_deadline_monotonic_ns"] == (
        MARKER_MONOTONIC_NS + manifest["confirmation_window_s"] * 1_000_000_000
    )
    # The 60 s window itself is untouched.
    assert manifest["confirmation_window_s"] == 60
    assert manifest["controller_marker"]["wall_utc"] == MARKER_WALL_UTC
    assert manifest["validity"] == "valid"
    assert not any(
        d["kind"] == "confirmation_marker_unavailable"
        for d in manifest["deviations"]
    )


def test_missing_controller_marker_invalidates_timed_run(
    tmp_path, plan_path, fast_run
) -> None:
    """No controller marker => the confirmation deadline is unverifiable, so
    a timed run is INVALID (report 5.2)."""
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
        expect_services=FIXTURE_SERVICES,
    )
    assert rc == 1
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "invalid"
    assert manifest["controller_monotonic_at_run_end_ns"] is None
    assert manifest["confirmation_deadline_clock_domain"] == "unavailable"
    assert manifest["confirmation_deadline_monotonic_ns"] is None
    reasons = " ".join(manifest["validity_reasons"])
    assert "confirmation marker" in reasons
    assert "--allow-missing-controller-marker" in reasons
    deviation = next(
        d
        for d in manifest["deviations"]
        if d["kind"] == "confirmation_marker_unavailable"
    )
    assert deviation["authorized_by_flag"] is None


def test_allow_missing_controller_marker_records_the_deviation(
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert manifest["confirmation_deadline_clock_domain"] == "unavailable"
    deviation = next(
        d
        for d in manifest["deviations"]
        if d["kind"] == "confirmation_marker_unavailable"
    )
    assert deviation["authorized_by_flag"] == "--allow-missing-controller-marker"


def test_controller_marker_poll_failure_is_recorded_not_raised(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    def boom(url, timeout_s):
        raise OSError("connection refused")

    monkeypatch.setattr(run_mod, "_http_get_json", boom)
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
        expect_services=FIXTURE_SERVICES,
        controller_url="http://127.0.0.1:8000",
        allow_missing_controller_marker=True,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["confirmation_deadline_clock_domain"] == "unavailable"
    assert "connection refused" in manifest["controller_marker"]["error"]


def test_poll_controller_marker_rejects_a_payload_without_monotonic_ns(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        run_mod, "_http_get_json", lambda url, timeout_s: {"accepted": 1}
    )
    marker = run_mod.poll_controller_marker("http://127.0.0.1:8000")
    assert marker["ok"] is False
    assert marker["monotonic_ns"] is None
    assert "monotonic_ns" in marker["error"]


# ---------------------------------------------------------------------------
# P5.4 defect 5: the marker must be polled at the TRUE end of the measured
# window - before the samplers are joined and before any hook
# ---------------------------------------------------------------------------


def test_controller_marker_is_polled_before_the_samplers_are_joined(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """Joining the samplers first can cost up to a full docker-stats /
    fetch_metrics timeout, and every second spent there silently widens the
    confirmation window to 60 + delta s."""
    order: list[str] = []

    def recording_get(url, timeout_s):
        order.append("marker")
        return {
            "monotonic_ns": MARKER_MONOTONIC_NS,
            "wall_utc": MARKER_WALL_UTC,
        }

    real_exit = run_mod.ControllerMetricsSampler.__exit__

    def recording_exit(self, exc_type, exc, tb):
        order.append("metrics-sampler-join")
        return real_exit(self, exc_type, exc, tb)

    monkeypatch.setattr(run_mod, "_http_get_json", recording_get)
    monkeypatch.setattr(run_mod.ControllerMetricsSampler, "__exit__", recording_exit)
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
        expect_services=FIXTURE_SERVICES,
        controller_url="http://127.0.0.1:8000",
    )
    assert rc == 0
    assert order[:2] == ["marker", "metrics-sampler-join"]


def test_controller_marker_lag_is_recorded_in_the_manifest(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    _fake_controller_marker(monkeypatch)
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
        expect_services=FIXTURE_SERVICES,
        controller_url="http://127.0.0.1:8000",
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    marker = manifest["controller_marker"]
    assert isinstance(marker["lag_s"], float)
    assert 0.0 <= marker["lag_s"] <= run_mod.CONTROLLER_MARKER_LAG_TOLERANCE_S
    assert marker["lag_tolerance_s"] == run_mod.CONTROLLER_MARKER_LAG_TOLERANCE_S
    assert not any(
        d["kind"] == "confirmation_marker_lag" for d in manifest["deviations"]
    )
    # The 60 s window value itself is untouched.
    assert manifest["confirmation_window_s"] == 60


def test_a_late_controller_marker_poll_is_warned_and_recorded_as_a_deviation(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """An anomalous marker must be visible to the analysis, not silent."""

    def slow_get(url, timeout_s):
        time.sleep(0.05)
        return {
            "monotonic_ns": MARKER_MONOTONIC_NS,
            "wall_utc": MARKER_WALL_UTC,
        }

    monkeypatch.setattr(run_mod, "_http_get_json", slow_get)
    monkeypatch.setattr(run_mod, "CONTROLLER_MARKER_LAG_TOLERANCE_S", 0.01)
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
        expect_services=FIXTURE_SERVICES,
        controller_url="http://127.0.0.1:8000",
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["controller_marker"]["lag_s"] > 0.01
    deviation = next(
        d for d in manifest["deviations"] if d["kind"] == "confirmation_marker_lag"
    )
    assert deviation["authorized_by_flag"] is None
    assert any("confirmation marker" in w for w in manifest["warnings"])
    # The deadline is still anchored on the controller's clock domain and the
    # 60 s window value is untouched; only the anomaly is recorded.
    assert manifest["confirmation_deadline_clock_domain"] == "controller"
    assert manifest["confirmation_window_s"] == 60


# ---------------------------------------------------------------------------
# P5.1 item 3 (report 5.4): mandatory artefacts per condition kind
# ---------------------------------------------------------------------------


def test_missing_sent_events_invalidates_and_withholds_the_seal(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """A missing sent_events.jsonl used to be a warning; an incomplete run
    must never look sealed (report 5.4)."""
    real = run_mod._run_subprocess

    def no_sent_events(cmd, log_path, timeout_s):
        rc = real(cmd, log_path, timeout_s)
        out_dir = Path(cmd[cmd.index("--output") + 1])
        run_id = cmd[cmd.index("--run-id") + 1]
        (out_dir / run_id / "sent_events.jsonl").unlink()
        return rc

    monkeypatch.setattr(run_mod, "_run_subprocess", no_sent_events)
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
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
    )
    assert rc == 1
    run_dir = base / "raw" / "smoke_sequence-r01"
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "invalid"
    assert "sent_events.jsonl" in manifest["missing_mandatory_artifacts"]
    assert any(
        "sent_events.jsonl" in reason for reason in manifest["validity_reasons"]
    )
    assert not (run_dir / checksums.SUMS_FILENAME).exists()


def test_controller_metrics_are_mandatory_where_the_protocol_mandates_them(
    tmp_path, plan_path, fast_run
) -> None:
    base = tmp_path / "results"
    run_id = "load_sweep-010mps-r01"
    rc = run_mod.execute_run(
        plan_path,
        run_id,
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        # load_sweep prescribes a 120 s cooldown; skipping it keeps this
        # unit test instantaneous (the deviation is recorded, and this test
        # asserts nothing about cooldowns).
        skip_cooldown=True,
        event_log_dir=_local_events(tmp_path, run_id),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
    )
    assert rc == 1
    manifest = _manifest(base, run_id)
    assert "controller_metrics.csv" in manifest["missing_mandatory_artifacts"]
    assert not (base / "raw" / run_id / checksums.SUMS_FILENAME).exists()


def test_mandatory_artifacts_respect_the_allow_missing_resources_override(
    tmp_path, plan_path, fast_run
) -> None:
    """An explicitly authorized absence is not a missing mandatory artefact:
    the run stays sealed (and the deviation is recorded)."""
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        allow_missing_resources=True,
        allow_missing_controller_marker=True,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["missing_mandatory_artifacts"] == []
    assert (base / "raw" / "smoke_sequence-r01" / checksums.SUMS_FILENAME).is_file()


# ---------------------------------------------------------------------------
# P5.1 item 8 (report 5.4): semantic validation of resources.csv
# ---------------------------------------------------------------------------


def _csv(tmp_path: Path, name: str, rows: list[str]) -> Path:
    path = tmp_path / name
    path.write_text(
        "\n".join([RESOURCES_HEADER] + rows) + "\n", encoding="utf-8"
    )
    return path


def test_validate_resources_csv_requires_parseable_timestamps(tmp_path) -> None:
    bad = _csv(
        tmp_path,
        "bad-ts.csv",
        [f"not-a-timestamp,egw-controller,10.0,1024,1.0,{SUT_NODE}"] * 40,
    )
    problems = " ".join(resources_mod.validate_resources_csv(bad))
    assert "timestamp" in problems


def test_validate_resources_csv_requires_distinct_sample_instants(tmp_path) -> None:
    """Thirty rows may be six containers at five instants (report 5.4)."""
    rows = [
        f"2026-09-07T10:00:{i:02d}Z,egw-{c},10.0,1024,1.0,{SUT_NODE}"
        for i in range(5)
        for c in range(8)
    ]
    path = _csv(tmp_path, "few-instants.csv", rows)
    problems = " ".join(resources_mod.validate_resources_csv(path))
    assert "distinct sample instant" in problems


def test_validate_resources_csv_requires_non_decreasing_timestamps(tmp_path) -> None:
    rows = [
        f"2026-09-07T10:00:{i:02d}Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
        for i in range(40)
    ]
    rows[20] = f"2026-09-07T09:59:00Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
    path = _csv(tmp_path, "unordered.csv", rows)
    problems = " ".join(resources_mod.validate_resources_csv(path))
    assert "non-decreasing" in problems


def test_validate_resources_csv_requires_numeric_cpu_and_memory(tmp_path) -> None:
    rows = [
        f"2026-09-07T10:00:{i:02d}Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
        for i in range(40)
    ]
    rows[3] = f"2026-09-07T10:00:03Z,egw-controller,n/a,1024,1.0,{SUT_NODE}"
    rows[4] = f"2026-09-07T10:00:04Z,egw-controller,10.0,,1.0,{SUT_NODE}"
    path = _csv(tmp_path, "non-numeric.csv", rows)
    problems = " ".join(resources_mod.validate_resources_csv(path))
    assert "cpu_pct" in problems
    assert "mem_bytes" in problems


def test_validate_resources_csv_requires_complete_columns(tmp_path) -> None:
    rows = [
        f"2026-09-07T10:00:{i:02d}Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
        for i in range(40)
    ]
    rows[7] = "2026-09-07T10:00:07Z,egw-controller,10.0"
    path = _csv(tmp_path, "short-row.csv", rows)
    problems = " ".join(resources_mod.validate_resources_csv(path))
    assert "column" in problems


def test_validate_resources_csv_checks_coverage_of_the_measured_window(
    tmp_path,
) -> None:
    """Thirty rows can be five seconds of six containers (report 5.4)."""
    path = _resources_file(tmp_path, name="short-window.csv")  # spans 39 s
    assert resources_mod.validate_resources_csv(path, expected_window_s=40.0) == []
    problems = " ".join(
        resources_mod.validate_resources_csv(path, expected_window_s=300.0)
    )
    assert "covered" in problems
    assert "measured window" in problems


def test_validate_resources_csv_uses_the_real_utc_window_not_only_duration(
    tmp_path,
) -> None:
    """A same-length CSV from a different hour is not this run's evidence."""
    path = _resources_file(tmp_path, name="wrong-real-window.csv")
    problems = " ".join(
        resources_mod.validate_resources_csv(
            path,
            expected_window_s=40.0,
            expected_window_start_utc="2026-09-07T11:00:00Z",
            expected_window_end_utc="2026-09-07T11:00:40Z",
        )
    )
    assert "do not effectively overlap" in problems
    assert "real measured window" in problems


def test_validate_resources_csv_requires_90_percent_real_window_coverage(
    tmp_path,
) -> None:
    # 36 one-second instants span 35 s of a 40 s window: 87.5%.
    path = _resources_file(tmp_path, rows=36, name="partial-real-window.csv")
    problems = " ".join(
        resources_mod.validate_resources_csv(
            path,
            expected_window_start_utc="2026-09-07T10:00:00Z",
            expected_window_end_utc="2026-09-07T10:00:40Z",
        )
    )
    assert "87.5%" in problems
    assert "below the required 90%" in problems


def test_validate_resources_csv_rejects_a_gap_above_the_protocol_cap(
    tmp_path,
) -> None:
    rows = [
        f"2026-09-07T10:00:{i:02d}Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
        for i in [*range(20), *range(30, 50)]
    ]
    path = _csv(tmp_path, "resource-gap.csv", rows)
    problems = " ".join(
        resources_mod.validate_resources_csv(
            path,
            expected_window_start_utc="2026-09-07T10:00:00Z",
            expected_window_end_utc="2026-09-07T10:00:49Z",
        )
    )
    assert "sampling gap" in problems
    assert "MAX_SAMPLE_GAP_S" in problems
    assert "11.0 s" in problems


def test_validate_resources_csv_requires_coverage_for_every_container(
    tmp_path,
) -> None:
    rows: list[str] = []
    for second in range(40):
        stamp = f"2026-09-07T10:00:{second:02d}Z"
        rows.append(
            f"{stamp},egw-controller,10.0,1024,1.0,{SUT_NODE}"
        )
        if second < 5:
            rows.append(f"{stamp},ditto,8.0,2048,2.0,{SUT_NODE}")
    path = _csv(tmp_path, "sparse-container.csv", rows)

    problems = " ".join(
        resources_mod.validate_resources_csv(
            path,
            expected_window_start_utc="2026-09-07T10:00:00Z",
            expected_window_end_utc="2026-09-07T10:00:40Z",
        )
    )

    assert "container 'ditto'" in problems
    assert "below the required 90%" in problems
    assert "sampling gap" in problems


def test_execute_run_rejects_resources_from_a_different_real_window(
    tmp_path, plan_path, fast_run
) -> None:
    rows = [
        f"2026-09-07T11:00:{i:02d}Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
        for i in range(40)
    ]
    path = _csv(tmp_path, "wrong-run.csv", rows)
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=path,
        allow_missing_controller_marker=True,
    )
    assert rc == 1
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["resource_source"] == "none"
    assert any("do not effectively overlap" in w for w in manifest["warnings"])


# ---------------------------------------------------------------------------
# P5.4 defect 4: strict numeric rule at ingest (finite and non-negative)
# ---------------------------------------------------------------------------


def _good_rows(count: int = 40) -> list[str]:
    return [
        f"2026-09-07T10:00:{i:02d}Z,egw-controller,10.0,1024,1.0,{SUT_NODE}"
        for i in range(count)
    ]


def test_validate_resources_csv_rejects_non_finite_values(tmp_path) -> None:
    """float('nan'/'inf') parse fine but are not measurements."""
    rows = _good_rows()
    rows[5] = f"2026-09-07T10:00:05Z,egw-controller,nan,1024,1.0,{SUT_NODE}"
    rows[6] = f"2026-09-07T10:00:06Z,egw-controller,10.0,inf,1.0,{SUT_NODE}"
    rows[7] = f"2026-09-07T10:00:07Z,egw-controller,10.0,1024,-Infinity,{SUT_NODE}"
    path = _csv(tmp_path, "non-finite.csv", rows)
    problems = " ".join(resources_mod.validate_resources_csv(path))
    assert "non-finite" in problems
    # The reason names the column AND the row.
    assert "cpu_pct" in problems and "line 7" in problems
    assert "mem_bytes" in problems and "line 8" in problems
    assert "mem_pct" in problems and "line 9" in problems


def test_validate_resources_csv_rejects_negative_values(tmp_path) -> None:
    rows = _good_rows()
    rows[9] = f"2026-09-07T10:00:09Z,egw-controller,-0.5,1024,1.0,{SUT_NODE}"
    rows[10] = f"2026-09-07T10:00:10Z,egw-controller,10.0,-1,1.0,{SUT_NODE}"
    path = _csv(tmp_path, "negative.csv", rows)
    problems = " ".join(resources_mod.validate_resources_csv(path))
    assert "negative" in problems
    assert "cpu_pct" in problems and "line 11" in problems
    assert "mem_bytes" in problems and "line 12" in problems


def test_a_non_finite_resources_csv_is_not_ingestible(
    tmp_path, plan_path, fast_run
) -> None:
    """A rejected file is treated as MISSING resources: the timed run is
    invalid, with the reason naming the defect."""
    rows = _good_rows()
    rows[5] = f"2026-09-07T10:00:05Z,egw-controller,Infinity,1024,1.0,{SUT_NODE}"
    path = _csv(tmp_path, "wire-infinity.csv", rows)
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=path,
        allow_missing_controller_marker=True,
    )
    assert rc == 1
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["resource_source"] == "none"
    assert any("non-finite" in w for w in manifest["warnings"])


# ---------------------------------------------------------------------------
# P5.4 defect 4 (writer side): controller_metrics.csv never records
# non-finite / negative / non-integer counters
# ---------------------------------------------------------------------------


def _metrics_rows(path: Path) -> list[list[str]]:
    import csv

    with open(path, "r", encoding="utf-8", newline="") as fh:
        return [row for row in csv.reader(fh) if row]


def test_fetch_metrics_rejects_the_json_non_finite_constants(monkeypatch) -> None:
    """json.loads accepts the NaN/Infinity JSON constants by default; the
    metrics snapshot must not."""

    class _Resp:
        def read(self):
            return b'{"accepted": 1, "queue_depth": Infinity}'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        metrics_mod.urllib.request, "urlopen", lambda url, timeout=None: _Resp()
    )
    with pytest.raises(ValueError):
        metrics_mod.fetch_metrics("http://127.0.0.1:8000")


def test_metrics_sampler_writes_empty_for_non_finite_or_negative_counters(
    tmp_path, monkeypatch
) -> None:
    snapshot = {
        "accepted": 5,
        "rejected": float("inf"),
        "duplicate": float("nan"),
        "failed": -1,
        "dropped": 2.5,
        "queue_depth": 3,
    }
    monkeypatch.setattr(
        metrics_mod, "fetch_metrics", lambda url, *a, **k: dict(snapshot)
    )
    csv_path = tmp_path / "controller_metrics.csv"
    with metrics_mod.ControllerMetricsSampler(
        csv_path, "http://127.0.0.1:8000", interval_s=60.0
    ) as sampler:
        pass
    rows = _metrics_rows(csv_path)
    assert rows[0] == metrics_mod.CSV_HEADER
    assert rows[1:]
    for row in rows[1:]:
        # inf/nan/negative/non-integer counters are written as EMPTY cells,
        # never as 'inf'/'nan'/'-1'/'2.5'.
        assert row[1:7] == ["5", "", "", "", "", "3"]
        # The ten item-18 columns follow (ADR 0011); this snapshot carries
        # none of them, so they are empty, never zero.
        assert row[7:] == [""] * (len(metrics_mod.CSV_HEADER) - 7)
    assert sampler.invalid_values >= 4
    assert "dropped" in (sampler.last_invalid or "")


# ---------------------------------------------------------------------------
# ADR 0011 item 18 (T41): the ten /metrics fields the sampler used to discard
# ---------------------------------------------------------------------------


#: The new columns after queue_depth, in the fixed order: five counts, then
#: the truth value, two strings and two numbers written verbatim.
ITEM18_COLUMNS = [
    "received",
    "in_progress",
    "processing_errors",
    "unacked",
    "mqtt_connection",
    "mqtt_subscribed",
    "started_at",
    "wall_utc",
    "uptime_s",
    "monotonic_ns",
]

SIX_COUNTERS = {
    "accepted": 5,
    "rejected": 0,
    "duplicate": 1,
    "failed": 0,
    "dropped": 0,
    "queue_depth": 3,
}


def _sample_one_row(tmp_path: Path, monkeypatch, snapshot: dict) -> tuple[dict, Any]:
    """One sampler pass over a recorded snapshot: (cells by column, sampler)."""
    monkeypatch.setattr(
        metrics_mod, "fetch_metrics", lambda url, *a, **k: dict(snapshot)
    )
    csv_path = tmp_path / "controller_metrics.csv"
    with metrics_mod.ControllerMetricsSampler(
        csv_path, "http://127.0.0.1:8000", interval_s=60.0
    ) as sampler:
        pass
    rows = _metrics_rows(csv_path)
    assert rows[0] == metrics_mod.CSV_HEADER
    assert rows[1:]
    assert all(len(row) == len(metrics_mod.CSV_HEADER) for row in rows[1:])
    return dict(zip(metrics_mod.CSV_HEADER, rows[1])), sampler


def test_metrics_csv_header_gains_the_item_18_columns_in_order() -> None:
    assert metrics_mod.CSV_HEADER == [
        "ts_utc",
        "accepted",
        "rejected",
        "duplicate",
        "failed",
        "dropped",
        "queue_depth",
        *ITEM18_COLUMNS,
    ]
    # The count rule covers the five integer fields, the raw rule the other
    # five; the header is exactly the two tuples behind the timestamp.
    assert metrics_mod.METRIC_FIELDS == (
        "accepted",
        "rejected",
        "duplicate",
        "failed",
        "dropped",
        "queue_depth",
        "received",
        "in_progress",
        "processing_errors",
        "unacked",
        "mqtt_connection",
    )
    assert metrics_mod.RAW_FIELDS == (
        "mqtt_subscribed",
        "started_at",
        "wall_utc",
        "uptime_s",
        "monotonic_ns",
    )
    assert metrics_mod.CSV_HEADER == [
        "ts_utc",
        *metrics_mod.METRIC_FIELDS,
        *metrics_mod.RAW_FIELDS,
    ]


def test_metrics_sampler_records_the_item_18_fields_verbatim(
    tmp_path, monkeypatch
) -> None:
    snapshot = {
        **SIX_COUNTERS,
        "received": 9,
        "in_progress": 1,
        "processing_errors": 0,
        "unacked": 2,
        "mqtt_connection": 1,
        "mqtt_subscribed": True,
        "started_at": "2026-09-07T09:58:00.000Z",
        "wall_utc": "2026-09-07T10:00:00.250Z",
        "uptime_s": 120.25,
        "monotonic_ns": 987_654_321_000,
    }
    cells, sampler = _sample_one_row(tmp_path, monkeypatch, snapshot)
    assert [cells[c] for c in ITEM18_COLUMNS] == [
        "9",
        "1",
        "0",
        "2",
        "1",
        "true",
        "2026-09-07T09:58:00.000Z",
        "2026-09-07T10:00:00.250Z",
        "120.25",
        "987654321000",
    ]
    assert cells["accepted"] == "5" and cells["queue_depth"] == "3"
    assert sampler.invalid_values == 0

    cells, sampler = _sample_one_row(
        tmp_path,
        monkeypatch,
        {**snapshot, "mqtt_subscribed": False, "uptime_s": 7, "mqtt_connection": 2.0},
    )
    assert cells["mqtt_subscribed"] == "false"
    assert cells["uptime_s"] == "7"
    assert cells["mqtt_connection"] == "2"
    assert sampler.invalid_values == 0


def test_metrics_sampler_leaves_absent_item_18_fields_empty_never_zero(
    tmp_path, monkeypatch
) -> None:
    """A controller that predates the fields sends none of them: every new
    cell stays empty (missing evidence), and absence is not a refusal."""
    cells, sampler = _sample_one_row(tmp_path, monkeypatch, dict(SIX_COUNTERS))
    assert [cells[c] for c in ITEM18_COLUMNS] == [""] * len(ITEM18_COLUMNS)
    assert [cells[c] for c in SIX_COUNTERS] == ["5", "0", "1", "0", "0", "3"]
    assert sampler.invalid_values == 0


def test_metrics_sampler_refuses_mistyped_item_18_values(tmp_path, monkeypatch) -> None:
    """A count that is a bool, negative, fractional, a string or infinite; a
    truth value that is a string; a string that is a number or a list; a
    number that is nan or a bool: each is an empty cell and a counted
    refusal, never a coerced value."""
    snapshot = {
        **SIX_COUNTERS,
        "received": True,
        "in_progress": -1,
        "processing_errors": 2.5,
        "unacked": "3",
        "mqtt_connection": float("inf"),
        "mqtt_subscribed": "true",
        "started_at": 12,
        "wall_utc": ["2026-09-07T10:00:00Z"],
        "uptime_s": float("nan"),
        "monotonic_ns": True,
    }
    cells, sampler = _sample_one_row(tmp_path, monkeypatch, snapshot)
    assert [cells[c] for c in ITEM18_COLUMNS] == [""] * len(ITEM18_COLUMNS)
    assert sampler.invalid_values >= len(ITEM18_COLUMNS)
    assert "monotonic_ns" in (sampler.last_invalid or "")


# ---------------------------------------------------------------------------
# ADR 0011 item 18: SUT log fetches, restart evidence steps and the
# configuration identity (T42)
# ---------------------------------------------------------------------------

# One fake stands for every item-18 step that runs a host command: the three
# log fetches, the two twin snapshots, the drain, the post-drain fetch and
# the harness events fetch. It appends '<label> <dest name> <run_id>' to a
# record file (so the ORDER of the steps is observable), prints on both
# streams and exits with the given code. Mode 'write[+option...]' writes
# {dest}: a twin snapshot as itest_reconcile's `snap` writes it when {dest}
# is twins.<label>.json (seed null), one event record of the run when it is
# events.post-drain.jsonl ('run:<id>' stamps another run id on it), and
# '<label> content for <run_id>' otherwise; 'sleep:<s>' waits that long
# first. Mode 'noop' writes nothing. Modes 'quiet' and 'gaveup' print what
# the runbook's `drained` helper prints when it succeeds (stdout) and when
# it gives up (stderr).
SUT_STEP_SCRIPT = """\
import json
import sys
import time
from pathlib import Path

record, label, run_id, dest, mode, rc = sys.argv[1:7]
flags = mode.split("+")
opts = dict(flag.partition(":")[::2] for flag in flags[1:])
with Path(record).open("a", encoding="utf-8") as fh:
    fh.write(" ".join((label, Path(dest).name, run_id)) + "\\n")
if "sleep" in opts:
    time.sleep(float(opts["sleep"]))
print(label + " step stdout")
sys.stderr.write(label + " step stderr\\n")
name = Path(dest).name
if flags[0] == "write":
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    if name.startswith("twins."):
        body = json.dumps({
            "label": name.split(".")[1],
            "seed": None,
            "devices": {"a" * 8: {"device_type": "smartwatch", "exists": True,
                                  "ingestion": {"accepted_count": 1}}},
        }) + "\\n"
    elif name == "events.post-drain.jsonl":
        body = json.dumps({"run_id": opts.get("run", run_id), "outcome": "accepted",
                           "seq": 0}) + "\\n"
    else:
        body = label + " content for " + run_id + "\\n"
    Path(dest).write_text(body, encoding="utf-8")
elif flags[0] == "quiet":
    print("drained: queue_depth 0 and identical counters on 27 consecutive readings "
          "over 130 s (0 0 0 true 2026-09-07T10:00:00Z 1 60 60 0 0 0 0 0) - an "
          "observation, not proof that processing has finished")
elif flags[0] == "gaveup":
    sys.stderr.write("STOP: drained: no quiet window of 130 s within 900 s (last "
                     "reading: 12 1 0 true 2026-09-07T10:00:00Z 1 60 40 0 0 0 0 0) - "
                     "do not take snapshots, do not start a run\\n")
sys.exit(int(rc))
"""

#: What the runbook's `drained` helper prints, as its transcript (both
#: streams through `tee`) carries it: the quiet line on success, the give-up
#: line at its limit.
DRAIN_QUIET_LINE = (
    "drained: queue_depth 0 and identical counters on 27 consecutive readings "
    "over 130 s (0 0 0 true 2026-09-07T10:00:00Z 1 60 60 0 0 0 0 0) - an "
    "observation, not proof that processing has finished\n"
)
DRAIN_GAVE_UP_LINE = (
    "STOP: drained: no quiet window of 130 s within 900 s (last reading: 12 1 0 "
    "true 2026-09-07T10:00:00Z 1 60 40 0 0 0 0 0) - do not take snapshots, do "
    "not start a run\n"
)
DRAIN_GET_FAILED_LINE = (
    "STOP: drained: GET http://127.0.0.1:8000/metrics failed or was not valid "
    "JSON, or a field was missing or of the wrong type\n"
)


def _plan_seed(plan_path: Path, run_id: str) -> int:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return int(next(r["seed"] for r in plan["runs"] if r["run_id"] == run_id))


def _twins_file(
    tmp_path: Path, label: str, *, seed: int | None = None, name: str | None = None, **overrides: Any
) -> Path:
    """A twin snapshot as itest_reconcile's `snap` writes it (label, seed,
    devices), with ``overrides`` applied on top."""
    doc: dict[str, Any] = {
        "label": label,
        "seed": seed,
        "devices": {
            "b" * 8: {"device_type": "smartwatch", "exists": True, "ingestion": {"accepted_count": 3}}
        },
    }
    doc.update(overrides)
    path = tmp_path / (name or f"external.twins.{label}.json")
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def _post_drain_events_file(
    tmp_path: Path, run_id: str, *, name: str = "external.events.post-drain.jsonl", lines: list[Any] | None = None
) -> Path:
    """The post-drain copy of a run's events.jsonl: one JSON object per line
    with this run's id and a logged outcome, unless ``lines`` says otherwise."""
    if lines is None:
        lines = [
            {"run_id": run_id, "outcome": "accepted", "seq": 0},
            {"run_id": run_id, "outcome": "duplicate", "seq": 0},
        ]
    path = tmp_path / name
    path.write_text(
        "".join((line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines),
        encoding="utf-8",
    )
    return path


def _drain_transcript(tmp_path: Path, text: str, *, name: str = "external.drained.txt") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path

RESTART_SCRIPT = """\
import sys
from pathlib import Path
Path(sys.argv[1]).write_text("restarted " + sys.argv[2], encoding="utf-8")
"""

SUT_LOG_FILES = {
    "broker_log": "logs/sut/broker.log",
    "controller_log": "logs/sut/controller.log",
    "docker_events": "logs/sut/docker-events.log",
}


def _step_tpl(
    script: Path, record: Path, label: str, mode: str = "write", rc: int = 0
) -> str:
    return (
        f'"{PY}" "{script.as_posix()}" "{record.as_posix()}" {label} '
        '{run_id} "{dest}" ' + f"{mode} {rc}"
    )


def _step_lines(record: Path) -> list[str]:
    """'<label> <dest name>' per recorded step, in execution order."""
    if not record.is_file():
        return []
    return [
        " ".join(line.split()[:2])
        for line in record.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _item18_run(
    tmp_path: Path,
    plan_path: Path,
    fast_run,
    monkeypatch,
    *,
    run_id: str = "controller_restart-r01",
    drain: tuple[str, int] = ("quiet", 0),
    snapshot: tuple[str, int] = ("write", 0),
    post_drain: tuple[str, int] = ("write", 0),
    log_fetch: dict[str, tuple[str, int]] | None = None,
    config_identity: bool = True,
    **overrides: Any,
) -> tuple[int, Path, Path]:
    """Execute one run with every item-18 step driven by the fake script.

    Returns (exit code, run directory, record file). The fake simulator is
    made visible in the record ('simulator - <run_id>') so the position of
    the 'before' snapshot against the measured run can be asserted."""
    script = _write_script(tmp_path, "sut_step.py", SUT_STEP_SCRIPT)
    record = tmp_path / "sut-steps.txt"
    restart_script = _write_script(tmp_path, "fake_restart.py", RESTART_SCRIPT)
    marker = tmp_path / "restart-marker.txt"

    def recording_subprocess(cmd, log_path, timeout_s):
        with record.open("a", encoding="utf-8") as fh:
            fh.write("simulator - " + cmd[cmd.index("--run-id") + 1] + "\n")
        return fast_run(cmd, log_path, timeout_s)

    monkeypatch.setattr(run_mod, "_run_subprocess", recording_subprocess)
    log_fetch = log_fetch or {}
    base = tmp_path / "results"
    kwargs: dict[str, Any] = dict(
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        fetch_events_cmd=_step_tpl(script, record, "events"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
        expect_services=FIXTURE_SERVICES,
        restart_cmd=(
            f'"{PY}" "{restart_script.as_posix()}" "{marker.as_posix()}" {{run_id}}'
        ),
        restart_at_s=0.05,
        twin_snapshot_cmd=_step_tpl(script, record, "snapshot", *snapshot),
        drain_cmd=_step_tpl(script, record, "drain", *drain),
        post_drain_fetch_cmd=_step_tpl(script, record, "post_drain", *post_drain),
        fetch_broker_log_cmd=_step_tpl(
            script, record, "broker_log", *log_fetch.get("broker_log", ("write", 0))
        ),
        fetch_controller_log_cmd=_step_tpl(
            script,
            record,
            "controller_log",
            *log_fetch.get("controller_log", ("write", 0)),
        ),
        fetch_docker_events_cmd=_step_tpl(
            script,
            record,
            "docker_events",
            *log_fetch.get("docker_events", ("write", 0)),
        ),
        allow_missing_controller_marker=True,
    )
    if config_identity:
        kwargs["config_identity_from"] = _config_identity_file(tmp_path)
    kwargs.update(overrides)
    # Keep the measured (fake) run alive while the restart timer fires.
    fast_run.sleep_s = 1.0 if kwargs.get("restart_cmd") else 0.0
    rc = run_mod.execute_run(plan_path, run_id, **kwargs)
    return rc, base / "raw" / run_id, record


def test_sut_log_fetch_hooks_run_after_the_events_fetch_into_logs_sut_and_are_sealed(
    tmp_path, plan_path, fast_run
) -> None:
    """The broker log, the controller container log and docker events are
    fetched through the collector-hook machinery into logs/sut/, after the
    harness events fetch, recorded in the manifest and sealed."""
    script = _write_script(tmp_path, "sut_step.py", SUT_STEP_SCRIPT)
    record = tmp_path / "sut-steps.txt"
    base = tmp_path / "results"
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        fetch_events_cmd=_step_tpl(script, record, "events"),
        sut_env_from=_sut_env_file(tmp_path),
        resources_from=_resources_file(tmp_path),
        expect_services=FIXTURE_SERVICES,
        fetch_broker_log_cmd=_step_tpl(script, record, "broker_log"),
        fetch_controller_log_cmd=_step_tpl(script, record, "controller_log"),
        fetch_docker_events_cmd=_step_tpl(script, record, "docker_events"),
        allow_missing_controller_marker=True,
    )
    assert rc == 0
    assert _step_lines(record) == [
        "events events.jsonl",
        "broker_log broker.log",
        "controller_log controller.log",
        "docker_events docker-events.log",
    ]
    run_dir = base / "raw" / "smoke_sequence-r01"
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["manifest_version"] == run_mod.MANIFEST_VERSION == "1.4"
    assert manifest["validity"] == "valid"
    fetches = manifest["sut_log_fetches"]
    assert [f["hook"] for f in fetches] == list(SUT_LOG_FILES)
    sealed = _sealed_names(run_dir)
    for fetch in fetches:
        hook = fetch["hook"]
        assert fetch["flag"] == run_mod.SUT_LOG_FETCH_FLAGS[hook]
        assert fetch["returncode"] == 0
        assert fetch["started_utc"] and fetch["finished_utc"]
        assert "{run_id}" not in fetch["command"] and "{dest}" not in fetch["command"]
        assert "smoke_sequence-r01" in fetch["command"]
        assert fetch["dest_file"] == SUT_LOG_FILES[hook]
        assert fetch["dest_exists"] is True
        assert (run_dir / fetch["dest_file"]).read_text(encoding="utf-8") == (
            f"{hook} content for smoke_sequence-r01\n"
        )
        assert fetch["stdout_file"] == f"logs/sut/hook-{hook}.stdout.txt"
        assert fetch["stderr_file"] == f"logs/sut/hook-{hook}.stderr.txt"
        assert fetch["stderr_tail"] == f"{hook} step stderr"
        assert fetch["dest_file"] in sealed
        assert fetch["stdout_file"] in sealed and fetch["stderr_file"] in sealed
    assert checksums.verify_sha256sums(run_dir) == []
    cli = manifest["config"]["cli"]
    for key in ("fetch_broker_log_cmd", "fetch_controller_log_cmd", "fetch_docker_events_cmd"):
        assert cli[key] and "{dest}" in cli[key]
    # Nothing of the restart-only evidence on a nominal run.
    assert manifest["twin_snapshots"] == []
    assert manifest["drain"] is None
    assert manifest["events_post_drain_fetch"] is None


def test_sut_log_fetch_failure_is_a_validity_reason_naming_the_flag(
    tmp_path, plan_path, fast_run
) -> None:
    """A fetch that exits non-zero, or one that exits 0 without writing its
    file, is never a silent warning; the other fetches still run and the
    seal is still written (the fetched logs are not mandatory artefacts)."""
    script = _write_script(tmp_path, "sut_step.py", SUT_STEP_SCRIPT)
    record = tmp_path / "sut-steps.txt"
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
        expect_services=FIXTURE_SERVICES,
        fetch_broker_log_cmd=_step_tpl(script, record, "broker_log", "write", 2),
        fetch_controller_log_cmd=_step_tpl(script, record, "controller_log", "noop", 0),
        fetch_docker_events_cmd=_step_tpl(script, record, "docker_events"),
        allow_missing_controller_marker=True,
    )
    assert rc == 1
    assert _step_lines(record) == [
        "broker_log broker.log",
        "controller_log controller.log",
        "docker_events docker-events.log",
    ]
    run_dir = base / "raw" / "smoke_sequence-r01"
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "invalid"
    reasons = manifest["validity_reasons"]
    broker = next(r for r in reasons if "--fetch-broker-log-cmd" in r)
    assert "exit code 2" in broker
    controller = next(r for r in reasons if "--fetch-controller-log-cmd" in r)
    assert "logs/sut/controller.log" in controller
    assert not any("--fetch-docker-events-cmd" in r for r in reasons)
    by_hook = {f["hook"]: f for f in manifest["sut_log_fetches"]}
    assert by_hook["broker_log"]["returncode"] == 2
    assert by_hook["controller_log"]["returncode"] == 0
    assert by_hook["controller_log"]["dest_exists"] is False
    assert by_hook["docker_events"]["dest_exists"] is True
    sealed = _sealed_names(run_dir)
    assert "logs/sut/docker-events.log" in sealed
    assert checksums.verify_sha256sums(run_dir) == []


def test_controller_restart_evidence_steps_run_in_order_and_are_sealed(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """For controller_restart: a twin snapshot before the measured run, the
    harness events fetch after the confirmation window, then the blocking
    drain, the post-drain fetch into its own file, the second snapshot and
    the log fetches; every file exists before the seal and every step is in
    the manifest."""
    rc, run_dir, record = _item18_run(tmp_path, plan_path, fast_run, monkeypatch)
    assert rc == 0
    assert _step_lines(record) == [
        "snapshot twins.before.json",
        "simulator -",
        "events events.jsonl",
        "drain drain.txt",
        "post_drain events.post-drain.jsonl",
        "snapshot twins.after.json",
        "broker_log broker.log",
        "controller_log controller.log",
        "docker_events docker-events.log",
    ]
    base = run_dir.parent.parent
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["manifest_version"] == "1.4"
    assert manifest["validity"] == "valid"
    assert manifest["restart"]["executed"] is True
    sealed = _sealed_names(run_dir)

    snapshots = manifest["twin_snapshots"]
    assert [s["hook"] for s in snapshots] == [
        "twin_snapshot_before",
        "twin_snapshot_after",
    ]
    assert [s["file"] for s in snapshots] == ["twins.before.json", "twins.after.json"]
    for snap, label in zip(snapshots, ("before", "after")):
        assert snap["flag"] == "--twin-snapshot-cmd"
        assert snap["returncode"] == 0
        assert snap["dest_exists"] is True
        # The hook's file is verified like an ingested one (F6): a snapshot
        # of the right label with a devices object.
        assert snap["source"] == "hook"
        assert snap["verified"] is True and snap["problems"] == []
        written = json.loads((run_dir / snap["file"]).read_text(encoding="utf-8"))
        assert written["label"] == label and written["devices"]
        assert snap["stdout_file"] == f"logs/sut/hook-{snap['hook']}.stdout.txt"
        assert snap["file"] in sealed and snap["stdout_file"] in sealed

    drain = manifest["drain"]
    assert drain["hook"] == "drain" and drain["flag"] == "--drain-cmd"
    assert drain["returncode"] == 0
    assert drain["source"] == "hook"
    assert drain["outcome"] == "quiet" and drain["verified"] is True
    assert drain["started_utc"] and drain["finished_utc"]
    assert drain["stdout_file"] == "logs/sut/hook-drain.stdout.txt"
    assert drain["stdout_file"] in sealed and drain["stderr_file"] in sealed
    assert not any("failed recovery" in w for w in manifest["warnings"])

    post_drain = manifest["events_post_drain_fetch"]
    assert post_drain["ok"] is True
    assert post_drain["file"] == "events.post-drain.jsonl"
    assert post_drain["source"] == "hook"
    assert post_drain["verified"] is True and post_drain["problems"] == []
    assert post_drain["template"] and "{dest}" not in post_drain["command"]
    assert post_drain["attempts"][0]["returncode"] == 0
    # The two event copies are kept apart: the harness fetch is untouched.
    assert (run_dir / "events.jsonl").read_text(encoding="utf-8") == (
        "events content for controller_restart-r01\n"
    )
    assert json.loads(
        (run_dir / "events.post-drain.jsonl").read_text(encoding="utf-8")
    ) == {"run_id": "controller_restart-r01", "outcome": "accepted", "seq": 0}
    assert manifest["events_source"].startswith("fetch-cmd:")
    assert "events.jsonl" in sealed and "events.post-drain.jsonl" in sealed

    assert manifest["configuration_identity"] == CONFIG_IDENTITY
    assert manifest["configuration_identity_file"] == "configuration_identity.json"
    assert json.loads(
        (run_dir / "configuration_identity.json").read_text(encoding="utf-8")
    ) == CONFIG_IDENTITY
    assert "configuration_identity.json" in sealed

    for hook, path in SUT_LOG_FILES.items():
        assert path in sealed
    assert checksums.verify_sha256sums(run_dir) == []
    cli = manifest["config"]["cli"]
    for key in ("twin_snapshot_cmd", "drain_cmd", "post_drain_fetch_cmd"):
        assert cli[key] and "{run_id}" in cli[key]
    assert cli["config_identity_from"] == str(tmp_path / "configuration_identity.json")
    for key in ("twins_before_from", "twins_after_from", "post_drain_events_from", "drain_transcript_from"):
        assert cli[key] is None
    assert "allow_missing_restart_evidence" not in cli
    assert "allow_missing_restart_evidence" not in manifest


def test_controller_restart_drain_failure_is_a_validity_reason(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """A drain that ends without either of the helper's lines (here: exit 3
    and no STOP line) is an instrument failure: outcome 'error', a reason."""
    rc, run_dir, record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, drain=("noop", 3)
    )
    assert rc == 1
    # The steps after the drain still run: the evidence is collected as it is.
    assert _step_lines(record)[3:6] == [
        "drain drain.txt",
        "post_drain events.post-drain.jsonl",
        "snapshot twins.after.json",
    ]
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert manifest["validity"] == "invalid"
    reason = next(r for r in manifest["validity_reasons"] if "--drain-cmd" in r)
    assert "exit code 3" in reason and "instrument failure" in reason
    assert manifest["drain"]["returncode"] == 3
    assert manifest["drain"]["outcome"] == "error"
    assert manifest["drain"]["verified"] is False
    assert (run_dir / checksums.SUMS_FILENAME).is_file()


def test_a_drain_that_exits_0_without_the_quiet_line_is_an_instrument_failure(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    rc, run_dir, _record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, drain=("noop", 0)
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert manifest["drain"]["outcome"] == "error"
    reason = next(r for r in manifest["validity_reasons"] if "--drain-cmd" in r)
    assert "exit code 0" in reason and "quiet line" in reason


def test_a_drain_that_gave_up_is_a_valid_observation_of_failed_recovery(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """F2: complete instrumentation, the drain reaches the helper's limit
    (the STOP line on stderr, exit 1): outcome 'gave-up', recorded with a
    warning, never a validity reason; the run is valid and sealed, and the
    steps after the drain still run and are recorded."""
    rc, run_dir, record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, drain=("gaveup", 1)
    )
    assert rc == 0
    assert _step_lines(record)[3:6] == [
        "drain drain.txt",
        "post_drain events.post-drain.jsonl",
        "snapshot twins.after.json",
    ]
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert manifest["validity"] == "valid" and manifest["validity_reasons"] == []
    drain = manifest["drain"]
    assert drain["outcome"] == "gave-up"
    assert drain["returncode"] == 1 and drain["verified"] is True
    assert "STOP: drained: no quiet window" in drain["stderr_tail"]
    assert run_dir.joinpath(drain["stderr_file"]).read_text(encoding="utf-8").endswith(
        DRAIN_GAVE_UP_LINE
    )
    (warning,) = [w for w in manifest["warnings"] if "failed recovery" in w]
    assert "not observed quiet within the helper's limit" in warning
    assert "retained" in warning
    assert not any(d["kind"] == "missing_restart_evidence" for d in manifest["deviations"])
    assert (run_dir / checksums.SUMS_FILENAME).is_file()
    assert checksums.verify_sha256sums(run_dir) == []
    assert manifest["events_post_drain_fetch"]["verified"] is True
    assert [s["file"] for s in manifest["twin_snapshots"]] == [
        "twins.before.json",
        "twins.after.json",
    ]


@pytest.mark.parametrize(
    "text, returncode, expected",
    [
        (DRAIN_QUIET_LINE, 0, "quiet"),
        ("noise\n" + DRAIN_QUIET_LINE, 0, "quiet"),
        (DRAIN_QUIET_LINE, None, "quiet"),
        (DRAIN_GAVE_UP_LINE, 1, "gave-up"),
        (DRAIN_GAVE_UP_LINE, None, "gave-up"),
        (DRAIN_QUIET_LINE, 1, "error"),  # the exit code contradicts the line
        (DRAIN_GAVE_UP_LINE, 0, "error"),
        (DRAIN_GET_FAILED_LINE, 1, "error"),  # the helper's other stop
        ("", 0, "error"),
        ("", None, "error"),
        (DRAIN_QUIET_LINE + DRAIN_GAVE_UP_LINE, None, "error"),  # both lines
        ("  " + DRAIN_QUIET_LINE, 0, "error"),  # a prefix, not an indented copy
    ],
)
def test_classify_drain_output(text, returncode, expected) -> None:
    assert run_mod.classify_drain_output(text, returncode) == expected
    assert expected in run_mod.DRAIN_OUTCOMES


@pytest.mark.parametrize(
    "snapshot, expected",
    [
        (("noop", 0), "twins.after.json"),  # exit 0 but no file written
        (("write", 4), "exit code 4"),
    ],
)
def test_controller_restart_twin_snapshot_failure_is_a_validity_reason(
    tmp_path, plan_path, fast_run, monkeypatch, snapshot, expected
) -> None:
    rc, run_dir, _record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, snapshot=snapshot
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert manifest["validity"] == "invalid"
    reasons = [r for r in manifest["validity_reasons"] if "--twin-snapshot-cmd" in r]
    assert len(reasons) == 2  # one per snapshot
    assert any(expected in r for r in reasons)
    assert any("twins.before.json" in r for r in reasons)


def test_controller_restart_post_drain_fetch_failure_is_a_validity_reason(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    rc, run_dir, _record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, post_drain=("noop", 1)
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert manifest["validity"] == "invalid"
    reason = next(
        r for r in manifest["validity_reasons"] if "--post-drain-fetch-cmd" in r
    )
    assert "events.post-drain.jsonl" in reason
    post_drain = manifest["events_post_drain_fetch"]
    assert post_drain["ok"] is False
    assert len(post_drain["attempts"]) == run_mod.FETCH_ATTEMPTS
    assert not (run_dir / "events.post-drain.jsonl").exists()
    # The harness copy is untouched by the failed post-drain fetch.
    assert (run_dir / "events.jsonl").read_text(encoding="utf-8") == (
        "events content for controller_restart-r01\n"
    )


def test_controller_restart_without_a_configuration_identity_is_invalid(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    rc, run_dir, _record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, config_identity=False
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert manifest["validity"] == "invalid"
    reason = next(
        r for r in manifest["validity_reasons"] if "--config-identity-from" in r
    )
    assert "configuration_identity.json" in reason
    assert manifest["configuration_identity"] is None
    assert manifest["configuration_identity_file"] is None
    assert not (run_dir / "configuration_identity.json").exists()


def test_config_identity_path_that_does_not_exist_is_a_warning_and_a_restart_reason(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    rc, run_dir, _record = _item18_run(
        tmp_path,
        plan_path,
        fast_run,
        monkeypatch,
        config_identity=False,
        config_identity_from=tmp_path / "missing-identity.json",
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert any(
        "--config-identity-from" in w and "not found" in w for w in manifest["warnings"]
    )
    assert any("--config-identity-from" in r for r in manifest["validity_reasons"])
    assert manifest["configuration_identity"] is None


def test_config_identity_is_optional_but_embedded_on_other_conditions(
    tmp_path, plan_path, fast_run
) -> None:
    """A missing identity is a reason for controller_restart only; a nominal
    run stays valid without it and embeds it when given."""
    base = tmp_path / "results"
    common = dict(
        base_dir=base,
        no_tls=True,
        post_run_wait_s=0.0,
        sut_env_from=_sut_env_file(tmp_path),
        expect_services=FIXTURE_SERVICES,
        allow_missing_controller_marker=True,
    )
    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r01",
        event_log_dir=_local_events(tmp_path, "smoke_sequence-r01"),
        resources_from=_resources_file(tmp_path),
        **common,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert manifest["configuration_identity"] is None
    assert manifest["configuration_identity_file"] is None
    assert manifest["config"]["cli"]["config_identity_from"] is None

    rc = run_mod.execute_run(
        plan_path,
        "smoke_sequence-r02",
        event_log_dir=_local_events(tmp_path / "second", "smoke_sequence-r02"),
        resources_from=_resources_file(tmp_path / "second"),
        config_identity_from=_config_identity_file(tmp_path),
        **common,
    )
    assert rc == 0
    manifest = _manifest(base, "smoke_sequence-r02")
    assert manifest["validity"] == "valid"
    assert manifest["configuration_identity"] == CONFIG_IDENTITY
    assert manifest["configuration_identity_file"] == "configuration_identity.json"
    assert "configuration_identity.json" in _sealed_names(base / "raw" / "smoke_sequence-r02")


def test_restart_evidence_steps_are_ignored_with_a_warning_on_other_conditions(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """The drain, the twin snapshots and the post-drain fetch belong to the
    controller_restart condition; on any other run they are not executed,
    the manifest records none and a warning names the condition."""
    rc, run_dir, record = _item18_run(
        tmp_path,
        plan_path,
        fast_run,
        monkeypatch,
        run_id="smoke_sequence-r01",
        restart_cmd=None,
        restart_at_s=None,
    )
    assert rc == 0
    assert _step_lines(record) == [
        "simulator -",
        "events events.jsonl",
        "broker_log broker.log",
        "controller_log controller.log",
        "docker_events docker-events.log",
    ]
    manifest = _manifest(run_dir.parent.parent, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert manifest["twin_snapshots"] == []
    assert manifest["drain"] is None
    assert manifest["events_post_drain_fetch"] is None
    assert not (run_dir / "twins.before.json").exists()
    assert not (run_dir / "events.post-drain.jsonl").exists()
    ignored = [w for w in manifest["warnings"] if "controller_restart" in w]
    assert ignored
    assert all(
        flag in " ".join(ignored)
        for flag in ("--twin-snapshot-cmd", "--drain-cmd", "--post-drain-fetch-cmd")
    )
    # The identity is embedded on every condition when given.
    assert manifest["configuration_identity"] == CONFIG_IDENTITY


def test_collect_ingests_the_configuration_identity_and_reapplies_the_restart_reasons(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """'collect' adds a missing configuration_identity.json to a sealed run
    like the SUT environment, and re-applies the run-time evidence reasons
    it cannot recover (a failed drain stays a reason)."""
    rc, run_dir, _record = _item18_run(
        tmp_path,
        plan_path,
        fast_run,
        monkeypatch,
        config_identity=False,
        drain=("noop", 3),
    )
    assert rc == 1
    base = run_dir.parent.parent
    manifest = _manifest(base, "controller_restart-r01")
    reasons = " ".join(manifest["validity_reasons"])
    assert "--config-identity-from" in reasons and "--drain-cmd" in reasons
    assert (run_dir / checksums.SUMS_FILENAME).is_file()

    rc = run_mod.collect_run(
        "controller_restart-r01",
        base_dir=base,
        plan_path=plan_path,
        config_identity_from=_config_identity_file(tmp_path),
    )
    assert rc == 1  # the drain failed at run time; collect cannot undo that
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["configuration_identity"] == CONFIG_IDENTITY
    assert manifest["configuration_identity_file"] == "configuration_identity.json"
    reasons = manifest["validity_reasons"]
    assert not any("--config-identity-from" in r for r in reasons)
    assert any("--drain-cmd" in r for r in reasons)
    assert "configuration_identity.json" in _sealed_names(run_dir)
    assert checksums.verify_sha256sums(run_dir) == []
    added = [
        f for entry in manifest["collection_history"] for f in entry["added_files"]
    ]
    assert "configuration_identity.json" in added

    # Idempotent: the same file again is a no-op, a different one is refused.
    assert (
        run_mod.collect_run(
            "controller_restart-r01",
            base_dir=base,
            plan_path=plan_path,
            config_identity_from=_config_identity_file(tmp_path),
        )
        == 1
    )
    other = tmp_path / "other-identity.json"
    other.write_text(json.dumps({**CONFIG_IDENTITY, "a3_choice": "b"}), "utf-8")
    assert (
        run_mod.collect_run(
            "controller_restart-r01",
            base_dir=base,
            plan_path=plan_path,
            config_identity_from=other,
        )
        == 2
    )


EXTERNAL_EVIDENCE_CLI = [
    "--twins-before-from",
    "ev/before.json",
    "--twins-after-from",
    "ev/after.json",
    "--post-drain-events-from",
    "ev/events.post-drain.jsonl",
    "--drain-transcript-from",
    "ev/drained.txt",
]

EXTERNAL_EVIDENCE_KWARGS = {
    "twins_before_from": "ev/before.json",
    "twins_after_from": "ev/after.json",
    "post_drain_events_from": "ev/events.post-drain.jsonl",
    "drain_transcript_from": "ev/drained.txt",
}


def test_run_and_collect_cli_pass_the_item_18_flags_through(monkeypatch) -> None:
    from egw_experiments import cli

    seen: dict[str, dict] = {}

    def fake_execute_run(plan_path, run_id, **kwargs):
        seen["run"] = kwargs
        return 0

    def fake_collect_run(run_id, **kwargs):
        seen["collect"] = kwargs
        return 0

    monkeypatch.setattr(cli, "execute_run", fake_execute_run)
    monkeypatch.setattr(cli, "collect_run", fake_collect_run)
    assert (
        cli.main(
            [
                "run",
                "--run-id",
                "controller_restart-r01",
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
                "identity.json",
                *EXTERNAL_EVIDENCE_CLI,
            ]
        )
        == 0
    )
    run_kwargs = seen["run"]
    assert run_kwargs["fetch_broker_log_cmd"] == "broker {dest}"
    assert run_kwargs["fetch_controller_log_cmd"] == "controller {dest}"
    assert run_kwargs["fetch_docker_events_cmd"] == "events {dest}"
    assert run_kwargs["twin_snapshot_cmd"] == "snap {dest}"
    assert run_kwargs["drain_cmd"] == "drain {run_id}"
    assert run_kwargs["post_drain_fetch_cmd"] == "post {dest}"
    assert run_kwargs["config_identity_from"] == "identity.json"
    for key, value in EXTERNAL_EVIDENCE_KWARGS.items():
        assert run_kwargs[key] == value, key
    assert "allow_missing_restart_evidence" not in run_kwargs
    assert (
        cli.main(
            [
                "collect",
                "--run-id",
                "controller_restart-r01",
                "--config-identity-from",
                "identity.json",
                *EXTERNAL_EVIDENCE_CLI,
            ]
        )
        == 0
    )
    assert seen["collect"]["config_identity_from"] == "identity.json"
    for key, value in EXTERNAL_EVIDENCE_KWARGS.items():
        assert seen["collect"][key] == value, key
    assert "allow_missing_restart_evidence" not in seen["collect"]


@pytest.mark.parametrize("command", ["run", "collect", "campaign"])
def test_the_allow_missing_restart_evidence_flag_no_longer_exists(
    command, monkeypatch, capsys
) -> None:
    """F6: missing restart evidence never qualifies through a flag."""
    from egw_experiments import cli

    argv = [command, "--allow-missing-restart-evidence"]
    if command != "campaign":
        argv[1:1] = ["--run-id", "controller_restart-r01"]
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2
    assert "--allow-missing-restart-evidence" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# F5: the collector window covers the before-snapshot's allowance
# ---------------------------------------------------------------------------


def _collector_window(plan_path: Path, run_id: str, *, snapshot: bool) -> int:
    """The {duration_s} the start hook must receive: warm-up + measured run
    + confirmation wait (0 in these tests) + margin, plus the snapshot's
    allowance when a twin snapshot is configured."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    entry = next(r for r in plan["runs"] if r["run_id"] == run_id)
    return (
        int(entry.get("warmup_s") or 0)
        + int(entry["duration_s"])
        + 0
        + run_mod.COLLECTOR_DURATION_MARGIN_S
        + (int(run_mod.SNAPSHOT_TIMEOUT_S) if snapshot else 0)
    )


def _start_hook_duration(record: Path) -> int:
    """The {duration_s} the fake start hook recorded (HOOK_SCRIPT)."""
    line = next(
        line for line in record.read_text(encoding="utf-8").splitlines()
        if line.startswith("start ")
    )
    return int(line.split()[2])


def test_the_collector_window_gains_the_snapshot_allowance_only_with_a_twin_snapshot(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """F5: with --twin-snapshot-cmd the {duration_s} handed to the collector
    start hook adds SNAPSHOT_TIMEOUT_S (= FETCH_TIMEOUT_S, the allowance the
    before-snapshot may take between the collector start and the measured
    run); without a snapshot it is unchanged."""
    assert run_mod.SNAPSHOT_TIMEOUT_S == run_mod.FETCH_TIMEOUT_S
    record, start_tpl, stop_tpl, fetch_tpl = _collector_hooks(tmp_path)
    hooks = dict(
        collector_start_cmd=start_tpl,
        collector_stop_cmd=stop_tpl,
        collector_fetch_cmd=fetch_tpl,
        expect_services=SIX_SERVICES,
        resources_from=None,
    )
    _rc, run_dir, _steps = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, **hooks
    )
    with_snapshot = _collector_window(plan_path, "controller_restart-r01", snapshot=True)
    assert _start_hook_duration(record) == with_snapshot
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert f" {with_snapshot} " in manifest["collector_hooks"][0]["command"]
    assert with_snapshot == _collector_window(
        plan_path, "controller_restart-r01", snapshot=False
    ) + int(run_mod.SNAPSHOT_TIMEOUT_S)

    # Without a snapshot (a smoke run through the same hooks): unchanged.
    record.unlink()
    rc, run_dir, _record = _hooked_run(
        tmp_path, plan_path, run_id="smoke_sequence-r01", base=tmp_path / "plain-results"
    )
    assert rc == 0
    manifest = _manifest(run_dir.parent.parent, "smoke_sequence-r01")
    without = _collector_window(plan_path, "smoke_sequence-r01", snapshot=False)
    assert f" {without} " in manifest["collector_hooks"][0]["command"]


def test_a_slow_successful_before_snapshot_leaves_the_run_valid(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """F5: a before-snapshot that takes its time (0.3 s here) under its own
    SNAPSHOT_TIMEOUT_S allowance is a successful step: the run is valid, the
    collector's CSV is ingested and covers the measured window, and the
    snapshot ran under the explicit timeout. The fixtures fake the wall
    clock, so the collector's real-time self-termination cannot be observed
    here; the window arithmetic is asserted by the test above."""
    record, start_tpl, stop_tpl, fetch_tpl = _collector_hooks(tmp_path)
    rc, run_dir, steps = _item18_run(
        tmp_path,
        plan_path,
        fast_run,
        monkeypatch,
        snapshot=("write+sleep:0.3", 0),
        collector_start_cmd=start_tpl,
        collector_stop_cmd=stop_tpl,
        collector_fetch_cmd=fetch_tpl,
        expect_services=SIX_SERVICES,
        resources_from=None,
    )
    assert rc == 0
    assert _step_lines(steps)[:2] == ["snapshot twins.before.json", "simulator -"]
    assert _hook_labels(record) == ["start", "stop", "fetch"]
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert manifest["validity"] == "valid"
    assert manifest["resource_source"] == "sut-collector"
    assert (run_dir / "resources.csv").is_file()
    before = manifest["twin_snapshots"][0]
    assert before["verified"] is True
    started = datetime.fromisoformat(before["started_utc"].replace("Z", "+00:00"))
    finished = datetime.fromisoformat(before["finished_utc"].replace("Z", "+00:00"))
    assert finished >= started
    assert _start_hook_duration(record) == _collector_window(
        plan_path, "controller_restart-r01", snapshot=True
    )


def test_the_twin_snapshot_hooks_run_under_the_snapshot_timeout(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    seen: list[tuple[str, float | None]] = []
    real = run_mod.execute_collector_hook

    def spy(hook, template, run_id, **kwargs):
        seen.append((hook, kwargs.get("timeout_s")))
        return real(hook, template, run_id, **kwargs)

    monkeypatch.setattr(run_mod, "execute_collector_hook", spy)
    rc, _run_dir, _record = _item18_run(tmp_path, plan_path, fast_run, monkeypatch)
    assert rc == 0
    timeouts = dict(seen)
    assert timeouts["twin_snapshot_before"] == run_mod.SNAPSHOT_TIMEOUT_S
    assert timeouts["twin_snapshot_after"] == run_mod.SNAPSHOT_TIMEOUT_S
    assert timeouts["drain"] == run_mod.DRAIN_TIMEOUT_S


# ---------------------------------------------------------------------------
# F6: restart evidence taken outside the harness is ingested and VERIFIED
# ---------------------------------------------------------------------------


def _bare_restart_run(tmp_path: Path, plan_path: Path, fast_run, monkeypatch) -> tuple[Path, Path]:
    """A controller_restart run with the restart, the log fetches and the
    identity, but none of the restart evidence steps: invalid, sealed.
    Returns (base, run_dir)."""
    rc, run_dir, _record = _item18_run(
        tmp_path,
        plan_path,
        fast_run,
        monkeypatch,
        twin_snapshot_cmd=None,
        drain_cmd=None,
        post_drain_fetch_cmd=None,
    )
    assert rc == 1
    base = run_dir.parent.parent
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["validity"] == "invalid"
    assert len(manifest["validity_reasons"]) == 4
    assert (run_dir / checksums.SUMS_FILENAME).is_file()
    return base, run_dir


def _external_evidence(tmp_path: Path, plan_path: Path, run_id: str, *, drain: str = DRAIN_QUIET_LINE) -> dict[str, Path]:
    seed = _plan_seed(plan_path, run_id)
    return dict(
        twins_before_from=_twins_file(tmp_path, "before", seed=seed),
        twins_after_from=_twins_file(tmp_path, "after", seed=seed),
        post_drain_events_from=_post_drain_events_file(tmp_path, run_id),
        drain_transcript_from=_drain_transcript(tmp_path, drain),
    )


def test_collect_ingests_verified_external_restart_evidence_with_provenance(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """F6: the run without hooks is invalid; 'collect' with the four files
    taken by the runbook's helpers verifies each against this run, copies
    it write-once under the hook's name, seals it and records its source
    path and sha256; the run becomes valid."""
    base, run_dir = _bare_restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    files = _external_evidence(tmp_path, plan_path, "controller_restart-r01")
    rc = run_mod.collect_run(
        "controller_restart-r01", base_dir=base, plan_path=plan_path, **files
    )
    assert rc == 0
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["validity"] == "valid" and manifest["validity_reasons"] == []
    sealed = _sealed_names(run_dir)
    assert checksums.verify_sha256sums(run_dir) == []

    snapshots = manifest["twin_snapshots"]
    assert [s["file"] for s in snapshots] == ["twins.before.json", "twins.after.json"]
    for snap, key in zip(snapshots, ("twins_before_from", "twins_after_from")):
        assert snap["source"] == "ingested"
        assert snap["from"] == str(files[key])
        assert snap["verified"] is True and snap["problems"] == []
        assert snap["flag"] == run_mod.RESTART_EVIDENCE_FROM_FLAGS[snap["hook"]]
        assert snap["sha256"] == checksums.sha256_file(run_dir / snap["file"])
        assert snap["sha256"] == checksums.sha256_file(files[key])
        assert snap["file"] in sealed
        assert "returncode" not in snap

    drain = manifest["drain"]
    assert drain["source"] == "ingested"
    assert drain["from"] == str(files["drain_transcript_from"])
    assert drain["outcome"] == "quiet" and drain["verified"] is True
    assert drain["file"] == "logs/sut/drain.txt"
    assert drain["sha256"] == checksums.sha256_file(run_dir / "logs" / "sut" / "drain.txt")
    assert "logs/sut/drain.txt" in sealed
    assert (run_dir / "logs" / "sut" / "drain.txt").read_text(encoding="utf-8") == DRAIN_QUIET_LINE

    post_drain = manifest["events_post_drain_fetch"]
    assert post_drain["source"] == "ingested"
    assert post_drain["from"] == str(files["post_drain_events_from"])
    assert post_drain["verified"] is True and post_drain["problems"] == []
    assert post_drain["file"] == "events.post-drain.jsonl"
    assert post_drain["sha256"] == checksums.sha256_file(run_dir / "events.post-drain.jsonl")
    assert "events.post-drain.jsonl" in sealed
    # The harness copy of the events is untouched.
    assert (run_dir / "events.jsonl").read_text(encoding="utf-8") == (
        "events content for controller_restart-r01\n"
    )
    added = [f for entry in manifest["collection_history"] for f in entry["added_files"]]
    assert set(added) >= {
        "twins.before.json",
        "twins.after.json",
        "events.post-drain.jsonl",
        "logs/sut/drain.txt",
    }
    actions = " ".join(manifest["collect_history"][-1]["actions"])
    assert "twins.before.json" in actions and "drain.txt" in actions

    # Idempotent: the same files again are no-ops and the run stays valid.
    assert run_mod.collect_run("controller_restart-r01", base_dir=base, plan_path=plan_path, **files) == 0
    assert checksums.verify_sha256sums(run_dir) == []
    # A different snapshot for the same file is refused (write-once).
    other = _twins_file(
        tmp_path, "before", seed=_plan_seed(plan_path, "controller_restart-r01"),
        name="other.before.json", devices={"c" * 8: {"device_type": "vest", "exists": False, "ingestion": {}}},
    )
    assert run_mod.collect_run("controller_restart-r01", base_dir=base, plan_path=plan_path, twins_before_from=other) == 2


def test_collect_refuses_a_post_drain_events_file_of_another_run(
    tmp_path, plan_path, fast_run, monkeypatch, capsys
) -> None:
    base, run_dir = _bare_restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    files = _external_evidence(tmp_path, plan_path, "controller_restart-r01")
    files["post_drain_events_from"] = _post_drain_events_file(
        tmp_path,
        "controller_restart-r02",
        name="wrong-run.jsonl",
    )
    rc = run_mod.collect_run(
        "controller_restart-r01", base_dir=base, plan_path=plan_path, **files
    )
    assert rc == 1
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["validity"] == "invalid"
    (reason,) = manifest["validity_reasons"]
    assert "--post-drain-events-from" in reason and "refused" in reason
    assert "'controller_restart-r02'" in reason and "'controller_restart-r01'" in reason
    post_drain = manifest["events_post_drain_fetch"]
    assert post_drain["source"] == "ingested" and post_drain["verified"] is False
    assert post_drain["sha256"] is None
    assert any("controller_restart-r02" in p for p in post_drain["problems"])
    # Nothing of the wrong run enters the evidence: the file is not copied.
    assert not (run_dir / "events.post-drain.jsonl").exists()
    assert "events.post-drain.jsonl" not in _sealed_names(run_dir)
    assert checksums.verify_sha256sums(run_dir) == []
    # The other three were ingested and stay in place.
    assert (run_dir / "twins.before.json").is_file()
    assert (run_dir / "logs" / "sut" / "drain.txt").is_file()
    assert "REFUSED" in " ".join(manifest["warnings"])
    err = capsys.readouterr().err
    assert "INVALID" in err and "controller_restart-r02" in err

    # The right file afterwards makes the run valid: a refusal blocks nothing.
    files["post_drain_events_from"] = _post_drain_events_file(tmp_path, "controller_restart-r01")
    assert run_mod.collect_run("controller_restart-r01", base_dir=base, plan_path=plan_path, **files) == 0
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["validity"] == "valid"
    assert manifest["events_post_drain_fetch"]["verified"] is True


@pytest.mark.parametrize(
    "key, expected",
    [
        ("twins_before_from", "--twins-before-from"),
        ("twins_after_from", "--twins-after-from"),
        ("post_drain_events_from", "--post-drain-events-from"),
        ("drain_transcript_from", "--drain-transcript-from"),
    ],
)
def test_collect_names_a_missing_external_file_as_a_reason(
    tmp_path, plan_path, fast_run, monkeypatch, key, expected
) -> None:
    base, _run_dir = _bare_restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    files = _external_evidence(tmp_path, plan_path, "controller_restart-r01")
    files[key] = tmp_path / "absent-file"
    rc = run_mod.collect_run(
        "controller_restart-r01", base_dir=base, plan_path=plan_path, **files
    )
    assert rc == 1
    manifest = _manifest(base, "controller_restart-r01")
    (reason,) = manifest["validity_reasons"]
    assert expected in reason and "absent-file" in reason and "not found" in reason
    assert any(expected in w and "not found" in w for w in manifest["warnings"])


def test_collect_ingests_a_gave_up_transcript_without_requiring_the_after_evidence(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """F2 + F6: a `drained` that gave up is a failed recovery, retained: with
    the before snapshot and the transcript alone the run is valid,
    drain.outcome is 'gave-up', and the after snapshot and the post-drain
    events are not required (a warning says why)."""
    base, run_dir = _bare_restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    seed = _plan_seed(plan_path, "controller_restart-r01")
    rc = run_mod.collect_run(
        "controller_restart-r01",
        base_dir=base,
        plan_path=plan_path,
        twins_before_from=_twins_file(tmp_path, "before", seed=seed),
        drain_transcript_from=_drain_transcript(tmp_path, DRAIN_GAVE_UP_LINE),
    )
    assert rc == 0
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["validity"] == "valid" and manifest["validity_reasons"] == []
    drain = manifest["drain"]
    assert drain["outcome"] == "gave-up" and drain["source"] == "ingested"
    assert drain["verified"] is True
    assert [s["file"] for s in manifest["twin_snapshots"]] == ["twins.before.json"]
    assert manifest["events_post_drain_fetch"] is None
    (warning,) = [w for w in manifest["warnings"] if "failed recovery" in w]
    assert "twins.after.json" in warning and "events.post-drain.jsonl" in warning
    assert "not required" in warning
    assert "logs/sut/drain.txt" in _sealed_names(run_dir)
    # A second collect pass does not stack the warning.
    assert run_mod.collect_run("controller_restart-r01", base_dir=base, plan_path=plan_path) == 0
    manifest = _manifest(base, "controller_restart-r01")
    assert len([w for w in manifest["warnings"] if "failed recovery" in w]) == 1


@pytest.mark.parametrize(
    "text, problem",
    [
        (DRAIN_GET_FAILED_LINE, "quiet line"),
        ("", "quiet line"),
        (DRAIN_QUIET_LINE + DRAIN_GAVE_UP_LINE, "both"),
    ],
)
def test_collect_refuses_a_transcript_without_the_helper_lines(
    tmp_path, plan_path, fast_run, monkeypatch, text, problem
) -> None:
    base, run_dir = _bare_restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    files = _external_evidence(tmp_path, plan_path, "controller_restart-r01", drain=text)
    rc = run_mod.collect_run(
        "controller_restart-r01", base_dir=base, plan_path=plan_path, **files
    )
    assert rc == 1
    manifest = _manifest(base, "controller_restart-r01")
    (reason,) = manifest["validity_reasons"]
    assert "--drain-transcript-from" in reason and problem in reason
    assert manifest["drain"]["outcome"] == "error"
    assert manifest["drain"]["verified"] is False
    assert not (run_dir / "logs" / "sut" / "drain.txt").exists()


def test_collect_refuses_a_snapshot_of_another_label_or_seed(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    base, run_dir = _bare_restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    seed = _plan_seed(plan_path, "controller_restart-r01")
    files = _external_evidence(tmp_path, plan_path, "controller_restart-r01")
    # An 'after' file handed in as the before snapshot; a before snapshot of
    # another seed handed in as the after one.
    files["twins_before_from"] = _twins_file(tmp_path, "after", seed=seed, name="mislabelled.json")
    files["twins_after_from"] = _twins_file(tmp_path, "after", seed=seed + 1, name="other-seed.json")
    rc = run_mod.collect_run(
        "controller_restart-r01", base_dir=base, plan_path=plan_path, **files
    )
    assert rc == 1
    manifest = _manifest(base, "controller_restart-r01")
    reasons = manifest["validity_reasons"]
    assert len(reasons) == 2
    before = next(r for r in reasons if "--twins-before-from" in r)
    assert "label must be 'before'" in before and "'after'" in before
    after = next(r for r in reasons if "--twins-after-from" in r)
    assert f"seed {seed + 1}" in after and f"{seed}" in after
    assert not (run_dir / "twins.before.json").exists()
    assert not (run_dir / "twins.after.json").exists()
    # A snapshot whose seed is null is accepted (the helper's `--like` form).
    files["twins_before_from"] = _twins_file(tmp_path, "before", name="no-seed-before.json")
    files["twins_after_from"] = _twins_file(tmp_path, "after", name="no-seed-after.json")
    assert run_mod.collect_run("controller_restart-r01", base_dir=base, plan_path=plan_path, **files) == 0


@pytest.mark.parametrize(
    "document, problem",
    [
        ([], "not an object"),
        ({"label": "before", "seed": None}, "devices must be a JSON object"),
        ({"label": "before", "seed": None, "devices": []}, "devices must be a JSON object"),
        ({"label": "before", "seed": None, "devices": {}}, "no device"),
        ({"label": "after", "seed": None, "devices": {"x": {}}}, "label must be 'before'"),
        ({"label": "before", "seed": 8, "devices": {"x": {}}}, "seed 8"),
    ],
)
def test_twin_snapshot_problems(document, problem) -> None:
    problems = run_mod.twin_snapshot_problems(document, label="before", seed=7)
    assert problems and any(problem in p for p in problems), problems
    assert run_mod.twin_snapshot_problems(
        {"label": "before", "seed": 7, "devices": {"x": {}}}, label="before", seed=7
    ) == []
    assert run_mod.twin_snapshot_problems(
        {"label": "before", "seed": None, "devices": {"x": {}}}, label="before", seed=7
    ) == []


@pytest.mark.parametrize(
    "lines, problem",
    [
        ([], "no event record"),
        ([""], "no event record"),
        (["not json"], "line 1 is not JSON"),
        (["[]"], "line 1 is not a JSON object"),
        ([{"run_id": "other", "outcome": "accepted"}], "belongs to run 'other'"),
        ([{"run_id": "r1", "outcome": "lost"}], "outcome 'lost'"),
        ([{"run_id": "r1"}], "outcome None"),
        ([{"run_id": "r1", "outcome": "accepted"}, {"run_id": "r1", "outcome": "dropped"}], "line 2"),
    ],
)
def test_post_drain_events_problems(tmp_path, lines, problem) -> None:
    path = _post_drain_events_file(tmp_path, "r1", lines=lines)
    problems = run_mod.post_drain_events_problems(path, "r1")
    assert problems and any(problem in p for p in problems), problems
    good = _post_drain_events_file(
        tmp_path,
        "r1",
        name="good.jsonl",
        lines=[{"run_id": "r1", "outcome": o} for o in ("accepted", "rejected", "duplicate", "failed")],
    )
    assert run_mod.post_drain_events_problems(good, "r1") == []


def test_post_drain_events_problems_are_bounded(tmp_path) -> None:
    path = _post_drain_events_file(
        tmp_path, "r1", lines=[{"run_id": "other", "outcome": "accepted"}] * 50
    )
    problems = run_mod.post_drain_events_problems(path, "r1")
    assert len(problems) <= 6 and problems[-1].startswith("further lines not checked")


def test_run_ingests_external_restart_evidence_in_place_of_the_hooks(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """The four --*-from flags work on 'run' as well: the before snapshot is
    ingested where the hook would take it, the others after the drain
    point; a valid set makes the run valid at run time."""
    files = _external_evidence(tmp_path, plan_path, "controller_restart-r01")
    rc, run_dir, record = _item18_run(
        tmp_path,
        plan_path,
        fast_run,
        monkeypatch,
        twin_snapshot_cmd=None,
        drain_cmd=None,
        post_drain_fetch_cmd=None,
        **files,
    )
    assert rc == 0
    assert _step_lines(record) == [
        "simulator -",
        "events events.jsonl",
        "broker_log broker.log",
        "controller_log controller.log",
        "docker_events docker-events.log",
    ]
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    assert manifest["validity"] == "valid"
    assert [s["source"] for s in manifest["twin_snapshots"]] == ["ingested", "ingested"]
    assert manifest["drain"]["source"] == "ingested" and manifest["drain"]["outcome"] == "quiet"
    assert manifest["events_post_drain_fetch"]["source"] == "ingested"
    cli = manifest["config"]["cli"]
    for key, path in files.items():
        assert cli[key] == str(path)
    sealed = _sealed_names(run_dir)
    for name in ("twins.before.json", "twins.after.json", "events.post-drain.jsonl", "logs/sut/drain.txt"):
        assert name in sealed


@pytest.mark.parametrize(
    "hook, from_key, from_flag",
    [
        ("twin_snapshot_cmd", "twins_before_from", "--twins-before-from"),
        ("twin_snapshot_cmd", "twins_after_from", "--twins-after-from"),
        ("drain_cmd", "drain_transcript_from", "--drain-transcript-from"),
        ("post_drain_fetch_cmd", "post_drain_events_from", "--post-drain-events-from"),
    ],
)
def test_a_hook_and_a_file_for_the_same_artefact_are_refused_before_anything_is_written(
    tmp_path, plan_path, fast_run, monkeypatch, capsys, hook, from_key, from_flag
) -> None:
    rc, run_dir, _record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, **{from_key: tmp_path / "x"}
    )
    assert rc == 2
    assert not run_dir.exists()
    err = capsys.readouterr().err
    assert from_flag in err and "mutually exclusive" in err
    assert "--" + hook.replace("_", "-") in err


def test_collect_cannot_replace_a_hooks_record_with_an_external_file(
    tmp_path, plan_path, fast_run, monkeypatch, capsys
) -> None:
    """A step taken by a hook at run time is a run-time measurement: an
    external file for the same artefact is refused (exit 2), whether the
    hook succeeded or failed."""
    rc, run_dir, _record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, drain=("noop", 3)
    )
    assert rc == 1
    base = run_dir.parent.parent
    seed = _plan_seed(plan_path, "controller_restart-r01")
    for kwargs, flag in (
        ({"drain_transcript_from": _drain_transcript(tmp_path, DRAIN_QUIET_LINE)}, "--drain-transcript-from"),
        ({"twins_before_from": _twins_file(tmp_path, "before", seed=seed)}, "--twins-before-from"),
        ({"post_drain_events_from": _post_drain_events_file(tmp_path, "controller_restart-r01")}, "--post-drain-events-from"),
    ):
        assert run_mod.collect_run("controller_restart-r01", base_dir=base, plan_path=plan_path, **kwargs) == 2
        err = capsys.readouterr().err
        assert flag in err and "hook" in err
    manifest = _manifest(base, "controller_restart-r01")
    assert manifest["drain"]["source"] == "hook" and manifest["drain"]["outcome"] == "error"
    assert checksums.verify_sha256sums(run_dir) == []


def test_a_post_drain_fetch_hook_that_delivers_another_runs_events_is_a_reason(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """The hook's output is verified like an ingested file."""
    rc, run_dir, _record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, post_drain=("write+run:other-run", 0)
    )
    assert rc == 1
    manifest = _manifest(run_dir.parent.parent, "controller_restart-r01")
    (reason,) = manifest["validity_reasons"]
    assert "--post-drain-fetch-cmd" in reason and "'other-run'" in reason
    post_drain = manifest["events_post_drain_fetch"]
    assert post_drain["ok"] is True and post_drain["verified"] is False


def test_external_evidence_flags_are_ignored_with_a_warning_on_other_conditions(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    files = _external_evidence(tmp_path, plan_path, "smoke_sequence-r01")
    rc, run_dir, _record = _item18_run(
        tmp_path,
        plan_path,
        fast_run,
        monkeypatch,
        run_id="smoke_sequence-r01",
        restart_cmd=None,
        restart_at_s=None,
        twin_snapshot_cmd=None,
        drain_cmd=None,
        post_drain_fetch_cmd=None,
        **files,
    )
    assert rc == 0
    manifest = _manifest(run_dir.parent.parent, "smoke_sequence-r01")
    assert manifest["validity"] == "valid"
    assert manifest["twin_snapshots"] == [] and manifest["drain"] is None
    assert not (run_dir / "twins.before.json").exists()
    ignored = " ".join(w for w in manifest["warnings"] if "controller_restart" in w)
    for flag in run_mod.RESTART_EVIDENCE_FROM_FLAGS.values():
        assert flag in ignored
    # The same on 'collect'.
    rc = run_mod.collect_run(
        "smoke_sequence-r01", base_dir=run_dir.parent.parent, plan_path=plan_path, **files
    )
    assert rc == 0
    manifest = _manifest(run_dir.parent.parent, "smoke_sequence-r01")
    assert manifest["twin_snapshots"] == [] and not (run_dir / "twins.after.json").exists()


def test_collect_drops_the_retired_flag_and_deviation_from_an_older_manifest(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """A manifest written before F6 may carry the retired key and deviation
    kind; 'collect' rewrites it under the current rules: the flag excuses
    nothing, and a hook drain record without an outcome is classified from
    the output the hook kept."""
    rc, run_dir, _record = _item18_run(tmp_path, plan_path, fast_run, monkeypatch)
    assert rc == 0
    base = run_dir.parent.parent
    path = run_dir / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["allow_missing_restart_evidence"] = True
    manifest["config"]["cli"]["allow_missing_restart_evidence"] = True
    manifest["deviations"].append(
        {"kind": "missing_restart_evidence", "detail": "x", "authorized_by_flag": "--allow-missing-restart-evidence"}
    )
    for key in ("outcome", "source", "verified"):
        manifest["drain"].pop(key)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksums.write_sha256sums(run_dir)
    assert run_mod.collect_run("controller_restart-r01", base_dir=base, plan_path=plan_path) == 0
    manifest = _manifest(base, "controller_restart-r01")
    assert "allow_missing_restart_evidence" not in manifest
    assert "allow_missing_restart_evidence" not in manifest["config"]["cli"]
    assert not any(d["kind"] == "missing_restart_evidence" for d in manifest["deviations"])
    assert manifest["drain"]["outcome"] == "quiet" and manifest["drain"]["source"] == "hook"
    assert manifest["validity"] == "valid"
