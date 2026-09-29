"""Cases for tools/session/events_coverage.py, the checker the docker-events
fetch of the finite proof applies to the run's continuous events capture.

Each case writes, as the fetch brings them back from the guest, the five
files of one capture - the events, the recorder's lifecycle, the start
facts, the CLI's stderr and the stop record - for a run whose window is
[T0, T1] on the guest clock, and runs the checker as the fetch runs it (one
process, its exit status and its 'key=value' lines). The capture of a run
with the proof's fault is complete; every case breaks ONE thing of it, and
the rule that thing belongs to must be the one that says so. They say
nothing about a real daemon: that the daemon serves its replay and its live
stream under one lock, that the CLI answers 0 when the stream is closed, and
the fields 'systemctl show docker' prints on the guest's systemd are for the
next authorised session to confirm.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "tools" / "session" / "events_coverage.py"
NS = 10 ** 9
T0 = 1_790_629_309          # RUN_T0: the recorder found ready (2026-09-28T21:01:49Z)
T1 = T0 + 1_500             # the stop request of the docker-events fetch
FAULT = T0 + 660            # the fault's kill, die and start
CONTROLLER = "egw-controller-1"
BROKER = "egw-mosquitto-1"


def event(action: str, second: int, name: str = BROKER, fraction_ns: int = 0, **attributes: str) -> dict:
    """One event as 'docker events --format {{json .}}' prints it."""
    cid = ("0f" if name == CONTROLLER else "00") + "a" * 62
    return {"status": action, "id": cid, "from": f"stub/{name}:1", "Type": "container", "Action": action,
            "Actor": {"ID": cid, "Attributes": {"image": f"stub/{name}:1", "name": name, **attributes}},
            "scope": "local", "time": second, "timeNano": second * NS + fraction_ns}


def events_of_a_run(heartbeat_s: int = 30, gap: tuple[int, int] | None = None) -> list[dict]:
    """The replay from before T0, the healthchecks' exec events every
    HEARTBEAT_S seconds through the window and past T1 (the closing
    witness), and the fault's three events."""
    out = []
    for second in range(T0 - 120, T1 + 5, heartbeat_s):
        if gap and gap[0] < second < gap[1]:
            continue
        out.append(event("exec_die: /bin/sh -c mosquitto_sub -t $SYS/# -C 1", second))
    out += [event("kill", FAULT, CONTROLLER, signal="9"), event("die", FAULT, CONTROLLER, 1000, exitCode="137"),
            event("start", FAULT + 14, CONTROLLER)]
    out.append(event("exec_die: /bin/sh -c mosquitto_sub -t $SYS/# -C 1", T1 + 2, fraction_ns=5))
    return sorted(out, key=lambda e: e["timeNano"])


LIFECYCLE = (f"start epoch={T0 - 2} pid=4242 since={T0 - 122}\n"
             f"cli-start epoch={T0 - 2} cli_pid=4245\n"
             f"ready epoch={T0} events_bytes=880 unit=active\n"
             f"cli-exit epoch={T1 + 3} rc=143 stop_requested=yes\n")
START_FACTS = "boot_id=488582b6-eae8-477b-9a6d-8f5e04947238\nMainPID=321\nExecMainStartTimestampMonotonic=4200000\n"
STOP = (f"stop_requested_guest_epoch={T1}\nunit_state_before_stop=active\n"
        "boot_id=488582b6-eae8-477b-9a6d-8f5e04947238\nMainPID=321\nExecMainStartTimestampMonotonic=4200000\n"
        "closing_witness_seen=yes\nunit_state_after_stop=inactive\n")


def capture(tmp_path: Path, events: list[dict] | None = None, **files: str | None) -> Path:
    """The five files of a complete capture; FILES replaces one (by its name
    with '.' as '_': events_jsonl, lifecycle_txt, start_facts_txt, cli_stderr,
    stop_txt), and None leaves it absent."""
    directory = tmp_path / "fetched"
    directory.mkdir(parents=True)
    texts = {
        "events.jsonl": "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in (events or events_of_a_run())),
        "lifecycle.txt": LIFECYCLE, "start-facts.txt": START_FACTS, "cli.stderr": "", "stop.txt": STOP,
    }
    for key, value in files.items():
        name = {"events_jsonl": "events.jsonl", "lifecycle_txt": "lifecycle.txt", "start_facts_txt": "start-facts.txt",
                "cli_stderr": "cli.stderr", "stop_txt": "stop.txt"}[key]
        texts[name] = value
    for name, text in texts.items():
        if text is not None:
            (directory / name).write_text(text, encoding="utf-8")
    return directory


def check(directory: Path, *args: str) -> tuple[int, dict[str, list[str]]]:
    result = subprocess.run([sys.executable, str(CHECKER), str(directory), "--run-t0", str(T0), *args],
                            capture_output=True, text=True, timeout=60)
    out: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        out.setdefault(key, []).append(value)
    assert result.stderr == "", result.stderr
    return result.returncode, out


EXPECTED = ("--expected", "kill,die,start")


def test_a_complete_capture_holds_every_rule_on_the_guest_clock_alone(tmp_path):
    rc, out = check(capture(tmp_path), *EXPECTED)
    assert rc == 0, out
    assert out["coverage"] == ["complete"]
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        assert out[f"rule_{rule}"][0].startswith("held: "), (rule, out)
    assert "reason" not in out
    # The requested interval, on the guest clock only, and the provenance.
    assert out["requested_since_guest_epoch"] == [str(T0)] and out["requested_since_utc"] == ["2026-09-28T21:01:49Z"]
    assert out["requested_until_guest_epoch"] == [str(T1)]
    assert out["clock"][0].startswith("guest: ") and "no host instant" in out["clock"][0]
    assert "not a history query" in out["provenance"][0]
    assert out["expected_found"] == ["kill@2026-09-28T21:12:49Z,die@2026-09-28T21:12:49Z,start@2026-09-28T21:13:03Z"]
    # The heartbeat gap is reported, and decides nothing.
    assert out["max_gap_in_window_s"] == ["30.0"] and "no threshold" in out["max_gap_note"][0]


def test_a_fault_free_run_demands_no_fault_event(tmp_path):
    quiet = [e for e in events_of_a_run() if e["Actor"]["Attributes"]["name"] != CONTROLLER]
    rc, out = check(capture(tmp_path, quiet))
    assert rc == 0, out
    assert out["coverage"] == ["complete"] and out["expected"] == ["none"]
    assert out["rule_R7"][0].startswith("not-required: ")


def _only_broken(out: dict[str, list[str]], rule: str) -> None:
    assert out["coverage"] == ["incomplete"], out
    broken = [key for key, values in out.items() if key.startswith("rule_") and values[0].startswith("broken: ")]
    assert broken == [f"rule_{rule}"], out
    assert [r.split(" ", 1)[0] for r in out["reason"]] == [rule], out


@pytest.mark.parametrize("rule, change, says", [
    ("R1", {"lifecycle_txt": LIFECYCLE.replace(f"ready epoch={T0} ", f"ready epoch={T0 + 7} ")},
     f"the recorder was ready at {T0 + 7}"),
    ("R1", {"lifecycle_txt": "".join(line + "\n" for line in LIFECYCLE.splitlines() if not line.startswith("ready "))},
     "the recorder's start, CLI start and readiness are not each recorded once: ready x0"),
    ("R2", {"stop_txt": STOP.replace("MainPID=321", "MainPID=977").replace("=4200000", "=9100000")},
     "the guest boot or the docker daemon changed during the capture (MainPID 321 -> 977"),
    ("R2", {"stop_txt": STOP.replace("boot_id=488582b6", "boot_id=0000aaaa")},
     "the guest boot or the docker daemon changed during the capture (boot_id 488582b6"),
    ("R2", {"start_facts_txt": START_FACTS.replace("MainPID=321", "MainPID=0"),
            "stop_txt": STOP.replace("MainPID=321", "MainPID=0")},
     "the guest boot or the docker daemon changed during the capture (MainPID 0 at the start: no daemon"),
    ("R3", {"lifecycle_txt": LIFECYCLE.replace(f"cli-exit epoch={T1 + 3} rc=143 stop_requested=yes",
                                               f"cli-exit epoch={T0 + 900} rc=0 stop_requested=no")},
     f"the events CLI ended by itself (epoch {T0 + 900}, exit 0) before any stop was requested"),
    ("R3", {"stop_txt": STOP.replace("unit_state_before_stop=active", "unit_state_before_stop=failed")},
     "the recorder unit was 'failed', not active, when the stop was requested"),
    ("R3", {"lifecycle_txt": "".join(line + "\n" for line in LIFECYCLE.splitlines() if not line.startswith("cli-exit"))},
     "the recorder wrote 0 end(s) of its CLI, not one"),
    ("R3", {"lifecycle_txt": LIFECYCLE.replace(f"cli-exit epoch={T1 + 3}", f"cli-exit epoch={T1 - 9}")},
     f"the CLI's end ({T1 - 9}) precedes the stop request ({T1}) by more than the guest clock's step band of 3 s"),
    ("R4", {"cli_stderr": "WARNING: the events stream skipped a message\n"},
     "the events CLI wrote to stderr: 'WARNING: the events stream skipped a message'"),
    ("R6", {"events_jsonl": "".join(json.dumps(e) + "\n" for e in events_of_a_run()) + '{"status":"kill","id":\n'},
     "1 line(s) of the capture are not a JSON object with an integer timeNano"),
    ("R7", {"events_jsonl": "".join(json.dumps(e) + "\n" for e in events_of_a_run() if e["Action"] != "kill")},
     "the expected event(s) kill (signal 9) of egw-controller-1 are not captured"),
])
def test_one_thing_broken_is_the_rule_it_belongs_to_and_never_complete(tmp_path, rule, change, says):
    rc, out = check(capture(tmp_path, **change), *EXPECTED)
    assert rc == 1, out
    _only_broken(out, rule)
    assert out[f"rule_{rule}"][0].startswith("broken: " + says), out[f"rule_{rule}"]


def test_the_kill_must_be_the_faults_sigkill_and_every_fault_event_within_the_window(tmp_path):
    # A kill with another signal is not the fault; a start before RUN_T0 is
    # not of this run.
    events = [e for e in events_of_a_run() if e["Action"] not in ("kill", "start")]
    events += [event("kill", FAULT, CONTROLLER, signal="15"), event("start", T0 - 30, CONTROLLER)]
    rc, out = check(capture(tmp_path, sorted(events, key=lambda e: e["timeNano"])), *EXPECTED)
    assert rc == 1
    _only_broken(out, "R7")
    assert out["rule_R7"][0] == (f"broken: the expected event(s) kill (signal 9), start of {CONTROLLER} are not captured "
                                 f"within [{T0}, {T1}]")


def test_no_event_past_the_second_of_the_stop_request_is_no_closing_witness(tmp_path):
    # The last event is stamped IN the second of the request: that is not
    # after it, so the stream is not shown live to the window's end.
    events = [e for e in events_of_a_run() if e["time"] < T1] + [event("exec_die", T1, fraction_ns=900_000_000)]
    rc, out = check(capture(tmp_path, events), *EXPECTED)
    assert rc == 1
    _only_broken(out, "R5")
    # One nanosecond into the next second is.
    events[-1] = event("exec_die", T1 + 1)
    rc, out = check(capture(tmp_path / "next", events), *EXPECTED)
    assert rc == 0, out


def test_an_empty_capture_is_broken_never_complete(tmp_path):
    rc, out = check(capture(tmp_path, events_jsonl=""), *EXPECTED)
    assert rc == 1
    assert out["rule_R6"] == ["broken: the capture holds no event at all"]
    assert out["rule_R5"][0].startswith("broken: ") and out["rule_R7"][0].startswith("broken: ")


def test_a_long_heartbeat_gap_is_reported_and_decides_nothing(tmp_path):
    rc, out = check(capture(tmp_path, events_of_a_run(gap=(T0 + 700, T0 + 1300))), *EXPECTED)
    assert rc == 0, out
    assert float(out["max_gap_in_window_s"][0]) > 600


@pytest.mark.parametrize("change, rule, says", [
    ({"lifecycle_txt": None}, "R1", "the lifecycle record could not be read (lifecycle.txt: FileNotFoundError"),
    ({"start_facts_txt": None}, "R2", "the boot and daemon facts could not be read (start-facts.txt)"),
    ({"start_facts_txt": "boot_id=488582b6-eae8-477b-9a6d-8f5e04947238\n"}, "R2",
     "the boot and daemon facts are not all recorded: MainPID (start), ExecMainStartTimestampMonotonic (start)"),
    ({"stop_txt": "unit_state_before_stop=active\n"}, "R3",
     "the stop record does not say when the stop was requested or the unit's state then"),
    ({"cli_stderr": None}, "R4", "the CLI's stderr could not be read (cli.stderr: FileNotFoundError"),
    ({"events_jsonl": None}, "R6", "the capture could not be read (events.jsonl: FileNotFoundError"),
])
def test_what_cannot_be_read_is_unknown_never_complete(tmp_path, change, rule, says):
    rc, out = check(capture(tmp_path, **change), *EXPECTED)
    assert rc == 2, out
    assert out["coverage"] == ["unknown"]
    assert out[f"rule_{rule}"][0].startswith("unknown: " + says), out[f"rule_{rule}"]
    assert all(not v[0].startswith("broken: ") for k, v in out.items() if k.startswith("rule_")), out
    assert any(r.startswith(f"{rule} unknown: ") for r in out["reason"])


def test_a_broken_rule_outweighs_one_that_cannot_be_judged(tmp_path):
    rc, out = check(capture(tmp_path, cli_stderr=None,
                            lifecycle_txt=LIFECYCLE.replace("rc=143 stop_requested=yes", "rc=0 stop_requested=no")),
                    *EXPECTED)
    assert rc == 1
    assert out["coverage"] == ["incomplete"]
    assert out["rule_R4"][0].startswith("unknown: ") and out["rule_R3"][0].startswith("broken: ")


def test_a_file_that_cannot_be_read_at_all_and_a_bad_invocation_are_unknown(tmp_path):
    directory = capture(tmp_path, events_jsonl=None)
    (directory / "events.jsonl").mkdir()
    rc, out = check(directory, *EXPECTED)
    assert rc == 2 and out["coverage"] == ["unknown"]
    assert out["rule_R6"][0].startswith("unknown: the capture could not be read (events.jsonl: IsADirectoryError")
    for args in ([str(directory)], [str(directory), "--run-t0", "soon"], [str(directory), "--run-t0", str(T0), "--bogus"],
                 [str(directory), "--run-t0", str(T0), "--expected", "kill;die"]):
        result = subprocess.run([sys.executable, str(CHECKER), *args], capture_output=True, text=True, timeout=60)
        assert result.returncode == 2, args
        assert result.stdout.startswith("coverage=unknown\nreason="), (args, result.stdout)
