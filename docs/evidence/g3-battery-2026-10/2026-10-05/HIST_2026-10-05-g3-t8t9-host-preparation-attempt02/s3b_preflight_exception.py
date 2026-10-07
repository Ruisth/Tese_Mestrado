"""Decide whether a failed preflight falls inside the authorised T8/T9 exception (2026-10-05).

Usage: s3b_preflight_exception.py <preflight attempt directory> <preflight driver console>

The exception was authorised by Rui on 2026-10-05 (output_test/decisions/
2026-10-05_g3-s3b-exception-authorisation.md), on the Project Manager's terms (register entry
"2026-10-05 12:09 WEST"): for ONE T8/T9 session, a preflight that ended exit 3 lets the session
go on only when the actual preflight attempt is identified and complete, all 15 other steps
ended 0, collector-check reports no problem, and a readable, consistent record shows that the
sole failure is the numeric duration judgement of collector-duration. Anything else halts.

It reads; it writes nothing and changes no verdict: the preflight stays failed and invalid.
One line per check is printed; the last line is either
    EXCEPTION APPLIES: ...      (exit 0)
or  EXCEPTION DOES NOT APPLY: ...  (exit 1)
Fails closed: a record that is missing, unreadable or not of the expected form is a refusal.
"""
import json
import re
import sys
from pathlib import Path

#: The frozen preflight's steps at 8e49261 (tools/session/preflight.sh, STEPS), in order.
STEPS = ("stack-start-interlock", "collector-copy", "collector-install", "deployed-tree-hashes",
         "deployed-vs-clone", "controller-health", "stack-health", "broker-secrets-check",
         "clock-offset", "guest-clock", "sut-environment", "sut-environment-fetch", "collector-live",
         "fetch-collector-output", "collector-check", "collector-duration")
#: The one step the exception covers.
EXCEPTED = "collector-duration"
#: preflight.sh's reason when collector-duration is its ONLY failed mandatory step, nothing was
#: observed (no 'observed system fault(s): ' prefix) and nothing was skipped (no 'not run: ').
REASON = ("the preflight ran, but mandatory instrumentation failed: the collector did not hold the "
          "duration it declares, or the shortfall could not be judged (see console/ and "
          "commands.jsonl); ")
SERVICES = ("egw-mosquitto-1", "egw-mongodb-1", "egw-ditto-policies-1", "egw-ditto-things-1",
            "egw-ditto-gateway-1", "egw-controller-1")
DECLARED_DURATION_S = 45.0
#: collector_shortfall.py's failing sentence for a READABLE report (its 'shortfall > tolerance'
#: branch); its other failing sentences say the shortfall is UNKNOWN and are refused.
SHORTFALL_LINE = re.compile(
    r"^the collector stopped (?P<short>[0-9.]+) s before the duration=(?P<dur>[0-9.]+)s its "
    r"'start:' line declares \(its own window is (?P<win>[0-9.]+) s\): the samples, the coverage "
    r"and the gaps were checked against that shorter window, not against the declared one\n?$")
DRIVER_LINE = re.compile(r"^DRIVER RESULT (?P<id>[^: ]+): exit=(?P<exit>\d+) .*$", re.M)

checks = []


def ok(what):
    checks.append(what)
    print("ok: " + what)


def refuse(why):
    print("EXCEPTION DOES NOT APPLY: " + why + " - the halt stands")
    sys.exit(1)


def num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def main(argv):
    if len(argv) != 3:
        print(__doc__.split("\n\n")[1])
        sys.exit(2)
    att, console = Path(argv[1]), Path(argv[2])

    # The actual attempt, identified by the driver's own last line.
    try:
        text = console.read_text(encoding="utf-8", errors="strict")
    except (OSError, ValueError) as exc:
        refuse(f"the preflight driver's console {console} could not be read ({exc})")
    lines = DRIVER_LINE.findall(text)
    if len(lines) != 1:
        refuse(f"the driver's console holds {len(lines)} 'DRIVER RESULT' lines, not exactly one")
    run_id, code = lines[0]
    if code != "3":
        refuse(f"the driver ended exit={code}: the exception covers exit 3 only")
    line = DRIVER_LINE.search(text).group(0)
    for want in ("status=failed", "instrumentation_validity=invalid", "system_outcome=inconclusive",
                 "export=exported"):
        if want not in line.split():
            refuse(f"the driver's result line does not say {want}: {line}")
    ok(f"driver result: {run_id} exit=3 failed, invalid, inconclusive, exported")
    if att.name != run_id or not att.is_dir():
        refuse(f"the attempt directory {att} is not the driver's attempt {run_id}")
    ok(f"attempt directory is the driver's: {att.name}")

    # The attempt record.
    try:
        a = json.loads((att / "attempt.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        refuse(f"attempt.json could not be read ({exc})")
    want = {"run_id": run_id, "scenario": "live preflight", "status": "failed",
            "instrumentation_validity": "invalid", "system_outcome": "inconclusive"}
    for k, v in want.items():
        if a.get(k) != v:
            refuse(f"attempt.json {k}={a.get(k)!r}, not {v!r}")
    if a.get("capture_failures") != []:
        refuse(f"attempt.json records capture failures: {a.get('capture_failures')!r}")
    if a.get("reason") != REASON:
        refuse("attempt.json's reason is not the frozen preflight's reason for collector-duration "
               f"as its only failed mandatory step, with nothing observed and nothing skipped: {a.get('reason')!r}")
    ok("attempt.json: failed, invalid, inconclusive; no capture failure; the only failed mandatory step is collector-duration; nothing observed, nothing skipped")

    # Every step, in order, complete; only collector-duration non-zero.
    try:
        cmds = [json.loads(x) for x in (att / "commands.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError) as exc:
        refuse(f"commands.jsonl could not be read ({exc})")
    names = tuple(c.get("name") for c in cmds)
    if names != STEPS:
        refuse(f"the steps are {list(names)}, not the frozen preflight's sixteen in order")
    for i, c in enumerate(cmds, 1):
        if c.get("seq") != i:
            refuse(f"step {c.get('name')} has seq {c.get('seq')}, not {i}")
        if c.get("killed_by_signal") is not None:
            refuse(f"step {c['name']} was killed by signal {c['killed_by_signal']}")
        want_rc = 1 if c["name"] == EXCEPTED else 0
        if c.get("exit_code") != want_rc:
            refuse(f"step {c['name']} ended {c.get('exit_code')}, not {want_rc}")
        cap = c.get("capture") or {}
        for stream in ("stdout", "stderr"):
            s = cap.get(stream) or {}
            if s.get("state") != "complete" or s.get("error") is not None or s.get("bytes_kept") != s.get("bytes_received"):
                refuse(f"step {c['name']}: its {stream} capture is not complete ({s!r})")
            f = att / str(c.get(stream) or "")
            if not c.get(stream) or not f.is_file() or f.stat().st_size != s.get("bytes_kept"):
                refuse(f"step {c['name']}: its {stream} file is missing or not the size recorded")
    ok("sixteen steps in the frozen order, each capture complete; fifteen ended 0, collector-duration ended 1")

    # collector-check: readable, no problem, six services.
    try:
        rep = json.loads((att / "analysis/collector/collector-check.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        refuse(f"analysis/collector/collector-check.json could not be read ({exc})")
    if rep.get("problems") != []:
        refuse(f"collector-check reports problems: {rep.get('problems')!r}")
    if rep.get("unexpected_names") != []:
        refuse(f"collector-check reports unexpected names: {rep.get('unexpected_names')!r}")
    rows = rep.get("rows_per_service")
    if not isinstance(rows, dict) or sorted(rows) != sorted(SERVICES) or not all(isinstance(v, int) and v > 0 for v in rows.values()):
        refuse(f"collector-check's rows per service are not the six services, each with rows: {rows!r}")
    for k in ("resource_validation", "closing_record_reconciliation"):
        if rep.get(k) != "run":
            refuse(f"collector-check {k}={rep.get(k)!r}, not 'run'")
    ok(f"collector-check: no problem, no unexpected name, six services ({min(rows.values())}-{max(rows.values())} rows each)")

    # The sole failure is the numeric duration judgement, on a readable, consistent report.
    dur, win, short = num(rep.get("declared_duration_s")), num(rep.get("window_seconds")), num(rep.get("declared_duration_shortfall_s"))
    if dur != DECLARED_DURATION_S or win is None or short is None or win <= 0 or short <= 0:
        refuse(f"the report's declared duration, window or shortfall is not usable (duration={dur}, window={win}, shortfall={short})")
    if abs((dur - win) - short) > 1e-6:
        refuse(f"the report is not consistent: duration {dur:g} - window {win:g} != shortfall {short:g}")
    try:
        out = (att / "console/016-collector-duration.stdout.txt").read_text(encoding="utf-8")
        err = (att / "console/016-collector-duration.stderr.txt").read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        refuse(f"collector-duration's console could not be read ({exc})")
    m = SHORTFALL_LINE.match(out)
    if not m or err != "":
        refuse(f"collector-duration's console is not the numeric shortfall judgement alone: {out!r} / stderr {err!r}")
    if (float(m["short"]), float(m["dur"]), float(m["win"])) != (short, dur, win):
        refuse("collector-duration's sentence does not carry the report's own numbers")
    ok(f"collector-duration failed on the numeric judgement alone: window {win:g} s of the declared {dur:g} s, shortfall {short:g} s (UTC stamps; not a measured early stop)")

    print(f"EXCEPTION APPLIES: preflight {run_id} stays failed and invalid; the session proceeds under the "
          f"authorised T8/T9 exception (collector-duration only: UTC window {win:g} s of {dur:g} s declared)")
    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv)
