"""Tests for egw_experiments.protocol and plan_gen (plan 7.1; CONTRACTS 2).

Stdlib-only fixtures; no docker, no network.
"""
from __future__ import annotations

import json

from egw_experiments import plan_gen, protocol

EXPECTED_TOTAL_RUNS = 5 + 10 + 10 + 10 + 4 * 10 + 1  # 76


def _load_sweep_order(plan: dict) -> list[tuple[float, int]]:
    return [
        (run["rate_msg_s"], run["repetition"])
        for run in plan["runs"]
        if run["condition_id"] == "load_sweep"
    ]


def test_protocol_conditions_match_plan_7_1() -> None:
    by_id = protocol.CONDITIONS_BY_ID
    assert set(by_id) == {
        "qemu_boots",
        "cold_start",
        "twin_creation",
        "nominal",
        "load_sweep",
        "soak",
    }
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
