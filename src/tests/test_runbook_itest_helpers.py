"""Positive and negative cases for the shell text of the integrated-gateway runbook.

Text under test: docs/setup/qemu_integrated_gateway.md - the tunnel file of 5.7, the
helper file that 6.1 writes through a quoted heredoc, the evidence-capturing lines of
6.2-6.4 and of test 9, the lines of test 7 and the tunnel line of test 8 (project
review of 2026-09-18, four residual defects).

Every line is read from the runbook WHEN THE TEST RUNS and handed to bash as it stands
(only the "host$ " prompt is removed), so a later edit of the runbook is tested as it
is. If an anchor line is no longer found the case FAILS: it is never skipped.

What these cases show, and what they do not: the DECISION LOGIC of the published text
in a non-interactive bash, against stub commands (curl, python, ssh, scp, ss, sleep,
and where named tee and pgrep) that stand first on PATH. No controller, broker, Docker
engine, guest or OpenSSH client takes part: nothing here shows that Sections 4-9 of the
runbook work on the real host or guest. DRAIN_QUIET_S is set to 0 and 'sleep' is
scaled down for the tests only; the 130 s figure itself is not under test.

The cases named "mline" and "drained" pin the thirteen-field reading and the quiet
window of ADR 0011 work item 19 against stub /metrics bodies (one body, or a sequence
of bodies served one per request); the "regen" case pins tools/session/regen_helpers.py
to the heredoc it regenerates the helper file from.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from egw_experiments import run as run_mod

if sys.platform == "win32":
    pytest.skip("runbook shell text is host-side bash for Linux/WSL: not run on win32", allow_module_level=True)
BASH = shutil.which("bash")
if BASH is None:
    pytest.skip("bash is not installed: the runbook shell text cannot be executed", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs" / "setup" / "qemu_integrated_gateway.md"
REAL_SLEEP = shutil.which("sleep") or "/bin/sleep"
REAL_TEE = shutil.which("tee") or "/usr/bin/tee"
REAL_PGREP = shutil.which("pgrep")

STARTED = "2026-09-18T10:00:00Z"

# The accounting identity of CONTRACTS 5: received == the sum of these eight terms, all from one response.
IDENTITY_TERMS = ("accepted", "rejected", "duplicate", "failed", "dropped", "processing_errors", "in_progress", "queue_depth")
# The thirteen fields of one _mline reading, in the fixed order the helper prints them (runbook 6.1).
MLINE_FIELDS = ("queue_depth", "in_progress", "unacked", "mqtt_subscribed", "started_at", "mqtt_connection", "received",
                "accepted", "rejected", "duplicate", "failed", "dropped", "processing_errors")


# --------------------------------------------------------------------------
# verbatim extraction from the runbook
# --------------------------------------------------------------------------
def _section(heading_start: str) -> list[str]:
    """Lines under the first heading that starts with `heading_start` (headings inside code fences do not count)."""
    out: list[str] = []
    level = None
    in_fence = False
    for ln in RUNBOOK.read_text(encoding="utf-8").splitlines():
        if ln.startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"(#{1,6}) ", ln)
        if m and level is None:
            if ln.startswith(heading_start):
                level = len(m.group(1))
            continue
        if m and level is not None and len(m.group(1)) <= level:
            break
        if level is not None:
            out.append(ln)
    if level is None:
        pytest.fail(f"runbook heading not found: {heading_start!r}")
    return out


def _host_commands(heading_start: str) -> list[str]:
    """The host$ commands of the fenced blocks of one section, prompt removed, continuation lines kept as they are."""
    cmds: list[str] = []
    cur: list[str] | None = None
    in_fence = False

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            cmds.append("\n".join(cur))
        cur = None

    for ln in _section(heading_start):
        if ln.startswith("```"):
            in_fence = not in_fence
            flush()
        elif not in_fence:
            continue
        elif ln.startswith("host$ "):
            flush()
            cur = [ln[len("host$ "):]]
        elif ln.startswith("guest$ "):
            flush()
        elif cur is not None:
            cur.append(ln)
    flush()
    return cmds


def _one(cmds: list[str], start: str) -> str:
    hits = [c for c in cmds if c.startswith(start)]
    if len(hits) != 1:
        pytest.fail(f"expected exactly one runbook command starting with {start!r}, found {len(hits)}")
    return hits[0]


def _fenced_code() -> str:
    out, in_fence = [], False
    for ln in RUNBOOK.read_text(encoding="utf-8").splitlines():
        if ln.startswith("```"):
            in_fence = not in_fence
        elif in_fence:
            out.append(ln)
    return "\n".join(out)


def tunnel_heredoc() -> str:
    return _one(_host_commands("### 5.7"), "cat > ~/egw-tcg/tunnel.sh <<'EOF'")


def tunnel_load_line() -> str:
    return _one(_host_commands("### 5.7"), "bash -n ~/egw-tcg/tunnel.sh")


def helpers_heredoc() -> str:
    return _one(_host_commands("### 6.1"), "cat > ~/egw-tcg/itest-helpers.sh <<'EOF'")


def helpers_load_line() -> str:
    return _one(_host_commands("### 6.1"), "bash -n ~/egw-tcg/itest-helpers.sh")


# --------------------------------------------------------------------------
# stub commands
# --------------------------------------------------------------------------
STUB_CURL = r"""#!/usr/bin/env bash
S=$EGW_STUB_STATE
echo "curl $*" >> "$S/calls.log"
url=
for a in "$@"; do case $a in http://*|https://*) url=$a;; esac; done
case $url in
  */ready) printf '%s' "$(cat "$S/ready_code" 2>/dev/null || echo 200)"; exit 0;;
  */metrics) if [ -d "$S/metrics.seq" ]; then
               # one answer per request, in order; the last one is repeated once they are used up
               n=$(($(cat "$S/metrics.calls" 2>/dev/null || echo 0) + 1)); echo "$n" > "$S/metrics.calls"
               f="$S/metrics.seq/$n.json"; [ -e "$f" ] || f="$S/metrics.seq/last.json"
               cat "$f"; exit 0
             fi
             [ -s "$S/metrics.json" ] || { echo "curl: (7) stub: connection refused" >&2; exit 7; }
             cat "$S/metrics.json"; exit 0;;
  */api/2/things/*) [ -s "$S/thing.json" ] || { echo "curl: (22) stub: 404" >&2; exit 22; }
             cat "$S/thing.json"; exit 0;;
esac
echo "curl stub: unexpected url '$url'" >&2; exit 2
"""

STUB_PYTHON = r"""#!/usr/bin/env bash
# stands for 'python' only: $SIM (egw_simulator) and $REC (egw_experiments.itest_reconcile). 'python3' stays real.
S=$EGW_STUB_STATE
echo "python $*" >> "$S/calls.log"
if [ "$1" = -m ] && [ "$2" = egw_simulator ]; then
  out=; rid=; prev=
  for a in "$@"; do case $prev in --output) out=$a;; --run-id) rid=$a;; esac; prev=$a; done
  if [ -s "$S/sent_events.jsonl" ]; then mkdir -p "$out/$rid" && cp "$S/sent_events.jsonl" "$out/$rid/sent_events.jsonl"; fi
  [ -e "$S/sim_silent" ] || echo "egw_simulator stub: done run_id=$rid" >&2
  [ ! -s "$S/sim_sleep" ] || "$EGW_REAL_SLEEP" "$(cat "$S/sim_sleep")"
  exit "$(cat "$S/sim_rc" 2>/dev/null || echo 0)"
fi
if [ "$1" = -m ] && [ "$2" = egw_experiments.itest_reconcile ]; then
  sub=$3; prefix=; label=; prev=
  for a in "$@"; do case $prev in --prefix) prefix=$a;; --label) label=$a;; esac; prev=$a; done
  rc=$(cat "$S/rec_${sub}_rc" 2>/dev/null || echo 0)
  echo "itest_reconcile stub: $sub exit=$rc"
  if [ "$sub" = snap ] && [ "$rc" = 0 ]; then echo '{"stub": true}' > "$prefix.twins.$label.json"; fi
  exit "$rc"
fi
if [ "$1" = -m ] && [ "$2" = egw_experiments ] && [ "$3" = run ]; then
  # harness_run: every argument kept exactly, NUL-separated
  for a in "$@"; do printf '%s\0' "$a"; done > "$S/harness_argv"
  exit "$(cat "$S/harness_rc" 2>/dev/null || echo 0)"
fi
echo "python stub: unexpected arguments: $*" >&2; exit 97
"""

STUB_SCP = r"""#!/usr/bin/env bash
S=$EGW_STUB_STATE
echo "scp $*" >> "$S/calls.log"
dest="${@: -1}"
[ -e "$S/remote_events.jsonl" ] || { echo "scp: stub: no such file on the guest" >&2; exit 1; }
cp "$S/remote_events.jsonl" "$dest"
"""

STUB_SSH = r"""#!/usr/bin/env bash
# Never reads stdin. One line per invocation in ssh.log, every argument in [brackets].
S=$EGW_STUB_STATE
{ printf 'ssh'; for a in "$@"; do printf ' [%s]' "$a"; done; echo; } >> "$S/ssh.log"
sock=; op=; master=0; prev=
for a in "$@"; do
  case $prev in -S) sock=$a;; -O) op=$a;; esac
  [ "$a" = -M ] && master=1
  prev=$a
done
case $op in
  check)
    if [ -e "$S/master_alive" ] && [ "$(cat "$S/master_alive")" = "$sock" ]; then echo "Master running (pid=4242)" >&2; exit 0; fi
    if [ -e "$S/check_error" ]; then cat "$S/check_error" >&2; exit 255; fi
    if [ -S "$sock" ]; then echo "Control socket connect($sock): Connection refused" >&2
    else echo "Control socket connect($sock): No such file or directory" >&2; fi
    exit 255;;
  exit)
    [ ! -e "$S/exit_fails" ] || { echo "stub: exit request failed" >&2; exit 255; }
    rm -f "$S/master_alive" "$sock"; echo "Exit request sent." >&2; exit 0;;
esac
if [ "$master" = 1 ]; then
  [ ! -e "$S/master_open_fails" ] || { echo "stub: forward failed" >&2; exit 255; }
  python3 -c 'import os, socket, sys
d, n = os.path.split(sys.argv[1]); os.chdir(d); socket.socket(socket.AF_UNIX).bind(n)' "$sock" || exit 255
  printf '%s' "$sock" > "$S/master_alive"; exit 0
fi
cmd="${@: -1}"
case $cmd in
  "date +%s") # guest_epoch (6.1): the guest's clock, or no answer at all
    [ ! -e "$S/guest_clock_fails" ] || { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255; }
    cat "$S/guest_epoch" 2>/dev/null || echo 1790000000; exit 0;;
  *sha256sum*) # the configuration identity capture of config_identity (6.1)
    if [ -e "$S/identity_exec" ]; then
      # the remote script run for real under a POSIX shell, with cd sent to the stub deployment directory (the
      # one substitution: /opt/egw/deployment is the guest's path); docker and sudo are the stubs on PATH
      exec "${EGW_STUB_GUEST_SH:-sh}" -c "cd() { command cd \"\$EGW_STUB_DEPLOYMENT\"; }; $cmd"
    fi
    # otherwise the recorded key=value lines
    cat "$S/identity_capture" 2>/dev/null; exit "$(cat "$S/ssh_identity_rc" 2>/dev/null || echo 0)";;
  *" ps -aq "*) [ -e "$S/svc_state_unreadable" ] && exit 1; cat "$S/svc_state" 2>/dev/null || echo running; exit 0;;
  *" stop "*)
    rc=$(cat "$S/ssh_stop_rc" 2>/dev/null || echo 0)
    if [ -e "$S/kill_fault_job_on_stop" ]; then kill -KILL "$PPID"; exit 0; fi
    if [ "$rc" = 0 ] && [ ! -e "$S/stop_has_no_effect" ]; then echo exited > "$S/svc_state"; fi
    [ ! -e "$S/term_fault_job_on_stop" ] || kill -TERM "$PPID"
    exit "$rc";;
  *" start "*)
    rc=$(cat "$S/ssh_start_rc" 2>/dev/null || echo 0)
    [ "$rc" != 0 ] || echo running > "$S/svc_state"
    exit "$rc";;
  *" logs "*) cat "$S/broker_log" 2>/dev/null; exit "$(cat "$S/ssh_logs_rc" 2>/dev/null || echo 0)";;
esac
echo "ssh stub: unexpected command: $cmd" >&2; exit 98
"""

STUB_SUDO = r"""#!/usr/bin/env bash
# the guest's sudo: runs the command as it is (the bench has no root and needs none)
echo "sudo $*" >> "$EGW_STUB_STATE/calls.log"
exec "$@"
"""

STUB_DOCKER = r"""#!/usr/bin/env bash
# the guest's docker, for the reads of config_identity's remote script: the broker log (its exit status and text
# set by the case), the controller image id, the image's source-commit label, the paho-mqtt version
S=$EGW_STUB_STATE
echo "docker $*" >> "$S/calls.log"
case "$*" in
  "compose "*" logs --no-color mosquitto")
    rc=$(cat "$S/docker_logs_rc" 2>/dev/null || echo 0)
    # a failed read may have streamed part of the log first (the daemon lost after N lines): the case decides
    [ "$rc" = 0 ] || [ -e "$S/docker_logs_partial" ] && cat "$S/guest_broker_log" 2>/dev/null
    [ "$rc" = 0 ] || { echo "docker stub: compose logs failed (exit $rc)" >&2; exit "$rc"; }
    exit 0;;
  "inspect -f {{.Image}} egw-controller-1") echo "sha256:$(cat "$S/guest_image_hex")"; exit 0;;
  "inspect -f "*"org.opencontainers.image.revision"*)
    [ "$4" = "sha256:$(cat "$S/guest_image_hex")" ] || { echo "docker stub: inspect of an image that is not the controller's: $4" >&2; exit 95; }
    cat "$S/guest_commit"; exit 0;;
  "exec egw-controller-1 python -c "*) cat "$S/guest_paho"; exit 0;;
esac
echo "docker stub: unexpected arguments: $*" >&2; exit 96
"""

STUB_SS = r"""#!/usr/bin/env bash
echo "State  Recv-Q Send-Q Local Address:Port  Peer Address:Port"
cat "$EGW_STUB_STATE/ss_out" 2>/dev/null
exit 0
"""

STUB_SLEEP = r"""#!/usr/bin/env bash
# scaled down: N seconds of the runbook become N * EGW_STUB_MS_PER_S milliseconds
n=${1%%.*}; case $n in ''|*[!0-9]*) n=0;; esac
ms=$(( n * ${EGW_STUB_MS_PER_S:-4} ))
exec "$EGW_REAL_SLEEP" "$(printf '%d.%03d' $((ms / 1000)) $((ms % 1000)))"
"""

# optional stubs, installed by the case that names them
STUB_TEE_FAILS = r"""#!/usr/bin/env bash
# writes like tee, then reports a failure (what a full disk gives after a partial write)
"$EGW_REAL_TEE" "$@"; exit 1
"""

# pkill / killall: never run for real from a test (they would reach the processes of whoever runs the tests); logged only
STUB_NEVER = r"""#!/usr/bin/env bash
echo "PATTERN-KILL ${0##*/} $*" >> "$EGW_STUB_STATE/calls.log"
exit 0
"""

STUB_PGREP = r"""#!/usr/bin/env bash
echo "pgrep $*" >> "$EGW_STUB_STATE/calls.log"
exit "$(cat "$EGW_STUB_STATE/pgrep_rc" 2>/dev/null || echo 0)"
"""

# The checkout's capture scripts, in the stub clone EGW_CLONE names (the real ones run against a stub guest in
# test_runbook_capture_wiring.py). Each call is recorded in capture.log and, so that its order against the guest
# commands can be read, in ssh.log too.
STUB_EVENTS_CAPTURE = r"""#!/usr/bin/env bash
# tools/session/events_capture.sh: 'start' prints the recorder's readiness and run_guest_t0 (events_start_rc 0) or a
# NOT READY line (any other status, the unit then not running); 'cleanup' says whether the unit was still active,
# stops it and, given a keep directory, keeps a partial capture there, write-once
S=$EGW_STUB_STATE
line="capture"; for a in "$@"; do line="$line [$a]"; done
echo "$line" >> "$S/capture.log"; echo "$line" >> "$S/ssh.log"
t0=$(cat "$S/events_t0" 2>/dev/null || echo 1790000000)
case $1 in
  start)
    rc=$(cat "$S/events_start_rc" 2>/dev/null || echo 0)
    [ "$rc" = 0 ] || { echo "NOT READY: the stub recorder unit egw-events-$2 did not show a live subscription"; exit "$rc"; }
    echo active > "$S/unit-$2"
    echo "ready epoch=$t0 events_bytes=100 unit=active"
    echo "run_guest_t0=$t0"
    exit 0;;
  cleanup)
    echo "unit_state_before_cleanup=$(cat "$S/unit-$2" 2>/dev/null || echo inactive)"
    echo inactive > "$S/unit-$2"
    if [ -n "${3:-}" ]; then
      [ ! -e "$3" ] || { echo "STOP: events_capture: $3 exists - NOT overwritten" >&2; exit 1; }
      mkdir -p "$3" && echo '{"Action":"exec_die","timeNano":1}' > "$3/events.partial.jsonl"
    fi
    exit 0;;
esac
exit 2
"""

STUB_FETCH_SUT_LOG = r"""#!/usr/bin/env bash
# tools/session/proof_fetch_sut_log.sh: writes DEST, write-once, from the case's <kind>.guest file (what the guest's
# log holds for the window) or fails as the case sets it (fetch_<kind>_rc), writing nothing; the docker-events fetch
# stops the stub unit and keeps its stop record whatever its ending
S=$EGW_STUB_STATE
line="fetch"; for a in "$@"; do line="$line [$a]"; done
echo "$line" >> "$S/capture.log"; echo "$line" >> "$S/ssh.log"
kind=$1 dest=$2 dir=$(dirname "$2")
mkdir -p "$dir"
[ ! -e "$dest" ] || { echo "STOP: proof_fetch_sut_log: $dest exists - NOT overwritten; nothing was read" >&2; exit 1; }
if [ "$kind" = docker-events ]; then
  echo inactive > "$S/unit-$4"
  echo "unit_state_before_stop=active" > "$dir/docker-events.stop.txt"
fi
rc=$(cat "$S/fetch_${kind}_rc" 2>/dev/null || echo 0)
[ "$rc" = 0 ] || { echo "STOP: proof_fetch_sut_log: the $kind log was NOT read on the guest (stub, exit $rc)" >&2; exit "$rc"; }
if [ -e "$S/$kind.guest" ]; then cat "$S/$kind.guest" > "$dest"
elif [ "$kind" = docker-events ]; then echo '{"Action":"exec_die","timeNano":1}' > "$dest"
else : > "$dest"; fi
[ -s "$dest" ] || { rm -f "$dest"; echo "STOP: proof_fetch_sut_log: the $kind log was NOT read on the guest (stub: nothing answered)" >&2; exit 1; }
echo "proof_fetch_sut_log: $kind: $(wc -l < "$dest") line(s), written to $dest"
"""


class Result:
    def __init__(self, rc: int, out: str) -> None:
        self.rc, self.out = rc, out
        self.lines = out.splitlines()

    def value(self, key: str) -> str:
        """The text after 'KEY=' on the echo line the case added after a pasted line."""
        hits = [ln[len(key) + 1:] for ln in self.lines if ln.startswith(key + "=")]
        assert len(hits) == 1, f"{key}= printed {len(hits)} times\n{self.out}"
        return hits[0]

    def starting(self, prefix: str) -> list[str]:
        return [ln for ln in self.lines if ln.startswith(prefix)]


class Bench:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.stubs = tmp_path / "stubs"
        self.state = tmp_path / "state"
        for d in (self.home / "egw-tcg", self.stubs, self.state):
            d.mkdir(parents=True)
        self.p = self.home / "egw-tcg" / "itest"
        self.sock = self.home / "egw-tcg" / "tunnel.ctl"
        for name, text in (("curl", STUB_CURL), ("python", STUB_PYTHON), ("scp", STUB_SCP), ("ssh", STUB_SSH),
                           ("ss", STUB_SS), ("sleep", STUB_SLEEP), ("pkill", STUB_NEVER), ("killall", STUB_NEVER)):
            self.install(name, text)
        self.install("python3", '#!/usr/bin/env bash\nexec "%s" "$@"\n' % sys.executable)
        # The checkout EGW_CLONE names: the collector's fetch script as it is, the two capture scripts as stubs.
        self.clone = tmp_path / "clone"
        for name, text in (("events_capture.sh", STUB_EVENTS_CAPTURE), ("proof_fetch_sut_log.sh", STUB_FETCH_SUT_LOG)):
            path = self.clone / "tools" / "session" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)
        scripts = self.clone / "src" / "deployment" / "scripts"
        scripts.mkdir(parents=True)
        shutil.copyfile(ROOT / "src" / "deployment" / "scripts" / "fetch-collector-output.sh",
                        scripts / "fetch-collector-output.sh")
        self.metrics()

    def install(self, name: str, text: str) -> None:
        f = self.stubs / name
        f.write_text(text, encoding="utf-8")
        f.chmod(0o755)

    def set(self, name: str, value: object = "") -> None:
        (self.state / name).write_text(f"{value}\n", encoding="utf-8")

    @staticmethod
    def reading(started_at: str = STARTED, queue_depth: int = 0, **fields: object) -> dict:
        """One /metrics body as the controller serves it: the four outcome counters and dropped, the progress
        fields of CONTRACTS 5 (received, in_progress, processing_errors) and the three session fields of
        ADR 0011 (mqtt_subscribed, mqtt_connection, unacked). Unless the case sets `received` itself, it is
        recomputed as the sum of the eight terms of the accounting identity, so that a case overriding a
        counter still serves a reading whose identity holds (and one that sets it breaks the identity on purpose)."""
        m = {"queue_depth": queue_depth, "started_at": started_at, "monotonic_ns": 1,
             "accepted": 0, "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0,
             "in_progress": 0, "processing_errors": 0,
             "mqtt_subscribed": True, "mqtt_connection": 1, "unacked": 0}
        m.update(fields)
        if "received" not in fields:
            m["received"] = sum(m[k] for k in IDENTITY_TERMS)
        return m

    def metrics(self, started_at: str = STARTED, queue_depth: int = 0, **fields: object) -> dict:
        """The body the stub curl serves for every GET /metrics from now on (see `reading`)."""
        m = self.reading(started_at, queue_depth, **fields)
        (self.state / "metrics.json").write_text(json.dumps(m), encoding="utf-8")
        return m

    def readings(self, *bodies: dict) -> None:
        """The bodies the stub curl serves for GET /metrics, one per request in this order; the last one is
        repeated once they are used up. Takes precedence over `metrics` for the rest of the case."""
        d = self.state / "metrics.seq"
        d.mkdir()
        for i, body in enumerate(bodies, 1):
            (d / f"{i}.json").write_text(json.dumps(body), encoding="utf-8")
        (d / "last.json").write_text(json.dumps(bodies[-1]), encoding="utf-8")

    def metrics_requests(self) -> int:
        """How many GET /metrics the stub curl has answered or refused so far."""
        return sum(1 for ln in self.calls().splitlines() if ln.startswith("curl ") and ln.endswith("/metrics"))

    def jsonl(self, name: str, rows: list[dict]) -> None:
        (self.state / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def calls(self) -> str:
        f = self.state / "calls.log"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def capture_calls(self) -> list[str]:
        """The calls of the stub clone's capture scripts, in order ('capture [start] [id]', 'fetch [kind] ...')."""
        f = self.state / "capture.log"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    def ssh_log(self) -> list[str]:
        f = self.state / "ssh.log"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    def simulator_calls(self) -> int:
        return self.calls().count("-m egw_simulator")

    def env(self, extra: dict[str, str]) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items()
               if k not in ("CTRL", "DITTO", "MQTT_PORT", "P", "TUNNEL_SOCK", "ACCEPT_UNACCOUNTED", "DEVICES",
                            "BASH_ENV", "ENV", "DRAIN_LIMIT_S")}
        env.update({"HOME": str(self.home), "PATH": f"{self.stubs}{os.pathsep}{os.environ.get('PATH', '')}",
                    "EGW_STUB_STATE": str(self.state), "EGW_REAL_SLEEP": REAL_SLEEP, "EGW_REAL_TEE": REAL_TEE,
                    "MOSQUITTO_SIMULATOR_PASSWORD": "stub-value-not-a-secret", "LC_ALL": "C",
                    "DRAIN_QUIET_S": "0", "DRAIN_STEP_S": "0", "READY_LIMIT_S": "0", "EGW_CLONE": str(self.clone)})
        env.update(extra)
        return env

    def run(self, body: str, timeout: int = 120, **extra: str) -> Result:
        script = self.tmp / "driver.sh"
        script.write_text(body + "\n", encoding="utf-8")
        proc = subprocess.Popen([BASH, str(script)], env=self.env(extra), cwd=str(self.tmp), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
            pytest.fail(f"the pasted lines did not end within {timeout} s\n{out}")
        return Result(proc.returncode, out)

    # the operator's start of a session: both files written by the runbook's own heredocs, then sourced
    def with_helpers(self, body: str) -> str:
        return "\n".join((tunnel_heredoc(), helpers_heredoc(), ". ~/egw-tcg/itest-helpers.sh", body))

    def with_tunnel(self, body: str) -> str:
        return "\n".join((tunnel_heredoc(), ". ~/egw-tcg/tunnel.sh", body))


@pytest.fixture
def bench(tmp_path: Path) -> Bench:
    return Bench(tmp_path)


def sent(*ids: str) -> list[dict]:
    return [{"message_id": m, "device_type": "smartwatch", "device_uuid": "uuid-0001", "seq": i} for i, m in enumerate(ids)]


def event(run_id: str, message_id: str, outcome: str) -> dict:
    return {"run_id": run_id, "message_id": message_id, "outcome": outcome, "attempts": 1, "error": None}


def prepare_accounted(bench: Bench, run_id: str, sent_rows: list[dict], events: list[dict] | None, before: dict) -> None:
    d = bench.p / run_id
    d.mkdir(parents=True)
    (d / "sent_events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in sent_rows), encoding="utf-8")
    if events is not None:
        (d / "events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in events), encoding="utf-8")
    (bench.p / f"{run_id}.metrics.before.json").write_text(json.dumps(before), encoding="utf-8")


def call_accounted(bench: Bench, run_id: str, **env: str) -> Result:
    return bench.run(bench.with_helpers(f'accounted {run_id}\necho "RC=$?"'), **env)


# --------------------------------------------------------------------------
# 6.1 - the helper file as the heredoc writes it
# --------------------------------------------------------------------------
def test_helper_heredoc_is_quoted_and_loads_the_file_holds_the_variable_name_not_the_password(bench: Bench) -> None:
    r = bench.run("\n".join((tunnel_heredoc(), helpers_heredoc(), helpers_load_line(), 'echo "RC=$?"')))
    assert r.value("RC") == "0", r.out
    assert "helpers loaded, reconcile helper importable" in r.lines
    text = (bench.home / "egw-tcg" / "itest-helpers.sh").read_text(encoding="utf-8")
    assert "--password $MOSQUITTO_SIMULATOR_PASSWORD" in text
    assert "stub-value-not-a-secret" not in text


def test_helper_file_sourced_with_an_empty_password_prints_stop_and_is_not_reported_as_loaded(bench: Bench) -> None:
    r = bench.run("\n".join((tunnel_heredoc(), helpers_heredoc(), helpers_load_line(), 'echo "RC=$?"')),
                  MOSQUITTO_SIMULATOR_PASSWORD="")
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: MOSQUITTO_SIMULATOR_PASSWORD is empty"), r.out
    assert "helpers loaded, reconcile helper importable" not in r.lines


def heredoc_body(command: str) -> str:
    """The text between the `cat > ... <<'EOF'` line and the `EOF` line of one runbook heredoc, as the file."""
    lines = command.split("\n")
    assert lines[0].startswith("cat > ") and "<<'EOF'" in lines[0] and lines[-1] == "EOF", command[:80]
    return "\n".join(lines[1:-1]) + "\n"


def test_regen_helpers_writes_exactly_the_body_of_the_6_1_heredoc(bench: Bench, tmp_path: Path) -> None:
    """tools/session/regen_helpers.py regenerates ~/egw-tcg/itest-helpers.sh from the runbook: the file it writes is
    byte for byte the heredoc body, i.e. the file the operator's own paste of 6.1 writes through bash."""
    script = ROOT / "tools" / "session" / "regen_helpers.py"
    target = tmp_path / "regen" / "itest-helpers.sh"
    target.parent.mkdir()
    proc = subprocess.run([sys.executable, str(script), str(RUNBOOK), str(target)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.startswith(f"wrote {target}: sha256 "), proc.stdout
    written = target.read_bytes().decode("utf-8")
    assert written == heredoc_body(helpers_heredoc())
    bench.run("\n".join((tunnel_heredoc(), helpers_heredoc())))
    assert target.read_bytes() == (bench.home / "egw-tcg" / "itest-helpers.sh").read_bytes()
    assert "_mline()" in written and "drained()" in written and "\r" not in written


# --------------------------------------------------------------------------
# 6.1 - _mline and drained: the thirteen-field reading and the quiet window (ADR 0011, work item 19)
# --------------------------------------------------------------------------
CTRL_DEFAULT = "http://127.0.0.1:8000"
QUIET_LINE = "drained: queue_depth 0 and identical counters on "
STOP_NO_WINDOW = "STOP: drained: no quiet window of "
STOP_NO_READING = f"STOP: drained: GET {CTRL_DEFAULT}/metrics failed or was not valid JSON, or a field was missing or of the wrong type"


def mline_of(m: dict) -> str:
    """The one line _mline prints for this body: the thirteen fields in order, mqtt_subscribed as true/false."""
    return " ".join(str(m[k]).lower() if k == "mqtt_subscribed" else str(m[k]) for k in MLINE_FIELDS)


def call_mline(bench: Bench) -> Result:
    return bench.run(bench.with_helpers('out=$(_mline 2>/dev/null); rc=$?; echo "OUT=$out"; echo "RC=$rc"'))


def call_drained(bench: Bench, limit_s: str = "2", **env: str) -> Result:
    """drained with the case's DRAIN_QUIET_S=0 and DRAIN_STEP_S=0: a quiet reading closes the window on the next
    equal reading, and a refusal spins until DRAIN_LIMIT_S (whole seconds of the host's /proc/uptime) has passed."""
    return bench.run(bench.with_helpers('drained\necho "RC=$?"'), DRAIN_LIMIT_S=limit_s, **env)


def quiet_reading_of(r: Result) -> str:
    """The reading inside the parentheses of the one success line; fails when the line is absent or reworded."""
    lines = r.starting(QUIET_LINE)
    assert len(lines) == 1, r.out
    m = re.match(r"^drained: queue_depth 0 and identical counters on (\d+) consecutive readings over (\d+) s \((.*?)\) - ", lines[0])
    assert m, lines[0]
    return m.group(3)


def assert_no_quiet_window(r: Result, last: dict) -> str:
    """drained gave up: the give-up line names the last reading, and neither the success line nor the other stop was printed."""
    assert r.value("RC") != "0", r.out
    stops = r.starting(STOP_NO_WINDOW)
    assert len(stops) == 1, r.out
    assert f"(last reading: {mline_of(last)}) - do not take snapshots, do not start a run" in stops[0], stops[0]
    assert not r.starting(QUIET_LINE) and not r.starting(STOP_NO_READING), r.out
    return stops[0]


def test_mline_prints_the_thirteen_fields_in_the_fixed_order_and_exits_0_when_the_identity_holds(bench: Bench) -> None:
    m = bench.metrics(accepted=3, rejected=1, duplicate=1, dropped=1)
    r = call_mline(bench)
    assert r.value("RC") == "0", r.out
    assert r.value("OUT") == mline_of(m) == f"0 0 0 true {STARTED} 1 6 3 1 1 0 1 0"


def test_mline_exits_3_with_the_line_when_the_accounting_identity_fails(bench: Bench) -> None:
    m = bench.metrics(accepted=3, rejected=1, duplicate=1, dropped=1, received=7)     # the eight terms sum to 6
    r = call_mline(bench)
    assert r.value("RC") == "3", r.out
    assert r.value("OUT") == mline_of(m) == f"0 0 0 true {STARTED} 1 7 3 1 1 0 1 0"


def seven_field_reading() -> dict:
    """The response of a controller build before the progress counters and the session fields."""
    return {"queue_depth": 0, "started_at": STARTED, "monotonic_ns": 1,
            "accepted": 0, "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0}


def without(m: dict, key: str) -> dict:
    return {k: v for k, v in m.items() if k != key}


NO_READING_BODIES = [
    ("seven-field response of an earlier controller build", seven_field_reading()),
    ("unacked missing", without(Bench.reading(), "unacked")),
    ("mqtt_subscribed missing", without(Bench.reading(), "mqtt_subscribed")),
    ("received missing", without(Bench.reading(), "received")),
    ("mqtt_subscribed the string true", Bench.reading(mqtt_subscribed="true")),
    ("in_progress the JSON true", Bench.reading(in_progress=True)),
    ("queue_depth null", Bench.reading(queue_depth=None, received=0)),
    ("received a float", Bench.reading(received=0.0)),
    ("accepted negative", Bench.reading(accepted=-1)),
    ("mqtt_connection a string", Bench.reading(mqtt_connection="1")),
    ("started_at with a space", Bench.reading(started_at="2026-09-18 10:00:00Z")),
    ("started_at empty", Bench.reading(started_at="")),
    ("started_at a number", Bench.reading(started_at=1758189600)),
    ("body not JSON", "not json"),
]


@pytest.mark.parametrize("label, body", NO_READING_BODIES, ids=[label for label, _ in NO_READING_BODIES])
def test_mline_prints_no_reading_and_exits_neither_0_nor_3_when_a_field_is_missing_or_of_the_wrong_type(bench: Bench, label: str, body: object) -> None:
    (bench.state / "metrics.json").write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    r = call_mline(bench)
    assert r.value("OUT") == "", r.out
    assert r.value("RC") not in ("0", "3"), r.out


def test_drained_closes_a_window_of_quiet_readings_and_keeps_the_start_of_the_success_line(bench: Bench) -> None:
    m = bench.metrics(accepted=3, rejected=1, duplicate=1, dropped=1)
    r = call_drained(bench)
    assert r.value("RC") == "0", r.out
    assert quiet_reading_of(r) == mline_of(m)
    assert len(quiet_reading_of(r).split()) == 13
    line = r.starting(QUIET_LINE)[0]
    assert "an observation, not proof that processing has finished" in line, line
    assert not r.starting("STOP"), r.out


def test_drained_refuses_a_quiet_window_with_mqtt_subscribed_false_throughout(bench: Bench) -> None:
    m = bench.metrics(mqtt_subscribed=False)
    r = call_drained(bench)
    assert_no_quiet_window(r, m)
    assert bench.metrics_requests() >= 3, bench.calls()               # it kept reading until the limit, never a STOP earlier
    assert " 0 0 0 false " in r.starting(STOP_NO_WINDOW)[0]
    # the control: the same counters on a subscribed connection are quiet
    m = bench.metrics(mqtt_subscribed=True)
    r = call_drained(bench)
    assert r.value("RC") == "0" and quiet_reading_of(r) == mline_of(m), r.out


def test_drained_refuses_a_quiet_window_with_unacked_above_0_and_the_queue_empty(bench: Bench) -> None:
    m = bench.metrics(unacked=2)
    r = call_drained(bench)
    assert_no_quiet_window(r, m)
    assert bench.metrics_requests() >= 3, bench.calls()
    assert "(last reading: 0 0 2 true " in r.starting(STOP_NO_WINDOW)[0]
    m = bench.metrics(unacked=0)
    r = call_drained(bench)
    assert r.value("RC") == "0" and quiet_reading_of(r) == mline_of(m), r.out


def test_drained_refuses_a_quiet_window_with_a_message_in_progress_and_the_queue_empty(bench: Bench) -> None:
    m = bench.metrics(in_progress=1)                                   # received follows: the identity holds
    assert m["received"] == 1
    r = call_drained(bench)
    assert_no_quiet_window(r, m)
    assert "(last reading: 0 1 0 true " in r.starting(STOP_NO_WINDOW)[0]


def test_drained_refuses_a_quiet_window_across_a_change_of_mqtt_connection(bench: Bench) -> None:
    """Every reading arrives on a new connection: each opens a new window, so none closes although every other
    field is quiet and unchanged."""
    bodies = [bench.reading(mqtt_connection=i) for i in range(1, 601)]
    bench.readings(*bodies)
    r = call_drained(bench)
    n = int((bench.state / "metrics.calls").read_text(encoding="utf-8"))
    assert 3 <= n < 600, n                                             # several readings, and the sequence never ran out
    assert_no_quiet_window(r, bodies[n - 1])


def test_drained_change_of_mqtt_connection_opens_a_new_window_that_closes_on_the_new_connection_only(bench: Bench) -> None:
    old, new = bench.reading(mqtt_connection=1), bench.reading(mqtt_connection=2)
    bench.readings(old, new)                                           # then `new` for every later request
    r = call_drained(bench)
    assert r.value("RC") == "0", r.out
    assert quiet_reading_of(r) == mline_of(new)
    # the reading on connection 1 is not part of the window that closed: DRAIN_QUIET_S=0 closes it on the second
    # equal reading, so the count is 2 and not 3
    assert r.starting(QUIET_LINE)[0].startswith(f"{QUIET_LINE}2 consecutive readings"), r.out


def test_drained_treats_a_reading_whose_identity_fails_as_not_quiet_and_not_as_a_stop(bench: Bench) -> None:
    bad = bench.metrics(accepted=3, rejected=1, duplicate=1, dropped=1, received=7)   # the eight terms sum to 6
    r = call_drained(bench)
    stop = assert_no_quiet_window(r, bad)                              # the line WAS a reading (status 3 with the line)
    assert bench.metrics_requests() >= 3, bench.calls()
    assert f"(last reading: 0 0 0 true {STARTED} 1 7 3 1 1 0 1 0)" in stop, stop
    # ... and it opens a new window: quiet readings after it close one that began after it
    good = bench.reading(accepted=3, rejected=1, duplicate=1, dropped=1)
    bench.readings(bad, good)
    r = call_drained(bench)
    assert r.value("RC") == "0", r.out
    assert quiet_reading_of(r) == mline_of(good) == f"0 0 0 true {STARTED} 1 6 3 1 1 0 1 0"
    assert r.starting(QUIET_LINE)[0].startswith(f"{QUIET_LINE}2 consecutive readings"), r.out


NO_READING_STOPS = [
    ("seven-field response of an earlier controller build", seven_field_reading()),
    ("unacked missing", without(Bench.reading(), "unacked")),
    ("mqtt_subscribed the string true", Bench.reading(mqtt_subscribed="true")),
    ("in_progress the JSON true", Bench.reading(in_progress=True)),
    ("started_at with a space", Bench.reading(started_at="2026-09-18 10:00:00Z")),
    ("body not JSON", "not json"),
]


@pytest.mark.parametrize("label, body", NO_READING_STOPS, ids=[label for label, _ in NO_READING_STOPS])
def test_drained_reading_without_the_thirteen_fields_is_the_get_failed_stop_not_a_reading(bench: Bench, label: str, body: object) -> None:
    (bench.state / "metrics.json").write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    r = call_drained(bench)
    assert r.value("RC") != "0", r.out
    stops = r.starting(STOP_NO_READING)
    assert len(stops) == 1 and "a controller build without the thirteen fields?" in stops[0], r.out
    assert not r.starting(STOP_NO_WINDOW) and not r.starting(QUIET_LINE), r.out
    assert bench.metrics_requests() == 1, bench.calls()               # a STOP, not a reading: no window, no second request


def test_drained_metrics_unreachable_is_still_the_get_failed_stop(bench: Bench) -> None:
    (bench.state / "metrics.json").unlink()
    r = call_drained(bench)
    assert r.value("RC") != "0", r.out
    assert len(r.starting(STOP_NO_READING)) == 1 and not r.starting(STOP_NO_WINDOW), r.out


def test_drained_keeps_both_output_prefixes(bench: Bench) -> None:
    """The success line's start is what the G2 acceptance proposal quotes; the give-up line's start is what
    tools/session/nominal.sh greps for (`^STOP: drained: no quiet window of [0-9]* s within [0-9]* s`)."""
    m = bench.metrics()
    r = call_drained(bench)
    assert r.value("RC") == "0", r.out
    assert re.match(r"^drained: queue_depth 0 and identical counters on \d+ consecutive readings over \d+ s \(", r.starting(QUIET_LINE)[0])
    assert quiet_reading_of(r) == mline_of(m)
    m = bench.metrics(queue_depth=1)                                   # the refusal the first version already made
    r = call_drained(bench)
    stop = assert_no_quiet_window(r, m)
    assert re.match(r"^STOP: drained: no quiet window of [0-9][0-9]* s within [0-9][0-9]* s", stop), stop
    assert re.match(r"^STOP: drained: no quiet window of 0 s within 2 s \(last reading: 1 0 0 true ", stop), stop


STABLE_FIELDS = ("started_at", "mqtt_connection", "accepted", "rejected", "duplicate", "failed", "dropped", "processing_errors")


@pytest.mark.parametrize("field", STABLE_FIELDS)
def test_drained_movement_of_a_stable_field_between_quiet_readings_opens_a_new_window(bench: Bench, field: str) -> None:
    """Four quiet readings that differ only in one of the nine stable fields (received follows the counters), then
    the last one repeated: the window that closes began at the last movement, so it counts two readings."""
    if field == "started_at":
        bodies = [bench.reading(started_at=f"2026-09-18T10:0{i}:00Z") for i in range(4)]
    else:
        bodies = [bench.reading(**{field: i}) for i in range(4)]
    assert len({mline_of(b) for b in bodies}) == 4
    bench.readings(*bodies)
    r = call_drained(bench)
    assert r.value("RC") == "0", r.out
    assert quiet_reading_of(r) == mline_of(bodies[-1])
    assert r.starting(QUIET_LINE)[0].startswith(f"{QUIET_LINE}2 consecutive readings"), r.out
    assert int((bench.state / "metrics.calls").read_text(encoding="utf-8")) == 5


def test_drained_text_keeps_the_three_defaults_and_the_thirteen_field_order(bench: Bench) -> None:
    text = heredoc_body(helpers_heredoc())
    assert "local quiet=${DRAIN_QUIET_S:-130} step=${DRAIN_STEP_S:-5} limit=${DRAIN_LIMIT_S:-900}" in text
    assert "#   " + " ".join(MLINE_FIELDS) in text                      # the order stated in the comment of _mline
    assert 'sleep "$step"' in text


# --------------------------------------------------------------------------
# 6.1 - drained: the quiet window and the limit are timed on /proc/uptime (quiet-timer repair after finite proof r01)
# --------------------------------------------------------------------------
# _upcs, redefined AFTER the helpers are sourced: each call prints the next value of state/uptime.seq (centiseconds;
# the last value repeats; the word "fail" makes the call fail), so a case sets the monotonic clock itself. drained
# reads it once before the first reading, then once before and once after every reading.
CLOCK_STUB = r"""_upcs() {
  local n v
  n=$(cat "$EGW_STUB_STATE/uptime.n" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$EGW_STUB_STATE/uptime.n"
  v=$(sed -n "${n}p" "$EGW_STUB_STATE/uptime.seq"); [ -n "$v" ] || v=$(tail -n 1 "$EGW_STUB_STATE/uptime.seq")
  [ "$v" != fail ] || return 1
  echo "$v"
}
"""
# A wall-clock step between readings, as this WSL2 host makes them: bash's SECONDS jumps by the given amount at every
# 'sleep' (a function takes precedence over the stub on PATH). A window timed on SECONDS would close (forward) or
# never close (backward); timed on /proc/uptime it is unaffected.
WALL_STEPS = {"no step": "", "forward 1000 s": "sleep() { SECONDS=$((SECONDS + 1000)); }\n",
              "backward 1000 s": "sleep() { SECONDS=$((SECONDS - 1000)); }\n"}
CLOCK_STOP = "STOP: drained: the monotonic clock (/proc/uptime) "
TIMER = "basis /proc/uptime (CLOCK_BOOTTIME, monotonic)"


def clock(t0: int, readings: list[object]) -> list[object]:
    """The clock sequence: t0, then (before, after) for every reading; a reading given as one value is instantaneous."""
    seq: list[object] = [t0]
    for r in readings:
        seq.extend(r if isinstance(r, tuple) else (r, r))
    return seq


def call_drained_clock(bench: Bench, uptime_cs: list[object], quiet_s: str = "490", limit_s: str = "900",
                       prefix: str = "") -> Result:
    (bench.state / "uptime.seq").write_text("".join(f"{v}\n" for v in uptime_cs), encoding="utf-8")
    return bench.run(bench.with_helpers(CLOCK_STUB + prefix + 'drained\necho "RC=$?"'),
                     DRAIN_QUIET_S=quiet_s, DRAIN_LIMIT_S=limit_s)


def success_elapsed(r: Result) -> tuple[int, str]:
    """(whole seconds of the success line, the quiet-timer tail of the same line)."""
    lines = r.starting(QUIET_LINE)
    assert len(lines) == 1, r.out
    m = re.match(r"^drained: queue_depth 0 and identical counters on \d+ consecutive readings over (\d+) s \(.*?\) - .*"
                 r"an observation, not proof that processing has finished; quiet timer: (.*)$", lines[0])
    assert m, lines[0]
    return int(m.group(1)), m.group(2)


@pytest.mark.parametrize("step", list(WALL_STEPS), ids=list(WALL_STEPS))
def test_drained_quiet_window_closes_at_490_s_of_proc_uptime_and_not_at_489_99_whatever_the_wall_clock_does(bench: Bench, step: str) -> None:
    m = bench.metrics()
    # the window opens on the first reading (1000.00 s); 489.99 s is not enough, 490.00 s closes it
    r = call_drained_clock(bench, clock(100000, [100000, 110000, 120000, 130000, 140000, 148999, 149000]),
                           prefix=WALL_STEPS[step])
    assert r.value("RC") == "0", r.out
    assert quiet_reading_of(r) == mline_of(m)
    elapsed, tail = success_elapsed(r)
    assert elapsed == 490, r.out
    assert r.starting(QUIET_LINE)[0].startswith(f"{QUIET_LINE}7 consecutive readings"), r.out
    assert tail.startswith(f"{TIMER}, window start 1000.00 s, end 1490.00 s, elapsed 490.00 s (required 490 s; start "
                           "after the reading that opened the window, end before the reading that closed it); wall clock UTC "), tail
    assert tail.endswith(", recorded only"), tail
    assert bench.metrics_requests() == 7, bench.calls()               # not closed on the 6th reading (489.99 s)


def test_drained_window_is_timed_up_to_the_start_of_the_closing_reading_not_to_its_return(bench: Bench) -> None:
    """A slow last reading: it starts at 489.99 s and returns at 500.00 s. Timed on its return the window would close
    on it; timed on its start it does not, and the next reading (500.00 s) closes it."""
    bench.metrics()
    r = call_drained_clock(bench, clock(0, [0, 20000, 40000, (48999, 50000), 50000]))
    assert r.value("RC") == "0", r.out
    elapsed, tail = success_elapsed(r)
    assert elapsed == 500, r.out
    assert tail.startswith(f"{TIMER}, window start 0.00 s, end 500.00 s, elapsed 500.00 s (required 490 s"), tail
    assert bench.metrics_requests() == 5, bench.calls()


@pytest.mark.parametrize("step", list(WALL_STEPS), ids=list(WALL_STEPS))
def test_drained_limit_is_900_s_of_proc_uptime_whatever_the_wall_clock_does(bench: Bench, step: str) -> None:
    bodies = [bench.reading(accepted=i) for i in range(12)]           # every reading moves a counter: never quiet
    bench.readings(*bodies)
    r = call_drained_clock(bench, clock(0, [i * 10000 for i in range(12)]), prefix=WALL_STEPS[step])
    assert r.value("RC") != "0", r.out
    assert bench.metrics_requests() == 10, bench.calls()               # given up on the reading at 900.00 s, no sooner
    stop = assert_no_quiet_window(r, bodies[9])
    assert stop.startswith("STOP: drained: no quiet window of 490 s within 900 s (last reading: "), stop
    assert stop.endswith(f"; quiet timer: {TIMER}, drain start 0.00 s, end 900.00 s, elapsed 900.00 s (limit 900 s), "
                         "the last window opened at 900.00 s"), stop


def test_drained_activity_restarts_the_window_on_proc_uptime(bench: Bench) -> None:
    quiet, busy = bench.reading(), bench.reading(queue_depth=1)
    bench.readings(quiet, quiet, busy, quiet)                         # then `quiet` for every later request
    # one reading every 100 s: the window of the first two readings is broken by the busy one at 200 s; the next
    # quiet reading (300 s) opens a new window, which closes at 800 s (500 s >= 490 s), within the 900 s limit
    r = call_drained_clock(bench, clock(0, [i * 10000 for i in range(12)]))
    assert r.value("RC") == "0", r.out
    elapsed, tail = success_elapsed(r)
    assert elapsed == 500, r.out
    assert tail.startswith(f"{TIMER}, window start 300.00 s, end 800.00 s, elapsed 500.00 s (required 490 s"), tail
    assert r.starting(QUIET_LINE)[0].startswith(f"{QUIET_LINE}6 consecutive readings"), r.out
    assert bench.metrics_requests() == 9, bench.calls()


def test_drained_490_s_since_the_window_opened_do_not_pass_when_the_reading_that_reaches_them_is_not_quiet(bench: Bench) -> None:
    quiet, busy = bench.reading(), bench.reading(in_progress=1)
    bench.readings(*([quiet] * 5 + [busy] * 20))                      # quiet from 0 s to 400 s, then busy for good
    r = call_drained_clock(bench, clock(0, [i * 10000 for i in range(25)]))
    assert r.value("RC") != "0", r.out
    assert_no_quiet_window(r, busy)


@pytest.mark.parametrize("label, uptime, text, requests", [
    ("unreadable before the first reading", ["fail"], "could not be read - no quiet window can be timed", 0),
    ("unreadable before a reading", [0, "fail"], "could not be read before a reading", 0),
    ("unreadable after a reading", [0, 0, "fail"], "could not be read after a reading", 1),
    ("going back between readings", [0, 0, 20000, 19999], "went back from 200.00 s to 199.99 s", 1),
    ("going back during a reading", [0, 20000, 19999], "went back from 200.00 s to 199.99 s", 1),
])
def test_drained_an_unusable_monotonic_clock_is_never_a_quiet_window(bench: Bench, label: str, uptime: list[object],
                                                                     text: str, requests: int) -> None:
    bench.metrics()
    r = call_drained_clock(bench, uptime)
    assert r.value("RC") != "0", r.out
    stops = r.starting(CLOCK_STOP)
    assert len(stops) == 1 and text in stops[0], r.out
    assert not r.starting(QUIET_LINE) and not r.starting(STOP_NO_WINDOW), r.out
    assert bench.metrics_requests() == requests, bench.calls()


@pytest.mark.parametrize("quiet, limit", [("0130", "900"), ("abc", "900"), ("490", "0900"), ("490", "-1")])
def test_drained_refuses_a_window_or_limit_that_is_not_a_whole_number_of_seconds(bench: Bench, quiet: str, limit: str) -> None:
    """A leading zero would be read as octal (0130 is 88 s) and a word as a variable name (0 s): refused, nothing timed."""
    bench.metrics()
    r = call_drained_clock(bench, clock(0, [0, 100000]), quiet_s=quiet, limit_s=limit)
    assert r.value("RC") != "0", r.out
    stops = r.starting("STOP: drained: DRAIN_QUIET_S=")
    assert len(stops) == 1 and "must both be whole numbers of seconds" in stops[0], r.out
    assert not r.starting(QUIET_LINE) and not r.starting(STOP_NO_WINDOW), r.out
    assert bench.metrics_requests() == 0, bench.calls()


def test_drained_reads_proc_uptime_in_centiseconds_and_never_backwards(bench: Bench) -> None:
    r = bench.run(bench.with_helpers('a=$(_upcs); b=$(_upcs); echo "A=$a"; echo "B=$b"'))
    a, b = r.value("A"), r.value("B")
    assert re.fullmatch(r"[0-9]+", a) and re.fullmatch(r"[0-9]+", b), r.out
    assert int(b) >= int(a), r.out
    up = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    assert abs(up * 100 - int(b)) < 6000, (up, b)                     # the same clock, read within a minute


def test_drained_text_times_the_window_and_the_limit_on_proc_uptime_only(bench: Bench) -> None:
    text = heredoc_body(helpers_heredoc())
    body = text[text.index("drained() {"):text.index("\n}\n", text.index("drained() {"))]
    assert "read -r up rest 2> /dev/null < /proc/uptime" in text
    assert "[ $((pre - since)) -ge $((quiet * 100)) ]" in body
    assert "[ $((now - t0)) -ge $((limit * 100)) ]" in body
    # SECONDS appears only in what is recorded beside the window (sec0 and the elapsed it gives), never in a decision
    rest = body.replace("sec0=$SECONDS", "").replace("bash SECONDS elapsed $((SECONDS - sec0))", "")
    assert "SECONDS" not in rest, [ln for ln in rest.splitlines() if "SECONDS" in ln]


SIX_SERVICES ="egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1"


def harness_argv(bench: Bench) -> list[str]:
    return [a.decode("utf-8") for a in (bench.state / "harness_argv").read_bytes().split(b"\0")[:-1]]


def test_harness_run_hands_the_six_services_to_the_collector_and_fetches_its_companions(bench: Bench) -> None:
    """The hooks of harness_run, split the way the harness splits them (shlex, no shell)."""
    r = bench.run(bench.with_helpers('harness_run smoke_sequence-r01\necho "RC=$?"'))
    assert r.value("RC") == "0", r.out
    argv = harness_argv(bench)
    assert argv[:4] == ["-m", "egw_experiments", "run", "--run-id"]
    opts = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    assert opts["--expect-services"] == SIX_SERVICES
    run_mod.parse_expected_services(opts["--expect-services"])  # the harness accepts the list
    assert "--expect-services {expect_services}" in opts["--collector-start-cmd"]

    dest = "/home/op/Projeto Mestrado/raw/smoke_sequence-r01/logs/collector/resources-smoke_sequence-r01.csv"
    start = shlex.split(run_mod.format_collector_template(
        opts["--collector-start-cmd"], "smoke_sequence-r01", duration_s=150, dest=dest,
        expect_services=SIX_SERVICES.split(",")))
    assert start[0] == "ssh" and start[1] == "egw-tcg"
    assert start[2].endswith(f"--duration 150 --expect-services {SIX_SERVICES}")
    fetch = shlex.split(run_mod.format_collector_template(
        opts["--collector-fetch-cmd"], "smoke_sequence-r01", duration_s=150, dest=dest,
        expect_services=SIX_SERVICES.split(",")))
    script = bench.clone / "src" / "deployment" / "scripts" / "fetch-collector-output.sh"
    assert fetch == ["sh", str(script), "egw-tcg", "/tmp/resources-smoke_sequence-r01.csv", dest]
    assert script.is_file()
    # The events fetch quotes its destination as well.
    events = shlex.split(run_mod.format_cmd_template(opts["--fetch-events-cmd"], "smoke_sequence-r01", "/a b/events.jsonl"))
    assert events[-1] == "/a b/events.jsonl"


def test_harness_run_exit_non_zero_prints_stop(bench: Bench) -> None:
    bench.set("harness_rc", 1)
    r = bench.run(bench.with_helpers('harness_run smoke_sequence-r01\necho "RC=$?"'))
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: harness_run smoke_sequence-r01: egw_experiments run exited non-zero"), r.out


# --------------------------------------------------------------------------
# 6.1 - harness_cmd: the run's Docker events recorder and its bounded SUT logs (work order G3 instrumentation, B)
# --------------------------------------------------------------------------
def sut_fetch_argv(opts: dict[str, str], hook: str, run_id: str, dest: str) -> list[str]:
    """One SUT fetch hook of the harness's argv, rendered and split as the harness runs it (run.py
    execute_collector_hook: format_collector_template, then shlex.split, no shell)."""
    return shlex.split(run_mod.format_collector_template(opts[run_mod.SUT_LOG_FETCH_FLAGS[hook]], run_id, duration_s=150,
                                                         dest=dest, expect_services=SIX_SERVICES.split(",")))


def test_harness_cmd_starts_the_recorder_before_the_harness_and_hands_it_the_three_run_scoped_fetches(bench: Bench) -> None:
    """Test 1 (fault-free): the recorder is started, and found ready, before the harness; the guest epoch of that
    readiness bounds the broker and controller logs and the events; no fault event is demanded; the harness's own
    docker-events fetch stops the unit, so the ending finds it stopped and keeps no partial capture."""
    bench.set("events_t0", 1790000123)
    r = bench.run(bench.with_helpers('harness_run smoke_sequence-r01\necho "RC=$?"'))
    assert r.value("RC") == "0", r.out
    calls = bench.capture_calls()
    assert calls[0] == "capture [start] [smoke_sequence-r01]", calls
    assert calls[-1] == "capture [cleanup] [smoke_sequence-r01] [%s]" % (bench.p / "smoke_sequence-r01.sut" / "events-partial"), calls
    argv = harness_argv(bench)
    opts = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    tools = str(bench.clone / "tools" / "session" / "proof_fetch_sut_log.sh")
    sut = "/home/op/Projeto Mestrado/raw/smoke_sequence-r01/logs/sut"
    assert sut_fetch_argv(opts, "broker_log", "smoke_sequence-r01", f"{sut}/broker.log") == \
        ["bash", tools, "broker", f"{sut}/broker.log", "1790000123"]
    assert sut_fetch_argv(opts, "controller_log", "smoke_sequence-r01", f"{sut}/controller.log") == \
        ["bash", tools, "controller", f"{sut}/controller.log", "1790000123"]
    # Fault-free: RUN_T0 and the run id, and no EXPECTED (events_coverage.py R7 not-required).
    assert sut_fetch_argv(opts, "docker_events", "smoke_sequence-r01", f"{sut}/docker-events.log") == \
        ["bash", tools, "docker-events", f"{sut}/docker-events.log", "1790000123", "smoke_sequence-r01"]
    # The start record is kept, write-once, beside the itest artefacts.
    record = (bench.p / "smoke_sequence-r01.sut" / "events-start.txt").read_text(encoding="utf-8")
    assert "run_guest_t0=1790000123" in record


def test_harness_cmd_whose_recorder_is_not_ready_never_starts_the_harness(bench: Bench) -> None:
    """Capture start failure: the harness is not run (harness_cmd answers 2, as the harness's own refusal does, so
    test 6's line never reads another run's directory), the unit is left stopped, and harness_run STOPs."""
    bench.set("events_start_rc", 3)
    r = bench.run(bench.with_helpers('harness_cmd smoke_sequence-r01; echo "HC=$?"\nharness_run smoke_sequence-r02\necho "RC=$?"'))
    assert r.value("HC") == "2", r.out
    assert r.value("RC") != "0", r.out
    assert not (bench.state / "harness_argv").exists(), "the harness was started without a ready recorder"
    assert r.starting("STOP: events_start smoke_sequence-r01: the Docker events recorder was NOT found ready"), r.out
    assert r.starting("STOP: harness_cmd smoke_sequence-r01: the harness was NOT started"), r.out
    assert r.starting("STOP: harness_run smoke_sequence-r02: egw_experiments run exited non-zero"), r.out
    assert "capture [cleanup] [smoke_sequence-r01]" in bench.capture_calls()
    assert (bench.state / "unit-smoke_sequence-r01").read_text(encoding="utf-8").strip() != "active"


def test_harness_cmd_refuses_a_run_id_whose_start_record_exists_and_starts_nothing(bench: Bench) -> None:
    """Write-once: an outer attempt never reuses another execution's record for the same run id."""
    (bench.p / "smoke_sequence-r01.sut").mkdir(parents=True)
    (bench.p / "smoke_sequence-r01.sut" / "events-start.txt").write_text("run_guest_t0=1\n", encoding="utf-8")
    r = bench.run(bench.with_helpers('harness_cmd smoke_sequence-r01; echo "HC=$?"'))
    assert r.value("HC") == "2", r.out
    assert r.starting("STOP: events_start smoke_sequence-r01: "), r.out
    assert bench.capture_calls() == [] and not (bench.state / "harness_argv").exists()


def test_test_6_line_demands_the_events_of_its_own_restart_and_not_the_proofs_sigkill(bench: Bench) -> None:
    """Test 6's line, executed: its harness hands the docker-events fetch the actions a compose restart must produce
    for the controller whatever signal ended it (die, start), never 'kill' (the proof's R7 requires signal 9 of a
    kill), and its restart command, snapshots and identity are handed as before."""
    cmds = _host_commands("### Test 6")
    plan = bench.home / "egw-tcg" / "pilot" / "campaign_plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({"runs": [{"run_id": "controller_restart-r01", "seed": 7}]}), encoding="utf-8")
    (bench.state / "identity_capture").write_text(capture_text(), encoding="utf-8")
    body = [_one(cmds, "RID="), _one(cmds, "SEED="), _one(cmds, "RESTART="), _one(cmds, "RAW6="), _one(cmds, "T6=stop; if")]
    r = bench.run(bench.with_helpers("\n".join(body + ['echo "T6=$T6"'])))
    argv = harness_argv(bench)
    opts = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    dest = "/raw/controller_restart-r01/logs/sut/docker-events.log"
    events = sut_fetch_argv(opts, "docker_events", "controller_restart-r01", dest)
    assert events[2:] == ["docker-events", dest, "1790000000", "controller_restart-r01", "die,start"], events
    assert "kill" not in events[-1]
    assert opts["--restart-cmd"].endswith("restart controller'") and opts["--restart-at-s"] == "300"
    assert bench.capture_calls()[0] == "capture [start] [controller_restart-r01]"
    # The stub harness seals nothing, so the line stops as it did before: the capture changes none of its checks.
    assert r.starting("STOP: test 6: the harness run was not sealed"), r.out
    assert r.value("T6") == "stop", r.out


# --------------------------------------------------------------------------
# 6.1 - config_identity: the configuration identity captured on the guest, as the harness validates it (F6b)
# --------------------------------------------------------------------------
#: What the remote script of config_identity prints on the guest, one key=value line per field, as a realistic
#: stack answers it (values of the shape the harness validates; the hashes are placeholders of the right form).
IDENTITY_CAPTURE = {
    "sha256": "3f" * 32,
    "max_inflight_messages": "4999",
    "max_inflight_bytes": "0",
    "max_queued_messages": "1000",
    "max_queued_bytes": "0",
    "persistent_client_expiration": "1h",
    "sys_interval": "10",
    "reloaded": "0",
    "stop_grace_period": "130s",
    "image": "sha256:" + "5a" * 32,
    "commit": "0123abcdef0123abcdef0123abcdef0123abcdef",
    "paho": "2.1.0",
}


def capture_text(**changes: str | None) -> str:
    """The capture with ``changes`` applied: a None value drops the line (the guest printed nothing for it)."""
    values = {**IDENTITY_CAPTURE, **changes}
    return "".join(f"{k}={v}\n" for k, v in values.items() if v is not None)


def call_config_identity(bench: Bench, capture: str | None = None, out: str = "$P/idt.json", **env: str) -> Result:
    if capture is not None:
        (bench.state / "identity_capture").write_text(capture, encoding="utf-8")
    return bench.run(bench.with_helpers(f'config_identity {out}\necho "RC=$?"'), **env)


def test_config_identity_writes_the_identity_the_harness_validates(bench: Bench) -> None:
    r = call_config_identity(bench, capture_text())
    assert r.value("RC") == "0", r.out
    assert not r.starting("STOP:"), r.out
    doc = json.loads((bench.p / "idt.json").read_text(encoding="utf-8"))
    assert run_mod.configuration_identity_problems(doc) == []
    assert doc == {
        "broker_conf_sha256": "3f" * 32,
        "broker_conf_values": {"max_inflight_messages": 4999, "max_inflight_bytes": 0, "max_queued_messages": 1000,
                               "max_queued_bytes": 0, "persistent_client_expiration": "1h", "sys_interval": 10},
        "broker_reloaded": False,
        "stop_grace_period": "130s",
        "controller_image_id": "sha256:" + "5a" * 32,
        "controller_source_commit": "0123abcdef0123abcdef0123abcdef0123abcdef",
        "paho_version": "2.1.0",
        "a3_choice": "a",
    }
    # One ssh session reads every value on the guest, from the sources the harness names (the remote script
    # spans several lines of the stub's log).
    log = "\n".join(bench.ssh_log())
    assert log.count("ssh [egw-tcg] [") == 1 and log.count("sha256sum") == 1
    call = log
    for source in ("sudo sha256sum", "mosquitto/config/mosquitto.conf", "max_inflight_messages", "max_inflight_bytes",
                   "max_queued_messages", "max_queued_bytes", "persistent_client_expiration", "sys_interval",
                   "logs --no-color mosquitto", "Reloading config", "stop_grace_period", "compose.yaml",
                   "docker inspect -f", "{{.Image}}", "egw-controller-1", "org.opencontainers.image.revision",
                   "docker exec egw-controller-1 python", "paho-mqtt"):
        assert source in call, source


def test_config_identity_reloaded_is_true_when_the_broker_log_holds_a_reload_line(bench: Bench) -> None:
    r = call_config_identity(bench, capture_text(reloaded="2"))
    assert r.value("RC") == "0", r.out
    doc = json.loads((bench.p / "idt.json").read_text(encoding="utf-8"))
    assert doc["broker_reloaded"] is True and run_mod.configuration_identity_problems(doc) == []


@pytest.mark.parametrize("key", sorted(IDENTITY_CAPTURE))
def test_config_identity_with_a_missing_value_stops_and_writes_no_file(bench: Bench, key: str) -> None:
    """A field the guest did not answer (no line, or an empty value): STOP naming it, nothing written - the
    harness would refuse the identity, and an invented value would state what the run did not rest on."""
    for capture in (capture_text(**{key: None}), capture_text(**{key: ""})):
        r = call_config_identity(bench, capture)
        assert r.value("RC") != "0", r.out
        assert r.starting("STOP: config_identity:"), r.out
        assert any(f"config_identity: {key} " in ln for ln in r.lines), r.out
        assert not (bench.p / "idt.json").exists()


@pytest.mark.parametrize("key, value", [
    ("sha256", "3f" * 31), ("max_inflight_messages", "many"), ("sys_interval", "-1"), ("reloaded", "yes"),
    ("image", "5a" * 32), ("commit", "0123ab"), ("commit", "not-a-commit"),
])
def test_config_identity_with_a_value_of_the_wrong_form_stops_and_writes_no_file(bench: Bench, key: str, value: str) -> None:
    r = call_config_identity(bench, capture_text(**{key: value}))
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: config_identity:"), r.out
    assert any(f"config_identity: {key} " in ln and value in ln for ln in r.lines), r.out
    assert not (bench.p / "idt.json").exists()


def test_config_identity_ssh_failure_stops_and_writes_no_file(bench: Bench) -> None:
    bench.set("ssh_identity_rc", 255)
    r = call_config_identity(bench, capture_text())
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: config_identity: ssh egw-tcg exited 255"), r.out
    assert not (bench.p / "idt.json").exists()


def test_config_identity_is_write_once_and_needs_a_path(bench: Bench) -> None:
    bench.p.mkdir(parents=True, exist_ok=True)
    (bench.p / "idt.json").write_text("{}\n", encoding="utf-8")
    r = call_config_identity(bench, capture_text())
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: config_identity:") and "exists" in r.out
    assert (bench.p / "idt.json").read_text(encoding="utf-8") == "{}\n"
    assert "sha256sum" not in "\n".join(bench.ssh_log())  # nothing was read
    r = call_config_identity(bench, capture_text(), out="")
    assert r.value("RC") != "0" and r.starting("STOP: config_identity: usage"), r.out


# 6.1 - config_identity: the remote fragment executed under stubs (review of 2026-09-25, D2): the broker log is
# read with its exit status, so a failed or empty read never becomes broker_reloaded=false
# --------------------------------------------------------------------------
GUEST_CONF = "".join(f"{k} {v}\n" for k, v in (
    ("listener", "8883 0.0.0.0"), ("allow_anonymous", "false"), ("persistence", "true"),
    ("max_inflight_messages", "4999"), ("max_inflight_bytes", "0"), ("max_queued_messages", "1000"),
    ("max_queued_bytes", "0"), ("persistent_client_expiration", "1h"), ("sys_interval", "10"), ("log_dest", "stdout"),
))
GUEST_COMPOSE = "services:\n  mosquitto:\n    image: a\n  controller:\n    image: b\n    stop_grace_period: 130s\n  ditto:\n    image: c\n"
BROKER_LOG_START = ("mosquitto-1  | 1758750000: mosquitto version 2.0.22 starting\n"
                    "mosquitto-1  | 1758750000: Config loaded from /mosquitto/config/mosquitto.conf.\n"
                    "mosquitto-1  | 1758750000: Opening ipv4 listen socket on port 8883.\n")
BROKER_LOG_RELOADED = BROKER_LOG_START + ("mosquitto-1  | 1758750600: Reloading config.\n"
                                         "mosquitto-1  | 1758750600: Config loaded from /mosquitto/config/mosquitto.conf.\n")


def guest_for_identity(bench: Bench, broker_log: str | None, logs_rc: int = 0, partial: bool = False) -> Path:
    """The stub guest the ssh stub's executing mode runs config_identity's remote script against: the deployment
    directory with the broker configuration and compose.yaml the script reads, the sudo and docker stubs, and the
    broker log the stub docker serves (None: the read succeeds with nothing) with the exit status of that read;
    `partial` serves the log before a non-zero exit (a read that failed after streaming part of the log)."""
    dep = bench.tmp / "guest-deployment"
    (dep / "mosquitto" / "config").mkdir(parents=True)
    (dep / "mosquitto" / "config" / "mosquitto.conf").write_text(GUEST_CONF, encoding="utf-8")
    (dep / "compose.yaml").write_text(GUEST_COMPOSE, encoding="utf-8")
    bench.install("sudo", STUB_SUDO)
    bench.install("docker", STUB_DOCKER)
    bench.set("identity_exec")
    bench.set("guest_image_hex", "5a" * 32)
    bench.set("guest_commit", "0123abcdef0123abcdef0123abcdef0123abcdef")
    bench.set("guest_paho", "2.1.0")
    bench.set("docker_logs_rc", logs_rc)
    if partial:
        bench.set("docker_logs_partial")
    if broker_log is not None:
        (bench.state / "guest_broker_log").write_text(broker_log, encoding="utf-8")
    return dep


def call_config_identity_on_the_guest(bench: Bench, dep: Path, **env: str) -> Result:
    return bench.run(bench.with_helpers('config_identity $P/idt.json\necho "RC=$?"'), EGW_STUB_DEPLOYMENT=str(dep), **env)


def test_config_identity_fragment_reads_the_guest_and_a_log_without_a_reload_line_is_not_reloaded(bench: Bench) -> None:
    """The remote script itself, run by the ssh stub under sh against the stub guest: every value comes from the files
    and the docker answers of that guest, and a successful read of a log that holds no reload line is False."""
    dep = guest_for_identity(bench, BROKER_LOG_START)
    r = call_config_identity_on_the_guest(bench, dep)
    assert r.value("RC") == "0", r.out
    assert not r.starting("STOP:"), r.out
    doc = json.loads((bench.p / "idt.json").read_text(encoding="utf-8"))
    assert run_mod.configuration_identity_problems(doc) == []
    assert doc == {
        "broker_conf_sha256": hashlib.sha256(GUEST_CONF.encode("utf-8")).hexdigest(),
        "broker_conf_values": {"max_inflight_messages": 4999, "max_inflight_bytes": 0, "max_queued_messages": 1000,
                               "max_queued_bytes": 0, "persistent_client_expiration": "1h", "sys_interval": 10},
        "broker_reloaded": False,
        "stop_grace_period": "130s",
        "controller_image_id": "sha256:" + "5a" * 32,
        "controller_source_commit": "0123abcdef0123abcdef0123abcdef0123abcdef",
        "paho_version": "2.1.0",
        "a3_choice": "a",
    }
    calls = bench.calls()
    assert "docker compose --env-file .env --env-file images.lock.env logs --no-color mosquitto" in calls
    assert "sudo sha256sum mosquitto/config/mosquitto.conf" in calls


def test_config_identity_fragment_a_log_with_a_reload_line_is_reloaded(bench: Bench) -> None:
    dep = guest_for_identity(bench, BROKER_LOG_RELOADED)
    r = call_config_identity_on_the_guest(bench, dep)
    assert r.value("RC") == "0", r.out
    doc = json.loads((bench.p / "idt.json").read_text(encoding="utf-8"))
    assert doc["broker_reloaded"] is True and run_mod.configuration_identity_problems(doc) == []


@pytest.mark.parametrize("partial", [False, True], ids=["nothing-streamed", "partial-log-streamed"])
def test_config_identity_fragment_a_log_that_could_not_be_read_stops_and_writes_no_file(bench: Bench, partial: bool) -> None:
    """docker compose logs fails, with nothing on stdout or after streaming part of the log (a part that even holds
    a reload line): the guest names the failed read and exits 5, the helper stops with no file, and nothing after
    the read runs on the guest - "no reload line" is never inferred from a log that was not read to its end. The
    partial case pins the exit-status arm of the guard on its own: the output is not empty, only the status fails."""
    dep = guest_for_identity(bench, BROKER_LOG_RELOADED, logs_rc=1, partial=partial)
    r = call_config_identity_on_the_guest(bench, dep)
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: config_identity: the broker log was NOT read on the guest"), r.out
    size = len(BROKER_LOG_RELOADED.rstrip("\n")) if partial else 0
    assert any(f"docker compose logs exit 1, {size} characters" in ln for ln in r.lines), r.out
    assert not (bench.p / "idt.json").exists()
    assert "docker inspect" not in bench.calls() and "docker exec" not in bench.calls()


def test_config_identity_fragment_an_empty_log_read_stops_and_writes_no_file(bench: Bench) -> None:
    """docker compose logs exits 0 with nothing: not an observation of the broker either (a running broker logs
    its start), so the helper stops with no file."""
    dep = guest_for_identity(bench, None)
    r = call_config_identity_on_the_guest(bench, dep)
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: config_identity: the broker log was NOT read on the guest"), r.out
    assert any("docker compose logs exit 0, 0 characters" in ln for ln in r.lines), r.out
    assert not (bench.p / "idt.json").exists()


# --------------------------------------------------------------------------
# Test 6 - the lines that hand the identity, the bound drain transcript and the post-drain copy to the harness
# --------------------------------------------------------------------------
def test_test_6_harness_line_captures_the_identity_and_hands_it_to_the_harness() -> None:
    line = _one(_host_commands("### Test 6"), "T6=stop; if")
    capture = "config_identity $P/$RID.config_identity.json"
    assert capture in line and line.index(capture) < line.index("harness_cmd $RID")
    assert "--config-identity-from $P/$RID.config_identity.json" in line.split("harness_cmd $RID", 1)[1]
    # No identity tolerance: only the restart-evidence-step reasons are expected from this harness run.
    assert "'without its restart evidence step' not in r" in line
    assert "identity" not in line.split("python3 -c", 1)[1].split("sys.exit", 1)[0]


def test_test_6_delta_line_names_the_post_drain_copy() -> None:
    line = _one(_host_commands("### Test 6"), '[ "$T6" = collected ] && $REC delta')
    command = line.split("     #", 1)[0]  # the command, without its trailing comment
    assert "--events $RAW6/events.post-drain.jsonl" in command
    assert "--also" not in command


def test_test_6_warm_up_variant_is_deferred_and_no_command_reads_another_runs_post_drain_copy() -> None:
    """Review of 2026-09-25, D3: the example of the warm-up variant named the preceding restart run's post-drain
    copy through $RAW6; it is withdrawn with a statement of what the variant needs. Test 6's commands hold no
    --also, and the main delta line is the only command that names --events."""
    cmds = _host_commands("### Test 6")
    assert [c for c in cmds if "--also" in c.split("     #", 1)[0]] == []  # the command part, not its comment
    with_events = [c for c in cmds if "--events" in c.split("     #", 1)[0]]
    assert with_events == [_one(cmds, '[ "$T6" = collected ] && $REC delta')]
    text = "\n".join(_section("### Test 6"))
    assert "No executable procedure for that variant is given here" in text
    assert "warm-up" in text and "--also" in text  # the option and the reason for it are still explained


def test_helper_table_names_config_identity() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "| `config_identity <out-file>` |" in text


def drain_line() -> str:
    return _one(_host_commands("### Test 6"), 'if [ "$T6" = ok ]; then printf')


def call_drain_line(bench: Bench, **env: str) -> Result:
    return bench.run(bench.with_helpers("\n".join(("RID=controller_restart-r01", "T6=ok", drain_line(),
                                                   'echo "T6=$T6"'))), **env)


def test_test_6_drain_line_writes_the_envelope_then_the_helpers_quiet_line(bench: Bench) -> None:
    """The transcript the collect line ingests: the envelope written before `drained` runs, then the helper's
    line through tee -a. The harness binds it to the run by that envelope (run.py, F6a) and classifies it quiet."""
    r = call_drain_line(bench)
    assert r.value("T6") == "drained", r.out
    text = (bench.p / "controller_restart-r01.drained.txt").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) == 2, text
    assert re.fullmatch(r"run_id=controller_restart-r01 captured_utc=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", lines[0])
    assert lines[1].startswith(QUIET_LINE)
    problems, captured = run_mod.drain_transcript_envelope_problems(
        text, run_id="controller_restart-r01", window_end_utc="2026-09-18T10:00:00.000Z")
    assert problems == [] and captured == lines[0].split("captured_utc=")[1]
    assert run_mod.classify_drain_output(text, None) == "quiet"
    assert run_mod.drain_transcript_envelope_problems(text, run_id="controller_restart-r02",
                                                       window_end_utc="2026-09-18T10:00:00.000Z")[0]


def test_test_6_drain_line_that_gives_up_keeps_the_envelope_and_the_stop_line(bench: Bench) -> None:
    bench.metrics(queue_depth=1)
    r = call_drain_line(bench, DRAIN_LIMIT_S="0")
    assert r.value("T6") == "gaveup", r.out
    assert r.starting("STOP: test 6: 'drained' gave up or failed"), r.out
    text = (bench.p / "controller_restart-r01.drained.txt").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("run_id=controller_restart-r01 captured_utc=") and lines[1].startswith(STOP_NO_WINDOW)
    assert run_mod.drain_transcript_envelope_problems(
        text, run_id="controller_restart-r01", window_end_utc="2026-09-18T10:00:00.000Z")[0] == []
    assert run_mod.classify_drain_output(text, None) == "gave-up"


# --------------------------------------------------------------------------
# defect 1 - accounted: identities, not totals
# --------------------------------------------------------------------------
def test_accounted_every_published_record_has_a_logged_outcome_returns_0_and_prints_ok(bench: Bench) -> None:
    rid = "itest-acc-01"
    before = bench.metrics()
    prepare_accounted(bench, rid, sent("msg-A", "msg-B", "msg-C", "msg-D"),
                      [event(rid, "msg-A", "accepted"), event(rid, "msg-B", "rejected"),
                       event(rid, "msg-C", "failed"), event(rid, "msg-D", "accepted"), event(rid, "msg-D", "duplicate")], before)
    bench.metrics(accepted=2, rejected=1, failed=1, duplicate=1)
    r = call_accounted(bench, rid)
    assert r.value("RC") == "0", r.out
    assert r.starting(f"OUTCOME RECONCILIATION {rid}: published=4 with_logged_outcome=4 without_logged_outcome=0 not_reconcilable=0"), r.out
    assert r.starting("-> OK: every published record of this run has a logged outcome"), r.out
    assert not r.starting("STOP"), r.out


def test_accounted_review_case_a_accepted_then_duplicate_b_without_record_counters_equal_sent_is_refused_and_names_b(bench: Bench) -> None:
    rid = "itest-acc-02"
    before = bench.metrics()
    prepare_accounted(bench, rid, sent("msg-A", "msg-B"),
                      [event(rid, "msg-A", "accepted"), event(rid, "msg-A", "duplicate")], before)
    bench.metrics(accepted=1, duplicate=1)          # the five counters moved by 2 for 2 published records
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting(f"OUTCOME RECONCILIATION {rid}: published=2 with_logged_outcome=1 without_logged_outcome=1"), r.out
    assert any("total=2" in ln and "decides nothing" in ln for ln in r.lines), r.out   # it IS the reviewer's scenario
    assert r.starting("  NO LOGGED OUTCOME: msg-B "), r.out
    assert not any("msg-A" in ln for ln in r.starting("  NO LOGGED OUTCOME")), r.out
    assert r.starting(f"STOP: accounted {rid}:"), r.out
    assert not any(ln.startswith("-> OK") for ln in r.lines), r.out
    assert not (bench.p / f"{rid}.unaccounted.txt").exists()


def test_accounted_outcome_logged_under_another_run_id_does_not_count(bench: Bench) -> None:
    rid = "itest-acc-03"
    before = bench.metrics()
    prepare_accounted(bench, rid, sent("msg-A", "msg-B"),
                      [event(rid, "msg-A", "accepted"), event("some-earlier-run", "msg-B", "accepted")], before)
    bench.metrics(accepted=2)
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting("  NO LOGGED OUTCOME: msg-B "), r.out
    assert not any(ln.startswith("-> OK") for ln in r.lines), r.out


def test_accounted_record_whose_outcome_is_not_one_of_the_four_does_not_count(bench: Bench) -> None:
    rid = "itest-acc-04"
    before = bench.metrics()
    prepare_accounted(bench, rid, sent("msg-A", "msg-B"),
                      [event(rid, "msg-A", "accepted"), event(rid, "msg-B", "received")], before)
    bench.metrics(accepted=1)
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting("  NO LOGGED OUTCOME: msg-B "), r.out


def test_accounted_message_id_published_twice_is_not_reconcilable_and_never_ok(bench: Bench) -> None:
    rid = "itest-acc-05"
    before = bench.metrics()
    prepare_accounted(bench, rid, sent("msg-A", "msg-A", "msg-B"),
                      [event(rid, "msg-A", "accepted"), event(rid, "msg-B", "accepted")], before)
    bench.metrics(accepted=2, duplicate=1)
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert len(r.starting("  NOT RECONCILABLE: msg-A ")) == 2, r.out
    assert any("not_reconcilable=2" in ln for ln in r.starting("OUTCOME RECONCILIATION")), r.out
    assert not any(ln.startswith("-> OK") for ln in r.lines), r.out


def test_accounted_fetched_event_log_missing_is_refused_before_anything_is_read(bench: Bench) -> None:
    rid = "itest-acc-06"
    prepare_accounted(bench, rid, sent("msg-A"), None, bench.metrics())
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting(f"STOP: accounted {rid}: sent_events.jsonl, the fetched events.jsonl or metrics.before.json is missing or empty"), r.out
    assert not r.starting("OUTCOME RECONCILIATION"), r.out


def test_accounted_fetched_event_log_empty_is_refused(bench: Bench) -> None:
    rid = "itest-acc-07"
    prepare_accounted(bench, rid, sent("msg-A"), [], bench.metrics())
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting(f"STOP: accounted {rid}:") and "missing or empty" in r.out, r.out
    assert not any(ln.startswith("-> OK") for ln in r.lines), r.out


def test_accounted_fetched_event_log_malformed_is_not_evaluated_and_nothing_is_decided(bench: Bench) -> None:
    rid = "itest-acc-08"
    prepare_accounted(bench, rid, sent("msg-A"), [], bench.metrics())
    (bench.p / rid / "events.jsonl").write_text('{"run_id": "itest-acc-08", "message_id": "msg-A", "outc', encoding="utf-8")
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert any("could not be evaluated" in ln for ln in r.starting(f"STOP: accounted {rid}:")), r.out
    assert not any(ln.startswith("-> OK") for ln in r.lines), r.out


def test_fetch_scp_failure_prints_stop_and_leaves_no_event_log(bench: Bench) -> None:
    rid = "itest-acc-09"
    prepare_accounted(bench, rid, sent("msg-A"), None, bench.metrics())
    r = bench.run(bench.with_helpers(f'fetch {rid} && accounted {rid}\necho "RC=$?"'))
    assert r.value("RC") != "0", r.out
    assert r.starting(f"STOP: fetch {rid}: scp of events.jsonl failed"), r.out
    assert not r.starting("OUTCOME RECONCILIATION"), r.out
    assert not (bench.p / rid / "events.jsonl").exists()


def test_accounted_controller_restart_between_snapshots_counters_are_not_compared_and_identities_still_decide_ok(bench: Bench) -> None:
    rid = "itest-acc-10"
    before = bench.metrics(accepted=40)
    prepare_accounted(bench, rid, sent("msg-A", "msg-B"),
                      [event(rid, "msg-A", "accepted"), event(rid, "msg-B", "accepted")], before)
    bench.metrics(started_at="2026-09-18T11:30:00Z", accepted=1)      # new process: counters started again
    r = call_accounted(bench, rid)
    assert r.value("RC") == "0", r.out
    assert r.starting("  counters since the before reading: not comparable (started_at differs"), r.out
    assert not any("total=" in ln for ln in r.lines), r.out
    assert r.starting("-> OK: every published record of this run has a logged outcome"), r.out


def test_accounted_controller_restart_between_snapshots_with_b_missing_is_refused_and_names_b(bench: Bench) -> None:
    rid = "itest-acc-11"
    before = bench.metrics(accepted=40)
    prepare_accounted(bench, rid, sent("msg-A", "msg-B"), [event(rid, "msg-A", "accepted")], before)
    bench.metrics(started_at="2026-09-18T11:30:00Z", accepted=1)
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting("  counters since the before reading: not comparable"), r.out
    assert r.starting("  NO LOGGED OUTCOME: msg-B "), r.out
    assert not any(ln.startswith("-> OK") for ln in r.lines), r.out


def test_accounted_queue_not_empty_is_refused_even_when_every_identity_has_an_outcome(bench: Bench) -> None:
    rid = "itest-acc-12"
    before = bench.metrics()
    prepare_accounted(bench, rid, sent("msg-A"), [event(rid, "msg-A", "accepted")], before)
    bench.metrics(accepted=1, queue_depth=3)
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting("-> queue_depth=3 at this reading"), r.out
    assert not any(ln.startswith("-> OK") for ln in r.lines), r.out


def test_accounted_metrics_unreachable_is_refused(bench: Bench) -> None:
    rid = "itest-acc-13"
    prepare_accounted(bench, rid, sent("msg-A"), [event(rid, "msg-A", "accepted")], bench.metrics())
    (bench.state / "metrics.json").unlink()
    r = call_accounted(bench, rid)
    assert r.value("RC") != "0", r.out
    assert any("/metrics failed" in ln for ln in r.starting(f"STOP: accounted {rid}:")), r.out


def test_accounted_operator_accepts_b_missing_the_fact_is_recorded_and_no_ok_line_is_printed(bench: Bench) -> None:
    rid = "itest-acc-14"
    before = bench.metrics()
    prepare_accounted(bench, rid, sent("msg-A", "msg-B"), [event(rid, "msg-A", "accepted")], before)
    bench.metrics(accepted=1)
    r = call_accounted(bench, rid, ACCEPT_UNACCOUNTED="1")
    assert r.value("RC") == "0", r.out                                 # the capture may go on ...
    assert r.starting("  NO LOGGED OUTCOME: msg-B "), r.out
    assert any("accepted by the operator" in ln for ln in r.starting("-> 1 published record(s)")), r.out
    assert not any(ln.startswith("-> OK") for ln in r.lines), r.out
    assert (bench.p / f"{rid}.unaccounted.txt").stat().st_size > 0     # ... and 'finish' ends non-zero on this file


# --------------------------------------------------------------------------
# defect 3 - evidence capture: run_test / sim_post
# --------------------------------------------------------------------------
def full_run(bench: Bench, rid: str, ids: tuple[str, ...] = ("msg-A", "msg-B"), logged: tuple[str, ...] | None = None) -> None:
    bench.jsonl("sent_events.jsonl", sent(*ids))
    bench.jsonl("remote_events.jsonl", [event(rid, m, "accepted") for m in (ids if logged is None else logged)])


def call_run_test(bench: Bench, rid: str, **env: str) -> Result:
    return bench.run(bench.with_helpers(f'run_test {rid} 42 --scenario smoke --duration 30\necho "RC=$?"'), **env)


def test_run_test_transcript_written_every_step_0_returns_0_and_prints_procedure_complete(bench: Bench) -> None:
    rid = "itest-ev-01"
    full_run(bench, rid)
    r = call_run_test(bench, rid)
    assert r.value("RC") == "0", r.out
    assert r.starting(f"TEST STATUS {rid}: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE"), r.out
    assert not r.starting("STOP"), r.out
    assert "egw_simulator stub: done" in (bench.p / f"{rid}.stderr.txt").read_text(encoding="utf-8")
    assert bench.simulator_calls() == 1
    assert (bench.p / f"{rid}.metrics.after.json").exists() and (bench.p / f"{rid}.twins.after.json").exists()


def test_run_test_transcript_target_cannot_be_created_simulator_is_never_started(bench: Bench) -> None:
    rid = "itest-ev-02"
    full_run(bench, rid)
    (bench.p / f"{rid}.stderr.txt").mkdir(parents=True)               # unwritable for every uid, root included
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    assert any("cannot be written -> simulator NOT started, nothing published" in ln for ln in r.starting(f"STOP: TEST STATUS {rid}:")), r.out
    assert bench.simulator_calls() == 0
    assert "PROCEDURE COMPLETE" not in r.out


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="/dev/full is needed for a real write failure of tee")
def test_run_test_real_tee_write_failure_with_simulator_exit_0_is_failed_and_post_still_runs(bench: Bench) -> None:
    rid = "itest-ev-03"
    full_run(bench, rid)
    bench.p.mkdir(parents=True, exist_ok=True)
    (bench.p / f"{rid}.stderr.txt").symlink_to("/dev/full")           # can be opened and truncated, every write fails
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    status = r.starting(f"STOP: TEST STATUS {rid}: simulator exit=0 transcript (tee) exit=")
    assert status and "transcript (tee) exit=0" not in status[0] and "-> FAILED" in status[0], r.out
    assert "PROCEDURE COMPLETE" not in r.out
    assert "itest_reconcile mark" in bench.calls()                     # marker and evidence still collected


def test_run_test_tee_reports_failure_after_writing_with_simulator_exit_0_is_failed(bench: Bench) -> None:
    rid = "itest-ev-04"
    full_run(bench, rid)
    bench.install("tee", STUB_TEE_FAILS)
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting(f"STOP: TEST STATUS {rid}: simulator exit=0 transcript (tee) exit=1 post=0 -> FAILED"), r.out
    assert "PROCEDURE COMPLETE" not in r.out
    assert (bench.p / f"{rid}.stderr.txt").stat().st_size > 0          # the file alone would not have shown it


def test_run_test_empty_transcript_with_simulator_exit_0_is_failed(bench: Bench) -> None:
    rid = "itest-ev-05"
    full_run(bench, rid)
    bench.set("sim_silent")
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting(f"STOP: TEST STATUS {rid}: simulator exit=0 transcript (tee) exit=0 post=0 -> FAILED"), r.out
    assert "PROCEDURE COMPLETE" not in r.out


def test_run_test_simulator_exit_3_is_failed_with_its_own_status_and_post_still_runs(bench: Bench) -> None:
    rid = "itest-ev-06"
    full_run(bench, rid)
    bench.set("sim_rc", 3)
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting(f"STOP: TEST STATUS {rid}: simulator exit=3 transcript (tee) exit=0 post=0 -> FAILED"), r.out
    assert "itest_reconcile mark" in bench.calls()


def test_run_test_precondition_fails_ready_not_200_simulator_is_never_called(bench: Bench) -> None:
    rid = "itest-ev-07"
    full_run(bench, rid)
    bench.set("ready_code", 503)
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting(f"STOP: TEST STATUS {rid}: precondition failed -> simulator NOT started, nothing published"), r.out
    assert bench.simulator_calls() == 0
    assert not (bench.p / f"{rid}.stderr.txt").exists() and not (bench.p / f"{rid}.metrics.before.json").exists()


def test_run_test_precondition_fails_run_id_already_used_simulator_is_never_called_and_nothing_is_overwritten(bench: Bench) -> None:
    rid = "itest-ev-08"
    full_run(bench, rid)
    bench.p.mkdir(parents=True, exist_ok=True)
    earlier = bench.p / f"{rid}.metrics.before.json"
    earlier.write_text('{"earlier": "run"}', encoding="utf-8")
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    assert any("this run id was already used" in ln for ln in r.starting(f"STOP: pre {rid}:")), r.out
    assert bench.simulator_calls() == 0
    assert earlier.read_text(encoding="utf-8") == '{"earlier": "run"}'


def test_run_test_precondition_fails_metrics_unreachable_simulator_is_never_called(bench: Bench) -> None:
    rid = "itest-ev-09"
    full_run(bench, rid)
    (bench.state / "metrics.json").unlink()
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting(f"STOP: TEST STATUS {rid}: precondition failed"), r.out
    assert bench.simulator_calls() == 0


def test_run_test_b_without_logged_outcome_is_failed_and_the_after_state_is_not_captured(bench: Bench) -> None:
    rid = "itest-ev-10"
    full_run(bench, rid, logged=("msg-A",))
    r = call_run_test(bench, rid)
    assert r.value("RC") != "0", r.out
    assert r.starting("  NO LOGGED OUTCOME: msg-B "), r.out
    assert r.starting(f"STOP: finish {rid}: the 'after' state was NOT captured"), r.out
    assert "PROCEDURE COMPLETE" not in r.out
    assert not (bench.p / f"{rid}.metrics.after.json").exists()


def test_run_test_b_missing_accepted_by_the_operator_is_captured_and_still_ends_non_zero(bench: Bench) -> None:
    rid = "itest-ev-11"
    full_run(bench, rid, logged=("msg-A",))
    r = call_run_test(bench, rid, ACCEPT_UNACCOUNTED="1")
    assert r.value("RC") != "0", r.out
    assert any("report as measured, not as complete" in ln for ln in r.starting(f"STOP: finish {rid}:")), r.out
    assert "PROCEDURE COMPLETE" not in r.out
    assert (bench.p / f"{rid}.metrics.after.json").exists() and (bench.p / f"{rid}.unaccounted.txt").exists()


# --------------------------------------------------------------------------
# defect 3 - the explicit lines of 6.2, 6.3, 6.4 and the broker log line of test 9
# --------------------------------------------------------------------------
def flow_62() -> tuple[str, str]:
    cmds = _host_commands("### 6.2")
    return _one(cmds, "RUN="), _one(cmds, "if pre $RUN")


def run_id_of(assignment: str, var: str) -> str:
    m = re.match(var + r"=([A-Za-z0-9_-]+)", assignment)
    assert m, f"no {var}=<id> in {assignment!r}"
    return m.group(1)


def test_flow_6_2_to_6_4_every_step_0_transcript_twin_and_status_lines_are_written_and_no_stop_is_printed(bench: Bench) -> None:
    run_line, sim_line = flow_62()
    rid = run_id_of(run_line, "RUN")
    full_run(bench, rid)
    bench.set("thing.json", '{"thingId": "org.c2dta:uuid-0001"}')
    c63 = _host_commands("### 6.3")
    body = [run_line, sim_line, 'echo "RC62=$?"', c63[0], 'echo "RC63=$?"', *c63[1:], 'echo "RCTWIN=$?"',
            _one(_host_commands("### 6.4"), "if [ -s $P/$RUN.metrics.after.json ]"), 'echo "RC64=$?"']
    r = bench.run(bench.with_helpers("\n".join(body)))
    assert (r.value("RC62"), r.value("RC63"), r.value("RCTWIN"), r.value("RC64")) == ("0", "0", "0", "0"), r.out
    assert r.starting(f"FLOW STATUS {rid}: simulator exit=0 transcript (tee) exit=0 mark exit=0"), r.out
    assert r.starting(f"FLOW STATUS {rid}: check exit=0 delta exit=0 unaccounted.txt present=no"), r.out
    assert not r.starting("STOP"), r.out
    assert (bench.p / f"{rid}.stderr.txt").stat().st_size > 0
    assert json.loads((bench.p / f"{rid}.twin.uuid-0001.json").read_text(encoding="utf-8"))["thingId"] == "org.c2dta:uuid-0001"


def test_flow_6_2_tee_reports_failure_with_simulator_exit_0_prints_stop_and_the_marker_is_still_read(bench: Bench) -> None:
    run_line, sim_line = flow_62()
    rid = run_id_of(run_line, "RUN")
    full_run(bench, rid)
    bench.install("tee", STUB_TEE_FAILS)
    r = bench.run(bench.with_helpers("\n".join((run_line, sim_line, 'echo "RC62=$?"'))))
    assert r.value("RC62") != "0", r.out
    assert r.starting(f"FLOW STATUS {rid}: simulator exit=0 transcript (tee) exit=1 mark exit=0"), r.out
    assert r.starting("STOP: 6.2: simulator, transcript or marker failed"), r.out
    assert "itest_reconcile mark" in bench.calls()


def test_flow_6_2_transcript_target_cannot_be_created_simulator_is_never_started(bench: Bench) -> None:
    run_line, sim_line = flow_62()
    rid = run_id_of(run_line, "RUN")
    full_run(bench, rid)
    (bench.p / f"{rid}.stderr.txt").mkdir(parents=True)
    r = bench.run(bench.with_helpers("\n".join((run_line, sim_line, 'echo "RC62=$?"'))))
    assert r.starting("STOP: precondition failed, or ") and "the simulator was NOT started" in r.out, r.out
    assert bench.simulator_calls() == 0
    assert not r.starting("FLOW STATUS"), r.out


def test_flow_6_2_precondition_fails_simulator_is_never_started(bench: Bench) -> None:
    run_line, sim_line = flow_62()
    full_run(bench, run_id_of(run_line, "RUN"))
    bench.set("ready_code", 503)
    r = bench.run(bench.with_helpers("\n".join((run_line, sim_line, 'echo "RC62=$?"'))))
    assert r.starting("STOP: precondition failed, or "), r.out
    assert bench.simulator_calls() == 0


def test_flow_6_3_b_without_logged_outcome_after_state_is_not_captured_and_6_4_refuses_to_run(bench: Bench) -> None:
    run_line, sim_line = flow_62()
    rid = run_id_of(run_line, "RUN")
    full_run(bench, rid, logged=("msg-A",))
    body = [run_line, sim_line, _host_commands("### 6.3")[0], 'echo "RC63=$?"',
            _one(_host_commands("### 6.4"), "if [ -s $P/$RUN.metrics.after.json ]")]
    r = bench.run(bench.with_helpers("\n".join(body)))
    assert r.value("RC63") != "0", r.out
    assert r.starting("  NO LOGGED OUTCOME: msg-B "), r.out
    assert r.starting("STOP: 6.3: the 'after' state was NOT captured"), r.out
    assert r.starting("STOP: 6.3 did not complete") and "check and delta were NOT run" in r.out, r.out
    assert "itest_reconcile check" not in bench.calls()


def twin_lines() -> list[str]:
    c63 = _host_commands("### 6.3")
    return [_one(c63, "UUID="), _one(c63, "twin $RUN $UUID")]


def test_flow_6_3_twin_get_fails_prints_stop_and_leaves_no_file(bench: Bench) -> None:
    run_line, _ = flow_62()
    rid = run_id_of(run_line, "RUN")
    prepare_accounted(bench, rid, sent("msg-A"), None, bench.metrics())
    r = bench.run(bench.with_helpers("\n".join((run_line, *twin_lines(), 'echo "RCTWIN=$?"'))))
    assert r.value("RCTWIN") != "0", r.out
    assert r.starting("STOP: 6.3: the twin of 'uuid-0001' was NOT saved"), r.out
    assert not list(bench.p.glob(f"{rid}.twin.*"))


def test_flow_6_3_twin_file_cannot_be_written_prints_stop_although_the_get_succeeds(bench: Bench) -> None:
    run_line, _ = flow_62()
    rid = run_id_of(run_line, "RUN")
    prepare_accounted(bench, rid, sent("msg-A"), None, bench.metrics())
    bench.set("thing.json", '{"thingId": "org.c2dta:uuid-0001"}')
    (bench.p / f"{rid}.twin.uuid-0001.json.tmp").mkdir()
    r = bench.run(bench.with_helpers("\n".join((run_line, *twin_lines(), 'echo "RCTWIN=$?"'))))
    assert r.value("RCTWIN") != "0", r.out
    assert r.starting("STOP: 6.3: the twin of 'uuid-0001' was NOT saved"), r.out
    assert not (bench.p / f"{rid}.twin.uuid-0001.json").exists()


def t9_lines(sub: str) -> tuple[str, str]:
    """Test 9 (b) or (c): the line that takes the guest epoch and runs the simulator, and the line that reads the
    broker log bounded to that sub-check."""
    cmds = _host_commands("### Test 9")
    rid = {"b": "itest-auth-wrongpw", "c": "itest-notls"}[sub]
    run = [c for c in cmds if f"T0_9{sub.upper()}=$(guest_epoch 3);" in c and "python -m egw_simulator" in c]
    if len(run) != 1:
        pytest.fail(f"expected exactly one runbook command of test 9({sub}) that reads the epoch and runs the simulator, found {len(run)}")
    return run[0], _one(cmds, f"sut_log broker {rid} ")


def call_t9(bench: Bench, sub: str) -> Result:
    run, read = t9_lines(sub)
    return bench.run(bench.with_helpers("\n".join((run, read, 'echo "RC9=$?"'))))


def test_test_9_whole_history_tail_of_the_broker_log_is_no_longer_read() -> None:
    """(b) and (c) were judged on 'docker compose logs --tail 20 mosquitto', whatever session those lines were of."""
    text = "\n".join(_host_commands("### Test 9"))
    assert "--tail 20" not in text and "itest-auth.broker.txt" not in text


@pytest.mark.parametrize("sub, rid", [("b", "itest-auth-wrongpw"), ("c", "itest-notls")])
def test_test_9_each_sub_check_reads_the_broker_log_bounded_from_its_own_guest_epoch(bench: Bench, sub: str, rid: str) -> None:
    bench.set("guest_epoch", 1790000456)
    bench.set("broker.guest", "2026-09-29T10:00:01.000000000Z 1790000457: Client egw-sim disconnected, not authorised.")
    r = call_t9(bench, sub)
    assert r.value("RC9") == "0", r.out
    assert not r.starting("STOP"), r.out
    assert bench.simulator_calls() == 1 and r.value("exit") == "0", r.out
    log = bench.p / f"{rid}.sut" / "broker.log"
    # 3 s back: the guest clock's step band (proof_fetch_sut_log.sh CLOCK_STEP_BAND_S)
    assert bench.capture_calls() == [f"fetch [broker] [{log}] [1790000453]"]
    assert "not authorised" in log.read_text(encoding="utf-8") and "not authorised" in r.out
    assert "written to" in (bench.p / f"{rid}.sut" / "broker.fetch.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", ["read fails", "read answers nothing", "guest clock not read"])
def test_test_9_a_broker_log_not_read_is_a_stop_and_never_evidence(bench: Bench, case: str) -> None:
    if case == "read fails":
        bench.set("fetch_broker_rc", 1)
    elif case == "guest clock not read":
        bench.set("guest_clock_fails")
    r = call_t9(bench, "b")
    assert r.value("RC9") != "0", r.out
    assert r.starting("STOP: test 9(b): the broker log bounded to (b) was NOT read"), r.out
    assert not (bench.p / "itest-auth-wrongpw.sut" / "broker.log").exists()
    if case == "guest clock not read":
        assert r.starting("STOP: guest_epoch: the guest clock was NOT read"), r.out
        assert bench.capture_calls() == [], "a read bounded by an epoch that was not read"


@pytest.mark.parametrize("sub", ["b", "c"])
@pytest.mark.parametrize("failure", ["ssh refused", "not whole seconds"])
def test_test_9_b_and_c_run_no_probe_and_print_no_exit_when_their_lower_bound_was_not_read(bench: Bench, sub: str,
                                                                                           failure: str) -> None:
    """Review of PR #51, P2: with ';' a guest clock that was not read still ran the simulator (an authentication
    attempt that changes the broker log) and printed its 'exit=', which for (b) and (c) is the expected refusal status:
    an unbounded probe could read as their evidence."""
    if failure == "ssh refused":
        bench.set("guest_clock_fails")
    else:
        bench.set("guest_epoch", "Tue Sep 29 10:00:00 UTC 2026")
    run, _ = t9_lines(sub)
    r = bench.run(bench.with_helpers(run + '\necho "RUN=$?"'))
    assert bench.simulator_calls() == 0, "the probe ran without its lower bound:\n" + r.out
    assert not r.starting("exit="), r.out
    assert r.starting(f"STOP: test 9({sub}): the lower bound of ({sub})'s evidence was NOT read - the probe was NOT run"), r.out
    assert r.value("RUN") == "1", r.out


def test_guest_epoch_takes_its_margin_back_and_refuses_one_that_is_not_whole_seconds(bench: Bench) -> None:
    bench.set("guest_epoch", 1790000456)
    r = bench.run(bench.with_helpers('T=$(guest_epoch 3); echo "RC=$?"; echo "T=$T"\n'
                                     'U=$(guest_epoch); echo "RCU=$?"; echo "U=$U"\n'
                                     'V=$(guest_epoch 3s); echo "RCV=$?"; echo "V=$V"'))
    assert (r.value("RC"), r.value("T")) == ("0", "1790000453"), r.out
    assert (r.value("RCU"), r.value("U")) == ("0", "1790000456"), r.out
    assert r.value("RCV") != "0" and r.value("V") == "", r.out
    assert r.starting("STOP: guest_epoch: usage: guest_epoch [<seconds back>]"), r.out
    assert sum("[date +%s]" in ln for ln in bench.ssh_log()) == 2, "a margin that is not a number reads no clock"


def test_sut_log_is_write_once_per_name_and_reads_nothing_the_second_time(bench: Bench) -> None:
    bench.set("broker.guest", "2026-09-29T10:00:01.000000000Z 1790000457: a line")
    run, read = t9_lines("b")
    r = bench.run(bench.with_helpers("\n".join((run, read, read, 'echo "RC9=$?"'))))
    assert r.value("RC9") != "0", r.out
    assert r.starting("STOP: sut_log broker itest-auth-wrongpw: "), r.out
    assert len(bench.capture_calls()) == 1


# --------------------------------------------------------------------------
# Tests 3 and 5 - the controller and broker logs bounded to the test
# --------------------------------------------------------------------------
def rejected_line(stamp: str, error: str) -> str:
    return f"{stamp} " + json.dumps({"ts": stamp, "level": "INFO", "logger": "egw_controller.service",
                                     "message": "telemetry event processed",
                                     "context": {"outcome": "rejected", "device_uuid": "uuid-0001", "seq": 3,
                                                 "attempts": 0, "error": error}})


def call_test3(bench: Bench, rid: str = "itest-invalid-01") -> Result:
    cmds = _host_commands("### Test 3")
    full_run(bench, rid)
    first, read = _one(cmds, "R=itest-invalid-01"), _one(cmds, '[ "$RT" = 0 ] && sut_log controller')
    return bench.run(bench.with_helpers("\n".join((first, 'echo "RT=$RT"', read, 'echo "RC3=$?"'))))


def test_test_3_counts_the_rejections_of_its_own_bounded_controller_log(bench: Bench) -> None:
    bench.set("guest_epoch", 1790000789)
    bench.set("controller.guest", "\n".join((rejected_line("2026-09-29T10:00:01.000Z", "schema: 'bpm' is required"),
                                             "2026-09-29T10:00:02.000Z not json")))
    r = call_test3(bench)
    assert r.value("RT") == "0" and r.value("RC3") == "0", r.out
    log = bench.p / "itest-invalid-01.sut" / "controller.log"
    assert bench.capture_calls() == [f"fetch [controller] [{log}] [1790000789]"]
    assert any("lines=2 rejected=1 " in ln and "'bpm' is required" in ln for ln in r.lines), r.out


@pytest.mark.parametrize("case", ["read fails", "read answers nothing"])
def test_test_3_a_controller_log_not_read_is_a_stop_and_shows_no_rejection(bench: Bench, case: str) -> None:
    if case == "read fails":
        bench.set("fetch_controller_rc", 1)
    r = call_test3(bench)
    assert r.value("RC3") != "0", r.out
    assert r.starting("STOP: test 3: the controller log bounded to this test was NOT read"), r.out
    assert not r.starting("controller log of this test"), r.out


def test_test_3_run_test_not_complete_reads_no_log(bench: Bench) -> None:
    bench.set("ready_code", 503)
    r = call_test3(bench)
    assert r.value("RT") != "0" and r.value("RC3") != "0", r.out
    assert bench.capture_calls() == []


def call_test5(bench: Bench, rid: str = "itest-dropout-01") -> Result:
    cmds = _host_commands("### Test 5")
    full_run(bench, rid)
    first, read = _one(cmds, "R=itest-dropout-01"), _one(cmds, 'if [ "$RT" != 0 ]; then stop "test 5: broker log')
    return bench.run(bench.with_helpers("\n".join((first, 'echo "RT=$RT"', read, 'echo "RC5=$?"'))))


def test_test_5_greps_its_client_in_the_broker_log_bounded_to_the_test(bench: Bench) -> None:
    bench.set("guest_epoch", 1790000999)
    bench.set("broker.guest", "\n".join((
        "mosquitto-1  | 2026-09-29T10:00:01.0Z 1: New client connected from 172.18.0.7:52130 as egw-simulator-itest-dropout-01",
        "mosquitto-1  | 2026-09-29T10:00:02.0Z 2: New client connected from 172.18.0.9:40000 as egw-controller",
        "mosquitto-1  | 2026-09-29T10:00:03.0Z 3: Client egw-simulator-itest-dropout-01 closed its connection.")))
    r = call_test5(bench)
    assert r.value("RC5") == "0", r.out
    log = bench.p / "itest-dropout-01.sut" / "broker.log"
    assert bench.capture_calls() == [f"fetch [broker] [{log}] [1790000999]"]
    excerpt = (bench.p / "itest-dropout-01.broker.txt").read_text(encoding="utf-8").splitlines()
    assert len(excerpt) == 2 and all("egw-simulator-itest-dropout-01" in ln for ln in excerpt)


@pytest.mark.parametrize("case, says", [
    ("read fails", "STOP: test 5: the broker log bounded to this test was NOT read"),
    ("no line of the client", "STOP: test 5: the broker log bounded to this test holds no line of the client"),
])
def test_test_5_a_log_not_read_or_without_the_client_is_a_stop(bench: Bench, case: str, says: str) -> None:
    if case == "read fails":
        bench.set("fetch_broker_rc", 1)
    else:
        bench.set("broker.guest", "mosquitto-1  | 2026-09-29T10:00:02.0Z 2: New client connected as egw-controller")
    r = call_test5(bench)
    assert r.value("RC5") != "0", r.out
    assert r.starting(says), r.out


# --------------------------------------------------------------------------
# defect 2 - test 7: interruption AND recovery must both be shown
# --------------------------------------------------------------------------
def _t7_body(prefix: str = "") -> tuple[str, str, str]:
    """All host$ lines of the test 7 block in their order; returns (body, run id, service)."""
    cmds = _host_commands("### Test 7")
    first = _one(cmds, "R=")
    rid = run_id_of(first, "R")
    svc = re.search(r"SVC=([A-Za-z0-9_-]+)", first)
    assert svc, first
    test_line = _one(cmds, "T7=stop; if pre $R")
    assert cmds.index(test_line) == len(cmds) - 2, "the evaluation line is expected right after the test line"
    body = [prefix, *cmds[:-1], 'echo "T7_VALUE=$T7"', cmds[-1].split("\n")[0], 'echo "EVAL_RC=$?"']
    return "\n".join(body), rid, svc.group(1)


def call_test7(bench: Bench, stub_pgrep_rc: int | None = 0, prefix: str = "", **env: str) -> tuple[Result, str, str]:
    body, rid, svc = _t7_body(prefix)
    full_run(bench, rid)
    bench.set("svc_state", "running")
    if stub_pgrep_rc is not None:
        bench.install("pgrep", STUB_PGREP)
        bench.set("pgrep_rc", stub_pgrep_rc)
    return bench.run(bench.with_helpers(body), **env), rid, svc


def svc_commands(bench: Bench, verb: str, svc: str) -> list[str]:
    return [ln for ln in bench.ssh_log() if ln.endswith(f" {verb} {svc}]")]


def final_state(bench: Bench) -> str:
    return (bench.state / "svc_state").read_text(encoding="utf-8").strip()


def assert_test7_not_accepted(r: Result) -> None:
    assert r.value("T7_VALUE") != "0" and r.value("T7_VALUE").startswith("failed:"), r.out
    assert r.starting("STOP: test 7: NOT accepted"), r.out
    assert r.value("EVAL_RC") != "0", r.out
    assert r.starting("STOP: test 7: not evaluated"), r.out
    assert not r.starting("Counter("), r.out


def test_test_7_stop_and_start_succeed_interruption_and_recovery_both_shown_status_is_0_and_the_run_is_evaluated(bench: Bench) -> None:
    r, rid, svc = call_test7(bench)
    assert r.value("T7_VALUE") == "0", r.out
    assert r.starting(f"INTERRUPTION SHOWN: {svc} went from 'running' to 'exited'"), r.out
    assert r.starting(f"RECOVERY SHOWN: {svc} is 'running' after start"), r.out
    assert r.starting("stop exit=0 state_before=running state_after_stop=exited"), r.out
    assert r.starting("start exit=0 state_after_start=running state_before_start=exited"), r.out
    assert not r.starting("STOP"), r.out
    assert r.value("EVAL_RC") == "0" and r.starting("Counter("), r.out
    assert len(svc_commands(bench, "stop", svc)) == 1 and len(svc_commands(bench, "start", svc)) == 1
    assert final_state(bench) == "running"
    assert (bench.p / f"{rid}.ready.txt").stat().st_size > 0


def test_test_7_stop_fails_and_start_succeeds_is_not_accepted_and_the_service_is_started_again(bench: Bench) -> None:
    bench.set("ssh_stop_rc", 1)
    r, _, svc = call_test7(bench)
    assert_test7_not_accepted(r)
    assert r.starting("stop exit=1 state_before=running state_after_stop=running"), r.out
    assert r.starting(f"STOP: the interruption of {svc} is NOT shown (stop exit=1"), r.out
    assert not r.starting("INTERRUPTION SHOWN"), r.out
    assert len(svc_commands(bench, "start", svc)) == 1 and final_state(bench) == "running"


def test_test_7_stop_fails_the_label_recovery_shown_is_not_printed_because_no_recovery_was_observed(bench: Bench) -> None:
    # defect C-1 (corrected in the runbook on 2026-09-18): the service never left 'running', so no recovery was observed
    bench.set("ssh_stop_rc", 1)
    r, _, svc = call_test7(bench)
    assert r.value("T7_VALUE").startswith("failed:"), r.out
    assert r.starting(f"STOP: the interruption of {svc} is NOT shown"), r.out
    assert not r.starting("RECOVERY SHOWN"), r.out
    assert r.starting("start exit=0 state_after_start=running state_before_start=running"), r.out
    assert r.starting(f"NO RECOVERY TO SHOW: {svc} is 'running' after start, but it was 'running' before the start"), r.out


def test_test_7_stop_succeeds_and_start_fails_is_not_accepted_and_the_operator_is_told_to_start_the_service(bench: Bench) -> None:
    bench.set("ssh_start_rc", 1)
    r, _, svc = call_test7(bench)
    assert_test7_not_accepted(r)
    assert r.starting("INTERRUPTION SHOWN"), r.out
    assert r.starting("start exit=1 state_after_start=exited"), r.out
    assert any("start it by hand before anything else" in ln for ln in r.starting(f"STOP: the recovery of {svc} is NOT shown (start exit=1")), r.out
    assert not r.starting("RECOVERY SHOWN"), r.out
    assert len(svc_commands(bench, "start", svc)) == 1


def test_test_7_stop_and_start_both_fail_is_not_accepted_and_both_exit_codes_are_printed(bench: Bench) -> None:
    bench.set("ssh_stop_rc", 1)
    bench.set("ssh_start_rc", 1)
    r, _, svc = call_test7(bench)
    assert_test7_not_accepted(r)
    assert r.starting("stop exit=1 ") and r.starting("start exit=1 "), r.out
    assert r.starting(f"STOP: the interruption of {svc} is NOT shown") and r.starting(f"STOP: the recovery of {svc} is NOT shown"), r.out
    assert len(svc_commands(bench, "start", svc)) == 1


def test_test_7_stop_exits_0_but_the_service_state_stays_running_is_not_accepted(bench: Bench) -> None:
    bench.set("stop_has_no_effect")
    r, _, svc = call_test7(bench)
    assert_test7_not_accepted(r)
    assert r.starting("stop exit=0 state_before=running state_after_stop=running"), r.out
    assert r.starting(f"STOP: the interruption of {svc} is NOT shown"), r.out


def test_test_7_service_state_unreadable_is_not_accepted_although_stop_and_start_exit_0(bench: Bench) -> None:
    bench.set("svc_state_unreadable")
    r, _, svc = call_test7(bench)
    assert_test7_not_accepted(r)
    assert r.starting("stop exit=0 state_before=unknown state_after_stop=unknown"), r.out
    assert not r.starting("INTERRUPTION SHOWN") and not r.starting("RECOVERY SHOWN"), r.out
    assert len(svc_commands(bench, "start", svc)) == 1


def test_test_7_wait_status_non_zero_with_both_shown_lines_present_is_not_accepted(bench: Bench) -> None:
    # isolates FW: the fault job prints both SHOWN lines and no STOP, only the status that 'wait' hands back is 3
    r, _, _ = call_test7(bench, prefix='wait() { builtin wait "$@"; return 3; }')
    assert r.starting("INTERRUPTION SHOWN") and r.starting("RECOVERY SHOWN"), r.out
    assert_test7_not_accepted(r)
    assert "fault_job=3" in r.value("T7_VALUE"), r.out


def test_test_7_fault_job_killed_after_the_stop_gives_wait_137_is_not_accepted_and_names_the_service_check(bench: Bench) -> None:
    bench.set("kill_fault_job_on_stop")
    r, _, svc = call_test7(bench)
    assert_test7_not_accepted(r)
    assert "fault_job=137" in r.value("T7_VALUE"), r.out
    assert any(f"check that {svc} is running" in ln for ln in r.starting("STOP: test 7: NOT accepted")), r.out
    assert svc_commands(bench, "start", svc) == []                      # a killed job cannot recover: the runbook says so


def test_test_7_fault_job_receives_term_during_the_outage_recovery_is_attempted_and_the_test_is_not_accepted(bench: Bench) -> None:
    bench.set("term_fault_job_on_stop")
    r, _, svc = call_test7(bench)
    assert_test7_not_accepted(r)
    assert r.starting("STOP: the fault job was interrupted - the recovery is attempted now"), r.out
    assert len(svc_commands(bench, "start", svc)) == 1 and final_state(bench) == "running"


def test_test_7_no_simulator_at_injection_time_nothing_is_stopped_the_service_is_started_and_the_status_is_never_0(bench: Bench) -> None:
    r, _, svc = call_test7(bench, stub_pgrep_rc=1)
    assert_test7_not_accepted(r)
    assert r.starting(f"STOP: no simulator process for") and "the fault was NOT injected" in r.out, r.out
    assert svc_commands(bench, "stop", svc) == []
    assert not r.starting("RECOVERY SHOWN") and r.starting("NO RECOVERY TO SHOW"), r.out
    assert len(svc_commands(bench, "start", svc)) == 1 and final_state(bench) == "running"


def test_test_7_simulator_fails_with_both_shown_lines_present_is_not_accepted(bench: Bench) -> None:
    bench.set("sim_rc", 2)
    r, _, _ = call_test7(bench)
    assert r.starting("INTERRUPTION SHOWN") and r.starting("RECOVERY SHOWN"), r.out
    assert_test7_not_accepted(r)
    assert "sim_post=1" in r.value("T7_VALUE"), r.out


def test_test_7_precondition_fails_no_fault_is_injected_nothing_is_published_and_the_run_is_not_evaluated(bench: Bench) -> None:
    bench.set("ready_code", 503)
    r, _, svc = call_test7(bench)
    assert r.value("T7_VALUE") == "stop", r.out
    assert r.starting("STOP: test 7: precondition failed - NO fault was injected and nothing was published"), r.out
    assert r.value("EVAL_RC") != "0" and r.starting("STOP: test 7: not evaluated"), r.out
    assert bench.simulator_calls() == 0
    assert svc_commands(bench, "stop", svc) == [] and svc_commands(bench, "start", svc) == []


def test_test_7_starts_the_recorder_after_pre_and_before_the_fault_and_judges_the_services_own_events(bench: Bench) -> None:
    """The MongoDB sub-check: the recorder is ready before the fault job starts; after the recovery its capture is
    fetched with the actions of the fault's own compose stop and start of egw-mongodb-1 - die, stop, start, never the
    kill, whose signal (15) is not the proof's SIGKILL - and a unit still running is stopped."""
    r, rid, svc = call_test7(bench)
    assert r.value("T7_VALUE") == "0", r.out
    log = bench.ssh_log()
    start = log.index(f"capture [start] [{rid}]")
    stop = next(i for i, ln in enumerate(log) if ln.endswith(f" stop {svc}]"))
    fetch = next(i for i, ln in enumerate(log) if ln.startswith("fetch [docker-events]"))
    recover = next(i for i, ln in enumerate(log) if ln.endswith(f" start {svc}]"))
    assert start < stop < recover < fetch, log
    d = bench.p / f"{rid}.sut"
    assert log[fetch] == f"fetch [docker-events] [{d}/docker-events.log] [1790000000] [{rid}] [die,stop,start] [egw-{svc}-1]"
    assert bench.capture_calls()[-1] == f"capture [cleanup] [{rid}]", "the fetch kept its records: nothing kept twice"
    assert (d / "docker-events.log").is_file() and (d / "docker-events.fetch.txt").is_file()


def test_test_7_recorder_not_ready_injects_no_fault_and_publishes_nothing(bench: Bench) -> None:
    bench.set("events_start_rc", 3)
    r, rid, svc = call_test7(bench)
    assert r.value("T7_VALUE") == "stop", r.out
    assert r.starting(f"STOP: events_start {rid}: the Docker events recorder was NOT found ready"), r.out
    assert r.starting("STOP: test 7: precondition failed - NO fault was injected and nothing was published"), r.out
    assert bench.simulator_calls() == 0
    assert svc_commands(bench, "stop", svc) == [] and svc_commands(bench, "start", svc) == []
    assert (bench.state / f"unit-{rid}").read_text(encoding="utf-8").strip() != "active"


def test_test_7_a_capture_not_shown_complete_is_a_stop_and_leaves_the_acceptance_as_it_stands(bench: Bench) -> None:
    """Whether an incomplete capture should block test 7 is a criterion, not decided here (work order C): the
    capture's failure is printed as a STOP, its partial records stay, and T7 is still decided by its SHOWN lines."""
    bench.set("fetch_docker-events_rc", 1)
    r, rid, _ = call_test7(bench)
    assert r.starting(f"STOP: events_stop {rid}: the Docker events capture is NOT shown complete"), r.out
    assert not (bench.p / f"{rid}.sut" / "docker-events.log").exists()
    assert r.value("T7_VALUE") == "0", r.out


def test_the_ditto_repeat_of_test_7_judges_egw_ditto_things_1(bench: Bench) -> None:
    t7 = _host_commands("### Test 7")
    ditto = _host_commands("### Repeat of test 7 for Ditto")
    first = _one(ditto, "R=")
    rid, svc = run_id_of(first, "R"), re.search(r"SVC=([A-Za-z0-9_-]+)", first).group(1)
    assert svc == "ditto-things"
    # the helpers of test 7 (DC, svc_state, fault_recover, fault, readyp), then the repeat's own three lines
    body = [ln for ln in t7[:-2] if not ln.startswith("R=")] + [first, ditto[1], 'echo "T7_VALUE=$T7"']
    full_run(bench, rid)
    bench.set("svc_state", "running")
    bench.install("pgrep", STUB_PGREP)
    bench.set("pgrep_rc", 0)
    r = bench.run(bench.with_helpers("\n".join(body)))
    assert r.value("T7_VALUE") == "0", r.out
    fetch = [ln for ln in bench.capture_calls() if ln.startswith("fetch [docker-events]")]
    assert fetch == [f"fetch [docker-events] [{bench.p / (rid + '.sut')}/docker-events.log] [1790000000] [{rid}] "
                     f"[die,stop,start] [egw-ditto-things-1]"]
    assert ditto[1] == _one(t7, "T7=stop; if pre $R"), "the repeat's test line is test 7's, unchanged"


@pytest.mark.skipif(REAL_PGREP is None, reason="pgrep (procps) is not installed")
def test_test_7_real_pgrep_finds_the_simulator_as_sim_post_starts_it_and_the_fault_is_injected(bench: Bench) -> None:
    bench.set("sim_sleep", 3)                                           # alive at the scaled '+90 s' (0.9 s)
    r, _, svc = call_test7(bench, stub_pgrep_rc=None, EGW_STUB_MS_PER_S="10")
    assert r.value("T7_VALUE") == "0", r.out
    assert r.starting("INTERRUPTION SHOWN") and r.starting("RECOVERY SHOWN"), r.out
    assert len(svc_commands(bench, "stop", svc)) == 1


@pytest.mark.skipif(REAL_PGREP is None, reason="pgrep (procps) is not installed")
def test_test_7_real_pgrep_simulator_already_gone_at_injection_time_nothing_is_stopped_and_the_status_is_never_0(bench: Bench) -> None:
    r, _, svc = call_test7(bench, stub_pgrep_rc=None, EGW_STUB_MS_PER_S="10")   # the stub simulator ends at once
    assert_test7_not_accepted(r)
    assert r.starting("STOP: no simulator process for"), r.out
    assert svc_commands(bench, "stop", svc) == [] and len(svc_commands(bench, "start", svc)) == 1


# --------------------------------------------------------------------------
# defect 4 - tunnels: this project's control socket only
# --------------------------------------------------------------------------
def make_stale_socket(path: Path) -> None:
    cwd = os.getcwd()
    try:
        os.chdir(path.parent)                                           # AF_UNIX paths are limited to about 108 bytes
        s = socket.socket(socket.AF_UNIX)
        s.bind(path.name)
        s.close()
    finally:
        os.chdir(cwd)


def reopen_line() -> str:
    return _one(_host_commands("### Test 8"), "tunnel_down && tunnel_up")


def test_tunnel_open_line_of_5_7_no_master_ports_free_opens_a_master_on_the_project_socket_and_prints_tunnel_up(bench: Bench) -> None:
    r = bench.run("\n".join((tunnel_heredoc(), tunnel_load_line(), 'echo "RC=$?"')))
    assert r.value("RC") == "0", r.out
    assert "TUNNEL UP" in r.lines, r.out
    opened = [ln for ln in bench.ssh_log() if "[-M]" in ln]
    assert len(opened) == 1 and f"[-S] [{bench.sock}]" in opened[0] and "[ExitOnForwardFailure=yes]" in opened[0], bench.ssh_log()
    assert all(f"[-S] [{bench.sock}]" in ln for ln in bench.ssh_log()), bench.ssh_log()


def test_tunnel_open_host_port_busy_and_no_master_prints_stop_opens_nothing_and_kills_nothing(bench: Bench) -> None:
    bench.set("ss_out", "LISTEN 0      128    127.0.0.1:8000       0.0.0.0:*")
    r = bench.run(bench.with_tunnel('tunnel_up\necho "RC=$?"'))
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: host port busy"), r.out
    assert "TUNNEL UP" not in r.out
    assert not [ln for ln in bench.ssh_log() if "[-M]" in ln]


def test_tunnel_open_master_already_answers_is_reported_as_master_answers_and_never_doubled(bench: Bench) -> None:
    (bench.state / "master_alive").write_text(str(bench.sock), encoding="utf-8")
    r = bench.run(bench.with_tunnel('tunnel_up\necho "RC=$?"'))
    assert r.value("RC") == "0", r.out
    assert r.starting("MASTER ANSWERS on "), r.out
    assert "TUNNEL UP" not in r.lines
    assert not [ln for ln in bench.ssh_log() if "[-M]" in ln]


def test_tunnel_open_ssh_exits_non_zero_prints_stop_and_never_tunnel_up(bench: Bench) -> None:
    bench.set("master_open_fails")
    r = bench.run(bench.with_tunnel('tunnel_up\necho "RC=$?"'))
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: ssh exited non-zero - the tunnel was NOT opened"), r.out
    assert "TUNNEL UP" not in r.lines


def test_tunnel_reopen_line_of_test_8_closes_only_the_project_socket_and_an_unrelated_ssh_forwarder_survives(bench: Bench) -> None:
    decoy = subprocess.Popen(["ssh -f -N -L 9999:127.0.0.1:9999 some-other-host", "60"], executable=REAL_SLEEP)
    try:
        if REAL_PGREP:                                                   # the decoy IS what the withdrawn pattern matched
            seen = subprocess.run([REAL_PGREP, "-f", "ssh -f -N"], capture_output=True, text=True).stdout.split()
            assert str(decoy.pid) in seen
        r = bench.run(bench.with_helpers("\n".join(("tunnel_up",'echo "RCUP=$?"', reopen_line().split("\n")[0], 'echo "RC=$?"'))))
        assert r.value("RCUP") == "0" and r.value("RC") == "0", r.out
        assert "TUNNEL CLOSED" in r.lines and r.lines.count("TUNNEL UP") == 2, r.out
        closing = [ln for ln in bench.ssh_log() if "[-O] [exit]" in ln]
        assert closing == [f"ssh [-S] [{bench.sock}] [-O] [exit] [egw-tcg]"], bench.ssh_log()
        assert all(f"[-S] [{bench.sock}]" in ln for ln in bench.ssh_log()), bench.ssh_log()
        assert "PATTERN-KILL" not in bench.calls(), bench.calls()          # neither pkill nor killall was run
        assert decoy.poll() is None, "an ssh forwarder that does not belong to the project was terminated"
    finally:
        decoy.kill()
        decoy.wait()


def test_tunnel_close_exit_request_fails_prints_stop_and_the_reopen_line_opens_nothing(bench: Bench) -> None:
    (bench.state / "master_alive").write_text(str(bench.sock), encoding="utf-8")
    make_stale_socket(bench.sock)
    bench.set("exit_fails")
    r = bench.run(bench.with_helpers("\n".join((reopen_line().split("\n")[0], 'echo "RC=$?"'))))
    assert r.value("RC") != "0", r.out
    assert r.starting("STOP: 'ssh -O exit' failed on "), r.out
    assert r.starting("STOP: test 8: tunnel NOT reopened"), r.out
    assert "TUNNEL CLOSED" not in r.lines and "TUNNEL UP" not in r.lines
    assert not [ln for ln in bench.ssh_log() if "[-M]" in ln]
    assert bench.sock.exists()


def test_tunnel_close_no_socket_file_is_reported_as_nothing_to_close_and_returns_0(bench: Bench) -> None:
    r = bench.run(bench.with_tunnel('tunnel_down\necho "RC=$?"'))
    assert r.value("RC") == "0", r.out
    assert r.starting("tunnel: no control socket at "), r.out
    assert "TUNNEL CLOSED" not in r.lines
    assert bench.ssh_log() == []


def test_tunnel_close_stale_socket_connection_refused_removes_only_that_file(bench: Bench) -> None:
    make_stale_socket(bench.sock)
    r = bench.run(bench.with_tunnel('tunnel_down\necho "RC=$?"'))
    assert r.value("RC") == "0", r.out
    assert any("stale socket file removed" in ln for ln in r.lines), r.out
    assert "TUNNEL CLOSED" not in r.lines
    assert not bench.sock.exists()
    assert not [ln for ln in bench.ssh_log() if "[-O] [exit]" in ln]


def test_tunnel_close_check_cannot_be_evaluated_prints_stop_and_leaves_the_socket_file_alone(bench: Bench) -> None:
    make_stale_socket(bench.sock)
    bench.set("check_error", "/home/x/.ssh/config: line 3: Bad configuration option: bogus")
    r = bench.run(bench.with_tunnel('tunnel_down\necho "RC=$?"'))
    assert r.value("RC") != "0", r.out
    assert any("could not be evaluated" in ln and "left alone" in ln for ln in r.starting("STOP: 'ssh -O check' on ")), r.out
    assert bench.sock.exists()


def test_tunnel_close_path_is_not_a_socket_prints_stop_and_does_not_remove_it(bench: Bench) -> None:
    bench.sock.write_text("not a socket\n", encoding="utf-8")
    r = bench.run(bench.with_tunnel('tunnel_down\necho "RC=$?"'))
    assert r.value("RC") != "0", r.out
    assert any("is not a socket - NOT removed" in ln for ln in r.starting("STOP: ")), r.out
    assert bench.sock.read_text(encoding="utf-8") == "not a socket\n"


def test_tunnel_text_every_ssh_control_command_names_the_project_socket_and_no_command_matches_processes_by_pattern() -> None:
    heredoc = tunnel_heredoc()
    code = [ln for ln in heredoc.splitlines() if not ln.lstrip().startswith("#")]
    control = [ln for ln in code if re.search(r"\bssh\b.*\s-O\s", ln)]
    assert control, "no 'ssh -O' line found in the tunnel file"
    for ln in control:
        for m in re.finditer(r"(?<!')\bssh (?!egw-tcg)([^|;&]*?)-O (check|exit)", ln):
            assert '-S "$TUNNEL_SOCK"' in m.group(1), ln
    assert any('ssh -S "$TUNNEL_SOCK" -O exit egw-tcg' in ln for ln in code)
    assert 'TUNNEL_SOCK=${TUNNEL_SOCK:-$HOME/egw-tcg/tunnel.ctl}' in code
    fenced = _fenced_code()
    for pattern in (r"\bpkill\b", r"\bkillall\b", r"\bpgrep\b[^\n]*\bkill\b", r"\bkill\b[^\n]*\$\(\s*(pgrep|pidof|ps)\b", r"\bfuser\s+-k"):
        assert not re.search(pattern, fenced), f"pattern-based kill in the runbook's commands: {pattern}"
    # every 'kill' in command position (not the word inside a message) addresses one recorded PID
    kills = re.findall(r"(?:^|[;&|{]|\bthen|\bdo)\s*kill\s+([^\s;]+)", fenced, flags=re.M)
    assert kills and all(target == "$READYP" for target in kills), kills
