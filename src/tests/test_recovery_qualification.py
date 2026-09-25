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
from test_experiments_run import (  # noqa: F401  (fixtures registered by import)
    DRAIN_GAVE_UP_LINE,
    _bare_restart_run,
    _external_evidence,
    _item18_run,
    _manifest,
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


def test_recovery_subcommand_is_documented_with_the_analyze_defaults() -> None:
    args = cli.build_parser().parse_args(["recovery"])
    assert args.plan == cli.DEFAULT_PLAN_PATH and args.base_dir is None
    assert "recovery [--base-dir PATH] [--plan PATH]" in (cli.__doc__ or "")
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["recovery", "--help"])
