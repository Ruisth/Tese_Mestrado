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
the fault demonstrated at its instant, the harness copy and the collector
file in the inventory), the harness's validity admitted only as E-12 states
(the sampling-gap form built with run.py's and resources.py's own
functions, never a reason string written here), the N1 sources' capacity
across the run (E-10: an A5 occurrence serving its own device alone, a
recorded death at most one candidate of the whole run, each source only a
candidate whose redelivery it may have preceded on the controller clock,
a further controller process start a recorded death that names no kill
case only when it may have preceded a claimant's redelivery) and the
drain verified before R1; and, in the section after test 27k, round 4:
a naming stands only as every legitimate assignment of the sources reads
it and an aggregate R3 names no culprit (E-13, checked against an
enumeration of every matching), a death beside a controller process
whose readings carry no monotonic_ns is not placed (E-4), the harness's
exit in the session facts agrees with the admission (E-11), and a
further death serves a candidate the kill cannot explain whose
redelivery it may have preceded, while no death serves a candidate
lined before the kill (E-13, E-10, E-4; the read-only check of round 4).

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
import threading
import time
import types
from pathlib import Path
from typing import Any

import pytest

from egw_experiments import controller_metrics as metrics_mod
from egw_experiments import proof_evaluator as pe
from egw_experiments import resources as resources_mod
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
#: A third process, after a further death the plan did not prescribe.
P2 = "2026-09-25T10:04:50Z"
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


def _capacity(doc: dict) -> dict:
    """The E-10 figures of R4's evidence, without the rule text they carry
    and without the deaths as placed and each candidate's possible sources,
    which the cases on the order rule assert apart."""
    figures = dict(_criterion(doc, "R4")["evidence"]["source_capacity"])
    assert "own device alone" in figures.pop("rule") and "(E-10)" in _criterion(doc, "R4")["evidence"]["source_capacity"]["rule"]
    figures.pop("deaths")
    figures.pop("possible_sources")
    return figures


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
        "R4: 2 undecided device(s) whose twins need 2 N1 case(s) that only a death could serve (no A5 "
        "occurrence on their own device can), against 1 recorded death(s): a delta mismatch beyond the "
        "named cases stands on at least one of them, which cannot be told (E-10)"
    ]
    assert [(u["device_uuid"], u["rule"], u["message_ids"]) for u in r4["evidence"]["undecided"]] == [
        (D1, "E-4", ["b-mid"]), (D3, "E-8", ["g-mid"]),
    ]
    assert _capacity(doc) == {
        "applied": True, "known": True, "why_unknown": None, "deaths_recorded": 1, "post_kill_started_at": [P1],
        "kill_available": 1, "a5_possible_by_device": {D1: [], D3: []}, "needed_by_device": {D1: 1, D3: 1},
        "needed": 2, "beyond_a5_by_device": {D1: 1, D3: 1}, "kill_needed": 2, "consistent": False,
        "matched": 1, "deaths_preceding_none": [], "deaths_serving_none": [],
    }
    mismatches = r4["evidence"]["mismatches"]
    assert len(mismatches) == 1 and mismatches[0]["device_uuid"] is None and mismatches[0]["devices"] == [D1, D3]
    assert mismatches[0]["stands_on"] == [] and mismatches[0]["undecided_candidates"] == ["b-mid", "g-mid"]
    assert "no source-consistent naming explains the twins" in mismatches[0]["problems"][0]
    assert f"({D1}: 1, {D3}: 1), against 1 recorded death(s) available" in mismatches[0]["problems"][0]
    assert "cannot be told when more than one needs a death" in mismatches[0]["note"]
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
    capacity = _capacity(doc)
    assert (capacity["needed"], capacity["kill_needed"], capacity["kill_available"]) == (2, 2, 1)
    assert r4["evidence"]["mismatches"][0]["device_uuid"] == D1 and r4["evidence"]["mismatches"][0]["devices"] == [D1]
    assert r4["evidence"]["mismatches"][0]["stands_on"] == [D1]
    assert f"stands on {D1} by itself" in r4["evidence"]["mismatches"][0]["note"]
    assert r4["reason"] == (
        "1 undecided device(s) whose twins need 2 N1 case(s) that only a death could serve (no A5 "
        f"occurrence on their own device can), against 1 recorded death(s): a delta mismatch beyond the "
        f"named cases stands on {D1} whatever the death(s) served (E-10)"
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
    capacity = _capacity(doc)
    assert capacity["a5_possible_by_device"] == {D1: [], D3: []} and capacity["beyond_a5_by_device"] == {D1: 1, D3: 1}
    assert (capacity["needed"], capacity["kill_needed"], capacity["kill_available"]) == (2, 2, 1)
    assert _outcome(doc)["report"]["a5_occurrences"][0]["device_uuid"] == D3  # read, reported, not a source of G
    # G's line without a received stamp: the occurrence may be its source,
    # and D3 is then covered by its own occurrence, D1 by the death.
    unstamped = B_DUPLICATE + [("g-mid", D3, 1, "duplicate", None, None)]
    doc = _evaluate(sent=SENT + [G], lines=unstamped, extra_after=twins, controller_log=[_a5_line(D3, in_band + NS)])
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == [] and _outcome(doc)["n1_cases"] == []
    capacity = _capacity(doc)
    assert capacity["a5_possible_by_device"] == {D1: [], D3: [1]} and capacity["beyond_a5_by_device"] == {D1: 1, D3: 0}
    assert (capacity["needed"], capacity["kill_needed"], capacity["kill_available"]) == (2, 1, 1)
    assert capacity["consistent"] is True and _criterion(doc, "R4")["observed"] is None
    for row in _criterion(doc, "R4")["evidence"]["devices"]:
        if row["device_uuid"] in (D1, D3):
            assert row["undecided"]["source_consistent"] is True, row["device_uuid"]
    # A single uncertain candidate against the one death: consistent, unshown.
    doc = _evaluate(lines=[line for line in LINES if line[0] != "b-mid"] + [("b-mid", D1, 1, "duplicate", in_band, None)], extra_after={D1: 1, "seqs": [(D1, 1)]})
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert _capacity(doc) == {
        "applied": True, "known": True, "why_unknown": None, "deaths_recorded": 1, "post_kill_started_at": [P1],
        "kill_available": 1, "a5_possible_by_device": {D1: []}, "needed_by_device": {D1: 1}, "needed": 1,
        "beyond_a5_by_device": {D1: 1}, "kill_needed": 1, "consistent": True, "matched": 1,
        "deaths_preceding_none": [], "deaths_serving_none": [],
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


def test_an_a5_occurrence_serves_its_own_device_alone_and_a_death_at_most_one_candidate_of_the_run() -> None:
    """E-10, the independent review of 2026-09-25 (P1): the capacity is
    read per device, never as one sum over the run. D1 needs two cases (B
    claims the kill beside F in the band: E-4, E-8) and D3 one (G's line
    carries no received stamp: E-8), with two A5 occurrences on D3: D3 is
    covered by its own occurrences, but nothing serves D1's second case,
    so the mismatch stands on D1 by itself and the run refutes, where the
    sum (one kill plus two occurrences against three needed) read the
    twins as consistent. With D1 needing one (B alone beside G) the one
    death serves D1 and an occurrence D3: consistent, inconclusive. An
    occurrence that cannot serve G lends nothing to D1 either."""
    in_band = (K_LOWER + K_UPPER) // 2
    F = ("f-mid", D1, 2, 401 * NS)
    G = ("g-mid", D3, 1, 380 * NS)
    two_on_d3 = [_a5_line(D3, in_band + NS), _a5_line(D3, in_band + 2 * NS)]
    lines = B_DUPLICATE + [("f-mid", D1, 2, "duplicate", in_band, None), ("g-mid", D3, 1, "duplicate", None, None)]
    twins = {D1: 2, D3: 1, "seqs": [(D1, 2), (D3, 1)]}
    doc = _evaluate(sent=SENT + [F, G], lines=lines, extra_after=twins, controller_log=two_on_d3)
    outcome = _outcome(doc)
    assert outcome["result"] == "refutes" and outcome["n1_cases"] == []
    assert outcome["refutations"] == [
        "R4: 1 undecided device(s) whose twins need 2 N1 case(s) that only a death could serve (no A5 "
        f"occurrence on their own device can), against 1 recorded death(s): a delta mismatch beyond the "
        f"named cases stands on {D1} whatever the death(s) served (E-10)"
    ]
    capacity = _capacity(doc)
    assert capacity["a5_possible_by_device"] == {D1: [], D3: [1, 2]} and capacity["needed_by_device"] == {D1: 2, D3: 1}
    assert capacity["beyond_a5_by_device"] == {D1: 2, D3: 0} and capacity["needed"] == 3
    assert (capacity["kill_needed"], capacity["kill_available"], capacity["consistent"]) == (2, 1, False)
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True and _criterion(doc, "S5")["holds"] is False
    mismatch = r4["evidence"]["mismatches"][0]
    assert mismatch["device_uuid"] == D1 and mismatch["devices"] == [D1] and mismatch["stands_on"] == [D1]
    assert mismatch["undecided_candidates"] == ["b-mid", "f-mid"]
    assert f"({D1}: 2), against 1 recorded death(s) available" in mismatch["problems"][0]
    assert "no A5 occurrence on their own device can serve" in mismatch["problems"][0]
    assert f"stands on {D1} by itself" in mismatch["note"] and "no identity is named as the case" in mismatch["note"]
    rows = {row["device_uuid"]: row for row in r4["evidence"]["devices"]}
    assert rows[D1]["undecided"]["source_consistent"] is False and rows[D3]["undecided"]["source_consistent"] is True
    assert rows[D1]["ok"] is None and rows[D3]["ok"] is None
    assert _criterion(doc, "S4")["holds"] is None and _criterion(doc, "R3")["observed"] is None
    # D1 needing one: the death serves it and an occurrence serves D3.
    lines = B_DUPLICATE + [("g-mid", D3, 1, "duplicate", None, None)]
    doc = _evaluate(sent=SENT + [G], lines=lines, extra_after={D1: 1, D3: 1, "seqs": [(D1, 1), (D3, 1)]}, controller_log=two_on_d3)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    capacity = _capacity(doc)
    assert capacity["beyond_a5_by_device"] == {D1: 1, D3: 0} and (capacity["kill_needed"], capacity["kill_available"]) == (1, 1)
    assert capacity["consistent"] is True and _criterion(doc, "R4")["observed"] is None
    for row in _criterion(doc, "R4")["evidence"]["devices"]:
        if row["device_uuid"] in (D1, D3):
            assert row["undecided"]["source_consistent"] is True, row["device_uuid"]
    # An occurrence received after G's redelivery serves no one: D1 (two
    # beyond its occurrences) is the mismatch by itself, D3 competes for
    # the death with it.
    lines = B_DUPLICATE + [("f-mid", D1, 2, "duplicate", in_band, None), ("g-mid", D3, 1, "duplicate", in_band, None)]
    doc = _evaluate(sent=SENT + [F, G], lines=lines, extra_after=twins, controller_log=[_a5_line(D3, in_band + NS)])
    assert _outcome(doc)["result"] == "refutes"
    capacity = _capacity(doc)
    assert capacity["a5_possible_by_device"] == {D1: [], D3: []} and capacity["beyond_a5_by_device"] == {D1: 2, D3: 1}
    assert (capacity["kill_needed"], capacity["kill_available"]) == (3, 1)
    mismatch = _criterion(doc, "R4")["evidence"]["mismatches"][0]
    assert mismatch["devices"] == [D1, D3] and mismatch["stands_on"] == [D1] and mismatch["device_uuid"] == D1
    assert f"stands on {D1} whatever the death(s) served (E-10)" in _criterion(doc, "R4")["reason"]
    assert "of its own device alone" in pe.IDENTIFICATION_RULES["E-10"]
    assert "the mismatch by itself" in pe.IDENTIFICATION_RULES["E-10"]


def test_a_further_controller_process_start_is_a_recorded_death_that_counts_to_the_capacity_and_names_no_kill_case() -> None:
    """E-10 and E-4, the independent review of 2026-09-25 (P2), read with
    the order rule of the joint check (F3): the readings record a third
    started_at after the restart's process, a second death the plan did
    not prescribe, placed on the controller clock between P1's last
    reading (K_UPPER + 65 s) and P2's first (K_UPPER + 85 s). B, its only
    duplicate line received after that death (K_UPPER + 90 s), claims the
    kill beside F in the band, and D1 needs two cases: the kill may have
    preceded both redeliveries and the further death B's, so a
    source-consistent naming exists (one per death) and the run is
    inconclusive with the starts named, never R4 against a capacity of
    one that the run's own readings contradict. Needing three refutes
    still. A lone claimant redelivered after the further death is neither
    named nor R3 (which death it was in progress at cannot be told, and
    P-4 names the command's kill alone), with E-4 as the label of what
    leaves it unshown, never E-7; two claimants redelivered after it are
    unshown under two deaths, which cover both. This case's earlier
    expectations used a lone claimant, and two claimants, redelivered
    BEFORE the further death (at 1,200 s and 1,210 s) and expected
    'inconclusive' and 'unshown under two': they encoded the wrong rule,
    since a death wholly after a redelivery cannot be its source (the
    joint check's 7c and 7d; the next test pins those cases)."""
    rows = _rows_with_a_further_death()
    in_band = (K_LOWER + K_UPPER) // 2
    F = ("f-mid", D1, 2, 401 * NS)
    late_b = ("b-mid", D1, 1, "duplicate", K_UPPER + 90 * NS, None)
    lines = [line for line in LINES if line[0] != "b-mid"] + [late_b, ("f-mid", D1, 2, "duplicate", in_band, None)]
    doc = _evaluate(sent=SENT + [F], lines=lines, extra_after={D1: 2, "seqs": [(D1, 2)]}, rows=rows)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == [] and outcome["n1_cases"] == []
    assert outcome["report"]["processes"]["post_kill_started_at"] == [P1, P2]
    capacity = _capacity(doc)
    assert capacity["deaths_recorded"] == 2 and capacity["post_kill_started_at"] == [P1, P2]
    assert (capacity["kill_needed"], capacity["kill_available"], capacity["consistent"]) == (2, 2, True)
    r3 = _criterion(doc, "R3")
    shown = {c["message_id"]: c["why_not_shown"] for c in r3["evidence"]["cannot_show_identities"]}
    assert list(shown) == ["b-mid", "f-mid"]
    assert f"2 controller process starts after the pre-kill one ({P1}, {P2})" in shown["b-mid"] and "(E-4)" in shown["b-mid"]
    assert "never named as a source (P-4)" in shown["b-mid"]
    assert f"a further death may have preceded its redelivered duplicate line (received at {K_UPPER + 90 * NS})" in shown["b-mid"]
    assert f"death 1 between the last reading of process {P1} (monotonic_ns {K_UPPER + 65 * NS}) and the first reading of process {P2} ({K_UPPER + 85 * NS})" in shown["b-mid"]
    assert any("a further death is recorded that P-4 never names" in n and "(E-10)" in n for n in r3["evidence"]["notes"])
    evidence = _criterion(doc, "R4")["evidence"]["source_capacity"]
    assert evidence["possible_sources"] == {"b-mid": {"a5_lines": [], "deaths": [0, 1]}, "f-mid": {"a5_lines": [], "deaths": [0]}}
    assert [(d["death"], d["kind"], d["placed"], d["may_precede"]) for d in evidence["deaths"]] == [
        (0, "kill", True, ["b-mid", "f-mid"]), (1, "further", True, ["b-mid"]),
    ]
    assert _capacity(doc)["matched"] == 2 and _capacity(doc)["deaths_preceding_none"] == []
    assert r3["observed"] is None and _criterion(doc, "S4")["holds"] is None
    assert _criterion(doc, "R4")["observed"] is None and _criterion(doc, "S5")["holds"] is None
    row = next(row for row in _criterion(doc, "R4")["evidence"]["devices"] if row["device_uuid"] == D1)
    assert row["undecided"]["source_consistent"] is True and row["undecided"]["message_ids"] == ["b-mid", "f-mid"]
    # Needing three against the two recorded deaths: R4 on D1 by itself.
    F2 = ("f2-mid", D1, 3, 402 * NS)
    doc = _evaluate(sent=SENT + [F, F2], lines=lines + [("f2-mid", D1, 3, "duplicate", in_band, None)], extra_after={D1: 3, "seqs": [(D1, 3)]}, rows=rows)
    assert _outcome(doc)["result"] == "refutes" and _outcome(doc)["n1_cases"] == []
    capacity = _capacity(doc)
    assert (capacity["kill_needed"], capacity["kill_available"], capacity["consistent"]) == (3, 2, False)
    assert _criterion(doc, "R4")["evidence"]["mismatches"][0]["stands_on"] == [D1]
    assert "against 2 recorded death(s)" in _criterion(doc, "R4")["reason"]
    # A lone claimant redelivered after the further death: unshown, not the
    # kill's named case (which it is under one death, test 16). What leaves
    # it unshown was read, so the label is E-4, never E-7.
    late_alone = [line for line in LINES if line[0] != "b-mid"] + [late_b]
    doc = _evaluate(lines=late_alone, extra_after={D1: 1, "seqs": [(D1, 1)]}, rows=rows)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["n1_cases"] == [] and _outcome(doc)["refutations"] == []
    shown = {c["message_id"]: c["why_not_shown"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]}
    assert list(shown) == ["b-mid"] and "further death, which is never named as a source (P-4)" in shown["b-mid"]
    assert _criterion(doc, "S4")["holds"] is None and _criterion(doc, "R3")["observed"] is None
    assert _capacity(doc)["kill_available"] == 2 and _criterion(doc, "R4")["observed"] is None
    assert [u["rule"] for u in _criterion(doc, "R4")["evidence"]["undecided"]] == ["E-4"]
    unshown = [r for r in _outcome(doc)["inconclusive_reasons"] if " cannot be shown (" in r]
    assert unshown and all(r.startswith(("S4 cannot be shown (E-4)", "S5 cannot be shown (E-4)", "S4, S5 cannot be shown (E-4)")) for r in unshown), unshown
    assert not any("(E-7)" in r.split(":")[0] for r in _outcome(doc)["inconclusive_reasons"])
    # Two claimants redelivered after the further death (test 22e's, each
    # R3 under one death): unshown under two, which cover both.
    G = ("g-mid", D3, 1, 380 * NS)
    late_g = ("g-mid", D3, 1, "duplicate", K_UPPER + 92 * NS, None)
    doc = _evaluate(sent=SENT + [G], lines=late_alone + [late_g], extra_after={D1: 1, D3: 1, "seqs": [(D1, 1), (D3, 1)]}, rows=rows)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    r3 = _criterion(doc, "R3")
    assert r3["evidence"]["not_named_identities"] == []
    assert [c["message_id"] for c in r3["evidence"]["cannot_show_identities"]] == ["b-mid", "g-mid"]
    assert all("2 identities claim the kill" in c["why_not_shown"] and "(E-4)" in c["why_not_shown"] for c in r3["evidence"]["cannot_show_identities"])
    assert all("a further death having possibly preceded the redelivery of b-mid, g-mid" in c["why_not_shown"] for c in r3["evidence"]["cannot_show_identities"])
    assert any("2 duplicate-only identities claim the kill" in n for n in r3["evidence"]["notes"])
    capacity = _capacity(doc)
    assert (capacity["kill_needed"], capacity["kill_available"], capacity["consistent"]) == (2, 2, True)
    assert "recorded death" in pe.IDENTIFICATION_RULES["E-10"] and "further death" in pe.IDENTIFICATION_RULES["E-4"]


def _rows_with_a_further_death() -> list[dict[str, str]]:
    """The scenario's readings and a third process, P2, first read at
    K_UPPER + 85 s: a further death placed between P1's last reading
    (K_UPPER + 65 s) and P2's first."""
    return _rows() + [
        _row(_ts(290), P2, 0, 0, monotonic_ns=K_UPPER + 85 * NS, unacked=0),
        _row(_ts(295), P2, 0, 0, monotonic_ns=K_UPPER + 95 * NS, unacked=0),
    ]


def test_a_further_death_wholly_after_every_redelivery_explains_nothing_and_turns_no_result() -> None:
    """The joint check of 2026-09-25 (F3, P1), cases 7a-7d: a death can be
    the source of a candidate only if it may have preceded that
    candidate's redelivered duplicate line on the controller clock. A
    crash of the new process late in the publication, after every
    redelivery (P2 first read at K_UPPER + 85 s, P1 last read at K_UPPER +
    65 s), explains nothing: case (1)'s R4 (surplus 2 on D1, one death that
    may precede) stands on D1 by itself, case (2)'s R4 (one on each of D1
    and D3) on the aggregate, two claimants of the kill stay R3 with R4
    beside them, and a lone claimant redelivered before the late death is
    named with the kill as its source and supports. Before this rule each
    of them read 'inconclusive'."""
    rows = _rows_with_a_further_death()
    in_band = (K_LOWER + K_UPPER) // 2
    F = ("f-mid", D1, 2, 401 * NS)
    G = ("g-mid", D3, 1, 380 * NS)
    # 7a: case (1), B and F in the band on D1, surplus 2, no A5.
    lines_bf = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "duplicate", in_band, None), ("f-mid", D1, 2, "duplicate", in_band, None),
    ]
    for label, readings in (("one death", None), ("a late further death", rows)):
        doc = _evaluate(sent=SENT + [F], lines=lines_bf, extra_after={D1: 2, "seqs": [(D1, 2)]}, rows=readings)
        assert _outcome(doc)["result"] == "refutes", label
        mismatch = _criterion(doc, "R4")["evidence"]["mismatches"][0]
        assert mismatch["stands_on"] == [D1] and mismatch["device_uuid"] == D1, label
        assert _criterion(doc, "S4")["holds"] is None and _criterion(doc, "R3")["observed"] is None, label
    capacity = _capacity(doc)
    assert (capacity["deaths_recorded"], capacity["kill_available"], capacity["kill_needed"]) == (2, 2, 2)
    assert (capacity["matched"], capacity["consistent"], capacity["deaths_preceding_none"]) == (1, False, [1])
    evidence = _criterion(doc, "R4")["evidence"]["source_capacity"]
    assert evidence["possible_sources"] == {"b-mid": {"a5_lines": [], "deaths": [0]}, "f-mid": {"a5_lines": [], "deaths": [0]}}
    assert evidence["deaths"][1]["may_precede"] == [] and evidence["deaths"][1]["after_monotonic_ns"] == K_UPPER + 65 * NS
    assert _outcome(doc)["refutations"] == [
        "R4: 1 undecided device(s) whose twins need 2 N1 case(s) that only a death could serve (no A5 occurrence "
        "on their own device can), against 2 recorded death(s), 1 of which may have preceded none of their "
        f"redeliveries: a delta mismatch beyond the named cases stands on {D1} whatever the death(s) served (E-10)"
    ]
    assert "1 of which may have preceded none of their redelivered duplicate lines" in mismatch["problems"][0]
    notes = _criterion(doc, "R3")["evidence"]["notes"]
    assert any(n.startswith("further death(s) 1 may have preceded no duplicate-only candidate's") and "explain nothing" in n for n in notes)
    # 7b: case (2), B on D1 and G on D3 in the band: R4 on the aggregate.
    lines_bg = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "duplicate", in_band, None), ("g-mid", D3, 1, "duplicate", in_band, None),
    ]
    doc = _evaluate(sent=SENT + [G], lines=lines_bg, extra_after={D1: 1, D3: 1, "seqs": [(D1, 1), (D3, 1)]}, rows=rows)
    assert _outcome(doc)["result"] == "refutes"
    mismatch = _criterion(doc, "R4")["evidence"]["mismatches"][0]
    assert mismatch["device_uuid"] is None and mismatch["devices"] == [D1, D3] and mismatch["stands_on"] == []
    assert (_capacity(doc)["matched"], _capacity(doc)["deaths_preceding_none"]) == (1, [1])
    # 7c: two claimants of the kill, redelivered at 1,200 s and 1,210 s,
    # both before the late death: R3 on each and R4 beside, as under one.
    lines_2cl = B_DUPLICATE + [("g-mid", D3, 1, "duplicate", 1_210 * NS, None)]
    doc = _evaluate(sent=SENT + [G], lines=lines_2cl, extra_after={D1: 1, D3: 1, "seqs": [(D1, 1), (D3, 1)]}, rows=rows)
    assert _outcome(doc)["result"] == "refutes"
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is True and _criterion(doc, "R4")["observed"] is True
    assert [c["message_id"] for c in r3["evidence"]["not_named_identities"]] == ["b-mid", "g-mid"]
    assert all("follow every claimant's redelivered duplicate line" in c["why_not_named"] for c in r3["evidence"]["not_named_identities"])
    assert r3["evidence"]["cannot_show_identities"] == []
    assert [u["device_uuid"] for u in _criterion(doc, "R4")["evidence"]["surplus_unexplained"]] == [D1, D3]
    # 7d: a lone claimant redelivered before the late death: named, supports.
    doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 1, "seqs": [(D1, 1)]}, rows=rows)
    assert _outcome(doc)["result"] == "supports" and _outcome(doc)["inconclusive_reasons"] == []
    case = _outcome(doc)["n1_cases"][0]
    assert (case["message_id"], case["source"]) == ("b-mid", "kill")
    assert f"its redelivered duplicate line (received at {1_200 * NS}) precedes every further death recorded" in case["source_evidence"]["further_deaths_after_its_redelivery"]
    assert _criterion(doc, "R4")["evidence"]["source_capacity"]["kill_available"] == 1
    sources = _criterion(doc, "R4")["evidence"]["source_capacity"]
    assert sources["deaths_recorded"] == 2
    assert "wholly after" in pe.IDENTIFICATION_RULES["E-4"] and "explains nothing" in pe.IDENTIFICATION_RULES["E-4"]
    assert "matching" in pe.IDENTIFICATION_RULES["E-10"] and "may have preceded" in pe.IDENTIFICATION_RULES["E-10"]


def test_a_death_the_readings_cannot_place_may_precede_any_redelivery() -> None:
    """E-4's placement fails closed: a further death whose readings
    contradict its interval (the dying process read again after the next
    process's first reading) or without a readable lower bound may have
    preceded any redelivery, so it is never read as wholly after one and
    no refutation rests on it; case (1) is then inconclusive. With no
    post-kill process recorded, the manifest's kill is the one death,
    placed after the last pre-kill reading; a tie with that reading is
    read inclusively, as the band of E-8 is."""
    in_band = (K_LOWER + K_UPPER) // 2
    F = ("f-mid", D1, 2, 401 * NS)
    lines_bf = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "duplicate", in_band, None), ("f-mid", D1, 2, "duplicate", in_band, None),
    ]
    blip = _rows()
    blip.insert(8, _row(_ts(200), "2026-09-25T10:03:20Z", 0, 0, monotonic_ns=K_UPPER + 20 * NS, unacked=0))
    doc = _evaluate(sent=SENT + [F], lines=lines_bf, extra_after={D1: 2, "seqs": [(D1, 2)]}, rows=blip)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    deaths = _criterion(doc, "R4")["evidence"]["source_capacity"]["deaths"]
    assert deaths[1]["placed"] is False and "which the readings contradict" in deaths[1]["placement"]
    assert deaths[1]["may_precede"] == ["b-mid", "f-mid"] and _capacity(doc)["consistent"] is True
    # The readings as a Death sees them.
    rows, _notes = pe.read_metrics_rows(_rows())
    split = pe.split_by_process(rows)
    (kill,) = pe.recorded_deaths(split, restart_ok=True)
    assert (kill.index, kill.dying_started_at, kill.next_started_at, kill.after, kill.before) == (0, P0, P1, K_LOWER, K_UPPER)
    assert kill.may_precede(K_LOWER) and kill.may_precede(K_LOWER + 1) and not kill.may_precede(K_LOWER - 1)
    assert kill.may_precede(None)
    pre_only = pe.split_by_process([r for r in rows if r.started_at == P0])
    (alone,) = pe.recorded_deaths(pre_only, restart_ok=True)
    assert (alone.after, alone.before, alone.next_started_at, alone.placed) == (K_LOWER, None, None, True)
    assert pe.recorded_deaths(pre_only, restart_ok=False) == []
    unplaced = pe.Death(1, P1, P2, None, K_UPPER)
    assert not unplaced.placed and unplaced.may_precede(0) and "not placed on the controller clock" in unplaced.placement()


def test_an_a5_occurrence_serves_only_a_candidate_whose_redelivery_it_may_precede() -> None:
    """E-10's matching applies P-4's order rule to an A5 occurrence as to a
    death (the joint check's note on over-counting within one device): D1
    needs three cases - B and F redelivered in the band, X without a
    received stamp - with one death and two occurrences on D1 whose
    in-progress deliveries were received after B's and F's redeliveries.
    The occurrences may serve X alone, and at most one of them does, so
    B and F need the one death: R4 stands on D1. Before, the device-wide
    count read the two occurrences against the three cases and found the
    twins consistent. With X's line stamped after both occurrences the
    later one names X (P-4: the unused occurrence received last before
    its redelivery; this docstring said the first, the rule before the
    check of 2026-09-25 on E-10) and the run refutes all the same: X
    keeps a source in the matching, and neither occurrence may precede
    B's or F's redelivery."""
    in_band = (K_LOWER + K_UPPER) // 2
    F = ("f-mid", D1, 2, 401 * NS)
    X = ("x-mid", D1, 3, 402 * NS)
    lines = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "duplicate", in_band, None),
        ("f-mid", D1, 2, "duplicate", in_band, None),
        ("x-mid", D1, 3, "duplicate", None, None),
    ]
    log = [_a5_line(D1, K_UPPER + 30 * NS), _a5_line(D1, K_UPPER + 40 * NS)]
    doc = _evaluate(sent=SENT + [F, X], lines=lines, extra_after={D1: 3, "seqs": [(D1, 3)]}, controller_log=log)
    assert _outcome(doc)["result"] == "refutes" and _outcome(doc)["n1_cases"] == []
    capacity = _capacity(doc)
    assert capacity["a5_possible_by_device"] == {D1: [1, 2]} and capacity["needed_by_device"] == {D1: 3}
    assert (capacity["beyond_a5_by_device"], capacity["kill_needed"], capacity["kill_available"]) == ({D1: 2}, 2, 1)
    assert (capacity["matched"], capacity["consistent"]) == (2, False)
    possible = _criterion(doc, "R4")["evidence"]["source_capacity"]["possible_sources"]
    assert possible == {
        "b-mid": {"a5_lines": [], "deaths": [0]},
        "f-mid": {"a5_lines": [], "deaths": [0]},
        "x-mid": {"a5_lines": [1, 2], "deaths": [0]},
    }
    assert _criterion(doc, "R4")["evidence"]["mismatches"][0]["stands_on"] == [D1]
    # X stamped after both occurrences: the later one names it (P-4), and
    # B and F, redelivered before both, still need the one death.
    stamped = lines[:-1] + [("x-mid", D1, 3, "duplicate", K_UPPER + 50 * NS, None)]
    doc = _evaluate(sent=SENT + [F, X], lines=stamped, extra_after={D1: 3, "seqs": [(D1, 3)]}, controller_log=log)
    assert _outcome(doc)["result"] == "refutes"
    assert [(c["message_id"], c["source"]) for c in _outcome(doc)["n1_cases"]] == [("x-mid", "a3-connection-end")]
    assert (_capacity(doc)["needed_by_device"], _capacity(doc)["matched"]) == ({D1: 2}, 1)
    assert _outcome(doc)["n1_cases"][0]["source_evidence"]["controller_log_line"] == 2
    assert _criterion(doc, "R4")["evidence"]["source_capacity"]["possible_sources"]["x-mid"] == {
        "a5_lines": [1, 2], "deaths": [0], "named": {"source": "a3-connection-end", "controller_log_line": 2},
    }


def test_the_occurrences_name_as_many_candidates_as_their_order_allows_whatever_the_order_of_the_log_lines() -> None:
    """The check of 2026-09-25 on E-10 (P2): P-4 gave each candidate the
    EARLIEST unused A5 occurrence before its redelivery, and E-10's
    matching left the named cases out. D1: B (seq 1) redelivered at
    1,300 s and Y (seq 2, published at 510 s inside the restart command's
    window, E-8) at 1,250 s; two occurrences on D1 received at 1,190 s and
    1,290 s; D3: G in the kill band. Twins: D1 surplus 2, D3 surplus 1.
    With the log in its chronological order B took the 1,190 s occurrence,
    Y found none before it and needed the one death beside G: R4 against
    one death, although B <- 1,290 s, Y <- 1,190 s and G <- the kill is
    source-consistent; with the two lines swapped the same facts read
    inconclusive. Each candidate now takes the unused occurrence received
    last before its redelivery: B and Y are named in either order, with
    the same occurrences, and G alone needs the death."""
    in_band = (K_LOWER + K_UPPER) // 2
    Y = ("y-mid", D1, 2, 510 * NS)
    G = ("g-mid", D3, 1, 380 * NS)
    lines = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "duplicate", 1_300 * NS, None),
        ("y-mid", D1, 2, "duplicate", 1_250 * NS, None),
        ("g-mid", D3, 1, "duplicate", in_band, None),
    ]
    twins = {D1: 2, D3: 1, "seqs": [(D1, 2), (D3, 1)]}
    chronological = [_a5_line(D1, 1_190 * NS), _a5_line(D1, 1_290 * NS)]
    results = []
    for log in (chronological, list(reversed(chronological))):
        doc = _evaluate(sent=SENT + [Y, G], lines=lines, extra_after=twins, controller_log=log)
        outcome = _outcome(doc)
        assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
        cases = {c["message_id"]: c for c in outcome["n1_cases"]}
        assert sorted(cases) == ["b-mid", "y-mid"] and {c["source"] for c in cases.values()} == {"a3-connection-end"}
        received = {m: c["source_evidence"]["identity"]["received_monotonic_ns"] for m, c in cases.items()}
        assert received == {"b-mid": 1_290 * NS, "y-mid": 1_190 * NS}
        r4 = _criterion(doc, "R4")
        assert r4["observed"] is None and r4["evidence"]["mismatches"] == []
        assert [(u["device_uuid"], u["rule"], u["message_ids"]) for u in r4["evidence"]["undecided"]] == [(D3, "E-8", ["g-mid"])]
        capacity = _capacity(doc)
        assert (capacity["needed_by_device"], capacity["kill_needed"], capacity["kill_available"]) == ({D3: 1}, 1, 1)
        assert (capacity["matched"], capacity["consistent"]) == (1, True)
        assert _criterion(doc, "R3")["evidence"]["not_named_identities"] == []
        assert _criterion(doc, "R3")["observed"] is None and _criterion(doc, "S4")["holds"] is None
        results.append((outcome["result"], sorted(received.items()), capacity))
    assert results[0] == results[1]
    assert "received last before its redelivered duplicate line" in pe.IDENTIFICATION_RULES["P-4"]
    assert "whatever the order of the log lines" in pe.IDENTIFICATION_RULES["P-4"]


def test_a_case_named_with_an_occurrence_may_leave_it_to_an_undecided_candidate_and_take_a_death() -> None:
    """The same check (E-10): which of a device's occurrences served which
    of its cases is inference, so a case named with an occurrence takes
    part in the matching. D1: B (restart-class, published before the kill)
    redelivered at 1,300 s and Y (published inside the restart command's
    window, E-8) at 1,230 s; one occurrence on D1 received at 1,190 s,
    which precedes both and names B (P-4); a further death placed between
    1,245 s and 1,265 s may precede B's redelivery but not Y's; D3: G in
    the kill band. With B left out of the matching, Y and G each needed
    the kill and R4 was observed against it, although B <- the further
    death, Y <- the occurrence and G <- the kill is source-consistent. B
    now keeps a source in the matching and the run is inconclusive. A B
    that the kill cannot explain (published after the restart command's
    end) may still have been in progress at the further death, which
    serves it: the same assignment holds and nothing is refuted. Only
    redelivered before the further death (1,240 s) is the occurrence its
    one source, and R4 then stands on the aggregate.

    Corrected in round 4 (E-13): this case also expected B NAMED with the
    occurrence, the naming the candidates' order gave it. The only
    legitimate assignment (G <- the kill, Y <- the occurrence, B <- the
    further death, all three served) gives the occurrence to Y, so no
    legitimate assignment bears that naming out: B is unshown, its source
    a further death P-4 never names. That expectation encoded the wrong
    rule.

    Corrected after the read-only check of round 4 (E-13, E-10): the
    second half expected B, published after the restart command's end and
    redelivered at 1,300 s, to have no death as its source, although the
    further death may have preceded that redelivery, and the run to refute
    (R4 against deaths said to precede none of the redeliveries). E-13
    lists a further death among the sources of a candidate whose
    redelivery it may have preceded, whether or not the kill can explain
    it: that expectation encoded the wrong rule. B is now unshown with the
    further death as its source and the run inconclusive; the refutation
    is kept for B redelivered at 1,240 s, before the further death, where
    the occurrence is its one source (named in some legitimate assignments
    and without a source in others)."""
    rows = _rows_with_a_further_death()
    in_band = (K_LOWER + K_UPPER) // 2
    Y = ("y-mid", D1, 2, 510 * NS)
    G = ("g-mid", D3, 1, 380 * NS)
    lines = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "duplicate", 1_300 * NS, None),
        ("y-mid", D1, 2, "duplicate", 1_230 * NS, None),
        ("g-mid", D3, 1, "duplicate", in_band, None),
    ]
    twins = {D1: 2, D3: 1, "seqs": [(D1, 2), (D3, 1)]}
    log = [_a5_line(D1, 1_190 * NS)]
    doc = _evaluate(sent=SENT + [Y, G], lines=lines, extra_after=twins, controller_log=log, rows=rows)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
    assert outcome["n1_cases"] == []
    shown = {c["message_id"]: c["why_not_shown"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]}
    assert sorted(shown) == ["b-mid", "g-mid", "y-mid"]
    assert "every legitimate assignment" in shown["b-mid"] and "(E-13)" in shown["b-mid"]
    assert "in progress at a further death (death 1), which P-4 never names as a source" in shown["b-mid"]
    assert _criterion(doc, "R3")["evidence"]["assignments"]["may_be"]["b-mid"] == ["further-death"]
    assert _criterion(doc, "R3")["evidence"]["assignments"]["not_borne_out"] == ["b-mid"]
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is None and r4["evidence"]["mismatches"] == []
    capacity = _capacity(doc)
    assert (capacity["needed_by_device"], capacity["beyond_a5_by_device"]) == ({D1: 2, D3: 1}, {D1: 1, D3: 1})
    assert (capacity["kill_needed"], capacity["kill_available"], capacity["matched"], capacity["consistent"]) == (2, 2, 3, True)
    assert r4["evidence"]["source_capacity"]["possible_sources"] == {
        "b-mid": {"a5_lines": [1], "deaths": [0, 1]},
        "y-mid": {"a5_lines": [1], "deaths": [0]},
        "g-mid": {"a5_lines": [], "deaths": [0]},
    }
    rows_by_device = {row["device_uuid"]: row for row in r4["evidence"]["devices"]}
    assert rows_by_device[D1]["undecided"]["source_consistent"] is True and rows_by_device[D3]["undecided"]["source_consistent"] is True
    assert "keeping one" in pe.IDENTIFICATION_RULES["E-10"] and "beside the cases named with an occurrence" in pe.IDENTIFICATION_RULES["E-10"]
    # B published after the restart command's end, so the kill cannot
    # explain it, and redelivered at 1,300 s, after the further death, at
    # which it may have been in progress: the further death serves it, and
    # the one legitimate assignment is the one above (E-13, E-10).
    late_b = [sent if sent[0] != "b-mid" else ("b-mid", D1, 1, 530 * NS) for sent in SENT]
    doc = _evaluate(sent=late_b + [Y, G], lines=lines, extra_after=twins, controller_log=log, rows=rows)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == [] and outcome["n1_cases"] == []
    shown = {c["message_id"]: c["why_not_shown"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]}
    assert sorted(shown) == ["b-mid", "g-mid", "y-mid"]
    assert "every legitimate assignment" in shown["b-mid"] and "(E-13)" in shown["b-mid"]
    assert "in progress at a further death (death 1), which P-4 never names as a source" in shown["b-mid"]
    assert _criterion(doc, "R3")["evidence"]["assignments"]["may_be"]["b-mid"] == ["further-death"]
    assert _criterion(doc, "R3")["observed"] is None and _criterion(doc, "R3")["evidence"]["r3_groups"] == []
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is None and r4["evidence"]["mismatches"] == []
    assert r4["evidence"]["source_capacity"]["possible_sources"]["b-mid"] == {"a5_lines": [1], "deaths": [1]}
    capacity = _capacity(doc)
    assert (capacity["kill_needed"], capacity["kill_available"], capacity["matched"], capacity["consistent"]) == (2, 2, 3, True)
    deaths = r4["evidence"]["source_capacity"]["deaths"]
    assert [(d["death"], d["may_serve"]) for d in deaths] == [(0, ["g-mid", "y-mid"]), (1, ["b-mid"])]
    # The same B redelivered at 1,240 s, before the further death: the
    # occurrence is its only source, and Y and G still need the one death
    # that may precede them (the further death follows all three
    # redeliveries).
    early_b = [line if line[0] != "b-mid" else ("b-mid", D1, 1, "duplicate", 1_240 * NS, None) for line in lines]
    doc = _evaluate(sent=late_b + [Y, G], lines=early_b, extra_after=twins, controller_log=log, rows=rows)
    outcome = _outcome(doc)
    assert outcome["result"] == "refutes" and outcome["n1_cases"] == []
    shown = {c["message_id"]: c["why_not_shown"] for c in _criterion(doc, "R3")["evidence"]["cannot_show_identities"]}
    assert "more than one legitimate assignment" in shown["b-mid"] and "(E-13)" in shown["b-mid"]
    assert _criterion(doc, "R3")["evidence"]["assignments"]["may_be"]["b-mid"] == ["a3-connection-end", "none"]
    assert _criterion(doc, "R3")["observed"] is None and _criterion(doc, "R3")["evidence"]["r3_groups"] == []
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True and _criterion(doc, "S5")["holds"] is False
    assert r4["evidence"]["source_capacity"]["possible_sources"]["b-mid"]["deaths"] == []
    capacity = _capacity(doc)
    assert (capacity["kill_needed"], capacity["kill_available"], capacity["matched"], capacity["consistent"]) == (2, 2, 2, False)
    assert (capacity["deaths_preceding_none"], capacity["deaths_serving_none"]) == ([1], [1])
    mismatch = r4["evidence"]["mismatches"][0]
    assert mismatch["device_uuid"] is None and mismatch["stands_on"] == []
    assert mismatch["undecided_candidates"] == ["b-mid", "g-mid", "y-mid"]


def test_an_occurrence_two_candidates_contend_for_goes_to_the_one_the_kill_cannot_explain() -> None:
    """The same check (P-4): the candidate order decided which of two
    candidates an occurrence named. D1: E (seq 2, published inside the
    restart command's window, E-8) redelivered at 1,250 s and N (seq 3)
    lined before the kill at 1,100 s; one occurrence on D1 received at
    1,050 s, which precedes both. E came first and took it, and N was R3
    ('no A5 occurrence names its device before its redelivery', which was
    false) with R4 beside it, although N <- the occurrence and E <- the
    kill is source-consistent. The occurrences are now offered first to
    the candidates the kill cannot explain: N is named, E is unshown
    (E-8) and the run is inconclusive. Two candidates lined before the
    kill against the one occurrence still refute: one of them has no
    source.

    Corrected in round 4 (E-13, the Project Manager's F3: 'Do not
    arbitrarily name one particular identity as the culprit when only the
    aggregate inconsistency is established'): the second half expected one
    of M and N named and the other R3, the seq order choosing which, with
    a text saying the occurrence named the other. That encoded the wrong
    rule. R3 is now observed on the group, 'at least 1 of these have no
    source', in either seq order, neither named nor singled out, and R4
    stands on D1, whose surplus of two one occurrence cannot serve."""
    E = ("e-mid", D1, 2, 510 * NS)
    N = ("n-mid", D1, 3, 380 * NS)
    lines = list(LINES) + [("e-mid", D1, 2, "duplicate", 1_250 * NS, None), ("n-mid", D1, 3, "duplicate", 1_100 * NS, None)]
    log = [_a5_line(D1, 1_050 * NS)]
    doc = _evaluate(sent=SENT + [E, N], lines=lines, extra_after={D1: 2, "seqs": [(D1, 3)]}, controller_log=log)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
    assert [(c["message_id"], c["source"]) for c in outcome["n1_cases"]] == [("n-mid", "a3-connection-end")]
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is None and r3["evidence"]["not_named_identities"] == []
    assert [c["message_id"] for c in r3["evidence"]["cannot_show_identities"]] == ["e-mid"]
    assert _criterion(doc, "R4")["observed"] is None
    assert (_capacity(doc)["needed_by_device"], _capacity(doc)["consistent"]) == ({D1: 1}, True)
    assert "the kill cannot explain" in pe.IDENTIFICATION_RULES["P-4"]
    # Two candidates lined before the kill, one occurrence: at least one of
    # them has no source, R3 on the group whatever their seq order, and
    # neither is named or singled out.
    groups = []
    for m_seq, n_seq in ((2, 3), (3, 2)):
        M = ("m-mid", D1, m_seq, 385 * NS)
        N_ = ("n-mid", D1, n_seq, 380 * NS)
        lines = list(LINES) + [("m-mid", D1, m_seq, "duplicate", 1_120 * NS, None), ("n-mid", D1, n_seq, "duplicate", 1_100 * NS, None)]
        doc = _evaluate(sent=SENT + [M, N_], lines=lines, extra_after={D1: 2, "seqs": [(D1, 3)]}, controller_log=log)
        outcome = _outcome(doc)
        assert outcome["result"] == "refutes" and outcome["n1_cases"] == []
        r3 = _criterion(doc, "R3")
        assert r3["observed"] is True and _criterion(doc, "S4")["holds"] is False
        assert r3["evidence"]["not_named_identities"] == [] and r3["evidence"]["cannot_show_identities"] == []
        (group,) = r3["evidence"]["r3_groups"]
        assert (group["message_ids"], group["without_source_at_least"], group["sources"]) == (["m-mid", "n-mid"], 1, ["A5 line 1"])
        assert "at least 1 of them have no source" in group["why"] and "none is singled out as R3" in group["why"]
        assert "only the aggregate is established (E-13)" in group["why"]
        assert r3["reason"].startswith("at least 1 of the 2 duplicate-only identities m-mid, n-mid have no source")
        assert _criterion(doc, "R4")["observed"] is True
        assert _criterion(doc, "R4")["evidence"]["mismatches"][0]["stands_on"] == [D1]
        # What the group states, the identities' own seqs aside.
        groups.append(({k: v for k, v in group.items() if k != "identities"}, outcome["refutations"]))
    assert groups[0] == groups[1]


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


def test_harness_validity_is_quoted_verbatim_and_admitted_only_as_e12_states(tmp_path) -> None:
    """The harness's validity is quoted as recorded and admitted for the
    proof only as E-12 states; 'valid' (with no reason) is admitted and the
    proof's own eligibility (E-11) is checked apart and met. This case
    earlier fed a validity reason naming MAX_SAMPLE_GAP_S ('controller_
    metrics.csv: sample gap ... exceeds MAX_SAMPLE_GAP_S') beside a sealed
    resources.csv and expected 'supports': run.py never writes that form
    (the joint check of 2026-09-25, F1), so the case is replaced by the
    real form, built with run.py's and resources.py's own functions (test
    27h below); a manifest field that decides the admission and cannot be
    read leaves it unknown (P-6), never admitted."""
    doc = _evaluate()
    assert doc["instrumentation"]["harness_validity"] == "valid"
    assert doc["instrumentation"]["harness_validity_reasons"] == []
    assert _outcome(doc)["result"] == "supports"
    assert doc["instrumentation"]["harness_admission"] == {
        "admitted": True, "form": "valid", "reasons": [], "collector_file": None, "seal_withheld_for": None,
        "rule": pe.IDENTIFICATION_RULES["E-12"],
    }
    assert "kept as recorded" in doc["instrumentation"]["note"] and "E-12" in doc["instrumentation"]["note"]
    assert "MAX_SAMPLE_GAP_S" in doc["cannot_show"]
    eligibility = doc["instrumentation"]["proof_eligibility"]
    assert eligibility["eligible"] is True and eligibility["reasons"] == [] and eligibility["unknown"] == []
    assert eligibility["rule"] == pe.IDENTIFICATION_RULES["E-11"] and "E-12" in eligibility["rule"]
    assert "MAX_SAMPLE_GAP_S" in eligibility["rule"]
    assert eligibility["checks"]["load"]["ok"] is True and eligibility["checks"]["publication"]["ok"] is True
    assert eligibility["checks"]["publication"]["source"] == "the simulator's own manifest"
    assert eligibility["checks"]["harness_admission"] == doc["instrumentation"]["harness_admission"]
    assert eligibility["checks"]["fault"] == {
        "restart_executed": True, "restart_returncode": 0, "restart_ok": True, "restart_requested_at_s": 150.0,
        "prescribed_at_s": 150, "at_the_prescribed_instant": True, "restart_shown": True, "session_facts_present": True,
    }
    # A requirement the harness's reasons overlap is checked on the record
    # itself, never read from the validity: 'valid' beside a simulator that
    # exited 1 is admitted and still not eligible.
    doc = _evaluate(manifest=_manifest(validity="valid", validity_reasons=[], simulator_returncode=1))
    _assert_not_eligible(doc, "the simulator did not exit 0")
    assert doc["instrumentation"]["harness_admission"]["form"] == "valid"
    # A field that decides the admission and cannot be read: unknown, the
    # eligibility unknown with it (P-6) unless a requirement also fails
    # (the last case's resources.csv is not the SUT collector's), the run
    # inconclusive either way.
    for changes, says, only_unknown in (
        ({"validity": None}, "validity None cannot be read", True),
        ({"validity_reasons": "none"}, "validity_reasons 'none' cannot be read", True),
        ({"validity_reasons": [3]}, "validity_reasons [3] cannot be read", True),
        ({"validity": "valid", "validity_reasons": pe.sampling_gap_validity_reasons()}, "validity 'valid' beside validity reason(s)", True),
        (
            # The sampling-gap form's two reasons, as run.py writes them,
            # with the warnings that decide the form absent.
            {"validity": "invalid", "validity_reasons": pe.sampling_gap_validity_reasons(), "resource_source": "none",
             "missing_mandatory_artifacts": ["resources.csv"]},
            "warnings None cannot be read",
            False,
        ),
    ):
        doc = _evaluate(manifest=_manifest(**changes))
        admission = doc["instrumentation"]["harness_admission"]
        assert (admission["admitted"], admission["form"]) == (None, "unknown"), changes
        assert any(says in reason for reason in admission["reasons"]), (says, admission["reasons"])
        eligibility = _eligibility(doc)
        assert eligibility["eligible"] is not True, changes
        if only_unknown:
            assert eligibility["eligible"] is None and eligibility["reasons"] == [], changes
        assert any(u.startswith("harness validity: whether it is admitted for the proof is unknown (E-12, P-6)") for u in eligibility["unknown"])
        assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    assert "never admitted" in pe.IDENTIFICATION_RULES["E-12"] and "(P-6)" in pe.IDENTIFICATION_RULES["E-12"]
    # The function the driver calls: a run directory that cannot be read,
    # or a manifest that is not a JSON object, is unknown, never admitted.
    missing = pe.harness_admission(_manifest(), tmp_path / "absent" / RID)
    assert (missing["admitted"], missing["form"]) == (None, "unknown")
    assert missing["reasons"][0].startswith("the run directory cannot be read: ")
    not_an_object = pe.harness_admission(["not", "an", "object"], tmp_path)
    assert (not_an_object["admitted"], not_an_object["form"]) == (None, "unknown")
    assert pe.harness_admission(_manifest(), tmp_path)["form"] == "valid"


def test_a_harness_invalidity_outside_the_sampling_gap_form_is_not_admitted() -> None:
    """The three harness reasons the joint check of 2026-09-25 named (P2:
    the evaluator supported beside the driver's NOT ELIGIBLE), each exactly
    as run.compute_validity writes it for a run whose only failure it is:
    not admitted (E-12), every reason quoted, and the run not eligible
    although every criterion holds. This replaces the case that expected
    'supports' for 'no controller confirmation marker' and a missing
    sut_environment.json ('the harness validity never decides the proof by
    itself, whatever its reason'): it encoded the blanket exclusion of the
    harness's invalidity that the Project Manager did not confirm (review
    of PR #47, section 6, P-8)."""
    base = _manifest()
    for changes, begins in (
        ({"confirmation_marker_ok": False}, "no controller confirmation marker: "),
        ({"collector_problems": ["the collector did not stop cleanly"]}, "collector output not accounted for: "),
        ({"sut_env_missing_fields": ["os_release"]}, "sut_environment.json unusable, missing required field(s): os_release"),
    ):
        arguments: dict[str, Any] = dict(
            timed=True, sut_env_present=True, allow_missing_sut_env=False, resource_source="sut-collector",
            allow_missing_resources=False, restart_required=True, restart_ok=True, simulator_returncode=0,
            skip_warmup=True, condition_id="controller_restart", allow_protocol_deviation=True,
            confirmation_marker_ok=True, collector_hooks=[], missing_artifacts=[], collector_problems=[],
            sut_log_fetches=base["sut_log_fetches"], twin_snapshots=base["twin_snapshots"], drain=base["drain"],
            events_post_drain_fetch=base["events_post_drain_fetch"], config_identity_ok=True,
        )
        arguments.update(changes)
        validity, reasons = run_mod.compute_validity(**arguments)
        assert validity == "invalid" and len(reasons) == 1 and reasons[0].startswith(begins), reasons
        doc = _evaluate(manifest=_manifest(validity=validity, validity_reasons=reasons))
        assert doc["instrumentation"]["harness_validity_reasons"] == reasons
        admission = doc["instrumentation"]["harness_admission"]
        assert (admission["admitted"], admission["form"], admission["collector_file"]) == (False, "not-admitted", None)
        assert f"harness validity reason (quoted): {reasons[0]}" in admission["reasons"]
        _assert_not_eligible(doc, "harness validity: not admitted for the proof (E-12, form 'not-admitted')", reasons[0])
        assert all(_criterion(doc, rule)["holds"] is True for rule in pe.SUPPORT_RULE_IDS), begins
        assert any(r.startswith("not eligible (E-11): harness validity: not admitted") for r in _outcome(doc)["inconclusive_reasons"])
    for text in (pe.IDENTIFICATION_RULES["E-11"], _eligibility(doc)["note"], pe.__doc__):
        assert "never decides the proof by itself" not in text and "never decisive by itself" not in text, text[:80]
        assert "E-12" in text, text[:80]
    assert "reported, not decisive" not in pe.IDENTIFICATION_RULES["E-11"]
    assert "any other harness invalidity makes the run not eligible" in pe.IDENTIFICATION_RULES["E-11"]


# ---------------------------------------------------------------------------
# 27a-27k. the Project Manager's review of PR #47 (2026-09-25) and the joint
# check of the same day: F1, the proof's eligibility (E-11), the harness's
# validity admitted only as E-12 states (27h-27j), the fault's instant, and
# the drain verified before R1
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


#: The measured window the collector file of the sampling-gap form covers.
GAP_WINDOW = ("2026-09-25T10:00:00Z", "2026-09-25T10:01:05Z")


def _gap_collector_csv(path: Path, *, other_problem: bool = False) -> None:
    """The collector file as the SUT collector writes it (resources.py's
    CSV_HEADER): one container sampled every second over GAP_WINDOW but for
    one 6 s gap (10:00:19 to 10:00:25), and, with ``other_problem``, one
    row whose cpu_pct is not a finite number."""
    rows = [",".join(resources_mod.CSV_HEADER)]
    for n, second in enumerate([*range(0, 20), *range(25, 66)]):
        cpu = "nan" if other_problem and n == 3 else "1.0"
        rows.append(f"2026-09-25T10:{second // 60:02d}:{second % 60:02d}Z,egw-controller-1,{cpu},1048576,0.1,egw")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", "utf-8")


def _sampling_gap_run(
    tmp_path: Path,
    *,
    other_problem: bool = False,
    validity_changes: dict[str, Any] | None = None,
    seal: bool = False,
    collector: str = "kept",
) -> tuple[Path, dict]:
    """The campaign's sampling-gap deviation exactly as the harness records
    it, built with run.py's and resources.py's own functions and no reason
    string written here: the builder's complete run directory without
    resources.csv; the collector file the harness's own fetch writes
    (logs/collector/resources-<run_id>.csv) with a 6 s gap, handed to
    run.ingest_resources with the fetch's source label and the measured
    window, which rejects it and records the warning; the mandatory
    artefacts missing as run.missing_mandatory_artifacts finds them; and the
    validity run.compute_validity gives with resource_source 'none' and the
    records of a complete item-18 run. SHA256SUMS is withheld, as run.py
    withholds it while a mandatory artefact is missing, unless ``seal``;
    ``collector`` 'removed' or 'emptied' takes the collector file away
    after the harness's run."""
    run_dir = _write_run_dir(tmp_path, seal=False)
    (run_dir / "resources.csv").unlink()
    fetched = run_dir / pe.fetch_collector_rel(RID)
    _gap_collector_csv(fetched, other_problem=other_problem)
    warnings: list[str] = []
    ingested = run_mod.ingest_resources(
        run_dir,
        fetched,
        warnings,
        expected_window_start_utc=GAP_WINDOW[0],
        expected_window_end_utc=GAP_WINDOW[1],
        source_label=pe.INGEST_SOURCE_FETCH,
    )
    assert ingested is False and not (run_dir / "resources.csv").exists()
    missing = run_mod.missing_mandatory_artifacts(run_dir, "controller_restart")
    base = _manifest()
    arguments: dict[str, Any] = dict(
        timed=True, sut_env_present=True, allow_missing_sut_env=False, resource_source="none",
        allow_missing_resources=False, restart_required=True, restart_ok=True, simulator_returncode=0,
        skip_warmup=True, condition_id="controller_restart", allow_protocol_deviation=True,
        confirmation_marker_ok=True, collector_hooks=[], missing_artifacts=missing, collector_problems=[],
        sut_log_fetches=base["sut_log_fetches"], twin_snapshots=base["twin_snapshots"], drain=base["drain"],
        events_post_drain_fetch=base["events_post_drain_fetch"], config_identity_ok=True,
    )
    arguments.update(validity_changes or {})
    validity, reasons = run_mod.compute_validity(**arguments)
    manifest = _manifest(
        validity=validity, validity_reasons=reasons, resource_source="none", warnings=warnings,
        missing_mandatory_artifacts=missing,
    )
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", "utf-8")
    if collector == "removed":
        fetched.unlink()
    elif collector == "emptied":
        fetched.write_text("", "utf-8")
    if seal:
        write_sha256sums(run_dir)
    return run_dir, manifest


def test_the_campaign_sampling_gap_deviation_as_the_harness_records_it_is_admitted_and_supports(tmp_path, capsys) -> None:
    """The ADR anticipates the harness marking the proof's run invalid under
    MAX_SAMPLE_GAP_S ('What it cannot show'), as it marked r01 and r02. The
    harness records that deviation in one form only: its ingest rejects the
    collector file, so resources.csv is never written, resource_source is
    'none', the validity reasons are 'no SUT resources' and 'mandatory
    artefact(s) missing ... resources.csv', MAX_SAMPLE_GAP_S appears only
    in the rejection's warning, the rejected file stays at
    logs/collector/resources-<run_id>.csv and SHA256SUMS is withheld (the
    archived r02 manifest has exactly this shape). Built here with the
    harness's own functions and with every other check holding, it is
    admitted (E-12) by the function the driver calls as well, the evidence
    inventory takes the rejected collector file and the withheld seal with
    the reasons stated, and the proof supports. Sealed afterwards and
    verifying, the same form is admitted with nothing withheld."""
    run_dir, manifest = _sampling_gap_run(tmp_path)
    # What the harness wrote, from its own functions.
    assert manifest["validity"] == "invalid" and manifest["validity_reasons"] == pe.sampling_gap_validity_reasons()
    assert manifest["validity_reasons"][0].startswith("no SUT resources: ")
    assert manifest["validity_reasons"][1].startswith("mandatory artefact(s) missing from the run directory: resources.csv ")
    assert not any("MAX_SAMPLE_GAP_S" in reason for reason in manifest["validity_reasons"])
    (rejection,) = [w for w in manifest["warnings"] if pe.INGEST_REJECTED_MARK in w]
    assert rejection.startswith(pe.INGEST_SOURCE_FETCH + " ") and "sampling gap(s) exceed the protocol maximum of 5 s (MAX_SAMPLE_GAP_S)" in rejection
    problems = resources_mod.validate_resources_csv(
        run_dir / pe.fetch_collector_rel(RID), expected_window_start_utc=GAP_WINDOW[0], expected_window_end_utc=GAP_WINDOW[1]
    )
    assert len(problems) == 1 and rejection.endswith(problems[0])
    assert manifest["missing_mandatory_artifacts"] == ["resources.csv"] and manifest["resource_source"] == "none"
    assert not (run_dir / "SHA256SUMS").exists() and not (run_dir / "resources.csv").exists()
    # The shared admission, as the driver calls it.
    admission = pe.harness_admission(manifest, run_dir)
    assert set(admission) == {"admitted", "form", "reasons", "collector_file", "seal_withheld_for", "rule"}
    assert (admission["admitted"], admission["form"]) == (True, "sampling-gap-only")
    assert admission["collector_file"] == f"logs/collector/resources-{RID}.csv"
    assert admission["seal_withheld_for"] == (
        "the missing mandatory artefact resources.csv alone (run.py withholds SHA256SUMS while a mandatory artefact is missing)"
    )
    assert admission["rule"] == pe.IDENTIFICATION_RULES["E-12"]
    assert f"ingest rejection (quoted): {rejection}" in admission["reasons"]
    assert all(f"harness validity reason (quoted): {r}" in admission["reasons"] for r in manifest["validity_reasons"])
    # The evaluator over the same directory: every other check holds.
    out = tmp_path / "verdict.json"
    assert _main(run_dir, out, _session_file(tmp_path)) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["system_outcome"]["result"] == "supports" and doc["system_outcome"]["inconclusive_reasons"] == []
    assert doc["instrumentation"]["harness_admission"] == admission
    assert doc["instrumentation"]["harness_validity"] == "invalid"
    assert doc["instrumentation"]["harness_validity_reasons"] == manifest["validity_reasons"]
    eligibility = doc["instrumentation"]["proof_eligibility"]
    assert eligibility["eligible"] is True and eligibility["reasons"] == [] and eligibility["unknown"] == []
    assert eligibility["checks"]["harness_admission"] == admission
    evidence = doc["instrumentation"]["proof_evidence"]
    assert evidence["complete"] is True and evidence["missing"] == [] and evidence["fetch_failures"] == []
    assert evidence["present"]["resources.csv"] is False and evidence["present"][admission["collector_file"]] is True
    accepted = evidence["accepted_in_the_sampling_gap_form"]
    assert len(accepted) == 2
    assert accepted[0].startswith("resources.csv: absent from the top of the run directory") and admission["collector_file"] in accepted[0]
    assert accepted[1].startswith("SHA256SUMS: absent, withheld by the harness for the missing mandatory artefact resources.csv alone")
    assert "sha256 of every file it read" in accepted[1]
    assert doc["instrumentation"]["seal"] == "unsealed"
    assert len(doc["sources"][admission["collector_file"]]) == 64
    assert "(admission 'sampling-gap-only', E-12)" in capsys.readouterr().err
    # Sealed afterwards and verifying: admitted, nothing withheld.
    sealed_dir, sealed = _sampling_gap_run(tmp_path / "sealed", seal=True)
    admission = pe.harness_admission(sealed, sealed_dir)
    assert (admission["form"], admission["seal_withheld_for"]) == ("sampling-gap-only", None)
    assert _main(sealed_dir, tmp_path / "sealed.json", _session_file(tmp_path / "sealed")) == 0
    evidence = json.loads((tmp_path / "sealed.json").read_text(encoding="utf-8"))["instrumentation"]["proof_evidence"]
    assert evidence["complete"] is True and len(evidence["accepted_in_the_sampling_gap_form"]) == 1


@pytest.mark.parametrize(
    "variant, fragment",
    [
        ("another-problem", "the ingest rejection lists a problem other than a MAX_SAMPLE_GAP_S sampling gap"),
        ("third-reason", "validity 'invalid' for reason(s) other than exactly the two run.compute_validity writes"),
        ("collector-removed", f"the rejected collector file logs/collector/resources-{RID}.csv is absent from the run directory"),
        ("collector-emptied", f"the rejected collector file logs/collector/resources-{RID}.csv is empty"),
    ],
    ids=["another-problem", "third-reason", "collector-removed", "collector-emptied"],
)
def test_the_sampling_gap_form_is_admitted_only_whole(tmp_path, variant: str, fragment: str) -> None:
    """E-12 admits the sampling-gap form only whole: the same run with the
    rejection also listing a problem that is not a sampling gap (a row
    whose cpu_pct is not a finite number), with a third validity reason
    (no controller confirmation marker), or with the rejected collector
    file missing from logs/collector or empty, is not admitted, every
    harness reason quoted, and the run is not eligible."""
    kwargs: dict[str, Any] = {
        "another-problem": {"other_problem": True},
        "third-reason": {"validity_changes": {"confirmation_marker_ok": False}},
        "collector-removed": {"collector": "removed"},
        "collector-emptied": {"collector": "emptied"},
    }[variant]
    run_dir, manifest = _sampling_gap_run(tmp_path, **kwargs)
    if variant == "another-problem":
        problems = resources_mod.validate_resources_csv(
            run_dir / pe.fetch_collector_rel(RID), expected_window_start_utc=GAP_WINDOW[0], expected_window_end_utc=GAP_WINDOW[1]
        )
        assert len(problems) == 2 and "MAX_SAMPLE_GAP_S" in problems[-1] and "MAX_SAMPLE_GAP_S" not in problems[0]
        assert manifest["validity_reasons"] == pe.sampling_gap_validity_reasons()
    if variant == "third-reason":
        assert len(manifest["validity_reasons"]) == 3
        assert any(r.startswith("no controller confirmation marker: ") for r in manifest["validity_reasons"])
    admission = pe.harness_admission(manifest, run_dir)
    assert (admission["admitted"], admission["form"], admission["collector_file"]) == (False, "not-admitted", None)
    assert any(fragment in reason for reason in admission["reasons"]), admission["reasons"]
    for reason in manifest["validity_reasons"]:
        assert f"harness validity reason (quoted): {reason}" in admission["reasons"]
    doc = pe.evaluate(pe.load_run_dir(run_dir), _session())
    assert doc["instrumentation"]["harness_admission"] == admission
    _assert_not_eligible(doc, "harness validity: not admitted for the proof (E-12, form 'not-admitted')", fragment)
    assert doc["instrumentation"]["proof_evidence"]["accepted_in_the_sampling_gap_form"] == []
    assert _outcome(doc)["refutations"] == []


def test_the_sampling_gap_form_is_recognised_from_the_records_run_py_writes_alone(tmp_path) -> None:
    """E-12 reads each record of the form, each derived from run.py's code
    path, and admits nothing short of all of them: resource_source 'none',
    missing_mandatory_artifacts ['resources.csv'] alone, exactly one
    rejection warning, no resources.csv at the top of the run directory, the
    harness's own fetch rejected where run.py writes it, a source label
    run.py passes, a file inside the run directory and a sampling-gap
    problem in the form validate_resources_csv writes. A rejection through
    '--resources-from' naming a file inside the run directory (as r02
    recorded it) is the same form."""
    run_dir, manifest = _sampling_gap_run(tmp_path)
    artefacts = pe.load_run_dir(run_dir)
    (rejection,) = [w for w in manifest["warnings"] if pe.INGEST_REJECTED_MARK in w]
    fetched = pe.fetch_collector_rel(RID)

    def _admit(changes: dict[str, Any] | None = None, add: tuple[str, ...] = ()) -> dict:
        return pe.admission_of({**manifest, **(changes or {})}, artefacts.files_present | set(add), artefacts.empty_files, artefacts.integrity)

    assert _admit()["form"] == "sampling-gap-only" and _admit()["collector_file"] == fetched
    moved = rejection.replace(f"/{fetched}", f"/logs/collector/resources-from/resources-{RID}.csv")
    for changes, add, fragment in (
        ({"resource_source": "sut-collector"}, (), "resource_source 'sut-collector', not 'none'"),
        ({"missing_mandatory_artifacts": ["resources.csv", "events.jsonl"]}, (), "missing_mandatory_artifacts ['resources.csv', 'events.jsonl'], not ['resources.csv'] alone"),
        ({"warnings": [rejection, rejection]}, (), "2 warning(s) of the ingest rejection"),
        ({"warnings": []}, (), "0 warning(s) of the ingest rejection"),
        ({}, ("resources.csv",), "resources.csv is present at the top of the run directory"),
        (
            {"warnings": [moved]}, (f"logs/collector/resources-from/resources-{RID}.csv",),
            f"the rejected file of the harness's own fetch is at logs/collector/resources-from/resources-{RID}.csv, not at {fetched}",
        ),
        ({"warnings": [rejection.replace(pe.INGEST_SOURCE_FETCH, "--another-source", 1)]}, (), "names a source that run.py does not pass"),
        (
            {"warnings": [pe.INGEST_SOURCE_RESOURCES_FROM + " /elsewhere/resources.csv" + rejection[rejection.index(pe.INGEST_REJECTED_MARK):]]}, (),
            "the rejected file '/elsewhere/resources.csv' is not in the run directory",
        ),
        (
            {"warnings": [rejection.replace("1 sampling gap(s)", "2 sampling gap(s)", 1)]}, (),
            "sampling-gap problem is not in the form resources.validate_resources_csv writes",
        ),
    ):
        admission = _admit(changes, add)
        assert (admission["admitted"], admission["form"], admission["collector_file"]) == (False, "not-admitted", None), changes
        assert any(fragment in reason for reason in admission["reasons"]), (fragment, admission["reasons"])
    manual = rejection.replace(pe.INGEST_SOURCE_FETCH, pe.INGEST_SOURCE_RESOURCES_FROM, 1)
    admission = _admit({"warnings": [manual]})
    assert (admission["form"], admission["collector_file"]) == ("sampling-gap-only", fetched)
    # On disk, the same through the function the driver calls.
    (run_dir / "resources.csv").write_text(RESOURCES_CSV, "utf-8")
    assert pe.harness_admission(manifest, run_dir)["form"] == "not-admitted"


def test_a_seal_that_fails_beside_the_sampling_gap_form_is_never_accepted(tmp_path, capsys) -> None:
    """A SHA256SUMS present that does not verify is never accepted: the
    evaluator does not evaluate the directory (exit 2, as today), the
    shared admission refuses the form, and in memory the failed seal is a
    failed record that leaves the run not eligible."""
    run_dir, manifest = _sampling_gap_run(tmp_path, seal=True)
    (run_dir / "sent_events.jsonl").write_text("{}\n", "utf-8")  # bytes changed after the seal
    admission = pe.harness_admission(manifest, run_dir)
    assert (admission["admitted"], admission["form"]) == (False, "not-admitted")
    assert "SHA256SUMS is present and does not verify (seal 'false')" in admission["reasons"]
    out = tmp_path / "verdict.json"
    assert _main(run_dir, out, _session_file(tmp_path)) == 2
    assert json.loads(out.read_text(encoding="utf-8"))["system_outcome"]["result"] == "not-evaluated"
    capsys.readouterr()
    artefacts = pe.load_run_dir(run_dir)
    assert artefacts.integrity == "false"
    doc = pe.evaluate(artefacts, _session())
    _assert_not_eligible(doc, "SHA256SUMS: the seal does not verify", "harness validity: not admitted")
    assert doc["instrumentation"]["proof_evidence"]["accepted_in_the_sampling_gap_form"] == []


def test_the_fault_is_required_at_the_plans_instant() -> None:
    """E-11 checks the prescribed fault instant (ADR 0011's table: 'fault |
    at t+150 s', issued through --restart-at-s so that the instant is in
    the manifest): run.py records the instant it scheduled as the restart
    record's requested_at_s. Another instant, an absent one or one that is
    not a number is not eligible; 150 s, as an integer or a float, is."""
    for value in (120.0, 150.5, "150", None, "absent"):
        restart = {**_manifest()["restart"], "requested_at_s": value}
        if value == "absent":
            restart.pop("requested_at_s")
            value = None
        doc = _evaluate(manifest=_manifest(restart=restart))
        _assert_not_eligible(
            doc,
            f"fault: the manifest's restart was requested at {value!r} s (restart.requested_at_s), not at the "
            "plan's t+150 s (ADR 0011: 'fault | at t+150 s'): the prescribed fault instant is not shown",
        )
        fault = _eligibility(doc)["checks"]["fault"]
        assert fault["at_the_prescribed_instant"] is False and fault["prescribed_at_s"] == 150
        assert _outcome(doc)["refutations"] == []
        assert all(_criterion(doc, rule)["holds"] is True for rule in pe.SUPPORT_RULE_IDS)
    doc = _evaluate(manifest=_manifest(restart={**_manifest()["restart"], "requested_at_s": 150}))
    assert _eligibility(doc)["eligible"] is True and _outcome(doc)["result"] == "supports"
    adr = " ".join(pe.ADR_PATH.read_text(encoding="utf-8").split())
    assert f"| fault | at t+{pe.PROOF_RESTART_AT_S} s, SIGKILL of the controller's container" in adr
    driver = (Path(__file__).resolve().parents[2] / "tools" / "session" / "proof.sh").read_text(encoding="utf-8")
    assert f"healthy_seconds EGW_PROOF_RESTART_AT_S {pe.PROOF_RESTART_AT_S})" in driver
    assert "requested_at_s" in pe.IDENTIFICATION_RULES["E-11"] and "t+150 s" in pe.IDENTIFICATION_RULES["E-11"]


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
# 27l-27r. round 4 of the review of PR #47 (2026-09-25): ambiguous contention
# never supports and an aggregate R3 names no culprit (E-13), a death beside
# a process whose readings carry no monotonic_ns is not placed (E-4), the
# harness's exit in the session facts agrees with the admission (E-11), and
# a further death serves a candidate the kill cannot explain (E-13, E-10)
# ---------------------------------------------------------------------------


def _duplicates(*items: tuple[str, int, int, int]) -> list[tuple]:
    """The scenario's lines (B accepted) and, per item (message_id, seq,
    publication in s, redelivery in s), one duplicate-only line on D1
    received at that instant on the controller clock."""
    return list(LINES) + [(m, D1, seq, "duplicate", received * NS, None) for m, seq, _publish, received in items]


def test_candidates_that_may_both_have_been_at_the_kill_contending_for_one_occurrence_are_named_in_no_order() -> None:
    """E-13, the probe of round 3 (jv/g_same_tier_probe.py): on D1, K
    (restart-class, published before the kill, redelivered at 1,300 s) and
    E (published inside the restart command's window, E-8, redelivered at
    1,250 s) with a surplus of two, and one A5 occurrence on D1 at 1,190 s
    that precedes both. Two legitimate assignments remain (K <- the
    occurrence and E <- the kill, or E <- the occurrence and K <- the
    kill), and they do not name K or E alike. The candidates' seq order
    used to choose: K first read 'inconclusive', E first 'supports' with K
    named for the kill. Now neither is named in either order, both are
    unshown with the same E-13 text, S4, R3, S5 and R4 are null and the
    run is inconclusive, never 'supports' and never refuted. A lone
    claimant with an occurrence before its redelivery is named alike by no
    two assignments either. A genuinely unique assignment still names and
    supports: E published after the restart command's end (the kill
    cannot explain it) takes the occurrence and K the kill."""
    documents = []
    for k_seq, e_seq in ((2, 3), (3, 2)):
        K = ("k-mid", D1, k_seq, 400 * NS)
        E = ("e-mid", D1, e_seq, 510 * NS)
        doc = _evaluate(
            sent=SENT + [K, E],
            lines=_duplicates(("k-mid", k_seq, 400, 1_300), ("e-mid", e_seq, 510, 1_250)),
            extra_after={D1: 2, "seqs": [(D1, 3)]},
            controller_log=[_a5_line(D1, 1_190 * NS)],
        )
        outcome = _outcome(doc)
        assert outcome["result"] == "inconclusive" and outcome["refutations"] == [], (k_seq, e_seq)
        assert outcome["n1_cases"] == []
        for rule_id in ("S4", "S5"):
            assert _criterion(doc, rule_id)["holds"] is None, (rule_id, k_seq)
        for rule_id in ("R3", "R4"):
            assert _criterion(doc, rule_id)["observed"] is None, (rule_id, k_seq)
        r3 = _criterion(doc, "R3")
        assert r3["evidence"]["not_named_identities"] == [] and r3["evidence"]["r3_groups"] == []
        shown = {c["message_id"]: c["why_not_shown"] for c in r3["evidence"]["cannot_show_identities"]}
        assert sorted(shown) == ["e-mid", "k-mid"]
        assert all("more than one legitimate assignment" in why and why.endswith("(E-13)") for why in shown.values())
        assert "named with an A3 connection end of its device (controller log line(s) 1); or named with the kill" in shown["k-mid"]
        assert "no assignment is chosen by sequence or log order" in shown["e-mid"]
        assert r3["evidence"]["assignments"]["may_be"] == {
            "e-mid": ["a3-connection-end", "kill-unshown"], "k-mid": ["a3-connection-end", "kill"],
        }
        assert [(u["device_uuid"], u["rule"], u["message_ids"]) for u in _criterion(doc, "R4")["evidence"]["undecided"]] == [
            (D1, "E-13", ["e-mid", "k-mid"]),
        ]
        assert any(r.startswith("S4 cannot be shown (E-13)") for r in outcome["inconclusive_reasons"])
        assert "E-13" in r3["identification_rules"] and "E-13" in _criterion(doc, "R4")["identification_rules"]
        documents.append((shown, _capacity(doc)))
    assert documents[0] == documents[1]
    # A lone claimant of the kill with an occurrence before its redelivery:
    # the kill or the connection end, which cannot be told.
    doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 1, "seqs": [(D1, 1)]}, controller_log=[_a5_line(D1, 1_190 * NS)])
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["n1_cases"] == []
    assert _criterion(doc, "R3")["evidence"]["assignments"]["may_be"]["b-mid"] == ["a3-connection-end", "kill"]
    # The occurrence after its redelivery: the kill alone, named (test 16).
    doc = _evaluate(lines=B_DUPLICATE, extra_after={D1: 1, "seqs": [(D1, 1)]}, controller_log=[_a5_line(D1, 1_205 * NS)])
    assert _outcome(doc)["result"] == "supports"
    assert [(c["message_id"], c["source"]) for c in _outcome(doc)["n1_cases"]] == [("b-mid", "kill")]
    # E published after the restart command's end: one legitimate
    # assignment, E <- the occurrence and K <- the kill; named, supports.
    K = ("k-mid", D1, 2, 400 * NS)
    E = ("e-mid", D1, 3, 530 * NS)
    doc = _evaluate(
        sent=SENT + [K, E],
        lines=_duplicates(("k-mid", 2, 400, 1_300), ("e-mid", 3, 530, 1_250)),
        extra_after={D1: 2, "seqs": [(D1, 3)]},
        controller_log=[_a5_line(D1, 1_190 * NS)],
    )
    assert _outcome(doc)["result"] == "supports" and _outcome(doc)["inconclusive_reasons"] == []
    cases = {c["message_id"]: c for c in _outcome(doc)["n1_cases"]}
    assert {m: c["source"] for m, c in cases.items()} == {"e-mid": "a3-connection-end", "k-mid": "kill"}
    assert cases["e-mid"]["source_evidence"]["controller_log_lines_possible"] == [1]
    assert _criterion(doc, "R3")["evidence"]["assignments"]["may_be"] == {"e-mid": ["a3-connection-end"], "k-mid": ["kill"]}
    # Two candidates lined before the kill and two occurrences before both:
    # both named alike in every assignment, each shown with the occurrence
    # an assignment read from the stamps gives it (the later redelivery the
    # later occurrence) and both lines listed, whatever the seqs or the
    # order of the log lines.
    two = [_a5_line(D1, 1_050 * NS), _a5_line(D1, 1_060 * NS)]
    shown_lines = []
    for m_seq, n_seq in ((2, 3), (3, 2)):
        for log in (two, list(reversed(two))):
            sent = [("m-mid", D1, m_seq, 385 * NS), ("n-mid", D1, n_seq, 380 * NS)]
            doc = _evaluate(
                sent=SENT + sent,
                lines=_duplicates(("m-mid", m_seq, 385, 1_120), ("n-mid", n_seq, 380, 1_100)),
                extra_after={D1: 2, "seqs": [(D1, 3)]},
                controller_log=log,
            )
            assert _outcome(doc)["result"] == "supports"
            cases = {c["message_id"]: c["source_evidence"] for c in _outcome(doc)["n1_cases"]}
            assert all(evidence["controller_log_lines_possible"] == [1, 2] for evidence in cases.values())
            shown_lines.append({m: evidence["identity"]["received_monotonic_ns"] for m, evidence in cases.items()})
    assert shown_lines == [{"m-mid": 1_060 * NS, "n-mid": 1_050 * NS}] * 4
    assert "E-13" in pe.IDENTIFICATION_RULES["P-4"] and "no order decides" in pe.IDENTIFICATION_RULES["E-13"]


def test_an_aggregate_r3_names_no_culprit_in_any_order() -> None:
    """E-13, the aggregate the Project Manager's F3 asks for ('Do not
    arbitrarily name one particular identity as the culprit when only the
    aggregate inconsistency is established'): three candidates lined
    before the kill on D1 (surplus three) and two A5 occurrences that
    precede all three. At least one of them has no source: R3 is observed
    on the group, listed with the two occurrences and 'at least 1', none
    of the three named or singled out, in each of the six seq orders and
    with the log lines in either order; R4 stands on D1 by itself. Two
    claimants of the kill and one candidate lined before it, against one
    occurrence that precedes all three and the kill, form one group too
    (either claimant may hold the occurrence, which leaves the lined one
    without a source), where E-4 alone would read each claimant R3 and name
    the lined one; the claimants of the kill with no other source keep
    E-4's reading (test 22e)."""
    log = [_a5_line(D1, 1_050 * NS), _a5_line(D1, 1_060 * NS)]
    seen = []
    for seqs in itertools.permutations((2, 3, 4)):
        for order in (log, list(reversed(log))):
            ids = ("x-mid", "y-mid", "z-mid")
            sent = [(m, D1, seq, (381 + n) * NS) for n, (m, seq) in enumerate(zip(ids, seqs))]
            lines = _duplicates(*((m, seq, 381 + n, 1_100 + 10 * n) for n, (m, seq) in enumerate(zip(ids, seqs))))
            doc = _evaluate(sent=SENT + sent, lines=lines, extra_after={D1: 3, "seqs": [(D1, 4)]}, controller_log=order)
            outcome = _outcome(doc)
            assert outcome["result"] == "refutes" and outcome["n1_cases"] == [], seqs
            r3 = _criterion(doc, "R3")
            assert r3["observed"] is True and r3["evidence"]["not_named_identities"] == []
            assert r3["evidence"]["cannot_show_identities"] == []
            (group,) = r3["evidence"]["r3_groups"]
            assert group["message_ids"] == ["x-mid", "y-mid", "z-mid"] and group["without_source_at_least"] == 1
            assert group["sources"] == ["A5 line 1", "A5 line 2"]
            mismatch = _criterion(doc, "R4")["evidence"]["mismatches"][0]
            assert _criterion(doc, "R4")["observed"] is True and mismatch["stands_on"] == [D1]
            seen.append((group["why"], r3["reason"], outcome["refutations"][0]))
    assert len(set(seen)) == 1
    assert "none is named as a case and none is singled out as R3" in seen[0][0]
    # Two claimants of the kill and a candidate lined before it, one
    # occurrence preceding all three: one group of three, at least one
    # without a source.
    K1 = ("k1-mid", D1, 2, 400 * NS)
    K2 = ("k2-mid", D1, 3, 390 * NS)
    N = ("n-mid", D1, 4, 380 * NS)
    lines = _duplicates(("k1-mid", 2, 400, 1_300), ("k2-mid", 3, 390, 1_290), ("n-mid", 4, 380, 1_100))
    doc = _evaluate(sent=SENT + [K1, K2, N], lines=lines, extra_after={D1: 3, "seqs": [(D1, 4)]}, controller_log=[_a5_line(D1, 1_050 * NS)])
    assert _outcome(doc)["result"] == "refutes" and _outcome(doc)["n1_cases"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is True and r3["evidence"]["not_named_identities"] == []
    (group,) = r3["evidence"]["r3_groups"]
    assert (group["message_ids"], group["sources"], group["without_source_at_least"]) == (
        ["k1-mid", "k2-mid", "n-mid"], ["A5 line 1", "death 0"], 1,
    )
    assert "the A3 connection end of controller log line 1, the kill" in group["why"]
    assert "E-13" in r3["identification_rules"] and "only the aggregate is established" in pe.IDENTIFICATION_RULES["E-13"]


def test_a_death_beside_a_process_whose_readings_carry_no_monotonic_ns_is_not_placed() -> None:
    """E-4's 'or when either cannot be read', re-check 0 of round 3 (P3 at
    recorded_deaths): three claimants of the kill on D1 redelivered at
    1,270 s, received by the last process P2 (first read 1,265 s, last
    1,285 s); between P1 (last read 1,245 s) and P2 a process PX ran and
    died, its readings without monotonic_ns. Three deaths may have preceded
    the redeliveries, as with PX readable. PX was sorted to the end of the
    chain and P2's death read as placed after 1,285 s, wholly after every
    redelivery: a false R4 against two deaths. The deaths PX's place
    decides are now not placed and may have preceded any redelivery, so
    the run is inconclusive, as with PX readable; the kill keeps its lower
    bound whatever process came next."""
    PX = "2026-09-25T10:04:10Z"
    R = 1_270
    F = ("f-mid", D1, 2, 401 * NS)
    F2 = ("f2-mid", D1, 3, 402 * NS)
    lines = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "duplicate", R * NS, None), ("f-mid", D1, 2, "duplicate", R * NS, None),
        ("f2-mid", D1, 3, "duplicate", R * NS, None),
    ]

    def _px_rows(readable: bool) -> list[dict[str, str]]:
        return _rows() + [
            _row(_ts(250), PX, 0, 0, monotonic_ns=1_250 * NS if readable else None, unacked=0),
            _row(_ts(255), PX, 0, 0, monotonic_ns=1_255 * NS if readable else None, unacked=0),
            _row(_ts(265), P2, 0, 0, monotonic_ns=1_265 * NS, unacked=0),
            _row(_ts(285), P2, 0, 0, monotonic_ns=1_285 * NS, unacked=0),
        ]

    for readable in (True, False):
        doc = _evaluate(sent=SENT + [F, F2], lines=lines, extra_after={D1: 3, "seqs": [(D1, 3)]}, rows=_px_rows(readable))
        assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == [], readable
        assert _criterion(doc, "R4")["observed"] is None and _capacity(doc)["consistent"] is True, readable
        deaths = _criterion(doc, "R4")["evidence"]["source_capacity"]["deaths"]
        assert all(d["may_precede"] == ["b-mid", "f-mid", "f2-mid"] for d in deaths), readable
    last = deaths[2]
    assert (last["dying_started_at"], last["next_started_at"], last["placed"], last["unordered_started_at"]) == (P2, PX, False, PX)
    assert f"process {PX} has no readable monotonic_ns" in last["placement"]
    assert deaths[1]["placed"] is True and deaths[1]["after_monotonic_ns"] == K_UPPER + 65 * NS
    # The deaths as recorded_deaths reads them: the one after P2 is the one
    # PX's place decides; the kill keeps its bound beside an unreadable next.
    rows, _notes = pe.read_metrics_rows(_px_rows(False))
    kill, p1_death, unordered = pe.recorded_deaths(pe.split_by_process(rows), restart_ok=True)
    assert kill.placed and p1_death.placed and not unordered.placed
    assert unordered.may_precede(0) and unordered.unordered_started_at == PX
    rows, _notes = pe.read_metrics_rows(_rows()[:6] + _px_rows(False)[-4:-2])
    (alone,) = pe.recorded_deaths(pe.split_by_process(rows), restart_ok=True)
    assert (alone.dying_started_at, alone.next_started_at, alone.after, alone.placed) == (P0, PX, K_LOWER, True)
    assert "never read as the last of them" in pe.IDENTIFICATION_RULES["E-4"]


def test_a_reading_whose_started_at_cannot_be_read_leaves_the_number_of_deaths_unknown_never_zero() -> None:
    """The read-only re-check of round 4 (P3 at split_by_process), on the
    shape of the case above: three claimants of the kill on D1 redelivered
    at 1,270 s, and between P1 (last read 1,245 s) and P2 (first read
    1,265 s) a process PX whose readings carry a readable monotonic_ns but
    an empty started_at cell. split_by_process kept those readings apart
    and recorded_deaths counted no process for them: two deaths against
    three claimants, and E-10 refuted on capacity (a false R4). An unread
    started_at is never read as no process (E-4, E-10): the number of
    deaths is unknown, so E-10's capacity is unknown and named, nothing is
    refuted on it, and no claimant is named or R3; the run is inconclusive,
    as with PX readable, which is unchanged."""
    PX = "2026-09-25T10:04:10Z"
    R = 1_270
    F = ("f-mid", D1, 2, 401 * NS)
    F2 = ("f2-mid", D1, 3, 402 * NS)
    lines = [line for line in LINES if line[0] != "b-mid"] + [
        ("b-mid", D1, 1, "duplicate", R * NS, None), ("f-mid", D1, 2, "duplicate", R * NS, None),
        ("f2-mid", D1, 3, "duplicate", R * NS, None),
    ]

    def _px_rows(started_at: str | None) -> list[dict[str, str]]:
        return _rows() + [
            _row(_ts(250), started_at, 0, 0, monotonic_ns=1_250 * NS, unacked=0),
            _row(_ts(255), started_at, 0, 0, monotonic_ns=1_255 * NS, unacked=0),
            _row(_ts(265), P2, 0, 0, monotonic_ns=1_265 * NS, unacked=0),
            _row(_ts(285), P2, 0, 0, monotonic_ns=1_285 * NS, unacked=0),
        ]

    documents = {}
    for label, started_at in (("readable", PX), ("no-started_at", None)):
        doc = _evaluate(sent=SENT + [F, F2], lines=lines, extra_after={D1: 3, "seqs": [(D1, 3)]}, rows=_px_rows(started_at))
        assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == [], label
        assert _criterion(doc, "R4")["observed"] is None and _criterion(doc, "R3")["observed"] is None, label
        r3 = _criterion(doc, "R3")["evidence"]
        assert r3["not_named_identities"] == [] and r3["r3_groups"] == [] and _outcome(doc)["n1_cases"] == [], label
        assert [c["message_id"] for c in r3["cannot_show_identities"]] == ["b-mid", "f-mid", "f2-mid"], label
        documents[label] = doc
    # PX readable: three deaths, the capacity known and consistent, as before.
    readable = _capacity(documents["readable"])
    assert (readable["applied"], readable["known"], readable["why_unknown"]) == (True, True, None)
    assert (readable["deaths_recorded"], readable["matched"], readable["consistent"]) == (3, 3, True)
    # PX's started_at unread: two deaths recorded, the number of deaths
    # unknown, and with it the capacity, which is named and decides nothing.
    unread = _capacity(documents["no-started_at"])
    assert (unread["applied"], unread["known"], unread["consistent"], unread["matched"]) == (False, False, None, None)
    assert unread["deaths_recorded"] == 2
    assert unread["why_unknown"] == (
        "the number of recorded controller deaths is unknown: 2 controller reading(s) (row(s) 9, 10) carry no "
        "readable started_at and are not shown to be the pre-kill process's (a monotonic_ns unread or above that "
        "process's last reading), so the process each belongs to cannot be read (E-4)"
    )
    r3 = _criterion(documents["no-started_at"], "R3")["evidence"]
    for claimant in r3["cannot_show_identities"]:
        assert "3 identities claim the kill as their source and the readings record 2 controller process starts" in claimant["why_not_shown"]
        assert "the number of controller deaths is unknown (2 controller reading(s) (row(s) 9, 10)" in claimant["why_not_shown"]
        assert "none is named and none is R3" in claimant["why_not_shown"]
    assert any(n.startswith("the number of controller deaths is unknown") and "nothing is refuted on capacity grounds" in n for n in r3["notes"])
    undecided = _criterion(documents["no-started_at"], "R4")["evidence"]["undecided"]
    assert [(u["device_uuid"], u["rule"]) for u in undecided] == [(D1, "E-4")]
    # A reading with an empty started_at at or below the pre-kill process's
    # last reading is of that process's time: it names no further process.
    rows, _notes = pe.read_metrics_rows([_row(_ts(0), None, 3, 1, monotonic_ns=K_LOWER)] + _rows())
    assert pe.unread_process_readings(pe.split_by_process(rows)) == [] and pe.deaths_unknown_of(pe.split_by_process(rows)) is None
    rows, _notes = pe.read_metrics_rows(_px_rows(None) + [_row(_ts(300), None, 0, 0, monotonic_ns=None)])
    assert [r.index for r in pe.unread_process_readings(pe.split_by_process(rows))] == [9, 10, 13]
    assert "the number of deaths is unknown" in pe.IDENTIFICATION_RULES["E-4"]
    assert "an unread cell is never read as no process" in pe.IDENTIFICATION_RULES["E-4"]
    assert "So it is when the number of deaths is unknown" in pe.IDENTIFICATION_RULES["E-10"]


def test_a_candidate_a_death_the_readings_do_not_record_may_have_preceded_is_neither_named_nor_r3() -> None:
    """E-4 with the number of deaths unknown, beyond the claimants: N,
    published after the restart command's end and redelivered at 1,270 s,
    with no A5 occurrence, beside the scenario's two processes and one
    reading at 1,250 s whose started_at cannot be read. On the deaths
    recorded alone the kill cannot explain N and no further death is
    recorded, so N was R3 and the run refuted; but that reading may be of a
    process after P1, whose death may have preceded N's redelivery. N is
    now neither named nor R3 and the run inconclusive. Unchanged: N stays
    R3 when the twin shows it unapplied, and P, lined before the kill, keeps
    its R3, since every death follows the pre-kill process's last reading."""
    N = ("n-mid", D1, 2, 540 * NS)
    P = ("p-mid", D1, 2, 360 * NS)
    rows = _rows() + [_row(_ts(250), None, 0, 0, monotonic_ns=1_250 * NS, unacked=0)]
    doc = _evaluate(sent=SENT + [N], lines=_duplicates(("n-mid", 2, 540, 1_270)), extra_after={D1: 1, "seqs": [(D1, 2)]}, rows=rows)
    assert _outcome(doc)["result"] == "inconclusive" and _outcome(doc)["refutations"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is None and r3["evidence"]["not_named_identities"] == []
    (unshown,) = r3["evidence"]["cannot_show_identities"]
    assert unshown["message_id"] == "n-mid"
    assert unshown["why_not_shown"].startswith(
        f"a further death may have preceded its redelivered duplicate line (received at {1_270 * NS}), and it may "
        "have been in progress at that death, which P-4 never names as a source: the number of controller deaths "
        "is unknown (1 controller reading(s) (row(s) 9)")
    assert unshown["why_not_shown"].endswith("so it is neither named nor R3 (E-4, E-10)")
    assert _capacity(doc)["known"] is False and _criterion(doc, "R4")["observed"] is None
    # Every reading names its process: N is R3 and the run refutes, as before.
    doc = _evaluate(sent=SENT + [N], lines=_duplicates(("n-mid", 2, 540, 1_270)), extra_after={D1: 1, "seqs": [(D1, 2)]})
    assert _outcome(doc)["result"] == "refutes"
    assert [c["message_id"] for c in _criterion(doc, "R3")["evidence"]["not_named_identities"]] == ["n-mid"]
    # The twin shows N unapplied (last_seq 1 below its seq 2): R3 on the
    # twin's evidence, whatever death may have preceded it.
    doc = _evaluate(sent=SENT + [N], lines=_duplicates(("n-mid", 2, 540, 1_270)), extra_after={D1: 1}, rows=rows)
    assert _outcome(doc)["result"] == "refutes"
    (rejected,) = _criterion(doc, "R3")["evidence"]["not_named_identities"]
    assert rejected["message_id"] == "n-mid" and "and the twin does not show it applied" in rejected["why_not_named"]
    assert "but the number of controller deaths is unknown" in rejected["why_not_named"]
    # P, lined before the kill, keeps its R3 beside the unknown deaths.
    doc = _evaluate(sent=SENT + [P], lines=_duplicates(("p-mid", 2, 360, 1_100)), extra_after={D1: 1, "seqs": [(D1, 2)]}, rows=rows)
    assert _outcome(doc)["result"] == "refutes"
    (rejected,) = _criterion(doc, "R3")["evidence"]["not_named_identities"]
    assert rejected["message_id"] == "p-mid" and "lined before the kill" in rejected["why_not_named"]
    assert _criterion(doc, "R3")["evidence"]["cannot_show_identities"] == []


def _session_with_exit(tmp_path: Path, harness_exit: Any) -> Path:
    path = tmp_path / "proof_session.json"
    path.write_text(json.dumps({**_session(), "harness_exit": harness_exit}, indent=2) + "\n", "utf-8")
    return path


def test_the_harness_exit_the_session_facts_carry_agrees_with_the_admission(tmp_path) -> None:
    """E-11, re-check 0 of round 3 (P3 at proof.sh:917): the driver refuses
    a 'valid' manifest beside a harness exit other than 0 ('a failure the
    manifest does not record') while the evaluator decided on the
    admission alone and wrote 'supports' beside it. With the session
    facts' harness_exit the two now agree: 0 for the 'valid' form; 0 or 1
    for the sampling-gap form, in which the harness exits 1; anything else
    not eligible. Without harness_exit the manifest's own validity stands
    and the absence is reported, deciding nothing; a refutation observed
    on read evidence stands beside a disagreeing exit (P-7)."""

    def _facts(harness_exit: Any) -> dict:
        facts = _session()
        if harness_exit is not None:
            facts["harness_exit"] = harness_exit
        return facts

    for harness_exit, eligible in ((None, True), (0, True), (1, False), (124, False), ("not-started", False), (True, False)):
        doc = _evaluate(session=_facts(harness_exit))
        eligibility = _eligibility(doc)
        assert eligibility["eligible"] is eligible, harness_exit
        assert _outcome(doc)["result"] == ("supports" if eligible else "inconclusive"), harness_exit
        check = eligibility["checks"]["harness_exit"]
        assert (check["read"], check["carried"], check["admission_form"], check["allowed"]) == (
            harness_exit, harness_exit is not None, "valid", [0],
        )
        if harness_exit is None:
            assert check["agrees"] is None and "carry no harness_exit" in check["note"] and "decides nothing" in check["note"]
        else:
            assert check["agrees"] is eligible
        if not eligible:
            (reason,) = eligibility["reasons"]
            assert reason.startswith(f"harness exit: the session facts record the harness's exit {harness_exit!r}")
            assert "a failure the manifest does not record" in reason
            assert any(r.startswith("not eligible (E-11): harness exit:") for r in _outcome(doc)["inconclusive_reasons"])
    # A refutation observed on read evidence stands beside it.
    doc = _evaluate(lines=B_DUPLICATE, session=_facts(1))
    assert _outcome(doc)["result"] == "refutes" and _eligibility(doc)["eligible"] is False
    # The sampling-gap form, as the harness records it: exit 1 (or 0) is
    # the form's own, any other exit is not.
    run_dir, _manifest_gap = _sampling_gap_run(tmp_path / "gap")
    for harness_exit, code in ((1, 0), (0, 0), (2, 3), (124, 3), (True, 3)):
        out = tmp_path / f"gap-{harness_exit}.json"
        session_dir = tmp_path / f"session-{harness_exit}"
        session_dir.mkdir()
        assert _main(run_dir, out, _session_with_exit(session_dir, harness_exit)) == code, harness_exit
        doc = json.loads(out.read_text(encoding="utf-8"))
        check = _eligibility(doc)["checks"]["harness_exit"]
        assert (check["admission_form"], check["allowed"], check["agrees"]) == ("sampling-gap-only", [0, 1], code == 0)
    assert "harness_exit" in pe.IDENTIFICATION_RULES["E-11"] and "0 or 1 in the sampling-gap form" in pe.IDENTIFICATION_RULES["E-11"]


def _every_matching(candidates: list[str], options: dict[str, list[str]]):
    """Every matching of the candidates to their options, each source used
    once, as candidate -> source (None: no source): brute force."""
    for choice in itertools.product(*[[None, *options.get(c, [])] for c in candidates]):
        taken = [s for s in choice if s is not None]
        if len(taken) == len(set(taken)):
            yield dict(zip(candidates, choice))


def test_the_legitimate_assignments_are_those_an_enumeration_of_every_matching_finds() -> None:
    """E-13 reads the legitimate assignments from one maximum matching and
    its alternating paths. On 300 small random graphs (up to five
    candidates and four sources) the sources each candidate may hold in
    some maximum matching, and whether it may hold none, equal what an
    enumeration of every matching finds, whatever maximum matching the
    reading starts from; and each deficient group's least number without a
    source is the least over every matching at all, its members exactly
    the candidates with options that some maximum matching leaves without
    one."""
    import random

    rng = random.Random(20260925)
    for _ in range(300):
        candidates = [f"c{n}" for n in range(rng.randint(1, 5))]
        sources = [f"s{n}" for n in range(rng.randint(1, 4))]
        options = {c: sorted(s for s in sources if rng.random() < 0.45) for c in candidates}
        every = list(_every_matching(candidates, options))
        size = max(sum(1 for s in m.values() if s is not None) for m in every)
        maximum = [m for m in every if sum(1 for s in m.values() if s is not None) == size]
        order = list(candidates)
        rng.shuffle(order)
        start = rng.choice(maximum)
        partial = {c: s for c, s in start.items() if s is not None and rng.random() < 0.5}
        match = pe._maximum_matching(order, options, partial)
        assert len(match) == size, (options, match)
        may_go_free, possible = pe.matching_alternatives(candidates, options, match)
        assert may_go_free == {c for c in candidates if any(m[c] is None for m in maximum)}, options
        for c in candidates:
            assert possible[c] == {m[c] for m in maximum if m[c] is not None}, (options, c)
        groups = pe.deficient_groups(candidates, options)
        members = [c for group in groups for c in group["message_ids"]]
        assert len(members) == len(set(members))
        assert set(members) == {c for c in candidates if options[c] and any(m[c] is None for m in maximum)}, options
        for group in groups:
            least = min(sum(1 for c in group["message_ids"] if m[c] is None) for m in every)
            assert group["without_source_at_least"] == least >= 1, (options, group)
            assert group["sources"] == sorted({s for c in group["message_ids"] for s in options[c]})


def test_a_candidate_the_kill_cannot_explain_may_have_been_in_progress_at_a_further_death() -> None:
    """The read-only check of round 4 (P2 at name_n1_cases): a candidate
    the kill cannot explain was offered no death at all, not even a
    further death its own record said may have preceded its redelivery,
    and the run refuted. E-13 lists a further death (never named, P-4)
    among the sources an assignment may give a candidate whose redelivered
    duplicate line it may have preceded, E-10 gives a recorded death to
    such a candidate whichever device's, and E-4 cannot tell an identity
    in progress at that further death from one that was not. The readings
    record a further death between P1's last reading (1,245 s) and P2's
    first (1,265 s); every candidate is published after the restart
    command's end (host 540-542 s), so the kill cannot explain it.

    (a) N alone, redelivered at 1,270 s, the twin +1 on D1, no A5 line:
    the further death is its source in every legitimate assignment, which
    P-4 never names, so N is neither named nor R3 and nothing is refuted.
    It refuted (R3 'the kill cannot be its source', R4 beside it).
    (b) N and N2 (1,272 s), one A5 occurrence at 1,190 s, the twin +2: the
    occurrence and the further death serve both, in either order, so
    neither is named and neither R3 nor R4 stands. It refuted with an R3
    group contending for the occurrence alone and an R4 against deaths
    said to precede none of the redeliveries that their records listed.
    (c) N, N2 and N3 (1,274 s), the twin +3: two sources for three, so
    at least one has none: R3 stands on the group, the further death among
    its sources, and R4 on D1, the kill serving none of them since none
    may have been in progress at it, never read as a death that preceded
    none of their redeliveries.
    (d) N named with the occurrence in every legitimate assignment (X, on
    D3, published after the command's end and redelivered at 1,272 s, has
    only the further death; U, on D1 in the kill band, only the kill):
    X is unshown, not R3 with R4 on D3 as it read, and N keeps the further
    death among the sources it may hold in E-10's matching."""
    rows = _rows_with_a_further_death()
    log = [_a5_line(D1, 1_190 * NS)]
    N = ("n-mid", D1, 2, 540 * NS)
    N2 = ("n2-mid", D1, 3, 541 * NS)
    N3 = ("n3-mid", D1, 4, 542 * NS)
    items = [("n-mid", 2, 540, 1_270), ("n2-mid", 3, 541, 1_272), ("n3-mid", 4, 542, 1_274)]

    # (a) N alone.
    doc = _evaluate(sent=SENT + [N], lines=_duplicates(*items[:1]), extra_after={D1: 1, "seqs": [(D1, 2)]}, rows=rows)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == [] and outcome["n1_cases"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is None and r3["evidence"]["not_named_identities"] == [] and r3["evidence"]["r3_groups"] == []
    (shown,) = r3["evidence"]["cannot_show_identities"]
    assert shown["message_id"] == "n-mid" and "(E-13)" in shown["why_not_shown"]
    assert "in progress at a further death (death 1), which P-4 never names as a source" in shown["why_not_shown"]
    assert r3["evidence"]["assignments"]["may_be"]["n-mid"] == ["further-death"]
    assert r3["evidence"]["assignments"]["sources_may_hold"]["n-mid"] == ["death 1"]
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is None and r4["evidence"]["mismatches"] == [] and _criterion(doc, "S5")["holds"] is None
    evidence = r4["evidence"]["source_capacity"]
    assert evidence["possible_sources"] == {"n-mid": {"a5_lines": [], "deaths": [1]}}
    assert [(d["death"], d["kind"], d["may_precede"], d["may_serve"]) for d in evidence["deaths"]] == [
        (0, "kill", ["n-mid"], []), (1, "further", ["n-mid"], ["n-mid"]),
    ]
    assert (_capacity(doc)["matched"], _capacity(doc)["consistent"]) == (1, True)

    # (b) N and N2 beside one occurrence.
    doc = _evaluate(sent=SENT + [N, N2], lines=_duplicates(*items[:2]), extra_after={D1: 2, "seqs": [(D1, 3)]}, rows=rows, controller_log=log)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == [] and outcome["n1_cases"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is None and r3["evidence"]["r3_groups"] == [] and r3["evidence"]["not_named_identities"] == []
    shown = {c["message_id"]: c["why_not_shown"] for c in r3["evidence"]["cannot_show_identities"]}
    assert sorted(shown) == ["n-mid", "n2-mid"]
    assert all("more than one legitimate assignment" in why and "(E-13)" in why for why in shown.values())
    assert r3["evidence"]["assignments"]["may_be"] == {
        "n-mid": ["a3-connection-end", "further-death"], "n2-mid": ["a3-connection-end", "further-death"],
    }
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is None and r4["evidence"]["mismatches"] == []
    assert r4["evidence"]["source_capacity"]["possible_sources"] == {
        "n-mid": {"a5_lines": [1], "deaths": [1]}, "n2-mid": {"a5_lines": [1], "deaths": [1]},
    }
    capacity = _capacity(doc)
    assert (capacity["needed_by_device"], capacity["beyond_a5_by_device"]) == ({D1: 2}, {D1: 1})
    assert (capacity["matched"], capacity["consistent"]) == (2, True)

    # (c) three of them: at least one has no source.
    doc = _evaluate(sent=SENT + [N, N2, N3], lines=_duplicates(*items), extra_after={D1: 3, "seqs": [(D1, 4)]}, rows=rows, controller_log=log)
    outcome = _outcome(doc)
    assert outcome["result"] == "refutes" and outcome["n1_cases"] == []
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is True and r3["evidence"]["not_named_identities"] == []
    (group,) = r3["evidence"]["r3_groups"]
    assert (group["message_ids"], group["sources"], group["without_source_at_least"]) == (
        ["n-mid", "n2-mid", "n3-mid"], ["A5 line 1", "death 1"], 1,
    )
    assert "the A3 connection end of controller log line 1, death 1 (a further death)" in group["why"]
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is True and _criterion(doc, "S5")["holds"] is False
    capacity = _capacity(doc)
    assert (capacity["kill_needed"], capacity["kill_available"], capacity["matched"], capacity["consistent"]) == (2, 2, 2, False)
    assert (capacity["deaths_preceding_none"], capacity["deaths_serving_none"]) == ([], [0])
    mismatch = r4["evidence"]["mismatches"][0]
    assert mismatch["stands_on"] == [D1] and mismatch["undecided_candidates"] == ["n-mid", "n2-mid", "n3-mid"]
    assert "may have preceded none" not in mismatch["problems"][0]
    assert "the kill serving none of them" in mismatch["problems"][0]
    (refutation,) = [r for r in outcome["refutations"] if r.startswith("R4")]
    assert "may have preceded none" not in refutation and "the kill serving none of them" in refutation

    # (d) N named with the occurrence beside X, which only the further death
    # may serve, and U in the kill band.
    U = ("u-mid", D1, 3, 401 * NS)
    X = ("x-mid", D3, 1, 541 * NS)
    lines = list(LINES) + [
        ("n-mid", D1, 2, "duplicate", 1_270 * NS, None),
        ("u-mid", D1, 3, "duplicate", (K_LOWER + K_UPPER) // 2, None),
        ("x-mid", D3, 1, "duplicate", 1_272 * NS, None),
    ]
    doc = _evaluate(sent=SENT + [N, U, X], lines=lines, extra_after={D1: 2, D3: 1, "seqs": [(D1, 3), (D3, 1)]}, rows=rows, controller_log=log)
    outcome = _outcome(doc)
    assert outcome["result"] == "inconclusive" and outcome["refutations"] == []
    assert [(c["message_id"], c["source"]) for c in outcome["n1_cases"]] == [("n-mid", "a3-connection-end")]
    r3 = _criterion(doc, "R3")
    assert r3["evidence"]["assignments"]["may_be"] == {
        "n-mid": ["a3-connection-end"], "u-mid": ["kill-unshown"], "x-mid": ["further-death"],
    }
    assert r3["observed"] is None and r3["evidence"]["not_named_identities"] == []
    r4 = _criterion(doc, "R4")
    assert r4["observed"] is None and r4["evidence"]["mismatches"] == []
    assert r4["evidence"]["source_capacity"]["possible_sources"] == {
        "u-mid": {"a5_lines": [], "deaths": [0]},
        "x-mid": {"a5_lines": [], "deaths": [1]},
        "n-mid": {"a5_lines": [1], "deaths": [1], "named": {"source": "a3-connection-end", "controller_log_line": 1}},
    }
    assert (_capacity(doc)["matched"], _capacity(doc)["consistent"]) == (2, True)
    assert "offered its device's occurrences and no death" not in pe.IDENTIFICATION_RULES["E-10"]
    assert "whether or not the kill can explain it" in pe.IDENTIFICATION_RULES["E-13"]


def test_no_death_serves_a_candidate_lined_before_the_kill_nor_one_redelivered_before_it() -> None:
    """The counterpart of the check above: a further death serves a
    candidate only when it may have preceded its redelivered duplicate
    line. P, lined before the kill (its duplicate line received at
    1,100 s, before the pre-kill process's last reading at 1,150 s), keeps
    its R3 even beside a death the readings cannot place (a process PX
    whose readings carry no monotonic_ns): every recorded death is the
    pre-kill process's or a later one's, after that reading, so none may
    have preceded P's line (E-4). N, published after the restart
    command's end and redelivered at 1,230 s, before P1's last reading
    (1,245 s), keeps its R3 beside the further death placed after it; the
    R3 says so in both cases."""
    PX = "2026-09-25T10:04:10Z"
    P = ("p-mid", D1, 2, 360 * NS)
    rows = _rows() + [
        _row(_ts(250), PX, 0, 0, monotonic_ns=None, unacked=0),
        _row(_ts(265), P2, 0, 0, monotonic_ns=1_265 * NS, unacked=0),
        _row(_ts(285), P2, 0, 0, monotonic_ns=1_285 * NS, unacked=0),
    ]
    doc = _evaluate(sent=SENT + [P], lines=_duplicates(("p-mid", 2, 360, 1_100)), extra_after={D1: 1, "seqs": [(D1, 2)]}, rows=rows)
    outcome = _outcome(doc)
    assert outcome["result"] == "refutes"
    r3 = _criterion(doc, "R3")
    assert r3["observed"] is True and r3["evidence"]["cannot_show_identities"] == []
    (rejected,) = r3["evidence"]["not_named_identities"]
    assert rejected["message_id"] == "p-mid" and "lined before the kill" in rejected["why_not_named"]
    assert "nor can a further death: its duplicate line was received before the pre-kill process's last reading" in rejected["why_not_named"]
    assert r3["evidence"]["assignments"]["may_be"]["p-mid"] == ["none"]
    deaths = _criterion(doc, "R4")["evidence"]["source_capacity"]["deaths"]
    assert [(d["death"], d["placed"]) for d in deaths] == [(0, True), (1, True), (2, False)]
    assert all(d["may_precede"] == [] and d["may_serve"] == [] for d in deaths), deaths
    notes = r3["evidence"]["notes"]
    assert any(n.startswith("further death(s) 1, 2 may have preceded no duplicate-only candidate's") for n in notes), notes
    assert "none may have preceded a duplicate line received before that reading" in pe.IDENTIFICATION_RULES["E-4"]

    N = ("n-mid", D1, 2, 540 * NS)
    doc = _evaluate(sent=SENT + [N], lines=_duplicates(("n-mid", 2, 540, 1_230)), extra_after={D1: 1, "seqs": [(D1, 2)]}, rows=_rows_with_a_further_death())
    outcome = _outcome(doc)
    assert outcome["result"] == "refutes"
    r3 = _criterion(doc, "R3")
    (rejected,) = r3["evidence"]["not_named_identities"]
    assert rejected["message_id"] == "n-mid" and "published after the restart command's end" in rejected["why_not_named"]
    assert "nor can a further death, each one recorded following its redelivered duplicate line" in rejected["why_not_named"]
    deaths = _criterion(doc, "R4")["evidence"]["source_capacity"]["deaths"]
    assert [(d["death"], d["may_precede"], d["may_serve"]) for d in deaths] == [(0, ["n-mid"], []), (1, [], [])]


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
    assert set(pe.IDENTIFICATION_RULES) == {f"P-{n}" for n in range(1, 8)} | {f"E-{n}" for n in range(1, 14)}
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
    # The fault at the plan's instant (E-11): the harness schedules the
    # restart at t+150 s and records that instant; the fake run lasts about
    # a second, so the timer the harness starts fires at once instead. Only
    # run.py's view of the threading module is stubbed.
    class _PromptTimer(threading.Timer):
        def __init__(self, interval, function, args=None, kwargs=None):
            super().__init__(0.05, function, args=args, kwargs=kwargs)

    threading_view = types.SimpleNamespace(**{name: getattr(threading, name) for name in dir(threading) if not name.startswith("__")})
    threading_view.Timer = _PromptTimer
    monkeypatch.setattr(run_mod, "threading", threading_view)
    rc, run_dir, _record = _item18_run(
        tmp_path,
        plan_path,
        sim,
        monkeypatch,
        run_id=run_id,
        restart_at_s=float(pe.PROOF_RESTART_AT_S),
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
    assert manifest["restart"]["requested_at_s"] == 150.0 and manifest["restart"]["executed"] is True
    assert pe.harness_admission(manifest, run_dir)["form"] == "valid"

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
