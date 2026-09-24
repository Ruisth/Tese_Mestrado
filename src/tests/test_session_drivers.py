"""Cases for the session drivers of tools/session: which failures they enforce.

The drivers themselves are the files under test, copied unmodified into a
temporary directory (they locate their helpers from ``$0``) and run against a
stub environment that stands in for the emulated gateway:

* ``$EGW_EXEC_REPO`` is the real repository, so ``local_export``, ``git`` and
  ``fetch-collector-output.sh`` are the real ones; ``$EGW_EXEC_VENV/bin/python``
  is this interpreter and ``bin/activate`` is empty.
* ``$HOME`` holds a stub ``egw-tcg/.env``, ``egw-tcg/itest-helpers.sh`` and
  ``egw-tcg/tunnel.sh``: the section 6.1 host helpers (``pre``, ``drained``,
  ``fetch``, ``accounted``, ``snap_pair``, ``twin``, ``metrics``,
  ``wait_ready``, ``harness_run``) keep their contracts, write the files the
  real ones write, and fail when ``EGW_STUB_FAIL`` names them.
* The "guest" is this machine. ``ssh``, ``scp`` and ``pgrep`` are stubs first on
  ``PATH``; the ssh stub rewrites the guest's absolute paths onto a fake guest
  root and runs the command under ``sh``, so each driver's own guest text (its
  ``set -e``, its sha256 comparisons, its ``exit``) is what decides. The guest
  root holds a copy of the clone's ``src/deployment``, which is what
  ``deployed_vs_clone.py`` compares against.
* Four of the guest's own tools (``validate-config.sh``,
  ``verify-controller-image.sh``, ``prepare-broker-secrets.sh`` and
  ``capture-sut-environment.sh``) are substituted at the call, because they need
  a real stack and have their own tests, while the deployed files themselves
  must stay byte-identical to the clone's for the tree comparison.
* ``collector_check.py`` and ``nominal_account.py`` (owned elsewhere) and the
  guest session scripts are replaced by stubs in the copied driver folder.

What these cases show is the drivers' own failure handling: the exit status,
the verdicts written into ``attempt.json`` and whether a verified package
reached ``output_test``. They say nothing about QEMU, the guest or the network.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the session drivers are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_DIR = REPO_ROOT / "tools" / "session"
EXPECT_SERVICES = ("egw-mosquitto-1", "egw-mongodb-1", "egw-ditto-policies-1",
                   "egw-ditto-things-1", "egw-ditto-gateway-1", "egw-controller-1")

# --------------------------------------------------------------------------
# Host-side stubs: the section 6.1 helper file, the secrets file and the tunnel
# --------------------------------------------------------------------------

ENV_FILE = """# stub .env for the driver tests: the value is redacted from every record.
MOSQUITTO_SIMULATOR_PASSWORD=stub-simulator-password
"""

TUNNEL_SH = """# shellcheck shell=bash
tunnel_check() { [ "${EGW_STUB_TUNNEL:-up}" = up ]; }
tunnel_up() {
    # A tunnel of 5.7 that cannot be opened at all: the host preamble then
    # FAILS, so every host step that needed it never ran.
    [ "${EGW_STUB_TUNNEL:-up}" != broken ] \
        || { echo "stub: the tunnel could not be opened" >&2; return 1; }
    echo "stub: tunnel up"
}
tunnel_down() { echo "stub: tunnel down"; }
"""

ITEST_HELPERS = """# shellcheck shell=bash
# Stub of ~/egw-tcg/itest-helpers.sh (runbook 6.1) for the driver tests. Each
# helper keeps its contract: it writes what the real one writes and returns
# non-zero with a STOP: line when EGW_STUB_FAIL names it.
P=$HOME/egw-tcg/itest
CTRL=${CTRL:-http://127.0.0.1:8000}
DITTO=${DITTO:-http://127.0.0.1:8080}
MQTT_PORT=${MQTT_PORT:-8883}
REC="$EGW_STUB_BIN/rec"
SIM="$EGW_STUB_BIN/sim --output $P"
mkdir -p "$P"

stop() { echo "STOP: $*" >&2; return 1; }

# stub_fails NAME: true when EGW_STUB_FAIL names this step.
stub_fails() {
    case ",${EGW_STUB_FAIL:-}," in *",$1,"*) return 0 ;; esac
    return 1
}

wait_ready() {
    # The helper's own give-up, in the runbook's wording: it polled and never
    # got 200 within the limit, which is the one observation it can make.
    stub_fails wait_ready \
        && { stop "wait_ready: /ready answered '503', not 200, for ${1:-60} s (tunnel of 5.7 down? stack not healthy?)"; return 1; }
    # The same give-up with curl's code for a request nobody answered: the
    # tunnel dropped during the wait, so the controller said nothing at all.
    stub_fails wait_ready-000 \
        && { stop "wait_ready: /ready answered '000', not 200, for ${1:-60} s (tunnel of 5.7 down? stack not healthy?)"; return 1; }
    # The step dying in the transport instead: nothing was observed about
    # /ready, and no give-up was reported.
    stub_fails wait_ready-dropped \
        && { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; return 255; }
    echo "stub: /ready 200"
}

drained() {
    stub_fails drained && { stop "drained: no quiet window"; return 1; }
    # A quiet window that is still being waited out, so that a driver can be
    # interrupted while its first step is in progress.
    if [ -n "${EGW_STUB_QUIESCE_HANG_S:-}" ]; then
        : > "$EGW_STUB_LOG.quiescehang"
        sleep "$EGW_STUB_QUIESCE_HANG_S"
    fi
    # The drain AFTER the measured window is the one nominal.sh runs with its
    # own limit: these three fail only that one, and never the 'drained' of the
    # precondition, which runs before the harness. They are the three ways the
    # step ends non-zero, and only the first says anything about the queue:
    # the helper's own give-up (the runbook's wording, with a thirteen-field
    # reading: queue_depth in_progress unacked mqtt_subscribed started_at
    # mqtt_connection received accepted rejected duplicate failed dropped
    # processing_errors), the helper's OTHER stop (a /metrics it could not
    # read, or one without those fields, which is what a dropped tunnel, a
    # stopped controller or an earlier controller build leaves), and the step
    # dying in the transport.
    if [ "${DRAIN_LIMIT_S:-}" = 1500 ]; then
        stub_fails post-drain && { stop "drained: no quiet window of ${DRAIN_QUIET_S:-130} s within ${DRAIN_LIMIT_S:-900} s (last reading: 4 0 0 true 2026-09-19T20:00:00Z 1 64 60 0 0 0 0 0) - do not take snapshots, do not start a run"; return 1; }
        stub_fails post-drain-unreachable && { stop "drained: GET $CTRL/metrics failed or was not valid JSON, or a field was missing or of the wrong type (tunnel of 5.7 down? controller stopped? a controller build without the thirteen fields?)"; return 1; }
        stub_fails post-drain-dropped && { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; return 255; }
    fi
    echo "drained: queue_depth 0 and identical counters (stub observation)"
}

metrics() {
    stub_fails metrics && { stop "metrics $1 $2: GET /metrics failed"; return 1; }
    [ ! -e "$P/$1.metrics.$2.json" ] || { stop "metrics $1 $2: exists"; return 1; }
    printf '{"queue_depth": 0, "started_at": "2026-09-19T20:00:00Z", "accepted": 60, "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0}\\n' \
        > "$P/$1.metrics.$2.json"
}

twin() {
    stub_fails twin && { stop "twin $1 $2: GET failed"; return 1; }
    printf '{"thingId": "org.c2dta:%s", "features": {}}\\n' "$2" > "$P/$1.twin.$2.json"
}

fetch() {
    stub_fails fetch && { stop "fetch $1: scp of events.jsonl failed"; return 1; }
    [ -s "$P/$1/sent_events.jsonl" ] || { stop "fetch $1: nothing was published"; return 1; }
    cp "$P/$1/sent_events.jsonl" "$P/$1/events.jsonl"
}

snap_pair() {
    local id=$1 label=$2
    shift 2
    metrics "$id" "$label" || return 1
    stub_fails snap_pair && { stop "snap_pair $id $label: the twin snapshot failed"; return 1; }
    "$EGW_STUB_BIN/rec" snap --prefix "$P/$id" --label "$label" "$@"
}

accounted() {
    stub_fails accounted && { stop "accounted $1: published records without a logged outcome"; return 1; }
    echo "OUTCOME RECONCILIATION $1: stub; every published record has a logged outcome"
}

pre() {
    local x
    [ -n "$1" ] && [ -n "$2" ] || { stop "pre: usage"; return 1; }
    stub_fails pre && { stop "pre $1: precondition failed"; return 1; }
    for x in "$P/$1" "$P/$1.metrics.before.json" "$P/$1.marker.json"; do
        [ ! -e "$x" ] || { stop "pre $1: $x exists - choose a NEW run id"; return 1; }
    done
    mkdir -p "$P/$1"
    wait_ready "${READY_LIMIT_S:-60}" && drained && snap_pair "$1" before --seed "$2" ${3:+--devices "$3"}
}

harness_run() {
    stub_fails harness_run && { stop "harness_run $1: egw_experiments run exited non-zero"; return 1; }
    "$EGW_STUB_BIN/harness" "$1"
}
"""

SESSION_COMMON = """# shellcheck shell=bash
# Stub of the session's SSH helpers: the guest is this machine, reached through
# the ssh/scp stubs that are first on PATH.
#
# 'session-helpers-gone' is the session helper that is no longer loadable once
# the stack has been restarted, as a session directory that was removed or a
# file that was truncated leaves it: sourcing this file then FAILS, so the
# wrapper around it never runs anything on the guest at all.
case ",${EGW_STUB_FAIL:-}," in
    *,session-helpers-gone,*)
        if [ -e "${EGW_STUB_LOG:-}.restarted" ]; then
            echo "${E:-the session}/scripts/session_common.sh: the session helpers are not there" >&2
            return 1
        fi
        ;;
esac
gssh() { ssh -o BatchMode=yes egw@127.0.0.1 "$@"; }
gscp() { scp -q "$@"; }
log()  { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
run_name() { echo s1; }
"""

SESSION_CLOSE_STUB = """#!/bin/sh
# Stub of guest/session_close.sh: the controlled power-off.
case ",${EGW_STUB_FAIL:-}," in
    *,session-close,*)
        echo "STOP: the guest did not power off" >&2
        exit 1
        ;;
esac
rm -f "$EGW_STUB_LOG.qemu"
case ",${EGW_STUB_FAIL:-}," in
    *,session-close-record,*)
        # The real script's third status: the guest IS off, and the boot
        # journal or the final guest state was not kept.
        echo "STOP: the boot journal was not collected" >&2
        exit 3
        ;;
esac
echo "stub: journal kept, guest powered off"
exit 0
"""

SESSION_OPEN_STUB = """#!/bin/sh
# Stub of guest/session_open.sh: boots the guest and leaves it up.
case ",${EGW_STUB_FAIL:-}," in
    *,boot,*)
        echo "STOP: QEMU wrapper ended early" >&2
        exit 1
        ;;
esac
mkdir -p "$1/boot"
: > "$EGW_STUB_LOG.qemu"
echo "stub: guest up"
exit 0
"""

# --------------------------------------------------------------------------
# Stubs of the helper scripts the drivers call but do not own
# --------------------------------------------------------------------------

COLLECTOR_CHECK_STUB = '''"""Stub of collector_check.py: writes its report and reports any problem.

Like the real one it validates the collection against the COLLECTOR'S OWN
window, so a collection that ended early is clean here and only the published
shortfall says so: EGW_STUB_COLLECTOR_WINDOW_S is the window it found.
"""
import json
import os
import sys

directory, run, expected, wanted, sut = sys.argv[1:6]
problems = []
if f",{os.environ.get('EGW_STUB_FAIL', '')}," .find(",collector-check,") >= 0:
    problems.append("stub: the collector output was rejected")
for suffix in ("", ".diagnostics.log", ".lifecycle.csv"):
    if not os.path.isfile(os.path.join(directory, f"resources-{run}.csv{suffix}")):
        problems.append(f"resources-{run}.csv{suffix} is missing")
declared = 45.0
window = float(os.environ.get("EGW_STUB_COLLECTOR_WINDOW_S", declared))
report = {"run": run, "expected_services": expected, "wanted_sha256": wanted,
          "sut_environment": sut, "declared_duration_s": declared, "declared_interval_s": 1.0,
          "window_seconds": window,
          "declared_duration_shortfall_s": (declared - window) if window < declared else None,
          "problems": problems}
with open(os.path.join(directory, "collector-check.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2)
for problem in problems:
    print(f"PROBLEM: {problem}")
print(f"collector check: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
'''

NOMINAL_ACCOUNT_STUB = '''"""Stub of nominal_account.py: writes analysis/accounting.json.

Like the real one it copies from the harness manifest the two things the 60 s
confirmation deadline rests on: the controller marker it was measured from
(EGW_STUB_CONTROLLER_MARKER) and the source of the deadline in the harness row
(EGW_STUB_DEADLINE_SOURCE), and it HONOURS the fourth argument, which is what
the driver knows about its own fetch of the post-drain log: only 'fetched', and
only with the log on disk, publishes a tail. A stub that ignored it would
report a tail whatever the driver said, nonsense and nothing included.
"""
import json
import os
import sys

raw, events, analysis = sys.argv[1:4]
told = sys.argv[4] if len(sys.argv) > 4 else "missing"
if told not in ("fetched", "not-fetched", "unknown"):
    print(f"STOP: nominal.sh must say whether the post-drain log was fetched; it said {told!r}",
          file=sys.stderr)
    sys.exit(1)
if f",{os.environ.get('EGW_STUB_FAIL', '')}," .find(",accounting,") >= 0:
    print("STOP: the accounting could not be produced", file=sys.stderr)
    sys.exit(1)
row = json.loads(os.environ.get("EGW_STUB_HARNESS_ROW")
                 or '{"sent_valid": 6720, "delivered_unique": 6720, "lost": 0, "late_confirmations": 0}')
row.setdefault("confirmation_deadline_source",
               os.environ.get("EGW_STUB_DEADLINE_SOURCE", "controller-marker"))
marker = json.loads(os.environ.get("EGW_STUB_CONTROLLER_MARKER")
                    or '{"ok": true, "monotonic_ns": 1000000000000, "lag_s": 0.4}')
fetched = told == "fetched" and os.path.isfile(events)
os.makedirs(analysis, exist_ok=True)
with open(os.path.join(analysis, "accounting.json"), "w", encoding="utf-8") as fh:
    json.dump({"harness_row": row, "controller_marker": marker,
               "after_drain": "every published identity accounted" if fetched else None,
               "after_drain_fetch": told,
               "after_drain_note": None if fetched else
                                   "no figure of that tail is claimed here"}, fh, indent=2)
print(f"accounting written for {raw} against {events} (fetch reported as {told})")
# The accounting that FAILS AFTER writing its file, as one killed by the host
# while it prints, or one whose own final work fails, leaves it: the file on
# disk looks complete and the step still exited non-zero.
if f",{os.environ.get('EGW_STUB_FAIL', '')}," .find(",accounting-late,") >= 0:
    print("STOP: the accounting failed after writing accounting.json", file=sys.stderr)
    sys.exit(1)
'''

# --------------------------------------------------------------------------
# Host stubs first on PATH
# --------------------------------------------------------------------------

CURL_STUB = '''#!/usr/bin/env python3
"""Stub curl: the controller and Ditto behind the tunnels of runbook 5.7.

Every endpoint answers for itself, so a driver that reads /health, /ready,
/metrics and a twin sees four different bodies. What the tests steer is the
HTTP code of each one, the controller PROCESS the counters belong to (a new
`started_at` and zero counters once the stack has been restarted) and the
stored twin state that comes back after that restart.

Its failure modes are curl's own: without `-f` any HTTP answer is exit 0 and
the body is written, with `-f` an error answer is exit 22 and nothing is
written, and a connection that was not made is exit 7 with the code `000`.
"""
import json
import os
import sys

VALUE_OPTIONS = {"-o", "--output", "-w", "--write-out", "-m", "--max-time", "-H", "--header",
                 "-X", "-d", "--data", "-A", "-e", "--connect-timeout"}
failures = f",{os.environ.get('EGW_STUB_FAIL', '')},"


def fails(token):
    return f",{token}," in failures


def marker(suffix):
    return os.environ.get("EGW_STUB_LOG", "") + suffix


def restarted():
    """True once the stack has been taken down and brought up again."""
    return os.path.exists(marker(".restarted"))


def run_id():
    return "itest-g2-01"


def metrics():
    started = "2026-09-19T20:00:00Z"
    accepted = int(os.environ.get("EGW_STUB_METRICS_ACCEPTED", "0"))
    if restarted():
        # /metrics is per process: a restarted controller is a new process
        # with a new start instant and counters that begin again at zero.
        if not fails("started-at-unchanged"):
            started = "2026-09-19T21:11:00Z"
        accepted = 3 if fails("late-counters") else 0
    body = {"queue_depth": 0, "started_at": started, "accepted": accepted,
            "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0}
    body.update(json.loads(os.environ.get("EGW_STUB_METRICS_EXTRA") or "{}"))
    return json.dumps(body), os.environ.get("EGW_STUB_METRICS_CODE", "200")


def twin():
    if fails("twin-unreadable"):
        return "{this is not JSON", "200"
    # The persistence defect itself: the volume did not hold the thing, so
    # Ditto answers 404 for it. 'twin-gone-before' is the same answer from the
    # start, when there is no stored state to demonstrate the survival of.
    if fails("twin-gone-before") or (restarted() and fails("twin-gone")):
        return json.dumps({"status": 404, "error": "things:thing.notfound",
                           "message": "The Thing with ID 'org.c2dta:stub-device' "
                                      "could not be found."}), "404"
    # The reading that was NOT made after the restart: nothing answered at all.
    if restarted() and fails("twin-unreachable"):
        return "", "000"
    count = 1 if (restarted() and fails("twin-changed")) else 60
    body = {"thingId": "org.c2dta:stub-device",
            "attributes": {"device_type": "smartwatch", "egw_id": "egw-01",
                           "schema_version": "1.0"},
            "features": {"ingestion": {"properties": {
                "last_run_id": os.environ.get("EGW_STUB_TWIN_RUN_ID") or run_id(),
                "last_seq": 59, "accepted_count": count}}}}
    if restarted() and fails("twin-stateless"):
        # The thing came back and the state this run stored in it did not.
        body["features"] = {}
    return json.dumps(body), "200"


output = None
write_out = None
fail_on_error = False
url = ""
args = sys.argv[1:]
index = 0
while index < len(args):
    arg = args[index]
    if arg in VALUE_OPTIONS:
        value = args[index + 1] if index + 1 < len(args) else ""
        if arg in ("-o", "--output"):
            output = value
        elif arg in ("-w", "--write-out"):
            write_out = value
        index += 2
        continue
    if arg.startswith("-"):
        if arg == "--fail" or (not arg.startswith("--") and "f" in arg[1:]):
            fail_on_error = True
        index += 1
        continue
    url = arg
    index += 1

if url.endswith("/health"):
    body = os.environ.get("EGW_STUB_HEALTH_BODY") or json.dumps({"status": "ok"})
    code = os.environ.get("EGW_STUB_HEALTH_CODE", "200")
elif url.endswith("/ready"):
    body = json.dumps({"status": "ready", "mqtt": "subscribed", "ditto": "reachable"})
    code = os.environ.get("EGW_STUB_READY_CODE", "200")
elif url.endswith("/metrics"):
    body, code = metrics()
elif "/api/2/things/" in url:
    body, code = twin()
else:
    body, code = json.dumps({"stub": url}), "200"
if fails("curl-down"):
    body, code = "", "000"

if code == "000":
    if output:
        open(output, "w", encoding="utf-8").close()
    status = 7
elif fail_on_error and not code.startswith("2"):
    status = 22
else:
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(body)
    else:
        sys.stdout.write(body)
    status = 0
if write_out:
    sys.stdout.write(write_out.replace("%{http_code}", code).replace(chr(92) + "n", chr(10)))
sys.exit(status)
'''

GIT_STUB = """#!/bin/sh
# stub git: the clone the drivers run from is a worktree whose .git file names
# a Windows path, which git cannot follow from WSL, so the real git refuses
# here and every attempt would stop at its identity read. The stub answers the
# two questions repo_identity asks, so that what these cases exercise is the
# drivers' own handling; EGW_STUB_FAIL=git makes it refuse instead, as git does
# on a checkout whose owner differs from the caller.
case ",${EGW_STUB_FAIL:-}," in
    *,git,*)
        echo "fatal: detected dubious ownership in repository" >&2
        exit 128
        ;;
esac
for a in "$@"; do
    case "$a" in
        rev-parse) echo "1111111111111111111111111111111111111111"; exit 0 ;;
        status) exit 0 ;;
    esac
done
exit 0
"""

PGREP_STUB = """#!/bin/sh
# stub pgrep: only ever asked about qemu-system-aarch64. A qemu process exists
# once the boot stub has run, and 'qemu-left' keeps one alive after the close.
# 'pgrep-error' is a pgrep that cannot ANSWER (no /proc, a broken procps): it
# exits 2, which is not "no match" and must never be read as one.
case ",${EGW_STUB_FAIL:-}," in
    *,pgrep-error,*)
        echo "pgrep: cannot open /proc" >&2
        exit 2
        ;;
    *,qemu-left,*)
        echo "4242 qemu-system-aarch64 -machine virt"
        exit 0
        ;;
esac
if [ -e "$EGW_STUB_LOG.qemu" ]; then
    echo "4242 qemu-system-aarch64 -machine virt"
    exit 0
fi
exit 1
"""

SSH_STUB = '''#!/usr/bin/env python3
"""Stub ssh: runs the guest command on this machine, under sh, with the
guest's absolute paths rewritten onto the fake guest root and the guest's own
tools substituted at the call."""
import os
import subprocess
import sys

VALUE_OPTIONS = {"-o", "-i", "-p", "-P", "-F", "-l", "-b", "-c"}
SUBSTITUTIONS = (
    ("sh scripts/verify-controller-image.sh", "guest_tool verify-controller-image"),
    ("sh scripts/validate-config.sh", "guest_tool validate-config"),
    ("sh scripts/prepare-broker-secrets.sh", "guest_tool prepare-broker-secrets"),
    ("sh scripts/capture-sut-environment.sh", "guest_tool capture-sut-environment"),
)
PATHS = ("/opt/egw", "/var/lib/docker", "/tmp/resources-", "/tmp/collect-resources", "/tmp/egw-pf-")

root = os.environ["EGW_STUB_GUEST_ROOT"]
positional = []
args = sys.argv[1:]
index = 0
while index < len(args):
    arg = args[index]
    if arg in VALUE_OPTIONS:
        index += 2
        continue
    if arg.startswith("-"):
        index += 1
        continue
    positional.append(arg)
    index += 1
if len(positional) < 2:
    print("stub ssh: no command given", file=sys.stderr)
    sys.exit(255)
command = " ".join(positional[1:])
with open(os.environ["EGW_STUB_LOG"], "a", encoding="utf-8") as log:
    log.write(f"ssh {positional[0]} {command}\\n")
refuse = os.environ.get("EGW_STUB_SSH_REFUSE")
if refuse and refuse in command:
    print(f"ssh: connect to host 127.0.0.1 port 2222: Connection refused ({refuse})",
          file=sys.stderr)
    sys.exit(255)
for old, new in SUBSTITUTIONS:
    command = command.replace(old, new)
for path in PATHS:
    command = command.replace(path, root + path)
env = dict(os.environ)
env["PATH"] = os.environ["EGW_STUB_GUEST_BIN"] + os.pathsep + env["PATH"]
sys.exit(subprocess.run(["sh", "-c", command], env=env).returncode)
'''

SCP_STUB = '''#!/usr/bin/env python3
"""Stub scp: copies between this machine and the fake guest root."""
import os
import shutil
import sys

VALUE_OPTIONS = {"-o", "-i", "-P", "-p", "-F", "-l", "-c"}
root = os.environ["EGW_STUB_GUEST_ROOT"]
positional = []
args = sys.argv[1:]
index = 0
while index < len(args):
    arg = args[index]
    if arg in VALUE_OPTIONS:
        index += 2
        continue
    if arg.startswith("-"):
        index += 1
        continue
    positional.append(arg)
    index += 1
with open(os.environ["EGW_STUB_LOG"], "a", encoding="utf-8") as log:
    log.write("scp " + " ".join(positional) + "\\n")
if len(positional) < 2:
    print("stub scp: usage", file=sys.stderr)
    sys.exit(1)


def local(path):
    head, sep, tail = path.partition(":")
    if sep and "/" not in head:
        return root + tail
    return path


destination = local(positional[-1])
for source in positional[:-1]:
    path = local(source)
    fail = os.environ.get("EGW_STUB_SCP_FAIL")
    if fail and fail in path:
        print(f"scp: stub transfer failure for {path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(path):
        print(f"scp: {path}: No such file or directory", file=sys.stderr)
        sys.exit(1)
    target = os.path.join(destination, os.path.basename(path)) if os.path.isdir(destination) else destination
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    shutil.copyfile(path, target)
    corrupt = os.environ.get("EGW_STUB_SCP_CORRUPT")
    if corrupt and corrupt in path:
        with open(target, "ab") as fh:
            fh.write(b"x")
    # A transfer that SUCCEEDED and brought nothing, as a truncated copy does.
    empty = os.environ.get("EGW_STUB_SCP_EMPTY")
    if empty and empty in path:
        open(target, "w", encoding="utf-8").close()
sys.exit(0)
'''

# --------------------------------------------------------------------------
# Guest-side stubs (first on PATH inside the ssh stub only)
# --------------------------------------------------------------------------

SUDO_STUB = """#!/bin/sh
while [ $# -gt 0 ]; do
    case "$1" in -n | -E | -H) shift ;; *) break ;; esac
done
exec "$@"
"""

SLEEP_STUB = """#!/bin/sh
# stub sleep: the guest's waits are not waited out in the tests.
exec /bin/sleep 0.05
"""

TIMEDATECTL_STUB = """#!/bin/sh
case ",${EGW_STUB_FAIL:-}," in
    *,timedatectl,*)
        echo "Failed to query server: Connection timed out" >&2
        exit 1
        ;;
esac
echo "Timezone=UTC"
echo "NTPSynchronized=yes"
exit 0
"""

SYSTEMCTL_STUB = """#!/bin/sh
case "${1:-}" in
    is-system-running) echo running; exit 0 ;;
    is-active) echo inactive; exit 3 ;;
esac
exit 0
"""

JOURNALCTL_STUB = """#!/bin/sh
echo "stub journal: collector unit started"
echo "stub journal: collector unit finished"
exit 0
"""

DMESG_STUB = """#!/bin/sh
case ",${EGW_STUB_FAIL:-}," in
    *,dmesg,*)
        echo "dmesg: read kernel buffer failed: Operation not permitted" >&2
        exit 1
        ;;
esac
echo "[    0.000000] Linux version 6.6.0 (stub)"
case ",${EGW_STUB_FAIL:-}," in
    *,oom,*) echo "[  123.456789] Memory cgroup out of memory: Killed process 321 (java)" ;;
esac
exit 0
"""

OPENSSL_STUB = """#!/bin/sh
# stub openssl (present in the guest image, runbook 5.3): the CA's own subject,
# expiry and fingerprint. No private material is ever read or printed.
case ",${EGW_STUB_FAIL:-}," in
    *,openssl,*)
        echo "unable to load certificate" >&2
        exit 1
        ;;
esac
echo "subject=CN = EGW dev CA"
echo "notAfter=Sep 18 12:00:00 2027 GMT"
echo "SHA256 Fingerprint=AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"
exit 0
"""

GUEST_TOOL_STUB = '''#!/usr/bin/env python3
"""Stub of the guest's own deployment tools (they need a real stack)."""
import json
import os
import sys

tool = sys.argv[1]
if f",{os.environ.get('EGW_STUB_FAIL', '')}," .find(f",{tool},") >= 0:
    print(f"ERROR: {tool} failed", file=sys.stderr)
    sys.exit(1)
if tool == "capture-sut-environment":
    destination = sys.argv[2]
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "w", encoding="utf-8") as fh:
        json.dump({"node": "egw-guest", "provider": os.environ.get("EGW_PROVIDER", ""),
                   "instance_type": os.environ.get("EGW_INSTANCE_TYPE", "")}, fh, indent=2)
print(f"{tool}: OK (stub)")
'''

DOCKER_STUB = '''#!/usr/bin/env python3
"""Stub docker/docker compose: the six expected services of the stack."""
import os
import sys

SERVICES = ("egw-mosquitto-1", "egw-mongodb-1", "egw-ditto-policies-1",
            "egw-ditto-things-1", "egw-ditto-gateway-1", "egw-controller-1")
failures = f",{os.environ.get('EGW_STUB_FAIL', '')},"
args = sys.argv[1:]
compose = False
while args and (args[0] == "compose" or args[0] == "--env-file"):
    if args[0] == "compose":
        compose = True
        args = args[1:]
    else:
        args = args[2:]


def fails(token):
    return f",{token}," in failures


if fails("docker-daemon"):
    # The daemon is not there at all: every docker call fails, and the record
    # the caller is writing holds an empty '## docker' section.
    print("Cannot connect to the Docker daemon at unix:///var/run/docker.sock.",
          file=sys.stderr)
    sys.exit(1)


def state(name):
    if fails("service-down") and name == SERVICES[0]:
        return "exited"
    return "running"


def polls(suffix):
    """How many times this stub has been asked one thing, counted on disk so
    that a wait which polls can be answered differently on each sample."""
    path = os.environ.get("EGW_STUB_LOG", "") + suffix
    seen = 0
    try:
        with open(path, encoding="utf-8") as fh:
            seen = int(fh.read() or 0)
    except (OSError, ValueError):
        seen = 0
    seen += 1
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(str(seen))
    return seen


def health(name):
    """What the container's healthcheck says. Only 'unhealthy' is the service
    failing: 'starting' is a healthcheck that has not concluded and 'none' a
    container that declares none, and neither says anything about the service,
    which is then judged by its state alone. The live preflight of 2026-09-19
    recorded 'egw-controller-1 running starting' and passed.

    G2 is stricter and waits for 'healthy': 'health-transition' is a service
    whose check concludes on the third sample, which is what such a wait has
    to be able to show."""
    if fails("service-unhealthy") and name == SERVICES[1]:
        return "unhealthy"
    if fails("health-starting") and name == SERVICES[5]:
        return "starting"
    if fails("no-healthcheck") and name == SERVICES[5]:
        return "none"
    if fails("health-transition") and name == SERVICES[5]:
        return "starting" if polls(".healthpolls") <= 2 else "healthy"
    return "healthy"


def restarted():
    """True once 'compose down' has been run: from there on every container
    object is a new one and the controller process is a new process."""
    return os.path.exists(os.environ.get("EGW_STUB_LOG", "") + ".restarted")


def midrun():
    """True once the measured window has passed: the harness stub writes this
    marker between the two guest-state snapshots."""
    return os.path.exists(os.environ.get("EGW_STUB_LOG", "") + ".midrun")


def oomkilled(name):
    return "true" if (fails("service-oomkilled") and name == SERVICES[2]) else "false"


def restarts(name):
    """A container that restarted while the measured run was in progress, and
    one that was destroyed and recreated in it: the new container object starts
    again at 0, so its count FALLS between the two records."""
    if fails("service-restarted") and name == SERVICES[5] and midrun():
        return "3"
    if fails("service-recreated") and name == SERVICES[3]:
        return "0" if midrun() else "3"
    return "0"


def container_id(name):
    """The container object's own id: a recreated container has a new one, and
    so does every container after a 'down' and 'up -d'. 'ids-unchanged' is the
    restart that was issued and did not replace the objects."""
    suffix = "b" if (fails("service-recreated") and name == SERVICES[3] and midrun()) else "a"
    if restarted() and not fails("ids-unchanged"):
        suffix = "c"
    return f"{SERVICES.index(name):02d}" + suffix * 62


def started_at(name):
    """When the container last started. A container restarted IN PLACE keeps
    its object (same id) and its RestartCount, which Docker increments from the
    restart POLICY: the instant it started again is the only thing that moves.

    'state-unreadable' is an inspect that ANSWERS NOTHING after the run, as a
    docker under pressure does: the field is then unknown, which is not a
    state, and the record of the guest after the run is not usable."""
    if fails("state-unreadable") and midrun():
        return ""
    if restarted() and not fails("not-later"):
        return "2026-09-19T21:11:00.500000000Z"
    moved = ((fails("service-restarted-in-place") and name == SERVICES[4])
             or (fails("service-recreated") and name == SERVICES[3])) and midrun()
    return "2026-09-19T20:31:07.100000000Z" if moved else "2026-09-19T19:58:00.100000000Z"


def listed():
    """The containers 'docker ps' reports: one may never have been there at
    all ('service-absent': docker answers 'No such object' for it, as it does
    for a container that was removed), and one may be gone after the run."""
    if fails("service-absent"):
        return tuple(name for name in SERVICES if name != SERVICES[2])
    if fails("service-gone") and midrun():
        return tuple(name for name in SERVICES if name != SERVICES[3])
    return SERVICES


command = args[0] if args else ""
if command == "up":
    if fails("docker-up"):
        print("stub: 'up -d' failed", file=sys.stderr)
        sys.exit(1)
    hang = os.environ.get("EGW_STUB_HANG_S")
    if hang:
        open(os.environ["EGW_STUB_LOG"] + ".hang", "w", encoding="utf-8").close()
        import time
        time.sleep(float(hang))
    for name in SERVICES:
        print(f"Container {name}  Started")
    sys.exit(0)
if command == "stop":
    if fails("stack-stop"):
        print("stub: the stack did not stop", file=sys.stderr)
        sys.exit(1)
    for name in SERVICES:
        print(f"Container {name}  Stopped")
    sys.exit(0)
if command == "down":
    # A driver of this repository never removes a volume: the stored state is
    # what the persistence check reads back, so the stub refuses -v loudly
    # instead of quietly destroying it.
    if "-v" in args or "--volumes" in args:
        print("stub: 'down -v' removes the named volumes and no driver may ask for it",
              file=sys.stderr)
        sys.exit(1)
    if fails("docker-down"):
        print("stub: 'down' failed", file=sys.stderr)
        sys.exit(1)
    open(os.environ["EGW_STUB_LOG"] + ".restarted", "w", encoding="utf-8").close()
    if fails("late-records"):
        # The controller logged another record of this run after the restart:
        # the quiet the persistence check rests on was not held.
        events = os.path.join(os.environ["EGW_STUB_GUEST_ROOT"], "opt", "egw", "deployment",
                              "data", "events", os.environ.get("EGW_STUB_TWIN_RUN_ID", ""))
        if os.path.isdir(events):
            with open(os.path.join(events, "events.jsonl"), "a", encoding="utf-8") as fh:
                fh.write('{"message_id": "m-late", "outcome": "accepted"}\\n')
    for name in SERVICES:
        print(f"Container {name}  Removed")
    sys.exit(0)
if command == "image" and len(args) > 1 and args[1] == "inspect":
    # An inspect that does not ANSWER reads no identity at all; an image BUILT
    # on the guest answers with no repo digest, which the caller's template
    # renders as 'none'. The two are not the same record.
    if fails("no-repo-digest"):
        print("Error: No such image", file=sys.stderr)
        sys.exit(1)
    if fails("locally-built-image"):
        print("none")
        sys.exit(0)
    print("stub/controller@sha256:" + "f" * 64)
    sys.exit(0)
if command == "ps":
    template = args[args.index("--format") + 1] if "--format" in args else "{{.Name}}"
    for name in listed():
        line = (template.replace("{{.Name}}", name).replace("{{.Names}}", name)
                .replace("{{.State}}", state(name)).replace("{{.Health}}", health(name))
                .replace("{{.Status}}", f"Up 3 minutes ({health(name)})")
                .replace("{{.Image}}", f"stub/{name}:1"))
        print(line)
    sys.exit(0)
if command == "inspect":
    template = args[args.index("-f") + 1] if "-f" in args else ""
    name = args[-1]
    if name not in listed():
        print(f"Error: No such object: {name}", file=sys.stderr)
        sys.exit(1)
    if fails("inspect-unanswered") and name == SERVICES[4]:
        # 'docker ps -a' holds this container and the inspect still fails, as a
        # daemon under pressure makes it: this is NOT the daemon saying the
        # container is gone, and nothing about it is determined by it.
        print("Error response from daemon: context deadline exceeded", file=sys.stderr)
        sys.exit(1)
    if ".Config.Image" in template:
        print(f"stub/{name}:1")
    elif ".Image" in template:
        print("sha256:" + "e" * 64)
    elif ".State.Health" in template:
        print(health(name))
    elif ".State.OOMKilled" in template:
        print(oomkilled(name))
    elif ".RestartCount" in template:
        print(restarts(name))
    elif ".Id" in template:
        print(container_id(name))
    elif ".State.StartedAt" in template:
        print(started_at(name))
    elif ".State.Status" in template:
        print(state(name))
    else:
        print("")
    sys.exit(0)
if command == "stats":
    for name in SERVICES:
        print(f"{name} 120MiB / 768MiB 15.6% 3.20%")
    sys.exit(0)
if command == "images":
    print("stub/controller 0.1.0 sha256:0000")
    sys.exit(0)
print(f"stub docker: nothing to do for {command!r} (compose={compose})")
sys.exit(0)
'''

SYSTEMD_RUN_STUB = '''#!/usr/bin/env python3
"""Stub systemd-run: runs the collector for one bounded window."""
import os
import sys

if f",{os.environ.get('EGW_STUB_FAIL', '')}," .find(",collector-live,") >= 0:
    print("stub: the collector unit could not be started", file=sys.stderr)
    sys.exit(1)
csv = next((a for a in sys.argv[1:] if a.endswith(".csv")), None)
if csv is None:
    print("stub systemd-run: no output path", file=sys.stderr)
    sys.exit(1)
os.makedirs(os.path.dirname(csv), exist_ok=True)
services = ("egw-mosquitto-1", "egw-mongodb-1", "egw-ditto-policies-1",
            "egw-ditto-things-1", "egw-ditto-gateway-1", "egw-controller-1")
with open(csv, "w", encoding="utf-8") as fh:
    fh.write("timestamp_utc,monotonic_ns,service,cpu_usage_usec,memory_current_bytes\\n")
    for second in range(45):
        for service in services:
            fh.write(f"2026-09-19T20:00:{second:02d}Z,{second * 10 ** 9},{service},1000,1048576\\n")
with open(csv + ".diagnostics.log", "w", encoding="utf-8") as fh:
    fh.write("2026-09-19T20:00:00Z start: collector_sha256=stub\\n")
    fh.write("2026-09-19T20:00:01Z inventory: missing=\\n")
    fh.write("2026-09-19T20:00:45Z stop: samples=45\\n")
with open(csv + ".lifecycle.csv", "w", encoding="utf-8") as fh:
    fh.write("service,container_id,started_at\\n")
    for service in services:
        fh.write(f"{service},stub,2026-09-19T19:58:00Z\\n")
print(f"Running as unit: {sys.argv[sys.argv.index('--unit') + 1]}.service")
'''

# --------------------------------------------------------------------------
# Stubs of the 6.1 tools the host helpers drive
# --------------------------------------------------------------------------

REC_STUB = '''#!/usr/bin/env python3
"""Stub of egw_experiments.itest_reconcile: mark, wait, check, delta, snap, same.

Its exit codes are the real ones: 0 carried out, 1 not carried out, 3 check:
not a protocol check, 4 delta: MISMATCH or queue not empty, same: DIFFERENT.
"""
import json
import os
import sys

DEFAULT_ROW = {"confirmation_deadline_source": "controller", "sent_valid": 60,
               "delivered_unique": 60, "lost": 0, "late_confirmations": 0,
               "double_accepted": 0, "intended_invalid_accepted": 0, "marker_lag_s": 0.4}
failures = f",{os.environ.get('EGW_STUB_FAIL', '')},"
command = sys.argv[1]


def prefix_of():
    if command in ("snap", "same"):
        return sys.argv[sys.argv.index("--prefix") + 1]
    return sys.argv[2].rstrip("/")


def devices_of(label):
    with open(prefix_of() + f".twins.{label}.json", encoding="utf-8") as fh:
        return json.load(fh)["devices"]


def write(suffix, body):
    with open(prefix_of() + suffix, "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=2)


if f",rec-{command}," in failures:
    print(f"error: stub {command} was not carried out", file=sys.stderr)
    sys.exit(1)
if command == "mark":
    write(".marker.json", {"confirmation_deadline_monotonic_ns": 10 ** 12, "clock_domain": "controller"})
elif command == "wait":
    write(".window-closed.json", {"monotonic_ns": 2 * 10 ** 12})
elif command == "snap":
    label = sys.argv[sys.argv.index("--label") + 1]
    # A twin whose stored state did not come back unchanged after a restart:
    # the snapshot taken then differs from the one taken before it.
    count = 1 if (label == "post-restart" and ",twin-changed," in failures) else 60
    write(f".twins.{label}.json", {"devices": {"stub-device": {"ingestion": count}}})
elif command == "same":
    before, after = sys.argv[-2], sys.argv[-1]
    left, right = devices_of(before), devices_of(after)
    for device in left:
        state = "identical" if left[device] == right.get(device) else "DIFFERENT"
        print(f"{device}: {state} {left[device]}")
    sys.exit(0 if left == right else 4)
elif command == "check":
    row = json.loads(os.environ.get("EGW_STUB_RECONCILE") or json.dumps(DEFAULT_ROW))
    write(".reconcile.json", {"row": row})
    print(f"check: {row}")
    sys.exit(int(os.environ.get("EGW_STUB_REC_CHECK", "0")))
elif command == "delta":
    print("delta: stub comparison")
    sys.exit(int(os.environ.get("EGW_STUB_REC_DELTA", "0")))
print(f"{command}: OK (stub)")
'''

SIM_STUB = '''#!/usr/bin/env python3
"""Stub simulator: writes sent_events.jsonl for one run."""
import json
import os
import sys

if f",{os.environ.get('EGW_STUB_FAIL', '')}," .find(",sim,") >= 0:
    print("stub simulator: publishing failed", file=sys.stderr)
    sys.exit(1)
args = sys.argv[1:]
output = args[args.index("--output") + 1]
run_id = args[args.index("--run-id") + 1]
directory = os.path.join(output, run_id)
os.makedirs(directory, exist_ok=True)
with open(os.path.join(directory, "sent_events.jsonl"), "w", encoding="utf-8") as fh:
    for sequence in range(60):
        fh.write(json.dumps({"message_id": f"m-{sequence:04d}", "device_uuid": "stub-device",
                             "device_type": "smartwatch", "seq": sequence, "run_id": run_id}) + "\\n")
print("tls=True qos=1 devices=smartwatch", file=sys.stderr)
print("done sent=60 intended_invalid=0 buffered_dropout=0 dropout_disconnects=0", file=sys.stderr)
'''

HARNESS_STUB = '''#!/usr/bin/env python3
"""Stub of 'egw_experiments run': seals one raw run directory."""
import json
import os
import sys

run_id = sys.argv[1]
raw = os.path.join(os.environ["HOME"], "egw-tcg", "pilot", "results", "raw", run_id)
os.makedirs(os.path.join(raw, "logs", "collector"), exist_ok=True)
# The measured window has passed: from here on the docker stub reports what
# happened to the containers during it (a restart, a recreation, a container
# that is gone), which is what the two guest-state records are compared for.
if any(f",{token}," in f",{os.environ.get('EGW_STUB_FAIL', '')},"
       for token in ("service-restarted", "service-recreated", "service-gone",
                     "service-restarted-in-place", "state-unreadable")):
    open(os.environ["EGW_STUB_LOG"] + ".midrun", "w", encoding="utf-8").close()
# The controller's own event log, on the guest, for the measured run and its
# warm-up: what the driver fetches after the drain.
events = os.path.join(os.environ["EGW_STUB_GUEST_ROOT"], "opt", "egw", "deployment", "data", "events")
for bucket in (run_id, run_id + ".warmup"):
    os.makedirs(os.path.join(events, bucket), exist_ok=True)
    with open(os.path.join(events, bucket, "events.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"message_id": "m-0000", "run_id": bucket, "outcome": "accepted"}) + "\\n")
validity = os.environ.get("EGW_STUB_MANIFEST_VALIDITY", "valid")
manifest = {"run_id": run_id, "validity": validity,
            "validity_reasons": [] if validity == "valid" else ["stub: the collector output was rejected"]}
with open(os.path.join(raw, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2)
# Every artefact nominal.sh declares as expected of a sealed capsule: without
# them the package really is incomplete, which is a verdict of its own.
sealed = {
    "sent_events.jsonl": json.dumps({"message_id": "m-0000", "run_id": run_id}) + "\\n",
    "events.jsonl": json.dumps({"message_id": "m-0000", "run_id": run_id,
                                "outcome": "accepted"}) + "\\n",
    "controller_metrics.csv": "ts_utc,queue_depth,accepted\\n2026-09-19T20:00:00Z,0,60\\n",
    "resources.csv": "ts_utc,service,cpu_usage_usec,memory_current_bytes\\n"
                     "2026-09-19T20:00:00Z,egw-controller-1,1000,1048576\\n",
    "logs/collector/resources-stub.csv": "ts_utc,service\\n2026-09-19T20:00:00Z,egw-controller-1\\n",
    "logs/collector/resources-stub.csv.diagnostics.log":
        "2026-09-19T20:00:00Z start: collector_sha256=stub\\n"
        "2026-09-19T20:00:01Z inventory: missing=\\n"
        "2026-09-19T20:12:02Z stop: samples=722\\n",
    "logs/collector/resources-stub.csv.lifecycle.csv":
        "service,container_id,started_at\\negw-controller-1,stub,2026-09-19T19:58:00Z\\n",
}
skip = os.environ.get("EGW_STUB_HARNESS_SKIP", "")
for name, body in sealed.items():
    if name == skip:
        continue
    with open(os.path.join(raw, name), "w", encoding="utf-8") as fh:
        fh.write(body)
with open(os.path.join(raw, "SHA256SUMS"), "w", encoding="utf-8") as fh:
    for name in ["manifest.json", *sealed]:
        fh.write(f"{'0' * 64}  {name}\\n")
print(f"harness run {run_id}: manifest validity {validity}")
'''


PY_CAPTURE_FAIL = '''#!/usr/bin/env python3
"""A $PY that behaves as interfaces 1 and 2 say local_export must when the
mandatory console capture of one named step fails: the command itself runs and
keeps its own exit code in commands.jsonl, the attempt grows a
capture_failures entry and its validity is downgraded, and the CLI exits 74.
Every other call is this interpreter, unchanged."""
import json
import os
import subprocess
import sys

args = sys.argv[1:]
target = os.environ["EGW_FAIL_CAPTURE_OF"]
real = os.environ["EGW_REAL_PYTHON"]
if "--name" in args and args[args.index("--name") + 1] == target:
    code = subprocess.run([real] + args).returncode
    attempt = args[args.index("--attempt") + 1]
    path = os.path.join(attempt, "attempt.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("capture_failures", []).append(
        {"seq": 1, "name": target, "stream": "stdout",
         "error": "[Errno 28] No space left on device",
         "bytes_received": 4096, "bytes_kept": 512})
    if data.get("instrumentation_validity") == "valid":
        data["instrumentation_validity"] = "invalid"
        data["validity_note"] = "downgraded from 'valid': 1 console capture(s) failed"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    print(f"error: the console capture of {target!r} failed (the command exited {code})",
          file=sys.stderr)
    sys.exit(74)
sys.exit(subprocess.run([real] + args).returncode)
'''

PY_ABSENT_MODULE = '''#!/usr/bin/env python3
"""A $PY whose FIRST pytest call is pointed at a module that is not there, as a
module moved, renamed or unreadable would be: pytest exits 4 ("file or
directory not found") and no test runs. Every other call is this interpreter."""
import os
import subprocess
import sys

args = sys.argv[1:]
real = os.environ["EGW_REAL_PYTHON"]
if "--name" in args and args[args.index("--name") + 1] == "pytest-local-export":
    args = [a.replace("tests/test_local_export.py", "tests/test_absent_module.py") for a in args]
sys.exit(subprocess.run([real] + args).returncode)
'''

PY_SKIPPED_MODULE = '''#!/usr/bin/env python3
"""A $PY whose FIRST pytest call is pointed at a module every case of which is
SKIPPED, as an environment-conditional skip at conftest or interpreter level
leaves one: pytest exits 0 and writes a report that counts the cases it
collected. Every other call is this interpreter, unchanged."""
import os
import subprocess
import sys

args = sys.argv[1:]
real = os.environ["EGW_REAL_PYTHON"]
if "--name" in args and args[args.index("--name") + 1] == "pytest-local-export":
    args = [os.environ["EGW_STUB_SKIPPED_MODULE"] if a.endswith("tests/test_local_export.py") else a
            for a in args]
sys.exit(subprocess.run([real] + args).returncode)
'''

ALL_SKIPPED_MODULE = '''"""Every case of this module is skipped, as a conftest-level skip leaves it."""
import pytest

pytestmark = pytest.mark.skip(reason="stub: nothing in this module is executed")


def test_one():
    assert True


def test_two():
    assert True
'''

PY_BACKFILL_FAILS_THEN_INTERRUPT = '''#!/usr/bin/env python3
"""A $PY whose `local_export backfill` always fails and which, on the second
capsule, sends the signal that interrupts the driver — as an operator does
after watching the first capsules fail. Every other call is this interpreter."""
import os
import signal
import subprocess
import sys

args = sys.argv[1:]
real = os.environ["EGW_REAL_PYTHON"]
if args[:2] == ["-m", "egw_experiments.local_export"] and args[2:3] == ["backfill"]:
    marker = os.environ["EGW_STUB_LOG"] + ".backfill"
    seen = int(open(marker, encoding="utf-8").read() or 0) if os.path.exists(marker) else 0
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write(str(seen + 1))
    print("error: the capsule could not be copied into output_test", file=sys.stderr)
    if seen:
        os.killpg(os.getpgid(0), signal.SIGTERM)
    sys.exit(2)
sys.exit(subprocess.run([real] + args).returncode)
'''

PY_SET_FAILS = '''#!/usr/bin/env python3
"""A $PY whose `local_export set --attempt` always fails, as a full or
read-only attempts area makes it: the clone's identity, the export tool's hash
and the drivers' hash never reach the attempt. Every other call is this
interpreter, unchanged."""
import os
import subprocess
import sys

args = sys.argv[1:]
real = os.environ["EGW_REAL_PYTHON"]
if args[:2] == ["-m", "egw_experiments.local_export"] and args[2:3] == ["set"]:
    print("error: the attempts area is full", file=sys.stderr)
    sys.exit(2)
sys.exit(subprocess.run([real] + args).returncode)
'''

PY_SET_FIELD_FAILS = '''#!/usr/bin/env python3
"""A $PY whose `local_export set --attempt` fails for the ONE field named in
EGW_FAIL_SET_FIELD, as a full or read-only attempts area or an attempt.json
that cannot be rewritten makes it: the verdict the driver established never
reaches attempt.json. Every other call, every other `set` included, is this
interpreter, unchanged."""
import os
import subprocess
import sys

args = sys.argv[1:]
real = os.environ["EGW_REAL_PYTHON"]
field = os.environ["EGW_FAIL_SET_FIELD"]
if (args[:2] == ["-m", "egw_experiments.local_export"] and args[2:3] == ["set"]
        and any(a.startswith(field + "=") for a in args)):
    print(f"error: {field} could not be written: the attempts area is full", file=sys.stderr)
    sys.exit(2)
sys.exit(subprocess.run([real] + args).returncode)
'''

PY_EXPORT_FAILS_ONCE = '''#!/usr/bin/env python3
"""A $PY whose `local_export export` always fails and whose SECOND
`local_export new` fails too, as a full attempts area and a broken output_test
mount do together: the first check's package never reaches output_test and the
attempt for the second check cannot be created. Its first pytest call is
pointed at a module that is not there, so nothing long runs."""
import os
import subprocess
import sys

args = sys.argv[1:]
real = os.environ["EGW_REAL_PYTHON"]
command = args[2] if args[:2] == ["-m", "egw_experiments.local_export"] else ""
if command == "export":
    print("error: the package could not be written to output_test", file=sys.stderr)
    sys.exit(2)
if command == "new":
    marker = os.environ["EGW_STUB_LOG"] + ".new"
    seen = int(open(marker, encoding="utf-8").read() or 0) if os.path.exists(marker) else 0
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write(str(seen + 1))
    if seen:
        print("error: the attempts area is full", file=sys.stderr)
        sys.exit(2)
if "--name" in args and args[args.index("--name") + 1] == "pytest-local-export":
    args = [a.replace("tests/test_local_export.py", "tests/test_absent_module.py") for a in args]
sys.exit(subprocess.run([real] + args).returncode)
'''


# --------------------------------------------------------------------------
# The bench
# --------------------------------------------------------------------------


def _write(path: Path, text: str, executable: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)
    return path


class Bench:
    """The stub environment one driver runs in."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.drivers = tmp_path / "drivers"
        shutil.copytree(SESSION_DIR, self.drivers)
        self.exec_dir = tmp_path / "exec"
        self.attempts = self.exec_dir / "attempts"
        self.out = tmp_path / "output_test"
        self.home = tmp_path / "home"
        self.guest_root = tmp_path / "guest"
        self.bin = tmp_path / "bin"
        self.guest_bin = tmp_path / "gbin"
        self.log = tmp_path / "stub.log"
        # What a fixture has set up for this bench (the run id a completed
        # slice left behind, say): part of every environment, and still
        # overridable per run.
        self.extra: dict[str, str] = {}
        for directory in (self.attempts, self.out, self.home, self.bin, self.guest_bin):
            directory.mkdir(parents=True, exist_ok=True)

        # The virtual environment: this interpreter, and an empty activate.
        _write(self.exec_dir / "venv" / "bin" / "python",
               f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', executable=True)
        _write(self.exec_dir / "venv" / "bin" / "activate", "# stub activate\n")
        _write(self.exec_dir / "venv-freeze.txt", "stub-package==0.0.1\n")

        # Host side: the secrets file and the section 6.1 helpers.
        _write(self.home / "egw-tcg" / ".env", ENV_FILE)
        _write(self.home / "egw-tcg" / "itest-helpers.sh", ITEST_HELPERS)
        _write(self.home / "egw-tcg" / "tunnel.sh", TUNNEL_SH)
        _write(self.home / "egw-tcg" / "ca.crt", "stub certificate\n")
        (self.home / "egw-tcg" / "itest").mkdir(parents=True, exist_ok=True)

        # The helpers the drivers call but do not own.
        _write(self.drivers / "collector_check.py", COLLECTOR_CHECK_STUB)
        _write(self.drivers / "nominal_account.py", NOMINAL_ACCOUNT_STUB)
        _write(self.drivers / "guest" / "session_open.sh", SESSION_OPEN_STUB, executable=True)
        _write(self.drivers / "guest" / "session_close.sh", SESSION_CLOSE_STUB, executable=True)

        # Host stubs first on PATH.
        _write(self.bin / "ssh", SSH_STUB, executable=True)
        _write(self.bin / "scp", SCP_STUB, executable=True)
        _write(self.bin / "pgrep", PGREP_STUB, executable=True)
        _write(self.bin / "curl", CURL_STUB, executable=True)
        _write(self.bin / "git", GIT_STUB, executable=True)
        for name, text in (("rec", REC_STUB), ("sim", SIM_STUB), ("harness", HARNESS_STUB)):
            _write(self.bin / name, text, executable=True)

        # Guest stubs, reached only through the ssh stub.
        for name, text in (("sudo", SUDO_STUB), ("sleep", SLEEP_STUB), ("dmesg", DMESG_STUB),
                           ("timedatectl", TIMEDATECTL_STUB), ("systemctl", SYSTEMCTL_STUB),
                           ("journalctl", JOURNALCTL_STUB), ("docker", DOCKER_STUB),
                           ("systemd-run", SYSTEMD_RUN_STUB), ("guest_tool", GUEST_TOOL_STUB),
                           ("openssl", OPENSSL_STUB)):
            _write(self.guest_bin / name, text, executable=True)

        # The fake guest: the clone's deployment tree, as it is deployed.
        deployment = self.guest_root / "opt" / "egw" / "deployment"
        shutil.copytree(REPO_ROOT / "src" / "deployment", deployment)
        (deployment / "data" / "events").mkdir(parents=True, exist_ok=True)
        _write(deployment / ".env", "STUB=1\n")
        # The TLS material and the broker password file, which the clone does
        # not hold (they are generated on the guest, runbook 5.3 and 5.4) and
        # which the deployed-tree listing never lists. Only their modes are
        # ever recorded; the bytes here stand for bytes nothing may read.
        self.certs = deployment / "mosquitto" / "config" / "certs"
        for name, mode in (("ca.crt", 0o644), ("server.crt", 0o644), ("server.key", 0o600)):
            _write(self.certs / name, f"stub {name}, never read by any driver\n").chmod(mode)
        _write(deployment / "mosquitto" / "config" / "passwd",
               "egw-simulator:stub-hash\n").chmod(0o600)
        _write(self.guest_root / "opt" / "egw" / "images"
               / "egw-controller-0.1.0-arm64.identity.txt", "sha256:stub\n")
        (self.guest_root / "var" / "lib" / "docker").mkdir(parents=True, exist_ok=True)
        (self.guest_root / "tmp").mkdir(parents=True, exist_ok=True)

        # The controller image archive and its identity record.
        self.images = tmp_path / "egw-images"
        _write(self.images / "egw-controller-0.1.0-arm64.tar", "stub image archive\n")
        _write(self.images / "egw-controller-0.1.0-arm64.identity.txt", "sha256:stub\n")

        self.build_integrated()
        self.session = self.open_session()

    # -- the identified OS build the session boots -------------------------
    def build_integrated(self) -> None:
        """The build artefacts, launcher and QEMU binary whose identities
        `guest_session_open.sh` reads before it starts anything."""
        checkout = self.tmp / "yocto"
        build = checkout / "src" / "yocto" / "build-integrated"
        self.deploy = build / "tmp" / "deploy" / "images" / "qemuarm64"
        stamp = "egw-gateway-image-qemuarm64.rootfs-20260918120819"
        for name in ("Image-qemuarm64.bin", f"{stamp}.tar.bz2", f"{stamp}.ext4",
                     f"{stamp}.qemuboot.conf", f"{stamp}.manifest"):
            _write(self.deploy / name, f"stub {name}\n")
        _write(checkout / "egw-data.img", "stub data disk\n")
        self.qemu = (build / "tmp" / "work" / "x86_64-linux" / "qemu-helper-native" / "1.0"
                     / "recipe-sysroot-native" / "usr" / "bin" / "qemu-system-aarch64")
        _write(self.qemu, '#!/bin/sh\n[ "${1:-}" = --version ] '
                          '&& echo "QEMU emulator version 8.2.0 (stub)"\nexit 0\n', executable=True)
        for name in ("scripts/run-qemu-integrated.sh", "kas/egw-qemuarm64-integrated.yml",
                     "kas/egw-qemuarm64-integrated.lock.yml"):
            _write(checkout / "src" / "yocto" / name, f"# stub {name}\n")

    # -- environment ------------------------------------------------------
    def env(self, **overrides) -> dict:
        environment = dict(os.environ)
        environment.update({
            "HOME": str(self.home),
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "EGW_EXEC_REPO": str(REPO_ROOT),
            "EGW_EXEC": str(self.exec_dir),
            "EGW_EXEC_VENV": str(self.exec_dir / "venv"),
            "EGW_ATTEMPTS": str(self.attempts),
            "EGW_OUTPUT_TEST": str(self.out),
            "EGW_SECRETS_ENV": str(self.home / "egw-tcg" / ".env"),
            "EGW_STUB_BIN": str(self.bin),
            "EGW_STUB_GUEST_BIN": str(self.guest_bin),
            "EGW_STUB_GUEST_ROOT": str(self.guest_root),
            "EGW_STUB_LOG": str(self.log),
            "EGW_YOCTO_CHECKOUT": str(self.tmp / "yocto"),
            "EGW_DATA_DISK": str(self.tmp / "yocto" / "egw-data.img"),
            "EGW_IMAGES_DIR": str(self.images),
        })
        environment.update(self.extra)
        for key, value in overrides.items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = str(value)
        return environment

    # -- the session the drivers attach to --------------------------------
    def open_session(self) -> Path:
        """A guest session attempt, still running, as the drivers expect."""
        session = Path(self.local_export(
            "new", "--attempts-root", str(self.attempts), "--scenario", "guest session",
            "--purpose", "engineering", "--dest-root", str(self.out)).strip())
        _write(session / "scripts" / "session_common.sh", SESSION_COMMON)
        _write(session / "scripts" / "session_close.sh", SESSION_CLOSE_STUB, executable=True)
        (self.exec_dir / "current_session").write_text(f"{session}\n", encoding="utf-8")
        return session

    def local_export(self, *args: str) -> str:
        result = subprocess.run([sys.executable, "-m", "egw_experiments.local_export", *args],
                                cwd=REPO_ROOT / "src", env=self.env(), capture_output=True,
                                text=True, timeout=300)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    # -- running a driver -------------------------------------------------
    def run(self, driver: str, *args: str, timeout: int = 600, **overrides) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(self.drivers / driver), *args], env=self.env(**overrides),
                              capture_output=True, text=True, timeout=timeout)

    def python_stub(self, text: str, **extra: str) -> dict:
        """Put a stub of the interpreter at $PY and return the environment it
        needs; every call it does not intercept is this interpreter."""
        _write(self.exec_dir / "venv" / "bin" / "python", text, executable=True)
        return {"EGW_REAL_PYTHON": sys.executable, **extra}

    def fail_capture_of(self, step: str) -> dict:
        """Make the mandatory console capture of one step fail (interface 1)."""
        return self.python_stub(PY_CAPTURE_FAIL, EGW_FAIL_CAPTURE_OF=step)

    def fail_set_of(self, field: str) -> dict:
        """Make the `local_export set` that records one field fail."""
        return self.python_stub(PY_SET_FIELD_FAILS, EGW_FAIL_SET_FIELD=field)

    # -- reading what a driver left ---------------------------------------
    def attempt(self, slug: str) -> Path:
        found = sorted(p for p in self.attempts.iterdir() if f"_{slug}_attempt" in p.name)
        assert found, f"no attempt for {slug} under {self.attempts}"
        return found[-1]

    def verdicts(self, slug: str) -> dict:
        return json.loads((self.attempt(slug) / "attempt.json").read_text(encoding="utf-8"))

    def package(self, slug: str) -> Path | None:
        run_id = self.verdicts(slug)["run_id"]
        for candidate in (self.out / "runs").glob(f"*/{run_id}"):
            return candidate
        return None

    def commands(self, slug: str) -> list[str]:
        path = self.attempt(slug) / "commands.jsonl"
        return [json.loads(line)["name"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def bench(tmp_path: Path) -> Bench:
    return Bench(tmp_path)


def report(result: subprocess.CompletedProcess) -> str:
    return f"exit={result.returncode}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"


# --------------------------------------------------------------------------
# driver_status.py: the one place the table is applied
# --------------------------------------------------------------------------

STATUS_CASES = [
    ({"status": "finished", "instrumentation_validity": "valid", "system_outcome": "pass"},
     "exported", "0", 0),
    ({"status": "finished", "instrumentation_validity": "valid", "system_outcome": "fail"},
     "exported", "0", 1),
    ({"status": "failed", "instrumentation_validity": "invalid", "system_outcome": "not-run"},
     "exported", "0", 2),
    ({"status": "failed", "instrumentation_validity": "invalid", "system_outcome": "inconclusive"},
     "exported", "0", 3),
    ({"status": "finished", "instrumentation_validity": "valid", "system_outcome": "unknown"},
     "exported", "0", 3),
    # A capture failure downgrades a run that otherwise looks complete.
    ({"status": "finished", "instrumentation_validity": "valid", "system_outcome": "pass",
      "capture_failures": [{"seq": 3, "name": "harness-run", "stream": "stdout",
                            "error": "[Errno 28] No space left on device",
                            "bytes_received": 4096, "bytes_kept": 512}]}, "exported", "0", 3),
    # The export outranks everything, the interruption outranks the stop.
    ({"status": "finished", "instrumentation_validity": "valid", "system_outcome": "pass"},
     "failed", "0", 4),
    ({"status": "interrupted", "instrumentation_validity": "invalid", "system_outcome": "interrupted"},
     "failed", "1", 4),
    ({"status": "interrupted", "instrumentation_validity": "unknown", "system_outcome": "interrupted"},
     "exported", "1", 130),
    ({"status": "failed", "instrumentation_validity": "not-applicable", "system_outcome": "fail"},
     "exported", "1", 5),
    # The same verdicts with a controlled stop that did NOT fail: a session
    # whose own records showed the system failing is a valid negative result,
    # so 'valid' (or 'not-applicable') plus 'fail' gives 1 for every driver.
    ({"status": "failed", "instrumentation_validity": "not-applicable", "system_outcome": "fail"},
     "exported", "0", 1),
    # The open guest session: nothing is exported, and that is not a failure.
    ({"status": "running", "instrumentation_validity": "unknown", "system_outcome": "unknown"},
     "deferred", "0", 0),
    ({"status": "running", "instrumentation_validity": "invalid", "system_outcome": "unknown"},
     "deferred", "0", 3),
]


def _attempt_with_receipt(tmp_path: Path, attempt: dict, package_state="verified") -> Path:
    """An ``attempt.json`` and, beside it, the ``export/receipt.json`` every
    export writes. ``package_state=None`` is a receipt that was never written."""
    path = tmp_path / "attempt.json"
    path.write_text(json.dumps({"run_id": "20260919T200000Z_stub_attempt01", **attempt}),
                    encoding="utf-8")
    if package_state is not None:
        _write(tmp_path / "export" / "receipt.json",
               json.dumps({"state": "complete", "package_state": package_state,
                           "package": str(tmp_path / "package")}))
    return path


@pytest.mark.parametrize("attempt, export_result, stop_failed, expected", STATUS_CASES)
def test_driver_status_applies_the_table(tmp_path, attempt, export_result, stop_failed, expected):
    path = _attempt_with_receipt(tmp_path, attempt)
    result = subprocess.run([sys.executable, str(SESSION_DIR / "driver_status.py"),
                             str(path), export_result, stop_failed], capture_output=True, text=True)
    assert result.returncode == expected, report(result)
    assert f"exit={expected}" in result.stdout
    assert "20260919T200000Z_stub_attempt01" in result.stdout
    for key in ("status=", "instrumentation_validity=", "system_outcome="):
        assert key in result.stdout


@pytest.mark.parametrize("attempt, expected", [
    ({"status": "running", "instrumentation_validity": "unknown", "system_outcome": "unknown"}, 0),
    ({"status": "running", "instrumentation_validity": "invalid", "system_outcome": "unknown"}, 3),
])
def test_driver_status_names_a_deferred_attempt_as_open(tmp_path, attempt, expected):
    # A deferred attempt has recorded no outcome and holds no package, so its
    # line must not carry the words of a finished, exported run.
    path = tmp_path / "attempt.json"
    path.write_text(json.dumps({"run_id": "20260919T200000Z_stub_attempt01", **attempt}),
                    encoding="utf-8")
    result = subprocess.run([sys.executable, str(SESSION_DIR / "driver_status.py"),
                             str(path), "deferred", "0"], capture_output=True, text=True)
    assert result.returncode == expected, report(result)
    assert "the guest session stays OPEN and is exported by guest_session_close.sh" in result.stdout
    assert "export=deferred" in result.stdout
    for claim in ("system outcome pass", "package exported and verified"):
        assert claim not in result.stdout, claim


def test_driver_status_fails_closed_on_an_unreadable_attempt(tmp_path):
    result = subprocess.run([sys.executable, str(SESSION_DIR / "driver_status.py"),
                             str(tmp_path / "missing.json"), "exported", "0"],
                            capture_output=True, text=True)
    assert result.returncode == 3, report(result)
    assert "exit=3" in result.stdout


# The export tool exits 0 for a package it sealed WITHOUT part of what the
# attempt registered, and says so in the one field of export/receipt.json that
# names the package. A driver must not call that "exported and verified".
PACKAGE_PASS = {"status": "finished", "instrumentation_validity": "valid", "system_outcome": "pass"}
PACKAGE_FAIL = {"status": "failed", "instrumentation_validity": "valid", "system_outcome": "fail"}


@pytest.mark.parametrize("attempt, package_state, expected, says", [
    (PACKAGE_PASS, "verified", 0, "package exported and verified"),
    # A registered source root the export refused to read through a link.
    (PACKAGE_PASS, "verified; incomplete: 1 registered source root(s), 0 registered artefact(s) "
                   "below one and 0 declared expected artefact(s) are NOT in this package",
     3, "registered source root(s)"),
    # The package is in output_test and the record does not name it.
    (PACKAGE_PASS, "verified; not named in the destination's index: LATEST_SUMMARY.md could not "
                   "be written", 3, "not named in the destination's index"),
    # A valid negative result is not lowered either: 3 outranks 1.
    (PACKAGE_FAIL, "verified; incomplete: 2 declared expected artefact(s) are NOT in this package",
     3, "declared expected artefact(s)"),
    # A receipt that cannot be read leaves the package's state unknown.
    (PACKAGE_PASS, None, 3, "does not say what the export left in the destination"),
])
def test_driver_status_refuses_a_package_that_is_not_verified(tmp_path, attempt, package_state,
                                                              expected, says):
    path = _attempt_with_receipt(tmp_path, attempt, package_state)
    result = subprocess.run([sys.executable, str(SESSION_DIR / "driver_status.py"),
                             str(path), "exported", "0"], capture_output=True, text=True)
    assert result.returncode == expected, report(result)
    assert f"exit={expected}" in result.stdout
    assert says in result.stdout
    if expected != 0:
        assert "package=INCOMPLETE" in result.stdout
        for claim in ("package exported and verified", "exit=0", "exit=1"):
            assert claim not in result.stdout, claim


def test_driver_status_reads_no_receipt_for_an_attempt_that_stays_open(tmp_path):
    # A deferred attempt has no package at all, and a failed export is already
    # the most serious code there is: neither is judged on a receipt.
    path = _attempt_with_receipt(tmp_path, {"status": "running", "instrumentation_validity":
                                            "unknown", "system_outcome": "unknown"},
                                 package_state=None)
    deferred = subprocess.run([sys.executable, str(SESSION_DIR / "driver_status.py"),
                               str(path), "deferred", "0"], capture_output=True, text=True)
    assert deferred.returncode == 0, report(deferred)
    assert "package=INCOMPLETE" not in deferred.stdout
    failed = subprocess.run([sys.executable, str(SESSION_DIR / "driver_status.py"),
                             str(_attempt_with_receipt(tmp_path, PACKAGE_PASS, package_state=None)),
                             "failed", "0"], capture_output=True, text=True)
    assert failed.returncode == 4, report(failed)


# --------------------------------------------------------------------------
# deployed_vs_clone.py: every difference is a problem
# --------------------------------------------------------------------------

def _listing(tmp_path: Path, tree: Path, extra: str = "") -> Path:
    lines = []
    for path in sorted(tree.rglob("*")):
        if path.is_file():
            digest = subprocess.run(["sha256sum", str(path)], capture_output=True, text=True).stdout.split()[0]
            lines.append(f"{digest}  ./{path.relative_to(tree).as_posix()}")
    path = tmp_path / "listing.txt"
    path.write_text("\n".join(lines) + "\n" + extra, encoding="utf-8")
    return path


# The exclusions preflight.sh lists the deployed tree with, and passes on.
EXCLUSIONS = ("--exclude", "data/*", "--exclude", ".env", "--exclude", "passwd",
              "--exclude", "mosquitto/config/certs/*", "--")


def _compare(listing: Path, tree: Path, *allowed: str,
             options: tuple = ()) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SESSION_DIR / "deployed_vs_clone.py"), *options,
                           str(listing), str(tree), *allowed], capture_output=True, text=True)


def test_deployed_vs_clone_accepts_an_identical_tree(tmp_path):
    tree = REPO_ROOT / "src" / "deployment"
    result = _compare(_listing(tmp_path, tree), tree)
    assert result.returncode == 0, report(result)
    assert "different: 0" in result.stdout


def test_deployed_vs_clone_reports_a_changed_file(tmp_path):
    clone = tmp_path / "clone"
    shutil.copytree(REPO_ROOT / "src" / "deployment", clone)
    listing = _listing(tmp_path, clone)
    (clone / "compose.yaml").write_text("changed on the clone side\n", encoding="utf-8")
    result = _compare(listing, clone)
    assert result.returncode == 1, report(result)
    assert "DIFFERS        compose.yaml" in result.stdout


def test_deployed_vs_clone_allows_only_the_named_paths(tmp_path):
    clone = tmp_path / "clone"
    shutil.copytree(REPO_ROOT / "src" / "deployment", clone)
    listing = _listing(tmp_path, clone)
    (clone / "README.md").write_text("the guest keeps an older README\n", encoding="utf-8")
    assert _compare(listing, clone, "README.md").returncode == 0
    assert "(allowed)" in _compare(listing, clone, "README.md").stdout
    assert _compare(listing, clone).returncode == 1


def test_deployed_vs_clone_reports_a_file_only_on_the_guest(tmp_path):
    clone = tmp_path / "clone"
    shutil.copytree(REPO_ROOT / "src" / "deployment", clone)
    listing = _listing(tmp_path, clone, extra=f"{'0' * 64}  ./scripts/extra-on-guest.sh\n")
    result = _compare(listing, clone)
    assert result.returncode == 1, report(result)
    assert "ONLY ON GUEST  scripts/extra-on-guest.sh" in result.stdout


def test_deployed_vs_clone_reports_a_file_only_in_the_clone(tmp_path):
    # A deployed file the guest has LOST is as much a difference as a changed
    # one: the listing simply has no line for it.
    clone = tmp_path / "clone"
    shutil.copytree(REPO_ROOT / "src" / "deployment", clone)
    listing = _listing(tmp_path, clone)
    kept = [line for line in listing.read_text(encoding="utf-8").splitlines()
            if not line.endswith("./scripts/collect-resources.sh")]
    listing.write_text("\n".join(kept) + "\n", encoding="utf-8")
    result = _compare(listing, clone)
    assert result.returncode == 1, report(result)
    assert "ONLY IN CLONE  scripts/collect-resources.sh" in result.stdout
    assert "only in the clone: 1" in result.stdout


def test_deployed_vs_clone_honours_the_callers_exclusions(tmp_path):
    # The paths the caller never listed on the guest (secrets, data, certs) are
    # not lost files; without the exclusions they would all be reported.
    clone = tmp_path / "clone"
    shutil.copytree(REPO_ROOT / "src" / "deployment", clone)
    _write(clone / ".env", "MOSQUITTO_SIMULATOR_PASSWORD=secret\n")
    _write(clone / "data" / "events" / "kept.jsonl", "{}\n")
    listing = _listing(tmp_path, clone)
    kept = [line for line in listing.read_text(encoding="utf-8").splitlines()
            if not (line.endswith("./.env") or "  ./data/" in line or "/certs/" in line)]
    listing.write_text("\n".join(kept) + "\n", encoding="utf-8")
    assert _compare(listing, clone, options=EXCLUSIONS).returncode == 0
    without = _compare(listing, clone)
    assert without.returncode == 1, report(without)
    assert "ONLY IN CLONE  .env" in without.stdout


def test_deployed_vs_clone_refuses_an_unknown_option(tmp_path):
    listing = _listing(tmp_path, REPO_ROOT / "src" / "deployment")
    result = _compare(listing, REPO_ROOT / "src" / "deployment", options=("--only-guest",))
    assert result.returncode == 1, report(result)
    assert "UNKNOWN OPTION" in result.stderr


def test_deployed_vs_clone_fails_closed_on_an_unusable_listing(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    result = _compare(empty, REPO_ROOT / "src" / "deployment")
    assert result.returncode == 1, report(result)
    assert "NOTHING COMPARED" in result.stdout
    malformed = tmp_path / "malformed.txt"
    malformed.write_text("not a sha256 line\n", encoding="utf-8")
    assert _compare(malformed, REPO_ROOT / "src" / "deployment").returncode == 1


# --------------------------------------------------------------------------
# junit_one_failure.py: the deliberate failure is judged on what it produced
# --------------------------------------------------------------------------

JUNIT_ONE_FAILURE = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="1" failures="1">
<testcase classname="t" name="test_this_fails_on_purpose"><failure>assert 2 == 3</failure></testcase>
</testsuite></testsuites>
"""
JUNIT_NO_TEST = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="0" errors="1"/></testsuites>
"""
JUNIT_TWO = JUNIT_ONE_FAILURE.replace("</testsuite>", """<testcase classname="t" name="another"/>
</testsuite>""")
JUNIT_PASSED = JUNIT_ONE_FAILURE.replace("<failure>assert 2 == 3</failure>", "")
JUNIT_ERROR = JUNIT_ONE_FAILURE.replace("<failure>", "<error>").replace("</failure>", "</error>")


@pytest.mark.parametrize("report_xml, expected, says", [
    (JUNIT_ONE_FAILURE, 0, "exactly one test case"),
    (JUNIT_NO_TEST, 1, "0 test case(s)"),
    (JUNIT_TWO, 1, "2 test case(s)"),
    (JUNIT_PASSED, 1, "it passed"),
    (JUNIT_ERROR, 1, "error"),
    ("not xml at all", 1, "could not be read"),
])
def test_junit_one_failure_judges_the_report(tmp_path, report_xml, expected, says):
    path = _write(tmp_path / "junit.xml", report_xml)
    result = subprocess.run([sys.executable, str(SESSION_DIR / "junit_one_failure.py"), str(path)],
                            capture_output=True, text=True)
    assert result.returncode == expected, report(result)
    assert says in result.stdout


def test_junit_one_failure_fails_closed_on_a_missing_report(tmp_path):
    result = subprocess.run([sys.executable, str(SESSION_DIR / "junit_one_failure.py"),
                             str(tmp_path / "never-written.xml")], capture_output=True, text=True)
    assert result.returncode == 1, report(result)


# --------------------------------------------------------------------------
# collector_shortfall.py: the duration the collector was asked for
# --------------------------------------------------------------------------

def _shortfall(tmp_path: Path, report_json) -> subprocess.CompletedProcess:
    path = tmp_path / "collector-check.json"
    path.write_text(report_json if isinstance(report_json, str) else json.dumps(report_json),
                    encoding="utf-8")
    return subprocess.run([sys.executable, str(SESSION_DIR / "collector_shortfall.py"), str(path)],
                          capture_output=True, text=True)


# The report collector_check.py writes for a 45 s collection asked of the guest.
def _check_report(window=45.0, duration=45.0, interval=1.0):
    shortfall = duration - window if duration is not None and window < duration else None
    return {"declared_duration_s": duration, "declared_interval_s": interval,
            "window_seconds": window, "declared_duration_shortfall_s": shortfall}


@pytest.mark.parametrize("report_json, expected, says", [
    (_check_report(), 0, "held its whole window"),
    # The stop hook reached the collector inside the round it was in.
    (_check_report(window=44.0), 0, "within the 1 s tolerated for the interval=1s round"),
    # A collector that died at two thirds of the duration it declares: the
    # check validated it against its own 31 s window, so only this says so.
    (_check_report(window=31.0), 1, "stopped 14 s before the duration=45s its 'start:' line declares"),
    # No usable interval: one second stands for the round it was in.
    (_check_report(window=43.0, interval=0.0), 1, "stopped 2 s before"),
    # The interval is read from the same 'start:' line as the duration, so a
    # collector declaring a long one must not be able to make its own tolerance
    # swallow half the collection: one round, bounded to a part of the duration.
    (_check_report(window=300.0, duration=600.0, interval=600.0), 1,
     "stopped 300 s before the duration=600s"),
    # Fail closed: nothing to judge is not "it reached its duration".
    (_check_report(duration=None), 1, "names no duration"),
    ({"problems": []}, 1, "does not carry 'declared_duration_shortfall_s'"),
    ("not json at all", 1, "could not be read"),
])
def test_collector_shortfall_judges_the_duration_the_collector_declares(tmp_path, report_json,
                                                                        expected, says):
    result = _shortfall(tmp_path, report_json)
    assert result.returncode == expected, report(result)
    assert says in result.stdout


def test_readme_says_the_shortfall_is_judged_against_the_declared_duration():
    # What the helper compares is the collector's own account of itself: the
    # window it held against the `duration=` its own `start:` line declares.
    # The `--duration` the driver passed is compared with nothing, and the
    # README must say what the code does, not the other way round.
    readme = " ".join((SESSION_DIR / "README.md").read_text(encoding="utf-8").split())
    assert "the collector's own window against the `duration=` its own `start:` line declares" in readme
    assert "the collector's own window against the `--duration` it was started with" not in readme
    assert "the `--duration 45` the driver passed is not compared with the declaration" in readme


def test_collector_shortfall_fails_closed_on_a_missing_report(tmp_path):
    result = subprocess.run([sys.executable, str(SESSION_DIR / "collector_shortfall.py"),
                             str(tmp_path / "never-written.json")], capture_output=True, text=True)
    assert result.returncode == 1, report(result)
    assert "UNKNOWN" in result.stdout


# --------------------------------------------------------------------------
# guest_state_delta.py: what the system did, and what the records cannot say
# --------------------------------------------------------------------------

FIRST_ID = "a" * 64
OTHER_ID = "0" * 64
BOOT_START = "2026-09-19T19:58:00.100000000Z"
LATER_START = "2026-09-19T20:31:07.100000000Z"


def _guest_state(restarts: str = "0", oomkilled: str = "false", oom_lines: str = "0",
                 names=("egw-controller-1", "egw-mongodb-1"), ident: str = FIRST_ID,
                 started: str = BOOT_START, fields: bool = True) -> str:
    """One guest-state record. `ident` and `started` are the first container's
    own id and the instant it last started, which the driver records so that a
    replaced container object and one restarted IN PLACE can both be seen;
    `fields=False` is a record written without them."""
    lines = ["egw-controller-1 Up 3 minutes (healthy)"]
    for name in names:
        kill = oomkilled if name == names[0] else "false"
        count = restarts if name == names[0] else "0"
        own = ident if name == names[0] else OTHER_ID
        when = started if name == names[0] else BOOT_START
        line = f"container {name} oomkilled={kill} restarts={count}"
        lines.append(line + (f" id={own} started={when}" if fields else ""))
    lines.append(f"memory-cgroup OOM lines: {oom_lines}")
    return "\n".join(lines) + "\n"


def _delta(tmp_path: Path, before: str, after: str, *options: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SESSION_DIR / "guest_state_delta.py"), *options,
                           str(_write(tmp_path / "before.txt", before)),
                           str(_write(tmp_path / "after.txt", after))],
                          capture_output=True, text=True)


def _group(stdout: str, group: str) -> str:
    """What the comparison printed under one of its two headings."""
    faults, _, problems = stdout.partition("## problems")
    return problems if group == "problems" else faults


def test_guest_state_delta_accepts_an_unchanged_guest(tmp_path):
    result = _delta(tmp_path, _guest_state(), _guest_state())
    assert result.returncode == 0, report(result)
    assert "0 fault(s), 0 problem(s)" in result.stdout
    assert "guest-state-delta: faults=0 problems=0" in result.stdout


@pytest.mark.parametrize("before, after, says", [
    (_guest_state(), _guest_state(oomkilled="true"), "was OOM-killed"),
    (_guest_state(restarts="0"), _guest_state(restarts="3"), "restarted during the run (0 -> 3)"),
    (_guest_state(oom_lines="0"), _guest_state(oom_lines="2"), "memory-cgroup OOM lines"),
    (_guest_state(), _guest_state()
     + f"container new-1 oomkilled=false restarts=0 id={'d' * 64} started={BOOT_START}\n",
     "no restart baseline"),
    # The other direction and the other sense: what the 'after' record alone
    # cannot show, because OOMKilled and RestartCount belong to the container
    # OBJECT and a recreated object starts again at false and 0.
    (_guest_state(), _guest_state(names=("egw-mongodb-1",)),
     "egw-controller-1 was running before the run and is not listed after it"),
    (_guest_state(restarts="3"), _guest_state(restarts="0"),
     "was replaced during the run: the restart count went 3 -> 0"),
    (_guest_state(restarts="3", ident="a" * 64), _guest_state(restarts="0", ident="c" * 64),
     "was replaced during the run: the container id changed"),
    # A container restarted IN PLACE ('docker restart', 'compose restart')
    # keeps its object and its RestartCount, which Docker increments from the
    # restart POLICY: the instant it started again is the only thing that moves.
    (_guest_state(), _guest_state(started=LATER_START),
     f"was restarted during the run: it started again at {LATER_START}"),
    (_guest_state(oomkilled="true"), _guest_state(),
     "was OOM-killed before the run and is not after it"),
])
def test_guest_state_delta_reports_what_the_system_did(tmp_path, before, after, says):
    # A fault the pair SHOWS is a result, not a broken comparison: it ends 1,
    # which nominal.sh reads as a system outcome and not as invalid evidence.
    result = _delta(tmp_path, before, after)
    assert result.returncode == 1, report(result)
    assert says in _group(result.stdout, "faults"), result.stdout
    assert "PROBLEM:" not in result.stdout, "nothing here leaves the pair uncomparable"


@pytest.mark.parametrize("before, after, says", [
    (_guest_state(), "nothing was recorded\n", "names no container"),
    (_guest_state(), _guest_state(oom_lines="many"), "no readable memory-cgroup OOM count"),
    # Without the id and the start instant, or with them 'unknown', neither a
    # replacement nor a restart in place can be seen: the pair must not read as
    # unchanged, and it must not read as a run in which nothing happened either.
    (_guest_state(fields=False), _guest_state(fields=False),
     "does not name the id of egw-controller-1"),
    (_guest_state(ident="unknown"), _guest_state(ident="unknown"),
     "does not name the id of egw-controller-1 (unknown)"),
    (_guest_state(started="unknown"), _guest_state(started="unknown"),
     "does not name the started of egw-controller-1 (unknown)"),
    # Two lines for one container: the last one used to win, so a record
    # naming it OOM-killed first could be overwritten by a later line.
    (_guest_state(), _guest_state(oomkilled="true")
     + f"container egw-controller-1 oomkilled=false restarts=0 id={FIRST_ID} started={BOOT_START}\n",
     "names egw-controller-1 more than once"),
    (_guest_state(), "egw-controller-1 Up 3 minutes (healthy)\n"
     "container egw-controller-1 oomkilled= restarts=\n"
     "container egw-mongodb-1 oomkilled=false restarts=0\nmemory-cgroup OOM lines: 0\n",
     "holds a container line that cannot be read (egw-controller-1)"),
    (_guest_state(oom_lines="2"), _guest_state(oom_lines="0"),
     "the record of this boot is not consistent"),
])
def test_guest_state_delta_reports_what_the_records_cannot_say(tmp_path, before, after, says):
    # A pair that cannot be compared ends 2: no measurement of the guest's
    # state was made, which is never "no fault was observed".
    result = _delta(tmp_path, before, after)
    assert result.returncode == 2, report(result)
    assert says in _group(result.stdout, "problems"), result.stdout


@pytest.mark.parametrize("after, says", [
    (_guest_state(started="unknown"), "does not name the started of egw-controller-1"),
    (_guest_state(ident="unknown"), "does not name the id of egw-controller-1"),
])
def test_guest_state_delta_reads_no_fault_out_of_a_field_it_could_not_read(tmp_path, after, says):
    # 'docker inspect' answered nothing after the run, so the record carries
    # the word 'unknown' where the id or the instant it last started belongs.
    # That is what the records do not let anyone say - never an instant that
    # differs from the one before, which would be a restart or a replacement
    # the run never showed. An indeterminate reading is not an observation.
    result = _delta(tmp_path, _guest_state(), after)
    assert result.returncode == 2, report(result)
    assert says in _group(result.stdout, "problems"), result.stdout
    assert "FAULT:" not in result.stdout, "nothing was observed here"
    assert "guest-state-delta: faults=0" in result.stdout


def test_guest_state_delta_prints_a_fault_it_saw_even_when_it_cannot_compare(tmp_path):
    # An unreadable OOM count does not take away the OOM kill the pair showed:
    # the fault is a fact, and it is printed beside the problem.
    result = _delta(tmp_path, _guest_state(), _guest_state(oomkilled="true", oom_lines="many"))
    assert result.returncode == 2, report(result)
    assert "FAULT: egw-controller-1 was OOM-killed (OOMKilled=true)" in result.stdout
    assert "guest-state-delta: faults=1 problems=2" in result.stdout


def test_guest_state_delta_wants_every_expected_container(tmp_path):
    # A record that holds fewer containers than the caller expects leaves the
    # state of the missing ones unknown, which is not "nothing happened". In
    # the 'before' record that is a problem; in the 'after' record it is the
    # fault that the container is gone.
    expected = "--expect", "egw-controller-1,egw-mongodb-1"
    assert _delta(tmp_path, _guest_state(), _guest_state(), *expected).returncode == 0
    result = _delta(tmp_path, _guest_state(names=("egw-controller-1",)),
                    _guest_state(names=("egw-controller-1",)), *expected)
    assert result.returncode == 2, report(result)
    assert "names 1 of the 2 expected containers (missing: egw-mongodb-1)" in result.stdout
    assert result.stdout.count("expected containers") == 2, "both records are checked"
    assert "FAULT: the guest state after the run names 1 of the 2" in result.stdout
    assert "PROBLEM: the guest state before the run names 1 of the 2" in result.stdout
    # One record that names them all and one that does not: the container is
    # gone, and that is a fault on its own, with nothing left uncomparable.
    gone = _delta(tmp_path, _guest_state(), _guest_state(names=("egw-controller-1",)), *expected)
    assert gone.returncode == 1, report(gone)
    assert "guest-state-delta: faults=2 problems=0" in gone.stdout


def test_guest_state_delta_missing_baseline_is_not_also_a_fault(tmp_path):
    # The BEFORE record does not name a container the caller expects, and the
    # AFTER record does. That is one gap in the baseline - the record does not
    # say what that container's state was when the run started - and it must
    # not ALSO be written down as something positively observed about it, which
    # would turn a record that does not say into a fact about the system.
    expected = "--expect", "egw-controller-1,egw-mongodb-1"
    result = _delta(tmp_path, _guest_state(names=("egw-controller-1",)), _guest_state(), *expected)
    assert result.returncode == 2, report(result)
    problems = _group(result.stdout, "problems")
    assert ("the guest state before the run names 1 of the 2 expected containers "
            "(missing: egw-mongodb-1)") in problems
    assert "egw-mongodb-1 is not named in the guest state before the run" in problems
    assert "FAULT:" not in result.stdout, result.stdout
    assert "guest-state-delta: faults=0 problems=2" in result.stdout
    # A container nobody expected, which only the AFTER record names, is one
    # that appeared during the run: that is still a fault the pair showed.
    new = _delta(tmp_path, _guest_state(), _guest_state()
                 + f"container new-1 oomkilled=false restarts=0 id={'d' * 64} started={BOOT_START}\n",
                 *expected)
    assert new.returncode == 1, report(new)
    assert "FAULT: new-1 was not running before the run" in new.stdout
    assert "guest-state-delta: faults=1 problems=0" in new.stdout


#: The helper run as its own script, with the reading of a record made to fail
#: in a way that is NOT an OSError - as a defect in the comparison, or an
#: interpreter that cannot go on, would: the status Python leaves for an
#: unhandled exception is 1, which is the status of a fault the pair SHOWED.
CRASHING_COMPARISON = '''"""guest_state_delta.py as __main__, with a record it cannot open at all."""
import builtins
import sys
import traceback  # noqa: F401 - imported before the patch below, so it stays usable

script, arguments = sys.argv[1], sys.argv[2:]
source = builtins.open(script, encoding="utf-8").read()
real = builtins.open


def guarded(file, *positional, **named):
    if str(file).endswith(".txt"):
        raise ValueError("the record could not be opened at all")
    return real(file, *positional, **named)


builtins.open = guarded
sys.argv = [script, *arguments]
exec(compile(source, script, "exec"), {"__name__": "__main__", "__file__": script})
'''


def test_guest_state_delta_that_crashed_is_not_a_fault_it_saw(tmp_path):
    # A crash of the comparison is a pair that was NOT COMPARED (2), never the
    # 1 of a fault it observed: a caller reading that 1 would record a system
    # fault nobody saw and hide the evidence failure behind it.
    record = _write(tmp_path / "before.txt", _guest_state())
    result = subprocess.run([sys.executable, str(_write(tmp_path / "crash.py", CRASHING_COMPARISON)),
                             str(SESSION_DIR / "guest_state_delta.py"), str(record), str(record)],
                            capture_output=True, text=True)
    assert result.returncode == 2, report(result)
    assert "the comparison itself failed (ValueError:" in result.stdout
    assert "FAULT:" not in result.stdout, "nothing was compared, so nothing was observed"
    # Every exit carries the summary line, which is what tells a status this
    # helper reached from one Python left behind after it.
    assert result.stdout.rstrip().endswith("guest-state-delta: faults=0 problems=1")


def test_guest_state_delta_invents_no_fault_out_of_a_record_it_could_not_read(tmp_path):
    # The record of the guest state after the run could not be read at all. A
    # record nobody read shows nothing: it is not every expected container
    # "gone after the run", which would be six positively observed faults out
    # of an evidence failure.
    expected = "--expect", "egw-controller-1,egw-mongodb-1"
    result = subprocess.run([sys.executable, str(SESSION_DIR / "guest_state_delta.py"), *expected,
                             str(_write(tmp_path / "before.txt", _guest_state())),
                             str(tmp_path / "absent.txt")], capture_output=True, text=True)
    assert result.returncode == 2, report(result)
    assert "FAULT:" not in result.stdout, "a record nobody could read observed nothing"
    assert "guest-state-delta: faults=0" in result.stdout
    assert "the guest state after the run could not be read" in result.stdout
    assert "no container of the pair could be compared" in result.stdout


def test_guest_state_delta_invents_no_fault_out_of_an_empty_record(tmp_path):
    # The same for a record the guest command left empty: the containers the
    # 'before' record names are not reported gone out of it.
    result = _delta(tmp_path, _guest_state(), "", "--expect", "egw-controller-1,egw-mongodb-1")
    assert result.returncode == 2, report(result)
    assert "FAULT:" not in result.stdout, result.stdout
    assert "guest-state-delta: faults=0" in result.stdout
    assert "the guest state after the run names no container" in result.stdout
    assert "PROBLEM: the guest state after the run names 0 of the 2 expected containers" in result.stdout


def test_guest_state_delta_refuses_an_unknown_option(tmp_path):
    result = _delta(tmp_path, _guest_state(), _guest_state(), "--all")
    assert result.returncode == 2, report(result)
    assert "UNKNOWN OPTION --all" in result.stderr


def test_guest_state_delta_fails_closed_on_a_missing_record(tmp_path):
    result = subprocess.run([sys.executable, str(SESSION_DIR / "guest_state_delta.py"),
                             str(tmp_path / "absent.txt"), str(tmp_path / "absent.txt")],
                            capture_output=True, text=True)
    assert result.returncode == 2, report(result)
    assert "could not be read" in result.stdout


# --------------------------------------------------------------------------
# driver_status.py --stop: the final line of a driver with no attempt
# --------------------------------------------------------------------------

def test_driver_status_stop_prints_the_contracted_line():
    result = subprocess.run([sys.executable, str(SESSION_DIR / "driver_status.py"),
                             "--stop", "2", "no open session"], capture_output=True, text=True)
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2 (a prerequisite failed" in result.stdout
    for key in ("status=no-attempt", "instrumentation_validity=unknown",
                "system_outcome=unknown", "export=none", "no open session"):
        assert key in result.stdout


def test_driver_status_stop_refuses_a_code_outside_the_table():
    result = subprocess.run([sys.executable, str(SESSION_DIR / "driver_status.py"),
                             "--stop", "9", "made up"], capture_output=True, text=True)
    assert result.returncode == 3, report(result)


# --------------------------------------------------------------------------
# repo_identity: the identity of the clean clone, or nothing
# --------------------------------------------------------------------------

def _identity(bench: Bench, **overrides) -> subprocess.CompletedProcess:
    """repo_identity as the drivers call it (sourced from the driver folder)."""
    return subprocess.run(["bash", "-c", 'cd "$1" && . ./common.sh && repo_identity', "_",
                           str(bench.drivers)], env=bench.env(**overrides),
                          capture_output=True, text=True)


def test_repo_identity_names_the_commit_and_the_driver_files(bench):
    result = _identity(bench)
    assert result.returncode == 0, report(result)
    identity = json.loads(result.stdout)
    assert identity["repo_commit"] and identity["repo_dirty_lines"] == 0
    assert "identity_error" not in identity
    # Every file the drivers are made of is hashed, not only the shell ones.
    before = identity["drivers_sha256"]
    for changed in ("driver_status.py", "guest/gssh.sh", "common.sh"):
        path = bench.drivers / changed
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "\n# a driver file that changed\n", encoding="utf-8")
        assert json.loads(_identity(bench).stdout)["drivers_sha256"] != before, changed
        path.write_text(original, encoding="utf-8")
    assert json.loads(_identity(bench).stdout)["drivers_sha256"] == before


def test_repo_identity_fails_when_git_cannot_read_the_clone(bench):
    result = _identity(bench, EGW_STUB_FAIL="git")
    assert result.returncode == 1, report(result)
    identity = json.loads(result.stdout)
    assert identity["repo_commit"] is None, "an unread commit is never an empty string"
    assert identity["repo_dirty_lines"] is None, "an unread clone is never 'clean'"
    assert "git rev-parse" in identity["identity_error"]


# --------------------------------------------------------------------------
# The drivers
# --------------------------------------------------------------------------

def test_preflight_passes_and_exports(bench):
    result = bench.run("preflight.sh")
    assert result.returncode == 0, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert (verdicts["status"], verdicts["instrumentation_validity"], verdicts["system_outcome"]) == (
        "finished", "valid", "pass")
    package = bench.package("live-preflight")
    assert package is not None and (package / "SHA256SUMS").is_file()
    assert "DRIVER RESULT" in result.stdout and "exit=0" in result.stdout
    # The fetch went through the repository helper, which verified every file.
    assert "fetch: result exit=0" in result.stdout
    # The shortfall judgement is a step like any other: the check comes first
    # and the judgement of what it published is the last thing recorded.
    assert bench.commands("live-preflight")[-2:] == ["collector-check", "collector-duration"]
    # The tree comparison ran in both directions, with the listing's own
    # exclusions: the clone's certs/ and the guest's data/ are not differences.
    assert "only in the clone: 0" in result.stdout


def test_preflight_prerequisite_stops_the_driver(bench):
    result = bench.run("preflight.sh", EGW_STUB_FAIL="docker-up")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["system_outcome"] == "not-run"
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "stack start interlock failed" in verdicts["reason"]
    assert "not run: collector-copy" in verdicts["reason"]
    assert "collector-check" in verdicts["reason"]
    # Nothing after the interlock ran, and the attempt was exported all the same.
    assert bench.commands("live-preflight") == ["stack-start-interlock"]
    assert bench.package("live-preflight") is not None


def test_preflight_unreadable_dmesg_is_not_no_oom(bench):
    # A dmesg that cannot be read leaves the OOM state of this boot UNKNOWN,
    # which is not "no OOM" and is not a stack seen failing either: the step
    # could not DETERMINE the state, so the check did not run (exit 1 -> 2).
    result = bench.run("preflight.sh", EGW_STUB_FAIL="dmesg")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["system_outcome"] == "not-run"
    assert "observed system fault(s)" not in verdicts["reason"]
    assert "OOM state is unknown" in verdicts["reason"]
    # The health check is the last step attempted: the rest is named as not run.
    assert bench.commands("live-preflight")[-1] == "stack-health"
    assert "broker-secrets-check" not in bench.commands("live-preflight")
    assert "not run: broker-secrets-check" in verdicts["reason"]


@pytest.mark.parametrize("failure, says", [
    ("service-oomkilled", "OOMKilled=true"),
    ("service-down", "status=exited"),
    ("service-unhealthy", "health=unhealthy"),
    ("oom", "memory-cgroup OOM lines: 1"),
])
def test_preflight_stack_it_saw_failing_is_a_system_failure(bench, failure, says):
    # The health step RAN and saw the stack failing: what it observed is sound,
    # so this is a measured system failure (valid, fail, exit 1), not a check
    # that did not run and not invalid instrumentation. The steps that
    # depend on a healthy stack are still skipped, and the driver still ends
    # non-zero, so nothing longer starts on the strength of it.
    result = bench.run("preflight.sh", EGW_STUB_FAIL=failure)
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "observed system fault(s):" in verdicts["reason"]
    assert "stack-health exit 3" in verdicts["reason"]
    assert says in _console(bench, "live-preflight", "stack-health")
    assert "not run: broker-secrets-check" in verdicts["reason"]
    assert "broker-secrets-check" not in bench.commands("live-preflight")
    assert bench.package("live-preflight") is not None


def test_preflight_observed_fault_does_not_claim_a_complete_preflight(bench):
    # The observation itself stops the steps that depend on a healthy stack, so
    # the record must not say in one breath that the stack failed and that this
    # preflight's own evidence is complete: what is written down is what was
    # observed and which steps were not run.
    result = bench.run("preflight.sh", EGW_STUB_FAIL="service-unhealthy")
    assert result.returncode == 1, report(result)
    reason = bench.verdicts("live-preflight")["reason"]
    assert "the preflight's own evidence is complete" not in reason, reason
    assert "the steps after it were not run: broker-secrets-check" in reason
    assert "collector-check" in reason


@pytest.mark.parametrize("state, records", [
    # The healthcheck of a service that is running has not concluded. This is
    # the live preflight of 2026-09-19, whose stack-health record reads
    # 'egw-controller-1 running starting' and which passed: a rule that failed
    # it would be a rule that calls a healthy stack a fault.
    ("health-starting", "health=starting"),
    # A container that declares no healthcheck at all answers 'none', which is
    # the absence of a question, not a bad answer.
    ("no-healthcheck", "health=none"),
])
def test_preflight_health_that_has_not_concluded_is_judged_by_the_state(bench, state, records):
    result = bench.run("preflight.sh", EGW_STUB_FAIL=state)
    assert result.returncode == 0, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert "observed system fault(s)" not in verdicts["reason"]
    assert "prerequisite failed" not in verdicts["reason"]
    # It is recorded as the word it is: judged by the state, never hidden.
    assert f"egw-controller-1 status=running {records}" in _console(bench, "live-preflight",
                                                                   "stack-health")
    assert "collector-check" in bench.commands("live-preflight")


def test_preflight_service_that_is_not_there_is_a_fault_not_an_unknown(bench):
    # docker ANSWERED: it does not hold that container. The stack is missing a
    # service, which is an observation of it failing and not a state nobody
    # could read - and it is what nominal.sh's own comparison calls the fault
    # "gone after the run" for the identical system state.
    result = bench.run("preflight.sh", EGW_STUB_FAIL="service-absent")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "observed system fault(s):" in verdicts["reason"]
    assert "stack-health exit 3" in verdicts["reason"]
    assert "egw-ditto-policies-1 status=absent" in _console(bench, "live-preflight", "stack-health")
    assert bench.package("live-preflight") is not None


def test_preflight_inspect_that_did_not_answer_is_not_a_container_that_is_gone(bench):
    # 'docker ps -a' holds the container and the inspect then fails for another
    # reason than the daemon's own "No such object": nothing about that
    # container was determined. Reading it as absent would record a service
    # GONE - a fault of the system - that nobody observed, so this is the check
    # not having run (exit 1 -> 2) and not a stack seen failing.
    result = bench.run("preflight.sh", EGW_STUB_FAIL="inspect-unanswered")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "not-run")
    assert "observed system fault(s)" not in verdicts["reason"]
    assert "prerequisite failed" in verdicts["reason"]
    assert "egw-ditto-gateway-1 status=indeterminate" in _console(bench, "live-preflight",
                                                                 "stack-health")
    assert "status=absent" not in _console(bench, "live-preflight", "stack-health")


def test_preflight_fault_it_saw_survives_a_reading_it_could_not_make(bench):
    # A container the kernel really did OOM-kill, in a run whose dmesg cannot
    # be read: the step saw one thing and could not determine another, and
    # neither erases the other (exit 4). The prerequisite verdict is the one it
    # has always been - the OOM state of this boot is unknown, so the check did
    # not run - and the fault it positively saw is in the reason all the same.
    result = bench.run("preflight.sh", EGW_STUB_FAIL="service-oomkilled,dmesg")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "not-run")
    assert verdicts["reason"].startswith("observed system fault(s):")
    assert "stack-health exit 4" in verdicts["reason"]
    assert "prerequisite failed" in verdicts["reason"]
    assert "OOMKilled=true" in _console(bench, "live-preflight", "stack-health")


def test_preflight_mandatory_fetch_hash_failure_is_invalid(bench):
    # The fetched CSV does not match the guest's sha256: the fetch helper
    # exits 4 and the preflight is invalid, not merely "not exported".
    result = bench.run("preflight.sh", EGW_STUB_SCP_CORRUPT=".csv")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "not fetched and verified" in verdicts["reason"]
    assert bench.package("live-preflight") is not None
    # The steps after it still ran: a mandatory failure is not a prerequisite.
    assert "collector-check" in bench.commands("live-preflight")


@pytest.mark.parametrize("overrides, says", [
    # The offset the harness's confirmation deadlines depend on: the loop's own
    # echo used to decide the step, so three unreachable reads passed as 0.
    ({"EGW_STUB_SSH_REFUSE": "date +%s"}, "the host/guest clock offset was not observed"),
    # 'timedatectl show; date -u' used to be decided by 'date -u' alone.
    ({"EGW_STUB_FAIL": "timedatectl"}, "the guest clock was not read"),
])
def test_preflight_clock_observations_that_failed_are_invalid(bench, overrides, says):
    result = bench.run("preflight.sh", **overrides)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert says in verdicts["reason"]
    # A mandatory failure is not a prerequisite: the steps after it still ran.
    assert "collector-check" in bench.commands("live-preflight")


def test_preflight_collector_that_stopped_early_is_invalid(bench):
    # The check validates a collection against the COLLECTOR'S OWN window, so a
    # collector that died at two thirds of the duration it declares reconciles
    # with itself and its report reads clean. This driver is the one that
    # starts the collector, so it is the one that judges the shortfall.
    result = bench.run("preflight.sh", EGW_STUB_COLLECTOR_WINDOW_S="31")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "the collector did not hold the duration it declares" in verdicts["reason"]
    # The judgement is a step like any other, so its figures are in the package.
    assert ("stopped 14 s before the duration=45s its 'start:' line declares"
            in _console(bench, "live-preflight", "collector-duration"))
    assert bench.package("live-preflight") is not None


def test_preflight_collector_check_without_the_shortfall_is_invalid(bench):
    # Fail closed: a report that does not say how far the collection fell short
    # leaves it unknown, which is not "it held the duration it declares".
    _write(bench.drivers / "collector_check.py",
           '"""A check that writes a report without the shortfall field."""\n'
           "import json\nimport os\nimport sys\n\n"
           "with open(os.path.join(sys.argv[1], 'collector-check.json'), 'w',\n"
           "          encoding='utf-8') as fh:\n"
           "    json.dump({'problems': []}, fh)\n"
           "print('collector check: 0 problem(s)')\n")
    result = bench.run("preflight.sh")
    assert result.returncode == 3, report(result)
    assert "the shortfall could not be judged" in bench.verdicts("live-preflight")["reason"]
    assert ("declared_duration_shortfall_s"
            in _console(bench, "live-preflight", "collector-duration"))


def test_preflight_shortfall_that_could_not_be_judged_at_all_names_the_step(bench):
    # The helper writes its line to stdout only when it RAN: absent, or an
    # interpreter that cannot be executed, leaves stdout empty and the error on
    # stderr. The cause recorded for the mandatory step must still be a
    # sentence a reader of the package can act on, never an empty one, and the
    # judgement's own stdout, stderr and exit code must reach the evidence.
    (bench.drivers / "collector_shortfall.py").unlink()
    result = bench.run("preflight.sh")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "mandatory instrumentation failed: ;" not in verdicts["reason"]
    assert ("the collector did not hold the duration it declares, or the shortfall could "
            "not be judged") in verdicts["reason"]
    assert "collector-duration" in bench.commands("live-preflight")


def test_preflight_refuses_a_collector_that_is_not_the_clones(bench):
    # The copy that reached the guest differs from the clone's file: the guest
    # step refuses before installing it, so the deployed tree is untouched.
    result = bench.run("preflight.sh", EGW_STUB_SCP_CORRUPT="collect-resources.sh")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "collector install failed" in verdicts["reason"]
    assert "STOP: the copied collector is not the clone's" in result.stdout
    deployed = bench.guest_root / "opt" / "egw" / "deployment" / "scripts" / "collect-resources.sh"
    assert deployed.read_bytes() == (REPO_ROOT / "src" / "deployment" / "scripts" / "collect-resources.sh").read_bytes()


def test_preflight_deployed_tree_difference_is_a_prerequisite(bench):
    changed = bench.guest_root / "opt" / "egw" / "deployment" / "compose.yaml"
    changed.write_text(changed.read_text(encoding="utf-8") + "\n# changed on the guest\n", encoding="utf-8")
    result = bench.run("preflight.sh")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["system_outcome"] == "not-run"
    assert "differs from the clean clone" in verdicts["reason"]


def test_preflight_deployed_file_the_guest_lost_is_a_prerequisite(bench):
    # The guest no longer has one of the clone's deployed files: the provenance
    # claim "the stack measured is the clean clone's" is false, and the
    # preflight must not run.
    (bench.guest_root / "opt" / "egw" / "deployment" / "mosquitto" / "config"
     / "mosquitto.conf").unlink()
    result = bench.run("preflight.sh")
    assert result.returncode == 2, report(result)
    assert "ONLY IN CLONE  mosquitto/config/mosquitto.conf" in result.stdout
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["system_outcome"] == "not-run"
    assert "differs from the clean clone" in verdicts["reason"]


def test_preflight_lost_capture_of_a_prerequisite_names_the_capture(bench):
    # 'stack-start-interlock' ran (the stack was started); only its console
    # record was lost. That is invalid instrumentation, not "the stack did not
    # start", and the outcome is never 'not-run'.
    result = bench.run("preflight.sh", **bench.fail_capture_of("stack-start-interlock"))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["system_outcome"] == "inconclusive"
    assert "the console capture of 'stack-start-interlock' failed" in verdicts["reason"]
    assert "stack start interlock failed" not in verdicts["reason"]
    assert "not run: collector-copy" in verdicts["reason"]


def test_preflight_with_an_unusable_git_does_not_run(bench):
    result = bench.run("preflight.sh", EGW_STUB_FAIL="git")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["system_outcome"] == "not-run"
    assert "identity of the clean clone" in verdicts["reason"]
    # Nothing was attempted: every step is named as not run.
    assert bench.commands("live-preflight") == []
    assert "not run: stack-start-interlock" in verdicts["reason"]
    assert "collector-check" in verdicts["reason"]


def test_preflight_without_a_session_prints_the_final_line(bench):
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("preflight.sh")
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2" in result.stdout
    assert "status=no-attempt" in result.stdout
    assert "STOP: no open session" in result.stderr


def test_preflight_allows_only_a_different_readme(bench):
    readme = bench.guest_root / "opt" / "egw" / "deployment" / "README.md"
    readme.write_text("the guest keeps an older README\n", encoding="utf-8")
    result = bench.run("preflight.sh")
    assert result.returncode == 0, report(result)
    assert bench.verdicts("live-preflight")["system_outcome"] == "pass"


def test_preflight_export_failure_outranks_the_verdict(bench):
    # output_test is a regular file: no package can be written there.
    shutil.rmtree(bench.out)
    bench.out.write_text("not a directory\n", encoding="utf-8")
    result = bench.run("preflight.sh")
    assert result.returncode == 4, report(result)
    assert "EXPORT FAILED" in result.stderr
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["system_outcome"] == "pass"          # the check itself passed
    assert bench.package("live-preflight") is None       # but nothing was exported


def test_preflight_interrupted_ends_and_does_not_continue(bench):
    hang = Path(str(bench.log) + ".hang")
    process = subprocess.Popen(["bash", str(bench.drivers / "preflight.sh")],
                               env=bench.env(EGW_STUB_HANG_S="6"),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 120
    while not hang.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            break
        time.sleep(0.05)
    assert hang.exists(), "the interlock step never started"
    process.send_signal(signal.SIGTERM)
    stdout, stderr = process.communicate(timeout=300)
    assert process.returncode == 130, f"exit={process.returncode}\n{stdout}\n{stderr}"
    verdicts = bench.verdicts("live-preflight")
    assert verdicts["status"] == "interrupted"
    assert verdicts["system_outcome"] == "interrupted"
    assert bench.package("live-preflight") is not None
    # The trap ended the driver: nothing after the interlock was attempted.
    assert "collector-check" not in bench.commands("live-preflight")
    assert "sut-environment" not in bench.commands("live-preflight")


def test_slice_passes_and_exports(bench):
    result = bench.run("slice.sh", "itest-slice-01", "4242")
    assert result.returncode == 0, report(result)
    verdicts = bench.verdicts("smartwatch-slice-1-hz-60-s")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert bench.package("smartwatch-slice-1-hz-60-s") is not None
    assert "SLICE PASS" in result.stdout


def test_slice_valid_negative_is_not_an_instrumentation_failure(bench):
    lost = json.dumps({"confirmation_deadline_source": "controller", "sent_valid": 60,
                       "delivered_unique": 58, "lost": 2, "late_confirmations": 0,
                       "double_accepted": 0, "intended_invalid_accepted": 0, "marker_lag_s": 0.4})
    result = bench.run("slice.sh", "itest-slice-02", "4243", EGW_STUB_RECONCILE=lost)
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("smartwatch-slice-1-hz-60-s")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert bench.package("smartwatch-slice-1-hz-60-s") is not None


def test_slice_failed_precondition_did_not_run(bench):
    result = bench.run("slice.sh", "itest-slice-03", "4244", EGW_STUB_FAIL="pre")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("smartwatch-slice-1-hz-60-s")
    assert verdicts["system_outcome"] == "not-run"
    assert "simulator-and-mark" not in bench.commands("smartwatch-slice-1-hz-60-s")
    assert bench.package("smartwatch-slice-1-hz-60-s") is not None


def test_slice_check_that_was_not_carried_out_is_invalid(bench):
    result = bench.run("slice.sh", "itest-slice-04", "4245", EGW_STUB_REC_CHECK="3")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("smartwatch-slice-1-hz-60-s")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "the protocol check was not carried out" in verdicts["reason"]


def test_slice_delta_mismatch_is_a_result_not_an_instrumentation_failure(bench):
    result = bench.run("slice.sh", "itest-slice-05", "4246", EGW_STUB_REC_DELTA="4")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("smartwatch-slice-1-hz-60-s")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")


def test_slice_delta_that_did_not_run_is_invalid(bench):
    result = bench.run("slice.sh", "itest-slice-06", "4247", EGW_STUB_REC_DELTA="1")
    assert result.returncode == 3, report(result)
    assert bench.verdicts("smartwatch-slice-1-hz-60-s")["instrumentation_validity"] == "invalid"


def test_slice_without_its_arguments_is_a_prerequisite(bench):
    # 1 is the code of a valid negative result: a driver called without a run
    # id measured nothing and must never claim one.
    result = bench.run("slice.sh")
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2" in result.stdout
    assert "usage: slice.sh RUN SEED" in result.stderr
    assert not list(bench.attempts.glob("*_smartwatch-slice-*"))
    assert bench.run("slice.sh", "itest-slice-07").returncode == 2


@pytest.mark.parametrize("reconcile, says", [
    ("[{\"lost\": 0}]", "'list' object has no attribute 'get'"),
    ("{\"lost\": 0}", "no usable sent_valid"),
])
def test_slice_unusable_reconciliation_is_invalid(bench, reconcile, says):
    # Exit 2 from the verdict snippet means there is nothing to judge: it is
    # never the 1 of "the delivery criteria failed".
    result = bench.run("slice.sh", "itest-slice-08", "4248", EGW_STUB_RECONCILE=reconcile)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("smartwatch-slice-1-hz-60-s")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "the reconciliation file was not judged (verdict exit 2)" in verdicts["reason"]
    assert says in result.stdout


def test_slice_lost_capture_of_pre_names_the_capture(bench):
    # 'pre' itself ran; only its console record was lost.
    result = bench.run("slice.sh", "itest-slice-09", "4249", **bench.fail_capture_of("pre"))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("smartwatch-slice-1-hz-60-s")
    assert verdicts["system_outcome"] == "inconclusive", "a step that ran is not 'not-run'"
    assert "the console capture of 'pre' failed" in verdicts["reason"]
    assert "precondition failed" not in verdicts["reason"]
    assert bench.package("smartwatch-slice-1-hz-60-s") is not None


# --------------------------------------------------------------------------
# The readiness wait the two G2 drivers share (guest_common.sh)
# --------------------------------------------------------------------------

GATE = "g2-gate-preconditions"
PERSIST = "g2-twin-persistence-restart"
# Long enough to be a bounded wait, short enough that a bench that polls ends:
# 0 s means one sample and then the limit, which is what a stack that is not
# at the gate has to answer with.
NOW = {"EGW_HEALTH_LIMIT_S": "0", "EGW_HEALTH_STEP_S": "1"}


def _ssh_log(bench: Bench) -> str:
    """Every ssh and scp command the stubs were given, or nothing at all when
    a driver stopped before it reached the guest."""
    try:
        return bench.log.read_text(encoding="utf-8")
    except OSError:
        return ""


def _wait_script(bench: Bench, limit: str = "0", step: str = "1") -> str:
    """The guest command healthy_wait_script builds, as the drivers build it."""
    result = subprocess.run(
        ["bash", "-c", 'cd "$1" && . ./common.sh && . ./guest_common.sh '
                       '&& healthy_wait_script "$2" "$3"',
         "_", str(bench.drivers), limit, step],
        env=bench.env(), capture_output=True, text=True)
    assert result.returncode == 0, report(result)
    return result.stdout


def _wait(bench: Bench, limit: str = "0", **overrides) -> subprocess.CompletedProcess:
    """That same guest command, run against the docker stub as the guest runs
    it: under /bin/sh, with no bash feature available to it."""
    script = bench.tmp / "healthy_wait.sh"
    script.write_text(_wait_script(bench, limit), encoding="utf-8")
    environment = bench.env(**overrides)
    environment["PATH"] = f"{bench.guest_bin}{os.pathsep}{environment['PATH']}"
    return subprocess.run(["sh", str(script)], env=environment, capture_output=True,
                          text=True, timeout=300)


def test_healthy_wait_is_written_once_and_used_by_both_drivers():
    # One implementation of the stricter G2 wait, in guest_common.sh: the two
    # drivers call it, and neither carries a poll of its own.
    shared = (SESSION_DIR / "guest_common.sh").read_text(encoding="utf-8")
    assert shared.count("healthy_wait_script()") == 1
    for driver in ("gate_health.sh", "persistence.sh"):
        text = (SESSION_DIR / driver).read_text(encoding="utf-8")
        assert "healthy_wait " in text, driver
        assert "healthy_wait_script" not in text, f"{driver} must not build the wait itself"
        assert ".State.Health" not in text, f"{driver} must not poll health on its own"


def test_healthy_wait_passes_when_every_service_is_healthy(bench):
    result = _wait(bench, "1800")
    assert result.returncode == 0, report(result)
    assert "ALL HEALTHY: the 6 expected services" in result.stdout
    for service in EXPECT_SERVICES:
        assert f"{service}=running/healthy" in result.stdout


@pytest.mark.parametrize("failure, says", [
    ("health-starting", "egw-controller-1(status=running health=starting)"),
    ("service-unhealthy", "egw-mongodb-1(status=running health=unhealthy)"),
    ("no-healthcheck", "egw-controller-1(status=running health=none)"),
    ("service-down", "egw-mosquitto-1(status=exited"),
    ("service-absent", "egw-ditto-policies-1(the daemon does not hold this container)"),
])
def test_healthy_wait_names_a_service_that_is_not_healthy(bench, failure, says):
    # G2 asks for 'healthy'. A check that has not concluded, one that fails,
    # a container that declares none and one the daemon does not hold are all
    # the system's own state: exit 1, with the service named.
    result = _wait(bench, "0", EGW_STUB_FAIL=failure)
    assert result.returncode == 1, report(result)
    assert "NOT HEALTHY" in result.stdout
    assert says in result.stdout


def test_healthy_wait_that_could_not_determine_a_state_is_not_a_failure(bench):
    # An inspect that failed for any other reason determines NOTHING about
    # that container: 2, never the 1 of a service that is not healthy.
    result = _wait(bench, "0", EGW_STUB_FAIL="inspect-unanswered")
    assert result.returncode == 2, report(result)
    assert "NOT DETERMINED" in result.stdout
    assert "egw-ditto-gateway-1(its status could not be read)" in result.stdout
    assert "NOT HEALTHY" not in result.stdout


def test_healthy_wait_keeps_both_what_it_saw_and_what_it_could_not_read(bench):
    result = _wait(bench, "0", EGW_STUB_FAIL="inspect-unanswered,service-unhealthy")
    assert result.returncode == 4, report(result)
    assert "NOT HEALTHY" in result.stdout and "NOT DETERMINED" in result.stdout


def test_healthy_wait_keeps_every_sample_so_a_transition_is_visible(bench):
    # The health check concludes on the third sample: the record holds the
    # samples before it, each with its instant, and not only the answer.
    result = _wait(bench, "1800", EGW_STUB_FAIL="health-transition")
    assert result.returncode == 0, report(result)
    samples = [line for line in result.stdout.splitlines() if " sample " in line]
    assert len(samples) >= 3, result.stdout
    assert "egw-controller-1=running/starting" in samples[0]
    assert "egw-controller-1=running/healthy" in samples[-1]
    assert samples[0].startswith("20") and "Z sample 1:" in samples[0]


def test_healthy_wait_refuses_a_limit_that_is_not_seconds(bench):
    result = subprocess.run(
        ["bash", "-c", 'cd "$1" && . ./common.sh && . ./guest_common.sh '
                       '&& healthy_seconds EGW_HEALTH_LIMIT_S 1800',
         "_", str(bench.drivers)],
        env=bench.env(EGW_HEALTH_LIMIT_S="soon"), capture_output=True, text=True)
    assert result.returncode == 1, report(result)
    assert result.stdout == "", "a limit that was not read is never replaced by the default"
    assert "is not a whole number of seconds" in result.stderr


# --------------------------------------------------------------------------
# gate_health.sh: the gate's precondition snapshot
# --------------------------------------------------------------------------

def test_gate_health_passes_and_exports(bench):
    result = bench.run("gate_health.sh")
    assert result.returncode == 0, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert bench.package(GATE) is not None
    # The five steps of the gate, each with its own record.
    for step in ("services-healthy", "controller-endpoints", "endpoints-verdict",
                 "counters-verdict", "container-identities", "tls-configuration"):
        assert step in bench.commands(GATE), step
    environment = bench.attempt(GATE) / "environment"
    assert json.loads((environment / "health.json").read_text(encoding="utf-8"))["status"] == "ok"
    assert json.loads((environment / "ready.json").read_text(encoding="utf-8"))["status"] == "ready"
    assert json.loads((environment / "metrics.json").read_text(encoding="utf-8"))["accepted"] == 0
    identities = (environment / "container_identities.txt").read_text(encoding="utf-8")
    for service in EXPECT_SERVICES:
        assert f"identity {service} image=stub/{service}:1" in identities
        assert "repo_digest=stub/controller@sha256:" in identities
    assert (environment / "egw-controller-build-identity.txt").read_text(encoding="utf-8")
    tls = (environment / "tls_configuration.txt").read_text(encoding="utf-8")
    assert "listener 8883" in tls and "allow_anonymous false" in tls
    assert "SHA256 Fingerprint=" in tls
    assert "600 " in tls and "server.key" in tls, "the mode of the private material is recorded"
    assert "stub server.key" not in tls, "a private key is never read into the evidence"


def test_gate_health_does_not_start_or_change_anything(bench):
    assert bench.run("gate_health.sh").returncode == 0
    log = _ssh_log(bench)
    for forbidden in (" up -d", " down", " restart", " stop", "systemd-run", "sudo "):
        assert forbidden not in log, f"gate_health.sh must not run{forbidden}"
    source = (SESSION_DIR / "gate_health.sh").read_text(encoding="utf-8")
    for forbidden in ("$DC", "$SIM", "up -d", "down"):
        assert forbidden not in source, f"gate_health.sh must not carry {forbidden}"


@pytest.mark.parametrize("failure, says", [
    ("health-starting", "egw-controller-1(status=running health=starting)"),
    ("service-unhealthy", "egw-mongodb-1(status=running health=unhealthy)"),
])
def test_gate_health_service_that_never_becomes_healthy_is_a_system_failure(bench, failure, says):
    # A health check that has not concluded passes the engineering preflight
    # and is NOT the gate: the stack answered, so this is a valid negative
    # result (1), never invalid instrumentation.
    result = bench.run("gate_health.sh", EGW_STUB_FAIL=failure, **NOW)
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert says in verdicts["reason"]
    assert verdicts["reason"].startswith("the first thing that was not as G2 requires:")
    assert bench.package(GATE) is not None


def test_gate_health_state_it_could_not_determine_is_invalid_not_a_failure(bench):
    result = bench.run("gate_health.sh", EGW_STUB_FAIL="inspect-unanswered", **NOW)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "could not be determined at all" in verdicts["reason"]


def test_gate_health_ready_that_answers_503_is_the_systems_answer(bench):
    result = bench.run("gate_health.sh", EGW_STUB_READY_CODE="503")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "/ready answered 503, not 200" in verdicts["reason"]


def test_gate_health_health_body_that_is_not_ok_is_the_systems_answer(bench):
    result = bench.run("gate_health.sh", EGW_STUB_HEALTH_BODY='{"status": "degraded"}')
    assert result.returncode == 1, report(result)
    assert "not ok" in bench.verdicts(GATE)["reason"]


def test_gate_health_body_that_cannot_be_read_is_invalid(bench):
    # A 200 whose body is not readable is not an answer this gate can record:
    # nothing is concluded from it, and it is never read as a system failure.
    result = bench.run("gate_health.sh", EGW_STUB_HEALTH_BODY="{not json")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "endpoints-verdict exit 2" in verdicts["reason"]


def test_gate_health_counter_that_is_not_zero_names_the_controlled_lifecycle(bench):
    result = bench.run("gate_health.sh", EGW_STUB_METRICS_ACCEPTED="60")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "accepted=60" in verdicts["reason"]
    action = verdicts["next_action"]
    assert "restart the controller through the documented lifecycle" in action
    assert "with the queue empty" in action
    assert "never delete data and never edit a counter" in action


def test_gate_health_metrics_without_a_started_at_is_invalid(bench):
    # A counter baseline that belongs to no identified process is not a
    # baseline: it is nothing to conclude from, not a zero that was read.
    result = bench.run("gate_health.sh", EGW_STUB_METRICS_EXTRA='{"started_at": ""}')
    assert result.returncode == 3, report(result)
    assert "counters-verdict exit 2" in bench.verdicts(GATE)["reason"]


def test_gate_health_broker_that_allows_anonymous_is_not_the_gate(bench):
    conf = bench.guest_root / "opt" / "egw" / "deployment" / "mosquitto" / "config" / "mosquitto.conf"
    conf.write_text(conf.read_text(encoding="utf-8").replace("allow_anonymous false",
                                                             "allow_anonymous true"),
                    encoding="utf-8")
    result = bench.run("gate_health.sh")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "allow_anonymous=true" in verdicts["reason"]


def test_gate_health_listener_on_another_port_is_not_the_publishing_path(bench):
    # The gate's TLS claim is about the port the smartwatch publishes on. A
    # broker listening somewhere else may be a healthy broker; it is not the
    # path this gate says carries the flow.
    conf = bench.guest_root / "opt" / "egw" / "deployment" / "mosquitto" / "config" / "mosquitto.conf"
    conf.write_text(conf.read_text(encoding="utf-8").replace("listener 8883", "listener 1883"),
                    encoding="utf-8")
    result = bench.run("gate_health.sh")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "listener=1883(expected 8883)" in verdicts["reason"]


def test_gate_health_broker_that_states_no_tls_version_is_not_the_gate(bench):
    # A listener with certificates but no stated version leaves what would be
    # negotiated to a default nobody recorded: the gate records the version or
    # it does not hold.
    conf = bench.guest_root / "opt" / "egw" / "deployment" / "mosquitto" / "config" / "mosquitto.conf"
    conf.write_text("\n".join(line for line in conf.read_text(encoding="utf-8").splitlines()
                              if not line.strip().startswith("tls_version")) + "\n",
                    encoding="utf-8")
    result = bench.run("gate_health.sh")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "tls_version(absent)" in verdicts["reason"]


def test_gate_health_records_the_material_the_broker_names(bench):
    # The certificate and the key the gate records must be the ones the broker
    # reads. A configuration naming other files must not be recorded with the
    # metadata of files nobody uses: the paths are translated from the broker's
    # own configuration and refused when they are not in the deployed tree.
    config = bench.guest_root / "opt" / "egw" / "deployment" / "mosquitto" / "config"
    (config / "certs" / "other-ca.crt").write_text(
        (config / "certs" / "ca.crt").read_text(encoding="utf-8"), encoding="utf-8")
    conf = config / "mosquitto.conf"
    conf.write_text(conf.read_text(encoding="utf-8").replace(
        "cafile /mosquitto/config/certs/ca.crt",
        "cafile /mosquitto/config/certs/other-ca.crt"), encoding="utf-8")
    result = bench.run("gate_health.sh")
    assert result.returncode == 0, report(result)
    tls = (bench.attempt(GATE) / "environment" / "tls_configuration.txt").read_text(encoding="utf-8")
    assert "cafile /mosquitto/config/certs/other-ca.crt -> mosquitto/config/certs/other-ca.crt" in tls
    assert "other-ca.crt" in tls.split("## modes")[1], "the mode recorded is that of the file the broker names"


def test_gate_health_material_outside_the_deployed_tree_is_not_recordable(bench):
    # A broker told to read a certificate from somewhere this tree does not
    # hold: the gate cannot say what it reads, and says so instead of recording
    # the files it would have guessed.
    conf = bench.guest_root / "opt" / "egw" / "deployment" / "mosquitto" / "config" / "mosquitto.conf"
    conf.write_text(conf.read_text(encoding="utf-8").replace(
        "certfile /mosquitto/config/certs/server.crt",
        "certfile /etc/ssl/elsewhere/server.crt"), encoding="utf-8")
    result = bench.run("gate_health.sh")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "tls-configuration exit 2" in verdicts["reason"]


def test_gate_health_ca_fingerprint_that_could_not_be_read_is_invalid(bench):
    result = bench.run("gate_health.sh", EGW_STUB_FAIL="openssl")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "tls-configuration exit 2" in verdicts["reason"]


def test_gate_health_identity_that_was_not_recorded_is_invalid(bench):
    result = bench.run("gate_health.sh", EGW_STUB_SSH_REFUSE="{{.Config.Image}}")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "identities of the six running containers were not recorded" in verdicts["reason"]


def test_gate_health_guest_that_cannot_be_reached_is_invalid(bench):
    # Nothing was observed about the stack: that is an invalid snapshot, and
    # never "the services are not healthy".
    result = bench.run("gate_health.sh", EGW_STUB_SSH_REFUSE="docker", **NOW)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "the readiness wait did not answer" in verdicts["reason"]
    assert "NOT HEALTHY" not in verdicts["reason"]


def test_gate_health_lost_capture_of_the_wait_names_the_capture(bench):
    result = bench.run("gate_health.sh", **bench.fail_capture_of("services-healthy"))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert "the console capture of 'services-healthy' failed" in verdicts["reason"]
    assert bench.package(GATE) is not None


def test_gate_health_with_an_argument_is_a_prerequisite(bench):
    result = bench.run("gate_health.sh", "itest-g2-01")
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2" in result.stdout
    assert "usage: gate_health.sh (no arguments)" in result.stderr
    assert not list(bench.attempts.glob(f"*_{GATE}_*"))


def test_gate_health_without_a_session_prints_the_final_line(bench):
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("gate_health.sh")
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2" in result.stdout


def test_gate_health_with_an_unusable_limit_reads_nothing(bench):
    result = bench.run("gate_health.sh", EGW_HEALTH_LIMIT_S="half an hour")
    assert result.returncode == 2, report(result)
    assert "EGW_HEALTH_LIMIT_S is not a whole number of seconds" in result.stdout
    assert not list(bench.attempts.glob(f"*_{GATE}_*"))


def test_gate_health_export_failure_outranks_the_verdict(bench):
    result = bench.run("gate_health.sh", **bench.python_stub(PY_EXPORT_FAILS_ONCE))
    assert result.returncode == 4, report(result)
    assert "EXPORT FAILED" in result.stderr


def test_gate_health_controller_that_was_never_reached_did_not_answer(bench):
    # curl writes an empty body and prints the code 000 when it never reached
    # the controller (its own exit 7). A reading that was not made is not an
    # answer: the snapshot is invalid, and the stack is NOT recorded as having
    # answered something the gate does not accept.
    result = bench.run("gate_health.sh", EGW_STUB_FAIL="curl-down")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) \
        == ("invalid", "inconclusive")
    reason = verdicts["reason"]
    assert "/health was not read (curl exit 7, HTTP code 000)" in reason
    assert "/ready was not read (curl exit 7, HTTP code 000)" in reason
    assert "/metrics was not read (curl exit 7, HTTP code 000)" in reason
    assert "the controller was not reached" in reason
    for invented in ("answered 000, not 200", "the controller's endpoints are not at the gate",
                     "the controller's counter baseline is not the gate's"):
        assert invented not in reason, invented
    # The three readings are kept as they were made: code and curl status.
    codes = (bench.attempt(GATE) / "environment" / "http_codes.txt").read_text(encoding="utf-8")
    assert codes.split() == ["health", "000", "7", "ready", "000", "7", "metrics", "000", "7"]


def test_gate_health_endpoint_that_answered_503_is_still_the_systems_answer(bench):
    # The other side of the same rule: a code the controller itself answered is
    # its answer, and that stays a valid negative result.
    result = bench.run("gate_health.sh", EGW_STUB_READY_CODE="503")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "/ready answered 503, not 200" in verdicts["reason"]
    assert "was not read" not in verdicts["reason"]


def test_gate_health_step_that_never_reached_the_guest_is_not_a_fault(bench):
    # The ssh wrapper itself fails (the session's helpers are gone): no guest
    # command ran, so nothing was observed about the services or the broker.
    # A step that never reached the guest is never read as the guest reporting
    # a fault.
    (bench.session / "scripts" / "session_common.sh").unlink()
    result = bench.run("gate_health.sh", **NOW)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) \
        == ("invalid", "inconclusive")
    reason = verdicts["reason"]
    assert "docker inspect" not in _ssh_log(bench), "nothing ran on the guest"
    assert "the readiness wait did not answer because it never reached the guest" in reason
    assert "never ran: it did not reach the guest" in reason
    for invented in ("not every expected service reached",
                     "the publishing path's configuration is not the gate's"):
        assert invented not in reason, invented


def test_gate_health_host_step_whose_preamble_failed_never_ran(bench):
    # The other wrapper: the tunnels of 5.7 could not be opened, so the host
    # preamble of runbook 6.1 failed and the reading of the three endpoints
    # never ran. A step that never ran observed nothing about the controller.
    result = bench.run("gate_health.sh", EGW_STUB_TUNNEL="broken")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) \
        == ("invalid", "inconclusive")
    reason = verdicts["reason"]
    assert "the controller's endpoints were not read (controller-endpoints exit 97)" in reason
    assert "'controller-endpoints' never ran" in reason
    assert "the controller's endpoints are not at the gate" not in reason


def test_gate_health_build_identity_that_is_empty_on_the_guest_is_no_identity(bench):
    identity = (bench.guest_root / "opt" / "egw" / "images"
                / "egw-controller-0.1.0-arm64.identity.txt")
    identity.write_text("", encoding="utf-8")
    result = bench.run("gate_health.sh")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "identities of the six running containers were not recorded" in verdicts["reason"]
    assert "the controller build identity are recorded" not in verdicts["reason"]


def test_gate_health_build_identity_that_arrived_empty_is_no_identity(bench):
    # The fetch itself succeeded and what reached environment/ holds nothing,
    # as a truncated transfer leaves it: an identity that was not read is not
    # an identity, and this gate records the controller image that was built.
    result = bench.run("gate_health.sh", EGW_STUB_SCP_EMPTY="identity.txt")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "egw-controller-build-identity.txt is EMPTY" in verdicts["reason"]
    kept = (bench.attempt(GATE) / "environment" / "egw-controller-build-identity.txt")
    assert kept.stat().st_size == 0
    assert "the controller build identity are recorded" not in verdicts["reason"]


def test_gate_health_repo_digest_that_could_not_be_read_is_no_identity(bench):
    # 'docker image inspect' that did not answer read no identity, and a
    # literal in its place would pass a gate that recorded nothing.
    result = bench.run("gate_health.sh", EGW_STUB_FAIL="no-repo-digest")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(GATE)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "identities of the six running containers were not recorded" in verdicts["reason"]
    identities = (bench.attempt(GATE) / "environment" / "container_identities.txt")
    kept = identities.read_text(encoding="utf-8")
    assert "repo_digest=NOT-READ" in kept
    assert "none-recorded" not in kept


def test_gate_health_image_built_on_the_guest_has_no_repo_digest_and_passes(bench):
    # An image built on the guest carries no repo digest at all. That is a fact
    # about the image, read from an inspect that ANSWERED, and it is recorded
    # as 'none' without failing the gate.
    result = bench.run("gate_health.sh", EGW_STUB_FAIL="locally-built-image")
    assert result.returncode == 0, report(result)
    identities = (bench.attempt(GATE) / "environment"
                  / "container_identities.txt").read_text(encoding="utf-8")
    assert "repo_digest=none" in identities
    assert "NOT-READ" not in identities


@pytest.mark.parametrize("overrides, says", [
    ({}, "the gate's preconditions hold"),
    ({"EGW_STUB_FAIL": "health-starting", **NOW},
     "egw-controller-1(status=running health=starting)"),
    ({"EGW_STUB_HEALTH_CODE": "000", "EGW_STUB_READY_CODE": "000"},
     "/health was not read (curl exit 7, HTTP code 000)"),
])
def test_gate_health_final_line_names_which_thing_it_was(bench, overrides, says):
    # The one line the operator reads has to tell a controller that is stuck
    # 'starting' from a controller that was never reached: both end non-zero,
    # and they call for different actions.
    result = bench.run("gate_health.sh", **overrides)
    final = result.stdout.strip().splitlines()[-1]
    assert final.startswith("DRIVER RESULT "), report(result)
    assert " headline=" in final, final
    assert says in final, final


# --------------------------------------------------------------------------
# persistence.sh: runbook 6.5 on the run the G2 slice produced
# --------------------------------------------------------------------------

G2_RUN = "itest-g2-01"


def _slice_done(bench: Bench, run: str = G2_RUN, records: int = 60) -> str:
    """What a completed slice leaves behind: the run directory with its
    published identities, the 'after' pair the 'persist-before' snapshot is
    taken like, and the controller's event log of that run on the guest."""
    itest = bench.home / "egw-tcg" / "itest"
    _write(itest / run / "sent_events.jsonl", "".join(
        json.dumps({"message_id": f"m-{n:04d}", "device_uuid": "stub-device",
                    "device_type": "smartwatch", "seq": n, "run_id": run}) + "\n"
        for n in range(records)))
    _write(itest / f"{run}.metrics.after.json", json.dumps(
        {"queue_depth": 0, "started_at": "2026-09-19T20:00:00Z", "accepted": records,
         "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0}))
    _write(itest / f"{run}.twins.after.json", json.dumps(
        {"label": "after", "devices": {"stub-device": {"ingestion": 60}}}))
    _write(bench.guest_root / "opt" / "egw" / "deployment" / "data" / "events" / run
           / "events.jsonl", "".join(
        json.dumps({"message_id": f"m-{n:04d}", "run_id": run, "outcome": "accepted"}) + "\n"
        for n in range(records)))
    bench.extra["EGW_STUB_TWIN_RUN_ID"] = run
    return run


def test_persistence_passes_and_exports(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN)
    assert result.returncode == 0, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert bench.package(PERSIST) is not None
    assert "RESTART SHOWN" in result.stdout
    assert "STATE PERSISTED" in result.stdout
    # /metrics is per process: zero counters and a new started_at after the
    # restart are expected, and are recorded as expected, never as loss.
    assert "never persisted, so 0 again is expected" in result.stdout
    assert "2026-09-19T20:00:00Z -> 2026-09-19T21:11:00Z" in result.stdout
    environment = bench.attempt(PERSIST) / "environment"
    for name in ("metrics.persist-before.json", "metrics.post-restart.json",
                 "containers.persist-before.txt", "containers.post-restart.txt",
                 "twin.persist-before.json", "twin.post-restart.json"):
        assert (environment / name).read_text(encoding="utf-8"), name
    itest = bench.home / "egw-tcg" / "itest"
    assert (itest / f"{G2_RUN}.twins.persist-before.json").is_file()
    assert (itest / f"{G2_RUN}.twins.post-restart.json").is_file()


def test_persistence_never_removes_a_volume_and_never_republishes(bench):
    _slice_done(bench)
    assert bench.run("persistence.sh", G2_RUN).returncode == 0
    log = _ssh_log(bench)
    assert " down\n" in log and " up -d\n" in log, log
    for forbidden in ("down -v", "--volumes", "volume rm", "volume prune"):
        assert forbidden not in log, forbidden
    # Nothing is published and no twin is written: the simulator is never
    # started and every call through the API is a read. The driver's own
    # commands are read, not its prose, which says what it never does.
    code = [line for line in (SESSION_DIR / "persistence.sh").read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")]
    for forbidden in ("down -v", "--volumes", "volume rm", "$SIM", "-X PUT", "-X POST", "--data"):
        assert not [line for line in code if forbidden in line], forbidden


def test_persistence_started_at_that_did_not_change_was_not_a_restart(bench):
    # An issued command is not a restart: without a new controller process the
    # readback shows nothing, so this is inconclusive, never a pass.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="started-at-unchanged")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "the restart was not shown" in verdicts["reason"]
    assert "the controller started_at did not change" in verdicts["reason"]
    assert "twin-state-same" not in bench.commands(PERSIST), "nothing is read from a restart that was not shown"


def test_persistence_container_ids_that_did_not_change_were_not_a_restart(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="ids-unchanged")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert "the container id of egw-mosquitto-1 did not change" in verdicts["reason"]


def test_persistence_containers_that_did_not_start_later_were_not_a_restart(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="not-later")
    assert result.returncode == 3, report(result)
    assert "did not start later than before the restart" in bench.verdicts(PERSIST)["reason"]


def test_persistence_twin_that_changed_is_a_valid_negative(bench):
    # A real persistence defect is a RESULT: the attempt keeps it, exported
    # and verified, and it is not called invalid instrumentation.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="twin-changed")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "is not the state that came back" in verdicts["reason"]
    assert "accepted_count" in verdicts["reason"]
    assert bench.package(PERSIST) is not None


def test_persistence_drained_that_failed_restarted_nothing(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="drained")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert verdicts["system_outcome"] == "not-run"
    assert "NOTHING was restarted" in verdicts["reason"]
    assert "not run: metrics-before" in verdicts["reason"]
    assert "restart-down-up" not in bench.commands(PERSIST)
    assert "down" not in _ssh_log(bench)
    assert bench.package(PERSIST) is not None


def test_persistence_stack_that_does_not_come_back_is_a_system_failure(bench):
    # The controller itself answered 503: that is the stack not coming back,
    # and the code it answered is named. The six services are still asked
    # directly over ssh, because that second channel is what can say what the
    # guest is doing.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="wait_ready")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "answered /ready 503, not 200" in verdicts["reason"]
    assert "the restart was issued" in verdicts["reason"]
    assert "services-healthy-again" in bench.commands(PERSIST)


def test_persistence_a_controller_nobody_reached_is_not_a_stack_that_failed(bench):
    # wait_ready gave up with curl's code 000: the request was answered by
    # nobody - the tunnel of 5.7 dropped during the hour it polls - so nothing
    # was observed about the stack coming back. That is a record that could not
    # be made, never the valid negative result this driver's strongest claim is.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="wait_ready-000")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert "NOT REACHED after the restart" in verdicts["reason"]
    assert "answered /ready 000" not in verdicts["reason"]
    assert "did not answer /ready 200 within" not in verdicts["reason"]
    assert "services-healthy-again" in bench.commands(PERSIST), (
        "the six services must still be asked over ssh, which is the second channel")


def test_persistence_readiness_that_was_not_observed_is_not_a_failure(bench):
    # The step died in the transport, so it reported nothing about /ready: a
    # status alone never says the stack failed to come back.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="wait_ready-dropped")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "readiness after the restart was NOT observed" in verdicts["reason"]
    assert "did not answer /ready 200" not in verdicts["reason"]


def test_persistence_services_that_do_not_become_healthy_again_are_a_failure(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="service-unhealthy", **NOW)
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "egw-mongodb-1(status=running health=unhealthy)" in verdicts["reason"]


def test_persistence_records_that_nothing_was_published_between_the_snapshots(bench):
    # The twin and the event log are read on both sides, and a log that grew
    # means the quiet this demonstration rests on was not held.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="late-records")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "nothing is published between the two snapshots was not held" in verdicts["reason"]
    assert "the event log of itest-g2-01 grew from 60 to 61 records" in verdicts["reason"]


def test_persistence_new_process_that_already_counted_is_not_quiet(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="late-counters")
    assert result.returncode == 3, report(result)
    assert "already counted accepted=3" in bench.verdicts(PERSIST)["reason"]


def test_persistence_twin_that_cannot_be_read_is_invalid(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="twin-unreadable")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "NOTHING was restarted" in verdicts["reason"]
    assert "restart-down-up" not in bench.commands(PERSIST)


def test_persistence_lost_capture_of_a_mandatory_step_is_invalid(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN,
                       **bench.fail_capture_of("containers-before"))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert "the console capture of 'containers-before' failed" in verdicts["reason"]
    assert "restart-down-up" not in bench.commands(PERSIST)
    assert bench.package(PERSIST) is not None


def test_persistence_restart_that_ended_non_zero_was_not_shown(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="docker-down")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert "the restart was not shown" in verdicts["reason"]
    assert "the restart was issued" in verdicts["reason"]


def test_persistence_without_a_completed_slice_is_a_prerequisite(bench):
    result = bench.run("persistence.sh", G2_RUN)
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2" in result.stdout
    assert "persistence.sh runs on a run the slice completed" in result.stderr
    assert "nothing was restarted" in result.stderr
    assert not list(bench.attempts.glob(f"*_{PERSIST}_*"))


def test_persistence_refuses_a_run_id_it_already_checked(bench):
    _slice_done(bench)
    _write(bench.home / "egw-tcg" / "itest" / f"{G2_RUN}.twins.persist-before.json", "{}")
    result = bench.run("persistence.sh", G2_RUN)
    assert result.returncode == 2, report(result)
    assert "its records are write-once" in result.stderr
    assert "down" not in _ssh_log(bench)


def test_persistence_without_its_argument_is_a_prerequisite(bench):
    result = bench.run("persistence.sh")
    assert result.returncode == 2, report(result)
    assert "usage: persistence.sh RUN" in result.stderr


def test_persistence_export_failure_outranks_the_verdict(bench):
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, **bench.python_stub(PY_EXPORT_FAILS_ONCE))
    assert result.returncode == 4, report(result)
    assert "EXPORT FAILED" in result.stderr


def test_persistence_interrupted_ends_and_does_not_continue(bench):
    # Interrupted while the queue is still being watched: the attempt is
    # marked interrupted and exported, and NOTHING is restarted after it.
    _slice_done(bench)
    hang = Path(str(bench.log) + ".quiescehang")
    process = subprocess.Popen(["bash", str(bench.drivers / "persistence.sh"), G2_RUN],
                               env=bench.env(EGW_STUB_QUIESCE_HANG_S="6"),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 120
    while not hang.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            break
        time.sleep(0.05)
    assert hang.exists(), "the quiesce step never started"
    process.send_signal(signal.SIGTERM)
    stdout, stderr = process.communicate(timeout=300)
    assert process.returncode == 130, f"exit={process.returncode}\n{stdout}\n{stderr}"
    verdicts = bench.verdicts(PERSIST)
    assert verdicts["status"] == "interrupted"
    assert verdicts["system_outcome"] == "interrupted"
    assert "restart-down-up" not in bench.commands(PERSIST)
    assert "down" not in _ssh_log(bench)
    assert bench.package(PERSIST) is not None


def test_persistence_twin_that_vanished_is_the_result_it_is(bench):
    # THE defect this driver exists to find: the restart is shown, the stack
    # comes back and the API answers 404 for the thing, because the volume did
    # not hold it. That is the system failing in front of the check - a valid
    # negative RESULT, exit 1 - and never invalid instrumentation.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="twin-gone")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "the twin's stored state did not survive the restart" in verdicts["reason"]
    assert "the API answered 404 for org.c2dta:stub-device after the restart" in verdicts["reason"]
    assert "the twin was not read through the API after the restart" not in verdicts["reason"]
    assert "RESTART SHOWN" in result.stdout, "the restart was shown before the twin was read"
    assert "not run: events-after stored-state" in verdicts["reason"]
    assert bench.package(PERSIST) is not None


def test_persistence_twin_that_came_back_without_its_state_is_the_result_it_is(bench):
    # The thing is there and the state this run stored in it is not: the same
    # result, read from the body instead of from the code.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="twin-stateless")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "the twin's stored state did not survive the restart" in verdicts["reason"]
    assert "carries no usable ingestion feature" in verdicts["reason"]


def test_persistence_twin_that_could_not_be_read_after_the_restart_is_invalid(bench):
    # The other side of the same rule: nothing answered at all, so no reading
    # was made and nothing is concluded about the stored state.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="twin-unreachable")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) \
        == ("invalid", "inconclusive")
    assert "the twin was not read through the API after the restart" in verdicts["reason"]
    assert "the API was not reached (curl exit 7, HTTP code 000)" in verdicts["reason"]
    assert "did not survive" not in verdicts["reason"]


def test_persistence_twin_that_is_not_there_before_the_restart_restarts_nothing(bench):
    # There is no stored state whose survival a restart could demonstrate: the
    # check does not run as a protocol check, and NOTHING is restarted.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="twin-gone-before")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert verdicts["system_outcome"] == "not-run"
    assert "the twin of itest-g2-01 is not there before the restart" in verdicts["reason"]
    assert "NOTHING was restarted" in verdicts["reason"]
    assert "restart-down-up" not in bench.commands(PERSIST)
    assert "down" not in _ssh_log(bench)


def test_persistence_step_that_never_reached_the_guest_is_not_the_stack_failing(bench):
    # The ssh wrapper itself fails after the restart (the session's helpers are
    # gone): the wait never ran on the guest, so nothing was observed about the
    # six services. 'the guest did not answer' is not 'the stack did not come
    # back', and a sentence with nothing after its colon is neither.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="session-helpers-gone", **NOW)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) \
        == ("invalid", "inconclusive")
    reason = verdicts["reason"]
    assert "the wait never reached the guest" in reason
    assert "came back to 'running' and 'healthy'" not in reason
    assert "not run: metrics-after" in reason


def test_persistence_comparison_that_did_not_run_stops_the_check(bench):
    # 'same' answered neither 0 nor 4: the two snapshots were not compared, so
    # the steps after it cannot be trusted with a verdict and are not run.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="rec-same")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) \
        == ("invalid", "inconclusive")
    assert "the two twin snapshots were not compared" in verdicts["reason"]
    assert "not run: twin-after events-after stored-state" in verdicts["reason"]
    assert "twin-after" not in bench.commands(PERSIST)
    assert "stored-state" not in bench.commands(PERSIST)


def test_persistence_stack_left_down_is_named_in_the_reason_and_on_the_line(bench):
    # 'down' came back and 'up -d' did not: the guest is left without its
    # stack, and that is what the operator has to read first - in the reason,
    # in the next action and on the one final line.
    _slice_done(bench)
    result = bench.run("persistence.sh", G2_RUN, EGW_STUB_FAIL="docker-up")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts(PERSIST)
    assert "THE STACK IS DOWN" in verdicts["reason"]
    assert "did NOT bring it back up" in verdicts["reason"]
    assert "no volume was removed" in verdicts["reason"]
    assert verdicts["next_action"].startswith("STOP: FIRST bring the stack back")
    assert "up -d" in verdicts["next_action"]
    final = result.stdout.strip().splitlines()[-1]
    assert "THE STACK IS DOWN" in final, final


def test_persistence_interrupted_with_the_stack_down_says_so(bench):
    # Interrupted in the one window this driver owns: between 'down' and a
    # 'up -d' that came back. The attempt must say what state the guest is in
    # and what to do about it - an interruption that recorded 'driver
    # interrupted' and nothing else would leave an operator believing the
    # stack is up.
    _slice_done(bench)
    hang = Path(str(bench.log) + ".hang")
    process = subprocess.Popen(["bash", str(bench.drivers / "persistence.sh"), G2_RUN],
                               env=bench.env(EGW_STUB_HANG_S="30"), start_new_session=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 180
    while not hang.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            break
        time.sleep(0.05)
    assert hang.exists(), "the stack was never taken down"
    # The operator's own interrupt reaches the whole group, as Ctrl-C does:
    # ssh and the command it is waiting for die with it.
    os.killpg(os.getpgid(process.pid), signal.SIGINT)
    stdout, stderr = process.communicate(timeout=300)
    assert process.returncode == 130, f"exit={process.returncode}\n{stdout}\n{stderr}"
    verdicts = bench.verdicts(PERSIST)
    assert verdicts["status"] == "interrupted"
    assert "THE STACK" in verdicts["reason"], verdicts["reason"]
    assert "NOTHING was restarted" not in verdicts["reason"]
    assert verdicts["next_action"].startswith("FIRST bring the stack back")
    final = stdout.strip().splitlines()[-1]
    assert "headline=" in final and "interrupted" in final, final
    assert "THE STACK" in final, final
    assert bench.package(PERSIST) is not None


def test_the_wrappers_answer_one_number_for_a_step_that_never_ran():
    # gx, gcp and hx each load something before the step's own command runs.
    # When that loading fails the step never ran, and all three say so with the
    # one number common.sh names.
    common = (SESSION_DIR / "common.sh").read_text(encoding="utf-8")
    shared = (SESSION_DIR / "guest_common.sh").read_text(encoding="utf-8")
    assert "EXIT_NOT_REACHED=97" in common
    assert shared.count("exit 97") == 3, "gx, gcp and hx each answer 97"


def test_readme_names_both_g2_drivers():
    readme = (SESSION_DIR / "README.md").read_text(encoding="utf-8")
    for driver in ("gate_health.sh", "persistence.sh"):
        assert driver in readme, driver
    assert "EGW_HEALTH_LIMIT_S" in readme
    assert "EGW_READY_LIMIT_S" in readme


def _plan(bench: Bench, run_id: str = "nominal-r01", seed: int = 7) -> None:
    _write(bench.home / "egw-tcg" / "pilot" / "campaign_plan.json",
           json.dumps({"runs": [{"run_id": run_id, "seed": seed, "condition": "nominal"}]}, indent=2))


def test_nominal_valid_negative_ends_one(bench):
    _plan(bench)
    late = json.dumps({"sent_valid": 6720, "delivered_unique": 6720, "lost": 0, "late_confirmations": 2926})
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_HARNESS_ROW=late)
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert bench.package("nominal-instrumentation-120-600") is not None
    assert "NOMINAL nominal-r01: validity=valid outcome=fail" in result.stdout


def test_nominal_passes_when_every_message_is_in_time(bench):
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01")
    assert result.returncode == 0, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")


def test_nominal_failed_accounting_never_becomes_not_run(bench):
    # The accounting is the analysis AFTER the sealed window: one that could
    # not be produced leaves the delivery unjudged (inconclusive, exit 3) and
    # is recorded as an incomplete observation. It does not make the window
    # the harness already sealed invalid, and it is never 'not-run'.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="accounting")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert verdicts["system_outcome"] == "inconclusive"
    assert verdicts["instrumentation_validity"] == "valid"
    assert "the identity accounting could not be produced" in verdicts["reason"]
    assert "post-window observation(s) incomplete:" in verdicts["reason"]
    assert "evidence requirement(s) not met" not in verdicts["reason"]
    assert "harness-run" in bench.commands("nominal-instrumentation-120-600")
    assert bench.package("nominal-instrumentation-120-600") is not None


def test_nominal_precondition_failure_did_not_start_the_harness(bench):
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="drained")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert verdicts["system_outcome"] == "not-run"
    assert "harness-run" not in bench.commands("nominal-instrumentation-120-600")


def test_nominal_refuses_a_collector_that_is_not_the_clones(bench):
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_SCP_CORRUPT="collect-resources.sh")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert verdicts["system_outcome"] == "not-run"
    assert "not the clean clone's" in verdicts["reason"]
    assert "harness-run" not in bench.commands("nominal-instrumentation-120-600")


def test_nominal_invalid_manifest_is_invalid(bench):
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_MANIFEST_VALIDITY="invalid")
    assert result.returncode == 3, report(result)
    assert bench.verdicts("nominal-instrumentation-120-600")["instrumentation_validity"] == "invalid"


def test_nominal_export_failure_keeps_the_attempt(bench):
    _plan(bench)
    shutil.rmtree(bench.out)
    bench.out.write_text("not a directory\n", encoding="utf-8")
    result = bench.run("nominal.sh", "nominal-r01")
    assert result.returncode == 4, report(result)
    assert "local_export recover" in result.stderr
    assert (bench.attempt("nominal-instrumentation-120-600") / "attempt.json").is_file()


def test_nominal_keeps_the_snapshots_in_the_package(bench):
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01")
    assert result.returncode == 0, report(result)
    package = bench.package("nominal-instrumentation-120-600")
    kept = sorted(p.name for p in (package / "analysis" / "snapshots").iterdir())
    assert kept == ["nominal-r01.metrics.after.json", "nominal-r01.metrics.before.json",
                    "nominal-r01.twins.after.json", "nominal-r01.twins.before.json"]


def test_nominal_snapshots_that_did_not_reach_the_package_are_mandatory(bench):
    # The copy is the ONLY path by which the mandatory 'pre' and
    # 'after-snapshots' evidence reaches output_test.
    _plan(bench)
    _write(bench.bin / "mkdir", """#!/bin/sh
for a in "$@"; do
    case "$a" in
        */analysis/snapshots)
            echo "mkdir: cannot create directory '$a': No space left on device" >&2
            exit 1
            ;;
    esac
done
exec /bin/mkdir "$@"
""", executable=True)
    result = bench.run("nominal.sh", "nominal-r01")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "snapshots were not copied into the package" in verdicts["reason"]
    assert "after-snapshots" in bench.commands("nominal-instrumentation-120-600")


# --------------------------------------------------------------------------
# nominal.sh: a system that failed is not a measurement that failed
#
# The five verifications of the project manager's follow-up of 2026-09-20,
# section 4, all on this stub bench and with no guest run.
# --------------------------------------------------------------------------

#: A fault the measured run positively SHOWS, and the sentence the comparison
#: of the two guest-state records prints for it.
OBSERVED_FAULTS = [
    ("service-oomkilled", "was OOM-killed"),
    ("service-restarted", "restarted during the run"),
    ("oom", "memory-cgroup OOM lines"),
    # A container destroyed and recreated during the measured window answers
    # 'false' and '0' again on the new object, so the pair is what shows it;
    # one that is gone after the run is in no 'after' line at all.
    ("service-recreated", "was replaced during the run"),
    ("service-gone", "was running before the run and is not listed after it"),
    # A container restarted IN PLACE keeps its object, so its id and its
    # RestartCount (which Docker increments from the restart policy) are the
    # same on both sides: without the instant it last started, the two records
    # are identical and the run reads as untouched.
    ("service-restarted-in-place", "it started again at"),
]


@pytest.mark.parametrize("failure, says", OBSERVED_FAULTS)
def test_nominal_observed_fault_with_complete_evidence_is_a_valid_negative(bench, failure, says):
    # Verification 1. A container OOM-killed, restarted, replaced or lost
    # while the window was being measured is what the run OBSERVED: the
    # evidence is complete and trustworthy and the SYSTEM is what failed.
    # Declaring the instrumentation invalid here would discard exactly the
    # negative result this work has to analyse.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL=failure)
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "observed system fault(s): a container was OOM-killed or restarted" in verdicts["reason"]
    assert "evidence requirement(s) not met" not in verdicts["reason"]
    assert says in result.stdout
    assert "NOMINAL nominal-r01: validity=valid outcome=fail" in result.stdout
    assert "observed=1 mandatory=0 incomplete=0" in result.stdout
    assert bench.package("nominal-instrumentation-120-600") is not None


@pytest.mark.parametrize("overrides, says", [
    # The controller marker the confirmation deadline is measured from was
    # never read: there is no clock domain to judge a 60 s window in.
    ({"EGW_STUB_CONTROLLER_MARKER": '{"ok": false, "error": "GET /metrics failed"}'},
     "controller_marker.ok is False"),
    # The deadline did not come from that marker at all.
    ({"EGW_STUB_DEADLINE_SOURCE": "event-derived-legacy"},
     "confirmation_deadline_source is event-derived-legacy, not controller-marker"),
])
def test_nominal_observed_fault_with_a_broken_clock_domain_is_invalid(bench, overrides, says):
    # Verification 2. The same class of fault, and a real defect of the clock
    # domain the deadline rests on: THAT is invalid instrumentation, the reason
    # names the requirement rather than the fault, and the fault is kept as a
    # fact - never as a successful system outcome.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="service-oomkilled", **overrides)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "fail")
    assert "observed system fault(s): a container was OOM-killed or restarted" in verdicts["reason"]
    assert "evidence requirement(s) not met: the clock domain the confirmation deadline rests on " \
           "is not intact" in verdicts["reason"]
    assert says in verdicts["reason"]
    assert bench.package("nominal-instrumentation-120-600") is not None


def test_nominal_observed_fault_with_a_lost_capture_is_invalid(bench):
    # Verification 2, the mandatory-capture variant: the console record of a
    # step is incomplete, so the evidence requirement is what failed. The fault
    # the run showed is still recorded and the outcome is still a failure.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="service-oomkilled",
                       **bench.fail_capture_of("post-drain"))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "fail")
    assert "observed system fault(s): a container was OOM-killed or restarted" in verdicts["reason"]
    assert "the console capture of 'post-drain' failed" in verdicts["reason"]


def test_nominal_a_guest_state_record_that_is_not_trusted_shows_no_fault(bench):
    # The guest answered, but the console capture of that answer failed, so the
    # record may hold part of it. What the comparison then reports about the
    # containers was not established: it is named as evidence that failed, with
    # the sentences it printed, and never as a fault the run showed.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="service-oomkilled",
                       **bench.fail_capture_of("guest-state-after"))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "observed system fault(s)" not in verdicts["reason"]
    assert "was not established" in verdicts["reason"]
    assert "was OOM-killed" in verdicts["reason"]


def test_nominal_drain_that_timed_out_keeps_the_measured_verdict(bench):
    # Verification 3. The harness sealed the measured window; only the drain
    # after it never went quiet. The drain GAVE UP - it watched the queue for
    # its whole limit and reported so - which is a fault the run showed and an
    # observation that is incomplete, never a reason to discard the window, and
    # nothing claims eventual delivery or a complete tail.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="post-drain")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert ("observed system fault(s): the drain after the run did not report a quiet window "
            "(post-drain exit 1)") in verdicts["reason"]
    assert "evidence requirement(s) not met" not in verdicts["reason"]
    assert ("post-window observation(s) incomplete: the drain after the run did not complete, "
            "so no eventual delivery and no complete tail is claimed") in verdicts["reason"]
    assert verdicts["post_window_observations"].startswith("incomplete: the drain after the run")
    # The fault is read from what the drain itself reported, so the record the
    # package keeps holds that sentence.
    assert "no quiet window of 130 s within 1500 s" in _console(
        bench, "nominal-instrumentation-120-600", "post-drain", "stderr")
    # The precondition's own drain, before the harness, is untouched: the run
    # was measured, which is why its verdict is kept.
    assert "harness-run" in bench.commands("nominal-instrumentation-120-600")
    assert bench.package("nominal-instrumentation-120-600") is not None


@pytest.mark.parametrize("failure, records", [
    # The drain's OTHER stop: it could not read /metrics at all, which is what
    # a tunnel that dropped, a refused connection or a controller that is no
    # longer there leaves. Nothing was observed about the queue.
    ("post-drain-unreachable", "GET http://127.0.0.1:8000/metrics failed"),
    # The step died in the transport, before any reading: the queue was never
    # watched at all.
    ("post-drain-dropped", "Connection refused"),
])
def test_nominal_drain_that_observed_nothing_is_not_a_fault(bench, failure, records):
    # The post-drain step runs over the tunnel, so its status alone says
    # nothing about the queue. A step that ended non-zero without the drain's
    # own give-up observed NOTHING, and writing it into the evidence as "the
    # drain did not report a quiet window" would record, as a fault of the
    # gateway, a dropped connection: the tail is simply unobserved, which is an
    # incomplete post-window observation and leaves the sealed window intact.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL=failure)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid",
                                                                                 "inconclusive")
    assert "observed system fault(s)" not in verdicts["reason"], verdicts["reason"]
    assert "did not report a quiet window" not in verdicts["reason"], verdicts["reason"]
    assert "evidence requirement(s) not met" not in verdicts["reason"]
    assert ("post-window observation(s) incomplete: the drain after the run did not complete, "
            "so no eventual delivery and no complete tail is claimed") in verdicts["reason"]
    assert records in _console(bench, "nominal-instrumentation-120-600", "post-drain", "stderr")
    assert "harness-run" in bench.commands("nominal-instrumentation-120-600")
    assert bench.package("nominal-instrumentation-120-600") is not None


def test_nominal_guest_state_after_that_cannot_be_read_is_invalid(bench):
    # Verification 4. 'docker inspect' answers nothing after the run, so the
    # record of the guest state after it is not usable and the two records
    # cannot be compared: mandatory evidence is missing, the instrumentation is
    # invalid, and a PASS cannot be asserted on it.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="state-unreadable")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive", "a pass is not asserted on missing evidence"
    assert "evidence requirement(s) not met" in verdicts["reason"]
    assert "the guest state after the run was not recorded" in verdicts["reason"]
    assert "the two guest states could not be compared (guest-state-delta exit 2)" in verdicts["reason"]
    assert "observed system fault(s)" not in verdicts["reason"], "nothing was observed here"
    assert bench.package("nominal-instrumentation-120-600") is not None


def test_nominal_fault_survives_a_comparison_that_could_not_be_made(bench):
    # The pair of records shows a container the kernel OOM-killed AND is
    # missing the instant another one last started, so the comparison itself
    # could not be completed (exit 2). Both are recorded, each in its own
    # group: the fault the run positively showed never disappears because
    # something else was indeterminate.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01",
                       EGW_STUB_FAIL="service-oomkilled,state-unreadable")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "fail")
    assert "observed system fault(s): a container was OOM-killed or restarted" in verdicts["reason"]
    assert "egw-ditto-policies-1 was OOM-killed (OOMKilled=true)" in verdicts["reason"], (
        "the package's own record names what was seen, not only that something was")
    assert ("evidence requirement(s) not met: the guest state after the run was not recorded"
            in verdicts["reason"])
    assert "the two guest states could not be compared (guest-state-delta exit 2)" in verdicts["reason"]
    assert bench.package("nominal-instrumentation-120-600") is not None


#: A comparison that fails before it judges anything: Python's own status for
#: an unhandled exception is 1, which is the status of a fault the pair SHOWED.
DELTA_THAT_CRASHED = '''"""A guest_state_delta.py that crashes: no verdict, and Python's exit 1."""
print("## faults: what the system did during the measured run")
raise RuntimeError("the comparison itself failed")
'''

#: One that ends 1 while its own summary line says it saw nothing: what it
#: printed is not a verdict it reached either.
DELTA_THAT_DISAGREES = '''"""A guest_state_delta.py whose summary does not agree with its status."""
print("## faults: what the system did during the measured run")
print("none")
print("guest-state-delta: faults=0 problems=0")
raise SystemExit(1)
'''


@pytest.mark.parametrize("helper", [DELTA_THAT_CRASHED, DELTA_THAT_DISAGREES],
                         ids=["crashed", "summary-disagrees"])
def test_nominal_comparison_it_cannot_trust_is_not_an_observed_fault(bench, helper):
    # The comparison exited 1 without reaching a verdict of its own. Read as
    # "a fault was observed", that would record an OOM kill or a restart that
    # nobody saw and bury the evidence failure behind it: a status whose
    # summary line is absent or disagrees is a pair that could NOT be compared,
    # which is mandatory evidence missing.
    _plan(bench)
    _write(bench.drivers / "guest_state_delta.py", helper)
    result = bench.run("nominal.sh", "nominal-r01")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid",
                                                                                 "inconclusive")
    assert "observed system fault(s)" not in verdicts["reason"], "nothing was observed here"
    assert ("evidence requirement(s) not met: the two guest states could not be compared "
            "(guest-state-delta exit 1: the comparison itself failed") in verdicts["reason"]
    assert bench.package("nominal-instrumentation-120-600") is not None


def _argv(bench: Bench, slug: str, step: str) -> list[str]:
    """The argv commands.jsonl recorded for one step of an attempt."""
    path = bench.attempt(slug) / "commands.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    found = [record for record in records if record["name"] == step]
    assert found, f"{step} is not in commands.jsonl"
    return found[-1]["argv"]


@pytest.mark.parametrize("overrides, told, tail, code", [
    ({}, "fetched", "every published identity accounted", 0),
    ({"EGW_STUB_SCP_FAIL": "/nominal-r01/events.jsonl"}, "not-fetched", None, 3),
])
def test_nominal_tells_the_accounting_whether_the_tail_was_fetched(bench, overrides, told, tail,
                                                                   code):
    # Whether the post-drain log was fetched is what THIS driver knows, and the
    # accounting is told it: a transfer that died mid-way leaves a file behind,
    # and a file on disk read as a complete tail publishes a tail nobody
    # observed. What it is told is what it acts on - the accounting publishes no
    # figure of a tail it was not told was fetched - so this is what the driver
    # passing the wrong thing would change in the package.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", **overrides)
    assert result.returncode == code, report(result)
    assert _argv(bench, "nominal-instrumentation-120-600", "identity-accounting")[-1] == told
    written = json.loads((bench.attempt("nominal-instrumentation-120-600") / "analysis"
                          / "accounting.json").read_text(encoding="utf-8"))
    assert (written["after_drain_fetch"], written["after_drain"]) == (told, tail)


def test_nominal_tells_the_accounting_when_the_fetch_result_could_not_be_read(bench):
    # The console record of the fetch was lost, so its own result is not
    # readable here: the driver says as much rather than either claim, and no
    # figure of that tail is published from the file it left.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01",
                       **bench.fail_capture_of("fetch-post-drain-events"))
    assert result.returncode == 3, report(result)
    assert _argv(bench, "nominal-instrumentation-120-600", "identity-accounting")[-1] == "unknown"


def test_nominal_reads_no_verdict_from_an_accounting_that_failed(bench):
    # The accounting wrote a complete-looking accounting.json and then exited
    # non-zero. A verdict is never derived from the output of a step that
    # failed: the delivery row and the clock domain the 60 s deadline rests on
    # are unknown, so they are not read, and the run is not sealed as a pass on
    # bytes nobody can vouch for.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="accounting-late")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid",
                                                                                 "inconclusive")
    assert ("the identity accounting did not complete, so the delivery row and the clock domain "
            "were not read") in verdicts["reason"]
    assert "the identity accounting could not be produced (exit 1)" in verdicts["reason"]
    assert "sent_valid 6720" not in verdicts["reason"], "no figure is read out of that file"
    assert "evidence requirement(s) not met" not in verdicts["reason"], (
        "the sealed window is not invalidated by an analysis made after it")


def test_nominal_pass_needs_complete_post_window_evidence(bench):
    # The delivery row itself passes, but the warm-up event log was never
    # fetched: a post-window observation is missing, so a clean pass cannot be
    # asserted. The measured window's own validity is untouched, the outcome is
    # inconclusive (exit 3, so nothing dependent proceeds) and the reason names
    # what is missing.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_SCP_FAIL=".warmup")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid",
                                                                                 "inconclusive")
    assert "the warm-up event log was not fetched" in verdicts["reason"]
    assert "post-window observation(s) incomplete:" in verdicts["reason"]
    assert "evidence requirement(s) not met" not in verdicts["reason"]
    assert "observed system fault(s)" not in verdicts["reason"]
    assert bench.package("nominal-instrumentation-120-600") is not None


def test_nominal_observed_fault_outranks_a_delivery_row_that_could_not_be_read(bench):
    # A container was OOM-killed during the run and the accounting could not be
    # produced. The fault is the system outcome - a failure that was observed
    # is not lowered to "undecided" because something else was not read - and
    # the reason says that the delivery figures were not read.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="service-oomkilled,accounting")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert "observed system fault(s): a container was OOM-killed or restarted" in verdicts["reason"]
    assert ("the identity accounting did not complete, so the delivery row and the clock domain "
            "were not read") in verdicts["reason"]
    assert "evidence requirement(s) not met" not in verdicts["reason"]


def test_nominal_delivery_row_without_its_four_figures_is_not_a_pass(bench):
    # A row that carries no sent_valid and no delivered_unique satisfied
    # "delivered == sent" through two absent counts. The four figures must be
    # whole numbers before any pass: anything else leaves the delivery
    # unjudged, with the fields that are missing named.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01",
                       EGW_STUB_HARNESS_ROW=json.dumps({"lost": 0, "late_confirmations": 0}))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid",
                                                                                 "inconclusive")
    assert ("the row does not carry sent_valid, delivered_unique as whole numbers, so the "
            "delivery was not judged") in verdicts["reason"]
    assert "the delivery of the measured window was not judged" in verdicts["reason"]
    # What the delivery row says is stated ONCE, at the end of the reason: the
    # incomplete group carries the consequence, not a second copy of it.
    assert verdicts["reason"].count("delivery at the harness fetch:") == 1, verdicts["reason"]


def _account_capsule(tmp_path: Path) -> Path:
    """A sealed raw run directory with three published identities, one of which
    the harness fetch confirmed before the deadline."""
    raw = tmp_path / "raw" / "nominal-r01"
    _write(raw / "manifest.json", json.dumps({"run_id": "nominal-r01", "validity": "valid",
                                              "confirmation_deadline_monotonic_ns": 10 ** 12}))
    _write(raw / "sent_events.jsonl", "".join(
        json.dumps({"message_id": f"m-{i}", "device_uuid": "stub-device",
                    "device_type": "smartwatch", "seq": i, "run_id": "nominal-r01"}) + "\n"
        for i in range(3)))
    _write(raw / "events.jsonl", json.dumps(
        {"message_id": "m-0", "run_id": "nominal-r01", "outcome": "accepted",
         "ditto_ack_monotonic_ns": 5 * 10 ** 11}) + "\n")
    return raw


def _account(raw: Path, post: Path, out: Path, *told: str) -> subprocess.CompletedProcess:
    """The real accounting helper; `told` is what the driver says about its own
    fetch of the post-drain log ('fetched', 'not-fetched', or nothing at all)."""
    return subprocess.run(
        [sys.executable, str(SESSION_DIR / "nominal_account.py"), str(raw), str(post), str(out), *told],
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}, capture_output=True, text=True)


def test_nominal_account_does_not_invent_a_tail_it_did_not_fetch(tmp_path):
    # The real accounting helper, on a capsule whose post-drain log was never
    # fetched: a log that is not there is not an empty one, so every figure of
    # that tail is null and named as not fetched. Counting each published
    # identity as "no outcome" against it would publish a tail nobody observed,
    # and that count is exactly what this dissertation reports.
    raw = _account_capsule(tmp_path)
    result = _account(raw, tmp_path / "never-fetched.jsonl", tmp_path / "analysis")
    assert result.returncode == 0, report(result)
    written = json.loads((tmp_path / "analysis" / "accounting.json").read_text(encoding="utf-8"))
    for field in ("after_drain", "after_drain_per_device", "events_records_after_drain",
                  "accepted_without_ack_instant_after_drain"):
        assert written[field] is None, field
    assert "was not fetched" in written["after_drain_note"]
    assert "after the drain: the post-drain event log was not fetched" in result.stdout
    # What WAS fetched is still accounted for, unchanged.
    assert written["at_harness_fetch"]["accepted_in_time"] == 1
    assert written["events_records_at_fetch"] == 1


def test_nominal_account_does_not_report_as_fetched_a_tail_that_is_not_there(tmp_path):
    # The driver says its fetch succeeded and the log is not at the path it
    # names - a file removed, a path that never was, a transfer that reported
    # success and wrote nothing. What is published is what was FOUND: reporting
    # 'fetched' beside a tail of nulls would say that a log was read and that
    # nothing was in it.
    raw = _account_capsule(tmp_path)
    result = _account(raw, tmp_path / "never-arrived.jsonl", tmp_path / "analysis", "fetched")
    assert result.returncode == 0, report(result)
    written = json.loads((tmp_path / "analysis" / "accounting.json").read_text(encoding="utf-8"))
    assert written["after_drain_fetch"] == "not-found"
    assert "is not there" in written["after_drain_note"]
    for field in ("after_drain", "after_drain_per_device", "events_records_after_drain",
                  "accepted_without_ack_instant_after_drain"):
        assert written[field] is None, field
    assert "no tail after the drain was found" in result.stdout


def test_nominal_account_does_not_read_a_partial_tail_as_a_complete_one(tmp_path):
    # A transfer that died mid-way leaves a file behind, and the file being on
    # disk is not the fact that it was fetched: the driver's own fetch is what
    # says so. A partial tail read as the whole of it would publish, as "no
    # outcome after the drain", identities whose records simply never arrived.
    raw = _account_capsule(tmp_path)
    post = _write(tmp_path / "events.post-drain.jsonl", json.dumps(
        {"message_id": "m-1", "run_id": "nominal-r01", "outcome": "accepted",
         "ditto_ack_monotonic_ns": 2 * 10 ** 12}) + "\n")
    result = _account(raw, post, tmp_path / "analysis", "not-fetched")
    assert result.returncode == 0, report(result)
    written = json.loads((tmp_path / "analysis" / "accounting.json").read_text(encoding="utf-8"))
    for field in ("after_drain", "after_drain_per_device", "events_records_after_drain",
                  "accepted_without_ack_instant_after_drain"):
        assert written[field] is None, field
    assert written["after_drain_fetch"] == "not-fetched"
    assert "may be a partial tail" in written["after_drain_note"]
    assert "may be a partial tail" in result.stdout
    # The same file, once the driver says its own fetch succeeded, IS the tail.
    complete = _account(raw, post, tmp_path / "fetched", "fetched")
    assert complete.returncode == 0, report(complete)
    tail = json.loads((tmp_path / "fetched" / "accounting.json").read_text(encoding="utf-8"))
    assert tail["after_drain"] == {"accepted_late": 1, "no_outcome": 2}
    assert tail["after_drain_note"] is None
    # A caller that says nothing claims nothing: the log is reported as it was
    # found, and the record says that is what these figures are.
    unstated = _account(raw, post, tmp_path / "unstated")
    assert unstated.returncode == 0, report(unstated)
    silent = json.loads((tmp_path / "unstated" / "accounting.json").read_text(encoding="utf-8"))
    assert silent["after_drain_fetch"] == "unstated"
    assert "as it was found on disk" in silent["after_drain_note"]
    # A fetch whose own result could not be read establishes nothing either.
    lost = _account(raw, post, tmp_path / "unknown", "unknown")
    assert lost.returncode == 0, report(lost)
    unread = json.loads((tmp_path / "unknown" / "accounting.json").read_text(encoding="utf-8"))
    assert unread["after_drain"] is None
    assert "could not be established" in unread["after_drain_note"]


def _documented_path(bench: Bench, path: str):
    """One of the five documented driver paths: (driver, arguments, overrides)."""
    late = json.dumps({"sent_valid": 6720, "delivered_unique": 6720, "lost": 0,
                       "late_confirmations": 2926})
    if path == "clean-pass":
        return "nominal.sh", ("nominal-r01",), {}
    if path == "valid-negative-delivery":
        return "nominal.sh", ("nominal-r01",), {"EGW_STUB_HARNESS_ROW": late}
    if path == "lost-capture":
        return "nominal.sh", ("nominal-r01",), bench.fail_capture_of("harness-run")
    if path == "failed-export":
        shutil.rmtree(bench.out)
        bench.out.write_text("not a directory\n", encoding="utf-8")
        return "nominal.sh", ("nominal-r01",), {}
    return "guest_session_close.sh", (), {"EGW_STUB_FAIL": "session-close"}


@pytest.mark.parametrize("path, expected", [
    ("clean-pass", 0),
    ("valid-negative-delivery", 1),
    ("lost-capture", 3),
    ("failed-export", 4),
    ("failed-controlled-stop", 5),
])
def test_the_documented_driver_paths_keep_their_codes(bench, path, expected):
    # Verification 5: the classification above moves nothing else. Each of the
    # five documented paths still ends with the code README.md gives it.
    _plan(bench)
    driver, arguments, overrides = _documented_path(bench, path)
    result = bench.run(driver, *arguments, **overrides)
    assert result.returncode == expected, report(result)


def test_nominal_records_every_expected_container_in_both_states(bench):
    # The comparison is given the six expected services, so a guest state that
    # names fewer of them is a problem of its own, and the records carry the
    # container id that tells a replaced object from a restarted one and the
    # instant it last started, which is all a restart in place moves.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01")
    assert result.returncode == 0, report(result)
    attempt = bench.attempt("nominal-instrumentation-120-600")
    for label in ("before", "after"):
        state = next(attempt.glob(f"console/*-guest-state-{label}.stdout.txt")).read_text(
            encoding="utf-8")
        for service in EXPECT_SERVICES:
            assert f"container {service} oomkilled=false restarts=0 id=" in state, (label, service)
        assert state.count(" started=2026-") == len(EXPECT_SERVICES), label
        assert "unknown" not in state, label
    assert "guest-state-delta: faults=0 problems=0" in result.stdout


def test_nominal_package_without_a_declared_artefact_is_not_a_pass(bench):
    # The run itself is sound and the export exits 0, but the package was
    # sealed without one of the artefacts the attempt declared: the export
    # says so in the receipt, and the driver's final line must not claim
    # "package exported and verified" for it.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_HARNESS_SKIP="events.jsonl")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert "package=INCOMPLETE" in result.stdout
    assert "declared expected artefact(s)" in result.stdout
    assert "package exported and verified" not in result.stdout
    assert bench.package("nominal-instrumentation-120-600") is not None, (
        "the package IS in output_test: what is missing is part of its evidence")


def test_nominal_unreadable_dmesg_before_the_run_stops_it(bench):
    # The OOM state of the boot is UNKNOWN, which is not "no OOM": there is no
    # baseline to compare the run against, so the harness is not started.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="dmesg")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert verdicts["system_outcome"] == "not-run"
    assert "harness-run" not in bench.commands("nominal-instrumentation-120-600")


def test_nominal_without_its_argument_is_a_prerequisite(bench):
    result = bench.run("nominal.sh")
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2" in result.stdout
    assert "usage: nominal.sh RUN_ID" in result.stderr


def test_nominal_with_an_unusable_git_does_not_run(bench):
    # git refusing (dubious ownership, an unreadable .git) leaves the clone's
    # commit unknown: that is never recorded as a clean clone at no commit.
    _plan(bench)
    result = bench.run("nominal.sh", "nominal-r01", EGW_STUB_FAIL="git")
    assert result.returncode == 2, report(result)
    verdicts = bench.verdicts("nominal-instrumentation-120-600")
    assert verdicts["system_outcome"] == "not-run"
    assert "identity of the clean clone" in verdicts["reason"]
    assert verdicts["identities"]["repo_commit"] is None
    assert verdicts["identities"]["repo_dirty_lines"] is None
    assert "git rev-parse" in verdicts["identities"]["identity_error"]
    assert "harness-run" not in bench.commands("nominal-instrumentation-120-600")


def _console(bench: Bench, slug: str, step: str, stream: str = "stdout") -> str:
    """What one step of an attempt printed, as the package keeps it."""
    found = sorted((bench.attempt(slug) / "console").glob(f"*-{step}.{stream}.txt"))
    assert found, f"no console record of {step}"
    return found[-1].read_text(encoding="utf-8")


def test_session_close_passes_and_exports(bench):
    result = bench.run("guest_session_close.sh")
    assert result.returncode == 0, report(result)
    verdicts = bench.verdicts("guest-session")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("not-applicable", "pass")
    assert bench.package("guest-session") is not None
    assert not (bench.exec_dir / "current_session").exists()
    # The artefacts record says what is true of the machine. 'pgrep -f' matches
    # full command lines, so the same test inside the step would match the
    # step's own 'bash -c' and never report a closed guest.
    record = _console(bench, "guest-session", "artefacts-after-poweroff")
    assert "no qemu process left" in record
    assert "STILL running" not in record


def test_session_close_artefacts_that_were_not_recorded_are_incomplete(bench):
    # The rootfs the session booted was renamed by a rebuild (its name carries
    # the build stamp), so it cannot be hashed. The step is a list of commands
    # and used to be decided by the last of them, which could not fail.
    result = bench.run("guest_session_close.sh",
                       EGW_YOCTO_CHECKOUT=str(bench.tmp / "no-such-checkout"))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("guest-session")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "the artefacts after the power-off were not recorded" in verdicts["reason"]
    assert "session closed: stack stopped" not in verdicts["reason"]
    assert bench.package("guest-session") is not None
    assert not (bench.exec_dir / "current_session").exists(), "the guest IS off"


def test_session_close_data_disk_that_cannot_be_listed_is_incomplete(bench):
    result = bench.run("guest_session_close.sh",
                       EGW_DATA_DISK=str(bench.tmp / "no-such-data-disk.img"))
    assert result.returncode == 3, report(result)
    assert "the artefacts after the power-off were not recorded" in (
        bench.verdicts("guest-session")["reason"])


def test_session_close_record_that_was_not_kept_is_not_a_failed_stop(bench):
    # guest/session_close.sh powered the guest off and could not keep the boot
    # journal or the final guest state (exit 3): the record of the close is
    # incomplete (3), never "the controlled stop failed" (5).
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="session-close-record")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("guest-session")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "a record of the close was not kept" in verdicts["reason"]
    assert "the controlled stop failed" not in verdicts["reason"]
    assert "journal and final state kept" not in verdicts["reason"]


def test_session_close_failed_controlled_stop_ends_five(bench):
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="session-close")
    assert result.returncode == 5, report(result)
    verdicts = bench.verdicts("guest-session")
    assert verdicts["system_outcome"] == "fail"
    assert "the controlled power-off failed" in verdicts["reason"]
    assert bench.package("guest-session") is not None


def test_session_close_failed_stack_stop_ends_five(bench):
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="stack-stop")
    assert result.returncode == 5, report(result)
    assert "the stack was not stopped" in bench.verdicts("guest-session")["reason"]


@pytest.mark.parametrize("step", ["stack-stop", "oom-before-poweroff", "session-close"])
def test_session_close_lost_capture_is_not_a_failed_stop(bench, step):
    # The step's own command ran: the stack WAS stopped and the guest WAS
    # powered off, and only the console record of it was lost (74). The close
    # is then an incomplete record (3), never "the controlled stop failed" (5).
    result = bench.run("guest_session_close.sh", **bench.fail_capture_of(step))
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("guest-session")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert f"the console capture of '{step}' failed" in verdicts["reason"]
    assert "the controlled stop failed" not in verdicts["reason"]
    assert "the session IS closed" in verdicts["next_action"]
    assert bench.package("guest-session") is not None
    assert not (bench.exec_dir / "current_session").exists()


def test_session_close_failed_stop_outranks_a_lost_capture(bench):
    # When the stop itself failed too, that is what the session is sealed with.
    over = bench.fail_capture_of("oom-before-poweroff")
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="session-close", **over)
    assert result.returncode == 5, report(result)
    verdicts = bench.verdicts("guest-session")
    assert verdicts["system_outcome"] == "fail"
    assert "the controlled stop failed" in verdicts["reason"]
    assert "the console capture of 'oom-before-poweroff' failed" in verdicts["reason"]


def test_session_close_keeps_the_session_while_qemu_runs(bench):
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="qemu-left")
    assert result.returncode == 5, report(result)
    assert (bench.exec_dir / "current_session").exists(), "current_session must survive a guest still running"
    assert "still running" in bench.verdicts("guest-session")["reason"]
    # And the record says the same thing as the verdict on the same attempt.
    record = _console(bench, "guest-session", "artefacts-after-poweroff")
    assert "a qemu-system-aarch64 process is STILL running" in record
    assert "no qemu process left" not in record


def test_session_close_pgrep_that_cannot_answer_keeps_the_session(bench):
    # pgrep answers 1 for "no match", but 2 or more when it could not answer at
    # all (an unreadable /proc, a procps that is not there). Reading that as
    # "no qemu process left" seals a guest that may still be UP as a closed
    # session, deletes the only record of it and writes an answer the driver
    # never established into the evidence.
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="pgrep-error")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("guest-session")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "could not be decided (pgrep exit 2)" in verdicts["reason"]
    assert "no qemu-system-aarch64 process is left" not in verdicts["reason"]
    assert "the guest is off" not in verdicts["reason"]
    assert "the session IS closed" not in verdicts["next_action"]
    assert (bench.exec_dir / "current_session").exists(), "a guest that may be up stays recorded"
    record = _console(bench, "guest-session", "artefacts-after-poweroff")
    assert "is UNKNOWN: pgrep exited 2" in record
    assert "no qemu process left" not in record
    assert bench.package("guest-session") is not None


def test_session_close_unreadable_dmesg_ends_five(bench):
    # The OOM state of the boot could not be read at all: that is an evidence
    # failure of the controlled close, and it keeps the 5 it has always had.
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="dmesg")
    assert result.returncode == 5, report(result)
    verdicts = bench.verdicts("guest-session")
    assert "OOM state of this boot could not be read" in verdicts["reason"]
    assert "observed system fault(s)" not in verdicts["reason"]


def test_session_close_observed_oom_is_a_system_failure_not_a_failed_close(bench):
    # The close read the record correctly and it says the kernel OOM-killed
    # something in this boot. The session IS closed and its record is complete:
    # what failed is the system, which is a valid negative result (1), never a
    # failed controlled stop (5) and never invalid instrumentation (3).
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="oom")
    assert result.returncode == 1, report(result)
    verdicts = bench.verdicts("guest-session")
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == (
        "not-applicable", "fail")
    assert "observed system fault(s) during this session:" in verdicts["reason"]
    assert "memory-cgroup OOM line(s) in this boot" in verdicts["reason"]
    assert "the controlled stop failed" not in verdicts["reason"]
    assert "journal and final state kept" in verdicts["reason"]
    record = _console(bench, "guest-session", "oom-before-poweroff")
    assert "Memory cgroup out of memory" in record
    assert "memory-cgroup OOM lines: 1" in record
    assert "no memory-cgroup OOM in this boot" not in record
    assert bench.package("guest-session") is not None
    assert not (bench.exec_dir / "current_session").exists(), "the guest IS off"


def test_session_close_observed_oom_with_an_incomplete_record_is_invalid(bench):
    # The OOM was observed AND the record of the close is incomplete: the
    # instrumentation is what is invalid (3), while the fault stays the system
    # outcome and is never softened into 'inconclusive'.
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="oom,session-close-record")
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("guest-session")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "fail"
    assert "memory-cgroup OOM line(s) in this boot" in verdicts["reason"]
    assert "a record of the close was not kept" in verdicts["reason"]


def test_session_close_failed_stop_outranks_an_observed_oom(bench):
    # When the controlled stop itself failed, that is what the session is
    # sealed with (5), and the observed OOM is still named in the reason.
    result = bench.run("guest_session_close.sh", EGW_STUB_FAIL="oom,session-close")
    assert result.returncode == 5, report(result)
    verdicts = bench.verdicts("guest-session")
    assert verdicts["system_outcome"] == "fail"
    assert "memory-cgroup OOM line(s) in this boot" in verdicts["reason"]
    assert "the controlled stop failed" in verdicts["reason"]


def test_session_close_interrupted_marks_and_exports_the_session(bench):
    # The stop and the power-off are the long steps of a TCG session, so an
    # interrupt there is the realistic one: the session attempt holds boot/,
    # guest/, host/ and every console record of the whole session.
    _write(bench.session / "scripts" / "session_close.sh",
           '#!/bin/sh\necho "stub: powering the guest off" > "$EGW_STUB_LOG.poweroff"\n'
           'sleep 60\nexit 0\n', executable=True)
    started = Path(str(bench.log) + ".poweroff")
    process = subprocess.Popen(["bash", str(bench.drivers / "guest_session_close.sh")],
                               env=bench.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    deadline = time.monotonic() + 300
    while not started.exists() and time.monotonic() < deadline and process.poll() is None:
        time.sleep(0.05)
    assert started.exists(), "the controlled power-off never started"
    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    stdout, stderr = process.communicate(timeout=300)
    assert process.returncode == 130, f"exit={process.returncode}\n{stdout}\n{stderr}"
    verdicts = bench.verdicts("guest-session")
    assert verdicts["status"] == "interrupted"
    assert bench.package("guest-session") is not None, "the session's evidence must be exported"
    assert "DRIVER RESULT" in stdout
    # The guest may still be running, so the session is not recorded as closed.
    assert (bench.exec_dir / "current_session").exists()


def test_session_close_without_a_session_prints_the_final_line(bench):
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("guest_session_close.sh")
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2" in result.stdout
    assert "STOP: no open session" in result.stderr


# --------------------------------------------------------------------------
# guest/session_close.sh: the G1 artefacts of the sealed build
# --------------------------------------------------------------------------

def _close_bench(tmp_path: Path, reachable: bool = True, refuse: str = "",
                 empty: str = "") -> Path:
    """An evidence directory as guest/session_close.sh expects to find one.

    The guest is reachable and answers the two collections the close keeps (the
    boot journal and the final state); ``refuse`` is a command it answers with
    an error instead, and ``empty`` one it answers with nothing at all.
    """
    evidence = tmp_path / "session"
    if reachable:
        gssh = (
            "gssh() {\n"
            '    case "${1:-}" in\n'
            f'        *{refuse or "no-such-command"}*)\n'
            '            echo "sudo: a password is required" >&2\n'
            "            return 1\n"
            "            ;;\n"
            f'        *{empty or "no-such-command"}*) return 0 ;;\n'
            '        *journalctl*) echo "stub: the boot journal of this session" ;;\n'
            '        *docker*) echo "stub: the final state of the stack" ;;\n'
            "    esac\n"
            "    return 0\n"
            "}\n")
    else:
        gssh = "gssh() { return 1; }\n"
    _write(evidence / "scripts" / "session_common.sh",
           "# shellcheck shell=bash\n" + gssh
           + 'log() { echo "$*"; }\n'
           "run_name() { echo s1; }\n")
    _write(evidence / "boot" / "s1.status", "qemu ended\n")
    (evidence / "guest").mkdir(parents=True, exist_ok=True)
    return evidence


def _close_script(evidence: Path, tmp_path: Path, **overrides) -> subprocess.CompletedProcess:
    """guest/session_close.sh over one evidence directory."""
    environment = dict(os.environ)
    environment.update({"EGW_YOCTO_CHECKOUT": str(tmp_path / "no-such-checkout"),
                        "EGW_G1_REFERENCE": str(tmp_path / "reference"), **overrides})
    return subprocess.run(["bash", str(SESSION_DIR / "guest" / "session_close.sh"), str(evidence)],
                          env=environment, capture_output=True, text=True, timeout=300)


def _g1(tmp_path: Path) -> dict:
    """A G1 build directory and a reference that agree, so that only the
    collections under test can decide the script's status."""
    deploy = tmp_path / "checkout" / "src" / "yocto" / "build" / "tmp" / "deploy" / "images" / "qemuarm64"
    _write(deploy / "Image", "stub kernel\n")
    digest = subprocess.run(["sha256sum", "Image"], cwd=deploy, capture_output=True, text=True).stdout
    _write(tmp_path / "reference" / "g1-deploy-before.sha256", digest)
    return {"EGW_YOCTO_CHECKOUT": str(tmp_path / "checkout"),
            "EGW_G1_REFERENCE": str(tmp_path / "reference")}


@pytest.mark.parametrize("kind, says", [
    ("refuse", "the boot journal was not collected"),
    ("empty", "the boot journal is empty"),
])
def test_guest_session_close_names_a_journal_that_was_not_kept(tmp_path, kind, says):
    # The two collections were redirected with 2>&1 and their status discarded,
    # so the session was sealed "journal and final state kept" with a file
    # holding one error line. A record that was not kept is the guest going off
    # as asked with its close recorded incompletely: exit 3, never a pass.
    evidence = _close_bench(tmp_path, **{kind: "journalctl"})
    result = _close_script(evidence, tmp_path, **_g1(tmp_path))
    assert result.returncode == 3, report(result)
    assert says in result.stdout
    journal = evidence / "guest" / "journal-s1.txt"
    assert "sudo: a password is required" not in journal.read_text(encoding="utf-8"), (
        "the error text never goes into the evidence file")
    if kind == "refuse":
        assert "a password is required" in (
            evidence / "guest" / "journal-s1.err").read_text(encoding="utf-8")


def test_guest_session_close_names_a_final_state_that_was_not_kept(tmp_path):
    evidence = _close_bench(tmp_path, refuse="docker")
    result = _close_script(evidence, tmp_path, **_g1(tmp_path))
    assert result.returncode == 3, report(result)
    assert "the final guest state was not collected" in result.stdout
    assert "the boot journal of this session" in (
        evidence / "guest" / "journal-s1.txt").read_text(encoding="utf-8")


def test_guest_session_close_keeps_both_collections(tmp_path):
    evidence = _close_bench(tmp_path)
    result = _close_script(evidence, tmp_path, **_g1(tmp_path))
    assert result.returncode == 0, report(result)
    assert "the boot journal of this session" in (
        evidence / "guest" / "journal-s1.txt").read_text(encoding="utf-8")
    assert "the final state of the stack" in (
        evidence / "guest" / "final-state-s1.txt").read_text(encoding="utf-8")
    assert "exit=0" in (evidence / "s1.session.status").read_text(encoding="utf-8")


def test_guest_session_close_failed_stop_outranks_a_record_not_kept(tmp_path):
    # An unreachable guest is the controlled stop itself failing (1), which the
    # driver reads as 5; it is never lowered to the record's own 3.
    result = _close_script(_close_bench(tmp_path, reachable=False), tmp_path, **_g1(tmp_path))
    assert result.returncode == 1, report(result)
    assert "already unreachable over SSH" in result.stdout


def test_guest_session_close_names_an_absent_g1_build(tmp_path):
    # The G1 reference lists the artefacts of the NON-integrated build. When
    # that directory is not on this machine the check must say so, not report a
    # checksum failure it never ran.
    evidence = _close_bench(tmp_path)
    environment = dict(os.environ, EGW_YOCTO_CHECKOUT=str(tmp_path / "no-such-checkout"),
                       EGW_G1_REFERENCE=str(tmp_path / "reference"))
    result = subprocess.run(["bash", str(SESSION_DIR / "guest" / "session_close.sh"), str(evidence)],
                            env=environment, capture_output=True, text=True, timeout=300)
    assert result.returncode == 1, report(result)
    check = (evidence / "g1-after-s1.sha256check.txt").read_text(encoding="utf-8")
    assert "the G1 build directory is absent" in check
    assert "were NOT checked" in check


def test_guest_session_close_names_an_absent_g1_reference(tmp_path):
    evidence = _close_bench(tmp_path)
    deploy = tmp_path / "checkout" / "src" / "yocto" / "build" / "tmp" / "deploy" / "images" / "qemuarm64"
    _write(deploy / "Image", "stub kernel\n")
    environment = dict(os.environ, EGW_YOCTO_CHECKOUT=str(tmp_path / "checkout"),
                       EGW_G1_REFERENCE=str(tmp_path / "no-such-reference"))
    result = subprocess.run(["bash", str(SESSION_DIR / "guest" / "session_close.sh"), str(evidence)],
                            env=environment, capture_output=True, text=True, timeout=300)
    assert result.returncode == 1, report(result)
    assert "the G1 reference file is absent" in (
        evidence / "g1-after-s1.sha256check.txt").read_text(encoding="utf-8")


def test_guest_session_close_checks_the_g1_artefacts(tmp_path):
    evidence = _close_bench(tmp_path)
    deploy = tmp_path / "checkout" / "src" / "yocto" / "build" / "tmp" / "deploy" / "images" / "qemuarm64"
    _write(deploy / "Image", "stub kernel\n")
    digest = subprocess.run(["sha256sum", "Image"], cwd=deploy, capture_output=True, text=True).stdout
    reference = tmp_path / "reference"
    _write(reference / "g1-deploy-before.sha256", digest)
    environment = dict(os.environ, EGW_YOCTO_CHECKOUT=str(tmp_path / "checkout"),
                       EGW_G1_REFERENCE=str(reference))
    result = subprocess.run(["bash", str(SESSION_DIR / "guest" / "session_close.sh"), str(evidence)],
                            env=environment, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, report(result)
    assert "Image: OK" in (evidence / "g1-after-s1.sha256check.txt").read_text(encoding="utf-8")
    # And a changed artefact is a failure, not a missing directory.
    _write(deploy / "Image", "a different kernel\n")
    changed = subprocess.run(["bash", str(SESSION_DIR / "guest" / "session_close.sh"), str(evidence)],
                             env=environment, capture_output=True, text=True, timeout=300)
    assert changed.returncode == 1, report(changed)
    assert "FAILED" in (evidence / "g1-after-s1.sha256check.txt").read_text(encoding="utf-8")


def test_session_open_refuses_an_open_session(bench):
    result = bench.run("guest_session_open.sh")
    assert result.returncode == 2, report(result)
    assert "a session is already open" in result.stderr
    assert "DRIVER RESULT none: exit=2" in result.stdout


def test_session_open_refuses_a_running_qemu(bench):
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("guest_session_open.sh", EGW_STUB_FAIL="qemu-left")
    assert result.returncode == 2, report(result)
    assert "qemu-system-aarch64 process is already running" in result.stderr


def _opened_session(bench: Bench) -> dict:
    attempts = sorted(p for p in bench.attempts.iterdir() if "_guest-session_attempt" in p.name)
    return json.loads((attempts[-1] / "attempt.json").read_text(encoding="utf-8"))


def test_session_open_leaves_the_session_open(bench):
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("guest_session_open.sh")
    assert result.returncode == 0, report(result)
    verdicts = _opened_session(bench)
    assert verdicts["status"] == "running", "the session attempt stays open until the close driver"
    assert (bench.exec_dir / "current_session").read_text(encoding="utf-8").strip().endswith(verdicts["run_id"])
    assert not list((bench.out / "runs").glob(f"*/{verdicts['run_id']}")), "nothing is exported yet"
    assert "exit=0" in result.stdout and "export=deferred" in result.stdout
    # The one final line must not claim the verdicts of a finished, exported
    # run: this attempt has no outcome and no package.
    assert "the guest session stays OPEN" in result.stdout
    for claim in ("system outcome pass", "package exported and verified"):
        assert claim not in result.stdout, claim


def test_session_open_that_cannot_record_the_session_does_not_boot(bench):
    # $EXEC/current_session is the only link between the booted guest and every
    # later driver: when it cannot be written, a guest that was started would
    # be left up with no driver able to stop it or to export the session.
    current = bench.exec_dir / "current_session"
    current.unlink()
    current.mkdir()          # the write fails, as on a full or read-only $EXEC
    result = bench.run("guest_session_open.sh")
    assert result.returncode == 2, report(result)
    verdicts = _opened_session(bench)
    assert verdicts["system_outcome"] == "not-run"
    assert "current_session" in verdicts["reason"]
    assert "the guest was NOT booted" in verdicts["reason"]
    assert not Path(str(bench.log) + ".qemu").exists(), "no guest may be started"
    assert "session open" not in result.stdout
    assert list((bench.out / "runs").glob(f"*/{verdicts['run_id']}")), "the attempt was exported"


def test_session_open_unread_build_identities_did_not_boot(bench):
    # The identities of what is about to run are read by one step of many
    # commands, whose LAST one is the controller image record: an OS build
    # whose artefacts are not there must stop the boot all the same.
    (bench.exec_dir / "current_session").unlink()
    shutil.rmtree(bench.deploy)
    result = bench.run("guest_session_open.sh")
    assert result.returncode == 2, report(result)
    verdicts = _opened_session(bench)
    assert verdicts["system_outcome"] == "not-run"
    assert "identities of what was about to run were not read" in verdicts["reason"]
    assert not Path(str(bench.log) + ".qemu").exists(), "no guest may be started"
    assert "boot" not in bench.commands("guest-session")
    assert not (bench.exec_dir / "current_session").exists()


def test_session_open_unreadable_qemu_binary_did_not_boot(bench):
    # The same for the emulator itself, which is read in the middle of the step.
    (bench.exec_dir / "current_session").unlink()
    bench.qemu.unlink()
    result = bench.run("guest_session_open.sh")
    assert result.returncode == 2, report(result)
    assert "identities of what was about to run were not read" in _opened_session(bench)["reason"]
    assert not Path(str(bench.log) + ".qemu").exists(), "no guest may be started"


def test_session_open_failed_identities_did_not_boot(bench):
    # The controller image record cannot be read: the identities of what was
    # about to run are incomplete, so the guest must not be booted.
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("guest_session_open.sh", EGW_IMAGES_DIR=bench.tmp / "no-such-images")
    assert result.returncode == 2, report(result)
    verdicts = _opened_session(bench)
    assert verdicts["system_outcome"] == "not-run"
    assert "identities" in verdicts["reason"]
    assert not (bench.exec_dir / "current_session").exists()
    assert list((bench.out / "runs").glob(f"*/{verdicts['run_id']}")), "the attempt was exported"


def test_session_open_failed_boot_did_not_open_a_session(bench):
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("guest_session_open.sh", EGW_STUB_FAIL="boot")
    assert result.returncode == 2, report(result)
    verdicts = _opened_session(bench)
    assert verdicts["system_outcome"] == "not-run"
    assert "boot failed" in verdicts["reason"]
    assert not (bench.exec_dir / "current_session").exists()
    assert list((bench.out / "runs").glob(f"*/{verdicts['run_id']}")), "the attempt was exported"


@pytest.mark.parametrize("failure", ["dmesg", "docker-daemon"])
def test_session_open_state_after_boot_leaves_the_session_invalid(bench, failure):
    # The mandatory record of the guest state is a LIST of guest commands and
    # was decided by the dmesg test that ends it. The stack the session exists
    # for is the six containers: a guest whose Docker daemon did not come up
    # produces a record whose '## docker' section is empty, and that record is
    # not the state of a healthy guest.
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("guest_session_open.sh", EGW_STUB_FAIL=failure)
    assert result.returncode == 3, report(result)
    verdicts = _opened_session(bench)
    assert verdicts["status"] == "running", "the guest is up: the session must stay open"
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "its state after the boot was not recorded" in verdicts["reason"]
    assert (bench.exec_dir / "current_session").exists()
    assert "session open but NOT characterised" in result.stdout
    assert "session open: " not in result.stdout


@pytest.mark.parametrize("field, stub_fail, says", [
    ("instrumentation_validity", "docker-daemon", "its state after the boot was not recorded"),
    ("pid", "", "its pid was not recorded"),
])
def test_session_open_verdict_that_could_not_be_written_is_not_a_healthy_session(
        bench, field, stub_fail, says):
    # The guest IS up and the write that records what this driver found failed,
    # so attempt.json keeps status=running and validity=unknown — which derives
    # 0, "the guest session stays OPEN", with an empty reason and nothing in
    # the package saying the guest was not characterised. A verdict that was
    # not written must never be read as a healthy session.
    (bench.exec_dir / "current_session").unlink()
    result = bench.run("guest_session_open.sh", EGW_STUB_FAIL=stub_fail,
                       **bench.fail_set_of(field))
    assert result.returncode == 3, report(result)
    assert says in result.stderr
    assert "attempt.json could not be updated" in result.stdout
    assert "DRIVER RESULT none: exit=3" in result.stdout
    assert "session open but" not in result.stdout
    verdicts = _opened_session(bench)
    assert verdicts["status"] == "running"
    assert (bench.exec_dir / "current_session").exists(), "the guest is up: the session is kept"


def test_session_open_keeps_every_driver_file_with_the_session(bench):
    # The copy kept with the session is the set repo_identity hashes: the
    # helpers that derive the exit codes are part of the record too.
    (bench.exec_dir / "current_session").unlink()
    assert bench.run("guest_session_open.sh").returncode == 0
    session = Path((bench.exec_dir / "current_session").read_text(encoding="utf-8").strip())
    kept = session / "scripts" / "drivers"
    for name in ("preflight.sh", "driver_status.py", "deployed_vs_clone.py",
                 "guest_state_delta.py", "junit_one_failure.py", "collector_shortfall.py",
                 "guest/gssh.sh", "guest/session_close.sh"):
        assert (kept / name).is_file(), name


# --------------------------------------------------------------------------
# export_checks.sh: the export itself is what is under test
# --------------------------------------------------------------------------

def _deliberate(bench: Bench) -> dict:
    return bench.verdicts("export-check-deliberate-failure")


def test_export_checks_exports_a_failed_test_as_failed(bench):
    result = bench.run("export_checks.sh", timeout=1800)
    verdicts = _deliberate(bench)
    assert (verdicts["status"], verdicts["instrumentation_validity"], verdicts["system_outcome"]) == (
        "failed", "valid", "fail"), report(result)
    assert "exactly one failed test, as intended" in verdicts["reason"]
    # The identity of the clean clone is written into both attempts, and the
    # passing check names what its report says RAN, not what it collected.
    for slug in ("export-check-success", "export-check-deliberate-failure"):
        assert bench.verdicts(slug)["identities"]["repo_commit"], slug
    passing = bench.verdicts("export-check-success")["reason"]
    assert "test case(s) in tests/junit.xml ran" in passing
    assert "skipped" in passing and "error(s)" in passing
    package = bench.package("export-check-deliberate-failure")
    assert package is not None and (package / "SHA256SUMS").is_file()
    assert (package / "tests" / "junit.xml").is_file()
    # Both attempts ended through the one place the table is applied, and the
    # deliberate negative result is not the driver's own code.
    assert result.stdout.count("DRIVER RESULT") == 2
    assert "EXPORT CHECKS: exit=0" in result.stdout
    assert result.returncode == 0, report(result)


def test_export_checks_unwritable_deliberate_test_is_not_as_intended(bench):
    # The folder cannot be created, so pytest exits 4 ("no tests ran"): a
    # non-zero exit that means the check never ran.
    _write(bench.bin / "mkdir", """#!/bin/sh
for a in "$@"; do
    case "$a" in
        */tests/deliberate)
            echo "mkdir: cannot create directory '$a': No space left on device" >&2
            exit 1
            ;;
    esac
done
exec /bin/mkdir "$@"
""", executable=True)
    result = bench.run("export_checks.sh", timeout=1800)
    assert result.returncode == 3, report(result)
    verdicts = _deliberate(bench)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "did NOT run" in verdicts["reason"]
    assert bench.package("export-check-deliberate-failure") is not None


def test_export_checks_lost_capture_is_not_as_intended(bench):
    # The check's console record was lost (74). The attempt carries
    # capture_failures, so the driver cannot end 0.
    result = bench.run("export_checks.sh", timeout=1800,
                       **bench.fail_capture_of("pytest-deliberate-failure"))
    assert result.returncode == 3, report(result)
    verdicts = _deliberate(bench)
    assert verdicts["capture_failures"], "the capture failure must reach the attempt"
    assert "the console capture of 'pytest-deliberate-failure' failed" in verdicts["reason"]
    assert "as intended" not in verdicts["reason"]


def test_export_checks_module_that_was_not_collected_is_not_a_failed_test(bench):
    # pytest's 4 ("file or directory not found") means NO test ran, which is
    # not a valid negative result: the passing check proved nothing.
    _write(bench.exec_dir / "venv" / "bin" / "python", PY_ABSENT_MODULE, executable=True)
    result = bench.run("export_checks.sh", timeout=1800, EGW_REAL_PYTHON=sys.executable)
    assert result.returncode == 3, report(result)
    verdicts = bench.verdicts("export-check-success")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "pytest exited 4: the test module was not collected" in verdicts["reason"]
    assert "EXPORT CHECKS: exit=3" in result.stdout
    assert bench.package("export-check-success") is not None


def test_export_checks_with_an_unusable_git_did_not_run(bench):
    # The clone's identity is a prerequisite of this driver as it is of every
    # other one, so it ends 2 ("the test did not run"), not 3.
    result = bench.run("export_checks.sh", timeout=1800, EGW_STUB_FAIL="git")
    assert result.returncode == 2, report(result)
    for slug in ("export-check-success", "export-check-deliberate-failure"):
        verdicts = bench.verdicts(slug)
        assert verdicts["system_outcome"] == "not-run", slug
        assert "identity of the clean clone" in verdicts["reason"], slug
    assert "EXPORT CHECKS: exit=2" in result.stdout


def test_export_checks_unrecorded_attempt_fields_did_not_run(bench):
    # The write of the clone's identity is a prerequisite here as it is in
    # every other driver: with a 'local_export set' that fails, the commit, the
    # dirty-line count and the export tool's hash never reach either attempt,
    # so neither check is one of this clone's and neither is run.
    result = bench.run("export_checks.sh", timeout=1800, **bench.python_stub(PY_SET_FAILS))
    assert result.returncode == 2, report(result)
    assert "EXPORT CHECKS: exit=2" in result.stdout
    for slug in ("export-check-success", "export-check-deliberate-failure"):
        verdicts = bench.verdicts(slug)
        assert verdicts["system_outcome"] == "not-run", slug
        assert verdicts["instrumentation_validity"] == "invalid", slug
        assert "the attempt fields could not be recorded" in verdicts["reason"], slug
        assert not verdicts["identities"], slug
    # Nothing was checked: neither pytest run was started.
    assert bench.commands("export-check-success") == []


def test_export_checks_a_module_that_was_entirely_skipped_checked_nothing(bench):
    # pytest exits 0 and writes tests="2" skipped="2" when every case it
    # collected was skipped, so a count of COLLECTED cases proves nothing ran.
    module = _write(bench.tmp / "skipped" / "test_all_skipped.py", ALL_SKIPPED_MODULE)
    result = bench.run("export_checks.sh", timeout=1800,
                       **bench.python_stub(PY_SKIPPED_MODULE, EGW_STUB_SKIPPED_MODULE=str(module)))
    assert result.returncode == 3, report(result)
    assert "EXPORT CHECKS: exit=3" in result.stdout
    verdicts = bench.verdicts("export-check-success")
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "executed no test case" in verdicts["reason"]
    assert "skipped=2" in verdicts["reason"]
    assert "passed" not in verdicts["reason"]
    assert bench.package("export-check-success") is not None


def test_export_checks_export_failure_outranks_a_later_prerequisite(bench):
    # The passing check's package did not reach output_test (4) and the second
    # attempt could not be created (2) — one cause, a full attempts area and a
    # broken destination. The more serious of the two is what the driver ends
    # with, and its summary line is printed all the same.
    result = bench.run("export_checks.sh", timeout=1800,
                       **bench.python_stub(PY_EXPORT_FAILS_ONCE))
    assert result.returncode == 4, report(result)
    assert "EXPORT CHECKS: exit=4" in result.stdout
    assert "exit=4 (the local export failed" in result.stdout
    assert "DRIVER RESULT none: exit=2" in result.stdout
    assert "the attempt for the deliberate failure could not be created" in result.stderr
    assert bench.package("export-check-success") is None


def test_backfill_interrupted_keeps_a_capsule_that_did_not_reach_output_test(bench):
    # Every capsule the backfill copies is exported as it goes, so an interrupt
    # in the middle leaves the ones already done exported and the ones that
    # FAILED still failed: 4 outranks 130, and the trap used to report 130.
    overrides = bench.python_stub(PY_BACKFILL_FAILS_THEN_INTERRUPT)
    process = subprocess.Popen(["bash", str(bench.drivers / "backfill.sh")],
                               env=bench.env(**overrides), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    stdout, stderr = process.communicate(timeout=300)
    assert process.returncode == 4, f"exit={process.returncode}\n{stdout}\n{stderr}"
    assert "DRIVER RESULT none: exit=4" in stdout
    assert "did not reach output_test as a verified package" in stdout
    assert "the remaining ones were not backfilled" in stdout


def test_export_checks_a_deliberate_test_that_passes_is_a_broken_check(bench):
    # The driver's own file is replaced after it is written, so the run that
    # follows produces a passing report: exactly the case "not zero" cannot see.
    _write(bench.bin / "cat", """#!/bin/sh
# A 'cat' that writes a PASSING test where the deliberately failing one
# belongs (the driver's only argument-less cat is that heredoc).
if [ "$#" -eq 0 ]; then
    /bin/cat > /dev/null
    printf 'def test_this_fails_on_purpose():\\n    assert 1 + 1 == 2\\n'
    exit 0
fi
exec /bin/cat "$@"
""", executable=True)
    result = bench.run("export_checks.sh", timeout=1800)
    assert result.returncode == 3, report(result)
    verdicts = _deliberate(bench)
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "did not behave as intended" in verdicts["reason"]
