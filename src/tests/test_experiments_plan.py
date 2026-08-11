"""Tests for egw_experiments.protocol and plan_gen (plan 7.1 completed per
audit 2026-08-08 section 9.5; CONTRACTS 2).

Stdlib-only fixtures; no docker, no network.
"""
from __future__ import annotations

import json

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
