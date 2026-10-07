"""Generator-measurement check of one simulator run (G4 pilot prerequisite P5).

``python -m egw_experiments generator-check (--run-dir RUN | --sim-dir DIR)
[--events FILE] [--tolerances FILE] [--window-s 1.0] [--warmup] [--out FILE]``

The plan checks generator delivery on every pilot run: a run whose generator
could not sustain the rate is a pilot finding, not a measurement. A mean rate
cannot show that. The run loop catches up after a stall ("if behind
schedule, publish immediately", ``egw_simulator.runner``), so the count, the
identity set, the first-to-last span and the mean rate of a run with a
mid-run stall are those of a perfect run. This check therefore rebuilds the
exact schedule of the run from the simulator's own manifest with the run
loop's own functions (``scheduled_times``, ``make_devices``, ``split_rate``,
``make_message_id``, the scenario's invalid-event injector and disconnect
windows; imported, never copied) and reads every record of
``sent_events.jsonl`` against it. Event k of a device is due at
``k * (1.0 / rate)`` after the loop's origin, the expression the loop itself
evaluates, and ``seq`` is k.

Sections, each on ONE clock; no figure subtracts a stamp of one clock from a
stamp of another:

- identity and count (exact, no tolerance): the manifest agrees with
  ``make_devices`` / ``split_rate``; every line is a JSON object with exactly
  the record contract's fields and types; every identity is a scheduled one
  of this run, once, with its UUID v5 ``message_id``; the counts equal the
  schedule and ``totals``; the invalid-event flags are the injector's;
  ``publish_monotonic_ns`` never decreases; the run root's copy is byte for
  byte the simulator's.
- generator timing (host monotonic clock): ``publish_monotonic_ns`` is taken
  immediately before the client's publish call, so it measures the client's
  publish-call cadence, NOT the wire send, broker ingress or delivery (paho
  keeps at most 20 QoS 1 messages in flight and queues the rest locally,
  returning at once). The simulator does not record its schedule origin, so
  the origin is inferred as the anchor ``A = min(publish - scheduled
  offset)`` and the lateness is RELATIVE: it omits one unknown constant
  ``c >= 0`` common to every event, which a stall, a ramp or a shortfall
  cannot hide because each of them makes the lateness vary. Reported: the
  relative lateness percentiles, overruns (an event published at or after
  the next scheduled instant, the state in which the loop skips its sleep),
  catch-up bursts (maximal chains of consecutive overrunning instants), the
  publish gaps, per-window counts (a reporting resolution outside the
  verdict), the span against the scheduled span, and the mean rates as a
  summary that cannot detect a mid-run stall.
- PUBACK observations (host clock; never in the verdict): a null puback
  means "not observed within the wait budget", never loss; nulls are split
  into structural (the zero budget of every event but the last of a
  coincident group, and of the run's last event), overrun and other.
- controller acceptance (guest clock; only with ``--events``; never in the
  verdict): arrival and acknowledgement cadence of the controller's copy of
  ``events.jsonl``, its unreadable lines counted, never skipped silently.
- elapsed (harness stamps, host clock; non-certifying): first publish after
  the harness's measured start, run end after the last publish, process time
  against the duration and the harness's kill bound.

Inputs are read as what they must be, every defect named: both manifests
are strict JSON (NaN, infinities and numbers beyond a float are refused), a
schedule with no event is not a schedule, and with ``--run-dir`` the run
directory's ``SHA256SUMS`` must exist and verify (the harness's own
``egw_experiments.checksums`` verification) and its harness manifest, when
present, must be a readable JSON object. A bare simulator directory
(``--sim-dir``) carries no seal of its own and none is verified.

Verdicts and exit codes: SUSTAINED 0 (identity exact, ``completed`` true and
every tolerance of an APPROVED profile entry for the run's scenario and
aggregate rate met); NOT_SHOWN 1 (an input defect: missing, unreadable or
inconsistent files, a seal that is missing or does not verify; never judged
as passed); 2 usage (bad arguments, a ``--window-s`` below
:data:`MIN_WINDOW_S`, an invalid tolerance file, an output that exists, lies
inside the run or a sealed directory, or cannot be written: then no report
is written and no verdict is given);
NOT_CERTIFIED 3 (metrics computed but no profile, a profile that is not
approved, no entry for the condition, or timing not applicable, as for
dropout-reconnect); NOT_SUSTAINED 4 (an approved tolerance exceeded, or a
whole run that did not complete its schedule). Exit 1 only ever means a
NOT_SHOWN evaluation, written to its report.

No tolerance is built in. A profile is a JSON file (:func:`load_tolerances`);
only one whose ``status`` is ``approved`` and whose ``approval`` names who
approved it, the decision record and the date certifies. A ``proposed``
profile is evaluated and labelled non-certifying.

The check only reads. Its JSON report is written once (``--out``, mode
``x``), never inside the run or simulator directory or any directory sealed
by ``SHA256SUMS``; keep it out of ``processed/`` and ``figures/``, which
``analyze`` cleans. The ``execution_mode`` is copied from the harness
manifest when it recorded one and is never inferred.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from egw_simulator.devices import make_devices, split_rate
from egw_simulator.envelope import make_message_id
from egw_simulator.output import SENT_EVENT_FIELDS
from egw_simulator.runner import scheduled_times
from egw_simulator.scenarios import (
    SCENARIOS,
    InvalidInjector,
    dropout_windows,
    window_index,
)

from .analyze import percentile
from .checksums import SUMS_FILENAME, verify_sha256sums
from .environment import utc_now_iso
from .run import MANIFEST_FILENAME, SUBPROCESS_GRACE_S, simulator_run_dir

CHECK_NAME = "egw-generator-check"
CHECK_VERSION = 1

EXIT_SUSTAINED = 0
EXIT_NOT_SHOWN = 1
EXIT_USAGE = 2
EXIT_NOT_CERTIFIED = 3
EXIT_NOT_SUSTAINED = 4

SUSTAINED = "SUSTAINED"
NOT_SHOWN = "NOT_SHOWN"
NOT_CERTIFIED = "NOT_CERTIFIED"
NOT_SUSTAINED = "NOT_SUSTAINED"
VERDICT_EXIT = {
    SUSTAINED: EXIT_SUSTAINED,
    NOT_SHOWN: EXIT_NOT_SHOWN,
    NOT_CERTIFIED: EXIT_NOT_CERTIFIED,
    NOT_SUSTAINED: EXIT_NOT_SUSTAINED,
}

NS = 1_000_000_000

#: Scheduled offsets closer than this are one instant: the slower devices'
#: instants coincide with smart_clothing's up to float rounding (about
#: 1e-15 s). Fixed here, far below the smallest pilot gap (22.4 ms at
#: 50 msg/s); never a tuning knob.
COINCIDENT_S = 1e-6

#: Ids listed per identity category, and problems kept in the report.
LIST_LIMIT = 20
PROBLEM_LIMIT = 200

DEFAULT_WINDOW_S = 1.0
#: The smallest ``--window-s``: the windows table holds one row per window,
#: so a unit slip (1e-6 for 1) would allocate billions of rows on a soak run.
#: A tenth of a second is still finer than the 1 Hz samplers it is read
#: against.
MIN_WINDOW_S = 0.1

#: The harness's layout (run.py): the measured run's simulator output under
#: logs/simulator/<run_id>/, the warm-up's under logs/warmup/<run_id>.warmup/.
SIMULATOR_LOGS = Path("logs") / "simulator"
WARMUP_LOGS = Path("logs") / "warmup"
WARMUP_SUFFIX = ".warmup"
SENT_EVENTS_FILENAME = "sent_events.jsonl"

PROFILE_STATUSES = ("proposed", "approved")
RATE_KEY_FORMAT = "<scenario>@<aggregate rate>"
PROFILE_KEYS = ("profile_id", "status", "approval", "rate_key", "basis", "conditions")
APPROVAL_KEYS = ("approved_by", "decision_record", "date")
TOLERANCE_KEYS = (
    "max_relative_lateness_ms",
    "max_overrun_events",
    "max_span_deviation_ms",
)
_RATE_TEXT_RE = re.compile(r"^[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

HOST_CLOCK = (
    "host monotonic clock (time.monotonic_ns of the simulator process on the "
    "load-generator host)"
)
HARNESS_CLOCK = (
    "host monotonic clock (the harness's time.monotonic_ns on the same host "
    "as the simulator)"
)
GUEST_CLOCK = (
    "guest monotonic clock (time.monotonic_ns of the controller inside the "
    "guest)"
)
MEASURES = {
    "generator": "client publish-call instants (taken before the paho "
    "publish call); not the wire send, broker ingress or delivery",
    "puback": "client-side observation of the QoS 1 acknowledgement within "
    "the wait budget; a null is not loss",
    "acceptance": "controller arrival (after broker queueing) and Ditto "
    "acknowledgement instants",
}
ANCHOR_METHOD = (
    "A = min over the records of (publish_monotonic_ns - scheduled offset); "
    "the simulator does not record its schedule origin, so lateness is "
    "relative: it omits one unknown constant c >= 0 common to every event"
)
PUBACK_STATEMENT = (
    "null = not observed within the wait budget; not evidence of loss; the "
    "publish call is not the wire send (paho keeps at most 20 QoS 1 messages "
    "in flight and queues the rest locally)"
)
CENSORING_NOTE = (
    "right-censored at the wait budget, the free time until the next "
    "scheduled instant (zero inside a coincident group, at the run's last "
    "event and when behind schedule); the stamp is taken after "
    "wait_for_publish returns, so it is an upper bound on the PUBACK arrival"
)
SUMMARY_NOTE = (
    "summary only, never in the verdict: a mean over the first-to-last span "
    "cannot detect a mid-run stall followed by catch-up"
)
WINDOWS_NOTE = (
    "reporting resolution only, outside the verdict: a stall that starts and "
    "ends inside one window is invisible here"
)
TIMING_NOT_APPLICABLE = (
    "dropout-reconnect buffers the events of each disconnect window and "
    "flushes them late by design, and its reconnect blocks; check version 1 "
    "defines no publish-call timing for it"
)
ACCEPTANCE_NOTE = (
    "guest clock: never subtracted from or compared with the host stamps of "
    "the generator, PUBACK and elapsed sections; received is the controller's "
    "arrival after broker queueing, not broker ingress; a served rate below "
    "the offered rate is a system observation, not a generator shortfall"
)


class CheckInputError(Exception):
    """An input cannot be read as what it must be; the verdict is NOT_SHOWN."""


class ToleranceError(ValueError):
    """The tolerance file is not a valid profile: a usage error (exit 2)."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


#: ``time.monotonic_ns`` is a signed 64-bit count: no stamp reaches 2**63.
STAMP_LIMIT_NS = 2**63


def _is_stamp(value: Any) -> bool:
    """A value a ``monotonic_ns`` stamp can be: an integer in [0, 2**63)."""
    return _is_int(value) and 0 <= value < STAMP_LIMIT_NS


def _finite(value: Any) -> bool:
    """A finite number; an integer too large for a float is not one (JSON
    holds such integers, and ``math.isfinite`` raises OverflowError on them)."""
    try:
        return _is_number(value) and math.isfinite(value)
    except OverflowError:
        return False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _brief(value: Any) -> str:
    text = json.dumps(value)
    return text if len(text) <= 40 else text[:37] + "..."


# ---------------------------------------------------------------------------
# Tolerance profiles (no default; only an approved profile certifies)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConditionTolerance:
    max_relative_lateness_ms: float
    max_overrun_events: int
    max_span_deviation_ms: float


@dataclass(frozen=True)
class ToleranceProfile:
    path: str
    sha256: str
    profile_id: str
    status: str
    approval: dict[str, str] | None
    basis: str
    conditions: dict[tuple[str, float], ConditionTolerance]

    @property
    def approved(self) -> bool:
        return self.status == "approved"


def _refuse_constant(name: str) -> None:
    raise ToleranceError(f"{name} is not a number a tolerance can hold")


def _refuse_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ToleranceError(f"key {key!r} appears twice in one object")
        seen[key] = value
    return seen


def _parse_condition_key(key: str) -> tuple[str, float]:
    scenario, sep, rate_text = key.rpartition("@")
    if not sep or scenario not in SCENARIOS:
        raise ToleranceError(
            f"condition {key!r} is not {RATE_KEY_FORMAT} with a known scenario "
            f"({', '.join(SCENARIOS)})"
        )
    if not _RATE_TEXT_RE.fullmatch(rate_text):
        raise ToleranceError(f"condition {key!r}: the rate is not a decimal number")
    rate = float(rate_text)
    if not math.isfinite(rate) or rate <= 0:
        raise ToleranceError(f"condition {key!r}: the rate must be finite and above 0")
    return scenario, rate


def _parse_condition(key: str, value: Any) -> ConditionTolerance:
    if not isinstance(value, dict):
        raise ToleranceError(f"condition {key!r} is not an object")
    unknown = sorted(set(value) - set(TOLERANCE_KEYS))
    if unknown:
        raise ToleranceError(f"condition {key!r}: unknown key(s) {', '.join(unknown)}")
    missing = [name for name in TOLERANCE_KEYS if name not in value]
    if missing:
        raise ToleranceError(f"condition {key!r}: missing {', '.join(missing)}")
    numbers: dict[str, float | int] = {}
    for name in TOLERANCE_KEYS:
        item = value[name]
        integer = name == "max_overrun_events"
        if not _is_number(item) or (integer and not _is_int(item)):
            kind = "an integer" if integer else "a number"
            raise ToleranceError(
                f"condition {key!r}: {name} must be {kind}, got {_brief(item)}"
            )
        if not _finite(item) or item < 0:
            raise ToleranceError(
                f"condition {key!r}: {name} must be finite, within the range of "
                "a float and not negative"
            )
        numbers[name] = item if integer else float(item)
    return ConditionTolerance(**numbers)


def load_tolerances(path: Path) -> ToleranceProfile:
    """Read and validate a tolerance profile; :class:`ToleranceError` if not.

    Keys, all required, no other: ``profile_id`` (non-empty string),
    ``status`` (``proposed`` or ``approved``), ``approval`` (null when
    proposed; when approved an object with exactly ``approved_by``,
    ``decision_record`` and ``date`` (ISO), none empty), ``rate_key`` (the
    literal ``"<scenario>@<aggregate rate>"``, the convention of the condition
    keys), ``basis`` (a non-empty string or list of non-empty strings) and
    ``conditions`` (at least one ``"<scenario>@<aggregate rate>"`` key, each
    with exactly ``max_relative_lateness_ms``, ``max_overrun_events``
    (integer) and ``max_span_deviation_ms``, finite and not negative). The
    rate of a key is matched to the manifest's ``rates_hz.aggregate`` by
    exact float equality; two keys naming the same condition are refused, as
    are booleans, NaN, infinities, integers too large for a float and
    repeated object keys.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise ToleranceError(f"{path} missing") from None
    except OSError as exc:
        raise ToleranceError(f"{path} unreadable: {exc}") from None
    try:
        doc = json.loads(
            data.decode("utf-8"),
            parse_constant=_refuse_constant,
            object_pairs_hook=_refuse_duplicate_keys,
        )
    except ToleranceError as exc:
        raise ToleranceError(f"{path}: {exc}") from None
    except (UnicodeDecodeError, ValueError) as exc:
        raise ToleranceError(f"{path} is not JSON: {exc}") from None
    try:
        return _validate_profile(doc, path=str(path), sha256=_sha256(data))
    except ToleranceError as exc:
        raise ToleranceError(f"{path}: {exc}") from None


def _validate_profile(doc: Any, *, path: str, sha256: str) -> ToleranceProfile:
    if not isinstance(doc, dict):
        raise ToleranceError("the profile is not a JSON object")
    unknown = sorted(set(doc) - set(PROFILE_KEYS))
    if unknown:
        raise ToleranceError(f"unknown key(s) {', '.join(unknown)}")
    missing = [key for key in PROFILE_KEYS if key not in doc]
    if missing:
        raise ToleranceError(f"missing key(s) {', '.join(missing)}")
    profile_id = doc["profile_id"]
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ToleranceError("profile_id must be a non-empty string")
    status = doc["status"]
    if status not in PROFILE_STATUSES:
        raise ToleranceError(
            f"status must be one of {', '.join(PROFILE_STATUSES)}, got {_brief(status)}"
        )
    if doc["rate_key"] != RATE_KEY_FORMAT:
        raise ToleranceError(f"rate_key must be the literal {RATE_KEY_FORMAT!r}")
    basis = doc["basis"]
    if isinstance(basis, list) and basis and all(
        isinstance(item, str) and item.strip() for item in basis
    ):
        basis_text = "\n".join(basis)
    elif isinstance(basis, str) and basis.strip():
        basis_text = basis
    else:
        raise ToleranceError("basis must be a non-empty string or list of non-empty strings")
    approval = doc["approval"]
    if status == "proposed":
        if approval is not None:
            raise ToleranceError("a proposed profile carries no approval (null)")
    else:
        if not isinstance(approval, dict):
            raise ToleranceError(
                "an approved profile needs approval: {approved_by, decision_record, date}"
            )
        extra = sorted(set(approval) - set(APPROVAL_KEYS))
        if extra:
            raise ToleranceError(f"approval: unknown key(s) {', '.join(extra)}")
        for key in APPROVAL_KEYS:
            if not isinstance(approval.get(key), str) or not approval[key].strip():
                raise ToleranceError(f"approval: {key} must be a non-empty string")
        try:
            if not _ISO_DATE_RE.fullmatch(approval["date"]):
                raise ValueError
            date.fromisoformat(approval["date"])
        except ValueError:
            raise ToleranceError("approval: date must be an ISO date (YYYY-MM-DD)") from None
    conditions = doc["conditions"]
    if not isinstance(conditions, dict) or not conditions:
        raise ToleranceError("conditions must be an object naming at least one condition")
    parsed: dict[tuple[str, float], ConditionTolerance] = {}
    for key, value in conditions.items():
        condition = _parse_condition_key(key)
        if condition in parsed:
            raise ToleranceError(f"condition {key!r} names a condition already given")
        parsed[condition] = _parse_condition(key, value)
    return ToleranceProfile(
        path=path,
        sha256=sha256,
        profile_id=profile_id,
        status=status,
        approval=dict(approval) if approval is not None else None,
        basis=basis_text,
        conditions=parsed,
    )


# ---------------------------------------------------------------------------
# The schedule, rebuilt from the simulator manifest with the run loop's code
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScheduledEvent:
    message_id: str
    device_uuid: str
    device_type: str
    seq: int
    offset_s: float
    instant: int
    zero_budget: bool
    intended_invalid: bool
    in_window: bool


@dataclass(frozen=True)
class Schedule:
    run_id: str
    scenario: str
    seed: int
    aggregate_rate_hz: float
    duration_s: float
    #: (device_uuid, seq) -> event, in the run loop's pop order.
    events: dict[tuple[str, int], ScheduledEvent]
    #: Offset of each distinct instant (first event of its group).
    instants: list[float]
    device_types: dict[str, str]
    per_device: dict[str, int]
    smallest_gap_s: float | None
    largest_gap_s: float | None
    scheduled_span_s: float
    structural_zero_budget: int
    invalid_expected: int
    dropout: dict[str, int] | None


def _manifest_shape_problems(manifest: dict) -> list[str]:
    problems = []
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"]:
        problems.append("run_id is not a non-empty string")
    scenario = manifest.get("scenario")
    if not isinstance(scenario, str) or scenario not in SCENARIOS:
        problems.append(
            f"scenario {_brief(scenario)} is not one of {', '.join(SCENARIOS)}"
        )
    if not _is_int(manifest.get("seed")):
        problems.append("seed is not an integer")
    duration = manifest.get("duration_s")
    if not _finite(duration) or duration <= 0:
        problems.append("duration_s is not a finite number above 0")
    rates = manifest.get("rates_hz")
    aggregate = rates.get("aggregate") if isinstance(rates, dict) else None
    if not _finite(aggregate) or aggregate <= 0:
        problems.append("rates_hz.aggregate is not a finite number above 0")
    devices = manifest.get("devices")
    if not isinstance(devices, list) or not devices or not all(
        isinstance(d, dict)
        and set(d) == {"device_type", "device_uuid"}
        and isinstance(d["device_type"], str)
        and isinstance(d["device_uuid"], str)
        for d in devices
    ):
        problems.append("devices is not a non-empty list of {device_type, device_uuid}")
    if not isinstance(manifest.get("completed"), bool):
        problems.append("completed is not a boolean")
    return problems


def reconstruct_schedule(sim_manifest: Any) -> tuple[Schedule | None, list[str]]:
    """The run's exact schedule, or None with the manifest's problems.

    The manifest must agree with itself: its devices are
    ``make_devices(seed, types)`` and its per-device rates are
    ``split_rate(aggregate, types)`` with exact float equality, the floats
    the run loop used. Events are ordered as the loop pops them, by
    (scheduled offset, device index, seq).
    """
    if not isinstance(sim_manifest, dict):
        return None, ["the simulator manifest is not a JSON object"]
    problems = _manifest_shape_problems(sim_manifest)
    if problems:
        return None, problems
    run_id = sim_manifest["run_id"]
    scenario = sim_manifest["scenario"]
    seed = sim_manifest["seed"]
    duration = float(sim_manifest["duration_s"])
    aggregate = sim_manifest["rates_hz"]["aggregate"]
    types = [d["device_type"] for d in sim_manifest["devices"]]
    try:
        devices = make_devices(seed, types)
        rates = split_rate(aggregate, types)
    except ValueError as exc:
        return None, [f"device types: {exc}"]
    listed = [{"device_type": d.device_type, "device_uuid": d.device_uuid} for d in devices]
    if listed != sim_manifest["devices"]:
        problems.append("devices are not make_devices(seed, device types)")
    if len({d.device_uuid for d in devices}) != len(devices):
        problems.append("device_uuid values are not unique (a device type listed twice)")
    per_device = sim_manifest["rates_hz"].get("per_device")
    if (
        not isinstance(per_device, dict)
        or not all(_is_number(v) for v in per_device.values())
        or per_device != rates
    ):
        problems.append(
            "rates_hz.per_device is not split_rate(aggregate, device types) "
            "exactly (the floats the run loop used)"
        )
    if problems:
        return None, problems

    spec = SCENARIOS[scenario]
    windows = dropout_windows(seed, duration) if spec.dropout else []
    raw: list[tuple[float, int, int]] = []
    injectors: list[InvalidInjector | None] = []
    for index, device in enumerate(devices):
        injectors.append(
            InvalidInjector(seed, device.device_uuid, spec.invalid_ratio)
            if spec.invalid_ratio
            else None
        )
        for seq, offset in enumerate(scheduled_times(rates[device.device_type], duration)):
            raw.append((offset, index, seq))
    if not raw:
        # The simulator accepts any duration above 0; below its schedule
        # epsilon the run loop schedules nothing, and there is nothing to check.
        return None, [
            f"no scheduled event: duration_s {_brief(duration)} at "
            f"{_brief(aggregate)} msg/s gives an empty schedule"
        ]
    raw.sort()

    instants: list[float] = []
    instant_of: list[int] = []
    for offset, _index, _seq in raw:
        if not instants or offset - instants[-1] > COINCIDENT_S:
            instants.append(offset)
        instant_of.append(len(instants) - 1)

    events: dict[tuple[str, int], ScheduledEvent] = {}
    windows_used: set[int] = set()
    structural = buffered = invalid = 0
    for position, (offset, index, seq) in enumerate(raw):
        device = devices[index]
        last_of_group = (
            position + 1 == len(raw) or instant_of[position + 1] != instant_of[position]
        )
        # The loop's wait budget is the free time until the next scheduled
        # event: zero for every event of a coincident group but the last,
        # and for the run's last event (nothing left on the heap).
        structural_zero = not last_of_group or position + 1 == len(raw)
        window = window_index(offset, windows) if windows else None
        if window is not None:
            windows_used.add(window)
            buffered += 1
        injector = injectors[index]
        flagged = injector is not None and injector.is_invalid(seq)
        structural += structural_zero
        invalid += flagged
        events[(device.device_uuid, seq)] = ScheduledEvent(
            message_id=make_message_id(run_id, device.device_uuid, seq),
            device_uuid=device.device_uuid,
            device_type=device.device_type,
            seq=seq,
            offset_s=offset,
            instant=instant_of[position],
            # A flushed (buffered) event is published with a zero budget too.
            zero_budget=structural_zero or window is not None,
            intended_invalid=flagged,
            in_window=window is not None,
        )
    gaps = [b - a for a, b in zip(instants, instants[1:])]
    return Schedule(
        run_id=run_id,
        scenario=scenario,
        seed=seed,
        aggregate_rate_hz=float(aggregate),
        duration_s=duration,
        events=events,
        instants=instants,
        device_types={d.device_uuid: d.device_type for d in devices},
        per_device={
            d.device_uuid: len(scheduled_times(rates[d.device_type], duration))
            for d in devices
        },
        smallest_gap_s=min(gaps) if gaps else None,
        largest_gap_s=max(gaps) if gaps else None,
        scheduled_span_s=raw[-1][0] - raw[0][0],
        structural_zero_budget=structural,
        invalid_expected=invalid,
        dropout=(
            {
                "windows": len(windows),
                "buffered_expected": buffered,
                "disconnects_expected": len(windows_used),
            }
            if spec.dropout
            else None
        ),
    ), []


# ---------------------------------------------------------------------------
# Strict reading of sent_events.jsonl: every defect named, none skipped
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SentRead:
    path: Path
    sha256: str
    lines: int
    #: (line number, record) of every line that is a well-formed record.
    records: list[tuple[int, dict]]
    problems: list[str]


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        raise CheckInputError(f"{path} missing") from None
    except OSError as exc:
        raise CheckInputError(f"{path} unreadable: {exc}") from None


def _record_problems(record: dict) -> list[str]:
    found = []
    missing = [key for key in SENT_EVENT_FIELDS if key not in record]
    extra = sorted(key for key in record if key not in SENT_EVENT_FIELDS)
    if missing:
        found.append(f"missing field(s) {', '.join(missing)}")
    if extra:
        found.append(f"unexpected field(s) {', '.join(extra)}")
    for key in ("run_id", "message_id", "device_uuid", "device_type"):
        if key in record and not isinstance(record[key], str):
            found.append(f"{key} must be a string, got {_brief(record[key])}")
    if "seq" in record and (not _is_int(record["seq"]) or record["seq"] < 0):
        found.append(
            f"seq must be a non-negative integer (not a boolean), got "
            f"{_brief(record['seq'])}"
        )
    if "publish_monotonic_ns" in record and not _is_stamp(record["publish_monotonic_ns"]):
        found.append(
            "publish_monotonic_ns must be a non-negative integer below 2**63 (not a "
            f"boolean), got {_brief(record['publish_monotonic_ns'])}"
        )
    puback = record.get("puback_monotonic_ns")
    if "puback_monotonic_ns" in record and puback is not None and not _is_stamp(puback):
        found.append(
            "puback_monotonic_ns must be a non-negative integer below 2**63 or null, "
            f"got {_brief(puback)}"
        )
    if "intended_invalid" in record and not isinstance(record["intended_invalid"], bool):
        found.append(
            f"intended_invalid must be a boolean, got {_brief(record['intended_invalid'])}"
        )
    return found


def read_sent_events(path: Path) -> SentRead:
    """Every line of ``sent_events.jsonl`` read strictly.

    The writer emits one newline-terminated JSON object per publish with
    exactly the contract's fields; a line that is empty, not JSON, not an
    object, missing a field, holding an extra one or a wrong type (a boolean
    is not an integer), or a last line without its newline (a truncated
    write) is a problem named by its line number, never skipped silently.
    :class:`CheckInputError` when the file is missing, unreadable or not
    UTF-8.
    """
    data = _read_bytes(path)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckInputError(f"{path} is not UTF-8: {exc}") from None
    pieces = text.split("\n")
    terminated = pieces[-1] == ""
    if terminated:
        pieces.pop()
    name = path.name
    problems: list[str] = []
    records: list[tuple[int, dict]] = []
    for number, line in enumerate(pieces, 1):
        if not terminated and number == len(pieces):
            problems.append(f"{name} line {number}: no final newline (truncated write?)")
        if not line.strip():
            problems.append(f"{name} line {number}: empty line")
            continue
        try:
            record = json.loads(line)
        except ValueError:
            problems.append(f"{name} line {number}: not valid JSON (truncated write?)")
            continue
        if not isinstance(record, dict):
            problems.append(f"{name} line {number}: not a JSON object")
            continue
        found = _record_problems(record)
        if found:
            problems.extend(f"{name} line {number}: {problem}" for problem in found)
            continue
        records.append((number, record))
    return SentRead(
        path=path, sha256=_sha256(data), lines=len(pieces), records=records,
        problems=problems,
    )


# ---------------------------------------------------------------------------
# A. Identity and count (exact; no tolerance)
# ---------------------------------------------------------------------------


def _ids(items: list[str]) -> dict:
    return {"count": len(items), "ids": items[:LIST_LIMIT]}


def check_identity(
    schedule: Schedule, sent: SentRead, sim_manifest: dict
) -> tuple[dict, list[str], list[tuple[dict, ScheduledEvent]]]:
    """(identity section, problems, usable (record, event) pairs in file order).

    A usable record is a scheduled identity of this run, first seen, with the
    manifest's device_type and its UUID v5 message_id. With ``completed``
    true every scheduled event must have its record; with ``completed``
    false (an interrupted run) the records must be a prefix of the schedule
    in the loop's pop order and agree with ``totals.sent`` (dropout-reconnect
    excepted from the prefix rule: a buffer may be unflushed).
    """
    completed = sim_manifest.get("completed") is True
    totals = sim_manifest.get("totals")
    totals = totals if isinstance(totals, dict) else {}
    foreign: list[str] = []
    unexpected: list[str] = []
    out_of_range: list[str] = []
    duplicates: list[str] = []
    message_id_mismatch: list[str] = []
    device_type_mismatch: list[str] = []
    invalid_mismatch: list[str] = []
    seen: set[tuple[str, int]] = set()
    usable: list[tuple[dict, ScheduledEvent]] = []
    for _number, record in sent.records:
        message_id = record["message_id"]
        if record["run_id"] != schedule.run_id:
            foreign.append(message_id)
            continue
        key = (record["device_uuid"], record["seq"])
        event = schedule.events.get(key)
        if event is None:
            unexpected.append(message_id)
            if record["device_uuid"] in schedule.device_types:
                out_of_range.append(message_id)
            continue
        bad = False
        if record["device_type"] != event.device_type:
            device_type_mismatch.append(message_id)
            bad = True
        if message_id != event.message_id:
            message_id_mismatch.append(message_id)
            bad = True
        if key in seen:
            duplicates.append(message_id)
            bad = True
        if bad:
            continue
        seen.add(key)
        if record["intended_invalid"] != event.intended_invalid:
            invalid_mismatch.append(message_id)
        usable.append((record, event))
    missing = [event.message_id for key, event in schedule.events.items() if key not in seen]

    problems: list[str] = []

    def note(items: list[str], text: str) -> None:
        if items:
            problems.append(f"{len(items)} {text}")

    note(
        foreign,
        f"record(s) carry a run_id other than the simulator manifest's ({schedule.run_id!r})",
    )
    unknown_device = len(unexpected) - len(out_of_range)
    if unknown_device:
        problems.append(
            f"{unknown_device} record(s) name a device_uuid that is not one of the "
            "manifest's devices"
        )
    note(out_of_range, "record(s) carry a seq beyond their device's schedule")
    note(
        device_type_mismatch,
        "record(s) carry a device_type other than the manifest's for their device_uuid",
    )
    note(
        message_id_mismatch,
        "record(s) carry a message_id that is not the UUID v5 of run_id:device_uuid:seq",
    )
    note(duplicates, "duplicate (device_uuid, seq) record(s)")
    note(invalid_mismatch, "record(s) whose intended_invalid flag is not the injector's")

    records = len(sent.records)
    totals_sent = totals.get("sent")
    if not _is_int(totals_sent):
        problems.append("the simulator manifest carries no integer totals.sent")
    elif totals_sent != records:
        problems.append(
            f"totals.sent is {totals_sent} but sent_events.jsonl holds {records} "
            "readable record(s)"
        )
    flagged = sum(1 for _number, record in sent.records if record["intended_invalid"])
    totals_invalid = totals.get("intended_invalid")
    if totals_invalid != flagged or not _is_int(totals_invalid):
        problems.append(
            f"totals.intended_invalid is {_brief(totals_invalid)} but {flagged} "
            "record(s) are flagged"
        )
    expected_dropout = schedule.dropout or {"buffered_expected": 0, "disconnects_expected": 0}
    if completed:
        if missing:
            problems.append(
                f"{len(missing)} scheduled event(s) have no record (the schedule "
                f"has {len(schedule.events)})"
            )
        if totals_invalid != schedule.invalid_expected:
            problems.append(
                f"totals.intended_invalid is {_brief(totals_invalid)} but the "
                f"injector flags {schedule.invalid_expected} scheduled event(s)"
            )
        for field, expected in (
            ("buffered_dropout", expected_dropout["buffered_expected"]),
            ("dropout_disconnects", expected_dropout["disconnects_expected"]),
        ):
            if totals.get(field) != expected or not _is_int(totals.get(field)):
                problems.append(
                    f"totals.{field} is {_brief(totals.get(field))} but the "
                    f"schedule gives {expected}"
                )
    elif schedule.dropout is None:
        prefix = set(list(schedule.events)[: len(seen)])
        if prefix != seen:
            problems.append(
                "the records of an interrupted run are not a prefix of the "
                "schedule in the run loop's order"
            )

    decreases, first_at, last = 0, None, None
    for number, record in sent.records:
        stamp = record["publish_monotonic_ns"]
        if last is not None and stamp < last:
            decreases += 1
            first_at = first_at or number
        last = stamp
    if decreases:
        problems.append(
            f"publish_monotonic_ns decreases {decreases} time(s) in file order "
            f"(first at line {first_at}); the writer appends in publish order"
        )

    recorded_per_device = Counter(event.device_uuid for _record, event in usable)
    identity = {
        "exact": not problems and completed and not missing,
        "consistent": not problems,
        "records": records,
        "events_expected": len(schedule.events),
        "per_device": {
            schedule.device_types[uuid]: {
                "device_uuid": uuid,
                "expected": expected,
                "recorded": recorded_per_device.get(uuid, 0),
            }
            for uuid, expected in schedule.per_device.items()
        },
        "missing": _ids(missing),
        "unexpected": _ids(unexpected),
        "duplicates": _ids(duplicates),
        "foreign_run_id": _ids(foreign),
        "message_id_mismatch": _ids(message_id_mismatch),
        "device_type_mismatch": _ids(device_type_mismatch),
        "seq_out_of_range": _ids(out_of_range),
        "totals_sent": totals_sent,
        "totals_match": _is_int(totals_sent) and totals_sent == records,
        "intended_invalid": {
            "recorded": flagged,
            "expected": schedule.invalid_expected,
            "totals": totals_invalid,
            "mismatches": len(invalid_mismatch),
        },
        "dropout": {
            "buffered_expected": expected_dropout["buffered_expected"],
            "buffered_recorded": totals.get("buffered_dropout"),
            "disconnects_expected": expected_dropout["disconnects_expected"],
            "disconnects_recorded": totals.get("dropout_disconnects"),
        },
        "publish_order_nondecreasing": decreases == 0,
    }
    return identity, problems, usable


# ---------------------------------------------------------------------------
# B. Generator timing (host monotonic clock)
# ---------------------------------------------------------------------------


def _window(offset_s: float, window_s: float) -> int:
    # COINCIDENT_S keeps a scheduled instant that float rounding put a hair
    # below a window boundary in the same window as its publish.
    return math.floor((offset_s + COINCIDENT_S) / window_s)


def generator_timing(
    schedule: Schedule,
    usable: list[tuple[dict, ScheduledEvent]],
    *,
    window_s: float = DEFAULT_WINDOW_S,
    partial: bool = False,
) -> tuple[dict, list[bool] | None]:
    """Section B and, per usable record, whether it overran (None when the
    timing is not computed)."""
    base = {"clock_domain": HOST_CLOCK, "measures": MEASURES["generator"]}
    if SCENARIOS[schedule.scenario].dropout:
        return {**base, "applicable": False, "reason": TIMING_NOT_APPLICABLE}, None
    if not usable:
        return {
            **base, "applicable": True, "partial": True, "computed": False,
            "reason": "no usable record",
        }, None
    publish = [record["publish_monotonic_ns"] for record, _event in usable]
    offsets = [event.offset_s for _record, event in usable]
    shifted = [p - t * NS for p, t in zip(publish, offsets)]
    anchor = min(shifted)
    lateness_ms = [(value - anchor) / 1e6 for value in shifted]
    anchored = [p - anchor for p in publish]  # ns since the inferred origin
    worst = max(range(len(usable)), key=lateness_ms.__getitem__)

    instants = schedule.instants
    overran = [
        event.instant + 1 < len(instants)
        and anchored[i] >= instants[event.instant + 1] * NS
        for i, (_record, event) in enumerate(usable)
    ]
    by_instant: dict[int, list[int]] = {}
    for i, flag in enumerate(overran):
        if flag:
            by_instant.setdefault(usable[i][1].instant, []).append(i)
    chains: list[list[int]] = []
    for instant in sorted(by_instant):
        if chains and instant == chains[-1][-1] + 1:
            chains[-1].append(instant)
        else:
            chains.append([instant])
    bursts = []
    for chain in chains:
        members = sorted(i for instant in chain for i in by_instant[instant])
        stamps = [publish[i] for i in members]
        span_ns = max(stamps) - min(stamps)
        bursts.append({
            "events": len(members),
            "first_offset_s": instants[chain[0]],
            "last_offset_s": instants[chain[-1]],
            "publish_span_ms": span_ns / 1e6,
            "peak_rate_hz": (len(members) - 1) * NS / span_ns
            if span_ns > 0 and len(members) > 1
            else None,
            "stall_estimate_ms": lateness_ms[members[0]],
        })
    largest = max(bursts, key=lambda burst: burst["events"]) if bursts else None

    gaps = [publish[i + 1] - publish[i] for i in range(len(publish) - 1)]
    if gaps:
        widest = max(range(len(gaps)), key=gaps.__getitem__)
        excess = max(
            gaps[i] - (offsets[i + 1] - offsets[i]) * NS for i in range(len(gaps))
        )
        publish_gaps = {
            "max": gaps[widest] / 1e6,
            "max_at_offset_s": offsets[widest + 1],
            "max_excess_over_schedule_ms": excess / 1e6,
        }
    else:
        publish_gaps = {"max": None, "max_at_offset_s": None, "max_excess_over_schedule_ms": None}

    scheduled_counts = Counter(_window(t, window_s) for t in offsets)
    published_counts = Counter(_window(a / NS, window_s) for a in anchored)
    last_window = max(max(scheduled_counts), max(published_counts))
    differences = [
        (k, scheduled_counts.get(k, 0), published_counts.get(k, 0))
        for k in range(0, last_window + 1)
    ]
    nonzero = [row for row in differences if row[1] != row[2]]
    windows = {
        "window_s": window_s,
        "count": len(differences),
        "max_deficit": min([0] + [q - s for _k, s, q in differences]),
        "max_excess": max([0] + [q - s for _k, s, q in differences]),
        "nonzero": len(nonzero),
        "worst": [
            {"start_s": k * window_s, "scheduled": s, "published": q, "difference": q - s}
            for k, s, q in sorted(nonzero, key=lambda row: (-abs(row[2] - row[1]), row[0]))[:10]
        ],
        "note": WINDOWS_NOTE,
    }

    published_span_ns = max(publish) - min(publish)
    scheduled_span_s = max(offsets) - min(offsets)
    timing = {
        **base,
        "applicable": True,
        "partial": partial,
        "computed": True,
        "records": len(usable),
        "anchor": {
            "method": ANCHOR_METHOD,
            "anchor_ns": round(anchor),
            "c_upper_bound_s": None,
        },
        "relative_lateness_ms": {
            "p50": percentile(lateness_ms, 50),
            "p95": percentile(lateness_ms, 95),
            "p99": percentile(lateness_ms, 99),
            "p999": percentile(lateness_ms, 99.9),
            "max": lateness_ms[worst],
            "max_message_id": usable[worst][1].message_id,
            "max_offset_s": offsets[worst],
        },
        "overruns": {
            "events": sum(overran),
            "bursts": len(bursts),
            "largest": largest,
            "list": bursts[:LIST_LIMIT],
        },
        "publish_gaps_ms": publish_gaps,
        "windows": windows,
        "span": {
            "published_s": published_span_ns / NS,
            "scheduled_s": scheduled_span_s,
            "deviation_ms": (published_span_ns - scheduled_span_s * NS) / 1e6,
        },
        "summary_rates": {
            "requested_hz": schedule.aggregate_rate_hz,
            "schedule_n_over_duration_hz": len(schedule.events) / schedule.duration_s,
            "first_to_last_hz": (len(publish) - 1) * NS / published_span_ns
            if published_span_ns > 0
            else None,
            "note": SUMMARY_NOTE,
        },
    }
    return timing, overran


# ---------------------------------------------------------------------------
# C. PUBACK observations (host clock; never in the verdict)
# ---------------------------------------------------------------------------


def puback_observations(
    schedule: Schedule,
    usable: list[tuple[dict, ScheduledEvent]],
    overran: list[bool] | None,
) -> dict:
    observed = [
        (record["puback_monotonic_ns"] - record["publish_monotonic_ns"]) / 1e6
        for record, _event in usable
        if record["puback_monotonic_ns"] is not None
    ]
    null_structural = null_overrun = null_other = 0
    population = observed_in_population = 0
    for i, (record, event) in enumerate(usable):
        late = overran is not None and overran[i]
        is_null = record["puback_monotonic_ns"] is None
        if not event.zero_budget and not late:
            population += 1
            observed_in_population += not is_null
        if not is_null:
            continue
        if event.zero_budget:
            null_structural += 1
        elif late:
            null_overrun += 1
        else:
            null_other += 1
    return {
        "clock_domain": HOST_CLOCK,
        "measures": MEASURES["puback"],
        "records": len(usable),
        "observed": len(observed),
        "null": len(usable) - len(observed),
        "structural_zero_budget": sum(event.zero_budget for _record, event in usable),
        "null_structural": null_structural,
        "null_overrun": null_overrun if overran is not None else None,
        "null_other": null_other,
        "positive_budget_population": population,
        "observed_fraction_positive_budget": observed_in_population / population
        if population
        else None,
        "observation_delay_ms": {
            "p50": percentile(observed, 50),
            "p95": percentile(observed, 95),
            "p99": percentile(observed, 99),
            "max": max(observed) if observed else None,
        },
        "puback_before_publish": sum(1 for delay in observed if delay < 0),
        "censoring_bound_ms": schedule.largest_gap_s * 1000
        if schedule.largest_gap_s is not None
        else None,
        "censoring_note": CENSORING_NOTE,
        "statement": PUBACK_STATEMENT,
    }


# ---------------------------------------------------------------------------
# D. Controller acceptance (guest clock; never in the verdict)
# ---------------------------------------------------------------------------


def _cadence(stamps: list[int], window_s: float) -> dict:
    if not stamps:
        return {"n": 0, "span_s": None, "max_gap_ms": None, "windows": None}
    ordered = sorted(stamps)
    span_ns = ordered[-1] - ordered[0]
    gaps = [b - a for a, b in zip(ordered, ordered[1:])]
    counts = Counter(math.floor((s - ordered[0]) / NS / window_s) for s in ordered)
    per_window = [counts.get(k, 0) for k in range(max(counts) + 1)]
    return {
        "n": len(ordered),
        "span_s": span_ns / NS,
        "max_gap_ms": max(gaps) / 1e6 if gaps else None,
        "windows": {
            "window_s": window_s,
            "count": len(per_window),
            "min": min(per_window),
            "max": max(per_window),
            "empty": per_window.count(0),
        },
    }


def controller_acceptance(events_path: Path, run_id: str | None, *, window_s: float) -> dict:
    """Section D from one copy of the controller's ``events.jsonl``.

    Every non-blank line is counted: unreadable lines (a torn final line
    included) and lines of another run are reported, never skipped silently.
    Spans, gaps and windows are computed on the guest stamps of this run's
    lines alone, relative to their own first stamp.
    """
    events_path = Path(events_path)
    section: dict[str, Any] = {
        "clock_domain": GUEST_CLOCK,
        "measures": MEASURES["acceptance"],
        "events_copy": {"path": str(events_path), "sha256": None},
        "note": ACCEPTANCE_NOTE,
    }
    try:
        data = _read_bytes(events_path)
        text = data.decode("utf-8")
    except CheckInputError as exc:
        return {**section, "error": str(exc)}
    except UnicodeDecodeError as exc:
        return {**section, "error": f"{events_path} is not UTF-8: {exc}"}
    section["events_copy"]["sha256"] = _sha256(data)
    lines = unreadable = other = backwards = 0
    accepted_without_ack = without_received = 0
    outcomes: Counter = Counter()
    received: list[int] = []
    acked: list[int] = []
    last = None
    for line in text.split("\n"):
        if not line.strip():
            continue
        lines += 1
        try:
            record = json.loads(line)
        except ValueError:
            record = None
        if not isinstance(record, dict):
            unreadable += 1
            continue
        if record.get("run_id") != run_id:
            other += 1
            continue
        outcome = record.get("outcome")
        outcomes[outcome if isinstance(outcome, str) else _brief(outcome)] += 1
        stamp = record.get("received_monotonic_ns")
        if _is_stamp(stamp):
            received.append(stamp)
            # One consumer logs in arrival order, so within one clock the
            # received stamps never decrease along the file; a decrease is a
            # restarted clock (itest_reconcile counts it the same way).
            if last is not None and stamp < last:
                backwards += 1
            last = stamp
        else:
            without_received += 1
        if outcome == "accepted":
            ack = record.get("ditto_ack_monotonic_ns")
            if _is_stamp(ack):
                acked.append(ack)
            else:
                accepted_without_ack += 1
    accepted = _cadence(acked, window_s)
    accepted["served_rate_hz"] = (
        (accepted["n"] - 1) / accepted["span_s"]
        if accepted["n"] > 1 and accepted["span_s"]
        else None
    )
    return {
        **section,
        "error": None,
        "lines": lines,
        "unreadable": unreadable,
        "other_run_id": other,
        "outcomes": dict(sorted(outcomes.items())),
        "received_missing": without_received,
        "accepted_without_ack": accepted_without_ack,
        "received": _cadence(received, window_s),
        "accepted_ack": accepted,
        "clock_backwards": backwards,
    }


# ---------------------------------------------------------------------------
# E. Elapsed time (harness stamps; non-certifying)
# ---------------------------------------------------------------------------


def harness_elapsed(
    harness_manifest: dict | None,
    usable: list[tuple[dict, ScheduledEvent]],
    duration_s: float,
) -> dict | None:
    if harness_manifest is None or not usable:
        return None
    started = harness_manifest.get("measured_started_monotonic_ns")
    finished = harness_manifest.get("finished_monotonic_ns")
    publish = [record["publish_monotonic_ns"] for record, _event in usable]
    # A value no monotonic_ns stamp can be is no stamp (non-certifying section).
    started = started if _is_stamp(started) else None
    finished = finished if _is_stamp(finished) else None
    process = (finished - started) / NS if started is not None and finished is not None else None
    kill_bound = duration_s + SUBPROCESS_GRACE_S
    return {
        "clock_domain": HARNESS_CLOCK,
        "measured_started_ns": started,
        "finished_ns": finished,
        "first_publish_after_start_s": (min(publish) - started) / NS
        if started is not None
        else None,
        "finished_after_last_publish_s": (finished - max(publish)) / NS
        if finished is not None
        else None,
        "process_elapsed_s": process,
        "duration_s": duration_s,
        "kill_bound_s": kill_bound,
        "within_kill_bound": process <= kill_bound if process is not None else None,
        "simulator_returncode": harness_manifest.get("simulator_returncode"),
    }


# ---------------------------------------------------------------------------
# Evaluation: the verdict (sections C, D and E never change it)
# ---------------------------------------------------------------------------


def _rate_key(scenario: Any, rate: Any) -> str | None:
    if not isinstance(scenario, str) or not _finite(rate):
        return None
    return f"{scenario}@{float(rate)!r}"


def evaluate(report: dict, profile: ToleranceProfile | None) -> dict:
    run = report["run"]
    timing = report.get("generator_timing")
    inputs = report["inputs"]
    result: dict[str, Any] = {
        "profile_id": profile.profile_id if profile else None,
        "profile_status": profile.status if profile else None,
        "profile_sha256": profile.sha256 if profile else None,
        "decision_record": (profile.approval or {}).get("decision_record") if profile else None,
        "rate_key": _rate_key(run.get("scenario"), run.get("aggregate_rate_hz")),
        "certifying": False,
        "per_tolerance": [],
        "verdict": None,
        "reasons": [],
    }

    def done(verdict: str, *reasons: str) -> dict:
        result["verdict"] = verdict
        result["reasons"] = list(reasons)
        return result

    if inputs["problem_count"]:
        shown = inputs["problems"][:LIST_LIMIT]
        more = inputs["problem_count"] - len(shown)
        return done(
            NOT_SHOWN,
            "not shown to be this run's whole schedule; nothing is judged as passed",
            *shown,
            *([f"... and {more} more problem(s) in the JSON report"] if more else []),
        )
    if run.get("completed") is not True:
        return done(
            NOT_SUSTAINED,
            "the simulator manifest says completed is not true: the schedule "
            "was not finished (an interrupted run)",
        )
    if not timing or not timing.get("applicable") or not timing.get("computed"):
        state = "not applicable" if timing and not timing.get("applicable") else "not computed"
        reason = timing.get("reason") if timing else "no schedule or no records"
        return done(NOT_CERTIFIED, f"generator timing {state}: {reason}")
    if profile is None:
        return done(
            NOT_CERTIFIED,
            "no tolerance profile (--tolerances): no tolerance is built in, and "
            "no report certifies without an approved profile",
        )
    tolerance = profile.conditions.get((run["scenario"], float(run["aggregate_rate_hz"])))
    if tolerance is None:
        return done(
            NOT_CERTIFIED,
            f"the profile {profile.profile_id!r} has no entry for {result['rate_key']}",
        )
    rows = [
        {
            "name": "max_relative_lateness_ms",
            "limit": tolerance.max_relative_lateness_ms,
            "value": timing["relative_lateness_ms"]["max"],
        },
        {
            "name": "max_overrun_events",
            "limit": tolerance.max_overrun_events,
            "value": timing["overruns"]["events"],
        },
        {
            "name": "max_span_deviation_ms",
            "limit": tolerance.max_span_deviation_ms,
            "value": abs(timing["span"]["deviation_ms"]),
        },
    ]
    for row in rows:
        row["within"] = row["value"] <= row["limit"]
    result["per_tolerance"] = rows
    if not profile.approved:
        return done(
            NOT_CERTIFIED,
            f"the profile {profile.profile_id!r} has status {profile.status!r}: "
            "the per-tolerance results are reported, labelled non-certifying; "
            "only a profile with status 'approved' that names its decision "
            "record certifies",
        )
    result["certifying"] = True
    outside = [row for row in rows if not row["within"]]
    if outside:
        return done(
            NOT_SUSTAINED,
            *(
                f"{row['name']}: {row['value']} exceeds the approved limit {row['limit']}"
                for row in outside
            ),
        )
    return done(
        SUSTAINED,
        f"every tolerance of the approved profile {profile.profile_id!r} "
        f"(decision record {profile.approval['decision_record']}) is met for "
        f"{result['rate_key']}",
    )


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


class _NotStrictJson(ValueError):
    """A number that strict JSON cannot hold (and the report could not)."""


def _refuse_non_finite_constant(name: str) -> None:
    raise _NotStrictJson(f"holds {name}, which is not a JSON number")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise _NotStrictJson(f"holds {text}, which is beyond the range of a float")
    return value


def _read_json_object(path: Path) -> tuple[dict | None, str | None, str | None]:
    """(object, sha256, problem): the problem names a missing, unreadable or
    non-object file; the object is None then.

    Strict JSON: NaN, Infinity, -Infinity and a number literal beyond the
    range of a float are refused here, so no value copied into the report
    can stop it from being written (it is serialised with
    ``allow_nan=False``)."""
    try:
        data = _read_bytes(path)
    except CheckInputError as exc:
        return None, None, str(exc)
    try:
        obj = json.loads(
            data.decode("utf-8"),
            parse_constant=_refuse_non_finite_constant,
            parse_float=_finite_float,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        return None, _sha256(data), f"{path} unreadable: {exc}"
    if not isinstance(obj, dict):
        return None, _sha256(data), f"{path} is not a JSON object"
    return obj, _sha256(data), None


def _seal_state(run_dir: Path) -> tuple[dict, list[str]]:
    """(the seal section, problems) of a harness run directory.

    The run directory's ``SHA256SUMS`` must exist and verify, with the
    harness's own verification (``egw_experiments.checksums``, as
    ``verify-checksums`` and ``analyze`` use it): otherwise its files are
    not shown to be the run's record, and nothing is judged as passed.
    """
    sums_path = run_dir / SUMS_FILENAME
    section: dict[str, Any] = {
        "applicable": True,
        "path": str(sums_path),
        "verification": "egw_experiments.checksums.verify_sha256sums",
        "state": None,
        "problem_count": 0,
        "problems": [],
    }
    if not sums_path.is_file():
        section["state"] = "missing"
        return section, [
            f"{SUMS_FILENAME} missing in {run_dir}: the run directory is not "
            "sealed, so its files are not shown to be the run's record"
        ]
    try:
        found = verify_sha256sums(run_dir)
    except (OSError, UnicodeDecodeError) as exc:
        section["state"] = "unreadable"
        return section, [f"{SUMS_FILENAME} of {run_dir} cannot be verified: {exc}"]
    section["state"] = "failed" if found else "verified"
    section["problem_count"] = len(found)
    section["problems"] = found[:PROBLEM_LIMIT]
    return section, [f"{SUMS_FILENAME} does not verify: {problem}" for problem in found]


def check_generator(
    *,
    sim_dir: Path | None = None,
    run_dir: Path | None = None,
    events_path: Path | None = None,
    profile: ToleranceProfile | None = None,
    window_s: float = DEFAULT_WINDOW_S,
    warmup: bool = False,
) -> dict:
    """The full report of one run; ``report['evaluation']['verdict']``.

    ``run_dir`` is a harness run directory: its ``SHA256SUMS`` must exist
    and verify, and the simulator output is read from
    ``logs/simulator/<run_id>/`` (or the warm-up's), where ``run_id`` is the
    harness manifest's (the directory's name without one). ``sim_dir`` is a
    bare simulator output directory, with no seal of its own. Exactly one is
    given. ``window_s`` is at least :data:`MIN_WINDOW_S`.
    """
    if (sim_dir is None) == (run_dir is None):
        raise ValueError("give exactly one of sim_dir and run_dir")
    if warmup and run_dir is None:
        raise ValueError("the warm-up is read from a harness run directory")
    if not (_finite(window_s) and window_s >= MIN_WINDOW_S):
        raise ValueError(
            f"the window must be a finite number of seconds of at least "
            f"{MIN_WINDOW_S}, got {window_s!r}"
        )
    problems: list[str] = []
    harness: dict | None = None
    harness_info: dict | None = None
    harness_problem: str | None = None
    root_copy_path: Path | None = None
    expected_run_id: str | None = None
    seal: dict[str, Any] = {
        "applicable": False,
        "reason": "a bare simulator directory carries no seal of its own; "
        "none is verified",
    }
    if run_dir is not None:
        run_dir = Path(run_dir)
        seal, seal_problems = _seal_state(run_dir)
        problems.extend(seal_problems)
        harness_path = run_dir / MANIFEST_FILENAME
        harness, harness_sha, harness_problem = _read_json_object(harness_path)
        harness_present = harness_path.exists()
        if harness_problem is not None and harness_present:
            # Present but unreadable, not strict JSON or not an object: the
            # run directory is not what a harness run must be. A MISSING
            # harness manifest only empties the elapsed section (and a sealed
            # run that lost it fails its seal above).
            problems.append(f"harness manifest: {harness_problem}")
        harness_info = {
            "path": str(harness_path),
            "present": harness_present,
            "sha256": harness_sha,
            "problem": harness_problem,
        }
        run_id = harness.get("run_id") if harness else None
        if not isinstance(run_id, str) or not run_id:
            run_id = run_dir.name
        if warmup:
            expected_run_id = f"{run_id}{WARMUP_SUFFIX}"
            sim_dir = simulator_run_dir(run_dir / WARMUP_LOGS, expected_run_id)
        else:
            expected_run_id = run_id
            sim_dir = simulator_run_dir(run_dir / SIMULATOR_LOGS, run_id)
            root_copy_path = run_dir / SENT_EVENTS_FILENAME
    sim_dir = Path(sim_dir)

    manifest_path = sim_dir / MANIFEST_FILENAME
    sim_manifest, manifest_sha, manifest_problem = _read_json_object(manifest_path)
    if manifest_problem:
        problems.append(manifest_problem)
    manifest = sim_manifest or {}
    if (
        sim_manifest is not None
        and expected_run_id is not None
        and manifest.get("run_id") != expected_run_id
    ):
        problems.append(
            f"simulator manifest run_id {_brief(manifest.get('run_id'))} is not the "
            f"harness run's ({expected_run_id!r})"
        )
    if harness is not None and "execution_mode" in harness:
        execution_mode, mode_source = harness["execution_mode"], "harness manifest"
    elif harness is not None:
        execution_mode = None
        mode_source = "not recorded: the harness manifest predates the field"
    elif harness_info is not None and harness_info["present"]:
        execution_mode = None
        mode_source = f"harness manifest not usable: {harness_problem}"
    else:
        execution_mode, mode_source = None, "no harness manifest"
    rates = manifest.get("rates_hz")
    rates = rates if isinstance(rates, dict) else {}
    run_section = {
        "run_id": manifest.get("run_id"),
        "scenario": manifest.get("scenario"),
        "seed": manifest.get("seed"),
        "aggregate_rate_hz": rates.get("aggregate"),
        "per_device_rates_hz": rates.get("per_device"),
        "duration_s": manifest.get("duration_s"),
        "completed": manifest.get("completed"),
        "warmup": warmup,
        "label": "warm-up: never stands for the measured run" if warmup else "measured run",
        "execution_mode": execution_mode,
        "execution_mode_source": mode_source,
    }

    schedule = None
    if sim_manifest is not None:
        schedule, schedule_problems = reconstruct_schedule(sim_manifest)
        problems.extend(f"simulator manifest: {problem}" for problem in schedule_problems)

    sent_path = sim_dir / SENT_EVENTS_FILENAME
    sent: SentRead | None = None
    sent_info: dict[str, Any] = {"path": str(sent_path), "sha256": None, "lines": None,
                                 "records": None, "problem_lines": None}
    try:
        sent = read_sent_events(sent_path)
    except CheckInputError as exc:
        problems.append(str(exc))
    else:
        problems.extend(sent.problems)
        sent_info.update(sha256=sent.sha256, lines=sent.lines, records=len(sent.records),
                         problem_lines=len(sent.problems))

    if root_copy_path is not None:
        root_copy: dict[str, Any] = {
            "applicable": True, "reason": None, "path": str(root_copy_path),
            "present": root_copy_path.is_file(), "sha256": None, "identical": None,
        }
        try:
            root_sha = _sha256(_read_bytes(root_copy_path))
        except CheckInputError as exc:
            problems.append(
                f"root copy: {exc} (the harness copies the simulator's "
                "sent_events.jsonl to the run root)"
            )
        else:
            root_copy["sha256"] = root_sha
            if sent is not None:
                root_copy["identical"] = root_sha == sent.sha256
                if not root_copy["identical"]:
                    problems.append(
                        f"root copy {root_copy_path} is not byte for byte the "
                        f"simulator's {sent_path}"
                    )
    else:
        root_copy = {
            "applicable": False,
            "reason": "the warm-up has no root copy" if warmup
            else "a bare simulator directory has no root copy",
        }

    identity = None
    usable: list[tuple[dict, ScheduledEvent]] = []
    if schedule is not None and sent is not None:
        identity, identity_problems, usable = check_identity(schedule, sent, manifest)
        problems.extend(identity_problems)

    timing = puback = None
    if schedule is not None and sent is not None:
        partial = bool(problems) or manifest.get("completed") is not True
        timing, overran = generator_timing(
            schedule, usable, window_s=window_s, partial=partial
        )
        puback = puback_observations(schedule, usable, overran)

    elapsed = None
    if harness is not None and not warmup and schedule is not None:
        elapsed = harness_elapsed(harness, usable, schedule.duration_s)
        started = elapsed["measured_started_ns"] if elapsed else None
        if started is not None and timing and timing.get("computed"):
            # The anchor cannot precede the harness's start stamp, so the
            # unknown constant c is at most their difference.
            timing["anchor"]["c_upper_bound_s"] = (
                timing["anchor"]["anchor_ns"] - started
            ) / NS

    acceptance = None
    if events_path is not None:
        acceptance = controller_acceptance(
            events_path, schedule.run_id if schedule else manifest.get("run_id"),
            window_s=window_s,
        )

    report: dict[str, Any] = {
        "check": CHECK_NAME,
        "check_version": CHECK_VERSION,
        "generated_utc": utc_now_iso(),
        "inputs": {
            "layout": "harness run directory" if run_dir is not None else "simulator directory",
            "run_dir": str(run_dir) if run_dir is not None else None,
            "simulator_dir": str(sim_dir),
            "seal": seal,
            "simulator_manifest": {"path": str(manifest_path), "sha256": manifest_sha},
            "sent_events": sent_info,
            "root_copy": root_copy,
            "harness_manifest": harness_info,
            "events": str(events_path) if events_path is not None else None,
            "tolerances": {
                "path": profile.path,
                "sha256": profile.sha256,
                "profile_id": profile.profile_id,
                "status": profile.status,
            } if profile is not None else None,
            "problem_count": len(problems),
            "problems": problems[:PROBLEM_LIMIT],
        },
        "run": run_section,
        "schedule": {
            "events_expected": len(schedule.events),
            "per_device_expected": {
                schedule.device_types[uuid]: n for uuid, n in schedule.per_device.items()
            },
            "distinct_instants": len(schedule.instants),
            "smallest_gap_ms": schedule.smallest_gap_s * 1000
            if schedule.smallest_gap_s is not None
            else None,
            "scheduled_span_s": schedule.scheduled_span_s,
            "structural_zero_budget": schedule.structural_zero_budget,
            "intended_invalid_expected": schedule.invalid_expected,
            "dropout": schedule.dropout,
        } if schedule is not None else None,
        "identity": identity,
        "generator_timing": timing,
        "puback_observations": puback,
        "controller_acceptance": acceptance,
        "elapsed": elapsed,
        "evaluation": None,
    }
    report["evaluation"] = evaluate(report, profile)
    return report


# ---------------------------------------------------------------------------
# Console summary, output and the subcommand
# ---------------------------------------------------------------------------


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def console_lines(report: dict) -> list[str]:
    """One summary line per section, each naming its clock."""
    run = report["run"]
    evaluation = report["evaluation"]
    label = "WARM-UP: never stands for the measured run" if run["warmup"] else "measured run"
    lines = [
        f"generator-check {run['run_id']}: {run['scenario']} @ "
        f"{run['aggregate_rate_hz']} msg/s for {run['duration_s']} s [{label}]",
        f"verdict: {evaluation['verdict']} (exit {VERDICT_EXIT[evaluation['verdict']]}); "
        f"certifying: {'yes' if evaluation['certifying'] else 'no'}; profile: "
        + (
            f"{evaluation['profile_id']} ({evaluation['profile_status']})"
            if evaluation["profile_id"]
            else "none"
        ),
    ]
    lines.extend(f"  - {reason}" for reason in evaluation["reasons"])
    for row in evaluation["per_tolerance"]:
        lines.append(
            f"  {row['name']}: {_fmt(row['value'])} against {_fmt(row['limit'])}: "
            f"{'within' if row['within'] else 'OUTSIDE'}"
            + ("" if evaluation["certifying"] else " (non-certifying)")
        )
    seal = report["inputs"]["seal"]
    if not seal["applicable"]:
        lines.append(f"seal [{SUMS_FILENAME}]: not applicable: {seal['reason']}")
    elif seal["state"] == "verified":
        lines.append(f"seal [{SUMS_FILENAME}]: verified")
    elif seal["state"] == "failed":
        lines.append(
            f"seal [{SUMS_FILENAME}]: FAILED, {seal['problem_count']} problem(s): the "
            "files are not shown to be the run's record"
        )
    else:
        lines.append(
            f"seal [{SUMS_FILENAME}]: {seal['state'].upper()}: the files are not "
            "shown to be the run's record"
        )
    identity = report["identity"]
    if identity is not None:
        root = report["inputs"]["root_copy"]
        lines.append(
            f"identity: {'exact' if identity['exact'] else 'NOT exact'}; "
            f"{identity['records']} record(s) of {identity['events_expected']} scheduled; "
            f"totals.sent {identity['totals_sent']}; missing {identity['missing']['count']}; "
            "root copy "
            + (
                ("identical" if root["identical"] else "NOT identical")
                if root.get("applicable")
                else "not applicable"
            )
        )
    timing = report["generator_timing"]
    if timing is not None and not timing.get("computed"):
        state = "not computed" if timing.get("applicable") else "not applicable"
        lines.append(f"generator timing [host monotonic clock]: {state}: {timing['reason']}")
    elif timing is not None:
        lateness = timing["relative_lateness_ms"]
        lines.append(
            "generator timing [host monotonic clock; client publish-call "
            "instants, not broker ingress"
            + ("; PARTIAL" if timing["partial"] else "")
            + f"]: relative lateness p50 {_fmt(lateness['p50'])} / p99 "
            f"{_fmt(lateness['p99'])} / max {_fmt(lateness['max'])} ms; overruns "
            f"{timing['overruns']['events']} in {timing['overruns']['bursts']} burst(s); "
            f"longest publish gap {_fmt(timing['publish_gaps_ms']['max'])} ms; span "
            f"deviation {_fmt(timing['span']['deviation_ms'])} ms; "
            f"{_fmt(timing['windows']['window_s'])} s windows not equal to the "
            f"schedule {timing['windows']['nonzero']}"
        )
        rates = timing["summary_rates"]
        lines.append(
            f"summary rates (cannot detect a mid-run stall): requested "
            f"{_fmt(rates['requested_hz'], 4)}, N/duration "
            f"{_fmt(rates['schedule_n_over_duration_hz'], 4)}, (N-1)/span "
            f"{_fmt(rates['first_to_last_hz'], 4)} msg/s"
        )
    puback = report["puback_observations"]
    if puback is not None:
        lines.append(
            f"puback [host monotonic clock; never in the verdict]: observed "
            f"{puback['observed']}, null {puback['null']} (structural "
            f"{puback['null_structural']}, overrun {_fmt(puback['null_overrun'])}, other "
            f"{puback['null_other']}); {PUBACK_STATEMENT}"
        )
    acceptance = report["controller_acceptance"]
    if acceptance is None:
        lines.append(
            "acceptance [guest monotonic clock; never in the verdict]: not requested (--events)"
        )
    elif acceptance.get("error"):
        lines.append(
            "acceptance [guest monotonic clock; never in the verdict]: "
            f"{acceptance['error']}"
        )
    else:
        accepted = acceptance["accepted_ack"]
        lines.append(
            "acceptance [guest monotonic clock; never in the verdict, never "
            f"subtracted from host stamps]: {accepted['n']} accepted, served "
            f"{_fmt(accepted['served_rate_hz'], 4)} msg/s over {_fmt(accepted['span_s'])} s; "
            f"lines {acceptance['lines']}, unreadable {acceptance['unreadable']}, other "
            f"run {acceptance['other_run_id']}, clock backwards "
            f"{acceptance['clock_backwards']}; a served rate below the offered rate is a "
            "system observation, not a generator shortfall"
        )
    elapsed = report["elapsed"]
    if elapsed is not None:
        lines.append(
            "elapsed [host monotonic clock, harness stamps; non-certifying]: first publish "
            f"{_fmt(elapsed['first_publish_after_start_s'])} s after the measured start; "
            f"end {_fmt(elapsed['finished_after_last_publish_s'])} s after the last "
            f"publish; process {_fmt(elapsed['process_elapsed_s'])} s (kill bound "
            f"{_fmt(elapsed['kill_bound_s'])} s); simulator_returncode "
            f"{elapsed['simulator_returncode']}"
        )
    else:
        harness = report["inputs"]["harness_manifest"]
        if run["warmup"]:
            why = "the warm-up (the harness stamps bracket the measured run)"
        elif harness is None:
            why = "a bare simulator directory has no harness manifest"
        else:
            why = harness["problem"] or "no usable record"
        lines.append(f"elapsed: not applicable: {why}")
    mode = run["execution_mode"]
    lines.append(
        f"execution mode: {mode if mode is not None else 'none'} ({run['execution_mode_source']})"
    )
    return lines


def write_report(path: Path, report: dict) -> None:
    """Write the report once: an existing file raises ``FileExistsError``;
    any other failure raises ``OSError`` and leaves no partial file behind
    (a partial report would block a write-once retry)."""
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Mode 'x': creation and the write-once refusal are one step.
    fh = open(path, "x", encoding="utf-8", newline="\n")
    try:
        with fh:
            fh.write(text)
    except BaseException:
        with contextlib.suppress(OSError):
            path.unlink()
        raise


def _out_refusal(out: Path, run_dir: Path | None, sim_dir: Path | None) -> str | None:
    """Why ``out`` may not be written, or None.

    Refused: an existing file (write-once); a path inside the run or the
    simulator directory, or inside the harness run directory that holds a
    simulator directory given as logs/<simulator|warmup>/<run_id>/ (the
    collection seals every file there); and a path inside any directory
    holding a SHA256SUMS seal.
    """
    if out.exists():
        return f"refusing to overwrite {out}: the report is write-once"
    protected = [Path(d).resolve() for d in (run_dir, sim_dir) if d is not None]
    if sim_dir is not None and Path(sim_dir).resolve().parent.parent.name == "logs":
        protected.append(Path(sim_dir).resolve().parents[2])
    target = out.resolve()
    sealed = [parent for parent in target.parents if (parent / SUMS_FILENAME).is_file()]
    for base in protected + sealed:
        if target == base or base in target.parents:
            return (
                f"refusing to write {out} inside {base}: a run directory and a "
                f"sealed directory ({SUMS_FILENAME}) are never written to; write "
                "beside raw/, e.g. <base>/checks/generator/<run_id>.json"
            )
    return None


def _usage(message: str) -> int:
    print(f"error: generator-check: {message}", file=sys.stderr)
    return EXIT_USAGE


def run_from_args(args: argparse.Namespace) -> int:
    """The ``generator-check`` subcommand (``egw_experiments.cli``)."""
    window_s = args.window_s
    if not (math.isfinite(window_s) and window_s >= MIN_WINDOW_S):
        return _usage(
            f"--window-s must be a finite number of seconds of at least {MIN_WINDOW_S}, "
            f"got {window_s}"
        )
    if args.warmup and args.run_dir is None:
        return _usage("--warmup reads the warm-up of a harness run: it needs --run-dir")
    profile = None
    if args.tolerances is not None:
        try:
            profile = load_tolerances(args.tolerances)
        except ToleranceError as exc:
            return _usage(f"tolerances: {exc}")
    out: Path | None = args.out
    refusal = _out_refusal(out, args.run_dir, args.sim_dir) if out is not None else None
    if refusal:
        return _usage(refusal)
    report = check_generator(
        sim_dir=args.sim_dir,
        run_dir=args.run_dir,
        events_path=args.events,
        profile=profile,
        window_s=window_s,
        warmup=args.warmup,
    )
    if out is not None:
        # Written before the console summary: a verdict line is printed only
        # when its exit code is the process's, and exit 1 only ever means a
        # NOT_SHOWN evaluation, never a failed write.
        try:
            write_report(out, report)
        except OSError as exc:
            if isinstance(exc, FileExistsError) and out.exists():
                return _usage(f"refusing to overwrite {out}: the report is write-once")
            return _usage(
                f"cannot write {out}: {exc}; no report was written and no verdict "
                "is given"
            )
    for line in console_lines(report):
        print(line)
    if out is not None:
        print(f"wrote {out}")
    return VERDICT_EXIT[report["evaluation"]["verdict"]]
