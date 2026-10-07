#!/usr/bin/env python3
"""BENCH STAND-IN (stream BENCH of the S4 preparation, 2026-10-05) for two commands of
test 6's lines: 'python -m egw_experiments run' (the harness, line 1425 through
harness_cmd) and 'python -m egw_experiments analyze' (line 1428). It is NOT the harness
and NOT analyze: no simulator runs, no broker, no collector, no measurement. The bench's
venv 'python' hands those two commands here; everything else of the venv is the real
python (the export tool, the drivers' helpers) or the test module's STUB_PYTHON ($REC,
the simulator).

What it does is what the harness leaves on the host for the case under test, with the
merged code's own functions where the harness uses them (the bench's copy of
egw_experiments, 1fd9792, first on sys.path):
  run      - refuses, as the harness does, a run directory that exists and a run id the
             plan does not hold (exit 2, nothing written); records its argv with every
             --password value hidden in $EGW_STUB_STATE/harness.argv.json; creates
             ~/egw-tcg/pilot/results/raw/<run_id>/; sets the plan entry 'running' with
             run.update_plan_status; runs, rendered with run.format_collector_template
             and split with shlex as run.py does, the hooks line 1425 hands it - the
             twin hook 'before', the restart command (run.format_cmd_template: the
             controller restart through the bench's ssh), the drain hook, the post-drain
             fetch, the twin hook 'after' and the three bounded SUT fetches - for real
             when the case says hooks=real (they then run the checkout's own
             proof_hook_twins.sh and proof_hook_drained.sh, the runbook's 'drained' with
             its real 130 s window, against the module's stubs), otherwise it writes
             their files itself; writes manifest.json (drain.outcome,
             resources_proved_down, resources_transition_rows, a 'bench_stand_in' key),
             the simulator directory logs/simulator/<run_id>/ (sent_events.jsonl and its
             manifest.json), events.jsonl, events.post-drain.jsonl, logs/sut/; when the
             case's exit is 0, SHA256SUMS last; then the plan entry 'completed' or
             'failed' with result_dir, finished_utc and validity (update_plan_status, as
             run.py does at its end); and exits with the case's code.
  analyze  - writes ~/egw-tcg/pilot/results/processed/per_run.csv (one row per run
             directory, the columns test 6 is read by) and exits with the case's code.
The case is read from $EGW_STUB_STATE/bench_<name> files: harness_rc (0), hooks
(files|real), drain_outcome (quiet|gave-up), restart (yes|no), harness_sleep (seconds to
sleep after the run directory is made, for 'term'), analyze_rc (0).
"""
import csv
import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from egw_experiments import run as run_mod

STATE = Path(os.environ["EGW_STUB_STATE"])
BENCH = Path(os.environ["BENCH"])
SIX = ["egw-mosquitto-1", "egw-mongodb-1", "egw-ditto-policies-1", "egw-ditto-things-1", "egw-ditto-gateway-1",
       "egw-controller-1"]
RULE = "1a-option-a-2026-10-05"


def case(name: str, default: str = "") -> str:
    f = STATE / f"bench_{name}"
    return f.read_text(encoding="utf-8").strip() if f.exists() else default


def say(text: str) -> None:
    print(text, flush=True)


def calls(text: str) -> None:
    with open(STATE / "calls.log", "a", encoding="utf-8") as fh:
        fh.write(text + "\n")


def masked(argv: list[str]) -> list[str]:
    out, hide = [], False
    for a in argv:
        out.append("<hidden>" if hide else a)
        hide = a == "--password"
    return out


def opts_of(argv: list[str]) -> dict[str, str]:
    o = {}
    for i, a in enumerate(argv):
        if a.startswith("--") and i + 1 < len(argv):
            o[a] = argv[i + 1]
    return o


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def hook(label: str, template: str, rid: str, dest: Path, logdir: Path, timeout: float = 1800.0) -> int:
    """One hook, rendered and split as run.py's execute_collector_hook does, run without a
    shell, stdin from the null device, in a session of its own; its output kept beside."""
    cmd = run_mod.format_collector_template(template, rid, duration_s=600, dest=dest, expect_services=SIX)
    argv = shlex.split(cmd, posix=True)
    calls(f"bench harness stand-in: hook {label}: {' '.join(argv)}")
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, start_new_session=True, timeout=timeout)
    write(logdir / f"hook-{label}.stdout.txt", p.stdout.decode("utf-8", "replace"))
    write(logdir / f"hook-{label}.stderr.txt", p.stderr.decode("utf-8", "replace"))
    say(f"[harness] (bench stand-in) hook {label}: exit {p.returncode}")
    return p.returncode


def cmd_run(argv: list[str]) -> int:
    o = opts_of(argv)
    rid = o.get("--run-id", "")
    plan = Path(o.get("--plan", ""))
    base = Path(o.get("--base-dir", ""))
    (STATE / "harness.argv.json").write_text(json.dumps(masked(argv), indent=1) + "\n", encoding="utf-8")
    calls("bench harness stand-in: python -m egw_experiments run " + " ".join(masked(argv)))
    say("[harness] BENCH STAND-IN for 'python -m egw_experiments run' (bs4_harness.py): NOT the harness")
    rc = int(case("harness_rc", "0"))
    run_dir = base / "raw" / rid
    if run_dir.exists():
        say(f"[harness] error: {run_dir} exists - refused (exit 2, nothing written)")
        return 2
    runs = json.loads(plan.read_text(encoding="utf-8")).get("runs", [])
    if not any(r.get("run_id") == rid for r in runs):
        say(f"[harness] error: run id {rid!r} is not in the plan {plan} - refused (exit 2)")
        return 2
    if rc == 2:
        say("[harness] refused before the run (bench case: harness exit 2) - nothing written")
        return 2
    run_dir.mkdir(parents=True)
    run_mod.update_plan_status(plan, rid, "running")
    say(f"[harness] run {rid}: run directory {run_dir} created; plan entry 'running' (run.update_plan_status)")
    sleep_s = case("harness_sleep")
    if sleep_s:
        write(BENCH / "harness.started", f"{os.getpid()}\n")
        say(f"[harness] (bench case) sleeping {sleep_s} s inside the run (pid {os.getpid()})")
        time.sleep(int(sleep_s))
    sut = run_dir / "logs" / "sut"
    sut.mkdir(parents=True)
    real = case("hooks", "files") == "real"
    prefix = Path(os.environ["HOME"]) / "egw-tcg" / "itest" / rid
    ident = o.get("--config-identity-from")
    if ident and Path(ident).is_file():
        write(run_dir / "configuration_identity.json", Path(ident).read_text(encoding="utf-8"))
    hooks: dict[str, int] = {}
    # the 'before' twin snapshot
    if real:
        hooks["twin_snapshot_before"] = hook("twin_snapshot_before", o["--twin-snapshot-cmd"], rid,
                                             run_dir / "twins.before.json", sut)
    else:
        write(Path(f"{prefix}.twins.before.json"), '{"bench": "stand-in twins before"}\n')
        write(run_dir / "twins.before.json", '{"bench": "stand-in twins before"}\n')
    # the simulator's directory (the workload is not run)
    sent = [{"message_id": f"bench-msg-{i}", "device_type": "smartwatch", "device_uuid": "uuid-0001", "seq": i,
             "run_id": rid} for i in range(3)]
    sent_text = "".join(json.dumps(r) + "\n" for r in sent)
    simd = run_dir / "logs" / "simulator" / rid
    write(simd / "sent_events.jsonl", sent_text)
    write(simd / "manifest.json", json.dumps({"run_id": rid, "totals": {"sent": len(sent)}, "bench": "stand-in"}) + "\n")
    write(run_dir / "sent_events.jsonl", sent_text)
    events_text = "".join(json.dumps({"run_id": rid, "message_id": r["message_id"], "outcome": "accepted",
                                      "attempts": 1, "error": None}) + "\n" for r in sent)
    write(run_dir / "events.jsonl", events_text)
    # the restart, once, as run.py's _execute_restart_cmd runs it
    restart: dict = {"template": o.get("--restart-cmd"), "at_s": o.get("--restart-at-s"), "executed": False}
    if case("restart", "yes") == "yes" and o.get("--restart-cmd"):
        cmd = run_mod.format_cmd_template(o["--restart-cmd"], rid)
        calls(f"bench harness stand-in: restart: {cmd}")
        p = subprocess.run(shlex.split(cmd, posix=True), capture_output=True, text=True, timeout=120)
        restart.update({"executed": True, "command": cmd, "returncode": p.returncode, "finished_utc": now_iso()})
        say(f"[harness] (bench stand-in) restart command run at once (not at +{o.get('--restart-at-s')} s): exit {p.returncode}")
    # the drain
    outcome = case("drain_outcome", "quiet")
    if real and outcome == "quiet":
        d = hook("drain", o["--drain-cmd"], rid, sut / "drain.txt", sut)
        hooks["drain"] = d
        text = (sut / "hook-drain.stdout.txt").read_text(encoding="utf-8")
        outcome = "quiet" if d == 0 and "drained: queue_depth 0" in text else "error"
    else:
        write(sut / "hook-drain.stdout.txt", f"bench stand-in: the drain's transcript (outcome {outcome}) is not run\n")
    # the post-drain copy and the 'after' twin snapshot (only after a quiet drain)
    if outcome == "quiet":
        if real:
            hooks["post_drain"] = hook("post_drain", o["--post-drain-fetch-cmd"], rid,
                                       run_dir / run_mod.POST_DRAIN_EVENTS_FILENAME, sut)
            hooks["twin_snapshot_after"] = hook("twin_snapshot_after", o["--twin-snapshot-cmd"], rid,
                                                run_dir / "twins.after.json", sut)
        else:
            write(run_dir / run_mod.POST_DRAIN_EVENTS_FILENAME, events_text)
            write(Path(f"{prefix}.twins.after.json"), '{"bench": "stand-in twins after"}\n')
            write(run_dir / "twins.after.json", '{"bench": "stand-in twins after"}\n')
    # the three bounded SUT reads, last
    if real:
        for label, flag, name in (("broker", "--fetch-broker-log-cmd", "broker.log"),
                                  ("controller", "--fetch-controller-log-cmd", "controller.log"),
                                  ("docker_events", "--fetch-docker-events-cmd", "docker-events.log")):
            hooks[label] = hook(label, o[flag], rid, sut / name, sut)
    else:
        write(sut / "controller.log", "2026-10-05T20:00:01.000000000Z bench controller line (stand-in)\n")
        write(sut / "broker.log", "2026-10-05T20:00:01.000000000Z bench broker line (stand-in)\n")
    failed_hooks = sorted(k for k, v in hooks.items() if v != 0)
    if failed_hooks and rc == 0:
        say(f"[harness] INVALID: (bench stand-in) hook(s) {', '.join(failed_hooks)} did not end 0")
        rc = 1
    validity = "valid" if rc == 0 else "invalid"
    manifest = {
        "bench_stand_in": "written by bs4_harness.py (the S4 bench), not by the harness",
        "run_id": rid, "validity": validity,
        "invalid_reasons": [] if rc == 0 else ["bench case: harness exit %d (an instrumentation reason)" % rc],
        "restart": restart, "hooks": hooks,
        "drain": {"outcome": outcome, "transcript": "logs/sut/hook-drain.stdout.txt"},
        "resources_proved_down": {"applies": True, "why_not": None, "die_utc": "2026-10-05T20:05:00.400000000Z",
                                  "start_utc": "2026-10-05T20:05:06.300000000Z",
                                  "effective_end_utc": "2026-10-05T20:05:06.300000000Z", "capped": False,
                                  "edge_gap_before_s": 0.4, "edge_gap_after_s": 1.2, "rejected_rows": [],
                                  "resources_ingested": True},
        "resources_transition_rows": {"rule": o.get("--restart-transition-rule"), "admitted": True, "why_not": None,
                                      "resources_ingested": True, "count": 2,
                                      "instants": ["2026-10-05T20:05:01Z", "2026-10-05T20:05:04Z"]},
    }
    write(run_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    if rc == 0:
        lines = []
        for f in sorted(p for p in run_dir.rglob("*") if p.is_file()):
            lines.append("%s  %s\n" % (hashlib.sha256(f.read_bytes()).hexdigest(), f.relative_to(run_dir).as_posix()))
        write(run_dir / "SHA256SUMS", "".join(lines))
    else:
        say(f"[harness] INVALID: bench case: harness exit {rc} (an instrumentation reason); SHA256SUMS is withheld")
    run_mod.update_plan_status(plan, rid, "completed" if rc == 0 else "failed", result_dir=str(run_dir),
                               finished_utc=now_iso(), validity=validity)
    say(f"[harness] run {rid} {'completed' if rc == 0 else 'FAILED'} (bench stand-in; plan entry rewritten by run.update_plan_status)")
    return rc


def cmd_analyze(argv: list[str]) -> int:
    o = opts_of(argv)
    base = Path(o.get("--base-dir", ""))
    calls("bench analyze stand-in: python -m egw_experiments analyze " + " ".join(argv))
    rc = int(case("analyze_rc", "0"))
    proc = base / "processed"
    proc.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in sorted((base / "raw").glob("*/manifest.json")):
        doc = json.loads(m.read_text(encoding="utf-8"))
        rows.append({"run_id": doc.get("run_id") or m.parent.name, "validity": doc.get("validity"), "lost": 0,
                     "late_confirmations": 0, "double_accepted": 0, "restart_metrics_endpoint_recovery_s": 12.0,
                     "restart_functional_recovery_s": 14.0})
    cols = ["run_id", "validity", "lost", "late_confirmations", "double_accepted",
            "restart_metrics_endpoint_recovery_s", "restart_functional_recovery_s"]
    with open(proc / "per_run.csv", "w", encoding="utf-8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    say(f"[analyze] BENCH STAND-IN (bs4_harness.py): wrote {proc / 'per_run.csv'} ({len(rows)} row(s)); exit {rc}")
    return rc


def main() -> int:
    argv = sys.argv[1:]
    # called as: bs4_harness.py -m egw_experiments <run|analyze> ...
    if argv[:2] != ["-m", "egw_experiments"] or len(argv) < 3:
        print("bench stand-in: unexpected arguments: " + " ".join(masked(argv)), file=sys.stderr)
        return 97
    sub, rest = argv[2], argv[3:]
    if sub == "run":
        return cmd_run(rest)
    if sub == "analyze":
        return cmd_analyze(rest)
    print(f"bench stand-in: unexpected subcommand {sub!r}", file=sys.stderr)
    return 97


if __name__ == "__main__":
    sys.exit(main())
