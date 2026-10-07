"""Cases for tools/session/g4_pilot_plan.py: the five-entry input plan of
the G4 bounded pilot (plan section 4.3, G4; runbook section 8 item 1).

The tool is run as the operator runs it, a subprocess of this interpreter
with the clone's ``src`` on PYTHONPATH (as test_proof_plan runs
proof_plan.py), and its functions are loaded from the file where a case
needs the plan as a value. What these cases show: the committed plan is the
tool's plan for the working master seed, byte for byte; every departure
from the frozen conditions is declared and none is undeclared; the ids and
seeds are fresh against G3's plan, the campaign plan of master seed 42, the
finite proof and the run_test seeds; the refusals write nothing; the
harness runs each entry, through a working copy, as the plan states it
(the fake simulator of test_experiments_run: no broker, no docker, no
guest); ``check`` refuses what would spend or mutate a run wrongly; and
``analyze`` treats the five-entry plan as experiments/g4-pilot/README.md
says.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from egw_experiments import analyze, cli, plan_gen, protocol
from egw_experiments import run as run_mod
from egw_experiments.analyze import CAMPAIGN_PLAN_ENV_VAR
from egw_simulator.devices import DEVICE_TYPES, device_uuid_for
from test_experiments_run import (  # noqa: F401  (the fixture is registered by import)
    FIXTURE_SERVICES,
    _local_events,
    _manifest,
    _plan_entry,
    _resources_file,
    _sut_env_file,
    fast_run,
)

SRC_DIR = Path(__file__).resolve().parents[1]
REPO = SRC_DIR.parent
TOOL = REPO / "tools" / "session" / "g4_pilot_plan.py"
PILOT_DIR = REPO / "experiments" / "g4-pilot"
COMMITTED = PILOT_DIR / "g4_pilot_plan.json"

#: The working master seed of the committed plan (the student's to confirm;
#: the tool has no default) and the fixed test seed of test_proof_plan.
WORKING_SEED = 20261007
TEST_SEED = 42

IDS = (
    "g4pilot-s1-nominal-0120s-11p2mps-a01",
    "g4pilot-s2-nominal-0600s-11p2mps-a01",
    "g4pilot-s3-loadsweep-0300s-010mps-a01",
    "g4pilot-s3-loadsweep-0300s-050mps-a01",
    "g4pilot-s4-soak-3600s-11p2mps-a01",
)

#: The five stages as runbook section 8 item 1 and plan section 4.3 state
#: them: (condition, scenario, rate, duration, warm-up, cool-down, stage).
FIGURES = {
    IDS[0]: ("nominal", "nominal", 11.2, 120, 0, 0, 1),
    IDS[1]: ("nominal", "nominal", 11.2, 600, 120, 0, 2),
    IDS[2]: ("load_sweep", "load-sweep", 10.0, 300, 0, 120, 3),
    IDS[3]: ("load_sweep", "load-sweep", 50.0, 300, 0, 120, 3),
    IDS[4]: ("soak", "soak", 11.2, 3600, 0, 0, 4),
}

#: The seeds the committed plan holds (derive_run_seed of 20261007).
WORKING_SEEDS = {
    IDS[0]: 3340462373,
    IDS[1]: 2626471893,
    IDS[2]: 3694409732,
    IDS[3]: 174127109,
    IDS[4]: 2294608585,
}

#: Spent elsewhere: G3's supplement (test_experiments_plan), the finite
#: proof r03 (its sealed plan), the run_test seeds of the runbook (42 is
#: also the simulator's default seed).
G3_R04_SEED = 1715385812
PROOF_R03_SEED = 265481284
RUN_TEST_SEEDS = (42, 7)

#: The fields the harness writes beside the status (run.py, update_plan_status).
HARNESS_WRITTEN = ("status", "result_dir", "finished_utc", "validity")


def _load_tool():
    spec = importlib.util.spec_from_file_location("g4_pilot_plan", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return _load_tool()


def _run_tool(*argv: str, home: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run([sys.executable, str(TOOL), *argv], env=env,
                          capture_output=True, text=True)


def _write(tmp_path: Path, *args: str, master_seed: str = str(WORKING_SEED),
           out: Path | None = None, home: Path | None = None) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the tool's ``write`` as the operator does; (its result, the plan path)."""
    out = out or tmp_path / "g4-pilot" / "plan" / "g4_pilot_plan.sealed.json"
    return _run_tool("write", "--master-seed", master_seed, "--out", str(out), *args, home=home), out


def _check(working: Path, sealed: Path, base: Path, run_id: str, *args: str,
           forbid_under: Path | None, home: Path | None = None) -> subprocess.CompletedProcess:
    forbid = ["--forbid-under", str(forbid_under)] if forbid_under is not None else []
    return _run_tool("check", "--plan", str(working), "--sealed", str(sealed), "--base-dir", str(base),
                     "--run-id", run_id, *forbid, *args, home=home)


def _canonical(plan: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan_gen.plan_to_json(plan), encoding="utf-8", newline="\n")
    return path


def _pair(tmp_path: Path, tool) -> tuple[Path, Path, Path]:
    """A sealed plan, its working byte copy and the pilot results base."""
    sealed = _canonical(tool.build_pilot_plan(WORKING_SEED),
                        tmp_path / "g4-pilot" / "plan" / "g4_pilot_plan.sealed.json")
    working = sealed.with_name("g4_pilot_plan.json")
    working.write_bytes(sealed.read_bytes())
    return working, sealed, tmp_path / "g4-pilot" / "results"


def _g3_plan(tmp_path: Path, *extra_entries: dict) -> Path:
    """G3's plan as it stands: the campaign plan of master seed 42 with the
    g3-t6 supplement (controller_restart-r04), plus ``extra_entries``."""
    path = plan_gen.write_campaign_plan(plan_gen.generate_campaign_plan(42),
                                        tmp_path / "pilot" / "campaign_plan.json")
    plan_gen.apply_plan_supplement(path, "g3-t6")
    if extra_entries:
        plan = plan_gen.load_campaign_plan(path)
        plan["runs"].extend(extra_entries)
        _canonical(plan, path)
    return path


def _refused(result: subprocess.CompletedProcess, *phrases: str) -> None:
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert result.stderr.startswith("STOP: g4_pilot_plan: "), result.stderr
    assert result.stderr.rstrip().endswith("nothing was written"), result.stderr
    for phrase in phrases:
        assert phrase in result.stderr, (phrase, result.stderr)


# ---------------------------------------------------------------------------
# the committed plan is the tool's plan for the working master seed
# ---------------------------------------------------------------------------


def test_the_committed_plan_is_the_tools_plan_for_the_working_master_seed_byte_for_byte(tool):
    body = COMMITTED.read_bytes()
    assert body == plan_gen.plan_to_json(tool.build_pilot_plan(WORKING_SEED)).encode("utf-8")
    assert b"\r" not in body and body.endswith(b"}\n")
    plan = json.loads(body)
    assert plan["master_seed"] == WORKING_SEED
    assert {e["run_id"]: e["seed"] for e in plan["runs"]} == WORKING_SEEDS
    assert tool.plan_problems(plan) == []


def test_write_gives_the_committed_bytes_and_names_each_entry_and_the_sha256(tmp_path):
    written, out = _write(tmp_path)
    assert written.returncode == 0, written.stderr
    assert written.stderr == ""
    body = out.read_bytes()
    assert body == COMMITTED.read_bytes()
    lines = written.stdout.splitlines()
    assert len(lines) == 6
    for order, (line, rid) in enumerate(zip(lines, IDS), start=1):
        cid, scenario, rate, duration, warmup, cooldown, stage = FIGURES[rid]
        assert line == (
            f"entry {order}: run_id={rid} stage={stage} condition_id={cid} scenario={scenario} "
            f"duration_s={duration} warmup_s={warmup} cooldown_s={cooldown} rate_msg_s={rate} "
            f"seed={WORKING_SEEDS[rid]}")
    assert lines[-1] == (f"wrote {out}: entries=5 master_seed={WORKING_SEED} "
                         f"sha256={hashlib.sha256(body).hexdigest()}")

    # Byte-identical on repeat.
    again, out_b = _write(tmp_path, out=tmp_path / "again" / "plan.json")
    assert again.returncode == 0, again.stderr
    assert out_b.read_bytes() == body


def test_the_pilot_readme_names_the_committed_plans_sha256():
    readme = (PILOT_DIR / "README.md").read_text(encoding="utf-8")
    assert hashlib.sha256(COMMITTED.read_bytes()).hexdigest() in readme


# ---------------------------------------------------------------------------
# the plan: five entries, the frozen records verbatim, every departure declared
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("master_seed", [WORKING_SEED, TEST_SEED])
def test_five_entries_in_stage_order_with_the_stated_figures_and_derived_seeds(tool, master_seed):
    plan = tool.build_pilot_plan(master_seed)
    assert set(plan) == {"plan_version", "protocol_version", "master_seed", "conditions", "runs", "pilot"}
    assert (plan["plan_version"], plan["protocol_version"], plan["master_seed"]) == (
        plan_gen.PLAN_VERSION, protocol.PROTOCOL_VERSION, master_seed)
    assert [entry["run_id"] for entry in plan["runs"]] == list(IDS)
    for order, entry in enumerate(plan["runs"], start=1):
        cid, scenario, rate, duration, warmup, cooldown, stage = FIGURES[entry["run_id"]]
        # plan_gen._run_entry of the frozen condition but for the pilot's
        # figures, numbered in stage order, plus the inert 'pilot' block.
        expected = plan_gen._run_entry(protocol.CONDITIONS_BY_ID[cid], entry["run_id"], 1, master_seed, rate)
        expected.update(duration_s=duration, warmup_s=warmup, cooldown_s=cooldown, order=order)
        assert {k: v for k, v in entry.items() if k != "pilot"} == expected
        assert entry["seed"] == plan_gen.derive_run_seed(master_seed, entry["run_id"])
        assert (entry["runner"], entry["scenario"], entry["status"]) == ("simulator", scenario, "planned")
        assert set(entry["pilot"]) == {"stage", "label", "deviations"}
        assert (entry["pilot"]["stage"], entry["pilot"]["label"]) == (stage, "PILOT - NON-CITABLE")

    text = plan_gen.plan_to_json(plan)
    assert plan_gen.plan_to_json(tool.build_pilot_plan(master_seed)) == text
    assert plan_gen.plan_to_json(json.loads(text)) == text
    # The plan never supplies an execution mode: that belongs to the run's
    # own provenance records, declared at run time.
    assert "execution_mode" not in text
    assert tool.plan_problems(plan) == []


def test_the_condition_records_are_the_frozen_ones_verbatim(tool):
    plan = tool.build_pilot_plan(WORKING_SEED)
    assert plan["conditions"] == [
        protocol.CONDITIONS_BY_ID[cid].to_dict() for cid in ("nominal", "load_sweep", "soak")]


def _departures(entry: dict) -> list[dict]:
    """What an entry departs from in its frozen condition, computed here."""
    frozen = protocol.CONDITIONS_BY_ID[entry["condition_id"]]
    out = []
    for field in ("runner", "scenario", "rate_msg_s", "duration_s", "warmup_s", "cooldown_s"):
        if field == "rate_msg_s" and frozen.rates_msg_s:
            # A sweep entry runs one of the sweep's levels.
            if entry[field] not in frozen.rates_msg_s:
                out.append({"field": field, "frozen": list(frozen.rates_msg_s), "pilot": entry[field]})
            continue
        if entry[field] != getattr(frozen, field):
            out.append({"field": field, "frozen": getattr(frozen, field), "pilot": entry[field]})
    return sorted(out, key=lambda d: d["field"])


def test_every_departure_of_an_entry_is_declared_and_none_is_undeclared(tool):
    plan = tool.build_pilot_plan(WORKING_SEED)
    declared = {}
    for entry in plan["runs"]:
        stated = entry["pilot"]["deviations"]
        for deviation in stated:
            assert set(deviation) == {"field", "frozen", "pilot", "basis"}
            # Each basis names where the pilot's value comes from, file:line.
            assert re.search(r"[\w./-]+\.(md|py):[0-9]+", deviation["basis"]), deviation
        declared[entry["run_id"]] = sorted(
            ({k: v for k, v in d.items() if k != "basis"} for d in stated), key=lambda d: d["field"])
        assert declared[entry["run_id"]] == _departures(entry)
    assert declared == {
        IDS[0]: [{"field": "duration_s", "frozen": 600, "pilot": 120},
                 {"field": "warmup_s", "frozen": 120, "pilot": 0}],
        IDS[1]: [],
        IDS[2]: [],
        IDS[3]: [],
        IDS[4]: [{"field": "duration_s", "frozen": 86_400, "pilot": 3600}],
    }


def test_the_condition_level_departures_are_declared_for_every_condition(tool):
    plan = tool.build_pilot_plan(WORKING_SEED)
    pilot = plan["pilot"]
    assert (pilot["non_citable"], pilot["not_campaign_attempts"]) == (True, True)
    assert pilot["purpose"]
    declared = pilot["deviations_from_protocol"]
    # Every condition of the frozen protocol, the ones this pilot does not
    # run included: "all conditions" is recorded, never silently waived.
    assert [row["condition_id"] for row in declared] == [c.id for c in protocol.CONDITIONS]
    for row, condition in zip(declared, protocol.CONDITIONS):
        mine = [e for e in plan["runs"] if e["condition_id"] == condition.id]
        levels = list(condition.rates_msg_s) if condition.rates_msg_s else (
            [condition.rate_msg_s] if condition.rate_msg_s is not None else [])
        assert row["frozen_runs"] == condition.repetitions * max(1, len(condition.rates_msg_s or ()))
        assert row["pilot_runs"] == len(mine)
        assert row["frozen_rates_msg_s"] == levels
        assert row["pilot_rates_msg_s"] == sorted({e["rate_msg_s"] for e in mine})
        assert row["note"] and re.search(r"[\w./-]+\.(md|py):[0-9]+", row["basis"]), row
        if condition.id == "load_sweep":
            assert row["pilot_order_msg_s"] == [e["rate_msg_s"] for e in sorted(mine, key=lambda e: e["order"])]
            assert "randomised" in row["frozen_order"]
        else:
            assert "pilot_order_msg_s" not in row and "frozen_order" not in row
    counts = {row["condition_id"]: (row["frozen_runs"], row["pilot_runs"]) for row in declared}
    assert counts == {
        "qemu_boots": (5, 0), "cold_start": (10, 0), "twin_creation": (10, 0), "smoke_sequence": (10, 0),
        "nominal": (10, 2), "load_sweep": (40, 2), "invalid_payload": (3, 0), "dropout_reconnect": (3, 0),
        "controller_restart": (3, 0), "soak": (1, 1),
    }
    # The frozen sweep order IS randomised by the master seed: the pilot's
    # fixed ascending order is a departure.
    sweep_order = [e["rate_msg_s"] for e in plan_gen.generate_campaign_plan(42)["runs"]
                   if e["condition_id"] == "load_sweep"]
    assert sweep_order != sorted(sweep_order)


def test_every_field_of_every_entry_has_a_source(tool):
    plan = tool.build_pilot_plan(WORKING_SEED)
    sources = plan["pilot"]["sources"]
    assert set(sources["runs"]) == set(IDS)
    for entry in plan["runs"]:
        named = sources["runs"][entry["run_id"]]
        assert set(named) == set(entry) - {"pilot"}, entry["run_id"]
        for field, source in named.items():
            assert re.search(r"[\w./-]+\.(md|py):[0-9]+", source), (entry["run_id"], field, source)
    assert set(sources["plan"]) == {
        "plan_version", "protocol_version", "master_seed", "conditions", "non_citable", "not_campaign_attempts"}


def test_the_checker_finds_a_figure_or_a_declaration_that_was_changed(tool):
    good = tool.build_pilot_plan(WORKING_SEED)
    assert tool.plan_problems(good) == []

    changed = json.loads(json.dumps(good))
    changed["runs"][0]["duration_s"] = 600
    assert any("duration_s" in p for p in tool.plan_problems(changed))

    undeclared = json.loads(json.dumps(good))
    undeclared["runs"][0]["pilot"]["deviations"].pop()
    assert any("declares" in p for p in tool.plan_problems(undeclared))

    reseeded = json.loads(json.dumps(good))
    reseeded["runs"][3]["seed"] = 1
    assert any("seed" in p for p in tool.plan_problems(reseeded))

    miscounted = json.loads(json.dumps(good))
    miscounted["pilot"]["deviations_from_protocol"][5]["pilot_runs"] = 40
    assert any("deviations_from_protocol" in p for p in tool.plan_problems(miscounted))

    swapped = json.loads(json.dumps(good))
    swapped["runs"][2], swapped["runs"][3] = swapped["runs"][3], swapped["runs"][2]
    assert tool.plan_problems(swapped)


# ---------------------------------------------------------------------------
# the ids and the seeds
# ---------------------------------------------------------------------------


def test_the_ids_state_their_figures_and_can_never_be_read_as_campaign_ids(tool):
    plan = tool.build_pilot_plan(WORKING_SEED)
    campaign_ids = {e["run_id"] for seed in (0, 42, WORKING_SEED)
                    for e in plan_gen.generate_campaign_plan(seed)["runs"]}
    supplement_ids = {plan_gen.supplementary_entry(42, key, 96)["run_id"] for key in plan_gen.SUPPLEMENTS}
    kinds = {"nominal": "nominal", "load_sweep": "loadsweep", "soak": "soak"}
    for entry in plan["runs"]:
        rid = entry["run_id"]
        assert tool.PILOT_ID_RE.fullmatch(rid)
        parts = re.fullmatch(
            r"g4pilot-s([1-4])-(nominal|loadsweep|soak)-([0-9]{4})s-([0-9]{3}|[0-9]+p[0-9])mps-a([0-9]{2})", rid)
        assert parts is not None, rid
        stage, kind, duration, rate, attempt = parts.groups()
        assert int(stage) == entry["pilot"]["stage"]
        assert kind == kinds[entry["condition_id"]]
        assert int(duration) == entry["duration_s"]
        assert float(rate.replace("p", ".")) == entry["rate_msg_s"]
        assert attempt == "01"
        assert rid not in campaign_ids | supplement_ids
        assert not any(rid.startswith(c.id) for c in protocol.CONDITIONS) and not rid.startswith("qemu_boot")
        assert not re.search(r"-r[0-9]{2}$", rid)
        # The harness's warm-up id still fits CONTRACTS 2.
        assert len(rid) <= 57 and plan_gen.RUN_ID_RE.fullmatch(rid + ".warmup")
    # The request's illustrative id is refused: it mimics a repetition number.
    assert tool.PILOT_ID_RE.fullmatch("g4pilot-nominal120-r01") is None


@pytest.mark.parametrize("master_seed", [WORKING_SEED, TEST_SEED])
def test_the_seeds_and_devices_are_fresh_against_g3_the_campaign_the_proof_and_run_test(tool, master_seed):
    plan = tool.build_pilot_plan(master_seed)
    seeds = [entry["seed"] for entry in plan["runs"]]
    assert len(set(seeds)) == 5

    g3 = plan_gen.generate_campaign_plan(42)
    r04 = plan_gen.supplementary_entry(42, "g3-t6", 96)
    assert (r04["run_id"], r04["seed"]) == ("controller_restart-r04", G3_R04_SEED)
    foreign = {e["seed"] for e in g3["runs"]} | {G3_R04_SEED, PROOF_R03_SEED, *RUN_TEST_SEEDS}
    assert not set(seeds) & foreign

    def devices(of_seeds):
        return {device_uuid_for(seed, device_type) for seed in of_seeds for device_type in DEVICE_TYPES}

    assert len(devices(seeds)) == 15
    assert not devices(seeds) & devices(foreign)
    # The tool checks against the same set on every write.
    assert set(tool.reference_seeds()) == foreign
    assert tool.collisions(plan, []) == []


# ---------------------------------------------------------------------------
# write: the refusals write nothing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("master_seed", ["4.2", "-1", "+7", "1_000", "42 ", "", "0x2a", "twenty"])
def test_refuses_a_master_seed_that_is_not_a_whole_number(tmp_path, master_seed):
    refused, out = _write(tmp_path, master_seed=master_seed)
    _refused(refused, f"the master seed {master_seed!r} is not a whole number")
    assert not (tmp_path / "g4-pilot").exists()


def test_refuses_an_existing_output_and_leaves_it_as_it_was(tmp_path):
    out = tmp_path / "plan.json"
    out.write_text("not a plan\n", encoding="utf-8")
    refused, _ = _write(tmp_path, out=out)
    _refused(refused, f"{out} exists: the plan is write-once and is not replaced")
    assert out.read_text(encoding="utf-8") == "not a plan\n"


def test_refuses_an_against_plan_that_holds_a_pilot_run_id_and_never_edits_it(tmp_path):
    taken = dict(plan_gen.load_campaign_plan(_g3_plan(tmp_path / "ref"))["runs"][-1], run_id=IDS[1], seed=12345)
    g3 = _g3_plan(tmp_path, taken)
    before = g3.read_bytes()
    refused, out = _write(tmp_path, "--against", str(g3))
    _refused(refused, f"the run id {IDS[1]!r} is held by {g3}")
    assert not out.exists() and g3.read_bytes() == before

    # G3's plan as it stands holds none of them: the plan is written and
    # G3's plan is exactly what it was.
    clean = _g3_plan(tmp_path / "clean")
    kept = clean.read_bytes()
    written, out = _write(tmp_path, "--against", str(clean))
    assert written.returncode == 0, written.stderr
    assert out.read_bytes() == COMMITTED.read_bytes()
    assert clean.read_bytes() == kept


def test_refuses_an_against_plan_whose_entry_carries_a_pilot_seed(tmp_path):
    seed = WORKING_SEEDS[IDS[2]]
    spent = dict(plan_gen.load_campaign_plan(_g3_plan(tmp_path / "ref"))["runs"][-1],
                 run_id="controller_restart-r99", seed=seed)
    g3 = _g3_plan(tmp_path, spent)
    refused, out = _write(tmp_path, "--against", str(g3))
    _refused(refused, f"the seed {seed} of {IDS[2]!r} is spent by {g3} (controller_restart-r99)")
    assert not out.exists()


def test_refuses_an_against_seed_a_pilot_entry_carries_or_one_that_is_not_a_whole_number(tmp_path):
    seed = WORKING_SEEDS[IDS[4]]
    refused, out = _write(tmp_path, "--against-seed", "9", "--against-seed", str(seed))
    _refused(refused, f"the seed {seed} of {IDS[4]!r} is spent by --against-seed {seed}")
    assert not out.exists()
    refused, out = _write(tmp_path, "--against-seed", "seven")
    _refused(refused, "the against seed 'seven' is not a whole number")
    assert not out.exists()


def test_the_built_in_references_and_a_device_collision_refuse_too(tmp_path, tool, monkeypatch, capsys):
    # The references are built in: a pilot seed among them is refused
    # without any --against.
    out = tmp_path / "plan.json"
    seed = WORKING_SEEDS[IDS[0]]
    monkeypatch.setattr(tool, "reference_seeds", lambda: {seed: "a reference"})
    assert tool.main(["write", "--master-seed", str(WORKING_SEED), "--out", str(out)]) == 2
    assert f"the seed {seed} of {IDS[0]!r} is spent by a reference" in capsys.readouterr().err
    assert not out.exists()
    monkeypatch.undo()

    # Two different seeds that gave one device would be refused as well.
    real = tool.device_uuid_for
    monkeypatch.setattr(tool, "device_uuid_for", lambda s, t, index=0: (
        "00000000-0000-4000-8000-000000000000" if (s, t) in ((seed, "smart_ring"), (99, "smart_ring"))
        else real(s, t, index)))
    assert tool.main(["write", "--master-seed", str(WORKING_SEED), "--out", str(out),
                      "--against-seed", "99"]) == 2
    err = capsys.readouterr().err
    assert (f"the device 00000000-0000-4000-8000-000000000000 (smart_ring) of {IDS[0]!r} "
            "is a device of --against-seed 99") in err
    assert not out.exists()


def test_refuses_an_against_plan_it_cannot_read(tmp_path):
    missing = tmp_path / "pilot" / "campaign_plan.json"
    refused, out = _write(tmp_path, "--against", str(missing))
    _refused(refused, f"the against plan {missing} could not be read")
    assert not out.exists()

    not_a_plan = tmp_path / "pilot" / "not-a-plan.json"
    not_a_plan.parent.mkdir(parents=True, exist_ok=True)
    not_a_plan.write_text('{"plan_version": "1.0"}\n', encoding="utf-8")
    refused, out = _write(tmp_path, "--against", str(not_a_plan))
    _refused(refused, "no 'runs' list of entries")
    assert not out.exists()

    broken = tmp_path / "pilot" / "broken.json"
    broken.write_text("{", encoding="utf-8")
    refused, out = _write(tmp_path, "--against", str(broken))
    _refused(refused, f"the against plan {broken} could not be read")
    assert not out.exists()


def test_refuses_an_output_under_g3s_tree_as_given_or_by_default(tmp_path):
    forbid = tmp_path / "pilot"
    out = forbid / "g4" / "plan.json"
    refused, _ = _write(tmp_path, "--forbid-under", str(forbid), out=out)
    _refused(refused, f"the output {out} lies under {forbid}")
    assert not out.parent.exists()

    # The default is ~/egw-tcg/pilot, G3's tree.
    home = tmp_path / "home"
    out = home / "egw-tcg" / "pilot" / "g4_pilot_plan.json"
    refused, _ = _write(tmp_path, out=out, home=home)
    _refused(refused, f"the output {out} lies under {home / 'egw-tcg' / 'pilot'}")
    assert not out.parent.exists()


def _limit_file_size() -> None:
    """A stand-in for a full disk in the child: no file may grow past 100
    bytes, and a write past it fails (EFBIG) instead of killing the process."""
    import resource
    import signal

    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    resource.setrlimit(resource.RLIMIT_FSIZE, (100, 100))


def test_a_write_that_fails_part_way_leaves_nothing_and_a_retry_writes_the_plan(tmp_path):
    pytest.importorskip("resource")
    out = tmp_path / "g4-pilot" / "plan" / "g4_pilot_plan.sealed.json"
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR), "PYTHONDONTWRITEBYTECODE": "1"}
    failed = subprocess.run(
        [sys.executable, str(TOOL), "write", "--master-seed", str(WORKING_SEED), "--out", str(out)],
        env=env, capture_output=True, text=True, preexec_fn=_limit_file_size)
    _refused(failed, f"{out} was not written")
    # No part of the plan is left under its name or under another, and the
    # directories this write created are gone: "nothing was written" holds.
    assert not out.exists()
    assert list(tmp_path.iterdir()) == []

    # So the retry is not refused as an existing output, and it writes the plan.
    written, _ = _write(tmp_path, out=out)
    assert written.returncode == 0, written.stderr
    assert out.read_bytes() == COMMITTED.read_bytes()
    assert [p.name for p in out.parent.iterdir()] == [out.name]


def test_write_plan_never_replaces_an_output_that_appeared_meanwhile(tmp_path, tool, monkeypatch):
    out = tmp_path / "plan" / "g4_pilot_plan.sealed.json"
    real = tool.plan_to_json

    def and_meanwhile(plan):
        # Another writer creates the output after the tool's own check.
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("another writer's plan\n", encoding="utf-8")
        return real(plan)

    monkeypatch.setattr(tool, "plan_to_json", and_meanwhile)
    with pytest.raises(tool.PlanNotWritten) as refused:
        tool.write_plan(tool.build_pilot_plan(WORKING_SEED), out)
    assert refused.value.left == []
    assert out.read_text(encoding="utf-8") == "another writer's plan\n"
    assert [p.name for p in out.parent.iterdir()] == [out.name]


def test_a_usage_error_writes_nothing(tmp_path):
    out = tmp_path / "plan.json"
    for argv in (
        [],
        ["write"],
        ["write", "--master-seed", "42"],
        ["write", "--out", str(out)],
        ["check", "--plan", str(out)],
        ["append-repeat", "--master-seed", "42", "--out", str(out)],
    ):
        result = _run_tool(*argv)
        assert result.returncode == 2, argv
        assert "usage: g4_pilot_plan.py" in result.stderr
    assert not out.exists()


# ---------------------------------------------------------------------------
# the harness runs each entry as planned, through a working copy
# ---------------------------------------------------------------------------


def test_the_harness_runs_each_entry_as_planned_through_a_working_copy(tmp_path, fast_run, tool):
    written, sealed = _write(tmp_path)
    assert written.returncode == 0, written.stderr
    sealed_bytes = sealed.read_bytes()
    working = sealed.with_name("g4_pilot_plan.json")
    working.write_bytes(sealed_bytes)
    base = tmp_path / "g4-pilot" / "results"
    digest = hashlib.sha256(sealed_bytes).hexdigest()

    for order, rid in enumerate(IDS, start=1):
        ready = _check(working, sealed, base, rid, "--sealed-sha256", digest, forbid_under=tmp_path / "pilot")
        assert ready.returncode == 0, ready.stderr
        assert ready.stdout.startswith(f"ready: {rid} (order {order} of 5, stage ")

        cid, scenario, rate, duration, warmup, cooldown, stage = FIGURES[rid]
        seed = plan_gen.derive_run_seed(WORKING_SEED, rid)
        start = len(fast_run.calls)
        rc = run_mod.execute_run(
            working,
            rid,
            base_dir=base,
            no_tls=True,
            post_run_wait_s=0.0,
            # The sweep's 120 s cool-down would be slept after each sweep run;
            # skipping it keeps this case instantaneous (it is recorded).
            skip_cooldown=cooldown > 0,
            event_log_dir=_local_events(tmp_path, rid),
            sut_env_from=_sut_env_file(tmp_path),
            resources_from=_resources_file(tmp_path),
            expect_services=FIXTURE_SERVICES,
            allow_missing_controller_marker=True,
        )
        calls = fast_run.calls[start:]

        # The simulator is given the entry's figures (CONTRACTS 7 argv); the
        # warm-up, only for stage 2, runs first under '<id>.warmup' with the
        # same seed.
        def given(argv):
            return {flag: argv[argv.index(flag) + 1]
                    for flag in ("--scenario", "--seed", "--duration", "--rate", "--run-id")}

        assert given(calls[-1]) == {"--scenario": scenario, "--seed": str(seed), "--duration": str(duration),
                                    "--rate": str(rate), "--run-id": rid}
        if warmup:
            assert len(calls) == 2
            assert given(calls[0]) == {"--scenario": scenario, "--seed": str(seed), "--duration": str(warmup),
                                       "--rate": str(rate), "--run-id": f"{rid}.warmup"}
        else:
            assert len(calls) == 1

        # The manifest records the entry as read, with its pilot block.
        manifest = _manifest(base, rid)
        assert (manifest["condition_id"], manifest["scenario"], manifest["runner"]) == (cid, scenario, "simulator")
        assert (manifest["duration_s"], manifest["warmup_s"], manifest["cooldown_s"]) == (duration, warmup, cooldown)
        assert (manifest["rate_msg_s"], manifest["seed"], manifest["repetition"]) == (rate, seed, 1)
        assert manifest["plan_master_seed"] == WORKING_SEED
        assert manifest["config"]["plan_entry"]["pilot"] == _plan_entry(sealed, rid)["pilot"]
        # The pilot's own departures engage no harness rule: stage 1's
        # warm-up 0 is no 'skip_warmup' deviation. The deviations recorded
        # are the ones this case makes (the 0 s confirmation wait, no
        # controller marker, the skipped sweep cool-down).
        kinds = {d["kind"] for d in manifest["deviations"]}
        assert kinds == {"confirmation_window_override", "confirmation_marker_unavailable"} | (
            {"cooldown_skipped"} if cooldown else set())
        if cid in ("load_sweep", "soak"):
            # The unchanged rule: controller metrics are mandatory evidence
            # there, and this case has no controller to sample.
            assert rc == 1
            assert "controller_metrics.csv" in manifest["missing_mandatory_artifacts"]

        # The harness rewrote only the status fields of this entry.
        entry = _plan_entry(working, rid)
        assert entry["status"] in ("completed", "failed")
        assert entry["result_dir"] == str(base / "raw" / rid)
        sealed_entry = _plan_entry(sealed, rid)
        assert {k: v for k, v in entry.items() if k not in HARNESS_WRITTEN} == {
            k: v for k, v in sealed_entry.items() if k != "status"}

        # The run just made can never be made again.
        again = _check(working, sealed, base, rid, forbid_under=tmp_path / "pilot")
        assert again.returncode == 2
        assert f"{rid} has status {entry['status']!r} in the working plan, not 'planned'" in again.stderr

    assert sealed.read_bytes() == sealed_bytes == COMMITTED.read_bytes()


# ---------------------------------------------------------------------------
# check: the refusals
# ---------------------------------------------------------------------------


def test_check_passes_entry_1_on_a_fresh_pair_and_entry_2_once_entry_1_has_run(tmp_path, tool):
    working, sealed, base = _pair(tmp_path, tool)
    forbid = tmp_path / "pilot"
    ready = _check(working, sealed, base, IDS[0], forbid_under=forbid)
    assert ready.returncode == 0, ready.stderr
    assert ready.stdout.strip() == (
        f"ready: {IDS[0]} (order 1 of 5, stage 1): {working} holds every frozen field of {sealed}, "
        f"the entries before it have run and {base / 'raw' / IDS[0]} is absent; nothing was written")

    # Entry 2 waits for entry 1: the pilot runs in order.
    refused = _check(working, sealed, base, IDS[1], forbid_under=forbid)
    _refused(refused, f"entry 1 ({IDS[0]}) comes before {IDS[1]} and is still 'planned': the pilot runs in order")

    # The harness's own status write (update_plan_status) changes only the
    # status fields, so entry 2 is then ready and entry 3 still waits.
    before = working.read_bytes()
    assert run_mod.update_plan_status(working, IDS[0], "failed", result_dir=str(base / "raw" / IDS[0]),
                                      finished_utc="2026-10-07T12:00:00.000Z", validity="invalid")
    assert working.read_bytes() != before
    assert _check(working, sealed, base, IDS[1], forbid_under=forbid).returncode == 0
    _refused(_check(working, sealed, base, IDS[2], forbid_under=forbid),
             f"entry 2 ({IDS[1]}) comes before {IDS[2]} and is still 'planned'")
    _refused(_check(working, sealed, base, IDS[0], forbid_under=forbid),
             f"{IDS[0]} has status 'failed' in the working plan, not 'planned'")
    _refused(_check(working, sealed, base, "nominal-r01", forbid_under=forbid),
             "the run id 'nominal-r01' is not in the working plan")


def test_check_refuses_an_existing_run_directory(tmp_path, tool):
    working, sealed, base = _pair(tmp_path, tool)
    (base / "raw" / IDS[0]).mkdir(parents=True)
    _refused(_check(working, sealed, base, IDS[0], forbid_under=tmp_path / "pilot"),
             f"{base / 'raw' / IDS[0]} exists: a run directory is never reused")


@pytest.mark.parametrize("change", ["duration", "seed", "pilot-block", "top-level", "extra-field"])
def test_check_refuses_a_working_plan_that_differs_from_the_sealed_one(tmp_path, tool, change):
    working, sealed, base = _pair(tmp_path, tool)
    plan = plan_gen.load_campaign_plan(working)
    if change == "duration":
        plan["runs"][1]["duration_s"] = 601
        phrase = f"entry 2 ({IDS[1]}) of the working plan differs from the sealed plan in duration_s"
    elif change == "seed":
        plan["runs"][4]["seed"] = 42
        phrase = f"entry 5 ({IDS[4]}) of the working plan differs from the sealed plan in seed"
    elif change == "pilot-block":
        plan["runs"][0]["pilot"]["deviations"] = []
        phrase = f"entry 1 ({IDS[0]}) of the working plan differs from the sealed plan in pilot"
    elif change == "top-level":
        plan["master_seed"] = 42
        phrase = "the working plan's master_seed differs from the sealed plan's"
    else:
        plan["runs"][0]["note"] = "edited by hand"
        phrase = f"entry 1 ({IDS[0]}) of the working plan carries a field the harness never writes: note"
    _canonical(plan, working)
    kept = working.read_bytes()
    _refused(_check(working, sealed, base, IDS[0], forbid_under=tmp_path / "pilot"), phrase)
    assert working.read_bytes() == kept


def test_check_refuses_a_plan_that_is_not_canonical_and_a_sha256_that_does_not_match(tmp_path, tool):
    working, sealed, base = _pair(tmp_path, tool)
    forbid = tmp_path / "pilot"
    working.write_text(json.dumps(plan_gen.load_campaign_plan(sealed)), encoding="utf-8", newline="\n")
    _refused(_check(working, sealed, base, IDS[0], forbid_under=forbid),
             f"{working} is not the canonical serialisation the harness writes (plan_to_json)")

    working.write_bytes(sealed.read_bytes())
    actual = hashlib.sha256(sealed.read_bytes()).hexdigest()
    _refused(_check(working, sealed, base, IDS[0], "--sealed-sha256", "0" * 64, forbid_under=forbid),
             f"the sealed plan's sha256 is {actual}, not {'0' * 64}")
    assert _check(working, sealed, base, IDS[0], "--sealed-sha256", actual, forbid_under=forbid).returncode == 0


def test_check_refuses_a_sealed_copy_that_was_run_against_or_is_the_working_copy(tmp_path, tool):
    working, sealed, base = _pair(tmp_path, tool)
    forbid = tmp_path / "pilot"
    _refused(_check(sealed, sealed, base, IDS[0], forbid_under=forbid),
             "the working plan and the sealed plan are the same file")

    assert run_mod.update_plan_status(sealed, IDS[0], "running")
    working.write_bytes(sealed.read_bytes())
    _refused(_check(working, sealed, base, IDS[0], forbid_under=forbid),
             f"entry 1 ({IDS[0]}) of the sealed plan has status 'running': the sealed copy is never given to run")


def test_check_refuses_a_sealed_plan_that_is_not_the_tools_plan(tmp_path, tool):
    working, sealed, base = _pair(tmp_path, tool)
    plan = plan_gen.load_campaign_plan(sealed)
    plan["runs"][3]["rate_msg_s"] = 100.0
    _canonical(plan, sealed)
    working.write_bytes(sealed.read_bytes())
    refused = _check(working, sealed, base, IDS[0], forbid_under=tmp_path / "pilot")
    _refused(refused, f"the sealed plan: entry 4 ({IDS[3]}): rate_msg_s is 100.0, the pilot's is 50.0")


@pytest.mark.parametrize("change", ["label", "purpose", "source", "basis", "note", "extra-key"])
def test_check_refuses_a_sealed_plan_whose_free_text_labels_or_sources_were_changed(tmp_path, tool, change):
    # The sealed copy must be the tool's plan for its own master seed byte
    # for byte, so what the figure checks do not judge is refused as well:
    # the free text, the top-level label, the sources and a key added to
    # the pilot block (an execution mode the plan must never supply).
    working, sealed, base = _pair(tmp_path, tool)
    plan = plan_gen.load_campaign_plan(sealed)
    pilot = plan["pilot"]
    if change == "label":
        pilot["label"] = "CITABLE"
    elif change == "purpose":
        pilot["purpose"] += " Edited by hand."
    elif change == "source":
        pilot["sources"]["runs"][IDS[0]]["seed"] = "made up"
    elif change == "basis":
        plan["runs"][0]["pilot"]["deviations"][0]["basis"] = "made up basis"
    elif change == "note":
        pilot["deviations_from_protocol"][4]["note"] = "edited by hand"
    else:
        pilot["execution_mode"] = "native-kvm"
    _canonical(plan, sealed)
    working.write_bytes(sealed.read_bytes())
    refused = _check(working, sealed, base, IDS[0], forbid_under=tmp_path / "pilot")
    _refused(refused, f"the sealed plan is not, byte for byte, this tool's plan for its master seed {WORKING_SEED}")


def test_check_accepts_the_tools_plan_for_the_master_seed_the_sealed_copy_names(tmp_path, tool):
    # The comparison is with the plan of the sealed copy's own master seed;
    # which sealed copy is meant is what --sealed-sha256 pins.
    sealed = _canonical(tool.build_pilot_plan(TEST_SEED), tmp_path / "g4-pilot" / "plan" / "sealed.json")
    working = sealed.with_name("working.json")
    working.write_bytes(sealed.read_bytes())
    ready = _check(working, sealed, tmp_path / "g4-pilot" / "results", IDS[0], forbid_under=tmp_path / "pilot")
    assert ready.returncode == 0, ready.stderr


def test_check_refuses_a_plan_or_base_under_g3s_tree_as_given_through_dotdot_or_a_link(tmp_path, tool):
    working, sealed, base = _pair(tmp_path, tool)
    forbid = tmp_path / "pilot"
    forbid.mkdir()
    under = forbid / "results"
    _refused(_check(working, sealed, under, IDS[0], forbid_under=forbid),
             f"the results base {under} lies under {forbid}")
    dotdot = tmp_path / "g4-pilot" / ".." / "pilot" / "results"
    _refused(_check(working, sealed, dotdot, IDS[0], forbid_under=forbid),
             f"the results base {dotdot} lies under {forbid}")
    inside = forbid / "plan.json"
    inside.write_bytes(working.read_bytes())
    _refused(_check(inside, sealed, base, IDS[0], forbid_under=forbid),
             f"the working plan {inside} lies under {forbid}")
    link = tmp_path / "linked"
    try:
        link.symlink_to(forbid, target_is_directory=True)
    except OSError:
        pytest.skip("no symbolic links here")
    _refused(_check(working, sealed, link / "results", IDS[0], forbid_under=forbid),
             f"the results base {link / 'results'} lies under {forbid}")
    _refused(_check(working, link / "plan.json", base, IDS[0], forbid_under=forbid),
             f"the sealed plan {link / 'plan.json'} lies under {forbid}")

    # The default is ~/egw-tcg/pilot, G3's tree.
    home = tmp_path / "home"
    g3_results = home / "egw-tcg" / "pilot" / "results"
    _refused(_check(working, sealed, g3_results, IDS[0], forbid_under=None, home=home),
             f"the results base {g3_results} lies under {home / 'egw-tcg' / 'pilot'}")


@pytest.mark.parametrize("field, value, phrase", [
    ("rate_msg_s", None, "rate_msg_s"),
    ("rate_msg_s", 0, "rate_msg_s"),
    ("duration_s", "120", "duration_s"),
    ("warmup_s", -1, "warmup_s"),
    ("cooldown_s", 1.5, "cooldown_s"),
    ("seed", 2**32, "seed"),
    ("seed", True, "seed"),
    ("runner", "external", "runner"),
    ("scenario", "smoke", "scenario"),
    ("condition_id", "qemu_boots", "condition_id"),
    ("repetition", 0, "repetition"),
    ("run_id", "g4pilot-s1-nominal-0120s-11p2mps-a01" + "x" * 22, "run_id"),
])
def test_an_entry_the_harness_could_not_run_as_planned_is_found_before_anything_starts(tool, field, value, phrase):
    entry = tool.build_pilot_plan(WORKING_SEED)["runs"][0]
    assert tool.entry_problems(entry) == []
    entry[field] = value
    problems = tool.entry_problems(entry)
    assert problems and any(phrase in p for p in problems), problems


# ---------------------------------------------------------------------------
# analyze reads the five-entry plan as the pilot README says
# ---------------------------------------------------------------------------


def _pilot_rows(plan: dict) -> list[dict]:
    """Valid per-run rows whose identities match the plan's entries."""
    rows = []
    for entry in plan["runs"]:
        rows.append({
            "condition_id": entry["condition_id"], "validity": "valid", "excluded": False,
            "run_id": entry["run_id"], "repetition": entry["repetition"], "seed": entry["seed"],
            "rate_msg_s": entry["rate_msg_s"], "duration_s": entry["duration_s"],
            "lost": 0, "delivery_rate": 1.0, "latency_ms_p95": 100.0 + entry["duration_s"],
            "measured_window_s": float(entry["duration_s"]),
        })
    return rows


def test_completeness_fails_by_construction_except_the_soaks_whose_window_fails_instead(tool):
    plan = tool.build_pilot_plan(WORKING_SEED)
    lists = {"smoke_sequence": (0, 10), "nominal": (2, 10), "load_sweep": (2, 40),
             "invalid_payload": (0, 3), "dropout_reconnect": (0, 3), "controller_restart": (0, 3)}
    for rows in ([], _pilot_rows(plan)):
        result = analyze.evaluate_acceptance(rows, plan)
        complete = {r["condition_id"]: r for r in result if r["criterion"] == "runs_complete"}
        for cid, (listed, planned) in lists.items():
            assert complete[cid]["passed"] is False, cid
            assert (f"the campaign plan lists {listed} run(s) for this condition, "
                    f"the frozen protocol plans {planned}") in complete[cid]["observed"]
        # Every substantive row of those six is gated False.
        for row in result:
            if row["condition_id"] in lists and row["passed"] is not None:
                assert row["passed"] is False, row

    # The soak is the exception: one listed, one planned, so with its run
    # present its completeness passes and its rows are evaluated; the 24 h
    # window fails by construction (and none of it is C13 evidence).
    result = analyze.evaluate_acceptance(_pilot_rows(plan), plan)
    soak = {r["criterion"]: r for r in result if r["condition_id"] == "soak"}
    assert soak["runs_complete"]["passed"] is True
    assert "1/1 planned run identities matched" in soak["runs_complete"]["observed"]
    assert soak["measured_window_ge_24h"]["passed"] is False
    assert "3600.00 s" in soak["measured_window_ge_24h"]["observed"]
    without = analyze.evaluate_acceptance([], plan)
    assert next(r for r in without if r["condition_id"] == "soak"
                and r["criterion"] == "runs_complete")["passed"] is False


def test_saturation_is_insufficient_evidence_at_every_load_and_the_nominal_summary_pools(tool):
    rows = _pilot_rows(tool.build_pilot_plan(WORKING_SEED))
    saturation = analyze.detect_saturation(rows)
    assert [load["rate_msg_s"] for load in saturation["loads"]] == [10.0, 50.0, 100.0, 250.0]
    assert [load["n_runs"] for load in saturation["loads"]] == [1, 1, 0, 0]
    for load in saturation["loads"]:
        assert load["verdict"] == "insufficient-evidence"
        assert f"{load['n_runs']}/10 valid runs" in load["insufficient_evidence_detail"][0]
    assert saturation["first_saturated_load_msg_s"] is None

    # The summary groups by (condition, rate): the 120 s and the 600 s
    # nominal runs pool into one row, so pilot results are read per run.
    summary = analyze.summarize_by_condition(rows)
    nominal = [s for s in summary if s["condition_id"] == "nominal" and s["metric"] == "latency_ms_p95"]
    assert len(nominal) == 1 and nominal[0]["n_runs"] == 2
    assert (nominal[0]["min"], nominal[0]["max"]) == (220.0, 700.0)


def test_analyze_of_the_pilot_base_reads_the_named_plan_and_leaves_g3s_tree_alone(
    tmp_path, tool, monkeypatch, capsys
):
    g3_plan = _g3_plan(tmp_path)
    g3_base = tmp_path / "pilot" / "results"
    (g3_base / "raw").mkdir(parents=True)
    sentinels = {g3_base / "processed" / "acceptance_by_condition.csv": b"G3's table, never regenerated\n",
                 g3_base / "figures" / "latency.png": b"G3's figure\n"}
    for path, body in sentinels.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    working, sealed, base = _pair(tmp_path, tool)
    (base / "raw").mkdir(parents=True)
    kept = {path: path.read_bytes() for path in (g3_plan, sealed, working)}

    # The environment fallback points at G3's plan; the explicit --plan wins.
    monkeypatch.setenv(CAMPAIGN_PLAN_ENV_VAR, str(g3_plan))
    assert cli.main(["analyze", "--base-dir", str(base), "--plan", str(sealed)]) == 0
    captured = capsys.readouterr()
    assert "could not be read" not in captured.err
    assert "BY COUNT ONLY" not in captured.out
    assert "the campaign plan lists no controller_restart run" in captured.out

    rows = list(csv.DictReader(
        (base / "processed" / "acceptance_by_condition.csv").read_text("utf-8").splitlines()))
    nominal = next(r for r in rows if r["condition_id"] == "nominal" and r["criterion"] == "runs_complete")
    assert f"missing {IDS[0]}, {IDS[1]}" in nominal["observed"]
    assert "the campaign plan lists 2 run(s) for this condition, the frozen protocol plans 10" in nominal["observed"]
    restart = next(r for r in rows if r["condition_id"] == "controller_restart" and r["criterion"] == "runs_complete")
    assert "the campaign plan lists 0 run(s)" in restart["observed"]

    for path, body in sentinels.items():
        assert path.read_bytes() == body
    for path, body in kept.items():
        assert path.read_bytes() == body
