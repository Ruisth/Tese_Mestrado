"""Operator helper for the ad-hoc itest-* runs of qemu_integrated_gateway.md.

``python -m egw_experiments.itest_reconcile {mark,wait,check,snap,delta,same}``

Runs on the HOST, in the venv where the repository is installed
(pip install -e .../src). It implements NO protocol rule of its own:

- the end-of-run marker is read with egw_experiments.run.poll_controller_marker
  (GET /metrics monotonic_ns, the controller's clock);
- the deadline is marker + egw_experiments.protocol.CONFIRMATION_WINDOW_S,
  the same arithmetic as run.py, written into a harness-shaped manifest. The
  window is always the imported constant: a marker file whose deadline is not
  exactly marker + CONFIRMATION_WINDOW_S is refused, never used;
- delivered / lost / late / duplicate accounting is done by
  egw_experiments.analyze.compute_run_metrics, unchanged.

Every file it writes is a SIBLING of the simulator run directory
(<prefix>.marker.json, <prefix>.twins.<label>.json, ...); the simulator's
write-once run directory itself is never modified by this module. Nothing is
read from the network at import time; only ``mark``, ``wait`` (controller
GET /metrics) and ``snap`` (Ditto GET thing) open a connection.

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
     warm-up), never a second copy of the same records.
- 1  the step was NOT carried out: marker unavailable, a write-once file
     already exists, an input file is missing or malformed, the controller
     clock went backwards, ``wait`` gave up, Ditto unreachable.
- 2  command-line usage error (argparse).
- 3  ``check`` only: the row was computed and saved, but the deadline is not
     on the controller marker (no marker file), so it is NOT a protocol check.
- 4  ``delta``: a per-device or /metrics MISMATCH, accepted records of a device
     that the 'from' snapshot does not hold, or a non-empty queue in the 'to'
     snapshot; ``same``: the two snapshots are DIFFERENT.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from egw_experiments.analyze import compute_run_metrics
from egw_experiments.environment import utc_now_iso
from egw_experiments.protocol import CONFIRMATION_WINDOW_S
from egw_experiments.run import (
    CONTROLLER_MARKER_LAG_TOLERANCE_S,
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


COMMANDS = {"mark": cmd_mark, "wait": cmd_wait, "check": cmd_check,
            "snap": cmd_snap, "delta": cmd_delta, "same": cmd_same}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m egw_experiments.itest_reconcile",
        description=__doc__.splitlines()[0],
        epilog="exit codes: 0 step carried out (check: not a verdict); "
               "1 step not carried out; 2 usage; 3 check: not a protocol "
               "check; 4 delta: MISMATCH or queue not empty, same: DIFFERENT",
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
    s = sub.add_parser("same")
    s.add_argument("--prefix", required=True)
    s.add_argument("label_a")
    s.add_argument("label_b")
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
