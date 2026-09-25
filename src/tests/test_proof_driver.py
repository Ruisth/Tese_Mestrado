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
  sealed run directory shaped by ``test_proof_evaluator``'s own builders
  (the scenario that supports, one that refutes, one that is inconclusive,
  a manifest invalid under MAX_SAMPLE_GAP_S), so the REAL evaluator runs
  over it; every other call goes to this interpreter unchanged;
* a guest ``docker`` that holds the controller container's state on disk
  (the same object, started later, after the fault) and the five other
  services, steerable through ``EGW_STUB_FAIL``;
* the section 6.1 helper stub extended with the runbook's own ``keep`` and
  stubs of ``_mline`` (thirteen fields, ``started_at`` moving with the
  fault), ``metrics`` and ``config_identity``;
* a "runbook" whose 6.1 heredoc is that helper stub, named to the driver
  with ``EGW_PROOF_RUNBOOK``, so the helpers check passes on the bench and
  fails against the real runbook.

What these cases show is the driver's own behaviour: the prerequisites that
leave the harness unstarted, the values and stop rules recorded before the
first ``drained``, the harness command line, the restart shown from the
driver's records, the three verdicts kept apart (the harness's own validity
quoted and never decisive), the 50-minute rule, the restoration in every
ending, the optional extension never run unless asked, and what reaches the
package. They say nothing about a real broker, controller, guest or network.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
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

from test_session_drivers import EXPECT_SERVICES, ITEST_HELPERS, Bench, _write, report  # noqa: E402
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
FAST = {
    "EGW_PROOF_MASTER_SEED": MASTER_SEED,
    "EGW_HEALTH_LIMIT_S": "3", "EGW_HEALTH_STEP_S": "1", "EGW_READY_LIMIT_S": "5",
    "EGW_PROOF_ATTEMPT_LIMIT_S": "600",
}

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
builders, so the real evaluator evaluates it."""
import json
import os
import shutil
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

# The fault, as the restart hook applies it on the guest: the same container
# object, started later (a kill + start); the docker stub reads this state.
state_path = LOG + ".proof-docker.json"
try:
    with open(state_path, encoding="utf-8") as fh:
        state = json.load(fh)
except (OSError, ValueError):
    state = {"controller": {"id": "0f" * 32, "started": "2026-09-25T10:00:00.100000000Z",
                            "status": "running", "starts": 0}}
controller = state["controller"]
if not fails("restart-not-shown"):
    controller["starts"] += 1
    controller["started"] = "2026-09-25T10:05:%02d.200000000Z" % controller["starts"]
    controller["status"] = "running"
if fails("controller-replaced"):
    controller["id"] = "1e" * 32
with open(state_path, "w", encoding="utf-8") as fh:
    json.dump(state, fh)
open(LOG + ".midrun", "w", encoding="utf-8").close()

from egw_experiments.checksums import write_sha256sums  # noqa: E402
from test_proof_evaluator import D1, LINES, NS, _manifest, _rows, _write_run_dir  # noqa: E402

result = os.environ.get("EGW_STUB_PROOF_RESULT", "supports")
kwargs = {}
if result == "refutes":
    kwargs["lines"] = LINES + [("a-mid", D1, 0, "accepted", 1_300 * NS, None)]
elif result == "inconclusive":
    kwargs["rows"] = _rows(last_pre=(0, 0))
validity = os.environ.get("EGW_STUB_MANIFEST_VALIDITY", "valid")
if validity != "valid":
    kwargs["manifest"] = _manifest(validity="invalid", validity_reasons=[
        "resources.csv: egw-controller-1 has a 6.0 s gap (00:18:29Z to 00:18:35Z) exceeding MAX_SAMPLE_GAP_S (5 s)"])
with tempfile.TemporaryDirectory() as tmp:
    run_dir = _write_run_dir(Path(tmp), name=run_id, seal=False, **kwargs)
    # What the real harness seals beside the proof's evidence: the collector's
    # files and the item-18 hooks' streams.
    (run_dir / "resources.csv").write_text(
        "ts_utc,service,cpu_usage_usec,memory_current_bytes\n2026-09-25T10:00:00Z,egw-controller-1,1000,1048576\n", "utf-8")
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
    if not fails("harness-unsealed"):
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
print(f"[harness] {run_id}: run directory sealed at {dest}; validity {validity}")
sys.exit(0 if validity == "valid" else 1)
'''

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
BOOT = "2026-09-25T09:58:00.100000000Z"


def fails(token):
    return f",{token}," in failures


def load():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"controller": {"id": "0f" * 32, "started": "2026-09-25T10:00:00.100000000Z",
                               "status": "running", "starts": 0}}


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
with open(LOG + ".proof-dockerlog", "a", encoding="utf-8") as fh:
    fh.write(("compose " if compose else "") + " ".join(args) + "\n")
cmd = args[0] if args else ""
ctl = state["controller"]


def container_id(name):
    if name == SERVICES[5]:
        return ctl["id"]
    return f"{SERVICES.index(name):02d}" + "a" * 62


def started_at(name):
    if name == SERVICES[5]:
        return ctl["started"]
    if fails("other-restarted") and name == SERVICES[4] and midrun():
        return "2026-09-25T10:06:00.300000000Z"
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
    return "healthy"


def oomkilled(name):
    return "true" if (fails("service-oomkilled") and name == SERVICES[1] and midrun()) else "false"


if compose and cmd == "start":
    if fails("start-fails"):
        print("Error response from daemon: stub start refused", file=sys.stderr)
        sys.exit(1)
    ctl["starts"] += 1
    ctl["started"] = "2026-09-25T10:05:%02d.200000000Z" % ctl["starts"]
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
'''

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
    stub_fails mline && { stop "_mline: GET $CTRL/metrics failed or was not valid JSON"; return 1; }
    echo "0 0 0 true $(_proof_started_at) 1 ${EGW_STUB_MLINE_RECEIVED:-0} 0 0 0 0 0 0"
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
        self.runbook = bench.tmp / "stub-runbook.md"
        _write(self.runbook, "# stub runbook for the proof driver\n\n```bash\n"
                             "host$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'\n" + self.helpers_text + "EOF\n```\n")
        self.harness_py = _write(bench.tmp / "harness_stub.py", HARNESS_STUB)
        _write(bench.bin / "python", PYTHON_STUB, executable=True)
        _write(bench.guest_bin / "docker", DOCKER_STUB, executable=True)
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
        return subprocess.Popen(["bash", str(self.bench.drivers / "proof.sh"), RID, COMMIT],
                                env=self.bench.env(**overrides), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)

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
        "EGW_HEALTH_LIMIT_S": 3, "EGW_HEALTH_STEP_S": 1, "EGW_READY_LIMIT_S": 5,
        "EGW_PROOF_ATTEMPT_LIMIT_S": 600, "EGW_PROOF_RESTART_AT_S": 150, "EGW_PROOF_DURATION_S": 300,
        "EGW_PROOF_RATE": 11.2, "EGW_PROOF_MASTER_SEED": 42, "EGW_PROOF_EXTENSION": "no",
        "EGW_PROOF_EXTENSION_LIMIT_S": 1790, "EGW_PROOF_BASE": str(pbench.base), "EGW_PROOF_PLAN": str(pbench.plan),
        "expected_source_commit": COMMIT,
    }
    assert verdicts["workload"]["engineering_diagnostic_not_a_g3_run"] is True
    # In the session facts, written as a step of its own BEFORE 'pre' (the
    # first 'drained'), with the two stop rules not reached and the clocks.
    facts = pbench.session_facts()
    assert facts["values"]["DRAIN_QUIET_S"] == 490 and facts["values"]["EGW_PROOF_ATTEMPT_LIMIT_S"] == 600
    assert [(r["id"], r["limit_s"], r["reached"]) for r in facts["stop_rules"]] == [("healthy", 3, False), ("attempt", 600, False)]
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
    assert "stop rule reached: the stack with the candidate was not running and healthy within 3 s" in verdicts["reason"]
    assert "the harness was NOT started" in verdicts["reason"]
    assert "stack=not-healthy" in verdicts["reason"]
    facts = pbench.session_facts()
    healthy = next(r for r in facts["stop_rules"] if r["id"] == "healthy")
    assert healthy["reached"] is True and healthy["reached_at"]
    assert [r["id"] for r in pe.stop_rules_of(facts)["reached"]] == ["healthy"]
    assert "pre" not in pbench.commands() and pbench.harness() is None


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
    assert _argv_value(argv, "--restart-cmd") == f"bash {drivers}/proof_restart_controller.sh {{run_id}}"
    assert _argv_value(argv, "--restart-at-s") == "150"
    assert _argv_value(argv, "--config-identity-from") == str(pbench.prefix / f"{RID}.config_identity.json")
    assert _argv_value(argv, "--twin-snapshot-cmd") == f"bash {drivers}/proof_hook_twins.sh {{run_id}} {{dest}} {seed}"
    assert _argv_value(argv, "--drain-cmd") == f"bash {drivers}/proof_hook_drained.sh {{run_id}}"
    assert _argv_value(argv, "--post-drain-fetch-cmd") == "scp -q egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl {dest}"
    for kind, flag in (("broker", "--fetch-broker-log-cmd"), ("controller", "--fetch-controller-log-cmd"),
                       ("docker-events", "--fetch-docker-events-cmd")):
        assert _argv_value(argv, flag) == f"bash {drivers}/proof_fetch_sut_log.sh {kind} {{dest}} {guest_epoch}"
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
    assert "timeout -k 30" in json.dumps(record["argv"])


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
    assert "manifest validity valid kept as recorded, not decisive for the proof" in verdicts["reason"]
    assert verdicts["reason"].endswith("; the guest was left with stack=healthy restart_shown=yes")
    assert "stands for this run only" in verdicts["next_action"]
    assert "PROOF proof-adr0011-r01: validity=valid outcome=pass evaluator=supports (exit 0)" in result.stdout
    assert pbench.package() is not None
    steps = pbench.commands()
    for step in ("helpers-check", "session-facts", "services-healthy", "guest-state-before", "containers-before",
                 "controller-process-before", "proof-plan", "pre", "identity-check", "harness-run",
                 "controller-process-after", "containers-after", "restart-shown", "metrics-after", "delta",
                 "evaluate", "guest-state-after", "guest-state-delta", "services-healthy-after"):
        assert step in steps, step
    assert steps.index("services-healthy-after") > steps.index("evaluate")
    assert steps.index("session-facts") < steps.index("pre") < steps.index("harness-run")
    document = pbench.verdict_document()
    assert document["instrumentation"]["proof_evidence"]["complete"] is True
    assert document["system_outcome"]["result"] == "supports"
    # At evaluation time the restoration has not been observed yet: the
    # evaluator echoes what the driver knew then, and decides nothing on it.
    assert document["restoration"]["state"] == "stack=unknown restart_shown=yes"
    facts = pbench.session_facts()
    assert facts["restoration"] == "stack=healthy restart_shown=yes" and facts["restart_shown"] is True
    assert facts["instants"]["harness_exit"] == 0 and facts["verdicts"]["system_outcome"] == "pass"
    # The same run with a stack that does not come back healthy is never a
    # pass: the restoration outcome is kept apart and downgrades it.
    shutil.rmtree(pbench.attempt())
    shutil.rmtree(pbench.base)
    pbench.plan.unlink()
    for path in pbench.prefix.glob(f"{RID}.*"):
        path.unlink()
    os.remove(str(pbench.bench.log) + ".proof-docker.json")
    os.remove(str(pbench.bench.log) + ".midrun")
    result = pbench.run(EGW_STUB_FAIL="healthy-again-fails")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "inconclusive")
    assert verdicts["proof_verdict"] == "supports"
    assert verdicts["restoration"] == "stack=not-healthy restart_shown=yes"
    assert "the guest was NOT fully restored: the stack was not running and healthy again within 3 s" in verdicts["reason"]
    assert verdicts["reason"].endswith("; the guest was left with stack=not-healthy restart_shown=yes")
    assert "observed system fault" not in verdicts["reason"]


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
    # a mandatory record missing, never a result.
    ("harness-tampered", "not-computed", "the proof was not evaluated (evaluate exit 2)"),
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
    assert "the proof's evidence is not complete" in verdicts["reason"]
    assert "services-healthy-after" in pbench.commands()


def test_a_harness_that_refuses_is_mandatory_never_not_run(pbench):
    result = pbench.run(EGW_STUB_HARNESS_EXIT="2")
    assert result.returncode == 3, report(result)
    verdicts = pbench.verdicts()
    assert verdicts["system_outcome"] == "inconclusive" and verdicts["instrumentation_validity"] == "invalid"
    assert "the harness run exited 2" in verdicts["reason"]
    assert "services-healthy-after" in pbench.commands()
    assert verdicts["status"] == "failed"


def test_harness_validity_invalid_under_the_sample_gap_rule_is_quoted_and_does_not_invalidate_the_proof(pbench):
    result = pbench.run(EGW_STUB_MANIFEST_VALIDITY="invalid")
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert "manifest validity invalid (resources.csv: egw-controller-1 has a 6.0 s gap" in verdicts["reason"]
    assert "MAX_SAMPLE_GAP_S" in verdicts["reason"]
    assert "kept as recorded, not decisive for the proof (ADR 0011) (harness exit 1;" in verdicts["reason"]
    assert "evidence requirement(s) not met" not in verdicts["reason"]
    document = pbench.verdict_document()
    assert document["instrumentation"]["harness_validity"] == "invalid"
    assert document["instrumentation"]["proof_evidence"]["complete"] is True
    assert pbench.session_facts()["instants"]["harness_exit"] == 1


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
    assert "restart-shown" not in steps and "delta" not in steps
    assert "the restart-shown check, the /metrics reading after and the delta were not run: a stop rule was reached" in verdicts["reason"]
    assert verdicts["restoration"].startswith("stack=healthy")
    assert "harness-run" in steps
    # The run directory was never written by the hanging harness: the
    # evaluator could not run, which is mandatory, never a result.
    assert verdicts["instrumentation_validity"] == "invalid"
    assert verdicts["proof_verdict"] == "not-computed"


def test_interrupt_restores_and_names_the_stack_state_on_the_final_line(pbench):
    proc = pbench.start(EGW_STUB_HANG_S="4")
    pbench.wait_for(lambda: pbench.harness() is not None, 120)
    proc.send_signal(signal.SIGINT)
    out, err = proc.communicate(timeout=300)
    assert proc.returncode == 130, f"exit={proc.returncode}\n{out}\n{err}"
    verdicts = pbench.verdicts()
    assert verdicts["status"] == "interrupted" and verdicts["system_outcome"] == "interrupted"
    assert verdicts["restoration"] == "stack=healthy restart_shown=unknown"
    assert "the guest was left with stack=healthy restart_shown=unknown" in verdicts["reason"]
    assert "preserved as incomplete and is never replaced" in verdicts["next_action"]
    assert 'headline="interrupted; the guest was left with stack=healthy restart_shown=unknown"' in out
    assert "DRIVER RESULT" in out and "exit=130" in out
    steps = pbench.commands()
    assert "harness-run" in steps and "services-healthy-after" in steps
    assert "evaluate" not in steps
    facts = pbench.session_facts()
    assert facts["instants"]["interrupted_utc"] and facts["restoration"] == "stack=healthy restart_shown=unknown"
    assert pbench.package() is not None


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
    # drain and the second fetch run after the restoration, and the result
    # is recorded APART: the proof's three verdicts are what they were.
    result = pbench.run(EGW_PROOF_EXTENSION="yes")
    assert result.returncode == 0, report(result)
    verdicts = pbench.verdicts()
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert verdicts["proof_verdict"] == "supports"
    steps = pbench.commands()
    for step in ("ext-restart", "ext-ready", "ext-drained", "ext-fetch"):
        assert step in steps, step
    assert steps.index("ext-restart") > steps.index("services-healthy-after")
    assert steps.count("services-healthy-after") == 2
    log = pbench.docker_log()
    assert "kill --signal=KILL egw-controller-1" in log and "compose start controller" in log
    assert log.count("kill --signal=KILL") == 1
    facts = pbench.session_facts()
    assert facts["extension"]["chosen"] is True and facts["extension"]["limit_s"] == 1790
    assert facts["extension"]["result"] == "not-refuted"
    assert facts["extension"]["received_after_ready"] == 0 and facts["extension"]["new_outcome_lines"] == 0
    assert facts["extension"]["started_at_after"] == "2026-09-25T10:04:35Z"
    assert verdicts["extension"] == "not-refuted"
    assert "optional extension: not-refuted (recorded apart, it decides nothing of the proof)" in verdicts["reason"]
    assert (pbench.prefix / f"{RID}.extension.restart.txt").is_file()
    assert (pbench.attempt() / "analysis" / "events.post-extension.jsonl").is_file()
    assert verdicts["workload"]["values"]["EGW_PROOF_EXTENSION"] == "yes"
    assert verdicts["restoration"] == "stack=healthy restart_shown=yes"


def test_the_extension_refutes_when_the_new_process_received_a_delivery(pbench):
    result = pbench.run(EGW_PROOF_EXTENSION="yes", EGW_STUB_MLINE_RECEIVED="3")
    assert result.returncode == 0, report(result)
    facts = pbench.session_facts()
    assert facts["extension"]["result"] == "refutes"
    assert facts["extension"]["received_after_ready"] == 3
    assert "the new process received 3 delivery(ies) with nothing published" in facts["extension"]["reasons"]
    verdicts = pbench.verdicts()
    assert verdicts["extension"] == "refutes"
    assert (verdicts["instrumentation_validity"], verdicts["system_outcome"]) == ("valid", "pass")
    assert "optional extension: refutes (recorded apart, it decides nothing of the proof)" in verdicts["reason"]


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
                  "`EGW_PROOF_RUNBOOK`", "`EGW_PROOF_RESTART_AT_S`"):
        assert value in readme, value
    assert "not decisive" in readme and "P-8" in readme
