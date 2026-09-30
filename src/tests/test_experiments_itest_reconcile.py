"""Tests for egw_experiments.itest_reconcile (runbook Sections 6 and 7 helper).

Fakes only: the controller marker (``poll_controller_marker``), the Ditto read
(``get_twin`` / ``urllib.request.urlopen``) and the clock (``time``) are
replaced in the module under test; the accounting is the UNMODIFIED
``compute_run_metrics``. No socket, no docker, no real waiting.
"""
from __future__ import annotations

import ast
import http.client
import io
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from egw_experiments import itest_reconcile as rec
from egw_experiments import protocol
from egw_experiments import run as run_mod
from egw_simulator.devices import DEVICE_TYPES, device_uuid_for

SRC_DIR = Path(__file__).resolve().parents[1]
RUNBOOK = SRC_DIR.parent / "docs" / "setup" / "qemu_integrated_gateway.md"
NS = 1_000_000_000
T0 = 5_000 * NS  # controller monotonic_ns at the end of the run
DEADLINE = T0 + protocol.CONFIRMATION_WINDOW_S * NS
RUN_ID = "itest-x"
DEV = device_uuid_for(42, "smartwatch")
RING = device_uuid_for(42, "smart_ring")
FINISHED_UTC = "2026-09-18T10:00:00.500Z"  # the simulator manifest's finished_utc
CTRL = "http://controller.invalid:8000"
DITTO = "http://ditto.invalid:8080"


# ---------------------------------------------------------------------------
# Fakes and synthetic files
# ---------------------------------------------------------------------------


def marker_record(ns: int | None, polled: str = "2026-09-18T10:00:01.000Z") -> dict:
    """Shape of run.poll_controller_marker's return value."""
    ok = ns is not None
    return {
        "url": f"{CTRL}/metrics",
        "polled_utc": polled,
        "ok": ok,
        "monotonic_ns": ns,
        "wall_utc": "2026-09-18T10:00:01.000Z" if ok else None,
        "error": None if ok else f"GET {CTRL}/metrics failed: refused",
    }


class FakeController:
    """Stands for poll_controller_marker: one scripted reading per poll."""

    def __init__(self, readings) -> None:
        self.readings = list(readings)
        self.urls: list[str] = []

    def __call__(self, controller_url, **_kwargs) -> dict:
        self.urls.append(controller_url)
        reading = self.readings.pop(0) if len(self.readings) > 1 else self.readings[0]
        return marker_record(reading)


class FakeWall:
    """Host wall clock of ``mark``: stands for utc_now_iso, and a poll costs
    ``poll_s`` seconds of it, so WHEN the stamp is taken is observable."""

    def __init__(self, controller, poll_s: float, start: str = FINISHED_UTC) -> None:
        self.controller = controller
        self.poll_s = poll_s
        self.now = datetime.fromisoformat(start.replace("Z", "+00:00"))

    def poll(self, controller_url, **kwargs) -> dict:
        # like run.poll_controller_marker: polled_utc is stamped BEFORE the request
        record = dict(self.controller(controller_url, **kwargs), polled_utc=self.utc_now_iso())
        self.now += timedelta(seconds=self.poll_s)
        return record

    def utc_now_iso(self) -> str:
        return (self.now.astimezone(timezone.utc).isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"))


def fake_mark_clock(monkeypatch, readings, poll_s: float = 0.5) -> FakeController:
    controller = FakeController(readings)
    wall = FakeWall(controller, poll_s)
    monkeypatch.setattr(rec, "poll_controller_marker", wall.poll)
    monkeypatch.setattr(rec, "utc_now_iso", wall.utc_now_iso)
    return controller


class FakeTime:
    """Stands for the time module inside itest_reconcile: sleeping is free."""

    def __init__(self) -> None:
        self.now = 1_000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records) -> None:
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )


def sent(seq: int, intended_invalid: bool = False) -> dict:
    return {"run_id": RUN_ID, "message_id": f"m{seq}", "device_uuid": DEV,
            "device_type": "smartwatch", "seq": seq,
            "intended_invalid": intended_invalid}


def event(seq: int, outcome: str, ack_ns: int | None = None,
          run_id: str = RUN_ID, device_uuid: str = DEV,
          received_ns: int = T0 - NS) -> dict:
    prefix = "m" if device_uuid == DEV else "r"
    return {"run_id": run_id, "message_id": f"{prefix}{seq}",
            "device_uuid": device_uuid, "device_type": "smartwatch",
            "seq": seq, "received_monotonic_ns": received_ns,
            "ditto_ack_monotonic_ns": ack_ns,
            "latency_ms": None if ack_ns is None else 5.0,
            "outcome": outcome, "attempts": 1, "error": None}


#: Four valid messages and one intended-invalid one. m0 confirmed in-window
#: and then redelivered (duplicate), m4 rejected, m1 confirmed EXACTLY on the
#: deadline, m2 received late and confirmed 1 ns after it (late), m3 never
#: confirmed. In the order and with the non-decreasing received stamps of a
#: real log (one consumer, one clock).
SENT = [sent(0), sent(1), sent(2), sent(3), sent(4, intended_invalid=True)]
EVENTS = [
    event(0, "accepted", T0 - 5, received_ns=T0 - 4 * NS),
    event(0, "duplicate", received_ns=T0 - 3 * NS),
    event(4, "rejected", received_ns=T0 - 2 * NS),
    event(1, "accepted", DEADLINE, received_ns=T0 - NS),
    event(2, "accepted", DEADLINE + 1, received_ns=DEADLINE - NS),
]


def sim_manifest(**changes) -> dict:
    """The fields of the simulator manifest (egw_simulator/output.py) read here."""
    manifest = {"run_id": RUN_ID, "scenario": "smoke", "seed": 42,
                "finished_utc": FINISHED_UTC, "completed": True,
                "totals": {"sent": len(SENT), "intended_invalid": 1}}
    manifest.update(changes)
    return manifest


def make_run(tmp_path: Path, events=EVENTS, name: str = RUN_ID, sent_records=SENT,
             manifest: dict | None = None) -> Path:
    run_dir = tmp_path / name
    run_dir.mkdir()
    write_json(run_dir / "manifest.json", manifest or sim_manifest())
    write_jsonl(run_dir / "sent_events.jsonl", sent_records)
    if events is not None:
        write_jsonl(run_dir / "events.jsonl", events)
    return run_dir


def stored_marker(ns: int = T0, **changes) -> dict:
    record = dict(
        marker_record(ns),
        confirmation_window_s=protocol.CONFIRMATION_WINDOW_S,
        confirmation_deadline_monotonic_ns=ns + protocol.CONFIRMATION_WINDOW_S * NS,
        lag_s=0.5,
        lag_tolerance_s=run_mod.CONTROLLER_MARKER_LAG_TOLERANCE_S,
    )
    record.update(changes)
    return record


def close_window(run_dir: Path, closed_ns: int = DEADLINE + 1) -> None:
    """Marker and window file as mark/wait leave them; events fetched later."""
    write_json(rec.sib(str(run_dir), ".marker.json"), stored_marker())
    closed = rec.sib(str(run_dir), ".window-closed.json")
    write_json(closed, marker_record(closed_ns))
    os.utime(closed, (1_000, 1_000))
    events = run_dir / "events.jsonl"
    if events.is_file():
        os.utime(events, (2_000, 2_000))


def twins(accepted_count, last_run_id="old", last_seq=9, exists=True,
          device_uuid: str = DEV, device_type: str = "smartwatch") -> dict:
    return {"label": "x", "seed": 42, "devices": {device_uuid: {
        "device_type": device_type, "exists": exists,
        "ingestion": {"last_run_id": last_run_id, "last_seq": last_seq,
                      "last_message_id": None, "last_ts": None,
                      "accepted_count": accepted_count}}}}


def ring_twins(accepted_count, **kwargs) -> dict:
    return twins(accepted_count, device_uuid=RING, device_type="smart_ring", **kwargs)


def both(first: dict, second: dict) -> dict:
    """One snapshot holding the devices of two."""
    return dict(first, devices={**first["devices"], **second["devices"]})


def metrics(started_at="2026-09-18T09:00:00.000Z", queue_depth=0, **counters) -> dict:
    body = {"accepted": 100, "rejected": 0, "duplicate": 0, "failed": 0,
            "dropped": 0, "queue_depth": queue_depth, "started_at": started_at}
    body.update(counters)
    return body


def make_delta_fixture(tmp_path: Path, *, after_count=503, after_metrics=None) -> Path:
    """EVENTS holds three accepted records (the late one included), one
    duplicate and one rejected."""
    run_dir = make_run(tmp_path)
    prefix = str(run_dir)
    write_json(rec.sib(prefix, ".twins.before.json"), twins(500))
    write_json(rec.sib(prefix, ".twins.after.json"),
               twins(after_count, last_run_id=RUN_ID, last_seq=2))
    write_json(rec.sib(prefix, ".metrics.before.json"), metrics())
    write_json(rec.sib(prefix, ".metrics.after.json"),
               after_metrics or metrics(accepted=103, duplicate=1, rejected=1))
    return run_dir


def listing(run_dir: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(run_dir.iterdir())}


# ---------------------------------------------------------------------------
# Module-level rules
# ---------------------------------------------------------------------------


def test_window_and_tolerance_are_the_harness_objects_not_redefined() -> None:
    assert rec.CONFIRMATION_WINDOW_S is protocol.CONFIRMATION_WINDOW_S
    assert rec.CONTROLLER_MARKER_LAG_TOLERANCE_S is run_mod.CONTROLLER_MARKER_LAG_TOLERANCE_S
    assert rec.poll_controller_marker is run_mod.poll_controller_marker
    tree = ast.parse(Path(rec.__file__).read_text(encoding="utf-8"))
    assigned = {
        target.id
        for node in ast.walk(tree) if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    assert "CONFIRMATION_WINDOW_S" not in assigned
    assert "CONTROLLER_MARKER_LAG_TOLERANCE_S" not in assigned


def test_exit_codes_are_distinct_and_documented() -> None:
    codes = [rec.EXIT_OK, rec.EXIT_FAILED, rec.EXIT_NOT_PROTOCOL, rec.EXIT_MISMATCH]
    assert codes == [0, 1, 3, 4]  # 2 is argparse's usage error
    for code in (0, 1, 2, 3, 4):
        assert f"- {code}  " in rec.__doc__


def _python(*args: str, code: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(SRC_DIR))
    cmd = [sys.executable, "-c", code] if code else [sys.executable, *args]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)


def test_import_opens_no_socket() -> None:
    proc = _python(code=(
        "import socket\n"
        "def boom(*a, **k): raise AssertionError('network access at import time')\n"
        "class NoSocket(socket.socket):\n"
        "    def __init__(self, *a, **k): boom()\n"
        "socket.socket = NoSocket\n"
        "socket.create_connection = boom\n"
        "socket.getaddrinfo = boom\n"
        "import egw_experiments.itest_reconcile as m\n"
        "print(m.__file__)\n"
    ))
    assert proc.returncode == 0, proc.stderr
    assert Path(proc.stdout.strip()).resolve() == Path(rec.__file__).resolve()


def test_runs_as_a_module_and_help_exits_zero() -> None:
    proc = _python("-m", "egw_experiments.itest_reconcile", "--help")
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""  # no runpy double-import warning either
    for sub in ("mark", "wait", "check", "snap", "delta", "same", "acceptance", "replay-check"):
        assert sub in proc.stdout
    assert "exit codes" in proc.stdout
    # the module's own synopsis names every subcommand too
    assert "{mark,wait,check,snap,delta,same,acceptance,replay-check}" in rec.__doc__.splitlines()[2]


def test_usage_errors_exit_2(capsys) -> None:
    for argv in ([], ["bogus"], ["snap", "--label", "x"], ["same", "--prefix", "p", "a"],
                 ["acceptance", "p/r"], ["replay-check", "p/r"]):
        with pytest.raises(SystemExit) as excinfo:
            rec.main(argv)
        assert excinfo.value.code == 2
    capsys.readouterr()


REC_FRAGMENT = re.compile(  # not the quoted mentions inside shell comments
    r"(?<!')\$REC ((?:mark|wait|check|snap|delta|same|acceptance|replay-check)\b.*?)(?=;|&&|\|\||[)}>]|\s#|$)"
)
SHELL_VARIABLE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")


def runbook_rec_fragments() -> list[list[str]]:
    """Every ``$REC <subcommand> ...`` of the runbook's fenced code, as argv.

    A fragment ends where the shell command does (``;``, ``&&``, ``||``, ``)``,
    ``}``, a redirection, a comment); ``"$@"`` is dropped and every other shell
    variable becomes ``1``, which is a valid path, label, URL and seed.
    """
    fragments, fenced = [], False
    for line in RUNBOOK.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif fenced:
            for match in REC_FRAGMENT.finditer(line):
                text = SHELL_VARIABLE.sub("1", match.group(1).replace('"$@"', ""))
                fragments.append(shlex.split(text))
    return fragments


def test_every_rec_command_line_of_the_runbook_parses() -> None:
    fragments = runbook_rec_fragments()
    # anchors: an extraction that no longer finds the lines FAILS, never skips
    assert len(fragments) >= 15
    assert {argv[0] for argv in fragments} == set(rec.COMMANDS)
    # --events is exercised by test 6's delta line; the runbook's only --also
    # example (the warm-up variant) was withdrawn on 2026-09-25 and the variant
    # deferred, so --also is documented by the parser's own tests, not anchored
    # here (test_runbook_itest_helpers holds test 6's commands to no --also).
    assert any("--events" in argv for argv in fragments)
    assert any("--like" in argv for argv in fragments)
    parser = rec.build_parser()
    for argv in fragments:
        try:
            parser.parse_args(argv)
        except SystemExit:
            pytest.fail(f"usage error for the runbook's: $REC {' '.join(argv)}")


def test_runbook_judges_test_3_and_test_4_per_identity_with_their_own_copies() -> None:
    """Decisions 3 and 4 of 2026-09-30: test 3's acceptance line reads the copy kept after the drain, test 4's replay
    check the replay's own sent records and the pre-replay copy (shell variables read as 1, '~' kept literal)."""
    fragments = runbook_rec_fragments()
    assert [argv for argv in fragments if argv[0] == "acceptance"] == [
        ["acceptance", "1/1", "--events", "1/1.events.post-drain.jsonl"]]
    assert [argv for argv in fragments if argv[0] == "replay-check"] == [
        ["replay-check", "1/1", "--replay-dir", "~/egw-tcg/itest-replay/1",
         "--events-before", "1/1.events.pre-replay.jsonl"]]


def test_command_line_defaults_and_destinations() -> None:
    parse = rec.build_parser().parse_args
    assert parse(["mark", "p/r"]).controller_url == "http://127.0.0.1:8000"
    assert parse(["wait", "p/r", "--controller-url", CTRL]).extra_timeout == 120.0
    assert parse(["check", "p/r", "--controller-url", CTRL]).run_dir == "p/r"
    snap = parse(["snap", "--prefix", "p/r", "--label", "before", "--seed", "42",
                  "--devices", "smartwatch", "--ditto-url", DITTO])
    assert (snap.seed, snap.devices, snap.like) == (42, "smartwatch", "before")
    assert parse(["snap", "--prefix", "p", "--label", "x"]).devices == ",".join(DEVICE_TYPES)
    assert parse(["snap", "--prefix", "p", "--label", "x"]).ditto_url == "http://127.0.0.1:8080"
    delta = parse(["delta", "raw/r", "--prefix", "p/r", "--also", "a", "--also", "b"])
    assert (delta.prefix, delta.frm, delta.to, delta.also) == ("p/r", "before", "after", ["a", "b"])
    assert delta.events is None  # the run directory's events.jsonl
    assert parse(["delta", "raw/r", "--events", "raw/r/events.post-drain.jsonl"]).events == (
        "raw/r/events.post-drain.jsonl"
    )
    same = parse(["same", "--prefix", "p/r", "after", "post-restart"])
    assert (same.label_a, same.label_b) == ("after", "post-restart")
    acceptance = parse(["acceptance", "p/r", "--events", "p/r.events.post-drain.jsonl"])
    assert (acceptance.run_dir, acceptance.events) == ("p/r", "p/r.events.post-drain.jsonl")
    replay = parse(["replay-check", "p/r", "--replay-dir", "x/r"])
    assert (replay.run_dir, replay.replay_dir, replay.prefix, replay.events_before, replay.frm, replay.to) == (
        "p/r", "x/r", None, None, "after", "replay")


# ---------------------------------------------------------------------------
# mark
# ---------------------------------------------------------------------------


def test_mark_writes_the_controller_clock_deadline(tmp_path, monkeypatch, capsys) -> None:
    run_dir = make_run(tmp_path, events=None)
    before = listing(run_dir)
    controller = fake_mark_clock(monkeypatch, [T0], poll_s=0.5)
    assert rec.main(["mark", str(run_dir), "--controller-url", CTRL]) == 0
    marker = json.loads((tmp_path / f"{RUN_ID}.marker.json").read_text("utf-8"))
    assert controller.urls == [CTRL]
    assert marker["monotonic_ns"] == T0
    assert marker["confirmation_window_s"] == protocol.CONFIRMATION_WINDOW_S
    assert marker["confirmation_deadline_monotonic_ns"] == DEADLINE
    assert marker["lag_s"] == pytest.approx(0.5)
    assert marker["polled_utc"] == FINISHED_UTC  # as recorded by the poll
    assert marker["poll_returned_utc"] == "2026-09-18T10:00:01.000Z"
    assert marker["lag_tolerance_s"] == run_mod.CONTROLLER_MARKER_LAG_TOLERANCE_S
    captured = capsys.readouterr()
    assert f"marker monotonic_ns={T0} lag_s=0.5" in captured.out
    assert "WARNING" not in captured.err
    assert listing(run_dir) == before  # the simulator run directory is untouched


def test_mark_is_write_once(tmp_path, monkeypatch, capsys) -> None:
    run_dir = make_run(tmp_path, events=None)
    monkeypatch.setattr(rec, "poll_controller_marker", FakeController([T0, T0 + 7 * NS]))
    assert rec.main(["mark", str(run_dir)]) == 0
    first = (tmp_path / f"{RUN_ID}.marker.json").read_bytes()
    assert rec.main(["mark", str(run_dir)]) == 1
    assert "refusing to overwrite" in capsys.readouterr().err
    assert (tmp_path / f"{RUN_ID}.marker.json").read_bytes() == first


def test_mark_exits_1_and_writes_nothing_when_the_marker_is_unavailable(
    tmp_path, monkeypatch, capsys
) -> None:
    run_dir = make_run(tmp_path, events=None)
    monkeypatch.setattr(rec, "poll_controller_marker", FakeController([None]))
    assert rec.main(["mark", str(run_dir)]) == 1
    assert "marker UNAVAILABLE" in capsys.readouterr().err
    assert not (tmp_path / f"{RUN_ID}.marker.json").exists()


def test_mark_counts_the_lag_up_to_the_return_of_a_slow_poll(tmp_path, monkeypatch, capsys) -> None:
    # The poll STARTS with no lag at all and takes 3 s: the controller clock was
    # read somewhere in between, so the harness rule (stamp after the poll has
    # returned) gives 3 s, above the tolerance. polled_utc alone would say 0.
    run_dir = make_run(tmp_path, events=None)
    fake_mark_clock(monkeypatch, [T0], poll_s=3.0)
    assert rec.main(["mark", str(run_dir)]) == 0
    assert "WARNING: marker lag" in capsys.readouterr().err
    marker = json.loads((tmp_path / f"{RUN_ID}.marker.json").read_text("utf-8"))
    assert marker["polled_utc"] == FINISHED_UTC
    assert marker["lag_s"] == pytest.approx(3.0)
    assert marker["confirmation_deadline_monotonic_ns"] == DEADLINE  # never moved by the lag


def test_mark_does_not_warn_on_the_tolerance_itself(tmp_path, monkeypatch, capsys) -> None:
    run_dir = make_run(tmp_path, events=None)
    fake_mark_clock(monkeypatch, [T0], poll_s=run_mod.CONTROLLER_MARKER_LAG_TOLERANCE_S)
    assert rec.main(["mark", str(run_dir)]) == 0
    captured = capsys.readouterr()
    assert f"lag_s={run_mod.CONTROLLER_MARKER_LAG_TOLERANCE_S}" in captured.out
    assert "WARNING" not in captured.err


def test_mark_warns_on_a_negative_lag_and_records_it_as_computed(tmp_path, monkeypatch, capsys) -> None:
    # finished_utc AFTER the poll returned: a stepped host clock or another run's manifest
    run_dir = make_run(tmp_path, events=None,
                       manifest=sim_manifest(finished_utc="2026-09-18T10:00:09.000Z"))
    fake_mark_clock(monkeypatch, [T0], poll_s=0.5)
    assert rec.main(["mark", str(run_dir)]) == 0
    assert "WARNING: marker lag unknown, negative" in capsys.readouterr().err
    marker = json.loads((tmp_path / f"{RUN_ID}.marker.json").read_text("utf-8"))
    assert marker["lag_s"] == pytest.approx(-8.0)


@pytest.mark.parametrize("manifest_text", [None, "{not json", "[]", '{"finished_utc": 5}'])
def test_mark_keeps_the_marker_when_the_lag_is_not_computable(
    tmp_path, monkeypatch, capsys, manifest_text
) -> None:
    run_dir = tmp_path / RUN_ID
    run_dir.mkdir()
    if manifest_text is not None:
        (run_dir / "manifest.json").write_text(manifest_text, "utf-8")
    monkeypatch.setattr(rec, "poll_controller_marker", FakeController([T0]))
    assert rec.main(["mark", str(run_dir)]) == 0
    assert "WARNING: marker lag unknown" in capsys.readouterr().err
    marker = json.loads((tmp_path / f"{RUN_ID}.marker.json").read_text("utf-8"))
    assert marker["lag_s"] is None
    assert marker["confirmation_deadline_monotonic_ns"] == DEADLINE


# ---------------------------------------------------------------------------
# wait
# ---------------------------------------------------------------------------


def _wait_fixture(tmp_path, monkeypatch, readings, marker=None):
    run_dir = make_run(tmp_path, events=None)
    write_json(rec.sib(str(run_dir), ".marker.json"), marker or stored_marker())
    clock = FakeTime()
    controller = FakeController(readings)
    monkeypatch.setattr(rec, "time", clock)
    monkeypatch.setattr(rec, "poll_controller_marker", controller)
    return run_dir, clock, controller


def test_wait_closes_only_strictly_after_the_deadline(tmp_path, monkeypatch, capsys) -> None:
    # unreachable, then before, then EXACTLY on the deadline, then 1 ns after
    run_dir, clock, controller = _wait_fixture(
        tmp_path, monkeypatch, [None, DEADLINE - NS, DEADLINE, DEADLINE + 1]
    )
    assert rec.main(["wait", str(run_dir), "--controller-url", CTRL]) == 0
    assert clock.sleeps == [rec.WAIT_POLL_INTERVAL_S] * 3
    assert controller.urls == [CTRL] * 4
    closed = json.loads((tmp_path / f"{RUN_ID}.window-closed.json").read_text("utf-8"))
    assert closed["monotonic_ns"] == DEADLINE + 1
    assert "window closed on the controller clock" in capsys.readouterr().out


def test_wait_exits_1_when_the_controller_clock_goes_backwards(
    tmp_path, monkeypatch, capsys
) -> None:
    run_dir, _clock, _ = _wait_fixture(tmp_path, monkeypatch, [T0 - 1])
    assert rec.main(["wait", str(run_dir)]) == 1
    assert "BACKWARDS" in capsys.readouterr().err
    assert not (tmp_path / f"{RUN_ID}.window-closed.json").exists()


def test_wait_gives_up_after_window_plus_extra_timeout(tmp_path, monkeypatch, capsys) -> None:
    run_dir, clock, _ = _wait_fixture(tmp_path, monkeypatch, [None])
    assert rec.main(["wait", str(run_dir), "--extra-timeout", "4"]) == 1
    assert "gave up" in capsys.readouterr().err
    budget = protocol.CONFIRMATION_WINDOW_S + 4
    assert budget < sum(clock.sleeps) <= budget + rec.WAIT_POLL_INTERVAL_S
    assert not (tmp_path / f"{RUN_ID}.window-closed.json").exists()


def test_wait_without_a_marker_exits_1(tmp_path, monkeypatch, capsys) -> None:
    run_dir = make_run(tmp_path, events=None)
    monkeypatch.setattr(rec, "poll_controller_marker", FakeController([DEADLINE + 1]))
    assert rec.main(["wait", str(run_dir)]) == 1
    assert "marker.json missing" in capsys.readouterr().err


def test_wait_refuses_a_second_window_file(tmp_path, monkeypatch, capsys) -> None:
    run_dir, _clock, _ = _wait_fixture(tmp_path, monkeypatch, [DEADLINE + 1])
    assert rec.main(["wait", str(run_dir)]) == 0
    assert rec.main(["wait", str(run_dir)]) == 1
    assert "refusing to overwrite" in capsys.readouterr().err


@pytest.mark.parametrize("changes", [
    {"confirmation_deadline_monotonic_ns": T0 + 3 * NS},   # a shorter window
    {"confirmation_deadline_monotonic_ns": DEADLINE + NS},  # a longer one
    {"confirmation_window_s": 3},
    {"ok": False},
    {"monotonic_ns": None},
    {"monotonic_ns": True},
])
def test_a_marker_file_with_another_window_is_refused_by_wait_and_check(
    tmp_path, monkeypatch, capsys, changes
) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir)
    write_json(rec.sib(str(run_dir), ".marker.json"), stored_marker(**changes))
    monkeypatch.setattr(rec, "time", FakeTime())
    monkeypatch.setattr(rec, "poll_controller_marker", FakeController([DEADLINE + 10 * NS]))
    assert rec.main(["wait", str(run_dir)]) == 1
    assert rec.main(["check", str(run_dir)]) == 1
    assert not (tmp_path / f"{RUN_ID}.reconcile.json").exists()
    capsys.readouterr()


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


def test_check_applies_the_harness_rule_on_the_controller_marker(tmp_path, capsys) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir)
    before = listing(run_dir)
    # lost > 0 and the exit status is still 0: check reports, it does not judge
    assert rec.main(["check", str(run_dir), "--controller-url", CTRL]) == 0
    out = json.loads((tmp_path / f"{RUN_ID}.reconcile.json").read_text("utf-8"))
    captured = capsys.readouterr()
    assert json.loads(captured.out) == out
    assert captured.err == ""
    assert out["run_id"] == RUN_ID
    assert out["confirmation_deadline_source"] == "controller-marker"
    assert out["sent_total"] == 5 and out["sent_valid"] == 4
    assert out["delivered_unique"] == 2  # m0, and m1 exactly ON the deadline
    assert out["late_confirmations"] == 1  # m2, 1 ns after the deadline
    assert out["lost"] == 2  # m2 (late) and m3 (never confirmed)
    assert out["duplicates"] == 1
    assert out["double_accepted"] == 0
    assert out["rejected_intended_invalid"] == 1
    assert out["events_accepted_total"] == 3
    assert out["marker_lag_s"] == 0.5
    assert out["sim_completed"] is True and out["sim_totals"]["sent"] == 5
    assert "EMULATED" in out["latency_label"]
    assert out["warnings"] == []
    manifest = json.loads((tmp_path / f"{RUN_ID}.reconcile" / "manifest.json").read_text("utf-8"))
    assert "NOT a harness run" in manifest["manifest_kind"]
    assert manifest["confirmation_window_s"] == protocol.CONFIRMATION_WINDOW_S
    assert manifest["confirmation_deadline_monotonic_ns"] == DEADLINE
    assert manifest["confirmation_deadline_clock_domain"] == "controller"
    assert listing(run_dir) == before


def test_check_counts_a_repeated_accepted_record_as_double_accepted(tmp_path, capsys) -> None:
    # received on the same stamp as the record before it: equal is not backwards
    again = event(0, "accepted", DEADLINE - 1, received_ns=DEADLINE - NS)
    run_dir = make_run(tmp_path, events=EVENTS + [again])
    close_window(run_dir)
    assert rec.main(["check", str(run_dir)]) == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert (out["delivered_unique"], out["double_accepted"]) == (2, 1)
    assert out["warnings"] == ["repeated accepted event for message_id m0"]
    assert "WARNING: 1 warning(s) in the row above" in captured.err


def test_check_is_repeatable_and_rebuilds_its_derived_files(tmp_path, capsys) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir)
    assert rec.main(["check", str(run_dir)]) == 0
    stale = tmp_path / f"{RUN_ID}.reconcile" / "stale.txt"
    stale.write_text("x", "utf-8")
    write_jsonl(run_dir / "events.jsonl",
                EVENTS + [event(3, "accepted", DEADLINE - 1, received_ns=DEADLINE - NS)])
    os.utime(run_dir / "events.jsonl", (3_000, 3_000))
    assert rec.main(["check", str(run_dir)]) == 0
    assert not stale.exists()
    out = json.loads((tmp_path / f"{RUN_ID}.reconcile.json").read_text("utf-8"))
    assert (out["delivered_unique"], out["lost"]) == (3, 1)
    capsys.readouterr()


def test_a_check_that_stops_does_not_leave_the_row_of_an_earlier_one(tmp_path, capsys) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir)
    assert rec.main(["check", str(run_dir)]) == 0
    assert (tmp_path / f"{RUN_ID}.reconcile.json").is_file()
    # passes the helper's own reading and fails inside the harness accounting
    bad = dict(event(3, "accepted", DEADLINE - 1, received_ns=DEADLINE - NS), latency_ms="fast")
    write_jsonl(run_dir / "events.jsonl", EVENTS + [bad])
    assert rec.main(["check", str(run_dir)]) == 1
    assert "error: compute_run_metrics cannot read the run files" in capsys.readouterr().err
    assert not (tmp_path / f"{RUN_ID}.reconcile.json").exists()


@pytest.mark.parametrize("key", rec.STAMPS)
@pytest.mark.parametrize("value", ["9999999999999999", 1.5, True])
def test_check_exits_1_on_a_stamp_that_is_neither_an_integer_nor_null(
    tmp_path, capsys, key, value
) -> None:
    bad = dict(event(3, "accepted", DEADLINE - 1, received_ns=DEADLINE - NS), **{key: value})
    run_dir = make_run(tmp_path, events=EVENTS + [bad])
    close_window(run_dir)
    assert rec.main(["check", str(run_dir)]) == 1  # 'error: ...', never a traceback
    err = capsys.readouterr().err
    assert err.startswith("error: ") and f"record 6: {key}" in err
    assert not (tmp_path / f"{RUN_ID}.reconcile").exists()


@pytest.mark.parametrize("kwargs,expected", [
    ({"sent_records": SENT[:3]},  # cut at a line boundary: the strict reader cannot see it
     "sent_events.jsonl holds 3 record(s) but the simulator manifest says totals.sent=5"),
    ({"sent_records": []}, "sent_events.jsonl holds 0 record(s)"),
    ({"manifest": sim_manifest(completed=False)}, "completed is not true"),
    ({"manifest": sim_manifest(totals={"sent": "5"})}, "no integer totals.sent"),
    ({"manifest": sim_manifest(totals=None)}, "no integer totals.sent"),
    ({"manifest": sim_manifest(run_id="itest-other")},
     "5 record(s) of sent_events.jsonl carry a run_id other than the simulator manifest's"),
    ({"manifest": sim_manifest(run_id="itest-other")},
     "5 record(s) of events.jsonl carry a run_id other than the simulator manifest's"),
])
def test_check_warns_when_the_files_are_not_shown_to_be_this_runs_and_whole(
    tmp_path, capsys, kwargs, expected
) -> None:
    run_dir = make_run(tmp_path, **kwargs)
    close_window(run_dir)
    assert rec.main(["check", str(run_dir)]) == 0  # it reports, it does not judge
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert [w for w in out["warnings"] if expected in w], out["warnings"]
    assert "warning(s) in the row above" in captured.err


def test_check_warns_when_the_controller_clock_restarts_along_the_log(tmp_path, capsys) -> None:
    # Guest reboot after the window closed: m3 is confirmed with 30 s of NEW
    # uptime, which compares as in-window against a deadline of the old clock.
    # A second reboot follows, so the count and the record of the FIRST
    # decrease are both observable (record 6 carries no stamp and is skipped).
    no_stamp = dict(event(4, "rejected"), received_monotonic_ns=None)
    rebooted = event(3, "accepted", 30 * NS, received_ns=29 * NS)
    later = event(0, "duplicate", received_ns=40 * NS)
    rebooted_again = event(0, "duplicate", received_ns=10 * NS)
    run_dir = make_run(
        tmp_path, events=EVENTS + [no_stamp, rebooted, later, rebooted_again])
    close_window(run_dir)
    assert rec.main(["check", str(run_dir)]) == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["delivered_unique"] == 3  # the harness rule, as it is
    assert out["warnings"][0].startswith(
        "controller clock went BACKWARDS along events.jsonl (2 time(s), first at record 7;")
    assert "NOT a protocol check for them" in out["warnings"][0]
    assert "WARNING: 1 warning(s)" in captured.err


def test_check_without_a_marker_exits_3_on_the_legacy_deadline(tmp_path, capsys) -> None:
    run_dir = make_run(tmp_path)
    assert rec.main(["check", str(run_dir)]) == 3
    captured = capsys.readouterr()
    assert "NOT a protocol check" in captured.err
    out = json.loads((tmp_path / f"{RUN_ID}.reconcile.json").read_text("utf-8"))
    assert out["confirmation_deadline_source"] == "event-derived-legacy"
    # the circular legacy rule cannot see the late confirmation: the late
    # message moved its own deadline (max received_monotonic_ns + window)
    assert out["late_confirmations"] == 0 and out["lost"] == 1
    assert out["marker_lag_s"] is None
    assert any(w.startswith("LEGACY/UNVERIFIABLE") for w in out["warnings"])


def test_check_refuses_before_wait(tmp_path, capsys) -> None:
    run_dir = make_run(tmp_path)
    write_json(rec.sib(str(run_dir), ".marker.json"), stored_marker())
    assert rec.main(["check", str(run_dir)]) == 1
    assert "run 'wait' before fetching" in capsys.readouterr().err
    assert not (tmp_path / f"{RUN_ID}.reconcile.json").exists()


@pytest.mark.parametrize("closed_ns", [DEADLINE, DEADLINE - NS, None])
def test_check_refuses_a_window_file_not_past_the_deadline(tmp_path, capsys, closed_ns) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir, closed_ns=closed_ns)
    assert rec.main(["check", str(run_dir)]) == 1
    assert "past the deadline" in capsys.readouterr().err


def test_check_refuses_events_fetched_before_the_window_closed(tmp_path, capsys) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir)
    os.utime(run_dir / "events.jsonl", (999, 999))
    assert rec.main(["check", str(run_dir)]) == 1
    assert "fetched BEFORE the window closed" in capsys.readouterr().err
    assert not (tmp_path / f"{RUN_ID}.reconcile.json").exists()


@pytest.mark.parametrize("missing", ["sent_events.jsonl", "events.jsonl", "manifest.json"])
def test_check_exits_1_on_a_missing_input(tmp_path, capsys, missing) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir)
    (run_dir / missing).unlink()
    assert rec.main(["check", str(run_dir)]) == 1
    assert f"{missing} missing" in capsys.readouterr().err


@pytest.mark.parametrize("name,text", [
    ("events.jsonl", '{"outcome": "accepted", "message_id": "m0"'),  # truncated fetch
    ("events.jsonl", "[1, 2]\n"),
    ("sent_events.jsonl", "not json\n"),
    ("manifest.json", "{"),
    ("manifest.json", "[]"),
])
def test_check_exits_1_on_a_malformed_input(tmp_path, capsys, name, text) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir)
    (run_dir / name).write_text(text, "utf-8")
    os.utime(run_dir / name, (2_000, 2_000))
    assert rec.main(["check", str(run_dir)]) == 1
    assert name in capsys.readouterr().err
    assert not (tmp_path / f"{RUN_ID}.reconcile.json").exists()


@pytest.mark.parametrize("sibling", [".marker.json", ".window-closed.json"])
def test_check_exits_1_on_a_malformed_sibling(tmp_path, capsys, sibling) -> None:
    run_dir = make_run(tmp_path)
    close_window(run_dir)
    rec.sib(str(run_dir), sibling).write_text("{truncated", "utf-8")
    assert rec.main(["check", str(run_dir)]) == 1
    assert "unreadable" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# snap
# ---------------------------------------------------------------------------


def _twin(accepted_count: int, last_seq: int) -> dict:
    return {"thingId": f"org.c2dta:{DEV}", "features": {"ingestion": {"properties": {
        "last_run_id": RUN_ID, "last_seq": last_seq, "last_message_id": "m",
        "last_ts": "2026-09-18T10:00:00.000Z", "accepted_count": accepted_count,
        "not_copied": 1}}}}


def test_snap_by_seed_records_existing_and_absent_twins(tmp_path, monkeypatch, capsys) -> None:
    ring = device_uuid_for(42, "smart_ring")
    calls = []

    def fake_get_twin(ditto_url, device_uuid):
        calls.append((ditto_url, device_uuid))
        return _twin(500, 9) if device_uuid == DEV else None  # 404 -> None

    monkeypatch.setattr(rec, "get_twin", fake_get_twin)
    prefix = str(tmp_path / RUN_ID)
    assert rec.main(["snap", "--prefix", prefix, "--label", "before", "--seed", "42",
                     "--devices", "smartwatch,smart_ring", "--ditto-url", DITTO]) == 0
    snap = json.loads((tmp_path / f"{RUN_ID}.twins.before.json").read_text("utf-8"))
    assert json.loads(capsys.readouterr().out) == snap
    assert calls == [(DITTO, DEV), (DITTO, ring)]
    assert (snap["label"], snap["seed"]) == ("before", 42)
    assert snap["devices"][DEV] == {
        "device_type": "smartwatch", "exists": True,
        "ingestion": {"last_run_id": RUN_ID, "last_seq": 9, "last_message_id": "m",
                      "last_ts": "2026-09-18T10:00:00.000Z", "accepted_count": 500}}
    assert snap["devices"][ring] == {
        "device_type": "smart_ring", "exists": False,
        "ingestion": dict.fromkeys(rec.INGESTION_KEYS)}


def test_snap_like_reuses_the_devices_of_another_label_and_is_write_once(
    tmp_path, monkeypatch, capsys
) -> None:
    prefix = str(tmp_path / RUN_ID)
    write_json(rec.sib(prefix, ".twins.after.json"), twins(503))
    monkeypatch.setattr(rec, "get_twin", lambda url, uuid: _twin(503, 2))
    argv = ["snap", "--prefix", prefix, "--label", "post-restart", "--like", "after"]
    assert rec.main(argv) == 0
    path = tmp_path / f"{RUN_ID}.twins.post-restart.json"
    snap = json.loads(path.read_text("utf-8"))
    assert list(snap["devices"]) == [DEV] and snap["seed"] is None
    first = path.read_bytes()
    assert rec.main(argv) == 1
    assert "refusing to overwrite" in capsys.readouterr().err
    assert path.read_bytes() == first


def test_snap_exits_1_without_the_like_snapshot(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(rec, "get_twin", lambda url, uuid: None)
    assert rec.main(["snap", "--prefix", str(tmp_path / RUN_ID), "--label", "after"]) == 1
    assert "twins.before.json missing" in capsys.readouterr().err


def test_snap_refuses_an_empty_device_selection(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(rec, "get_twin", lambda url, uuid: pytest.fail("no read expected"))
    assert rec.main(["snap", "--prefix", str(tmp_path / RUN_ID), "--label", "before",
                     "--seed", "42", "--devices", ""]) == 1
    assert "no device selected" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_snap_exits_1_on_an_unknown_device_type(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(rec, "get_twin", lambda url, uuid: None)
    assert rec.main(["snap", "--prefix", str(tmp_path / RUN_ID), "--label", "before",
                     "--seed", "42", "--devices", "toaster"]) == 1
    assert "unknown device types" in capsys.readouterr().err


@pytest.mark.parametrize("failure", [
    urllib.error.URLError("connection refused"),
    urllib.error.HTTPError("u", 503, "unavailable", None, None),
    ValueError("not json"),
])
def test_snap_writes_nothing_when_a_twin_cannot_be_read(
    tmp_path, monkeypatch, capsys, failure
) -> None:
    def fake_get_twin(ditto_url, device_uuid):
        if device_uuid != DEV:
            raise failure
        return _twin(1, 1)

    monkeypatch.setattr(rec, "get_twin", fake_get_twin)
    assert rec.main(["snap", "--prefix", str(tmp_path / RUN_ID), "--label", "before",
                     "--seed", "42"]) == 1
    assert "GET thing" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_get_twin_sends_the_pre_authenticated_header_and_maps_404_to_none(monkeypatch) -> None:
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append((req.full_url, dict(req.header_items()), timeout))
        if len(seen) == 1:
            return _Resp(json.dumps(_twin(7, 3)).encode("utf-8"))
        raise urllib.error.HTTPError(req.full_url, 404 if len(seen) == 2 else 500, "x", None, None)

    monkeypatch.setattr(rec.urllib.request, "urlopen", fake_urlopen)
    assert rec.get_twin(DITTO + "/", DEV)["thingId"] == f"org.c2dta:{DEV}"
    assert rec.get_twin(DITTO, DEV) is None
    with pytest.raises(urllib.error.HTTPError):
        rec.get_twin(DITTO, DEV)
    url, headers, timeout = seen[0]
    assert url == f"{DITTO}/api/2/things/org.c2dta:{DEV}"
    assert {k.lower(): v for k, v in headers.items()} == {
        "x-ditto-pre-authenticated": "pre:egw-controller"}
    assert timeout is not None


# ---------------------------------------------------------------------------
# delta
# ---------------------------------------------------------------------------


def test_delta_matches_twin_and_metrics_deltas_with_the_event_log(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path)
    assert rec.main(["delta", str(run_dir)]) == 0
    out = capsys.readouterr().out
    # late and repeated accepted records count: the twin counter moved for each
    assert f"{DEV} smartwatch: existed_before=True accepted_count 500 -> 503 (delta 3)" in out
    assert "accepted records in events.jsonl 3" in out
    assert f"last_run_id {RUN_ID} last_seq 2: OK" in out
    assert "/metrics accepted: 100 -> 103 (delta 3); events.jsonl 3: OK" in out
    assert "/metrics duplicate: 0 -> 1 (delta 1); events.jsonl 1: OK" in out
    assert "/metrics dropped: 0 -> 0 (delta 0)\n" in out  # reported, never compared
    assert "MISMATCH" not in out


def test_delta_exits_4_on_a_twin_mismatch(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path, after_count=560)
    assert rec.main(["delta", str(run_dir)]) == 4
    assert "(delta 60)" in capsys.readouterr().out


def test_delta_exits_4_when_the_twin_does_not_end_on_the_last_accepted_seq(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path)
    write_json(rec.sib(str(run_dir), ".twins.after.json"),
               twins(503, last_run_id=RUN_ID, last_seq=1))
    assert rec.main(["delta", str(run_dir)]) == 4
    assert "last_seq 1: MISMATCH" in capsys.readouterr().out


def test_delta_exits_4_on_a_metrics_mismatch(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(
        tmp_path, after_metrics=metrics(accepted=103, duplicate=1, rejected=1, failed=2))
    assert rec.main(["delta", str(run_dir)]) == 4
    assert "/metrics failed: 0 -> 2 (delta 2); events.jsonl 0: MISMATCH" in capsys.readouterr().out


def test_delta_refuses_to_compare_metrics_across_a_controller_restart(tmp_path, capsys) -> None:
    # counters restarted from zero: any subtraction would be meaningless
    run_dir = make_delta_fixture(tmp_path, after_metrics=metrics(
        started_at="2026-09-18T10:30:00.000Z", accepted=2, duplicate=0, rejected=0))
    assert rec.main(["delta", str(run_dir)]) == 0  # the twins still close
    out = capsys.readouterr().out
    assert "RESTARTED" in out and "no delta is computed" in out
    assert "/metrics accepted" not in out
    assert "last_seq 2: OK" in out


def test_delta_still_reports_a_twin_mismatch_across_a_restart(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path, after_count=3, after_metrics=metrics(
        started_at="2026-09-18T10:30:00.000Z", accepted=3))
    assert rec.main(["delta", str(run_dir)]) == 4
    assert "RESTARTED" in capsys.readouterr().out


def test_delta_exits_4_while_the_queue_is_not_empty(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path, after_metrics=metrics(
        accepted=103, duplicate=1, rejected=1, queue_depth=2))
    assert rec.main(["delta", str(run_dir)]) == 4
    assert "queue_depth=2" in capsys.readouterr().out


def test_delta_says_so_when_the_metrics_are_not_compared(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path)
    rec.sib(str(run_dir), ".metrics.after.json").unlink()
    assert rec.main(["delta", str(run_dir)]) == 0  # the twins close
    out = capsys.readouterr().out
    assert "/metrics: NOT compared (" in out and "metrics.after.json missing)" in out
    assert "metrics.before.json" not in out and "/metrics accepted" not in out
    rec.sib(str(run_dir), ".metrics.before.json").unlink()
    assert rec.main(["delta", str(run_dir)]) == 0  # harness runs: no snapshots at all
    out = capsys.readouterr().out
    assert "metrics.before.json and " in out and "metrics.after.json missing)" in out


def test_delta_checks_the_queue_of_the_to_reading_even_without_a_from_reading(
    tmp_path, capsys
) -> None:
    run_dir = make_delta_fixture(tmp_path, after_metrics=metrics(
        accepted=103, duplicate=1, rejected=1, queue_depth=7))
    rec.sib(str(run_dir), ".metrics.before.json").unlink()
    assert rec.main(["delta", str(run_dir)]) == 4
    out = capsys.readouterr().out
    assert "NOT compared" in out and "queue_depth=7" in out


def test_delta_exits_4_when_the_snapshots_do_not_hold_the_device_that_published(
    tmp_path, capsys
) -> None:
    # 'snap --seed 7' next to a run of seed 42: twins that were never touched close
    other = device_uuid_for(7, "smartwatch")
    untouched = twins(None, last_run_id=None, last_seq=None, exists=False, device_uuid=other)
    run_dir = make_delta_fixture(tmp_path)
    write_json(rec.sib(str(run_dir), ".twins.before.json"), untouched)
    write_json(rec.sib(str(run_dir), ".twins.after.json"), untouched)
    assert rec.main(["delta", str(run_dir)]) == 4
    out = capsys.readouterr().out
    assert f"{DEV}: 3 accepted record(s) in events.jsonl but absent from the 'before' snapshot" in out
    assert f"{other} smartwatch: existed_before=False accepted_count None -> None (delta 0)" in out


def test_delta_exits_4_for_a_device_found_only_in_an_also_log(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path)
    warmup = tmp_path / "warmup.events.jsonl"
    write_jsonl(warmup, [event(0, "accepted", T0 - 9, run_id=f"{RUN_ID}.warmup", device_uuid=RING)])
    assert rec.main(["delta", str(run_dir), "--also", str(warmup)]) == 4
    assert f"{RING}: 1 accepted record(s)" in capsys.readouterr().out


def test_delta_counts_each_device_on_its_own_and_accepts_a_first_use(tmp_path, capsys) -> None:
    # the ring did not exist before (accepted_count null, as on a fresh MongoDB
    # volume) and has one accepted record; the watch has three
    run_dir = make_delta_fixture(tmp_path)
    write_jsonl(run_dir / "events.jsonl",
                EVENTS + [event(0, "accepted", T0 - 2, device_uuid=RING),
                          event(1, "duplicate", device_uuid=RING)])
    prefix = str(run_dir)
    write_json(rec.sib(prefix, ".twins.before.json"), both(
        twins(500), ring_twins(None, last_run_id=None, last_seq=None, exists=False)))
    write_json(rec.sib(prefix, ".twins.after.json"), both(
        twins(503, last_run_id=RUN_ID, last_seq=2), ring_twins(1, last_run_id=RUN_ID, last_seq=0)))
    write_json(rec.sib(prefix, ".metrics.after.json"), metrics(accepted=104, duplicate=2, rejected=1))
    assert rec.main(["delta", prefix]) == 0
    out = capsys.readouterr().out
    assert (f"{DEV} smartwatch: existed_before=True accepted_count 500 -> 503 (delta 3); "
            "accepted records in events.jsonl 3;") in out
    assert (f"{RING} smart_ring: existed_before=False accepted_count None -> 1 (delta 1); "
            f"accepted records in events.jsonl 1; last_run_id {RUN_ID} last_seq 0: OK") in out
    assert "MISMATCH" not in out


def test_delta_closes_when_nothing_was_accepted_and_the_twin_never_existed(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path, after_metrics=metrics(rejected=1))
    write_jsonl(run_dir / "events.jsonl", [event(4, "rejected")])
    absent = twins(None, last_run_id=None, last_seq=None, exists=False)
    write_json(rec.sib(str(run_dir), ".twins.before.json"), absent)
    write_json(rec.sib(str(run_dir), ".twins.after.json"), absent)
    assert rec.main(["delta", str(run_dir)]) == 0
    out = capsys.readouterr().out
    assert "accepted_count None -> None (delta 0); accepted records in events.jsonl 0;" in out


def test_delta_exits_4_when_the_twin_ends_on_another_run(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path)
    write_json(rec.sib(str(run_dir), ".twins.after.json"),
               twins(503, last_run_id="itest-other", last_seq=2))
    assert rec.main(["delta", str(run_dir)]) == 4
    assert "last_run_id itest-other last_seq 2: MISMATCH" in capsys.readouterr().out


def test_delta_takes_the_run_from_the_first_record_that_names_one(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(
        tmp_path, after_metrics=metrics(accepted=103, duplicate=1, rejected=2))
    write_jsonl(run_dir / "events.jsonl", [dict(event(9, "rejected"), run_id=None)] + EVENTS)
    assert rec.main(["delta", str(run_dir)]) == 0
    write_json(rec.sib(str(run_dir), ".twins.after.json"),
               twins(503, last_run_id=RUN_ID, last_seq=1))
    assert rec.main(["delta", str(run_dir)]) == 4
    assert "last_seq 1: MISMATCH" in capsys.readouterr().out


def test_delta_prefix_labels_and_also(tmp_path, capsys) -> None:
    # harness layout: run directory elsewhere, snapshots under --prefix, and a
    # warm-up log whose accepted records patched the same twin
    (tmp_path / "raw").mkdir()
    (tmp_path / "itest").mkdir()
    run_dir = make_run(tmp_path / "raw")
    prefix = str(tmp_path / "itest" / RUN_ID)
    write_json(rec.sib(prefix, ".twins.t0.json"), twins(500))
    write_json(rec.sib(prefix, ".twins.t1.json"), twins(505, last_run_id=RUN_ID, last_seq=2))
    warmup = tmp_path / "warmup.events.jsonl"
    write_jsonl(warmup, [event(0, "accepted", T0 - 9, run_id=f"{RUN_ID}.warmup"),
                         event(7, "accepted", T0 - 8, run_id=f"{RUN_ID}.warmup")])
    base = ["delta", str(run_dir), "--prefix", prefix, "--from", "t0", "--to", "t1"]
    assert rec.main(base) == 4  # without --also: off by exactly the warm-up records
    assert "(delta 5); accepted records in events.jsonl 3;" in capsys.readouterr().out
    assert rec.main(base + ["--also", str(warmup)]) == 0
    # last_seq is judged on the primary run only (warm-up seq 7 is ignored)
    assert "accepted records in events.jsonl 5; last_run_id itest-x last_seq 2: OK" in capsys.readouterr().out


def test_delta_reads_the_post_drain_copy_with_events_and_leaves_the_timed_file_alone(
    tmp_path, capsys
) -> None:
    """F6c (test 6 of the runbook): one message accepted inside the timed
    copy of events.jsonl and a second one accepted only during the drain,
    so the after twin grew by two. The timed accounting keeps its result
    (the second message is late for the deadline: lost 1), the timed file
    is not touched, and the persistence delta compares the after twin with
    the post-drain copy named by --events, never with the timed file (which
    would report a false MISMATCH) nor with both (--also would count the
    shared record twice)."""
    timed = [event(0, "accepted", T0 - 5, received_ns=T0 - 4 * NS)]
    run_dir = make_run(
        tmp_path, events=timed, sent_records=[sent(0), sent(1)],
        manifest=sim_manifest(totals={"sent": 2, "intended_invalid": 0}),
    )
    close_window(run_dir)
    post_drain = tmp_path / "events.post-drain.jsonl"
    write_jsonl(post_drain, timed + [event(1, "accepted", DEADLINE + 5 * NS, received_ns=DEADLINE + 4 * NS)])
    prefix = str(run_dir)
    write_json(rec.sib(prefix, ".twins.before.json"), twins(500))
    write_json(rec.sib(prefix, ".twins.after.json"), twins(502, last_run_id=RUN_ID, last_seq=1))
    before = listing(run_dir)

    # The timed analysis: the deadline result stands, from the timed file.
    assert rec.main(["check", str(run_dir), "--controller-url", CTRL]) == 0
    row = json.loads((tmp_path / f"{RUN_ID}.reconcile.json").read_text("utf-8"))
    assert row["delivered_unique"] == 1 and row["lost"] == 1
    capsys.readouterr()

    # The timed file against the after twin: a false MISMATCH, by exactly
    # the record accepted during the drain.
    assert rec.main(["delta", str(run_dir)]) == 4
    out = capsys.readouterr().out
    assert "(delta 2); accepted records in events.jsonl 1;" in out and "MISMATCH" in out

    # The post-drain copy, selected explicitly: the persistence delta closes.
    assert rec.main(["delta", str(run_dir), "--events", str(post_drain)]) == 0
    out = capsys.readouterr().out
    assert "(delta 2); accepted records in events.post-drain.jsonl 2;" in out
    assert f"last_run_id {RUN_ID} last_seq 1: OK" in out and "MISMATCH" not in out
    # Appending the post-drain copy through --also would double-count m0.
    assert rec.main(["delta", str(run_dir), "--also", str(post_drain)]) == 4
    assert "(delta 2); accepted records in events.jsonl 3;" in capsys.readouterr().out
    # Nothing in the run directory changed: the timed copy and its
    # accounting are preserved.
    assert listing(run_dir) == before
    assert json.loads((tmp_path / f"{RUN_ID}.reconcile.json").read_text("utf-8")) == row


def test_delta_exits_1_on_a_missing_or_truncated_events_file(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path)
    assert rec.main(["delta", str(run_dir), "--events", str(tmp_path / "nowhere.jsonl")]) == 1
    assert "nowhere.jsonl" in capsys.readouterr().err
    (tmp_path / "cut.jsonl").write_text('{"outcome": "acc', "utf-8")
    assert rec.main(["delta", str(run_dir), "--events", str(tmp_path / "cut.jsonl")]) == 1
    assert "cut.jsonl" in capsys.readouterr().err


def test_delta_exits_4_when_a_device_is_absent_from_the_to_snapshot(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path)
    write_json(rec.sib(str(run_dir), ".twins.before.json"), both(twins(500), ring_twins(7)))
    assert rec.main(["delta", str(run_dir)]) == 4
    assert "absent from the 'after' snapshot: MISMATCH" in capsys.readouterr().out


@pytest.mark.parametrize("sibling,content", [
    (".twins.before.json", None),
    (".twins.after.json", "{truncated"),
    (".twins.after.json", '{"devices": []}'),
    (".twins.before.json", '{"devices": {}}'),  # nothing would be compared
    (".twins.after.json", '{"devices": {}}'),
    (".twins.after.json", json.dumps({"devices": {DEV: {"device_type": "smartwatch"}}})),
    (".twins.after.json", json.dumps(twins("503"))),
    (".metrics.after.json", "{truncated"),
    (".metrics.after.json", json.dumps({"accepted": 103})),  # no started_at
    (".metrics.before.json", json.dumps(metrics(accepted="100"))),
    (".metrics.after.json", json.dumps(metrics(queue_depth=None))),  # not an empty queue
    (".metrics.after.json", json.dumps({k: v for k, v in metrics().items() if k != "queue_depth"})),
])
def test_delta_exits_1_on_missing_or_malformed_snapshots(tmp_path, capsys, sibling, content) -> None:
    run_dir = make_delta_fixture(tmp_path)
    path = rec.sib(str(run_dir), sibling)
    if content is None:
        path.unlink()
    else:
        path.write_text(content, "utf-8")
    assert rec.main(["delta", str(run_dir)]) == 1
    captured = capsys.readouterr()
    assert sibling in captured.err
    assert captured.out == ""  # refused before any line is printed


def test_delta_exits_1_on_a_missing_or_truncated_event_log(tmp_path, capsys) -> None:
    run_dir = make_delta_fixture(tmp_path)
    (run_dir / "events.jsonl").write_text('{"outcome": "acc', "utf-8")
    assert rec.main(["delta", str(run_dir)]) == 1
    assert "line 1" in capsys.readouterr().err
    (run_dir / "events.jsonl").unlink()
    assert rec.main(["delta", str(run_dir)]) == 1
    assert rec.main(["delta", str(run_dir), "--also", str(tmp_path / "nowhere.jsonl")]) == 1
    capsys.readouterr()


# ---------------------------------------------------------------------------
# delta: the N1 report (decision 2 of 2026-09-30), opt-in and exit-neutral
# ---------------------------------------------------------------------------

RESTART_EPOCH = 1_790_000_000  # the capture's requested_since (RUN_T0), guest clock


def a3_line(device_uuid: str, received_ns: int, level: str = "ERROR", cause: str = "write-failed") -> str:
    """A controller log line as `docker logs --timestamps` prints it: the
    connection end the controller logs at ERROR under A3 (INFO: a graceful
    stop), with the delivery in progress."""
    return "2026-09-30T10:03:10.000000000Z " + json.dumps({
        "ts": "2026-09-30T10:03:10.001Z", "level": level, "logger": "egw_controller.mqtt",
        "message": "MQTT connection ended by the controller",
        "context": {"cause": cause, "connection": 2, "occurrence": 1, "backoff_s": 1.0,
                    "identity": {"topic": f"c2dt/egw-01/{device_uuid}/telemetry", "mid": 7, "qos": 1,
                                 "dup": False, "connection": 2, "received_monotonic_ns": received_ns}}})


def quiet_metrics(**counters) -> dict:
    """metrics() as the controller serves a whole /metrics reading that is
    quiet (CONTRACTS 5): queue_depth, in_progress and unacked 0,
    mqtt_subscribed true and the accounting identity holding."""
    body = metrics(**counters)
    body.update(in_progress=0, unacked=0, mqtt_subscribed=True, mqtt_connection=1, processing_errors=0)
    body["received"] = sum(body[key] for key in ("accepted", "rejected", "duplicate", "failed", "dropped",
                                                 "processing_errors", "in_progress", "queue_depth"))
    return body


def make_n1_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """make_delta_fixture plus m5 (published, seq 5) whose only line is a
    duplicate, and a twin that grew by one more than the device's accepted
    records and ended on seq 5: the device line is a MISMATCH. The
    controller log holds one A3 connection end of DEV received before m5's
    redelivery; the 'after' /metrics reading is quiet."""
    run_dir = make_delta_fixture(tmp_path, after_count=504,
                                 after_metrics=quiet_metrics(accepted=103, duplicate=2, rejected=1))
    write_jsonl(run_dir / "sent_events.jsonl", SENT + [sent(5)])
    write_jsonl(run_dir / "events.jsonl", EVENTS + [event(5, "duplicate", received_ns=DEADLINE)])
    write_json(rec.sib(str(run_dir), ".twins.after.json"), twins(504, last_run_id=RUN_ID, last_seq=5))
    log = tmp_path / "controller.log"
    log.write_text(a3_line(DEV, DEADLINE - NS) + "\n", encoding="utf-8")
    return run_dir, log


#: What delta prints today for make_n1_fixture, without any N1 option: the
#: output the options must leave byte for byte.
N1_FIXTURE_PLAIN = (
    f"{DEV} smartwatch: existed_before=True accepted_count 500 -> 504 (delta 4); accepted records in "
    f"events.jsonl 3; last_run_id {RUN_ID} last_seq 5: MISMATCH\n"
    "/metrics accepted: 100 -> 103 (delta 3); events.jsonl 3: OK\n"
    "/metrics rejected: 0 -> 1 (delta 1); events.jsonl 1: OK\n"
    "/metrics duplicate: 0 -> 2 (delta 2); events.jsonl 2: OK\n"
    "/metrics failed: 0 -> 0 (delta 0); events.jsonl 0: OK\n"
    "/metrics dropped: 0 -> 0 (delta 0)\n"
)


def n1_added_lines(with_report: str, plain: str) -> list[str]:
    """The lines the N1 report added, after checking that removing them
    leaves the plain output exactly: the annotation lines under a device
    line, and the section from the 'N1 REPORT' line to the end."""
    lines = with_report.splitlines()
    cut = next(i for i, ln in enumerate(lines) if ln.startswith("N1 REPORT"))
    annotations = [ln for ln in lines[:cut] if ln.startswith("  n1_applied_unconfirmed on ")]
    kept = [ln for ln in lines[:cut] if not ln.startswith("  n1_applied_unconfirmed on ")]
    assert kept == plain.splitlines(), "an existing delta line changed or moved"
    return annotations + lines[cut:]


def test_delta_n1_report_annotates_the_mismatch_and_changes_no_exit(tmp_path, capsys) -> None:
    run_dir, log = make_n1_fixture(tmp_path)
    assert rec.main(["delta", str(run_dir), "--controller-log", str(log)]) == 4
    out = capsys.readouterr().out
    lines = out.splitlines()
    i = lines.index(N1_FIXTURE_PLAIN.splitlines()[0])
    assert lines[i].endswith(": MISMATCH")  # the device line is unchanged and stays a mismatch
    assert lines[i + 1].startswith(f"  n1_applied_unconfirmed on {DEV}: m5 seq 5")
    assert "a3-connection-end" in lines[i + 1] and "controller log line 1" in lines[i + 1]
    assert "stays in lost" in lines[i + 1]
    assert "n1_applied_unconfirmed=1 duplicate_only_unexplained=0" in out
    added = n1_added_lines(out, N1_FIXTURE_PLAIN)
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in added), added


def test_delta_n1_report_without_a_controller_log_leaves_the_identity_unexplained(tmp_path, capsys) -> None:
    run_dir, _log = make_n1_fixture(tmp_path)
    assert rec.main(["delta", str(run_dir), "--n1-report"]) == 4
    out = capsys.readouterr().out
    assert "  n1_applied_unconfirmed on " not in out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out
    (line,) = [ln for ln in out.splitlines() if ln.startswith("  duplicate_only_unexplained m5 ")]
    assert "failed condition(s) 2:" in line and "controller log not read" in line, line
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in n1_added_lines(out, N1_FIXTURE_PLAIN))


def test_delta_without_the_n1_options_is_byte_identical(tmp_path, capsys) -> None:
    run_dir, _log = make_n1_fixture(tmp_path)
    assert rec.main(["delta", str(run_dir)]) == 4
    assert capsys.readouterr().out == N1_FIXTURE_PLAIN


def _fixture_first_use(tmp_path: Path) -> Path:
    run_dir = make_delta_fixture(tmp_path)
    write_jsonl(run_dir / "events.jsonl",
                EVENTS + [event(0, "accepted", T0 - 2, device_uuid=RING), event(1, "duplicate", device_uuid=RING)])
    prefix = str(run_dir)
    write_json(rec.sib(prefix, ".twins.before.json"), both(
        twins(500), ring_twins(None, last_run_id=None, last_seq=None, exists=False)))
    write_json(rec.sib(prefix, ".twins.after.json"), both(
        twins(503, last_run_id=RUN_ID, last_seq=2), ring_twins(1, last_run_id=RUN_ID, last_seq=0)))
    write_json(rec.sib(prefix, ".metrics.after.json"), metrics(accepted=104, duplicate=2, rejected=1))
    return run_dir


def _fixture_last_seq(tmp_path: Path) -> Path:
    run_dir = make_delta_fixture(tmp_path)
    write_json(rec.sib(str(run_dir), ".twins.after.json"), twins(503, last_run_id=RUN_ID, last_seq=1))
    return run_dir


DELTA_FIXTURES = {
    "closes": make_delta_fixture,
    "twin mismatch": lambda p: make_delta_fixture(p, after_count=560),
    "last_seq mismatch": _fixture_last_seq,
    "metrics mismatch": lambda p: make_delta_fixture(
        p, after_metrics=metrics(accepted=103, duplicate=1, rejected=1, failed=2)),
    "restart": lambda p: make_delta_fixture(p, after_metrics=metrics(
        started_at="2026-09-18T10:30:00.000Z", accepted=2, duplicate=0, rejected=0)),
    "queue": lambda p: make_delta_fixture(p, after_metrics=metrics(
        accepted=103, duplicate=1, rejected=1, queue_depth=2)),
    "first use": _fixture_first_use,
    "n1": lambda p: make_n1_fixture(p)[0],
}


@pytest.mark.parametrize("name", sorted(DELTA_FIXTURES))
def test_delta_n1_report_never_changes_an_exit_code_or_an_existing_line(tmp_path, capsys, name) -> None:
    run_dir = DELTA_FIXTURES[name](tmp_path)
    plain_rc = rec.main(["delta", str(run_dir)])
    plain = capsys.readouterr().out
    assert rec.main(["delta", str(run_dir), "--n1-report"]) == plain_rc
    out = capsys.readouterr().out
    added = n1_added_lines(out, plain)
    assert added[0].startswith("N1 REPORT") or added[0].startswith("  n1_applied_unconfirmed on ")
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in added), added


def test_delta_n1_report_on_a_first_use_closes_and_names_the_unpublished_redelivery(tmp_path, capsys) -> None:
    run_dir = _fixture_first_use(tmp_path)
    assert rec.main(["delta", str(run_dir), "--n1-report"]) == 0
    out = capsys.readouterr().out
    assert "MISMATCH" not in out
    (line,) = [ln for ln in out.splitlines() if ln.startswith("  duplicate_only_unexplained r1 ")]
    assert "not a valid published identity" in line


@pytest.mark.parametrize("named", ["missing", "a directory", "undecodable"])
def test_delta_n1_report_with_an_unreadable_controller_log_is_not_fatal(tmp_path, capsys, named) -> None:
    run_dir, _log = make_n1_fixture(tmp_path)
    path = tmp_path / "nowhere.log"
    if named == "a directory":
        path.mkdir()
    elif named == "undecodable":
        path = tmp_path / "controller.log"  # errors="replace", as the proof reads it: still read
        path.write_bytes(b"\xff\xfe" + a3_line(DEV, DEADLINE - NS).encode("utf-8") + b"\n")
    rc = rec.main(["delta", str(run_dir), "--controller-log", str(path)])
    out = capsys.readouterr().out
    assert rc == 4  # as without the option; never 1
    if named == "undecodable":
        assert "n1_applied_unconfirmed=1" in out
    else:
        assert "controller log not read" in out
        assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out


# --- the harness layout of test 6: --restart-evidence ----------------------

RESTART_RECORD = {"template": "ssh ... restart controller", "requested_at_s": 300, "executed": True,
                  "command": "ssh ... restart controller", "started_utc": "2026-09-30T10:05:00.000Z",
                  "started_monotonic_ns": 1, "returncode": 0, "stderr_tail": "", "error": None,
                  "finished_utc": "2026-09-30T10:05:02.000Z"}


def make_restart_evidence(tmp_path: Path, *, drain: str = "quiet", die: bool = True,
                          controller_log: str = "2026-09-30T10:00:00.000000000Z {\"message\": \"started\"}\n"
                          ) -> tuple[Path, str]:
    """A sealed harness run directory of a controller_restart run as test 6
    leaves it (raw/<run_id>: the manifest's restart evidence records, the
    two verified snapshots, the post-drain copy, logs/sut/ with the
    controller log and the complete Docker events capture), plus the twin
    hook's write-once siblings under --prefix. m5 is duplicate-only with a
    twin excess of one; the capture holds the controller's die inside its
    window unless ``die`` is false. Returns (run directory, prefix)."""
    from egw_experiments.checksums import write_sha256sums

    run_dir = tmp_path / "raw" / RUN_ID
    (run_dir / "logs" / "sut").mkdir(parents=True)
    write_jsonl(run_dir / "sent_events.jsonl", SENT + [sent(5)])
    write_jsonl(run_dir / "events.jsonl", EVENTS)
    write_jsonl(run_dir / "events.post-drain.jsonl", EVENTS + [event(5, "duplicate", received_ns=DEADLINE)])
    snapshots = {"before": twins(500), "after": twins(504, last_run_id=RUN_ID, last_seq=5)}
    prefix = str(tmp_path / "itest" / RUN_ID)
    (tmp_path / "itest").mkdir()
    for label, doc in snapshots.items():
        write_json(run_dir / f"twins.{label}.json", doc)
        write_json(rec.sib(prefix, f".twins.{label}.json"), doc)
    sut = run_dir / "logs" / "sut"
    (sut / "controller.log").write_text(controller_log, encoding="utf-8")
    at = (RESTART_EPOCH + 300) * NS + 17
    events = [{"Type": "container", "Action": "kill" if not die else "die", "time": at // NS, "timeNano": at,
               "Actor": {"ID": "c" * 64, "Attributes": {"name": "egw-controller-1", "signal": "15"}}}]
    write_jsonl(sut / "docker-events.log", events)
    (sut / "docker-events.coverage.txt").write_text(
        f"coverage=complete\nrequested_since_guest_epoch={RESTART_EPOCH}\n"
        f"requested_until_guest_epoch={RESTART_EPOCH + 900}\nexpected=die,start\ncontainer=egw-controller-1\n",
        encoding="utf-8")
    write_json(run_dir / "manifest.json", {
        "run_id": RUN_ID, "condition_id": "controller_restart", "validity": "valid", "validity_reasons": [],
        "exclusion": None, "restart": RESTART_RECORD, "drain": {"outcome": drain, "source": "hook"},
        "twin_snapshots": [{"file": "twins.before.json", "verified": True},
                           {"file": "twins.after.json", "verified": True}],
        "events_post_drain_fetch": {"file": "events.post-drain.jsonl", "verified": True},
        "sut_log_fetches": [
            {"hook": "controller_log", "returncode": 0, "dest_exists": True, "dest_file": "logs/sut/controller.log"},
            {"hook": "docker_events", "returncode": 0, "dest_exists": True,
             "dest_file": "logs/sut/docker-events.log"}],
    })
    write_sha256sums(run_dir)
    return run_dir, prefix


def t6_delta(run_dir: Path, prefix: str) -> list[str]:
    """Test 6's delta line of the runbook."""
    return ["delta", str(run_dir), "--prefix", prefix, "--events", str(run_dir / "events.post-drain.jsonl"),
            "--controller-log", str(run_dir / "logs" / "sut" / "controller.log"),
            "--restart-evidence", str(run_dir)]


def test_delta_restart_evidence_supplies_the_death_source(tmp_path, capsys) -> None:
    run_dir, prefix = make_restart_evidence(tmp_path)
    argv = t6_delta(run_dir, prefix)
    assert rec.main(argv[:6]) == 4  # the plain line: m5's device is a MISMATCH
    plain = capsys.readouterr().out
    assert rec.main(argv) == 4
    out = capsys.readouterr().out
    assert f"  n1_applied_unconfirmed on {DEV}: m5 seq 5" in out and "controller-death" in out
    assert "n1_applied_unconfirmed=1 duplicate_only_unexplained=0" in out
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in n1_added_lines(out, plain))


def test_delta_restart_evidence_without_the_die_is_no_source(tmp_path, capsys) -> None:
    run_dir, prefix = make_restart_evidence(tmp_path, die=False)
    assert rec.main(t6_delta(run_dir, prefix)) == 4
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out
    (line,) = [ln for ln in out.splitlines() if ln.startswith("  duplicate_only_unexplained m5 ")]
    assert "failed condition(s) 2:" in line


def test_delta_restart_evidence_whose_drain_was_not_quiet_leaves_condition_3_unevaluable(tmp_path, capsys) -> None:
    run_dir, prefix = make_restart_evidence(tmp_path, drain="gave-up")
    argv = t6_delta(run_dir, prefix)
    assert rec.main(argv[:6]) == 4
    capsys.readouterr()
    assert rec.main(argv) == 4
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out
    (line,) = [ln for ln in out.splitlines() if ln.startswith("  duplicate_only_unexplained m5 ")]
    assert "3" in line.split("failed condition(s) ", 1)[1].split(":", 1)[0] and "drain" in line, line


def test_delta_restart_evidence_must_be_the_compared_snapshots_and_copy(tmp_path, capsys) -> None:
    """The snapshots and the events copy delta compares must be the run's
    verified ones; otherwise condition 3 is not shown and nothing is named."""
    run_dir, prefix = make_restart_evidence(tmp_path)
    write_json(rec.sib(prefix, ".twins.after.json"), twins(504, last_run_id=RUN_ID, last_seq=6))
    assert rec.main(t6_delta(run_dir, prefix)) == 4
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0" in out and "verified snapshot" in out
    run_dir, prefix = make_restart_evidence(tmp_path / "second")
    argv = t6_delta(run_dir, prefix)
    argv[argv.index("--events") + 1] = str(run_dir / "events.jsonl")  # the timed copy
    rec.main(argv)
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0" in out and "post-drain copy" in out


@pytest.mark.parametrize("problem", ["missing", "another run"])
def test_delta_restart_evidence_that_cannot_be_read_is_not_fatal(tmp_path, capsys, problem) -> None:
    run_dir, prefix = make_restart_evidence(tmp_path)
    argv = t6_delta(run_dir, prefix)
    if problem == "missing":
        argv[-1] = str(tmp_path / "nowhere")
    else:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        write_json(run_dir / "manifest.json", dict(manifest, run_id="controller_restart-r09"))
    assert rec.main(argv) == 4
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out
    assert "restart evidence not read" in out


def test_delta_parser_takes_the_n1_options() -> None:
    parse = rec.build_parser().parse_args
    plain = parse(["delta", "raw/r"])
    assert (plain.n1_report, plain.controller_log, plain.restart_evidence) == (False, None, None)
    full = parse(["delta", "raw/r", "--n1-report", "--controller-log", "raw/r/logs/sut/controller.log",
                  "--restart-evidence", "raw/r"])
    assert (full.n1_report, full.controller_log, full.restart_evidence) == (
        True, "raw/r/logs/sut/controller.log", "raw/r")


# --- round 0 of the verification ---------------------------------------------


def test_delta_n1_report_counts_the_also_files_duplicate_only_identities_on_the_device(tmp_path, capsys) -> None:
    """The --also file of another run id (the harness warm-up) is in delta's
    arithmetic; a duplicate-only identity of it on DEV may be the one the
    twin applied: two duplicate-only identities against an excess of one,
    so none is named."""
    run_dir, log = make_n1_fixture(tmp_path)
    warm = tmp_path / "warmup-events.jsonl"
    write_jsonl(warm, [dict(event(0, "duplicate", run_id=f"{RUN_ID}.warmup", received_ns=T0 - 9 * NS),
                            message_id="w0")])
    write_json(rec.sib(str(run_dir), ".metrics.after.json"), quiet_metrics(accepted=103, duplicate=3, rejected=1))
    argv = ["delta", str(run_dir), "--also", str(warm)]
    assert rec.main(argv) == 4
    plain = capsys.readouterr().out
    assert rec.main(argv + ["--controller-log", str(log)]) == 4
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out
    (line,) = [ln for ln in out.splitlines() if ln.startswith("  duplicate_only_unexplained m5 ")]
    assert "failed condition(s) 3:" in line and "another run id" in line, line
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in n1_added_lines(out, plain))


@pytest.mark.parametrize("value", ["²", "١٧٩٠"])
def test_delta_restart_evidence_with_a_malformed_capture_window_is_not_fatal(tmp_path, capsys, value) -> None:
    run_dir, prefix = make_restart_evidence(tmp_path)
    coverage = run_dir / "logs" / "sut" / "docker-events.coverage.txt"
    coverage.write_text(coverage.read_text(encoding="utf-8").replace(
        "requested_until_guest_epoch=", f"requested_until_guest_epoch={value}"), encoding="utf-8")
    assert rec.main(t6_delta(run_dir, prefix)) == 4  # as without the options; never 1
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out
    assert "whole-number capture window" in out


@pytest.mark.parametrize("file", [["twins.before.json"], {"name": "twins.before.json"}])
def test_delta_restart_evidence_with_a_malformed_manifest_is_not_fatal(tmp_path, capsys, file) -> None:
    run_dir, prefix = make_restart_evidence(tmp_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["twin_snapshots"] = [{"file": file, "verified": True}, {"file": "twins.after.json", "verified": True}]
    write_json(run_dir / "manifest.json", manifest)
    assert rec.main(t6_delta(run_dir, prefix)) == 4  # as without the options; never 1
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out
    assert "restart evidence not read" in out


def _status_word_case(tmp_path: Path, case: str) -> tuple[list[str], list[str]]:
    """(plain argv, argv with the N1 options) whose options carry an
    operator-chosen name spelling a status word."""
    if case.startswith("restart evidence"):
        run_dir, prefix = make_restart_evidence(tmp_path)
        for label in ("OK", "MISMATCH"):
            source = rec.sib(prefix, ".twins.before.json" if label == "OK" else ".twins.after.json")
            write_json(rec.sib(prefix, f".twins.{label}.json"), json.loads(source.read_text(encoding="utf-8")))
        # the 'to' snapshot compared is not the run's verified one
        write_json(rec.sib(prefix, ".twins.MISMATCH.json"), twins(504, last_run_id=RUN_ID, last_seq=6))
        argv = t6_delta(run_dir, prefix)[:6] + ["--from", "OK", "--to", "MISMATCH"]
        return argv, argv + ["--restart-evidence", str(run_dir)]
    run_dir, log = make_n1_fixture(tmp_path)
    argv = ["delta", str(run_dir)]
    if case == "log named OK":
        named = tmp_path / "OK.log"
        named.write_bytes(log.read_bytes())
        return argv, argv + ["--controller-log", str(named)]
    if case == "missing log named MISMATCH":
        return argv, argv + ["--controller-log", str(tmp_path / "MISMATCH.log")]
    prefix = str(run_dir)
    write_json(rec.sib(prefix, ".twins.OK.json"), json.loads(rec.sib(prefix, ".twins.after.json").read_text("utf-8")))
    argv = argv + ["--to", "OK"]
    if case == "label OK, draining reading":
        write_json(rec.sib(prefix, ".metrics.OK.json"), metrics(accepted=103, duplicate=2, rejected=1, queue_depth=1))
    return argv, argv + ["--controller-log", str(log)]


@pytest.mark.parametrize("case", ["log named OK", "missing log named MISMATCH", "label OK, draining reading",
                                  "label OK, no reading", "restart evidence with labels OK and MISMATCH"])
def test_delta_n1_lines_hold_no_status_word_whatever_the_operator_names(tmp_path, capsys, case) -> None:
    """No line the N1 report adds holds the upper-case status words, even
    when a file name or a snapshot label the operator chose spells one: the
    added lines name the options' roles, never the names given."""
    plain_argv, argv = _status_word_case(tmp_path, case)
    plain_rc = rec.main(plain_argv)
    plain = capsys.readouterr().out
    assert rec.main(argv) == plain_rc
    added = n1_added_lines(capsys.readouterr().out, plain)
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in added), added


# --- round 1 of the verification ---------------------------------------------


@pytest.mark.parametrize("change", [
    "in_progress absent", "unacked absent", "mqtt_subscribed absent", "received absent",
    "mqtt_subscribed false", "in_progress 1", "unacked 2", "in_progress not-an-integer", "identity fails",
])
def test_delta_n1_report_needs_a_to_reading_quiet_as_the_contract_defines_one(tmp_path, capsys, change) -> None:
    """Without --restart-evidence the twin evidence is the 'to' /metrics
    reading, which must be quiet as CONTRACTS 5 defines one reading
    (queue_depth, in_progress and unacked 0, mqtt_subscribed true and the
    accounting identity holding; an absent field is never read as zero or
    false): otherwise condition 3 is not shown and nothing is named."""
    run_dir, log = make_n1_fixture(tmp_path)
    reading = quiet_metrics(accepted=103, duplicate=2, rejected=1)
    field, _sep, value = change.partition(" ")
    if change == "identity fails":
        reading["received"] += 1
    elif value == "absent":
        del reading[field]
    elif value == "false":
        reading[field] = False
    elif value == "not-an-integer":
        reading[field] = "0"
    else:
        reading[field] = int(value)
    write_json(rec.sib(str(run_dir), ".metrics.after.json"), reading)
    plain_rc = rec.main(["delta", str(run_dir)])
    plain = capsys.readouterr().out
    assert rec.main(["delta", str(run_dir), "--controller-log", str(log)]) == plain_rc == 4
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=1" in out
    (evidence,) = [ln for ln in out.splitlines() if ln.startswith("  condition 3 evidence: ")]
    assert "not shown quiet" in evidence, evidence
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in n1_added_lines(out, plain))


@pytest.mark.parametrize("device", [None, ""])
def test_delta_n1_report_places_a_duplicate_line_without_a_device_on_its_published_device(
    tmp_path, capsys, device
) -> None:
    """m6, published on DEV, has a duplicate line that names no device and
    the twin ended on its seq: DEV has two duplicate-only identities against
    a surplus of one, so m5 is not named."""
    run_dir, log = make_n1_fixture(tmp_path)
    m6 = dict(event(6, "duplicate", received_ns=DEADLINE + NS), device_uuid=device)
    write_jsonl(run_dir / "sent_events.jsonl", SENT + [sent(5), sent(6)])
    write_jsonl(run_dir / "events.jsonl", EVENTS + [event(5, "duplicate", received_ns=DEADLINE), m6])
    write_json(rec.sib(str(run_dir), ".twins.after.json"), twins(504, last_run_id=RUN_ID, last_seq=6))
    write_json(rec.sib(str(run_dir), ".metrics.after.json"), quiet_metrics(accepted=103, duplicate=3, rejected=1))
    plain_rc = rec.main(["delta", str(run_dir)])
    plain = capsys.readouterr().out
    assert rec.main(["delta", str(run_dir), "--controller-log", str(log)]) == plain_rc == 4
    out = capsys.readouterr().out
    assert "n1_applied_unconfirmed=0 duplicate_only_unexplained=2" in out
    (line,) = [ln for ln in out.splitlines() if ln.startswith("  duplicate_only_unexplained m5 ")]
    assert "failed condition(s) 3:" in line, line
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in n1_added_lines(out, plain))


def test_delta_n1_report_with_many_identities_keeps_its_exit(tmp_path, capsys) -> None:
    """1200 duplicate-only identities of DEV with 1200 A3 ends before them
    (the matching's longest augmenting paths): the report is made, and the
    exit is the plain one."""
    count = 1200
    run_dir = make_delta_fixture(tmp_path, after_metrics=quiet_metrics(accepted=103, duplicate=1 + count, rejected=1))
    extra = [dict(event(10 + i, "duplicate", received_ns=DEADLINE + i), message_id=f"k{i}") for i in range(count)]
    write_jsonl(run_dir / "sent_events.jsonl", SENT + [dict(sent(10 + i), message_id=f"k{i}") for i in range(count)])
    write_jsonl(run_dir / "events.jsonl", EVENTS + extra)
    log = tmp_path / "controller.log"
    log.write_text("".join(a3_line(DEV, T0 + i) + "\n" for i in range(count)), encoding="utf-8")
    assert rec.main(["delta", str(run_dir)]) == 0
    capsys.readouterr()
    assert rec.main(["delta", str(run_dir), "--controller-log", str(log)]) == 0
    out = capsys.readouterr().out
    assert f"n1_applied_unconfirmed=0 duplicate_only_unexplained={count}" in out
    assert f"controller log (--controller-log): {count} A3 connection end(s)" in out


DEEP = "[" * 100_000


@pytest.mark.parametrize("where", ["controller log", "sent_events.jsonl", "restart manifest", "verified snapshot",
                                   "docker events capture"])
def test_delta_n1_report_with_a_deeply_nested_json_line_keeps_its_exit(tmp_path, capsys, where) -> None:
    """The JSON decoder raises RecursionError on deep nesting: in a source
    the N1 options name, such a line is one that is not a record (never an
    exception, never exit 1)."""
    if where in ("controller log", "sent_events.jsonl"):
        run_dir, log = make_n1_fixture(tmp_path)
        plain_argv = ["delta", str(run_dir)]
        argv = plain_argv + ["--controller-log", str(log)]
        if where == "controller log":
            log.write_text("2026-09-30T10:03:10.000000000Z {\"message\": " + DEEP + "\n"
                           + a3_line(DEV, DEADLINE - NS) + "\n", encoding="utf-8")
        else:
            sent_file = run_dir / "sent_events.jsonl"
            sent_file.write_text(sent_file.read_text(encoding="utf-8") + "{\"a\": " + DEEP + "\n", encoding="utf-8")
        expected = "n1_applied_unconfirmed=1 duplicate_only_unexplained=0"
    else:
        from egw_experiments.checksums import write_sha256sums

        run_dir, prefix = make_restart_evidence(tmp_path)
        argv = t6_delta(run_dir, prefix)
        plain_argv = argv[:6]
        target = {"restart manifest": run_dir / "manifest.json", "verified snapshot": run_dir / "twins.after.json",
                  "docker events capture": run_dir / "logs" / "sut" / "docker-events.log"}[where]
        if where == "docker events capture":
            target.write_text("{\"Action\": " + DEEP + "\n" + target.read_text(encoding="utf-8"), encoding="utf-8")
            write_sha256sums(run_dir)
            expected = "n1_applied_unconfirmed=1 duplicate_only_unexplained=0"
        else:
            target.write_text("{\"devices\": " + DEEP + "\n", encoding="utf-8")
            expected = "n1_applied_unconfirmed=0 duplicate_only_unexplained=1"
    plain_rc = rec.main(plain_argv)
    plain = capsys.readouterr().out
    assert rec.main(argv) == plain_rc == 4
    out = capsys.readouterr().out
    assert expected in out, out
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in n1_added_lines(out, plain))


def test_delta_n1_report_that_cannot_be_made_changes_no_exit_and_no_line(tmp_path, capsys, monkeypatch) -> None:
    """Whatever the report meets, delta's own lines and exit stand: an
    exception inside it is reported as a report not made."""
    run_dir, log = make_n1_fixture(tmp_path)

    def boom(**_kwargs):
        raise RuntimeError("unforeseen")

    monkeypatch.setattr(rec.n1_report, "n1_applied_unconfirmed", boom)
    assert rec.main(["delta", str(run_dir), "--controller-log", str(log)]) == 4
    out = capsys.readouterr().out
    added = n1_added_lines(out, N1_FIXTURE_PLAIN)
    assert added[0].startswith("N1 REPORT") and "not made (RuntimeError)" in added[0], added
    assert "  n1_applied_unconfirmed on " not in out
    assert all("OK" not in ln and "MISMATCH" not in ln for ln in added)


def test_delta_n1_sources_line_counts_the_dies_the_window_holds(tmp_path, capsys) -> None:
    """At most one death per run is a source, however many dies of the
    controller the window holds; the sources line says how many it holds."""
    from egw_experiments.checksums import write_sha256sums

    run_dir, prefix = make_restart_evidence(tmp_path)
    capture = run_dir / "logs" / "sut" / "docker-events.log"
    first = json.loads(capture.read_text(encoding="utf-8").splitlines()[0])
    write_jsonl(capture, [first, dict(first, timeNano=first["timeNano"] + 60 * NS, time=first["time"] + 60)])
    write_sha256sums(run_dir)
    assert rec.main(t6_delta(run_dir, prefix)) == 4
    (sources,) = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("  sources: ")]
    assert "one death counted (2 dies of egw-controller-1 captured in the window)" in sources, sources


# ---------------------------------------------------------------------------
# same
# ---------------------------------------------------------------------------


def test_same_exits_0_on_identical_and_4_on_different_snapshots(tmp_path, capsys) -> None:
    prefix = str(tmp_path / RUN_ID)
    write_json(rec.sib(prefix, ".twins.after.json"), twins(503))
    write_json(rec.sib(prefix, ".twins.post-restart.json"), dict(twins(503), label="other"))
    write_json(rec.sib(prefix, ".twins.replay.json"), twins(504))
    assert rec.main(["same", "--prefix", prefix, "after", "post-restart"]) == 0
    assert f"{DEV}: identical" in capsys.readouterr().out  # the label is not compared
    assert rec.main(["same", "--prefix", prefix, "after", "replay"]) == 4
    assert f"{DEV}: DIFFERENT" in capsys.readouterr().out


def test_same_reports_a_device_present_in_one_snapshot_only(tmp_path, capsys) -> None:
    prefix = str(tmp_path / RUN_ID)
    write_json(rec.sib(prefix, ".twins.a.json"), twins(1))
    write_json(rec.sib(prefix, ".twins.b.json"), both(twins(1), ring_twins(1)))
    assert rec.main(["same", "--prefix", prefix, "a", "b"]) == 4
    assert f"{RING}: DIFFERENT (only in 'b')" in capsys.readouterr().out
    assert rec.main(["same", "--prefix", prefix, "b", "a"]) == 4
    out = capsys.readouterr().out
    assert f"{DEV}: identical" in out and f"{RING}: DIFFERENT" in out


def test_same_exits_1_on_a_missing_or_malformed_snapshot(tmp_path, capsys) -> None:
    prefix = str(tmp_path / RUN_ID)
    write_json(rec.sib(prefix, ".twins.a.json"), twins(1))
    assert rec.main(["same", "--prefix", prefix, "a", "b"]) == 1
    assert "twins.b.json missing" in capsys.readouterr().err
    rec.sib(prefix, ".twins.b.json").write_text("null", "utf-8")
    assert rec.main(["same", "--prefix", prefix, "a", "b"]) == 1
    assert "not a JSON object" in capsys.readouterr().err


def tree(root: Path) -> dict[str, bytes]:
    """Every file under root with its bytes: a command that writes nothing leaves it equal."""
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------
# acceptance (decision 3 of 2026-09-30): test 3 is not timed, but every valid
# message must have an accepted line in the copy of the events fetched after
# the run's final drain
# ---------------------------------------------------------------------------
#: m0 and m1 valid, m2 intended invalid: test 3 in miniature.
ACC_SENT = [sent(0), sent(1), sent(2, intended_invalid=True)]


def make_acceptance(tmp_path: Path, copy_records, sent_records=ACC_SENT) -> tuple[Path, Path]:
    run_dir = make_run(tmp_path, events=None, sent_records=sent_records,
                       manifest=sim_manifest(totals={"sent": len(sent_records), "intended_invalid": 1}))
    copy = rec.sib(str(run_dir), ".events.post-drain.jsonl")
    write_jsonl(copy, copy_records)
    return run_dir, copy


def acceptance(run_dir: Path, copy: Path) -> int:
    return rec.main(["acceptance", str(run_dir), "--events", str(copy)])


def test_acceptance_counts_a_late_acceptance_and_writes_nothing(tmp_path, capsys) -> None:
    # m0 received and confirmed an hour after the deadline: late, but accepted by the end of the drain
    run_dir, copy = make_acceptance(tmp_path, [
        event(0, "accepted", DEADLINE + 3_600 * NS, received_ns=DEADLINE + 3_000 * NS),
        event(1, "accepted", T0 - 5),
        event(2, "rejected"),
    ])
    before = tree(tmp_path)
    assert acceptance(run_dir, copy) == rec.EXIT_OK
    out = capsys.readouterr().out
    assert f"ACCEPTANCE BY THE END OF THE DRAIN {RUN_ID}" in out
    assert "valid=2 accepted by the end of the drain=2 never accepted=0" in out
    assert "NEVER ACCEPTED" not in out
    assert "-> OK: every valid message" in out and "-> FAIL" not in out
    assert tree(tmp_path) == before  # writes nothing


def test_acceptance_reads_no_timestamp(tmp_path, capsys) -> None:
    """No deadline and no stamp: stamps that no deadline accounting could read change nothing."""
    odd = [dict(event(0, "accepted"), ditto_ack_monotonic_ns="not a stamp", received_monotonic_ns=None),
           dict(event(1, "accepted"), ditto_ack_monotonic_ns=-1)]
    run_dir, copy = make_acceptance(tmp_path, odd)
    assert acceptance(run_dir, copy) == rec.EXIT_OK
    assert "never accepted=0" in capsys.readouterr().out


def test_acceptance_a_failure_then_an_acceptance_counts_as_accepted(tmp_path, capsys) -> None:
    run_dir, copy = make_acceptance(tmp_path, [event(0, "accepted", T0), event(1, "failed"),
                                               event(1, "duplicate"), event(1, "accepted", DEADLINE + NS)])
    assert acceptance(run_dir, copy) == rec.EXIT_OK
    assert "valid=2 accepted by the end of the drain=2 never accepted=0" in capsys.readouterr().out


@pytest.mark.parametrize("m1_lines, shown", [
    ([event(1, "failed")], "outcome lines in the copy: failed x1"),
    ([event(1, "duplicate"), event(1, "duplicate")], "outcome lines in the copy: duplicate x2"),
    ([event(1, "rejected")], "outcome lines in the copy: other x1 (rejected)"),
    ([event(1, "failed"), event(1, "duplicate"), event(1, "bogus")],
     "outcome lines in the copy: failed x1, duplicate x1, other x1 (bogus)"),
    ([], "outcome lines in the copy: none"),
    # accepted, but under another run id: not this run's identity
    ([event(1, "accepted", T0, run_id="itest-other")], "outcome lines in the copy: none"),
], ids=["failed", "duplicate-only", "valid-rejected", "mixed", "no-line", "other-run-id"])
def test_acceptance_names_a_valid_message_never_accepted_with_its_outcome_lines(tmp_path, capsys, m1_lines,
                                                                                shown) -> None:
    run_dir, copy = make_acceptance(tmp_path, [event(0, "accepted", T0), *m1_lines, event(2, "rejected")])
    assert acceptance(run_dir, copy) == rec.EXIT_MISMATCH
    out = capsys.readouterr().out
    assert "valid=2 accepted by the end of the drain=1 never accepted=1" in out
    assert f"  NEVER ACCEPTED: m1 (smartwatch seq=1) {shown}" in out.splitlines()
    assert "  NEVER ACCEPTED: m0" not in out
    assert out.splitlines()[-1].startswith("-> FAIL: 1 valid message")


def test_acceptance_names_every_valid_message_never_accepted(tmp_path, capsys) -> None:
    records = [sent(seq) for seq in range(30)]
    run_dir, copy = make_acceptance(tmp_path, [event(0, "accepted", T0)], sent_records=records)
    assert acceptance(run_dir, copy) == rec.EXIT_MISMATCH
    out = capsys.readouterr().out
    assert "valid=30 accepted by the end of the drain=1 never accepted=29" in out
    assert len([ln for ln in out.splitlines() if ln.startswith("  NEVER ACCEPTED: ")]) == 29  # each one, no cap


@pytest.mark.parametrize("m2_lines", [[], [event(2, "failed")], [event(2, "duplicate")]],
                         ids=["no-line", "failed", "duplicate"])
def test_acceptance_does_not_require_an_intended_invalid_message(tmp_path, capsys, m2_lines) -> None:
    run_dir, copy = make_acceptance(tmp_path, [event(0, "accepted", T0), event(1, "accepted", T0), *m2_lines])
    assert acceptance(run_dir, copy) == rec.EXIT_OK
    assert "valid=2 accepted by the end of the drain=2 never accepted=0" in capsys.readouterr().out


def test_acceptance_requires_every_message_not_marked_intended_invalid_exactly(tmp_path, capsys) -> None:
    """Conservative reading: only intended_invalid true exempts a message; any other value keeps it required."""
    records = [sent(0), dict(sent(1), intended_invalid="true"), dict(sent(2), intended_invalid=None)]
    run_dir, copy = make_acceptance(tmp_path, [event(0, "accepted", T0)], sent_records=records)
    assert acceptance(run_dir, copy) == rec.EXIT_MISMATCH
    out = capsys.readouterr().out
    assert "valid=3 accepted by the end of the drain=1 never accepted=2" in out


@pytest.mark.parametrize("case", ["copy missing", "copy truncated", "sent missing", "sent truncated",
                                  "sent empty", "no valid message", "message_id missing", "message_id empty",
                                  "message_id twice", "two run ids", "no run id"])
def test_acceptance_exits_1_on_bad_input(tmp_path, capsys, case) -> None:
    run_dir, copy = make_acceptance(tmp_path, [event(0, "accepted", T0), event(1, "accepted", T0)])
    sent_path = run_dir / "sent_events.jsonl"
    rewrite = {
        "sent empty": [],
        "no valid message": [sent(0, intended_invalid=True), sent(1, intended_invalid=True)],
        "message_id missing": [sent(0), {k: v for k, v in sent(1).items() if k != "message_id"}],
        "message_id empty": [sent(0), dict(sent(1), message_id="")],
        "message_id twice": [sent(0), sent(1), sent(1)],
        "two run ids": [sent(0), dict(sent(1), run_id="itest-other")],
        "no run id": [{k: v for k, v in sent(0).items() if k != "run_id"}, sent(1)],
    }
    reason = {
        "copy missing": "post-drain.jsonl missing", "copy truncated": "not a JSON object",
        "sent missing": "sent_events.jsonl missing", "sent truncated": "not a JSON object",
        "sent empty": "holds no published record", "no valid message": "holds no valid message",
        "message_id missing": "no usable message_id", "message_id empty": "no usable message_id",
        "message_id twice": "occurs more than once", "two run ids": "one run_id", "no run id": "one run_id",
    }[case]
    if case == "copy missing":
        copy.unlink()
    elif case == "copy truncated":
        copy.write_text(copy.read_text("utf-8") + '{"run_id": "itest-x", "outc', "utf-8")
    elif case == "sent missing":
        sent_path.unlink()
    elif case == "sent truncated":
        sent_path.write_text(sent_path.read_text("utf-8") + '{"message_id": ', "utf-8")
    else:
        write_jsonl(sent_path, rewrite[case])
        # the manifest agrees with the rewritten file: each case is refused for its own reason
        write_json(run_dir / "manifest.json",
                   sim_manifest(totals={"sent": len(rewrite[case]), "intended_invalid": 1}))
    before = tree(tmp_path)
    assert acceptance(run_dir, copy) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert captured.err.startswith("error: ") and captured.out == ""  # nothing judged, nothing printed
    assert reason in captured.err, captured.err
    assert tree(tmp_path) == before


# ---------------------------------------------------------------------------
# replay-check (decision 4 of 2026-09-30): test 4's replay judged per identity
# ---------------------------------------------------------------------------
REPLAY_SENT = [sent(0), sent(1), sent(2)]
#: The first run's log as its 'finish' fetched it: every message accepted once, in time.
PRE = [event(0, "accepted", T0 - 5, received_ns=T0 - 4 * NS),
       event(1, "accepted", T0 - 4, received_ns=T0 - 3 * NS),
       event(2, "accepted", T0 - 3, received_ns=T0 - 2 * NS)]
#: The 'after' reading: every field the same-process rule reads, above zero, and the controller clock when it was
#: read ('finish' takes it after the window closed; the replay is published later still).
AFTER = metrics(accepted=100, rejected=5, duplicate=5, failed=5, dropped=5, processing_errors=5,
                received=125, in_progress=0, mqtt_connection=1, uptime_s=50.0, unacked=0,
                monotonic_ns=DEADLINE + 10 * NS)
#: when the replay's lines are received: after the 'after' reading
REPLAY_NS = DEADLINE + 100 * NS


def dup(seq: int) -> dict:
    """A duplicate line the replay adds to the log."""
    return event(seq, "duplicate", received_ns=REPLAY_NS)


def replay_reading(duplicates: int, **changes) -> dict:
    """The 'replay' reading of the same process: only duplicate (and received) moved."""
    body = dict(AFTER, duplicate=AFTER["duplicate"] + duplicates, received=AFTER["received"] + duplicates,
                uptime_s=AFTER["uptime_s"] + 400.0, monotonic_ns=AFTER["monotonic_ns"] + 400 * NS)
    body.update(changes)
    return body


def make_replay(tmp_path: Path, added, *, pre=PRE, replay: dict | None = None, after: dict | None = None,
                replay_sent=REPLAY_SENT) -> tuple[Path, Path]:
    run_dir = make_run(tmp_path, events=[*pre, *added], sent_records=REPLAY_SENT,
                       manifest=sim_manifest(totals={"sent": 3, "intended_invalid": 0}))
    prefix = str(run_dir)
    write_jsonl(rec.sib(prefix, ".events.pre-replay.jsonl"), pre)  # a byte prefix: the same writer
    replay_dir = tmp_path / "itest-replay" / RUN_ID
    replay_dir.mkdir(parents=True)
    write_json(replay_dir / "manifest.json", sim_manifest(totals={"sent": len(replay_sent), "intended_invalid": 0}))
    write_jsonl(replay_dir / "sent_events.jsonl", replay_sent)
    duplicates = sum(1 for e in added if e["outcome"] == "duplicate")
    write_json(rec.sib(prefix, ".metrics.after.json"), after or AFTER)
    write_json(rec.sib(prefix, ".metrics.replay.json"), replay or replay_reading(duplicates))
    return run_dir, replay_dir


def replay_check(run_dir: Path, replay_dir: Path, *extra: str) -> int:
    return rec.main(["replay-check", str(run_dir), "--replay-dir", str(replay_dir), *extra])


def test_replay_check_every_replayed_identity_a_duplicate_exits_0_and_writes_nothing(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)])
    before = tree(tmp_path)
    assert replay_check(run_dir, replay_dir) == rec.EXIT_OK
    out = capsys.readouterr().out
    assert f"REPLAY CHECK {RUN_ID}: replayed identities=3; lines added since the pre-replay copy=3" in out
    assert "duplicate_replayed=3 of 3" in out
    assert "duplicate_redelivery=0" in out and "mqtt_connection 1 -> 1 (delta 0)" in out
    assert "one controller process" in out and "NOT one controller process" not in out
    assert "/metrics accepted: 100 -> 100 (delta 0): OK" in out
    assert "/metrics duplicate: 5 -> 8 (delta 3); duplicate_replayed + duplicate_redelivery = 3 + 0 = 3: equal" in out
    assert "FAIL" not in out and out.splitlines()[-1].startswith("-> OK: ")
    assert tree(tmp_path) == before  # writes nothing


def test_replay_check_the_pre_replay_copy_can_be_named(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)])
    moved = tmp_path / "elsewhere.jsonl"
    rec.sib(str(run_dir), ".events.pre-replay.jsonl").rename(moved)
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED  # the default copy is gone
    assert ".events.pre-replay.jsonl missing" in capsys.readouterr().err
    assert replay_check(run_dir, replay_dir, "--events-before", str(moved)) == rec.EXIT_OK


def test_replay_check_a_redelivery_within_the_reconnection_budget_is_tolerated_not_explained(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(1), dup(2)],
                                      replay=replay_reading(4, mqtt_connection=2))
    assert replay_check(run_dir, replay_dir) == rec.EXIT_OK
    out = capsys.readouterr().out
    assert "duplicate_replayed=3 of 3" in out and "duplicate_redelivery=1" in out
    assert "mqtt_connection 1 -> 2 (delta 1)" in out
    assert "consistent with the reconnection budget" in out
    assert "caused" not in out and "because" not in out  # a tolerance, never a cause
    assert "= 3 + 1 = 4: equal" in out


def test_replay_check_a_redelivery_beyond_the_reconnection_budget_fails(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(1), dup(2)])
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    out = capsys.readouterr().out
    assert "duplicate_redelivery=1" in out and "mqtt_connection 1 -> 1 (delta 0)" in out
    assert "beyond the reconnection budget" in out and "consistent with the reconnection budget" not in out
    assert out.splitlines()[-1].startswith("-> FAIL: ")


@pytest.mark.parametrize("connections, expected", [(1, rec.EXIT_MISMATCH), (2, rec.EXIT_OK)])
def test_replay_check_a_duplicate_of_an_identity_not_replayed_is_redelivery(tmp_path, capsys, connections,
                                                                           expected) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2), dup(9)],
                                      replay=replay_reading(4, mqtt_connection=connections))
    assert replay_check(run_dir, replay_dir) == expected
    out = capsys.readouterr().out
    assert "duplicate_replayed=3 of 3" in out and "duplicate_redelivery=1" in out


def test_replay_check_a_replayed_identity_without_a_duplicate_fails(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1)])
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    out = capsys.readouterr().out
    assert "duplicate_replayed=2 of 3" in out
    assert "  NO DUPLICATE FROM THE REPLAY: m2" in out.splitlines()


def test_replay_check_an_acceptance_from_the_replay_fails(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), event(2, "accepted", REPLAY_NS + NS,
                                                                       received_ns=REPLAY_NS)],
                                      replay=replay_reading(2, accepted=101, received=128))
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    lines = capsys.readouterr().out.splitlines()
    assert "  ACCEPTED FROM THE REPLAY: m2" in lines
    assert "  MORE THAN ONE ACCEPTED LINE: m2 (2 accepted lines)" in lines
    assert "/metrics accepted: 100 -> 101 (delta 1): FAIL" in lines


def test_replay_check_counts_raw_accepted_lines_not_the_in_window_accounting(tmp_path, capsys) -> None:
    """A late repeat of m0 before the replay: compute_run_metrics files it under late_confirmations, never under
    double_accepted; the identity has two accepted lines all the same."""
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)],
                                      pre=[*PRE, event(0, "accepted", DEADLINE + 1, received_ns=DEADLINE)])
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    lines = capsys.readouterr().out.splitlines()
    assert "  MORE THAN ONE ACCEPTED LINE: m0 (2 accepted lines)" in lines
    assert not [ln for ln in lines if ln.startswith("  ACCEPTED FROM THE REPLAY")]


def test_replay_check_readings_of_two_processes_fail_and_nothing_is_differenced(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)],
                                      replay=replay_reading(3, started_at="2026-09-18T11:00:00.000Z"))
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    out = capsys.readouterr().out
    assert "NOT one controller process" in out and "started_at" in out
    assert "(delta" not in out  # no difference is taken across two processes
    assert "not evaluable" in out
    assert out.splitlines()[-1].startswith("-> FAIL: ")


@pytest.mark.parametrize("field", ["uptime_s", "received", "accepted", "rejected", "duplicate", "failed", "dropped",
                                   "processing_errors", "mqtt_connection"])
def test_replay_check_a_decreasing_field_means_two_processes(tmp_path, capsys, field) -> None:
    changes = {field: 10.0 if field == "uptime_s" else AFTER[field] - 1}
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)], replay=replay_reading(3, **changes))
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    out = capsys.readouterr().out
    assert "NOT one controller process" in out
    assert f"{field} {AFTER[field]} -> {changes[field]} decreased" in out
    assert "(delta" not in out


def test_replay_check_a_queue_not_empty_in_the_replay_reading_fails(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)], replay=replay_reading(3, queue_depth=1))
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    assert "/metrics queue_depth=1 in the 'replay' reading: FAIL" in capsys.readouterr().out


def test_replay_check_an_accepted_counter_that_moved_fails(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)],
                                      replay=replay_reading(3, accepted=101, received=129))
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    assert "/metrics accepted: 100 -> 101 (delta 1): FAIL" in capsys.readouterr().out


def test_replay_check_the_metrics_duplicate_difference_is_reported_and_decides_nothing(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)], replay=replay_reading(5))
    assert replay_check(run_dir, replay_dir) == rec.EXIT_OK
    out = capsys.readouterr().out
    assert "/metrics duplicate: 5 -> 10 (delta 5); duplicate_replayed + duplicate_redelivery = 3 + 0 = 3: " \
           "NOT EQUAL (reported, decides nothing)" in out


def _without(body: dict, key: str) -> dict:
    return {k: v for k, v in body.items() if k != key}


@pytest.mark.parametrize("sibling, body, field", [
    (".metrics.replay.json", _without(replay_reading(3), "mqtt_connection"), "mqtt_connection"),
    (".metrics.replay.json", replay_reading(3, mqtt_connection=True), "mqtt_connection"),
    (".metrics.replay.json", replay_reading(3, mqtt_connection=-1), "mqtt_connection"),
    (".metrics.replay.json", replay_reading(3, mqtt_connection="2"), "mqtt_connection"),
    (".metrics.replay.json", replay_reading(3, mqtt_connection=1.0), "mqtt_connection"),
    (".metrics.replay.json", replay_reading(3, mqtt_connection=None), "mqtt_connection"),
    (".metrics.after.json", _without(AFTER, "mqtt_connection"), "mqtt_connection"),
    (".metrics.after.json", _without(AFTER, "started_at"), "started_at"),
    (".metrics.replay.json", replay_reading(3, started_at=""), "started_at"),
    (".metrics.replay.json", _without(replay_reading(3), "uptime_s"), "uptime_s"),
    (".metrics.replay.json", replay_reading(3, uptime_s="450"), "uptime_s"),
    (".metrics.replay.json", replay_reading(3, uptime_s=True), "uptime_s"),
    (".metrics.after.json", _without(AFTER, "received"), "received"),
    (".metrics.after.json", _without(AFTER, "processing_errors"), "processing_errors"),
    (".metrics.replay.json", _without(replay_reading(3), "queue_depth"), "queue_depth"),
    (".metrics.replay.json", replay_reading(3, duplicate=8.0), "duplicate"),
])
def test_replay_check_exits_1_on_a_field_absent_or_not_of_its_type(tmp_path, capsys, sibling, body, field) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)])
    write_json(rec.sib(str(run_dir), sibling), body)
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert sibling in captured.err and field in captured.err, captured.err
    assert captured.out == ""  # never read as zero, nothing judged


@pytest.mark.parametrize("sibling", [".metrics.replay.json", ".metrics.after.json"])
def test_replay_check_exits_1_when_a_reading_is_missing(tmp_path, capsys, sibling) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)])
    rec.sib(str(run_dir), sibling).unlink()
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert f"{sibling} missing" in captured.err and captured.out == ""


@pytest.mark.parametrize("case", ["first line differs", "log shorter than the copy", "copy without its last newline",
                                  "copy empty"])
def test_replay_check_exits_1_when_the_pre_replay_copy_is_not_a_prefix_of_the_log(tmp_path, capsys, case) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)])
    copy = rec.sib(str(run_dir), ".events.pre-replay.jsonl")
    if case == "first line differs":
        write_jsonl(copy, [event(0, "accepted", T0 - 5, received_ns=T0 - 2 * NS), *PRE[1:]])
    elif case == "log shorter than the copy":
        write_jsonl(run_dir / "events.jsonl", PRE[:2])
    elif case == "copy without its last newline":
        copy.write_bytes(copy.read_bytes().rstrip(b"\n"))
    else:
        copy.write_bytes(b"")
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert "pre-replay" in captured.err and captured.out == ""


def test_replay_check_exits_1_on_a_truncated_log(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)])
    with open(run_dir / "events.jsonl", "a", encoding="utf-8") as fh:
        fh.write('{"run_id": ')
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    assert "not a JSON object" in capsys.readouterr().err


@pytest.mark.parametrize("case", ["empty", "message_id twice", "message_id missing", "missing", "two run ids"])
def test_replay_check_exits_1_on_a_replay_whose_identities_cannot_be_told_apart(tmp_path, capsys, case) -> None:
    rows = {"empty": [], "message_id twice": [sent(0), sent(1), sent(1)],
            "message_id missing": [sent(0), _without(sent(1), "message_id")],
            "two run ids": [sent(0), dict(sent(1), run_id="itest-other")]}.get(case, REPLAY_SENT)
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)], replay_sent=rows)
    if case == "missing":
        (replay_dir / "sent_events.jsonl").unlink()
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert "sent_events.jsonl" in captured.err and captured.out == ""


def test_replay_check_exits_1_on_a_line_of_another_run_id(tmp_path, capsys) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2), event(3, "duplicate", run_id="itest-other")])
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert "itest-other" in captured.err and captured.out == ""


@pytest.mark.parametrize("received_ns", [T0 + 2 * NS, AFTER["monotonic_ns"], None],
                         ids=["before-the-after-reading", "at-the-after-reading", "no-stamp"])
def test_replay_check_never_credits_the_replay_with_a_line_received_before_the_after_reading(tmp_path, capsys,
                                                                                            received_ns) -> None:
    """A line of the FIRST run appended after the pre-replay fetch and received before the 'after' reading (a late
    redelivery of m0), while the replay's own m0 left no line: by position alone it would stand for m0's duplicate
    from the replay. The controller stamps it on the clock of the 'after' reading (one process), so it is not the
    replay's: the replay interval cannot be told from the copy, nothing is judged (exit 1), never a pass."""
    gap = dict(event(0, "duplicate", received_ns=T0), received_monotonic_ns=received_ns)
    run_dir, replay_dir = make_replay(tmp_path, [gap, dup(1), dup(2)])
    before = tree(tmp_path)
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert "record 4" in captured.err and "'after' reading" in captured.err, captured.err
    assert "replay interval cannot be told" in captured.err, captured.err
    assert captured.out == ""  # nothing judged, nothing printed
    assert tree(tmp_path) == before


def test_replay_check_the_line_of_the_verifier_counter_example_is_not_a_pass(tmp_path, capsys) -> None:
    """The counter-example as found: the 'after' reading already counts the gap duplicate (it was logged before it),
    the replay adds m1 and m2 only. Before the fix this exited 0 with 'duplicate_replayed=3 of 3'."""
    gap = event(0, "duplicate", received_ns=T0 + 2 * NS)
    after = dict(AFTER, duplicate=AFTER["duplicate"] + 1, received=AFTER["received"] + 1)
    run_dir, replay_dir = make_replay(tmp_path, [gap, dup(1), dup(2)], after=after,
                                      replay=dict(after, duplicate=after["duplicate"] + 2,
                                                  received=after["received"] + 2, uptime_s=450.0,
                                                  monotonic_ns=after["monotonic_ns"] + 400 * NS))
    assert replay_check(run_dir, replay_dir) != rec.EXIT_OK
    assert "duplicate_replayed=3 of 3" not in capsys.readouterr().out


@pytest.mark.parametrize("value", ["absent", None, "123", 1.5, True])
def test_replay_check_exits_1_without_the_controller_clock_of_the_after_reading(tmp_path, capsys, value) -> None:
    """Within one process the 'after' reading's monotonic_ns bounds the replay's lines; without it (an integer, CONTRACTS
    5) no line can be shown to be the replay's, and an absent field is never read as zero."""
    after = _without(AFTER, "monotonic_ns") if value == "absent" else dict(AFTER, monotonic_ns=value)
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)], after=after)
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert ".metrics.after.json" in captured.err and "monotonic_ns" in captured.err, captured.err
    assert captured.out == ""


def test_replay_check_two_processes_still_fail_whatever_the_stamps(tmp_path, capsys) -> None:
    """Across two processes the stamps are not read (the clock of a new boot starts again): test 4 fails, as the
    same-process rule says, and is not turned into 'not evaluated'."""
    early = [event(seq, "duplicate", received_ns=T0) for seq in range(3)]
    run_dir, replay_dir = make_replay(tmp_path, early, replay=replay_reading(3, started_at="2026-09-18T11:00:00.000Z",
                                                                             monotonic_ns=NS))
    assert replay_check(run_dir, replay_dir) == rec.EXIT_MISMATCH
    assert "NOT one controller process" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# acceptance and replay-check: the sent file must be the whole of what the
# simulator says it published (totals.sent of its manifest.json)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("manifest", [
    sim_manifest(totals={"sent": 4, "intended_invalid": 1}, completed=False),
    sim_manifest(totals={"sent": 4, "intended_invalid": 1}),
    sim_manifest(totals={"sent": "3", "intended_invalid": 1}),
    sim_manifest(totals=None),
    None,
], ids=["one-record-short-not-completed", "one-record-short", "totals-sent-a-string", "no-totals", "no-manifest"])
def test_acceptance_exits_1_on_a_sent_file_the_simulator_totals_do_not_match(tmp_path, capsys, manifest) -> None:
    """m3 was published (the simulator counted it) but its record is not in the file: a message never judged is not
    a message accepted. Without a whole file nothing is judged."""
    run_dir, copy = make_acceptance(tmp_path, [event(0, "accepted", T0), event(1, "accepted", T0)])
    if manifest is None:
        (run_dir / "manifest.json").unlink()
    else:
        write_json(run_dir / "manifest.json", manifest)
    before = tree(tmp_path)
    assert acceptance(run_dir, copy) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert "manifest.json" in captured.err and captured.out == "", captured.err
    assert tree(tmp_path) == before


def test_acceptance_a_simulator_run_not_completed_is_judged_on_the_whole_file_it_left(tmp_path, capsys) -> None:
    """completed=false with a whole file (totals.sent = the records): every published message is listed, so it is
    judged; nothing about the interruption is decided here."""
    run_dir, copy = make_acceptance(tmp_path, [event(0, "accepted", T0), event(1, "accepted", T0)])
    write_json(run_dir / "manifest.json", sim_manifest(totals={"sent": 3, "intended_invalid": 1}, completed=False))
    assert acceptance(run_dir, copy) == rec.EXIT_OK
    assert "valid=2 accepted by the end of the drain=2 never accepted=0" in capsys.readouterr().out


@pytest.mark.parametrize("manifest", [sim_manifest(totals={"sent": 4, "intended_invalid": 0}, completed=False),
                                      sim_manifest(totals={"sent": 2, "intended_invalid": 0}), None],
                         ids=["one-record-short", "one-record-too-many", "no-manifest"])
def test_replay_check_exits_1_on_a_replay_sent_file_the_simulator_totals_do_not_match(tmp_path, capsys,
                                                                                     manifest) -> None:
    run_dir, replay_dir = make_replay(tmp_path, [dup(0), dup(1), dup(2)])
    if manifest is None:
        (replay_dir / "manifest.json").unlink()
    else:
        write_json(replay_dir / "manifest.json", manifest)
    assert replay_check(run_dir, replay_dir) == rec.EXIT_FAILED
    captured = capsys.readouterr()
    assert "manifest.json" in captured.err and captured.out == "", captured.err


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def test_sib_appends_to_the_prefix_and_ignores_a_trailing_slash(tmp_path) -> None:
    assert rec.sib("p/itest-x/", ".marker.json") == Path("p/itest-x.marker.json")
    assert rec.sib("p/itest-x", ".twins.after.json") == Path("p/itest-x.twins.after.json")


def test_save_new_never_overwrites(tmp_path) -> None:
    path = tmp_path / "deep" / "f.json"
    rec.save_new(path, {"a": 1})
    with pytest.raises(rec.HelperError):
        rec.save_new(path, {"a": 2})
    assert json.loads(path.read_text("utf-8")) == {"a": 1}


# ---------------------------------------------------------------------------
# Work order of 2026-09-29 (G3 instrumentation readiness), A1: a typed HTTP
# failure of the real marker poll (run.poll_controller_marker, the network
# read replaced) is a failed poll, never a crash and never a marker
# ---------------------------------------------------------------------------


class ScriptedGet:
    """Stands for run._http_get_json under the REAL poll_controller_marker:
    an exception in the script is raised, an integer answers as the
    controller clock; the last item repeats."""

    def __init__(self, *script) -> None:
        self.script = list(script)
        self.calls = 0

    def __call__(self, url, timeout_s):
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        return {"monotonic_ns": item, "wall_utc": "2026-09-18T10:01:02.000Z"}


def real_poll_with(monkeypatch, *script) -> ScriptedGet:
    get = ScriptedGet(*script)
    monkeypatch.setattr(run_mod, "_http_get_json", get)
    # the helper's own poll, in case a fixture replaced it with a fake
    monkeypatch.setattr(rec, "poll_controller_marker", run_mod.poll_controller_marker)
    return get


def test_mark_exits_1_without_a_marker_file_on_a_typed_http_failure(tmp_path, monkeypatch, capsys) -> None:
    run_dir = make_run(tmp_path, events=None)
    real_poll_with(monkeypatch, http.client.IncompleteRead(b'{"mono', 30))
    assert rec.main(["mark", str(run_dir), "--controller-url", CTRL]) == rec.EXIT_FAILED
    err = capsys.readouterr().err
    assert "marker UNAVAILABLE" in err and "IncompleteRead" in err
    assert not (tmp_path / f"{RUN_ID}.marker.json").exists()


def test_wait_counts_a_typed_http_failure_as_a_failed_poll_and_closes_on_the_real_reading(
    tmp_path, monkeypatch, capsys
) -> None:
    run_dir, clock, _ = _wait_fixture(tmp_path, monkeypatch, [DEADLINE + 1])
    get = real_poll_with(monkeypatch, http.client.BadStatusLine(""), DEADLINE + 1)
    assert rec.main(["wait", str(run_dir), "--controller-url", CTRL]) == rec.EXIT_OK
    assert get.calls == 2
    assert clock.sleeps == [rec.WAIT_POLL_INTERVAL_S]      # the failure waits the usual interval, no fast retry
    closed = json.loads((tmp_path / f"{RUN_ID}.window-closed.json").read_text("utf-8"))
    # the window file is the real reading, nothing of the failed one
    assert closed["ok"] is True and closed["error"] is None
    assert closed["monotonic_ns"] == DEADLINE + 1
    assert "window closed on the controller clock" in capsys.readouterr().out


def test_wait_gives_up_on_typed_http_failures_without_a_window_file(tmp_path, monkeypatch, capsys) -> None:
    run_dir, clock, _ = _wait_fixture(tmp_path, monkeypatch, [DEADLINE + 1])
    real_poll_with(monkeypatch, http.client.IncompleteRead(b"", 5))
    assert rec.main(["wait", str(run_dir), "--extra-timeout", "4"]) == rec.EXIT_FAILED
    assert "gave up" in capsys.readouterr().err
    budget = protocol.CONFIRMATION_WINDOW_S + 4
    assert budget < sum(clock.sleeps) <= budget + rec.WAIT_POLL_INTERVAL_S
    assert set(clock.sleeps) == {rec.WAIT_POLL_INTERVAL_S}
    assert not (tmp_path / f"{RUN_ID}.window-closed.json").exists()


@pytest.mark.parametrize("exc", [KeyboardInterrupt(), TypeError("bug")], ids=["KeyboardInterrupt", "TypeError"])
def test_wait_lets_cancellation_and_programming_errors_propagate(tmp_path, monkeypatch, capsys, exc) -> None:
    run_dir, _clock, _ = _wait_fixture(tmp_path, monkeypatch, [DEADLINE + 1])
    get = real_poll_with(monkeypatch, http.client.IncompleteRead(b"", 5), exc)
    with pytest.raises(type(exc)):
        rec.main(["wait", str(run_dir)])
    assert get.calls == 2
    assert not (tmp_path / f"{RUN_ID}.window-closed.json").exists()
