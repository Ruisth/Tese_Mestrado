"""N1 identities reported as ``n1_applied_unconfirmed`` (decision 2 of
2026-09-30): an explanation beside the delivery accounting, never a count.

The identity in progress at a controller death, or at a connection end after
its ``PATCH``, may have reached the twin without an ``accepted`` line
(CONTRACTS §5, "Redelivery (v1.2)"; ADR 0011, N1); its redelivery is then
classified ``duplicate`` and it stays ``lost`` under section 9. This module
names such an identity only when all three conditions of the adopted rule
hold, and reports every other duplicate-only identity as
``duplicate_only_unexplained`` with the conditions it failed:

1. its only outcome lines (of this run id, in the events copy compared with
   the post-drain ``after`` snapshot) are ``duplicate``, and it is a valid
   published identity of the run (``sent_events.jsonl``, not intended
   invalid);
2. the run records a source for it: the controller death of a restart
   record whose restart executed with exit 0 and whose complete capture
   holds a ``die`` of ``egw-controller-1`` inside the capture window (the
   120 s replayed before RUN_T0 excluded) - at most one death per run from
   this source; or a connection end the controller logged under A3 (ERROR
   "MQTT connection ended by the controller"; an INFO line is a graceful
   stop, not A3) on the identity's own device, whose in-progress delivery's
   ``received_monotonic_ns`` precedes the identity's first ``duplicate``
   line's ``received_monotonic_ns``. Each source explains at most one
   identity;
3. on its device, Δ``accepted_count`` between the ``before`` snapshot and
   the ``after`` snapshot taken after a quiet drain exceeds the device's
   ``accepted`` lines in that events copy by exactly the number of
   identities reported on that device, and the twin's ``last_seq`` is not
   below each reported identity's ``seq``. The absolute ``accepted_count``
   is never used. Per device, all or nothing: if the device has more
   duplicate-only identities than the surplus, or any fails a condition,
   none of them is named (they cannot be told apart).

When attribution is not demonstrated (an unread source, an unreadable stamp,
a death two devices would need, a drain not quiet, snapshots not verified),
the identity is unexplained, never N1. The readings taken here:

- condition 1: the lines are those of the run id the caller names; a
  ``message_id`` published more than once, or a sent record whose
  ``intended_invalid`` is not ``false``, is not shown to be a valid
  identity. An unpublished duplicate-only identity can never be N1, but it
  counts among its device's duplicate-only identities (it may be the one
  the twin applied);
- condition 2, the death: "the capture window" is the coverage record's
  ``[requested_since_guest_epoch, requested_until_guest_epoch + 1)`` over the
  daemon's ``timeNano``, the window rule R7 of events_coverage.py reads, and
  the record must start with ``coverage=complete``; the restart record must
  show ``executed``, ``started_utc``, ``finished_utc``, ``returncode`` 0 and
  no ``error`` (analyze's ``restart_hook_ok``);
- condition 2, the sources: a device is served when a maximum matching of
  its duplicate-only identities to its own A3 ends covers them all, or all
  but one and the one death is left to it. The death is left to a device
  only when no other device has a duplicate-only identity its own ends
  leave uncovered: that identity may have been the death's one delivery
  (not applied), so which device the death explained cannot be told;
- condition 3: the twin snapshots are read as ``itest_reconcile delta``
  reads them (an absent twin's null ``accepted_count`` is 0; every
  ``accepted`` line of the compared log counts, whatever its run id), so
  the device arithmetic is delta's; whether the ``after`` snapshot follows
  a quiet drain, and whether the snapshots are the verified ones, is the
  caller's to establish and to pass as ``twin_evidence_problem``.

Stated limits: the death carries no order check - no condition places the
``die`` before the identity's redelivery, so a death is attributed by count
alone (condition 3's arithmetic and the one-death rule), the literal reading
of the adopted wording. ``after.last_run_id`` is not compared (as in the
finite proof's N1 naming). Which of several possible sources served which
identity is inference: each named identity lists its possible sources, and
none of that decides anything.

What does not change: a named identity stays in ``lost`` and in every
zero-lost criterion, the ``delta`` line of its device stays a mismatch,
it is never counted as accepted, delivered or on time, and no exactly-once
claim is made; no accepted record is fabricated. Exit codes and the analyser
(``egw_experiments.analyze``) are untouched: the report is written beside
them by ``recovery_qualification`` (T6's harness runs) and printed by
``itest_reconcile delta`` only when one of its N1 options is given.

Standard library only, and deliberately independent of the finite proof's
evaluator (which imports ``itest_reconcile`` at its top, so importing it
here would close a cycle through ``delta``): the A3 parser below re-reads
what the proof's A5 parser reads, and a drift test holds the two together.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

NS = 1_000_000_000

#: The controller's container (compose project ``egw``; the default of
#: events_coverage.py and of the T6 capture).
CONTROLLER_CONTAINER = "egw-controller-1"

#: The message of ``MqttBridge.end_connection`` (egw_controller/mqtt.py):
#: at ERROR an A3 connection end, at INFO a graceful stop.
A3_END_MESSAGE = "MQTT connection ended by the controller"

#: The two kinds of source a named identity may list.
SOURCE_A3 = "a3-connection-end"
SOURCE_DEATH = "controller-death"

#: Written into every report: what the report does not change.
NOTE = (
    "explanation only: a named identity stays in lost and in every zero-lost "
    "criterion, the delta line of its device stays a mismatch, and it is "
    "never counted as accepted, delivered or on time; no exactly-once claim"
)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# tolerant readers: a file that cannot be read is "not read", never an error
# ---------------------------------------------------------------------------


def read_text_lines(path: str | Path) -> tuple[list[str] | None, str | None]:
    """The lines of a log file, read as the finite proof reads the
    controller log (UTF-8, undecodable bytes replaced), or (None, why)."""
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines(), None
    except FileNotFoundError:
        return None, f"{path.name} missing"
    except OSError as exc:
        return None, f"{path.name} unreadable ({type(exc).__name__})"


def read_jsonl(path: str | Path) -> tuple[list[dict[str, Any]] | None, str | None]:
    """The JSON objects of a JSON-lines file (a line that is not one is
    skipped, as the analysis reader does: CONTRACTS v1.2 allows a torn last
    line), or (None, why)."""
    lines, why = read_text_lines(path)
    if lines is None:
        return None, why
    records = []
    for text in lines:
        if not text.strip():
            continue
        try:
            obj = json.loads(text)
        except ValueError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records, None


def read_json_object(path: str | Path) -> tuple[dict[str, Any] | None, str | None]:
    """A JSON object file, or (None, why)."""
    path = Path(path)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{path.name} missing"
    except (OSError, ValueError) as exc:
        return None, f"{path.name} unreadable ({type(exc).__name__})"
    if not isinstance(obj, dict):
        return None, f"{path.name} is not a JSON object"
    return obj, None


def twin_devices(snapshot: Any) -> dict[str, Any] | None:
    """The ``devices`` mapping of a twin snapshot as ``snap`` writes it, or
    None when there is none."""
    devices = snapshot.get("devices") if isinstance(snapshot, dict) else None
    return devices if isinstance(devices, dict) and devices else None


# ---------------------------------------------------------------------------
# the A3 source: the controller log
# ---------------------------------------------------------------------------


def _json_after_prefix(line: str) -> dict[str, Any] | None:
    """The JSON object of a log line, after any compose (``name | ``) or
    docker (``--timestamps``) prefix."""
    start = line.find("{")
    if start < 0:
        return None
    try:
        obj = json.loads(line[start:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _device_of_topic(topic: Any) -> str | None:
    parts = topic.split("/") if isinstance(topic, str) else []
    return parts[2] if len(parts) == 4 and parts[0] == "c2dt" and parts[3] == "telemetry" else None


def a3_connection_ends(log_lines: list[str]) -> list[dict[str, Any]]:
    """The A3 connection ends of a controller log, in file order: the lines
    at ERROR whose message is :data:`A3_END_MESSAGE` (the INFO line of a
    graceful stop is not one), each with its line number (1-based, blank
    lines counted), the controller's ``ts``, the cause and connection, the
    device of the delivery in progress (the topic's third segment) and that
    delivery's ``received_monotonic_ns`` as logged (the controller clock)."""
    ends: list[dict[str, Any]] = []
    for number, text in enumerate(log_lines, 1):
        if not text.strip():
            continue
        obj = _json_after_prefix(text)
        if obj is None or obj.get("message") != A3_END_MESSAGE or obj.get("level") != "ERROR":
            continue
        context = obj.get("context") if isinstance(obj.get("context"), dict) else {}
        identity = context.get("identity") if isinstance(context.get("identity"), dict) else {}
        ends.append(
            {
                "line": number,
                "ts": obj.get("ts"),
                "cause": context.get("cause"),
                "connection": context.get("connection"),
                "device_uuid": _device_of_topic(identity.get("topic")),
                "received_monotonic_ns": identity.get("received_monotonic_ns"),
            }
        )
    return ends


# ---------------------------------------------------------------------------
# the death source: the restart record and the captured die
# ---------------------------------------------------------------------------


def _restart_problem(record: Any) -> str | None:
    """Why the restart record does not show the restart executed with exit
    0, or None when it does (analyze's ``restart_hook_ok``)."""
    if not isinstance(record, dict):
        return "no restart record"
    if record.get("executed") is not True:
        return "the restart record does not show the restart executed"
    if not (record.get("started_utc") and record.get("finished_utc")):
        return "the restart record has no started_utc/finished_utc"
    if not (_is_int(record.get("returncode")) and record["returncode"] == 0):
        return f"the restart command exited {record.get('returncode')!r}"
    if record.get("error"):
        return "the restart record carries an error"
    return None


def capture_window(coverage_text: str | None) -> tuple[tuple[int, int] | None, str | None]:
    """The capture window [since, until] (guest epochs) of a coverage record
    that starts with ``coverage=complete``, or (None, why)."""
    if coverage_text is None:
        return None, "the capture's coverage record was not read"
    lines = coverage_text.splitlines()
    if not lines or lines[0].strip() != "coverage=complete":
        return None, "the capture is not shown complete (its coverage record does not start with coverage=complete)"
    values: dict[str, str] = {}
    for text in lines:
        key, sep, value = text.strip().partition("=")
        if sep and key and key not in values:
            values[key] = value
    since, until = values.get("requested_since_guest_epoch", ""), values.get("requested_until_guest_epoch", "")
    if not (since.isdigit() and until.isdigit()) or int(until) < int(since):
        return None, "the coverage record gives no whole-number capture window"
    return (int(since), int(until)), None


def controller_deaths(
    restart_record: Any,
    docker_event_lines: list[str] | None,
    coverage_text: str | None,
    container: str = CONTROLLER_CONTAINER,
) -> tuple[list[dict[str, Any]], str | None]:
    """The death source of a run: ``([death], None)`` when the restart record
    shows the restart executed with exit 0 and the complete capture holds a
    ``die`` of ``container`` inside its window; ``([], why)`` otherwise. One
    death at most, however many ``die`` events the window holds."""
    why = _restart_problem(restart_record)
    if why is not None:
        return [], why
    if docker_event_lines is None:
        return [], "the run's Docker events capture was not read"
    window, why = capture_window(coverage_text)
    if window is None:
        return [], why
    since, until = window
    dies: list[tuple[int, int]] = []
    for number, text in enumerate(docker_event_lines, 1):
        if not text.strip():
            continue
        try:
            event = json.loads(text)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        stamp = event.get("timeNano")
        if not _is_int(stamp) or not since * NS <= stamp < (until + 1) * NS:
            continue
        actor = event.get("Actor") if isinstance(event.get("Actor"), dict) else {}
        attributes = actor.get("Attributes") if isinstance(actor.get("Attributes"), dict) else {}
        if event.get("Type", "container") == "container" and event.get("Action") == "die" \
                and attributes.get("name") == container:
            dies.append((number, stamp))
    if not dies:
        return [], (
            f"no 'die' of {container} is captured inside the capture window [{since}, {until}] "
            "(guest epochs; the replay before it excluded)"
        )
    line, stamp = dies[0]
    return [
        {
            "source": SOURCE_DEATH,
            "container": container,
            "die_line": line,
            "die_time_nano": stamp,
            "dies_in_window": len(dies),
            "restart_started_utc": restart_record.get("started_utc"),
        }
    ], None


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------


def _matching_size(order: list[str], options: dict[str, list[Any]]) -> int:
    """The size of a maximum matching of identities to sources, each source
    serving one identity (augmenting paths; the size does not depend on the
    order)."""
    held: dict[Any, str] = {}

    def augment(identity: str, seen: set[Any]) -> bool:
        for source in options.get(identity, []):
            if source in seen:
                continue
            seen.add(source)
            if source not in held or augment(held[source], seen):
                held[source] = identity
                return True
        return False

    return sum(1 for identity in order if augment(identity, set()))


def _count(entry: Any) -> tuple[bool, int | None]:
    """(readable, accepted_count) of a snapshot entry: readable when the
    entry has an ``ingestion`` object whose ``accepted_count`` is an integer
    or null."""
    ingestion = entry.get("ingestion") if isinstance(entry, dict) else None
    if not isinstance(ingestion, dict):
        return False, None
    value = ingestion.get("accepted_count")
    return (value is None or _is_int(value)), (value if _is_int(value) else None)


def n1_applied_unconfirmed(
    *,
    run_id: str | None,
    sent_records: list[dict[str, Any]] | None,
    events: list[dict[str, Any]],
    twins_before: dict[str, Any] | None,
    twins_after: dict[str, Any] | None,
    twin_evidence_problem: str | None = None,
    deaths: list[dict[str, Any]] | None = None,
    deaths_note: str | None = None,
    a3_ends: list[dict[str, Any]] | None = None,
    a3_note: str | None = None,
) -> dict[str, Any]:
    """The report of one run (see the module docstring for the rule).

    ``events`` is the events copy compared with the twins (every line
    counts in a device's accepted lines, as ``delta`` counts them; only the
    lines of ``run_id`` are read for identities). ``twins_before`` and
    ``twins_after`` are the snapshots' ``devices`` mappings. ``None`` means
    not read: ``sent_records`` (condition 1), the snapshots (condition 3),
    ``deaths`` and ``a3_ends`` (condition 2, with ``deaths_note`` and
    ``a3_note`` saying why). ``twin_evidence_problem`` names what leaves
    condition 3 unshown (a drain not quiet, snapshots not verified). Never
    raises on data."""
    notes: list[str] = []
    lines_by_id: dict[str, list[dict[str, Any]]] = {}
    if isinstance(run_id, str) and run_id:
        for record in events:
            if not isinstance(record, dict) or record.get("run_id") != run_id:
                continue
            message_id = record.get("message_id")
            if isinstance(message_id, str) and message_id:
                lines_by_id.setdefault(message_id, []).append(record)
    else:
        notes.append("the events copy names no run id: no identity was read")
    candidates = [
        mid for mid, lines in lines_by_id.items()
        if all(line.get("outcome") == "duplicate" for line in lines)
    ]

    valid: dict[str, dict[str, Any]] | None = None
    if sent_records is not None:
        published: dict[str, int] = {}
        for record in sent_records:
            if isinstance(record, dict) and record.get("run_id") == run_id and isinstance(record.get("message_id"), str):
                published[record["message_id"]] = published.get(record["message_id"], 0) + 1
        valid = {
            record["message_id"]: record
            for record in sent_records
            if isinstance(record, dict) and record.get("run_id") == run_id
            and isinstance(record.get("message_id"), str) and record["message_id"]
            and published[record["message_id"]] == 1 and record.get("intended_invalid") is False
        }

    # Each candidate's facts and the reasons of the conditions it fails.
    reasons: dict[str, dict[str, list[str]]] = {mid: {} for mid in candidates}

    def fail(mid: str, condition: str, why: str) -> None:
        found = reasons[mid].setdefault(condition, [])
        if why not in found:
            found.append(why)

    facts: dict[str, dict[str, Any]] = {}
    by_device: dict[str, list[str]] = {}
    for mid in candidates:
        lines = lines_by_id[mid]
        device = next((line["device_uuid"] for line in lines
                       if isinstance(line.get("device_uuid"), str) and line["device_uuid"]), None)
        record = valid.get(mid) if valid is not None else None
        seq = (record or lines[0]).get("seq")
        stamp = lines[0].get("received_monotonic_ns")
        facts[mid] = {
            "message_id": mid,
            "device_uuid": device,
            "seq": seq if _is_int(seq) else None,
            "first_duplicate_received_monotonic_ns": stamp if _is_int(stamp) else None,
        }
        if valid is None:
            fail(mid, "1", "sent_events.jsonl was not read, so it is not shown to be a valid published identity "
                           "of this run")
        elif record is None:
            fail(mid, "1", "not a valid published identity of this run (absent from sent_events.jsonl under this "
                           "run id, intended invalid, or published more than once): it can never be N1")
        elif record.get("device_uuid") != device:
            fail(mid, "1", "its published record names another device than its outcome lines")
        if device is None:
            fail(mid, "3", "its outcome lines name no device")
        else:
            by_device.setdefault(device, []).append(mid)

    # Condition 3: the device arithmetic, exactly delta's.
    before, after = twins_before or {}, twins_after or {}
    devices_out: dict[str, dict[str, Any]] = {}
    for device in sorted(set(before) | set(after) | set(by_device)):
        readable_b, count_b = _count(before.get(device))
        readable_a, count_a = _count(after.get(device))
        delta = (count_a or 0) - (count_b or 0) if readable_b and readable_a else None
        accepted = sum(1 for record in events if isinstance(record, dict)
                       and record.get("device_uuid") == device and record.get("outcome") == "accepted")
        excess = delta - accepted if delta is not None else None
        devices_out[device] = {"delta": delta, "accepted_lines": accepted, "excess": excess,
                               "duplicate_only": len(by_device.get(device, [])), "reported": 0}
        if excess is not None and excess > 0 and not by_device.get(device):
            notes.append(f"device {device}: excess {excess} with no duplicate-only identity of this run: "
                         "nothing is named")
    for device, mids in by_device.items():
        figures = devices_out[device]
        why = None
        if twin_evidence_problem:
            why = f"not evaluable: {twin_evidence_problem}"
        elif twins_before is None or twins_after is None:
            why = "the twin snapshots were not read"
        elif figures["delta"] is None:
            why = "the device is not in both snapshots with a readable accepted_count"
        elif figures["excess"] <= 0:
            why = (f"the twin shows no surplus on the device (delta {figures['delta']} against "
                   f"{figures['accepted_lines']} accepted line(s): excess {figures['excess']}), so no identity "
                   "is shown applied")
        elif len(mids) > figures["excess"]:
            why = (f"{len(mids)} duplicate-only identities on the device against an excess of {figures['excess']}: "
                   "they cannot be told apart, so none is named")
        elif len(mids) < figures["excess"]:
            why = (f"an excess of {figures['excess']} beyond the device's {len(mids)} duplicate-only "
                   "identit" + ("y" if len(mids) == 1 else "ies") + ": the count is not exact, so none is named")
        if why is not None:
            for mid in mids:
                fail(mid, "3", why)
            continue
        ingestion = after[device].get("ingestion") or {}
        last_seq = ingestion.get("last_seq")
        for mid in mids:
            seq = facts[mid]["seq"]
            if not _is_int(last_seq) or seq is None or last_seq < seq:
                fail(mid, "3", f"the after snapshot's last_seq {last_seq!r} is below the identity's seq {seq!r} "
                               "(or one of them cannot be read): the twin is not shown to have advanced to it")

    # Condition 2: the sources, each explaining one identity at most.
    ends = [end for end in (a3_ends or []) if isinstance(end, dict)]
    death = deaths[0] if deaths else None
    options: dict[str, list[Any]] = {}
    for mid in candidates:
        stamp = facts[mid]["first_duplicate_received_monotonic_ns"]
        options[mid] = [
            end.get("line") for end in ends
            if end.get("device_uuid") == facts[mid]["device_uuid"] and facts[mid]["device_uuid"] is not None
            and _is_int(end.get("received_monotonic_ns")) and stamp is not None
            and end["received_monotonic_ns"] < stamp
        ]
    uncovered = {device: len(mids) - _matching_size(mids, options) for device, mids in by_device.items()}
    wanting = sorted(device for device, short in uncovered.items() if short > 0)
    if a3_ends is None:
        a3_text = f"controller log not read ({a3_note or 'not given'})"
    else:
        a3_text = f"{len(ends)} A3 connection end(s) read from the controller log"
    if deaths is None:
        death_text = f"controller death source not read ({deaths_note or 'not given'})"
    elif death is None:
        death_text = f"no controller death source ({deaths_note or 'none recorded'})"
    else:
        death_text = "one controller death"
    for device, mids in by_device.items():
        short = uncovered[device]
        if short == 0:
            continue
        own = len({line for mid in mids for line in options[mid]})
        if death is None:
            why = (f"no source may precede {'it' if len(mids) == 1 else 'them all'}: its device's A3 connection ends "
                   f"that precede the redelivery ({own}) serve {len(mids) - short} of its {len(mids)} "
                   f"duplicate-only identit{'y' if len(mids) == 1 else 'ies'}; {a3_text}; {death_text}")
        elif short > 1:
            why = (f"{short} of the device's duplicate-only identities have no own A3 connection end left, and the "
                   f"one controller death explains one at most ({a3_text})")
        elif len(wanting) > 1:
            why = (f"the one controller death would be needed by duplicate-only identities on {len(wanting)} "
                   f"devices ({', '.join(wanting)}): which one it explained cannot be told")
        else:
            continue
        for mid in mids:
            fail(mid, "2", why)

    # All or nothing per device: one member that fails a condition leaves
    # the others unnamed (the twin cannot tell which one it applied).
    named: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    for device, mids in by_device.items():
        failing = [mid for mid in mids if reasons[mid]]
        if failing:
            for mid in mids:
                if not reasons[mid]:
                    fail(mid, "3", "all or nothing on the device: " + ", ".join(
                        f"{other} fails condition(s) {', '.join(sorted(reasons[other]))}" for other in failing
                    ) + ", so the twin cannot tell which identity it applied")
            continue
        death_possible = death is not None and wanting in ([], [device])
        for mid in mids:
            sources = [
                {"source": SOURCE_A3, "controller_log_line": end.get("line"),
                 "received_monotonic_ns": end.get("received_monotonic_ns")}
                for end in ends if end.get("line") in options[mid]
            ]
            if death_possible:
                sources.append({key: death[key] for key in ("source", "die_time_nano") if key in death})
            named.append({**facts[mid], "possible_sources": sources})
        devices_out[device]["reported"] = len(mids)
    for mid in candidates:
        if reasons[mid]:
            unexplained.append({
                **facts[mid],
                "failed": sorted(reasons[mid]),
                "reason": "; ".join(
                    f"condition {condition}: " + "; ".join(reasons[mid][condition])
                    for condition in sorted(reasons[mid])
                ),
            })
    return {
        "run_id": run_id,
        "n1_applied_unconfirmed": named,
        "duplicate_only_unexplained": unexplained,
        "devices": devices_out,
        "sources": {
            "controller_log_read": a3_ends is not None,
            "controller_log_note": a3_note,
            "a3_ends": len(ends),
            "deaths_read": deaths is not None,
            "deaths_note": deaths_note,
            "deaths": list(deaths or []),
        },
        "twin_evidence_problem": twin_evidence_problem,
        "notes": notes,
        "note": NOTE,
    }
