"""Judge how far a live collection fell short of the duration the collector declares.

Usage: collector_shortfall.py <collector-check.json>

`collector_check.py` validates a collection against the COLLECTOR'S OWN window:
there is no measured window in a preflight, so a collector that died early
reconciles with itself at full coverage and its report reads clean. The seconds
it fell short of the `duration=` its `start:` line declares are therefore
published as `declared_duration_shortfall_s`, and `preflight.sh` — the driver
that starts the collector — judges them here and nowhere else. What is compared
is the collector's own account of itself, the `duration=` it declares, against
the window it held; the `--duration` the driver passed it is not part of this
judgement, so a collector that declares a duration other than the one it was
given is not seen here.

A shortfall of at most one declared interval is the last round the collector
was in when the stop hook reached it. That interval is the collector's own
account too, so the tolerance is bounded: one round, and never more than a
twentieth of the declared duration (nor less than a second). Beyond it the
collection ended early, which is a failed mandatory step of the preflight
(`README.md`, "Which step is which"): the sample count, the coverage and the
gaps were all checked against a window shorter than the declared one.

It fails closed: a report that cannot be read, or one that does not say what
duration the collector declared or how long its own window was, leaves the
shortfall unknown, which is not "it reached its duration". One line is printed
and the exit status is 0 (the collection reached the duration declared) or 1.
"""
import json
import sys
from pathlib import Path

USAGE = "usage: collector_shortfall.py <collector-check.json>"

#: The largest part of the declared duration one declared round may stand for.
#: The interval is read from the same `start:` line as the duration, so without
#: this bound a collector declaring a long interval could fall arbitrarily far
#: short of its own duration and still be judged to have held its window.
MAX_TOLERANCE_FRACTION = 0.05


def number(report, name):
    """The report's field ``name`` when it is a number, else None."""
    value = report.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def judge(path):
    """(exit status, one line) for the collector check report at ``path``."""
    try:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return 1, (f"the collector check report {path} could not be read ({exc}): how far "
                   "the collection fell short of the duration the collector declares is UNKNOWN")
    if not isinstance(report, dict) or "declared_duration_shortfall_s" not in report:
        return 1, (f"the collector check report {path} does not carry "
                   "'declared_duration_shortfall_s': how far the collection fell short of "
                   "the duration the collector declares is UNKNOWN")
    duration = number(report, "declared_duration_s")
    window = number(report, "window_seconds")
    interval = number(report, "declared_interval_s")
    shortfall = number(report, "declared_duration_shortfall_s")
    if duration is None or window is None:
        return 1, ("the collector check report names no duration= the collector declares "
                   f"({report.get('declared_duration_s')}) or no window it held "
                   f"({report.get('window_seconds')}): the shortfall is UNKNOWN")
    round_s = interval if interval and interval > 0 else 1.0
    tolerance = min(round_s, max(1.0, MAX_TOLERANCE_FRACTION * duration))
    if shortfall is None:
        return 0, (f"the collector held its whole window: {window:g} s of the "
                   f"duration={duration:g}s its 'start:' line declares")
    if shortfall > tolerance:
        return 1, (f"the collector stopped {shortfall:g} s before the duration={duration:g}s its "
                   f"'start:' line declares (its own window is {window:g} s): the samples, the "
                   "coverage and the gaps were checked against that shorter window, not against "
                   "the declared one")
    return 0, (f"the collector held {window:g} s of the duration={duration:g}s its 'start:' "
               f"line declares, {shortfall:g} s short: within the {tolerance:g} s tolerated for "
               f"the interval={round_s:g}s round it was in when the stop hook reached it")


def main(argv):
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return 1
    code, line = judge(argv[0])
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
