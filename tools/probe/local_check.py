#!/usr/bin/env python3
"""Local functional check of the broker-hold tool against a pinned Mosquitto on Docker.

A TOOL CHECK, NOT EVIDENCE. It runs the real clients of ``broker_hold.py``
(``sysreader``, ``hold``, ``publish``, ``discard``) and the real ``verdict``
against an isolated container of the pinned ``eclipse-mosquitto`` image on the
workstation's Docker (x86-64), through the same phases P0–P8 the session
driver sequences on the guest, with the same measurement copies of the
configuration. What it shows is that the tool exercises publication,
retention, the kill of the subscriber, the resumption of its session, the
redelivery with acknowledgement, the discard and the verdict end to end on a
real broker; it shows nothing about the emulated guest, its timing or its
memory, and nothing of it is QEMU evidence.

The attempt directory it writes has the layout of the session driver's
(``environment/probe/…``), so the same ``verdict`` reads it and the same
``local_export backfill`` can carry it into ``output_test`` labelled as a
local functional tool verification.

Secrets: the two passwords are read from a file of ``NAME=value`` lines
(``--secrets-env``) into the clients' environment; they never reach a command
line or a record.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / "broker_hold.py"
CONTAINER = "egw-probe-local"
SUBSCRIBED = "SUBSCRIBED:"


def utc_now() -> str:
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{dt.microsecond // 1000:03d}Z"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_secrets(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    for name in ("MOSQUITTO_SIMULATOR_PASSWORD", "MOSQUITTO_CONTROLLER_PASSWORD"):
        if not out.get(name):
            raise SystemExit(f"prerequisite: {name} is not in {path}")
    return out


class Steps:
    """The record of every command, like the driver's commands.jsonl."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.seq = 0

    def run(self, name: str, argv: list[str], *, timeout: float = 300, check: bool = False, env=None,
            redact: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
        self.seq += 1
        t0 = time.monotonic()
        started = utc_now()
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        shown = [("<redacted>" if a in redact else a) for a in argv]
        record = {"seq": self.seq, "name": name, "argv": shown, "started_utc": started,
                  "duration_s": round(time.monotonic() - t0, 3), "exit": proc.returncode,
                  "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        print(f"[{name}] exit={proc.returncode} ({record['duration_s']} s)", flush=True)
        if check and proc.returncode != 0:
            raise RuntimeError(f"{name} failed ({proc.returncode}): {proc.stdout[-500:]} {proc.stderr[-500:]}")
        return proc


class Phases:
    def __init__(self, path: Path) -> None:
        self.path = path

    def mark(self, phase: str, edge: str) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"phase": phase, f"{edge}_utc": utc_now(), f"{edge}_epoch": int(time.time())}) + "\n")
        print(f"--- {phase} {edge} {utc_now()}", flush=True)

    def note(self, phase: str, key: str, value) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"phase": phase, key: value}) + "\n")


class Recorder(threading.Thread):
    """The 1 s recorder, through ``docker exec`` (the container's own cgroup v2 files)."""

    COLUMNS = "ts_utc,epoch,mem_current,mem_max,mem_peak,anon,file,active_file,inactive_file,ev_max,ev_oom,ev_oom_kill,db_bytes,state,restarts"
    SCRIPT = ("cd /sys/fs/cgroup && cat memory.current memory.max && (cat memory.peak 2>/dev/null || echo '?') && "
              "for k in anon file active_file inactive_file; do awk -v k=$k '$1==k{print $2; f=1} END{if(!f)print \"?\"}' memory.stat; done && "
              "for k in max oom oom_kill; do awk -v k=$k '$1==k{print $2; f=1} END{if(!f)print \"?\"}' memory.events; done && "
              "(wc -c < /mosquitto/data/mosquitto.db 2>/dev/null || echo 0)")

    def __init__(self, out: Path, container: str, interval_s: float = 1.0) -> None:
        super().__init__(daemon=True)
        self.out = out
        self.container = container
        self.interval_s = interval_s
        self.stop_flag = threading.Event()
        self.samples = 0

    def run(self) -> None:
        with open(self.out, "w", encoding="utf-8") as fh:
            fh.write(f"# local_check recorder container={self.container} interval={self.interval_s} start={utc_now()}\n")
            fh.write(self.COLUMNS + "\n")
        state, restarts = "?", "?"
        while not self.stop_flag.is_set():
            t0 = time.monotonic()
            if self.samples % 10 == 0:
                ins = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}} {{.RestartCount}}", self.container],
                                     capture_output=True, text=True)
                if ins.returncode == 0 and ins.stdout.strip():
                    state, restarts = ins.stdout.split()[0], ins.stdout.split()[1]
                else:
                    state, restarts = "?", "?"
            ts, ep = utc_now(), int(time.time())
            ex = subprocess.run(["docker", "exec", self.container, "sh", "-c", self.SCRIPT], capture_output=True, text=True)
            vals = [v.strip() for v in ex.stdout.splitlines()] if ex.returncode == 0 else []
            if len(vals) != 11:
                vals = ["?"] * 11
            with open(self.out, "a", encoding="utf-8") as fh:
                fh.write(",".join([ts, str(ep), *vals, state, restarts]) + "\n")
            self.samples += 1
            delay = self.interval_s - (time.monotonic() - t0)
            if delay > 0:
                self.stop_flag.wait(delay)
        with open(self.out, "a", encoding="utf-8") as fh:
            fh.write(f"# stop samples={self.samples} end={utc_now()}\n")


def wait_line(path: Path, needle: str, limit_s: float) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit_s:
        try:
            if needle in path.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def sys_last(path: Path, topic: str):
    last = None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("event") == "sys" and r.get("topic") == topic:
                last = r.get("value")
    except OSError:
        pass
    return last


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--image", required=True, help="the pinned eclipse-mosquitto reference (repo@sha256:...)")
    p.add_argument("--conf", required=True, help="the deployed mosquitto.conf to copy (the measurement lines are appended)")
    p.add_argument("--acl", required=True, help="the deployed acl to copy (the $SYS read is added)")
    p.add_argument("--certs", required=True, help="directory with ca.crt, server.crt, server.key")
    p.add_argument("--passwd", required=True, help="the mosquitto password file for egw-simulator and egw-controller")
    p.add_argument("--secrets-env", required=True)
    p.add_argument("--messages", required=True, help="messages.jsonl from 'broker_hold.py generate'")
    p.add_argument("--out", required=True, help="the attempt directory to write")
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--port", type=int, default=8883)
    p.add_argument("--W", type=int, default=4999)
    p.add_argument("--Q", type=int, default=1000)
    p.add_argument("--expiry", default="1h")
    p.add_argument("--A", type=int, default=4999)
    p.add_argument("--B", type=int, default=1100)
    p.add_argument("--rate", type=float, default=11.2)
    p.add_argument("--memory", default="128m")
    p.add_argument("--memory-max", type=int, default=134217728)
    p.add_argument("--p0", type=float, default=60)
    p.add_argument("--p1", type=float, default=10)
    p.add_argument("--hold1", type=float, default=130)
    p.add_argument("--p4", type=float, default=10)
    p.add_argument("--hold2", type=float, default=70)
    p.add_argument("--p7-limit", type=float, default=300)
    p.add_argument("--p7-idle", type=float, default=30)
    p.add_argument("--p8", type=float, default=30)
    p.add_argument("--label", default="local functional tool verification, not QEMU evidence")
    p.add_argument("--keep", action="store_true", help="leave the container and volume in place (debugging only)")
    args = p.parse_args(argv)

    out = Path(args.out).resolve()
    if out.exists():
        raise SystemExit(f"prerequisite: {out} exists; attempts are write-once")
    pr = out / "environment" / "probe"
    pr.mkdir(parents=True)
    tag = out.name
    volume = f"egw-probe-local-data-{tag}"
    label = f"egw.probe.attempt={tag}"
    steps = Steps(out / "commands.jsonl")
    phases = Phases(pr / "phases.jsonl")
    secrets = load_secrets(Path(args.secrets_env))
    env = dict(os.environ)
    env.update(secrets)
    env["PYTHONUTF8"] = "1"

    # the measurement copies, hashed
    conf_text = Path(args.conf).read_text(encoding="utf-8")
    conf_text += ("\n# --- broker-hold measurement (ADR 0011, condition C3): probe settings, not production values ---\n"
                  f"max_inflight_messages {args.W}\nmax_inflight_bytes 0\nmax_queued_messages {args.Q}\n"
                  f"max_queued_bytes 0\npersistent_client_expiration {args.expiry}\n")
    acl_lines = []
    for line in Path(args.acl).read_text(encoding="utf-8").splitlines():
        acl_lines.append(line)
        if line.startswith("user egw-controller"):
            acl_lines.append("topic read $SYS/#")
    conf_path = pr / "mosquitto.measure.conf"
    acl_path = pr / "acl.measure"
    conf_path.write_text(conf_text, encoding="utf-8", newline="\n")
    acl_path.write_text("\n".join(acl_lines) + "\n", encoding="utf-8", newline="\n")
    messages = Path(args.messages).resolve()
    shutil.copyfile(messages, pr / "messages.jsonl")
    params = {"W": args.W, "Q": args.Q, "expiry": args.expiry, "A": args.A, "B": args.B, "rate_hz": args.rate,
              "hold1_s": args.hold1, "hold2_s": args.hold2, "p0_s": args.p0, "p4_s": args.p4,
              "p7_limit_s": args.p7_limit, "memory": args.memory, "memory_max": args.memory_max,
              "broker": f"127.0.0.1:{args.port}", "container": CONTAINER, "volume": volume, "label": label,
              "recorder_gap_limit_s": 5, "guest_offset_s": 0, "image": args.image,
              "kind": args.label, "conf_sha256": sha256_file(conf_path), "acl_sha256": sha256_file(acl_path),
              "messages_sha256": sha256_file(messages), "python": args.python, "host": "workstation docker (x86-64)"}
    (pr / "params.json").write_text(json.dumps(params, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def client(name: str, *cargs: str) -> subprocess.Popen:
        stdout = open(pr / f"{name}.stdout.txt", "w", encoding="utf-8")
        stderr = open(pr / f"{name}.stderr.txt", "w", encoding="utf-8")
        return subprocess.Popen([args.python, str(PROBE), *cargs], stdout=stdout, stderr=stderr, env=env)

    ca = str(Path(args.certs) / "ca.crt")
    host = ["--host", "127.0.0.1", "--port", str(args.port), "--ca-cert", ca]
    rec_thread = None
    probe_state = None
    result = {"outcome": "not-run"}
    hold = None
    sysr = None
    try:
        # the ownership guard
        ins = subprocess.run(["docker", "inspect", CONTAINER], capture_output=True, text=True)
        if ins.returncode == 0:
            raise SystemExit(f"prerequisite: a container named {CONTAINER} exists; it is not this check's to remove")
        # the broker
        phases.mark("setup", "start")
        steps.run("volume-create", ["docker", "volume", "create", "--label", label, volume], check=True)
        steps.run("probe-start", [
            "docker", "run", "-d", "--name", CONTAINER, "--label", label, "--memory", args.memory,
            "-p", f"{args.port}:8883",
            "-v", f"{Path(args.certs).resolve()}:/mosquitto/config/certs:ro",
            "-v", f"{Path(args.passwd).resolve()}:/mosquitto/config/passwd:ro",
            "-v", f"{conf_path}:/mosquitto/config/mosquitto.conf:ro",
            "-v", f"{acl_path}:/mosquitto/config/acl:ro",
            "-v", f"{volume}:/mosquitto/data", args.image], check=True)
        started = False
        for _ in range(60):
            logs = subprocess.run(["docker", "logs", CONTAINER], capture_output=True, text=True)
            if "listen socket on port 8883" in logs.stdout + logs.stderr:
                started = True
                break
            st = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", CONTAINER], capture_output=True, text=True)
            if st.stdout.strip() != "running":
                break
            time.sleep(1)
        steps.run("probe-inspect", ["docker", "inspect", "-f",
                                    "id={{.Id}} image={{.Image}} state={{.State.Status}} label={{index .Config.Labels \"egw.probe.attempt\"}}", CONTAINER])
        mm = subprocess.run(["docker", "exec", CONTAINER, "cat", "/sys/fs/cgroup/memory.max"], capture_output=True, text=True)
        phases.note("setup", "memory_max", mm.stdout.strip())
        if not started:
            phases.note("P0", "broker_refused", True)
        rec_thread = Recorder(pr / "recorder.csv", CONTAINER)
        rec_thread.start()
        phases.mark("setup", "end")

        if started:
            # P0
            phases.mark("P0", "start")
            sysr = client("sysreader", "sysreader", *host, "--stop-file", str(pr / "sys.stop"), "--limit", "7200",
                          "--record", str(pr / "sys.jsonl"))
            if not wait_line(pr / "sysreader.stdout.txt", SUBSCRIBED, 30):
                phases.note("P0", "sys_unreadable", True)
                raise RuntimeError("the $SYS reader did not subscribe: " + (pr / "sysreader.stderr.txt").read_text())
            time.sleep(args.p0)
            phases.mark("P0", "end")
            # P1
            phases.mark("P1", "start")
            hold = client("hold_p1", "hold", *host, "--stop-file", str(pr / "hold_p1.stop"), "--limit", "7200",
                          "--record", str(pr / "hold_p1.jsonl"))
            if not wait_line(pr / "hold_p1.stdout.txt", SUBSCRIBED, 30):
                raise RuntimeError("the holding subscriber did not subscribe: " + (pr / "hold_p1.stderr.txt").read_text())
            time.sleep(args.p1)
            store_base = sys_last(pr / "sys.jsonl", "$SYS/broker/store/messages/count")
            phases.note("P1", "store_baseline", store_base)
            phases.mark("P1", "end")
            # P2
            phases.mark("P2", "start")
            r2 = steps.run("p2-publish", [args.python, str(PROBE), "publish", "--messages", str(pr / "messages.jsonl"),
                                          "--first", "0", "--count", str(args.A), "--rate", str(args.rate), *host,
                                          "--record", str(pr / "publish_p2.jsonl")], timeout=args.A / args.rate + 600, env=env)
            phases.mark("P2", "end")
            phases.note("P2", "publisher_exit", r2.returncode)
            # P3
            phases.mark("P3", "start")
            time.sleep(args.hold1)
            phases.note("P3", "store_end", sys_last(pr / "sys.jsonl", "$SYS/broker/store/messages/count"))
            phases.note("P3", "inflight_end", sys_last(pr / "sys.jsonl", "$SYS/broker/messages/inflight"))
            phases.mark("P3", "end")
            # P4: the kill, no DISCONNECT
            phases.mark("P4", "start")
            if hold.poll() is None:
                hold.kill()
                phases.note("P4", "sigkill_at", utc_now())
                hold.wait(timeout=30)
                phases.note("P4", "hold_p1_exit", str(hold.returncode))
            else:
                phases.note("P4", "hold_p1_exit", str(hold.returncode))
                phases.note("P4", "hold_ended_early", True)
            seen = False
            t0 = time.monotonic()
            while time.monotonic() - t0 < args.p4:
                logs = subprocess.run(["docker", "logs", CONTAINER], capture_output=True, text=True)
                text = logs.stdout + logs.stderr
                if any("egw-probe-hold" in ln and ("closed its connection" in ln or "disconnect" in ln.lower() or "Socket error" in ln)
                       for ln in text.splitlines()):
                    seen = True
                    break
                time.sleep(1)
            phases.note("P4", "disconnection_seen", seen)
            if not seen:
                phases.note("P4", "limit_reached", True)
            phases.mark("P4", "end")
            # P5
            phases.mark("P5", "start")
            r5 = steps.run("p5-publish", [args.python, str(PROBE), "publish", "--messages", str(pr / "messages.jsonl"),
                                          "--first", str(args.A), "--count", str(args.B), "--rate", str(args.rate), *host,
                                          "--record", str(pr / "publish_p5.jsonl")], timeout=args.B / args.rate + 600, env=env)
            phases.mark("P5", "end")
            phases.note("P5", "publisher_exit", r5.returncode)
            # P6
            phases.mark("P6", "start")
            time.sleep(args.hold2)
            store_p6 = sys_last(pr / "sys.jsonl", "$SYS/broker/store/messages/count")
            phases.note("P6", "store_end", store_p6)
            phases.note("P6", "dropped_end", sys_last(pr / "sys.jsonl", "$SYS/broker/publish/messages/dropped"))
            phases.mark("P6", "end")
            # P7
            phases.mark("P7", "start")
            # what comes back is the count ABOVE the baseline (the store holds
            # the broker's own retained messages, the $SYS topics among them)
            expect = str(args.A)
            if (store_p6 or "").isdigit() and (store_base or "").isdigit() and int(store_p6) > int(store_base):
                expect = str(int(store_p6) - int(store_base))
            phases.note("P7", "expect", expect)
            hold = client("hold_p7", "hold", "--ack", *host, "--stop-file", str(pr / "hold_p7.stop"), "--expect", expect,
                          "--idle", str(args.p7_idle), "--limit", str(args.p7_limit), "--record", str(pr / "hold_p7.jsonl"))
            wait_line(pr / "hold_p7.stdout.txt", SUBSCRIBED, 30)
            try:
                hold.wait(timeout=args.p7_limit + 60)
                phases.note("P7", "hold_p7_exit", str(hold.returncode))
            except subprocess.TimeoutExpired:
                hold.kill()
                hold.wait()
                phases.note("P7", "hold_p7_exit", "ended-by-driver")
                phases.note("P7", "limit_reached", True)
                phases.note("P7", "stop_rule_reached", "the holding subscriber did not end within its limit plus 60 s")
            if "why=limit" in (pr / "hold_p7.stdout.txt").read_text(encoding="utf-8", errors="replace"):
                phases.note("P7", "limit_reached", True)
            phases.note("P7", "store_end", sys_last(pr / "sys.jsonl", "$SYS/broker/store/messages/count"))
            phases.mark("P7", "end")
            # P8
            phases.mark("P8", "start")
            time.sleep(args.p8)
            steps.run("discard", [args.python, str(PROBE), "discard", *host, "--record", str(pr / "discard.jsonl")], env=env)
            phases.mark("P8", "end")
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        result = {"outcome": "aborted", "reason": str(exc)}
        print(f"STOP: {exc}", file=sys.stderr)
    finally:
        # the clients reaped, the recorder stopped, the state read, the probe removed
        for proc in (hold, sysr):
            if proc is not None and proc.poll() is None:
                if proc is sysr:
                    (pr / "sys.stop").write_text("")
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                else:
                    proc.kill()
                    proc.wait()
        if rec_thread is not None:
            rec_thread.stop_flag.set()
            rec_thread.join(timeout=15)
        ps = subprocess.run(["docker", "inspect", "-f",
                             '{"status":"{{.State.Status}}","oom_killed":{{.State.OOMKilled}},"restart_count":{{.RestartCount}},"exit_code":{{.State.ExitCode}},"id":"{{.Id}}","image":"{{.Image}}","label":"{{index .Config.Labels "egw.probe.attempt"}}"}',
                             CONTAINER], capture_output=True, text=True)
        if ps.returncode == 0:
            (pr / "probe_state.json").write_text(ps.stdout.strip() + "\n", encoding="utf-8")
            try:
                probe_state = json.loads(ps.stdout)
            except ValueError:
                probe_state = None
        logs = subprocess.run(["docker", "logs", "-t", CONTAINER], capture_output=True, text=True)
        (pr / "broker.log").write_text(logs.stdout + logs.stderr, encoding="utf-8")
        if not args.keep and probe_state is not None and probe_state.get("label") == tag:
            steps.run("probe-remove", ["docker", "rm", "-f", CONTAINER])
            steps.run("volume-remove", ["docker", "volume", "rm", volume])
    for f in ("hold_p1", "hold_p7", "publish_p2", "publish_p5", "sys"):
        (pr / f"{f}.jsonl").touch()
    # the verdict, the real one
    spec = importlib.util.spec_from_file_location("broker_hold", PROBE)
    bh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bh)
    vrc = bh.main(["verdict", "--params", str(pr / "params.json"), "--phases", str(pr / "phases.jsonl"),
                   "--broker-log", str(pr / "broker.log"), "--publish-p2", str(pr / "publish_p2.jsonl"),
                   "--publish-p5", str(pr / "publish_p5.jsonl"), "--hold-p1", str(pr / "hold_p1.jsonl"),
                   "--hold-p7", str(pr / "hold_p7.jsonl"), "--sys", str(pr / "sys.jsonl"),
                   "--recorder", str(pr / "recorder.csv"), "--probe-state", str(pr / "probe_state.json"),
                   "--out", str(pr / "verdict.json")])
    verdict = json.loads((pr / "verdict.json").read_text(encoding="utf-8"))
    result.update({"kind": args.label, "broker_verdict": verdict["result"], "verdict_exit": vrc,
                   "image": args.image, "tag": tag, "finished_utc": utc_now(),
                   "container_removed": not args.keep and probe_state is not None and probe_state.get("label") == tag})
    if result.get("outcome") == "not-run":
        result["outcome"] = "completed"
    (out / "local_check.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"LOCAL CHECK: {result['outcome']}; broker verdict {verdict['result']} (exit {vrc}); {args.label}")
    return vrc if result["outcome"] == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
