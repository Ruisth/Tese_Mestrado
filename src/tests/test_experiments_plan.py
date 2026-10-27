"""Tests for egw_experiments.protocol and plan_gen (plan 7.1 completed per
audit 2026-08-08 section 9.5; CONTRACTS 2).

Stdlib-only fixtures; no docker, no network.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from egw_experiments import plan_gen, protocol

# Audit 9.5: the plan must enumerate EVERY condition claims C10/C11/C12/C14
# depend on, not only the original 76 runs.
#   qemu_boots 5 + cold_start 10 + twin_creation 10 + smoke_sequence 10
#   + nominal 10 + load_sweep 4*10 + invalid_payload 3 + dropout_reconnect 3
#   + controller_restart 3 + soak 1 = 95
EXPECTED_TOTAL_RUNS = 5 + 10 + 10 + 10 + 10 + 4 * 10 + 3 + 3 + 3 + 1  # 95

EXPECTED_CONDITION_IDS = {
    "qemu_boots",
    "cold_start",
    "twin_creation",
    "smoke_sequence",
    "nominal",
    "load_sweep",
    "invalid_payload",
    "dropout_reconnect",
    "controller_restart",
    "soak",
}


def _load_sweep_order(plan: dict) -> list[tuple[float, int]]:
    return [
        (run["rate_msg_s"], run["repetition"])
        for run in plan["runs"]
        if run["condition_id"] == "load_sweep"
    ]


def test_protocol_conditions_match_plan_7_1() -> None:
    by_id = protocol.CONDITIONS_BY_ID
    assert set(by_id) == EXPECTED_CONDITION_IDS
    assert by_id["qemu_boots"].repetitions == 5
    assert by_id["qemu_boots"].performance_claims_allowed is False
    assert by_id["cold_start"].repetitions == 10
    assert by_id["twin_creation"].repetitions == 10
    nominal = by_id["nominal"]
    assert (nominal.repetitions, nominal.duration_s, nominal.warmup_s) == (10, 600, 120)
    sweep = by_id["load_sweep"]
    assert sweep.rates_msg_s == (10.0, 50.0, 100.0, 250.0)
    assert (sweep.repetitions, sweep.duration_s, sweep.cooldown_s) == (10, 300, 120)
    soak = by_id["soak"]
    assert (soak.repetitions, soak.duration_s) == (1, 24 * 3600)


def test_missing_conditions_added_per_audit_9_5() -> None:
    """smoke_sequence/invalid_payload/dropout_reconnect/controller_restart
    exist with the audit-mandated shapes so C14/C11/C10/C12 have a full
    path through the campaign plan."""
    by_id = protocol.CONDITIONS_BY_ID

    smoke = by_id["smoke_sequence"]
    assert (smoke.runner, smoke.scenario, smoke.repetitions) == (
        "simulator",
        "smoke",
        10,
    )

    invalid = by_id["invalid_payload"]
    assert (invalid.runner, invalid.scenario) == ("simulator", "invalid-payload")
    assert (invalid.repetitions, invalid.duration_s) == (3, 300)
    assert invalid.rate_msg_s == protocol.NOMINAL_RATE_MSG_S

    dropout = by_id["dropout_reconnect"]
    assert (dropout.runner, dropout.scenario) == ("simulator", "dropout-reconnect")
    assert (dropout.repetitions, dropout.duration_s) == (3, 600)

    restart = by_id["controller_restart"]
    assert (restart.runner, restart.scenario) == ("simulator", "nominal")
    assert (restart.repetitions, restart.duration_s) == (3, 600)
    assert restart.rate_msg_s == protocol.NOMINAL_RATE_MSG_S
    assert "--restart-cmd" in restart.notes


def test_timed_conditions_are_exactly_the_simulator_driven_ones() -> None:
    # Audit 9.1/9.2: every simulator-driven run is timed (requires SUT env
    # and SUT resources); external conditions are operator-measured.
    simulator_ids = {c.id for c in protocol.CONDITIONS if c.runner == "simulator"}
    assert protocol.TIMED_CONDITION_IDS == simulator_ids
    assert simulator_ids == {
        "smoke_sequence",
        "nominal",
        "load_sweep",
        "invalid_payload",
        "dropout_reconnect",
        "controller_restart",
        "soak",
    }


def test_condition_claim_map_covers_audit_claims() -> None:
    claims = protocol.CONDITION_CLAIMS
    assert set(claims) == EXPECTED_CONDITION_IDS
    assert claims["smoke_sequence"] == ("C14",)
    assert claims["invalid_payload"] == ("C11",)
    assert claims["dropout_reconnect"] == ("C10",)
    assert claims["controller_restart"] == ("C12",)
    assert claims["cold_start"] == ("C04",)
    assert claims["soak"] == ("C13",)


def test_plan_is_deterministic_for_same_master_seed() -> None:
    plan_a = plan_gen.generate_campaign_plan(42)
    plan_b = plan_gen.generate_campaign_plan(42)
    assert plan_gen.plan_to_json(plan_a) == plan_gen.plan_to_json(plan_b)


def test_load_sweep_order_is_randomized_and_stable_per_seed() -> None:
    order_42a = _load_sweep_order(plan_gen.generate_campaign_plan(42))
    order_42b = _load_sweep_order(plan_gen.generate_campaign_plan(42))
    order_7 = _load_sweep_order(plan_gen.generate_campaign_plan(7))
    assert order_42a == order_42b
    # Different master seeds shuffle the 40-entry block differently.
    assert order_42a != order_7
    # The block was actually shuffled, not left in enumeration order.
    enumeration_order = [
        (rate, rep) for rate in (10.0, 50.0, 100.0, 250.0) for rep in range(1, 11)
    ]
    assert sorted(order_42a) == sorted(enumeration_order)
    assert order_42a != enumeration_order


def test_plan_enumerates_all_runs_with_unique_ids_and_orders() -> None:
    plan = plan_gen.generate_campaign_plan(123)
    runs = plan["runs"]
    assert len(runs) == EXPECTED_TOTAL_RUNS
    run_ids = [run["run_id"] for run in runs]
    assert len(set(run_ids)) == len(run_ids)
    for run_id in run_ids:
        assert plan_gen.RUN_ID_RE.match(run_id), run_id
    assert [run["order"] for run in runs] == list(range(1, EXPECTED_TOTAL_RUNS + 1))
    assert all(run["status"] == "planned" for run in runs)
    # Each sweep rate appears exactly 10 times.
    sweep = [run for run in runs if run["condition_id"] == "load_sweep"]
    for rate in (10.0, 50.0, 100.0, 250.0):
        assert sum(1 for run in sweep if run["rate_msg_s"] == rate) == 10
    # The audit 9.5 conditions are enumerated with the expected run counts.
    by_condition: dict[str, int] = {}
    for run in runs:
        by_condition[run["condition_id"]] = by_condition.get(run["condition_id"], 0) + 1
    assert by_condition["smoke_sequence"] == 10
    assert by_condition["invalid_payload"] == 3
    assert by_condition["dropout_reconnect"] == 3
    assert by_condition["controller_restart"] == 3
    # run_id naming: smoke_sequence-r01 .. smoke_sequence-r10 etc.
    assert "smoke_sequence-r01" in set(run_ids)
    assert "invalid_payload-r03" in set(run_ids)
    assert "dropout_reconnect-r03" in set(run_ids)
    assert "controller_restart-r03" in set(run_ids)
    # Every run carries its runner so the harness can route it.
    for run in runs:
        assert run["runner"] in ("simulator", "external")


def test_per_run_seeds_are_deterministic_and_distinct() -> None:
    seed_a = plan_gen.derive_run_seed(42, "nominal-r01")
    seed_b = plan_gen.derive_run_seed(42, "nominal-r01")
    seed_c = plan_gen.derive_run_seed(42, "nominal-r02")
    seed_d = plan_gen.derive_run_seed(43, "nominal-r01")
    assert seed_a == seed_b
    assert 0 <= seed_a < 2**32
    assert seed_a != seed_c
    assert seed_a != seed_d
    plan = plan_gen.generate_campaign_plan(42)
    for run in plan["runs"]:
        assert run["seed"] == plan_gen.derive_run_seed(42, run["run_id"])


def test_plan_write_and_load_round_trip(tmp_path) -> None:
    plan = plan_gen.generate_campaign_plan(42)
    path = tmp_path / "campaign_plan.json"
    plan_gen.write_campaign_plan(plan, path)
    loaded = plan_gen.load_campaign_plan(path)
    assert loaded == json.loads(plan_gen.plan_to_json(plan))
    assert loaded["master_seed"] == 42
    assert loaded["protocol_version"] == protocol.PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# The supplementary entry of G3's test 6 (offline block authorised 2026-10-05)
# ---------------------------------------------------------------------------

#: The campaign plan of master seed 42 as generated before the supplement
#: existed (the pilot plan on the host was generated with seed 42): adding a
#: supplement must not change one byte of what ``generate_campaign_plan``
#: writes.
PLAN_42_SHA256 = "5679d43f549278279689c92ea0806393a6ba23be257e13c340c98b02c85e5cac"

#: The three planned controller_restart entries of master seed 42, as the
#: pilot plan held them before any run (copies of 2026-10-02/03 in
#: output_test): all three are used on the guest (r01 2026-09-18, r02
#: 2026-09-19, r03 2026-10-03, each invalid) and stay exactly as they are.
FROZEN_RESTART_ENTRIES_42 = [
    {"condition_id": "controller_restart", "cooldown_s": 0, "duration_s": 600, "order": 92 + i,
     "rate_msg_s": 11.2, "repetition": i + 1, "run_id": f"controller_restart-r0{i + 1}",
     "runner": "simulator", "scenario": "nominal", "seed": seed, "status": "planned", "warmup_s": 0}
    for i, seed in enumerate((1604901681, 588895280, 2189910495))
]

#: Run ids already used on the guest under the pilot plan (its entries with a
#: status other than 'planned' in the copy of 2026-10-03), plus the finite
#: proof's diagnostic ids, which ran from plans of their own.
USED_RUN_IDS = {
    "smoke_sequence-r01", "smoke_sequence-r02", "nominal-r01", "nominal-r02",
    "controller_restart-r01", "controller_restart-r02", "controller_restart-r03",
    "proof-adr0011-r01", "proof-adr0011-r02", "proof-adr0011-r03",
}

#: How the canonical serialisation ends: ``runs`` is the last key.
PLAN_TAIL = "\n  ]\n}\n"


def _pilot_plan_text_as_on_2026_10_03() -> str:
    """The pilot plan as the host held it after test 6's r03: master seed 42,
    the three controller_restart entries carrying the statuses the harness
    wrote (status, result_dir, finished_utc, validity), canonical bytes."""
    plan = plan_gen.generate_campaign_plan(42)
    finished = {1: "2026-09-18T22:00:22.646Z", 2: "2026-09-19T00:23:15.492Z", 3: "2026-10-03T13:41:59.000Z"}
    for entry in plan["runs"]:
        if entry["condition_id"] == "controller_restart":
            rid = entry["run_id"]
            entry.update(status="failed", validity="invalid", finished_utc=finished[entry["repetition"]],
                         result_dir=f"/home/ruisth/egw-tcg/pilot/results/raw/{rid}")
    return plan_gen.plan_to_json(plan)


def _restart_entries(plan: dict) -> list[dict]:
    return [e for e in plan["runs"] if e["condition_id"] == "controller_restart"]


def test_the_campaign_plan_and_its_restart_entries_are_byte_identical_to_before() -> None:
    """The supplement never enters what ``plan`` generates: the same 95 runs,
    the same three controller_restart entries, the same bytes, the same
    protocol version."""
    plan = plan_gen.generate_campaign_plan(42)
    text = plan_gen.plan_to_json(plan)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == PLAN_42_SHA256
    assert len(plan["runs"]) == EXPECTED_TOTAL_RUNS
    assert _restart_entries(plan) == FROZEN_RESTART_ENTRIES_42
    assert not any("supplement" in e for e in plan["runs"])
    assert protocol.PROTOCOL_VERSION == "1.0.0"
    assert protocol.CONDITIONS_BY_ID["controller_restart"].repetitions == 3


def test_g3_t6_supplementary_entry_is_controller_restart_r04_with_the_original_load() -> None:
    """One fresh entry: the frozen condition's runner, scenario, rate,
    duration, warm-up and cool-down (r03's but for its id, repetition, seed
    and order), seeded by the plan's own seed rule and marked as the supplement."""
    entry = plan_gen.supplementary_entry(42, "g3-t6", 96)
    assert entry == {
        "condition_id": "controller_restart", "cooldown_s": 0, "duration_s": 600, "order": 96,
        "rate_msg_s": 11.2, "repetition": 4, "run_id": "controller_restart-r04", "runner": "simulator",
        "scenario": "nominal", "seed": plan_gen.derive_run_seed(42, "controller_restart-r04"),
        "status": "planned", "supplement": "g3-t6", "warmup_s": 0,
    }
    assert entry["seed"] == 1715385812
    r03 = FROZEN_RESTART_ENTRIES_42[2]
    same = {k for k in r03 if k not in ("run_id", "repetition", "seed", "order")}
    assert {k: entry[k] for k in same} == {k: r03[k] for k in same}
    assert plan_gen.SUPPLEMENTS == {"g3-t6": ("controller_restart", 4)}


def test_supplementary_run_id_collides_with_no_planned_or_used_run_id() -> None:
    """The collision guard: the id is none the campaign plan enumerates (the
    ids do not depend on the master seed), none used on the guest, and its
    seed is none of the plan's; the harness runs only ids in its plan, so an
    id no plan ever held was never run by it."""
    rid = plan_gen.supplementary_entry(42, "g3-t6", 96)["run_id"]
    for seed in (0, 7, 42, 123):
        assert rid not in {e["run_id"] for e in plan_gen.generate_campaign_plan(seed)["runs"]}
    assert rid not in USED_RUN_IDS
    assert plan_gen.RUN_ID_RE.match(rid)
    seeds = {e["seed"] for e in plan_gen.generate_campaign_plan(42)["runs"]}
    assert plan_gen.supplementary_entry(42, "g3-t6", 96)["seed"] not in seeds


def test_supplement_appends_one_entry_and_keeps_every_byte_before_it() -> None:
    """On the pilot plan as the host held it (statuses written by the
    harness), the supplement adds r04 after the last entry: every byte of the
    file up to the last entry's closing brace is kept, r01-r03 included."""
    before = _pilot_plan_text_as_on_2026_10_03()
    after, entry, added = plan_gen.supplement_plan(before, "g3-t6")
    assert added is True
    assert after.startswith(before[: -len(PLAN_TAIL)] + ",\n    {\n")
    assert after.endswith(PLAN_TAIL) and "\r" not in after
    old, new = json.loads(before), json.loads(after)
    assert new["runs"][:-1] == old["runs"]
    assert new["runs"][-1] == entry == plan_gen.supplementary_entry(42, "g3-t6", 96)
    assert {k: new[k] for k in new if k != "runs"} == {k: old[k] for k in old if k != "runs"}
    assert [e["run_id"] for e in _restart_entries(new)] == [f"controller_restart-r0{i}" for i in (1, 2, 3, 4)]
    assert after == plan_gen.plan_to_json(new)


def test_supplement_is_never_added_twice_whatever_status_the_entry_has_reached() -> None:
    """Applied again - before the run or after it - the plan is left as it is."""
    once, entry, _ = plan_gen.supplement_plan(_pilot_plan_text_as_on_2026_10_03(), "g3-t6")
    again, entry_again, added = plan_gen.supplement_plan(once, "g3-t6")
    assert (again, entry_again, added) == (once, entry, False)
    ran = json.loads(once)
    ran["runs"][-1].update(status="completed", validity="valid", finished_utc="2026-10-06T10:00:00.000Z",
                           result_dir="/home/ruisth/egw-tcg/pilot/results/raw/controller_restart-r04")
    ran_text = plan_gen.plan_to_json(ran)
    assert plan_gen.supplement_plan(ran_text, "g3-t6")[0::2] == (ran_text, False)


def _mutated(how: str) -> str:
    text = _pilot_plan_text_as_on_2026_10_03()
    plan = json.loads(text)
    runs = plan["runs"]
    r03 = next(e for e in runs if e["run_id"] == "controller_restart-r03")
    r04 = plan_gen.supplementary_entry(42, "g3-t6", 96)
    if how == "crlf":
        return text.replace("\n", "\r\n")
    if how == "indent-4":
        return json.dumps(plan, indent=4, sort_keys=True, ensure_ascii=False) + "\n"
    if how == "no-final-newline":
        return text[:-1]
    if how == "not-json":
        return text[:-3]
    if how == "no-runs-list":
        return plan_gen.plan_to_json({k: v for k, v in plan.items() if k != "runs"})
    if how == "r03-seed-changed":
        r03["seed"] += 1
    elif how == "r03-renumbered":
        r03["order"] = 99
    elif how == "r03-rate-changed":
        r03["rate_msg_s"] = 5.6
    elif how == "entry-removed":
        runs.remove(next(e for e in runs if e["run_id"] == "controller_restart-r02"))
    elif how == "protocol-version":
        plan["protocol_version"] = "1.0.1"
    elif how == "master-seed-not-a-number":
        plan["master_seed"] = True
    elif how == "foreign-extra-entry":
        runs.append({**r04, "run_id": "controller_restart-r05", "repetition": 5})
    elif how == "r04-other-seed":
        runs.append({**r04, "seed": r04["seed"] + 1})
    elif how == "r04-without-its-mark":
        runs.append({k: v for k, v in r04.items() if k != "supplement"})
    else:
        raise AssertionError(how)
    return plan_gen.plan_to_json(plan)


@pytest.mark.parametrize("how", [
    "crlf", "indent-4", "no-final-newline", "not-json", "no-runs-list", "r03-seed-changed", "r03-renumbered",
    "r03-rate-changed", "entry-removed", "protocol-version", "master-seed-not-a-number", "foreign-extra-entry",
    "r04-other-seed", "r04-without-its-mark",
])
def test_supplement_refuses_a_plan_it_cannot_extend_without_changing_it(how: str) -> None:
    """Refused, naming the reason: a file not in the harness's canonical bytes
    (rewriting it would change bytes of entries it holds), a plan that is not
    the frozen generation of its master seed, or one already holding an id
    that collides with the supplement's."""
    with pytest.raises(plan_gen.PlanSupplementError):
        plan_gen.supplement_plan(_mutated(how), "g3-t6")


def test_supplement_refuses_an_unknown_key() -> None:
    with pytest.raises(plan_gen.PlanSupplementError, match="unknown supplement"):
        plan_gen.supplement_plan(_pilot_plan_text_as_on_2026_10_03(), "g3-t7")


def test_apply_plan_supplement_writes_lf_bytes_once_and_leaves_a_refused_file_alone(tmp_path) -> None:
    path = tmp_path / "campaign_plan.json"
    path.write_bytes(_pilot_plan_text_as_on_2026_10_03().encode("utf-8"))
    entry, added = plan_gen.apply_plan_supplement(path, "g3-t6")
    written = path.read_bytes()
    assert added is True and entry["run_id"] == "controller_restart-r04"
    assert b"\r" not in written and json.loads(written)["runs"][-1] == entry
    assert plan_gen.apply_plan_supplement(path, "g3-t6") == (entry, False)
    assert path.read_bytes() == written
    assert sorted(p.name for p in tmp_path.iterdir()) == ["campaign_plan.json"]
    refused = tmp_path / "refused.json"
    refused.write_bytes(_mutated("r03-seed-changed").encode("utf-8"))
    kept = refused.read_bytes()
    with pytest.raises(plan_gen.PlanSupplementError):
        plan_gen.apply_plan_supplement(refused, "g3-t6")
    assert refused.read_bytes() == kept


def test_analysis_reads_the_supplemented_plan_unchanged_and_says_the_plan_lists_four() -> None:
    """analyze.py is not changed: with the supplement, the pilot plan's
    controller_restart identities are four, r04 among them with its own seed,
    and the completeness row says the plan lists four where the frozen
    protocol plans three (it fails on completeness in a pilot tree anyway)."""
    from egw_experiments import analyze

    plan = json.loads(plan_gen.supplement_plan(_pilot_plan_text_as_on_2026_10_03(), "g3-t6")[0])
    identities = analyze.plan_identities_by_condition(plan)["controller_restart"]
    assert identities[-1] == ("controller_restart-r04", 4, 1715385812, 11.2)
    rows = analyze.evaluate_acceptance([], plan)
    complete = next(r for r in rows if r["condition_id"] == "controller_restart" and r["criterion"] == "runs_complete")
    assert complete["passed"] is False
    assert "the campaign plan lists 4 run(s) for this condition, the frozen protocol plans 3" in complete["observed"]
