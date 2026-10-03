"""Positive and negative cases for the shell text of the integrated-gateway runbook.

Text under test: docs/setup/qemu_integrated_gateway.md - the tunnel file of 5.7, the
helper file that 6.1 writes through a quoted heredoc, the evidence-capturing lines of
6.2-6.4 and of test 9, the lines of test 7 (project review of 2026-09-18, four
residual defects) and the six lines of test 8 (the in-process reboot, 2026-10-03).

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
  # the simulator manifest, only for the cases that give one (a real itest_reconcile reads its totals)
  if [ -s "$S/sim_manifest.json" ]; then mkdir -p "$out/$rid" && cp "$S/sim_manifest.json" "$out/$rid/manifest.json"; fi
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
# test 8: once the reboot command was given, the guest answers no command for guest_down_calls calls (255, the guest
# down or booting; default 2), never again after guest_dies_after_calls calls when the case sets it, and never at all
# with guest_never_answers. The tunnel's control-socket operations above do not count.
t8_guest_answers() {
  local n
  [ -e "$S/rebooted_at" ] || return 0
  [ ! -e "$S/guest_never_answers" ] || return 1
  n=$(( $(cat "$S/after_reboot.calls" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$S/after_reboot.calls"
  [ "$n" -gt "$(cat "$S/guest_down_calls" 2>/dev/null || echo 2)" ] || return 1
  [ ! -s "$S/guest_dies_after_calls" ] || [ "$n" -le "$(cat "$S/guest_dies_after_calls")" ]
}
case $cmd in
  */proc/sys/kernel/random/boot_id) # test 8: the kernel boot id - boot_id before the reboot command, boot_id.post after it
    t8_guest_answers || { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255; }
    [ ! -e "$S/boot_id_unreadable" ] || { echo "cat: /proc/sys/kernel/random/boot_id: No such file or directory" >&2; exit 1; }
    if [ -e "$S/rebooted_at" ]; then cat "$S/boot_id.post"; else cat "$S/boot_id"; fi; exit 0;;
  "docker ps -q --no-trunc | sort") # test 8: the running container ids - containers.pre before the reboot; after it, nothing
    # for docker_ps_empty_calls reads (dockerd starting; default 1), then containers.post when the case gives one, else the same set
    t8_guest_answers || { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255; }
    if [ -e "$S/rebooted_at" ]; then
      n=$(( $(cat "$S/docker_ps.calls" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$S/docker_ps.calls"
      [ "$n" -gt "$(cat "$S/docker_ps_empty_calls" 2>/dev/null || echo 1)" ] || exit 0
      if [ -e "$S/containers.post" ]; then cat "$S/containers.post"; else cat "$S/containers.pre"; fi; exit 0
    fi
    cat "$S/containers.pre"; exit 0;;
  *"sudo systemctl reboot"*) # test 8, line a: the reboot command; the connection drops with it (255); the controller that
    # comes back is a new process when the case gives metrics.post.json
    echo "stub: -1 previous boot"; echo "stub:  0 this boot"; echo "itest-ev-01"
    date -u +%FT%TZ > "$S/rebooted_at"
    [ ! -s "$S/metrics.post.json" ] || cp "$S/metrics.post.json" "$S/metrics.json"
    exit 255;;
  *"findmnt -no SOURCE /var/lib/docker") # test 8, line c: the read-only observations after the unaided return
    t8_guest_answers || { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255; }
    echo "running"; echo "stub: -1 previous boot"; echo "egw-controller-1 Up 2 minutes (healthy)"; echo "/dev/vdb"
    exit "$(cat "$S/observations_rc" 2>/dev/null || echo 0)";;
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
  "[ ! -e /opt/egw/deployment/data/events/"*" ]") # test 3's first line: does the guest hold an event log of the run id?
    [ ! -e "$S/guest_check_fails" ] || { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255; }
    rid=${cmd#"[ ! -e /opt/egw/deployment/data/events/"}; rid=${rid%" ]"}
    [ ! -e "$S/guest_events/$rid" ]; exit;;
  "cat /opt/egw/deployment/data/events/"*"/events.jsonl") # test 3's keep line: the guest's event log as it is now
    [ ! -e "$S/guest_log_read_fails" ] || { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255; }
    cat "$S/remote_events.jsonl"; exit;;
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
# stops it and, given a keep directory, keeps a partial capture there, write-once - or, with events_cleanup_rc set,
# cannot show the unit stopped (the guest not reached): a STOP, that status, the unit's state left as it was
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
    rc=$(cat "$S/events_cleanup_rc" 2>/dev/null || echo 0)
    [ "$rc" = 0 ] || { echo "STOP: events_capture: the recorder unit egw-events-$2 was not shown stopped - it may still run (stub, exit $rc)" >&2; exit "$rc"; }
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
# log holds for the window) or fails as the case sets it (fetch_<kind>_rc), writing nothing - or, with
# fetch_<kind>_nofile, ends 0 and writes nothing; the docker-events fetch stops the stub unit and keeps its stop record
# whatever its ending
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
[ ! -e "$S/fetch_${kind}_nofile" ] || { echo "proof_fetch_sut_log: $kind: (stub) exit 0, nothing written"; exit 0; }
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
    plan.write_text(json.dumps({"runs": [{"run_id": "controller_restart-r03", "seed": 7}]}), encoding="utf-8")
    (bench.state / "identity_capture").write_text(capture_text(), encoding="utf-8")
    body = [_one(cmds, "RID="), _one(cmds, "SEED="), _one(cmds, "RESTART="), _one(cmds, "RAW6="), _one(cmds, "T6=stop; if")]
    r = bench.run(bench.with_helpers("\n".join(body + ['echo "T6=$T6"'])))
    argv = harness_argv(bench)
    opts = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    dest = "/raw/controller_restart-r03/logs/sut/docker-events.log"
    events = sut_fetch_argv(opts, "docker_events", "controller_restart-r03", dest)
    assert events[2:] == ["docker-events", dest, "1790000000", "controller_restart-r03", "die,start"], events
    assert "kill" not in events[-1]
    assert opts["--restart-cmd"].endswith("restart controller'") and opts["--restart-at-s"] == "300"
    assert bench.capture_calls()[0] == "capture [start] [controller_restart-r03]"
    # The finite proof's restart-evidence hooks of the checkout, rendered and split as the harness runs them (review
    # of PR #51, B1): the twin snapshots with the plan's seed, the drain, the post-drain copy of this run's events.
    session = bench.clone / "tools" / "session"
    run_dir = "/raw/controller_restart-r03"

    def hook(flag: str, dest: str) -> list[str]:
        return shlex.split(run_mod.format_collector_template(opts[flag], "controller_restart-r03", duration_s=600,
                                                             dest=dest, expect_services=SIX_SERVICES.split(",")))

    assert hook("--twin-snapshot-cmd", f"{run_dir}/twins.before.json") == \
        ["bash", str(session / "proof_hook_twins.sh"), "controller_restart-r03", f"{run_dir}/twins.before.json", "7"]
    assert hook("--drain-cmd", f"{run_dir}/logs/sut/drain.txt") == \
        ["bash", str(session / "proof_hook_drained.sh"), "controller_restart-r03"]
    assert hook("--post-drain-fetch-cmd", f"{run_dir}/events.post-drain.jsonl") == \
        ["scp", "-q", "egw-tcg:/opt/egw/deployment/data/events/controller_restart-r03/events.jsonl",
         f"{run_dir}/events.post-drain.jsonl"]
    # Decision 1a (adopted 2026-09-30): the StartedAt read the harness runs after its docker-events fetch and before
    # it ingests the resources, through the checkout's script, into the run's logs/sut/.
    assert hook("--fetch-started-at-cmd", f"{run_dir}/logs/sut/controller-started-at.txt") == \
        ["bash", str(session / "fetch_started_at.sh"), f"{run_dir}/logs/sut/controller-started-at.txt"]
    # After the harness, one read-only line on the manifest's resources_proved_down (the stub harness wrote none).
    assert r.starting("test 6: resources_proved_down: "), r.out
    # The stub harness seals nothing, so the line stops: its run directory was not sealed.
    assert r.starting("STOP: test 6: the harness run was not sealed"), r.out
    assert r.value("T6") == "stop", r.out


def test_test_6_line_reads_no_manifest_of_a_run_directory_harness_cmd_refused(bench: Bench) -> None:
    """Review of decision 1a (2026-09-30, round 0): harness_cmd answers 2, the harness NOT started, when the run
    directory already exists - another execution's - so that test 6's line never reads another run's directory; its
    resources_proved_down summary must then print nothing of that directory's manifest. (The directory appears after
    the run id's own guard found the entry unused, as another execution in between would leave it: the guard itself
    refuses an existing one first.)"""
    cmds = _host_commands("### Test 6")
    plan = bench.home / "egw-tcg" / "pilot" / "campaign_plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({"runs": [{"run_id": "controller_restart-r03", "seed": 7}]}), encoding="utf-8")
    (bench.state / "identity_capture").write_text(capture_text(), encoding="utf-8")
    other = bench.tmp / "another-execution"
    other.mkdir(parents=True)
    (other / "manifest.json").write_text(json.dumps({"validity": "valid", "resources_proved_down": {
        "applies": True, "why_not": None, "die_utc": "2026-10-01T10:05:00.400000000Z",
        "start_utc": "2026-10-01T10:05:06.300000000Z", "effective_end_utc": "2026-10-01T10:05:06.300000000Z",
        "capped": False, "edge_gap_before_s": 0.0, "edge_gap_after_s": 2.0, "rejected_rows": [],
        "resources_ingested": True}}), encoding="utf-8")
    appears = f'mkdir -p ~/egw-tcg/pilot/results/raw && mv {shlex.quote(str(other))} ~/egw-tcg/pilot/results/raw/$RID'
    body = [_one(cmds, "RID="), appears, _one(cmds, "SEED="), _one(cmds, "RESTART="), _one(cmds, "RAW6="),
            _one(cmds, "T6=stop; if")]
    r = bench.run(bench.with_helpers("\n".join(body + ['echo "T6=$T6"'])))
    assert not (bench.state / "harness_argv").exists(), "the harness was started over another execution's directory"
    assert r.starting("STOP: harness_cmd controller_restart-r03: "), r.out
    summary = r.starting("test 6: resources_proved_down: ")
    assert len(summary) == 1, r.out
    assert "applies=" not in summary[0] and "2026-10-01T10:05" not in summary[0], summary
    assert "harness_cmd answered 2" in summary[0], summary
    assert r.value("T6") == "stop", r.out


@pytest.mark.parametrize("harness_rc", [0, 1])
def test_harness_cmd_whose_cleanup_fails_answers_3_and_names_the_harness_status(bench: Bench, harness_rc: int) -> None:
    """Review of PR #51, B2: the cleanup after the harness cannot show the unit stopped; harness_cmd exited with the
    harness's status, hiding it. It now answers 3, which the harness never answers, and its STOP names both."""
    bench.set("harness_rc", harness_rc)
    bench.set("events_cleanup_rc", 1)
    r = bench.run(bench.with_helpers('harness_cmd smoke_sequence-r01; echo "HC=$?"'))
    assert r.value("HC") == "3", r.out
    stop = r.starting("STOP: harness_cmd smoke_sequence-r01: ")
    assert len(stop) == 1 and f"the harness answered {harness_rc}" in stop[0] and "FAILED" in stop[0], r.out
    assert "egw-events-smoke_sequence-r01 may still run" in stop[0] and "INCOMPLETE" in stop[0], r.out


@pytest.mark.parametrize("fetch_rc, first_cleanup, again_cleanup, first, again", [
    (0, 0, 0, "0", "0"),
    (0, 1, 0, "3", "0"),
    (0, 1, 1, "3", "3"),
    (1, 0, 0, "1", "1"),
], ids=["complete-cleanup_ok-then_ok", "complete-cleanup_failed-then_ok", "complete-cleanup_failed_twice",
        "not_complete"])
def test_events_stop_called_again_answers_by_the_capture_fetched_before_and_the_cleanup_now(
        bench: Bench, fetch_rc: int, first_cleanup: int, again_cleanup: int, first: str, again: str) -> None:
    """Review of PR #51, B2, second round: called again, events_stop fetches nothing and answered 1 - 'the capture
    not shown complete' - whatever the capture fetched before was and whatever the cleanup showed. It now answers by
    the two results kept apart: the capture fetched before (complete when it wrote docker-events.log, which stays as
    it was) and the cleanup now (0 when it showed the unit stopped, 3 when it failed); 1 only without a complete
    capture."""
    rid = "itest-mongo-fault-09"
    bench.set("fetch_docker-events_rc", fetch_rc)
    bench.set("events_cleanup_rc", first_cleanup)
    r1 = bench.run(bench.with_helpers(f'T0=$(events_start {rid}); echo "$T0" > "$HOME/t0"\n'
                                      f'events_stop {rid} "$T0" die,stop,start egw-mongodb-1; echo "EV1=$?"'))
    assert r1.value("EV1") == first, r1.out
    log = bench.p / f"{rid}.sut" / "docker-events.log"
    kept = log.read_bytes() if log.exists() else None
    assert (kept is not None) == (fetch_rc == 0), r1.out
    bench.set("events_cleanup_rc", again_cleanup)
    r2 = bench.run(bench.with_helpers(f'events_stop {rid} "$(cat "$HOME/t0")" die,stop,start egw-mongodb-1\n'
                                      'echo "EV2=$?"'))
    assert r2.value("EV2") == again, r2.out
    assert len([c for c in bench.capture_calls() if c.startswith("fetch [docker-events]")]) == 1, "fetched twice"
    assert bench.capture_calls()[-1].startswith(f"capture [cleanup] [{rid}]"), "the repeat did not run the cleanup"
    said = [ln for ln in r2.lines if ln.startswith((f"STOP: events_stop {rid}: ", f"events_stop {rid}: "))]
    assert len(said) == 1 and "docker-events.fetch.txt exists" in said[0], r2.out
    if kept is None:
        assert said[0].startswith("STOP: ") and "nothing was fetched" in said[0], r2.out
        assert "IS shown complete" not in said[0] and not log.exists(), r2.out
        return
    assert log.read_bytes() == kept, "the complete capture was changed by the repeat"
    assert "nothing was fetched again" in said[0] and "IS shown complete" in said[0], r2.out
    assert "NOT shown complete" not in r2.out, r2.out
    if again == "3":
        assert said[0].startswith("STOP: ") and "INCOMPLETE" in said[0], r2.out
        assert f"egw-events-{rid} may still run" in said[0], r2.out
    else:
        assert not said[0].startswith("STOP") and "showed the unit stopped" in said[0], r2.out


def test_test_6_whose_recorder_is_not_ready_and_whose_cleanup_failed_says_the_unit_may_still_run(bench: Bench) -> None:
    """Review of PR #51, B2, second round (nit): harness_cmd answers 2 whenever the harness was not started, a cleanup
    that failed on the way included (the harness never ran, so there is no status of it to keep apart); test 6's STOP
    for 2 said only that the harness was not started. The status stays 2, and harness_cmd's STOP and test 6's point to
    the failed cleanup."""
    cmds = _host_commands("### Test 6")
    plan = bench.home / "egw-tcg" / "pilot" / "campaign_plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({"runs": [{"run_id": "controller_restart-r03", "seed": 7}]}), encoding="utf-8")
    (bench.state / "identity_capture").write_text(capture_text(), encoding="utf-8")
    bench.set("events_start_rc", 3)
    bench.set("events_cleanup_rc", 1)
    body = [_one(cmds, "RID="), _one(cmds, "SEED="), _one(cmds, "RESTART="), _one(cmds, "RAW6="), _one(cmds, "T6=stop; if")]
    r = bench.run(bench.with_helpers("\n".join(body + ['echo "T6=$T6"'])))
    assert r.value("T6") == "stop", r.out
    assert not (bench.state / "harness_argv").exists(), "the harness was started without a ready recorder"
    start = r.starting("STOP: events_start controller_restart-r03: ")
    assert len(start) == 1 and "egw-events-controller_restart-r03 may still run" in start[0], r.out
    hc = r.starting("STOP: harness_cmd controller_restart-r03: the harness was NOT started")
    assert len(hc) == 1 and "events_start's STOP above" in hc[0], r.out
    t6 = r.starting("STOP: test 6: ")
    assert len(t6) == 1 and "exited 2" in t6[0] and "may then still run" in t6[0], r.out


def test_test_6_takes_controller_restart_r03_the_first_entry_never_used_on_the_guest() -> None:
    """Review of 2026-09-30 (RB-3): test 6 named controller_restart-r01, which the pilot tree already holds (r01 ran on
    2026-09-18 and r02 on 2026-09-19), so harness_cmd refused it and the documented line could only stop."""
    assert run_id_of(_one(_host_commands("### Test 6"), "RID="), "RID") == "controller_restart-r03"


@pytest.mark.parametrize("used", ["raw directory", "start record"])
def test_test_6_entry_already_used_is_refused_and_nothing_starts(bench: Bench, used: str) -> None:
    """Review of 2026-09-30 (RB-3): like test 1's, test 6's entry is refused when it was already used - its raw
    directory in the pilot tree, or its record beside the itest artefacts - before anything starts: no readiness
    check, no drain, no configuration identity, no recorder, no harness; and the delta line after it refuses too."""
    cmds = _host_commands("### Test 6")
    first = _one(cmds, "RID=")
    rid = run_id_of(first, "RID")
    plan = bench.home / "egw-tcg" / "pilot" / "campaign_plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({"runs": [{"run_id": f"controller_restart-r0{i}", "seed": 6 + i} for i in (1, 2, 3)]}),
                    encoding="utf-8")
    (bench.state / "identity_capture").write_text(capture_text(), encoding="utf-8")
    trace = (bench.home / "egw-tcg" / "pilot" / "results" / "raw" / rid if used == "raw directory"
             else bench.p / f"{rid}.sut")
    trace.mkdir(parents=True)
    body = [first, 'echo "F6=$F6"', _one(cmds, "SEED="), _one(cmds, "RESTART="), _one(cmds, "RAW6="),
            _one(cmds, "T6=stop; if"), 'echo "T6=$T6"', _one(cmds, '[ "$T6" = ok ] && $REC delta'), 'echo "RD=$?"']
    r = bench.run(bench.with_helpers("\n".join(body)))
    assert r.value("F6") == "used" and r.value("T6") == "stop" and r.value("RD") != "0", r.out
    refused = r.starting(f"STOP: test 6: {rid} was already used")
    assert len(refused) == 1 and "record the choice" in refused[0], r.out
    assert any("the harness run was NOT started" in ln and "F6='used'" in ln for ln in r.starting("STOP: test 6: ")), r.out
    assert not (bench.state / "harness_argv").exists() and bench.capture_calls() == []
    assert "/ready" not in bench.calls() and "/metrics" not in bench.calls(), bench.calls()
    assert not (bench.p / f"{rid}.config_identity.json").exists()
    assert "itest_reconcile delta" not in bench.calls()
    assert list(trace.iterdir()) == [], "the earlier execution's trace was changed"


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
    command = line.split("     #", 1)[0]  # the command, without its trailing comment
    capture = "config_identity $P/$RID.config_identity.json"
    assert capture in command and command.index(capture) < command.index("harness_cmd $RID")
    assert "--config-identity-from $P/$RID.config_identity.json" in command.split("harness_cmd $RID", 1)[1]
    # Review of PR #51, B1/B2: the harness takes the restart evidence itself, so no harness status is tolerated any
    # more - T6 is ok only on harness_cmd's 0, a cleanup failure (3) is its own state - and the drain has this
    # shell's own window, step and limit.
    assert "without its restart evidence step" not in command
    assert 'if [ "$HR" = 3 ]; then T6=incomplete' in command
    assert 'elif [ "$HR" = 0 ] && [ -s $RAW6/SHA256SUMS ]; then' in command
    assert "DRAIN_QUIET_S=$DRAIN_QUIET_S DRAIN_STEP_S=$DRAIN_STEP_S DRAIN_LIMIT_S=$DRAIN_LIMIT_S " \
           "EVENTS_EXPECTED=die,start harness_cmd $RID" in command


def test_test_6_hands_the_harness_the_started_at_read_and_summarises_the_proved_down_record() -> None:
    """Decision 1a (adopted 2026-09-30): the StartedAt read is one more argument of harness_cmd (the 6.1 heredoc is
    unchanged), and once the harness returns the line prints one read-only summary of resources_proved_down."""
    line = _one(_host_commands("### Test 6"), "T6=stop; if")
    command = line.split("     #", 1)[0]
    after = command.split("harness_cmd $RID", 1)[1]
    assert '--fetch-started-at-cmd "bash \\"$EGW_CLONE/tools/session/fetch_started_at.sh\\" \\"{dest}\\""' in after
    assert after.index("--fetch-started-at-cmd") < after.index("HR=$?")
    summary = after.split("HR=$?;", 1)[1].split('if [ "$HR" = 3 ]', 1)[0]
    assert "resources_proved_down" in summary and "$RAW6/manifest.json" in summary
    assert "HR=" not in summary, "the summary must not change the harness's status"
    helpers = helpers_heredoc()
    assert "fetch-started-at" not in helpers and "fetch_started_at" not in helpers


def test_test_6_note_records_the_prospective_adoption_of_the_proved_down_interval() -> None:
    text = " ".join("\n".join(_section("### Test 6")).split())
    note = text.split("*Note (2026-09-19):*", 1)[1]
    assert "**proposed, not adopted**" in note
    assert "on 2026-09-30 the student adopted the proved-down interval (decision 1a) prospectively" in note
    assert "`fetch_started_at.sh`" in note
    assert "stay invalid under the rules they were run with" in note


def test_test_6_takes_no_drain_post_drain_copy_or_after_snapshot_outside_the_harness() -> None:
    """Review of PR #51, B1: the drain, the post-drain copy and the 'after' snapshot ran after harness_cmd had
    stopped the recorder, outside the run's capture; the harness now takes them, and nothing ingests them later."""
    commands = [c.split("     #", 1)[0] for c in _host_commands("### Test 6")]
    text = "\n".join(commands)
    for gone in ("drained 2>&1 | tee", "events.post-drain.jsonl && [ -s", "--label after", "egw_experiments collect",
                 "--drain-transcript-from", "--twins-before-from", "--post-drain-events-from"):
        assert gone not in text, gone
    assert "$REC snap" not in text


def test_test_6_delta_line_names_the_post_drain_copy() -> None:
    line = _one(_host_commands("### Test 6"), '[ "$T6" = ok ] && $REC delta')
    command = line.split("     #", 1)[0]  # the command, without its trailing comment
    assert "--events $RAW6/events.post-drain.jsonl" in command
    assert "--prefix $P/$RID" in command
    assert "--also" not in command
    # Decision 2 of 2026-09-30: the N1 report's two sources, the run's sealed controller log and the run directory
    # (its restart record, its Docker events capture and its drain); the line's guard and stop are unchanged.
    assert "--controller-log $RAW6/logs/sut/controller.log --restart-evidence $RAW6 ||" in command
    assert command.startswith('[ "$T6" = ok ] && $REC delta ')
    assert command.endswith(''' || stop "test 6: delta NOT run (T6='$T6') or it exited non-zero (4 = MISMATCH)"''')


def test_test_6_names_the_limit_the_harness_puts_on_its_drain_hook() -> None:
    """Review of PR #51, B1, second round: test 6's drain runs as the harness's hook, which run.py ends after
    DRAIN_TIMEOUT_S and records as a drain in error (an invalid run), where the external 'drained' had no such limit.
    The comment that gives the drain's window, step and limit names that one too, with run.py's value."""
    line = _one(_host_commands("### Test 6"), "RAW6=")
    comment = line.split("     #", 1)[1]
    assert f"after {int(run_mod.DRAIN_TIMEOUT_S)} s (run.py DRAIN_TIMEOUT_S)" in comment, comment
    assert "gave-up" in comment and "'error'" in comment, comment


def test_test_6_warm_up_variant_is_deferred_and_no_command_reads_another_runs_post_drain_copy() -> None:
    """Review of 2026-09-25, D3: the example of the warm-up variant named the preceding restart run's post-drain
    copy through $RAW6; it is withdrawn with a statement of what the variant needs. Test 6's commands hold no
    --also, and the main delta line is the only command that names --events."""
    cmds = _host_commands("### Test 6")
    assert [c for c in cmds if "--also" in c.split("     #", 1)[0]] == []  # the command part, not its comment
    with_events = [c for c in cmds if "--events" in c.split("     #", 1)[0]]
    assert with_events == [_one(cmds, '[ "$T6" = ok ] && $REC delta')]
    text = "\n".join(_section("### Test 6"))
    assert "No executable procedure for that variant is given here" in text
    assert "warm-up" in text and "--also" in text  # the option and the reason for it are still explained


def test_helper_table_names_config_identity() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "| `config_identity <out-file>` |" in text


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


# --------------------------------------------------------------------------
# Decisions of 2026-09-30 (prospective): test 3's post-drain copy and its per-identity acceptance check (3), test
# 4's replay judged per identity (4), test 1's harness run on a nominal entry never used (1b), the timed families (3)
# --------------------------------------------------------------------------
T3 = "itest-invalid-01"
#: v-1 and v-2 valid, i-1 intended invalid, as the simulator writes them (one run id, one message_id each)
T3_SENT = [{"run_id": T3, "message_id": m, "device_type": "smartwatch", "device_uuid": "uuid-0001", "seq": i,
            "intended_invalid": m.startswith("i-")} for i, m in enumerate(("v-1", "v-2", "i-1"))]


def t3_guest_log(bench: Bench, v2: str | None = "accepted") -> None:
    """v2=None: v-2 has no outcome line at all in the guest's log."""
    bench.jsonl("sent_events.jsonl", T3_SENT)
    (bench.state / "sim_manifest.json").write_text(json.dumps(
        {"run_id": T3, "completed": True, "totals": {"sent": len(T3_SENT), "intended_invalid": 1}}), encoding="utf-8")
    bench.jsonl("remote_events.jsonl", [event(T3, "v-1", "accepted"), *([event(T3, "v-2", v2)] if v2 else []),
                                        event(T3, "i-1", "rejected")])


def call_test3_acceptance(bench: Bench, real_rec: bool = False) -> Result:
    """Test 3's run, the line that keeps the copy fetched after the drain and the acceptance line, as pasted. With
    real_rec the acceptance line runs this checkout's itest_reconcile on the kept copy (the capture before it keeps
    the stub: the real mark, wait and check would need a controller)."""
    cmds = _host_commands("### Test 3")
    first, keep_line = _one(cmds, "R=itest-invalid-01"), _one(cmds, "C3=stop;")
    check = _one(cmds, '[ "$C3" = ok ] && $REC acceptance')
    real = ('REC="python3 -m egw_experiments.itest_reconcile"',) if real_rec else ()
    body = "\n".join((first, 'echo "RT=$RT"', keep_line, 'echo "C3=$C3"', *real, check, 'echo "RA=$?"'))
    return bench.run(bench.with_helpers(body), PYTHONPATH=str(ROOT / "src"))


def acceptance_calls(bench: Bench) -> list[str]:
    return [ln for ln in bench.calls().splitlines() if "itest_reconcile acceptance" in ln]


def test_test_3_keeps_the_copy_fetched_after_the_drain_and_checks_every_valid_message_on_it(bench: Bench) -> None:
    t3_guest_log(bench)
    r = call_test3_acceptance(bench)
    assert (r.value("RT"), r.value("C3"), r.value("RA")) == ("0", "ok", "0"), r.out
    assert not r.starting("STOP"), r.out
    kept = bench.p / f"{T3}.events.post-drain.jsonl"
    # the file 'finish' fetched after its 'drained' (wait && drained && fetch), kept as it was
    assert kept.read_bytes() == (bench.p / T3 / "events.jsonl").read_bytes()
    assert acceptance_calls(bench) == [
        f"python -m egw_experiments.itest_reconcile acceptance {bench.p}/{T3} --events {kept}"]


@pytest.mark.parametrize("rc", [4, 1], ids=["never-accepted", "not-evaluable"])
def test_test_3_an_acceptance_check_that_does_not_end_0_is_a_stop(bench: Bench, rc: int) -> None:
    t3_guest_log(bench)
    bench.set("rec_acceptance_rc", rc)
    r = call_test3_acceptance(bench)
    assert r.value("C3") == "ok" and r.value("RA") != "0", r.out
    assert r.starting("STOP: test 3: the per-identity acceptance check"), r.out


@pytest.mark.parametrize("v2, ok", [("accepted", True), ("failed", False), ("duplicate", False)])
def test_test_3_acceptance_line_runs_the_real_check_on_the_kept_copy(bench: Bench, v2: str, ok: bool) -> None:
    t3_guest_log(bench, v2)
    r = call_test3_acceptance(bench, real_rec=True)
    assert r.value("RT") == "0" and r.value("C3") == "ok", r.out
    if ok:
        assert r.value("RA") == "0", r.out
        assert any("valid=2 accepted by the end of the drain=2 never accepted=0" in ln for ln in r.lines), r.out
    else:
        assert r.value("RA") != "0", r.out
        assert f"  NEVER ACCEPTED: v-2 (smartwatch seq=1) outcome lines in the copy: {v2} x1" in r.lines, r.out
        assert r.starting("STOP: test 3: the per-identity acceptance check"), r.out


@pytest.mark.parametrize("case", ["precondition fails", "fetch fails"])
def test_test_3_without_a_post_drain_copy_is_not_evaluated(bench: Bench, case: str) -> None:
    """No copy after the drain (the run stopped before its fetch: a drain that gave up does the same): the copy is
    not kept, nothing is judged and test 3 is not passed."""
    t3_guest_log(bench)
    if case == "precondition fails":
        bench.set("ready_code", 503)
    else:
        (bench.state / "remote_events.jsonl").unlink()
    r = call_test3_acceptance(bench)
    assert r.value("RT") != "0" and r.value("C3") == "stop" and r.value("RA") != "0", r.out
    assert r.starting("STOP: test 3: no copy of the events fetched after the drain of this run"), r.out
    assert r.starting("STOP: test 3: the per-identity acceptance check was not run (C3='stop')"), r.out
    assert not (bench.p / f"{T3}.events.post-drain.jsonl").exists()
    assert acceptance_calls(bench) == []


def test_test_3_a_valid_message_without_any_outcome_line_fails_test_3_not_left_unevaluated(bench: Bench) -> None:
    """Decision 3: a valid message with no outcome line in the copy fetched after the drain fails test 3. 'accounted'
    names it and stops 'finish' AFTER its fetch (run_test ends non-zero), so the copy exists: it is kept and judged
    (exit 4: test 3 FAILS), not reported as 'not evaluated'."""
    t3_guest_log(bench, v2=None)
    r = call_test3_acceptance(bench, real_rec=True)
    assert r.value("RT") != "0", r.out
    assert r.starting(f"STOP: accounted {T3}: published records of this run are named above"), r.out
    assert r.value("C3") == "ok" and r.value("RA") != "0", r.out
    kept = bench.p / f"{T3}.events.post-drain.jsonl"
    assert kept.read_bytes() == (bench.p / T3 / "events.jsonl").read_bytes()
    assert "  NEVER ACCEPTED: v-2 (smartwatch seq=1) outcome lines in the copy: none" in r.lines, r.out
    assert r.starting("STOP: test 3: the per-identity acceptance check"), r.out
    assert any("(exit 4: test 3 FAILS)" in ln for ln in r.lines if ln.startswith("STOP: test 3")), r.out
    assert not r.starting("STOP: test 3: no copy"), r.out


def test_test_3_a_used_run_id_never_judges_the_copy_an_earlier_execution_left(bench: Bench) -> None:
    """The run id was already used: 'pre' refuses it and nothing is published, but the earlier execution's fetched
    copy is still there (every message accepted). It is not this run's post-drain copy: not kept, not judged."""
    t3_guest_log(bench)
    old = bench.p / T3
    old.mkdir(parents=True)
    (old / "events.jsonl").write_bytes((bench.state / "remote_events.jsonl").read_bytes())
    r = call_test3_acceptance(bench)
    assert r.value("RT") != "0" and r.value("C3") == "stop" and r.value("RA") != "0", r.out
    assert r.starting("STOP: test 3: no copy of the events fetched after the drain of this run"), r.out
    assert not (bench.p / f"{T3}.events.post-drain.jsonl").exists()
    assert acceptance_calls(bench) == []


def test_test_3_an_existing_post_drain_copy_is_never_overwritten_and_nothing_is_judged(bench: Bench) -> None:
    t3_guest_log(bench)
    bench.p.mkdir(parents=True, exist_ok=True)
    kept = bench.p / f"{T3}.events.post-drain.jsonl"
    kept.write_text("old\n", encoding="utf-8")
    r = call_test3_acceptance(bench)
    assert r.value("RT") == "0" and r.value("C3") == "stop" and r.value("RA") != "0", r.out
    assert r.starting(f"STOP: keep: {kept} exists - NOT overwritten"), r.out
    assert kept.read_text(encoding="utf-8") == "old\n"
    assert acceptance_calls(bench) == []


@pytest.mark.parametrize("case", ["the guest holds a log of the run id", "the guest does not answer"])
def test_test_3_a_run_id_the_guest_already_holds_is_never_judged(bench: Bench, case: str) -> None:
    """The guest's event log of a run id persists and is appended to (test 8: the old data/events/* directories are
    intact), and the host's $P/$R cannot show it. An earlier execution of the same run id (the same seed, so the same
    message_ids) left its accepted lines there and this execution only adds duplicates: the fetched copy would show
    every valid message accepted. The run id is fresh only when neither the host nor the guest holds it, and a guest
    that does not answer leaves it used: not kept, not judged, test 3 not evaluated."""
    t3_guest_log(bench)
    bench.jsonl("remote_events.jsonl", [event(T3, "v-1", "accepted"), event(T3, "v-2", "accepted"),
                                        event(T3, "i-1", "rejected"), event(T3, "v-1", "duplicate"),
                                        event(T3, "v-2", "duplicate"), event(T3, "i-1", "rejected")])
    if case == "the guest holds a log of the run id":
        (bench.state / "guest_events" / T3).mkdir(parents=True)
    else:
        bench.set("guest_check_fails")
    r = call_test3_acceptance(bench)
    assert r.value("C3") == "stop" and r.value("RA") != "0", r.out
    assert r.starting("STOP: test 3: no copy of the events fetched after the drain of this run (F3='used'"), r.out
    assert not (bench.p / f"{T3}.events.post-drain.jsonl").exists()
    assert acceptance_calls(bench) == []
    assert any(f"[[ ! -e /opt/egw/deployment/data/events/{T3} ]]" in ln for ln in bench.ssh_log()), bench.ssh_log()


def test_test_3_a_run_id_neither_the_host_nor_the_guest_holds_is_fresh(bench: Bench) -> None:
    t3_guest_log(bench)
    (bench.state / "guest_events" / "itest-invalid-02").mkdir(parents=True)  # another run id's log on the guest
    r = call_test3_acceptance(bench)
    assert (r.value("RT"), r.value("C3"), r.value("RA")) == ("0", "ok", "0"), r.out


@pytest.mark.parametrize("case", ["the guest holds a log of the run id", "the guest does not answer",
                                  "the host holds the run id"])
def test_test_3_publishes_nothing_on_a_run_id_that_is_not_fresh(bench: Bench, case: str) -> None:
    """Review of 2026-09-30 (34-1): the first line found the run id used on the guest (F3 'used') and still started
    the simulator, publishing a 120 s run that can never be judged into the earlier execution's event log on the
    guest. Section 7, rule 1: a failed precondition publishes nothing. The line now starts nothing unless F3 is
    'fresh': no guest clock read, no 'before' snapshot, no simulator, and one STOP."""
    t3_guest_log(bench)
    if case == "the guest holds a log of the run id":
        (bench.state / "guest_events" / T3).mkdir(parents=True)
    elif case == "the guest does not answer":
        bench.set("guest_check_fails")
    else:
        (bench.p / T3).mkdir(parents=True)
    first = _one(_host_commands("### Test 3"), "R=itest-invalid-01")
    r = bench.run(bench.with_helpers("\n".join((first, 'echo "RT=$RT"', 'echo "F3=$F3"'))))
    assert r.value("F3") == "used" and r.value("RT") != "0", r.out
    assert bench.simulator_calls() == 0, r.out
    assert not (bench.p / f"{T3}.metrics.before.json").exists() and not (bench.p / f"{T3}.stderr.txt").exists()
    assert not any(ln.endswith("[date +%s]") for ln in bench.ssh_log()), bench.ssh_log()
    stop = r.starting("STOP: test 3: ")
    assert len(stop) == 1 and "the simulator was NOT started" in stop[0] and "nothing was published" in stop[0], r.out


#: scp that fails part-way, leaving the bytes it had written (OpenSSH scp and sftp leave a partial destination): here
#: the first line of the guest's log, cut on a line boundary so that it still parses
PARTIAL_SCP = r"""#!/usr/bin/env bash
S=$EGW_STUB_STATE
echo "scp $*" >> "$S/calls.log"
head -n 1 "$S/remote_events.jsonl" > "${@: -1}"
echo "scp: stub: connection lost part-way" >&2
exit 1
"""

#: scp that copies the guest's log whole; the controller then appends one more line to it (after the fetch)
SCP_THEN_APPEND = r"""#!/usr/bin/env bash
S=$EGW_STUB_STATE
echo "scp $*" >> "$S/calls.log"
cp "$S/remote_events.jsonl" "${@: -1}"
cat "$S/appended_after_fetch.jsonl" >> "$S/remote_events.jsonl"
"""


@pytest.mark.parametrize("case", ["the fetch failed part-way", "a line was appended after the fetch",
                                  "the guest does not answer"])
def test_test_3_keeps_only_a_copy_that_is_the_guests_whole_log(bench: Bench, case: str) -> None:
    """Decision 3: test 3 is judged on the copy of the events fetched after the drain; without it, it is not evaluated
    (a STOP), never passed. A fetch that failed part-way leaves a partial file (the missing lines judged 'never
    accepted': a verdict on a copy that was never fetched), and a log that grew after the fetch cannot be told from
    one: the second line keeps the file only when it is the guest's log as a whole, else nothing is judged."""
    t3_guest_log(bench)
    if case == "the fetch failed part-way":
        bench.install("scp", PARTIAL_SCP)
    elif case == "a line was appended after the fetch":
        bench.install("scp", SCP_THEN_APPEND)
        bench.jsonl("appended_after_fetch.jsonl", [event(T3, "v-2", "duplicate")])
    else:
        bench.set("guest_log_read_fails")
    r = call_test3_acceptance(bench, real_rec=True)
    if case == "the fetch failed part-way":
        assert r.starting(f"STOP: fetch {T3}: scp of events.jsonl failed") and r.value("RT") != "0", r.out
    else:
        assert r.value("RT") == "0", r.out
    assert r.value("C3") == "stop" and r.value("RA") != "0", r.out
    assert not any("NEVER ACCEPTED" in ln or ln.startswith("ACCEPTANCE BY THE END") for ln in r.lines), r.out
    assert r.starting("STOP: test 3: no copy of the events fetched after the drain of this run (F3='fresh'"), r.out
    assert not (bench.p / f"{T3}.events.post-drain.jsonl").exists()
    assert any("[cat /opt/egw/deployment/data/events/" + T3 + "/events.jsonl]" in ln for ln in bench.ssh_log()), \
        bench.ssh_log()


def t4_metrics_difference_line() -> str:
    hits = [c for c in _host_commands("### Test 4")
            if "'$P/$R.metrics.after.json'" in c and "'$P/$R.metrics.replay.json'" in c]
    assert len(hits) == 1, hits
    return hits[0]


T4_AFTER = {"started_at": STARTED, "uptime_s": 500.0, "monotonic_ns": 2_000, "queue_depth": 0, "received": 125,
            "accepted": 100, "rejected": 5, "duplicate": 5, "failed": 5, "dropped": 5, "processing_errors": 5,
            "in_progress": 0, "unacked": 0, "mqtt_subscribed": True, "mqtt_connection": 1}
T4_REPLAY = dict(T4_AFTER, uptime_s=560.0, monotonic_ns=62_000, received=128, duplicate=8)
T4_REPLAYS = {
    "one process": T4_REPLAY,
    "started_at differs": dict(T4_REPLAY, started_at="2026-09-18T10:30:00Z", uptime_s=40.0, received=3, accepted=0,
                               rejected=0, duplicate=3, failed=0, dropped=0, processing_errors=0),
    "uptime_s decreased": dict(T4_REPLAY, uptime_s=499.0),
    "accepted decreased": dict(T4_REPLAY, accepted=99, received=127),
    "processing_errors decreased": dict(T4_REPLAY, processing_errors=4, received=127),
    "mqtt_connection decreased": dict(T4_REPLAY, mqtt_connection=0),
}


@pytest.mark.parametrize("case", list(T4_REPLAYS))
def test_test_4_metrics_difference_line_differences_only_two_readings_of_one_process(bench: Bench, case: str) -> None:
    """Decision 4: before any difference of the 'after' and 'replay' /metrics readings, the same-process checks of
    CONTRACTS 5 must hold (the same started_at; uptime_s, the cumulative counters and mqtt_connection non-decreasing).
    The line printed the differences of two processes too, beside 'same controller process: False', and ended 0."""
    rid = "itest-dup-01"
    bench.p.mkdir(parents=True, exist_ok=True)
    (bench.p / f"{rid}.metrics.after.json").write_text(json.dumps(T4_AFTER), encoding="utf-8")
    (bench.p / f"{rid}.metrics.replay.json").write_text(json.dumps(T4_REPLAYS[case]), encoding="utf-8")
    r = bench.run(bench.with_helpers("\n".join((f"R={rid}; REPLAYED=captured", t4_metrics_difference_line(),
                                                'echo "RCD=$?"'))))
    differences = [ln for ln in r.lines if ln.startswith("{'accepted': ")]
    if case == "one process":
        assert differences == ["{'accepted': 0, 'rejected': 0, 'duplicate': 3, 'failed': 0, 'dropped': 0} "
                               "same controller process: True"], r.out
        assert r.value("RCD") == "0" and not r.starting("STOP"), r.out
    else:
        assert differences == [], r.out
        assert r.value("RCD") != "0", r.out
        assert r.starting("STOP: test 4: "), r.out


def t4_check_line() -> str:
    hits = [c for c in _host_commands("### Test 4") if "$REC replay-check" in c]
    assert len(hits) == 1, hits
    return hits[0]


# exit 5 (2026-10-01): the replay's own duplicate line not demonstrated - not passed, its own STOP, not a failure
@pytest.mark.parametrize("replayed, rc, passes", [("stop", 0, False), ("ok", 0, False), ("captured", 4, False),
                                                  ("captured", 1, False), ("captured", 5, False),
                                                  ("captured", 0, True)])
def test_test_4_replay_check_line_runs_only_on_a_captured_replay_and_passes_only_on_0(bench: Bench, replayed: str,
                                                                                     rc: int, passes: bool) -> None:
    bench.set("rec_replay-check_rc", rc)
    r = bench.run(bench.with_helpers("\n".join((f"R=itest-dup-01; REPLAYED={replayed}", t4_check_line(),
                                                'echo "RC4=$?"'))))
    calls = [ln for ln in bench.calls().splitlines() if "itest_reconcile replay-check" in ln]
    if replayed == "captured":
        assert calls == [f"python -m egw_experiments.itest_reconcile replay-check {bench.p}/itest-dup-01 --replay-dir "
                         f"{bench.home}/egw-tcg/itest-replay/itest-dup-01 --events-before "
                         f"{bench.p}/itest-dup-01.events.pre-replay.jsonl"], bench.calls()
    else:
        assert calls == [], bench.calls()
    if passes:
        assert r.value("RC4") == "0" and not r.starting("STOP"), r.out
    elif rc == 5 and replayed == "captured":
        assert r.value("RC4") != "0", r.out
        assert len(r.starting("STOP: test 4: NOT DEMONSTRATED")) == 1, r.out
        assert not r.starting("STOP: test 4: the per-identity replay check"), r.out  # not a failure
    else:
        assert r.value("RC4") != "0", r.out
        assert len(r.starting("STOP: test 4: the per-identity replay check")) == 1, r.out
        assert not r.starting("STOP: test 4: NOT DEMONSTRATED"), r.out


def t1_harness_lines() -> tuple[str, str]:
    cmds = _host_commands("### Test 1")
    return _one(cmds, "RID=nominal-r02"), _one(cmds, '[ "$T1H" = ok ] && wait_ready')


def test_test_1_harness_run_takes_nominal_r02_when_it_was_never_used(bench: Bench) -> None:
    check, run = t1_harness_lines()
    r = bench.run(bench.with_helpers("\n".join((check, 'echo "T1H=$T1H"', run, 'echo "RC1=$?"'))))
    assert r.value("T1H") == "ok" and r.value("RC1") == "0", r.out
    argv = harness_argv(bench)
    assert argv[argv.index("--run-id") + 1] == "nominal-r02"
    assert "--duration" not in argv and "--warmup" not in " ".join(argv)  # the plan's 600 s and 120 s, unchanged


@pytest.mark.parametrize("used", ["raw directory", "start record"])
def test_test_1_harness_entry_already_used_is_refused_and_nothing_starts(bench: Bench, used: str) -> None:
    trace = (bench.home / "egw-tcg" / "pilot" / "results" / "raw" / "nominal-r02" if used == "raw directory"
             else bench.p / "nominal-r02.sut")
    trace.mkdir(parents=True)
    check, run = t1_harness_lines()
    r = bench.run(bench.with_helpers("\n".join((check, 'echo "T1H=$T1H"', run, 'echo "RC1=$?"'))))
    assert r.value("T1H") == "stop" and r.value("RC1") != "0", r.out
    assert r.starting("STOP: test 1 (harness): nominal-r02 was already used"), r.out
    assert not (bench.state / "harness_argv").exists()
    assert bench.capture_calls() == []  # no recorder was started either


def test_test_1_plan_listing_shows_the_nominal_entries(bench: Bench) -> None:
    from egw_experiments import plan_gen
    plan = bench.home / "egw-tcg" / "pilot" / "campaign_plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps(plan_gen.generate_campaign_plan(42)), encoding="utf-8")
    listing = _one(_host_commands("### Test 1"), 'python3 -c "import json;p=json.load(')
    assert "expected ['nominal-r01', 'nominal-r02', 'nominal-r03']" in listing
    r = bench.run(listing)
    assert "['nominal-r01', 'nominal-r02', 'nominal-r03']" in r.lines, r.out


def _paragraph(heading: str, start: str) -> str:
    # strip: the first paragraph of a section follows the blank line after its heading
    hits = [p.strip("\n") for p in "\n".join(_section(heading)).split("\n\n") if p.strip("\n").startswith(start)]
    assert len(hits) == 1, f"{heading}: {len(hits)} paragraph(s) starting with {start!r}"
    return hits[0]


def test_section_7_states_the_timed_families() -> None:
    text = _paragraph("## 7.", "**Timed families (decision of 2026-09-30")
    for needle in ("test 1 (each of its three runs)", "test 2", "`itest-dup-02`", "test 5", "test 6",
                   "test 8's post-reboot smoke", "`lost = 0` and `late_confirmations = 0`", "marker plus 60 s",
                   "recorded as failed", "sizing finding", "does not turn the failure into a pass",
                   "throughput choice T1", "not test 1", "`delivery_across_restart_zero_lost`",
                   "`RESTART_RECOVERY_MAX_S`", "Test 3 is not timed", "`$P/$R.events.post-drain.jsonl`",
                   "decide nothing else for test 3", "No deadline, rate, duration or load changes"):
        assert needle in text, needle


def test_test_1_names_what_its_harness_run_is_and_is_not() -> None:
    cmds = _host_commands("### Test 1")
    assert not [c for c in cmds if c.startswith("RID=smoke_sequence")]
    text = "\n".join(_section("### Test 1"))
    assert "if the run is marked invalid for coverage, repeat with `--run-id` of a nominal entry" not in text
    expected = _paragraph("### Test 1", "Expected per run:")
    assert "`late_confirmations > 0` fails test 1" in expected and "sizing finding" in expected
    for needle in ("30 distinct instants, 90 % coverage, 5 s gaps", "reported as measured",
                   "**not** a passed 30 s smoke", "**not** a performance approval or a successful nominal delivery",
                   "distinct from the three wearable functional runs", "ten `smoke_sequence` repetitions of C14"):
        assert needle in text, needle


def test_test_3_expected_list_requires_every_valid_message_accepted_by_the_end_of_the_drain() -> None:
    expected = _paragraph("### Test 3", "Expected:")
    for needle in ("`$P/$R.events.post-drain.jsonl`", "accepted late", "fails test 3", "gives up",
                   "not evaluated", "never passed", "Test 3 is not timed", "decide nothing else for test 3",
                   "`valid rejected = 0`", "every `delta` line `OK`",
                   # a STOP of 'finish' after its fetch leaves the copy: judged, never 'not evaluated'
                   "stops after its fetch", "without any outcome line fails test 3", "`F3`",
                   # fresh on the host AND on the guest, whose log of a run id persists and is appended to
                   "neither the host (`$P/$R`) nor the guest holds it", "a guest that does not answer leaves `F3`",
                   # a partial fetch is no copy: not kept, not judged
                   "the guest's whole log", "failed part-way", "appended to the guest's log after the fetch",
                   # judged as fetched: a line between the drain's last reading and the fetch counts
                   "after the last reading of the drain and before the fetch", "cannot make a message accepted"):
        assert needle in expected, needle
    # an accepted line that reached the controller after the drain and before the fetch is in the copy and counts
    assert "is beyond the planned collection and can only make test 3 fail" not in expected


def test_test_4_expected_list_judges_the_replay_per_identity_and_includes_the_sequence_reset() -> None:
    expected = _paragraph("### Test 4", "Expected")
    assert "`duplicate` equals the number of replayed messages" not in expected
    assert "`duplicate` = number of replayed messages" not in expected
    for needle in ("`started_at`", "`uptime_s`", "`processing_errors`", "`mqtt_connection`", "non-decreasing",
                   "`duplicate_replayed`", "`duplicate_redelivery`", "consistent with the reconnection budget",
                   "decides nothing", "`accepted 0`", "`queue_depth 0`", "UNCHANGED", "`itest-dup-02`",
                   "never been run", "`lost = 0`, `late_confirmations = 0`", "a failure of test 4",
                   # the replay's lines: beyond the copy AND received after the 'after' reading
                   "`received_monotonic_ns`", "at or before the `after` reading", "exit 1",
                   # 2026-10-01: a redelivery of the first run is bounded by k, the reconnections of the interval
                   "k = 0", "ADR 0011, N2", "more than k added `duplicate` lines", "**not demonstrated**",
                   "exits 5", "**not passed**", "distinct from a failure", "takes precedence",
                   # the difference line: no difference of two processes
                   "takes no difference of two readings that are not of one process"):
        assert needle in expected, needle
    assert "caused by" not in expected
    # the limit stated until 2026-10-01 is removed: such a line can no longer stand for the replay's
    assert "A stated limit, not conservative" not in expected
    assert "so it could stand for a replayed identity's own `duplicate` line" not in expected
    # a line appended after the pre-replay fetch can stand for a replay line: it does NOT only make test 4 fail
    assert "it can only make test 4 fail" not in expected


def test_tests_5_6_and_8_are_timed_and_section_8_names_the_spent_entry() -> None:
    t5 = _paragraph("### Test 5", "Expected:")
    assert "test 5 fails" in t5 and "sizing finding" in t5
    assert "a guest-speed finding under TCG, reported as measured;" not in t5
    t6 = "\n".join(_section("### Test 6"))
    assert "is reported as measured, never suppressed" not in t6
    for needle in ("`delivery_across_restart_zero_lost`", "own row of `per_run.csv`",
                   "`lost = 0` and `late_confirmations = 0`", "beside that criterion"):
        assert needle in t6, needle
    assert "a timed family" in _paragraph("### Test 8", "Expected:")
    order = _paragraph("## 8.", "1. **Order.**")
    assert "`nominal-r02`" in order and "test 1" in order.lower()


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
#: The start of the optional, read-only re-run of delta with the N1 report (decision 2 of 2026-09-30) that closes the
#: test 7 block and its Ditto repeat, after the evaluation line.
T7_N1_LINE = ('[ "$T7" != stop ] && [ "$LC" = 0 ] && [ -s $P/$R.sut/controller.log ] && [ -s $P/$R.twins.after.json ] '
              '&& { $REC delta ')
#: An assignment of T7 in a command, in any of the forms bash takes it (a declaration keyword with its options before
#: it, a subshell, a loop body); the stop message only quotes T7's value
T7_ASSIGNMENT = re.compile(r"(^|[;&|{(]|then|else|do)\s*((export|declare|local|readonly|typeset)\s+(-\w+\s+)*)?T7=")


def _t7_body(prefix: str = "", n1: bool = False) -> tuple[str, str, str]:
    """All host$ lines of the test 7 block in their order, the optional N1 re-run of delta left out unless ``n1``;
    returns (body, run id, service)."""
    cmds = _host_commands("### Test 7")
    first = _one(cmds, "R=")
    rid = run_id_of(first, "R")
    svc = re.search(r"SVC=([A-Za-z0-9_-]+)", first)
    assert svc, first
    test_line = _one(cmds, "T7=stop; if pre $R")
    n1_line = _one(cmds, T7_N1_LINE)
    assert cmds.index(test_line) == len(cmds) - 3, "the evaluation line is expected right after the test line"
    assert cmds[-1] == n1_line, "the optional N1 re-run of delta is expected last, after the evaluation line"
    body = [prefix, *cmds[:-2], 'echo "T7_VALUE=$T7"', cmds[-2].split("\n")[0], 'echo "EVAL_RC=$?"']
    if n1:
        body += [n1_line.split("     #", 1)[0], 'echo "N1_RC=$?"']
    return "\n".join(body), rid, svc.group(1)


def _ditto_body(n1: bool = False) -> tuple[str, str, str]:
    """The Ditto repeat as the runbook has it pasted: test 7's helpers (DC, svc_state, fault_recover, fault, readyp),
    then the repeat's own lines (the optional N1 re-run of delta only with ``n1``); returns (body, run id, service)."""
    t7, ditto = _host_commands("### Test 7"), _host_commands("### Repeat of test 7 for Ditto")
    first = _one(ditto, "R=")
    rid, svc = run_id_of(first, "R"), re.search(r"SVC=([A-Za-z0-9_-]+)", first).group(1)
    assert len(ditto) == 4 and ditto[3] == _one(ditto, T7_N1_LINE)
    body = [ln for ln in t7[:-3] if not ln.startswith("R=")] + [first, ditto[1], 'echo "T7_VALUE=$T7"',
                                                                 ditto[2].split("\n")[0], 'echo "EVAL_RC=$?"']
    if n1:
        body += [ditto[3].split("     #", 1)[0], 'echo "N1_RC=$?"']
    return "\n".join(body), rid, svc


def _t7_guest_logs(bench: Bench) -> None:
    """What the guest's controller and broker logs hold for a sub-check's window (read by sut_log)."""
    bench.set("controller.guest", '2026-09-29T10:00:01.000000000Z {"level": "WARNING", "message": "Ditto PATCH failed"}')
    bench.set("broker.guest", "2026-09-29T10:00:01.000000000Z 1790000001: Client egw-controller has exceeded timeout")


def call_test7(bench: Bench, stub_pgrep_rc: int | None = 0, prefix: str = "", sub: str = "mongodb",
               n1: bool = False, **env: str) -> tuple[Result, str, str]:
    body, rid, svc = _t7_body(prefix, n1=n1) if sub == "mongodb" else _ditto_body(n1=n1)
    full_run(bench, rid)
    bench.set("svc_state", "running")
    _t7_guest_logs(bench)
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


def test_the_ditto_repeat_of_test_7_judges_egw_ditto_things_1(bench: Bench) -> None:
    t7 = _host_commands("### Test 7")
    ditto = _host_commands("### Repeat of test 7 for Ditto")
    r, rid, svc = call_test7(bench, sub="ditto")
    assert svc == "ditto-things"
    assert r.value("T7_VALUE") == "0", r.out
    fetch = [ln for ln in bench.capture_calls() if ln.startswith("fetch [docker-events]")]
    assert fetch == [f"fetch [docker-events] [{bench.p / (rid + '.sut')}/docker-events.log] [1790000000] [{rid}] "
                     f"[die,stop,start] [egw-ditto-things-1]"]
    assert ditto[1] == _one(t7, "T7=stop; if pre $R"), "the repeat's test line is test 7's, unchanged"


# --------------------------------------------------------------------------
# Test 7, both sub-checks: an incomplete capture or scoped log is never an accepted fault test (review of PR #51, B2)
# --------------------------------------------------------------------------
SUB_CHECKS = ["mongodb", "ditto"]


def assert_incomplete_keeps_the_observations(bench: Bench, r: Result, rid: str, svc: str, *parts: str) -> None:
    """T7 is neither 0 nor 'failed:' (the system's behaviour was shown), the STOP says the instrumentation is
    incomplete, the observations are printed and kept, and the evaluation line refuses."""
    value = r.value("T7_VALUE")
    assert value.startswith("incomplete:") and all(p in value for p in parts), r.out
    assert r.starting(f"INTERRUPTION SHOWN: {svc} went from 'running' to 'exited'"), r.out
    assert r.starting(f"RECOVERY SHOWN: {svc} is 'running' after start"), r.out
    stop = [ln for ln in r.starting("STOP: test 7: ") if "INCOMPLETE" in ln]
    assert len(stop) == 1 and "the interruption and the recovery are shown" in stop[0], r.out
    assert not r.starting("STOP: test 7: NOT accepted"), r.out
    assert r.value("EVAL_RC") != "0" and not r.starting("Counter("), r.out
    fault = (bench.p / f"{rid}.fault.txt").read_text(encoding="utf-8")
    assert "INTERRUPTION SHOWN" in fault and "RECOVERY SHOWN" in fault
    assert (bench.p / f"{rid}.ready.txt").stat().st_size > 0, "the /ready record was not kept"


@pytest.mark.parametrize("sub", SUB_CHECKS)
@pytest.mark.parametrize("case", ["incomplete", "missing"])
def test_test_7_both_faults_shown_but_the_capture_not_complete_is_not_accepted_and_keeps_the_observations(
        bench: Bench, sub: str, case: str) -> None:
    """The capture not shown complete (the fetch's status 1), or answered 0 without a docker-events.log: T7 was 0,
    decided by the SHOWN lines alone; it is now 'incomplete:' and the evaluation line refuses."""
    bench.set("fetch_docker-events_rc" if case == "incomplete" else "fetch_docker-events_nofile", 1)
    r, rid, svc = call_test7(bench, sub=sub)
    assert_incomplete_keeps_the_observations(bench, r, rid, svc, "events_stop=1")
    assert r.starting(f"STOP: events_stop {rid}: the Docker events capture is NOT shown complete"), r.out
    assert not (bench.p / f"{rid}.sut" / "docker-events.log").exists()


@pytest.mark.parametrize("sub", SUB_CHECKS)
@pytest.mark.parametrize("kind", ["controller", "broker"])
def test_test_7_both_faults_shown_but_a_scoped_log_not_read_is_not_accepted(bench: Bench, sub: str,
                                                                             kind: str) -> None:
    bench.set(f"fetch_{kind}_rc", 1)
    r, rid, svc = call_test7(bench, sub=sub)
    assert_incomplete_keeps_the_observations(bench, r, rid, svc, f"{kind}_log=1", "events_stop=0")
    assert r.starting(f"STOP: sut_log {kind} {rid}: the {kind} log bounded to"), r.out
    assert not (bench.p / f"{rid}.sut" / f"{kind}.log").exists()
    assert (bench.p / f"{rid}.sut" / "docker-events.log").is_file(), "the complete capture was not kept"


@pytest.mark.parametrize("sub", SUB_CHECKS)
def test_test_7_a_complete_capture_whose_cleanup_fails_stays_complete_and_the_sub_check_is_incomplete(
        bench: Bench, sub: str) -> None:
    bench.set("events_cleanup_rc", 1)
    r, rid, svc = call_test7(bench, sub=sub)
    assert_incomplete_keeps_the_observations(bench, r, rid, svc, "events_stop=3")
    stop = [ln for ln in r.starting(f"STOP: events_stop {rid}: ")]
    assert len(stop) == 1 and "IS shown complete" in stop[0] and "INCOMPLETE" in stop[0], r.out
    assert f"egw-events-{rid} may still run" in stop[0], r.out
    assert (bench.p / f"{rid}.sut" / "docker-events.log").is_file(), "the complete capture was not kept"


@pytest.mark.parametrize("sub", SUB_CHECKS)
def test_test_7_both_sub_checks_read_their_logs_from_the_recorders_readiness_after_the_recovery_and_before_the_fetch(
        bench: Bench, sub: str) -> None:
    """The scoped logs of the sub-check (sut_log), bounded by its own T0_7 - the recorder's readiness, not the guest
    clock at the read - read after the recovery and before events_stop, whose window then still covers them."""
    bench.set("events_t0", 1790000321)
    r, rid, svc = call_test7(bench, sub=sub)
    assert r.value("T7_VALUE") == "0", r.out
    assert not r.starting("STOP"), r.out
    assert r.value("EVAL_RC") == "0" and r.starting("Counter("), r.out
    d = bench.p / f"{rid}.sut"
    log = bench.ssh_log()
    recover = next(i for i, ln in enumerate(log) if ln.endswith(f" start {svc}]"))
    controller = log.index(f"fetch [controller] [{d}/controller.log] [1790000321]")
    broker = log.index(f"fetch [broker] [{d}/broker.log] [1790000321]")
    fetch = next(i for i, ln in enumerate(log) if ln.startswith("fetch [docker-events]"))
    assert recover < controller < broker < fetch, log
    assert (d / "controller.log").is_file() and (d / "broker.log").is_file()
    assert (d / "controller.fetch.txt").is_file() and (d / "broker.fetch.txt").is_file()


@pytest.mark.parametrize("sub", SUB_CHECKS)
@pytest.mark.parametrize("capture, ev", [("complete", "0"), ("not_complete", "1")])
def test_test_7_an_observation_that_failed_keeps_the_instrumentations_statuses_beside_it(bench: Bench, sub: str,
                                                                                         capture: str, ev: str) -> None:
    """Review of PR #51, B2, second round: when an observation of the system failed, the 'failed:' value and its STOP
    named only sim_post, the fault job and the /ready poller, so a capture or log that was incomplete as well showed
    only in the helpers' own STOPs. The value and the STOP now carry the three instrumentation statuses too, in every
    branch, beside the system's and never in place of them."""
    bench.set("ssh_stop_rc", 1)
    if capture == "not_complete":
        bench.set("fetch_docker-events_rc", 1)
    r, rid, svc = call_test7(bench, sub=sub)
    assert_test7_not_accepted(r)
    assert r.value("T7_VALUE") == \
        f"failed:sim_post=0,fault_job=1,readyp_kill=0,events_stop={ev},controller_log=0,broker_log=0", r.out
    stop = r.starting("STOP: test 7: NOT accepted")
    assert len(stop) == 1, r.out
    assert "sim_post exit=0, fault job exit=1, kill of the /ready poller exit=0" in stop[0], stop[0]
    assert f"events_stop exit={ev}, controller log read exit=0, broker log read exit=0" in stop[0], stop[0]
    assert not r.starting("STOP: test 7: the interruption and the recovery are shown"), r.out


# --------------------------------------------------------------------------
# Test 7, both sub-checks: the optional N1 report of delta (decision 2 of 2026-09-30)
# --------------------------------------------------------------------------
def _n1_reruns(bench: Bench) -> list[str]:
    """The delta calls that name a controller log: the optional re-run only ('finish' names none)."""
    return [ln for ln in bench.calls().splitlines()
            if ln.startswith("python -m egw_experiments.itest_reconcile delta ") and "--controller-log" in ln]


@pytest.mark.parametrize("sub", SUB_CHECKS)
def test_test_7_the_optional_n1_report_reruns_delta_with_the_sub_checks_controller_log(bench: Bench, sub: str) -> None:
    r, rid, _svc = call_test7(bench, sub=sub, n1=True)
    assert r.value("T7_VALUE") == "0", r.out
    assert r.value("N1_RC") == "0" and not r.starting("STOP"), r.out
    assert _n1_reruns(bench) == [f"python -m egw_experiments.itest_reconcile delta {bench.p}/{rid} "
                                 f"--controller-log {bench.p}/{rid}.sut/controller.log"]
    for line in _host_commands("### Test 7")[-1:] + _host_commands("### Repeat of test 7 for Ditto")[-1:]:
        command = line.split("     #", 1)[0]
        # read-only: no assignment of T7 (its value is only quoted in the stop message), and no redirection
        assert line.startswith(T7_N1_LINE) and not T7_ASSIGNMENT.search(command), line
        assert ">" not in command, line


def test_test_7_read_only_check_catches_every_form_of_an_assignment_of_t7() -> None:
    """Review of 2026-09-30 (H3): the check that replaced '"T7=" not in the line' missed 'export T7=ok', 'declare
    T7=ok', 'local', 'readonly', 'typeset' and '(T7=ok)', which the old check caught."""
    for form in ("a || export T7=ok", "a || declare T7=ok", "a || declare -g T7=ok", "a || local T7=ok",
                 "a || readonly T7=ok", "a || typeset T7=ok", "a || (T7=ok)", "a && T7=ok", "a; T7=ok",
                 "{ export T7=ok; $REC delta x; }", "if a; then T7=ok; fi", "for x in 1; do T7=ok; done", "T7=ok"):
        assert T7_ASSIGNMENT.search(form), form
    for quoted in ("stop \"test 7: ... - it is read-only: finish's delta and T7='$T7' stand\"", '[ "$T7" != stop ]'):
        assert not T7_ASSIGNMENT.search(quoted), quoted


@pytest.mark.parametrize("sub", SUB_CHECKS)
def test_test_7_the_n1_report_runs_beside_a_delta_mismatch_and_changes_no_status(bench: Bench, sub: str) -> None:
    """An N1 identity makes the device line a MISMATCH, so 'finish' stops and T7 is 'failed:'; the re-run still
    reports (exit 4 is a result), with no STOP of its own, and the failed T7 stands."""
    bench.set("rec_delta_rc", 4)
    r, rid, _svc = call_test7(bench, sub=sub, n1=True)
    assert r.value("T7_VALUE").startswith("failed:sim_post="), r.out
    assert r.value("N1_RC") == "0" and not r.starting("STOP: test 7: the optional N1 report"), r.out
    assert len(_n1_reruns(bench)) == 1


@pytest.mark.parametrize("sub", SUB_CHECKS)
@pytest.mark.parametrize("case", ["controller log not read", "delta not carried out"])
def test_test_7_the_n1_report_not_produced_is_a_stop_of_its_own(bench: Bench, sub: str, case: str) -> None:
    if case == "controller log not read":
        bench.set("fetch_controller_rc", 1)
    else:
        bench.set("rec_delta_rc", 1)
    r, _rid, _svc = call_test7(bench, sub=sub, n1=True)
    assert r.value("N1_RC") != "0", r.out
    assert len(r.starting("STOP: test 7: the optional N1 report was NOT produced")) == 1, r.out
    assert len(_n1_reruns(bench)) == (0 if case == "controller log not read" else 1)


@pytest.mark.parametrize("again", ["the Ditto repeat", "test 7 pasted again"])
def test_test_7_n1_report_after_a_refused_precondition_in_the_same_shell_runs_no_delta(bench: Bench, again: str) -> None:
    """Review of 2026-09-30 (RB-1): the optional N1 line tested LC only, which the test line never resets. Pasted in
    the same shell after a completed sub-check (LC 0), on a run id already used - 'pre' refuses it, nothing is
    injected or published - it ran delta on an earlier execution's files and printed an N1 report for a run that never
    started, with no STOP. Each N1 line now first tests T7, which stays 'stop' exactly when the test line's
    precondition failed or the line was interrupted: no delta runs, and the line prints its STOP."""
    body, mongo_rid, _svc = _t7_body(n1=True)
    t7, ditto = _host_commands("### Test 7"), _host_commands("### Repeat of test 7 for Ditto")
    lines = ditto if again == "the Ditto repeat" else [_one(t7, "R="), _one(t7, "T7=stop; if pre $R"), *t7[-2:]]
    rid = run_id_of(lines[0], "R")
    if again == "the Ditto repeat":
        # an earlier execution of the Ditto repeat left its files: its run directory, its log and its 'after' twins
        (bench.p / f"{rid}.sut").mkdir(parents=True)
        (bench.p / rid).mkdir()
        (bench.p / f"{rid}.sut" / "controller.log").write_text("an earlier execution's controller log\n", encoding="utf-8")
        (bench.p / f"{rid}.twins.after.json").write_text('{"stub": true}\n', encoding="utf-8")
    full_run(bench, mongo_rid)
    bench.set("svc_state", "running")
    _t7_guest_logs(bench)
    bench.install("pgrep", STUB_PGREP)
    bench.set("pgrep_rc", 0)
    body += "\n" + "\n".join((lines[0], lines[1], 'echo "AGAIN_T7=$T7"', lines[2].split("\n")[0], 'echo "AGAIN_EVAL=$?"',
                              lines[3].split("     #", 1)[0], 'echo "AGAIN_N1=$?"'))
    r = bench.run(bench.with_helpers(body))
    # the MongoDB sub-check completed and produced its N1 report (LC 0 is left in the shell)
    assert r.value("T7_VALUE") == "0" and r.value("N1_RC") == "0", r.out
    assert r.value("AGAIN_T7") == "stop" and r.value("AGAIN_EVAL") != "0", r.out
    assert r.starting(f"STOP: pre {rid}: "), r.out
    assert r.starting("STOP: test 7: precondition failed - NO fault was injected and nothing was published"), r.out
    assert r.value("AGAIN_N1") != "0", r.out
    assert len(r.starting("STOP: test 7: the optional N1 report was NOT produced")) == 1, r.out
    assert _n1_reruns(bench) == [f"python -m egw_experiments.itest_reconcile delta {bench.p}/{mongo_rid} "
                                 f"--controller-log {bench.p}/{mongo_rid}.sut/controller.log"], r.out
    assert bench.simulator_calls() == 1


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
# test 8 - the guest reboots inside the same QEMU process (2026-10-03): a different boot id within a bounded wait,
# the containers back UNAIDED before anything starts them, then readiness, state and the fresh smoke
# --------------------------------------------------------------------------
T8_PRE_ID = "aaaaaaaa-0000-4000-8000-00000000000a"
T8_POST_ID = "bbbbbbbb-0000-4000-8000-00000000000b"
T8_POST_STARTED = "2026-10-03T14:26:40Z"
#: six running container objects, as 'docker ps -q --no-trunc | sort' lists them (one full id per line, sorted)
T8_CONTAINERS = sorted("%064x" % (0x1000 + i) for i in range(6))
T8_SMOKE = "itest-post-reboot-01"
#: the start of each of the six lines of the block, in the order they are pasted (a to f)
T8_STARTS = ("T8=stop; if wait_ready && drained && metrics itest-reboot pre-reboot",
             'if [ "$T8" = rebooting ]',
             'if [ "$T8" = rebooted ]',
             '[ "$T8" = returned ] && tunnel_down && tunnel_up',
             '[ "$T8" = reconnected ] && wait_ready 3600',
             'if [ "$T8" = ok ]; then R=itest-post-reboot-01')


def t8_lines() -> list[str]:
    """The six host$ lines of the test 8 block, a to f, each without its continuation (comment) lines."""
    cmds = _host_commands("### Test 8")
    lines = [_one(cmds, start) for start in T8_STARTS]
    assert cmds == lines, "the test 8 block is expected to hold exactly these six lines, in this order"
    return [ln.split("\n")[0] for ln in lines]


def _t8_body(from_line: str = "a") -> str:
    """Lines a to f pasted in one shell, each followed by an echo of the carrier T8 it left (RC_F after the smoke
    line); ``from_line`` 'b' leaves line a out (the lines after it in a shell in which it never ran)."""
    body = []
    for letter, line in zip("abcdef", t8_lines()):
        if letter < from_line:
            continue
        body.append(line)
        body.append('echo "RC_F=$?"' if letter == "f" else f'echo "T8_{letter.upper()}=$T8"')
    return "\n".join(body)


def t8_prepare(bench: Bench, post_started_at: str | None = T8_POST_STARTED) -> None:
    """The guest and controller a success needs: the boot id before and after, the six container ids, a controller
    that is a new process after the reboot (``post_started_at``; None leaves the same process), the smoke's files."""
    bench.set("boot_id", T8_PRE_ID)
    bench.set("boot_id.post", T8_POST_ID)
    bench.set("containers.pre", "\n".join(T8_CONTAINERS))
    if post_started_at is not None:
        (bench.state / "metrics.post.json").write_text(json.dumps(bench.reading(started_at=post_started_at)), encoding="utf-8")
    full_run(bench, T8_SMOKE)


def call_test8(bench: Bench, from_line: str = "a", **env: str) -> Result:
    return bench.run(bench.with_helpers(_t8_body(from_line)), timeout=240, **env)


def t8_ssh_after_reboot(bench: Bench, tail: str) -> list[str]:
    """The ssh invocations after the reboot command whose last argument ends with ``tail``."""
    log = bench.ssh_log()
    rebooted = [i for i, ln in enumerate(log) if "sudo systemctl reboot" in ln]
    assert len(rebooted) == 1, log
    return [ln for ln in log[rebooted[0] + 1:] if ln.endswith(f"{tail}]")]


def t8_boot_id_polls(bench: Bench) -> list[str]:
    return t8_ssh_after_reboot(bench, "/proc/sys/kernel/random/boot_id")


def t8_container_reads(bench: Bench) -> list[str]:
    return t8_ssh_after_reboot(bench, "docker ps -q --no-trunc | sort")


def assert_t8_nothing_started_anything(bench: Bench) -> None:
    """No 'compose up', 'start' or 'restart' went to the guest: a return is only unaided when nothing started it."""
    for ln in bench.ssh_log():
        assert not re.search(r"compose\b.*\b(up|start|restart)\b", ln), ln
    assert "PATTERN-KILL" not in bench.calls(), bench.calls()


def assert_t8_no_smoke(bench: Bench, r: Result) -> None:
    assert bench.simulator_calls() == 0, bench.calls()
    assert r.value("RC_F") != "0", r.out
    assert r.starting("STOP: test 8: the post-reboot smoke is NOT started"), r.out


def t8_index(bench: Bench, tail: str, last: bool = False) -> int:
    """The index in the ssh log of the first (or last) invocation whose last argument ends with ``tail``."""
    hits = [i for i, ln in enumerate(bench.ssh_log()) if ln.endswith(f"{tail}]")]
    assert hits, (tail, bench.ssh_log())
    return hits[-1] if last else hits[0]


def test_test_8_success_path_different_boot_id_after_a_few_polls_same_container_set_same_twins_new_process_and_the_smoke(
        bench: Bench) -> None:
    t8_prepare(bench)
    r = call_test8(bench)
    assert (r.value("T8_A"), r.value("T8_B"), r.value("T8_C"), r.value("T8_D"), r.value("T8_E")) == \
        ("rebooting", "rebooted", "returned", "reconnected", "ok"), r.out
    assert not r.starting("STOP"), r.out
    assert r.starting(f"REBOOT SHOWN: boot id {T8_PRE_ID} -> {T8_POST_ID}"), r.out
    assert r.starting("CONTAINERS RETURNED UNAIDED"), r.out
    assert r.starting(f"CONTROLLER PROCESS NEW: started_at {STARTED} -> {T8_POST_STARTED}"), r.out
    assert "TUNNEL UP" in r.lines, r.out
    assert r.value("RC_F") == "0", r.out
    assert r.starting(f"TEST STATUS {T8_SMOKE}: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE"), r.out
    assert bench.simulator_calls() == 1
    # what line a saved before the reboot, and what the lines after it read back
    assert (bench.p / "itest-reboot.boot_id.pre").read_text(encoding="utf-8").strip() == T8_PRE_ID
    assert (bench.p / "itest-reboot.boot_id.post").read_text(encoding="utf-8").strip() == T8_POST_ID
    assert (bench.p / "itest-reboot.containers.pre").read_text(encoding="utf-8").split() == T8_CONTAINERS
    assert (bench.p / "itest-reboot.containers.post").read_text(encoding="utf-8").split() == T8_CONTAINERS
    assert json.loads((bench.p / "itest-reboot.metrics.pre-reboot.json").read_text(encoding="utf-8"))["started_at"] == STARTED
    assert json.loads((bench.p / "itest-reboot.metrics.post-reboot.json").read_text(encoding="utf-8"))["started_at"] == T8_POST_STARTED
    assert (bench.p / "itest-reboot.twins.pre-reboot.json").exists() and (bench.p / "itest-reboot.twins.post-reboot.json").exists()
    # the saves came before the reboot command; the polls after it are bounded per read and found the new id at the third
    log = bench.ssh_log()
    reboot_at = next(i for i, ln in enumerate(log) if "sudo systemctl reboot" in ln)
    assert t8_index(bench, "/proc/sys/kernel/random/boot_id") < reboot_at, log
    assert t8_index(bench, "docker ps -q --no-trunc | sort") < reboot_at, log
    polls = t8_boot_id_polls(bench)
    assert len(polls) == 3 and all("[-o] [BatchMode=yes] [-o] [ConnectTimeout=10]" in ln for ln in polls), polls
    # the containers were read only once the reboot was shown (the first read after the reboot follows the last poll),
    # and nothing started them
    reads = t8_container_reads(bench)
    assert len(reads) == 2 and all("[-o] [BatchMode=yes] [-o] [ConnectTimeout=10]" in ln for ln in reads), reads
    first_read_after = min(i for i, ln in enumerate(log) if i > reboot_at and ln.endswith("[docker ps -q --no-trunc | sort]"))
    assert first_read_after > t8_index(bench, "/proc/sys/kernel/random/boot_id", last=True), log
    assert_t8_nothing_started_anything(bench)
    # the read-only observations came after the return, before the tunnel and the snapshot
    observed = t8_ssh_after_reboot(bench, "findmnt -no SOURCE /var/lib/docker")
    assert len(observed) == 1, observed
    assert t8_index(bench, "findmnt -no SOURCE /var/lib/docker") > t8_index(bench, "docker ps -q --no-trunc | sort", last=True), log
    assert t8_index(bench, "findmnt -no SOURCE /var/lib/docker") < next(i for i, ln in enumerate(log) if "[-M]" in ln), log
    assert "--label post-reboot" in bench.calls() and "same" in bench.calls()


def test_test_8_guest_never_answers_is_a_stop_after_90_bounded_reads_and_no_later_line_runs(bench: Bench) -> None:
    t8_prepare(bench)
    bench.set("guest_never_answers")
    r = call_test8(bench)
    assert r.value("T8_A") == "rebooting" and r.value("T8_B") == "rebooting", r.out
    assert any("the guest never answered" in ln for ln in r.starting("STOP: test 8: reboot NOT shown")), r.out
    assert not r.starting("REBOOT SHOWN"), r.out
    polls = t8_boot_id_polls(bench)
    assert len(polls) == 90 and all("[-o] [BatchMode=yes] [-o] [ConnectTimeout=10]" in ln for ln in polls), len(polls)
    assert t8_container_reads(bench) == [] and not r.starting("CONTAINERS RETURNED UNAIDED"), r.out
    assert not [ln for ln in bench.ssh_log() if "[-M]" in ln], bench.ssh_log()
    assert "--label post-reboot" not in bench.calls() and "same" not in bench.calls(), bench.calls()
    assert r.value("T8_C") == "rebooting" and r.value("T8_D") == "rebooting" and r.value("T8_E") == "rebooting", r.out
    assert_t8_no_smoke(bench, r)
    assert_t8_nothing_started_anything(bench)


@pytest.mark.parametrize("case, says", [
    ("kept answering the old id", "kept answering the OLD boot id"),
    ("answered the old id, then went down for good", "then stopped answering"),
])
def test_test_8_unchanged_boot_id_is_reboot_not_shown_and_no_later_line_runs(bench: Bench, case: str, says: str) -> None:
    t8_prepare(bench)
    bench.set("boot_id.post", T8_PRE_ID)
    if case.startswith("kept"):
        bench.set("guest_down_calls", 0)
    else:
        bench.set("guest_dies_after_calls", 3)                           # calls 1-2 down, call 3 the old id, then nothing
    r = call_test8(bench)
    assert r.value("T8_B") == "rebooting", r.out
    stops = r.starting("STOP: test 8: reboot NOT shown")
    assert len(stops) == 1 and says in stops[0], r.out
    assert not r.starting("REBOOT SHOWN"), r.out
    assert len(t8_boot_id_polls(bench)) == 90
    assert not (bench.p / "itest-reboot.boot_id.post").exists()
    assert t8_container_reads(bench) == [] and not [ln for ln in bench.ssh_log() if "[-M]" in ln]
    assert r.value("T8_E") == "rebooting", r.out
    assert_t8_no_smoke(bench, r)


@pytest.mark.parametrize("case", ["one container missing", "one container recreated", "nothing listed"])
def test_test_8_a_container_set_that_differs_is_not_an_unaided_return_nothing_is_started_and_no_smoke_runs(
        bench: Bench, case: str) -> None:
    t8_prepare(bench)
    if case == "one container missing":
        bench.set("containers.post", "\n".join(T8_CONTAINERS[:-1]))
    elif case == "one container recreated":
        bench.set("containers.post", "\n".join(sorted(T8_CONTAINERS[:-1] + ["%064x" % 0x2000])))
    else:
        bench.set("docker_ps_empty_calls", 1000)
    r = call_test8(bench)
    assert r.value("T8_B") == "rebooted" and r.value("T8_C") == "rebooted", r.out
    assert r.starting("REBOOT SHOWN"), r.out
    assert not r.starting("CONTAINERS RETURNED UNAIDED"), r.out
    assert any("did NOT return unaided" in ln for ln in r.starting("STOP: test 8:")), r.out
    assert len(t8_container_reads(bench)) == 90
    assert_t8_nothing_started_anything(bench)
    assert t8_ssh_after_reboot(bench, "findmnt -no SOURCE /var/lib/docker") == []
    assert not [ln for ln in bench.ssh_log() if "[-M]" in ln]
    assert r.value("T8_D") == "rebooted" and r.value("T8_E") == "rebooted", r.out
    assert_t8_no_smoke(bench, r)


@pytest.mark.parametrize("case", ["five containers before the reboot", "boot id unreadable", "metrics unreachable",
                                  "twin snapshot refused"])
def test_test_8_a_failed_precondition_of_line_a_reboots_nothing_and_no_later_line_runs(bench: Bench, case: str) -> None:
    t8_prepare(bench)
    if case.startswith("five"):
        bench.set("containers.pre", "\n".join(T8_CONTAINERS[:-1]))
    elif case == "boot id unreadable":
        bench.set("boot_id_unreadable")
    elif case == "metrics unreachable":
        (bench.state / "metrics.json").unlink()
    else:
        bench.set("rec_snap_rc", 1)
    r = call_test8(bench)
    assert r.value("T8_A") == "stop", r.out
    assert r.starting("STOP: test 8:") and any("the guest was NOT rebooted" in ln for ln in r.starting("STOP: test 8:")), r.out
    assert not [ln for ln in bench.ssh_log() if "sudo systemctl reboot" in ln], bench.ssh_log()
    assert not r.starting("REBOOT ISSUED") and not r.starting("REBOOT SHOWN"), r.out
    assert all(r.value(f"T8_{x}") == "stop" for x in "BCDE"), r.out
    assert not [ln for ln in bench.ssh_log() if "[-M]" in ln]
    assert_t8_no_smoke(bench, r)


@pytest.mark.parametrize("case, says", [
    ("same reports DIFFERENT", "'same' reported DIFFERENT"),
    ("started_at unchanged", "started_at unchanged"),
])
def test_test_8_state_not_verified_on_line_e_leaves_the_smoke_unstarted(bench: Bench, case: str, says: str) -> None:
    t8_prepare(bench, post_started_at=None if case == "started_at unchanged" else T8_POST_STARTED)
    if case == "same reports DIFFERENT":
        bench.set("rec_same_rc", 4)
    r = call_test8(bench)
    assert r.value("T8_D") == "reconnected" and r.value("T8_E") == "reconnected", r.out
    assert r.starting("REBOOT SHOWN") and r.starting("CONTAINERS RETURNED UNAIDED"), r.out
    assert not r.starting("CONTROLLER PROCESS NEW"), r.out
    stops = r.starting("STOP: test 8: persistence across the reboot NOT verified")
    assert len(stops) == 1 and says in stops[0], r.out
    assert_t8_no_smoke(bench, r)


def test_test_8_observations_not_read_after_the_return_is_a_stop_that_keeps_the_return_shown(bench: Bench) -> None:
    t8_prepare(bench)
    bench.set("observations_rc", 1)
    r = call_test8(bench)
    assert r.value("T8_B") == "rebooted" and r.value("T8_C") == "rebooted", r.out
    assert r.starting("CONTAINERS RETURNED UNAIDED"), r.out
    assert any("observations were NOT all read" in ln for ln in r.starting("STOP: test 8:")), r.out
    assert not [ln for ln in bench.ssh_log() if "[-M]" in ln]
    assert_t8_no_smoke(bench, r)


def test_test_8_lines_after_a_refuse_in_a_shell_in_which_a_never_ran(bench: Bench) -> None:
    t8_prepare(bench)
    r = call_test8(bench, from_line="b")
    assert all(r.value(f"T8_{x}") == "" for x in "BCDE"), r.out
    assert len(r.starting("STOP: test 8:")) == 5, r.out
    assert bench.ssh_log() == [] and bench.simulator_calls() == 0


def test_test_8_text_states_the_in_process_reboot_the_unaided_return_and_the_halt_before_test_9() -> None:
    section = "\n".join(_section("### Test 8"))
    for needle in ("without `-no-reboot`", "same QEMU process", "operator decision", "never automatic",
                   "REBOOT SHOWN", "CONTAINERS RETURNED UNAIDED", "CONTROLLER PROCESS NEW", "`restart: unless-stopped`",
                   "BatchMode=yes", "ConnectTimeout=10", "at most 90 reads", "Test 9 is not started"):
        assert needle in section, needle
    assert "QEMU exits (-no-reboot)" not in section
    assert "Re-launch exactly as in 3.3" not in section
    expected = _paragraph("### Test 8", "Expected:")
    assert "a timed family" in expected and "`UNVERIFIED:`" in expected
    appendix = "\n".join(_section("## Appendix B"))
    assert "in-process reboot" in appendix and "guest-unverified" in appendix.split("in-process reboot", 1)[1]
    # the lines run nothing by pattern and start nothing on the guest
    for ln in t8_lines():
        assert not re.search(r"\bkill\b|\bpgrep\b|\bpkill\b", ln), ln
        assert not re.search(r"compose\b.*\b(up|start|restart)\b", ln), ln


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
    """Test 8's tunnel line (d), pasted after a line that set its carrier: the line reopens nothing otherwise."""
    return "T8=returned\n" + _one(_host_commands("### Test 8"), '[ "$T8" = returned ] && tunnel_down && tunnel_up')


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
        r = bench.run(bench.with_helpers("\n".join(("tunnel_up",'echo "RCUP=$?"', reopen_line(), 'echo "RC=$?"'))))
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
    r = bench.run(bench.with_helpers("\n".join((reopen_line(), 'echo "RC=$?"'))))
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
