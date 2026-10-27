#!/usr/bin/env python3
"""Bench of the second opening of S3: one change to a COPY of the fixture.

The fixture (made by bs3b_fixture.sh in <dest>) is a copy of the exported package of the real
failed preflight 20261005T105656Z_live-preflight_attempt11 under <dest>/attempts/<run id>/ and
the driver console as the operator script saw it, without its last line, in
<dest>/preflight.console.txt. This script changes that copy, never the original, and prints
one line saying what it changed. Every line of commands.jsonl other than the one changed is
kept byte for byte.

Usage (the execution venv's python): bs3b_mutate.py <variant> <dest>

Variants:
  unchanged            nothing
  step7-exit1          commands.jsonl: step 7 (stack-health) exit_code 0 -> 1
  no-attempt-json      attempt.json removed
  other-run-id         the console's DRIVER RESULT line names ..._attempt12 (no such attempt)
  other-run-id-dir     the same, and a copy of the attempt directory named ..._attempt12
                       (its attempt.json still says ..._attempt11)
  collector-problem    analysis/collector/collector-check.json: one problem listed
  capture-failures     attempt.json: capture_failures holds one record
  capture-truncated    commands.jsonl: step 13 (collector-live) stdout capture state 'truncated'
  system-fault         attempt.json: system_outcome 'fail' and the reason starts with the frozen
                       preflight's 'observed system fault(s): ' (stack-health exit 3); the
                       console's DRIVER RESULT line says system_outcome=fail, as the driver's
                       own line would
  system-fault-record  attempt.json alone, as in system-fault; the console unchanged
  reason-fault         attempt.json: the reason alone starts with an observed fault
                       (system_outcome stays 'inconclusive'); validator only
"""
import json
import shutil
import sys
from pathlib import Path

RID = "20261005T105656Z_live-preflight_attempt11"
OTHER = "20261005T105656Z_live-preflight_attempt12"
FAULT = ("observed system fault(s): the stack is not healthy, a container was OOM-killed or is not "
         "there at all, or the kernel reports a memory-cgroup OOM in this boot (stack-health exit 3); ")


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def one_command(att, seq, change):
    path = att / "commands.jsonl"
    lines = path.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.strip() and json.loads(line).get("seq") == seq:
            rec = json.loads(line)
            what = change(rec)
            lines[i] = json.dumps(rec)
            path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
            return f"commands.jsonl step {seq} ({rec['name']}): {what}; every other line unchanged"
    raise SystemExit(f"bs3b_mutate: no step {seq} in {path}")


def driver_line(dest, change):
    path = dest / "preflight.console.txt"
    lines = path.read_text(encoding="utf-8").split("\n")
    hits = [i for i, x in enumerate(lines) if x.startswith("DRIVER RESULT ")]
    if len(hits) != 1:
        raise SystemExit(f"bs3b_mutate: {len(hits)} DRIVER RESULT lines in {path}")
    lines[hits[0]] = change(lines[hits[0]])
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    new = lines[hits[0]]
    return new[:72] + " ... " + new[new.index(" status="):]


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    variant, dest = argv[1], Path(argv[2])
    if not str(dest).startswith("/tmp/g3-s3b-bench/"):
        print("refused: <dest> must be under /tmp/g3-s3b-bench/")
        return 2
    att = dest / "attempts" / RID
    if not (att / "attempt.json").is_file():
        print(f"refused: {att} holds no attempt.json")
        return 2
    if variant == "unchanged":
        msg = "nothing changed"
    elif variant == "step7-exit1":
        def change(rec):
            old, rec["exit_code"] = rec["exit_code"], 1
            return f"exit_code {old} -> 1"
        msg = one_command(att, 7, change)
    elif variant == "no-attempt-json":
        (att / "attempt.json").unlink()
        msg = "attempt.json removed"
    elif variant in ("other-run-id", "other-run-id-dir"):
        line = driver_line(dest, lambda x: x.replace(f"DRIVER RESULT {RID}:", f"DRIVER RESULT {OTHER}:", 1))
        msg = f"the console's DRIVER RESULT line now reads: {line}"
        if variant == "other-run-id-dir":
            shutil.copytree(att, dest / "attempts" / OTHER, copy_function=shutil.copy2)
            msg += f"; a copy of the attempt directory is named {OTHER} (its attempt.json run_id is still {RID})"
        else:
            msg += f"; no attempt directory {OTHER} exists"
    elif variant == "collector-problem":
        path = att / "analysis/collector/collector-check.json"
        rep = json.loads(path.read_text(encoding="utf-8"))
        rep["problems"] = ["bench: egw-mongodb-1 has 3 forward gaps in its window (a problem listed by the check)"]
        dump(path, rep)
        msg = f"collector-check.json problems = {rep['problems']!r}"
    elif variant == "capture-failures":
        path = att / "attempt.json"
        a = json.loads(path.read_text(encoding="utf-8"))
        a["capture_failures"] = [{"step": "collector-live", "seq": 13,
                                  "note": "bench: the console capture of 'collector-live' was lost"}]
        dump(path, a)
        msg = f"attempt.json capture_failures = {a['capture_failures']!r}"
    elif variant == "capture-truncated":
        def change(rec):
            rec["capture"]["stdout"]["state"] = "truncated"
            return "capture.stdout.state complete -> truncated (bytes unchanged)"
        msg = one_command(att, 13, change)
    elif variant in ("system-fault", "system-fault-record", "reason-fault"):
        path = att / "attempt.json"
        a = json.loads(path.read_text(encoding="utf-8"))
        if variant != "reason-fault":
            a["system_outcome"] = "fail"
        a["reason"] = FAULT + a["reason"]
        dump(path, a)
        msg = f"attempt.json system_outcome={a['system_outcome']!r}, reason starts {a['reason'][:60]!r}"
        if variant == "system-fault":
            line = driver_line(dest, lambda x: x.replace(" system_outcome=inconclusive ", " system_outcome=fail ", 1))
            msg += f"; the console's DRIVER RESULT line now reads: {line}"
    else:
        print(f"unknown variant {variant}")
        return 2
    print(f"fixture variant {variant}: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
