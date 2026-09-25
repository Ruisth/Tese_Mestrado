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
that holds the controller container's state on disk and answers the three
log reads and the events read, and a ``$REC`` whose ``snap`` records its
argv and is write-once like the real one.

What these cases show is the wrappers' own behaviour: the byte-stable lines
the harness classifies, the write-once files, the D2 rule ("the log was NOT
read on the guest ... neither observed nor excluded") applied to a failed
and to an empty read, with the guest's reason kept in the capsule, the
bounded events read, the SIGKILL-then-start sequence with both guest
readings in the record and both instants in the manifest's 500-character
``stderr_tail`` (the restart hook is run by ``_execute_restart_cmd`` itself,
under a guest whose fault-time stderr passes through, as compose's does),
and a helper file that cannot be loaded ending every hook before it touches
the guest. They say nothing about a real broker, controller, docker engine,
guest or network.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the session drivers are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)

from test_session_drivers import EXPECT_SERVICES, ITEST_HELPERS, Bench, _write, report  # noqa: E402

from egw_experiments import run as run_mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPO_ROOT / "docs" / "setup" / "qemu_integrated_gateway.md"
HOOKS = ("proof_hook_twins.sh", "proof_hook_drained.sh", "proof_fetch_sut_log.sh",
         "proof_restart_controller.sh")
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


# --------------------------------------------------------------------------
# Stubs of this module
# --------------------------------------------------------------------------

DOCKER_STUB = r'''#!/usr/bin/env python3
"""Stub docker for the proof hooks: the controller container, with its state
on disk, the broker and controller logs, the events read, the kill and the
compose start. What the tests steer through EGW_STUB_FAIL: a log read that
fails or that answers nothing, an events read that fails, a kill or a start
that is refused, a start without effect, a start that writes past the
harness's stderr budget, an inspect that does not answer."""
import json
import os
import sys

STATE = os.environ["EGW_STUB_LOG"] + ".proof-docker.json"
failures = f",{os.environ.get('EGW_STUB_FAIL', '')},"
FIRST_ID = "0f" * 32


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

if compose and cmd == "logs":
    # The broker's log, as 'docker compose logs --no-color --timestamps
    # mosquitto' prints it: one connection line per second.
    if fails("broker-log-fails"):
        print("no such service: mosquitto", file=sys.stderr)
        sys.exit(1)
    if fails("broker-log-empty"):
        sys.exit(0)
    for i in range(3):
        print(f"mosquitto-1  | 2026-09-25T10:00:0{i}.000000000Z 2026-09-25T10:00:0{i}: "
              "New connection from 172.18.0.7:52130 on port 8883.")
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
    for i, message in enumerate(("MQTT connected", "MQTT subscription granted; bridge ready")):
        print(f"2026-09-25T10:00:0{i}.500000000Z "
              + json.dumps({"ts": f"2026-09-25T10:00:0{i}.500Z", "level": "INFO",
                            "logger": "egw_controller.mqtt", "message": message}),
              file=sys.stderr)
    sys.exit(0)
if cmd == "events":
    if fails("docker-events-fails"):
        print("Cannot connect to the Docker daemon at unix:///var/run/docker.sock.", file=sys.stderr)
        sys.exit(1)
    if "--until" not in args:
        # The real command without --until FOLLOWS the daemon and never
        # returns; the stub refuses instead of hanging the test.
        print("stub: 'docker events' without --until never returns", file=sys.stderr)
        sys.exit(1)
    if fails("docker-events-empty"):
        sys.exit(0)
    print("stub events " + " ".join(args[1:]))
    print("2026-09-25T10:02:30.000000000Z container kill 0f0f (name=egw-controller-1, signal=9)")
    print("2026-09-25T10:02:30.100000000Z container die 0f0f (name=egw-controller-1, exitCode=137)")
    print("2026-09-25T10:02:31.000000000Z container start 0f0f (name=egw-controller-1)")
    sys.exit(0)
if cmd == "kill":
    if fails("kill-fails"):
        print("Error response from daemon: stub kill refused", file=sys.stderr)
        sys.exit(1)
    state["status"] = "exited"
    save(state)
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
'''

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
        _write(bench.bin / "rec", REC_STUB, executable=True)
        self.prefix = bench.home / "egw-tcg" / "itest"
        self.run_dir = bench.tmp / "raw" / RID
        self.sut_logs = self.run_dir / "logs" / "sut"
        self.sut_logs.mkdir(parents=True, exist_ok=True)

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
def hooks(tmp_path: Path) -> Hooks:
    return Hooks(Bench(tmp_path))


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
# proof_fetch_sut_log.sh (design 2.12 tests 13 and 14)
# --------------------------------------------------------------------------

FETCH_KINDS = {"broker": "broker_log", "controller": "controller_log", "docker-events": "docker_events"}


def _fetch(hooks: Hooks, kind: str, **overrides) -> tuple[subprocess.CompletedProcess, Path]:
    dest = hooks.sut_logs / run_mod.SUT_LOG_FILES[FETCH_KINDS[kind]]
    template = hooks.template("proof_fetch_sut_log.sh", kind, "{dest}", GUEST_T0)
    return hooks.run_hook(template, dest, **overrides), dest


@pytest.mark.parametrize("kind, token, exit_text, reason", [
    # A read that FAILED (ssh non-zero: the daemon's error on stderr, which
    # the controller read merges on the guest and so counts as bytes) and a
    # read that ANSWERED NOTHING (exit 0, empty) are both a log that was not
    # read: neither leaves a file. The daemon's reason, when there is one,
    # stays in the capsule either way.
    ("broker", "broker-log-fails", r"ssh egw-tcg exit 1, 0 bytes", "no such service: mosquitto"),
    ("broker", "broker-log-empty", r"ssh egw-tcg exit 0, 0 bytes", None),
    ("controller", "controller-log-fails", r"ssh egw-tcg exit 1, [1-9][0-9]* bytes",
     "Error: No such container: egw-controller-1"),
    ("controller", "controller-log-empty", r"ssh egw-tcg exit 0, 0 bytes", None),
    ("docker-events", "docker-events-fails", r"ssh egw-tcg exit 1, 0 bytes", "Cannot connect to the Docker daemon"),
    ("docker-events", "docker-events-empty", r"ssh egw-tcg exit 0, 0 bytes", None),
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
    # The read is test 5's: compose logs of the mosquitto service, without
    # colour and with timestamps, from the deployment directory.
    assert ("compose logs --no-color --timestamps mosquitto" in hooks.docker_calls()[-1])
    assert any("cd " in line and "/opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env logs"
               in line for line in hooks.ssh_commands())
    # DEST is write-once: the fetch that finds it stops without reading.
    again, _ = _fetch(hooks, "broker")
    assert again.returncode == 1, report(again)
    assert f"STOP: proof_fetch_sut_log: {dest} exists - NOT overwritten; nothing was read" in again.stderr
    assert len(hooks.ssh_commands()) == 1
    # The controller logs its JSON lines to stderr: the read merges the two
    # streams ON THE GUEST, so the lines reach DEST and ssh's own stderr
    # stays apart (and empty here).
    result, dest = _fetch(hooks, "controller")
    assert result.returncode == 0, report(result)
    assert "docker logs --timestamps egw-controller-1 2>&1" in hooks.ssh_commands()[-1]
    entries = [json.loads(line.split(" ", 1)[1]) for line in dest.read_text(encoding="utf-8").splitlines()]
    assert [e["message"] for e in entries] == ["MQTT connected", "MQTT subscription granted; bridge ready"]
    assert result.stderr == ""


def test_fetch_docker_events_is_bounded_by_since_and_until(hooks):
    result, dest = _fetch(hooks, "docker-events")
    assert result.returncode == 0, report(result)
    head = dest.read_text(encoding="utf-8").splitlines()[0]
    # '--since' is the driver's guest instant, '--until' the guest's own
    # clock when the read started: the read returns instead of following
    # the daemon (the stub refuses an unbounded read outright).
    match = re.fullmatch(r"stub events --filter container=egw-controller-1 --since (\d+) --until (\d+)", head)
    assert match, head
    assert match.group(1) == GUEST_T0
    assert int(match.group(2)) >= int(GUEST_T0)
    assert "docker events --filter container=egw-controller-1 --since 1700000000 --until $(date +%s)" \
        in hooks.ssh_commands()[-1]
    # A SINCE that is not a whole number of seconds is refused before the
    # guest is reached.
    bad = hooks.run_hook(hooks.template("proof_fetch_sut_log.sh", "docker-events", "{dest}", "now"),
                         hooks.sut_logs / "events-2.log")
    assert bad.returncode == 2, report(bad)
    assert "SINCE_GUEST_EPOCH 'now' is not a whole number of seconds: nothing was read" in bad.stderr
    assert len(hooks.ssh_commands()) == 1
    unknown = hooks.run_hook(hooks.template("proof_fetch_sut_log.sh", "journal", "{dest}", GUEST_T0),
                             hooks.sut_logs / "journal.log")
    assert unknown.returncode == 2, report(unknown)
    assert "KIND 'journal' is not broker, controller or docker-events: nothing was read" in unknown.stderr


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
