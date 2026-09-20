"""Check one live collector output (CSV + companions) against the expected services.

Usage: collector_check.py <dir> <run> <expected,services> <wanted sha256> <sut_environment.json>

Exit 0 only when: the deployed collector hash is the wanted one, the diagnostics
carry exactly one start, inventory and stop record, each with a strictly valid
leading UTC timestamp and in that order, the collector was given the expected
set the inventory is judged against and reports no missing service, the closing
record accounts for every sampling round (a number for each of its counters,
none of them contradicting another, no elapsed time in neither count, no more
rounds withheld than taken, no more stamped rounds than the collector's own
window can hold, and no contradiction between its rounds and the CSV's
instants), every expected service has rows, and the CSV passes
validate_resources_csv with the collector's own start..stop as the measured
window.

The check fails closed. A bound that is missing, malformed, duplicated or
reversed stops the resource validation, which is then reported as NOT run -- a
problem of its own -- so that the minimum number of samples, the coverage of the
measured window and the sampling gaps are never silently left unchecked. A
reversed or empty window is named by the shared reconciliation below, which
refuses to read a record against it. A closing record that cannot account for
its own samples is unusable in the same way (2026-09-19).

What the closing record states is ALWAYS recorded, in the collector's own
words, whether or not it is a problem: ``closing_counters`` holds every counter
as the collector wrote it and ``observations`` holds what the record says
without being a verdict here -- the forward UTC gaps, the withheld samples,
more rounds than its own window and interval imply, a rate or a window below
the declared one, and rounds that wrote no row. The collector documents these
as harmless, or the protocol judges them elsewhere on the real instants of the
CSV (2026-09-20). The rule this file applies to the closing record is not a
copy of the one ``egw_experiments.run.inspect_collector_outputs`` applies to
the same record after a timed run: it is the SAME function,
``egw_experiments.run.reconcile_closing_record``, so the preflight and the
harness cannot disagree about what an unusable record is, and the instants are
counted here with the ingest's own ``parse_csv_timestamp``, so a CSV that the
protocol accepts is not refused here over the spelling of a timestamp. The
ORDER of the three records in the file is judged by that same function too
(2026-09-20): it was the last rule the two halves still held as two unequal
copies, and the copies disagreed about a diagnostics whose inventory came
before its start. Where a kind of record occurs more than once, both halves
keep the FIRST one found, so the window they report for one set of bytes is
one window.

One thing this check cannot judge: the coverage it validates is the coverage of
the COLLECTOR'S OWN window (there is no measured window here, as there is after
a timed run), so a collection that ended before the ``duration=`` it was asked
for is validated against itself. The shortfall is therefore reported as
``declared_duration_shortfall_s``, in seconds, at the top level of
``<dir>/collector-check.json`` (null when the collector's window reached the
declared duration, or when there is no window or no declared duration to
compare), for the driver -- which does know what it asked the collector for --
to judge (2026-09-20).

<dir>/collector-check.json is always written, even when the check itself raises,
and any problem gives exit 1.
"""
import csv
import json
import re
import sys
import traceback
from collections import Counter
from pathlib import Path

from egw_experiments.resources import parse_csv_timestamp, validate_resources_csv
from egw_experiments.run import reconcile_closing_record

USAGE = ("usage: collector_check.py <dir> <run> <expected,services> <wanted sha256> "
         "<sut_environment.json>")

# One diagnostics record: collect-resources.sh's diag() writes the UTC timestamp,
# a space and the message, so the keyword follows an optional leading token. The
# token is matched loosely on purpose: a record whose timestamp is malformed must
# be found and reported, not read as an absent record.
RECORD_RE = re.compile(r"^(?:(\S+) )?(start|inventory|stop):(?: |$)")
STAMP_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INTEGER_RE = re.compile(r"^\d+$")
DECIMAL_RE = re.compile(r"^\d+(?:\.\d+)?$")
#: ``interval=1s``/``duration=45s`` of the start record: seconds, with or
#: without the collector's trailing unit.
SECONDS_RE = re.compile(r"^(\d+(?:\.\d+)?)s?$")

# Why the absence of each record leaves the output unusable.
ABSENT = {
    "start": "the collector did not record which collector ran nor when it began",
    "inventory": "the collector did not stop cleanly (it writes the inventory when "
                 "the stop hook's SIGTERM ends it)",
    "stop": "the closing record is absent, so the end of the measured window and the "
            "number of samples kept are unknown",
}

# The other figures of the closing record, in the order collect-resources.sh
# writes them, with what the collector counts in each in its own words (the two
# counts it keeps, the time the withheld samples cost, and the samples whose
# cost it cannot measure). EVERY one of them is recorded, always. Only what
# really means the evidence cannot be accounted for is a problem:
#   - a figure the collector could not compute ('unknown') or does not state:
#     its closing record cannot be read;
#   - withheld_runs_unmeasured and withheld_open_at_stop above zero
#     (UNMEASURED_COUNTERS): elapsed time in NEITHER count, i.e. withheld
#     samples whose cost no accepted sample has measured;
#   - withheld_elapsed_s above zero while withheld_samples reads zero: the
#     record contradicts itself (see the fabricated zeros below).
# utc_gap_seconds and withheld_samples above zero are recorded and reported,
# never a verdict of their own (2026-09-20): collect-resources.sh:117-120 says
# a wall clock stepped FORWARD adds to utc_gap_seconds "although no time passed
# unsampled", and a withheld sample is the pacing artefact the collector
# recalibrates after (two samples in one wall-clock second). The authority on
# the spacing of the evidence is validate_resources_csv, which reads the REAL
# instants of the CSV and judges them against the protocol's MAX_SAMPLE_GAP_S
# (src/egw_experiments/protocol.py) -- not a counter compared with zero.
# What the collector really writes when it cannot read its own state
# (collect-resources.sh:1303-1342, AWK_SUMMARY and the defaults around it),
# since the rule must not rest on a premise the collector does not hold:
#   - the closing awk could not run at all: the shell's defaults leave all
#     five figures 'unknown';
#   - it ran but found no '#last' line: the first four read 'unknown' and
#     withheld_open_at_stop reads 0 (it is 0 from BEGIN);
#   - it ran and the '#last' line is there but a field is not a number: ONLY
#     utc_gap_seconds degrades to 'unknown'; withheld_samples and
#     withheld_runs_unmeasured fall back to 0, withheld_elapsed_s to 0.00 and
#     withheld_open_at_stop stays 0 (collect-resources.sh:396-398 documents
#     the same fallback for a line an older collector wrote).
# A zero in the withheld figures is therefore NOT proof that nothing was
# withheld, which is why withheld_elapsed_s is read here too: a figure above
# zero while the count reads zero is a contradiction inside the record.
CLOSING_COUNTERS = {
    "utc_gap_seconds": "second(s) of UTC, beyond one interval, in which no sample was "
                       "stamped",
    "withheld_samples": "sample(s) withheld (each fell in a second that is not after "
                        "the last stamped one -- a clock stepped back, or two samples "
                        "in one second -- so no rows were written for it)",
    "withheld_elapsed_s": "second(s) of elapsed time without an accepted sample, beyond "
                          "one interval and the forward UTC gaps, that finished runs of "
                          "withheld samples cost",
    "withheld_runs_unmeasured": "run(s) of withheld samples whose elapsed time could "
                                "not be measured (what they cost is in neither count)",
    "withheld_open_at_stop": "withheld sample(s) of a run still open when the collector "
                             "stopped (no accepted sample has measured it)",
}
#: Written as a decimal figure of seconds, not as a count.
DECIMAL_COUNTERS = ("withheld_elapsed_s",)
#: Above zero, these are elapsed time in neither count: a problem of their own.
UNMEASURED_COUNTERS = ("withheld_runs_unmeasured", "withheld_open_at_stop")
#: What the protocol, not this check, judges about the two counters above zero.
JUDGED_ELSEWHERE = (
    "the spacing of the real instants is judged by validate_resources_csv against the "
    "protocol's MAX_SAMPLE_GAP_S, which is the authority on it"
)


def utc_stamp(token):
    """``token`` as a strict YYYY-MM-DDTHH:MM:SSZ UTC instant, else None.

    The DIAGNOSTICS records are held to the strict spelling: the collector
    writes its bounds through awk strftime and nothing else is a bound of a
    measured window. The parsing itself is the ingest's own
    ``parse_csv_timestamp``, so both halves read one instant one way, and a
    well-shaped token that is not a calendar instant is rejected here too.
    """
    if token is None or not STAMP_RE.match(token):
        return None
    return parse_csv_timestamp(token)


def diagnostics_records(lines):
    """The start/inventory/stop records of the diagnostics, by kind.

    Each record is ``{line_no, line, token, stamp}``; ``stamp`` is None when the
    leading token is not a strictly valid UTC timestamp."""
    found = {"start": [], "inventory": [], "stop": []}
    for line_no, line in enumerate(lines, start=1):
        match = RECORD_RE.match(line.strip())
        if match is None:
            continue
        token = match.group(1)
        found[match.group(2)].append(
            {"line_no": line_no, "line": line, "token": token, "stamp": utc_stamp(token)}
        )
    return found


def one_record(kind, found, problems):
    """The single record of ``kind``, with its timestamp checked.

    Returns ``(record, ok)``. ``record`` is the FIRST one found (None when
    there is none), so the report still shows what was read;
    ``egw_experiments.run.inspect_collector_outputs`` keeps the first one too
    (2026-09-20), so a diagnostics holding two collectors does not give the
    two halves two different windows for the same bytes. ``ok`` is False when
    the record is missing, duplicated or carries no strictly valid leading UTC
    timestamp -- each of which is a problem of its own."""
    if not found:
        problems.append(f"no '{kind}:' line in the diagnostics: {ABSENT[kind]}")
        return None, False
    record, ok = found[0], True
    if len(found) > 1:
        problems.append(
            f"{len(found)} '{kind}:' lines in the diagnostics (lines "
            f"{', '.join(str(r['line_no']) for r in found)}): more than one collector "
            "wrote this output, so its bounds are ambiguous")
        ok = False
    if record["stamp"] is None:
        problems.append(
            f"the '{kind}:' line carries no strictly valid leading UTC timestamp "
            f"(YYYY-MM-DDTHH:MM:SSZ): {record['token']!r}")
        ok = False
    return record, ok


def field(record, name):
    """The ``name=<value>`` field of a record's line, else None."""
    match = re.search(rf"\b{name}=(\S+)", record["line"])
    return match.group(1) if match else None


def seconds(token):
    """``45s``/``45`` as a number of seconds, else None."""
    match = SECONDS_RE.match(token) if token else None
    return float(match.group(1)) if match else None


def declared_services(record):
    """The ``expected services:`` value of a start record, as written."""
    _, sep, value = record["line"].rpartition("expected services: ")
    return value.strip() if sep else None


def check(d, rid, expect, want_sha, sut, report):
    """Fill ``report`` (its ``problems`` above all) for one collector output."""
    problems = report["problems"]
    observations = report["observations"]
    csv_path = d / f"resources-{rid}.csv"
    if not SHA256_RE.match(want_sha):
        problems.append(f"the wanted collector sha256 {want_sha!r} is not a sha256")
    if not expect:
        problems.append("no expected services were given: a service without a single "
                        "row would go unnoticed")

    # The diagnostics bounds: exactly one start, inventory and stop, each stamped
    # and in that order, with a start strictly earlier than the stop.
    diag_path = d / f"resources-{rid}.csv.diagnostics.log"
    lines = diag_path.read_text(encoding="utf-8").splitlines() if diag_path.is_file() else []
    if not lines:
        problems.append("no diagnostics companion: the collector's bounds are unknown")
    found = diagnostics_records(lines)
    start, start_ok = one_record("start", found["start"], problems)
    inventory, inventory_ok = one_record("inventory", found["inventory"], problems)
    stop, stop_ok = one_record("stop", found["stop"], problems)
    report["start_line"] = start["line"] if start else None
    report["inventory"] = inventory["line"] if inventory else None
    report["stop_line"] = stop["line"] if stop else None

    sha = None
    if start is not None:
        candidate = field(start, "collector_sha256")
        if candidate is not None and SHA256_RE.match(candidate):
            sha = candidate
        else:
            problems.append(f"the 'start:' line carries no usable collector_sha256 "
                            f"({candidate!r})")
            start_ok = False
        # The expected set the collector was GIVEN. Without it the inventory's
        # missing= is vacuous: a collector started without --expect-services
        # writes 'none declared' and then 'missing=none', having been asked
        # about nothing (2026-09-20). inspect_collector_outputs makes the same
        # comparison after a timed run, in the same words.
        declared = declared_services(start)
        report["declared_expected_services"] = declared
        declared_set = (set() if declared in (None, "", "none declared")
                        else set(declared.split(",")))
        if expect and declared_set != set(expect):
            problems.append(
                f"the collector's 'start:' line declares expected services "
                f"{declared!r}, this check was given {','.join(expect)!r}: the start "
                "hook did not pass the same --expect-services to the collector, so its "
                "inventory's missing= was judged against another set")
        report["declared_interval_s"] = seconds(field(start, "interval"))
        report["declared_duration_s"] = seconds(field(start, "duration"))
    report["deployed_sha256"] = sha
    if sha is None:
        problems.append("the deployed collector hash is unknown, so it cannot be "
                        f"compared with the clean clone's {want_sha}")
    elif sha != want_sha:
        problems.append(f"deployed collector hash {sha} is not the clean clone's {want_sha}")

    if inventory is not None:
        missing = field(inventory, "missing")
        if missing is None:
            problems.append("the 'inventory:' line has no 'missing=' field: "
                            f"{inventory['line']!r}")
            inventory_ok = False
        elif missing != "none":
            problems.append(f"inventory reports missing services: {inventory['line']}")

    withheld = None
    if stop is not None:
        samples = field(stop, "samples")
        if samples is None or not INTEGER_RE.match(samples):
            problems.append(f"the 'stop:' line carries no integer samples= count "
                            f"({samples!r}): its closing record cannot be read")
            stop_ok = False
        else:
            report["samples"] = int(samples)
        # What the collector could and could not measure, in its own words.
        # Every figure is recorded; a figure it did not state, or stated as
        # 'unknown', leaves the closing record as unreadable as a missing
        # samples= count. See CLOSING_COUNTERS for what is a problem and what
        # is only recorded here.
        counters = report.setdefault("closing_counters", {})
        read = {}
        for name, counts in CLOSING_COUNTERS.items():
            value = field(stop, name)
            counters[name] = value
            pattern = DECIMAL_RE if name in DECIMAL_COUNTERS else INTEGER_RE
            if value is None:
                problems.append(f"the collector's 'stop:' line has no '{name}=' field: "
                                f"the collector's own count of {counts} is not stated, "
                                "so its closing record is incomplete")
                stop_ok = False
            elif not pattern.match(value):
                problems.append(f"the collector's 'stop:' line carries {name}={value}: "
                                "the collector could not read its own state file when "
                                "it closed (it then writes 'unknown'), so its count of "
                                f"{counts} is unknown and its closing record cannot be "
                                "read")
                stop_ok = False
            else:
                read[name] = float(value) if name in DECIMAL_COUNTERS else int(value)
        for name in UNMEASURED_COUNTERS:
            if read.get(name):
                problems.append(
                    f"the collector reports {name}={counters[name]}: "
                    f"{counters[name]} {CLOSING_COUNTERS[name]}, so that time is "
                    "accounted for nowhere and the evidence cannot be added up")
        if read.get("utc_gap_seconds"):
            observations.append(
                f"the collector reports utc_gap_seconds={counters['utc_gap_seconds']}: "
                f"{counters['utc_gap_seconds']} {CLOSING_COUNTERS['utc_gap_seconds']}. "
                "A wall clock stepped forward adds to it although no time passed "
                "unsampled (collect-resources.sh), so it is recorded, not judged here: "
                f"{JUDGED_ELSEWHERE}")
        if read.get("withheld_samples"):
            observations.append(
                f"the collector reports withheld_samples={counters['withheld_samples']}"
                f" ({counters['withheld_elapsed_s']} s of elapsed time): "
                f"{counters['withheld_samples']} "
                f"{CLOSING_COUNTERS['withheld_samples']}. The collector recalibrates "
                "its phase after one, so it is recorded, not judged here: "
                f"{JUDGED_ELSEWHERE}, and what the withheld samples cost is a problem "
                "of its own when it is in neither count")
        if read.get("withheld_elapsed_s") and read.get("withheld_samples") == 0:
            problems.append(
                f"the collector reports withheld_elapsed_s={counters['withheld_elapsed_s']}"
                " while withheld_samples=0: the closing record contradicts itself, and "
                "the zero is what its closing awk writes when it cannot read the "
                "withheld count in its state file (collect-resources.sh:1303-1330), so "
                "the samples that cost that elapsed time are unaccounted for")
        withheld = read.get("withheld_samples")

    # The ORDER of the records -- their file positions and their stamps -- is
    # judged by reconcile_closing_record below, which reports both in the
    # words the two halves share: one rule in one place, so the harness half
    # cannot seal records this half refuses (2026-09-20; the file order was
    # the last rule still held here as a second, unequal copy). Here the
    # verdict additionally stops the resource validation, which has no
    # unambiguous window to validate against.
    order_ok = True
    if start and stop and start["stamp"] and stop["stamp"]:
        order_ok = start["stamp"] < stop["stamp"]
    if start and stop:
        report["window"] = [start["token"], stop["token"]]

    # The collector's own window: the only length these two records can prove,
    # and the one the reconciliation below reads the closing record against. A
    # stop that is not after the start measures nothing, so no length is
    # recorded from it and nothing is derived from it (2026-09-20).
    window_s = None
    if start and stop and start["stamp"] and stop["stamp"]:
        measured = int((stop["stamp"] - start["stamp"]).total_seconds())
        if measured > 0:
            window_s = measured
            report["window_seconds"] = window_s

    if not (d / f"resources-{rid}.csv.lifecycle.csv").is_file():
        problems.append("no lifecycle companion")
    markers = sorted(p.name for p in d.glob("*.self-test"))
    if markers:
        problems.append(f"self-test marker(s) present ({', '.join(markers)}): the "
                        "collector ran on substituted inputs, so this output is NOT a "
                        "measurement")

    # Rows per service, and the instants behind them.
    rows, instants, csv_ok = Counter(), set(), False
    if not csv_path.is_file():
        problems.append(f"no CSV: {csv_path.name} was not fetched")
    else:
        try:
            with open(csv_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                header = reader.fieldnames or []
                if "container" not in header or "ts_utc" not in header:
                    problems.append(f"the CSV header {header!r} has no 'container'/"
                                    "'ts_utc' column: its rows cannot be attributed")
                else:
                    for r in reader:
                        name = (r.get("container") or "").strip()
                        if name:
                            rows[name] += 1
                        instants.add((r.get("ts_utc") or "").strip())
                    csv_ok = True
        except (OSError, csv.Error, UnicodeDecodeError) as exc:
            problems.append(f"the CSV could not be read: {exc}")
    report["rows_per_service"] = dict(rows)
    report["unexpected_names"] = sorted(set(rows) - set(expect))
    report["distinct_instants"] = len(instants)
    for s in expect:
        if rows.get(s, 0) == 0:
            problems.append(f"expected service {s} has no rows")

    # The closing record against its own start record and against the CSV.
    # The rule is reconcile_closing_record, the ONE function
    # egw_experiments.run.inspect_collector_outputs calls after a timed run:
    # only a record that contradicts itself is a problem, and what the record
    # says beyond that -- withheld rounds, forward clock steps, the rounds its
    # declared interval implies, a rate or a window below the declared one,
    # rounds that wrote no row -- is recorded as an observation. The instants
    # are counted with the ingest's own parse_csv_timestamp, the parser
    # validate_resources_csv uses on the same cells, so a CSV that the
    # protocol accepts cannot be refused here over the spelling of its
    # timestamps (2026-09-20).
    if csv_ok and start is not None and stop is not None and start["stamp"] and stop["stamp"]:
        report["distinct_instants_in_window"] = sum(
            1 for at in (parse_csv_timestamp(i) for i in instants)
            if at is not None and start["stamp"] <= at <= stop["stamp"]
        )
    reconciliation = reconcile_closing_record(
        samples=report["samples"],
        withheld=withheld,
        instants_in_window=report.get("distinct_instants_in_window"),
        csv_readable=csv_ok,
        window=(
            start["token"] if start and start["stamp"] else None,
            stop["token"] if stop and stop["stamp"] else None,
        ),
        window_seconds=window_s,
        interval_s=report["declared_interval_s"],
        duration_s=report["declared_duration_s"],
        record_lines=(
            start["line_no"] if start else None,
            inventory["line_no"] if inventory else None,
            stop["line_no"] if stop else None,
        ),
    )
    report["closing_record_reconciliation"] = reconciliation["state"]
    report["rounds_the_declared_interval_implies"] = (
        reconciliation["rounds_the_declared_interval_implies"]
    )
    # The seconds by which the collection fell short of the duration= it was
    # asked for. Neither half can judge it: the stop hook's SIGTERM ends a
    # timed run's collector before its declared duration (nominal-r01 closed
    # a 722 s window of the 840 s it declared), and nothing in the fetched
    # output says which case this is. The preflight's collector, on the other
    # hand, IS started with an explicit --duration and is expected to reach
    # it, and this is the only window the coverage is judged over here -- a
    # collection that ended early is validated against itself -- so the
    # figure is reported for the driver to read (2026-09-20).
    report["declared_duration_shortfall_s"] = (
        reconciliation["declared_duration_shortfall_s"]
    )
    problems += reconciliation["problems"]
    observations += reconciliation["observations"]
    if reconciliation["records_in_order"] is False:
        order_ok = False
    bounds_ok = start_ok and inventory_ok and stop_ok and order_ok

    # The SUT node the CSV must come from.
    node = None
    try:
        environment = json.loads(Path(sut).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"sut_environment.json {sut} could not be read: {exc}")
    else:
        node = environment.get("node") if isinstance(environment, dict) else None
        if not node:
            problems.append(f"sut_environment.json {sut} carries no 'node': the host "
                            "the CSV must have been collected on is unknown")
            node = None

    # The resource validation itself: it runs only on an unambiguous window, and
    # its absence is reported as a problem, never left silent.
    blockers = []
    if not bounds_ok:
        blockers.append("the collector's start/inventory/stop records do not give one "
                        "unambiguous, ordered measured window")
    if not csv_ok:
        blockers.append("the CSV could not be read")
    if node is None:
        blockers.append("the SUT node is unknown")
    if blockers:
        report["resource_validation"] = "not run: " + "; ".join(blockers)
    else:
        try:
            reasons = validate_resources_csv(
                str(csv_path), expected_host=node,
                expected_window_start_utc=report["window"][0],
                expected_window_end_utc=report["window"][1])
        except Exception as exc:  # a validator that cannot judge is not a pass
            report["resource_validation"] = f"not run: validate_resources_csv raised {exc!r}"
            problems.append(f"validate_resources_csv raised {exc!r}: the CSV was not validated")
        else:
            report["resource_validation"] = "run"
            problems += [f"validate_resources_csv: {p}" for p in reasons]
    if report["resource_validation"] != "run":
        problems.append(
            f"the resource validation did NOT run ({report['resource_validation']}): the "
            "minimum number of samples, the coverage of the measured window and the "
            "sampling gaps are UNCHECKED")


def main(argv):
    if len(argv) < 2:
        print(USAGE, file=sys.stderr)
        return 1
    d = Path(argv[1])
    report = {"run": argv[2] if len(argv) > 2 else None, "deployed_sha256": None,
              "rows_per_service": {}, "unexpected_names": [], "distinct_instants": 0,
              "distinct_instants_in_window": None, "window": [None, None],
              "window_seconds": None, "start_line": None, "stop_line": None,
              "inventory": None, "declared_expected_services": None,
              "declared_interval_s": None, "declared_duration_s": None,
              "declared_duration_shortfall_s": None,
              "rounds_the_declared_interval_implies": None,
              "samples": None, "closing_counters": {},
              "closing_record_reconciliation": "not run",
              "resource_validation": "not run", "observations": [], "problems": []}
    if len(argv) != 6:
        report["problems"].append(f"wrong number of arguments ({len(argv) - 1}); {USAGE}")
    else:
        try:
            check(d, argv[2], [s for s in argv[3].split(",") if s], argv[4], argv[5], report)
        except Exception:  # the check itself must never end without a report
            report["problems"].append(
                "collector_check raised: "
                + " | ".join(traceback.format_exc(limit=5).strip().splitlines()))
    text = json.dumps(report, indent=2)
    try:
        (d / "collector-check.json").write_text(text + "\n", encoding="utf-8")
    except OSError as exc:
        report["problems"].append(f"collector-check.json could not be written: {exc}")
        text = json.dumps(report, indent=2)
        print(f"collector-check.json could not be written: {exc}", file=sys.stderr)
    print(text)
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
