"""Tests for egw_experiments.generator_check (G4 pilot prerequisite P5).

Every simulator output is produced by the REAL ``egw_simulator.runner.run``
into ``tmp_path`` on a fake monotonic clock, so the stall and catch-up
regressions exercise the run loop's own catch-up code, not a synthetic file.
The fakes stall inside one publish call, oversleep once, cost more than the
scheduled interval per call, delay the acknowledgement or fail mid-run. No
broker, no socket, no real sleeping; the checks go through ``cli.main``.
"""
from __future__ import annotations

import errno
import functools
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from egw_experiments import cli
from egw_experiments import generator_check as gc
from egw_experiments.checksums import write_sha256sums
from egw_experiments.run import SUBPROCESS_GRACE_S
from egw_simulator.devices import make_devices, split_rate
from egw_simulator.publisher import InMemoryPublisher, PublishResult
from egw_simulator.runner import RunConfig, run, scheduled_times
from egw_simulator.validation import SchemaValidator

SRC_DIR = Path(__file__).resolve().parents[1]
PROPOSED_PROFILE = (
    SRC_DIR.parent / "experiments" / "g4-pilot" / "generator_tolerances.proposed.json"
)
NS = 1_000_000_000
T0_S = 1_000.0  # the fake monotonic clock at the start of every simulated run
STARTED_BEFORE_S = 0.15  # harness stamp before the run loop's origin
FINISHED_AFTER_S = 0.05  # harness stamp after the run loop returned
RUN_ID = "gc-run"
PROFILE_A = {
    "max_relative_lateness_ms": 20.0,
    "max_overrun_events": 0,
    "max_span_deviation_ms": 20.0,
}
APPROVAL = {
    "approved_by": "test",
    "decision_record": "tests/test_generator_check.py",
    "date": "2026-10-07",
}
_DEFAULT = object()
_OUT = itertools.count()


# ---------------------------------------------------------------------------
# Fakes: clocks and publishers driving the real run loop
# ---------------------------------------------------------------------------


class FakeClock:
    """Monotonic fake as in test_simulator_runner: sleep() advances time
    instantly. It starts at ``T0_S`` so every stamp is a positive integer."""

    def __init__(self) -> None:
        self.start = T0_S
        self.t = T0_S

    def monotonic(self) -> float:
        return self.t

    def monotonic_ns(self) -> int:
        return int(self.t * 1e9)

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.t += seconds


class StallingClock(FakeClock):
    """Oversleeps once: the first sleep that ends at or after ``at_s`` (run
    offset) returns ``stall_s`` late, as a descheduled process would."""

    def __init__(self, at_s: float, stall_s: float) -> None:
        super().__init__()
        self.at_s = at_s
        self.stall_s = stall_s
        self.stalled = False

    def sleep(self, seconds: float) -> None:
        super().sleep(seconds)
        if not self.stalled and self.t - self.start >= self.at_s:
            self.stalled = True
            self.t += self.stall_s


class StallOncePublisher(InMemoryPublisher):
    """The first publish call at or after ``at_s`` (run offset) blocks for
    ``stall_s`` after its stamp was taken, as a slow client call would."""

    def __init__(self, clock: FakeClock, at_s: float, stall_s: float) -> None:
        super().__init__(clock=clock)
        self.clock = clock
        self.at_s = at_s
        self.stall_s = stall_s
        self.stalled = False

    def publish(self, topic, payload, *, wait_budget_s: float = 0.0):
        result = super().publish(topic, payload, wait_budget_s=wait_budget_s)
        if not self.stalled and self.clock.t - self.clock.start >= self.at_s:
            self.stalled = True
            self.clock.sleep(self.stall_s)
        return result


class CostlyPublisher(InMemoryPublisher):
    """Every publish call costs ``cost_s`` after its stamp: a generator that
    cannot keep up with the schedule (sustained shortfall)."""

    def __init__(self, clock: FakeClock, cost_s: float) -> None:
        super().__init__(clock=clock)
        self.clock = clock
        self.cost_s = cost_s

    def publish(self, topic, payload, *, wait_budget_s: float = 0.0):
        result = super().publish(topic, payload, wait_budget_s=wait_budget_s)
        self.clock.sleep(self.cost_s)
        return result


class FailingPublisher(InMemoryPublisher):
    """Raises at the ``fail_at``-th publish call (0-based): an interrupted run."""

    def __init__(self, clock: FakeClock, fail_at: int) -> None:
        super().__init__(clock=clock)
        self.fail_at = fail_at

    def publish(self, topic, payload, *, wait_budget_s: float = 0.0):
        if len(self.records) == self.fail_at:
            raise RuntimeError("connection lost")
        return super().publish(topic, payload, wait_budget_s=wait_budget_s)


class StartStallPublisher(InMemoryPublisher):
    """The first publish call waits ``stall_s`` BEFORE its stamp is taken:
    a start stall (first-call cost, a descheduled process) after which the
    run loop catches up, so the first event is the late one."""

    def __init__(self, clock: FakeClock, stall_s: float) -> None:
        super().__init__(clock=clock)
        self.clock = clock
        self.stall_s = stall_s

    def publish(self, topic, payload, *, wait_budget_s: float = 0.0):
        if not self.records:
            self.clock.sleep(self.stall_s)
        return super().publish(topic, payload, wait_budget_s=wait_budget_s)


class DelayedAckPublisher:
    """Fake broker whose PUBACK arrives ``ack_delay_s`` after each publish
    (as in test_simulator_runner): the wait is bounded by the budget, the
    puback is None when the delay does not fit it."""

    def __init__(self, clock: FakeClock, ack_delay_s: float) -> None:
        self.clock = clock
        self.ack_delay_s = ack_delay_s

    def connect(self) -> None:
        pass

    def publish(self, topic, payload, *, wait_budget_s: float = 0.0):
        publish_ns = self.clock.monotonic_ns()
        if wait_budget_s >= self.ack_delay_s:
            self.clock.sleep(self.ack_delay_s)
            return PublishResult(publish_ns, self.clock.monotonic_ns())
        self.clock.sleep(wait_budget_s)
        return PublishResult(publish_ns, None)

    def drain(self, timeout_s: float = 60.0) -> bool:
        return True

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Runs, profiles and checks
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _validator() -> SchemaValidator:
    return SchemaValidator()


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def config(output_dir: Path, *, run_id: str = RUN_ID, scenario: str = "smoke",
           duration_s: float = 10.0, rate: float = 11.2, seed: int = 7) -> RunConfig:
    return RunConfig(
        scenario=scenario, seed=seed, run_id=run_id, egw_id="egw-01",
        duration_s=duration_s, aggregate_rate_hz=rate, broker_host="127.0.0.1",
        broker_port=8883, output_dir=output_dir,
    )


def seal(run_dir: Path) -> Path:
    """(Re)write the run directory's SHA256SUMS, as the harness seals a run;
    a test that edits a sealed run on purpose re-seals it so that the defect
    under test, not the seal, is what the check must find."""
    write_sha256sums(run_dir)
    return run_dir


def simulate(root: Path, *, run_id: str = RUN_ID, scenario: str = "smoke",
             duration_s: float = 10.0, rate: float = 11.2, seed: int = 7,
             clock: FakeClock | None = None, publisher=None,
             harness_extra: dict | None = None) -> Path:
    """Run the real run loop into a harness-shaped run directory and return
    it: logs/simulator/<run_id>/, the root copy of sent_events.jsonl, a
    harness manifest whose stamps bracket the run on the same fake clock and
    the SHA256SUMS seal over all of it. The harness manifest records the
    requested load in the top-level fields run.py writes (``scenario``,
    ``seed``, ``rate_msg_s``, ``duration_s`` and ``warmup_s``, 0 here: no
    warm-up); ``harness_extra`` overrides any of them."""
    clock = clock if clock is not None else FakeClock()
    pub = publisher(clock) if publisher is not None else InMemoryPublisher(clock=clock)
    run_dir = root / "raw" / run_id
    started_ns = int(round((clock.t - STARTED_BEFORE_S) * 1e9))
    result = run(
        config(run_dir / "logs" / "simulator", run_id=run_id, scenario=scenario,
               duration_s=duration_s, rate=rate, seed=seed),
        pub, clock=clock, validator=_validator(),
    )
    shutil.copyfile(result.sent_events_path, run_dir / "sent_events.jsonl")
    write_json(run_dir / "manifest.json", {
        "run_id": run_id,
        "scenario": scenario,
        "seed": seed,
        "rate_msg_s": rate,
        "duration_s": duration_s,
        "warmup_s": 0,
        "measured_started_monotonic_ns": started_ns,
        "finished_monotonic_ns": clock.monotonic_ns() + int(FINISHED_AFTER_S * 1e9),
        "simulator_returncode": 0,
        **(harness_extra or {}),
    })
    return seal(run_dir)


def sim_dir(run_dir: Path, run_id: str = RUN_ID) -> Path:
    return run_dir / "logs" / "simulator" / run_id


def warm_up(run_dir: Path, *, duration_s: float = 2.0, **load) -> Path:
    """Run the real run loop as the harness's warm-up of ``run_dir``
    (logs/warmup/<run_id>.warmup/, the measured run's scenario, seed and
    rate unless ``load`` says otherwise) and re-seal the run directory."""
    clock = FakeClock()
    run(config(run_dir / "logs" / "warmup", run_id=f"{RUN_ID}.warmup",
               duration_s=duration_s, **load),
        InMemoryPublisher(clock=clock), clock=clock, validator=_validator())
    return seal(run_dir)


def expected_events(rate: float, duration_s: float) -> int:
    return sum(len(scheduled_times(r, duration_s)) for r in split_rate(rate).values())


def write_profile(path: Path, *, status: str = "approved", approval=_DEFAULT,
                  conditions: dict | None = None, **extra) -> Path:
    doc = {
        "profile_id": "test-profile",
        "status": status,
        "approval": (dict(APPROVAL) if status == "approved" else None)
        if approval is _DEFAULT else approval,
        "rate_key": "<scenario>@<aggregate rate>",
        "basis": "test fixture",
        "conditions": conditions if conditions is not None
        else {"smoke@11.2": dict(PROFILE_A)},
    }
    doc.update(extra)
    write_json(path, doc)
    return path


def check(tmp_path: Path, *argv) -> tuple[int, dict]:
    """Run ``generator-check`` with a fresh --out; return (exit code, report)."""
    out = tmp_path / "checks" / f"{next(_OUT)}.json"
    rc = cli.main(["generator-check", *(str(a) for a in argv), "--out", str(out)])
    return rc, json.loads(out.read_text(encoding="utf-8"))


def approved(tmp_path: Path, **kwargs) -> Path:
    return write_profile(tmp_path / f"profile-{next(_OUT)}.json", **kwargs)


def tree(path: Path) -> dict:
    """Every file and directory under ``path`` with its bytes (None for a
    directory): equal before and after means nothing was written there."""
    return {
        str(p.relative_to(path)): (p.read_bytes() if p.is_file() else None)
        for p in sorted(path.rglob("*"))
    }


# ---------------------------------------------------------------------------
# 1. Correct cadence
# ---------------------------------------------------------------------------


def test_correct_cadence_is_sustained_under_an_approved_profile(tmp_path, capsys) -> None:
    run_dir = simulate(tmp_path)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == gc.EXIT_SUSTAINED == 0
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "SUSTAINED" and evaluation["certifying"] is True
    assert evaluation["rate_key"] == "smoke@11.2"
    assert [row["within"] for row in evaluation["per_tolerance"]] == [True, True, True]

    n = expected_events(11.2, 10.0)
    identity = rep["identity"]
    assert identity["exact"] is True
    assert identity["records"] == identity["totals_sent"] == rep["schedule"]["events_expected"] == n
    assert identity["missing"]["count"] == identity["duplicates"]["count"] == 0
    assert rep["inputs"]["root_copy"]["identical"] is True
    assert rep["inputs"]["problem_count"] == 0
    assert rep["inputs"]["seal"]["state"] == "verified"

    timing = rep["generator_timing"]
    assert timing["applicable"] is True and timing["partial"] is False
    assert "host" in timing["clock_domain"]
    assert "not" in timing["measures"] and "broker ingress" in timing["measures"]
    assert timing["overruns"]["events"] == 0 and timing["overruns"]["bursts"] == 0
    assert 0.0 <= timing["relative_lateness_ms"]["max"] <= 0.001
    assert timing["span"]["scheduled_s"] == pytest.approx(9.9)
    assert abs(timing["span"]["deviation_ms"]) <= 0.001
    assert timing["windows"]["nonzero"] == 0
    assert timing["publish_gaps_ms"]["max"] == pytest.approx(100.0, abs=0.001)
    assert "cannot detect a mid-run stall" in timing["summary_rates"]["note"]

    out = capsys.readouterr().out
    assert "verdict: SUSTAINED" in out
    assert "host monotonic clock" in out and "not evidence of loss" in out
    assert "acceptance" in out and "not requested" in out


# ---------------------------------------------------------------------------
# 2. Same count, identity and span with a stall and catch-up
# ---------------------------------------------------------------------------

STALL_S = 0.5


@pytest.mark.parametrize("make_clock,make_publisher", [
    pytest.param(FakeClock, lambda clock: StallOncePublisher(clock, 4.15, STALL_S),
                 id="slow-publish-call"),
    pytest.param(lambda: StallingClock(4.25, STALL_S), None, id="oversleep"),
])
def test_a_stall_with_catch_up_keeps_count_and_span_but_is_detected(
    tmp_path, make_clock, make_publisher
) -> None:
    profile = approved(tmp_path)
    base_dir = simulate(tmp_path / "base")
    stall_dir = simulate(tmp_path / "stall", clock=make_clock(), publisher=make_publisher)
    rc_base, base = check(tmp_path, "--run-dir", base_dir, "--tolerances", profile)
    rc, rep = check(tmp_path, "--run-dir", stall_dir, "--tolerances", profile)
    assert rc_base == 0

    # What a mean over the span sees: nothing at all.
    ids = [r["message_id"] for r in read_jsonl(stall_dir / "sent_events.jsonl")]
    base_ids = [r["message_id"] for r in read_jsonl(base_dir / "sent_events.jsonl")]
    assert sorted(ids) == sorted(base_ids) and len(ids) == len(set(ids))
    assert rep["identity"]["exact"] is True
    assert rep["identity"]["records"] == base["identity"]["records"]
    span, base_span = rep["generator_timing"]["span"], base["generator_timing"]["span"]
    assert span["published_s"] == pytest.approx(base_span["published_s"], abs=2e-9)
    rates = rep["generator_timing"]["summary_rates"]
    assert rates["first_to_last_hz"] == pytest.approx(
        base["generator_timing"]["summary_rates"]["first_to_last_hz"], rel=1e-9
    )

    # What the schedule sees: overruns, a catch-up burst, the lateness and
    # the gap of the stall.
    timing = rep["generator_timing"]
    assert timing["overruns"]["events"] > 0 and timing["overruns"]["bursts"] == 1
    largest = timing["overruns"]["largest"]
    assert abs(largest["events"] - STALL_S * 11.2) <= 3  # one coincident group
    assert 4.2 <= largest["first_offset_s"] <= largest["last_offset_s"] <= 4.8
    lateness = timing["relative_lateness_ms"]["max"]
    assert STALL_S * 1000 - 100.0 - 0.001 <= lateness <= STALL_S * 1000 + 0.001
    assert largest["stall_estimate_ms"] == pytest.approx(lateness, abs=0.001)
    gap = timing["publish_gaps_ms"]["max"]
    assert STALL_S * 1000 - 0.001 <= gap <= STALL_S * 1000 + 100.0 + 0.001
    # The stall starts and ends inside one 1 s window: invisible there.
    assert timing["windows"]["nonzero"] == 0

    assert rc == gc.EXIT_NOT_SUSTAINED == 4
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_SUSTAINED" and evaluation["certifying"] is True
    outside = {row["name"] for row in evaluation["per_tolerance"] if not row["within"]}
    assert outside == {"max_relative_lateness_ms", "max_overrun_events"}


START_STALL_S = 0.25


def test_a_start_stall_with_catch_up_is_not_sustained(tmp_path) -> None:
    """The first event is the late one: anchoring on the first record would
    hide the stall (lateness 0, no overrun) and a signed span deviation
    (negative here) would pass. The anchor is the minimum over the records
    and the span deviation is compared in absolute value."""
    run_dir = simulate(tmp_path, publisher=lambda clock: StartStallPublisher(clock, START_STALL_S))
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rep["identity"]["exact"] is True
    timing = rep["generator_timing"]
    lateness = timing["relative_lateness_ms"]
    assert lateness["max"] == pytest.approx(START_STALL_S * 1000, abs=0.001)
    assert lateness["max_offset_s"] == 0.0  # the first scheduled instant
    overruns = timing["overruns"]
    assert overruns["events"] > 0 and overruns["bursts"] == 1
    assert overruns["largest"]["first_offset_s"] == 0.0  # the burst opens the run
    assert overruns["largest"]["stall_estimate_ms"] == pytest.approx(
        START_STALL_S * 1000, abs=0.001)
    assert timing["span"]["deviation_ms"] == pytest.approx(-START_STALL_S * 1000, abs=0.001)

    assert rc == gc.EXIT_NOT_SUSTAINED == 4
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_SUSTAINED" and evaluation["certifying"] is True
    rows = {row["name"]: row for row in evaluation["per_tolerance"]}
    assert {name for name, row in rows.items() if not row["within"]} == {
        "max_relative_lateness_ms", "max_overrun_events", "max_span_deviation_ms"}
    assert rows["max_span_deviation_ms"]["value"] == pytest.approx(
        START_STALL_S * 1000, abs=0.001)


# ---------------------------------------------------------------------------
# 3. Sustained shortfall
# ---------------------------------------------------------------------------


def test_a_sustained_shortfall_stretches_the_span_and_is_not_sustained(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0,
                       publisher=lambda clock: CostlyPublisher(clock, 0.15))
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 4 and rep["evaluation"]["verdict"] == "NOT_SUSTAINED"
    assert rep["identity"]["exact"] is True  # every event published, just late
    timing = rep["generator_timing"]
    assert timing["span"]["deviation_ms"] > 1000.0  # stretched
    assert timing["relative_lateness_ms"]["max"] > 1000.0
    assert timing["relative_lateness_ms"]["max_offset_s"] >= 2.5  # grows to the end
    # Only in this case does the mean over the span move as well.
    assert timing["summary_rates"]["first_to_last_hz"] < 0.75 * 11.2
    assert all(not row["within"] for row in rep["evaluation"]["per_tolerance"])


# ---------------------------------------------------------------------------
# 4. Incomplete or unreadable records: NOT_SHOWN, never SUSTAINED
# ---------------------------------------------------------------------------


def _both_copies(run_dir: Path) -> list[Path]:
    return [sim_dir(run_dir) / "sent_events.jsonl", run_dir / "sent_events.jsonl"]


def _edit_lines(edit, *, root_only: bool = False):
    def mutate(run_dir: Path) -> None:
        paths = _both_copies(run_dir)[1:] if root_only else _both_copies(run_dir)
        for path in paths:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            path.write_text("".join(edit(lines)), encoding="utf-8", newline="\n")
    return mutate


def _set(index: int, **changes):
    def edit(lines):
        record = json.loads(lines[index])
        record.update(changes)
        lines[index] = json.dumps(record, separators=(",", ":")) + "\n"
        return lines
    return edit


def _drop(index: int, key: str):
    def edit(lines):
        record = json.loads(lines[index])
        del record[key]
        lines[index] = json.dumps(record, separators=(",", ":")) + "\n"
        return lines
    return edit


def _replace(index: int, text: str):
    def edit(lines):
        lines[index] = text
        return lines
    return edit


def _insert(index: int, text: str):
    def edit(lines):
        lines.insert(index, text)
        return lines
    return edit


def _truncate_last(lines):
    lines[-1] = lines[-1][: len(lines[-1]) // 2]
    return lines


def _duplicate(index: int):
    def edit(lines):
        lines.append(lines[index])
        return lines
    return edit


def _delete(index: int):
    def edit(lines):
        del lines[index]
        return lines
    return edit


def _swap_publish(i: int, j: int):
    def edit(lines):
        a, b = json.loads(lines[i]), json.loads(lines[j])
        a["publish_monotonic_ns"], b["publish_monotonic_ns"] = (
            b["publish_monotonic_ns"], a["publish_monotonic_ns"])
        lines[i] = json.dumps(a, separators=(",", ":")) + "\n"
        lines[j] = json.dumps(b, separators=(",", ":")) + "\n"
        return lines
    return edit


def _sim_manifest(edit):
    def mutate(run_dir: Path) -> None:
        path = sim_dir(run_dir) / "manifest.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        edit(doc)
        write_json(path, doc)
    return mutate


def _write(relative: str, data: bytes):
    def mutate(run_dir: Path) -> None:
        (run_dir / relative).write_bytes(data)
    return mutate


def _unlink(relative: str):
    def mutate(run_dir: Path) -> None:
        (run_dir / relative).unlink()
    return mutate


def _harness(**changes):
    def mutate(run_dir: Path) -> None:
        doc = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        doc.update(changes)
        write_json(run_dir / "manifest.json", doc)
    return mutate


SIM = f"logs/simulator/{RUN_ID}"

DEFECTS = [
    pytest.param(_edit_lines(_truncate_last), "truncated", id="truncated-last-line"),
    pytest.param(_edit_lines(_replace(4, "not json\n")), "line 5: not valid JSON",
                 id="not-json-line"),
    pytest.param(_edit_lines(_insert(5, "\n")), "line 6: empty line", id="blank-line"),
    pytest.param(_edit_lines(_drop(2, "publish_monotonic_ns")),
                 "line 3: missing field(s) publish_monotonic_ns", id="missing-publish-stamp"),
    pytest.param(_edit_lines(_set(2, extra=1)), "line 3: unexpected field(s) extra",
                 id="extra-field"),
    pytest.param(_edit_lines(_set(2, seq=True)), "line 3: seq", id="seq-bool"),
    pytest.param(_edit_lines(_set(2, publish_monotonic_ns="1000000000000")),
                 "line 3: publish_monotonic_ns", id="ns-as-string"),
    pytest.param(_edit_lines(_set(2, puback_monotonic_ns=1.5)),
                 "line 3: puback_monotonic_ns", id="puback-float"),
    # Valid JSON integers no monotonic_ns stamp can be: named, never an OverflowError.
    pytest.param(_edit_lines(_set(2, publish_monotonic_ns=10**400)),
                 "line 3: publish_monotonic_ns", id="ns-beyond-64-bits"),
    pytest.param(_edit_lines(_set(2, puback_monotonic_ns=10**400)),
                 "line 3: puback_monotonic_ns", id="puback-beyond-64-bits"),
    pytest.param(_edit_lines(_set(2, intended_invalid=0)), "line 3: intended_invalid",
                 id="flag-not-bool"),
    pytest.param(_edit_lines(_set(2, run_id="other-run")), "run_id other than",
                 id="foreign-run-id"),
    pytest.param(_edit_lines(_duplicate(2)), "duplicate", id="duplicate-line"),
    pytest.param(_edit_lines(_set(2, message_id=str(uuid.uuid4()))), "message_id",
                 id="wrong-message-id"),
    pytest.param(_edit_lines(_set(2, device_type="smart_ring")), "device_type",
                 id="wrong-device-type"),
    pytest.param(_edit_lines(_set(2, seq=10_000)), "beyond their device's schedule",
                 id="seq-out-of-range"),
    pytest.param(_edit_lines(_set(2, intended_invalid=True)), "intended_invalid",
                 id="flag-not-the-injectors"),
    pytest.param(_edit_lines(_delete(9)), "totals.sent", id="deleted-line"),
    pytest.param(_edit_lines(_swap_publish(2, 3)), "decreases", id="publish-order"),
    pytest.param(_unlink(f"{SIM}/manifest.json"), "manifest.json missing",
                 id="manifest-missing"),
    pytest.param(_write(f"{SIM}/manifest.json", b"[]"), "not a JSON object",
                 id="manifest-not-an-object"),
    pytest.param(_write(f"{SIM}/manifest.json", b"{"), "manifest.json unreadable",
                 id="manifest-not-json"),
    pytest.param(_sim_manifest(lambda d: d["rates_hz"]["per_device"].update(smart_ring=0.2)),
                 "per_device", id="per-device-rate-edited"),
    pytest.param(_sim_manifest(lambda d: d.update(seed=8)), "make_devices",
                 id="seed-edited"),
    pytest.param(_sim_manifest(lambda d: d["totals"].update(sent=d["totals"]["sent"] + 1)),
                 "totals.sent", id="totals-edited"),
    pytest.param(_sim_manifest(lambda d: d.update(scenario="walk")), "scenario",
                 id="unknown-scenario"),
    pytest.param(_sim_manifest(lambda d: d.update(run_id="other-run")),
                 "is not the harness run's", id="simulator-manifest-of-another-run"),
    pytest.param(_harness(run_id="other-run"), "other-run", id="harness-manifest-of-another-run"),
    pytest.param(_edit_lines(_set(2, puback_monotonic_ns=None), root_only=True),
                 "root copy", id="root-copy-differs"),
    pytest.param(_unlink("sent_events.jsonl"), "root copy", id="root-copy-missing"),
    pytest.param(_unlink(f"{SIM}/sent_events.jsonl"), "sent_events.jsonl missing",
                 id="sent-events-missing"),
    pytest.param(_write(f"{SIM}/sent_events.jsonl", b"\xff\xfe{}\n"), "UTF-8",
                 id="sent-events-not-utf8"),
]


@pytest.mark.parametrize("mutate,expected", DEFECTS)
def test_incomplete_or_unreadable_records_are_not_shown(tmp_path, capsys, mutate, expected) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    mutate(run_dir)
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == gc.EXIT_NOT_SHOWN == 1
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_SHOWN" and evaluation["certifying"] is False
    assert evaluation["per_tolerance"] == []
    assert any(expected in reason for reason in evaluation["reasons"]), evaluation["reasons"]
    assert rep["inputs"]["problem_count"] > 0
    if rep["generator_timing"] is not None:
        assert rep["generator_timing"]["partial"] is True
    assert expected in capsys.readouterr().out


def test_a_whole_run_whose_manifest_says_not_completed_is_not_sustained(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    _sim_manifest(lambda d: d.update(completed=False))(run_dir)
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 4 and rep["evaluation"]["verdict"] == "NOT_SUSTAINED"
    assert any("completed" in reason for reason in rep["evaluation"]["reasons"])
    assert rep["identity"]["consistent"] is True and rep["identity"]["exact"] is False


def test_an_interrupted_run_is_not_sustained(tmp_path) -> None:
    clock = FakeClock()
    with pytest.raises(RuntimeError, match="connection lost"):
        run(config(tmp_path / "sim", duration_s=3.0), FailingPublisher(clock, 20),
            clock=clock, validator=_validator())
    rc, rep = check(tmp_path, "--sim-dir", tmp_path / "sim" / RUN_ID,
                    "--tolerances", approved(tmp_path))
    assert rc == 4 and rep["evaluation"]["verdict"] == "NOT_SUSTAINED"
    identity = rep["identity"]
    assert identity["consistent"] is True and identity["exact"] is False
    assert identity["records"] == identity["totals_sent"] == 20
    assert identity["missing"]["count"] == expected_events(11.2, 3.0) - 20


def test_an_interrupted_run_whose_records_are_not_a_schedule_prefix_is_not_shown(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    _sim_manifest(lambda d: d.update(completed=False))(run_dir)
    _edit_lines(_delete(9))(run_dir)
    _sim_manifest(lambda d: d["totals"].update(sent=d["totals"]["sent"] - 1))(run_dir)
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir)
    assert rc == 1
    assert any("prefix" in reason for reason in rep["evaluation"]["reasons"])


def _strict_json(path: Path):
    """Read a report as strict JSON: NaN and infinities are refused."""
    def refuse(name):
        raise AssertionError(f"the report holds {name}, which is not JSON")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=refuse)


def _sim_manifest_literal(key: str, literal: str):
    """Set one top-level key of the simulator manifest to a raw JSON literal."""
    def mutate(run_dir: Path) -> None:
        path = sim_dir(run_dir) / "manifest.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc[key] = "@@literal@@"
        text = json.dumps(doc, indent=2).replace('"@@literal@@"', literal)
        path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return mutate


NON_FINITE = [
    pytest.param(_sim_manifest(lambda d: d["rates_hz"]["per_device"].update(smart_ring=math.nan)),
                 "NaN", id="per-device-rate-nan"),
    pytest.param(_sim_manifest(lambda d: d["rates_hz"].update(aggregate=math.nan)), "NaN",
                 id="aggregate-rate-nan"),
    pytest.param(_sim_manifest(lambda d: d.update(seed=math.inf)), "Infinity",
                 id="seed-infinity"),
    pytest.param(_sim_manifest(lambda d: d.update(duration_s=-math.inf)), "-Infinity",
                 id="duration-minus-infinity"),
    pytest.param(_sim_manifest(lambda d: d.update(completed=math.nan)), "NaN",
                 id="completed-nan"),
    pytest.param(_sim_manifest_literal("duration_s", "1e400"), "1e400",
                 id="duration-beyond-a-float"),
    pytest.param(_sim_manifest(lambda d: d["rates_hz"].update(aggregate=10**400)),
                 "rates_hz.aggregate", id="aggregate-integer-beyond-a-float"),
    pytest.param(_harness(execution_mode=math.nan), "NaN", id="harness-manifest-nan"),
]


@pytest.mark.parametrize("mutate,expected", NON_FINITE)
def test_a_manifest_number_json_cannot_hold_is_not_shown_and_reported(
    tmp_path, capsys, mutate, expected
) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    mutate(run_dir)
    seal(run_dir)
    out = tmp_path / "checks" / "report.json"
    argv = ["generator-check", "--run-dir", str(run_dir),
            "--tolerances", str(approved(tmp_path)), "--out", str(out)]
    assert cli.main(argv) == gc.EXIT_NOT_SHOWN == 1
    rep = _strict_json(out)  # written, and strict JSON
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_SHOWN" and evaluation["certifying"] is False
    assert any(expected in reason for reason in evaluation["reasons"]), evaluation["reasons"]
    printed = capsys.readouterr().out
    assert "verdict: NOT_SHOWN (exit 1)" in printed and f"wrote {out}" in printed


def test_a_run_with_no_scheduled_event_is_not_shown_and_reported(tmp_path) -> None:
    # The simulator accepts any duration above 0; below its schedule epsilon
    # the schedule is empty and the run writes no record.
    run_dir = simulate(tmp_path, duration_s=1e-10)
    assert (run_dir / "sent_events.jsonl").read_bytes() == b""
    out = tmp_path / "checks" / "report.json"
    argv = ["generator-check", "--run-dir", str(run_dir),
            "--tolerances", str(approved(tmp_path)), "--out", str(out)]
    assert cli.main(argv) == gc.EXIT_NOT_SHOWN == 1
    rep = _strict_json(out)
    assert rep["evaluation"]["verdict"] == "NOT_SHOWN"
    assert any("no scheduled event" in r for r in rep["evaluation"]["reasons"])
    assert rep["schedule"] is None and rep["generator_timing"] is None


def test_an_out_that_cannot_be_created_is_a_usage_error_without_a_verdict(tmp_path, capsys) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0)
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory\n", encoding="utf-8")
    out = blocker / "report.json"
    argv = ["generator-check", "--run-dir", str(run_dir),
            "--tolerances", str(approved(tmp_path)), "--out", str(out)]
    assert cli.main(argv) == gc.EXIT_USAGE == 2
    captured = capsys.readouterr()
    assert "cannot write" in captured.err and str(out) in captured.err
    assert "refusing to overwrite" not in captured.err
    # No verdict line: its exit code would not be the process's.
    assert "verdict:" not in captured.out
    assert blocker.read_text(encoding="utf-8") == "a file, not a directory\n"


class _FullDisk:
    """A file object whose write fails as on a full disk."""

    def __init__(self, fh) -> None:
        self.fh = fh

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        self.fh.close()
        return False

    def write(self, text: str) -> int:
        raise OSError(errno.ENOSPC, "No space left on device")

    def close(self) -> None:
        self.fh.close()


@pytest.mark.parametrize("failure,expected", [
    ("permission", "Permission denied"),
    ("full-disk", "No space left on device"),
])
def test_an_os_error_writing_the_report_exits_2_and_leaves_no_partial_report(
    tmp_path, capsys, monkeypatch, failure, expected
) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0)
    out = tmp_path / "checks" / "report.json"
    real_open = open

    def failing_open(path, mode="r", *args, **kwargs):
        if Path(path) == out:
            if failure == "permission":
                raise PermissionError(errno.EACCES, "Permission denied", str(path))
            return _FullDisk(real_open(path, mode, *args, **kwargs))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(gc, "open", failing_open, raising=False)
    argv = ["generator-check", "--run-dir", str(run_dir),
            "--tolerances", str(approved(tmp_path)), "--out", str(out)]
    assert cli.main(argv) == gc.EXIT_USAGE == 2
    captured = capsys.readouterr()
    assert "cannot write" in captured.err and expected in captured.err
    assert "verdict:" not in captured.out
    assert not out.exists()  # no partial report blocks a write-once retry


# ---------------------------------------------------------------------------
# 4b. With --run-dir the run's seal must verify; its manifest must be readable
# ---------------------------------------------------------------------------


def test_a_consistent_edit_the_seal_detects_is_not_shown(tmp_path, capsys) -> None:
    profile = approved(tmp_path)
    base_dir = simulate(tmp_path / "base")
    stall_dir = simulate(tmp_path / "stall",
                         publisher=lambda clock: StallOncePublisher(clock, 4.15, STALL_S))
    rc, rep = check(tmp_path, "--run-dir", stall_dir, "--tolerances", profile)
    assert rc == 4 and rep["inputs"]["seal"]["state"] == "verified"
    # The same edit to both copies passes the root-copy comparison and the
    # schedule: only the seal can show that these are not the run's records.
    for target, source in zip(_both_copies(stall_dir), _both_copies(base_dir)):
        shutil.copyfile(source, target)
    capsys.readouterr()
    rc, rep = check(tmp_path, "--run-dir", stall_dir, "--tolerances", profile)
    assert rc == gc.EXIT_NOT_SHOWN == 1
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_SHOWN" and evaluation["certifying"] is False
    assert evaluation["per_tolerance"] == []
    assert rep["inputs"]["root_copy"]["identical"] is True
    assert rep["identity"]["exact"] is True  # the edit is otherwise invisible
    seal_info = rep["inputs"]["seal"]
    assert seal_info["state"] == "failed"
    assert seal_info["problems"] == [
        f"mismatch: logs/simulator/{RUN_ID}/sent_events.jsonl",
        "mismatch: sent_events.jsonl",
    ]
    assert any("SHA256SUMS" in r and "mismatch: sent_events.jsonl" in r
               for r in evaluation["reasons"]), evaluation["reasons"]
    assert "seal [SHA256SUMS]: FAILED" in capsys.readouterr().out


@pytest.mark.parametrize("mutate,state,expected", [
    pytest.param(_unlink("SHA256SUMS"), "missing", "SHA256SUMS missing", id="unsealed"),
    pytest.param(_write("added.txt", b"after the seal\n"), "failed", "unlisted: added.txt",
                 id="file-added-after-the-seal"),
    pytest.param(_unlink(f"{SIM}/manifest.json"), "failed",
                 f"missing: {SIM}/manifest.json", id="sealed-file-deleted"),
    pytest.param(_write("SHA256SUMS", b"not a sums line\n"), "failed", "malformed line 1",
                 id="malformed-seal"),
    pytest.param(_write("SHA256SUMS", b"\xff\xfe\n"), "unreadable", "SHA256SUMS",
                 id="seal-not-utf8"),
])
def test_a_run_dir_without_a_verified_seal_is_not_shown(tmp_path, mutate, state, expected) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0)
    mutate(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == gc.EXIT_NOT_SHOWN == 1
    assert rep["evaluation"]["verdict"] == "NOT_SHOWN"
    assert rep["inputs"]["seal"]["state"] == state
    assert any(expected in r for r in rep["evaluation"]["reasons"]), rep["evaluation"]["reasons"]


def test_a_bare_simulator_directory_has_no_seal_to_verify(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0)
    (run_dir / "SHA256SUMS").unlink()
    rc, rep = check(tmp_path, "--sim-dir", sim_dir(run_dir), "--tolerances", approved(tmp_path))
    assert rc == 0 and rep["evaluation"]["verdict"] == "SUSTAINED"
    assert rep["inputs"]["seal"]["applicable"] is False


@pytest.mark.parametrize("content,expected", [
    (b"{corrupt", "manifest.json unreadable"),
    (b"[]", "is not a JSON object"),
], ids=["not-json", "not-an-object"])
def test_an_unreadable_harness_manifest_is_not_shown(tmp_path, capsys, content, expected) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0, harness_extra={"execution_mode": "tcg-emulated"})
    (run_dir / "manifest.json").write_bytes(content)
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == gc.EXIT_NOT_SHOWN == 1
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_SHOWN"
    assert any(r.startswith("harness manifest: ") and expected in r
               for r in evaluation["reasons"]), evaluation["reasons"]
    run_section = rep["run"]
    assert run_section["execution_mode"] is None  # never inferred
    assert run_section["execution_mode_source"].startswith("harness manifest not usable: ")
    assert expected in run_section["execution_mode_source"]
    assert "no harness manifest" not in capsys.readouterr().out


def test_an_impossible_stamp_counts_as_no_stamp_in_non_certifying_sections(tmp_path) -> None:
    # The elapsed and acceptance sections never change the verdict: an
    # integer no monotonic_ns stamp can be is treated as no stamp there.
    run_dir = simulate(tmp_path, duration_s=2.0)
    _harness(measured_started_monotonic_ns=10**400)(run_dir)
    seal(run_dir)
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        "".join(json.dumps({"run_id": RUN_ID, "outcome": "accepted",
                            "received_monotonic_ns": stamp,
                            "ditto_ack_monotonic_ns": stamp}) + "\n"
                for stamp in (GUEST_OFFSET_NS, 10**400, GUEST_OFFSET_NS + GUEST_STEP_NS)),
        encoding="utf-8", newline="\n")
    out = tmp_path / "checks" / "report.json"
    argv = ["generator-check", "--run-dir", str(run_dir), "--events", str(events_path),
            "--tolerances", str(approved(tmp_path)), "--out", str(out)]
    assert cli.main(argv) == gc.EXIT_SUSTAINED == 0
    rep = _strict_json(out)
    assert rep["elapsed"]["measured_started_ns"] is None
    assert rep["generator_timing"]["anchor"]["c_upper_bound_s"] is None
    acceptance = rep["controller_acceptance"]
    assert acceptance["received_missing"] == acceptance["accepted_without_ack"] == 1
    assert acceptance["received"]["n"] == acceptance["accepted_ack"]["n"] == 2


# ---------------------------------------------------------------------------
# 4c. The simulator's records must be the load the harness requested (F1)
# ---------------------------------------------------------------------------

LOAD_KEYS = ("scenario", "seed", "rate_msg_s", "duration_s")


def _load_states(rep: dict) -> dict:
    return {row["harness_key"]: row["state"] for row in rep["load_reconciliation"]["fields"]}


def _harness_without(*keys: str):
    def mutate(run_dir: Path) -> None:
        doc = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        for key in keys:
            del doc[key]
        write_json(run_dir / "manifest.json", doc)
    return mutate


def test_the_reported_load_counterexample_is_not_shown(tmp_path, capsys) -> None:
    """A harness request for load-sweep, seed 8, 50 msg/s, 300 s, with
    same-id simulator records of nominal, seed 7, 11.2 msg/s, 1 s: certified
    SUSTAINED when only the run_id was compared."""
    run_dir = simulate(tmp_path, scenario="nominal", duration_s=1.0, harness_extra={
        "scenario": "load-sweep", "seed": 8, "rate_msg_s": 50.0, "duration_s": 300})
    profile = approved(tmp_path, conditions={"nominal@11.2": PROFILE_A,
                                             "load-sweep@50.0": PROFILE_A})
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", profile)
    assert rc == gc.EXIT_NOT_SHOWN == 1
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_SHOWN" and evaluation["certifying"] is False
    assert evaluation["per_tolerance"] == []
    assert _load_states(rep) == dict.fromkeys(LOAD_KEYS, "contradicts")
    assert rep["load_reconciliation"]["reconciled"] is False
    for key in LOAD_KEYS:
        assert any(f"harness manifest requested {key}" in r for r in evaluation["reasons"]), key
    assert "requested load" in capsys.readouterr().out


@pytest.mark.parametrize("changes,key", [
    pytest.param({"scenario": "nominal"}, "scenario", id="scenario"),
    pytest.param({"seed": 8}, "seed", id="seed"),
    pytest.param({"rate_msg_s": 50.0}, "rate_msg_s", id="rate"),
    pytest.param({"duration_s": 300}, "duration_s", id="duration"),
])
def test_a_measured_load_the_harness_did_not_request_is_not_shown(tmp_path, changes, key) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0, harness_extra=changes)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 1 and rep["evaluation"]["verdict"] == "NOT_SHOWN"
    assert rep["evaluation"]["certifying"] is False and rep["evaluation"]["per_tolerance"] == []
    states = _load_states(rep)
    assert states.pop(key) == "contradicts"
    assert set(states.values()) == {"agrees"}
    assert any(f"harness manifest requested {key}" in r for r in rep["evaluation"]["reasons"])


def test_a_measured_load_as_run_py_records_it_is_reconciled(tmp_path) -> None:
    # run.py records duration_s as an integer and rate_msg_s as a float; the
    # simulator records duration_s as a float: equal numbers agree.
    run_dir = simulate(tmp_path, duration_s=3.0, harness_extra={"duration_s": 3})
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 0 and rep["evaluation"]["verdict"] == "SUSTAINED"
    load = rep["load_reconciliation"]
    assert load["applicable"] is True and load["reconciled"] is True
    assert load["not_recorded"] == []
    assert _load_states(rep) == dict.fromkeys(LOAD_KEYS, "agrees")
    rows = {row["harness_key"]: row for row in load["fields"]}
    assert rows["duration_s"]["requested"] == 3 and rows["duration_s"]["simulator"] == 3.0


@pytest.mark.parametrize("warmup_s,load,key", [
    pytest.param(5, {}, "warmup_s", id="duration"),
    pytest.param(2, {"seed": 8}, "seed", id="seed"),
    pytest.param(2, {"rate": 10.0}, "rate_msg_s", id="rate"),
    pytest.param(2, {"scenario": "nominal"}, "scenario", id="scenario"),
])
def test_a_warm_up_load_the_harness_did_not_request_is_not_shown(
    tmp_path, warmup_s, load, key
) -> None:
    run_dir = warm_up(simulate(tmp_path, duration_s=3.0, harness_extra={"warmup_s": warmup_s}),
                      **load)
    profile = approved(tmp_path)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--warmup", "--tolerances", profile)
    assert rc == 1 and rep["evaluation"]["verdict"] == "NOT_SHOWN"
    assert rep["run"]["warmup"] is True
    states = _load_states(rep)
    assert states.pop(key) == "contradicts"
    assert set(states.values()) == {"agrees"}
    # The measured run is read against duration_s, never against warmup_s.
    rc, measured = check(tmp_path, "--run-dir", run_dir, "--tolerances", profile)
    assert rc == 0 and measured["load_reconciliation"]["reconciled"] is True


def test_a_warm_up_load_as_the_harness_requested_it_is_reconciled(tmp_path) -> None:
    run_dir = warm_up(simulate(tmp_path, duration_s=3.0, harness_extra={"warmup_s": 2}))
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--warmup", "--tolerances", approved(tmp_path))
    assert rc == 0 and rep["evaluation"]["verdict"] == "SUSTAINED"
    assert rep["run"]["warmup"] is True and rep["load_reconciliation"]["reconciled"] is True
    assert _load_states(rep) == {"scenario": "agrees", "seed": "agrees",
                                 "rate_msg_s": "agrees", "warmup_s": "agrees"}


@pytest.mark.parametrize("mutate,key,warmup", [
    pytest.param(_harness_without("scenario"), "scenario", False, id="scenario"),
    pytest.param(_harness_without("seed"), "seed", False, id="seed"),
    pytest.param(_harness_without("rate_msg_s"), "rate_msg_s", False, id="rate"),
    pytest.param(_harness_without("duration_s"), "duration_s", False, id="duration"),
    pytest.param(_harness(seed=None), "seed", False, id="seed-null"),
    pytest.param(_harness_without("warmup_s"), "warmup_s", True, id="warm-up-duration"),
])
def test_a_load_field_the_harness_did_not_record_never_certifies(
    tmp_path, capsys, mutate, key, warmup
) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0, harness_extra={"warmup_s": 2})
    warm_up(run_dir)
    mutate(run_dir)
    seal(run_dir)
    argv = ["--run-dir", run_dir, *(["--warmup"] if warmup else []),
            "--tolerances", approved(tmp_path)]
    rc, rep = check(tmp_path, *argv)
    assert rc == gc.EXIT_NOT_CERTIFIED == 3
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_CERTIFIED" and evaluation["certifying"] is False
    # The tolerances are evaluated and labelled, as with a proposed profile.
    assert [row["within"] for row in evaluation["per_tolerance"]] == [True, True, True]
    assert any("records no" in r and key in r for r in evaluation["reasons"]), evaluation["reasons"]
    load = rep["load_reconciliation"]
    assert load["reconciled"] is False and load["not_recorded"] == [key]
    assert _load_states(rep)[key] == "not recorded"
    assert "(non-certifying)" in capsys.readouterr().out


def test_an_unrecorded_load_field_is_reported_on_an_incomplete_run(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    _sim_manifest(lambda d: d.update(completed=False))(run_dir)
    _harness_without("seed")(run_dir)
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 4 and rep["evaluation"]["verdict"] == "NOT_SUSTAINED"
    assert rep["evaluation"]["certifying"] is False
    assert any("records no seed" in r for r in rep["evaluation"]["reasons"])


def test_a_missing_harness_manifest_empties_the_elapsed_section_and_never_certifies(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0)
    (run_dir / "manifest.json").unlink()
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 3 and rep["evaluation"]["verdict"] == "NOT_CERTIFIED"
    assert rep["evaluation"]["certifying"] is False
    assert rep["elapsed"] is None
    assert rep["run"]["execution_mode_source"] == "no harness manifest"
    assert rep["load_reconciliation"]["not_recorded"] == list(LOAD_KEYS)


@pytest.mark.parametrize("changes,seed", [
    pytest.param({"seed": "7"}, 7, id="seed-as-a-string"),
    pytest.param({"seed": True}, 1, id="seed-as-a-boolean"),  # True == 1 in Python
    pytest.param({"rate_msg_s": "11.2"}, 7, id="rate-as-a-string"),
])
def test_a_load_field_the_harness_recorded_as_no_number_is_not_shown(tmp_path, changes, seed) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0, seed=seed, harness_extra=changes)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 1 and rep["evaluation"]["verdict"] == "NOT_SHOWN"
    key = next(iter(changes))
    assert _load_states(rep)[key] == "unreadable"


def test_a_bare_simulator_directory_has_no_harness_request_to_reconcile(tmp_path) -> None:
    # The harness manifest beside it contradicts the simulator, but a bare
    # simulator directory is read alone: its manifest is its only record.
    run_dir = simulate(tmp_path, duration_s=2.0, harness_extra={"seed": 8})
    rc, rep = check(tmp_path, "--sim-dir", sim_dir(run_dir), "--tolerances", approved(tmp_path))
    assert rc == 0 and rep["evaluation"]["verdict"] == "SUSTAINED"
    load = rep["load_reconciliation"]
    assert load["applicable"] is False and "bare simulator directory" in load["reason"]


# ---------------------------------------------------------------------------
# 4d. An impossible acknowledgement chronology is an input defect (F2)
# ---------------------------------------------------------------------------


def _puback_at(index: int, *, of: str, delta_ns: int = 0):
    """Set record ``index``'s puback stamp to the publish stamp of the same
    record (``of='own'``) or of the next one (``of='next'``), plus ``delta_ns``."""
    def edit(lines):
        record = json.loads(lines[index])
        base = json.loads(lines[index + 1] if of == "next" else lines[index])
        record["puback_monotonic_ns"] = base["publish_monotonic_ns"] + delta_ns
        lines[index] = json.dumps(record, separators=(",", ":")) + "\n"
        return lines
    return edit


# Record 2 closes the coincident group at offset 0; record 3 is due 100 ms later.
@pytest.mark.parametrize("edit,expected,field", [
    pytest.param(_puback_at(2, of="own", delta_ns=-1),
                 "earlier than their own publish_monotonic_ns", "before_own_publish",
                 id="ack-before-its-own-publish"),
    pytest.param(_puback_at(2, of="next", delta_ns=1),
                 "later than the next record's publish_monotonic_ns", "after_next_publish",
                 id="ack-after-the-next-publish"),
])
def test_an_impossible_ack_chronology_is_not_shown(tmp_path, capsys, edit, expected, field) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    _edit_lines(edit)(run_dir)
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == gc.EXIT_NOT_SHOWN == 1
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_SHOWN" and evaluation["certifying"] is False
    assert evaluation["per_tolerance"] == []
    assert any(expected in r and "line 3" in r for r in evaluation["reasons"]), evaluation["reasons"]
    chronology = rep["identity"]["puback_chronology"]
    assert chronology["consistent"] is False and chronology[field] == 1
    assert expected in capsys.readouterr().out


@pytest.mark.parametrize("edit", [
    pytest.param(_puback_at(2, of="own"), id="ack-equal-to-its-own-publish"),
    pytest.param(_puback_at(2, of="next"), id="ack-equal-to-the-next-publish"),
    pytest.param(_puback_at(3, of="own", delta_ns=50_000_000), id="ack-between-the-publishes"),
    pytest.param(_set(2, puback_monotonic_ns=None), id="ack-null"),
    # The run's last record has no next publish: the drain may follow it.
    pytest.param(_puback_at(-1, of="own", delta_ns=5 * NS), id="last-ack-after-the-run"),
])
def test_a_possible_ack_chronology_leaves_the_verdict_unchanged(tmp_path, edit) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    _edit_lines(edit)(run_dir)
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 0 and rep["evaluation"]["verdict"] == "SUSTAINED"
    chronology = rep["identity"]["puback_chronology"]
    assert chronology == {"before_own_publish": 0, "after_next_publish": 0, "consistent": True}


def test_null_acks_are_absent_observations_not_chronology_defects(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0,
                       publisher=lambda clock: DelayedAckPublisher(clock, ack_delay_s=5.0))
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 0 and rep["identity"]["puback_chronology"]["consistent"] is True
    assert rep["puback_observations"]["observed"] == 0


# ---------------------------------------------------------------------------
# 5. Absent ACK observations
# ---------------------------------------------------------------------------


def test_absent_ack_observations_leave_the_generator_verdict_unchanged(tmp_path, capsys) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0,
                       publisher=lambda clock: DelayedAckPublisher(clock, ack_delay_s=5.0))
    assert all(r["puback_monotonic_ns"] is None
               for r in read_jsonl(run_dir / "sent_events.jsonl"))
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", approved(tmp_path))
    assert rc == 0 and rep["evaluation"]["verdict"] == "SUSTAINED"
    puback = rep["puback_observations"]
    n = expected_events(11.2, 3.0)
    assert puback["observed"] == 0 and puback["null"] == n
    assert puback["positive_budget_population"] > 0
    assert puback["observed_fraction_positive_budget"] == 0.0
    assert puback["null_other"] == puback["positive_budget_population"]
    assert puback["observation_delay_ms"]["p50"] is None
    assert "not evidence of loss" in puback["statement"]
    assert "host" in puback["clock_domain"]
    assert "never in the verdict" in capsys.readouterr().out


def test_fast_acks_are_missed_exactly_on_the_structural_zero_budget_events(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0,
                       publisher=lambda clock: DelayedAckPublisher(clock, ack_delay_s=0.01))
    rc, rep = check(tmp_path, "--run-dir", run_dir)
    assert rc == 3
    schedule, puback = rep["schedule"], rep["puback_observations"]
    structural = schedule["events_expected"] - schedule["distinct_instants"] + 1
    assert schedule["structural_zero_budget"] == structural > 0
    assert puback["null"] == puback["null_structural"] == structural
    assert puback["null_overrun"] == puback["null_other"] == 0
    assert puback["observed_fraction_positive_budget"] == 1.0
    assert puback["observation_delay_ms"]["p50"] == pytest.approx(10.0, abs=0.001)


# ---------------------------------------------------------------------------
# 6. No certification without an approved profile; profile validation
# ---------------------------------------------------------------------------


def test_without_a_profile_nothing_certifies(tmp_path) -> None:
    rc, rep = check(tmp_path, "--run-dir", simulate(tmp_path, duration_s=3.0))
    assert rc == gc.EXIT_NOT_CERTIFIED == 3
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_CERTIFIED" and evaluation["certifying"] is False
    assert evaluation["profile_id"] is None and evaluation["per_tolerance"] == []
    assert any("no tolerance profile" in reason for reason in evaluation["reasons"])


def test_a_proposed_profile_is_evaluated_but_never_certifies(tmp_path) -> None:
    profile = write_profile(tmp_path / "proposed.json", status="proposed")
    rc, rep = check(tmp_path, "--run-dir", simulate(tmp_path, duration_s=3.0),
                    "--tolerances", profile)
    assert rc == 3
    evaluation = rep["evaluation"]
    assert evaluation["verdict"] == "NOT_CERTIFIED" and evaluation["certifying"] is False
    assert evaluation["profile_status"] == "proposed"
    assert [row["within"] for row in evaluation["per_tolerance"]] == [True, True, True]
    assert any("proposed" in reason for reason in evaluation["reasons"])
    assert rep["inputs"]["tolerances"]["sha256"] == gc.load_tolerances(profile).sha256


@pytest.mark.parametrize("conditions", [
    {"nominal@11.2": PROFILE_A},
    {"smoke@11.200000000000001": PROFILE_A},  # the next float: exact match only
])
def test_a_condition_absent_from_the_profile_is_not_certified(tmp_path, conditions) -> None:
    rc, rep = check(tmp_path, "--run-dir", simulate(tmp_path, duration_s=3.0),
                    "--tolerances", approved(tmp_path, conditions=conditions))
    assert rc == 3
    assert any("no entry for smoke@11.2" in r for r in rep["evaluation"]["reasons"])


def test_the_shipped_proposal_is_proposed_and_never_certifies(tmp_path) -> None:
    profile = gc.load_tolerances(PROPOSED_PROFILE)
    assert profile.status == "proposed" and profile.approval is None
    tolerance = gc.ConditionTolerance(20.0, 0, 20.0)
    assert profile.conditions == {
        ("nominal", 11.2): tolerance,
        ("load-sweep", 10.0): tolerance,
        ("load-sweep", 50.0): tolerance,
        ("soak", 11.2): tolerance,
    }
    basis = profile.basis
    assert "NOT adopted" in basis
    assert "engineering basis only" in basis and "non-citable" in basis
    # Profile A as described: relative overruns and lateness, an absolute span
    # deviation; no claim that 20 ms cannot move a 1 Hz sample or bin.
    assert "zero relative overruns" in basis and "absolute first-to-last span" in basis
    assert "not a licence to repeat" in basis
    assert "shifts no sampled observation" not in basis

    run_dir = simulate(tmp_path, scenario="nominal", duration_s=2.0)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", PROPOSED_PROFILE)
    assert rc == 3
    evaluation = rep["evaluation"]
    assert evaluation["certifying"] is False and evaluation["profile_status"] == "proposed"
    assert [row["within"] for row in evaluation["per_tolerance"]] == [True, True, True]
    assert rep["inputs"]["tolerances"]["profile_id"] == profile.profile_id


def _bad(**changes):
    def edit(doc):
        doc.update(changes)
    return edit


def _bad_tolerance(**changes):
    def edit(doc):
        doc["conditions"]["smoke@11.2"].update(changes)
    return edit


def _without(key: str, *, tolerance: bool = False):
    def edit(doc):
        del (doc["conditions"]["smoke@11.2"] if tolerance else doc)[key]
    return edit


BAD_PROFILES = [
    pytest.param(_bad(approval={"approved_by": "x", "date": "2026-10-07"}), "decision_record",
                 id="approved-without-decision-record"),
    pytest.param(_bad(approval={**APPROVAL, "approved_by": ""}), "approved_by",
                 id="approved-with-an-empty-approver"),
    pytest.param(_bad(approval={**APPROVAL, "date": "07-10-2026"}), "date",
                 id="approved-with-a-non-iso-date"),
    pytest.param(_bad(approval=None), "approval", id="approved-without-approval"),
    pytest.param(_bad(status="proposed"), "approval", id="proposed-with-an-approval"),
    pytest.param(_bad(status="adopted"), "status", id="unknown-status"),
    pytest.param(_bad(default_tolerance=1), "default_tolerance", id="unknown-key"),
    pytest.param(_without("basis"), "basis", id="missing-basis"),
    pytest.param(_bad(basis=""), "basis", id="empty-basis"),
    pytest.param(_bad(rate_key="scenario:rate"), "rate_key", id="other-rate-key-format"),
    pytest.param(_bad(conditions={}), "conditions", id="no-condition"),
    pytest.param(_bad(conditions={"smoke11.2": PROFILE_A}), "smoke11.2", id="key-without-at"),
    pytest.param(_bad(conditions={"walk@11.2": PROFILE_A}), "walk@11.2", id="unknown-scenario"),
    pytest.param(_bad(conditions={"smoke@fast": PROFILE_A}), "smoke@fast", id="rate-not-a-number"),
    pytest.param(_bad(conditions={"smoke@11.2": PROFILE_A, "smoke@11.20": PROFILE_A}),
                 "smoke@11.20", id="the-same-rate-twice"),
    pytest.param(_bad_tolerance(max_gap_ms=1.0), "max_gap_ms", id="unknown-tolerance"),
    pytest.param(_without("max_span_deviation_ms", tolerance=True), "max_span_deviation_ms",
                 id="missing-tolerance"),
    pytest.param(_bad_tolerance(max_overrun_events=True), "max_overrun_events", id="bool"),
    pytest.param(_bad_tolerance(max_overrun_events=1.5), "max_overrun_events",
                 id="fractional-overruns"),
    pytest.param(_bad_tolerance(max_relative_lateness_ms=-1.0), "max_relative_lateness_ms",
                 id="negative"),
    pytest.param(_bad_tolerance(max_span_deviation_ms="20"), "max_span_deviation_ms",
                 id="string"),
    # Valid JSON integers too large for a float: refused, never an OverflowError.
    pytest.param(_bad_tolerance(max_overrun_events=10**400), "max_overrun_events",
                 id="integer-too-large-for-a-float"),
    pytest.param(_bad_tolerance(max_relative_lateness_ms=10**400), "max_relative_lateness_ms",
                 id="limit-too-large-for-a-float"),
]


@pytest.mark.parametrize("edit,expected", BAD_PROFILES)
def test_an_invalid_profile_is_a_usage_error(tmp_path, capsys, edit, expected) -> None:
    path = write_profile(tmp_path / "profile.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    edit(doc)
    write_json(path, doc)
    run_dir = simulate(tmp_path, duration_s=2.0)
    out = tmp_path / "out.json"
    argv = ["generator-check", "--run-dir", str(run_dir), "--tolerances", str(path),
            "--out", str(out)]
    assert cli.main(argv) == gc.EXIT_USAGE == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and expected in err
    assert not out.exists()
    with pytest.raises(gc.ToleranceError):
        gc.load_tolerances(path)


@pytest.mark.parametrize("text,expected", [
    pytest.param('"max_relative_lateness_ms": NaN', "NaN", id="nan"),
    pytest.param('"max_relative_lateness_ms": Infinity', "Infinity", id="infinity"),
    pytest.param('"max_relative_lateness_ms": -Infinity', "Infinity", id="minus-infinity"),
])
def test_a_profile_holding_nan_or_infinity_is_a_usage_error(tmp_path, capsys, text, expected) -> None:
    path = write_profile(tmp_path / "profile.json")
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"max_relative_lateness_ms": 20.0', text), encoding="utf-8")
    assert text in path.read_text(encoding="utf-8")
    argv = ["generator-check", "--run-dir", str(simulate(tmp_path, duration_s=2.0)),
            "--tolerances", str(path)]
    assert cli.main(argv) == 2
    assert expected in capsys.readouterr().err


@pytest.mark.parametrize("content", [None, b"{", b"[]", b'{"profile_id": "a", "profile_id": "b"}'],
                         ids=["missing", "not-json", "not-an-object", "duplicate-key"])
def test_an_unreadable_profile_is_a_usage_error(tmp_path, capsys, content) -> None:
    path = tmp_path / "profile.json"
    if content is not None:
        path.write_bytes(content)
    argv = ["generator-check", "--run-dir", str(simulate(tmp_path, duration_s=2.0)),
            "--tolerances", str(path)]
    assert cli.main(argv) == 2
    assert "profile.json" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 7. Clock domains: the controller section reads guest stamps only
# ---------------------------------------------------------------------------

GUEST_OFFSET_NS = 10**15
GUEST_STEP_NS = 7_000_000


def _numbers(node):
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _numbers(value)
    elif isinstance(node, list):
        for value in node:
            yield from _numbers(value)


def test_the_controller_section_reads_guest_stamps_only(tmp_path, capsys) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    sent = read_jsonl(run_dir / "sent_events.jsonl")
    n = len(sent)
    events = []
    for i, record in enumerate(sent):
        received = GUEST_OFFSET_NS + i * GUEST_STEP_NS  # unrelated to the host stamps
        accepted = i != 5
        events.append({
            "run_id": RUN_ID, "message_id": record["message_id"],
            "device_uuid": record["device_uuid"], "device_type": record["device_type"],
            "seq": record["seq"], "received_monotonic_ns": received,
            "ditto_ack_monotonic_ns": received + 3_000_000 if accepted else None,
            "latency_ms": 3.0 if accepted else None,
            "outcome": "accepted" if accepted else "rejected", "attempts": 1, "error": None,
        })
    events[10], events[11] = events[11], events[10]  # one backwards step
    other = dict(events[0], run_id="other-run")
    text = "".join(json.dumps(e) + "\n" for e in events + [other])
    text += '{"run_id": "gc-run", "message_id": "torn'  # a torn final line
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(text, encoding="utf-8", newline="\n")

    rc_without, without = check(tmp_path, "--run-dir", run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--events", events_path)
    assert rc == rc_without == 3  # never in the verdict
    assert rep["generator_timing"] == without["generator_timing"]
    assert rep["puback_observations"] == without["puback_observations"]
    assert without["controller_acceptance"] is None

    acceptance = rep["controller_acceptance"]
    assert "guest" in acceptance["clock_domain"]
    assert acceptance["lines"] == n + 2
    assert acceptance["unreadable"] == 1 and acceptance["other_run_id"] == 1
    assert acceptance["outcomes"] == {"accepted": n - 1, "rejected": 1}
    assert acceptance["clock_backwards"] == 1
    assert acceptance["received"]["span_s"] == pytest.approx((n - 1) * GUEST_STEP_NS / NS)
    assert acceptance["received"]["max_gap_ms"] == pytest.approx(GUEST_STEP_NS / 1e6)
    accepted_ack = acceptance["accepted_ack"]
    assert accepted_ack["n"] == n - 1
    assert accepted_ack["span_s"] == pytest.approx((n - 1) * GUEST_STEP_NS / NS)
    assert accepted_ack["served_rate_hz"] == pytest.approx((n - 2) / ((n - 1) * GUEST_STEP_NS / NS))
    assert accepted_ack["max_gap_ms"] == pytest.approx(2 * GUEST_STEP_NS / 1e6)
    assert acceptance["events_copy"]["sha256"] and acceptance["events_copy"]["path"]
    assert "never subtracted" in acceptance["note"]
    # A guest stamp minus a host stamp (or a raw guest stamp) would be about
    # 1e15 ns, 1e9 ms or 1e6 s: no number of the section comes near.
    assert all(abs(v) < 1e5 for v in _numbers(acceptance))
    assert "guest" in capsys.readouterr().out


def test_an_unreadable_events_copy_is_reported_and_changes_nothing(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0)
    profile = approved(tmp_path)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", profile,
                    "--events", tmp_path / "absent.jsonl")
    assert rc == 0 and rep["evaluation"]["verdict"] == "SUSTAINED"
    assert "missing" in rep["controller_acceptance"]["error"]
    (tmp_path / "bad.jsonl").write_bytes(b"\xff\xfe")
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", profile,
                    "--events", tmp_path / "bad.jsonl")
    assert rc == 0 and "UTF-8" in rep["controller_acceptance"]["error"]


# ---------------------------------------------------------------------------
# 8. dropout-reconnect: identity applies, timing is not applicable
# ---------------------------------------------------------------------------


def test_dropout_reconnect_timing_is_not_applicable(tmp_path) -> None:
    run_dir = simulate(tmp_path, scenario="dropout-reconnect", seed=5, duration_s=60.0)
    profile = approved(tmp_path, conditions={"dropout-reconnect@11.2": PROFILE_A})
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", profile)
    assert rc == 3 and rep["evaluation"]["verdict"] == "NOT_CERTIFIED"
    assert any("not applicable" in r for r in rep["evaluation"]["reasons"])
    assert rep["generator_timing"]["applicable"] is False
    identity = rep["identity"]
    assert identity["exact"] is True
    dropout = identity["dropout"]
    assert dropout["buffered_recorded"] == dropout["buffered_expected"] > 0
    assert dropout["disconnects_recorded"] == dropout["disconnects_expected"] > 0
    assert rep["puback_observations"]["records"] == identity["records"]

    _sim_manifest(lambda d: d["totals"].update(
        buffered_dropout=d["totals"]["buffered_dropout"] + 1))(run_dir)
    seal(run_dir)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--tolerances", profile)
    assert rc == 1
    assert any("buffered_dropout" in r for r in rep["evaluation"]["reasons"])


# ---------------------------------------------------------------------------
# 9. Output: write-once, never inside the run or the simulator directory
# ---------------------------------------------------------------------------


def test_the_report_is_write_once_and_never_inside_the_run(tmp_path, capsys) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0)
    before = tree(run_dir)
    out = tmp_path / "checks" / "generator" / f"{RUN_ID}.json"
    argv = ["generator-check", "--run-dir", str(run_dir), "--out", str(out)]
    assert cli.main(argv) == 3
    first = out.read_bytes()
    assert json.loads(first)["check"] == gc.CHECK_NAME
    capsys.readouterr()
    assert cli.main(argv) == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    assert out.read_bytes() == first

    for inside in (run_dir / "check.json", sim_dir(run_dir) / "check.json",
                   run_dir / "logs" / "checks" / "check.json"):
        assert cli.main(["generator-check", "--run-dir", str(run_dir),
                         "--out", str(inside)]) == 2
        assert "inside" in capsys.readouterr().err
    for inside in (sim_dir(run_dir) / "check.json", run_dir / "check.json"):
        # Given as a bare simulator directory, the harness run around it is
        # protected all the same.
        assert cli.main(["generator-check", "--sim-dir", str(sim_dir(run_dir)),
                         "--out", str(inside)]) == 2
        assert "inside" in capsys.readouterr().err
    assert tree(run_dir) == before  # the run was never written to

    sealed = tmp_path / "package"
    sealed.mkdir()
    (sealed / "SHA256SUMS").write_text("", encoding="utf-8")
    assert cli.main(["generator-check", "--run-dir", str(run_dir),
                     "--out", str(sealed / "checks" / "check.json")]) == 2
    assert "SHA256SUMS" in capsys.readouterr().err
    assert list(sealed.iterdir()) == [sealed / "SHA256SUMS"]


# ---------------------------------------------------------------------------
# Execution mode, warm-up, elapsed time, usage
# ---------------------------------------------------------------------------


def test_the_execution_mode_is_copied_from_the_harness_manifest_never_inferred(tmp_path) -> None:
    recorded = simulate(tmp_path / "a", harness_extra={"execution_mode": "tcg-emulated"})
    rc, rep = check(tmp_path, "--run-dir", recorded)
    assert rep["run"]["execution_mode"] == "tcg-emulated"
    assert rep["run"]["execution_mode_source"] == "harness manifest"

    old = simulate(tmp_path / "b")
    write_json(old / "sut_environment.json", {"role": "sut", "provider": "QEMU/TCG emulated"})
    seal(old)
    rc, rep = check(tmp_path, "--run-dir", old)
    assert rep["run"]["execution_mode"] is None
    assert "not recorded" in rep["run"]["execution_mode_source"]

    rc, rep = check(tmp_path, "--sim-dir", sim_dir(old))
    assert rep["run"]["execution_mode"] is None
    assert rep["run"]["execution_mode_source"] == "no harness manifest"


def test_the_warm_up_is_checked_on_request_and_labelled(tmp_path, capsys) -> None:
    run_dir = simulate(tmp_path, duration_s=3.0, harness_extra={"warmup_s": 2})
    warm_up(run_dir)
    capsys.readouterr()
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--warmup")
    assert rc == 3
    assert rep["run"]["warmup"] is True and rep["run"]["run_id"] == f"{RUN_ID}.warmup"
    assert rep["identity"]["exact"] is True
    assert rep["inputs"]["root_copy"]["applicable"] is False
    assert rep["elapsed"] is None
    assert "never stands for the measured run" in capsys.readouterr().out
    rc, measured = check(tmp_path, "--run-dir", run_dir)
    assert measured["run"]["warmup"] is False and measured["run"]["run_id"] == RUN_ID

    without = simulate(tmp_path / "other", duration_s=2.0)
    rc, rep = check(tmp_path, "--run-dir", without, "--warmup")
    assert rc == 1 and rep["evaluation"]["verdict"] == "NOT_SHOWN"
    assert cli.main(["generator-check", "--sim-dir", str(sim_dir(run_dir)), "--warmup"]) == 2


def test_the_elapsed_section_uses_the_harness_stamps(tmp_path) -> None:
    run_dir = simulate(tmp_path)
    rc, rep = check(tmp_path, "--run-dir", run_dir)
    elapsed = rep["elapsed"]
    assert elapsed["first_publish_after_start_s"] == pytest.approx(STARTED_BEFORE_S, abs=1e-6)
    assert elapsed["finished_after_last_publish_s"] == pytest.approx(FINISHED_AFTER_S, abs=1e-6)
    assert elapsed["process_elapsed_s"] == pytest.approx(
        STARTED_BEFORE_S + 9.9 + FINISHED_AFTER_S, abs=1e-6)
    assert elapsed["kill_bound_s"] == 10.0 + SUBPROCESS_GRACE_S
    assert elapsed["simulator_returncode"] == 0
    anchor = rep["generator_timing"]["anchor"]
    assert anchor["c_upper_bound_s"] == pytest.approx(STARTED_BEFORE_S, abs=1e-6)
    rc, bare = check(tmp_path, "--sim-dir", sim_dir(run_dir))
    assert bare["elapsed"] is None and bare["generator_timing"]["anchor"]["c_upper_bound_s"] is None
    assert bare["inputs"]["root_copy"]["applicable"] is False


@pytest.mark.parametrize("window", ["0", "-1", "nan", "inf"])
def test_a_window_that_is_not_a_positive_finite_number_is_a_usage_error(tmp_path, capsys, window) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0)
    assert cli.main(["generator-check", "--run-dir", str(run_dir), "--window-s", window]) == 2
    assert "--window-s" in capsys.readouterr().err


@pytest.mark.parametrize("window", ["0.0999", "0.05", "1e-3", "1e-5"])
def test_a_window_below_a_tenth_of_a_second_is_a_usage_error(tmp_path, capsys, window) -> None:
    # The windows table holds one row per window: a unit slip (1e-6 for 1)
    # would allocate billions of rows on a soak run.
    run_dir = simulate(tmp_path, duration_s=2.0)
    out = tmp_path / "out.json"
    argv = ["generator-check", "--run-dir", str(run_dir), "--window-s", window,
            "--out", str(out)]
    assert cli.main(argv) == gc.EXIT_USAGE == 2
    err = capsys.readouterr().err
    assert "--window-s" in err and "0.1" in err
    assert not out.exists()
    with pytest.raises(ValueError, match="window"):
        gc.check_generator(run_dir=run_dir, window_s=float(window))


def test_a_window_of_a_tenth_of_a_second_is_accepted(tmp_path) -> None:
    run_dir = simulate(tmp_path, duration_s=2.0)
    rc, rep = check(tmp_path, "--run-dir", run_dir, "--window-s", "0.1")
    assert rc == 3 and rep["generator_timing"]["windows"]["window_s"] == 0.1
    assert gc.MIN_WINDOW_S == 0.1


def test_one_input_layout_is_required(tmp_path) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["generator-check"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        cli.main(["generator-check", "--run-dir", str(tmp_path), "--sim-dir", str(tmp_path)])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Schedule reconstruction against the pilot conditions
# ---------------------------------------------------------------------------


def _sim_manifest_for(scenario: str, rate: float, duration_s: float, seed: int = 7) -> dict:
    devices = make_devices(seed)
    doc = {
        "run_id": "pilot-x", "scenario": scenario, "seed": seed,
        "devices": [{"device_type": d.device_type, "device_uuid": d.device_uuid}
                    for d in devices],
        "rates_hz": {"aggregate": rate, "per_device": split_rate(rate)},
        "duration_s": duration_s, "completed": True,
        "totals": {"sent": 0, "intended_invalid": 0, "buffered_dropout": 0,
                   "dropout_disconnects": 0},
    }
    return json.loads(json.dumps(doc))  # the floats as a manifest file holds them


@pytest.mark.parametrize("scenario,rate,duration_s,events,zero_budget,smallest_gap_ms", [
    ("nominal", 11.2, 120.0, 1_344, 145, 100.0),
    ("nominal", 11.2, 600.0, 6_720, 721, 100.0),
    ("load-sweep", 10.0, 300.0, 3_001, 323, 112.0),
    ("load-sweep", 50.0, 300.0, 15_001, 1_609, 22.4),
    ("soak", 11.2, 3600.0, 40_320, 4_321, 100.0),
])
def test_the_schedule_of_each_pilot_condition_is_rebuilt_exactly(
    scenario, rate, duration_s, events, zero_budget, smallest_gap_ms
) -> None:
    schedule, problems = gc.reconstruct_schedule(_sim_manifest_for(scenario, rate, duration_s))
    assert problems == []
    assert len(schedule.events) == events
    assert schedule.structural_zero_budget == zero_budget
    assert schedule.structural_zero_budget == events - len(schedule.instants) + 1
    assert schedule.smallest_gap_s * 1000 == pytest.approx(smallest_gap_ms, abs=1e-6)


# ---------------------------------------------------------------------------
# 10. No network and no write on import
# ---------------------------------------------------------------------------


def test_import_opens_no_socket_and_writes_nothing(tmp_path) -> None:
    env = dict(os.environ, PYTHONPATH=str(SRC_DIR), PYTHONDONTWRITEBYTECODE="1")
    code = (
        "import socket\n"
        "def boom(*a, **k): raise AssertionError('network access at import time')\n"
        "class NoSocket(socket.socket):\n"
        "    def __init__(self, *a, **k): boom()\n"
        "socket.socket = NoSocket\n"
        "socket.create_connection = boom\n"
        "socket.getaddrinfo = boom\n"
        "import egw_experiments.generator_check as m\n"
        "print(m.__file__)\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], env=env, cwd=tmp_path,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert Path(proc.stdout.strip()).resolve() == Path(gc.__file__).resolve()
    assert list(tmp_path.iterdir()) == []
    assert math.isfinite(gc.COINCIDENT_S) and gc.COINCIDENT_S < 0.001
