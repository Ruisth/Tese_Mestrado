"""Tests for egw_experiments.proof_evaluator (ADR 0011, "The finite proof").

The evaluator applies S1-S6, R1-R4 and the inconclusive rule by identity to
the post-drain copy of the events and the twin snapshots of one proof
session, and writes one verdict document with three sections never merged.
These cases pin: every rule text to the ADR (read when the test runs, so a
later edit of the ADR is tested as it is); the readings in file order with
empty cells read as absent, never zero; each identification rule the design
flags (P-1 to P-7, E-1 to E-11) on a small in-memory scenario (three
devices, one kill on the controller clock, a host anchor for the report);
the precedence of an observed refutation, and that a refutation is never
recorded on evidence that was not read (E-7) nor on a duplicate line inside
the sampling band around the kill (E-8); the CLI's exit codes; the loader
against a run directory the harness itself built with the fixtures of
test_experiments_run (the fake simulator and the recorded item-18 hooks: no
broker, no docker, no network) under the proof's own diagnostic plan; in
the section after test 22, the branch review's findings, each with the
mutation it must catch; and, in the section after test 27, the Project
Manager's review of PR #47 (2026-09-25): the proof's eligibility (E-11: the
prescribed load, the publication completed, the population record whole,
the fault demonstrated, the harness copy and the collector file in the
inventory), the N1 sources' capacity across the run (E-10) and the drain
verified before R1.

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
)
from test_proof_plan import _write as _write_proof_plan

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
#: The host: the measured window starts at host monotonic 350 s, the
#: restart command (restart.started_monotonic_ns) at 500 s = 150 s later,
#: as the plan says; it returns 22 s later (finished_utc, as in r01/r02),
#: so its window on the host clock, with the 3 s band, ends at 525 s and
#: the kill lands inside it.
HOST_START_NS = 350 * NS
HOST_KILL_NS = 500 * NS
HOST_RESTART_END_NS = HOST_KILL_NS + 25 * NS
#: The four identities of the scenario: (message_id, device, seq,
#: publish_monotonic_ns on the host): A and D lined before the kill, B
#: published before it and lined only after, C published while away (after
#: the restart command's window, before the resubscription at 530 s).
A = ("a-mid", D1, 0, 360 * NS)
B = ("b-mid", D1, 1, 400 * NS)
C = ("c-mid", D2, 0, 528 * NS)
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
SIM_MANIFEST_REL = pe.simulator_manifest_rel(RID)
FULL_FILES = {
    "manifest.json",
    "sent_events.jsonl",
    "events.jsonl",
    POST_DRAIN_EVENTS_FILENAME,
    *TWIN_SNAPSHOT_FILES.values(),
    "controller_metrics.csv",
    "resources.csv",
    "configuration_identity.json",
    *(f"logs/sut/{name}" for name in SUT_LOG_FILES.values()),
    SIM_MANIFEST_REL,
    "SHA256SUMS",
}
#: The collector file as the SUT collector writes it (one row is enough
#: for the inventory: its content is the campaign's validity, not the
#: proof's).
RESOURCES_CSV = "ts_utc,container,cpu_pct,mem_bytes,mem_pct,host\n2026-09-25T10:00:00Z,egw-controller-1,1.0,1048576,0.1,egw\n"
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
        "scenario": "nominal",
        "seed": 7,
        "rate_msg_s": 11.2,
        "duration_s": 300,
        "warmup_s": 0,
        "cooldown_s": 0,
        "validity": "valid",
        "validity_reasons": [],
        "resource_source": "sut-collector",
        "simulator_returncode": 0,
        "events_source": "fetch-cmd: scp egw-tcg:/opt/egw/deployment/data/events/proof-adr0011-r01/events.jsonl events.jsonl",
        "events_fetch": {
            "template": "scp egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl \"{dest}\"",
            "command": "scp egw-tcg:/opt/egw/deployment/data/events/proof-adr0011-r01/events.jsonl events.jsonl",
            "attempts": [{"attempt": 1, "returncode": 0, "dest_exists": True}],
            "ok": True,
        },
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


def _session(*, reached: bool = False, restart_shown: bool | None = True) -> dict:
    return {
        "values": {"DRAIN_QUIET_S": 130, "EGW_PROOF_ATTEMPT_LIMIT_S": 3000},
        "stop_rules": [
            {"rule": STOP_RULE_HEALTHY, "limit_s": 1200, "reached": False},
            {"rule": STOP_RULE_ATTEMPT, "limit_s": 3000, "reached": reached},
        ],
        "restoration": "stack=healthy restart_shown=yes",
        "restart_shown": restart_shown,
    }


def _simulator_manifest(sent_count: int, *, run_id: str = RID, **changes: Any) -> dict:
    """The simulator's own manifest as egw_simulator.output writes it,
    reduced to what E-11 reads: the run, the load it was given, whether
    its schedule ran to the end and what it published."""
    manifest: dict[str, Any] = {
        "protocol_version": "1.0",
        "scenario": "nominal",
        "seed": 7,
        "run_id": run_id,
        "egw_id": "egw-01",
        "rates_hz": {"aggregate": 11.2, "per_device": {}},
        "duration_s": 300.0,
        "qos": 1,
        "completed": True,
        "totals": {"sent": sent_count, "intended_invalid": 0, "buffered_dropout": 0, "dropout_disconnects": 0},
    }
    manifest.update(changes)
    return manifest


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
    simulator_manifest: dict | None = None,
) -> pe.RunArtefacts:
    """The artefacts of the scenario in memory: the loader is exercised
    apart (test 33); every other case reads through this builder. The
    simulator's manifest declares what the sent list holds, unless one is
    given."""
    sent = SENT if sent is None else sent
    lines = LINES if lines is None else lines
    before = BEFORE if before is None else before
    after = _after_from(before, lines, extra_after) if after is None else after
    manifest = _manifest() if manifest is None else manifest
    if simulator_manifest is None:
        simulator_manifest = _simulator_manifest(len(sent), run_id=str(manifest.get("run_id") or RID))
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
        simulator_manifest=simulator_manifest,
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
    (run_dir / "resources.csv").write_text(RESOURCES_CSV, "utf-8")
    if artefacts.simulator_manifest is not None:
        sim_path = run_dir / pe.simulator_manifest_rel(str(artefacts.manifest.get("run_id") or name))
        sim_path.parent.mkdir(parents=True, exist_ok=True)
        sim_path.write_text(json.dumps(artefacts.simulator_manifest, indent=2) + "\n", "utf-8")
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


def test_s6_cannot_be_stated_without_w_and_p2_says_so() -> None:
    """W unknown (max_inflight_messages not a positive integer) is the other
    reading S6 cannot make; the P-2 text the document carries covers it."""
    identity = {**CONFIG_IDENTITY, "broker_conf_values": {**CONFIG_IDENTITY["broker_conf_values"], "max_inflight_messages": 0}}
    doc = _evaluate(manifest=_manifest(configuration_identity=identity))
    s6 = _criterion(doc, "S6")
    assert s6["holds"] is None and "W" in s6["reason"] and set(s6["identification_rules"]) == {"P-2"}
    assert "max_inflight_messages" in pe.IDENTIFICATION_RULES["P-2"] and "W" in pe.IDENTIFICATION_RULES["P-2"]
    assert _outcome(doc)["result"] == "inconclusive"
    assert any(r.startswith("S6 cannot be stated (P-2)") for r in _outcome(doc)["inconclusive_reasons"])
    assert any("(W) is not a positive integer" in f for f in doc["instrumentation"]["proof_evidence"]["fetch_failures"])


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


def _without_post_drain_copy(**changes: Any) -> pe.RunArtefacts:
    """The scenario with the post-drain copy absent from the run directory."""
    artefacts = _artefacts(**changes)
    artefacts.events_post_drain = None
    artefacts.files_present = FULL_FILES - {POST_DRAIN_EVENTS_FILENAME}
    return artefacts


def _assert_nothing_shown_by_identity(doc: dict, problem: str) -> None:
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
    for rule_id in ("S2", "S3", "S4", "S5"):
        assert _criterion(doc, rule_id)["holds"] is None, rule_id
        assert "E-7" in _criterion(doc, rule_id)["identification_rules"], rule_id
    for rule_id in pe.REFUTATION_RULE_IDS:
        assert _criterion(doc, rule_id)["observed"] is None, rule_id
    assert _criterion(doc, "S1")["holds"] is True and _criterion(doc, "S6")["holds"] is True
    assert any(r.startswith("any fetch listed above fails") and problem in r for r in outcome["inconclusive_reasons"])
    assert any(r.startswith("S2, S3, S4, S5 cannot be shown (E-7)") and problem in r for r in outcome["inconclusive_reasons"])
    assert doc["instrumentation"]["proof_evidence"]["complete"] is False
    assert POST_DRAIN_EVENTS_FILENAME in doc["instrumentation"]["proof_evidence"]["cannot_serve_the_criteria"]
    assert outcome["report"]["method"]["criteria_copy_usable"] is False
    assert outcome["n1_cases"] == [] and outcome["failed_only_restart_class"] == []


def test_a_post_drain_copy_not_fetched_or_not_verified_is_never_a_refutation() -> None:
    """The ADR lists a failed fetch under Inconclusive and a refutation is
    'never re-run away', so R1 (every identity without a line) and R4 (a
    delta against zero accepted lines) must not be observed on a copy that
    was not read: after a quiet drain with every other evidence complete,
    the run is inconclusive and S2 to S5, R1 to R4 are null (E-7)."""
    failed_fetch = _manifest(events_post_drain_fetch={
        "template": "scp {dest}", "ok": False, "file": POST_DRAIN_EVENTS_FILENAME, "source": "hook",
        "verified": False, "problems": [], "attempts": [{"attempt": 1, "returncode": 1, "dest_exists": False}],
    })
    doc = pe.evaluate(_without_post_drain_copy(manifest=failed_fetch), _session())
    _assert_nothing_shown_by_identity(doc, "the post-drain fetch failed after 1 attempt(s)")
    assert doc["instrumentation"]["proof_evidence"]["drain"]["outcome"] == "quiet"
    # Recorded as verified but absent from the directory: the same.
    doc = pe.evaluate(_without_post_drain_copy(), _session())
    _assert_nothing_shown_by_identity(doc, "recorded as verified but absent")
    # Fetched, present and readable, but not verified as this run's copy:
    # its lines are not the criteria's evidence either.
    unverified = _manifest(events_post_drain_fetch={
        **_manifest()["events_post_drain_fetch"], "verified": False, "problems": ["run_id of line 3 is 'other'"],
    })
    doc = _evaluate(manifest=unverified, lines=B_DUPLICATE)
    _assert_nothing_shown_by_identity(doc, "not the post-drain copy of this run: run_id of line 3 is 'other'")
    # A refutation observed on evidence that WAS read still stands: none
    # depends on the post-drain copy, so nothing refutes here, while with the
    # copy read the same lines refute (R3).
    assert _outcome(_evaluate(lines=B_DUPLICATE))["result"] == "refutes"


def test_an_unsealed_directory_without_its_post_drain_copy_exits_3_not_1(tmp_path, capsys) -> None:
    run_dir = _write_run_dir(tmp_path, seal=False)
    (run_dir / POST_DRAIN_EVENTS_FILENAME).unlink()
    out = tmp_path / "verdict.json"
    assert _main(run_dir, out, _session_file(tmp_path)) == 3
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["system_outcome"]["result"] == "inconclusive" and doc["system_outcome"]["refutations"] == []
    assert doc["system_outcome"]["criteria"]["R1"]["observed"] is None
    assert doc["system_outcome"]["criteria"]["R4"]["observed"] is None
    assert any("recorded as verified but absent" in m for m in doc["instrumentation"]["proof_evidence"]["missing"])
    assert "refutations: " not in capsys.readouterr().err


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


def test_duplicate_only_without_twin_evidence_cannot_be_shown_and_is_not_r3() -> None:
    """R3 reads 'without the surplus the identity was not applied': a surplus
    of zero, not a surplus unknown. With the after snapshot's hook failed
    (no file, not verified) the candidate is neither named nor R3, S4 and
    R3 are null like S5 and R4, and the failed fetch leaves the run
    inconclusive (E-7) instead of refuted."""
    snapshots = _manifest()["twin_snapshots"]
    snapshots[1] = {**snapshots[1], "returncode": 1, "dest_exists": False, "verified": False}
    artefacts = _artefacts(lines=B_DUPLICATE, manifest=_manifest(twin_snapshots=snapshots))
    artefacts.twins_after = None
    artefacts.files_present = FULL_FILES - {TWIN_SNAPSHOT_FILES["twin_snapshot_after"]}
    doc = pe.evaluate(artefacts, _session())
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    for rule_id in ("S4", "S5"):
        assert _criterion(doc, rule_id)["holds"] is None, rule_id
    for rule_id in ("R3", "R4"):
        assert _criterion(doc, rule_id)["observed"] is None, rule_id
    r3 = _criterion(doc, "R3")
    assert r3["evidence"]["not_named_identities"] == []
    assert [c["message_id"] for c in r3["evidence"]["cannot_show_identities"]] == ["b-mid"]
    assert "twins.after.json: the twin snapshot is not verified (exit 1)" in r3["evidence"]["cannot_show_identities"][0]["why_not_shown"]
    assert "E-7" in r3["identification_rules"]
    reasons = _outcome(doc)["inconclusive_reasons"]
    assert any(r.startswith("any fetch listed above fails") and "twins.after.json" in r for r in reasons)
    assert any(r.startswith("S4 cannot be shown (E-7)") for r in reasons)
    assert any(r.startswith("S5 cannot be shown (E-7)") for r in reasons)
    assert _outcome(doc)["n1_cases"] == []
    # A candidate on a device neither (present, verified) snapshot names is
    # not shown either; an R3 observed on a device with evidence still
    # stands beside it.
    H = ("h-mid", D4, 0, 400 * NS)
    lines = LINES + [("h-mid", D4, 0, "duplicate", 1_230 * NS, None)]
    doc = _evaluate(sent=SENT + [H], lines=lines)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert _criterion(doc, "S4")["holds"] is None and _criterion(doc, "R3")["observed"] is None
    assert "neither snapshot names it" in _criterion(doc, "R3")["evidence"]["cannot_show_identities"][0]["why_not_shown"]
    doc = _evaluate(sent=SENT + [H], lines=[line for line in lines if line[0] != "b-mid"] + [("b-mid", D1, 1, "duplicate", 1_200 * NS, None)])
    assert _outcome(doc)["result"] == "refutes" and _criterion(doc, "R3")["observed"] is True
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["not_named_identities"]] == ["b-mid"]
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]] == ["h-mid"]


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
    F = ("f-mid", D1, 2, 528 * NS)  # published while away: never the kill's
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


def test_a_device_only_the_after_snapshot_names_without_an_accepted_line_is_not_compared() -> None:
    """The runbook's `delta` flags absence from the before snapshot only for
    a device with accepted records and loops over the before snapshot's
    devices, so a device that only the after snapshot names, with no line,
    is reported and not compared: no mismatch, no R4."""
    after = {**_after_from(BEFORE, LINES), D4: (3, "earlier", 2)}
    doc = _evaluate(after=after)
    assert _outcome(doc)["result"] == "supports"
    row = next(row for row in _criterion(doc, "S5")["evidence"]["devices"] if row["device_uuid"] == D4)
    assert row["compared"] is False and row["ok"] is True and row["problems"] == [] and "not compared" in row["note"]
    assert _criterion(doc, "R4")["observed"] is False and _criterion(doc, "R4")["evidence"]["mismatches"] == []
    compared = next(row for row in _criterion(doc, "S5")["evidence"]["devices"] if row["device_uuid"] == D1)
    assert compared["compared"] is True and "note" not in compared
    # A device of the before snapshot absent from the after one stays a
    # mismatch, as `delta` prints it.
    doc = _evaluate(after={k: v for k, v in _after_from(BEFORE, LINES).items() if k != D2})
    assert _outcome(doc)["result"] == "refutes"
    assert _criterion(doc, "R4")["evidence"]["mismatches"] == [{"device_uuid": D2, "problems": ["absent from the after snapshot"]}]


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
# 22a-22i. the branch review's findings: E-8, E-7 over the controller log and
# an unverified twin, S5's equality, E-4, P-4's record, P-1's file order
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "received", [K_UPPER, (K_LOWER + K_UPPER) // 2, K_LOWER], ids=["upper-bound", "inside", "lower-bound"]
)
def test_a_duplicate_only_line_in_the_sampling_band_cannot_be_shown_and_never_refutes(received: int) -> None:
    """E-8: the identity and twin evidence of test 16 (B in progress at the
    kill, surplus 1, last_seq 1), with its redelivered duplicate line
    written at or inside the controller-clock band between the last
    pre-kill and the first post-kill reading, where the 1 Hz poll cannot
    place the kill. Whether it was in progress at the kill cannot be shown
    from such a reading, so it is neither named nor R3, its device is
    undecided for S5/R4 and the run is inconclusive, never refuted; one
    nanosecond above the band the same evidence names the case (test 16)."""
    lines = [line for line in LINES if line[0] != "b-mid"] + [("b-mid", D1, 1, "duplicate", received, None)]
    twin = {D1: 1, "seqs": [(D1, 1)]}
    doc = _evaluate(lines=lines, extra_after=twin)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
    assert outcome["n1_cases"] == []
    for rule_id in ("S4", "S5"):
        assert _criterion(doc, rule_id)["holds"] is None, rule_id
    for rule_id in ("R3", "R4"):
        assert _criterion(doc, rule_id)["observed"] is None, rule_id
    r3 = _criterion(doc, "R3")
    assert r3["evidence"]["not_named_identities"] == []
    shown = r3["evidence"]["cannot_show_identities"]
    assert [c["message_id"] for c in shown] == ["b-mid"] and shown[0]["class"] == "ambiguous"
    why = shown[0]["why_not_shown"]
    assert "cannot be shown" in why and "(E-8)" in why and "the restart class" not in why
    assert str(K_LOWER) in why and str(K_UPPER) in why and str(received) in why
    assert "E-8" in r3["identification_rules"]
    r4 = _criterion(doc, "R4")
    assert "E-8" in r4["identification_rules"]
    assert r4["evidence"]["mismatches"] == [] and r4["evidence"]["surplus_unexplained"] == []
    assert r4["evidence"]["undecided"] == [{"device_uuid": D1, "rule": "E-8", "why": why, "message_ids": ["b-mid"]}]
    row = next(row for row in r4["evidence"]["devices"] if row["device_uuid"] == D1)
    assert row["ok"] is None and row["undecided"]["rule"] == "E-8" and row["surplus"] == 1
    reasons = outcome["inconclusive_reasons"]
    assert any(r.startswith("S4 cannot be shown (E-8)") and str(K_LOWER) in r and str(K_UPPER) in r for r in reasons)
    assert any(r.startswith("S5 cannot be shown (E-8)") and D1 in r for r in reasons)
    assert outcome["report"]["classification"]["ambiguous"] == 1
    assert "sampling band" in pe.IDENTIFICATION_RULES["E-8"] and "never refuted" in pe.IDENTIFICATION_RULES["E-8"]
    assert "E-8" in pe.IDENTIFICATION_RULES["P-3"] and "E-8" in pe.IDENTIFICATION_RULES["P-4"]
    # One nanosecond above the band: named from the kill, the run supports.
    above = [line for line in LINES if line[0] != "b-mid"] + [("b-mid", D1, 1, "duplicate", K_UPPER + 1, None)]
    doc = _evaluate(lines=above, extra_after=twin)
    assert _outcome(doc)["result"] == "supports"
    assert [(c["message_id"], c["source"]) for c in _outcome(doc)["n1_cases"]] == [("b-mid", "kill")]
    # Without a band (no readable monotonic_ns on both sides) the same
    # candidate cannot be placed either: E-8, not R3.
    no_band = [_row(_ts(0), P0, 3, 1, monotonic_ns=None)]
    doc = _evaluate(lines=B_DUPLICATE, extra_after=twin, rows=no_band)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    shown = _criterion(doc, "R3")["evidence"]["cannot_show_identities"]
    assert [c["message_id"] for c in shown] == ["b-mid"] and "could not be placed" in shown[0]["why_not_shown"]
    # A duplicate line the pre-kill process wrote (below the band) is not in
    # progress at the kill and, with no A3 occurrence, is R3 as before.
    below = [line for line in LINES if line[0] != "b-mid"] + [("b-mid", D1, 1, "duplicate", K_LOWER - NS, None)]
    doc = _evaluate(lines=below, extra_after=twin)
    assert _outcome(doc)["result"] == "refutes" and _criterion(doc, "R3")["observed"] is True
    not_named = _criterion(doc, "R3")["evidence"]["not_named_identities"]
    assert not_named[0]["class"] == "pre_kill_lined"
    assert "lined before the kill on the controller clock" in not_named[0]["why_not_named"]


def test_a_controller_log_that_cannot_serve_the_criteria_leaves_an_a3_source_unshown_never_r3() -> None:
    """E-7 over the controller log (the ADR's item 6, fetched 'so that an
    N1 case caused by an A3 connection end is named and not read as R3'):
    with the fetch recorded failed, recorded but the file absent, or the
    file unreadable, an A3 connection end can be shown neither way, so a
    duplicate-only identity not named with the kill as its source is
    neither named nor R3, its device is undecided for S5/R4 and the run is
    inconclusive with the failed fetch named; with the log read and an A5
    occurrence the same identity is a named case (test 17). The kill still
    names its one case on the record, and a candidate the twin shows
    unapplied stays R3 on the twin's evidence, which was read."""
    lines = [line for line in LINES if line[0] != "c-mid"] + [("c-mid", D2, 0, "duplicate", 1_230 * NS, None)]
    twin = {D2: 1, "seqs": [(D2, 0)]}
    log_rel = f"logs/sut/{SUT_LOG_FILES['controller_log']}"
    fetches = _manifest()["sut_log_fetches"]
    fetches[1] = {**fetches[1], "returncode": 1, "dest_exists": False}
    failed_fetch = _manifest(sut_log_fetches=fetches)

    def _unshown(doc: dict, problem: str) -> None:
        outcome = _outcome(doc)
        assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
        assert outcome["n1_cases"] == []
        for rule_id in ("S4", "S5"):
            assert _criterion(doc, rule_id)["holds"] is None, rule_id
        for rule_id in ("R3", "R4"):
            assert _criterion(doc, rule_id)["observed"] is None, rule_id
        r3 = _criterion(doc, "R3")
        assert r3["evidence"]["not_named_identities"] == []
        shown = r3["evidence"]["cannot_show_identities"]
        assert [c["message_id"] for c in shown] == ["c-mid"]
        why = shown[0]["why_not_shown"]
        assert problem in why and "(E-7)" in why and "neither way" in why
        r4 = _criterion(doc, "R4")
        assert r4["evidence"]["undecided"] == [{"device_uuid": D2, "rule": "E-7", "why": why, "message_ids": ["c-mid"]}]
        assert r4["evidence"]["mismatches"] == [] and "E-7" in r4["identification_rules"]
        reasons = outcome["inconclusive_reasons"]
        assert any(r.startswith("any fetch listed above fails") and problem in r for r in reasons)
        assert any(r.startswith("S4 cannot be shown (E-7)") and problem in r for r in reasons)
        assert any(r.startswith("S5 cannot be shown (E-7)") and problem in r for r in reasons)
        assert doc["instrumentation"]["proof_evidence"]["cannot_serve_the_criteria"][log_rel] == problem
        assert outcome["report"]["method"]["controller_log_usable"] is False
        assert outcome["report"]["method"]["controller_log_problem"] == problem

    # The fetch recorded failed: exit 1, no file.
    artefacts = _artefacts(lines=lines, extra_after=twin, manifest=failed_fetch)
    artefacts.controller_log = None
    artefacts.files_present = FULL_FILES - {log_rel}
    _unshown(pe.evaluate(artefacts, _session()), f"{log_rel}: the fetch {SUT_LOG_FETCH_FLAGS['controller_log']} exit 1 and wrote no file")
    # The fetch recorded failed although it wrote a file, and the file holds
    # an A5 line that would name the case: a record the harness refused
    # serves no criterion, so the occurrence is not read.
    wrote = _manifest()["sut_log_fetches"]
    wrote[1] = {**wrote[1], "returncode": 1, "dest_exists": True}
    doc = _evaluate(lines=lines, extra_after=twin, manifest=_manifest(sut_log_fetches=wrote), controller_log=[_a5_line(D2, 1_205 * NS)])
    _unshown(doc, f"{log_rel}: the fetch {SUT_LOG_FETCH_FLAGS['controller_log']} exit 1 and wrote its file")
    assert _outcome(doc)["report"]["a5_occurrences"][0]["device_uuid"] == D2  # reported, never read for a criterion
    # Recorded as fetched, but the file is absent from the run directory.
    artefacts = _artefacts(lines=lines, extra_after=twin)
    artefacts.controller_log = None
    artefacts.files_present = FULL_FILES - {log_rel}
    _unshown(pe.evaluate(artefacts, _session()), f"{log_rel}: recorded as fetched but absent from the run directory")
    # Present but unreadable: the loader's problem is the failed fetch.
    artefacts = _artefacts(lines=lines, extra_after=twin)
    artefacts.controller_log = None
    artefacts.problems = [f"{log_rel} unreadable: [Errno 5] Input/output error"]
    _unshown(pe.evaluate(artefacts, _session()), f"{log_rel} unreadable: [Errno 5] Input/output error")
    # The log read: an A5 occurrence before the redelivery names the case.
    doc = _evaluate(lines=lines, extra_after=twin, controller_log=[_a5_line(D2, 1_205 * NS)])
    assert _outcome(doc)["result"] == "supports"
    assert [(c["message_id"], c["source"]) for c in _outcome(doc)["n1_cases"]] == [("c-mid", "a3-connection-end")]
    assert _outcome(doc)["report"]["method"] ["controller_log_usable"] is True
    # The log read and no occurrence: R3, as test 17 states.
    doc = _evaluate(lines=lines, extra_after=twin)
    assert _outcome(doc)["result"] == "refutes" and _criterion(doc, "R3")["observed"] is True
    # With the log unread the kill still names its one case on the record
    # (the run stays inconclusive for the failed fetch) ...
    artefacts = _artefacts(lines=B_DUPLICATE, extra_after={D1: 1, "seqs": [(D1, 1)]}, manifest=failed_fetch)
    artefacts.controller_log = None
    artefacts.files_present = FULL_FILES - {log_rel}
    doc = pe.evaluate(artefacts, _session())
    assert [(c["message_id"], c["source"]) for c in _outcome(doc)["n1_cases"]] == [("b-mid", "kill")]
    assert _criterion(doc, "S4")["holds"] is True and _criterion(doc, "S5")["holds"] is True
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    # ... two claimants of the kill are then unshown, not R3 (one may be an
    # A3 case the unread log would have named) ...
    G = ("g-mid", D3, 1, 380 * NS)
    artefacts = _artefacts(
        sent=SENT + [G],
        lines=B_DUPLICATE + [("g-mid", D3, 1, "duplicate", 1_210 * NS, None)],
        extra_after={D1: 1, D3: 1, "seqs": [(D1, 1), (D3, 1)]},
        manifest=failed_fetch,
    )
    artefacts.controller_log = None
    artefacts.files_present = FULL_FILES - {log_rel}
    doc = pe.evaluate(artefacts, _session())
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert _criterion(doc, "R3")["evidence"]["not_named_identities"] == []
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]] == ["b-mid", "g-mid"]
    assert all("at most one N1 case per death" in c["why_not_shown"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"])
    # ... and a candidate the twin shows unapplied (no surplus on D2) stays
    # R3 on the twin's evidence, which was read: the run refutes.
    artefacts = _artefacts(lines=lines, manifest=failed_fetch)
    artefacts.controller_log = None
    artefacts.files_present = FULL_FILES - {log_rel}
    doc = pe.evaluate(artefacts, _session())
    assert _outcome(doc)["result"] == "refutes" and _criterion(doc, "R3")["observed"] is True
    assert "no surplus" in _criterion(doc, "R3")["evidence"]["not_named_identities"][0]["why_not_named"]
    assert "controller log" in pe.IDENTIFICATION_RULES["E-7"] and "item 6" in pe.IDENTIFICATION_RULES["E-7"]


def test_a_twin_snapshot_present_and_readable_but_not_verified_serves_no_criterion() -> None:
    """E-7's clause for a snapshot the harness refused: the after snapshot's
    hook wrote a file the loader reads, but the record says verified=false
    (exit 0 with problems). Its figures serve no criterion: S5/R4 are null,
    a duplicate-only candidate is neither named nor R3, the run is
    inconclusive with the failure named. The guard on twins_problem in
    evaluate() is what keeps the file out: without it B, with no surplus in
    the unverified file, would be R3 and the run refuted."""
    snapshots = _manifest()["twin_snapshots"]
    snapshots[1] = {**snapshots[1], "verified": False, "problems": ["device set differs from the before snapshot's"]}
    unverified = _manifest(twin_snapshots=snapshots)
    problem = "twins.after.json: the twin snapshot is not verified (exit 0): device set differs from the before snapshot's"
    doc = _evaluate(lines=B_DUPLICATE, manifest=unverified)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
    for rule_id in ("S4", "S5"):
        assert _criterion(doc, rule_id)["holds"] is None, rule_id
    for rule_id in ("R3", "R4"):
        assert _criterion(doc, rule_id)["observed"] is None, rule_id
    r3 = _criterion(doc, "R3")
    assert r3["evidence"]["not_named_identities"] == []
    assert [c["message_id"] for c in r3["evidence"]["cannot_show_identities"]] == ["b-mid"]
    assert problem in r3["evidence"]["cannot_show_identities"][0]["why_not_shown"]
    assert _criterion(doc, "S5")["reason"] == f"the twin evidence cannot serve the criteria: {problem}"
    assert _criterion(doc, "S5")["evidence"]["devices"] == []
    assert outcome["report"]["method"]["twin_evidence_problem"] == problem
    assert outcome["report"]["devices"]["surplus"] == []
    assert doc["instrumentation"]["proof_evidence"]["cannot_serve_the_criteria"]["twins.after.json"] == problem
    assert doc["instrumentation"]["proof_evidence"]["present"]["twins.after.json"] is True
    reasons = outcome["inconclusive_reasons"]
    assert any(r.startswith("any fetch listed above fails") and problem in r for r in reasons)
    assert any(r.startswith("S4 cannot be shown (E-7)") and problem in r for r in reasons)
    assert any(r.startswith("S5 cannot be shown (E-7)") and problem in r for r in reasons)
    # With every line accepted the unverified file leaves S5/R4 null too:
    # never 'holds' on a refused snapshot.
    doc = _evaluate(manifest=unverified)
    assert _criterion(doc, "S5")["holds"] is None and _criterion(doc, "R4")["observed"] is None
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    # The before snapshot refused: the same.
    snapshots = _manifest()["twin_snapshots"]
    snapshots[0] = {**snapshots[0], "verified": False, "problems": ["seed mismatch"]}
    doc = _evaluate(lines=B_DUPLICATE, manifest=_manifest(twin_snapshots=snapshots))
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert _criterion(doc, "R3")["observed"] is None and _criterion(doc, "R4")["observed"] is None
    assert "twins.before.json: the twin snapshot is not verified (exit 0): seed mismatch" in _criterion(doc, "S5")["reason"]


def test_accepted_count_advancing_by_fewer_than_the_accepted_lines_is_r4() -> None:
    """S5's tolerance is an equality: a twin whose accepted_count advanced
    by FEWER than the device's accepted lines (an accepted line the twin
    does not carry: a lost write or a wrong rebuild) is a delta mismatch
    and R4, exactly as one that advanced by more (test 21)."""
    after = _after_from(BEFORE, LINES)
    after[D1] = (BEFORE[D1][0] + 1, RID, 1)  # two accepted lines on D1 (a, b), the twin advanced by one
    doc = _evaluate(after=after)
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True and _criterion(doc, "S5")["holds"] is False
    assert r4["evidence"]["mismatches"] == [
        {"device_uuid": D1, "problems": ["accepted_count advanced by 1 against 2 accepted line(s) and 0 named N1 case(s)"]}
    ]
    assert _outcome(doc)["result"] == "refutes" and any(r.startswith("R4:") for r in _outcome(doc)["refutations"])
    # Not advanced at all, the twin's ingestion untouched: a mismatch on the
    # count and on last_run_id/last_seq alike.
    after[D1] = BEFORE[D1]
    doc = _evaluate(after=after)
    problems = _criterion(doc, "R4")["evidence"]["mismatches"][0]["problems"]
    assert problems[0].startswith("accepted_count advanced by 0 against 2 accepted line(s)")
    assert any(p.startswith("last_run_id 'earlier' last_seq 9") for p in problems)
    assert _outcome(doc)["result"] == "refutes"


def test_several_kill_claimants_name_none_and_each_is_r3() -> None:
    """E-4: one consumer dies once, so at most one identity was in progress
    at the kill. Two duplicate-only identities on different devices, each
    restart-class, published before the kill and with its device's surplus
    of one, both claim it: none is named (not the first, not any), each is
    R3 with the rule as its ground, and the note says so."""
    G = ("g-mid", D3, 1, 380 * NS)
    lines = B_DUPLICATE + [("g-mid", D3, 1, "duplicate", 1_210 * NS, None)]
    doc = _evaluate(sent=SENT + [G], lines=lines, extra_after={D1: 1, D3: 1, "seqs": [(D1, 1), (D3, 1)]})
    outcome = _outcome(doc)
    assert outcome["n1_cases"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is True and _criterion(doc, "S4")["holds"] is False
    not_named = r3["evidence"]["not_named_identities"]
    assert [c["message_id"] for c in not_named] == ["b-mid", "g-mid"]
    assert all("at most one N1 case per death" in c["why_not_named"] for c in not_named)
    assert r3["evidence"]["cannot_show_identities"] == []
    assert any("2 duplicate-only identities claim the kill" in n for n in r3["evidence"]["notes"])
    assert outcome["result"] == "refutes" and any(r.startswith("R3:") for r in outcome["refutations"])
    assert "E-4" in r3["identification_rules"] and "one N1 case per death" in pe.IDENTIFICATION_RULES["E-4"]
    # Each device's surplus is then unexplained: R4 beside R3.
    assert _criterion(doc, "R4")["observed"] is True
    assert [u["device_uuid"] for u in _criterion(doc, "R4")["evidence"]["surplus_unexplained"]] == [D1, D3]


def test_a_restart_that_did_not_execute_with_exit_0_is_not_the_kills_source() -> None:
    """P-4's third condition: the kill is shown by the manifest's restart
    record. With the restart hook exited non-zero, or not executed, the
    identity of test 16 is not named with the kill as its source and is R3
    with that ground; the record's figures are carried as evidence."""
    for change in ({"returncode": 1}, {"executed": False, "returncode": 0}):
        manifest = _manifest(restart={**_manifest()["restart"], **change})
        doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 1, "seqs": [(D1, 1)]}, manifest=manifest)
        assert _outcome(doc)["n1_cases"] == [], change
        r3 = _criterion(doc, "R3")
        assert r3["observed"] is True, change
        why = r3["evidence"]["not_named_identities"][0]["why_not_named"]
        assert "the manifest's restart did not execute with exit 0" in why, change
        assert _outcome(doc)["result"] == "refutes", change
        assert _criterion(doc, "S1")["evidence"]["restart_returncode"] == change["returncode"]
        assert _criterion(doc, "S1")["evidence"]["restart_executed"] == change.get("executed", True)


def test_s1_reads_the_last_pre_kill_row_in_file_order_not_the_latest_ts_utc() -> None:
    """P-1: 'the last reading before it' is the last row of the pre-kill
    process in FILE order. The WSL host clock steps back 2-3 s about every
    30 s, so that row can carry a ts_utc earlier than its predecessor's;
    the predecessor is not the reading S1 decides on (test 4 pins the
    process split, this pins the order within the process)."""
    raw = [
        _row(_ts(100), P0, 3, 1, monotonic_ns=1_100 * NS),
        _row(_ts(150), P0, 3, 1, monotonic_ns=1_149 * NS),
        _row(_ts(148), P0, 0, 0, monotonic_ns=K_LOWER),  # stepped back 2 s; nothing in flight
        _row(_ts(175), P1, 0, 0, monotonic_ns=K_UPPER),
    ]
    rows, notes = pe.read_metrics_rows(raw)
    split = pe.split_by_process(rows)
    s1 = pe.s1_kill_found_work(split.pre_kill, _manifest()["restart"])
    assert s1.holds is False and s1.evidence["last_reading"]["row"] == 2
    assert s1.evidence["last_reading"]["ts_utc"] == _ts(148) and s1.evidence["last_reading"]["in_flight"] == 0
    assert any("row 2" in note and "host clock step" in note for note in notes)
    doc = _evaluate(rows=raw)
    assert _criterion(doc, "S1")["holds"] is False and _outcome(doc)["result"] == "inconclusive"
    assert _criterion(doc, "S1")["evidence"]["last_reading"]["row"] == 2
    # The converse: work on the stepped-back last row, none on its predecessor.
    raw[1] = _row(_ts(150), P0, 0, 0, monotonic_ns=1_149 * NS)
    raw[2] = _row(_ts(148), P0, 2, 1, monotonic_ns=K_LOWER)
    doc = _evaluate(rows=raw)
    s1 = _criterion(doc, "S1")
    assert s1["holds"] is True and s1["evidence"]["last_reading"]["row"] == 2 and s1["evidence"]["last_reading"]["in_flight"] == 3
    assert _outcome(doc)["result"] == "supports"


def test_the_first_readable_started_at_defines_the_pre_kill_process() -> None:
    """P-1: a first row whose started_at cell is empty is unreadable for the
    split and does not make the pre-kill process None; the first READABLE
    row's started_at does, so every P0 row is pre-kill, the empty row is
    counted unreadable, and S1 reads the last P0 row."""
    raw = [_row(_ts(0), None, 3, 1, monotonic_ns=1_000 * NS)] + _rows()
    rows, _notes = pe.read_metrics_rows(raw)
    assert rows[0].started_at is None
    split = pe.split_by_process(rows)
    assert split.pre_started_at == P0
    assert [r.index for r in split.unreadable] == [0]
    assert [r.index for r in split.pre_kill] == [1, 2, 3, 4, 5, 6]
    assert [r.index for r in split.post_kill] == [7, 8, 9]
    doc = _evaluate(rows=raw)
    s1 = _criterion(doc, "S1")
    assert s1["holds"] is True and s1["evidence"]["last_reading"]["row"] == 6
    assert s1["evidence"]["last_reading"]["started_at"] == P0
    assert _outcome(doc)["result"] == "supports"
    assert _outcome(doc)["report"]["processes"] == {
        "pre_kill_started_at": P0, "post_kill_started_at": [P1], "pre_kill_rows": 6, "post_kill_rows": 3, "unreadable_rows": 1,
    }


def test_no_surplus_unexplained_entry_when_the_surplus_equals_the_named_cases() -> None:
    """R4's surplus_unexplained is evidence for the reader: a device whose
    surplus is exactly its named cases gets no entry (a 'surplus 1, named
    1, unexplained 0' row would state a problem that is not there), while
    a surplus beyond the named cases is listed with the difference."""
    doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 1, "seqs": [(D1, 1)]})
    assert [case["message_id"] for case in _outcome(doc)["n1_cases"]] == ["b-mid"]
    assert _criterion(doc, "R4")["evidence"]["surplus_unexplained"] == []
    assert _criterion(doc, "R4")["observed"] is False and _outcome(doc)["result"] == "supports"
    doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 2, "seqs": [(D1, 1)]})
    assert _criterion(doc, "R4")["evidence"]["surplus_unexplained"] == [
        {"device_uuid": D1, "surplus": 2, "named_n1_cases": 1, "unexplained": 1}
    ]
    assert _criterion(doc, "R4")["observed"] is True


# ---------------------------------------------------------------------------
# 22j-22l. the review of the review: E-9 (the twin refutes on an undecided
# device only under every naming), E-4 beside an unshown candidate, and the
# restart command's window on the host clock (E-8)
# ---------------------------------------------------------------------------


def test_a_twin_that_refutes_under_every_naming_of_an_undecided_candidate_is_r4_on_read_evidence() -> None:
    """E-9: an undecided duplicate-only candidate (E-8 here, E-7 over the
    log at the end) leaves S5/R4 null only while naming it could leave the
    twin's figures right. A surplus beyond every undecided candidate, a
    last_seq regressed against the before snapshot, or a last_run_id wrong
    whether or not the candidate is named, was read from the twin whatever
    the candidate was: R4 stands on it, with S4/R3 still null for the
    candidate. E-7 nulls what was not read, never a refutation that was."""
    in_band = (K_LOWER + K_UPPER) // 2
    lines = [line for line in LINES if line[0] != "b-mid"] + [("b-mid", D1, 1, "duplicate", in_band, None)]
    # accepted_count advanced by 4 against 1 accepted line and one undecided
    # candidate: at most one case could be named, so two remain unexplained.
    doc = _evaluate(lines=lines, extra_after={D1: 3, "seqs": [(D1, 1)]})
    outcome = _outcome(doc)
    assert outcome["result"] == "refutes"
    assert outcome["refutations"] == [
        "R4: 1 device(s) with a delta mismatch beyond the named cases; 1 of them under every "
        "naming of its unshown duplicate-only candidate(s) (E-9)"
    ]
    assert _criterion(doc, "R4")["observed"] is True and _criterion(doc, "S5")["holds"] is False
    assert _criterion(doc, "S4")["holds"] is None and _criterion(doc, "R3")["observed"] is None
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]] == ["b-mid"]
    assert outcome["n1_cases"] == []
    r4 = _criterion(doc, "R4")
    mismatch = r4["evidence"]["mismatches"][0]
    assert mismatch["device_uuid"] == D1 and mismatch["undecided_candidates"] == ["b-mid"]
    assert mismatch["problems"][0] == "accepted_count advanced by 4 against 1 accepted line(s) and 0 named N1 case(s)"
    assert mismatch["namings_tried"] == [] and "the count fits none" in mismatch["note"] and "(E-9)" in mismatch["note"]
    assert r4["evidence"]["undecided"] == [] and r4["evidence"]["last_seq_regressions"] == []
    row = next(row for row in r4["evidence"]["devices"] if row["device_uuid"] == D1)
    assert row["ok"] is False and row["undecided"]["explained"] is False and row["undecided"]["rule"] == "E-8"
    assert row["surplus"] == 3 and row["undecided"]["message_ids"] == ["b-mid"]
    for rule_id in ("S5", "R4"):
        assert {"E-9", "E-8"} <= set(_criterion(doc, rule_id)["identification_rules"]), rule_id
    assert any(r.startswith("S4 cannot be shown (E-8)") for r in outcome["inconclusive_reasons"])
    # A last_seq regressed against the before snapshot under its run_id: no
    # naming touches it (P-5), and the one naming the count allows leaves
    # the twin's last_run_id wrong as well.
    after = _after_from(BEFORE, lines, {D1: 1, "seqs": [(D1, 1)]})
    after[D1] = (after[D1][0], "earlier", 3)
    doc = _evaluate(lines=lines, after=after)
    r4 = _criterion(doc, "R4")
    assert _outcome(doc)["result"] == "refutes" and r4["observed"] is True
    assert _criterion(doc, "S4")["holds"] is None and _criterion(doc, "R3")["observed"] is None
    regression = r4["evidence"]["last_seq_regressions"][0]
    assert regression["device_uuid"] == D1 and regression["undecided_candidates"] == ["b-mid"]
    assert regression["regressed"] == "last_seq 3 is below the before snapshot's 9 under the same run_id 'earlier'"
    tried = r4["evidence"]["mismatches"][0]["namings_tried"]
    assert len(tried) == 1 and tried[0]["named_cases"] == 1 and tried[0]["highest_named_seq"] == 1
    assert tried[0]["expected_last_seq"] == 1 and tried[0]["delta_ok"] is False
    assert tried[0]["problems"] == ["last_run_id 'earlier' last_seq 3 against this run's highest applied seq 1"]
    assert tried[0]["regressed"] == regression["regressed"]
    assert "1 device(s) whose last_seq regressed" in r4["reason"] and "(E-9)" in r4["reason"]
    # The count fits the one naming, but the twin's last_run_id is not this
    # run's although the run then applied seq 1 on the device: wrong under
    # the naming as without it, a mismatch that stands; no regression.
    after = _after_from(BEFORE, lines, {D1: 1, "seqs": [(D1, 1)]})
    after[D1] = (after[D1][0], "earlier", 9)
    doc = _evaluate(lines=lines, after=after)
    r4 = _criterion(doc, "R4")
    assert _outcome(doc)["result"] == "refutes" and r4["observed"] is True
    assert r4["evidence"]["last_seq_regressions"] == []
    mismatch = r4["evidence"]["mismatches"][0]
    assert "each naming tried leaves a problem or a regression" in mismatch["note"]
    assert mismatch["namings_tried"][0]["problems"] == [
        "last_run_id 'earlier' last_seq 9 against this run's highest applied seq 1"
    ]
    assert mismatch["namings_tried"][0]["regressed"] is None
    # The figures that naming the candidate would leave right (test 22a's)
    # stay undecided: nothing is decided on them, and the naming tried says
    # what it would leave.
    doc = _evaluate(lines=lines, extra_after={D1: 1, "seqs": [(D1, 1)]})
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert _criterion(doc, "R4")["observed"] is None and _criterion(doc, "S5")["holds"] is None
    row = next(row for row in _criterion(doc, "R4")["evidence"]["devices"] if row["device_uuid"] == D1)
    assert row["ok"] is None and row["undecided"]["explained"] is True and "note" not in row["undecided"]
    assert row["undecided"]["namings_tried"] == [
        {"named_cases": 1, "highest_named_seq": 1, "expected_last_seq": 1, "problems": [], "regressed": None, "delta_ok": True}
    ]
    assert _criterion(doc, "R4")["evidence"]["undecided"] == [
        {"device_uuid": D1, "rule": "E-8", "why": row["undecided"]["why"], "message_ids": ["b-mid"]}
    ]
    # The same over the controller log (E-7): a surplus of three beyond the
    # one candidate the unread log might have named is R4 all the same.
    log_rel = f"logs/sut/{SUT_LOG_FILES['controller_log']}"
    fetches = _manifest()["sut_log_fetches"]
    fetches[1] = {**fetches[1], "returncode": 1, "dest_exists": False}
    c_lines = [line for line in LINES if line[0] != "c-mid"] + [("c-mid", D2, 0, "duplicate", 1_230 * NS, None)]
    artefacts = _artefacts(lines=c_lines, extra_after={D2: 3, "seqs": [(D2, 0)]}, manifest=_manifest(sut_log_fetches=fetches))
    artefacts.controller_log = None
    artefacts.files_present = FULL_FILES - {log_rel}
    doc = pe.evaluate(artefacts, _session())
    assert _outcome(doc)["result"] == "refutes" and _criterion(doc, "R4")["observed"] is True
    assert _criterion(doc, "R3")["observed"] is None and _criterion(doc, "S4")["holds"] is None
    mismatch = _criterion(doc, "R4")["evidence"]["mismatches"][0]
    assert mismatch["device_uuid"] == D2 and mismatch["undecided_candidates"] == ["c-mid"] and mismatch["namings_tried"] == []
    assert {"E-9", "E-7"} <= set(_criterion(doc, "R4")["identification_rules"])
    assert any(r.startswith("any fetch listed above fails") for r in _outcome(doc)["inconclusive_reasons"])
    assert "E-9" in pe.IDENTIFICATION_RULES and "no naming fits the count" in pe.IDENTIFICATION_RULES["E-9"]
    assert "(E-9)" in pe.IDENTIFICATION_RULES["E-7"] and "(E-9)" in pe.IDENTIFICATION_RULES["E-8"]


def test_one_kill_claimant_beside_an_unshown_candidate_is_neither_named_nor_r3_and_the_one_death_cannot_explain_two_twins() -> None:
    """E-4 with E-8/E-7, the namings read under E-10: one consumer dies
    once. B (restart-class, published before the restart command, its
    device's surplus of one) claims the kill; G, on another device with the
    same twin evidence, has its duplicate line inside the band and can be
    shown neither way (E-8). If G was in progress at the kill B was not,
    and nothing read tells them apart: B is neither named nor R3, with E-4
    as its ground, S4 and R3 null. But the twins were read: D1 and D3 each
    advanced by one beyond their accepted lines, and the run evidences one
    death and no A5 occurrence, so whichever identity was in progress at
    the kill, the other device's surplus is a delta mismatch beyond the
    named cases: R4 is observed on the aggregate, without naming the device
    or the identity. The same with F on B's own device (surplus two, one
    death: the Project Manager's counterexample of 2026-09-25). This case's
    earlier expectation, 'inconclusive' in both halves, spent the one death
    independently on each device and encoded the wrong rule. With the
    controller log unusable (E-7) the capacity is unknown and the run stays
    inconclusive; two claimants shown by the record stay R3 (E-4) whatever
    else is unshown."""
    in_band = (K_LOWER + K_UPPER) // 2
    G = ("g-mid", D3, 1, 380 * NS)
    lines = B_DUPLICATE + [("g-mid", D3, 1, "duplicate", in_band, None)]
    twins = {D1: 1, D3: 1, "seqs": [(D1, 1), (D3, 1)]}
    doc = _evaluate(sent=SENT + [G], lines=lines, extra_after=twins)
    outcome = _outcome(doc)
    assert outcome["result"] == "refutes" and outcome["n1_cases"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is None and _criterion(doc, "S4")["holds"] is None
    assert r3["evidence"]["not_named_identities"] == []
    shown = {c["message_id"]: c["why_not_shown"] for c in r3["evidence"]["cannot_show_identities"]}
    assert list(shown) == ["b-mid", "g-mid"]
    assert "at most one N1 case per death (E-4)" in shown["b-mid"] and "g-mid (E-8)" in shown["b-mid"]
    assert "neither named nor R3" in shown["b-mid"] and "(E-8)" in shown["g-mid"]
    assert any("beside 1 duplicate-only identity(ies)" in n and "(E-4)" in n for n in r3["evidence"]["notes"])
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True and _criterion(doc, "S5")["holds"] is False
    assert outcome["refutations"] == [
        "R4: 2 undecided device(s) whose twins together need 2 N1 case(s) against a source capacity "
        "of 1: a delta mismatch beyond the named cases stands on at least one of them, which cannot "
        "be told (E-10)"
    ]
    assert [(u["device_uuid"], u["rule"], u["message_ids"]) for u in r4["evidence"]["undecided"]] == [
        (D1, "E-4", ["b-mid"]), (D3, "E-8", ["g-mid"]),
    ]
    assert r4["evidence"]["source_capacity"] == {
        "applied": True, "known": True, "why_unknown": None, "kill_available": 1,
        "a5_possible_by_device": {D1: [], D3: []}, "needed": 2, "capacity": 1, "consistent": False,
    }
    mismatches = r4["evidence"]["mismatches"]
    assert len(mismatches) == 1 and mismatches[0]["device_uuid"] is None and mismatches[0]["devices"] == [D1, D3]
    assert mismatches[0]["undecided_candidates"] == ["b-mid", "g-mid"]
    assert "no source-consistent naming explains the twins" in mismatches[0]["problems"][0]
    assert "the kill (1 available) and 0 A5 occurrence(s)" in mismatches[0]["problems"][0]
    assert "no identity is named as the case and none as the mismatch" in mismatches[0]["note"] and "(E-10)" in mismatches[0]["note"]
    # Per device the figures stay as read: each count is explained on its
    # own and marked inconsistent with the sources; neither is named.
    for device in (D1, D3):
        row = next(row for row in r4["evidence"]["devices"] if row["device_uuid"] == device)
        assert row["ok"] is None and row["undecided"]["explained"] is True, device
        assert row["undecided"]["source_consistent"] is False, device
    assert r4["evidence"]["last_seq_regressions"] == [] and r4["evidence"]["surplus_unexplained"] == []
    assert {"E-9", "E-10", "E-4", "E-8"} <= set(r4["identification_rules"])
    assert any(r.startswith("S4 cannot be shown (E-8)") and "(E-4)" in r for r in outcome["inconclusive_reasons"])
    # F on B's own device, surplus 2: B is unshown likewise and the device's
    # one undecided entry lists both; naming both fits the twin's count and
    # not the one death: R4 on the device, neither identity named.
    F = ("f-mid", D1, 2, 401 * NS)
    doc = _evaluate(sent=SENT + [F], lines=B_DUPLICATE + [("f-mid", D1, 2, "duplicate", in_band, None)], extra_after={D1: 2, "seqs": [(D1, 2)]})
    assert _outcome(doc)["result"] == "refutes" and _outcome(doc)["n1_cases"] == []
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]] == ["b-mid", "f-mid"]
    assert _criterion(doc, "R3")["observed"] is None and _criterion(doc, "S4")["holds"] is None
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True and _criterion(doc, "S5")["holds"] is False
    undecided = r4["evidence"]["undecided"]
    assert len(undecided) == 1 and undecided[0]["device_uuid"] == D1 and undecided[0]["rule"] == "E-8"
    assert undecided[0]["message_ids"] == ["b-mid", "f-mid"]
    row = next(row for row in r4["evidence"]["devices"] if row["device_uuid"] == D1)
    assert row["ok"] is None and row["undecided"]["namings_tried"][0]["named_cases"] == 2
    assert row["undecided"]["namings_tried"][0]["delta_ok"] is True and row["undecided"]["source_consistent"] is False
    assert (r4["evidence"]["source_capacity"]["needed"], r4["evidence"]["source_capacity"]["capacity"]) == (2, 1)
    assert r4["evidence"]["mismatches"][0]["device_uuid"] == D1 and r4["evidence"]["mismatches"][0]["devices"] == [D1]
    assert r4["reason"] == (
        "1 undecided device(s) whose twins together need 2 N1 case(s) against a source capacity of 1: "
        "a delta mismatch beyond the named cases stands on at least one of them, which cannot be told (E-10)"
    )
    # G unshown by the controller log instead (E-7): the claimant is unshown
    # with that label, the capacity unknown (an unread log is not proof of
    # zero A3 events), the run inconclusive for the failed fetch - never R4
    # on capacity grounds.
    log_rel = f"logs/sut/{SUT_LOG_FILES['controller_log']}"
    fetches = _manifest()["sut_log_fetches"]
    fetches[1] = {**fetches[1], "returncode": 1, "dest_exists": False}
    artefacts = _artefacts(sent=SENT + [G], lines=lines, extra_after=twins, manifest=_manifest(sut_log_fetches=fetches))
    artefacts.controller_log = None
    artefacts.files_present = FULL_FILES - {log_rel}
    doc = pe.evaluate(artefacts, _session())
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == [] and _outcome(doc)["n1_cases"] == []
    shown = {c["message_id"]: c["why_not_shown"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]}
    assert list(shown) == ["b-mid", "g-mid"] and "g-mid (E-7)" in shown["b-mid"] and "(E-7)" in shown["g-mid"]
    capacity = _criterion(doc, "R4")["evidence"]["source_capacity"]
    assert capacity["applied"] is False and capacity["known"] is False and capacity["consistent"] is None
    assert capacity["why_unknown"].startswith(log_rel) and capacity["needed"] == 2
    assert _criterion(doc, "R4")["observed"] is None and _criterion(doc, "S5")["holds"] is None
    # Two claimants shown by the record beside H, on a device neither
    # snapshot names: the two are R3 as E-4 states (test 22e), H unshown.
    G_above = [("g-mid", D3, 1, "duplicate", 1_210 * NS, None)]
    H = ("h-mid", D4, 0, 400 * NS)
    doc = _evaluate(sent=SENT + [G, H], lines=B_DUPLICATE + G_above + [("h-mid", D4, 0, "duplicate", 1_230 * NS, None)], extra_after=twins)
    assert _outcome(doc)["result"] == "refutes" and _criterion(doc, "R3")["observed"] is True
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["not_named_identities"]] == ["b-mid", "g-mid"]
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]] == ["h-mid"]
    assert "beside" in pe.IDENTIFICATION_RULES["E-4"] and "(E-9)" in pe.IDENTIFICATION_RULES["E-4"]


def test_the_namings_respect_the_sources_the_run_evidences_across_the_run() -> None:
    """E-10 (the review of PR #47, F3): the namings E-9 tries must fit the
    sources evidenced across the whole run. A second evidenced A3 source
    that suffices names its case (an A5 occurrence on G's device before its
    redelivery): both twins are explained and the run supports; the same
    occurrence after G's redelivery cannot be G's source, so the one death
    is all there is and R4 stands; when G's line carries no received stamp
    the occurrence's order against it cannot be read, so it may be G's
    source: the capacity suffices and the cases stay unshown (inconclusive).
    A single uncertain candidate against one death stays inconclusive; no
    hypothetical A3 event is ever added; two candidates on one device with
    the log unusable stay inconclusive on E-9's count alone."""
    in_band = (K_LOWER + K_UPPER) // 2
    G = ("g-mid", D3, 1, 380 * NS)
    lines = B_DUPLICATE + [("g-mid", D3, 1, "duplicate", in_band, None)]
    twins = {D1: 1, D3: 1, "seqs": [(D1, 1), (D3, 1)]}
    doc = _evaluate(sent=SENT + [G], lines=lines, extra_after=twins, controller_log=[_a5_line(D3, in_band - NS)])
    assert _outcome(doc)["result"] == "supports"
    assert [(c["message_id"], c["source"]) for c in _outcome(doc)["n1_cases"]] == [("b-mid", "kill"), ("g-mid", "a3-connection-end")]
    assert _criterion(doc, "R4")["evidence"]["source_capacity"]["applied"] is False
    # The occurrence after G's redelivery names nothing and serves no
    # undecided candidate: the one death cannot explain both twins.
    doc = _evaluate(sent=SENT + [G], lines=lines, extra_after=twins, controller_log=[_a5_line(D3, in_band + NS)])
    assert _outcome(doc)["result"] == "refutes" and _outcome(doc)["n1_cases"] == []
    capacity = _criterion(doc, "R4")["evidence"]["source_capacity"]
    assert capacity["a5_possible_by_device"] == {D1: [], D3: []} and (capacity["needed"], capacity["capacity"]) == (2, 1)
    assert _outcome(doc)["report"]["a5_occurrences"][0]["device_uuid"] == D3  # read, reported, not a source of G
    # G's line without a received stamp: the occurrence may be its source.
    unstamped = B_DUPLICATE + [("g-mid", D3, 1, "duplicate", None, None)]
    doc = _evaluate(sent=SENT + [G], lines=unstamped, extra_after=twins, controller_log=[_a5_line(D3, in_band + NS)])
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == [] and _outcome(doc)["n1_cases"] == []
    capacity = _criterion(doc, "R4")["evidence"]["source_capacity"]
    assert capacity["a5_possible_by_device"] == {D1: [], D3: [1]} and (capacity["needed"], capacity["capacity"]) == (2, 2)
    assert capacity["consistent"] is True and _criterion(doc, "R4")["observed"] is None
    for row in _criterion(doc, "R4")["evidence"]["devices"]:
        if row["device_uuid"] in (D1, D3):
            assert row["undecided"]["source_consistent"] is True, row["device_uuid"]
    # A single uncertain candidate against the one death: consistent, unshown.
    doc = _evaluate(lines=[line for line in LINES if line[0] != "b-mid"] + [("b-mid", D1, 1, "duplicate", in_band, None)], extra_after={D1: 1, "seqs": [(D1, 1)]})
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert _criterion(doc, "R4")["evidence"]["source_capacity"] == {
        "applied": True, "known": True, "why_unknown": None, "kill_available": 1,
        "a5_possible_by_device": {D1: []}, "needed": 1, "capacity": 1, "consistent": True,
    }
    # Two candidates on one device, surplus 2, the log unusable: E-7 leaves
    # both unshown and the capacity unknown; the count alone is read.
    F = ("f-mid", D1, 2, 401 * NS)
    log_rel = f"logs/sut/{SUT_LOG_FILES['controller_log']}"
    fetches = _manifest()["sut_log_fetches"]
    fetches[1] = {**fetches[1], "returncode": 1, "dest_exists": False}
    artefacts = _artefacts(sent=SENT + [F], lines=B_DUPLICATE + [("f-mid", D1, 2, "duplicate", in_band, None)], extra_after={D1: 2, "seqs": [(D1, 2)]}, manifest=_manifest(sut_log_fetches=fetches))
    artefacts.controller_log = None
    artefacts.files_present = FULL_FILES - {log_rel}
    doc = pe.evaluate(artefacts, _session())
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]] == ["b-mid", "f-mid"]
    capacity = _criterion(doc, "R4")["evidence"]["source_capacity"]
    assert capacity["applied"] is False and capacity["known"] is False and capacity["why_unknown"].startswith(log_rel)
    assert _criterion(doc, "R4")["observed"] is None and "E-10" in _criterion(doc, "R4")["identification_rules"]
    assert "E-10" in pe.IDENTIFICATION_RULES and "capacity" in pe.IDENTIFICATION_RULES["E-10"]
    assert "(E-10)" in pe.IDENTIFICATION_RULES["E-9"] and "not proof of zero A3 events" in pe.IDENTIFICATION_RULES["E-10"]
    assert "no A3 event assumed that the log does not record" in pe.IDENTIFICATION_RULES["E-10"]


def test_a_publication_inside_the_restart_commands_window_cannot_be_shown_and_never_refutes() -> None:
    """E-8 on the host clock: the manifest's started_monotonic_ns is the
    instant the harness spawned the restart command, and the SIGKILL lands
    during it (finished_utc 22 s later here, as in r01/r02). X, published
    5 s after that start, duplicate-only, restart-class and with its
    device's surplus, is neither 'published before the kill' nor after it:
    it is neither named nor R3 and the run is inconclusive, where the
    hook's start alone would have refuted it (R3 and R4). Published at the
    window's end (plus the 3 s host band) it is R3 as before; a publication
    that cannot be placed at all is unshown too, and without a readable
    end the window has none."""
    X = ("x-mid", D3, 1, 505 * NS)
    lines = LINES + [("x-mid", D3, 1, "duplicate", K_UPPER + 20 * NS, None)]
    twin = {D3: 1, "seqs": [(D3, 1)]}
    doc = _evaluate(sent=SENT + [X], lines=lines, extra_after=twin)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == [] and outcome["n1_cases"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is None and _criterion(doc, "S4")["holds"] is None
    assert r3["evidence"]["not_named_identities"] == []
    shown = r3["evidence"]["cannot_show_identities"]
    assert [c["message_id"] for c in shown] == ["x-mid"] and shown[0]["class"] == "restart_class"
    why = shown[0]["why_not_shown"]
    assert "inside the restart command's window" in why and "(E-8)" in why and "the restart class" not in why
    assert str(505 * NS) in why and str(HOST_KILL_NS) in why and str(HOST_RESTART_END_NS) in why
    assert shown[0]["published_before_kill"] is False and shown[0]["published_during_restart"] is True
    assert _criterion(doc, "R4")["observed"] is None and _criterion(doc, "S5")["holds"] is None
    assert _criterion(doc, "R4")["evidence"]["undecided"][0]["message_ids"] == ["x-mid"]
    report = outcome["report"]["classification"]
    assert report["published_before_kill"] == 3 and report["published_during_restart"] == 1
    assert report["published_while_away"] == 1 and report["published_after_resubscription"] == 0
    assert report["away_window"]["restart_command_end_host_monotonic_ns"] == HOST_RESTART_END_NS
    assert "restart command's window" in report["away_window"]["note"]
    assert _classify(lines, SENT + [X]).published_during_restart == ["x-mid"]
    assert any(r.startswith("S4 cannot be shown (E-8)") and "restart command's window" in r for r in outcome["inconclusive_reasons"])
    # At the window's end: published after the kill on the host clock, R3
    # (and its surplus R4), as before.
    at_end = SENT + [("x-mid", D3, 1, HOST_RESTART_END_NS)]
    doc = _evaluate(sent=at_end, lines=lines, extra_after=twin)
    assert _outcome(doc)["result"] == "refutes" and _criterion(doc, "R3")["observed"] is True
    not_named = _criterion(doc, "R3")["evidence"]["not_named_identities"]
    assert [c["message_id"] for c in not_named] == ["x-mid"]
    assert "published after the restart command's end on the host clock" in not_named[0]["why_not_named"]
    assert _criterion(doc, "R4")["observed"] is True
    assert _classify(lines, at_end).published_while_away == ["c-mid", "x-mid"]
    # A publication that cannot be placed against the command's start (no
    # publish_monotonic_ns on the sent line) is unshown, not R3.
    doc = _evaluate(sent=SENT + [("x-mid", D3, 1, None)], lines=lines, extra_after=twin)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    shown = _criterion(doc, "R3")["evidence"]["cannot_show_identities"]
    assert [c["message_id"] for c in shown] == ["x-mid"] and shown[0]["publication_unplaced"] is True
    assert "cannot be placed against the restart command's start" in shown[0]["why_not_shown"]
    # Without a readable finished_utc the window has no end: every identity
    # published after the command's start is inside it, and the note says so.
    manifest = _manifest(restart={**_manifest()["restart"], "finished_utc": None})
    doc = _evaluate(sent=at_end, lines=lines, extra_after=twin, manifest=manifest)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    report = _outcome(doc)["report"]["classification"]
    assert report["published_during_restart"] == 2 and report["published_while_away"] == 0
    assert report["away_window"]["restart_command_end_host_monotonic_ns"] is None
    assert any("the restart command's end is unplaced" in n for n in report["notes"])
    assert "an instant that cannot be read" in _criterion(doc, "R3")["evidence"]["cannot_show_identities"][0]["why_not_shown"]
    assert "restart command's window" in pe.IDENTIFICATION_RULES["E-8"]
    assert "restart command's window" in pe.IDENTIFICATION_RULES["P-4"] and "restart command's window" in pe.IDENTIFICATION_RULES["P-3"]


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
    """A complete diagnostic with only the campaign's sampling-gap deviation
    still supports: the harness's validity is quoted, and the proof's own
    eligibility (E-11) is checked apart and met."""
    reasons = ["controller_metrics.csv: sample gap 12.0 s exceeds MAX_SAMPLE_GAP_S (5.0 s) after the restart"]
    doc = _evaluate(manifest=_manifest(validity="invalid", validity_reasons=reasons))
    assert doc["instrumentation"]["harness_validity"] == "invalid"
    assert doc["instrumentation"]["harness_validity_reasons"] == reasons
    assert _outcome(doc)["result"] == "supports"
    assert doc["instrumentation"]["proof_evidence"]["complete"] is True
    assert "kept as recorded" in doc["instrumentation"]["note"]
    assert "MAX_SAMPLE_GAP_S" in doc["cannot_show"]
    eligibility = doc["instrumentation"]["proof_eligibility"]
    assert eligibility["eligible"] is True and eligibility["reasons"] == [] and eligibility["unknown"] == []
    assert eligibility["rule"] == pe.IDENTIFICATION_RULES["E-11"] and "MAX_SAMPLE_GAP_S" in eligibility["rule"]
    assert eligibility["checks"]["load"]["ok"] is True and eligibility["checks"]["publication"]["ok"] is True
    assert eligibility["checks"]["publication"]["source"] == "the simulator's own manifest"
    assert eligibility["checks"]["fault"] == {
        "restart_executed": True, "restart_returncode": 0, "restart_ok": True, "restart_shown": True, "session_facts_present": True,
    }


# ---------------------------------------------------------------------------
# 27a-27g. the Project Manager's review of PR #47 (2026-09-25): F1, the proof's
# eligibility (E-11), and the drain verified before R1
# ---------------------------------------------------------------------------


def _eligibility(doc: dict) -> dict:
    return doc["instrumentation"]["proof_eligibility"]


def _assert_not_eligible(doc: dict, *fragments: str) -> None:
    """Not eligible: inconclusive with every reason named, never supports;
    each fragment is found in one of the eligibility's reasons."""
    eligibility = _eligibility(doc)
    assert eligibility["eligible"] is False, eligibility
    assert _outcome(doc)["result"] == "inconclusive"
    for fragment in fragments:
        assert any(fragment in reason for reason in eligibility["reasons"]), (fragment, eligibility["reasons"])
    assert any(r.startswith("not eligible (E-11)") or r.startswith("any fetch listed above fails") for r in _outcome(doc)["inconclusive_reasons"])


def test_the_initial_event_copy_must_be_present_with_its_fetch_recorded_ok() -> None:
    """The ADR keeps two event copies apart: the harness fetch and the
    post-drain fetch, and a failed fetch is inconclusive. A successful
    post-drain fetch with the harness copy absent, a harness fetch recorded
    failed beside a stale readable file, or no fetch record at all, each
    leave the run not eligible; the post-drain copy still serves the
    criteria and refutes nothing here."""
    artefacts = _artefacts()
    artefacts.events_timed = None
    artefacts.files_present = FULL_FILES - {"events.jsonl"}
    doc = pe.evaluate(artefacts, _session())
    _assert_not_eligible(doc, "records: the proof's evidence is not complete", "events.jsonl: recorded as fetched but absent from the run directory")
    evidence = doc["instrumentation"]["proof_evidence"]
    assert evidence["complete"] is False and evidence["present"]["events.jsonl"] is False
    assert any(m.startswith("events.jsonl: recorded as fetched but absent") for m in evidence["missing"])
    assert any(r.startswith("any fetch listed above fails") and "events.jsonl" in r for r in _outcome(doc)["inconclusive_reasons"])
    assert _criterion(doc, "S2")["holds"] is True and _outcome(doc)["refutations"] == []
    assert evidence["present"][POST_DRAIN_EVENTS_FILENAME] is True
    # The harness fetch failed: the readable file beside it is not the copy.
    failed = _manifest(
        events_fetch={**_manifest()["events_fetch"], "ok": False, "attempts": [{"attempt": 1, "returncode": 1, "dest_exists": True}]},
        events_source="/opt/egw/events/proof-adr0011-r01.jsonl (local fallback)",
    )
    doc = _evaluate(manifest=failed)
    _assert_not_eligible(doc, "events.jsonl: the harness fetch failed after 1 attempt(s): the readable file beside it is not the copy")
    assert doc["instrumentation"]["proof_evidence"]["present"]["events.jsonl"] is True
    assert _outcome(doc)["report"]["copies"]["events.jsonl"]["lines"] == 2  # reported, never a criterion
    # No fetch record at all: the copy is not shown fetched.
    doc = _evaluate(manifest=_manifest(events_fetch=None))
    _assert_not_eligible(doc, "events.jsonl: no harness fetch record (events_fetch, --fetch-events-cmd)")
    assert any(m.startswith("events.jsonl: no harness fetch record") for m in doc["instrumentation"]["proof_evidence"]["missing"])


def test_a_simulator_that_failed_or_stopped_early_after_a_shown_restart_never_supports() -> None:
    """The simulator fails after the fault and before the 300 s: the harness
    drains, fetches, seals and records the failure; every identity that was
    published is accepted and the twins match. That is a shorter workload,
    not the prescribed one: not eligible, every criterion holding on what
    was published notwithstanding. The simulator's own manifest is the
    record of the publication: not completed, a copy that is not whole, or
    another run's or load's manifest, each disqualify; a refutation
    observed on the copy still stands (P-7)."""
    early = _manifest(simulator_returncode=1, validity="invalid", validity_reasons=[
        "simulator exited with code 1: the measured run did not complete cleanly; there is no override for a failed measured run",
    ])
    doc = _evaluate(manifest=early, simulator_manifest=_simulator_manifest(4, completed=False))
    _assert_not_eligible(
        doc,
        "publication: the simulator did not exit 0 (simulator_returncode 1)",
        "completed is False: the schedule did not run to its end",
    )
    assert all(_criterion(doc, rule)["holds"] is True for rule in pe.SUPPORT_RULE_IDS)
    assert _outcome(doc)["refutations"] == []
    assert _eligibility(doc)["checks"]["publication"]["read"]["completed"] is False
    assert _eligibility(doc)["checks"]["simulator_returncode"] == 1
    assert any(r.startswith("not eligible (E-11): publication:") for r in _outcome(doc)["inconclusive_reasons"])
    # The simulator exited 0 but its manifest says the schedule did not run
    # to its end; a copy that is not whole; another run's or load's manifest.
    _assert_not_eligible(_evaluate(simulator_manifest=_simulator_manifest(4, completed=False)), "completed is False")
    _assert_not_eligible(_evaluate(simulator_manifest=_simulator_manifest(5)), "totals.sent 5 against 4 record(s) of this run in sent_events.jsonl: the copy is not whole")
    _assert_not_eligible(_evaluate(simulator_manifest=_simulator_manifest(4, run_id="other")), "its run_id is 'other'")
    _assert_not_eligible(_evaluate(simulator_manifest=_simulator_manifest(4, duration_s=600.0)), "its duration_s is 600.0")
    _assert_not_eligible(_evaluate(simulator_manifest=_simulator_manifest(4, rates_hz={"aggregate": 5.0, "per_device": {}})), "its rates_hz.aggregate is 5.0")
    _assert_not_eligible(_evaluate(simulator_manifest=_simulator_manifest(4, scenario="smoke")), "its scenario is 'smoke'")
    _assert_not_eligible(_evaluate(simulator_manifest=_simulator_manifest(4, totals={"sent": "4"})), "totals.sent '4' is not an integer")
    # A refutation observed on the copy that was read stands beside the
    # ineligibility: never re-run away, and the eligibility still named.
    twice = LINES + [("b-mid", D1, 1, "accepted", 1_300 * NS, None)]
    doc = _evaluate(manifest=early, lines=twice, simulator_manifest=_simulator_manifest(4, completed=False))
    assert _outcome(doc)["result"] == "refutes" and _eligibility(doc)["eligible"] is False
    assert any(r.startswith("R2:") for r in _outcome(doc)["refutations"])


@pytest.mark.parametrize(
    "change",
    [{"duration_s": 600}, {"rate_msg_s": 5.0}, {"scenario": "smoke"}, {"warmup_s": 60}, {"condition_id": "nominal"}, {"duration_s": None}],
    ids=lambda change: next(iter(change)),
)
def test_the_prescribed_load_is_required_from_the_manifests_entry(change: dict) -> None:
    doc = _evaluate(manifest=_manifest(**change))
    key = next(iter(change))
    _assert_not_eligible(doc, "load: the manifest's entry is not the diagnostic plan's", f"{key} {change[key]!r}")
    checks = _eligibility(doc)["checks"]["load"]
    assert checks["ok"] is False and checks["read"][key] == change[key] and checks["prescribed"] == pe.PROOF_LOAD
    assert _outcome(doc)["refutations"] == []


def test_the_prescribed_load_is_the_plan_helpers_and_the_adrs() -> None:
    """The figures E-11 requires are the ones tools/session/proof_plan.py
    writes and the ADR states ('300 s of publication = 3,360 messages')."""
    helper = (Path(__file__).resolve().parents[2] / "tools" / "session" / "proof_plan.py").read_text(encoding="utf-8")
    assert f'PROOF_CONDITION_ID = "{pe.PROOF_LOAD["condition_id"]}"' in helper
    assert f"PROOF_DURATION_S = {pe.PROOF_LOAD['duration_s']}" in helper
    assert f"PROOF_RATE_MSG_S = {pe.PROOF_LOAD['rate_msg_s']}" in helper
    assert pe.PROOF_LOAD["scenario"] == "nominal" and pe.PROOF_LOAD["warmup_s"] == 0
    assert pe.PROOF_EXPECTED_MESSAGES == 3360 == round(pe.PROOF_LOAD["duration_s"] * pe.PROOF_LOAD["rate_msg_s"])
    adr = " ".join(pe.ADR_PATH.read_text(encoding="utf-8").split())
    assert "no warm-up, 300 s of publication = 3,360 messages" in adr


def test_an_unreliable_population_record_cannot_qualify_a_reduced_denominator() -> None:
    """A skipped line (E-5), a record without a message_id, a repeated
    message_id or another run's record make sent_events.jsonl unreliable
    as the population: not eligible, and the count read is never reduced
    to fit. Without the simulator's manifest the only count is the file's,
    which must then equal the plan's 3,360 with no tolerance; with 3,360
    records it is met."""
    artefacts = _artefacts()
    artefacts.skipped_lines = {"sent_events.jsonl": 1}
    doc = pe.evaluate(artefacts, _session())
    _assert_not_eligible(doc, "population: sent_events.jsonl is not a reliable record", "1 line(s) skipped (not a JSON object or not UTF-8, E-5)")
    population = _eligibility(doc)["checks"]["population"]
    assert population["reliable"] is False and population["records_of_this_run"] == 4 and population["skipped_lines"] == 1
    assert "a smaller denominator is never read from it" in _eligibility(doc)["reasons"][0]
    artefacts = _artefacts()
    artefacts.sent_events.append({"run_id": RID, "seq": 9})
    _assert_not_eligible(pe.evaluate(artefacts, _session()), "1 record(s) of this run without a message_id")
    artefacts = _artefacts()
    artefacts.sent_events.append(_sent(*A))
    _assert_not_eligible(pe.evaluate(artefacts, _session()), "1 record(s) repeating a message_id")
    artefacts = _artefacts()
    artefacts.sent_events.append(_sent("z-mid", D1, 9, 900 * NS, run_id="other"))
    _assert_not_eligible(pe.evaluate(artefacts, _session()), "1 record(s) of another run")
    # The simulator's manifest absent: the file's count against the plan's.
    artefacts = _artefacts()
    artefacts.simulator_manifest = None
    artefacts.files_present = FULL_FILES - {SIM_MANIFEST_REL}
    doc = pe.evaluate(artefacts, _session())
    _assert_not_eligible(
        doc,
        f"publication: the simulator's manifest ({SIM_MANIFEST_REL}) is absent or unreadable, so the only count is "
        "sent_events.jsonl's: 4 record(s) of this run against the plan's 3360 (300 s x 11.2 msg/s), with no tolerance",
    )
    publication = _eligibility(doc)["checks"]["publication"]
    assert publication["source"].startswith("sent_events.jsonl's count") and publication["expected_from_plan"] == 3360
    assert doc["instrumentation"]["proof_evidence"]["present"][SIM_MANIFEST_REL] is False
    # Present but unreadable: the loader's problem is named.
    artefacts = _artefacts()
    artefacts.simulator_manifest = None
    artefacts.problems = [f"{SIM_MANIFEST_REL}: manifest.json is not a JSON object"]
    doc = pe.evaluate(artefacts, _session())
    _assert_not_eligible(doc, "manifest.json is not a JSON object")
    assert f"{SIM_MANIFEST_REL}: manifest.json is not a JSON object" in doc["instrumentation"]["proof_evidence"]["fetch_failures"]
    assert _eligibility(doc)["checks"]["publication"]["problem"] == f"{SIM_MANIFEST_REL}: manifest.json is not a JSON object"
    # With the plan's 3,360 records, every one lined, the fallback is met.
    devices = (D1, D2, D3)
    big_sent = [(f"m-{i:04d}", devices[i % 3], i // 3, 360 * NS + i * 50_000_000) for i in range(3360)]
    big_lines = [(f"m-{i:04d}", devices[i % 3], i // 3, "accepted", 1_200 * NS + i * 1_000_000, None) for i in range(3360)]
    artefacts = _artefacts(sent=big_sent, lines=big_lines)
    artefacts.simulator_manifest = None
    artefacts.files_present = FULL_FILES - {SIM_MANIFEST_REL}
    doc = pe.evaluate(artefacts, _session())
    assert _eligibility(doc)["eligible"] is True and _eligibility(doc)["checks"]["publication"]["ok"] is True
    assert _eligibility(doc)["checks"]["publication"]["records_of_this_run"] == 3360
    assert _outcome(doc)["result"] == "supports"


def test_all_accepted_evidence_with_a_failed_or_unshown_restart_is_never_a_standalone_supports() -> None:
    """The fault must be demonstrated: the manifest's restart executed with
    exit 0 AND the session facts' restart_shown true. Every identity
    accepted and every criterion holding, the evaluator's own document
    still says inconclusive when the restart is not shown; a null or absent
    restart_shown is unknown (P-6), never read as shown."""
    for change in ({"returncode": 1}, {"executed": False, "returncode": 0}, {"returncode": None}):
        doc = _evaluate(manifest=_manifest(restart={**_manifest()["restart"], **change}))
        _assert_not_eligible(doc, "fault: the manifest's restart did not execute with exit 0")
        assert all(_criterion(doc, rule)["holds"] is True for rule in pe.SUPPORT_RULE_IDS), change
        assert _outcome(doc)["refutations"] == [], change
        assert _eligibility(doc)["checks"]["fault"]["restart_ok"] is False
    doc = pe.evaluate(_artefacts(), _session(restart_shown=False))
    _assert_not_eligible(doc, "fault: the session facts record the restart as not shown (restart_shown false): the fault was not applied")
    assert doc["session_facts"]["restart_shown"] is False and _eligibility(doc)["checks"]["fault"]["restart_shown"] is False
    assert all(_criterion(doc, rule)["holds"] is True for rule in pe.SUPPORT_RULE_IDS)
    # Null: unknown, not false.
    doc = pe.evaluate(_artefacts(), _session(restart_shown=None))
    eligibility = _eligibility(doc)
    assert eligibility["eligible"] is None and eligibility["reasons"] == []
    assert eligibility["unknown"] == ["fault: whether the restart was shown is unknown: the session facts carry no restart_shown (null) (P-6)"]
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert eligibility["unknown"][0] in _outcome(doc)["inconclusive_reasons"]
    assert not any(r.startswith("not eligible (E-11)") for r in _outcome(doc)["inconclusive_reasons"])
    assert "restart_shown" in pe.IDENTIFICATION_RULES["P-6"] and "never read as false" in pe.IDENTIFICATION_RULES["P-6"]
    # No session facts: the stop rules and the restart are both unknown.
    doc = pe.evaluate(_artefacts(), None)
    eligibility = _eligibility(doc)
    assert eligibility["eligible"] is None and eligibility["checks"]["fault"]["session_facts_present"] is False
    assert eligibility["unknown"] == ["fault: whether the restart was shown is unknown: no session facts (proof_session.json) were given (P-6)"]
    reasons = _outcome(doc)["inconclusive_reasons"]
    assert any("whether a stop rule of the ceiling was reached is unknown" in r for r in reasons)
    assert eligibility["unknown"][0] in reasons


def test_the_collector_file_is_required_in_the_inventory() -> None:
    """Item 5 of 'What it records' lists the collector file: absent, or not
    the SUT collector's (the manifest's resource_source), the evidence is
    not complete and the run not eligible; the inventory names every
    record the ADR lists."""
    artefacts = _artefacts()
    artefacts.files_present = FULL_FILES - {"resources.csv"}
    doc = pe.evaluate(artefacts, _session())
    _assert_not_eligible(doc, "resources.csv: absent (the collector file, item 5 of 'What it records')")
    evidence = doc["instrumentation"]["proof_evidence"]
    assert evidence["present"]["resources.csv"] is False and evidence["complete"] is False
    assert any(r.startswith("any fetch listed above fails") and "resources.csv" in r for r in _outcome(doc)["inconclusive_reasons"])
    doc = _evaluate(manifest=_manifest(resource_source="local-dev"))
    _assert_not_eligible(doc, "resources.csv: resource_source 'local-dev', not the SUT collector's ('sut-collector')")
    present = _evaluate()["instrumentation"]["proof_evidence"]["present"]
    assert set(present) == FULL_FILES - {"manifest.json"} and all(present.values())


def test_r1_needs_the_drain_record_verified_not_merely_the_quiet_string() -> None:
    """R1 asserts missing identities after a completed drain: the drain
    record must be verified by the harness with outcome 'quiet', never the
    outcome string alone (P-7, E-7). Unverified, or without a record, R1
    is null and the missing lines go to the inconclusive rule with the
    drain named as a failed fetch."""
    missing = [line for line in LINES if line[0] != "c-mid"]
    unverified = _manifest(drain={**_manifest()["drain"], "verified": False})
    doc = _evaluate(lines=missing, manifest=unverified)
    r1 = _criterion(doc, "R1")
    assert r1["observed"] is None and "no completed drain" in r1["reason"] and "verified False" in r1["reason"]
    assert r1["evidence"] == {
        "drain_outcome": "quiet", "drain_verified": False, "drain_completed": False,
        "without_outcome_line": 1, "without_outcome_line_ids": ["c-mid"],
    }
    assert {"P-7", "E-7"} <= set(r1["identification_rules"])
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert any(f.startswith("drain: outcome 'quiet'") for f in doc["instrumentation"]["proof_evidence"]["fetch_failures"])
    assert doc["instrumentation"]["proof_evidence"]["drain"] == {"source": "hook", "outcome": "quiet", "verified": False}
    doc = _evaluate(lines=missing, manifest=_manifest(drain=None))
    assert _criterion(doc, "R1")["observed"] is None and _criterion(doc, "R1")["evidence"]["drain_completed"] is False
    assert any(m.startswith("drain: no record") for m in doc["instrumentation"]["proof_evidence"]["missing"])
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    # Verified and quiet: observed, as test 15 states.
    doc = _evaluate(lines=missing)
    assert _criterion(doc, "R1")["observed"] is True and _criterion(doc, "R1")["evidence"]["drain_completed"] is True


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
    assert doc["instrumentation"]["proof_eligibility"]["rule"] == pe.IDENTIFICATION_RULES["E-11"]
    assert doc["instrumentation"]["proof_eligibility"]["eligible"] is True
    assert set(pe.IDENTIFICATION_RULES) == {f"P-{n}" for n in range(1, 8)} | {f"E-{n}" for n in range(1, 12)}
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


def test_a_jsonl_line_that_is_not_utf8_is_skipped_and_counted_never_a_crash(tmp_path, capsys, monkeypatch) -> None:
    """CONTRACTS.md lets a torn final line exist on disk and tells a reader
    to skip a line that is not JSON: a line that is not UTF-8 is such a line
    (E-5), counted and never a traceback, since exit 1 is 'refutes'. A torn
    line of the post-drain copy leaves the copy serving the criteria; a
    torn line of sent_events.jsonl is skipped and counted likewise, but the
    population record is then unreliable and the run not eligible (E-11):
    exit 3, never a reduced denominator (this case's earlier expectation,
    exit 0 with the torn sent line, encoded the wrong rule). A CSV that
    does not decode is a read problem the evidence names; a failure of the
    evaluator itself is exit 2, never a result."""
    run_dir = _write_run_dir(tmp_path, seal=False)
    with (run_dir / POST_DRAIN_EVENTS_FILENAME).open("ab") as fh:
        fh.write(b"\xff\n" + json.dumps(_line("c-mid", D2, 0, "duplicate", 1_290 * NS)).encode() + b"\n")
    write_sha256sums(run_dir)
    out = tmp_path / "verdict.json"
    assert _main(run_dir, out, _session_file(tmp_path)) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["instrumentation"]["skipped_lines"] == {"sent_events.jsonl": 0, "events.jsonl": 0, POST_DRAIN_EVENTS_FILENAME: 1}
    assert doc["system_outcome"]["report"]["copies"][POST_DRAIN_EVENTS_FILENAME]["lines"] == 5  # the line after the torn one was read
    assert doc["instrumentation"]["proof_eligibility"]["eligible"] is True
    assert "Traceback" not in capsys.readouterr().err
    # The torn line in sent_events.jsonl: skipped and counted, and the
    # population is no longer a reliable record of what was published.
    torn = _write_run_dir(tmp_path / "torn", seal=False)
    with (torn / "sent_events.jsonl").open("ab") as fh:
        fh.write(b'{"run_id": "' + RID.encode() + b'", "message_id": "torn-\xff\xfe"}\n')
    write_sha256sums(torn)
    records, skipped = pe._read_jsonl(torn / "sent_events.jsonl")
    assert len(records) == 4 and skipped == 1
    out_torn = tmp_path / "torn.json"
    assert _main(torn, out_torn, _session_file(tmp_path / "torn")) == 3
    doc = json.loads(out_torn.read_text(encoding="utf-8"))
    assert doc["instrumentation"]["skipped_lines"]["sent_events.jsonl"] == 1
    assert doc["system_outcome"]["result"] == "inconclusive" and doc["system_outcome"]["refutations"] == []
    eligibility = doc["instrumentation"]["proof_eligibility"]
    assert eligibility["eligible"] is False and eligibility["checks"]["population"]["records_of_this_run"] == 4
    assert any(r.startswith("population:") and "1 line(s) skipped" in r for r in eligibility["reasons"])
    assert any(r.startswith("not eligible (E-11): population:") for r in doc["system_outcome"]["inconclusive_reasons"])
    assert "Traceback" not in capsys.readouterr().err
    # controller_metrics.csv that does not decode: a read problem, named as
    # a failed fetch; S1 cannot be read; still exit 3, no traceback.
    bad_csv = _write_run_dir(tmp_path / "csv", seal=False)
    with (bad_csv / "controller_metrics.csv").open("ab") as fh:
        fh.write(b"\xff,,,,,,,,,,,,,,,,\n")
    write_sha256sums(bad_csv)
    out2 = tmp_path / "csv.json"
    assert _main(bad_csv, out2, _session_file(tmp_path / "csv")) == 3
    doc = json.loads(out2.read_text(encoding="utf-8"))
    assert any(p.startswith("controller_metrics.csv unreadable") for p in doc["instrumentation"]["read_problems"])
    assert any(f.startswith("controller_metrics.csv unreadable") for f in doc["instrumentation"]["proof_evidence"]["fetch_failures"])
    assert doc["system_outcome"]["criteria"]["S1"]["holds"] is None
    assert "Traceback" not in capsys.readouterr().err
    # The evaluator's own failure: exit 2 with the traceback on stderr, no
    # document written, never exit 1.
    def boom(artefacts, session):
        raise RuntimeError("an unexpected failure of the evaluator")

    monkeypatch.setattr(pe, "evaluate", boom)
    assert _main(run_dir, tmp_path / "crash.json", _session_file(tmp_path)) == 2
    err = capsys.readouterr().err
    assert "error: the proof was not evaluated: RuntimeError: an unexpected failure of the evaluator" in err
    assert "Traceback" in err and not (tmp_path / "crash.json").exists()


def test_a_present_but_unreadable_twin_snapshot_is_a_failed_fetch_with_a_stated_reason(tmp_path) -> None:
    """A snapshot the harness verified but that load_devices refuses at
    evaluation time (scenario D) is neither 'missing' nor a record failure:
    the loader's problem is fed to the evidence as a failed fetch, S5/R4 and
    the naming are null, and the reasons are never left empty. The problem
    names the file by its relative path, so the bytes do not depend on where
    the run directory sits."""
    run_dir = _write_run_dir(tmp_path, seal=False, lines=B_DUPLICATE)
    (run_dir / "twins.after.json").write_text(json.dumps({"label": "after", "seed": None, "devices": {"x": {}}}), "utf-8")
    write_sha256sums(run_dir)
    out = tmp_path / "verdict.json"
    assert _main(run_dir, out, _session_file(tmp_path)) == 3
    text = out.read_text(encoding="utf-8")
    assert str(tmp_path) not in text and str(run_dir) not in text
    doc = json.loads(text)
    outcome = doc["system_outcome"]
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
    assert doc["instrumentation"]["read_problems"] == ["twins.after.json: malformed entry for x"]
    assert doc["instrumentation"]["proof_evidence"]["complete"] is False
    assert "twins.after.json: malformed entry for x" in doc["instrumentation"]["proof_evidence"]["fetch_failures"]
    assert doc["instrumentation"]["proof_evidence"]["cannot_serve_the_criteria"] == {"twins.after.json": "twins.after.json: malformed entry for x"}
    assert outcome["inconclusive_reasons"] != []
    assert any(r.startswith("any fetch listed above fails") and "malformed entry for x" in r for r in outcome["inconclusive_reasons"])
    assert any(r.startswith("S4 cannot be shown (E-7)") for r in outcome["inconclusive_reasons"])
    assert any(r.startswith("S5 cannot be shown (E-7)") and "malformed entry for x" in r for r in outcome["inconclusive_reasons"])
    for rule_id in ("S4", "S5"):
        assert outcome["criteria"][rule_id]["holds"] is None, rule_id
    for rule_id in ("R3", "R4"):
        assert outcome["criteria"][rule_id]["observed"] is None, rule_id
    # In memory the same, and a CSV header that is not the sampler's is a
    # note, never a failed fetch (the CSV's completeness rule is a readable
    # pre-kill row).
    artefacts = _artefacts()
    artefacts.notes = ["controller_metrics.csv: the header is not the sampler's 17-column header; absent columns read as absent fields"]
    doc = pe.evaluate(artefacts, _session())
    assert _outcome(doc)["result"] == "supports" and doc["instrumentation"]["read_notes"] == artefacts.notes


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


def test_end_to_end_over_a_harness_built_run_dir(tmp_path, fast_run, monkeypatch, capsys) -> None:
    """The harness executes the proof's one-entry diagnostic plan (written
    by tools/session/proof_plan.py: controller_restart, nominal, 300 s at
    11.2 msg/s, no warm-up) with the fake simulator and the recorded item-18
    hooks; the loader then reads the sealed 1.4 layout it wrote and the
    run is eligible (E-11). Builder: _item18_run with the twin snapshot and
    post-drain hooks replaced by this module's copy scripts (the fixture's
    `write` mode carries neither identities nor a differing after
    snapshot), the sent lines and the simulator's own manifest rewritten by
    a wrapper of the fake simulator, and the controller /metrics poll
    stubbed in-process."""
    run_id = RID
    written, plan_path = _write_proof_plan(tmp_path, master_seed="42")
    assert written.returncode == 0, written.stderr
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
        # The simulator's own record of the publication (E-11): the load it
        # was given, its schedule completed, what it published.
        (out_dir / "manifest.json").write_text(
            json.dumps(_simulator_manifest(len(sent_lines), run_id=run_id), indent=2) + "\n", "utf-8"
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
    assert artefacts.simulator_manifest is not None and artefacts.simulator_manifest["totals"]["sent"] == 6
    assert pe.simulator_manifest_rel(run_id) in artefacts.files_present and "resources.csv" in artefacts.files_present
    assert (manifest["scenario"], manifest["duration_s"], manifest["rate_msg_s"], manifest["warmup_s"]) == ("nominal", 300, 11.2, 0)
    assert manifest["events_fetch"]["ok"] is True and manifest["resource_source"] == "sut-collector"

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
    eligibility = doc["instrumentation"]["proof_eligibility"]
    assert eligibility["eligible"] is True and eligibility["reasons"] == [] and eligibility["unknown"] == []
    assert eligibility["checks"]["publication"]["source"] == "the simulator's own manifest"
    assert eligibility["checks"]["publication"]["read"]["totals_sent"] == 6
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
    assert set(doc["sources"]) >= {"manifest.json", "controller_metrics.csv", "logs/sut/controller.log", "SHA256SUMS", "resources.csv", pe.simulator_manifest_rel(run_id)}
    assert json.loads(capsys.readouterr().out) == doc
