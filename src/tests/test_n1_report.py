"""Tests for egw_experiments.n1_report (decision 2 of 2026-09-30).

An identity whose only outcome lines are ``duplicate`` is reported as
``n1_applied_unconfirmed`` only when the three conditions of the adopted rule
hold: a valid published identity of the run (1), a source the run records for
it (2: a controller death with its captured ``die``, or an A3 connection end
of its own device received before its redelivery; each source explains one
identity at most) and the twin's arithmetic on its device (3: the excess of
Δ``accepted_count`` over the device's accepted lines equals exactly the number
reported there, the twin's ``last_seq`` not below any of their ``seq``; all or
nothing per device). Every other duplicate-only identity is
``duplicate_only_unexplained`` with its failed conditions named. Pure
functions only: no file, no network.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

from egw_experiments import analyze as analyze_mod
from egw_experiments import itest_reconcile as rec
from egw_experiments import n1_report as n1
from egw_experiments import proof_evaluator as pe

SRC_DIR = Path(__file__).resolve().parents[1]
NS = 1_000_000_000
R = "controller_restart-r01"
D = "dddddddd-0000-5000-8000-00000000000d"
E = "eeeeeeee-0000-5000-8000-00000000000e"


# ---------------------------------------------------------------------------
# synthetic records
# ---------------------------------------------------------------------------


def sent(mid: str, seq: int, device: str = D, invalid: bool = False) -> dict:
    return {"run_id": R, "message_id": mid, "device_uuid": device, "device_type": "smartwatch",
            "seq": seq, "publish_monotonic_ns": 1, "puback_monotonic_ns": 2, "intended_invalid": invalid}


def line(mid: str, seq: int, outcome: str, received: int, device: str = D, run_id: str = R) -> dict:
    return {"run_id": run_id, "message_id": mid, "device_uuid": device, "device_type": "smartwatch",
            "seq": seq, "received_monotonic_ns": received,
            "ditto_ack_monotonic_ns": received + 1 if outcome == "accepted" else None,
            "latency_ms": None, "outcome": outcome, "attempts": 1, "error": None}


def twin(count, last_run_id, last_seq, exists: bool = True) -> dict:
    return {"device_type": "smartwatch", "exists": exists,
            "ingestion": {"last_run_id": last_run_id, "last_seq": last_seq, "last_message_id": None,
                          "last_ts": None, "accepted_count": count}}


def end(device: str, received: int, number: int) -> dict:
    """An A3 connection end as a3_connection_ends returns it."""
    return {"line": number, "ts": "2026-09-30T10:00:00.000Z", "cause": "write-failed", "connection": 2,
            "device_uuid": device, "received_monotonic_ns": received}


SENT = [sent("m0", 0), sent("m1", 1), sent("m2", 2)]
EVENTS = [line("m0", 0, "accepted", 1000), line("m1", 1, "accepted", 2000), line("m2", 2, "duplicate", 5000)]
BEFORE = {D: twin(10, "old", 9)}
AFTER = {D: twin(13, R, 2)}


def report(**changes) -> dict:
    """Case 1 of the map (an A3 end of D received before m2's redelivery,
    twin excess 1), with ``changes`` applied."""
    kwargs = dict(run_id=R, sent_records=SENT, events=EVENTS, twins_before=BEFORE, twins_after=AFTER,
                  twin_evidence_problem=None, deaths=[], deaths_note=None,
                  a3_ends=[end(D, 4000, 7)], a3_note=None)
    kwargs.update(changes)
    return n1.n1_applied_unconfirmed(**kwargs)


def named(doc: dict) -> list[str]:
    return [case["message_id"] for case in doc["n1_applied_unconfirmed"]]


def unexplained(doc: dict) -> dict[str, dict]:
    return {case["message_id"]: case for case in doc["duplicate_only_unexplained"]}


def failed(doc: dict, mid: str) -> list[str]:
    return unexplained(doc)[mid]["failed"]


# ---------------------------------------------------------------------------
# condition 2: the A3 connection end
# ---------------------------------------------------------------------------


def test_case_1_an_a3_end_before_the_redelivery_names_the_identity() -> None:
    doc = report()
    assert named(doc) == ["m2"]
    case = doc["n1_applied_unconfirmed"][0]
    assert case["device_uuid"] == D and case["seq"] == 2
    assert case["first_duplicate_received_monotonic_ns"] == 5000
    assert case["possible_sources"] == [
        {"source": n1.SOURCE_A3, "controller_log_line": 7, "received_monotonic_ns": 4000}
    ]
    assert doc["duplicate_only_unexplained"] == []
    assert doc["devices"][D]["excess"] == 1
    assert doc["devices"][D]["delta"] == 3 and doc["devices"][D]["accepted_lines"] == 2
    assert doc["devices"][D]["duplicate_only"] == 1 and doc["devices"][D]["reported"] == 1
    # A report, never a count: the note says what it does not change.
    for words in ("lost", "zero-lost", "exactly-once"):
        assert words in doc["note"]
    assert "MISMATCH" not in doc["note"] and "OK" not in doc["note"]


def test_case_2_an_a3_end_received_after_the_redelivery_cannot_serve() -> None:
    doc = report(a3_ends=[end(D, 6000, 7)])
    assert named(doc) == []
    assert failed(doc, "m2") == ["2"]


def test_an_a3_end_received_at_the_redelivery_itself_cannot_serve() -> None:
    """P-4's order is strict: the end's delivery precedes the redelivery."""
    assert failed(report(a3_ends=[end(D, 5000, 7)]), "m2") == ["2"]


def test_case_3_an_a3_end_on_another_device_cannot_serve() -> None:
    assert failed(report(a3_ends=[end(E, 4000, 7)]), "m2") == ["2"]


def test_an_unreadable_stamp_leaves_the_end_unable_to_serve() -> None:
    no_stamp = dict(end(D, 4000, 7), received_monotonic_ns=None)
    assert failed(report(a3_ends=[no_stamp]), "m2") == ["2"]
    events = EVENTS[:2] + [dict(EVENTS[2], received_monotonic_ns=None)]
    assert failed(report(events=events), "m2") == ["2"]


def _a3_line(device: str, received, *, level: str = "ERROR", cause: str = "write-failed",
             prefix: str = "2026-09-30T10:03:10.000000000Z ", message: str = n1.A3_END_MESSAGE,
             topic: str | None = None) -> str:
    """A controller log line as `docker logs --timestamps` prints it (the
    stamp, then the JSON object the controller's formatter writes)."""
    return prefix + json.dumps({
        "ts": "2026-09-30T10:03:10.001Z", "level": level, "logger": "egw_controller.mqtt", "message": message,
        "context": {"cause": cause, "connection": 2,
                    "identity": {"topic": topic or f"c2dt/egw-01/{device}/telemetry", "mid": 7, "qos": 1,
                                 "dup": False, "connection": 2, "received_monotonic_ns": received},
                    "occurrence": 1, "backoff_s": 1.0 if cause != "stop" else 0.0},
    })


def test_case_4_a_graceful_stop_is_not_an_a3_end() -> None:
    info = _a3_line(D, 4000, level="INFO", cause="stop")
    assert n1.a3_connection_ends([info]) == []
    doc = report(a3_ends=n1.a3_connection_ends([info]))
    assert failed(doc, "m2") == ["2"]
    # The same line at ERROR is an A3 end, and it serves.
    error = _a3_line(D, 4000)
    (parsed,) = n1.a3_connection_ends(["not json", "", error])
    assert parsed["line"] == 3 and parsed["device_uuid"] == D and parsed["received_monotonic_ns"] == 4000
    assert named(report(a3_ends=[parsed])) == ["m2"]


# ---------------------------------------------------------------------------
# condition 3: the twin's arithmetic on the device, all or nothing
# ---------------------------------------------------------------------------


def test_case_5_no_surplus_on_the_device() -> None:
    doc = report(twins_after={D: twin(12, R, 2)})
    assert named(doc) == [] and failed(doc, "m2") == ["3"]
    assert doc["devices"][D]["excess"] == 0
    assert "surplus" in unexplained(doc)["m2"]["reason"]


def test_case_6_a_surplus_beyond_the_candidates_names_none() -> None:
    doc = report(twins_after={D: twin(14, R, 2)})
    assert named(doc) == [] and failed(doc, "m2") == ["3"]
    assert doc["devices"][D]["excess"] == 2


def _two_candidates(after: dict, ends: list[dict], deaths: list | None = None) -> dict:
    sent_records = SENT + [sent("m3", 3)]
    events = EVENTS + [line("m3", 3, "duplicate", 5500)]
    return report(sent_records=sent_records, events=events, twins_after=after, a3_ends=ends,
                  deaths=deaths if deaths is not None else [])


def test_case_7_more_candidates_than_the_surplus_cannot_be_told_apart() -> None:
    doc = _two_candidates({D: twin(13, R, 3)}, [end(D, 4000, 7), end(D, 4100, 8)])
    assert named(doc) == []
    assert failed(doc, "m2") == ["3"] and failed(doc, "m3") == ["3"]
    assert "cannot be told apart" in unexplained(doc)["m2"]["reason"]


def test_case_8_fewer_sources_than_candidates_names_none() -> None:
    doc = _two_candidates({D: twin(14, R, 3)}, [end(D, 4000, 7)])
    assert named(doc) == []
    assert failed(doc, "m2") == ["2"] and failed(doc, "m3") == ["2"]


def test_case_9_two_ends_serve_two_candidates() -> None:
    doc = _two_candidates({D: twin(14, R, 3)}, [end(D, 4000, 7), end(D, 4100, 8)])
    assert named(doc) == ["m2", "m3"]
    assert doc["duplicate_only_unexplained"] == []
    assert doc["devices"][D]["reported"] == 2


def test_each_end_explains_one_identity_whatever_the_order_of_the_lines() -> None:
    """One end received before both redeliveries and one between them: a
    matching exists (the later end to m3, the earlier to m2) whichever end
    is read first."""
    ends = [end(D, 5200, 8), end(D, 4000, 7)]
    assert named(_two_candidates({D: twin(14, R, 3)}, ends)) == ["m2", "m3"]
    # Both ends between the two redeliveries: m2 has none, so none is named.
    late = [end(D, 5200, 8), end(D, 5300, 9)]
    doc = _two_candidates({D: twin(14, R, 3)}, late)
    assert named(doc) == [] and failed(doc, "m2") == ["2"] and failed(doc, "m3") == ["2"]


def test_case_10_a_twin_not_advanced_to_the_identity() -> None:
    doc = report(twins_after={D: twin(13, R, 1)})
    assert named(doc) == [] and failed(doc, "m2") == ["3"]
    assert "last_seq" in unexplained(doc)["m2"]["reason"]


def test_an_unreadable_last_seq_is_not_advanced() -> None:
    assert failed(report(twins_after={D: twin(13, R, None)}), "m2") == ["3"]


def test_a_device_absent_from_a_snapshot_is_not_evaluable() -> None:
    doc = report(twins_after={E: twin(13, R, 2)})
    assert failed(doc, "m2") == ["3"]
    doc = report(twins_before=None, twins_after=None)
    assert failed(doc, "m2") == ["3"] and "not read" in unexplained(doc)["m2"]["reason"]


def test_case_17_absolute_counts_are_never_used() -> None:
    events = [EVENTS[2]]
    first_use = report(events=events, twins_before={D: twin(None, None, None, exists=False)},
                       twins_after={D: twin(1, R, 2)})
    long_lived = report(events=events, twins_before={D: twin(1000, "old", 9)}, twins_after={D: twin(1001, R, 2)})
    assert named(first_use) == ["m2"]
    assert first_use == long_lived


def test_case_18_a_twin_evidence_problem_leaves_every_candidate_unexplained() -> None:
    problem = "the drain was not recorded quiet"
    doc = report(twin_evidence_problem=problem)
    assert named(doc) == [] and failed(doc, "m2") == ["3"]
    assert problem in unexplained(doc)["m2"]["reason"]


def test_case_19_an_unpublished_candidate_blocks_its_device() -> None:
    events = EVENTS + [line("x9", 9, "duplicate", 5200)]
    doc = report(events=events, twins_after={D: twin(14, R, 9)},
                 a3_ends=[end(D, 4000, 7), end(D, 4100, 8)])
    assert named(doc) == []
    assert "1" in failed(doc, "x9")
    assert "not a valid published identity" in unexplained(doc)["x9"]["reason"]
    assert "3" in failed(doc, "m2")  # all or nothing: x9 can never be N1, so m2 is not named either
    assert "all or nothing" in unexplained(doc)["m2"]["reason"]


@pytest.mark.parametrize("record", [
    sent("m2", 2, invalid=True),
    {**sent("m2", 2), "run_id": "another-run"},
    {k: v for k, v in sent("m2", 2).items() if k != "intended_invalid"},
])
def test_an_intended_invalid_or_foreign_or_unmarked_sent_record_is_not_a_valid_identity(record) -> None:
    doc = report(sent_records=SENT[:2] + [record])
    assert named(doc) == [] and "1" in failed(doc, "m2")


def test_a_repeated_sent_record_is_not_shown_valid() -> None:
    assert "1" in failed(report(sent_records=SENT + [sent("m2", 2)]), "m2")


def test_sent_records_not_read_leave_condition_1_unshown() -> None:
    doc = report(sent_records=None)
    assert named(doc) == [] and "1" in failed(doc, "m2")
    assert "not read" in unexplained(doc)["m2"]["reason"]


def test_a_device_with_a_surplus_and_no_candidate_is_a_note_only() -> None:
    doc = report(events=EVENTS[:2], twins_after={D: twin(13, R, 1)})
    assert doc["n1_applied_unconfirmed"] == [] and doc["duplicate_only_unexplained"] == []
    assert doc["devices"][D]["excess"] == 1 and doc["devices"][D]["duplicate_only"] == 0
    assert any(D in note and "excess 1" in note for note in doc["notes"])


# ---------------------------------------------------------------------------
# condition 1: only duplicate lines, of this run id
# ---------------------------------------------------------------------------


def test_case_15_n2_is_not_a_candidate() -> None:
    """A duplicate after an accepted line (N2) is in neither list."""
    events = EVENTS + [line("m1", 1, "duplicate", 6000)]
    doc = report(events=events)
    assert "m1" not in named(doc) and "m1" not in unexplained(doc)


def test_case_16_duplicate_and_failed_lines_are_not_duplicate_only() -> None:
    events = EVENTS[:2] + [line("m2", 2, "duplicate", 5000), line("m2", 2, "failed", 5600)]
    doc = report(events=events)
    assert doc["n1_applied_unconfirmed"] == [] and doc["duplicate_only_unexplained"] == []


def test_lines_of_another_run_id_are_not_read_for_the_candidates() -> None:
    events = EVENTS[:2] + [line("m2", 2, "duplicate", 5000, run_id=f"{R}.warmup")]
    doc = report(events=events)
    assert doc["n1_applied_unconfirmed"] == [] and doc["duplicate_only_unexplained"] == []
    assert report(run_id=None)["n1_applied_unconfirmed"] == []


# ---------------------------------------------------------------------------
# condition 2: the controller death (restart record + captured die)
# ---------------------------------------------------------------------------

T0_EPOCH = 1_790_000_000
T1_EPOCH = T0_EPOCH + 700
RESTART = {"template": "x", "requested_at_s": 300, "executed": True, "command": "x",
           "started_utc": "2026-09-30T10:05:00.000Z", "started_monotonic_ns": 1, "returncode": 0,
           "stderr_tail": "", "error": None, "finished_utc": "2026-09-30T10:05:02.000Z"}


def coverage(verdict: str = "complete", since: int = T0_EPOCH, until: int | str = T1_EPOCH) -> str:
    return (f"coverage={verdict}\nrequested_since_guest_epoch={since}\nrequested_since_utc=x\n"
            f"requested_until_guest_epoch={until}\nrequested_until_utc=x\nexpected=die,start\n"
            "container=egw-controller-1\nrule_R7=held: x\n")


def docker_event(epoch_ns: int, action: str = "die", name: str = n1.CONTROLLER_CONTAINER,
                 kind: str = "container") -> str:
    return json.dumps({"Type": kind, "Action": action, "Actor": {"ID": "c" * 64, "Attributes": {"name": name}},
                       "time": epoch_ns // NS, "timeNano": epoch_ns})


DIE_IN_WINDOW = docker_event((T0_EPOCH + 300) * NS + 17)
DOCKER_LINES = [docker_event((T0_EPOCH + 1) * NS, "exec_start"), docker_event((T0_EPOCH + 299) * NS, "kill"),
                DIE_IN_WINDOW, docker_event((T0_EPOCH + 302) * NS, "start")]

OLD_PROCESS = "2026-09-30T09:00:00.000000Z"
NEW_PROCESS = "2026-09-30T10:05:03.000000Z"
THIRD_PROCESS = "2026-09-30T10:07:41.000000Z"


def reading(started_at: str | None, monotonic_ns) -> dict:
    """A row of controller_metrics.csv as csv.DictReader gives it: strings,
    an empty cell for a field the controller did not send."""
    return {"ts_utc": "2026-09-30T10:05:00Z", "started_at": started_at or "",
            "monotonic_ns": "" if monotonic_ns is None else str(monotonic_ns)}


#: The controller's readings of the restart, on the clock of the events'
#: received_monotonic_ns: the old process's last reading at 4000, the new
#: one's first at 4500, before m2's redelivery (5000).
READINGS = [reading(OLD_PROCESS, 3000), reading(OLD_PROCESS, 4000), reading(NEW_PROCESS, 4500),
            reading(NEW_PROCESS, 5500)]


def placed_deaths(readings: list[dict] | None = None) -> list[dict]:
    """The run's one death, placed by ``readings`` (READINGS by default)."""
    deaths, why = n1.controller_deaths(RESTART, DOCKER_LINES, coverage(),
                                       readings=READINGS if readings is None else readings)
    assert why is None and len(deaths) == 1
    return deaths


def test_case_11_a_death_with_its_captured_die_names_the_identity() -> None:
    deaths, why = n1.controller_deaths(RESTART, DOCKER_LINES, coverage(), readings=READINGS)
    assert why is None
    assert len(deaths) == 1 and deaths[0]["source"] == n1.SOURCE_DEATH
    assert deaths[0]["die_time_nano"] == (T0_EPOCH + 300) * NS + 17
    doc = report(a3_ends=[], deaths=deaths)
    assert named(doc) == ["m2"]
    assert [s["source"] for s in doc["n1_applied_unconfirmed"][0]["possible_sources"]] == [n1.SOURCE_DEATH]


def test_at_most_one_death_per_run_from_the_restart_source() -> None:
    lines = DOCKER_LINES + [docker_event((T0_EPOCH + 400) * NS)]
    deaths, why = n1.controller_deaths(RESTART, lines, coverage())
    assert why is None and len(deaths) == 1 and deaths[0]["dies_in_window"] == 2


def test_the_capture_window_is_r7s_half_open_second_range() -> None:
    edge = docker_event((T1_EPOCH + 1) * NS - 1)
    assert n1.controller_deaths(RESTART, [edge], coverage())[0]
    beyond = docker_event((T1_EPOCH + 1) * NS)
    assert n1.controller_deaths(RESTART, [beyond], coverage())[0] == []
    at_t0 = docker_event(T0_EPOCH * NS)
    assert n1.controller_deaths(RESTART, [at_t0], coverage())[0]


@pytest.mark.parametrize("variant", ["no die", "die in the replay", "another container", "not read",
                                     "capture incomplete", "no window", "coverage not read", "not a container"])
def test_case_12_a_death_without_its_captured_die_is_no_source(variant: str) -> None:
    lines, cov = DOCKER_LINES, coverage()
    if variant == "no die":
        lines = [ln for ln in DOCKER_LINES if ln != DIE_IN_WINDOW]
    elif variant == "die in the replay":
        lines = [docker_event((T0_EPOCH - 60) * NS)]
    elif variant == "another container":
        lines = [docker_event((T0_EPOCH + 300) * NS, name="egw-mongodb-1")]
    elif variant == "not read":
        lines = None
    elif variant == "capture incomplete":
        cov = coverage("incomplete")
    elif variant == "no window":
        cov = coverage(until="null")
    elif variant == "coverage not read":
        cov = None
    else:
        lines = [docker_event((T0_EPOCH + 300) * NS, kind="network")]
    deaths, why = n1.controller_deaths(RESTART, lines, cov)
    assert deaths == [] and why
    doc = report(a3_ends=[], deaths=deaths, deaths_note=why)
    assert named(doc) == [] and failed(doc, "m2") == ["2"]


def test_a_coverage_record_whose_first_line_is_not_complete_is_no_capture() -> None:
    cov = "reason=x\n" + coverage()
    assert n1.controller_deaths(RESTART, DOCKER_LINES, cov)[0] == []


@pytest.mark.parametrize("record", [
    None,
    {**RESTART, "returncode": 1},
    {**RESTART, "error": "timed out"},
    {**RESTART, "executed": False},
    {**RESTART, "returncode": False},
    {**RESTART, "finished_utc": None},
    "not a record",
])
def test_case_13_a_die_without_a_good_restart_record_is_no_source(record) -> None:
    deaths, why = n1.controller_deaths(record, DOCKER_LINES, coverage())
    assert deaths == [] and why
    assert named(report(a3_ends=[], deaths=deaths)) == []


def _two_devices(ends: list[dict]) -> dict:
    sent_records = SENT + [sent("n0", 0, device=E), sent("n5", 5, device=E)]
    events = EVENTS + [line("n0", 0, "accepted", 3000, device=E), line("n5", 5, "duplicate", 6000, device=E)]
    deaths = placed_deaths()
    return report(sent_records=sent_records, events=events,
                  twins_before={D: twin(10, "old", 9), E: twin(20, "old", 9)},
                  twins_after={D: twin(13, R, 2), E: twin(22, R, 5)}, a3_ends=ends, deaths=deaths)


def test_case_14_one_death_two_devices_names_none_and_an_own_end_frees_it() -> None:
    doc = _two_devices([])
    assert named(doc) == []
    assert failed(doc, "m2") == ["2"] and failed(doc, "n5") == ["2"]
    assert "cannot be told" in unexplained(doc)["m2"]["reason"]
    doc = _two_devices([end(E, 5500, 3)])
    assert sorted(named(doc)) == ["m2", "n5"]
    sources = {c["message_id"]: [s["source"] for s in c["possible_sources"]] for c in doc["n1_applied_unconfirmed"]}
    assert sources["m2"] == [n1.SOURCE_DEATH]
    assert sources["n5"][0] == n1.SOURCE_A3


def test_a_death_contended_by_a_device_that_fails_elsewhere_is_still_contended() -> None:
    """The death's one delivery may have been E's duplicate-only identity
    (not applied: E shows no surplus); then D's surplus has no source. Which
    one it explained cannot be told, so D's identity is not named."""
    sent_records = SENT + [sent("n5", 5, device=E)]
    events = EVENTS + [line("n5", 5, "duplicate", 6000, device=E)]
    deaths, _why = n1.controller_deaths(RESTART, DOCKER_LINES, coverage())
    doc = report(sent_records=sent_records, events=events,
                 twins_before={D: twin(10, "old", 9), E: twin(20, "old", 9)},
                 twins_after={D: twin(13, R, 2), E: twin(20, "old", 9)}, a3_ends=[], deaths=deaths)
    assert named(doc) == []
    assert "2" in failed(doc, "m2") and "3" in failed(doc, "n5")


def test_one_death_serves_one_identity_of_a_device_whose_ends_serve_the_rest() -> None:
    deaths = placed_deaths()
    doc = _two_candidates({D: twin(14, R, 3)}, [end(D, 4000, 7)], deaths=deaths)
    assert named(doc) == ["m2", "m3"]
    doc = _two_candidates({D: twin(14, R, 3)}, [], deaths=deaths)
    assert named(doc) == [] and failed(doc, "m2") == ["2"]


def test_sources_not_read_are_named_in_the_reason() -> None:
    doc = report(a3_ends=None, a3_note="no --controller-log given", deaths=None, deaths_note="no restart evidence")
    reason = unexplained(doc)["m2"]["reason"]
    assert "controller log not read" in reason and "no --controller-log given" in reason
    assert doc["sources"]["controller_log_read"] is False and doc["sources"]["deaths_read"] is False


# ---------------------------------------------------------------------------
# drift pins: the A3 parser against the proof's, the message against mqtt.py
# ---------------------------------------------------------------------------


def test_case_20_the_a3_parser_reads_what_the_proofs_a5_parser_reads() -> None:
    lines = [
        _a3_line(D, 1_205 * NS),                                          # docker --timestamps prefix
        _a3_line(E, 1_300 * NS, prefix=""),                               # no prefix
        _a3_line(D, 1_400 * NS, prefix="egw-controller-1  | "),           # compose prefix
        _a3_line(D, 1_500 * NS, level="INFO", cause="stop"),               # graceful stop: not A3
        _a3_line(D, 1_600 * NS, message="MQTT connection end already requested; acknowledgement closed",
                 level="INFO"),
        _a3_line(D, None, topic="not/a/topic"),                           # no device, no stamp
        "not a json line",
        "",
        _a3_line(E, 1_700 * NS, cause="publish-failed"),
    ]
    mine = n1.a3_connection_ends(lines)
    proofs, _notes = pe.a5_occurrences(lines)
    assert len(mine) == len(proofs) == 5
    for ours, theirs in zip(mine, proofs):
        assert ours["line"] == theirs["line"]
        assert ours["ts"] == theirs["ts"]
        assert ours["cause"] == theirs["cause"] and ours["connection"] == theirs["connection"]
        assert ours["device_uuid"] == theirs["device_uuid"]
        assert ours["received_monotonic_ns"] == theirs["identity"]["received_monotonic_ns"]
    assert n1.A3_END_MESSAGE == pe.A5_MESSAGE


def test_the_a3_message_is_the_controllers_at_both_levels() -> None:
    source = (SRC_DIR / "egw_controller" / "mqtt.py").read_text(encoding="utf-8")
    levels = set(re.findall(r"logger\.(info|error)\(\s*" + re.escape(json.dumps(n1.A3_END_MESSAGE)), source))
    assert levels == {"info", "error"}


def test_the_module_is_stdlib_only_and_never_imports_the_proof() -> None:
    tree = ast.parse((SRC_DIR / "egw_experiments" / "n1_report.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import of the package"
            imported.add((node.module or "").split(".")[0])
    # stdlib only: in particular never egw_experiments.proof_evaluator, which
    # imports itest_reconcile at its top (a cycle through delta's import).
    assert imported <= set(sys.stdlib_module_names) | {"__future__"}, imported


# ---------------------------------------------------------------------------
# condition 3's arithmetic is delta's
# ---------------------------------------------------------------------------


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_case_21_the_device_arithmetic_equals_what_delta_prints(tmp_path, capsys) -> None:
    run_dir = tmp_path / R
    run_dir.mkdir()
    events = EVENTS + [line("m0", 0, "duplicate", 5100), line("m3", 3, "rejected", 5200)]
    _jsonl(run_dir / "events.jsonl", events)
    _jsonl(run_dir / "sent_events.jsonl", SENT)
    warmup = [line("w0", 0, "accepted", 10, run_id=f"{R}.warmup"), line("w1", 7, "accepted", 20, run_id=f"{R}.warmup")]
    also = tmp_path / "warmup.events.jsonl"
    _jsonl(also, warmup)
    snapshot = {"label": "x", "seed": 42}
    _write(rec.sib(str(run_dir), ".twins.before.json"), {**snapshot, "devices": {D: twin(10, "old", 9)}})
    _write(rec.sib(str(run_dir), ".twins.after.json"), {**snapshot, "devices": {D: twin(16, R, 2)}})
    for extra, lines in (([], events), (["--also", str(also)], events + warmup)):
        rec.main(["delta", str(run_dir), *extra])
        out = capsys.readouterr().out
        match = re.search(rf"{D} smartwatch: .*\(delta (-?\d+)\); accepted records in \S+ (\d+);", out)
        assert match, out
        doc = n1.n1_applied_unconfirmed(run_id=R, sent_records=SENT, events=lines,
                                        twins_before={D: twin(10, "old", 9)}, twins_after={D: twin(16, R, 2)})
        assert doc["devices"][D]["delta"] == int(match.group(1))
        assert doc["devices"][D]["accepted_lines"] == int(match.group(2))


# ---------------------------------------------------------------------------
# round 0 of the verification: the duplicate-only identities of another run
# id, the first redelivery, and a capture window that never raises
# ---------------------------------------------------------------------------


def test_a_duplicate_only_identity_of_another_run_id_on_the_device_blocks_the_naming() -> None:
    """delta's arithmetic counts every accepted line of the compared log,
    whatever its run id (the --also file of the warm-up run): a duplicate-only
    identity of that other run on the device may be the one the twin applied,
    so the device has two duplicate-only identities against an excess of one
    and none is named (adopted rule 2, condition 3)."""
    events = EVENTS + [line("w0", 0, "duplicate", 3000, run_id=f"{R}.warmup")]
    doc = report(events=events)
    assert named(doc) == []
    assert failed(doc, "m2") == ["3"]
    assert "another run id" in unexplained(doc)["m2"]["reason"]
    assert doc["devices"][D]["other_run_duplicate_only"] == 1
    # It is not an identity of this run: listed in neither list.
    assert "w0" not in unexplained(doc)
    # Nor with a surplus that would also cover it: the reported count (m2
    # alone) would not equal the excess.
    doc = report(events=events, twins_after={D: twin(14, R, 2)})
    assert named(doc) == [] and failed(doc, "m2") == ["3"]


def test_another_run_ids_identities_block_only_their_own_device_and_only_when_duplicate_only() -> None:
    other = f"{R}.warmup"
    on_e = EVENTS + [line("w0", 0, "duplicate", 3000, device=E, run_id=other)]
    assert named(report(events=on_e)) == ["m2"]
    # An identity of the other run with an accepted line (N2 there) is not
    # duplicate-only; its accepted line is in the device's accepted lines.
    n2 = EVENTS + [line("w0", 0, "accepted", 2500, run_id=other), line("w0", 0, "duplicate", 3000, run_id=other)]
    assert named(report(events=n2, twins_after={D: twin(14, R, 2)})) == ["m2"]


def test_the_first_duplicate_line_is_the_earliest_received_whatever_the_file_order() -> None:
    """P-4's order rule reads the identity's first redelivery: the earliest
    received duplicate line (the finite proof reads the minimum), not the
    first line of the file. An end received between the two redeliveries
    cannot precede the first one."""
    events = EVENTS[:2] + [line("m2", 2, "duplicate", 7000), line("m2", 2, "duplicate", 5000)]
    doc = report(events=events, a3_ends=[end(D, 6000, 7)])
    assert named(doc) == [] and failed(doc, "m2") == ["2"]
    assert unexplained(doc)["m2"]["first_duplicate_received_monotonic_ns"] == 5000
    doc = report(events=events, a3_ends=[end(D, 4000, 7)])
    assert named(doc) == ["m2"]
    assert doc["n1_applied_unconfirmed"][0]["first_duplicate_received_monotonic_ns"] == 5000


def test_a_duplicate_line_without_a_stamp_leaves_the_first_redelivery_unread() -> None:
    """A duplicate line without received_monotonic_ns may be the first
    redelivery: the order is not shown, so no end can serve (an unreadable
    stamp is never N1)."""
    events = EVENTS[:2] + [line("m2", 2, "duplicate", 5000), dict(line("m2", 2, "duplicate", 0),
                                                                  received_monotonic_ns=None)]
    doc = report(events=events, a3_ends=[end(D, 4000, 7)])
    assert named(doc) == [] and failed(doc, "m2") == ["2"]
    assert unexplained(doc)["m2"]["first_duplicate_received_monotonic_ns"] is None


@pytest.mark.parametrize("value", ["²", "١٧٩٠٠٠٠٠٠٠",
                                   "+1790000000", "1_790_000_000"])
def test_the_capture_window_is_read_in_ascii_digits_only_and_never_raises(value: str) -> None:
    """events_coverage.py reads the window with re.fullmatch("[0-9]+"): any
    other value gives no window (never an exception, whatever str.isdigit
    or int would make of it)."""
    for cov in (coverage(since=value), coverage(until=value)):
        window, why = n1.capture_window(cov)
        assert window is None and "whole-number" in why
        deaths, why = n1.controller_deaths(RESTART, DOCKER_LINES, cov)
        assert deaths == [] and why


# ---------------------------------------------------------------------------
# round 1 of the verification: lines without one readable device, and inputs
# that raised (the recursion of the matching and of the JSON decoder, the
# integer digit limit)
# ---------------------------------------------------------------------------


def _no_device(record: dict, variant: str) -> dict:
    record = dict(record)
    if variant == "missing":
        del record["device_uuid"]
    else:
        record["device_uuid"] = {"null": None, "empty": "", "not a string": 7}[variant]
    return record


@pytest.mark.parametrize("variant", ["missing", "null", "empty", "not a string"])
def test_a_duplicate_only_identity_whose_lines_name_no_device_blocks_its_published_device(variant) -> None:
    """mx is published on D, but its duplicate line names no device: it may
    be the identity the twin applied on D (the twin even ended on its seq),
    so D has two duplicate-only identities against an excess of one and
    none is named (adopted rule 2, condition 3: all or nothing per device)."""
    mx = _no_device(line("mx", 3, "duplicate", 5500), variant)
    doc = report(events=EVENTS + [mx], sent_records=SENT + [sent("mx", 3)], twins_after={D: twin(13, R, 3)})
    assert doc["devices"][D]["excess"] == 1
    assert named(doc) == []
    assert "3" in failed(doc, "m2") and "3" in failed(doc, "mx")
    # Unpublished as well, its device cannot be told at all: it may count on
    # any device, so it blocks every one.
    doc = report(events=EVENTS + [mx], twins_after={D: twin(13, R, 3)})
    assert named(doc) == [] and "3" in failed(doc, "m2")


def test_a_duplicate_only_identity_whose_lines_name_two_devices_blocks_both() -> None:
    """m9's two duplicate lines name D and E: which twin it may have reached
    cannot be told, so neither device names its own identity."""
    sent_records = SENT + [sent("n5", 5, device=E), sent("m9", 9)]
    events = EVENTS + [line("n5", 5, "duplicate", 6000, device=E), line("m9", 9, "duplicate", 5600),
                       line("m9", 9, "duplicate", 5700, device=E)]
    doc = report(sent_records=sent_records, events=events,
                 twins_before={D: twin(10, "old", 9), E: twin(20, "old", 9)},
                 twins_after={D: twin(13, R, 9), E: twin(21, R, 5)},
                 a3_ends=[end(D, 4000, 7), end(E, 5500, 8)])
    assert named(doc) == []
    assert "3" in failed(doc, "m2") and "3" in failed(doc, "n5") and "3" in failed(doc, "m9")


@pytest.mark.parametrize("variant", ["missing", "null", "not a string"])
def test_an_accepted_line_without_a_readable_device_names_nothing(variant) -> None:
    """m1's accepted line names no device: delta's arithmetic (the lines'
    device_uuid) counts it on no device, so a device's accepted lines may be
    undercounted and its excess overstated - here the twin grew by exactly
    D's two accepted records, m2 was not applied, and nothing is named."""
    m1 = _no_device(line("m1", 1, "accepted", 2000), variant)
    doc = report(events=[EVENTS[0], m1, EVENTS[2]], twins_after={D: twin(12, R, 2)})
    assert doc["devices"][D]["accepted_lines"] == 1  # delta's count, unchanged
    assert named(doc) == [] and failed(doc, "m2") == ["3"]
    assert "without a readable device" in unexplained(doc)["m2"]["reason"]
    # Of another run id too (an --also file's line, which delta counts).
    warm = _no_device(line("w1", 1, "accepted", 2000, run_id=f"{R}.warmup"), variant)
    assert named(report(events=EVENTS + [warm])) == []


@pytest.mark.parametrize("identity", ["another run id", "no readable message_id"])
def test_a_duplicate_only_line_of_no_readable_device_that_is_not_this_runs_blocks_every_device(identity) -> None:
    other = line("w0", 0, "duplicate", 3000, run_id=f"{R}.warmup")
    del other["device_uuid"]
    if identity == "no readable message_id":
        other = dict(other, run_id=R, message_id=None)
    doc = report(events=EVENTS + [other])
    assert named(doc) == [] and failed(doc, "m2") == ["3"]


def test_many_identities_and_ends_never_raise_and_are_matched() -> None:
    """The matching of identities to A3 ends is not recursive: 1200
    duplicate-only identities, each with the same 1200 ends before it (the
    shape whose augmenting paths are the longest), are all served; with one
    end fewer one identity is left without a source. The twin shows no
    surplus, so condition 3 alone fails and nothing is named either way."""
    count = 1200
    sent_records = [sent(f"k{i}", i) for i in range(count)]
    events = [line(f"k{i}", i, "duplicate", NS + i) for i in range(count)]
    ends = [end(D, 1 + i, i + 1) for i in range(count)]
    kwargs = dict(run_id=R, sent_records=sent_records, events=events, twins_before={D: twin(0, "old", 0)},
                  twins_after={D: twin(0, R, count - 1)}, deaths=[])
    doc = n1.n1_applied_unconfirmed(**kwargs, a3_ends=ends)
    assert doc["n1_applied_unconfirmed"] == []
    assert {tuple(case["failed"]) for case in doc["duplicate_only_unexplained"]} == {("3",)}
    doc = n1.n1_applied_unconfirmed(**kwargs, a3_ends=ends[1:])
    assert {tuple(case["failed"]) for case in doc["duplicate_only_unexplained"]} == {("2", "3")}
    assert len(doc["duplicate_only_unexplained"]) == count


DEEP = "[" * 100_000


def test_a_deeply_nested_json_line_is_not_read_never_raised(tmp_path) -> None:
    """The JSON decoder raises RecursionError (not a ValueError) on deep
    nesting: every reader takes such a line as one that is not a record."""
    jsonl = tmp_path / "sent_events.jsonl"
    jsonl.write_text(json.dumps(SENT[0]) + "\n" + "{\"a\": " + DEEP + "\n", encoding="utf-8")
    assert n1.read_jsonl(jsonl) == ([SENT[0]], None)
    obj = tmp_path / "twins.after.json"
    obj.write_text("{\"devices\": " + DEEP + "\n", encoding="utf-8")
    records, why = n1.read_json_object(obj)
    assert records is None and "unreadable" in why
    deep_log = "2026-09-30T10:03:10.000000000Z {\"message\": " + DEEP
    assert n1.a3_connection_ends([deep_log, _a3_line(D, 4000)])[0]["line"] == 2
    deaths, why = n1.controller_deaths(RESTART, ["{\"Action\": " + DEEP] + DOCKER_LINES, coverage())
    assert why is None and deaths[0]["die_line"] == 4


def test_a_capture_window_beyond_the_integer_digit_limit_is_no_window() -> None:
    """int() refuses a string of more than 4300 digits (ValueError): such a
    window is not a whole-number window, never an exception."""
    huge = "1" + "0" * 4300
    for cov in (coverage(since=huge), coverage(until=huge)):
        window, why = n1.capture_window(cov)
        assert window is None and "whole-number" in why
        deaths, why = n1.controller_deaths(RESTART, DOCKER_LINES, cov)
        assert deaths == [] and why


# ---------------------------------------------------------------------------
# review of 2026-09-30: the events copy split at newlines only (D2-1), the
# death contended by an identity no A3 end is matched to (D2-2), a capture
# window key given twice (D2-3)
# ---------------------------------------------------------------------------

F = "ffffffff-0000-5000-8000-00000000000f"


@pytest.mark.parametrize("separator", [" ", " ", "\u0085"])
def test_a_raw_line_separator_inside_a_string_field_does_not_split_the_line(tmp_path, separator) -> None:
    """The controller writes its lines with ensure_ascii=False, so a failed
    line's error (a snippet of Ditto's body) may hold a raw U+2028, U+2029 or
    U+0085. The copy is split at newlines only, as the analysis reader splits
    it: m2 keeps its failed line, so it is not duplicate-only and nothing is
    named or listed."""
    failed_line = dict(line("m2", 2, "failed", 4500), error=f"Ditto 502: bad{separator}gateway")
    path = tmp_path / "events.post-drain.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                            for r in EVENTS[:2] + [failed_line, EVENTS[2]]), encoding="utf-8")
    records, why = n1.read_jsonl(path)
    assert why is None and records == analyze_mod._read_jsonl(path)
    assert [r["outcome"] for r in records] == ["accepted", "accepted", "failed", "duplicate"]
    doc = report(events=records)
    assert named(doc) == [] and doc["duplicate_only_unexplained"] == []


@pytest.mark.parametrize("variant", ["lines naming two other devices", "a duplicate line without a message_id",
                                     "another run id's identity"])
def test_the_death_is_contended_by_a_duplicate_only_identity_no_a3_end_is_matched_to(variant) -> None:
    """m2 on D needs the one death (no A3 end). A duplicate-only identity on
    other devices to which no device's A3 ends are matched - its lines name
    two devices, its line has no readable message_id, or it is of another
    run id - may have been the death's one delivery (not applied): which one
    the death explained cannot be told, so m2 is not named. An own A3 end
    still frees m2, and the death is then no possible source of it."""
    deaths = placed_deaths()
    assert named(report(a3_ends=[], deaths=deaths)) == ["m2"]
    sent_records = SENT
    if variant == "lines naming two other devices":
        extra = [line("m9", 9, "duplicate", 5600, device=E), line("m9", 9, "duplicate", 5700, device=F)]
        sent_records = SENT + [sent("m9", 9, device=E)]
    elif variant == "a duplicate line without a message_id":
        extra = [dict(line("m9", 9, "duplicate", 5600, device=E), message_id=None)]
    else:
        extra = [line("w9", 9, "duplicate", 5600, device=E, run_id=f"{R}.warmup")]
    doc = report(a3_ends=[], deaths=deaths, events=EVENTS + extra, sent_records=sent_records)
    assert named(doc) == []
    assert failed(doc, "m2") == ["2"] and "cannot be told" in unexplained(doc)["m2"]["reason"]
    doc = report(a3_ends=[end(D, 4000, 7)], deaths=deaths, events=EVENTS + extra, sent_records=sent_records)
    assert named(doc) == ["m2"]
    assert [s["source"] for s in doc["n1_applied_unconfirmed"][0]["possible_sources"]] == [n1.SOURCE_A3]


@pytest.mark.parametrize("key", ["requested_since_guest_epoch", "requested_until_guest_epoch"])
@pytest.mark.parametrize("order", ["earlier first", "later first"])
def test_a_capture_window_key_given_twice_is_ambiguous_and_gives_no_death(key, order) -> None:
    """As decision 1a reads the same record (proved_down.py): each window key
    exactly once, or the window is ambiguous and there is no death, whichever
    of the two values comes first."""
    own = T0_EPOCH if key == "requested_since_guest_epoch" else T1_EPOCH
    values = (own - 200, own) if order == "earlier first" else (own, own - 200)
    cov = coverage().replace(f"{key}={own}\n", "".join(f"{key}={value}\n" for value in values))
    assert cov.count(f"{key}=") == 2
    window, why = n1.capture_window(cov)
    assert window is None and "ambiguous" in why
    deaths, why = n1.controller_deaths(RESTART, DOCKER_LINES, cov)
    assert deaths == [] and "ambiguous" in why


# ---------------------------------------------------------------------------
# review of PR #53, F2: the death serves an identity only when the controller
# readings place it before that identity's first redelivery (one clock: the
# readings' monotonic_ns and the lines' received_monotonic_ns, CONTRACTS 5)
# ---------------------------------------------------------------------------


def test_f2_without_controller_readings_the_death_serves_no_identity() -> None:
    """The finding: a captured die and a surplus of one named m2 by count
    alone. Without the readings nothing places the death before m2's
    redelivery: m2 is unexplained (condition 2), its facts still reported."""
    deaths, why = n1.controller_deaths(RESTART, DOCKER_LINES, coverage())
    assert why is None and len(deaths) == 1  # the death is still recorded
    doc = report(a3_ends=[], deaths=deaths)
    assert doc["devices"][D]["excess"] == 1
    assert named(doc) == [] and failed(doc, "m2") == ["2"]
    case = unexplained(doc)["m2"]
    assert "not shown to precede" in case["reason"] and "not read" in case["reason"]
    assert case["first_duplicate_received_monotonic_ns"] == 5000 and case["seq"] == 2


def test_f2_a_duplicate_before_an_unrelated_later_death_is_unexplained() -> None:
    """The PM's counterexample: m2's redelivery (5000) was received before
    the restart the readings show (the old process read until 6000, the new
    one from 7000), with the device's surplus 1: the later death cannot
    explain the earlier duplicate."""
    later = [reading(OLD_PROCESS, 4000), reading(OLD_PROCESS, 6000), reading(NEW_PROCESS, 7000)]
    doc = report(a3_ends=[], deaths=placed_deaths(later))
    assert doc["devices"][D]["excess"] == 1
    assert named(doc) == [] and failed(doc, "m2") == ["2"]
    assert "not shown to precede" in unexplained(doc)["m2"]["reason"]


#: Readings that do not show the death before m2's redelivery (5000).
ORDER_NOT_SHOWN = {
    "no reading": [],
    "no process change": [reading(OLD_PROCESS, 3000), reading(OLD_PROCESS, 4000)],
    "two process changes": [reading(OLD_PROCESS, 3000), reading(NEW_PROCESS, 3500), reading(THIRD_PROCESS, 4500)],
    "back to the first process": [reading(OLD_PROCESS, 3000), reading(NEW_PROCESS, 3500),
                                  reading(OLD_PROCESS, 4500)],
    "a reading without started_at": [reading(OLD_PROCESS, 3000), reading(None, 3500), reading(NEW_PROCESS, 4500)],
    "the old process's last monotonic_ns empty": [reading(OLD_PROCESS, 3000), reading(OLD_PROCESS, None),
                                                  reading(NEW_PROCESS, 4500)],
    "the new process's first monotonic_ns not an integer": [reading(OLD_PROCESS, 4000),
                                                            reading(NEW_PROCESS, "4.5e3"),
                                                            reading(NEW_PROCESS, 4600)],
    "a fractional monotonic_ns": [reading(OLD_PROCESS, 4000), reading(NEW_PROCESS, "4500.5")],
    "the bounding readings out of order": [reading(OLD_PROCESS, 4600), reading(NEW_PROCESS, 4500)],
    "the duplicate between the bounding readings": [reading(OLD_PROCESS, 4000), reading(NEW_PROCESS, 6000)],
    "the duplicate at the new process's first reading": [reading(OLD_PROCESS, 4000), reading(NEW_PROCESS, 5000)],
}


@pytest.mark.parametrize("case", sorted(ORDER_NOT_SHOWN))
def test_f2_readings_that_do_not_place_the_death_before_the_redelivery_leave_it_unexplained(case: str) -> None:
    doc = report(a3_ends=[], deaths=placed_deaths(ORDER_NOT_SHOWN[case]))
    assert named(doc) == [] and failed(doc, "m2") == ["2"]
    assert "not shown to precede" in unexplained(doc)["m2"]["reason"]


def test_f2_readings_not_read_leave_the_death_unplaced_and_say_why() -> None:
    deaths, why = n1.controller_deaths(RESTART, DOCKER_LINES, coverage(), readings=None,
                                       readings_note="controller_metrics.csv missing")
    assert why is None and deaths[0]["process_change"] is None
    doc = report(a3_ends=[], deaths=deaths)
    assert named(doc) == [] and "controller_metrics.csv missing" in unexplained(doc)["m2"]["reason"]


def test_f2_a_death_the_readings_place_before_the_redelivery_names_the_identity() -> None:
    """The demonstrated case: one process change, bounded by readings with
    integer monotonic_ns, the new process's first reading (4500) before
    m2's first redelivery (5000), the device's surplus 1."""
    (death,) = placed_deaths()
    assert death["process_change"] == {"old_process_last_reading": 2, "old_process_last_monotonic_ns": 4000,
                                       "new_process_first_reading": 3, "new_process_first_monotonic_ns": 4500}
    assert death["order_note"] is None
    doc = report(a3_ends=[], deaths=[death])
    assert named(doc) == ["m2"]
    (source,) = doc["n1_applied_unconfirmed"][0]["possible_sources"]
    assert source["source"] == n1.SOURCE_DEATH and source["new_process_first_monotonic_ns"] == 4500


def test_f2_the_death_is_matched_with_the_ends_as_one_more_source_at_its_reading() -> None:
    """m2 (5000) and m3 (5500) on D, one A3 end of D at 5200, which precedes
    m3's redelivery only. A death placed at 4500 serves m2: both named.
    Placed at 5300 it too precedes m3's redelivery only: m2 has no source,
    so neither is named (all or nothing), where the count alone named both."""
    ends = [end(D, 5200, 8)]
    assert named(_two_candidates({D: twin(14, R, 3)}, ends, deaths=placed_deaths())) == ["m2", "m3"]
    late = placed_deaths([reading(OLD_PROCESS, 4000), reading(NEW_PROCESS, 5300)])
    doc = _two_candidates({D: twin(14, R, 3)}, ends, deaths=late)
    assert named(doc) == [] and failed(doc, "m2") == ["2"] and failed(doc, "m3") == ["2"]
    assert "not shown to precede" in unexplained(doc)["m2"]["reason"]


def test_f2_the_death_is_listed_only_for_an_identity_whose_redelivery_it_precedes() -> None:
    """m2 is served by its own A3 end (4000): a death placed after m2's
    redelivery is no possible source of it; one placed before it is."""
    later = placed_deaths([reading(OLD_PROCESS, 6000), reading(NEW_PROCESS, 7000)])
    doc = report(deaths=later)
    assert named(doc) == ["m2"]
    assert [s["source"] for s in doc["n1_applied_unconfirmed"][0]["possible_sources"]] == [n1.SOURCE_A3]
    doc = report(deaths=placed_deaths())
    assert [s["source"] for s in doc["n1_applied_unconfirmed"][0]["possible_sources"]] == [
        n1.SOURCE_A3, n1.SOURCE_DEATH]


def test_f2_the_readings_are_read_from_the_samplers_csv_and_never_raise(tmp_path) -> None:
    import csv

    from egw_experiments.controller_metrics import CSV_HEADER

    path = tmp_path / "controller_metrics.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows({"ts_utc": "2026-09-30T10:05:00Z", "started_at": row["started_at"],
                          "monotonic_ns": row["monotonic_ns"]} for row in READINGS)
    readings, why = n1.read_controller_readings(path)
    assert why is None and len(readings) == 4
    change, why = n1.process_change(readings)
    assert why is None and change["new_process_first_monotonic_ns"] == 4500
    assert n1.read_controller_readings(tmp_path / "absent.csv") == (None, "absent.csv missing")
    # A field beyond the csv module's limit raises csv.Error: not read, never raised.
    path.write_text(",".join(CSV_HEADER) + "\n" + "x" * 200_000 + "\n", encoding="utf-8")
    readings, why = n1.read_controller_readings(path)
    assert readings is None and "unreadable" in why
