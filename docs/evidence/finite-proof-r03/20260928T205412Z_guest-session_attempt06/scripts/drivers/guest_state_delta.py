"""Compare the guest's container state before and after a measured run.

Usage: guest_state_delta.py [--expect NAME[,NAME...]] [--expect-restarted NAME]...
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

A driver that itself restarts a container during the measured run - the proof
session of ADR 0011 kills the controller's container and starts it again -
names that container with `--expect-restarted NAME` (repeatable), and then the
pair is read in a third group as well:

* EXPECTED RESTARTS - the one in-place restart of a container so named, when it
  is the ONLY thing the pair shows about that container: the same container
  object (the id), a start instant that is LATER, a restart count that did not
  move and no OOM kill on either side. It is printed under its own heading as
  `EXPECTED-RESTART` and is not a fault. That is all the option changes: a
  named container the pair shows anything else about - an OOM kill, a
  replacement, a restart count that moved - keeps every fault exactly as it
  would without the option, and every other container is judged as without it.
  A named container the pair shows NO restart of at all (the same start instant
  on both sides, not named on one side or on either, or two start instants that
  cannot be read and ordered) is a PROBLEM: an expectation the pair does not
  confirm is never satisfied by silence.

Every finding is printed under its own heading and names the container it is
about, and the LAST line of every exit is the summary
`guest-state-delta: faults=N problems=M`. The exit status is 0 (the pair could
be compared and there is nothing to report; an expected restart is not
something to report), 1 (it could be compared and at least one fault was
observed: a result) or 2 (the records could not be compared; any fault seen
all the same is printed too). A failure of the
comparison ITSELF is 2 as well, never the 1 Python leaves for an unhandled
exception, which is the status of a fault the pair SHOWED: a helper that
crashed must not reach its caller as a fault nobody observed, with the real
evidence failure hidden behind it. The summary line is what tells a status this
helper reached from one it did not, and a caller reads no verdict without it.
"""
import re
import sys
import traceback

USAGE = ("usage: guest_state_delta.py [--expect NAME[,NAME...]] [--expect-restarted NAME]... "
         "<guest-state-before stdout> <guest-state-after stdout>")

CONTAINER = re.compile(r"^container (?P<name>\S+) oomkilled=(?P<oom>\S+) "
                       r"restarts=(?P<restarts>\S+)(?: id=(?P<id>\S+))?"
                       r"(?: started=(?P<started>\S+))?$")
NAMED = re.compile(r"^container(?: (?P<name>\S+))?")
OOM_LINES = re.compile(r"^memory-cgroup OOM lines: (?P<count>\S+)$")

#: A start instant as `docker inspect` prints `State.StartedAt`: RFC 3339 in
#: UTC, with up to nine fractional digits and the trailing zeros trimmed.
INSTANT = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}:\d{2})"
                     r"(?:\.(?P<fraction>\d{1,9}))?Z$")

#: The three groups a finding belongs to: what the system did, what the
#: records do not let anyone say, and what the caller said the run would do to
#: a container and the pair shows it did.
FAULT = "fault"
PROBLEM = "problem"
EXPECTED = "expected-restart"


def instant(text):
    """A key that orders one start instant against another, or None.

    Two instants the pattern reads compare as they are in time, because every
    part of the key has a fixed width once the fraction is padded to the nine
    digits Docker trims. One it cannot read has no order: a caller that needs
    "later" must then say the order could not be decided, never guess it.
    """
    match = INSTANT.match(text or "")
    if not match:
        return None
    return match.group("date"), match.group("time"), (match.group("fraction") or "").ljust(9, "0")


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


def restarted_in_place(name, started, was_started):
    """The one sentence of a restart that kept the container object.

    It is the fault `container_findings` reports for a start instant that
    moved, and the one finding `expected_restart` may take out of the faults:
    the sentence lives here so that the two never drift apart.
    """
    return (f"{name} was restarted during the run: it started again at {started} "
            f"(it had been running since {was_started})")


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
        findings.append((FAULT, restarted_in_place(name, started, was_started)))
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


def expected_restart(name, was, now, findings):
    """The findings of one container the caller expects restarted IN PLACE.

    The pair must show exactly that and nothing else about the container: the
    same object (the id), a start instant that is later, a restart count that
    did not move and no OOM kill on either side. Then the one fault the restart
    would be is returned as ``EXPECTED`` instead. When the pair shows no
    restart of it at all - not named on a side, the same start instant on
    both, or two instants that cannot be read and ordered as a later one - a
    ``PROBLEM`` says so beside whatever else the findings hold, because an
    expectation the pair does not confirm is never satisfied by silence. When
    it does show the container started again later but with something else on
    top - a replacement, an OOM kill, a restart count that moved - its findings
    are returned as they are: they say what happened instead, and no fault is
    taken out of them.
    """
    unmet = (f"the caller expected {name} to be restarted in place during the run and the "
             "pair does not show it: %s")
    if was is None and now is None:
        return findings + [(PROBLEM, unmet % "neither record names it")]
    if was is None:
        return findings + [(PROBLEM, unmet % "it is not named in the guest state before the "
                                             "run, so there is no start instant to compare with")]
    if now is None:
        return findings + [(PROBLEM, unmet % "it is not listed in the guest state after the run")]
    was_oom, was_restarts, was_identity, was_started = was
    oom, restarts, identity, started = now
    if not was_started or not started:
        # `read` has already reported the field that is not there; without it
        # no restart in place can be seen, expected or not.
        return findings + [(PROBLEM, unmet % "the instant it last started is not named on "
                                             "both sides")]
    if was_started == started:
        return findings + [(PROBLEM, unmet % f"it has been running since {started} in both "
                                             "records")]
    then, again = instant(was_started), instant(started)
    if then is None or again is None:
        # The instant moved, which `container_findings` has reported as a
        # restart; whether it moved LATER, which is what a restart the caller
        # applied must show, cannot be decided from text the pattern does not
        # read. The fault stands, and the expectation is not met by it.
        return findings + [(PROBLEM, unmet % f"its start instant changed ({was_started} -> "
                                             f"{started}) but the two could not be read as "
                                             "instants, so which is later could not be decided")]
    if again < then:
        return findings + [(PROBLEM, unmet % f"its start instant went backwards ({was_started} "
                                             f"-> {started}), which is not a restart")]
    same_object = bool(was_identity and identity and was_identity == identity)
    quiet = (was_oom == "false" and oom == "false" and was_restarts.isdigit()
             and restarts == was_restarts)
    if same_object and quiet and findings == [(FAULT, restarted_in_place(name, started,
                                                                          was_started))]:
        return [(EXPECTED, f"{name} was restarted in place during the run, as expected: it "
                           f"started again at {started} (it had been running since "
                           f"{was_started}), the same container object ({identity[:12]}) "
                           f"with its restart count unchanged ({restarts}) and not "
                           "OOM-killed")]
    # The pair shows something else about this container - a replacement, an
    # OOM kill, a restart count that moved - and the faults above it say what:
    # they are what the option leaves exactly as it found them.
    return findings


def compare(before_path, after_path, expected=(), restarted=()):
    """(faults, problems, expected restarts) of the two records, most concrete first."""
    faults, problems, accepted = [], [], []
    before, oom_before = read(before_path, "before", expected, faults, problems)
    after, oom_after = read(after_path, "after", expected, faults, problems)
    if before and after:
        for name in sorted(set(before) | set(after) | set(restarted)):
            was, now = before.get(name), after.get(name)
            # A container only the caller names is nothing the pair says: its
            # expectation alone is judged, never a container gone or new.
            findings = [] if was is None and now is None else \
                container_findings(name, was, now, expected)
            if name in restarted:
                findings = expected_restart(name, was, now, findings)
            for group, sentence in findings:
                (faults if group == FAULT else accepted if group == EXPECTED
                 else problems).append(sentence)
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
        for name in restarted:
            problems.append(f"the caller expected {name} to be restarted in place during the "
                            "run and the pair does not show it: no container of the pair could "
                            "be compared")
    if oom_after is None or oom_before is None:
        problems.append("the memory-cgroup OOM state of this boot is UNKNOWN, which is not 'no OOM'")
    elif oom_after:
        grew = f"{oom_before} before, {oom_after} after"
        faults.append(f"the kernel reports memory-cgroup OOM lines in this boot ({grew})")
    elif oom_before:
        problems.append(f"the kernel reported {oom_before} memory-cgroup OOM line(s) before the "
                        f"run and {oom_after} after it: the record of this boot is not consistent")
    return faults, problems, accepted


def parse(argv):
    """The expected container names, the ones expected restarted, and the two records.

    ``--expect`` names the containers the records must hold, as one list;
    ``--expect-restarted`` names one the caller's own run restarts in place, and
    is given once per container (a list with commas is read the same way, and a
    name given twice counts once). Each of them is a statement about the run,
    so one that names no container at all is not an empty statement but an
    argument that could not be read.
    """
    expected, restarted, rest = [], [], list(argv)
    while rest and rest[0].startswith("-"):
        option = rest.pop(0)
        if option == "--":
            break
        if option not in ("--expect", "--expect-restarted") or not rest:
            print(f"UNKNOWN OPTION {option}\n{USAGE}", file=sys.stderr)
            return None
        names = [name for name in rest.pop(0).split(",") if name]
        if option == "--expect":
            expected = names
            continue
        if not names:
            print(f"EMPTY OPTION {option}: it names no container\n{USAGE}", file=sys.stderr)
            return None
        restarted.extend(name for name in names if name not in restarted)
    if len(rest) != 2:
        print(USAGE, file=sys.stderr)
        return None
    return expected, restarted, rest[0], rest[1]


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
    expected, restarted, before_path, after_path = parsed
    faults, problems, accepted = compare(before_path, after_path, expected, restarted)
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
    counted = f"guest state before/after: {len(faults)} fault(s), {len(problems)} problem(s)"
    if restarted:
        # The third group exists only when the caller made a statement for it
        # to answer: without the option, every line is what it always was.
        print("## expected restarts: what the caller said the run would do, and the pair shows")
        for sentence in accepted:
            print(f"EXPECTED-RESTART: {sentence}")
        if not accepted:
            print("none")
        counted += f", {len(accepted)} expected restart(s)"
    print(counted)
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
