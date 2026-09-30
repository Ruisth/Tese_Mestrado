"""Cases for tools/session/proof_events_recorder.sh, the guest's continuous
Docker events recorder of a proof run, and for the ash-compatibility of the
guest commands that start, stop and clean it up.

They run the recorder under the host's POSIX shell (and under the image's own
busybox when EGW_TEST_BUSYBOX_DIR points at the wrappers of
tools/test/make-busybox-wrappers.sh, as test_probe_recorder.py does) with a
fake 'docker' on PATH whose 'events' follows until it is signalled, ends by
itself, or fails at once, and a fake 'date' that can take its time. The
recorder is a process group of its own here, and 'systemctl stop' is that
group signalled with TERM, as systemd ends a unit's control group. Nothing
here touches a real daemon, a container or the guest.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the recorder is a POSIX shell script for the guest", allow_module_level=True)
if shutil.which("sh") is None:
    pytest.skip("sh is not installed", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION = REPO_ROOT / "tools" / "session"
RECORDER = SESSION / "proof_events_recorder.sh"

FAKE_DOCKER = """#!/bin/sh
# fake docker: 'events' as FAKE_EVENTS_MODE says - follow (a line now, then
# one every 0.2 s until it is signalled), exit-first (two lines, then the
# daemon closes the stream: exit 0), fail-start (the daemon is not there:
# stderr and exit 1). Every call is recorded in FAKE_DOCKER_CALLS.
echo "$$ $*" >> "$FAKE_DOCKER_CALLS"
[ "${1:-}" = events ] || exit 1
case "${FAKE_EVENTS_MODE:-follow}" in
    fail-start)
        echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock." >&2
        exit 1 ;;
    exit-first)
        echo '{"Action":"exec_die","timeNano":1790629309000000000}'
        echo '{"Action":"exec_die","timeNano":1790629310000000000}'
        exit 0 ;;
esac
n=0
while :; do
    echo "{\\"Action\\":\\"exec_die\\",\\"n\\":$n,\\"timeNano\\":1790629309000000000}"
    n=$((n + 1))
    sleep 0.2
done
"""

FAKE_DATE = """#!/bin/sh
# fake date: a fixed epoch; the FIRST call takes FAKE_DATE_FIRST_DELAY_S
# seconds (a guest under load), leaving FAKE_DATE_MARK behind when it starts.
if [ -n "${FAKE_DATE_FIRST_DELAY_S:-}" ] && [ ! -e "$FAKE_DATE_MARK" ]; then
    : > "$FAKE_DATE_MARK"
    sleep "$FAKE_DATE_FIRST_DELAY_S"
fi
echo 1790629309
"""


def _shell() -> list[str]:
    busybox = os.environ.get("EGW_TEST_BUSYBOX_DIR")
    return [str(Path(busybox) / "sh")] if busybox else ["sh"]


def _bench(tmp_path: Path, **env: str) -> tuple[Path, dict]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in (("docker", FAKE_DOCKER), ("date", FAKE_DATE)):
        (bin_dir / name).write_text(text, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    capture = tmp_path / "egw-events-r01"
    capture.mkdir()
    for name in ("lifecycle.txt", "events.jsonl", "cli.stderr"):
        (capture / name).write_text("", encoding="utf-8")
    environment = dict(os.environ)
    busybox = os.environ.get("EGW_TEST_BUSYBOX_DIR")
    environment["PATH"] = f"{bin_dir}{os.pathsep}{busybox}" if busybox else f"{bin_dir}{os.pathsep}{environment['PATH']}"
    environment["FAKE_DOCKER_CALLS"] = str(tmp_path / "docker.calls")
    environment["FAKE_DATE_MARK"] = str(tmp_path / "date.mark")
    environment.update(env)
    return capture, environment


def _start(capture: Path, env: dict) -> subprocess.Popen:
    return subprocess.Popen([*_shell(), str(RECORDER), str(capture), "1790629189"], env=env,
                            stdin=subprocess.DEVNULL, start_new_session=True)


def _lifecycle(capture: Path) -> list[str]:
    return (capture / "lifecycle.txt").read_text(encoding="utf-8").splitlines()


def _wait(predicate, limit_s: float = 30.0) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit_s:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("the condition did not come about in time")


def _alive(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] not in ("Z", "X")
    except OSError:
        return False


def _cli_pid(capture: Path) -> int:
    line = next(line for line in _lifecycle(capture) if line.startswith("cli-start "))
    return int(re.search(r"cli_pid=(\d+)", line).group(1))


@pytest.mark.parametrize("signalled", ["the unit's group", "the recorder alone"])
def test_a_stop_ends_the_cli_and_is_recorded_as_the_stop(tmp_path, signalled):
    capture, env = _bench(tmp_path)
    proc = _start(capture, env)
    try:
        _wait(lambda: (capture / "events.jsonl").stat().st_size > 0 and len(_lifecycle(capture)) >= 2)
        cli = _cli_pid(capture)
        if signalled == "the unit's group":
            os.killpg(proc.pid, signal.SIGTERM)     # 'systemctl stop': the whole control group
        else:
            proc.send_signal(signal.SIGTERM)       # the recorder alone: its trap passes TERM on
        assert proc.wait(timeout=30) == 0
    finally:
        _kill_group(proc)
    life = _lifecycle(capture)
    assert [line.split()[0] for line in life] == ["start", "cli-start", "cli-exit"], life
    assert re.fullmatch(r"start epoch=\d+ pid=\d+ since=1790629189", life[0])
    assert re.fullmatch(r"cli-exit epoch=\d+ rc=\d+ stop_requested=yes", life[2]), life
    assert not _alive(cli), "the CLI was ended with the recorder, never left behind"
    lines = (capture / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines and all(line.startswith('{"Action":"exec_die"') for line in lines)
    calls = (tmp_path / "docker.calls").read_text(encoding="utf-8")
    assert "events --since 1790629189 --filter type=container --format {{json .}}" in calls
    assert (capture / "cli.stderr").read_text(encoding="utf-8") == ""


def test_a_cli_that_ends_by_itself_with_status_0_is_recorded_as_no_stop(tmp_path):
    # The daemon closed the stream: the CLI answers 0, and the recorder says
    # it ended without a stop - the break the checker never reads as coverage.
    capture, env = _bench(tmp_path, FAKE_EVENTS_MODE="exit-first")
    proc = _start(capture, env)
    try:
        assert proc.wait(timeout=30) == 0
    finally:
        _kill_group(proc)
    life = _lifecycle(capture)
    assert [line.split()[0] for line in life] == ["start", "cli-start", "cli-exit"], life
    assert re.fullmatch(r"cli-exit epoch=\d+ rc=0 stop_requested=no", life[2]), life
    assert len((capture / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_a_cli_that_fails_at_start_is_recorded_with_its_status_and_its_reason(tmp_path):
    capture, env = _bench(tmp_path, FAKE_EVENTS_MODE="fail-start")
    proc = _start(capture, env)
    try:
        assert proc.wait(timeout=30) == 1
    finally:
        _kill_group(proc)
    life = _lifecycle(capture)
    assert re.fullmatch(r"cli-exit epoch=\d+ rc=1 stop_requested=no", life[-1]), life
    assert "Cannot connect to the Docker daemon" in (capture / "cli.stderr").read_text(encoding="utf-8")
    assert (capture / "events.jsonl").read_text(encoding="utf-8") == ""


def test_a_stop_before_the_cli_was_started_starts_none_and_leaves_none_behind(tmp_path):
    # The stop arrives while the recorder is still writing its start line
    # (its clock takes its time): no pid to pass it to yet. No CLI is
    # started after it, and the record says so.
    capture, env = _bench(tmp_path, FAKE_DATE_FIRST_DELAY_S="2")
    proc = _start(capture, env)
    try:
        _wait(lambda: (tmp_path / "date.mark").exists())
        time.sleep(0.3)
        proc.send_signal(signal.SIGTERM)           # the recorder itself, not its clock
        assert proc.wait(timeout=30) == 0
    finally:
        _kill_group(proc)
    life = _lifecycle(capture)
    assert [line.split()[0] for line in life] == ["start", "cli-exit"], life
    assert life[1] == "cli-exit epoch=1790629309 rc=none stop_requested=yes cli_started=no"
    assert not (tmp_path / "docker.calls").exists(), "no CLI was started after the stop"


def test_a_recorder_killed_outright_leaves_no_end_of_its_cli(tmp_path):
    # SIGKILL runs no trap: the lifecycle then holds no 'cli-exit', which the
    # checker reads as an end never recorded (R3 broken), never as a stop.
    capture, env = _bench(tmp_path)
    proc = _start(capture, env)
    try:
        _wait(lambda: len(_lifecycle(capture)) >= 2)
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=30)
    finally:
        _kill_group(proc)
    assert [line.split()[0] for line in _lifecycle(capture)] == ["start", "cli-start"]


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


# --------------------------------------------------------------------------
# The guest commands around it parse under the guest's shell
# --------------------------------------------------------------------------


def _guest_scripts() -> dict[str, str]:
    """The guest commands of the start step and the cleanup, rendered by the
    functions of events_capture.sh as proof.sh and the host command render
    them (the file sourced, the function called), and of the stop, as
    proof_fetch_sut_log.sh writes its parameters before its here-document."""
    env = {**os.environ, "RECORDER": str(RECORDER), "RECORDER_SHA": "0" * 64, "RID": "r01"}
    rendered = {}
    for name, function in (("start", "events_recorder_script"), ("cleanup", "events_cleanup_script")):
        rendered[name] = subprocess.run(["bash", "-c", f'. "{SESSION / "events_capture.sh"}" && {function}'],
                                        env=env, capture_output=True, text=True, check=True).stdout
    hook = (SESSION / "proof_fetch_sut_log.sh").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(hook) if line.endswith("$(cat << 'GUEST_STOP'"))
    end = next(i for i in range(start + 1, len(hook)) if hook[i] == "GUEST_STOP")
    rendered["stop"] = ("D='/tmp/egw-events-r01'\nUNIT='egw-events-r01'\nMARKER_C='egw-mosquitto-1'\nMARKER_EXEC_S=45\n"
                        "WITNESS_S=45\n" + "\n".join(hook[start + 1:end]) + "\n")
    return rendered


@pytest.mark.parametrize("name", ["start", "cleanup", "stop"])
def test_the_guest_commands_parse_under_the_guests_shell(tmp_path, name):
    script = _guest_scripts()[name]
    if name == "start":
        # The recorder travels inside it byte for byte, between its own
        # here-document lines.
        assert "<< 'EGW_EVENTS_RECORDER'\n" + RECORDER.read_text(encoding="utf-8") + "EGW_EVENTS_RECORDER\n" in script
    path = tmp_path / f"{name}.sh"
    path.write_text(script, encoding="utf-8")
    result = subprocess.run([*_shell(), "-n", str(path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    # No bashism the image's ash lacks, in the commands or in the recorder.
    # 'head -c' and 'tail -c': the image's BusyBox 1.36.1 has neither option
    # (review of 2026-09-29), and 'sh -n' cannot check an applet's options.
    for construct in ("[[", "<<<", "$'", "PIPESTATUS", "pipefail", "EPOCHREALTIME", "%N", "local ", "head -1",
                      "head -c", "tail -c", "trap '' SIG", "SIGTERM"):
        assert construct not in script, (name, construct)


FAKE_SYSTEMCTL = """#!/bin/sh
# fake systemctl of the cleanup: the unit's state is the content of
# FAKE_UNIT_STATE, an empty one a state that cannot be read (nothing on
# stdout, exit 1); 'is-active' answers 0 for active only, 3 otherwise, as
# systemd does for a unit that no longer exists; 'stop' answers FAKE_STOP_RC
# and leaves FAKE_STATE_AFTER_STOP behind ('unchanged': a stop with no
# effect). Every call is recorded in FAKE_SYSTEMCTL_CALLS.
echo "$*" >> "$FAKE_SYSTEMCTL_CALLS"
case "$1" in
    is-active)
        state=$(cat "$FAKE_UNIT_STATE")
        if [ -z "$state" ]; then
            echo "Failed to connect to bus: Connection refused" >&2
            exit 1
        fi
        echo "$state"
        [ "$state" = active ] && exit 0
        exit 3 ;;
    stop)
        [ "$FAKE_STATE_AFTER_STOP" = unchanged ] || echo "$FAKE_STATE_AFTER_STOP" > "$FAKE_UNIT_STATE"
        exit "${FAKE_STOP_RC:-0}" ;;
esac
exit 1
"""


@pytest.mark.parametrize("before, after_stop, stop_rc, rc, after", [
    # definitively stopped: no stop is requested
    ("inactive", "-", 0, 0, None),
    ("failed", "-", 0, 0, None),
    # anything else is stopped and its state read again (review of PR #51, P1)
    ("active", "inactive", 0, 0, "inactive"),
    ("activating", "inactive", 0, 0, "inactive"),
    ("deactivating", "failed", 0, 0, "failed"),
    ("reloading", "inactive", 0, 0, "inactive"),
    ("", "inactive", 0, 0, "inactive"),
    # not shown stopped after the stop: non-zero
    ("active", "unchanged", 0, 1, "active"),
    ("activating", "activating", 0, 1, "activating"),
    ("active", "", 0, 1, "unknown"),
    # a stop that failed stays non-zero, as before
    ("active", "inactive", 1, 1, "inactive"),
])
def test_the_cleanup_stops_every_unit_not_shown_stopped_and_ends_0_only_once_it_is(tmp_path, before, after_stop,
                                                                                    stop_rc, rc, after):
    """The cleanup's guest command run under the guest's shell (the image's busybox with EGW_TEST_BUSYBOX_DIR): only
    'inactive' and 'failed' are a unit already stopped; any other state - one between, or none at all - is stopped
    and read again, and the step answers 0 only when it is then 'inactive' or 'failed'."""
    capture, env = _bench(tmp_path)
    bin_dir = tmp_path / "bin"
    for name, text in (("systemctl", FAKE_SYSTEMCTL), ("sudo", '#!/bin/sh\nexec "$@"\n')):
        (bin_dir / name).write_text(text, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    (capture / "lifecycle.txt").write_text("start epoch=1790629300 pid=4242\n", encoding="utf-8")
    state = tmp_path / "unit.state"
    state.write_text(before + "\n", encoding="utf-8")
    env.update(FAKE_UNIT_STATE=str(state), FAKE_STATE_AFTER_STOP=after_stop, FAKE_STOP_RC=str(stop_rc),
               FAKE_SYSTEMCTL_CALLS=str(tmp_path / "systemctl.calls"))
    script = _guest_scripts()["cleanup"]
    assert "D='/tmp/egw-events-r01'\n" in script
    path = tmp_path / "cleanup.sh"
    path.write_text(script.replace("D='/tmp/egw-events-r01'\n", f"D='{capture}'\n"), encoding="utf-8")
    result = subprocess.run([*_shell(), str(path)], env=env, capture_output=True, text=True, timeout=60)
    out = result.stdout.splitlines()
    assert result.returncode == rc, result.stdout + result.stderr
    assert f"unit_state_before_cleanup={before or 'unknown'}" in out, result.stdout
    calls = (tmp_path / "systemctl.calls").read_text(encoding="utf-8").splitlines()
    if after is None:
        assert "stop egw-events-r01" not in calls and not any(line.startswith("cleanup_stop_requested_guest_epoch=")
                                                              or line.startswith("unit_state_after_cleanup=")
                                                              for line in out), result.stdout
    else:
        assert "stop egw-events-r01" in calls and "cleanup_stop_requested_guest_epoch=1790629309" in out, result.stdout
        assert f"unit_state_after_cleanup={after}" in out, result.stdout
    # The recorder's lifecycle record is printed whatever the state.
    assert "start epoch=1790629300 pid=4242" in out and "events_lines=0" in out and "cli_stderr_bytes=0" in out
