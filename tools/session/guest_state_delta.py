"""Compare the guest's container state before and after a measured run.

Usage: guest_state_delta.py [--expect NAME[,NAME...]]
                           <guest-state-before stdout> <guest-state-after stdout>

The two console records are written by the identical `guest-state` command of
`nominal.sh`, which prints one line per container

    container <name> oomkilled=<true|false> restarts=<n> id=<container id> started=<instant>

and one line with the kernel's own count for this boot

    memory-cgroup OOM lines: <n>

Every field of that line is REQUIRED, and `unknown` is not a value: the id is
what shows a container object that was replaced, and the instant it last
started is what shows one that was restarted IN PLACE, which changes neither
the id nor the restart count (Docker increments `RestartCount` from the restart
POLICY, not from an explicit `docker restart`). A record that does not carry
them, or carries them twice for one container, leaves those two facts
unknowable and is a problem of its own, never a pair that quietly compares
equal.

The two records are judged as a PAIR, in both directions and in both senses,
and what they say is reported in two groups, because observing the system fail
is a RESULT while failing to observe is an invalid measurement:

* FAULTS - what the system did: a container that was OOM-killed, one that
  restarted during the measured window (by its count or by its start instant),
  one that was REPLACED during it (a recreated container object carries a new
  id and starts again at restart count 0, so the OOM and restart history the
  'before' record holds is lost with the old object), one that is gone after
  the run, one that appears only after it, and the kernel's own memory-cgroup
  OOM lines. The pilot has already lost a run to a Ditto OOM: these are facts
  about the run, not notes, and they are not a defect of the measurement.
* PROBLEMS - what the records do not let anyone say: a record that cannot be
  read, a container line the pattern cannot read, a container named twice, a
  missing or `unknown` id or start instant, a restart count that is not an
  integer, an unreadable OOM-line count, and a BEFORE record that does not name
  every container the caller expects - which is a gap in the baseline of each
  of those containers, and never also a fault observed about one of them (in
  the AFTER record that same silence is the fault "gone after the run").

Every finding is printed under its own heading and names the container it is
about, and the LAST line of every exit is the summary
`guest-state-delta: faults=N problems=M`. The exit status is 0 (the pair could
be compared and there is nothing to report), 1 (it could be compared and at
least one fault was observed: a result) or 2 (the records could not be
compared; any fault seen all the same is printed too). A failure of the
comparison ITSELF is 2 as well, never the 1 Python leaves for an unhandled
exception, which is the status of a fault the pair SHOWED: a helper that
crashed must not reach its caller as a fault nobody observed, with the real
evidence failure hidden behind it. The summary line is what tells a status this
helper reached from one it did not, and a caller reads no verdict without it.
"""
import re
import sys
import traceback

USAGE = ("usage: guest_state_delta.py [--expect NAME[,NAME...]] "
         "<guest-state-before stdout> <guest-state-after stdout>")

CONTAINER = re.compile(r"^container (?P<name>\S+) oomkilled=(?P<oom>\S+) "
                       r"restarts=(?P<restarts>\S+)(?: id=(?P<id>\S+))?"
                       r"(?: started=(?P<started>\S+))?$")
NAMED = re.compile(r"^container(?: (?P<name>\S+))?")
OOM_LINES = re.compile(r"^memory-cgroup OOM lines: (?P<count>\S+)$")

#: The two groups a finding belongs to: what the system did, and what the
#: records do not let anyone say.
FAULT = "fault"
PROBLEM = "problem"


def read(path, label, expected, faults, problems):
    """(containers, OOM line count) of one guest-state record."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        problems.append(f"the guest state {label} the run could not be read: {exc}")
        return {}, None
    containers = {}
    for line in (raw.strip() for raw in lines):
        match = CONTAINER.match(line)
        if match:
            name = match.group("name")
            if name in containers:
                # Two lines for one container: the last one used to win, so a
                # record naming it OOM-killed first could be overwritten by a
                # later line saying it was not.
                problems.append(f"the guest state {label} the run names {name} more than "
                                f"once: which line is its state cannot be decided")
                continue
            fields = {}
            for field in ("id", "started"):
                fields[field] = match.group(field)
                if not fields[field] or fields[field] == "unknown":
                    problems.append(f"the guest state {label} the run does not name the "
                                    f"{field} of {name} ({match.group(field) or 'no field'}): a "
                                    "container object that was replaced, or one that was "
                                    "restarted in place, could not be seen")
                    # A field the record does not carry is kept as nothing at
                    # all, never as the word 'unknown': compared with the real
                    # id or instant on the other side it would otherwise read
                    # as a replacement or a restart the run never showed, and
                    # an indeterminate reading is not an observation.
                    fields[field] = None
            containers[name] = (match.group("oom"), match.group("restarts"),
                                fields["id"], fields["started"])
            continue
        broken = NAMED.match(line)
        if broken:
            # A line 'docker inspect' left half-written names its container
            # even when the pattern cannot read it: it is a problem about that
            # container, never a line that quietly disappears from both sides.
            problems.append(f"the guest state {label} the run holds a container line that "
                            f"cannot be read ({broken.group('name') or 'no name given'}): {line!r}")
    if not containers:
        problems.append(f"the guest state {label} the run names no container")
    missing = [name for name in expected if name not in containers]
    if missing:
        # In the AFTER record an expected container that is not named is a
        # container that is gone: a fact about the run. In the BEFORE record it
        # leaves that container's state unknowable, which is a problem. A
        # record that names NO container at all - one that could not be read,
        # or one a guest command left empty - shows neither: a record nobody
        # could read shows nothing, and no container is reported gone out of it.
        note = (f"the guest state {label} the run names {len(expected) - len(missing)} "
                f"of the {len(expected)} expected containers (missing: "
                f"{', '.join(missing)})")
        (faults if label == "after" and containers else problems).append(note)
    counts = [match.group("count") for match in
              (OOM_LINES.match(line.strip()) for line in lines) if match]
    if len(counts) != 1 or not counts[0].isdigit():
        problems.append(f"the guest state {label} the run holds no readable "
                        f"memory-cgroup OOM count ({', '.join(counts) or 'none'})")
        return containers, None
    return containers, int(counts[0])


def container_findings(name, was, now, expected=()):
    """What the pair of records says about one container, in both senses.

    Each finding is a pair (group, sentence): ``FAULT`` for what the system
    did, ``PROBLEM`` for what the two records do not let anyone say. ``expected``
    is the caller's list of containers the BEFORE record was supposed to name:
    one of those that it does not name is a gap in the baseline, never also a
    fault positively observed about that container.
    """
    if now is None:
        return [(FAULT, f"{name} was running before the run and is not listed after it")]
    oom, restarts, identity, started = now
    findings = []
    if oom == "true":
        findings.append((FAULT, f"{name} was OOM-killed (OOMKilled={oom})"))
    elif oom != "false":
        findings.append((PROBLEM, f"{name} has no readable OOMKilled state after the run "
                                  f"(OOMKilled={oom})"))
    if was is None:
        if name in expected:
            # `read` has already reported that the BEFORE record does not name
            # every expected container, and this is one of them: the baseline
            # for it is missing. Saying ALSO that it "was not running before
            # the run" would report as positively observed about this container
            # what is only a record that does not say.
            findings.append((PROBLEM, f"{name} is not named in the guest state before the run, so "
                                      "it has no restart baseline and nothing about it was "
                                      "compared"))
        else:
            findings.append((FAULT, f"{name} was not running before the run: there is no restart "
                                    "baseline for it"))
        return findings
    was_oom, was_restarts, was_identity, was_started = was
    replaced = (f"{name} was replaced during the run: %s, so its OOM and restart history "
                "was reset with the old container object")
    new_object = bool(was_identity and identity and was_identity != identity)
    if new_object:
        findings.append((FAULT, replaced % f"the container id changed ({was_identity[:12]} -> "
                                           f"{identity[:12]})"))
    if was_started and started and was_started != started:
        # The one signal an in-place restart leaves: 'docker restart' keeps the
        # container object (same id) and does not touch RestartCount, which
        # Docker increments from the restart POLICY, so without this the two
        # records are identical.
        findings.append((FAULT, f"{name} was restarted during the run: it started again at "
                                f"{started} (it had been running since {was_started})"))
    if not was_restarts.isdigit() or not restarts.isdigit():
        findings.append((PROBLEM, f"{name} has no readable restart count (before {was_restarts}, "
                                  f"after {restarts})"))
    elif int(restarts) > int(was_restarts):
        findings.append((FAULT, f"{name} restarted during the run ({was_restarts} -> {restarts})"))
    elif int(restarts) < int(was_restarts) and not new_object:
        # A count that fell with no id to prove it: the container object was
        # recreated all the same, because a restart count never decreases.
        findings.append((FAULT, replaced % f"the restart count went {was_restarts} -> {restarts}"))
    if was_oom == "true" and oom == "false":
        findings.append((FAULT, f"{name} was OOM-killed before the run and is not after it: the "
                                "container object was replaced and its OOM history lost"))
    return findings


def compare(before_path, after_path, expected=()):
    """(faults, problems) of the two records, most concrete first."""
    faults, problems = [], []
    before, oom_before = read(before_path, "before", expected, faults, problems)
    after, oom_after = read(after_path, "after", expected, faults, problems)
    if before and after:
        for name in sorted(set(before) | set(after)):
            for group, sentence in container_findings(name, before.get(name), after.get(name),
                                                      expected):
                (faults if group == FAULT else problems).append(sentence)
    else:
        # One side names no container at all. `read` has already said so; what
        # must NOT follow from it is one "gone after the run" per container the
        # other side names, or one "no restart baseline" per container this one
        # does: a record nobody could read shows nothing, and an absence of
        # observation is never an observation of absence.
        side = "before" if not before else "after"
        problems.append(f"the guest state {side} the run shows no container at all, so no "
                        "container of the pair could be compared: none is reported as gone "
                        "after the run, and none as new since it")
    if oom_after is None or oom_before is None:
        problems.append("the memory-cgroup OOM state of this boot is UNKNOWN, which is not 'no OOM'")
    elif oom_after:
        grew = f"{oom_before} before, {oom_after} after"
        faults.append(f"the kernel reports memory-cgroup OOM lines in this boot ({grew})")
    elif oom_before:
        problems.append(f"the kernel reported {oom_before} memory-cgroup OOM line(s) before the "
                        f"run and {oom_after} after it: the record of this boot is not consistent")
    return faults, problems


def parse(argv):
    """The expected container names and the two records."""
    expected, rest = [], list(argv)
    while rest and rest[0].startswith("-"):
        option = rest.pop(0)
        if option == "--":
            break
        if option != "--expect" or not rest:
            print(f"UNKNOWN OPTION {option}\n{USAGE}", file=sys.stderr)
            return None
        expected = [name for name in rest.pop(0).split(",") if name]
    if len(rest) != 2:
        print(USAGE, file=sys.stderr)
        return None
    return expected, rest[0], rest[1]


def main(argv):
    parsed = parse(argv)
    if parsed is None:
        # The comparison was never made at all, which is not "no fault". Its
        # summary line is printed here as well, because every exit of this
        # helper carries one: a caller that does not find it knows that what it
        # is reading is not a verdict this helper reached.
        print("PROBLEM: the arguments could not be read, so no pair was compared")
        print("guest-state-delta: faults=0 problems=1")
        return 2
    expected, before_path, after_path = parsed
    faults, problems = compare(before_path, after_path, expected)
    print("## faults: what the system did during the measured run")
    for fault in faults:
        print(f"FAULT: {fault}")
    if not faults:
        print("none")
    print("## problems: what the two records do not let anyone say")
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if not problems:
        print("none")
    print(f"guest state before/after: {len(faults)} fault(s), {len(problems)} problem(s)")
    print(f"guest-state-delta: faults={len(faults)} problems={len(problems)}")
    if problems:
        return 2
    return 1 if faults else 0


def run(argv):
    """:func:`main`, with a failure of the comparison ITSELF ending 2.

    Python leaves 1 for an unhandled exception, and 1 is the status of a fault
    the pair showed: without this, a crash of this helper would be recorded by
    its caller as a system fault that was never observed, and the evidence
    failure behind it would be lost. Here it is what it is - the pair could not
    be compared - and it carries the same summary line as every other exit.
    """
    try:
        return main(argv)
    except Exception as exc:  # noqa: BLE001 - any failure here is a pair NOT compared
        traceback.print_exc()
        print(f"PROBLEM: the comparison itself failed ({type(exc).__name__}: {exc}), "
              "so the two records were not compared")
        print("guest-state-delta: faults=0 problems=1")
        return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
