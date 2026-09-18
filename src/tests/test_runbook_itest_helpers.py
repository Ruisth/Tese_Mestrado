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
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path

import pytest

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
  */metrics) [ -s "$S/metrics.json" ] || { echo "curl: (7) stub: connection refused" >&2; exit 7; }
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
        self.metrics()

    def install(self, name: str, text: str) -> None:
        f = self.stubs / name
        f.write_text(text, encoding="utf-8")
        f.chmod(0o755)

    def set(self, name: str, value: object = "") -> None:
        (self.state / name).write_text(f"{value}\n", encoding="utf-8")

    def metrics(self, started_at: str = STARTED, queue_depth: int = 0, **counters: int) -> dict:
        m = {"queue_depth": queue_depth, "started_at": started_at, "monotonic_ns": 1,
             "accepted": 0, "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0}
        m.update(counters)
        (self.state / "metrics.json").write_text(json.dumps(m), encoding="utf-8")
        return m

    def jsonl(self, name: str, rows: list[dict]) -> None:
        (self.state / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def calls(self) -> str:
        f = self.state / "calls.log"
        return f.read_text(encoding="utf-8") if f.exists() else ""

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
                    "DRAIN_QUIET_S": "0", "DRAIN_STEP_S": "0", "READY_LIMIT_S": "0"})
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


def broker_log_line() -> str:
    return _one(_host_commands("### Test 9"), "ssh egw-tcg 'cd /opt/egw/deployment && docker compose")


def call_broker_log(bench: Bench) -> Result:
    return bench.run(bench.with_helpers("\n".join((broker_log_line().split("\n")[0], 'echo "RC9=$?"'))))


def test_test_9_broker_log_saved_returns_0_without_stop(bench: Bench) -> None:
    bench.set("broker_log", "1758190000: Client egw-sim disconnected, not authorised.")
    r = call_broker_log(bench)
    assert r.value("RC9") == "0", r.out
    assert not r.starting("STOP"), r.out
    assert "not authorised" in (bench.p / "itest-auth.broker.txt").read_text(encoding="utf-8")


def test_test_9_broker_log_ssh_fails_with_partial_output_prints_stop_and_names_the_ssh_status(bench: Bench) -> None:
    bench.set("broker_log", "1758190000: partial line")
    bench.set("ssh_logs_rc", 255)
    r = call_broker_log(bench)
    assert r.value("RC9") != "0", r.out
    assert any("ssh exit=255, tee exit=0" in ln for ln in r.starting("STOP: test 9(b)/(c): the broker log was NOT saved")), r.out


def test_test_9_broker_log_tee_reports_failure_prints_stop_and_names_the_tee_status(bench: Bench) -> None:
    bench.set("broker_log", "1758190000: some line")
    bench.install("tee", STUB_TEE_FAILS)
    r = call_broker_log(bench)
    assert r.value("RC9") != "0", r.out
    assert any("ssh exit=0, tee exit=1" in ln for ln in r.starting("STOP: test 9(b)/(c): the broker log was NOT saved")), r.out


def test_test_9_broker_log_empty_output_prints_stop(bench: Bench) -> None:
    r = call_broker_log(bench)
    assert r.value("RC9") != "0", r.out
    assert r.starting("STOP: test 9(b)/(c): the broker log was NOT saved"), r.out


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
