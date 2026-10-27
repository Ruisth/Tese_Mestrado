"""Positive and negative cases for the verdict of deployment/scripts/probe-acl.sh.

The script under test is the repository file itself, run unmodified under dash
and under bash. Only its environment is replaced: a stub ``docker`` (and a
``sleep`` that only shortens the one-second poll) are put first on PATH. The
stub plays the broker container: it keeps a broker log, models the ACL, and can
be told per probe client how to misbehave.

What these cases show is the DECISION LOGIC of the script for a given set of
observations. They say nothing about Docker, Compose, Mosquitto or the guest:
the texts printed by the stub were read in sources and never observed here.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("probe-acl.sh needs a POSIX host (sh, /proc or date, chmod)", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "src" / "deployment" / "scripts" / "probe-acl.sh"
if not SCRIPT.is_file():
    pytest.skip(f"{SCRIPT} is not in this tree", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)
REAL_SLEEP = shutil.which("sleep")
if REAL_SLEEP is None:
    pytest.skip("sleep is not installed", allow_module_level=True)

TAG = "t1"
SHELLS = [
    pytest.param("dash", marks=pytest.mark.skipif(shutil.which("dash") is None, reason="dash is not installed")),
    pytest.param("bash"),
]

# The stub. Its state directory is $STUB_STATE; behaviour/<name> holds one keyword.
STUB_DOCKER = r"""#!/bin/sh
S=$STUB_STATE
B=$S/behaviour
LOG=$S/broker.log
SLEEP=@SLEEP@
printf '%s\n' "$*" >>"$S/calls.log"
beh() { if [ -f "$B/$1" ]; then cat "$B/$1"; else echo "$2"; fi; }
logline() { printf '%s 1758186100: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)" "$1" >>"$LOG"; }
emit() {  # emit TIMESTAMPS TAIL
    if [ "$1" = 1 ]; then sed 's/^/mosquitto-1  | /' "$LOG" | tail -n "$2"
    else sed 's/^[^ ]* //; s/^/mosquitto-1  | /' "$LOG" | tail -n "$2"; fi
}
wait_for() {  # wait_for FILE (non-empty), at most 20 s
    n=0
    while [ ! -s "$1" ] && [ "$n" -lt 400 ]; do "$SLEEP" 0.05; n=$((n + 1)); done
}
[ "$1" = compose ] || { echo "stub docker: unexpected: $*" >&2; exit 64; }
shift
while [ "${1:-}" = --env-file ]; do shift 2; done
cmd=${1:-}; shift
case "$cmd" in
logs)
    ts=0; tail=100000
    while [ $# -gt 0 ]; do
        case "$1" in --timestamps) ts=1;; --tail) tail=$2; shift;; esac
        shift
    done
    if [ "$ts" = 0 ]; then emit 0 "$tail"; exit 0; fi
    if [ "$tail" = 1 ]; then
        case "$(beh logs-anchor ok)" in
            ok) emit 1 1; exit 0;;
            rc1) echo "stub: cannot connect to the Docker daemon" >&2; exit 1;;
            empty) exit 0;;
        esac
        exit 64
    fi
    case "$(beh logs-final ok)" in
        ok) emit 1 "$tail"; exit 0;;
        rc1-full) emit 1 "$tail"; echo "stub: error from daemon in stream" >&2; exit 1;;
        rc1-truncated) emit 1 "$tail" | head -n 7; echo "stub: error from daemon in stream" >&2; exit 1;;
        empty) exit 0;;
        anchor-gone) emit 1 "$tail" | tail -n +4; exit 0;;
        unwritable) chmod a-w "$ACL_PROBE_OUT"; emit 1 "$tail"; exit 0;;
    esac
    exit 64;;
exec)
    while :; do
        case "${1:-}" in -T) shift;; -e) shift 2;; *) break;; esac
    done
    [ "${1:-}" = mosquitto ] || { echo "stub docker: unexpected service: $*" >&2; exit 64; }
    shift
    if [ "$1" = sh ]; then
        script=$3; id=$4; user=$5; shift 5
        case "$script" in *mosquitto_sub*) kind=sub;; *mosquitto_pub*) kind=pub;; *) exit 64;; esac
    else
        kind=anon; id=
        while [ $# -gt 0 ]; do [ "$1" = -i ] && id=$2; shift; done
    fi
    label=${id#egw-acl-$STUB_TAG-}
    case "$kind" in
    sub)
        b=$(beh "$label" ok)
        if [ "$b" = exec-fail ]; then echo "Error response from daemon: container is not running" >&2; exit 1; fi
        logline "Received SUBSCRIBE from $id"
        logline "$id 1 c2dt/#"
        [ "$b" = early ] && exit 27
        wait_for "$S/anon.done"
        [ "$b" = resubscribed ] && logline "$id 1 c2dt/#"
        "$SLEEP" 1.1
        [ "$b" = noise ] && echo 'OCI runtime exec failed: exec failed: unable to start container process'
        [ -f "$S/deliver.$label" ] && cat "$S/deliver.$label"
        if [ "$b" = lost ]; then echo "Error: The connection was lost." >&2; exit 14; fi
        exit 27;;
    pub)
        proto=$1; topic=$2; payload=$3
        b=$(beh "$label" ok)
        if [ "$b" = exec-fail ]; then echo "Error response from daemon: container is not running"; exit 1; fi
        [ "$b" = slow ] && "$SLEEP" 2.2
        [ "$b" = wait-sim-sub-end ] && wait_for "$ACL_PROBE_OUT/sim-sub.end"
        acl=$(beh acl enforced)
        echo "Client $id sending CONNECT"
        case "$user" in
        egw-simulator)
            echo "$topic $payload" >>"$S/deliver.ctl-sub"
            [ "$acl" = leak-read ] && echo "$topic $payload" >>"$S/deliver.sim-sub";;
        egw-controller)
            [ "$acl" = "leak-write-$proto" ] && echo "$topic $payload" >>"$S/deliver.ctl-sub"
            [ "$proto" = mqttv5 ] && echo "Warning: Publish 1 failed: Not authorized.";;
        esac
        exit 0;;
    anon)
        rc=64
        refusal='Connection error: Connection Refused: not authorised.'
        accepted="New client connected from 127.0.0.1:40000 as $id (p2, c1, k60)."
        case "$(beh anon refused)" in
            refused) logline "Client $id disconnected, not authorised."; echo "$refusal" >&2; rc=5;;
            accepted-timeout) logline "$accepted"; echo "Timed out" >&2; rc=27;;
            accepted-rc0) logline "$accepted"; rc=0;;
            accepted-delivery) logline "$accepted"; echo 'c2dt/site/dev/telemetry {"v":1}'; rc=27;;
            accepted-log-only) logline "$accepted"; echo "$refusal" >&2; rc=5;;
            exec-err-stderr) echo "Error response from daemon: container is not running" >&2; rc=1;;
            exec-err-stdout) echo 'OCI runtime exec failed: exec failed: unable to start container process'; rc=126;;
            refused-with-stdout-noise) echo "$refusal" >&2; echo 'OCI runtime exec failed'; rc=5;;
            tls-error) echo "Error: A TLS error occurred." >&2; rc=8;;
            empty-stderr) rc=5;;
            rc5-other-text) echo "Connection error: Connection Refused: bad user name or password." >&2; rc=5;;
        esac
        : >"$S/anon.done"; echo done >"$S/anon.done"
        exit "$rc";;
    esac;;
esac
echo "stub docker: unexpected: $cmd $*" >&2
exit 64
"""

INITIAL_BROKER_LOG = (
    "2026-09-18T09:00:00.000000001Z 1758186000: mosquitto version 2.0.22 starting\n"
    "2026-09-18T09:00:00.000000002Z 1758186000: Opening ipv4 listen socket on port 8883.\n"
    "2026-09-18T09:00:00.000000003Z 1758186000: mosquitto version 2.0.22 running\n"
)
DOT_ENV = "MOSQUITTO_SIMULATOR_PASSWORD=sim-secret\nMOSQUITTO_CONTROLLER_PASSWORD=ctl-secret\n"


@dataclass
class Run:
    rc: int
    stdout: str
    stderr: str
    out: Path
    state: Path

    @property
    def calls(self) -> str:
        f = self.state / "calls.log"
        return f.read_text() if f.exists() else ""

    def describe(self) -> str:
        return f"exit={self.rc}\n--- stdout\n{self.stdout}--- stderr\n{self.stderr}--- docker calls\n{self.calls}"


def _executable(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_probe(shell, tmp_path, behaviours=None, args=(TAG,), env=None, dot_env=DOT_ENV, make_out=False) -> Run:
    bindir, state, deploy = tmp_path / "bin", tmp_path / "state", tmp_path / "deployment"
    out = tmp_path / "evidence" / "itest-acl"
    for d in (bindir, state / "behaviour", deploy, out.parent):
        d.mkdir(parents=True)
    _executable(bindir / "docker", STUB_DOCKER.replace("@SLEEP@", REAL_SLEEP))
    # The probe polls once a second for the SUBSCRIBE lines: only that wait is shortened.
    _executable(bindir / "sleep", f'#!/bin/sh\nexec "{REAL_SLEEP}" 0.1\n')
    (state / "broker.log").write_text(INITIAL_BROKER_LOG)
    for name, keyword in (behaviours or {}).items():
        (state / "behaviour" / name).write_text(keyword + "\n")
    if dot_env is not None:
        (deploy / ".env").write_text(dot_env)
    if make_out:
        out.mkdir()
    environ = {
        "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
        "LC_ALL": "C",
        "EGW_DEPLOY_DIR": str(deploy),
        "ACL_PROBE_OUT": str(out),
        "ACL_PROBE_WINDOW": "60",
        "ACL_PROBE_READY": "3",
        "STUB_STATE": str(state),
        "STUB_TAG": TAG,
    }
    environ.update(env or {})
    p = subprocess.run([shell, str(SCRIPT), *args], env=environ, cwd=tmp_path, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=120)
    return Run(p.returncode, p.stdout, p.stderr, out, state)


def assert_verdict(r: Run, code: int, verdict: str, decisive=()) -> None:
    lines = r.stdout.splitlines()
    assert r.rc == code, r.describe()
    assert lines and lines[-1] == f"verdict={verdict}", r.describe()
    assert [ln for ln in lines if ln.startswith("verdict=")] == [f"verdict={verdict}"], r.describe()
    for text in decisive:
        assert any(text in ln for ln in lines), f"no output line contains {text!r}\n{r.describe()}"
    assert (r.out / "verdict.txt").read_text() == r.stdout, r.describe()


# ---------------------------------------------------------------- positive

@pytest.mark.parametrize("shell", SHELLS)
def test_acl_enforced_anonymous_refused_complete_log_gives_pass_exit_0(shell, tmp_path):
    r = run_probe(shell, tmp_path)
    assert_verdict(r, 0, "PASS", [
        "authorised subscriber (egw-controller):   P1=1 P2=0 P3=0 P4=1 rc=27",
        "unauthorised subscriber (egw-simulator):  deliveries=0 stdout_bytes=0 rc=27",
        "liveness: covered=yes",
        "anonymous: refused rc=5 refusal_lines=1 deliveries=0 stdout_bytes=0 accepted_in_broker_log=0",
        "evidence: broker_log=complete checked: anchor_rc=0 collection_rc=0",
        "after_collection=ok",
    ])
    anon_calls = [c for c in r.calls.splitlines() if f"egw-acl-{TAG}-anon" in c]
    assert len(anon_calls) == 1 and " -u " not in anon_calls[0] and " -P " not in anon_calls[0], r.describe()
    assert not (r.out / "broker_tail.tmp").exists() and not (r.out / "write_check.tmp").exists()


# ---------------------------------------------------------------- negative

@dataclass
class Case:
    name: str
    behaviours: dict
    code: int
    verdict: str
    decisive: list
    env: dict = field(default_factory=dict)


LOG_RC1 = "evidence: broker_log=incomplete (docker compose logs returned 1)"
CASES = [
    # Anonymous connection: accepted -> FAIL; anything that is not an observed CONNACK 5 -> INCONCLUSIVE.
    Case("anonymous_session_accepted_and_alive_until_timeout_gives_FAIL_exit_1",
         {"anon": "accepted-timeout"}, 1, "FAIL", ["anonymous: accepted rc=27", "accepted_in_broker_log=1"]),
    Case("anonymous_session_accepted_with_rc_0_gives_FAIL_exit_1",
         {"anon": "accepted-rc0"}, 1, "FAIL", ["anonymous: accepted rc=0"]),
    Case("anonymous_client_received_a_message_gives_FAIL_exit_1",
         {"anon": "accepted-delivery"}, 1, "FAIL", ["anonymous: accepted rc=27 refusal_lines=0 deliveries=1"]),
    Case("anonymous_refusal_printed_but_broker_logged_an_accepted_session_gives_FAIL_exit_1",
         {"anon": "accepted-log-only"}, 1, "FAIL", ["anonymous: accepted rc=5 refusal_lines=1", "accepted_in_broker_log=1"]),
    Case("anonymous_exec_error_on_stderr_gives_INCONCLUSIVE_exit_3",
         {"anon": "exec-err-stderr"}, 3, "INCONCLUSIVE", ["anonymous: inconclusive rc=1 refusal_lines=0"]),
    Case("anonymous_exec_error_on_stdout_gives_INCONCLUSIVE_exit_3",
         {"anon": "exec-err-stdout"}, 3, "INCONCLUSIVE", ["anonymous: inconclusive rc=126 refusal_lines=0 deliveries=0 stdout_bytes=72"]),
    Case("anonymous_refusal_text_with_other_bytes_on_stdout_gives_INCONCLUSIVE_exit_3",
         {"anon": "refused-with-stdout-noise"}, 3, "INCONCLUSIVE", ["anonymous: inconclusive rc=5 refusal_lines=1 deliveries=0 stdout_bytes=24"]),
    Case("anonymous_tls_error_gives_INCONCLUSIVE_exit_3",
         {"anon": "tls-error"}, 3, "INCONCLUSIVE", ["anonymous: inconclusive rc=8 refusal_lines=0"]),
    Case("anonymous_rc_5_with_empty_stderr_gives_INCONCLUSIVE_exit_3",
         {"anon": "empty-stderr"}, 3, "INCONCLUSIVE", ["anonymous: inconclusive rc=5 refusal_lines=0"]),
    Case("anonymous_rc_5_with_another_refusal_text_gives_INCONCLUSIVE_exit_3",
         {"anon": "rc5-other-text"}, 3, "INCONCLUSIVE", ["anonymous: inconclusive rc=5 refusal_lines=0"]),
    # ACL.
    Case("message_delivered_to_the_write_only_user_gives_FAIL_exit_1",
         {"acl": "leak-read"}, 1, "FAIL", ["unauthorised subscriber (egw-simulator):  deliveries=2 "]),
    Case("publication_of_the_read_only_user_delivered_v311_gives_FAIL_exit_1",
         {"acl": "leak-write-mqttv311"}, 1, "FAIL", ["P1=1 P2=1 P3=0 P4=1"]),
    Case("publication_of_the_read_only_user_delivered_v5_gives_FAIL_exit_1",
         {"acl": "leak-write-mqttv5"}, 1, "FAIL", ["P1=1 P2=0 P3=1 P4=1"]),
    Case("bytes_that_are_not_a_delivery_on_the_unauthorised_subscriber_give_INCONCLUSIVE_exit_3",
         {"sim-sub": "noise"}, 3, "INCONCLUSIVE", ["unauthorised subscriber (egw-simulator):  deliveries=0 stdout_bytes=72 rc=27"]),
    # Positive control and liveness.
    Case("unauthorised_subscriber_ended_before_the_last_publication_gives_INCONCLUSIVE_exit_3",
         {"sim-sub": "early", "p4-sim-pub": "wait-sim-sub-end"}, 3, "INCONCLUSIVE",
         ["liveness: covered=no", "deliveries=0 stdout_bytes=0 rc=27"]),
    Case("last_publication_returned_too_close_to_the_end_of_the_window_gives_INCONCLUSIVE_exit_3",
         {"p4-sim-pub": "slow"}, 3, "INCONCLUSIVE", ["liveness: covered=no"], {"ACL_PROBE_WINDOW": "3"}),
    Case("unauthorised_subscriber_lost_its_connection_gives_INCONCLUSIVE_exit_3",
         {"sim-sub": "lost"}, 3, "INCONCLUSIVE", ["deliveries=0 stdout_bytes=0 rc=14"]),
    Case("unauthorised_subscriber_subscribed_twice_gives_INCONCLUSIVE_exit_3",
         {"sim-sub": "resubscribed"}, 3, "INCONCLUSIVE", ["whole run: ctl-sub=1 sim-sub=2"]),
    Case("authorised_subscriber_never_started_so_nothing_was_published_gives_INCONCLUSIVE_exit_3",
         {"ctl-sub": "exec-fail"}, 3, "INCONCLUSIVE", ["subscribe_lines_before_publish: ctl-sub=0 sim-sub=1", "P1=0 P2=0 P3=0 P4=0 rc=1"]),
    Case("first_publisher_did_not_run_gives_INCONCLUSIVE_exit_3",
         {"p1-sim-pub": "exec-fail"}, 3, "INCONCLUSIVE", ["publishers rc: P1=1 P2=0 P3=0 P4=0", "P1=0 P2=0 P3=0 P4=1"]),
    # Broker log collection (project review round 3, item 3): never PASS; FAIL keeps precedence.
    Case("log_collection_failed_with_full_output_and_all_else_passing_gives_INCONCLUSIVE_exit_3",
         {"logs-final": "rc1-full"}, 3, "INCONCLUSIVE",
         [LOG_RC1, "P1=1 P2=0 P3=0 P4=1 rc=27", "liveness: covered=yes", "whole run: ctl-sub=1 sim-sub=1 (broker log rc=1)"]),
    Case("log_collection_failed_with_partial_output_and_all_else_passing_gives_INCONCLUSIVE_exit_3",
         {"logs-final": "rc1-truncated"}, 3, "INCONCLUSIVE",
         [LOG_RC1, "P1=1 P2=0 P3=0 P4=1 rc=27", "liveness: covered=yes", "whole run: ctl-sub=1 sim-sub=1 (broker log rc=1)",
          "anonymous: inconclusive rc=5 refusal_lines=1"]),
    Case("log_collection_empty_with_rc_0_gives_INCONCLUSIVE_exit_3",
         {"logs-final": "empty"}, 3, "INCONCLUSIVE", ["the collection is empty"]),
    Case("log_collection_no_longer_contains_the_anchor_line_gives_INCONCLUSIVE_exit_3",
         {"logs-final": "anchor-gone"}, 3, "INCONCLUSIVE", ["the anchor line occurs 0 times in the collection"]),
    Case("anchor_could_not_be_read_before_the_run_gives_INCONCLUSIVE_exit_3",
         {"logs-anchor": "rc1"}, 3, "INCONCLUSIVE", ["broker_log=incomplete (no anchor line was read before the run (rc=1)"]),
    Case("anchor_collection_empty_before_the_run_gives_INCONCLUSIVE_exit_3",
         {"logs-anchor": "empty"}, 3, "INCONCLUSIVE", ["broker_log=incomplete (no anchor line was read before the run (rc=0)"]),
    Case("log_collection_failed_and_unauthorised_delivery_gives_FAIL_exit_1",
         {"logs-final": "rc1-truncated", "acl": "leak-read"}, 1, "FAIL", [LOG_RC1, "deliveries=2 "]),
    Case("log_collection_failed_and_anonymous_session_alive_until_timeout_gives_FAIL_exit_1",
         {"logs-final": "rc1-truncated", "anon": "accepted-timeout"}, 1, "FAIL", [LOG_RC1, "anonymous: accepted rc=27"]),
]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_verdict(case, shell, tmp_path):
    r = run_probe(shell, tmp_path, case.behaviours, env=case.env)
    assert_verdict(r, case.code, case.verdict, case.decisive)


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write to a read-only directory")
@pytest.mark.parametrize("shell", SHELLS)
def test_evidence_directory_unwritable_after_the_run_gives_INCONCLUSIVE_exit_3_and_a_warning(shell, tmp_path):
    try:
        r = run_probe(shell, tmp_path, {"logs-final": "unwritable"})
    finally:
        out = tmp_path / "evidence" / "itest-acl"
        if out.exists():
            out.chmod(0o755)
    lines = r.stdout.splitlines()
    assert r.rc == 3, r.describe()
    assert lines and lines[-1] == "verdict=INCONCLUSIVE", r.describe()
    assert any("after_collection=failed" in ln for ln in lines), r.describe()
    assert "verdict.txt could NOT be written completely" in r.stderr, r.describe()
    assert not (r.out / "verdict.txt").exists()


# ---------------------------------------------------------------- usage and preconditions

def assert_nothing_run(r: Run, stderr_text: str) -> None:
    assert r.rc == 2, r.describe()
    assert stderr_text in r.stderr, r.describe()
    assert r.stdout == "", r.describe()
    assert r.calls == "", r.describe()          # docker was never called
    assert not (r.out / "verdict.txt").exists(), r.describe()


USAGE = [
    ("no_tag", dict(args=()), "usage: "),
    ("tag_with_a_space", dict(args=("a b",)), "usage: "),
    ("tag_with_a_slash", dict(args=("../x",)), "usage: "),
    ("window_not_a_number", dict(env={"ACL_PROBE_WINDOW": "9o"}), "must be whole numbers"),
    ("window_not_above_the_guard", dict(env={"ACL_PROBE_WINDOW": "2"}), "must be whole numbers"),
    ("ready_not_a_number", dict(env={"ACL_PROBE_READY": "-1"}), "must be whole numbers"),
    ("dot_env_missing", dict(dot_env=None), "/.env"),
    ("controller_password_missing", dict(dot_env="MOSQUITTO_SIMULATOR_PASSWORD=x\n"), "not set in"),
    ("simulator_password_empty", dict(dot_env="MOSQUITTO_SIMULATOR_PASSWORD=\nMOSQUITTO_CONTROLLER_PASSWORD=y\n"), "not set in"),
    ("evidence_directory_exists", dict(make_out=True), "refusing to overwrite"),
]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("kwargs,stderr_text", [u[1:] for u in USAGE], ids=[u[0] + "_gives_exit_2_nothing_run" for u in USAGE])
def test_precondition(kwargs, stderr_text, shell, tmp_path):
    r = run_probe(shell, tmp_path, **kwargs)
    assert_nothing_run(r, stderr_text)
    if not kwargs.get("make_out"):
        assert not r.out.exists(), r.describe()


@pytest.mark.parametrize("shell", SHELLS)
def test_dot_env_referencing_an_unset_variable_gives_exit_2_nothing_run_never_the_fail_code(shell, tmp_path):
    # Before the fix of 2026-09-18 bash left with its own status 1 (= FAIL) here.
    r = run_probe(shell, tmp_path, dot_env=DOT_ENV + "EGW_NOTE=$EGW_NOT_SET_ANYWHERE\n")
    assert r.rc == 2, r.describe()
    assert r.stdout == "" and r.calls == "" and not r.out.exists(), r.describe()


# Same class: reading .env must never end the probe with a verdict code, nor let it run on a file read in part.
# Before the fix: "exit 0" left with 0 (= PASS) in both shells; after the syntax error bash went on and ran docker.
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("tail", ["exit 0\n", "exit 1\n", "BROKEN=$(\n", "false\n"],
                         ids=["exit_0", "exit_1", "syntax_error", "last_command_fails"])
def test_dot_env_that_is_not_read_to_its_end_with_status_0_gives_exit_2_nothing_run(tail, shell, tmp_path):
    r = run_probe(shell, tmp_path, dot_env=DOT_ENV + tail)
    assert r.rc == 2, r.describe()
    assert r.stdout == "" and r.calls == "" and not r.out.exists(), r.describe()
    assert "nothing was run" in r.stderr, r.describe()


@pytest.mark.parametrize("shell", SHELLS)
def test_deployment_directory_missing_gives_exit_2_nothing_run(shell, tmp_path):
    r = run_probe(shell, tmp_path, env={"EGW_DEPLOY_DIR": str(tmp_path / "absent")})
    assert r.rc == 2 and r.stdout == "" and r.calls == "" and not r.out.exists(), r.describe()


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write to a read-only directory")
@pytest.mark.parametrize("shell", SHELLS)
def test_evidence_directory_cannot_be_created_gives_exit_2_nothing_run(shell, tmp_path):
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(0o555)
    try:
        r = run_probe(shell, tmp_path, env={"ACL_PROBE_OUT": str(parent / "itest-acl")})
    finally:
        parent.chmod(0o755)
    assert r.rc == 2 and r.stdout == "" and r.calls == "", r.describe()
    assert not (parent / "itest-acl").exists(), r.describe()
