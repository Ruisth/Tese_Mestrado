"""Cases for the finite proof's hook wrappers of tools/session (ADR 0011).

Under test, copied unmodified into the bench of ``test_session_drivers`` and
executed for real under its stubs: ``proof_hook_twins.sh`` (the harness's
``--twin-snapshot-cmd``), ``proof_hook_drained.sh`` (``--drain-cmd``),
``proof_fetch_sut_log.sh`` (the three ``--fetch-*-log-cmd`` hooks) and
``proof_restart_controller.sh`` (``--restart-cmd``, the fault). Each is run
the way the harness runs it: its template rendered with the harness's own
``format_collector_template`` / ``format_cmd_template`` and split with
``shlex.split`` into one argv, no shell, stdin from the null device, in the
environment the driver's host step would hand it (the stub ``.env`` exported,
``EGW_CLONE`` set). The bench is reused as it stands - the real
``local_export``, this interpreter as the venv, the ssh and scp stubs that run
guest commands on this machine against a fake guest root - and on top of it
this module installs the section 6.1 helper stub extended with the runbook's
own ``keep`` (read from the runbook when the test runs), a guest ``docker``
that holds the controller container's state on disk and answers the two
stored multi-session logs within the bounds it is given and the events (the
daemon's bounded history of 256 and its live stream, the fault's kill, die
and start among them), a guest ``date`` on a steady clock, and a ``$REC``
whose ``snap`` records its argv and is write-once like the real one. The
events recorder is started by the driver's own guest command
(``events_recorder_script`` of proof.sh, rendered as the driver renders it)
and runs as the unit the bench's ``systemd-run`` and ``systemctl`` stubs
keep in the background.

What these cases show is the wrappers' own behaviour: the byte-stable lines
the harness classifies, the write-once files, the D2 rule ("the log was NOT
read on the guest ... neither observed nor excluded") applied to a failed
and to an empty read, with the guest's reason kept in the capsule, the two
logs bounded to the run on the guest clock (an earlier session's lines,
an old A5 line on the same device among them, left out and witnessed; a
read the daemon did not bound, or a line without a stamp, refused), the
events captured continuously and judged (past the daemon's bounded history;
a CLI that ended by itself with status 0, a restarted daemon, a CLI that
warned, a stream that fell silent, a missing fault event: never complete;
a fault-free run: no fault event demanded), the SIGKILL-then-start sequence
with both guest readings in the record and both instants in the manifest's
500-character ``stderr_tail`` (the restart hook is run by
``_execute_restart_cmd`` itself, under a guest whose fault-time stderr
passes through, as compose's does), and a helper file that cannot be loaded
ending every hook before it touches the guest. They say nothing about a
real broker, controller, docker engine, guest or network: that docker
25.0.9 and compose 2.26.0 take '--since'/'--until' in epoch seconds, that
the daemon serves its replay and live stream under one lock and that the
CLI answers 0 when the stream is closed are for the next authorised
session to confirm.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the session drivers are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)

from test_session_drivers import EXPECT_SERVICES, ITEST_HELPERS, Bench, _write, report  # noqa: E402

from test_proof_evaluator import D1, _a5_line  # noqa: E402

from egw_experiments import proof_evaluator as pe  # noqa: E402
from egw_experiments import run as run_mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPO_ROOT / "docs" / "setup" / "qemu_integrated_gateway.md"
PROOF_SH = REPO_ROOT / "tools" / "session" / "proof.sh"
HOOKS = ("proof_hook_twins.sh", "proof_hook_drained.sh", "proof_fetch_sut_log.sh",
         "proof_restart_controller.sh", "proof_events_recorder.sh")
RID = "proof-adr0011-r01"
SEED = "7"
GUEST_T0 = "1700000000"
DITTO = "http://127.0.0.1:8080"

# --------------------------------------------------------------------------
# The runbook's own 'keep', read when the test runs
# --------------------------------------------------------------------------


def runbook_helper_body() -> str:
    """The body of the 6.1 heredoc, found as regen_helpers.py finds it."""
    lines = RUNBOOK.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.startswith("host$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "EOF")
    return "\n".join(lines[start + 1:end]) + "\n"


def runbook_function(name: str) -> str:
    """One shell function of the heredoc, from its `name() {` line to the
    first line that is exactly `}`."""
    body = runbook_helper_body().splitlines()
    start = next(i for i, line in enumerate(body) if line.startswith(f"{name}() {{"))
    end = next(i for i in range(start, len(body)) if body[i] == "}")
    return "\n".join(body[start:end + 1]) + "\n"


def proof_function(name: str) -> str:
    """One shell function of proof.sh, from its `name() {` line to the first
    line that is exactly `}` (the driver's own guest commands, run here as
    the driver renders them)."""
    lines = PROOF_SH.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}() {{"))
    end = next(i for i in range(start, len(lines)) if lines[i] == "}")
    return "\n".join(lines[start:end + 1]) + "\n"


# --------------------------------------------------------------------------
# Stubs of this module
# --------------------------------------------------------------------------

# The stub guest's clock (the bench log's anchor file): STEADY, from a real
# anchor, read by the guest's stub `date`, the docker stub's events and
# logs and the cases alike. The WSL2 host's wall clock is stepped backwards
# by 2-3 s about every 30 s (LOG.md), which would reorder the guest instants
# the events capture compares (the stop request, the closing witness) by
# the bench's accident, never by the code under test.


def _clock_anchor(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        pass
    anchor = {"epoch0": time.time(), "mono0": time.monotonic()}
    try:
        with open(path, "x", encoding="utf-8") as fh:
            json.dump(anchor, fh)
    except FileExistsError:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return anchor


def steady_ns(path):
    """The stub guest's clock, in nanoseconds since the epoch."""
    anchor = _clock_anchor(path)
    return int((anchor["epoch0"] + (time.monotonic() - anchor["mono0"])) * 1e9)


STEADY_CLOCK = ("import json, time\n\n" + inspect.getsource(_clock_anchor) + "\n\n" + inspect.getsource(steady_ns)
                + "\n\ndef now_ns():\n    return steady_ns(os.environ['EGW_STUB_LOG'] + '.clock')\n")

DATE_STUB = '''#!/usr/bin/env python3
"""Stub date of the stub guest: the bench's steady clock, in the forms the
guest scripts ask for ('date +%s', 'date -u +%Y-%m-%dT%H:%M:%SZ')."""
import os
import sys
from datetime import datetime, timezone
@@CLOCK@@

fmt = "%a %b %e %H:%M:%S UTC %Y"
for arg in sys.argv[1:]:
    if arg.startswith("+"):
        fmt = arg[1:]
    elif arg != "-u":
        print("stub date: unsupported argument %r" % arg, file=sys.stderr)
        sys.exit(1)
ns = now_ns()
now = datetime.fromtimestamp(ns / 1e9, timezone.utc)
print(now.strftime(fmt.replace("%s", str(ns // 10 ** 9))))
'''.replace("@@CLOCK@@", STEADY_CLOCK)

# 'docker events' of the stub guest, shared with the proof driver's docker
# stub (test_proof_driver): the daemon's bounded history (the last 256
# events, as Docker documents it) and the live stream. The events the cases
# (and this module's kill and start) put on the guest are kept, in order, in
# LOG.events-store; a history query (--until) answers the last 256 of them
# within its bounds, the container filter applied after that buffer, as the
# r03 copy suggests the daemon does; a follow (no --until) replays that
# history from --since and then streams, as it is written, every event added
# to the store, with a healthcheck exec event of the broker every 0.1 s as
# the stream's heartbeat, each as one JSON object the way '{{json .}}'
# prints it, until the CLI is ended by a signal. Steered through
# EGW_STUB_FAIL - 'events-cli-fails' (the CLI cannot reach the daemon: stderr
# and exit 1 at once), 'events-silent' (the CLI runs and receives nothing),
# 'events-stderr' (the CLI warns on stderr and goes on) - and through
# EGW_STUB_EVENTS_EOF_AFTER (the daemon closes the stream after that many
# heartbeats: the CLI exits 0 by itself) and EGW_STUB_EVENTS_QUIET_AFTER (no
# heartbeat after that many, the CLI still running). A follow ends by itself
# after EGW_STUB_EVENTS_LIFETIME_S (300 s), so a case that fails leaves no
# stream behind. The host stub defines now_ns(), its guest clock.
EVENTS_STUB = r'''
EVENTS_STORE = os.environ["EGW_STUB_LOG"] + ".events-store"
HISTORY_LIMIT = 256
EVENT_NS = 10 ** 9


def stored_events():
    try:
        with open(EVENTS_STORE, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        return []


def store_event(action, name, cid, **attributes):
    ns = now_ns()
    event = {"status": action, "id": cid, "from": f"stub/{name}:1", "Type": "container", "Action": action,
             "Actor": {"ID": cid, "Attributes": {"image": f"stub/{name}:1", "name": name, **attributes}},
             "scope": "local", "time": ns // EVENT_NS, "timeNano": ns}
    with open(EVENTS_STORE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, separators=(",", ":")) + "\n")
    return event


def emit_event(event):
    sys.stdout.write(json.dumps(event, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def docker_events(args):
    def opt(name):
        return args[args.index(name) + 1] if name in args else None

    if fails("events-cli-fails"):
        print("Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?",
              file=sys.stderr)
        sys.exit(1)
    since, until = opt("--since"), opt("--until")
    wanted = opt("--filter")
    current = stored_events()
    history = [e for e in current if since is None or e["timeNano"] >= int(since) * EVENT_NS][-HISTORY_LIMIT:]
    if until is not None:
        for event in history:
            if event["timeNano"] >= (int(until) + 1) * EVENT_NS:
                continue
            if wanted and wanted.startswith("container=") \
                    and event["Actor"]["Attributes"].get("name") != wanted.partition("=")[2]:
                continue
            emit_event(event)
        sys.exit(0)
    started = time.monotonic()
    lifetime = float(os.environ.get("EGW_STUB_EVENTS_LIFETIME_S", "300"))
    if fails("events-silent"):
        while time.monotonic() - started < lifetime:
            time.sleep(0.1)
        sys.exit(0)
    for event in history:
        emit_event(event)
    if fails("events-stderr"):
        print("WARNING: stub: the events stream skipped a message", file=sys.stderr, flush=True)
    seen = len(current)
    eof_after = int(os.environ.get("EGW_STUB_EVENTS_EOF_AFTER", "0"))
    quiet_after = int(os.environ.get("EGW_STUB_EVENTS_QUIET_AFTER", "0"))
    beats = 0
    cid = "00" + "a" * 62
    while time.monotonic() - started < lifetime:
        current = stored_events()
        for event in current[seen:]:
            emit_event(event)
        seen = len(current)
        if not quiet_after or beats < quiet_after:
            ns = now_ns()
            action = ("exec_create", "exec_start", "exec_die")[beats % 3] + ": /bin/sh -c mosquitto_sub -t $SYS/# -C 1"
            emit_event({"status": action, "id": cid, "from": "stub/egw-mosquitto-1:1", "Type": "container",
                        "Action": action, "Actor": {"ID": cid, "Attributes": {"name": "egw-mosquitto-1"}},
                        "scope": "local", "time": ns // EVENT_NS, "timeNano": ns})
        beats += 1
        if eof_after and beats >= eof_after:
            sys.exit(0)
        time.sleep(0.1)
    sys.exit(0)
'''

DOCKER_STUB = r'''#!/usr/bin/env python3
"""Stub docker for the proof hooks: the controller container, with its state
on disk, the broker and controller logs, the events, the kill and the
compose start. The two logs are the stored multi-session logs a case writes
(LOG.broker-log, LOG.controller-log; a default of the run otherwise), read
as docker reads them: '--since' and '--until' in whole seconds of the stamp
of each line, with the daemon's own rule since Docker 23: '--since' is
applied only until the first line at or after it, every later line passes
(the guest clock steps back), and the read ends at the first line past
'--until'. What the tests steer through EGW_STUB_FAIL: a log read that
fails or that answers nothing, a daemon that ignores the bounds
('logs-ignore-since'), a line without a stamp in the answer
('log-unstamped'), a kill or a start that is refused, a start without
effect, a start that writes past the harness's stderr budget, an inspect
that does not answer; the events as EVENTS_STUB says. The kill and the start
add the daemon's kill (signal 9), die and start events to the events."""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

STATE = os.environ["EGW_STUB_LOG"] + ".proof-docker.json"
failures = f",{os.environ.get('EGW_STUB_FAIL', '')},"
FIRST_ID = "0f" * 32
STAMP = re.compile(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?Z ")
@@CLOCK@@


def fails(token):
    return f",{token}," in failures


def load():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"id": FIRST_ID, "started": "2026-09-25T10:00:00.100000000Z",
                "status": "running", "starts": 0}


def save(state):
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def log(line):
    with open(os.environ["EGW_STUB_LOG"] + ".proof-dockerlog", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


@@EVENTS@@


def stored_log(kind, default):
    try:
        with open(os.environ["EGW_STUB_LOG"] + f".{kind}-log", encoding="utf-8") as fh:
            return fh.read().splitlines()
    except OSError:
        return default


def bounded(lines):
    """The lines within --since/--until, by the second of each line's stamp
    (after the compose prefix and an ESC[2K), as the daemon bounds them:
    '--since' only until the first line at or after it (moby's log
    forwarder), the read ended at the first line past '--until'."""
    since = args[args.index("--since") + 1] if "--since" in args else None
    until = args[args.index("--until") + 1] if "--until" in args else None
    if fails("logs-ignore-since"):
        since = None
    out = []
    for line in lines:
        bare = re.sub(r"^mosquitto-\d+ *\| ", "", line.replace("\x1b[2K", "", 1))
        m = STAMP.match(bare)
        if m:
            at = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            if since is not None and at < int(since):
                continue
            since = None
            if until is not None and at > int(until):
                break
        out.append(line)
    if fails("log-unstamped") and "--since" in args:
        out.insert(len(out) // 2, "a line of the log without a stamp" if not out or "mosquitto" not in out[0]
                   else "mosquitto-1  | a line of the log without a stamp")
    return out


args = sys.argv[1:]
compose = False
while args and (args[0] == "compose" or args[0] == "--env-file"):
    if args[0] == "compose":
        compose = True
        args = args[1:]
    else:
        args = args[2:]
state = load()
log(("compose " if compose else "") + " ".join(args))
cmd = args[0] if args else ""

if cmd == "logs" and fails("witness-fails") and "--until" in args and "--since" not in args:
    # The exclusion witness's read (only '--until RUN_T0'), refused.
    print("Error response from daemon: stub witness read refused", file=sys.stderr)
    sys.exit(1)
if compose and cmd == "logs":
    # The broker's log, as 'docker compose logs --no-color --timestamps
    # mosquitto' prints it: one connection line per second.
    if fails("compose-warns"):
        print("WARN stub compose warning: a line compose wrote to stderr", file=sys.stderr)
    if fails("broker-log-fails"):
        print("no such service: mosquitto", file=sys.stderr)
        sys.exit(1)
    if fails("broker-log-empty"):
        sys.exit(0)
    for line in bounded(stored_log("broker", [
            f"mosquitto-1  | 2026-09-25T10:00:0{i}.000000000Z 2026-09-25T10:00:0{i}: "
            "New connection from 172.18.0.7:52130 on port 8883." for i in range(3)])):
        print(line)
    sys.exit(0)
if compose and cmd == "start":
    if fails("start-fails"):
        print("Error response from daemon: stub start refused", file=sys.stderr)
        sys.exit(1)
    if fails("start-verbose"):
        # A guest that writes more than the harness keeps of the hook's
        # stderr (500 characters) between the two readings: eight warning
        # lines of some 80 characters each, before the progress lines.
        for i in range(8):
            print(f"WARN[0000] stub compose warning {i}: a line the guest wrote to stderr during the fault",
                  file=sys.stderr)
    if not fails("start-no-effect"):
        # A 'start' after a 'kill' keeps the container OBJECT: the same id,
        # a later StartedAt.
        state["starts"] += 1
        state["started"] = f"2026-09-25T10:05:{state['starts']:02d}.200000000Z"
        state["status"] = "running"
        store_event("start", "egw-controller-1", state["id"])
    save(state)
    # Compose v2 prints its progress on STDERR, where the ssh session relays
    # it into the hook's own stderr and so into the manifest's tail.
    print(" Container egw-controller-1  Starting", file=sys.stderr)
    print(" Container egw-controller-1  Started", file=sys.stderr)
    sys.exit(0)
if compose:
    print(f"stub docker compose: nothing to do for {cmd!r}", file=sys.stderr)
    sys.exit(1)

if cmd == "logs":
    # The controller container's log: the controller logs its JSON lines to
    # STDERR (logging_config.py), and 'docker logs' replays each stream on
    # its own descriptor, so a reader that keeps only stdout reads nothing.
    if fails("controller-log-fails"):
        print("Error: No such container: egw-controller-1", file=sys.stderr)
        sys.exit(1)
    if fails("controller-log-empty"):
        sys.exit(0)
    default = [f"2026-09-25T10:00:0{i}.500000000Z "
               + json.dumps({"ts": f"2026-09-25T10:00:0{i}.500Z", "level": "INFO",
                             "logger": "egw_controller.mqtt", "message": message})
               for i, message in enumerate(("MQTT connected", "MQTT subscription granted; bridge ready"))]
    for line in bounded(stored_log("controller", default)):
        print(line, file=sys.stderr)
    sys.exit(0)
if cmd == "events":
    docker_events(args)
if cmd == "kill":
    if fails("kill-fails"):
        print("Error response from daemon: stub kill refused", file=sys.stderr)
        sys.exit(1)
    state["status"] = "exited"
    save(state)
    store_event("kill", "egw-controller-1", state["id"], signal="9")
    store_event("die", "egw-controller-1", state["id"], exitCode="137")
    print("egw-controller-1")
    sys.exit(0)
if cmd == "inspect":
    if fails("inspect-fails"):
        print("Error response from daemon: context deadline exceeded", file=sys.stderr)
        sys.exit(1)
    template = args[args.index("-f") + 1] if "-f" in args else "{{.Id}}"
    started = "" if fails("inspect-empty-started") else state["started"]
    print(template.replace("{{.Id}}", state["id"]).replace("{{.State.StartedAt}}", started)
          .replace("{{.State.Status}}", state["status"]))
    sys.exit(0)
print(f"stub docker: nothing to do for {cmd!r}", file=sys.stderr)
sys.exit(1)
'''.replace("@@CLOCK@@", STEADY_CLOCK).replace("@@EVENTS@@", EVENTS_STUB)

REC_STUB = r'''#!/usr/bin/env python3
"""Stub of egw_experiments.itest_reconcile for the proof hooks: 'snap' only.
Its argv is recorded, the snapshot it writes is shaped like the real one and
the file is write-once, as the real save_new makes it ('x' mode)."""
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["EGW_STUB_LOG"] + ".rec", "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\n")
if not args or args[0] != "snap":
    print("stub rec: only 'snap' is answered here", file=sys.stderr)
    sys.exit(2)
if ",rec-snap," in f",{os.environ.get('EGW_STUB_FAIL', '')},":
    print("error: GET thing stub-device failed: stub", file=sys.stderr)
    sys.exit(1)


def opt(name):
    return args[args.index(name) + 1] if name in args else None


prefix, label, seed, like = opt("--prefix"), opt("--label"), opt("--seed"), opt("--like")
if seed is not None:
    seed_value = int(seed)
    devices = {"stub-device": {"device_type": "smartwatch", "exists": True,
                               "ingestion": {"last_run_id": None, "last_seq": None, "accepted_count": 0}}}
else:
    seed_value = None
    with open(f"{prefix}.twins.{like or 'before'}.json", encoding="utf-8") as fh:
        devices = json.load(fh)["devices"]
snap = {"label": label, "seed": seed_value, "devices": devices}
path = f"{prefix}.twins.{label}.json"
try:
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(snap, indent=2) + "\n")
except FileExistsError:
    print(f"error: refusing to overwrite {path}", file=sys.stderr)
    sys.exit(1)
print(json.dumps(snap, indent=2))
'''


# --------------------------------------------------------------------------
# The bench, extended for the hooks
# --------------------------------------------------------------------------


class Hooks:
    """The bench with the helper stub extended by the runbook's `keep`, the
    docker of this module on the guest side and the recording `$REC`."""

    def __init__(self, bench: Bench) -> None:
        self.bench = bench
        self.helpers = bench.home / "egw-tcg" / "itest-helpers.sh"
        _write(self.helpers, ITEST_HELPERS + "\n" + runbook_function("keep"))
        _write(bench.guest_bin / "docker", DOCKER_STUB, executable=True)
        _write(bench.guest_bin / "date", DATE_STUB, executable=True)
        _write(bench.bin / "rec", REC_STUB, executable=True)
        self.prefix = bench.home / "egw-tcg" / "itest"
        self.run_dir = bench.tmp / "raw" / RID
        self.sut_logs = self.run_dir / "logs" / "sut"
        self.sut_logs.mkdir(parents=True, exist_ok=True)
        self.clock = str(bench.log) + ".clock"

    # -- the stub guest's steady clock and its events ----------------------
    def now(self) -> int:
        """The stub guest's clock, whole seconds."""
        return steady_ns(self.clock) // 10 ** 9

    def store_events(self, *events: dict) -> None:
        """Events the daemon emits now (LOG.events-store, in order)."""
        with open(str(self.bench.log) + ".events-store", "a", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, separators=(",", ":")) + "\n")

    def events_dir(self, run_id: str = RID) -> Path:
        """The run's capture directory on the stub guest."""
        return self.bench.guest_root / "tmp" / f"egw-events-{run_id}"

    def start_recorder(self, run_id: str = RID, **overrides) -> subprocess.CompletedProcess:
        """The driver's own 'events-recorder-start' guest command (proof.sh's
        events_recorder_script, run as the driver renders it), sent to the
        stub guest as gx sends it."""
        recorder = self.bench.drivers / "proof_events_recorder.sh"
        rendered = subprocess.run(
            ["bash", "-c", proof_function("events_recorder_script") + "events_recorder_script"],
            env={**os.environ, "RECORDER": str(recorder), "RID": run_id,
                 "RECORDER_SHA": hashlib.sha256(recorder.read_bytes()).hexdigest()},
            capture_output=True, text=True, check=True)
        return self.run_argv(["ssh", "-o", "BatchMode=yes", "egw@127.0.0.1", rendered.stdout], **overrides)

    def recorder_pid(self, run_id: str = RID) -> int | None:
        path = Path(f"{self.bench.log}.unit-egw-events-{run_id}.pid")
        return int(path.read_text(encoding="utf-8")) if path.exists() else None

    def recorder_running(self, run_id: str = RID) -> bool:
        return self.run_argv([str(self.bench.guest_bin / "systemctl"), "is-active", "-q",
                              f"egw-events-{run_id}"]).returncode == 0

    def stop_recorder(self, run_id: str = RID) -> None:
        """What a case leaves running is ended (never a stream behind it)."""
        pid = self.recorder_pid(run_id)
        if pid is not None:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def wait_for(self, predicate, limit_s: float = 30.0) -> None:
        t0 = time.monotonic()
        while time.monotonic() - t0 < limit_s:
            if predicate():
                return
            time.sleep(0.05)
        raise AssertionError("the condition did not come about in time")

    def captured(self, run_id: str = RID) -> list[dict]:
        path = self.events_dir(run_id) / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.endswith("}")]

    # -- the environment the driver's host step hands a hook --------------
    def env(self, **overrides) -> dict:
        values = {"MOSQUITTO_SIMULATOR_PASSWORD": "stub-simulator-password", "EGW_CLONE": str(REPO_ROOT)}
        values.update(overrides)
        return self.bench.env(**values)

    def template(self, hook: str, *args: str) -> str:
        return " ".join(["bash", str(self.bench.drivers / hook), *args])

    def run_argv(self, argv: list[str], **overrides) -> subprocess.CompletedProcess:
        return subprocess.run(argv, env=self.env(**overrides), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120, start_new_session=True)

    def run_hook(self, template: str, dest: Path, **overrides) -> subprocess.CompletedProcess:
        """One item-18 hook, as execute_collector_hook renders and splits it."""
        cmd = run_mod.format_collector_template(template, RID, duration_s=300, dest=dest,
                                                expect_services=list(EXPECT_SERVICES))
        return self.run_argv(shlex.split(cmd, posix=True), **overrides)

    def run_restart(self, **overrides) -> subprocess.CompletedProcess:
        """The restart hook, as _execute_restart_cmd renders and splits it."""
        cmd = run_mod.format_cmd_template(self.template("proof_restart_controller.sh", "{run_id}"), RID)
        return self.run_argv(shlex.split(cmd, posix=True), **overrides)

    def run_restart_by_the_harness(self, monkeypatch, **overrides) -> dict:
        """The restart hook run by _execute_restart_cmd itself, in the
        driver's environment: the manifest's restart record, whose
        ``stderr_tail`` (the LAST 500 characters of the hook's stderr) is the
        only copy of that stderr the harness keeps - no hook-*.stderr.txt is
        written for the restart hook."""
        for key, val in self.env(**overrides).items():
            monkeypatch.setenv(key, val)
        record: dict = {}
        run_mod._execute_restart_cmd(self.template("proof_restart_controller.sh", "{run_id}"), RID, record)
        return record

    # -- what the stubs recorded ------------------------------------------
    def ssh_commands(self) -> list[str]:
        if not self.bench.log.exists():
            return []
        return [line for line in self.bench.log.read_text(encoding="utf-8").splitlines()
                if line.startswith("ssh ")]

    def docker_calls(self) -> list[str]:
        path = Path(str(self.bench.log) + ".proof-dockerlog")
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def rec_calls(self) -> list[list[str]]:
        path = Path(str(self.bench.log) + ".rec")
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def restart_record(self) -> dict[str, list[str]]:
        """The write-once record, as {phase: [key=value lines]}."""
        phases: dict[str, list[str]] = {}
        current = "head"
        for line in (self.prefix / f"{RID}.restart.txt").read_text(encoding="utf-8").splitlines():
            if line.startswith("phase="):
                current = line.partition("=")[2]
                phases[current] = []
            else:
                phases.setdefault(current, []).append(line)
        return phases


@pytest.fixture
def hooks(tmp_path: Path):
    bench = Hooks(Bench(tmp_path))
    yield bench
    # A recorder unit a case left running is ended with its stream.
    for pid_file in tmp_path.glob("stub.log.unit-egw-events-*.pid"):
        try:
            os.killpg(int(pid_file.read_text(encoding="utf-8")), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, ValueError):
            pass


def value(lines: list[str], key: str) -> str:
    return next(line.partition("=")[2] for line in lines if line.startswith(key + "="))


# --------------------------------------------------------------------------
# The helper stub's 'keep' is the runbook's
# --------------------------------------------------------------------------


def test_the_stub_helper_keep_is_the_runbooks_and_is_write_once(hooks):
    keep = runbook_function("keep")
    assert keep in RUNBOOK.read_text(encoding="utf-8")
    assert keep in hooks.helpers.read_text(encoding="utf-8")
    source = hooks.bench.tmp / "source.txt"
    source.write_text("kept bytes\n", encoding="utf-8")
    target = hooks.bench.tmp / "target.txt"
    script = f'. "$HOME/egw-tcg/itest-helpers.sh" && keep {shlex.quote(str(source))} {shlex.quote(str(target))}'
    first = hooks.run_argv(["bash", "-c", script])
    assert first.returncode == 0, report(first)
    second = hooks.run_argv(["bash", "-c", script])
    assert second.returncode == 1, report(second)
    assert f"STOP: keep: {target} exists - NOT overwritten" in second.stderr
    assert target.read_text(encoding="utf-8") == "kept bytes\n"


# --------------------------------------------------------------------------
# proof_hook_twins.sh (design 2.12 test 11)
# --------------------------------------------------------------------------


def test_hook_twins_writes_the_prefix_sibling_and_dest_write_once_with_the_plans_seed_and_like_before_for_after(hooks):
    template = hooks.template("proof_hook_twins.sh", "{run_id}", "{dest}", SEED)
    before_dest = hooks.run_dir / run_mod.TWIN_SNAPSHOT_FILES["twin_snapshot_before"]
    result = hooks.run_hook(template, before_dest)
    assert result.returncode == 0, report(result)
    # The runbook's own command line for 'before': the plan's seed, no --like.
    assert hooks.rec_calls() == [["snap", "--prefix", str(hooks.prefix / RID), "--label", "before",
                                  "--seed", SEED, "--ditto-url", DITTO]]
    sibling = hooks.prefix / f"{RID}.twins.before.json"
    assert sibling.read_bytes() == before_dest.read_bytes()
    snapshot = json.loads(before_dest.read_text(encoding="utf-8"))
    assert (snapshot["label"], snapshot["seed"]) == ("before", int(SEED))
    assert f"snapshot kept as {sibling} and {before_dest}" in result.stdout
    # The sibling is write-once: a second 'before' for the same run id takes
    # nothing and overwrites nothing.
    again = hooks.run_hook(template, hooks.bench.tmp / "elsewhere" / "twins.before.json")
    assert again.returncode == 1, report(again)
    assert f"STOP: proof_hook_twins: {sibling} exists - run id and label already used" in again.stderr
    assert len(hooks.rec_calls()) == 1
    assert not (hooks.bench.tmp / "elsewhere" / "twins.before.json").exists()
    # 'after' is taken --like before, with no seed of its own, and the label
    # is read from DEST's name.
    after_dest = hooks.run_dir / run_mod.TWIN_SNAPSHOT_FILES["twin_snapshot_after"]
    result = hooks.run_hook(template, after_dest)
    assert result.returncode == 0, report(result)
    assert hooks.rec_calls()[-1] == ["snap", "--prefix", str(hooks.prefix / RID), "--label", "after",
                                     "--like", "before", "--ditto-url", DITTO]
    after = json.loads(after_dest.read_text(encoding="utf-8"))
    assert (after["label"], after["seed"]) == ("after", None)
    assert (hooks.prefix / f"{RID}.twins.after.json").read_bytes() == after_dest.read_bytes()
    # DEST is write-once too, and a DEST that exists stops the hook BEFORE
    # any snapshot is taken: no sibling appears for that run id.
    other = hooks.bench.tmp / "other-run" / "twins.before.json"
    _write(other, "an earlier file\n")
    template_other = hooks.template("proof_hook_twins.sh", "other-r01", "{dest}", SEED)
    result = hooks.run_hook(template_other, other)
    assert result.returncode == 1, report(result)
    assert f"STOP: proof_hook_twins: {other} exists - NOT overwritten" in result.stderr
    assert not (hooks.prefix / "other-r01.twins.before.json").exists()
    assert len(hooks.rec_calls()) == 2
    assert other.read_text(encoding="utf-8") == "an earlier file\n"


def test_hook_twins_writes_no_dest_when_the_snapshot_fails_and_refuses_what_it_cannot_read(hooks):
    template = hooks.template("proof_hook_twins.sh", "{run_id}", "{dest}", SEED)
    dest = hooks.run_dir / "twins.before.json"
    failed = hooks.run_hook(template, dest, EGW_STUB_FAIL="rec-snap")
    assert failed.returncode == 1, report(failed)
    assert "STOP: proof_hook_twins: the before twin snapshot was not taken ($REC snap exited 1)" in failed.stderr
    assert f"{dest} was NOT written" in failed.stderr
    assert not dest.exists()
    assert not (hooks.prefix / f"{RID}.twins.before.json").exists()
    # 'after' without a 'before' sibling has no device set to derive from.
    after = hooks.run_hook(template, hooks.run_dir / "twins.after.json")
    assert after.returncode == 1, report(after)
    assert "twins.before.json is missing or empty: 'after' is taken --like before" in after.stderr
    assert len(hooks.rec_calls()) == 1
    # A DEST whose name carries no label, and a seed that is not a whole
    # number, are refused before anything is read.
    unnamed = hooks.run_hook(template, hooks.run_dir / "twins.json")
    assert unnamed.returncode == 2, report(unnamed)
    assert "neither twins.before.json nor twins.after.json" in unnamed.stderr
    bad_seed = hooks.run_hook(hooks.template("proof_hook_twins.sh", "{run_id}", "{dest}", "seven"), dest)
    assert bad_seed.returncode == 2, report(bad_seed)
    assert "SEED 'seven' is not a whole number" in bad_seed.stderr
    assert len(hooks.rec_calls()) == 1
    assert not dest.exists()


# --------------------------------------------------------------------------
# proof_hook_drained.sh (design 2.12 test 12)
# --------------------------------------------------------------------------


def test_hook_drained_prints_the_helpers_lines_unchanged_and_exits_as_the_helper(hooks):
    template = hooks.template("proof_hook_drained.sh", "{run_id}")
    unused = hooks.run_dir / "drain-has-no-dest"
    quiet = hooks.run_hook(template, unused, DRAIN_QUIET_S="490")
    assert quiet.returncode == 0, report(quiet)
    # The stub helper's quiet line, byte for byte, starting the line: what
    # the harness classifies (run.py DRAIN_QUIET_LINE_PREFIX).
    assert "drained: queue_depth 0 and identical counters (stub observation)" in quiet.stdout.splitlines()
    assert run_mod.classify_drain_output(quiet.stdout + quiet.stderr, quiet.returncode) == "quiet"
    assert f"proof_hook_drained: {RID}: drained with DRAIN_QUIET_S=490 DRAIN_STEP_S=5 DRAIN_LIMIT_S=900" in quiet.stdout
    assert quiet.stderr == ""
    gave_up = hooks.run_hook(template, unused, EGW_STUB_FAIL="drained")
    assert gave_up.returncode == 1, report(gave_up)
    assert "STOP: drained: no quiet window" in gave_up.stderr.splitlines()
    assert run_mod.classify_drain_output(gave_up.stdout + gave_up.stderr, gave_up.returncode) == "gave-up"
    assert not unused.exists()


def test_hook_drained_refuses_a_quiet_window_below_130_s_and_a_value_that_is_not_seconds_before_polling(hooks):
    template = hooks.template("proof_hook_drained.sh", "{run_id}")
    unused = hooks.run_dir / "drain-has-no-dest"
    lowered = hooks.run_hook(template, unused, DRAIN_QUIET_S="100")
    assert lowered.returncode == 2, report(lowered)
    assert "DRAIN_QUIET_S=100 is below the runbook's 130 s ('Never lower it', 6.1): nothing was polled" in lowered.stderr
    assert "drained:" not in lowered.stdout
    unreadable = hooks.run_hook(template, unused, DRAIN_LIMIT_S="15m")
    assert unreadable.returncode == 2, report(unreadable)
    assert "DRAIN_LIMIT_S='15m' is not a whole number of seconds: nothing was polled" in unreadable.stderr
    assert "drained:" not in unreadable.stdout
    # Neither line was printed, which the harness records as a drain that
    # ended in error, never as a quiet window.
    assert run_mod.classify_drain_output(lowered.stdout + lowered.stderr, lowered.returncode) == "error"


# --------------------------------------------------------------------------
# proof_fetch_sut_log.sh (design 2.12 tests 13 and 14; the r03 closure, C)
# --------------------------------------------------------------------------

FETCH_KINDS = {"broker": "broker_log", "controller": "controller_log", "docker-events": "docker_events"}
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


def _fetch(hooks: Hooks, kind: str, since: str = GUEST_T0, *extra: str,
           **overrides) -> tuple[subprocess.CompletedProcess, Path]:
    dest = hooks.sut_logs / run_mod.SUT_LOG_FILES[FETCH_KINDS[kind]]
    template = hooks.template("proof_fetch_sut_log.sh", kind, "{dest}", since, *extra)
    return hooks.run_hook(template, dest, **overrides), dest


def _utc(epoch: int, fraction: str = "") -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + fraction + "Z"


@pytest.mark.parametrize("kind, token, exit_text, reason", [
    # A read that FAILED (ssh non-zero: the daemon's error on stderr, which
    # the controller read merges on the guest and so counts as bytes) and a
    # read that ANSWERED NOTHING (exit 0, empty) are both a log that was not
    # read: neither leaves a file. The daemon's reason, when there is one,
    # stays in the capsule either way. (The docker events are no longer one
    # read: their capture's failures are the cases of the recorder below.)
    ("broker", "broker-log-fails", r"ssh egw-tcg exit 1, 0 bytes", "no such service: mosquitto"),
    ("broker", "broker-log-empty", r"ssh egw-tcg exit 0, 0 bytes", None),
    ("controller", "controller-log-fails", r"ssh egw-tcg exit 1, [1-9][0-9]* bytes",
     "Error: No such container: egw-controller-1"),
    ("controller", "controller-log-empty", r"ssh egw-tcg exit 0, 0 bytes", None),
])
def test_fetch_sut_log_writes_no_dest_on_a_failed_or_empty_read_and_says_so(hooks, kind, token, exit_text, reason):
    result, dest = _fetch(hooks, kind, EGW_STUB_FAIL=token)
    assert result.returncode == 1, report(result)
    lines = result.stderr.splitlines()
    # The STOP line is the LAST line of stderr, whatever came before it.
    expected = (rf"STOP: proof_fetch_sut_log: the {kind} log was NOT read on the guest \({exit_text}\): "
                rf"what it would show is neither observed nor excluded - {re.escape(str(dest))} was NOT written")
    assert re.fullmatch(expected, lines[-1]), report(result)
    if reason is not None:
        assert reason in result.stderr, report(result)
    if kind == "controller" and reason is not None:
        # The controller read merges the daemon's stderr ON THE GUEST, so
        # its reason is in the output that is about to be removed: the hook
        # copies the last of it to stderr first, and the reason precedes
        # the STOP line.
        assert re.fullmatch(r"proof_fetch_sut_log: the controller read exited 1 after answering [1-9][0-9]* bytes; "
                            r"the last of them \(up to 400\) follow:", lines[-3]), report(result)
        assert lines[-2] == reason
    else:
        # Unmerged, the reason reaches stderr by itself; an empty answer has
        # nothing to excerpt.
        assert "after answering" not in result.stderr, report(result)
    assert not dest.exists()
    assert not Path(str(dest) + ".tmp").exists()
    assert hooks.ssh_commands(), "the read was attempted on the guest"


def test_fetch_sut_log_writes_dest_and_prints_its_line_count_and_sha256_on_a_read_that_was_made(hooks):
    result, dest = _fetch(hooks, "broker")
    assert result.returncode == 0, report(result)
    lines = dest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and all("New connection" in line for line in lines)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    assert f"proof_fetch_sut_log: broker: 3 line(s), {dest.stat().st_size} bytes, sha256 {sha}, written to {dest}" in result.stdout
    assert not Path(str(dest) + ".tmp").exists()
    # The read is test 5's - compose logs of the mosquitto service, without
    # colour and with timestamps, from the deployment directory - bounded on
    # the guest clock: from RUN_T0 to the guest's own clock read just before
    # it, both printed with what the bound left out (nothing here).
    until = re.search(r"until_guest_epoch=(\d+) ", result.stdout).group(1)
    assert hooks.docker_calls()[-1] == f"compose logs --no-color --timestamps --since {GUEST_T0} --until {until} mosquitto"
    assert any("cd " in line and "/opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env logs"
               in line for line in hooks.ssh_commands())
    assert (f"proof_fetch_sut_log: broker: bounds since_guest_epoch={GUEST_T0} ({_utc(int(GUEST_T0))}) "
            f"until_guest_epoch={until} ({_utc(int(until))}) first=2026-09-25T10:00:00.000000000Z "
            f"last=2026-09-25T10:00:02.000000000Z excluded_before_since_lines=0 excluded_sha256={EMPTY_SHA} "
            "outside=0 unstamped=0") in result.stdout
    assert abs(int(until) - hooks.now()) <= 5, "UNTIL is the guest's clock at the fetch"
    # DEST is write-once: the fetch that finds it stops without reading.
    reads = len(hooks.ssh_commands())
    again, _ = _fetch(hooks, "broker")
    assert again.returncode == 1, report(again)
    assert f"STOP: proof_fetch_sut_log: {dest} exists - NOT overwritten; nothing was read" in again.stderr
    assert len(hooks.ssh_commands()) == reads
    # The controller logs its JSON lines to stderr: the read merges the two
    # streams ON THE GUEST, so the lines reach DEST and ssh's own stderr
    # stays apart (and empty here).
    result, dest = _fetch(hooks, "controller")
    assert result.returncode == 0, report(result)
    until = re.search(r"until_guest_epoch=(\d+) ", result.stdout).group(1)
    assert f"docker logs --timestamps --since {GUEST_T0} --until {until} egw-controller-1 2>&1" in hooks.ssh_commands()[-1]
    entries = [json.loads(line.split(" ", 1)[1]) for line in dest.read_text(encoding="utf-8").splitlines()]
    assert [e["message"] for e in entries] == ["MQTT connected", "MQTT subscription granted; bridge ready"]
    assert result.stderr == ""


def _multi_session_logs(hooks: Hooks) -> dict:
    """A controller log and a broker log as the containers keep them across
    sessions: an earlier session three days ago (the controller's A5 line on
    the SAME device, whose received_monotonic_ns is of another boot), then
    this run's lines after RUN_T0. The broker's first line carries compose's
    ESC[2K, as r03's did."""
    now = hooks.now()
    run_t0 = now - 60
    old = now - 3 * 86400
    stamp = lambda epoch: _utc(epoch, ".250000000")  # noqa: E731
    old_controller = [
        f"{stamp(old)} " + json.dumps({"ts": _utc(old), "level": "INFO", "logger": "uvicorn", "message": "Uvicorn running"}),
        _a5_line(D1, 111_000, prefix=f"{stamp(old + 5)} "),
        f"{stamp(old + 6)} " + json.dumps({"ts": _utc(old + 6), "level": "INFO", "logger": "egw_controller.mqtt",
                                           "message": "MQTT subscription granted; bridge ready"}),
    ]
    run_controller = [
        f"{stamp(run_t0 + 1)} " + json.dumps({"ts": _utc(run_t0 + 1), "level": "INFO", "logger": "egw_controller.mqtt",
                                              "message": "MQTT connected"}),
        _a5_line(D1, 999_000_000_000, prefix=f"{stamp(run_t0 + 30)} "),
    ]
    old_broker = [f"\x1b[2Kmosquitto-1  | {stamp(old)} mosquitto version 2.0.18 starting",
                  f"mosquitto-1  | {stamp(old + 1)} New connection from 172.18.0.9:40000 on port 8883."]
    run_broker = [f"mosquitto-1  | {stamp(run_t0 + 2)} New connection from 172.18.0.7:52130 on port 8883.",
                  f"mosquitto-1  | {stamp(run_t0 + 40)} Client egw-controller closed its connection."]
    Path(str(hooks.bench.log) + ".controller-log").write_text("\n".join(old_controller + run_controller) + "\n", "utf-8")
    Path(str(hooks.bench.log) + ".broker-log").write_text("\n".join(old_broker + run_broker) + "\n", "utf-8")
    return {"run_t0": run_t0, "controller": (old_controller, run_controller), "broker": (old_broker, run_broker)}


@pytest.mark.parametrize("kind", ["controller", "broker"])
def test_the_two_logs_keep_the_runs_lines_only_and_record_what_they_leave_out(hooks, kind):
    logs = _multi_session_logs(hooks)
    old, run = logs[kind]
    result, dest = _fetch(hooks, kind, str(logs["run_t0"]))
    assert result.returncode == 0, report(result)
    # Only this run's lines: the earlier session - the A5 line of another
    # boot on the same device among them - never enters the run's copy.
    assert dest.read_text(encoding="utf-8").splitlines() == run
    # What the bound left out is recorded on the guest, never transferred:
    # its line count and the sha256 of exactly those lines.
    excluded = hashlib.sha256("".join(line + "\n" for line in old).encode("utf-8")).hexdigest()
    assert f"excluded_before_since_lines={len(old)} excluded_sha256={excluded} outside=0 unstamped=0" in result.stdout
    assert f"since_guest_epoch={logs['run_t0']} ({_utc(logs['run_t0'])})" in result.stdout
    assert "Uvicorn running" not in result.stdout + result.stderr and "version 2.0.18" not in result.stdout
    if kind == "controller":
        occurrences, notes = pe.a5_occurrences(dest.read_text(encoding="utf-8").splitlines())
        assert [o["identity"]["received_monotonic_ns"] for o in occurrences] == [999_000_000_000]
        assert [o["device_uuid"] for o in occurrences] == [D1]
        assert notes["subscription_granted_ts"] == []


@pytest.mark.parametrize("kind", ["controller", "broker"])
def test_a_read_the_daemon_did_not_bound_is_not_the_runs_log(hooks, kind):
    # '--since' was in r03's events read too: the bound is shown by the
    # lines themselves, never by the flag. A daemon that answers the whole
    # history is a read NOT bounded to the run: no file, and the old lines
    # are named by number and stamp only, never excerpted into the capsule.
    logs = _multi_session_logs(hooks)
    old, _ = logs[kind]
    result, dest = _fetch(hooks, kind, str(logs["run_t0"]), EGW_STUB_FAIL="logs-ignore-since")
    assert result.returncode == 1, report(result)
    assert not dest.exists() and not Path(str(dest) + ".tmp").exists()
    assert f"of which {len(old)} lie outside [{_utc(logs['run_t0'])}, " in result.stderr, report(result)
    assert "first: line 1, stamp " in result.stderr
    assert result.stderr.splitlines()[-1].startswith(
        f"STOP: proof_fetch_sut_log: the {kind} log was NOT read as bounded to the run [{_utc(logs['run_t0'])}, ")
    assert result.stderr.splitlines()[-1].endswith(f"- {dest} was NOT written")
    assert "Uvicorn running" not in result.stderr and "version 2.0.18" not in result.stderr
    assert "written to" not in result.stdout


@pytest.mark.parametrize("kind", ["controller", "broker"])
def test_a_line_without_a_stamp_is_a_read_not_bounded_to_the_run(hooks, kind):
    result, dest = _fetch(hooks, kind, EGW_STUB_FAIL="log-unstamped")
    assert result.returncode == 1, report(result)
    assert "of which 0 lie outside" in result.stderr and "and 1 carry no timestamp (first: line " in result.stderr
    assert "was NOT read as bounded to the run" in result.stderr.splitlines()[-1]
    assert not dest.exists()


def _stepped_back_logs(hooks: Hooks, behind: int) -> dict:
    """A log whose guest clock stepped back across RUN_T0 AFTER the first line
    of the run: the daemon's since check ended at that line, so the stepped
    line is answered (r03's controller log: 21:11:03.66 then 21:11:02.69)."""
    now = hooks.now()
    run_t0 = now - 60
    old = now - 3 * 86400
    stamp = lambda epoch: _utc(epoch, ".250000000")  # noqa: E731
    msg = lambda epoch, text: f"{stamp(epoch)} " + json.dumps(  # noqa: E731
        {"ts": _utc(epoch), "level": "INFO", "logger": "egw_controller.mqtt", "message": text})
    old_lines = [msg(old, "an earlier session")]
    run_lines = [msg(run_t0, "MQTT connected"), msg(run_t0 - behind, "stepped back"), msg(run_t0 + 5, "later")]
    Path(str(hooks.bench.log) + ".controller-log").write_text("\n".join(old_lines + run_lines) + "\n", "utf-8")
    return {"run_t0": run_t0, "old": old_lines, "run": run_lines}


def test_a_line_stepped_back_across_run_t0_after_the_first_is_the_runs_and_counted_apart(hooks):
    # Review of 2026-09-29: the daemon passes every line after the first one
    # at or after '--since', and the guest clock steps back by up to 3 s.
    logs = _stepped_back_logs(hooks, behind=2)
    result, dest = _fetch(hooks, "controller", str(logs["run_t0"]))
    assert result.returncode == 0, report(result)
    assert dest.read_text(encoding="utf-8").splitlines() == logs["run"]
    assert "outside=0 unstamped=0 stepped_back_before_since=1" in result.stdout
    assert "an earlier session" not in dest.read_text(encoding="utf-8")


def test_a_line_older_than_the_clock_step_band_still_fails_the_read(hooks):
    logs = _stepped_back_logs(hooks, behind=10)
    result, dest = _fetch(hooks, "controller", str(logs["run_t0"]))
    assert result.returncode == 1, report(result)
    assert "of which 1 lie outside" in result.stderr and not dest.exists()


@pytest.mark.parametrize("kind", ["controller", "broker"])
def test_a_witness_read_that_failed_is_reported_unknown_not_counted(hooks, kind):
    # Review of 2026-09-29: the witness's own exit status is read, and the
    # count and hash of an error message are never reported as what the
    # bound left out.
    logs = _multi_session_logs(hooks)
    result, dest = _fetch(hooks, kind, str(logs["run_t0"]), EGW_STUB_FAIL="witness-fails")
    assert result.returncode == 0, report(result)
    assert "excluded_before_since_lines=unknown excluded_sha256=unknown " in result.stdout
    assert result.stdout.split("bounds ", 1)[1].split("
", 1)[0].endswith(" excluded_read_rc=1,1")
    assert dest.read_text(encoding="utf-8").splitlines() == logs[kind][1]


def test_the_brokers_witness_leaves_compose_stderr_apart_as_the_read_does(hooks):
    logs = _multi_session_logs(hooks)
    old, _ = logs["broker"]
    result, _ = _fetch(hooks, "broker", str(logs["run_t0"]), EGW_STUB_FAIL="compose-warns")
    assert result.returncode == 0, report(result)
    excluded = hashlib.sha256("".join(line + "\n" for line in old).encode("utf-8")).hexdigest()
    assert f"excluded_before_since_lines={len(old)} excluded_sha256={excluded} " in result.stdout
    assert "WARN stub compose warning" in result.stderr


def test_fetch_refuses_arguments_it_cannot_use_before_the_guest_is_reached(hooks):
    cases = [
        (("broker", "{dest}", "now"), "RUN_T0 'now' is not a whole number of seconds"),
        (("journal", "{dest}", GUEST_T0), "KIND 'journal' is not broker, controller or docker-events: nothing was read"),
        (("docker-events", "{dest}", GUEST_T0), "usage: proof_fetch_sut_log.sh"),
        (("broker", "{dest}", GUEST_T0, "{run_id}"), "usage: proof_fetch_sut_log.sh"),
        (("docker-events", "{dest}", GUEST_T0, "../x"), "RUN_ID '../x' is not a plain run id"),
        (("docker-events", "{dest}", GUEST_T0, "{run_id}", "kill;die"), "EXPECTED 'kill;die' is not a comma-separated list"),
    ]
    for args, says in cases:
        result = hooks.run_hook(hooks.template("proof_fetch_sut_log.sh", *args), hooks.sut_logs / "docker-events.log")
        assert result.returncode == 2, report(result)
        assert says in result.stderr, (args, report(result))
    assert hooks.ssh_commands() == []


# --- the docker events: the recorder the driver starts, and the fetch that stops and judges it


def _events_fetch(hooks: Hooks, run_t0: int, expected: str | None = "kill,die,start",
                  **overrides) -> tuple[subprocess.CompletedProcess, Path]:
    extra = ("{run_id}",) + ((expected,) if expected else ())
    return _fetch(hooks, "docker-events", str(run_t0), *extra, **overrides)


def _run_t0(start: subprocess.CompletedProcess) -> int:
    return int(re.search(r"^run_guest_t0=(\d+)$", start.stdout, re.M).group(1))


def _coverage(hooks: Hooks) -> dict[str, list[str]]:
    """The coverage record the fetch kept, as {key: [values]}."""
    out: dict[str, list[str]] = {}
    for line in (hooks.sut_logs / "docker-events.coverage.txt").read_text(encoding="utf-8").splitlines():
        key, _, rest = line.partition("=")
        out.setdefault(key, []).append(rest)
    return out


def test_the_recorders_start_says_when_it_is_ready_and_is_write_once(hooks):
    start = hooks.start_recorder()
    assert start.returncode == 0, report(start)
    t0 = _run_t0(start)
    d = hooks.events_dir()
    recorder = hooks.bench.drivers / "proof_events_recorder.sh"
    # The clone's recorder, written to the guest byte for byte and checked
    # there; the boot and daemon facts; the lifecycle up to readiness.
    assert (d / "recorder.sh").read_bytes() == recorder.read_bytes()
    assert f"recorder_sha256={hashlib.sha256(recorder.read_bytes()).hexdigest()}" in start.stdout
    facts = (d / "start-facts.txt").read_text(encoding="utf-8").splitlines()
    assert facts[0].startswith("boot_id=") and len(facts[0]) > len("boot_id=")
    assert facts[1:] == ["MainPID=321", "ExecMainStartTimestampMonotonic=4200000"]
    life = (d / "lifecycle.txt").read_text(encoding="utf-8").splitlines()
    assert [line.split()[0] for line in life] == ["start", "cli-start", "ready"]
    since = int(re.search(r"^recorder_since_guest_epoch=(\d+)$", start.stdout, re.M).group(1))
    assert f"since={since}" in life[0] and since <= t0 - 115
    assert life[2].startswith(f"ready epoch={t0} ") and life[2].endswith("unit=active")
    assert hooks.recorder_running()
    assert hooks.captured(), "ready means the subscription answered"
    # A second start for the same run id starts nothing.
    again = hooks.start_recorder()
    assert again.returncode == 1, report(again)
    assert f"STOP: {d} exists: the events capture of a run id is write-once; nothing was started" in again.stdout
    assert hooks.recorder_running() and len(hooks.ssh_commands()) == 2


@pytest.mark.parametrize("token, rc, says", [
    ("events-unit-fails", 1, f"STOP: the recorder unit egw-events-{RID} could not be started"),
    ("events-silent", 3, f"NOT READY: the recorder unit egw-events-{RID} did not show a live subscription"),
    ("events-cli-fails", 3, f"NOT READY: the recorder unit egw-events-{RID} did not show a live subscription"),
])
def test_a_recorder_that_cannot_start_or_is_not_ready_is_stopped_and_says_so(hooks, token, rc, says):
    start = hooks.start_recorder(EGW_STUB_FAIL=token)
    assert start.returncode == rc, report(start)
    assert says in start.stdout, report(start)
    assert "run_guest_t0=" not in start.stdout
    assert not hooks.recorder_running()
    life = (hooks.events_dir() / "lifecycle.txt").read_text(encoding="utf-8")
    assert "ready " not in life
    if token == "events-cli-fails":
        # The CLI ended by itself at once: its end and its reason are kept.
        assert "rc=1 stop_requested=no" in life and "Cannot connect to the Docker daemon" in start.stdout
    if token == "events-silent":
        # Running but receiving nothing: stopped by the step, and so ended
        # with the stop requested.
        assert "unit_state_after_stop=inactive" in start.stdout and "stop_requested=yes" in life


def test_events_past_the_daemons_bounded_history_are_captured_and_the_fault_is_found(hooks, monkeypatch):
    start = hooks.start_recorder()
    assert start.returncode == 0, report(start)
    t0 = _run_t0(start)
    # The fault, issued by the real restart hook: the daemon's kill (signal
    # 9), die and start of the controller reach the live stream.
    manifest = hooks.run_restart_by_the_harness(monkeypatch)
    assert manifest["returncode"] == 0, manifest
    hooks.wait_for(lambda: any(e.get("Action") == "start" for e in hooks.captured()))
    # Then more than the daemon keeps: 300 later events of the broker.
    filler = []
    for i in range(300):
        ns = steady_ns(hooks.clock)
        filler.append({"status": "exec_die", "id": "00" + "a" * 62, "from": "stub/egw-mosquitto-1:1", "Type": "container",
                       "Action": "exec_die", "Actor": {"ID": "00" + "a" * 62, "Attributes": {"name": "egw-mosquitto-1"}},
                       "scope": "local", "time": ns // 10 ** 9, "timeNano": ns + i})
    hooks.store_events(*filler)
    # A history query as r03 made it answers from the bounded buffer: the
    # kill and the start are no longer in it, and it says nothing of that.
    until = hooks.now()
    history = hooks.run_argv(["ssh", "egw-tcg", f"docker events --filter container=egw-controller-1 --since {t0} --until {until}"])
    assert history.returncode == 0 and history.stdout == "", report(history)
    whole = hooks.run_argv(["ssh", "egw-tcg", f"docker events --since {t0} --until {until}"])
    assert len(whole.stdout.splitlines()) == 256
    # The recorder captured them as they happened, and the fetch finds them
    # within the run's window.
    result, dest = _events_fetch(hooks, t0)
    assert result.returncode == 0, report(result)
    captured = [json.loads(line) for line in dest.read_text(encoding="utf-8").splitlines()]
    kill = [e for e in captured if e["Action"] == "kill" and e["Actor"]["Attributes"]["name"] == "egw-controller-1"]
    assert kill and kill[0]["Actor"]["Attributes"]["signal"] == "9"
    assert sum(e["Action"] == "exec_die" for e in captured) >= 300
    coverage = _coverage(hooks)
    assert coverage["coverage"] == ["complete"]
    assert coverage["requested_since_guest_epoch"] == [str(t0)] and coverage["expected"] == ["kill,die,start"]
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        assert coverage[f"rule_{rule}"][0].startswith("held: "), coverage
    assert "reason" not in coverage
    assert coverage["expected_found"][0].startswith("kill@")
    assert "provenance" in coverage and "not a history query" in coverage["provenance"][0]
    assert f"proof_fetch_sut_log: docker-events: coverage=complete from RUN_T0 {t0}" in result.stdout
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    assert f"sha256 {sha}, written to {dest}" in result.stdout
    # The records of the capture are kept beside it, and the unit is gone.
    for name in ("lifecycle.txt", "start-facts.txt", "cli-stderr.txt", "stop.txt", "coverage.txt"):
        assert (hooks.sut_logs / f"docker-events.{name}").is_file(), name
    assert not (hooks.sut_logs / "docker-events.partial.jsonl").exists()
    life = (hooks.sut_logs / "docker-events.lifecycle.txt").read_text(encoding="utf-8").splitlines()
    assert life[-1].startswith("cli-exit ") and life[-1].endswith("stop_requested=yes")
    stop = (hooks.sut_logs / "docker-events.stop.txt").read_text(encoding="utf-8")
    assert "unit_state_before_stop=active" in stop and "closing_witness_seen=yes" in stop
    assert "unit_state_after_stop=inactive" in stop
    assert not hooks.recorder_running()


def test_a_fault_free_capture_is_complete_without_expected_events_and_never_complete_when_they_are_missing(hooks):
    # The events of the fault are demanded of the run whose scenario
    # generates them, never of a fault-free run; here no fault happened.
    first = hooks.start_recorder()
    assert first.returncode == 0, report(first)
    result, dest = _events_fetch(hooks, _run_t0(first))
    assert result.returncode == 1, report(result)
    assert not dest.exists() and (hooks.sut_logs / "docker-events.partial.jsonl").is_file()
    coverage = _coverage(hooks)
    assert coverage["coverage"] == ["incomplete"]
    assert coverage["rule_R7"][0].startswith("broken: the expected event(s) kill (signal 9), die, start of egw-controller-1")
    assert [r.split(" ")[0] for r in coverage["reason"]] == ["R7"]
    assert "the docker-events capture is NOT shown complete (coverage=incomplete, checker exit 1)" in result.stderr
    # A fault-free run: the same capture, no expectation, complete.
    other = "fault-free-r01"
    second = hooks.start_recorder(other)
    assert second.returncode == 0, report(second)
    sut = hooks.bench.tmp / "raw" / other / "logs" / "sut"
    template = hooks.template("proof_fetch_sut_log.sh", "docker-events", "{dest}", str(_run_t0(second)), other)
    free = hooks.run_argv(shlex.split(run_mod.format_collector_template(
        template, other, duration_s=300, dest=sut / "docker-events.log", expect_services=list(EXPECT_SERVICES))))
    assert free.returncode == 0, report(free)
    text = (sut / "docker-events.coverage.txt").read_text(encoding="utf-8")
    assert text.startswith("coverage=complete\n") and "rule_R7=not-required: " in text and "expected=none" in text


@pytest.mark.parametrize("case, rule, says", [
    # The CLI ended by itself mid-run, with status 0 - the CLI's answer when
    # the daemon closes the stream: a break, never read as coverage.
    ("eof", "R3", "the events CLI ended by itself"),
    # The daemon was restarted (its MainPID and start stamp changed): what
    # the stream missed meanwhile is unknown.
    ("daemon-restarted", "R2", "the guest boot or the docker daemon changed during the capture"),
    # The CLI reported a problem on stderr.
    ("stderr", "R4", "the events CLI wrote to stderr"),
    # The stream fell silent: no event after the stop request shows it live
    # to the window's end.
    ("no-witness", "R5", "no event is stamped after the second of the stop request"),
])
def test_a_capture_that_was_broken_is_kept_apart_and_never_complete(hooks, case, rule, says):
    env = {"eof": {"EGW_STUB_EVENTS_EOF_AFTER": "15"}, "stderr": {"EGW_STUB_FAIL": "events-stderr"},
           "no-witness": {"EGW_STUB_EVENTS_QUIET_AFTER": "3"}}.get(case, {})
    start = hooks.start_recorder(**env)
    assert start.returncode == 0, report(start)
    t0 = _run_t0(start)
    if case == "eof":
        hooks.wait_for(lambda: "cli-exit" in (hooks.events_dir() / "lifecycle.txt").read_text(encoding="utf-8"))
        assert not hooks.recorder_running()
    if case == "daemon-restarted":
        Path(str(hooks.bench.log) + ".docker-daemon.json").write_text(
            json.dumps({"MainPID": "977", "ExecMainStartTimestampMonotonic": "9100000"}), "utf-8")
    if case == "no-witness":
        # Silent from a second BEFORE the one the stop is requested in: its
        # three heartbeats captured, and the guest clock past them.
        hooks.wait_for(lambda: len(hooks.captured()) >= 3)
        last = max(e["timeNano"] for e in hooks.captured()) // 10 ** 9
        hooks.wait_for(lambda: hooks.now() > last)
    result, dest = _events_fetch(hooks, t0, expected=None)
    assert result.returncode == 1, report(result)
    assert not dest.exists()
    assert (hooks.sut_logs / "docker-events.partial.jsonl").is_file()
    coverage = _coverage(hooks)
    assert coverage["coverage"] == ["incomplete"], coverage
    assert coverage[f"rule_{rule}"][0].startswith("broken: " + says), coverage
    assert any(r.startswith(f"{rule} broken: {says}") for r in coverage["reason"])
    assert f"proof_fetch_sut_log: docker-events: {rule} broken: {says}" in result.stderr
    last = result.stderr.splitlines()[-1]
    assert last.startswith("STOP: proof_fetch_sut_log: the docker-events capture is NOT shown complete (coverage=incomplete")
    assert last.endswith(f"was NOT written; what was captured is kept as {hooks.sut_logs}/docker-events.partial.jsonl")
    if case == "eof":
        assert "rc=0 stop_requested=no" in (hooks.sut_logs / "docker-events.lifecycle.txt").read_text(encoding="utf-8")
        assert "unit_state_before_stop=inactive" in (hooks.sut_logs / "docker-events.stop.txt").read_text(encoding="utf-8")
    assert not hooks.recorder_running()


def test_a_recorder_the_fetch_could_not_stop_is_not_judged(hooks):
    # The stop was refused: the capture was not shown to end by it, so it is
    # not judged, whatever it holds, and the unit is left to the driver's
    # restoration, which stops it and records the capture incomplete.
    start = hooks.start_recorder()
    assert start.returncode == 0, report(start)
    result, dest = _events_fetch(hooks, _run_t0(start), expected=None, EGW_STUB_FAIL="events-stop-fails")
    assert result.returncode == 1, report(result)
    assert f"STOP: 'systemctl stop egw-events-{RID}' failed" in result.stderr
    coverage = _coverage(hooks)
    assert coverage["coverage"] == ["unknown"]
    assert coverage["reason"] == [f"the stop of the recorder unit egw-events-{RID} on the guest exited 1 (ssh egw-tcg): "
                                  "the capture was not judged"]
    assert "unit_state_after_stop=active" in (hooks.sut_logs / "docker-events.stop.txt").read_text(encoding="utf-8")
    assert not dest.exists() and (hooks.sut_logs / "docker-events.partial.jsonl").is_file()
    assert hooks.recorder_running()


def test_an_events_fetch_with_no_recorder_on_the_guest_is_not_judged(hooks):
    result, dest = _events_fetch(hooks, hooks.now() - 60)
    assert result.returncode == 1, report(result)
    assert f"STOP: /tmp/egw-events-{RID} is not on the guest" in result.stderr.replace(str(hooks.bench.guest_root), "")
    coverage = _coverage(hooks)
    assert coverage["coverage"] == ["unknown"]
    assert any("the stop of the recorder unit" in r and "the capture was not judged" in r for r in coverage["reason"])
    assert not dest.exists() and not (hooks.sut_logs / "docker-events.partial.jsonl").exists()
    assert "coverage=unknown, checker exit 2" in result.stderr.splitlines()[-1]


@pytest.mark.parametrize("kind, token, flag, reason", [
    ("broker", "broker-log-empty", "--fetch-broker-log-cmd", None),
    ("controller", "controller-log-fails", "--fetch-controller-log-cmd", "Error: No such container: egw-controller-1"),
])
def test_fetch_sut_log_run_by_the_harness_hook_runner_keeps_the_stop_line_in_the_capsule(hooks, monkeypatch, kind, token,
                                                                                         flag, reason):
    """The wrapper through execute_collector_hook itself: the record the
    manifest keeps and the hook-<hook>.stderr.txt the seal covers, with the
    guest's reason when the failed read gave one."""
    for key, val in hooks.env(EGW_STUB_FAIL=token).items():
        monkeypatch.setenv(key, val)
    label = FETCH_KINDS[kind]
    dest = hooks.sut_logs / run_mod.SUT_LOG_FILES[label]
    template = hooks.template("proof_fetch_sut_log.sh", kind, "{dest}", GUEST_T0)
    record = run_mod.execute_collector_hook(label, template, RID, duration_s=300, dest=dest,
                                            expect_services=list(EXPECT_SERVICES),
                                            log_dir=hooks.sut_logs, timeout_s=120)
    assert record["returncode"] == 1
    assert record["flag"] == flag
    assert f"the {kind} log was NOT read on the guest" in record["stderr_tail"]
    assert "neither observed nor excluded" in record["stderr_tail"]
    kept = (hooks.sut_logs / f"hook-{label}.stderr.txt").read_text(encoding="utf-8")
    stop = f"STOP: proof_fetch_sut_log: the {kind} log was NOT read on the guest"
    assert kept.splitlines()[-1].startswith(stop)
    if reason is None:
        assert kept.startswith(stop)
    else:
        assert kept.startswith(f"proof_fetch_sut_log: the {kind} read exited 1 after answering")
        assert reason in kept and reason in record["stderr_tail"]
    assert not dest.exists()
    record["dest_exists"] = dest.is_file()
    record["dest_file"] = f"logs/sut/{run_mod.SUT_LOG_FILES[label]}"
    reasons = run_mod.sut_log_fetch_failures([record])
    assert len(reasons) == 1 and reasons[0].startswith(f"SUT log fetch {flag} failed with exit code 1")


def test_an_incomplete_events_capture_run_by_the_harness_hook_runner_is_a_fetch_failure(hooks, monkeypatch):
    """A capture the checker does not find complete leaves the harness a
    fetch that exited 1 and wrote no file: the validity reason of item 18,
    the eligibility's and the evaluator's incomplete evidence, unchanged."""
    start = hooks.start_recorder(EGW_STUB_EVENTS_EOF_AFTER="15")
    assert start.returncode == 0, report(start)
    hooks.wait_for(lambda: not hooks.recorder_running())
    for key, val in hooks.env().items():
        monkeypatch.setenv(key, val)
    dest = hooks.sut_logs / run_mod.SUT_LOG_FILES["docker_events"]
    template = hooks.template("proof_fetch_sut_log.sh", "docker-events", "{dest}", str(_run_t0(start)), "{run_id}",
                              "kill,die,start")
    record = run_mod.execute_collector_hook("docker_events", template, RID, duration_s=300, dest=dest,
                                            expect_services=list(EXPECT_SERVICES), log_dir=hooks.sut_logs, timeout_s=120)
    assert record["returncode"] == 1 and record["flag"] == "--fetch-docker-events-cmd"
    assert "the docker-events capture is NOT shown complete (coverage=incomplete" in record["stderr_tail"]
    record["dest_exists"] = dest.is_file()
    record["dest_file"] = "logs/sut/docker-events.log"
    assert record["dest_exists"] is False
    reasons = run_mod.sut_log_fetch_failures([record])
    assert len(reasons) == 1 and reasons[0].startswith("SUT log fetch --fetch-docker-events-cmd failed with exit code 1")


# --------------------------------------------------------------------------
# proof_restart_controller.sh (design 2.12 test 10)
# --------------------------------------------------------------------------


def test_the_restart_template_is_sigkill_then_start_of_the_controller_container_and_records_both_guest_instants(hooks, monkeypatch):
    manifest = hooks.run_restart_by_the_harness(monkeypatch)
    assert manifest["returncode"] == 0, manifest
    # The fault, in one ssh session and in this order: a SIGKILL of the
    # controller's container, then a compose start of the controller service.
    fault = [line for line in hooks.ssh_commands() if "docker kill" in line]
    assert len(fault) == 1
    assert fault[0].endswith("/opt/egw/deployment && docker kill --signal=KILL egw-controller-1 "
                             "&& docker compose --env-file .env --env-file images.lock.env start controller")
    calls = hooks.docker_calls()
    assert calls.index("kill --signal=KILL egw-controller-1") < calls.index("compose start controller")
    assert calls[0].startswith("inspect") and calls[-1].startswith("inspect")
    # The write-once record: the guest instants and the container before and
    # after; the id stayed (kill + start keeps the object) and StartedAt moved.
    record = hooks.restart_record()
    assert list(record) == ["head", "before", "fault", "after", "observation"]
    assert value(record["head"], "run_id") == RID
    assert value(record["head"], "container") == "egw-controller-1"
    for phase in ("before", "after"):
        assert re.fullmatch(r"\d+", value(record[phase], "guest_epoch"))
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value(record[phase], "guest_utc"))
        assert re.fullmatch(r"[0-9a-f]{64}", value(record[phase], "container_id"))
    assert value(record["before"], "started_at") == "2026-09-25T10:00:00.100000000Z"
    assert value(record["after"], "started_at") == "2026-09-25T10:05:01.200000000Z"
    assert value(record["before"], "status") == "running" and value(record["after"], "status") == "running"
    assert value(record["before"], "container_id") == value(record["after"], "container_id")
    assert value(record["fault"], "fault_exit") == "0"
    assert value(record["fault"], "fault_command").startswith("cd /opt/egw/deployment && docker kill --signal=KILL")
    assert value(record["observation"], "container_id_same") == "yes"
    assert value(record["observation"], "started_at_changed") == "yes"
    # Both guest instants reach the manifest, whose restart record keeps ONLY
    # the last 500 characters of the hook's stderr: the line the hook prints
    # LAST carries both by itself, well under 250 characters, after whatever
    # the guest wrote to stderr during the fault (compose's progress lines,
    # which the stub prints to stderr as compose does).
    before = f"{value(record['before'], 'guest_utc')} (epoch {value(record['before'], 'guest_epoch')})"
    after = f"{value(record['after'], 'guest_utc')} (epoch {value(record['after'], 'guest_epoch')})"
    tail = manifest["stderr_tail"]
    assert len(tail) <= 500
    last = tail.splitlines()[-1]
    assert last == (f"proof_restart_controller: guest instants: before {before}, after {after}; "
                    "container_id_same=yes started_at_changed=yes; the restart-shown step decides")
    assert len(last) < 250, len(last)
    assert tail.index(" Container egw-controller-1  Started") < tail.index("guest instants:")
    # The line printed before the fault is context in time order; it is
    # whole here because this guest wrote little.
    assert f"proof_restart_controller: before the fault: guest {before}, egw-controller-1 started" in tail
    # A run id gets one fault: the second call stops on the record and kills
    # nothing.
    again = hooks.run_restart()
    assert again.returncode == 1, report(again)
    assert f"STOP: proof_restart_controller: {hooks.prefix / f'{RID}.restart.txt'} exists" in again.stderr
    assert "nothing was killed" in again.stderr
    assert hooks.docker_calls().count("kill --signal=KILL egw-controller-1") == 1


def test_restart_keeps_both_guest_instants_in_the_manifests_tail_when_the_guest_writes_past_the_budget(hooks, monkeypatch):
    """The scenario of the review of 2026-09-25: the guest writes more than
    500 characters to stderr between the two readings (compose warnings and
    progress, an ssh notice), so the tail starts inside that noise."""
    manifest = hooks.run_restart_by_the_harness(monkeypatch, EGW_STUB_FAIL="start-verbose")
    assert manifest["returncode"] == 0, manifest
    record = hooks.restart_record()
    tail = manifest["stderr_tail"]
    assert len(tail) == 500
    # The line printed before the fault is gone from the tail, and the noise
    # is what the tail begins with...
    assert "before the fault: guest" not in tail
    assert "stub compose warning" in tail
    # ...and the last line still holds both instants, as the manifest reads.
    last = tail.splitlines()[-1]
    assert last.startswith("proof_restart_controller: guest instants: before ")
    for phase in ("before", "after"):
        assert f"{value(record[phase], 'guest_utc')} (epoch {value(record[phase], 'guest_epoch')})" in last
    assert last.endswith("; container_id_same=yes started_at_changed=yes; the restart-shown step decides")


def test_restart_kills_nothing_when_the_container_was_not_read_before_the_fault(hooks):
    result = hooks.run_restart(EGW_STUB_FAIL="inspect-fails")
    assert result.returncode == 1, report(result)
    assert ("STOP: proof_restart_controller: the controller container was NOT read on the guest before the fault "
            "(ssh egw-tcg exit 4): nothing was killed") in result.stderr
    assert not (hooks.prefix / f"{RID}.restart.txt").exists()
    assert not any("kill" in call for call in hooks.docker_calls())
    # An inspect that answers with no StartedAt is a reading that was not
    # made, never an instant: nothing is killed either.
    result = hooks.run_restart(EGW_STUB_FAIL="inspect-empty-started")
    assert result.returncode == 1, report(result)
    assert "started_at is empty: the instant was not read" in result.stderr
    assert "the reading before the fault is not of the expected form" in result.stderr
    assert "nothing was killed" in result.stderr
    assert not (hooks.prefix / f"{RID}.restart.txt").exists()
    assert not any("kill" in call for call in hooks.docker_calls())


@pytest.mark.parametrize("token, killed", [("kill-fails", False), ("start-fails", True)])
def test_restart_whose_fault_command_fails_keeps_the_reading_before_it_and_exits_non_zero(hooks, monkeypatch, token, killed):
    manifest = hooks.run_restart_by_the_harness(monkeypatch, EGW_STUB_FAIL=token)
    assert manifest["returncode"] == 1, manifest
    record = hooks.restart_record()
    assert list(record) == ["head", "before", "fault"]
    assert value(record["fault"], "fault_exit") == "1"
    assert re.fullmatch(r"[0-9a-f]{64}", value(record["before"], "container_id"))
    # The STOP line is the last line of the manifest's tail, after the
    # daemon's refusal that the guest wrote to stderr, and it names the
    # instant read before the fault: the tail ends with every instant the
    # hook read, whatever came before it.
    tail = manifest["stderr_tail"]
    last = tail.splitlines()[-1]
    assert last.startswith("STOP: proof_restart_controller: the fault command exited 1 (kill --signal=KILL then compose start "
                           "controller): whether the controller was killed and started again is NOT established by this record")
    assert last.endswith(f"; before the fault: guest {value(record['before'], 'guest_utc')} "
                         f"(epoch {value(record['before'], 'guest_epoch')})")
    assert f"Error response from daemon: stub {token.partition('-')[0]} refused" in tail
    assert "after the fault" not in tail and "guest instants:" not in tail
    calls = hooks.docker_calls()
    # The '&&' chain: a refused kill dispatches no start at all; a refused
    # start was dispatched after a kill that was carried out (the stub's
    # state on disk exists only once the kill went through).
    assert calls.count("kill --signal=KILL egw-controller-1") == 1
    assert ("compose start controller" in calls) is killed
    assert Path(str(hooks.bench.log) + ".proof-docker.json").exists() is killed


def test_restart_records_a_start_without_effect_as_an_observation_and_decides_nothing(hooks):
    result = hooks.run_restart(EGW_STUB_FAIL="start-no-effect")
    assert result.returncode == 0, report(result)
    record = hooks.restart_record()
    assert value(record["before"], "started_at") == value(record["after"], "started_at")
    assert value(record["after"], "status") == "exited"
    assert value(record["observation"], "started_at_changed") == "no"
    assert value(record["observation"], "container_id_same") == "yes"
    assert "started_at_changed=no; the restart-shown step decides" in result.stderr


# --------------------------------------------------------------------------
# Every hook: the helper file, the run id, and the shell text
# --------------------------------------------------------------------------


def _every_hook(hooks: Hooks, run_id: str = RID, with_fetch: bool = True,
                **overrides) -> dict[str, subprocess.CompletedProcess]:
    """One call of each wrapper, as the harness renders it; the fetch takes
    no run id, so a case about run ids leaves it out."""
    results = {
        "proof_hook_twins.sh": hooks.run_hook(hooks.template("proof_hook_twins.sh", run_id, "{dest}", SEED),
                                              hooks.run_dir / "twins.before.json", **overrides),
        "proof_hook_drained.sh": hooks.run_hook(hooks.template("proof_hook_drained.sh", run_id),
                                                hooks.run_dir / "unused", **overrides),
        "proof_restart_controller.sh": hooks.run_argv(
            shlex.split(run_mod.format_cmd_template(hooks.template("proof_restart_controller.sh", run_id), RID)),
            **overrides),
    }
    if with_fetch:
        results["proof_fetch_sut_log.sh"] = hooks.run_hook(
            hooks.template("proof_fetch_sut_log.sh", "broker", "{dest}", GUEST_T0),
            hooks.sut_logs / "broker.log", **overrides)
    return results


def _nothing_touched(hooks: Hooks) -> None:
    assert hooks.ssh_commands() == []
    assert hooks.rec_calls() == []
    assert not (hooks.run_dir / "twins.before.json").exists()
    assert not (hooks.sut_logs / "broker.log").exists()
    assert not (hooks.prefix / f"{RID}.restart.txt").exists()


def test_every_hook_stops_with_97_and_touches_nothing_when_the_helper_file_cannot_be_loaded(hooks):
    hooks.helpers.unlink()
    for hook, result in _every_hook(hooks).items():
        assert result.returncode == 97, hook + "\n" + report(result)
        assert result.stderr.startswith(f"STOP: {hook[:-3]}: the helper file {hooks.helpers} is not readable: "
                                        "the hook never reached"), hook + "\n" + report(result)
    _nothing_touched(hooks)
    # A helper file that loads and FAILS is the same: the runbook's own last
    # line stops when the .env was not exported, and sourcing then returns
    # non-zero. The guard is read from the runbook, and the hooks run
    # without the password.
    guard = next(line for line in runbook_helper_body().splitlines()
                 if line.startswith('[ -n "$MOSQUITTO_SIMULATOR_PASSWORD" ] || stop'))
    _write(hooks.helpers, ITEST_HELPERS + "\n" + runbook_function("keep") + guard + "\n")
    for hook, result in _every_hook(hooks, MOSQUITTO_SIMULATOR_PASSWORD=None).items():
        assert result.returncode == 97, hook + "\n" + report(result)
        assert "STOP: MOSQUITTO_SIMULATOR_PASSWORD is empty" in result.stderr, hook
        assert f"STOP: {hook[:-3]}: the helper file {hooks.helpers} could not be loaded: the hook never reached" \
            in result.stderr, hook + "\n" + report(result)
    _nothing_touched(hooks)


def test_every_hook_that_takes_a_run_id_refuses_one_that_is_not_a_plain_name(hooks):
    for hook, result in _every_hook(hooks, run_id="'../x y'", with_fetch=False).items():
        assert result.returncode == 2, hook + "\n" + report(result)
        assert "RUN_ID '../x y' is not a plain run id" in result.stderr, hook
    _nothing_touched(hooks)


def test_the_hooks_are_shellcheck_clean_at_error_severity():
    shellcheck = shutil.which("shellcheck") or os.path.expanduser("~/egw-exec/venv/bin/shellcheck")
    if not os.access(shellcheck, os.X_OK):
        pytest.skip("shellcheck is not installed (the technical CI runs it over every *.sh)")
    result = subprocess.run([shellcheck, "-S", "error", *[str(REPO_ROOT / "tools" / "session" / h) for h in HOOKS]],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
