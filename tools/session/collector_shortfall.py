"""Judge how far a live collection fell short of the duration the collector declares.

Usage: collector_shortfall.py <collector-check.json>

`collector_check.py` validates a collection against the COLLECTOR'S OWN window:
there is no measured window in a preflight, so a collector that died early
reconciles with itself at full coverage and its report reads clean. How far it
fell short of the `duration=` its `start:` line declares is therefore judged
here, by `preflight.sh` -- the driver that starts the collector -- and nowhere
else. What is compared is the collector's own account of itself, the
`duration=` it declares, against the window it held; the `--duration` the
driver passed it is not part of this judgement, so a collector that declares a
duration other than the one it was given is not seen here.

The window it held is measured on the guest's monotonic clock (2026-10-05):
between the `uptime_s=` bounds its `start:` and `stop:` records carry, which
must come from one boot (the same `boot_id=`), as `collector_check.py`
publishes them under `monotonic_bounds`. That is the clock the collector's own
`--duration` loop runs on (`/proc/uptime`), which no wall-clock step moves. The
UTC window of the same two records is kept beside the verdict, for the coverage
and for diagnosis, and is never the verdict: on 2026-10-05 it read 43 s of a
45 s collection whose calibration lines put 38 s of UTC against 40.69 s of
uptime, and a wall clock set forward would make a collector that stopped early
read whole. Bounds that are missing (every output of the collector before that
date), malformed, reversed or from two boots leave the duration UNKNOWN, which
is a failure; nothing falls back to UTC.

A shortfall of at most one declared interval is the last round the collector
was in when the stop hook reached it. That interval is the collector's own
account too, so the tolerance is bounded: one round, and never more than a
twentieth of the declared duration (nor less than a second). Beyond it the
collection ended early, which is a failed mandatory step of the preflight
(`README.md`, "Which step is which"): the sample count, the coverage and the
gaps were all checked against a window shorter than the declared one.

It fails closed: a report that cannot be read, or one that does not say what
duration the collector declared or where its own window began and ended,
leaves the shortfall unknown, which is not "it reached its duration". One line
is printed and the exit status is 0 (the collection reached the duration
declared) or 1.
"""
import json
import re
import sys
from pathlib import Path

USAGE = "usage: collector_shortfall.py <collector-check.json>"

#: The largest part of the declared duration one declared round may stand for.
#: The interval is read from the same `start:` line as the duration, so without
#: this bound a collector declaring a long interval could fall arbitrarily far
#: short of its own duration and still be judged to have held its window.
MAX_TOLERANCE_FRACTION = 0.05

#: A bound as the collector writes it: the first field of /proc/uptime, which
#: the kernel writes with two decimals, and the kernel's boot id.
UPTIME_RE = re.compile(r"^\d+\.\d\d$")
BOOT_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
BOUNDS = ("start_uptime_s", "stop_uptime_s", "start_boot_id", "stop_boot_id")


def number(report, name):
    """The report's field ``name`` when it is a number, else None."""
    value = report.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def monotonic_window(report):
    """``((start, stop, boot, centiseconds), None)`` or ``(None, why)``.

    The two uptime bounds and the boot id they share, as the collector wrote
    them, and the window between them in centiseconds (both bounds carry two
    decimals, so the difference is exact)."""
    bounds = report.get("monotonic_bounds")
    if not isinstance(bounds, dict):
        return None, ("the collector check report carries no 'monotonic_bounds' "
                      f"({bounds!r})")
    missing = [name for name in BOUNDS if bounds.get(name) is None]
    if missing:
        return None, (f"the collector's 'start:'/'stop:' records carry no {', '.join(missing)} "
                      "(an output of the collector before 2026-10-05, or one that lost them)")
    malformed = [
        f"{name}={bounds[name]!r}" for name in BOUNDS
        if not isinstance(bounds[name], str)
        or not (UPTIME_RE if name.endswith("_uptime_s") else BOOT_ID_RE).match(bounds[name])
    ]
    if malformed:
        return None, (f"the collector's bounds are malformed ({', '.join(malformed)}; the "
                      "collector writes /proc/uptime with two decimals and the kernel's boot "
                      "id, and 'unknown'/'unavailable' when it could not read them)")
    start, stop = bounds["start_uptime_s"], bounds["stop_uptime_s"]
    boot = bounds["start_boot_id"]
    if bounds["stop_boot_id"] != boot:
        return None, (f"the collector's bounds come from different boots ({boot} at the start, "
                      f"{bounds['stop_boot_id']} at the stop): two uptimes of two boots measure "
                      "nothing between them")
    centiseconds = int(stop.replace(".", "")) - int(start.replace(".", ""))
    if centiseconds <= 0:
        return None, (f"the collector's bounds are reversed or empty (uptime {start} s at the "
                      f"start, {stop} s at the stop)")
    return (start, stop, boot, centiseconds), None


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
    utc_window = number(report, "window_seconds")
    interval = number(report, "declared_interval_s")
    if duration is None:
        return 1, ("the collector check report names no duration= the collector declares "
                   f"({report.get('declared_duration_s')}): the shortfall is UNKNOWN")
    utc = ("its UTC window, kept for coverage and diagnosis, "
           + (f"reads {utc_window:g} s" if utc_window is not None else "is unknown"))
    held, why = monotonic_window(report)
    if held is None:
        return 1, (f"{why}: the duration is judged only on the collector's uptime bounds from "
                   "one boot, never on its UTC stamps, so how far it fell short of the "
                   f"duration={duration:g}s its 'start:' line declares is UNKNOWN ({utc})")
    start, stop, boot, centiseconds = held
    window = centiseconds / 100
    clock = f"on the guest's monotonic clock (uptime {start} s to {stop} s, boot {boot})"
    round_s = interval if interval and interval > 0 else 1.0
    tolerance = min(round_s, max(1.0, MAX_TOLERANCE_FRACTION * duration))
    shortfall_cs = round(duration * 100) - centiseconds
    if shortfall_cs <= 0:
        return 0, (f"the collector held its whole window: {window:g} s {clock} of the "
                   f"duration={duration:g}s its 'start:' line declares; {utc}")
    shortfall = shortfall_cs / 100
    if shortfall_cs > round(tolerance * 100):
        return 1, (f"the collector stopped {shortfall:g} s before the duration={duration:g}s "
                   f"its 'start:' line declares (its own window is {window:g} s {clock}; "
                   f"{utc}): the samples, the coverage and the gaps were checked against that "
                   "shorter window, not against the declared one")
    return 0, (f"the collector held {window:g} s {clock} of the duration={duration:g}s its "
               f"'start:' line declares, {shortfall:g} s short: within the {tolerance:g} s "
               f"tolerated for the interval={round_s:g}s round it was in when the stop hook "
               f"reached it; {utc}")


def main(argv):
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return 1
    code, line = judge(argv[0])
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
