"""Tests for egw_experiments.itest_reconcile (runbook Sections 6 and 7 helper).

Fakes only: the controller marker (``poll_controller_marker``), the Ditto read
(``get_twin`` / ``urllib.request.urlopen``) and the clock (``time``) are
replaced in the module under test; the accounting is the UNMODIFIED
``compute_run_metrics``. No socket, no docker, no real waiting.
"""
from __future__ import annotations

import ast
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
    for sub in ("mark", "wait", "check", "snap", "delta", "same"):
        assert sub in proc.stdout
    assert "exit codes" in proc.stdout


def test_usage_errors_exit_2(capsys) -> None:
    for argv in ([], ["bogus"], ["snap", "--label", "x"], ["same", "--prefix", "p", "a"]):
        with pytest.raises(SystemExit) as excinfo:
            rec.main(argv)
        assert excinfo.value.code == 2
    capsys.readouterr()


REC_FRAGMENT = re.compile(  # not the quoted mentions inside shell comments
    r"(?<!')\$REC ((?:mark|wait|check|snap|delta|same)\b.*?)(?=;|&&|\|\||[)}>]|\s#|$)"
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
