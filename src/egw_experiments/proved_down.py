"""The proved-down interval of decision 1a, derived from a run directory.

Decision 1a (the student's adoption of 2026-09-30, prospective): at a
``controller_restart`` run's restart, the restarted controller's resource
rows are judged by the interval in which it is PROVED down - from its Docker
``die`` (D) to its ``start`` (S) - instead of as one gap against
``MAX_SAMPLE_GAP_S``. The interval exists only if everything below holds;
anything short of it, and any ambiguity at all, gives NO interval, the reason
named, and the ordinary rule then decides the file exactly as before
(``egw_experiments.resources.validate_resources_csv`` without ``proved_down``).

1. The restart record shows the restart executed with return code 0.
2. The StartedAt read was fetched: exactly one ``started_at`` record among the
   run's SUT fetches (``--fetch-started-at-cmd``), ended 0, its file
   ``logs/sut/controller-started-at.txt`` present and not empty.
3. The run's docker-events fetch ended 0 with ``logs/sut/docker-events.log``,
   and its verdict ``logs/sut/docker-events.coverage.txt`` starts with
   ``coverage=complete``, names ``container=egw-controller-1``, expects
   ``die`` and ``start`` and gives whole-number ``requested_since_guest_epoch``
   (t0) and ``requested_until_guest_epoch`` (t1), each key once.
4. In the capture window [t0, t1 + 1) - the window of the capture's own rule
   R7 (``tools/session/events_coverage.py``), which leaves out the 120 s the
   recorder's subscription replays before RUN_T0 - among the container events
   of egw-controller-1: EXACTLY one ``die`` and EXACTLY one ``start``, the
   start strictly after the die, both of one container id (``Actor.ID``, 64
   lower-case hex). Every line of the capture must be a JSON object with an
   integer ``timeNano``.
5. The StartedAt record (``tools/session/fetch_started_at.sh``: exactly the
   lines ``container=``, ``container_id=``, ``started_at=``, ``guest_epoch=``)
   names egw-controller-1 and the pair's container id, its ``started_at`` is
   RFC 3339 ending ``Z`` with at most nine fractional digits (parsed to
   integer nanoseconds here, never through ``datetime.fromisoformat``), it
   was read at or after S (``guest_epoch``, read before the inspect so that
   the inspect is at or after it, times 10^9 not before S) and
   |S - StartedAt| <= 1 s.

The last condition of the rule - the container has a row at or before
``sec(D)`` and one after ``sec(S)`` - is the validator's
(``resources.proved_down_outcomes``), since it reads the rows.

Every instant is on the guest clock (the daemon's ``timeNano``, StartedAt, the
guest's ``date +%s`` and the collector's rows); the host-clock restart record
is read for its outcome only. Pure: files are read, nothing is written.

The restart transition rule (``resources.TRANSITION_RULE``; option A of the T6
page, qualified, adopted by the student on 2026-10-05, prospective, for the new
G3 T6 run) rests on one more file: :func:`read_lifecycle_witness` reads the
collector's own lifecycle record of this run (``<the run's collector
CSV>.lifecycle.csv``, collect-resources.sh) as the collector writes it and
keeps its rows of the pair's container id or of the container's name. A record
missing, not UTF-8, without its header, with any row not of the collector's
form, or going back in time is unreadable as a whole: it grants nothing.
"""

from __future__ import annotations

import calendar
import json
import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .protocol import RESOURCE_SAMPLE_INTERVAL_S
from .resources import (
    LifecycleRecord,
    LifecycleWitness,
    ProvedDownInterval,
    ns_utc_text,
    whole_second,
)

#: The restarted container: the one test 6's restart names, the one its
#: capture's coverage verdict and its StartedAt record must both name.
CONTAINER = "egw-controller-1"

#: The StartedAt record the harness's --fetch-started-at-cmd writes, under
#: the run's logs/sut/ (run.py SUT_LOG_SUBDIR).
STARTED_AT_FILENAME = "controller-started-at.txt"

_SUT_DIR = "logs/sut"
DOCKER_EVENTS_REL = f"{_SUT_DIR}/docker-events.log"
COVERAGE_REL = f"{_SUT_DIR}/docker-events.coverage.txt"
STARTED_AT_REL = f"{_SUT_DIR}/{STARTED_AT_FILENAME}"

#: The harness's hook labels of the two fetches the interval rests on.
DOCKER_EVENTS_HOOK = "docker_events"
STARTED_AT_HOOK = "started_at"

_NS = 1_000_000_000
#: |S - StartedAt| may not exceed this (decision 1a: "to 1 s").
STARTED_AT_TOLERANCE_NS = _NS

_WHOLE = re.compile(r"[0-9]+")
_CONTAINER_ID = re.compile(r"[0-9a-f]{64}")
#: RFC 3339's DIGIT is ASCII 0-9: [0-9], never \d, which also matches every
#: other Unicode decimal digit (and int() converts them).
_RFC3339_Z = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]{1,9}))?Z"
)
_STARTED_AT_KEYS = ("container", "container_id", "started_at", "guest_epoch")

#: The collector's lifecycle record beside its CSV (collect-resources.sh,
#: "Files written beside <output.csv>"; run.py COLLECTOR_OUTPUT_FILES), its
#: header and the four events it writes.
LIFECYCLE_SUFFIX = ".lifecycle.csv"
LIFECYCLE_HEADER = "ts_utc,event,container_id,name"
LIFECYCLE_EVENTS = frozenset({"appeared", "disappeared", "counter_reset", "named"})
#: The collector's stamp: a whole UTC second, ASCII digits, ``Z``.
_LIFECYCLE_STAMP = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z")
#: A cgroup's id (the directory name without docker-/.scope) and a container
#: name as the collector writes them; a name is empty until it resolves.
_LIFECYCLE_ID = re.compile(r"[0-9A-Za-z_.-]+")
_LIFECYCLE_NAME = re.compile(r"[0-9A-Za-z_.-]*")


def parse_rfc3339_ns(text: str) -> int | None:
    """``YYYY-MM-DDTHH:MM:SS[.f{1,9}]Z`` as integer nanoseconds since the
    epoch, or None for anything else (an offset other than ``Z``, more than
    nine fractional digits, an impossible date). The fraction is read as
    digits, so no nanosecond is rounded away."""
    match = _RFC3339_Z.fullmatch(text or "")
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(g) for g in match.groups()[:6])
    try:
        whole = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    frac = match.group(7) or ""
    return calendar.timegm(whole.timetuple()) * _NS + int(frac.ljust(9, "0") or "0")


def _whole_number(text: str) -> int | None:
    """Digits only, as an int; None for anything else, and for digits too
    many for Python to convert from text (``sys.get_int_max_str_digits()``),
    which would otherwise raise inside the harness."""
    if not _WHOLE.fullmatch(text):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _key_values(text: str) -> tuple[dict[str, list[str]], list[str]]:
    """``key=value`` lines as {key: [values]}, plus the lines that are not."""
    values: dict[str, list[str]] = {}
    other: list[str] = []
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if not sep or not key:
            other.append(line)
            continue
        values.setdefault(key, []).append(value)
    return values, other


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _fetch_record(manifest: Mapping[str, Any], hook: str) -> tuple[dict | None, str | None]:
    fetches = manifest.get("sut_log_fetches")
    records = [
        r for r in (fetches if isinstance(fetches, list) else [])
        if isinstance(r, dict) and r.get("hook") == hook
    ]
    if len(records) != 1:
        return None, f"{len(records)} records of it"
    return records[0], None


def derive_proved_down(
    run_dir: str | Path, manifest: Mapping[str, Any]
) -> tuple[ProvedDownInterval | None, str | None, dict[str, Any]]:
    """The proved-down interval of a run, from its directory and its manifest
    (or the harness's in-memory records of the same keys: ``condition_id``,
    ``restart``, ``sut_log_fetches``).

    Returns ``(interval, None, facts)`` when every condition of the module
    docstring holds, else ``(None, why_not, facts)``; ``facts`` holds what
    was established before the first condition that failed (the instants in
    integer nanoseconds and as UTC text, the counts of die and start events
    in the window, StartedAt and S - StartedAt, the interval and exempt
    lengths). Reads files only."""
    run_dir = Path(run_dir)
    facts: dict[str, Any] = {"container": CONTAINER}

    def no(why: str) -> tuple[None, str, dict[str, Any]]:
        return None, why, facts

    if manifest.get("condition_id") != "controller_restart":
        return no(
            f"the plan condition is {manifest.get('condition_id')!r}, not "
            "controller_restart: the rule belongs to the restart condition"
        )
    restart = manifest.get("restart")
    executed = restart.get("executed") if isinstance(restart, dict) else None
    returncode = restart.get("returncode") if isinstance(restart, dict) else None
    if not (
        executed is True
        and isinstance(returncode, int)
        and not isinstance(returncode, bool)
        and returncode == 0
    ):
        return no(
            "the restart record does not show the restart executed with return "
            f"code 0 (executed={executed!r}, returncode={returncode!r})"
        )

    # The StartedAt read (--fetch-started-at-cmd): ended 0 with its file.
    record, problem = _fetch_record(manifest, STARTED_AT_HOOK)
    started_path = run_dir / STARTED_AT_REL
    if (
        record is None
        or record.get("returncode") != 0
        or record.get("dest_exists") is not True
        or not started_path.is_file()
        or started_path.stat().st_size == 0
    ):
        return no(
            "the StartedAt fetch (--fetch-started-at-cmd) did not end 0 with a "
            f"non-empty {STARTED_AT_REL}"
            + (f" ({problem})" if problem else "")
        )

    # The run's capture and its verdict.
    record, problem = _fetch_record(manifest, DOCKER_EVENTS_HOOK)
    events_path = run_dir / DOCKER_EVENTS_REL
    if (
        record is None
        or record.get("returncode") != 0
        or record.get("dest_exists") is not True
        or record.get("dest_file") != DOCKER_EVENTS_REL
        or not events_path.is_file()
    ):
        return no(
            f"the docker-events fetch did not end 0 with its file {DOCKER_EVENTS_REL}"
            + (f" ({problem})" if problem else "")
        )
    coverage_text = _read_text(run_dir / COVERAGE_REL)
    if coverage_text is None:
        return no(f"the capture's coverage verdict ({COVERAGE_REL}) could not be read")
    lines = coverage_text.splitlines()
    if not lines or lines[0] != "coverage=complete":
        return no(
            "the capture is not shown complete (the first line of "
            f"{COVERAGE_REL} is {lines[0] if lines else ''!r}, not 'coverage=complete')"
        )
    values, _other = _key_values(coverage_text)
    for key in ("container", "expected", "requested_since_guest_epoch", "requested_until_guest_epoch"):
        if len(values.get(key, [])) != 1:
            return no(
                f"the capture's coverage verdict gives {key}= "
                f"{len(values.get(key, []))} times, not once: ambiguous"
            )
    if values["container"][0] != CONTAINER:
        return no(
            f"the capture's coverage verdict names container "
            f"{values['container'][0]!r}, not {CONTAINER}"
        )
    expected = values["expected"][0].split(",")
    if "die" not in expected or "start" not in expected:
        return no(
            f"the capture's expected actions {values['expected'][0]!r} do not "
            "include die and start"
        )
    since, until = values["requested_since_guest_epoch"][0], values["requested_until_guest_epoch"][0]
    t0, t1 = _whole_number(since), _whole_number(until)
    if t0 is None or t1 is None or t1 < t0:
        return no(
            "the capture's requested_since_guest_epoch and "
            f"requested_until_guest_epoch ({since!r}, {until!r}) are not a "
            "whole-number window"
        )
    facts["capture_since_guest_epoch"] = t0
    facts["capture_until_guest_epoch"] = t1

    # The die and the start of the container in the window [t0, t1 + 1).
    events_text = _read_text(events_path)
    if events_text is None:
        return no(f"{DOCKER_EVENTS_REL} could not be read")
    dies: list[dict] = []
    starts: list[dict] = []
    for number, line in enumerate(events_text.splitlines(), 1):
        try:
            event = json.loads(line)
        except ValueError:
            event = None
        stamp = event.get("timeNano") if isinstance(event, dict) else None
        if not isinstance(stamp, int) or isinstance(stamp, bool):
            return no(
                f"line {number} of {DOCKER_EVENTS_REL} is not a JSON object with "
                "an integer timeNano"
            )
        if not (t0 * _NS <= stamp < (t1 + 1) * _NS):
            continue
        actor = event.get("Actor")
        attrs = actor.get("Attributes") if isinstance(actor, dict) else None
        if event.get("Type", "container") != "container" or not isinstance(attrs, dict) \
                or attrs.get("name") != CONTAINER:
            continue
        if event.get("Action") == "die":
            dies.append(event)
        elif event.get("Action") == "start":
            starts.append(event)
    facts["die_events_in_window"] = len(dies)
    facts["start_events_in_window"] = len(starts)
    if len(dies) != 1 or len(starts) != 1:
        return no(
            f"{len(dies)} die and {len(starts)} start event(s) of {CONTAINER} in "
            f"the capture window [{t0}, {t1 + 1}): exactly one of each is required"
        )
    die, start = dies[0], starts[0]
    die_id, start_id = die["Actor"].get("ID"), start["Actor"].get("ID")
    if die_id != start_id:
        return no(
            f"the die and the start carry different container ids ({die_id!r}, "
            f"{start_id!r})"
        )
    if not isinstance(die_id, str) or not _CONTAINER_ID.fullmatch(die_id):
        return no(f"the container id {die_id!r} of the die and the start is not 64 lower-case hex")
    d_ns, s_ns = die["timeNano"], start["timeNano"]
    try:
        die_utc, start_utc = ns_utc_text(d_ns), ns_utc_text(s_ns)
    except (OverflowError, OSError, ValueError):
        return no(
            f"the die ({d_ns} ns) or the start ({s_ns} ns) is not an instant "
            "UTC text can name, so the rows' whole seconds cannot be compared "
            "with it"
        )
    if s_ns <= d_ns:
        return no(f"the start at {start_utc} is not after the die at {die_utc}")
    try:
        # The validator looks for the first row one sampling interval after
        # the start's second: that second must be nameable too.
        whole_second(s_ns) + timedelta(seconds=RESOURCE_SAMPLE_INTERVAL_S)
    except OverflowError:
        return no(
            f"the second one sampling interval after the start at {start_utc} is "
            "past the last instant UTC text can name, so no row can be stamped "
            "after the start"
        )
    interval = ProvedDownInterval(container=CONTAINER, die_ns=d_ns, start_ns=s_ns)
    exit_code = die["Actor"]["Attributes"].get("exitCode")
    facts.update({
        "container_id": die_id,
        "die_ns": d_ns,
        "die_utc": die_utc,
        "die_exit_code": exit_code if isinstance(exit_code, str) else None,
        "start_ns": s_ns,
        "start_utc": start_utc,
        "effective_end_ns": interval.effective_end_ns,
        "effective_end_utc": ns_utc_text(interval.effective_end_ns),
        "capped": interval.capped,
        "interval_s": (s_ns - d_ns) / _NS,
        "exempt_s": (interval.effective_end_ns - d_ns) / _NS,
    })

    # The StartedAt record: the same container and id, read after S, within 1 s of S.
    record_text = _read_text(started_path)
    if record_text is None:
        return no(f"the StartedAt record {STARTED_AT_REL} could not be read")
    fields, other = _key_values(record_text)
    malformed = [line for line in other if line.strip()] or sorted(
        key for key in fields if key not in _STARTED_AT_KEYS
    )
    counts = {key: len(fields.get(key, [])) for key in _STARTED_AT_KEYS}
    if malformed or any(n != 1 for n in counts.values()):
        return no(
            f"the StartedAt record {STARTED_AT_REL} is not of the expected form "
            "(exactly one line each of container=, container_id=, started_at= "
            "and guest_epoch=, nothing else)"
        )
    record_fields = {key: fields[key][0] for key in _STARTED_AT_KEYS}
    started_ns = parse_rfc3339_ns(record_fields["started_at"])
    read_epoch = _whole_number(record_fields["guest_epoch"])
    if (
        started_ns is None
        or not _CONTAINER_ID.fullmatch(record_fields["container_id"])
        or read_epoch is None
    ):
        return no(
            f"the StartedAt record {STARTED_AT_REL} is not of the expected form "
            "(a 64 lower-case hex container_id, an RFC 3339 started_at ending Z, "
            "a whole-number guest_epoch)"
        )
    facts.update({
        "started_at": record_fields["started_at"],
        "started_at_ns": started_ns,
        "start_minus_started_at_s": (s_ns - started_ns) / _NS,
        "started_at_read_guest_epoch": read_epoch,
    })
    if record_fields["container"] != CONTAINER:
        return no(
            f"the StartedAt record names container {record_fields['container']!r}, "
            f"not {CONTAINER}"
        )
    if record_fields["container_id"] != die_id:
        return no(
            f"the StartedAt record's container id {record_fields['container_id']} "
            f"differs from the die/start pair's {die_id}"
        )
    if read_epoch * _NS < s_ns:
        return no(
            f"the StartedAt record was read at guest epoch {read_epoch}, before "
            f"the start at {ns_utc_text(s_ns)}"
        )
    if abs(s_ns - started_ns) > STARTED_AT_TOLERANCE_NS:
        return no(
            f"S - StartedAt is {(s_ns - started_ns) / _NS:.9f} s: the start at "
            f"{ns_utc_text(s_ns)} and StartedAt {record_fields['started_at']} "
            "differ by more than 1 s"
        )
    return interval, None, facts


def _lifecycle_stamp(text: str) -> datetime | None:
    match = _LIFECYCLE_STAMP.fullmatch(text)
    if match is None:
        return None
    try:
        return datetime(*(int(g) for g in match.groups()), tzinfo=timezone.utc)
    except ValueError:
        return None


def read_lifecycle_witness(
    path: str | Path | None, container_id: str | None
) -> LifecycleWitness:
    """The collector's lifecycle record of this run (``path``, the run's
    ``<collector CSV>.lifecycle.csv``) as the witness of the restart
    transition rule for ``container_id``, the die/start pair's id.

    Every line after the header ``ts_utc,event,container_id,name`` must be a
    row of the collector's form (a whole-second ``...Z`` stamp, one of
    :data:`LIFECYCLE_EVENTS`, an id and a name, four fields), in
    non-decreasing time; the rows of ``container_id`` or of :data:`CONTAINER`
    are kept, in file order. Anything short of that - no id of the pair, no
    file, a file that cannot be read or is not UTF-8, another header, one row
    not of the form, a row going back in time - gives a witness with its
    ``problem`` named and no rows, which grants nothing. Reads the file only."""

    def no(why: str) -> LifecycleWitness:
        return LifecycleWitness(container=CONTAINER, container_id=container_id, problem=why)

    if not isinstance(container_id, str) or not _CONTAINER_ID.fullmatch(container_id):
        return no(
            "the container id of the die/start pair is not established (64 "
            "lower-case hex), so no row of the collector's lifecycle record "
            "can be matched to it"
        )
    if path is None:
        return no("no collector lifecycle record (.lifecycle.csv) belongs to this run")
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError:
        return no(f"the collector's lifecycle record {path.name} could not be read")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return no(f"the collector's lifecycle record {path.name} is not UTF-8 text")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    if not lines or lines[0] != LIFECYCLE_HEADER:
        return no(
            f"the collector's lifecycle record {path.name} does not start with "
            f"the header {LIFECYCLE_HEADER!r}"
        )
    records: list[LifecycleRecord] = []
    previous: datetime | None = None
    for number, line in enumerate(lines[1:], 2):
        fields = line.split(",")
        stamp = _lifecycle_stamp(fields[0]) if len(fields) == 4 else None
        if (
            stamp is None
            or fields[1] not in LIFECYCLE_EVENTS
            or not _LIFECYCLE_ID.fullmatch(fields[2])
            or not _LIFECYCLE_NAME.fullmatch(fields[3])
        ):
            return no(
                f"line {number} of the collector's lifecycle record {path.name} "
                "is not a lifecycle row of the collector (a whole-second UTC "
                "stamp ending Z, one of appeared/disappeared/counter_reset/named, "
                "a container id and a name, comma-separated)"
            )
        if previous is not None and stamp < previous:
            return no(
                f"line {number} of the collector's lifecycle record {path.name} "
                f"goes back in time ({fields[0]} after {previous.isoformat()}): "
                "out of order"
            )
        previous = stamp
        if fields[2] == container_id or fields[3] == CONTAINER:
            records.append(LifecycleRecord(stamp, fields[1], fields[2], fields[3]))
    return LifecycleWitness(
        container=CONTAINER, container_id=container_id, records=tuple(records)
    )
