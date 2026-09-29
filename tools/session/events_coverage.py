"""Whether a proof run's continuous Docker events capture covers the run.

Usage: events_coverage.py DIR --run-t0 GUEST_EPOCH [--expected ACTION[,ACTION...]]
                          [--container NAME]

DIR holds what the docker-events fetch of proof_fetch_sut_log.sh brought back
from the guest's capture directory (/tmp/egw-events-RUN_ID) after it stopped
the recorder unit (proof_events_recorder.sh, started by proof.sh before the
workload and the fault):

    events.jsonl     the events the recorder captured, one JSON object per line
    lifecycle.txt    the recorder's transitions ('start', 'cli-start',
                     'cli-exit') and the start step's 'ready'
    start-facts.txt  the guest's boot_id and the docker unit's MainPID and
                     ExecMainStartTimestampMonotonic when the recorder started
    cli.stderr       what the events CLI said on stderr
    stop.txt         what the stop script printed: the stop requested
                     (stop_requested_guest_epoch), the unit's state before
                     it, the same boot and daemon facts, the unit's state
                     after it

A FILE THAT EXISTS, OR AN EXIT STATUS OF 0, IS NOT COVERAGE. The capture is
COMPLETE only when every rule below holds; one that is broken makes it
INCOMPLETE, and one that cannot be judged from what was fetched (a file
absent or unreadable, a fact not printed) makes it UNKNOWN unless another is
broken. Nothing is guessed, and no threshold is invented:

  R1  the recorder started, started its CLI and was found ready, each once,
      and it was ready no later than RUN_T0 (the guest epoch the driver
      recorded at readiness, which bounds the run's window from below)
  R2  one guest boot and one docker daemon throughout: the boot_id, the
      daemon's MainPID (non-zero) and its start stamp are the same at the
      start and at the stop (a daemon restarted under live-restore leaves the
      containers' StartedAt unchanged, so this is read from systemd)
  R3  the unit was active when the stop was requested, and the recorder
      wrote exactly one end of its CLI, with the stop requested, no earlier
      than the request (within the guest clock's 3 s step band): a CLI that
      ended by itself - even with status 0, which the CLI answers when the
      daemon closes the stream - is a break
  R4  the CLI said nothing on stderr
  R5  a closing witness: an event of the stream stamped AFTER the second in
      which the stop was requested (timeNano at or past the request epoch
      plus one second), so the subscription was live past the window's end
  R6  every line of the capture is a JSON object with an integer timeNano
  R7  only when the scenario expects them (--expected, which the driver
      passes for the fault it issues and never for a fault-free run): each
      expected action of the container (kill with signal 9, die, start...)
      is captured within [RUN_T0, the stop request]

The largest gap between two consecutive events within the window is
reported (the containers' healthcheck exec events are the stream's
heartbeat); it decides nothing.

EVERY INSTANT HERE IS THE GUEST'S: the epochs the recorder, the start step
and the stop script read with 'date +%s', and the daemon's own timeNano. No
host instant is read or printed (the host's instants of the fetch are in the
manifest's hook record, apart).

Output: 'key=value' lines on stdout (the hook keeps them as
logs/sut/docker-events.coverage.txt), the first 'coverage=complete|
incomplete|unknown', then the requested interval on the guest clock, the
provenance, one 'rule_RN=held|broken|unknown|not-required: ...' line per
rule and one 'reason=...' line per rule not held. Exit status: 0 complete,
1 incomplete, 2 unknown - a failure of the checker itself included, which is
never read as a capture that was judged.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

USAGE = ("usage: events_coverage.py DIR --run-t0 GUEST_EPOCH [--expected ACTION[,ACTION...]] "
         "[--container NAME]")
NS = 1_000_000_000
HELD, BROKEN, UNKNOWN, NOT_REQUIRED = "held", "broken", "unknown", "not-required"
LIFECYCLE_EVENTS = ("start", "cli-start", "ready", "cli-exit")
DAEMON_FACTS = ("boot_id", "MainPID", "ExecMainStartTimestampMonotonic")
# The signal the proof's fault sends (SIGKILL): docker records it on the
# kill event as the attribute 'signal'.
KILL_SIGNAL = "9"
# The guest's wall clock is stepped backwards by 2-3 s about every 30 s on
# this host (proof.sh's HEALTHY_RULE_PY and the evaluator apply the same
# band): the end of the CLI, read a moment after the stop request, may read
# up to that much earlier than it and still be the end BY that stop.
CLOCK_STEP_BAND_S = 3


class Unreadable(Exception):
    """A file of the capture that could not be read."""


def utc(epoch: int | float | None) -> str:
    """A guest epoch as UTC text (arithmetic on the recorded number, never a
    clock reading)."""
    if epoch is None:
        return "null"
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Unreadable(f"{path.name}: {type(exc).__name__}: {exc}") from None


def key_values(text: str) -> dict[str, str]:
    """'key=value' lines (the first value of a key wins; other lines are
    ignored)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and key not in out:
            out[key] = value
    return out


def lifecycle(text: str) -> dict[str, list[dict[str, str]]]:
    """The lifecycle lines, by event: each line is 'EVENT key=value...'."""
    out: dict[str, list[dict[str, str]]] = {name: [] for name in LIFECYCLE_EVENTS}
    for line in text.splitlines():
        words = line.split()
        if not words or words[0] not in out:
            continue
        fields = {}
        for word in words[1:]:
            key, sep, value = word.partition("=")
            if sep:
                fields[key] = value
        out[words[0]].append(fields)
    return out


def whole(text: str | None) -> int | None:
    return int(text) if text is not None and re.fullmatch(r"[0-9]+", text) else None


def attributes(event: dict) -> dict:
    actor = event.get("Actor")
    attrs = actor.get("Attributes") if isinstance(actor, dict) else None
    return attrs if isinstance(attrs, dict) else {}


def judge(directory: Path, run_t0: int, expected: list[str], container: str) -> tuple[str, list[str]]:
    rules: dict[str, tuple[str, str]] = {}
    facts: list[str] = []

    def load(name: str):
        try:
            return read_text(directory / name)
        except Unreadable as exc:
            return exc

    events_text = load("events.jsonl")
    life_text = load("lifecycle.txt")
    start_text = load("start-facts.txt")
    stderr_text = load("cli.stderr")
    stop_text = load("stop.txt")

    life = lifecycle(life_text) if isinstance(life_text, str) else None
    stop = key_values(stop_text) if isinstance(stop_text, str) else None
    t1 = whole(stop.get("stop_requested_guest_epoch")) if stop is not None else None

    # R6 first: the events every other rule reads.
    events: list[dict] = []
    malformed: list[int] = []
    if isinstance(events_text, Unreadable):
        rules["R6"] = (UNKNOWN, f"the capture could not be read ({events_text})")
    else:
        for number, line in enumerate(events_text.splitlines(), 1):
            try:
                event = json.loads(line)
            except ValueError:
                event = None
            if not isinstance(event, dict) or not isinstance(event.get("timeNano"), int) \
                    or isinstance(event.get("timeNano"), bool):
                malformed.append(number)
                continue
            events.append(event)
        if malformed:
            rules["R6"] = (BROKEN, f"{len(malformed)} line(s) of the capture are not a JSON object with an integer "
                                   f"timeNano (first: line {malformed[0]})")
        elif not events:
            rules["R6"] = (BROKEN, "the capture holds no event at all")
        else:
            rules["R6"] = (HELD, f"all {len(events)} line(s) are JSON objects with an integer timeNano")
    facts.append("events_lines=" + ("unreadable" if isinstance(events_text, Unreadable)
                                    else str(len(events) + len(malformed))))

    # R1: started, CLI started, ready - each once - and ready no later than RUN_T0.
    if life is None:
        rules["R1"] = (UNKNOWN, f"the lifecycle record could not be read ({life_text})")
    else:
        counts = {name: len(life[name]) for name in ("start", "cli-start", "ready")}
        wrong = [f"{name} x{n}" for name, n in counts.items() if n != 1]
        if wrong:
            rules["R1"] = (BROKEN, "the recorder's start, CLI start and readiness are not each recorded once: "
                                   + ", ".join(wrong))
        else:
            ready = whole(life["ready"][0].get("epoch"))
            start = whole(life["start"][0].get("epoch"))
            facts += [f"recorder_start_guest_epoch={start if start is not None else 'null'}",
                      f"recorder_since_guest_epoch={life['start'][0].get('since', 'null')}",
                      f"ready_guest_epoch={ready if ready is not None else 'null'}"]
            if ready is None:
                rules["R1"] = (UNKNOWN, "the readiness line carries no guest epoch")
            elif ready > run_t0:
                rules["R1"] = (BROKEN, f"the recorder was ready at {ready} ({utc(ready)}), after RUN_T0 {run_t0} "
                                       f"({utc(run_t0)}): the window's start was not covered")
            else:
                rules["R1"] = (HELD, f"started, CLI started and ready once; ready at {ready} ({utc(ready)}), "
                                     f"no later than RUN_T0 {run_t0}")

    # R2: one boot and one daemon from the start to the stop.
    begin = key_values(start_text) if isinstance(start_text, str) else None
    if begin is None or stop is None:
        missing = [name for name, text in (("start-facts.txt", start_text), ("stop.txt", stop_text))
                   if not isinstance(text, str)]
        rules["R2"] = (UNKNOWN, "the boot and daemon facts could not be read (" + ", ".join(missing) + ")")
    else:
        absent = [f"{fact} ({where})" for where, doc in (("start", begin), ("stop", stop))
                  for fact in DAEMON_FACTS if not doc.get(fact)]
        changed = [f"{fact} {begin[fact]} -> {stop[fact]}" for fact in DAEMON_FACTS
                   if begin.get(fact) and stop.get(fact) and begin[fact] != stop[fact]]
        stopped = [where for where, doc in (("start", begin), ("stop", stop)) if doc.get("MainPID") == "0"]
        facts += [f"{where}_{fact}={doc.get(fact) or 'null'}"
                  for where, doc in (("start", begin), ("stop", stop)) for fact in DAEMON_FACTS]
        if changed or stopped:
            rules["R2"] = (BROKEN, "the guest boot or the docker daemon changed during the capture ("
                                   + "; ".join(changed + [f"MainPID 0 at the {w}: no daemon" for w in stopped]) + ")")
        elif absent:
            rules["R2"] = (UNKNOWN, "the boot and daemon facts are not all recorded: " + ", ".join(absent))
        else:
            rules["R2"] = (HELD, f"one boot ({begin['boot_id']}) and one docker daemon (MainPID {begin['MainPID']}, "
                                 f"start stamp {begin['ExecMainStartTimestampMonotonic']}) from start to stop")

    # R3: active at the stop request, and one end of the CLI, by that stop.
    if life is None or stop is None:
        rules["R3"] = (UNKNOWN, "the lifecycle record or the stop record could not be read")
    else:
        state = stop.get("unit_state_before_stop")
        exits = life["cli-exit"]
        facts += [f"stop_requested_guest_epoch={t1 if t1 is not None else 'null'}",
                  f"unit_state_before_stop={state or 'null'}",
                  f"unit_state_after_stop={stop.get('unit_state_after_stop') or 'null'}"]
        facts += [f"cli_exit=epoch={e.get('epoch', 'null')} rc={e.get('rc', 'null')} "
                  f"stop_requested={e.get('stop_requested', 'null')}" for e in exits]
        self_ended = [e for e in exits if e.get("stop_requested") != "yes"]
        if t1 is None or state is None:
            rules["R3"] = (UNKNOWN, "the stop record does not say when the stop was requested or the unit's state then")
        elif self_ended:
            e = self_ended[0]
            rules["R3"] = (BROKEN, f"the events CLI ended by itself (epoch {e.get('epoch')}, exit {e.get('rc')}), "
                                   "without a stop passed to it: the stream was broken there, whatever its exit status")
        elif state != "active":
            rules["R3"] = (BROKEN, f"the recorder unit was '{state}', not active, when the stop was requested")
        elif len(exits) != 1:
            rules["R3"] = (BROKEN, f"the recorder wrote {len(exits)} end(s) of its CLI, not one"
                                   + (" (none: its end by the stop is not recorded)" if not exits else ""))
        elif whole(exits[0].get("epoch")) is None:
            rules["R3"] = (UNKNOWN, "the end of the CLI carries no guest epoch")
        elif whole(exits[0]["epoch"]) < t1 - CLOCK_STEP_BAND_S:
            rules["R3"] = (BROKEN, f"the CLI's end ({exits[0]['epoch']}) precedes the stop request ({t1}) by more than "
                                   f"the guest clock's step band of {CLOCK_STEP_BAND_S} s")
        elif exits[0].get("cli_started") == "no":
            rules["R3"] = (BROKEN, "the stop arrived before the CLI was started")
        else:
            rules["R3"] = (HELD, f"active when the stop was requested at {t1} ({utc(t1)}); one end of the CLI, "
                                 f"by that stop, at {exits[0]['epoch']}")

    # R4: the CLI said nothing on stderr.
    if isinstance(stderr_text, Unreadable):
        rules["R4"] = (UNKNOWN, f"the CLI's stderr could not be read ({stderr_text})")
    elif stderr_text.strip():
        first = stderr_text.strip().splitlines()[0][:200]
        rules["R4"] = (BROKEN, f"the events CLI wrote to stderr: {first!r}")
    else:
        rules["R4"] = (HELD, "the CLI's stderr is empty")

    # R5: a closing witness past the second of the stop request.
    latest = max((e["timeNano"] for e in events), default=None)
    facts.append(f"latest_event_guest_epoch={latest // NS if latest is not None else 'null'}")
    if t1 is None:
        rules["R5"] = (UNKNOWN, "the stop request's epoch is not recorded, so no closing witness can be judged")
    elif isinstance(events_text, Unreadable):
        rules["R5"] = (UNKNOWN, "the capture could not be read")
    elif latest is not None and latest >= (t1 + 1) * NS:
        rules["R5"] = (HELD, f"an event at {latest // NS} ({utc(latest // NS)}), after the second of the stop request "
                             f"({t1}): the subscription was live past the window's end")
    else:
        rules["R5"] = (BROKEN, f"no event is stamped after the second of the stop request ({t1}, {utc(t1)}): the "
                               "subscription is not shown live to the window's end")

    # The window [RUN_T0, the stop request], and the heartbeat gap (report only).
    window = [e for e in events if run_t0 * NS <= e["timeNano"] and (t1 is None or e["timeNano"] < (t1 + 1) * NS)]
    stamps = [e["timeNano"] for e in window]
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    facts += [f"events_in_window={len(window)}",
              f"first_event_in_window_utc={utc(stamps[0] // NS) if stamps else 'null'}",
              f"last_event_in_window_utc={utc(stamps[-1] // NS) if stamps else 'null'}",
              f"max_gap_in_window_s={round(max(gaps) / NS, 3) if gaps else 'null'}",
              "max_gap_note=reported only: no threshold is applied to it"]

    # R7: the expected fault events, only when the scenario expects them.
    if not expected:
        rules["R7"] = (NOT_REQUIRED, "no fault event is expected of this run (none was passed)")
    elif t1 is None or isinstance(events_text, Unreadable):
        rules["R7"] = (UNKNOWN, "the window's end or the capture is not readable, so the expected events cannot be sought")
    else:
        found, lacking = [], []
        for action in expected:
            hits = [e for e in window
                    if e.get("Type", "container") == "container" and e.get("Action") == action
                    and attributes(e).get("name") == container
                    and (action != "kill" or str(attributes(e).get("signal")) == KILL_SIGNAL)]
            if hits:
                found.append(f"{action}@{utc(hits[0]['timeNano'] // NS)}")
            else:
                lacking.append(action + (f" (signal {KILL_SIGNAL})" if action == "kill" else ""))
        facts.append("expected_found=" + (",".join(found) or "none"))
        if lacking:
            rules["R7"] = (BROKEN, f"the expected event(s) {', '.join(lacking)} of {container} are not captured within "
                                   f"[{run_t0}, {t1}]")
        else:
            rules["R7"] = (HELD, f"every expected event of {container} is captured within the window: " + ", ".join(found))

    order = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
    states = [rules[r][0] for r in order]
    if BROKEN in states:
        verdict = "incomplete"
    elif UNKNOWN in states:
        verdict = "unknown"
    else:
        verdict = "complete"
    lines = [f"coverage={verdict}",
             f"requested_since_guest_epoch={run_t0}", f"requested_since_utc={utc(run_t0)}",
             f"requested_until_guest_epoch={t1 if t1 is not None else 'null'}",
             f"requested_until_utc={utc(t1)}",
             "requested_until_note=the stop request of the docker-events fetch, which runs after the drain and "
             "the post-drain copy",
             "provenance=docker events --since <recorder since> --filter type=container --format {{json .}}, "
             "subscribed by the recorder unit (proof_events_recorder.sh) before RUN_T0 and meant to be followed to "
             "its stop, not a history query; whether it was followed throughout is the verdict and the rules below",
             "clock=guest: every epoch here is the guest's date +%s or the daemon's timeNano; no host instant",
             "expected=" + (",".join(expected) if expected else "none"),
             f"container={container}"]
    lines += facts
    lines += [f"rule_{r}={rules[r][0]}: {rules[r][1]}" for r in order]
    lines += [f"reason={r} {rules[r][0]}: {rules[r][1]}" for r in order if rules[r][0] in (BROKEN, UNKNOWN)]
    return verdict, lines


def main(argv: list[str]) -> int:
    args = list(argv)
    directory = run_t0 = None
    expected: list[str] = []
    container = "egw-controller-1"
    while args:
        arg = args.pop(0)
        if arg in ("--run-t0", "--expected", "--container") and args:
            value = args.pop(0)
            if arg == "--run-t0":
                run_t0 = whole(value)
                if run_t0 is None:
                    print(f"coverage=unknown\nreason=usage: --run-t0 {value!r} is not a whole number of seconds")
                    return 2
            elif arg == "--expected":
                expected = [a for a in value.split(",") if a]
                if not all(re.fullmatch(r"[a-z_]+", a) for a in expected):
                    print(f"coverage=unknown\nreason=usage: --expected {value!r} is not a comma list of actions")
                    return 2
            else:
                container = value
        elif directory is None and not arg.startswith("-"):
            directory = Path(arg)
        else:
            print(f"coverage=unknown\nreason={USAGE}")
            return 2
    if directory is None or run_t0 is None:
        print(f"coverage=unknown\nreason={USAGE}")
        return 2
    verdict, lines = judge(directory, run_t0, expected, container)
    print("\n".join(lines))
    return {"complete": 0, "incomplete": 1}.get(verdict, 2)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as exc:  # the checker's own failure is no judgement of the capture
        print(f"coverage=unknown\nreason=the checker itself failed: {type(exc).__name__}: {exc}")
        sys.exit(2)
