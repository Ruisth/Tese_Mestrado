"""Lifecycle cases for tools/session/broker_measure.sh, on the drivers' stub bench.

The bench of ``test_session_drivers`` is reused: the real ``local_export``,
this interpreter as the venv, the ssh and scp stubs that run guest commands on
this machine against a fake guest root. On top of it this module installs its
own guest ``docker`` (the six services of the stack and the probe container,
with state on disk), ``systemd-run``/``systemctl`` (which really run the guest
recorder as a background process) and a stub of the probe tool whose clients
write records shaped like the real ones and whose ``verdict`` is the real one.

What these cases show is the driver's own behaviour: that phase P7 ends only
after the redelivery client ended and its status is captured; that a client
which does not end is ended by the driver and the run is inconclusive; that an
interruption — including one that lands while the stack is being stopped —
reaps the clients and restores the stack; that a name already in use stops the
driver before it touches anything; that a restoration which fails, or a record
which could not be made, never yields a passing session while the broker
observation is kept apart in ``broker_verdict``. They say nothing about a real
broker, the guest or the network.
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
if shutil.which("bash") is None or shutil.which("timeout") is None:
    pytest.skip("bash and timeout are needed", allow_module_level=True)

from test_session_drivers import Bench, _write, report  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_PROBE = REPO_ROOT / "tools" / "probe" / "broker_hold.py"

# --------------------------------------------------------------------------
# guest stubs of this module
# --------------------------------------------------------------------------

DOCKER_STUB = r'''#!/usr/bin/env python3
"""Stub docker for the broker measurement: the six services and the probe."""
import json
import os
import sys
import time

SERVICES = ("egw-mosquitto-1", "egw-mongodb-1", "egw-ditto-policies-1",
            "egw-ditto-things-1", "egw-ditto-gateway-1", "egw-controller-1")
STATE = os.environ["EGW_STUB_LOG"] + ".docker.json"
CG = os.environ.get("PROBE_CGROUP_ROOT", "/nonexistent")
DK = os.environ.get("PROBE_DOCKER_ROOT", "/nonexistent")
failures = f",{os.environ.get('EGW_STUB_FAIL', '')},"


def fails(token):
    return f",{token}," in failures


def load():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"services": {s: {"state": "running", "health": "healthy"} for s in SERVICES},
                "containers": {}, "volumes": {}}


def save(state):
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def log(line):
    with open(os.environ["EGW_STUB_LOG"] + ".dockerlog", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


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

if compose:
    cmd = args[0] if args else ""
    if cmd == "stop":
        if fails("stack-stop"):
            print("stub: compose stop failed", file=sys.stderr)
            sys.exit(1)
        if fails("stack-stop-hang"):
            time.sleep(float(os.environ.get("EGW_STUB_HANG_S", "5")))
        for s in SERVICES:
            state["services"][s] = {"state": "exited", "health": "none"}
        save(state)
        sys.exit(0)
    if cmd == "start":
        if fails("stack-start"):
            print("stub: compose start failed", file=sys.stderr)
            sys.exit(1)
        for s in SERVICES:
            state["services"][s] = {"state": "running", "health": "unhealthy" if fails("healthy-again") else "healthy"}
        save(state)
        sys.exit(0)
    if cmd == "ps":
        for s in SERVICES:
            print(f"{s} {state['services'][s]['state']} {state['services'][s]['health']}")
        sys.exit(0)
    sys.exit(0)

cmd = args[0] if args else ""


def render(template, name):
    svc = state["services"].get(name)
    con = state["containers"].get(name)
    if svc is None and con is None:
        print(f"Error: No such object: {name}", file=sys.stderr)
        sys.exit(1)
    if svc is not None:
        fields = {"Id": f"{SERVICES.index(name):02d}" + "a" * 62, "State.Status": svc["state"],
                  "State.OOMKilled": "false", "State.ExitCode": "0", "RestartCount": "0",
                  "State.StartedAt": "2026-09-19T20:00:00Z", "Image": "sha256:stubimage", "health": svc["health"],
                  "label": ""}
    else:
        fields = {"Id": con["id"], "State.Status": con["state"], "State.OOMKilled": str(con.get("oom", False)).lower(),
                  "State.ExitCode": str(con.get("exit", 0)), "RestartCount": str(con.get("restarts", 0)),
                  "State.StartedAt": con["started"], "Image": con["image"], "health": "none",
                  "label": con["labels"].get("egw.probe.attempt", "")}
    out = template
    out = out.replace("{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", fields["health"])
    out = out.replace('{{index .Config.Labels "egw.probe.attempt"}}', fields["label"])
    for key in ("State.Status", "State.OOMKilled", "State.ExitCode", "State.StartedAt", "RestartCount", "Id", "Image"):
        out = out.replace("{{." + key + "}}", fields[key])
    return out


if cmd == "inspect":
    template = "{{.Id}}"
    rest = args[1:]
    if rest and rest[0] == "-f":
        template, rest = rest[1], rest[2:]
    for name in rest:
        print(render(template, name))
    sys.exit(0)

if cmd == "volume":
    sub, name = args[1], args[-1]
    vdir = os.path.join(DK, "volumes", name, "_data")
    if sub == "create":
        if name in state["volumes"]:
            print(f"Error: volume {name} exists", file=sys.stderr)
            sys.exit(1)
        labels = {}
        for i, a in enumerate(args):
            if a == "--label":
                k, _, v = args[i + 1].partition("=")
                labels[k] = v + os.environ.get("EGW_STUB_VOLUME_LABEL_SUFFIX", "")
        state["volumes"][name] = {"labels": labels}
        os.makedirs(vdir, exist_ok=True)
        with open(os.path.join(vdir, "mosquitto.db"), "w") as fh:
            fh.write("stub store")
        save(state)
        print(name)
        sys.exit(0)
    if sub == "inspect":
        if name not in state["volumes"]:
            print(f"Error response from daemon: get {name}: no such volume", file=sys.stderr)
            sys.exit(1)
        if "-f" in args:
            template = args[args.index("-f") + 1]
            label = (state["volumes"][name].get("labels") or {}).get("egw.probe.attempt", "")
            print(template.replace('{{index .Labels "egw.probe.attempt"}}', label))
        sys.exit(0)
    if sub == "rm":
        if name not in state["volumes"]:
            print(f"Error: No such volume: {name}", file=sys.stderr)
            sys.exit(1)
        del state["volumes"][name]
        save(state)
        print(name)
        sys.exit(0)
    sys.exit(1)

if cmd == "run":
    name = args[args.index("--name") + 1]
    labels = {}
    for i, a in enumerate(args):
        if a == "--label":
            k, _, v = args[i + 1].partition("=")
            labels[k] = v + os.environ.get("EGW_STUB_LABEL_SUFFIX", "")
    if name in state["containers"]:
        print(f"docker: Error response from daemon: Conflict. The container name \"/{name}\" is already in use.", file=sys.stderr)
        sys.exit(125)
    if fails("probe-run"):
        print("docker: Error response from daemon: stub run failure", file=sys.stderr)
        sys.exit(125)
    cid = ("%064x" % (abs(hash(name + str(time.time()))) % (1 << 200)))[:64]
    refused = fails("probe-refused")
    con = {"id": cid, "state": "exited" if refused else "running", "started": "2026-09-24T10:00:00.000000000Z",
           "image": "sha256:" + "b" * 64, "labels": labels, "oom": False, "restarts": 0, "exit": 3 if refused else 0,
           "log": (["2026-09-24T10:00:00: mosquitto version 2.0.22 starting",
                    "2026-09-24T10:00:00: Error: Invalid max_inflight_messages value (stub)."] if refused else
                   ["2026-09-24T10:00:00: mosquitto version 2.0.22 starting",
                    "2026-09-24T10:00:00: Config loaded from /mosquitto/config/mosquitto.conf.",
                    "2026-09-24T10:00:00: Opening ipv4 listen socket on port 8883.",
                    "2026-09-24T10:01:10: New client connected from 10.0.2.2:5000 as egw-probe-hold (p2, c0, k60, u'egw-controller')."]
                   + ([] if fails("no-disconnect-line") else ["2026-09-24T10:03:20: Client egw-probe-hold closed its connection."]))}
    state["containers"][name] = con
    cg = os.path.join(CG, "docker", cid)
    os.makedirs(cg, exist_ok=True)
    mem_max = os.environ.get("EGW_STUB_MEMORY_MAX", "134217728")
    for fname, text in (("memory.current", "20000000\n"), ("memory.max", mem_max + "\n"), ("memory.peak", "21000000\n"),
                        ("memory.stat", "anon 10000000\nfile 5000000\nactive_file 1\ninactive_file 2\n"),
                        ("memory.events", "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n")):
        with open(os.path.join(cg, fname), "w") as fh:
            fh.write(text)
    save(state)
    print(cid)
    sys.exit(0)

if cmd == "logs":
    name = args[-1]
    con = state["containers"].get(name)
    if con is None:
        print(f"Error: No such container: {name}", file=sys.stderr)
        sys.exit(1)
    for line in con["log"]:
        print(line)
    sys.exit(0)

if cmd == "rm":
    name = args[-1]
    if fails("probe-remove"):
        print("stub: rm failed", file=sys.stderr)
        sys.exit(1)
    if name not in state["containers"]:
        print(f"Error: No such container: {name}", file=sys.stderr)
        sys.exit(1)
    del state["containers"][name]
    save(state)
    print(name)
    sys.exit(0)

print(f"stub docker: unhandled {args}", file=sys.stderr)
sys.exit(1)
'''

SYSTEMD_RUN_STUB = r'''#!/usr/bin/env python3
"""Stub systemd-run: really runs the unit's command in the background."""
import os
import subprocess
import sys

args = sys.argv[1:]
unit = args[args.index("--unit") + 1]
if "," + "recorder-start" + "," in "," + os.environ.get("EGW_STUB_FAIL", "") + ",":
    print("stub: the unit could not be started", file=sys.stderr)
    sys.exit(1)
i = args.index("--collect") + 1 if "--collect" in args else args.index(unit) + 1
command = args[i:]
proc = subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
with open(os.environ["EGW_STUB_LOG"] + ".unit." + unit, "w") as fh:
    fh.write(str(proc.pid))
print(f"Running as unit: {unit}.service")
'''

SYSTEMCTL_STUB = r'''#!/usr/bin/env python3
"""Stub systemctl: is-active and stop of the units systemd-run started."""
import os
import signal
import sys
import time

cmd, unit = sys.argv[1], sys.argv[-1]
path = os.environ["EGW_STUB_LOG"] + ".unit." + unit
failures = "," + os.environ.get("EGW_STUB_FAIL", "") + ","
try:
    pid = int(open(path).read().strip())
except (OSError, ValueError):
    pid = None


def alive(p):
    try:
        os.kill(p, 0)
        return True
    except OSError:
        return False


def polls(suffix):
    p = os.environ["EGW_STUB_LOG"] + suffix
    try:
        n = int(open(p).read() or 0)
    except (OSError, ValueError):
        n = 0
    n += 1
    with open(p, "w") as fh:
        fh.write(str(n))
    return n


if cmd == "is-active":
    # 'recorder-start-late': the unit IS running, but the first query after it
    # was started, the one inside the start command, answers as if it were not
    # (a slow systemd); queries before the unit exists are not counted
    if ",recorder-start-late," in failures and pid is not None and polls(".isactive") == 1:
        print("activating")
        sys.exit(3)
    if pid and alive(pid):
        print("active")
        sys.exit(0)
    print("inactive")
    sys.exit(3)
if cmd == "stop":
    if ",recorder-stop-fails," in failures:
        # the stop is refused and the unit keeps running
        print("Failed to stop " + unit + ".service: stub refusal", file=sys.stderr)
        sys.exit(1)
    if pid and alive(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not alive(pid):
                break
            time.sleep(0.1)
    sys.exit(0)
sys.exit(0)
'''

PROBE_STUB = r'''#!/usr/bin/env python3
"""Stub of broker_hold.py: clients whose records are shaped like the real
ones, driven by EGW_STUB_* variables; the verdict is the real one."""
import base64
import importlib.util
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

LOG = os.environ["EGW_STUB_LOG"]
A = int(os.environ.get("EGW_PROBE_A", "6"))
B = int(os.environ.get("EGW_PROBE_B", "4"))
Q = int(os.environ.get("EGW_PROBE_Q", "2"))


def utc():
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{dt.microsecond // 1000:03d}Z"


def opt(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def rec(path, event, **fields):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": event, "t_utc": utc(), "t_mono_ns": time.monotonic_ns(), **fields}) + "\n")
        fh.flush()


def marker(name):
    open(LOG + "." + name, "w").close()


def term_handler(name):
    def handler(*_):
        marker(name)
        sys.exit(143)
    return handler


def ids():
    out = []
    for i in range(A + B):
        mid = f"a{i}" if i < A else f"b{i - A}"
        dev = "d1" if i % 2 == 0 else "d2"
        out.append((mid, dev, i // 2))
    return out


cmd = sys.argv[1]
if cmd == "generate":
    # like the real one, the simulator resolves its schemas from EGW_SCHEMA_DIR
    # when that is set: a value meant for the guest (a path relative to the
    # deployment tree) does not exist on the host and is a prerequisite failure
    schema_dir = os.environ.get("EGW_SCHEMA_DIR")
    if schema_dir is not None and not os.path.isdir(schema_dir):
        print(f"STOP: [Errno 2] No such file or directory: '{schema_dir}/telemetry-envelope-v1.schema.json'", file=sys.stderr)
        sys.exit(2)
    out = opt("--out")
    count = int(opt("--count"))
    with open(out, "w", encoding="utf-8") as fh:
        for i, (mid, dev, seq) in enumerate(ids()[:count]):
            payload = json.dumps({"message_id": mid, "device_uuid": dev, "seq": seq})
            fh.write(json.dumps({"i": i, "t_offset_s": round(i / 11.2, 6), "topic": f"c2dt/egw-01/{dev}/telemetry",
                                 "message_id": mid, "device_uuid": dev, "device_type": "smartwatch", "seq": seq,
                                 "bytes": len(payload), "payload_b64": base64.b64encode(payload.encode()).decode()}) + "\n")
    print(f"generated: count={count}")
    sys.exit(0)

if cmd == "publish":
    record = opt("--record")
    first, count = int(opt("--first")), int(opt("--count"))
    exit_code = int(os.environ.get("EGW_STUB_PUBLISH_EXIT", "0"))
    unacked = 1 if exit_code == 1 else 0
    rec(record, "connected", first=first, count=count)
    for k, (mid, dev, seq) in enumerate(ids()[first:first + count]):
        rec(record, "published", i=first + k, mid=k + 1, rc=0, message_id=mid, device_uuid=dev, seq=seq, bytes=300,
            due_offset_s=k / 11.2, publish_mono_ns=1, puback_mono_ns=None if k < unacked else 2, puback_utc=utc())
    rec(record, "end", first=first, count=count, published=count, acked=count - unacked, unacked=unacked, span_s=0.1)
    print(f"published: first={first} count={count} published={count} acked={count - unacked} unacked={unacked}")
    if exit_code == 1:
        print("NOT EXACT: stub")
    sys.exit(exit_code)

if cmd == "hold":
    record = opt("--record")
    stop_file = opt("--stop-file")
    ack = "--ack" in sys.argv
    name = "hold_p7" if ack else "hold_p1"
    signal.signal(signal.SIGTERM, term_handler(name + "_term"))
    with open(LOG + "." + name + "_pid", "w") as fh:
        fh.write(str(os.getpid()))
    rec(record, "connect", session_present=ack, reason="0:Success")
    rec(record, "subscribe", topic="c2dt/+/+/telemetry", granted=["1:GrantedQoS1"], required_qos=1)
    print(f"SUBSCRIBED: topic=c2dt/+/+/telemetry granted=['1:GrantedQoS1'] session_present={ack} ack={ack}", flush=True)
    if not ack:
        for k, (mid, dev, seq) in enumerate(ids()[:A]):
            rec(record, "delivery", n=k + 1, mid=k + 1, dup=False, qos=1, retain=False, bytes=300,
                topic=f"c2dt/egw-01/{dev}/telemetry", message_id=mid, device_uuid=dev, seq=seq, ack_requested=False)
        limit = float(opt("--limit", "3600"))
        t0 = time.monotonic()
        while not (stop_file and os.path.exists(stop_file)) and time.monotonic() - t0 < limit:
            time.sleep(0.2)
        rec(record, "end", received=A, acked=0, ack_failed=0, why="stop-file", session_present=False, recorder_failed=False)
        print("hold end: received=%d acked=0 why=stop-file" % A)
        sys.exit(0)
    time.sleep(float(os.environ.get("EGW_STUB_P7_DELAY_S", "0.5")))
    held = ids()[:A] + ids()[A:A + Q]
    for k, (mid, dev, seq) in enumerate(held):
        rec(record, "delivery", n=k + 1, mid=k + 1, dup=k < A, qos=1, retain=False, bytes=300,
            topic=f"c2dt/egw-01/{dev}/telemetry", message_id=mid, device_uuid=dev, seq=seq, ack_requested=True)
        rec(record, "ack", n=k + 1, mid=k + 1, qos=1, rc=0, ok=True)
    hang = float(os.environ.get("EGW_STUB_P7_HANG_S", "0"))
    if hang:
        time.sleep(hang)
    why = os.environ.get("EGW_STUB_P7_WHY", "expected-and-idle")
    rec(record, "end", received=len(held), acked=len(held), ack_failed=0, why=why, session_present=True, recorder_failed=False)
    print(f"hold end: received={len(held)} acked={len(held)} ack_failed=0 why={why} session_present=True span_s=1")
    sys.exit(int(os.environ.get("EGW_STUB_P7_EXIT", "0")))

if cmd == "sysreader":
    record = opt("--record")
    stop_file = opt("--stop-file")
    phases_path = os.path.join(os.path.dirname(record), "phases.jsonl")
    signal.signal(signal.SIGTERM, term_handler("sys_term"))
    rec(record, "connect", reason="0:Success", session_present=False)
    rec(record, "subscribe", topic="$SYS/#", granted=["0:GrantedQoS0"])
    print("SUBSCRIBED: topic=$SYS/# granted=['0:GrantedQoS0']", flush=True)
    rec(record, "sys", topic="$SYS/broker/version", value="mosquitto version 2.0.22")
    print("SYS: $SYS/broker/version = mosquitto version 2.0.22", flush=True)

    hold_p7_path = os.path.join(os.path.dirname(record), "hold_p7.jsonl")

    def current_phase():
        last = "P0"
        try:
            with open(phases_path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if "start_utc" in r and r.get("phase", "").startswith("P"):
                        last = r["phase"]
                    if "end_utc" in r and r.get("phase") == "P7":
                        last = "P8"
        except OSError:
            pass
        if last == "P7":
            # the store empties as the redeliveries are acknowledged: once the
            # client has written its end record, the broker holds nothing
            try:
                if '"end"' in open(hold_p7_path, encoding="utf-8").read():
                    last = "P7-done"
            except OSError:
                pass
        return last

    values = {"P0": (0, 0, 0), "P1": (0, 0, 0), "P2": (A, 0, A), "P3": (A, 0, A), "P4": (A, 0, A),
              "P5": (A + Q, B - Q, 0), "P6": (A + Q, B - Q, 0), "P7": (A + Q, B - Q, 0),
              "P7-done": (0, B - Q, 0), "P8": (0, B - Q, 0)}
    t0 = time.monotonic()
    while not os.path.exists(stop_file) and time.monotonic() - t0 < 600:
        store, dropped, inflight = values[current_phase()]
        rec(record, "sys", topic="$SYS/broker/store/messages/count", value=str(store))
        rec(record, "sys", topic="$SYS/broker/publish/messages/dropped", value=str(dropped))
        rec(record, "sys", topic="$SYS/broker/messages/inflight", value=str(inflight))
        rec(record, "sys", topic="$SYS/broker/clients/connected", value="2")
        time.sleep(0.2)
    rec(record, "end", received=1, version="mosquitto version 2.0.22", recorder_failed=False)
    print("sysreader end")
    sys.exit(0)

if cmd == "discard":
    rec(opt("--record"), "discard", client_id="egw-probe-hold", connected=True, session_present=False, reason="0:Success")
    print("discarded: client_id=egw-probe-hold session_present=False")
    sys.exit(0)

if cmd == "verdict":
    spec = importlib.util.spec_from_file_location("broker_hold_real", os.environ["EGW_REAL_PROBE"])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.exit(mod.main(sys.argv[1:]))

print(f"stub probe: unhandled {sys.argv[1:]}", file=sys.stderr)
sys.exit(2)
'''


FAST = {
    "EGW_PROBE_A": "6", "EGW_PROBE_B": "4", "EGW_PROBE_W": "6", "EGW_PROBE_Q": "2",
    "EGW_PROBE_P0_S": "1", "EGW_PROBE_P1_S": "0", "EGW_PROBE_HOLD1_S": "1", "EGW_PROBE_HOLD2_S": "1",
    "EGW_PROBE_P4_S": "3", "EGW_PROBE_P7_LIMIT_S": "20", "EGW_PROBE_P7_GRACE_S": "5", "EGW_PROBE_P8_S": "1",
    "EGW_PROBE_SETUP_LIMIT_S": "300", "EGW_PROBE_STEP_TIMEOUT_S": "60", "EGW_PROBE_CLIENT_START_S": "10",
    "EGW_HEALTH_LIMIT_S": "3", "EGW_HEALTH_STEP_S": "1",
}


class ProbeBench(Bench):
    """The drivers' bench with this module's guest stubs and the probe stub."""

    def __init__(self, tmp_path: Path) -> None:
        super().__init__(tmp_path)
        for name, text in (("docker", DOCKER_STUB), ("systemd-run", SYSTEMD_RUN_STUB), ("systemctl", SYSTEMCTL_STUB)):
            _write(self.guest_bin / name, text, executable=True)
        self.probe = _write(tmp_path / "probe_stub.py", PROBE_STUB, executable=True)
        # the secrets file of runbook 5.2 also carries the controller's GUEST
        # settings, among them the schema directory relative to the deployment
        # tree: a host step that sources it and then runs the simulator fails,
        # which is what the C3 session of 2026-09-23 met on its first step
        with open(self.home / "egw-tcg" / ".env", "a", encoding="utf-8") as fh:
            fh.write("EGW_SCHEMA_DIR=src/schemas\nMOSQUITTO_CONTROLLER_PASSWORD=stub-controller-password\n")
        # the bench's scp, behind a wrapper that can be made slow
        (self.bin / "scp").rename(self.bin / "scp.real")
        _write(self.bin / "scp", '#!/bin/sh\n[ -z "${EGW_STUB_SCP_DELAY_S:-}" ] || sleep "$EGW_STUB_SCP_DELAY_S"\n'
                                 'exec "$(dirname "$0")/scp.real" "$@"\n', executable=True)
        self.cgroup_root = tmp_path / "cg"
        self.cgroup_root.mkdir()
        self.extra.update(FAST)
        self.extra.update({
            "EGW_PROBE_TOOL": str(self.probe),
            "EGW_REAL_PROBE": str(REAL_PROBE),
            "PROBE_CGROUP_ROOT": str(self.cgroup_root),
            "PROBE_DOCKER_ROOT": str(self.guest_root / "var" / "lib" / "docker"),
        })

    def start(self, **overrides) -> subprocess.Popen:
        return subprocess.Popen(["bash", str(self.drivers / "broker_measure.sh")], env=self.env(**overrides),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def run_driver(self, **overrides) -> subprocess.CompletedProcess:
        return self.run("broker_measure.sh", timeout=300, **overrides)

    def probe_attempt(self) -> Path:
        found = sorted(p for p in self.attempts.iterdir() if "broker-hold" in p.name)
        assert found, f"no broker-hold attempt under {self.attempts}"
        return found[-1]

    def probe_verdicts(self) -> dict:
        return json.loads((self.probe_attempt() / "attempt.json").read_text(encoding="utf-8"))

    def phases(self) -> dict:
        out: dict = {}
        path = self.probe_attempt() / "environment" / "probe" / "phases.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            out.setdefault(r["phase"], {}).update({k: v for k, v in r.items() if k != "phase"})
        return out

    def docker_state(self) -> dict:
        return json.loads(Path(str(self.log) + ".docker.json").read_text(encoding="utf-8"))

    def docker_log(self) -> str:
        try:
            return Path(str(self.log) + ".dockerlog").read_text(encoding="utf-8")
        except OSError:
            return ""

    def marker(self, name: str) -> bool:
        return Path(str(self.log) + "." + name).exists()

    def wait_for(self, predicate, limit_s: float = 60.0) -> None:
        t0 = time.monotonic()
        while time.monotonic() - t0 < limit_s:
            if predicate():
                return
            time.sleep(0.2)
        raise AssertionError("the condition did not come about in time")

    def pid_of(self, name: str) -> int | None:
        try:
            return int(Path(str(self.log) + "." + name + "_pid").read_text().strip())
        except (OSError, ValueError):
            return None


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@pytest.fixture
def pbench(tmp_path: Path) -> ProbeBench:
    return ProbeBench(tmp_path)


def _hold_p7_end_epoch(bench: ProbeBench) -> float:
    from datetime import datetime, timezone
    path = bench.probe_attempt() / "environment" / "probe" / "hold_p7.jsonl"
    end = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if '"end"' in l][-1]
    t = end["t_utc"].rstrip("Z")
    return datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc).timestamp()


# --------------------------------------------------------------------------
# PR43-01: the redelivery client is waited for, with a bound
# --------------------------------------------------------------------------

def test_p7_ends_after_the_client_ended_and_captures_its_status(pbench):
    result = pbench.run_driver(EGW_STUB_P7_DELAY_S="3")
    assert result.returncode == 0, report(result)
    verdicts = pbench.probe_verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["broker_verdict"] == "supports"
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=stopped"
    phases = pbench.phases()
    assert phases["P7"]["hold_p7_exit"] == "0"
    assert "limit_reached" not in phases["P7"]
    assert phases["P7"]["end_epoch"] >= _hold_p7_end_epoch(pbench) - 1, "P7 ended before the client's end record"
    assert not pbench.marker("hold_p7_term"), "the driver ended a client that was still finishing"
    assert phases["P8"]["sysreader_exit"] == "0"
    assert not _alive(pbench.pid_of("hold_p7")) and not _alive(pbench.pid_of("hold_p1"))
    # the guest: the stack stopped and started, the probe created and removed by its label
    dlog = pbench.docker_log()
    assert "compose stop -t 60" in dlog and "compose start" in dlog
    assert dlog.index("compose stop -t 60") < dlog.index("run -d --name egw-probe-broker") < dlog.index("rm -f egw-probe-broker") < dlog.index("compose start")
    assert pbench.docker_state()["containers"] == {} and pbench.docker_state()["volumes"] == {}
    env = pbench.probe_attempt() / "environment" / "probe"
    for name in ("verdict.json", "recorder.csv", "broker.log", "probe_state.json", "mosquitto.measure.conf", "acl.measure"):
        assert (env / name).is_file(), name
    assert json.loads((env / "probe_state.json").read_text())["oom_killed"] is False
    exported = list((pbench.out / "runs").glob("*/*broker-hold-measurement*"))
    assert exported and (exported[0] / "SHA256SUMS").is_file(), "no verified package reached output_test"


def test_generate_never_inherits_a_schema_directory_from_the_callers_environment(pbench):
    # the documented host set-up exports the guest's EGW_SCHEMA_DIR in the
    # caller's shell; the venv-only step must resolve the clone's schemas
    # whatever was inherited (the stub's generate fails on a path that is
    # not a directory, as the real one does)
    result = pbench.run_driver(EGW_SCHEMA_DIR="/nonexistent/guest/deployment/schemas")
    assert result.returncode == 0, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["broker_verdict"] == "supports" and verdicts["system_outcome"] == "pass"
    assert (pbench.probe_attempt() / "environment" / "probe" / "messages.jsonl").stat().st_size > 0


def test_a_client_that_does_not_end_is_ended_by_the_driver_and_the_run_is_inconclusive(pbench):
    result = pbench.run_driver(EGW_STUB_P7_HANG_S="60", EGW_PROBE_P7_LIMIT_S="1", EGW_PROBE_P7_GRACE_S="1")
    assert result.returncode == 3, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["system_outcome"] == "inconclusive"
    assert verdicts["broker_verdict"] == "inconclusive"
    phases = pbench.phases()
    assert phases["P7"]["limit_reached"] is True and "stop_rule_reached" in phases["P7"]
    assert phases["P7"]["hold_p7_exit"] == "ended-by-driver"
    assert pbench.marker("hold_p7_term"), "the client was not ended"
    assert not _alive(pbench.pid_of("hold_p7"))
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=stopped"


# --------------------------------------------------------------------------
# PR43-05: restoration, ownership, completion
# --------------------------------------------------------------------------

def test_an_interruption_reaps_the_clients_and_restores_the_stack(pbench):
    proc = pbench.start(EGW_PROBE_HOLD1_S="60")
    phases_file = None

    def in_p3():
        nonlocal phases_file
        try:
            phases_file = pbench.probe_attempt() / "environment" / "probe" / "phases.jsonl"
            return '"P3"' in phases_file.read_text(encoding="utf-8")
        except (AssertionError, OSError):
            return False

    pbench.wait_for(in_p3, 90)
    hold_pid = pbench.pid_of("hold_p1")
    assert _alive(hold_pid)
    proc.send_signal(signal.SIGINT)
    out, err = proc.communicate(timeout=120)
    assert proc.returncode == 130, f"exit={proc.returncode}\n{out}\n{err}"
    verdicts = pbench.probe_verdicts()
    assert verdicts["status"] == "interrupted"
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=stopped"
    assert not _alive(hold_pid), "the holding client outlived the driver"
    assert pbench.marker("sys_term") or not _alive(pbench.pid_of("sys"))
    dlog = pbench.docker_log()
    assert "compose start" in dlog and "rm -f egw-probe-broker" in dlog
    assert pbench.docker_state()["containers"] == {}
    assert all(s["state"] == "running" for s in pbench.docker_state()["services"].values())


def test_an_interruption_while_the_stack_is_being_stopped_still_restores_it(pbench):
    proc = pbench.start(EGW_STUB_FAIL="stack-stop-hang", EGW_STUB_HANG_S="4")
    pbench.wait_for(lambda: "compose stop -t 60" in pbench.docker_log(), 60)
    time.sleep(0.5)
    proc.send_signal(signal.SIGINT)
    out, err = proc.communicate(timeout=120)
    assert proc.returncode == 130, f"exit={proc.returncode}\n{out}\n{err}"
    dlog = pbench.docker_log()
    assert "compose start" in dlog, "the stack, stopped by a command that returned after the interrupt, was not started again"
    assert all(s["state"] == "running" for s in pbench.docker_state()["services"].values())
    assert pbench.probe_verdicts()["restoration"].startswith("stack=healthy")


def test_a_container_of_the_probes_name_that_exists_stops_the_driver_before_it_touches_anything(pbench):
    env = pbench.env()
    env["PATH"] = f"{pbench.guest_bin}{os.pathsep}{env['PATH']}"
    subprocess.run(["docker", "run", "-d", "--name", "egw-probe-broker", "--label", "egw.probe.attempt=someone-else", "img"],
                   env=env, check=True, capture_output=True)
    result = pbench.run_driver()
    assert result.returncode == 2, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert "already exists" in verdicts["reason"]
    dlog = pbench.docker_log()
    assert "compose stop" not in dlog and "rm -f" not in dlog
    assert "egw-probe-broker" in pbench.docker_state()["containers"], "a container this attempt did not create was removed"


def test_a_restoration_that_fails_never_yields_a_passing_session(pbench):
    result = pbench.run_driver(EGW_STUB_FAIL="stack-start")
    assert result.returncode == 3, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["broker_verdict"] == "supports", "the broker observation must be kept apart"
    assert verdicts["system_outcome"] != "pass"
    assert verdicts["restoration"].startswith("stack=unknown") or verdicts["restoration"].startswith("stack=not-healthy")
    assert "NOT fully restored" in verdicts["reason"]
    assert json.loads((pbench.probe_attempt() / "environment" / "probe" / "verdict.json").read_text())["result"] == "supports"


def test_a_stack_not_healthy_again_is_a_stop_rule_and_not_a_pass(pbench):
    result = pbench.run_driver(EGW_STUB_FAIL="healthy-again")
    assert result.returncode == 3, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["broker_verdict"] == "supports"
    assert verdicts["system_outcome"] == "inconclusive"
    assert verdicts["restoration"].startswith("stack=not-healthy")
    assert "stop rule" in verdicts["reason"]


def test_a_record_that_could_not_be_made_never_yields_a_passing_session(pbench):
    result = pbench.run_driver(EGW_STUB_SCP_FAIL="recorder.csv")
    assert result.returncode == 3, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["system_outcome"] == "inconclusive"
    assert "not recorded" in verdicts["reason"] and "recorder" in verdicts["reason"]
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=stopped"


def test_a_broker_that_refuses_its_configuration_is_r1_and_the_guest_is_restored(pbench):
    result = pbench.run_driver(EGW_STUB_FAIL="probe-refused")
    assert result.returncode == 1, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["broker_verdict"] == "refutes"
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=stopped"
    assert "rm -f egw-probe-broker" in pbench.docker_log()


def _recorder_pid(pbench: ProbeBench) -> int | None:
    units = list(Path(str(pbench.log)).parent.glob(Path(str(pbench.log)).name + ".unit.*"))
    if not units:
        return None
    try:
        return int(units[0].read_text().strip())
    except ValueError:
        return None


def _steps(pbench: ProbeBench) -> list[str]:
    path = pbench.probe_attempt() / "commands.jsonl"
    return [json.loads(l)["name"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# --------------------------------------------------------------------------
# B1: the recorder's real state, the stop verified
# --------------------------------------------------------------------------

def test_a_recorder_whose_start_was_not_confirmed_is_still_found_stopped_and_fetched(pbench):
    result = pbench.run_driver(EGW_STUB_FAIL="recorder-start-late")
    assert result.returncode == 2, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["system_outcome"] == "not-run"
    steps = _steps(pbench)
    assert "recorder-stop" in steps and "recorder-fetch" in steps, steps
    assert not _alive(_recorder_pid(pbench)), "the recorder unit was left running"
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=stopped"
    assert (pbench.probe_attempt() / "environment" / "probe" / "recorder.csv").is_file()


def test_a_recorder_stop_that_failed_is_never_declared_stopped_even_with_a_readable_csv(pbench):
    result = pbench.run_driver(EGW_STUB_FAIL="recorder-stop-fails")
    assert result.returncode == 3, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["broker_verdict"] == "supports", "the broker observation is kept apart from the cleanup"
    assert verdicts["system_outcome"] != "pass"
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=unknown"
    assert "not verified stopped" in verdicts["reason"]
    assert (pbench.probe_attempt() / "environment" / "probe" / "recorder.csv").is_file(), "the CSV is fetched anyway"
    pid = _recorder_pid(pbench)
    if _alive(pid):
        os.kill(pid, signal.SIGTERM)


# --------------------------------------------------------------------------
# B2: the stop rules enforced
# --------------------------------------------------------------------------

def test_the_setup_budget_is_one_budget_and_no_stage_starts_beyond_it(pbench):
    # the stop itself succeeds after 4 s; with a 3 s budget nothing after it may start
    result = pbench.run_driver(EGW_STUB_FAIL="stack-stop-hang", EGW_STUB_HANG_S="4", EGW_PROBE_SETUP_LIMIT_S="3",
                               EGW_PROBE_STEP_TIMEOUT_S="60")
    assert result.returncode in (2, 3), report(result)
    dlog = pbench.docker_log()
    assert "compose stop -t 60" in dlog
    assert "run -d --name egw-probe-broker" not in dlog, "the probe was created after the setup budget was spent"
    assert "compose start" in dlog
    verdicts = pbench.probe_verdicts()
    assert "setup budget" in verdicts["reason"]
    assert verdicts["restoration"].startswith("stack=healthy")
    assert all(s["state"] == "running" for s in pbench.docker_state()["services"].values())


def test_a_configuration_transfer_that_spends_the_budget_starts_no_probe(pbench):
    # the two measurement copies take 4 s each; with a 6 s budget the second
    # is cut by what is left of it, and the probe broker is never started
    result = pbench.run_driver(EGW_STUB_SCP_DELAY_S="4", EGW_PROBE_SETUP_LIMIT_S="6", EGW_PROBE_STEP_TIMEOUT_S="60")
    assert result.returncode in (2, 3), report(result)
    dlog = pbench.docker_log()
    assert "compose stop -t 60" in dlog
    assert "run -d --name egw-probe-broker" not in dlog, "the probe was started after the setup budget was spent"
    assert "compose start" in dlog
    steps = _steps(pbench)
    assert "probe-start" not in steps and "recorder-start" not in steps and "p2-publish" not in steps, steps
    verdicts = pbench.probe_verdicts()
    assert "setup budget" in verdicts["reason"]
    assert verdicts["restoration"].startswith("stack=healthy")
    assert all(s["state"] == "running" for s in pbench.docker_state()["services"].values())


def test_a_recorder_transfer_that_spends_the_budget_starts_no_recorder_and_removes_the_probe(pbench):
    # the copies take 5 s each: the two measurement copies fit a 14 s budget,
    # the probe starts, and the recorder's copy is cut by what is left
    result = pbench.run_driver(EGW_STUB_SCP_DELAY_S="5", EGW_PROBE_SETUP_LIMIT_S="14", EGW_PROBE_STEP_TIMEOUT_S="60")
    assert result.returncode in (2, 3), report(result)
    dlog = pbench.docker_log()
    assert "run -d --name egw-probe-broker" in dlog, "this case needs the probe to have started"
    ssh_log = _ssh_text(pbench)
    assert "systemd-run" not in ssh_log, "the recorder was started after the setup budget was spent"
    steps = _steps(pbench)
    assert "recorder-start" not in steps and "p2-publish" not in steps, steps
    assert "rm -f egw-probe-broker" in dlog and "compose start" in dlog
    assert pbench.docker_state()["containers"] == {}
    verdicts = pbench.probe_verdicts()
    assert "setup budget" in verdicts["reason"]
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=none"


def test_the_bounded_dispatchers_refuse_a_spent_allowance_without_invoking_anything(tmp_path):
    # the boundary itself: gxt and gcpt given 0, '' or a non-number call
    # nothing (a 'timeout 0' would disable the bound, not enforce it)
    driver = (REPO_ROOT / "tools" / "session" / "broker_measure.sh").read_text(encoding="utf-8")
    import re
    funcs = "".join(m.group(0) for m in re.finditer(r"^(budget_spent|gxt|gcpt)\(\) \{.*?^\}\n", driver, re.S | re.M))
    assert "gxt() {" in funcs and "gcpt() {" in funcs and "budget_spent() {" in funcs
    script = funcs + """
ex() { echo "CALLED $*"; return 0; }
EXIT_NOT_REACHED=97
SESSION=/nonexistent
for limit in 0 '' abc; do
    gxt "$limit" A step 'echo hi'; echo "gxt[$limit]=$?"
    gcpt "$limit" A copy src dst; echo "gcpt[$limit]=$?"
done
gxt 5 A step 'echo hi'; echo "gxt[5]=$?"
"""
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert "CALLED" not in result.stdout.split("gxt[abc]")[0], result.stdout
    for limit in ("0", "", "abc"):
        assert f"gxt[{limit}]=124" in result.stdout and f"gcpt[{limit}]=124" in result.stdout, result.stdout
    assert "CALLED" in result.stdout and "gxt[5]=0" in result.stdout, result.stdout
    assert result.stderr.count("was NOT started") == 6


def test_the_session_drivers_look_for_qemu_by_its_process_name_never_by_command_line():
    # the C3 session of 2026-09-23: the close driver's 'pgrep -f' matched the
    # shell that invoked it, whose command line held the pattern, and reported
    # a running guest where there was none
    import re
    for name in ("guest_session_open.sh", "guest_session_close.sh"):
        text = (REPO_ROOT / "tools" / "session" / name).read_text(encoding="utf-8")
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        assert not re.search(r"pgrep\s+-[a-zA-Z]*f[a-zA-Z]*\s+qemu", code), f"{name} matches qemu by command line"
        assert re.search(r"pgrep\s+-[a-zA-Z]*x[a-zA-Z]*\s+qemu-system-aarch64", code), f"{name} does not match qemu by its exact name"


def _ssh_text(pbench: ProbeBench) -> str:
    try:
        return pbench.log.read_text(encoding="utf-8")
    except OSError:
        return ""


def test_a_p4_stop_rule_ends_the_measurement_before_p5_and_p7(pbench):
    result = pbench.run_driver(EGW_STUB_FAIL="no-disconnect-line", EGW_PROBE_P4_S="2")
    assert result.returncode == 3, report(result)
    steps = _steps(pbench)
    assert "p2-publish" in steps and "p5-publish" not in steps, steps
    assert not (pbench.probe_attempt() / "environment" / "probe" / "hold_p7.stdout.txt").exists() \
        or "SUBSCRIBED" not in (pbench.probe_attempt() / "environment" / "probe" / "hold_p7.stdout.txt").read_text()
    phases = pbench.phases()
    assert phases["P4"]["limit_reached"] is True and "stop_rule_reached" in phases["P4"]
    assert "P5" not in phases and "P7" not in phases
    assert "P8" in phases and "discard" in steps, "the final readings and the discard still run"
    verdicts = pbench.probe_verdicts()
    assert verdicts["broker_verdict"] == "inconclusive" and verdicts["system_outcome"] == "inconclusive"
    assert "disconnection line" in verdicts["reason"]
    assert verdicts["restoration"] == "stack=healthy probe=removed recorder=stopped"
    # the partial observation is preserved
    assert (pbench.probe_attempt() / "environment" / "probe" / "hold_p1.jsonl").stat().st_size > 0


# --------------------------------------------------------------------------
# C2: ownership is the label being exactly this attempt's id
# --------------------------------------------------------------------------

def test_a_container_whose_label_merely_contains_the_attempt_id_is_left_alone(pbench):
    result = pbench.run_driver(EGW_STUB_LABEL_SUFFIX="-x")
    assert result.returncode == 3, report(result)
    verdicts = pbench.probe_verdicts()
    # a container not established as this attempt's is neither removed nor
    # read as its evidence: its log and state are not fetched, so the broker
    # observation is inconclusive, and the session is not a pass
    assert verdicts["broker_verdict"] == "inconclusive"
    assert verdicts["system_outcome"] != "pass"
    assert "did NOT create" in verdicts["reason"]
    assert verdicts["restoration"].startswith("stack=healthy probe=unknown")
    assert "egw-probe-broker" in pbench.docker_state()["containers"], "a container not carrying this attempt's label was removed"
    assert "rm -f" not in pbench.docker_log()


def test_a_volume_whose_label_is_not_exactly_the_attempt_id_is_left_alone(pbench):
    result = pbench.run_driver(EGW_STUB_VOLUME_LABEL_SUFFIX="-x")
    assert result.returncode == 3, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["broker_verdict"] == "supports"
    assert verdicts["system_outcome"] != "pass"
    assert "does not carry this attempt's label" in verdicts["reason"]
    assert pbench.docker_state()["volumes"], "a volume not carrying this attempt's label was removed"
    assert "volume rm" not in pbench.docker_log()


def test_a_publisher_that_is_not_exact_is_a_missing_record_not_a_refutation(pbench):
    result = pbench.run_driver(EGW_STUB_PUBLISH_EXIT="1")
    assert result.returncode == 3, report(result)
    verdicts = pbench.probe_verdicts()
    assert verdicts["broker_verdict"] == "inconclusive"
    assert verdicts["system_outcome"] == "inconclusive"
    assert json.loads((pbench.probe_attempt() / "environment" / "probe" / "verdict.json").read_text())["refuted"] == []
