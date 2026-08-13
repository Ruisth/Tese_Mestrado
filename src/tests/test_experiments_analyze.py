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
from egw_experiments.checksums import write_sha256sums
from egw_experiments.plan_gen import generate_campaign_plan

# Confirmation-deadline rule (CONTRACTS 5, sprint P5): the deadline lives
# in the CONTROLLER's clock domain and is taken from the manifest whenever
# confirmation_deadline_clock_domain == "controller" — the harness reads
# the controller's confirmation marker (GET /metrics monotonic_ns) right
# after the measured process exits and adds the window. Runs without that
# marker fall back to the LEGACY event-derived deadline
# (max received_monotonic_ns + window), which is circular. Every default
# fixture event uses MAX_RECEIVED_NS, so DEADLINE_NS is both the standard
# fixture's controller-domain deadline and its event-derived one.
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
    sim_totals: dict | None = None,
    seal: bool = True,
) -> Path:
    """Build one synthetic raw run directory.

    ``seal`` writes SHA256SUMS over the finished directory, exactly as
    ``run``/``collect`` do: since sprint P5 the analysis refuses to
    aggregate unsealed TIMED runs (report 5.4), so a fixture that is not
    sealed is a fixture of an unverifiable run.
    """
    run_dir = base / "raw" / run_id
    run_dir.mkdir(parents=True)
    if sim_totals is not None:
        # The simulator's own manifest (egw_simulator.runner) under the
        # harness's logs/simulator/ output dir: carries the run totals the
        # C10 acceptance verifies (dropout_disconnects, buffered_dropout).
        sim_dir = run_dir / "logs" / "simulator" / run_id
        sim_dir.mkdir(parents=True)
        (sim_dir / "manifest.json").write_text(
            json.dumps({"run_id": run_id, "totals": sim_totals}) + "\n", "utf-8"
        )
    manifest = {
        "run_id": run_id,
        "condition_id": "nominal",
        "scenario": "nominal",
        "rate_msg_s": 11.2,
        "duration_s": 600,
        "seed": 1,
        "repetition": 1,
        "confirmation_window_s": WINDOW_S,
        # Authoritative controller-domain marker (sprint P5): captured from
        # GET /metrics right after the measured process exited.
        "confirmation_deadline_monotonic_ns": DEADLINE_NS,
        "confirmation_deadline_clock_domain": "controller",
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
    if seal:
        write_sha256sums(run_dir)
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
# Confirmation deadline: controller marker vs legacy event-derived
# (report 5.2 / CONTRACTS 5, sprint P5)
# ---------------------------------------------------------------------------


def test_late_message_past_controller_deadline_is_lost_even_when_it_is_the_max_event(
    tmp_path,
) -> None:
    """REGRESSION (report 5.2, deadline circularity).

    The controller-domain deadline D comes from the manifest (the harness
    read the controller's confirmation marker after the measured process
    exited). A message whose ditto_ack lands AFTER D must count as LOST
    even though its own received_monotonic_ns is the maximum over the
    run's events. Under the old event-derived rule that same message
    pushed the deadline forward by its own lateness and was counted as
    delivered — the bug this test pins down.
    """
    marker_ns = 5_000_000_000  # end of the measured run, controller clock
    deadline_ns = marker_ns + WINDOW_NS
    events = [
        # Ordinary in-window confirmation.
        event_record(
            "m0", "accepted", received_ns=1_000_000, ack_ns=marker_ns + 1_000
        ),
        # The straggler: received last (max received_monotonic_ns of the
        # run) and confirmed 1 ns past the controller-domain deadline.
        event_record(
            "m1",
            "accepted",
            received_ns=deadline_ns - 1,
            ack_ns=deadline_ns + 1,
        ),
    ]
    run_dir = make_run(
        tmp_path,
        "deadline-circularity",
        sent=[sent_record("m0"), sent_record("m1", 1)],
        events=events,
        manifest_extra={
            "controller_monotonic_at_run_end_ns": marker_ns,
            "confirmation_deadline_monotonic_ns": deadline_ns,
            "confirmation_deadline_clock_domain": "controller",
        },
    )
    row = analyze.compute_run_metrics(run_dir)

    assert row["confirmation_deadline_source"] == "controller-marker"
    assert row["delivered_unique"] == 1
    assert row["late_confirmations"] == 1
    assert row["lost"] == 1
    assert row["delivery_rate"] == 0.5
    # The authoritative path is not legacy and raises no legacy warning.
    assert "LEGACY/UNVERIFIABLE" not in row["warnings"]

    # Control: the SAME evidence under the legacy event-derived rule
    # rescues the straggler, because it extends its own deadline.
    legacy_dir = make_run(
        tmp_path,
        "deadline-circularity-legacy",
        sent=[sent_record("m0"), sent_record("m1", 1)],
        events=events,
        manifest_extra={
            "confirmation_deadline_monotonic_ns": None,
            "confirmation_deadline_clock_domain": None,
        },
    )
    legacy = analyze.compute_run_metrics(legacy_dir)
    assert legacy["confirmation_deadline_source"] == "event-derived-legacy"
    assert legacy["delivered_unique"] == 2
    assert legacy["lost"] == 0
    assert "LEGACY/UNVERIFIABLE" in legacy["warnings"]
    assert "circular" in legacy["warnings"]


def test_controller_marker_deadline_boundary_is_inclusive(tmp_path) -> None:
    """An ack exactly ON the controller-domain deadline is in-window; one
    nanosecond later is late. The 60 s rule itself is unchanged."""
    marker_ns = 9_000_000_000
    deadline_ns = marker_ns + WINDOW_NS
    events = [
        event_record("m0", "accepted", received_ns=10, ack_ns=deadline_ns),
        event_record("m1", "accepted", received_ns=20, ack_ns=deadline_ns + 1),
    ]
    run_dir = make_run(
        tmp_path,
        "deadline-boundary",
        sent=[sent_record("m0"), sent_record("m1", 1)],
        events=events,
        manifest_extra={
            "confirmation_deadline_monotonic_ns": deadline_ns,
            "confirmation_deadline_clock_domain": "controller",
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["delivered_unique"] == 1
    assert row["late_confirmations"] == 1
    assert row["lost"] == 1


def test_legacy_event_derived_deadline_in_window_vs_late(tmp_path) -> None:
    """Without a controller marker the deadline is max(received) + window
    and the run is flagged LEGACY/UNVERIFIABLE."""
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
        manifest_extra={
            "confirmation_deadline_monotonic_ns": None,
            "confirmation_deadline_clock_domain": "unavailable",
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["delivered_unique"] == 2
    assert row["late_confirmations"] == 1
    assert row["lost"] == 1
    assert row["confirmation_deadline_source"] == "event-derived-legacy"
    assert "LEGACY/UNVERIFIABLE" in row["warnings"]
    assert "'unavailable'" in row["warnings"]


def test_zero_events_fall_back_to_manifest_deadline(tmp_path) -> None:
    """With zero controller events and a non-controller clock domain, the
    manifest deadline is the last-resort fallback and is flagged."""
    run_dir = make_run(
        tmp_path,
        "no-events",
        sent=[sent_record("m0"), sent_record("m1", 1)],
        events=[],
        manifest_extra={"confirmation_deadline_clock_domain": "harness-host"},
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["delivered_unique"] == 0
    assert row["lost"] == 2
    assert row["confirmation_deadline_source"] == "manifest-other-domain-legacy"
    assert "falling back" in row["warnings"]
    assert "harness-host" in row["warnings"]


def test_harness_host_deadline_is_ignored_in_favour_of_event_derived(
    tmp_path,
) -> None:
    """A deadline captured on the harness host (which runs OFF the ARM VM,
    plan 5.1) is NOT in the controller's clock domain: it must never be
    trusted, however plausible it looks."""
    implausible = 999_000_000_000_000_000
    events = [
        event_record("m0", "accepted"),  # inside the event-derived window
        # Late per the event-derived deadline although far below the
        # harness-host manifest value.
        event_record("m1", "accepted", ack_ns=DEADLINE_NS + 1),
    ]
    run_dir = make_run(
        tmp_path,
        "harness-host-deadline",
        sent=[sent_record("m0"), sent_record("m1", 1)],
        events=events,
        manifest_extra={
            "confirmation_deadline_monotonic_ns": implausible,
            "confirmation_deadline_clock_domain": "harness-host",
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["confirmation_deadline_source"] == "event-derived-legacy"
    assert "LEGACY/UNVERIFIABLE" in row["warnings"]
    assert row["late_confirmations"] == 1
    assert row["delivered_unique"] == 1
    assert row["lost"] == 1


def test_controller_marker_before_last_received_event_is_flagged(tmp_path) -> None:
    """A 'controller' deadline that precedes the last received event is a
    mislabelled clock domain: used as recorded, but loudly flagged."""
    events = [event_record("m0", "accepted", received_ns=10**12, ack_ns=10**12 + 5)]
    run_dir = make_run(
        tmp_path,
        "suspect-marker",
        sent=[sent_record("m0")],
        events=events,
        manifest_extra={
            "confirmation_deadline_monotonic_ns": 1_000,
            "confirmation_deadline_clock_domain": "controller",
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["confirmation_deadline_source"] == "controller-marker"
    assert "IMPLAUSIBLE controller confirmation marker" in row["warnings"]
    assert row["late_confirmations"] == 1
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
        manifest_extra={
            "confirmation_deadline_monotonic_ns": None,
            "confirmation_deadline_clock_domain": None,
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["confirmation_deadline_source"] == "event-derived-legacy"
    assert "LEGACY/UNVERIFIABLE" in row["warnings"]


def test_run_without_any_deadline_source_warns_and_counts_all_in_window(
    tmp_path,
) -> None:
    """No controller marker, no events with received_monotonic_ns and no
    manifest deadline: nothing can bound the window, which must be said
    out loud rather than silently accepted."""
    event = event_record("m0", "accepted")
    event["received_monotonic_ns"] = None
    run_dir = make_run(
        tmp_path,
        "no-deadline-at-all",
        sent=[sent_record("m0")],
        events=[event],
        manifest_extra={
            "confirmation_deadline_monotonic_ns": None,
            "confirmation_deadline_clock_domain": None,
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["confirmation_deadline_source"] == "none"
    assert "no confirmation deadline available" in row["warnings"]
    assert row["delivered_unique"] == 1


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


def _cpu_samples_at(start: datetime, count: int, cpu_pct: float) -> list[dict]:
    return [
        {"ts": start + timedelta(seconds=i), "cpu_pct": cpu_pct, "mem_bytes": 1}
        for i in range(count)
    ]


def test_sustained_cpu_gap_over_cadence_cap_breaks_the_streak() -> None:
    """Cadence cap (work order P1b): a sampling gap > MAX_SAMPLE_GAP_S
    breaks the sustained window — two samples far apart can never fake a
    sustained minute."""
    start = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)
    # 30 samples at 1 Hz, a 10 s hole, then 40 more: without the cap the
    # naive span would be 79 s; with the cap the best streak is 39 s.
    samples = _cpu_samples_at(start, 30, 95.0)
    samples += _cpu_samples_at(start + timedelta(seconds=40), 40, 95.0)
    assert analyze.sustained_cpu_seconds(samples) == 39.0

    # Degenerate case E5: two above-threshold samples 10 minutes apart must
    # not count as a sustained 10 minutes.
    sparse = [
        {"ts": start, "cpu_pct": 95.0},
        {"ts": start + timedelta(seconds=600), "cpu_pct": 95.0},
    ]
    assert analyze.sustained_cpu_seconds(sparse) == 0.0

    # Gaps up to the cap (5 s) do NOT break the streak.
    tolerated = [
        {"ts": start + timedelta(seconds=i * 5), "cpu_pct": 95.0}
        for i in range(13)
    ]
    assert analyze.sustained_cpu_seconds(tolerated) == 60.0


def test_queue_growth_gap_over_cadence_cap_breaks_the_window() -> None:
    """Cadence cap (work order P1b) for the queue-growth detector: growth
    cannot be claimed continuous across a > MAX_SAMPLE_GAP_S hole."""
    depths_a = [101.0 + i for i in range(31)]  # 30 s of strict growth
    samples = _queue_samples(depths_a)
    # 10 s hole, then 40 more strictly increasing samples (still above the
    # floor and above the previous depth).
    start_b = T0 + timedelta(seconds=40)
    depths_b = [200.0 + i for i in range(41)]
    samples += [
        {"ts": start_b + timedelta(seconds=i), "queue_depth": depth}
        for i, depth in enumerate(depths_b)
    ]
    span = analyze.queue_growth_sustained_seconds(samples)
    assert span == 40.0  # the post-gap window only; never 70+ s across it


def _sweep_row(
    rate: float,
    loss: float,
    p95: float,
    host_sustained_s: float = 0.0,
    queue_sustained_s: float = 0.0,
    **overrides,
) -> dict:
    """One valid, fully instrumented load-sweep run row (P1b sufficiency)."""
    row = {
        "run_id": f"load_sweep-{rate}-r",
        "condition_id": "load_sweep",
        "rate_msg_s": rate,
        "validity": "valid",
        "excluded": False,
        "loss_rate": loss,
        "latency_ms_p95": p95,
        "host_cpu_sustained_gt090_s": host_sustained_s,
        "queue_growth_sustained_s": queue_sustained_s,
        "resources_coverage_pct": 100.0,
        "resources_head_gap_s": 0.0,
        "resources_distinct_instants": 301,
        "resources_per_container_sufficient": True,
        # Controller metrics are mandated instrumentation for the sweep:
        # since sprint P5 their coverage/head gap/instant count must be
        # sufficient too, otherwise the load is insufficient-evidence.
        "metrics_coverage_pct": 100.0,
        "metrics_head_gap_s": 0.0,
        "metrics_distinct_instants": 301,
    }
    row.update(overrides)
    return row


def _sweep_load(rate: float, loss: float, p95: float, n: int = 10, **kw) -> list[dict]:
    """A complete load: n (default: the planned 10) identical valid runs."""
    return [_sweep_row(rate, loss, p95, **kw) for _ in range(n)]


def _load_at(result: dict, rate: float) -> dict:
    return next(load for load in result["loads"] if load["rate_msg_s"] == rate)


def test_saturation_triggers_on_loss_criterion() -> None:
    rows = _sweep_load(10.0, 0.0, 100.0)
    rows += _sweep_load(50.0, 0.02, 100.0)  # mean loss 2% > 1%
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    assert _load_at(result, 10.0)["saturated"] is False
    assert _load_at(result, 10.0)["verdict"] == "not-saturated"
    assert _load_at(result, 50.0)["triggered"]["loss_rate"] is True
    assert _load_at(result, 50.0)["triggered"]["p95_latency"] is False
    assert _load_at(result, 50.0)["verdict"] == "saturated"


def test_saturation_triggers_on_p95_criterion() -> None:
    rows = _sweep_load(10.0, 0.0, 200.0)
    rows += _sweep_load(50.0, 0.0, 1500.0)  # mean p95 > 1000 ms
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    assert _load_at(result, 50.0)["triggered"]["p95_latency"] is True
    assert _load_at(result, 50.0)["triggered"]["loss_rate"] is False


def test_saturation_triggers_on_sustained_host_cpu_criterion() -> None:
    # Audit 9.7: the CPU criterion is HOST-LEVEL (normalized by nproc),
    # not the raw per-container docker-stats percentage.
    rows = _sweep_load(10.0, 0.0, 100.0)
    rows += _sweep_load(50.0, 0.0, 100.0, host_sustained_s=65.0)
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    assert _load_at(result, 50.0)["triggered"]["host_cpu_sustained"] is True


def test_saturation_cpu_fraction_below_half_is_not_saturated() -> None:
    # Decision rule: the CPU criterion holds only when at least HALF of the
    # runs at a load show a sustained >= 60 s event. 4 of 10 < 0.5.
    rows = _sweep_load(50.0, 0.0, 100.0, n=4, host_sustained_s=65.0)
    rows += _sweep_load(50.0, 0.0, 100.0, n=6)
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] is None
    load = _load_at(result, 50.0)
    assert load["n_runs"] == 10
    assert load["host_cpu_sustained_run_fraction"] < 0.5
    assert load["triggered"]["host_cpu_sustained"] is False
    assert load["saturated"] is False
    assert load["verdict"] == "not-saturated"


def test_saturation_cpu_fraction_at_least_half_is_saturated() -> None:
    # 5 of 10 runs with sustained >= 60 s: fraction >= 0.5, criterion holds.
    rows = _sweep_load(50.0, 0.0, 100.0, n=5, host_sustained_s=65.0)
    rows += _sweep_load(50.0, 0.0, 100.0, n=5)
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    load = _load_at(result, 50.0)
    assert load["triggered"]["host_cpu_sustained"] is True
    assert load["saturated"] is True
    assert load["verdict"] == "saturated"


def test_saturation_triggers_on_queue_growth_criterion() -> None:
    # Audit 9.7: queue growth is measured (controller_metrics.csv), no TODO.
    rows = _sweep_load(10.0, 0.0, 100.0)
    rows += _sweep_load(50.0, 0.0, 100.0, n=6, queue_sustained_s=75.0)
    rows += _sweep_load(50.0, 0.0, 100.0, n=4, queue_sustained_s=0.0)
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] == 50.0
    assert _load_at(result, 50.0)["triggered"]["queue_growth"] is True
    assert _load_at(result, 50.0)["queue_growth_run_fraction"] == 0.6
    assert _load_at(result, 10.0)["triggered"]["queue_growth"] is False


def test_saturation_criteria_not_evaluable_without_instrumentation() -> None:
    # Runs without nproc/controller_metrics carry None; the criterion is
    # None (not evaluable), never silently False, and cannot saturate. The
    # load's verdict is insufficient-evidence (P1b), never not-saturated.
    rows = [
        _sweep_row(
            50.0,
            0.0,
            100.0,
            host_sustained_s=None,
            queue_sustained_s=None,
            resources_coverage_pct=None,
        )
        for _ in range(10)
    ]
    result = analyze.detect_saturation(rows)
    load = _load_at(result, 50.0)
    assert load["triggered"]["host_cpu_sustained"] is None
    assert load["triggered"]["queue_growth"] is None
    assert load["saturated"] is False
    assert load["verdict"] == "insufficient-evidence"


def test_saturation_not_triggered_below_thresholds() -> None:
    rows = _sweep_load(10.0, 0.0, 100.0)
    # thresholds are strict (>) for loss/p95; sustained windows below
    # 60 s never count.
    rows += _sweep_load(
        50.0, 0.01, 1000.0, host_sustained_s=59.0, queue_sustained_s=59.0
    )
    result = analyze.detect_saturation(rows)
    assert result["first_saturated_load_msg_s"] is None
    assert all(not load["saturated"] for load in result["loads"])
    assert _load_at(result, 10.0)["verdict"] == "not-saturated"
    assert _load_at(result, 50.0)["verdict"] == "not-saturated"
    # The queue-growth rule is now documented and evaluated (audit 9.7)
    # and explicitly marked pending advisor sign-off before exp-v1 (R23).
    criteria = result["criteria"]
    assert criteria["queue_depth_floor"] == 100
    assert criteria["queue_growth_sustain_s"] == 60
    assert criteria["host_cpu_utilization_gt"] == 0.90
    assert criteria["run_fraction_gte"] == 0.5
    assert criteria["max_sample_gap_s"] == 5.0
    assert criteria["expected_runs_per_load"] == 10
    assert criteria["min_resource_coverage_pct"] == 90.0
    assert "PENDING ADVISOR SIGN-OFF" in result["pending_advisor_signoff"]
    assert "exp-v1" in result["pending_advisor_signoff"]


# ---------------------------------------------------------------------------
# Saturation evidence sufficiency (work order P1b)
# ---------------------------------------------------------------------------


def test_saturation_planned_loads_without_runs_are_insufficient_evidence() -> None:
    # Every PLANNED sweep rate is listed even with zero runs, with verdict
    # insufficient-evidence — an absent load can never read as a decided one.
    result = analyze.detect_saturation([])
    rates = [load["rate_msg_s"] for load in result["loads"]]
    assert rates == [10.0, 50.0, 100.0, 250.0]
    for load in result["loads"]:
        assert load["n_runs"] == 0
        assert load["verdict"] == "insufficient-evidence"
        assert "0/10 valid runs" in load["insufficient_evidence_detail"][0]
    assert result["first_saturated_load_msg_s"] is None


def test_saturation_nine_of_ten_valid_runs_is_insufficient_evidence() -> None:
    # 9/10 valid runs: even a clear threshold crossing must not decide the
    # load from a subset (work order P1b).
    rows = _sweep_load(50.0, 0.05, 100.0, n=9)
    result = analyze.detect_saturation(rows)
    load = _load_at(result, 50.0)
    assert load["triggered"]["loss_rate"] is True  # threshold logic intact
    assert load["saturated"] is True
    assert load["verdict"] == "insufficient-evidence"
    assert any(
        "9/10 valid runs" in detail
        for detail in load["insufficient_evidence_detail"]
    )
    assert result["first_saturated_load_msg_s"] is None


def test_saturation_run_below_resource_coverage_is_insufficient_evidence() -> None:
    # 10/10 runs but one with resources covering only half of the measured
    # window: the load cannot be decided (documented 90% minimum).
    rows = _sweep_load(50.0, 0.0, 100.0, n=9)
    rows += _sweep_load(
        50.0, 0.0, 100.0, n=1, resources_coverage_pct=50.0
    )
    result = analyze.detect_saturation(rows)
    load = _load_at(result, 50.0)
    assert load["verdict"] == "insufficient-evidence"
    assert any(
        "resources coverage 50.0% below the 90% minimum" in detail
        for detail in load["insufficient_evidence_detail"]
    )


def test_saturation_rejects_sparse_per_container_resource_evidence() -> None:
    rows = _sweep_load(50.0, 0.0, 100.0, n=9)
    rows += _sweep_load(
        50.0,
        0.0,
        100.0,
        n=1,
        resources_per_container_sufficient=False,
        host_sustained_s=None,
    )

    load = _load_at(analyze.detect_saturation(rows), 50.0)

    assert load["verdict"] == "insufficient-evidence"
    assert any(
        "per-container resource series" in detail
        for detail in load["insufficient_evidence_detail"]
    )


def test_saturation_run_without_metrics_is_insufficient_not_unsaturated() -> None:
    # A run without controller metrics makes the load insufficient-evidence
    # (queue-growth criterion not evaluable), never 'not-saturated'.
    rows = _sweep_load(50.0, 0.0, 100.0, n=9)
    rows += _sweep_load(50.0, 0.0, 100.0, n=1, queue_sustained_s=None)
    result = analyze.detect_saturation(rows)
    load = _load_at(result, 50.0)
    assert load["verdict"] == "insufficient-evidence"
    assert any(
        "controller metrics missing" in detail
        for detail in load["insufficient_evidence_detail"]
    )


def test_saturation_invalid_and_excluded_sweep_rows_are_refiltered() -> None:
    # Defensive re-filter: rows with validity != 'valid' or excluded True
    # never enter the saturation evaluation even if a caller passes them.
    rows = _sweep_load(50.0, 0.0, 100.0)
    rows += [_sweep_row(50.0, 0.9, 100.0, validity="invalid")]
    rows += [_sweep_row(50.0, 0.9, 100.0, excluded=True)]
    result = analyze.detect_saturation(rows)
    load = _load_at(result, 50.0)
    assert load["n_runs"] == 10
    assert load["triggered"]["loss_rate"] is False
    assert load["verdict"] == "not-saturated"


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
# Sampling coverage, cadence columns and manifest evidence (work order P1b)
# ---------------------------------------------------------------------------


def test_sampling_stats_coverage_and_gaps() -> None:
    window = (T0, T0 + timedelta(seconds=600))
    # Perfect 1 Hz series: 100% coverage, 1 s interior gaps, no tail gap.
    full = [T0 + timedelta(seconds=i) for i in range(601)]
    stats = analyze.sampling_stats(full, window)
    assert stats["coverage_pct"] == 100.0
    assert stats["max_gap_s"] == 1.0
    assert stats["head_gap_s"] == 0.0
    assert stats["tail_gap_s"] == 0.0

    # 100 s hole: coverage drops by (100 - 5) s; interior max gap 100 s.
    holed = [T0 + timedelta(seconds=i) for i in range(101)]
    holed += [T0 + timedelta(seconds=i) for i in range(200, 601)]
    stats = analyze.sampling_stats(holed, window)
    assert math.isclose(stats["coverage_pct"], 100.0 * 505 / 600, abs_tol=1e-9)
    assert stats["max_gap_s"] == 100.0
    assert stats["tail_gap_s"] == 0.0

    # Truncated tail: last sample 60 s before the window end; a sample
    # covers at most MAX_SAMPLE_GAP_S (5 s) forward.
    truncated = [T0 + timedelta(seconds=i) for i in range(541)]
    stats = analyze.sampling_stats(truncated, window)
    assert math.isclose(stats["coverage_pct"], 100.0 * 545 / 600, abs_tol=1e-9)
    assert stats["tail_gap_s"] == 60.0

    # HEAD GAP (report 5.4): a series that only starts sampling 300 s into
    # the window is not continuous evidence, and the interior max gap
    # cannot show it (here it stays 1 s).
    late_start = [T0 + timedelta(seconds=i) for i in range(300, 601)]
    stats = analyze.sampling_stats(late_start, window)
    assert stats["head_gap_s"] == 300.0
    assert stats["max_gap_s"] == 1.0
    assert math.isclose(stats["coverage_pct"], 100.0 * 300 / 600, abs_tol=1e-9)

    # No usable window -> stats are None (cannot be computed).
    stats = analyze.sampling_stats(full, None)
    assert stats == {
        "coverage_pct": None,
        "max_gap_s": None,
        "head_gap_s": None,
        "tail_gap_s": None,
    }

    # Empty in-window series: 0% coverage, gaps not measurable.
    stats = analyze.sampling_stats([], window)
    assert stats["coverage_pct"] == 0.0
    assert stats["max_gap_s"] is None and stats["tail_gap_s"] is None


def test_per_run_coverage_columns_computed_from_csvs(tmp_path) -> None:
    """E4/E5: per_run rows expose resources/metrics coverage of the measured
    window plus max/tail gaps (work order P1b columns)."""
    start = T0
    end = T0 + timedelta(seconds=600)
    resources = []
    for i in range(0, 101):  # 1 Hz, then a 100 s hole, then 1 Hz again
        resources.append([_iso(start + timedelta(seconds=i)), "egw-controller", 10.0, 1024, 1.0])
    for i in range(200, 601):
        resources.append([_iso(start + timedelta(seconds=i)), "egw-controller", 10.0, 1024, 1.0])
    metrics = [
        [_iso(start + timedelta(seconds=i)), i, 0, 0, 0, 0, 5]
        for i in range(0, 541)  # stops 60 s before the window end
    ]
    run_dir = make_run(
        tmp_path,
        "coverage-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra=_window_manifest(start, end),
        resources_rows=resources,
        controller_metrics_rows=metrics,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["measured_window_s"] == 600.0
    assert math.isclose(row["resources_coverage_pct"], 100.0 * 505 / 600, abs_tol=1e-9)
    assert row["resources_max_gap_s"] == 100.0
    assert math.isclose(row["metrics_coverage_pct"], 100.0 * 545 / 600, abs_tol=1e-9)
    assert row["metrics_max_gap_s"] == 1.0
    assert row["metrics_tail_gap_s"] == 60.0
    # The mandated columns are part of the per_run.csv schema.
    for column in ("resources_coverage_pct", "metrics_coverage_pct"):
        assert column in analyze.PER_RUN_COLUMNS


def test_resources_by_run_marks_sparse_container_series_insufficient(
    tmp_path,
) -> None:
    start = T0
    end = T0 + timedelta(seconds=40)
    resources = []
    for i in range(41):
        resources.append(
            [_iso(start + timedelta(seconds=i)), "egw-controller", 10.0, 1024, 1.0]
        )
        if i < 5:
            resources.append(
                [_iso(start + timedelta(seconds=i)), "ditto", 8.0, 2048, 2.0]
            )
    run_dir = make_run(
        tmp_path,
        "sparse-container-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra=_window_manifest(start, end),
        resources_rows=resources,
        sut_env={"nproc": 4},
    )

    row = analyze.compute_run_metrics(run_dir)
    by_container = {item["container"]: item for item in row["_resources"]}

    assert by_container["egw-controller"]["coverage_sufficient"] is True
    assert by_container["ditto"]["coverage_sufficient"] is False
    assert row["resources_per_container_sufficient"] is False
    assert by_container["ditto"]["coverage_pct"] < 90.0
    assert "container 'ditto' has insufficient" in row["warnings"]
    assert "host-level CPU aggregates are audit-only" in row["warnings"]


def test_scientific_resource_consumers_exclude_insufficient_container_rows() -> None:
    row = {
        "_resources": [
            {
                "container": "egw-controller",
                "cpu_pct_mean": 10.0,
                "coverage_sufficient": True,
            },
            {
                "container": "ditto",
                "cpu_pct_mean": 99.0,
                "coverage_sufficient": False,
            },
            {
                "container": "legacy-without-admissibility-flag",
                "cpu_pct_mean": 50.0,
            },
        ]
    }

    assert [
        item["container"] for item in analyze.admissible_resource_rows(row)
    ] == ["egw-controller"]


def test_metrics_accepted_delta_and_events_accepted_total(tmp_path) -> None:
    """Reconciliation inputs (work order P1b): the raw accepted-event count
    and the cumulative accepted-counter delta over the measured window."""
    start = T0
    end = T0 + timedelta(seconds=600)
    mids = [f"m{i}" for i in range(5)]
    metrics = [
        [_iso(start + timedelta(seconds=0)), 100, 0, 0, 0, 0, 5],
        [_iso(start + timedelta(seconds=1)), 103, 0, 0, 0, 0, 5],
        [_iso(start + timedelta(seconds=2)), 105, 0, 0, 0, 0, 5],
    ]
    run_dir = make_run(
        tmp_path,
        "reconcile-run",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=[event_record(m, "accepted") for m in mids]
        + [event_record(mids[0], "duplicate")],
        manifest_extra=_window_manifest(start, end),
        controller_metrics_rows=metrics,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["events_accepted_total"] == 5  # 'duplicate' outcomes excluded
    assert row["metrics_accepted_delta"] == 5.0  # 105 - 100

    # Without controller_metrics.csv the delta is None (criterion fails).
    bare = make_run(
        tmp_path,
        "no-metrics-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    bare_row = analyze.compute_run_metrics(bare)
    assert bare_row["metrics_accepted_delta"] is None


def test_simulator_manifest_totals_read_for_dropout_runs(tmp_path) -> None:
    """E2: dropout_disconnects/buffered_dropout come from the SIMULATOR's
    manifest under logs/simulator/; missing totals warn on dropout runs."""
    run_dir = make_run(
        tmp_path,
        "dropout_reconnect-r01",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "condition_id": "dropout_reconnect",
            "scenario": "dropout-reconnect",
        },
        sim_totals={
            "sent": 100,
            "intended_invalid": 0,
            "buffered_dropout": 17,
            "dropout_disconnects": 3,
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["dropout_disconnects"] == 3
    assert row["buffered_dropout"] == 17
    assert "totals missing" not in row["warnings"]

    # A dropout run WITHOUT the simulator manifest: values None + warning.
    bare = make_run(
        tmp_path,
        "dropout_reconnect-r02",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "condition_id": "dropout_reconnect",
            "scenario": "dropout-reconnect",
            "repetition": 2,
        },
    )
    bare_row = analyze.compute_run_metrics(bare)
    assert bare_row["dropout_disconnects"] is None
    assert bare_row["buffered_dropout"] is None
    assert "dropout run without simulator-manifest totals" in bare_row["warnings"]

    # Non-dropout runs stay quiet about absent totals.
    nominal = make_run(
        tmp_path,
        "nominal-r09",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    nominal_row = analyze.compute_run_metrics(nominal)
    assert nominal_row["dropout_disconnects"] is None
    assert "totals missing" not in nominal_row["warnings"]


def test_restart_hook_record_read_from_manifest(tmp_path) -> None:
    """E3: restart_hook_ok reflects the manifest's restart record (executed
    timestamps + exit 0, no error); its absence warns on restart runs."""
    ok_record = {
        "template": "ssh vm docker compose restart controller",
        "requested_at_s": 300,
        "executed": True,
        "started_utc": "2026-09-07T10:05:00Z",
        "finished_utc": "2026-09-07T10:05:03Z",
        "returncode": 0,
    }
    ok_dir = make_run(
        tmp_path,
        "controller_restart-r01",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "condition_id": "controller_restart",
            "restart": ok_record,
        },
    )
    assert analyze.compute_run_metrics(ok_dir)["restart_hook_ok"] is True

    failed_record = dict(ok_record, returncode=1)
    failed_dir = make_run(
        tmp_path,
        "controller_restart-r02",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "condition_id": "controller_restart",
            "restart": failed_record,
            "repetition": 2,
        },
    )
    failed_row = analyze.compute_run_metrics(failed_dir)
    assert failed_row["restart_hook_ok"] is False
    assert "restart-hook record" in failed_row["warnings"]

    missing_dir = make_run(
        tmp_path,
        "controller_restart-r03",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={"condition_id": "controller_restart", "repetition": 3},
    )
    missing_row = analyze.compute_run_metrics(missing_dir)
    assert missing_row["restart_hook_ok"] is None
    assert "restart-hook record" in missing_row["warnings"]


def test_analyze_end_to_end_dropout_acceptance_from_files(tmp_path) -> None:
    """File-level positive control (work order P1b): three fully-formed
    dropout runs pass every C10 criterion in acceptance_by_condition.csv."""
    base = tmp_path / "results"
    start = T0
    end = T0 + timedelta(seconds=600)
    mids = [f"m{i}" for i in range(3)]
    for rep in range(1, 4):
        metrics = [
            [_iso(start), 0, 0, 0, 0, 0, 5],
            [_iso(start + timedelta(seconds=1)), 3, 0, 0, 0, 0, 5],
        ]
        make_run(
            base,
            f"dropout_reconnect-r{rep:02d}",
            sent=[sent_record(m, i) for i, m in enumerate(mids)],
            events=[event_record(m, "accepted") for m in mids],
            manifest_extra={
                "condition_id": "dropout_reconnect",
                "scenario": "dropout-reconnect",
                "repetition": rep,
                "validity": "valid",
                **_window_manifest(start, end),
            },
            controller_metrics_rows=metrics,
            sim_totals={"buffered_dropout": 9, "dropout_disconnects": 2},
        )
    assert analyze.analyze(base_dir=base) == 0
    acceptance = _read_csv(base / "processed" / "acceptance_by_condition.csv")
    dropout = {
        r["criterion"]: r
        for r in acceptance
        if r["condition_id"] == "dropout_reconnect"
    }
    for criterion in (
        "runs_complete",
        "zero_lost_within_window",
        "zero_double_accepted",
        "dropout_disconnects_ge_1_every_run",
        "buffered_dropout_ge_1_every_run",
        "controller_metrics_reconciled",
    ):
        assert dropout[criterion]["passed"] == "true", criterion
    assert "3/3 valid runs" in dropout["runs_complete"]["observed"]


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
    # No load_sweep runs in this fixture: every PLANNED load is listed as
    # insufficient-evidence (work order P1b), never as decided.
    assert [load["rate_msg_s"] for load in saturation["loads"]] == [
        10.0, 50.0, 100.0, 250.0,
    ]
    assert all(
        load["verdict"] == "insufficient-evidence" for load in saturation["loads"]
    )
    # Acceptance rows exist for every planned condition; absent conditions
    # (e.g. smoke_sequence) are FAILED, not blank (work order P1b).
    acceptance = _read_csv(base / "processed" / "acceptance_by_condition.csv")
    smoke_complete = next(
        r
        for r in acceptance
        if r["condition_id"] == "smoke_sequence" and r["criterion"] == "runs_complete"
    )
    assert smoke_complete["passed"] == "false"
    assert "0/10 valid runs" in smoke_complete["observed"]
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
# Validity gate (work order P1 fix 1): invalid runs never aggregate
# ---------------------------------------------------------------------------


def test_invalid_runs_excluded_from_aggregation_but_listed(tmp_path, capsys) -> None:
    """Runs with validity != 'valid' are removed from summaries, saturation,
    acceptance and figures, stay listed in per_run.csv, and a notice names
    them (work order P1 fix 1)."""
    base = tmp_path / "results"
    mids = [f"m{i}" for i in range(5)]
    make_run(
        base,
        "nominal-r01",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=[event_record(m, "accepted") for m in mids],
        manifest_extra={"validity": "valid", "validity_reasons": []},
    )
    # Invalid nominal run with a much worse delivery rate: it must not
    # drag the summary down.
    make_run(
        base,
        "nominal-r02",
        sent=[sent_record(f"x{i}", i) for i in range(5)],
        events=[event_record("x0", "accepted")],
        manifest_extra={
            "repetition": 2,
            "validity": "invalid",
            "validity_reasons": ["no SUT resources"],
        },
    )
    # Invalid load_sweep run with 100% loss: saturation must see NO sweep
    # data at all.
    make_run(
        base,
        "load_sweep-100.0-r01",
        sent=[sent_record(f"s{i}", i) for i in range(5)],
        events=[],
        manifest_extra={
            "condition_id": "load_sweep",
            "scenario": "load-sweep",
            "rate_msg_s": 100.0,
            "validity": "invalid",
            "validity_reasons": ["simulator exited with code 1"],
        },
    )
    assert analyze.analyze(base_dir=base) == 0
    out = capsys.readouterr().out
    assert "2 run(s) with validity != 'valid'" in out
    assert "nominal-r02" in out
    assert "load_sweep-100.0-r01" in out

    # per_run.csv keeps ALL runs listed with their validity flag.
    per_run = {r["run_id"]: r for r in _read_csv(base / "processed" / "per_run.csv")}
    assert set(per_run) == {"nominal-r01", "nominal-r02", "load_sweep-100.0-r01"}
    assert per_run["nominal-r01"]["validity"] == "valid"
    assert per_run["nominal-r02"]["validity"] == "invalid"

    # Summaries aggregate only the valid run.
    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    delivery = [
        r
        for r in summary
        if r["condition_id"] == "nominal" and r["metric"] == "delivery_rate"
    ]
    assert len(delivery) == 1
    assert delivery[0]["n_runs"] == "1"
    assert float(delivery[0]["mean"]) == 1.0
    assert not any(r["condition_id"] == "load_sweep" for r in summary)

    # Saturation sees no load_sweep input from the invalid run: every
    # planned load stays insufficient-evidence with zero valid runs (P1b).
    saturation = json.loads(
        (base / "processed" / "saturation.json").read_text("utf-8")
    )
    assert all(
        load["n_runs"] == 0 and load["verdict"] == "insufficient-evidence"
        for load in saturation["loads"]
    )
    assert saturation["first_saturated_load_msg_s"] is None


def test_legacy_manifest_without_validity_key_still_aggregated(
    tmp_path, capsys
) -> None:
    """A manifest WITHOUT a validity key (legacy raw runs/fixtures) is
    treated as valid; only a present non-'valid' value excludes."""
    base = tmp_path / "results"
    mids = [f"m{i}" for i in range(3)]
    make_run(
        base,
        "nominal-r01",
        sent=[sent_record(m, i) for i, m in enumerate(mids)],
        events=[event_record(m, "accepted") for m in mids],
        # make_run writes no 'validity' key at all (legacy shape).
    )
    assert analyze.analyze(base_dir=base) == 0
    out = capsys.readouterr().out
    assert "validity != 'valid'" not in out
    per_run = _read_csv(base / "processed" / "per_run.csv")
    assert per_run[0]["validity"] == ""
    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    delivery = next(
        r
        for r in summary
        if r["condition_id"] == "nominal" and r["metric"] == "delivery_rate"
    )
    assert delivery["n_runs"] == "1"


def test_per_run_reports_resource_source_and_flags_non_sut(tmp_path) -> None:
    """per_run rows carry resource_source; anything other than
    'sut-collector' gets a per-run warning (work order P1 fix 2)."""
    run_dir = make_run(
        tmp_path,
        "local-dev-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={"resource_source": "local-dev"},
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["resource_source"] == "local-dev"
    assert "not 'sut-collector'" in row["warnings"]

    ok_dir = make_run(
        tmp_path,
        "sut-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={"resource_source": "sut-collector"},
    )
    ok_row = analyze.compute_run_metrics(ok_dir)
    assert ok_row["resource_source"] == "sut-collector"
    assert "not 'sut-collector'" not in ok_row["warnings"]

    # Legacy manifest without the key: flagged too (None provenance).
    legacy_dir = make_run(
        tmp_path,
        "legacy-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    legacy_row = analyze.compute_run_metrics(legacy_dir)
    assert legacy_row["resource_source"] is None
    assert "not 'sut-collector'" in legacy_row["warnings"]


def test_manifest_deviations_listed_as_per_run_warning(tmp_path) -> None:
    """Any manifest 'deviations' entries produce a per-run warning listing
    them (work order P1 fix 5)."""
    run_dir = make_run(
        tmp_path,
        "deviant-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "deviations": [
                {
                    "kind": "skip_warmup",
                    "detail": "warm-up skipped",
                    "authorized_by_flag": "--allow-protocol-deviation",
                },
                {
                    "kind": "warmup_nonzero_exit",
                    "detail": "warm-up exited with code 1",
                    "authorized_by_flag": None,
                },
            ]
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert "protocol deviation(s) recorded" in row["warnings"]
    assert "skip_warmup (authorized by --allow-protocol-deviation)" in row["warnings"]
    assert "warmup_nonzero_exit (no authorizing flag)" in row["warnings"]

    clean_dir = make_run(
        tmp_path,
        "clean-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={"deviations": []},
    )
    clean_row = analyze.compute_run_metrics(clean_dir)
    assert "protocol deviation(s)" not in clean_row["warnings"]


def test_read_resources_csv_accepts_old_and_new_headers(tmp_path) -> None:
    """The analysis READER tolerates both the legacy 5-column schema (old
    fixtures/raw runs) and the new 6-column host-provenance schema; only
    run-time ingestion is strict (work order P1 fix 3)."""
    old = tmp_path / "old.csv"
    old.write_text(
        "ts_utc,container,cpu_pct,mem_bytes,mem_pct\n"
        "2026-09-07T10:00:00Z,egw-controller,12.5,1024,1.2\n",
        "utf-8",
    )
    new = tmp_path / "new.csv"
    new.write_text(
        "ts_utc,container,cpu_pct,mem_bytes,mem_pct,host\n"
        "2026-09-07T10:00:00Z,egw-controller,12.5,1024,1.2,sut-vm\n",
        "utf-8",
    )
    for path in (old, new):
        by_container = analyze.read_resources_csv(path)
        assert set(by_container) == {"egw-controller"}
        (sample,) = by_container["egw-controller"]
        assert sample["cpu_pct"] == 12.5
        assert sample["mem_bytes"] == 1024


# ---------------------------------------------------------------------------
# Per-condition acceptance (audit 9.5, claims C10/C11/C12/C14)
# ---------------------------------------------------------------------------


#: Criteria that stay deliberately informational/descriptive (passed=None
#: by design, work order P1b); every other criterion must be True/False.
INFORMATIONAL_CRITERIA = {
    "valid_delivery_rate_mean_informational",
    "delivery_descriptive",
}

#: The planned simulator conditions (protocol.py CONDITIONS): acceptance
#: rows must exist for ALL of them, even with an empty raw/ tree.
PLANNED_SIMULATOR_CONDITIONS = {
    "smoke_sequence",
    "nominal",
    "load_sweep",
    "invalid_payload",
    "dropout_reconnect",
    "controller_restart",
    "soak",
}


def _acc_row(cid: str, **overrides) -> dict:
    base = {
        "condition_id": cid,
        "validity": "valid",
        "excluded": False,
        "lost": 0,
        "double_accepted": 0,
        "intended_invalid_sent": 0,
        "rejected_intended_invalid": 0,
        "intended_invalid_accepted": 0,
        "delivery_rate": 1.0,
    }
    base.update(overrides)
    return base


def _dropout_row(**overrides) -> dict:
    """A dropout run satisfying every C10 criterion (work order P1b)."""
    base = _acc_row(
        "dropout_reconnect",
        dropout_disconnects=2,
        buffered_dropout=15,
        events_accepted_total=100,
        metrics_accepted_delta=100.0,
    )
    base.update(overrides)
    return base


def _restart_row(**overrides) -> dict:
    """A controller_restart run satisfying every C12 criterion.

    Since sprint P5 that includes the recovery evidence (report 5.4):
    downtime observed, the /metrics ENDPOINT answering again inside
    RESTART_RECOVERY_MAX_S and accepted-counter progress after the restart.
    Sprint P5.4 adds the bounded FUNCTIONAL criterion: the first evidence
    that ingestion itself resumed must also fall inside that bound.
    """
    base = _acc_row(
        "controller_restart",
        restart_hook_ok=True,
        restart_downtime_evidence=True,
        restart_metrics_endpoint_recovery_s=8.0,
        restart_functional_recovery_s=9.0,
        restart_functional_recovery_source="metrics-accepted-counter",
        restart_accepted_progress=1_200.0,
    )
    base.update(overrides)
    return base


def _soak_row(**overrides) -> dict:
    """A soak run satisfying the full C13 Definition of Done (P1b)."""
    base = _acc_row(
        "soak",
        measured_window_s=86_400.0,
        resources_coverage_pct=99.9,
        resources_max_gap_s=2.0,
        resources_head_gap_s=1.0,
        resources_distinct_instants=86_000,
        metrics_coverage_pct=99.9,
        metrics_max_gap_s=2.0,
        metrics_head_gap_s=1.0,
        metrics_distinct_instants=86_000,
        metrics_tail_gap_s=1.0,
        events_accepted_total=900_000,
        metrics_accepted_delta=900_100.0,  # within the +-1% tolerance
        delivered_unique=900_000,
        sent_valid=900_000,
    )
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
    complete = _acc(result, "smoke_sequence", "runs_complete")
    assert complete["passed"] is True
    assert complete["expected_runs"] == 10
    assert complete["claims"] == "C14"
    assert _acc(result, "smoke_sequence", "zero_lost")["passed"] is True


def test_acceptance_smoke_sequence_fails_on_missing_run_or_loss() -> None:
    rows = [_acc_row("smoke_sequence") for _ in range(9)]  # one run missing
    result = analyze.evaluate_acceptance(rows)
    assert _acc(result, "smoke_sequence", "runs_complete")["passed"] is False
    # The sibling substantive criterion is completeness-gated too (P1b):
    # zero lost over 9 runs is NOT acceptance evidence for 10 planned runs.
    zero_lost = _acc(result, "smoke_sequence", "zero_lost")
    assert zero_lost["passed"] is False
    assert "9/10 valid runs" in zero_lost["observed"]

    rows = [_acc_row("smoke_sequence") for _ in range(10)]
    rows[3]["lost"] = 1
    result = analyze.evaluate_acceptance(rows)
    assert _acc(result, "smoke_sequence", "runs_complete")["passed"] is True
    assert _acc(result, "smoke_sequence", "zero_lost")["passed"] is False


def test_acceptance_smoke_sequence_invalid_run_fails_completeness() -> None:
    rows = [_acc_row("smoke_sequence") for _ in range(10)]
    rows[0]["validity"] = "invalid"
    result = analyze.evaluate_acceptance(rows)
    complete = _acc(result, "smoke_sequence", "runs_complete")
    assert complete["passed"] is False
    assert "9/10 valid runs" in complete["observed"]
    assert complete["n_runs"] == 9


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
    # zero lost + zero double-accepted (module docstring).
    rows = [_dropout_row() for _ in range(3)]
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


def test_acceptance_dropout_one_of_three_runs_fails_completeness() -> None:
    """E1: dropout_reconnect with 1/3 runs must FAIL, never pass or blank."""
    result = analyze.evaluate_acceptance([_dropout_row()])
    complete = _acc(result, "dropout_reconnect", "runs_complete")
    assert complete["passed"] is False
    assert "1/3 valid runs" in complete["observed"]
    # Every substantive criterion is gated on completeness.
    for criterion in (
        "zero_lost_within_window",
        "zero_double_accepted",
        "dropout_disconnects_ge_1_every_run",
        "buffered_dropout_ge_1_every_run",
        "controller_metrics_reconciled",
    ):
        row = _acc(result, "dropout_reconnect", criterion)
        assert row["passed"] is False
        assert "1/3 valid runs" in row["observed"]


def test_acceptance_dropout_requires_real_disconnects_every_run() -> None:
    """E2: a 'dropout' run in which no disconnect actually happened (or
    whose simulator manifest totals are missing) fails the C10 criteria."""
    rows = [_dropout_row() for _ in range(3)]
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "dropout_reconnect", "dropout_disconnects_ge_1_every_run")[
            "passed"
        ]
        is True
    )
    assert (
        _acc(result, "dropout_reconnect", "buffered_dropout_ge_1_every_run")[
            "passed"
        ]
        is True
    )

    # One run with zero disconnects: that criterion fails, buffered intact.
    rows = [_dropout_row(), _dropout_row(dropout_disconnects=0), _dropout_row()]
    result = analyze.evaluate_acceptance(rows)
    disconnects = _acc(
        result, "dropout_reconnect", "dropout_disconnects_ge_1_every_run"
    )
    assert disconnects["passed"] is False
    assert "2/3 run(s) with dropout_disconnects >= 1" in disconnects["observed"]
    assert (
        _acc(result, "dropout_reconnect", "buffered_dropout_ge_1_every_run")[
            "passed"
        ]
        is True
    )

    # One run without simulator-manifest totals (None): fails and says why.
    rows = [
        _dropout_row(),
        _dropout_row(dropout_disconnects=None, buffered_dropout=None),
        _dropout_row(),
    ]
    result = analyze.evaluate_acceptance(rows)
    disconnects = _acc(
        result, "dropout_reconnect", "dropout_disconnects_ge_1_every_run"
    )
    assert disconnects["passed"] is False
    assert "simulator manifest totals missing in 1 run(s)" in disconnects["observed"]
    assert (
        _acc(result, "dropout_reconnect", "buffered_dropout_ge_1_every_run")[
            "passed"
        ]
        is False
    )


def test_acceptance_controller_metrics_reconciliation() -> None:
    """Work order P1b: dropout/load_sweep/soak mandate controller metrics;
    the accepted-counter delta must reconcile with events.jsonl within the
    documented +-1% (floor 1) tolerance; missing metrics FAIL, never blank."""
    rows = [_dropout_row() for _ in range(3)]
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "dropout_reconnect", "controller_metrics_reconciled")["passed"]
        is True
    )

    # Delta within +-1%: 100 accepted vs delta 101 still reconciles.
    rows = [_dropout_row(metrics_accepted_delta=101.0) for _ in range(3)]
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "dropout_reconnect", "controller_metrics_reconciled")["passed"]
        is True
    )

    # Out of tolerance: 100 vs 110 fails.
    rows = [_dropout_row(), _dropout_row(metrics_accepted_delta=110.0), _dropout_row()]
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "dropout_reconnect", "controller_metrics_reconciled")["passed"]
        is False
    )

    # Metrics absent: failed with the mandated detail, not blank.
    rows = [_dropout_row(), _dropout_row(metrics_accepted_delta=None), _dropout_row()]
    result = analyze.evaluate_acceptance(rows)
    reconciled = _acc(result, "dropout_reconnect", "controller_metrics_reconciled")
    assert reconciled["passed"] is False
    assert "controller metrics missing" in reconciled["observed"]


def test_acceptance_controller_restart_criteria() -> None:
    rows = [_restart_row() for _ in range(3)]
    result = analyze.evaluate_acceptance(rows)
    across = _acc(result, "controller_restart", "delivery_across_restart_zero_lost")
    assert across["passed"] is True
    assert across["claims"] == "C12"
    assert (
        _acc(result, "controller_restart", "zero_double_accepted")["passed"] is True
    )
    assert (
        _acc(result, "controller_restart", "restart_hook_executed_every_run")[
            "passed"
        ]
        is True
    )

    rows[1]["double_accepted"] = 3
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "controller_restart", "zero_double_accepted")["passed"] is False
    )


def test_acceptance_restart_without_hook_record_fails() -> None:
    """E3: a controller_restart run whose manifest has no successfully
    executed restart-hook record fails the C12 hook criterion."""
    # Hook record absent entirely (restart_hook_ok None).
    rows = [_restart_row(), _restart_row(restart_hook_ok=None), _restart_row()]
    result = analyze.evaluate_acceptance(rows)
    hook = _acc(result, "controller_restart", "restart_hook_executed_every_run")
    assert hook["passed"] is False
    assert "2/3 run(s) with executed restart hook" in hook["observed"]
    # The other criteria are unaffected.
    assert (
        _acc(result, "controller_restart", "delivery_across_restart_zero_lost")[
            "passed"
        ]
        is True
    )

    # Hook executed but with a non-zero exit (restart_hook_ok False).
    rows = [_restart_row(), _restart_row(restart_hook_ok=False), _restart_row()]
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "controller_restart", "restart_hook_executed_every_run")[
            "passed"
        ]
        is False
    )


def test_acceptance_soak_definition_of_done_passes_when_all_met() -> None:
    result = analyze.evaluate_acceptance([_soak_row()])
    assert _acc(result, "soak", "runs_complete")["passed"] is True
    for criterion in (
        "measured_window_ge_24h",
        "resources_coverage_and_cadence",
        "controller_metrics_coverage_and_cadence",
        "no_unrecovered_interruption",
        "controller_metrics_reconciled",
    ):
        row = _acc(result, "soak", criterion)
        assert row["passed"] is True, criterion
    # Delivery stays descriptive (plan 7.3): informational, no pass/fail.
    descriptive = _acc(result, "soak", "delivery_descriptive")
    assert descriptive["passed"] is None
    assert "no CI" in descriptive["observed"]


def test_acceptance_soak_shorter_than_24h_fails_window_criterion_only() -> None:
    result = analyze.evaluate_acceptance([_soak_row(measured_window_s=80_000.0)])
    assert _acc(result, "soak", "measured_window_ge_24h")["passed"] is False
    # The other DoD criteria are unaffected.
    assert _acc(result, "soak", "resources_coverage_and_cadence")["passed"] is True
    assert (
        _acc(result, "soak", "controller_metrics_coverage_and_cadence")["passed"]
        is True
    )
    assert _acc(result, "soak", "no_unrecovered_interruption")["passed"] is True


def test_acceptance_soak_90s_metrics_gap_fails_cadence_not_interruption() -> None:
    # A 90 s hole in controller_metrics: > 60 s sampling gap (cadence DoD
    # fails) but <= 120 s (no unrecovered interruption) — the criteria are
    # independent.
    result = analyze.evaluate_acceptance([_soak_row(metrics_max_gap_s=90.0)])
    assert (
        _acc(result, "soak", "controller_metrics_coverage_and_cadence")["passed"]
        is False
    )
    assert _acc(result, "soak", "no_unrecovered_interruption")["passed"] is True
    assert _acc(result, "soak", "resources_coverage_and_cadence")["passed"] is True
    assert _acc(result, "soak", "measured_window_ge_24h")["passed"] is True


def test_acceptance_soak_truncated_tail_fails_interruption_criterion() -> None:
    # Collection dying 300 s before the window end: the last sample is not
    # within 120 s of the end -> unrecovered interruption; coverage (99.66%)
    # still passes, isolating the failing criterion.
    result = analyze.evaluate_acceptance(
        [_soak_row(metrics_tail_gap_s=300.0, metrics_coverage_pct=99.66)]
    )
    assert _acc(result, "soak", "no_unrecovered_interruption")["passed"] is False
    assert (
        _acc(result, "soak", "controller_metrics_coverage_and_cadence")["passed"]
        is True
    )
    assert _acc(result, "soak", "measured_window_ge_24h")["passed"] is True


def test_acceptance_soak_missing_window_or_stats_fails_not_blank() -> None:
    # A soak run without measured_window_utc (all stats None) fails every
    # DoD criterion with observable detail — never a blank verdict.
    result = analyze.evaluate_acceptance(
        [
            _soak_row(
                measured_window_s=None,
                resources_coverage_pct=None,
                resources_max_gap_s=None,
                metrics_coverage_pct=None,
                metrics_max_gap_s=None,
                metrics_tail_gap_s=None,
            )
        ]
    )
    for criterion in (
        "measured_window_ge_24h",
        "resources_coverage_and_cadence",
        "controller_metrics_coverage_and_cadence",
        "no_unrecovered_interruption",
    ):
        assert _acc(result, "soak", criterion)["passed"] is False, criterion


def test_acceptance_without_runs_emits_failed_rows_for_all_conditions() -> None:
    """E1: zero runs must NEVER produce blank acceptance rows — every
    planned simulator condition gets FAILED rows (work order P1b)."""
    result = analyze.evaluate_acceptance([])
    assert {r["condition_id"] for r in result} == PLANNED_SIMULATOR_CONDITIONS
    for row in result:
        assert row["n_runs"] == 0
        if row["criterion"] in INFORMATIONAL_CRITERIA:
            assert row["passed"] is None
        else:
            assert row["passed"] is False, (row["condition_id"], row["criterion"])
    # load_sweep expects repetitions x number of swept rates (10 x 4).
    assert _acc(result, "load_sweep", "runs_complete")["expected_runs"] == 40
    assert "0/40 valid runs" in _acc(result, "load_sweep", "runs_complete")["observed"]
    assert _acc(result, "soak", "runs_complete")["expected_runs"] == 1


def test_acceptance_full_synthetic_campaign_passes_every_criterion() -> None:
    """A fully-formed synthetic campaign satisfies every acceptance
    criterion (work order P1b positive control)."""
    rows: list[dict] = []
    rows += [_acc_row("smoke_sequence") for _ in range(10)]
    rows += [_acc_row("nominal") for _ in range(10)]
    for rate in (10.0, 50.0, 100.0, 250.0):
        rows += [
            _acc_row(
                "load_sweep",
                rate_msg_s=rate,
                events_accepted_total=1000,
                metrics_accepted_delta=1000.0,
            )
            for _ in range(10)
        ]
    rows += [
        _acc_row(
            "invalid_payload",
            intended_invalid_sent=20,
            rejected_intended_invalid=20,
        )
        for _ in range(3)
    ]
    rows += [_dropout_row() for _ in range(3)]
    rows += [_restart_row() for _ in range(3)]
    rows += [_soak_row()]
    result = analyze.evaluate_acceptance(rows)
    assert {r["condition_id"] for r in result} == PLANNED_SIMULATOR_CONDITIONS
    for row in result:
        if row["criterion"] in INFORMATIONAL_CRITERIA:
            assert row["passed"] is None
        else:
            assert row["passed"] is True, (row["condition_id"], row["criterion"])


# ---------------------------------------------------------------------------
# External conditions analyzed by the same script (audit 9.6, claim C15)
# ---------------------------------------------------------------------------


def make_external_run(
    base: Path,
    run_id: str,
    condition: str,
    samples: list[dict],
    exclusion=None,
    seal: bool = True,
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
    if seal:
        write_sha256sums(run_dir)
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


# ---------------------------------------------------------------------------
# Evidence integrity (report 5.4 "Integridade nao e verificada", sprint P5)
# ---------------------------------------------------------------------------


def _tamper(run_dir: Path, filename: str = "events.jsonl") -> None:
    """Rewrite a sealed file so its digest no longer matches SHA256SUMS."""
    path = run_dir / filename
    path.write_text(path.read_text("utf-8") + "\n", "utf-8")


def test_check_run_integrity_verdicts(tmp_path) -> None:
    sealed = make_run(
        tmp_path / "a",
        "sealed",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    assert analyze.check_run_integrity(sealed) == (analyze.INTEGRITY_OK, [])

    unsealed = make_run(
        tmp_path / "b",
        "unsealed",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        seal=False,
    )
    verdict, problems = analyze.check_run_integrity(unsealed)
    assert verdict == analyze.INTEGRITY_UNSEALED
    assert problems == []

    tampered = make_run(
        tmp_path / "c",
        "tampered",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    _tamper(tampered)
    verdict, problems = analyze.check_run_integrity(tampered)
    assert verdict == analyze.INTEGRITY_FAILED
    assert any("mismatch: events.jsonl" in p for p in problems)

    # A file listed in SHA256SUMS but deleted from disk is equally fatal.
    missing = make_run(
        tmp_path / "d",
        "missing-file",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        resources_rows=[["2026-09-07T10:00:00.000Z", "c", 1.0, 10, 0.1]],
    )
    (missing / "resources.csv").unlink()
    verdict, problems = analyze.check_run_integrity(missing)
    assert verdict == analyze.INTEGRITY_FAILED
    assert any("missing: resources.csv" in p for p in problems)


def test_per_run_flags_integrity_failure_with_loud_warning(tmp_path) -> None:
    run_dir = make_run(
        tmp_path,
        "tampered-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    _tamper(run_dir)
    row = analyze.compute_run_metrics(run_dir)
    assert row["integrity_ok"] == analyze.INTEGRITY_FAILED
    assert "evidence integrity failure" in row["warnings"]
    assert "integrity_ok" in analyze.PER_RUN_COLUMNS


def test_per_run_flags_unsealed_run(tmp_path) -> None:
    run_dir = make_run(
        tmp_path,
        "unsealed-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        seal=False,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["integrity_ok"] == analyze.INTEGRITY_UNSEALED
    assert "evidence integrity unverifiable" in row["warnings"]


def test_analyze_excludes_tampered_run_from_aggregation(tmp_path, capsys) -> None:
    """A run whose evidence does not verify is listed but never aggregated."""
    base = tmp_path / "results"
    for rep, latency in ((1, 10.0), (2, 20.0)):
        make_run(
            base,
            f"nominal-r{rep:02d}",
            sent=[sent_record("m0")],
            events=[event_record("m0", "accepted", latency_ms=latency)],
            manifest_extra={"repetition": rep},
        )
    _tamper(base / "raw" / "nominal-r02")

    assert analyze.analyze(base_dir=base) == 0
    out = capsys.readouterr().out
    assert "EVIDENCE INTEGRITY FAILURE" in out
    assert "nominal-r02" in out

    per_run = {r["run_id"]: r for r in _read_csv(base / "processed" / "per_run.csv")}
    assert per_run["nominal-r01"]["integrity_ok"] == "true"
    assert per_run["nominal-r02"]["integrity_ok"] == "false"

    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    latency = next(
        r
        for r in summary
        if r["condition_id"] == "nominal" and r["metric"] == "latency_ms_mean"
    )
    # Only the intact run survives: n=1 and the mean is its own latency.
    assert latency["n_runs"] == "1"
    assert float(latency["mean"]) == 10.0


def test_analyze_excludes_unsealed_timed_run_from_aggregation(
    tmp_path, capsys
) -> None:
    base = tmp_path / "results"
    make_run(
        base,
        "nominal-r01",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted", latency_ms=10.0)],
    )
    make_run(
        base,
        "nominal-r02",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted", latency_ms=90.0)],
        manifest_extra={"repetition": 2},
        seal=False,
    )
    assert analyze.analyze(base_dir=base) == 0
    out = capsys.readouterr().out
    assert "EVIDENCE INTEGRITY UNVERIFIABLE" in out
    assert "nominal-r02" in out

    per_run = {r["run_id"]: r for r in _read_csv(base / "processed" / "per_run.csv")}
    assert per_run["nominal-r02"]["integrity_ok"] == "unsealed"
    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    latency = next(
        r
        for r in summary
        if r["condition_id"] == "nominal" and r["metric"] == "latency_ms_mean"
    )
    assert latency["n_runs"] == "1"
    assert float(latency["mean"]) == 10.0


def test_analyze_excludes_tampered_external_run_from_duration_stats(
    tmp_path, capsys
) -> None:
    base = tmp_path / "results"
    for rep, duration in ((1, 30.0), (2, 90.0)):
        make_external_run(
            base,
            f"cold_start-r{rep:02d}",
            "cold_start",
            [{"label": "boot", "duration_s": duration}],
        )
    _tamper(base / "raw" / "cold_start-r02", "timings.json")

    assert analyze.analyze(base_dir=base) == 0
    err = capsys.readouterr().err
    assert "evidence integrity failure in external run cold_start-r02" in err

    external = _read_csv(base / "processed" / "external_runs.csv")
    verdicts = {r["run_id"]: r["integrity_ok"] for r in external}
    assert verdicts == {"cold_start-r01": "true", "cold_start-r02": "false"}

    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    row = next(r for r in summary if r["condition_id"] == "cold_start")
    assert row["n_runs"] == "1"
    assert float(row["mean"]) == 30.0


def test_analyze_excludes_unsealed_external_run_from_duration_stats(
    tmp_path, capsys
) -> None:
    """An external run with NO SHA256SUMS at all was never sealed, so its
    duration is unverifiable evidence: a verified seal is required before a
    run may contribute to mean/stdev/CI95/median/min/max (sprint P5.4).
    The run stays listed in external_runs.csv with its flag."""
    base = tmp_path / "results"
    make_external_run(
        base, "cold_start-r01", "cold_start", [{"label": "boot", "duration_s": 30.0}]
    )
    make_external_run(
        base,
        "cold_start-r02",
        "cold_start",
        [{"label": "boot", "duration_s": 900.0}],
        seal=False,
    )

    assert analyze.analyze(base_dir=base) == 0
    err = capsys.readouterr().err
    assert "evidence integrity unverifiable in external run cold_start-r02" in err
    assert "cold_start-r01" not in err

    external = _read_csv(base / "processed" / "external_runs.csv")
    verdicts = {r["run_id"]: r["integrity_ok"] for r in external}
    assert verdicts == {"cold_start-r01": "true", "cold_start-r02": "unsealed"}

    summary = _read_csv(base / "processed" / "summary_by_condition.csv")
    row = next(r for r in summary if r["condition_id"] == "cold_start")
    assert row["n_runs"] == "1"
    assert float(row["mean"]) == 30.0


# ---------------------------------------------------------------------------
# Identity-based completeness (report 5.4 "Completude por contagem")
# ---------------------------------------------------------------------------


def _plan_rows(plan: dict, condition_id: str, **extra) -> list[dict]:
    """Per-run acceptance rows built from the plan's own run identities."""
    return [
        _acc_row(
            condition_id,
            run_id=entry["run_id"],
            repetition=entry["repetition"],
            seed=entry["seed"],
            rate_msg_s=entry["rate_msg_s"],
            **extra,
        )
        for entry in plan["runs"]
        if entry["condition_id"] == condition_id
    ]


def test_acceptance_identity_matches_plan() -> None:
    plan = generate_campaign_plan(4242)
    rows = _plan_rows(plan, "smoke_sequence")
    complete = _acc(
        analyze.evaluate_acceptance(rows, plan), "smoke_sequence", "runs_complete"
    )
    assert complete["passed"] is True
    assert "10/10 planned run identities matched" in complete["observed"]


def test_acceptance_identity_detects_duplicate_and_missing_run() -> None:
    """The count can be right while the campaign is wrong: one run executed
    twice and another never executed (report 5.4)."""
    plan = generate_campaign_plan(4242)
    rows = _plan_rows(plan, "smoke_sequence")
    rows[-1] = dict(rows[0])  # a re-run of r01 replacing r10
    result = analyze.evaluate_acceptance(rows, plan)
    complete = _acc(result, "smoke_sequence", "runs_complete")
    assert complete["n_runs"] == 10  # the COUNT still looks complete
    assert complete["passed"] is False
    assert "missing smoke_sequence-r10" in complete["observed"]
    assert "duplicated smoke_sequence-r01" in complete["observed"]
    # The substantive criterion is gated on completeness.
    assert _acc(result, "smoke_sequence", "zero_lost")["passed"] is False


def test_acceptance_identity_detects_wrong_seed() -> None:
    plan = generate_campaign_plan(4242)
    rows = _plan_rows(plan, "smoke_sequence")
    rows[3]["seed"] = 999_999
    complete = _acc(
        analyze.evaluate_acceptance(rows, plan), "smoke_sequence", "runs_complete"
    )
    assert complete["passed"] is False
    assert "mismatched smoke_sequence-r04" in complete["observed"]
    assert "seed=999999" in complete["observed"]


def test_acceptance_identity_detects_unplanned_run() -> None:
    plan = generate_campaign_plan(4242)
    rows = _plan_rows(plan, "smoke_sequence")
    rows.append(_acc_row("smoke_sequence", run_id="smoke_sequence-rXX", seed=1))
    complete = _acc(
        analyze.evaluate_acceptance(rows, plan), "smoke_sequence", "runs_complete"
    )
    assert complete["passed"] is False
    assert "unexpected smoke_sequence-rXX" in complete["observed"]


def test_acceptance_identity_for_load_sweep_is_per_rate() -> None:
    """40 sweep runs with the wrong mix of rates must fail: completeness is
    per load level, not a global count."""
    plan = generate_campaign_plan(4242)
    rows = _plan_rows(plan, "load_sweep")
    assert len(rows) == 40
    # Every 250 msg/s run replaced by a duplicate of one 10 msg/s run.
    ten = next(r for r in rows if r["rate_msg_s"] == 10.0)
    rows = [dict(ten) if r["rate_msg_s"] == 250.0 else r for r in rows]
    complete = _acc(
        analyze.evaluate_acceptance(rows, plan), "load_sweep", "runs_complete"
    )
    assert complete["n_runs"] == 40  # count intact
    assert complete["passed"] is False
    observed = complete["observed"]
    assert "rate 250 msg/s" in observed
    assert "rate 10 msg/s" in observed
    assert "duplicated" in observed


def test_acceptance_without_plan_keeps_count_check_and_warns() -> None:
    rows = [_acc_row("smoke_sequence") for _ in range(10)]
    complete = _acc(
        analyze.evaluate_acceptance(rows), "smoke_sequence", "runs_complete"
    )
    assert complete["passed"] is True
    assert "identity checking NOT performed" in complete["observed"]
    assert analyze.CAMPAIGN_PLAN_ENV_VAR in complete["observed"]


def test_load_campaign_plan_for_analysis_env_fallback(tmp_path, monkeypatch) -> None:
    plan = generate_campaign_plan(7)
    path = tmp_path / "campaign_plan.json"
    path.write_text(json.dumps(plan), "utf-8")
    monkeypatch.setenv(analyze.CAMPAIGN_PLAN_ENV_VAR, str(path))
    loaded, problem = analyze.load_campaign_plan_for_analysis(None)
    assert problem is None
    assert loaded["master_seed"] == 7
    # An explicit argument always wins over the environment variable.
    monkeypatch.setenv(analyze.CAMPAIGN_PLAN_ENV_VAR, str(tmp_path / "nope.json"))
    loaded, problem = analyze.load_campaign_plan_for_analysis(path)
    assert problem is None and loaded["master_seed"] == 7


def test_load_campaign_plan_for_analysis_reports_problems(tmp_path) -> None:
    plan, problem = analyze.load_campaign_plan_for_analysis(tmp_path / "absent.json")
    assert plan is None and "could not be read" in problem

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", "utf-8")
    plan, problem = analyze.load_campaign_plan_for_analysis(malformed)
    assert plan is None and "could not be read" in problem

    no_runs = tmp_path / "no_runs.json"
    no_runs.write_text(json.dumps({"plan_version": "1.0"}), "utf-8")
    plan, problem = analyze.load_campaign_plan_for_analysis(no_runs)
    assert plan is None and "no 'runs' list" in problem


def test_analyze_uses_plan_from_env_var(tmp_path, monkeypatch) -> None:
    """End-to-end: the env-var fallback makes identity checking work even
    without the (separately owned) CLI flag."""
    base = tmp_path / "results"
    plan = generate_campaign_plan(4242)
    entry = next(e for e in plan["runs"] if e["run_id"] == "smoke_sequence-r01")
    make_run(
        base,
        "smoke_sequence-r01",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "condition_id": "smoke_sequence",
            "scenario": "smoke",
            "repetition": entry["repetition"],
            "seed": entry["seed"],
            "rate_msg_s": entry["rate_msg_s"],
        },
    )
    plan_path = tmp_path / "campaign_plan.json"
    plan_path.write_text(json.dumps(plan), "utf-8")
    monkeypatch.setenv(analyze.CAMPAIGN_PLAN_ENV_VAR, str(plan_path))

    assert analyze.analyze(base_dir=base) == 0
    acceptance = _read_csv(base / "processed" / "acceptance_by_condition.csv")
    complete = next(
        r
        for r in acceptance
        if r["condition_id"] == "smoke_sequence"
        and r["criterion"] == "runs_complete"
    )
    # One of ten planned runs executed: identity checking names the rest.
    assert complete["passed"] == "false"
    assert "missing smoke_sequence-r02" in complete["observed"]


def test_analyze_without_plan_warns_identity_not_checked(tmp_path, capsys) -> None:
    base = tmp_path / "results"
    make_run(
        base,
        "nominal-r01",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    assert analyze.analyze(base_dir=base) == 0
    out = capsys.readouterr().out
    assert "checked BY COUNT ONLY" in out
    assert analyze.CAMPAIGN_PLAN_ENV_VAR in out


def test_analyze_with_unreadable_plan_degrades_with_warning(tmp_path, capsys) -> None:
    base = tmp_path / "results"
    make_run(
        base,
        "nominal-r01",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    assert analyze.analyze(base_dir=base, plan_path=tmp_path / "absent.json") == 0
    captured = capsys.readouterr()
    assert "could not be read" in captured.err
    assert "checked BY COUNT ONLY" in captured.out


# ---------------------------------------------------------------------------
# Head gap and minimum coverage (report 5.4 "Soak ignora o gap inicial",
# "Controller metrics sem cobertura minima")
# ---------------------------------------------------------------------------


def test_per_run_head_gap_columns_from_csvs(tmp_path) -> None:
    """The head gap (window start -> first sample) is measured and exposed;
    an interior max_gap of 1 s cannot reveal a series that started late."""
    start = T0
    end = T0 + timedelta(seconds=600)
    resources = [
        [_iso(start + timedelta(seconds=i)), "egw-controller", 10.0, 1024, 1.0]
        for i in range(120, 601)  # sampling only starts 120 s into the window
    ]
    metrics = [
        [_iso(start + timedelta(seconds=i)), i, 0, 0, 0, 0, 5]
        for i in range(0, 601)
    ]
    run_dir = make_run(
        tmp_path,
        "head-gap-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra=_window_manifest(start, end),
        resources_rows=resources,
        controller_metrics_rows=metrics,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["resources_head_gap_s"] == 120.0
    assert row["resources_max_gap_s"] == 1.0  # interior cadence is perfect
    assert row["metrics_head_gap_s"] == 0.0
    for column in ("resources_head_gap_s", "metrics_head_gap_s"):
        assert column in analyze.PER_RUN_COLUMNS


def test_acceptance_soak_head_gap_fails_coverage_criterion() -> None:
    """C13: a soak whose resources sampling only starts hours into the
    window fails the coverage/cadence criterion, not the others."""
    rows = [_soak_row(resources_head_gap_s=3_600.0)]
    result = analyze.evaluate_acceptance(rows)
    assert _acc(result, "soak", "resources_coverage_and_cadence")["passed"] is False
    assert (
        _acc(result, "soak", "controller_metrics_coverage_and_cadence")["passed"]
        is True
    )
    assert _acc(result, "soak", "measured_window_ge_24h")["passed"] is True
    assert _acc(result, "soak", "no_unrecovered_interruption")["passed"] is True
    observed = _acc(result, "soak", "resources_coverage_and_cadence")["observed"]
    assert "head gap 3600.00 s" in observed


def test_acceptance_soak_metrics_head_gap_fails_metrics_criterion() -> None:
    rows = [_soak_row(metrics_head_gap_s=90.0)]  # > SOAK_MAX_SAMPLING_GAP_S
    result = analyze.evaluate_acceptance(rows)
    assert (
        _acc(result, "soak", "controller_metrics_coverage_and_cadence")["passed"]
        is False
    )
    assert _acc(result, "soak", "resources_coverage_and_cadence")["passed"] is True


def test_acceptance_soak_missing_head_gap_fails_not_blank() -> None:
    """A head gap that could not be measured (no window/no samples) must
    fail the criterion, never silently pass."""
    rows = [_soak_row(resources_head_gap_s=None, metrics_head_gap_s=None)]
    result = analyze.evaluate_acceptance(rows)
    for criterion in (
        "resources_coverage_and_cadence",
        "controller_metrics_coverage_and_cadence",
    ):
        row = _acc(result, "soak", criterion)
        assert row["passed"] is False
        assert "head gap n/a" in row["observed"]


def test_saturation_metrics_coverage_below_minimum_is_insufficient_evidence() -> None:
    """Controller metrics covering a fraction of the window can no more
    decide a load than sparse resources can (report 5.4)."""
    rows = _sweep_load(10.0, 0.0, 100.0)
    rows += _sweep_load(50.0, 0.0, 100.0, n=9)
    rows += _sweep_load(50.0, 0.0, 100.0, n=1, metrics_coverage_pct=40.0)
    rows += _sweep_load(100.0, 0.0, 100.0)
    rows += _sweep_load(250.0, 0.0, 100.0)
    load = _load_at(analyze.detect_saturation(rows), 50.0)
    assert load["verdict"] == "insufficient-evidence"
    assert load["evidence_sufficient"] is False
    assert any(
        "controller metrics coverage 40.0% below the 90% minimum" in detail
        for detail in load["insufficient_evidence_detail"]
    )
    # The intact loads keep their decided verdict.
    assert _load_at(analyze.detect_saturation(rows), 10.0)["verdict"] == "not-saturated"


def test_saturation_head_gap_beyond_cap_is_insufficient_evidence() -> None:
    rows = _sweep_load(10.0, 0.0, 100.0)
    rows += _sweep_load(50.0, 0.0, 100.0, n=9)
    rows += _sweep_load(50.0, 0.0, 100.0, n=1, resources_head_gap_s=42.0)
    rows += _sweep_load(100.0, 0.0, 100.0)
    rows += _sweep_load(250.0, 0.0, 100.0)
    load = _load_at(analyze.detect_saturation(rows), 50.0)
    assert load["verdict"] == "insufficient-evidence"
    assert any(
        "resources head gap 42.0 s exceeds the 5 s sampling-cadence cap" in detail
        for detail in load["insufficient_evidence_detail"]
    )


def test_saturation_insufficient_evidence_never_hides_a_crossing() -> None:
    """A load that crosses a threshold but lacks instrumentation is
    insufficient-evidence, and is NOT reported as the saturation point."""
    rows = _sweep_load(10.0, 0.0, 100.0)
    rows += _sweep_load(50.0, 0.05, 100.0, metrics_coverage_pct=10.0)  # 5% loss
    result = analyze.detect_saturation(rows)
    load = _load_at(result, 50.0)
    assert load["saturated"] is True  # the raw crossing is still reported
    assert load["verdict"] == "insufficient-evidence"
    assert result["first_saturated_load_msg_s"] is None


# ---------------------------------------------------------------------------
# Semantic validation of the sampled series (report 5.4 "Validacao superficial")
# ---------------------------------------------------------------------------


def _write_csv_text(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", "utf-8")
    return path


def test_read_resources_csv_validated_counts_every_drop_reason(tmp_path) -> None:
    path = _write_csv_text(
        tmp_path / "resources.csv",
        [
            "ts_utc,container,cpu_pct,mem_bytes,mem_pct",
            "2026-09-07T10:00:00.000Z,egw-controller,10.0,1024,1.0",
            "not-a-timestamp,egw-controller,10.0,1024,1.0",
            "2026-09-07T10:00:01.000Z,egw-controller,NaN%,1024,1.0",
            "2026-09-07T10:00:02.000Z,,10.0,1024,1.0",
            "2026-09-07T10:00:03.000Z,egw-controller",
            "2026-09-07T09:59:00.000Z,egw-controller,10.0,1024,1.0",
            "2026-09-07T10:00:04.000Z,egw-controller,20.0,2048,2.0",
        ],
    )
    series, report = analyze.read_resources_csv_validated(path)
    assert report["rows_total"] == 7
    assert report["rows_dropped"] == 5
    assert report["reasons"] == {
        "unparseable_ts": 1,
        "non_numeric": 1,
        "empty_field": 1,
        "missing_column": 1,
        "decreasing_ts": 1,
    }
    # Only the two well-formed, non-decreasing rows survive.
    assert [s["cpu_pct"] for s in series["egw-controller"]] == [10.0, 20.0]
    assert report["distinct_instants"] == 2
    assert "unparseable_ts=1" in analyze.series_report_summary(report)


def test_read_controller_metrics_csv_validated_counts_every_drop_reason(
    tmp_path,
) -> None:
    path = _write_csv_text(
        tmp_path / "controller_metrics.csv",
        [
            "ts_utc,accepted,rejected,duplicate,failed,dropped,queue_depth",
            "2026-09-07T10:00:00.000Z,1,0,0,0,0,5",
            "nope,2,0,0,0,0,5",
            ",3,0,0,0,0,5",
            "2026-09-07T10:00:01.000Z,x,0,0,0,0,5",
            "2026-09-07T10:00:02.000Z,,,,,,",
            "2026-09-07T09:59:00.000Z,4,0,0,0,0,5",
            "2026-09-07T10:00:03.000Z,5,0,0,0,0,9",
        ],
    )
    samples, report = analyze.read_controller_metrics_csv_validated(path)
    assert report["rows_total"] == 7
    assert report["rows_dropped"] == 5
    assert report["reasons"]["unparseable_ts"] == 1
    assert report["reasons"]["empty_field"] == 1
    assert report["reasons"]["non_numeric"] == 1
    assert report["reasons"]["no_counters"] == 1
    assert report["reasons"]["decreasing_ts"] == 1
    assert [s["accepted"] for s in samples] == [1.0, 5.0]
    assert report["distinct_instants"] == 2


def test_per_run_counts_dropped_rows_and_distinct_instants(tmp_path) -> None:
    """Three containers sampled at the same two instants are TWO sample
    instants, not six; invalid rows are dropped and counted."""
    start = T0
    end = T0 + timedelta(seconds=600)
    resources = []
    for i in (0, 1):
        for container in ("egw-controller", "mosquitto", "ditto-gateway"):
            resources.append(
                [_iso(start + timedelta(seconds=i)), container, 10.0, 1024, 1.0]
            )
    resources.append(["not-a-timestamp", "egw-controller", 10.0, 1024, 1.0])
    metrics = [
        [_iso(start + timedelta(seconds=i)), i, 0, 0, 0, 0, 5] for i in (0, 1)
    ]
    metrics.append([_iso(start + timedelta(seconds=2)), "x", 0, 0, 0, 0, 5])
    run_dir = make_run(
        tmp_path,
        "semantic-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra=_window_manifest(start, end),
        resources_rows=resources,
        controller_metrics_rows=metrics,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["resource_samples"] == 6  # six container rows
    assert row["resources_distinct_instants"] == 2  # two sample instants
    assert row["resources_rows_dropped"] == 1
    assert row["metrics_distinct_instants"] == 2
    assert row["metrics_rows_dropped"] == 1
    assert "resources.csv: 1/7 row(s) dropped" in row["warnings"]
    assert "unparseable_ts=1" in row["warnings"]
    assert "controller_metrics.csv: 1/3 row(s) dropped" in row["warnings"]
    assert "non_numeric=1" in row["warnings"]


def test_read_resources_csv_rejects_non_finite_and_negative_values(tmp_path) -> None:
    """inf/nan/negative are not usable measurements (sprint P5.4): a
    mem_bytes of inf used to CRASH the analysis (int(float('inf')) raises
    OverflowError, which the ValueError clause never caught) and an inf/nan
    cpu_pct used to pass straight into the aggregates."""
    path = _write_csv_text(
        tmp_path / "resources.csv",
        [
            "ts_utc,container,cpu_pct,mem_bytes,mem_pct",
            "2026-09-07T10:00:00.000Z,egw-controller,10.0,1024,1.0",
            "2026-09-07T10:00:01.000Z,egw-controller,inf,1024,1.0",
            "2026-09-07T10:00:02.000Z,egw-controller,nan,1024,1.0",
            "2026-09-07T10:00:03.000Z,egw-controller,10.0,inf,1.0",
            "2026-09-07T10:00:04.000Z,egw-controller,-3.0,1024,1.0",
            "2026-09-07T10:00:05.000Z,egw-controller,10.0,1024,-1.0",
            "2026-09-07T10:00:06.000Z,egw-controller,20.0,2048,2.0",
        ],
    )
    series, report = analyze.read_resources_csv_validated(path)
    assert report["rows_total"] == 7
    assert report["reasons"] == {"non_finite": 3, "negative": 2}
    assert report["rows_dropped"] == 5
    assert [s["cpu_pct"] for s in series["egw-controller"]] == [10.0, 20.0]
    assert "non_finite=3" in analyze.series_report_summary(report)


def test_read_controller_metrics_csv_rejects_invalid_counters(tmp_path) -> None:
    """Controller counters are non-negative finite INTEGER counts: 1.5, -3,
    nan and inf are not counter values (sprint P5.4)."""
    path = _write_csv_text(
        tmp_path / "controller_metrics.csv",
        [
            "ts_utc,accepted,rejected,duplicate,failed,dropped,queue_depth",
            "2026-09-07T10:00:00.000Z,1,0,0,0,0,5",
            "2026-09-07T10:00:01.000Z,inf,0,0,0,0,5",
            "2026-09-07T10:00:02.000Z,nan,0,0,0,0,5",
            "2026-09-07T10:00:03.000Z,-3,0,0,0,0,5",
            "2026-09-07T10:00:04.000Z,1.5,0,0,0,0,5",
            "2026-09-07T10:00:05.000Z,7,0,0,0,0,-1",
            "2026-09-07T10:00:06.000Z,9,0,0,0,0,5",
        ],
    )
    samples, report = analyze.read_controller_metrics_csv_validated(path)
    assert report["rows_total"] == 7
    assert report["reasons"] == {"non_finite": 2, "negative": 2, "non_integral": 1}
    assert report["rows_dropped"] == 5
    assert [s["accepted"] for s in samples] == [1.0, 9.0]


def test_non_finite_resource_sample_neither_crashes_nor_fakes_saturation(
    tmp_path,
) -> None:
    """A single inf sample used to make host_cpu_utilization inf (declaring
    saturation) or kill the whole run with an uncaught OverflowError."""
    start = T0
    end = T0 + timedelta(seconds=600)
    resources = [
        [_iso(start + timedelta(seconds=0)), "egw-controller", 10.0, 1024, 1.0],
        [_iso(start + timedelta(seconds=1)), "egw-controller", "inf", 1024, 1.0],
        [_iso(start + timedelta(seconds=2)), "egw-controller", 10.0, "inf", 1.0],
        [_iso(start + timedelta(seconds=3)), "egw-controller", "nan", 1024, 1.0],
        [_iso(start + timedelta(seconds=4)), "egw-controller", 20.0, 2048, 2.0],
    ]
    metrics = [
        [_iso(start + timedelta(seconds=0)), 1, 0, 0, 0, 0, 5],
        [_iso(start + timedelta(seconds=1)), "inf", 0, 0, 0, 0, 5],
        [_iso(start + timedelta(seconds=2)), 3, 0, 0, 0, 0, 5],
    ]
    run_dir = make_run(
        tmp_path,
        "non-finite-run",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra=_window_manifest(start, end),
        resources_rows=resources,
        controller_metrics_rows=metrics,
        sut_env={"nproc": 4},
    )
    row = analyze.compute_run_metrics(run_dir)

    assert row["resource_samples"] == 2
    assert row["cpu_pct_max"] == 20.0
    assert row["mem_bytes_max"] == 2048
    assert math.isfinite(float(row["host_cpu_utilization_max"]))
    # 20/(100*4) = 0.05 is far below the 0.90 host-CPU threshold: no
    # saturation may be declared from a discarded inf sample.
    assert row["host_cpu_sustained_gt090_s"] == 0.0
    assert row["resources_rows_dropped"] == 3
    assert "non_finite=3" in row["warnings"]
    assert row["metrics_rows_dropped"] == 1
    assert row["metrics_accepted_delta"] == 2.0
    assert "controller_metrics.csv" in row["warnings"]


def test_saturation_single_distinct_instant_is_insufficient_evidence() -> None:
    """A series with one valid instant cannot support a cadence claim."""
    rows = _sweep_load(10.0, 0.0, 100.0)
    rows += _sweep_load(50.0, 0.0, 100.0, n=9)
    rows += _sweep_load(50.0, 0.0, 100.0, n=1, metrics_distinct_instants=1)
    rows += _sweep_load(100.0, 0.0, 100.0)
    rows += _sweep_load(250.0, 0.0, 100.0)
    load = _load_at(analyze.detect_saturation(rows), 50.0)
    assert load["verdict"] == "insufficient-evidence"
    assert any(
        "controller metrics has 1 valid distinct sample instant(s)" in detail
        for detail in load["insufficient_evidence_detail"]
    )


def test_acceptance_soak_insufficient_distinct_instants_fails() -> None:
    rows = [_soak_row(metrics_distinct_instants=1)]
    result = analyze.evaluate_acceptance(rows)
    row = _acc(result, "soak", "controller_metrics_coverage_and_cadence")
    assert row["passed"] is False
    assert "1 valid distinct instant(s)" in row["observed"]


# ---------------------------------------------------------------------------
# C12 recovery evidence (report 5.4 "C12 nao demonstra recuperacao")
# ---------------------------------------------------------------------------


def _restart_record(started: datetime, finished: datetime) -> dict:
    return {
        "restart": {
            "executed": True,
            "started_utc": _iso(started),
            "finished_utc": _iso(finished),
            "returncode": 0,
            "error": None,
        }
    }


def _metric_series(pairs: list[tuple[int, float]]) -> list[dict]:
    return [
        {"ts": T0 + timedelta(seconds=offset), "accepted": accepted}
        for offset, accepted in pairs
    ]


def test_restart_recovery_evidence_from_sampling_gap() -> None:
    """A hole in controller_metrics.csv straddling the restart IS the
    downtime evidence: a failed poll writes no row."""
    samples = _metric_series(
        [(i, float(i)) for i in range(0, 296)]
        + [(i, float(i)) for i in range(320, 341)]
    )
    evidence = analyze.restart_recovery_evidence(
        _restart_record(T0 + timedelta(seconds=300), T0 + timedelta(seconds=310))[
            "restart"
        ],
        samples,
    )
    assert evidence["downtime_evidence"] is True
    # First sample after finished_utc: the /metrics ENDPOINT answered again.
    assert evidence["metrics_endpoint_recovery_s"] == 10.0
    assert evidence["accepted_progress"] == 20.0


def test_restart_recovery_evidence_from_counter_reset() -> None:
    """A restarted controller starts its counters at zero: the reset is
    downtime evidence even when sampling never missed a beat."""
    samples = _metric_series(
        [(i, float(i)) for i in range(0, 301)]
        + [(i, float(i - 310)) for i in range(310, 341)]
    )
    evidence = analyze.restart_recovery_evidence(
        _restart_record(T0 + timedelta(seconds=300), T0 + timedelta(seconds=310))[
            "restart"
        ],
        samples,
    )
    assert evidence["downtime_evidence"] is True
    assert evidence["metrics_endpoint_recovery_s"] == 0.0
    assert evidence["accepted_progress"] == 30.0


def test_restart_recovery_evidence_absent_when_nothing_happened() -> None:
    """A hook that ran while the controller never blinked leaves NO
    downtime evidence: uninterrupted 1 Hz samples, no counter reset."""
    samples = _metric_series([(i, float(i)) for i in range(0, 341)])
    evidence = analyze.restart_recovery_evidence(
        _restart_record(T0 + timedelta(seconds=300), T0 + timedelta(seconds=310))[
            "restart"
        ],
        samples,
    )
    assert evidence["downtime_evidence"] is False
    assert evidence["metrics_endpoint_recovery_s"] == 0.0
    assert evidence["accepted_progress"] == 30.0


def test_restart_recovery_evidence_unknown_without_instrumentation() -> None:
    record = _restart_record(
        T0 + timedelta(seconds=300), T0 + timedelta(seconds=310)
    )["restart"]
    unknown = {
        "downtime_evidence": None,
        "metrics_endpoint_recovery_s": None,
        "accepted_progress": None,
        "functional_recovery_s": None,
        "functional_recovery_source": None,
    }
    assert analyze.restart_recovery_evidence(record, []) == unknown
    assert analyze.restart_recovery_evidence(None, _metric_series([(0, 0.0)])) == unknown
    assert (
        analyze.restart_recovery_evidence(
            {"executed": True, "returncode": 0}, _metric_series([(0, 0.0)])
        )
        == unknown
    )


def test_restart_endpoint_reply_is_not_functional_readiness() -> None:
    """The endpoint answering again only proves GET /metrics replied. The
    BOUNDED functional criterion asks when MQTT/Ditto ingestion actually
    resumed: here the counter stays flat for 400 s (sprint P5.4)."""
    samples = _metric_series(
        [(i, float(i)) for i in range(0, 296)]
        + [(i, 295.0) for i in range(313, 713)]
        + [(713, 296.0)]
    )
    evidence = analyze.restart_recovery_evidence(
        _restart_record(T0 + timedelta(seconds=300), T0 + timedelta(seconds=310))[
            "restart"
        ],
        samples,
    )
    assert evidence["downtime_evidence"] is True
    assert evidence["metrics_endpoint_recovery_s"] == 3.0
    # The legacy last-minus-first progress check passes on this run.
    assert evidence["accepted_progress"] == 1.0
    # The functional criterion does not: ingestion resumed 403 s later.
    assert evidence["functional_recovery_source"] == "metrics-accepted-counter"
    assert evidence["functional_recovery_s"] == 403.0
    assert evidence["functional_recovery_s"] > analyze.RESTART_RECOVERY_MAX_S


def test_restart_functional_recovery_prefers_controller_event_timestamps() -> None:
    """When the manifest carries the controller's confirmation marker the
    restart instant maps into the CONTROLLER's clock domain, so the first
    accepted event after the restart is the preferred evidence."""
    marker_ns = 1_000_000_000_000
    marker = {"ok": True, "monotonic_ns": marker_ns, "wall_utc": _iso(T0)}
    finished_ns = marker_ns + 310 * 1_000_000_000
    events = [
        event_record("m0", "accepted", received_ns=finished_ns - 200_000_000_000),
        event_record("m1", "accepted", received_ns=finished_ns + 5_000_000_000),
        event_record("m2", "accepted", received_ns=finished_ns + 60_000_000_000),
    ]
    # The counter series would answer 'never': it stays flat throughout.
    samples = _metric_series([(i, 295.0) for i in range(313, 700)])
    evidence = analyze.restart_recovery_evidence(
        _restart_record(T0 + timedelta(seconds=300), T0 + timedelta(seconds=310))[
            "restart"
        ],
        samples,
        events=events,
        controller_marker=marker,
    )
    assert evidence["metrics_endpoint_recovery_s"] == 3.0
    assert evidence["functional_recovery_source"] == "events-accepted-monotonic"
    assert evidence["functional_recovery_s"] == 5.0

    # Without the marker there is no bridge between the harness wall clock
    # and the controller's monotonic domain: the counter series decides.
    fallback = analyze.restart_recovery_evidence(
        _restart_record(T0 + timedelta(seconds=300), T0 + timedelta(seconds=310))[
            "restart"
        ],
        samples,
        events=events,
    )
    assert fallback["functional_recovery_source"] == "metrics-accepted-counter"
    assert fallback["functional_recovery_s"] is None


def test_per_run_restart_recovery_columns_from_controller_metrics(tmp_path) -> None:
    start = T0
    end = T0 + timedelta(seconds=600)
    metrics = [
        [_iso(start + timedelta(seconds=i)), i, 0, 0, 0, 0, 1]
        for i in range(0, 296)
    ]
    metrics += [
        [_iso(start + timedelta(seconds=i)), i - 320, 0, 0, 0, 0, 1]
        for i in range(320, 601)
    ]
    run_dir = make_run(
        tmp_path,
        "controller_restart-r01",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "condition_id": "controller_restart",
            "scenario": "nominal",
            **_window_manifest(start, end),
            **_restart_record(
                start + timedelta(seconds=300), start + timedelta(seconds=310)
            ),
        },
        controller_metrics_rows=metrics,
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["restart_hook_ok"] is True
    assert row["restart_downtime_evidence"] is True
    assert row["restart_metrics_endpoint_recovery_s"] == 10.0
    assert row["restart_accepted_progress"] == 280.0
    # The counter resets to 0 across the restart, so the first post-restart
    # value is the baseline and ingestion is shown to resume one sample on.
    assert row["restart_functional_recovery_s"] == 11.0
    assert row["restart_functional_recovery_source"] == "metrics-accepted-counter"
    for column in (
        "restart_downtime_evidence",
        "restart_metrics_endpoint_recovery_s",
        "restart_functional_recovery_s",
        "restart_functional_recovery_source",
        "restart_accepted_progress",
    ):
        assert column in analyze.PER_RUN_COLUMNS
    # The old, readiness-suggesting name is gone.
    assert "restart_recovery_s" not in analyze.PER_RUN_COLUMNS


def test_per_run_restart_without_metrics_has_no_recovery_evidence(tmp_path) -> None:
    start = T0
    end = T0 + timedelta(seconds=600)
    run_dir = make_run(
        tmp_path,
        "controller_restart-r02",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "condition_id": "controller_restart",
            "scenario": "nominal",
            **_window_manifest(start, end),
            **_restart_record(
                start + timedelta(seconds=300), start + timedelta(seconds=310)
            ),
        },
    )
    row = analyze.compute_run_metrics(run_dir)
    assert row["restart_downtime_evidence"] is None
    assert row["restart_metrics_endpoint_recovery_s"] is None
    assert row["restart_accepted_progress"] is None
    assert row["restart_functional_recovery_s"] is None
    assert row["restart_functional_recovery_source"] is None
    assert "without usable recovery evidence" in row["warnings"]


def test_acceptance_controller_restart_requires_downtime_evidence() -> None:
    """A hook that exited 0 without the controller ever going down is not
    C12 evidence (report 5.4)."""
    rows = [_restart_row(restart_downtime_evidence=False) for _ in range(3)]
    result = analyze.evaluate_acceptance(rows)
    assert _acc(result, "controller_restart", "restart_hook_executed_every_run")[
        "passed"
    ] is True
    downtime = _acc(
        result, "controller_restart", "restart_downtime_evidence_every_run"
    )
    assert downtime["passed"] is False
    assert "0/3 run(s) with controller downtime evidence" in downtime["observed"]


def test_acceptance_controller_restart_requires_endpoint_recovery_within_bound() -> None:
    rows = [_restart_row() for _ in range(3)]
    rows[0]["restart_metrics_endpoint_recovery_s"] = 600.0  # > RESTART_RECOVERY_MAX_S
    result = analyze.evaluate_acceptance(rows)
    recovery = _acc(
        result, "controller_restart", "restart_metrics_endpoint_recovery_within_bound"
    )
    assert recovery["passed"] is False
    assert "2/3 run(s)" in recovery["observed"]
    assert "120 s" in recovery["observed"]
    # The criterion must not read as functional readiness.
    assert "endpoint" in recovery["observed"]


def test_acceptance_controller_restart_requires_bounded_functional_recovery() -> None:
    rows = [_restart_row() for _ in range(3)]
    rows[0]["restart_functional_recovery_s"] = 400.0  # > RESTART_RECOVERY_MAX_S
    result = analyze.evaluate_acceptance(rows)
    functional = _acc(
        result, "controller_restart", "restart_functional_recovery_within_bound"
    )
    assert functional["passed"] is False
    assert "2/3 run(s)" in functional["observed"]
    assert "120 s" in functional["observed"]


def test_acceptance_controller_restart_functional_recovery_is_never_blank() -> None:
    """No post-restart evidence of resumed ingestion is a FAILURE, and it is
    reported apart from missing instrumentation; neither is blank."""
    rows = [
        _restart_row(restart_functional_recovery_s=None),
        _restart_row(restart_functional_recovery_s=None),
        _restart_row(
            restart_functional_recovery_s=None,
            restart_functional_recovery_source=None,
        ),
    ]
    result = analyze.evaluate_acceptance(rows)
    functional = _acc(
        result, "controller_restart", "restart_functional_recovery_within_bound"
    )
    assert functional["passed"] is False
    assert "0/3 run(s)" in functional["observed"]
    assert "no post-restart evidence of resumed ingestion in 2 run(s)" in (
        functional["observed"]
    )
    assert "insufficient instrumentation in 1 run(s)" in functional["observed"]


def test_acceptance_controller_restart_requires_accepted_progress() -> None:
    rows = [_restart_row() for _ in range(3)]
    rows[2]["restart_accepted_progress"] = 0.0
    result = analyze.evaluate_acceptance(rows)
    progress = _acc(result, "controller_restart", "restart_accepted_progress_after")
    assert progress["passed"] is False
    assert "2/3 run(s) with accepted-counter progress" in progress["observed"]


def test_acceptance_controller_restart_recovery_criteria_pass_when_demonstrated() -> None:
    rows = [_restart_row() for _ in range(3)]
    result = analyze.evaluate_acceptance(rows)
    for criterion in (
        "restart_downtime_evidence_every_run",
        "restart_metrics_endpoint_recovery_within_bound",
        "restart_functional_recovery_within_bound",
        "restart_accepted_progress_after",
    ):
        assert _acc(result, "controller_restart", criterion)["passed"] is True


def test_acceptance_controller_restart_without_instrumentation_fails_loudly() -> None:
    """Missing series => the criteria FAIL as 'insufficient instrumentation',
    never blank (report 5.4)."""
    rows = [
        _restart_row(
            restart_downtime_evidence=None,
            restart_metrics_endpoint_recovery_s=None,
            restart_accepted_progress=None,
            restart_functional_recovery_s=None,
            restart_functional_recovery_source=None,
        )
        for _ in range(3)
    ]
    result = analyze.evaluate_acceptance(rows)
    for criterion in (
        "restart_downtime_evidence_every_run",
        "restart_metrics_endpoint_recovery_within_bound",
        "restart_functional_recovery_within_bound",
        "restart_accepted_progress_after",
    ):
        row = _acc(result, "controller_restart", criterion)
        assert row["passed"] is False, criterion
        assert "insufficient instrumentation in 3 run(s)" in row["observed"]


def test_acceptance_end_to_end_controller_restart_recovery_from_files(
    tmp_path,
) -> None:
    """The three C12 recovery criteria are computed end-to-end from the
    files the harness already writes."""
    base = tmp_path / "results"
    start = T0
    end = T0 + timedelta(seconds=600)
    metrics = [
        [_iso(start + timedelta(seconds=i)), i, 0, 0, 0, 0, 1]
        for i in range(0, 296)
    ]
    metrics += [
        [_iso(start + timedelta(seconds=i)), i - 320, 0, 0, 0, 0, 1]
        for i in range(320, 601)
    ]
    mids = [f"m{i}" for i in range(3)]
    for rep in (1, 2, 3):
        make_run(
            base,
            f"controller_restart-r{rep:02d}",
            sent=[sent_record(m, i) for i, m in enumerate(mids)],
            events=[event_record(m, "accepted") for m in mids],
            manifest_extra={
                "condition_id": "controller_restart",
                "scenario": "nominal",
                "repetition": rep,
                **_window_manifest(start, end),
                **_restart_record(
                    start + timedelta(seconds=300),
                    start + timedelta(seconds=310),
                ),
            },
            controller_metrics_rows=metrics,
        )
    assert analyze.analyze(base_dir=base) == 0
    acceptance = _read_csv(base / "processed" / "acceptance_by_condition.csv")
    restart = {
        r["criterion"]: r
        for r in acceptance
        if r["condition_id"] == "controller_restart"
    }
    for criterion in (
        "runs_complete",
        "restart_hook_executed_every_run",
        "delivery_across_restart_zero_lost",
        "zero_double_accepted",
        "restart_downtime_evidence_every_run",
        "restart_metrics_endpoint_recovery_within_bound",
        "restart_functional_recovery_within_bound",
        "restart_accepted_progress_after",
    ):
        assert restart[criterion]["passed"] == "true", criterion


def test_acceptance_end_to_end_endpoint_recovery_without_ingestion_fails(
    tmp_path,
) -> None:
    """The C12 bound must be about functional readiness: an endpoint that
    answers 10 s after the restart while ingestion only resumes 401 s later
    passes the endpoint observation and FAILS the functional criterion
    (sprint P5.4)."""
    base = tmp_path / "results"
    start = T0
    end = T0 + timedelta(seconds=900)
    metrics = [
        [_iso(start + timedelta(seconds=i)), i, 0, 0, 0, 0, 1]
        for i in range(0, 296)
    ]
    # GET /metrics answers again at +320 s, but the accepted counter is
    # frozen: nothing is being ingested.
    metrics += [
        [_iso(start + timedelta(seconds=i)), 295, 0, 0, 0, 0, 1]
        for i in range(320, 711)
    ]
    metrics += [
        [_iso(start + timedelta(seconds=i)), 295 + (i - 710), 0, 0, 0, 0, 1]
        for i in range(711, 901)
    ]
    mids = [f"m{i}" for i in range(3)]
    for rep in (1, 2, 3):
        make_run(
            base,
            f"controller_restart-r{rep:02d}",
            sent=[sent_record(m, i) for i, m in enumerate(mids)],
            events=[event_record(m, "accepted") for m in mids],
            manifest_extra={
                "condition_id": "controller_restart",
                "scenario": "nominal",
                "repetition": rep,
                **_window_manifest(start, end),
                **_restart_record(
                    start + timedelta(seconds=300),
                    start + timedelta(seconds=310),
                ),
            },
            controller_metrics_rows=metrics,
        )
    assert analyze.analyze(base_dir=base) == 0

    acceptance = _read_csv(base / "processed" / "acceptance_by_condition.csv")
    restart = {
        r["criterion"]: r
        for r in acceptance
        if r["condition_id"] == "controller_restart"
    }
    assert restart["restart_metrics_endpoint_recovery_within_bound"]["passed"] == "true"
    # The legacy unbounded progress check also passes on this run.
    assert restart["restart_accepted_progress_after"]["passed"] == "true"
    functional = restart["restart_functional_recovery_within_bound"]
    assert functional["passed"] == "false"
    assert "0/3 run(s)" in functional["observed"]

    per_run = {r["run_id"]: r for r in _read_csv(base / "processed" / "per_run.csv")}
    row = per_run["controller_restart-r01"]
    assert float(row["restart_metrics_endpoint_recovery_s"]) == 10.0
    assert float(row["restart_functional_recovery_s"]) == 401.0
    assert row["restart_functional_recovery_source"] == "metrics-accepted-counter"


# ---------------------------------------------------------------------------
# per_run.csv records which confirmation deadline was used (report 5.2)
# ---------------------------------------------------------------------------


def test_per_run_csv_records_confirmation_deadline_source(tmp_path) -> None:
    base = tmp_path / "results"
    make_run(
        base,
        "nominal-r01",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
    )
    make_run(
        base,
        "nominal-r02",
        sent=[sent_record("m0")],
        events=[event_record("m0", "accepted")],
        manifest_extra={
            "repetition": 2,
            "confirmation_deadline_monotonic_ns": None,
            "confirmation_deadline_clock_domain": "unavailable",
        },
    )
    assert analyze.analyze(base_dir=base) == 0
    per_run = {r["run_id"]: r for r in _read_csv(base / "processed" / "per_run.csv")}
    assert per_run["nominal-r01"]["confirmation_deadline_source"] == "controller-marker"
    assert (
        per_run["nominal-r02"]["confirmation_deadline_source"]
        == "event-derived-legacy"
    )
    assert "LEGACY/UNVERIFIABLE" in per_run["nominal-r02"]["warnings"]
    assert "LEGACY/UNVERIFIABLE" not in per_run["nominal-r01"]["warnings"]
