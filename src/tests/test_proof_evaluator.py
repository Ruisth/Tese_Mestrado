"""Tests for egw_experiments.proof_evaluator (ADR 0011, "The finite proof").

The evaluator applies S1-S6, R1-R4 and the inconclusive rule by identity to
the post-drain copy of the events and the twin snapshots of one proof
session, and writes one verdict document with three sections never merged.
These cases pin: every rule text to the ADR (read when the test runs, so a
later edit of the ADR is tested as it is); the readings in file order with
empty cells read as absent, never zero; each identification rule the design
flags (P-1 to P-7, E-1 to E-6) on a small in-memory scenario (three
devices, one kill on the controller clock, a host anchor for the report);
the precedence of an observed refutation; the CLI's exit codes; and, last,
the loader against a run directory the harness itself built with the
fixtures of test_experiments_run (the fake simulator and the recorded
item-18 hooks: no broker, no docker, no network).

Test 33 replaces two of the fixture's hooks with scripts of its own: the
fixture's `write` mode carries neither identities in the post-drain copy
nor an after snapshot that differs from the before one, so the post-drain
fetch and the twin snapshot are handed scripts that copy files this test
writes; the sent lines are rewritten through a wrapper of the fake
simulator; the controller /metrics poll is stubbed in-process, as the
sampler's own tests stub it.
"""
from __future__ import annotations

import csv
import itertools
import json
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

from egw_experiments import controller_metrics as metrics_mod
from egw_experiments import proof_evaluator as pe
from egw_experiments import run as run_mod
from egw_experiments.checksums import write_sha256sums
from egw_experiments.controller_metrics import CSV_HEADER
from egw_experiments.run import (
    POST_DRAIN_EVENTS_FILENAME,
    SUT_LOG_FETCH_FLAGS,
    SUT_LOG_FILES,
    TWIN_SNAPSHOT_FILES,
)
from test_experiments_run import (  # noqa: F401  (fixtures registered by import)
    CONFIG_IDENTITY,
    PY,
    _item18_run,
    _plan_seed,
    _snapshot_devices,
    fast_run,
    plan_path,
)

RID = "proof-adr0011-r01"
NS = 1_000_000_000
D1 = "11111111-1111-4111-8111-111111111111"
D2 = "22222222-2222-4222-8222-222222222222"
D3 = "33333333-3333-4333-8333-333333333333"
D4 = "44444444-4444-4444-8444-444444444444"
#: The two controller processes, as /metrics names them (started_at).
P0 = "2026-09-25T10:00:00Z"
P1 = "2026-09-25T10:02:35Z"
#: The kill on the controller clock: after the last pre-kill reading and
#: before the first post-kill one (monotonic_ns as the controller reports).
K_LOWER = 1_150 * NS
K_UPPER = 1_180 * NS
#: The host: the measured window starts at host monotonic 350 s, the kill
#: (restart.started_monotonic_ns) at 500 s = 150 s later, as the plan says.
HOST_START_NS = 350 * NS
HOST_KILL_NS = 500 * NS
#: The four identities of the scenario: (message_id, device, seq,
#: publish_monotonic_ns on the host): A and D lined before the kill, B
#: published before it and lined only after, C published while away.
A = ("a-mid", D1, 0, 360 * NS)
B = ("b-mid", D1, 1, 400 * NS)
C = ("c-mid", D2, 0, 510 * NS)
D = ("d-mid", D3, 0, 370 * NS)
SENT = [A, B, C, D]
#: Their post-drain lines: (message_id, device, seq, outcome,
#: received_monotonic_ns on the controller clock, error).
LINES = [
    ("a-mid", D1, 0, "accepted", 1_010 * NS, None),
    ("d-mid", D3, 0, "accepted", 1_020 * NS, None),
    ("b-mid", D1, 1, "accepted", 1_200 * NS, None),
    ("c-mid", D2, 0, "accepted", 1_210 * NS, None),
]
BEFORE = {D1: (5, "earlier", 9), D2: (5, "earlier", 9), D3: (5, "earlier", 9)}
FULL_FILES = {
    "manifest.json",
    "sent_events.jsonl",
    "events.jsonl",
    POST_DRAIN_EVENTS_FILENAME,
    *TWIN_SNAPSHOT_FILES.values(),
    "controller_metrics.csv",
    "configuration_identity.json",
    *(f"logs/sut/{name}" for name in SUT_LOG_FILES.values()),
    "SHA256SUMS",
}
STOP_RULE_HEALTHY = (
    "the stack with the candidate healthy within 20 minutes of its start (as for "
    "the broker measurement, and on the same records)"
)
STOP_RULE_ATTEMPT = "the attempt stopped 50 minutes after its first `drained` starts"


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------


def _ts(seconds: float) -> str:
    """A host wall-clock stamp: 10:00:00 is the measured window's start."""
    whole = int(seconds)
    return f"2026-09-25T10:{whole // 60:02d}:{whole % 60:02d}.000Z"


def _row(
    ts_utc: str,
    started_at: str | None,
    queue_depth: int | None,
    in_progress: int | None,
    *,
    monotonic_ns: int | None,
    unacked: int | None = None,
    subscribed: str = "true",
) -> dict[str, str]:
    """One raw controller_metrics.csv row (every column, empty = absent)."""
    row = {name: "" for name in CSV_HEADER}
    row.update(
        {
            "ts_utc": ts_utc,
            "accepted": "0",
            "rejected": "0",
            "duplicate": "0",
            "failed": "0",
            "dropped": "0",
            "queue_depth": "" if queue_depth is None else str(queue_depth),
            "received": "0",
            "in_progress": "" if in_progress is None else str(in_progress),
            "processing_errors": "0",
            "unacked": "" if unacked is None else str(unacked),
            "mqtt_connection": "1",
            "mqtt_subscribed": subscribed,
            "started_at": started_at or "",
            "wall_utc": ts_utc,
            "uptime_s": "10.0",
            "monotonic_ns": "" if monotonic_ns is None else str(monotonic_ns),
        }
    )
    return row


def _rows(*, last_pre: tuple[int | None, int | None] = (3, 1), unacked_last: int | None = 4) -> list[dict[str, str]]:
    """The readings of the scenario: the pre-kill process P0 up to K_LOWER,
    the post-kill process P1 from K_UPPER (resubscribed at its second
    reading), all in file order."""
    rows = [_row(_ts(i), P0, 3, 1, monotonic_ns=(1_000 + i) * NS, unacked=4) for i in (0, 30, 60, 90, 120)]
    rows.append(_row(_ts(150), P0, *last_pre, monotonic_ns=K_LOWER, unacked=unacked_last))
    rows.append(_row(_ts(175), P1, 0, 0, monotonic_ns=K_UPPER, unacked=0, subscribed="false"))
    rows.append(_row(_ts(180), P1, 2, 1, monotonic_ns=K_UPPER + 5 * NS, unacked=3, subscribed="true"))
    rows.append(_row(_ts(240), P1, 0, 0, monotonic_ns=K_UPPER + 65 * NS, unacked=0, subscribed="true"))
    return rows


def _sent(message_id: str, device: str, seq: int, publish: int | None, *, invalid: bool = False, run_id: str = RID) -> dict:
    return {
        "run_id": run_id,
        "message_id": message_id,
        "device_uuid": device,
        "device_type": "smartwatch",
        "seq": seq,
        "publish_monotonic_ns": publish,
        "puback_monotonic_ns": None if publish is None else publish + 5_000_000,
        "intended_invalid": invalid,
    }


def _line(message_id: str, device: str, seq: int, outcome: str, received: int | None, error: str | None = None, *, run_id: str = RID) -> dict:
    return {
        "run_id": run_id,
        "message_id": message_id,
        "device_uuid": device,
        "device_type": "smartwatch",
        "seq": seq,
        "received_monotonic_ns": received,
        "ditto_ack_monotonic_ns": received + 1_000_000 if received is not None and outcome == "accepted" else None,
        "latency_ms": 1.0 if outcome == "accepted" else None,
        "outcome": outcome,
        "attempts": 1,
        "error": error,
    }


def _twins(label: str, counts: dict[str, tuple[int | None, str | None, int | None]]) -> dict:
    """A snapshot as itest_reconcile's `snap` writes it: (accepted_count,
    last_run_id, last_seq) per device."""
    return {
        "label": label,
        "seed": 7,
        "devices": {
            device: {
                "device_type": "smartwatch",
                "exists": True,
                "ingestion": {
                    "last_run_id": last_run_id,
                    "last_seq": last_seq,
                    "last_message_id": None,
                    "last_ts": None,
                    "accepted_count": accepted_count,
                },
            }
            for device, (accepted_count, last_run_id, last_seq) in counts.items()
        },
    }


def _after_from(before: dict, lines: list[tuple], extra: dict[str, int] | None = None) -> dict:
    """The after snapshot the lines and the named cases imply: accepted
    lines advance accepted_count, this run's highest applied seq is the
    twin's last_seq under this run_id."""
    extra = extra or {}
    counts = {}
    for device, (count, last_run_id, last_seq) in before.items():
        accepted = [line for line in lines if line[1] == device and line[3] == "accepted"]
        applied_seqs = [line[2] for line in accepted] + [seq for dev, seq in extra.get("seqs", []) if dev == device]
        counts[device] = (
            count + len(accepted) + extra.get(device, 0),
            RID if applied_seqs else last_run_id,
            max(applied_seqs) if applied_seqs else last_seq,
        )
    return counts


def _manifest(**changes: Any) -> dict:
    """A manifest 1.4 as run.py writes it for a controller_restart run,
    reduced to the records the evaluator reads."""
    manifest: dict[str, Any] = {
        "manifest_version": "1.4",
        "run_id": RID,
        "condition_id": "controller_restart",
        "seed": 7,
        "validity": "valid",
        "validity_reasons": [],
        "restart": {
            "template": "bash proof_restart_controller.sh {run_id}",
            "requested_at_s": 150.0,
            "executed": True,
            "returncode": 0,
            "started_utc": _ts(150),
            "started_monotonic_ns": HOST_KILL_NS,
            "finished_utc": _ts(172),
            "stderr_tail": "guest before 2026-09-25T10:02:30Z after 2026-09-25T10:02:52Z",
        },
        "drain": {
            "hook": "drain",
            "flag": "--drain-cmd",
            "source": "hook",
            "outcome": "quiet",
            "verified": True,
            "returncode": 0,
        },
        "twin_snapshots": [
            {
                "hook": hook,
                "flag": "--twin-snapshot-cmd",
                "file": file,
                "source": "hook",
                "returncode": 0,
                "dest_exists": True,
                "verified": True,
                "problems": [],
            }
            for hook, file in TWIN_SNAPSHOT_FILES.items()
        ],
        "events_post_drain_fetch": {
            "template": "scp {dest}",
            "ok": True,
            "file": POST_DRAIN_EVENTS_FILENAME,
            "source": "hook",
            "verified": True,
            "problems": [],
            "attempts": [{"attempt": 1, "returncode": 0, "dest_exists": True}],
        },
        "sut_log_fetches": [
            {
                "hook": hook,
                "flag": SUT_LOG_FETCH_FLAGS[hook],
                "returncode": 0,
                "dest_exists": True,
                "dest_file": f"logs/sut/{name}",
            }
            for hook, name in SUT_LOG_FILES.items()
        ],
        "configuration_identity": dict(CONFIG_IDENTITY),
        "measured_window_utc": {"start": _ts(0), "end": _ts(300)},
        "measured_started_monotonic_ns": HOST_START_NS,
        "controller_marker": None,
    }
    manifest.update(changes)
    return manifest


def _session(*, reached: bool = False) -> dict:
    return {
        "values": {"DRAIN_QUIET_S": 130, "EGW_PROOF_ATTEMPT_LIMIT_S": 3000},
        "stop_rules": [
            {"rule": STOP_RULE_HEALTHY, "limit_s": 1200, "reached": False},
            {"rule": STOP_RULE_ATTEMPT, "limit_s": 3000, "reached": reached},
        ],
        "restoration": "stack=healthy restart_shown=yes",
        "restart_shown": True,
    }


def _artefacts(
    *,
    sent: list[tuple] | None = None,
    lines: list[tuple] | None = None,
    before: dict | None = None,
    after: dict | None = None,
    rows: list[dict[str, str]] | None = None,
    manifest: dict | None = None,
    controller_log: list[str] | None = None,
    integrity: str = "true",
    files_present: set[str] | None = None,
    extra_after: dict | None = None,
) -> pe.RunArtefacts:
    """The artefacts of the scenario in memory: the loader is exercised
    apart (test 33); every other case reads through this builder."""
    sent = SENT if sent is None else sent
    lines = LINES if lines is None else lines
    before = BEFORE if before is None else before
    after = _after_from(before, lines, extra_after) if after is None else after
    manifest = _manifest() if manifest is None else manifest
    return pe.RunArtefacts(
        run_dir=Path("in-memory") / RID,
        manifest=manifest,
        sent_events=[_sent(*item) for item in sent],
        events_timed=[_line(*item) for item in lines if item[4] is not None and item[4] < K_LOWER],
        events_post_drain=[_line(*item) for item in lines],
        twins_before=_twins("before", before)["devices"],
        twins_after=_twins("after", after)["devices"],
        metrics_rows=_rows() if rows is None else rows,
        metrics_header=list(CSV_HEADER),
        configuration_identity=dict(CONFIG_IDENTITY),
        controller_log=controller_log or [],
        broker_log=[],
        docker_events=[],
        drain_text="drained: queue_depth 0 and identical counters on 27 consecutive readings over 130 s\n",
        integrity=integrity,
        integrity_problems=[],
        sha256s={"manifest.json": "0" * 64},
        files_present=FULL_FILES if files_present is None else files_present,
        skipped_lines={},
        problems=[],
    )


def _evaluate(session: dict | None = None, **kwargs: Any) -> dict:
    return pe.evaluate(_artefacts(**kwargs), _session() if session is None else session)


def _outcome(doc: dict) -> dict:
    return doc["system_outcome"]


def _criterion(doc: dict, rule_id: str) -> dict:
    return doc["system_outcome"]["criteria"][rule_id]


def _a5_line(device: str, received_ns: int, *, prefix: str = "2026-09-25T10:03:10.000000000Z ", cause: str = "write-failed") -> str:
    """A controller log line as `docker logs --timestamps` prints it: the
    stamp, then the JSON object the controller's formatter writes."""
    return prefix + json.dumps(
        {
            "ts": "2026-09-25T10:03:10.001Z",
            "level": "ERROR",
            "logger": "egw_controller.mqtt",
            "message": pe.A5_MESSAGE,
            "context": {
                "cause": cause,
                "connection": 2,
                "identity": {
                    "topic": f"c2dt/egw-01/{device}/telemetry",
                    "mid": 7,
                    "qos": 1,
                    "dup": False,
                    "connection": 2,
                    "received_monotonic_ns": received_ns,
                },
                "occurrence": 1,
                "backoff_s": 1.0,
            },
        }
    )


def _write_run_dir(
    tmp_path: Path,
    *,
    name: str = RID,
    seal: bool = True,
    tamper: bool = False,
    controller_log: list[str] | None = None,
    **kwargs: Any,
) -> Path:
    """The scenario as a run directory on disk, sealed like the harness
    seals it (SHA256SUMS last, covering every file)."""
    artefacts = _artefacts(controller_log=controller_log, **kwargs)
    run_dir = tmp_path / "results" / "raw" / name
    sut = run_dir / "logs" / "sut"
    sut.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps(artefacts.manifest, indent=2, sort_keys=True) + "\n", "utf-8")
    for filename, records in (
        ("sent_events.jsonl", artefacts.sent_events),
        ("events.jsonl", artefacts.events_timed),
        (POST_DRAIN_EVENTS_FILENAME, artefacts.events_post_drain),
    ):
        (run_dir / filename).write_text("".join(json.dumps(r) + "\n" for r in records), "utf-8")
    for label, devices in (("before", artefacts.twins_before), ("after", artefacts.twins_after)):
        (run_dir / f"twins.{label}.json").write_text(
            json.dumps({"label": label, "seed": 7, "devices": devices}, indent=2) + "\n", "utf-8"
        )
    with (run_dir / "controller_metrics.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(artefacts.metrics_rows)
    (run_dir / "configuration_identity.json").write_text(json.dumps(CONFIG_IDENTITY, indent=2) + "\n", "utf-8")
    (sut / "broker.log").write_text("2026-09-25T10:00:00: New client connected\n", "utf-8")
    (sut / "controller.log").write_text("".join(line + "\n" for line in (controller_log or ["not json"])), "utf-8")
    (sut / "docker-events.log").write_text("2026-09-25T10:02:30 container kill\n", "utf-8")
    (sut / "hook-drain.stdout.txt").write_text(artefacts.drain_text or "", "utf-8")
    if seal:
        write_sha256sums(run_dir)
    if tamper:
        (run_dir / "sent_events.jsonl").write_text("{}\n", "utf-8")
    return run_dir


def _session_file(tmp_path: Path, **kwargs: Any) -> Path:
    path = tmp_path / "proof_session.json"
    path.write_text(json.dumps(_session(**kwargs), indent=2) + "\n", "utf-8")
    return path


def _main(run_dir: Path, out: Path, session: Path | None, *extra: str) -> int:
    argv = ["--run-dir", str(run_dir), "--out", str(out)]
    if session is not None:
        argv += ["--session", str(session)]
    return pe.main(argv + list(extra))


# ---------------------------------------------------------------------------
# 1. the rule texts
# ---------------------------------------------------------------------------


def test_every_rule_text_is_verbatim_in_the_adr() -> None:
    """Each constant is, whitespace aside, a substring of the ADR read now;
    the ADR wraps its lines, the constants do not."""
    adr = " ".join(pe.ADR_PATH.read_text(encoding="utf-8").split())
    for rule_id, text in pe.RULES.items():
        assert " ".join(text.split()) in adr, rule_id
    assert pe.rule_texts_not_in(pe.ADR_PATH) == []
    assert set(pe.RULES) >= {*pe.SUPPORT_RULE_IDS, *pe.REFUTATION_RULE_IDS, "inconclusive", "cannot_show"}
    # The check is not vacuous: a reworded rule is not found.
    assert " ".join("The kill found work: some other wording.".split()) not in adr


# ---------------------------------------------------------------------------
# 2-3. the readings
# ---------------------------------------------------------------------------


def test_metrics_rows_keep_file_order_and_read_empty_cells_as_none_never_zero() -> None:
    raw = [
        _row(_ts(2), P0, 3, None, monotonic_ns=1_002 * NS, unacked=None),
        _row(_ts(1), P0, None, 1, monotonic_ns=None, unacked=2),
        _row(_ts(3), "", 0, 0, monotonic_ns=1_003 * NS),
    ]
    rows, _notes = pe.read_metrics_rows(raw)
    assert [r.index for r in rows] == [0, 1, 2]
    assert [r.ts_utc for r in rows] == [_ts(2), _ts(1), _ts(3)]
    assert rows[0].in_progress is None and rows[0].unacked is None and rows[0].queue_depth == 3
    assert rows[1].queue_depth is None and rows[1].monotonic_ns is None and rows[1].unacked == 2
    assert rows[0].in_flight is None and rows[1].in_flight is None and rows[2].in_flight == 0
    assert rows[2].started_at is None
    assert rows[2].queue_depth == 0  # a written zero is a zero; an empty cell is not


def test_a_decreasing_ts_utc_row_is_reported_not_dropped() -> None:
    raw = [
        _row(_ts(10), P0, 3, 1, monotonic_ns=1_010 * NS),
        _row(_ts(8), P0, 3, 1, monotonic_ns=1_011 * NS),
        _row(_ts(12), P0, 3, 1, monotonic_ns=1_012 * NS),
    ]
    rows, notes = pe.read_metrics_rows(raw)
    assert len(rows) == 3
    assert len(notes) == 1 and "row 1" in notes[0] and "host clock step" in notes[0]
    assert "never dropped" in notes[0]


# ---------------------------------------------------------------------------
# 4-6. S1
# ---------------------------------------------------------------------------


def test_s1_reads_the_last_row_of_the_pre_kill_process() -> None:
    """A post-kill row stamped EARLIER on the host clock (a step) follows the
    last pre-kill row; started_at, not ts_utc, decides which reading S1 reads."""
    raw = [
        _row(_ts(100), P0, 3, 1, monotonic_ns=1_100 * NS),
        _row(_ts(150), P0, 2, 1, monotonic_ns=K_LOWER),
        _row(_ts(148), P1, 0, 0, monotonic_ns=K_UPPER),  # earlier ts_utc, later process
        _row(_ts(200), P1, 0, 0, monotonic_ns=K_UPPER + 20 * NS),
    ]
    rows, notes = pe.read_metrics_rows(raw)
    split = pe.split_by_process(rows)
    assert [r.index for r in split.pre_kill] == [0, 1] and [r.index for r in split.post_kill] == [2, 3]
    s1 = pe.s1_kill_found_work(split.pre_kill, _manifest()["restart"])
    assert s1.holds is True
    assert s1.evidence["last_reading"]["row"] == 1
    assert s1.evidence["last_reading"]["in_flight"] == 3
    assert s1.evidence["restart_started_utc"] == _ts(150)
    assert "P-1" in s1.identification_rules
    assert notes and "row 2" in notes[0]


def test_s1_fails_when_the_last_pre_kill_reading_shows_nothing_in_flight_and_the_proof_is_inconclusive() -> None:
    doc = _evaluate(rows=_rows(last_pre=(0, 0)))
    assert _criterion(doc, "S1")["holds"] is False
    assert _outcome(doc)["result"] == "inconclusive"
    assert any(r.startswith("the kill found nothing in flight (S1 fails)") for r in _outcome(doc)["inconclusive_reasons"])
    assert _outcome(doc)["refutations"] == []


def test_s1_is_unreadable_when_in_progress_is_an_empty_cell() -> None:
    doc = _evaluate(rows=_rows(last_pre=(3, None)))
    s1 = _criterion(doc, "S1")
    assert s1["holds"] is None
    assert "in_progress" in s1["reason"] and "never zero" in s1["reason"]
    assert _outcome(doc)["result"] == "inconclusive"
    assert any(r.startswith("S1 cannot be read") for r in _outcome(doc)["inconclusive_reasons"])


# ---------------------------------------------------------------------------
# 7-8. S6
# ---------------------------------------------------------------------------


def test_s6_holds_below_w_and_states_when_the_window_filled_and_from_which_reading() -> None:
    rows, _ = pe.read_metrics_rows(_rows())
    below = pe.s6_window(rows, 4999)
    assert below.holds is True and below.evidence["filled"] is False and below.evidence["filled_from"] is None
    assert below.evidence["max_queue_plus_in_progress"] == 4
    assert "stayed below W = 4999" in below.evidence["statement"]

    raw = _rows()
    raw[3] = _row(_ts(90), P0, 10, 2, monotonic_ns=1_090 * NS, unacked=12)
    raw[4] = _row(_ts(120), P0, 11, 1, monotonic_ns=1_120 * NS, unacked=12)
    rows, _ = pe.read_metrics_rows(raw)
    filled = pe.s6_window(rows, 12)
    assert filled.holds is True and filled.evidence["filled"] is True
    assert filled.evidence["filled_from"]["row"] == 3
    assert filled.evidence["filled_from"]["ts_utc"] == _ts(90)
    assert filled.evidence["filled_from"]["monotonic_ns"] == 1_090 * NS
    assert "filled from row 3" in filled.evidence["statement"]
    doc = _evaluate(rows=raw, manifest=_manifest(configuration_identity={**CONFIG_IDENTITY, "broker_conf_values": {**CONFIG_IDENTITY["broker_conf_values"], "max_inflight_messages": 12}}))
    assert _outcome(doc)["window"] == {"W": 12, "max_queue_plus_in_progress": 12, "filled": True, "filled_from": filled.evidence["filled_from"]}


def test_s6_cannot_be_stated_without_a_readable_row() -> None:
    raw = [_row(_ts(i), P0, None, None, monotonic_ns=(1_000 + i) * NS) for i in range(3)]
    rows, _ = pe.read_metrics_rows(raw)
    s6 = pe.s6_window(rows, 4999)
    assert s6.holds is None and "P-2" in s6.identification_rules
    doc = _evaluate(rows=raw)
    assert _outcome(doc)["result"] == "inconclusive"
    assert any(r.startswith("S6 cannot be stated (P-2)") for r in _outcome(doc)["inconclusive_reasons"])


# ---------------------------------------------------------------------------
# 9-10. the restart classes
# ---------------------------------------------------------------------------


def _classify(lines: list[tuple], sent: list[tuple] = SENT, rows: list[dict[str, str]] | None = None) -> pe.Classification:
    rows_typed, _ = pe.read_metrics_rows(_rows() if rows is None else rows)
    split = pe.split_by_process(rows_typed)
    manifest = _manifest()
    index = pe.lines_by_identity([_line(*item) for item in lines], RID)
    valid = pe.valid_identities([_sent(*item) for item in sent], RID).valid
    return pe.classify_identities(valid, index.by_id, pe.kill_band(split.pre_kill, split.post_kill), manifest["restart"], manifest, split.post_kill, [])


def test_restart_classes_are_split_on_the_controller_clock_band() -> None:
    E = ("e-mid", D3, 1, 405 * NS)
    lines = LINES + [("e-mid", D3, 1, "accepted", 1_160 * NS, None)]  # inside [K_LOWER, K_UPPER]
    classification = _classify(lines, SENT + [E])
    assert classification.pre_kill_lined == ["a-mid", "d-mid"]
    assert classification.restart_class == ["b-mid", "c-mid"]
    assert classification.ambiguous == ["e-mid"]
    assert classification.band["k_lower_monotonic_ns"] == K_LOWER
    assert classification.band["k_upper_monotonic_ns"] == K_UPPER
    # An identity without any line is restart-class; a line without a
    # received stamp is ambiguous.
    F = ("f-mid", D2, 1, 520 * NS)
    G = ("g-mid", D2, 2, 521 * NS)
    classification = _classify(LINES + [("g-mid", D2, 2, "accepted", None, None)], SENT + [F, G])
    assert "f-mid" in classification.restart_class and "g-mid" in classification.ambiguous
    # Without a band nothing lined can be placed: ambiguous, never support.
    no_band = [_row(_ts(0), P0, 3, 1, monotonic_ns=None)]
    classification = _classify(LINES, SENT, rows=no_band)
    assert classification.ambiguous == ["a-mid", "b-mid", "c-mid", "d-mid"]
    assert any("could not be placed" in note for note in classification.notes)


def test_published_while_away_is_a_report_figure_with_a_stated_band_and_never_decides() -> None:
    classification = _classify(LINES)
    assert classification.published_before_kill == ["a-mid", "b-mid", "d-mid"]
    assert classification.published_while_away == ["c-mid"]
    assert classification.published_after_resubscription == []
    assert classification.away_window["band_s"] == 3.0
    assert classification.away_window["resubscribed_row"]["row"] == 7
    assert "never" in classification.away_window["note"] and "decide" in classification.away_window["note"]
    # Moving C's publication to after the resubscription changes the report
    # figure and nothing of the criteria or the result.
    late = [A, B, ("c-mid", D2, 0, 700 * NS), D]
    early = _evaluate()
    moved = _evaluate(sent=late)
    assert _classify(LINES, late).published_after_resubscription == ["c-mid"]
    assert moved["system_outcome"]["criteria"] == early["system_outcome"]["criteria"]
    assert moved["system_outcome"]["result"] == early["system_outcome"]["result"] == "supports"
    report = moved["system_outcome"]["report"]["classification"]
    assert report["published_after_resubscription"] == 1 and report["published_while_away"] == 0


# ---------------------------------------------------------------------------
# 11-13. S2
# ---------------------------------------------------------------------------


def test_s2_needs_a_line_for_every_valid_identity_and_accepted_for_the_restart_classes() -> None:
    assert _criterion(_evaluate(), "S2")["holds"] is True
    without_line = [line for line in LINES if line[0] != "c-mid"]
    doc = _evaluate(lines=without_line)
    s2 = _criterion(doc, "S2")
    assert s2["holds"] is False and s2["evidence"]["without_outcome_line_ids"] == ["c-mid"]
    # A restart-class identity that ends without an accepted line and is not
    # a named N1 case: rejected, say (a valid message the controller refused).
    rejected = [line for line in LINES if line[0] != "b-mid"] + [("b-mid", D1, 1, "rejected", 1_200 * NS, None)]
    doc = _evaluate(lines=rejected)
    s2 = _criterion(doc, "S2")
    assert s2["holds"] is False
    assert s2["evidence"]["not_accepted_and_not_named_ids"][0]["message_id"] == "b-mid"
    assert _outcome(doc)["result"] == "inconclusive"
    assert any(r.startswith("does not support (E-3)") for r in _outcome(doc)["inconclusive_reasons"])
    # A pre-kill-lined identity accepted before the kill and redelivered as a
    # duplicate after it (N2) is not of the restart classes and holds.
    n2 = LINES + [("a-mid", D1, 0, "duplicate", 1_205 * NS, None)]
    doc = _evaluate(lines=n2)
    assert _criterion(doc, "S2")["holds"] is True and _criterion(doc, "S4")["holds"] is True
    assert _outcome(doc)["result"] == "supports"


def test_restart_class_failed_only_is_inconclusive_naming_each_lines_error() -> None:
    failed = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "failed", 1_200 * NS, "ditto 503"),
        ("b-mid", D1, 1, "failed", 1_260 * NS, "ditto timeout"),
    ]
    doc = _evaluate(lines=failed)
    assert _outcome(doc)["result"] == "inconclusive"
    assert _outcome(doc)["refutations"] == []
    named = _outcome(doc)["failed_only_restart_class"]
    assert named == [{"message_id": "b-mid", "device_uuid": D1, "seq": 1, "class": "restart_class", "errors": ["ditto 503", "ditto timeout"]}]
    reason = next(r for r in _outcome(doc)["inconclusive_reasons"] if r.startswith("when none of R1 to R4 holds"))
    assert "'ditto 503'" in reason and "'ditto timeout'" in reason
    assert _criterion(doc, "S2")["holds"] is False
    # The failed-only reading is given only when none of R1 to R4 holds: with
    # a refutation observed the run refutes and the reason is not listed.
    doc = _evaluate(lines=failed + [("c-mid", D2, 0, "accepted", 1_290 * NS, None)])
    assert _outcome(doc)["result"] == "refutes"
    assert not any(r.startswith("when none of R1 to R4 holds") for r in _outcome(doc)["inconclusive_reasons"])


def test_ambiguous_band_failed_only_is_not_read_as_support() -> None:
    E = ("e-mid", D3, 1, 405 * NS)
    lines = LINES + [("e-mid", D3, 1, "failed", 1_160 * NS, "ditto 503")]
    doc = _evaluate(sent=SENT + [E], lines=lines)
    assert _outcome(doc)["result"] == "inconclusive"
    assert _outcome(doc)["failed_only_restart_class"][0]["class"] == "ambiguous"
    assert _criterion(doc, "S2")["evidence"]["ambiguous"] == 1


# ---------------------------------------------------------------------------
# 14-15. S3/R2 and R1
# ---------------------------------------------------------------------------


def test_s3_and_r2_count_every_accepted_line_of_the_post_drain_copy_late_included() -> None:
    twice = LINES + [("b-mid", D1, 1, "accepted", 9_999 * NS, None)]  # far after any window
    doc = _evaluate(lines=twice)
    assert _criterion(doc, "S3")["holds"] is False
    assert _criterion(doc, "R2")["observed"] is True
    assert _criterion(doc, "R2")["evidence"]["identities"] == [{"message_id": "b-mid", "device_uuid": D1, "seq": 1, "accepted_lines": 2}]
    assert _outcome(doc)["result"] == "refutes"
    assert any(r.startswith("R2:") for r in _outcome(doc)["refutations"])


def test_r1_needs_a_completed_drain() -> None:
    missing = [line for line in LINES if line[0] != "c-mid"]
    gave_up = _manifest(drain={**_manifest()["drain"], "outcome": "gave-up", "returncode": 1})
    doc = _evaluate(lines=missing, manifest=gave_up)
    r1 = _criterion(doc, "R1")
    assert r1["observed"] is None and "no completed drain" in r1["reason"]
    assert _outcome(doc)["result"] == "inconclusive"
    assert any("reaches its limit" in r for r in _outcome(doc)["inconclusive_reasons"])
    assert _outcome(doc)["refutations"] == []
    doc = _evaluate(lines=missing)
    assert _criterion(doc, "R1")["observed"] is True
    assert _criterion(doc, "R1")["evidence"]["without_outcome_line_ids"] == ["c-mid"]
    assert _outcome(doc)["result"] == "refutes"


# ---------------------------------------------------------------------------
# 16-22. N1 cases, R3, S5, R4
# ---------------------------------------------------------------------------

B_DUPLICATE = [line for line in LINES if line[0] != "b-mid"] + [("b-mid", D1, 1, "duplicate", 1_200 * NS, None)]


def test_n1_case_from_the_kill_is_named_with_the_twin_surplus_and_last_seq() -> None:
    doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 1, "seqs": [(D1, 1)]})
    cases = _outcome(doc)["n1_cases"]
    assert len(cases) == 1
    case = cases[0]
    assert case["message_id"] == "b-mid" and case["source"] == "kill"
    assert case["twin_evidence"] == {"accepted_count_before": 5, "accepted_count_after": 7, "accepted_lines": 1, "surplus": 1, "last_seq": 1, "last_run_id": RID}
    assert case["source_evidence"]["restart_started_utc"] == _ts(150)
    assert "inference" in case["source_evidence"]
    assert _criterion(doc, "S4")["holds"] is True and _criterion(doc, "R3")["observed"] is False
    assert _criterion(doc, "S5")["holds"] is True and _criterion(doc, "R4")["observed"] is False
    assert _criterion(doc, "S2")["holds"] is True
    assert _outcome(doc)["result"] == "supports"
    # Without the twin's last_seq reaching the identity's seq the case is not
    # named (the surplus alone is not the evidence S4 requires).
    after = _after_from(BEFORE, B_DUPLICATE, {D1: 1, "seqs": [(D1, 1)]})
    after[D1] = (after[D1][0], RID, 0)
    doc = _evaluate(lines=B_DUPLICATE, after=after)
    assert _outcome(doc)["n1_cases"] == []
    assert _criterion(doc, "R3")["observed"] is True
    assert "last_seq 0 is below the identity's seq 1" in _criterion(doc, "R3")["evidence"]["not_named_identities"][0]["why_not_named"]


def test_n1_case_from_an_a3_connection_end_cites_the_controller_log_occurrence() -> None:
    lines = [line for line in LINES if line[0] != "c-mid"] + [("c-mid", D2, 0, "duplicate", 1_230 * NS, None)]
    log = ["not a json line", _a5_line(D2, 1_205 * NS)]
    doc = _evaluate(lines=lines, extra_after={D2: 1, "seqs": [(D2, 0)]}, controller_log=log)
    cases = _outcome(doc)["n1_cases"]
    assert len(cases) == 1 and cases[0]["message_id"] == "c-mid"
    assert cases[0]["source"] == "a3-connection-end"
    evidence = cases[0]["source_evidence"]
    assert evidence["controller_log_line"] == 2 and evidence["cause"] == "write-failed"
    assert evidence["identity"]["received_monotonic_ns"] == 1_205 * NS
    assert evidence["identity"]["topic"] == f"c2dt/egw-01/{D2}/telemetry"
    assert doc["instrumentation"]["controller_log_non_json_lines"] == 1
    assert _outcome(doc)["result"] == "supports"
    # An occurrence AFTER the redelivered line, or on another device, names
    # nothing; C was published while away, so the kill is not its source.
    doc = _evaluate(lines=lines, extra_after={D2: 1, "seqs": [(D2, 0)]}, controller_log=[_a5_line(D2, 1_240 * NS)])
    assert _outcome(doc)["n1_cases"] == [] and _criterion(doc, "R3")["observed"] is True
    doc = _evaluate(lines=lines, extra_after={D2: 1, "seqs": [(D2, 0)]}, controller_log=[_a5_line(D1, 1_205 * NS)])
    assert _outcome(doc)["n1_cases"] == [] and _outcome(doc)["result"] == "refutes"


def test_duplicate_only_without_surplus_is_r3() -> None:
    doc = _evaluate(lines=B_DUPLICATE)  # after = before + accepted lines: no surplus on D1
    assert _outcome(doc)["n1_cases"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is True
    assert r3["evidence"]["not_named_identities"][0]["message_id"] == "b-mid"
    assert "no surplus" in r3["evidence"]["not_named_identities"][0]["why_not_named"]
    assert _criterion(doc, "S4")["holds"] is False
    assert _outcome(doc)["result"] == "refutes"
    assert any(r.startswith("R3:") for r in _outcome(doc)["refutations"])


def test_more_duplicate_only_than_surplus_names_none_and_is_r3() -> None:
    F = ("f-mid", D1, 2, 401 * NS)
    lines = B_DUPLICATE + [("f-mid", D1, 2, "duplicate", 1_202 * NS, None)]
    doc = _evaluate(sent=SENT + [F], lines=lines, extra_after={D1: 1, "seqs": [(D1, 2)]})
    assert _outcome(doc)["n1_cases"] == []
    not_named = _criterion(doc, "R3")["evidence"]["not_named_identities"]
    assert [item["message_id"] for item in not_named] == ["b-mid", "f-mid"]
    assert all("cannot be told apart" in item["why_not_named"] for item in not_named)
    assert _outcome(doc)["result"] == "refutes"


def test_surplus_beyond_the_named_cases_is_r4() -> None:
    doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 2, "seqs": [(D1, 1)]})
    assert [case["message_id"] for case in _outcome(doc)["n1_cases"]] == ["b-mid"]
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True
    assert r4["evidence"]["mismatches"][0]["device_uuid"] == D1
    assert "advanced by 3 against 1 accepted line(s) and 1 named N1 case(s)" in r4["evidence"]["mismatches"][0]["problems"][0]
    assert _criterion(doc, "S5")["holds"] is False
    assert _criterion(doc, "R3")["observed"] is False
    assert _outcome(doc)["result"] == "refutes"


def test_s5_tolerates_exactly_one_per_named_case_and_nothing_else() -> None:
    # Two named on one device: B from the kill, F from an A3 connection end.
    F = ("f-mid", D1, 2, 515 * NS)  # published while away: never the kill's
    lines = B_DUPLICATE + [("f-mid", D1, 2, "duplicate", 1_240 * NS, None)]
    log = [_a5_line(D1, 1_215 * NS)]
    doc = _evaluate(sent=SENT + [F], lines=lines, extra_after={D1: 2, "seqs": [(D1, 1), (D1, 2)]}, controller_log=log)
    assert sorted(case["source"] for case in _outcome(doc)["n1_cases"]) == ["a3-connection-end", "kill"]
    s5 = _criterion(doc, "S5")
    assert s5["holds"] is True
    device = next(row for row in s5["evidence"]["devices"] if row["device_uuid"] == D1)
    assert device["delta"] == 3 and device["accepted_lines"] == 1 and device["named_n1_cases"] == 2
    assert device["expected_last_seq"] == 2 and device["ok"] is True
    assert _outcome(doc)["result"] == "supports"
    # Surplus 2 with one named: R4.
    doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 2, "seqs": [(D1, 1)]})
    assert _criterion(doc, "S5")["holds"] is False and _criterion(doc, "R4")["observed"] is True
    # A device with accepted lines absent from the before snapshot is a
    # mismatch, as `delta` reads it.
    before = {D1: BEFORE[D1], D2: BEFORE[D2]}
    doc = _evaluate(before=before, after=_after_from(before, LINES))
    problems = next(row for row in _criterion(doc, "S5")["evidence"]["devices"] if row["device_uuid"] == D3)["problems"]
    assert "absent from the before snapshot" in problems and _outcome(doc)["result"] == "refutes"


def test_r4_last_seq_regression_within_the_run_and_against_the_before_snapshot() -> None:
    after = _after_from(BEFORE, LINES)
    after[D1] = (after[D1][0], RID, 0)  # the run applied seq 1 on D1
    doc = _evaluate(after=after)
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True
    assert r4["evidence"]["last_seq_regressions"] == [{"device_uuid": D1, "regressed": "last_seq 0 is below the run's highest applied seq 1"}]
    assert _outcome(doc)["result"] == "refutes"
    before = {**BEFORE, D4: (5, "earlier", 9)}
    after = _after_from(before, LINES)
    after[D4] = (5, "earlier", 8)  # no line of this run on D4; the twin went back
    doc = _evaluate(before=before, after=after)
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True
    assert r4["evidence"]["last_seq_regressions"][0]["device_uuid"] == D4
    assert "below the before snapshot's 9" in r4["evidence"]["last_seq_regressions"][0]["regressed"]
    assert "P-5" in r4["identification_rules"]


# ---------------------------------------------------------------------------
# 23-27. inconclusive conditions, precedence, the harness verdict
# ---------------------------------------------------------------------------


def test_a_gave_up_drain_is_inconclusive_unless_r2_r3_or_r4_was_observed() -> None:
    gave_up = _manifest(drain={**_manifest()["drain"], "outcome": "gave-up", "returncode": 1})
    doc = _evaluate(manifest=gave_up)
    assert _outcome(doc)["result"] == "inconclusive"
    assert doc["instrumentation"]["proof_evidence"]["drain"]["outcome"] == "gave-up"
    assert doc["instrumentation"]["proof_evidence"]["complete"] is True
    twice = LINES + [("b-mid", D1, 1, "accepted", 1_300 * NS, None)]
    doc = _evaluate(manifest=gave_up, lines=twice)
    assert _outcome(doc)["result"] == "refutes"
    assert any("reaches its limit" in r for r in _outcome(doc)["inconclusive_reasons"])
    assert "P-7" in _criterion(doc, "R1")["identification_rules"]


def test_a_failed_sut_log_fetch_is_inconclusive() -> None:
    fetches = _manifest()["sut_log_fetches"]
    fetches[1] = {**fetches[1], "returncode": 1, "dest_exists": False}
    doc = _evaluate(manifest=_manifest(sut_log_fetches=fetches))
    evidence = doc["instrumentation"]["proof_evidence"]
    assert evidence["complete"] is False
    assert any("logs/sut/controller.log" in f and "exit 1" in f for f in evidence["fetch_failures"])
    assert _outcome(doc)["result"] == "inconclusive"
    assert any(r.startswith("any fetch listed above fails") for r in _outcome(doc)["inconclusive_reasons"])
    fetches[1] = {**fetches[1], "returncode": 0, "dest_exists": False}
    doc = _evaluate(manifest=_manifest(sut_log_fetches=fetches))
    assert any("wrote no file" in f for f in doc["instrumentation"]["proof_evidence"]["fetch_failures"])
    # A record missing altogether is missing evidence as well.
    doc = _evaluate(manifest=_manifest(sut_log_fetches=fetches[:2]))
    assert any("docker-events.log" in m for m in doc["instrumentation"]["proof_evidence"]["missing"])
    assert _outcome(doc)["result"] == "inconclusive"


def test_a_stop_rule_reached_in_the_session_facts_is_inconclusive() -> None:
    doc = _evaluate(session=_session(reached=True))
    assert _outcome(doc)["result"] == "inconclusive"
    reason = next(r for r in _outcome(doc)["inconclusive_reasons"] if r.startswith("a stop rule of the ceiling is reached"))
    assert STOP_RULE_ATTEMPT in reason and "limit 3000 s" in reason
    assert doc["session_facts"]["stop_rules_reached"][0]["rule"] == STOP_RULE_ATTEMPT
    assert doc["restoration"] == {"state": "stack=healthy restart_shown=yes", "note": "not computed here: the driver observes it"}


def test_missing_session_facts_leave_the_stop_rules_unknown_and_the_proof_inconclusive() -> None:
    doc = pe.evaluate(_artefacts(), None)
    assert _outcome(doc)["result"] == "inconclusive"
    assert any("(P-6)" in r and "no session facts" in r for r in _outcome(doc)["inconclusive_reasons"])
    assert doc["session_facts"]["present"] is False and doc["restoration"]["state"] is None
    doc = pe.evaluate(_artefacts(), {"restoration": "stack=healthy"})
    assert any("no readable stop_rules (P-6)" in r for r in _outcome(doc)["inconclusive_reasons"])


def test_harness_validity_is_recorded_verbatim_and_does_not_decide_the_proof() -> None:
    reasons = ["controller_metrics.csv: sample gap 12.0 s exceeds MAX_SAMPLE_GAP_S (5.0 s) after the restart"]
    doc = _evaluate(manifest=_manifest(validity="invalid", validity_reasons=reasons))
    assert doc["instrumentation"]["harness_validity"] == "invalid"
    assert doc["instrumentation"]["harness_validity_reasons"] == reasons
    assert _outcome(doc)["result"] == "supports"
    assert doc["instrumentation"]["proof_evidence"]["complete"] is True
    assert "kept as recorded" in doc["instrumentation"]["note"]
    assert "MAX_SAMPLE_GAP_S" in doc["cannot_show"]


# ---------------------------------------------------------------------------
# 28-32. the document and the CLI
# ---------------------------------------------------------------------------


def test_a_seal_that_fails_is_not_evaluated_exit_2(tmp_path, capsys) -> None:
    run_dir = _write_run_dir(tmp_path, tamper=True)
    out = tmp_path / "verdict.json"
    assert _main(run_dir, out, _session_file(tmp_path)) == 2
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["system_outcome"]["result"] == "not-evaluated"
    assert doc["instrumentation"]["seal"] == "false"
    assert any("sent_events.jsonl" in p for p in doc["instrumentation"]["seal_problems"])
    assert "SHA256SUMS does not verify" in doc["instrumentation"]["not_evaluated"]
    assert doc["system_outcome"]["criteria"] == {}
    assert "instrumentation" in doc and "restoration" in doc
    assert json.loads(capsys.readouterr().out) == doc
    # An unsealed directory is evaluated, and the missing seal is missing evidence.
    unsealed = _write_run_dir(tmp_path / "u", seal=False)
    out2 = tmp_path / "verdict2.json"
    assert _main(unsealed, out2, _session_file(tmp_path / "u")) == 3
    doc = json.loads(out2.read_text(encoding="utf-8"))
    assert doc["instrumentation"]["seal"] == "unsealed"
    assert any("never sealed" in f for f in doc["instrumentation"]["proof_evidence"]["fetch_failures"])


def test_supports_needs_all_six_no_refutation_and_no_inconclusive_condition() -> None:
    base = _evaluate()
    assert _outcome(base)["result"] == "supports"
    assert all(_criterion(base, rule)["holds"] is True for rule in pe.SUPPORT_RULE_IDS)
    assert all(_criterion(base, rule)["observed"] is False for rule in pe.REFUTATION_RULE_IDS)
    assert _outcome(base)["refutations"] == [] and _outcome(base)["inconclusive_reasons"] == []
    assert base["instrumentation"]["proof_evidence"]["complete"] is True
    assert _outcome(base)["report"]["by_class"]["restart_classes"] == {"identities": 2, "lines": 2, "accepted": 2, "duplicate": 0, "failed": 0, "rejected": 0, "none": 0}
    assert _outcome(base)["report"]["by_class"]["other_valid"]["identities"] == 2
    perturbed = {
        "S1": _evaluate(rows=_rows(last_pre=(0, 0))),
        "S2": _evaluate(lines=[line for line in LINES if line[0] != "c-mid"]),
        "S3": _evaluate(lines=LINES + [("b-mid", D1, 1, "accepted", 1_300 * NS, None)]),
        "S4": _evaluate(lines=B_DUPLICATE),
        "S5": _evaluate(after={**_after_from(BEFORE, LINES), D2: (9, RID, 0)}),
        "stop": _evaluate(session=_session(reached=True)),
        "evidence": _evaluate(integrity="unsealed"),
    }
    for name, doc in perturbed.items():
        assert _outcome(doc)["result"] != "supports", name
    assert _outcome(perturbed["S1"])["result"] == "inconclusive"
    assert _outcome(perturbed["S2"])["result"] == "refutes"  # R1 after a completed drain
    assert _outcome(perturbed["S5"])["result"] == "refutes"
    assert _outcome(perturbed["evidence"])["result"] == "inconclusive"
    # The support preamble is carried: a run that merely refutes nothing does
    # not support.
    assert _outcome(base)["rules"]["support"] == pe.RULES["support"]


def _strings(node: Any) -> set[str]:
    if isinstance(node, str):
        return {node}
    if isinstance(node, dict):
        return set().union(*(_strings(v) for v in node.values())) if node else set()
    if isinstance(node, list):
        return set().union(*(_strings(v) for v in node)) if node else set()
    return set()


def _keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node) | (set().union(*(_keys(v) for v in node.values())) if node else set())
    if isinstance(node, list):
        return set().union(*(_keys(v) for v in node)) if node else set()
    return set()


def test_the_verdict_document_has_three_separate_sections_and_every_rule_text() -> None:
    doc = json.loads(pe.render(_evaluate()))
    assert {"instrumentation", "system_outcome", "restoration"} <= set(doc)
    assert set(doc["instrumentation"]).isdisjoint({"result", "criteria"})
    assert set(doc["system_outcome"]).isdisjoint({"harness_validity", "seal", "proof_evidence"})
    assert doc["restoration"]["note"] == "not computed here: the driver observes it"
    assert doc["proof"] == pe.PROOF and doc["label"] == pe.LABEL and doc["evaluator_version"] == "1"
    strings = _strings(doc)
    for rule_id, text in pe.RULES.items():
        assert text in strings, rule_id
    for rule_id in (*pe.SUPPORT_RULE_IDS, *pe.REFUTATION_RULE_IDS):
        assert doc["system_outcome"]["criteria"][rule_id]["rule"] == pe.RULES[rule_id]
    # Every identification rule is labelled and carried.
    carried = doc["system_outcome"]["report"]["method"]["identification_rules"]
    assert carried == pe.IDENTIFICATION_RULES
    assert set(doc["system_outcome"]["criteria"]["S1"]["identification_rules"]) == {"P-1"}
    assert set(doc["system_outcome"]["criteria"]["S2"]["identification_rules"]) == {"P-3", "E-1"}
    assert set(doc["system_outcome"]["criteria"]["R4"]["identification_rules"]) == {"P-5", "E-2"}
    assert doc["cannot_show"] == pe.RULES["cannot_show"]
    assert doc["system_outcome"]["report"]["method"]["criteria_copy"] == POST_DRAIN_EVENTS_FILENAME
    assert doc["system_outcome"]["report"]["copies"]["events.jsonl"]["lines"] == 2
    assert doc["system_outcome"]["report"]["copies"][POST_DRAIN_EVENTS_FILENAME]["lines"] == 4


def test_the_verdict_is_byte_identical_on_repeat(tmp_path, capsys) -> None:
    run_dir = _write_run_dir(tmp_path, lines=B_DUPLICATE, extra_after={D1: 1, "seqs": [(D1, 1)]}, controller_log=[_a5_line(D2, 1_205 * NS)])
    session = _session_file(tmp_path)
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    assert _main(run_dir, first, session) == 0
    out_first = capsys.readouterr().out
    time.sleep(0.01)
    assert _main(run_dir, second, session) == 0
    out_second = capsys.readouterr().out
    assert first.read_bytes() == second.read_bytes()
    assert out_first == out_second == first.read_text(encoding="utf-8")
    assert b"\r" not in first.read_bytes()
    doc = json.loads(out_first)
    # No instant of the evaluation enters the document: every key that
    # names an instant is one the evidence carried.
    assert not {k for k in _keys(doc) if "generated" in k or "evaluated_utc" in k or "written" in k}
    assert set(doc["sources"]) >= {"manifest.json", "sent_events.jsonl", POST_DRAIN_EVENTS_FILENAME, "twins.before.json", "twins.after.json", "controller_metrics.csv", "logs/sut/controller.log", "SHA256SUMS"}
    assert all(len(v) == 64 for v in doc["sources"].values())


def test_cli_exit_codes_0_1_3_2(tmp_path, capsys) -> None:
    session = _session_file(tmp_path)
    supports = _write_run_dir(tmp_path / "s")
    assert _main(supports, tmp_path / "s.json", session) == 0
    assert "[proof] " in capsys.readouterr().err
    refutes = _write_run_dir(tmp_path / "r", lines=B_DUPLICATE)
    assert _main(refutes, tmp_path / "r.json", session) == 1
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["system_outcome"]["result"] == "refutes"
    inconclusive = _write_run_dir(tmp_path / "i", rows=_rows(last_pre=(0, 0)))
    assert _main(inconclusive, tmp_path / "i.json", session) == 3
    capsys.readouterr()
    # Not evaluated: an unreadable run directory, a write-once refusal, a
    # rule text that is not in the file handed as the ADR, a usage error.
    assert _main(tmp_path / "absent", tmp_path / "a.json", session) == 2
    assert "error:" in capsys.readouterr().err
    assert _main(supports, tmp_path / "s.json", session) == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    not_the_adr = tmp_path / "other.md"
    not_the_adr.write_text("# not the ADR\n", "utf-8")
    assert _main(supports, tmp_path / "s2.json", session, "--adr", str(not_the_adr)) == 2
    assert "not found verbatim in the ADR" in capsys.readouterr().err
    assert _main(supports, tmp_path / "s3.json", session, "--adr", str(pe.ADR_PATH)) == 0
    capsys.readouterr()
    with pytest.raises(SystemExit) as raised:
        pe.main(["--out", str(tmp_path / "u.json")])
    assert raised.value.code == 2
    assert _main(supports, tmp_path / "s4.json", None) == 3  # no session facts: P-6


# ---------------------------------------------------------------------------
# 33. the loader against a run directory the harness built
# ---------------------------------------------------------------------------

COPY_SCRIPT = """\
import shutil
import sys
from pathlib import Path
src, dest = sys.argv[1], sys.argv[2]
Path(dest).parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(src, dest)
"""

SNAPSHOT_SCRIPT = """\
import shutil
import sys
from pathlib import Path
run_id, dest, before, after = sys.argv[1:5]
src = before if Path(dest).name == "twins.before.json" else after
Path(dest).parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(src, dest)
"""


def test_end_to_end_over_a_harness_built_run_dir(tmp_path, plan_path, fast_run, monkeypatch, capsys) -> None:
    """The harness executes one controller_restart run with the fake
    simulator and the recorded item-18 hooks; the loader then reads the
    sealed 1.4 layout it wrote. Builder: _item18_run with the twin snapshot
    and post-drain hooks replaced by this module's copy scripts (the
    fixture's `write` mode carries neither identities nor a differing after
    snapshot), the sent lines rewritten by a wrapper of the fake simulator,
    and the controller /metrics poll stubbed in-process."""
    run_id = "controller_restart-r01"
    seed = _plan_seed(plan_path, run_id)
    devices = list(run_mod.expected_twin_devices(seed))
    marker = tmp_path / "restart-marker.txt"

    # The readings: the pre-kill process until the fake restart writes its
    # marker, the post-kill process afterwards, on a controller clock of
    # this test's own; polled every 20 ms so both processes have rows.
    class _FastSampler(run_mod.ControllerMetricsSampler):
        def __init__(self, csv_path, url, interval_s=1.0):
            super().__init__(csv_path, url, interval_s=0.02)

    ticks = itertools.count()

    def fake_fetch(url, timeout_s=5.0):
        i = next(ticks)
        killed = marker.is_file()
        return {
            "accepted": 3 + i, "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0,
            "queue_depth": 0 if killed else 5, "received": 3 + i,
            "in_progress": 0 if killed else 1, "processing_errors": 0,
            "unacked": 0 if killed else 6, "mqtt_connection": 2 if killed else 1,
            "mqtt_subscribed": True,
            "started_at": P1 if killed else P0,
            "wall_utc": _ts(i), "uptime_s": 1.0 + i,
            "monotonic_ns": (2_000 if killed else 1_000) * NS + i * 1_000_000,
        }

    monkeypatch.setattr(run_mod, "ControllerMetricsSampler", _FastSampler)
    monkeypatch.setattr(metrics_mod, "fetch_metrics", fake_fetch)
    original_poll = run_mod.poll_controller_marker
    monkeypatch.setattr(run_mod, "poll_controller_marker", lambda url, **kwargs: original_poll(None))

    # The identities: two per device, seq 0 lined before the kill, seq 1
    # after it; every one accepted.
    sent_lines = [
        _sent(f"{device[:8]}-{seq}", device, seq, 0, run_id=run_id) for device in devices for seq in (0, 1)
    ]
    post_lines = [
        _line(f"{device[:8]}-{seq}", device, seq, "accepted", (500 if seq == 0 else 3_000) * NS, run_id=run_id)
        for device in devices
        for seq in (0, 1)
    ]
    post_file = tmp_path / "post-drain.jsonl"
    post_file.write_text("".join(json.dumps(line) + "\n" for line in post_lines), "utf-8")
    before_devices = _snapshot_devices(seed)
    after_devices = json.loads(json.dumps(before_devices))
    for entry in after_devices.values():
        entry["ingestion"].update({"accepted_count": 5, "last_run_id": run_id, "last_seq": 1})
    before_file, after_file = tmp_path / "before.json", tmp_path / "after.json"
    before_file.write_text(json.dumps({"label": "before", "seed": seed, "devices": before_devices}), "utf-8")
    after_file.write_text(json.dumps({"label": "after", "seed": None, "devices": after_devices}), "utf-8")
    copy_script = tmp_path / "copy.py"
    copy_script.write_text(textwrap.dedent(COPY_SCRIPT), "utf-8")
    snapshot_script = tmp_path / "snapshot.py"
    snapshot_script.write_text(textwrap.dedent(SNAPSHOT_SCRIPT), "utf-8")

    def sim(cmd, log_path, timeout_s):
        stamp = time.monotonic_ns()  # before the restart fires
        fast_run.sleep_s = sim.sleep_s
        rc = fast_run(cmd, log_path, timeout_s)
        out_dir = Path(cmd[cmd.index("--output") + 1]) / cmd[cmd.index("--run-id") + 1]
        (out_dir / "sent_events.jsonl").write_text(
            "".join(json.dumps({**line, "publish_monotonic_ns": stamp + n}) + "\n" for n, line in enumerate(sent_lines)),
            "utf-8",
        )
        return rc

    sim.sleep_s = 0.0
    rc, run_dir, _record = _item18_run(
        tmp_path,
        plan_path,
        sim,
        monkeypatch,
        run_id=run_id,
        controller_url="http://127.0.0.1:8000",
        twin_snapshot_cmd=(
            f'"{PY}" "{snapshot_script.as_posix()}" {{run_id}} "{{dest}}" '
            f'"{before_file.as_posix()}" "{after_file.as_posix()}"'
        ),
        post_drain_fetch_cmd=f'"{PY}" "{copy_script.as_posix()}" "{post_file.as_posix()}" "{{dest}}"',
    )
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert rc == 0, manifest.get("validity_reasons")
    assert (run_dir / "SHA256SUMS").is_file()

    artefacts = pe.load_run_dir(run_dir)
    assert artefacts.integrity == "true"
    assert artefacts.metrics_header == CSV_HEADER
    rows, _notes = pe.read_metrics_rows(artefacts.metrics_rows)
    split = pe.split_by_process(rows)
    assert split.pre_kill and split.post_kill, (len(split.pre_kill), len(split.post_kill))
    assert split.pre_started_at == P0 and split.post_started_ats == [P1]
    assert len(artefacts.sent_events) == 6 and len(artefacts.events_post_drain) == 6
    assert artefacts.twins_before is not None and artefacts.twins_after is not None
    assert artefacts.controller_log is not None and artefacts.broker_log is not None
    assert artefacts.configuration_identity == CONFIG_IDENTITY
    assert artefacts.drain_text is not None and "drained: queue_depth 0" in artefacts.drain_text

    out = tmp_path / "proof_verdict.json"
    session = _session_file(tmp_path)
    capsys.readouterr()  # the harness's own [harness] lines
    code = _main(run_dir, out, session)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0, (doc["system_outcome"]["inconclusive_reasons"], doc["system_outcome"]["refutations"])
    assert doc["run_id"] == run_id
    assert doc["system_outcome"]["result"] == "supports"
    assert doc["instrumentation"]["harness_validity"] == manifest["validity"]
    assert doc["instrumentation"]["harness_validity_reasons"] == manifest["validity_reasons"]
    assert doc["instrumentation"]["seal"] == "true"
    assert doc["instrumentation"]["proof_evidence"]["complete"] is True
    assert doc["instrumentation"]["proof_evidence"]["drain"] == {"source": "hook", "outcome": "quiet", "verified": True}
    assert doc["instrumentation"]["drain_text_outcome"] == "quiet"
    assert doc["instrumentation"]["controller_log_non_json_lines"] == 1
    s1 = doc["system_outcome"]["criteria"]["S1"]
    assert s1["holds"] is True and s1["evidence"]["last_reading"]["in_flight"] == 6
    assert s1["evidence"]["last_reading"]["started_at"] == P0
    assert s1["evidence"]["restart_started_utc"] == manifest["restart"]["started_utc"]
    assert doc["system_outcome"]["criteria"]["S6"]["evidence"]["W"] == 4999
    report = doc["system_outcome"]["report"]
    assert report["by_class"]["restart_classes"]["identities"] == 3
    assert report["by_class"]["other_valid"]["identities"] == 3
    assert report["classification"]["published_before_kill"] == 6
    assert report["devices"]["expected_from_seed"] == run_mod.expected_twin_devices(seed)
    assert set(doc["sources"]) >= {"manifest.json", "controller_metrics.csv", "logs/sut/controller.log", "SHA256SUMS"}
    assert json.loads(capsys.readouterr().out) == doc
