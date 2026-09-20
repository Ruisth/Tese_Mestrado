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

The two records are judged as a PAIR, in both directions and in both senses. A
container that was OOM-killed, one that restarted during the measured window
(by its count or by its start instant), one that is gone after the run and one
that was REPLACED during it (a recreated container object carries a new id and
starts again at restart count 0, so the OOM and restart history the 'before'
record holds is lost with the old object) are all facts about the run, not
notes: the pilot has already lost a run to a Ditto OOM. They are therefore
problems here, and so is anything that leaves them unknown - a record that
cannot be read, a container line the pattern cannot read, a count that is not
an integer, a container with no baseline, and a record that does not name every
container the caller expects. Every problem is printed and names the container
it is about; the exit status is 0 (nothing to report) or 1 (any problem).
"""
import re
import sys

USAGE = ("usage: guest_state_delta.py [--expect NAME[,NAME...]] "
         "<guest-state-before stdout> <guest-state-after stdout>")

CONTAINER = re.compile(r"^container (?P<name>\S+) oomkilled=(?P<oom>\S+) "
                       r"restarts=(?P<restarts>\S+)(?: id=(?P<id>\S+))?"
                       r"(?: started=(?P<started>\S+))?$")
NAMED = re.compile(r"^container(?: (?P<name>\S+))?")
OOM_LINES = re.compile(r"^memory-cgroup OOM lines: (?P<count>\S+)$")


def read(path, label, expected, problems):
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
            for field in ("id", "started"):
                if not match.group(field) or match.group(field) == "unknown":
                    problems.append(f"the guest state {label} the run does not name the "
                                    f"{field} of {name} ({match.group(field) or 'no field'}): a "
                                    "container object that was replaced, or one that was "
                                    "restarted in place, could not be seen")
            containers[name] = (match.group("oom"), match.group("restarts"),
                                match.group("id"), match.group("started"))
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
        problems.append(f"the guest state {label} the run names {len(expected) - len(missing)} "
                        f"of the {len(expected)} expected containers (missing: "
                        f"{', '.join(missing)})")
    counts = [match.group("count") for match in
              (OOM_LINES.match(line.strip()) for line in lines) if match]
    if len(counts) != 1 or not counts[0].isdigit():
        problems.append(f"the guest state {label} the run holds no readable "
                        f"memory-cgroup OOM count ({', '.join(counts) or 'none'})")
        return containers, None
    return containers, int(counts[0])


def container_problems(name, was, now):
    """What the pair of records says about one container, in both senses."""
    if now is None:
        return [f"{name} was running before the run and is not listed after it"]
    oom, restarts, identity, started = now
    problems = []
    if oom == "true":
        problems.append(f"{name} was OOM-killed (OOMKilled={oom})")
    elif oom != "false":
        problems.append(f"{name} has no readable OOMKilled state after the run (OOMKilled={oom})")
    if was is None:
        problems.append(f"{name} was not running before the run: there is no restart baseline for it")
        return problems
    was_oom, was_restarts, was_identity, was_started = was
    replaced = (f"{name} was replaced during the run: %s, so its OOM and restart history "
                "was reset with the old container object")
    new_object = bool(was_identity and identity and was_identity != identity)
    if new_object:
        problems.append(replaced % f"the container id changed ({was_identity[:12]} -> "
                                   f"{identity[:12]})")
    if was_started and started and was_started != started:
        # The one signal an in-place restart leaves: 'docker restart' keeps the
        # container object (same id) and does not touch RestartCount, which
        # Docker increments from the restart POLICY, so without this the two
        # records are identical.
        problems.append(f"{name} was restarted during the run: it started again at {started} "
                        f"(it had been running since {was_started})")
    if not was_restarts.isdigit() or not restarts.isdigit():
        problems.append(f"{name} has no readable restart count (before {was_restarts}, "
                        f"after {restarts})")
    elif int(restarts) > int(was_restarts):
        problems.append(f"{name} restarted during the run ({was_restarts} -> {restarts})")
    elif int(restarts) < int(was_restarts) and not new_object:
        # A count that fell with no id to prove it: the container object was
        # recreated all the same, because a restart count never decreases.
        problems.append(replaced % f"the restart count went {was_restarts} -> {restarts}")
    if was_oom == "true" and oom == "false":
        problems.append(f"{name} was OOM-killed before the run and is not after it: the "
                        "container object was replaced and its OOM history lost")
    return problems


def compare(before_path, after_path, expected=()):
    """Every problem in the two records, most concrete first."""
    problems = []
    before, oom_before = read(before_path, "before", expected, problems)
    after, oom_after = read(after_path, "after", expected, problems)
    for name in sorted(set(before) | set(after)):
        problems.extend(container_problems(name, before.get(name), after.get(name)))
    if oom_after is None or oom_before is None:
        problems.append("the memory-cgroup OOM state of this boot is UNKNOWN, which is not 'no OOM'")
    elif oom_after:
        grew = f"{oom_before} before, {oom_after} after"
        problems.append(f"the kernel reports memory-cgroup OOM lines in this boot ({grew})")
    elif oom_before:
        problems.append(f"the kernel reported {oom_before} memory-cgroup OOM line(s) before the "
                        f"run and {oom_after} after it: the record of this boot is not consistent")
    return problems


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
        return 1
    expected, before_path, after_path = parsed
    problems = compare(before_path, after_path, expected)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    print(f"guest state before/after: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
