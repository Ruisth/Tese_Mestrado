"""Tests for egw_experiments.analyze (plan 7.2/7.3 definitions, verbatim).

All fixtures are synthetic stdlib-built files in tmp_path; no docker, no
network, no third-party dependencies.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from egw_experiments import analyze

# v1.1 clock-domain rule (CONTRACTS/plan 5.1): the confirmation deadline
# lives in the CONTROLLER's clock domain — max(received_monotonic_ns) over
# the run's controller events plus confirmation_window_s. Every default
# fixture event uses MAX_RECEIVED_NS, so DEADLINE_NS is the event-derived
# deadline of the standard fixture run.
WINDOW_S = 60
WINDOW_NS = WINDOW_S * 1_000_000_000
MAX_RECEIVED_NS = 100
DEADLINE_NS = MAX_RECEIVED_NS + WINDOW_NS


# ---------------------------------------------------------------------------
# Synthetic raw-run builder
# ---------------------------------------------------------------------------


def sent_record(mid: str, seq: int = 0, intended_invalid: bool = False) -> dict:
    return {
        "run_id": "r",
        "message_id": mid,
        "device_uuid": "d0000000-0000-4000-8000-000000000000",
        "seq": seq,
        "publish_monotonic_ns": 1_000 + seq,
        "puback_monotonic_ns": 2_000 + seq,
        "intended_invalid": intended_invalid,
    }


def event_record(
    mid: str | None,
    outcome: str,
    latency_ms: float | None = None,
    ack_ns: int | None = None,
    seq: int = 0,
    received_ns: int = MAX_RECEIVED_NS,
) -> dict:
    if outcome == "accepted":
        if ack_ns is None:
            ack_ns = DEADLINE_NS - 1_000
        if latency_ms is None:
            latency_ms = 10.0
    else:
        ack_ns = None
        latency_ms = None
    return {
        "run_id": "r",
        "message_id": mid,
        "device_uuid": "d0000000-0000-4000-8000-000000000000",
        "device_type": "smartwatch",
        "seq": seq,
        "received_monotonic_ns": received_ns,
        "ditto_ack_monotonic_ns": ack_ns,
        "latency_ms": latency_ms,
        "outcome": outcome,
        "attempts": 1,
        "error": None,
    }


def make_run(
    base: Path,
    run_id: str,
    sent: list[dict],
    events: list[dict],
    manifest_extra: dict | None = None,
    resources_rows: list[list] | None = None,
    controller_metrics_rows: list[list] | None = None,
    sut_env: dict | None = None,
) -> Path:
    run_dir = base / "raw" / run_id
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "condition_id": "nominal",
        "scenario": "nominal",
        "rate_msg_s": 11.2,
        "duration_s": 600,
        "seed": 1,
        "repetition": 1,
        "confirmation_window_s": WINDOW_S,
        # Harness-host clock domain, informational only (v1.1); the fixture
        # value is plausible against the events so no warning fires.
        "confirmation_deadline_monotonic_ns": DEADLINE_NS,
        "confirmation_deadline_clock_domain": "harness-host",
        "exclusion": None,
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", "utf-8"
    )
    (run_dir / "sent_events.jsonl").write_text(
        "".join(json.dumps(rec) + "\n" for rec in sent), "utf-8"
    )
    (run_dir / "events.jsonl").write_text(
        "".join(json.dumps(rec) + "\n" for rec in events), "utf-8"
    )
    if resources_rows is not None:
        lines = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct"]
        lines += [",".join(str(v) for v in row) for row in resources_rows]
        (run_dir / "resources.csv").write_text("\n".join(lines) + "\n", "utf-8")
    if controller_metrics_rows is not None:
        lines = ["ts_utc,accepted,rejected,duplicate,failed,dropped,queue_depth"]
        lines += [",".join(str(v) for v in row) for row in controller_metrics_rows]
        (run_dir / "controller_metrics.csv").write_text(
            "\n".join(lines) + "\n", "utf-8"
        )
    if sut_env is not None:
        (run_dir / "sut_environment.json").write_text(
            json.dumps(sut_env) + "\n", "utf-8"
        )
    return run_dir


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


T0 = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Delivery-rate definitions (plan 7.3 verbatim)
# ---------------------------------------------------------------------------


def test_delivery_all_accepted(tmp_path) -> None:
    mids = [f"m{i}" for i in range(5)]
    run_dir = make_run(
        tmp_path,
        "all-accepted",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=[event_record(m, "accepted", latency_ms=5.0) for m in mids],
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["sent_valid"] == 5
    assert row["delivered_unique"] == 5
    assert row["lost"] == 0
    assert row["delivery_rate"] == 1.0
    assert row["loss_rate"] == 0.0


def test_delivery_duplicates_counted_separately_and_once(tmp_path) -> None:
    mids = [f"m{i}" for i in range(4)]
    events = [event_record(m, "accepted") for m in mids]
    events += [event_record(mids[0], "duplicate"), event_record(mids[1], "duplicate")]
    run_dir = make_run(
        tmp_path,
        "dups",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=events,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["delivered_unique"] == 4  # unique confirmations only
    assert row["duplicates"] == 2
    assert row["delivery_rate"] == 1.0
    assert row["lost"] == 0


def test_intended_invalid_rejected_is_validation_success_not_loss(tmp_path) -> None:
    valid = [f"m{i}" for i in range(3)]
    invalid = ["bad0", "bad1"]
    sent = [sent_record(m, i) for i, m in enumerate(valid)]
    sent += [sent_record(m, 10 + i, intended_invalid=True) for i, m in enumerate(invalid)]
    events = [event_record(m, "accepted") for m in valid]
    events += [event_record(m, "rejected") for m in invalid]
    run_dir = make_run(tmp_path, "invalid-ok", sent=sent, events=events)
    row = analyze.compute_run_metrics(run_dir)
    # intended_invalid excluded from the denominator (plan 7.3)
    assert row["sent_total"] == 5
    assert row["sent_valid"] == 3
    assert row["intended_invalid_sent"] == 2
    assert row["rejected_intended_invalid"] == 2
    assert row["rejected_valid"] == 0
    # correctly rejected invalid payloads are never losses
    assert row["lost"] == 0
    assert row["delivery_rate"] == 1.0
    assert row["intended_invalid_accepted"] == 0


def test_lost_message_counts_against_delivery_rate(tmp_path) -> None:
    mids = [f"m{i}" for i in range(5)]
    run_dir = make_run(
        tmp_path,
        "one-lost",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=[event_record(m, "accepted") for m in mids[:4]],  # m4 never confirmed
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["delivered_unique"] == 4
    assert row["lost"] == 1
    assert row["delivery_rate"] == 0.8
    assert row["loss_rate"] == 0.2


def test_late_confirmation_past_60s_window_counts_as_lost(tmp_path) -> None:
    mids = [f"m{i}" for i in range(5)]
    events = [event_record(m, "accepted") for m in mids[:4]]
    # m4 confirmed only AFTER the confirmation deadline: still lost.
    events.append(event_record(mids[4], "accepted", ack_ns=DEADLINE_NS + 1))
    run_dir = make_run(
        tmp_path,
        "late-conf",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=events,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["late_confirmations"] == 1
    assert row["delivered_unique"] == 4
    assert row["lost"] == 1
    assert row["delivery_rate"] == 0.8


def test_valid_rejected_message_is_lost_and_counted_rejected(tmp_path) -> None:
    mids = [f"m{i}" for i in range(3)]
    events = [event_record(m, "accepted") for m in mids[:2]]
    events.append(event_record(mids[2], "rejected"))
    run_dir = make_run(
        tmp_path,
        "valid-rejected",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=events,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["rejected_valid"] == 1
    assert row["delivered_unique"] == 2
    assert row["lost"] == 1  # no unique confirmation for the rejected one


# ---------------------------------------------------------------------------
# Confirmation deadline in the controller's clock domain (v1.1, plan 5.1)
# ---------------------------------------------------------------------------


def test_deadline_derived_from_controller_events_in_window_vs_late(tmp_path) -> None:
    """The deadline is max(received_monotonic_ns) + window, in the
    controller's clock domain — no manifest deadline is needed."""
    mids = ["m0", "m1", "m2"]
    max_received = 2_000
    events = [
        event_record("m0", "accepted", received_ns=500, ack_ns=500 + 10_000),
        # Ack exactly 1 ns inside the event-derived window: in-window.
        event_record(
            "m1",
            "accepted",
            received_ns=max_received,
            ack_ns=max_received + WINDOW_NS - 1,
        ),
        # Ack past max(received) + window: late, hence lost.
        event_record(
            "m2",
            "accepted",
            received_ns=1_000,
            ack_ns=max_received + WINDOW_NS + 1,
        ),
    ]
    run_dir = make_run(
        tmp_path,
        "clock-domain",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=events,
        manifest_extra={"confirmation_deadline_monotonic_ns": None},
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["delivered_unique"] == 2
    assert row["late_confirmations"] == 1
    assert row["lost"] == 1
    # The manifest deadline is informational only; its absence is noted.
    assert "missing from manifest" in row["warnings"]


def test_zero_events_fall_back_to_manifest_deadline(tmp_path) -> None:
    """With zero controller events the manifest deadline (harness-host
    clock domain) is the last-resort fallback."""
    run_dir = make_run(
        tmp_path,
        "no-events",
        sent=[sent_record("m0"), sent_record("m1", 1)],
        events=[],
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["delivered_unique"] == 0
    assert row["lost"] == 2
    assert "falling back" in row["warnings"]
    assert "harness-host" in row["warnings"]


def test_implausible_manifest_deadline_warns_and_uses_event_derived(tmp_path) -> None:
    """A manifest deadline captured on another host (plan 5.1: harness runs
    off the ARM VM) can be arbitrarily far from the controller's monotonic
    values; it must be flagged loudly and the event-derived deadline used."""
    implausible = 999_000_000_000_000_000  # far outside [max(received), +2w]
    events = [
        event_record("m0", "accepted"),  # inside the event-derived window
        # Late per the event-derived deadline although far below the
        # (implausible) manifest deadline.
        event_record("m1", "accepted", ack_ns=DEADLINE_NS + 1),
    ]
    run_dir = make_run(
        tmp_path,
        "implausible-deadline",
        sent=[sent_record("m0"), sent_record("m1", 1)],
        events=events,
        manifest_extra={"confirmation_deadline_monotonic_ns": implausible},
    )
    row = analyze.compute_run_metrics(run_dir)
    assert "IMPLAUSIBLE" in row["warnings"]
    assert row["late_confirmations"] == 1
    assert row["delivered_unique"] == 1
    assert row["lost"] == 1


def test_accepted_event_without_ack_counts_but_warns(tmp_path) -> None:
    """An accepted event with ditto_ack_monotonic_ns null violates
    CONTRACTS 5; it is still counted (as before) but flagged."""
    rec = event_record("m0", "accepted")
    rec["ditto_ack_monotonic_ns"] = None
    rec["latency_ms"] = None
    run_dir = make_run(
        tmp_path, "no-ack", sent=[sent_record("m0")], events=[rec]
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["delivered_unique"] == 1
    assert row["latency_count"] == 0
    assert "accepted event without ditto_ack_monotonic_ns" in row["warnings"]


# ---------------------------------------------------------------------------
# Warm-up interplay (CONTRACTS v1.1 section 4: run-scoped dedupe)
# ---------------------------------------------------------------------------


def test_measured_run_after_warmup_has_zero_duplicates(tmp_path) -> None:
    """A measured run following a same-seed warm-up (same device_uuids, seq
    restarting at 0, distinct run_id) must contain zero 'duplicate'
    outcomes in its OWN events.jsonl for delivery_rate to be ~1.0.

    The harness warm-up intentionally reuses the run's seed (it warms the
    real twins), so this holds only with a controller implementing
    CONTRACTS >= v1.1 run-scoped dedupe: the seq floor resets when the
    run_id changes. Controller-side regression coverage lives in
    tests/test_controller_dedupe.py; this fixture encodes the expected
    v1.1 evidence shape (seq restarts at 0, no duplicates).
    """
    mids = [f"m{i}" for i in range(5)]
    # Same device_uuid as the warm-up would use; seq restarts at 0.
    sent = [sent_record(m, seq=i) for i, m in enumerate(mids)]
    events = [event_record(m, "accepted", seq=i) for i, m in enumerate(mids)]
    run_dir = make_run(tmp_path, "after-warmup", sent=sent, events=events)
    row = analyze.compute_run_metrics(run_dir)
    assert row["duplicates"] == 0
    assert row["delivery_rate"] == 1.0


# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------


def test_intended_invalid_accepted_is_flagged_and_delivered_unchanged(tmp_path) -> None:
    sent = [
        sent_record("m0"),
        sent_record("m1", 1),
        sent_record("bad0", 2, intended_invalid=True),
    ]
    events = [
        event_record("m0", "accepted"),
        event_record("m1", "accepted"),
        event_record("bad0", "accepted"),  # validation defect
    ]
    run_dir = make_run(tmp_path, "invalid-accepted", sent=sent, events=events)
    row = analyze.compute_run_metrics(run_dir)
    assert row["intended_invalid_accepted"] == 1
    assert row["delivered_unique"] == 2  # only valid sent messages count
    assert row["delivery_rate"] == 1.0
    assert "validation defect" in row["warnings"]


def test_confirmed_message_id_absent_from_sent_events_is_unmatched(tmp_path) -> None:
    run_dir = make_run(
        tmp_path,
        "ghost-confirmation",
        sent=[sent_record("m0")],
        events=[
            event_record("m0", "accepted"),
            event_record("ghost", "accepted"),
        ],
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["confirmed_unmatched"] == 1
    assert row["delivered_unique"] == 1
    assert "absent" in row["warnings"]


def test_run_dir_with_only_manifest_returns_none(tmp_path, capsys) -> None:
    run_dir = tmp_path / "raw" / "cold_start-r01"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        '{"run_id": "cold_start-r01"}\n', "utf-8"
    )
    assert analyze.compute_run_metrics(run_dir) is None
    assert "no sent_events.jsonl" in capsys.readouterr().err


def test_manifest_without_deadline_warns(tmp_path) -> None:
    run_dir = make_run(
        tmp_path,
        "no-deadline",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={"confirmation_deadline_monotonic_ns": None},
    )
    row = analyze.compute_run_metrics(run_dir)
    assert "missing from manifest" in row["warnings"]


# ---------------------------------------------------------------------------
# Latency percentile math
# ---------------------------------------------------------------------------


def test_percentile_linear_interpolation() -> None:
    values = [float(i) for i in range(1, 11)]  # 1..10
    assert analyze.percentile(values, 50) == 5.5
    assert math.isclose(analyze.percentile(values, 95), 9.55)
    assert math.isclose(analyze.percentile(values, 99), 9.91)
    assert analyze.percentile(values, 0) == 1.0
    assert analyze.percentile(values, 100) == 10.0
    assert analyze.percentile([42.0], 95) == 42.0
    assert analyze.percentile([], 50) is None


def test_per_run_latency_stats_from_accepted_events(tmp_path) -> None:
    mids = [f"m{i}" for i in range(4)]
    latencies = [10.0, 20.0, 30.0, 40.0]
    run_dir = make_run(
        tmp_path,
        "latency",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=[
            event_record(m, "accepted", latency_ms=lat)
            for m, lat in zip(mids, latencies)
        ],
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["latency_count"] == 4
    assert row["latency_ms_mean"] == 25.0
    assert row["latency_ms_p50"] == 25.0
    assert math.isclose(row["latency_ms_p95"], 38.5)
    assert row["latency_ms_min"] == 10.0
    assert row["latency_ms_max"] == 40.0


# ---------------------------------------------------------------------------
# CI95 (t-distribution, hardcoded table) against a hand-computed example
# ---------------------------------------------------------------------------


def test_ci95_hand_computed_example() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    mean, stdev, half = analyze.ci95(values)
    assert mean == 3.0
    assert math.isclose(stdev, math.sqrt(2.5), rel_tol=1e-12)
    # t(df=4, two-sided 95%) = 2.776; half = 2.776 * sqrt(2.5)/sqrt(5)
    expected_half = 2.776 * math.sqrt(2.5) / math.sqrt(5)
    assert math.isclose(half, expected_half, rel_tol=1e-12)
    assert math.isclose(half, 1.962928, abs_tol=1e-5)


def test_ci95_undefined_for_single_run() -> None:
    mean, stdev, half = analyze.ci95([7.5])
    assert mean == 7.5
    assert stdev is None and half is None
    assert analyze.ci95([]) == (None, None, None)


def test_t_table_spot_values_and_conservative_fallback() -> None:
    assert analyze.t_critical_95(1) == 12.706
    assert analyze.t_critical_95(9) == 2.262  # n=10 runs
    assert analyze.t_critical_95(30) == 2.042
    assert analyze.t_critical_95(100) == 2.042  # documented df>30 fallback


# ---------------------------------------------------------------------------
# Sustained CPU and saturation criteria (plan 7.3)
# ---------------------------------------------------------------------------


def _cpu_samples(count: int, cpu_pct: float) -> list[dict]:
    start = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)
    return [
        {"ts": start + timedelta(seconds=i), "cpu_pct": cpu_pct, "mem_bytes": 1}
        for i in range(count)
    ]


def test_sustained_cpu_seconds() -> None:
    # 61 samples at 1 Hz above 90% span exactly 60 s.
    assert analyze.sustained_cpu_seconds(_cpu_samples(61, 95.0)) == 60.0
    assert analyze.sustained_cpu_seconds(_cpu_samples(30, 95.0)) == 29.0
    assert analyze.sustained_cpu_seconds(_cpu_samples(61, 89.9)) == 0.0
    # A dip below the threshold breaks the streak.
    samples = _cpu_samples(30, 95.0) + _cpu_samples(1, 10.0) + _cpu_samples(30, 95.0)
    assert analyze.sustained_cpu_seconds(samples) < 60.0


def _sweep_row(
    rate: float,
    loss: float,
    p95: float,
    host_sustained_s: float = 0.0,
    queue_sustained_s: float = 0.0,
) -> dict:
    return {
        "condition_id": "load_sweep",
        "rate_msg_s": rate,
        "loss_rate": loss,
        "latency_ms_p95": p95,
        "host_cpu_sustained_gt090_s": host_sustained_s,
        "queue_growth_sustained_s": queue_sustained_s,
    }


def test_saturation_triggers_on_loss_criterion() -> None:
    rows = [
        _sweep_row(10.0, 0.0, 100.0),
        _sweep_row(50.0, 0.02, 100.0),  # mean loss 2% > 1%
    ]
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    by_rate = {load["rate_msg_s"]: load for load in result["loads"]}
    assert by_rate[10.0]["saturated"] is False
    assert by_rate[50.0]["triggered"]["loss_rate"] is True
    assert by_rate[50.0]["triggered"]["p95_latency"] is False


def test_saturation_triggers_on_p95_criterion() -> None:
    rows = [
        _sweep_row(10.0, 0.0, 200.0),
        _sweep_row(50.0, 0.0, 1500.0),  # mean p95 > 1000 ms
    ]
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    by_rate = {load["rate_msg_s"]: load for load in result["loads"]}
    assert by_rate[50.0]["triggered"]["p95_latency"] is True
    assert by_rate[50.0]["triggered"]["loss_rate"] is False


def test_saturation_triggers_on_sustained_host_cpu_criterion() -> None:
    # Audit 9.7: the CPU criterion is HOST-LEVEL (normalized by nproc),
    # not the raw per-container docker-stats percentage.
    rows = [
        _sweep_row(10.0, 0.0, 100.0),
        _sweep_row(50.0, 0.0, 100.0, host_sustained_s=65.0),
    ]
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    by_rate = {load["rate_msg_s"]: load for load in result["loads"]}
    assert by_rate[50.0]["triggered"]["host_cpu_sustained"] is True


def test_saturation_cpu_fraction_one_of_three_runs_is_not_saturated() -> None:
    # Decision rule: the CPU criterion holds only when at least HALF of the
    # runs at a load show a sustained >= 60 s event. 1 of 3 < 0.5.
    rows = [
        _sweep_row(50.0, 0.0, 100.0, host_sustained_s=65.0),
        _sweep_row(50.0, 0.0, 100.0),
        _sweep_row(50.0, 0.0, 100.0),
    ]
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] is None
    load = result["loads"][0]
    assert load["n_runs"] == 3
    assert load["host_cpu_sustained_run_fraction"] < 0.5
    assert load["triggered"]["host_cpu_sustained"] is False
    assert load["saturated"] is False


def test_saturation_cpu_fraction_two_of_three_runs_is_saturated() -> None:
    # 2 of 3 runs with sustained >= 60 s: fraction >= 0.5, criterion holds.
    rows = [
        _sweep_row(50.0, 0.0, 100.0, host_sustained_s=65.0),
        _sweep_row(50.0, 0.0, 100.0, host_sustained_s=61.0),
        _sweep_row(50.0, 0.0, 100.0),
    ]
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    load = result["loads"][0]
    assert load["triggered"]["host_cpu_sustained"] is True
    assert load["saturated"] is True


def test_saturation_triggers_on_queue_growth_criterion() -> None:
    # Audit 9.7: queue growth is measured (controller_metrics.csv), no TODO.
    rows = [
        _sweep_row(10.0, 0.0, 100.0),
        _sweep_row(50.0, 0.0, 100.0, queue_sustained_s=61.0),
        _sweep_row(50.0, 0.0, 100.0, queue_sustained_s=75.0),
        _sweep_row(50.0, 0.0, 100.0, queue_sustained_s=0.0),
    ]
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    by_rate = {load["rate_msg_s"]: load for load in result["loads"]}
    assert by_rate[50.0]["triggered"]["queue_growth"] is True
    assert by_rate[50.0]["queue_growth_run_fraction"] == 2 / 3
    assert by_rate[10.0]["triggered"]["queue_growth"] is False


def test_saturation_criteria_not_evaluable_without_instrumentation() -> None:
    # Runs without nproc/controller_metrics carry None; the criterion is
    # None (not evaluable), never silently False, and cannot saturate.
    rows = [
        {
            "condition_id": "load_sweep",
            "rate_msg_s": 50.0,
            "loss_rate": 0.0,
            "latency_ms_p95": 100.0,
            "host_cpu_sustained_gt090_s": None,
            "queue_growth_sustained_s": None,
        }
    ]
    result = analyze.detect_saturation(rows)
    load = result["loads"][0]
    assert load["triggered"]["host_cpu_sustained"] is None
    assert load["triggered"]["queue_growth"] is None
    assert load["saturated"] is False


def test_saturation_not_triggered_below_thresholds() -> None:
    rows = [
        _sweep_row(10.0, 0.0, 100.0),
        # thresholds are strict (>) for loss/p95; sustained windows below
        # 60 s never count.
        _sweep_row(50.0, 0.01, 1000.0, host_sustained_s=59.0, queue_sustained_s=59.0),
    ]
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] is None
    assert all(not load["saturated"] for load in result["loads"])
    # The queue-growth rule is now documented and evaluated (audit 9.7)
    # and explicitly marked pending advisor sign-off before exp-v1 (R23).
    criteria = result["criteria"]
    assert criteria["queue_depth_floor"] == 100
    assert criteria["queue_growth_sustain_s"] == 60
    assert criteria["host_cpu_utilization_gt"] == 0.90
    assert criteria["run_fraction_gte"] == 0.5
    assert "PENDING ADVISOR SIGN-OFF" in result["pending_advisor_signoff"]
    assert "exp-v1" in result["pending_advisor_signoff"]


# ---------------------------------------------------------------------------
# Queue-growth detector (audit 9.7; rule pending advisor sign-off)
# ---------------------------------------------------------------------------


def _queue_samples(depths: list[float | None], start: datetime = T0) -> list[dict]:
    return [
        {"ts": start + timedelta(seconds=i), "queue_depth": depth}
        for i, depth in enumerate(depths)
    ]


def test_queue_growth_61_increasing_samples_above_floor_span_60s() -> None:
    depths = [101.0 + i for i in range(61)]  # strictly increasing, > 100
    assert analyze.queue_growth_sustained_seconds(_queue_samples(depths)) == 60.0


def test_queue_growth_below_floor_never_counts() -> None:
    depths = [10.0 + i for i in range(61)]  # strictly increasing but <= 100
    assert analyze.queue_growth_sustained_seconds(_queue_samples(depths)) == 0.0


def test_queue_growth_plateau_breaks_the_window() -> None:
    # Strict increase required: a plateau splits the streak.
    depths = [101.0 + i for i in range(31)]
    depths += [depths[-1]]  # plateau
    depths += [depths[-1] + 1 + i for i in range(31)]
    span = analyze.queue_growth_sustained_seconds(_queue_samples(depths))
    assert span < 60.0


def test_queue_growth_dip_below_floor_resets() -> None:
    depths = [101.0 + i for i in range(30)] + [50.0] + [200.0 + i for i in range(30)]
    span = analyze.queue_growth_sustained_seconds(_queue_samples(depths))
    assert span < 60.0


# ---------------------------------------------------------------------------
# Host-level CPU normalization (audit 9.7)
# ---------------------------------------------------------------------------


def test_host_cpu_series_normalizes_by_nproc() -> None:
    by_container = {
        "a": [{"ts": T0, "cpu_pct": 200.0}, {"ts": T0 + timedelta(seconds=1), "cpu_pct": 100.0}],
        "b": [{"ts": T0, "cpu_pct": 200.0}, {"ts": T0 + timedelta(seconds=1), "cpu_pct": 60.0}],
    }
    series = analyze.host_cpu_series(by_container, nproc=4)
    # (200+200)/(100*4) = 1.0; (100+60)/(100*4) = 0.4
    assert [round(p["host_cpu_utilization"], 6) for p in series] == [1.0, 0.4]


def test_host_cpu_sustained_seconds_thresholds() -> None:
    series = [
        {"ts": T0 + timedelta(seconds=i), "host_cpu_utilization": 0.95}
        for i in range(61)
    ]
    assert analyze.host_cpu_sustained_seconds(series) == 60.0
    series_low = [
        {"ts": T0 + timedelta(seconds=i), "host_cpu_utilization": 0.90}
        for i in range(61)
    ]  # threshold is strict (> 0.90)
    assert analyze.host_cpu_sustained_seconds(series_low) == 0.0


def test_compute_run_metrics_host_cpu_from_sut_environment(tmp_path) -> None:
    # Two containers at 200% each with nproc=4 -> host utilization 1.0.
    n = 65
    resources = []
    for i in range(n):
        ts = _iso(T0 + timedelta(seconds=i))
        resources.append([ts, "egw-controller", 200.0, 1024, 1.0])
        resources.append([ts, "mosquitto", 200.0, 1024, 1.0])
    run_dir = make_run(
        tmp_path,
        "host-cpu",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        resources_rows=resources,
        sut_env={"role": "sut", "nproc": 4},
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["nproc"] == 4
    assert row["host_cpu_utilization_max"] == 1.0
    assert row["host_cpu_sustained_gt090_s"] == float(n - 1)
    # Raw per-container basis still reported (single-CPU docker semantics).
    assert row["cpu_pct_max"] == 200.0


def test_compute_run_metrics_without_nproc_flags_host_cpu_not_evaluable(tmp_path) -> None:
    resources = [[_iso(T0), "egw-controller", 95.0, 1024, 1.0]]
    run_dir = make_run(
        tmp_path,
        "no-nproc",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        resources_rows=resources,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["nproc"] is None
    assert row["host_cpu_utilization_max"] is None
    assert row["host_cpu_sustained_gt090_s"] is None
    assert "nproc unavailable" in row["warnings"]


# ---------------------------------------------------------------------------
# Measured-window filtering (audit 9.4)
# ---------------------------------------------------------------------------


def _window_manifest(start: datetime, end: datetime) -> dict:
    return {
        "measured_window_utc": {"start": _iso(start), "end": _iso(end)},
        "measured_started_monotonic_ns": 123,
    }


def test_resources_filtered_to_measured_window(tmp_path) -> None:
    start = T0
    end = T0 + timedelta(seconds=600)
    resources = [
        # Warm-up sample (before the window): must be excluded.
        [_iso(start - timedelta(seconds=30)), "egw-controller", 99.0, 9_000_000, 9.0],
        # In-window samples.
        [_iso(start + timedelta(seconds=10)), "egw-controller", 10.0, 1_000_000, 1.0],
        [_iso(start + timedelta(seconds=11)), "egw-controller", 20.0, 2_000_000, 2.0],
        # Post-run sample (after the window): must be excluded.
        [_iso(end + timedelta(seconds=30)), "egw-controller", 98.0, 8_000_000, 8.0],
    ]
    run_dir = make_run(
        tmp_path,
        "windowed",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra=_window_manifest(start, end),
        resources_rows=resources,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["resource_samples"] == 2  # only the in-window samples
    assert row["cpu_pct_max"] == 20.0  # 99/98 outside the window ignored
    assert row["mem_bytes_max"] == 2_000_000
    res = row["_resources"][0]
    assert res["samples"] == 2
    assert res["cpu_pct_mean"] == 15.0


def test_controller_metrics_filtered_to_measured_window(tmp_path) -> None:
    start = T0
    end = T0 + timedelta(seconds=600)
    metrics = [
        # Before the window: huge queue depth must not leak into the max.
        [_iso(start - timedelta(seconds=5)), 1, 0, 0, 0, 0, 9999],
        [_iso(start + timedelta(seconds=1)), 2, 0, 0, 0, 0, 5],
        [_iso(start + timedelta(seconds=2)), 3, 0, 0, 0, 0, 7],
        [_iso(end + timedelta(seconds=5)), 4, 0, 0, 0, 0, 8888],
    ]
    run_dir = make_run(
        tmp_path,
        "windowed-metrics",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra=_window_manifest(start, end),
        controller_metrics_rows=metrics,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["controller_metric_samples"] == 2
    assert row["queue_depth_max"] == 7.0


def test_missing_measured_window_aggregates_unfiltered_with_warning(tmp_path) -> None:
    resources = [[_iso(T0), "egw-controller", 12.0, 1024, 1.0]]
    run_dir = make_run(
        tmp_path,
        "no-window",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        resources_rows=resources,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["resource_samples"] == 1
    assert "measured_window_utc" in row["warnings"]


def test_queue_growth_detected_from_controller_metrics_csv(tmp_path) -> None:
    metrics = [
        [_iso(T0 + timedelta(seconds=i)), i, 0, 0, 0, 0, 101 + i]
        for i in range(61)
    ]
    run_dir = make_run(
        tmp_path,
        "queue-growth",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        controller_metrics_rows=metrics,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["controller_metric_samples"] == 61
    assert row["queue_depth_max"] == 161.0
    assert row["queue_growth_sustained_s"] == 60.0


def test_double_accepted_counted_for_restart_acceptance(tmp_path) -> None:
    # Two accepted events for the SAME message_id: the second is a
    # double-accept (twin patched twice) - claim C12's failure mode.
    run_dir = make_run(
        tmp_path,
        "double-accept",
        sent=[sent_record("m0"), sent_record("m1", 1)],
        events=[
            event_record("m0", "accepted"),
            event_record("m0", "accepted"),
            event_record("m1", "accepted"),
        ],
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["double_accepted"] == 1
    assert row["delivered_unique"] == 2
    assert "repeated accepted event" in row["warnings"]


# ---------------------------------------------------------------------------
# End-to-end analyze on a synthetic raw tree
# ---------------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_analyze_end_to_end_regenerates_processed_outputs(tmp_path, capsys) -> None:
    base = tmp_path / "results"
    mids = [f"m{i}" for i in range(5)]
    resources = [
        ["2026-09-07T10:00:00.000Z", "egw-controller", 12.5, 1_048_576, 1.2],
        ["2026-09-07T10:00:01.000Z", "egw-controller", 25.0, 2_097_152, 2.4],
        ["2026-09-07T10:00:00.000Z", "mosquitto", 1.0, 524_288, 0.5],
    ]
    make_run(
        base,
        "nominal-r01",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=[
            event_record(m, "accepted", latency_ms=lat)
            for m, lat in zip(mids[:4], [10.0, 20.0, 30.0, 40.0])
        ],
        resources_rows=resources,
    )
    # An excluded run: listed in per_run.csv but out of summaries (plan 7.3).
    make_run(
        base,
        "nominal-r02",
        sent=[sent_record("x0")],
        events=[],
        manifest_extra={
            "repetition": 2,
            "exclusion": "proven instrumentation failure: sampler crashed",
        },
    )
    # A stale file in processed/ must disappear (full regeneration).
    (base / "processed").mkdir(parents=True)
    (base / "processed" / "stale.csv").write_text("old\n", "utf-8")

    assert analyze.analyze(base_dir=base) == 0

    assert not (base / "processed" / "stale.csv").exists()
    per_run = _read_csv(base / "processed" / "per_run.csv")
    assert [row["run_id"] for row in per_run] == ["nominal-r01", "nominal-r02"]

    row = per_run[0]
    assert row["condition_id"] == "nominal"
    assert row["sent_valid"] == "5"
    assert row["delivered_unique"] == "4"
    assert row["lost"] == "1"
    assert float(row["delivery_rate"]) == 0.8
    assert float(row["loss_rate"]) == 0.2
    assert float(row["latency_ms_mean"]) == 25.0
    assert float(row["latency_ms_p50"]) == 25.0
    assert float(row["latency_ms_p95"]) == 38.5
    assert row["excluded"] == "false"
    assert float(row["cpu_pct_max"]) == 25.0
    assert row["mem_bytes_max"] == "2097152"

    excluded_row = per_run[1]
    assert excluded_row["excluded"] == "true"
    assert "instrumentation failure" in excluded_row["exclusion_reason"]

    resources_by_run = _read_csv(base / "processed" / "resources_by_run.csv")
    by_container = {r["container"]: r for r in resources_by_run}
    assert by_container["egw-controller"]["samples"] == "2"
    assert float(by_container["egw-controller"]["cpu_pct_mean"]) == 18.75
    assert float(by_container["egw-controller"]["cpu_pct_max"]) == 25.0
    assert by_container["egw-controller"]["mem_bytes_max"] == "2097152"
    assert by_container["mosquitto"]["samples"] == "1"

    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    delivery = [
        r
        for r in summary
        if r["condition_id"] == "nominal" and r["metric"] == "delivery_rate"
    ]
    assert len(delivery) == 1
    # Excluded run is out of the summary: n_runs == 1, CI undefined.
    assert delivery[0]["n_runs"] == "1"
    assert float(delivery[0]["mean"]) == 0.8
    assert delivery[0]["stdev"] == ""
    assert delivery[0]["ci95_lo"] == ""

    saturation = json.loads(
        (base / "processed" / "saturation.json").read_text("utf-8")
    )
    assert saturation["first_saturated_load_msg_s"] is None
    assert saturation["loads"] == []  # no load_sweep runs in this fixture
    assert (base / "figures").is_dir()
    capsys.readouterr()  # notices printed; not asserted


def test_summary_ci_matches_hand_computed_value_across_runs(tmp_path) -> None:
    base = tmp_path / "results"
    # Five nominal runs with delivery rates 1.0, 1.0, 0.8, 0.6, 0.6.
    rates = {"r01": 5, "r02": 5, "r03": 4, "r04": 3, "r05": 3}
    for idx, (suffix, delivered) in enumerate(sorted(rates.items()), start=1):
        mids = [f"m{idx}-{i}" for i in range(5)]
        make_run(
            base,
            f"nominal-{suffix}",
            sent=[sent_record(m, i) for i, m in enumerate(mids)],
            events=[event_record(m, "accepted") for m in mids[:delivered]],
            manifest_extra={"repetition": idx},
        )
    assert analyze.analyze(base_dir=base) == 0
    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    delivery = next(
        r
        for r in summary
        if r["condition_id"] == "nominal" and r["metric"] == "delivery_rate"
    )
    values = [1.0, 1.0, 0.8, 0.6, 0.6]
    mean = statistics.fmean(values)
    stdev = statistics.stdev(values)
    half = 2.776 * stdev / math.sqrt(5)
    assert delivery["n_runs"] == "5"
    assert math.isclose(float(delivery["mean"]), mean, abs_tol=1e-6)
    assert math.isclose(float(delivery["stdev"]), stdev, abs_tol=1e-6)
    assert math.isclose(float(delivery["ci95_lo"]), mean - half, abs_tol=1e-6)
    assert math.isclose(float(delivery["ci95_hi"]), mean + half, abs_tol=1e-6)
    assert math.isclose(float(delivery["median"]), 0.8, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Per-condition acceptance (audit 9.5, claims C10/C11/C12/C14)
# ---------------------------------------------------------------------------


def _acc_row(cid: str, **overrides) -> dict:
    base = {
        "condition_id": cid,
        "validity": "valid",
        "lost": 0,
        "double_accepted": 0,
        "intended_invalid_sent": 0,
        "rejected_intended_invalid": 0,
        "intended_invalid_accepted": 0,
        "delivery_rate": 1.0,
    }
    base.update(overrides)
    return base


def _acc(result: list[dict], cid: str, criterion: str) -> dict:
    return next(
        r
        for r in result
        if r["condition_id"] == cid and r["criterion"] == criterion
    )


def test_acceptance_smoke_sequence_all_complete_zero_lost() -> None:
    rows = [_acc_row("smoke_sequence") for _ in range(10)]
    result = analyze.evaluate_acceptance(rows)
    complete = _acc(result, "smoke_sequence", "all_runs_complete")
    assert complete["passed"] is True
    assert complete["expected_runs"] == 10
    assert complete["claims"] == "C14"
    assert _acc(result, "smoke_sequence", "zero_lost")["passed"] is True


def test_acceptance_smoke_sequence_fails_on_missing_run_or_loss() -> None:
    rows = [_acc_row("smoke_sequence") for _ in range(9)]  # one run missing
    result = analyze.evaluate_acceptance(rows)
    assert _acc(result, "smoke_sequence", "all_runs_complete")["passed"] is False

    rows = [_acc_row("smoke_sequence") for _ in range(10)]
    rows[3]["lost"] = 1
    result = analyze.evaluate_acceptance(rows)
    assert _acc(result, "smoke_sequence", "all_runs_complete")["passed"] is True
    assert _acc(result, "smoke_sequence", "zero_lost")["passed"] is False


def test_acceptance_smoke_sequence_invalid_run_fails_completeness() -> None:
    rows = [_acc_row("smoke_sequence") for _ in range(10)]
    rows[0]["validity"] = "invalid"
    result = analyze.evaluate_acceptance(rows)
    assert _acc(result, "smoke_sequence", "all_runs_complete")["passed"] is False


def test_acceptance_invalid_payload_rejection_criteria() -> None:
    rows = [
        _acc_row(
            "invalid_payload",
            intended_invalid_sent=20,
            rejected_intended_invalid=20,
            delivery_rate=1.0,
        )
        for _ in range(3)
    ]
    result = analyze.evaluate_acceptance(rows)
    rejected = _acc(result, "invalid_payload", "all_intended_invalid_rejected")
    assert rejected["passed"] is True
    assert rejected["claims"] == "C11"
    assert (
        _acc(result, "invalid_payload", "zero_intended_invalid_accepted")["passed"]
        is True
    )
    # The plan 7.3 valid-delivery accounting is reported informationally.
    info = _acc(result, "invalid_payload", "valid_delivery_rate_mean_informational")
    assert info["passed"] is None
    assert info["observed"].startswith("1.0")

    rows[1]["rejected_intended_invalid"] = 19
    rows[1]["intended_invalid_accepted"] = 1
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "invalid_payload", "all_intended_invalid_rejected")["passed"]
        is False
    )
    assert (
        _acc(result, "invalid_payload", "zero_intended_invalid_accepted")["passed"]
        is False
    )


def test_acceptance_dropout_reconnect_tolerates_buffered_redelivery() -> None:
    # Buffered messages confirmed within the window are simply not lost;
    # acceptance = zero lost + zero double-accepted (module docstring).
    rows = [_acc_row("dropout_reconnect") for _ in range(3)]
    result = analyze.evaluate_acceptance(rows)
    zero_lost = _acc(result, "dropout_reconnect", "zero_lost_within_window")
    assert zero_lost["passed"] is True
    assert zero_lost["claims"] == "C10"
    assert (
        _acc(result, "dropout_reconnect", "zero_double_accepted")["passed"] is True
    )

    rows[0]["lost"] = 2
    rows[2]["double_accepted"] = 1
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "dropout_reconnect", "zero_lost_within_window")["passed"]
        is False
    )
    assert (
        _acc(result, "dropout_reconnect", "zero_double_accepted")["passed"] is False
    )


def test_acceptance_controller_restart_criteria() -> None:
    rows = [_acc_row("controller_restart") for _ in range(3)]
    result = analyze.evaluate_acceptance(rows)
    across = _acc(result, "controller_restart", "delivery_across_restart_zero_lost")
    assert across["passed"] is True
    assert across["claims"] == "C12"
    assert (
        _acc(result, "controller_restart", "zero_double_accepted")["passed"] is True
    )

    rows[1]["double_accepted"] = 3
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "controller_restart", "zero_double_accepted")["passed"] is False
    )


def test_acceptance_without_runs_is_not_evaluable() -> None:
    result = analyze.evaluate_acceptance([])
    for row in result:
        assert row["passed"] is None
        assert row["n_runs"] == 0


# ---------------------------------------------------------------------------
# External conditions analyzed by the same script (audit 9.6, claim C15)
# ---------------------------------------------------------------------------


def make_external_run(
    base: Path,
    run_id: str,
    condition: str,
    samples: list[dict],
    exclusion=None,
) -> Path:
    run_dir = base / "raw" / run_id
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "condition_id": condition,
        "runner": "external",
        "exclusion": exclusion,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", "utf-8")
    timings = {
        "run_id": run_id,
        "condition": condition,
        "samples": samples,
        "method": "fixture",
        "notes": None,
    }
    (run_dir / "timings.json").write_text(json.dumps(timings) + "\n", "utf-8")
    return run_dir


def test_analyze_summarizes_external_cold_start_durations(tmp_path, capsys) -> None:
    base = tmp_path / "results"
    durations = [30.0, 40.0, 50.0]
    for i, duration in enumerate(durations, start=1):
        make_external_run(
            base,
            f"cold_start-r{i:02d}",
            "cold_start",
            [
                {
                    "label": f"cold_start-r{i:02d}",
                    "started_utc": "2026-09-07T10:00:00Z",
                    "ended_utc": "2026-09-07T10:01:00Z",
                    "duration_s": duration,
                }
            ],
        )
    assert analyze.analyze(base_dir=base) == 0
    capsys.readouterr()
    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    row = next(
        r
        for r in summary
        if r["condition_id"] == "cold_start" and r["metric"] == "duration_s"
    )
    assert row["n_runs"] == "3"
    assert float(row["mean"]) == 40.0
    assert float(row["min"]) == 30.0
    assert float(row["max"]) == 50.0
    # mean/sd/CI95 per the task: stdev = 10, half = t(2)=4.303 * 10/sqrt(3)
    expected_half = 4.303 * 10.0 / math.sqrt(3)
    assert math.isclose(float(row["ci95_lo"]), 40.0 - expected_half, abs_tol=1e-4)
    assert math.isclose(float(row["ci95_hi"]), 40.0 + expected_half, abs_tol=1e-4)
    # Per-sample listing regenerated too.
    listing = _read_csv(base / "processed" / "external_runs.csv")
    assert len(listing) == 3
    assert {r["condition_id"] for r in listing} == {"cold_start"}


def test_analyze_lists_qemu_boots_pass_fail_without_stats(tmp_path, capsys) -> None:
    base = tmp_path / "results"
    make_external_run(
        base,
        "qemu_boot-r01",
        "qemu_boots",
        [
            {"label": "boot1", "duration_s": 12.0, "outcome": "pass"},
            {"label": "boot2", "duration_s": 900.0, "outcome": "fail"},
            {"label": "boot3"},
        ],
    )
    assert analyze.analyze(base_dir=base) == 0
    capsys.readouterr()
    listing = _read_csv(base / "processed" / "external_runs.csv")
    outcomes = {r["sample_label"]: r["outcome"] for r in listing}
    assert outcomes == {"boot1": "pass", "boot2": "fail", "boot3": "unspecified"}
    # Plan 5.1: NO performance statistics from QEMU - no summary row at all.
    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    assert not any(r["condition_id"] == "qemu_boots" for r in summary)


def test_excluded_external_run_out_of_duration_summary(tmp_path, capsys) -> None:
    base = tmp_path / "results"
    make_external_run(
        base,
        "twin_creation-r01",
        "twin_creation",
        [{"label": "t1", "duration_s": 5.0}],
    )
    make_external_run(
        base,
        "twin_creation-r02",
        "twin_creation",
        [{"label": "t2", "duration_s": 500.0}],
        exclusion="proven instrumentation failure",
    )
    assert analyze.analyze(base_dir=base) == 0
    capsys.readouterr()
    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    row = next(
        r
        for r in summary
        if r["condition_id"] == "twin_creation" and r["metric"] == "duration_s"
    )
    assert row["n_runs"] == "1"
    assert float(row["mean"]) == 5.0


def test_soak_summary_is_descriptive_without_ci(tmp_path) -> None:
    base = tmp_path / "results"
    mids = [f"m{i}" for i in range(4)]
    make_run(
        base,
        "soak-r01",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=[event_record(m, "accepted") for m in mids],
        manifest_extra={
            "condition_id": "soak",
            "scenario": "soak",
            "duration_s": 86_400,
        },
    )
    assert analyze.analyze(base_dir=base) == 0
    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    soak_rows = [r for r in summary if r["condition_id"] == "soak"]
    assert soak_rows, "soak must appear in the summary"
    for row in soak_rows:
        # Plan 7.3: soak is analyzed descriptively, no CI of its own.
        assert row["ci95_lo"] == "" and row["ci95_hi"] == "" and row["stdev"] == ""
        assert row["mean"] != "" and row["median"] != ""
