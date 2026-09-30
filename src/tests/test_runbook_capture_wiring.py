"""The run-scoped capture of PR #50 wired into the G3 procedures of the runbook (work order of 2026-09-29, B).

Under test, executed for real: the helper functions of runbook 6.1 as the runbook writes them (read from
docs/setup/qemu_integrated_gateway.md when the test runs: guest_epoch, sut_log, events_start, events_cleanup,
events_stop, harness_cmd, harness_run), the lines of tests 3, 5 and 9(b)/(c), the lines of test 6 and the compose
command of test 7, and the checkout's own scripts they call (tools/session/events_capture.sh,
proof_fetch_sut_log.sh, proof_events_recorder.sh, events_coverage.py, and test 6's restart-evidence hooks
proof_hook_twins.sh and proof_hook_drained.sh). They run on the stub guest of test_proof_hooks (the ssh, scp,
systemd-run and systemctl stubs of test_session_drivers; the docker stub that keeps the multi-session logs, the
daemon's events and the compose operations; the guest's steady clock). The harness is a stub that does what the
capture depends on by the harness's own code (run.py execute_collector_hook, _execute_restart_cmd, drain_hook_outcome,
fetch_events_via_cmd, sut_log_fetch_failures, restart_evidence_failures), in the order of run.py execute_run, and
seals its run directory with a plain SHA256SUMS.

What these cases show is the wiring: the recorder is ready before the workload and the fault, every log and the
events are bounded to the run or the sub-check, a read or capture that failed never becomes evidence, the unit is
stopped on every ending with what it captured kept, and each fault is judged on its own container. They say nothing
about a real guest, engine or broker: that Docker 25.0.9 records a compose stop as kill (signal 15), die and stop,
and a compose restart as kill, die, stop, start and restart, is its documentation, not an observation here - the
new capture is guest-unverified.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the session drivers are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)

from test_session_drivers import EXPECT_SERVICES, ITEST_HELPERS, _write, report  # noqa: E402

from test_proof_hooks import STEADY_CLOCK, Hooks, capture_script, hooks, runbook_function  # noqa: E402,F401

from test_runbook_itest_helpers import _host_commands, _one, t9_lines  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION = REPO_ROOT / "tools" / "session"
HELPERS = ("keep", "guest_epoch", "sut_log", "events_start", "events_cleanup", "events_stop", "harness_cmd",
           "harness_run")

PYTHON_STUB = r'''#!/usr/bin/env bash
# 'python' of the operator's venv: the harness ('-m egw_experiments run') is the stub harness of this module; the
# simulator ('-m egw_simulator') is a client the broker refuses, its line logged on the stub guest's clock; anything
# else is the real interpreter
if [ "${1:-}" = -m ] && [ "${2:-}" = egw_experiments ] && [ "${3:-}" = run ]; then
  shift 3
  exec "$EGW_WIRING_PY" "$EGW_WIRING_HARNESS" "$@"
fi
if [ "${1:-}" = -m ] && [ "${2:-}" = egw_simulator ]; then
  rid=; prev=
  for a in "$@"; do [ "$prev" != --run-id ] || rid=$a; prev=$a; done
  printf 'mosquitto-1  | %s Client egw-simulator-%s disconnected, not authorised.\n' \
    "$("$EGW_STUB_GUEST_BIN/date" -u +%Y-%m-%dT%H:%M:%S.500000000Z)" "$rid" >> "$EGW_STUB_LOG.broker-log"
  echo "egw_simulator: connection failed: MQTT connect to 127.0.0.1:8883 not acknowledged within 15 s" >&2
  exit 1
fi
exec "$EGW_WIRING_PY" "$@"
'''

FAKE_HARNESS = r'''"""Stub of 'python -m egw_experiments run' for the runbook's harness_cmd: what the harness does that the capture
depends on, by the harness's own code and in the order of run.py execute_run, and nothing else. It makes the run
directory (one that exists is refused, exit 2), takes the 'before' twin snapshot when --twin-snapshot-cmd is given,
logs a connection line of the broker and of the controller on the stub guest's clock (the workload), issues
--restart-cmd through run.py's _execute_restart_cmd when one is given and holds EGW_WIRING_HOLD_S seconds. Then, as
execute_run does after its events fetch: the drain (--drain-cmd, its outcome read by drain_hook_outcome), the
post-drain copy of the events (--post-drain-fetch-cmd, through fetch_events_via_cmd and verify_post_drain_record),
the 'after' snapshot and, LAST, the three SUT fetch hooks, each through execute_collector_hook. They are judged with
sut_log_fetch_failures and, for a run with a --restart-cmd (a controller_restart run), restart_evidence_failures,
into manifest.json: exit 1 when that makes the run invalid, 0 otherwise. The run directory is then sealed
(SHA256SUMS). Not run.py's: a twin snapshot counts as verified when its hook ended 0 and wrote its file (the devices
of the plan's seed are not checked here). EGW_WIRING_HARNESS_DIES=before-drain ends it with an exception after the
measured run, before its drain: no drain, no fetch, no manifest. Once the three fetches have run, it leaves
LOG.fetches-done and holds EGW_WIRING_HOLD_AFTER_FETCHES_S seconds before it judges and seals them."""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from egw_experiments import run as run_mod
@@CLOCK@@

args = sys.argv[1:]
SERVICES = @@SERVICES@@


def opt(name):
    return args[args.index(name) + 1] if name in args else None


def guest_stamp():
    return datetime.fromtimestamp(now_ns() / 1e9, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f000Z")


run_id = opt("--run-id")
run_dir = Path(opt("--base-dir")) / "raw" / run_id
if run_dir.exists():
    print(f"error: {run_dir} exists", file=sys.stderr)
    sys.exit(2)
sut = run_dir / "logs" / "sut"
sut.mkdir(parents=True)
log = os.environ["EGW_STUB_LOG"]


def hook(name, template, dest, timeout_s=None):
    """One item-18 hook, as execute_run's _run_sut_hook runs it."""
    record = run_mod.execute_collector_hook(name, template, run_id, duration_s=300, dest=dest,
                                            expect_services=SERVICES, log_dir=sut, timeout_s=timeout_s)
    for stream in ("stdout", "stderr"):
        path = record.pop(f"{stream}_path", None)
        if path is not None:
            record[f"{stream}_file"] = Path(path).relative_to(run_dir).as_posix()
    record["dest_exists"] = Path(dest).is_file()
    return record


twin_snapshots = []


def twin(name):
    template = opt("--twin-snapshot-cmd")
    if not template:
        return
    file = run_mod.TWIN_SNAPSHOT_FILES[name]
    record = hook(name, template, run_dir / file, timeout_s=run_mod.SNAPSHOT_TIMEOUT_S)
    record.update({"file": file, "source": "hook", "problems": [],
                   "verified": record.get("returncode") == 0 and record["dest_exists"]})
    twin_snapshots.append(record)


with open(log + ".harness-started", "w", encoding="utf-8") as fh:
    fh.write(run_id)
twin("twin_snapshot_before")
with open(log + ".broker-log", "a", encoding="utf-8") as fh:
    fh.write(f"mosquitto-1  | {guest_stamp()} New client connected from 172.18.0.7:52130 as egw-simulator-{run_id}\n")
with open(log + ".controller-log", "a", encoding="utf-8") as fh:
    fh.write(f"{guest_stamp()} " + json.dumps({"level": "INFO", "logger": "egw_controller.mqtt",
                                               "message": f"MQTT connected ({run_id})"}) + "\n")
restart = {}
if opt("--restart-cmd"):
    run_mod._execute_restart_cmd(opt("--restart-cmd"), run_id, restart)
time.sleep(float(os.environ.get("EGW_WIRING_HOLD_S", "0")))
if os.environ.get("EGW_WIRING_HARNESS_DIES") == "before-drain":
    raise RuntimeError("stub: the harness failed after its measured run, before its drain")
drain = None
if opt("--drain-cmd"):
    drain = hook("drain", opt("--drain-cmd"), sut / run_mod.DRAIN_TRANSCRIPT_FILENAME,
                 timeout_s=run_mod.DRAIN_TIMEOUT_S)
    drain.pop("dest_exists", None)
    drain["source"] = "hook"
    drain["outcome"] = run_mod.drain_hook_outcome(drain, run_dir)
    drain["verified"] = drain["outcome"] != "error"
post_drain = None
if opt("--post-drain-fetch-cmd"):
    ok, command, attempts = run_mod.fetch_events_via_cmd(opt("--post-drain-fetch-cmd"), run_id,
                                                         run_dir / run_mod.POST_DRAIN_EVENTS_FILENAME)
    post_drain = {"template": opt("--post-drain-fetch-cmd"), "command": command, "attempts": attempts, "ok": ok,
                  "file": run_mod.POST_DRAIN_EVENTS_FILENAME, "source": "hook"}
    run_mod.verify_post_drain_record(post_drain, run_dir, run_id)
twin("twin_snapshot_after")
fetches = []
for name, flag in run_mod.SUT_LOG_FETCH_FLAGS.items():
    template = opt(flag)
    if not template:
        continue
    dest = sut / run_mod.SUT_LOG_FILES[name]
    record = hook(name, template, dest)
    record["dest_file"] = dest.relative_to(run_dir).as_posix()
    fetches.append(record)
# The StartedAt read of decision 1a (run.py: --fetch-started-at-cmd into logs/sut/controller-started-at.txt), after
# the docker-events fetch, recorded among the SUT fetches so that a failed read is a reason like theirs.
if opt("--fetch-started-at-cmd"):
    dest = sut / "controller-started-at.txt"
    record = hook("started_at", opt("--fetch-started-at-cmd"), dest)
    record["dest_file"] = dest.relative_to(run_dir).as_posix()
    fetches.append(record)
with open(log + ".fetches-done", "w", encoding="utf-8") as fh:
    fh.write(run_id)
time.sleep(float(os.environ.get("EGW_WIRING_HOLD_AFTER_FETCHES_S", "0")))
reasons = run_mod.sut_log_fetch_failures(fetches)
if opt("--restart-cmd"):
    reasons += run_mod.restart_evidence_failures(twin_snapshots, drain, post_drain)
manifest = {"run_id": run_id, "validity": "invalid" if reasons else "valid", "validity_reasons": reasons,
            "restart": restart, "twin_snapshots": twin_snapshots, "drain": drain,
            "events_post_drain_fetch": post_drain, "sut_log_fetches": fetches}
(run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
sums = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(run_dir).as_posix()}"
        for p in sorted(run_dir.rglob("*")) if p.is_file()]
(run_dir / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
print(f"[harness] run {run_id}: validity {manifest['validity']}")
for reason in reasons:
    print(f"[harness] INVALID: {reason}", file=sys.stderr)
sys.exit(1 if reasons else 0)
'''.replace("@@CLOCK@@", STEADY_CLOCK).replace("@@SERVICES@@", repr(list(EXPECT_SERVICES)))

# The drain the harness runs: proof_hook_drained.sh sources the helper file and calls 'drained' once the stub harness
# has started (test 6's precondition 'drained' runs before it and is the stub's). With EGW_WIRING_DRAIN set, what the
# drain does then and only then, while it would poll /metrics: the controller logs a line and the daemon records an
# exec in egw-mongodb-1 (egw-drain-probe), both of this run; then 'quiet' ends with the stub's quiet line, 'gave-up'
# with the helper's give-up and 'hang' waits (an operator's Ctrl-C never reaches it: the harness runs its hooks in a
# session of their own). The hook's pid is left in LOG.drain-probed.
DRAIN_WRAPPER = r'''
eval "$(declare -f drained | sed '1s/^drained/stub_drained/')"
drained() {
  local rid stamp
  if [ -z "${EGW_WIRING_DRAIN:-}" ] || [ ! -e "$EGW_STUB_LOG.harness-started" ]; then stub_drained "$@"; return; fi
  rid=$(cat "$EGW_STUB_LOG.harness-started")
  stamp=$("$EGW_STUB_GUEST_BIN/date" -u +%Y-%m-%dT%H:%M:%S.500000000Z)
  printf '%s {"level": "INFO", "logger": "egw_controller.service", "message": "drain-only probe (%s)"}\n' \
    "$stamp" "$rid" >> "$EGW_STUB_LOG.controller-log"
  ssh egw-tcg "docker exec egw-mongodb-1 egw-drain-probe $rid" || return 1
  echo "$$" > "$EGW_STUB_LOG.drain-probed"
  sleep 1
  case $EGW_WIRING_DRAIN in
    gave-up) stop "drained: no quiet window of ${DRAIN_QUIET_S:-130} s within ${DRAIN_LIMIT_S:-900} s (last reading: 4 0 0 true 2026-09-19T20:00:00Z 1 64 60 0 0 0 0 0) - do not take snapshots, do not start a run"; return 1;;
    hang) sleep 60;;
  esac
  stub_drained "$@"
}
'''

# $REC of the bench: 'delta' checks that what test 6's delta line names is there - the two twin snapshots beside the
# prefix and the events file - and records its argv; anything else goes to the proof hooks' recording 'snap' stub.
REC_WITH_DELTA = r'''#!/usr/bin/env bash
if [ "${1:-}" = delta ]; then
  printf '%s\n' "$*" >> "$EGW_STUB_LOG.rec-delta"
  prefix=; events=; prev=
  for a in "$@"; do case $prev in --prefix) prefix=$a;; --events) events=$a;; esac; prev=$a; done
  for f in "$prefix.twins.before.json" "$prefix.twins.after.json" "$events"; do
    [ -s "$f" ] || { echo "stub delta: $f is missing or empty" >&2; exit 2; }
  done
  echo "stub delta: read $prefix.twins.before.json, $prefix.twins.after.json and $events"
  exit 0
fi
exec "$EGW_STUB_BIN/rec-snap" "$@"
'''

# A line of the stub guest's logs stamped on its own clock, as the daemon stamps what a container writes now.
GUEST_LOG = r'''
glog() {  # glog broker|controller TEXT
  local stamp
  stamp=$("$EGW_STUB_GUEST_BIN/date" -u +%Y-%m-%dT%H:%M:%S.500000000Z)
  if [ "$1" = broker ]; then printf 'mosquitto-1  | %s %s\n' "$stamp" "$2"; else printf '%s %s\n' "$stamp" "$2"; fi \
    >> "$EGW_STUB_LOG.$1-log"
}
'''


class Wiring:
    """The hooks bench with the runbook's own helpers and the stub harness and simulator."""

    def __init__(self, bench: Hooks) -> None:
        self.hooks = bench
        self.p = bench.bench.home / "egw-tcg" / "itest"
        _write(bench.helpers, ITEST_HELPERS + "\n" + "".join(runbook_function(name) for name in HELPERS)
               + DRAIN_WRAPPER)
        shutil.copyfile(bench.bench.bin / "rec", bench.bench.bin / "rec-snap")
        (bench.bench.bin / "rec-snap").chmod(0o755)
        _write(bench.bench.bin / "rec", REC_WITH_DELTA, executable=True)
        self.harness = bench.bench.tmp / "fake_harness.py"
        _write(self.harness, FAKE_HARNESS)
        _write(bench.bench.bin / "python", PYTHON_STUB, executable=True)

    def env(self, **overrides) -> dict:
        return {"EGW_WIRING_PY": sys.executable, "EGW_WIRING_HARNESS": str(self.harness),
                "PYTHONPATH": str(REPO_ROOT / "src"), **overrides}

    def run(self, body: str, **overrides) -> subprocess.CompletedProcess:
        script = '. "$HOME/egw-tcg/itest-helpers.sh"\n' + GUEST_LOG + body
        return self.hooks.run_argv(["bash", "-c", script], **self.env(**overrides))

    def sut(self, name: str) -> Path:
        return self.p / f"{name}.sut"

    def raw(self, run_id: str) -> Path:
        return self.hooks.bench.home / "egw-tcg" / "pilot" / "results" / "raw" / run_id

    def run_t0(self, name: str) -> int:
        text = (self.sut(name) / "events-start.txt").read_text(encoding="utf-8")
        return int(re.search(r"^run_guest_t0=(\d+)$", text, re.M).group(1))

    def old_logs(self, broker: tuple[str, ...] = (), controller: tuple[str, ...] = ()) -> dict[str, list[str]]:
        """Lines of an earlier session three days ago, in the logs the containers keep across sessions."""
        old = self.hooks.now() - 3 * 86400
        stamp = datetime.fromtimestamp(old, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.250000000Z")
        lines = {"broker": [f"\x1b[2Kmosquitto-1  | {stamp} mosquitto version 2.0.22 starting",
                            *(f"mosquitto-1  | {stamp} {text}" for text in broker)],
                 "controller": [f"{stamp} " + json.dumps({"level": "INFO", "message": "Uvicorn running"}),
                                *(f"{stamp} {text}" for text in controller)]}
        for kind, text in lines.items():
            Path(f"{self.hooks.bench.log}.{kind}-log").write_text("\n".join(text) + "\n", encoding="utf-8")
        return lines


@pytest.fixture
def wiring(hooks) -> Wiring:  # noqa: F811 - the fixture of test_proof_hooks
    return Wiring(hooks)


def coverage(path: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, rest = line.partition("=")
        out.setdefault(key, []).append(rest)
    return out


def events_of(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


T6_RID = "controller_restart-r01"
# The configuration identity of test 6 (config_identity of 6.1 reads the guest): a write-once stand-in, which the stub
# harness does not read.
CONFIG_IDENTITY_STUB = ('config_identity() { [ ! -e "$1" ] || return 1; '
                        "echo '{\"stub\": \"configuration identity\"}' > \"$1\"; }")


def _t6_lines(wiring: Wiring, until_harness: bool = False) -> str:
    """Test 6's commands as the runbook gives them - every command but the closing 'analyze', or those up to and
    including the harness line - then T6's value; the plan holds the run's seed and the stub guest holds the run's
    events, which the post-drain copy fetches."""
    bench = wiring.hooks.bench
    plan = bench.home / "egw-tcg" / "pilot" / "campaign_plan.json"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(json.dumps({"runs": [{"run_id": T6_RID, "seed": 7}]}), encoding="utf-8")
    events = bench.guest_root / "opt" / "egw" / "deployment" / "data" / "events" / T6_RID / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text(json.dumps({"run_id": T6_RID, "message_id": "m-1", "outcome": "accepted"}) + "\n",
                      encoding="utf-8")
    cmds = _host_commands("### Test 6")
    harness = cmds.index(_one(cmds, "T6=stop; if"))
    chosen = cmds[:harness + 1] if until_harness else \
        [c for c in cmds if not c.startswith("python -m egw_experiments analyze")]
    return "\n".join((CONFIG_IDENTITY_STUB, *chosen, 'echo "T6=$T6"'))


def _t6_value(result: subprocess.CompletedProcess) -> str | None:
    values = re.findall(r"^T6=(.*)$", result.stdout, re.M)
    return values[-1] if values else None


def _stop_record(sut: Path) -> dict[str, str]:
    lines = (sut / "docker-events.stop.txt").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


def _drain_probe(captured: list[dict]) -> list[dict]:
    """The exec the drain alone caused (DRAIN_WRAPPER), as the daemon recorded it."""
    return [e for e in captured if e["Action"].startswith(f"exec_create: egw-drain-probe {T6_RID}")]


# --------------------------------------------------------------------------
# tools/session/events_capture.sh: one source of the recorder's lifecycle
# --------------------------------------------------------------------------


def test_the_host_command_sends_the_guest_command_proof_sh_renders_and_starts_and_cleans_up_a_unit(wiring):
    hooks, rid = wiring.hooks, "cap-r01"
    capture = SESSION / "events_capture.sh"
    start = hooks.run_argv(["bash", str(capture), "start", rid])
    assert start.returncode == 0, report(start)
    t0 = int(re.search(r"^run_guest_t0=(\d+)$", start.stdout, re.M).group(1))
    assert hooks.recorder_running(rid) and abs(t0 - hooks.now()) <= 5
    # One text: what the host command sent is what proof.sh renders (the file sourced, the function called).
    recorder = SESSION / "proof_events_recorder.sh"
    rendered = capture_script("events_recorder_script", {**os.environ, "RID": rid, "RECORDER": str(recorder),
                                                         "RECORDER_SHA": hashlib.sha256(recorder.read_bytes()).hexdigest()})
    assert rendered in hooks.bench.log.read_text(encoding="utf-8")
    again = hooks.run_argv(["bash", str(capture), "start", rid])
    assert again.returncode == 1 and "is write-once; nothing was started" in again.stdout, report(again)
    keep = wiring.p / "cap-r01.sut" / "events-partial"
    clean = hooks.run_argv(["bash", str(capture), "cleanup", rid, str(keep)])
    assert clean.returncode == 0, report(clean)
    assert "unit_state_before_cleanup=active" in clean.stdout and not hooks.recorder_running(rid)
    assert (keep / "events.partial.jsonl").stat().st_size > 0 and not (keep / "events.jsonl").exists()
    life = (keep / "lifecycle.txt").read_text(encoding="utf-8").splitlines()
    assert life[-1].startswith("cli-exit ") and life[-1].endswith("stop_requested=yes"), life
    assert (keep / "start-facts.txt").is_file() and (keep / "cli-stderr.txt").is_file()
    twice = hooks.run_argv(["bash", str(capture), "cleanup", rid, str(keep)])
    assert twice.returncode == 1 and f"{keep} exists - NOT overwritten" in twice.stderr, report(twice)


def test_a_keep_dir_that_exists_is_not_overwritten_but_the_unit_is_still_stopped(wiring):
    """Write-once applies to the host copy only: the guest's cleanup runs whatever KEEP_DIR's state."""
    hooks, rid = wiring.hooks, "cap-r02"
    capture = SESSION / "events_capture.sh"
    assert hooks.run_argv(["bash", str(capture), "start", rid]).returncode == 0
    keep = wiring.p / f"{rid}.sut" / "events-partial"
    keep.mkdir(parents=True)
    (keep / "events.partial.jsonl").write_text("an earlier copy\n", encoding="utf-8")
    clean = hooks.run_argv(["bash", str(capture), "cleanup", rid, str(keep)])
    assert clean.returncode == 1 and f"{keep} exists - NOT overwritten" in clean.stderr, report(clean)
    assert "unit_state_before_cleanup=active" in clean.stdout and not hooks.recorder_running(rid), report(clean)
    assert (keep / "events.partial.jsonl").read_text(encoding="utf-8") == "an earlier copy\n"
    assert sorted(p.name for p in keep.iterdir()) == ["events.partial.jsonl"]


def test_a_cleanup_that_did_not_reach_the_guest_keeps_nothing_and_can_be_repeated_to_stop_the_unit(wiring):
    """events_cleanup (6.1) while ssh to the guest fails: the unit is not stopped and no keep directory is made, so
    the repeated cleanup, once the guest answers, stops it and keeps what it captured."""
    rid = "smoke_sequence-r06"
    start = wiring.run(f'events_start {rid}; echo "ES=$?"')
    assert "ES=0" in start.stdout, report(start)
    keep = wiring.sut(rid) / "events-partial"
    records = wiring.hooks.bench.tmp / "no-stop-record"
    first = wiring.run(f'events_cleanup {rid} {records}; echo "EC1=$?"', EGW_STUB_SSH_REFUSE="unit_state_before_cleanup")
    assert "EC1=1" in first.stdout and f"STOP: events_cleanup {rid}: " in first.stderr, report(first)
    assert wiring.hooks.recorder_running(rid) and not keep.exists(), report(first)
    second = wiring.run(f'events_cleanup {rid} {records}; echo "EC2=$?"')
    assert "EC2=0" in second.stdout, report(second)
    assert not wiring.hooks.recorder_running(rid), "the repeated cleanup did not stop the unit"
    assert (keep / "events.partial.jsonl").stat().st_size > 0 and (keep / "lifecycle.txt").is_file()


def test_a_cleanup_whose_copy_failed_can_be_repeated_and_then_keeps_the_whole_capture(wiring):
    """The copy is write-once as a whole: a cleanup that stopped the unit but whose copies failed leaves no
    events-partial/, so its repeat, once the guest answers, keeps the recorder's four files there (review of part B,
    item 2: an events-partial/ made before the copies stayed empty and refused every repeat)."""
    rid = "smoke_sequence-r10"
    start = wiring.run(f'events_start {rid}; echo "ES=$?"')
    assert "ES=0" in start.stdout, report(start)
    keep = wiring.sut(rid) / "events-partial"
    records = wiring.hooks.bench.tmp / "no-stop-record"
    first = wiring.run(f'events_cleanup {rid} {records}; echo "EC1=$?"', EGW_STUB_SCP_FAIL="egw-events-")
    assert "EC1=1" in first.stdout and f"STOP: events_cleanup {rid}: " in first.stderr, report(first)
    assert not wiring.hooks.recorder_running(rid), report(first)
    assert not keep.exists(), f"{keep} was made by a copy that failed: " + report(first)
    second = wiring.run(f'events_cleanup {rid} {records}; echo "EC2=$?"')
    assert "EC2=0" in second.stdout, report(second)
    assert sorted(p.name for p in keep.iterdir()) == ["cli-stderr.txt", "events.partial.jsonl", "lifecycle.txt",
                                                      "start-facts.txt"]
    assert (keep / "events.partial.jsonl").stat().st_size > 0
    assert sorted(p.name for p in wiring.sut(rid).iterdir()) == ["events-partial", "events-start.txt"], \
        "a staging copy was left beside the capture"


def test_a_start_whose_session_dropped_and_whose_cleanup_failed_says_the_unit_may_still_run(wiring):
    """The ssh of the start drops once the guest has started the unit (255), and the cleanup after it cannot reach
    the guest: the STOP never claims the unit was stopped - it says it may still run and names the repeat (review of
    part B, item 3)."""
    rid = "smoke_sequence-r11"
    result = wiring.run(f'T0=$(events_start {rid}); echo "ES=$?"', EGW_STUB_SSH_DROP="run_guest_t0=",
                        EGW_STUB_SSH_REFUSE="unit_state_before_cleanup")
    assert "ES=0" not in result.stdout, report(result)
    assert wiring.hooks.recorder_running(rid), "the case needs the unit the dropped session had started"
    stop = next(ln for ln in result.stderr.splitlines() if ln.startswith(f"STOP: events_start {rid}: "))
    assert "NOT found ready" in stop and f"egw-events-{rid} may still run" in stop, stop
    assert f"events_capture.sh cleanup {rid}" in stop, stop
    again = wiring.hooks.run_argv(["bash", str(SESSION / "events_capture.sh"), "cleanup", rid])
    assert again.returncode == 0 and not wiring.hooks.recorder_running(rid), report(again)


def _stops(hooks, rid: str) -> int:
    """How many 'systemctl stop' calls ended the unit (the systemctl stub's record)."""
    path = Path(f"{hooks.bench.log}.unit-egw-events-{rid}.stops")
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def test_a_cleanup_stops_an_activating_unit_and_ends_0_only_once_it_is_shown_stopped(wiring):
    """Review of PR #51, P1: only 'inactive' and 'failed' are stopped; a unit in a state between (here 'activating')
    was left running with exit 0, and its capture copied as partial while it still ran."""
    hooks, rid = wiring.hooks, "cap-r03"
    capture = SESSION / "events_capture.sh"
    assert hooks.run_argv(["bash", str(capture), "start", rid]).returncode == 0
    keep = wiring.p / f"{rid}.sut" / "events-partial"
    clean = hooks.run_argv(["bash", str(capture), "cleanup", rid, str(keep)], EGW_STUB_FAIL="events-activating")
    assert "unit_state_before_cleanup=activating" in clean.stdout, report(clean)
    assert "cleanup_stop_requested_guest_epoch=" in clean.stdout, report(clean)
    assert not hooks.recorder_running(rid) and _stops(hooks, rid) == 1, report(clean)
    assert "unit_state_after_cleanup=inactive" in clean.stdout and clean.returncode == 0, report(clean)
    assert sorted(p.name for p in keep.iterdir()) == ["cli-stderr.txt", "events.partial.jsonl", "lifecycle.txt",
                                                      "start-facts.txt"]


@pytest.mark.parametrize("token, after", [("events-stop-noeffect", "active"), ("events-state-unreadable", "unknown")])
def test_a_cleanup_that_cannot_show_the_unit_stopped_fails_says_it_may_still_run_and_copies_nothing(wiring, token,
                                                                                                    after):
    """Review of PR #51, P1: a stop with no effect, or a state that cannot be read, never ends the cleanup 0 - the
    host command (and the runbook's events_cleanup) STOPs saying the unit may still run, and no partial copy is made
    while it may still write; once it can be shown stopped, the repeated cleanup keeps the capture."""
    hooks, rid = wiring.hooks, f"cap-{token}"
    capture = SESSION / "events_capture.sh"
    assert hooks.run_argv(["bash", str(capture), "start", rid]).returncode == 0
    keep = wiring.p / f"{rid}.sut" / "events-partial"
    clean = hooks.run_argv(["bash", str(capture), "cleanup", rid, str(keep)], EGW_STUB_FAIL=token)
    assert clean.returncode != 0, report(clean)
    assert "cleanup_stop_requested_guest_epoch=" in clean.stdout, report(clean)
    assert f"unit_state_after_cleanup={after}" in clean.stdout, report(clean)
    stop = next(ln for ln in clean.stderr.splitlines() if ln.startswith("STOP: events_capture: "))
    assert f"egw-events-{rid} was not shown stopped" in stop and "may still run" in stop, stop
    assert not wiring.sut(rid).exists() or not any(wiring.sut(rid).iterdir()), report(clean)
    bare = hooks.run_argv(["bash", str(capture), "cleanup", rid], EGW_STUB_FAIL=token)
    assert bare.returncode != 0 and "may still run" in bare.stderr, report(bare)
    records = hooks.bench.tmp / "no-stop-record"
    runbook = wiring.run(f'events_cleanup {rid} {records}; echo "EC=$?"', EGW_STUB_FAIL=token)
    assert "EC=1" in runbook.stdout, report(runbook)
    stop = next(ln for ln in runbook.stderr.splitlines() if ln.startswith(f"STOP: events_cleanup {rid}: "))
    assert "may still run" in stop, stop
    assert not keep.exists(), report(runbook)
    again = wiring.run(f'events_cleanup {rid} {records}; echo "EC=$?"')
    assert "EC=0" in again.stdout and not hooks.recorder_running(rid), report(again)
    assert (keep / "events.partial.jsonl").stat().st_size > 0


def test_a_cleanup_of_a_unit_the_fetch_already_stopped_requests_no_stop_and_keeps_the_capture(wiring):
    """The normal path, unchanged: the docker-events fetch stopped the unit ('inactive'), so the cleanup stops
    nothing, ends 0 and keeps what the recorder captured."""
    hooks, rid = wiring.hooks, "cap-r04"
    capture = SESSION / "events_capture.sh"
    assert hooks.run_argv(["bash", str(capture), "start", rid]).returncode == 0
    assert hooks.run_argv(["ssh", "egw-tcg", f"sudo systemctl stop egw-events-{rid}"]).returncode == 0
    assert not hooks.recorder_running(rid) and _stops(hooks, rid) == 1
    keep = wiring.p / f"{rid}.sut" / "events-partial"
    clean = hooks.run_argv(["bash", str(capture), "cleanup", rid, str(keep)])
    assert clean.returncode == 0, report(clean)
    assert "unit_state_before_cleanup=inactive" in clean.stdout, report(clean)
    assert "cleanup_stop_requested_guest_epoch=" not in clean.stdout and _stops(hooks, rid) == 1, report(clean)
    assert (keep / "events.partial.jsonl").stat().st_size > 0


def test_the_host_command_refuses_what_it_cannot_use_before_the_guest_is_reached(wiring):
    capture = SESSION / "events_capture.sh"
    for args in (["start"], ["start", "../x"], ["start", "a b"], ["stop", "r01"], ["cleanup", "r01", "k", "x"]):
        result = wiring.hooks.run_argv(["bash", str(capture), *args])
        assert result.returncode == 2, (args, report(result))
        assert result.stderr.startswith("STOP: events_capture: "), (args, report(result))
    assert wiring.hooks.ssh_commands() == []


def test_proof_sh_sources_the_shared_lifecycle_and_keeps_no_copy_of_it():
    text = (SESSION / "proof.sh").read_text(encoding="utf-8")
    assert '. "$(dirname "$0")/events_capture.sh"' in text
    assert "events_recorder_script() {" not in text and "events_cleanup_script() {" not in text
    assert 'gx_bounded events-recorder-start "$LIVE_REST" "$(events_recorder_script)"' in text
    assert 'gx "$A" events-recorder-cleanup "$(events_cleanup_script)"' in text


# --------------------------------------------------------------------------
# Tests 1 and 6: harness_cmd / harness_run
# --------------------------------------------------------------------------


def test_a_fault_free_harness_run_is_captured_from_readiness_and_its_logs_are_the_runs_only(wiring):
    rid = "smoke_sequence-r01"
    old = wiring.old_logs(broker=("New client connected from 172.18.0.7:40000 as egw-simulator-smoke_sequence-r01",))
    result = wiring.run(f'harness_run {rid}; echo "RC=$?"')
    assert "RC=0" in result.stdout, report(result)
    run_dir = wiring.raw(rid)
    sut = run_dir / "logs" / "sut"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["validity"] == "valid" and manifest["validity_reasons"] == [], manifest
    t0 = wiring.run_t0(rid)
    # Stale-log exclusion: an earlier session's lines - one of the same client id among them - are left out of the
    # run's copies, and witnessed by count only.
    broker = (sut / "broker.log").read_text(encoding="utf-8").splitlines()
    assert len(broker) == 1 and broker[0].endswith(f"as egw-simulator-{rid}") and not set(old["broker"]) & set(broker)
    controller = (sut / "controller.log").read_text(encoding="utf-8").splitlines()
    assert len(controller) == 1 and f"MQTT connected ({rid})" in controller[0]
    hook_out = (sut / "hook-broker_log.stdout.txt").read_text(encoding="utf-8")
    assert f"since_guest_epoch={t0} " in hook_out
    # (the stub daemon's '--until' is whole seconds: a run line of RUN_T0's own second may be counted beside them)
    assert int(re.search(r"excluded_before_since_lines=(\d+) ", hook_out).group(1)) >= len(old["broker"])
    # The events: captured from readiness to the fetch's stop, complete, no fault event demanded.
    cov = coverage(sut / "docker-events.coverage.txt")
    assert cov["coverage"] == ["complete"] and cov["expected"] == ["none"], cov
    assert cov["requested_since_guest_epoch"] == [str(t0)] and cov["rule_R7"][0].startswith("not-required")
    assert (sut / "docker-events.log").is_file()
    assert not wiring.hooks.recorder_running(rid)
    assert not (wiring.sut(rid) / "events-partial").exists(), "the fetch kept the records: nothing kept twice"


def test_the_test_6_restart_is_judged_by_its_own_events_and_never_by_the_proofs_sigkill(wiring):
    rid = T6_RID
    wiring.old_logs()
    result = wiring.run(_t6_lines(wiring, until_harness=True))
    assert _t6_value(result) == "ok", report(result)
    sut = wiring.raw(rid) / "logs" / "sut"
    cov = coverage(sut / "docker-events.coverage.txt")
    assert cov["coverage"] == ["complete"] and cov["expected"] == ["die,start"], cov
    assert cov["container"] == ["egw-controller-1"] and cov["rule_R7"][0].startswith("held: ")
    captured = events_of(sut / "docker-events.log")
    kills = [e for e in captured if e["Action"] == "kill" and e["Actor"]["Attributes"]["name"] == "egw-controller-1"]
    assert kills and all(e["Actor"]["Attributes"]["signal"] == "15" for e in kills), "a compose restart: SIGTERM"
    # The proof's own R7, unchanged, would not accept this capture: its kill must carry signal 9.
    judged = wiring.hooks.bench.tmp / "judge"
    judged.mkdir()
    for kept, name in (("docker-events.log", "events.jsonl"), ("docker-events.lifecycle.txt", "lifecycle.txt"),
                       ("docker-events.start-facts.txt", "start-facts.txt"), ("docker-events.cli-stderr.txt", "cli.stderr"),
                       ("docker-events.stop.txt", "stop.txt")):
        shutil.copyfile(sut / kept, judged / name)
    proof_r7 = subprocess.run([sys.executable, str(SESSION / "events_coverage.py"), str(judged), "--run-t0",
                               cov["requested_since_guest_epoch"][0], "--expected", "kill,die,start"],
                              capture_output=True, text=True)
    assert proof_r7.returncode == 1, proof_r7.stdout
    assert "rule_R7=broken: the expected event(s) kill (signal 9) of egw-controller-1" in proof_r7.stdout


def test_test_6_reads_the_restarted_controllers_started_at_after_its_capture_and_seals_it(wiring):
    """Decision 1a (adopted 2026-09-30): the harness's StartedAt read runs the checkout's fetch_started_at.sh on the
    guest after the docker-events fetch, and its record - the controller the compose restart started again - is
    sealed in the run's logs/sut/; the line then prints one read-only summary of resources_proved_down."""
    wiring.old_logs()
    result = wiring.run(_t6_lines(wiring, until_harness=True))
    assert _t6_value(result) == "ok", report(result)
    run_dir = wiring.raw(T6_RID)
    record = (run_dir / "logs" / "sut" / "controller-started-at.txt").read_text(encoding="utf-8").splitlines()
    assert record[:3] == ["container=egw-controller-1", "container_id=" + "0f" * 32,
                          "started_at=2026-09-25T10:05:01.200000000Z"], record
    assert re.fullmatch(r"guest_epoch=\d+", record[3]) and len(record) == 4, record
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    fetches = manifest["sut_log_fetches"]
    assert [f["hook"] for f in fetches][-2:] == ["docker_events", "started_at"]
    assert fetches[-1]["returncode"] == 0 and fetches[-1]["dest_exists"] is True
    assert "logs/sut/controller-started-at.txt" in (run_dir / "SHA256SUMS").read_text(encoding="utf-8")
    assert re.search(r"^test 6: resources_proved_down: ", result.stdout, re.M), report(result)


def test_test_6_whose_started_at_read_failed_is_invalid_and_never_ok(wiring):
    wiring.old_logs()
    result = wiring.run(_t6_lines(wiring, until_harness=True), EGW_STUB_FAIL="inspect-fails")
    assert _t6_value(result) == "stop", report(result)
    assert not (wiring.raw(T6_RID) / "logs" / "sut" / "controller-started-at.txt").exists()
    assert "[harness] INVALID: SUT fetch --fetch-started-at-cmd failed" in result.stderr, report(result)
    assert "STOP: test 6: the harness run was not sealed, or it exited 1" in result.stderr, report(result)


def test_a_capture_whose_closing_marker_never_arrives_leaves_the_run_invalid_and_no_docker_events_log(wiring):
    rid = "smoke_sequence-r02"
    wiring.old_logs()
    result = wiring.run(f'harness_run {rid}; echo "RC=$?"', EGW_STUB_EVENTS_STALL_AFTER="3")
    assert "RC=0" not in result.stdout, report(result)
    assert f"STOP: harness_run {rid}: egw_experiments run exited non-zero" in result.stderr, report(result)
    sut = wiring.raw(rid) / "logs" / "sut"
    manifest = json.loads((wiring.raw(rid) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["validity"] == "invalid"
    assert any("--fetch-docker-events-cmd failed" in r for r in manifest["validity_reasons"]), manifest
    assert not (sut / "docker-events.log").exists() and (sut / "docker-events.partial.jsonl").is_file()
    cov = coverage(sut / "docker-events.coverage.txt")
    assert cov["coverage"] == ["incomplete"] and cov["rule_R5"][0].startswith("broken: the closing marker"), cov
    assert not wiring.hooks.recorder_running(rid)
    # The two logs were read all the same; only the events are not shown complete.
    assert (sut / "broker.log").is_file() and (sut / "controller.log").is_file()


@pytest.mark.parametrize("token, says", [
    ("events-silent", "NOT READY: the recorder unit egw-events-"),
    ("events-unit-fails", "STOP: the recorder unit egw-events-"),
])
def test_a_recorder_not_ready_never_starts_the_harness_and_leaves_no_unit_running(wiring, token, says):
    rid = "smoke_sequence-r03"
    result = wiring.run(f'harness_cmd {rid}; echo "HC=$?"', EGW_STUB_FAIL=token)
    assert "HC=2" in result.stdout, report(result)
    assert f"STOP: harness_cmd {rid}: the harness was NOT started" in result.stderr, report(result)
    assert not Path(f"{wiring.hooks.bench.log}.harness-started").exists()
    assert not wiring.raw(rid).exists()
    assert not wiring.hooks.recorder_running(rid)
    assert says in (wiring.sut(rid) / "events-start.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=["TERM", "INT"])
def test_an_interrupted_harness_run_stops_the_recorder_and_keeps_what_it_captured(wiring, sig):
    rid = "smoke_sequence-r04"
    wiring.old_logs()
    script = '. "$HOME/egw-tcg/itest-helpers.sh"\n' + f'harness_run {rid}; echo "RC=$?"'
    proc = subprocess.Popen(["bash", "-c", script], env=wiring.hooks.env(**wiring.env(EGW_WIRING_HOLD_S="120")),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        wiring.hooks.wait_for(lambda: Path(f"{wiring.hooks.bench.log}.harness-started").exists(), limit_s=90)
        assert wiring.hooks.recorder_running(rid)
        os.killpg(proc.pid, sig)          # the operator's Ctrl-C, or a TERM, reaches the whole step
        out, err = proc.communicate(timeout=120)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
    assert f"harness_cmd {rid}: interrupted" in err, out + err
    assert not wiring.hooks.recorder_running(rid), "the unit was left running after the interruption"
    keep = wiring.sut(rid) / "events-partial"
    assert (keep / "events.partial.jsonl").stat().st_size > 0, out + err
    life = (keep / "lifecycle.txt").read_text(encoding="utf-8").splitlines()
    assert [line.split()[0] for line in life] == ["start", "cli-start", "ready", "cli-exit"], life
    assert life[-1].endswith("stop_requested=yes")
    # Never the run's capture: no docker-events.log was written anywhere.
    assert not list(wiring.hooks.bench.home.rglob("docker-events.log"))


def _interrupt_once(wiring, body: str, ready, sig, **overrides) -> tuple[str, str]:
    """Runs the helpers and BODY as one step (its own process group), sends SIG to the whole group once READY()
    holds, and returns what the step printed when it ended."""
    script = '. "$HOME/egw-tcg/itest-helpers.sh"\n' + body
    proc = subprocess.Popen(["bash", "-c", script], env=wiring.hooks.env(**wiring.env(**overrides)),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        wiring.hooks.wait_for(ready, limit_s=60)
        os.killpg(proc.pid, sig)
        return proc.communicate(timeout=120)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM], ids=["INT", "TERM"])
@pytest.mark.parametrize("body", ['harness_run {rid}; echo "RC=$?"', 'R={rid}; T0_7=$(events_start $R); echo "ES=$?"'],
                         ids=["harness_run", "test_7_start"])
def test_an_interruption_while_the_recorder_starts_leaves_no_unit_running_and_starts_nothing(wiring, sig, body):
    """Tests 1/6 (harness_run) and 7 (T0_7=$(events_start $R)): the unit is started and the start step still waits for
    its readiness when the step is interrupted: events_start stops the unit before it ends."""
    rid = "smoke_sequence-r05"
    out, err = _interrupt_once(wiring, body.format(rid=rid), lambda: wiring.hooks.recorder_running(rid), sig,
                               EGW_STUB_FAIL="events-silent")
    assert not Path(f"{wiring.hooks.bench.log}.harness-started").exists()
    assert not wiring.hooks.recorder_running(rid), "the unit was left running after the interruption: " + out + err
    assert f"STOP: events_start {rid}: interrupted" in err, out + err


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM], ids=["INT", "TERM"])
def test_an_interruption_after_the_recorder_is_ready_but_before_the_harness_stops_the_unit(wiring, sig):
    """The instant between the readiness (events_start has answered) and the harness's start is covered too: the
    step's events_start is held there by a wrapper of the runbook's own function."""
    rid = "smoke_sequence-r07"
    gap = Path(f"{wiring.hooks.bench.log}.start-returned")
    body = ('eval "$(declare -f events_start | sed \'1s/^events_start/real_events_start/\')"\n'
            'events_start() { real_events_start "$@"; local rc=$?; : > "$EGW_STUB_LOG.start-returned"; sleep 60; '
            'return $rc; }\n' + f'harness_run {rid}; echo "RC=$?"')
    out, err = _interrupt_once(wiring, body, gap.exists, sig)
    assert wiring.run_t0(rid) > 0, "the recorder had been found ready"
    assert not Path(f"{wiring.hooks.bench.log}.harness-started").exists(), out + err
    assert not wiring.hooks.recorder_running(rid), "the unit was left running after the interruption: " + out + err
    assert f"harness_cmd {rid}: interrupted" in err and f"STOP: harness_cmd {rid}: the harness was NOT started" in err


@pytest.mark.parametrize("where", ["while_it_starts", "before_the_harness"])
def test_an_interruption_whose_cleanup_cannot_reach_the_guest_says_the_unit_may_still_run(wiring, where):
    """events_start's interruption and harness_cmd's: the cleanup that follows cannot reach the guest, so the STOP
    says the unit may still run and names the repeat, never that it was stopped (review of part B, item 3)."""
    rid = "smoke_sequence-r12"
    refuse = {"EGW_STUB_SSH_REFUSE": "unit_state_before_cleanup"}
    if where == "while_it_starts":
        out, err = _interrupt_once(wiring, f'R={rid}; T0_7=$(events_start $R); echo "ES=$?"',
                                   lambda: wiring.hooks.recorder_running(rid), signal.SIGINT,
                                   EGW_STUB_FAIL="events-silent", **refuse)
        prefix = f"STOP: events_start {rid}: interrupted"
    else:
        gap = Path(f"{wiring.hooks.bench.log}.start-returned")
        body = ('eval "$(declare -f events_start | sed \'1s/^events_start/real_events_start/\')"\n'
                'events_start() { real_events_start "$@"; local rc=$?; : > "$EGW_STUB_LOG.start-returned"; sleep 60; '
                'return $rc; }\n' + f'harness_run {rid}; echo "RC=$?"')
        out, err = _interrupt_once(wiring, body, gap.exists, signal.SIGINT, **refuse)
        prefix = f"STOP: harness_cmd {rid}: the harness was NOT started"
    assert not Path(f"{wiring.hooks.bench.log}.harness-started").exists(), out + err
    assert wiring.hooks.recorder_running(rid), "the case needs a cleanup that could not reach the guest: " + out + err
    stop = next((ln for ln in err.splitlines() if ln.startswith(prefix)), out + err)
    assert f"egw-events-{rid} may still run" in stop and f"events_capture.sh cleanup {rid}" in stop, stop


def test_a_harness_fetch_that_stopped_the_unit_but_kept_no_capture_leaves_it_to_the_ending(wiring):
    """The docker-events fetch reached the guest's stop (its stop record is written) but its copy of the capture
    failed: the run is invalid, and the ending, finding neither docker-events.log nor docker-events.partial.jsonl,
    keeps what the recorder captured in events-partial/ (review of part B, item 1: the stop record alone was read as
    the capture kept)."""
    rid = "smoke_sequence-r09"
    wiring.old_logs()
    result = wiring.run(f'harness_run {rid}; echo "RC=$?"', EGW_STUB_SCP_FAIL_DEST="events.jsonl")
    assert "RC=0" not in result.stdout, report(result)
    manifest = json.loads((wiring.raw(rid) / "manifest.json").read_text(encoding="utf-8"))
    assert any("--fetch-docker-events-cmd failed" in r for r in manifest["validity_reasons"]), manifest
    sut = wiring.raw(rid) / "logs" / "sut"
    assert (sut / "docker-events.stop.txt").is_file()
    assert not (sut / "docker-events.log").exists() and not (sut / "docker-events.partial.jsonl").exists()
    assert not wiring.hooks.recorder_running(rid)
    keep = wiring.sut(rid) / "events-partial"
    assert (keep / "events.partial.jsonl").is_file(), report(result)
    assert (keep / "events.partial.jsonl").stat().st_size > 0
    assert not list(wiring.hooks.bench.home.rglob("docker-events.log"))


def test_harness_cmd_refuses_a_run_directory_another_execution_left_before_any_recorder_starts(wiring):
    """The harness refuses a run directory that exists, and the records in it are another execution's: harness_cmd
    refuses it first (2), so no recorder is started whose ending would decide from them (review of part B,
    item 1)."""
    rid = "smoke_sequence-r08"
    old_sut = wiring.raw(rid) / "logs" / "sut"
    old_sut.mkdir(parents=True)
    for name in ("docker-events.log", "docker-events.stop.txt"):
        (old_sut / name).write_text("an earlier execution's record\n", encoding="utf-8")
    result = wiring.run(f'harness_cmd {rid}; echo "HC=$?"')
    assert "HC=2" in result.stdout, report(result)
    assert f"STOP: harness_cmd {rid}: " in result.stderr and "the harness was NOT started" in result.stderr, \
        report(result)
    assert not wiring.sut(rid).exists(), "a recorder was started for a run the harness refuses: " + report(result)
    assert not any(f"egw-events-{rid}" in c for c in wiring.hooks.ssh_commands())
    assert not Path(f"{wiring.hooks.bench.log}.harness-started").exists()
    assert {p.name: p.read_text(encoding="utf-8") for p in old_sut.iterdir()} == \
        {"docker-events.log": "an earlier execution's record\n", "docker-events.stop.txt": "an earlier execution's record\n"}


# --------------------------------------------------------------------------
# Test 6: the drain and the post-drain copy inside the run's own capture (review of PR #51, B1)
# --------------------------------------------------------------------------


def _assert_the_drain_is_inside_the_capture(wiring: Wiring) -> tuple[Path, dict]:
    """The exec and the controller line that only the drain produced are in the run's sealed capture, and the
    recorder's stop and its closing marker come after them on the guest's clock."""
    assert Path(f"{wiring.hooks.bench.log}.drain-probed").exists(), "the drain never ran once the harness had started"
    run_dir = wiring.raw(T6_RID)
    sut = run_dir / "logs" / "sut"
    captured = events_of(sut / "docker-events.log")
    probes = _drain_probe(captured)
    assert len(probes) == 1, "the event only the drain caused is not in the run's docker-events.log"
    probe = probes[0]
    assert probe["Actor"]["Attributes"]["name"] == "egw-mongodb-1"
    assert f"drain-only probe ({T6_RID})" in (sut / "controller.log").read_text(encoding="utf-8"), \
        "the controller line only the drain caused is not in the run's controller.log"
    stop = _stop_record(sut)
    marker = next(e for e in captured if stop["closing_marker"] in e["Action"])
    assert wiring.run_t0(T6_RID) <= probe["time"] <= int(stop["stop_requested_guest_epoch"])
    assert probe["timeNano"] < marker["timeNano"], "the closing marker came before the drain's event"
    assert coverage(sut / "docker-events.coverage.txt")["coverage"] == ["complete"]
    assert not wiring.hooks.recorder_running(T6_RID)
    return run_dir, json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


def test_test_6_its_drain_and_post_drain_copy_are_inside_the_runs_capture_and_the_stop_comes_after(wiring):
    """The finite proof's restart-evidence hooks run by test 6's harness: the drain (a quiet window), the post-drain
    copy and the 'after' snapshot come before the three SUT fetches, so what the drain alone caused is in the sealed
    docker-events.log and controller.log; delta then reads the twin hook's siblings and the post-drain copy."""
    wiring.old_logs()
    result = wiring.run(_t6_lines(wiring), EGW_WIRING_DRAIN="quiet")
    run_dir, manifest = _assert_the_drain_is_inside_the_capture(wiring)
    assert manifest["validity"] == "valid" and manifest["validity_reasons"] == [], manifest
    assert manifest["drain"]["outcome"] == "quiet" and manifest["drain"]["source"] == "hook"
    transcript = (run_dir / manifest["drain"]["stdout_file"]).read_text(encoding="utf-8")
    assert f"proof_hook_drained: {T6_RID}: drained with DRAIN_QUIET_S=130 DRAIN_STEP_S=5 DRAIN_LIMIT_S=900" in transcript
    assert manifest["events_post_drain_fetch"]["verified"] and (run_dir / "events.post-drain.jsonl").is_file()
    for label in ("before", "after"):
        assert (wiring.p / f"{T6_RID}.twins.{label}.json").read_bytes() == \
            (run_dir / f"twins.{label}.json").read_bytes()
    assert (run_dir / "SHA256SUMS").is_file()
    assert _t6_value(result) == "ok", report(result)
    delta = Path(f"{wiring.hooks.bench.log}.rec-delta").read_text(encoding="utf-8").splitlines()
    assert delta == [f"delta {run_dir} --prefix {wiring.p}/{T6_RID} --events {run_dir}/events.post-drain.jsonl"]
    assert "stub delta: read " in result.stdout and "STOP: test 6" not in result.stderr, report(result)


def test_test_6_a_drain_that_gives_up_is_captured_the_post_drain_copy_still_runs_and_the_run_records_gave_up(wiring):
    wiring.old_logs()
    result = wiring.run(_t6_lines(wiring), EGW_WIRING_DRAIN="gave-up")
    run_dir, manifest = _assert_the_drain_is_inside_the_capture(wiring)
    assert manifest["drain"]["outcome"] == "gave-up" and manifest["validity"] == "valid", manifest
    stderr = (run_dir / manifest["drain"]["stderr_file"]).read_text(encoding="utf-8")
    assert "STOP: drained: no quiet window of 130 s within 900 s" in stderr
    assert manifest["events_post_drain_fetch"]["verified"] and (run_dir / "events.post-drain.jsonl").is_file()
    assert _t6_value(result) == "gaveup", report(result)
    assert "STOP: test 6: the drain gave up" in result.stderr, report(result)
    assert not Path(f"{wiring.hooks.bench.log}.rec-delta").exists(), "delta ran on a drain that gave up"


def test_test_6_a_harness_that_fails_before_its_drain_stops_the_unit_and_keeps_the_partial_capture(wiring):
    wiring.old_logs()
    result = wiring.run(_t6_lines(wiring, until_harness=True), EGW_WIRING_DRAIN="quiet",
                        EGW_WIRING_HARNESS_DIES="before-drain")
    assert _t6_value(result) == "stop", report(result)
    assert not Path(f"{wiring.hooks.bench.log}.drain-probed").exists()
    assert not wiring.hooks.recorder_running(T6_RID), "the unit was left running after the harness failed"
    keep = wiring.sut(T6_RID) / "events-partial"
    assert (keep / "events.partial.jsonl").stat().st_size > 0, report(result)
    assert not list(wiring.hooks.bench.home.rglob("docker-events.log"))


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM], ids=["INT", "TERM"])
def test_test_6_interrupted_during_its_drain_stops_the_unit_and_keeps_a_partial_capture_that_holds_the_drain(wiring,
                                                                                                              sig):
    wiring.old_logs()
    probed = Path(f"{wiring.hooks.bench.log}.drain-probed")
    try:
        out, err = _interrupt_once(wiring, _t6_lines(wiring, until_harness=True), probed.exists, sig,
                                   EGW_WIRING_DRAIN="hang")
        # The harness runs its hooks in a session of their own: the step's signal does not reach the drain hook,
        # which is still waiting when the step has ended (the runbook says so).
        try:
            os.kill(int(probed.read_text(encoding="utf-8")), 0)
            hook_alive = True
        except ProcessLookupError:
            hook_alive = False
    finally:
        if probed.exists():
            try:
                os.killpg(int(probed.read_text(encoding="utf-8")), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, ValueError):
                pass
    assert hook_alive, "the drain hook was ended by the step's signal"
    assert "T6=ok" not in out.splitlines(), out + err
    assert f"harness_cmd {T6_RID}: interrupted" in err, out + err
    assert not wiring.hooks.recorder_running(T6_RID), "the unit was left running after the interruption"
    partial = events_of(wiring.sut(T6_RID) / "events-partial" / "events.partial.jsonl")
    assert len(_drain_probe(partial)) == 1, "the partial capture does not hold the drain it was interrupted in"
    assert not list(wiring.hooks.bench.home.rglob("docker-events.log"))


def test_test_6_interrupted_after_its_docker_events_fetch_keeps_the_capture_in_the_run_directory_as_fetched(wiring):
    """Review of PR #51, B1, second round (the text, not the behaviour, was wrong): interrupted once the harness's
    docker-events fetch has run - while it judges or seals - the fetch has already stopped the recorder and written the
    capture in the run directory's logs/sut (complete here, as it was fetched), so the ending keeps no events-partial/
    and the run directory is left unsealed; T6 is not ok. Before that fetch, the capture goes to events-partial/ (the
    two cases above)."""
    wiring.old_logs()
    done = Path(f"{wiring.hooks.bench.log}.fetches-done")
    out, err = _interrupt_once(wiring, _t6_lines(wiring, until_harness=True), done.exists, signal.SIGINT,
                               EGW_WIRING_DRAIN="quiet", EGW_WIRING_HOLD_AFTER_FETCHES_S="60")
    assert "T6=ok" not in out.splitlines(), out + err
    assert f"harness_cmd {T6_RID}: interrupted" in err, out + err
    sut = wiring.raw(T6_RID) / "logs" / "sut"
    assert coverage(sut / "docker-events.coverage.txt")["coverage"] == ["complete"], out + err
    assert len(_drain_probe(events_of(sut / "docker-events.log"))) == 1, "the capture does not hold the drain"
    assert not (wiring.raw(T6_RID) / "SHA256SUMS").exists() and not (wiring.raw(T6_RID) / "manifest.json").exists()
    assert not (wiring.sut(T6_RID) / "events-partial").exists(), "the capture the fetch kept was kept twice"
    assert not wiring.hooks.recorder_running(T6_RID)


# --------------------------------------------------------------------------
# Collection and cleanup failures reach the callers (review of PR #51, B2)
# --------------------------------------------------------------------------


def test_harness_cmd_whose_cleanup_fails_after_a_valid_run_answers_3_and_names_the_harness_status(wiring):
    """The harness answered 0 and its capture is complete, but the cleanup after it cannot show the unit stopped:
    harness_cmd answers 3 (never a status of the harness), its STOP names both, and the sealed capture stays as it
    is."""
    rid = "smoke_sequence-r14"
    wiring.old_logs()
    result = wiring.run(f'harness_run {rid}; echo "RC=$?"', EGW_STUB_SSH_REFUSE="unit_state_before_cleanup")
    assert "RC=3" in result.stdout, report(result)
    stop = next(ln for ln in result.stderr.splitlines() if ln.startswith(f"STOP: harness_cmd {rid}: "))
    assert "the harness answered 0" in stop and "cleanup" in stop and "FAILED" in stop, stop
    assert f"egw-events-{rid} may still run" in stop and "INCOMPLETE" in stop, stop
    assert f"STOP: harness_run {rid}: the procedure is INCOMPLETE" in result.stderr, report(result)
    assert f"STOP: harness_run {rid}: egw_experiments run exited non-zero" not in result.stderr
    sut = wiring.raw(rid) / "logs" / "sut"
    manifest = json.loads((wiring.raw(rid) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["validity"] == "valid", manifest
    assert coverage(sut / "docker-events.coverage.txt")["coverage"] == ["complete"]
    assert (sut / "docker-events.log").stat().st_size > 0


def test_test_6_a_valid_harness_run_whose_cleanup_fails_is_never_ok_and_is_kept_as_evidence(wiring):
    """The old line tolerated any non-zero harness status whose reasons named only the restart evidence: a cleanup
    failure hidden behind the harness's status set T6 ok. Now T6 is ok only when harness_cmd answered 0."""
    wiring.old_logs()
    result = wiring.run(_t6_lines(wiring, until_harness=True), EGW_WIRING_DRAIN="quiet",
                        EGW_STUB_SSH_REFUSE="unit_state_before_cleanup")
    assert _t6_value(result) == "incomplete", report(result)
    assert f"STOP: harness_cmd {T6_RID}: the harness answered 0" in result.stderr, report(result)
    stop = next(ln for ln in result.stderr.splitlines() if ln.startswith("STOP: test 6: "))
    assert "INCOMPLETE" in stop and "kept" in stop, stop
    run_dir = wiring.raw(T6_RID)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["validity"] == "valid" and (run_dir / "SHA256SUMS").is_file()
    assert coverage(run_dir / "logs" / "sut" / "docker-events.coverage.txt")["coverage"] == ["complete"]


# --------------------------------------------------------------------------
# Tests 3, 5 and 9(b)/(c): the logs bounded to the test and to the sub-check
# --------------------------------------------------------------------------


def test_test_5_greps_its_client_in_its_own_bounded_broker_log_and_never_in_an_earlier_session(wiring):
    rid = "itest-dropout-01"
    old = wiring.old_logs(broker=(f"New client connected from 172.18.0.9:40000 as egw-simulator-{rid}",
                                  f"Client egw-simulator-{rid} closed its connection."))
    cmds = _host_commands("### Test 5")
    run_test = ('run_test() { glog broker "New client connected from 172.18.0.7:52130 as egw-simulator-$1"; '
                'glog broker "New client connected from 172.18.0.9:1883 as egw-controller"; '
                'glog broker "Client egw-simulator-$1 closed its connection."; return 0; }')
    body = "\n".join((run_test, _one(cmds, "R=itest-dropout-01"),
                      _one(cmds, 'if [ "$RT" != 0 ]; then stop "test 5: broker log'), 'echo "RC5=$?"'))
    result = wiring.run(body)
    assert "RC5=0" in result.stdout, report(result)
    excerpt = (wiring.p / f"{rid}.broker.txt").read_text(encoding="utf-8").splitlines()
    assert len(excerpt) == 2 and not set(old["broker"]) & set(excerpt), excerpt
    assert excerpt[0].endswith(f"as egw-simulator-{rid}") and excerpt[1].endswith("closed its connection.")
    fetch = (wiring.sut(rid) / "broker.fetch.txt").read_text(encoding="utf-8")
    assert int(re.search(r"excluded_before_since_lines=(\d+) ", fetch).group(1)) >= len(old["broker"])


def test_test_3_counts_only_the_rejections_of_its_own_bounded_controller_log(wiring):
    rid = "itest-invalid-01"
    rejected = lambda error: json.dumps({"level": "INFO", "logger": "egw_controller.service",  # noqa: E731
                                         "message": "telemetry event processed",
                                         "context": {"outcome": "rejected", "error": error}})
    wiring.old_logs(controller=(rejected("an earlier session's rejection"),))
    cmds = _host_commands("### Test 3")
    run_test = f"run_test() {{ glog controller '{rejected('schema: this test')}'; return 0; }}"
    body = "\n".join((run_test, _one(cmds, "R=itest-invalid-01"), _one(cmds, '[ "$RT" = 0 ] && sut_log controller'),
                      'echo "RC3=$?"'))
    result = wiring.run(body)
    assert "RC3=0" in result.stdout, report(result)
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("controller log of this test"))
    assert "lines=1 rejected=1 " in line and "schema: this test" in line, line
    assert "earlier session" not in (wiring.sut(rid) / "controller.log").read_text(encoding="utf-8")


def test_test_9_b_and_c_each_read_the_broker_log_bounded_from_their_own_guest_epoch(wiring):
    old = wiring.old_logs(broker=("Client egw-simulator-itest-auth-wrongpw disconnected, not authorised.",))
    body = "\n".join((*t9_lines("b"), 'echo "RCB=$?"',
                      # (b) lasts ~15 s on the guest (its CONNACK timeout) before its read; the stub simulator ends at
                      # once, so the gap is modelled: more than the 3 s (c)'s window opens before its epoch, in
                      # whole seconds of the guest clock
                      "sleep 4",
                      *t9_lines("c"), 'echo "RCC=$?"'))
    result = wiring.run(body)
    assert "RCB=0" in result.stdout and "RCC=0" in result.stdout, report(result)
    assert re.findall(r"^exit=.*$", result.stdout, re.M) == ["exit=1", "exit=1"], report(result)
    b = (wiring.sut("itest-auth-wrongpw") / "broker.log").read_text(encoding="utf-8").splitlines()
    c = (wiring.sut("itest-notls") / "broker.log").read_text(encoding="utf-8").splitlines()
    assert len(b) == 1 and "egw-simulator-itest-auth-wrongpw disconnected, not authorised" in b[0]
    assert not set(old["broker"]) & set(b), "an earlier session's refusal is never (b)'s evidence"
    assert len(c) == 1 and "egw-simulator-itest-notls" in c[0], c


def test_test_9_b_keeps_its_refusal_when_the_guest_clock_steps_back_right_after_its_epoch(wiring):
    """The guest's wall clock steps back by up to 3 s (proof_fetch_sut_log.sh CLOCK_STEP_BAND_S): stepped back between
    (b)'s epoch and the broker's refusal a moment later, the refusal is stamped before that epoch, and the daemon's
    '--since' (applied until the first line at or after it) would leave it out of (b)'s read."""
    old = wiring.old_logs(broker=("Client egw-simulator-itest-auth-wrongpw disconnected, not authorised.",))
    cmds = _host_commands("### Test 9")
    line, _ = t9_lines("b")
    # the runbook's own epoch read and simulator command, run apart so that the clock can be stepped between them
    epoch = re.search(r"T0_9B=\$\(guest_epoch 3\)", line).group(0)
    simulator = re.search(r'python -m egw_simulator run [^;]*; echo "exit=\$\?"', line).group(0)
    taken = wiring.run(epoch + '; echo "T0=$T0_9B"')
    t0 = re.search(r"^T0=(\d+)$", taken.stdout, re.M)
    assert t0, report(taken)
    stepped = wiring.run(f"T0_9B={t0.group(1)}; {simulator}", EGW_STUB_DATE_OFFSET_S="-3")
    assert "exit=1" in stepped.stdout, report(stepped)
    # (b)'s read follows its ~15 s CONNACK timeout: the stepped clock is past the epoch again by then
    wiring.hooks.wait_for(lambda: wiring.hooks.now() - 3 > int(t0.group(1)) + 3, limit_s=20)
    read = wiring.run(f"T0_9B={t0.group(1)}\n" + _one(cmds, "sut_log broker itest-auth-wrongpw ") + '\necho "RC9=$?"',
                      EGW_STUB_DATE_OFFSET_S="-3")
    assert "RC9=0" in read.stdout, report(read)
    b = (wiring.sut("itest-auth-wrongpw") / "broker.log").read_text(encoding="utf-8").splitlines()
    assert len(b) == 1 and "egw-simulator-itest-auth-wrongpw disconnected, not authorised" in b[0], b
    assert not set(old["broker"]) & set(b), "an earlier session's refusal is never (b)'s evidence"


@pytest.mark.parametrize("sub, rid", [("b", "itest-auth-wrongpw"), ("c", "itest-notls")])
def test_test_9_b_and_c_make_no_connection_attempt_when_the_guest_clock_was_not_read(wiring, sub, rid):
    """Review of PR #51, P2: the guest does not answer 'date +%s', so (b)'s or (c)'s lower bound is not read: no
    connection attempt reaches the broker (its log is unchanged), no 'exit=' is printed - it would be the refusal
    status (b) and (c) expect - and the STOP names the sub-check."""
    run, read = t9_lines(sub)
    result = wiring.run(run + '\necho "RUN=$?"\n' + read + '\necho "READ=$?"', EGW_STUB_SSH_REFUSE="date +%s")
    assert "RUN=1" in result.stdout and "READ=1" in result.stdout, report(result)
    assert not re.search(r"^exit=", result.stdout, re.M), report(result)
    broker = Path(f"{wiring.hooks.bench.log}.broker-log")
    assert not broker.exists() or f"egw-simulator-{rid}" not in broker.read_text(encoding="utf-8"), report(result)
    assert f"STOP: test 9({sub}): the lower bound of ({sub})'s evidence was NOT read - the probe was NOT run" \
        in result.stderr, report(result)
    assert not (wiring.sut(rid) / "broker.log").exists(), report(result)


# --------------------------------------------------------------------------
# Test 7: the dependency faults, each judged on its own container
# --------------------------------------------------------------------------


def _dc_line() -> str:
    return _one(_host_commands("### Test 7"), "DC=")


@pytest.mark.parametrize("svc", ["mongodb", "ditto-things"])
def test_test_7_a_dependency_fault_is_captured_and_judged_on_that_dependencys_container(wiring, svc):
    rid = f"itest-{svc}-fault-01"
    body = "\n".join((_dc_line(), f"R={rid}; SVC={svc}", 'T0_7=$(events_start $R) || exit 9',
                      'ssh egw-tcg "$DC stop $SVC"', 'ssh egw-tcg "$DC start $SVC"',
                      'events_stop $R "$T0_7" die,stop,start egw-$SVC-1; echo "EV=$?"'))
    result = wiring.run(body)
    assert "EV=0" in result.stdout, report(result)
    d = wiring.sut(rid)
    cov = coverage(d / "docker-events.coverage.txt")
    assert cov["coverage"] == ["complete"] and cov["container"] == [f"egw-{svc}-1"], cov
    assert cov["expected"] == ["die,stop,start"] and cov["rule_R7"][0].startswith("held: ")
    assert [f.split("@")[0] for f in cov["expected_found"][0].split(",")] == ["die", "stop", "start"]
    kills = [e for e in events_of(d / "docker-events.log") if e["Action"] == "kill"]
    assert kills and all(e["Actor"]["Attributes"]["name"] == f"egw-{svc}-1" for e in kills)
    assert all(e["Actor"]["Attributes"]["signal"] == "15" for e in kills)
    assert (d / "docker-events.fetch.txt").is_file() and not wiring.hooks.recorder_running(rid)


def test_test_7_a_complete_capture_whose_cleanup_fails_stays_complete_and_events_stop_answers_3(wiring):
    """Review of PR #51, B2: the fetch shows the capture complete, then the cleanup cannot show the unit stopped.
    events_stop answered 0 (the fetch's status); it now answers 3 - the capture stays complete as it was fetched, the
    procedure is incomplete and the unit may still run - and the repeated cleanup changes nothing in the capture."""
    rid = "itest-mongodb-fault-06"
    body = "\n".join((_dc_line(), f"R={rid}; SVC=mongodb", 'T0_7=$(events_start $R) || exit 9',
                      'ssh egw-tcg "$DC stop $SVC"', 'ssh egw-tcg "$DC start $SVC"',
                      'events_stop $R "$T0_7" die,stop,start egw-$SVC-1; echo "EV=$?"'))
    result = wiring.run(body, EGW_STUB_SSH_REFUSE="unit_state_before_cleanup")
    assert "EV=3" in result.stdout, report(result)
    d = wiring.sut(rid)
    assert coverage(d / "docker-events.coverage.txt")["coverage"] == ["complete"]
    kept = (d / "docker-events.log").read_bytes()
    assert kept, "the complete capture was not kept"
    stop = next(ln for ln in result.stderr.splitlines() if ln.startswith(f"STOP: events_stop {rid}: "))
    assert "IS shown complete" in stop and "INCOMPLETE" in stop and f"egw-events-{rid} may still run" in stop, stop
    assert "NOT shown complete" not in result.stderr, report(result)
    again = wiring.hooks.run_argv(["bash", str(SESSION / "events_capture.sh"), "cleanup", rid])
    assert again.returncode == 0 and not wiring.hooks.recorder_running(rid), report(again)
    assert (d / "docker-events.log").read_bytes() == kept
    assert coverage(d / "docker-events.coverage.txt")["coverage"] == ["complete"]
    assert not (d / "events-partial").exists()


def test_test_7_events_stop_pasted_again_after_a_complete_capture_answers_3_then_0_and_never_1(wiring):
    """Review of PR #51, B2, second round: the complete capture's cleanup fails (3); pasted again while the guest is
    still not reached, events_stop answered 1 - 'the capture not shown complete' - and, once it is reached, 1 again,
    whatever the cleanup showed. It now answers 3 and then 0: the capture fetched before stays complete as it was
    fetched, nothing is fetched again, and only the procedure's close changes."""
    rid = "itest-mongodb-fault-07"
    body = "\n".join((_dc_line(), f"R={rid}; SVC=mongodb", 'T0_7=$(events_start $R) || exit 9',
                      'ssh egw-tcg "$DC stop $SVC"', 'ssh egw-tcg "$DC start $SVC"',
                      'events_stop $R "$T0_7" die,stop,start egw-$SVC-1; echo "EV=$?"'))
    refuse = {"EGW_STUB_SSH_REFUSE": "unit_state_before_cleanup"}
    first = wiring.run(body, **refuse)
    assert "EV=3" in first.stdout, report(first)
    d, t0 = wiring.sut(rid), wiring.run_t0(rid)
    kept = {name: (d / name).read_bytes() for name in ("docker-events.log", "docker-events.fetch.txt",
                                                       "docker-events.coverage.txt")}
    paste = f'events_stop {rid} {t0} die,stop,start egw-mongodb-1; echo "EV2=$?"'
    still = wiring.run(paste, **refuse)
    assert "EV2=3" in still.stdout, report(still)
    stop = next(ln for ln in still.stderr.splitlines() if ln.startswith(f"STOP: events_stop {rid}: "))
    assert "nothing was fetched again" in stop and "IS shown complete" in stop and "INCOMPLETE" in stop, stop
    assert f"egw-events-{rid} may still run" in stop, stop
    closed = wiring.run(paste)
    assert "EV2=0" in closed.stdout, report(closed)
    assert f"STOP: events_stop {rid}" not in closed.stderr, report(closed)
    said = next(ln for ln in closed.stdout.splitlines() if ln.startswith(f"events_stop {rid}: "))
    assert "nothing was fetched again" in said and "IS shown complete" in said, said
    assert "showed the unit stopped" in said, said
    assert {name: (d / name).read_bytes() for name in kept} == kept, "the complete capture or its records changed"
    assert not (d / "events-partial").exists() and not wiring.hooks.recorder_running(rid)


def test_test_7_events_judged_on_another_container_or_with_the_proofs_kill_are_not_complete(wiring):
    """The container named is the one R7 judges (the controller, by default, holds none of the fault's events), and
    the proof's R7 is unchanged: a kill is required with signal 9, which a compose stop never sends."""
    starts = "\n".join(f'T0_{i}=$(events_start itest-mongodb-fault-0{i}) || exit 9' for i in (2, 3))
    body = "\n".join((_dc_line(), starts, 'ssh egw-tcg "$DC stop mongodb"', 'ssh egw-tcg "$DC start mongodb"',
                      'events_stop itest-mongodb-fault-02 "$T0_2" die,stop,start; echo "EV2=$?"',
                      'events_stop itest-mongodb-fault-03 "$T0_3" kill,die,stop,start egw-mongodb-1; echo "EV3=$?"'))
    result = wiring.run(body)
    assert "EV2=1" in result.stdout and "EV3=1" in result.stdout, report(result)
    two = coverage(wiring.sut("itest-mongodb-fault-02") / "docker-events.coverage.txt")
    assert two["rule_R7"][0].startswith("broken: the expected event(s) die, stop, start of egw-controller-1"), two
    three = coverage(wiring.sut("itest-mongodb-fault-03") / "docker-events.coverage.txt")
    assert three["rule_R7"][0].startswith("broken: the expected event(s) kill (signal 9) of egw-mongodb-1"), three
    for name in ("itest-mongodb-fault-02", "itest-mongodb-fault-03"):
        assert not (wiring.sut(name) / "docker-events.log").exists()
        assert (wiring.sut(name) / "docker-events.partial.jsonl").is_file()
        assert not wiring.hooks.recorder_running(name)
    assert "STOP: events_stop itest-mongodb-fault-02: the Docker events capture is NOT shown complete" in result.stderr


def test_test_7_events_stop_interrupted_in_its_fetch_and_pasted_again_stops_the_unit_and_keeps_its_capture(wiring):
    """Ctrl-C inside the fetch (here: the closing marker's exec never answers) ends the step before the guest's stop;
    pasting events_stop again, as test 7's prose says, fetches nothing a second time but stops the unit and keeps
    what it captured, never as the run's docker-events.log."""
    rid = "itest-mongodb-fault-04"
    start = wiring.run(f'events_start {rid}; echo "ES=$?"')
    assert "ES=0" in start.stdout, report(start)
    t0 = wiring.run_t0(rid)
    dockerlog = Path(str(wiring.hooks.bench.log) + ".proof-dockerlog")
    out, err = _interrupt_once(
        wiring, f'events_stop {rid} {t0} die,stop,start egw-mongodb-1; echo "EV=$?"',
        lambda: dockerlog.exists() and "exec egw-mosquitto-1" in dockerlog.read_text(encoding="utf-8"),
        signal.SIGINT, EGW_STUB_FAIL="exec-hangs")
    assert wiring.hooks.recorder_running(rid), "the case needs the unit left running by the interruption: " + out + err
    d = wiring.sut(rid)
    again = wiring.run(f'events_stop {rid} {t0} die,stop,start egw-mongodb-1; echo "EV2=$?"')
    assert "EV2=1" in again.stdout, report(again)
    assert f"STOP: events_stop {rid}: {d}/docker-events.fetch.txt exists" in again.stderr, report(again)
    assert not wiring.hooks.recorder_running(rid), "the pasted events_stop left the unit running"
    assert (d / "events-partial" / "events.partial.jsonl").stat().st_size > 0, report(again)
    assert not (d / "docker-events.log").exists()


def test_test_7_events_stop_whose_fetch_copied_nothing_leaves_the_capture_to_the_cleanup_and_the_paste_keeps_it(wiring):
    """The guest stops answering during the fetch: its stop ssh and its copies fail, and it still writes its (empty)
    stop record. The capture was not kept, so the cleanup - which cannot reach the guest either - and then the paste
    of events_stop that test 7's prose prescribes, once the guest answers, keep it in events-partial/ (review of part
    B, item 1: the stop record alone was read as the capture kept, and the capture was left to the guest's tmpfs)."""
    rid = "itest-mongodb-fault-05"
    start = wiring.run(f'events_start {rid}; echo "ES=$?"')
    assert "ES=0" in start.stdout, report(start)
    t0 = wiring.run_t0(rid)
    first = wiring.run(f'events_stop {rid} {t0} die,stop,start egw-mongodb-1; echo "EV1=$?"',
                       EGW_STUB_SSH_REFUSE="stop_requested_guest_epoch", EGW_STUB_SCP_FAIL="egw-events-")
    assert "EV1=1" in first.stdout, report(first)
    d = wiring.sut(rid)
    assert (d / "docker-events.stop.txt").is_file()
    assert not (d / "docker-events.log").exists() and not (d / "docker-events.partial.jsonl").exists()
    assert wiring.hooks.recorder_running(rid), "the case needs a cleanup that could not reach the guest"
    assert not (d / "events-partial").exists(), report(first)
    again = wiring.run(f'events_stop {rid} {t0} die,stop,start egw-mongodb-1; echo "EV2=$?"')
    assert "EV2=1" in again.stdout and f"{d}/docker-events.fetch.txt exists" in again.stderr, report(again)
    assert not wiring.hooks.recorder_running(rid), "the pasted events_stop left the unit running"
    assert (d / "events-partial" / "events.partial.jsonl").is_file(), report(again)
    assert (d / "events-partial" / "events.partial.jsonl").stat().st_size > 0
    assert not (d / "docker-events.log").exists()


# --------------------------------------------------------------------------
# What the runbook and the fetch hook say about the capture
# --------------------------------------------------------------------------
RUNBOOK = REPO_ROOT / "docs" / "setup" / "qemu_integrated_gateway.md"


def _comment_text(lines: list[str]) -> str:
    return " ".join(ln.strip().lstrip("#").strip() for ln in lines)


def test_test_9_does_not_state_as_fact_that_the_refusal_names_its_client_id():
    """Whether Mosquitto 2.0.22's 'not authorised' line carries the client id or <unknown> is UNVERIFIED (test 9(e));
    the comment of (b) and (c) says so, and how such a line in (c)'s window is read (review of part B, item 4)."""
    lines = RUNBOOK.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("# (b) and (c): the broker log is the actual evidence"))
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("# (b) wrong password"))
    comment = _comment_text(lines[start:end])
    assert "(b)'s evidence is a refusal naming its client id" not in comment, comment
    assert "UNVERIFIED:" in comment and "<unknown>" in comment, comment


def test_test_6_says_where_an_interruption_leaves_the_capture_before_and_after_the_harnesss_events_fetch():
    """Review of PR #51, B1, second round: the paragraph said that an interruption 'at any point' of the harness
    leaves the capture in events-partial/ and never as a docker-events.log; after the harness's docker-events fetch
    the capture is already in the run directory as that fetch left it (the case above), and an interruption during
    that fetch leaves the fetch running in its own session."""
    paragraph = next(p for p in RUNBOOK.read_text(encoding="utf-8").split("\n\n")
                     if p.startswith("**The run's own capture"))
    assert "at any point of it" not in paragraph, paragraph
    assert "before the harness's docker-events fetch" in paragraph, paragraph
    assert "after that fetch" in paragraph and "unsealed" in paragraph, paragraph
    assert "during that fetch" in paragraph, paragraph


def test_an_older_clone_without_the_capture_scripts_never_starts_the_harness_and_the_docs_say_so(wiring):
    """EGW_CLONE naming a checkout without tools/session/events_capture.sh (as the helper file's default, the older
    Yocto clone): harness_cmd answers 2 and the harness is not started. The EGW_CLONE paragraph says that, and the
    fetch hook's header names who starts the recorder and supplies RUN_T0 (review of part B, item 5)."""
    rid = "smoke_sequence-r13"
    older = wiring.hooks.bench.tmp / "older-clone"
    (older / "src").mkdir(parents=True)
    result = wiring.run(f'harness_run {rid}; echo "RC=$?"', EGW_CLONE=str(older))
    assert "RC=0" not in result.stdout, report(result)
    assert f"STOP: harness_cmd {rid}: the harness was NOT started" in result.stderr, report(result)
    assert not Path(f"{wiring.hooks.bench.log}.harness-started").exists() and not wiring.raw(rid).exists()
    assert wiring.hooks.ssh_commands() == []
    paragraph = next(p for p in RUNBOOK.read_text(encoding="utf-8").split("\n\n")
                     if p.startswith("**`EGW_CLONE` must name the checkout"))
    assert "every `harness_run` ends invalid" not in paragraph, paragraph
    assert "the harness is not started" in paragraph, paragraph
    header = _comment_text((SESSION / "proof_fetch_sut_log.sh").read_text(encoding="utf-8").splitlines()[1:43])
    assert "that proof.sh started" not in header and "the instant proof.sh recorded" not in header, header
    assert "events_capture.sh" in header and "events_start" in header, header


def test_a_copy_that_brought_back_some_files_keeps_them_apart_as_incomplete_and_the_repeat_keeps_the_capture(wiring):
    """A cleanup whose copy failed for one file keeps the files that did arrive, in a directory named as incomplete
    and named in its STOP, never as events-partial/; the repeat then keeps the whole capture (second review of part B:
    the staging directory was deleted on failure, so a partial capture that reached the host was thrown away)."""
    rid = "smoke_sequence-r31"
    start = wiring.run(f'events_start {rid}; echo "ES=$?"')
    assert "ES=0" in start.stdout, report(start)
    keep = wiring.sut(rid) / "events-partial"
    records = wiring.hooks.bench.tmp / "no-stop-record-31"
    first = wiring.run(f'events_cleanup {rid} {records}; echo "EC1=$?"', EGW_STUB_SCP_FAIL_DEST="cli-stderr.txt")
    assert "EC1=1" in first.stdout, report(first)
    assert not wiring.hooks.recorder_running(rid), report(first)
    assert not keep.exists(), report(first)
    stages = [p for p in wiring.sut(rid).iterdir() if p.name.startswith("events-partial.copy.")]
    assert len(stages) == 1, sorted(p.name for p in wiring.sut(rid).iterdir())
    assert sorted(p.name for p in stages[0].iterdir()) == ["events.partial.jsonl", "lifecycle.txt", "start-facts.txt"]
    assert (stages[0] / "events.partial.jsonl").stat().st_size > 0
    stop = next(ln for ln in first.stderr.splitlines() if ln.startswith("STOP: events_capture: 3 of the recorder"))
    assert "INCOMPLETE" in stop and str(stages[0]) in stop, stop
    second = wiring.run(f'events_cleanup {rid} {records}; echo "EC2=$?"')
    assert "EC2=0" in second.stdout, report(second)
    assert sorted(p.name for p in keep.iterdir()) == ["cli-stderr.txt", "events.partial.jsonl", "lifecycle.txt",
                                                      "start-facts.txt"]
    assert stages[0].is_dir(), "the incomplete copy of the first attempt is kept as its record"
