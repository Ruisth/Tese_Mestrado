"""Operator helper for the ad-hoc itest-* runs of qemu_integrated_gateway.md.

``python -m egw_experiments.itest_reconcile {mark,wait,check,snap,delta,same,acceptance,replay-check}``

Runs on the HOST, in the venv where the repository is installed
(pip install -e .../src). It implements NO protocol rule of its own:

- the end-of-run marker is read with egw_experiments.run.poll_controller_marker
  (GET /metrics monotonic_ns, the controller's clock);
- the deadline is marker + egw_experiments.protocol.CONFIRMATION_WINDOW_S,
  the same arithmetic as run.py, written into a harness-shaped manifest. The
  window is always the imported constant: a marker file whose deadline is not
  exactly marker + CONFIRMATION_WINDOW_S is refused, never used;
- delivered / lost / late / duplicate accounting is done by
  egw_experiments.analyze.compute_run_metrics, unchanged;
- ``acceptance`` and ``replay-check`` apply items of the Expected lists of
  the runbook's tests 3 and 4 as the decisions of 2026-09-30 word them, per
  identity and on raw lines; they apply no deadline and change no figure of
  that accounting.

Every file it writes is a SIBLING of the simulator run directory
(<prefix>.marker.json, <prefix>.twins.<label>.json, ...); the simulator's
write-once run directory itself is never modified by this module. Nothing is
read from the network at import time; only ``mark``, ``wait`` (controller
GET /metrics) and ``snap`` (Ditto GET thing) open a connection.

``delta`` can add the N1 report of decision 2 of 2026-09-30
(egw_experiments.n1_report), opt-in: ``--n1-report`` prints it,
``--controller-log FILE`` gives it the A3 source (the controller log of the
run) and ``--restart-evidence RUN_DIR`` the death source (a harness run
directory: its ``restart`` record and its Docker events capture, the death
placed by its ``controller_metrics.csv``, without which it serves no
identity) together
with the evidence that the 'after' snapshot follows a quiet drain (its
recovery qualification, its verified snapshots and post-drain copy, which
must be the ones compared); either source option implies ``--n1-report``.
Without ``--restart-evidence`` that evidence is the 'to' /metrics reading,
quiet as CONTRACTS 5 defines one reading (queue_depth, in_progress and
unacked 0, mqtt_subscribed true and the accounting identity holding; a
field that is absent is never read as zero or false): one reading, not the
quiet window of ``drained``, which the runbook's ``finish`` observes before
it takes the 'after' pair and which delta cannot re-check. Without either,
condition 3 is not shown. The report is an
explanation, never a status: under a device line that stays ``MISMATCH`` it
names the ``n1_applied_unconfirmed`` identities of that device, and after
the last line it prints the counts, the sources and every
``duplicate_only_unexplained`` identity with its failed conditions; no line
it adds holds the upper-case status words (it names the options' labels and
files by their role, never by the names given), a named source that cannot
be read, or holds a malformed record, is reported as not read (never exit
1), a report that cannot be made at all is one line saying so, and no exit
code changes.
Without the options the output is byte for byte what it was.

Exit codes (the runbook's shell helpers test them):

- 0  the step was carried out. For ``check`` this is NOT a verdict: it exits 0
     also when ``lost > 0`` or with ``warnings`` in the row (it reports, the
     operator judges the printed row; a WARNING line on stderr says so). For
     ``delta``: every line that was compared closed. A controller restart
     between the two /metrics snapshots (planned in the fault tests) is
     printed and leaves the status to the twins; a missing /metrics snapshot
     is printed as not compared. ``delta`` compares the twins with the run
     directory's ``events.jsonl`` unless ``--events <file>`` names another
     copy of the log (the runbook's test 6 names the post-drain copy,
     ``events.post-drain.jsonl``: messages completed during the drain are in
     the after twin but not in the timed copy, which keeps its deadline
     accounting untouched); ``--also`` adds the log of another run id (the
     warm-up), never a second copy of the same records. For ``acceptance``
     (test 3, decision of 2026-09-30): every valid message of the run's
     ``sent_events.jsonl`` has an ``accepted`` line of that run in the copy
     of the events ``--events`` names (the copy fetched after the run's final
     drain); no timestamp is read, so a late acceptance counts. For
     ``replay-check`` (test 4, decision of 2026-09-30): the two /metrics
     readings are of one process and every per-identity condition, the
     reconnection budget, /metrics accepted unchanged and an empty queue in
     the 'to' reading held. Neither writes anything.
- 1  the step was NOT carried out: marker unavailable, a write-once file
     already exists, an input file is missing or malformed, the controller
     clock went backwards, ``wait`` gave up, Ditto unreachable. For
     ``acceptance`` and ``replay-check`` also: a published record without a
     usable message_id, a message_id twice, records of more than one run id,
     a sent_events.jsonl whose record count is not the totals.sent of the
     simulator manifest beside it, no message to judge, a /metrics field
     absent or not of its type (never read as zero), a pre-replay copy that
     is not a prefix of the log, a line of the log that carries another run
     id, and (one process) a line beyond the pre-replay copy that was
     received at or before the 'from' reading, or a 'from' reading without
     an integer monotonic_ns.
- 2  command-line usage error (argparse).
- 3  ``check`` only: the row was computed and saved, but the deadline is not
     on the controller marker (no marker file), so it is NOT a protocol check.
- 4  ``delta``: a per-device or /metrics MISMATCH, accepted records of a device
     that the 'from' snapshot does not hold, or a non-empty queue in the 'to'
     snapshot; ``same``: the two snapshots are DIFFERENT; ``acceptance``: a
     valid message never accepted in the copy; ``replay-check``: readings of
     two processes, a replayed identity without a duplicate line from the
     replay, with an accepted line from it or with more than one accepted
     line, more further duplicates than reconnections, /metrics accepted
     moved or a non-empty queue.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from egw_experiments import n1_report
from egw_experiments import recovery_qualification as rq
from egw_experiments.analyze import compute_run_metrics
from egw_experiments.environment import utc_now_iso
from egw_experiments.protocol import CONFIRMATION_WINDOW_S
from egw_experiments.run import (
    CONTROLLER_MARKER_LAG_TOLERANCE_S,
    MANIFEST_FILENAME,
    POST_DRAIN_EVENTS_FILENAME,
    TWIN_SNAPSHOT_FILES,
    poll_controller_marker,
)
from egw_simulator.devices import DEVICE_TYPES, make_devices

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NOT_PROTOCOL = 3
EXIT_MISMATCH = 4

NS = 1_000_000_000
PREAUTH = {"x-ditto-pre-authenticated": "pre:egw-controller"}
INGESTION_KEYS = (
    "last_run_id", "last_seq", "last_message_id", "last_ts", "accepted_count"
)
COUNTERS = ("accepted", "rejected", "duplicate", "failed", "dropped")
STAMPS = ("received_monotonic_ns", "ditto_ack_monotonic_ns")
WAIT_POLL_INTERVAL_S = 2.0


class HelperError(Exception):
    """The step cannot be carried out; ``main`` reports it and exits 1."""


def sib(prefix: str, suffix: str) -> Path:
    return Path(str(prefix).rstrip("/") + suffix)


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load(path: Path) -> dict:
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HelperError(f"{path} missing") from None
    except (OSError, ValueError) as exc:
        raise HelperError(f"{path} unreadable: {exc}") from None
    if not isinstance(obj, dict):
        raise HelperError(f"{path} is not a JSON object")
    return obj


def save_new(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Mode 'x': creation and the write-once refusal are one step.
        with open(path, "x", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, indent=2) + "\n")
    except FileExistsError:
        raise HelperError(f"refusing to overwrite {path}") from None


def jsonl(path: Path) -> list[dict]:
    # Stricter than the analysis reader (which skips a bad line silently): a
    # truncated line is what a fetch during a write looks like, and it would
    # turn a confirmed message into a lost one.
    records = []
    try:
        with open(path, encoding="utf-8") as fh:
            for number, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    obj = None
                if not isinstance(obj, dict):
                    raise HelperError(
                        f"{path} line {number} is not a JSON object "
                        "(truncated fetch?); fetch the file again"
                    )
                records.append(obj)
    except FileNotFoundError:
        raise HelperError(f"{path} missing") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise HelperError(f"{path} unreadable: {exc}") from None
    return records


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def load_marker(path: Path) -> dict:
    """The marker written by ``mark``, accepted only with the harness window."""
    marker = load(path)
    start = marker.get("monotonic_ns")
    if marker.get("ok") is not True or not is_int(start):
        raise HelperError(f"{path} holds no usable controller marker")
    if (
        marker.get("confirmation_window_s") != CONFIRMATION_WINDOW_S
        or marker.get("confirmation_deadline_monotonic_ns")
        != start + CONFIRMATION_WINDOW_S * NS
    ):
        raise HelperError(
            f"{path}: the recorded deadline is not marker + "
            f"{CONFIRMATION_WINDOW_S} s (CONFIRMATION_WINDOW_S); the window "
            "is never taken from a file"
        )
    return marker


def load_devices(path: Path) -> dict:
    devices = load(path).get("devices")
    if not isinstance(devices, dict):
        raise HelperError(f"{path} is not a twin snapshot (no 'devices')")
    if not devices:
        raise HelperError(f"{path} holds no device: nothing would be compared")
    for device_uuid, entry in devices.items():
        ingestion = entry.get("ingestion") if isinstance(entry, dict) else None
        if (
            not isinstance(ingestion, dict)
            or "device_type" not in entry
            or "exists" not in entry
            or any(k not in ingestion for k in INGESTION_KEYS)
            or not (ingestion["accepted_count"] is None
                    or is_int(ingestion["accepted_count"]))
        ):
            raise HelperError(f"{path}: malformed entry for {device_uuid}")
    return devices


# --- mark: end-of-run marker on the controller clock -----------------------
def cmd_mark(args) -> int:
    marker = poll_controller_marker(args.controller_url)
    # HOST stamp taken as soon as the poll has returned, before anything else,
    # as run.py does: polled_utc is stamped BEFORE the request, and the
    # controller reads its clock somewhere within the round trip.
    returned_utc = utc_now_iso()
    if not marker["ok"]:
        print(f"marker UNAVAILABLE: {marker['error']}", file=sys.stderr)
        return EXIT_FAILED
    marker["confirmation_window_s"] = CONFIRMATION_WINDOW_S
    marker["confirmation_deadline_monotonic_ns"] = (
        int(marker["monotonic_ns"]) + CONFIRMATION_WINDOW_S * NS
    )
    # Lag between the simulator's own finished_utc and the RETURN of this poll
    # (an upper bound: a slow GET /metrics must not read as no lag). Both
    # stamps are HOST wall-clock values, so they are comparable with each
    # other; the value is kept as computed, and a negative one warns. An
    # unreadable simulator manifest must not cost the marker just polled: the
    # lag is then unknown and the warning below says so.
    sim_manifest = Path(args.run_dir) / "manifest.json"
    lag = None
    if sim_manifest.is_file():
        try:
            finished = load(sim_manifest).get("finished_utc")
            if finished:
                lag = (
                    parse_utc(returned_utc) - parse_utc(finished)
                ).total_seconds()
        except (HelperError, AttributeError, TypeError, ValueError) as exc:
            print(f"lag not computable: {exc}", file=sys.stderr)
    marker["poll_returned_utc"] = returned_utc
    marker["lag_s"] = lag
    marker["lag_tolerance_s"] = CONTROLLER_MARKER_LAG_TOLERANCE_S
    save_new(sib(args.run_dir, ".marker.json"), marker)
    print(f"marker monotonic_ns={marker['monotonic_ns']} lag_s={lag}")
    if lag is None or lag < 0 or lag > CONTROLLER_MARKER_LAG_TOLERANCE_S:
        print(
            "WARNING: marker lag unknown, negative or above "
            f"{CONTROLLER_MARKER_LAG_TOLERANCE_S} s: the effective window was "
            f"{CONFIRMATION_WINDOW_S} s + lag, i.e. more lenient than plan 7.3",
            file=sys.stderr,
        )
    return EXIT_OK


# --- wait: until the CONTROLLER clock has passed the deadline --------------
def cmd_wait(args) -> int:
    marker = load_marker(sib(args.run_dir, ".marker.json"))
    deadline = marker["confirmation_deadline_monotonic_ns"]
    give_up = time.monotonic() + CONFIRMATION_WINDOW_S + args.extra_timeout
    while True:
        now = poll_controller_marker(args.controller_url)
        if now["ok"]:
            if int(now["monotonic_ns"]) < marker["monotonic_ns"]:
                print(
                    "controller clock went BACKWARDS (guest reboot?): the "
                    "marker is no longer usable for this run",
                    file=sys.stderr,
                )
                return EXIT_FAILED
            # Strictly after: a confirmation stamped exactly on the deadline
            # is still in-window (analyze.py: late means ack > deadline).
            if int(now["monotonic_ns"]) > deadline:
                save_new(sib(args.run_dir, ".window-closed.json"), now)
                print("confirmation window closed on the controller clock")
                return EXIT_OK
        if time.monotonic() > give_up:
            print("gave up waiting for the deadline", file=sys.stderr)
            return EXIT_FAILED
        time.sleep(WAIT_POLL_INTERVAL_S)


# --- check: the harness's own accounting on an ad-hoc run ------------------
def input_warnings(sim: dict, sent: list[dict], events: list[dict]) -> list[str]:
    """What the accounting cannot see: whether the files are this run's, whole.

    An ad-hoc run directory has no seal, and compute_run_metrics takes the
    files as given; nothing here changes a count, it only says so in the row.
    """
    found = []
    run_id = sim.get("run_id")
    for name, records in (("sent_events.jsonl", sent), ("events.jsonl", events)):
        foreign = sum(1 for r in records if r.get("run_id") != run_id)
        if foreign:
            found.append(
                f"{foreign} record(s) of {name} carry a run_id other than the "
                f"simulator manifest's ({run_id!r}): not this run's file?"
            )
    totals = sim.get("totals")
    declared = totals.get("sent") if isinstance(totals, dict) else None
    if not is_int(declared):
        found.append("simulator manifest carries no integer totals.sent: that "
                     "sent_events.jsonl is whole is not shown")
    elif declared != len(sent):
        found.append(
            f"sent_events.jsonl holds {len(sent)} record(s) but the simulator "
            f"manifest says totals.sent={declared}: incomplete copy?"
        )
    if sim.get("completed") is not True:
        found.append("simulator manifest: completed is not true")
    # One consumer takes the messages in arrival order and logs each before the
    # next (controller service.run), so within one clock the received stamps
    # never decrease along the append-only file. A decrease is a restarted
    # clock (guest reboot): every later stamp compares as in-window against
    # the marker deadline, whatever its real time.
    last, backwards, first_at = None, 0, None
    for number, record in enumerate(events, 1):
        stamp = record.get("received_monotonic_ns")
        if stamp is None:
            continue
        if last is not None and stamp < last:
            backwards += 1
            first_at = first_at or number
        last = stamp
    if backwards:
        found.append(
            f"controller clock went BACKWARDS along events.jsonl ({backwards} "
            f"time(s), first at record {first_at}; guest reboot?): the marker "
            "deadline does not apply to the records after it - NOT a protocol "
            "check for them"
        )
    return found


def cmd_check(args) -> int:
    # args.controller_url is accepted for symmetry with mark/wait and unused:
    # check reads files only.
    run_dir = Path(args.run_dir)
    marker_path = sib(args.run_dir, ".marker.json")
    closed = sib(args.run_dir, ".window-closed.json")
    # present and well-formed, or the step stops
    sent_records = jsonl(run_dir / "sent_events.jsonl")
    event_records = jsonl(run_dir / "events.jsonl")
    for number, record in enumerate(event_records, 1):
        for key in STAMPS:
            if not (record.get(key) is None or is_int(record[key])):
                raise HelperError(
                    f"{run_dir / 'events.jsonl'} record {number}: {key} is "
                    "neither an integer nor null"
                )
    if marker_path.is_file():
        marker = load_marker(marker_path)
        domain = "controller"
        if not closed.is_file():
            raise HelperError(
                f"{closed} missing: run 'wait' before fetching events.jsonl"
            )
        closed_ns = load(closed).get("monotonic_ns")
        if not is_int(closed_ns) or (
            closed_ns <= marker["confirmation_deadline_monotonic_ns"]
        ):
            raise HelperError(
                f"{closed} does not show the controller clock past the deadline"
            )
        if (run_dir / "events.jsonl").stat().st_mtime < closed.stat().st_mtime:
            raise HelperError(
                "events.jsonl was fetched BEFORE the window closed: in-window "
                "confirmations may be missing; fetch it again"
            )
    else:
        # No marker was taken at the end of the run: the harness analysis
        # then falls back to its LEGACY event-derived deadline and says so.
        marker = {"ok": False, "monotonic_ns": None, "lag_s": None,
                  "confirmation_deadline_monotonic_ns": None,
                  "error": f"{marker_path} missing"}
        domain = "unavailable"
    sim = load(run_dir / "manifest.json")
    work = sib(args.run_dir, ".reconcile")
    if work.exists():
        shutil.rmtree(work)  # derived data only; rebuilt on every check
    # A check that stops below must not leave the row of an earlier one.
    sib(args.run_dir, ".reconcile.json").unlink(missing_ok=True)
    work.mkdir(parents=True)
    for name in ("sent_events.jsonl", "events.jsonl"):
        shutil.copy2(run_dir / name, work / name)
    manifest = {
        "manifest_kind": "itest-adhoc-reconcile (NOT a harness run)",
        "run_id": sim.get("run_id") or run_dir.name,
        "scenario": sim.get("scenario"),
        "seed": sim.get("seed"),
        "confirmation_window_s": CONFIRMATION_WINDOW_S,
        "controller_marker": marker,
        "controller_monotonic_at_run_end_ns": marker["monotonic_ns"],
        "confirmation_deadline_monotonic_ns": marker[
            "confirmation_deadline_monotonic_ns"
        ],
        "confirmation_deadline_clock_domain": domain,
    }
    (work / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    try:
        row = compute_run_metrics(work)
    except (KeyError, TypeError, ValueError) as exc:
        raise HelperError(
            f"compute_run_metrics cannot read the run files: {exc!r}"
        ) from None
    if row is None:
        raise HelperError("compute_run_metrics returned no row")
    row.pop("_resources", None)
    keys = (
        "run_id", "confirmation_deadline_source", "sent_total", "sent_valid",
        "intended_invalid_sent", "delivered_unique", "lost",
        "late_confirmations", "duplicates", "double_accepted", "failed",
        "rejected_valid", "rejected_intended_invalid", "rejected_unmatched",
        "intended_invalid_accepted", "confirmed_unmatched",
        "events_accepted_total", "latency_count", "latency_ms_p50",
        "latency_ms_p95", "latency_ms_max",
    )
    out = {k: row[k] for k in keys}
    out["marker_lag_s"] = marker.get("lag_s")
    out["sim_completed"] = sim.get("completed")
    out["sim_totals"] = sim.get("totals")
    out["latency_label"] = "ARM64 EMULATED (QEMU/TCG); not a performance result"
    # Warnings about the seal, resources.csv, controller_metrics.csv,
    # resource_source and the measured window are expected here: an ad-hoc
    # run has none of that instrumentation. Every other warning is shown.
    expected = ("evidence integrity unverifiable", "resources.csv missing",
                "controller_metrics.csv missing", "resource_source",
                "manifest has no usable measured_window_utc")
    out["warnings"] = input_warnings(sim, sent_records, event_records) + [
        w for w in str(row["warnings"]).split(" | ")
        if w and not w.startswith(expected)
    ]
    sib(args.run_dir, ".reconcile.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    if out["warnings"]:
        print(f"WARNING: {len(out['warnings'])} warning(s) in the row above; "
              "the exit status does not reflect them", file=sys.stderr)
    if out["confirmation_deadline_source"] != "controller-marker":
        print("NOT a protocol check: deadline not on the controller marker",
              file=sys.stderr)
        return EXIT_NOT_PROTOCOL
    return EXIT_OK


# --- snap: twin ingestion state of identified devices ----------------------
def get_twin(ditto_url: str, device_uuid: str):
    url = f"{ditto_url.rstrip('/')}/api/2/things/org.c2dta:{device_uuid}"
    req = urllib.request.Request(url, headers=PREAUTH)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def cmd_snap(args) -> int:
    if args.seed is not None:
        types = tuple(t for t in args.devices.split(",") if t)
        try:
            devices = {d.device_uuid: d.device_type
                       for d in make_devices(args.seed, types)}
        except ValueError as exc:
            raise HelperError(str(exc)) from None
    else:
        base = load_devices(sib(args.prefix, f".twins.{args.like}.json"))
        devices = {u: e["device_type"] for u, e in base.items()}
    if not devices:
        raise HelperError("no device selected: --devices is empty")
    snap = {"label": args.label, "seed": args.seed, "devices": {}}
    for device_uuid, device_type in devices.items():
        # All or nothing: one failed read and no snapshot file is written.
        try:
            twin = get_twin(args.ditto_url, device_uuid)
        except (OSError, ValueError) as exc:
            raise HelperError(f"GET thing {device_uuid} failed: {exc}") from None
        if twin is not None and not isinstance(twin, dict):
            raise HelperError(f"GET thing {device_uuid}: not a JSON object")
        props = {}
        if twin is not None:
            props = ((twin.get("features") or {}).get("ingestion") or {}).get(
                "properties") or {}
        snap["devices"][device_uuid] = {
            "device_type": device_type,
            "exists": twin is not None,
            "ingestion": {k: props.get(k) for k in INGESTION_KEYS},
        }
    save_new(sib(args.prefix, f".twins.{args.label}.json"), snap)
    print(json.dumps(snap, indent=2))
    return EXIT_OK


# --- delta: per-device and per-process differences vs the event log --------
#: The first line of the N1 report delta adds (decision 2 of 2026-09-30).
N1_HEADER = ("N1 REPORT (explanation only; lost and every delta status "
             "unchanged)")


def _restart_evidence(run_dir: Path, primary_run, primary: list[dict],
                      before: dict, after: dict):
    """The death source and the condition-3 problems a harness run directory
    gives the N1 report: (deaths, deaths_note, problems). Everything is read
    tolerantly; what cannot be read is named, never raised. The texts name
    the snapshots by their role ('from', 'to'), never by the labels or the
    paths given, so that no added line can spell a status word."""
    manifest, why = n1_report.read_json_object(run_dir / MANIFEST_FILENAME)
    if manifest is None:
        text = f"restart evidence not read ({why})"
        return None, text, [text + ": the drain and the snapshots are not shown"]
    if manifest.get("run_id") != primary_run:
        text = ("restart evidence not read as this run's: its manifest names "
                "another run id than the compared events")
        return None, text, [text]
    try:
        facts, manifest = rq.run_facts(run_dir, str(primary_run), planned=False)
        deaths, deaths_note = rq.n1_death_source(run_dir, manifest)
    except Exception as exc:  # broad on purpose: a malformed record is "not read", never exit 1
        text = f"restart evidence not read ({type(exc).__name__})"
        return None, text, [text]
    problems = []
    problem = rq.n1_evidence_problem(facts)
    if problem is not None:
        problems.append(problem)
    # The snapshots and the copy delta compares must be the verified ones.
    for role, devices, hook in (("from", before, "twin_snapshot_before"),
                                ("to", after, "twin_snapshot_after")):
        file = TWIN_SNAPSHOT_FILES[hook]
        verified = n1_report.twin_devices(
            n1_report.read_json_object(run_dir / file)[0])
        if verified != devices:
            problems.append(f"the '{role}' snapshot compared is not the run's "
                            f"verified snapshot {file}")
    post_drain, _why = n1_report.read_jsonl(run_dir / POST_DRAIN_EVENTS_FILENAME)
    if post_drain != primary:
        problems.append("the events copy compared is not the run's verified "
                        f"post-drain copy ({POST_DRAIN_EVENTS_FILENAME})")
    return deaths, deaths_note, problems


#: The terms of the accounting identity of one /metrics reading (CONTRACTS
#: 5): received equals their sum.
IDENTITY_TERMS = ("accepted", "rejected", "duplicate", "failed", "dropped",
                  "processing_errors", "in_progress", "queue_depth")


def quiet_reading_problem(reading: dict) -> str | None:
    """Why one /metrics reading is not shown quiet as CONTRACTS 5 defines a
    quiet reading, or None: queue_depth, in_progress and unacked 0,
    mqtt_subscribed true and the accounting identity holding, every value
    from that one reading (the runbook's 'drained' reads each reading so).
    A field that is absent or not of its type is never read as zero or
    false. One reading is not drained's quiet window: that window is the
    runbook's (finish takes the 'after' pair only after 'drained'), and
    delta cannot re-check it."""
    unread = [key for key in ("received", "unacked") + IDENTITY_TERMS
              if not (is_int(reading.get(key)) and reading[key] >= 0)]
    if not isinstance(reading.get("mqtt_subscribed"), bool):
        unread.append("mqtt_subscribed")
    if unread:
        return f"{', '.join(unread)} absent or not of the contract's type"
    busy = [f"{key}={reading[key]}" for key in ("queue_depth", "in_progress", "unacked")
            if reading[key] != 0]
    if reading["mqtt_subscribed"] is not True:
        busy.append("mqtt_subscribed=false")
    if busy:
        return ", ".join(busy)
    total = sum(reading[key] for key in IDENTITY_TERMS)
    if reading["received"] != total:
        return (f"the accounting identity fails (received {reading['received']}, "
                f"the sum of its terms {total})")
    return None


def n1_delta_report(args, primary: list[dict], events: list[dict], primary_run,
                    before: dict, after: dict, to_reading: dict | None) -> dict:
    """The N1 report (decision 2 of 2026-09-30) of the log and snapshots
    delta compares, with the sources its options name. The options' labels
    and paths are named by their role ('to', the --controller-log file),
    never echoed."""
    sent, sent_why = n1_report.read_jsonl(Path(args.run_dir) / "sent_events.jsonl")
    problems = []
    if to_reading is not None:
        why = quiet_reading_problem(to_reading)
        if why is not None:
            problems.append("the 'to' /metrics reading is not shown quiet "
                            f"(CONTRACTS 5): {why}")
    deaths, deaths_note = None, "no --restart-evidence given"
    if args.restart_evidence:
        deaths, deaths_note, more = _restart_evidence(
            Path(args.restart_evidence), primary_run, primary, before, after)
        problems += more
    elif to_reading is None:
        problems.append("no evidence that the 'to' snapshot follows a quiet "
                        "drain (no --restart-evidence and no 'to' /metrics "
                        "reading)")
    ends, a3_note = None, "no --controller-log given"
    if args.controller_log:
        lines, a3_note = n1_report.read_text_lines(
            args.controller_log, name="the --controller-log file")
        if lines is not None:
            ends = n1_report.a3_connection_ends(lines)
    report = n1_report.n1_applied_unconfirmed(
        run_id=primary_run, sent_records=sent, events=events,
        twins_before=before, twins_after=after,
        twin_evidence_problem="; ".join(problems) or None,
        deaths=deaths, deaths_note=deaths_note, a3_ends=ends, a3_note=a3_note)
    return {"report": report, "sent_note": sent_why}


def n1_annotation(case: dict) -> str:
    """The line under a device line for one named identity."""
    sources = [
        f"{n1_report.SOURCE_A3} at controller log line "
        f"{s.get('controller_log_line')}"
        if s.get("source") == n1_report.SOURCE_A3 else str(s.get("source"))
        for s in case["possible_sources"]
    ]
    return (f"  n1_applied_unconfirmed on {case['device_uuid']}: "
            f"{case['message_id']} seq {case['seq']} (possible "
            f"source{'' if len(sources) == 1 else 's'}: {'; '.join(sources)}) "
            "- reported, not delivered: it stays in lost and its device line "
            "stays a mismatch")


def n1_summary(n1: dict) -> list[str]:
    """The lines printed after delta's last line: the counts, the sources,
    what leaves condition 3 unshown, each unexplained identity with its
    failed conditions, and what the report does not change."""
    report = n1["report"]
    named = report["n1_applied_unconfirmed"]
    unexplained = report["duplicate_only_unexplained"]
    src = report["sources"]
    if src["controller_log_read"]:
        log = (f"controller log (--controller-log): {src['a3_ends']} A3 "
               "connection end(s)")
    else:
        log = f"controller log not read ({src['controller_log_note']})"
    if src["deaths"]:
        dies = src["deaths"][0].get("dies_in_window")
        death = (f"controller death: one death counted ({dies} "
                 f"{'die' if dies == 1 else 'dies'} of "
                 f"{n1_report.CONTROLLER_CONTAINER} captured in the window)")
    elif src["deaths_read"]:
        death = f"controller death: none ({src['deaths_note']})"
    else:
        death = f"controller death not read ({src['deaths_note']})"
    lines = [
        f"{N1_HEADER}: n1_applied_unconfirmed={len(named)} "
        f"duplicate_only_unexplained={len(unexplained)}",
        f"  sources: {log}; {death}",
    ]
    if n1["sent_note"]:
        lines.append(f"  sent_events.jsonl not read ({n1['sent_note']}): no "
                     "identity is shown valid")
    if report["twin_evidence_problem"]:
        lines.append(f"  condition 3 evidence: {report['twin_evidence_problem']}")
    for case in unexplained:
        device = ("no single device" if case["device_uuid"] is None
                  else case["device_uuid"])
        lines.append(f"  duplicate_only_unexplained {case['message_id']} on "
                     f"{device} seq {case['seq']}: failed "
                     f"condition(s) {', '.join(case['failed'])}: {case['reason']}")
    lines += [f"  note: {note}" for note in report["notes"]]
    lines.append(f"  {report['note']}")
    return lines


def n1_delta_lines(args, primary: list[dict], events: list[dict], primary_run,
                   before: dict, after: dict,
                   to_reading: dict | None) -> tuple[dict[str, list[str]], list[str]]:
    """The lines the N1 report adds, made before delta prints its first
    line: (the annotation lines by device, the summary lines). Never
    raises: a report that cannot be made is one summary line saying so,
    and delta's own lines and exit stand."""
    try:
        n1 = n1_delta_report(args, primary, events, primary_run, before, after,
                             to_reading)
        annotations: dict[str, list[str]] = {}
        for case in n1["report"]["n1_applied_unconfirmed"]:
            annotations.setdefault(case["device_uuid"], []).append(n1_annotation(case))
        return annotations, n1_summary(n1)
    except Exception as exc:  # broad on purpose: the report never changes delta's lines or exit
        return {}, [f"{N1_HEADER}: not made ({type(exc).__name__}); no "
                    "identity is named"]


def cmd_delta(args) -> int:
    prefix = args.prefix or args.run_dir
    before = load_devices(sib(prefix, f".twins.{args.frm}.json"))
    after = load_devices(sib(prefix, f".twins.{args.to}.json"))
    # The log the twins are compared with: the run directory's timed copy,
    # or the copy --events names (the post-drain copy of the runbook's test
    # 6). The timed file is only ever read here.
    events_path = Path(args.events) if args.events else Path(args.run_dir) / "events.jsonl"
    log_name = events_path.name
    primary = jsonl(events_path)
    events = list(primary)
    for path in args.also:
        events += jsonl(Path(path))
    m_before = sib(prefix, f".metrics.{args.frm}.json")
    m_after = sib(prefix, f".metrics.{args.to}.json")
    readings = {}
    for path in (m_before, m_after):
        if not path.is_file():
            continue
        body = load(path)
        # started_at identifies the controller PROCESS (CONTRACTS 5); without
        # it nothing shows that both readings belong to one process.
        if not isinstance(body.get("started_at"), str) or any(
            not is_int(body.get(key)) for key in COUNTERS + ("queue_depth",)
        ):
            raise HelperError(
                f"{path} is not a /metrics reading (started_at and the "
                f"integer counters {', '.join(COUNTERS)} and queue_depth are "
                "required)"
            )
        readings[path] = body
    # events.jsonl is one file per run_id (controller EventLogger bucket).
    primary_run = next((e["run_id"] for e in primary if e.get("run_id")), None)
    # The N1 report (decision 2 of 2026-09-30), opt-in: made before any line
    # is printed, from sources read tolerantly; it never touches 'ok'.
    n1 = None
    if args.n1_report or args.controller_log or args.restart_evidence:
        n1 = n1_delta_lines(args, primary, events, primary_run, before, after,
                            readings.get(m_after))
    ok = True
    # The loop below filters the log by the snapshot; this filters the snapshot
    # by the log. A snapshot taken with another seed or --devices than the run
    # would otherwise close with 'OK' on twins that were never touched.
    accepted_by_device = Counter(
        e.get("device_uuid") for e in events if e.get("outcome") == "accepted"
    )
    for device_uuid, count in accepted_by_device.items():
        if device_uuid not in before:
            ok = False
            print(f"{device_uuid}: {count} accepted record(s) in {log_name} "
                  f"but absent from the '{args.frm}' snapshot (another seed or "
                  "--devices than the run?): MISMATCH")
    for device_uuid, b in before.items():
        a = after.get(device_uuid)
        if a is None:
            ok = False
            print(f"{device_uuid} {b['device_type']}: absent from the "
                  f"'{args.to}' snapshot: MISMATCH")
            continue
        # EVERY accepted record counts here, late and repeated ones included:
        # the controller increments accepted_count once per accepted outcome.
        acc = [e for e in events if e.get("device_uuid") == device_uuid
               and e.get("outcome") == "accepted"]
        d = (a["ingestion"]["accepted_count"] or 0) - (
            b["ingestion"]["accepted_count"] or 0)
        line_ok = d == len(acc)
        seqs = [e["seq"] for e in acc
                if e.get("run_id") == primary_run and is_int(e.get("seq"))]
        if seqs:
            line_ok = (line_ok
                       and a["ingestion"]["last_run_id"] == primary_run
                       and a["ingestion"]["last_seq"] == max(seqs))
        ok = ok and line_ok
        print(f"{device_uuid} {b['device_type']}: existed_before={b['exists']} "
              f"accepted_count {b['ingestion']['accepted_count']} -> "
              f"{a['ingestion']['accepted_count']} (delta {d}); accepted "
              f"records in {log_name} {len(acc)}; last_run_id "
              f"{a['ingestion']['last_run_id']} last_seq "
              f"{a['ingestion']['last_seq']}: {'OK' if line_ok else 'MISMATCH'}")
        if n1 is not None:
            for text in n1[0].get(device_uuid, []):
                print(text)
    if len(readings) < 2:
        missing = [str(p) for p in (m_before, m_after) if p not in readings]
        print(f"/metrics: NOT compared ({' and '.join(missing)} missing)")
    else:
        mb, ma = readings[m_before], readings[m_after]
        outcomes = Counter(e.get("outcome") for e in events)
        if mb["started_at"] != ma["started_at"]:
            print("/metrics: controller process RESTARTED between the two "
                  "snapshots (started_at differs); its counters restarted "
                  "from zero, so no delta is computed")
        else:
            for key in COUNTERS:
                dm = ma[key] - mb[key]
                note = ""
                if key != "dropped":
                    same = dm == outcomes.get(key, 0)
                    ok = ok and same
                    note = (f"; {log_name} {outcomes.get(key, 0)}: "
                            f"{'OK' if same else 'MISMATCH'}")
                print(f"/metrics {key}: {mb[key]} -> {ma[key]} "
                      f"(delta {dm}){note}")
    # The 'to' reading alone settles this, whatever happened to the other one.
    if m_after in readings and readings[m_after]["queue_depth"] != 0:
        ok = False
        print(f"/metrics queue_depth={readings[m_after]['queue_depth']} in "
              "the 'to' snapshot: the controller was still draining; repeat "
              "the fetch and the snapshots under a new label")
    if n1 is not None:
        for text in n1[1]:
            print(text)
    return EXIT_OK if ok else EXIT_MISMATCH


# --- same: two snapshots must be identical (persistence checks) ------------
def cmd_same(args) -> int:
    a = load_devices(sib(args.prefix, f".twins.{args.label_a}.json"))
    b = load_devices(sib(args.prefix, f".twins.{args.label_b}.json"))
    ok = a == b
    for device_uuid in a:
        state = "identical" if a[device_uuid] == b.get(device_uuid) else "DIFFERENT"
        print(f"{device_uuid}: {state} {a[device_uuid]['ingestion']}")
    for device_uuid in b:
        if device_uuid not in a:
            print(f"{device_uuid}: DIFFERENT (only in '{args.label_b}')")
    return EXIT_OK if ok else EXIT_MISMATCH


# --- shared by acceptance and replay-check: identities of one run -----------
def sent_identities(path: Path) -> tuple[str, dict[str, dict]]:
    """The run id and the published records of a sent_events.jsonl.

    One run's file or nothing: every record carries the same non-empty run_id
    and a non-empty message_id that no other record carries. Otherwise the
    identities cannot be told apart and nothing is judged. And the whole
    file: the simulator manifest beside it (written last, in a finally) must
    count as many published records (totals.sent) as the file holds; a
    message missing from the file would never be judged, which is not the
    same as judged and passed.
    """
    records = jsonl(path)
    if not records:
        raise HelperError(
            f"{path} holds no published record: nothing would be judged")
    run_ids = {r.get("run_id") if isinstance(r.get("run_id"), str) else None
               for r in records}
    run_id = run_ids.pop() if len(run_ids) == 1 else None
    if not run_id:
        raise HelperError(f"{path}: the records do not all carry one run_id "
                          "- not one run's file")
    by_id: dict[str, dict] = {}
    for number, record in enumerate(records, 1):
        message_id = record.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            raise HelperError(f"{path} record {number} has no usable "
                              "message_id: NOT reconcilable by identity")
        if message_id in by_id:
            raise HelperError(f"{path}: message_id {message_id} occurs more "
                              "than once: NOT reconcilable by identity")
        by_id[message_id] = record
    manifest_path = path.parent / "manifest.json"
    totals = load(manifest_path).get("totals")
    declared = totals.get("sent") if isinstance(totals, dict) else None
    if not is_int(declared) or declared != len(records):
        raise HelperError(
            f"{path} holds {len(records)} record(s) but {manifest_path} "
            f"gives totals.sent={declared!r}: the file is not shown to hold "
            "every message the simulator published")
    return run_id, by_id


def message_key(record: dict) -> str | None:
    message_id = record.get("message_id")
    return message_id if isinstance(message_id, str) else None


def named(label: str, ids: list[str], note=None, limit: int = 20) -> None:
    for message_id in ids[:limit]:
        print(f"  {label}: {message_id}{note(message_id) if note else ''}")
    if len(ids) > limit:
        print(f"  {label}: ... and {len(ids) - limit} more")


# --- acceptance: test 3, every valid message accepted by the end of the drain
def outcome_lines(outcomes: list) -> str:
    """The outcome lines of one identity: failed, duplicate or other (named)."""
    if not outcomes:
        return "none"
    kinds = Counter(o if o in ("failed", "duplicate") else "other"
                    for o in outcomes)
    text = ", ".join(f"{k} x{kinds[k]}"
                     for k in ("failed", "duplicate", "other") if kinds[k])
    others = sorted({str(o) for o in outcomes
                     if o not in ("failed", "duplicate")})
    return text + (f" ({', '.join(others)})" if others else "")


def cmd_acceptance(args) -> int:
    sent_path = Path(args.run_dir) / "sent_events.jsonl"
    run_id, published = sent_identities(sent_path)
    events_path = Path(args.events)
    events = jsonl(events_path)
    # Valid unless the simulator marked it intended invalid: only a literal
    # true exempts a message, any other value keeps it required.
    valid = [m for m, r in published.items()
             if r.get("intended_invalid") is not True]
    if not valid:
        raise HelperError(
            f"{sent_path} holds no valid message: nothing would be judged")
    # The identity is the message_id WITHIN this run id. No timestamp is
    # read: an acceptance after the controller-clock deadline counts, as long
    # as it is in this copy (the end of the planned collection).
    lines: dict[str, list] = {m: [] for m in valid}
    for record in events:
        message_id = message_key(record)
        if record.get("run_id") == run_id and message_id in lines:
            lines[message_id].append(record.get("outcome"))
    never = [m for m in valid if "accepted" not in lines[m]]
    print(f"ACCEPTANCE BY THE END OF THE DRAIN {run_id} ({events_path.name}): "
          f"valid={len(valid)} accepted by the end of the drain="
          f"{len(valid) - len(never)} never accepted={len(never)}")
    for message_id in never:  # each one: the list is the evidence
        record = published[message_id]
        print(f"  NEVER ACCEPTED: {message_id} ({record.get('device_type')} "
              f"seq={record.get('seq')}) outcome lines in the copy: "
              f"{outcome_lines(lines[message_id])}")
    if never:
        print(f"-> FAIL: {len(never)} valid message(s) of {run_id} have no "
              f"accepted line in {events_path.name}")
        return EXIT_MISMATCH
    print(f"-> OK: every valid message of {run_id} has an accepted line in "
          f"{events_path.name} (a late acceptance counts: no deadline is "
          "applied)")
    return EXIT_OK


# --- replay-check: test 4, the replay judged per identity -------------------
#: The cumulative /metrics fields of the contract's same-process rule
#: (CONTRACTS 5, "Restart between two readings A and B", rule 1), with
#: mqtt_connection, cumulative too: none may decrease from A to B.
SAME_PROCESS_COUNTERS = ("received", "accepted", "rejected", "duplicate",
                         "failed", "dropped", "processing_errors",
                         "mqtt_connection")


def load_reading(path: Path) -> dict:
    """A /metrics reading with every field replay-check reads.

    started_at a non-empty string, uptime_s a non-negative number, the
    cumulative counters and queue_depth non-negative integers (is_int: not a
    bool, not a float). An absent field is never read as zero.
    """
    body = load(path)
    started_at = body.get("started_at")
    bad = [] if isinstance(started_at, str) and started_at else ["started_at"]
    uptime = body.get("uptime_s")
    if not (isinstance(uptime, (int, float)) and not isinstance(uptime, bool)
            and math.isfinite(uptime) and uptime >= 0):
        bad.append("uptime_s")
    bad += [key for key in SAME_PROCESS_COUNTERS + ("queue_depth",)
            if not (is_int(body.get(key)) and body[key] >= 0)]
    if bad:
        raise HelperError(
            f"{path} is not a usable /metrics reading: {', '.join(bad)} "
            "absent or not of its type; an absent field is never read as zero"
        )
    return body


def read_bytes(path: Path) -> bytes:
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        raise HelperError(f"{path} missing") from None
    except OSError as exc:
        raise HelperError(f"{path} unreadable: {exc}") from None


def cmd_replay_check(args) -> int:
    prefix = args.prefix or args.run_dir
    run_id, replayed = sent_identities(
        Path(args.replay_dir) / "sent_events.jsonl")
    ids = list(replayed)
    # The replay interval of the log: the lines the re-fetched events.jsonl
    # holds beyond the pre-replay copy. The guest log is append-only, so the
    # copy must be a byte prefix of it that ends on a whole line.
    before_path = (Path(args.events_before) if args.events_before
                   else sib(prefix, ".events.pre-replay.jsonl"))
    log_path = Path(args.run_dir) / "events.jsonl"
    before_bytes, log_bytes = read_bytes(before_path), read_bytes(log_path)
    if not before_bytes.endswith(b"\n"):
        raise HelperError(f"{before_path} is empty or does not end with a "
                          "whole line: the replay interval cannot be told")
    if not log_bytes.startswith(before_bytes):
        raise HelperError(f"{before_path} is not a prefix of {log_path}: the "
                          "guest log is append-only, so these are not two "
                          "readings of one log")
    before, log = jsonl(before_path), jsonl(log_path)
    for number, record in enumerate(log, 1):
        if record.get("run_id") != run_id:
            raise HelperError(
                f"{log_path} record {number} carries run_id "
                f"{record.get('run_id')!r}, not the replay's {run_id!r}: not "
                "this run's log")
    added = log[len(before):]
    frm = sib(prefix, f".metrics.{args.frm}.json")
    ma, mr = load_reading(frm), load_reading(
        sib(prefix, f".metrics.{args.to}.json"))
    # One process first (CONTRACTS 5): no difference across two processes.
    reasons = [] if ma["started_at"] == mr["started_at"] else [
        f"started_at {ma['started_at']} != {mr['started_at']}"]
    reasons += [f"{key} {ma[key]} -> {mr[key]} decreased"
                for key in ("uptime_s", *SAME_PROCESS_COUNTERS)
                if mr[key] < ma[key]]
    if not reasons:
        # Within one process the controller stamps every line on the clock of
        # the readings (CONTRACTS 5, received_monotonic_ns). The copy was
        # fetched before the 'from' reading, so a line received at or before
        # that reading is the first run's, appended after the fetch, and by
        # position alone it would stand for a line of the replay (the same
        # run id and message_id). Across two processes the stamps are not
        # compared (a new boot restarts the clock): the check fails below.
        at = ma.get("monotonic_ns")
        if not is_int(at):
            raise HelperError(
                f"{frm}: monotonic_ns absent or not an integer: no line can "
                "be shown to be the replay's; an absent field is never read "
                "as zero")
        early = [number for number, record in enumerate(added, len(before) + 1)
                 if not (is_int(record.get("received_monotonic_ns"))
                         and record["received_monotonic_ns"] > at)]
        if early:
            raise HelperError(
                f"{log_path} record {early[0]} ({len(early)} line(s) in all) "
                f"is beyond {before_path.name} but was received at or before "
                f"the '{args.frm}' reading (monotonic_ns {at}), or carries no "
                "integer received_monotonic_ns: it is not shown to be the "
                "replay's, so the replay interval cannot be told")

    def by_identity(records: list[dict], outcome: str) -> Counter:
        return Counter(message_key(r) for r in records
                       if r.get("outcome") == outcome)

    # Raw lines, not the in-window accounting of compute_run_metrics, which
    # files a late repeat under late_confirmations, never double_accepted.
    added_dup = by_identity(added, "duplicate")
    added_acc = by_identity(added, "accepted")
    total_acc = by_identity(log, "accepted")
    no_dup = [m for m in ids if added_dup[m] == 0]
    acc_from_replay = [m for m in ids if added_acc[m] > 0]
    multi_acc = [m for m in ids if total_acc[m] > 1]
    duplicate_replayed = len(ids) - len(no_dup)
    # every further duplicate line: the second and later of a replayed
    # identity and any of an identity that was not replayed
    duplicate_redelivery = sum(added_dup.values()) - duplicate_replayed
    outcomes = ("accepted", "duplicate", "rejected", "failed")
    kinds = Counter(r.get("outcome") if r.get("outcome") in outcomes
                    else "other" for r in added)
    print(f"REPLAY CHECK {run_id}: replayed identities={len(ids)}; lines "
          f"added since the pre-replay copy={len(added)} ("
          + ", ".join(f"{k} {kinds[k]}" for k in (*outcomes, "other")) + ")")
    failed: list[str] = []

    def judge(ok: bool, text: str, what: str = "") -> None:
        print(f"{text}: {'OK' if ok else 'FAIL'}")
        if not ok:
            failed.append(what)

    judge(not no_dup, f"per identity: duplicate_replayed={duplicate_replayed} "
          f"of {len(ids)} (replayed identities that gained a duplicate line "
          "from the replay)", "a replayed identity without a duplicate line")
    judge(not acc_from_replay, f"per identity: {len(acc_from_replay)} "
          "replayed identity(ies) gained an accepted line from the replay "
          "(must be 0)", "an accepted line from the replay")
    judge(not multi_acc, f"per identity: {len(multi_acc)} replayed "
          "identity(ies) with more than one accepted line in the log (raw "
          "lines; double_accepted must be 0)", "more than one accepted line")
    labels = f"'{args.frm}' -> '{args.to}'"
    if reasons:
        judge(False, f"/metrics {labels}: NOT one controller process "
              f"({'; '.join(reasons)}): the readings are of different "
              "processes and no difference is taken",
              "readings of two processes")
        judge(False, f"duplicate_redelivery={duplicate_redelivery} (further "
              "duplicate lines added during the replay interval): the "
              "reconnection budget is not evaluable across two processes",
              "the reconnection budget not evaluable")
        judge(False, "/metrics accepted: not evaluable across two processes",
              "/metrics accepted not evaluable")
    else:
        judge(True, f"/metrics {labels}: one controller process (same "
              f"started_at; uptime_s and {', '.join(SAME_PROCESS_COUNTERS)} "
              "non-decreasing)")
        budget = mr["mqtt_connection"] - ma["mqtt_connection"]
        text = (f"duplicate_redelivery={duplicate_redelivery} (further "
                "duplicate lines added during the replay interval); "
                f"mqtt_connection {ma['mqtt_connection']} -> "
                f"{mr['mqtt_connection']} (delta {budget})")
        if duplicate_redelivery == 0:
            judge(True, text)
        elif duplicate_redelivery <= budget:
            # A tolerance only: a delta of mqtt_connection counts successful
            # CONNACKs, so an extra duplicate and an unrelated reconnection
            # can meet the ceiling together.
            judge(True, f"{text}: consistent with the reconnection budget "
                  "(tolerated, not attributed)")
        else:
            judge(False, f"{text}: beyond the reconnection budget",
                  "further duplicates beyond the reconnection budget")
        moved = mr["accepted"] - ma["accepted"]
        judge(moved == 0, f"/metrics accepted: {ma['accepted']} -> "
              f"{mr['accepted']} (delta {moved})", "/metrics accepted moved")
    # The 'to' reading alone settles this, as in delta.
    judge(mr["queue_depth"] == 0, f"/metrics queue_depth={mr['queue_depth']} "
          f"in the '{args.to}' reading", "a non-empty queue")
    if reasons:
        print("/metrics duplicate: not differenced across two processes "
              "(reported, decides nothing)")
    else:
        total = duplicate_replayed + duplicate_redelivery
        moved = mr["duplicate"] - ma["duplicate"]
        print(f"/metrics duplicate: {ma['duplicate']} -> {mr['duplicate']} "
              f"(delta {moved}); duplicate_replayed + duplicate_redelivery = "
              f"{duplicate_replayed} + {duplicate_redelivery} = {total}: "
              f"{'equal' if moved == total else 'NOT EQUAL'} (reported, "
              "decides nothing)")
    named("NO DUPLICATE FROM THE REPLAY", no_dup)
    named("ACCEPTED FROM THE REPLAY", acc_from_replay)
    named("MORE THAN ONE ACCEPTED LINE", multi_acc,
          lambda m: f" ({total_acc[m]} accepted lines)")
    if failed:
        print(f"-> FAIL: {'; '.join(failed)}")
        return EXIT_MISMATCH
    print("-> OK: every replayed identity gained a duplicate line and no "
          "accepted line from the replay, none has more than one accepted "
          "line, the further duplicates are within the reconnection budget, "
          "and the two /metrics readings are of one process with accepted "
          "unchanged and an empty queue")
    return EXIT_OK


COMMANDS = {"mark": cmd_mark, "wait": cmd_wait, "check": cmd_check,
            "snap": cmd_snap, "delta": cmd_delta, "same": cmd_same,
            "acceptance": cmd_acceptance, "replay-check": cmd_replay_check}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m egw_experiments.itest_reconcile",
        description=__doc__.splitlines()[0],
        epilog="exit codes: 0 step carried out (check: not a verdict); "
               "1 step not carried out; 2 usage; 3 check: not a protocol "
               "check; 4 delta: MISMATCH or queue not empty, same: DIFFERENT, "
               "acceptance: a valid message never accepted, replay-check: "
               "a condition of test 4 failed",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("mark", "wait", "check"):
        s = sub.add_parser(name)
        s.add_argument("run_dir")
        s.add_argument("--controller-url", default="http://127.0.0.1:8000")
        if name == "wait":
            s.add_argument("--extra-timeout", type=float, default=120.0)
    s = sub.add_parser("snap")
    s.add_argument("--prefix", required=True)
    s.add_argument("--label", required=True)
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--devices", default=",".join(DEVICE_TYPES))
    s.add_argument("--like", default="before")
    s.add_argument("--ditto-url", default="http://127.0.0.1:8080")
    s = sub.add_parser("delta")
    s.add_argument("run_dir")
    s.add_argument("--prefix", default=None)
    s.add_argument("--from", dest="frm", default="before")
    s.add_argument("--to", default="after")
    s.add_argument("--events", default=None,
                   help="the copy of the event log to compare the twins with "
                        "(default: <run_dir>/events.jsonl, the timed copy); "
                        "the runbook's test 6 names the post-drain copy, "
                        "events.post-drain.jsonl")
    s.add_argument("--also", action="append", default=[],
                   help="extra events.jsonl of ANOTHER run id (e.g. the "
                        "harness warm-up run); never a second copy of the "
                        "same records, which would be counted twice")
    s.add_argument("--n1-report", action="store_true",
                   help="add the N1 report (decision 2 of 2026-09-30): the "
                        "duplicate-only identities, named "
                        "n1_applied_unconfirmed or duplicate_only_unexplained; "
                        "an explanation that changes no line status and no "
                        "exit code")
    s.add_argument("--controller-log", default=None, metavar="FILE",
                   help="the run's controller log, the A3 source of the N1 "
                        "report (implies --n1-report)")
    s.add_argument("--restart-evidence", default=None, metavar="RUN_DIR",
                   help="a harness run directory: its restart record and "
                        "Docker events capture are the death source of the N1 "
                        "report, placed by its controller_metrics.csv, its "
                        "drain and verified snapshots the evidence for "
                        "condition 3 (implies --n1-report)")
    s = sub.add_parser("same")
    s.add_argument("--prefix", required=True)
    s.add_argument("label_a")
    s.add_argument("label_b")
    s = sub.add_parser("acceptance")
    s.add_argument("run_dir")
    s.add_argument("--events", required=True,
                   help="the copy of the event log fetched after the run's "
                        "final drain (the runbook's test 3 keeps it as "
                        "<run>.events.post-drain.jsonl)")
    s = sub.add_parser("replay-check")
    s.add_argument("run_dir")
    s.add_argument("--replay-dir", required=True,
                   help="the replay's simulator directory: its "
                        "sent_events.jsonl names the replayed identities")
    s.add_argument("--prefix", default=None)
    s.add_argument("--events-before", default=None,
                   help="the copy of the log taken before the replay "
                        "(default: <prefix>.events.pre-replay.jsonl)")
    s.add_argument("--from", dest="frm", default="after")
    s.add_argument("--to", default="replay")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.cmd](args)
    except HelperError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
