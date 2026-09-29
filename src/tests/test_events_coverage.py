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
# The container the stop script issues its closing marker in: the
# broker's, which the proof never faults (R7 reads the controller's).
MARKER_C = BROKER
# The closing marker's nonce: the guest's /proc/sys/kernel/random/uuid, read
# by the stop script after it recorded the stop request.
NONCE = "3f1c2a9e-5b7d-4c21-9e0a-7d6b8f4a2c10"


def event(action: str, second: int, name: str = BROKER, fraction_ns: int = 0, **attributes: str) -> dict:
    """One event as 'docker events --format {{json .}}' prints it."""
    cid = ("0f" if name == CONTROLLER else "00") + "a" * 62
    return {"status": action, "id": cid, "from": f"stub/{name}:1", "Type": "container", "Action": action,
            "Actor": {"ID": cid, "Attributes": {"image": f"stub/{name}:1", "name": name, **attributes}},
            "scope": "local", "time": second, "timeNano": second * NS + fraction_ns}


def marker_events(nonce: str = NONCE, name: str = MARKER_C, second: int = T1 + 1) -> list[dict]:
    """The daemon's events of the closing marker, the no-op 'docker exec NAME
    sh -c ": egw-events-close NONCE"' the stop script issues after it
    recorded the stop request: exec_create and exec_start carry the command
    in their Action (as r03's healthcheck execs carry theirs), exec_die does
    not."""
    command = f"sh -c : egw-events-close {nonce}"
    return [event(f"exec_create: {command}", second, name, 100, execID="e" * 64),
            event(f"exec_start: {command}", second, name, 200, execID="e" * 64),
            event("exec_die", second, name, 300, execID="e" * 64, exitCode="0")]


def events_of_a_run(heartbeat_s: int = 30, gap: tuple[int, int] | None = None, marker: bool = True) -> list[dict]:
    """The replay from before T0, the healthchecks' exec events every
    HEARTBEAT_S seconds through the window and past T1, the fault's three
    events and (MARKER) the closing marker's exec events."""
    out = []
    for second in range(T0 - 120, T1 + 5, heartbeat_s):
        if gap and gap[0] < second < gap[1]:
            continue
        out.append(event("exec_die: /bin/sh -c mosquitto_sub -t $SYS/# -C 1", second))
    out += [event("kill", FAULT, CONTROLLER, signal="9"), event("die", FAULT, CONTROLLER, 1000, exitCode="137"),
            event("start", FAULT + 14, CONTROLLER)]
    out.append(event("exec_die: /bin/sh -c mosquitto_sub -t $SYS/# -C 1", T1 + 2, fraction_ns=5))
    if marker:
        out += marker_events()
    return sorted(out, key=lambda e: e["timeNano"])


LIFECYCLE = (f"start epoch={T0 - 2} pid=4242 since={T0 - 122}\n"
             f"cli-start epoch={T0 - 2} cli_pid=4245\n"
             f"ready epoch={T0} events_bytes=880 unit=active\n"
             f"cli-exit epoch={T1 + 3} rc=143 stop_requested=yes\n")
START_FACTS = "boot_id=488582b6-eae8-477b-9a6d-8f5e04947238\nMainPID=321\nExecMainStartTimestampMonotonic=4200000\n"
STOP = (f"stop_requested_guest_epoch={T1}\nunit_state_before_stop=active\n"
        "boot_id=488582b6-eae8-477b-9a6d-8f5e04947238\nMainPID=321\nExecMainStartTimestampMonotonic=4200000\n"
        f"closing_marker={NONCE}\nclosing_marker_container={MARKER_C}\nclosing_marker_exec_rc=0\n"
        "closing_marker_seen=yes\nunit_state_after_stop=inactive\n")
# The stop record of a stop that issued no closing marker.
STOP_WITHOUT_MARKER = "".join(line + "\n" for line in STOP.splitlines() if not line.startswith("closing_marker"))


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
    # No fault: the controller's kill, die and start are absent (the
    # closing marker, the broker's exec, stays).
    quiet = [e for e in events_of_a_run() if e["Action"] not in ("kill", "die", "start")]
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
     f"the events CLI ended by itself (epoch {T0 + 900}, exit 0), without a stop passed to it"),
    ("R3", {"stop_txt": STOP.replace("unit_state_before_stop=active", "unit_state_before_stop=failed")},
     "the recorder unit was 'failed', not active, when the stop was requested"),
    ("R3", {"lifecycle_txt": "".join(line + "\n" for line in LIFECYCLE.splitlines() if not line.startswith("cli-exit"))},
     "the recorder wrote 0 end(s) of its CLI, not one (none: its end by the stop is not recorded)"),
    ("R3", {"lifecycle_txt": LIFECYCLE + f"cli-exit epoch={T1 + 4} rc=143 stop_requested=yes\n"},
     "the recorder wrote 2 end(s) of its CLI, not one"),
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


def test_the_provenance_line_claims_no_continuity_the_rules_do_not_show(tmp_path):
    # Review of 2026-09-29: the record of an incomplete capture must not say
    # it was followed continuously; the method is stated, the outcome is the
    # verdict's.
    broken = LIFECYCLE.replace(f"cli-exit epoch={T1 + 3} rc=143 stop_requested=yes",
                               f"cli-exit epoch={T0 + 900} rc=0 stop_requested=no")
    rc, out = check(capture(tmp_path, lifecycle_txt=broken), *EXPECTED)
    assert rc == 1 and out["coverage"] == ["incomplete"]
    assert "continuously" not in out["provenance"][0]
    assert "whether it was followed throughout is the verdict and the rules below" in out["provenance"][0]
    assert out["rule_R3"][0].startswith("broken: ")


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


# --- R5, the closing marker (PM bounded review of PR #50, F1) -------------------
# The stop request is recorded at T1; a guest clock stepped back makes that
# request read EARLIER than events already captured (an event stored at 100,
# the request stamped 98). A later stamp is therefore no observation made
# after the request: only the closing marker, caused by the fetch after it
# recorded the request and identified by its nonce, is.


def test_an_event_stamped_after_the_stop_request_is_no_closing_marker_and_never_complete(tmp_path):
    # The capture holds an event stamped T1 + 2 (and none of a marker); the
    # stop record carries no marker: nothing shows an observation made after
    # the request, whatever the stamps say.
    rc, out = check(capture(tmp_path, events_of_a_run(marker=False), stop_txt=STOP_WITHOUT_MARKER), *EXPECTED)
    assert out["coverage"] != ["complete"], out
    assert rc == 2 and out["coverage"] == ["unknown"], out
    assert out["latest_event_guest_epoch"] == [str(T1 + 2)]
    assert out["rule_R5"][0].startswith("unknown: the stop record carries no closing marker"), out["rule_R5"]
    assert all(not v[0].startswith("broken: ") for k, v in out.items() if k.startswith("rule_")), out


def test_a_closing_marker_issued_but_not_captured_is_broken_whatever_later_stamps_the_capture_holds(tmp_path):
    # The stop record says the marker was issued (and that the guest saw it:
    # its own claim, never read); the capture holds later-stamped events but
    # no event of the marker.
    rc, out = check(capture(tmp_path, events_of_a_run(marker=False)), *EXPECTED)
    assert rc == 1, out
    _only_broken(out, "R5")
    assert out["rule_R5"][0].startswith(f"broken: the closing marker {NONCE} was issued in {MARKER_C} after the stop "
                                        "request"), out["rule_R5"]
    assert out["closing_marker_event_guest_epoch"] == ["null"]


def test_the_closing_marker_captured_holds_r5_and_the_capture_is_complete(tmp_path):
    rc, out = check(capture(tmp_path), *EXPECTED)
    assert rc == 0, out
    assert out["coverage"] == ["complete"]
    r5 = out["rule_R5"][0]
    assert r5.startswith(f"held: the closing marker {NONCE}") and MARKER_C in r5, r5
    assert "the marker was caused after the stop request was recorded" in r5
    assert "caused after the window's end" in r5
    assert out["closing_marker"] == [NONCE] and out["closing_marker_container"] == [MARKER_C]
    # The marker's container is the one the stop record names, not R7's.
    assert out["container"] == [CONTROLLER]
    assert out["closing_marker_exec_rc"] == ["0"]
    assert out["closing_marker_event_guest_epoch"] == [str(T1 + 1)]
    assert out["latest_event_guest_epoch"] == [str(T1 + 2)]


def test_the_closing_marker_holds_r5_whatever_its_stamp_and_no_later_stamp_is_needed(tmp_path):
    # The guest clock stepped back between the request and the marker's exec:
    # the marker's events read BEFORE T1 and nothing is stamped after it. The
    # marker is identified by its nonce, never by a stamp.
    events = [e for e in events_of_a_run(marker=False) if e["time"] < T1] + marker_events(second=T1 - 2)
    rc, out = check(capture(tmp_path, sorted(events, key=lambda e: e["timeNano"])), *EXPECTED)
    assert rc == 0, out
    assert out["coverage"] == ["complete"] and out["rule_R5"][0].startswith("held: ")
    assert out["closing_marker_event_guest_epoch"] == [str(T1 - 2)]


def test_a_closing_marker_whose_exec_failed_is_broken(tmp_path):
    # A failed exec caused nothing after the request, whatever the capture
    # holds (here: the marker's events too, which do not count).
    for n, events in enumerate((events_of_a_run(marker=False), events_of_a_run())):
        rc, out = check(capture(tmp_path / str(n), events,
                                stop_txt=STOP.replace("closing_marker_exec_rc=0", "closing_marker_exec_rc=1")),
                        *EXPECTED)
        assert rc == 1, out
        _only_broken(out, "R5")
        assert out["rule_R5"][0].startswith(f"broken: the closing marker's exec in {MARKER_C} exited 1"), out["rule_R5"]
        assert out["closing_marker_exec_rc"] == ["1"]


@pytest.mark.parametrize("marker", [
    marker_events(name=CONTROLLER),                     # the nonce, in ANOTHER container
    marker_events(nonce=NONCE[:-4]),                    # part of the nonce only
    marker_events(nonce=NONCE[4:]),
    marker_events(nonce="0e8b1a52-6c3d-4f10-8a7e-2b9c5d1f6e04"),   # another marker's nonce
    marker_events()[2:],                                # the exec_die alone, which carries no command
], ids=["another-container", "nonce-truncated-end", "nonce-truncated-start", "another-nonce", "exec-die-only"])
def test_an_event_that_is_not_the_markers_own_is_no_closing_marker(tmp_path, marker):
    events = sorted(events_of_a_run(marker=False) + marker, key=lambda e: e["timeNano"])
    rc, out = check(capture(tmp_path, events), *EXPECTED)
    assert rc == 1, out
    _only_broken(out, "R5")
    assert out["closing_marker_event_guest_epoch"] == ["null"]


@pytest.mark.parametrize("stop, says", [
    (STOP_WITHOUT_MARKER, "the stop record carries no closing marker"),
    (STOP.replace(f"closing_marker={NONCE}", "closing_marker=none"), "the stop record carries no closing marker"),
    (STOP.replace(f"closing_marker={NONCE}", "closing_marker="), "the stop record carries no closing marker"),
    (STOP.replace(f"closing_marker={NONCE}", f"closing_marker={NONCE.upper()}"),
     f"the stop record's closing marker '{NONCE.upper()}' is not a well-formed nonce"),
    (STOP.replace(f"closing_marker={NONCE}", f"closing_marker={NONCE[:-1]}"),
     f"the stop record's closing marker '{NONCE[:-1]}' is not a well-formed nonce"),
    (STOP.replace(f"closing_marker_container={MARKER_C}\n", ""),
     "the stop record does not name the container the closing marker was issued in"),
    (STOP.replace("closing_marker_exec_rc=0\n", ""), "the stop record does not say how the closing marker's exec ended"),
    (STOP.replace("closing_marker_exec_rc=0", "closing_marker_exec_rc=unknown"),
     "the stop record does not say how the closing marker's exec ended"),
    # The exec did not end within the stop script's bound and was killed
    # (a daemon that never answered it): whatever the capture holds - here
    # the marker's events too - its outcome is unknown.
    (STOP.replace("closing_marker_exec_rc=0", "closing_marker_exec_rc=timeout"),
     f"the closing marker's exec in {MARKER_C} did not end within the stop script's bound and was killed"),
], ids=["absent", "none", "empty", "upper-case", "short", "no-container", "no-exec-rc", "exec-rc-not-a-number",
        "exec-timed-out"])
def test_a_closing_marker_the_stop_record_does_not_state_is_unknown_never_complete(tmp_path, stop, says):
    rc, out = check(capture(tmp_path, stop_txt=stop), *EXPECTED)
    assert rc == 2, out
    assert out["coverage"] == ["unknown"]
    assert out["rule_R5"][0].startswith("unknown: " + says), out["rule_R5"]
    assert all(not v[0].startswith("broken: ") for k, v in out.items() if k.startswith("rule_")), out


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
