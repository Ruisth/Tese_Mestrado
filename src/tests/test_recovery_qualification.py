"""Tests for egw_experiments.recovery_qualification (review finding F2).

The quantitative analyser never reads ``drain.outcome``: a valid
controller_restart run whose drain gave up (a failed recovery, retained by
run.py as an observation) can pass every C12 row of its acceptance table.
ADR 0011 leaves analyze.py unchanged, so the qualification lives in a layer
of its own, beside the analyser's outputs. These cases build sealed run
directories with the harness fixtures of test_experiments_run (the fake
simulator and the recorded item-18 hooks: no broker, no docker, no network)
and read the layer's files back, through the module and through the CLI.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from egw_experiments import analyze as analyze_mod
from egw_experiments import cli
from egw_experiments import recovery_qualification as rq
from egw_experiments import run as run_mod
from egw_experiments.checksums import write_sha256sums
from test_experiments_run import (  # noqa: F401  (fixtures registered by import)
    DRAIN_GAVE_UP_LINE,
    _bare_restart_run,
    _external_evidence,
    _item18_run,
    _manifest,
    _plan_seed,
    fast_run,
    plan_path,
)

R01, R02, R03 = "controller_restart-r01", "controller_restart-r02", "controller_restart-r03"


def _restart_run(tmp_path, plan_path, fast_run, monkeypatch, run_id: str = R01, **kwargs) -> Path:
    """One controller_restart run through the harness with every item-18
    step driven by the recorded hooks; returns the results base."""
    _rc, run_dir, _record = _item18_run(
        tmp_path, plan_path, fast_run, monkeypatch, run_id=run_id, **kwargs
    )
    return run_dir.parent.parent


def _files(base: Path) -> tuple[dict, list[dict]]:
    doc = json.loads((base / "processed" / rq.JSON_FILENAME).read_text(encoding="utf-8"))
    rows = list(
        csv.DictReader((base / "processed" / rq.CSV_FILENAME).read_text(encoding="utf-8").splitlines())
    )
    return doc, rows


def _row(doc: dict, run_id: str) -> dict:
    return next(r for r in doc["runs"] if r["run_id"] == run_id)


# ---------------------------------------------------------------------------
# the rule, as a pure function of what the manifest records
# ---------------------------------------------------------------------------


def _facts(**changes) -> dict:
    facts = {
        "validity": "valid",
        "integrity": "ok",
        "excluded": False,
        "drain_outcome": "quiet",
        "twins_before_verified": True,
        "twins_after_verified": True,
        "post_drain_verified": True,
    }
    facts.update(changes)
    return facts


@pytest.mark.parametrize(
    "changes, expected, reason",
    [
        ({}, "recovery_observed", ""),
        ({"drain_outcome": "gave-up"}, "recovery_failed", "gave up"),
        ({"drain_outcome": "gave-up", "twins_after_verified": False, "post_drain_verified": False},
         "recovery_failed", "gave up"),
        ({"drain_outcome": "error"}, "not_evidenced", "drain outcome 'error'"),
        ({"drain_outcome": "absent"}, "not_evidenced", "drain outcome 'absent'"),
        ({"twins_after_verified": False}, "not_evidenced", "after snapshot"),
        ({"post_drain_verified": False}, "not_evidenced", "post-drain events"),
        ({"validity": "invalid"}, "not_evidenced", "validity 'invalid'"),
        ({"validity": "absent"}, "not_evidenced", "validity 'absent'"),
        ({"integrity": "unsealed"}, "not_evidenced", "integrity 'unsealed'"),
        ({"integrity": "failed"}, "not_evidenced", "integrity 'failed'"),
        ({"excluded": True}, "not_evidenced", "excluded"),
    ],
)
def test_qualification_rule(changes, expected, reason) -> None:
    qualification, why = rq.qualification_of(_facts(**changes))
    assert qualification == expected and qualification in rq.QUALIFICATIONS
    assert reason in why


# ---------------------------------------------------------------------------
# sealed runs of the harness, read back through the layer
# ---------------------------------------------------------------------------


def test_a_quiet_drain_with_verified_after_evidence_is_recovery_observed(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    doc = rq.qualify_recovery(base, plan_path)
    assert doc["condition_id"] == "controller_restart"
    assert [r["run_id"] for r in doc["runs"]] == [R01, R02, R03]  # the plan's order
    row = _row(doc, R01)
    assert row["planned"] is True
    assert row["validity"] == "valid" and row["integrity"] == "ok"
    assert row["drain_outcome"] == "quiet" and row["drain_source"] == "hook"
    assert row["twins_before_verified"] is True and row["twins_after_verified"] is True
    assert row["post_drain_verified"] is True
    assert row["qualification"] == "recovery_observed" and row["reason"] == ""
    # The plan's other two runs have no directory yet: not evidenced, and
    # the criterion names them.
    for run_id in (R02, R03):
        absent = _row(doc, run_id)
        assert absent["validity"] == "absent" and absent["drain_outcome"] == "absent"
        assert absent["qualification"] == "not_evidenced"
    criterion = doc["criterion"]
    assert criterion["name"] == rq.CRITERION
    assert criterion["passed"] is False
    assert [n["run_id"] for n in criterion["not_qualified"]] == [R02, R03]
    assert all(n["qualification"] == "not_evidenced" for n in criterion["not_qualified"])
    assert "1/3" in criterion["detail"]
    assert doc["statement"] == rq.STATEMENT
    for word in ("lost", "late", "N1", "acceptance"):
        assert word in doc["statement"]


def test_every_planned_run_recovery_observed_passes_the_criterion(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    for run_id in (R01, R02, R03):
        base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch, run_id=run_id)
    doc = rq.qualify_recovery(base, plan_path)
    assert [r["qualification"] for r in doc["runs"]] == ["recovery_observed"] * 3
    assert doc["criterion"]["passed"] is True and doc["criterion"]["not_qualified"] == []
    assert "3/3" in doc["criterion"]["detail"]
    line = rq.summary_line(doc)
    assert line.startswith("[recovery] ") and rq.CRITERION in line and "PASSED" in line


def test_a_gave_up_drain_of_a_valid_run_is_recovery_failed_and_named(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """The observation stays valid (run.py: a drain that gave up is never a
    validity reason); the qualification says the recovery failed and the
    criterion is false naming the run."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch, drain=("gaveup", 1))
    assert _manifest(base, R01)["validity"] == "valid"
    doc = rq.qualify_recovery(base, plan_path)
    row = _row(doc, R01)
    assert row["validity"] == "valid" and row["drain_outcome"] == "gave-up"
    assert row["qualification"] == "recovery_failed"
    assert "gave up" in row["reason"]
    named = doc["criterion"]["not_qualified"][0]
    assert named["run_id"] == R01 and named["qualification"] == "recovery_failed"
    assert doc["criterion"]["passed"] is False
    line = rq.summary_line(doc)
    assert "FAILED" in line and f"{R01} (recovery_failed" in line


def test_an_error_drain_makes_an_invalid_run_not_evidenced(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch, drain=("noop", 3))
    assert _manifest(base, R01)["validity"] == "invalid"
    doc = rq.qualify_recovery(base, plan_path)
    row = _row(doc, R01)
    assert row["validity"] == "invalid" and row["drain_outcome"] == "error"
    assert row["qualification"] == "not_evidenced"
    assert "validity 'invalid'" in row["reason"]
    assert doc["criterion"]["passed"] is False
    assert doc["criterion"]["not_qualified"][0] == {
        "run_id": R01, "qualification": "not_evidenced", "reason": row["reason"],
    }


def test_ingested_evidence_is_reported_with_its_source(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """The runbook's path: the hooks did not run, the four files were
    ingested by 'collect'; the layer reads the same records."""
    base, _run_dir = _bare_restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    doc = rq.qualify_recovery(base, plan_path)
    row = _row(doc, R01)
    assert row["validity"] == "invalid" and row["qualification"] == "not_evidenced"
    assert row["drain_outcome"] == "absent" and row["drain_source"] is None
    files = _external_evidence(tmp_path, plan_path, R01)
    assert cli.main(["collect", "--run-id", R01, "--base-dir", str(base), "--plan", str(plan_path),
                     "--twins-before-from", str(files["twins_before_from"]),
                     "--twins-after-from", str(files["twins_after_from"]),
                     "--post-drain-events-from", str(files["post_drain_events_from"]),
                     "--drain-transcript-from", str(files["drain_transcript_from"])]) == 0
    row = _row(rq.qualify_recovery(base, plan_path), R01)
    assert row["drain_source"] == "ingested" and row["drain_outcome"] == "quiet"
    assert row["captured_utc"] == "2026-09-07T10:30:00Z"
    assert row["qualification"] == "recovery_observed"


def test_an_unsealed_or_tampered_run_is_not_evidenced(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    run_dir = base / "raw" / R01
    (run_dir / "events.jsonl").write_text("tampered\n", encoding="utf-8")
    row = _row(rq.qualify_recovery(base, plan_path), R01)
    assert row["integrity"] == "failed" and row["qualification"] == "not_evidenced"
    (run_dir / "SHA256SUMS").unlink()
    row = _row(rq.qualify_recovery(base, plan_path), R01)
    assert row["integrity"] == "unsealed" and row["qualification"] == "not_evidenced"


def test_without_a_plan_the_planned_set_is_unknown(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    monkeypatch.delenv(analyze_mod.CAMPAIGN_PLAN_ENV_VAR, raising=False)
    doc = rq.qualify_recovery(base, None)
    assert doc["plan"] is None
    assert [r["run_id"] for r in doc["runs"]] == [R01]
    assert _row(doc, R01)["planned"] is False
    assert _row(doc, R01)["qualification"] == "recovery_observed"
    assert doc["criterion"]["passed"] is False
    assert "no campaign plan" in doc["criterion"]["detail"]


def test_an_unreadable_plan_is_named_in_the_detail(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """A plan that was supplied but cannot be read is not "no plan supplied": the
    criterion fails and its detail (the one line the CLI prints) carries the
    reason recorded in plan_problem."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    plan_path.write_text("{ not json", encoding="utf-8")
    doc = rq.qualify_recovery(base, plan_path)
    assert doc["plan"] is None and doc["plan_problem"]
    assert doc["criterion"]["passed"] is False
    detail = doc["criterion"]["detail"]
    assert "could not be read" in detail and doc["plan_problem"] in detail
    assert "no campaign plan supplied" not in detail
    assert doc["plan_problem"] in rq.summary_line(doc)


def test_an_unplanned_restart_run_in_raw_is_listed_and_counted(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """A controller_restart directory the plan does not list (a renamed or
    stray run) is reported, marked unplanned, and must qualify too."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch, drain=("gaveup", 1))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["runs"] = [r for r in plan["runs"] if r["run_id"] != R01]
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    doc = rq.qualify_recovery(base, plan_path)
    assert [r["run_id"] for r in doc["runs"]] == [R02, R03, R01]
    assert _row(doc, R01)["planned"] is False
    assert _row(doc, R01)["qualification"] == "recovery_failed"
    assert [n["run_id"] for n in doc["criterion"]["not_qualified"]] == [R02, R03, R01]


def test_a_plan_without_restart_runs_does_not_pass_on_an_unplanned_directory(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """A readable plan with no controller_restart entry and one old valid,
    quiet restart directory in raw/: the directory is listed, unplanned and
    recovery_observed, and the criterion still fails - an unplanned run never
    stands for a planned one, and with no planned run there is nothing to
    qualify (review of 2026-09-25, D1)."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["runs"] = [r for r in plan["runs"] if r.get("condition_id") != rq.CONDITION_ID]
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    doc = rq.qualify_recovery(base, plan_path)
    assert doc["plan_problem"] is None
    assert [r["run_id"] for r in doc["runs"]] == [R01]
    assert _row(doc, R01)["planned"] is False
    assert _row(doc, R01)["qualification"] == "recovery_observed"
    assert doc["criterion"]["passed"] is False
    assert doc["criterion"]["not_qualified"] == []
    detail = doc["criterion"]["detail"]
    assert "lists no controller_restart run" in detail and "1 unplanned directory" in detail
    assert "1/1" in detail
    line = rq.summary_line(doc)
    assert "FAILED" in line and "PASSED" not in line


# ---------------------------------------------------------------------------
# through the CLI: run/collect to the final report
# ---------------------------------------------------------------------------


def _processed(base: Path) -> dict[str, bytes]:
    return {
        p.name: p.read_bytes()
        for p in sorted((base / "processed").iterdir())
        if p.name not in (rq.JSON_FILENAME, rq.CSV_FILENAME)
    }


def test_cli_analyze_propagates_the_failed_recovery_and_leaves_the_analysers_outputs_unchanged(
    tmp_path, plan_path, fast_run, monkeypatch, capsys
) -> None:
    """The contradiction of finding F2, end to end: a valid run whose drain
    gave up. The analyser's report says nothing of it (its C12 rows read
    the metrics and events, never drain.outcome); the layer writes the
    failed recovery beside that report, in files of its own, and the
    analyser's files are byte for byte what analyze() alone writes."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch, drain=("gaveup", 1))
    assert analyze_mod.analyze(base_dir=base, plan_path=plan_path) == 0
    alone = _processed(base)
    assert alone and rq.JSON_FILENAME not in alone
    capsys.readouterr()

    assert cli.main(["analyze", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    out = capsys.readouterr().out
    assert _processed(base) == alone
    doc, rows = _files(base)
    assert _row(doc, R01)["qualification"] == "recovery_failed"
    assert doc["criterion"]["passed"] is False
    (line,) = [ln for ln in out.splitlines() if ln.startswith("[recovery] ")]
    assert line == rq.summary_line(doc)
    assert rq.CRITERION in line and "FAILED" in line and R01 in line and "recovery_failed" in line
    assert rq.JSON_FILENAME in line
    # The csv mirrors the json, one row per run of the plan.
    assert [r["run_id"] for r in rows] == [R01, R02, R03]
    assert rows[0]["qualification"] == "recovery_failed" and rows[0]["drain_outcome"] == "gave-up"
    assert rows[0]["validity"] == "valid" and rows[0]["twins_after_verified"] == "true"
    assert set(rows[0]) == set(rq.CSV_COLUMNS)
    # The analyser's own report: the run is valid and its acceptance table
    # carries no row of this layer and no word of the drain.
    per_run = (base / "processed" / "per_run.csv").read_text(encoding="utf-8")
    assert R01 in per_run and "gave-up" not in per_run
    acceptance = (base / "processed" / "acceptance_by_condition.csv").read_text(encoding="utf-8")
    assert rq.CRITERION not in acceptance and "gave-up" not in acceptance
    assert "restart_hook_executed_every_run" in acceptance  # the analyser's own C12 rows are there


def test_cli_analyze_writes_the_quiet_case_as_recovery_observed(
    tmp_path, plan_path, fast_run, monkeypatch, capsys
) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    assert cli.main(["analyze", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    doc, _rows = _files(base)
    assert _row(doc, R01)["qualification"] == "recovery_observed"
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("[recovery] "))
    assert "1/3" in line and R02 in line and R03 in line


def test_cli_analyze_exit_code_is_the_analysers(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """A false criterion never fails the analyze command: its exit code says
    whether the processed tree was regenerated (as a failed acceptance row
    does not fail it either); the result is in the files and on stdout."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch, drain=("gaveup", 1))
    assert cli.main(["analyze", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    assert "exit code" in (cli._cmd_analyze.__doc__ or "")
    # No raw/ at all: analyze's own refusal, and no layer output is written.
    empty = tmp_path / "nothing"
    empty.mkdir()
    assert cli.main(["analyze", "--base-dir", str(empty), "--plan", str(plan_path)]) == 2
    assert not (empty / "processed").exists()


def test_recovery_subcommand_runs_the_layer_alone(
    tmp_path, plan_path, fast_run, monkeypatch, capsys
) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    # Standalone: processed/ is created if absent and never cleaned (a
    # stale file of the analyser survives; only analyze regenerates it).
    stale = base / "processed" / "per_run.csv"
    stale.parent.mkdir()
    stale.write_text("stale\n", encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["recovery", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    assert stale.read_text(encoding="utf-8") == "stale\n"
    doc, rows = _files(base)
    assert _row(doc, R01)["qualification"] == "recovery_observed"
    out = capsys.readouterr().out
    assert out.startswith("[recovery] ") and rq.CRITERION in out
    # Repeatable, and identical: no timestamp enters the files.
    before = (base / "processed" / rq.JSON_FILENAME).read_bytes()
    assert cli.main(["recovery", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    assert (base / "processed" / rq.JSON_FILENAME).read_bytes() == before
    # Without raw/ there is nothing to qualify.
    empty = tmp_path / "nothing"
    empty.mkdir()
    assert cli.main(["recovery", "--base-dir", str(empty), "--plan", str(plan_path)]) == 2
    assert "does not exist" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# decision 2 of 2026-09-30: the N1 identities, reported beside the
# qualification and never counted
# ---------------------------------------------------------------------------

NS = 1_000_000_000
RUN_T0 = 1_790_000_000  # the capture's requested_since, guest clock


def _n1_evidence(base: Path, plan_path: Path, run_id: str = R01, *, die: bool = True) -> str:
    """Rewrite a sealed restart run so that m2, published on the run's
    smartwatch, has only a duplicate line in the post-drain copy while the
    twin grew by one more than the device's accepted lines and ended on its
    seq; the controller's die is inside the capture's window (unless
    ``die`` is false) and the restart record is the harness's own (exit 0).
    The directory is sealed again, as a harness run leaves it. Returns the
    smartwatch's uuid."""
    run_dir = base / "raw" / run_id
    devices = run_mod.expected_twin_devices(_plan_seed(plan_path, run_id))
    watch = next(u for u, t in devices.items() if t == "smartwatch")
    sent = [{"run_id": run_id, "message_id": f"m{i}", "device_uuid": watch, "device_type": "smartwatch",
             "seq": i, "publish_monotonic_ns": i, "puback_monotonic_ns": i, "intended_invalid": False}
            for i in range(3)]
    lines = [dict(sent[i], received_monotonic_ns=1000 * (i + 1), outcome=outcome,
                  ditto_ack_monotonic_ns=None, latency_ms=None, attempts=1, error=None)
             for i, outcome in ((0, "accepted"), (1, "accepted"), (2, "duplicate"))]
    for name, rows in (("sent_events.jsonl", sent), (run_mod.POST_DRAIN_EVENTS_FILENAME, lines)):
        (run_dir / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    before = json.loads((run_dir / "twins.before.json").read_text(encoding="utf-8"))
    after = json.loads(json.dumps(before))
    ingestion = after["devices"][watch]["ingestion"]
    ingestion.update(accepted_count=before["devices"][watch]["ingestion"]["accepted_count"] + 3,
                     last_run_id=run_id, last_seq=2)
    (run_dir / "twins.after.json").write_text(json.dumps(after) + "\n", encoding="utf-8")
    sut = run_dir / "logs" / "sut"
    at = (RUN_T0 + 300) * NS + 17
    event = {"Type": "container", "Action": "die" if die else "kill", "time": at // NS, "timeNano": at,
             "Actor": {"ID": "c" * 64, "Attributes": {"name": "egw-controller-1"}}}
    (sut / "docker-events.log").write_text(json.dumps(event) + "\n", encoding="utf-8")
    (sut / "docker-events.coverage.txt").write_text(
        f"coverage=complete\nrequested_since_guest_epoch={RUN_T0}\nrequested_until_guest_epoch={RUN_T0 + 900}\n"
        "expected=die,start\ncontainer=egw-controller-1\n", encoding="utf-8")
    write_sha256sums(run_dir)
    return watch


def test_a_duplicate_only_identity_with_its_death_and_twin_excess_is_reported_and_never_counted(
    tmp_path, plan_path, fast_run, monkeypatch, capsys
) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    restart = _manifest(base, R01)["restart"]
    assert restart["executed"] is True and restart["returncode"] == 0
    watch = _n1_evidence(base, plan_path)
    assert analyze_mod.analyze(base_dir=base, plan_path=plan_path) == 0
    alone = _processed(base)
    capsys.readouterr()
    assert cli.main(["analyze", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    assert _processed(base) == alone  # the analyser's files are what analyze() alone writes
    doc, rows = _files(base)
    row = _row(doc, R01)
    assert row["qualification"] == "recovery_observed"
    assert row["n1_applied_unconfirmed"] == 1 and row["duplicate_only_unexplained"] == 0
    (case,) = row["n1"]["n1_applied_unconfirmed"]
    assert case["message_id"] == "m2" and case["device_uuid"] == watch and case["seq"] == 2
    assert [s["source"] for s in case["possible_sources"]] == ["controller-death"]
    assert row["n1"]["events_copy"] == run_mod.POST_DRAIN_EVENTS_FILENAME
    assert rows[0]["n1_applied_unconfirmed"] == "1" and rows[0]["duplicate_only_unexplained"] == "0"
    assert set(rows[0]) == set(rq.CSV_COLUMNS)
    # Reported, never counted: the identity stays lost for the analyser and
    # the layer's statement, criterion and qualification rule are unchanged.
    per_run = list(csv.DictReader((base / "processed" / "per_run.csv").read_text(encoding="utf-8").splitlines()))
    assert int(next(r for r in per_run if r["run_id"] == R01)["lost"]) >= 1
    assert doc["statement"] == rq.STATEMENT
    for word in ("lost", "late", "N1", "acceptance"):
        assert word in doc["statement"]
    assert "n1_applied_unconfirmed" not in (base / "processed" / "acceptance_by_condition.csv").read_text("utf-8")


def test_without_the_captured_die_the_identity_is_unexplained(tmp_path, plan_path, fast_run, monkeypatch) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    _n1_evidence(base, plan_path, die=False)
    row = _row(rq.qualify_recovery(base, plan_path), R01)
    assert row["n1_applied_unconfirmed"] == 0 and row["duplicate_only_unexplained"] == 1
    (case,) = row["n1"]["duplicate_only_unexplained"]
    assert case["message_id"] == "m2" and case["failed"] == ["2"]


def test_a_drain_that_gave_up_names_no_identity(tmp_path, plan_path, fast_run, monkeypatch) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch, drain=("gaveup", 1))
    _n1_evidence(base, plan_path)
    doc = rq.qualify_recovery(base, plan_path)
    row = _row(doc, R01)
    assert row["qualification"] == "recovery_failed"
    assert row["n1_applied_unconfirmed"] == 0 and row["duplicate_only_unexplained"] == 1
    (case,) = row["n1"]["duplicate_only_unexplained"]
    assert "3" in case["failed"] and "drain" in case["reason"]


def test_a_planned_run_without_a_directory_has_empty_n1_columns(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    assert cli.main(["recovery", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    doc, rows = _files(base)
    for run_id in (R02, R03):
        absent = _row(doc, run_id)
        assert absent["n1_applied_unconfirmed"] is None and absent["duplicate_only_unexplained"] is None
        assert absent["n1"] is None
        row = next(r for r in rows if r["run_id"] == run_id)
        assert row["n1_applied_unconfirmed"] == "" and row["duplicate_only_unexplained"] == ""
    # The harness's own run: the fixture's post-drain copy holds one accepted
    # line and no duplicate-only identity, so both counts are zero.
    assert _row(doc, R01)["n1_applied_unconfirmed"] == 0 and _row(doc, R01)["duplicate_only_unexplained"] == 0


def test_a_malformed_capture_window_is_no_death_and_never_stops_the_layer(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """A coverage record whose window is not in ASCII digits (a superscript
    digit passes str.isdigit but not int) gives no death source: the layer
    and the recovery command run on, and the identity is unexplained."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    _n1_evidence(base, plan_path)
    coverage = base / "raw" / R01 / "logs" / "sut" / "docker-events.coverage.txt"
    coverage.write_text(coverage.read_text(encoding="utf-8").replace(
        "requested_until_guest_epoch=", "requested_until_guest_epoch=²"), encoding="utf-8")
    write_sha256sums(base / "raw" / R01)
    row = _row(rq.qualify_recovery(base, plan_path), R01)
    assert row["qualification"] == "recovery_observed"
    assert row["n1_applied_unconfirmed"] == 0 and row["duplicate_only_unexplained"] == 1
    (case,) = row["n1"]["duplicate_only_unexplained"]
    assert case["failed"] == ["2"] and "whole-number capture window" in case["reason"]
    assert cli.main(["recovery", "--base-dir", str(base), "--plan", str(plan_path)]) == 0


# round 1 of the verification ---------------------------------------------------


def test_a_duplicate_line_without_a_device_in_the_post_drain_copy_blocks_the_naming(
    tmp_path, plan_path, fast_run, monkeypatch
) -> None:
    """mx, published on the watch, has a duplicate line without a device in
    the verified post-drain copy (the harness's check of the copy accepts
    it) and the twin ended on its seq: the watch has two duplicate-only
    identities against a surplus of one, so neither is named."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    watch = _n1_evidence(base, plan_path)
    run_dir = base / "raw" / R01
    mx_sent = {"run_id": R01, "message_id": "mx", "device_uuid": watch, "device_type": "smartwatch", "seq": 3,
               "publish_monotonic_ns": 3, "puback_monotonic_ns": 3, "intended_invalid": False}
    mx_line = {"run_id": R01, "message_id": "mx", "device_type": "smartwatch", "seq": 3,
               "received_monotonic_ns": 5000, "outcome": "duplicate", "ditto_ack_monotonic_ns": None,
               "latency_ms": None, "attempts": 1, "error": None}
    for name, row in (("sent_events.jsonl", mx_sent), (run_mod.POST_DRAIN_EVENTS_FILENAME, mx_line)):
        path = run_dir / name
        path.write_text(path.read_text(encoding="utf-8") + json.dumps(row) + "\n", encoding="utf-8")
    after = json.loads((run_dir / "twins.after.json").read_text(encoding="utf-8"))
    after["devices"][watch]["ingestion"]["last_seq"] = 3
    (run_dir / "twins.after.json").write_text(json.dumps(after) + "\n", encoding="utf-8")
    write_sha256sums(run_dir)
    assert run_mod.post_drain_events_problems(run_dir / run_mod.POST_DRAIN_EVENTS_FILENAME, R01) == []
    row = _row(rq.qualify_recovery(base, plan_path), R01)
    assert row["qualification"] == "recovery_observed"
    assert row["n1_applied_unconfirmed"] == 0 and row["duplicate_only_unexplained"] == 2
    cases = {case["message_id"]: case for case in row["n1"]["duplicate_only_unexplained"]}
    assert "3" in cases["m2"]["failed"] and "3" in cases["mx"]["failed"]


DEEP = "[" * 100_000

#: (n1_applied_unconfirmed, duplicate_only_unexplained) of each case: m2 keeps
#: its death source unless the capture window is lost, and its twin
#: evidence unless the before snapshot is.
NEVER_STOPS = {
    "coverage epoch of 4301 digits": (0, 1),
    "deeply nested controller log line": (1, 0),
    "deeply nested Docker events line": (1, 0),
    "deeply nested sent line": (1, 0),
    "deeply nested snapshot": (0, 1),
    "many identities": (0, 1201),
}


@pytest.mark.parametrize("case", sorted(NEVER_STOPS))
def test_the_layer_never_stops_on_the_files_it_reads_for_the_n1_report(
    tmp_path, plan_path, fast_run, monkeypatch, capsys, case
) -> None:
    """The N1 report reads files the layer did not read before; nothing in
    them stops the layer (the default analyze runs it): a line the JSON
    decoder cannot nest into (RecursionError) is not a record, a window
    beyond int()'s digit limit is no window, and the matching of many
    identities to many A3 ends is not recursive."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    watch = _n1_evidence(base, plan_path)
    run_dir = base / "raw" / R01
    sut = run_dir / "logs" / "sut"
    if case == "coverage epoch of 4301 digits":
        coverage = sut / "docker-events.coverage.txt"
        coverage.write_text(coverage.read_text(encoding="utf-8").replace(
            "requested_until_guest_epoch=", "requested_until_guest_epoch=1" + "0" * 4300 + "\nx="), encoding="utf-8")
    elif case == "deeply nested controller log line":
        (sut / "controller.log").write_text("2026-09-30T10:03:10.000000000Z {\"message\": " + DEEP + "\n",
                                            encoding="utf-8")
    elif case == "deeply nested Docker events line":
        capture = sut / "docker-events.log"
        capture.write_text("{\"Action\": " + DEEP + "\n" + capture.read_text(encoding="utf-8"), encoding="utf-8")
    elif case == "deeply nested sent line":
        sent_file = run_dir / "sent_events.jsonl"
        sent_file.write_text(sent_file.read_text(encoding="utf-8") + "{\"a\": " + DEEP + "\n", encoding="utf-8")
    elif case == "deeply nested snapshot":
        (run_dir / "twins.before.json").write_text("{\"devices\": " + DEEP + "\n", encoding="utf-8")
    else:
        count = 1200
        sent = [{"run_id": R01, "message_id": f"k{i}", "device_uuid": watch, "device_type": "smartwatch",
                 "seq": 10 + i, "publish_monotonic_ns": 1, "puback_monotonic_ns": 1, "intended_invalid": False}
                for i in range(count)]
        lines = [dict(record, received_monotonic_ns=NS + i, outcome="duplicate", ditto_ack_monotonic_ns=None,
                      latency_ms=None, attempts=1, error=None) for i, record in enumerate(sent)]
        for name, rows in (("sent_events.jsonl", sent), (run_mod.POST_DRAIN_EVENTS_FILENAME, lines)):
            path = run_dir / name
            path.write_text(path.read_text(encoding="utf-8") + "".join(json.dumps(r) + "\n" for r in rows),
                            encoding="utf-8")
        end = {"ts": "2026-09-30T10:03:10.001Z", "level": "ERROR", "message": "MQTT connection ended by the controller",
               "context": {"cause": "write-failed", "connection": 2,
                           "identity": {"topic": f"c2dt/egw-01/{watch}/telemetry", "received_monotonic_ns": 1}}}
        (sut / "controller.log").write_text("".join(json.dumps(end) + "\n" for _ in range(count)), encoding="utf-8")
    write_sha256sums(run_dir)
    assert cli.main(["recovery", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    if case != "deeply nested sent line":  # the analyser itself reads sent_events.jsonl (and stops on that line)
        assert cli.main(["analyze", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    capsys.readouterr()
    doc, _rows = _files(base)
    row = _row(doc, R01)
    assert row["qualification"] == "recovery_observed"
    assert (row["n1_applied_unconfirmed"], row["duplicate_only_unexplained"]) == NEVER_STOPS[case]


def test_an_n1_report_that_cannot_be_made_never_stops_the_layer(
    tmp_path, plan_path, fast_run, monkeypatch, capsys
) -> None:
    """Whatever the report meets, the qualification and the files stand:
    an exception inside it leaves the run's N1 columns empty and says why."""
    base = _restart_run(tmp_path, plan_path, fast_run, monkeypatch)
    _n1_evidence(base, plan_path)

    def boom(**_kwargs):
        raise RuntimeError("unforeseen")

    monkeypatch.setattr(rq.n1_report, "n1_applied_unconfirmed", boom)
    assert cli.main(["recovery", "--base-dir", str(base), "--plan", str(plan_path)]) == 0
    capsys.readouterr()
    doc, rows = _files(base)
    row = _row(doc, R01)
    assert row["qualification"] == "recovery_observed"
    assert row["n1_applied_unconfirmed"] is None and row["duplicate_only_unexplained"] is None
    assert row["n1"]["events_copy"] is None and "RuntimeError" in row["n1"]["problem"]
    assert rows[0]["n1_applied_unconfirmed"] == "" and rows[0]["duplicate_only_unexplained"] == ""


def test_recovery_subcommand_is_documented_with_the_analyze_defaults() -> None:
    args = cli.build_parser().parse_args(["recovery"])
    assert args.plan == cli.DEFAULT_PLAN_PATH and args.base_dir is None
    assert "recovery [--base-dir PATH] [--plan PATH]" in (cli.__doc__ or "")
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["recovery", "--help"])
