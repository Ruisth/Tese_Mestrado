"""Cases for tools/session/proof_plan.py: the one-entry diagnostic plan of
the finite proof of ADR 0011.

The helper is run as the driver runs it, a subprocess of this interpreter
with the clone's ``src`` on PYTHONPATH, and what it writes is read back
through the harness's own plan loader and executed by the harness with the
fake simulator and the recorded item-18 hooks of test_experiments_run: no
broker, no docker, no guest. What these cases show is the entry the harness
is given (its shape against ``plan_gen._run_entry``, its seed against
``derive_run_seed``), the refusals that leave nothing written, and that the
harness reads the entry as the proof's run.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from egw_experiments import plan_gen, protocol
from egw_experiments import run as run_mod
from test_experiments_run import (  # noqa: F401  (the fixture is registered by import)
    _item18_run,
    _manifest,
    _step_lines,
    fast_run,
)

SRC_DIR = Path(__file__).resolve().parents[1]
HELPER = SRC_DIR.parent / "tools" / "session" / "proof_plan.py"

RID = "proof-adr0011-r01"
SEED = 42
PILOT_RID = "controller_restart-r01"
DIAGNOSTIC_PREFIX = "diagnostic: duration_s 300 for the finite proof (ADR 0011)"


def _write(tmp_path: Path, *args: str, run_id: str = RID, master_seed: str = str(SEED),
           out: Path | None = None) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the helper's ``write`` as the driver does; (its result, the plan path)."""
    out = out or tmp_path / "proof" / f"plan-{run_id}.json"
    result = subprocess.run(
        [sys.executable, str(HELPER), "write", "--run-id", run_id, "--master-seed", master_seed,
         "--out", str(out), *args],
        env={**os.environ, "PYTHONPATH": str(SRC_DIR)}, capture_output=True, text=True)
    return result, out


def _pilot_plan(tmp_path: Path, *extra_run_ids: str) -> Path:
    """A pilot plan as the runbook generates it (``plan --master-seed 42``),
    with ``extra_run_ids`` appended as entries of its own."""
    plan = plan_gen.generate_campaign_plan(42)
    for run_id in extra_run_ids:
        plan["runs"].append(dict(plan["runs"][-1], run_id=run_id))
    return plan_gen.write_campaign_plan(plan, tmp_path / "pilot" / "campaign_plan.json")


# ---------------------------------------------------------------------------
# the plan: one controller_restart entry of 300 s with the derived seed
# ---------------------------------------------------------------------------


def test_the_diagnostic_plan_has_one_controller_restart_entry_of_300_s_with_the_derived_seed(tmp_path):
    result, out = _write(tmp_path)
    assert result.returncode == 0, result.stderr
    plan = plan_gen.load_campaign_plan(out)

    # The campaign plan's shape, one condition and one run.
    campaign = plan_gen.generate_campaign_plan(SEED)
    assert set(plan) == set(campaign)
    assert (plan["plan_version"], plan["protocol_version"], plan["master_seed"]) == (
        plan_gen.PLAN_VERSION, protocol.PROTOCOL_VERSION, SEED)
    assert len(plan["runs"]) == 1 and len(plan["conditions"]) == 1

    # The entry is plan_gen._run_entry of the frozen controller_restart
    # condition but for the proof's duration_s, numbered as the generator
    # numbers its runs; its seed is derive_run_seed's.
    frozen = protocol.CONDITIONS_BY_ID["controller_restart"]
    expected = plan_gen._run_entry(frozen, RID, 1, SEED, protocol.NOMINAL_RATE_MSG_S)
    expected.update(duration_s=300, order=1)
    (entry,) = plan["runs"]
    assert entry == expected
    assert entry["seed"] == plan_gen.derive_run_seed(SEED, RID)
    assert (entry["condition_id"], entry["scenario"], entry["runner"]) == (
        "controller_restart", "nominal", "simulator")
    assert (entry["duration_s"], entry["warmup_s"], entry["cooldown_s"]) == (300, 0, 0)
    assert entry["rate_msg_s"] == 11.2 == protocol.NOMINAL_RATE_MSG_S
    assert (entry["repetition"], entry["status"], entry["order"]) == (1, "planned", 1)
    # The harness's default restart instant for this entry is the ADR's t+150 s.
    assert entry["duration_s"] / 2.0 == 150.0

    # The condition record states the same figures as the entry, annotated
    # as the proof's diagnostic; every other field is the frozen condition's.
    (condition,) = plan["conditions"]
    assert condition["notes"].startswith(DIAGNOSTIC_PREFIX)
    assert (condition["duration_s"], condition["repetitions"]) == (300, 1)
    for key, value in frozen.to_dict().items():
        if key not in ("duration_s", "repetitions", "notes"):
            assert condition[key] == value, key


def test_the_plan_is_byte_identical_on_repeat_and_the_line_names_its_sha256(tmp_path):
    first, out_a = _write(tmp_path, out=tmp_path / "a" / "plan.json")
    second, out_b = _write(tmp_path, out=tmp_path / "b" / "plan.json")
    assert first.returncode == 0 and second.returncode == 0
    body = out_a.read_bytes()
    assert body == out_b.read_bytes()
    # The campaign plan's canonical serialisation: sorted keys, two-space
    # indent, one trailing newline, no timestamp, LF only.
    assert body == plan_gen.plan_to_json(json.loads(body)).encode("utf-8")
    assert b"\r" not in body
    digest = hashlib.sha256(body).hexdigest()
    line = first.stdout.strip()
    assert line.startswith(f"wrote {out_a}: run_id={RID} condition_id=controller_restart ")
    assert f" duration_s=300 warmup_s=0 cooldown_s=0 rate_msg_s=11.2 seed={plan_gen.derive_run_seed(SEED, RID)} " in line
    assert line.endswith(f"master_seed={SEED} sha256={digest}")
    assert first.stderr == ""


# ---------------------------------------------------------------------------
# the refusals: nothing is written
# ---------------------------------------------------------------------------


def test_refuses_a_run_id_present_in_the_pilot_plan_and_never_edits_it(tmp_path):
    pilot = _pilot_plan(tmp_path, "proof-adr0011-taken")
    before = pilot.read_bytes()

    refused, out = _write(tmp_path, "--pilot-plan", str(pilot), run_id="proof-adr0011-taken")
    assert refused.returncode == 2
    assert not out.exists()
    assert refused.stderr.startswith("STOP: proof_plan: ")
    assert "'proof-adr0011-taken' is in the pilot plan" in refused.stderr
    assert "never an entry of the pilot plan" in refused.stderr
    assert refused.stderr.rstrip().endswith("nothing was written")

    # A fresh run id is written with the pilot plan named, and the pilot plan
    # is exactly what it was.
    written, out = _write(tmp_path, "--pilot-plan", str(pilot))
    assert written.returncode == 0, written.stderr
    assert out.is_file()
    assert pilot.read_bytes() == before


def test_refuses_a_run_id_the_campaign_plan_enumerates_without_a_pilot_plan_file(tmp_path):
    # The campaign's run ids do not depend on the master seed, so the guard
    # needs no pilot plan file: every id the pilot plan would hold is refused.
    for run_id in (PILOT_RID, "nominal-r01", "load_sweep-010mps-r01", "qemu_boot-r01", "soak-r01"):
        refused, out = _write(tmp_path, run_id=run_id)
        assert refused.returncode == 2, run_id
        assert not out.exists()
        assert f"the run id {run_id!r} is one the campaign plan enumerates" in refused.stderr
        assert refused.stderr.rstrip().endswith("nothing was written")


def test_refuses_a_pilot_plan_it_cannot_read(tmp_path):
    missing = tmp_path / "pilot" / "campaign_plan.json"
    refused, out = _write(tmp_path, "--pilot-plan", str(missing))
    assert refused.returncode == 2 and not out.exists()
    assert "could not be read" in refused.stderr
    assert f"that {RID!r} is absent from it cannot be established" in refused.stderr

    not_a_plan = tmp_path / "pilot" / "not-a-plan.json"
    not_a_plan.parent.mkdir(parents=True, exist_ok=True)
    not_a_plan.write_text('{"plan_version": "1.0"}\n', encoding="utf-8")
    refused, out = _write(tmp_path, "--pilot-plan", str(not_a_plan))
    assert refused.returncode == 2 and not out.exists()
    assert "no 'runs' list of entries" in refused.stderr

    not_json = tmp_path / "pilot" / "broken.json"
    not_json.write_text("{", encoding="utf-8")
    refused, out = _write(tmp_path, "--pilot-plan", str(not_json))
    assert refused.returncode == 2 and not out.exists()
    assert "could not be read" in refused.stderr


@pytest.mark.parametrize("master_seed", ["4.2", "-1", "+7", "1_000", "42 ", " 42", "forty-two", "", "0x2a"])
def test_refuses_a_master_seed_that_is_not_a_whole_number(tmp_path, master_seed):
    refused, out = _write(tmp_path, master_seed=master_seed)
    assert refused.returncode == 2
    assert not out.exists()
    assert f"the master seed {master_seed!r} is not a whole number" in refused.stderr


@pytest.mark.parametrize("master_seed", ["0", "42", "18446744073709551616"])
def test_accepts_every_whole_number_as_the_master_seed(tmp_path, master_seed):
    written, out = _write(tmp_path, master_seed=master_seed)
    assert written.returncode == 0, written.stderr
    plan = plan_gen.load_campaign_plan(out)
    assert plan["master_seed"] == int(master_seed)
    assert plan["runs"][0]["seed"] == plan_gen.derive_run_seed(int(master_seed), RID)


def test_refuses_an_existing_output_file_and_leaves_it_as_it_was(tmp_path):
    out = tmp_path / "proof" / f"plan-{RID}.json"
    out.parent.mkdir(parents=True)
    out.write_text("not a plan\n", encoding="utf-8")
    refused, _ = _write(tmp_path, out=out)
    assert refused.returncode == 2
    assert f"{out} exists: the plan is write-once and is not replaced" in refused.stderr
    assert out.read_text(encoding="utf-8") == "not a plan\n"


@pytest.mark.parametrize("run_id", ["proof adr0011", "proof/adr0011", "a" * 65, "", "proof:r01"])
def test_refuses_a_run_id_outside_the_charset_of_contracts_2(tmp_path, run_id):
    refused, out = _write(tmp_path, run_id=run_id)
    assert refused.returncode == 2
    assert not out.exists()
    assert f"the run id {run_id!r} is outside the charset of CONTRACTS 2" in refused.stderr


def test_a_usage_error_writes_nothing(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    out = tmp_path / "plan.json"
    for argv in (
        [],
        ["write"],
        ["write", "--run-id", RID, "--master-seed", "42"],
        ["write", "--run-id", RID, "--out", str(out)],
        ["read", "--run-id", RID, "--master-seed", "42", "--out", str(out)],
    ):
        result = subprocess.run([sys.executable, str(HELPER), *argv], env=env,
                                capture_output=True, text=True)
        assert result.returncode == 2, argv
        assert "usage: proof_plan.py write --run-id RID --master-seed N --out PATH" in result.stderr
    assert not out.exists()


# ---------------------------------------------------------------------------
# the harness accepts the plan and reads the entry as the proof's run
# ---------------------------------------------------------------------------


def test_the_harness_loads_the_plan_and_runs_the_entry_with_the_restart_evidence_hooks(
    tmp_path, fast_run, monkeypatch
):
    result, proof_plan = _write(tmp_path)
    assert result.returncode == 0, result.stderr

    # The harness's own loader and lookup (execute_run: the run id must be in
    # the plan it is given): the proof's id is, the pilot's is not.
    loaded = run_mod.load_campaign_plan(proof_plan)
    assert [entry["run_id"] for entry in loaded["runs"]] == [RID]
    assert run_mod.execute_run(proof_plan, PILOT_RID, base_dir=tmp_path / "refused") == 2
    assert not (tmp_path / "refused").exists()

    rc, run_dir, record = _item18_run(tmp_path, proof_plan, fast_run, monkeypatch, run_id=RID)
    assert rc == 0
    assert run_dir == tmp_path / "results" / "raw" / RID

    # The simulator was given the entry's figures (CONTRACTS 7 argv).
    (argv,) = [cmd for cmd in fast_run.calls if cmd[cmd.index("--run-id") + 1] == RID]
    given = {flag: argv[argv.index(flag) + 1] for flag in ("--scenario", "--seed", "--duration", "--rate")}
    assert given == {
        "--scenario": "nominal",
        "--seed": str(plan_gen.derive_run_seed(SEED, RID)),
        "--duration": "300",
        "--rate": "11.2",
    }

    # The manifest records the entry as read, and the restart-evidence
    # steps ran because the condition is controller_restart.
    manifest = _manifest(run_dir.parent.parent, RID)
    assert manifest["validity"] == "valid"
    assert manifest["plan_master_seed"] == SEED
    assert (manifest["condition_id"], manifest["scenario"], manifest["runner"]) == (
        "controller_restart", "nominal", "simulator")
    assert (manifest["duration_s"], manifest["warmup_s"], manifest["cooldown_s"]) == (300, 0, 0)
    assert manifest["rate_msg_s"] == 11.2
    assert manifest["seed"] == plan_gen.derive_run_seed(SEED, RID)
    assert manifest["repetition"] == 1
    assert manifest["restart"]["executed"] is True
    assert [s["hook"] for s in manifest["twin_snapshots"]] == [
        "twin_snapshot_before", "twin_snapshot_after"]
    assert all(s["verified"] is True for s in manifest["twin_snapshots"])
    assert manifest["drain"]["outcome"] == "quiet" and manifest["drain"]["verified"] is True
    assert manifest["events_post_drain_fetch"]["ok"] is True
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
    # No warm-up run: the fake simulator was started once, for the measured run.
    assert len(fast_run.calls) == 1
