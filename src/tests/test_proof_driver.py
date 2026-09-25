"""Cases for tools/session/proof.sh, the session driver of the finite proof of
ADR 0011, and its two helpers proof_session.py and proof_helpers_check.py.

The driver is executed for real on the bench of ``test_session_drivers``
(the real ``local_export``, this interpreter as the venv, the ssh and scp
stubs that run guest commands on this machine against a fake guest root) and
on top of it this module installs:

* a ``python`` first on PATH that intercepts ONLY ``-m egw_experiments run``
  - the harness step the driver runs through the host preamble - and hands
  it to a stub harness which records its argv and environment, applies the
  fault to the guest's docker state as the restart hook would, and writes a
  run directory shaped by ``test_proof_evaluator``'s own builders (the
  scenario that supports, one that refutes, one that is inconclusive, the
  campaign's MAX_SAMPLE_GAP_S deviation in the one form run.py records it),
  with the validity, the reasons, the warnings and the seal run.py's own
  functions give for it, so the REAL evaluator runs over it; every other
  call goes to this interpreter unchanged;
* a guest ``docker`` that holds the controller container's state on disk
  (the same object, started later, after the fault) and the five other
  services, steerable through ``EGW_STUB_FAIL``;
* the section 6.1 helper stub extended with the runbook's own ``keep`` and
  stubs of ``_mline`` (thirteen fields, ``started_at`` moving with the
  fault; one reading can be made to fail), ``wait_ready`` (one that can take
  its time), ``metrics`` and ``config_identity``;
* a "runbook" whose 6.1 heredoc is that helper stub, named to the driver
  with ``EGW_PROOF_RUNBOOK``, so the helpers check passes on the bench and
  fails against the real runbook.

What these cases show is the driver's own behaviour: the prerequisites that
leave the harness unstarted, the values and stop rules recorded before the
first ``drained``, the harness command line, the restart shown from the
driver's records, the three verdicts kept apart (the harness's own validity
quoted as recorded and admitted only as E-12 states, by the evaluator's own
``harness_admission``), the 50-minute rule, the restoration in every ending,
the optional extension never run unless asked, and what reaches the
package. They say nothing about a real broker, controller, guest or network.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import json as _json
import os
import os as _os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the session drivers are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None or shutil.which("timeout") is None:
    pytest.skip("bash and timeout are needed", allow_module_level=True)

from test_session_drivers import EXPECT_SERVICES, ITEST_HELPERS, TUNNEL_SH, Bench, _write, report  # noqa: E402
from test_proof_hooks import runbook_function  # noqa: E402
from test_proof_evaluator import STOP_RULE_ATTEMPT, STOP_RULE_HEALTHY  # noqa: E402
from test_experiments_run import CONFIG_IDENTITY  # noqa: E402

from egw_experiments import plan_gen  # noqa: E402
from egw_experiments import proof_evaluator as pe  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
SESSION_DIR = REPO_ROOT / "tools" / "session"
RUNBOOK = REPO_ROOT / "docs" / "setup" / "qemu_integrated_gateway.md"
ADR = REPO_ROOT / "docs" / "adr" / "0011-controller-restart-recovery.md"
SLUG = "finite-proof-adr-0011"
RID = "proof-adr0011-r01"
COMMIT = CONFIG_IDENTITY["controller_source_commit"]  # the candidate's source commit, as config_identity names it
MASTER_SEED = "42"
# The 20-minute rule runs from the candidate's start (the containers'
# StartedAt, which the stub docker takes from the real clock at the stack's
# stub boot): the bench's limit leaves room for the records taken before the
# wait, and the tests of the rule move the boot into the past.
HEALTH_LIMIT_S = 12
FAST = {
    "EGW_PROOF_MASTER_SEED": MASTER_SEED,
    "EGW_HEALTH_LIMIT_S": str(HEALTH_LIMIT_S), "EGW_HEALTH_STEP_S": "1", "EGW_READY_LIMIT_S": "5",
    "EGW_PROOF_ATTEMPT_LIMIT_S": "600",
}
# THE STUB GUEST'S CLOCK IS STEADY. The 20-minute rule compares instants of
# the guest clock taken seconds apart (docker's StartedAt, the samples of the
# shared wait); on this WSL2 host the wall clock is stepped backwards by
# about 2 s every 30 s and drifts ahead between the steps (LOG.md), so two
# wall-clock instants of the bench can reorder by several seconds. The stub
# guest therefore keeps ONE clock of its own: the host's monotonic clock
# from a real anchor (an anchor file beside the bench log, created by the
# first reader), read by the docker stub, the harness stub, the guest's
# stub `date` and the bench's own writers alike, and every StartedAt is
# the boot plus a fixed offset. The driver under test keeps its own 3 s
# band for a real guest's clock; the bench never relies on it.


def _clock_anchor(path=None):
    path = path or _os.environ["EGW_STUB_LOG"] + ".clock"
    try:
        with open(path, encoding="utf-8") as fh:
            return _json.load(fh)
    except (OSError, ValueError):
        pass
    anchor = {"epoch0": _time.time(), "mono0": _time.monotonic()}
    try:
        with open(path, "x", encoding="utf-8") as fh:
            _json.dump(anchor, fh)
    except FileExistsError:
        with open(path, encoding="utf-8") as fh:
            return _json.load(fh)
    return anchor


def fake_now(path=None):
    """The stub guest's clock: steady, from a real anchor."""
    anchor = _clock_anchor(path)
    return datetime.fromtimestamp(anchor["epoch0"] + (_time.monotonic() - anchor["mono0"]), timezone.utc)


def instant(when):
    """As docker prints StartedAt: RFC 3339, nanoseconds, UTC."""
    return when.strftime("%Y-%m-%dT%H:%M:%S") + ".%09dZ" % (when.microsecond * 1000)


def initial_state(path=None):
    """The stack's stub boot: a second before its first reading, or
    EGW_STUB_BOOT_AGE_S seconds ago; the controller container started two
    seconds after the five others."""
    boot = fake_now(path) - timedelta(seconds=float(_os.environ.get("EGW_STUB_BOOT_AGE_S", "1")))
    return {"boot": instant(boot),
            "controller": {"id": "0f" * 32, "started": instant(boot + timedelta(seconds=2)),
                           "status": "running", "starts": 0}}


def parse(text):
    """A StartedAt back to a datetime (whole seconds)."""
    return datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


# The same functions, as the stubs' source (one text, never a second copy).
STUB_CLOCK = ("import json as _json, os as _os, time as _time\nfrom datetime import datetime, timedelta, timezone\n\n"
              + "\n".join(inspect.getsource(f) for f in (_clock_anchor, fake_now, instant, initial_state, parse)))

DATE_STUB = '''#!/usr/bin/env python3
"""Stub date of the stub guest: the steady clock of the bench, in the forms
the guest scripts ask for (`date +%s`, `date -u +%Y-%m-%dT%H:%M:%SZ`)."""
import sys
@@CLOCK@@

fmt = "%a %b %e %H:%M:%S UTC %Y"
for arg in sys.argv[1:]:
    if arg.startswith("+"):
        fmt = arg[1:]
    elif arg != "-u":
        print("stub date: unsupported argument %r" % arg, file=sys.stderr)
        sys.exit(1)
now = fake_now()
fmt = fmt.replace("%s", str(int(now.timestamp()))).replace("%N", "%09d" % (now.microsecond * 1000))
print(now.strftime(fmt))
'''.replace("@@CLOCK@@", STUB_CLOCK)

# --------------------------------------------------------------------------
# Stubs of this module
# --------------------------------------------------------------------------

PYTHON_STUB = """#!/bin/sh
# The 'python' of the activated venv on the bench: the harness step's
# 'python -m egw_experiments run' goes to the stub harness, everything else
# to the real interpreter.
if [ "${1:-}" = -m ] && [ "${2:-}" = egw_experiments ] && [ "${3:-}" = run ]; then
    shift 3
    exec "$EGW_REAL_PYTHON" "$EGW_STUB_HARNESS_PY" "$@"
fi
exec "$EGW_REAL_PYTHON" "$@"
"""

HARNESS_STUB = r'''"""Stub of 'egw_experiments run' for the proof driver: records what it was
given, applies the fault to the guest's docker state as the restart hook
would have, and writes a sealed run directory shaped by the evaluator tests'
builders, so the real evaluator evaluates it. A signal that reaches it
(the real harness has no handler and dies where it is) is recorded in
LOG.harness-signalled before it ends, so a case can tell whether the
driver's interrupt reached the harness at all."""
import json
import os
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path

SRC = Path(os.environ["EGW_STUB_SRC"])
sys.path[:0] = [str(SRC), str(SRC / "tests")]
LOG = os.environ["EGW_STUB_LOG"]
failures = "," + os.environ.get("EGW_STUB_FAIL", "") + ","


def fails(token):
    return f",{token}," in failures


def signalled(signum, frame):
    with open(LOG + ".harness-signalled", "a", encoding="utf-8") as fh:
        fh.write(f"{signum}\n")
    sys.exit(128 + signum)


signal.signal(signal.SIGINT, signalled)
signal.signal(signal.SIGTERM, signalled)

argv = sys.argv[1:]
with open(LOG + ".harness-argv", "w", encoding="utf-8") as fh:
    json.dump({"argv": argv,
               "env": {k: os.environ.get(k) for k in ("DRAIN_QUIET_S", "DRAIN_STEP_S", "DRAIN_LIMIT_S", "EGW_CLONE")},
               "cwd": os.getcwd()}, fh, indent=2)
hang = os.environ.get("EGW_STUB_HANG_S")
if hang:
    time.sleep(float(hang))
forced = os.environ.get("EGW_STUB_HARNESS_EXIT")
if forced:
    print(f"[harness] stub: refusing with exit {forced}", file=sys.stderr)
    sys.exit(int(forced))


def opt(name):
    return argv[argv.index(name) + 1]


run_id = opt("--run-id")
base = Path(opt("--base-dir"))
@@CLOCK@@

# The fault, as the restart hook applies it on the guest: the same container
# object, started later (a kill + start: two minutes after the boot per
# start, on the stub guest's steady clock); the docker stub reads this state.
state_path = LOG + ".proof-docker.json"
try:
    with open(state_path, encoding="utf-8") as fh:
        state = json.load(fh)
except (OSError, ValueError):
    state = initial_state()
controller = state["controller"]
if not fails("restart-not-shown"):
    controller["starts"] += 1
    controller["started"] = instant(parse(state["boot"]) + timedelta(seconds=120 * controller["starts"]))
    controller["status"] = "running"
if fails("controller-replaced"):
    controller["id"] = "1e" * 32
with open(state_path, "w", encoding="utf-8") as fh:
    json.dump(state, fh)
open(LOG + ".midrun", "w", encoding="utf-8").close()

from egw_experiments import proof_evaluator as pe  # noqa: E402
from egw_experiments import run as run_mod  # noqa: E402
from egw_experiments.checksums import write_sha256sums  # noqa: E402
from test_proof_evaluator import (  # noqa: E402
    D1, GAP_WINDOW, LINES, NS, _gap_collector_csv, _manifest, _rows, _write_run_dir)

result = os.environ.get("EGW_STUB_PROOF_RESULT", "supports")
kwargs = {}
if result == "refutes":
    kwargs["lines"] = LINES + [("a-mid", D1, 0, "accepted", 1_300 * NS, None)]
elif result == "inconclusive":
    kwargs["rows"] = _rows(last_pre=(0, 0))
# The manifest as the harness writes it: the simulator's exit status and the
# record of its own copy of the events (the first of the two copies), beside
# the item-18 records the evaluator tests' builder holds; its validity, its
# reasons, the resource source, the mandatory artefacts missing and the
# warnings are what run.py's own functions give for the run directory as
# written (compute_validity, missing_mandatory_artifacts, ingest_resources),
# and SHA256SUMS is withheld while a mandatory artefact is missing, as
# run.py withholds it - no validity reason is written here. Steered
# through EGW_STUB_SAMPLING_GAP ('gap': the collector file the harness's
# own fetch wrote has a 6 s sampling gap, so the ingest rejects it and the
# run is the campaign's MAX_SAMPLE_GAP_S deviation exactly as the harness
# records it; 'gap-and-other-problem': the same file with one row whose
# cpu_pct is not a finite number beside the gap), EGW_STUB_SIMULATOR_EXIT
# (the simulator failed), EGW_STUB_EVENTS_FETCH ('failed': the copy failed
# and a stale file is left; 'missing': no record and no file) and
# EGW_STUB_NO_RESOURCES (no collector file ingested into the run
# directory).
manifest = _manifest()
simulator_exit = int(os.environ.get("EGW_STUB_SIMULATOR_EXIT", "0"))
manifest["simulator_returncode"] = simulator_exit
sampling_gap = os.environ.get("EGW_STUB_SAMPLING_GAP", "")
events_fetch = os.environ.get("EGW_STUB_EVENTS_FETCH", "ok")
# The evaluator's builder carries an ok events_fetch record by default:
# "missing" means no record at all, so it is removed, never left behind.
manifest.pop("events_fetch", None)
if events_fetch != "missing":
    manifest["events_fetch"] = {
        "template": "scp egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl \"{dest}\"",
        "command": "scp egw-tcg:/opt/egw/deployment/data/events/%s/events.jsonl dest" % run_id,
        "attempts": [{"attempt": 1, "returncode": 0 if events_fetch == "ok" else 1, "dest_exists": True}],
        "ok": events_fetch == "ok",
    }
kwargs["manifest"] = manifest
with tempfile.TemporaryDirectory() as tmp:
    run_dir = _write_run_dir(Path(tmp), name=run_id, seal=False, **kwargs)
    if events_fetch == "missing":
        (run_dir / "events.jsonl").unlink()
    # What the real harness keeps beside the proof's evidence: the collector's
    # files and the item-18 hooks' streams.
    collector = run_dir / "logs" / "collector"
    collector.mkdir(parents=True)
    (collector / f"resources-{run_id}.csv").write_text("ts_utc,service\n2026-09-25T10:00:00Z,egw-controller-1\n", "utf-8")
    (collector / f"resources-{run_id}.csv.diagnostics.log").write_text(
        "2026-09-25T10:00:00Z start: collector_sha256=stub\n2026-09-25T10:00:01Z inventory: missing=\n"
        "2026-09-25T10:12:02Z stop: samples=722\n", "utf-8")
    (collector / f"resources-{run_id}.csv.lifecycle.csv").write_text(
        "service,container_id,started_at\negw-controller-1,stub,2026-09-25T09:58:00Z\n", "utf-8")
    for name in ("hook-drain.stderr.txt", "hook-twin_snapshot_before.stdout.txt", "hook-twin_snapshot_after.stdout.txt"):
        (run_dir / "logs" / "sut" / name).write_text("", "utf-8")
    # The collector file: ingested as resources.csv (the evaluator's builder
    # wrote it), none at all (EGW_STUB_NO_RESOURCES), or, in the sampling-gap
    # form, the file the harness's own fetch wrote at
    # logs/collector/resources-<run_id>.csv handed to run.ingest_resources
    # with the fetch's source label and the measured window, which rejects
    # it (resources.csv is never written) and records the warning.
    warnings = []
    resource_source = "sut-collector"
    if sampling_gap or os.environ.get("EGW_STUB_NO_RESOURCES"):
        (run_dir / "resources.csv").unlink(missing_ok=True)
        resource_source = "none"
    if sampling_gap:
        fetched = run_dir / pe.fetch_collector_rel(run_id)
        _gap_collector_csv(fetched, other_problem=sampling_gap == "gap-and-other-problem")
        ingested = run_mod.ingest_resources(
            run_dir, fetched, warnings, expected_window_start_utc=GAP_WINDOW[0],
            expected_window_end_utc=GAP_WINDOW[1], source_label=pe.INGEST_SOURCE_FETCH)
        assert ingested is False and not (run_dir / "resources.csv").exists()
    missing = run_mod.missing_mandatory_artifacts(run_dir, "controller_restart")
    validity, reasons = run_mod.compute_validity(
        timed=True, sut_env_present=True, allow_missing_sut_env=False, resource_source=resource_source,
        allow_missing_resources=False, restart_required=True, restart_ok=True, simulator_returncode=simulator_exit,
        skip_warmup=True, condition_id="controller_restart", allow_protocol_deviation=True,
        confirmation_marker_ok=True, collector_hooks=[], missing_artifacts=missing, collector_problems=[],
        sut_log_fetches=manifest["sut_log_fetches"], twin_snapshots=manifest["twin_snapshots"], drain=manifest["drain"],
        events_post_drain_fetch=manifest["events_post_drain_fetch"], config_identity_ok=True)
    manifest.update(validity=validity, validity_reasons=reasons, resource_source=resource_source,
                    missing_mandatory_artifacts=missing, warnings=warnings)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", "utf-8")
    harness_exit = 0 if validity == "valid" and events_fetch == "ok" else 1
    # SHA256SUMS last, and only when no mandatory artefact is missing (run.py
    # withholds it otherwise).
    if not missing and not fails("harness-unsealed"):
        write_sha256sums(run_dir)
    if fails("harness-tampered"):
        # Bytes changed after the seal: SHA256SUMS no longer verifies.
        (run_dir / "sent_events.jsonl").write_text("{}\n", "utf-8")
    dest = base / "raw" / run_id
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(run_dir), str(dest))
# The controller's own event log on the guest, as it stands after the drain
# (what a second fetch, the extension's, reads).
guest_events = Path(os.environ["EGW_STUB_GUEST_ROOT"]) / "opt" / "egw" / "deployment" / "data" / "events" / run_id
guest_events.mkdir(parents=True, exist_ok=True)
shutil.copyfile(dest / "events.post-drain.jsonl", guest_events / "events.jsonl")
# The prefix siblings the hooks write on the host (write-once, as they do).
prefix = Path(os.environ["HOME"]) / "egw-tcg" / "itest"
prefix.mkdir(parents=True, exist_ok=True)
for label in ("before", "after"):
    sibling = prefix / f"{run_id}.twins.{label}.json"
    if not sibling.exists():
        shutil.copyfile(dest / f"twins.{label}.json", sibling)
record = prefix / f"{run_id}.restart.txt"
if not record.exists():
    record.write_text(
        f"run_id={run_id}\ncontainer=egw-controller-1\nphase=before\nguest_epoch=1700000150\n"
        "guest_utc=2026-09-25T10:02:30Z\ncontainer_id=" + "0f" * 32 + "\nstarted_at=2026-09-25T10:00:00.100000000Z\n"
        "status=running\nphase=fault\nfault_exit=0\nphase=after\nguest_epoch=1700000172\n"
        "guest_utc=2026-09-25T10:02:52Z\ncontainer_id=" + controller["id"] + "\nstarted_at=" + controller["started"]
        + "\nstatus=running\nphase=observation\ncontainer_id_same=yes\nstarted_at_changed=yes\n", "utf-8")
print(f"[harness] {run_id}: run directory written at {dest} ({'sealed' if (dest / 'SHA256SUMS').exists() else 'NOT sealed'}); "
      f"validity {manifest['validity']}")
sys.exit(harness_exit)
'''.replace("@@CLOCK@@", STUB_CLOCK)

DOCKER_STUB = r'''#!/usr/bin/env python3
"""Stub docker for the proof driver's guest: the six services, the controller
container's state on disk (the same object started later after the fault),
the kill and the compose start the restart hook issues, and the readings the
guest-state and container records take. Steered through EGW_STUB_FAIL:
'service-oomkilled' (mongodb OOM-killed after the run), 'other-restarted'
(the ditto gateway started again after the run), 'healthy-again-fails' (the
controller unhealthy after the fault), 'kill-fails' (the fault refused)."""
import json
import os
import sys

SERVICES = ("egw-mosquitto-1", "egw-mongodb-1", "egw-ditto-policies-1",
            "egw-ditto-things-1", "egw-ditto-gateway-1", "egw-controller-1")
LOG = os.environ["EGW_STUB_LOG"]
STATE = LOG + ".proof-docker.json"
failures = f",{os.environ.get('EGW_STUB_FAIL', '')},"
@@CLOCK@@


def fails(token):
    return f",{token}," in failures


def load():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return initial_state()


def save(state):
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def midrun():
    return os.path.exists(LOG + ".midrun")


args = sys.argv[1:]
compose = False
while args and (args[0] == "compose" or args[0] == "--env-file"):
    if args[0] == "compose":
        compose = True
        args = args[1:]
    else:
        args = args[2:]
state = load()
if not os.path.exists(STATE):
    save(state)   # the stub boot is fixed at the first reading
with open(LOG + ".proof-dockerlog", "a", encoding="utf-8") as fh:
    fh.write(("compose " if compose else "") + " ".join(args) + "\n")
cmd = args[0] if args else ""
ctl = state["controller"]
BOOT = state["boot"]


def container_id(name):
    if name == SERVICES[5]:
        return ctl["id"]
    return f"{SERVICES.index(name):02d}" + "a" * 62


def started_at(name):
    if name == SERVICES[5]:
        return ctl["started"]
    if fails("other-restarted") and name == SERVICES[4] and midrun():
        return instant(parse(BOOT) + timedelta(seconds=600))
    return BOOT


def status(name):
    if name == SERVICES[5]:
        return ctl["status"]
    return "running"


def health(name):
    if fails("healthy-again-fails") and name == SERVICES[5] and midrun():
        return "unhealthy"
    if fails("service-unhealthy") and name == SERVICES[1]:
        return "unhealthy"
    # A stack whose health checks conclude only EGW_STUB_HEALTHY_AFTER_S
    # seconds after its boot: 'starting' until then.
    settle = os.environ.get("EGW_STUB_HEALTHY_AFTER_S")
    if settle and fake_now() < parse(BOOT) + timedelta(seconds=float(settle)):
        return "starting"
    return "healthy"


def oomkilled(name):
    return "true" if (fails("service-oomkilled") and name == SERVICES[1] and midrun()) else "false"


if compose and cmd == "start":
    if fails("start-fails"):
        print("Error response from daemon: stub start refused", file=sys.stderr)
        sys.exit(1)
    ctl["starts"] += 1
    ctl["started"] = instant(parse(BOOT) + timedelta(seconds=120 * ctl["starts"]))
    ctl["status"] = "running"
    save(state)
    print(" Container egw-controller-1  Started", file=sys.stderr)
    sys.exit(0)
if compose:
    print(f"stub docker compose: nothing to do for {cmd!r}", file=sys.stderr)
    sys.exit(1)
if cmd == "kill":
    if fails("kill-fails"):
        print("Error response from daemon: stub kill refused", file=sys.stderr)
        sys.exit(1)
    ctl["status"] = "exited"
    save(state)
    print("egw-controller-1")
    sys.exit(0)
if cmd == "ps":
    template = args[args.index("--format") + 1] if "--format" in args else "{{.Names}}"
    for name in SERVICES:
        print(template.replace("{{.Names}}", name).replace("{{.Name}}", name)
              .replace("{{.Status}}", f"Up 3 minutes ({health(name)})").replace("{{.State}}", status(name))
              .replace("{{.Health}}", health(name)))
    sys.exit(0)
if cmd == "inspect":
    template = args[args.index("-f") + 1] if "-f" in args else ""
    name = args[-1]
    if name not in SERVICES:
        print(f"Error: No such object: {name}", file=sys.stderr)
        sys.exit(1)
    if "{{if .State.Health}}" in template:
        print(health(name))
    elif ".State.Health" in template:
        print(health(name))
    elif ".State.OOMKilled" in template:
        print(oomkilled(name))
    elif ".RestartCount" in template:
        print("0")
    elif ".State.StartedAt" in template:
        print(started_at(name))
    elif ".State.Status" in template:
        print(status(name))
    elif ".Id" in template:
        print(container_id(name))
    else:
        print("")
    sys.exit(0)
print(f"stub docker: nothing to do for {cmd!r}", file=sys.stderr)
sys.exit(1)
'''.replace("@@CLOCK@@", STUB_CLOCK)

# The section 6.1 helper stub, extended: the runbook's own `keep`, and stubs
# of `_mline` (thirteen fields; started_at follows the controller's starts in
# the docker state), `metrics` (write-once, the same started_at) and
# `config_identity` (the candidate's identity, write-once).
PROOF_HELPERS_EXTRA = r'''
# --- proof driver stubs: _mline, metrics, config_identity ---------------------
_proof_started_at() {
    python3 - "$EGW_STUB_LOG.proof-docker.json" <<'PY'
import json, sys
try:
    starts = json.load(open(sys.argv[1], encoding="utf-8"))["controller"]["starts"]
except Exception:
    starts = 0
print("2026-09-25T10:00:00Z" if starts == 0 else "2026-09-25T10:%02d:35Z" % (2 + starts))
PY
}
_mline() {
    # Every reading is counted (LOG.mline-calls, one line each): 'received' is
    # EGW_STUB_MLINE_RECEIVED from the reading EGW_STUB_MLINE_RECEIVED_FROM_CALL
    # on (the first, by default), and 0 before it. The proof's readings are
    # the first (before) and the second (after); the extension's are the
    # third (after ready) and the fourth (after its 'drained').
    # EGW_STUB_MLINE_FAIL_CALL names the one reading that fails (2: the
    # reading after the run, which is the extension's baseline), and
    # EGW_STUB_MLINE_HANG_CALL the one reading that takes
    # EGW_STUB_MLINE_HANG_S seconds (a /metrics that does not answer).
    echo x >> "$EGW_STUB_LOG.mline-calls"
    local calls received=0
    calls=$(wc -l < "$EGW_STUB_LOG.mline-calls")
    stub_fails mline && { stop "_mline: GET $CTRL/metrics failed or was not valid JSON"; return 1; }
    [ "$calls" != "${EGW_STUB_MLINE_FAIL_CALL:-}" ] || { stop "_mline: GET $CTRL/metrics failed or was not valid JSON (reading $calls)"; return 1; }
    [ "$calls" != "${EGW_STUB_MLINE_HANG_CALL:-}" ] || sleep "${EGW_STUB_MLINE_HANG_S:-0}"
    [ "$calls" -lt "${EGW_STUB_MLINE_RECEIVED_FROM_CALL:-1}" ] || received=${EGW_STUB_MLINE_RECEIVED:-0}
    echo "0 0 0 true $(_proof_started_at) 1 $received 0 0 0 0 0 0"
}
wait_ready() {
    stub_fails wait_ready \
        && { stop "wait_ready: /ready answered '503', not 200, for ${1:-60} s (tunnel of 5.7 down? stack not healthy?)"; return 1; }
    # A /ready that takes its time (EGW_STUB_READY_HANG_S): the attempt's
    # clock must not run meanwhile, since the 50-minute rule runs from the
    # first 'drained'.
    [ -z "${EGW_STUB_READY_HANG_S:-}" ] || sleep "$EGW_STUB_READY_HANG_S"
    echo "stub: /ready 200 (limit ${1:-60} s)"
}
metrics() {
    stub_fails metrics && { stop "metrics $1 $2: GET /metrics failed"; return 1; }
    [ ! -e "$P/$1.metrics.$2.json" ] || { stop "metrics $1 $2: $P/$1.metrics.$2.json exists"; return 1; }
    printf '{"queue_depth": 0, "started_at": "%s", "accepted": 0, "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0}\n' \
        "$(_proof_started_at)" > "$P/$1.metrics.$2.json"
}
config_identity() {
    stub_fails config_identity && { stop "config_identity: ssh egw-tcg exited 255 - nothing was written"; return 1; }
    [ ! -e "$1" ] || { stop "config_identity: $1 exists - NOT overwritten"; return 1; }
    python3 - "$1" <<'PY'
import json, os, sys
doc = json.loads(os.environ["EGW_STUB_CONFIG_IDENTITY"])
fails = "," + os.environ.get("EGW_STUB_FAIL", "") + ","
if ",other-commit," in fails:
    doc["controller_source_commit"] = "deadbeef0"
if ",broker-reloaded," in fails:
    doc["broker_reloaded"] = True
with open(sys.argv[1], "x", encoding="utf-8") as fh:
    json.dump(doc, fh, indent=2)
    fh.write("\n")
print("config_identity: wrote " + sys.argv[1])
PY
}
'''

# The bench's tunnel stub, extended: 'tunnel_up' may take its time
# (EGW_STUB_TUNNEL_UP_HANG_S), which with EGW_STUB_TUNNEL=down is a runbook
# 6.1 preamble that blocks - an ssh that never completes its banner.
PROOF_TUNNEL_SH = TUNNEL_SH.replace(
    '    echo "stub: tunnel up"\n',
    '    [ -z "${EGW_STUB_TUNNEL_UP_HANG_S:-}" ] || sleep "$EGW_STUB_TUNNEL_UP_HANG_S"\n    echo "stub: tunnel up"\n')
assert PROOF_TUNNEL_SH != TUNNEL_SH

PY_SLOW_STEP = '''#!/usr/bin/env python3
"""A $PY whose `local_export exec` of the step EGW_SLOW_STEP takes
EGW_SLOW_STEP_S seconds longer: an offline step between two live ones that
takes its time. Every other call is this interpreter, unchanged."""
import os
import subprocess
import sys
import time

args = sys.argv[1:]
if "--name" in args and args[args.index("--name") + 1] == os.environ["EGW_SLOW_STEP"]:
    time.sleep(float(os.environ["EGW_SLOW_STEP_S"]))
sys.exit(subprocess.run([os.environ["EGW_REAL_PYTHON"]] + args).returncode)
'''


# --------------------------------------------------------------------------
# The bench, extended for the proof driver
# --------------------------------------------------------------------------


class ProofBench:
    """The bench with the python interception, the proof's guest docker, the
    extended helper stub, the stub runbook and the pilot plan."""

    def __init__(self, bench: Bench) -> None:
        self.bench = bench
        self.helpers = bench.home / "egw-tcg" / "itest-helpers.sh"
        self.helpers_text = ITEST_HELPERS + "\n" + runbook_function("keep") + PROOF_HELPERS_EXTRA
        _write(self.helpers, self.helpers_text)
        _write(bench.home / "egw-tcg" / "tunnel.sh", PROOF_TUNNEL_SH)
        self.runbook = bench.tmp / "stub-runbook.md"
        _write(self.runbook, "# stub runbook for the proof driver\n\n```bash\n"
                             "host$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'\n" + self.helpers_text + "EOF\n```\n")
        self.harness_py = _write(bench.tmp / "harness_stub.py", HARNESS_STUB)
        _write(bench.bin / "python", PYTHON_STUB, executable=True)
        _write(bench.guest_bin / "docker", DOCKER_STUB, executable=True)
        _write(bench.guest_bin / "date", DATE_STUB, executable=True)
        self.clock = str(bench.log) + ".clock"
        plan_gen.write_campaign_plan(plan_gen.generate_campaign_plan(42),
                                     bench.home / "egw-tcg" / "pilot" / "campaign_plan.json")
        self.prefix = bench.home / "egw-tcg" / "itest"
        self.base = bench.home / "egw-tcg" / "proof" / "results"
        self.plan = bench.home / "egw-tcg" / "proof" / f"plan-{RID}.json"
        bench.extra.update(FAST)
        bench.extra.update({
            "EGW_REAL_PYTHON": sys.executable,
            "EGW_STUB_HARNESS_PY": str(self.harness_py),
            "EGW_STUB_SRC": str(SRC_DIR),
            "EGW_STUB_CONFIG_IDENTITY": json.dumps(CONFIG_IDENTITY),
            "EGW_PROOF_RUNBOOK": str(self.runbook),
        })

    def run(self, *args: str, **overrides) -> subprocess.CompletedProcess:
        argv = args if args else (RID, COMMIT)
        return self.bench.run("proof.sh", *argv, timeout=600, **overrides)

    def start(self, **overrides) -> subprocess.Popen:
        """The driver as a terminal job of its own (a process group whose
        leader it is), so that an interrupt can be sent as Ctrl-C sends it:
        to the whole group, never to the driver's shell alone. Its output
        goes to files that ``finish`` reads back, never to a pipe nobody
        drains while the test waits: the evaluate step echoes the whole
        verdict document, and a driver blocked on a full pipe never reaches
        the step the test waits for."""
        self.driver_out = open(self.bench.tmp / "driver.stdout.txt", "w", encoding="utf-8")
        self.driver_err = open(self.bench.tmp / "driver.stderr.txt", "w", encoding="utf-8")
        return subprocess.Popen(["bash", str(self.bench.drivers / "proof.sh"), RID, COMMIT],
                                env=self.bench.env(**overrides), stdout=self.driver_out, stderr=self.driver_err,
                                text=True, start_new_session=True)

    def finish(self, proc: subprocess.Popen, timeout: float) -> tuple[str, str]:
        """Wait for a driver ``start`` began and return what it wrote to
        stdout and stderr, as ``communicate`` would have."""
        try:
            proc.wait(timeout=timeout)
        finally:
            self.driver_out.close()
            self.driver_err.close()
        return (Path(self.driver_out.name).read_text(encoding="utf-8"),
                Path(self.driver_err.name).read_text(encoding="utf-8"))

    @staticmethod
    def interrupt(proc: subprocess.Popen) -> None:
        """The operator's Ctrl-C: SIGINT to the driver's whole process group."""
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)

    def harness_signalled(self) -> list[int]:
        """The signals the stub harness received, in order (none: it was
        never signalled, so an interrupt of the driver did not reach it)."""
        path = Path(str(self.bench.log) + ".harness-signalled")
        if not path.exists():
            return []
        return [int(line) for line in path.read_text(encoding="utf-8").split()]

    def docker_state(self) -> dict:
        path = Path(str(self.bench.log) + ".proof-docker.json")
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def boot_stack(self, age_s: float) -> datetime:
        """The stub stack booted AGE_S seconds ago: the state the docker stub
        reads, written before the driver runs, so a test knows the boot
        instant (the five services started then, the controller two seconds
        later). Returns the boot instant."""
        boot = (fake_now(self.clock) - timedelta(seconds=age_s)).replace(microsecond=0)
        state = {"boot": instant(boot),
                 "controller": {"id": "0f" * 32, "started": instant(boot + timedelta(seconds=2)),
                                "status": "running", "starts": 0}}
        Path(str(self.bench.log) + ".proof-docker.json").write_text(json.dumps(state), encoding="utf-8")
        return boot

    def healthy_record(self, transition_at: datetime, name: str = "earlier-services-healthy.txt") -> Path:
        """A console record of the shared healthy wait, as gate_health.sh's
        'services-healthy' leaves it, whose ALL HEALTHY transition was seen
        at TRANSITION_AT (guest clock, whole seconds)."""
        seen = transition_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        earlier = (transition_at - timedelta(seconds=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        services = " ".join(f"{s}=running/healthy" for s in EXPECT_SERVICES)
        starting = " ".join(f"{s}=running/starting" for s in EXPECT_SERVICES)
        return _write(self.bench.tmp / name,
                      f"{earlier} sample 1: {starting}\n{seen} sample 2: {services}\n"
                      "ALL HEALTHY: the 6 expected services are running and healthy (sample 2)\n")

    def reset(self) -> None:
        """Between two runs of the driver in one case: the attempt, the run
        directory, the plan, the prefix siblings and the stub guest's state
        removed, as a fresh run id and a fresh guest would leave them."""
        shutil.rmtree(self.attempt())
        shutil.rmtree(self.base, ignore_errors=True)
        self.plan.unlink(missing_ok=True)
        for path in self.prefix.glob(f"{RID}.*"):
            path.unlink()
        for suffix in (".proof-docker.json", ".midrun", ".mline-calls", ".harness-argv"):
            Path(str(self.bench.log) + suffix).unlink(missing_ok=True)

    def attempt(self) -> Path:
        return self.bench.attempt(SLUG)

    def verdicts(self) -> dict:
        return self.bench.verdicts(SLUG)

    def commands(self) -> list[str]:
        return self.bench.commands(SLUG)

    def package(self) -> Path | None:
        return self.bench.package(SLUG)

    def attempts(self) -> list[Path]:
        return sorted(p for p in self.bench.attempts.iterdir() if f"_{SLUG}_attempt" in p.name)

    def harness(self) -> dict | None:
        path = Path(str(self.bench.log) + ".harness-argv")
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def session_facts(self) -> dict:
        return json.loads((self.attempt() / "analysis" / "proof_session.json").read_text(encoding="utf-8"))

    def verdict_document(self) -> dict:
        return json.loads((self.attempt() / "analysis" / "proof_verdict.json").read_text(encoding="utf-8"))

    def console(self, step: str, stream: str = "stdout") -> str:
        found = sorted((self.attempt() / "console").glob(f"*-{step}.{stream}.txt"))
        return found[-1].read_text(encoding="utf-8") if found else ""

    def seq_of(self, step: str) -> int:
        found = sorted((self.attempt() / "console").glob(f"*-{step}.stdout.txt"))
        assert found, f"no console record of {step}"
        return int(found[-1].name.split("-", 1)[0])

    def docker_log(self) -> str:
        path = Path(str(self.bench.log) + ".proof-dockerlog")
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def wait_for(self, predicate, limit_s: float = 60.0) -> None:
        t0 = time.monotonic()
        while time.monotonic() - t0 < limit_s:
            if predicate():
                return
            time.sleep(0.2)
        raise AssertionError("the condition did not come about in time")


@pytest.fixture
def pbench(tmp_path: Path) -> ProofBench:
    return ProofBench(Bench(tmp_path))


def _argv_value(argv: list[str], flag: str) -> str:
    assert flag in argv, f"{flag} is not in the harness argv: {argv}"
    return argv[argv.index(flag) + 1]


# --------------------------------------------------------------------------
# proof_session.py: the session facts the evaluator reads
# --------------------------------------------------------------------------

HELPER_SESSION = SESSION_DIR / "proof_session.py"
HELPER_CHECK = SESSION_DIR / "proof_helpers_check.py"


def _session_cmd(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HELPER_SESSION), *args], capture_output=True, text=True)


def test_proof_session_write_update_reach_keep_the_file_whole_and_the_evaluators_field_names(tmp_path):
    path = tmp_path / "analysis" / "proof_session.json"
    written = _session_cmd("write", str(path), "--healthy-limit-s", "1200", "--attempt-limit-s", "3000",
                           'values={"DRAIN_QUIET_S": 130}', "clocks.host_utc=2026-09-25T10:00:00Z", "run_id=" + RID)
    assert written.returncode == 0, report(written)
    doc = json.loads(path.read_text(encoding="utf-8"))
    # The field names are the evaluator's, and the two stop rules are the
    # ADR's texts, not reached, with the limits the driver read.
    assert doc["values"] == {"DRAIN_QUIET_S": 130}
    assert [(r["id"], r["rule"], r["limit_s"], r["reached"], r["reached_at"]) for r in doc["stop_rules"]] == [
        ("healthy", STOP_RULE_HEALTHY, 1200, False, None),
        ("attempt", STOP_RULE_ATTEMPT, 3000, False, None)]
    adr = " ".join(ADR.read_text(encoding="utf-8").split())
    assert STOP_RULE_HEALTHY in adr and STOP_RULE_ATTEMPT in adr
    assert doc["stop_rule_consequence"] in adr
    assert (doc["restart_shown"], doc["restoration"], doc["extension"]) == (None, "not-started", None)
    assert doc["clocks"] == {"host_utc": "2026-09-25T10:00:00Z"}
    read = pe.stop_rules_of(doc)
    assert read["known"] is True and read["reached"] == []
    # An update merges dotted fields and parses JSON values; the file stays a
    # whole document (rewritten through a rename) and every earlier field stays.
    updated = _session_cmd("update", str(path), "values.W=4999", "restart_shown=true",
                           "restoration=stack=healthy restart_shown=yes", "instants.harness_exit=1")
    assert updated.returncode == 0, report(updated)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["values"] == {"DRAIN_QUIET_S": 130, "W": 4999}
    assert doc["restart_shown"] is True
    assert doc["restoration"] == "stack=healthy restart_shown=yes"
    assert doc["instants"] == {"harness_exit": 1}
    assert doc["clocks"] == {"host_utc": "2026-09-25T10:00:00Z"}
    assert not list(path.parent.glob("*.tmp"))
    # A stop rule reached is what the evaluator reads as 'reached'.
    reached = _session_cmd("reach", str(path), "attempt", "2026-09-25T10:50:00Z")
    assert reached.returncode == 0, report(reached)
    doc = json.loads(path.read_text(encoding="utf-8"))
    read = pe.stop_rules_of(doc)
    assert [r["id"] for r in read["reached"]] == ["attempt"]
    assert doc["stop_rules"][1]["reached_at"] == "2026-09-25T10:50:00Z"
    assert doc["stop_rules"][0]["reached"] is False
    shown = _session_cmd("show", str(path))
    assert shown.returncode == 0 and json.loads(shown.stdout) == doc


def test_proof_session_refuses_a_second_write_an_unknown_rule_and_a_bad_assignment(tmp_path):
    path = tmp_path / "proof_session.json"
    first = _session_cmd("write", str(path), "--healthy-limit-s", "3", "--attempt-limit-s", "5")
    assert first.returncode == 0, report(first)
    before = path.read_bytes()
    second = _session_cmd("write", str(path), "--healthy-limit-s", "3", "--attempt-limit-s", "5")
    assert second.returncode == 2 and "STOP: proof_session:" in second.stderr and "written once" in second.stderr
    assert path.read_bytes() == before
    rule = _session_cmd("reach", str(path), "extension", "2026-09-25T10:00:00Z")
    assert rule.returncode == 2 and "not a stop rule of the proof" in rule.stderr
    assert path.read_bytes() == before
    bad = _session_cmd("update", str(path), "no-equals-sign")
    assert bad.returncode == 2 and "is not KEY=VALUE" in bad.stderr
    assert path.read_bytes() == before
    limit = _session_cmd("write", str(tmp_path / "other.json"), "--healthy-limit-s", "3m", "--attempt-limit-s", "5")
    assert limit.returncode == 2 and "not a whole number" in limit.stderr
    assert not (tmp_path / "other.json").exists()
    missing = _session_cmd("update", str(tmp_path / "absent.json"), "a=1")
    assert missing.returncode == 2 and "cannot be read" in missing.stderr
    usage = _session_cmd("bogus")
    assert usage.returncode == 2 and "usage:" in usage.stderr


# --------------------------------------------------------------------------
# proof_helpers_check.py: the deployed helper file against the 6.1 heredoc
# --------------------------------------------------------------------------


def test_proof_helpers_check_extracts_the_heredoc_as_regen_helpers_does_and_judges_equality(tmp_path):
    # regen_helpers.py's own extraction, run as it is run, is the reference.
    target = tmp_path / "itest-helpers.sh"
    regen = subprocess.run([sys.executable, str(SESSION_DIR / "regen_helpers.py"), str(RUNBOOK), str(target)],
                           capture_output=True, text=True)
    assert regen.returncode == 0, report(regen)
    sys.path.insert(0, str(SESSION_DIR))
    try:
        import proof_helpers_check as check
    finally:
        sys.path.remove(str(SESSION_DIR))
    body = check.heredoc_body(RUNBOOK.read_text(encoding="utf-8"))
    assert body.encode("utf-8") == target.read_bytes()
    equal = subprocess.run([sys.executable, str(HELPER_CHECK), str(RUNBOOK), str(target)], capture_output=True, text=True)
    assert equal.returncode == 0, report(equal)
    assert "HELPERS OK: the deployed helper file is the runbook's section 6.1 heredoc, byte for byte" in equal.stdout
    assert hashlib.sha256(target.read_bytes()).hexdigest() in equal.stdout
    # One byte more, and the check names the difference and ends 1.
    with target.open("a", encoding="utf-8") as fh:
        fh.write("# a hand edit\n")
    differs = subprocess.run([sys.executable, str(HELPER_CHECK), str(RUNBOOK), str(target)], capture_output=True, text=True)
    assert differs.returncode == 1, report(differs)
    assert "STOP: proof_helpers_check:" in differs.stderr and "is NOT the runbook's section 6.1 heredoc" in differs.stderr
    assert "regenerate it with regen_helpers.py" in differs.stderr
    # A file or a runbook that cannot be read, or a runbook without the
    # heredoc, is 2: nothing was compared.
    absent = subprocess.run([sys.executable, str(HELPER_CHECK), str(RUNBOOK), str(tmp_path / "absent.sh")],
                            capture_output=True, text=True)
    assert absent.returncode == 2 and "could not be read" in absent.stderr
    no_heredoc = tmp_path / "no-heredoc.md"
    no_heredoc.write_text("# nothing here\n", encoding="utf-8")
    none = subprocess.run([sys.executable, str(HELPER_CHECK), str(no_heredoc), str(target)], capture_output=True, text=True)
    assert none.returncode == 2 and "holds no complete section 6.1 heredoc" in none.stderr
    usage = subprocess.run([sys.executable, str(HELPER_CHECK)], capture_output=True, text=True)
    assert usage.returncode == 2 and "usage" in usage.stderr


# --------------------------------------------------------------------------
# proof.sh: prerequisites (design 2.12 tests 1-5, 7)
# --------------------------------------------------------------------------


def test_refuses_without_an_open_session_and_touches_nothing(pbench):
    (pbench.bench.exec_dir / "current_session").unlink()
    result = pbench.run()
    assert result.returncode == 2, report(result)
    assert "DRIVER RESULT none: exit=2" in result.stdout and "(no open session)" in result.stdout
    assert pbench.attempts() == []
    assert pbench.harness() is None
    assert not pbench.plan.exists() and not list(pbench.prefix.glob(f"{RID}.*"))
    assert not pbench.docker_log()


def test_refuses_a_used_run_id_a_pilot_plan_run_id_or_an_existing_raw_dir(pbench):
    # A prefix sibling of the run id on the host: the id was used.
    _write(pbench.prefix / f"{RID}.metrics.before.json", "{}\n")
    used = pbench.run()
    assert used.returncode == 2, report(used)
    assert "already used" in used.stdout and pbench.attempts() == []
    (pbench.prefix / f"{RID}.metrics.before.json").unlink()
    # The raw run directory exists: write-once.
    (pbench.base / "raw" / RID).mkdir(parents=True)
    raw = pbench.run()
    assert raw.returncode == 2, report(raw)
    assert f"{pbench.base / 'raw' / RID} exists" in raw.stdout and pbench.attempts() == []
    shutil.rmtree(pbench.base)
    # A run id the pilot plan holds: proof_plan.py refuses it (the plan is
    # read, never edited) and the harness is not started.
    pilot = pbench.bench.home / "egw-tcg" / "pilot" / "campaign_plan.json"
    before = pilot.read_bytes()
    result = pbench.run("controller_restart-r01", COMMIT)
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert "the diagnostic plan was not written" in verdicts["reason"]
    assert "harness-run" not in pbench.commands() and pbench.harness() is None
    assert pilot.read_bytes() == before
    assert "the harness was NOT started" in verdicts["reason"]


@pytest.mark.parametrize("overrides, says", [
    ({"DRAIN_QUIET_S": "100"}, "DRAIN_QUIET_S=100 is below the runbook's 130 s"),
    ({"DRAIN_LIMIT_S": "15m"}, "DRAIN_LIMIT_S='15m' is not a whole number"),
    ({"EGW_PROOF_ATTEMPT_LIMIT_S": "fifty"}, "EGW_PROOF_ATTEMPT_LIMIT_S is not a whole number"),
    ({"EGW_HEALTH_LIMIT_S": "20min"}, "EGW_HEALTH_LIMIT_S is not a whole number"),
    ({"EGW_PROOF_MASTER_SEED": None}, "EGW_PROOF_MASTER_SEED='' is not a whole number"),
    ({"EGW_PROOF_EXTENSION": "maybe"}, "is neither 'yes' nor 'no'"),
    ({"EGW_PROOF_RATE": "fast"}, "EGW_PROOF_RATE='fast' is not a number"),
    # The fault must fall inside the measured window: the harness cancels its
    # restart timer when the run ends, so at or beyond the duration it would
    # never fire, and 0 is no instant into the run.
    ({"EGW_PROOF_RESTART_AT_S": "300"}, "EGW_PROOF_RESTART_AT_S=300 is not strictly between 0 and EGW_PROOF_DURATION_S=300"),
    ({"EGW_PROOF_RESTART_AT_S": "0"}, "EGW_PROOF_RESTART_AT_S=0 is not strictly between 0 and EGW_PROOF_DURATION_S=300"),
    ({"EGW_PROOF_RESTART_AT_S": "301"}, "the harness cancels its restart timer when the measured run ends, so the fault would never fire"),
])
def test_refuses_a_value_that_is_not_a_whole_number_and_a_quiet_window_below_130(pbench, overrides, says):
    result = pbench.run(**overrides)
    assert result.returncode == 2, report(result)
    assert says in result.stdout and "nothing was started" in result.stdout
    assert pbench.attempts() == [] and pbench.harness() is None


def test_refuses_a_bad_run_id_or_commit_and_needs_timeout(pbench):
    bad_id = pbench.run("bad id", COMMIT)
    assert bad_id.returncode == 2 and "is not a plain run id" in bad_id.stdout
    bad_commit = pbench.run(RID, "not-hex")
    assert bad_commit.returncode == 2 and "is not 7 to 40 hex characters" in bad_commit.stdout
    usage = pbench.run(RID)
    assert usage.returncode == 2 and "usage: proof.sh RUN_ID EXPECTED_SOURCE_COMMIT" in usage.stdout
    assert pbench.attempts() == []


def test_refuses_a_results_base_or_a_plan_under_the_pilot_directory_before_anything_starts(pbench):
    # The driver never writes under ~/egw-tcg/pilot/: a results base or a
    # plan given there - as written, or resolving there through '..' - is
    # refused before anything starts, and the pilot directory is as it was.
    pilot = pbench.bench.home / "egw-tcg" / "pilot"
    before = sorted(p.name for p in pilot.iterdir())
    for overrides, says in (
        ({"EGW_PROOF_BASE": str(pilot / "results")}, f"EGW_PROOF_BASE='{pilot / 'results'}' lies under {pilot}/"),
        ({"EGW_PROOF_PLAN": str(pilot / f"plan-{RID}.json")}, f"EGW_PROOF_PLAN='{pilot / f'plan-{RID}.json'}' lies under {pilot}/"),
        ({"EGW_PROOF_BASE": str(pbench.bench.home / "egw-tcg" / "proof" / ".." / "pilot" / "results")}, "lies under"),
    ):
        result = pbench.run(**overrides)
        assert result.returncode == 2, report(result)
        assert says in result.stdout and "where this driver never writes; nothing was started" in result.stdout
        assert pbench.attempts() == [] and pbench.harness() is None
        assert sorted(p.name for p in pilot.iterdir()) == before
    # A base beside the pilot directory, whose name merely starts with it, is
    # not under it.
    beside = pbench.bench.home / "egw-tcg" / "pilot-proof" / "results"
    result = pbench.run(EGW_PROOF_BASE=str(beside), EGW_STUB_FAIL="drained")
    assert result.returncode == 2, report(result)
    assert "lies under" not in result.stdout and pbench.verdicts()["workload"]["values"]["EGW_PROOF_BASE"] == str(beside)


def test_refuses_when_the_deployed_helper_file_differs_from_the_runbook_heredoc(pbench):
    # Against the real runbook the stub helper file is not the heredoc.
    result = pbench.run(EGW_PROOF_RUNBOOK=None)
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert "is not the runbook's section 6.1 heredoc" in verdicts["reason"]
    assert "regenerate it with regen_helpers.py" in verdicts["reason"]
    assert (pbench.attempt() / "environment" / "helpers-check.txt").is_file()
    assert "harness-run" not in pbench.commands() and "pre" not in pbench.commands()
    # And a hand edit of the deployed file against the stub runbook is caught too.
    shutil.rmtree(pbench.attempt())
    with pbench.helpers.open("a", encoding="utf-8") as fh:
        fh.write("# hand edit\n")
    edited = pbench.run()
    assert edited.returncode == 2, report(edited)
    assert "first difference" in pbench.console("helpers-check", "stderr")


@pytest.mark.parametrize("token, says", [
    ("other-commit", "controller_source_commit 'deadbeef0' is not the expected"),
    ("broker-reloaded", "broker_reloaded is True, not false"),
])
def test_refuses_when_config_identity_names_another_source_commit_or_a_reloaded_broker(pbench, token, says):
    result = pbench.run(EGW_STUB_FAIL=token)
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert "the candidate on the guest is not the identified image" in verdicts["reason"]
    assert "the harness was NOT started" in verdicts["reason"]
    assert says in pbench.console("identity-check", "stderr")
    assert "pre" in pbench.commands() and "harness-run" not in pbench.commands()
    assert pbench.harness() is None


def test_the_values_and_stop_rules_are_recorded_before_the_first_drained(pbench):
    result = pbench.run(DRAIN_QUIET_S="490", EGW_STUB_FAIL="drained")
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert "precondition failed" in verdicts["reason"]
    # On the attempt, before anything started: every environment value.
    values = verdicts["workload"]["values"]
    assert values == {
        "DRAIN_QUIET_S": 490, "DRAIN_STEP_S": 5, "DRAIN_LIMIT_S": 900,
        "EGW_HEALTH_LIMIT_S": HEALTH_LIMIT_S, "EGW_HEALTH_STEP_S": 1, "EGW_READY_LIMIT_S": 5,
        "EGW_PROOF_ATTEMPT_LIMIT_S": 600, "EGW_PROOF_RESTART_AT_S": 150, "EGW_PROOF_DURATION_S": 300,
        "EGW_PROOF_RATE": 11.2, "EGW_PROOF_MASTER_SEED": 42, "EGW_PROOF_EXTENSION": "no",
        "EGW_PROOF_EXTENSION_LIMIT_S": 1790, "extension_restart_limit_after_grace_s": 300, "extension_fetch_limit_s": 300,
        "EGW_PROOF_BASE": str(pbench.base), "EGW_PROOF_PLAN": str(pbench.plan),
        "EGW_PROOF_RUNBOOK": str(pbench.runbook), "EGW_PROOF_HEALTHY_RECORD": None, "expected_source_commit": COMMIT,
    }
    assert verdicts["workload"]["engineering_diagnostic_not_a_g3_run"] is True
    # In the session facts, written as a step of its own BEFORE 'pre' (the
    # first 'drained'), with the two stop rules not reached and the clocks.
    facts = pbench.session_facts()
    assert facts["values"]["DRAIN_QUIET_S"] == 490 and facts["values"]["EGW_PROOF_ATTEMPT_LIMIT_S"] == 600
    assert [(r["id"], r["limit_s"], r["reached"]) for r in facts["stop_rules"]] == [
        ("healthy", HEALTH_LIMIT_S, False), ("attempt", 600, False)]
    assert pe.stop_rules_of(facts)["known"] is True
    assert set(facts["clocks"]) == {"host_utc", "host_epoch", "host_uptime_s", "guest_epoch", "guest_utc", "offset_s"}
    assert isinstance(facts["clocks"]["guest_epoch"], int)
    assert pbench.seq_of("session-facts") < pbench.seq_of("pre")
    assert (pbench.attempt() / "environment" / "clocks.txt").read_text(encoding="utf-8").startswith("host_utc=")
    assert facts["instants"]["first_drained_started_utc"]
    assert facts["run_id"] == RID and facts["attempt"] == pbench.attempt().name


def test_the_stack_not_healthy_within_the_limit_is_a_stop_rule_and_the_proof_is_not_run(pbench):
    result = pbench.run(EGW_STUB_FAIL="service-unhealthy")
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert (f"stop rule reached: the stack with the candidate was not running and healthy within {HEALTH_LIMIT_S} s of its start"
            in verdicts["reason"])
    assert "the harness was NOT started" in verdicts["reason"]
    assert "stack=not-healthy" in verdicts["reason"]
    facts = pbench.session_facts()
    healthy = next(r for r in facts["stop_rules"] if r["id"] == "healthy")
    assert healthy["reached"] is True and healthy["reached_at"]
    assert [r["id"] for r in pe.stop_rules_of(facts)["reached"]] == ["healthy"]
    assert "pre" not in pbench.commands() and pbench.harness() is None
    # The wait ran under what was left of the allowance from the candidate's
    # start (the containers read before it), never under a fresh limit.
    rule = facts["healthy_rule"]
    assert rule["established_by"] == "own-observation" and rule["limit_s"] == HEALTH_LIMIT_S
    assert 0 < rule["poll_bound_s"] <= HEALTH_LIMIT_S - rule["spent_before_wait_s"]
    steps = pbench.commands()
    assert steps.index("containers-before") < steps.index("healthy-rule") < steps.index("services-healthy")


PY_SESSION_UPDATE_FAILS = '''#!/usr/bin/env python3
"""A $PY whose `proof_session.py update` always fails, as a full attempts
area makes it. Every other call is this interpreter, unchanged."""
import os
import subprocess
import sys

args = sys.argv[1:]
if args and args[0].endswith("proof_session.py") and args[1:2] == ["update"]:
    print("STOP: proof_session: stub: the attempts area is full", file=sys.stderr)
    sys.exit(2)
sys.exit(subprocess.run([os.environ["EGW_REAL_PYTHON"]] + args).returncode)
'''


def test_a_record_not_kept_or_facts_not_updated_before_the_harness_leave_it_unstarted(pbench):
    # Before the harness every failure is a prerequisite (design 2.2): a
    # mandatory record that could not be made never lets the fault reach the
    # guest for an attempt already known to be invalid. The helper file
    # check's record not kept:
    _write(pbench.bench.bin / "cp", CP_REFUSES.format(name="helpers-check.txt"), executable=True)
    result = pbench.run()
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert "the record of the helper file check was not kept in environment/helpers-check.txt" in verdicts["reason"]
    assert "the harness was NOT started" in verdicts["reason"]
    steps = pbench.commands()
    assert "harness-run" not in steps and "pre" not in steps and pbench.harness() is None
    # The session facts not updated (the plan's facts, before 'pre'):
    shutil.rmtree(pbench.attempt())
    (pbench.bench.bin / "cp").unlink()
    result = pbench.run(**pbench.bench.python_stub(PY_SESSION_UPDATE_FAILS))
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert "a mandatory record was not made before the harness: the session facts could not be updated" in verdicts["reason"]
    steps = pbench.commands()
    assert "proof-plan" in steps and "pre" not in steps and "harness-run" not in steps
    assert pbench.harness() is None and not pbench.docker_log().count("kill")


def test_a_rate_that_is_not_one_number_is_refused_and_a_path_with_a_quote_is_recorded_as_it_is(pbench):
    # The values are one JSON record: a rate of two dots passes no check
    # that only refuses a leading or trailing one, and a quote in a path
    # would end its string early; both would leave the values unrecorded.
    for rate in ("11.2.0", "011.2", "1e3"):
        result = pbench.run(EGW_PROOF_RATE=rate)
        assert result.returncode == 2, report(result)
        assert f"EGW_PROOF_RATE='{rate}' is not a number" in result.stdout and pbench.attempts() == []
    leading_zero = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="0600")
    assert leading_zero.returncode == 2, report(leading_zero)
    assert "EGW_PROOF_ATTEMPT_LIMIT_S='0600' is not a plain whole number" in leading_zero.stdout
    # A quote in a path is recorded as it is (JSON-escaped): the plan path,
    # which no hook template carries. The results base is different: every
    # "{dest}" the harness renders lies under it, so a quote there is refused
    # before anything starts (the spaced-drivers case shows it).
    plan = pbench.bench.tmp / 'pl"an\\here.json'
    result = pbench.run(EGW_PROOF_PLAN=str(plan), EGW_STUB_FAIL="drained")
    assert result.returncode == 2, report(result)
    values = pbench.verdicts()["workload"]["values"]
    assert values["EGW_PROOF_PLAN"] == str(plan) and values["EGW_PROOF_RATE"] == 11.2
    assert pbench.session_facts()["values"]["EGW_PROOF_PLAN"] == str(plan)


def test_clocks_txt_keeps_each_timedatectl_line_whole(pbench):
    _write(pbench.bench.guest_bin / "timedatectl", "#!/bin/sh\necho 'Timezone=UTC'\n"
                                                    "echo 'TimeUSec=Thu 2026-09-25 10:00:00 UTC'\n", executable=True)
    result = pbench.run(EGW_STUB_FAIL="drained")
    assert result.returncode == 2, report(result)
    lines = (pbench.attempt() / "environment" / "clocks.txt").read_text(encoding="utf-8").splitlines()
    assert "guest_timedatectl=Timezone=UTC" in lines
    assert "guest_timedatectl=TimeUSec=Thu 2026-09-25 10:00:00 UTC" in lines
    assert not [line for line in lines if line in ("guest_timedatectl=Thu", "guest_timedatectl=UTC")]
    assert lines[0].startswith("host_utc=") and any(line.startswith("offset_s=") for line in lines)


# --------------------------------------------------------------------------
# proof.sh: the plan, the harness command line, the restart (tests 8-10, 26)
# --------------------------------------------------------------------------


def test_the_diagnostic_plan_has_one_controller_restart_entry_of_300_s_with_the_derived_seed(pbench):
    result = pbench.run()
    assert result.returncode == 0, report(result)
    kept = json.loads((pbench.attempt() / "environment" / "proof_plan.json").read_text(encoding="utf-8"))
    assert kept == json.loads(pbench.plan.read_text(encoding="utf-8"))
    [entry] = kept["runs"]
    assert (entry["run_id"], entry["condition_id"], entry["scenario"], entry["duration_s"], entry["warmup_s"],
            entry["cooldown_s"], entry["rate_msg_s"]) == (RID, "controller_restart", "nominal", 300, 0, 0, 11.2)
    assert entry["seed"] == plan_gen.derive_run_seed(int(MASTER_SEED), RID)
    assert kept["master_seed"] == int(MASTER_SEED)
    sha = (pbench.attempt() / "environment" / "proof_plan.sha256").read_text(encoding="utf-8").split()[0]
    assert sha == hashlib.sha256(pbench.plan.read_bytes()).hexdigest()
    facts = pbench.session_facts()
    assert (facts["plan"]["sha256"], facts["plan"]["seed"], facts["plan"]["master_seed"]) == (sha, entry["seed"], 42)
    assert pbench.verdicts()["seed"] == entry["seed"]


def test_the_harness_is_given_the_proof_plan_base_hooks_identity_and_restart_at_150(pbench):
    result = pbench.run()
    assert result.returncode == 0, report(result)
    harness = pbench.harness()
    argv = harness["argv"]
    drivers = pbench.bench.drivers
    attempt = pbench.attempt()
    seed = plan_gen.derive_run_seed(int(MASTER_SEED), RID)
    guest_epoch = pbench.session_facts()["clocks"]["guest_epoch"]
    assert _argv_value(argv, "--run-id") == RID
    assert _argv_value(argv, "--plan") == str(pbench.plan)
    assert _argv_value(argv, "--base-dir") == str(pbench.base)
    assert _argv_value(argv, "--sut-env-from") == str(attempt / "environment" / "sut_environment.json")
    # The hook path and "{dest}" are double-quoted in every template, as the
    # runbook's harness_cmd quotes "{dest}": the harness splits them without
    # a shell.
    assert _argv_value(argv, "--restart-cmd") == f'bash "{drivers}/proof_restart_controller.sh" {{run_id}}'
    assert _argv_value(argv, "--restart-at-s") == "150"
    assert _argv_value(argv, "--config-identity-from") == str(pbench.prefix / f"{RID}.config_identity.json")
    assert _argv_value(argv, "--twin-snapshot-cmd") == f'bash "{drivers}/proof_hook_twins.sh" {{run_id}} "{{dest}}" {seed}'
    assert _argv_value(argv, "--drain-cmd") == f'bash "{drivers}/proof_hook_drained.sh" {{run_id}}'
    assert _argv_value(argv, "--post-drain-fetch-cmd") == 'scp -q egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl "{dest}"'
    for kind, flag in (("broker", "--fetch-broker-log-cmd"), ("controller", "--fetch-controller-log-cmd"),
                       ("docker-events", "--fetch-docker-events-cmd")):
        assert _argv_value(argv, flag) == f'bash "{drivers}/proof_fetch_sut_log.sh" {kind} "{{dest}}" {guest_epoch}'
    runbook_argv = _harness_argv_of(runbook_function("harness_cmd"), f"harness_cmd {RID}", pbench.bench.home)
    assert _argv_value(runbook_argv, "--fetch-events-cmd").endswith('"{dest}"')
    assert str(guest_epoch).isdigit()
    # The runbook's fixed arguments, expanded in the host step (the secret
    # from the exported .env, the alias, the clone's fetch script).
    assert _argv_value(argv, "--password") == "stub-simulator-password"
    assert _argv_value(argv, "--port") == "8883"
    assert _argv_value(argv, "--controller-url") == "http://127.0.0.1:8000"
    assert _argv_value(argv, "--ca-cert") == str(pbench.bench.home / "egw-tcg" / "ca.crt")
    assert _argv_value(argv, "--expect-services") == ",".join(EXPECT_SERVICES)
    assert _argv_value(argv, "--collector-fetch-cmd") == (
        f'sh "{REPO_ROOT}/src/deployment/scripts/fetch-collector-output.sh" egw-tcg /tmp/resources-{{run_id}}.csv "{{dest}}"')
    assert "--skip-warmup" not in argv and not any(a.startswith("--allow-") for a in argv)
    assert argv.count("--plan") == 1 and argv.count("--base-dir") == 1 and argv.count("--sut-env-from") == 1
    # The hooks read the drain values from the environment the step exported.
    assert harness["env"] == {"DRAIN_QUIET_S": "130", "DRAIN_STEP_S": "5", "DRAIN_LIMIT_S": "900",
                              "EGW_CLONE": str(REPO_ROOT)}
    # The console record of the step never holds the secret's value.
    record = next(json.loads(line) for line in (attempt / "commands.jsonl").read_text(encoding="utf-8").splitlines()
                  if json.loads(line)["name"] == "harness-run")
    assert "stub-simulator-password" not in json.dumps(record["argv"])
    assert "$MOSQUITTO_SIMULATOR_PASSWORD" in json.dumps(record["argv"])
    # Under the attempt's allowance, as a job of the step's shell that
    # forwards the driver's interrupt ('bounded'), never a bare 'timeout'.
    step_text = record["argv"][-1]
    assert "timeout -k 30" in step_text and "\nbounded " in step_text and "bounded ()" in step_text
    assert "\ntimeout " not in step_text


def test_the_restart_template_is_sigkill_then_start_of_the_controller_container_and_records_both_guest_instants(pbench):
    # The driver hands the harness the SIGKILL-then-start hook as its restart
    # template (the hook's own cases show the sequence and the two guest
    # instants), and the record the hook writes reaches the package.
    result = pbench.run()
    assert result.returncode == 0, report(result)
    argv = pbench.harness()["argv"]
    template = _argv_value(argv, "--restart-cmd")
    hook = Path(shlex.split(template)[1])
    assert hook.name == "proof_restart_controller.sh" and hook.is_file()
    text = hook.read_text(encoding="utf-8")
    assert "docker kill --signal=KILL egw-controller-1" in text and "start controller" in text
    package = pbench.package()
    record = (package / "analysis" / "snapshots" / f"{RID}.restart.txt").read_text(encoding="utf-8")
    assert "phase=before" in record and "phase=after" in record and record.count("guest_epoch=") == 2
    assert pbench.verdicts()["workload"]["fault"].startswith("SIGKILL of the controller's container followed by a start")


def test_hook_templates_survive_the_harness_split_under_a_base_and_a_drivers_path_with_a_space(pbench):
    # The harness renders {run_id} and {dest} and splits each template with
    # shlex.split, without a shell: unquoted, a results base or a drivers'
    # path with a space in it - both accepted by the driver's own
    # prerequisites - would break every hook. The templates are rendered
    # here exactly as the harness renders them, against such a base.
    from egw_experiments import run as run_mod
    spaced = pbench.bench.tmp / "drivers with a space"
    shutil.copytree(pbench.bench.drivers, spaced)
    pbench.bench.drivers = spaced
    base = pbench.bench.tmp / "proof results"
    result = pbench.run(EGW_PROOF_BASE=str(base))
    assert result.returncode == 0, report(result)
    argv = pbench.harness()["argv"]
    assert _argv_value(argv, "--base-dir") == str(base)
    seed = plan_gen.derive_run_seed(int(MASTER_SEED), RID)
    guest_epoch = str(pbench.session_facts()["clocks"]["guest_epoch"])
    dest = base / "raw" / RID / "twins.before.json"
    expected = {
        "--restart-cmd": ["bash", str(spaced / "proof_restart_controller.sh"), RID],
        "--twin-snapshot-cmd": ["bash", str(spaced / "proof_hook_twins.sh"), RID, dest.as_posix(), str(seed)],
        "--drain-cmd": ["bash", str(spaced / "proof_hook_drained.sh"), RID],
        "--fetch-broker-log-cmd": ["bash", str(spaced / "proof_fetch_sut_log.sh"), "broker", dest.as_posix(), guest_epoch],
        "--fetch-controller-log-cmd": ["bash", str(spaced / "proof_fetch_sut_log.sh"), "controller", dest.as_posix(), guest_epoch],
        "--fetch-docker-events-cmd": ["bash", str(spaced / "proof_fetch_sut_log.sh"), "docker-events", dest.as_posix(), guest_epoch],
    }
    for flag, words in expected.items():
        rendered = run_mod.format_collector_template(_argv_value(argv, flag), RID, duration_s=300, dest=dest,
                                                     expect_services=list(EXPECT_SERVICES))
        assert shlex.split(rendered, posix=True) == words, flag
    rendered = run_mod.format_cmd_template(_argv_value(argv, "--post-drain-fetch-cmd"), RID, dest.as_posix())
    assert shlex.split(rendered, posix=True) == [
        "scp", "-q", f"egw-tcg:/opt/egw/deployment/data/events/{RID}/events.jsonl", dest.as_posix()]
    # And the whole session ran from the spaced drivers' path: the package
    # holds the hook's record and the verdict.
    assert pbench.package() is not None and pbench.verdicts()["system_outcome"] == "pass"
    # A drivers' path the templates cannot hold double-quoted is refused
    # before anything starts.
    quoted = pbench.bench.tmp / 'drivers "quoted"'
    shutil.copytree(spaced, quoted)
    pbench.bench.drivers = quoted
    shutil.rmtree(pbench.attempt())
    refused = pbench.run(EGW_PROOF_BASE=str(pbench.bench.tmp / "other results"))
    assert refused.returncode == 2, report(refused)
    assert "holds a double quote or a backslash" in refused.stdout and pbench.attempts() == []
    # So is a results base the templates cannot hold: every "{dest}" the
    # harness renders lies under it.
    pbench.bench.drivers = spaced
    refused = pbench.run(EGW_PROOF_BASE=str(pbench.bench.tmp / 'results "quoted"'))
    assert refused.returncode == 2, report(refused)
    assert "the results base" in refused.stdout and "holds a double quote or a backslash" in refused.stdout
    assert pbench.attempts() == []


def _harness_argv_of(function_text: str, call: str, home: Path) -> list[str]:
    """Run one shell function with 'python' replaced by a function that prints
    its arguments NUL-separated, in the environment the host preamble sets."""
    script = (function_text + "\npython() { printf '%s\\0' \"$@\"; }\n" + call + "\n")
    env = {**os.environ, "HOME": str(home), "MQTT_PORT": "8883", "CTRL": "http://127.0.0.1:8000",
           "MOSQUITTO_SIMULATOR_PASSWORD": "stub-simulator-password", "EGW_CLONE": str(REPO_ROOT)}
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, report(result)
    return result.stdout.split("\0")[:-1]


def _driver_function(name: str) -> str:
    """One shell function of proof.sh, from its `name() {` line to the first
    line that is exactly `}`."""
    lines = (SESSION_DIR / "proof.sh").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}() {{"))
    end = next(i for i in range(start, len(lines)) if lines[i] == "}")
    return "\n".join(lines[start:end + 1]) + "\n"


def test_proof_harness_cmd_fixed_arguments_equal_the_runbooks_harness_cmd_except_plan_base_and_sut_env(tmp_path):
    runbook = _harness_argv_of(runbook_function("harness_cmd"), f"harness_cmd {RID}", tmp_path)
    assert runbook[:3] == ["-m", "egw_experiments", "run"]
    expected = runbook[3:]
    plan, base, sut = str(tmp_path / "proof" / "plan.json"), str(tmp_path / "proof" / "results"), str(tmp_path / "sut.json")
    for flag, value in (("--plan", plan), ("--base-dir", base), ("--sut-env-from", sut)):
        expected[expected.index(flag) + 1] = value
    driver = _harness_argv_of(_driver_function("proof_harness_args"),
                              f"proof_harness_args {RID} {plan} {base} {sut}; python \"${{HARNESS_ARGS[@]}}\"", tmp_path)
    assert driver == expected
    # The runbook's line is what it is: the pilot plan and results base,
    # which the proof never uses.
    assert _argv_value(runbook, "--plan") == str(tmp_path / "egw-tcg" / "pilot" / "campaign_plan.json")
    assert _argv_value(runbook, "--base-dir") == str(tmp_path / "egw-tcg" / "pilot" / "results")


# --------------------------------------------------------------------------
# proof.sh: the three verdicts (tests 15-19, 21, 22, 24)
# --------------------------------------------------------------------------


def test_evaluator_supports_gives_pass_only_with_complete_evidence_and_a_healthy_stack(pbench):
    result = pbench.run()
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["proof_verdict"] == "supports"
    assert verdicts["restoration"] == "stack=healthy restart_shown=yes"
    assert verdicts["restart_shown"] == "yes"
    assert "the proof's evaluator: supports" in verdicts["reason"]
    # The harness's validity as recorded, with the form E-12 admitted it in.
    # (It read "not decisive for the proof" until the blanket reading of P-8,
    # which the Project Manager did not confirm, was replaced by E-12.)
    assert ("manifest validity valid kept as recorded, admitted for the proof only as E-12 states "
            "(harness_admission form 'valid')") in verdicts["reason"]
    assert verdicts["reason"].endswith("; the guest was left with stack=healthy restart_shown=yes")
    assert "stands for this run only" in verdicts["next_action"]
    assert "PROOF proof-adr0011-r01: validity=valid outcome=pass evaluator=supports (exit 0)" in result.stdout
    assert pbench.package() is not None
    steps = pbench.commands()
    for step in ("helpers-check", "session-facts", "containers-before", "healthy-rule", "services-healthy",
                 "healthy-rule-check", "guest-state-before",
                 "controller-process-before", "proof-plan", "ready", "pre", "identity-check", "harness-run",
                 "eligibility", "controller-process-after", "containers-after", "restart-shown", "metrics-after", "delta",
                 "guest-state-after", "guest-state-delta", "services-healthy-after", "evaluate"):
        assert step in steps, step
    # The evaluator runs AFTER the guest state after and the restoration, so
    # that the write-once verdict document echoes the restoration observed.
    assert steps.index("guest-state-delta") < steps.index("services-healthy-after") < steps.index("evaluate")
    assert steps.index("session-facts") < steps.index("ready") < steps.index("pre") < steps.index("harness-run")
    # The candidate's start is read before the wait (P-15), and the first
    # healthy sample was within the allowance from it; the run was eligible
    # (P-16) and the harness exit is in the facts beside the reading.
    assert steps.index("containers-before") < steps.index("healthy-rule") < steps.index("services-healthy") < steps.index("healthy-rule-check")
    facts = pbench.session_facts()
    rule = facts["healthy_rule"]
    assert rule["established_by"] == "own-observation" and rule["earlier_record"] is None
    assert 0 <= rule["elapsed_s"] <= HEALTH_LIMIT_S and rule["first_healthy_utc"] and rule["candidate_start_utc"]
    assert facts["eligibility"]["complete"] is True and facts["eligibility"]["problems"] == []
    assert facts["eligibility"]["harness_exit"] == 0 and facts["harness_exit"] == 0
    assert "ELIGIBLE:" in pbench.console("eligibility")
    # The harness validity was read by the evaluator's own function (E-12):
    # the driver's reading and the verdict document's are the same object.
    assert facts["eligibility"]["harness_admission"]["form"] == "valid"
    assert facts["eligibility"]["harness_admission"] == pbench.verdict_document()["instrumentation"]["harness_admission"]
    assert (facts["eligibility"]["collector_file"], facts["eligibility"]["collector_file_present"]) == ("resources.csv", True)
    assert "clock epoch=" in (pbench.attempt() / "environment" / "containers.before.txt").read_text(encoding="utf-8")
    document = pbench.verdict_document()
    assert document["instrumentation"]["proof_evidence"]["complete"] is True
    assert document["system_outcome"]["result"] == "supports"
    # The document's restoration section is the echo of what the driver
    # observed before evaluating (it decides nothing on it): never 'unknown'
    # in a session whose restoration wait ran.
    assert document["restoration"]["state"] == "stack=healthy restart_shown=yes"
    facts = pbench.session_facts()
    assert facts["restoration"] == "stack=healthy restart_shown=yes" and facts["restart_shown"] is True
    assert facts["instants"]["harness_exit"] == 0 and facts["verdicts"]["system_outcome"] == "pass"
    # The same run with a stack that does not come back healthy is never a
    # pass: the restoration outcome is kept apart and downgrades it.
    pbench.reset()
    result = pbench.run(EGW_STUB_FAIL="healthy-again-fails")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "inconclusive")
    assert verdicts["proof_verdict"] == "supports"
    assert verdicts["restoration"] == "stack=not-healthy restart_shown=yes"
    assert (f"the guest was NOT fully restored: the stack was not running and healthy again within {HEALTH_LIMIT_S} s"
            in verdicts["reason"])
    assert verdicts["reason"].endswith("; the guest was left with stack=not-healthy restart_shown=yes")
    assert "observed system fault" not in verdicts["reason"]
    # The restoration wait is never cut short and precedes the evaluator, so
    # the document echoes the stack NOT healthy again as observed.
    assert pbench.verdict_document()["restoration"]["state"] == "stack=not-healthy restart_shown=yes"
    assert pbench.verdict_document()["system_outcome"]["result"] == "supports"


def test_evaluator_refutes_gives_valid_fail_exit_1(pbench):
    result = pbench.run(EGW_STUB_PROOF_RESULT="refutes")
    assert result.returncode == 1, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert verdicts["proof_verdict"] == "refutes"
    assert "the proof's evaluator: refutes" in verdicts["reason"]
    assert "R2" in verdicts["reason"] and "refutations:" in verdicts["reason"]
    assert "never re-run it away" in verdicts["next_action"] and "option 4 next best" in verdicts["next_action"]
    assert verdicts["restoration"] == "stack=healthy restart_shown=yes"
    assert pbench.package() is not None
    assert pbench.verdict_document()["system_outcome"]["result"] == "refutes"


def test_evaluator_inconclusive_gives_exit_3_and_is_never_a_pass(pbench):
    result = pbench.run(EGW_STUB_PROOF_RESULT="inconclusive")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "inconclusive")
    assert verdicts["proof_verdict"] == "inconclusive"
    assert "the proof's evaluator: inconclusive" in verdicts["reason"] and "S1" in verdicts["reason"]
    assert "the student decides whether to repeat" in verdicts["next_action"]
    assert "services-healthy-after" in pbench.commands()


@pytest.mark.parametrize("token, evaluator, says", [
    # A seal that fails: the evaluator does not evaluate (exit 2), which is
    # a mandatory record missing, never a result. Its not-evaluated path
    # prints no 'error: ' line, only its '[proof] ' summary, which is then
    # the cause in the note (never nothing after the colon).
    ("harness-tampered", "not-computed",
     f"the proof was not evaluated (evaluate exit 2): {RID}: not-evaluated; inconclusive: SHA256SUMS does not verify"),
    # An unsealed directory: evaluated, inconclusive (exit 3), and the
    # proof's evidence is not complete, so the attempt is invalid as well.
    ("harness-unsealed", "inconclusive", "proof evidence incomplete"),
])
def test_an_evaluator_that_could_not_run_or_whose_evidence_is_incomplete_is_mandatory_and_inconclusive(
        pbench, token, evaluator, says):
    result = pbench.run(EGW_STUB_FAIL=token)
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert verdicts["proof_verdict"] == evaluator
    assert "evidence requirement(s) not met:" in verdicts["reason"]
    assert says in verdicts["reason"]
    assert "(evaluate exit 2): ;" not in verdicts["reason"]
    assert "the proof's evidence is not complete" in verdicts["reason"]
    assert "services-healthy-after" in pbench.commands()


PY_EVALUATOR_SILENT = '''#!/usr/bin/env python3
"""A $PY whose `-m egw_experiments.proof_evaluator` exits 2 printing nothing
at all. Every other call is this interpreter, unchanged."""
import os
import subprocess
import sys

args = sys.argv[1:]
if args[:2] == ["-m", "egw_experiments.proof_evaluator"]:
    sys.exit(2)
sys.exit(subprocess.run([os.environ["EGW_REAL_PYTHON"]] + args).returncode)
'''


def test_an_evaluator_that_exits_2_printing_nothing_is_noted_as_such(pbench):
    # No 'error: ' line and no '[proof] ' line: the mandatory note still says
    # what it can - that no reason was printed - and never ends with nothing
    # after the colon, since that note can be the headline of the result.
    result = pbench.run(**pbench.bench.python_stub(PY_EVALUATOR_SILENT))
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["proof_verdict"] == "not-computed"
    assert "the proof was not evaluated (evaluate exit 2): no reason printed on stderr" in verdicts["reason"]
    assert 'headline="the proof was not evaluated (evaluate exit 2): no reason printed on stderr"' in result.stdout


def test_a_harness_that_refuses_is_mandatory_never_not_run(pbench):
    result = pbench.run(EGW_STUB_HARNESS_EXIT="2")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "inconclusive" and verdicts["instrumentation_validity"] == "invalid"
    assert "the harness run exited 2" in verdicts["reason"]
    assert "services-healthy-after" in pbench.commands()
    assert verdicts["status"] == "failed"


def test_the_campaign_sampling_gap_deviation_as_the_harness_records_it_is_admitted_and_the_attempt_passes(pbench):
    # The ADR anticipates the harness marking the run invalid under
    # MAX_SAMPLE_GAP_S, as it marked both earlier restart runs. The harness
    # records that deviation in one form only (the archived r02 manifest has
    # exactly this shape): its ingest rejects the collector file, so
    # resources.csv is never written, resource_source is 'none', the two
    # validity reasons are 'no SUT resources' and 'mandatory artefact(s)
    # missing ... resources.csv', MAX_SAMPLE_GAP_S appears only in the
    # rejection's warning, the rejected file stays at
    # logs/collector/resources-<run_id>.csv, SHA256SUMS is withheld and the
    # harness exits 1. The stub builds it with run.py's own functions. The
    # driver reads it with the evaluator's own harness_admission (E-12,
    # P-16): admitted, the collector file taken where the admission names
    # it, and the evaluator supports over the same directory - the attempt
    # passes. (This case used to feed a validity reason naming
    # MAX_SAMPLE_GAP_S beside a sealed resources.csv, a form run.py never
    # writes, and the driver matched the literal: that encoded a wrong rule,
    # under which the real form could never be admitted.)
    result = pbench.run(EGW_STUB_SAMPLING_GAP="gap")
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["proof_verdict"] == "supports" and verdicts["status"] == "finished"
    raw = pbench.base / "raw" / RID
    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    # What the harness recorded, from its own functions.
    assert manifest["validity"] == "invalid" and manifest["validity_reasons"] == pe.sampling_gap_validity_reasons()
    assert not any("MAX_SAMPLE_GAP_S" in reason for reason in manifest["validity_reasons"])
    (rejection,) = [w for w in manifest["warnings"] if pe.INGEST_REJECTED_MARK in w]
    assert rejection.startswith(pe.INGEST_SOURCE_FETCH + " ") and "(MAX_SAMPLE_GAP_S)" in rejection
    assert (manifest["resource_source"], manifest["missing_mandatory_artifacts"]) == ("none", ["resources.csv"])
    assert not (raw / "resources.csv").exists() and not (raw / "SHA256SUMS").exists()
    assert (raw / "logs" / "collector" / f"resources-{RID}.csv").stat().st_size > 0
    # The reason quotes the harness validity as recorded and names the form.
    assert "manifest validity invalid (no SUT resources: " in verdicts["reason"]
    assert "kept as recorded, admitted for the proof only as E-12 states (harness_admission form 'sampling-gap-only')" in verdicts["reason"]
    assert "(harness exit 1;" in verdicts["reason"]
    assert "evidence requirement(s) not met" not in verdicts["reason"]
    # The two parts read the same admission, from the same function.
    document = pbench.verdict_document()
    facts = pbench.session_facts()
    admission = facts["eligibility"]["harness_admission"]
    assert admission == document["instrumentation"]["harness_admission"]
    assert (admission["admitted"], admission["form"]) == (True, "sampling-gap-only")
    assert admission["collector_file"] == f"logs/collector/resources-{RID}.csv"
    assert admission["seal_withheld_for"].startswith("the missing mandatory artefact resources.csv alone")
    assert f"ingest rejection (quoted): {rejection}" in admission["reasons"]
    assert document["instrumentation"]["harness_validity"] == "invalid"
    assert document["instrumentation"]["proof_eligibility"]["eligible"] is True
    assert document["instrumentation"]["proof_evidence"]["complete"] is True
    assert len(document["instrumentation"]["proof_evidence"]["accepted_in_the_sampling_gap_form"]) == 2
    # The eligibility reading (P-16): complete, in the sampling-gap form,
    # with the collector file where the admission names it.
    eligibility = facts["eligibility"]
    assert eligibility["complete"] is True and eligibility["problems"] == [] and eligibility["sampling_gap_only"] is True
    assert (eligibility["collector_file"], eligibility["collector_file_present"]) == (admission["collector_file"], True)
    assert eligibility["resources_csv_present"] is False
    assert eligibility["harness_validity"] == "invalid" and eligibility["simulator_returncode"] == 0
    assert facts["instants"]["harness_exit"] == 1 and facts["harness_exit"] == 1
    console = pbench.console("eligibility")
    assert "ELIGIBLE: " in console and "harness validity is admitted as E-12 states (form 'sampling-gap-only')" in console
    assert f"the collector file the ingest rejected is kept at logs/collector/resources-{RID}.csv" in console
    assert "stands for this run only" in verdicts["next_action"]
    # The package's declared artefacts follow the same inventory: amended on
    # the attempt, with what was changed and why (the harness never writes
    # resources.csv, and withholds SHA256SUMS, in this form), and the package
    # is complete against them.
    assert "raw/*/resources.csv" not in verdicts["expected_artefacts"]
    assert "raw/*/SHA256SUMS" not in verdicts["expected_artefacts"]
    assert f"raw/*/logs/collector/resources-{RID}.csv" in verdicts["expected_artefacts"]
    amended = verdicts["expected_artefacts_amended"]
    assert amended["replaced"] == {"raw/*/resources.csv": f"raw/*/logs/collector/resources-{RID}.csv"}
    assert amended["dropped"] == ["raw/*/SHA256SUMS"] and amended["rule"].startswith("E-12")
    assert "package exported and verified" in result.stdout and pbench.package() is not None


def test_a_rejection_that_is_not_the_sampling_gap_alone_is_not_admitted_and_the_attempt_is_invalid(pbench):
    # The same run, but the collector file the ingest rejected also holds a
    # row whose cpu_pct is not a finite number: the rejection lists a
    # problem beside the sampling gap, so the invalidity is not the
    # campaign's deviation alone (E-12). The driver's gate refuses it
    # (P-16) - and, the form not being admitted, the top-level resources.csv
    # is what the evidence then lacks - and the evaluator, applying the same
    # function, refuses it too: invalid, inconclusive, never a pass.
    result = pbench.run(EGW_STUB_SAMPLING_GAP="gap-and-other-problem")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert verdicts["proof_verdict"] == "inconclusive"
    assert "the proof's execution or evidence is incomplete (eligibility exit 1, P-16):" in verdicts["reason"]
    assert "harness validity not admitted for the proof (E-12, form 'not-admitted'" in verdicts["reason"]
    assert "the ingest rejection lists a problem other than a MAX_SAMPLE_GAP_S sampling gap" in verdicts["reason"]
    assert "resources.csv: the collector file is absent or empty" in verdicts["reason"]
    facts = pbench.session_facts()
    eligibility = facts["eligibility"]
    assert eligibility["complete"] is False and eligibility["sampling_gap_only"] is False
    assert eligibility["harness_admission"]["form"] == "not-admitted"
    assert eligibility["harness_admission"] == pbench.verdict_document()["instrumentation"]["harness_admission"]
    document_eligibility = pbench.verdict_document()["instrumentation"]["proof_eligibility"]
    assert document_eligibility["eligible"] is False
    assert any("harness validity: not admitted for the proof (E-12, form 'not-admitted')" in r
               for r in document_eligibility["reasons"])
    assert verdicts["next_action"].startswith("the attempt is inconclusive, not passing")
    assert "stands for this run only" not in verdicts["next_action"]
    # Not the admitted form: the declared artefacts are not amended.
    assert "raw/*/resources.csv" in verdicts["expected_artefacts"] and "expected_artefacts_amended" not in verdicts


# --------------------------------------------------------------------------
# proof.sh: the eligibility of the run (F1, P-16)
# --------------------------------------------------------------------------


def test_a_simulator_that_failed_after_the_restart_is_incomplete_evidence_never_a_pass(pbench):
    # The simulator fails after the fault, before the prescribed 300 s: the
    # harness drains, fetches, seals, records the failure and exits 1. Every
    # published identity is accepted, and still neither part reads it as
    # support: the evaluator refuses the run as not eligible (E-11: the
    # prescribed publication did not complete) and the driver's own gate
    # makes the attempt invalid, since this is not the sampling-gap
    # deviation the ADR admits (P-16, E-12). The harness's reason is the one
    # run.compute_validity writes for it.
    result = pbench.run(EGW_STUB_SIMULATOR_EXIT="1")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert verdicts["proof_verdict"] == "inconclusive"
    eligibility = pbench.verdict_document()["instrumentation"]["proof_eligibility"]
    assert eligibility["eligible"] is False and any("simulator" in r for r in eligibility["reasons"])
    assert "the proof's execution or evidence is incomplete (eligibility exit 1, P-16):" in verdicts["reason"]
    assert "simulator_returncode is 1, not 0: the prescribed publication did not complete" in verdicts["reason"]
    assert "harness validity not admitted for the proof (E-12, form 'not-admitted'" in verdicts["reason"]
    assert "harness validity reason (quoted): simulator exited with code 1" in verdicts["reason"]
    facts = pbench.session_facts()
    assert facts["eligibility"]["complete"] is False and facts["eligibility"]["simulator_returncode"] == 1
    assert facts["eligibility"]["sampling_gap_only"] is False and facts["harness_exit"] == 1
    assert facts["eligibility"]["harness_admission"]["form"] == "not-admitted"
    assert verdicts["next_action"].startswith("the attempt is inconclusive, not passing")
    assert "the attempt's instrumentation is invalid" in verdicts["next_action"]
    assert "stands for this run only" not in verdicts["next_action"]
    assert "services-healthy-after" in pbench.commands() and "evaluate" in pbench.commands()


@pytest.mark.parametrize("state, says", [
    # The first copy failed although a stale, readable events.jsonl is left.
    ("failed", "events_fetch: the harness copy of the events failed after 1 attempt(s)"),
    # No record of the first copy at all, and no file.
    ("missing", "events_fetch: no record of the harness copy of the events (--fetch-events-cmd)"),
])
def test_a_missing_or_failed_initial_copy_of_the_events_is_incomplete_evidence(pbench, state, says):
    # The ADR keeps two copies of the events apart, the harness fetch and the
    # post-drain fetch: a successful post-drain copy never makes up for the
    # first one (P-16), whatever the file left behind reads.
    result = pbench.run(EGW_STUB_EVENTS_FETCH=state)
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert says in verdicts["reason"] and "P-16" in verdicts["reason"]
    facts = pbench.session_facts()
    assert facts["eligibility"]["complete"] is False
    assert facts["eligibility"]["events_fetch_ok"] is (False if state == "failed" else None)
    assert "stands for this run only" not in verdicts["next_action"]
    if state == "failed":
        assert (pbench.base / "raw" / RID / "events.jsonl").is_file()


def test_a_missing_collector_file_is_incomplete_evidence(pbench):
    # The collector file (resources.csv) is among the records the ADR lists
    # ("the collector file and the manifest, as today"): never ingested into
    # the run directory, and no rejection of it recorded, the evidence is
    # incomplete - the harness's two reasons for a missing resources.csv
    # without the ingest's sampling-gap rejection are not the form E-12
    # admits, so the collector file is not taken from anywhere else.
    result = pbench.run(EGW_STUB_NO_RESOURCES="1")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert "resources.csv: the collector file is absent or empty" in verdicts["reason"]
    eligibility = pbench.session_facts()["eligibility"]
    assert eligibility["resources_csv_present"] is False and eligibility["collector_file_present"] is False
    assert eligibility["harness_admission"]["form"] == "not-admitted"
    assert "0 warning(s) of the ingest rejection" in verdicts["reason"]


# --------------------------------------------------------------------------
# proof.sh: the next action from the final outcome (R1, P-17)
# --------------------------------------------------------------------------


def test_the_next_action_follows_the_final_outcome_never_the_raw_evaluator_result(pbench):
    # An unshown restart: the evaluator itself no longer supports (E-11, the
    # fault not demonstrated), the attempt is invalid and inconclusive, and
    # the next action never says a result stands.
    result = pbench.run(EGW_STUB_FAIL="restart-not-shown")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["proof_verdict"] == "inconclusive"
    assert pbench.verdict_document()["instrumentation"]["proof_eligibility"]["eligible"] is False
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert verdicts["next_action"].startswith("the attempt is inconclusive, not passing")
    assert "the attempt's instrumentation is invalid" in verdicts["next_action"]
    assert "stands for this run only" not in verdicts["next_action"]
    # A supporting component result downgraded by the driver alone (R1):
    # the incomplete restoration and the observed fault below.
    # The same component result downgraded by an incomplete restoration.
    pbench.reset()
    result = pbench.run(EGW_STUB_FAIL="healthy-again-fails")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["proof_verdict"] == "supports"
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "inconclusive")
    assert "does not stand for the attempt: the guest not fully restored (stack=not-healthy)" in verdicts["next_action"]
    assert "the stack was left not-healthy: resolve it before any other guest session" in verdicts["next_action"]
    assert "stands for this run only" not in verdicts["next_action"]
    # And a fault the guest state showed beside a supporting component
    # result is a valid negative result, never "the result stands".
    pbench.reset()
    result = pbench.run(EGW_STUB_FAIL="service-oomkilled")
    assert result.returncode == 1, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["proof_verdict"], verdicts["system_outcome"]) == ("supports", "fail")
    assert "a fault the guest state showed beside the proof's own restart is a valid negative result" in verdicts["next_action"]
    assert "the evaluator's component result (supports) does not stand for the attempt" in verdicts["next_action"]
    assert "stands for this run only" not in verdicts["next_action"]


# --------------------------------------------------------------------------
# proof.sh: the first stop rule from the candidate's start (F2, P-15)
# --------------------------------------------------------------------------


def test_a_candidate_start_beyond_the_allowance_reaches_the_rule_before_the_wait(pbench):
    # The stack booted an hour ago and no earlier healthy transition of that
    # start is named: the allowance from the candidate's start is spent, so
    # the wait is NOT started (a late poll never resets it) and the rule is
    # recorded reached with the candidate's start.
    boot = pbench.boot_stack(3600)
    result = pbench.run()
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert (f"stop rule reached: the stack with the candidate was not healthy within {HEALTH_LIMIT_S} s of its start "
            "(healthy-rule exit 1") in verdicts["reason"]
    assert "the wait was NOT started" in verdicts["reason"]
    steps = pbench.commands()
    assert "containers-before" in steps and "healthy-rule" in steps
    assert "services-healthy" not in steps and "pre" not in steps and pbench.harness() is None
    facts = pbench.session_facts()
    healthy = next(r for r in facts["stop_rules"] if r["id"] == "healthy")
    assert healthy["reached"] is True and healthy["reached_at"]
    rule = facts["healthy_rule"]
    assert rule["candidate_start_utc"] == instant(boot) and rule["established_by"] is None
    assert rule["spent_before_wait_s"] >= 3600 and rule["earlier_record"] is None
    assert "HEALTHY RULE REACHED: the candidate start" in pbench.console("healthy-rule")
    assert "lies 36" in pbench.console("healthy-rule") and "beyond the 12 s allowance" in pbench.console("healthy-rule")


def test_late_polling_cannot_reset_the_candidate_health_allowance(pbench):
    # The stack booted 4 s ago and its health checks conclude only 30 s after
    # the boot: the wait runs under what is left of the 12 s allowance from
    # the boot (at most 8 s), not under a fresh 12 s, so it ends NOT HEALTHY
    # within that remainder and the rule is reached - a success first
    # observed past the allowance is never accepted.
    pbench.boot_stack(4)
    result = pbench.run(EGW_STUB_HEALTHY_AFTER_S="30")
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert (f"stop rule reached: the stack with the candidate was not running and healthy within {HEALTH_LIMIT_S} s of its start "
            "(services-healthy exit 1 under the") in verdicts["reason"]
    assert "s left of that allowance" in verdicts["reason"]
    facts = pbench.session_facts()
    rule = facts["healthy_rule"]
    assert rule["spent_before_wait_s"] >= 4 and 0 < rule["poll_bound_s"] <= HEALTH_LIMIT_S - 4
    assert next(r for r in facts["stop_rules"] if r["id"] == "healthy")["reached"] is True
    assert "NOT HEALTHY after" in pbench.console("services-healthy")
    assert "healthy-rule-check" not in pbench.commands() and "pre" not in pbench.commands()
    # The same stack, polled soon after its boot, is healthy in time: the
    # allowance runs from the start, not from the poll.
    pbench.reset()
    pbench.boot_stack(0)
    result = pbench.run(EGW_STUB_HEALTHY_AFTER_S="3")
    assert result.returncode == 0, report(result)
    rule = pbench.session_facts()["healthy_rule"]
    # The instant of the sample that saw ALL HEALTHY is read at the sample's
    # start, before its inspections: a stack healthy 3 s after its boot is
    # first seen by a sample whose instant may precede that by the sample's
    # own duration (2 was observed on the bench), so the elapsed time is
    # bounded by the allowance and not below by 3 - the earlier '3 <=' read
    # the instant as the observation's, which the record does not say - and
    # the record states that bias beside the instant.
    assert 0 <= rule["elapsed_s"] <= HEALTH_LIMIT_S and rule["established_by"] == "own-observation"
    assert rule["first_healthy_instant_note"].startswith("the instant of the sample that saw ALL HEALTHY is read at the sample start")
    assert "previous_sample_span_s" in rule and "previous_sample_utc" in rule


def test_the_healthy_rule_check_rejects_a_first_healthy_sample_past_the_deadline(tmp_path):
    # The check after the wait, on its own records: a first ALL HEALTHY
    # sample past start + limit is the rule reached (1), one within it is
    # met (0), a record without a readable transition cannot establish it
    # (2), and a transition established by an earlier record is not judged
    # against the deadline (the idle time of a healthy guest is not boot
    # delay).
    code = _driver_variable("HEALTHY_RULE_PY")
    clock = int(datetime(2026, 9, 25, 10, 1, 40, tzinfo=timezone.utc).timestamp())
    containers = tmp_path / "containers.before.txt"
    containers.write_text(f"clock epoch={clock} utc=2026-09-25T10:01:40Z\n" + "".join(
        f"container {s} id={'ab' * 32} started=2026-09-25T10:00:0{i}.000000000Z\n" for i, s in enumerate(EXPECT_SERVICES)),
        encoding="utf-8")
    late = tmp_path / "late.txt"
    late.write_text("2026-09-25T10:20:01Z sample 1: x=running/starting\n2026-09-25T10:20:16Z sample 2: x=running/healthy\n"
                    "ALL HEALTHY: the 6 expected services are running and healthy (sample 2)\n", encoding="utf-8")
    early = tmp_path / "early.txt"
    early.write_text("2026-09-25T10:05:00Z sample 1: x=running/healthy\n"
                     "ALL HEALTHY: the 6 expected services are running and healthy (sample 1)\n", encoding="utf-8")
    unreadable = tmp_path / "none.txt"
    unreadable.write_text("2026-09-25T10:05:00Z sample 1: x=running/starting\nNOT HEALTHY after 1200 s and 80 sample(s): x\n",
                          encoding="utf-8")

    def check(record: Path, established: str = "own-observation") -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-c", code, "check", ",".join(EXPECT_SERVICES), str(containers), "1200",
                               str(record), established], capture_output=True, text=True)

    past = check(late)
    assert past.returncode == 1, report(past)
    assert "HEALTHY RULE REACHED: the stack was first observed healthy 1216 s after the candidate start" in past.stdout
    assert "elapsed_s=1216" in past.stdout and "first_healthy_utc=2026-09-25T10:20:16Z" in past.stdout
    # The instant of the sample is its start: the span from the previous
    # sample's instant (its duration plus the step) is recorded beside it
    # with the note, and nothing is refused on it.
    assert "previous_sample_utc=2026-09-25T10:20:01Z" in past.stdout and "previous_sample_span_s=15.0" in past.stdout
    assert "first_healthy_instant_note=the instant of the sample that saw ALL HEALTHY is read at the sample start" in past.stdout
    met = check(early)
    assert met.returncode == 0, report(met)
    assert "HEALTHY RULE MET: first observed healthy 300 s after the candidate start 2026-09-25T10:00:00.000000000Z" in met.stdout
    assert "previous_sample_utc=null" in met.stdout and "previous_sample_span_s=null" in met.stdout
    none = check(unreadable)
    assert none.returncode == 2, report(none)
    assert "CANNOT BE ESTABLISHED: the record of the wait holds no ALL HEALTHY transition" in none.stdout
    reused = check(late, "earlier-record")
    assert reused.returncode == 0, report(reused)
    assert "established by the earlier record" in reused.stdout
    # The guest wall clock is stepped backwards by 2-3 s on this host: a
    # sample that reads within that band before the start is simultaneous
    # (elapsed 0, noted), one beyond it is a clock that is not consistent.
    stepped = tmp_path / "stepped.txt"
    stepped.write_text("2026-09-25T09:59:58Z sample 1: x=running/healthy\n"
                       "ALL HEALTHY: the 6 expected services are running and healthy (sample 1)\n", encoding="utf-8")
    within = check(stepped)
    assert within.returncode == 0, report(within)
    assert "elapsed_s=0" in within.stdout and "clock_step_note=the first healthy sample (2026-09-25T09:59:58Z) reads 2.000 s before" in within.stdout
    inconsistent = tmp_path / "inconsistent.txt"
    inconsistent.write_text("2026-09-25T09:59:50Z sample 1: x=running/healthy\n"
                            "ALL HEALTHY: the 6 expected services are running and healthy (sample 1)\n", encoding="utf-8")
    beyond = check(inconsistent)
    assert beyond.returncode == 2, report(beyond)
    assert "by more than the clock step band of 3 s: the guest clock is not consistent" in beyond.stdout
    # And the bound before the wait: the remainder from the candidate's
    # start, never more than the limit; a service the record does not name
    # leaves the start unknown (2).
    bound = subprocess.run([sys.executable, "-c", code, "bound", ",".join(EXPECT_SERVICES), str(containers), "1200", ""],
                           capture_output=True, text=True)
    assert bound.returncode == 0, report(bound)
    assert "bound=1100" in bound.stdout and "\"spent_before_wait_s\": 100" in bound.stdout
    assert "established=own-observation" in bound.stdout
    partial = tmp_path / "partial.txt"
    partial.write_text("\n".join(containers.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8")
    unknown = subprocess.run([sys.executable, "-c", code, "bound", ",".join(EXPECT_SERVICES), str(partial), "1200", ""],
                             capture_output=True, text=True)
    assert unknown.returncode == 2, report(unknown)
    assert "CANNOT BE ESTABLISHED: the candidate start is unknown: egw-controller-1: not named" in unknown.stdout


def test_dockers_zero_started_at_is_an_unknown_start_never_a_start_in_year_1(tmp_path):
    # docker reports the StartedAt 0001-01-01T00:00:00Z for a container
    # created but never started. That is no start: the candidate's start is
    # then unknown and the 20-minute rule cannot be established (2) - before
    # the wait and in the check after it, with or without an earlier record
    # named - never the rule REACHED with a candidate start in year 1 (the
    # joint check's case, which the rule read as a real start).
    code = _driver_variable("HEALTHY_RULE_PY")
    clock = int(datetime(2026, 9, 25, 10, 1, 40, tzinfo=timezone.utc).timestamp())
    record = tmp_path / "wait.txt"
    record.write_text("2026-09-25T10:05:00Z sample 1: x=running/healthy\n"
                      "ALL HEALTHY: the 6 expected services are running and healthy (sample 1)\n", encoding="utf-8")
    for zero in ("0001-01-01T00:00:00Z", "0001-01-01T00:00:00.000000000Z"):
        lines = [f"clock epoch={clock} utc=2026-09-25T10:01:40Z"]
        for i, service in enumerate(EXPECT_SERVICES):
            started = zero if service == "egw-controller-1" else f"2026-09-25T10:00:0{i}.000000000Z"
            lines.append(f"container {service} id={'ab' * 32} started={started}")
        containers = tmp_path / "containers.before.txt"
        containers.write_text("\n".join(lines) + "\n", encoding="utf-8")
        for args in (["bound", ",".join(EXPECT_SERVICES), str(containers), "1200", ""],
                     ["bound", ",".join(EXPECT_SERVICES), str(containers), "1200", str(record)],
                     ["check", ",".join(EXPECT_SERVICES), str(containers), "1200", str(record), "own-observation"]):
            result = subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True)
            assert result.returncode == 2, report(result)
            assert (f"CANNOT BE ESTABLISHED: the candidate start is unknown: egw-controller-1: its start instant '{zero}' "
                    "is the zero StartedAt docker reports for a container created but never started, which is no start") in result.stdout
            assert "HEALTHY RULE REACHED" not in result.stdout and "0001-01-01" not in result.stdout.split("healthy_rule=")[-1]
            # Named in the record, it is not also reported as missing from it.
            assert "not named in the containers record" not in result.stdout


def test_an_earlier_healthy_transition_of_this_same_start_is_reused_and_one_of_another_start_is_refused(pbench):
    # The stack booted an hour ago and gate_health.sh saw it healthy 5 s
    # after that boot (after the controller's start, 2 s after the boot):
    # named, that transition establishes the rule and the driver's own late
    # observation is not charged as boot delay.
    boot = pbench.boot_stack(3600)
    record = pbench.healthy_record(boot + timedelta(seconds=5))
    result = pbench.run(EGW_PROOF_HEALTHY_RECORD=str(record))
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["workload"]["values"]["EGW_PROOF_HEALTHY_RECORD"] == str(record)
    facts = pbench.session_facts()
    rule = facts["healthy_rule"]
    assert rule["established_by"] == "earlier-record" and rule["earlier_record"] == str(record)
    assert rule["earlier_elapsed_s"] == 5 and rule["poll_bound_s"] == HEALTH_LIMIT_S
    assert rule["elapsed_s"] >= 3600 and rule["first_healthy_utc"]
    assert not [r for r in facts["stop_rules"] if r["reached"]]
    assert (pbench.attempt() / "environment" / "healthy-record.txt").read_bytes() == record.read_bytes()
    assert "established by the earlier record" in pbench.console("healthy-rule-check")
    # A transition seen BEFORE the stack's start (by more than the guest
    # clock's step band) is of another start: refused, the rule cannot be
    # established from it (not-run, stated).
    pbench.reset()
    boot = pbench.boot_stack(3600)
    other = pbench.healthy_record(boot - timedelta(seconds=10), "other-start.txt")
    result = pbench.run(EGW_PROOF_HEALTHY_RECORD=str(other))
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert "the first stop rule cannot be established (healthy-rule exit 2):" in verdicts["reason"]
    assert "it is not a healthy transition of this same start" in verdicts["reason"]
    assert "services-healthy" not in pbench.commands() and pbench.harness() is None
    # A transition of this start seen beyond the allowance establishes
    # nothing: the rule is reached, and the wait is not started.
    pbench.reset()
    boot = pbench.boot_stack(3600)
    late = pbench.healthy_record(boot + timedelta(seconds=30), "late-transition.txt")
    result = pbench.run(EGW_PROOF_HEALTHY_RECORD=str(late))
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert "healthy-rule exit 1" in verdicts["reason"]
    assert next(r for r in pbench.session_facts()["stop_rules"] if r["id"] == "healthy")["reached"] is True
    assert "lies 30 s after the candidate start" in pbench.console("healthy-rule")
    # Established by the record but not healthy NOW (a service unhealthy):
    # the driver's own poll before the run is the precondition of a healthy
    # stack, under the full limit, and its failure is a precondition failed
    # - the rule the record established is not recorded as reached by a
    # poll that did not measure it, and the reason says which service.
    pbench.reset()
    boot = pbench.boot_stack(3600)
    record = pbench.healthy_record(boot + timedelta(seconds=5), "established-then-unhealthy.txt")
    result = pbench.run(EGW_PROOF_HEALTHY_RECORD=str(record), EGW_STUB_FAIL="service-unhealthy")
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert ("precondition failed: the stack with the candidate was not running and healthy when polled before the run "
            f"(services-healthy exit 1 under the full {HEALTH_LIMIT_S} s); the 20-minute rule was established by the earlier "
            "record named and this poll does not reach it") in verdicts["reason"]
    assert "stop rule reached" not in verdicts["reason"]
    assert "egw-mongodb-1(status=running health=unhealthy)" in verdicts["reason"]
    facts = pbench.session_facts()
    assert facts["healthy_rule"]["established_by"] == "earlier-record" and facts["healthy_rule"]["poll_bound_s"] == HEALTH_LIMIT_S
    assert not [r for r in facts["stop_rules"] if r["reached"]]
    assert "services-healthy" in pbench.commands() and "pre" not in pbench.commands() and pbench.harness() is None
    # A record that cannot be read is refused before anything starts.
    pbench.reset()
    result = pbench.run(EGW_PROOF_HEALTHY_RECORD=str(pbench.bench.tmp / "absent.txt"))
    assert result.returncode == 2, report(result)
    assert "is not a readable file" in result.stdout and pbench.attempts() == []


def _driver_variable(name: str) -> str:
    """The text of one single-quoted top-level variable of proof.sh (the
    interpreter text handed to $PY -c), from `NAME='` to the closing quote."""
    text = (SESSION_DIR / "proof.sh").read_text(encoding="utf-8")
    start = text.index(f"{name}='") + len(name) + 2
    return text[start:text.index("\n'\n", start)]


def test_restart_not_shown_is_mandatory_invalid(pbench):
    result = pbench.run(EGW_STUB_FAIL="restart-not-shown")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["restart_shown"] == "no"
    assert "the restart was not shown - the fault was not applied:" in verdicts["reason"]
    assert "the controller started_at did not change" in verdicts["reason"]
    assert "NOT SHOWN: the controller started_at did not change" in pbench.console("restart-shown")
    assert verdicts["restoration"] == "stack=healthy restart_shown=no"
    assert pbench.session_facts()["restart_shown"] is False
    # guest_state_delta's own reading agrees: an expected restart the pair does not show is a problem.
    assert "PROBLEM: the caller expected egw-controller-1 to be restarted in place" in pbench.console("guest-state-delta")
    assert "services-healthy-after" in pbench.commands()


def test_a_replaced_controller_is_not_the_restart_the_proof_issued(pbench):
    result = pbench.run(EGW_STUB_FAIL="controller-replaced")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["restart_shown"] == "no"
    assert "the object was replaced, not killed and started" in verdicts["reason"]
    assert verdicts["instrumentation_validity"] == "invalid"


CP_REFUSES = """#!/bin/sh
# A 'cp' that refuses one destination, as a full disk does.
for a in "$@"; do
    case "$a" in
        */environment/{name})
            echo "cp: cannot create regular file '$a': No space left on device" >&2
            exit 1
            ;;
    esac
done
exec /bin/cp "$@"
"""


def test_a_containers_after_record_that_cannot_be_read_is_not_judged_never_not_shown(pbench):
    # The record of the containers after the run is not kept (the copy
    # fails): the restart-shown check cannot read it. That is NOT JUDGED
    # (exit 2), a mandatory record missing - never NOT SHOWN, which would
    # attribute "the fault was not applied" to the system out of a record
    # that could not be read.
    _write(pbench.bench.bin / "cp", CP_REFUSES.format(name="containers.after.txt"), executable=True)
    result = pbench.run()
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["restart_shown"] == "unknown"
    assert "the containers after the run was not kept in environment/containers.after.txt" in verdicts["reason"]
    assert "could not be judged from the records (restart-shown exit 2)" in verdicts["reason"]
    assert "the fault was not applied" not in verdicts["reason"]
    assert "NOT JUDGED: the records could not be read or compared: FileNotFoundError" in pbench.console("restart-shown")
    assert "NOT SHOWN" not in pbench.console("restart-shown")
    assert pbench.session_facts()["restart_shown"] is None
    assert verdicts["restoration"] == "stack=healthy restart_shown=unknown"


def test_delta_exit_4_on_a_named_n1_case_is_a_result_not_a_failure(pbench):
    result = pbench.run(EGW_STUB_REC_DELTA="4")
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert "delta exit 4" in verdicts["reason"]
    assert "post-window observation(s) incomplete" not in verdicts["reason"]
    assert pbench.session_facts()["instants"]["delta_exit"] == 4
    # 1 (the comparison not carried out) is an incomplete observation, and
    # the outcome cannot then be a clean pass.
    shutil.rmtree(pbench.attempt())
    shutil.rmtree(pbench.base)
    pbench.plan.unlink()
    for path in pbench.prefix.glob(f"{RID}.*"):
        path.unlink()
    os.remove(str(pbench.bench.log) + ".proof-docker.json")
    os.remove(str(pbench.bench.log) + ".midrun")
    result = pbench.run(EGW_STUB_REC_DELTA="1")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "inconclusive")
    assert "post-window observation(s) incomplete: the runbook's delta over the post-drain copy did not run (exit 1)" in verdicts["reason"]


@pytest.mark.parametrize("token, says", [
    ("other-restarted", "egw-ditto-gateway-1"),
    ("service-oomkilled", "egw-mongodb-1"),
])
def test_an_expected_controller_restart_is_not_a_guest_state_fault_but_any_other_change_is(pbench, token, says):
    result = pbench.run(EGW_STUB_FAIL=token)
    assert result.returncode == 1, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    assert verdicts["proof_verdict"] == "supports"
    assert verdicts["reason"].startswith("observed system fault(s): a container was OOM-killed, replaced or gone, "
                                         "or a container other than the controller restarted during the run")
    assert says in verdicts["reason"]
    delta = pbench.console("guest-state-delta")
    assert "EXPECTED-RESTART: egw-controller-1 was restarted in place during the run" in delta
    assert "FAULT: egw-controller-1" not in delta
    assert verdicts["restoration"] == "stack=healthy restart_shown=yes"


def test_the_50_minute_rule_ends_the_attempt_inconclusive_and_still_restores(pbench):
    result = pbench.run(EGW_STUB_HANG_S="60", EGW_PROOF_ATTEMPT_LIMIT_S="6")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "inconclusive"
    assert "stop rule(s) reached: stop rule reached: the attempt was stopped 6 s after its first 'drained' started" in verdicts["reason"]
    assert "preserved as incomplete" in verdicts["reason"]
    facts = pbench.session_facts()
    attempt_rule = next(r for r in facts["stop_rules"] if r["id"] == "attempt")
    assert attempt_rule["reached"] is True and attempt_rule["reached_at"]
    assert facts["instants"]["harness_exit"] in (124, 137)
    assert 0 < facts["instants"]["harness_allowance_s"] <= 6
    steps = pbench.commands()
    assert "harness-run" in steps and "services-healthy-after" in steps and "evaluate" in steps
    # No further proof step starts after the rule: every live observation
    # after the harness is listed as not run, by name, and the restoration
    # still ran (never under the bound).
    for step in ("controller-process-after", "containers-after", "restart-shown", "metrics-after", "delta",
                 "guest-state-after", "guest-state-delta"):
        assert step not in steps, step
    assert ("not run after the attempt's stop rule was reached (no further proof step starts): controller-process-after, "
            "containers-after, restart-shown, metrics-after, delta, guest-state-after, guest-state-delta") in verdicts["reason"]
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == ("harness-run", "during")
    assert facts["eligibility"]["complete"] is False and "did not complete" in facts["eligibility"]["problems"][0]
    assert verdicts["restoration"].startswith("stack=healthy")
    assert "harness-run" in steps
    # The run directory was never written by the hanging harness: the
    # evaluator could not run, which is mandatory, never a result.
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["proof_verdict"] == "not-computed"
    # 'timeout' ended the harness (SIGTERM reached it), and the rule is
    # recorded once.
    assert pbench.harness_signalled() == [signal.SIGTERM]
    assert verdicts["reason"].count("stop rule reached") == 1


def test_an_allowance_spent_before_pre_records_the_stop_rule_once_and_starts_nothing(pbench):
    # The allowance bounds 'pre' itself (F2): an allowance of 0 s is spent
    # before 'pre' can start, so 'pre' is NOT started (never 'timeout 0',
    # which would run it unbounded), no 'drained' runs, the harness is not
    # started, and the rule is recorded once, with the step it fell before.
    # (Before F2 this case expected 'pre' to run under a spent allowance and
    # the rule to be checked only at the harness: that encoded the wrong
    # rule.) No 'drained' started, so the attempt never began and it is
    # not-run - the one ending of the 50-minute rule that is not
    # inconclusive: from 'pre' on (during it, between it and the harness,
    # during or after any later step) the proof is recorded inconclusive.
    # The allowance spent between 'pre' and the harness is the case below.
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="0")
    assert result.returncode == 2, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "not-run"
    assert verdicts["reason"].count("stop rule reached") == 1
    assert ("was spent before 'pre' could start ('pre' was NOT started, so no 'drained' ran and the attempt never "
            "began: not-run)") in verdicts["reason"]
    assert "recorded inconclusive" not in verdicts["reason"]
    assert "ended by 'timeout'" not in verdicts["reason"]
    assert "the harness was NOT started" in verdicts["reason"]
    steps = pbench.commands()
    assert "pre" not in steps and "harness-run" not in steps and pbench.harness() is None
    assert "ready" in steps
    facts = pbench.session_facts()
    attempt_rule = next(r for r in facts["stop_rules"] if r["id"] == "attempt")
    assert attempt_rule["reached"] is True and attempt_rule["reached_at"]
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == ("pre", "before")
    assert facts["instants"]["first_drained_started_utc"]
    assert "harness_exit" not in facts["instants"]
    assert not (pbench.base / "raw" / RID).exists()
    assert not list(pbench.prefix.glob(f"{RID}.*"))
    assert "kill" not in pbench.docker_log()
    assert verdicts["restoration"].startswith("stack=healthy")


def test_pre_blocking_across_the_expiry_is_ended_by_the_bound_and_starts_no_harness(pbench):
    # 'pre' blocks (its 'drained' waits 8 s) across an allowance of 3 s: it
    # is ended by 'timeout' under the bound, the rule is recorded once as
    # reached during 'pre', the harness is NOT started and no fault reaches
    # the guest. The rule was reached after the first 'drained' started, so
    # the proof is recorded inconclusive, as the ADR's stop-rule text says
    # ("If a stop rule is reached, the session stops and the proof is
    # recorded inconclusive"): exit 3, the instrumentation invalid (no run,
    # no evidence). (This case expected the attempt not-run, exit 2, since
    # the change that bounded 'pre' - a reading that was not the Project
    # Manager's and contradicts that text: the expectation is corrected.)
    result = pbench.run(EGW_STUB_QUIESCE_HANG_S="8", EGW_PROOF_ATTEMPT_LIMIT_S="3")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert verdicts["status"] == "failed"
    assert "the proof is recorded inconclusive by that rule" in verdicts["reason"]
    assert verdicts["next_action"].startswith("the attempt is inconclusive, not passing")
    assert "the student decides whether to repeat it" in verdicts["next_action"]
    assert verdicts["reason"].count("stop rule reached") == 1
    assert "('pre' was ended by 'timeout', exit 124)" in verdicts["reason"] or "('pre' was ended by 'timeout', exit 137)" in verdicts["reason"]
    assert "the harness was NOT started" in verdicts["reason"]
    steps = pbench.commands()
    assert "pre" in steps and "harness-run" not in steps and "identity-check" not in steps and pbench.harness() is None
    facts = pbench.session_facts()
    attempt_rule = next(r for r in facts["stop_rules"] if r["id"] == "attempt")
    assert attempt_rule["reached"] is True and attempt_rule["reached_at"]
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == ("pre", "during")
    assert "kill" not in pbench.docker_log()
    assert not (pbench.base / "raw" / RID).exists()
    assert verdicts["restoration"].startswith("stack=healthy")


def test_a_preamble_blocking_across_the_expiry_is_ended_by_the_bound_as_pre_itself_is(pbench):
    # The tunnel is down and 'tunnel_up' blocks for 8 s (an ssh that never
    # completes its banner) across an allowance of 3 s: the runbook's 6.1
    # preamble of 'pre' runs INSIDE the bound, so the step is ended by
    # 'timeout' before 'drained' could run, the rule is recorded once as
    # reached during 'pre', and the harness is NOT started. (hx loads the
    # preamble before and outside the bound: 'pre' would have run on across
    # the expiry until the tunnel answered.) 'pre' was dispatched under the
    # attempt's clock, which runs from the instant recorded as the first
    # 'drained' start, and the rule was reached during it: the proof is
    # recorded inconclusive (exit 3), as the ADR's stop-rule text says, not
    # not-run (the expectation this case had, corrected: whether 'drained'
    # itself had begun inside the step is not what the step's status says).
    result = pbench.run(EGW_STUB_TUNNEL="down", EGW_STUB_TUNNEL_UP_HANG_S="8", EGW_PROOF_ATTEMPT_LIMIT_S="3")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert verdicts["next_action"].startswith("the attempt is inconclusive, not passing")
    assert verdicts["reason"].count("stop rule reached") == 1
    assert "('pre' was ended by 'timeout', exit 124)" in verdicts["reason"] or "('pre' was ended by 'timeout', exit 137)" in verdicts["reason"]
    assert "the harness was NOT started" in verdicts["reason"]
    steps = pbench.commands()
    assert "ready" in steps and "pre" in steps and "harness-run" not in steps and pbench.harness() is None
    assert "drained:" not in pbench.console("pre") and "stub: tunnel up" not in pbench.console("pre")
    facts = pbench.session_facts()
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == ("pre", "during")
    assert next(r for r in facts["stop_rules"] if r["id"] == "attempt")["reached"] is True
    assert "kill" not in pbench.docker_log() and not (pbench.base / "raw" / RID).exists()
    # The step's record: the preamble is handed to the bounded shell as the
    # value of EGW_HOST_PRE and loaded with 'eval' after 'bounded', never as
    # code text before it.
    record = [json.loads(line) for line in (pbench.attempt() / "commands.jsonl").read_text(encoding="utf-8").splitlines()
              if json.loads(line)["name"] == "pre"][-1]
    argv = record["argv"]
    assert argv[0] == "env" and argv[1].startswith("EGW_HOST_PRE=") and "tunnel_check || tunnel_up" in argv[1]
    before_bound, inner = argv[-1].rsplit("\nbounded ", 1)
    assert 'eval "$EGW_HOST_PRE"' in inner and "exit 97" in inner and "tunnel_up" not in before_bound
    assert 0 < int(inner.split()[0]) <= 3


def test_a_later_observation_crossing_the_expiry_is_recorded_and_no_further_proof_step_runs(pbench):
    # The harness returns with a few seconds of the allowance left; the
    # next required live observation (the controller process after, whose
    # /metrics does not answer) crosses the expiry: it is ended by the
    # bound, the rule is recorded once as reached during that step, no
    # subsequent proof command runs, the restoration still runs (never
    # under the bound), the evaluation may finish afterwards over the sealed
    # run directory but the outcome is inconclusive with the rule named.
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="20", EGW_STUB_MLINE_HANG_CALL="2", EGW_STUB_MLINE_HANG_S="40")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "inconclusive"
    assert verdicts["reason"].count("stop rule reached") == 1
    assert "('controller-process-after' was ended by 'timeout', exit 124" in verdicts["reason"] \
        or "('controller-process-after' was ended by 'timeout', exit 137" in verdicts["reason"]
    assert "no further proof step was started" in verdicts["reason"]
    assert ("not run after the attempt's stop rule was reached (no further proof step starts): containers-after, "
            "restart-shown, metrics-after, delta, guest-state-after, guest-state-delta") in verdicts["reason"]
    steps = pbench.commands()
    assert "harness-run" in steps and "controller-process-after" in steps
    for step in ("containers-after", "restart-shown", "metrics-after", "delta", "guest-state-after", "guest-state-delta"):
        assert step not in steps, step
    assert "services-healthy-after" in steps and "evaluate" in steps
    assert steps.index("controller-process-after") < steps.index("services-healthy-after") < steps.index("evaluate")
    facts = pbench.session_facts()
    attempt_rule = next(r for r in facts["stop_rules"] if r["id"] == "attempt")
    assert attempt_rule["reached"] is True and attempt_rule["reached_at"]
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == (
        "controller-process-after", "during")
    assert facts["instants"]["harness_exit"] == 0 and facts["eligibility"]["complete"] is True
    assert facts["instants"]["not_started_after_stop_rule"].startswith("containers-after, restart-shown")
    # The run directory the harness sealed is kept and evaluated offline;
    # the evaluator reads the rule reached and says inconclusive, and the
    # restart, never judged, stays unknown.
    assert (pbench.base / "raw" / RID / "SHA256SUMS").is_file()
    assert verdicts["proof_verdict"] == "inconclusive" and verdicts["restart_shown"] == "unknown"
    assert "a stop rule of the ceiling is reached" in verdicts["reason"]
    assert "stands for this run only" not in verdicts["next_action"]
    assert "the attempt is inconclusive, not passing" in verdicts["next_action"]
    assert verdicts["restoration"] == "stack=healthy restart_shown=unknown"
    # The step's console record was kept as partial, and the 'timeout'
    # reached the reading (the step did not run on unbounded).
    record = [json.loads(line) for line in (pbench.attempt() / "commands.jsonl").read_text(encoding="utf-8").splitlines()
              if json.loads(line)["name"] == "controller-process-after"][-1]
    assert "\nbounded " in record["argv"][-1] and 0 < int(record["argv"][-1].rsplit("\nbounded ", 1)[1].split()[0]) <= 20


def test_an_allowance_spent_between_two_live_steps_is_recorded_once_and_blocks_the_next_step_and_the_extension(pbench):
    # The harness returns with most of the allowance left, and the offline
    # eligibility reading between it and the next live observation takes
    # longer than what is left: the allowance is spent BETWEEN two live
    # steps, none in progress - the 'before' path with steps after it,
    # which at 3f5b8d5 latched in a subshell and was lost. The next live
    # step is not started; the rule is recorded once, and the session
    # facts, the reason's stop-rule segment, the headline and the final
    # line's count agree on it and on the FIRST step skipped; every later
    # live step is listed as not run; the restoration still runs; and the
    # extension, although asked for, is blocked by the rule: its kill +
    # start is a fault step and never starts after the expiry.
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="25", EGW_PROOF_EXTENSION="yes",
                        **pbench.bench.python_stub(PY_SLOW_STEP, EGW_SLOW_STEP="eligibility", EGW_SLOW_STEP_S="40"))
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "inconclusive")
    reason = verdicts["reason"]
    assert reason.count("stop rule reached") == 1
    assert ("stop rule(s) reached: stop rule reached: the attempt's allowance of 25 s from its first 'drained' was spent "
            "before 'controller-process-after' could start ('controller-process-after' was NOT started); "
            "no further proof step was started") in reason
    assert ("not run after the attempt's stop rule was reached (no further proof step starts): controller-process-after, "
            "containers-after, restart-shown, metrics-after, delta, guest-state-after, guest-state-delta") in reason
    steps = pbench.commands()
    assert "harness-run" in steps and "eligibility" in steps and "services-healthy-after" in steps and "evaluate" in steps
    for step in ("controller-process-after", "containers-after", "restart-shown", "metrics-after", "delta",
                 "guest-state-after", "guest-state-delta"):
        assert step not in steps, step
    assert not any(step.startswith("ext-") for step in steps)
    facts = pbench.session_facts()
    attempt_rule = next(r for r in facts["stop_rules"] if r["id"] == "attempt")
    assert attempt_rule["reached"] is True and attempt_rule["reached_at"]
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == (
        "controller-process-after", "before")
    assert facts["instants"]["harness_exit"] == 0 and facts["eligibility"]["complete"] is True
    assert facts["instants"]["not_started_after_stop_rule"] == (
        "controller-process-after, containers-after, restart-shown, metrics-after, delta, guest-state-after, guest-state-delta")
    assert facts["extension"]["chosen"] is True and facts["extension"]["ran"] is False
    assert "the extension was not run: a stop rule of the proof was reached" in facts["extension"]["reasons"]
    assert verdicts["extension"] == "inconclusive" and "kill" not in pbench.docker_log()
    assert verdicts["headline"].startswith(
        "stop rule reached: the attempt's allowance of 25 s from its first 'drained' was spent before 'controller-process-after'")
    assert "stop_rules=1" in result.stdout and "extension=inconclusive" in result.stdout
    assert verdicts["proof_verdict"] == "inconclusive" and verdicts["restart_shown"] == "unknown"
    assert "the attempt is inconclusive, not passing" in verdicts["next_action"]
    assert "stands for this run only" not in verdicts["next_action"]
    assert verdicts["restoration"] == "stack=healthy restart_shown=unknown"


def test_an_allowance_spent_between_pre_and_the_harness_starts_no_harness_and_is_inconclusive(pbench):
    # 'pre' ends in time; the offline identity check after it takes longer
    # than what is left of the allowance (the bench's PY_SLOW_STEP delays
    # that step, deterministically): the allowance is spent BETWEEN 'pre'
    # and the harness. The harness step is not dispatched (the remainder is
    # checked before it), the rule is recorded once as reached before
    # 'harness-run', no fault reaches the guest, the restoration still runs,
    # and the attempt is inconclusive - 'pre' and its 'drained' ran, so the
    # proof is recorded inconclusive, never not-run. (This path lost its only
    # case when the case of an allowance of 0 s became the case before 'pre',
    # its replacement declared impossible without a clock stub; the joint
    # check showed PY_SLOW_STEP forces it, so it is covered again.)
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="10",
                        **pbench.bench.python_stub(PY_SLOW_STEP, EGW_SLOW_STEP="identity-check", EGW_SLOW_STEP_S="15"))
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    reason = verdicts["reason"]
    assert reason.count("stop rule reached") == 1
    assert ("stop rule reached: the attempt's allowance of 10 s was spent before the harness could start "
            "(the harness was NOT started; the run directory was never created)") in reason
    assert "ended by 'timeout'" not in reason and "(harness exit not-started;" in reason
    assert ("not run after the attempt's stop rule was reached (no further proof step starts): controller-process-after, "
            "containers-after, restart-shown, metrics-after, delta, guest-state-after, guest-state-delta") in reason
    steps = pbench.commands()
    assert "pre" in steps and "identity-check" in steps and "harness-run" not in steps and pbench.harness() is None
    assert "services-healthy-after" in steps and "evaluate" in steps
    facts = pbench.session_facts()
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == (
        "harness-run", "before")
    assert facts["instants"]["harness_exit"] is None and facts["instants"]["harness_started_utc"] is None
    assert facts["instants"]["harness_allowance_s"] == 0
    assert "harness_exit=not-started" in result.stdout
    assert not (pbench.base / "raw" / RID).exists()
    assert "kill" not in pbench.docker_log() and pbench.docker_state()["controller"]["starts"] == 0
    assert verdicts["restoration"].startswith("stack=healthy")
    assert verdicts["next_action"].startswith("the attempt is inconclusive, not passing")


# The tunnel answers until 'pre' has written the configuration identity, then
# drops once; reopening it takes EGW_STUB_TUNNEL_UP_HANG_S (the joint check's
# probe): the 6.1 preamble of the harness step - the first host step after
# 'pre' - takes its time, and every later one finds the tunnel open.
PREAMBLE_TUNNEL = """# shellcheck shell=bash
tunnel_check() { [ ! -e "$HOME/egw-tcg/itest/@RID@.config_identity.json" ] || [ -e "$HOME/egw-tcg/tunnel-reopened" ]; }
tunnel_up() { sleep "${EGW_STUB_TUNNEL_UP_HANG_S:-0}"; : > "$HOME/egw-tcg/tunnel-reopened"; echo "stub: tunnel up"; }
tunnel_down() { echo "stub: tunnel down"; }
""".replace("@RID@", RID)


def test_the_harness_steps_bound_is_computed_after_its_preamble_and_a_spent_allowance_starts_no_harness(pbench):
    # 'pre' ends well inside a 10 s allowance and the harness step is
    # dispatched with most of it left; its own 6.1 preamble (loaded before
    # its bound, as hx loads it) then takes 20 s reopening the tunnel. The
    # step was handed the absolute deadline (T0 + the allowance on
    # /proc/uptime) and computes its bound AFTER the preamble: nothing is
    # left, so the harness - and its fault hook - is NOT started (the step
    # answers 98) and the rule is recorded once as reached before
    # 'harness-run'. (The joint check's probe showed the harness starting
    # 34 s into a 20 s allowance under a bound computed before the preamble,
    # with the dispatch instant recorded as the harness's start.)
    _write(pbench.bench.home / "egw-tcg" / "tunnel.sh", PREAMBLE_TUNNEL)
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="10", EGW_STUB_TUNNEL_UP_HANG_S="20")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert verdicts["reason"].count("stop rule reached") == 1
    assert ("stop rule reached: the attempt's allowance of 10 s was spent before the harness could start "
            "(the harness was NOT started; the run directory was never created)") in verdicts["reason"]
    assert "harness-run" in pbench.commands() and pbench.harness() is None
    assert "kill" not in pbench.docker_log() and pbench.docker_state()["controller"]["starts"] == 0
    assert not (pbench.base / "raw" / RID).exists()
    stderr = pbench.console("harness-run", "stderr")
    assert ("STOP: the attempt's allowance of 10 s from its first 'drained' was spent when the host preamble of this "
            "step had loaded") in stderr and "the harness was NOT started" in stderr
    assert "stub: tunnel up" in pbench.console("harness-run") and "harness_started_utc=" not in pbench.console("harness-run")
    record = [json.loads(line) for line in (pbench.attempt() / "commands.jsonl").read_text(encoding="utf-8").splitlines()
              if json.loads(line)["name"] == "harness-run"][-1]
    assert record["exit_code"] == 98
    facts = pbench.session_facts()
    instants = facts["instants"]
    # The deadline is in the step's text, and the bound is computed from it
    # after the preamble, before 'bounded'.
    step_text = record["argv"][-1]
    deadline = instants["first_drained_started_host_uptime_s"] + 10
    assert f"HARNESS_LEFT=$(({deadline} - HARNESS_UP))" in step_text
    assert step_text.index("HARNESS_LEFT=") < step_text.index('\nbounded "$HARNESS_LEFT" python -m egw_experiments run')
    assert (instants["attempt_limit_reached_step"], instants["attempt_limit_reached_when"]) == ("harness-run", "before")
    assert instants["harness_started_utc"] is None and instants["harness_exit"] is None
    assert instants["harness_allowance_s"] == 0 and instants["harness_step_dispatched_utc"]
    assert "harness_exit=not-started" in result.stdout
    assert verdicts["restoration"].startswith("stack=healthy")
    # A preamble that takes its time but leaves some of the allowance: the
    # harness starts under what is left AFTER the preamble, and the start
    # recorded is the harness's own, taken inside the step immediately before
    # it, not the instant the step was dispatched.
    pbench.reset()
    (pbench.bench.home / "egw-tcg" / "tunnel-reopened").unlink()
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="60", EGW_STUB_TUNNEL_UP_HANG_S="6")
    assert result.returncode == 0, report(result)
    instants = pbench.session_facts()["instants"]
    started_after = instants["harness_started_host_uptime_s"] - instants["first_drained_started_host_uptime_s"]
    assert started_after >= 6
    assert instants["harness_allowance_s"] == 60 - started_after
    assert instants["harness_started_utc"] and instants["harness_step_dispatched_utc"]
    assert "harness_started_utc=" + instants["harness_started_utc"] in pbench.console("harness-run")


def test_an_allowance_spent_during_the_restoration_blocks_the_extension_and_leaves_the_proof_as_it_was(pbench):
    # Every live proof observation ends inside a 20 s allowance; the
    # restoration (never bounded, as it must be) then takes 30 s longer, so
    # the allowance runs out while it runs and no live step records it. The
    # extension, asked for, must still not start after the expiry: its kill
    # + start is a fault step and its readings are live (P-10). It is blocked
    # with that reason - the extension's own, not a stop rule of the proof,
    # whose live observations all ended in time: the proof passes as it was.
    # (The joint check's probe showed the extension's kill + start 42 s into
    # a 25 s allowance, the rule never recorded.)
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="20", EGW_PROOF_EXTENSION="yes",
                        **pbench.bench.python_stub(PY_SLOW_STEP, EGW_SLOW_STEP="services-healthy-after", EGW_SLOW_STEP_S="30"))
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["proof_verdict"] == "supports" and "stop rule" not in verdicts["reason"]
    assert verdicts["extension"] == "inconclusive"
    assert "optional extension: inconclusive (recorded apart, it decides nothing of the proof)" in verdicts["reason"]
    facts = pbench.session_facts()
    assert not [r for r in facts["stop_rules"] if r["reached"]]
    assert "attempt_limit_reached_step" not in facts["instants"]
    assert facts["extension"]["chosen"] is True and facts["extension"]["ran"] is False
    assert ("the extension was not run: the attempt's allowance of 20 s from its first 'drained' was spent before the "
            "extension could start") in facts["extension"]["reasons"]
    assert "a stop rule of the proof was reached" not in facts["extension"]["reasons"]
    assert not any(step.startswith("ext-") for step in pbench.commands())
    assert "kill" not in pbench.docker_log() and pbench.docker_state()["controller"]["starts"] == 1
    assert "stop_rules=0" in result.stdout and "extension=inconclusive" in result.stdout


def test_the_offline_comparisons_still_judge_complete_records_after_the_expiry(pbench):
    # restart-shown and the guest-state delta compare records already taken
    # and acquire no live observation, so offline analysis may finish them
    # after the expiry (Project Manager's review, F2). The guest state after
    # is taken whole, but the allowance is spent when it ends (PY_SLOW_STEP
    # delays the step's dispatch past it, deterministically): the rule is
    # recorded as reached after 'guest-state-after', and the delta still
    # compares the two records - the OOM kill the complete record shows is
    # judged, and the attempt fails with the fault named, instead of ending
    # inconclusive by the rule with the fault never read.
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="20", EGW_STUB_FAIL="service-oomkilled",
                        **pbench.bench.python_stub(PY_SLOW_STEP, EGW_SLOW_STEP="guest-state-after", EGW_SLOW_STEP_S="30"))
    assert result.returncode == 1, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "fail")
    reason = verdicts["reason"]
    assert reason.startswith("observed system fault(s): a container was OOM-killed, replaced or gone") and "egw-mongodb-1" in reason
    assert ("stop rule(s) reached: stop rule reached: the attempt's allowance of 20 s from its first 'drained' was spent "
            "when 'guest-state-after' ended") in reason
    assert "not run after the attempt's stop rule was reached" not in reason
    steps = pbench.commands()
    assert steps.index("guest-state-after") < steps.index("guest-state-delta") < steps.index("services-healthy-after")
    assert "FAULT: egw-mongodb-1" in pbench.console("guest-state-delta")
    facts = pbench.session_facts()
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == (
        "guest-state-after", "after")
    assert "not_started_after_stop_rule" not in facts["instants"]
    assert "a fault the guest state showed beside the proof's own restart is a valid negative result" in verdicts["next_action"]
    # The containers after taken whole, the allowance spent when that step
    # ends: the restart-shown check still compares the two readings and the
    # two container records, and the replacement they show is judged - not
    # the restart the proof issued, a mandatory record failed - while the
    # live observations after it are not started, and the delta, whose
    # record after was never taken, is not run.
    pbench.reset()
    result = pbench.run(EGW_PROOF_ATTEMPT_LIMIT_S="20", EGW_STUB_FAIL="controller-replaced",
                        **pbench.bench.python_stub(PY_SLOW_STEP, EGW_SLOW_STEP="containers-after", EGW_SLOW_STEP_S="30"))
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("invalid", "inconclusive")
    assert verdicts["restart_shown"] == "no"
    assert "the restart was not shown - the fault was not applied:" in verdicts["reason"]
    assert "the object was replaced, not killed and started" in verdicts["reason"]
    assert ("not run after the attempt's stop rule was reached (no further proof step starts): metrics-after, delta, "
            "guest-state-after, guest-state-delta") in verdicts["reason"]
    steps = pbench.commands()
    assert steps.index("containers-after") < steps.index("restart-shown")
    for step in ("metrics-after", "delta", "guest-state-after", "guest-state-delta"):
        assert step not in steps, step
    facts = pbench.session_facts()
    assert (facts["instants"]["attempt_limit_reached_step"], facts["instants"]["attempt_limit_reached_when"]) == (
        "containers-after", "after")
    assert facts["restart_shown"] is False
    assert facts["instants"]["not_started_after_stop_rule"] == "metrics-after, delta, guest-state-after, guest-state-delta"


def test_the_allowance_latch_is_set_in_the_drivers_own_shell_and_never_in_a_subshell():
    # The review of 3f5b8d5 (P1): live_start printed the remainder and was
    # called in a command substitution, so ATTEMPT_REACHED, the stop rule
    # and the headline were set in a subshell and lost - every later live
    # step recorded the rule again, the reason carried no stop rule, the
    # final line said stop_rules=0 and the extension's blocker did not
    # fire. live_start answers in LIVE_REST and is never substituted; the
    # driver's own functions, run here with the clock and the recording
    # stubbed, latch once and skip every later step.
    text = (SESSION_DIR / "proof.sh").read_text(encoding="utf-8")
    assert "$(live_start" not in text
    functions = "".join(_driver_function(name) for name in
                        ("left", "attempt_reached", "live_start", "live_end", "live_hx", "live_gx", "live_ex"))
    script = "\n".join([
        "set -u",
        "ATTEMPT_LIMIT=10", "T0=0", "NOW=4",
        "uptime_s() { printf '%s' \"$NOW\"; }",
        "now_utc() { printf '%s' 2026-09-25T10:00:00Z; }",
        "session_update() { echo \"session_update $*\"; }",
        "first_note() { [ -n \"$FIRST\" ] || FIRST=$1; }",
        "stoprule() { stoprules+=(\"$2\"); first_note \"$2\"; }",
        "hx() { echo \"hx $2\"; }",
        "ex() { echo \"ex $2\"; }",
        "guest_literal() { return 0; }",
        "STEP_NOT_STARTED=98", "ATTEMPT_REACHED=0", "not_started=()", "incomplete=()", "stoprules=()", "FIRST=''",
        "A=/nowhere", "SESSION=/nowhere", "HOST_PRE=true", "EXIT_NOT_REACHED=97",
        functions,
        "live_ex fourth true; echo \"rc=$?\"",
        "echo \"reached=$ATTEMPT_REACHED stoprules=${#stoprules[@]}\"",
        "NOW=100",
        "live_hx first 'true'; echo \"rc=$?\"",
        "live_gx second 'true'; echo \"rc=$?\"",
        "live_ex third true; echo \"rc=$?\"",
        "echo \"reached=$ATTEMPT_REACHED stoprules=${#stoprules[@]} not_started=${not_started[*]}\"",
        "echo \"first=$FIRST\"",
    ])
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, report(result)
    out = result.stdout
    # With 6 s left the step runs (no latch); with the allowance spent the
    # three steps that follow are not started, the latch is set once, one
    # stop rule is recorded, and the facts name the FIRST step skipped.
    assert "ex fourth\nrc=0\nreached=0 stoprules=0\n" in out
    assert out.count("rc=98") == 3 and "hx first" not in out and "ex second" not in out and "ex third" not in out
    assert "reached=1 stoprules=1 not_started=first second third" in out
    assert out.count("session_update instants.attempt_limit_reached_step=") == 1
    assert "instants.attempt_limit_reached_step=first instants.attempt_limit_reached_when=before" in out
    assert ("first=stop rule reached: the attempt's allowance of 10 s from its first 'drained' was spent before 'first' "
            "could start ('first' was NOT started); no further proof step was started") in out


def test_the_ready_wait_runs_before_the_attempts_clock_starts(pbench):
    # The 50-minute rule runs "after its first 'drained' starts" (ADR 0011):
    # a /ready that takes 20 s under an allowance of 15 s must not spend it.
    # The wait is a step of its own ('ready') before the instant the rule is
    # measured from, and 'pre' is the step whose first command is 'drained'.
    result = pbench.run(EGW_STUB_READY_HANG_S="20", EGW_PROOF_ATTEMPT_LIMIT_S="15")
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "pass" and "stop rule" not in verdicts["reason"]
    steps = pbench.commands()
    assert steps.index("session-facts") < steps.index("ready") < steps.index("pre") < steps.index("harness-run")
    records = {json.loads(line)["name"]: json.loads(line)
               for line in (pbench.attempt() / "commands.jsonl").read_text(encoding="utf-8").splitlines()}
    assert records["ready"]["argv"][-1].endswith("\nwait_ready 5")
    # 'pre' runs under the allowance (F2): its helpers in a shell of their
    # own under 'bounded', with the run id as its argument, and no
    # 'wait_ready' in it.
    pre = records["pre"]["argv"][-1]
    assert 'drained && metrics "$1" before && config_identity "$P/$1.config_identity.json"' in pre
    assert pre.rstrip().endswith(f"_ '{RID}'") and "\nbounded " in pre and "timeout -k 30" in pre
    assert "wait_ready" not in pre
    assert 0 < int(pre.rsplit("\nbounded ", 1)[1].split()[0]) <= 15
    facts = pbench.session_facts()
    # The recorded instant is after the /ready wait (taken at step 3, the
    # clocks record precedes it by at least the hang) and the allowance the
    # harness ran under was measured from it, not from before the wait.
    assert facts["instants"]["first_drained_started_host_uptime_s"] - facts["clocks"]["host_uptime_s"] >= 20
    assert 0 < facts["instants"]["harness_allowance_s"] <= 15
    # The harness's own start, taken inside its step after the preamble, on
    # the same monotonic clock: the allowance it ran under is what was left
    # of the 15 s from the first 'drained' at that instant.
    started_after = facts["instants"]["harness_started_host_uptime_s"] - facts["instants"]["first_drained_started_host_uptime_s"]
    assert 0 <= started_after < 15 and facts["instants"]["harness_allowance_s"] == 15 - started_after
    assert facts["instants"]["harness_started_utc"] and facts["instants"]["harness_step_dispatched_utc"]
    assert not [r for r in facts["stop_rules"] if r["reached"]]


def test_interrupt_restores_and_names_the_stack_state_on_the_final_line(pbench):
    # The operator's Ctrl-C goes to the driver's whole process group. 'timeout'
    # moves itself and the harness into a group of their own, which that
    # signal never reaches: the step's shell must forward it, or the harness
    # goes on detached and applies the fault after the driver has ended,
    # outside any record. The stub harness hangs before its fault for longer
    # than the driver takes to end, and records the signal it received.
    proc = pbench.start(EGW_STUB_HANG_S="25")
    pbench.wait_for(lambda: pbench.harness() is not None, 120)
    interrupted_at = time.monotonic()
    pbench.interrupt(proc)
    out, err = pbench.finish(proc, timeout=300)
    assert proc.returncode == 130, f"exit={proc.returncode}\n{out}\n{err}"
    # The interrupt reached the harness, which ended where it was: no fault
    # was applied, no run directory was written, then or afterwards.
    pbench.wait_for(lambda: pbench.harness_signalled() == [signal.SIGINT], 30)
    assert not Path(str(pbench.bench.log) + ".midrun").exists()
    assert not (pbench.base / "raw" / RID).exists()
    verdicts = pbench.verdicts()
    assert verdicts["status"] == "interrupted" and verdicts["system_outcome"] == "interrupted"
    assert verdicts["restoration"] == "stack=healthy restart_shown=unknown"
    assert "the guest was left with stack=healthy restart_shown=unknown" in verdicts["reason"]
    assert "preserved as incomplete and is never replaced" in verdicts["next_action"]
    assert 'headline="interrupted; the guest was left with stack=healthy restart_shown=unknown"' in out
    assert "DRIVER RESULT" in out and "exit=130" in out
    steps = pbench.commands()
    assert "services-healthy-after" in steps
    assert "evaluate" not in steps
    facts = pbench.session_facts()
    assert facts["instants"]["interrupted_utc"] and facts["restoration"] == "stack=healthy restart_shown=unknown"
    assert pbench.package() is not None
    # Long after the hang would have ended, the guest is as the ending said:
    # the controller was never killed and started again.
    remaining = 25 - (time.monotonic() - interrupted_at)
    if remaining > 0:
        time.sleep(min(remaining + 3, 30))
    assert not Path(str(pbench.bench.log) + ".midrun").exists()
    assert not (pbench.base / "raw" / RID).exists()
    assert pbench.docker_state().get("controller", {}).get("starts", 0) == 0
    assert "kill" not in pbench.docker_log()


def test_snapshots_session_facts_and_verdict_reach_the_package(pbench):
    result = pbench.run()
    assert result.returncode == 0, report(result)
    package = pbench.package()
    assert package is not None
    kept = sorted(p.name for p in (package / "analysis" / "snapshots").iterdir())
    assert kept == [f"{RID}.config_identity.json", f"{RID}.metrics.after.json", f"{RID}.metrics.before.json",
                    f"{RID}.restart.txt", f"{RID}.twins.after.json", f"{RID}.twins.before.json"]
    assert (package / "analysis" / "proof_session.json").is_file()
    assert (package / "analysis" / "proof_verdict.json").is_file()
    assert json.loads((package / "analysis" / "proof_verdict.json").read_text(encoding="utf-8"))["run_id"] == RID
    raw = package / "raw" / RID
    for name in ("manifest.json", "sent_events.jsonl", "events.jsonl", "events.post-drain.jsonl", "twins.before.json",
                 "twins.after.json", "configuration_identity.json", "controller_metrics.csv", "SHA256SUMS",
                 "logs/sut/broker.log", "logs/sut/controller.log", "logs/sut/docker-events.log"):
        assert (raw / name).is_file(), name
    env = package / "environment"
    for name in ("proof_plan.json", "proof_plan.sha256", "sut_environment.json", "clocks.txt", "containers.before.txt",
                 "containers.after.txt", "helpers-check.txt"):
        assert (env / name).is_file(), name
    siblings = sorted(p.name for p in (package / "simulator").iterdir())
    assert siblings == kept
    receipt = json.loads((pbench.attempt() / "export" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["package_state"] == "verified"
    assert "DRIVER RESULT" in result.stdout and "package exported and verified" in result.stdout


def test_snapshots_that_did_not_reach_the_package_are_mandatory(pbench):
    _write(pbench.bench.bin / "mkdir", """#!/bin/sh
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
    result = pbench.run()
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["instrumentation_validity"] == "invalid"
    assert "were not copied into the package" in verdicts["reason"]
    assert verdicts["proof_verdict"] == "supports" and verdicts["system_outcome"] == "inconclusive"


# --------------------------------------------------------------------------
# proof.sh: the optional extension (test 25)
# --------------------------------------------------------------------------


def test_the_optional_extension_never_runs_unless_asked(pbench):
    result = pbench.run()
    assert result.returncode == 0, report(result)
    steps = pbench.commands()
    assert not any(step.startswith("ext-") for step in steps)
    assert pbench.session_facts()["extension"] is None
    assert pbench.verdicts()["extension"] == "not-chosen"
    assert "optional extension" not in pbench.verdicts()["reason"]
    # The stub harness applies the proof's one fault to the state itself, so
    # no kill reaches the guest's docker unless the extension issues one.
    assert "kill" not in pbench.docker_log()


def test_the_extension_runs_bounded_when_asked_and_is_recorded_apart(pbench):
    # With EGW_PROOF_EXTENSION=yes the second kill + start (the restart hook
    # itself, on the guest), the ready wait and one /metrics reading, the
    # drain, the /metrics reading after it and the second fetch run after the
    # restoration, every step under the extension's ceiling, and the result
    # is recorded APART: the proof's three verdicts are what they were.
    result = pbench.run(EGW_PROOF_EXTENSION="yes")
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["proof_verdict"] == "supports"
    steps = pbench.commands()
    for step in ("ext-restart", "ext-ready", "ext-drained", "ext-metrics", "ext-fetch"):
        assert step in steps, step
    assert steps.index("ext-restart") > steps.index("services-healthy-after")
    assert (steps.index("ext-restart") < steps.index("ext-ready") < steps.index("ext-drained")
            < steps.index("ext-metrics") < steps.index("ext-fetch"))
    assert steps.count("services-healthy-after") == 2
    assert steps.index("services-healthy-after", steps.index("ext-fetch")) > steps.index("ext-fetch")
    log = pbench.docker_log()
    assert "kill --signal=KILL egw-controller-1" in log and "compose start controller" in log
    assert log.count("kill --signal=KILL") == 1
    facts = pbench.session_facts()
    assert facts["extension"]["chosen"] is True and facts["extension"]["ran"] is True
    assert facts["extension"]["limit_s"] == 1790
    assert facts["extension"]["result"] == "not-refuted"
    assert facts["extension"]["received_after_ready"] == 0 and facts["extension"]["received_after_drained"] == 0
    assert facts["extension"]["new_outcome_lines"] == 0
    assert facts["extension"]["started_at_after"] == "2026-09-25T10:04:35Z"
    assert verdicts["extension"] == "not-refuted"
    assert "optional extension: not-refuted (recorded apart, it decides nothing of the proof)" in verdicts["reason"]
    assert (pbench.prefix / f"{RID}.extension.restart.txt").is_file()
    assert (pbench.attempt() / "analysis" / "events.post-extension.jsonl").is_file()
    assert verdicts["workload"]["values"]["EGW_PROOF_EXTENSION"] == "yes"
    assert verdicts["restoration"] == "stack=healthy restart_shown=yes"
    # Each step of the extension ran under 'bounded' with what was left of
    # the ceiling - and the restart command under the ADR's "grace period
    # plus 5 minutes" (the 130 s stop_grace_period the configuration
    # identity reports, plus 300 s), the second fetch under its "5 minutes",
    # each the smaller bound at that point - and the extension's own restart
    # record reached the package beside the proof's snapshots and as a
    # simulator sibling.
    records = [json.loads(line) for line in (pbench.attempt() / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
    limits = {}
    for record in records:
        if record["name"].startswith("ext-"):
            text = record["argv"][-1]
            assert "\nbounded " in text and "timeout -k 30" in text, record["name"]
            # The call is the last line ('bounded LIMIT CMD...'); the first
            # 'bounded' line is the function's own definition.
            limits[record["name"]] = int(text.rsplit("\nbounded ", 1)[1].split()[0])
    assert limits["ext-restart"] == 130 + 300 and limits["ext-fetch"] == 300
    for name in ("ext-ready", "ext-drained", "ext-metrics"):
        assert 0 < limits[name] <= 1790, name
    assert facts["values"]["stop_grace_period_s"] == 130 and facts["identity"]["stop_grace_period"] == "130s"
    assert facts["extension"]["stop_rules"] == [
        {"id": "ext-restart", "rule": "the restart command within the grace period plus 5 minutes",
         "limit_s": 430, "grace_period_s": 130},
        {"id": "ext-fetch", "rule": "the second fetch within 5 minutes", "limit_s": 300}]
    adr = " ".join(ADR.read_text(encoding="utf-8").split())
    for rule in facts["extension"]["stop_rules"]:
        assert rule["rule"] in adr, rule
    assert "stop_rule_reached" not in facts["extension"]
    # The extension's own restoration (after its second kill + start) is
    # recorded apart; the verdict document echoes the proof's, taken before.
    assert facts["extension"]["restoration"] == "stack=healthy restart_shown=yes"
    assert pbench.verdict_document()["restoration"]["state"] == "stack=healthy restart_shown=yes"
    package = pbench.package()
    assert (package / "analysis" / "snapshots" / f"{RID}.extension.restart.txt").is_file()
    assert (package / "simulator" / f"{RID}.extension.restart.txt").is_file()


@pytest.mark.parametrize("from_reading, after_ready", [
    # 'received' in every reading, and only in the reading after the
    # extension's 'drained' (the fourth _mline: before, after, ready, drained):
    # the reading that decides is the one after 'drained' (ADR 0011), so a
    # redelivery that arrives during the quiet window refutes as well.
    ("1", 3),
    ("4", 0),
])
def test_the_extension_refutes_when_the_new_process_received_a_delivery(pbench, from_reading, after_ready):
    result = pbench.run(EGW_PROOF_EXTENSION="yes", EGW_STUB_MLINE_RECEIVED="3",
                        EGW_STUB_MLINE_RECEIVED_FROM_CALL=from_reading)
    assert result.returncode == 0, report(result)
    facts = pbench.session_facts()
    assert facts["extension"]["result"] == "refutes"
    assert facts["extension"]["received_after_ready"] == after_ready
    assert facts["extension"]["received_after_drained"] == 3
    assert "the new process received 3 delivery(ies) with nothing published" in facts["extension"]["reasons"]
    verdicts = pbench.verdicts()
    assert verdicts["extension"] == "refutes"
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert "optional extension: refutes (recorded apart, it decides nothing of the proof)" in verdicts["reason"]
    steps = pbench.commands()
    assert steps.index("ext-drained") < steps.index("ext-metrics") < steps.index("ext-fetch")


def test_the_extension_chosen_but_not_runnable_is_recorded_inconclusive_never_not_chosen(pbench):
    # Chosen, the extension is answered for: a stack not healthy again after
    # the run keeps it from running, and that is recorded as inconclusive
    # with the reason, never as an extension nobody asked for.
    result = pbench.run(EGW_PROOF_EXTENSION="yes", EGW_STUB_FAIL="healthy-again-fails")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["extension"] == "inconclusive"
    assert "optional extension: inconclusive (recorded apart, it decides nothing of the proof)" in verdicts["reason"]
    assert verdicts["workload"]["values"]["EGW_PROOF_EXTENSION"] == "yes"
    facts = pbench.session_facts()
    assert facts["extension"]["chosen"] is True and facts["extension"]["ran"] is False
    assert facts["extension"]["result"] == "inconclusive"
    assert ("the extension was not run: the stack was not running and healthy again after the run (stack=not-healthy)"
            in facts["extension"]["reasons"])
    assert not any(step.startswith("ext-") for step in pbench.commands())
    assert "kill" not in pbench.docker_log()
    assert verdicts["restoration"] == "stack=not-healthy restart_shown=yes"


def test_the_extension_ceiling_ends_its_step_and_records_inconclusive(pbench):
    # The ceiling bounds every step of the extension, not only the start of
    # one: a 'drained' that would wait 8 s under a ceiling of 5 s is ended
    # by 'timeout', the extension is inconclusive with the ceiling named,
    # nothing after it runs, and the stack is still restored afterwards.
    result = pbench.run(EGW_PROOF_EXTENSION="yes", EGW_PROOF_EXTENSION_LIMIT_S="5", EGW_STUB_QUIESCE_HANG_S="8")
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["extension"] == "inconclusive"
    facts = pbench.session_facts()
    assert facts["extension"]["result"] == "inconclusive" and facts["extension"]["limit_s"] == 5
    assert "the extension's ceiling of 5 s was reached" in facts["extension"]["reasons"]
    steps = pbench.commands()
    assert "ext-restart" in steps and "ext-fetch" not in steps and "ext-metrics" not in steps
    assert steps.count("services-healthy-after") == 2
    assert verdicts["restoration"] == "stack=healthy restart_shown=yes"
    # Under a ceiling of 5 s the restart's own rule (430 s) was not the
    # bound, so the ceiling is what is named, and no rule is recorded reached.
    assert "stop_rule_reached" not in facts["extension"]


def test_the_extensions_per_step_stop_rules_bound_the_step_and_are_named_when_reached():
    # ext_step runs a step under the smaller of its rule's bound and what is
    # left of the ceiling; ext_cut names what 'timeout' reached - the rule,
    # in the ADR's words, or the ceiling. The two functions are run on their
    # own here (a rule of 300 s cannot be reached on the bench in time), with
    # the ceiling's remainder and the host step replaced.
    restart_rule = "the restart command within the grace period plus 5 minutes"
    fetch_rule = "the second fetch within 5 minutes"
    adr = " ".join(ADR.read_text(encoding="utf-8").split())
    assert restart_rule in adr and fetch_rule in adr
    driver = (SESSION_DIR / "proof.sh").read_text(encoding="utf-8")
    assert f"EXT_RULE_RESTART='{restart_rule}'" in driver and f"EXT_RULE_FETCH='{fetch_rule}'" in driver
    assert "EXT_FETCH_LIMIT=300" in driver and "EXT_RESTART_LIMIT=$((GRACE_S + 300))" in driver
    functions = _driver_function("ext_step") + _driver_function("ext_cut")

    def run(left: int, bound: str, rule: str, rc: int) -> str:
        script = (functions
                  + "\nA=attempt\nEXTENSION_LIMIT=1790\next_reasons=()\nEXT_STEP_RULE=''\nEXT_STEP_LIMIT=''\n"
                  + "bounded() { :; }\n"
                  + f"ext_left() {{ echo {left}; }}\n"
                  + "hx() { printf 'hx %s: %s\\n' \"$2\" \"${3##*$'\\n'}\"; }\n"
                  + "session_update() { printf 'session_update %s\\n' \"$*\"; }\n"
                  + f"ext_step ext-restart '{bound}' '{rule}' true\n"
                  + f"ext_cut ext-restart {rc}; echo \"cut=$?\"\n"
                  + "printf 'reason: %s\\n' \"${ext_reasons[@]}\"\n")
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert result.returncode == 0, report(result)
        return result.stdout

    # The rule's bound is the smaller: the step runs under it, and a
    # 'timeout' (124) names the rule and records it reached.
    out = run(1000, "430", restart_rule, 124)
    assert "hx ext-restart: bounded 430 true\n" in out and "cut=0" in out
    assert (f"reason: the extension's stop rule reached: {restart_rule} (430 s; 'ext-restart' was ended by "
            "'timeout', exit 124)\n") in out
    assert f"session_update extension.stop_rule_reached={restart_rule}\n" in out
    # The ceiling's remainder is the smaller: the step runs under it, and the
    # kill after the grace (137) names the ceiling, not the rule.
    out = run(100, "430", restart_rule, 137)
    assert "hx ext-restart: bounded 100 true\n" in out
    assert "reason: the extension's ceiling of 1790 s was reached during 'ext-restart' (exit 137)\n" in out
    assert "stop_rule_reached" not in out
    # A step without a rule of its own runs under the remainder alone.
    out = run(1000, "", "", 124)
    assert "hx ext-restart: bounded 1000 true\n" in out
    assert "reason: the extension's ceiling of 1790 s was reached during 'ext-restart' (exit 124)\n" in out
    # Any other status is not a bound reached: nothing is recorded.
    out = run(1000, "430", restart_rule, 1)
    assert "cut=1" in out and "reason: \n" in out and "stop rule" not in out


def test_the_extension_without_the_baseline_reading_after_the_run_is_inconclusive_never_not_refuted(pbench):
    # The controller process is not read after the run (the second _mline
    # fails): the proof's restart is NOT JUDGED, a mandatory record missing
    # that does not stop the driver. The extension, chosen, then has no
    # baseline to show its own restart against - any reading would differ
    # from an empty one - so it is not run and is inconclusive with that
    # reason, never not-refuted; no second kill reaches the guest.
    result = pbench.run(EGW_PROOF_EXTENSION="yes", EGW_STUB_MLINE_FAIL_CALL="2")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["instrumentation_validity"] == "invalid" and verdicts["restart_shown"] == "unknown"
    assert "the controller process could not be read after the run (_mline exit 1)" in verdicts["reason"]
    assert "could not be judged from the records (restart-shown exit 2)" in verdicts["reason"]
    assert verdicts["extension"] == "inconclusive"
    assert "optional extension: inconclusive (recorded apart, it decides nothing of the proof)" in verdicts["reason"]
    facts = pbench.session_facts()
    assert facts["extension"]["chosen"] is True and facts["extension"]["ran"] is False
    assert facts["extension"]["result"] == "inconclusive"
    assert ("the restart cannot be shown: no baseline started_at was read after the run (controller-process-after)"
            in facts["extension"]["reasons"])
    assert not any(step.startswith("ext-") for step in pbench.commands())
    assert "kill" not in pbench.docker_log()
    assert pbench.docker_state()["controller"]["starts"] == 1


def test_the_extension_is_not_run_when_the_grace_period_cannot_be_read_as_seconds(pbench):
    # The restart's stop rule is bounded from the stop_grace_period the
    # configuration identity reports: one that is not a whole number of
    # seconds in the compose form leaves the rule unbounded, so the
    # extension is not run (inconclusive, with the reason) while the proof
    # itself, which does not rest on it, is what it was.
    identity = dict(CONFIG_IDENTITY, stop_grace_period="soon")
    result = pbench.run(EGW_PROOF_EXTENSION="yes", EGW_STUB_CONFIG_IDENTITY=json.dumps(identity))
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["extension"] == "inconclusive"
    facts = pbench.session_facts()
    assert facts["values"]["stop_grace_period_s"] is None and facts["identity"]["stop_grace_period"] == "soon"
    assert facts["extension"]["ran"] is False and facts["extension"]["result"] == "inconclusive"
    assert ("the stop rule 'the restart command within the grace period plus 5 minutes' cannot be bounded: "
            "the configuration identity's stop_grace_period was not read as whole seconds" in facts["extension"]["reasons"])
    assert facts["extension"]["stop_rules"][0]["limit_s"] is None and facts["extension"]["stop_rules"][0]["grace_period_s"] is None
    assert facts["extension"]["stop_rules"][1]["limit_s"] == 300
    assert not any(step.startswith("ext-") for step in pbench.commands())
    assert "stop_grace_period=soon stop_grace_period_s= " in pbench.console("identity-check")


def test_an_interrupt_during_the_extension_restores_after_its_kill_and_names_the_state(pbench):
    # The extension's kill + start mutates the stack again: an interrupt
    # while its 'drained' waits must read the stack back (the restoration
    # wait a second time) before the ending names the state, never repeat
    # the state the first restoration found.
    proc = pbench.start(EGW_PROOF_EXTENSION="yes", EGW_STUB_QUIESCE_HANG_S="8")
    console = pbench.bench.attempts

    def draining() -> bool:
        return any(console.glob(f"*_{SLUG}_attempt*/console/*-ext-drained.stdout.txt"))

    pbench.wait_for(draining, 180)
    pbench.interrupt(proc)
    out, err = pbench.finish(proc, timeout=300)
    assert proc.returncode == 130, f"exit={proc.returncode}\n{out}\n{err}"
    verdicts = pbench.verdicts()
    assert verdicts["status"] == "interrupted"
    assert verdicts["restoration"] == "stack=healthy restart_shown=yes"
    assert verdicts["reason"].endswith("; the guest was left with stack=healthy restart_shown=yes")
    steps = pbench.commands()
    assert steps.count("services-healthy-after") == 2
    assert steps.index("services-healthy-after", steps.index("ext-restart")) > steps.index("ext-restart")
    assert "ext-fetch" not in steps and "ext-metrics" not in steps
    assert pbench.docker_log().count("kill --signal=KILL") == 1
    facts = pbench.session_facts()
    assert facts["instants"]["interrupted_utc"] and facts["restoration"] == "stack=healthy restart_shown=yes"
    assert facts["extension"]["ran"] is True and facts["extension"]["result"] == "inconclusive"


# --------------------------------------------------------------------------
# hygiene
# --------------------------------------------------------------------------


def test_the_driver_is_shellcheck_clean_at_error_severity():
    shellcheck = shutil.which("shellcheck") or str(Path(sys.executable).parent / "shellcheck")
    if not Path(shellcheck).is_file():
        pytest.skip("shellcheck is not installed")
    result = subprocess.run([shellcheck, "-S", "error", str(SESSION_DIR / "proof.sh")], capture_output=True, text=True)
    assert result.returncode == 0, report(result)


def test_the_readme_names_the_driver_its_values_and_the_three_verdicts():
    readme = " ".join((SESSION_DIR / "README.md").read_text(encoding="utf-8").split())
    assert "`proof.sh RUN_ID EXPECTED_SOURCE_COMMIT`" in readme
    assert "`proof_plan.py`" in readme and "`proof_session.py`" in readme and "`proof_helpers_check.py`" in readme
    for value in ("`DRAIN_QUIET_S`", "`EGW_PROOF_ATTEMPT_LIMIT_S`", "`EGW_PROOF_MASTER_SEED`", "`EGW_PROOF_EXTENSION`",
                  "`EGW_PROOF_RUNBOOK`", "`EGW_PROOF_RESTART_AT_S`", "`EGW_PROOF_HEALTHY_RECORD`"):
        assert value in readme, value
    # The harness's own validity is admitted only as E-12 states, through the
    # evaluator's own function. (This asserted "not decisive", the blanket
    # reading of P-8 the Project Manager did not confirm: corrected.)
    assert "P-8" in readme and "E-12" in readme and "`harness_admission`" in readme
    assert "not decisive" not in readme
    # The driver's own rules, each stated with its label: the allowance from
    # the first 'drained' as one deadline over every live observation, the
    # extension's two per-step stop rules, its baseline, the restart instant
    # inside the window, no path under the pilot, the 20-minute rule from
    # the candidate's start, the eligibility of the run, the next action
    # from the final outcome.
    for label in ("P-10", "P-11", "P-12", "P-13", "P-14", "P-15", "P-16", "P-17"):
        assert f"**{label}**" in readme, label
    assert "every live proof observation" in readme and "candidate's start" in readme
    assert "MAX_SAMPLE_GAP_S" in readme and "never the evaluator's raw result" in readme
    # P-10 as it now reads: the harness step's bound after its preamble, the
    # offline comparisons after an expiry, the extension blocked by it, and
    # the rule reached from 'pre' on recorded inconclusive; P-15: docker's
    # zero StartedAt is an unknown start.
    assert "after its preamble" in readme and "offline comparisons" in readme
    assert "the attempt's allowance spent before it could start" in readme
    assert "from `pre` on" in readme and "`0001-01-01T00:00:00Z`" in readme
    assert "the ADR gives no `/ready` figure" in readme and "runbook's `wait_ready` default of 60 s" in readme
    assert "the 300 s of the planning ceiling" not in readme
